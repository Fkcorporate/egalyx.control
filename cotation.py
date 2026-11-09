"""
cotation.py — RÈGLE UNIQUE DE COTATION DES RISQUES (Egalyx Control)
=====================================================================

Ce module est la seule source de vérité pour :
  - les seuils de niveaux (Faible / Moyen / Élevé / Critique),
  - le calcul BRUT / NET (ISO 31000 / 31010),
  - les couleurs et libellés affichés.

app.py, models.py, les templates (via les globals Jinja) et le JavaScript
(via window.EgalyxCotation, généré à partir de ce fichier) l'utilisent.
Pour changer une règle, on ne modifie QUE ce fichier.

Règle :
  BRUT = impact × probabilité                       (1 à 25)
  NET  = impact × probabilité ajustée
         probabilité ajustée = probabilité × (1 − taux de réduction)
         taux de réduction selon la maîtrise (1 à 5) : 0 %, 10 %, 25 %, 40 %, 60 %
  Niveaux : ≤ 4 Faible · ≤ 10 Moyen · ≤ 16 Élevé · > 16 Critique
  Le NET est le niveau de référence (tri, couleurs, compteurs « critiques »).
"""

import unicodedata

# ----------------------------------------------------------------------
# PARAMÈTRES
# ----------------------------------------------------------------------
SEUILS = (4, 10, 16)          # bornes hautes de Faible, Moyen, Élevé
SCORE_MAX = 25

NIVEAUX = ('Faible', 'Moyen', 'Élevé', 'Critique')
NON_EVALUE = 'Non évalué'

TAUX_REDUCTION_MAITRISE = {
    1: 0.00,   # Très faible  : aucun contrôle
    2: 0.10,   # Faible       : contrôles informels
    3: 0.25,   # Moyenne      : contrôles documentés
    4: 0.40,   # Bonne        : contrôles testés
    5: 0.60,   # Très bonne   : contrôles continus et audités
}

# ----------------------------------------------------------------------
# PARAMÈTRES PAR CLIENT (facultatif)
# ----------------------------------------------------------------------
# L'application peut enregistrer un « fournisseur » qui renvoie, pour le contexte courant
# (client de l'utilisateur ou de l'évaluation enregistrée), un dict
#   {'seuils': (faible, moyen, eleve), 'taux': {1: 0.0, ..., 5: 0.6}}
# ou None pour la règle par défaut ci-dessus. La matrice reste 5 × 5.
_fournisseur_parametres = None


def definir_fournisseur(fonction):
    global _fournisseur_parametres
    _fournisseur_parametres = fonction


def parametres_actifs():
    """(seuils, taux) applicables au contexte courant."""
    if _fournisseur_parametres is not None:
        try:
            p = _fournisseur_parametres()
        except Exception:
            p = None
        if p:
            seuils = tuple(float(x) for x in p.get('seuils') or SEUILS)
            taux = {int(k): float(v) for k, v in (p.get('taux') or TAUX_REDUCTION_MAITRISE).items()}
            if len(seuils) == 3 and seuils[0] < seuils[1] < seuils[2]:
                return seuils, taux
    return SEUILS, TAUX_REDUCTION_MAITRISE


# Une seule palette pour tout l'outil (écrans, PDF, matrices, graphiques).
# Palette ordinale vérifiée (daltonisme + vision normale) : vert → ambre → orange → rouge foncé.
# Le niveau est toujours écrit en toutes lettres à côté de la couleur.
# 'bs' = classe Bootstrap la plus proche, pour le code existant qui attend
# un nom de couleur Bootstrap (text-bg-{{ bs }}).
STYLES = {
    'Faible':     {'cle': 'faible',   'hex': '#16a34a', 'texte': '#ffffff', 'bs': 'success',   'action': 'Surveillance courante'},
    'Moyen':      {'cle': 'moyen',    'hex': '#e0a800', 'texte': '#1f2937', 'bs': 'warning',   'action': "Plan d'action recommandé"},
    'Élevé':      {'cle': 'eleve',    'hex': '#ea580c', 'texte': '#ffffff', 'bs': 'orange',    'action': 'Actions correctives rapides'},
    'Critique':   {'cle': 'critique', 'hex': '#991b1b', 'texte': '#ffffff', 'bs': 'danger',    'action': 'Escalade à la direction'},
    NON_EVALUE:   {'cle': 'na',       'hex': '#94a3b8', 'texte': '#ffffff', 'bs': 'secondary', 'action': 'À évaluer'},
}

