"""Recette : dossier de mission figé après le rapport définitif, réouverture motivée."""
import datetime as dt
import io
import os
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
import models as M
from models import db

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


C = {r: socle.navigateur(A, ids[r]) for r in ('admin_a', 'gestionnaire', 'validateur', 'lecteur', 'admin_b')}


def req(role, methode, url, **kw):
    r = appel(C[role], methode, url, **kw)
    with C[role].session_transaction() as s:
        fl = [m for _, m in (s.get('_flashes') or [])]
        s.pop('_flashes', None)
    return r, fl


def obj(Mod, i):
    with A.app.app_context():
        x = db.session.get(Mod, i)
        db.session.expunge_all()
        return x


with A.app.app_context():
    g = db.session.get(M.User, ids['gestionnaire'])
    audit = socle.creer(M.Audit, reference='AUD-FIG', titre='Audit des achats', type_audit='interne', client_id=1,
                        responsable_id=ids['gestionnaire'], equipe_audit_ids=str([ids['gestionnaire'], ids['validateur']]),
                        statut='en_cours')
    feuille = socle.creer(M.FeuilleTravail, audit_id=audit.id, client_id=1, titre='Feuille achats', reference='FT-FIG')
    test = socle.creer(M.TestControleFeuille, feuille_travail_id=feuille.id, objet_test='Contrôle des bons de commande',
                       )
    cst = socle.creer(M.Constatation, reference='CST-FIG', description='Bons de commande non signés', audit_id=audit.id,
                      client_id=1, reponse_audite='OK', position_audite='accord')
    db.session.commit()
    AID, FID, TID, CID = audit.id, feuille.id, test.id, cst.id

print('--- Avant le rapport définitif : tout se modifie')
r, fl = req('gestionnaire', 'post', f'/constatation/{CID}/modifier', data={'description': 'Bons de commande non signés (2)'})
verif('constat modifiable avant le définitif', 'figé' not in ' '.join(fl) and r.status_code != 423, (r.status_code, fl))

print('--- Rapport définitif')
with A.app.app_context():
    a = db.session.get(M.Audit, AID); a.etat_rapport = 'definitif'; a.rapport_definitif_le = dt.datetime.utcnow(); db.session.commit()
avant_cst = obj(M.Constatation, CID).description
avant_test = obj(M.TestControleFeuille, TID).objet_test
avant_titre = obj(M.Audit, AID).titre
n_tests = lambda: M.TestControleFeuille.query.filter_by(feuille_travail_id=FID).count()
with A.app.app_context():
    n0 = n_tests()

TENTATIVES = [
    ('modifier un constat', 'post', f'/constatation/{CID}/modifier', {'data': {'description': 'retouché'}}),
    ('supprimer un constat', 'post', f'/constatation/{CID}/supprimer', {}),
    ('changer le statut d\'un constat', 'post', f'/constatation/{CID}/changer-statut', {'data': {'statut': 'clos'}}),
    ('ajouter une preuve à un constat', 'post', f'/constatation/{CID}/upload-preuve',
     {'data': {'fichier': (io.BytesIO(b'%PDF-1.4'), 'p.pdf')}, 'content_type': 'multipart/form-data'}),
    ('ajouter un constat', 'post', f'/audit/{AID}/constatation/ajouter', {'data': {'description': 'nouveau'}}),
    ('ajouter une recommandation', 'post', f'/audit/{AID}/recommandation/ajouter', {'data': {'titre': 'x'}}),
    ('modifier la fiche de l\'audit', 'post', f'/audit/{AID}/edit', {'data': {'titre': 'retouché'}}),
    ('supprimer l\'audit', 'post', f'/audit/{AID}/supprimer', {}),
    ('modifier l\'équipe', 'post', f'/audit/{AID}/gerer-equipe', {'data': {'equipe_ids': str(ids['lecteur'])}}),
    ('nouvelle feuille de travail', 'post', f'/audit/{AID}/feuille-travail/nouvelle', {'data': {'titre': 'x'}}),
    ('modifier une feuille de travail', 'post', f'/feuille-travail/{FID}/mettre-a-jour', {'data': {'titre': 'x'}}),
    ('supprimer une feuille de travail', 'post', f'/feuille-travail/{FID}/supprimer', {}),
    ('ajouter un test (API)', 'post', f'/api/feuille-travail/{FID}/test', {'json': {'description': 'nouveau test'}}),
    ('modifier un test (API)', 'put', f'/api/feuille-travail/test/{TID}', {'json': {'description': 'retouché'}}),
    ('supprimer un test (API)', 'delete', f'/api/feuille-travail/test/{TID}', {}),
    ('ajouter une erreur à un test (API)', 'post', f'/api/feuille-travail/test/{TID}/erreur', {'json': {'description': 'x'}}),
    ('déposer une preuve dans la feuille', 'post', f'/feuille-travail/{FID}/upload-preuve',
     {'data': {'fichier': (io.BytesIO(b'%PDF-1.4'), 'p.pdf')}, 'content_type': 'multipart/form-data'}),
    ('commenter la feuille (API)', 'post', f'/api/feuille-travail/{FID}/commentaire', {'json': {'contenu': 'x'}}),
    ('restaurer une ancienne version (API)', 'post', f'/api/feuille-travail/{FID}/restaurer/1', {}),
    ('annuler la validation (circuit de revue)', 'post', f'/api/audit/{AID}/workflow/annuler-validation', {'json': {}}),
    ('appliquer un modèle de feuille', 'post', f'/api/modele-feuille/1/appliquer/{AID}', {'json': {}}),
]
for nom, methode, url, kw in TENTATIVES:
    r, fl = req('gestionnaire', methode, url, **kw)
    refuse = r.status_code == 423 or any('dossier de mission est figé' in m for m in fl)
    verif(f'figé : {nom} → refusé', refuse, (r.status_code, fl[:1]))
