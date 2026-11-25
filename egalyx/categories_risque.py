"""
egalyx/categories_risque.py — liste des catégories de risque proposée par défaut (fiche risque).

Les codes historiques (operationnel, financier, juridique, compliance, reputation, strategique, technologique,
humain, environnemental) sont conservés : les risques déjà classés ne changent pas.
Une organisation qui a défini sa propre liste (Paramétrage > Listes déroulantes, liste « categorie ») garde la sienne.
"""
CATEGORIES_RISQUE = [
    ('strategique', 'Stratégique'),
    ('gouvernance', 'Gouvernance'),
    ('operationnel', 'Opérationnel'),
    ('financier', 'Financier'),
    ('credit', 'Crédit / contrepartie'),
    ('marche', 'Marché (taux, change, prix)'),
    ('liquidite', 'Liquidité'),
    ('fiscal', 'Fiscal'),
    ('juridique', 'Juridique'),
    ('compliance', 'Conformité réglementaire'),
    ('lcbft', 'Blanchiment / financement du terrorisme (LCB-FT)'),
    ('fraude', 'Fraude et corruption'),
    ('informatique', 'Informatique / systèmes d\'information'),
    ('cybersecurite', 'Cybersécurité'),
    ('donnees', 'Protection des données personnelles'),
    ('technologique', 'Technologique'),
    ('continuite', 'Continuité d\'activité'),
    ('humain', 'Ressources humaines'),
    ('sante_securite', 'Santé et sécurité au travail'),
    ('securite_physique', 'Sécurité physique et des biens'),
    ('achats', 'Achats, fournisseurs et tiers'),
    ('logistique', 'Logistique et approvisionnement'),
    ('commercial', 'Commercial / clients'),
    ('qualite', 'Qualité des produits et services'),
    ('projet', 'Projets'),
    ('reputation', 'Réputation / image'),
    ('environnemental', 'Environnemental et climatique'),
    ('rse', 'Social et sociétal (RSE)'),
    ('pays', 'Pays / politique'),
    ('autre', 'Autre'),
]
LIBELLES = dict(CATEGORIES_RISQUE)


def libelle(code):
    """Libellé lisible d'une catégorie (le code tel quel s'il vient d'une liste propre à l'organisation)."""
    if not code:
        return ''
    return LIBELLES.get(code, code)


def enregistrer(app):
    app.jinja_env.filters['categorie_risque'] = libelle
