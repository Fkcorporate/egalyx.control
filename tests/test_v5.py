"""Tests des modules v5 : synthèse du rapport, automatismes, bibliothèque, démo, rendu des pages."""
import os
import re
import sys
from datetime import date, datetime, timedelta
from types import SimpleNamespace as N

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, 'tests', 'stubs'))

import cotation  # noqa: E402
MODULES_EGALYX = {'securite_compte', 'sso', 'parametres_risque', 'alerte', 'alertes', 'tiers', 'signature', 'paiement',
                  'export_donnees', 'api_doc', 'organigramme_editeur', 'sauvegardes', 'demo', 'rapport_comite',
                  'bibliotheque', 'recherche', 'ma_semaine'}
import models  # noqa: E402  (double)
from egalyx.rapport_comite import rediger_synthese, decisions_attendues  # noqa: E402
from egalyx.automatismes import etat_kri  # noqa: E402

SORTIE = os.path.join(RACINE, 'tests', 'rendu')
os.makedirs(SORTIE, exist_ok=True)

CH = {'date': '05/11/2026', 'fenetre': 30, 'total_risques': 42, 'evalues': 31, 'couverture': 74, 'critiques': 3,
      'critiques_bruts': 9, 'tendance_critiques': {'ecart': 1, 'sens': 'mal'}, 'plans_retard': 3, 'plans_ouverts': 8,
      'retard_max': 45, 'incidents': 6, 'incidents_graves': 3, 'kri_alerte': 2, 'kri_actifs': 4, 'hors_appetence': 5,
      'audits': 2, 'constatations': 5, 'constatations_majeures': 3, 'recommandations_retard': 2, 'tiers': 6,
      'tiers_renforces': 3, 'criblages_a_verifier': 1, 'alertes': 1, 'alertes_ouvertes': 1, 'alertes_delais': 0}


# ------------------------------------------------------------------ synthèse rédigée
def test_synthese_complete():
    p = rediger_synthese(CH)
    texte = ' '.join(p)
    assert '31 risques évalués sur 42 recensés (74 %)' in texte and 'insuffisante' in texte
    assert '3 risques restent critiques' in texte and 'en hausse de 1' in texte and '9 étaient critiques' in texte
    assert "5 risques dépassent l'appétence" in texte
    assert "3 plans d'action sur 8" in texte and '45 jours' in texte
    assert '6 incidents déclarés' in texte and 'dont 3 graves' in texte
    assert '2 indicateurs de risque sur 4 sont au-delà de leur seuil' in texte
    assert '1 correspondance avec les listes de sanctions' in texte
    d = decisions_attendues(CH)
    assert len(d) == 5 and any('appétence' in x for x in d) and any('sanctions' in x for x in d)


def test_synthese_singulier_et_cas_vides():
    c = dict(CH, critiques=1, critiques_bruts=1, tendance_critiques={'ecart': -1, 'sens': 'bien'}, plans_retard=1,
             hors_appetence=1, incidents=1, incidents_graves=0, kri_alerte=1, couverture=100, evalues=42)
    t = ' '.join(rediger_synthese(c))
    assert '1 risque reste critique ' in t and 'en baisse de 1' in t and '1 était critique' in t
    assert "1 risque dépasse l'appétence fixée par la direction et appelle une" in t
    assert '1 incident déclaré sur' in t and 'insuffisante' not in t
    assert 'formalisée' in ' '.join(rediger_synthese(dict(CH, hors_appetence=None)))
    assert 'à construire' in rediger_synthese(dict(CH, total_risques=0))[0]
    assert "Fixer et formaliser l'appétence" in ' '.join(decisions_attendues(dict(CH, hors_appetence=None)))
    assert decisions_attendues(dict(CH, hors_appetence=0, plans_retard=0, recommandations_retard=0, couverture=90,
                                    criblages_a_verifier=0, alertes_delais=0)) == []


# ------------------------------------------------------------------ automatismes
def test_etat_kri():
    assert etat_kri(12, 8, 12) == 'critique' and etat_kri(9, 8, 12) == 'alerte' and etat_kri(5, 8, 12) == 'normal'
    assert etat_kri(96, 99, 97, 'inferieur') == 'critique' and etat_kri(98, 99, 97, 'inferieur') == 'alerte'
    assert etat_kri(99.5, 99, 97, 'inferieur') == 'normal' and etat_kri(None, 1, 2) == 'inconnu'