r, _ = req('admin_a', 'post', f'/constatation/{CID}/modifier', data={'description': 'retouché par l\'admin'})
verif('figé aussi pour l\'administrateur', r.status_code == 423 or obj(M.Constatation, CID).description == avant_cst)
verif('rien n\'a changé dans le dossier', obj(M.Constatation, CID) is not None and obj(M.Constatation, CID).description == avant_cst
      and obj(M.TestControleFeuille, TID) is not None and obj(M.TestControleFeuille, TID).objet_test == avant_test
      and obj(M.Audit, AID) is not None and obj(M.Audit, AID).titre == avant_titre and obj(M.FeuilleTravail, FID) is not None)
with A.app.app_context():
    verif('aucun test ajouté', n_tests() == n0, (n_tests(), n0))
r, _ = req('gestionnaire', 'put', f'/api/feuille-travail/test/{TID}', json={'description': 'x'})
verif('réponse API claire (423, « dossier_fige »)', r.status_code == 423 and (r.get_json() or {}).get('dossier_fige') is True, r.status_code)

print('--- Ce qui reste possible')
r, fl = req('validateur', 'post', f'/audit-suivi/{AID}/temps', data=dict(date=dt.date.today().isoformat(), heures='1.5', activite='suivi'))
with A.app.app_context():
    verif('temps de suivi saisi', M.TempsAudit.query.filter_by(audit_id=AID).count() == 1)
r, fl = req('gestionnaire', 'post', f'/audit/{AID}/changer-statut', data={'statut': 'termine'})
verif('changer le statut de l\'audit (clôture) : pas bloqué', r.status_code != 423 and not any('figé' in m for m in fl), (r.status_code, fl[:1]))
r, fl = req('gestionnaire', 'post', f'/audit/{AID}/upload-fichier-rapport',
            data={'fichier': (io.BytesIO(b'%PDF-1.4'), 'rapport_signe.pdf')}, content_type='multipart/form-data')
verif('déposer le rapport signé : pas bloqué', r.status_code != 423 and not any('figé' in m for m in fl), (r.status_code, fl[:1]))

print('--- Autre organisation')
r, fl = req('admin_b', 'post', f'/constatation/{CID}/modifier', data={'description': 'x'})
verif('autre organisation : rien sur l\'état du dossier (pas de 423)', r.status_code != 423 and not any('figé' in m for m in fl), r.status_code)

print('--- Réouverture motivée')
r, fl = req('validateur', 'post', f'/audit-suivi/{AID}/dossier/rouvrir', data={'motif': 'Erreur de saisie dans le test T-01'})
verif('membre sans droit de gestion : réouverture refusée', r.status_code == 403 and obj(M.Audit, AID).dossier_rouvert_le is None, r.status_code)
req('gestionnaire', 'post', f'/audit-suivi/{AID}/dossier/rouvrir', data={'motif': 'erreur'})
verif('motif trop court : refusé', obj(M.Audit, AID).dossier_rouvert_le is None)
r, fl = req('gestionnaire', 'post', f'/audit-suivi/{AID}/dossier/rouvrir', data={'motif': 'Erreur de saisie dans le test T-01 relevée en revue qualité'})
a = obj(M.Audit, AID)
verif('réouverture par le gestionnaire, motif conservé', a.dossier_rouvert_le is not None and 'revue qualité' in (a.dossier_rouvert_motif or ''))
with A.app.app_context():
    verif('réouverture journalisée', M.JournalActiviteClient.query.filter_by(action='audit_dossier_rouvert').count() == 1)
    verif('équipe prévenue', M.Notification.query.filter_by(destinataire_id=ids['validateur']).filter(
        M.Notification.titre.like('Dossier rouvert%')).count() >= 1)
r, _ = req('gestionnaire', 'get', f'/audit-suivi/{AID}/reponses')
verif('page : « Dossier rouvert » et bouton « Figer de nouveau »', r.status_code == 200 and b'Dossier rouvert' in r.data and b'Figer de nouveau' in r.data)
r, fl = req('gestionnaire', 'put', f'/api/feuille-travail/test/{TID}', json={'objet_test': 'Contrôle des bons de commande (corrigé)'})
verif('dossier rouvert : la correction passe', r.status_code != 423, r.status_code)
req('gestionnaire', 'post', f'/audit-suivi/{AID}/dossier/figer')
verif('figé de nouveau', obj(M.Audit, AID).dossier_rouvert_le is None)
with A.app.app_context():
    verif('nouveau verrouillage journalisé', M.JournalActiviteClient.query.filter_by(action='audit_dossier_refige').count() == 1)
r, _ = req('gestionnaire', 'put', f'/api/feuille-travail/test/{TID}', json={'description': 'encore'})
verif('après le nouveau verrouillage : refusé', r.status_code == 423, r.status_code)
r, _ = req('gestionnaire', 'get', f'/audit-suivi/{AID}/reponses')
verif('page : « Dossier figé » et formulaire de réouverture', b'Dossier fig' in r.data and b'Rouvrir le dossier' in r.data)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
