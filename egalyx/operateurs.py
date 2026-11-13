"""
egalyx/operateurs.py — espace opérateur : chaque droit fait ce qu'il dit, sur chaque page.

1. Droits (PermissionOperateur), affichés et modifiables par l'administrateur, par familles :
     Risques    : évaluer les risques · voir les dispositifs de maîtrise
     Campagnes  : voir · créer et réaliser · valider ou rejeter
     Plans      : voir ses plans · les faire avancer (sous-actions, pièces jointes, commentaires)
   Périmètre : directions, services et catégories de risques autorisés (vide = pas de limite sur cet axe).

2. Contrôle à l'entrée de CHAQUE page de l'espace opérateur (adresse tapée à la main comprise) :
   le droit nécessaire, puis l'élément demandé (risque, campagne et ce qui en dépend) dans le périmètre,
   avec les mêmes règles que les listes de l'espace opérateur. Ce qui est confié à la personne reste
   toujours accessible (campagne dont elle est créatrice / réalisatrice / valideuse ; risque dont elle est
   valideur désigné des évaluations ; plans dont elle est responsable — vérifié par la page elle-même).
   Refus : message clair et retour au tableau de bord (403 en JSON pour les appels de la page).
   Les gestionnaires qui utilisent les mêmes adresses (valider / rejeter / rouvrir une campagne) ne sont pas concernés.

3. Mise à niveau, une seule fois : les opérateurs existants reçoivent les droits qui n'étaient pas appliqués
   jusqu'ici (valider les campagnes, faire avancer les plans, voir les dispositifs, voir campagnes et plans) :
   personne ne perd d'accès le jour de l'installation.

4. Écrans d'administration : liste des opérateurs, ajout (collaborateur existant), page de droits unique
   (ajout et modification), retrait du rôle.
"""
import logging
from datetime import datetime

from flask import abort, flash, g, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from egalyx.commun import client_id_courant, est_admin_client, est_super_admin, journaliser

journal = logging.getLogger('egalyx.operateurs')

DROITS = [
    ('risques', 'Risques', 'fa-triangle-exclamation', [
        ('peut_evaluer_risques', 'Évaluer les risques', 'Pré-évaluation (phase 1) des risques de son périmètre.'),
        ('peut_voir_dispositifs', 'Voir les dispositifs de maîtrise', 'Les contrôles du risque, dans la fiche du risque.'),
    ]),
    ('campagnes', 'Campagnes de contrôle', 'fa-clipboard-list', [
        ('peut_voir_campagnes', 'Voir les campagnes', 'Celles qui lui sont confiées ou de son périmètre : détail, statistiques, pièces.'),
        ('peut_executer_campagnes', 'Créer et réaliser des campagnes', 'Créer, démarrer, exécuter, relever les anomalies, joindre des pièces.'),
        ('peut_valider_campagnes', 'Valider ou rejeter les campagnes', 'Quand il en est le valideur désigné (jamais sur sa propre campagne).'),
    ]),
    ('plans', 'Plans d’action', 'fa-list-check', [
        ('peut_voir_plans_action', 'Voir ses plans d’action', 'Ceux dont il est responsable ou qu’il a créés.'),
        ('peut_executer_plans_action', 'Faire avancer ses plans', 'Sous-actions, avancement, pièces jointes, commentaires.'),
    ]),
]
TOUS_DROITS = [c for _g, _l, _i, ds in DROITS for c, _a, _b in ds]
LIBELLE = {c: a for _g, _l, _i, ds in DROITS for c, a, _b in ds}
# Un droit d'action suppose le droit de voir
SUPPOSE = {'peut_executer_campagnes': 'peut_voir_campagnes', 'peut_valider_campagnes': 'peut_voir_campagnes',
           'peut_executer_plans_action': 'peut_voir_plans_action'}
# Droits jamais appliqués avant cette version : accordés aux opérateurs existants lors de la mise à niveau
NOUVEAUX = ('peut_valider_campagnes', 'peut_executer_plans_action', 'peut_voir_dispositifs', 'peut_voir_campagnes',
            'peut_voir_plans_action')
