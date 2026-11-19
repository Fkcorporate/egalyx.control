"""Recette : heure et devise par organisation ; lettre de mission (en-têtes par organisation, PDF, envoi).

Heure et devise
  - réglées par le super admin pour une organisation, et par l'administrateur pour la sienne ;
  - heures affichées dans le fuseau de l'organisation (dates seules jamais décalées ; heures saisies non converties) ;
  - « aujourd'hui » de l'organisation ; montants dans sa devise.
Lettre de mission
  - modèles d'en-tête gérés par le super admin seulement ; aperçu ;
  - lettre enregistrée côté serveur ; destinataires proposés depuis l'audit ;
  - e-mail mis en page + PDF joint, réponse au chef de mission ; historique ; adresses contrôlées ; droits.
"""
import datetime as dt
import os
import re
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, appel, creer
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
import models as M
from models import db

sup = socle.navigateur(A, ids['superadmin'])
adm = socle.navigateur(A, ids['admin_a'])
ges = socle.navigateur(A, ids['gestionnaire'])
lec = socle.navigateur(A, ids['lecteur'])
with A.app.app_context():
    CID = db.session.get(M.User, ids['admin_a']).client_id
    CIDB = db.session.get(M.User, ids['admin_b']).client_id

print('--- Heure et devise : réglages')
r = sup.post(f'/super-admin/client/{CID}/reglages', data={'fuseau_horaire': 'Africa/Abidjan', 'devise': 'XOF'})
with A.app.app_context():
    c = db.session.get(M.Client, CID)
    verif('super admin : fuseau Abidjan et devise FCFA enregistrés', c.fuseau_horaire == 'Africa/Abidjan' and c.devise == 'XOF', f'{r.status_code} {c.fuseau_horaire} {c.devise}')
r = sup.post(f'/super-admin/client/{CID}/reglages', data={'fuseau_horaire': 'Lune/Base', 'devise': 'XOF'})
with A.app.app_context():
    verif('fuseau inconnu refusé', db.session.get(M.Client, CID).fuseau_horaire == 'Africa/Abidjan')
h = sup.get(f'/super-admin/client/{CID}/reglages').data.decode()
verif('page de réglages : heure locale et exemple de montant', 'Heure locale' in h and '1 500 000' in h and 'FCFA' in h)
verif('vue d\'ensemble des organisations', sup.get('/super-admin/organisations/reglages').status_code == 200)
for nom, c_ in (('administrateur', adm), ('lecteur', lec)):
    r = c_.get(f'/super-admin/client/{CID}/reglages')
    verif(f'{nom} : pas d\'accès aux réglages super admin', r.status_code in (302, 403, 404), str(r.status_code))
r = adm.post('/organisation/heure-devise', data={'fuseau_horaire': 'Africa/Abidjan', 'devise': 'XOF'})
verif('administrateur de l\'organisation : peut régler la sienne', r.status_code == 302, str(r.status_code))
r = lec.post('/organisation/heure-devise', data={'fuseau_horaire': 'UTC', 'devise': 'EUR'})
with A.app.app_context():
    verif('… un simple utilisateur non', r.status_code in (302, 403) and db.session.get(M.Client, CID).devise == 'XOF', str(r.status_code))

print('--- Heure et devise : affichage')
from egalyx import localisation as L
from flask_login import login_user


def rendu(uid, gabarit, **ctx):
    with A.app.test_request_context('/'):
        u = db.session.get(M.User, uid)
        login_user(u)
        return A.app.jinja_env.from_string(gabarit).render(**ctx)


midi = dt.datetime(2026, 1, 15, 12, 0)                  # 12:00 UTC
with A.app.app_context():
    db.session.get(M.Client, CIDB).fuseau_horaire = 'America/Toronto'; db.session.get(M.Client, CIDB).devise = 'EUR'
    db.session.commit()
verif('heure affichée dans le fuseau de l\'organisation (Abidjan : 12:00)', rendu(ids['admin_a'], "{{ d.strftime('%d/%m %H:%M') }}", d=midi) == '15/01 12:00')
verif('… autre organisation (Montréal : 07:00)', rendu(ids['admin_b'], "{{ d.strftime('%d/%m %H:%M') }}", d=midi) == '15/01 07:00')
minuit = dt.datetime(2026, 1, 15, 0, 0)
verif('date seule jamais décalée (Montréal, minuit UTC -> 15/01)', rendu(ids['admin_b'], "{{ d.strftime('%d/%m/%Y') }}", d=minuit) == '15/01/2026')
verif('d.hour converti', rendu(ids['admin_b'], '{{ d.hour }}', d=midi) == '7')
saisie = L.DateLocale(2026, 1, 15, 9, 30)
verif('heure saisie par l\'utilisateur non convertie', rendu(ids['admin_b'], "{{ d.strftime('%H:%M') }}", d=saisie) == '09:30')
verif('filtre format_datetime converti', '07' in rendu(ids['admin_b'], '{{ d|format_datetime }}', d=midi) if 'format_datetime' in A.app.jinja_env.filters else True)
with A.app.app_context():
    inc_cols = {c.name for c in M.Incident.__table__.columns}
    i = creer(M.Incident, client_id=CIDB, titre='Panne', date_occurrence=dt.datetime(2026, 1, 15, 9, 30)) if 'titre' in inc_cols else None
    db.session.commit(); IID = i.id if i else None
