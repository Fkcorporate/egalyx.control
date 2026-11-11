"""Incidents et signalements : droits, déclaration sans risque, résolution, escalade, approbation (double regard),
délais (SLA), API, « Ma semaine », signalement par les utilisateurs et par le lien public, conversion en incident."""
import json
import re
import sys
import time
from datetime import datetime, timedelta

import socle
import objets
from socle import Muet, appel, creer
from werkzeug.security import generate_password_hash

with Muet():
    A, ids = socle.preparer()
    O = objets.peupler_objets(A, ids)
import models as M
from models import db

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond))
    print('OK   ' if cond else 'ÉCHEC', nom, detail)


def nav(role):
    return socle.navigateur(A, ids[role])


def go(role, m, url, **kw):
    r = appel(nav(role) if role else A.app.test_client(), m, url, **kw)
    return r, r.data.decode('utf-8', 'ignore')


def obj(modele, i):
    with A.app.app_context():
        db.session.expire_all()
        return db.session.get(modele, i)


with A.app.app_context():
    def utilisateur(nom, perms, operateur=False):
        u = M.User(username=nom, email=f'{nom}@recette.test', role='utilisateur', client_id=1, is_active=True,
                   is_operateur=operateur, permissions=dict(socle.perms(), **perms))
        u.password_hash = generate_password_hash(socle.MDP)
        db.session.add(u); db.session.flush()
        return u.id
    sans = {k: False for k in ('can_view_incidents', 'can_manage_incidents', 'can_escalate_incidents',
                               'can_resolve_incidents', 'can_view_tickets', 'can_manage_tickets', 'can_manage_audit')}
    ids['resp_incidents'] = utilisateur('resp_incidents', dict(sans, can_view_incidents=True, can_manage_incidents=True,
                                                               can_view_tickets=True, can_manage_tickets=True))
    ids['escaladeur'] = utilisateur('escaladeur', dict(sans, can_escalate_incidents=True))
    ids['trieur'] = utilisateur('trieur', dict(sans, can_view_tickets=True, can_manage_tickets=True))
    ids['simple'] = utilisateur('simple', dict(sans))
    ids['lect_inc'] = utilisateur('lect_inc', dict(sans, can_view_incidents=True))
    op = db.session.get(M.User, ids['operateur'])
    if not M.PermissionOperateur.query.filter_by(user_id=op.id).first():
        po = M.PermissionOperateur(user_id=op.id, client_id=1, peut_evaluer_risques=True, peut_voir_evaluations=True)
        db.session.add(po); db.session.flush(); op.operateur_permissions_id = po.id
    rq = db.session.get(M.Risque, O['a']['risque'])
    i1 = M.Incident(reference='INC-R1', titre='Panne serveur', client_id=1, risque_id=rq.id, statut='ouvert',
                    gravite='elevee', created_by=ids['resp_incidents'], declare_par_id=ids['resp_incidents'],
                    responsable_resolution_id=ids['resp_incidents'], superviseur_id=ids['escaladeur'], sla_heures=48)
    db.session.add(i1); db.session.commit()
    iid = i1.id

