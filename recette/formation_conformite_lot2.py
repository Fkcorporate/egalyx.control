"""Recette : formation à la conformité, lot 2.

Bibliothèque Egalyx (amorçage, gestion par le super admin seulement, versions, retrait, suppression protégée),
import d'un module et d'un parcours, version adaptée au profil réglementaire, nouvelle version et mise à jour,
lancement d'un parcours, attestation PDF (droits), relances automatiques (étapes, une seule fois, désactivables),
KRI alimenté une fois par jour, rapport au comité."""
import json
import os
import re
from datetime import date, timedelta

os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
import models as M
from models import db
from egalyx import formation_bibliotheque as fb
from egalyx import formation_conformite as fc
from egalyx import formation_conformite_lot2 as lot2
from egalyx.modules_client import MODULES

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


def jeton(c, url='/dashboard'):
    t = appel(c, 'get', url).data.decode(errors='ignore')
    m = re.search(r'name="csrf_token" value="([^"]+)"', t) or re.search(r'name="csrf-token" content="([^"]+)"', t)
    return m.group(1) if m else ''


sa, admin, lect, oper, admin_b = (socle.navigateur(A, ids[r]) for r in ('superadmin', 'admin_a', 'lecteur', 'operateur', 'admin_b'))
with A.app.app_context():
    c1 = db.session.get(M.Client, 1); c1.modules_actifs = {k: True for k in MODULES}; db.session.commit()

print('--- 1. Bibliothèque : amorçage et gestion par le super admin')
with A.app.app_context():
    codes = {b.code for b in M.ModuleBibliothequeFormation.query}
    verif('13 modules amorcés (7 contrôle interne + 6 conformité), tous publiés', codes == fb.CODES and len(codes) == 13
          and M.ModuleBibliothequeFormation.query.filter_by(statut='publie').count() == 13, len(codes))
    verif('parcours contrôle interne : 7 modules dans l’ordre', [b.code for b in M.ModuleBibliothequeFormation.query.filter_by(
        parcours='controle_interne').order_by(M.ModuleBibliothequeFormation.ordre)] == ['ci_bases', 'ci_cartographie_risques', 'ci_processus',
                                                                                        'ci_carto_processus', 'ci_campagnes_n1', 'ci_controle_n2', 'ci_plans_action'])
    lot2.amorcer(A.app)
    verif('amorçage relancé : rien en double', M.ModuleBibliothequeFormation.query.count() == 13)
r = appel(sa, 'get', '/formation-conformite/bibliotheque-egalyx')
verif('super admin : page de la bibliothèque', r.status_code == 200 and 'La cartographie des risques'.encode() in r.data, r.status_code)
verif('menu super admin : « Bibliothèque de formation »', 'Bibliothèque de formation'.encode() in appel(sa, 'get', '/dashboard').data)
for nom, c in (('administrateur d’organisation', admin), ('simple utilisateur', lect)):
    verif(f'{nom} : bibliothèque Egalyx non modifiable', appel(c, 'get', '/formation-conformite/bibliotheque-egalyx').status_code == 403
          and appel(c, 'get', '/formation-conformite/bibliotheque-egalyx/module/nouveau').status_code == 403)
r = appel(sa, 'post', '/formation-conformite/bibliotheque-egalyx/module/nouveau', data={
    'csrf_token': jeton(sa, '/formation-conformite/bibliotheque-egalyx/module/nouveau'), 'code': 'Qualité ISO 9001', 'titre': 'La démarche qualité',
    'categorie': 'controle_interne', 'parcours': 'controle_interne', 'ordre': '8', 'profil': 'tous', 'contenu': 'Texte',
    'questions_json': json.dumps([{'texte': 'Q ?', 'choix': ['a', 'b'], 'bonnes': [0]}]), 'action': 'enregistrer'})
with A.app.app_context():
    nb = M.ModuleBibliothequeFormation.query.filter_by(code='qualit_iso_9001').first() or M.ModuleBibliothequeFormation.query.filter(
        M.ModuleBibliothequeFormation.code.like('qualit%')).first()
    verif('super admin : nouveau module en brouillon (code nettoyé)', nb is not None and nb.statut == 'brouillon' and re.fullmatch(r'[a-z0-9_]+', nb.code), nb and nb.code)
    NB = nb.id
r = appel(admin, 'get', '/formation-conformite/')
verif('client : module en brouillon invisible', 'La démarche qualité'.encode() not in r.data)

print('--- 2. Côté client : bibliothèque, profil, import')
r = appel(admin, 'get', '/formation-conformite/')
t = r.data.decode(errors='ignore')
with A.app.app_context():
    vue = lot2.vue_client(1)
    profil = vue['profil']
    conf = next(p for p in vue['parcours'] if p['code'] == 'conformite')
    principal = {l['b'].code for l in conf['lignes']}
    autres = {l['b'].code for l in conf['autres']}
