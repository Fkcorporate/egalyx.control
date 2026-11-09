"""
Rendu des gabarits v4 et des gabarits modifiés avec des données de test (doubles),
pour vérifier qu'aucun ne plante et que les informations clés apparaissent.
Les pages sont aussi écrites dans tests/rendu/ pour contrôle visuel.
"""
import os
import sys
from datetime import date, datetime, timedelta
from types import SimpleNamespace as N

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, 'tests', 'stubs'))

import models  # noqa: E402  (double)
from test_v4_parcours import fabriquer_app  # noqa: E402

SORTIE = os.path.join(RACINE, 'tests', 'rendu')
os.makedirs(SORTIE, exist_ok=True)


@pytest.fixture(scope='module')
def app():
    from egalyx import tiers, signature, parametres_risque, organigramme, base_donnees
    a = fabriquer_app()
    for m in (tiers, signature, organigramme):
        m.enregistrer(a)
    a.register_blueprint(parametres_risque.bp)
    a.register_blueprint(base_donnees._blueprint(a))
    a.jinja_env.globals.update(resume_signatures=lambda t, i: {'total': 2, 'valides': 1, 'modifie': True},
                               appetence_risque=lambda r: {'seuil': 10.0, 'depasse': True, 'ecart': 2.0},
                               est_referent_alerte=lambda: True)
    models.User._registre.clear()
    models.db.session.add(models.User(id=1, username='alice', email='alice@acme.ci', role='admin', client_id=1, is_client_admin=True))
    return a


def rendre(app, gabarit, **ctx):
    from flask import render_template, session
    with app.test_request_context('/'):
        session['_uid'] = 1
        html = render_template(gabarit, **ctx)
    with open(os.path.join(SORTIE, gabarit.replace('/', '__')), 'w', encoding='utf-8') as f:
        f.write(html)
    return html


def tiers_exemple():
    cr = N(id=5, created_at=datetime(2026, 11, 3, 10, 5), nb_entrees_controlees=1243, auteur=N(username='alice'),
           statut='a_verifier', commentaire=None, verificateur=None, verifie_le=None,
           correspondances=[{'nom_controle': 'Kouassi Trading SARL', 'role': 'Tiers', 'nom_liste': 'KOUASSI TRADING',
                             'nom_correspondant': 'KOUASSI TRADING', 'source': 'ONU', 'programme': 'RES 1718', 'score': 0.93}])
    return N(id=7, reference='TRS-0007', nom='Kouassi Trading SARL', type_tiers='fournisseur', nature='personne_morale',
             statut='en_cours', sigle='KT', numero_identification='CI-ABJ-2019-B-1234', pays="Côte d'Ivoire",
             pays_residence='Mali', secteur='Négoce de métaux précieux', est_ppe=True, canal='distance',
             montant_relation=125000000, responsable=N(username='alice'), responsable_id=1, date_derniere_revue=date(2025, 10, 1),
             date_prochaine_revue=date(2026, 10, 1), revue_en_retard=True, score_lcb=85, niveau_vigilance='renforcee',
             facteurs_lcb=[['Pays sur la liste grise du GAFI', 20], ['Personne politiquement exposée (PPE)', 30],
                           ["Secteur d'activité sensible", 15], ['Relation établie à distance', 10]],
             criticite='elevee', criticite_score=65, impact_arret=3, dependance_pct=40, substituable=False, note_evaluation=2.5,
             beneficiaires_effectifs=[{'nom': 'Aya Kouassi', 'part': 60, 'pays': "Côte d'Ivoire", 'ppe': True}],
             structure_complexe=False, date_naissance=None, commentaire='Fournisseur stratégique', sanction_confirmee=False,
             criblages=[cr], revues=[N(created_at=datetime(2025, 10, 1), type_revue='kyc', niveau_vigilance='standard', note=None,
                                       commentaire='RAS', auteur=N(username='alice'))])


