"""
egalyx/anti_spam_contact.py — anti-spam du formulaire « Demande de démonstration » (/api/contact).

Sans service extérieur (pas de Google reCAPTCHA : aucun cookie, aucune clé, rien à déclarer à la CNIL) :
  1. petite question à résoudre (« Combien font sept plus quatre ? »), écrite en lettres pour gêner les robots ;
  2. champ piège invisible : un humain le laisse vide, un robot le remplit → faux « succès », rien n'est envoyé ;
  3. délai minimal : un formulaire envoyé moins de 3 s après l'affichage est refusé ;
  4. jeton signé à usage unique, valable 2 h (impossible de rejouer la même réponse) ;
  5. limite par adresse IP : 5 messages par heure.
La question vient de GET /api/contact/defi (appelée par la page d'accueil).
Coupure d'urgence : EGALYX_ANTI_SPAM_CONTACT=0.
"""
import hashlib
import os
import random
import secrets
import threading
import time

from flask import current_app, jsonify, request
from itsdangerous import BadSignature, URLSafeTimedSerializer

NOMBRES = ['zéro', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix']
DELAI_MIN, DUREE_MAX, PAR_HEURE = 3, 2 * 3600, 5
CHAMP_PIEGE = 'site_web'
_verrou = threading.Lock()
_utilises = {}          # nonce -> expiration
_envois = {}            # ip -> [horodatages]


def actif():
    return (os.environ.get('EGALYX_ANTI_SPAM_CONTACT') or '1').strip() != '0'


def _signeur():
    return URLSafeTimedSerializer(current_app.secret_key, salt='egalyx-contact-defi')


def _empreinte(reponse, nonce):
    return hashlib.sha256(f'{nonce}:{reponse}'.encode()).hexdigest()[:24]


def _ip():
    fwd = (request.headers.get('X-Forwarded-For') or '').split(',')[-1].strip()   # ajoutée par le proxy de Render (la 1re peut être inventée)
    return fwd or request.remote_addr or '?'


def nouveau_defi():
    a, b = random.randint(1, 9), random.randint(1, 9)
    if random.random() < .3 and a != b:
        a, b = max(a, b), min(a, b)
        question, reponse = f'Combien font {NOMBRES[a]} moins {NOMBRES[b]} ?', a - b
    else:
        question, reponse = f'Combien font {NOMBRES[a]} plus {NOMBRES[b]} ?', a + b
    nonce = secrets.token_urlsafe(9)
    jeton = _signeur().dumps({'n': nonce, 'h': _empreinte(reponse, nonce), 't': time.time()})
    return {'question': question + ' (répondez en chiffres)', 'jeton': jeton}


def _menage(maintenant):
    for k in [k for k, v in _utilises.items() if v < maintenant]:
        _utilises.pop(k, None)
    for ip in list(_envois):
        _envois[ip] = [t for t in _envois[ip] if t > maintenant - 3600]
        if not _envois[ip]:
            _envois.pop(ip, None)


def verifier(data):
    """None si tout va bien ; sinon (code, message, faux_succes)."""
    if (data.get(CHAMP_PIEGE) or '').strip():
        return 200, 'piège', True
    jeton, reponse = (data.get('defi_jeton') or '').strip(), (data.get('defi_reponse') or '').strip()
    if not jeton or not reponse:
        return 400, 'Répondez à la petite question anti-spam avant d’envoyer.', False
    try:
        contenu = _signeur().loads(jeton, max_age=DUREE_MAX)
    except BadSignature:
        return 400, 'La question anti-spam a expiré : rechargez la page puis réessayez.', False
    maintenant = time.time()
    if maintenant - float(contenu.get('t', 0)) < DELAI_MIN:
        return 400, 'Envoi trop rapide : relisez votre message puis réessayez.', False
    try:
        valeur = int(reponse.replace(' ', ''))
    except ValueError:
        return 400, 'Réponse anti-spam incorrecte : écrivez le résultat en chiffres.', False
    if _empreinte(valeur, contenu.get('n', '')) != contenu.get('h'):
        return 400, 'Réponse anti-spam incorrecte. Une nouvelle question vous est proposée.', False
    ip = _ip()
    with _verrou:
        _menage(maintenant)
        if contenu['n'] in _utilises:
            return 400, 'Cette question a déjà servi : rechargez la page puis réessayez.', False
        if len(_envois.get(ip, [])) >= PAR_HEURE:
            return 429, 'Trop de messages envoyés depuis votre connexion. Réessayez dans une heure ou écrivez-nous directement.', False
        _utilises[contenu['n']] = maintenant + DUREE_MAX
        _envois.setdefault(ip, []).append(maintenant)
    return None


def enregistrer(app, csrf=None):
    from egalyx.commun import exempter_controle_ancien

    @app.route('/api/contact/defi')
    def contact_defi():
        r = jsonify(nouveau_defi() if actif() else {'question': None, 'jeton': None})
        r.headers['Cache-Control'] = 'no-store'
        return r
    exempter_controle_ancien(app, {'contact_defi'})
    try:
        from egalyx import double_auth
        double_auth._LIBRES.update({'contact_defi'})
    except Exception:  # noqa: BLE001
        pass

    origine = app.view_functions.get('api_contact')
    if origine is None:
        return

    def api_contact_protege(*a, **k):
        if actif():
            data = (request.get_json(silent=True) or {}) if request.is_json else request.form
            refus = verifier(data)
            if refus:
                code, message, faux_succes = refus
                current_app.logger.warning('Formulaire de contact bloqué (%s) depuis %s', message if not faux_succes else 'champ piège', _ip())
                if faux_succes:      # ne rien apprendre au robot
                    return jsonify({'success': True, 'message': 'Votre demande a été envoyée avec succès !'}), 200
                return jsonify({'success': False, 'message': message, 'errors': [message], 'nouveau_defi': True}), code
        return origine(*a, **k)

    api_contact_protege.__name__ = origine.__name__
    api_contact_protege.__doc__ = origine.__doc__
    app.view_functions['api_contact'] = api_contact_protege