MISE_A_NIVEAU = 'operateurs_droits_v2'

# page -> (droit nécessaire, élément contrôlé)
CAMP = 'campagne'
PAGES = {
    'operateur_detail_risque': (None, 'risque'),
    'operateur_evaluer_risque': ('peut_evaluer_risques', 'risque'),
    'operateur_liste_campagnes': ('peut_voir_campagnes', None),
    'operateur_detail_campagne': ('peut_voir_campagnes', CAMP),
    'operateur_statistiques_campagne': ('peut_voir_campagnes', CAMP),
    'operateur_telecharger_fichier_campagne': ('peut_voir_campagnes', 'fichier_campagne'),
    'operateur_creer_campagne': ('peut_executer_campagnes', None),
    'operateur_modifier_campagne': ('peut_executer_campagnes', CAMP),
    'operateur_demarrer_campagne': ('peut_executer_campagnes', CAMP),
    'operateur_executer_campagne': ('peut_executer_campagnes', CAMP),
    'operateur_gerer_anomalies': ('peut_executer_campagnes', CAMP),
    'operateur_ajouter_anomalie': ('peut_executer_campagnes', CAMP),
    'operateur_supprimer_anomalie': ('peut_executer_campagnes', CAMP),
    'operateur_modifier_anomalie': ('peut_executer_campagnes', 'anomalie'),
    'operateur_ecarter_anomalie': ('peut_executer_campagnes', 'anomalie'),
    'operateur_upload_fichier_campagne': ('peut_executer_campagnes', CAMP),
    'operateur_supprimer_fichier_campagne': ('peut_executer_campagnes', 'fichier_campagne'),
    'operateur_rouvrir_campagne': ('peut_executer_campagnes', CAMP),
    'operateur_valider_campagne': ('peut_valider_campagnes', CAMP),
    'rejeter_campagne': ('peut_valider_campagnes', CAMP),
    'operateur_plans_action': ('peut_voir_plans_action', None),
    'operateur_suivre_plan_action': ('peut_voir_plans_action', None),          # POST : faire avancer (voir plus bas)
    'operateur_telecharger_fichier_plan': ('peut_voir_plans_action', None),
    'operateur_ajouter_sous_action': ('peut_executer_plans_action', None),
    'operateur_terminer_sous_action': ('peut_executer_plans_action', None),
    'operateur_supprimer_sous_action': ('peut_executer_plans_action', None),
    'operateur_supprimer_commentaire': ('peut_executer_plans_action', None),
    'operateur_ajouter_fichier_plan': ('peut_executer_plans_action', None),
    'operateur_supprimer_fichier_plan': ('peut_executer_plans_action', None),
    'operateur_commenter_plan_action': ('peut_executer_plans_action', None),
}


def _m():
    import models
    return models


def droits_de(u=None):
    """PermissionOperateur de l'utilisateur (ou None)."""
    u = u or current_user
    if not getattr(u, 'is_operateur', False):
        return None
    M = _m()
    p = None
    if getattr(u, 'operateur_permissions_id', None):
        p = M.db.session.get(M.PermissionOperateur, u.operateur_permissions_id)
    if p is None:
        p = M.PermissionOperateur.query.filter_by(user_id=u.id).first()
    return p


def a_droit(p, droit):
    if p is None or not droit:
        return p is not None
    return bool(getattr(p, droit, False))


def _liste(v):
    return [x for x in (v or []) if x not in (None, '', 0)]


# ------------------------------------------------------------------ périmètre
def risque_dans_perimetre(p, risque):
    """Mêmes règles que la liste « Risques » de l'espace opérateur."""
    M = _m()
    carto = M.db.session.get(M.Cartographie, risque.cartographie_id) if risque.cartographie_id else None
    dirs, servs, types = _liste(p.directions_autorisees), _liste(p.services_autorises), _liste(p.types_risques_autorises)
    if dirs and (carto is None or carto.direction_id not in dirs):
        return False
    if servs and (carto is None or carto.service_id not in servs):
        return False
    if types and getattr(risque, 'type_risque', None) not in types:
        return False
    return True


