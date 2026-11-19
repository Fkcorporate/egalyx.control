"""
outils/menage_projet.py — range dans archives/ les scripts et les pages qui ne servent plus.

Rien n'est supprimé : les fichiers sont DÉPLACÉS dans archives/menage_2026_11/ (même arborescence),
avec la liste dans archives/menage_2026_11/MANIFESTE.txt. On peut tout remettre en place.

Liste établie le 18/11/2026 :
  - SCRIPTS : fichiers .py de la racine qu'aucune partie de l'application n'importe (ni app.py, ni models,
    ni egalyx/, services/, routes/, tests/, recette/…, directement ou par un autre script importé) :
    anciennes migrations et réparations ponctuelles, copies (« app copie 2.py », « models copie 5.py »…),
    essais, et scripts dangereux à garder hors de portée (nuclear_reset, reset_db, recreate_database…).
    Restent à la racine, en plus des modules de l'application, les 4 outils d'exploitation :
    reparer_base.py, create_first_super_admin.py, reset_super_admin.py, reinitialiser_mot_de_passe.py.
  - PAGES : copies et versions obsolètes de gabarits (« detail copie 3.html »…) qu'aucun code ni
    aucune page n'utilise.

Usage (dans le dossier du projet) :
  python3 outils/menage_projet.py              # montre ce qui serait rangé (ne touche à rien)
  python3 outils/menage_projet.py --appliquer  # range
  python3 outils/menage_projet.py --restaurer  # remet tout en place
"""
import os
import shutil
import sys

ARCHIVE = os.path.join('archives', 'menage_2026_11')

