"""
egalyx/organigramme_structure.py — organigramme de l'organisation (remplace la grille de cartes de /admin/organigramme).

Arbre hiérarchique : organisation → pays → pôles / filiales → directions → services, avec pour chaque niveau :
responsable (photo ou initiales, « poste à pourvoir » sinon), collaborateurs rattachés, cartographies et risques
du périmètre (cumulés vers le haut). Zoom, déplacement à la souris, recherche, plier / déplier, affichage des
collaborateurs, fiche détaillée au clic, impression A3 paysage (ou PDF via l'impression du navigateur).

  GET /admin/organigramme              la page (même adresse qu'avant)
  GET /organigramme/pays               redirige vers la page (l'arbre montre déjà les pays)
"""
from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from egalyx.commun import a_permission, client_id_courant, est_super_admin

LIBELLE_RESP = {'pays': 'Responsable pays', 'pole': 'Responsable du pôle', 'direction': 'Directeur·rice',
                'service': 'Chef·fe de service', 'organisation': 'Direction générale'}
COULEUR = {'organisation': '#0f172a', 'pays': '#0f766e', 'pole': '#4f46e5', 'direction': '#1e3a8a', 'service': '#0284c7'}


def _actifs(q, cls):
    if hasattr(cls, 'is_archived'):
        q = q.filter((cls.is_archived.is_(None)) | (cls.is_archived.is_(False)))
    if hasattr(cls, 'is_active'):
        q = q.filter((cls.is_active.is_(None)) | (cls.is_active.is_(True)))
    return q


def _client(q, cls, cid):
    return q.filter(cls.client_id == cid) if cid is not None and hasattr(cls, 'client_id') else q


def _personne(u):
    from egalyx import photo_profil
    nom = getattr(u, 'nom_affiche', None) or u.username
    mots = [m for m in nom.replace('-', ' ').split() if m]
    return {'id': u.id, 'nom': nom, 'email': u.email, 'photo': photo_profil.photo_url(u),
            'initiales': (''.join(m[0] for m in mots[:2]) or '?').upper(),
            'poste': getattr(u, 'fonction', None) or getattr(u, 'poste', None), 'compte': True}


def _responsable(obj):
    u = getattr(obj, 'responsable', None) if getattr(obj, 'responsable_id', None) else None
    if u is not None:
        return dict(_personne(u), compte=True)
    nom = (getattr(obj, 'responsable_nom_manuel', None) or '').strip()
    if nom:
        morceaux = [m for m in nom.replace('.', ' ').split() if m]
        return {'id': None, 'nom': nom, 'email': None, 'photo': None, 'compte': False,
                'initiales': ''.join(m[0] for m in morceaux[:2]).upper() or '?', 'poste': None}
    return None


