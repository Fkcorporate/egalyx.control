"""
egalyx/structure.py — les collaborateurs dans la structure de l'organisation.

1. Rattachement : chaque utilisateur peut être rattaché à une direction et/ou un service
   (User.direction_id, User.service_id). Le champ texte « Département » est rempli automatiquement.

2. Périmètre d'accès (User.perimetre_acces), choisi par l'administrateur :
     organisation (défaut : rien ne change) | pole | direction | service
   Un utilisateur limité à sa direction ne voit, dans les listes, que les éléments de sa direction
   (cartographies, risques, KRI, incidents et plans liés à ces risques, processus, veille, PCA,
   programmes d'audit, campagnes et planifications de contrôle…), plus les éléments transverses
   (sans direction) et ceux de niveau supérieur qui le concernent (son pôle, son pays).
   Une adresse directe vers un élément hors périmètre répond « introuvable », sauf si la personne
   en est responsable / évaluateur / auditeur : on n'empêche jamais quelqu'un de faire ce qu'on lui a confié.
   Administrateurs et super administrateur : jamais limités. Périmètre choisi mais rattachement
   absent : pas de limite (et l'écran de l'utilisateur le signale).
   Désactivation d'urgence : EGALYX_PERIMETRE=0.

3. Suppression d'une direction, d'un service, d'un pôle ou d'un pays : refusée tant que l'élément
   est utilisé (tous les modules, collaborateurs rattachés, sous-niveaux actifs), avec la liste exacte.

4. Un collaborateur qui part : le compte est DÉSACTIVÉ (jamais effacé : l'historique reste attribué),
   puis ses responsabilités en cours sont transférées à une autre personne
   (/client-admin/utilisateur/<id>/responsabilites).
"""
import logging
import os

from flask import Blueprint, abort, flash, g, has_request_context, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from egalyx.commun import a_permission, client_id_courant, est_admin_client, est_super_admin, journaliser

journal = logging.getLogger('egalyx.structure')
bp = Blueprint('structure', __name__)

PERIMETRES = [
    ('organisation', 'Toute l’organisation', 'Voit tous les éléments de l’organisation (selon ses permissions).'),
    ('pole', 'Son pôle / sa filiale', 'Voit les éléments des directions et services de son pôle.'),
    ('direction', 'Sa direction', 'Voit les éléments de sa direction et de ses services.'),
    ('service', 'Son service', 'Voit les éléments de son service (et ceux de sa direction qui ne visent aucun service).'),
]
LIBELLE_PERIMETRE = {c: l for c, l, _d in PERIMETRES}
NIVEAUX = (('service_id', 'services'), ('direction_id', 'directions'), ('pole_id', 'poles'), ('pays_id', 'pays'))

# Éléments portant directement leur place dans la structure
MODELES_DIRECTS = ('Cartographie', 'Processus', 'VeilleReglementaire', 'MatriceConformite', 'ProcessusActivite',
                   'DispositifMaitrise', 'ProgrammeAudit', 'PlanQualiteFonction', 'CampagneControle',
                   'PlanContinuiteActivite', 'MissionControle', 'PlanificationControle', 'RecommandationExterne')
# Libellés pour les messages « encore utilisé par… »
LIBELLES = {
    'Cartographie': 'cartographie(s)', 'Processus': 'processus', 'VeilleReglementaire': 'texte(s) de veille',
    'MatriceConformite': 'matrice(s) de conformité', 'ProcessusActivite': 'activité(s) de processus',
    'DispositifMaitrise': 'dispositif(s) de maîtrise', 'ProgrammeAudit': 'programme(s) d’audit',
    'PlanQualiteFonction': 'plan(s) qualité', 'CampagneControle': 'campagne(s) de contrôle',
    'PlanContinuiteActivite': 'plan(s) de continuité', 'MissionControle': 'mission(s) de contrôle',
    'PlanificationControle': 'planification(s) de contrôle', 'RecommandationExterne': 'recommandation(s) externe(s)',
    'ProcessusMetierDirection': 'lien(s) avec un processus métier', 'BibliothequeRisque': None,
    'User': 'collaborateur(s) rattaché(s)', 'Service': 'service(s) actif(s)', 'Direction': 'direction(s) active(s)',
    'Pole': 'pôle(s) / filiale(s) actif(s)',
}
NE_PAS_FILTRER = {'Direction', 'Service', 'Pole', 'Pays', 'User', 'BibliothequeRisque', 'ProcessusMetierDirection'}


