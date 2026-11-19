"""Recette : plus aucun bouton ne vise une adresse inexistante, et les adresses ajoutées marchent (avec les bons droits).

1. Balayage de tous les gabarits AFFICHÉS : appels fetch(...), window.open / location.href et liens href="/..." en dur
   comparés aux adresses réelles de l'application (et à la méthode HTTP utilisée).
2. Chaque adresse réparée (egalyx/boutons_repares.py) est appelée : résultat, droits, cloisonnement.
"""
import datetime as dt
import glob
import os
import re
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, creer
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
import models as M
from models import db

app = A.app
RACINE = os.path.join(app.root_path, 'templates')
regles = [(r.rule, r.methods - {'HEAD', 'OPTIONS'}) for r in app.url_map.iter_rules()]


def motif(rule):
    return re.compile('^' + re.escape(re.sub(r'<[^>]+>', '\x00', rule)).replace('\x00', '[^/]+') + '/?$')


REGLES = [(motif(r), m) for r, m in regles]
DERNIERS = {r.rstrip('/').rsplit('/', 1)[-1] for r, _ in regles if '<' not in r.rstrip('/').rsplit('/', 1)[-1]}
# gabarits affichés : appelés par render_template quelque part, ou inclus / étendus par un gabarit
code = ''.join(open(f, encoding='utf-8', errors='ignore').read() for f in
               [os.path.join(app.root_path, 'app.py')] + glob.glob(os.path.join(app.root_path, 'sections', '*.py'))
               + glob.glob(os.path.join(app.root_path, 'egalyx', '*.py')))
tous = {os.path.relpath(f, RACINE): open(f, encoding='utf-8', errors='ignore').read()
        for f in glob.glob(os.path.join(RACINE, '**', '*.html'), recursive=True)}
inclus = set()
for s in tous.values():
    inclus.update(re.findall(r'{%-?\s*(?:include|extends|import|from)\s+["\']([^"\']+)["\']', s))
affiches = {t for t in tous if f"'{t}'" in code or f'"{t}"' in code or t in inclus}
FETCH = re.compile(r'fetch\(\s*([`\'"])(/[^`\'"]*?)\1\s*(?:\+\s*[\w.]+\s*\+\s*([`\'"])([^`\'"]*)\3)?\s*(,\s*\{(.{0,400}?)\})?', re.S)
LIEN = re.compile(r'(?:window\.open\(|location\.href\s*=)\s*([`\'"])(/[^`\'"]*)\1(?:\s*\+\s*[\w.]+\s*\+\s*([`\'"])([^`\'"]*)\3)?')
HREF = re.compile(r'href=(["\'])(/[a-zA-Z][^"\'{}]*)\1')


def resoudre(url, suite=None):
    u = url + ('1' + suite if suite is not None else '')
    u = re.sub(r'\$\{[^}]*\}', '1', u)
    u = u.split('?')[0].split('#')[0]
    return u if (suite == '/' or not u.endswith('/') or len(u) == 1) else u + '1'


morts = []
for t in sorted(affiches):
    s = tous[t]
    for m in FETCH.finditer(s):
        url = m.group(2)
        if '{{' in url or url.startswith('/static/'):
            continue
        u = resoudre(url, m.group(4))
        meth = re.search(r"method\s*:\s*['\"](\w+)", m.group(6) or '')
        meth = meth.group(1).upper() if meth else 'GET'
        if m.group(4) == '/':        # '/api/client/' + id + '/' + action : action variable -> l'un des segments connus
            trouvees = [ms for seg in DERNIERS for rx, ms in REGLES if rx.match(u + seg)]
        else:
            trouvees = [ms for rx, ms in REGLES if rx.match(u)]
        if not trouvees:
            morts.append((t, 'fetch', url))
        elif not any(meth in ms for ms in trouvees):
            morts.append((t, f'méthode {meth}', url))
    for m in list(LIEN.finditer(s)) + list(HREF.finditer(s)):
        url = m.group(2)
        if '{{' in url or url.startswith(('/static/', '//')) or url == '/':
            continue
        u = resoudre(url, m.group(4) if m.re is LIEN else None)
        if not any(rx.match(u) for rx, _ in REGLES):
            morts.append((t, 'lien', url))
print('--- Balayage des gabarits affichés')
verif(f'{len(affiches)} gabarits affichés : aucun appel vers une adresse inexistante', not morts,
      '\n      ' + '\n      '.join(f'{t} [{k}] {u}' for t, k, u in morts[:40]))

print('--- Adresses réparées')
adm = socle.navigateur(A, ids['admin_a'])
sup = socle.navigateur(A, ids['superadmin'])
lec = socle.navigateur(A, ids['lecteur'])
autre = socle.navigateur(A, ids['admin_b'])
with A.app.app_context():
    cid = db.session.get(M.User, ids['admin_a']).client_id
    k = M.ApiKey(client_id=cid, name='ERP', created_by=ids['admin_a']); k.generate_keys(); db.session.add(k)
    inc = creer(M.Incident, client_id=cid, titre='Panne serveur', reference='INC-ARCH', is_archived=True)
    q = creer(M.Questionnaire, titre='Satisfaction', code='SAT-1', client_id=cid, created_by=ids['admin_a'])
    db.session.flush()
    cat = creer(M.QuestionnaireCategorie, questionnaire_id=q.id, titre='Général', client_id=cid)
    db.session.flush()
    qu = creer(M.Question, categorie_id=cat.id, texte='Êtes-vous satisfait ?', type='choix', client_id=cid)
    db.session.flush()
    creer(M.OptionQuestion, question_id=qu.id, valeur='oui', texte='Oui', client_id=cid)
    vieux = creer(M.KRI, nom='KRI ancien', client_id=cid, est_actif=False, archived_at=dt.datetime.utcnow() - dt.timedelta(days=120))
    recent = creer(M.KRI, nom='KRI récent', client_id=cid, est_actif=False, archived_at=dt.datetime.utcnow() - dt.timedelta(days=5))
    db.session.commit()
    KID, OLD, IID, QID, NEW, KEY = k.id, vieux.id, inc.id, q.id, recent.id, k.api_key

