"""
Modules Egalyx Control ajoutés en v4.

Branchement (une seule ligne, à la fin de app.py, avant « if __name__ == '__main__' ») :
    from egalyx import enregistrer_extensions
    enregistrer_extensions(app, db, csrf=csrf, recalculer_cotations=recalculer_toutes_cotations)
"""

# --- Journal (remplace les anciens print()) : erreurs -> WARNING (journaux du serveur) ; le reste -> DEBUG,
#     visible seulement avec EGALYX_TRACES=1. Ajouté le 18/11/2026 (ménage).
import logging as _logging_journal
import os as _os_journal
_JOURNAL = _logging_journal.getLogger('egalyx.modules')
_MOTS_ALERTE = ('\u274c', '\u26a0', 'ERREUR', 'Erreur', 'erreur', 'ERROR', 'Error', 'error', 'Exception', 'chec', 'Traceback', 'CRITIQUE')
if _os_journal.environ.get('EGALYX_TRACES') == '1' and not _JOURNAL.handlers:
    _JOURNAL.setLevel(_logging_journal.DEBUG)
    _h = _logging_journal.StreamHandler()
    _h.setFormatter(_logging_journal.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
    _JOURNAL.addHandler(_h)
    _JOURNAL.propagate = False


def _journal(*args, sep=' ', **_ignore):
    """Ancien print() : écrit dans le journal au lieu de la sortie standard."""
    try:
        texte = sep.join(str(a) for a in args)
    except Exception:  # noqa: BLE001
        return
    if any(m in texte for m in _MOTS_ALERTE) and not texte.lstrip().startswith(('\u2705', '\u2713')):
        _JOURNAL.warning(texte)
    elif _JOURNAL.isEnabledFor(_logging_journal.DEBUG):
        _JOURNAL.debug(texte)
# --- fin du journal
import logging

journal = logging.getLogger('egalyx')

# Passerelle d'IA (egalyx/ia_passerelle.py) : posée dès l'import d'egalyx, c'est-à-dire avant que app.py et les
# services lisent la clé d'IA ; toutes les demandes d'IA passent ensuite par elle (fournisseur, masquage, journal).
try:
    from egalyx import ia_passerelle as _ia_passerelle
    _ia_passerelle.preparer_environnement()
    _ia_passerelle.installer()
except Exception as _e:  # noqa: BLE001
    journal.warning("Passerelle d'IA non installée : %s", _e)


def enregistrer_extensions(app, db, csrf=None, recalculer_cotations=None, construire_dashboard=None):
    from egalyx import (base_donnees, double_auth, sso, parametres_risque, alerte, tiers, signature,
                        paiement, export_donnees, api_doc, organigramme)
    from egalyx import stockage_persistant
    stockage_persistant.enregistrer(app)    # Render : fichiers déposés sur le disque persistant (EGALYX_DONNEES ou /var/data)
    from egalyx import garde_mot_de_passe
    garde_mot_de_passe.enregistrer(app)     # SÉCURITÉ : un mauvais mot de passe ne doit jamais ouvrir de session
    base_donnees.enregistrer(app, db)
    from egalyx import cloisonnement
    cloisonnement.enregistrer(app)          # isolation des organisations sur toutes les routes
    from egalyx import cloisonnement_listes
    cloisonnement_listes.enregistrer(app)   # filet : les listes ne montrent que l'organisation de l'utilisateur
    from egalyx import questionnaires_publics
    questionnaires_publics.enregistrer(app)  # réponses publiques : questionnaire public, actif, dans ses dates
    double_auth.enregistrer(app)
    sso.enregistrer(app)
    parametres_risque.enregistrer(app, recalculer=recalculer_cotations)
    alerte.enregistrer(app)
    tiers.enregistrer(app)
    signature.enregistrer(app)
    paiement.enregistrer(app, csrf=csrf)
    export_donnees.enregistrer(app)
    api_doc.enregistrer(app, csrf=csrf)
    organigramme.enregistrer(app)

    # v5 : démonstration, rapport au comité, bibliothèque sectorielle, recherche, « Ma semaine », automatismes
    from egalyx import demo, rapport_comite, bibliotheque, recherche, ma_semaine, automatismes
    demo.enregistrer(app)
    rapport_comite.enregistrer(app, construire_dashboard=construire_dashboard)
    bibliotheque.enregistrer(app)
    from egalyx import import_cartographie
    import_cartographie.enregistrer(app)
    from egalyx import alertes_incidents
    alertes_incidents.enregistrer(app)
    from egalyx import identite
    identite.enregistrer(app)
    from egalyx import rapport_contenu
    rapport_contenu.enregistrer(app)                # contenu des rapports (sections, signataires, textes) par organisation
    from egalyx import dossier_fige
    dossier_fige.enregistrer(app)                   # dossier de mission figé après le rapport définitif
    from egalyx import satisfaction_audit
    satisfaction_audit.enregistrer(app)             # avis des audités en fin de mission
    from egalyx import fonction_audit
    fonction_audit.enregistrer(app)                 # univers d'audit, qualité de la fonction (IIA 2024), charte
    from egalyx import carto_processus
    carto_processus.enregistrer(app)                # cartographie des processus (module sur activation du super admin)
    from egalyx import ia_audit
    ia_audit.enregistrer(app)                       # IA au cœur de l'audit : constats depuis les notes, premier jet du rapport
    from egalyx import analyse_donnees
    analyse_donnees.enregistrer(app)                # analyse des données d'audit (module sur activation du super admin)
    from egalyx import analyse_sources
    analyse_sources.enregistrer(app)                # sources de données (connecteurs) et analyses programmées (audit continu)
    from egalyx import assistant_donnees
    assistant_donnees.enregistrer(app)              # assistant : tous les outils pour l'IA, couverture d'audit, indicateurs
    from egalyx import photo_profil
    photo_profil.enregistrer(app)
    try:                                   # paquet facultatif : /ci (301 vers l'accueil), /debug/create-user-form (404)
        from egalyx import pages_cassees
        pages_cassees.enregistrer(app)
    except ImportError:
        pass
    from egalyx import kri_sources_securite
    kri_sources_securite.enregistrer(app)  # SÉCURITÉ : sources KRI réservées au super-admin, ni SQLite, ni fichier, ni réseau interne
    try:                                   # paquet facultatif : analyse de cartographie : score calculé + rédaction IA vérifiée
        from egalyx import ia_cartographie
        ia_cartographie.enregistrer(app)
    except ImportError:
        pass
    from egalyx import kri_connecteurs
    kri_connecteurs.enregistrer(app)       # KRI : 12 connecteurs (Jira, ServiceNow, Odoo, Google Sheets…) + relevé automatique
    from egalyx import kri_fiche
    kri_fiche.enregistrer(app)             # fiche KRI (valeur, jauge, graphique, historique) + suppression des sources en erreur
    from egalyx import kri_ia
    kri_ia.enregistrer(app)                # KRI : « Analyser avec l'IA » à la demande (soumis à l'interrupteur IA du super-admin)
    from egalyx import bienvenue
    bienvenue.enregistrer(app)          # e-mail de bienvenue (accès, identifiant, guide de double authentification)
    recherche.enregistrer(app)
    ma_semaine.enregistrer(app)
    automatismes.enregistrer(app)
    from egalyx import modules_client
    modules_client.enregistrer(app)
    from egalyx import ia
    ia.enregistrer(app)                     # interrupteur unique de l'IA (plateforme, client, permission)
    from egalyx import aide
    aide.enregistrer(app)                   # centre d'aide /aide + base de connaissances de l'assistant
    from egalyx import circuit_controle
    circuit_controle.enregistrer(app)       # circuit unique campagnes de contrôle ↔ contrôle interne N2
    from egalyx import c2n_cartographie
    c2n_cartographie.enregistrer(app)       # N2 ↔ cartographie (dispositifs testés), méthode de test
    from egalyx import c2n_echantillon
    c2n_echantillon.enregistrer(app)        # échantillon N2 élément par élément, tirage aléatoire tracé
    from egalyx import plans_unifies
    plans_unifies.enregistrer(app)          # registre unique : plans des risques + plans du contrôle N2
    from egalyx import notifications_prefs
    notifications_prefs.enregistrer(app)    # « Mes notifications » : application / e-mail / résumé quotidien
    from egalyx import application_mobile
    application_mobile.enregistrer(app)     # installable sur téléphone : manifeste, icônes, service worker
    from egalyx import anti_spam_contact
    anti_spam_contact.enregistrer(app, csrf=csrf)   # formulaire de contact du site : question, champ piège, limite par IP
    from egalyx import blog
    blog.enregistrer(app)                   # blog public : vrais articles, catégories, sitemap, SEO
    from egalyx import connexion_client
    connexion_client.enregistrer(app)       # page de connexion aux couleurs du client (https://<client>.egalyx.com)
    try:                                    # paquet optionnel « nouvelle apparence » (classique / nouvelle au choix)
        from egalyx import apparence
        apparence.enregistrer(app)
    except ImportError:
        pass
    from egalyx import menage
    menage.enregistrer(app)                 # ancien module programmes/missions → N2 ; pages de test réservées
    from egalyx import recommandations, kri_suivi, audit_plus
    recommandations.enregistrer(app)        # registre unique des recommandations (audit, N2, externes)
    kri_suivi.enregistrer(app)              # KRI : fraîcheur des mesures, seuils cohérents et historisés
    audit_plus.enregistrer(app)             # audit : rapport provisoire/définitif, réponses, temps, indépendance
    from egalyx import logigrammes
    logigrammes.enregistrer(app)
    from egalyx import pca, qualite
    pca.enregistrer(app)                    # PCA : droits, circuit de validation, exercices, activations, documents
    qualite.enregistrer(app)                # qualité : droits, validation des plans, non-conformités, revues
    from egalyx import incidents, signalements, maitrise
    maitrise.enregistrer(app)               # dispositifs de maîtrise et plans d'action des risques : droits, vérifications
    incidents.enregistrer(app)              # incidents : droits, délais (SLA), risque/dispositif facultatifs, Ma semaine
    signalements.enregistrer(app)           # signalements (ex-support) : déclarant, suivi, lien public protégé
    from egalyx import gestion_clients
    gestion_clients.enregistrer(app)        # super admin : supprimer / réinitialiser / exporter un client, synchroniser les droits
    from egalyx import permissions_grille
    permissions_grille.enregistrer(app)     # grille des permissions issue du catalogue ; modules non souscrits verrouillés
    from egalyx import masquage
    masquage.enregistrer(app)               # liens, boutons, formulaires et blocs des fonctions indisponibles : retirés
    _filtres_min_max(app)                   # « [a, b]|min » et « valeur|min(borne) » fonctionnent tous les deux
    try:                                   # paquet facultatif : fiche cartographie rapide (matrices en cache)
        from egalyx import carto_rapide, compression, cloture_campagne
        carto_rapide.enregistrer(app)
        cloture_campagne.enregistrer(app)  # réglage : qui peut clôturer une campagne d'évaluation
        compression.enregistrer(app)       # pages compressées (gzip) : beaucoup plus légères à télécharger
    except ImportError:
        pass
    try:                                   # paquet facultatif : collaborateurs rattachés à la structure, périmètre, départs
        from egalyx import structure, organigramme_structure
        structure.enregistrer(app)
        organigramme_structure.enregistrer(app)   # organigramme hiérarchique (pays → pôles → directions → services)
        from egalyx import structure_orga
        structure_orga.enregistrer(app)           # page « Structure de l'organisation » (/admin/directions)
        from egalyx import operateurs
        operateurs.enregistrer(app)               # espace opérateur : droits appliqués sur chaque page, écrans d'administration
        from egalyx import audit_compteurs
        audit_compteurs.enregistrer(app)          # fiche audit : nombre de feuilles de travail dès l'ouverture
        from egalyx import plans_nature
        plans_nature.enregistrer(app)             # plans d'action : audit, risque et indépendant chacun dans son module
        from egalyx import plans_suivi
        plans_suivi.enregistrer(app)              # progression, fin de plan, recommandation et constatation : mêmes règles partout
        from egalyx import localisation, lettre_mission
        localisation.enregistrer(app)             # heure et devise de chaque organisation
        lettre_mission.enregistrer(app)           # lettre de mission : en-têtes par organisation, PDF, envoi aux bonnes personnes
        from egalyx import papier_entete
        papier_entete.enregistrer(app)            # papier à en-tête PDF du client (rapport d'audit, lettre de mission)
        from egalyx import securite
        securite.enregistrer(app)                 # outils de débogage fermés en production, limite de connexion, en-têtes
        from egalyx import installation
        installation.enregistrer(app)             # on-premise : flask creer-super-admin, flask verifier-installation
        from egalyx import licence
        licence.enregistrer(app)                  # on-premise : clé de licence (inactive sauf EGALYX_LICENCE_REQUISE=1)
        from egalyx import appreciation_reco
        appreciation_reco.enregistrer(app)        # appréciation de l'auditeur sur chaque recommandation
        from egalyx import categories_risque
        categories_risque.enregistrer(app)        # catégories de risque par défaut (+ libellés lisibles)
        from egalyx import cartouche_qualite
        cartouche_qualite.enregistrer(app)        # cartouche qualité (code, date, version, page) du rapport d'audit
        from egalyx import boutons_repares
        boutons_repares.enregistrer(app)          # boutons qui appelaient une adresse inexistante
        from egalyx import statuts
        statuts.enregistrer(app)                  # une seule écriture des statuts par objet (+ conversion des données)
        from egalyx import pdf_secours
        pdf_secours.enregistrer(app)              # sans WeasyPrint : version imprimable au lieu d'une erreur 500
    except ImportError:
        pass
    try:                                   # paquet facultatif : notifications sur téléphone / ordinateur + pastille
        from egalyx import notifications_push
        notifications_push.enregistrer(app)
    except ImportError:
        pass
    try:                                   # paquet facultatif : la demande de changement d'offre part vraiment
        from egalyx import demande_offre, questionnaire_stats
        demande_offre.enregistrer(app)
        questionnaire_stats.enregistrer(app)
    except ImportError:
        pass
    try:                                   # paquet facultatif : l'IA dit la vérité (vraie IA ou « analyse automatique » signalée)
        from egalyx import ia_honnete
        ia_honnete.enregistrer(app)
    except ImportError:
        pass
    from egalyx import langue
    langue.enregistrer(app)                 # EN DERNIER : bascule français / anglais (remplace les anciens systèmes)

    from datetime import datetime as _dt
    app.jinja_env.globals.setdefault('datetime', _dt)      # utilisé par errors/500.html
    from egalyx import courriel
    app.jinja_env.globals.update(
        egalyx_paiement_actif=lambda: bool(paiement.prestataires()),
        egalyx_courriel_configure=courriel.est_configure,
    )
    _journal("✅ Modules v4 : 2FA, SSO, alerte interne, tiers/LCB-FT, signature, paiement, export, "
          "API documentée, organigramme éditable, paramètres de risque, sauvegardes, démonstration, "
          "rapport au comité, bibliothèque sectorielle, recherche globale, Ma semaine, relances")

def _filtres_min_max(app):
    """app.py redéfinit les filtres Jinja « min » et « max » en « valeur|min(borne) ». Les écrans qui utilisent
    la forme standard « [a, b]|min » recevaient alors la liste elle-même (barres vides, organigramme et graphiques faux).
    Ces versions acceptent les deux formes."""
    def fabrique(fonction):
        def filtre(valeur, *args, attribute=None, **kw):
            if isinstance(valeur, (list, tuple, set)) or (hasattr(valeur, '__iter__') and not isinstance(valeur, (str, bytes, dict))):
                elements = [x for x in valeur if x is not None]
                if not elements:
                    return None
                if attribute:     # comme Jinja : renvoie l'élément dont l'attribut est le plus petit / grand
                    cle = lambda x: (x.get(attribute) if isinstance(x, dict) else getattr(x, attribute, None)) or 0
                    return fonction(elements, key=cle)
                return fonction(elements)
            borne = args[0] if args else kw.get('min_value', kw.get('max_value', 0))
            try:
                return fonction(float(valeur), float(borne))
            except (TypeError, ValueError):
                return valeur
        return filtre
    app.jinja_env.filters['min'] = fabrique(min)
    app.jinja_env.filters['max'] = fabrique(max)
