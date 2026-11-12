"""Gestion des clients par le super admin : suppression définitive, réinitialisation des données, export,
synchronisation des permissions.

Les boutons de la fiche client (« Résilier le client », « Réinitialiser les données », « Exporter les données »,
« Synchroniser les permissions ») appelaient des adresses qui n'existaient pas : rien ne se passait.

Suppression : toutes les lignes de l'organisation sont retrouvées table par table (colonne client_id), puis toutes
les lignes qui en dépendent par clé étrangère, même sans client_id (tables d'association, sous-éléments…).
Les liens qui pointent vers ces lignes depuis des lignes conservées (journaux du super admin…) sont remis à vide.
On ne travaille qu'avec les tables et colonnes qui existent vraiment dans la base. Tout se fait dans une seule
transaction : en cas d'erreur, rien n'est supprimé.
"""
import os
import io
import json
import zipfile
from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, jsonify, request, send_file, session
from flask_login import current_user
from sqlalchemy import inspect as sa_inspect

from egalyx.commun import super_admin_requis

bp = Blueprint('gestion_clients', __name__)

# Réinitialisation : ce qui est conservé (l'organisation, ses comptes, son organigramme et ses réglages).
CONSERVES_REINITIALISATION = {
    'clients', 'user', 'users', 'poles', 'direction', 'service', 'parametres_risque', 'permission_operateur',
    'permissions_operateurs', 'abonnements_clients', 'abonnement_client', 'reglages_egalyx', 'environnements_clients',
    'client_environment', 'cles_api', 'api_keys',
}


def _tables_reelles():
    """Tables et colonnes telles qu'elles existent dans la base (et non telles que le code les décrit)."""
    meta = _meta_reelle()
    return set(meta.tables), {n: {c.name for c in t.c} for n, t in meta.tables.items()}


def _meta_reelle():
    """Structure lue dans la base : clés étrangères et colonnes obligatoires réelles (une ancienne base peut
    avoir des liens que le code ne déclare plus, ou l'inverse)."""
    from sqlalchemy import MetaData
    from models import db
    meta = MetaData()
    meta.reflect(bind=db.engine)
    return meta


def _tables_triees():
    import warnings
    meta = _meta_reelle()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return list(meta.sorted_tables)


def _cle_primaire(table):
    pk = list(table.primary_key.columns)
    return pk[0].name if len(pk) == 1 else None


def plan_suppression(client_id, conserver=()):
    """Calcule, sans rien modifier, les lignes à supprimer et les liens à vider.
    Renvoie (a_supprimer: {table: set(ids)}, assoc: {table: [(col, table_parent)]}, compte: {table: n})."""
    from models import db
    tables = _tables_triees()
    colonnes = {t.name: {c.name for c in t.c} for t in tables}
    par_nom = {t.name: t for t in tables}
    a_supprimer = {}

    def ids(table, condition):
        pk = _cle_primaire(table)
        if not pk or pk not in colonnes[table.name]:
            return set()
        return {r[0] for r in db.session.execute(db.select(table.c[pk]).where(condition)).all()}

    # 1. Lignes de l'organisation
    if 'clients' in par_nom and 'clients' not in conserver:
        a_supprimer['clients'] = {client_id}
    for t in tables:
        if t.name in conserver or t.name == 'clients':
            continue
        if 'client_id' in t.c and 'client_id' in colonnes[t.name]:
            trouve = ids(t, t.c.client_id == client_id)
            if trouve:
                a_supprimer.setdefault(t.name, set()).update(trouve)

    # 2. Lignes qui dépendent de celles-ci (clé étrangère obligatoire), jusqu'à stabilité
    change = True
    while change:
        change = False
        for t in tables:
            if t.name in conserver or not _cle_primaire(t):
                continue
            for fk in t.foreign_keys:
                parent = fk.column.table.name
                col = fk.parent
                if parent not in a_supprimer or col.name not in colonnes[t.name] or col.nullable:
                    continue
                cibles = a_supprimer[parent]
                if not cibles:
                    continue
                trouve = ids(t, col.in_(list(cibles))) - a_supprimer.get(t.name, set())
                if trouve:
                    a_supprimer.setdefault(t.name, set()).update(trouve)
                    change = True
    compte = {k: len(v) for k, v in a_supprimer.items() if v}
    return a_supprimer, compte


