"""
Modules Egalyx Control ajoutés en v4.

Branchement (une seule ligne, à la fin de app.py, avant « if __name__ == '__main__' ») :
    from egalyx import enregistrer_extensions
    enregistrer_extensions(app, db, csrf=csrf, recalculer_cotations=recalculer_toutes_cotations)
"""
import logging

journal = logging.getLogger('egalyx')


def enregistrer_extensions(app, db, csrf=None, recalculer_cotations=None, construire_dashboard=None):
    from egalyx import (base_donnees, double_auth, sso, parametres_risque, alerte, tiers, signature,
                        paiement, export_donnees, api_doc, organigramme)
    from egalyx import garde_mot_de_passe
    garde_mot_de_passe.enregistrer(app)     # SÉCURITÉ : un mauvais mot de passe ne doit jamais ouvrir de session
    base_donnees.enregistrer(app, db)
    from egalyx import cloisonnement
    cloisonnement.enregistrer(app)          # isolation des organisations sur toutes les routes
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
    from egalyx import photo_profil
    photo_profil.enregistrer(app)
    from egalyx import pages_cassees
    pages_cassees.enregistrer(app)       # /ci (301 vers l'accueil), /debug/create-user-form (404)
    from egalyx import kri_sources_securite
    kri_sources_securite.enregistrer(app)  # SÉCURITÉ : sources KRI réservées au super-admin, ni SQLite, ni fichier, ni réseau interne
    from egalyx import ia_cartographie
    ia_cartographie.enregistrer(app)       # analyse de cartographie : score calculé + rédaction IA vérifiée
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
    from egalyx import langue
    langue.enregistrer(app)                 # EN DERNIER : bascule français / anglais (remplace les anciens systèmes)

    from datetime import datetime as _dt
    app.jinja_env.globals.setdefault('datetime', _dt)      # utilisé par errors/500.html
    from egalyx import courriel
    app.jinja_env.globals.update(
        egalyx_paiement_actif=lambda: bool(paiement.prestataires()),
        egalyx_courriel_configure=courriel.est_configure,
    )
    print("✅ Modules v4 : 2FA, SSO, alerte interne, tiers/LCB-FT, signature, paiement, export, "
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
