"""
egalyx/kri_sources_securite.py — collecte automatique des KRI (« Sources de données ») sécurisée.

Faille corrigée (recette nov. 2026) : un administrateur client ou un gestionnaire pouvait créer une
source « Base de données → SQLite » pointant vers la base d'Egalyx et y lire les données de TOUTES les
organisations ; une source « Fichier » lisait n'importe quel fichier du serveur ; une source « API »
appelait n'importe quelle adresse, y compris interne, sans délai maximum.

1. Les écrans et API des sources sont réservés au super-administrateur (403 pour les autres).
2. Quel que soit l'écran (ou le planificateur), le moteur de collecte refuse :
   - SQLite et les fichiers du serveur ;
   - une API qui n'est pas en https, ou dont l'adresse mène à un réseau interne / privé ;
   - une base PostgreSQL / MySQL hébergée sur une adresse interne / privée.
   Les appels API ont un délai maximum (15 s), ne suivent pas les redirections et sont limités à 5 Mo.
3. Une source dangereuse est refusée dès l'enregistrement (même par un script).
4. Les messages d'erreur montrés à l'écran sont génériques ; le détail part dans le journal du serveur.
5. Formules de transformation : `eval` remplacé par un calcul limité aux opérations arithmétiques.
6. Statistiques d'un KRI : la « dernière valeur » est la plus récente par date (et non par ordre de saisie).
7. Les anciennes routes en double de /kri/<id>/modifier renvoient vers la vraie page de modification.
"""
import ast
import ipaddress
import logging
import operator
import socket
from functools import wraps
from urllib.parse import urlparse

from flask import abort, jsonify, request
from flask_login import current_user

journal = logging.getLogger('egalyx.kri_sources')

VUES_RESERVEES = (
    'liste_sources_donnees', 'nouvelle_source_donnee', 'editer_source_donnee', 'detail_source_donnee',
    'executer_source', 'lier_source_kri', 'lier_source_kri_api', 'stats_sources', 'api_sources_disponibles',
    'synchroniser_kri_manuel', 'api_transformateurs',
)
DELAI = 15
TAILLE_MAX = 5 * 1024 * 1024


class SourceRefusee(ValueError):
    pass


# --------------------------------------------------------------------------- adresses autorisées
def _adresses(hote):
    try:
        return {i[4][0] for i in socket.getaddrinfo(hote, None)}
    except (socket.gaierror, UnicodeError):
        raise SourceRefusee("Adresse introuvable")


def hote_public(hote):
    """Vrai si toutes les adresses IP de l'hôte sont publiques (ni locale, ni privée, ni réservée)."""
    if not hote:
        return False
    for a in _adresses(hote.strip('[]')):
        ip = ipaddress.ip_address(a.split('%')[0])
        if getattr(ip, 'ipv4_mapped', None):
            ip = ip.ipv4_mapped
        if not ip.is_global or ip.is_multicast:
            return False
    return True


def verifier_url(url):
    u = urlparse((url or '').strip())
    if u.scheme != 'https' or not u.hostname:
        raise SourceRefusee("Seules les adresses https:// sont acceptées")
    if u.username or u.password:
        raise SourceRefusee("Identifiants interdits dans l'adresse : utilisez l'authentification de la source")
    if not hote_public(u.hostname):
        raise SourceRefusee("Adresse interne ou privée refusée")
    return url


def probleme_source(type_source, config):
    """Message si la source est dangereuse, sinon None. Ne fait pas de requête réseau pour 'base_donnees' interne évidente."""
    config = config or {}
    try:
        if type_source == 'fichier':
            return "Les fichiers du serveur ne peuvent pas servir de source"
        if type_source == 'base_donnees':
            if (config.get('type') or 'postgresql') not in ('postgresql', 'mysql'):
                return "Seules les bases PostgreSQL et MySQL externes sont acceptées"
            if not hote_public(config.get('host')):
                return "Base hébergée sur une adresse interne ou privée : refusée"
        if type_source == 'api':
            verifier_url(config.get('url'))
    except SourceRefusee as e:
        return str(e)
    return None


