"""Recette des améliorations : registre des recommandations, KRI, audit (rapport, réponses, temps, indépendance, programme)."""
import io, sys, datetime as dt
import socle, objets
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
    O = objets.peupler_objets(A, ids)['a']
import models as M
from models import db

res = []
def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)
nav = {r: socle.navigateur(A, ids[r]) for r in ('gestionnaire', 'validateur', 'operateur', 'lecteur', 'admin_a', 'admin_b')}
def get(role, url):
    r = appel(nav[role], 'get', url); e = socle.cause(A); return r, e
def post(role, url, **kw):
    r = appel(nav[role], 'post', url, **kw); e = socle.cause(A); return r, e
def obj(Mod, i):
    with A.app.app_context():
        o = db.session.get(Mod, i); db.session.expunge(o) if o is not None else None; return o

# =========================================================== 1. Registre des recommandations
print('--- Registre des recommandations')
r, e = post('gestionnaire', '/recommandations/externe/nouvelle', data=dict(
    source='cac', emetteur='Cabinet XYZ — exercice 2025', titre='Formaliser la séparation des tâches en trésorerie',
    description='Le même agent saisit et valide les virements.', priorite='haute', date_echeance='2026-01-15',
    responsable_id=str(ids['operateur'])))
with A.app.app_context():
    ext = M.RecommandationExterne.query.first(); eid = ext.id if ext else None
verif('Le gestionnaire crée une recommandation du commissaire aux comptes', eid and r.status_code == 302, f'{r.status_code} {e}')
r, e = get('gestionnaire', '/recommandations/'); t = r.data.decode('utf-8', 'ignore')
verif('Elle apparaît dans le registre, avec les indicateurs', r.status_code == 200 and 'Formaliser la séparation' in t and 'Taux de mise en œuvre' in t, f'{r.status_code} {e}')
r, e = get('lecteur', '/recommandations/')
verif('Un simple lecteur n\'ouvre pas le registre', r.status_code in (302, 403), str(r.status_code))
r, e = get('operateur', '/recommandations/miennes'); t = r.data.decode('utf-8', 'ignore')
verif('L\'opérateur la voit dans « Mes recommandations » (espace opérateur)', r.status_code == 200 and 'Formaliser la séparation' in t and 'sidebar-operateur' in t, f'{r.status_code} {e}')
r, e = post('operateur', f'/recommandations/externe/{eid}/avancement', data=dict(progression='50', commentaire=''))
verif('Avancement sans commentaire refusé', obj(M.RecommandationExterne, eid).progression == 0)
r, e = post('operateur', f'/recommandations/externe/{eid}/avancement', data=dict(progression='50', commentaire='Procédure rédigée'))
verif('Avancement à 50 % enregistré', obj(M.RecommandationExterne, eid).progression == 50, e)
r, e = post('operateur', f'/recommandations/externe/{eid}/avancement', data=dict(progression='100', commentaire='Mis en place', demander_cloture='1'))
verif('Demande de clôture sans preuve refusée', obj(M.RecommandationExterne, eid).demande_cloture_le is None)
r, e = post('operateur', f'/recommandations/externe/{eid}/avancement', content_type='multipart/form-data',
            data=dict(progression='100', commentaire='Mis en place', demander_cloture='1', preuve=(io.BytesIO(b'%PDF-1.4 preuve'), 'procedure.pdf')))
x = obj(M.RecommandationExterne, eid)
verif('Avec une preuve : clôture demandée', x.demande_cloture_le is not None and x.progression == 100, e)
r, e = post('operateur', f'/recommandations/externe/{eid}/avancement', content_type='multipart/form-data',
            data=dict(progression='100', commentaire='x', preuve=(io.BytesIO(b'MZ'), 'virus.exe')))
with A.app.app_context():
    n_exe = M.SuiviRecommandation.query.filter(M.SuiviRecommandation.nom_fichier.like('%.exe')).count()
verif('Fichier .exe refusé comme preuve', n_exe == 0)
r, e = post('operateur', f'/recommandations/externe/{eid}/cloture', data=dict(decision='valider'))
verif('Le responsable ne valide pas sa propre clôture', obj(M.RecommandationExterne, eid).statut != 'cloturee')
with A.app.app_context():
    sid = M.SuiviRecommandation.query.filter(M.SuiviRecommandation.fichier.isnot(None)).first().id
