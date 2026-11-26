"""Recette : l'assistant répond aux questions sur les données (couverture d'audit, recommandations filtrées, indicateurs),
sans IA (moteur local) et avec l'IA (outils), sous l'interrupteur du super admin. Faux fournisseur : aucun appel réseau."""
import json
import os
import re
from datetime import date, timedelta
from types import SimpleNamespace as NS

os.environ['EGALYX_COLLECTE_AUTO'] = '0'
os.environ.pop('ASSISTANT_IA_EXTERNE', None)
import socle
from socle import Muet, appel
os.environ['OPENAI_API_KEY'] = 'sk-recette' + 'x' * 40
os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-recette-' + 'z' * 30
with Muet():
    A, ids = socle.preparer()
import models as M
from models import db
from egalyx import ia_passerelle as P, ia as IA

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


APPELS, SCENARIO = [], {'etapes': []}


def faux(completions, *a, **kw):
    texte = json.dumps(kw.get('messages'), ensure_ascii=False)
    APPELS.append({'texte': texte, 'outils': [t['function']['name'] for t in kw.get('tools') or []]})
    etape = SCENARIO['etapes'].pop(0) if SCENARIO['etapes'] else {'texte': 'Fin.'}
    if 'outil' in etape:
        tc = NS(id='appel1', type='function', function=NS(name=etape['outil'], arguments=json.dumps(etape['args'])))
        return NS(choices=[NS(message=NS(content=None, tool_calls=[tc]))])
    jeton = re.search(r'\[PERSONNE_\d+\]', texte)
    return NS(choices=[NS(message=NS(content=etape['texte'].replace('{personne}', jeton.group(0) if jeton else '?'), tool_calls=None))])


P.installer(); P._etat['origine'] = faux


def csrf(c):
    r = appel(c, 'get', '/dashboard')
    m = re.search(r'name="csrf-token" content="([^"]+)"', r.data.decode(errors='ignore'))
    return m.group(1) if m else ''


def demander(c, q):
    r = appel(c, 'post', '/assistant/message', json={'message': q}, headers={'X-CSRFToken': csrf(c), 'Accept': 'application/json'})
    return r.get_json() or {}


def jeton_form(c, url):
    m = re.search(r'name="csrf_token" value="([^"]+)"', appel(c, 'get', url).data.decode(errors='ignore'))
    return m.group(1) if m else ''


sa, admin, gest, lect, admin_b = (socle.navigateur(A, ids[r]) for r in ('superadmin', 'admin_a', 'gestionnaire', 'lecteur', 'admin_b'))
with A.app.app_context():
    IA.ecrire_reglage('ia_active', True); IA.ecrire_reglage('ia_fournisseur', 'openai'); IA.ecrire_reglage('ia_masquage', True)
    IA.ecrire_reglage('ia_fonctions', {'assistant_donnees': False})
    auj = date.today()
    dcr = socle.creer(M.Direction, nom='Direction des crédits', client_id=1)
    dfi = socle.creer(M.Direction, nom='Direction financière', client_id=1)
    db.session.flush()
    g = db.session.get(M.User, ids['gestionnaire']); g.direction_id = dcr.id; g.prenom, g.nom = 'Awa', 'Koné'
    v = db.session.get(M.User, ids['validateur']); v.direction_id = dfi.id
    a = socle.creer(M.Audit, reference='AUD-AS', titre='Audit des crédits', type_audit='interne', client_id=1, statut='termine')
    db.session.flush()
    def reco(ref, score, jours, resp):
        r = socle.creer(M.Recommandation, reference=ref, description=f'Recommandation {ref}', urgence=3, impact_operationnel=3,
                        audit_id=a.id, client_id=1, statut='en_cours', responsable_id=resp, date_echeance=auj + timedelta(days=jours))
        r.score_priorite = score
    reco('REC-CRIT-RETARD', 90, -10, ids['gestionnaire'])
    reco('REC-CRIT-AVENIR', 85, 30, ids['validateur'])
    reco('REC-BASSE-RETARD', 20, -5, ids['validateur'])
    for nom, niv, dernier in (('Octroi de crédit', 'eleve', None), ('Trésorerie', 'eleve', auj - timedelta(days=100)),
                              ('Moyens généraux', 'faible', None)):
        socle.creer(M.EntiteAuditable, nom=nom, client_id=1, niveau_risque=niv, actif=True, dernier_audit_manuel=dernier, type_entite='processus')
    socle.creer(M.Recommandation, reference='REC-B', description='Reco de B', urgence=3, impact_operationnel=3, audit_id=a.id, client_id=2,
                statut='en_cours', date_echeance=auj - timedelta(days=3)).score_priorite = 95
    db.session.commit()

