"""Registre des recommandations : supprimer une ligne d'historique ou tout l'historique."""
import os
import sys

import socle
import objets
from socle import Muet, appel, creer

with Muet():
    A, ids = socle.preparer()
    objets.peupler_objets(A, ids)
import models as M
from models import db

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond))
    print('OK   ' if cond else 'ÉCHEC', nom, detail)


def go(role, m, url, **kw):
    r = appel(socle.navigateur(A, ids[role]), m, url, **kw)
    return r, r.data.decode('utf-8', 'ignore')


with A.app.app_context():
    r = creer(M.RecommandationExterne, client_id=1, titre='Reco CAC', reference='EXT-1', statut='en_cours',
              progression=40, responsable_id=ids['operateur'], created_by=ids['gestionnaire'])
    rid = r.id
    dossier = os.path.join(A.app.instance_path, 'preuves_recommandations')
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, 'preuve_test.pdf')
    open(chemin, 'wb').write(b'%PDF-1.4 test')
    s1 = M.SuiviRecommandation(client_id=1, source='externe', recommandation_id=rid, action='avancement', progression=20,
                               commentaire='premier', user_id=ids['operateur'],
                               fichier='preuves_recommandations/preuve_test.pdf', nom_fichier='preuve.pdf')
    s2 = M.SuiviRecommandation(client_id=1, source='externe', recommandation_id=rid, action='avancement', progression=40,
                               commentaire='second', user_id=ids['operateur'])
    s3 = M.SuiviRecommandation(client_id=1, source='externe', recommandation_id=rid, action='avancement', progression=40,
                               commentaire='troisième', user_id=ids['operateur'])
    db.session.add_all([s1, s2, s3]); db.session.commit()
    s1id, s2id = s1.id, s2.id


def nb():
    with A.app.app_context():
        return M.SuiviRecommandation.query.filter_by(source='externe', recommandation_id=rid).count()


base = f'/recommandations/externe/{rid}'
r, t = go('gestionnaire', 'get', base)
verif('Le gestionnaire voit les boutons de suppression', r.status_code == 200 and "Vider l'historique" in t and 'fa-trash-alt' in t, str(r.status_code))
r, t = go('operateur', 'get', base)
verif('Le responsable (non gestionnaire) ne les voit pas', "Vider l'historique" not in t, str(r.status_code))
for role in ('lecteur', 'operateur', 'admin_b'):
    go(role, 'post', f'{base}/historique/{s2id}/supprimer')
verif('Lecteur, responsable et autre organisation ne peuvent rien supprimer', nb() == 3)
r, _ = go('gestionnaire', 'post', f'{base}/historique/{s1id}/supprimer')
verif('Le gestionnaire supprime une ligne', nb() == 2 and r.status_code == 302, str(r.status_code))
verif('… et sa preuve jointe est effacée du disque', not os.path.exists(chemin))
with A.app.app_context():
    j = M.JournalActiviteClient.query.filter_by(action='historique_recommandation_supprime').first()
    verif('La suppression reste tracée au journal d\'activité', j is not None and j.details.get('commentaire') == 'premier')
r, _ = go('gestionnaire', 'post', f'{base}/historique/999999/supprimer')
verif('Ligne inexistante : 404', r.status_code == 404, str(r.status_code))
r, _ = go('gestionnaire', 'post', f'{base}/historique/vider')
verif('Vider l\'historique', nb() == 0, str(r.status_code))
with A.app.app_context():
    x = db.session.get(M.RecommandationExterne, rid)
    verif('L\'avancement et le statut ne changent pas', x.progression == 40 and x.statut == 'en_cours')
r, t = go('admin_a', 'get', base)
verif('La fiche s\'affiche avec un historique vide', r.status_code == 200, str(r.status_code))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
