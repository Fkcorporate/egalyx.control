"""
egalyx/aide.py — centre d'aide (/aide) et moteur de réponse de l'assistant.

- Recherche plein texte sans dépendance ni IA : normalisation (accents, casse), racines,
  synonymes, correction des fautes de frappe, pondération par champ et par rareté du mot.
- Visibilité : un visiteur non connecté ne voit que les fiches « public » (connexion, mot de
  passe, 2FA, alerte) ; les fiches super administrateur ne sont visibles que de lui ; pour une
  fonction à laquelle la personne n'a pas accès, la fiche le dit et ne propose pas de lien.
- repondre(question) : réponse prête pour le widget de l'assistant (texte, boutons, suggestions)
  ou None si aucune fiche ne correspond avec assez de confiance.
"""
import difflib
import math
import re
import unicodedata

from flask import Blueprint, abort, jsonify, render_template, request, url_for
from flask_login import current_user

from egalyx.aide_contenu import ARTICLES, CATEGORIES, GLOSSAIRE, article

bp = Blueprint('aide', __name__, url_prefix='/aide')

# ----------------------------------------------------------------------
# Texte
# ----------------------------------------------------------------------
MOTS_VIDES = set("""
a au aux avec ce ces cet cette c ca d dans de des du elle en est et etre il ils j je l la le les leur lui m ma
mais me mes moi mon n ne nos notre nous on ou par pas pour qu que quel quelle quelles quels qui sa se ses si son
sur t ta te tes toi ton tu un une vos votre vous y comment faire fait faut peut peux puis veux voudrais
dois doit bien tout tous toute toutes quoi ya il y a est-ce svp merci bonjour stp aussi encore deja alors donc
egalyx outil logiciel application appli
""".split())

# Équivalences : on ramène chaque mot à un terme commun (après normalisation)
SYNONYMES = {
    'mdp': 'motdepasse', 'password': 'motdepasse', 'pwd': 'motdepasse',
    'carto': 'cartographie', 'cartos': 'cartographie',
    'reco': 'recommandation', 'recos': 'recommandation',
    'dmr': 'dispositif', 'pa': 'plan', 'pda': 'plan',
    'bcp': 'pca', 'pra': 'pca', 'lcbft': 'lcb', 'aml': 'lcb', 'blanchiment': 'lcb',
    'kyc': 'tiers', 'whistleblowing': 'alerte', 'lanceur': 'alerte',
    'mail': 'email', 'mails': 'email', 'courriel': 'email', 'courriels': 'email', 'e': 'email',
    'mfa': '2fa', 'totp': '2fa', 'otp': '2fa', 'authenticator': '2fa', 'authentificateur': '2fa',
    'login': 'connexion', 'connecter': 'connexion', 'connecte': 'connexion',
    'bug': 'erreur', 'bogue': 'erreur', 'plante': 'erreur', 'crash': 'erreur',
    'payement': 'paiement', 'payer': 'paiement', 'momo': 'mobile',
    'dashboard': 'tableau', 'reporting': 'rapport',
    'supprimer': 'archiver', 'effacer': 'archiver',
    'droit': 'permission', 'droits': 'permission', 'habilitation': 'permission', 'habilitations': 'permission',
    'acces': 'permission',
    'ajouter': 'creer', 'nouveau': 'creer', 'nouvelle': 'creer', 'nouvel': 'creer', 'cree': 'creer', 'creation': 'creer',
    'lgbt': 'lcb', 'lbc': 'lcb',
}


def normaliser(texte):
    t = unicodedata.normalize('NFD', (texte or '').lower())
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', ' ', t.replace("'", ' ').replace('’', ' ')).strip()


def racine(mot):
    mot = SYNONYMES.get(mot, mot)
    if mot.isdigit() or len(mot) <= 3:
        return mot
    for fin in ('ements', 'ement', 'ations', 'ation', 'ences', 'ence', 'ables', 'able', 'ees', 'ee', 'es', 'er', 'ez', 's', 'x', 'e'):
        if mot.endswith(fin) and len(mot) - len(fin) >= 4:
            mot = mot[:-len(fin)]
            break
    return mot[:7]


def termes(texte, garder_vides=False):
    sortie = []
    for m in normaliser(texte).split():
        if not garder_vides and (m in MOTS_VIDES or len(m) < 2):
            continue
        sortie.append(racine(m))
    return sortie


# ----------------------------------------------------------------------
# Index (construit une fois)
# ----------------------------------------------------------------------
POIDS = (('mots', 3.0), ('titre', 2.5), ('questions', 2.0), ('resume', 1.0), ('notes', 0.5), ('etapes', 0.5))
_INDEX = None


