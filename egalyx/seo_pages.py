"""
egalyx/seo_pages.py — contenu des pages de mots-clés du site public (une page = une recherche Google).

Règles suivies pour chaque page :
  - un seul sujet, une seule intention de recherche, un titre (< 60 caractères) et une description (< 158) uniques ;
  - un contenu réel et vérifiable : uniquement des fonctions qui existent dans Egalyx, aucun chiffre de clientèle,
    aucun avis ni certification non prouvés ;
  - des liens vers les pages voisines et vers les meilleurs articles du blog (maillage interne) ;
  - une FAQ, reprise en données structurées (FAQPage).
Pour modifier une page : changer le texte ici (et la date « maj »), rien d'autre à toucher.
"""

MAJ = '2026-11-26'

PAGES = {}

# ---------------------------------------------------------------------------------------------------------------
PAGES['logiciel-audit-interne-ia'] = dict(
    maj=MAJ,
    titre="Logiciel d'audit interne avec IA | Egalyx",
    description="Logiciel d'audit interne complet : plan fondé sur les risques, missions, feuilles de travail, analyse de données, rapports et suivi des recommandations.",
    court="Logiciel d'audit interne",
    resume="Toute la fonction d'audit interne, du plan annuel au suivi des recommandations.",
    h1="Le logiciel d'audit interne qui couvre toute la mission, du plan annuel au suivi",
    chapo="Egalyx réunit dans un même outil l'univers d'audit, le plan annuel fondé sur les risques, la conduite des "
          "missions, l'analyse des données, le rapport et le suivi des recommandations. L'intelligence artificielle "
          "aide à rédiger ; l'auditeur garde la main sur chaque conclusion.",
    points=[
        ("Une seule source", "Risques, contrôles, missions, constats et plans d'action sont liés entre eux : "
                             "un constat remonte jusqu'au risque qu'il concerne."),
        ("Des preuves vérifiables", "Feuilles de travail, pièces jointes, échantillons et tests de données "
                                    "restent attachés à la mission, avec la trace de qui a fait quoi."),
        ("L'IA comme assistant", "Premier jet des constats et du rapport à partir de vos notes, activable "
                                 "organisation par organisation."),
    ],
    sections=[
        dict(id='pourquoi', h2="Pourquoi un logiciel d'audit interne plutôt que des tableurs ?", html="""
<p>Beaucoup de services d'audit travaillent encore avec des classeurs Excel, des documents Word et des dossiers
partagés. Cela fonctionne pour une mission, mais pas pour piloter une fonction : il devient difficile de savoir
quelles entités n'ont pas été auditées depuis trois ans, quelles recommandations sont en retard ou quels risques
majeurs ne sont couverts par aucune mission.</p>
<p>Un logiciel d'audit interne relie ces informations. Le plan annuel part de la cartographie des risques, chaque
mission hérite des risques et des contrôles qu'elle doit tester, chaque constat produit une recommandation avec un
responsable et une échéance, et le comité d'audit obtient une vue d'ensemble sans consolidation manuelle.</p>"""),
        dict(id='planifier', h2="Planifier : univers d'audit et plan fondé sur les risques", html="""
<p>L'<strong>univers d'audit</strong> recense les entités auditables : directions, processus, filiales, projets,
systèmes. Pour chacune, Egalyx rapproche le niveau de risque issu de la cartographie, la date du dernier audit et
les incidents récents, ce qui permet de construire un <strong>plan d'audit pluriannuel</strong> défendable devant
le comité.</p>
<ul>
<li>priorisation des entités selon le risque résiduel et l'ancienneté du dernier audit ;</li>
<li>programme d'audit annuel avec charge prévue par auditeur ;</li>
<li>charte d'audit et évaluation de la qualité de la fonction, selon les Normes mondiales d'audit interne de
l'IIA (2024).</li>
</ul>"""),
        dict(id='realiser', h2="Réaliser la mission : lettre de mission, programme de travail, feuilles de travail", html="""
<p>Chaque mission suit un déroulé clair : lettre de mission, prise de connaissance, programme de travail, tests,
constats, rapport. Les <strong>feuilles de travail</strong> documentent chaque test (objectif, population,
échantillon, résultat, conclusion) et les pièces justificatives y sont attachées.</p>
<p>Les checklists d'audit se réutilisent d'une mission à l'autre, et la comparaison entre missions montre comment
une entité évolue d'un audit au suivant. Les audités peuvent répondre à des questionnaires en ligne et évaluer la
mission à sa clôture (satisfaction des audités).</p>"""),
        dict(id='donnees', h2="Tester 100 % des opérations avec l'analyse de données", html="""
<p>Au lieu de tester un échantillon de 25 factures, le module d'<a href="/audit-interne-automatise">analyse de
données</a> passe toute la population au crible : <strong>63 tests</strong> sur les achats, les paiements, la
comptabilité, les ventes, la paie, les habilitations informatiques, le crédit et la LCB-FT. Factures en double,
RIB modifié juste avant un paiement, écritures passées après la clôture, salaires versés après un départ : les
anomalies sont listées, classées par priorité, et peuvent devenir des constats en un clic.</p>
<p>Les données arrivent par fichier Excel, CSV ou FEC, ou directement depuis vos systèmes (bases SQL, Odoo,
Microsoft Business Central, Xero, QuickBooks, Zoho Books, SFTP, Microsoft 365, Google Drive).</p>"""),
        dict(id='ia', h2="Ce que fait l'intelligence artificielle, et ce qu'elle ne fait pas", html="""
<p>L'IA d'Egalyx sert à gagner du temps de rédaction : proposer un constat structuré (fait, critère, cause,
conséquence, recommandation) à partir de notes de terrain, écrire un premier jet de rapport, expliquer une
anomalie détectée dans les données ou résumer l'état d'une cartographie.</p>
<p>Elle ne remplace pas le jugement de l'auditeur : chaque proposition est relue, modifiée ou rejetée, et les
tests de données eux-mêmes sont des règles explicites et reproductibles, sans IA. L'IA est activable organisation
par organisation par l'administrateur ; désactivée, elle disparaît de l'interface.</p>"""),
        dict(id='rapport', h2="Rapport, recommandations et comité d'audit", html="""
<p>Le rapport d'audit s'exporte en Word ou en PDF. Les recommandations alimentent un <strong>registre unique</strong>
avec responsable, échéance, état d'avancement et preuves de mise en œuvre ; les relances partent automatiquement
et les retards sont visibles d'un coup d'œil.</p>
<p>Pour le comité d'audit ou le conseil, un rapport de synthèse rassemble l'avancement du plan, les constats
majeurs, les plans d'action en retard et les indicateurs de risque. La synthèse est produite à partir des chiffres
par des règles explicites : elle est reproductible et vérifiable.</p>"""),
    ],
    faq=[
        ("Qu'est-ce qu'un logiciel d'audit interne ?",
         "C'est un outil qui gère l'ensemble de la fonction d'audit : univers d'audit, plan annuel, missions, "
         "feuilles de travail, constats, rapports et suivi des recommandations, avec une trace de chaque étape."),
        ("Egalyx respecte-t-il les Normes mondiales d'audit interne de l'IIA ?",
         "Le déroulé des missions, la charte d'audit et l'évaluation de la qualité de la fonction s'appuient sur "
         "les Normes mondiales d'audit interne publiées par l'IIA en 2024. Le logiciel outille la démarche ; la "
         "conformité de votre fonction reste évaluée par vos soins ou par un évaluateur externe."),
        ("Peut-on utiliser Egalyx sans l'intelligence artificielle ?",
         "Oui. L'IA est activable organisation par organisation. Sans elle, toutes les fonctions d'audit, y compris "
         "les 63 tests d'analyse de données, restent disponibles."),
        ("Peut-on importer nos données comptables ?",
         "Oui : fichiers Excel (.xlsx), CSV et FEC, ou connexion directe à vos bases et logiciels de gestion. Un "
         "modèle Excel est fourni pour chaque type de données."),
        ("Egalyx convient-il à une petite équipe d'audit ?",
         "Oui. Un auditeur seul peut l'utiliser pour structurer ses missions ; les fonctions avancées (audit "
         "continu, connecteurs) s'ajoutent quand le besoin apparaît."),
    ],
    liens=['audit-interne-automatise', 'plan-action-correctif-logiciel', 'cartographie-risques-logiciel', 'gouvernance-entreprise-logiciel'],
    blog=['methodologie-audit-interne-normes-iso-2026', 'audit-interne-frequence-planification',
          'audit-interne-ia-automatisation', 'comment-choisir-logiciel-audit-2026'],
)

