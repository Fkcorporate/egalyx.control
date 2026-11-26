"""Jeu de données fictif « achats, fournisseurs, paiements » avec anomalies connues (recette et démonstration).

Toutes les données sont inventées. Chaque anomalie plantée est listée dans ATTENDU pour vérifier les tests.
"""
import csv
import io
import random
from datetime import date, timedelta

ATTENDU = {
    'FAC_DOUBLON': {'FA-0100', 'FA-0100-B'},
    'FAC_NUMERO': {'FA-0200'},
    'PAI_DOUBLON': {'VIR-0300', 'VIR-0300-B'},
    'PAI_SANS_FACTURE': {'VIR-SANS'},
    'PAI_SUP_FACTURE': {'VIR-0400', 'VIR-0400-B'},
    'BC_APRES_FACTURE': {'FA-0500', 'FA-0501', 'FA-0502'},
    'FRACTIONNEMENT': {'BC-FR-1', 'BC-FR-2', 'BC-FR-3'},
    'SEPARATION': {'VIR-SEP'},
    'RIB_PARTAGE': {'F012', 'F059'},
    'RIB_SALARIE': {'F060'},
    'RIB_PAIEMENT': {'VIR-RIB'},
    'RIB_MODIFIE': {'VIR-MOD'},
    'FOURN_RECENT': {'VIR-NEW'},
    'FOURN_INCONNU': {'VIR-INC', 'VIR-BLQ'},
    'WEEKEND': {'VIR-WE'},
    'DELEGATION': {'VIR-DEL', 'BC-SANS-APP'},
    'PRIX_UNITAIRE': {'BC-PRIX'},
}


def _jour_ouvre(rng, debut=date(2026, 1, 5), fin=date(2026, 6, 26)):
    while True:
        d = debut + timedelta(days=rng.randint(0, (fin - debut).days))
        if d.weekday() < 5:
            return d


def _rib(n):
    return f'CI{n:03d} 0{n % 9 + 1}001 {n:012d} {n % 97:02d}'