def _construire():
    docs = []
    for a in ARTICLES:
        champs = {}
        for nom, _poids in POIDS:
            v = a.get(nom)
            texte = ' '.join(v) if isinstance(v, list) else (v or '')
            champs[nom] = set(termes(texte))
        docs.append((a, champs))
    for terme, definition in GLOSSAIRE:
        a = {'id': 'glossaire-' + normaliser(terme).replace(' ', '-'), 'cat': 'glossaire', 'titre': terme,
             'resume': definition, 'etapes': [], 'notes': [], 'mots': [], 'liens': [], 'perms': None,
             'pour': 'public', 'questions': [], 'glossaire': True}
        docs.append((a, {'mots': set(termes(terme)), 'titre': set(termes(terme)), 'questions': set(),
                         'resume': set(termes(definition)), 'notes': set(), 'etapes': set()}))
    df = {}
    for _a, champs in docs:
        for t in set().union(*champs.values()):
            df[t] = df.get(t, 0) + 1
    n = len(docs)
    idf = {t: math.log(1 + n / f) for t, f in df.items()}
    return {'docs': docs, 'idf': idf, 'vocab': sorted(idf)}


def index():
    global _INDEX
    if _INDEX is None:
        _INDEX = _construire()
    return _INDEX


def _corriger(t, vocab):
    if t in vocab or len(t) < 6:
        return t
    proche = difflib.get_close_matches(t, vocab, n=1, cutoff=0.86)
    return proche[0] if proche else t


# ----------------------------------------------------------------------
# Droits
# ----------------------------------------------------------------------
def _connecte(u):
    return bool(u is not None and getattr(u, 'is_authenticated', False))


def _super_admin(u):
    return _connecte(u) and (getattr(u, 'role', None) == 'super_admin' or bool(getattr(u, 'is_super_admin', False)))


def _admin(u):
    return _super_admin(u) or (_connecte(u) and (getattr(u, 'role', None) == 'admin'
                                                 or bool(getattr(u, 'is_client_admin', False))))


def _a_perm(u, perms):
    if not perms or _super_admin(u):
        return True
    if not _connecte(u):
        return False
    f = getattr(u, 'has_permission', None)
    try:
        return any(f(p) for p in perms) if f else any(getattr(u, p, False) for p in perms)
    except Exception:
        return False


def visible(a, u=None):
    u = current_user if u is None else u
    if a['pour'] == 'super_admin':
        return _super_admin(u)
    if not _connecte(u):
        return a['pour'] == 'public'
    return True


def acces(a, u=None):
    """(autorisé, message) — message explique quoi faire quand ce n'est pas autorisé."""
    u = current_user if u is None else u
    if a['pour'] == 'admin' and not _admin(u) and (not a['perms'] or not _a_perm(u, a['perms'])):
        return False, ('Cette opération est réservée à l’administrateur de votre organisation : '
                       'transmettez-lui votre demande.')
    if not _a_perm(u, a['perms']):
        return False, ('Vous n’avez pas accès à cette fonction. Demandez à votre administrateur la permission '
                       'correspondante (ou l’activation du module pour votre organisation).')
    return True, None


def liens(a, u=None):
    ok, _ = acces(a, u)
    if not ok:
        return []
    sortie = []
    for libelle, endpoint in a['liens']:
        try:
            sortie.append({'libelle': libelle, 'url': url_for(endpoint)})
        except Exception:
            continue                     # page absente de cette installation
    return sortie


# ----------------------------------------------------------------------
# Recherche
# ----------------------------------------------------------------------
def chercher(question, u=None, n=5):
    """[(score, article)] triés ; score ≈ part pondérée de la question couverte par la fiche (0 à 3)."""
    u = current_user if u is None else u
    idx = index()
    vocab_set = idx['idf']
    q = []
    for t in termes(question):
        t = _corriger(t, idx['vocab']) if t not in vocab_set else t
        if t not in q:
            q.append(t)
    if not q:
        return []
    total = sum(idx['idf'].get(t, 1.5) for t in q)
    resultats = []
    texte_q = normaliser(question)
    veut_guide = bool(set(texte_q.split()) & {'guide', 'guides', 'capture', 'captures', 'image', 'images', 'illustre',
                                               'tutoriel', 'tuto', 'ecran', 'ecrans', 'montre', 'montrer', 'video'})
    for a, champs in idx['docs']:
        if not visible(a, u):
            continue
        s, s2 = 0.0, 0.0
        for t in q:
            presents = [p for nom, p in POIDS if t in champs[nom]]
            s += max(presents, default=0) * idx['idf'].get(t, 0)
            s2 += sum(presents) * idx['idf'].get(t, 0)       # départage : mot présent dans plusieurs champs
        if not s:
            continue
        score = s / total + 0.05 * s2 / total
        # bonus : phrase type ou titre presque identique
        for phrase in a['questions'] + [normaliser(a['titre'])]:
            if phrase and difflib.SequenceMatcher(None, texte_q, phrase).ratio() > 0.8:
                score += 1.5
                break
        if a.get('glossaire'):
            score *= 0.85
        elif a.get('illustrations') and not veut_guide:
            score *= 0.85                    # à question égale, la fiche courte répond plus vite ; le guide reste juste derrière
        resultats.append((round(score, 3), a))
    resultats.sort(key=lambda x: -x[0])
    return resultats[:n]


