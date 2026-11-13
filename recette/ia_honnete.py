"""Recette : l'« IA » dit la vérité (vraie IA ou « automatique » signalée) + 4 écrans trompeurs corrigés."""
import datetime as dt
import json
import os
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, appel, creer
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
import objets
import models as M
from models import db
from egalyx import ia as interrupteur, ia_moteur
with Muet():
    O = objets.peupler_objets(A, ids)
interrupteur.ecrire_reglage('ia_active', True)
os.environ['OPENAI_API_KEY'] = ''                     # d'abord : pas d'IA disponible


def go(role, m, url, **kw):
    r = appel(socle.navigateur(A, ids[role]), m, url, **kw)
    return r, r.data.decode('utf-8', 'ignore'), socle.cause(A)


def js(r):
    try:
        return json.loads(r.data.decode('utf-8'))
    except Exception:
        return {}


vues = A.app.view_functions
print('--- Branchements')
verif('incident : analyse remplacée', 'ia_honnete' in getattr(vues['analyse_ia_incident'], '__wrapped__', vues['analyse_ia_incident']).__module__)
verif('C2N : recommandations remplacées', 'ia_honnete' in getattr(vues['c2n_generer_recommandations_ia'], '__wrapped__', vues['c2n_generer_recommandations_ia']).__module__)
verif('demande d\'offre : vue remplacée + API créée', 'demande_offre' in vues['client_request_upgrade'].__wrapped__.__module__
      and 'api_client_upgrade_request' in vues)
verif('statistiques de questionnaire remplacées', 'questionnaire_stats' in vues['statistiques_questionnaire'].__wrapped__.__module__)

print('--- Qualité (sans IA : règles fixes, sans hasard, signalées)')
r1, _, e = go('admin_a', 'post', '/api/qualite/generer-objectifs', json={'titre': 'Plan qualité achats'})
r2, _, _ = go('admin_a', 'post', '/api/qualite/generer-objectifs', json={'titre': 'Plan qualité achats'})
d1, d2 = js(r1), js(r2)
verif('objectifs : réponse signalée « automatique »', r1.status_code == 200 and d1.get('origine') == 'automatique', f'{r1.status_code} {e} {d1}')
verif('objectifs : deux clics = même réponse (plus de hasard)', d1.get('objectifs') == d2.get('objectifs') and d1.get('objectifs'))
r, _, e = go('admin_a', 'post', '/api/qualite/suggerer-assurance', json={'titre': 'Plan qualité achats'})
d = js(r)
verif('assurance qualité : fonctionne (était en erreur)', r.status_code == 200 and d.get('success') and d.get('origine') == 'automatique',
      f'{r.status_code} {e} {str(d)[:160]}')
for url, corps in (('/api/qualite/suggerer-description', {'titre': 'Plan achats', 'objectifs': ['Réduire les litiges']}),
                   ('/api/qualite/generer-indicateurs', {'titre': 'Plan achats', 'objectifs': ['Réduire les litiges']}),
                   ('/api/qualite/suggerer-maturite', {'titre': 'Plan achats structuré'}),
                   ('/api/qualite/generer-plan-complet', {'titre': 'Plan achats'})):
    r, _, e = go('admin_a', 'post', url, json=corps); d = js(r)
    verif(f'{url.split("/")[-1]} : OK et « automatique »', r.status_code == 200 and d.get('origine') == 'automatique', f'{r.status_code} {e} {str(d)[:120]}')

print('--- Qualité avec IA (réponse simulée du fournisseur)')
os.environ['OPENAI_API_KEY'] = 'sk-proj-' + 'x' * 40
appels = []
vrai_demander = ia_moteur.demander_json


