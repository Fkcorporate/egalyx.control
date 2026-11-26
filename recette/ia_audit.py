"""Recette : IA au cœur de l'audit (étape 1) — passerelle (fournisseur, masquage, journal), interrupteurs du super admin,
rédaction des constats depuis les notes, premier jet du rapport. Un faux fournisseur remplace l'appel réseau."""
import io
import json
import os
import re
from types import SimpleNamespace as NS

os.environ['EGALYX_COLLECTE_AUTO'] = '0'
os.environ['OPENAI_API_KEY'] = 'sk-recette' + 'x' * 40
os.environ['MISTRAL_API_KEY'] = 'mistral-recette-' + 'y' * 30
os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-recette-' + 'z' * 30
os.environ['DEEPSEEK_API_KEY'] = 'sk-deepseek-' + 'w' * 30
import socle
from socle import Muet, appel
os.environ['OPENAI_API_KEY'] = 'sk-recette' + 'x' * 40     # socle retire la clé : on remet une clé de test (faux fournisseur)
with Muet():
    A, ids = socle.preparer()
import models as M
from models import db
from egalyx import ia_passerelle as P, ia as IA

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


# ---------------------------------------------------------------- faux fournisseur
APPELS, REPONSE = [], {'contenu': '{}', 'erreur': None}


def faux(completions, *a, **kw):
    APPELS.append({'base': str(completions._client.base_url), 'cle': completions._client.api_key, 'kw': kw,
                   'texte': json.dumps(kw.get('messages'), ensure_ascii=False)})
    if REPONSE['erreur']:
        raise RuntimeError(REPONSE['erreur'])
    return NS(choices=[NS(message=NS(content=REPONSE['contenu'], tool_calls=None))])


verif('passerelle installée devant la bibliothèque openai', P.installer())
P._etat['origine'] = faux


def jeton(c, url):
    r = appel(c, 'get', url)
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.data.decode(errors='ignore')) or \
        re.search(r'name="csrf-token" content="([^"]+)"', r.data.decode(errors='ignore'))
    return m.group(1) if m else ''


sa, admin, gest, lect, admin_b = (socle.navigateur(A, ids[r]) for r in ('superadmin', 'admin_a', 'gestionnaire', 'lecteur', 'admin_b'))
with A.app.app_context():
    IA.ecrire_reglage('ia_active', True); IA.ecrire_reglage('ia_fournisseur', 'openai'); IA.ecrire_reglage('ia_masquage', True)
    IA.ecrire_reglage('ia_fonctions', {})
    g = db.session.get(M.User, ids['gestionnaire']); g.prenom, g.nom = 'Awa', 'Koné'
    a = socle.creer(M.Audit, reference='AUD-IA', titre='Audit des achats', type_audit='interne', client_id=1, statut='en_cours',
                    responsable_id=ids['gestionnaire'], objectifs='Vérifier la maîtrise des engagements de dépenses.')
    for i, gr in enumerate(('majeure', 'moyenne'), 1):
        socle.creer(M.Constatation, reference=f'CST-{i}', description=f'Constat {i} sur les bons de commande.', gravite=gr, audit_id=a.id, client_id=1)
    socle.creer(M.Recommandation, reference='REC-1', description='Formaliser les délégations.', urgence=3, impact_operationnel=3, audit_id=a.id, client_id=1)
    db.session.commit()
    AID = a.id
JS = {'Accept': 'application/json'}
NOTES = ("Selon M. Traoré, caissier, Awa Koné a validé 12 bons de commande sur 40 sans délégation (Banque Recette), "
         "montants > 5 000 000 FCFA ; compte 0123456789012 ; contact traore@banque.ci, +225 07 08 09 10 11.")


def proposer_constat(c, notes=NOTES):
    return appel(c, 'post', f'/audit-ia/audit/{AID}/constat/proposer', json={'notes': notes},
                 headers={'X-CSRFToken': jeton(c, f'/audit/{AID}'), **JS})