# --------------------------------------------------------------------------- moteur de collecte
def _patcher_moteur():
    try:
        import collecte_engine
    except ImportError:
        return
    M = collecte_engine.CollecteEngine
    if getattr(M, '_egalyx_securise', False):
        return

    def _recuperer_donnees_brutes(self, source):
        msg = probleme_source(source.type_source, source.config_connexion)
        if msg:
            raise SourceRefusee(msg)
        if source.type_source not in ('api', 'base_donnees'):
            raise SourceRefusee("Type de source non pris en charge")
        return M._egalyx_origine_brutes(self, source)

    def _recuperer_depuis_fichier(self, config):
        raise SourceRefusee("Les fichiers du serveur ne peuvent pas servir de source")

    def _recuperer_depuis_api(self, config, auth):
        import json as _json
        import requests
        url = verifier_url(config.get('url'))
        method = (config.get('method') or 'GET').upper()
        if method not in ('GET', 'POST'):
            raise SourceRefusee("Méthode non autorisée")
        headers = config.get('headers') or {}
        if isinstance(headers, str):
            try:
                headers = _json.loads(headers or '{}')
            except ValueError:
                headers = {}
        headers = {str(k): str(v) for k, v in dict(headers).items()}
        params = dict(config.get('params') or {})
        auth_tuple = None
        if auth:
            t = auth.get('type')
            if t == 'bearer':
                headers['Authorization'] = f"Bearer {auth.get('token')}"
            elif t == 'basic':
                auth_tuple = (auth.get('username'), auth.get('password'))
            elif t == 'api_key':
                if str(auth.get('in_header', 'true')).lower() in ('1', 'true', 'oui', 'on'):
                    headers[auth.get('key_name')] = auth.get('key_value')
                else:
                    params[auth.get('key_name')] = auth.get('key_value')
        r = requests.request(method, url, headers=headers, params=params, auth=auth_tuple,
                             timeout=DELAI, allow_redirects=False, stream=True)
        if 300 <= r.status_code < 400:
            raise SourceRefusee("Redirection refusée : indiquez l'adresse finale de l'API")
        r.raise_for_status()
        contenu = b''
        for bloc in r.iter_content(65536):
            contenu += bloc
            if len(contenu) > TAILLE_MAX:
                raise SourceRefusee("Réponse trop volumineuse (5 Mo maximum)")
        r._content = contenu
        return self._parse_reponse_api(r)

    def _recuperer_depuis_bdd(self, config, auth):
        if (config.get('type') or 'postgresql') not in ('postgresql', 'mysql'):
            raise SourceRefusee("Seules les bases PostgreSQL et MySQL externes sont acceptées")
        if not hote_public(config.get('host')):
            raise SourceRefusee("Base hébergée sur une adresse interne ou privée : refusée")
        requete = (config.get('requete') or '').strip().rstrip(';')
        if not requete.lower().startswith(('select', 'with')) or ';' in requete:
            raise SourceRefusee("Une seule requête de lecture (SELECT) est acceptée")
        return M._egalyx_origine_bdd(self, dict(config, requete=requete), auth)

    def collecter_source(self, source_id, force=False):
        try:
            res = M._egalyx_origine_collecter(self, source_id, force)
        except SourceRefusee as e:
            return {'success': False, 'error': str(e), 'erreurs': [{'global': str(e)}], 'kri_collectes': []}
        if isinstance(res, dict):
            propres = []
            for e in res.get('erreurs') or []:
                journal.warning("Collecte source %s : %s", source_id, e)
                if isinstance(e, dict):
                    propres.append({k: (_message_public(v) if k in ('global', 'erreur', 'error') else v)
                                    for k, v in e.items()})
                else:
                    propres.append({'global': _message_public(e)})
            res['erreurs'] = propres
            if res.get('error'):
                res['error'] = _message_public(res['error'])
        return res

    M._egalyx_origine_brutes = M._recuperer_donnees_brutes
    M._egalyx_origine_bdd = M._recuperer_depuis_bdd
    M._egalyx_origine_collecter = M.collecter_source
    M._recuperer_donnees_brutes = _recuperer_donnees_brutes
    M._recuperer_depuis_fichier = _recuperer_depuis_fichier
    M._recuperer_depuis_api = _recuperer_depuis_api
    M._recuperer_depuis_bdd = _recuperer_depuis_bdd
    M.collecter_source = collecter_source
    M._egalyx_securise = True


MESSAGES_SURS = ("Source inexistante", "Source inactive", "Pas encore l'heure de la collecte")


def _message_public(m):
    m = str(m or '')
    if m in MESSAGES_SURS or any(m.startswith(p) for p in (
            "Seules", "Les fichiers", "Base hébergée", "Adresse", "Identifiants", "Méthode", "Redirection",
            "Réponse trop", "Une seule requête", "Type de source", "Valeur")):
        return m
    return "La collecte a échoué : vérifiez l'adresse, l'authentification et le chemin de la donnée (détail dans le journal du serveur)."


# --------------------------------------------------------------------------- formules sans eval
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Mod: operator.mod, ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}
_FONCTIONS = {'sum': sum, 'len': len, 'min': min, 'max': max, 'abs': abs, 'round': round}