print('--- Outils donnés à l’IA')
import importlib, sys
appli = sys.modules.get(A.app.import_name)
noms = {s['function']['name'] for s in appli.ASSISTANT_SCHEMAS}
verif('l’IA dispose de tous les outils de lecture (recommandations, constats, N2, couverture, indicateurs…)',
      {'lister_recommandations', 'lister_constatations', 'lister_nc_c2n', 'mes_taches', 'chercher_reference', 'couverture_audit',
       'indicateurs_audit'} <= noms and len(noms) >= 20, len(noms))
verif('chaque outil déclaré existe vraiment', all(n in appli.ASSISTANT_FONCTIONS for n in noms))

print('--- Sans IA (moteur local)')
APPELS.clear()
r = demander(gest, 'Quels processus à risque élevé n’ont jamais été audités ?')
t = json.dumps(r, ensure_ascii=False)
verif('« processus à risque élevé jamais audités » : réponse sans IA', r.get('intention') == 'couverture_audit' and 'Octroi de crédit' in t
      and 'Trésorerie' not in t and 'Moyens généraux' not in t and not APPELS, (r.get('intention'), r.get('texte')))
r = demander(gest, 'Quelles recommandations critiques sont en retard ?')
t = json.dumps(r, ensure_ascii=False)
verif('« recommandations critiques en retard » : seulement critiques ET échues', 'REC-CRIT-RETARD' in t and 'REC-CRIT-AVENIR' not in t
      and 'REC-BASSE-RETARD' not in t and 'REC-B' not in t.replace('REC-BASSE', ''), r.get('texte'))
r = demander(gest, 'Quelles recommandations de la direction des crédits sont en cours ?')
t = json.dumps(r, ensure_ascii=False)
verif('« recommandations de la direction des crédits » : filtrées par la direction du responsable', 'REC-CRIT-RETARD' in t
      and 'REC-CRIT-AVENIR' not in t and 'REC-BASSE-RETARD' not in t, r.get('texte'))
r = demander(gest, f'Indicateurs de l’audit {date.today().year}')
t = json.dumps(r, ensure_ascii=False)
verif('« indicateurs de l’audit » : programme, recommandations mises en œuvre, couverture', r.get('intention') == 'indicateurs_audit'
      and 'Programme' in t and 'mises en œuvre' in t and 'Couverture' in t, r.get('intention'))
r = demander(lect, 'Quelles recommandations critiques sont en retard ?')
t = json.dumps(r, ensure_ascii=False)
verif('utilisateur sans droit sur l’audit : pas de données', 'REC-CRIT-RETARD' not in t, r.get('texte'))
r = demander(admin_b, 'Quelles recommandations critiques sont en retard ?')
t = json.dumps(r, ensure_ascii=False)
verif('autre organisation : ne voit que ses recommandations', 'REC-CRIT-RETARD' not in t and 'REC-B' in t, r.get('texte'))

print('--- Avec l’IA (outils)')
QUESTION = 'Rédige deux lignes sur ce qui bloque chez nous en ce moment, côté suivi.'
APPELS.clear()
r = demander(gest, QUESTION)
verif('fonction « Assistant : réponses avec l’IA » coupée : aucun appel à l’IA', not APPELS and r.get('intention') != 'ia_externe', r.get('intention'))
appel(sa, 'post', '/super-admin/ia/', data={'csrf_token': jeton_form(sa, '/super-admin/ia/'), 'action': 'fonctions', 'f_assistant_donnees': '1',
                                           'f_redaction_constats': '1', 'f_premier_jet_rapport': '1', 'f_preparation_mission': '1'})
