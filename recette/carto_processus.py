"""Recette : cartographie des processus (module sur activation du super admin)."""
import os
import re
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


def jeton(c, url='/carte-processus/'):
    r = appel(c, 'get', url)
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.data.decode(errors='ignore'))
    if m:
        return m.group(1)
    m = re.search(r'name="csrf-token" content="([^"]+)"', r.data.decode(errors='ignore'))
    return m.group(1) if m else ''


def poster(c, url, data=None, page='/carte-processus/', **kw):
    return appel(c, 'post', url, data={**(data or {}), 'csrf_token': jeton(c, page)}, **kw)


def pm(cid=1, **f):
    return M.ProcessusMetier.query.filter_by(client_id=cid, **f)


sa, admin, gest, lect, admin_b = (socle.navigateur(A, ids[r]) for r in ('superadmin', 'admin_a', 'gestionnaire', 'lecteur', 'admin_b'))
with A.app.app_context():
    lec = db.session.get(M.User, ids['lecteur']); lec.permissions = {**(lec.permissions or {}), 'can_view_carto_processus': True}
    ge = db.session.get(M.User, ids['gestionnaire']); ge.permissions = {**(ge.permissions or {}), 'can_manage_carto_processus': True}
    db.session.commit()

print('--- Module fermé tant que le super admin ne l’a pas activé')
with A.app.app_context():
    verif('client sans restriction : module fermé', db.session.get(M.Client, 1).modules_actifs is None
          and not db.session.get(M.User, ids['admin_a']).has_permission('can_view_carto_processus'))
r = appel(admin, 'get', '/carte-processus/')
verif('administrateur : page refusée avant activation', r.status_code == 403, r.status_code)
r = appel(gest, 'get', '/carte-processus/')
verif('utilisateur avec la permission : refusé quand même (module fermé)', r.status_code == 403, r.status_code)
r = appel(admin, 'get', '/dashboard')
verif('menu : pas d’entrée « Carte des processus »', b'carte-processus' not in r.data, r.status_code)
r = appel(sa, 'get', '/super-admin/client/1/modules')
verif('page Modules du super admin : case proposée, non cochée, « sur activation »', r.status_code == 200
      and re.search(rb'value="carto_processus"\s*>', r.data) and b'sur activation' in r.data)
# un autre choix de modules (sans la carte) la laisse fermée
r = poster(sa, '/super-admin/client/1/modules', {'action': 'enregistrer', 'modules': ['cartographie', 'audit', 'processus']}, page='/super-admin/client/1/modules')
verif('choix de modules sans la carte : toujours fermée', appel(admin, 'get', '/carte-processus/').status_code == 403)

print('--- Activation par le super admin')
r = poster(sa, '/super-admin/client/1/modules', {'action': 'enregistrer', 'modules': ['cartographie', 'audit', 'processus', 'carto_processus']},
           page='/super-admin/client/1/modules')
verif('super admin : module activé', r.status_code in (302, 303), r.status_code)
r = appel(admin, 'get', '/carte-processus/')
verif('administrateur : page ouverte, état vide avec modèles types', r.status_code == 200 and b'Banque / microfinance' in r.data, r.status_code)
verif('menu : entrée « Carte des processus »', b'/carte-processus/' in appel(admin, 'get', '/dashboard').data)
verif('client B : toujours fermé', appel(admin_b, 'get', '/carte-processus/').status_code == 403)
with A.app.app_context():
    verif('administrateur : droits voir + organiser donnés à l’activation', db.session.get(M.User, ids['admin_a']).has_permission('can_manage_carto_processus'))
    from egalyx.permissions_grille import grille
    sec = next(s for s in grille(db.session.get(M.User, ids['lecteur']), db.session.get(M.Client, 1)) if s['code'] == 'carto_processus')
    verif('grille des droits : module actif, case « voir » cochée pour le lecteur', sec['actif'] and dict((p, c) for p, _l, c in sec['perms'])['can_view_carto_processus'])

print('--- Modèle type, carte, vues')
r = poster(admin, '/carte-processus/modele', {'modele': 'banque'})
with A.app.app_context():
    n1 = pm(is_archived=False).count()
    verif('modèle « banque » : processus et sous-processus créés', n1 >= 20 and pm(code='REA-03').first().type_processus == 'metier'
          and pm(code='REA-03.2').first().parent_id == pm(code='REA-03').first().id, n1)
