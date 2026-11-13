"""Recette : connecteurs KRI (12 outils) — requêtes exactes, lecture de la valeur, erreurs, pages, droits, relevé automatique."""
import datetime as dt
import json
import os
import re
from cryptography.fernet import Fernet
os.environ.setdefault('EGALYX_CLE_CHIFFREMENT', Fernet.generate_key().decode())
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import requests
import socle
from socle import Muet
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


# ---------------------------------------------------------------- faux réseau : chaque outil répond comme sa documentation
APPELS = []


class Rep:
    def __init__(self, code, corps):
        self.status_code = code; self._b = json.dumps(corps).encode()
    def iter_content(self, n):
        yield self._b
    def json(self):
        return json.loads(self._b)


REPONSES = {
    'atlassian.net/rest/api/3/search/approximate-count': {'count': 7},
    'service-now.com/api/now/stats/': {'result': {'stats': {'count': '12'}}},
    'zendesk.com/api/v2/search/count': {'count': 31},
    'freshdesk.com/api/v2/search/tickets': {'results': [], 'total': 4},
    'api.github.com/search/issues': {'total_count': 9, 'incomplete_results': False, 'items': []},
    '/issues_statistics': {'statistics': {'counts': {'all': 50, 'closed': 38, 'opened': 12}}},
    'api.hubapi.com/crm/v3/objects/': {'total': 17, 'results': []},
    '/json/2/account.move/search_count': 23,
    'pagerduty.com/incidents': {'incidents': [], 'limit': 1, 'offset': 0, 'more': True, 'total': 3},
    '/api/v1/query': {'status': 'ok', 'series': [{'pointlist': [[1, 0.5], [2, 1.25], [3, None]]}]},
    'sheets.googleapis.com': {'range': 'KRI!B2', 'majorDimension': 'ROWS', 'values': [['12,5 %']]},
    'api.airtable.com': {'id': 'recABCDEFGHIJ1234', 'fields': {'Total': 42, 'Nom': 'x'}},
}
FORCER = {}


def faux_request(methode, url, **kw):
    APPELS.append(dict(kw, methode=methode, url=url))
    for motif, (code, corps) in FORCER.items():
        if motif in url:
            if code == 'timeout':
                raise requests.Timeout()
            return Rep(code, corps)
    for motif, corps in REPONSES.items():
        if motif in url:
            return Rep(200, corps)
    return Rep(404, {})


requests.request = faux_request

with Muet():
    A, ids = socle.preparer()
import objets
import models as M
from models import db
from egalyx import kri_connecteurs as K, kri_sources_securite as S
S.hote_public = lambda h: bool(h) and not re.match(r'^\d', h) and h not in ('localhost',)
with Muet():
    try: objets.peupler_objets(A, ids)
    except TypeError: objets.peupler_objets(A)

