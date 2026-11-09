"""Matrice de sécurité des décisions : chaque rôle tente chaque action (même sans bouton, en forgeant la requête).
On regarde en base si l'action a réellement eu lieu."""
import re, json, sys
import socle, objets
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
    O = objets.peupler_objets(A, ids)['a']
import models as M
from models import db

MOTIF = {'raison': 'Motif de recette suffisamment long', 'commentaire': 'Commentaire de recette', 'motif': 'Motif de recette long',
         'date_approbation': '2026-11-05', 'nouvelle_annee': '2027', 'nouveau_statut': 'cloturee', 'statut': 'cloturee',
         'progression': '100', 'action': 'approuver', 'decision': 'valider'}
# (libellé, méthode, url, modèle, id, champ, valeur de départ, rôles qui DEVRAIENT pouvoir)
CAS = [
 ('Approuver un programme d\'audit', 'POST', '/programme-audit/{programme}/approuver', M.ProgrammeAudit, O['programme'], 'statut', 'en_elaboration', 'admin_a gestionnaire validateur'),
 ('Désapprouver un programme d\'audit', 'POST', '/programme-audit/{programme}/desapprouver', M.ProgrammeAudit, O['programme'], 'statut', 'actif', 'admin_a gestionnaire validateur'),
 ('Archiver un programme d\'audit', 'POST', '/programme-audit/{programme}/archiver', M.ProgrammeAudit, O['programme'], 'statut', 'en_elaboration', 'admin_a gestionnaire validateur'),
 ('Supprimer une mission d\'audit', 'POST', '/mission-audit/{mission}/supprimer', M.MissionAudit, O['mission'], 'statut', 'planifiee', 'admin_a gestionnaire'),
 ('Reprogrammer une mission d\'audit', 'POST', '/mission-audit/{mission}/reprogrammer', M.MissionAudit, O['mission'], 'annee_prevue', 2026, 'admin_a gestionnaire'),
 ('Convertir une mission en audit (lien)', 'GET', '/mission-audit/{mission}/convertir-audit', M.MissionAudit, O['mission'], 'statut', 'planifiee', 'admin_a gestionnaire'),
 ('Rejeter une recommandation N2', 'POST', '/c2n/recommandation/{reco}/rejeter', M.RecommandationC2N, O['reco'], 'statut', 'proposee', 'admin_a gestionnaire validateur'),
 ('Accepter une recommandation N2', 'POST', '/c2n/recommandation/{reco}/accepter', M.RecommandationC2N, O['reco'], 'statut', 'proposee', 'admin_a gestionnaire validateur'),
 ('Valider un risque proposé', 'POST', '/risque/{risque_propose}/valider', M.Risque, O['risque_propose'], 'statut', 'en_validation', 'admin_a validateur'),
 ('Rejeter un risque proposé', 'POST', '/risque/{risque_propose}/rejeter', M.Risque, O['risque_propose'], 'statut', 'en_validation', 'admin_a validateur'),
 ('Clôturer une campagne d\'évaluation (lien)', 'GET', '/cartographie/{carto}/cloturer-campagne/{campagne_eval}', M.CampagneEvaluation, O['campagne_eval'], 'statut', 'en_cours', 'admin_a gestionnaire'),
 ('Valider une campagne de contrôle', 'POST', '/operateur/campagne/{campagne}/valider', M.CampagneControle, O['campagne'], 'statut', 'en_attente_validation', 'admin_a gestionnaire validateur'),
 ('Rejeter une campagne de contrôle', 'POST', '/operateur/campagne/{campagne}/rejeter', M.CampagneControle, O['campagne'], 'statut', 'en_attente_validation', 'admin_a gestionnaire validateur'),
 ('Valider une planification N2', 'POST', '/c2n/planification/{planification}/valider', M.PlanificationControle, O['planification'], 'statut', 'soumis', 'admin_a gestionnaire validateur'),
 ('Terminer un plan d\'action', 'POST', '/plan-action-independant/{plan}/terminer', M.PlanAction, O['plan'], 'statut', 'en_cours', 'admin_a gestionnaire validateur'),
]
ROLES = ['admin_a', 'gestionnaire', 'validateur', 'operateur', 'lecteur', 'admin_b']
def jeton(c):
    r = appel(c, 'get', '/dashboard')
    m = re.search(r'name="csrf-token" content="([^"]+)"', r.data.decode('utf-8', 'ignore')) or \
        re.search(r'csrf_token[^>]*value="([^"]+)"', r.data.decode('utf-8', 'ignore'))
    return m.group(1) if m else ''
lignes = []
for lib, meth, url, Mod, oid, champ, depart, attendus in CAS:
    url = url.format(**O)
    ligne = {'action': lib, 'url': url}
    for role in ROLES:
        with A.app.app_context():
            o = db.session.get(Mod, oid); setattr(o, champ, depart)
            if hasattr(o, 'is_archived'): o.is_archived = False
            if Mod is M.CampagneControle:
                o.soumis_par_id = ids['operateur']
            if Mod is M.PlanificationControle:
                o.soumis_par_id = ids['operateur']
            if lib.startswith('Convertir'):
                M.Audit.query.filter(M.Audit.reference.like('AUD-%')).delete(synchronize_session=False)
                o.audit_id = None if hasattr(o, 'audit_id') else None
            db.session.commit()
        c = socle.navigateur(A, ids[role])
        if meth == 'GET':
            rep = appel(c, 'get', url + ('&' if '?' in url else '?') + 'csrf_token=' + jeton(c))
        else:
            rep = appel(c, 'post', url, data=MOTIF, headers={'X-Requested-With': 'XMLHttpRequest'})
            if rep.status_code in (400, 415) or b'JSON' in (rep.data or b'')[:400]:
                rep = appel(c, 'post', url, json=MOTIF)
        err = socle.cause(A) if rep.status_code >= 500 else ''
        socle.cause(A)
        with A.app.app_context():
            o = db.session.get(Mod, oid)
            apres = getattr(o, champ); arch = getattr(o, 'is_archived', False)
        fait = (apres != depart) or bool(arch)
        ligne[role] = {'fait': fait, 'code': rep.status_code, 'apres': apres, 'err': err, 'attendu': role in attendus.split()}
    lignes.append(ligne)
json.dump(lignes, open(socle.ICI + '/securite.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(f"{'Action':42}" + ''.join(f'{r[:11]:>12}' for r in ROLES))
for l in lignes:
    cel = ''
    for r in ROLES:
        x = l[r]
        s = ('FAIT' if x['fait'] else 'refusé') + ('' if x['code'] < 500 else '!500')
        if x['fait'] and not x['attendu']: s = '⚠' + s
        if not x['fait'] and x['attendu']: s = '?' + s
        cel += f'{s:>12}'
    print(f"{l['action'][:42]:42}{cel}")