def _ordre_suppression(tables, colonnes, a_supprimer):
    """Tables concernées, chaque table avant celles qu'elle référence par un lien obligatoire."""
    concernees = [t for t in tables if a_supprimer.get(t.name)]
    noms = {t.name for t in concernees}
    attend = {t.name: set() for t in concernees}      # table -> tables qui doivent être vidées AVANT elle
    for t in concernees:
        for fk in t.foreign_keys:
            parent = fk.column.table.name
            if parent in noms and parent != t.name and not fk.parent.nullable and fk.parent.name in colonnes[t.name]:
                attend[parent].add(t.name)
    ordre, restant = [], dict(attend)
    while restant:
        prets = [n for n, deps in restant.items() if not (deps & set(restant))]
        if not prets:                               # vraie boucle de liens obligatoires : ordre par défaut
            prets = [n for n in (x.name for x in reversed(concernees)) if n in restant]
        for n in prets:
            ordre.append(n)
            restant.pop(n)
    par_nom = {t.name: t for t in concernees}
    return [par_nom[n] for n in ordre]


def executer_suppression(client_id, conserver=()):
    """Supprime l'organisation (ou seulement ses données si `conserver` est fourni). Une seule transaction."""
    from models import db
    tables = _tables_triees()
    colonnes = {t.name: {c.name for c in t.c} for t in tables}
    a_supprimer, compte = plan_suppression(client_id, conserver)
    try:
        # a. Vider les liens facultatifs qui pointent vers une ligne supprimée (casse les cycles, protège les autres)
        for t in tables:
            for fk in t.foreign_keys:
                parent = fk.column.table.name
                col = fk.parent
                if parent not in a_supprimer or not a_supprimer[parent] or col.name not in colonnes[t.name]:
                    continue
                if not col.nullable:
                    continue
                db.session.execute(t.update().where(col.in_(list(a_supprimer[parent]))).values({col.name: None}))
        # b. Tables sans clé simple (associations) : supprimer les liens vers des lignes supprimées
        for t in tables:
            if _cle_primaire(t):
                continue
            for fk in t.foreign_keys:
                parent = fk.column.table.name
                if parent in a_supprimer and a_supprimer[parent] and fk.parent.name in colonnes[t.name]:
                    db.session.execute(t.delete().where(fk.parent.in_(list(a_supprimer[parent]))))
            if 'client_id' in t.c and 'client_id' in colonnes[t.name] and t.name not in conserver:
                db.session.execute(t.delete().where(t.c.client_id == client_id))
        # c. Supprimer les « enfants » avant les « parents ». Ordre calculé sur les seuls liens obligatoires
        #    (les liens facultatifs viennent d'être vidés) : l'ordre de SQLAlchemy abandonne en cas de boucle.
        for t in _ordre_suppression(tables, colonnes, a_supprimer):
            cibles = a_supprimer.get(t.name)
            pk = _cle_primaire(t)
            if not cibles or not pk:
                continue
            liste = list(cibles)
            for i in range(0, len(liste), 500):
                db.session.execute(t.delete().where(t.c[pk].in_(liste[i:i + 500])))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return compte


def _tracer(message, details):
    """Trace plateforme (SystemLog, sans client) : elle survit à la suppression du client."""
    from models import db, SystemLog
    from egalyx.commun import adresse_ip
    try:
        db.session.add(SystemLog(level='warning', module='super_admin', message=message,
                                 details=dict(details, par=getattr(current_user, 'username', None)),
                                 ip_address=(adresse_ip() or '')[:45]))
        db.session.commit()
    except Exception:  # noqa: BLE001
        db.session.rollback()


def _client(client_id):
    from models import db, Client
    return db.session.get(Client, client_id)


def _json(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (bytes, bytearray)):
        return None
    return v


@bp.route('/api/client/<int:client_id>/terminate', methods=['POST'])
@super_admin_requis
def supprimer_client(client_id):
    """Suppression définitive d'un client et de toutes ses données. Il faut retaper le nom du client."""
    client = _client(client_id)
    if client is None:
        return jsonify(success=False, error='Client introuvable.'), 404
    donnees = request.get_json(silent=True) or request.form
    if (donnees.get('confirmation') or '').strip() != (client.nom or '').strip():
        return jsonify(success=False, error='Pour confirmer, retapez exactement le nom du client.'), 400
    if getattr(current_user, 'client_id', None) == client_id:
        return jsonify(success=False, error='Vous ne pouvez pas supprimer l’organisation de votre propre compte.'), 400
    nom = client.nom
    try:
        compte = executer_suppression(client_id)
    except Exception as e:  # noqa: BLE001
        return jsonify(success=False, error=f'Suppression annulée, rien n’a été supprimé : {e}'), 500
    if session.get('viewing_client_id') == client_id:
        session.pop('viewing_client_id', None)
    _tracer(f'Client supprimé : {nom}', {'client_id': client_id, 'nom': nom, 'lignes': sum(compte.values()),
                                         'tables': compte})
    return jsonify(success=True, message=f'Client « {nom} » supprimé ({sum(compte.values())} éléments).', detail=compte)


