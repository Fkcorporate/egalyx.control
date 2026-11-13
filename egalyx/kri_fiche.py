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
        'projection': projection(kri, ms),
    }


def projection(kri, ms):
    """Tendance linéaire des 6 dernières mesures (au moins 3) : quand les seuils seront-ils franchis ?
    Calcul pur, reproductible. {'texte', 'couleur', 'icone', 'jours_alerte', 'jours_critique', 'pente_par_mois'} ou None."""
    pts = [(m.date_mesure, m.valeur) for m in ms if m.valeur is not None and m.date_mesure][-6:]
    if len(pts) < 3:
        return None
    t0 = pts[0][0]
    xs = [(d - t0).total_seconds() / 86400 for d, _ in pts]
    ys = [v for _, v in pts]
    n, mx, my = len(xs), sum(xs) / len(xs), sum(ys) / len(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den <= 0:
        return None
    pente = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den        # par jour
    derniere, d_der = ys[-1], pts[-1][0]
    bas = (kri.sens_evaluation_seuil or 'superieur') == 'inferieur'
    a, c = kri.seuil_alerte, kri.seuil_critique
    franchi = (lambda v, s: s is not None and (v <= s if bas else v >= s))
    ech = max(abs(my), 1e-9)
    res = {'pente_par_mois': pente * 30, 'jours_alerte': None, 'jours_critique': None}
    if franchi(derniere, c):
        return dict(res, texte='Déjà au-delà du seuil critique.', couleur='#D92D20', icone='fa-circle-exclamation')
    defavorable = (pente < 0) if bas else (pente > 0)
    if abs(pente * 30) < ech * 0.01 or not defavorable:
        return dict(res, texte=('Tendance favorable : aucun dépassement de seuil prévu.' if abs(pente * 30) >= ech * 0.01
                                else 'Tendance stable : aucun dépassement de seuil prévu.'), couleur='#079455', icone='fa-shield-heart')

    def jours(seuil):
        if seuil is None or franchi(derniere, seuil):
            return 0 if seuil is not None else None
        j = (seuil - derniere) / pente
        return j if j > 0 else None
    ja, jc = jours(a), jours(c)
    res.update(jours_alerte=ja, jours_critique=jc)
    from datetime import timedelta

    def quand(j):
        d = d_der + timedelta(days=j)
        mois = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre')
        return f"{mois[d.month - 1]} {d.year}" if j > 45 else f"dans environ {max(1, round(j))} jour(s)"
    if jc is not None and jc > 365:
        return dict(res, texte="Tendance défavorable, mais pas de franchissement du seuil critique prévu dans l'année.",
                    couleur='#DC6803', icone='fa-arrow-trend-up' if not bas else 'fa-arrow-trend-down')
    morceaux = []
    if ja and ja > 0 and (jc is None or ja < jc):
        morceaux.append(f"seuil d'alerte vers {quand(ja)}" if ja > 45 else f"seuil d'alerte {quand(ja)}")
    if jc is not None:
        morceaux.append(f"seuil critique vers {quand(jc)}" if jc > 45 else f"seuil critique {quand(jc)}")
    if not morceaux:
        return dict(res, texte='Tendance défavorable.', couleur='#DC6803', icone='fa-arrow-trend-up')
    return dict(res, texte='Au rythme actuel : ' + ', puis '.join(morceaux) + '.', couleur='#D92D20' if (jc or 999) < 90 else '#DC6803',
                icone='fa-hourglass-half')


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


def graphique_svg(kri, ms, largeur=720, hauteur=230):
    """Graphique vectoriel (SVG) de l'évolution avec les seuils, pour le PDF : net à toute échelle, sans dépendance."""
    pts = [(m.date_mesure, m.valeur) for m in ms if m.valeur is not None and m.date_mesure]
    if len(pts) < 2:
        return None
    g, d, h, b = 46, 14, 14, 30
    t0, t1 = pts[0][0], pts[-1][0]
    duree = max((t1 - t0).total_seconds(), 1)
    seuils = [(kri.seuil_alerte, '#F79009', 'alerte'), (kri.seuil_critique, '#F04438', 'critique'), (kri.seuil_cible, '#17B26A', 'cible')]
    vals = [v for _, v in pts] + [s for s, _, _ in seuils if s is not None]
    vmin, vmax = min(vals), max(vals)
    if vmax == vmin:
        vmin, vmax = vmin - 1, vmax + 1
    marge = (vmax - vmin) * 0.12
    vmin, vmax = vmin - marge, vmax + marge
    X = lambda t: g + (largeur - g - d) * ((t - t0).total_seconds() / duree)
    Y = lambda v: h + (hauteur - h - b) * (1 - (v - vmin) / (vmax - vmin))
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largeur} {hauteur}" width="100%" font-family="DejaVu Sans, Arial" font-size="9">']
    for i in range(5):
        v = vmin + (vmax - vmin) * i / 4
        o.append(f'<line x1="{g}" x2="{largeur - d}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#EAECF0" stroke-width="1"/>')
        o.append(f'<text x="{g - 6}" y="{Y(v) + 3:.1f}" text-anchor="end" fill="#667085">{v:.3g}</text>')
    for s, coul, lib in seuils:
        if s is not None:
            o.append(f'<line x1="{g}" x2="{largeur - d}" y1="{Y(s):.1f}" y2="{Y(s):.1f}" stroke="{coul}" stroke-width="1.2" stroke-dasharray="5 4"/>')
            o.append(f'<text x="{largeur - d}" y="{Y(s) - 3:.1f}" text-anchor="end" fill="{coul}" font-weight="bold">{lib} {s:g}</text>')
    ligne = ' '.join(f'{X(t):.1f},{Y(v):.1f}' for t, v in pts)
    o.append(f'<polygon points="{X(pts[0][0]):.1f},{Y(vmin):.1f} {ligne} {X(pts[-1][0]):.1f},{Y(vmin):.1f}" fill="#1D4ED8" fill-opacity="0.07"/>')
    o.append(f'<polyline points="{ligne}" fill="none" stroke="#1D4ED8" stroke-width="2" stroke-linejoin="round"/>')
    for t, v in pts[-40:]:
        e = _etat(kri, v, t)
        coul = ETATS.get(e, ETATS['inconnu'])[1]
        o.append(f'<circle cx="{X(t):.1f}" cy="{Y(v):.1f}" r="2.8" fill="{coul}" stroke="#fff" stroke-width="1"/>')
    idx = sorted({0, len(pts) // 2, len(pts) - 1})
    for i in idx:
        t = pts[i][0]
        ancre = 'start' if i == 0 else ('end' if i == len(pts) - 1 else 'middle')
        o.append(f'<text x="{X(t):.1f}" y="{hauteur - 10}" text-anchor="{ancre}" fill="#667085">{t:%d/%m/%Y}</text>')
    o.append('</svg>')
    return ''.join(o)


def rapport_pdf(kri_id):
    """Rapport PDF d'un KRI : synthèse, jauge, graphique vectoriel, historique COMPLET (commentaires entiers)."""
    import models as M
    from flask import make_response, render_template
    k = M.db.session.get(M.KRI, kri_id)
    if k is None or (not getattr(current_user, 'is_super_admin', False) and k.client_id != current_user.client_id):
        abort(404)
    mesures = M.MesureKRI.query.filter_by(kri_id=k.id).all()
    f = fiche_kri(k, mesures)
    ms = sorted([m for m in mesures if m.valeur is not None and m.date_mesure], key=lambda m: (m.date_mesure, m.id or 0))
    client = M.db.session.get(M.Client, k.client_id) if k.client_id else None
    html = render_template('kri/rapport_pdf.html', kri=k, f=f, svg=graphique_svg(k, ms), client=client,
                           genere_le=datetime.utcnow(), auteur=current_user)
    if request.args.get('html') == '1':
        return html
    try:
        from weasyprint import HTML
    except ImportError:
        flash("Le module PDF (WeasyPrint) n'est pas installé sur ce serveur : voici la version imprimable.", 'warning')
        return html
    pdf = HTML(string=html, base_url=request.url_root).write_pdf()
    nom = ''.join(c for c in f"rapport_{k.type_indicateur or 'kri'}_{k.nom}".replace(' ', '_') if c.isalnum() or c in '._-')[:80]
    rep = make_response(pdf)
    rep.headers['Content-Type'] = 'application/pdf'
    rep.headers['Content-Disposition'] = f'attachment; filename={nom}_{datetime.utcnow():%Y%m%d}.pdf'
    return rep


def enregistrer(app):
    if 'telecharger_rapport_kri_pdf' in app.view_functions:
        app.view_functions['telecharger_rapport_kri_pdf'] = login_required(rapport_pdf)
    app.jinja_env.globals['fiche_kri'] = fiche_kri
    app.jinja_env.globals['kri_raison_erreur_source'] = raison_erreur
    if 'kri_supprimer_source' not in app.view_functions:
        app.add_url_rule('/kri/sources/<int:id>/supprimer', 'kri_supprimer_source', login_required(supprimer_source), methods=['POST'])