r, _ = get('operateur', f'/recommandations/preuve/{sid}')
verif('Le responsable télécharge sa preuve', r.status_code == 200 and r.data.startswith(b'%PDF'), str(r.status_code))
r, _ = get('admin_b', f'/recommandations/preuve/{sid}')
verif('L\'autre organisation ne peut pas la télécharger', r.status_code == 404, str(r.status_code))
r, _ = get('admin_b', f'/recommandations/externe/{eid}')
verif('… ni ouvrir la fiche', r.status_code == 404, str(r.status_code))
r, e = post('validateur', f'/recommandations/externe/{eid}/cloture', data=dict(decision='valider', commentaire='Preuve conforme'))
x = obj(M.RecommandationExterne, eid)
verif('Un autre gestionnaire valide : clôturée', x.statut == 'cloturee' and x.cloture_validee_par_id == ids['validateur'], e)

with A.app.app_context():
    audit = socle.creer(M.Audit, reference='AUD-REC', titre='Audit trésorerie', type_audit='interne', client_id=1,
                        responsable_id=ids['gestionnaire'], equipe_audit_ids=str(ids['validateur']),
                        participants_ids=str(ids['lecteur']), created_by=ids['gestionnaire'])
    cst = socle.creer(M.Constatation, reference='CST-1', description='Rapprochements bancaires non revus', audit_id=audit.id,
                      client_id=1, created_by=ids['gestionnaire'])
    reco = socle.creer(M.Recommandation, reference='REC-1', description='Faire revoir les rapprochements par le N+1',
                       type_recommandation='corrective', audit_id=audit.id, constatation_id=cst.id, client_id=1, urgence=2, impact_operationnel=2,
                       responsable_id=ids['lecteur'], created_by=ids['gestionnaire'],
                       date_echeance=dt.date.today() - dt.timedelta(days=10))
    db.session.commit(); aid, cid, rid = audit.id, cst.id, reco.id
r, e = get('lecteur', '/recommandations/miennes'); t = r.data.decode('utf-8', 'ignore')
verif('Une recommandation d\'audit apparaît chez son responsable, signalée en retard', 'REC-1' in t and 'de retard' in t, e)
post('lecteur', f'/recommandations/audit/{rid}/avancement', content_type='multipart/form-data',
     data=dict(progression='100', commentaire='Revue mise en place', demander_cloture='1', preuve=(io.BytesIO(b'ok'), 'pv.txt')))
r, e = post('gestionnaire', f'/recommandations/audit/{rid}/cloture', data=dict(decision='refuser', commentaire='court'))
verif('Refus de clôture sans motif suffisant refusé', obj(M.Recommandation, rid).demande_cloture_le is not None)
r, e = post('gestionnaire', f'/recommandations/audit/{rid}/cloture', data=dict(decision='refuser', commentaire='Joindre le PV signé par le N+1'))
x = obj(M.Recommandation, rid)
verif('Refus motivé : la demande est annulée, le motif est gardé', x.demande_cloture_le is None and x.motif_refus_cloture and x.statut != 'termine', e)
with A.app.app_context():
    from egalyx.recommandations import registre, indicateurs
    ind = indicateurs(registre(1))
verif('Indicateurs : 1 clôturée sur 2, 1 échue', ind['cloturees'] == 1 and ind['total'] == 2 and ind['echues'] == 1, str(ind))

# =========================================================== 2. KRI
print('--- KRI')
from egalyx.kri_suivi import SeuilsIncoherents, fraicheur
with A.app.app_context():
    k = M.KRI(nom='Taux de rejets de virements', client_id=1, risque_id=O['risque'], seuil_alerte=8, seuil_critique=5,
              sens_evaluation_seuil='superieur', frequence_mesure='mensuel', type_indicateur='kri')
    db.session.add(k)
    try:
        db.session.commit(); refuse = False
    except SeuilsIncoherents:
        db.session.rollback(); refuse = True