def fausse_ia(consignes, donnees, max_tokens=1500, temperature=0.3):
    appels.append((consignes, donnees))
    ia_moteur.marquer(ia_moteur.IA)
    if 'objectifs SMART' in consignes:
        return {'objectifs': ['Réduire de 20 % les litiges fournisseurs d\'ici juin 2027']}
    if 'incident' in consignes.lower():
        return {'classification': {'type': 'operationnel', 'gravite': 'elevee'}, 'causes_probables': ['Procédure de sauvegarde non suivie'],
                'recommandations': ['Rétablir la sauvegarde quotidienne'], 'delai_estime': '2 jours', 'informations_manquantes': ['Durée exacte']}
    if 'contrôle interne de niveau 2' in consignes:
        return {'recommandations': [{'titre': 'Revoir la séparation des tâches sur les virements', 'description': '3 anomalies sur 10.',
                                     'priorite': 'haute', 'categorie': 'organisation'}]}
    if 'continuité' in consignes:
        if 'exercices' in consignes:
            return {'exercices': [{'titre': 'Simulation de perte du site', 'description': 'Table ronde.', 'type': 'table_top',
                                   'duree_suggeree': '3 heures', 'objectifs': ['Tester la cellule de crise']}]}
        return {'actions': [{'titre': 'Désigner un site de repli', 'description': 'Aucun site de repli.', 'phase': 'preparation',
                             'priorite': 'haute', 'delai_suggere': '60 jours'}]}
    return {}


ia_moteur.demander_json = fausse_ia
r, _, e = go('admin_a', 'post', '/api/qualite/generer-objectifs', json={'titre': 'Plan qualité achats'}); d = js(r)
verif('objectifs : vraie IA appelée, origine « ia »', d.get('origine') == 'ia' and d.get('objectifs') == ['Réduire de 20 % les litiges fournisseurs d\'ici juin 2027']
      and d.get('ia_modele'), str(d)[:200])

print('--- Incidents')
with A.app.app_context():
    inc = creer(M.Incident, reference='INC-IA', titre='Sauvegarde non réalisée', description='La sauvegarde de nuit a échoué.',
                client_id=1, created_by=ids['gestionnaire'], gravite='elevee', type_incident='operationnel', statut='ouvert')
    vieux = creer(M.Incident, reference='INC-OLD', titre='Ancien', client_id=1, created_by=ids['gestionnaire'],
                  analyse_ia=json.dumps({'classification': {'type': 'x', 'gravite': 'y'}, 'causes_probables': ['Défaut de configuration'],
                                         'recommandations': ['Former'], 'score_confiance': 85}), ia_score_confiance=85)
    db.session.commit(); iid, vid = inc.id, vieux.id
r, _, e = go('admin_a', 'get', f'/incident/{iid}/analyse-ia')
with A.app.app_context():
    a = json.loads(db.session.get(M.Incident, iid).analyse_ia)
    sc = db.session.get(M.Incident, iid).ia_score_confiance
verif('analyse avec IA : contenu de l\'IA, origine « ia », aucun score inventé', a.get('origine') == 'ia' and a['causes_probables'] == ['Procédure de sauvegarde non suivie']
      and sc == 0, f'{r.status_code} {e} {a}')
r, t, e = go('admin_a', 'get', f'/incident/{iid}')
verif('fiche incident : « Rédigée par l\'IA », plus de « confiance 85 % »', r.status_code == 200 and "Rédigée par l'IA" in t and 'Score de confiance' not in t,
      f'{r.status_code} {e}')
os.environ['OPENAI_API_KEY'] = ''
ia_moteur.demander_json = vrai_demander
r, _, e = go('admin_a', 'get', f'/incident/{iid}/analyse-ia')
with A.app.app_context():
    a = json.loads(db.session.get(M.Incident, iid).analyse_ia)
verif('analyse sans IA : « automatique », pas de cause inventée', a.get('origine') == 'automatique' and a['causes_probables'] == []
      and 'Défaut de configuration' not in json.dumps(a, ensure_ascii=False), str(a)[:200])
r, t, e = go('admin_a', 'get', f'/incident/{iid}')
verif('fiche : « Analyse automatique, sans IA »', 'Analyse automatique, sans IA' in t, e)
r, t, e = go('admin_a', 'get', f'/incident/{vid}')
verif('ancienne analyse factice : signalée « à relancer »', r.status_code == 200 and 'ancienne version' in t, f'{r.status_code} {e}')
r, t, e = go('admin_a', 'get', '/incidents/dashboard-ia')
verif('tableau d\'analyse : plus de « Intelligence Artificielle », origine affichée', r.status_code == 200 and 'Intelligence Artificielle' not in t
      and 'Origine' in t, f'{r.status_code} {e}')
