"""
egalyx/analyse_moteur.py — moteur de l'analyse des données d'audit (lot 1 : achats, fournisseurs, paiements).

Sans Flask ni base de données : lecture des fichiers, correspondance des colonnes, contrôle de qualité,
bibliothèque de tests. Le moteur est déterministe : même fichier + mêmes réglages = même résultat
(c'est ce qui rend un résultat d'audit vérifiable). L'IA n'intervient pas ici (egalyx/analyse_donnees.py).

Principes :
  - une valeur mal formée (date, montant) est signalée, jamais devinée ;
  - un test dont les données manquent est « non applicable », avec ce qu'il faut importer ;
  - chaque anomalie renvoie à la ligne du fichier d'origine (numéro de ligne Excel / CSV).
"""
import csv
import gzip
import hashlib
import io
import math
import re
import unicodedata
from datetime import date, datetime, timedelta

import pandas as pd

MAX_LIGNES = 200_000
MAX_ANOMALIES = 500           # conservées par test (le nombre total est toujours exact)
MAX_ERREURS_EXEMPLES = 5

# ====================================================================== jeux de données
# (code, libellé, obligatoire, type, synonymes d'en-tête)
# types : id (identifiant rapproché entre fichiers), texte, nom (personne), date, montant, nombre, rib, telephone
JEUX = {
    'fournisseurs': {
        'libelle': 'Fournisseurs', 'icone': 'fa-building', 'ref': 'code', 'tiers': 'nom', 'date': 'date_creation', 'montant': None,
        'aide': 'Fichier des fournisseurs (fiche tiers) extrait du logiciel comptable ou de l’ERP.',
        'champs': [
            ('code', 'Code fournisseur', True, 'id', ['code fournisseur', 'code', 'id fournisseur', 'numero fournisseur', 'n fournisseur', 'compte tiers', 'tiers', 'vendor id', 'supplier id', 'code tiers']),
            ('nom', 'Nom / raison sociale', True, 'texte', ['nom', 'raison sociale', 'nom fournisseur', 'fournisseur', 'libelle', 'denomination', 'vendor name', 'supplier name', 'intitule']),
            ('rib', 'RIB / IBAN', True, 'rib', ['rib', 'iban', 'compte bancaire', 'numero de compte', 'n compte', 'coordonnees bancaires', 'bank account', 'compte banque']),
            ('date_creation', 'Date de création', False, 'date', ['date de creation', 'date creation', 'cree le', 'date ouverture', 'created on', 'creation']),
            ('cree_par', 'Créé par', False, 'nom', ['cree par', 'createur', 'saisi par', 'utilisateur creation', 'created by', 'auteur']),
            ('date_modif_rib', 'Date de modification du RIB', False, 'date', ['date modification rib', 'date modif rib', 'rib modifie le', 'date changement rib', 'derniere modification rib']),
            ('adresse', 'Adresse', False, 'texte', ['adresse', 'address', 'adresse postale', 'localisation']),
            ('telephone', 'Téléphone', False, 'telephone', ['telephone', 'tel', 'phone', 'contact', 'mobile', 'portable']),
            ('nif', 'N° fiscal (NCC / NIF)', False, 'id', ['nif', 'ncc', 'numero fiscal', 'n compte contribuable', 'compte contribuable', 'identifiant fiscal', 'tax id', 'rccm']),
            ('statut', 'Statut', False, 'texte', ['statut', 'etat', 'actif', 'status', 'bloque']),
        ]},
    'factures': {
        'libelle': 'Factures fournisseurs', 'icone': 'fa-file-invoice', 'ref': 'numero', 'tiers': 'fournisseur', 'date': 'date', 'montant': 'montant',
        'aide': 'Factures reçues (journal des achats ou registre des factures), une ligne par facture.',
        'champs': [
            ('numero', 'N° de facture', True, 'id', ['numero facture', 'n facture', 'facture', 'num facture', 'reference facture', 'ref facture', 'invoice number', 'invoice', 'numero', 'piece']),
            ('fournisseur', 'Code fournisseur', True, 'id', ['code fournisseur', 'fournisseur', 'tiers', 'compte tiers', 'vendor', 'supplier', 'code tiers']),
            ('date', 'Date de facture', True, 'date', ['date facture', 'date', 'date de facture', 'invoice date', 'date piece']),
            ('montant', 'Montant TTC', True, 'montant', ['montant ttc', 'montant', 'total ttc', 'montant facture', 'net a payer', 'amount', 'total', 'ttc']),
            ('commande', 'N° de bon de commande', False, 'id', ['bon de commande', 'n commande', 'numero commande', 'bc', 'commande', 'purchase order', 'po', 'ref commande']),
            ('date_saisie', 'Date de saisie', False, 'date', ['date saisie', 'date de saisie', 'saisi le', 'date comptabilisation', 'entry date']),
            ('saisi_par', 'Saisi par', False, 'nom', ['saisi par', 'utilisateur', 'operateur', 'cree par', 'entered by', 'user']),
            ('devise', 'Devise', False, 'texte', ['devise', 'monnaie', 'currency']),
        ]},
    'paiements': {
        'libelle': 'Paiements', 'icone': 'fa-money-bill-transfer', 'ref': 'reference', 'tiers': 'fournisseur', 'date': 'date', 'montant': 'montant',
        'aide': 'Règlements fournisseurs (virements, chèques, espèces) extraits de la trésorerie ou de la banque.',
        'champs': [
            ('reference', 'Référence du paiement', True, 'id', ['reference', 'ref', 'numero paiement', 'n paiement', 'reference paiement', 'n virement', 'numero cheque', 'payment id', 'piece']),
            ('fournisseur', 'Code fournisseur', True, 'id', ['code fournisseur', 'fournisseur', 'beneficiaire', 'tiers', 'code tiers', 'vendor', 'supplier']),
            ('date', 'Date du paiement', True, 'date', ['date paiement', 'date', 'date de paiement', 'date valeur', 'date reglement', 'payment date']),
            ('montant', 'Montant payé', True, 'montant', ['montant', 'montant paye', 'montant regle', 'montant paiement', 'amount', 'debit']),
            ('rib', 'RIB / IBAN bénéficiaire', True, 'rib', ['rib', 'iban', 'compte beneficiaire', 'rib beneficiaire', 'compte bancaire', 'numero de compte', 'bank account']),
            ('approuve_par', 'Approuvé par', False, 'nom', ['approuve par', 'approbateur', 'valide par', 'autorise par', 'signataire', 'approved by', 'validation']),
            ('facture', 'N° de facture payée', False, 'id', ['numero facture', 'n facture', 'facture', 'reference facture', 'invoice', 'facture payee']),
            ('mode', 'Mode de paiement', False, 'texte', ['mode', 'mode de paiement', 'moyen de paiement', 'type paiement', 'payment method']),
        ]},
    'commandes': {
        'libelle': 'Bons de commande', 'icone': 'fa-cart-shopping', 'ref': 'numero', 'tiers': 'fournisseur', 'date': 'date', 'montant': 'montant',
        'aide': 'Bons de commande émis (une ligne par commande, ou par ligne d’article pour le test des prix).',
        'champs': [
            ('numero', 'N° de commande', True, 'id', ['numero commande', 'n commande', 'bon de commande', 'bc', 'commande', 'numero', 'purchase order', 'po']),
            ('fournisseur', 'Code fournisseur', True, 'id', ['code fournisseur', 'fournisseur', 'tiers', 'code tiers', 'vendor', 'supplier']),
            ('date', 'Date de commande', True, 'date', ['date commande', 'date', 'date de commande', 'order date', 'date bc']),
            ('montant', 'Montant', True, 'montant', ['montant', 'montant ttc', 'montant ht', 'total', 'amount', 'montant commande']),
            ('approuve_par', 'Approuvé par', False, 'nom', ['approuve par', 'approbateur', 'valide par', 'autorise par', 'signataire', 'approved by']),
            ('article', 'Article', False, 'texte', ['article', 'code article', 'designation', 'produit', 'item', 'libelle article']),
            ('quantite', 'Quantité', False, 'nombre', ['quantite', 'qte', 'qty', 'quantity']),
            ('prix_unitaire', 'Prix unitaire', False, 'montant', ['prix unitaire', 'pu', 'prix', 'unit price', 'cout unitaire']),
        ]},
    'salaries': {
        'libelle': 'Salariés', 'icone': 'fa-id-badge', 'ref': 'matricule', 'tiers': 'nom', 'date': None, 'montant': None,
        'aide': 'Fichier du personnel (paie ou RH) : sert uniquement à repérer un fournisseur qui partage le RIB, le téléphone ou l’adresse d’un salarié.',
        'champs': [
            ('matricule', 'Matricule', True, 'id', ['matricule', 'id', 'numero salarie', 'n salarie', 'employee id', 'code']),
            ('nom', 'Nom et prénom', True, 'texte', ['nom', 'nom prenom', 'nom et prenom', 'salarie', 'employe', 'name']),
            ('rib', 'RIB / IBAN', True, 'rib', ['rib', 'iban', 'compte bancaire', 'numero de compte', 'bank account']),
            ('telephone', 'Téléphone', False, 'telephone', ['telephone', 'tel', 'phone', 'mobile', 'portable', 'contact']),
            ('adresse', 'Adresse', False, 'texte', ['adresse', 'address', 'domicile']),
            ('date_sortie', 'Date de sortie', False, 'date', ['date sortie', 'date de sortie', 'date depart', 'fin contrat', 'termination date']),
        ]},
}
JEUX.update({
    'grand_livre': {
        'libelle': 'Grand livre (écritures)', 'icone': 'fa-book', 'ref': 'numero', 'tiers': 'compte', 'date': 'date', 'montant': '_mt',
        'aide': 'Écritures comptables, une ligne par ligne d’écriture : export du grand livre (SYSCOHADA) ou fichier des écritures comptables (FEC).',
        'champs': [
            ('numero', 'N° d’écriture', True, 'id', ['n ecriture', 'numero ecriture', 'ecriturenum', 'num ecriture', 'numero de l ecriture', 'n mouvement', 'mouvement', 'entry number', 'n operation']),
            ('date', 'Date de l’écriture', True, 'date', ['date ecriture', 'ecrituredate', 'date comptable', 'date', 'date operation', 'date de l ecriture']),
            ('compte', 'N° de compte', True, 'texte', ['compte', 'comptenum', 'n compte', 'numero compte', 'compte general', 'compte comptable', 'account', 'n de compte']),
            ('debit', 'Débit', True, 'montant', ['debit', 'montant debit', 'mouvement debit', 'debit fcfa', 'debit xof']),
            ('credit', 'Crédit', True, 'montant', ['credit', 'montant credit', 'mouvement credit', 'credit fcfa', 'credit xof']),
            ('libelle', 'Libellé', False, 'texte', ['libelle', 'ecriturelib', 'libelle ecriture', 'designation', 'description', 'intitule', 'libelle operation']),
            ('journal', 'Code journal', False, 'texte', ['journal', 'journalcode', 'code journal', 'jnl', 'jl']),
            ('piece', 'Pièce justificative', False, 'texte', ['piece', 'pieceref', 'reference piece', 'n piece', 'justificatif', 'ref piece', 'piece justificative']),
            ('saisi_par', 'Saisi par', False, 'nom', ['saisi par', 'utilisateur', 'operateur', 'auteur', 'user', 'cree par', 'login']),
            ('date_saisie', 'Date et heure de saisie', False, 'horodatage', ['date saisie', 'date de saisie', 'validdate', 'date validation', 'saisi le', 'horodatage', 'date heure saisie', 'date creation', 'created on']),
            ('tiers', 'Compte de tiers', False, 'texte', ['compauxnum', 'compte auxiliaire', 'compte tiers', 'tiers', 'auxiliaire']),
            ('lettrage', 'Lettrage', False, 'texte', ['lettrage', 'ecriturelet', 'code lettrage', 'let']),
        ]},
    'ventes': {
        'libelle': 'Factures clients (ventes)', 'icone': 'fa-file-invoice-dollar', 'ref': 'numero', 'tiers': 'client', 'date': 'date', 'montant': 'montant',
        'aide': 'Factures et avoirs émis, une ligne par document (journal des ventes ou facturation).',
        'champs': [
            ('numero', 'N° de facture ou d’avoir', True, 'id', ['numero facture', 'n facture', 'facture', 'num facture', 'numero', 'n document', 'numero document', 'invoice number', 'piece']),
            ('client', 'Code client', True, 'id', ['code client', 'client', 'compte client', 'tiers', 'code tiers', 'customer', 'n client']),
            ('date', 'Date', True, 'date', ['date facture', 'date', 'date document', 'invoice date', 'date de facture']),
            ('montant', 'Montant TTC', True, 'montant', ['montant ttc', 'montant', 'total ttc', 'total', 'net a payer', 'amount', 'ttc']),
            ('type', 'Type (facture / avoir)', False, 'texte', ['type', 'nature', 'type document', 'type piece', 'sens', 'document']),
            ('facture_origine', 'Facture d’origine (avoirs)', False, 'id', ['facture origine', 'facture d origine', 'facture liee', 'facture annulee', 'avoir sur', 'ref facture origine', 'origine']),
            ('remise_pct', 'Remise (%)', False, 'nombre', ['remise', 'taux remise', 'remise %', 'taux de remise', 'discount', 'rabais']),
            ('vendeur', 'Vendeur', False, 'nom', ['vendeur', 'commercial', 'agent', 'saisi par', 'salesman']),
        ]},
    'clients': {
        'libelle': 'Clients', 'icone': 'fa-users', 'ref': 'code', 'tiers': 'nom', 'date': 'date_creation', 'montant': None,
        'aide': 'Fichier des clients : statut (actif, bloqué, contentieux) et limite de crédit autorisée.',
        'champs': [
            ('code', 'Code client', True, 'id', ['code client', 'code', 'client', 'compte client', 'n client', 'customer id', 'code tiers']),
            ('nom', 'Nom / raison sociale', True, 'texte', ['nom', 'raison sociale', 'nom client', 'client', 'denomination', 'intitule', 'customer name']),
            ('statut', 'Statut', False, 'texte', ['statut', 'etat', 'actif', 'status', 'bloque', 'situation']),
            ('limite_credit', 'Limite de crédit', False, 'montant', ['limite credit', 'limite de credit', 'plafond', 'encours autorise', 'credit limit', 'plafond credit']),
            ('date_creation', 'Date de création', False, 'date', ['date creation', 'date de creation', 'cree le', 'created on']),
        ]},
    'encaissements': {
        'libelle': 'Encaissements', 'icone': 'fa-hand-holding-dollar', 'ref': 'reference', 'tiers': 'client', 'date': 'date', 'montant': 'montant',
        'aide': 'Règlements reçus des clients (banque, caisse, mobile money), une ligne par encaissement.',
        'champs': [
            ('reference', 'Référence', True, 'id', ['reference', 'ref', 'numero encaissement', 'n encaissement', 'n recu', 'numero recu', 'piece', 'receipt']),
            ('client', 'Code client', True, 'id', ['code client', 'client', 'compte client', 'tiers', 'payeur', 'customer']),
            ('date', 'Date', True, 'date', ['date encaissement', 'date', 'date reglement', 'date valeur', 'date de reception']),
            ('montant', 'Montant', True, 'montant', ['montant', 'montant encaisse', 'montant regle', 'credit', 'amount']),
            ('facture', 'N° de facture réglée', False, 'id', ['numero facture', 'n facture', 'facture', 'facture reglee', 'reference facture', 'invoice']),
            ('mode', 'Mode de règlement', False, 'texte', ['mode', 'mode de reglement', 'moyen de paiement', 'type reglement']),
        ]},
})
# lot 4 : paie, habilitations, crédit, opérations (LCB-FT) ; champs complémentaires des salariés et des clients (KYC)
JEUX['salaries']['champs'] += [
    ('date_entree', 'Date d’entrée', False, 'date', ['date entree', 'date d entree', 'date embauche', 'embauche', 'hire date']),
    ('fonction', 'Fonction', False, 'texte', ['fonction', 'poste', 'emploi', 'job title']),
]
JEUX['clients']['champs'] += [
    ('piece_identite', 'N° de pièce d’identité', False, 'texte', ['piece identite', 'n piece', 'numero piece', 'cni', 'passeport', 'id document', 'piece']),
    ('expiration_piece', 'Expiration de la pièce', False, 'date', ['expiration piece', 'date expiration', 'validite piece', 'expire le', 'expiry']),
    ('adresse', 'Adresse', False, 'texte', ['adresse', 'domicile', 'address']),
    ('profession', 'Profession / activité', False, 'texte', ['profession', 'activite', 'occupation', 'secteur']),
    ('pep', 'Personne politiquement exposée', False, 'texte', ['pep', 'ppe', 'personne politiquement exposee', 'politiquement expose']),
    ('niveau_risque', 'Niveau de risque LCB-FT', False, 'texte', ['niveau risque', 'risque', 'profil risque', 'classe risque', 'risk']),
    ('date_revue', 'Date de dernière revue KYC', False, 'date', ['date revue', 'derniere revue', 'revue kyc', 'mise a jour kyc', 'date mise a jour']),
]
JEUX.update({
    'paie': {
        'libelle': 'Paie (salaires versés)', 'icone': 'fa-money-check-dollar', 'ref': 'matricule', 'tiers': 'nom', 'date': 'periode', 'montant': 'montant',
        'aide': 'Livre de paie ou virements de salaires : une ligne par salarié et par mois.',
        'champs': [
            ('matricule', 'Matricule', True, 'id', ['matricule', 'n salarie', 'id salarie', 'employee id', 'code salarie']),
            ('nom', 'Nom et prénom', True, 'texte', ['nom', 'nom prenom', 'nom et prenom', 'salarie', 'employe']),
            ('periode', 'Mois de paie', True, 'date', ['periode', 'mois', 'mois de paie', 'periode de paie', 'date paie', 'pay period']),
            ('montant', 'Net payé', True, 'montant', ['net paye', 'net a payer', 'net', 'montant', 'salaire net', 'net pay']),
            ('rib', 'RIB / IBAN de versement', False, 'rib', ['rib', 'iban', 'compte', 'compte bancaire', 'numero de compte']),
            ('brut', 'Salaire brut', False, 'montant', ['brut', 'salaire brut', 'gross']),
            ('heures_sup', 'Heures supplémentaires', False, 'nombre', ['heures sup', 'heures supplementaires', 'hs', 'overtime']),
        ]},
    'utilisateurs_si': {
        'libelle': 'Comptes utilisateurs (SI)', 'icone': 'fa-user-lock', 'ref': 'identifiant', 'tiers': 'nom', 'date': 'derniere_connexion', 'montant': None,
        'aide': 'Liste des comptes d’une application (comptabilité, système bancaire…) avec leurs rôles et leur dernière connexion.',
        'champs': [
            ('identifiant', 'Identifiant', True, 'texte', ['identifiant', 'login', 'user id', 'utilisateur', 'compte', 'username', 'code utilisateur']),
            ('nom', 'Nom', True, 'texte', ['nom', 'nom complet', 'nom prenom', 'full name', 'titulaire']),
            ('statut', 'Statut', True, 'texte', ['statut', 'etat', 'actif', 'status', 'enabled']),
            ('roles', 'Rôles / profils', True, 'texte', ['roles', 'role', 'profils', 'profil', 'habilitations', 'groupes', 'droits']),
            ('matricule', 'Matricule (RH)', False, 'id', ['matricule', 'n salarie', 'employee id']),
            ('derniere_connexion', 'Dernière connexion', False, 'date', ['derniere connexion', 'last login', 'dernier acces', 'date derniere connexion']),
            ('date_creation', 'Date de création', False, 'date', ['date creation', 'cree le', 'created on', 'date de creation']),
            ('application', 'Application', False, 'texte', ['application', 'systeme', 'module', 'logiciel']),
        ]},
    'credits': {
        'libelle': 'Crédits accordés', 'icone': 'fa-hand-holding-dollar', 'ref': 'numero', 'tiers': 'client', 'date': 'date', 'montant': 'montant',
        'aide': 'Portefeuille de crédits : une ligne par dossier (mise en place, encours, retard, classement).',
        'champs': [
            ('numero', 'N° de dossier', True, 'id', ['numero dossier', 'n dossier', 'numero pret', 'n pret', 'reference', 'numero credit', 'dossier']),
            ('client', 'Code client', True, 'id', ['code client', 'client', 'n client', 'compte client', 'emprunteur']),
            ('date', 'Date de mise en place', True, 'date', ['date mise en place', 'date deblocage', 'date octroi', 'date', 'date accord']),
            ('montant', 'Montant accordé', True, 'montant', ['montant', 'montant accorde', 'montant octroye', 'montant pret', 'capital']),
            ('accorde_par', 'Accordé par', False, 'nom', ['accorde par', 'approuve par', 'decideur', 'comite', 'valide par', 'autorise par']),
            ('agent', 'Agent de crédit', False, 'nom', ['agent', 'agent de credit', 'charge de clientele', 'gestionnaire']),
            ('garantie', 'Garantie', False, 'texte', ['garantie', 'surete', 'suretes', 'nantissement', 'hypotheque', 'caution']),
            ('encours', 'Encours', False, 'montant', ['encours', 'capital restant du', 'crd', 'solde']),
            ('jours_retard', 'Jours de retard', False, 'nombre', ['jours retard', 'jours de retard', 'retard', 'arrieres jours', 'days past due', 'dpd']),
            ('classement', 'Classement', False, 'texte', ['classement', 'classe', 'statut', 'qualite', 'categorie risque']),
        ]},
    'operations': {
        'libelle': 'Opérations clients (comptes)', 'icone': 'fa-arrow-right-arrow-left', 'ref': 'reference', 'tiers': 'client', 'date': 'date', 'montant': 'montant',
        'aide': 'Mouvements sur les comptes de la clientèle (dépôts, retraits, virements) pour les tests de lutte contre le blanchiment.',
        'champs': [
            ('reference', 'Référence', True, 'id', ['reference', 'ref', 'n operation', 'numero operation', 'transaction id', 'piece']),
            ('client', 'Client / compte', True, 'id', ['client', 'code client', 'compte', 'n compte', 'numero de compte', 'account']),
            ('date', 'Date', True, 'date', ['date', 'date operation', 'date valeur', 'date transaction']),
            ('montant', 'Montant', True, 'montant', ['montant', 'amount', 'montant operation']),
            ('sens', 'Sens / type', False, 'texte', ['sens', 'type', 'type operation', 'nature', 'libelle operation', 'code operation']),
            ('canal', 'Canal', False, 'texte', ['canal', 'moyen', 'mode', 'channel', 'instrument']),
            ('pays', 'Pays de la contrepartie', False, 'texte', ['pays', 'pays contrepartie', 'pays beneficiaire', 'pays donneur', 'country']),
            ('agence', 'Agence', False, 'texte', ['agence', 'guichet', 'branch']),
        ]},
})
CYCLES = [('achats', 'Achats, fournisseurs et paiements', ['fournisseurs', 'factures', 'paiements', 'commandes']),
          ('compta', 'Comptabilité', ['grand_livre']),
          ('ventes', 'Ventes, clients et encaissements', ['ventes', 'clients', 'encaissements']),
          ('rh', 'Personnel, paie et habilitations', ['salaries', 'paie', 'utilisateurs_si']),
          ('banque', 'Banque et microfinance', ['credits', 'operations'])]
