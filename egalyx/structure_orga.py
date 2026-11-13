"""
egalyx/structure_orga.py — page « Structure de l'organisation » (remplace la grille de cartes de /admin/directions).

Une seule vue, lisible, de toute la structure : organisation → pays → pôles / filiales → directions → services.
Pour chaque entité : responsable (nom, fonction), collaborateurs rattachés (cumulés vers le haut), cartographies
et risques du périmètre, et les actions (ajouter une sous-entité, modifier, archiver, voir dans l'organigramme).

  GET /admin/directions            la vue choisie par la personne : arborescence (défaut) ou cartes (ancienne vue)
  GET /admin/directions?vue=arbre|cartes   bascule ; le choix est retenu (cookie, 1 an) pour les prochaines visites
  GET /admin/directions/cartes     l'ancienne vue en cartes, directement
  GET /admin/services              redirige vers la page (l'ancienne adresse affichait « Direction non spécifiée »)

Les formulaires existants (pays, pôle, direction, service) sont réutilisés ; ouverts depuis la page, ils
reviennent sur la page après l'enregistrement et se pré-remplissent avec le parent choisi
(?pays_id=…, ?pole_id=…).
"""
from urllib.parse import urlparse

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from egalyx.commun import a_permission, client_id_courant

TYPES = {
    'organisation': ('Organisation', 'fa-building'),
    'pays': ('Pays', 'fa-earth-africa'),
    'pole': ('Pôle / filiale', 'fa-layer-group'),
    'direction': ('Direction', 'fa-sitemap'),
    'service': ('Service', 'fa-users-gear'),
}
ENFANTS = {'organisation': 'entité', 'pays': 'pôle', 'pole': 'direction', 'direction': 'service', 'service': ''}
FORMULAIRES = {'nouveau_pays', 'editer_pays', 'nouveau_pole', 'editer_pole', 'nouvelle_direction', 'modifier_direction',
               'nouveau_service', 'modifier_service'}
RETOUR = '/admin/directions'


def _u(endpoint, **kw):
    try:
        return url_for(endpoint, **kw)
    except Exception:  # noqa: BLE001
        return None


def _avec_retour(url):
    if not url:
        return None
    return url + ('&' if '?' in url else '?') + 'retour=' + RETOUR


def _actions(n, peut_gerer):
    t, i = n['type'], n['id']
    a = {'ajouter': [], 'modifier': None, 'archiver': None, 'archiver_methode': 'DELETE', 'utilisateur': None}
    if not peut_gerer:
        return a
    if t == 'organisation':
        a['ajouter'] = [('Un pays', _avec_retour(_u('nouveau_pays')), 'fa-earth-africa'),
                        ('Un pôle / une filiale', _avec_retour(_u('nouveau_pole')), 'fa-layer-group'),
                        ('Une direction', _avec_retour(_u('nouvelle_direction')), 'fa-sitemap')]
    elif t == 'pays':
        a['ajouter'] = [('Un pôle / une filiale', _avec_retour(_u('nouveau_pole', pays_id=i)), 'fa-layer-group')]
        a['modifier'] = _avec_retour(_u('editer_pays', id=i))
        a['archiver'] = _u('supprimer_pays', id=i)
    elif t == 'pole':
        a['ajouter'] = [('Une direction', _avec_retour(_u('nouvelle_direction', pole_id=i)), 'fa-sitemap')]
        a['modifier'] = _avec_retour(_u('editer_pole', id=i))
        a['archiver'] = _u('supprimer_pole', id=i)
    elif t == 'direction':
        a['ajouter'] = [('Un service', _avec_retour(_u('nouveau_service', direction_id=i)), 'fa-users-gear')]
        a['modifier'] = _avec_retour(_u('modifier_direction', direction_id=i))
        a['archiver'] = _u('archiver_direction', direction_id=i)
        a['archiver_methode'] = 'POST'
    elif t == 'service':
        a['modifier'] = _avec_retour(_u('modifier_service', service_id=i))
        a['archiver'] = _u('supprimer_service', service_id=i)
    if t in ('direction', 'service') and a_permission('can_manage_users'):
        cle = 'direction_id' if t == 'direction' else 'service_id'
        a['utilisateur'] = _u('client_admin_creer_utilisateur', **{cle: i})
    a['ajouter'] = [x for x in a['ajouter'] if x[1]]
    return a


def lignes(racine, peut_gerer):
    """L'arbre à plat, dans l'ordre d'affichage (parents avant enfants)."""
    sortie = []

    def visiter(n, parent, profondeur):
        libelle, icone = TYPES[n['type']]
        sous = n['enfants']
        types_sous = {e['type'] for e in sous}
        if len(types_sous) == 1:
            t = next(iter(types_sous))
            mot = {'pays': 'pays', 'pole': 'pôle', 'direction': 'direction', 'service': 'service'}[t]
            resume_sous = f"{len(sous)} {mot}{'s' if len(sous) > 1 and not mot.endswith('s') else ''}"
        else:
            resume_sous = f"{len(sous)} entité{'s' if len(sous) > 1 else ''}" if sous else ''
        sortie.append({
            'cle': n['cle'], 'parent': parent, 'profondeur': profondeur, 'type': n['type'], 'id': n['id'],
            'libelle_type': libelle, 'icone': icone, 'nom': n['nom'], 'couleur': n['couleur'],
            'drapeau': n.get('drapeau'), 'description': n.get('description') or '',
            'responsable': n['responsable'], 'role': n['role'],
            'a_responsable': n['type'] in ('pole', 'direction', 'service'),
            'membres': n['membres'], 'equipe': n['equipe'], 'effectif': n['effectif'],
            'total_effectif': n['total_effectif'], 'total_cartos': n['total_cartos'],
            'total_risques': n['total_risques'], 'nb_enfants': len(sous), 'resume_sous': resume_sous,
            'actions': _actions(n, peut_gerer),
        })
        for e in sous:
            visiter(e, n['cle'], profondeur + 1)

    visiter(racine, None, 0)
    return sortie