@bp.route('/api/client/<int:client_id>/apercu-suppression')
@super_admin_requis
def apercu_suppression(client_id):
    """Ce qui serait supprimé, sans rien supprimer (affiché avant la confirmation)."""
    client = _client(client_id)
    if client is None:
        return jsonify(success=False, error='Client introuvable.'), 404
    _a, compte = plan_suppression(client_id)
    return jsonify(success=True, nom=client.nom, total=sum(compte.values()), tables=compte)


@bp.route('/api/client/<int:client_id>/reset-data', methods=['POST'])
@super_admin_requis
def reinitialiser_client(client_id):
    """Efface les données de travail du client (risques, audits, contrôles…) ; garde l'organisation,
    ses utilisateurs, son organigramme et ses réglages. Il faut retaper le nom du client."""
    client = _client(client_id)
    if client is None:
        return jsonify(success=False, error='Client introuvable.'), 404
    donnees = request.get_json(silent=True) or request.form
    if (donnees.get('confirmation') or '').strip() != (client.nom or '').strip():
        return jsonify(success=False, error='Pour confirmer, retapez exactement le nom du client.'), 400
    try:
        compte = executer_suppression(client_id, conserver=CONSERVES_REINITIALISATION)
    except Exception as e:  # noqa: BLE001
        return jsonify(success=False, error=f'Réinitialisation annulée, rien n’a été effacé : {e}'), 500
    _tracer(f'Données du client réinitialisées : {client.nom}', {'client_id': client_id, 'lignes': sum(compte.values())})
    return jsonify(success=True, message=f'Données de « {client.nom} » réinitialisées ({sum(compte.values())} éléments).')


@bp.route('/api/client/<int:client_id>/export-data')
@super_admin_requis
def exporter_client(client_id):
    """Toutes les données du client, une table par fichier JSON, dans un zip (à faire avant une suppression)."""
    from models import db
    client = _client(client_id)
    if client is None:
        return jsonify(success=False, error='Client introuvable.'), 404
    a_supprimer, _c = plan_suppression(client_id)
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, 'w', zipfile.ZIP_DEFLATED) as z:
        for t in _tables_triees():
            ids = a_supprimer.get(t.name)
            pk = _cle_primaire(t)
            if not ids or not pk:
                continue
            cols = list(t.c)
            lignes = []
            liste = list(ids)
            for i in range(0, len(liste), 500):
                for r in db.session.execute(db.select(*cols).where(t.c[pk].in_(liste[i:i + 500]))).mappings():
                    lignes.append({k: _json(v) for k, v in r.items()})
            if t.name in ('user', 'users'):
                for l in lignes:
                    for secret in ('password_hash', 'totp_secret', 'secret_2fa', 'otp_secret'):
                        l.pop(secret, None)
            z.writestr(f'{t.name}.json', json.dumps(lignes, ensure_ascii=False, indent=1))
    tampon.seek(0)
    _tracer(f'Données du client exportées : {client.nom}', {'client_id': client_id})
    nom = ''.join(ch if ch.isalnum() else '_' for ch in (client.nom or 'client'))
    return send_file(tampon, mimetype='application/zip', as_attachment=True,
                     download_name=f'export_{nom}_{date.today().isoformat()}.zip')


def _synchroniser(u):
    """Remet les permissions d'un utilisateur en cohérence avec les modules de son organisation."""
    from egalyx.permissions_grille import normaliser
    from egalyx.modules_client import donner_modules_aux_admins, modules_du_client, _est_admin_organisation, MODULES
    if u.client is None:
        return False
    avant = dict(u.permissions or {})
    u.permissions = normaliser(avant, u.client, anciennes=avant)
    if _est_admin_organisation(u):
        actifs = modules_du_client(u.client)
        donner_modules_aux_admins(u.client, set(actifs) if actifs is not None else set(MODULES))
    return dict(u.permissions or {}) != avant