ORDRE_JEUX = [j for _c, _l, js in CYCLES for j in js]


def champs(jeu):
    return JEUX[jeu]['champs']


def types_jeu(jeu):
    return {c[0]: c[3] for c in champs(jeu)}


# ====================================================================== textes et normalisation
def sans_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', str(s)) if unicodedata.category(c) != 'Mn')


def norm_entete(s):
    s = sans_accents(s).lower().replace('°', ' ').replace('º', ' ')
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return re.sub(r'\b(n|no|num)\b', 'n', s).strip()


def norm_id(v):
    """Identifiant rapproché entre fichiers : majuscules, sans espaces ni ponctuation, zéros de tête retirés."""
    s = re.sub(r'[^0-9A-Z]', '', sans_accents(v).upper())
    s2 = s.lstrip('0')
    return s2 or s


def norm_nom(v):
    return re.sub(r'\s+', ' ', re.sub(r'[^0-9a-z]+', ' ', sans_accents(v).lower())).strip()


def norm_rib(v):
    return re.sub(r'[^0-9A-Z]', '', sans_accents(v).upper())


def norm_tel(v):
    chiffres = re.sub(r'\D', '', str(v))
    return chiffres[-8:] if len(chiffres) >= 8 else ''


def _vide(v):
    return v is None or (isinstance(v, float) and math.isnan(v)) or (isinstance(v, str) and not v.strip())


def texte(v):
    if _vide(v):
        return ''
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, (datetime, date)):
        return v.strftime('%d/%m/%Y')
    return re.sub(r'\s+', ' ', str(v)).strip()


# ====================================================================== montants et dates
_DEVISES = re.compile(r'(fcfa|f\s?cfa|xof|xaf|cfa|eur|euros?|usd|\$|€|f\b)', re.I)


def separateur_decimal(valeurs):
    """Décide une fois pour toute la colonne : ',' ou '.' (ex. « 1.250 » = 1 250 en FCFA, 1,25 ailleurs)."""
    virgule = point = 0
    for v in valeurs:
        if not isinstance(v, str):
            continue
        s = re.sub(r'[\s  ]', '', v)
        if re.search(r',\d{1,2}$', s) or re.search(r'\.\d{3},\d+$', s):
            virgule += 1
        elif re.search(r'\.\d{1,2}$', s) or re.search(r',\d{3}\.\d+$', s):
            point += 1
    return ',' if virgule >= point and virgule > 0 else '.' if point > 0 else None


def lire_montant(v, sep=None):
    """float, ou None si la valeur est vide, ou la chaîne 'ERREUR' si elle n'est pas un montant."""
    if _vide(v):
        return None
    if isinstance(v, bool):
        return 'ERREUR'
    if isinstance(v, (int, float)):
        return float(v)
    s = _DEVISES.sub('', str(v)).strip()
    s = re.sub(r'[\s  \']', '', s)
    negatif = False
    if s.startswith('(') and s.endswith(')'):
        negatif, s = True, s[1:-1]
    if s.endswith('-'):
        negatif, s = True, s[:-1]
    if s.startswith('-'):
        negatif, s = not negatif, s[1:]
    if s.startswith('+'):
        s = s[1:]
    if not s or not re.fullmatch(r'[0-9.,]+', s):
        return 'ERREUR'
    if sep == ',' or (sep is None and ',' in s and '.' not in s and not re.fullmatch(r'\d{1,3}(,\d{3})+', s)):
        s = s.replace('.', '').replace(',', '.')
    elif sep == '.':
        s = s.replace(',', '')
    else:                                   # séparateurs de milliers seuls : « 1.250.000 » ou « 1,250,000 »
        s = s.replace(',', '').replace('.', '') if re.fullmatch(r'\d{1,3}([.,]\d{3})+', s) else s.replace(',', '')
    if s.count('.') > 1:
        return 'ERREUR'
    try:
        x = float(s)
    except ValueError:
        return 'ERREUR'
    return -x if negatif else x


_FORMATS_DATE = ['%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%Y-%m-%d', '%Y/%m/%d', '%d/%m/%y', '%d-%m-%y', '%Y%m%d',
                 '%d/%m/%Y %H:%M', '%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M']


def lire_date(v):
    """date, None (vide) ou 'ERREUR'. Les dates sont lues jour/mois/année ; jamais mois/jour."""
    if _vide(v):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if 20000 <= v <= 80000:             # numéro de série Excel (1954 à 2119)
            return date(1899, 12, 30) + timedelta(days=int(v))
        if 19000101 <= v <= 21001231:
            v = str(int(v))
        else:
            return 'ERREUR'
    s = str(v).strip()
    s = re.sub(r'\.\d+$', '', s.replace('T00:00:00', ''))
    for f in _FORMATS_DATE:
        try:
            d = datetime.strptime(s, f).date()
            return d if 1950 <= d.year <= 2100 else 'ERREUR'
        except ValueError:
            continue
    return 'ERREUR'


def lire_horodatage(v):
    """datetime (avec l'heure si le fichier la donne), None ou 'ERREUR'."""
    if _vide(v):
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    if isinstance(v, (int, float)) and not isinstance(v, bool) and 20000 <= v <= 80000:
        return datetime(1899, 12, 30) + timedelta(days=float(v))
    s = re.sub(r'\.\d+$', '', str(v).strip())
    for f in ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M', '%d-%m-%Y %H:%M:%S',
              '%d-%m-%Y %H:%M', '%Y%m%d %H:%M:%S', '%Y%m%d%H%M%S'):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    d = lire_date(v)
    return d if d in (None, 'ERREUR') else datetime(d.year, d.month, d.day)


# ====================================================================== lecture des fichiers
class ErreurFichier(Exception):
    pass


def empreinte(octets):
    return hashlib.sha256(octets).hexdigest()


def _ligne_entete(lignes):
    for i, l in enumerate(lignes[:15]):
        if sum(1 for v in l if not _vide(v)) >= 2:
            return i
    return 0


def lire_fichier(octets, nom_fichier, feuille=None, max_lignes=MAX_LIGNES):
    """Renvoie (entetes, lignes, infos). infos : format, feuilles, feuille, separateur, encodage, premiere_ligne."""
    nom = (nom_fichier or '').lower()
    infos = {'format': '', 'feuilles': [], 'feuille': '', 'separateur': '', 'encodage': ''}
    if nom.endswith(('.xlsx', '.xlsm')):
        try:
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(octets), read_only=True, data_only=True)
        except Exception as e:  # noqa: BLE001
            raise ErreurFichier("Le classeur Excel n'a pas pu être ouvert (fichier abîmé ou protégé par mot de passe).") from e
        infos['format'] = 'Excel'
        infos['feuilles'] = list(wb.sheetnames)
        nom_feuille = feuille if feuille in wb.sheetnames else wb.sheetnames[0]
        infos['feuille'] = nom_feuille
        brut = []
        for row in wb[nom_feuille].iter_rows(values_only=True):
            brut.append(list(row))
            if len(brut) > max_lignes + 16:
                raise ErreurFichier(f'Le fichier dépasse {max_lignes:,} lignes. Découpez-le par période (par exemple par trimestre).'.replace(',', ' '))
        wb.close()
    elif nom.endswith(('.csv', '.txt')):
        for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
            try:
                contenu = octets.decode(enc)
                infos['encodage'] = enc.replace('-sig', '')
                break
            except UnicodeDecodeError:
                continue
        echantillon = '\n'.join(contenu.splitlines()[:30])
        try:
            sep = csv.Sniffer().sniff(echantillon, delimiters=';,\t|').delimiter
        except csv.Error:
            sep = max(';,\t|', key=lambda c: echantillon.count(c))
        infos['format'], infos['separateur'] = 'CSV', {'\t': 'tabulation'}.get(sep, sep)
        brut = []
        for row in csv.reader(io.StringIO(contenu), delimiter=sep):
            brut.append(row)
            if len(brut) > max_lignes + 16:
                raise ErreurFichier(f'Le fichier dépasse {max_lignes:,} lignes. Découpez-le par période (par exemple par trimestre).'.replace(',', ' '))
    elif nom.endswith('.xls'):
        raise ErreurFichier('Ancien format Excel (.xls) : ouvrez le fichier dans Excel et enregistrez-le au format .xlsx, puis importez-le à nouveau.')
    else:
        raise ErreurFichier('Format non pris en charge : importez un fichier Excel (.xlsx) ou CSV (.csv).')
    if not brut:
        raise ErreurFichier('Le fichier est vide.')
    i = _ligne_entete(brut)
    entetes = [texte(v) or f'Colonne {j + 1}' for j, v in enumerate(brut[i])]
    vus = {}
    for j, e in enumerate(entetes):               # en-têtes en double : « Montant », « Montant (2) »
        if e in vus:
            vus[e] += 1
            entetes[j] = f'{e} ({vus[e]})'
        else:
            vus[e] = 1
    lignes = [l for l in brut[i + 1:] if any(not _vide(v) for v in l)]
    infos['premiere_ligne'] = i + 2                # numéro (1 = première ligne du fichier) de la première ligne de données
    infos['lignes_brutes'] = brut[i + 1:]
    if not lignes:
        raise ErreurFichier("Le fichier ne contient que la ligne d'en-tête.")
    return entetes, lignes, infos


# ====================================================================== correspondance des colonnes
MOTS_VIDES = {'de', 'la', 'le', 'les', 'du', 'des', 'd', 'l', 'a', 'en', 'au', 'aux', 'par', 'the', 'of'}


def _cle_entete(s):
    return ' '.join(m for m in norm_entete(s).split() if m not in MOTS_VIDES)


def proposer_correspondance(jeu, entetes):
    """{champ: en-tête} proposé à partir des noms de colonnes (sans IA). Chaque en-tête sert une seule fois."""
    normes = [_cle_entete(e) for e in entetes]
    candidats = []
    for code, _lib, oblig, _t, syn in champs(jeu):
        for j, n in enumerate(normes):
            meilleur = 0
            for rang, s in enumerate(syn):
                s = _cle_entete(s)
                if n == s:
                    meilleur = max(meilleur, 100 - rang)
                elif re.search(r'\b' + re.escape(s) + r'\b', n) and len(s) >= 3:
                    meilleur = max(meilleur, 50 - rang)
            if meilleur:
                candidats.append((meilleur + (5 if oblig else 0), code, j))
    choix, pris = {}, set()
    for _score, code, j in sorted(candidats, key=lambda x: -x[0]):
        if code not in choix and j not in pris:
            choix[code] = entetes[j]
            pris.add(j)
    return choix


def obligatoires_manquants(jeu, correspondance):
    return [lib for code, lib, oblig, _t, _s in champs(jeu) if oblig and not correspondance.get(code)]


# ====================================================================== normalisation + contrôle de qualité
def normaliser(jeu, entetes, lignes_brutes, correspondance, premiere_ligne=2):
    """Construit le tableau normalisé (colonnes = champs + _ligne) et le contrôle de qualité."""
    idx = {e: j for j, e in enumerate(entetes)}
    garde = [(k, l) for k, l in enumerate(lignes_brutes) if any(not _vide(v) for v in l)]
    n = len(garde)
    colonnes = {'_ligne': [premiere_ligne + k for k, _l in garde]}
    qualite = {'lignes': n, 'champs': [], 'bloquant': [], 'avertissements': []}
    for code, lib, oblig, typ, _s in champs(jeu):
        entete = correspondance.get(code)
        if not entete or entete not in idx:
            colonnes[code] = [None] * n if typ in ('date', 'montant', 'nombre') else [''] * n
            qualite['champs'].append({'code': code, 'libelle': lib, 'obligatoire': oblig, 'colonne': '', 'vides': n, 'erreurs': 0, 'exemples': []})
            continue
        j = idx[entete]
        brut = [l[j] if j < len(l) else None for _k, l in garde]
        erreurs, exemples, vides = 0, [], 0
        if typ == 'montant' or typ == 'nombre':
            sep = separateur_decimal(brut)
            valeurs = []
            for (k, _l), v in zip(garde, brut):
                x = lire_montant(v, sep)
                if x == 'ERREUR':
                    erreurs += 1
                    if len(exemples) < MAX_ERREURS_EXEMPLES:
                        exemples.append({'ligne': premiere_ligne + k, 'valeur': texte(v)[:40]})
                    x = None
                elif x is None:
                    vides += 1
                valeurs.append(x)
        elif typ in ('date', 'horodatage'):
            lecteur = lire_date if typ == 'date' else lire_horodatage
            valeurs = []
            for (k, _l), v in zip(garde, brut):
                d = lecteur(v)
                if d == 'ERREUR':
                    erreurs += 1
                    if len(exemples) < MAX_ERREURS_EXEMPLES:
                        exemples.append({'ligne': premiere_ligne + k, 'valeur': texte(v)[:40]})
                    d = None
                elif d is None:
                    vides += 1
                valeurs.append(d)
        else:
            valeurs = [texte(v)[:300] for v in brut]
            vides = sum(1 for v in valeurs if not v)
            if typ == 'rib':
                for (k, _l), v in zip(garde, valeurs):
                    if v and len(norm_rib(v)) < 10:
                        erreurs += 1
                        if len(exemples) < MAX_ERREURS_EXEMPLES:
                            exemples.append({'ligne': premiere_ligne + k, 'valeur': v[:40]})
        colonnes[code] = valeurs
        qualite['champs'].append({'code': code, 'libelle': lib, 'obligatoire': oblig, 'colonne': entete,
                                  'vides': vides, 'erreurs': erreurs, 'exemples': exemples})
        if jeu == 'grand_livre' and code in ('debit', 'credit'):
            vides = 0                                   # une ligne d'écriture n'a qu'un côté renseigné : vide = 0
        if oblig and (vides or erreurs):
            qualite['avertissements'].append(
                f'« {lib} » : ' + ', '.join(x for x in (f'{vides} ligne(s) vide(s)' if vides else '',
                                                         f'{erreurs} valeur(s) illisible(s)' if erreurs else '') if x)
                + ' — ces lignes sont écartées des tests qui utilisent ce champ.')
    df = pd.DataFrame(colonnes)
    for code, _lib, _o, typ, _s in champs(jeu):
        if typ in ('date', 'horodatage'):
            df[code] = pd.to_datetime(pd.Series(df[code], dtype=object), errors='coerce')
        elif typ in ('montant', 'nombre'):
            df[code] = pd.to_numeric(pd.Series(df[code], dtype=object), errors='coerce')
    df = derives(jeu, df)
    if jeu == 'grand_livre' and correspondance.get('debit') and correspondance.get('credit'):
        sans = int((df['debit'].isna() & df['credit'].isna()).sum())
        if sans:
            qualite['avertissements'].append(f'{sans} ligne(s) sans débit ni crédit.')
    # indicateurs de contrôle (à rapprocher de la comptabilité)
    info = JEUX[jeu]
    if jeu == 'grand_livre':
        qualite['total'] = float(df['debit'].sum(skipna=True))
        qualite['total_credit'] = float(df['credit'].sum(skipna=True))
        if abs(qualite['total'] - qualite['total_credit']) > 1:
            qualite['avertissements'].append(f"Total des débits ({_fr(qualite['total'])}) différent du total des crédits "
                                             f"({_fr(qualite['total_credit'])}) : extraction incomplète ou écritures déséquilibrées.")
    elif info['montant']:
        m = df[info['montant']]
        qualite['total'] = float(m.sum(skipna=True))
        qualite['negatifs'] = int((m < 0).sum())
        qualite['nuls'] = int((m == 0).sum())
    if info['date'] and df[info['date']].notna().any():
        qualite['periode'] = [df[info['date']].min().date().isoformat(), df[info['date']].max().date().isoformat()]
    cles = [c[0] for c in champs(jeu) if correspondance.get(c[0])]
    if cles and n:
        qualite['doublons_exacts'] = int(df.duplicated(subset=cles, keep='first').sum())
    ref = info['ref']
    if jeu in ('fournisseurs', 'salaries') and correspondance.get(ref):
        ids = df[ref].map(lambda v: norm_id(v) if v else '')
        qualite['identifiants_en_double'] = int(ids[ids != ''].duplicated().sum())
        if qualite['identifiants_en_double']:
            qualite['avertissements'].append(f"{qualite['identifiants_en_double']} code(s) en double dans le fichier : vérifiez l’extraction.")
    if jeu == 'ventes' and qualite.get('negatifs'):
        qualite['negatifs'] = 0                                    # avoirs en négatif : normal pour les ventes
    if qualite.get('negatifs'):
        qualite['avertissements'].append(f"{qualite['negatifs']} montant(s) négatif(s) (avoirs ou annulations ?) : ils sont exclus des tests de doublons.")
    if qualite.get('doublons_exacts'):
        qualite['avertissements'].append(f"{qualite['doublons_exacts']} ligne(s) strictement identique(s) à une autre : extraction en double, ou anomalie réelle.")
    return df, qualite


# ====================================================================== stockage du tableau normalisé
def vers_octets(df):
    tampon = io.StringIO()
    out = df.copy()
    horo = {c[0] for j in JEUX.values() for c in j['champs'] if c[3] == 'horodatage'}
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime('%Y-%m-%d %H:%M:%S' if c in horo else '%Y-%m-%d')
    out.to_csv(tampon, index=False)
    return gzip.compress(tampon.getvalue().encode('utf-8'))