APPELS.clear(); demander(gest, QUESTION)
verif('fonction activée mais utilisateur sans la permission « Utiliser l’analyse IA » : aucun appel', not APPELS)
with A.app.app_context():
    g = db.session.get(M.User, ids['gestionnaire']); g.permissions = {**(g.permissions or {}), 'can_use_ia_analysis': True}; db.session.commit()
SCENARIO['etapes'] = [{'outil': 'lister_recommandations', 'args': {'priorite': 'critique', 'en_retard_seulement': True}},
                      {'texte': 'Une recommandation critique est en retard (REC-CRIT-RETARD), suivie par {personne}.'}]
APPELS.clear()
r = demander(gest, QUESTION)
verif('fonction activée : l’IA répond', r.get('intention') == 'ia_externe' and len(APPELS) == 2, (r.get('intention'), len(APPELS)))
verif('… les nouveaux outils lui sont proposés', APPELS and 'couverture_audit' in APPELS[0]['outils'] and 'lister_recommandations' in APPELS[0]['outils'])
verif('… l’outil a lu les données de l’organisation (et elles seules)', len(APPELS) > 1 and 'REC-CRIT-RETARD' in APPELS[1]['texte']
      and 'REC-B"' not in APPELS[1]['texte'] and 'Reco de B' not in APPELS[1]['texte'])
verif('… nom du responsable masqué avant l’envoi, remis en clair dans la réponse', len(APPELS) > 1 and 'Koné' not in APPELS[1]['texte']
      and 'Awa' in r.get('texte', '') and 'Koné' in r.get('texte', ''), r.get('texte'))
CORPS = []
def faux_anthropic(corps):
    CORPS.append(corps)
    if len(CORPS) == 1:
        return {'stop_reason': 'tool_use', 'content': [{'type': 'tool_use', 'id': 'u1', 'name': 'couverture_audit', 'input': {'niveau_min': 'eleve'}}]}
    res = json.dumps(corps['messages'][-1]['content'], ensure_ascii=False)
    return {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': 'Processus à risque élevé jamais audité : Octroi de crédit.' if 'Octroi' in res else 'Rien.'}]}
P._etat['anthropic'] = faux_anthropic
appel(sa, 'post', '/super-admin/ia/', data={'csrf_token': jeton_form(sa, '/super-admin/ia/'), 'action': 'fournisseur', 'fournisseur': 'anthropic'})
r = demander(gest, QUESTION)
verif('assistant avec Claude : appelle un outil (format Anthropic), lit les données, répond', r.get('intention') == 'ia_externe' and len(CORPS) == 2
      and any(t['name'] == 'couverture_audit' for t in CORPS[0].get('tools', [])) and CORPS[1]['messages'][-1]['content'][0]['type'] == 'tool_result'
      and 'Octroi de crédit' in r.get('texte', ''), (r.get('intention'), len(CORPS), r.get('texte')))
appel(sa, 'post', '/super-admin/ia/', data={'csrf_token': jeton_form(sa, '/super-admin/ia/'), 'action': 'fournisseur', 'fournisseur': 'openai'})
appel(sa, 'post', '/super-admin/ia/', data={'csrf_token': jeton_form(sa, '/super-admin/ia/'), 'ia_active': '0'})
APPELS.clear(); demander(gest, QUESTION)
verif('interrupteur général coupé : aucun appel à l’IA', not APPELS)
appel(sa, 'post', '/super-admin/ia/', data={'csrf_token': jeton_form(sa, '/super-admin/ia/'), 'ia_active': '1'})
r = appel(sa, 'get', '/super-admin/ia/')
verif('page du super admin : interrupteur « Assistant : réponses avec l’IA »', 'Assistant : réponses avec l’IA'.encode() in r.data)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