# Ancienne correspondance (_qualifier_score / calculer_niveau_risque) :
# conservée pour le code qui lit encore le 2e élément du tuple.
COULEUR_BS_HISTORIQUE = {
    'Faible': 'success', 'Moyen': 'warning', 'Élevé': 'danger',
    'Critique': 'dark', NON_EVALUE: 'secondary',
}


# ----------------------------------------------------------------------
# NIVEAUX
# ----------------------------------------------------------------------
def _nombre(valeur):
    """Convertit en float positif, sinon None (gère '3', '3,5', None, '')."""
    if valeur is None or valeur == '':
        return None
    try:
        nombre = float(str(valeur).replace(',', '.'))
    except (TypeError, ValueError):
        return None
    return nombre if nombre > 0 else None


def niveau(score, seuils=None):
    """Score (brut ou net) → 'Faible' | 'Moyen' | 'Élevé' | 'Critique' | 'Non évalué'."""
    s = _nombre(score)
    if s is None:
        return NON_EVALUE
    seuils = seuils or parametres_actifs()[0]
    if s <= seuils[0]:
        return 'Faible'
    if s <= seuils[1]:
        return 'Moyen'
    if s <= seuils[2]:
        return 'Élevé'
    return 'Critique'


def _sans_accent(texte):
    return ''.join(c for c in unicodedata.normalize('NFD', texte)
                   if unicodedata.category(c) != 'Mn')


_ALIAS = {
    'faible': 'Faible', 'low': 'Faible', 'mineur': 'Faible', 'tres faible': 'Faible',
    'moyen': 'Moyen', 'modere': 'Moyen', 'medium': 'Moyen', 'moderee': 'Moyen',
    'eleve': 'Élevé', 'elevee': 'Élevé', 'high': 'Élevé', 'majeur': 'Élevé', 'important': 'Élevé',
    'critique': 'Critique', 'critical': 'Critique', 'tres eleve': 'Critique', 'extreme': 'Critique',
}


def normaliser(libelle):
    """'eleve', 'ÉLEVÉ', 'Elevé', 'high'… → 'Élevé'. Inconnu ou vide → 'Non évalué'."""
    if not libelle:
        return NON_EVALUE
    if libelle in STYLES:
        return libelle
    cle = _sans_accent(str(libelle)).strip().lower().replace('_', ' ')
    return _ALIAS.get(cle, NON_EVALUE)


def style(libelle_ou_score):
    """Style d'affichage d'un niveau (accepte aussi un score numérique)."""
    if isinstance(libelle_ou_score, (int, float)) and not isinstance(libelle_ou_score, bool):
        nom = niveau(libelle_ou_score)
    else:
        nom = normaliser(libelle_ou_score)
    return dict(STYLES[nom], niveau=nom)


def qualifier(score):
    """Compatibilité avec l'ancien _qualifier_score : (niveau, couleur Bootstrap)."""
    nom = niveau(score)
    return nom, COULEUR_BS_HISTORIQUE[nom]


# ----------------------------------------------------------------------
# CALCUL BRUT / NET
# ----------------------------------------------------------------------
def taux_reduction(niveau_maitrise):
    m = _nombre(niveau_maitrise)
    if m is None:
        return 0.0
    return parametres_actifs()[1].get(int(round(m)), 0.0)


def scores(impact, probabilite, niveau_maitrise=None):
    """Calcul ISO : même dictionnaire que l'ancien calculer_scores_risque()."""
    i, p = _nombre(impact), _nombre(probabilite)
    if i is None or p is None:
        return {
            'score_brut': 0, 'niveau_brut': NON_EVALUE,
            'score_net': 0, 'niveau_net': NON_EVALUE,
            'probabilite_ajustee': 0, 'taux_reduction': 0,
        }
    brut = round(i * p, 2)
    t = taux_reduction(niveau_maitrise)
    p_aj = round(p * (1 - t), 2)
    net = round(i * p_aj, 2)
    return {
        'score_brut': int(brut) if brut == int(brut) else brut,
        'niveau_brut': niveau(brut),
        'score_net': net,
        'niveau_net': niveau(net),
        'probabilite_ajustee': p_aj,
        'taux_reduction': t,
    }


def _premier(objet, *noms):
    for nom in noms:
        v = _nombre(getattr(objet, nom, None))
        if v is not None:
            return v
    return None