print('--- Interrupteurs')
r = appel(gest, 'get', f'/audit/{AID}')
verif('sans la permission « Utiliser l’analyse IA » : pas de panneau de notes', r.status_code == 200 and b'iaNotesTexte' not in r.data, r.status_code)
verif('… et proposition refusée', proposer_constat(gest).status_code == 403)
with A.app.app_context():
    g = db.session.get(M.User, ids['gestionnaire']); g.permissions = {**(g.permissions or {}), 'can_use_ia_analysis': True}; db.session.commit()
r = appel(gest, 'get', f'/audit/{AID}')
verif('avec la permission : panneau « Rédiger à partir de mes notes » + champs critère / conséquence', b'iaNotesTexte' in r.data
      and b'name="critere"' in r.data and b'name="consequence"' in r.data)
verif('lien « Rédaction du rapport » sur la fiche de l’audit', f'/audit-ia/audit/{AID}/redaction'.encode() in r.data)
r = appel(sa, 'get', '/super-admin/ia/')
verif('page du super admin : fonctions, fournisseur, confidentialité, journal', r.status_code == 200 and all(x in r.data for x in (
    'Rédaction des constats'.encode(), b'Mistral AI', b'Masquage', 'Derniers appels'.encode())), r.status_code)
r = appel(sa, 'post', '/super-admin/ia/', data={'csrf_token': jeton(sa, '/super-admin/ia/'), 'action': 'fonctions', 'f_premier_jet_rapport': '1'})
verif('super admin coupe « Rédaction des constats »', proposer_constat(gest).status_code == 403
      and b'iaNotesTexte' not in appel(gest, 'get', f'/audit/{AID}').data)
r = appel(sa, 'post', '/super-admin/ia/', data={'csrf_token': jeton(sa, '/super-admin/ia/'), 'action': 'fonctions',
                                                'f_premier_jet_rapport': '1', 'f_redaction_constats': '1'})
appel(sa, 'post', '/super-admin/ia/', data={'csrf_token': jeton(sa, '/super-admin/ia/'), 'ia_active': '0'})
verif('interrupteur général coupé : tout est refusé', proposer_constat(gest).status_code == 403)
appel(sa, 'post', '/super-admin/ia/', data={'csrf_token': jeton(sa, '/super-admin/ia/'), 'ia_active': '1'})

print('--- Rédaction d’un constat (OpenAI, masquage)')
REPONSE['contenu'] = json.dumps({'titre': 'Engagements sans délégation', 'fait': '[PERSONNE_1] signale que [PERSONNE_2] a validé 12 bons sur 40.',
                                 'critere': 'À confirmer : procédure achats', 'cause': 'Absence de matrice', 'consequence': 'Engagements non autorisés',
                                 'recommandation': 'Mettre à jour la matrice des délégations', 'gravite': 'Majeure', 'type': 'non-conformité',
                                 'points_a_verifier': ['Confirmer le nombre de bons']})
APPELS.clear()
r = proposer_constat(gest)
j = r.get_json() or {}
c = j.get('constat') or {}
verif('proposition faite par l’IA', r.status_code == 200 and j.get('origine') == 'ia', (r.status_code, j.get('origine')))
envoye = APPELS[-1]['texte'] if APPELS else ''
verif('envoyé à OpenAI (api.openai.com)', APPELS and 'api.openai.com' in APPELS[-1]['base'])
verif('masquage : ni nom, ni e-mail, ni téléphone, ni compte, ni organisation envoyés', all(x not in envoye for x in (
    'Traoré', 'Koné', 'traore@banque.ci', '07 08 09 10 11', '0123456789012', 'Banque Recette')) and '[PERSONNE_1]' in envoye, envoye[:160])
