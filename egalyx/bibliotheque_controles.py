"""
Contrôles types (dispositifs de maîtrise) associés aux risques de la bibliothèque sectorielle.
Clé : intitulé exact du risque dans bibliotheque_donnees.SECTEURS.
Chaque contrôle : (nom, type, nature, fréquence) — valeurs compatibles avec le formulaire des dispositifs :
  type      Préventif | Détectif | Correctif | Dirigeant
  nature    Manuel | Automatique | Mixte
  fréquence Permanent | Quotidien | Hebdomadaire | Mensuel | Trimestriel | Semestriel | Annuel | Exceptionnel
Ce sont des points de départ : l'organisation les adapte, désigne un responsable et évalue leur efficacité.
"""

P, D, C, G = 'Préventif', 'Détectif', 'Correctif', 'Dirigeant'
M, A, X = 'Manuel', 'Automatique', 'Mixte'

CONTROLES = {
    # ------------------------------------------------------------------ transverse
    "Fraude interne (détournement d'actifs)": [
        ("Séparation des tâches entre engagement, paiement et comptabilisation", P, M, 'Permanent'),
        ("Revue mensuelle des écritures inhabituelles (montants ronds, hors heures, utilisateurs sensibles)", D, X, 'Mensuel'),
        ("Inventaire contradictoire des actifs et de la caisse", D, M, 'Trimestriel'),
    ],
    "Fraude aux paiements fournisseurs (faux RIB, fausses factures)": [
        ("Contre-appel au fournisseur sur un numéro connu avant tout changement de RIB", P, M, 'Permanent'),
        ("Double validation des paiements au-delà d'un seuil", P, X, 'Permanent'),
        ("Rapprochement commande – réception – facture avant paiement", P, X, 'Permanent'),
    ],
    "Corruption et trafic d'influence": [
        ("Cartographie des risques de corruption et code de conduite signé", G, M, 'Annuel'),
        ("Évaluation d'intégrité des intermédiaires et partenaires avant contrat", P, M, 'Permanent'),
        ("Registre des cadeaux et invitations avec validation au-delà d'un plafond", D, M, 'Trimestriel'),
    ],
    "Cyberattaque par rançongiciel": [
        ("Sauvegardes isolées hors ligne et test de restauration", C, X, 'Mensuel'),
        ("Application des correctifs de sécurité selon un délai défini", P, X, 'Mensuel'),
        ("Sensibilisation et simulation d'hameçonnage du personnel", P, M, 'Semestriel'),
    ],
    "Fuite de données personnelles": [
        ("Revue des habilitations aux applications contenant des données personnelles", D, M, 'Semestriel'),
        ("Chiffrement des postes portables et des échanges de fichiers", P, A, 'Permanent'),
        ("Registre des traitements et procédure de notification des violations", G, M, 'Annuel'),
    ],
    "Indisponibilité prolongée du système d'information": [
        ("Plan de continuité informatique testé (bascule sur site de secours)", C, X, 'Annuel'),
        ("Supervision des serveurs et alertes de disponibilité", D, A, 'Permanent'),
        ("Alimentation électrique secourue (onduleurs, groupe électrogène) entretenue", P, M, 'Trimestriel'),
    ],
    "Départ d'une personne clé sans relève": [
        ("Plan de succession des postes clés", G, M, 'Annuel'),
        ("Documentation des procédures critiques et binômes formés", P, M, 'Semestriel'),
    ],
    "Non-respect d'une nouvelle obligation réglementaire": [
        ("Veille réglementaire avec analyse d'impact et responsable désigné", P, M, 'Mensuel'),
        ("Plan de mise en conformité suivi par la conformité", D, M, 'Trimestriel'),
    ],
    "Erreur significative dans les états financiers": [
        ("Rapprochements bancaires et des comptes de tiers revus et signés", D, M, 'Mensuel'),
        ("Revue analytique des comptes à la clôture par un second niveau", D, M, 'Trimestriel'),
        ("Calendrier de clôture et liste de contrôle des écritures d'inventaire", P, M, 'Trimestriel'),
    ],
    "Accident du travail grave": [
        ("Document unique d'évaluation des risques professionnels mis à jour", G, M, 'Annuel'),
        ("Contrôle du port des équipements de protection individuelle", D, M, 'Hebdomadaire'),
        ("Formation sécurité à l'embauche et habilitations spécifiques", P, M, 'Annuel'),
    ],
    "Atteinte à la réputation sur les réseaux sociaux": [
        ("Veille des mentions de l'organisation sur les réseaux sociaux", D, X, 'Quotidien'),
        ("Procédure de gestion de crise et porte-parole désigné", C, M, 'Annuel'),
    ],
    "Conflit d'intérêts non déclaré": [
        ("Déclaration annuelle d'intérêts des dirigeants et acheteurs", P, M, 'Annuel'),
        ("Contrôle croisé fournisseurs – personnel (adresses, comptes bancaires)", D, X, 'Semestriel'),
    ],
    # ------------------------------------------------------------------ banque
    "Risque de crédit : défaut des grands emprunteurs": [
        ("Analyse financière et notation interne avant octroi, validées par le comité de crédit", P, M, 'Permanent'),
        ("Suivi des limites de concentration par contrepartie et groupe", D, X, 'Mensuel'),
        ("Revue annuelle des grands dossiers et des garanties", D, M, 'Annuel'),
    ],
    "Dégradation du portefeuille (créances en souffrance)": [
        ("Liste des impayés et relance dès le premier jour de retard", D, X, 'Quotidien'),
        ("Classement et provisionnement des créances selon les règles prudentielles", C, X, 'Mensuel'),
        ("Comité de recouvrement des dossiers sensibles", C, M, 'Mensuel'),
    ],
    "Non-respect des ratios prudentiels": [
        ("Calcul et contrôle des ratios avant transmission au superviseur", D, X, 'Mensuel'),
        ("Tableau d'alerte des ratios proches des seuils présenté à la direction", G, X, 'Mensuel'),
    ],
    "Blanchiment de capitaux via les comptes clients": [
        ("Connaissance client (KYC) complète à l'ouverture et mise à jour selon le risque", P, M, 'Permanent'),
        ("Surveillance automatisée des opérations atypiques et analyse des alertes", D, A, 'Quotidien'),
        ("Déclaration de soupçon à la cellule de renseignement financier dans les délais", C, M, 'Exceptionnel'),
    ],
    "Manquement au gel des avoirs (sanctions financières)": [
        ("Filtrage des clients et des virements contre les listes de sanctions à jour", P, A, 'Permanent'),
        ("Revue des alertes de filtrage et traçabilité des décisions", D, M, 'Quotidien'),
    ],
    "Risque de liquidité": [
        ("Suivi quotidien de la trésorerie et des impasses de liquidité", D, X, 'Quotidien'),
        ("Plan de financement d'urgence et tests de résistance", C, M, 'Semestriel'),
    ],
    "Fraude sur la monétique et le mobile banking": [
        ("Authentification forte des opérations et plafonds par canal", P, A, 'Permanent'),
        ("Détection en temps réel des transactions suspectes", D, A, 'Permanent'),
        ("Procédure d'opposition et de remboursement des clients", C, M, 'Permanent'),
    ],
    "Erreurs opérationnelles dans le traitement des opérations": [
        ("Validation à quatre yeux des opérations au-delà d'un seuil", P, M, 'Permanent'),
        ("Contrôle de second niveau par échantillon des opérations de la veille", D, M, 'Quotidien'),
        ("Rapprochement des comptes internes et suspens", D, X, 'Quotidien'),
    ],
    "Fraude interne en agence": [
        ("Arrêté de caisse quotidien contresigné et contrôle inopiné", D, M, 'Quotidien'),
        ("Revue des opérations sur comptes dormants et comptes du personnel", D, X, 'Mensuel'),
        ("Rotation des postes sensibles et congés obligatoires", P, M, 'Annuel'),
    ],
    "Risque de change et de taux": [
        ("Limites de position de change et de sensibilité au taux suivies quotidiennement", D, X, 'Quotidien'),
        ("Comité actif-passif (ALM) et stratégie de couverture", G, M, 'Trimestriel'),
    ],
    "Défaillance d'un prestataire informatique critique": [
        ("Contrat avec engagements de service, réversibilité et droit d'audit", P, M, 'Annuel'),
        ("Suivi des engagements de service et revue annuelle du prestataire", D, M, 'Trimestriel'),
        ("Plan de sortie ou de reprise en cas de défaillance", C, M, 'Annuel'),
    ],
    "Pratiques commerciales abusives (protection de la clientèle)": [
        ("Affichage des conditions tarifaires et remise du contrat avant signature", P, M, 'Permanent'),
        ("Traitement des réclamations clients dans un délai défini et analyse des causes", C, M, 'Mensuel'),
    ],
    # ------------------------------------------------------------------ microfinance
    "Surendettement des membres et hausse du PAR 30": [
        ("Analyse de la capacité de remboursement et consultation du bureau d'information sur le crédit", P, M, 'Permanent'),
        ("Suivi du PAR 30 par agent et par agence", D, X, 'Hebdomadaire'),
        ("Visites de contrôle des emprunteurs par un agent différent", D, M, 'Mensuel'),
    ],
    "Fraude des agents de crédit (crédits fictifs)": [
        ("Visite de vérification d'un échantillon de dossiers par le contrôle", D, M, 'Mensuel'),
        ("Décaissement sur compte de l'emprunteur, jamais en espèces à l'agent", P, M, 'Permanent'),
        ("Rotation des portefeuilles entre agents", P, M, 'Annuel'),
    ],
    "Vol ou perte d'espèces en agence ou en tournée": [
        ("Plafond d'encaisse et transfert sécurisé des excédents", P, M, 'Quotidien'),
        ("Arrêté de caisse contresigné et contrôle inopiné", D, M, 'Quotidien'),
        ("Assurance des valeurs en caisse et en transport", C, M, 'Annuel'),
    ],
    "Non-respect des normes prudentielles SFD": [
        ("Calcul et revue des normes prudentielles avant transmission", D, X, 'Trimestriel'),
        ("Tableau de bord prudentiel présenté au conseil", G, M, 'Trimestriel'),
    ],
    "Système d'information de gestion non fiable": [
        ("Rapprochement entre le système de gestion et la comptabilité", D, X, 'Mensuel'),
        ("Gestion des habilitations et journal des modifications", P, A, 'Permanent'),
    ],
    "Gouvernance faible des organes élus": [
        ("Formation des élus et charte de gouvernance signée", G, M, 'Annuel'),
        ("Procès-verbaux des organes et suivi des décisions", D, M, 'Trimestriel'),
    ],
    "Risque de liquidité lors de retraits massifs": [
        ("Suivi quotidien de la trésorerie par agence et réserve de liquidité", D, X, 'Quotidien'),
        ("Ligne de refinancement mobilisable et plan d'urgence", C, M, 'Annuel'),
    ],
    "Blanchiment via les transferts et dépôts": [
        ("Identification des clients et origine des fonds au-delà d'un seuil", P, M, 'Permanent'),
        ("Revue des transferts et dépôts atypiques", D, X, 'Hebdomadaire'),
    ],
    "Taux effectif global excessif ou non affiché": [
        ("Calcul du TEG conforme et contrôle par rapport au taux d'usure", P, X, 'Permanent'),
        ("Affichage des conditions en agence et dans les contrats", P, M, 'Permanent'),
    ],
    "Catastrophe climatique affectant les emprunteurs agricoles": [
        ("Plafond d'exposition au crédit agricole par zone", P, M, 'Annuel'),
        ("Assurance indicielle ou fonds de garantie proposés aux emprunteurs", C, M, 'Annuel'),
    ],
    # ------------------------------------------------------------------ assurance
    "Insuffisance des provisions techniques": [
        ("Calcul actuariel des provisions revu par un second niveau", D, M, 'Trimestriel'),
        ("Analyse des boni et mali sur exercices antérieurs", D, M, 'Annuel'),
    ],
    "Fraude à l'assurance (sinistres fictifs ou majorés)": [
        ("Expertise contradictoire des sinistres au-delà d'un seuil", P, M, 'Permanent'),
        ("Détection des signaux de fraude (déclarations répétées, délais suspects)", D, X, 'Hebdomadaire'),
        ("Cellule d'enquête et dépôt de plainte", C, M, 'Exceptionnel'),
    ],
    "Primes émises non encaissées": [
        ("Application de la règle « pas de prime, pas de garantie » et suspension automatique", P, A, 'Permanent'),
        ("Balance âgée des primes et relance des intermédiaires", D, X, 'Mensuel'),
    ],
    "Défaillance d'un réassureur": [
        ("Sélection des réassureurs selon leur notation et limites par réassureur", P, M, 'Annuel'),
        ("Suivi des créances sur réassureurs", D, M, 'Trimestriel'),
    ],
    "Non-respect de la marge de solvabilité": [
        ("Calcul de la marge de solvabilité et projections", D, X, 'Trimestriel'),
        ("Plan de redressement préparé en cas de dépassement", C, M, 'Annuel'),
    ],
    "Placements non conformes ou dépréciés": [
        ("Contrôle des placements par rapport aux règles de dispersion et de congruence", P, M, 'Trimestriel'),
        ("Évaluation des actifs et provisions pour dépréciation", D, M, 'Semestriel'),
    ],
    "Mauvaise conduite des intermédiaires": [
        ("Agrément et vérification des intermédiaires avant mandat", P, M, 'Permanent'),
        ("Contrôle des reversements de primes et des réclamations par intermédiaire", D, M, 'Trimestriel'),
    ],
    "Retard de règlement des sinistres": [
        ("Suivi des délais de règlement par dossier avec alertes", D, A, 'Hebdomadaire'),
        ("Délégations de règlement définies par montant", P, M, 'Annuel'),
    ],
    "Blanchiment via les contrats d'assurance vie": [
        ("Connaissance client et origine des fonds à la souscription et aux versements", P, M, 'Permanent'),
        ("Surveillance des rachats anticipés et versements atypiques", D, X, 'Mensuel'),
    ],
    "Catastrophe naturelle à forte concentration de risques": [
        ("Suivi des cumuls d'engagements par zone géographique", D, X, 'Trimestriel'),
        ("Programme de réassurance catastrophe adapté aux cumuls", C, M, 'Annuel'),
    ],
    # ------------------------------------------------------------------ mines et énergie
    "Accident majeur sur site (effondrement, explosion)": [
        ("Permis de travail et consignation avant interventions dangereuses", P, M, 'Permanent'),
        ("Inspections géotechniques et des installations à risque", D, M, 'Mensuel'),
        ("Plan d'urgence interne et exercices d'évacuation", C, M, 'Semestriel'),
    ],
    "Pollution environnementale (rejets, déversement)": [
        ("Surveillance des rejets et de la qualité de l'eau", D, X, 'Mensuel'),
        ("Bacs de rétention et procédure de confinement des déversements", C, M, 'Permanent'),
    ],
    "Conflit avec les communautés riveraines": [
        ("Plan d'engagement des parties prenantes et comité de concertation", G, M, 'Trimestriel'),
        ("Mécanisme de gestion des plaintes des communautés", C, M, 'Mensuel'),
    ],
    "Retrait ou suspension du permis d'exploitation": [
        ("Registre des obligations du permis et échéancier de conformité", P, M, 'Trimestriel'),
        ("Audit de conformité réglementaire du site", D, M, 'Annuel'),
    ],
    "Corruption dans l'obtention des titres et autorisations": [
        ("Interdiction des paiements de facilitation et traçabilité des démarches", P, M, 'Permanent'),
        ("Évaluation d'intégrité des consultants et intermédiaires", P, M, 'Permanent'),
    ],
    "Vol de production ou de carburant": [
        ("Rapprochement production, stocks et expéditions", D, X, 'Hebdomadaire'),
        ("Contrôle d'accès et vidéosurveillance des zones de stockage", P, A, 'Permanent'),
    ],
    "Volatilité des cours des matières premières": [
        ("Politique de couverture des prix validée par le conseil", G, M, 'Annuel'),
        ("Suivi des positions et scénarios de prix", D, M, 'Mensuel'),
    ],
    "Rupture de la chaîne d'approvisionnement (pièces, carburant)": [
        ("Stock de sécurité des pièces critiques et du carburant", P, M, 'Mensuel'),
        ("Fournisseurs alternatifs qualifiés", C, M, 'Annuel'),
    ],
    "Insécurité sur les sites et convois": [
        ("Plan de sûreté et escorte des convois sensibles", P, M, 'Permanent'),
        ("Analyse des incidents de sûreté et mise à jour du plan", C, M, 'Trimestriel'),
    ],
    "Non-respect du contenu local": [
        ("Suivi des achats et emplois locaux par rapport aux engagements", D, M, 'Trimestriel'),
        ("Plan de développement des fournisseurs locaux", G, M, 'Annuel'),
    ],
    # ------------------------------------------------------------------ télécoms
    "Panne majeure du réseau": [
        ("Redondance des équipements cœur de réseau et des liaisons", P, A, 'Permanent'),
        ("Supervision du réseau et escalade des incidents", D, A, 'Permanent'),
        ("Plan de reprise et exercices de bascule", C, M, 'Annuel'),
    ],
    "Fraude télécom (SIM box, bypass, roaming)": [
        ("Système de détection de la fraude et tests d'appels", D, A, 'Quotidien'),
        ("Blocage des numéros frauduleux et analyse des pertes", C, X, 'Hebdomadaire'),
    ],
    "Fraude et blanchiment sur le mobile money": [
        ("Plafonds par niveau d'identification du client", P, A, 'Permanent'),
        ("Surveillance des transactions atypiques et des agents à risque", D, A, 'Quotidien'),
    ],
    "Non-respect des obligations de qualité de service": [
        ("Mesure interne des indicateurs de qualité exigés par le régulateur", D, A, 'Mensuel'),
        ("Plan d'amélioration des zones sous les seuils", C, M, 'Trimestriel'),
    ],
    "Fuite de données clients": [
        ("Accès aux données clients limité, journalisé et revu", P, A, 'Permanent'),
        ("Revue des accès des prestataires et du personnel", D, M, 'Trimestriel'),
    ],
    "Revenue leakage (facturation incomplète)": [
        ("Rapprochement des enregistrements d'appels et de la facturation", D, A, 'Quotidien'),
        ("Revue des tarifs paramétrés avant mise en production", P, M, 'Permanent'),
    ],
    "Identification des abonnés non conforme": [
        ("Contrôle des pièces d'identité à l'activation des cartes SIM", P, X, 'Permanent'),
        ("Audit d'échantillons de dossiers d'abonnés par point de vente", D, M, 'Mensuel'),
    ],
    "Cyberattaque sur le cœur de réseau": [
        ("Segmentation du réseau et durcissement des équipements", P, X, 'Permanent'),
        ("Centre de supervision de la sécurité et réponse aux incidents", D, A, 'Permanent'),
    ],
    "Dépendance à un équipementier": [
        ("Contrats de maintenance avec engagements et stock de pièces", P, M, 'Annuel'),
        ("Stratégie de diversification des fournisseurs", G, M, 'Annuel'),
    ],
    "Fraude interne dans la distribution (dealers)": [
        ("Rapprochement des stocks de crédit et cartes SIM par distributeur", D, X, 'Hebdomadaire'),
        ("Contrôle des commissions versées et des anomalies", D, X, 'Mensuel'),
    ],
    # ------------------------------------------------------------------ secteur public
    "Irrégularités dans la passation des marchés publics": [
        ("Plan de passation et respect des seuils et procédures", P, M, 'Annuel'),
        ("Commission d'ouverture des plis et procès-verbaux", P, M, 'Permanent'),
        ("Revue a posteriori d'un échantillon de marchés", D, M, 'Semestriel'),
    ],
    "Détournement de deniers publics": [
        ("Séparation ordonnateur – comptable et contrôle de la régie", P, M, 'Permanent'),
        ("Arrêté de caisse et rapprochements bancaires", D, M, 'Mensuel'),
    ],
    "Paiement de dépenses non justifiées (service fait non constaté)": [
        ("Attestation de service fait avant tout paiement", P, M, 'Permanent'),
        ("Contrôle de la chaîne de la dépense par le contrôleur financier", D, M, 'Permanent'),
    ],
    "Agents fictifs ou doublons dans la paie": [
        ("Recensement physique et contrôle biométrique des agents", D, X, 'Annuel'),
        ("Rapprochement du fichier de paie avec le fichier du personnel", D, A, 'Mensuel'),
    ],
    "Recettes non recouvrées": [
        ("Suivi des restes à recouvrer et relances", D, X, 'Mensuel'),
        ("Rapprochement des recettes déclarées et encaissées", D, X, 'Mensuel'),
    ],
    "Non-réalisation des projets financés (bailleurs)": [
        ("Plan de travail et budget suivis par le comité de pilotage", G, M, 'Trimestriel'),
        ("Rapports d'avancement physique et financier", D, M, 'Trimestriel'),
    ],
    "Gestion défaillante du patrimoine (immobilisations, véhicules)": [
        ("Inventaire physique du patrimoine et étiquetage", D, M, 'Annuel'),
        ("Carnet de bord et contrôle de l'usage des véhicules", D, M, 'Mensuel'),
    ],
    "Retards dans la reddition des comptes": [
        ("Calendrier de production des comptes et suivi des échéances", P, M, 'Annuel'),
        ("Revue préalable des comptes avant transmission", D, M, 'Annuel'),
    ],
    "Conflits d'intérêts des décideurs": [
        ("Déclaration d'intérêts et de patrimoine des décideurs", P, M, 'Annuel'),
        ("Retrait des décisions en cas de conflit déclaré", P, M, 'Permanent'),
    ],
    "Indisponibilité des systèmes de gestion financière": [
        ("Sauvegardes et procédure de reprise des applications financières", C, X, 'Hebdomadaire'),
        ("Procédure dégradée manuelle documentée", C, M, 'Annuel'),
    ],
    # ------------------------------------------------------------------ industrie et commerce
    "Rupture d'approvisionnement en matières premières": [
        ("Stock de sécurité et suivi des délais fournisseurs", P, X, 'Hebdomadaire'),
        ("Fournisseurs alternatifs qualifiés", C, M, 'Annuel'),
    ],
    "Écarts d'inventaire et démarque inconnue": [
        ("Inventaires tournants et inventaire annuel contradictoire", D, M, 'Mensuel'),
        ("Analyse des écarts et contrôle d'accès aux zones de stockage", D, X, 'Mensuel'),
    ],
    "Non-conformité qualité d'un produit": [
        ("Contrôle qualité à réception et en fin de production", D, X, 'Permanent'),
        ("Traçabilité des lots et procédure de rappel", C, M, 'Permanent'),
    ],
    "Créances clients impayées": [
        ("Plafond de crédit par client et blocage automatique au dépassement", P, A, 'Permanent'),
        ("Balance âgée et relances échelonnées", D, X, 'Hebdomadaire'),
    ],
    "Pratiques anticoncurrentielles": [
        ("Formation au droit de la concurrence des commerciaux", P, M, 'Annuel'),
        ("Revue juridique des accords de distribution et de prix", D, M, 'Annuel'),
    ],
    "Panne d'un équipement de production critique": [
        ("Maintenance préventive planifiée", P, M, 'Mensuel'),
        ("Stock de pièces critiques et contrat de dépannage", C, M, 'Annuel'),
    ],
    "Fraude douanière et fiscale": [
        ("Revue des déclarations en douane et des valeurs déclarées", D, M, 'Mensuel'),
        ("Calendrier fiscal et revue des déclarations par un second niveau", P, M, 'Mensuel'),
    ],
    "Contrefaçon des produits de la marque": [
        ("Dépôt et protection des marques dans les pays de commercialisation", P, M, 'Annuel'),
        ("Veille du marché et signalement aux autorités", D, M, 'Trimestriel'),
    ],
    "Incendie sur site de production ou entrepôt": [
        ("Détection incendie, extincteurs et vérification périodique", P, X, 'Semestriel'),
        ("Plan d'évacuation et exercices", C, M, 'Annuel'),
    ],
    "Dépendance à un grand client": [
        ("Suivi de la part de chiffre d'affaires par client et objectif de diversification", G, M, 'Trimestriel'),
        ("Contrats pluriannuels et clauses de préavis", P, M, 'Annuel'),
    ],
}


def controles_du_risque(intitule):
    return [{'nom': n, 'type': t, 'nature': na, 'frequence': f} for n, t, na, f in CONTROLES.get(intitule, [])]