if IID:
    with A.app.app_context():
        db.session.expire_all()
        v = db.session.get(M.Incident, IID).date_occurrence
        verif('date d\'occurrence d\'un incident repérée comme heure saisie', isinstance(v, L.DateLocale), type(v).__name__)
verif('montant en FCFA (sans décimales)', rendu(ids['admin_a'], '{{ 1500000|montant }}') == '1 500 000 FCFA', repr(rendu(ids['admin_a'], '{{ 1500000|montant }}')))
verif('montant en euros', rendu(ids['admin_b'], '{{ 1500.5|montant }}') == '1 500,50 €', repr(rendu(ids['admin_b'], '{{ 1500.5|montant }}')))
verif('symbole de la devise', rendu(ids['admin_a'], '{{ devise() }}') == 'FCFA')
with A.app.app_context():
    from zoneinfo import ZoneInfo
    db.session.get(M.Client, CIDB).fuseau_horaire = 'Pacific/Kiritimati'; db.session.commit()
    attendu = dt.datetime.now(ZoneInfo('Pacific/Kiritimati')).date()
    verif('« aujourd\'hui » dans le fuseau de l\'organisation (UTC+14)', L.aujourdhui(CIDB) == attendu, f'{L.aujourdhui(CIDB)} {attendu}')
    db.session.get(M.Client, CIDB).fuseau_horaire = 'America/Toronto'; db.session.commit()
r = adm.get('/dashboard')
verif('tableau de bord : s\'affiche', r.status_code == 200, str(r.status_code))

print('--- Lettre de mission : modèles d\'en-tête (super admin)')
r = sup.post(f'/super-admin/client/{CID}/lettres-mission/nouveau', data={
    'nom': 'Direction de l\'audit', 'logo_position': 'gauche', 'couleur': '#0D9488', 'titre_entete': 'Banque Alpha — Audit Interne',
    'lignes_entete': 'Plateau, Abidjan\nTél. +225 27 00 00 00', 'mention_haut': 'Confidentiel', 'pied_page': 'SA au capital de 10 milliards',
    'signature': 'Le Directeur de l\'Audit Interne', 'objet_email': 'Mission {reference} : {objet}',
    'message_email': 'Madame, Monsieur,\nVeuillez trouver la lettre de la mission {objet} ({date_debut} – {date_fin}).\n{emetteur}',
    'est_defaut': '1', 'actif': ['0', '1']})      # comme le formulaire : champ caché « 0 » puis case cochée « 1 »
with A.app.app_context():
    mod = M.ModeleLettreMission.query.filter_by(client_id=CID).first()
    MID = mod.id if mod else None
verif('modèle créé, actif et mis par défaut', mod is not None and mod.est_defaut and mod.actif and mod.couleur == '#0D9488', str(r.status_code))
r = sup.post(f'/super-admin/client/{CID}/lettres-mission/{MID}/apercu', data={'nom': 'X', 'titre_entete': 'Titre en cours de saisie', 'couleur': '#123456', 'logo_position': 'gauche'})
verif('aperçu en direct (formulaire non enregistré)', r.status_code == 200 and 'Titre en cours de saisie' in r.data.decode() and '#123456' in r.data.decode(), str(r.status_code))
with A.app.app_context():
    verif('… sans rien enregistrer', db.session.get(M.ModeleLettreMission, MID).titre_entete == 'Banque Alpha — Audit Interne')
r = sup.post(f'/super-admin/client/{CID}/lettres-mission/{MID}/dupliquer')
with A.app.app_context():
    verif('dupliquer', M.ModeleLettreMission.query.filter_by(client_id=CID).count() == 2)
    copie = M.ModeleLettreMission.query.filter_by(client_id=CID, est_defaut=False).first(); COPIE = copie.id
sup.post(f'/super-admin/client/{CID}/lettres-mission/{COPIE}/supprimer')
with A.app.app_context():
    verif('supprimer', M.ModeleLettreMission.query.filter_by(client_id=CID).count() == 1)
