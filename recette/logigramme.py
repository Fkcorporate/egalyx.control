"""Module Processus / logigrammes : parcours réel + droits + étanchéité."""
import sys, json
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
nav = {r: socle.navigateur(A, ids[r]) for r in ('gestionnaire', 'lecteur', 'operateur', 'admin_b')}
import re as _re
JETON = {}
def jeton(role):
    if role not in JETON:
        t = appel(nav[role], 'get', '/dashboard').data.decode('utf-8', 'ignore')
        mm = _re.search(r'name="csrf-token" content="([^"]+)"', t)
        JETON[role] = mm.group(1) if mm else ''
    return JETON[role]
def go(role, m, url, **kw):
    if m != 'get':
        kw.setdefault('headers', {})['X-CSRFToken'] = jeton(role)
    r = appel(nav[role], m, url, **kw); return r, socle.cause(A)
def js(r):
    try:
        return json.loads(r.data or b'{}')
    except Exception:
        return {}

r, e = go('gestionnaire', 'get', '/logigramme/nouveau')
verif('Page « nouveau logigramme »', r.status_code == 200, f'{r.status_code} {e}')
r, e = go('gestionnaire', 'post', '/logigramme/nouveau', data={'nom': 'Paiement fournisseurs', 'description': 'De la facture au virement',
                                                               'direction_id': str(O['direction'])})
with A.app.app_context():
    act = M.ProcessusActivite.query.filter_by(nom='Paiement fournisseurs').first(); aid = act.id if act else None
verif('Création du logigramme', aid is not None, f'{r.status_code} {e}')
r, e = go('gestionnaire', 'get', f'/editer_logigramme/{aid}')
verif('Éditeur : s\'ouvre', r.status_code == 200, f'{r.status_code} {e}')
els = []
for i, (typ, lib) in enumerate([('debut', 'Réception facture'), ('action', 'Saisie comptable'), ('controle', 'Validation N+1'), ('fin', 'Virement')]):
    r, e = go('gestionnaire', 'post', f'/api/logigramme/{aid}/elements', json={'type': typ, 'libelle': lib, 'position_x': 100 + 150 * i, 'position_y': 100})
    els.append(js(r).get('id'))
verif('Ajout de 4 éléments', all(els), f'{els} {e}')
liens = []
for a, b in zip(els, els[1:]):
    r, e = go('gestionnaire', 'post', f'/api/logigramme/{aid}/liens', json={'source_id': a, 'cible_id': b})
    liens.append(js(r).get('id'))
verif('Ajout de 3 liens', all(liens), f'{liens} {e}')
r, e = go('gestionnaire', 'post', f'/api/logigramme/{aid}/liens', json={'source_id': els[0], 'cible_id': 999999})
with A.app.app_context():
    autre = M.ProcessusActivite(nom='Autre logigramme', client_id=1, created_by=ids['gestionnaire']); db.session.add(autre); db.session.flush()
    eo = M.ElementLogigramme(activite_id=autre.id, type_element='action', libelle='Ailleurs', position_x=0, position_y=0, client_id=1)
    db.session.add(eo); db.session.commit(); eo_id = eo.id
r2, e2 = go('gestionnaire', 'post', f'/api/logigramme/{aid}/liens', json={'source_id': els[0], 'cible_id': eo_id})
with A.app.app_context():
    n_croise = M.LienLogigramme.query.filter_by(element_cible_id=eo_id).count()
verif('Lien vers l\'élément d\'un AUTRE logigramme refusé', n_croise == 0, f'{r2.status_code} {e2}')
verif('Lien vers un élément inexistant refusé', r.status_code >= 400 or not js(r).get('success', True), f'{r.status_code} {e}')
r, e = go('gestionnaire', 'post', f'/api/logigramme/element/{els[2]}/associer-risque', json={'risque_id': O['risque']})
verif('Rattacher un risque à une étape', r.status_code == 200 and js(r).get('success', True), f'{r.status_code} {e} {js(r)}')
r, e = go('gestionnaire', 'get', f'/api/logigramme/{aid}/risques-associes')
verif('Risques du logigramme', r.status_code == 200, f'{r.status_code} {e}')
r, e = go('gestionnaire', 'put', f'/api/element/{els[1]}', json={'libelle': 'Saisie et rapprochement', 'position_x': 260, 'position_y': 120})
with A.app.app_context():
    el = db.session.get(M.ElementLogigramme, els[1])