def depuis_octets(jeu, octets):
    df = pd.read_csv(io.BytesIO(gzip.decompress(octets)), dtype=str, keep_default_na=False)
    for code, _lib, _o, typ, _s in champs(jeu):
        if code not in df.columns:
            df[code] = ''
        if typ in ('date', 'horodatage'):
            df[code] = pd.to_datetime(df[code].where(df[code] != '', None), format='%Y-%m-%d %H:%M:%S' if typ == 'horodatage' else '%Y-%m-%d',
                                      errors='coerce')
        elif typ in ('montant', 'nombre'):
            df[code] = pd.to_numeric(df[code].where(df[code] != '', None), errors='coerce')
        else:
            df[code] = df[code].astype(object)
    df['_ligne'] = pd.to_numeric(df['_ligne'], errors='coerce').fillna(0).astype(int)
    return derives(jeu, df)


def derives(jeu, df):
    """Colonnes calculées : montant de la ligne d'écriture, avoirs."""
    if jeu == 'grand_livre':
        df['_mt'] = (df['debit'].fillna(0) - df['credit'].fillna(0)).abs()
    elif jeu == 'ventes':
        typ = df['type'].fillna('').astype(str).map(lambda v: sans_accents(v).lower())
        df['_avoir'] = typ.str.contains('avoir|credit|annul|retour', regex=True) | (df['montant'] < 0)
    return df


# ====================================================================== bibliothèque de tests
def _f(x):
    try:
        x = float(x)
        return None if math.isnan(x) else x
    except (TypeError, ValueError):
        return None


def _d(x):
    if x is None or (isinstance(x, float) and math.isnan(x)) or x is pd.NaT:
        return ''
    try:
        return pd.Timestamp(x).date().isoformat()
    except (TypeError, ValueError):
        return ''


class Contexte:
    """Données d'une exécution : tableaux normalisés + noms des fournisseurs pour l'affichage."""

    def __init__(self, donnees, devise='FCFA', cloture=None):
        self.d = {k: v for k, v in (donnees or {}).items() if v is not None and len(v)}
        self.devise = devise
        self.cloture = cloture                       # date de clôture de la période (datetime.date) ou None
        self.noms, self.noms_clients = {}, {}
        for jeu, cible in (('fournisseurs', self.noms), ('clients', self.noms_clients)):
            f = self.d.get(jeu)
            if f is not None:
                for code, nom in zip(f['code'], f['nom']):
                    if code:
                        cible.setdefault(norm_id(code), nom)

    def a(self, jeu, *champs_requis):
        df = self.d.get(jeu)
        if df is None:
            return False
        for c in champs_requis:
            if c not in df.columns:
                return False
            s = df[c]
            if pd.api.types.is_datetime64_any_dtype(s) or pd.api.types.is_numeric_dtype(s):
                if not s.notna().any():
                    return False
            elif not (s.fillna('').astype(str).str.strip() != '').any():
                return False
        return True

    def tiers(self, code, clients=False):
        nom = (self.noms_clients if clients else self.noms).get(norm_id(code)) if code else ''
        return f'{code} — {nom}' if nom and nom != code else (code or '')

    def anomalie(self, jeu, ligne, motif, groupe=None):
        info = JEUX[jeu]
        tiers = ligne.get(info['tiers'], '') if info['tiers'] else ''
        if jeu in ('factures', 'paiements', 'commandes'):
            tiers = self.tiers(tiers)
        elif jeu in ('ventes', 'encaissements', 'credits', 'operations'):
            tiers = self.tiers(tiers, clients=True)
        elif jeu in ('paie', 'utilisateurs_si'):
            tiers = f"{ligne.get('nom', '')}" + (f" ({ligne.get('matricule')})" if jeu == 'paie' and ligne.get('matricule') else '')
        elif jeu in ('fournisseurs', 'clients'):
            tiers = f"{ligne.get('code', '')} — {ligne.get('nom', '')}"
        elif jeu == 'grand_livre':
            tiers = f"{ligne.get('compte', '')}" + (f" · {ligne.get('libelle', '')}" if ligne.get('libelle') else '')
        return {'jeu': jeu, 'ligne': int(ligne.get('_ligne', 0) or 0), 'ref': str(ligne.get(info['ref'], '') or ''),
                'tiers': str(tiers or ''), 'date': _d(ligne.get(info['date'])) if info['date'] else '',
                'montant': (abs(_f(ligne.get(info['montant'])) or 0) if jeu in ('ventes', 'operations') else _f(ligne.get(info['montant'])))
                if info['montant'] else None,
                'motif': motif, 'groupe': groupe}


def _lignes(df):
    return df.to_dict('records')


def _grappes(dates, jours):
    """Regroupe des dates triées : deux dates consécutives à moins de `jours` jours sont dans la même grappe."""
    grappes, courant = [], []
    for i, d in dates:
        if courant and (d - courant[-1][1]).days > jours:
            grappes.append(courant)
            courant = []
        courant.append((i, d))
    if courant:
        grappes.append(courant)
    return [g for g in grappes if len(g) >= 2]


def _fr(x, dev=''):
    if x is None:
        return '—'
    s = f'{x:,.0f}'.replace(',', ' ') if abs(x - round(x)) < 0.005 else f'{x:,.2f}'.replace(',', ' ').replace('.', ',')
    return f'{s} {dev}'.strip()


def _jours_feries(texte_liste):
    fixes, dates = set(), set()
    for morceau in re.split(r'[\s,;]+', texte_liste or ''):
        m = re.fullmatch(r'(\d{1,2})/(\d{1,2})(?:/(\d{4}))?', morceau)
        if not m:
            continue
        j, mo, an = int(m.group(1)), int(m.group(2)), m.group(3)
        try:
            if an:
                dates.add(date(int(an), mo, j))
            elif 1 <= j <= 31 and 1 <= mo <= 12:
                fixes.add((mo, j))
        except ValueError:
            continue
    return fixes, dates


def _plafonds(texte_liste):
    res = {}
    for l in (texte_liste or '').splitlines():
        if '=' in l:
            nom, _sep, mt = l.rpartition('=')
            x = lire_montant(mt.strip())
            if nom.strip() and isinstance(x, float):
                res[norm_nom(nom)] = x
    return res


# --- tests ------------------------------------------------------------------------------------------
def t_fac_doublon(c, p):
    df = c.d['factures']
    df = df[df['montant'] > 0].dropna(subset=['date'])
    res, g = [], 0
    for (_f_, _m), grp in df.assign(_fn=df['fournisseur'].map(norm_id), _mr=df['montant'].round(2)).groupby(['_fn', '_mr']):
        if len(grp) < 2 or not _f_:
            continue
        recs = _lignes(grp.sort_values('date'))
        for grappe in _grappes([(i, r['date']) for i, r in enumerate(recs)], int(p['jours'])):
            g += 1
            nums = ', '.join(str(recs[i]['numero']) for i, _d_ in grappe)
            for i, _d_ in grappe:
                res.append(c.anomalie('factures', recs[i], f'Même fournisseur et même montant à moins de {int(p["jours"])} jours (factures {nums})', g))
    return res, len(df)


def t_fac_numero(c, p):
    df = c.d['factures']
    df = df.assign(_fn=df['fournisseur'].map(norm_id), _nn=df['numero'].map(norm_id))
    df = df[(df['_nn'] != '') & (df['_fn'] != '')]
    res, g = [], 0
    for _k, grp in df.groupby(['_fn', '_nn']):
        if len(grp) < 2:
            continue
        g += 1
        montants = ' / '.join(_fr(_f(x)) for x in grp['montant'])
        for r in _lignes(grp):
            res.append(c.anomalie('factures', r, f'Numéro de facture saisi {len(grp)} fois pour ce fournisseur (montants : {montants})', g))
    return res, len(df)


def t_pai_doublon(c, p):
    df = c.d['paiements']
    df = df[df['montant'] > 0].dropna(subset=['date'])
    res, g = [], 0
    for (_f_, _m), grp in df.assign(_fn=df['fournisseur'].map(norm_id), _mr=df['montant'].round(2)).groupby(['_fn', '_mr']):
        if len(grp) < 2 or not _f_:
            continue
        recs = _lignes(grp.sort_values('date'))
        for grappe in _grappes([(i, r['date']) for i, r in enumerate(recs)], int(p['jours'])):
            g += 1
            refs = ', '.join(str(recs[i]['reference']) for i, _d_ in grappe)
            meme_fact = len({norm_id(recs[i].get('facture', '')) for i, _d_ in grappe} - {''}) == 1
            for i, _d_ in grappe:
                res.append(c.anomalie('paiements', recs[i], f'Même bénéficiaire et même montant à moins de {int(p["jours"])} jours (paiements {refs})'
                                      + (' — même facture' if meme_fact else ''), g))
    return res, len(df)


def t_pai_sans_facture(c, p):
    pa, fa = c.d['paiements'], c.d['factures']
    nums = set(fa['numero'].map(norm_id)) - {''}
    res = []
    for r in _lignes(pa):
        if (_f(r['montant']) or 0) < float(p['montant_min']):
            continue
        ref = norm_id(r.get('facture', ''))
        if not ref:
            res.append(c.anomalie('paiements', r, 'Paiement sans référence de facture'))
        elif ref not in nums:
            res.append(c.anomalie('paiements', r, f'Facture {r["facture"]} introuvable dans le fichier des factures'))
    return res, len(pa)


def t_pai_sup_facture(c, p):
    pa, fa = c.d['paiements'], c.d['factures']
    pa = pa.assign(_nf=pa['facture'].map(norm_id))
    pa = pa[pa['_nf'] != '']
    montants = {}
    for r in _lignes(fa):
        k = norm_id(r['numero'])
        if k and _f(r['montant']) is not None:
            montants[k] = montants.get(k, 0) + r['montant']
    tol = float(p['tolerance_pct']) / 100
    res, g = [], 0
    for k, grp in pa.groupby('_nf'):
        if k not in montants:
            continue
        paye = float(grp['montant'].sum(skipna=True))
        if paye > montants[k] * (1 + tol) + 0.5:
            g += 1
            for r in _lignes(grp):
                res.append(c.anomalie('paiements', r, f'Facture {r["facture"]} : payé {_fr(paye, c.devise)} pour une facture de {_fr(montants[k], c.devise)} '
                                      f'(trop-payé {_fr(paye - montants[k], c.devise)}, {len(grp)} paiement(s))', g))
    return res, len(pa)


def t_fac_sans_bc(c, p):
    fa = c.d['factures']
    bcs = set(c.d['commandes']['numero'].map(norm_id)) - {''} if c.a('commandes', 'numero') else None
    res = []
    for r in _lignes(fa):
        if (_f(r['montant']) or 0) < float(p['montant_min']):
            continue
        bc = norm_id(r.get('commande', ''))
        if not bc:
            res.append(c.anomalie('factures', r, 'Facture sans bon de commande'))
        elif bcs is not None and bc not in bcs:
            res.append(c.anomalie('factures', r, f'Bon de commande {r["commande"]} introuvable dans le fichier des commandes'))
    return res, len(fa)


def t_bc_apres_facture(c, p):
    fa, bc = c.d['factures'], c.d['commandes']
    dates = {}
    for r in _lignes(bc.dropna(subset=['date'])):
        k = norm_id(r['numero'])
        if k:
            dates[k] = min(dates.get(k, r['date']), r['date'])
    res = []
    for r in _lignes(fa.dropna(subset=['date'])):
        k = norm_id(r.get('commande', ''))
        if k in dates and dates[k] > r['date']:
            res.append(c.anomalie('factures', r, f'Commande {r["commande"]} datée du {dates[k].strftime("%d/%m/%Y")}, '
                                  f'après la facture ({(dates[k] - r["date"]).days} jours) : commande de régularisation'))
    return res, len(fa)


def t_fractionnement(c, p):
    jeu = 'commandes' if c.a('commandes', 'montant', 'date', 'fournisseur') else 'factures'
    df = c.d[jeu]
    seuil, jours = float(p['seuil']), int(p['jours'])
    plancher = seuil * float(p['part_min_pct']) / 100
    sous = df[(df['montant'] >= plancher) & (df['montant'] > 0) & (df['montant'] < seuil)].dropna(subset=['date'])
    res, g = [], 0
    for _f_, grp in sous.assign(_fn=sous['fournisseur'].map(norm_id)).groupby('_fn'):
        if len(grp) < 2 or not _f_:
            continue
        recs = _lignes(grp.sort_values('date'))
        fenetres = []                       # toutes les fenêtres de `jours` jours dont le total atteint le seuil
        for i in range(len(recs)):
            j = i
            while j + 1 < len(recs) and (recs[j + 1]['date'] - recs[i]['date']).days <= jours:
                j += 1
            if j > i and sum(_f(r['montant']) or 0 for r in recs[i:j + 1]) >= seuil:
                fenetres.append([i, j])
        fusion = []                         # fenêtres qui se chevauchent = un seul cas
        for i, j in fenetres:
            if fusion and i <= fusion[-1][1]:
                fusion[-1][1] = max(fusion[-1][1], j)
            else:
                fusion.append([i, j])
        for i, j in fusion:
            bloc = recs[i:j + 1]
            total = sum(_f(r['montant']) or 0 for r in bloc)
            g += 1
            for r in bloc:
                res.append(c.anomalie(jeu, r, f'{len(bloc)} {JEUX[jeu]["libelle"].lower()} du même fournisseur entre le '
                                      f'{bloc[0]["date"].strftime("%d/%m/%Y")} et le {bloc[-1]["date"].strftime("%d/%m/%Y")}, '
                                      f'chacune sous le seuil de {_fr(seuil, c.devise)}, total {_fr(total, c.devise)}', g))
    return res, len(df)


def t_delegation(c, p):
    plafonds, seuil = _plafonds(p['plafonds']), float(p['seuil'])
    res, population = [], 0
    for jeu in ('commandes', 'paiements'):
        if not c.a(jeu, 'approuve_par'):
            continue
        df = c.d[jeu]
        population += len(df)
        for r in _lignes(df):
            mt = _f(r['montant'])
            if mt is None:
                continue
            qui = norm_nom(r.get('approuve_par', ''))
            if not qui:
                if mt >= seuil:
                    res.append(c.anomalie(jeu, r, f'Aucun approbateur pour un montant supérieur au seuil de {_fr(seuil, c.devise)}'))
            elif qui in plafonds and mt > plafonds[qui]:
                res.append(c.anomalie(jeu, r, f'Approuvé par {r["approuve_par"]} au-delà de son plafond ({_fr(plafonds[qui], c.devise)})'))
            elif plafonds and qui not in plafonds and mt >= seuil:
                res.append(c.anomalie(jeu, r, f'Approuvé par {r["approuve_par"]}, absent de la liste des délégations'))
    return res, population


def t_separation(c, p):
    res, population = [], 0
    pa = c.d['paiements']
    population = len(pa)
    createurs = {}
    if c.a('fournisseurs', 'cree_par'):
        for r in _lignes(c.d['fournisseurs']):
            if norm_id(r['code']) and norm_nom(r.get('cree_par', '')):
                createurs[norm_id(r['code'])] = r['cree_par']
    saisies = {}
    if c.a('factures', 'saisi_par'):
        for r in _lignes(c.d['factures']):
            if norm_id(r['numero']) and norm_nom(r.get('saisi_par', '')):
                saisies[norm_id(r['numero'])] = r['saisi_par']
    for r in _lignes(pa):
        app = norm_nom(r.get('approuve_par', ''))
        if not app:
            continue
        cr = createurs.get(norm_id(r['fournisseur']))
        if cr and norm_nom(cr) == app:
            res.append(c.anomalie('paiements', r, f'{r["approuve_par"]} a créé le fournisseur et approuvé son paiement'))
            continue
        sa = saisies.get(norm_id(r.get('facture', '')))
        if sa and norm_nom(sa) == app:
            res.append(c.anomalie('paiements', r, f'{r["approuve_par"]} a saisi la facture et approuvé son paiement'))
    return res, population


def t_rib_partage(c, p):
    res, g = [], 0
    fo = c.d['fournisseurs']
    fo = fo.assign(_r=fo['rib'].map(norm_rib), _c=fo['code'].map(norm_id))
    fo = fo[fo['_r'].str.len() >= 10]
    for rib, grp in fo.groupby('_r'):
        if grp['_c'].nunique() < 2:
            continue
        g += 1
        codes = ', '.join(sorted(set(grp['code'].astype(str))))
        for r in _lignes(grp):
            res.append(c.anomalie('fournisseurs', r, f'RIB partagé par {grp["_c"].nunique()} fournisseurs ({codes})', g))
    return res, len(c.d['fournisseurs'])


def t_rib_salarie(c, p):
    fo, sa = c.d['fournisseurs'], c.d['salaries']
    par_rib, par_tel, par_adr = {}, {}, {}
    for r in _lignes(sa):
        if len(norm_rib(r['rib'])) >= 10:
            par_rib[norm_rib(r['rib'])] = r
        if norm_tel(r.get('telephone', '')):
            par_tel[norm_tel(r['telephone'])] = r
        a = norm_nom(r.get('adresse', ''))
        if len(a) >= 10:
            par_adr[a] = r
    res = []
    for r in _lignes(fo):
        s = par_rib.get(norm_rib(r['rib']))
        if s:
            res.append(c.anomalie('fournisseurs', r, f'Même RIB que le salarié {s["matricule"]} — {s["nom"]}'))
            continue
        s = par_tel.get(norm_tel(r.get('telephone', '')))
        if s:
            res.append(c.anomalie('fournisseurs', r, f'Même téléphone que le salarié {s["matricule"]} — {s["nom"]}'))
            continue
        s = par_adr.get(norm_nom(r.get('adresse', '')))
        if s:
            res.append(c.anomalie('fournisseurs', r, f'Même adresse que le salarié {s["matricule"]} — {s["nom"]}'))
    return res, len(fo)


def t_rib_paiement(c, p):
    pa, fo = c.d['paiements'], c.d['fournisseurs']
    ribs = {}
    for r in _lignes(fo):
        if norm_id(r['code']) and len(norm_rib(r['rib'])) >= 10:
            ribs.setdefault(norm_id(r['code']), set()).add(norm_rib(r['rib']))
    res = []
    for r in _lignes(pa):
        attendu = ribs.get(norm_id(r['fournisseur']))
        recu = norm_rib(r.get('rib', ''))
        if attendu and len(recu) >= 10 and recu not in attendu:
            res.append(c.anomalie('paiements', r, f'Payé sur le compte …{recu[-6:]} alors que la fiche du fournisseur indique …'
                                  + ' / …'.join(x[-6:] for x in sorted(attendu))))
    return res, len(pa)


def t_rib_modifie(c, p):
    pa, fo = c.d['paiements'], c.d['fournisseurs']
    modifs = {norm_id(r['code']): r['date_modif_rib'] for r in _lignes(fo.dropna(subset=['date_modif_rib'])) if norm_id(r['code'])}
    jours = int(p['jours'])
    res = []
    for r in _lignes(pa.dropna(subset=['date'])):
        dm = modifs.get(norm_id(r['fournisseur']))
        if dm is not None and timedelta(0) <= r['date'] - dm <= timedelta(days=jours):
            res.append(c.anomalie('paiements', r, f'RIB du fournisseur modifié le {dm.strftime("%d/%m/%Y")}, '
                                  f'{(r["date"] - dm).days} jour(s) avant ce paiement'))
    return res, len(pa)


def t_fournisseur_recent(c, p):
    pa, fo = c.d['paiements'], c.d['fournisseurs']
    crees = {norm_id(r['code']): r['date_creation'] for r in _lignes(fo.dropna(subset=['date_creation'])) if norm_id(r['code'])}
    jours = int(p['jours'])
    res = []
    for r in _lignes(pa.dropna(subset=['date'])):
        dc = crees.get(norm_id(r['fournisseur']))
        if dc is not None and timedelta(0) <= r['date'] - dc <= timedelta(days=jours):
            res.append(c.anomalie('paiements', r, f'Fournisseur créé le {dc.strftime("%d/%m/%Y")}, payé {(r["date"] - dc).days} jour(s) après'))
    return res, len(pa)


def t_fournisseur_inconnu(c, p):
    fo = c.d['fournisseurs']
    connus = set(fo['code'].map(norm_id)) - {''}
    bloques = set()
    if c.a('fournisseurs', 'statut'):
        for r in _lignes(fo):
            if re.search(r'bloqu|inactif|ferm|suspendu|supprim|non|blocked|inactive', sans_accents(r.get('statut', '')).lower()):
                bloques.add(norm_id(r['code']))
    res, population = [], 0
    for jeu in ('paiements', 'factures'):
        if not c.a(jeu, 'fournisseur'):
            continue
        population += len(c.d[jeu])
        for r in _lignes(c.d[jeu]):
            k = norm_id(r['fournisseur'])
            if not k:
                continue
            if k not in connus:
                res.append(c.anomalie(jeu, r, 'Fournisseur absent du fichier des fournisseurs'))
            elif k in bloques:
                res.append(c.anomalie(jeu, r, 'Fournisseur bloqué ou inactif dans le fichier des fournisseurs'))
    return res, population