attendu, autre = ('lcbft_uemoa', 'lcbft_france') if profil == 'uemoa' else ('lcbft_france', 'lcbft_uemoa')
verif(f'version LCB-FT adaptée au profil ({profil}) proposée en premier, l’autre en « Autres versions »', attendu in principal and autre in autres)
verif('page client : bibliothèque, parcours, boutons', r.status_code == 200 and 'Bibliothèque Egalyx' in t and 'Parcours contrôle interne' in t
      and 'Importer le parcours (7)' in t and 'Lancer le parcours' in t)
r = appel(admin, 'post', '/formation-conformite/bibliotheque/ci_bases/importer', data={'csrf_token': jeton(admin, '/formation-conformite/')})
with A.app.app_context():
    mod = M.ModuleFormationConformite.query.filter_by(client_id=1, origine='ci_bases').first()
    verif('import d’un module : copie publiée, version de la bibliothèque notée', mod is not None and mod.statut == 'publie'
          and mod.origine_version == 1 and len(mod.questions) == 5)
    MID = mod.id
r = appel(admin, 'post', '/formation-conformite/bibliotheque/ci_bases/importer', data={'csrf_token': jeton(admin, '/formation-conformite/')})
r = appel(admin, 'post', '/formation-conformite/bibliotheque/parcours/controle_interne/importer', data={'csrf_token': jeton(admin, '/formation-conformite/')})
with A.app.app_context():
    n = M.ModuleFormationConformite.query.filter(M.ModuleFormationConformite.client_id == 1,
                                                 M.ModuleFormationConformite.origine.like('ci_%')).count()
    verif('import du parcours : 7 modules, sans doublon', n == 7, n)
r = appel(admin, 'post', '/formation-conformite/bibliotheque/inexistant/importer', data={'csrf_token': jeton(admin, '/formation-conformite/')})
verif('module inconnu : 404', r.status_code == 404)
r = appel(admin_b, 'post', '/formation-conformite/bibliotheque/ci_bases/importer', data={'csrf_token': jeton(admin_b)})
verif('organisation sans le module : import refusé', r.status_code in (403, 404), r.status_code)
r = appel(lect, 'post', '/formation-conformite/bibliotheque/ci_bases/importer', data={'csrf_token': jeton(lect)})
verif('simple utilisateur : import refusé', r.status_code == 403)
r = appel(sa, 'post', f'/formation-conformite/bibliotheque-egalyx/module/{NB}/etat', data={'csrf_token': jeton(sa, '/formation-conformite/bibliotheque-egalyx'), 'action': 'publier'})
verif('module publié par le super admin : visible par le client', 'La démarche qualité'.encode() in appel(admin, 'get', '/formation-conformite/').data)

print('--- 3. Nouvelle version publiée par le super admin')
with A.app.app_context():
    b = M.ModuleBibliothequeFormation.query.filter_by(code='ci_bases').first()
    BID, contenu = b.id, b.contenu
    qs = json.dumps(b.questions, ensure_ascii=False)
r = appel(sa, 'post', f'/formation-conformite/bibliotheque-egalyx/module/{BID}', data={
    'csrf_token': jeton(sa, f'/formation-conformite/bibliotheque-egalyx/module/{BID}'), 'titre': 'Les bases du contrôle interne',
    'categorie': 'controle_interne', 'parcours': 'controle_interne', 'ordre': '1', 'profil': 'tous', 'duree_minutes': '12', 'score_min': '80',
    'contenu': contenu + '\n\n## Nouveau paragraphe\nAjout de la version 2.', 'questions_json': qs, 'action': 'enregistrer'})
with A.app.app_context():
    verif('modification d’un module publié : version 2', db.session.get(M.ModuleBibliothequeFormation, BID).version == 2)
t = appel(admin, 'get', '/formation-conformite/').data.decode(errors='ignore')
verif('client : « Nouvelle version disponible »', 'Nouvelle version disponible' in t)
t = appel(admin, 'get', f'/formation-conformite/module/{MID}').data.decode(errors='ignore')
verif('fiche du module : bandeau et bouton de mise à jour', 'Reprendre la nouvelle version' in t)
r = appel(admin, 'post', f'/formation-conformite/module/{MID}/mettre-a-jour', data={'csrf_token': jeton(admin, f'/formation-conformite/module/{MID}')})
with A.app.app_context():
    mod = db.session.get(M.ModuleFormationConformite, MID)
    verif('mise à jour : contenu repris, version 2 notée, version du module client augmentée', 'Ajout de la version 2' in mod.contenu
          and mod.origine_version == 2 and mod.version == 2)