verif('… montants et chiffres gardés pour l’analyse', '5 000 000' in envoye and '12 bons' in envoye)
verif('réponse remise en clair (vrais noms)', 'Traoré' in c.get('fait', '') and 'Koné' in c.get('fait', ''), c.get('fait'))
verif('gravité et type normalisés pour le formulaire', c.get('gravite') == 'majeure' and c.get('type') == 'non_conformite', (c.get('gravite'), c.get('type')))
with A.app.app_context():
    ja = M.JournalActiviteClient.query.filter_by(action='ia_appel').order_by(M.JournalActiviteClient.id.desc()).first()
    verif('journal : fournisseur, modèle, données masquées, fonction — sans le contenu', ja and ja.details.get('fournisseur') == 'openai'
          and ja.details.get('donnees_masquees', 0) >= 5 and 'Traoré' not in json.dumps(ja.details, ensure_ascii=False), ja.details if ja else None)

print('--- Fournisseur européen (Mistral) et anciennes fonctions')
appel(sa, 'post', '/super-admin/ia/', data={'csrf_token': jeton(sa, '/super-admin/ia/'), 'action': 'fournisseur', 'fournisseur': 'mistral'})
APPELS.clear()
r = proposer_constat(gest)
kw = APPELS[-1]['kw'] if APPELS else {}
verif('super admin choisit Mistral : envoi vers api.eu.mistral.ai', APPELS and 'api.eu.mistral.ai' in APPELS[-1]['base']
      and APPELS[-1]['cle'] == os.environ['MISTRAL_API_KEY'], APPELS[-1]['base'] if APPELS else None)
verif('… modèle Mistral, paramètres traduits', kw.get('model') == 'mistral-medium-latest' and 'max_completion_tokens' not in kw and kw.get('max_tokens'))
with A.app.test_request_context():
    from flask_login import login_user
    login_user(db.session.get(M.User, ids['gestionnaire']))
    from openai import OpenAI
    APPELS.clear()
    rep = OpenAI(api_key=os.environ['OPENAI_API_KEY']).chat.completions.create(
        model='gpt-4o-mini', messages=[{'role': 'user', 'content': 'Analyse : M. Traoré a validé le dossier.'}])
    verif('ancienne fonction (client openai direct) : passe aussi par Mistral, masquée', APPELS and 'api.eu.mistral.ai' in APPELS[-1]['base']
          and 'Traoré' not in APPELS[-1]['texte'])
print('--- Anthropic (Claude) et DeepSeek')
CORPS = []
def faux_anthropic(corps):
    CORPS.append(corps)
    return {'id': 'm1', 'model': corps['model'], 'stop_reason': 'end_turn', 'usage': {'input_tokens': 1, 'output_tokens': 1},
            'content': [{'type': 'thinking', 'thinking': ''}, {'type': 'text', 'text': '```json\n' + REPONSE['contenu'] + '\n```'}]}
P._etat['anthropic'] = faux_anthropic
appel(sa, 'post', '/super-admin/ia/', data={'csrf_token': jeton(sa, '/super-admin/ia/'), 'action': 'fournisseur', 'fournisseur': 'anthropic'})
APPELS.clear()
r = proposer_constat(gest)
j = r.get_json() or {}
co = CORPS[-1] if CORPS else {}
verif('Claude : constat proposé par l’IA (JSON extrait du bloc de code)', j.get('origine') == 'ia' and 'Traoré' in (j.get('constat') or {}).get('fait', ''), j.get('origine'))
verif('… API native d’Anthropic (aucun appel OpenAI), modèle Claude, consigne JSON, marge de réflexion', not APPELS and co.get('model') == 'claude-sonnet-5-5'
      and 'JSON' in co.get('system', '') and co.get('max_tokens', 0) >= 1200 + P.ANTHROPIC_MARGE_REFLEXION, co.get('model'))