# ---------------------------------------------------------------- 1. les 12 connecteurs
CAS = {
    'jira': ({'site': 'https://monentreprise.atlassian.net/jira', 'email': 'ci@m.fr', 'jql': 'project = SEC AND statusCategory != Done'}, {'jeton': 'tok'}, 7),
    'servicenow': ({'instance': 'monentreprise', 'utilisateur': 'svc', 'table': 'incident', 'requete': 'active=true^priority=1'}, {'jeton': 'pw'}, 12),
    'zendesk': ({'sous_domaine': 'monentreprise', 'email': 'a@m.fr', 'requete': 'type:ticket status<solved'}, {'jeton': 'tok'}, 31),
    'freshdesk': ({'domaine': 'monentreprise.freshdesk.com', 'requete': 'status:2 AND priority:4'}, {'jeton': 'key'}, 4),
    'github': ({'recherche': 'repo:o/r is:issue is:open label:securite'}, {'jeton': 'ghp'}, 9),
    'gitlab': ({'adresse': 'gitlab.com', 'projet': 'monorg/appli', 'etiquettes': 'securite', 'etat': 'opened'}, {'jeton': 'glpat'}, 12),
    'hubspot': ({'objet': 'tickets', 'propriete': 'hs_pipeline_stage', 'operateur': 'EQ', 'valeur': '1'}, {'jeton': 'pat'}, 17),
    'odoo': ({'adresse': 'monentreprise.odoo.com', 'base': 'monentreprise', 'modele': 'account.move',
              'domaine': '[["payment_state", "=", "not_paid"]]'}, {'jeton': 'k'}, 23),
    'pagerduty': ({'region': 'eu', 'statuts': 'triggered,acknowledged'}, {'jeton': 'pd'}, 3),
    'datadog': ({'site': 'datadoghq.eu', 'requete': 'avg:x{env:prod}', 'fenetre': '1h'}, {'jeton': 'api', 'jeton2': 'app'}, 1.25),
    'google_sheets': ({'classeur': 'https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789/edit#gid=0', 'cellule': 'KRI!B2'}, {'jeton': 'AIza'}, 12.5),
    'airtable': ({'base': 'appABCDEFGHIJ1234', 'table': 'Indicateurs', 'enregistrement': 'recABCDEFGHIJ1234', 'champ': 'Total'}, {'jeton': 'pat'}, 42),
}
verif('12 connecteurs au catalogue', len(K.CATALOGUE) == 12 and set(CAS) == set(K.PAR_CODE))
for code, (p, s, attendu) in CAS.items():
    APPELS.clear()
    try:
        v = K.appel(code, p, s); err = ''
    except K.ErreurConnecteur as e:
        v, err = None, str(e)
    a = APPELS[-1] if APPELS else {}
    verif(f'{code} : valeur lue = {attendu}', v == attendu, f'{v} {err}')
    verif(f'{code} : https, sans redirection, délai max', a.get('url', '').startswith('https://') and a.get('allow_redirects') is False and a.get('timeout') == 15)
a = {}
for code, test in (
        ('jira', lambda a: a['methode'] == 'POST' and a['url'] == 'https://monentreprise.atlassian.net/rest/api/3/search/approximate-count'
         and a['json'] == {'jql': 'project = SEC AND statusCategory != Done'} and a['auth'] == ('ci@m.fr', 'tok')),
        ('servicenow', lambda a: a['url'].endswith('monentreprise.service-now.com/api/now/stats/incident') and a['params']['sysparm_count'] == 'true'),
        ('zendesk', lambda a: a['auth'] == ('a@m.fr/token', 'tok')),
        ('freshdesk', lambda a: a['params']['query'] == '"status:2 AND priority:4"' and a['auth'] == ('key', 'X')),
        ('github', lambda a: a['headers']['Authorization'] == 'Bearer ghp' and a['headers']['X-GitHub-Api-Version'] == '2022-11-28'),
        ('gitlab', lambda a: a['url'] == 'https://gitlab.com/api/v4/projects/monorg%2Fappli/issues_statistics' and a['headers']['PRIVATE-TOKEN'] == 'glpat'),
        ('hubspot', lambda a: a['methode'] == 'POST' and a['json']['filterGroups'][0]['filters'][0] == {'propertyName': 'hs_pipeline_stage', 'operator': 'EQ', 'value': '1'}),
        ('odoo', lambda a: a['url'] == 'https://monentreprise.odoo.com/json/2/account.move/search_count' and a['headers']['X-Odoo-Database'] == 'monentreprise'
         and a['json'] == {'domain': [['payment_state', '=', 'not_paid']]}),
        ('pagerduty', lambda a: a['url'] == 'https://api.eu.pagerduty.com/incidents' and a['params']['total'] == 'true'
         and a['headers']['Authorization'] == 'Token token=pd' and a['params']['statuses[]'] == ['triggered', 'acknowledged']),
        ('datadog', lambda a: a['url'] == 'https://api.datadoghq.eu/api/v1/query' and a['headers']['DD-APPLICATION-KEY'] == 'app'
         and a['params']['to'] - a['params']['from'] == 3600),
        ('google_sheets', lambda a: a['url'].endswith('/spreadsheets/1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789/values/KRI%21B2') and a['params']['key'] == 'AIza'),
        ('airtable', lambda a: a['url'] == 'https://api.airtable.com/v0/appABCDEFGHIJ1234/Indicateurs/recABCDEFGHIJ1234')):
    APPELS.clear(); p, s, _ = CAS[code]; K.appel(code, p, s)
    try:
        ok = test(APPELS[-1])
    except Exception as e:  # noqa: BLE001
        ok = False
    verif(f'{code} : requête conforme à la documentation', ok, str({k: v for k, v in APPELS[-1].items() if k not in ('auth',)})[:150] if not ok else '')