def calculer(formule, contexte):
    """Arithmétique (+ - * / % **), nombres, variables du contexte, donnees[...] et sum/len/min/max/abs/round."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float, str)):
            return n.value
        if isinstance(n, ast.Name):
            if n.id in contexte:
                return contexte[n.id]
            raise ValueError(f"variable inconnue : {n.id}")
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(b) > 10:
                raise ValueError("puissance trop grande")
            return _OPS[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))
        if isinstance(n, ast.Subscript):
            return ev(n.value)[ev(n.slice)]
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FONCTIONS and not n.keywords:
            return _FONCTIONS[n.func.id](*[ev(a) for a in n.args])
        if isinstance(n, (ast.List, ast.Tuple)):
            return [ev(e) for e in n.elts]
        raise ValueError("élément de formule non autorisé")
    if len(formule or '') > 500:
        raise ValueError("formule trop longue")
    return ev(ast.parse(formule or 'donnees', mode='eval'))


# --------------------------------------------------------------------------- enregistrement
def enregistrer(app):
    from sqlalchemy import event
    import models as M
    from models import db

    _patcher_moteur()

    # 1. écrans réservés au super-administrateur
    def reserve(vue):
        @wraps(vue)
        def garde(*a, **k):
            if not (current_user.is_authenticated and getattr(current_user, 'is_super_admin', False)):
                if request.path.startswith('/api/') or request.is_json or request.method != 'GET':
                    return jsonify({'success': False, 'error': "Réservé au super-administrateur"}), 403
                abort(403)
            return vue(*a, **k)
        return garde

    for nom in VUES_RESERVEES:
        if nom in app.view_functions and not getattr(app.view_functions[nom], '_egalyx_reserve', False):
            app.view_functions[nom] = reserve(app.view_functions[nom])
            app.view_functions[nom]._egalyx_reserve = True

    # 3. refus à l'enregistrement (tout écran, tout script)
    Source = getattr(M, 'SourceDonnee', None)
    if Source is not None:
        def _controle(session, _ctx, _inst):
            for o in list(session.new) + list(session.dirty):
                if isinstance(o, Source):
                    msg = probleme_source(o.type_source, o.config_connexion)
                    if msg:
                        raise SourceRefusee(msg)
        from sqlalchemy.orm import Session
        if not getattr(Source, '_egalyx_controle', False):
            event.listen(Session, 'before_flush', _controle)
            Source._egalyx_controle = True

        # message lisible plutôt qu'une erreur 500 si la source est refusée
        for nom in ('nouvelle_source_donnee', 'editer_source_donnee'):
            v = app.view_functions.get(nom)
            if v is None:
                continue

            def lisible(v=v):
                @wraps(v)
                def f(*a, **k):
                    if request.method == 'POST' and request.form.get('type_source'):
                        fo = request.form
                        msg = probleme_source(fo.get('type_source'), {
                            'url': fo.get('api_url'), 'type': fo.get('bdd_type'), 'host': fo.get('bdd_host'),
                            'chemin': fo.get('fichier_chemin')})
                        if msg:
                            from flask import flash, redirect
                            flash(f"Source refusée : {msg}", 'danger')
                            return redirect(request.url)
                    try:
                        return v(*a, **k)
                    except SourceRefusee as e:
                        db.session.rollback()
                        from flask import flash, redirect, url_for
                        flash(f"Source refusée : {e}", 'danger')
                        return redirect(request.url)
                f._egalyx_reserve = True
                return f
            app.view_functions[nom] = lisible()

    # 5. formules sans eval
    T = getattr(M, 'TransformateurDonnee', None)
    if T is not None and hasattr(T, '_appliquer_formule'):
        def _appliquer_formule(self, donnees, **kwargs):
            try:
                return calculer((self.config or {}).get('formule', 'donnees'), {'donnees': donnees, **kwargs})
            except Exception as e:
                raise ValueError(f"Erreur formule: {e}")
        T._appliquer_formule = _appliquer_formule

    # 6. statistiques triées par date
    K = getattr(M, 'KRI', None)
    if K is not None:
        def get_statistiques(self):
            mesures = sorted([m for m in (self.mesures or []) if m.valeur is not None],
                             key=lambda m: (m.date_mesure is None, m.date_mesure))
            if not mesures:
                return None
            v = [m.valeur for m in mesures]
            return {'moyenne': sum(v) / len(v), 'min': min(v), 'max': max(v), 'nb_mesures': len(v),
                    'derniere_valeur': v[-1]}
        K.get_statistiques = get_statistiques

    # 7. routes en double de /kri/<id>/modifier : même vue que la route principale
    principale = app.view_functions.get('modifier_kri')
    if principale is not None:
        for nom in ('afficher_modifier_kri', 'traiter_modifier_kri'):
            if nom in app.view_functions:
                app.view_functions[nom] = principale