def _m():
    import models
    return models


def _actif(q, modele):
    if hasattr(modele, 'is_archived'):
        q = q.filter((modele.is_archived.is_(None)) | (modele.is_archived.is_(False)))
    if hasattr(modele, 'deleted_at'):
        q = q.filter(modele.deleted_at.is_(None))
    return q


def _du_client(q, modele, cid):
    if cid is not None and hasattr(modele, 'client_id'):
        q = q.filter(modele.client_id == cid)
    return q


# ======================================================================= choix et rattachement
def choix_structure(cid=None):
    """Directions actives (avec pôle) et leurs services, pour les listes déroulantes."""
    M = _m()
    cid = cid if cid is not None else client_id_courant()
    q = _actif(M.Direction.query, M.Direction)
    q = _du_client(q, M.Direction, cid).filter((M.Direction.is_active.is_(None)) | (M.Direction.is_active.is_(True)))
    directions = q.order_by(M.Direction.nom).all()
    ids = [d.id for d in directions]
    services = []
    if ids:
        qs = _actif(M.Service.query.filter(M.Service.direction_id.in_(ids)), M.Service)
        services = qs.filter((M.Service.is_active.is_(None)) | (M.Service.is_active.is_(True))).order_by(M.Service.nom).all()
    par_dir = {}
    for s in services:
        par_dir.setdefault(s.direction_id, []).append(s)
    return [{'id': d.id, 'nom': d.nom, 'pole': d.pole.nom if getattr(d, 'pole', None) else None,
             'services': [{'id': s.id, 'nom': s.nom} for s in par_dir.get(d.id, [])]} for d in directions]


def entites_dirigees(u):
    """[(niveau, nom)] des pôles, directions et services actifs dont la personne est responsable (calcul une fois par page)."""
    if u is None or not getattr(u, 'id', None):
        return []
    cache = g.get('eg_dirige') if has_request_context() else None
    if cache is None or cache.get('_client') != getattr(u, 'client_id', None):
        M = _m()
        cache = {'_client': getattr(u, 'client_id', None)}
        for modele, niveau in ((M.Pole, 'Pôle'), (M.Direction, 'Direction'), (M.Service, 'Service')):
            q = _actif(modele.query.filter(modele.responsable_id.isnot(None)), modele)
            if hasattr(modele, 'is_active'):
                q = q.filter((modele.is_active.is_(None)) | (modele.is_active.is_(True)))
            if cache['_client'] is not None and hasattr(modele, 'client_id'):
                q = q.filter(modele.client_id == cache['_client'])
            for x in q.all():
                cache.setdefault(x.responsable_id, []).append((niveau, x.nom))
        if has_request_context():
            g.eg_dirige = cache
    return cache.get(u.id, [])


def affectation(u):
    """Où se trouve l'utilisateur : direction, service, pôle, pays, périmètre (+ libellés)."""
    M = _m()
    d = M.Direction.query.get(u.direction_id) if getattr(u, 'direction_id', None) else None
    s = M.Service.query.get(u.service_id) if getattr(u, 'service_id', None) else None
    if s is not None and d is None:
        d = s.direction
    pole = getattr(d, 'pole', None) if d is not None else None
    pays = getattr(pole, 'pays', None) if pole is not None else None
    per = getattr(u, 'perimetre_acces', None) or 'organisation'
    manque = (per == 'pole' and pole is None) or (per == 'direction' and d is None) or (per == 'service' and s is None)
    return {'direction': d, 'service': s, 'pole': pole, 'pays': pays, 'perimetre': per,
            'perimetre_libelle': LIBELLE_PERIMETRE.get(per, per), 'incomplet': manque, 'dirige': entites_dirigees(u),
            'libelle': ' · '.join(x.nom for x in (d, s) if x is not None)}


