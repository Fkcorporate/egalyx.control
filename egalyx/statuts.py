"""
egalyx/statuts.py — une seule écriture des statuts par objet.

Recensement du 19/11/2026 (toutes les écritures et comparaisons de statut, rattachées à leur modèle) :
chaque module a son vocabulaire (« terminee » au contrôle N2, « termine » pour les plans d'audit et de
risque ; « ouvert / ferme » pour les non-conformités N2, « ouverte / close » en qualité…). Les écrans qui
mélangent les modules (« Ma semaine », « Tous les plans d'action », rapport au comité) savent déjà lire les
deux. Les vrais écarts étaient des écritures isolées hors vocabulaire (ex. dispositif « à_améliorer » avec
accents, jamais reconnu par les filtres « a_ameliorer »), et une comparaison fausse (rapport N2).

Ce module :
  - fixe le vocabulaire de chaque objet (VOCABULAIRE) et les variantes reconnues (ALIAS) ;
  - corrige toute variante au moment de l'enregistrement, quel que soit l'écran ou l'import ;
  - convertit une fois les données existantes (migration 0003, et au démarrage si elle n'a pas été lancée).
"""
import logging

from sqlalchemy import event, inspect, text

journal = logging.getLogger('egalyx.statuts')

VOCABULAIRE = {
    'PlanAction': ('en_attente', 'planifie', 'en_cours', 'suspendu', 'retarde', 'termine', 'annule'),
    'SousAction': ('a_faire', 'en_cours', 'retarde', 'termine', 'annule'),
    'PlanActionC2N': ('a_faire', 'en_cours', 'bloquee', 'terminee', 'annulee'),
    'SousActionPlanC2N': ('a_faire', 'en_cours', 'terminee', 'annulee'),
    'ActionAmeliorationQualite': ('a_faire', 'en_cours', 'terminee', 'annulee'),
    'NonConformiteC2N': ('ouvert', 'en_cours', 'ferme'),
    'NonConformite': ('ouverte', 'en_traitement', 'verifiee', 'close'),
    'Incident': ('en_attente', 'en_attente_approbation', 'ouvert', 'en_cours', 'resolu', 'ferme', 'rejete'),
    'DispositifMaitrise': ('actif', 'inactif', 'en_cours', 'a_ameliorer', 'obsolete'),
    'Recommandation': ('a_traiter', 'en_cours', 'retarde', 'termine', 'rejetee', 'annule'),
    'RecommandationC2N': ('proposee', 'acceptee', 'en_cours', 'realisee', 'rejetee'),
}
ALIAS = {
    'PlanAction': {'terminee': 'termine', 'complete': 'termine', 'complet': 'termine', 'cloture': 'termine', 'annulee': 'annule'},
    'SousAction': {'terminee': 'termine', 'annulee': 'annule'},
    'PlanActionC2N': {'termine': 'terminee', 'annule': 'annulee', 'bloque': 'bloquee'},
    'SousActionPlanC2N': {'termine': 'terminee', 'annule': 'annulee'},
    'ActionAmeliorationQualite': {'termine': 'terminee', 'annule': 'annulee'},
    'NonConformiteC2N': {'ouverte': 'ouvert', 'fermee': 'ferme', 'close': 'ferme', 'clos': 'ferme', 'cloturee': 'ferme'},
    'NonConformite': {'ouvert': 'ouverte', 'ferme': 'close', 'fermee': 'close', 'clos': 'close', 'cloturee': 'close'},
    'Incident': {'ouverte': 'ouvert', 'resolue': 'resolu', 'fermee': 'ferme', 'close': 'ferme', 'clos': 'ferme'},
    'DispositifMaitrise': {'à_améliorer': 'a_ameliorer', 'a_améliorer': 'a_ameliorer', 'obsolète': 'obsolete'},
    'Recommandation': {'terminee': 'termine', 'cloturee': 'termine', 'close': 'termine'},
    'RecommandationC2N': {'terminee': 'realisee', 'termine': 'realisee', 'cloturee': 'realisee'},
}
_INSTALLE = []


def canonique(modele, valeur):
    if valeur is None:
        return None
    v = str(valeur).strip()
    return ALIAS.get(modele, {}).get(v, v)


def _avant_ecriture(session, _contexte, _instances):
    for obj in list(session.new) + list(session.dirty):
        nom = type(obj).__name__
        if nom not in ALIAS:
            continue
        v = getattr(obj, 'statut', None)
        c = canonique(nom, v)
        if c != v:
            obj.statut = c
            journal.debug('%s %s : statut « %s » -> « %s »', nom, getattr(obj, 'id', None), v, c)


def convertir_base(connexion):
    """Convertit les variantes déjà enregistrées. Idempotente ; retourne {modèle: nombre de lignes}."""
    import models as M
    tables = set(inspect(connexion).get_table_names())
    faits = {}
    for nom, alias in ALIAS.items():
        modele = getattr(M, nom, None)
        if modele is None or modele.__tablename__ not in tables:
            continue
        n = 0
        for ancien, nouveau in alias.items():
            r = connexion.execute(text(f'UPDATE "{modele.__tablename__}" SET statut = :n WHERE statut = :a'), {'n': nouveau, 'a': ancien})
            n += r.rowcount or 0
        if n:
            faits[nom] = n
    return faits


def enregistrer(app):
    if not _INSTALLE:
        from sqlalchemy.orm import Session
        event.listen(Session, 'before_flush', _avant_ecriture)
        _INSTALLE.append(True)
    import os
    if os.environ.get('EGALYX_STATUTS_AU_DEMARRAGE', '1') == '1':
        try:
            from models import db
            with app.app_context():
                with db.engine.begin() as c:
                    faits = convertir_base(c)
            if faits:
                journal.warning('Statuts harmonisés au démarrage : %s', faits)
        except Exception as e:  # noqa: BLE001  — jamais bloquant
            journal.info('Harmonisation des statuts reportée : %s', e)