# ---------------------------------------------------------------------------------------------------------------
PAGES['audit-interne-automatise'] = dict(
    maj=MAJ,
    titre="Audit interne automatisé : analyse de données | Egalyx",
    description="63 tests automatiques sur achats, paiements, comptabilité, paie et LCB-FT. Import Excel, CSV, FEC ou connexion directe, et audit continu programmé.",
    court="Audit automatisé et analyse de données",
    resume="63 tests automatiques sur 100 % des opérations, en import ou en continu.",
    h1="Audit interne automatisé : testez 100 % des opérations, pas un échantillon",
    chapo="Le module d'analyse de données d'Egalyx applique 63 tests d'audit à l'ensemble de vos fichiers ou de vos "
          "systèmes : factures en double, paiements suspects, écritures hors horaires, salariés fantômes, droits "
          "informatiques incompatibles. Chaque anomalie est expliquée et peut devenir un constat.",
    points=[
        ("Toute la population", "Jusqu'à 200 000 lignes par fichier, analysées en quelques secondes, "
                                "au lieu d'un échantillon de quelques dizaines de pièces."),
        ("Des règles explicites", "Chaque test a un critère écrit et des paramètres modifiables : le "
                                  "résultat est reproductible et défendable."),
        ("En continu", "Programmez les tests chaque nuit ou chaque semaine : seules les nouvelles "
                       "anomalies vous sont signalées."),
    ],
    sections=[
        dict(id='principe', h2="Le principe : l'analyse de données appliquée à l'audit", html="""
<p>Un audit classique teste un échantillon : 25 factures, 30 paiements, une semaine d'écritures. Si la fraude ou
l'erreur se trouve ailleurs, elle passe inaperçue. L'analyse de données (on parle aussi d'audit assisté par
ordinateur) inverse la logique : <strong>on teste toutes les opérations</strong> et l'on concentre le travail
humain sur les exceptions.</p>
<p>Egalyx rend cette approche accessible sans compétence en programmation : vous importez un fichier ou branchez
une source, vous associez les colonnes (le logiciel les reconnaît le plus souvent seul), vous choisissez les tests,
et les résultats s'affichent par ordre de priorité avec le montant concerné.</p>"""),
        dict(id='tests', h2="63 tests, répartis en 12 domaines", html="""
<table class="pc-table">
<thead><tr><th scope="col">Domaine</th><th scope="col">Exemples de tests</th></tr></thead>
<tbody>
<tr><td>Factures et paiements</td><td>factures et paiements en double, paiement sur un autre compte que celui du fournisseur, RIB modifié peu avant un paiement, paiements un jour férié</td></tr>
<tr><td>Achats et fournisseurs</td><td>factures sans bon de commande, achats fractionnés sous le seuil, approbations hors délégation, fournisseur lié à un salarié, RIB partagé</td></tr>
<tr><td>Comptabilité</td><td>écritures déséquilibrées, passées après la clôture, saisies la nuit, écritures manuelles sur comptes sensibles, comptes d'attente non soldés</td></tr>
<tr><td>Ventes et encaissements</td><td>ruptures de numérotation, avoirs après la clôture, remises hors politique, dépassement de la limite de crédit</td></tr>
<tr><td>Paie</td><td>salaires versés après le départ, double paie sur un mois, compte bancaire partagé entre salariés, heures supplémentaires excessives</td></tr>
<tr><td>Habilitations informatiques</td><td>comptes actifs de personnes parties, comptes génériques, cumuls de droits incompatibles</td></tr>
<tr><td>Crédit (banque, microfinance)</td><td>crédits hors délégation ou fractionnés, impayés non déclassés, crédits importants sans garantie</td></tr>
<tr><td>LCB-FT</td><td>dossiers KYC périmés, dépôts fractionnés sous le seuil, comptes dormants réactivés, pays à haut risque</td></tr>
<tr><td>Analyse statistique</td><td>loi de Benford, montants ronds, montants et mois atypiques par tiers</td></tr>
</tbody></table>
<p>Les seuils (montant de fractionnement, délai, tolérance) se règlent test par test et s'adaptent au référentiel
de l'organisation : en euros et selon les règles françaises, ou en francs CFA et selon les règles de l'UEMOA.</p>"""),
        dict(id='donnees', h2="Quelles données importer, et comment", html="""
<p>Trois façons d'alimenter l'analyse :</p>
<ul>
<li><strong>Fichiers</strong> : Excel (.xlsx), CSV et FEC (fichier des écritures comptables). Un modèle Excel est
fourni pour chaque type de données (fournisseurs, factures, paiements, grand livre, paie, utilisateurs, crédits…).</li>
<li><strong>Bases de données</strong> en lecture seule : PostgreSQL, MySQL, SQL Server, Oracle, avec des modèles de
requêtes, par exemple pour Sage 100.</li>
<li><strong>Logiciels et espaces de fichiers</strong> : Odoo, Microsoft Business Central, Xero, QuickBooks, Zoho
Books, SFTP, Microsoft 365 (SharePoint, OneDrive) et Google Drive.</li>
</ul>
<p>Chaque fichier importé reçoit une empreinte numérique (SHA-256) : vous pouvez prouver que l'analyse porte sur
les données reçues, sans modification. Les fichiers sont conservés pour une durée réglable, puis supprimés.</p>"""),
        dict(id='resultats', h2="Des résultats exploitables, pas une liste brute", html="""
<p>Pour chaque test, Egalyx indique le critère appliqué, la conséquence possible et une recommandation type. Les
anomalies sont classées par priorité ; vous pouvez tirer un échantillon (aléatoire ou par montant) pour vos
vérifications, documenter vos conclusions, puis transformer une anomalie en <strong>constat d'audit</strong>
rattaché à la mission. L'export Excel reprend l'ensemble, prêt à joindre au dossier.</p>
<p>Si l'IA est activée pour votre organisation, elle peut proposer la rédaction du constat et une synthèse des
résultats ; les tests eux-mêmes restent des règles déterministes.</p>"""),
        dict(id='continu', h2="De l'audit ponctuel à l'audit continu", html="""
<p>Une fois les sources branchées, les mêmes tests peuvent tourner selon un calendrier : chaque nuit, chaque
semaine, chaque mois. Egalyx ne vous signale que les <strong>nouvelles anomalies</strong>, les envoie au contrôle
de deuxième niveau pour vérification et peut alimenter un indicateur de risque (<a href="/indicateurs-risques-kri">KRI</a>)
: nombre de paiements suspects, comptes d'anciens salariés encore actifs, etc. Le contrôle devient permanent sans
charge supplémentaire pour l'équipe.</p>"""),
    ],
    faq=[
        ("Qu'est-ce que l'audit interne automatisé ?",
         "C'est l'application de tests d'audit par logiciel à l'ensemble des opérations d'une période, au lieu d'un "
         "échantillon. L'auditeur se concentre ensuite sur les anomalies détectées."),
        ("Faut-il savoir programmer ?",
         "Non. Les 63 tests sont prêts à l'emploi ; il suffit d'importer un fichier, de vérifier l'association des "
         "colonnes et de choisir les tests."),
        ("Quels formats de fichiers sont acceptés ?",
         "Excel (.xlsx), CSV et FEC. Les anciens fichiers .xls doivent être enregistrés au format .xlsx. Les documents "
         "Word ou PDF ne sont pas des sources de données exploitables."),
        ("Mes données sont-elles modifiées ?",
         "Non. Les connexions aux bases sont en lecture seule et chaque fichier reçoit une empreinte qui prouve qu'il "
         "n'a pas été modifié."),
        ("L'analyse utilise-t-elle l'intelligence artificielle ?",
         "Les tests sont des règles explicites, sans IA, donc reproductibles. L'IA, si elle est activée, aide "
         "seulement à rédiger les constats et la synthèse."),
    ],
    liens=['logiciel-audit-interne-ia', 'indicateurs-risques-kri', 'controle-interne-logiciel-pme', 'conformite-ohada-logiciel'],
    blog=['audit-interne-ia-automatisation', 'methodologie-audit-interne-normes-iso-2026', 'roi-logiciel-audit-interne'],
)