def appliquer_affectation(u, direction_id, service_id, perimetre, cid):
    """Enregistre le rattachement (sans commit). Renvoie un message d'erreur ou None."""
    M = _m()
    d = s = None
    if service_id:
        s = M.Service.query.get(service_id)
        if s is None or (cid and getattr(s, 'client_id', None) not in (None, cid)
                         and getattr(s.direction, 'client_id', None) != cid):
            return 'Service introuvable.'
        d = s.direction
    if direction_id and d is None:
        d = M.Direction.query.get(direction_id)
        if d is None or (cid and getattr(d, 'client_id', None) not in (None, cid)):
            return 'Direction introuvable.'
    if d is not None and direction_id and d.id != direction_id and s is not None:
        return 'Ce service n’appartient pas à la direction choisie.'
    if d is not None and cid and getattr(d, 'client_id', None) not in (None, cid):
        return 'Direction introuvable.'
    perimetre = perimetre if perimetre in LIBELLE_PERIMETRE else 'organisation'
    u.direction_id = d.id if d is not None else None
    u.service_id = s.id if s is not None else None
    u.perimetre_acces = perimetre
    if d is not None or s is not None:
        u.department = ' · '.join(x.nom for x in (d, s) if x is not None)[:100]
    return None


# ======================================================================= périmètre
def ensembles(u=None):
    """Identifiants autorisés par niveau, ou None si l'utilisateur n'est pas limité."""
    u = u or current_user
    if os.environ.get('EGALYX_PERIMETRE', '1') != '1':
        return None
    if not getattr(u, 'is_authenticated', False) or est_admin_client(u) or est_super_admin(u):
        return None
    per = getattr(u, 'perimetre_acces', None) or 'organisation'
    if per == 'organisation':
        return None
    a = affectation(u)
    if a['incomplet']:
        return None
    M = _m()
    d, s, pole, pays = a['direction'], a['service'], a['pole'], a['pays']
    E = {'pays': set(), 'poles': set(), 'directions': set(), 'services': set(), 'perimetre': per}
    if pays is not None:
        E['pays'].add(pays.id)
    if per == 'pole':
        E['poles'].add(pole.id)
        dirs = [x.id for x in M.Direction.query.filter_by(pole_id=pole.id).all()]
        E['directions'].update(dirs)
        if dirs:
            E['services'].update(x.id for x in M.Service.query.filter(M.Service.direction_id.in_(dirs)).all())
    elif per == 'direction':
        if pole is not None:
            E['poles'].add(pole.id)
        E['directions'].add(d.id)
        E['services'].update(x.id for x in M.Service.query.filter_by(direction_id=d.id).all())
    else:
        if pole is not None:
            E['poles'].add(pole.id)
        if d is not None:
            E['directions'].add(d.id)
        E['services'].add(s.id)
    return E


def structure_objet(obj, profondeur=3):
    """{'service_id': …, 'direction_id': …, 'pole_id': …, 'pays_id': …} d'un élément (ou de son parent)."""
    if obj is None or profondeur < 0:
        return {}
    st = {col: getattr(obj, col, None) for col, _k in NIVEAUX if hasattr(type(obj), col)}
    if type(obj).__name__ in MODELES_DIRECTS or any(v is not None for v in st.values()):
        return st
    M = _m()
    for attr, modele in (('cartographie_id', 'Cartographie'), ('risque_id', 'Risque'), ('processus_id', 'Processus')):
        v = getattr(obj, attr, None)
        if v:
            parent = getattr(M, modele).query.get(v)
            if parent is not None:
                return structure_objet(parent, profondeur - 1)
    return {}


def objet_visible(obj, E):
    if not E:
        return True
    st = structure_objet(obj)
    for col, cle in NIVEAUX:
        v = st.get(col)
        if v is not None and v not in E[cle]:
            return False
    return True


def _expr(cls, E):
    from sqlalchemy import and_, or_
    parties = []
    for col, cle in NIVEAUX:
        c = getattr(cls, col, None)
        if c is not None and hasattr(c, 'in_'):
            parties.append(or_(c.is_(None), c.in_(sorted(E[cle]) or [-1])))
    return and_(*parties) if parties else None