def risque_confie(u, risque):
    """Valideur désigné des évaluations des opérateurs pour ce risque."""
    try:
        from egalyx.parametres_risque import valideur_operateurs
        v = valideur_operateurs(u.client_id, risque.cartographie_id)
        return v is not None and v.id == u.id
    except Exception:  # noqa: BLE001
        return False


def campagne_accessible(u, p, c):
    """Mêmes règles que la fiche d'une campagne : confiée à la personne, ou dans ses directions / services."""
    if u.id in (getattr(c, 'createur_id', None), getattr(c, 'evaluateur_id', None), getattr(c, 'valideur_id', None)):
        return True
    dirs, servs = _liste(p.directions_autorisees), _liste(p.services_autorises)
    if dirs and getattr(c, 'direction_id', None) in dirs:
        return True
    if servs and getattr(c, 'service_id', None) in servs:
        return True
    return False


def _element(nature):
    """L'élément demandé par l'adresse (ou None s'il n'existe pas : la page répondra elle-même)."""
    M = _m()
    va = request.view_args or {}
    s = M.db.session
    if nature == 'risque' and va.get('risque_id'):
        return 'risque', s.get(M.Risque, va['risque_id'])
    if nature == CAMP and va.get('campagne_id'):
        return CAMP, s.get(M.CampagneControle, va['campagne_id'])
    if nature == 'anomalie' and va.get('anomalie_id'):
        a = s.get(M.AnomalieDetectee, va['anomalie_id'])
        cid = getattr(a, 'campagne_id', None) if a is not None else None
        return CAMP, (s.get(M.CampagneControle, cid) if cid else None)
    if nature == 'fichier_campagne' and va.get('fichier_id'):
        f = s.get(M.FichierCampagneControle, va['fichier_id'])
        cid = getattr(f, 'campagne_id', None) if f is not None else None
        return CAMP, (s.get(M.CampagneControle, cid) if cid else None)
    return None, None


def _refus(message):
    journal.info("Espace opérateur : refus pour %s sur %s (%s)", getattr(current_user, 'id', '?'), request.endpoint, message)
    appel_page = (request.method != 'GET' and (request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                  or 'application/json' in (request.headers.get('Accept') or '') or request.method == 'DELETE'))
    if appel_page or request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': message}), 403
    flash(message, 'error')
    return redirect(url_for('operateur_dashboard'))


def controler():
    ep = request.endpoint or ''
    if ep not in PAGES or not getattr(current_user, 'is_authenticated', False) or not getattr(current_user, 'is_operateur', False):
        return None
    p = droits_de()
    if p is None:
        return None                                  # la page elle-même répond « permissions introuvables »
    droit, nature = PAGES[ep]
    if ep == 'operateur_suivre_plan_action' and request.method == 'POST':
        droit = 'peut_executer_plans_action'
    genre, obj = _element(nature) if nature else (None, None)
    if obj is not None and getattr(obj, 'client_id', None) not in (None, current_user.client_id):
        return _refus("Vous n'avez pas accès à cet élément.")
    if genre == 'risque' and obj is not None:
        confie = risque_confie(current_user, obj)
        if ep == 'operateur_evaluer_risque' and confie:
            return None                              # le valideur désigné ouvre l'évaluation pour la valider
        if not confie and not risque_dans_perimetre(p, obj):
            return _refus("Vous n'avez pas accès à ce risque : il est en dehors de votre périmètre.")
    if droit and not a_droit(p, droit):
        return _refus(f"Votre profil d'opérateur ne permet pas cette action ({LIBELLE.get(droit, droit).lower()}). "
                      "Demandez à votre administrateur si nécessaire.")
    if genre == CAMP and obj is not None and not campagne_accessible(current_user, p, obj):
        return _refus("Vous n'avez pas accès à cette campagne : elle ne vous est pas confiée et n'est pas dans votre périmètre.")
    return None