SCRIPTS = [
    " translation_manager.py",
    "A.py",
    "add_bilingual_decorator.py",
    "add_client_to_user.py",
    "add_column_campagne_active.py",
    "add_columns_directly.py",
    "add_columns_to_plans_action.py",
    "add_decorator_to_all_routes.py",
    "add_incident_columns.py",
    "add_missing_columns.py",
    "add_password_security_fields.py",
    "add_subdomain_column.py",
    "add_type_column.py",
    "add_user_blocked_columns.py",
    "analyse_database.py",
    "app copie 2.py",
    "app copie.py",
    "app1.py",
    "app_fixed.py",
    "auto_fix_translations.py",
    "auto_translate.py",
    "babel_from_csv.py",
    "backfill_scores.py",
    "check_all_tables.py",
    "check_ia.py",
    "check_notifications.py",
    "check_real_state.py",
    "check_remaining.py",
    "check_specific_notification.py",
    "check_tables.py",
    "check_translations.py",
    "clean_false_positives.py",
    "cleanup.py",
    "convert_csv_to_js.py",
    "correct_audit_form.py",
    "correction_audit_id.py",
    "correction_complete.py",
    "correction_complete_v2.py",
    "create_db_final.py",
    "create_migration.py",
    "create_migration_fixed.py",
    "create_missing_tables.py",
    "create_proper_translations.py",
    "create_tables.py",
    "create_translation_base.py",
    "debug_routes.py",
    "diagnostic_leger.py",
    "extract_all_texts.py",
    "filters.py",
    "final_cleanup.py",
    "final_migration.py",
    "final_repair.py",
    "find_and_fix.py",
    "find_database.py",
    "find_untranslated_texts.py",
    "fix_all_c2n_columns.py",
    "fix_all_tables.py",
    "fix_all_veille_final.py",
    "fix_bibliotheque.py",
    "fix_c2n_migrations.py",
    "fix_c2n_tables.py",
    "fix_client_id_column.py",
    "fix_client_id_columns.py",
    "fix_columns.py",
    "fix_created_by.py",
    "fix_critical_tables.py",
    "fix_critical_translations.py",
    "fix_database.py",
    "fix_database_columns.py",
    "fix_database_corrected.py",
    "fix_database_now.py",
    "fix_direction_table.py",
    "fix_evaluation_risque.py",
    "fix_evaluations.py",
    "fix_final.py",
    "fix_french_texts.py",
    "fix_historique_recommandations.py",
    "fix_incident_columns.py",
    "fix_manager.py",
    "fix_missing_columns.py",
    "fix_models.py",
    "fix_net_manquant.py",
    "fix_plans_action.py",
    "fix_plans_action_permissions.py",
    "fix_priorite_column.py",
    "fix_qualite_complet.py",
    "fix_qualite_revue.py",
    "fix_sqlalchemy_mappers.py",
    "fix_sqlalchemy_text.py",
    "fix_super_admin_data.py",
    "fix_tables.py",
    "fix_tables_veille.py",
    "fix_translation_system.py",
    "fix_urgent.py",
    "fix_user_table.py",
    "force_fix.py",
    "forms copie.py",
    "generate_articles.py",
    "generate_with_ai.py",
    "import_articles_csv.py",
    "import_biblio.py",
    "import_biblio_complet.py",
    "import_biblio_data.py",
    "import_translations.py",
    "import_users.py",
    "import_users_simple.py",
    "init_app.py",
    "init_bibliotheque.py",
    "init_collecte_system.py",
    "init_database.py",
    "init_permissions.py",
    "list_all_routes.py",
    "logo.py",
    "manage_ia.py",
    "middleware_subdomain.py",
    "migrate_add_pays_to_poles.py",
    "migrate_add_user_columns.py",
    "migrate_all.py",
    "migrate_all_client_id.py",
    "migrate_all_columns.py",
    "migrate_anomalies.py",
    "migrate_api_keys.py",
    "migrate_archive_fields copie.py",
    "migrate_archive_fields.py",
    "migrate_archive_fixed.py",
    "migrate_auditeurs.py",
    "migrate_audits_qualite.py",
    "migrate_c2n.py",
    "migrate_c2n_client_id.py",
    "migrate_c2n_tables.py",
    "migrate_campagne_c2n.py",
    "migrate_client_id.py",
    "migrate_client_subdomain.py",
    "migrate_collab.py",
    "migrate_collect_fields.py",
    "migrate_db.py",
    "migrate_directions_services_client.py",
    "migrate_dispositif_id.py",
    "migrate_incident_columns.py",
    "migrate_incidents.py",
    "migrate_iso_columns.py",
    "migrate_kri.py",
    "migrate_menaces.py",
    "migrate_missing_tables.py",
    "migrate_organisme_created_by.py",
    "migrate_plans_action.py",
    "migrate_qualite.py",
    "migrate_qualite_tables.py",
    "migrate_recommandations.py",
    "migrate_sources.py",
    "migrate_sous_actions.py",
    "migrate_tables.py",
    "migrate_translations.py",
    "migrate_veille.py",
    "migrate_veille_meta.py",
    "migrate_veille_perimetre.py",
    "migrate_veille_poles.py",
    "migration.py",
    "migration_add_archived_fields.py",
    "migration_add_client_id.py",
    "migration_add_client_id_c2n.py",
    "migration_add_columns.py",
    "migration_add_processus_id.py",
    "migration_add_processus_id_correct.py",
    "migration_add_statut_archive.py",
    "migration_ajout_colonnes_kri.py",
    "migration_archivage_logigrammes.py",
    "migration_campagnes.py",
    "migration_campagnes_fixed.py",
    "migration_definitive.py",
    "migration_definitive_logigramme.py",
    "migration_espace_travail.py",
    "migration_finale.py",
    "migration_fix_lien_processus.py",
    "migration_kri.py",
    "migration_kri_simple.py",
    "migration_lien_logigramme.py",
    "migration_logigramme.py",
    "migration_logigramme_direction_service.py",
    "migration_logigramme_fix.py",
    "migration_mission_archive.py",
    "migration_organigramme.py",
    "migration_plan_pluie.py",
    "migration_programme_archive.py",
    "migration_programme_audit.py",
    "migration_relations.py",
    "migration_sqlite.py",
    "migrations_add_formules.py",
    "models copie 2.py",
    "models copie 3.py",
    "models copie 4.py",
    "models copie 5.py",
    "models copie.py",
    "models1.py",
    "notification_service.py",
    "nuclear_reset.py",
    "ok.py",
    "programme.py",
    "python migration_fix.py",
    "quick_verification.py",
    "reate_c2n_tables.py",
    "rebuild_database.py",
    "recreate_database.py",
    "recreate_missing_tables.py",
    "refresh_sqlalchemy.py",
    "repair_database.py",
    "replace_english_texts.py",
    "reset_db.py",
    "run_ia_tool.py",
    "scan_templates.py",
    "script_fix_permissions.py",
    "script_migration.py",
    "setup_language.py",
    "smart_translate.py",
    "test_api.py",
    "test_api_routes.py",
    "test_collecte_rh.py",
    "test_complet_logigramme.py",
    "test_email_simple.py",
    "test_final.py",
    "test_ia_detailed.py",
    "test_notif.py",
    "test_openai.py",
    "test_service_ia.py",
    "test_translations.py",
    "translate_all.py",
    "translate_all_templates.py",
    "translate_auto_free.py",
    "translate_final.py",
    "translate_simple.py",
    "translate_templates_improved.py",
    "translate_with_openai.py",
    "translate_with_openai_fixed.py",
    "translation_manager_fixed.py",
    "ultimate_fix.py",
    "update_all_templates.py",
    "update_database.py",
    "update_db.py",
    "update_existing_data.py",
    "url_translations.py",
    "utils copie 2.py",
    "utils copie 3.py",
    "utils copie 4.py",
    "utils copie.py",
    "utils_parametrage.py",
    "verification_csv.py",
    "verify_translations.py",
    "ya.py",
    "yi.py",
    "yo.py",
    "yoyo.py"
]