# ---------------------------------------------------------------- 2. erreurs et sécurité
def message(code, p, s):
    try:
        K.appel(code, p, s); return ''
    except K.ErreurConnecteur as e:
        return str(e)
FORCER['atlassian.net'] = (401, {'errorMessages': ['x']})
verif('401 : « identifiants refusés »', 'identifiants refusés' in message('jira', *CAS['jira'][:2]))
FORCER['atlassian.net'] = (400, {'errorMessages': ["Erreur dans la requête JQL : le champ « foo » n'existe pas."]})
m = message('jira', *CAS['jira'][:2]); verif('400 : message de l\'outil relayé', 'requête refusée' in m and 'foo' in m, m[:120])
FORCER['atlassian.net'] = ('timeout', None)
verif('délai dépassé : message clair', 'n\'a pas répondu' in message('jira', *CAS['jira'][:2]))
FORCER.clear()
verif('sous-domaine piégé refusé', 'invalide' in message('jira', dict(CAS['jira'][0], site='evil.com/x?'), {'jeton': 't'}))
verif('GitLab sur adresse IP interne refusé', 'invalide' in message('gitlab', dict(CAS['gitlab'][0], adresse='10.0.0.5'), {'jeton': 't'}))
verif('Odoo sur localhost refusé', 'invalide' in message('odoo', dict(CAS['odoo'][0], adresse='localhost'), {'jeton': 't'}))
verif('jeton manquant : message', 'obligatoire' in message('github', CAS['github'][0], {}))
verif('filtre Odoo invalide : message', 'filtre Odoo invalide' in message('odoo', dict(CAS['odoo'][0], domaine='pas du json'), {'jeton': 'k'}))
REPONSES['sheets.googleapis.com'] = {'values': [['Bonjour']]}
verif('valeur non numérique : message', "n'est pas un nombre" in message('google_sheets', *CAS['google_sheets'][:2]))
REPONSES['sheets.googleapis.com'] = {'range': 'KRI!B2', 'values': [['12,5 %']]}
verif('nombres français lus', K.nombre('1 234,5') == 1234.5 and K.nombre('12,5 %') == 12.5 and K.nombre(7) == 7)

# ---------------------------------------------------------------- 3. pages, droits, enregistrement, relevé
with A.app.app_context():
    cid = db.session.get(M.User, ids['admin_a']).client_id
    k = M.KRI(nom='Vulnérabilités critiques ouvertes', client_id=cid, type_indicateur='kri', seuil_alerte=5, seuil_critique=10,
              frequence_mesure='quotidien', unite_mesure='tickets')
    db.session.add(k); db.session.commit(); kid = k.id
adm = socle.navigateur(A, ids['admin_a'])
r = adm.get(f'/kri/{kid}/detail'); t = r.get_data(as_text=True)
verif('fiche KRI (admin) : bouton « Connecter un outil »', r.status_code == 200 and 'Connecter un outil' in t, f'{r.status_code} {socle.cause(A)}')
g = socle.navigateur(A, ids['gestionnaire'])
t = g.get(f'/kri/{kid}/detail').get_data(as_text=True)
verif('fiche KRI (gestionnaire) : pas de bouton, message', 'Connecter un outil' not in t and "administrateur de votre organisation" in t)
verif('gestionnaire : page des connecteurs refusée', g.get(f'/kri/{kid}/connecteur').status_code == 404)
verif('autre organisation : refusée', socle.navigateur(A, ids['admin_b']).get(f'/kri/{kid}/connecteur').status_code == 404)
r = adm.get(f'/kri/{kid}/connecteur'); t = r.get_data(as_text=True)
verif('page des connecteurs : 12 outils', r.status_code == 200 and t.count('class="cx-outil"') == 12, f'{r.status_code} {socle.cause(A)}')
for code in K.PAR_CODE:
    r = adm.get(f'/kri/{kid}/connecteur?outil={code}')
    if r.status_code != 200:
        verif(f'formulaire {code}', False, f'{r.status_code} {socle.cause(A)}')