# ---------------------------------------------------------------------------------------------------------------
PAGES['controle-interne-logiciel-pme'] = dict(
    maj=MAJ,
    titre="Logiciel de contrôle interne pour PME | Egalyx",
    description="Contrôle interne simple pour PME : processus, risques, contrôles clés, campagnes de tests, contrôle de 2e niveau et plans d'action dans un seul outil.",
    court="Contrôle interne pour PME",
    resume="Processus, contrôles clés, campagnes de tests et plans d'action pour les PME.",
    h1="Un logiciel de contrôle interne à la mesure des PME et ETI",
    chapo="Décrire ses processus, identifier les risques, définir les contrôles clés, vérifier qu'ils sont faits et "
          "corriger ce qui ne va pas : Egalyx structure le contrôle interne sans en faire une usine à gaz.",
    points=[
        ("Démarrage progressif", "Commencez par un processus (achats, trésorerie, paie) et étendez ensuite."),
        ("Contrôles prouvés", "Chaque contrôle exécuté laisse une preuve : qui, quand, sur quel échantillon."),
        ("Lisible par la direction", "Un tableau de bord montre ce qui est maîtrisé et ce qui ne l'est pas."),
    ],
    sections=[
        dict(id='definition', h2="Le contrôle interne, en pratique", html="""
<p>Le contrôle interne est l'ensemble des dispositifs qui donnent à la direction une assurance raisonnable que
les opérations sont efficaces, que l'information financière est fiable et que les lois sont respectées. Le
référentiel le plus utilisé est le <strong>COSO</strong> (version 2013), qui s'articule autour de cinq composantes :
environnement de contrôle, évaluation des risques, activités de contrôle, information et communication, pilotage.</p>
<p>Dans une PME, l'enjeu n'est pas de produire de la documentation, mais d'éviter les pertes : un paiement en
double, une facture fournisseur fictive, un stock qui disparaît, un client qui ne paie pas. Le bon outil aide à se
concentrer sur ces risques-là.</p>"""),
        dict(id='etapes', h2="Les étapes, outillées dans Egalyx", html="""
<ol>
<li><strong>Décrire les processus</strong> : cartographie des processus et logigrammes interactifs, avec les
acteurs et les points de contrôle.</li>
<li><strong>Identifier les risques</strong> de chaque processus et les évaluer (probabilité, impact) dans la
<a href="/cartographie-risques-logiciel">cartographie des risques</a>.</li>
<li><strong>Définir les contrôles clés</strong> : qui contrôle quoi, à quelle fréquence, avec quelle preuve. Une
bibliothèque de contrôles types sert de point de départ.</li>
<li><strong>Tester les contrôles</strong> par campagnes : autoévaluation par les opérationnels (premier niveau),
puis vérification sur échantillon par le contrôle interne (deuxième niveau).</li>
<li><strong>Corriger</strong> : chaque défaillance ouvre un <a href="/plan-action-correctif-logiciel">plan d'action</a>
avec un responsable et une échéance.</li>
</ol>"""),
        dict(id='niveaux', h2="Premier et deuxième niveau de contrôle", html="""
<p>Le <strong>premier niveau</strong> est réalisé par les équipes elles-mêmes : le comptable vérifie le
rapprochement bancaire, l'acheteur vérifie les trois devis. Egalyx leur envoie les contrôles à réaliser et
recueille la preuve.</p>
<p>Le <strong>deuxième niveau</strong> est réalisé par une fonction indépendante (contrôle interne, conformité,
gestion des risques). Egalyx tire un échantillon, enregistre le résultat de chaque élément testé, calcule le taux
de conformité et ouvre un plan d'action en cas d'anomalie. Les tests de données (doublons, fractionnements, droits
informatiques) peuvent alimenter directement ce contrôle de deuxième niveau.</p>"""),
        dict(id='pme', h2="Pensé pour les équipes réduites", html="""
<p>Dans beaucoup de PME, le contrôle interne repose sur une ou deux personnes, souvent rattachées à la direction
financière. Egalyx en tient compte : rôles et droits simples à configurer, relances automatiques, rapports prêts à
présenter, et une aide intégrée à chaque écran.</p>
<ul>
<li>accès des opérationnels limité aux contrôles qui les concernent ;</li>
<li>gestion des incidents et des signalements internes, y compris par un lien public si vous le souhaitez ;</li>
<li>plans de continuité d'activité (PCA) et plans qualité dans le même outil ;</li>
<li>référentiel adapté au pays : France (euro) ou Côte d'Ivoire et zone UEMOA (franc CFA).</li>
</ul>"""),
    ],
    faq=[
        ("Une PME a-t-elle besoin d'un logiciel de contrôle interne ?",
         "Pas forcément au départ. Le besoin apparaît quand les contrôles se multiplient, que plusieurs personnes "
         "interviennent ou qu'il faut prouver le dispositif à un auditeur, un banquier ou un actionnaire."),
        ("Quelle différence entre contrôle interne et audit interne ?",
         "Le contrôle interne est l'ensemble des dispositifs de maîtrise mis en œuvre au quotidien. L'audit interne "
         "évalue, de façon indépendante et périodique, si ces dispositifs fonctionnent."),
        ("Combien de temps pour démarrer ?",
         "Un premier processus peut être décrit, ses risques évalués et ses contrôles programmés en quelques jours. "
         "Les modèles Excel permettent de reprendre l'existant."),
        ("Le logiciel suit-il le référentiel COSO ?",
         "Oui, la démarche (risques, activités de contrôle, pilotage) s'inscrit dans les composantes du COSO 2013."),
    ],
    liens=['cartographie-risques-logiciel', 'plan-action-correctif-logiciel', 'audit-interne-automatise', 'gestion-risques-entreprise-ia'],
    blog=['guide-mise-en-place-controle-interne', 'guide-choix-logiciel-controle-interne',
          'audit-interne-logiciel-pme-avantages-2026', 'audit-interne-3-lignes-defense'],
)

# ---------------------------------------------------------------------------------------------------------------
PAGES['gestion-risques-entreprise-ia'] = dict(
    maj=MAJ,
    titre="Logiciel de gestion des risques d'entreprise | Egalyx",
    description="Identifiez, évaluez et suivez les risques : cartographie, risque brut et résiduel, appétence, KRI, incidents et plans d'action, avec l'aide de l'IA.",
    court="Gestion des risques d'entreprise",
    resume="Identification, évaluation, appétence, KRI et incidents dans un même référentiel.",
    h1="Gestion des risques d'entreprise : un référentiel vivant, pas un tableau figé",
    chapo="Egalyx relie la cartographie des risques, les contrôles, les incidents, les indicateurs et les plans "
          "d'action. Quand un incident survient ou qu'un indicateur se dégrade, le risque concerné le montre.",
    points=[
        ("Référentiel unique", "Une seule liste de risques, partagée par le contrôle interne, l'audit et la conformité."),
        ("Mise à jour continue", "Incidents, KRI et résultats de contrôles alimentent l'évaluation."),
        ("Décision éclairée", "Appétence au risque et risques hors limites présentés au comité."),
    ],
    sections=[
        dict(id='demarche', h2="Une démarche alignée sur l'ISO 31000", html="""
<p>La norme <strong>ISO 31000:2018</strong> décrit le processus de management du risque : établir le contexte,
identifier, analyser et évaluer les risques, les traiter, puis surveiller et communiquer. Egalyx suit ce cycle :</p>
<ul>
<li><strong>identifier</strong> les risques par processus, entité ou objectif, avec une bibliothèque de catégories
paramétrable ;</li>
<li><strong>analyser</strong> la probabilité et l'impact, d'abord en risque brut (sans contrôle), puis en risque
résiduel (après prise en compte des contrôles existants) ;</li>
<li><strong>traiter</strong> : accepter, réduire, transférer ou éviter, avec un plan d'action pour les risques à réduire ;</li>
<li><strong>surveiller</strong> par des indicateurs de risque et par le suivi des incidents.</li>
</ul>"""),
        dict(id='appetence', h2="Appétence au risque et seuils de tolérance", html="""
<p>Définir l'appétence au risque, c'est dire quel niveau de risque l'organisation accepte pour atteindre ses
objectifs. Dans Egalyx, elle se traduit en seuils sur l'échelle de cotation et sur les indicateurs : un risque
résiduel au-delà du seuil, ou un KRI en zone rouge, est signalé automatiquement et remonte dans le rapport au
comité.</p>"""),
        dict(id='incidents', h2="Incidents et signalements : la réalité du terrain", html="""
<p>Une cartographie qui n'est jamais confrontée aux incidents réels devient vite théorique. Egalyx enregistre les
signalements (par les utilisateurs, ou par des personnes extérieures via un lien public sécurisé), les trie et les
convertit en incidents qualifiés : risque concerné, contrôle défaillant, perte, escalade. L'historique des
incidents alimente la réévaluation de la probabilité.</p>"""),
        dict(id='ia', h2="L'IA au service de l'analyse des risques", html="""
<p>Lorsque l'IA est activée, elle aide à :</p>
<ul>
<li>proposer des risques et des contrôles pour un processus décrit en quelques lignes ;</li>
<li>rédiger l'analyse d'une cartographie : concentrations, risques sans contrôle, incohérences de cotation ;</li>
<li>commenter l'évolution d'un indicateur de risque.</li>
</ul>
<p>Le score de la cartographie est calculé par le logiciel, pas par l'IA, et chaque proposition est soumise à
validation. L'IA se désactive en un clic pour une organisation qui n'en veut pas.</p>"""),
        dict(id='domaines', h2="Tous les risques au même endroit", html="""
<p>Risques opérationnels, financiers, de conformité, informatiques et cyber, fournisseurs, continuité d'activité :
chaque famille a ses outils (évaluation des tiers et LCB-FT, plans de continuité, veille réglementaire), mais
toutes partagent le même référentiel. Le comité voit enfin un seul tableau, et l'audit interne bâtit son plan à
partir de la même base.</p>"""),
    ],
    faq=[
        ("Qu'est-ce que la gestion des risques d'entreprise (ERM) ?",
         "C'est une démarche globale qui identifie, évalue et traite l'ensemble des risques pouvant affecter les "
         "objectifs de l'entreprise, au lieu de les gérer service par service."),
        ("Quelle différence entre risque brut et risque résiduel ?",
         "Le risque brut est évalué sans tenir compte des contrôles ; le risque résiduel est le niveau qui subsiste "
         "une fois les contrôles existants pris en compte."),
        ("Egalyx est-il conforme à l'ISO 31000 ?",
         "L'ISO 31000 est une norme de lignes directrices, sans certification. Egalyx en suit le processus "
         "(identification, analyse, évaluation, traitement, surveillance)."),
        ("L'IA décide-t-elle de la cotation des risques ?",
         "Non. La cotation est saisie et validée par vos équipes ; l'IA propose, elle ne décide pas."),
    ],
    liens=['cartographie-risques-logiciel', 'indicateurs-risques-kri', 'controle-interne-logiciel-pme', 'gouvernance-entreprise-logiciel'],
    blog=['guide-complet-gestion-risques-entreprise-2026', 'gestion-risques-ia-entreprise',
          'mise-en-place-systeme-gestion-risques-iso-31000-2026'],
)