r = poster(admin, '/carte-processus/modele', {'modele': 'banque'})
with A.app.app_context():
    verif('modèle appliqué deux fois : aucun doublon', pm(is_archived=False).count() == n1)
    ids_p = {p.code: p.id for p in pm().all()}
    rq = socle.creer(M.Risque, reference='RQ-CP', intitule='Fraude au crédit', client_id=1, processus_metier_associe_id=ids_p['REA-03.1'])
    rq.dernier_niveau_risque = 'Critique'
    import datetime as dt
    au = socle.creer(M.Audit, reference='AUD-CP', titre='Audit crédit', type_audit='interne', client_id=1, statut='termine',
                     processus_concerne='Octroi et gestion des crédits')
    au.date_fin_reelle = dt.date.today() - dt.timedelta(days=90)
    db.session.commit()
r = appel(lect, 'get', '/carte-processus/?vue=risques')
html = r.data.decode()
verif('lecteur (voir) : carte affichée en vue risques', r.status_code == 200 and 'Processus de réalisation' in html and 'Octroi et gestion des crédits' in html, r.status_code)
m = re.search(r'var D = (\{.*?\}), GERER', html, re.S)
import json
D = json.loads(m.group(1)) if m else {'bandes': {}}
octroi = next((p for p in D['bandes'].get('realisation', []) if p['code'] == 'REA-03'), {})
verif('risque d’un sous-processus remonté sur son processus (Critique)', octroi.get('nb_risques') == 1 and octroi.get('niveau') == 4, octroi.get('niveau'))
verif('audit rattaché par le nom du processus : audité < 12 mois', octroi.get('couverture') == 'recent' and octroi.get('nb_audits') == 1, octroi.get('couverture'))
verif('lecteur : pas de bouton d’organisation ni de formulaire', 'id="cpOrganiser"' not in html and 'id="cpModalProcessus"' not in html and 'data-cp-nouveau>' not in html)
r = appel(lect, 'get', '/carte-processus/imprimer?vue=audit')
verif('version imprimable A4 paysage', r.status_code == 200 and b'A4 landscape' in r.data and b'Couverture d' in r.data, r.status_code)

print('--- Droits d’écriture')
r = poster(lect, '/carte-processus/processus', {'nom': 'Intrus', 'bande': 'support'})
verif('lecteur : ajout refusé', r.status_code == 403, r.status_code)
r = appel(lect, 'post', '/carte-processus/organiser', json={'bandes': {}}, headers={'X-CSRFToken': jeton(lect)})
verif('lecteur : organisation refusée', r.status_code == 403, r.status_code)
r = poster(gest, '/carte-processus/processus', {'nom': 'Gestion des réclamations <script>x</script>', 'code': 'REA-06', 'bande': 'realisation'})
with A.app.app_context():
    p = pm(code='REA-06').first()
    verif('gestionnaire (organiser) : processus ajouté', r.status_code in (302, 303) and p is not None and p.reference.startswith('PROC-'))
    PID = p.id
r = appel(gest, 'get', '/carte-processus/')
verif('nom échappé sur la carte', b'<script>x</script>' not in r.data and b'&lt;script&gt;x&lt;/script&gt;' in r.data)
r = poster(gest, '/carte-processus/processus', {'nom': 'Doublon', 'code': 'REA-06', 'bande': 'realisation'})
with A.app.app_context():
    verif('code déjà utilisé : refusé', pm(nom='Doublon').first() is None)
    verif('journal des modifications', M.JournalActiviteClient.query.filter_by(action='carto_processus_cree').count() >= 1)

print('--- Organiser, modifier, interactions, retirer')
with A.app.app_context():
    autre = socle.creer(M.ProcessusMetier, reference='PROC-B1', nom='Processus de B', client_id=2, type_processus='metier', is_archived=False, est_actif=True)
    db.session.commit()
    BID = autre.id
    pil = [p.id for p in pm(type_processus='strategique', parent_id=None).order_by(M.ProcessusMetier.code).all()]
r = appel(admin, 'post', '/carte-processus/organiser', json={'bandes': {'pilotage': list(reversed(pil[1:])), 'support': [pil[0], BID]}},
          headers={'X-CSRFToken': jeton(admin)})