def criteres(E):
    """Options with_loader_criteria appliquées à toutes les requêtes ORM de la page."""
    from sqlalchemy import or_, select
    from sqlalchemy.orm import with_loader_criteria
    M = _m()
    opts = []
    for nom in MODELES_DIRECTS:
        cls = getattr(M, nom, None)
        e = _expr(cls, E) if cls is not None else None
        if e is not None:
            opts.append(with_loader_criteria(cls, e, include_aliases=True, propagate_to_loaders=False))
    carto = _expr(M.Cartographie, E)
    risques = select(M.Risque.id).where(or_(M.Risque.cartographie_id.is_(None),
                                            M.Risque.cartographie_id.in_(select(M.Cartographie.id).where(carto))))
    opts.append(with_loader_criteria(M.Risque, or_(M.Risque.cartographie_id.is_(None),
                                                   M.Risque.cartographie_id.in_(select(M.Cartographie.id).where(carto))),
                                     include_aliases=True, propagate_to_loaders=False))
    for nom in ('CampagneEvaluation',):
        cls = getattr(M, nom, None)
        if cls is not None and hasattr(cls, 'cartographie_id'):
            opts.append(with_loader_criteria(cls, or_(cls.cartographie_id.is_(None),
                                                      cls.cartographie_id.in_(select(M.Cartographie.id).where(carto))),
                                             include_aliases=True, propagate_to_loaders=False))
    for nom in ('KRI', 'Incident', 'PlanAction', 'EvaluationRisque'):
        cls = getattr(M, nom, None)
        if cls is not None and hasattr(cls, 'risque_id'):
            opts.append(with_loader_criteria(cls, or_(cls.risque_id.is_(None), cls.risque_id.in_(risques)),
                                             include_aliases=True, propagate_to_loaders=False))
    proc = _expr(M.Processus, E) if hasattr(M, 'Processus') else None
    if proc is not None and hasattr(M, 'Audit') and hasattr(M.Audit, 'processus_id'):
        opts.append(with_loader_criteria(M.Audit, or_(M.Audit.processus_id.is_(None),
                                                      M.Audit.processus_id.in_(select(M.Processus.id).where(proc))),
                                         include_aliases=True, propagate_to_loaders=False))
    return opts


def _filtrer(etat):
    if not has_request_context():
        return
    opts = g.get('eg_perimetre_criteres')
    if not opts or g.get('eg_perimetre_pause'):
        return
    if not etat.is_select or etat.is_column_load or etat.is_relationship_load:
        return
    etat.statement = etat.statement.options(*opts)


def _json():
    return request.path.startswith('/api/') or request.is_json or 'application/json' in (request.headers.get('Accept') or '')


def controler():
    """Avant chaque page : calcule le périmètre et refuse l'accès direct à un élément hors périmètre."""
    g.eg_perimetre = None
    g.eg_perimetre_criteres = None
    if not getattr(current_user, 'is_authenticated', False):
        return None
    try:
        E = ensembles()
    except Exception as e:  # noqa: BLE001 — ne jamais bloquer l'application pour un calcul de périmètre
        journal.warning("Périmètre non calculé pour %s : %s", getattr(current_user, 'id', '?'), e)
        return None
    if not E:
        return None
    g.eg_perimetre = E
    if request.view_args:
        from egalyx.cloisonnement import _est_en_charge, _modeles, modele_pour
        _mm, db, par_nom, _pt = _modeles()
        for param, valeur in request.view_args.items():
            if not isinstance(valeur, int):
                continue
            modele = modele_pour(request.endpoint, param, par_nom)
            if modele is None or modele.__name__ in NE_PAS_FILTRER:
                continue
            try:
                obj = db.session.get(modele, valeur)
            except Exception:  # noqa: BLE001
                continue
            if obj is None or objet_visible(obj, E):
                continue
            if _est_en_charge(obj, current_user.id):
                g.eg_perimetre_pause = True            # élément confié à la personne : page complète, sans filtre
                continue
            journal.info("Hors périmètre : utilisateur %s -> %s %s=%s", current_user.id, request.endpoint, param, valeur)
            if _json():
                return jsonify({'success': False, 'error': 'Introuvable'}), 404
            abort(404)
    g.eg_perimetre_criteres = criteres(E)
    return None


# ======================================================================= suppression d'un niveau de structure
SUPPRESSIONS = {'supprimer_direction': ('Direction', 'direction_id'), 'supprimer_service': ('Service', 'service_id'),
                'supprimer_pole': ('Pole', 'id'), 'supprimer_pays': ('Pays', 'id')}