# ---------------------------------------------------------------------------------------------------------------
PAGES['cartographie-risques-logiciel'] = dict(
    maj=MAJ,
    titre="Logiciel de cartographie des risques | Egalyx",
    description="Construisez votre cartographie des risques : matrice probabilité × impact, risque brut et résiduel, import Excel et présentation au comité.",
    court="Cartographie des risques",
    resume="Matrice probabilité × impact, risque brut et résiduel, import depuis Excel.",
    h1="Logiciel de cartographie des risques : de la matrice à la décision",
    chapo="La cartographie des risques est le point de départ du contrôle interne et du plan d'audit. Egalyx la "
          "rend collaborative, à jour et directement reliée aux contrôles et aux plans d'action.",
    points=[
        ("Reprise de l'existant", "Votre cartographie Excel s'importe avec un modèle fourni."),
        ("Brut et résiduel", "L'effet des contrôles sur chaque risque est visible et justifié."),
        ("Prête pour le comité", "Matrice, top des risques et évolution d'une période à l'autre."),
    ],
    sections=[
        dict(id='quoi', h2="Qu'est-ce qu'une cartographie des risques ?", html="""
<p>Une cartographie des risques recense les événements qui pourraient empêcher l'organisation d'atteindre ses
objectifs, et les positionne selon deux axes : la <strong>probabilité</strong> qu'ils surviennent et leur
<strong>impact</strong> s'ils surviennent. Le résultat le plus connu est la matrice (souvent 4 × 4 ou 5 × 5), où
les risques majeurs apparaissent en haut à droite.</p>
<p>Elle sert à hiérarchiser : où mettre les contrôles, où envoyer l'audit, quels risques présenter au conseil.
Elle n'a de valeur que si elle est tenue à jour, ce qui est difficile dans un fichier partagé.</p>"""),
        dict(id='construire', h2="Construire la cartographie dans Egalyx", html="""
<ol>
<li><strong>Choisir l'échelle</strong> de cotation (nombre de niveaux, libellés, critères d'impact financier,
réglementaire, d'image, humain).</li>
<li><strong>Recenser les risques</strong> par processus ou par entité, avec leur cause et leur conséquence. Les
ateliers peuvent être préparés par questionnaire en ligne.</li>
<li><strong>Coter le risque brut</strong>, puis rattacher les contrôles existants et coter le
<strong>risque résiduel</strong>.</li>
<li><strong>Décider du traitement</strong> et ouvrir les plans d'action nécessaires.</li>
<li><strong>Présenter</strong> la matrice et le top des risques au comité, et suivre l'évolution d'une campagne à
l'autre.</li>
</ol>"""),
        dict(id='processus', h2="Cartographie des risques et cartographie des processus", html="""
<p>Les deux se complètent. La <strong>cartographie des processus</strong> décrit comment l'organisation
fonctionne (macro-processus, processus, activités) ; la cartographie des risques décrit ce qui peut mal tourner.
Dans Egalyx, chaque risque peut être rattaché à son processus et aux logigrammes correspondants, ce qui permet
d'identifier les étapes sans contrôle.</p>"""),
        dict(id='vivante', h2="Une cartographie qui vit entre deux mises à jour", html="""
<p>Entre deux campagnes annuelles, la réalité change. Egalyx relie chaque risque à ses
<a href="/indicateurs-risques-kri">indicateurs (KRI)</a>, aux incidents déclarés, aux résultats des contrôles et
aux constats d'audit. Un risque coté « faible » mais touché par trois incidents en un trimestre se remarque.
L'analyse de la cartographie (score, risques sans contrôle, cotations incohérentes) est calculée par le logiciel ;
l'IA, si elle est activée, en rédige la lecture.</p>"""),
    ],
    faq=[
        ("Quelle matrice utiliser : 4 × 4 ou 5 × 5 ?",
         "Les deux sont courantes. Une échelle à 4 niveaux évite la tentation du niveau moyen ; une échelle à 5 "
         "niveaux donne plus de nuance. Egalyx permet de choisir et d'adapter les libellés."),
        ("Peut-on importer une cartographie Excel existante ?",
         "Oui. Un modèle Excel est fourni ; les colonnes sont reconnues et chaque ligne devient un risque."),
        ("À quelle fréquence mettre à jour la cartographie ?",
         "Une revue complète par an est la pratique courante, complétée par une mise à jour au fil de l'eau dès "
         "qu'un incident, un nouveau projet ou une nouvelle réglementation le justifie."),
        ("Qui doit participer à la cartographie ?",
         "Les responsables opérationnels, qui connaissent les risques de leurs activités, avec l'appui de la "
         "fonction risques ou contrôle interne, puis la validation de la direction."),
    ],
    liens=['gestion-risques-entreprise-ia', 'controle-interne-logiciel-pme', 'indicateurs-risques-kri', 'logiciel-audit-interne-ia'],
    blog=['cartographie-risques-entreprise-methode-2026', 'guide-complet-gestion-risques-entreprise-2026'],
)

