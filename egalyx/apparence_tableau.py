"""
egalyx/apparence_tableau.py — PAQUET OPTIONNEL « nouvelle apparence » : tableau de bord mis en page comme la maquette.

Uniquement quand l'apparence « Nouvelle » est choisie pour le client (par le super-admin) :
  - /dashboard affiche : accueil + chiffres clés (risques critiques net, incidents ouverts, plans en retard,
    contrôles N2 conformes), risques les plus élevés (net), cartographie nette 5 × 5, efficacité des dispositifs,
    incidents par gravité, activité récente — avec les vraies données de l'organisation ;
  - juste après la connexion, l'administrateur du client arrive sur ce tableau de bord (bouton « Administration »
    pour sa page d'administration, qui reste accessible depuis le menu).
En apparence « Classique », rien ne change : la page d'origine est servie telle quelle.
Chaque bloc est calculé à part : une erreur dans un bloc l'affiche vide, sans bloquer la page.
"""
from egalyx.localisation import aujourdhui as _aujourdhui  # date du jour dans le fuseau de l'organisation
from datetime import date, datetime, timedelta

from flask import g, redirect, render_template, request, url_for
from flask_login import current_user

FINIS_INCIDENT = {'resolu', 'résolu', 'ferme', 'fermé', 'clos', 'cloture', 'clôturé', 'annule', 'annulé'}
GRAVITES = (('critique', 'Critique'), ('elevee', 'Élevée'), ('moyenne', 'Moyenne'), ('faible', 'Faible'))
MOIS = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre',
        'novembre', 'décembre')
JOURS = ('lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche')


def _m():
    import models
    return models


def _peut(*perms):
    if getattr(current_user, 'is_super_admin', False):
        return True
    for p in perms:
        try:
            if current_user.has_permission(p):
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _bloc(nom, fonction, defaut):
    try:
        return fonction()
    except Exception as e:  # noqa: BLE001
        try:
            from egalyx.apparence import journal
            journal(f'tableau de bord « nouvelle » : bloc {nom} indisponible ({e!r})')
        except Exception:  # noqa: BLE001
            pass
        try:
            _m().db.session.rollback()
        except Exception:  # noqa: BLE001
            pass
        return defaut


def _borne(v):
    try:
        v = int(round(float(v)))
    except (TypeError, ValueError):
        return None
    return min(5, max(1, v)) if v else None


# ------------------------------------------------------------------ blocs
def _risques(cid):
    """Dernière évaluation de chaque risque : niveau, score et position nets."""
    m = _m()
    q = m.Risque.query.filter(m.Risque.is_archived.isnot(True))
    if cid:
        q = q.filter(m.Risque.client_id == cid)
    risques = q.all()
    ids = [r.id for r in risques]
    dernieres = {}
    if ids:
        for e in m.EvaluationRisque.query.filter(m.EvaluationRisque.risque_id.in_(ids)) \
                .order_by(m.EvaluationRisque.created_at.asc()).all():
            dernieres[e.risque_id] = e
    lignes = []
    for r in risques:
        e = dernieres.get(r.id)
        if e is not None:
            impact = _borne(e.impact_conf or e.impact_val or e.impact_pre)
            proba = _borne(e.probabilite_ajustee or e.probabilite_conf or e.probabilite_val or e.probabilite_pre)
            score = e.score_risque_net if e.score_risque_net is not None else e.score_risque
            niveau = e.niveau_risque_net or e.niveau_risque
        else:
            impact, proba = _borne(r.impact), _borne(r.probabilite)
            score, niveau = r.dernier_score_risque or r.score_risque, r.dernier_niveau_risque or r.niveau_criticite
        if impact is None:
            impact = _borne(r.impact)
        if proba is None:
            proba = _borne(r.probabilite)
        try:
            score = float(score) if score is not None else (impact * proba if impact and proba else None)
        except (TypeError, ValueError):
            score = None
        lignes.append({'risque': r, 'impact': impact, 'proba': proba, 'score': score, 'niveau': niveau or '',
                       'evalue': e is not None})
    grille = [[0] * 5 for _ in range(5)]          # grille[impact-1][proba-1]
    for l in lignes:
        if l['impact'] and l['proba']:
            grille[l['impact'] - 1][l['proba'] - 1] += 1
    critiques = [l for l in lignes if (l['niveau'] or '').lower().startswith('critique')]
    top = sorted([l for l in lignes if l['score'] is not None], key=lambda l: -l['score'])[:5]
    return {'total': len(lignes), 'critiques': len(critiques), 'grille': grille, 'top': top,
            'evalues': sum(1 for l in lignes if l['evalue'])}