r, _, _ = go('admin_b', 'get', f'/incident/{iid}/analyse-ia')
with A.app.app_context():
    verif('autre organisation : analyse refusée', r.status_code in (302, 403, 404) and json.loads(db.session.get(M.Incident, iid).analyse_ia)['origine'] == 'automatique',
          str(r.status_code))

print('--- Contrôle de niveau 2 : recommandations')
with A.app.app_context():
    pl = db.session.get(M.PlanificationControle, O['a']['planification'])
    ex = creer(M.ExecutionControle, client_id=1, taux_conformite=60.0, volume_previsionnel=20, volume_controle=10, nb_anomalies=4,
               nb_conformes=6) if hasattr(M, 'ExecutionControle') else None
    if ex is not None:
        pl.execution_id = ex.id
    db.session.commit(); plid = pl.id
r, _, e = go('admin_a', 'post', '/c2n/recommandations/generer-ia', json={'planification_id': plid}); d = js(r)
with A.app.app_context():
    recos = M.RecommandationC2N.query.filter_by(planification_id=plid).all()
    titres = [x.titre for x in recos]
verif('sans IA : règles tirées des résultats, source « automatique »', d.get('source') == 'automatique' and "Analyser les causes de non-conformité" in titres,
      f'{r.status_code} {e} {d.get("message")} {titres}')
verif('sans IA : plus de recommandations génériques ajoutées d\'office', not any('Automatiser' in t or 'Former les' in t for t in titres), str(titres))
n1 = len(titres)
go('admin_a', 'post', '/c2n/recommandations/generer-ia', json={'planification_id': plid})
with A.app.app_context():
    verif('2e clic : pas de doublons', M.RecommandationC2N.query.filter_by(planification_id=plid).count() == n1)
os.environ['OPENAI_API_KEY'] = 'sk-proj-' + 'x' * 40
ia_moteur.demander_json = fausse_ia
r, _, e = go('admin_a', 'post', '/c2n/recommandations/generer-ia', json={'planification_id': plid}); d = js(r)
with A.app.app_context():
    r_ia = M.RecommandationC2N.query.filter_by(planification_id=plid, source='ia').all()
verif('avec IA : recommandation propre au contrôle, source « ia »', d.get('source') == 'ia' and any('séparation des tâches' in x.titre for x in r_ia),
      f'{e} {d.get("message")}')
verif('données envoyées à l\'IA : taux et anomalies réels', any('contrôle interne de niveau 2' in c and d_['execution'] and d_['execution']['taux_conformite'] == 60.0
                                                             for c, d_ in appels if isinstance(d_, dict) and 'execution' in d_))
r, _, _ = go('admin_b', 'post', '/c2n/recommandations/generer-ia', json={'planification_id': plid})
verif('autre organisation : refusé', r.status_code in (403, 404), str(r.status_code))

print('--- PCA : suggestions')
from services.ia_pca_service import IAPcaService
with A.app.test_request_context():
    s = IAPcaService.suggerer_actions_specifiques({'maturite_globale': 2, 'processus_critiques': []}, [])
    verif('PCA avec IA : actions de l\'IA', s and s[0]['titre'] == 'Désigner un site de repli' and ia_moteur.origine_courante() == 'ia', str(s)[:120])
with A.app.test_request_context():
    s = IAPcaService.suggerer_exercices_specifiques({'maturite_globale': 2}, [])
    verif('PCA avec IA : exercices (objectifs en texte)', s and s[0]['type'] == 'table_top' and isinstance(s[0]['objectifs'], str), str(s)[:120])
os.environ['OPENAI_API_KEY'] = ''
ia_moteur.demander_json = vrai_demander
with A.app.test_request_context():
    s = IAPcaService.suggerer_actions_specifiques({'maturite_globale': 2, 'processus_critiques': [], 'nb_actions': 0, 'nb_exercices': 0,
                                                   'derniere_date_test': None, 'statut': 'en_redaction'}, [])
    verif('PCA sans IA : règles, signalées « automatique »', isinstance(s, list) and ia_moteur.origine_courante() == 'automatique', str(s)[:120])
t = open(os.path.join(A.app.root_path, 'templates/pca/detail_plan.html'), encoding='utf-8').read()
verif('PCA : titre de la fenêtre selon l\'origine réelle', "egPcaOrigine" in t and "Actions suggérées par l'IA\n" not in t)