verif('Seuils incohérents refusés (alerte 8 > critique 5 alors que le risque monte avec la valeur)', refuse)
with A.app.app_context():
    k = M.KRI(nom='Taux de rejets de virements', client_id=1, risque_id=O['risque'], seuil_alerte=5, seuil_critique=8,
              sens_evaluation_seuil='superieur', frequence_mesure='mensuel', type_indicateur='kri')
    db.session.add(k); db.session.commit(); kid = k.id
    verif('KRI jamais mesuré : « jamais »', fraicheur(k)['etat'] == 'jamais')
    db.session.add(M.MesureKRI(kri_id=kid, valeur=6, date_mesure=dt.datetime.utcnow() - dt.timedelta(days=70), client_id=1))
    db.session.commit()
    k = db.session.get(M.KRI, kid)
    verif('Dernière mesure il y a 70 jours pour un KRI mensuel : « en retard »', fraicheur(k)['etat'] == 'en_retard', str(fraicheur(k)))
    verif('Avec les seuils actuels, 6 est « alerte »', k.get_etat_alerte(6) == 'alerte')
    k.seuil_alerte, k.seuil_critique = 3, 4; db.session.commit()
    h = M.HistoriqueSeuilKRI.query.filter_by(kri_id=kid).all()
    verif('Changement de seuils : l\'ancien jeu est conservé', len(h) == 1 and h[0].seuil_alerte == 5 and h[0].seuil_critique == 8)
    k = db.session.get(M.KRI, kid)
    vieille = dt.datetime.utcnow() - dt.timedelta(days=70)
    verif('La mesure ancienne (6) reste « alerte » avec les seuils de son époque', k.get_etat_alerte(6, vieille) == 'alerte')
    verif('… mais serait « critique » avec les nouveaux seuils', k.get_etat_alerte(6) == 'critique')
    verif('Le changement de seuil ne laisse pas le KRI modifié', not db.session.dirty)
    avant = M.Notification.query.filter_by(type_notification='kri_critique').count()
    db.session.add(M.MesureKRI(kri_id=kid, valeur=9, date_mesure=dt.datetime.utcnow(), client_id=1)); db.session.commit()
    apres = M.Notification.query.filter_by(type_notification='kri_critique').all()
    dest = {n.destinataire_id for n in apres}
    verif('Mesure critique : les gestionnaires des risques sont invités à réévaluer le risque',
          len(apres) > avant and ids['admin_a'] in dest and ids['validateur'] in dest and ids['lecteur'] not in dest, str(dest))
r, e = get('admin_a', '/dashboard-strategique'); t = r.data.decode('utf-8', 'ignore')
verif('Tableau stratégique : la page s\'ouvre avec le nouveau KRI', r.status_code == 200, e)
r, e = get('gestionnaire', '/kri'); t = r.data.decode('utf-8', 'ignore')
verif('Liste des KRI : la page s\'ouvre', r.status_code == 200, e)
r, e = get('gestionnaire', f'/kri/{kid}/detail'); t = r.data.decode('utf-8', 'ignore')
verif('Fiche du KRI (seuils historiques dans l\'historique des mesures) : la page s\'ouvre', r.status_code == 200, e)

# =========================================================== 3. Audit
print('--- Audit')
r, e = get('gestionnaire', f'/audit/{aid}'); t = r.data.decode('utf-8', 'ignore')
verif('Fiche de l\'audit : encadré « Rapport et équipe »', r.status_code == 200 and 'id="suivi-rapport"' in t and 'Indépendance' in t, f'{r.status_code} {e}')
r, e = post('gestionnaire', f'/audit-suivi/{aid}/rapport/provisoire', data=dict(date_limite=''))
verif('Rapport provisoire refusé tant que l\'équipe n\'a pas signé l\'indépendance', obj(M.Audit, aid).etat_rapport is None)
post('validateur', f'/audit-suivi/{aid}/independance', data=dict(conflit='1', details='', atteste='1'))
with A.app.app_context():
    n = M.DeclarationIndependance.query.filter_by(audit_id=aid).count()
verif('Conflit signalé sans explication refusé', n == 0)
post('validateur', f'/audit-suivi/{aid}/independance', data=dict(conflit='0', atteste='1'))
post('gestionnaire', f'/audit-suivi/{aid}/independance', data=dict(conflit='0', atteste='1'))
r, e = post('lecteur', f'/audit-suivi/{aid}/independance', data=dict(conflit='0', atteste='1'))
with A.app.app_context():
    n = M.DeclarationIndependance.query.filter_by(audit_id=aid).count()