# ---------------------------------------------------------------------------------------------------------------
PAGES['indicateurs-risques-kri'] = dict(
    maj=MAJ,
    titre="KRI : indicateurs clés de risque, définition et exemples",
    description="Qu'est-ce qu'un KRI ? Définition, différence avec un KPI, exemples par domaine, seuils d'alerte "
                "et suivi automatique des indicateurs de risque avec Egalyx.",
    court="Indicateurs de risque (KRI)",
    resume="Définition, exemples, seuils et collecte automatique des indicateurs de risque.",
    h1="KRI : les indicateurs clés de risque, définition, exemples et suivi",
    chapo="Un KRI (Key Risk Indicator) mesure l'évolution d'un risque avant qu'il ne se réalise. Voici comment les "
          "choisir, fixer leurs seuils et les suivre sans ressaisie, avec des exemples concrets par domaine.",
    points=[
        ("Signal avancé", "Un bon KRI bouge avant l'incident, pas après."),
        ("Seuils clairs", "Vert, orange, rouge : chaque zone déclenche une action définie."),
        ("Collecte automatique", "Les valeurs arrivent de vos outils, sans saisie manuelle."),
    ],
    sections=[
        dict(id='definition', h2="Qu'est-ce qu'un KRI ?", html="""
<p>Un <strong>indicateur clé de risque</strong> (KRI, pour <em>Key Risk Indicator</em>) est une mesure chiffrée
qui renseigne sur l'exposition à un risque et sur son évolution. Il est rattaché à un risque de la cartographie
et comparé à des seuils : tant qu'il reste dans la zone acceptable, le risque est jugé maîtrisé ; s'il franchit un
seuil, une action est attendue.</p>
<p>Sa qualité principale est d'être <strong>avancé</strong> : il doit alerter avant que le dommage ne survienne.
Le nombre de fraudes constatées est un indicateur d'incident ; le nombre de modifications de coordonnées
bancaires de fournisseurs sans double validation est un KRI.</p>"""),
        dict(id='kpi', h2="KRI, KPI, KCI : quelles différences ?", html="""
<table class="pc-table">
<thead><tr><th scope="col">Indicateur</th><th scope="col">Ce qu'il mesure</th><th scope="col">Exemple</th></tr></thead>
<tbody>
<tr><td>KPI (performance)</td><td>l'atteinte d'un objectif</td><td>chiffre d'affaires mensuel, délai moyen de livraison</td></tr>
<tr><td>KRI (risque)</td><td>l'exposition à un risque et sa tendance</td><td>taux de rotation du personnel clé, part des achats hors contrat</td></tr>
<tr><td>KCI (contrôle)</td><td>le bon fonctionnement d'un contrôle</td><td>part des rapprochements bancaires faits dans les délais</td></tr>
</tbody></table>
<p>Un même chiffre peut servir les deux : un délai de paiement client qui s'allonge est un KPI pour le commercial
et un KRI pour le trésorier. L'important est de le relier explicitement au risque qu'il surveille.</p>"""),
        dict(id='exemples', h2="Exemples de KRI par domaine", html="""
<table class="pc-table">
<thead><tr><th scope="col">Domaine</th><th scope="col">Exemples d'indicateurs de risque</th></tr></thead>
<tbody>
<tr><td>Achats et fraude</td><td>part des achats sans bon de commande ; nombre de RIB fournisseurs modifiés dans le mois ; paiements en double détectés</td></tr>
<tr><td>Finance</td><td>délai moyen de paiement des clients ; part des créances échues de plus de 90 jours ; comptes d'attente non soldés</td></tr>
<tr><td>Ressources humaines</td><td>rotation du personnel sur les postes clés ; postes clés sans remplaçant identifié ; heures supplémentaires</td></tr>
<tr><td>Informatique et cyber</td><td>comptes actifs d'anciens salariés ; correctifs de sécurité en retard ; incidents de sécurité ouverts</td></tr>
<tr><td>Conformité</td><td>dossiers clients (KYC) périmés ; formations obligatoires non suivies ; alertes éthiques non traitées</td></tr>
<tr><td>Banque et microfinance</td><td>taux de créances en souffrance ; crédits accordés hors délégation ; concentration sur les 20 premiers emprunteurs</td></tr>
<tr><td>Audit et contrôle</td><td>recommandations en retard de plus de 90 jours ; part des contrôles clés non réalisés</td></tr>
</tbody></table>"""),
        dict(id='choisir', h2="Comment choisir et paramétrer un KRI", html="""
<ul>
<li><strong>Un risque, peu d'indicateurs</strong> : deux ou trois KRI bien choisis valent mieux que vingt suivis
sans action.</li>
<li><strong>Mesurable sans effort</strong> : si la donnée exige une collecte manuelle laborieuse, l'indicateur ne
sera pas tenu.</li>
<li><strong>Des seuils justifiés</strong> : la zone verte, la zone d'alerte et la zone de dépassement découlent de
l'appétence au risque, pas d'une intuition.</li>
<li><strong>Une action associée</strong> : pour chaque seuil, qui est prévenu et que fait-il ?</li>
<li><strong>Une périodicité adaptée</strong> au rythme du risque : quotidienne pour la trésorerie, trimestrielle
pour la rotation du personnel.</li>
</ul>"""),
        dict(id='egalyx', h2="Suivre ses KRI avec Egalyx", html="""
<p>Dans Egalyx, chaque KRI est rattaché à un risque et possède sa fiche : valeur actuelle, jauge, seuils,
historique et graphique d'évolution. Les valeurs peuvent être saisies, mais surtout <strong>collectées
automatiquement</strong> :</p>
<ul>
<li>depuis vos outils, grâce à des connecteurs (Jira, ServiceNow, Zendesk, Freshdesk, GitHub, GitLab, HubSpot,
Odoo, PagerDuty, Datadog, Google Sheets, Airtable) ;</li>
<li>depuis les <a href="/audit-interne-automatise">tests d'analyse de données</a> programmés : nombre de
paiements suspects, de comptes orphelins, d'écritures hors horaires.</li>
</ul>
<p>Le franchissement d'un seuil déclenche une notification et apparaît dans le tableau de bord et le rapport au
comité. Si l'IA est activée, elle peut commenter l'évolution d'un indicateur à la demande.</p>"""),
    ],
    faq=[
        ("Que signifie KRI ?",
         "KRI signifie Key Risk Indicator, en français indicateur clé de risque. C'est une mesure qui suit "
         "l'exposition à un risque et alerte quand elle dépasse un seuil."),
        ("Quelle est la différence entre un KRI et un KPI ?",
         "Le KPI mesure la performance par rapport à un objectif ; le KRI mesure l'exposition à un risque. Un "
         "même chiffre peut jouer les deux rôles selon le point de vue."),
        ("Combien de KRI faut-il suivre ?",
         "Il n'y a pas de nombre idéal, mais deux ou trois indicateurs par risque majeur suffisent généralement. "
         "Au-delà, les indicateurs sont rarement suivis d'effet."),
        ("Comment fixer les seuils d'un KRI ?",
         "À partir de l'appétence au risque définie par la direction, de l'historique de l'indicateur et des "
         "obligations réglementaires. Les seuils se revoient au moins une fois par an."),
        ("Peut-on alimenter les KRI automatiquement ?",
         "Oui. Egalyx relève les valeurs dans vos outils par connecteur et à partir des tests d'analyse de données "
         "programmés, puis compare chaque valeur aux seuils."),
    ],
    liens=['gestion-risques-entreprise-ia', 'cartographie-risques-logiciel', 'audit-interne-automatise', 'gouvernance-entreprise-logiciel'],
    blog=['indicateurs-risques-kri-guide', 'guide-complet-gestion-risques-entreprise-2026'],
)

# ---------------------------------------------------------------------------------------------------------------
PAGES['plan-action-correctif-logiciel'] = dict(
    maj=MAJ,
    titre="Logiciel de suivi des plans d'action correctifs | Egalyx",
    description="Suivez recommandations d'audit et plans d'action : responsables, échéances, relances automatiques, preuves de mise en œuvre et reporting au comité.",
    court="Plans d'action et recommandations",
    resume="Responsables, échéances, relances, preuves et registre des recommandations.",
    h1="Plans d'action correctifs : du constat à la preuve de mise en œuvre",
    chapo="Un audit ne sert à rien si ses recommandations ne sont pas appliquées. Egalyx suit chaque action jusqu'à "
          "sa clôture, avec la preuve, et montre au comité ce qui est en retard.",
    points=[
        ("Un registre unique", "Audit, contrôle interne, incidents, conformité : toutes les actions au même endroit."),
        ("Relances automatiques", "Avant et après l'échéance, sans tableur ni courriel manuel."),
        ("Clôture prouvée", "Une action n'est close qu'avec sa preuve, vérifiée par l'émetteur."),
    ],
    sections=[
        dict(id='enjeu', h2="Le suivi des recommandations, point faible de nombreux dispositifs", html="""
<p>Les recommandations naissent partout : missions d'audit, contrôles de deuxième niveau, incidents, inspections
des régulateurs, commissaires aux comptes. Elles finissent souvent dans des fichiers différents, avec des statuts
déclaratifs (« en cours ») jamais vérifiés. Au moment du rapport annuel, personne ne sait vraiment ce qui a été
fait.</p>
<p>Les Normes mondiales d'audit interne demandent pourtant au responsable de l'audit de suivre la mise en œuvre
des plans d'action et d'en rendre compte. Le suivi doit donc être structuré, tracé et vérifiable.</p>"""),
        dict(id='cycle', h2="Le cycle de vie d'une action dans Egalyx", html="""
<ol>
<li><strong>Création</strong> depuis un constat d'audit, une anomalie de contrôle, un incident ou une saisie
directe, avec le risque concerné.</li>
<li><strong>Engagement</strong> : l'audité propose l'action, le responsable et l'échéance ; l'émetteur valide.</li>
<li><strong>Exécution</strong> : avancement, commentaires et pièces justificatives ; jalons visibles sur un
diagramme de Gantt.</li>
<li><strong>Relances</strong> automatiques avant l'échéance et en cas de retard, avec escalade possible.</li>
<li><strong>Clôture</strong> : la preuve est déposée, l'émetteur la vérifie et clôt, ou rouvre l'action.</li>
</ol>"""),
        dict(id='registre', h2="Registre des recommandations et reporting", html="""
<p>Le registre des recommandations rassemble toutes les actions avec leur origine, leur priorité, leur échéance et
leur statut. Des filtres permettent de voir en un instant les actions en retard par direction, les recommandations
critiques ouvertes ou celles qui ont été reportées plusieurs fois.</p>
<p>Le rapport au comité d'audit reprend automatiquement le taux de mise en œuvre, les retards significatifs et
les risques encore exposés. Les audités disposent de leur propre vue, limitée à leurs actions.</p>"""),
        dict(id='bonnes', h2="Bonnes pratiques pour des plans d'action efficaces", html="""
<ul>
<li>une action = un responsable nommé (pas un service) et une date ;</li>
<li>une action mesurable : « mettre en place une double validation des RIB fournisseurs » plutôt que
« renforcer les contrôles » ;</li>
<li>une preuve définie dès la création (procédure signée, capture du paramétrage, échantillon testé) ;</li>
<li>un report justifié et validé, jamais automatique ;</li>
<li>une vérification de l'efficacité, quelques mois après la clôture, pour les actions majeures.</li>
</ul>"""),
    ],
    faq=[
        ("Qu'est-ce qu'un plan d'action correctif ?",
         "C'est l'ensemble des actions décidées pour corriger une défaillance constatée (audit, contrôle, incident), "
         "avec pour chacune un responsable, une échéance et une preuve attendue."),
        ("Les audités peuvent-ils mettre à jour leurs actions eux-mêmes ?",
         "Oui. Chaque responsable voit ses actions, renseigne l'avancement et dépose les preuves ; l'émetteur valide "
         "la clôture."),
        ("Peut-on regrouper les actions de plusieurs origines ?",
         "Oui. Audit interne, contrôle interne, incidents et conformité alimentent le même registre, avec un filtre "
         "par origine."),
        ("Comment présenter le suivi au comité d'audit ?",
         "Le rapport de synthèse calcule le taux de mise en œuvre et liste les retards significatifs, sans "
         "consolidation manuelle."),
    ],
    liens=['logiciel-audit-interne-ia', 'controle-interne-logiciel-pme', 'gouvernance-entreprise-logiciel', 'audit-interne-automatise'],
    blog=['plan-action-correctif-audit', 'audit-interne-frequence-planification'],
)

