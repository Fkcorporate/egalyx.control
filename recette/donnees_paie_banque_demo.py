"""Jeu de données fictif « personnel, paie, habilitations, crédit, opérations clients » (1er semestre 2026, arrêté au
30/06/2026) avec anomalies connues (recette et démonstration). Toutes les données sont inventées."""
import random
from datetime import date, timedelta

ARRETE = date(2026, 6, 30)
ATTENDU = {
    'PAIE_APRES_SORTIE': {'M0010'},
    'PAIE_INCONNU': {'M9999'},
    'PAIE_DOUBLE': {'M0020'},
    'PAIE_RIB_PARTAGE': {'M0030', 'M0031'},
    'PAIE_VARIATION': {'M0040'},
    'PAIE_HEURES_SUP': {'M0050'},
    'SI_DEPARTS': {'kdiallo'},
    'SI_GENERIQUES': {'admin', 'test01'},
    'SI_INACTIFS': {'akone2'},
    'SI_INCOMPATIBLES': {'mtraore'},
    'CRD_DELEGATION': {'CR-DEL'},
    'CRD_FRACTIONNEMENT': {'CR-FR-1', 'CR-FR-2', 'CR-FR-3'},
    'CRD_PARTIES_LIEES': {'CR-PERS'},
    'CRD_SOUFFRANCE': {'CR-RET'},
    'CRD_SANS_GARANTIE': {'CR-SG'},
    'KYC_INCOMPLET': {'CL070', 'CL071', 'CL072'},
    'LCB_FRACTIONNEMENT': {'OP-FR-1', 'OP-FR-2', 'OP-FR-3'},
    'LCB_PEP': {'OP-PEP'},
    'LCB_DORMANTS': {'OP-DOR'},
    'LCB_PAYS': {'OP-PAYS'},
    'LCB_TRANSIT': {'OP-TR-1', 'OP-TR-2'},
    'STAT_MONTANTS': {'OP-ATY'},
}


def _rib(n):
    return f'CI{n:03d} 0{n % 9 + 1}001 {n:012d} {n % 97:02d}'