# ------------------------------------------------------------------ mise à niveau
def mettre_a_niveau():
    """Une seule fois : les opérateurs existants gardent tout ce qu'ils pouvaient faire."""
    if g.get('_eg_op_niveau_vu'):
        return None
    g._eg_op_niveau_vu = True
    try:
        from egalyx import ia
        if ia.reglages().get(MISE_A_NIVEAU):
            return None
        M = _m()
        n = 0
        for p in M.PermissionOperateur.query.all():
            for d in NOUVEAUX:
                if not getattr(p, d, False):
                    setattr(p, d, True)
            n += 1
        M.db.session.commit()
        ia.ecrire_reglage(MISE_A_NIVEAU, datetime.utcnow().isoformat(timespec='seconds'))
        journal.warning("Opérateurs : mise à niveau des droits faite pour %s opérateur(s)", n)
    except Exception as e:  # noqa: BLE001
        journal.warning("Opérateurs : mise à niveau des droits non faite (%s)", e)
        try:
            _m().db.session.rollback()
        except Exception:  # noqa: BLE001
            pass
    return None


# ------------------------------------------------------------------ administration
def _peut_administrer():
    return est_admin_client() or est_super_admin()


def _structure(cid):
    M = _m()
    dirs = M.Direction.query.filter_by(client_id=cid).filter(
        (M.Direction.is_archived.is_(None)) | (M.Direction.is_archived.is_(False))).order_by(M.Direction.nom).all()
    servs = M.Service.query.filter(M.Service.direction_id.in_([d.id for d in dirs] or [-1])).filter(
        (M.Service.is_archived.is_(None)) | (M.Service.is_archived.is_(False))).order_by(M.Service.nom).all()
    par_dir = {}
    for s in servs:
        par_dir.setdefault(s.direction_id, []).append(s)
    groupes = {}
    for d in dirs:
        groupes.setdefault(d.pole.nom if getattr(d, 'pole', None) else 'Directions rattachées à l’organisation', []).append(
            {'id': d.id, 'nom': d.nom, 'services': [{'id': s.id, 'nom': s.nom} for s in par_dir.get(d.id, [])]})
    types = sorted({t for (t,) in M.db.session.query(M.Risque.type_risque).filter(
        M.Risque.client_id == cid, M.Risque.type_risque.isnot(None)).distinct().all() if t and t.strip()})
    noms_dirs = {d.id: d.nom for d in dirs}
    noms_servs = {s.id: s.nom for s in servs}
    return groupes, types, noms_dirs, noms_servs


def resume_perimetre(p, noms_dirs, noms_servs):
    dirs, servs, types = _liste(p.directions_autorisees), _liste(p.services_autorises), _liste(p.types_risques_autorises)
    morceaux = []
    if dirs:
        morceaux.append(', '.join(noms_dirs.get(i, 'direction archivée') for i in dirs))
    if servs:
        morceaux.append('services : ' + ', '.join(noms_servs.get(i, 'service archivé') for i in servs))
    if types:
        morceaux.append('catégories : ' + ', '.join(types))
    return morceaux or ['Toute l’organisation']


def page_operateurs():
    if not _peut_administrer():
        flash('Accès non autorisé', 'error')
        return redirect(url_for('dashboard'))
    M = _m()
    cid = client_id_courant()
    operateurs = M.User.query.filter_by(client_id=cid, is_operateur=True).all()
    operateurs.sort(key=lambda u: (not u.is_active, u.nom_affiche.lower()))
    candidats = M.User.query.filter(M.User.client_id == cid, M.User.is_active.is_(True),
                                    (M.User.is_operateur.is_(None)) | (M.User.is_operateur.is_(False)),
                                    M.User.role.notin_(['admin', 'super_admin'])).all()
    candidats = [u for u in candidats if not getattr(u, 'is_client_admin', False)]
    candidats.sort(key=lambda u: u.nom_affiche.lower())
    _g, _t, noms_dirs, noms_servs = _structure(cid)
    lignes = []
    for u in operateurs:
        p = droits_de(u)
        lignes.append({'u': u, 'p': p,
                       'perimetre': resume_perimetre(p, noms_dirs, noms_servs) if p else ['Droits à définir'],
                       'droits': [(LIBELLE[d], g_) for g_, _l, _i, ds in DROITS for d, _a, _b in ds if p is not None and getattr(p, d, False)]})
    try:
        from egalyx.structure import affectation
    except ImportError:  # pragma: no cover
        affectation = None
    return render_template('egalyx/operateurs_admin.html', lignes=lignes, candidats=candidats, droits=DROITS,
                           affectation=affectation,
                           url_creer=_url('client_admin_creer_utilisateur'))