def generer(graine=42):
    rng = random.Random(graine)
    fournisseurs, factures, paiements, commandes, salaries = [], [], [], [], []
    for i in range(1, 61):
        fournisseurs.append({'Code fournisseur': f'F{i:03d}', 'Raison sociale': f'FOURNISSEUR {i:03d} SARL', 'RIB': _rib(1000 + i),
                             'Date de création': date(2023, 1, 1) + timedelta(days=i * 7), 'Créé par': 'K. Yao',
                             'Date modification RIB': None, 'Téléphone': f'+225 07 10 {i:02d} {i:02d} {i:02d}',
                             'Adresse': f'Lot {i}, zone industrielle de Yopougon', 'Statut': 'Actif'})
    fo = {f['Code fournisseur']: f for f in fournisseurs}
    fo['F059']['RIB'] = fo['F012']['RIB']                       # RIB partagé
    fo['F058']['Date de création'] = date(2026, 3, 2)           # fournisseur récent payé vite
    fo['F057']['Date modification RIB'] = date(2026, 4, 10)     # RIB modifié avant paiement
    fo['F056']['Statut'] = 'Bloqué'                             # fournisseur bloqué payé
    fo['F055']['Créé par'] = 'S. Diallo'                        # crée puis approuve
    for i in range(1, 41):
        salaries.append({'Matricule': f'M{i:04d}', 'Nom et prénom': f'SALARIÉ {i:02d}', 'RIB': _rib(5000 + i),
                         'Téléphone': f'+225 05 20 {i:02d} {i:02d} {i:02d}', 'Adresse': f'Cité {i}, Cocody', 'Date de sortie': None})
    fo['F060']['RIB'] = salaries[4]['RIB']                      # fournisseur = salarié

    articles = [('Ramette papier A4', 2950), ('Cartouche toner', 59000), ('Carburant (litre)', 875), ('Gants nitrile (boîte)', 4500)]
    codes = [f'F{i:03d}' for i in range(1, 55)]
    n = 0
    for k in range(1, 1101):
        n += 1
        f = rng.choice(codes)
        d = _jour_ouvre(rng)
        mt = round(10 ** rng.uniform(4.0, 7.0), -1)              # répartition naturelle (Benford)
        num = f'FA-{k:04d}'
        bc = f'BC-{k:04d}' if rng.random() > 0.04 else ''
        if bc:
            art, pu = rng.choice(articles)
            pu_reel = round(pu * rng.uniform(0.95, 1.08))
            commandes.append({'N° commande': bc, 'Fournisseur': f, 'Date': d - timedelta(days=rng.randint(3, 20)), 'Montant': mt,
                              'Approuvé par': 'D. Kouassi', 'Article': art, 'Quantité': max(1, round(mt / pu_reel)), 'Prix unitaire': pu_reel})
        factures.append({'N° facture': num, 'Code fournisseur': f, 'Date facture': d, 'Montant TTC': mt, 'Bon de commande': bc,
                         'Date de saisie': d + timedelta(days=1 if d.weekday() < 4 else 3), 'Saisi par': 'M. Traoré'})
        pd_ = d + timedelta(days=rng.randint(10, 40))
        while pd_.weekday() >= 5:
            pd_ += timedelta(days=1)
        paiements.append({'Référence': f'VIR-{k:04d}', 'Fournisseur': f, 'Date paiement': pd_, 'Montant': mt, 'RIB bénéficiaire': fo[f]['RIB'],
                          'Approuvé par': 'S. Diallo' if mt <= 10_000_000 else 'Direction générale', 'N° facture': num, 'Mode': 'Virement'})
    fa = {x['N° facture']: x for x in factures}
    pa = {x['Référence']: x for x in paiements}
    co = {x['N° commande']: x for x in commandes}

    def facture(num, f, d, mt, bc=''):
        factures.append({'N° facture': num, 'Code fournisseur': f, 'Date facture': d, 'Montant TTC': mt, 'Bon de commande': bc,
                         'Date de saisie': d, 'Saisi par': 'M. Traoré'})

    def paiement(ref, f, d, mt, num, rib=None, app='S. Diallo'):
        paiements.append({'Référence': ref, 'Fournisseur': f, 'Date paiement': d, 'Montant': mt, 'RIB bénéficiaire': rib or fo.get(f, {}).get('RIB', _rib(9999)),
                          'Approuvé par': app, 'N° facture': num, 'Mode': 'Virement'})

    # Factures en double (même fournisseur, même montant, 3 jours d'écart)
    fa['FA-0100'].update({'Code fournisseur': 'F010', 'Montant TTC': 3_456_780, 'Date facture': date(2026, 2, 9)})
    facture('FA-0100-B', 'F010', date(2026, 2, 12), 3_456_780)
    # Même numéro saisi deux fois (montants différents)
    fa['FA-0200'].update({'Code fournisseur': 'F011'})
    facture('FA-0200', 'F011', fa['FA-0200']['Date facture'] + timedelta(days=60), 987_650)
    # Paiement en double
    pa['VIR-0300'].update({'Fournisseur': 'F013', 'Montant': 2_345_670, 'Date paiement': date(2026, 3, 16), 'RIB bénéficiaire': fo['F013']['RIB']})
    fa['FA-0300'].update({'Code fournisseur': 'F013', 'Montant TTC': 2_345_670})
    paiement('VIR-0300-B', 'F013', date(2026, 3, 19), 2_345_670, 'FA-0300')
    # Paiement sans facture
    paiement('VIR-SANS', 'F014', date(2026, 4, 7), 1_234_560, '')
    # Facture payée au-delà de son montant
    fa['FA-0400'].update({'Code fournisseur': 'F015', 'Montant TTC': 4_000_000})
    pa['VIR-0400'].update({'Fournisseur': 'F015', 'Montant': 2_500_000, 'RIB bénéficiaire': fo['F015']['RIB']})
    paiement('VIR-0400-B', 'F015', date(2026, 5, 12), 2_500_010, 'FA-0400')
    # Commandes postérieures à la facture
    for num in ('FA-0500', 'FA-0501', 'FA-0502'):
        bc = fa[num]['Bon de commande'] or f'BC-REG-{num}'
        fa[num]['Bon de commande'] = bc
        if bc in co:
            co[bc]['Date'] = fa[num]['Date facture'] + timedelta(days=6)
        else:
            commandes.append({'N° commande': bc, 'Fournisseur': fa[num]['Code fournisseur'], 'Date': fa[num]['Date facture'] + timedelta(days=6),
                              'Montant': fa[num]['Montant TTC'], 'Approuvé par': 'D. Kouassi', 'Article': '', 'Quantité': None, 'Prix unitaire': None})
    # Fractionnement : 3 commandes de F020 sous 5 M en 5 jours
    for j, (mt, dd) in enumerate(((1_800_000, 4), (1_900_000, 6), (1_700_000, 8)), 1):
        commandes.append({'N° commande': f'BC-FR-{j}', 'Fournisseur': 'F054', 'Date': date(2026, 5, dd), 'Montant': mt,
                          'Approuvé par': 'D. Kouassi', 'Article': '', 'Quantité': None, 'Prix unitaire': None})
    # Séparation des tâches : S. Diallo a créé F055 et approuve son paiement
    paiement('VIR-SEP', 'F055', date(2026, 4, 22), 845_000, '')
    # Fournisseur payé sur un autre compte
    paiement('VIR-RIB', 'F030', date(2026, 4, 23), 1_675_430, '', rib='CI999 09999 000000999999 99')
    # RIB modifié 5 jours avant paiement
    paiement('VIR-MOD', 'F057', date(2026, 4, 15), 3_120_000, '')
    # Fournisseur créé le 02/03, payé le 06/03
    paiement('VIR-NEW', 'F058', date(2026, 3, 6), 2_210_000, '')
    # Fournisseur inconnu ; fournisseur bloqué
    paiement('VIR-INC', 'F999', date(2026, 5, 20), 1_980_000, '', rib='CI888 08888 000000888888 88')
    paiement('VIR-BLQ', 'F056', date(2026, 5, 21), 760_000, '')
    # Paiement un samedi
    paiement('VIR-WE', 'F016', date(2026, 6, 13), 1_115_000, '')
    # Délégation : S. Diallo (plafond 10 M) approuve 15 M ; commande de 6 M sans approbateur
    paiement('VIR-DEL', 'F017', date(2026, 6, 10), 15_000_000, '')
    commandes.append({'N° commande': 'BC-SANS-APP', 'Fournisseur': 'F018', 'Date': date(2026, 6, 2), 'Montant': 6_000_000,
                      'Approuvé par': '', 'Article': '', 'Quantité': None, 'Prix unitaire': None})
    # Prix unitaire anormal
    commandes.append({'N° commande': 'BC-PRIX', 'Fournisseur': 'F019', 'Date': date(2026, 6, 3), 'Montant': 450_000,
                      'Approuvé par': 'D. Kouassi', 'Article': 'Ramette papier A4', 'Quantité': 100, 'Prix unitaire': 4500})
    return {'fournisseurs': fournisseurs, 'factures': factures, 'paiements': paiements, 'commandes': commandes, 'salaries': salaries}


def _fr_montant(x):
    return '' if x is None else f'{x:,.0f}'.replace(',', ' ')


def en_csv(lignes):
    """CSV « à la française » : point-virgule, dates jj/mm/aaaa, montants avec espaces."""
    out = io.StringIO()
    w = csv.writer(out, delimiter=';')
    entetes = list(lignes[0])
    w.writerow(entetes)
    for l in lignes:
        w.writerow([v.strftime('%d/%m/%Y') if isinstance(v, date) else _fr_montant(v) if isinstance(v, (int, float)) else (v or '') for v in l.values()])
    return out.getvalue().encode('cp1252', errors='replace')


def en_xlsx(lignes, feuille='Données'):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = feuille
    ws.append(['Extraction du logiciel comptable — données fictives'])
    ws.append([])
    ws.append(list(lignes[0]))
    for l in lignes:
        ws.append(list(l.values()))
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()