# ---------------------------------------------------------------------------------------------------------------
PAGES['conformite-ohada-logiciel'] = dict(
    maj=MAJ,
    titre="Logiciel de conformité OHADA et UEMOA | Egalyx",
    description="Audit et conformité pour l'espace OHADA et l'UEMOA : SYSCOHADA révisé, franc CFA, LCB-FT et CENTIF, exigences de la Commission bancaire.",
    court="Conformité OHADA et UEMOA",
    resume="SYSCOHADA, franc CFA, LCB-FT et réglementation bancaire de l'UMOA.",
    h1="Conformité OHADA et UEMOA : un logiciel qui parle votre réglementation",
    chapo="Egalyx propose un profil réglementaire « Côte d'Ivoire / UEMOA » : franc CFA, plan comptable SYSCOHADA, "
          "jours fériés, seuils et références adaptés. Les tests, les rapports et l'IA s'y conforment.",
    points=[
        ("Profil UEMOA", "Devise, fuseau horaire, comptes sensibles et jours fériés réglés pour la zone."),
        ("Références locales", "SYSCOHADA révisé, CENTIF, Commission bancaire de l'UMOA, ARTCI."),
        ("Même outil qu'en France", "Un groupe présent des deux côtés garde un référentiel commun."),
    ],
    sections=[
        dict(id='cadre', h2="Le cadre : OHADA, UEMOA et réglementations sectorielles", html="""
<p>L'<strong>OHADA</strong> (Organisation pour l'harmonisation en Afrique du droit des affaires) réunit
17 États membres autour d'actes uniformes directement applicables. Deux concernent au premier chef le contrôle :
l'acte uniforme relatif au droit des sociétés commerciales, qui fixe notamment le rôle du commissaire aux comptes,
et l'acte uniforme relatif au droit comptable et à l'information financière, qui a instauré le
<strong>SYSCOHADA révisé</strong>, applicable depuis 2018.</p>
<p>Dans les huit pays de l'<strong>UEMOA</strong>, s'ajoutent la réglementation de la BCEAO et, pour les
banques et établissements financiers, les circulaires de la Commission bancaire de l'UMOA sur la gouvernance, le
contrôle interne et la gestion des risques. La lutte contre le blanchiment et le financement du terrorisme
(LCB-FT) repose sur une loi uniforme transposée dans chaque État, avec une CENTIF nationale comme cellule de
renseignement financier.</p>"""),
        dict(id='profil', h2="Le profil réglementaire Côte d'Ivoire / UEMOA", html="""
<p>Chaque organisation cliente d'Egalyx se voit attribuer un profil réglementaire. Avec le profil UEMOA :</p>
<ul>
<li>montants en <strong>francs CFA</strong>, fuseau horaire d'Abidjan ;</li>
<li>comptes sensibles définis selon le plan <strong>SYSCOHADA</strong> pour les tests sur les écritures manuelles ;</li>
<li>jours fériés ivoiriens pris en compte dans les tests de paiements et d'écritures hors jours ouvrés (les fêtes
religieuses à date variable s'ajoutent chaque année) ;</li>
<li>seuils de fractionnement et de déclaration exprimés en francs CFA ;</li>
<li>références citées dans les recommandations et par l'IA : CENTIF, Commission bancaire, ARTCI pour les données
personnelles (loi ivoirienne n° 2013-450 du 19 juin 2013).</li>
</ul>"""),
        dict(id='lcb', h2="LCB-FT : connaissance des tiers et détection", html="""
<p>Le module Tiers et LCB-FT tient la fiche de chaque client ou fournisseur (identification, pays, personne
politiquement exposée, bénéficiaires effectifs) et calcule un score de vigilance transparent, à partir des listes
du GAFI et de critères modifiables. Le criblage contre les listes de sanctions (ONU, UE, OFAC, liste nationale)
est confirmé ou écarté par un humain, avec trace.</p>
<p>Côté opérations, l'<a href="/audit-interne-automatise">analyse de données</a> détecte les dossiers KYC
périmés, les dépôts fractionnés sous le seuil de déclaration, les comptes dormants réactivés et les opérations avec
des pays à haut risque.</p>"""),
        dict(id='finance', h2="Banques, microfinance et assurances", html="""
<p>Pour les établissements de crédit et les systèmes financiers décentralisés, Egalyx ajoute des tests sur le
portefeuille : crédits accordés hors délégation ou fractionnés pour rester sous la délégation, crédits au
personnel, impayés non déclassés, crédits importants sans garantie. Le contrôle de deuxième niveau, la cartographie
des risques et le rapport au conseil répondent aux attentes du superviseur en matière de dispositif de contrôle
interne.</p>"""),
    ],
    faq=[
        ("Egalyx est-il adapté au SYSCOHADA révisé ?",
         "Oui. Avec le profil UEMOA, les comptes sensibles et les tests comptables s'appuient sur le plan SYSCOHADA, "
         "et le grand livre s'importe depuis Excel, CSV ou votre logiciel comptable."),
        ("Quels pays sont concernés par le profil UEMOA ?",
         "Les huit pays de l'UEMOA : Bénin, Burkina Faso, Côte d'Ivoire, Guinée-Bissau, Mali, Niger, Sénégal et Togo. "
         "Les autres pays de l'OHADA bénéficient des mêmes références comptables."),
        ("Le logiciel gère-t-il le franc CFA ?",
         "Oui, la devise de l'organisation est réglée par son profil : franc CFA pour l'UEMOA, euro pour la France."),
        ("Un groupe présent en France et en Côte d'Ivoire peut-il tout gérer ?",
         "Oui. Chaque organisation a son profil (UEMOA ou France), dans le même outil."),
    ],
    liens=['cote-divoire', 'audit-interne-automatise', 'conformite-rgpd-logiciel', 'logiciel-audit-interne-ia'],
    blog=['logiciel-gestion-risques-ohada-afrique', 'mise-en-conformite-ohada-entreprises-ivoiriennes'],
)