@bp.route('/api/user/<int:user_id>/permissions')
@super_admin_requis
def permissions_utilisateur(user_id):
    from models import db, User
    u = db.session.get(User, user_id)
    if u is None:
        return jsonify(success=False, error='Utilisateur introuvable.'), 404
    return jsonify(success=True, permissions={k: bool(u.has_permission(k)) for k in sorted((u.permissions or {}).keys())})


@bp.route('/api/user/<int:user_id>/sync-permissions', methods=['POST'])
@super_admin_requis
def synchroniser_utilisateur(user_id):
    from models import db, User
    u = db.session.get(User, user_id)
    if u is None:
        return jsonify(success=False, error='Utilisateur introuvable.'), 404
    _synchroniser(u)
    db.session.commit()
    return jsonify(success=True, message=f'Permissions de {u.username} synchronisées avec les modules de son organisation.')


@bp.route('/api/client/<int:client_id>/sync-permissions', methods=['POST'])
@super_admin_requis
def synchroniser_client(client_id):
    from models import db, User
    client = _client(client_id)
    if client is None:
        return jsonify(success=False, error='Client introuvable.'), 404
    users = User.query.filter_by(client_id=client_id).all()
    for u in users:
        _synchroniser(u)
    db.session.commit()
    return jsonify(success=True, message=f'Permissions de {len(users)} utilisateur(s) synchronisées.')


# ---------------------------------------------------------------- adresse d'accès d'un client
def domaine_principal():
    """Domaine sous lequel sont créés les sous-domaines clients (EGALYX_DOMAINE, par défaut egalyx.com)."""
    return (os.environ.get('EGALYX_DOMAINE') or 'egalyx.com').strip().lower().lstrip('.')


def normaliser_sous_domaine(valeur):
    """« https://SONAPIE.egalyx.com/ » → « sonapie »."""
    v = (valeur or '').strip().lower()
    if '://' in v:
        v = v.split('://', 1)[1]
    v = v.split('/')[0].split(':')[0]
    dom = domaine_principal()
    if v.endswith('.' + dom):
        v = v[:-len(dom) - 1]
    return v.split('.')[0] if v else ''


def sous_domaine_du_client(client):
    """Sous-domaine du client : le sien, sinon celui de son environnement (les clients créés avant cette version n'en
    avaient que sur l'environnement)."""
    if client is None:
        return None
    sd = normaliser_sous_domaine(getattr(client, 'sous_domaine', None))
    if sd:
        return sd
    try:
        from models import EnvironnementClient
        env = EnvironnementClient.query.filter(EnvironnementClient.client_id == client.id,
                                               EnvironnementClient.sous_domaine.isnot(None)).first()
        return normaliser_sous_domaine(env.sous_domaine) if env else None
    except Exception:  # noqa: BLE001
        return None


def url_client(client_ou_sd):
    """https://sonapie.egalyx.com (ou None si pas de sous-domaine)."""
    sd = client_ou_sd if isinstance(client_ou_sd, str) else sous_domaine_du_client(client_ou_sd)
    sd = normaliser_sous_domaine(sd)
    return f'https://{sd}.{domaine_principal()}' if sd else None


_CACHE_HOTES = {'quand': 0.0, 'table': {}}


def _table_sous_domaines():
    """{sous-domaine normalisé: client_id}, d'après les clients puis leurs environnements, quelle que soit la forme
    enregistrée (« momo », « momo.egalyx.com », « https://Momo.egalyx.com/ »…). Mise en cache 60 s."""
    import time as _t
    if _t.time() - _CACHE_HOTES['quand'] < 60 and _CACHE_HOTES['table']:
        return _CACHE_HOTES['table']
    from models import Client, EnvironnementClient
    table = {}
    for cid, sd in EnvironnementClient.query.with_entities(EnvironnementClient.client_id, EnvironnementClient.sous_domaine) \
            .filter(EnvironnementClient.sous_domaine.isnot(None)).all():
        n = normaliser_sous_domaine(sd)
        if n:
            table.setdefault(n, cid)
    for cid, sd in Client.query.with_entities(Client.id, Client.sous_domaine).filter(Client.sous_domaine.isnot(None)).all():
        n = normaliser_sous_domaine(sd)
        if n:
            table[n] = cid                      # le sous-domaine du client l'emporte sur celui d'un environnement
    _CACHE_HOTES.update(quand=_t.time(), table=table)
    return table