def generer(graine=11):
    rng = random.Random(graine)
    salaries, paie = [], []
    for i in range(1, 121):
        salaries.append({'Matricule': f'M{i:04d}', 'Nom et prénom': f'AGENT {i:03d}', 'RIB': _rib(7000 + i), 'Téléphone': f'+225 07 30 {i:02d} {i:02d} {i:02d}',
                         'Adresse': f'Quartier {i}, Abidjan', 'Date de sortie': None, 'Date d’entrée': date(2015, 1, 1) + timedelta(days=i * 20),
                         'Fonction': rng.choice(['Chargé de clientèle', 'Caissier', 'Comptable', 'Analyste crédit'])})
    sa = {s['Matricule']: s for s in salaries}
    sa['M0010']['Date de sortie'] = date(2026, 3, 31)
    sa['M0031']['RIB'] = sa['M0030']['RIB']
    base = {s['Matricule']: round(rng.uniform(250_000, 1_200_000), -3) for s in salaries}
    for m in range(1, 7):
        fin = (date(2026, m + 1, 1) - timedelta(days=1)) if m < 12 else date(2026, 12, 31)
        for s in salaries:
            mat = s['Matricule']
            if s['Date de sortie'] and (fin.year, fin.month) > (s['Date de sortie'].year, s['Date de sortie'].month) and mat != 'M0010':
                continue
            net = base[mat] * (2.1 if (mat == 'M0040' and m == 5) else 1)
            paie.append({'Matricule': mat, 'Nom et prénom': s['Nom et prénom'], 'Mois de paie': fin, 'Net payé': net, 'RIB': s['RIB'],
                         'Salaire brut': round(net * 1.32, -3), 'Heures supplémentaires': 45 if (mat == 'M0050' and m == 3) else rng.choice([0, 0, 2, 4, 8])})
    paie.append(dict(paie[[p['Matricule'] for p in paie].index('M0020') + 120], **{'Net payé': base['M0020']}))     # février payé deux fois
    paie.append({'Matricule': 'M9999', 'Nom et prénom': 'PERSONNE INCONNUE', 'Mois de paie': date(2026, 4, 30), 'Net payé': 650_000, 'RIB': _rib(9999),
                 'Salaire brut': 858_000, 'Heures supplémentaires': 0})

    utilisateurs = []
    for i in range(1, 81):
        utilisateurs.append({'Identifiant': f'agent{i:03d}', 'Nom': f'AGENT {i:03d}', 'Statut': 'Actif', 'Rôles': rng.choice(['Saisie', 'Consultation', 'Caisse', 'Analyse crédit']),
                             'Matricule': f'M{i:04d}', 'Dernière connexion': ARRETE - timedelta(days=rng.randint(0, 20)), 'Date de création': date(2023, 1, 5)})
    utilisateurs += [
        {'Identifiant': 'kdiallo', 'Nom': 'AGENT 010', 'Statut': 'Actif', 'Rôles': 'Saisie', 'Matricule': 'M0010', 'Dernière connexion': date(2026, 5, 12), 'Date de création': date(2020, 1, 1)},
        {'Identifiant': 'admin', 'Nom': 'Administrateur', 'Statut': 'Actif', 'Rôles': 'Administrateur', 'Matricule': '', 'Dernière connexion': date(2026, 6, 28), 'Date de création': date(2019, 1, 1)},
        {'Identifiant': 'test01', 'Nom': 'Compte de test', 'Statut': 'Actif', 'Rôles': 'Saisie', 'Matricule': '', 'Dernière connexion': date(2026, 6, 2), 'Date de création': date(2024, 3, 1)},
        {'Identifiant': 'akone2', 'Nom': 'AGENT 085', 'Statut': 'Actif', 'Rôles': 'Consultation', 'Matricule': 'M0085', 'Dernière connexion': date(2025, 10, 1), 'Date de création': date(2022, 1, 1)},
        {'Identifiant': 'mtraore', 'Nom': 'AGENT 090', 'Statut': 'Actif', 'Rôles': 'Création fournisseurs; Validation paiements', 'Matricule': 'M0090',
         'Dernière connexion': date(2026, 6, 29), 'Date de création': date(2021, 1, 1)},
        {'Identifiant': 'ancien', 'Nom': 'AGENT 099', 'Statut': 'Désactivé', 'Rôles': 'Saisie', 'Matricule': 'M0099', 'Dernière connexion': date(2024, 1, 1), 'Date de création': date(2020, 1, 1)},
    ]

    clients = []
    for i in range(1, 121):
        clients.append({'Code client': f'CL{i:03d}', 'Nom': f'CLIENT BANQUE {i:03d}', 'Statut': 'Actif', 'Limite de crédit': None, 'Date de création': date(2020, 1, 1),
                        'Pièce d’identité': f'CNI-{100000 + i}', 'Expiration de la pièce': date(2029, 1, 1), 'Adresse': f'Rue {i}, Abidjan', 'Profession': 'Commerçant',
                        'PEP': 'Non', 'Niveau de risque': 'Moyen', 'Date de revue': date(2025, 9, 1)})
    cl = {c['Code client']: c for c in clients}
    cl['CL060']['Nom'] = sa['M0005']['Nom et prénom']
    cl['CL070']['Pièce d’identité'] = ''
    cl['CL071']['Expiration de la pièce'] = date(2025, 2, 1)
    cl['CL072'].update({'Niveau de risque': 'Élevé', 'Date de revue': date(2024, 6, 1)})
    cl['CL081']['PEP'] = 'Oui'

    credits = []
    for k in range(1, 401):
        mt = round(10 ** rng.uniform(5.7, 7.2), -4)
        credits.append({'N° de dossier': f'CR-{k:04d}', 'Code client': f'CL{rng.randint(1, 59):03d}', 'Date': date(2026, 1, 2) + timedelta(days=rng.randint(0, 175)),
                        'Montant': mt, 'Accordé par': 'Chef d’agence Plateau' if mt <= 25_000_000 else 'Comité de crédit', 'Agent': rng.choice(['J. Koffi', 'M. Sylla']),
                        'Garantie': rng.choice(['Caution', 'Nantissement', 'Hypothèque']), 'Encours': round(mt * 0.8), 'Jours de retard': rng.choice([0] * 9 + [30]),
                        'Classement': 'Sain'})
    def cr(num, **kw):
        credits.append(dict({'N° de dossier': num, 'Code client': 'CL010', 'Date': date(2026, 3, 2), 'Montant': 5_000_000, 'Accordé par': 'Comité de crédit',
                             'Agent': 'J. Koffi', 'Garantie': 'Caution', 'Encours': 4_000_000, 'Jours de retard': 0, 'Classement': 'Sain'}, **kw))
    cr('CR-DEL', Montant=60_000_000, **{'Accordé par': 'Chef d’agence Plateau', 'Code client': 'CL011'})
    for j, d in enumerate((3, 5, 8), 1):
        cr(f'CR-FR-{j}', Montant=9_000_000, Date=date(2026, 4, d), **{'Code client': 'CL050', 'Accordé par': 'Chef d’agence Plateau'})
    cr('CR-PERS', Montant=8_000_000, **{'Code client': 'CL060'})
    cr('CR-RET', Montant=12_000_000, **{'Code client': 'CL012', 'Jours de retard': 120, 'Classement': 'Sain', 'Encours': 9_500_000})
    cr('CR-SG', Montant=30_000_000, **{'Code client': 'CL013', 'Garantie': ''})

    operations, n = [], [0]
    def op(client, d, mt, sens, canal='Virement', pays='Côte d’Ivoire', ref=None):
        n[0] += 1
        operations.append({'Référence': ref or f'OP-{n[0]:06d}', 'Client / compte': client, 'Date': d, 'Montant': mt, 'Sens': sens, 'Canal': canal,
                           'Pays': pays, 'Agence': 'Plateau'})
    for i in range(1, 80):
        for _ in range(30):
            d = date(2026, 1, 2) + timedelta(days=rng.randint(0, 178))
            mt = round(10 ** rng.uniform(4.5, 6.0), -3)
            if rng.random() < 0.55:
                op(f'CL{i:03d}', d, mt, 'Versement', rng.choice(['Espèces', 'Virement', 'Mobile money']))
            else:
                op(f'CL{i:03d}', d, -mt, rng.choice(['Retrait', 'Virement émis']), rng.choice(['Espèces', 'Virement']))
    for j, (d, mt) in enumerate(((10, 4_500_000), (12, 4_800_000), (14, 4_200_000)), 1):
        op('CL080', date(2026, 5, d), mt, 'Versement', 'Espèces', ref=f'OP-FR-{j}')
    op('CL081', date(2026, 4, 20), 25_000_000, 'Virement reçu', 'Virement', 'France', ref='OP-PEP')
    op('CL082', date(2025, 12, 1), 50_000, 'Versement', 'Espèces')
    op('CL082', date(2026, 6, 25), 15_000_000, 'Virement reçu', 'Virement', ref='OP-DOR')
    op('CL084', date(2026, 3, 3), -2_000_000, 'Virement émis', 'Virement', 'Iran', ref='OP-PAYS')
    op('CL083', date(2026, 5, 10), 40_000_000, 'Virement reçu', 'Virement', 'Côte d’Ivoire', ref='OP-TR-1')
    op('CL083', date(2026, 5, 11), -38_000_000, 'Retrait', 'Espèces', ref='OP-TR-2')
    for k in range(12):
        op('CL085', date(2026, 1, 5) + timedelta(days=k * 14), 200_000 + k * 1000, 'Versement', 'Virement')
    op('CL085', date(2026, 6, 20), 9_000_000, 'Versement', 'Virement', ref='OP-ATY')
    return {'salaries': salaries, 'paie': paie, 'utilisateurs_si': utilisateurs, 'clients': clients, 'credits': credits, 'operations': operations}