verif('Les deux membres de l\'équipe signent (un audité ne peut pas)', n == 2, str(n))
post('gestionnaire', f'/audit-suivi/{aid}/reponses', data=dict(constatation_id=str(cid), quoi='5c', critere='Procédure trésorerie §4.2',
                                                              cause_racine='Effectif réduit', consequence='Fraude non détectée'))
x = obj(M.Constatation, cid)
verif('Constat complété en 5C (critère, cause, conséquence)', x.critere and x.consequence == 'Fraude non détectée')
r, e = post('lecteur', f'/audit-suivi/{aid}/reponses', data=dict(constatation_id=str(cid), quoi='reponse', position='accord', reponse='Nous sommes d\'accord'))
verif('Pas de réponse avant le rapport provisoire', obj(M.Constatation, cid).reponse_audite is None)
r, e = post('gestionnaire', f'/audit-suivi/{aid}/rapport/provisoire', data=dict(date_limite=''))
a = obj(M.Audit, aid)
verif('Rapport provisoire émis, date limite à 15 jours', a.etat_rapport == 'provisoire' and a.date_limite_reponses == dt.date.today() + dt.timedelta(days=15), e)
with A.app.app_context():
    notif = M.Notification.query.filter_by(destinataire_id=ids['lecteur'], type_notification='audit_rapport').count()
verif('L\'audité est prévenu', notif >= 1)
r, e = post('gestionnaire', f'/audit-suivi/{aid}/rapport/definitif')
verif('Rapport définitif refusé : pas de réponse et date limite non passée', obj(M.Audit, aid).etat_rapport == 'provisoire')
post('lecteur', f'/audit-suivi/{aid}/reponses', data=dict(constatation_id=str(cid), quoi='reponse', position='accord', reponse='Nous sommes d\'accord'))
verif('« D\'accord » sans plan d\'action refusé', obj(M.Constatation, cid).reponse_audite is None)
post('lecteur', f'/audit-suivi/{aid}/reponses', data=dict(constatation_id=str(cid), quoi='reponse', position='accord', reponse='Nous sommes d\'accord',
                                                          plan='Revue mensuelle signée par le N+1', date_engagement='2026-12-31'))
x = obj(M.Constatation, cid)
verif('Réponse de l\'audité enregistrée (position, plan, engagement)', x.position_audite == 'accord' and x.date_engagement == dt.date(2026, 12, 31))
r, e = post('gestionnaire', f'/audit-suivi/{aid}/rapport/definitif')
verif('Rapport définitif émis', obj(M.Audit, aid).etat_rapport == 'definitif', e)
post('lecteur', f'/audit-suivi/{aid}/reponses', data=dict(constatation_id=str(cid), quoi='reponse', position='desaccord', reponse='Finalement non'))
verif('Après le définitif, la réponse est figée', obj(M.Constatation, cid).position_audite == 'accord')
r, e = get('lecteur', f'/audit-suivi/{aid}/reponses')
verif('L\'audité consulte la page des réponses', r.status_code == 200, e)
r, e = get('admin_b', f'/audit-suivi/{aid}/reponses')
verif('L\'autre organisation ne la voit pas', r.status_code == 404, str(r.status_code))
post('validateur', f'/audit-suivi/{aid}/temps', data=dict(date=dt.date.today().isoformat(), heures='3.5', activite='terrain'))
post('validateur', f'/audit-suivi/{aid}/temps', data=dict(date=(dt.date.today() + dt.timedelta(days=3)).isoformat(), heures='2', activite='terrain'))
r, _ = post('lecteur', f'/audit-suivi/{aid}/temps', data=dict(date=dt.date.today().isoformat(), heures='2', activite='terrain'))
with A.app.app_context():
    tot = sum(t.heures for t in M.TempsAudit.query.filter_by(audit_id=aid).all())