r = adm.get(f'/admin/api-keys/{KID}/details')
verif('clé API : détail', r.status_code == 200 and r.get_json()['api_key'] == KEY, str(r.status_code))
verif('… autre organisation : introuvable', autre.get(f'/admin/api-keys/{KID}/details').status_code == 404)
r = adm.post(f'/admin/api-keys/{KID}/regenerer')
verif('clé API : régénérée (nouvelle clé)', r.status_code == 200 and r.get_json()['api_key'] != KEY)
r = adm.post(f'/admin/api-keys/{KID}/revoke')
with A.app.app_context():
    verif('clé API : révoquée', r.status_code == 200 and db.session.get(M.ApiKey, KID).is_revoked)
r = lec.post(f'/admin/api-keys/{KID}/regenerer')
verif('… simple utilisateur : refusé', r.status_code in (302, 403))

with A.app.app_context():
    t = M.PermissionTemplate(name='Lecture seule', role='utilisateur', permissions={'can_view_audit': True}, client_id=cid)
    t_autre = M.PermissionTemplate(name='Modèle B', role='utilisateur', permissions={'can_manage_audit': True},
                                   client_id=db.session.get(M.User, ids['admin_b']).client_id)
    db.session.add_all([t, t_autre]); db.session.commit(); TID, TB = t.id, t_autre.id
h = adm.get('/admin/templates-permissions').data.decode()
verif('modèles de permissions : seulement ceux de l\'organisation', 'Lecture seule' in h and 'Modèle B' not in h)
r = adm.post(f'/admin/template/{TID}/appliquer')
with A.app.app_context():
    u = db.session.get(M.User, ids['lecteur'])
    verif('modèle appliqué aux utilisateurs du rôle (administrateurs exclus)', r.status_code == 200 and u.permissions == {'can_view_audit': True}
          and db.session.get(M.User, ids['admin_a']).permissions != {'can_view_audit': True}, str(r.get_json()))
verif('modèle d\'une autre organisation : introuvable', adm.post(f'/admin/template/{TB}/appliquer').status_code == 404)

r = adm.delete(f'/api/incident/{IID}/supprimer-definitivement')
with A.app.app_context():
    verif('incident archivé supprimé définitivement', r.status_code == 200 and db.session.get(M.Incident, IID) is None, str(r.get_json()))

r = adm.post('/kri/nettoyer-anciens')
with A.app.app_context():
    verif('KRI archivés > 90 jours supprimés, les récents gardés', r.get_json()['count'] == 1 and db.session.get(M.KRI, OLD) is None
          and db.session.get(M.KRI, NEW) is not None, str(r.get_json()))
r = adm.get('/api/kris/archives/export')
verif('export des KRI archivés (CSV)', r.status_code == 200 and 'KRI récent' in r.data.decode('utf-8-sig'))
r = adm.post('/kri/restaurer-tous')
with A.app.app_context():
    verif('tous les KRI archivés restaurés', r.get_json()['count'] >= 1 and db.session.get(M.KRI, NEW).est_actif)

r = adm.post(f'/questionnaires/{QID}/dupliquer')
with A.app.app_context():
    c = M.Questionnaire.query.filter(M.Questionnaire.code.like('SAT-1-COPIE%')).first()
    verif('questionnaire dupliqué avec ses questions et options (inactif)', r.status_code == 200 and c is not None and not c.est_actif
          and sum(len(x.questions) for x in c.categories) == 1 and len(c.categories[0].questions[0].options) == 1)
verif('… autre organisation : introuvable', autre.post(f'/questionnaires/{QID}/dupliquer').status_code == 404)

r = adm.get('/api/demandes-reevaluation/stats')
verif('réévaluations : statistiques', r.status_code == 200 and 'total' in r.get_json()['stats'], str(r.status_code))
r = adm.get('/api/demandes-reevaluation/liste?statut=en_attente')
verif('réévaluations : liste', r.status_code == 200 and isinstance(r.get_json()['demandes'], list))

r = sup.get('/api/system/health')
verif('super admin : santé du système', r.status_code == 200 and r.get_json()['database'] is True)
verif('super admin : recharger les gabarits', sup.post('/api/system/reload-templates').get_json()['success'])
verif('super admin : export des journaux', sup.get('/api/system/export-logs').status_code == 200)
verif('… administrateur d\'organisation : pas d\'accès', adm.get('/api/system/health').status_code == 404)

anon = app.test_client()
for p in ('guide-utilisation', 'completes'):
    r = anon.get(f'/docs/{p}')
    verif(f'documentation publique /docs/{p}', r.status_code == 200, str(r.status_code))
verif('/docs/api -> documentation de l\'API', anon.get('/docs/api').status_code == 302)
r = anon.post('/api/contact', data={'nom_complet': 'Awa', 'email': 'awa@exemple.ci', 'message': 'Bonjour', 'sujet': "Contact Côte d'Ivoire"})
verif('formulaire Côte d\'Ivoire -> adresse de contact réelle (protégée par la question anti-spam)', r.status_code == 400 and 'anti-spam' in (r.get_json().get('message') or ''), str(r.status_code))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
