"""Connecteurs de l'analyse de données : contrôles sans réseau."""
from datetime import date

import pytest

from egalyx import analyse_connecteurs as ac


@pytest.mark.parametrize('sql,ok', [('SELECT * FROM t', True), ('with a as (select 1) select * from a', True), ('UPDATE t SET a = 1', False),
                                    ('SELECT 1; DROP TABLE t', False), ('SELECT * INTO x FROM t', False), ("SELECT 'delete' FROM t", True),
                                    ('select * from t -- ; drop', True), ('EXEC sp_who', False)])
def test_requetes_lecture_seule(sql, ok):
    if ok:
        ac.verifier_requete(sql)
    else:
        with pytest.raises(ac.ErreurSource):
            ac.verifier_requete(sql)


def test_periodes_glissantes():
    j = date(2026, 2, 10)
    assert ac.periode('mois_precedent', j) == (date(2026, 1, 1), date(2026, 1, 31))
    assert ac.periode('trimestre_precedent', j) == (date(2025, 10, 1), date(2025, 12, 31))
    assert ac.periode('annee_precedente', j) == (date(2025, 1, 1), date(2025, 12, 31))


def test_domaines_officiels():
    with pytest.raises(ac.ErreurSource):
        ac.verifier_url('https://api.xero.com.pirate.net/x', ac.XERO_DOMAINES)
    with pytest.raises(ac.ErreurSource):
        ac.verifier_url('http://api.xero.com/x', ac.XERO_DOMAINES)
    assert ac.verifier_url('https://api.xero.com/api.xro/2.0/Invoices', ac.XERO_DOMAINES)


def test_tableau_aux_colonnes_de_l_outil():
    e = ac.tableau('paiements', [{'reference': 'P1', 'fournisseur': 'F1', 'date': '2026-01-05', 'montant': 10.0, 'rib': 'CI0012345678'}])
    assert e.correspondance['montant'] == 'Montant payé' and e.lignes == [['P1', 'F1', '2026-01-05', 10.0, 'CI0012345678']]
    assert e.en_octets().decode().splitlines()[0].startswith('Référence du paiement;')
