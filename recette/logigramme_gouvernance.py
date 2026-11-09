"""Logigrammes : versions et validation, couloirs d'acteurs, vérification du dessin, conversion des anciens processus."""
import os, re, sys, json, datetime as dt
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
nav = {r: socle.navigateur(A, ids[r]) for r in ('gestionnaire', 'validateur', 'lecteur', 'admin_a', 'admin_b')}
with A.app.app_context():
    v = db.session.get(M.User, ids['validateur']); p = dict(v.permissions); p['can_manage_logigram'] = True
    v.permissions = p; db.session.commit()
JETON = {}
def jeton(role):
    if role not in JETON:
        t = appel(nav[role], 'get', '/dashboard').data.decode('utf-8', 'ignore')
        mm = re.search(r'name="csrf-token" content="([^"]+)"', t); JETON[role] = mm.group(1) if mm else ''
    return JETON[role]
def go(role, m, url, **kw):
    if m != 'get' and 'json' in kw:
        kw.setdefault('headers', {})['X-CSRFToken'] = jeton(role)
    r = appel(nav[role], m, url, **kw); return r, socle.cause(A)
def js(r):
    try: return json.loads(r.data or b'{}')
    except Exception: return {}
def act(i):
    with A.app.app_context():
        a = db.session.get(M.ProcessusActivite, i); db.session.expunge(a); return a

go('gestionnaire', 'post', '/logigramme/nouveau', data={'nom': 'Achats', 'description': 'Procédure achats'})
with A.app.app_context():
    aid = M.ProcessusActivite.query.filter_by(nom='Achats').first().id
def el(typ, lib, x, y):
    r, _ = go('gestionnaire', 'post', f'/api/logigramme/{aid}/elements', json={'type': typ, 'libelle': lib, 'position_x': x, 'position_y': y}); return js(r).get('id')
def lien(s, c, lib=''):
    go('gestionnaire', 'post', f'/api/logigramme/{aid}/liens', json={'source_id': s, 'cible_id': c, 'libelle': lib})

print('--- Vérification du dessin')
r, e = go('gestionnaire', 'get', f'/logigrammes-suivi/{aid}/verification'); v = js(r)
verif('Logigramme vide : erreur', not v.get('ok') and v.get('erreurs'), e)
d = el('debut', 'Besoin', 20, 50); dem = el('action', 'Demande d\'achat', 200, 50); dec = el('decision', 'Montant > 5 000 ?', 380, 40)
n1 = el('controle', 'Visa du directeur', 560, 220); cmd = el('action', 'Bon de commande', 740, 50); isole = el('action', 'Étape oubliée', 900, 400)
lien(d, dem); lien(dem, dec); lien(dec, n1)
r, _ = go('gestionnaire', 'get', f'/logigrammes-suivi/{aid}/verification'); v = js(r)
msgs = ' | '.join(x['message'] for x in v['erreurs'])
verif('Sans fin, étape isolée, décision à une sortie : erreurs détectées',
      'Aucune « Fin »' in msgs and 'reliée(s) à rien' in msgs and 'deux sorties' in msgs, msgs[:200])
r, e = go('gestionnaire', 'post', f'/logigrammes-suivi/{aid}/soumettre')
verif('Soumission refusée tant qu\'il y a des erreurs', (act(aid).statut_validation or 'brouillon') == 'brouillon', e)
fin = el('fin', 'Commande envoyée', 1080, 50)
lien(dec, cmd); lien(n1, cmd); lien(cmd, fin)
go('gestionnaire', 'delete', f'/api/element/{isole}', json={})
r, _ = go('gestionnaire', 'get', f'/logigrammes-suivi/{aid}/verification'); v = js(r)
av = ' | '.join(x['message'] for x in v['avertissements'])
verif('Dessin corrigé : plus d\'erreur', v.get('ok'), ' | '.join(x['message'] for x in v['erreurs']))
verif('Avertissements utiles : sorties de décision non libellées, contrôle non rattaché', 'Libellez' in av and 'sans contrôle du référentiel' in av, av[:200])

