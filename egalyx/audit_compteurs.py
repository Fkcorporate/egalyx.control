"""
egalyx/audit_compteurs.py — compteurs de la fiche d'un audit calculés côté serveur.

Le nombre de feuilles de travail (onglet et bouton « Feuilles de travail ») n'était rempli qu'après le
chargement de l'onglet, donc affichait 0 tant qu'on ne l'avait pas ouvert. Il est maintenant calculé à
l'affichage de la page, avec les mêmes règles que la liste (feuilles non archivées de l'audit, de l'organisation).
"""
import logging

journal = logging.getLogger('egalyx.audit_compteurs')


def nb_feuilles_travail(audit_id):
    try:
        import models as M
        from flask_login import current_user
        q = M.FeuilleTravail.query.filter(M.FeuilleTravail.audit_id == audit_id,
                                          (M.FeuilleTravail.is_archived.is_(False)) | (M.FeuilleTravail.is_archived.is_(None)))
        cid = getattr(current_user, 'client_id', None)
        if cid is not None and getattr(current_user, 'role', None) != 'super_admin':
            q = q.filter(M.FeuilleTravail.client_id == cid)
        return q.count()
    except Exception as e:  # noqa: BLE001
        journal.warning("Compteur des feuilles de travail indisponible (audit %s) : %s", audit_id, e)
        return 0


def enregistrer(app):
    app.jinja_env.globals.update(eg_nb_feuilles_travail=nb_feuilles_travail)