verif('… données masquées avant l’envoi à Claude', co and 'Traoré' not in json.dumps(co, ensure_ascii=False) and '[PERSONNE_' in json.dumps(co, ensure_ascii=False))
r = appel(sa, 'post', '/super-admin/ia/', data={'csrf_token': jeton(sa, '/super-admin/ia/'), 'action': 'fournisseur', 'fournisseur': 'deepseek'})
APPELS.clear()
proposer_constat(gest)
verif('DeepSeek choisi : envoi vers api.deepseek.com, modèle deepseek-flash', APPELS and 'api.deepseek.com' in APPELS[-1]['base']
      and APPELS[-1]['kw'].get('model') == 'deepseek-flash' and APPELS[-1]['cle'] == os.environ['DEEPSEEK_API_KEY'], APPELS[-1]['base'] if APPELS else None)
r = appel(sa, 'get', '/super-admin/ia/')
verif('page du super admin : 4 fournisseurs, avertissement DeepSeek (données en Chine)', all(x.encode() in r.data for x in (
    'OpenAI', 'Anthropic (Claude)', 'Mistral AI', 'DeepSeek', 'stocke les données en Chine')))
appel(sa, 'post', '/super-admin/ia/', data={'csrf_token': jeton(sa, '/super-admin/ia/'), 'action': 'fournisseur', 'fournisseur': 'mistral'})
appel(sa, 'post', '/super-admin/ia/', data={'csrf_token': jeton(sa, '/super-admin/ia/'), 'action': 'masquage', 'ia_masquage': '0'})
APPELS.clear(); proposer_constat(gest)
verif('masquage coupé par le super admin : données envoyées telles quelles', APPELS and 'Traoré' in APPELS[-1]['texte'])
appel(sa, 'post', '/super-admin/ia/', data={'csrf_token': jeton(sa, '/super-admin/ia/'), 'action': 'masquage', 'ia_masquage': '1'})

print('--- Sans IA (panne du fournisseur)')
REPONSE['erreur'] = 'réseau coupé'
r = proposer_constat(gest)
j = r.get_json() or {}
verif('proposition automatique annoncée comme telle, notes reprises dans le fait', j.get('origine') == 'automatique'
      and 'Traoré' in (j.get('constat') or {}).get('fait', '') and 'sans IA' in j.get('origine_libelle', ''), j.get('origine'))
REPONSE['erreur'] = None

print('--- Création du constat (5 C)')
t = jeton(gest, f'/audit/{AID}')
r = appel(gest, 'post', f'/audit/{AID}/constatation/ajouter', data={'csrf_token': t, 'description': 'Fait relu', 'type_constatation': 'non_conformite',
          'gravite': 'majeure', 'critere': 'Procédure achats §4.2', 'consequence': 'Engagements non autorisés', 'cause_racine': 'Matrice absente',
          'recommandations_immediates': 'Mettre à jour la matrice'})
with A.app.app_context():
    cst = M.Constatation.query.filter_by(audit_id=AID, description='Fait relu').first()
    verif('critère et conséquence enregistrés avec le constat', cst is not None and cst.critere == 'Procédure achats §4.2'
          and cst.consequence == 'Engagements non autorisés' and cst.recommandations_immediates == 'Mettre à jour la matrice')

print('--- Premier jet du rapport')
REPONSE['contenu'] = json.dumps({'resume': 'RÉSUMÉ-IA : la mission a relevé 3 constats dont 1 majeur (CST-1).',
                                 'conclusion': 'CONCLUSION-IA : dispositif à améliorer.', 'opinion': 'a_ameliorer'})