print('--- Couloirs d\'acteurs')
r, e = go('gestionnaire', 'post', f'/logigrammes-suivi/{aid}/acteurs', data={'acteurs': 'Demandeur\nDirecteur\nAcheteur\ndemandeur'})
verif('Couloirs enregistrés (doublon ignoré)', act(aid).acteurs == ['Demandeur', 'Directeur', 'Acheteur'], f'{act(aid).acteurs} {e}')
r, _ = go('gestionnaire', 'get', f'/logigrammes-suivi/{aid}/acteurs')
verif('L\'éditeur récupère les couloirs', js(r).get('acteurs') == ['Demandeur', 'Directeur', 'Acheteur'])
with A.app.app_context():
    from egalyx.logigrammes import acteur_de
    a = db.session.get(M.ProcessusActivite, aid)
    verif('Chaque étape appartient au couloir où elle est dessinée',
          acteur_de(db.session.get(M.ElementLogigramme, dem), a.acteurs) == 'Demandeur' and
          acteur_de(db.session.get(M.ElementLogigramme, n1), a.acteurs) == 'Directeur')
r, e = go('gestionnaire', 'get', f'/editer_logigramme/{aid}'); t = r.data.decode('utf-8', 'ignore')
verif('Éditeur : barre de gouvernance, couche des couloirs, bouton « Vérifier »',
      r.status_code == 200 and 'couloirs-layer' in t and 'btn-verifier-logigramme' in t and 'Versions, validation' in t, e)
r, e = go('lecteur', 'post', f'/logigrammes-suivi/{aid}/acteurs', data={'acteurs': 'Pirate'})
verif('Un lecteur ne modifie pas les couloirs', act(aid).acteurs[0] == 'Demandeur', str(r.status_code))

print('--- Versions et validation')
go('gestionnaire', 'post', f'/logigrammes-suivi/{aid}/proprietaire', data={'proprietaire_id': str(ids['lecteur'])})
verif('Propriétaire désigné', act(aid).proprietaire_id == ids['lecteur'])
r, e = go('gestionnaire', 'post', f'/logigrammes-suivi/{aid}/soumettre')
verif('Soumission à validation', act(aid).statut_validation == 'en_validation', e)
go('validateur', 'post', f'/logigrammes-suivi/{aid}/rejeter', data={'motif': 'court'})
verif('Rejet sans motif refusé', act(aid).statut_validation == 'en_validation')
go('validateur', 'post', f'/logigrammes-suivi/{aid}/rejeter', data={'motif': 'Ajouter le seuil dans la décision'})
x = act(aid)
verif('Rejet motivé : retour en brouillon avec le motif', x.statut_validation == 'brouillon' and x.motif_rejet, x.motif_rejet)
go('gestionnaire', 'post', f'/logigrammes-suivi/{aid}/soumettre')
os.environ['EGALYX_LOGIGRAMME_DOUBLE_REGARD'] = '1'
go('gestionnaire', 'post', f'/logigrammes-suivi/{aid}/valider')
verif('Option double regard : l\'auteur ne valide pas lui-même', act(aid).statut_validation == 'en_validation')
os.environ.pop('EGALYX_LOGIGRAMME_DOUBLE_REGARD')
r, e = go('validateur', 'post', f'/logigrammes-suivi/{aid}/valider', data={'commentaire': 'Conforme à la politique achats'})
x = act(aid)
verif('Validation : version 1, revue dans un an', x.statut_validation == 'valide' and x.version_courante == 1
      and x.date_revue_prevue == dt.date.today() + dt.timedelta(days=365), e)
with A.app.app_context():
    v1 = M.VersionLogigramme.query.filter_by(activite_id=aid, version=1).first()
    verif('La version 1 est figée (éléments, liens, couloirs, acteur de chaque étape)',
          v1 and len(v1.contenu['elements']) == 6 and len(v1.contenu['liens']) == 6 and v1.contenu['acteurs'][0] == 'Demandeur'
          and any(e['acteur'] == 'Directeur' for e in v1.contenu['elements']), str(v1.contenu['acteurs'] if v1 else None))
    v1id = v1.id
r, e = go('lecteur', 'get', f'/logigrammes-suivi/{aid}/version/{v1id}'); t = r.data.decode('utf-8', 'ignore')
verif('Le propriétaire consulte la version figée (dessin + tableau)', r.status_code == 200 and '<svg' in t and 'Visa du directeur' in t, e)
go('gestionnaire', 'put', f'/api/element/{cmd}', json={'libelle': 'Bon de commande signé'})
x = act(aid)
verif('Modifier le dessin le repasse en brouillon ; la v1 reste en vigueur', x.statut_validation == 'brouillon' and x.version_courante == 1)
with A.app.app_context():
    v1 = db.session.get(M.VersionLogigramme, v1id)
    verif('… et la copie figée de la v1 n\'a pas bougé', any(e['libelle'] == 'Bon de commande' for e in v1.contenu['elements']))