print('--- KRI : suggestions de secours signalées')
with A.app.test_request_context():
    from services.kri_ia_service import KRIIAService
    k = KRIIAService.__new__(KRIIAService)
    try:
        k._simuler_generation_kri({'intitule': 'Fraude', 'categorie': 'operationnel'})
    except Exception:
        pass
    verif('KRI : modèles types marqués « automatique »', ia_moteur.origine_courante() == 'automatique')
r, _, e = go('admin_a', 'get', f"/api/risque/{O['a']['risque']}/kris/suggestions"); d = js(r)
verif('KRI modèles types : fonctionne (était en erreur 500), sans score inventé', r.status_code == 200 and d.get('origine') == 'automatique'
      and 'score_confiance' not in json.dumps(d), f'{r.status_code} {e}')
r, _, _ = go('admin_b', 'get', f"/api/risque/{O['a']['risque']}/kris/suggestions")
verif('KRI modèles types : autre organisation refusée', r.status_code == 404, str(r.status_code))
t = open(os.path.join(A.app.root_path, 'templates/kri/form.html'), encoding='utf-8').read()
verif('formulaire KRI : « modèles types » affiché quand ce n\'est pas l\'IA', 'modèles types' in t and "d.origine === 'ia'" in t)

print('--- Libellés « IA » des fonctions sans IA')
with A.app.app_context():
    carto = O['a']['carto']
r, t, e = go('admin_a', 'get', f'/cartographie/{carto}/analyse-ia-ultra')
verif('« Ultra » : renommée « Analyse automatique approfondie », sans IA', r.status_code in (200, 302) and (r.status_code == 302 or
      ('Analyse automatique approfondie' in t and 'calculée par des règles' in t and 'Analyse Intelligente' not in t)), f'{r.status_code} {e}')
r, t, e = go('admin_a', 'get', f'/cartographie/{carto}')
verif('cartographie : bouton décrit « sans IA »', 'Analyse automatique approfondie (calcul par règles, sans IA)' in t, f'{r.status_code} {e}')
r, t, e = go('admin_a', 'get', '/dashboard')
verif('avertissement commun « Proposition automatique » chargé', 'egIaOrigine' in t, f'{r.status_code} {e}')

print('--- Interrupteur super-admin respecté')
interrupteur.ecrire_reglage('ia_active', False)
os.environ['OPENAI_API_KEY'] = 'sk-proj-' + 'x' * 40
try:
    ia_moteur.demander_json('x', {})
    verif('IA coupée : le moteur refuse', False)
except ia_moteur.IndisponibleIA:
    verif('IA coupée : le moteur refuse', True)
r, _, _ = go('admin_a', 'post', '/c2n/recommandations/generer-ia', json={'planification_id': plid})
verif('IA coupée : génération C2N bloquée', r.status_code in (403, 404), str(r.status_code))
interrupteur.ecrire_reglage('ia_active', True)
os.environ['OPENAI_API_KEY'] = ''

print('--- Demande de changement d\'offre')
with A.app.app_context():
    f1 = creer(M.FormuleAbonnement, nom='Essentiel', code='ESS') if 'code' in M.FormuleAbonnement.__table__.c else creer(M.FormuleAbonnement, nom='Essentiel')
    f2 = creer(M.FormuleAbonnement, nom='Premium', code='PRE') if 'code' in M.FormuleAbonnement.__table__.c else creer(M.FormuleAbonnement, nom='Premium')
    c = db.session.get(M.Client, 1); c.formule_id = f1.id; db.session.commit(); f2id = f2.id; f1id = f1.id
r, _, e = go('admin_a', 'post', '/api/client/upgrade-request', json={'formule_id': f2id}); d = js(r)
with A.app.app_context():
    tk = M.TicketSupport.query.filter_by(client_id=1, source='changement_offre').all()
verif('API : un vrai ticket de support est créé', r.status_code == 200 and d.get('success') and len(tk) == 1 and 'Essentiel → Premium' in tk[0].sujet,
      f'{r.status_code} {e} {d}')
verif('message honnête avec la référence du ticket', tk and tk[0].reference in (d.get('message') or '') and 'espace support' in d.get('message', ''))
r, _, _ = go('admin_a', 'post', '/api/client/upgrade-request', json={'formule_id': f2id}); d = js(r)
with A.app.app_context():
    verif('2e demande identique : pas de doublon', M.TicketSupport.query.filter_by(client_id=1, source='changement_offre').count() == 1
          and 'déjà enregistrée' in d.get('message', ''))