def t_weekend(c, p):
    fixes, dates = _jours_feries(p['feries'])
    res, population = [], 0
    for jeu, champ, quoi in (('paiements', 'date', 'Paiement'), ('factures', 'date_saisie', 'Facture saisie')):
        if not c.a(jeu, champ):
            continue
        df = c.d[jeu].dropna(subset=[champ])
        population += len(df)
        for r in _lignes(df):
            d = r[champ].date()
            if d.weekday() >= 5:
                res.append(c.anomalie(jeu, r, f'{quoi} un {("samedi", "dimanche")[d.weekday() - 5]} ({d.strftime("%d/%m/%Y")})'))
            elif (d.month, d.day) in fixes or d in dates:
                res.append(c.anomalie(jeu, r, f'{quoi} un jour férié ({d.strftime("%d/%m/%Y")})'))
    return res, population


def t_montants_ronds(c, p):
    base, mini = float(p['multiple']), float(p['montant_min'])
    res, population = [], 0
    for jeu in ('paiements', 'factures'):
        if not c.a(jeu, 'montant'):
            continue
        df = c.d[jeu].dropna(subset=['montant'])
        population += len(df)
        for r in _lignes(df[(df['montant'] >= mini) & ((df['montant'] % base).abs() < 0.005)]):
            res.append(c.anomalie(jeu, r, f'Montant rond (multiple de {_fr(base, c.devise)})'))
    return res, population


BENFORD = {d: math.log10(1 + 1 / d) for d in range(1, 10)}


def t_benford(c, p):
    return _benford(c, p, 'factures' if c.a('factures', 'montant') else 'paiements', 'montant')


def _benford(c, p, jeu, champ):
    df = c.d[jeu].dropna(subset=[champ])
    df = df[df[champ] >= 10]
    n = len(df)
    if n < int(p['minimum']):
        return None, f'Trop peu de montants ({n}) : la loi de Benford n’est significative qu’à partir de {int(p["minimum"])} montants.'
    premier = df[champ].map(lambda x: int(str(int(abs(x)))[0]))
    obs = premier.value_counts().to_dict()
    tableau, mad, sur = [], 0.0, []
    for d in range(1, 10):
        o = obs.get(d, 0) / n
        e = BENFORD[d]
        z = (abs(o - e) - 1 / (2 * n)) / math.sqrt(e * (1 - e) / n)
        mad += abs(o - e)
        tableau.append({'chiffre': d, 'observe': round(o * 100, 1), 'attendu': round(e * 100, 1), 'z': round(z, 2), 'nombre': obs.get(d, 0)})
        if o > e and z > 1.96:
            sur.append(d)
    mad /= 9
    conformite = ('conformité étroite' if mad <= 0.006 else 'conformité acceptable' if mad <= 0.012
                  else 'conformité marginale' if mad <= 0.015 else 'non-conformité')
    if mad <= 0.012:
        sur = []                       # conformité étroite ou acceptable : pas de liste d'anomalies, seul le tableau compte
    res = []
    for r, ch in zip(_lignes(df), premier):
        if ch in sur:
            res.append(c.anomalie(jeu, r, f'Premier chiffre {ch}, sur-représenté par rapport à la loi de Benford'))
    return res, n, {'tableau': tableau, 'mad': round(mad, 4), 'conformite': conformite, 'sur_representes': sur, 'jeu': jeu}


def t_concentration(c, p):
    jeu = 'paiements' if c.a('paiements', 'montant') else 'factures'
    df = c.d[jeu].dropna(subset=['montant'])
    df = df[df['montant'] > 0]
    total = float(df['montant'].sum())
    if not total:
        return [], len(df)
    parts = df.assign(_fn=df['fournisseur'].map(norm_id)).groupby('_fn').agg(montant=('montant', 'sum'), nb=('montant', 'size'),
                                                                               code=('fournisseur', 'first'))
    parts = parts.sort_values('montant', ascending=False)
    seuil = float(p['part_pct']) / 100
    tableau, res = [], []
    cumul = 0.0
    for k, row in parts.head(10).iterrows():
        cumul += row['montant']
        tableau.append({'tiers': c.tiers(row['code']), 'montant': float(row['montant']), 'part': round(row['montant'] / total * 100, 1),
                        'cumul': round(cumul / total * 100, 1), 'nombre': int(row['nb'])})
        if row['montant'] / total >= seuil:
            res.append({'jeu': jeu, 'ligne': 0, 'ref': '', 'tiers': c.tiers(row['code']), 'date': '', 'montant': float(row['montant']),
                        'motif': f'{round(row["montant"] / total * 100, 1)} % du total ({int(row["nb"])} opérations)', 'groupe': None})
    return res, len(df), {'tableau': tableau, 'total': total, 'fournisseurs': int(len(parts)), 'jeu': jeu}


def t_prix_unitaire(c, p):
    bc = c.d['commandes']
    bc = bc.assign(_a=bc['article'].map(norm_nom))
    if c.a('commandes', 'prix_unitaire'):
        pu = bc['prix_unitaire']
    else:
        pu = bc['montant'] / bc['quantite'].where(bc['quantite'] > 0)
    bc = bc.assign(_pu=pu)
    bc = bc[(bc['_a'] != '') & bc['_pu'].notna() & (bc['_pu'] > 0)]
    ecart = float(p['ecart_pct']) / 100
    res, g = [], 0
    for _a, grp in bc.groupby('_a'):
        if len(grp) < 3:
            continue
        med = float(grp['_pu'].median())
        trop = grp[grp['_pu'] > med * (1 + ecart)]
        if len(trop):
            g += 1
        for r in _lignes(trop):
            res.append(c.anomalie('commandes', r, f'« {r["article"]} » acheté {_fr(r["_pu"], c.devise)} l’unité, '
                                  f'{round((r["_pu"] / med - 1) * 100)} % au-dessus du prix médian ({_fr(med, c.devise)}, {len(grp)} achats)', g))
    return res, len(bc)


# (code, titre, domaine, fonction, jeux et champs requis [(jeu, (champs…))], paramètres, niveau, description,
#  critère, conséquence, recommandation)
# Paramètres : (code, libellé, défaut, aide)
FERIES_CI = '01/01 01/05 07/08 15/08 01/11 15/11 25/12'
TESTS = [
    dict(code='FAC_DOUBLON', titre='Factures en double', domaine='Factures', f=t_fac_doublon, requis=[('factures', ('fournisseur', 'montant', 'date'))],
         params=[('jours', 'Écart maximal entre les dates (jours)', 30, '')], niveau='eleve',
         description='Même fournisseur, même montant, dates proches : facture enregistrée deux fois, ou présentée deux fois par le fournisseur.',
         critere='Chaque facture fournisseur ne doit être enregistrée et payée qu’une seule fois (contrôle d’unicité à la saisie).',
         consequence='Risque de double paiement et de perte financière ; charges surévaluées.',
         recommandation='Activer le contrôle bloquant des doublons (fournisseur, numéro, montant) dans le logiciel et récupérer les sommes payées en double.'),
    dict(code='FAC_NUMERO', titre='Numéro de facture en double', domaine='Factures', f=t_fac_numero, requis=[('factures', ('fournisseur', 'numero'))],
         params=[], niveau='eleve',
         description='Le même numéro de facture est enregistré plusieurs fois pour un même fournisseur (même si le montant diffère).',
         critere='Un numéro de facture est unique pour un fournisseur donné.',
         consequence='Double comptabilisation ou double paiement ; possible falsification de facture.',
         recommandation='Rendre l’unicité du couple fournisseur / numéro de facture obligatoire à la saisie et régulariser les doublons.'),
    dict(code='PAI_DOUBLON', titre='Paiements en double', domaine='Paiements', f=t_pai_doublon, requis=[('paiements', ('fournisseur', 'montant', 'date'))],
         params=[('jours', 'Écart maximal entre les dates (jours)', 10, '')], niveau='eleve',
         description='Même bénéficiaire, même montant, dates proches.',
         critere='Un paiement n’est émis qu’une fois, sur une facture approuvée et non encore réglée.',
         consequence='Perte financière directe si le doublon n’est pas récupéré.',
         recommandation='Rapprocher chaque paiement d’une facture non soldée avant émission ; demander le remboursement des doublons.'),
    dict(code='PAI_SANS_FACTURE', titre='Paiements sans facture', domaine='Paiements', f=t_pai_sans_facture,
         requis=[('paiements', ('facture',)), ('factures', ('numero',))],
         params=[('montant_min', 'Montant minimal analysé', 0, 'Pour ignorer les petites dépenses')], niveau='eleve',
         description='Paiement sans référence de facture, ou dont la facture n’existe pas dans le fichier des factures.',
         critere='Tout paiement fournisseur est justifié par une facture enregistrée et approuvée.',
         consequence='Paiements non justifiés : risque de fraude ou d’erreur, charges non documentées.',
         recommandation='Interdire l’émission d’un paiement sans facture enregistrée ; obtenir les justificatifs des paiements relevés.'),
    dict(code='PAI_SUP_FACTURE', titre='Factures payées au-delà de leur montant', domaine='Paiements', f=t_pai_sup_facture,
         requis=[('paiements', ('facture', 'montant')), ('factures', ('numero', 'montant'))],
         params=[('tolerance_pct', 'Tolérance (%)', 0.5, 'Écarts de change ou d’arrondi')], niveau='eleve',
         description='La somme des paiements d’une facture dépasse son montant.',
         critere='Le total payé sur une facture n’excède pas son montant.',
         consequence='Trop-payé à récupérer ; possible paiement en double par acomptes.',
         recommandation='Bloquer le paiement d’une facture soldée et récupérer les trop-payés.'),
    dict(code='FAC_SANS_BC', titre='Factures sans bon de commande', domaine='Achats', f=t_fac_sans_bc, requis=[('factures', ('commande',))],
         params=[('montant_min', 'Montant minimal analysé', 0, 'Par exemple le seuil au-delà duquel un bon de commande est obligatoire')],
         niveau='moyen',
         description='Facture sans bon de commande, ou dont le bon de commande n’existe pas.',
         critere='Tout achat au-delà du seuil fixé par la procédure fait l’objet d’un bon de commande approuvé avant la livraison.',
         consequence='Engagements de dépenses hors circuit d’approbation ; budget non maîtrisé.',
         recommandation='Rendre le bon de commande obligatoire au-delà du seuil et rejeter les factures sans commande.'),
    dict(code='BC_APRES_FACTURE', titre='Commandes postérieures à la facture', domaine='Achats', f=t_bc_apres_facture,
         requis=[('factures', ('commande', 'date')), ('commandes', ('numero', 'date'))], params=[], niveau='moyen',
         description='Le bon de commande est daté après la facture : la commande a régularisé un achat déjà fait.',
         critere='Le bon de commande est émis et approuvé avant la facture.',
         consequence='Contournement du circuit d’approbation des achats.',
         recommandation='Interdire les commandes de régularisation, ou les soumettre à une approbation spécifique et tracée.'),
    dict(code='FRACTIONNEMENT', titre='Achats fractionnés sous le seuil', domaine='Achats', f=t_fractionnement,
         requis=[('factures|commandes', ('fournisseur', 'montant', 'date'))],
         params=[('seuil', 'Seuil d’approbation ou d’appel d’offres', 5_000_000, ''), ('jours', 'Période regroupée (jours)', 7, ''),
                 ('part_min_pct', 'Ne retenir que les achats d’au moins (% du seuil)', 25, 'Écarte les petits achats courants')],
         niveau='eleve',
         description='Plusieurs achats auprès du même fournisseur, chacun sous le seuil, dont le total le dépasse : fractionnement pour éviter l’approbation ou la mise en concurrence.',
         critere='Un besoin ne doit pas être fractionné pour rester sous un seuil d’approbation ou de mise en concurrence.',
         consequence='Contournement des délégations et des appels d’offres ; risque de favoritisme.',
         recommandation='Contrôler le cumul des achats par fournisseur sur une période glissante et sanctionner le fractionnement.'),
    dict(code='DELEGATION', titre='Approbations hors délégation', domaine='Achats', f=t_delegation,
         requis=[('commandes|paiements', ('approuve_par', 'montant'))],
         params=[('seuil', 'Montant à partir duquel une approbation est exigée', 1_000_000, ''),
                 ('plafonds', 'Délégations (une par ligne : « Nom = plafond »)', '', 'Ex. : Kouassi Jean = 10 000 000')],
         niveau='eleve',
         description='Opération non approuvée au-delà du seuil, ou approuvée au-delà du plafond de délégation de l’approbateur.',
         critere='Chaque engagement est approuvé par une personne dont la délégation couvre le montant.',
         consequence='Engagements non autorisés ; non-respect de la gouvernance.',
         recommandation='Paramétrer les plafonds de délégation dans le logiciel (approbation bloquante) et mettre à jour la matrice des délégations.'),
    dict(code='SEPARATION', titre='Séparation des tâches', domaine='Fournisseurs', f=t_separation,
         requis=[('paiements', ('approuve_par',)), ('fournisseurs|factures', ('cree_par|saisi_par',))], params=[], niveau='eleve',
         description='La même personne crée le fournisseur (ou saisit la facture) puis approuve son paiement.',
         critere='La création des fournisseurs, la saisie des factures et l’approbation des paiements sont confiées à des personnes différentes.',
         consequence='Une seule personne peut créer un fournisseur fictif et le payer : risque élevé de fraude.',
         recommandation='Séparer les droits dans le logiciel (matrice des incompatibilités) et revoir les paiements concernés.'),
    dict(code='RIB_PARTAGE', titre='RIB partagé entre fournisseurs', domaine='Fournisseurs', f=t_rib_partage, requis=[('fournisseurs', ('rib', 'code'))],
         params=[], niveau='eleve',
         description='Le même compte bancaire figure sur la fiche de plusieurs fournisseurs.',
         critere='Chaque fournisseur a son propre compte bancaire, vérifié à la création.',
         consequence='Signe de fournisseur fictif ou de détournement de paiements.',
         recommandation='Vérifier l’identité des fournisseurs concernés et la titularité des comptes ; bloquer les doublons de RIB à la création.'),
    dict(code='RIB_SALARIE', titre='Fournisseur lié à un salarié', domaine='Fournisseurs', f=t_rib_salarie,
         requis=[('fournisseurs', ('rib',)), ('salaries', ('rib',))], params=[], niveau='eleve',
         description='Un fournisseur a le même RIB, le même téléphone ou la même adresse qu’un salarié.',
         critere='Les liens entre salariés et fournisseurs sont déclarés (conflits d’intérêts) et approuvés.',
         consequence='Conflit d’intérêts non déclaré ou fournisseur fictif au profit d’un salarié.',
         recommandation='Obtenir les déclarations de conflits d’intérêts, analyser les paiements concernés et bloquer les fiches non justifiées.'),
    dict(code='RIB_PAIEMENT', titre='Paiement sur un autre compte que celui du fournisseur', domaine='Paiements', f=t_rib_paiement,
         requis=[('paiements', ('rib', 'fournisseur')), ('fournisseurs', ('rib', 'code'))], params=[], niveau='eleve',
         description='Le compte crédité est différent du RIB enregistré sur la fiche du fournisseur.',
         critere='Les paiements sont émis uniquement vers le compte enregistré et vérifié du fournisseur.',
         consequence='Détournement de paiement (fraude au changement de RIB).',
         recommandation='Interdire la saisie libre du compte bénéficiaire ; confirmer par contre-appel tout changement de RIB.'),
    dict(code='RIB_MODIFIE', titre='RIB modifié peu avant un paiement', domaine='Paiements', f=t_rib_modifie,
         requis=[('paiements', ('date', 'fournisseur')), ('fournisseurs', ('date_modif_rib',))],
         params=[('jours', 'Délai entre la modification et le paiement (jours)', 30, '')], niveau='moyen',
         description='Le RIB du fournisseur a été modifié dans les jours qui précèdent un paiement.',
         critere='Toute modification de RIB est confirmée auprès du fournisseur (contre-appel) avant le paiement suivant.',
         consequence='Fraude au changement de coordonnées bancaires.',
         recommandation='Vérifier la preuve de confirmation de chaque changement de RIB relevé.'),
    dict(code='FOURN_RECENT', titre='Fournisseur récent payé rapidement', domaine='Fournisseurs', f=t_fournisseur_recent,
         requis=[('paiements', ('date', 'fournisseur')), ('fournisseurs', ('date_creation',))],
         params=[('jours', 'Délai entre la création et le paiement (jours)', 30, '')], niveau='moyen',
         description='Fournisseur payé dans les jours qui suivent sa création.',
         critere='Un nouveau fournisseur fait l’objet de vérifications (existence, références, mise en concurrence) avant tout paiement.',
         consequence='Signe possible de fournisseur fictif ou de fournisseur imposé hors procédure.',
         recommandation='Vérifier le dossier de référencement des fournisseurs concernés.'),
    dict(code='FOURN_INCONNU', titre='Fournisseur absent ou bloqué', domaine='Fournisseurs', f=t_fournisseur_inconnu,
         requis=[('fournisseurs', ('code',)), ('paiements|factures', ('fournisseur',))], params=[], niveau='eleve',
         description='Facture ou paiement d’un fournisseur absent du fichier des fournisseurs, ou bloqué / inactif.',
         critere='Seuls les fournisseurs référencés et actifs peuvent être facturés et payés.',
         consequence='Paiements hors référentiel : fraude ou erreur d’imputation.',
         recommandation='Rendre la fiche fournisseur active obligatoire pour toute saisie et analyser les opérations relevées.'),
    dict(code='WEEKEND', titre='Paiements le week-end ou un jour férié', domaine='Paiements', f=t_weekend, requis=[('paiements', ('date',))],
         params=[('feries', 'Jours fériés (jj/mm ou jj/mm/aaaa)', FERIES_CI, 'Fêtes fixes de Côte d’Ivoire par défaut ; ajoutez les fêtes mobiles de la période')],
         niveau='faible',
         description='Paiement émis (ou facture saisie) un samedi, un dimanche ou un jour férié.',
         critere='Les opérations sont réalisées pendant les heures ouvrées, ou font l’objet d’une autorisation particulière.',
         consequence='Opérations échappant à la supervision habituelle.',
         recommandation='Justifier les opérations relevées et limiter les accès hors jours ouvrés.'),
    dict(code='MONTANTS_RONDS', titre='Montants ronds', domaine='Analyse des montants', f=t_montants_ronds, requis=[('paiements|factures', ('montant',))],
         params=[('multiple', 'Multiple de', 100_000, ''), ('montant_min', 'À partir de', 1_000_000, '')], niveau='faible',
         description='Montants élevés et parfaitement ronds, inhabituels pour des factures réelles (TVA, quantités).',
         critere='Les montants facturés correspondent à des quantités et prix réels.',
         consequence='Indice d’estimation, d’avance non justifiée ou de facture fictive.',
         recommandation='Obtenir les justificatifs détaillés des opérations relevées.'),
    dict(code='BENFORD', titre='Loi de Benford', domaine='Analyse des montants', f=t_benford, requis=[('factures|paiements', ('montant',))],
         params=[('minimum', 'Nombre minimal de montants', 300, '')], niveau='faible',
         description='Répartition des premiers chiffres des montants comparée à la loi de Benford : un écart signale des montants fabriqués ou une manipulation de seuils.',
         critere='Dans une population naturelle de montants, la répartition des premiers chiffres suit la loi de Benford.',
         consequence='Indice de manipulation des montants (à confirmer par des tests détaillés).',
         recommandation='Examiner les opérations des chiffres sur-représentés.'),
    dict(code='CONCENTRATION', titre='Concentration sur quelques fournisseurs', domaine='Analyse des montants', f=t_concentration,
         requis=[('paiements|factures', ('montant', 'fournisseur'))],
         params=[('part_pct', 'Part du total à partir de laquelle signaler (%)', 20, '')], niveau='faible',
         description='Fournisseurs qui concentrent une part importante des achats.',
         critere='La dépendance envers un fournisseur est connue, justifiée et suivie.',
         consequence='Dépendance, pouvoir de négociation réduit, risque de favoritisme.',
         recommandation='Vérifier la mise en concurrence et les contrats des fournisseurs relevés.'),
    dict(code='PRIX_UNITAIRE', titre='Écarts de prix pour un même article', domaine='Achats', f=t_prix_unitaire,
         requis=[('commandes', ('article', 'prix_unitaire|quantite'))],
         params=[('ecart_pct', 'Écart au prix médian (%)', 20, '')], niveau='moyen',
         description='Un même article acheté nettement plus cher que son prix habituel (prix médian, 3 achats au moins).',
         critere='Les prix d’achat respectent les contrats-cadres et les prix négociés.',
         consequence='Surfacturation, rétro-commissions ou mauvaise négociation.',
         recommandation='Justifier les écarts relevés et mettre en place des prix de référence par article.'),
]
TESTS_PAR_CODE = {t['code']: t for t in TESTS}
NIVEAUX = {'eleve': ('Élevé', 3), 'moyen': ('Moyen', 2), 'faible': ('Faible', 1)}
DOMAINES = ['Factures', 'Paiements', 'Achats', 'Fournisseurs', 'Analyse des montants']