r = appel(gest, 'get', f'/audit-ia/audit/{AID}/redaction')
verif('page de rédaction', r.status_code == 200 and b'Proposer un premier jet' in r.data and 'Pas encore rédigé'.encode() in r.data, r.status_code)
APPELS.clear()
r = appel(gest, 'post', f'/audit-ia/audit/{AID}/redaction/proposer', headers={'X-CSRFToken': jeton(gest, f'/audit-ia/audit/{AID}/redaction'), **JS})
j = r.get_json() or {}
verif('premier jet proposé par l’IA', j.get('origine') == 'ia' and j.get('resume', '').startswith('RÉSUMÉ-IA'), j.get('origine'))
verif('… à partir des constats et recommandations de la mission', APPELS and 'CST-1' in APPELS[-1]['texte'] and 'REC-1' in APPELS[-1]['texte'])
t = jeton(gest, f'/audit-ia/audit/{AID}/redaction')
appel(gest, 'post', f'/audit-ia/audit/{AID}/redaction', data={'csrf_token': t, 'action': 'brouillon', 'resume': j['resume'], 'conclusion': j['conclusion'], 'ia': '1'})
from docx import Document


def word():
    r = appel(gest, 'get', f'/audit/{AID}/rapport-word-pro')
    return '\n'.join(p.text for p in Document(io.BytesIO(r.data)).paragraphs) if r.status_code == 200 else ''


verif('brouillon : absent du rapport Word', 'RÉSUMÉ-IA' not in word())
t = jeton(gest, f'/audit-ia/audit/{AID}/redaction')
appel(gest, 'post', f'/audit-ia/audit/{AID}/redaction', data={'csrf_token': t, 'action': 'valider', 'resume': j['resume'] + ' (relu)',
                                                            'conclusion': j['conclusion'], 'ia': '1'})
w = word()
verif('validé : résumé et conclusion dans le rapport Word', 'RÉSUMÉ-IA' in w and '(relu)' in w and 'CONCLUSION-IA' in w)
r = appel(gest, 'get', f'/audit/{AID}/rapport-pdf-elegant')
if r.status_code == 200 and r.data[:4] == b'%PDF':
    import pypdf
    txt = ' '.join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(r.data)).pages)
    verif('validé : résumé et conclusion dans le PDF élégant', 'RÉSUMÉ-IA' in txt and 'CONCLUSION-IA' in txt)
r = appel(gest, 'get', f'/audit-ia/audit/{AID}/redaction')
verif('page : état « Validé », premier jet IA relu', 'Validé'.encode() in r.data and 'proposé par l’IA'.encode() in r.data)
t = jeton(gest, f'/audit-ia/audit/{AID}/redaction')
appel(gest, 'post', f'/audit-ia/audit/{AID}/redaction', data={'csrf_token': t, 'action': 'retirer'})
verif('validation retirée : de nouveau absent du rapport', 'RÉSUMÉ-IA' not in word())
t = jeton(gest, f'/audit-ia/audit/{AID}/redaction')
r = appel(gest, 'post', f'/audit-ia/audit/{AID}/redaction', data={'csrf_token': t, 'action': 'valider', 'resume': '', 'conclusion': 'x'})
with A.app.app_context():
    verif('valider un texte incomplet : refusé', db.session.get(M.Audit, AID).redaction_rapport.get('etat') == 'brouillon')

print('--- Préparation de la mission')
appel(sa, 'post', '/super-admin/ia/', data={'csrf_token': jeton(sa, '/super-admin/ia/'), 'action': 'fonctions',
                                           'f_premier_jet_rapport': '1', 'f_redaction_constats': '1', 'f_preparation_mission': '1'})
with A.app.app_context():
    au = db.session.get(M.Audit, AID); au.processus_concerne = 'Achats et approvisionnements'
    ra = socle.creer(M.Risque, reference='RQ-A', intitule='Engagement sans délégation', client_id=1, processus_concerne='Achats et approvisionnements')
    ra.dernier_niveau_risque = 'Élevé'
    rb = socle.creer(M.Risque, reference='RQ-B', intitule='Fournisseur fictif', client_id=1)
    db.session.flush()
    socle.creer(M.AuditRisque, audit_id=AID, risque_id=rb.id)
    socle.creer(M.ControleProcessus, reference='CTL-1', nom='Revue mensuelle des délégations', risque_id=ra.id, client_id=1,
                frequence='Mensuelle', is_archived=False)
    rx = socle.creer(M.Risque, reference='RQ-X', intitule='Risque d’une autre organisation', client_id=2)
    prec = socle.creer(M.Audit, reference='AUD-2024', titre='Audit achats 2024', type_audit='interne', client_id=1, statut='termine',
                       processus_concerne='Achats et approvisionnements')
    db.session.flush()
    socle.creer(M.Recommandation, reference='REC-2024-1', description='Contrôler les fournisseurs créés', urgence=3, impact_operationnel=3,
                audit_id=prec.id, client_id=1, statut='en_cours')
    db.session.commit()
    RA_ID = ra.id