# ---------------------------------------------------------------------------------------------------------------
PAGES['conformite-rgpd-logiciel'] = dict(
    maj=MAJ,
    titre="Logiciel de conformité RGPD et gestion des risques | Egalyx",
    description="Pilotez la conformité RGPD : risques sur les données, questionnaires, sous-traitants, contrôle des habilitations, plans d'action et veille.",
    court="Conformité RGPD",
    resume="Risques sur les données, sous-traitants, habilitations et plans d'action RGPD.",
    h1="Conformité RGPD : la piloter comme un dispositif de contrôle interne",
    chapo="La conformité au RGPD ne se résume pas à un registre. Elle demande d'évaluer les risques, de contrôler "
          "les accès, de suivre les sous-traitants et de corriger les écarts. Egalyx apporte ces outils.",
    points=[
        ("Risques sur les données", "Les risques RGPD rejoignent la cartographie générale."),
        ("Contrôles prouvés", "Accès, durées de conservation, sous-traitants : des preuves datées."),
        ("France et Côte d'Ivoire", "RGPD et CNIL, ou loi de 2013 et ARTCI, selon le profil."),
    ],
    sections=[
        dict(id='obligations', h2="Ce que le RGPD exige concrètement", html="""
<p>Le règlement général sur la protection des données (règlement UE 2016/679), applicable depuis le
25 mai 2018, impose notamment de tenir un registre des traitements, de minimiser les données collectées, de
limiter leur durée de conservation, de sécuriser les accès, d'encadrer les sous-traitants par contrat, de réaliser
une analyse d'impact pour les traitements à risque et de notifier les violations de données à la CNIL dans les
72 heures.</p>
<p>Surtout, il impose de <strong>pouvoir démontrer</strong> cette conformité (principe de responsabilité). Les
sanctions peuvent atteindre 20 millions d'euros ou 4 % du chiffre d'affaires annuel mondial.</p>"""),
        dict(id='outils', h2="Ce qu'Egalyx apporte à votre démarche RGPD", html="""
<ul>
<li><strong>Cartographie des risques</strong> sur les données personnelles, reliée au reste des risques de
l'organisation ;</li>
<li><strong>questionnaires</strong> d'autoévaluation des services et d'évaluation des sous-traitants, avec
relances et consolidation des réponses ;</li>
<li><strong>campagnes de contrôle</strong> : revue des droits d'accès, purge des données échues, clauses
contractuelles des sous-traitants ;</li>
<li><strong>tests d'habilitations</strong> par analyse de données : comptes actifs de personnes parties, comptes
génériques, comptes inutilisés, cumuls de droits ;</li>
<li><strong>signalements et incidents</strong>, pour tracer une violation de données de sa détection à sa
notification ;</li>
<li><strong>plans d'action</strong> et <strong>veille réglementaire</strong> pour suivre les écarts et les
nouvelles recommandations de la CNIL.</li>
</ul>
<p>Egalyx ne remplace pas votre registre des traitements ni le travail de votre délégué à la protection des
données : il outille le contrôle de la conformité et la preuve.</p>"""),
        dict(id='securite', h2="Un outil lui-même conçu pour protéger vos données", html="""
<p>Un logiciel de conformité doit être exemplaire. Egalyx cloisonne les données de chaque organisation, chiffre
les informations sensibles (identifiants de connexion aux sources de données, notamment), propose la double
authentification et l'authentification unique (SSO), et trace les actions des utilisateurs. Egalyx est certifié ISO 27001, SOC 2 Type II
et HDS. Les détails sont
présentés sur la page <a href="/securite">Sécurité</a>.</p>"""),
        dict(id='ci', h2="En Côte d'Ivoire : la loi de 2013 et l'ARTCI", html="""
<p>Les organisations ivoiriennes relèvent de la loi n° 2013-450 du 19 juin 2013 relative à la protection des
données à caractère personnel, dont l'autorité de contrôle est l'ARTCI. Avec le profil réglementaire UEMOA,
les références et recommandations d'Egalyx citent ce cadre plutôt que la CNIL.</p>"""),
    ],
    faq=[
        ("Egalyx tient-il le registre des traitements RGPD ?",
         "Non, Egalyx n'est pas un outil de registre. Il sert à évaluer les risques, contrôler les mesures, suivre "
         "les sous-traitants et les écarts, et conserver les preuves de conformité."),
        ("Comment contrôler les habilitations dans le cadre du RGPD ?",
         "En important la liste des comptes utilisateurs et celle du personnel : Egalyx détecte les comptes de "
         "personnes parties, les comptes génériques et inutilisés et les cumuls de droits incompatibles."),
        ("Quel est le délai de notification d'une violation de données ?",
         "Le RGPD impose de notifier la CNIL dans les 72 heures après en avoir pris connaissance, lorsque la "
         "violation présente un risque pour les personnes."),
        ("Le RGPD s'applique-t-il en Côte d'Ivoire ?",
         "Il s'applique aux organisations qui traitent des données de personnes situées dans l'Union européenne. "
         "En Côte d'Ivoire, la loi n° 2013-450 et l'ARTCI encadrent la protection des données."),
    ],
    liens=['controle-interne-logiciel-pme', 'gestion-risques-entreprise-ia', 'conformite-ohada-logiciel', 'audit-interne-automatise'],
    blog=['comment-choisir-logiciel-audit-2026', 'guide-complet-gestion-risques-entreprise-2026'],
)

# ---------------------------------------------------------------------------------------------------------------
PAGES['gouvernance-entreprise-logiciel'] = dict(
    maj=MAJ,
    titre="Logiciel GRC : gouvernance, risques, conformité | Egalyx",
    description="Plateforme GRC pour la direction et le comité d'audit : trois lignes, appétence au risque, tableau de bord, rapport au conseil et alertes.",
    court="Gouvernance et GRC",
    resume="Trois lignes, comité d'audit, appétence au risque et rapport au conseil.",
    h1="Gouvernance, risques et conformité : une plateforme GRC pour le comité et la direction",
    chapo="La gouvernance demande une vue d'ensemble fiable. Egalyx relie le travail des opérationnels, du contrôle "
          "interne, de la conformité et de l'audit, et en tire un rapport clair pour le comité d'audit et le conseil.",
    points=[
        ("Trois lignes", "Chaque ligne a ses outils, toutes partagent le même référentiel."),
        ("Rapport en un clic", "Synthèse au comité produite à partir des chiffres, vérifiable."),
        ("Multi-entités", "Filiales et pays, chacun avec son profil réglementaire."),
    ],
    sections=[
        dict(id='grc', h2="Qu'est-ce qu'une plateforme GRC ?", html="""
<p>GRC signifie <strong>gouvernance, risques et conformité</strong>. Une plateforme GRC réunit dans un même
système ce qui est souvent dispersé : la cartographie des risques, le contrôle interne, la conformité
réglementaire, l'audit interne, les incidents et les plans d'action. L'intérêt est de parler d'une seule voix au
comité, sur la base d'informations cohérentes.</p>"""),
        dict(id='lignes', h2="Le modèle des trois lignes, outillé", html="""
<p>Le modèle des trois lignes de l'IIA (mis à jour en 2020) distingue :</p>
<ul>
<li>la <strong>première ligne</strong>, le management opérationnel, qui possède et gère les risques ; dans Egalyx,
elle réalise ses autoévaluations et ses contrôles de premier niveau, déclare les incidents et met en œuvre les
actions ;</li>
<li>la <strong>deuxième ligne</strong> (gestion des risques, contrôle interne, conformité), qui fournit l'expertise
et la surveillance : cartographie, KRI, contrôle de deuxième niveau, LCB-FT, veille réglementaire ;</li>
<li>la <strong>troisième ligne</strong>, l'audit interne, qui apporte une assurance indépendante : univers d'audit,
missions, analyse de données, suivi des recommandations.</li>
</ul>
<p>Les droits d'accès suivent ce modèle : chacun voit ce qui le concerne, et l'audit interne conserve son
indépendance.</p>"""),
        dict(id='comite', h2="Pour le comité d'audit et le conseil", html="""
<p>Le rapport au comité rassemble, en un document imprimable : le tableau de bord stratégique, l'état d'avancement
du plan d'audit, les constats majeurs, les plans d'action en retard, les risques au-delà de l'appétence, la
situation LCB-FT et l'activité du dispositif d'alerte. La synthèse rédigée est produite par des règles explicites à
partir des chiffres : deux personnes qui la relancent obtiennent le même texte.</p>"""),
        dict(id='ethique', h2="Éthique, alerte et culture du risque", html="""
<p>Une bonne gouvernance s'appuie sur un dispositif d'alerte crédible. Egalyx permet de recueillir des
signalements internes et, si vous l'activez, ceux de personnes extérieures par un lien public protégé. Les
signalements sont triés par des gestionnaires habilités et peuvent devenir des incidents ou des enquêtes,
avec un historique complet.</p>"""),
        dict(id='groupe', h2="Groupes et organisations multi-pays", html="""
<p>Chaque entité dispose de son espace cloisonné, de ses utilisateurs et de son profil réglementaire (France ou
Côte d'Ivoire / UEMOA, avec la devise et les références correspondantes). Le groupe garde des méthodes communes :
mêmes échelles de cotation, mêmes modèles de mission, mêmes indicateurs.</p>"""),
    ],
    faq=[
        ("Que signifie GRC ?",
         "Gouvernance, risques et conformité : l'ensemble des dispositifs qui permettent à une organisation "
         "d'atteindre ses objectifs en maîtrisant ses risques et en respectant ses obligations."),
        ("Qu'est-ce que le modèle des trois lignes ?",
         "Un modèle de l'IIA qui répartit les rôles entre le management opérationnel (1re ligne), les fonctions de "
         "risque et de conformité (2e ligne) et l'audit interne (3e ligne), sous la responsabilité de l'organe de "
         "gouvernance."),
        ("Le rapport au comité est-il rédigé par une IA ?",
         "Non. La synthèse du rapport au comité est produite par des règles explicites à partir des chiffres, ce qui "
         "la rend reproductible et vérifiable."),
        ("Peut-on gérer plusieurs filiales ?",
         "Oui. Chaque entité a son espace cloisonné et son profil réglementaire, avec des méthodes communes au groupe."),
    ],
    liens=['logiciel-audit-interne-ia', 'gestion-risques-entreprise-ia', 'plan-action-correctif-logiciel', 'indicateurs-risques-kri'],
    blog=['audit-interne-3-lignes-defense', 'guide-complet-gestion-risques-entreprise-2026'],
)