verif('Modifier un élément (texte, position)', el and el.libelle == 'Saisie et rapprochement', e)
for fmt in ('export-json', 'export-html', 'export-diagramme', 'export-visuel'):
    r, e = go('gestionnaire', 'get', f'/logigramme/{aid}/{fmt}')
    verif(f'Export {fmt}', r.status_code == 200, f'{r.status_code} {e[:120]}')
r, e = go('gestionnaire', 'get', '/liste_logigrammes')
verif('Liste des logigrammes', r.status_code == 200 and 'Paiement fournisseurs' in r.data.decode('utf-8', 'ignore'), e)
# Droits
with A.app.app_context():
    n_av = M.ElementLogigramme.query.filter_by(activite_id=aid).count()
r, e = go('lecteur', 'post', f'/api/logigramme/{aid}/elements', json={'type': 'action', 'libelle': 'Intrus', 'position_x': 1, 'position_y': 1})
r2, _ = go('lecteur', 'delete', f'/api/element/{els[1]}')
with A.app.app_context():
    n_ap = M.ElementLogigramme.query.filter_by(activite_id=aid).count()
verif('Un lecteur ne peut ni ajouter ni supprimer d\'élément', n_ap == n_av, f'{r.status_code}/{r2.status_code}')
r, e = go('operateur', 'put', f'/api/element/{els[1]}', json={'libelle': 'Opérateur'})
with A.app.app_context():
    verif('Un opérateur ne peut pas modifier le logigramme', db.session.get(M.ElementLogigramme, els[1]).libelle != 'Opérateur', str(r.status_code))
r, e = go('admin_b', 'get', f'/editer_logigramme/{aid}')
verif('L\'autre organisation ne l\'ouvre pas', r.status_code in (302, 403, 404) and 'Paiement fournisseurs' not in r.data.decode('utf-8', 'ignore'), str(r.status_code))
r, e = go('admin_b', 'get', f'/api/logigramme/{aid}/elements')
verif('… ni ses éléments par l\'API', r.status_code in (403, 404) or not (js(r).get('elements')), str(r.status_code))
r, e = go('admin_b', 'put', f'/api/element/{els[0]}', json={'libelle': 'Piraté'})
with A.app.app_context():
    verif('… ni ne modifie un élément', db.session.get(M.ElementLogigramme, els[0]).libelle != 'Piraté', str(r.status_code))
r, e = go('admin_b', 'post', f'/api/logigramme/element/{els[0]}/associer-risque', json={'risque_id': O['risque']})
r, e = go('gestionnaire', 'post', f'/api/logigramme/element/{els[0]}/associer-risque', json={'risque_id': 3})
with A.app.app_context():
    croise = M.RisqueElementLogigramme.query.filter_by(element_logigramme_id=els[0], risque_id=3).count()
verif('On ne rattache pas le risque d\'une autre organisation', croise == 0, f'{r.status_code} {js(r)}')
r, e = go('gestionnaire', 'post', f'/api/logigramme/{aid}/archiver')
with A.app.app_context():
    verif('Archivage', db.session.get(M.ProcessusActivite, aid).is_archived, f'{r.status_code} {e}')
r, e = go('gestionnaire', 'post', f'/api/logigramme/{aid}/restaurer')
r, e = go('gestionnaire', 'post', f'/api/logigramme/{aid}/elements', json={'type': 'decision', 'libelle': 'Montant > 10 000 ?', 'position_x': 300, 'position_y': 250})
did = js(r).get('id')
r1, _ = go('gestionnaire', 'post', f'/api/logigramme/{aid}/liens', json={'source_id': did, 'cible_id': els[2], 'libelle': 'Oui'})
r2, _ = go('gestionnaire', 'post', f'/api/logigramme/{aid}/liens', json={'source_id': did, 'cible_id': els[3], 'libelle': 'Non'})
with A.app.app_context():
    sorties = sorted(l.libelle for l in M.LienLogigramme.query.filter_by(element_source_id=did).all())
verif('Décision (losange) avec deux sorties « Oui » / « Non »', did and sorties == ['Non', 'Oui'], str(sorties))
r, e = go('gestionnaire', 'get', f'/editer_logigramme/{aid}')
verif('L\'éditeur propose la forme « Décision »', 'data-type="decision"' in r.data.decode('utf-8', 'ignore'), e)
for fmt in ('export-html', 'export-visuel', 'export-diagramme'):
    r, e = go('gestionnaire', 'get', f'/logigramme/{aid}/{fmt}')
    verif(f'Export {fmt} avec une décision', r.status_code == 200, f'{r.status_code} {e[:100]}')
print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