def page():
    if not a_permission('can_view_departments', 'can_manage_departments'):
        flash('Accès refusé', 'error')
        return redirect(url_for('dashboard'))
    from egalyx import organigramme_structure
    racine, stats, sans, _noeuds = organigramme_structure.construire(client_id_courant())
    peut_gerer = a_permission('can_manage_departments')
    pays = [n for n in racine['enfants'] if n['type'] == 'pays']
    return render_template('egalyx/structure_orga.html', racine=racine, lignes=lignes(racine, peut_gerer),
                           stats=stats, sans_rattachement=sans, peut_gerer=peut_gerer, pays=pays,
                           peut_rattacher=a_permission('can_manage_users'),
                           url_organigramme=_u('admin_organigramme'),
                           url_archives=_u('admin_directions_archivees'),
                           url_cartes=_u('admin_directions_cartes'),
                           url_utilisateurs=_u('client_admin_utilisateurs') if a_permission('can_manage_users', 'can_view_users_list') else None,
                           ajouter=_actions(racine, peut_gerer)['ajouter'])


def services_redirige():
    return redirect(url_for('admin_directions'))


def _retour_sur(reponse):
    """Après un formulaire ouvert depuis la page : revenir sur la page (adresse locale uniquement)."""
    try:
        if request.endpoint not in FORMULAIRES or request.method != 'POST' or reponse.status_code not in (302, 303):
            return reponse
        retour = request.args.get('retour') or ''
        loc = urlparse(retour)
        if retour.startswith('/admin/') and not loc.netloc and not loc.scheme and '//' not in retour:
            cible = urlparse(reponse.headers.get('Location') or '')
            if cible.path.startswith('/admin/'):          # enregistrement réussi (une erreur réaffiche le formulaire)
                reponse.headers['Location'] = retour
    except Exception:  # noqa: BLE001
        pass
    return reponse


PREREMPLIR = """<script>(function(){var q=new URLSearchParams(location.search);
['pays_id','pole_id','direction_id'].forEach(function(k){var v=q.get(k);if(!v)return;
document.querySelectorAll('select[name="'+k+'"]').forEach(function(s){if(!s.value||s.value==='0'||s.value==='None'){s.value=v;s.dispatchEvent(new Event('change'));}});});})();</script>"""


def _preremplir(reponse):
    """Formulaire « nouveau » ouvert avec ?pays_id= / ?pole_id= : le parent est déjà choisi."""
    try:
        if (request.method == 'GET' and request.endpoint in ('nouveau_pole', 'nouvelle_direction', 'nouveau_service')
                and any(k in request.args for k in ('pays_id', 'pole_id', 'direction_id'))
                and reponse.status_code == 200 and reponse.mimetype == 'text/html' and not reponse.direct_passthrough):
            corps = reponse.get_data(as_text=True)
            if '</body>' in corps:
                reponse.set_data(corps.replace('</body>', PREREMPLIR + '</body>', 1))
    except Exception:  # noqa: BLE001
        pass
    return reponse


COOKIE_VUE = 'eg_vue_structure'
VUES = ('arbre', 'cartes')


def _avec_choix(reponse, vue):
    from flask import make_response
    reponse = make_response(reponse)
    if request.args.get('vue') in VUES or request.endpoint == 'admin_directions_cartes':
        reponse.set_cookie(COOKIE_VUE, vue, max_age=365 * 24 * 3600, samesite='Lax', httponly=True,
                           secure=request.is_secure)
    return reponse


def enregistrer(app):
    if 'admin_directions' in app.view_functions:
        ancienne = app.view_functions['admin_directions']

        def cartes():
            return _avec_choix(ancienne(), 'cartes')

        def choisir():
            vue = request.args.get('vue')
            if vue not in VUES:
                vue = request.cookies.get(COOKIE_VUE)
            if vue == 'cartes':
                return _avec_choix(ancienne(), 'cartes')
            return _avec_choix(page(), 'arbre')

        app.add_url_rule('/admin/directions/cartes', 'admin_directions_cartes', login_required(cartes))
        app.view_functions['admin_directions'] = login_required(choisir)
        app.config['EG_VUES_STRUCTURE'] = ('admin_directions_cartes',)
    else:
        app.add_url_rule('/admin/directions', 'admin_directions', login_required(page))
    if 'admin_services' in app.view_functions:
        app.view_functions['admin_services'] = login_required(services_redirige)
    app.after_request(_retour_sur)
    app.after_request(_preremplir)
