"""
egalyx/kri_fiche.py — données de la fiche d'un KRI (templates/kri/detail.html) et nettoyage des sources.

- fiche_kri(kri, mesures) : dernière valeur, état (avec les seuils en vigueur à la date de la mesure),
  variation, tendance, fraîcheur, série pour le graphique, fichiers, connexions.
- /kri/sources/<id>/supprimer (super-admin) : supprime une source (les mesures déjà relevées restent).
- sources_diagnostic(sources) : pourquoi une source est en erreur, en clair.
"""
from datetime import datetime

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user, login_required

ETATS = {
    'critique': ('Critique', '#D92D20', '#FEE4E2', 'fa-circle-exclamation'),
    'hors_cible': ('Hors cible', '#D92D20', '#FEE4E2', 'fa-circle-exclamation'),
    'alerte': ('Alerte', '#DC6803', '#FEF0C7', 'fa-triangle-exclamation'),
    'sous_performance': ('Sous la cible', '#DC6803', '#FEF0C7', 'fa-triangle-exclamation'),
    'normal': ('Normal', '#079455', '#DCFAE6', 'fa-circle-check'),
    'dans_cible': ('Dans la cible', '#079455', '#DCFAE6', 'fa-circle-check'),
    'inconnu': ('Pas de mesure', '#667085', '#F2F4F7', 'fa-circle-question'),
}
FRAICHEUR = {'a_jour': ('À jour', '#079455'), 'en_retard': ('Mesure en retard', '#D92D20'), 'jamais': ('Jamais mesuré', '#667085')}


def _etat(kri, valeur, date=None):
    if valeur is None:
        return 'inconnu'
    try:
        return kri.get_etat_alerte(valeur, a_la_date=date)
    except TypeError:
        return kri.get_etat_alerte(valeur)


def fiche_kri(kri, mesures):
    import models as M
    ms = sorted([m for m in (mesures or []) if m.valeur is not None and m.date_mesure],
                key=lambda m: (m.date_mesure, m.id or 0))
    derniere = ms[-1] if ms else None
    precedente = ms[-2] if len(ms) > 1 else None
    etat = _etat(kri, derniere.valeur, derniere.date_mesure) if derniere else 'inconnu'
    variation = None
    if derniere and precedente:
        variation = derniere.valeur - precedente.valeur
    # Tendance : est-ce que ça va dans le bon sens ?
    sens = (kri.sens_evaluation_seuil or 'superieur')
    if variation is None or abs(variation) < 1e-12:
        tendance = ('stable', 'Stable', '#667085', 'fa-arrow-right')
    else:
        degrade = (variation > 0) if sens != 'inferieur' else (variation < 0)
        tendance = ('degradation', 'Se dégrade', '#D92D20', 'fa-arrow-trend-up' if variation > 0 else 'fa-arrow-trend-down') if degrade \
            else ('amelioration', "S'améliore", '#079455', 'fa-arrow-trend-up' if variation > 0 else 'fa-arrow-trend-down')
    try:
        from egalyx.kri_suivi import fraicheur
        fr = fraicheur(kri)
    except Exception:  # noqa: BLE001
        fr = {'etat': 'a_jour' if derniere else 'jamais'}
    valeurs = [m.valeur for m in ms]
    lignes = []
    for i, m in enumerate(reversed(ms)):
        e = _etat(kri, m.valeur, m.date_mesure)
        avant = ms[len(ms) - i - 2] if len(ms) - i - 2 >= 0 else None
        lignes.append({'mesure': m, 'etat': e, 'variation': (m.valeur - avant.valeur) if avant else None,
                       'auto': (m.commentaire or '').startswith('Collecte auto')})
    fichiers = []
    if getattr(M, 'FichierKRI', None) is not None and kri.id:
        fichiers = M.FichierKRI.query.filter_by(kri_id=kri.id).order_by(M.FichierKRI.created_at.desc()).all()
    connexions = []
    try:
        from egalyx.kri_connecteurs import PAR_CODE, liens_connecteur
        connexions = [(l, PAR_CODE[l.source.config_connexion['connecteur']]) for l in liens_connecteur(kri)]
    except Exception:  # noqa: BLE001
        pass
    return {
        'derniere': derniere, 'precedente': precedente, 'variation': variation, 'tendance': tendance,
        'etat': etat, 'etat_info': ETATS.get(etat, ETATS['inconnu']), 'fraicheur': fr,
        'fraicheur_info': FRAICHEUR.get(fr.get('etat'), FRAICHEUR['jamais']),
        'stats': {'nb': len(valeurs), 'min': min(valeurs) if valeurs else None, 'max': max(valeurs) if valeurs else None,
                  'moyenne': (sum(valeurs) / len(valeurs)) if valeurs else None,
                  'nb_alertes': len([x for x in lignes if x['etat'] in ('alerte', 'critique', 'sous_performance', 'hors_cible')])},
        'serie': {'dates': [m.date_mesure.strftime('%d/%m/%Y') for m in ms[-60:]], 'valeurs': valeurs[-60:]},
        'lignes': lignes, 'fichiers': fichiers, 'connexions': connexions, 'etats': ETATS,
        'est_kpi': (kri.type_indicateur or 'kri') == 'kpi',
    }


def raison_erreur(source):
    """Explication lisible de l'échec d'une source (sans appel réseau long)."""
    cfg = source.config_connexion or {}
    if cfg.get('connecteur'):
        return "Connecteur : relevez-le depuis la fiche du KRI pour voir le message exact (jeton révoqué, requête modifiée…)."
    try:
        from egalyx.kri_sources_securite import probleme_source
        msg = probleme_source(source.type_source, cfg)
    except Exception:  # noqa: BLE001
        msg = None
    if msg:
        return f"{msg}. Source probablement fictive ou de test : supprimez-la."
    if source.type_source == 'api' and not cfg.get('url'):
        return "Aucune adresse configurée : supprimez-la ou complétez-la."
    return "L'outil n'a pas renvoyé de valeur exploitable (adresse, authentification ou chemin de la donnée)."


def supprimer_source(id):
    import models as M
    from models import db
    if not getattr(current_user, 'is_super_admin', False):
        abort(403)
    s = db.session.get(M.SourceDonnee, id)
    if s is None:
        abort(404)
    nom = s.nom
    db.session.delete(s)          # liens et historique des collectes supprimés ; les mesures restent
    db.session.commit()
    try:
        from egalyx.commun import journaliser
        journaliser('kri_source_supprimee', {'source': id, 'nom': nom}, client_id=s.client_id)
    except Exception:  # noqa: BLE001
        pass
    flash(f"Source « {nom} » supprimée. Les mesures déjà relevées sont conservées.", 'success')
    return redirect(request.referrer or url_for('liste_sources_donnees'))


def enregistrer(app):
    app.jinja_env.globals['fiche_kri'] = fiche_kri
    app.jinja_env.globals['kri_raison_erreur_source'] = raison_erreur
    if 'kri_supprimer_source' not in app.view_functions:
        app.add_url_rule('/kri/sources/<int:id>/supprimer', 'kri_supprimer_source', login_required(supprimer_source), methods=['POST'])