def vider_cache_hotes():
    _CACHE_HOTES.update(quand=0.0, table={})


def client_par_hote(hote):
    """Client correspondant à l'hôte de la requête (momo.egalyx.com → client dont le sous-domaine est « momo »)."""
    from models import Client
    sd = normaliser_sous_domaine(hote)
    if not sd:
        return None
    cid = _table_sous_domaines().get(sd)
    if cid is None:
        vider_cache_hotes()                     # sous-domaine peut-être tout juste enregistré
        cid = _table_sous_domaines().get(sd)
    return Client.query.get(cid) if cid is not None else None


def db_lower(colonne):
    from sqlalchemy import func
    return func.lower(colonne)


# ---------------------------------------------------------------- modification d'un client (super admin)
SOUS_DOMAINES_RESERVES = {'www', 'api', 'admin', 'app', 'mail', 'smtp', 'ftp', 'static', 'cdn', 'egalyx', 'support',
                          'aide', 'help', 'status', 'login', 'auth', 'super-admin', 'localhost'}
RE_SOUS_DOMAINE = __import__('re').compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')


def verifier_sous_domaine(valeur, client_id):
    """Renvoie (valeur normalisée ou None, message d'erreur ou None)."""
    from models import Client, EnvironnementClient
    v = normaliser_sous_domaine(valeur)
    if not v:
        return None, None
    if not RE_SOUS_DOMAINE.match(v):
        return None, ('Sous-domaine invalide : lettres minuscules, chiffres et tirets uniquement (sans accent ni espace), '
                      'sans tiret au début ni à la fin.')
    if v in SOUS_DOMAINES_RESERVES:
        return None, f'Le sous-domaine « {v} » est réservé.'
    autre = Client.query.filter(Client.sous_domaine == v, Client.id != client_id).first()
    env = EnvironnementClient.query.filter(EnvironnementClient.sous_domaine == v,
                                           EnvironnementClient.client_id != client_id).first()
    if autre is not None or env is not None:
        return None, f'Le sous-domaine « {v} » est déjà utilisé par un autre client.'
    return v, None


def modifier_client(id):
    """Formulaire « Modifier le client » de la fiche (onglet Configuration).

    Corrige l'ancienne version, qui désactivait le client à chaque enregistrement (champ is_active absent du
    formulaire), ignorait le sous-domaine et écrasait la formule par une liste figée. L'activation passe par
    Suspendre / Réactiver, la formule par « Changer formule » (modules et limites synchronisés).
    """
    from flask import flash, redirect, url_for
    from models import db, Client, EnvironnementClient, JournalActiviteClient
    client = Client.query.get_or_404(id)
    retour = redirect(url_for('super_admin_client_detail', id=id) + '#configuration')
    f = request.form
    erreurs = []
    nom = ' '.join((f.get('nom') or client.nom or '').split())[:200]
    if not nom:
        erreurs.append('Le nom du client est obligatoire.')
    email = (f.get('contact_email') or '').strip()[:120]
    if email and not __import__('re').match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        erreurs.append('Adresse e-mail de contact invalide.')
    sous_domaine, err = verifier_sous_domaine(f.get('sous_domaine'), client.id)
    if err:
        erreurs.append(err)
    domaine = (f.get('domaine') or '').strip().lower()[:200] or None
    if domaine and Client.query.filter(Client.domaine == domaine, Client.id != client.id).first():
        erreurs.append(f'Le domaine « {domaine} » est déjà utilisé par un autre client.')
    limites = {}
    for champ in ('max_utilisateurs', 'max_risques', 'max_audits'):
        v = (f.get(champ) or '').strip()
        if v:
            try:
                limites[champ] = max(1, int(v))
            except ValueError:
                erreurs.append(f'Valeur invalide pour {champ.replace("max_", "le nombre maximal de ")}.')
    if erreurs:
        for e in erreurs:
            flash(e, 'danger')
        return retour

    avant = {k: getattr(client, k, None) for k in ('nom', 'contact_nom', 'contact_email', 'contact_telephone',
                                                   'description', 'domaine', 'sous_domaine', 'max_utilisateurs',
                                                   'max_risques', 'max_audits')}
    client.nom = nom
    if 'contact_nom' in f:
        client.contact_nom = (f.get('contact_nom') or '').strip()[:100] or None
    if 'contact_email' in f:
        client.contact_email = email or None
    if 'contact_telephone' in f:
        client.contact_telephone = (f.get('contact_telephone') or '').strip()[:20] or None
    if 'description' in f:
        client.description = (f.get('description') or '').strip() or None
    if 'domaine' in f:
        client.domaine = domaine
    if 'sous_domaine' in f:
        client.sous_domaine = sous_domaine
        for env in EnvironnementClient.query.filter_by(client_id=client.id).all():
            env.sous_domaine = sous_domaine
            if sous_domaine:
                env.url_acces = url_client(sous_domaine)
    for k, v in limites.items():
        setattr(client, k, v)
    client.updated_at = datetime.utcnow()
    apres = {k: getattr(client, k, None) for k in avant}
    modifs = {k: {'avant': avant[k], 'apres': apres[k]} for k in avant if avant[k] != apres[k]}
    try:
        if modifs:
            db.session.add(JournalActiviteClient(client_id=client.id, utilisateur_id=current_user.id,
                                                 action='modification_client',
                                                 details={'par': current_user.username, 'modifications': modifs},
                                                 ip_address=request.remote_addr))
        db.session.commit()
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        flash(f'Enregistrement impossible : {e}', 'danger')
        return retour
    vider_cache_hotes()
    if not modifs:
        flash('Aucune modification.', 'info')
    else:
        lib = {'nom': 'nom', 'contact_nom': 'contact', 'contact_email': 'e-mail', 'contact_telephone': 'téléphone',
               'description': 'description', 'domaine': 'domaine', 'sous_domaine': 'sous-domaine',
               'max_utilisateurs': 'limite utilisateurs', 'max_risques': 'limite risques', 'max_audits': 'limite audits'}
        flash('Client mis à jour : ' + ', '.join(lib[k] for k in modifs) + '.', 'success')
    return retour


