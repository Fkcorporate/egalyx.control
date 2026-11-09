"""Jeu de données de recette : un objet de chaque type utile, dans l'organisation A (et une copie dans B)."""
import datetime as dt
from socle import creer

def peupler_objets(A, ids):
    import models as M
    from models import db
    out = {}
    with A.app.app_context():
        for cl, suf in ((1, 'a'), (2, 'b')):
            createur = ids['gestionnaire'] if cl == 1 else ids['admin_b']
            d = creer(M.Direction, nom=f'Direction {suf}', client_id=cl)
            carto = creer(M.Cartographie, nom=f'Carto {suf}', client_id=cl, direction_id=d.id, created_by=createur)
            risque = creer(M.Risque, reference=f'R-{suf}', intitule=f'Risque {suf}', cartographie_id=carto.id,
                           client_id=cl, created_by=createur)
            prop = creer(M.Risque, reference=f'RP-{suf}', intitule=f'Risque proposé {suf}', cartographie_id=carto.id,
                         client_id=cl, created_by=createur, statut='en_validation')
            prog = creer(M.ProgrammeAudit, reference=f'PA-{suf}', nom=f'Programme {suf}', periode='annuel', annee_debut=2026,
                         annee_fin=2026, methode_generation='manuel', client_id=cl, created_by=createur, statut='en_elaboration')
            mission = creer(M.MissionAudit, reference=f'MA-{suf}', titre=f'Mission {suf}', programme_id=prog.id,
                            annee_prevue=2026, client_id=cl, statut='planifiee', created_by=createur)
            ref = creer(M.ReferentielControle, client_id=cl)
            pl = creer(M.PlanificationControle, reference=f'PL-{suf}', annee=2026, date_prevue=dt.date.today(),
                       referentiel_id=ref.id, client_id=cl, controleur_id=ids['operateur'] if cl == 1 else ids['admin_b'],
                       validateur_requis_id=ids['validateur'] if cl == 1 else ids['admin_b'], statut='en_cours')
            reco = creer(M.RecommandationC2N, planification_id=pl.id, titre=f'Reco {suf}', client_id=cl, statut='proposee',
                         created_by=createur) if hasattr(M.RecommandationC2N, 'created_by') else \
                   creer(M.RecommandationC2N, planification_id=pl.id, titre=f'Reco {suf}', client_id=cl, statut='proposee')
            camp = creer(M.CampagneControle, nom=f'Campagne {suf}', reference=f'CC-{suf}', date_debut=dt.date.today(),
                         date_fin=dt.date.today() + dt.timedelta(days=30), createur_id=createur, client_id=cl,
                         statut='en_preparation', evaluateur_id=ids['operateur'] if cl == 1 else ids['admin_b'],
                         valideur_id=ids['validateur'] if cl == 1 else ids['admin_b'], planification_c2n_id=pl.id)
            ce = creer(M.CampagneEvaluation, cartographie_id=carto.id, nom=f'Campagne éval {suf}', statut='en_cours',
                       client_id=cl) if hasattr(M.CampagneEvaluation, 'client_id') else \
                 creer(M.CampagneEvaluation, cartographie_id=carto.id, nom=f'Campagne éval {suf}', statut='en_cours')
            pa = creer(M.PlanAction, reference=f'PAC-{suf}', nom=f'Plan {suf}', client_id=cl, created_by=createur)
            out[suf] = dict(direction=d.id, carto=carto.id, risque=risque.id, risque_propose=prop.id, programme=prog.id,
                            mission=mission.id, planification=pl.id, reco=reco.id, campagne=camp.id, campagne_eval=ce.id,
                            plan=pa.id)
        db.session.commit()
    return out
