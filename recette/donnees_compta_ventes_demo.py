"""Jeu de données fictif « comptabilité, ventes et encaissements » (exercice 2025, clôture au 31/12/2025)
avec anomalies connues (recette et démonstration). Toutes les données sont inventées."""
import csv
import io
import random
from datetime import date, datetime, timedelta

CLOTURE = date(2025, 12, 31)
FERIES = {(1, 1), (5, 1), (8, 7), (8, 15), (11, 1), (11, 15), (12, 25)}
ATTENDU = {
    'GL_DESEQUILIBRE': {'OD-DES'},
    'GL_DOUBLON': {'ACH-D1', 'ACH-D2'},
    'GL_SANS_PIECE': {'OD-SP'},
    'GL_HORS_HEURES': {'OD-NUIT', 'OD-DIM'},
    'GL_APRES_CLOTURE': {'OD-TARD'},
    'GL_SENSIBLES': {'OD-CAI'},
    'GL_ATTENTE': {'471100'},
    'GL_UTILISATEURS': {'OD-ADM'},
    'GL_RONDS': {'OD-RND'},
    'GL_EXTOURNES': {'OD-EXT1', 'OD-EXT2'},
    'VTE_NUMEROTATION': {'FV-2025-0415', 'FV-2025-0500'},
    'VTE_AVOIRS_CLOTURE': {'AV-2025-001'},
    'VTE_AVOIR_ORIGINE': {'AV-2025-002', 'AV-2025-003'},
    'VTE_REMISES': {'FV-2025-0300'},
    'VTE_CLIENT_BLOQUE': {'FV-2025-0450', 'FV-2025-0600'},
    'VTE_CREDIT': {'C010'},
    'VTE_CUT_OFF': {'FV-2025-0795', 'AV-2025-001'},
    'ENC_NON_LETTRES': {'ENC-SANS', 'ENC-INC', 'ENC-SUP'},
}


def _ouvre(rng, debut=date(2025, 1, 2), fin=date(2025, 12, 30)):
    while True:
        d = debut + timedelta(days=rng.randint(0, (fin - debut).days))
        if d.weekday() < 5 and (d.month, d.day) not in FERIES:
            return d


def _saisie(rng, d):
    s = d + timedelta(days=rng.randint(0, 2))
    while s.weekday() >= 5 or (s.month, s.day) in FERIES:
        s += timedelta(days=1)
    return datetime(s.year, s.month, s.day, rng.randint(8, 17), rng.randint(0, 59))