r = appel(sa, 'post', f'/formation-conformite/bibliotheque-egalyx/module/{BID}/etat', data={'csrf_token': jeton(sa, '/formation-conformite/bibliotheque-egalyx'), 'action': 'supprimer'})
with A.app.app_context():
    verif('suppression d’un module importé par un client : refusée', db.session.get(M.ModuleBibliothequeFormation, BID) is not None)

print('--- 4. Lancer un parcours')
r = appel(admin, 'get', '/formation-conformite/campagne/nouvelle?parcours=controle_interne')
verif('formulaire : parcours proposé et présélectionné', 'value="parcours:controle_interne" selected'.encode() in r.data)
r = appel(admin, 'post', '/formation-conformite/campagne/nouvelle', data={
    'csrf_token': jeton(admin, '/formation-conformite/campagne/nouvelle'), 'module_id': 'parcours:controle_interne',
    'date_limite': (date.today() + timedelta(days=7)).isoformat(), 'cible_type': 'utilisateurs',
    'cible_utilisateurs': [str(ids['lecteur']), str(ids['operateur'])], 'relances_auto': '1'})
with A.app.app_context():
    camps = M.CampagneFormationConformite.query.filter(M.CampagneFormationConformite.client_id == 1,
                                                       M.CampagneFormationConformite.titre.like('Parcours contrôle interne%')).all()
    verif('parcours lancé : une campagne par module (8 avec le module qualité publié), 2 personnes chacune',
          len(camps) == 8 and all(M.AffectationFormationConformite.query.filter_by(campagne_id=c.id).count() == 2 for c in camps), len(camps))
    camp_bases = next(c for c in camps if c.module_id == MID)
    KID = camp_bases.id
    aid = M.AffectationFormationConformite.query.filter_by(campagne_id=KID, user_id=ids['lecteur']).first().id
    mod = db.session.get(M.ModuleFormationConformite, MID)
    bonnes = {f'q{i}': [str(b) for b in q['bonnes']] for i, q in enumerate(mod.questions)}

print('--- 5. Attestation PDF')
r = appel(lect, 'get', f'/formation-conformite/attestation/{aid}.pdf')
verif('pas d’attestation avant validation', r.status_code == 404)
r = appel(lect, 'post', f'/formation-conformite/suivre/{aid}', data={'csrf_token': jeton(lect, f'/formation-conformite/suivre/{aid}'), **bonnes})
verif('quiz réussi : lien vers l’attestation', 'Télécharger l’attestation'.encode() in r.data)
r = appel(lect, 'get', f'/formation-conformite/attestation/{aid}.pdf')
verif('attestation PDF téléchargée par la personne', r.status_code == 200 and r.data[:4] == b'%PDF' and r.mimetype == 'application/pdf', r.status_code)
verif('attestation : le gestionnaire peut la télécharger', appel(admin, 'get', f'/formation-conformite/attestation/{aid}.pdf').status_code == 200)
verif('attestation : un autre utilisateur ne peut pas', appel(oper, 'get', f'/formation-conformite/attestation/{aid}.pdf').status_code == 404)
verif('attestation : une autre organisation ne peut pas', appel(admin_b, 'get', f'/formation-conformite/attestation/{aid}.pdf').status_code == 404)
with A.app.app_context():
    a = db.session.get(M.AffectationFormationConformite, aid)
    u = db.session.get(M.User, a.user_id)
    cv1 = lot2.code_verification(a, db.session.get(M.ModuleFormationConformite, MID), u)
    verif('code de vérification stable (12 caractères)', len(cv1) == 12 and cv1 == lot2.code_verification(a, db.session.get(M.ModuleFormationConformite, MID), u))
verif('« Mes formations » : bouton Attestation', 'Attestation'.encode() in appel(lect, 'get', '/formation-conformite/mes-formations').data)