# ------------------------------------------------------------------ bibliothèque et démo
def test_bibliotheque_donnees():
    from egalyx.bibliotheque_donnees import SECTEURS, risques_du_secteur, IMPACT_TXT, PROBA_TXT
    from egalyx.bibliotheque import CODES
    assert set(CODES) == set(SECTEURS)
    for code, s in SECTEURS.items():
        intitules = [r[0] for r in s['risques']]
        assert len(intitules) == len(set(intitules)) and len(intitules) >= 10, code
        for r in risques_du_secteur(code):
            assert r['intitule'] and r['cause'] and r['consequences'] and r['referentiel']
            assert IMPACT_TXT[r['impact']] and PROBA_TXT[r['probabilite']]
    # les catégories utilisées par la démo existent bien dans la bibliothèque
    from egalyx.demo import DIRECTIONS
    for _p, _po, _d, secteur, cats in DIRECTIONS:
        dispo = {r['categorie'] for r in risques_du_secteur(secteur)}
        assert set(cats) & dispo, (secteur, cats)


def test_echelles_coherentes_avec_le_modele():
    """Les libellés écrits par la bibliothèque doivent être reconnus par Risque (échelles 1-5 de models.py)."""
    src = open(os.path.join(RACINE, 'models.py'), encoding='utf-8').read()
    from egalyx.bibliotheque_donnees import IMPACT_TXT, PROBA_TXT
    imp = re.search(r"ECHELLE_IMPACT = \{(.*?)\}", src, re.S).group(1)
    pro = re.search(r"ECHELLE_PROBABILITE = \{(.*?)\}", src, re.S).group(1)
    for n, txt in IMPACT_TXT.items():
        assert re.search(rf"'{txt}': {n}\b", imp), txt
    for n, txt in PROBA_TXT.items():
        assert re.search(rf"'{txt}': {n}\b", pro), txt


def test_mot_de_passe_demo_respecte_la_politique():
    from egalyx.demo import _mot_de_passe
    for _ in range(50):
        m = _mot_de_passe()
        assert len(m) >= 12 and re.search('[A-Z]', m) and re.search('[a-z]', m) and re.search('[0-9]', m)
        assert re.search(r'[!@#$%^&*(),.?":{}|<>]', m) and ' ' not in m


# ------------------------------------------------------------------ rendu
@pytest.fixture(scope='module')
def app():
    from test_v4_parcours import fabriquer_app
    from egalyx import recherche, ma_semaine, rapport_comite, bibliotheque, demo, tiers
    a = fabriquer_app()
    for m in (recherche, ma_semaine, bibliotheque, demo, tiers):
        m.enregistrer(a)
    rapport_comite.enregistrer(a)
    for ep in ('tableau_de_bord_strategique', 'liste_cartographies', 'switch_client'):
        a.add_url_rule('/' + ep, ep, lambda **k: 'x')
    a.jinja_env.globals.update(cotation_style=cotation.style, cotation_niveau=cotation.niveau)
    models.User._registre.clear()
    models.db.session.add(models.User(id=1, username='alice', email='a@x', role='admin', client_id=1, is_client_admin=True))
    return a


def rendre(app, gabarit, **ctx):
    from flask import render_template, session
    with app.test_request_context('/'):
        session['_uid'] = 1
        html = render_template(gabarit, **ctx)
    open(os.path.join(SORTIE, gabarit.replace('/', '__')), 'w', encoding='utf-8').write(html)
    return html