def test_tiers(app):
    from egalyx import tiers
    from models import User
    T = N(TYPES={'client': 'Client', 'fournisseur': 'Fournisseur'}, VIGILANCES={'simplifiee': 'Simplifiée', 'renforcee': 'Renforcée'})
    t = tiers_exemple()
    h = rendre(app, 'egalyx/tiers_detail.html', fiche=t, Tiers=T, STATUTS=tiers.STATUTS, CRITICITES=tiers.CRITICITES,
               IMPACTS=tiers.IMPACTS, NATURES=tiers.NATURES, CANAUX=tiers.CANAUX, bareme={})
    assert 'KOUASSI TRADING' in h and '93 %' in h and 'Renforcée' in h and '125 000 000' in h and 'en retard' in h
    h = rendre(app, 'egalyx/tiers_liste.html', tiers=[t], ind={'total': 1, 'renforcee': 1, 'revue': 1, 'criblage': 1, 'fournisseurs_critiques': 1},
               Tiers=T, type_t=None, vig=None, filtre=None, recherche='', CRITICITES=tiers.CRITICITES)
    assert 'TRS-0007' in h and 'À vérifier' in h
    h = rendre(app, 'egalyx/tiers_formulaire.html', fiche=t, NATURES=tiers.NATURES, CANAUX=tiers.CANAUX, IMPACTS=tiers.IMPACTS, Tiers=T,
               utilisateurs=User.query.all())
    assert 'Aya Kouassi' in h and 'selected' in h
    h = rendre(app, 'egalyx/tiers_formulaire.html', fiche=N(id=None, type_tiers='client', beneficiaires_effectifs=None, substituable=None),
               NATURES=tiers.NATURES, CANAUX=tiers.CANAUX, IMPACTS=tiers.IMPACTS, Tiers=T, utilisateurs=[])
    assert 'Nouveau tiers' in h
    h = rendre(app, 'egalyx/sanctions.html', sources=[('ONU', 1243, datetime(2026, 11, 1, 9, 0))])
    assert '1243' in h


def test_signature(app):
    from egalyx.signature import ROLES
    o = N(id=3, reference='AUD-2026-0003', titre="Audit des achats", client_id=1)
    d = {'libelle': "Rapport d'audit", 'titre': lambda o: o.titre, 'lien': lambda o: '/audit/3'}
    sigs = [N(id=1, signataire=N(username='alice'), signataire_id=1, role_signataire='auteur', commentaire='Version finale',
              created_at=datetime(2026, 11, 2, 15, 0), adresse_ip='41.202.1.1', methode='code_email', revoquee=False, valide=True),
            N(id=2, signataire=N(username='bob'), signataire_id=2, role_signataire='approbateur', commentaire=None,
              created_at=datetime(2026, 10, 30), adresse_ip='10.0.0.2', methode='mot_de_passe', revoquee=False, valide=False)]
    for par_email, envoye in ((True, False), (True, True), (False, False)):
        h = rendre(app, 'egalyx/signature.html', d=d, o=o, type_doc='audit', empreinte='a' * 64, signatures=sigs, ROLES=ROLES,
                   code_envoye=envoye, par_email=par_email, deja_signe=False, peut_signer=True)
        assert 'Document modifié depuis' in h and 'eIDAS' in h
        assert ('Recevoir un code' in h) == (par_email and not envoye)
        assert ('mot_de_passe' in h) == (not par_email)
    h = rendre(app, 'egalyx/signature.html', d=d, o=o, type_doc='audit', empreinte='a' * 64, signatures=sigs, ROLES=ROLES,
               code_envoye=False, par_email=True, deja_signe=False, peut_signer=False)
    assert 'permission « Signer les documents »' in h and 'Recevoir un code' not in h


def test_parametres_risque(app):
    from egalyx.parametres_risque import _defauts
    p = N(seuil_faible=5, seuil_moyen=11, seuil_eleve=17, taux=lambda: {1: 0, 2: .1, 3: .25, 4: .4, 5: .6}, appetence_score_net=10,
          appetence_par_categorie={'Financier': 6}, appetence_declaration='Aucune tolérance conformité', pays_liste_noire=['Iran'],
          pays_liste_grise=[], secteurs_sensibles=None, seuil_montant_lcb=None, listes_gafi_maj_le=date(2026, 6, 19))
    with app.test_request_context('/'):
        h = rendre(app, 'egalyx/parametres_risque.html', p=p, form=None, categories=['Financier', 'Opérationnel'],
                   defaut=_defauts(), en_erreur=False)
    assert 'value="17"' in h and 'value="6"' in h and 'Aucune tolérance' in h and 'casino' in h and '19/06/2026' in h
    h = rendre(app, 'egalyx/parametres_risque.html', p=None, form=None, categories=[], defaut=_defauts(), en_erreur=False)
    assert 'value="16"' in h and 'Corée du Nord' in h
    from werkzeug.datastructures import ImmutableMultiDict
    f = ImmutableMultiDict({'seuil_faible': '9', 'seuil_moyen': '3', 'seuil_eleve': '16', 'taux_1': '0'})
    h = rendre(app, 'egalyx/parametres_risque.html', p=None, form=f, categories=[], defaut=_defauts(), en_erreur=True)
    assert 'value="9"' in h and 'value="3"' in h


