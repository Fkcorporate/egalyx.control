"""Moteur de l'analyse des données d'audit (egalyx/analyse_moteur.py) : lecture, normalisation, tests."""
import io
from datetime import date

import pandas as pd

from egalyx import analyse_moteur as am


def _csv(lignes):
    return ('\n'.join(';'.join(l) for l in lignes)).encode('utf-8')


def test_montants_formats_courants():
    assert am.lire_montant('1 250 000 FCFA') == 1250000.0
    assert am.lire_montant('1.250.000') == 1250000.0
    assert am.lire_montant('1,250,000') == 1250000.0
    assert am.lire_montant('1 234,56', ',') == 1234.56
    assert am.lire_montant('1,234.56', '.') == 1234.56
    assert am.lire_montant('-300') == -300.0
    assert am.lire_montant('(300)') == -300.0
    assert am.lire_montant('') is None
    assert am.lire_montant('n/a') == 'ERREUR'


def test_dates_jour_mois_jamais_devinees():
    assert am.lire_date('05/03/2026') == date(2026, 3, 5)
    assert am.lire_date('2026-03-05') == date(2026, 3, 5)
    assert am.lire_date('05-03-26') == date(2026, 3, 5)
    assert am.lire_date(46086) == date(2026, 3, 5)
    assert am.lire_date('13/13/2026') == 'ERREUR'
    assert am.lire_date('') is None


def test_lecture_csv_et_correspondance():
    octets = _csv([['N° facture', 'Code fournisseur', 'Date facture', 'Montant TTC'], ['FA1', 'F1', '05/03/2026', '1 000'],
                   ['FA2', 'F1', '07/03/2026', '1 000']])
    e, _l, inf = am.lire_fichier(octets, 'f.csv')
    corr = am.proposer_correspondance('factures', e)
    assert corr == {'numero': 'N° facture', 'fournisseur': 'Code fournisseur', 'date': 'Date facture', 'montant': 'Montant TTC'}
    df, q = am.normaliser('factures', e, inf['lignes_brutes'], corr, inf['premiere_ligne'])
    assert q['lignes'] == 2 and q['total'] == 2000.0 and list(df['_ligne']) == [2, 3]
    df2 = am.depuis_octets('factures', am.vers_octets(df))
    assert df2['date'].iloc[0] == pd.Timestamp('2026-03-05') and df2['montant'].sum() == 2000.0


def test_doublons_et_non_applicable():
    octets = _csv([['N° facture', 'Code fournisseur', 'Date facture', 'Montant TTC'], ['FA1', 'F1', '05/03/2026', '1 000'],
                   ['FA1-bis', 'F1', '07/03/2026', '1 000'], ['FA3', 'F2', '07/03/2026', '1 000']])
    e, _l, inf = am.lire_fichier(octets, 'f.csv')
    df, _q = am.normaliser('factures', e, inf['lignes_brutes'], am.proposer_correspondance('factures', e), inf['premiere_ligne'])
    r = am.executer({'factures': df}, ['FAC_DOUBLON', 'RIB_PARTAGE'])
    assert r['FAC_DOUBLON']['statut'] == 'anomalies' and r['FAC_DOUBLON']['cas'] == 1 and r['FAC_DOUBLON']['nb'] == 2
    assert r['RIB_PARTAGE']['statut'] == 'non_applicable' and 'fournisseurs' in r['RIB_PARTAGE']['raison']


def test_resultat_reproductible_et_echantillon():
    octets = _csv([['N° facture', 'Code fournisseur', 'Date facture', 'Montant TTC']]
                  + [[f'FA{i}', f'F{i % 7}', f'{1 + i % 28:02d}/03/2026', str(1000 + i * 37)] for i in range(200)])
    e, _l, inf = am.lire_fichier(octets, 'f.csv')
    df, _q = am.normaliser('factures', e, inf['lignes_brutes'], am.proposer_correspondance('factures', e), inf['premiere_ligne'])
    choix = [t['code'] for t in am.TESTS]
    assert am.executer({'factures': df}, choix) == am.executer({'factures': df}, choix)
    e1, g = am.tirer_echantillon(df, 'factures', 15, 'aleatoire', 77)
    e2, _ = am.tirer_echantillon(df, 'factures', 15, 'aleatoire', g)
    assert g == 77 and [x['ref'] for x in e1] == [x['ref'] for x in e2] and len(e1) == 15


def test_grand_livre_fec_et_cloture():
    lignes = ['JournalCode\tEcritureNum\tEcritureDate\tCompteNum\tEcritureLib\tDebit\tCredit\tValidDate',
              'OD\t1\t20251229\t411100\tFacture a etablir\t8000000,00\t0,00\t20251229',
              'OD\t1\t20251229\t701100\tFacture a etablir\t0,00\t8000000,00\t20251229',
              'OD\t2\t20260105\t701100\tAnnulation\t8000000,00\t0,00\t20260105',
              'OD\t2\t20260105\t411100\tAnnulation\t0,00\t8000000,00\t20260105',
              'OD\t3\t20250310\t471100\tA identifier\t500000,00\t0,00\t20250310',
              'OD\t3\t20250310\t521100\tA identifier\t0,00\t490000,00\t20250310']
    e, _l, inf = am.lire_fichier('\n'.join(lignes).encode(), 'FEC.txt')
    corr = am.proposer_correspondance('grand_livre', e)
    assert not am.obligatoires_manquants('grand_livre', corr)
    df, q = am.normaliser('grand_livre', e, inf['lignes_brutes'], corr, inf['premiere_ligne'])
    codes = ['GL_DESEQUILIBRE', 'GL_EXTOURNES', 'GL_ATTENTE']
    sans = am.executer({'grand_livre': df}, codes)
    assert sans['GL_EXTOURNES']['statut'] == 'non_applicable'
    r = am.executer({'grand_livre': df}, codes, cloture=date(2025, 12, 31))
    assert r['GL_EXTOURNES']['cas'] == 1 and r['GL_DESEQUILIBRE']['nb'] == 1 and r['GL_ATTENTE']['anomalies'][0]['ref'] == '471100'