def dashboard_exemple():
    risques = [N(id=i, reference=f'R-BQ-{i:03d}', intitule=f'Risque {i}', categorie='Crédit') for i in range(1, 6)]
    m = [[[] for _ in range(5)] for _ in range(5)]
    m[4][3] = [{'ref': 'R-BQ-001', 'score': 16, 'niveau': 'Élevé'}] * 2
    m[3][3] = [{'ref': 'R-BQ-002', 'score': 13, 'niveau': 'Élevé'}]
    m[1][1] = [{'ref': 'x', 'score': 4, 'niveau': 'Faible'}] * 4
    cot = lambda b, n: {'score_brut': b, 'score_net': n, 'niveau_net': cotation.niveau(n), 'niveau_brut': cotation.niveau(b)}
    top = [{'risque': risques[i], 'cot': cot(20 - i, 17 - i * 2), 'entite': 'Direction du crédit', 'avant': None} for i in range(5)]
    plan = N(reference='PA-2026-001', nom='Renforcer la séparation des tâches', responsable=N(username='koffi'))
    return {
        'kpi': {'critiques': {'valeur': 3, 'brut': 9, 'tendance': {'ecart': 1, 'sens': 'mal'}},
                'score_moyen': {'valeur': 8.4, 'tendance': {'ecart': -0.6, 'sens': 'bien'}},
                'couverture': {'valeur': 74, 'evalues': 31, 'total': 42, 'tendance': None},
                'plans_retard': {'valeur': 3, 'ouverts': 8}, 'kri_alerte': {'valeur': 2, 'actifs': 4},
                'incidents': {'valeur': 6, 'graves': 3, 'tendance': {'ecart': 2, 'sens': 'mal'}}},
        'niveaux_net': {'Critique': 3, 'Élevé': 7, 'Moyen': 12, 'Faible': 9},
        'niveaux_brut': {'Critique': 9, 'Élevé': 11, 'Moyen': 8, 'Faible': 3},
        'matrices': {'net': m, 'brut': m},
        'evolution': [{'mois': f'{k:02d}/2026', 'libelle': x, 'critiques': c, 'eleves': e, 'evalues': 30}
                      for k, (x, c, e) in enumerate(zip(['déc', 'janv 26', 'févr', 'mars', 'avr', 'mai', 'juin', 'juil', 'août', 'sept', 'oct', 'nov'],
                                                        [1, 1, 2, 2, 2, 3, 2, 2, 3, 3, 2, 3], [4, 5, 5, 6, 6, 6, 7, 7, 6, 7, 8, 7]), 1)],
        'top_risques': top,
        'appetence': {'nombre': 2, 'seuil_global': 10, 'risques': [dict(top[0], appetence={'seuil': 10.0, 'ecart': 7.0}),
                                                                   dict(top[1], appetence={'seuil': 6.0, 'ecart': 9.0})]},
        'plans_retard': [{'plan': plan, 'jours': 45, 'echeance': date(2026, 9, 21), 'avancement': 30}],
        'nb_plans_retard': 3,
        'kri_alerte': [{'kri': N(nom='Taux de créances en souffrance', unite_mesure='%'), 'etat': 'alerte', 'valeur': 9.7, 'grave': False}],
        'incidents_graves': [N(date_occurrence=datetime(2026, 10, 24), titre='Virement frauduleux après changement de RIB', gravite='critique')],
        'fenetre_jours': 30,
    }


def test_rapport_comite(app):
    d = dashboard_exemple()
    audits = [{'audit': N(reference='AUD-2026-001', titre="Audit de l'octroi de crédit", statut='termine'),
               'constatations': 3, 'majeures': 2, 'recos': 3, 'recos_retard': 1}]
    recos = [N(reference='REC-1-01', description='Corriger les comités sans quorum', date_echeance=date(2026, 10, 16), taux_avancement=40)]
    h = rendre(app, 'egalyx/rapport_comite.html', d=d, c=CH, synthese=rediger_synthese(CH), decisions=decisions_attendues(CH),
               audits=audits, reco_retard=recos, client=N(nom='Sahel Finance (démonstration)'),
               genere_le=datetime(2026, 11, 5, 9, 30), auteur='Awa Diallo')
    for attendu in ('Rapport au comité d’audit', 'Sahel Finance', 'Décisions attendues', '31 risques évalués', 'R-BQ-001',
                    'PA-2026-001', 'Virement frauduleux', 'AUD-2026-001', 'REC-1-01', '+9.0', 'Awa Diallo', '<svg'):
        assert attendu in h, attendu