# ====================================================================== lot 2 : comptabilité (grand livre)
COMPTES_GENERIQUES = {'admin', 'administrateur', 'administrator', 'sa', 'root', 'system', 'systeme', 'sysadmin', 'test', 'user', 'utilisateur',
                      'superviseur', 'interface', 'batch', 'import'}
LIBELLES_VAGUES = {'divers', 'div', 'regul', 'regularisation', 'od', 'ajustement', 'correction', 'ecart', 'x', 'xx', 'a', 'na', 'sans objet'}
SANS_CLOTURE = 'Indiquez la date de clôture de la période (en haut de l’étape Tests).'


def _liste(texte_liste):
    return [x.strip() for x in re.split(r'[\n,;]+', texte_liste or '') if x.strip()]


def _gl(c):
    df = c.d['grand_livre']
    jr = df['journal'].fillna('').astype(str).map(norm_id) if 'journal' in df.columns else ''
    return df.assign(_ecr=jr + '|' + df['numero'].fillna('').astype(str).map(norm_id), _cpt=df['compte'].fillna('').astype(str).map(lambda v: re.sub(r'\D', '', v) or v))


def _par_ecriture(df):
    return _lignes(df.drop_duplicates('_ecr'))


def _cl(c):
    return pd.Timestamp(c.cloture) if c.cloture else None


def t_gl_desequilibre(c, p):
    df = _gl(c)
    g = df.groupby('_ecr').agg(d=('debit', 'sum'), cr=('credit', 'sum'))
    ecarts = g[(g['d'] - g['cr']).abs() > float(p['tolerance'])]
    res = []
    premiere = {r['_ecr']: r for r in _par_ecriture(df)}
    for k, row in ecarts.iterrows():
        r = dict(premiere[k])
        r['_mt'] = abs(row['d'] - row['cr'])
        res.append(c.anomalie('grand_livre', r, f'Écriture déséquilibrée : débit {_fr(row["d"], c.devise)}, crédit {_fr(row["cr"], c.devise)}'))
    return res, df['_ecr'].nunique()


def t_gl_doublon(c, p):
    df = _gl(c)
    df = df[df['_mt'] > 0].dropna(subset=['date'])
    lib = df['libelle'].fillna('').astype(str).map(norm_nom) if 'libelle' in df.columns else ''
    df = df.assign(_k=df['_cpt'] + '|' + df['date'].dt.strftime('%Y%m%d') + '|' + df['_mt'].round(2).astype(str) + '|'
                   + (df['debit'].fillna(0) > 0).astype(str) + '|' + lib)
    res, g = [], 0
    for _k, grp in df.groupby('_k'):
        if grp['_ecr'].nunique() < 2:
            continue
        g += 1
        nums = ', '.join(sorted(set(grp['numero'].astype(str))))
        for r in _lignes(grp.drop_duplicates('_ecr')):
            res.append(c.anomalie('grand_livre', r, f'Même compte, même date, même montant et même libellé dans les écritures {nums}', g))
    return res, df['_ecr'].nunique()


def t_gl_sans_piece(c, p):
    df = _gl(c)
    avec_piece, avec_lib = c.a('grand_livre', 'piece'), c.a('grand_livre', 'libelle')
    res = []
    for r in _par_ecriture(df):
        motifs = []
        if avec_piece and not str(r.get('piece') or '').strip():
            motifs.append('sans pièce justificative')
        if avec_lib:
            lib = norm_nom(r.get('libelle') or '')
            if not lib:
                motifs.append('sans libellé')
            elif lib in LIBELLES_VAGUES or len(lib) <= 2:
                motifs.append(f'libellé non explicite (« {r["libelle"]} »)')
        if motifs and (_f(r['_mt']) or 0) >= float(p['montant_min']):
            res.append(c.anomalie('grand_livre', r, 'Écriture ' + ' et '.join(motifs)))
    return res, df['_ecr'].nunique()


def t_gl_hors_heures(c, p):
    df = _gl(c)
    fixes, dates = _jours_feries(p['feries'])
    h1, h2 = int(p['heure_debut']), int(p['heure_fin'])
    avec_heure = c.a('grand_livre', 'date_saisie') and bool((df['date_saisie'].dropna().dt.hour + df['date_saisie'].dropna().dt.minute > 0).any())
    champ = 'date_saisie' if c.a('grand_livre', 'date_saisie') else 'date'
    res = []
    for r in _par_ecriture(df.dropna(subset=[champ])):
        t = r[champ]
        d = t.date()
        quoi = 'Saisie' if champ == 'date_saisie' else 'Écriture datée'
        if d.weekday() >= 5:
            res.append(c.anomalie('grand_livre', r, f'{quoi} un {("samedi", "dimanche")[d.weekday() - 5]} ({t.strftime("%d/%m/%Y %H:%M" if avec_heure else "%d/%m/%Y")})'))
        elif (d.month, d.day) in fixes or d in dates:
            res.append(c.anomalie('grand_livre', r, f'{quoi} un jour férié ({d.strftime("%d/%m/%Y")})'))
        elif avec_heure and (t.hour >= h1 or t.hour < h2):
            res.append(c.anomalie('grand_livre', r, f'Saisie à {t.strftime("%H:%M")} le {d.strftime("%d/%m/%Y")}, hors des heures de travail'))
    return res, df['_ecr'].nunique()


def t_gl_apres_cloture(c, p):
    cl = _cl(c)
    if cl is None:
        return None, SANS_CLOTURE
    df = _gl(c).dropna(subset=['date', 'date_saisie'])
    limite = cl + pd.Timedelta(days=int(p['jours']) + 1)
    res = []
    for r in _par_ecriture(df[(df['date'] <= cl) & (df['date_saisie'] >= limite)]):
        res.append(c.anomalie('grand_livre', r, f'Datée du {r["date"].strftime("%d/%m/%Y")} mais saisie le {r["date_saisie"].strftime("%d/%m/%Y")}, '
                              f'{(r["date_saisie"] - cl).days} jours après la clôture'))
    return res, df['_ecr'].nunique()


def t_gl_sensibles(c, p):
    df = _gl(c)
    journaux = {norm_id(j) for j in _liste(p['journaux'])}
    prefixes = [re.sub(r'\D', '', x) for x in _liste(p['comptes'].replace(' ', ',')) if re.sub(r'\D', '', x)]
    mini = float(p['montant_min'])
    df = df[df['journal'].fillna('').astype(str).map(norm_id).isin(journaux) & (df['_mt'] >= mini)]
    res = []
    for r in _lignes(df):
        if any(r['_cpt'].startswith(x) for x in prefixes):
            res.append(c.anomalie('grand_livre', r, f'Écriture manuelle (journal {r.get("journal")}) sur le compte sensible {r["compte"]}'))
    return res, len(c.d['grand_livre'])


def t_gl_attente(c, p):
    df = _gl(c).dropna(subset=['date'])
    prefixes = [re.sub(r'\D', '', x) for x in _liste(p['comptes'].replace(' ', ',')) if re.sub(r'\D', '', x)]
    df = df[df['_cpt'].map(lambda v: any(v.startswith(x) for x in prefixes))]
    ref = _cl(c) or (df['date'].max() if len(df) else None)
    lettre = c.a('grand_livre', 'lettrage')
    res = []
    for cpt, grp in df.groupby('_cpt'):
        solde = float(grp['debit'].fillna(0).sum() - grp['credit'].fillna(0).sum())
        if abs(solde) <= float(p['montant_min']):
            continue
        ouvertes = grp[grp['lettrage'].fillna('').astype(str).str.strip() == ''] if lettre else grp
        vieille = _lignes((ouvertes if len(ouvertes) else grp).sort_values('date').head(1))[0]
        age = (ref - vieille['date']).days if ref is not None else 0
        a = c.anomalie('grand_livre', vieille, f'Solde {"débiteur" if solde > 0 else "créditeur"} de {_fr(abs(solde), c.devise)} ; '
                       f'plus ancienne écriture {"non lettrée " if lettre else ""}du {vieille["date"].strftime("%d/%m/%Y")} ({age} jours)')
        a['montant'], a['ref'] = abs(solde), str(vieille['compte'])
        res.append(a)
    return res, int(df['_cpt'].nunique())


def t_gl_utilisateurs(c, p):
    df = _gl(c)
    habilites = {norm_nom(x) for x in _liste(p['habilites'])}
    res = []
    for r in _par_ecriture(df):
        qui = norm_nom(r.get('saisi_par') or '')
        if not qui:
            continue
        if qui in COMPTES_GENERIQUES:
            res.append(c.anomalie('grand_livre', r, f'Saisie avec le compte générique « {r["saisi_par"]} » (personne non identifiable)'))
        elif habilites and qui not in habilites:
            res.append(c.anomalie('grand_livre', r, f'Saisie par {r["saisi_par"]}, absent de la liste des personnes habilitées'))
    return res, df['_ecr'].nunique()


def t_gl_ronds(c, p):
    df = _gl(c)
    base, mini = float(p['multiple']), float(p['montant_min'])
    df = df[(df['_mt'] >= mini) & ((df['_mt'] % base).abs() < 0.005)]
    return [c.anomalie('grand_livre', r, f'Montant rond (multiple de {_fr(base, c.devise)}) sur le compte {r["compte"]}') for r in _lignes(df)], len(c.d['grand_livre'])


def t_gl_benford(c, p):
    return _benford(c, p, 'grand_livre', '_mt')


def t_gl_extournes(c, p):
    cl = _cl(c)
    if cl is None:
        return None, SANS_CLOTURE
    df = _gl(c).dropna(subset=['date'])
    df = df[df['_mt'] >= float(p['montant_min'])]
    avant = df[(df['date'] > cl - pd.Timedelta(days=int(p['jours_avant']))) & (df['date'] <= cl)]
    apres = df[(df['date'] > cl) & (df['date'] <= cl + pd.Timedelta(days=int(p['jours_apres'])))]
    index = {}
    for r in _lignes(apres):
        index.setdefault((r['_cpt'], round(r['_mt'], 2), (r['debit'] or 0) > 0 if not pd.isna(r['debit']) else False), []).append(r)
    res, g, pris = [], 0, set()
    for r in _lignes(avant):
        sens = (r['debit'] or 0) > 0 if not pd.isna(r['debit']) else False
        for x in index.get((r['_cpt'], round(r['_mt'], 2), not sens), []):
            if x['_ecr'] in pris:
                continue
            pris.add(x['_ecr'])
            g += 1
            res.append(c.anomalie('grand_livre', r, f'Passée le {r["date"].strftime("%d/%m/%Y")}, juste avant la clôture, et contre-passée '
                                  f'le {x["date"].strftime("%d/%m/%Y")} (écriture {x["numero"]})', g))
            res.append(c.anomalie('grand_livre', x, f'Contre-passe l’écriture {r["numero"]} du {r["date"].strftime("%d/%m/%Y")}', g))
            break
    return res, len(avant)


# ====================================================================== lot 2 : ventes et encaissements
def _ventes(c):
    v = c.d['ventes']
    return v[~v['_avoir']], v[v['_avoir']]


def t_vte_numerotation(c, p):
    fa, _av = _ventes(c)
    res, g = [], 0
    nn = fa['numero'].fillna('').astype(str).map(norm_id)
    for _k, grp in fa.assign(_n=nn)[nn != ''].groupby('_n'):
        if len(grp) > 1:
            g += 1
            for r in _lignes(grp):
                res.append(c.anomalie('ventes', r, f'Numéro de facture attribué {len(grp)} fois', g))
    series = {}
    for r in _lignes(fa):
        m = re.match(r'^(.*?)(\d+)\s*$', str(r['numero'] or ''))
        if m:
            series.setdefault(m.group(1).strip().upper(), {}).setdefault(int(m.group(2)), r)
    for _pref, nums in series.items():
        if len(nums) < 5:
            continue
        cles = sorted(nums)
        for a, b in zip(cles, cles[1:]):
            if 1 < b - a <= int(p['trou_max']) + 1:
                manq = b - a - 1
                res.append(c.anomalie('ventes', nums[b], f'{manq} numéro(s) manquant(s) avant cette facture (après {nums[a]["numero"]})'
                                      + ('' if manq > 3 else ' : ' + ', '.join(str(x) for x in range(a + 1, b)))))
    return res, len(fa)


def t_vte_avoirs_cloture(c, p):
    cl = _cl(c)
    if cl is None:
        return None, SANS_CLOTURE
    fa, av = _ventes(c)
    dates = {norm_id(r['numero']): r for r in _lignes(fa.dropna(subset=['date']))}
    av = av.dropna(subset=['date'])
    av = av[(av['date'] > cl) & (av['date'] <= cl + pd.Timedelta(days=int(p['jours'])))]
    res = []
    for r in _lignes(av):
        o = dates.get(norm_id(r.get('facture_origine', '') or ''))
        if o is not None and o['date'] <= cl:
            res.append(c.anomalie('ventes', r, f'Avoir du {r["date"].strftime("%d/%m/%Y")} annulant la facture {o["numero"]} du '
                                  f'{o["date"].strftime("%d/%m/%Y")} (période close)'))
        elif o is None:
            res.append(c.anomalie('ventes', r, f'Avoir du {r["date"].strftime("%d/%m/%Y")}, après la clôture, sans facture d’origine identifiée'))
    return res, len(av)


def t_vte_avoir_origine(c, p):
    fa, av = _ventes(c)
    montants = {}
    for r in _lignes(fa):
        k = norm_id(r['numero'])
        if k and _f(r['montant']) is not None:
            montants[k] = montants.get(k, 0) + abs(r['montant'])
    res, cumul, g = [], {}, 0
    for r in _lignes(av):
        k = norm_id(r.get('facture_origine', '') or '')
        if not k:
            res.append(c.anomalie('ventes', r, 'Avoir sans facture d’origine'))
        elif k not in montants:
            res.append(c.anomalie('ventes', r, f'Facture d’origine {r["facture_origine"]} introuvable'))
        else:
            cumul.setdefault(k, []).append(r)
    for k, lst in cumul.items():
        total = sum(abs(_f(x['montant']) or 0) for x in lst)
        if total > montants[k] * 1.005 + 0.5:
            g += 1
            for x in lst:
                res.append(c.anomalie('ventes', x, f'Avoirs cumulés ({_fr(total, c.devise)}) supérieurs à la facture {x["facture_origine"]} '
                                      f'({_fr(montants[k], c.devise)})', g))
    return res, len(av)


def t_vte_remises(c, p):
    fa, _av = _ventes(c)
    rem = fa['remise_pct']
    facteur = 100 if rem.dropna().max() <= 1 and (rem.dropna() > 0).any() else 1
    seuil = float(p['seuil'])
    res = []
    for r, x in zip(_lignes(fa), rem * facteur):
        if not pd.isna(x) and x > seuil:
            res.append(c.anomalie('ventes', r, f'Remise de {round(x, 1)} %, au-delà de la politique commerciale ({seuil:g} %)'))
    return res, len(fa)


def t_vte_client_bloque(c, p):
    cl = c.d['clients']
    connus = set(cl['code'].map(norm_id)) - {''}
    bloques = set()
    if c.a('clients', 'statut'):
        for r in _lignes(cl):
            if re.search(r'bloqu|inactif|ferm|suspendu|content|litig|douteu|blocked|inactive', sans_accents(r.get('statut', '')).lower()):
                bloques.add(norm_id(r['code']))
    fa, _av = _ventes(c)
    res = []
    for r in _lignes(fa):
        k = norm_id(r['client'])
        if not k:
            continue
        if k not in connus:
            res.append(c.anomalie('ventes', r, 'Client absent du fichier des clients'))
        elif k in bloques:
            res.append(c.anomalie('ventes', r, 'Vente à un client bloqué, inactif ou en contentieux'))
    return res, len(fa)


def t_vte_credit(c, p):
    cl, enc = c.d['clients'], c.d['encaissements']
    v = c.d['ventes']
    du = {}
    for r in _lignes(v):
        k = norm_id(r['client'])
        mt = abs(_f(r['montant']) or 0)
        du[k] = du.get(k, 0) + (-mt if r['_avoir'] else mt)
    for r in _lignes(enc):
        k = norm_id(r['client'])
        du[k] = du.get(k, 0) - (_f(r['montant']) or 0)
    res = []
    for r in _lignes(cl):
        lim = _f(r.get('limite_credit'))
        k = norm_id(r['code'])
        if lim and lim > 0 and du.get(k, 0) > lim:
            a = c.anomalie('clients', r, f'Encours de {_fr(du[k], c.devise)} pour une limite de {_fr(lim, c.devise)} '
                           f'(dépassement de {_fr(du[k] - lim, c.devise)})')
            a['montant'] = du[k] - lim
            res.append(a)
    return res, int((cl['limite_credit'].fillna(0) > 0).sum())


def t_vte_cut_off(c, p):
    cl = _cl(c)
    if cl is None:
        return None, SANS_CLOTURE
    fa, av = _ventes(c)
    fa = fa.dropna(subset=['date'])
    av = av.dropna(subset=['date'])
    fin = fa[(fa['date'] > cl - pd.Timedelta(days=int(p['jours_avant']))) & (fa['date'] <= cl)]
    debut = av[(av['date'] > cl) & (av['date'] <= cl + pd.Timedelta(days=int(p['jours_apres'])))]
    par_origine = {norm_id(r.get('facture_origine') or ''): r for r in _lignes(debut) if r.get('facture_origine')}
    par_montant = {}
    for r in _lignes(debut):
        par_montant.setdefault((norm_id(r['client']), round(abs(r['montant']), 2)), []).append(r)
    res, g, pris = [], 0, set()
    for r in _lignes(fin):
        x = par_origine.get(norm_id(r['numero']))
        if x is None:
            cand = [y for y in par_montant.get((norm_id(r['client']), round(abs(r['montant']), 2)), []) if y['_ligne'] not in pris]
            x = cand[0] if cand else None
        if x is None or x['_ligne'] in pris:
            continue
        pris.add(x['_ligne'])
        g += 1
        res.append(c.anomalie('ventes', r, f'Facturée le {r["date"].strftime("%d/%m/%Y")}, juste avant la clôture, puis annulée par '
                              f'l’avoir {x["numero"]} du {x["date"].strftime("%d/%m/%Y")}', g))
        res.append(c.anomalie('ventes', x, f'Avoir annulant la facture {r["numero"]} de fin de période', g))
    return res, len(fin)


def t_enc_non_lettres(c, p):
    enc, v = c.d['encaissements'], c.d['ventes']
    fa = v[~v['_avoir']]
    montants = {}
    for r in _lignes(fa):
        k = norm_id(r['numero'])
        if k:
            montants[k] = montants.get(k, 0) + abs(_f(r['montant']) or 0)
    res, cumul, g = [], {}, 0
    for r in _lignes(enc):
        k = norm_id(r.get('facture', '') or '')
        if not k:
            res.append(c.anomalie('encaissements', r, 'Encaissement non rattaché à une facture'))
        elif k not in montants:
            res.append(c.anomalie('encaissements', r, f'Facture {r["facture"]} introuvable dans les ventes'))
        else:
            cumul.setdefault(k, []).append(r)
    for k, lst in cumul.items():
        total = sum(_f(x['montant']) or 0 for x in lst)
        if total > montants[k] * 1.005 + 0.5:
            g += 1
            for x in lst:
                res.append(c.anomalie('encaissements', x, f'Encaissé {_fr(total, c.devise)} pour la facture {x["facture"]} de '
                                      f'{_fr(montants[k], c.devise)}', g))
    return res, len(enc)