def _url(endpoint, **kw):
    try:
        return url_for(endpoint, **kw)
    except Exception:  # noqa: BLE001
        return None


def _lire_formulaire(p, f):
    """Droits et périmètre depuis le formulaire (nouveaux noms et anciens noms acceptés)."""
    for d in TOUS_DROITS:
        setattr(p, d, f.get(d) in ('on', '1', 'true', 'y'))
    for action, voir in SUPPOSE.items():
        if getattr(p, action):
            setattr(p, voir, True)
    p.peut_creer_plans_action = bool(p.peut_executer_plans_action)        # ancien nom, gardé cohérent
    p.peut_voir_evaluations = True
    p.peut_modifier_evaluations = bool(p.peut_evaluer_risques)
    if hasattr(p, 'peut_evaluer_dispositifs') and p.peut_evaluer_dispositifs is None:
        p.peut_evaluer_dispositifs = False

    def entiers(nom):
        return sorted({int(x) for x in (f.getlist(nom) or f.getlist(nom + '[]')) if str(x).isdigit()})
    p.directions_autorisees = entiers('directions')
    p.services_autorises = entiers('services')
    p.types_risques_autorises = sorted({t.strip() for t in (f.getlist('types_risques') or f.getlist('types_risques[]')) if t.strip()})


def _cible(user_id, cid):
    M = _m()
    u = M.db.session.get(M.User, user_id) if user_id else None
    if u is None or (not est_super_admin() and u.client_id != cid):
        abort(404)
    return u


def page_droits(user_id):
    """Droits d'un opérateur (modification) — même page que pour l'ajout."""
    if not _peut_administrer():
        flash('Accès non autorisé', 'error')
        return redirect(url_for('dashboard'))
    cid = client_id_courant()
    u = _cible(user_id, cid)
    if not u.is_operateur:
        return redirect(url_for('operateur_nouveau', user_id=u.id))
    M = _m()
    p = droits_de(u)
    if p is None:
        p = M.PermissionOperateur(user_id=u.id, client_id=u.client_id, created_by=current_user.id)
        M.db.session.add(p)
    if request.method == 'POST':
        _lire_formulaire(p, request.form)
        p.updated_at = datetime.utcnow() if hasattr(p, 'updated_at') else None
        M.db.session.flush()
        u.operateur_permissions_id = p.id
        M.db.session.commit()
        journaliser('operateur_droits', {'user_id': u.id, 'par': current_user.username,
                                         'droits': [d for d in TOUS_DROITS if getattr(p, d)]})
        flash(f'Droits de {u.nom_affiche} enregistrés.', 'success')
        return redirect(url_for('admin_operateurs'))
    return _formulaire(u, p, nouveau=False)