# Copies de modules de services (nom avec espace : impossibles à importer, donc jamais utilisées)
AUTRES = [
    "services/analyse_ia copie.py",
    "services/analyse_ia copie 2.py",
    # anciennes migrations : scripts isolés et une révision Alembic inachevée (révision parente jamais renseignée),
    # remplacés par migrations/versions/20261118_0001_reference.py
    "migrations/add_archived_by_column.py",
    "migrations/ajouter_createur_id.py",
    "migrations/migrate_c2n_improvements.py",
    "migrations/versions/add_password_security_fields.py"
]

PAGES = [
    # 19/11/2026 : pages jamais affichées (aucune route ne les utilise) dont les boutons appelaient des adresses inexistantes
    "admin/api_keys_management.html", "audit/constatation/gestion_preuves.html", "audit/notifications.html",
    "c2n/dashboard_recommandations.html", "campagnes_controle/detail.html", "cartographie/_dashboard_dynamique.html",
    "constatation/gestion_preuves.html", "dashboard_strategique/index.html", "logigramme/archive_logigrammes.html",
    "plans_action/espace_travail.html", "blog.html", "features.html", "rapports_audit.html", "home.html.backup",
    "audit/detail_audit copie 2.html",
    "audit/detail_audit copie 3.html",
    "audit/detail_audit copie 4.html",
    "audit/detail_audit copie.html",
    "audit/rapports copie 2.html",
    "audit/rapports copie.html",
    "audits copie.html",
    "base copie 2.html",
    "base copie.html",
    "cartographie/analyse_ia&.html",
    "cartographie/detail copie 2.html",
    "cartographie/detail copie 3.html",
    "cartographie/detail copie 4.html",
    "cartographie/detail copie 5.html",
    "cartographie/detail copie 6.html",
    "cartographie/detail copie.html",
    "cartographie/evaluation copie.html",
    "cartographie/evaluation_triphase copie.html",
    "cartographie/form copie.html",
    "cartographie/liste copie 2.html",
    "cartographie/matrice copie.html",
    "cartographie/matrice_risque copie.html",
    "cartographie/risque_detail copie 2.html",
    "cartographie/risque_detail copie.html",
    "cartographie/risque_form copie.html",
    "dashboard copie 2.html",
    "dashboard copie.html",
    "home copie 2.html",
    "home copie 3.html",
    "home copie.html",
    "kri/form copie.html",
    "kri/liste copie.html",
    "logigramme/editeur_logigramme copie 2.html",
    "logigramme/editeur_logigramme copie 3.html",
    "logigramme/editeur_logigramme copie 4.html",
    "logigramme/editeur_logigramme copie.html",
    "logigramme/liste_logigrammes copie.html",
    "logigramme/nouveau_logigramme copie.html",
    "programme_audit/chronogramme copie.html",
    "tableau_de_bord_strategique-obselete.html"
]


def _paires():
    for f in SCRIPTS:
        yield f, os.path.join(ARCHIVE, 'racine', f)
    for f in AUTRES:
        yield f, os.path.join(ARCHIVE, f)
    for f in PAGES:
        yield os.path.join('templates', f), os.path.join(ARCHIVE, 'templates', f)


def main():
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(racine)
    if not os.path.exists('app.py'):
        sys.exit('Lancez ce script depuis le projet Egalyx (app.py introuvable).')
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == '--restaurer':
        n = 0
        for origine, archive in _paires():
            if os.path.exists(archive) and not os.path.exists(origine):
                os.makedirs(os.path.dirname(origine) or '.', exist_ok=True)
                shutil.move(archive, origine); n += 1
        print(f'{n} fichier(s) remis en place.')
        return
    presents = [(o, a) for o, a in _paires() if os.path.exists(o)]
    if mode != '--appliquer':
        print(f'{len(presents)} fichier(s) seraient rangés dans {ARCHIVE}/ :')
        for o, _a in presents:
            print('  ', o)
        print('\nRien n\'a été modifié. Pour ranger : python3 outils/menage_projet.py --appliquer')
        return
    os.makedirs(ARCHIVE, exist_ok=True)
    with open(os.path.join(ARCHIVE, 'MANIFESTE.txt'), 'a', encoding='utf-8') as m:
        for o, a in presents:
            os.makedirs(os.path.dirname(a), exist_ok=True)
            shutil.move(o, a)
            m.write(f'{o} -> {a}\n')
    print(f'{len(presents)} fichier(s) rangés dans {ARCHIVE}/ (liste : MANIFESTE.txt).')
    print('Pour annuler : python3 outils/menage_projet.py --restaurer')


if __name__ == '__main__':
    main()