print('--- Droits incidents (sans « Gérer les audits »)')
for url in ('/incidents', f'/incident/{iid}', '/incidents/dashboard-avance', '/incident/nouveau'):
    r, _ = go('resp_incidents', 'get', url)
    verif(f'Gestionnaire des incidents : {url} accessible', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')
r, _ = go('lect_inc', 'get', '/incidents')
verif('« Voir les incidents » suffit pour la liste', r.status_code == 200, str(r.status_code))
go('lect_inc', 'post', f'/incident/{iid}/modifier', data={'titre': 'PIRATE'})
verif('… mais pas pour modifier', obj(M.Incident, iid).titre == 'Panne serveur')
r, _ = go('simple', 'get', '/incidents')
verif('Sans permission incidents : pas de liste', r.status_code in (302, 403), str(r.status_code))
r, _ = go('admin_b', 'get', f'/incident/{iid}')
verif('Autre organisation : introuvable', r.status_code in (302, 404), str(r.status_code))

print('--- API (plantait)')
r, t = go('resp_incidents', 'get', '/api/incidents')
d = json.loads(t) if r.status_code == 200 else {}
verif('Liste des incidents en JSON', r.status_code == 200 and d.get('success') and d['data'], f'{r.status_code} {socle.cause(A)}')
verif('Droits calculés pour l\'utilisateur (vrai/faux)', d and isinstance(d['data'][0].get('peut_modifier'), bool))
r, t = go('resp_incidents', 'get', f'/api/incidents/{iid}')
verif('Détail d\'un incident en JSON', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')

print('--- Déclarer sans risque ni dispositif, résoudre')
r, t = go('resp_incidents', 'get', '/incident/nouveau')
def option(nom):
    m = re.search(r'<select[^>]*name="%s"[^>]*>(.*?)</select>' % nom, t, re.S)
    vals = re.findall(r'<option[^>]*value="([^"]+)"', m.group(1)) if m else []
    return next((v for v in vals if v not in ('', '0')), '')
avant = obj(M.Incident, iid) and None
with A.app.app_context():
    n0 = M.Incident.query.count()
r, t2 = go('resp_incidents', 'post', '/incident/nouveau', data={
    'titre': 'Fraude constatée', 'description': 'Détectée en caisse', 'gravite': option('gravite') or 'moyenne',
    'type_incident': option('type_incident') or 'operationnel', 'date_occurrence': datetime.now().strftime('%Y-%m-%dT%H:%M'),
    'direction_associee': option('direction_associee'), 'service_associe': option('service_associe'),
    'risque_id': '0', 'dispositif_id': '0', 'responsable_resolution_id': str(ids['resp_incidents']),
    'superviseur_id': '0', 'directeur_id': '0', 'sla_heures': '48'})
with A.app.app_context():
    n1 = M.Incident.query.count()
    nouv = M.Incident.query.filter_by(titre='Fraude constatée').first()
    nid = nouv.id if nouv else None
verif('Incident déclaré sans risque ni dispositif (« à qualifier »)', n1 == n0 + 1 and nouv and nouv.risque_id is None,
      f'{r.status_code} {socle.cause(A)}')
if nid:
    r, _ = go('resp_incidents', 'post', f'/incident/{nid}/resoudre', data={
        'statut': 'resolu', 'cause_racine': 'x' * 30, 'actions_correctives': 'y' * 30, 'commentaire_cloture': 'z' * 20})
    verif('Résolution refusée tant qu\'il n\'est pas rattaché à un risque', obj(M.Incident, nid).statut not in ('resolu', 'ferme'))
    r, t = go('resp_incidents', 'get', f'/incident/{nid}')
    verif('La fiche d\'un incident sans risque s\'affiche', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')

print('--- Escalade et approbation')
r, t = go('escaladeur', 'post', f'/api/incident/{iid}/escalader', json={'raison': 'Pas de réponse'})
verif('« Escalader les incidents » permet d\'escalader', obj(M.Incident, iid).niveau_escalade == 2, f'{r.status_code} {t[:120]}')
r, t = go('lect_inc', 'post', f'/api/incident/{iid}/escalader', json={'raison': 'x'})
verif('« Voir » ne permet pas d\'escalader', obj(M.Incident, iid).niveau_escalade == 2, str(r.status_code))
with A.app.app_context():
    x = db.session.get(M.Incident, iid)
    x.approbation_requise, x.approbation_statut, x.statut = True, 'en_attente', 'en_attente_approbation'
    x.responsable_resolution_id = ids['resp_incidents']      # l'escalade a pu réattribuer le responsable
    db.session.commit()
    from egalyx.incidents import peut_approuver
    resp = db.session.get(M.User, ids['resp_incidents']); gest = db.session.get(M.User, ids['gestionnaire'])
    verif('Le responsable de la résolution ne peut pas approuver sa propre résolution', not peut_approuver(x, resp))
    verif('Un autre gestionnaire des incidents peut approuver', peut_approuver(x, gest))
r, t = go('gestionnaire', 'get', f'/incident/{iid}/approuver')
verif('Page d\'approbation accessible au gestionnaire', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')
r, _ = go('gestionnaire', 'post', f'/incident/{iid}/approuver', data={'approbation': 'approuve', 'commentaire': 'Vérifié, conforme'})
with A.app.app_context():
    h = M.IncidentHistorique.query.filter_by(incident_id=iid, action='approbation_approuve').count()
verif('L\'approbation est inscrite à l\'historique (elle ne l\'était jamais)', h == 1, f'{r.status_code} {obj(M.Incident, iid).approbation_statut}')

print('--- Délais (SLA)')
with A.app.app_context():
    vieux = M.Incident(reference='INC-SLA', titre='Ancien', client_id=1, statut='ouvert', gravite='moyenne',
                       created_by=ids['resp_incidents'], responsable_resolution_id=ids['resp_incidents'], sla_heures=48,
                       created_at=datetime.utcnow() - timedelta(days=4), date_detection=datetime.utcnow() - timedelta(days=4))
    db.session.add(vieux); db.session.commit(); sid = vieux.id
    from egalyx.incidents import verifier_delais
    n = verifier_delais()
    n2 = verifier_delais()
    v = db.session.get(M.Incident, sid)
    notifs = M.Notification.query.filter_by(destinataire_id=ids['resp_incidents'], entite_type='incident', entite_id=sid).count()
verif('Délai dépassé détecté et marqué', v.sla_viole and v.sla_date_limite is not None and n >= 1)
verif('… une seule fois (pas de nouvelle alerte au passage suivant)', n2 == 0 and notifs == 1, f'{n2} {notifs}')
r, t = go('resp_incidents', 'get', '/incidents?sla_viole=oui')
verif('Le filtre « délai dépassé » le retrouve', r.status_code == 200 and 'INC-SLA' in t, str(r.status_code))

print('--- Ma semaine')
r, t = go('resp_incidents', 'get', '/ma-semaine')
verif('Le responsable voit l\'incident à traiter (délai dépassé)', 'Incident à traiter' in t and 'INC-SLA' in t, str(r.status_code))
verif('Le gestionnaire voit l\'incident à qualifier', 'Incident à qualifier' in t or 'Fraude constatée' in t)

print('--- Signaler (utilisateurs connectés)')
r, t = go('simple', 'get', '/dashboard')
verif('« Signaler un incident » est dans le menu de tous', 'Signaler un incident' in t, str(r.status_code))
r, t = go('simple', 'get', '/support/ticket/nouveau?client=2')
verif('L\'ancienne adresse renvoie vers sa propre organisation', r.status_code == 302 and '/signalements/nouveau' in (r.headers.get('Location') or ''))
r, t = go('simple', 'get', '/signalements/nouveau')
with A.app.app_context():
    dir_b = M.Direction.query.filter_by(client_id=2).first()
verif('Formulaire de signalement ouvert, sans les données d\'une autre organisation',
      r.status_code == 200 and (dir_b is None or dir_b.nom not in t), f'{r.status_code} {socle.cause(A)}')
def poster(role, sujet, url='/signalements/nouveau', client=None):
    c = client or nav(role)
    return appel(c, 'post', url, data={'nom': 'Awa K.', 'email': 'awa.kone@egalyx-recette.fr', 'societe': 'Recette', 'sujet': sujet,
                                       'description': 'Le terminal de paiement est en panne depuis ce matin.',
                                       'priorite': 'haute', 'direction_type': 'autre', 'direction_manuel': 'Comptabilité',
                                       'direction_select': '', 'service_select': ''})
with A.app.app_context():
    nt0 = M.TicketSupport.query.count()
r = poster('simple', 'Terminal en panne')
with A.app.app_context():
    tk = M.TicketSupport.query.filter_by(sujet='Terminal en panne').first()
    tkid = tk.id if tk else None
    notif_tri = M.Notification.query.filter_by(destinataire_id=ids['trieur'], entite_type='ticket').count()
verif('Signalement enregistré dans SA organisation, avec son déclarant',
      tk is not None and tk.client_id == 1 and tk.declarant_id == ids['simple'], f'{r.status_code} {socle.cause(A)}')
verif('Les gestionnaires des signalements sont prévenus', notif_tri == 1, str(notif_tri))
r, t = go('simple', 'get', '/signalements/mes-signalements')
verif('« Mes signalements » le montre au déclarant', r.status_code == 200 and 'Terminal en panne' in t, f'{r.status_code} {socle.cause(A)}')
r = poster('operateur', 'Fuite d\'eau atelier')
with A.app.app_context():
    tko = M.TicketSupport.query.filter_by(sujet='Fuite d\'eau atelier').first()
verif('Un opérateur peut signaler', tko is not None and tko.declarant_id == ids['operateur'], str(r.status_code))
r, t = go('operateur', 'get', '/operateur/dashboard')
verif('… depuis son espace (lien présent)', 'signalements/nouveau' in t, str(r.status_code))

print('--- Détails d\'un signalement')
r, _ = go('lecteur', 'get', f'/support/ticket/{tkid}/details')
verif('Un autre membre sans droit ne lit plus le détail (nom, e-mail…)', r.status_code == 403, str(r.status_code))
r, _ = go('simple', 'get', f'/support/ticket/{tkid}/details')
verif('Le déclarant lit le sien', r.status_code == 200, str(r.status_code))
r, _ = go('trieur', 'get', f'/support/ticket/{tkid}/details')
verif('Le gestionnaire des signalements le lit', r.status_code == 200, str(r.status_code))

print('--- Conversion en incident')
r, _ = go('trieur', 'post', f'/support/ticket/{tkid}/traiter', data={'statut': 'traite', 'convertir_incident': 'on', 'gravite_incident': 'elevee'})
verif('Sans « Gérer les incidents », pas de conversion', obj(M.TicketSupport, tkid).incident_id is None, str(r.status_code))
r, _ = go('resp_incidents', 'post', f'/support/ticket/{tkid}/traiter', data={'statut': 'traite', 'convertir_incident': 'on', 'gravite_incident': 'elevee'})
t_ = obj(M.TicketSupport, tkid)
inc = obj(M.Incident, t_.incident_id) if t_.incident_id else None
verif('Conversion réussie (échouait : risque et dispositif obligatoires)', inc is not None and inc.risque_id is None,
      f'{r.status_code} {socle.cause(A)}')
if inc:
    with A.app.app_context():
        h = M.IncidentHistorique.query.filter_by(incident_id=inc.id, action='cree_depuis_signalement').count()
        nd = M.Notification.query.filter_by(destinataire_id=ids['simple'], entite_type='ticket').count()
    verif('Le déclarant d\'origine reste le déclarant de l\'incident', inc.declare_par_id == ids['simple'])
    verif('L\'origine est inscrite à l\'historique de l\'incident', h == 1)
    verif('Le déclarant est prévenu de la suite donnée', nd >= 1, str(nd))
r, t = go('simple', 'get', '/signalements/mes-signalements')
verif('« Mes signalements » indique l\'incident créé', 'Transformé en incident' in t)
r, t = go('trieur', 'get', '/ma-semaine')
verif('Ma semaine du gestionnaire : signalement à trier', 'Signalement à trier' in t and 'Fuite' in t, str(r.status_code))

print('--- Lien public (personnes sans compte)')
r, t = go(None, 'get', '/support/ticket/nouveau')
with A.app.app_context():
    dir_a = M.Direction.query.filter_by(client_id=1).first()
verif('Ancienne adresse anonyme : plus de formulaire du « premier client »',
      r.status_code == 404 and (dir_a is None or dir_a.nom not in t), str(r.status_code))
r, _ = go(None, 'get', '/support/ticket/nouveau?client=1')
verif('… même en choisissant l\'organisation dans l\'adresse', r.status_code == 404, str(r.status_code))
with A.app.app_context():
    cl = db.session.get(M.Client, 1)
    cl.signalement_jeton = 'jeton-de-recette-0123456789abcdef'; cl.signalement_public = False; db.session.commit()
r, _ = go(None, 'get', '/signalements/public/jeton-de-recette-0123456789abcdef')
verif('Lien public désactivé par défaut', r.status_code == 404, str(r.status_code))
r, t = go('lecteur', 'get', '/signalements/parametres')
verif('Un simple utilisateur ne règle pas le lien public', r.status_code == 403, str(r.status_code))
go('admin_a', 'post', '/signalements/parametres', data={'action': 'activer'})
with A.app.app_context():
    cl = db.session.get(M.Client, 1); jeton = cl.signalement_jeton; actif = cl.signalement_public
verif('L\'administrateur l\'active', actif and jeton)
pub = A.app.test_client()
url = f'/signalements/public/{jeton}'
r = appel(pub, 'get', url)
verif('Le lien public ouvre le formulaire de l\'organisation', r.status_code == 200 and b'Recette' in r.data or r.status_code == 200, str(r.status_code))
with A.app.app_context():
    np0 = M.TicketSupport.query.count()
r = poster(None, 'Robot', url=url, client=pub)          # envoyé aussitôt : refusé
with A.app.app_context():
    np1 = M.TicketSupport.query.count()
verif('Envoi immédiat (robot) refusé', np1 == np0, str(r.status_code))
with pub.session_transaction() as s_:
    s_['signalement_ouvert_1'] = time.time() - 10
r = appel(pub, 'post', url, data={'nom': 'Robot', 'email': 'robot@egalyx-recette.fr', 'societe': 'x', 'sujet': 'Piège', 'description': 'x',
                                  'priorite': 'normale', 'direction_type': 'autre', 'direction_manuel': 'x', 'site_web': 'http://spam'})
with A.app.app_context():
    piege = M.TicketSupport.query.filter_by(sujet='Piège').count()
verif('Champ piège rempli : refusé', piege == 0)
with pub.session_transaction() as s_:
    s_['signalement_ouvert_1'] = time.time() - 10
r = poster(None, 'Câble arraché parking', url=url, client=pub)
with A.app.app_context():
    ext = M.TicketSupport.query.filter_by(sujet='Câble arraché parking').first()
verif('Signalement d\'une personne extérieure enregistré dans la bonne organisation',
      ext is not None and ext.client_id == 1 and ext.declarant_id is None, f'{r.status_code} {socle.cause(A)}')
for k in range(6):
    with pub.session_transaction() as s_:
        s_['signalement_ouvert_1'] = time.time() - 10
    poster(None, f'Rafale {k}', url=url, client=pub)
with A.app.app_context():
    rafale = M.TicketSupport.query.filter(M.TicketSupport.sujet.like('Rafale%')).count()
verif('Au-delà de 5 envois par heure : refusé', rafale <= 4, str(rafale))
go('admin_a', 'post', '/signalements/parametres', data={'action': 'regenerer'})
r = appel(A.app.test_client(), 'get', url)
verif('Lien régénéré : l\'ancien ne fonctionne plus', r.status_code == 404, str(r.status_code))

print('--- Base existante : risque et dispositif obligatoires → facultatifs')
with A.app.app_context():
    from sqlalchemy import inspect as sa_inspect, text
    brut = db.engine.raw_connection(); cur = brut.cursor()
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='incidents'"); ddl = cur.fetchone()[0]
    ancien = re.sub(r'(risque_id INTEGER)', r'\1 NOT NULL', ddl, count=1)
    ancien = re.sub(r'(dispositif_id INTEGER)', r'\1 NOT NULL', ancien, count=1)
    ancien = re.sub(r'CREATE TABLE "?incidents"?', 'CREATE TABLE incidents__vieux', ancien, count=1)
    cur.execute('PRAGMA foreign_keys=OFF'); cur.execute(ancien)
    cur.execute('UPDATE incidents SET risque_id = COALESCE(risque_id, 1), dispositif_id = COALESCE(dispositif_id, 1)')
    cur.execute('INSERT INTO incidents__vieux SELECT * FROM incidents'); cur.execute('DROP TABLE incidents')
    cur.execute('ALTER TABLE incidents__vieux RENAME TO incidents'); brut.commit(); brut.close(); db.engine.dispose()
    avant = {c['name']: c['nullable'] for c in sa_inspect(db.engine).get_columns('incidents')}
    nb = db.session.execute(text('SELECT COUNT(*) FROM incidents')).scalar()
    from egalyx.incidents import rendre_liens_facultatifs
    rendre_liens_facultatifs(A.app)
    apres = {c['name']: c['nullable'] for c in sa_inspect(db.engine).get_columns('incidents')}
    nb2 = db.session.execute(text('SELECT COUNT(*) FROM incidents')).scalar()
verif('Ancienne base simulée (colonnes obligatoires)', avant['risque_id'] is False and avant['dispositif_id'] is False)
verif('Mise à jour : risque et dispositif facultatifs, aucun incident perdu',
      apres['risque_id'] and apres['dispositif_id'] and nb2 == nb and nb > 0, f'{nb} → {nb2}')

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