go('gestionnaire', 'post', f'/logigrammes-suivi/{aid}/soumettre'); go('gestionnaire', 'post', f'/logigrammes-suivi/{aid}/valider')
with A.app.app_context():
    v2 = M.VersionLogigramme.query.filter_by(activite_id=aid, version=2).first()
verif('Par défaut, l\'auteur peut valider : version 2, tracée « par son auteur »', v2 and v2.nature == 'auto_validation')
go('lecteur', 'post', f'/logigrammes-suivi/{aid}/revue', data={'commentaire': 'Rien à changer'})
with A.app.app_context():
    nb = M.VersionLogigramme.query.filter_by(activite_id=aid, nature='revue').count()
verif('Le propriétaire confirme la revue annuelle', nb == 1)
r, e = go('gestionnaire', 'get', f'/logigrammes-suivi/{aid}')
verif('Page « Versions et validation »', r.status_code == 200 and 'Historique des versions' in r.data.decode('utf-8', 'ignore'), e)
r, e = go('gestionnaire', 'get', '/liste_logigrammes'); t = r.data.decode('utf-8', 'ignore')
verif('Liste : statut et version affichés', 'Validé · v2' in t, e)
with A.app.app_context():
    a = db.session.get(M.ProcessusActivite, aid); a.date_revue_prevue = dt.date.today() - dt.timedelta(days=3); db.session.commit()
r, _ = go('gestionnaire', 'get', '/liste_logigrammes')
verif('Liste : « Revue en retard »', 'Revue en retard' in r.data.decode('utf-8', 'ignore'))
r, _ = go('lecteur', 'get', '/ma-semaine')
verif('« Ma semaine » du propriétaire : revue de procédure', 'Revue de procédure' in r.data.decode('utf-8', 'ignore'))
r, _ = go('admin_b', 'get', f'/logigrammes-suivi/{aid}')
verif('L\'autre organisation n\'y a pas accès', r.status_code == 404, str(r.status_code))
r, _ = go('admin_b', 'get', f'/logigrammes-suivi/{aid}/version/{v1id}')
verif('… ni aux versions', r.status_code == 404, str(r.status_code))

print('--- Conversion d\'un ancien processus')
with A.app.app_context():
    p = socle.creer(M.Processus, nom='Recrutement', client_id=1, responsable_id=ids['gestionnaire'])
    e1 = socle.creer(M.EtapeProcessus, processus_id=p.id, ordre=1, nom='Expression du besoin', responsable_id=ids['lecteur'], type_etape='action', client_id=1)
    e2 = socle.creer(M.EtapeProcessus, processus_id=p.id, ordre=2, nom='Budget disponible ?', responsable_id=ids['gestionnaire'], type_etape='decision', client_id=1)
    e3 = socle.creer(M.EtapeProcessus, processus_id=p.id, ordre=3, nom='Entretien', responsable_id=ids['lecteur'], type_etape='action', client_id=1)
    db.session.commit(); pid = p.id
r, e = go('gestionnaire', 'get', f'/processus/{pid}')
verif('La fiche de l\'ancien processus propose la conversion', 'Convertir ce processus en logigramme' in r.data.decode('utf-8', 'ignore'), f'{r.status_code} {e}')
r, e = go('gestionnaire', 'post', f'/logigrammes-suivi/convertir-processus/{pid}')
with A.app.app_context():
    c = M.ProcessusActivite.query.filter_by(processus_source_id=pid).first()
    els = M.ElementLogigramme.query.filter_by(activite_id=c.id).all() if c else []
    types = sorted(x.type_element for x in els)
    nl = M.LienLogigramme.query.filter_by(activite_id=c.id).count() if c else 0
verif('Converti : début + 3 étapes + fin, enchaînées, couloirs par responsable',
      c and types == ['action', 'action', 'debut', 'decision', 'fin'] and nl == 4 and len(c.acteurs) == 2, f'{types} {nl} {c.acteurs if c else None} {e}')
go('gestionnaire', 'post', f'/logigrammes-suivi/convertir-processus/{pid}')
with A.app.app_context():
    verif('Une seconde conversion ne crée pas de doublon', M.ProcessusActivite.query.filter_by(processus_source_id=pid).count() == 1)
r, _ = go('admin_b', 'post', f'/logigrammes-suivi/convertir-processus/{pid}')
verif('L\'autre organisation ne peut pas le convertir', r.status_code == 404, str(r.status_code))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