COLONNE = {'Direction': 'direction_id', 'Service': 'service_id', 'Pole': 'pole_id', 'Pays': 'pays_id'}


def utilisations(niveau, ident, cid=None):
    """[(libellé, nombre)] des éléments actifs qui utilisent ce niveau de structure."""
    from models import db
    M = _m()
    col = COLONNE[niveau]
    total = {}
    for mapper in db.Model.registry.mappers:
        cls = mapper.class_
        nom = cls.__name__
        if nom == niveau or not hasattr(cls, col) or LIBELLES.get(nom, '') is None:
            continue
        if nom == 'Service' and niveau == 'Direction':
            continue                                  # les services suivent leur direction : vérifiés un par un
        try:
            q = _actif(cls.query.filter(getattr(cls, col) == ident), cls)
            if hasattr(cls, 'is_active') and nom in ('User', 'Direction', 'Pole', 'Service'):
                q = q.filter((cls.is_active.is_(None)) | (cls.is_active.is_(True)))
            n = q.count()
        except Exception:  # noqa: BLE001
            db.session.rollback()
            continue
        if n:
            lib = LIBELLES.get(nom) or nom
            total[lib] = total.get(lib, 0) + n
    if niveau == 'Direction':
        for s in _actif(M.Service.query.filter_by(direction_id=ident), M.Service).all():
            for lib, n in utilisations('Service', s.id, cid):
                cle = f'{lib} (service « {s.nom} »)'
                total[cle] = total.get(cle, 0) + n
    return sorted(total.items(), key=lambda x: -x[1])


def verifier_suppression():
    if request.method != 'DELETE' or request.endpoint not in SUPPRESSIONS:
        return None
    if not getattr(current_user, 'is_authenticated', False):
        return None
    niveau, param = SUPPRESSIONS[request.endpoint]
    ident = (request.view_args or {}).get(param)
    if not isinstance(ident, int):
        return None
    try:
        usages = utilisations(niveau, ident, client_id_courant())
    except Exception as e:  # noqa: BLE001
        journal.warning("Vérification avant suppression impossible (%s %s) : %s", niveau, ident, e)
        return None
    if not usages:
        return None
    nom, accord = {'Direction': ('Cette direction', 'e'), 'Service': ('Ce service', ''), 'Pole': ('Ce pôle', ''),
                   'Pays': ('Ce pays', '')}[niveau]
    detail = ', '.join(f'{n} {lib}' for lib, n in usages[:8])
    conseil = ('Archivez-la plutôt (elle restera consultable), ou rattachez d’abord ces éléments ailleurs.'
               if niveau == 'Direction' else 'Rattachez d’abord ces éléments à une autre entité.')
    return jsonify({'success': False, 'usages': [{'libelle': l, 'nombre': n} for l, n in usages],
                    'error': f'{nom} est encore utilisé{accord} : {detail}. {conseil}'}), 400


# ======================================================================= départ d'un collaborateur
CHAMPS_CHARGE = ('responsable_id', 'responsable_mesure_id', 'responsable_resolution_id', 'referent_pre_evaluation_id',
                 'validateur_id', 'evaluateur_final_id', 'evaluateur_id', 'valideur_id', 'controleur_id',
                 'validateur_requis_id', 'superviseur_id', 'directeur_id', 'auditeur_id', 'responsable_suivi_id',
                 'proprietaire_id', 'pilote_id', 'approbateur_id')
STATUTS_CLOS = {'termine', 'terminee', 'termines', 'clos', 'close', 'cloture', 'cloturee', 'clotures', 'resolu', 'resolue',
                'archive', 'archivee', 'realise', 'realisee', 'annule', 'annulee', 'abandonne', 'abandonnee', 'ferme',
                'fermee', 'complete', 'completee', 'acheve', 'achevee', 'implemente', 'mise_en_oeuvre', 'rejete',
                'rejetee', 'valide_definitif', 'confirmee', 'confirme'}