def entrees_evaluation(evaluation):
    """Impact, probabilité, maîtrise retenus : confirmation > validation > pré-évaluation > champ simple."""
    impact = _premier(evaluation, 'impact_conf', 'impact_val', 'impact_pre', 'impact')
    proba = _premier(evaluation, 'probabilite_conf', 'probabilite_val', 'probabilite_pre', 'probabilite')
    maitrise = _premier(evaluation, 'niveau_maitrise_conf', 'niveau_maitrise_val',
                        'niveau_maitrise_pre', 'niveau_maitrise')
    return impact, proba, maitrise


def depuis_evaluation(evaluation):
    """
    Cotation complète d'une évaluation, recalculée depuis ses cotations
    (jamais depuis un score stocké qui pourrait dater de l'ancienne règle).
    Si l'impact ou la probabilité manquent, on se rabat sur les scores stockés.
    """
    vide = {
        'evalue': False, 'impact': None, 'probabilite': None, 'niveau_maitrise': None,
        'score_brut': None, 'niveau_brut': NON_EVALUE,
        'score_net': None, 'niveau_net': NON_EVALUE,
        'probabilite_ajustee': None, 'taux_reduction': 0,
    }
    if evaluation is None:
        return vide
    impact, proba, maitrise = entrees_evaluation(evaluation)
    if impact and proba:
        res = scores(impact, proba, maitrise)
        res.update(evalue=True, impact=impact, probabilite=proba, niveau_maitrise=maitrise)
        return res
    # Repli : scores déjà stockés
    net = _nombre(getattr(evaluation, 'score_risque_net', None)) or _nombre(getattr(evaluation, 'score_risque', None))
    brut = _nombre(getattr(evaluation, 'score_risque_brut', None)) or net
    if net is None and brut is None:
        return vide
    return dict(vide, evalue=True, score_brut=brut, niveau_brut=niveau(brut),
                score_net=net if net is not None else brut,
                niveau_net=niveau(net if net is not None else brut),
                taux_reduction=_nombre(getattr(evaluation, 'taux_reduction_maitrise', None)) or 0)


def appliquer(evaluation):
    """
    Écrit la cotation sur l'objet évaluation (brut, net, champs historiques).
    Ne fait rien si impact ou probabilité manquent. Retourne le dict de scores ou None.
    """
    impact, proba, maitrise = entrees_evaluation(evaluation)
    if not (impact and proba):
        return None
    res = scores(impact, proba, maitrise)
    valeurs = {
        'score_risque_brut': res['score_brut'],
        'niveau_risque_brut': res['niveau_brut'],
        'score_risque_net': res['score_net'],
        'niveau_risque_net': res['niveau_net'],
        'probabilite_ajustee': res['probabilite_ajustee'],
        'taux_reduction_maitrise': res['taux_reduction'],
        # Champs historiques = NET (référence)
        'score_risque': res['score_net'],
        'niveau_risque': res['niveau_net'],
    }
    for champ, valeur in valeurs.items():
        if hasattr(type(evaluation), champ) or hasattr(evaluation, champ):
            try:
                setattr(evaluation, champ, valeur)
            except Exception:
                pass
    return res


# ----------------------------------------------------------------------
# EXPORT POUR LE JAVASCRIPT
# ----------------------------------------------------------------------
def config_js():
    """Dictionnaire sérialisable injecté dans window.EgalyxCotation (base.html)."""
    seuils, taux = parametres_actifs()
    return {
        'seuils': list(seuils),
        'scoreMax': SCORE_MAX,
        'tauxReduction': {str(k): v for k, v in taux.items()},
        'styles': {nom: {'cle': s['cle'], 'hex': s['hex'], 'texte': s['texte'], 'action': s['action']}
                   for nom, s in STYLES.items()},
    }


# Niveau de maîtrise (1 = insuffisant … 5 = excellent) : rouge -> vert, partout dans l'outil.
COULEURS_MAITRISE = {1: '#dc2626', 2: '#ea580c', 3: '#e0a800', 4: '#65a30d', 5: '#16a34a'}
LIBELLES_MAITRISE = {1: 'Insuffisant', 2: 'Partiel', 3: 'Adéquat', 4: 'Bon', 5: 'Excellent'}


def couleur_maitrise(niveau):
    try:
        n = int(round(float(niveau)))
    except (TypeError, ValueError):
        return '#94a3b8'
    return COULEURS_MAITRISE.get(min(5, max(1, n)), '#94a3b8')