r = adm.get(f'/super-admin/client/{CID}/lettres-mission/{MID}')
verif('administrateur de l\'organisation : ne gère pas les en-têtes', r.status_code in (302, 403, 404), str(r.status_code))
r = sup.get(f'/super-admin/client/{CIDB}/lettres-mission/{MID}')
verif('modèle d\'une autre organisation : introuvable par cette adresse', r.status_code == 404, str(r.status_code))

r = sup.post(f'/super-admin/client/{CID}/lettres-mission/{MID}', data={'nom': 'Direction de l\'audit', 'couleur': '#0D9488', 'actif': '0', 'logo_position': 'gauche'})
with A.app.app_context():
    verif('case « Actif » décochée : modèle inactif', db.session.get(M.ModeleLettreMission, MID).actif is False)
sup.post(f'/super-admin/client/{CID}/lettres-mission/{MID}', data={'nom': 'Direction de l\'audit', 'couleur': '#0D9488', 'actif': ['0', '1'],
         'logo_position': 'gauche', 'titre_entete': 'Banque Alpha — Audit Interne', 'mention_haut': 'Confidentiel',
         'objet_email': 'Mission {reference} : {objet}',
         'message_email': 'Madame, Monsieur,\nVeuillez trouver la lettre de la mission {objet} ({date_debut} – {date_fin}).\n{emetteur}'})

print('--- Lettre de mission : rédaction et destinataires')
with A.app.app_context():
    u_aud = creer(M.User, username='audite_achats', email='audite@banque-alpha.test', client_id=CID, role='utilisateur', is_active=True, password_hash='x')
    u_obs = creer(M.User, username='observ', email='observ@banque-alpha.test', client_id=CID, role='utilisateur', is_active=True, password_hash='x')
    db.session.flush()
    chef = db.session.get(M.User, ids['gestionnaire'])
    au = creer(M.Audit, titre='Audit des achats', reference='AUD-ACH-26', client_id=CID, created_by=ids['admin_a'],
               responsable_id=chef.id, participants_ids=str(u_aud.id), observateurs_ids=str(u_obs.id),
               equipe_audit_ids=str(ids['admin_a']), membres_externes=[{'nom': 'Kouassi', 'prenom': 'Awa', 'email': 'awa.kouassi@externe.test', 'fonction': 'Commissaire aux comptes'}],
               date_debut_prevue=dt.date(2026, 12, 1), date_fin_prevue=dt.date(2026, 12, 19), statut='planifie')
    db.session.flush()
    fe = creer(M.FeuilleTravail, reference='FT-ACH', titre='Feuille achats', audit_id=au.id, client_id=CID)
    db.session.commit()
    FID, CHEF_MAIL = fe.id, chef.email
lettre = {'reference': 'AUD-ACH-26', 'objet': 'Audit des achats', 'destinataire': 'Mme la Directrice des Achats',
          'introduction': 'Dans le cadre du plan annuel…', 'objectifs': 'Évaluer la maîtrise des achats.', 'date_debut': '2026-12-01',
          'date_fin': '2026-12-19', 'emetteur': 'Le DAI', 'modele_id': MID, 'confidentialite': True, 'confidentialite_texte': 'Confidentiel.'}
r = adm.post(f'/api/feuille-travail/{FID}/lettre-mission', json=lettre)
with A.app.app_context():
    db.session.expire_all()
    verif('lettre enregistrée sur le serveur (relue sur un autre poste)', (db.session.get(M.FeuilleTravail, FID).contenu or {}).get('lettre_mission', {}).get('objectifs') == 'Évaluer la maîtrise des achats.', str(r.status_code))
d = adm.get(f'/api/feuille-travail/{FID}/lettre-mission/donnees').get_json()
places = {x['email']: (x['place'], x['coche']) for x in d['destinataires']}
verif('audité proposé en destinataire', places.get('audite@banque-alpha.test') == ('a', True), str(places))
verif('membre externe proposé en destinataire', places.get('awa.kouassi@externe.test') == ('a', True))
verif('chef de mission en copie', places.get(CHEF_MAIL) == ('cc', True))
verif('observateur proposé, non coché', places.get('observ@banque-alpha.test') == ('cc', False))
verif('modèle d\'en-tête proposé', [m['id'] for m in d['modeles']] == [MID])
r = adm.get(f'/api/feuille-travail/{FID}/lettre-mission/apercu')
verif('aperçu avec l\'en-tête du modèle', r.status_code == 200 and 'Banque Alpha — Audit Interne' in r.data.decode() and 'CONFIDENTIEL' in r.data.decode())
r = adm.get(f'/api/feuille-travail/{FID}/lettre-mission/pdf')
verif('PDF téléchargeable', r.status_code == 200 and r.data[:4] == b'%PDF' and r.mimetype == 'application/pdf', f'{r.status_code} {r.mimetype}')
autre = socle.navigateur(A, ids['admin_b'])
verif('autre organisation : feuille introuvable', autre.get(f'/api/feuille-travail/{FID}/lettre-mission/donnees').status_code == 404)

