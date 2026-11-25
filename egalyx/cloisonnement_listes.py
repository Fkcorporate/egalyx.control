"""
egalyx/cloisonnement_listes.py — filet de sécurité : une LISTE ne montre jamais les données d'une autre organisation.

egalyx/cloisonnement.py protège les adresses qui visent UN élément (/audit/12 d'un autre client -> 404).
Mais des pages construisent des listes sans filtrer par organisation (« Comparaison d'audits », listes
déroulantes de directions, de services, de responsables, exports…). Plutôt que de corriger ces centaines
de requêtes une par une, ce module ajoute automatiquement, pendant chaque page d'un utilisateur rattaché
à une organisation, la condition « client_id = son organisation » à toute lecture des tables qui ont une
colonne client_id. Même technique que egalyx/structure.py (périmètre par direction), déjà en service.

Ce qui reste visible :
  - les éléments de l'organisation de l'utilisateur ;
  - les éléments sans organisation (client_id vide : données communes ou anciennes, comme aujourd'hui) ;
  - les éléments explicitement partagés (modèles publics, bibliothèque de risques publiée…).

Pas de filtre :
  - super administrateur (il voit tout, y compris quand il consulte une organisation) ;
  - visiteur non connecté (pages publiques), tâches planifiées, commandes flask ;
  - recherche d'un élément précis par son identifiant ou par une valeur unique (nom d'utilisateur, e-mail,
    jeton…) : c'est egalyx/cloisonnement.py qui contrôle l'accès, et les contrôles « ce nom existe déjà »
    doivent voir toute la table ;
  - chargements de relations (audit.constatations…) : ils suivent l'élément déjà autorisé.

Appel par l'API publique (clé X-API-Key) : filtré sur l'organisation de la clé.

Désactivation d'urgence, sans redéployer le code : variable EGALYX_CLOISONNEMENT_LISTES=0 sur Render.
Code qui doit volontairement voir toutes les organisations :  with sans_cloisonnement(): ...
"""
import logging
import os
from contextlib import contextmanager

from flask import g, has_request_context
from flask_login import current_user

journal = logging.getLogger('egalyx.cloisonnement_listes')

COLONNES_PARTAGE = ('is_public', 'est_public', 'est_publie')    # élément volontairement partagé entre organisations
NE_PAS_FILTRER = {'Client'}


def actif():
    return os.environ.get('EGALYX_CLOISONNEMENT_LISTES', '1') != '0'


@contextmanager
def sans_cloisonnement():
    precedent = g.get('eg_cloison_pause') if has_request_context() else None
    if has_request_context():
        g.eg_cloison_pause = True
    try:
        yield
    finally:
        if has_request_context():
            g.eg_cloison_pause = precedent


def _organisation_de_la_requete():
    """Calculé une fois par page (avant la vue) : l'écouteur ne doit jamais toucher current_user lui-même."""
    g.eg_cloison_cid = None
    if not actif():
        return
    try:
        if not getattr(current_user, 'is_authenticated', False):
            return
        if getattr(current_user, 'role', None) == 'super_admin':
            return
        sa = getattr(current_user, 'is_super_admin', False)
        if (sa() if callable(sa) else sa) is True:
            return
        g.eg_cloison_cid = getattr(current_user, 'client_id', None) or None
    except Exception as e:  # noqa: BLE001 — ne jamais bloquer une page pour ce calcul
        journal.warning('Organisation de la requête non déterminée : %s', e)


def _cid():
    if not has_request_context() or g.get('eg_cloison_pause'):
        return None
    cid = g.get('eg_cloison_cid')
    if cid:
        return cid
    if g.get('api_key') is not None and g.get('client_id'):     # API publique : organisation de la clé
        return g.get('client_id')
    return None


def _recherche_ciblee(statement):
    """Vrai si la requête vise un élément précis : « clé primaire = … », « … IN (…) » ou « colonne unique = … »."""
    from sqlalchemy.sql import operators, visitors
    from sqlalchemy.sql.elements import BinaryExpression
    from sqlalchemy.sql.schema import Column
    clause = getattr(statement, 'whereclause', None)
    if clause is None:
        return False
    for el in visitors.iterate(clause):
        if isinstance(el, BinaryExpression) and el.operator in (operators.eq, operators.in_op):
            for cote in (el.left, el.right):
                if isinstance(cote, Column) and (cote.primary_key or cote.unique) and cote.name != 'client_id':
                    return True
    return False


def _critere(cls, cid):
    from sqlalchemy import or_
    conditions = [cls.client_id == cid, cls.client_id.is_(None)]
    for nom in COLONNES_PARTAGE:
        col = getattr(cls, nom, None)
        if col is not None and hasattr(col, 'is_'):
            conditions.append(col.is_(True))
    return or_(*conditions)


def _filtrer(etat):
    if not etat.is_select or etat.is_column_load or etat.is_relationship_load:
        return
    cid = _cid()
    if not cid:
        return
    try:
        from sqlalchemy.orm import with_loader_criteria
        options = []
        for mapper in etat.all_mappers:
            cls = mapper.class_
            if cls.__name__ in NE_PAS_FILTRER or 'client_id' not in mapper.columns:
                continue
            options.append(with_loader_criteria(cls, _critere(cls, cid), include_aliases=True,
                                                propagate_to_loaders=False))
        if not options or _recherche_ciblee(etat.statement):
            return
        etat.statement = etat.statement.options(*options)
    except Exception as e:  # noqa: BLE001 — en cas de doute, la requête part telle qu'avant
        journal.warning('Filtre organisation non appliqué : %s', e)


def enregistrer(app):
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    if not getattr(app, '_eg_cloison_listes', False):
        event.listen(Session, 'do_orm_execute', _filtrer)
        app._eg_cloison_listes = True
    app.before_request_funcs.setdefault(None, []).insert(0, _organisation_de_la_requete)
    journal.info('Cloisonnement des listes %s', 'actif' if actif() else 'DÉSACTIVÉ (EGALYX_CLOISONNEMENT_LISTES=0)')