print('--- 6. Relances automatiques')
with A.app.app_context():
    limite = db.session.get(M.CampagneFormationConformite, KID).date_limite
    avant = M.Notification.query.filter_by(entite_type='formation_campagne', entite_id=KID).count()
    r1 = lot2.relancer_automatiquement(limite - timedelta(days=7))
    apres = M.Notification.query.filter_by(entite_type='formation_campagne', entite_id=KID).count()
    verif('J-7 : seule la personne qui n’a pas validé est relancée', apres - avant == 1, (apres - avant, r1))
    r2 = lot2.relancer_automatiquement(limite - timedelta(days=7))
    verif('J-7 relancé une deuxième fois le même jour : aucun doublon', M.Notification.query.filter_by(entite_type='formation_campagne', entite_id=KID).count() == apres)
    lot2.relancer_automatiquement(limite - timedelta(days=3))
    verif('jour sans étape : rien', M.Notification.query.filter_by(entite_type='formation_campagne', entite_id=KID).count() == apres)
    lot2.relancer_automatiquement(limite + timedelta(days=1))
    n_retard = M.Notification.query.filter_by(entite_type='formation_campagne', entite_id=KID).order_by(M.Notification.id.desc()).first()
    verif('J+1 : relance « en retard », urgence importante', n_retard.titre.startswith('Formation en retard') and n_retard.urgence == 'important')
    autre = db.session.get(M.CampagneFormationConformite, next(c.id for c in camps if c.id != KID))
    autre.relances_auto = False; db.session.commit()
    av = M.Notification.query.filter_by(entite_type='formation_campagne', entite_id=autre.id).count()
    lot2.relancer_automatiquement(limite + timedelta(days=7))
    verif('relances désactivées sur une campagne : aucune relance', M.Notification.query.filter_by(entite_type='formation_campagne', entite_id=autre.id).count() == av)
    verif('relances journalisées', M.JournalActiviteClient.query.filter_by(action='formation_relance_auto').count() >= 2)

print('--- 7. KRI alimenté par la campagne')
with A.app.app_context():
    kri = M.KRI(nom='Formations obligatoires non suivies (%)', client_id=1, unite_mesure='%', seuil_alerte=20, seuil_critique=40)
    db.session.add(kri); db.session.commit(); KRI_ID = kri.id
    kri_b = M.KRI(nom='KRI autre organisation', client_id=2); db.session.add(kri_b); db.session.commit(); KRI_B = kri_b.id
r = appel(admin, 'post', f'/formation-conformite/campagne/{KID}/action', data={'csrf_token': jeton(admin, f'/formation-conformite/campagne/{KID}'),
                                                                              'action': 'reglages', 'relances_auto': '1', 'kri_id': str(KRI_B)})
with A.app.app_context():
    verif('KRI d’une autre organisation : refusé', db.session.get(M.CampagneFormationConformite, KID).kri_id is None)
r = appel(admin, 'post', f'/formation-conformite/campagne/{KID}/action', data={'csrf_token': jeton(admin, f'/formation-conformite/campagne/{KID}'),
                                                                              'action': 'reglages', 'relances_auto': '1', 'kri_id': str(KRI_ID)})
with A.app.app_context():
    verif('KRI relié à la campagne', db.session.get(M.CampagneFormationConformite, KID).kri_id == KRI_ID)
    jour = date.today()
    lot2.relancer_automatiquement(jour)
    mesures = M.MesureKRI.query.filter_by(kri_id=KRI_ID).all()
    verif('mesure du jour : 50 % n’ont pas validé (1 sur 2)', len(mesures) == 1 and mesures[0].valeur == 50.0, [x.valeur for x in mesures])
    lot2.relancer_automatiquement(jour)
    verif('une seule mesure par jour', M.MesureKRI.query.filter_by(kri_id=KRI_ID).count() == 1)
    lot2.relancer_automatiquement(jour + timedelta(days=1))
    verif('le lendemain : nouvelle mesure', M.MesureKRI.query.filter_by(kri_id=KRI_ID).count() == 2)

print('--- 8. Rapport au comité')
with A.app.app_context():
    u = db.session.get(M.User, ids['admin_a']); p = dict(u.permissions or {}); p['can_view_rapport_comite'] = True; u.permissions = p; db.session.commit()
r = appel(admin, 'get', '/rapports/comite-audit')
t = r.data.decode(errors='ignore')
verif('rapport au comité : bloc « Formation à la conformité » (taux et retards)', r.status_code == 200 and 'Formation à la conformité' in t
      and 'campagnes, ' in t, r.status_code)
from egalyx import rapport_comite
phr = rapport_comite.rediger_synthese({'date': '27/11/2026', 'total_risques': 10, 'evalues': 10, 'couverture': 100, 'critiques': 0,
                                       'critiques_bruts': 0, 'hors_appetence': 0, 'formation_campagnes': 3, 'formation_taux': 64,
                                       'formation_retard': 5})
verif('synthèse : phrase sur la formation', any(x.startswith('Formation à la conformité : 3 campagnes en cours, taux de réalisation de 64 %, 5 personnes en retard')
                                                 for x in phr), phr[-1])
phr0 = rapport_comite.rediger_synthese({'date': '27/11/2026', 'total_risques': 10, 'evalues': 10, 'couverture': 100, 'critiques': 0,
                                        'critiques_bruts': 0, 'hors_appetence': 0})
verif('synthèse : rien sur la formation si le module n’est pas utilisé', not any('Formation' in x for x in phr0))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