NOMS_LISIBLES = {
    'Risque': 'Risques', 'KRI': 'Indicateurs (KRI)', 'Incident': 'Incidents', 'PlanAction': 'Plans d’action',
    'SousAction': 'Sous-actions', 'Audit': 'Audits', 'Recommandation': 'Recommandations', 'Constatation': 'Constatations',
    'DispositifMaitrise': 'Dispositifs de maîtrise', 'EvaluationRisque': 'Évaluations de risques',
    'Direction': 'Directions dirigées', 'Service': 'Services dirigés', 'Pole': 'Pôles dirigés',
    'VeilleReglementaire': 'Textes de veille', 'PlanContinuiteActivite': 'Plans de continuité',
    'ActionPCA': 'Actions de PCA', 'PlanificationControle': 'Contrôles planifiés', 'MissionControle': 'Missions de contrôle',
    'Cartographie': 'Cartographies', 'Processus': 'Processus', 'ProgrammeAudit': 'Programmes d’audit',
    'TiersLCB': 'Tiers', 'Tiers': 'Tiers', 'PlanQualite': 'Plans qualité', 'ActionQualite': 'Actions qualité',
}


def _sans_accent(t):
    import unicodedata
    t = unicodedata.normalize('NFD', str(t or '').lower())
    return ''.join(c for c in t if unicodedata.category(c) != 'Mn').replace(' ', '_').replace('-', '_')


def _en_cours(obj):
    if getattr(obj, 'is_archived', False) or getattr(obj, 'deleted_at', None):
        return False
    for c in ('statut', 'status', 'etat'):
        v = getattr(obj, c, None)
        if isinstance(v, str) and v and _sans_accent(v) in STATUTS_CLOS:
            return False
    return True


def _titre(obj):
    for c in ('reference', 'code', 'titre', 'intitule', 'nom', 'libelle', 'name', 'title'):
        v = getattr(obj, c, None)
        if v:
            return str(v)[:90]
    return f'#{obj.id}'


def responsabilites(user_id, cid):
    """{(modèle, champ): [objets en cours]} des éléments confiés à la personne."""
    from models import db
    sortie = {}
    for mapper in db.Model.registry.mappers:
        cls = mapper.class_
        if cls.__name__ in ('User', 'Notification', 'JournalActiviteClient') or not hasattr(cls, 'id'):
            continue
        for champ in CHAMPS_CHARGE:
            col = getattr(cls, champ, None)
            if col is None or not hasattr(col, 'property') or not hasattr(col.property, 'columns'):
                continue
            try:
                q = cls.query.filter(col == user_id)
                if cid and hasattr(cls, 'client_id'):
                    q = q.filter((cls.client_id == cid) | (cls.client_id.is_(None)))
                objets = [o for o in q.limit(500).all() if _en_cours(o)]
            except Exception:  # noqa: BLE001
                db.session.rollback()
                continue
            if objets:
                sortie[(cls.__name__, champ)] = objets
    return sortie


def _peut_gerer_utilisateurs():
    return est_admin_client() or a_permission('can_manage_users', 'can_edit_users', 'can_deactivate_users')


def _utilisateur_du_client(id_):
    M = _m()
    u = M.User.query.get(id_)
    cid = client_id_courant()
    if u is None or (not est_super_admin() and u.client_id != cid):
        abort(404)
    return u


def desactiver_utilisateur(id):
    """Remplace la suppression définitive : désactivation + transfert des responsabilités."""
    from models import db
    if not _peut_gerer_utilisateurs():
        return jsonify({'success': False, 'error': 'Accès réservé aux administrateurs'}), 403
    u = _utilisateur_du_client(id)
    if u.id == current_user.id:
        return jsonify({'success': False, 'error': 'Vous ne pouvez pas retirer votre propre compte'}), 400
    if (u.is_client_admin or u.role in ('admin', 'super_admin')) and not est_super_admin():
        return jsonify({'success': False, 'error': 'Vous ne pouvez pas retirer un autre administrateur'}), 403
    u.is_active = False
    if hasattr(u, 'session_token'):
        u.session_token = None                 # déconnecte ses sessions ouvertes
    journaliser('desactivation_utilisateur', {'user_id': u.id, 'username': u.username, 'par': current_user.username})
    db.session.commit()
    n = sum(len(v) for v in responsabilites(u.id, u.client_id).values())
    cible = url_for('structure.responsabilites_page', id=u.id)
    msg = (f'Compte de {u.username} désactivé : il ne peut plus se connecter, son historique est conservé. '
           + (f'{n} responsabilité(s) en cours à transférer.' if n else 'Aucune responsabilité en cours.'))
    formulaire = request.mimetype in ('application/x-www-form-urlencoded', 'multipart/form-data') \
        and request.headers.get('X-Requested-With') != 'XMLHttpRequest' and not _json()
    if request.method == 'POST' and not formulaire:          # appel depuis une page (fetch) : réponse JSON
        return jsonify({'success': True, 'message': msg, 'redirect': cible if n else None, 'responsabilites': n})
    flash(msg, 'success')
    return redirect(cible)