def generer(graine=7):
    rng = random.Random(graine)
    gl, n = [], [0]
    users = ['M. Traoré', 'A. Koné', 'K. Yao']

    def ecriture(journal, d, lignes, libelle, num=None, piece=None, qui=None, saisie=None):
        n[0] += 1
        num = num or f'{journal}-{n[0]:06d}'
        piece = f'PJ-{n[0]:06d}' if piece is None else piece
        s = saisie or _saisie(rng, d)
        for compte, debit, credit in lignes:
            gl.append({'N° écriture': num, 'Date': d, 'Compte': compte, 'Débit': debit or None, 'Crédit': credit or None, 'Libellé': libelle,
                       'Journal': journal, 'Pièce': piece, 'Saisi par': qui or rng.choice(users), 'Date de saisie': s})

    for _ in range(1300):
        d = _ouvre(rng)
        ttc = round(10 ** rng.uniform(4.0, 7.0))
        ht = round(ttc / 1.18)
        t = rng.random()
        if t < 0.35:
            ecriture('ACH', d, [(rng.choice(['601100', '605200', '622400', '624100']), ht, 0), ('445200', ttc - ht, 0), ('401100', 0, ttc)], f'Facture fournisseur {rng.randint(100, 999)}')
        elif t < 0.65:
            ecriture('VTE', d, [('411100', ttc, 0), ('701100', 0, ht), ('443100', 0, ttc - ht)], f'Facture client {rng.randint(100, 999)}')
        elif t < 0.8:
            ecriture('BQ', d, [('401100', ttc, 0), ('521100', 0, ttc)], 'Règlement fournisseur')
        elif t < 0.95:
            ecriture('BQ', d, [('521100', ttc, 0), ('411100', 0, ttc)], 'Encaissement client')
        else:
            petit = round(10 ** rng.uniform(3.0, 5.0))
            ecriture('CAI', d, [('605100', petit, 0), ('571100', 0, petit)], 'Dépense de caisse')
    # anomalies plantées
    ecriture('OD', date(2025, 4, 8), [('658100', 1_000_000, 0), ('521100', 0, 990_000)], 'Régularisation frais bancaires', num='OD-DES')
    for k in ('ACH-D1', 'ACH-D2'):
        ecriture('ACH', date(2025, 5, 14), [('605200', 1_987_797, 0), ('445200', 357_803, 0), ('401100', 0, 2_345_600)], 'Entretien climatisation FA-778', num=k)
    ecriture('OD', date(2025, 7, 3), [('658100', 640_000, 0), ('401100', 0, 640_000)], 'Divers', num='OD-SP', piece='')
    ecriture('OD', date(2025, 6, 11), [('622400', 1_250_000, 0), ('401100', 0, 1_250_000)], 'Loyer complémentaire', num='OD-NUIT', saisie=datetime(2025, 6, 11, 23, 40))
    ecriture('OD', date(2025, 9, 12), [('628100', 830_000, 0), ('401100', 0, 830_000)], 'Frais de mission', num='OD-DIM', saisie=datetime(2025, 9, 14, 10, 5))
    ecriture('OD', CLOTURE, [('603100', 4_500_000, 0), ('311100', 0, 4_500_000)], 'Variation de stocks', num='OD-TARD', saisie=datetime(2026, 3, 15, 10, 0))
    ecriture('OD', date(2025, 10, 22), [('658100', 2_500_000, 0), ('571100', 0, 2_500_000)], 'Sortie de caisse', num='OD-CAI')
    ecriture('OD', date(2025, 3, 17), [('471100', 3_000_000, 0), ('521100', 0, 3_000_000)], 'Virement à identifier', num='OD-ATT')
    ecriture('OD', date(2025, 8, 20), [('628100', 415_000, 0), ('401100', 0, 415_000)], 'Frais divers fournisseur', num='OD-ADM', qui='admin')
    ecriture('OD', date(2025, 11, 28), [('659100', 50_000_000, 0), ('499100', 0, 50_000_000)], 'Provision pour risques', num='OD-RND')
    ecriture('OD', date(2025, 12, 29), [('411100', 8_000_000, 0), ('701100', 0, 8_000_000)], 'Facture à établir client C033', num='OD-EXT1')
    ecriture('OD', date(2026, 1, 5), [('701100', 8_000_000, 0), ('411100', 0, 8_000_000)], 'Annulation facture à établir C033', num='OD-EXT2')

    # ventes, clients, encaissements
    clients = [{'Code client': f'C{i:03d}', 'Raison sociale': f'CLIENT {i:03d} SA', 'Statut': 'Actif', 'Limite de crédit': 200_000_000,
                'Date de création': date(2022, 1, 1) + timedelta(days=i * 9)} for i in range(1, 81)]
    clients[76]['Statut'] = 'Bloqué'                         # C077
    clients[9]['Limite de crédit'] = 5_000_000               # C010
    dates = sorted(_ouvre(rng, date(2025, 1, 3), date(2025, 12, 26)) for _ in range(800))
    ventes, encaissements = [], []
    for k, d in enumerate(dates, 1):
        if 412 <= k <= 414:
            continue                                          # trou dans la numérotation
        num = f'FV-2025-{k:04d}'
        cl = 'C010' if k % 80 == 10 else f'C{rng.randint(11, 76):03d}'
        mt = round(10 ** rng.uniform(5.0, 6.8), -2)
        ventes.append({'N° facture': num, 'Code client': cl, 'Date': d, 'Montant TTC': mt, 'Type': 'Facture', 'Facture d’origine': '',
                       'Remise %': rng.choice([0, 0, 0, 2, 3, 5]), 'Vendeur': rng.choice(['B. Ouattara', 'F. Kouamé'])})
        if cl != 'C010':
            encaissements.append({'Référence': f'ENC-{k:04d}', 'Code client': cl, 'Date': d + timedelta(days=rng.randint(15, 45)), 'Montant': mt,
                                  'N° facture': num, 'Mode': rng.choice(['Virement', 'Chèque', 'Mobile money'])})
    v = {x['N° facture']: x for x in ventes}
    v['FV-2025-0300']['Remise %'] = 25
    v['FV-2025-0450']['Code client'] = 'C077'
    v['FV-2025-0600']['Code client'] = 'C099'
    v['FV-2025-0795'].update({'Date': date(2025, 12, 29), 'Code client': 'C033', 'Montant TTC': 8_000_000})
    ventes.append(dict(v['FV-2025-0500'], **{'Code client': 'C012', 'Montant TTC': 777_700}))      # numéro attribué deux fois
    ventes.append({'N° facture': 'AV-2025-001', 'Code client': 'C033', 'Date': date(2026, 1, 5), 'Montant TTC': -8_000_000, 'Type': 'Avoir',
                   'Facture d’origine': 'FV-2025-0795', 'Remise %': None, 'Vendeur': 'B. Ouattara'})
    ventes.append({'N° facture': 'AV-2025-002', 'Code client': 'C020', 'Date': date(2025, 6, 10), 'Montant TTC': -1_200_000, 'Type': 'Avoir',
                   'Facture d’origine': '', 'Remise %': None, 'Vendeur': 'F. Kouamé'})
    o = v['FV-2025-0100']
    ventes.append({'N° facture': 'AV-2025-003', 'Code client': o['Code client'], 'Date': o['Date'] + timedelta(days=20), 'Montant TTC': -(o['Montant TTC'] + 500_000),
                   'Type': 'Avoir', 'Facture d’origine': 'FV-2025-0100', 'Remise %': None, 'Vendeur': 'F. Kouamé'})
    encaissements = [e for e in encaissements if e['N° facture'] != 'FV-2025-0795']
    encaissements.append({'Référence': 'ENC-SANS', 'Code client': 'C021', 'Date': date(2025, 9, 9), 'Montant': 1_450_000, 'N° facture': '', 'Mode': 'Espèces'})
    encaissements.append({'Référence': 'ENC-INC', 'Code client': 'C022', 'Date': date(2025, 9, 10), 'Montant': 980_000, 'N° facture': 'FV-2025-9999', 'Mode': 'Chèque'})
    encaissements.append({'Référence': 'ENC-SUP', 'Code client': v['FV-2025-0200']['Code client'], 'Date': date(2025, 9, 11), 'Montant': 500_000,
                          'N° facture': 'FV-2025-0200', 'Mode': 'Virement'})
    return {'grand_livre': gl, 'ventes': ventes, 'clients': clients, 'encaissements': encaissements}