def test_pages_v5(app):
    from egalyx.bibliotheque_donnees import SECTEURS, risques_du_secteur
    h = rendre(app, 'egalyx/bibliotheque.html', secteurs=SECTEURS, secteur='banque', risques=risques_du_secteur('banque'),
               cartos=[N(id=1, nom='Risques — Direction du crédit')])
    assert 'Blanchiment de capitaux' in h and 'BCEAO' in h and 'Importer' in h and 'Ctrl K' in h and 'rgFond' in h
    today = date.today()
    taches = [{'type': "Plan d'action", 'titre': 'Renforcer la séparation des tâches', 'sous_titre': 'PA-2026-001 · 30 %',
               'echeance': today - timedelta(days=45), 'retard_jours': 45, 'lien': '/plan', 'priorite': 0},
              {'type': 'Mesure de KRI', 'titre': 'Taux de créances', 'sous_titre': 'Dernière mesure : 03/10/2026',
               'echeance': today + timedelta(days=3), 'retard_jours': 0, 'lien': '/kri', 'priorite': 1}]
    h = rendre(app, 'egalyx/ma_semaine.html', taches=taches, resume={'retard': 1, 'semaine': 1, 'total': 2}, aujourd_hui=today)
    assert '45 j de retard' in h and 'Cette semaine' in h and 'Plus tard' not in h
    assert 'Bonne semaine' in rendre(app, 'egalyx/ma_semaine.html', taches=[], resume={'retard': 0, 'semaine': 0, 'total': 0}, aujourd_hui=today)
    etapes = [{'titre': f'Étape {i}', 'aide': 'aide', 'fait': i < 4, 'lien': '/x'} for i in range(10)]
    h = rendre(app, 'egalyx/demarrage.html', d={'etapes': etapes, 'faites': 4, 'total': 10, 'pourcentage': 40})
    assert '40 %' in h and h.count('Commencer') == 6
    h = rendre(app, 'egalyx/demo.html', client=N(nom='Sahel Finance (démonstration)', reference='DEMO01'),
               identifiants=[('admin_demo01', 'Demo-ab12cd34Kx7!', 'admin')],
               rapport=[('Utilisateurs', True, '4 comptes'), ('Incidents', False, 'IntegrityError : …')], demos=None)
    assert 'Demo-ab12cd34Kx7!' in h and 'IntegrityError' in h
    assert 'Créer une organisation de démonstration' in rendre(app, 'egalyx/demo.html', client=None, identifiants=None, rapport=None,
                                                              demos=[N(id=3, reference='DEMO01', nom='Sahel', is_active=True)])


def test_recherche_texte_court(app, monkeypatch):
    monkeypatch.setenv('EGALYX_2FA_OBLIGATOIRE_ADMINS', '0')
    from egalyx.recherche import rechercher
    with app.test_request_context('/'):
        assert rechercher(1, 'a') == [] and rechercher(None, 'credit') == []
    c = app.test_client()
    c.get('/_connexion/1')
    assert c.get('/api/recherche?q=x').get_json() == {'resultats': []}
    monkeypatch.setenv('EGALYX_2FA_OBLIGATOIRE_ADMINS', '1')
    assert c.get('/api/recherche?q=x').status_code == 403          # administrateur sans 2FA : bloqué


def test_gabarits_plus_recents_que_le_code():
    """Cas réel : templates v5 installés mais modules egalyx/ plus anciens -> aucune page ne doit planter."""
    from flask import Flask, render_template, session
    from test_v4_parcours import Souple
    from egalyx import double_auth
    a = Flask(__name__, template_folder=os.path.join(RACINE, 'templates')); a.secret_key = 'x'
    a.jinja_env.undefined = Souple
    a.jinja_env.add_extension('jinja2.ext.do'); a.jinja_env.add_extension('jinja2.ext.loopcontrols')
    from flask_login import current_user
    a.jinja_env.globals.update(csrf_token=lambda: 'j', t=lambda s, *x, **k: s, should_display_module=lambda *x: True,
                               url_exists=lambda e: e in a.view_functions, current_user=current_user)
    a.url_build_error_handlers.append(lambda err, ep, vals: (_ for _ in ()).throw(err) if ep.split('.')[0] in MODULES_EGALYX else '/#' + ep)
    double_auth.enregistrer(a)           # seul un module v4 est présent, comme chez l'utilisateur
    with a.test_request_context('/'):
        session['_uid'] = 1
        html = render_template('base.html')
    assert 'Ma semaine' not in html and 'rgFond' not in html and 'Sécurité du compte' in html