@bp.route('/client-admin/utilisateur/<int:id>/responsabilites', methods=['GET', 'POST'])
@login_required
def responsabilites_page(id):
    from models import db
    if not _peut_gerer_utilisateurs():
        flash('Accès réservé aux administrateurs de l’organisation.', 'warning')
        return redirect(url_for('dashboard'))
    u = _utilisateur_du_client(id)
    M = _m()
    cid = u.client_id
    resp = responsabilites(u.id, cid)
    candidats = M.User.query.filter(M.User.client_id == cid, M.User.id != u.id,
                                    (M.User.is_active.is_(None)) | (M.User.is_active.is_(True))) \
        .order_by(M.User.username).all()
    if request.method == 'POST':
        cible_id = request.form.get('nouveau_responsable', type=int)
        cible = next((c for c in candidats if c.id == cible_id), None)
        choisis = set(request.form.getlist('categorie'))
        if cible is None:
            flash('Choisissez la personne qui reprend les responsabilités.', 'warning')
        elif not choisis:
            flash('Cochez au moins une catégorie à transférer.', 'warning')
        else:
            n = 0
            for (modele, champ), objets in resp.items():
                if f'{modele}.{champ}' not in choisis:
                    continue
                for o in objets:
                    setattr(o, champ, cible.id)
                    n += 1
            if request.form.get('desactiver') and u.is_active:
                u.is_active = False
            journaliser('transfert_responsabilites', {'de': u.username, 'vers': cible.username, 'elements': n,
                                                      'categories': sorted(choisis)})
            db.session.commit()
            try:
                from models import Notification
                kw = dict(type_notification='info', titre='Responsabilités transférées',
                          message=f'{n} élément(s) suivis par {u.username} vous ont été confiés par {current_user.username}.',
                          destinataire_id=cible.id, entite_type='user', entite_id=u.id)
                if hasattr(Notification, 'client_id'):
                    kw['client_id'] = cid
                db.session.add(Notification(**kw))
                db.session.commit()
            except Exception:  # noqa: BLE001
                db.session.rollback()
            flash(f'{n} élément(s) transféré(s) à {cible.username}.', 'success')
            return redirect(url_for('structure.responsabilites_page', id=u.id))
    categories = [{'cle': f'{m}.{c}', 'libelle': NOMS_LISIBLES.get(m, m), 'role': c.replace('_id', '').replace('_', ' '),
                   'n': len(o), 'exemples': [_titre(x) for x in o[:5]]}
                  for (m, c), o in sorted(resp.items(), key=lambda kv: (NOMS_LISIBLES.get(kv[0][0], kv[0][0]), kv[0][1]))]
    return render_template('egalyx/responsabilites.html', u=u, categories=categories, candidats=candidats,
                           total=sum(c['n'] for c in categories), aff=affectation(u))


# ======================================================================= formulaires utilisateur
CREATION = {'client_admin_creer_utilisateur', 'gestionnaire_creer_utilisateur'}
EDITION = {'client_admin_editer_utilisateur', 'gestionnaire_editer_utilisateur', 'admin_editer_utilisateur'}