COMPTES_SENSIBLES = '47, 52, 57, 58, 46'
TESTS += [
    dict(code='GL_DESEQUILIBRE', titre='Écritures déséquilibrées', domaine='Comptabilité', f=t_gl_desequilibre,
         requis=[('grand_livre', ('numero', 'debit', 'credit'))], params=[('tolerance', 'Tolérance d’arrondi', 1, '')], niveau='eleve',
         description='Écritures dont le total des débits diffère du total des crédits.',
         critere='Toute écriture est équilibrée (principe de la partie double, SYSCOHADA).',
         consequence='Comptes faux, balance non équilibrée, états financiers non fiables.',
         recommandation='Corriger les écritures relevées et bloquer la validation d’une écriture déséquilibrée dans le logiciel.'),
    dict(code='GL_DOUBLON', titre='Écritures en double', domaine='Comptabilité', f=t_gl_doublon,
         requis=[('grand_livre', ('compte', 'date'))], params=[], niveau='moyen',
         description='Même compte, même date, même montant, même sens et même libellé, dans des écritures différentes.',
         critere='Chaque opération n’est comptabilisée qu’une fois.',
         consequence='Charges ou produits comptés deux fois ; paiement possible en double.',
         recommandation='Contrepasser les doublons confirmés et contrôler l’unicité des pièces à la saisie.'),
    dict(code='GL_SANS_PIECE', titre='Écritures sans pièce ou sans libellé', domaine='Comptabilité', f=t_gl_sans_piece,
         requis=[('grand_livre', ('piece|libelle',))], params=[('montant_min', 'Montant minimal analysé', 0, '')], niveau='moyen',
         description='Écritures sans référence de pièce justificative, sans libellé ou avec un libellé non explicite (« divers », « régul »…).',
         critere='Toute écriture comptable est appuyée par une pièce justificative datée et référencée (Acte uniforme OHADA relatif au droit comptable).',
         consequence='Écritures non justifiables, risque de manipulation des comptes.',
         recommandation='Obtenir les justificatifs des écritures relevées ; rendre la référence de pièce obligatoire.'),
    dict(code='GL_HORS_HEURES', titre='Saisies la nuit, le week-end ou un jour férié', domaine='Comptabilité', f=t_gl_hors_heures,
         requis=[('grand_livre', ('date',))],
         params=[('heure_debut', 'Début de la nuit (heure)', 20, ''), ('heure_fin', 'Fin de la nuit (heure)', 6, ''),
                 ('feries', 'Jours fériés (jj/mm ou jj/mm/aaaa)', FERIES_CI, '')], niveau='faible',
         description='Écritures saisies la nuit, un week-end ou un jour férié (date et heure de saisie ; à défaut, date de l’écriture).',
         critere='Les écritures sont saisies pendant les heures de travail, sous supervision.',
         consequence='Écritures passées hors contrôle, risque de manipulation.',
         recommandation='Justifier les saisies relevées et restreindre l’accès au logiciel hors des heures ouvrées.'),
    dict(code='GL_APRES_CLOTURE', titre='Écritures passées après la clôture', domaine='Comptabilité', f=t_gl_apres_cloture,
         requis=[('grand_livre', ('date', 'date_saisie'))],
         params=[('jours', 'Délai normal après la clôture (jours)', 30, 'Écritures d’inventaire attendues dans ce délai')], niveau='eleve',
         description='Écritures datées de la période close mais saisies bien après la clôture.',
         critere='Les écritures d’une période sont passées avant l’arrêté des comptes ; au-delà, elles sont autorisées et documentées.',
         consequence='Résultat modifié après la clôture (gestion du résultat).',
         recommandation='Verrouiller les périodes clôturées et soumettre toute écriture tardive à l’approbation de la direction financière.'),
    dict(code='GL_SENSIBLES', titre='Écritures manuelles sur comptes sensibles', domaine='Comptabilité', f=t_gl_sensibles,
         requis=[('grand_livre', ('journal', 'compte'))],
         params=[('journaux', 'Journaux manuels (codes)', 'OD, ODS, REG, DIV', 'Opérations diverses, régularisations'),
                 ('comptes', 'Comptes sensibles (début du numéro)', COMPTES_SENSIBLES, 'SYSCOHADA : 46 associés, 47 attente, 52 banques, 57 caisse, 58 virements internes'),
                 ('montant_min', 'À partir de', 1_000_000, '')], niveau='eleve',
         description='Écritures d’opérations diverses passées directement sur la trésorerie, les comptes d’attente ou les comptes d’associés.',
         critere='Les mouvements de trésorerie passent par les journaux de banque et de caisse ; les écritures manuelles sont autorisées.',
         consequence='Détournement masqué par une écriture manuelle.',
         recommandation='Revoir chaque écriture relevée avec sa pièce et son autorisation.'),
    dict(code='GL_ATTENTE', titre='Comptes d’attente non soldés', domaine='Comptabilité', f=t_gl_attente,
         requis=[('grand_livre', ('compte',))],
         params=[('comptes', 'Comptes d’attente (début du numéro)', '47', 'SYSCOHADA : 471 à 476'), ('montant_min', 'Solde minimal', 0, '')],
         niveau='moyen',
         description='Comptes d’attente ou transitoires dont le solde n’est pas nul en fin de période, avec l’âge de la plus ancienne écriture.',
         critere='Les comptes d’attente sont apurés régulièrement et soldés à la clôture.',
         consequence='Opérations non identifiées ; risque d’erreur ou de dissimulation.',
         recommandation='Analyser et apurer les soldes relevés ; suivre mensuellement les comptes d’attente.'),
    dict(code='GL_UTILISATEURS', titre='Écritures saisies par des personnes non habilitées', domaine='Comptabilité', f=t_gl_utilisateurs,
         requis=[('grand_livre', ('saisi_par',))],
         params=[('habilites', 'Personnes habilitées (une par ligne)', '', 'Laissez vide pour ne repérer que les comptes génériques (admin…)')],
         niveau='moyen',
         description='Écritures saisies avec un compte générique (admin, système…) ou par une personne absente de la liste des habilitations.',
         critere='Seules les personnes habilitées saisissent des écritures, avec un identifiant personnel.',
         consequence='Saisies non traçables, séparation des tâches non respectée.',
         recommandation='Supprimer les comptes génériques et revoir les droits du logiciel comptable.'),
    dict(code='GL_RONDS', titre='Montants ronds en comptabilité', domaine='Comptabilité', f=t_gl_ronds, requis=[('grand_livre', ('debit',))],
         params=[('multiple', 'Multiple de', 1_000_000, ''), ('montant_min', 'À partir de', 5_000_000, '')], niveau='faible',
         description='Écritures d’un montant élevé et parfaitement rond (estimations, provisions, ajustements).',
         critere='Les écritures d’estimation sont documentées et approuvées.',
         consequence='Estimations non justifiées pouvant modifier le résultat.',
         recommandation='Obtenir la justification des écritures relevées.'),
    dict(code='GL_BENFORD', titre='Loi de Benford sur les écritures', domaine='Comptabilité', f=t_gl_benford, requis=[('grand_livre', ('debit',))],
         params=[('minimum', 'Nombre minimal de montants', 1000, '')], niveau='faible',
         description='Répartition des premiers chiffres des montants d’écritures comparée à la loi de Benford.',
         critere='Dans une population naturelle de montants, la répartition des premiers chiffres suit la loi de Benford.',
         consequence='Indice de montants fabriqués ou ajustés (à confirmer par des tests détaillés).',
         recommandation='Examiner les écritures des chiffres sur-représentés.'),
    dict(code='GL_EXTOURNES', titre='Écritures de fin de période contre-passées', domaine='Comptabilité', f=t_gl_extournes,
         requis=[('grand_livre', ('compte', 'date'))],
         params=[('jours_avant', 'Jours avant la clôture', 15, ''), ('jours_apres', 'Jours après la clôture', 45, ''),
                 ('montant_min', 'À partir de', 1_000_000, '')], niveau='eleve',
         description='Écriture importante passée juste avant la clôture puis contre-passée (même compte, même montant, sens inverse) juste après.',
         critere='Les écritures de clôture reflètent des opérations réelles de la période.',
         consequence='Résultat de la période embelli puis corrigé discrètement (gestion du résultat).',
         recommandation='Justifier chaque couple relevé et faire approuver les écritures d’inventaire par la direction financière.'),
    dict(code='VTE_NUMEROTATION', titre='Numérotation des factures de vente', domaine='Ventes et encaissements', f=t_vte_numerotation,
         requis=[('ventes', ('numero',))], params=[('trou_max', 'Ignorer les sauts de plus de (numéros)', 50, 'Changement de série')], niveau='eleve',
         description='Numéros de facture manquants dans une série, ou attribués plusieurs fois.',
         critere='Les factures sont numérotées de façon continue et chronologique, sans trou ni doublon.',
         consequence='Factures supprimées ou ventes non comptabilisées (chiffre d’affaires dissimulé).',
         recommandation='Justifier chaque numéro manquant (facture annulée et conservée) ; bloquer la suppression de factures.'),
    dict(code='VTE_AVOIRS_CLOTURE', titre='Avoirs après la clôture', domaine='Ventes et encaissements', f=t_vte_avoirs_cloture,
         requis=[('ventes', ('date',))], params=[('jours', 'Jours après la clôture', 60, '')], niveau='eleve',
         description='Avoirs émis après la clôture qui annulent des factures de la période close.',
         critere='Le chiffre d’affaires d’une période ne comprend que des ventes réelles ; les annulations sont rattachées à la bonne période.',
         consequence='Chiffre d’affaires surévalué à la clôture.',
         recommandation='Analyser les avoirs relevés et provisionner les annulations connues à la clôture.'),
    dict(code='VTE_AVOIR_ORIGINE', titre='Avoirs sans facture d’origine ou excessifs', domaine='Ventes et encaissements', f=t_vte_avoir_origine,
         requis=[('ventes', ('facture_origine',))], params=[], niveau='moyen',
         description='Avoirs sans facture d’origine, avec une facture introuvable, ou dont le cumul dépasse la facture.',
         critere='Tout avoir est rattaché à une facture et approuvé ; il n’en dépasse pas le montant.',
         consequence='Avoirs fictifs servant à détourner des encaissements ou à réduire le chiffre d’affaires.',
         recommandation='Rendre obligatoire la facture d’origine et l’approbation des avoirs.'),
    dict(code='VTE_REMISES', titre='Remises hors politique commerciale', domaine='Ventes et encaissements', f=t_vte_remises,
         requis=[('ventes', ('remise_pct',))], params=[('seuil', 'Remise maximale autorisée (%)', 10, '')], niveau='moyen',
         description='Factures avec une remise supérieure au taux autorisé.',
         critere='Les remises respectent la politique commerciale ; au-delà, elles sont approuvées.',
         consequence='Perte de marge, complaisance envers certains clients.',
         recommandation='Paramétrer le taux maximal dans le logiciel et faire approuver les dépassements.'),
    dict(code='VTE_CLIENT_BLOQUE', titre='Ventes à des clients bloqués ou inconnus', domaine='Ventes et encaissements', f=t_vte_client_bloque,
         requis=[('ventes', ('client',)), ('clients', ('code',))], params=[], niveau='moyen',
         description='Factures à un client absent du fichier des clients, ou bloqué, inactif, en contentieux.',
         critere='Seuls les clients référencés et actifs peuvent être facturés à crédit.',
         consequence='Créances irrécouvrables, clients fictifs.',
         recommandation='Bloquer la facturation des clients non actifs et analyser les ventes relevées.'),
    dict(code='VTE_CREDIT', titre='Dépassement de la limite de crédit', domaine='Ventes et encaissements', f=t_vte_credit,
         requis=[('ventes', ('client', 'montant')), ('clients', ('limite_credit',)), ('encaissements', ('client', 'montant'))], params=[], niveau='moyen',
         description='Clients dont l’encours (ventes − avoirs − encaissements de la période) dépasse la limite de crédit.',
         critere='L’encours de chaque client reste dans la limite de crédit accordée.',
         consequence='Risque d’impayés et de créances douteuses.',
         recommandation='Bloquer les livraisons au-delà de la limite et relancer les clients relevés.'),
    dict(code='VTE_CUT_OFF', titre='Ventes de fin de période annulées après la clôture', domaine='Ventes et encaissements', f=t_vte_cut_off,
         requis=[('ventes', ('date', 'client'))], params=[('jours_avant', 'Jours avant la clôture', 10, ''), ('jours_apres', 'Jours après la clôture', 45, '')],
         niveau='eleve',
         description='Facture émise juste avant la clôture puis annulée par un avoir juste après (même facture, ou même client et même montant).',
         critere='Le chiffre d’affaires est rattaché à la période de la livraison effective (séparation des exercices).',
         consequence='Chiffre d’affaires gonflé artificiellement à la clôture.',
         recommandation='Vérifier les bons de livraison des factures relevées et corriger le chiffre d’affaires.'),
    dict(code='ENC_NON_LETTRES', titre='Encaissements non rattachés', domaine='Ventes et encaissements', f=t_enc_non_lettres,
         requis=[('encaissements', ('facture',)), ('ventes', ('numero',))], params=[], niveau='moyen',
         description='Encaissements sans facture, avec une facture introuvable, ou supérieurs à la facture.',
         critere='Chaque encaissement est rattaché (lettré) à la facture qu’il règle.',
         consequence='Créances clients fausses ; risque de détournement d’encaissements (« lapping »).',
         recommandation='Lettrer les encaissements relevés et contrôler mensuellement la balance âgée des clients.'),
]
DOMAINES += ['Comptabilité', 'Ventes et encaissements']


# ====================================================================== lot 4 : paie, habilitations, crédit, LCB-FT, statistique
INACTIF = r'inactif|desactiv|bloqu|suspendu|supprim|ferm|disabled|inactive|locked|expire|non'
GENERIQUES_SI = {'admin', 'administrateur', 'administrator', 'root', 'sa', 'system', 'systeme', 'test', 'tests', 'demo', 'invite', 'guest', 'stagiaire',
                 'temp', 'temporaire', 'user', 'utilisateur', 'support', 'maintenance', 'batch', 'interface', 'operateur', 'caisse', 'guichet'}


def _ref_date(c):
    return pd.Timestamp(c.cloture) if c.cloture else pd.Timestamp(date.today())


def _mois(d):
    return (d.year, d.month)


def _actif(statut):
    return not re.search(INACTIF, sans_accents(statut or '').lower())


def t_paie_apres_sortie(c, p):
    sorties = {norm_id(r['matricule']): r['date_sortie'] for r in _lignes(c.d['salaries'].dropna(subset=['date_sortie'])) if norm_id(r['matricule'])}
    res = []
    for r in _lignes(c.d['paie'].dropna(subset=['periode'])):
        ds = sorties.get(norm_id(r['matricule']))
        if ds is not None and _mois(r['periode']) > _mois(ds):
            res.append(c.anomalie('paie', r, f'Salaire de {r["periode"].strftime("%m/%Y")} versé après le départ du {ds.strftime("%d/%m/%Y")}'))
    return res, len(c.d['paie'])


def t_paie_inconnu(c, p):
    connus = set(c.d['salaries']['matricule'].map(norm_id)) - {''}
    res = [c.anomalie('paie', r, 'Matricule absent du fichier du personnel (salarié fictif ?)') for r in _lignes(c.d['paie'])
           if norm_id(r['matricule']) and norm_id(r['matricule']) not in connus]
    return res, len(c.d['paie'])


def t_paie_double(c, p):
    df = c.d['paie'].dropna(subset=['periode'])
    df = df.assign(_m=df['matricule'].map(norm_id), _p=df['periode'].dt.strftime('%Y-%m'))
    res, g = [], 0
    for (_m, per), grp in df[df['_m'] != ''].groupby(['_m', '_p']):
        if len(grp) > 1:
            g += 1
            for r in _lignes(grp):
                res.append(c.anomalie('paie', r, f'{len(grp)} salaires versés pour {per[5:]}/{per[:4]}', g))
    return res, len(df)


def t_paie_rib_partage(c, p):
    sa = c.d['salaries']
    sa = sa.assign(_r=sa['rib'].map(norm_rib), _m=sa['matricule'].map(norm_id))
    sa = sa[sa['_r'].str.len() >= 10]
    res, g = [], 0
    for _r, grp in sa.groupby('_r'):
        if grp['_m'].nunique() > 1:
            g += 1
            noms = ', '.join(f'{x["matricule"]} {x["nom"]}' for x in _lignes(grp))
            for r in _lignes(grp):
                a = c.anomalie('salaries', r, f'Même compte bancaire pour {grp["_m"].nunique()} salariés : {noms}', g)
                res.append(a)
    return res, len(c.d['salaries'])


def t_paie_variation(c, p):
    df = c.d['paie'].dropna(subset=['periode', 'montant'])
    df = df.assign(_m=df['matricule'].map(norm_id))
    ecart = float(p['ecart_pct']) / 100
    res = []
    for _m, grp in df.groupby('_m'):
        if len(grp) < 3:
            continue
        med = float(grp['montant'].median())
        for r in _lignes(grp[grp['montant'] > med * (1 + ecart)]):
            res.append(c.anomalie('paie', r, f'Net de {r["periode"].strftime("%m/%Y")} : {_fr(r["montant"], c.devise)}, '
                                  f'{round((r["montant"] / med - 1) * 100)} % au-dessus du net habituel ({_fr(med, c.devise)})'))
    return res, len(df)


def t_paie_heures_sup(c, p):
    seuil = float(p['seuil'])
    df = c.d['paie'].dropna(subset=['heures_sup'])
    return [c.anomalie('paie', r, f'{r["heures_sup"]:g} heures supplémentaires sur le mois (au-delà de {seuil:g})')
            for r in _lignes(df[df['heures_sup'] > seuil])], len(df)


def _comptes_actifs(c):
    df = c.d['utilisateurs_si']
    return df[df['statut'].fillna('').astype(str).map(_actif)]


def t_si_departs(c, p):
    sa = c.d['salaries'].dropna(subset=['date_sortie'])
    ref = _ref_date(c)
    sa = sa[sa['date_sortie'] <= ref]
    par_mat = {norm_id(r['matricule']): r for r in _lignes(sa)}
    par_nom = {norm_nom(r['nom']): r for r in _lignes(sa)}
    res = []
    for r in _lignes(_comptes_actifs(c)):
        s = par_mat.get(norm_id(r.get('matricule') or '')) if r.get('matricule') else None
        s = s or par_nom.get(norm_nom(r['nom']))
        if s is None:
            continue
        apres = r.get('derniere_connexion')
        utilise = apres is not None and not pd.isna(apres) and apres > s['date_sortie']
        res.append(c.anomalie('utilisateurs_si', r, f'Compte actif alors que {s["nom"]} a quitté l’entreprise le {s["date_sortie"].strftime("%d/%m/%Y")}'
                              + (f' ; utilisé après le départ (dernière connexion le {apres.strftime("%d/%m/%Y")})' if utilise else '')))
    return res, len(c.d['utilisateurs_si'])


def t_si_generiques(c, p):
    res = []
    for r in _lignes(_comptes_actifs(c)):
        mots = set(re.split(r'[^a-z0-9]+', norm_nom(r['identifiant']) + ' ' + norm_nom(r['nom']))) - {''}
        ident = re.sub(r'\d+$', '', norm_nom(r['identifiant']).replace(' ', ''))
        if ident in GENERIQUES_SI or mots & {'test', 'admin', 'invite', 'guest', 'stagiaire', 'temporaire', 'generique'}:
            res.append(c.anomalie('utilisateurs_si', r, f'Compte générique ou partagé actif (« {r["identifiant"]} ») : actions non attribuables à une personne'))
    return res, len(c.d['utilisateurs_si'])


def t_si_inactifs(c, p):
    ref, jours = _ref_date(c), int(p['jours'])
    res = []
    for r in _lignes(_comptes_actifs(c)):
        d = r.get('derniere_connexion')
        if d is None or pd.isna(d):
            cree = r.get('date_creation')
            if cree is not None and not pd.isna(cree) and (ref - cree).days > jours:
                res.append(c.anomalie('utilisateurs_si', r, f'Compte actif jamais utilisé, créé le {cree.strftime("%d/%m/%Y")}'))
        elif (ref - d).days > jours:
            res.append(c.anomalie('utilisateurs_si', r, f'Compte actif sans connexion depuis {(ref - d).days} jours'))
    return res, len(c.d['utilisateurs_si'])


def _paires(texte_liste):
    res = []
    for l in (texte_liste or '').splitlines():
        if '+' in l:
            a, b = [norm_nom(x) for x in l.split('+', 1)]
            if a and b:
                res.append((a, b, l.strip()))
    return res