# ------------------------------------------------------------------ permissions
def _app_permissions():
    from test_v4_parcours import fabriquer_app
    from egalyx import tiers, rapport_comite, bibliotheque, ma_semaine, recherche, signature, organigramme, parametres_risque
    a = fabriquer_app()
    for m in (tiers, rapport_comite, bibliotheque, ma_semaine, recherche, signature, organigramme):
        m.enregistrer(a)
    a.register_blueprint(parametres_risque.bp)
    a.jinja_env.globals['has_permission'] = lambda p: __import__('flask_login').current_user.has_permission(p)
    for ep in ('tableau_de_bord_strategique', 'liste_cartographies', 'admin_directions'):
        a.add_url_rule('/' + ep, ep, lambda **k: 'x')
    return a


@pytest.fixture()
def utilisateurs(monkeypatch):
    monkeypatch.setenv('EGALYX_2FA_OBLIGATOIRE_ADMINS', '0')
    models.User._registre.clear(); models.Client._registre.clear()
    db = models.db
    db.session.add(models.Client(id=1, nom='ACME', reference='ACME'))
    lecteur = models.User(username='lecteur', email='l@x', role='utilisateur', client_id=1, droits={'can_view_dashboard'})
    tiers_lect = models.User(username='kyc', email='k@x', role='utilisateur', client_id=1, droits={'can_view_tiers'})
    conf = models.User(username='conf', email='c@x', role='compliance', client_id=1,
                       droits={'can_view_tiers', 'can_manage_tiers', 'can_manage_alertes'})
    for u in (lecteur, tiers_lect, conf):
        db.session.add(u)
    return {'lecteur': lecteur, 'kyc': tiers_lect, 'conf': conf}


def test_routes_refusees_sans_permission(utilisateurs):
    a = _app_permissions(); c = a.test_client()
    c.get(f"/_connexion/{utilisateurs['lecteur'].id}")
    for url in ('/conformite/tiers/', '/conformite/tiers/nouveau', '/rapports/comite-audit', '/risques/bibliotheque/',
                '/parametres/risques/', '/processus/1/organigramme/editer', '/conformite/alertes/'):
        r = c.get(url)
        assert r.status_code == 302 and r.location.endswith('/dashboard'), url
    assert c.post('/api/processus/1/organigramme', json={}).status_code == 403
    assert c.post('/conformite/tiers/1/action', data={'action': 'cribler'}).status_code == 302


def test_lecture_seule_et_referent(utilisateurs):
    from egalyx.alerte import est_referent
    from egalyx.commun import a_permission
    a = _app_permissions()
    with a.test_request_context('/'):
        assert est_referent(utilisateurs['conf']) and not est_referent(utilisateurs['kyc'])
        assert not est_referent(models.User(username='sa', role='super_admin'))   # confidentialité
        assert a_permission('can_view_tiers', u=utilisateurs['kyc']) and not a_permission('can_manage_tiers', u=utilisateurs['kyc'])
    c = a.test_client(); c.get(f"/_connexion/{utilisateurs['kyc'].id}")
    assert c.get('/conformite/tiers/nouveau').status_code == 302                  # lecture seule : pas de création


def test_menu_selon_permissions(utilisateurs):
    from flask import render_template, session
    a = _app_permissions()
    a.jinja_env.globals.update(should_display_module=lambda *x: True, est_referent_alerte=lambda: __import__('egalyx.alerte', fromlist=['x']).est_referent())
    def menu(u):
        with a.test_request_context('/'):
            session['_uid'] = u.id
            return render_template('base.html')
    h = menu(utilisateurs['lecteur'])
    for absent in ('Tiers &amp; LCB-FT', 'Alertes internes', "Rapport au comité", 'Bibliothèque de risques', '>Conformité<'):
        assert absent not in h, absent
    assert 'Ma semaine' in h
    h = menu(utilisateurs['conf'])
    assert 'Tiers &amp; LCB-FT' in h and 'Alertes internes' in h and "Rapport au comité" not in h