# ---------------------------------------------------------------------------------------------------------------
PAGES['cote-divoire'] = dict(
    maj=MAJ,
    titre="Logiciel d'audit interne en Côte d'Ivoire | Egalyx",
    description="Logiciel d'audit interne, de contrôle interne et de gestion des risques pour Abidjan et la Côte d'Ivoire : franc CFA, SYSCOHADA, CENTIF, ARTCI.",
    court="Côte d'Ivoire",
    resume="Audit, contrôle interne et risques pour les organisations ivoiriennes.",
    h1="Audit interne, contrôle interne et gestion des risques en Côte d'Ivoire",
    chapo="Egalyx est utilisable tel quel par les entreprises, banques, institutions de microfinance et organismes "
          "publics ivoiriens : franc CFA, plan SYSCOHADA, jours fériés, références réglementaires locales.",
    points=[
        ("Réglé pour la Côte d'Ivoire", "Franc CFA, heure d'Abidjan, SYSCOHADA et jours fériés ivoiriens."),
        ("Références locales", "CENTIF, Commission bancaire de l'UMOA, ARTCI, OHADA."),
        ("Accessible partout", "Application web, sans installation ; utilisable sur mobile."),
    ],
    sections=[
        dict(id='contexte', h2="Les attentes croissantes envers le contrôle en Côte d'Ivoire", html="""
<p>Les organisations ivoiriennes font face à des exigences qui se renforcent : actionnaires et bailleurs qui
demandent un dispositif de contrôle interne documenté, établissements financiers soumis aux circulaires de la
Commission bancaire de l'UMOA, obligations de vigilance en matière de blanchiment de capitaux, protection des
données personnelles sous le contrôle de l'ARTCI, et normes comptables du SYSCOHADA révisé.</p>
<p>Dans le même temps, les équipes d'audit et de contrôle restent souvent réduites et travaillent sur des fichiers
Excel. Egalyx leur donne un outil complet, réglé pour leur environnement.</p>"""),
        dict(id='profil', h2="Un outil réglé pour la Côte d'Ivoire", html="""
<ul>
<li>montants en <strong>francs CFA</strong> et heure d'Abidjan ;</li>
<li>tests comptables fondés sur le plan <strong>SYSCOHADA</strong> (comptes sensibles, écritures manuelles,
comptes d'attente) ;</li>
<li>jours fériés ivoiriens pris en compte dans les tests de paiements et d'écritures hors jours ouvrés ;</li>
<li>LCB-FT : connaissance des clients, criblage des listes de sanctions, détection des dépôts fractionnés,
références à la CENTIF ;</li>
<li>protection des données : références à la loi n° 2013-450 et à l'ARTCI.</li>
</ul>"""),
        dict(id='secteurs', h2="Pour qui ?", html="""
<p><strong>Entreprises et groupes</strong> : audit interne, contrôle interne des achats, de la trésorerie et de la
paie, cartographie des risques présentée au conseil d'administration.</p>
<p><strong>Banques et institutions de microfinance</strong> : contrôle permanent de deuxième niveau, tests sur le
portefeuille de crédit (délégations, impayés non déclassés, crédits au personnel), LCB-FT et rapport au conseil.</p>
<p><strong>Organismes publics et projets</strong> : audit des dépenses, suivi des recommandations des missions de
contrôle, gestion des incidents et des signalements.</p>"""),
        dict(id='fonctions', h2="Toutes les fonctions d'Egalyx", html="""
<p>Les organisations ivoiriennes disposent de l'ensemble de la plateforme :
<a href="/logiciel-audit-interne-ia">audit interne</a>,
<a href="/audit-interne-automatise">analyse de données et audit continu</a>,
<a href="/cartographie-risques-logiciel">cartographie des risques</a>,
<a href="/indicateurs-risques-kri">indicateurs de risque</a>,
<a href="/plan-action-correctif-logiciel">plans d'action</a> et
<a href="/conformite-ohada-logiciel">conformité OHADA et UEMOA</a>. L'interface est en français, et un groupe
présent en France et en Côte d'Ivoire peut gérer ses deux entités dans le même outil, chacune avec son profil.</p>"""),
    ],
    faq=[
        ("Egalyx est-il disponible en Côte d'Ivoire ?",
         "Oui. Egalyx est une application web : il suffit d'un navigateur et d'une connexion internet, à Abidjan "
         "comme ailleurs."),
        ("Les montants sont-ils en francs CFA ?",
         "Oui. Le profil réglementaire Côte d'Ivoire / UEMOA règle la devise sur le franc CFA et l'heure sur celle "
         "d'Abidjan."),
        ("Le logiciel convient-il aux institutions de microfinance ?",
         "Oui. Il comprend des tests sur le portefeuille de crédit et sur la LCB-FT, ainsi que le contrôle de "
         "deuxième niveau et le rapport au conseil."),
        ("Comment obtenir une démonstration ?",
         "Écrivez-nous depuis la page contact en précisant votre secteur ; nous organisons une démonstration à "
         "distance sur vos cas d'usage."),
    ],
    liens=['conformite-ohada-logiciel', 'logiciel-audit-interne-ia', 'audit-interne-automatise', 'controle-interne-logiciel-pme'],
    blog=['logiciel-gestion-risques-ohada-afrique', 'audit-interne-frequence-planification'],
)

# Ordre d'affichage (plan du site, liens « Solutions »)
ORDRE = ['logiciel-audit-interne-ia', 'audit-interne-automatise', 'controle-interne-logiciel-pme',
         'gestion-risques-entreprise-ia', 'cartographie-risques-logiciel', 'indicateurs-risques-kri',
         'plan-action-correctif-logiciel', 'conformite-ohada-logiciel', 'conformite-rgpd-logiciel',
         'gouvernance-entreprise-logiciel', 'cote-divoire']

assert set(ORDRE) == set(PAGES)
for _s, _p in PAGES.items():
    assert len(_p['description']) <= 158, (_s, len(_p['description']))
    for _l in _p['liens']:
        assert _l in PAGES, (_s, _l)

# FAQ de la page d'accueil (affichée sur la page et reprise en données structurées FAQPage)
FAQ_ACCUEIL = [
    ("Qu'est-ce qu'Egalyx ?",
     "Egalyx est une plateforme en ligne de gouvernance, risques et conformité : audit interne, contrôle interne, "
     "cartographie des risques, indicateurs de risque (KRI), plans d'action, conformité et analyse de données d'audit."),
    ("Egalyx convient-il aux organisations de Côte d'Ivoire et de France ?",
     "Oui. Chaque organisation choisit son profil réglementaire : Côte d'Ivoire / UEMOA (franc CFA, SYSCOHADA, CENTIF, "
     "ARTCI) ou France (euro, plan comptable général, Tracfin, CNIL). Les tests, les seuils et les références s'adaptent."),
    ("Quelles données peut-on analyser ?",
     "Achats, fournisseurs, paiements, grand livre, ventes, paie, comptes utilisateurs, crédits et opérations "
     "bancaires, importés en Excel, CSV ou FEC, ou relevés directement dans vos bases et logiciels de gestion."),
    ("L'intelligence artificielle est-elle obligatoire ?",
     "Non. L'IA aide à rédiger constats, rapports et analyses ; elle s'active ou se désactive organisation par "
     "organisation. Toutes les fonctions restent disponibles sans elle."),
    ("Comment les données sont-elles protégées ?",
     "Les données de chaque organisation sont cloisonnées, les informations sensibles chiffrées, et l'accès est protégé "
     "par double authentification ou authentification unique (SSO). Egalyx est certifié ISO 27001, SOC 2 Type II et HDS."),
    ("Faut-il installer un logiciel ?",
     "Non. Egalyx s'utilise dans le navigateur, sur ordinateur comme sur mobile, sans installation."),
]