with A.app.app_context():
    verif('glisser-déposer : changement de bande (type) et ordre enregistrés', r.status_code == 200 and db.session.get(M.ProcessusMetier, pil[0]).type_processus == 'support'
          and all(e.type_processus == 'support' for e in pm(parent_id=pil[0]).all()))
    verif('… processus d’une autre organisation ignoré', db.session.get(M.ProcessusMetier, BID).type_processus == 'metier')
    from egalyx import carto_processus as CP
    verif('… ordre gardé', CP.lire(1)['ordre']['pilotage'] == list(reversed(pil[1:])))
    pere, fils = ids_p['REA-03'], ids_p['REA-03.1']
r = poster(admin, '/carte-processus/processus', {'id': pere, 'nom': 'Octroi et gestion des crédits', 'parent_id': fils, 'bande': 'realisation'})
with A.app.app_context():
    verif('pas de boucle (processus rangé sous son propre sous-processus)', db.session.get(M.ProcessusMetier, pere).parent_id is None)
r = poster(admin, '/carte-processus/processus', {'id': BID, 'nom': 'Pirate', 'bande': 'support'})
with A.app.app_context():
    verif('modifier un processus d’une autre organisation : introuvable', r.status_code == 404 and db.session.get(M.ProcessusMetier, BID).nom == 'Processus de B', r.status_code)
r = poster(admin, '/carte-processus/interactions', {'de': ids_p['REA-01'], 'vers': ids_p['REA-03'], 'libelle': 'dossier KYC'})
r2 = poster(admin, '/carte-processus/interactions', {'de': ids_p['REA-01'], 'vers': BID, 'libelle': 'fuite'})
with A.app.app_context():
    fl = CP.lire(1)['flux']
    verif('interaction ajoutée ; vers une autre organisation refusée', len(fl) == 1 and fl[0]['libelle'] == 'dossier KYC', fl)
    FID = fl[0]['id'] if fl else 'x'
r = appel(admin, 'get', '/carte-processus/?interactions=1')
verif('interaction dessinée sur la carte', r.status_code == 200 and b'dossier KYC' in r.data and b'avec-liens' in r.data)
r = poster(admin, f'/carte-processus/interactions/{FID}/supprimer')
with A.app.app_context():
    verif('interaction supprimée', CP.lire(1)['flux'] == [])
r = poster(admin, '/carte-processus/reglages', {'titre': 'Macro-cartographie SODEMI', 'entree': 'Attentes', 'sortie': 'Satisfaction',
                                                'bande_pilotage': 'Management', 'bande_realisation': 'Opérationnels', 'bande_support': 'Supports'})
r = appel(admin, 'get', '/carte-processus/')
verif('réglages : titres de la carte et des bandes', b'Macro-cartographie SODEMI' in r.data and b'Op\xc3\xa9rationnels' in r.data and b'Attentes' in r.data)
r = poster(admin, f'/carte-processus/processus/{pere}/retirer')
with A.app.app_context():
    verif('retirer : processus et sous-processus archivés, risque gardé', db.session.get(M.ProcessusMetier, pere).is_archived
          and all(e.is_archived for e in pm(parent_id=pere).all()) and M.Risque.query.filter_by(reference='RQ-CP').first() is not None)
r = poster(admin, f'/carte-processus/processus/{BID}/retirer')
verif('retirer un processus d’une autre organisation : introuvable', r.status_code == 404, r.status_code)

print('--- Autre organisation')
r = poster(sa, '/super-admin/client/2/modules', {'action': 'enregistrer', 'modules': ['cartographie', 'carto_processus']}, page='/super-admin/client/2/modules')
r = appel(admin_b, 'get', '/carte-processus/')
verif('organisation B activée : ne voit que ses processus', r.status_code == 200 and b'Processus de B' in r.data and b'Octroi' not in r.data
      and b'Macro-cartographie SODEMI' not in r.data, r.status_code)
r = appel(sa, 'get', '/carte-processus/?client_id=1')
verif('super admin : consulte la carte d’une organisation', r.status_code == 200 and b'Macro-cartographie SODEMI' in r.data, r.status_code)
r = poster(sa, '/super-admin/client/1/modules', {'action': 'aucune_restriction'}, page='/super-admin/client/1/modules')
verif('« Retirer la restriction » : la carte redevient fermée (activation explicite)', appel(admin, 'get', '/carte-processus/').status_code == 403)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