r = appel(gest, 'get', f'/audit-ia/audit/{AID}/preparation')
verif('page de préparation : risques, contrôles, audits précédents retrouvés', r.status_code == 200 and b'RQ-A' in r.data and b'RQ-B' in r.data
      and b'RQ-X' not in r.data and b'Proposer le programme de travail' in r.data, r.status_code)
REPONSE['contenu'] = json.dumps({'objectifs': ['Vérifier les délégations'], 'points_attention': ['REC-2024-1 encore ouverte'],
    'documents_a_demander': ['Matrice des délégations', 'Liste des bons de commande'],
    'tests': [{'titre': 'Revue des délégations', 'risque_ref': 'RQ-A', 'controle_ref': 'CTL-1', 'objectif': 'Contrôle exécuté',
               'procedure': '1. Obtenir les revues\n2. Vérifier', 'criteres_acceptation': 'Revue signée', 'echantillon': 'Revues mensuelles',
               'taille_echantillon': '3', 'methode': 'Aléatoire', 'periode': '2026', 'pieces': ['PV de revue'], 'criticite': 'élevé', 'jours': '1,5'},
              {'titre': 'Fournisseurs', 'risque_ref': 'RQ-X', 'controle_ref': 'INVENTE', 'objectif': 'x', 'procedure': '1. y',
               'taille_echantillon': 25, 'methode': 'jugement', 'criticite': 'moyen', 'jours': 1}]})
APPELS.clear()
r = appel(gest, 'post', f'/audit-ia/audit/{AID}/preparation/proposer', headers={'X-CSRFToken': jeton(gest, f'/audit-ia/audit/{AID}/preparation'), **JS})
j = r.get_json() or {}
envoye = APPELS[-1]['texte'] if APPELS else ''
verif('programme proposé par l’IA', j.get('origine') == 'ia' and len(j.get('tests', [])) == 2, j.get('origine'))
verif('… à partir des risques, du contrôle et de la recommandation ouverte de l’audit précédent', all(x in envoye for x in ('RQ-A', 'RQ-B', 'CTL-1', 'REC-2024-1'))
      and 'RQ-X' not in envoye)
t1, t2 = (j.get('tests') or [{}, {}])[:2]
verif('valeurs normalisées (échantillon, méthode, criticité, jours)', t1.get('taille_echantillon') == 3 and t1.get('methode') == 'aleatoire'
      and t1.get('criticite') == 'eleve' and t1.get('jours') == 1.5, t1)
verif('référence de risque ou de contrôle inventée / d’une autre organisation : effacée', t2.get('risque_ref') == '' and t2.get('controle_ref') == '', t2)
r = appel(gest, 'post', f'/audit-ia/audit/{AID}/preparation/creer', json={'tests': [t1, t2], 'documents': j['documents_a_demander'], 'origine': 'ia'},
          headers={'X-CSRFToken': jeton(gest, f'/audit-ia/audit/{AID}/preparation'), **JS})
