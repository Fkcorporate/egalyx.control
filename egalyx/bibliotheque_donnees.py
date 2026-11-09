"""
Bibliothèque de risques prêts à l'emploi, par secteur.
Chaque risque : (intitulé, catégorie, cause, conséquences, impact 1-5, probabilité 1-5, référentiel).
Impact et probabilité sont des valeurs de départ indicatives, à ajuster par l'organisation.
"""

SECTEURS = {
    'transverse': {
        'nom': 'Commun à toutes les organisations',
        'referentiels': 'COSO 2013, ISO 31000, OHADA (AUSCGIE, AUDCIF), RGPD / lois nationales de protection des données',
        'risques': [
            ("Fraude interne (détournement d'actifs)", 'Fraude', "Séparation des tâches insuffisante, contrôles a posteriori faibles", "Pertes financières, atteinte à la réputation, sanctions", 4, 3, 'COSO principe 8'),
            ("Fraude aux paiements fournisseurs (faux RIB, fausses factures)", 'Fraude', "Changement de coordonnées bancaires sans contre-appel, validation unique", "Paiements irrécupérables", 4, 3, 'COSO principe 10'),
            ("Corruption et trafic d'influence", 'Conformité', "Interactions avec agents publics, intermédiaires non évalués", "Poursuites pénales, exclusion des marchés publics", 5, 2, 'Sapin II art. 17, conventions ONU et UA'),
            ("Cyberattaque par rançongiciel", 'Systèmes d\'information', "Correctifs non appliqués, sauvegardes non isolées, hameçonnage", "Arrêt d'activité, perte de données, rançon", 5, 3, 'ISO 27001 A.8, NIST CSF'),
            ("Fuite de données personnelles", 'Conformité', "Droits d'accès excessifs, envoi de fichiers non chiffrés", "Sanction de l'autorité de protection des données, perte de confiance", 4, 3, 'RGPD art. 32, loi ivoirienne 2013-450, loi sénégalaise 2008-12'),
            ("Indisponibilité prolongée du système d'information", 'Systèmes d\'information', "Absence de plan de continuité testé, coupures électriques", "Interruption des opérations clés", 4, 3, 'ISO 22301'),
            ("Départ d'une personne clé sans relève", 'Ressources humaines', "Connaissances non documentées, absence de plan de succession", "Perte de savoir-faire, retards", 3, 3, 'COSO principe 4'),
            ("Non-respect d'une nouvelle obligation réglementaire", 'Conformité', "Veille réglementaire absente ou non diffusée", "Amendes, injonctions", 3, 3, 'COSO principe 9'),
            ("Erreur significative dans les états financiers", 'Financier', "Clôture manuelle, rapprochements non revus", "Réserves du commissaire aux comptes, décisions faussées", 4, 2, 'AUDCIF / SYSCOHADA révisé'),
            ("Accident du travail grave", 'Santé et sécurité', "Formation insuffisante, équipements de protection non portés", "Atteinte aux personnes, responsabilité pénale de l'employeur", 5, 2, 'Code du travail, ISO 45001'),
            ("Atteinte à la réputation sur les réseaux sociaux", 'Réputation', "Incident client mal géré, absence de veille", "Perte de clients, crise médiatique", 3, 3, 'COSO ERM 2017'),
            ("Conflit d'intérêts non déclaré", 'Éthique', "Absence de déclaration annuelle, relations familiales avec fournisseurs", "Décisions biaisées, surcoûts", 3, 3, 'Code de conduite, Sapin II'),
        ],
    },
    'banque': {
        'nom': 'Banque',
        'referentiels': 'BCEAO / COBAC (circulaires gouvernance, contrôle interne et risques), Bâle II/III, loi uniforme LBC/FT UEMOA, GAFI',
        'risques': [
            ("Risque de crédit : défaut des grands emprunteurs", 'Crédit', "Concentration du portefeuille, analyse financière insuffisante", "Provisions massives, atteinte aux fonds propres", 5, 3, 'Dispositif prudentiel UMOA, normes de division des risques'),
            ("Dégradation du portefeuille (créances en souffrance)", 'Crédit', "Suivi des impayés tardif, garanties mal évaluées", "Hausse du coût du risque", 4, 4, 'Instruction BCEAO créances en souffrance'),
            ("Non-respect des ratios prudentiels", 'Conformité', "Croissance des encours non anticipée, pilotage des fonds propres faible", "Sanctions de la Commission bancaire", 5, 2, 'Dispositif prudentiel UMOA / COBAC'),
            ("Blanchiment de capitaux via les comptes clients", 'LCB-FT', "KYC incomplet, scénarios de détection inadaptés", "Sanctions, retrait d'agrément, perte de correspondants", 5, 3, 'Loi uniforme LBC/FT, recommandations GAFI 10 et 20'),
            ("Manquement au gel des avoirs (sanctions financières)", 'LCB-FT', "Filtrage des virements absent ou non mis à jour", "Sanctions pénales et internationales", 5, 2, 'Résolutions ONU, règlement UEMOA gel des avoirs'),
            ("Risque de liquidité", 'Financier', "Dépendance à quelques gros déposants, inadéquation des maturités", "Incapacité à honorer les retraits", 5, 2, 'Bâle III LCR / NSFR'),
            ("Fraude sur la monétique et le mobile banking", 'Fraude', "Authentification faible, surveillance des transactions limitée", "Pertes, réclamations clients", 4, 4, 'Instruction BCEAO paiements électroniques'),
            ("Erreurs opérationnelles dans le traitement des opérations", 'Opérationnel', "Saisies manuelles, contrôles de second niveau absents", "Pertes, litiges", 3, 4, 'Bâle risque opérationnel'),
            ("Fraude interne en agence", 'Fraude', "Rotation du personnel insuffisante, contrôles de caisse irréguliers", "Détournements", 4, 3, 'Circulaire contrôle interne'),
            ("Risque de change et de taux", 'Marché', "Positions non couvertes, absence de limites", "Pertes de marché", 3, 3, 'Bâle risque de marché'),
            ("Défaillance d'un prestataire informatique critique", 'Externalisation', "Contrat sans clause de réversibilité, dépendance unique", "Interruption des services bancaires", 4, 2, 'Lignes directrices externalisation'),
            ("Pratiques commerciales abusives (protection de la clientèle)", 'Conformité', "Tarification non transparente, réclamations non traitées", "Sanctions, contentieux", 3, 3, 'Réglementation BCEAO services bancaires gratuits'),
        ],
    },
    'microfinance': {
        'nom': 'Microfinance (SFD)',
        'referentiels': 'Loi portant réglementation des SFD (UMOA), instructions BCEAO, COBAC pour la CEMAC',
        'risques': [
            ("Surendettement des membres et hausse du PAR 30", 'Crédit', "Analyse de capacité de remboursement superficielle, crédits croisés", "Pertes, dégradation de la mission sociale", 4, 4, 'Instruction BCEAO normes prudentielles SFD'),
            ("Fraude des agents de crédit (crédits fictifs)", 'Fraude', "Visites terrain non contrôlées, décaissements en espèces", "Pertes, perte de confiance des membres", 4, 3, 'Contrôle interne SFD'),
            ("Vol ou perte d'espèces en agence ou en tournée", 'Opérationnel', "Encaisses élevées, transport non sécurisé", "Pertes, atteinte à la sécurité du personnel", 4, 3, 'Procédures de caisse'),
            ("Non-respect des normes prudentielles SFD", 'Conformité', "Croissance rapide, fonds propres insuffisants", "Mise sous administration provisoire", 5, 2, 'Loi SFD UMOA'),
            ("Système d'information de gestion non fiable", 'Systèmes d\'information', "Logiciel non intégré, saisies a posteriori", "Reporting erroné, fraudes non détectées", 3, 4, 'Instruction BCEAO SIG'),
            ("Gouvernance faible des organes élus", 'Gouvernance', "Formation insuffisante des élus, conflits d'intérêts", "Décisions inadaptées, détournements", 4, 3, 'Loi SFD'),
            ("Risque de liquidité lors de retraits massifs", 'Financier', "Rumeurs, crise locale, concentration de l'épargne", "Cessation de paiement", 5, 2, 'Normes de liquidité SFD'),
            ("Blanchiment via les transferts et dépôts", 'LCB-FT', "Identification sommaire des membres", "Sanctions", 4, 2, 'Loi uniforme LBC/FT'),
            ("Taux effectif global excessif ou non affiché", 'Conformité', "Frais annexes non intégrés", "Sanctions, réputation", 3, 3, 'Loi sur l\'usure UMOA'),
            ("Catastrophe climatique affectant les emprunteurs agricoles", 'Externe', "Concentration sectorielle, absence d'assurance indicielle", "Défauts massifs", 4, 3, 'ISO 31000'),
        ],
    },
    'assurance': {
        'nom': 'Assurance',
        'referentiels': 'Code CIMA (contrôle interne, solvabilité, LBC/FT), Solvabilité II pour les filiales européennes',
        'risques': [
            ("Insuffisance des provisions techniques", 'Technique', "Hypothèses actuarielles obsolètes, sinistres tardifs", "Pertes, non-respect de la marge de solvabilité", 5, 3, 'Code CIMA'),
            ("Fraude à l'assurance (sinistres fictifs ou majorés)", 'Fraude', "Expertise insuffisante, collusion avec prestataires", "Surcoûts sinistres", 4, 4, 'Code CIMA'),
            ("Primes émises non encaissées", 'Financier', "Délivrance d'attestations sans paiement, intermédiaires défaillants", "Créances irrécouvrables, sanction CIMA", 4, 4, 'Article 13 du Code CIMA'),
            ("Défaillance d'un réassureur", 'Contrepartie', "Concentration, notation faible", "Charge de sinistres non couverte", 5, 2, 'Code CIMA réassurance'),
            ("Non-respect de la marge de solvabilité", 'Conformité', "Croissance rapide, placements non admis", "Retrait d'agrément", 5, 2, 'Code CIMA'),
            ("Placements non conformes ou dépréciés", 'Financier', "Règles de dispersion non respectées", "Perte de valeur, sanctions", 4, 3, 'Code CIMA placements'),
            ("Mauvaise conduite des intermédiaires", 'Conformité', "Agents non agréés, conseil inadapté", "Contentieux, sanctions", 3, 3, 'Code CIMA intermédiation'),
            ("Retard de règlement des sinistres", 'Opérationnel', "Processus manuel, pièces incomplètes", "Réclamations, réputation", 3, 4, 'Code CIMA'),
            ("Blanchiment via les contrats d'assurance vie", 'LCB-FT', "Rachats anticipés non surveillés", "Sanctions", 4, 2, 'Règlement CIMA LBC/FT'),
            ("Catastrophe naturelle à forte concentration de risques", 'Technique', "Cumuls non suivis", "Sinistralité exceptionnelle", 5, 2, 'Gestion des cumuls'),
        ],
    },
    'mines_energie': {
        'nom': 'Mines, pétrole et énergie',
        'referentiels': 'Codes miniers et pétroliers nationaux, ITIE, IFC Performance Standards, ISO 14001 / 45001',
        'risques': [
            ("Accident majeur sur site (effondrement, explosion)", 'Santé et sécurité', "Procédures de sécurité non appliquées, maintenance différée", "Pertes humaines, arrêt du site", 5, 2, 'ISO 45001'),
            ("Pollution environnementale (rejets, déversement)", 'Environnement', "Bassins de rétention insuffisants, contrôles environnementaux rares", "Amendes, réparation, conflit avec les communautés", 5, 3, 'ISO 14001, IFC PS3'),
            ("Conflit avec les communautés riveraines", 'Social', "Engagements sociaux non tenus, compensation contestée", "Blocage du site", 4, 3, 'IFC PS1 et PS5'),
            ("Retrait ou suspension du permis d'exploitation", 'Conformité', "Obligations du cahier des charges non respectées", "Arrêt d'activité", 5, 2, 'Code minier'),
            ("Corruption dans l'obtention des titres et autorisations", 'Conformité', "Intermédiaires locaux non vérifiés", "Poursuites, annulation des titres", 5, 2, 'ITIE, FCPA / Sapin II'),
            ("Vol de production ou de carburant", 'Fraude', "Contrôles de stock insuffisants, pesées non fiables", "Pertes", 4, 4, 'COSO'),
            ("Volatilité des cours des matières premières", 'Marché', "Absence de couverture", "Baisse de rentabilité", 4, 4, 'Politique de couverture'),
            ("Rupture de la chaîne d'approvisionnement (pièces, carburant)", 'Opérationnel', "Fournisseurs uniques, logistique enclavée", "Arrêt de production", 4, 3, 'ISO 22301'),
            ("Insécurité sur les sites et convois", 'Sécurité', "Zones instables, protection insuffisante", "Atteinte aux personnes, pertes", 5, 3, 'Principes volontaires sécurité et droits humains'),
            ("Non-respect du contenu local", 'Conformité', "Recrutement et achats locaux insuffisants", "Pénalités", 3, 3, 'Codes miniers et pétroliers'),
        ],
    },
    'telecoms': {
        'nom': 'Télécoms et numérique',
        'referentiels': 'Autorités de régulation des télécoms (ARTCI, ARTP…), réglementation monnaie électronique BCEAO, ISO 27001',
        'risques': [
            ("Panne majeure du réseau", 'Opérationnel', "Redondance insuffisante, alimentation électrique des sites", "Pénalités du régulateur, perte de clients", 5, 3, 'Cahier des charges de la licence'),
            ("Fraude télécom (SIM box, bypass, roaming)", 'Fraude', "Détection en temps réel absente", "Pertes de revenus interconnexion", 4, 4, 'GSMA FF'),
            ("Fraude et blanchiment sur le mobile money", 'LCB-FT', "Identification des clients incomplète, limites non appliquées", "Sanctions BCEAO, retrait d'agrément", 5, 3, 'Instruction BCEAO monnaie électronique'),
            ("Non-respect des obligations de qualité de service", 'Conformité', "Investissements insuffisants", "Amendes du régulateur", 4, 3, 'Décisions du régulateur'),
            ("Fuite de données clients", 'Conformité', "Accès internes non tracés, sous-traitants", "Sanctions, réputation", 4, 3, 'Lois protection des données'),
            ("Revenue leakage (facturation incomplète)", 'Financier', "Rapprochements réseau / facturation absents", "Perte de chiffre d'affaires", 4, 4, 'Revenue assurance TM Forum'),
            ("Identification des abonnés non conforme", 'Conformité', "Ventes de SIM préactivées", "Amendes, suspension des ventes", 4, 3, 'Réglementation identification abonnés'),
            ("Cyberattaque sur le cœur de réseau", 'Systèmes d\'information', "Équipements non mis à jour, accès fournisseurs", "Interruption, espionnage", 5, 2, 'ISO 27001, GSMA'),
            ("Dépendance à un équipementier", 'Externalisation', "Contrat unique, sanctions internationales", "Blocage de maintenance", 4, 2, 'Politique fournisseurs'),
            ("Fraude interne dans la distribution (dealers)", 'Fraude', "Commissions non contrôlées", "Pertes", 3, 4, 'COSO'),
        ],
    },
    'secteur_public': {
        'nom': 'Secteur public et établissements publics',
        'referentiels': 'Directives UEMOA / CEMAC sur les finances publiques et les marchés publics, codes des marchés publics, INTOSAI',
        'risques': [
            ("Irrégularités dans la passation des marchés publics", 'Conformité', "Fractionnement, entente, dossiers incomplets", "Annulation, sanctions, détournements", 5, 4, 'Code des marchés publics, directive UEMOA'),
            ("Détournement de deniers publics", 'Fraude', "Séparation ordonnateur / comptable non respectée", "Préjudice, poursuites", 5, 3, 'Directive UEMOA RGCP'),
            ("Paiement de dépenses non justifiées (service fait non constaté)", 'Financier', "Contrôle du service fait formel", "Pertes", 4, 4, 'RGCP'),
            ("Agents fictifs ou doublons dans la paie", 'Fraude', "Fichier de paie non rapproché des effectifs réels", "Surcoût salarial", 4, 3, 'Contrôle de la masse salariale'),
            ("Recettes non recouvrées", 'Financier', "Titres non émis, régies mal contrôlées", "Manque à gagner", 4, 4, 'RGCP'),
            ("Non-réalisation des projets financés (bailleurs)", 'Opérationnel', "Capacités de gestion faibles, décaissements tardifs", "Suspension des financements", 4, 3, 'Procédures des bailleurs'),
            ("Gestion défaillante du patrimoine (immobilisations, véhicules)", 'Opérationnel', "Inventaire absent", "Pertes, usages privés", 3, 4, 'Comptabilité des matières'),
            ("Retards dans la reddition des comptes", 'Conformité', "Comptabilité tenue tardivement", "Observations de la Cour des comptes", 3, 4, 'Directive UEMOA'),
            ("Conflits d'intérêts des décideurs", 'Éthique', "Déclarations de patrimoine non contrôlées", "Décisions partiales", 4, 3, 'Lois anticorruption nationales'),
            ("Indisponibilité des systèmes de gestion financière", 'Systèmes d\'information', "Infrastructures vieillissantes", "Blocage des paiements", 3, 3, 'Schéma directeur informatique'),
        ],
    },
    'industrie_commerce': {
        'nom': 'Industrie, distribution et commerce',
        'referentiels': 'OHADA, normes qualité ISO 9001, ISO 14001, ISO 45001',
        'risques': [
            ("Rupture d'approvisionnement en matières premières", 'Opérationnel', "Fournisseur unique, délais d'importation", "Arrêt de production, ventes perdues", 4, 3, 'ISO 22301'),
            ("Écarts d'inventaire et démarque inconnue", 'Fraude', "Inventaires annuels seulement, accès aux stocks libres", "Pertes", 3, 4, 'COSO'),
            ("Non-conformité qualité d'un produit", 'Qualité', "Contrôles en cours de fabrication insuffisants", "Rappel, réclamations, réputation", 4, 3, 'ISO 9001'),
            ("Créances clients impayées", 'Financier', "Plafonds de crédit non suivis", "Trésorerie tendue, pertes", 4, 4, 'Politique de crédit client'),
            ("Pratiques anticoncurrentielles", 'Conformité', "Échanges d'informations avec concurrents", "Amendes", 4, 2, 'Règlement UEMOA concurrence'),
            ("Panne d'un équipement de production critique", 'Opérationnel', "Maintenance préventive insuffisante", "Arrêt de ligne", 4, 3, 'Plan de maintenance'),
            ("Fraude douanière et fiscale", 'Conformité', "Classement tarifaire erroné, sous-évaluation", "Redressements, pénalités", 4, 3, 'Code des douanes, CGI'),
            ("Contrefaçon des produits de la marque", 'Externe', "Marques non protégées à l'OAPI", "Perte de parts de marché", 3, 3, 'Accord de Bangui (OAPI)'),
            ("Incendie sur site de production ou entrepôt", 'Santé et sécurité', "Installations électriques vétustes, stockage inadapté", "Destruction d'actifs", 5, 2, 'Réglementation ICPE'),
            ("Dépendance à un grand client", 'Stratégique', "Concentration du chiffre d'affaires", "Chute brutale des ventes", 4, 3, 'ISO 31000'),
        ],
    },
}

IMPACT_TXT = {1: 'negligeable', 2: 'mineur', 3: 'modere', 4: 'majeur', 5: 'critique'}
PROBA_TXT = {1: 'tres_rare', 2: 'rare', 3: 'possible', 4: 'probable', 5: 'frequente'}


def risques_du_secteur(code):
    s = SECTEURS.get(code)
    if not s:
        return []
    return [{'index': i, 'intitule': r[0], 'categorie': r[1], 'cause': r[2], 'consequences': r[3],
             'impact': r[4], 'probabilite': r[5], 'referentiel': r[6]} for i, r in enumerate(s['risques'])]