def indicateurs_clients():
    """Pour la liste des clients (super admin), calculé une fois par page :
    {client_id: {utilisateurs, double_auth (%), derniere_connexion, demarrage (%), a_surveiller: [raisons]}}."""
    from flask import g
    if hasattr(g, '_egalyx_indicateurs_clients'):
        return g._egalyx_indicateurs_clients
    from datetime import datetime as _dt, timedelta as _td
    from sqlalchemy import func
    from models import db, User, Client
    out = {}
    lignes = db.session.query(User.client_id, func.count(User.id),
                              func.sum(db.case((User.totp_actif.is_(True), 1), else_=0)),
                              func.max(User.last_login)) \
        .filter(User.client_id.isnot(None), User.is_active.is_(True), User.role != 'super_admin') \
        .group_by(User.client_id).all()
    for cid, n, n2fa, derniere in lignes:
        out[cid] = {'utilisateurs': n or 0, 'double_auth': round(100 * (n2fa or 0) / n) if n else 0,
                    'derniere_connexion': derniere}
    try:
        from egalyx.ma_semaine import etapes_demarrage
    except Exception:  # noqa: BLE001
        etapes_demarrage = None
    for c in Client.query.all():
        d = out.setdefault(c.id, {'utilisateurs': 0, 'double_auth': 0, 'derniere_connexion': None})
        d['demarrage'] = None
        if etapes_demarrage is not None:
            try:
                e = etapes_demarrage(c.id)
                d['demarrage'], d['delai_valeur'] = e['pourcentage'], e.get('delai_valeur')
            except Exception:  # noqa: BLE001
                db.session.rollback()
        raisons = []
        if c.is_active:
            if not d['derniere_connexion'] or d['derniere_connexion'] < _dt.utcnow() - _td(days=30):
                raisons.append('aucune connexion depuis 30 jours')
            if d['utilisateurs'] and d['double_auth'] < 50:
                raisons.append(f"double authentification {d['double_auth']} %")
            if d.get('demarrage') is not None and d['demarrage'] < 50 and c.created_at and \
                    c.created_at < _dt.utcnow() - _td(days=14):
                raisons.append('mise en route bloquée')
        d['a_surveiller'] = raisons
    g._egalyx_indicateurs_clients = out
    return out


def enregistrer(app):
    app.register_blueprint(bp)
    app.jinja_env.globals['indicateurs_clients'] = indicateurs_clients
    app.jinja_env.globals['url_client'] = url_client
    app.jinja_env.globals['sous_domaine_du_client'] = sous_domaine_du_client