# ------------------------------------------------------------------ modules par client
def test_catalogue_modules_coherent():
    from egalyx.modules_client import CATALOGUE, MODULES, PROFILS, GROUPES, MODULE_DE_PERMISSION
    perms = [p for m in CATALOGUE for p in m[4]]
    assert len(perms) == len(set(perms)), 'une permission ne doit appartenir qu’à un seul module'
    assert all(m[3] in GROUPES for m in CATALOGUE)
    for nom, (_l, _d, codes) in PROFILS.items():
        assert codes and set(codes) <= set(MODULES), nom
    # chaque permission du catalogue existe réellement dans l'application
    src = open(os.path.join(RACINE, 'models.py'), encoding='utf-8').read() + open(os.path.join(RACINE, 'app.py'), encoding='utf-8').read()
    for p in MODULE_DE_PERMISSION:
        assert f"'{p}'" in src, p


def test_filtrage_par_module():
    from egalyx.modules_client import permission_autorisee_par_module, modules_depuis_formule
    c = N(modules_actifs=None)
    u = N(client=c)
    assert permission_autorisee_par_module(u, 'can_manage_risks')                    # aucun choix : pas de restriction
    c.modules_actifs = {'audit': True, 'plans_action': True, 'cartographie': False}
    assert permission_autorisee_par_module(u, 'can_manage_audit')
    assert not permission_autorisee_par_module(u, 'can_manage_risks')
    assert not permission_autorisee_par_module(u, 'can_view_tiers')                 # absent = désactivé
    assert permission_autorisee_par_module(u, 'can_view_dashboard')                 # transversal
    assert permission_autorisee_par_module(u, 'can_manage_users')
    f = N(modules={'audit_interne': True, 'cartographie': False, 'incidents': False, 'suivi_kri': True})
    m = modules_depuis_formule(f)
    assert 'audit' in m and 'kri' in m and 'cartographie' not in m and 'incidents' not in m and 'tiers' in m


def test_page_modules_et_effet_immediat(monkeypatch):
    from test_v4_parcours import fabriquer_app
    from egalyx import modules_client, tiers
    from flask import render_template, session
    monkeypatch.setenv('EGALYX_2FA_OBLIGATOIRE_ADMINS', '0')
    a = fabriquer_app(); modules_client.enregistrer(a); tiers.enregistrer(a)
    for ep in ('super_admin_clients', 'super_admin_client_detail'):
        a.add_url_rule('/' + ep + '/<int:id>' if 'detail' in ep else '/' + ep, ep, lambda **k: 'x')
    a.jinja_env.globals['has_permission'] = lambda p: __import__('flask_login').current_user.has_permission(p)
    a.jinja_env.globals['should_display_module'] = lambda p: __import__('flask_login').current_user.has_permission(p) if p.startswith('can_') else False
    models.User._registre.clear(); models.Client._registre.clear()
    cab = models.Client(nom="Cabinet d'audit Koné", reference='KONE'); models.db.session.add(cab)
    sa = models.User(username='sa', email='sa@x', role='super_admin'); models.db.session.add(sa)
    adm = models.User(username='adm', email='a@k', role='admin', client_id=cab.id, is_client_admin=True); models.db.session.add(adm)
    c = a.test_client(); c.get(f'/_connexion/{sa.id}')
    r = c.get(f'/super-admin/client/{cab.id}/modules')
    assert r.status_code == 200 and 'Aucune restriction' in r.text and 'Cabinet ou service d’audit' in r.text
    c.post(f'/super-admin/client/{cab.id}/modules', data={'action': 'enregistrer', 'modules': ['audit', 'programme_audit', 'plans_action']})
    assert cab.modules_actifs['audit'] and not cab.modules_actifs['tiers'] and not cab.modules_actifs['cartographie']
    # l'administrateur du cabinet perd immédiatement l'accès aux modules non souscrits, sans reconnexion
    c2 = a.test_client(); c2.get(f'/_connexion/{adm.id}')
    assert c2.get('/conformite/tiers/').status_code == 302
    assert adm.has_permission('can_manage_audit') and not adm.has_permission('can_manage_risks')
    with a.test_request_context('/'):
        session['_uid'] = adm.id
        menu = render_template('base.html')
    assert 'Tiers &amp; LCB-FT' not in menu and 'Bibliothèque de risques' not in menu
    # retour sans restriction
    c.post(f'/super-admin/client/{cab.id}/modules', data={'action': 'aucune_restriction'})
    assert cab.modules_actifs is None and adm.has_permission('can_manage_risks')
    # un administrateur client ne peut pas modifier ses propres modules
    assert c2.get(f'/super-admin/client/{cab.id}/modules').status_code == 404