def t_si_incompatibles(c, p):
    paires = _paires(p['incompatibilites'])
    if not paires:
        return None, 'Indiquez au moins une incompatibilité (« rôle A + rôle B »).'
    res = []
    for r in _lignes(_comptes_actifs(c)):
        roles = [norm_nom(x) for x in re.split(r'[;,|/\n]+', str(r.get('roles') or '')) if x.strip()]
        for a, b, lib in paires:
            ra = [x for x in roles if a in x]
            rb = [x for x in roles if b in x and x not in ra]
            if ra and rb:
                res.append(c.anomalie('utilisateurs_si', r, f'Cumul de rôles incompatibles : {lib}'))
                break
    return res, len(c.d['utilisateurs_si'])


def t_crd_delegation(c, p):
    plafonds, seuil = _plafonds(p['plafonds']), float(p['seuil'])
    res = []
    for r in _lignes(c.d['credits']):
        mt = _f(r['montant'])
        if mt is None:
            continue
        qui = norm_nom(r.get('accorde_par') or '')
        if not qui:
            if mt >= seuil:
                res.append(c.anomalie('credits', r, f'Aucun décideur renseigné pour un crédit de plus de {_fr(seuil, c.devise)}'))
        elif qui in plafonds and mt > plafonds[qui]:
            res.append(c.anomalie('credits', r, f'Accordé par {r["accorde_par"]} au-delà de sa délégation ({_fr(plafonds[qui], c.devise)})'))
        elif plafonds and qui not in plafonds and mt >= seuil:
            res.append(c.anomalie('credits', r, f'Accordé par {r["accorde_par"]}, absent de la liste des délégations'))
    return res, len(c.d['credits'])


def t_crd_fractionnement(c, p):
    seuil, jours = float(p['seuil']), int(p['jours'])
    df = c.d['credits'].dropna(subset=['date'])
    df = df[(df['montant'] > 0) & (df['montant'] < seuil) & (df['montant'] >= seuil * float(p['part_min_pct']) / 100)]
    res, g = [], 0
    for _k, grp in df.assign(_c=df['client'].map(norm_id)).groupby('_c'):
        recs = _lignes(grp.sort_values('date'))
        i = 0
        while i < len(recs):
            j = i
            while j + 1 < len(recs) and (recs[j + 1]['date'] - recs[i]['date']).days <= jours:
                j += 1
            bloc = recs[i:j + 1]
            total = sum(_f(x['montant']) or 0 for x in bloc)
            if len(bloc) > 1 and total >= seuil:
                g += 1
                for x in bloc:
                    res.append(c.anomalie('credits', x, f'{len(bloc)} crédits au même client en {jours} jours, chacun sous {_fr(seuil, c.devise)}, '
                                          f'total {_fr(total, c.devise)}', g))
                i = j + 1
            else:
                i += 1
    return res, len(c.d['credits'])


def t_crd_parties_liees(c, p):
    noms_sal = {norm_nom(r['nom']): r for r in _lignes(c.d['salaries']) if norm_nom(r['nom'])}
    mats = {norm_id(r['matricule']): r for r in _lignes(c.d['salaries']) if norm_id(r['matricule'])}
    res = []
    for r in _lignes(c.d['credits']):
        nom = c.noms_clients.get(norm_id(r['client']), '')
        s = noms_sal.get(norm_nom(nom)) or mats.get(norm_id(r['client']))
        if s is not None:
            res.append(c.anomalie('credits', r, f'Crédit à un membre du personnel ({s["matricule"]} — {s["nom"]}) : conditions et approbation à vérifier'))
    return res, len(c.d['credits'])


def t_crd_souffrance(c, p):
    seuil = int(p['jours'])
    res = []
    for r in _lignes(c.d['credits'].dropna(subset=['jours_retard'])):
        if r['jours_retard'] > seuil and not re.search(r'douteu|litigi|contentieu|compromis|souffrance|deprecie|default|perte|irrecouvr',
                                                         sans_accents(r.get('classement') or '').lower()):
            a = c.anomalie('credits', r, f'{int(r["jours_retard"])} jours de retard, classé « {r.get("classement") or "non renseigné"} » '
                           f'(créance en souffrance au-delà de {seuil} jours)')
            if _f(r.get('encours')):
                a['montant'] = _f(r['encours'])
            res.append(a)
    return res, len(c.d['credits'])


def t_crd_sans_garantie(c, p):
    seuil = float(p['seuil'])
    df = c.d['credits']
    res = [c.anomalie('credits', r, f'Crédit de plus de {_fr(seuil, c.devise)} sans garantie renseignée') for r in _lignes(df[df['montant'] >= seuil])
           if not re.sub(r'aucun|aucune|neant|sans|nan|none|non|-', '', norm_nom(r.get('garantie') or '')).strip()]
    return res, len(df)


def t_kyc(c, p):
    cl = c.d['clients']
    ref = _ref_date(c)
    delais = {'eleve': int(p['revue_eleve']), 'moyen': int(p['revue_moyen']), 'faible': int(p['revue_faible'])}
    cols = {k: c.a('clients', k) for k in ('piece_identite', 'expiration_piece', 'adresse', 'profession', 'date_revue', 'niveau_risque')}
    res = []
    for r in _lignes(cl):
        motifs = []
        if cols['piece_identite'] and not str(r.get('piece_identite') or '').strip():
            motifs.append('pièce d’identité manquante')
        e = r.get('expiration_piece')
        if cols['expiration_piece'] and e is not None and not pd.isna(e) and e < ref:
            motifs.append(f'pièce expirée le {e.strftime("%d/%m/%Y")}')
        for k, lib in (('adresse', 'adresse'), ('profession', 'profession')):
            if cols[k] and not str(r.get(k) or '').strip():
                motifs.append(f'{lib} manquante')
        if cols['date_revue']:
            niv = sans_accents(r.get('niveau_risque') or '').lower()
            niv = 'eleve' if re.search(r'elev|haut|fort|high', niv) else 'faible' if re.search(r'faible|bas|low', niv) else 'moyen'
            d = r.get('date_revue')
            if d is None or pd.isna(d):
                motifs.append('jamais revu')
            elif (ref - d).days > delais[niv]:
                motifs.append(f'revue KYC du {d.strftime("%d/%m/%Y")} dépassée (risque {niv.replace("eleve", "élevé")})')
        if motifs:
            res.append(c.anomalie('clients', r, 'Dossier client : ' + ', '.join(motifs)))
    return res, len(cl)


ENTRANT = r'depot|versement|credit|recu|entree|reception|encaissement|\bin\b'
SORTANT = r'retrait|debit|emis|sortie|paiement|envoi|\bout\b'


def _sens(r):
    s = sans_accents(str(r.get('sens') or '')).lower()
    mt = _f(r.get('montant')) or 0
    if mt < 0 or re.search(SORTANT, s):
        return 'sortie'
    if re.search(ENTRANT, s):
        return 'entree'
    return ''


def _especes(r, avec_canal):
    txt = sans_accents(str(r.get('canal') or '') + ' ' + str(r.get('sens') or '')).lower()
    return bool(re.search(r'esp|cash|liquide|caisse|guichet|numeraire', txt)) if avec_canal else True


def t_lcb_fractionnement(c, p):
    seuil, jours = float(p['seuil']), int(p['jours'])
    plancher = seuil * float(p['part_min_pct']) / 100
    avec_canal = c.a('operations', 'canal')
    df = c.d['operations'].dropna(subset=['date'])
    ops = [r for r in _lignes(df) if _sens(r) == 'entree' and _especes(r, avec_canal) and plancher <= abs(_f(r['montant']) or 0) < seuil]
    par_client = {}
    for r in ops:
        par_client.setdefault(norm_id(r['client']), []).append(r)
    res, g = [], 0
    for _k, recs in par_client.items():
        recs.sort(key=lambda x: x['date'])
        i = 0
        while i < len(recs):
            j = i
            while j + 1 < len(recs) and (recs[j + 1]['date'] - recs[i]['date']).days <= jours:
                j += 1
            bloc = recs[i:j + 1]
            total = sum(abs(_f(x['montant']) or 0) for x in bloc)
            if len(bloc) > 1 and total >= seuil:
                g += 1
                for x in bloc:
                    res.append(c.anomalie('operations', x, f'{len(bloc)} dépôts{" en espèces" if avec_canal else ""} en {jours} jours, chacun juste sous le seuil de '
                                          f'{_fr(seuil, c.devise)}, total {_fr(total, c.devise)}', g))
                i = j + 1
            else:
                i += 1
    return res, len(df)


def t_lcb_pep(c, p):
    sensibles = {}
    for r in _lignes(c.d['clients']):
        pep = re.search(r'^(oui|yes|o|y|1|true|vrai|pep|ppe)', sans_accents(str(r.get('pep') or '')).lower().strip())
        risque = re.search(r'elev|haut|fort|high', sans_accents(str(r.get('niveau_risque') or '')).lower())
        if pep or risque:
            sensibles[norm_id(r['code'])] = 'personne politiquement exposée' if pep else 'client à risque élevé'
    seuil = float(p['seuil'])
    res = [c.anomalie('operations', r, f'Opération de {_fr(abs(r["montant"]), c.devise)} d’un {sensibles[norm_id(r["client"])]} : vigilance renforcée')
           for r in _lignes(c.d['operations']) if norm_id(r['client']) in sensibles and abs(_f(r['montant']) or 0) >= seuil]
    return res, len(c.d['operations'])


def t_lcb_dormants(c, p):
    jours, mini = int(p['jours']), float(p['montant_min'])
    df = c.d['operations'].dropna(subset=['date'])
    res = []
    for _k, grp in df.assign(_c=df['client'].map(norm_id)).groupby('_c'):
        recs = _lignes(grp.sort_values('date'))
        for avant, r in zip(recs, recs[1:]):
            ecart = (r['date'] - avant['date']).days
            if ecart >= jours and abs(_f(r['montant']) or 0) >= mini:
                res.append(c.anomalie('operations', r, f'Compte sans mouvement pendant {ecart} jours puis opération de {_fr(abs(r["montant"]), c.devise)}'))
    return res, len(df)


def t_lcb_pays(c, p):
    liste = {norm_nom(x) for x in _liste(p['pays'])}
    res = [c.anomalie('operations', r, f'Contrepartie dans un pays à haut risque ({r["pays"]})') for r in _lignes(c.d['operations'])
           if norm_nom(r.get('pays') or '') in liste]
    return res, len(c.d['operations'])


def t_lcb_transit(c, p):
    heures, part = float(p['heures']), float(p['part_pct']) / 100
    df = c.d['operations'].dropna(subset=['date'])
    res, g = [], 0
    for _k, grp in df.assign(_c=df['client'].map(norm_id)).groupby('_c'):
        recs = _lignes(grp.sort_values('date'))
        entrees = [r for r in recs if _sens(r) == 'entree' and abs(_f(r['montant']) or 0) >= float(p['montant_min'])]
        sorties = [r for r in recs if _sens(r) == 'sortie']
        pris = set()
        for e in entrees:
            for s_ in sorties:
                delai = (s_['date'] - e['date']).total_seconds() / 3600
                if s_['_ligne'] not in pris and 0 <= delai <= heures and abs(_f(s_['montant']) or 0) >= abs(e['montant']) * part:
                    pris.add(s_['_ligne'])
                    g += 1
                    res.append(c.anomalie('operations', e, f'Entrée de {_fr(abs(e["montant"]), c.devise)} ressortie aussitôt '
                                          f'({_fr(abs(s_["montant"]), c.devise)} le {s_["date"].strftime("%d/%m/%Y")}) : compte de transit ?', g))
                    res.append(c.anomalie('operations', s_, f'Sortie qui suit l’entrée {e["reference"]}', g))
                    break
    return res, len(df)


ORDRE_STAT = ['paiements', 'factures', 'ventes', 'operations', 'credits']


def _jeu_stat(c):
    for j in ORDRE_STAT:
        if c.a(j, 'montant') and c.a(j, JEUX[j]['tiers']):
            return j
    return None


def _z_robuste(valeurs, x):
    """Écart robuste (médiane et écart absolu médian) calculé sur le logarithme des montants : un montant 10 fois plus
    élevé que d'habitude pèse autant pour un petit tiers que pour un gros. Renvoie (écart, médiane des montants)."""
    v = pd.Series([max(float(a), 1.0) for a in valeurs])
    lv = v.map(math.log10)
    med = float(lv.median())
    mad = float((lv - med).abs().median())
    if mad < 0.005:
        mad = 0.005                       # montants presque identiques : un écart net reste détectable
    return 0.6745 * (math.log10(max(float(x), 1.0)) - med) / mad, float(10 ** med)


def t_stat_montants(c, p):
    jeu = _jeu_stat(c)
    df = c.d[jeu].dropna(subset=['montant'])
    df = df.assign(_t=df[JEUX[jeu]['tiers']].map(norm_id), _a=df['montant'].abs())
    seuil, mini = float(p['seuil']), int(p['minimum'])
    res = []
    for _t, grp in df[df['_t'] != ''].groupby('_t'):
        if len(grp) < mini:
            continue
        vals = list(grp['_a'])
        for r in _lignes(grp):
            z, med = _z_robuste(vals, r['_a'])
            if z > seuil and r['_a'] >= med * float(p['multiple']):
                res.append(c.anomalie(jeu, r, f'Montant atypique pour ce tiers : {_fr(r["_a"], c.devise)} contre {_fr(med, c.devise)} habituellement '
                                      f'(écart robuste {z:.1f} ; {len(grp)} opérations)'))
    return res, len(df)


def t_stat_mensuel(c, p):
    jeu = _jeu_stat(c)
    df = c.d[jeu].dropna(subset=['montant', 'date'])
    df = df.assign(_t=df[JEUX[jeu]['tiers']].map(norm_id), _m=df['date'].dt.strftime('%Y-%m'), _a=df['montant'].abs())
    seuil = float(p['seuil'])
    res = []
    for t, grp in df[df['_t'] != ''].groupby('_t'):
        mois = grp.groupby('_m')['_a'].sum()
        if len(mois) < 4:
            continue
        for m, total in mois.items():
            z, med = _z_robuste(list(mois), total)
            if z > seuil and total >= med * 2:
                r = _lignes(grp[grp['_m'] == m].sort_values('_a', ascending=False).head(1))[0]
                a = c.anomalie(jeu, r, f'Total de {m[5:]}/{m[:4]} pour ce tiers : {_fr(total, c.devise)} contre {_fr(med, c.devise)} par mois habituellement '
                               f'(écart robuste {z:.1f})')
                a['montant'] = float(total)
                res.append(a)
    return res, len(df)