def page_nouveau():
    """Ajouter un opérateur : choisir un collaborateur existant, puis ses droits et son périmètre."""
    if not _peut_administrer():
        flash('Accès non autorisé', 'error')
        return redirect(url_for('dashboard'))
    cid = client_id_courant()
    uid = request.values.get('user_id', type=int)
    if not uid:
        flash('Choisissez le collaborateur à faire opérateur.', 'warning')
        return redirect(url_for('admin_operateurs'))
    u = _cible(uid, cid)
    if u.is_operateur:
        return redirect(url_for('admin_operateur_permissions', user_id=u.id))
    if u.role in ('admin', 'super_admin') or getattr(u, 'is_client_admin', False):
        flash('Un administrateur ne peut pas devenir opérateur.', 'error')
        return redirect(url_for('admin_operateurs'))
    M = _m()
    if request.method == 'POST':
        return promouvoir()
    p = M.PermissionOperateur(user_id=u.id, client_id=u.client_id)
    for d in TOUS_DROITS:                                    # proposition par défaut, modifiable
        setattr(p, d, d in ('peut_evaluer_risques', 'peut_voir_dispositifs', 'peut_voir_campagnes',
                            'peut_executer_campagnes', 'peut_voir_plans_action', 'peut_executer_plans_action'))
    if getattr(u, 'direction_id', None):
        p.directions_autorisees = [u.direction_id]
    if getattr(u, 'service_id', None):
        p.services_autorises = [u.service_id]
    p.types_risques_autorises = []
    return _formulaire(u, p, nouveau=True)


def promouvoir():
    """POST /admin/operateur/promouvoir (et le formulaire « ajouter un opérateur »)."""
    if not _peut_administrer():
        flash('Accès non autorisé', 'error')
        return redirect(url_for('dashboard'))
    M = _m()
    cid = client_id_courant()
    u = _cible(request.form.get('user_id', type=int), cid)
    if u.role in ('admin', 'super_admin') or getattr(u, 'is_client_admin', False):
        flash('Un administrateur ne peut pas devenir opérateur.', 'error')
        return redirect(url_for('admin_operateurs'))
    p = droits_de(u) or M.PermissionOperateur.query.filter_by(user_id=u.id).first()
    if p is None:
        p = M.PermissionOperateur(user_id=u.id, client_id=u.client_id, created_by=current_user.id)
        M.db.session.add(p)
    _lire_formulaire(p, request.form)
    M.db.session.flush()
    u.is_operateur = True
    u.operateur_permissions_id = p.id
    M.db.session.commit()
    journaliser('promotion_operateur', {'user_id': u.id, 'par': current_user.username})
    flash(f'{u.nom_affiche} est maintenant opérateur. Il retrouve son espace opérationnel à sa prochaine page.', 'success')
    return redirect(url_for('admin_operateurs'))


def retrograder(user_id):
    """Retirer le rôle d'opérateur (le compte et son historique restent)."""
    if not _peut_administrer():
        flash('Accès non autorisé', 'error')
        return redirect(url_for('dashboard'))
    M = _m()
    u = _cible(user_id, client_id_courant())
    p = droits_de(u)
    if p is not None:
        M.db.session.delete(p)
    u.is_operateur = False
    u.operateur_permissions_id = None
    M.db.session.commit()
    journaliser('retrait_operateur', {'user_id': u.id, 'par': current_user.username})
    flash(f'{u.nom_affiche} n’est plus opérateur : il retrouve l’interface standard (selon ses permissions).', 'success')
    return redirect(url_for('admin_operateurs'))


def _formulaire(u, p, nouveau):
    groupes, types, _nd, _ns = _structure(u.client_id)
    return render_template('egalyx/operateur_droits.html', u=u, p=p, nouveau=nouveau, droits=DROITS, groupes=groupes,
                           types=types, suppose=SUPPOSE,
                           dirs=set(_liste(p.directions_autorisees)), servs=set(_liste(p.services_autorises)),
                           cats=set(_liste(p.types_risques_autorises)))


def enregistrer(app):
    app.before_request(mettre_a_niveau)
    app.before_request(controler)
    app.add_url_rule('/admin/operateur/nouveau', 'operateur_nouveau', login_required(page_nouveau), methods=['GET', 'POST'])
    for ep, vue in (('admin_operateurs', page_operateurs), ('promouvoir_operateur', promouvoir),
                    ('retrograder_operateur', retrograder), ('admin_operateur_permissions', page_droits)):
        if ep in app.view_functions:
            app.view_functions[ep] = login_required(vue)
    app.jinja_env.globals.update(eg_droits_operateur=droits_de)