SEUIL_REPONSE = 1.1          # en dessous : pas assez sûr pour répondre seul


def repondre(question, u=None, seuil=SEUIL_REPONSE):
    """Réponse pour l'assistant, ou None."""
    u = current_user if u is None else u
    res = chercher(question, u, n=4)
    if not res or res[0][0] < seuil:
        return None
    score, a = res[0]
    ok, message = acces(a, u)
    lignes = [f"**{a['titre']}**", a['resume']]
    if a['etapes']:
        lignes += [f"{i}. {e}" for i, e in enumerate(a['etapes'], 1)]
    for note in a['notes'][:2]:
        lignes.append('💡 ' + note)
    if not ok:
        lignes.append('🔒 ' + message)
    actions = [{'libelle': l['libelle'], 'url': l['url'], 'icone': 'fa-external-link-alt'} for l in liens(a, u)]
    if not a.get('glossaire'):
        try:
            actions.append({'libelle': 'Fiche complète', 'url': url_for('aide.fiche', id_=a['id']), 'icone': 'fa-book-open'})
        except Exception:
            pass
    suggestions = [b['titre'] for s, b in res[1:] if s >= seuil * 0.6 and not b.get('glossaire')][:2]
    return {'texte': '\n'.join(lignes), 'cartes': [], 'actions': actions[:4], 'suggestions': suggestions,
            'intention': 'base_connaissances', 'article': a['id'], 'score': score}


def proches(question, u=None, n=3):
    """Titres des fiches les plus proches, pour aider quand la réponse n'est pas sûre."""
    return [a['titre'] for s, a in chercher(question, u, n=n + 2) if s >= 0.35 and not a.get('glossaire')][:n]


# ----------------------------------------------------------------------
# Pages
# ----------------------------------------------------------------------
def _categories_visibles(u):
    sortie = []
    for code, titre, icone in CATEGORIES:
        arts = [a for a in ARTICLES if a['cat'] == code and visible(a, u)]
        if arts:
            sortie.append({'code': code, 'titre': titre, 'icone': icone, 'articles': arts})
    return sortie


def _rendu(texte):
    """**gras** uniquement ; le reste est échappé."""
    from markupsafe import Markup, escape
    return Markup(re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', str(escape(texte))))


@bp.route('/')
def accueil():
    q = (request.args.get('q') or '').strip()[:200]
    resultats = [a for _s, a in chercher(q, n=12)] if q else []
    guides = [a for a in ARTICLES if a.get('illustrations') and visible(a)]
    return render_template('egalyx/aide_index.html', categories=[c for c in _categories_visibles(current_user)
                                                                 if not guides or c['code'] != 'guide'],
                           q=q, resultats=resultats, guides=guides,
                           glossaire=GLOSSAIRE if current_user.is_authenticated else [])


@bp.route('/fiche/<id_>')
def fiche(id_):
    a = article(id_)
    if a is None or not visible(a):
        abort(404)
    ok, message = acces(a)
    voisins = [b for b in ARTICLES if b['cat'] == a['cat'] and b['id'] != a['id'] and visible(b)][:6]
    cat = next((c for c in CATEGORIES if c[0] == a['cat']), None)
    precedent = suivant = None
    if a.get('illustrations'):                     # guide illustré : navigation d'un guide au suivant
        serie = [b for b in ARTICLES if b.get('illustrations') and visible(b)]
        i = next((k for k, b in enumerate(serie) if b['id'] == a['id']), None)
        if i is not None:
            precedent = serie[i - 1] if i > 0 else None
            suivant = serie[i + 1] if i + 1 < len(serie) else None
    return render_template('egalyx/aide_fiche.html', a=a, ok=ok, message=message, liens=liens(a),
                           voisins=voisins, categorie=cat, precedent=precedent, suivant=suivant)


@bp.route('/guide-complet')
def guide_complet():
    """Toutes les fiches visibles sur une page imprimable (Ctrl P → PDF)."""
    return render_template('egalyx/aide_guide.html', categories=_categories_visibles(current_user),
                           glossaire=GLOSSAIRE)


@bp.route('/api/chercher')
def api_chercher():
    q = (request.args.get('q') or '').strip()[:200]
    return jsonify({'resultats': [{'id': a['id'], 'titre': a['titre'], 'resume': a['resume'], 'score': s,
                                   'url': url_for('aide.fiche', id_=a['id'])}
                                  for s, a in chercher(q, n=8) if not a.get('glossaire')]})


def enregistrer(app):
    app.register_blueprint(bp)
    app.jinja_env.filters.setdefault('aide_rendu', _rendu)
    index()