verif('12 formulaires affichés', all(adm.get(f'/kri/{kid}/connecteur?outil={c_}').status_code == 200 for c_ in K.PAR_CODE))
p, s, _ = CAS['jira']
form = dict(p, outil='jira', jeton='secret-jira-123', frequence='86400')
r = adm.post(f'/kri/{kid}/connecteur', data=dict(form, action='tester')); t = r.get_data(as_text=True)
verif('Tester : valeur affichée, rien enregistré', 'Connexion réussie' in t and '>7 ' in t)
with A.app.app_context():
    verif('Tester : aucune source créée', M.SourceDonnee.query.filter(M.SourceDonnee.nom.like('Jira%')).count() == 0)
r = adm.post(f'/kri/{kid}/connecteur', data=dict(form, action='enregistrer'), follow_redirects=True); t = r.get_data(as_text=True)
verif('Enregistrer : connecté et première mesure', r.status_code == 200 and 'première mesure enregistrée (7)' in t, f'{r.status_code} {socle.cause(A)}')
with A.app.app_context():
    src = M.SourceDonnee.query.filter(M.SourceDonnee.nom.like('Jira%')).first()
    verif('jeton chiffré en base', src is not None and 'secret-jira-123' not in json.dumps(src.auth_config) and src.auth_config.get('jeton_chiffre'))
    verif('mesure enregistrée sur le KRI', [m.valeur for m in M.MesureKRI.query.filter_by(kri_id=kid)] == [7.0])
    sid = src.id; lien = M.SourceKRILink.query.filter_by(source_id=sid).first().id
    verif('jeton absent de la page', 'secret-jira-123' not in adm.get(f'/kri/{kid}/connecteur').get_data(as_text=True))
# relevé automatique : échéance passée → relevé une fois, pas deux
REPONSES['atlassian.net/rest/api/3/search/approximate-count'] = {'count': 11}
with A.app.app_context():
    src = db.session.get(M.SourceDonnee, sid); src.prochaine_execution = dt.datetime.utcnow() - dt.timedelta(minutes=1); db.session.commit()
n1 = K.relever_echeances(A.app); n2 = K.relever_echeances(A.app)
with A.app.app_context():
    vals = sorted(m.valeur for m in M.MesureKRI.query.filter_by(kri_id=kid))
verif('relevé automatique : source échue relevée une seule fois', n1 >= 1 and n2 == 0 and vals == [7.0, 11.0], f'{n1} {n2} {vals}')
FORCER['atlassian.net'] = (401, {})
r = adm.post(f'/kri/{kid}/connecteur/{lien}', data={'action': 'collecter'}, follow_redirects=True); t = r.get_data(as_text=True)
verif('Relever maintenant : erreur claire (jeton révoqué)', 'identifiants refusés' in t, socle.cause(A))
FORCER.clear()
r = adm.post(f'/kri/{kid}/connecteur/{lien}', data={'action': 'collecter'}, follow_redirects=True)
verif('Relever maintenant : OK', 'Mesure relevée : 11' in r.get_data(as_text=True))
verif('autre organisation : ne peut pas relever', socle.navigateur(A, ids['admin_b']).post(f'/kri/{kid}/connecteur/{lien}', data={'action': 'collecter'}).status_code == 404)
t = adm.get(f'/kri/{kid}/detail').get_data(as_text=True)
verif('fiche KRI : connexion Jira affichée', 'Collecte automatique' in t and '>Jira<' in t and f'/kri/{kid}/connecteur' in t, socle.cause(A))
r = adm.post(f'/kri/{kid}/connecteur/{lien}', data={'action': 'supprimer'}, follow_redirects=True)
with A.app.app_context():
    verif('Supprimer : connexion retirée, mesures conservées', db.session.get(M.SourceDonnee, sid) is None
          and M.MesureKRI.query.filter_by(kri_id=kid).count() >= 2)
verif('sources génériques toujours réservées au super-admin', adm.get('/kri/sources').status_code == 403)
print(f'\n{sum(res)}/{len(res)}')