r, _, _ = go('admin_a', 'post', '/api/client/upgrade-request', json={'formule_id': f1id})
verif('formule déjà active : refusée', js(r).get('success') is False)
r, _, _ = go('lecteur', 'post', '/api/client/upgrade-request', json={'formule_id': f2id})
verif('simple utilisateur : refusé', r.status_code == 403, str(r.status_code))
r, _, e = go('admin_a', 'post', '/client/request-upgrade', data={'formule_id': f2id})
verif('formulaire classique : redirige sans erreur', r.status_code == 302, f'{r.status_code} {e}')
t = open(os.path.join(A.app.root_path, 'templates/client_admin/usage.html'), encoding='utf-8').read()
verif('page Utilisation : affiche le message du serveur (plus de faux « envoyée »)', 'data.message' in t and "alert('Demande d\\'upgrade envoyée" not in t)

print('--- Statistiques de questionnaire')
with A.app.app_context():
    db.session.get(M.Client, 1).formule_id = None; db.session.commit()     # la formule d'essai limite les modules
    q = creer(M.Questionnaire, titre='Satisfaction', code='SAT-1', client_id=1)
    cat = creer(M.QuestionnaireCategorie, questionnaire_id=q.id, titre='Général', client_id=1) if 'client_id' in M.QuestionnaireCategorie.__table__.c \
        else creer(M.QuestionnaireCategorie, questionnaire_id=q.id, titre='Général')
    qu = creer(M.Question, categorie_id=cat.id, texte='Note globale', type='rating', echelle_min=1, echelle_max=5, client_id=1)
    for note, mois in ((5, 0), (5, 0), (4, 1), (2, 1), (5, 2)):
        rq = creer(M.ReponseQuestionnaire, questionnaire_id=q.id, session_id=f's{note}{mois}', statut='complet', client_id=1,
                   date_debut=dt.datetime.utcnow() - dt.timedelta(days=31 * mois))
        creer(M.ReponseQuestion, reponse_questionnaire_id=rq.id, question_id=qu.id, valeur_numerique=note, client_id=1)
    db.session.commit(); qid = q.id
r, t, e = go('admin_a', 'get', f'/questionnaires/{qid}/stats')
verif('page des statistiques : OK', r.status_code == 200, f'{r.status_code} {e}')
verif('notes réelles : 1→0, 2→1, 3→0, 4→1, 5→3 (plus de 5,10,15,20,25)', '[0, 1, 0, 1, 3]' in t and '[5, 10, 15, 20, 25]' not in t)
verif('moyenne affichée (4,20)', '4,20' in t)
verif('réponses par mois réelles (plus de 12,19,15,25,22,30)', '[12, 19, 15, 25, 22, 30]' not in t and '[0, 0, 0, 1, 2, 2]' in t)
r, _, _ = go('admin_b', 'get', f'/questionnaires/{qid}/stats')
verif('autre organisation : statistiques refusées', r.status_code == 404, str(r.status_code))

print('--- Mots de passe proposés')
for p in ('templates/client_admin/creer_utilisateur.html', 'templates/super_admin/client_detail.html'):
    t = open(os.path.join(A.app.root_path, p), encoding='utf-8').read()
    gen = t[t.find('function genererMotDePasse') if 'genererMotDePasse' in t else t.find('function generatePassword'):][:900]
    verif(f'{p.split("/")[-1]} : générateur cryptographique, plus de Math.random', 'egMotDePasseSur' in gen and 'Math.random' not in gen)
t = open(os.path.join(A.app.root_path, 'templates/egalyx/_mot_de_passe_sur.html'), encoding='utf-8').read()
verif('générateur : crypto.getRandomValues, 12 caractères minimum', 'getRandomValues' in t and 'Math.max(12' in t and 'Math.random' not in t)
r, t, e = go('superadmin', 'get', '/super-admin/client/1')
verif('fiche client super-admin : s\'affiche avec le générateur', r.status_code in (200, 302) and (r.status_code == 302 or 'egMotDePasseSur' in t), f'{r.status_code} {e}')

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