def enregistrer_affectation_formulaire(reponse):
    """Après l'enregistrement réussi d'un formulaire utilisateur : rattachement + périmètre."""
    try:
        if request.method != 'POST' or request.endpoint not in CREATION | EDITION:
            return reponse
        if 'eg_affectation' not in request.form or reponse.status_code not in (301, 302, 303):
            return reponse
        from models import db
        M = _m()
        if request.endpoint in EDITION:
            u = M.User.query.get((request.view_args or {}).get('id'))
        else:
            nom = (request.form.get('username') or '').strip()
            u = M.User.query.filter_by(username=nom).first() if nom else None
        if u is None or (not est_super_admin() and u.client_id != getattr(current_user, 'client_id', None)):
            return reponse
        def identite():
            for champ, taille in (('prenom', 80), ('nom', 80), ('fonction', 120)):
                if f'eg_{champ}' in request.form and hasattr(u, champ):
                    setattr(u, champ, (request.form.get(f'eg_{champ}') or '').strip()[:taille] or None)
        identite()
        erreur = appliquer_affectation(u, request.form.get('eg_direction_id', type=int),
                                       request.form.get('eg_service_id', type=int),
                                       request.form.get('eg_perimetre') or 'organisation', u.client_id)
        if erreur:
            db.session.rollback()
            identite()                                   # le nom et la fonction restent enregistrés
            db.session.commit()
            flash(f'Rattachement non enregistré : {erreur}', 'warning')
        else:
            db.session.commit()
    except Exception as e:  # noqa: BLE001
        journal.warning("Rattachement non enregistré : %s", e)
        try:
            from models import db
            db.session.rollback()
        except Exception:  # noqa: BLE001
            pass
    return reponse


def mettre_a_jour_profil():
    """/profil/update : identité, e-mail, mot de passe — sans page d'erreur si le mot de passe est trop faible."""
    import re
    from models import db
    M = _m()
    u = current_user
    f = request.form
    for champ, taille in (('prenom', 80), ('nom', 80), ('fonction', 120)):
        if champ in f and hasattr(u, champ):
            setattr(u, champ, (f.get(champ) or '').strip()[:taille] or None)
    if 'email' in f:
        email = (f.get('email') or '').strip()
        if email != (u.email or ''):
            if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
                flash('Adresse e-mail invalide : elle n’a pas été modifiée.', 'error')
            elif M.User.query.filter(M.User.email == email, M.User.id != u.id).first():
                flash('Cette adresse e-mail est déjà utilisée par un autre compte.', 'error')
            else:
                u.email = email
    if 'department' in f and not getattr(u, 'direction_id', None):
        u.department = (f.get('department') or '').strip()[:100] or u.department
    nouveau = (f.get('new_password') or '').strip()
    if nouveau:
        if nouveau != (f.get('confirm_password') or '').strip():
            db.session.rollback()
            flash('Les deux mots de passe ne correspondent pas.', 'error')
            return redirect(url_for('profil_utilisateur'))
        try:
            u.set_password(nouveau)
        except ValueError as e:
            db.session.rollback()
            flash(f'Mot de passe non modifié : {e}.', 'error')
            return redirect(url_for('profil_utilisateur'))
    try:
        db.session.commit()
        flash('Mot de passe mis à jour.' if nouveau else 'Profil mis à jour.', 'success')
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        journal.warning('Profil non enregistré (%s) : %s', getattr(u, 'id', '?'), e)
        flash('Le profil n’a pas pu être enregistré. Réessayez.', 'error')
    return redirect(url_for('profil_utilisateur'))


def nouvel_utilisateur_redirige():
    """Une seule page de création : /client-admin/utilisateur/nouveau -> /client-admin/utilisateur/creer."""
    return redirect(url_for('client_admin_creer_utilisateur', **request.args), code=302 if request.method == 'GET' else 307)


def enregistrer(app):
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    app.register_blueprint(bp)
    if not getattr(app, '_eg_perimetre_ecoute', False):
        event.listen(Session, 'do_orm_execute', _filtrer)
        app._eg_perimetre_ecoute = True
    app.before_request(controler)
    app.before_request(verifier_suppression)
    app.after_request(enregistrer_affectation_formulaire)
    for ancien in ('client_api_delete_user', 'gestionnaire_supprimer_utilisateur', 'admin_supprimer_utilisateur'):
        if ancien in app.view_functions:
            app.view_functions[ancien] = login_required(desactiver_utilisateur)
    if 'update_profil' in app.view_functions:
        app.view_functions['update_profil'] = login_required(mettre_a_jour_profil)
    if 'client_admin_nouvel_utilisateur' in app.view_functions and 'client_admin_creer_utilisateur' in app.view_functions:
        app.view_functions['client_admin_nouvel_utilisateur'] = login_required(nouvel_utilisateur_redirige)
    app.jinja_env.globals.update(eg_structure_choix=choix_structure, eg_affectation=affectation,
                                 eg_perimetres=PERIMETRES)