def _txt(v, sep_dec=','):
    if v is None:
        return ''
    if isinstance(v, datetime):
        return v.strftime('%d/%m/%Y %H:%M')
    if isinstance(v, date):
        return v.strftime('%d/%m/%Y')
    if isinstance(v, (int, float)):
        return f'{v:,.0f}'.replace(',', ' ')
    return str(v)


def en_csv(lignes):
    out = io.StringIO()
    w = csv.writer(out, delimiter=';')
    w.writerow(list(lignes[0]))
    for l in lignes:
        w.writerow([_txt(x) for x in l.values()])
    return out.getvalue().encode('cp1252', errors='replace')


def en_xlsx(lignes):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(list(lignes[0]))
    for l in lignes:
        ws.append(list(l.values()))
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def en_fec(gl):
    """Fichier des écritures comptables (FEC) : tabulations, dates AAAAMMJJ, virgule décimale, 18 colonnes."""
    entetes = ['JournalCode', 'JournalLib', 'EcritureNum', 'EcritureDate', 'CompteNum', 'CompteLib', 'CompAuxNum', 'CompAuxLib', 'PieceRef',
               'PieceDate', 'EcritureLib', 'Debit', 'Credit', 'EcritureLet', 'DateLet', 'ValidDate', 'Montantdevise', 'Idevise']
    lignes = ['\t'.join(entetes)]
    for l in gl:
        dm = lambda x: f'{x:.2f}'.replace('.', ',') if x else '0,00'
        lignes.append('\t'.join([l['Journal'], l['Journal'], l['N° écriture'], l['Date'].strftime('%Y%m%d'), l['Compte'], '', '', '', l['Pièce'],
                                 l['Date'].strftime('%Y%m%d'), l['Libellé'], dm(l['Débit']), dm(l['Crédit']), '', '',
                                 l['Date de saisie'].strftime('%Y%m%d'), '', '']))
    return ('\n'.join(lignes) + '\n').encode('utf-8')