def _incidents(cid):
    m = _m()
    q = m.Incident.query.filter(m.Incident.is_archived.isnot(True))
    if cid:
        q = q.filter(m.Incident.client_id == cid)
    maintenant = datetime.utcnow()
    ouverts, hors_delai = 0, 0
    par_gravite = {k: 0 for k, _ in GRAVITES}
    for i in q.all():
        if (i.statut or '').strip().lower() in FINIS_INCIDENT:
            continue
        ouverts += 1
        if i.sla_viole or (i.sla_date_limite and i.sla_date_limite < maintenant):
            hors_delai += 1
        gr = (i.gravite or '').strip().lower().replace('é', 'e')
        gr = {'majeure': 'elevee', 'haute': 'elevee', 'elevé': 'elevee', 'mineure': 'faible', 'basse': 'faible'}.get(gr, gr)
        if gr in par_gravite:
            par_gravite[gr] += 1
    return {'ouverts': ouverts, 'hors_delai': hors_delai,
            'par_gravite': [(lib, par_gravite[k], k) for k, lib in GRAVITES]}


def _plans(cid):
    from egalyx import plans_unifies
    lst = plans_unifies.lignes(cid)
    ouverts = [l for l in lst if l['etat'] in ('a_faire', 'en_cours')]
    return {'ouverts': len(ouverts), 'retard': sum(1 for l in ouverts if l['en_retard'])}


def _controles_n2(cid):
    m = _m()
    seuil = 95
    try:
        from egalyx.c2n_cartographie import reglages
        seuil = reglages(cid)['seuils'].get('conforme', 95)
    except Exception:  # noqa: BLE001
        pass
    debut = datetime(_aujourdhui().year, 1, 1)
    q = m.ExecutionControle.query.filter(m.ExecutionControle.taux_conformite.isnot(None))
    if cid:
        q = q.filter(m.ExecutionControle.client_id == cid)
    q = q.filter((m.ExecutionControle.date_execution >= debut) | (m.ExecutionControle.date_execution.is_(None)))
    taux = [e.taux_conformite for e in q.all() if e.taux_conformite is not None]
    conformes = sum(1 for t in taux if t >= seuil)
    return {'total': len(taux), 'conformes': conformes,
            'pct': round(conformes * 100 / len(taux)) if taux else None, 'seuil': seuil, 'annee': _aujourdhui().year}


def _dispositifs(cid):
    m = _m()
    q = m.DispositifMaitrise.query.filter(m.DispositifMaitrise.is_archived.isnot(True))
    if cid:
        q = q.filter(m.DispositifMaitrise.client_id == cid)
    notes = [d.efficacite_reelle for d in q.all() if d.efficacite_reelle]
    total = len(notes)
    groupes = [('Efficaces (4–5)', sum(1 for n in notes if n >= 4), '#1D4ED8'),
               ('À renforcer (3)', sum(1 for n in notes if n == 3), '#F59E0B'),
               ('Insuffisants (1–2)', sum(1 for n in notes if n <= 2), '#B42318')]
    return {'total': total, 'groupes': [(lib, n, round(n * 100 / total) if total else 0, c) for lib, n, c in groupes]}


def _il_y_a(d):
    if not d:
        return ''
    s = (datetime.utcnow() - d).total_seconds()
    if s < 3600:
        return f'il y a {max(1, int(s // 60))} min'
    if s < 86400:
        return f'il y a {int(s // 3600)} h'
    if s < 172800:
        return 'hier'
    return f'le {d.strftime("%d/%m")}'


