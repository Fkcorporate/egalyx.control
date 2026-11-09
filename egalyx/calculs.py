"""
egalyx/calculs.py — calculs « purs » des modules Egalyx (aucune dépendance à Flask ou à la base).
Tout ce qui est ici est couvert par tests/test_calculs.py.
"""
import base64
import hashlib
import hmac
import json
import math
import re
import secrets
import struct
import time
import unicodedata
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from urllib.parse import quote


# ============================================================================
# 1. DOUBLE AUTHENTIFICATION (TOTP — RFC 6238, compatible Google Authenticator,
#    Microsoft Authenticator, FreeOTP…)
# ============================================================================
TOTP_PERIODE = 30
TOTP_CHIFFRES = 6


def totp_nouveau_secret():
    """Secret aléatoire de 160 bits encodé en base32 (format attendu par les applications)."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')


def _hotp(secret_b32, compteur, chiffres=TOTP_CHIFFRES):
    cle = base64.b32decode(secret_b32 + '=' * (-len(secret_b32) % 8), casefold=True)
    mac = hmac.new(cle, struct.pack('>Q', compteur), hashlib.sha1).digest()
    decalage = mac[-1] & 0x0F
    valeur = struct.unpack('>I', mac[decalage:decalage + 4])[0] & 0x7FFFFFFF
    return str(valeur % (10 ** chiffres)).zfill(chiffres)


def totp_code(secret_b32, instant=None):
    return _hotp(secret_b32, int((instant if instant is not None else time.time()) // TOTP_PERIODE))


def totp_verifier(secret_b32, code, dernier_pas_utilise=None, instant=None, tolerance=1):
    """
    Vérifie un code à 6 chiffres (tolérance ± 1 période pour le décalage d'horloge).
    Retourne le numéro de pas accepté (à mémoriser pour interdire la réutilisation du même code),
    ou None si le code est invalide ou déjà utilisé.
    """
    code = re.sub(r'\s', '', str(code or ''))
    if not secret_b32 or not re.fullmatch(r'\d{%d}' % TOTP_CHIFFRES, code):
        return None
    pas = int((instant if instant is not None else time.time()) // TOTP_PERIODE)
    for p in range(pas - tolerance, pas + tolerance + 1):
        if hmac.compare_digest(_hotp(secret_b32, p), code):
            if dernier_pas_utilise is not None and p <= dernier_pas_utilise:
                return None          # code déjà utilisé (rejeu)
            return p
    return None


def totp_uri(secret_b32, compte, emetteur='Egalyx Control'):
    """URI otpauth:// à encoder dans le QR code."""
    libelle = quote(f'{emetteur}:{compte}')
    return (f'otpauth://totp/{libelle}?secret={secret_b32}&issuer={quote(emetteur)}'
            f'&algorithm=SHA1&digits={TOTP_CHIFFRES}&period={TOTP_PERIODE}')


def codes_secours(nombre=8):
    """Codes de secours lisibles (ex. 7KQ4-M2PX), à n'afficher qu'une fois puis stocker hachés."""
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ['-'.join(''.join(secrets.choice(alphabet) for _ in range(4)) for _ in range(2)) for _ in range(nombre)]


def normaliser_code_secours(code):
    return re.sub(r'[^A-Z0-9]', '', str(code or '').upper())


# ============================================================================
# 2. TEXTE : normalisation (sans accents, minuscules) et ressemblance de noms
# ============================================================================
def normaliser_texte(texte):
    t = unicodedata.normalize('NFD', str(texte or ''))
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn').lower()
    t = re.sub(r'[^a-z0-9 ]+', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


_MOTS_VIDES = {'sa', 'sarl', 'sas', 'sasu', 'suarl', 'ltd', 'llc', 'inc', 'gie', 'eurl', 'et', 'de', 'du', 'des', 'la', 'le', 'les', 'l', 'd'}


def similarite_noms(a, b):
    """
    Ressemblance entre deux noms (0 à 1), robuste à l'ordre des mots, aux accents et aux formes juridiques.
    Ex. « Société Générale SA » ~ « GENERALE (SOCIETE) ».
    """
    ma = [m for m in normaliser_texte(a).split() if m not in _MOTS_VIDES]
    mb = [m for m in normaliser_texte(b).split() if m not in _MOTS_VIDES]
    if not ma or not mb:
        return 0.0
    direct = SequenceMatcher(None, ' '.join(ma), ' '.join(mb)).ratio()
    trie = SequenceMatcher(None, ' '.join(sorted(ma)), ' '.join(sorted(mb))).ratio()
    # part des mots du nom le plus court retrouvés (approximativement) dans l'autre
    courts, longs = (ma, mb) if len(ma) <= len(mb) else (mb, ma)
    trouves = sum(1 for m in courts if any(SequenceMatcher(None, m, n).ratio() >= 0.85 for n in longs))
    couverture = trouves / len(courts)
    return round(max(direct, trie, couverture * 0.95 if len(courts) >= 2 else couverture * 0.8), 3)


def cribler(nom, liste, seuil=0.85, alias_separateur=';'):
    """
    Compare un nom à une liste de sanctions. `liste` : itérable de dicts {id, nom, alias, pays, source, programme}.
    Retourne les correspondances triées (score décroissant) au-dessus du seuil.
    """
    resultats = []
    for e in liste:
        noms = [e.get('nom', '')] + [x.strip() for x in str(e.get('alias') or '').split(alias_separateur) if x.strip()]
        meilleur, nom_trouve = 0.0, ''
        for n in noms:
            s = similarite_noms(nom, n)
            if s > meilleur:
                meilleur, nom_trouve = s, n
        if meilleur >= seuil:
            resultats.append({'id': e.get('id'), 'nom_liste': e.get('nom'), 'nom_correspondant': nom_trouve,
                              'score': meilleur, 'source': e.get('source'), 'programme': e.get('programme'),
                              'pays': e.get('pays')})
    return sorted(resultats, key=lambda r: r['score'], reverse=True)


# ============================================================================
# 3. LCB-FT : score de risque d'un tiers et niveau de vigilance
# ============================================================================
# Listes GAFI au 19 juin 2026 (plénière). Le GAFI les révise à chaque plénière (février, juin, octobre) :
# elles sont modifiables par chaque client dans « Paramètres des risques ».
GAFI_LISTE_NOIRE_2026_06 = ['Corée du Nord', 'Iran', 'Myanmar']
GAFI_LISTE_GRISE_2026_06 = [
    'Angola', 'Bolivie', 'Bosnie-Herzégovine', 'Bulgarie', 'Cameroun', "Côte d'Ivoire",
    'République démocratique du Congo', 'Haïti', 'Irak', 'Kenya', 'Koweït', 'Laos', 'Liban', 'Monaco',
    'Népal', 'Papouasie-Nouvelle-Guinée', 'Soudan du Sud', 'Syrie', 'Venezuela', 'Vietnam',
    'Îles Vierges britanniques', 'Yémen',
]
SECTEURS_SENSIBLES = [
    'immobilier', 'casino', 'jeux', 'change', 'crypto', 'actifs numériques', 'métaux précieux', 'or', 'diamant',
    'armement', 'transfert d’argent', "transfert d'argent", 'ong', 'association', 'btp', 'marchés publics',
    'pétrole', 'mines', 'art', 'antiquités', 'véhicules', 'transport maritime',
]

BAREME_LCB = {
    'pays_liste_noire': 50, 'pays_liste_grise': 20, 'ppe': 30, 'secteur_sensible': 15,
    'relation_a_distance': 10, 'beneficiaires_non_identifies': 20, 'structure_complexe': 10,
    'montant_eleve': 10, 'correspondance_sanction': 100,
}
SEUILS_VIGILANCE = (30, 60)   # < 30 simplifiée, < 60 standard, sinon renforcée
DELAI_REVUE_MOIS = {'simplifiee': 36, 'standard': 24, 'renforcee': 12, 'refus': 12}


def _dans(pays, liste):
    p = normaliser_texte(pays)
    return bool(p) and any(p == normaliser_texte(x) for x in (liste or []))


def score_lcb(tiers, liste_noire=None, liste_grise=None, secteurs=None, seuil_montant=None):
    """
    Score LCB-FT d'un tiers (dict ou objet) selon une grille transparente.
    Retourne {score, niveau, facteurs:[(libellé, points)], delai_revue_mois}.
    Une correspondance de sanction CONFIRMÉE impose le niveau « refus ».
    """
    g = (lambda k, d=None: tiers.get(k, d)) if isinstance(tiers, dict) else (lambda k, d=None: getattr(tiers, k, d))
    noire = GAFI_LISTE_NOIRE_2026_06 if liste_noire is None else liste_noire
    grise = GAFI_LISTE_GRISE_2026_06 if liste_grise is None else liste_grise
    secteurs = SECTEURS_SENSIBLES if secteurs is None else secteurs
    facteurs = []
    pays = [x for x in (g('pays'), g('pays_residence')) if x]
    if any(_dans(p, noire) for p in pays):
        facteurs.append(('Pays sur la liste noire du GAFI', BAREME_LCB['pays_liste_noire']))
    elif any(_dans(p, grise) for p in pays):
        facteurs.append(('Pays sur la liste grise du GAFI', BAREME_LCB['pays_liste_grise']))
    if g('est_ppe'):
        facteurs.append(('Personne politiquement exposée (PPE)', BAREME_LCB['ppe']))
    secteur = normaliser_texte(g('secteur'))
    if secteur and any(normaliser_texte(s) in secteur for s in secteurs):
        facteurs.append(("Secteur d'activité sensible", BAREME_LCB['secteur_sensible']))
    if (g('canal') or '') == 'distance':
        facteurs.append(('Relation établie à distance', BAREME_LCB['relation_a_distance']))
    if (g('nature') or 'personne_morale') == 'personne_morale' and not (g('beneficiaires_effectifs') or []):
        facteurs.append(('Bénéficiaires effectifs non identifiés', BAREME_LCB['beneficiaires_non_identifies']))
    if g('structure_complexe'):
        facteurs.append(('Structure de détention complexe', BAREME_LCB['structure_complexe']))
    montant = g('montant_relation')
    if seuil_montant and montant and float(montant) >= float(seuil_montant):
        facteurs.append(('Montant de la relation élevé', BAREME_LCB['montant_eleve']))
    if g('sanction_confirmee'):
        facteurs.append(('Correspondance confirmée sur une liste de sanctions', BAREME_LCB['correspondance_sanction']))
    score = min(100, sum(p for _, p in facteurs))
    if g('sanction_confirmee'):
        niveau = 'refus'
    elif score < SEUILS_VIGILANCE[0]:
        niveau = 'simplifiee'
    elif score < SEUILS_VIGILANCE[1]:
        niveau = 'standard'
    else:
        niveau = 'renforcee'
    return {'score': score, 'niveau': niveau, 'facteurs': facteurs, 'delai_revue_mois': DELAI_REVUE_MOIS[niveau]}


def ajouter_mois(d, mois):
    a, m = divmod(d.month - 1 + mois, 12)
    annee, mois_ = d.year + a, m + 1
    jours = [31, 29 if (annee % 4 == 0 and (annee % 100 != 0 or annee % 400 == 0)) else 28,
             31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mois_ - 1]
    return d.replace(year=annee, month=mois_, day=min(d.day, jours))


# ============================================================================
# 4. FOURNISSEURS : criticité
# ============================================================================
def criticite_fournisseur(impact_arret, dependance_pct, substituable, note_evaluation=None):
    """
    impact_arret : 1 (faible) à 4 (bloquant) ; dependance_pct : part de l'activité ; substituable : bool ;
    note_evaluation : dernière note qualité /5 (facultative). Retourne (score 0-100, niveau).
    """
    s = (int(impact_arret or 1) - 1) * 20                      # 0 à 60
    s += min(25, int((dependance_pct or 0) / 4))               # 0 à 25
    s += 0 if substituable else 15
    if note_evaluation is not None and float(note_evaluation) < 3:
        s += 10
    s = min(100, s)
    niveau = 'faible' if s < 25 else 'moyenne' if s < 50 else 'elevee' if s < 75 else 'critique'
    return s, niveau


# ============================================================================
# 5. SIGNATURE INTERNE : empreinte d'un document
# ============================================================================
CHAMPS_EXCLUS_EMPREINTE = {'updated_at', 'last_login', 'derniere_activite', 'last_request_at', 'total_requests',
                           'nb_vues', 'vues', 'read_at', 'est_lue'}


def _jsonable(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, (bytes, bytearray)):
        return hashlib.sha256(v).hexdigest()
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def empreinte(contenu):
    """SHA-256 d'un contenu (dict/list) sérialisé de façon canonique (clés triées, sans espaces)."""
    def nettoyer(x):
        if isinstance(x, dict):
            return {str(k): nettoyer(v) for k, v in x.items() if k not in CHAMPS_EXCLUS_EMPREINTE}
        if isinstance(x, (list, tuple)):
            return [nettoyer(v) for v in x]
        return _jsonable(x)
    texte = json.dumps(nettoyer(contenu), sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str)
    return hashlib.sha256(texte.encode('utf-8')).hexdigest()


def code_numerique(chiffres=6):
    return ''.join(secrets.choice('0123456789') for _ in range(chiffres))


# ============================================================================
# 6. PAIEMENT
# ============================================================================
EUR_XOF = 655.957          # parité fixe euro / franc CFA (UEMOA et CEMAC : XAF identique)


def montant_xof(montant_eur):
    """Conversion EUR → XOF/XAF, arrondie au multiple de 5 supérieur (exigence CinetPay)."""
    return int(math.ceil(float(montant_eur) * EUR_XOF / 5.0) * 5)


def montant_centimes(montant):
    return int(round(float(montant) * 100))


def verifier_signature_stripe(corps, entete_signature, secret, tolerance_s=300, maintenant=None):
    """
    Vérifie l'en-tête Stripe-Signature (t=…,v1=…) : HMAC-SHA256(secret, f"{t}.{corps}").
    Refuse les événements de plus de `tolerance_s` secondes (protection contre le rejeu).
    """
    if not (corps is not None and entete_signature and secret):
        return False
    morceaux = dict(p.split('=', 1) for p in entete_signature.split(',') if '=' in p)
    ts = morceaux.get('t')
    signatures = [v for k, v in (p.split('=', 1) for p in entete_signature.split(',') if '=' in p) if k == 'v1']
    if not ts or not signatures:
        return False
    try:
        if abs((maintenant if maintenant is not None else time.time()) - int(ts)) > tolerance_s:
            return False
    except ValueError:
        return False
    corps_b = corps if isinstance(corps, bytes) else str(corps).encode('utf-8')
    attendu = hmac.new(secret.encode('utf-8'), ts.encode() + b'.' + corps_b, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(attendu, s) for s in signatures)


def periode_abonnement(debut, periode):
    """Fin d'un abonnement payé (inclus) : +1 mois ou +12 mois, moins un jour."""
    return ajouter_mois(debut, 12 if periode == 'annuel' else 1) - timedelta(days=1)


# ============================================================================
# 7. APPÉTENCE AU RISQUE
# ============================================================================
def seuil_appetence(categorie, seuil_global, par_categorie=None):
    """Seuil applicable : celui de la catégorie s'il est défini, sinon le seuil global (None = pas de limite)."""
    par_categorie = par_categorie or {}
    cle = normaliser_texte(categorie)
    for k, v in par_categorie.items():
        if normaliser_texte(k) == cle and v not in (None, ''):
            return float(v)
    return float(seuil_global) if seuil_global not in (None, '') else None


def depasse_appetence(score_net, categorie, seuil_global, par_categorie=None):
    s = seuil_appetence(categorie, seuil_global, par_categorie)
    return s is not None and score_net is not None and float(score_net) > s


def valider_seuils(faible, moyen, eleve):
    """Seuils de cotation : 1 ≤ faible < moyen < élevé < 25. Retourne la liste des erreurs."""
    erreurs = []
    try:
        f, m, e = float(faible), float(moyen), float(eleve)
    except (TypeError, ValueError):
        return ['Les seuils doivent être des nombres.']
    if not (1 <= f < m < e < 25):
        erreurs.append('Les seuils doivent respecter 1 ≤ Faible < Moyen < Élevé < 25.')
    return erreurs