def test_pages_simples(app):
    h = rendre(app, 'egalyx/export_donnees.html', nb_tables=212)
    assert '212' in h
    e = {'nombre': 1, 'derniere': datetime.now(), 'fichiers': [{'nom': 'egalyx-20261104-021700.sqlite.gz', 'taille': 5242880,
                                                                  'date': datetime.now()}], 'en_retard': False, 'auto': True,
         'dossier': '/srv/sauvegardes', 'retention': 30}
    h = rendre(app, 'egalyx/sauvegardes.html', e=e, manquantes=[('user', 'totp_actif', 'ALTER…')])
    assert '5.0 Mo' in h and 'mettre-a-jour-base' in h
    p = N(reference='EGX1', statut='initie', formule=N(nom='Pro'), paye_le=None)
    assert 'Vérifier à nouveau' in rendre(app, 'egalyx/paiement_retour.html', p=p)


def test_organigramme(app):
    data = {'etapes': [{'id': 1, 'ordre': 1, 'nom': 'Réception de la demande', 'x': 40, 'y': 40, 'largeur': 160, 'hauteur': 60, 'couleur': '#1A3C6B', 'type': 'debut'},
                       {'id': 2, 'ordre': 2, 'nom': 'Validation budgétaire', 'x': 260, 'y': 40, 'largeur': 140, 'hauteur': 70, 'couleur': '#b54708', 'type': 'decision'},
                       {'id': 3, 'ordre': 3, 'nom': 'Émission du bon de commande', 'x': 480, 'y': 40, 'largeur': 180, 'hauteur': 60, 'couleur': '#1A3C6B', 'type': 'action'}],
            'liens': [{'source': 1, 'cible': 2, 'label': ''}, {'source': 2, 'cible': 3, 'label': 'oui'}]}
    h = rendre(app, 'egalyx/organigramme_editeur.html', processus=N(id=9, nom='Achats'), donnees=data)
    assert 'Validation budg' in h and '/api/processus/9/organigramme' in h


def test_compte_et_publics(app):
    u = models.User.query.get(1)
    u.totp_actif, u.totp_active_le, u.totp_codes_secours = True, datetime(2026, 11, 1), ['h'] * 2
    h = rendre(app, 'egalyx/securite_compte.html', u=u, obligatoire=True, codes_restants=2,
               fournisseurs_sso=[{'code': 'microsoft', 'nom': 'Microsoft', 'icone': 'fab fa-microsoft'}])
    assert 'générez-en de nouveaux' in h and 'Obligatoire pour les administrateurs' in h and 'Microsoft' in h
    h = rendre(app, 'egalyx/2fa_activer.html', secret='JBSWY3DPEHPK3PXPJBSWY3DP', uri='otpauth://totp/x', obligatoire=True)
    assert 'JBSW Y3DP' in h and 'qrcode' in h
    assert 'Vérification en deux étapes' in rendre(app, 'egalyx/2fa_verification.html')


def test_gabarits_modifies(app):
    """Pages existantes touchées en v4 : la partie ajoutée se rend correctement."""
    import egalyx.sso as sso
    os.environ.update(SSO_GOOGLE_CLIENT_ID='a', SSO_GOOGLE_CLIENT_SECRET='b')
    try:
        h = rendre(app, '_partials/boutons_sso.html')
        assert 'Continuer avec Google' in h and '/sso/google' in h
    finally:
        del os.environ['SSO_GOOGLE_CLIENT_ID'], os.environ['SSO_GOOGLE_CLIENT_SECRET']
    assert rendre(app, '_partials/boutons_sso.html').strip() == ''
    h = rendre(app, '_partials/bandeau_signature.html', type_doc='audit', doc_id=3)
    assert 'document modifié après 1 signature' in h
    h = rendre(app, 'securite.html')
    for interdit in ('SOC 2', 'Bug bounty', 'AES-256', 'Datacenters certifiés', "Tests d'intrusion"):
        assert interdit not in h, interdit
    assert 'Double authentification' in h and 'Sauvegardes quotidiennes' in h