print('--- Lettre de mission : envoi')
from services.email_service import email_service
envois = []
original = email_service.send_email
email_service.send_email = lambda *a, **k: envois.append((a, k)) or True
mode = (email_service.is_local, getattr(email_service, 'simulation_mode', False))
email_service.is_local, email_service.simulation_mode = False, False
try:
    r = adm.post(f'/api/feuille-travail/{FID}/lettre-mission/envoyer', json={'a': ['audite@banque-alpha.test', 'awa.kouassi@externe.test'], 'cc': [CHEF_MAIL]})
    j = r.get_json()
    verif('envoi accepté', r.status_code == 200 and j['success'] and not j['simulation'], str(j))
    (a_, k_) = envois[-1]
    verif('destinataires et copie corrects', a_[0] == ['audite@banque-alpha.test', 'awa.kouassi@externe.test'] and k_['cc'] == [CHEF_MAIL])
    verif('réponses adressées au chef de mission', k_['reply_to'] == CHEF_MAIL)
    verif('objet du modèle, variables remplies', a_[1] == 'Mission AUD-ACH-26 : Audit des achats', a_[1])
    verif('message du modèle, dates en clair', '01/12/2026 – 19/12/2026' in a_[2], a_[2][:120])
    verif('PDF joint', k_['attachments'][0][0].endswith('.pdf') and k_['attachments'][0][1][:4] == b'%PDF')
    html = k_['html_body']
    verif('e-mail mis en page aux couleurs du modèle, lettre dans le corps', '#0D9488' in html and '&lt;table' not in html and '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">' in html and 'Banque Alpha — Audit Interne' in html and 'Évaluer la maîtrise des achats.' in html)
    with A.app.app_context():
        db.session.expire_all()
        h = (db.session.get(M.FeuilleTravail, FID).contenu or {}).get('lettre_mission_envoyee') or []
    verif('historique : destinataires, copie, auteur', h and h[-1]['a'] == ['audite@banque-alpha.test', 'awa.kouassi@externe.test'] and h[-1]['par'] == ids['admin_a'])
    n = len(envois)
    r = adm.post(f'/api/feuille-travail/{FID}/lettre-mission/envoyer', json={'a': ['pas-une-adresse'], 'cc': []})
    verif('adresse invalide refusée, rien envoyé', r.status_code == 400 and len(envois) == n and 'pas-une-adresse' in r.get_json()['error'])
    r = adm.post(f'/api/feuille-travail/{FID}/lettre-mission/envoyer', json={'a': [], 'cc': [CHEF_MAIL]})
    verif('sans destinataire principal : refusé', r.status_code == 400 and len(envois) == n)
    r = socle.navigateur(A, u_id := None).post if False else None
    with A.app.app_context():
        intrus = creer(M.User, username='intrus', email='intrus@banque-alpha.test', client_id=CID, role='utilisateur', is_active=True, password_hash='x')
        db.session.commit(); INTRUS = intrus.id
    r = socle.navigateur(A, INTRUS).post(f'/api/feuille-travail/{FID}/lettre-mission/envoyer', json={'a': ['x@y.test']})
    verif('personne hors de l\'équipe d\'audit : envoi refusé', r.status_code in (302, 403) and len(envois) == n, str(r.status_code))
    r = adm.post(f'/api/feuille-travail/{FID}/envoyer-lettre', json={'email': 'audite@banque-alpha.test', 'message': 'Bonjour'})
    verif('ancienne adresse d\'envoi : passe par le nouvel envoi (PDF, chef de mission)', r.status_code == 200 and len(envois) == n + 1 and envois[-1][1]['reply_to'] == CHEF_MAIL, str(r.status_code))
    email_service.send_email = lambda *a, **k: False
    r = adm.post(f'/api/feuille-travail/{FID}/lettre-mission/envoyer', json={'a': ['audite@banque-alpha.test']})
    verif('refus du serveur d\'e-mail signalé (plus de faux « envoyé »)', r.status_code == 502 and not r.get_json()['success'])
    email_service.send_email = lambda *a, **k: True
    email_service.is_local = True
    r = adm.post(f'/api/feuille-travail/{FID}/lettre-mission/envoyer', json={'a': ['audite@banque-alpha.test']})
    verif('serveur d\'e-mail non configuré : envoi signalé comme SIMULÉ', r.get_json()['simulation'] and 'SIMULÉ' in r.get_json()['message'])
finally:
    email_service.send_email = original
    email_service.is_local, email_service.simulation_mode = mode
h = adm.get(f'/audit/feuille-travail/{FID}/editer') if False else None

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