def construire(cid):
    """Arbre complet + statistiques (dictionnaires prêts pour le gabarit)."""
    import models as M
    from models import db
    from sqlalchemy import func
    pays = _client(_actifs(M.Pays.query, M.Pays), M.Pays, cid).order_by(M.Pays.ordre, M.Pays.nom).all()
    poles = _client(_actifs(M.Pole.query, M.Pole), M.Pole, cid).order_by(M.Pole.ordre, M.Pole.nom).all()
    directions = _client(_actifs(M.Direction.query, M.Direction), M.Direction, cid).order_by(M.Direction.nom).all()
    ids_dir = [d.id for d in directions]
    services = _actifs(M.Service.query.filter(M.Service.direction_id.in_(ids_dir or [-1])), M.Service) \
        .order_by(M.Service.nom).all()
    gens = M.User.query.filter(M.User.client_id == cid, (M.User.is_active.is_(None)) | (M.User.is_active.is_(True))) \
        .order_by(M.User.username).all() if cid else []

    # éléments de chaque niveau (cartographies, risques)
    cartos = _client(_actifs(M.Cartographie.query, M.Cartographie), M.Cartographie, cid).all()
    q = db.session.query(M.Risque.cartographie_id, func.count(M.Risque.id))
    if hasattr(M.Risque, 'is_archived'):
        q = q.filter((M.Risque.is_archived.is_(None)) | (M.Risque.is_archived.is_(False)))
    nb_risques = dict(q.filter(M.Risque.cartographie_id.in_([c.id for c in cartos] or [-1]))
                      .group_by(M.Risque.cartographie_id).all())

    noeuds = {}

    def noeud(type_, obj, nom, couleur=None):
        n = {'cle': f'{type_}-{obj.id if obj is not None else 0}', 'type': type_, 'id': obj.id if obj is not None else None,
             'nom': nom, 'description': (getattr(obj, 'description', None) or '')[:400] if obj is not None else '',
             'responsable': _responsable(obj) if obj is not None else None, 'role': LIBELLE_RESP[type_],
             'couleur': couleur or COULEUR[type_], 'enfants': [], 'membres': [], 'equipe': [],
             'cartos': [], 'nb_risques': 0}
        noeuds[n['cle']] = n
        return n

    try:
        from models import ConfigurationOrganigramme
        conf = ConfigurationOrganigramme.query.filter_by(client_id=cid).first() if cid else None
    except Exception:  # noqa: BLE001
        conf = None
    client = M.Client.query.get(cid) if cid else None
    nom_racine = (conf.nom_entreprise if conf and conf.nom_entreprise and conf.nom_entreprise != "Nom de l'entreprise"
                  else getattr(client, 'nom', None)) or 'Organisation'
    racine = noeud('organisation', None, nom_racine)
    racine['cle'] = 'organisation-0'
    racine['logo'] = conf.logo_entreprise if conf and getattr(conf, 'logo_entreprise', None) else None

    n_pays = {p.id: noeud('pays', p, p.nom) for p in pays}
    for p in pays:
        n_pays[p.id]['drapeau'] = p.drapeau
        racine['enfants'].append(n_pays[p.id])
    n_poles = {}
    for p in poles:
        n = noeud('pole', p, p.nom, p.couleur if (p.couleur or '').startswith('#') else None)
        n_poles[p.id] = n
        (n_pays[p.pays_id]['enfants'] if p.pays_id in n_pays else racine['enfants']).append(n)
    n_dirs = {}
    for d in directions:
        parent = n_poles.get(d.pole_id)
        n = noeud('direction', d, d.nom, parent['couleur'] if parent else None)
        n_dirs[d.id] = n
        (parent['enfants'] if parent else racine['enfants']).append(n)
    n_serv = {}
    for s in services:
        n = noeud('service', s, s.nom)
        n['equipe'] = [x for x in (s.equipe_membres or []) if isinstance(x, str) and x.strip()][:50]
        n_serv[s.id] = n
        n_dirs[s.direction_id]['enfants'].append(n)

    sans_rattachement = []
    responsables = {n['responsable']['id'] for n in noeuds.values() if n.get('responsable') and n['responsable'].get('id')}
    for u in gens:
        cible = n_serv.get(u.service_id) or n_dirs.get(u.direction_id)
        if cible:
            cible['membres'].append(_personne(u))
        elif u.id not in responsables:          # un responsable de pôle figure déjà dans l'organigramme, à sa place
            sans_rattachement.append(_personne(u))

    for c in cartos:
        cible = (n_serv.get(c.service_id) or n_dirs.get(c.direction_id) or n_poles.get(getattr(c, 'pole_id', None))
                 or n_pays.get(getattr(c, 'pays_id', None)) or racine)
        cible['cartos'].append({'id': c.id, 'nom': c.nom, 'risques': nb_risques.get(c.id, 0)})
        cible['nb_risques'] += nb_risques.get(c.id, 0)

    def cumuler(n, profondeur=0):
        n['profondeur'] = profondeur
        n['effectif'] = len(n['membres']) + len(n['equipe'])
        n['total_effectif'] = n['effectif'] + sum(cumuler(e, profondeur + 1)['total_effectif'] for e in n['enfants'])
        n['total_cartos'] = len(n['cartos']) + sum(e['total_cartos'] for e in n['enfants'])
        n['total_risques'] = n['nb_risques'] + sum(e['total_risques'] for e in n['enfants'])
        n['descendants'] = len(n['enfants']) + sum(e['descendants'] for e in n['enfants'])
        return n
    # Les directions rattachées directement à l'organisation (direction générale…) viennent en premier
    racine['enfants'].sort(key=lambda e: {'direction': 0, 'pole': 1, 'pays': 2}.get(e['type'], 3))
    cumuler(racine)

    tete = [n for n in noeuds.values() if n['type'] in ('pole', 'direction', 'service')]
    pourvus = [n for n in tete if n['responsable']]
    stats = {'pays': len(pays), 'poles': len(poles), 'directions': len(directions), 'services': len(services),
             'collaborateurs': len(gens), 'rattaches': len(gens) - len(sans_rattachement),
             'postes': len(tete), 'pourvus': len(pourvus), 'vacants': len(tete) - len(pourvus),
             'encadrement': round(100 * len(pourvus) / len(tete)) if tete else 0}
    return racine, stats, sans_rattachement, noeuds


