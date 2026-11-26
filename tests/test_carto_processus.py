"""Cartographie des processus : règles d'activation du module et calculs de la carte (sans base de données)."""
from datetime import date, timedelta
from types import SimpleNamespace as NS

from egalyx import carto_processus as CP
from egalyx import modules_client as MC


def test_module_au_catalogue_et_sur_activation():
    assert 'carto_processus' in MC.MODULES
    assert MC.MODULE_DE_PERMISSION['can_view_carto_processus'] == 'carto_processus'
    assert MC.MODULE_DE_PERMISSION['can_manage_carto_processus'] == 'carto_processus'
    assert 'carto_processus' in MC.SUR_ACTIVATION
    assert 'carto_processus' in MC.PROFILS['complet'][2]


def test_ferme_sans_choix_explicite_du_super_admin():
    u = NS(client=NS(modules_actifs=None, formule=None))
    assert MC.permission_autorisee_par_module(u, 'can_view_carto_processus') is False
    assert MC.permission_autorisee_par_module(u, 'can_manage_risks') is True          # les autres modules : inchangé
    formule = NS(modules={'cartographie': True, 'audit_interne': True})
    u = NS(client=NS(modules_actifs=None, formule=formule))
    assert 'carto_processus' not in MC.modules_du_client(u.client)
    assert MC.permission_autorisee_par_module(u, 'can_view_carto_processus') is False
    assert 'carto_processus' not in MC.modules_depuis_formule(formule)
    assert 'carto_processus' not in MC.modules_depuis_formule(None)
    u = NS(client=NS(modules_actifs={'cartographie': True}, formule=None))              # choix fait avant le module
    assert MC.permission_autorisee_par_module(u, 'can_view_carto_processus') is False


def test_ouvert_quand_le_super_admin_l_a_coche():
    u = NS(client=NS(modules_actifs={'cartographie': True, 'carto_processus': True}, formule=None))
    assert MC.permission_autorisee_par_module(u, 'can_view_carto_processus') is True
    u = NS(client=NS(modules_actifs={'cartographie': True, 'carto_processus': False}, formule=None))
    assert MC.permission_autorisee_par_module(u, 'can_manage_carto_processus') is False


def test_niveaux_de_risque_libres():
    assert CP.rang_niveau('Critique') == 4
    assert CP.rang_niveau('ÉLEVÉ') == 3 and CP.rang_niveau('Très élevé') == 3 and CP.rang_niveau('Fort') == 3
    assert CP.rang_niveau('Moyen') == 2 and CP.rang_niveau('Modéré') == 2
    assert CP.rang_niveau('faible') == 1 and CP.rang_niveau('Négligeable') == 1
    assert CP.rang_niveau(None) == 0 and CP.rang_niveau('') == 0 and CP.rang_niveau('?') == 0


def test_couverture_d_audit():
    j = date(2026, 11, 25)
    assert CP.couverture(None, j)[0] == 'jamais'
    assert CP.couverture(j - timedelta(days=100), j)[0] == 'recent'
    assert CP.couverture(j - timedelta(days=500), j)[0] == 'ancien'
    assert CP.couverture(j - timedelta(days=1500), j)[0] == 'tres_ancien'


def test_reglages_nettoyes():
    r = CP.normaliser({'titre': '  Carte   ' + 'x' * 300, 'bandes': {'pilotage': '', 'support': 'Supports', 'inconnue': 'z'},
                       'ordre': {'pilotage': [3, '4', 'a'], 'pirate': [1]},
                       'flux': [{'de': 1, 'vers': 1}, {'de': '2', 'vers': 3, 'libelle': 'données ' * 30}, {'de': 'x'}],
                       'sous_processus': False})
    assert len(r['titre']) == CP.LONGUEUR['titre'] and r['titre'].startswith('Carte x')
    assert r['bandes']['pilotage'] == 'Processus de pilotage' and r['bandes']['support'] == 'Supports' and 'inconnue' not in r['bandes']
    assert r['ordre'] == {'pilotage': [3, 4]}
    assert len(r['flux']) == 1 and r['flux'][0]['de'] == 2 and len(r['flux'][0]['libelle']) <= CP.LONGUEUR['flux']
    assert r['sous_processus'] is False
    assert CP.normaliser(None)['entree'] == CP.DEFAUT['entree']


def test_modeles_types_coherents():
    for code, (nom, lignes) in CP.MODELES.items():
        codes = [l[1] for l in lignes]
        assert len(codes) == len(set(codes)), code
        assert {l[0] for l in lignes} <= set(CP.TYPE_DE_BANDE), code
        assert {'pilotage', 'realisation', 'support'} <= {l[0] for l in lignes}, code