PAYS_RISQUE = 'Iran, IR, Corée du Nord, KP, Myanmar, MM'
TESTS += [
    dict(code='PAIE_APRES_SORTIE', titre='Salaires versés après le départ', domaine='Paie', f=t_paie_apres_sortie,
         requis=[('paie', ('matricule', 'periode')), ('salaries', ('date_sortie',))], params=[], niveau='eleve',
         description='Salaire versé pour un mois postérieur à la date de sortie du salarié.',
         critere='La paie d’un salarié s’arrête au solde de tout compte ; les sorties sont transmises à la paie sans délai.',
         consequence='Paiements indus ; risque de détournement par maintien d’un salarié parti dans la paie.',
         recommandation='Récupérer les sommes versées à tort et rapprocher chaque mois les sorties RH et la paie.'),
    dict(code='PAIE_INCONNU', titre='Salariés payés absents du personnel', domaine='Paie', f=t_paie_inconnu,
         requis=[('paie', ('matricule',)), ('salaries', ('matricule',))], params=[], niveau='eleve',
         description='Matricule payé qui n’existe pas dans le fichier du personnel.',
         critere='Seuls les salariés présents dans le fichier du personnel sont payés.',
         consequence='Salariés fictifs (« emplois fantômes »).',
         recommandation='Vérifier l’existence des personnes relevées (pièce d’identité, contrat, présence) et bloquer leur paie.'),
    dict(code='PAIE_DOUBLE', titre='Double paie sur un même mois', domaine='Paie', f=t_paie_double,
         requis=[('paie', ('matricule', 'periode'))], params=[], niveau='eleve',
         description='Plusieurs salaires versés au même matricule pour le même mois.',
         critere='Un seul salaire par salarié et par mois (hors rappels documentés).',
         consequence='Paiement en double.', recommandation='Justifier les doubles versements (rappel, avance) ou les récupérer.'),
    dict(code='PAIE_RIB_PARTAGE', titre='Compte bancaire partagé entre salariés', domaine='Paie', f=t_paie_rib_partage,
         requis=[('salaries', ('rib', 'matricule'))], params=[], niveau='eleve',
         description='Le même compte bancaire reçoit le salaire de plusieurs salariés.',
         critere='Chaque salaire est versé sur un compte au nom du salarié.',
         consequence='Signe de salarié fictif ou de détournement de salaires.',
         recommandation='Obtenir les attestations de titularité des comptes relevés.'),
    dict(code='PAIE_VARIATION', titre='Variations anormales du salaire net', domaine='Paie', f=t_paie_variation,
         requis=[('paie', ('matricule', 'montant', 'periode'))], params=[('ecart_pct', 'Écart au net habituel (%)', 30, '')], niveau='moyen',
         description='Mois où le net payé dépasse nettement le net habituel du salarié (médiane, 3 mois au moins).',
         critere='Toute variation de rémunération est justifiée (avenant, prime approuvée, rappel).',
         consequence='Primes ou rappels non autorisés.', recommandation='Obtenir les justificatifs des variations relevées.'),
    dict(code='PAIE_HEURES_SUP', titre='Heures supplémentaires excessives', domaine='Paie', f=t_paie_heures_sup,
         requis=[('paie', ('heures_sup',))], params=[('seuil', 'Heures par mois au-delà desquelles signaler', 20, 'Selon le Code du travail et la convention collective')],
         niveau='moyen', description='Salariés dont les heures supplémentaires du mois dépassent le seuil.',
         critere='Les heures supplémentaires respectent les plafonds légaux et sont autorisées au préalable.',
         consequence='Coût indu, heures fictives, non-respect du droit du travail.',
         recommandation='Rapprocher les heures payées des relevés de présence et des autorisations.'),
    dict(code='SI_DEPARTS', titre='Comptes actifs de personnes parties', domaine='Habilitations informatiques', f=t_si_departs,
         requis=[('utilisateurs_si', ('statut',)), ('salaries', ('date_sortie',))], params=[], niveau='eleve',
         description='Compte applicatif encore actif alors que le salarié a quitté l’entreprise (et parfois utilisé après).',
         critere='Les accès sont retirés le jour du départ (procédure de sortie).',
         consequence='Accès non autorisé aux données et aux opérations.',
         recommandation='Désactiver les comptes relevés, analyser leur utilisation après le départ et automatiser le retrait des accès.'),
    dict(code='SI_GENERIQUES', titre='Comptes génériques actifs', domaine='Habilitations informatiques', f=t_si_generiques,
         requis=[('utilisateurs_si', ('identifiant',))], params=[], niveau='moyen',
         description='Comptes partagés ou génériques (admin, test, invité, stagiaire…) encore actifs.',
         critere='Chaque compte est nominatif ; les comptes techniques sont limités, protégés et surveillés.',
         consequence='Actions non attribuables à une personne ; contournement de la séparation des tâches.',
         recommandation='Désactiver les comptes génériques ou les rattacher à un responsable nommé, avec un mot de passe coffré.'),
    dict(code='SI_INACTIFS', titre='Comptes actifs inutilisés', domaine='Habilitations informatiques', f=t_si_inactifs,
         requis=[('utilisateurs_si', ('statut',))], params=[('jours', 'Sans connexion depuis (jours)', 90, '')], niveau='faible',
         description='Comptes actifs sans connexion depuis longtemps, ou jamais utilisés.',
         critere='Les comptes inutilisés sont désactivés lors de la revue périodique des habilitations.',
         consequence='Comptes oubliés exploitables par un tiers.', recommandation='Désactiver les comptes relevés après confirmation du responsable.'),
    dict(code='SI_INCOMPATIBLES', titre='Cumuls de droits incompatibles', domaine='Habilitations informatiques', f=t_si_incompatibles,
         requis=[('utilisateurs_si', ('roles',))],
         params=[('incompatibilites', 'Incompatibilités (une par ligne : « rôle A + rôle B »)',
                  'création fournisseur + validation paiement\nsaisie + validation\ncomptable + trésor\nadministrateur + comptab', '')],
         niveau='eleve', description='Comptes qui cumulent des rôles incompatibles (matrice de séparation des tâches).',
         critere='Les rôles incompatibles sont attribués à des personnes différentes.',
         consequence='Une seule personne peut initier et valider une opération : risque de fraude.',
         recommandation='Retirer l’un des rôles ou mettre en place un contrôle compensatoire documenté.'),
    dict(code='CRD_DELEGATION', titre='Crédits accordés hors délégation', domaine='Crédit', f=t_crd_delegation,
         requis=[('credits', ('accorde_par', 'montant'))],
         params=[('seuil', 'Montant à partir duquel un décideur est exigé', 5_000_000, ''),
                 ('plafonds', 'Délégations (une par ligne : « Décideur = plafond »)', '', 'Ex. : Chef d’agence Plateau = 25 000 000')],
         niveau='eleve', description='Crédit accordé au-delà de la délégation du décideur, ou sans décideur.',
         critere='Chaque crédit est accordé par l’organe compétent selon la grille des délégations.',
         consequence='Engagements non autorisés, risque de crédit non maîtrisé.',
         recommandation='Faire ratifier les dossiers relevés par l’organe compétent et bloquer la mise en place hors délégation.'),
    dict(code='CRD_FRACTIONNEMENT', titre='Crédits fractionnés sous la délégation', domaine='Crédit', f=t_crd_fractionnement,
         requis=[('credits', ('client', 'montant', 'date'))],
         params=[('seuil', 'Plafond de délégation', 25_000_000, ''), ('jours', 'Période regroupée (jours)', 30, ''),
                 ('part_min_pct', 'Ne retenir que les crédits d’au moins (% du plafond)', 20, '')], niveau='eleve',
         description='Plusieurs crédits au même client, chacun sous le plafond de délégation, dont le total le dépasse.',
         critere='Un besoin de financement n’est pas fractionné pour rester dans la délégation.',
         consequence='Contournement du comité de crédit.', recommandation='Consolider l’exposition par client avant toute décision.'),
    dict(code='CRD_PARTIES_LIEES', titre='Crédits au personnel', domaine='Crédit', f=t_crd_parties_liees,
         requis=[('credits', ('client',)), ('clients', ('nom',)), ('salaries', ('nom',))], params=[], niveau='moyen',
         description='Crédits dont l’emprunteur est un membre du personnel (même nom ou même matricule).',
         critere='Les crédits au personnel et aux parties liées suivent des conditions et une approbation spécifiques (réglementation prudentielle).',
         consequence='Conditions de faveur, conflits d’intérêts.', recommandation='Vérifier l’approbation et les conditions de chaque dossier relevé.'),
    dict(code='CRD_SOUFFRANCE', titre='Impayés non déclassés', domaine='Crédit', f=t_crd_souffrance,
         requis=[('credits', ('jours_retard',))], params=[('jours', 'Retard à partir duquel la créance est en souffrance (jours)', 90, '')],
         niveau='eleve', description='Crédits en retard au-delà du seuil mais toujours classés sains.',
         critere='Les créances en souffrance sont déclassées et provisionnées selon la réglementation (dispositif prudentiel BCEAO / COBAC).',
         consequence='Risque de crédit sous-estimé, provisions insuffisantes, résultat surévalué.',
         recommandation='Déclasser et provisionner les créances relevées ; automatiser le déclassement.'),
    dict(code='CRD_SANS_GARANTIE', titre='Crédits importants sans garantie', domaine='Crédit', f=t_crd_sans_garantie,
         requis=[('credits', ('garantie', 'montant'))], params=[('seuil', 'À partir de', 10_000_000, '')], niveau='moyen',
         description='Crédits au-delà du seuil sans garantie renseignée.',
         critere='Les crédits au-delà du seuil fixé par la politique de crédit sont garantis.',
         consequence='Perte en cas de défaut.', recommandation='Vérifier les dossiers relevés et compléter les garanties.'),
    dict(code='KYC_INCOMPLET', titre='Dossiers clients (KYC) incomplets ou périmés', domaine='LCB-FT', f=t_kyc,
         requis=[('clients', ('piece_identite|expiration_piece|date_revue',))],
         params=[('revue_eleve', 'Revue des clients à risque élevé (jours)', 365, ''), ('revue_moyen', 'Risque moyen (jours)', 730, ''),
                 ('revue_faible', 'Risque faible (jours)', 1095, '')], niveau='eleve',
         description='Clients sans pièce d’identité, pièce expirée, adresse ou profession manquante, ou revue KYC dépassée selon le niveau de risque.',
         critere='L’identité des clients est vérifiée et tenue à jour selon leur niveau de risque (loi uniforme LBC/FT, instructions BCEAO).',
         consequence='Manquement aux obligations de vigilance ; sanctions du régulateur.',
         recommandation='Compléter les dossiers relevés et bloquer les opérations des clients non mis à jour.'),
    dict(code='LCB_FRACTIONNEMENT', titre='Dépôts fractionnés sous le seuil de déclaration', domaine='LCB-FT', f=t_lcb_fractionnement,
         requis=[('operations', ('client', 'montant', 'date'))],
         params=[('seuil', 'Seuil de déclaration ou de vigilance', 5_000_000, 'À adapter au seuil réglementaire applicable'),
                 ('jours', 'Période regroupée (jours)', 7, ''), ('part_min_pct', 'Dépôts d’au moins (% du seuil)', 50, '')], niveau='eleve',
         description='Plusieurs dépôts (en espèces si le canal est connu) juste sous le seuil, dont le total le dépasse : fractionnement (« schtroumpfage »).',
         critere='Les opérations fractionnées pour éviter un seuil sont détectées et analysées (vigilance, déclaration de soupçon).',
         consequence='Blanchiment non détecté ; manquement aux obligations déclaratives.',
         recommandation='Analyser les cas relevés et, si le soupçon persiste, déclarer à la CENTIF.'),
    dict(code='LCB_PEP', titre='Opérations importantes des clients sensibles', domaine='LCB-FT', f=t_lcb_pep,
         requis=[('operations', ('client', 'montant')), ('clients', ('pep|niveau_risque',))],
         params=[('seuil', 'À partir de', 10_000_000, '')], niveau='moyen',
         description='Opérations au-delà du seuil de personnes politiquement exposées ou de clients à risque élevé.',
         critere='Les opérations des clients sensibles font l’objet d’une vigilance renforcée (origine des fonds, approbation).',
         consequence='Blanchiment ou corruption non détectés.', recommandation='Documenter l’origine des fonds pour chaque opération relevée.'),
    dict(code='LCB_DORMANTS', titre='Comptes dormants réactivés', domaine='LCB-FT', f=t_lcb_dormants,
         requis=[('operations', ('client', 'date', 'montant'))],
         params=[('jours', 'Inactivité d’au moins (jours)', 180, ''), ('montant_min', 'Opération d’au moins', 1_000_000, '')], niveau='moyen',
         description='Compte sans mouvement pendant longtemps, puis opération importante.',
         critere='La réactivation d’un compte dormant est contrôlée (identité, origine des fonds).',
         consequence='Utilisation frauduleuse d’un compte oublié, blanchiment.', recommandation='Vérifier l’identité et l’origine des fonds des cas relevés.'),
    dict(code='LCB_PAYS', titre='Opérations avec des pays à haut risque', domaine='LCB-FT', f=t_lcb_pays,
         requis=[('operations', ('pays',))], params=[('pays', 'Pays (noms ou codes ISO)', PAYS_RISQUE, 'Tenez la liste à jour avec les publications du GAFI')],
         niveau='eleve', description='Opérations dont la contrepartie est dans un pays de la liste.',
         critere='Les opérations avec les pays à haut risque font l’objet de mesures de vigilance renforcée.',
         consequence='Financement du terrorisme, contournement de sanctions.', recommandation='Appliquer la vigilance renforcée et documenter chaque opération.'),
    dict(code='LCB_TRANSIT', titre='Fonds en transit rapide', domaine='LCB-FT', f=t_lcb_transit,
         requis=[('operations', ('client', 'date', 'montant', 'sens'))],
         params=[('heures', 'Sortie dans les (heures)', 72, ''), ('part_pct', 'Part ressortie d’au moins (%)', 80, ''),
                 ('montant_min', 'Entrée d’au moins', 5_000_000, '')], niveau='eleve',
         description='Entrée importante aussitôt ressortie (retrait ou virement) : compte utilisé comme compte de passage.',
         critere='Les mouvements incohérents avec le profil du client sont détectés et analysés.',
         consequence='Blanchiment par compte de passage.', recommandation='Analyser les cas relevés et déclarer à la CENTIF si le soupçon persiste.'),
    dict(code='STAT_MONTANTS', titre='Montants atypiques pour un tiers', domaine='Analyse statistique', f=t_stat_montants,
         requis=[('paiements|factures|ventes|operations|credits', ('montant',))],
         params=[('seuil', 'Écart robuste à partir duquel signaler', 3.5, 'Méthode de la médiane (écart absolu médian), sur le logarithme des montants'),
                 ('multiple', 'Et au moins … fois le montant habituel', 3, ''), ('minimum', 'Opérations minimales par tiers', 5, '')], niveau='faible',
         description='Pour chaque fournisseur, client ou compte, montants très éloignés de ses montants habituels (méthode robuste de la médiane).',
         critere='Les opérations sont cohérentes avec l’activité habituelle du tiers.',
         consequence='Erreur de saisie, surfacturation ou opération frauduleuse isolée.', recommandation='Justifier les opérations relevées.'),
    dict(code='STAT_MENSUEL', titre='Mois atypiques par tiers', domaine='Analyse statistique', f=t_stat_mensuel,
         requis=[('paiements|factures|ventes|operations|credits', ('montant', 'date'))],
         params=[('seuil', 'Écart robuste à partir duquel signaler', 3.5, '')], niveau='faible',
         description='Mois où le total d’un tiers s’écarte fortement de ses autres mois et en dépasse le double (4 mois au moins).',
         critere='L’activité avec un tiers évolue de façon explicable (contrat, saisonnalité).',
         consequence='Pic d’activité anormal (favoritisme, fractionnement, fraude).', recommandation='Expliquer les pics relevés avec les responsables.'),
]
DOMAINES += ['Paie', 'Habilitations informatiques', 'Crédit', 'LCB-FT', 'Analyse statistique']
TESTS_PAR_CODE = {t['code']: t for t in TESTS}


def manquants(test, c):
    """Ce qu'il faut importer pour que le test soit applicable (liste de phrases ; vide = applicable)."""
    manque = []
    for jeux, chps in test['requis']:
        options = jeux.split('|')
        ok = False
        for jeu in options:
            if all(any(c.a(jeu, x) for x in ch.split('|')) for ch in chps):
                ok = True
                break
        if not ok:
            noms = ' ou '.join(JEUX[j]['libelle'].lower() for j in options)
            libs = {code: lib for j in options for code, lib, *_r in champs(j)}
            details = ', '.join(' ou '.join(f'« {libs.get(x, x)} »' for x in ch.split('|')) for ch in chps)
            manque.append(f'{noms} avec {details}')
    return manque


def parametres_effectifs(test, valeurs):
    res = {}
    for code, _lib, defaut, _aide in test['params']:
        v = (valeurs or {}).get(code, defaut)
        if isinstance(defaut, (int, float)):
            x = lire_montant(v) if isinstance(v, str) else v
            v = x if isinstance(x, (int, float)) and x >= 0 else defaut
        else:
            v = str(v if v is not None else defaut)[:2000]
        res[code] = v
    return res


def executer(donnees, choix, parametres=None, devise='FCFA', limite=None, cloture=None):
    """Lance les tests choisis. Renvoie {code: résultat}. Ne lève jamais d'erreur pour un test isolé."""
    c = Contexte(donnees, devise, cloture)
    resultats = {}
    for t in TESTS:
        if t['code'] not in choix:
            continue
        p = parametres_effectifs(t, (parametres or {}).get(t['code']))
        r = {'code': t['code'], 'titre': t['titre'], 'domaine': t['domaine'], 'niveau': t['niveau'], 'parametres': p,
             'statut': 'ok', 'raison': '', 'population': 0, 'nb': 0, 'cas': 0, 'montant': 0.0, 'anomalies': [], 'tableau': None}
        manque = manquants(t, c)
        if manque:
            r.update(statut='non_applicable', raison='Données à importer : ' + ' ; '.join(manque) + '.')
            resultats[t['code']] = r
            continue
        try:
            sortie = t['f'](c, p)
        except Exception as e:  # noqa: BLE001
            r.update(statut='erreur', raison=f'Le test n’a pas pu aboutir ({type(e).__name__}). Vérifiez les données importées.')
            resultats[t['code']] = r
            continue
        if sortie[0] is None:
            r.update(statut='non_applicable', raison=sortie[1])
            resultats[t['code']] = r
            continue
        anomalies, population = sortie[0], sortie[1]
        if len(sortie) > 2:
            r['tableau'] = sortie[2]
        anomalies.sort(key=lambda a: (-(a['montant'] or 0), a['jeu'], a['ligne']))
        if any(a['groupe'] for a in anomalies):            # garder les groupes ensemble, du plus gros au plus petit
            poids = {}
            for a in anomalies:
                if a['groupe']:
                    poids[a['groupe']] = poids.get(a['groupe'], 0) + (a['montant'] or 0)
            anomalies.sort(key=lambda a: (-poids.get(a['groupe'], a['montant'] or 0), a['groupe'] or 0, a['date'], a['ligne']))
        r['population'] = int(population)
        r['nb'] = len(anomalies)
        r['cas'] = len({a['groupe'] for a in anomalies if a['groupe']}) + sum(1 for a in anomalies if not a['groupe'])
        if t['code'] == 'CONCENTRATION':
            r['montant'] = 0.0
        else:
            vus = set()
            for a in anomalies:                    # une ligne comptée une fois
                k = (a['jeu'], a['ligne'])
                if k not in vus and a['montant']:
                    vus.add(k)
                    r['montant'] += a['montant']
        r['montant'] = round(r['montant'], 2)
        lim = limite or MAX_ANOMALIES
        r['anomalies'] = anomalies[:lim]
        r['tronque'] = len(anomalies) > lim
        r['statut'] = 'anomalies' if anomalies else 'ok'
        resultats[t['code']] = r
    return resultats


def priorite(r):
    """Ordre d'examen : niveau du test, puis montant concerné, puis nombre de cas."""
    return (-NIVEAUX.get(r['niveau'], ('', 0))[1] if r['statut'] == 'anomalies' else 0, r['statut'] != 'anomalies', -(r['montant'] or 0), -r['cas'])


# ====================================================================== échantillonnage traçable
def tirer_echantillon(df, jeu, taille, methode='aleatoire', graine=None):
    """Échantillon reproductible : la graine est conservée, le même tirage peut être refait."""
    import random
    info = JEUX[jeu]
    lignes = _lignes(df)
    taille = max(1, min(int(taille), len(lignes)))
    if methode == 'montants' and info['montant']:
        choisis = sorted(lignes, key=lambda r: -(_f(r[info['montant']]) or 0))[:taille]
    else:
        graine = int(graine) if graine is not None else random.SystemRandom().randint(1, 999_999)
        rng = random.Random(graine)
        choisis = sorted(rng.sample(lignes, taille), key=lambda r: r['_ligne'])
    c = Contexte({})
    return [c.anomalie(jeu, r, '') for r in choisis], graine


# ====================================================================== modèles de fichier
def exemple(jeu):
    """Deux lignes d'exemple (fictives) pour le fichier modèle."""
    ex = {
        'fournisseurs': [['F001', 'SOCIÉTÉ EXEMPLE SARL', 'CI008 01001 012345678901 23', '15/01/2024', 'K. Yao', '', 'Abidjan, Plateau', '+225 07 00 00 00 01', 'CC1234567A', 'Actif'],
                         ['F002', 'FOURNITURES DÉMO SA', 'CI008 01002 098765432109 87', '03/02/2025', 'A. Koné', '10/06/2026', 'Abidjan, Cocody', '+225 05 00 00 00 02', 'CC7654321B', 'Actif']],
        'factures': [['FA-2026-0001', 'F001', '05/03/2026', '1 180 000', 'BC-2026-010', '06/03/2026', 'M. Traoré', 'FCFA'],
                     ['FA-2026-0002', 'F002', '12/03/2026', '4 720 000', 'BC-2026-011', '13/03/2026', 'M. Traoré', 'FCFA']],
        'paiements': [['VIR-2026-001', 'F001', '20/03/2026', '1 180 000', 'CI008 01001 012345678901 23', 'S. Diallo', 'FA-2026-0001', 'Virement'],
                      ['VIR-2026-002', 'F002', '28/03/2026', '4 720 000', 'CI008 01002 098765432109 87', 'S. Diallo', 'FA-2026-0002', 'Virement']],
        'commandes': [['BC-2026-010', 'F001', '01/03/2026', '1 180 000', 'D. Kouassi', 'Ramette papier A4', '400', '2 950'],
                      ['BC-2026-011', 'F002', '08/03/2026', '4 720 000', 'D. Kouassi', 'Cartouche toner', '80', '59 000']],
        'salaries': [['M0001', 'KOUAME Ange', 'CI008 01003 011111111111 11', '+225 07 00 00 00 03', 'Abidjan, Yopougon', '', '02/05/2019', 'Comptable'],
                     ['M0002', 'BAMBA Awa', 'CI008 01004 022222222222 22', '+225 01 00 00 00 04', 'Abidjan, Marcory', '30/06/2026', '15/09/2021', 'Caissière']],
        'paie': [['M0001', 'KOUAME Ange', '31/01/2026', '450 000', 'CI008 01003 011111111111 11', '612 000', '4'],
                 ['M0002', 'BAMBA Awa', '31/01/2026', '320 000', 'CI008 01004 022222222222 22', '421 000', '0']],
        'utilisateurs_si': [['akouame', 'KOUAME Ange', 'Actif', 'Saisie comptable; Consultation', 'M0001', '28/06/2026', '02/05/2019', 'Sage 100'],
                            ['abamba', 'BAMBA Awa', 'Désactivé', 'Caisse', 'M0002', '29/06/2026', '15/09/2021', 'Core banking']],
        'credits': [['CR-2026-0001', 'CL001', '12/02/2026', '15 000 000', 'Comité de crédit', 'J. Koffi', 'Hypothèque', '12 400 000', '0', 'Sain'],
                    ['CR-2026-0002', 'CL002', '20/02/2026', '2 500 000', 'Chef d’agence Plateau', 'M. Sylla', '', '1 900 000', '95', 'Sain']],
        'operations': [['OP-000001', 'CL001', '03/03/2026', '4 500 000', 'Versement', 'Espèces', 'Côte d’Ivoire', 'Plateau'],
                       ['OP-000002', 'CL001', '04/03/2026', '-4 300 000', 'Virement émis', 'Virement', 'Mali', 'Plateau']],
        'grand_livre': [['ACH-000125', '05/03/2026', '601100', '1 000 000', '', 'Achat fournitures FA-2026-0001', 'ACH', 'FA-2026-0001', 'M. Traoré', '06/03/2026 09:14', 'F001', ''],
                        ['ACH-000125', '05/03/2026', '401100', '', '1 000 000', 'Achat fournitures FA-2026-0001', 'ACH', 'FA-2026-0001', 'M. Traoré', '06/03/2026 09:14', 'F001', 'A']],
        'ventes': [['FV-2026-0001', 'C001', '04/03/2026', '2 360 000', 'Facture', '', '5', 'A. Koné'],
                   ['AV-2026-0001', 'C001', '20/03/2026', '-236 000', 'Avoir', 'FV-2026-0001', '', 'A. Koné']],
        'clients': [['C001', 'CLIENT EXEMPLE SA', 'Actif', '10 000 000', '12/01/2024', 'CNI CI0012345', '31/12/2030', 'Abidjan, Plateau', 'Négoce', 'Non', 'Moyen', '15/01/2026'],
                    ['C002', 'COMMERCE DÉMO SARL', 'Bloqué', '2 000 000', '03/05/2025', 'RCCM CI-ABJ-2020-B-1', '', 'Bouaké', 'Commerce', 'Non', 'Élevé', '10/03/2024']],
        'encaissements': [['ENC-2026-0001', 'C001', '15/04/2026', '2 124 000', 'FV-2026-0001', 'Virement'],
                          ['ENC-2026-0002', 'C002', '16/04/2026', '500 000', 'FV-2026-0002', 'Mobile money']],
    }
    return ex[jeu]