def _activite(cid):
    m = _m()
    q = m.JournalActivite.query
    if cid:
        q = q.filter(m.JournalActivite.client_id == cid)
    q = q.filter(~m.JournalActivite.action.in_(('connexion', 'deconnexion', 'déconnexion', 'login', 'logout')))
    out, noms = [], {}
    for j in q.order_by(m.JournalActivite.date_creation.desc()).limit(5).all():
        if j.utilisateur_id not in noms:
            u = m.db.session.get(m.User, j.utilisateur_id) if j.utilisateur_id else None
            noms[j.utilisateur_id] = u.username if u else ''
        texte = (j.details if isinstance(j.details, str) else '') or (j.action or '').replace('_', ' ')
        out.append({'qui': noms[j.utilisateur_id], 'quoi': texte[:110], 'quand': _il_y_a(j.date_creation)})
    return out


def _date_du_jour():
    d = _aujourdhui()
    return f'{JOURS[d.weekday()].capitalize()} {d.day} {MOIS[d.month - 1]}'


def _client_id():
    from egalyx.commun import client_id_courant
    return client_id_courant()


def page_nouvelle():
    cid = _client_id()
    voir_risques = _peut('can_manage_risks', 'can_view_risks', 'can_validate_risks')
    voir_incidents = _peut('can_manage_incidents', 'can_view_incidents')
    voir_n2 = _peut('can_view_controle_interne_n2', 'can_manage_controle_interne_n2')
    voir_plans = _peut('can_view_action_plans', 'can_manage_action_plans') or voir_n2
    vide_r = {'total': 0, 'critiques': 0, 'grille': [[0] * 5 for _ in range(5)], 'top': [], 'evalues': 0}
    d = {
        'risques': _bloc('risques', lambda: _risques(cid), vide_r) if voir_risques else None,
        'incidents': _bloc('incidents', lambda: _incidents(cid), None) if voir_incidents else None,
        'plans': _bloc('plans', lambda: _plans(cid), None) if voir_plans else None,
        'n2': _bloc('contrôles N2', lambda: _controles_n2(cid), None) if voir_n2 else None,
        'dispositifs': _bloc('dispositifs', lambda: _dispositifs(cid), None) if voir_risques else None,
        'activite': _bloc('activité', lambda: _activite(cid), []),
    }
    try:
        from egalyx.ma_semaine import a_traiter
        attention = a_traiter(50)['total']
    except Exception:  # noqa: BLE001
        attention = 0
    return render_template('egalyx/tableau_nouveau.html', d=d, attention=attention, jour=_date_du_jour(),
                           est_admin_client=bool(getattr(current_user, 'is_client_admin', False)))


def _apres_connexion():
    """La page précédente est la connexion ou la saisie du code : on vient de se connecter."""
    ref = request.referrer or ''
    return any(x in ref for x in ('/auth/login', '/login', '/2fa/verification', '/securite/verification'))


def enregistrer(app):
    from egalyx.apparence import apparence_nouvelle

    origine_dashboard = app.view_functions.get('dashboard')
    if origine_dashboard is not None:
        def dashboard_selon_apparence(*a, **k):
            if (getattr(current_user, 'is_authenticated', False) and not getattr(current_user, 'is_operateur', False)
                    and request.args.get('vue') != 'classique' and apparence_nouvelle()
                    and _client_id()):
                return page_nouvelle()
            return origine_dashboard(*a, **k)
        dashboard_selon_apparence.__name__ = origine_dashboard.__name__
        dashboard_selon_apparence.__doc__ = origine_dashboard.__doc__
        app.view_functions['dashboard'] = dashboard_selon_apparence

    origine_admin = app.view_functions.get('client_admin_dashboard')
    if origine_admin is not None:
        def admin_selon_apparence(*a, **k):
            if (getattr(current_user, 'is_authenticated', False) and request.method == 'GET'
                    and _apres_connexion() and apparence_nouvelle()):
                return redirect(url_for('dashboard'))
            return origine_admin(*a, **k)
        admin_selon_apparence.__name__ = origine_admin.__name__
        admin_selon_apparence.__doc__ = origine_admin.__doc__
        app.view_functions['client_admin_dashboard'] = admin_selon_apparence