verif('Temps : 3,5 h saisies ; date future et non-membre refusés', tot == 3.5 and r.status_code == 403, f'{tot} {r.status_code}')
r, e = get('gestionnaire', f'/audit-suivi/{aid}/temps')
verif('Page du temps passé', r.status_code == 200 and '3.5' in r.data.decode(), e)

print('--- Programme d\'audit')
pid = O['programme']
import os
os.environ['EGALYX_PROGRAMME_DOUBLE_REGARD'] = '1'
r, e = post('gestionnaire', f'/programme-audit/{pid}/approuver', data=dict(date_approbation='2026-11-05'))
verif('Option « double regard » activée : l\'auteur ne l\'approuve pas lui-même', obj(M.ProgrammeAudit, pid).statut == 'en_elaboration', e)
os.environ.pop('EGALYX_PROGRAMME_DOUBLE_REGARD')
r, e = post('gestionnaire', f'/programme-audit/{pid}/approuver', data=dict(date_approbation='2026-11-05'))
p = obj(M.ProgrammeAudit, pid)
with A.app.app_context():
    auto = M.JournalAuditProgramme.query.filter_by(programme_id=pid, action='auto_approbation').count()
verif('Par défaut, l\'auteur peut l\'approuver : noté « auto-approbation »', p.statut == 'actif' and p.approuve_par_id == ids['gestionnaire'] and auto == 1, e)
r, e = post('validateur', f'/programme-audit/{pid}/approuver', data=dict(date_approbation='2026-11-05'))
with A.app.app_context():
    nb_appro = M.JournalAuditProgramme.query.filter(M.JournalAuditProgramme.programme_id == pid,
                                                    M.JournalAuditProgramme.action.in_(['approbation', 'auto_approbation'])).count()
    p2 = db.session.get(M.ProgrammeAudit, pid)
verif('Approuver deux fois est refusé', nb_appro == 1 and p2.approuve_par_id == ids['gestionnaire'], str(nb_appro))
r, e = post('validateur', f'/programme-audit/{pid}/desapprouver', data=dict(raison='court'))
verif('Désapprobation sans motif refusée', obj(M.ProgrammeAudit, pid).statut == 'actif')
r, e = post('validateur', f'/programme-audit/{pid}/desapprouver', data=dict(raison='Périmètre à revoir après la réorganisation'))
p = obj(M.ProgrammeAudit, pid)
with A.app.app_context():
    j = M.JournalAuditProgramme.query.filter_by(programme_id=pid, action='desapprobation').first()
verif('Désapprobation motivée : motif à part (plus dans « archivage ») et journalisée',
      p.statut == 'en_elaboration' and p.motif_desapprobation and not p.archive_reason and j is not None, e)

print('--- Plan d\'action ↔ audits')
r, e = appel(nav['gestionnaire'], 'put', f'/api/plan-action/{O["plan"]}/audits', json={'audit_ids': [aid]}), socle.cause(A)
with A.app.app_context():
    pl = db.session.get(M.PlanAction, O['plan']); liens = [x.id for x in pl.audits]
verif('Le lien plan d\'action ↔ audits est enregistré', liens == [aid], f'{r.status_code} {e} {liens}')

print('--- Lien vers le contrôle N2')
with A.app.app_context():
    rc = M.RecommandationC2N(planification_id=O['planification'], titre='Renforcer les contrôles', client_id=1,
                             statut='acceptee', responsable_id=ids['operateur'], created_by=ids['gestionnaire'])
    db.session.add(rc); db.session.commit(); rcid = rc.id
r, e = get('gestionnaire', f'/recommandations/c2n/{rcid}'); t = r.data.decode('utf-8', 'ignore')
import re as _re
lien = _re.search(r'href="([^"]+)"[^>]*><i class="fas fa-up-right-from-square', t)
verif('Fiche d\'une recommandation N2 : le lien mène à une page (pas à des données brutes)',
      r.status_code == 200 and lien and '/detail' not in lien.group(1), lien.group(1) if lien else e)
r2, e2 = get('gestionnaire', lien.group(1)) if lien else (None, '')
verif('… et cette page s\'affiche en HTML', r2 is not None and r2.status_code == 200 and 'text/html' in r2.headers.get('Content-Type', ''),
      f"{getattr(r2, 'status_code', '?')} {e2}")

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