with A.app.app_context():
    fs = M.FeuilleTravail.query.filter_by(audit_id=AID).order_by(M.FeuilleTravail.id).all()
    fa = next((f for f in fs if f.risque_id == RA_ID), None)
    ta = M.TestControleFeuille.query.filter_by(feuille_travail_id=fa.id).first() if fa else None
    verif('feuilles créées : une par risque, tests transverses, documents à demander', r.status_code == 200 and len(fs) == 3
          and any(f.type_feuille == 'checklist' and 'Matrice des délégations' in (f.description or '') for f in fs), (r.status_code, len(fs)))
    verif('test créé avec procédure, pièces, échantillon, méthode, contrôle, rattaché à son risque', ta is not None and ta.taille_echantillon == 3
          and ta.methode_echantillonnage == 'aleatoire' and RA_ID in [x.id for x in ta.risques_associes] and 'PV de revue' in (ta.procedure or '')
          and ta.reference_norme == 'CTL-1' and fa.controle_id is not None)
r = appel(sa, 'post', '/super-admin/ia/', data={'csrf_token': jeton(sa, '/super-admin/ia/'), 'action': 'fonctions',
                                                'f_premier_jet_rapport': '1', 'f_redaction_constats': '1'})
APPELS.clear()
r = appel(gest, 'post', f'/audit-ia/audit/{AID}/preparation/proposer', headers={'X-CSRFToken': jeton(gest, f'/audit-ia/audit/{AID}/preparation'), **JS})
j = r.get_json() or {}
titres = [t['titre'] for t in j.get('tests', [])]
verif('fonction coupée par le super admin : aucun appel à l’IA, programme type sans IA', not APPELS and j.get('origine') == 'automatique', len(APPELS))
verif('… un test par contrôle (échantillon selon la fréquence : mensuel → 3), un test de suivi par recommandation ouverte',
      any('Revue mensuelle' in t for t in titres) and any('REC-2024-1' in t for t in titres)
      and next((t['taille_echantillon'] for t in j['tests'] if 'Revue mensuelle' in t['titre']), 0) == 3, titres)
appel(sa, 'post', '/super-admin/ia/', data={'csrf_token': jeton(sa, '/super-admin/ia/'), 'action': 'fonctions',
                                           'f_premier_jet_rapport': '1', 'f_redaction_constats': '1', 'f_preparation_mission': '1'})
verif('autre organisation : préparation introuvable', appel(admin_b, 'get', f'/audit-ia/audit/{AID}/preparation').status_code == 404
      and appel(admin_b, 'post', f'/audit-ia/audit/{AID}/preparation/creer', json={'tests': [t1]},
                headers={'X-CSRFToken': jeton(admin_b, '/dashboard'), **JS}).status_code in (403, 404))

print('--- Droits et cloisonnement')
verif('autre organisation : introuvable', appel(admin_b, 'get', f'/audit-ia/audit/{AID}/redaction').status_code == 404
      and proposer_constat(admin_b).status_code in (403, 404))
verif('simple utilisateur hors équipe : refusé', appel(lect, 'get', f'/audit-ia/audit/{AID}/redaction').status_code == 403)
with A.app.app_context():
    au = db.session.get(M.Audit, AID); au.etat_rapport = 'definitif'; au.dossier_rouvert_le = None; db.session.commit()
t = jeton(gest, f'/audit-ia/audit/{AID}/redaction')
r = appel(gest, 'post', f'/audit-ia/audit/{AID}/redaction', data={'csrf_token': t, 'action': 'valider', 'resume': 'Modif', 'conclusion': 'Modif'})
with A.app.app_context():
    verif('rapport définitif émis (dossier figé) : rédaction non modifiable', db.session.get(M.Audit, AID).redaction_rapport.get('resume') != 'Modif')
verif('… page en lecture seule', b'readonly' in appel(gest, 'get', f'/audit-ia/audit/{AID}/redaction').data)
r = appel(gest, 'post', f'/audit-ia/audit/{AID}/preparation/creer', json={'tests': [t1]},
          headers={'X-CSRFToken': jeton(gest, f'/audit-ia/audit/{AID}/preparation'), **JS})
with A.app.app_context():
    verif('… préparation : plus de création de feuilles', M.FeuilleTravail.query.filter_by(audit_id=AID).count() == 3, r.status_code)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