def _liens(n, peut_gerer):
    """Actions proposées dans la fiche d'un nœud (seulement les pages qui existent)."""
    def u(endpoint, **kw):
        try:
            return url_for(endpoint, **kw)
        except Exception:  # noqa: BLE001
            return None
    l = []
    if peut_gerer:
        t, i = n['type'], n['id']
        if t == 'pays':
            l += [('Modifier', u('editer_pays', id=i), 'fa-pen'), ('Ajouter un pôle', u('nouveau_pole'), 'fa-plus')]
        elif t == 'pole':
            l += [('Modifier', u('editer_pole', id=i), 'fa-pen'), ('Ajouter une direction', u('nouvelle_direction'), 'fa-plus')]
        elif t == 'direction':
            l += [('Modifier', u('modifier_direction', direction_id=i), 'fa-pen'),
                  ('Ajouter un service', u('nouveau_service', direction_id=i), 'fa-plus')]
        elif t == 'service':
            l += [('Modifier', u('modifier_service', service_id=i), 'fa-pen')]
        elif t == 'organisation':
            l += [('Ajouter une direction', u('nouvelle_direction'), 'fa-plus'), ('Ajouter un pôle', u('nouveau_pole'), 'fa-plus'),
                  ('Logo et nom', u('configurer_organigramme'), 'fa-image')]
    return [x for x in l if x[1]]


def _url_ok(endpoint, **kw):
    try:
        return url_for(endpoint, **kw)
    except Exception:  # noqa: BLE001
        return None


def page():
    if not a_permission('can_view_departments', 'can_manage_departments'):
        flash('Accès refusé', 'error')
        return redirect(url_for('dashboard'))
    cid = client_id_courant()
    racine, stats, sans, noeuds = construire(cid)
    peut_gerer = a_permission('can_manage_departments')
    details = {}
    for cle, n in noeuds.items():
        details[cle] = {
            'nom': n['nom'], 'type': n['type'], 'role': n['role'], 'description': n['description'],
            'responsable': n['responsable'], 'membres': n['membres'], 'equipe': n['equipe'],
            'cartos': [dict(c, url=_url_ok('detail_cartographie', id=c['id'])) for c in n['cartos']],
            'total_effectif': n['total_effectif'], 'total_cartos': n['total_cartos'], 'total_risques': n['total_risques'],
            'enfants': [{'cle': e['cle'], 'nom': e['nom'], 'type': e['type']} for e in n['enfants']],
            'actions': [{'libelle': a, 'url': b, 'icone': c} for a, b, c in _liens(n, peut_gerer)],
        }
    return render_template('egalyx/organigramme.html', racine=racine, stats=stats, sans_rattachement=sans,
                           details=details, peut_gerer=peut_gerer,
                           url_utilisateurs=_url_ok('client_admin_utilisateurs') if a_permission('can_manage_users', 'can_view_users_list') else None,
                           url_pdf=_url_ok('admin_organigramme_pdf'),
                           url_config=_url_ok('configurer_organigramme'),
                           url_directions=_url_ok('admin_directions'))


def par_pays():
    return redirect(url_for('admin_organigramme'))


def enregistrer(app):
    if 'admin_organigramme' in app.view_functions:
        app.view_functions['admin_organigramme'] = login_required(page)
    else:
        app.add_url_rule('/admin/organigramme', 'admin_organigramme', login_required(page))
    if 'organigramme_par_pays' in app.view_functions:
        app.view_functions['organigramme_par_pays'] = login_required(par_pays)
