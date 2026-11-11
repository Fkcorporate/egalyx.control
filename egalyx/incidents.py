"""
egalyx/incidents.py — gestion des incidents : droits cohérents, délais, escalade, « Ma semaine ».

1. Droits identiques sur toutes les pages /incident(s) et leurs API :
     voir      = « Voir », « Gérer », « Escalader » ou « Résoudre les incidents »
     gérer     = « Gérer les incidents » (déclarer, qualifier, rattacher, archiver, joindre des fichiers)
     escalader = « Escalader » ou « Gérer » — ou le responsable / superviseur / directeur de l'incident
     résoudre  = « Résoudre » ou « Gérer » — ou le responsable de résolution de l'incident
   Une personne nommée sur un incident (déclarant, responsable, superviseur, directeur) peut toujours l'ouvrir.
   Avant : la plupart des pages demandaient « Gérer les audits » ; les permissions incidents ne servaient presque pas.
2. Les règles « qui peut modifier / escalader / approuver / rouvrir / archiver » de l'incident (utilisées par les
   boutons de la fiche) suivent ces droits. Approbation : superviseur, directeur ou « Résoudre / Gérer », mais jamais
   le responsable de résolution (double regard ; EGALYX_INCIDENT_DOUBLE_REGARD=0 pour l'assouplir).
3. Risque et dispositif deviennent facultatifs à la déclaration (incident « à qualifier », par exemple issu d'un
   signalement) ; le risque est exigé avant la résolution. La base est mise à jour au démarrage.
4. Délais (SLA) : date limite calculée, incident marqué « délai dépassé » et personnes concernées prévenues une fois.
   Vérifié au plus toutes les 10 minutes pendant l'utilisation, et par `flask verifier-incidents`.
   L'escalade automatique existante (services/escalade_service.py, toutes les heures) est conservée.
5. API : la liste et le détail des incidents ne plantent plus (to_dict renvoyait des fonctions).
6. « Ma semaine » : incidents confiés, à qualifier, à approuver, délais dépassés.
"""
import os
import re
import time
from datetime import datetime, timedelta

from flask import flash, has_request_context, jsonify, redirect, request, url_for
from flask_login import current_user

from egalyx.commun import a_permission, est_admin_client

VOIR = ('can_view_incidents', 'can_manage_incidents', 'can_escalate_incidents', 'can_resolve_incidents')
GERER = ('can_manage_incidents',)
ESCALADER = ('can_escalate_incidents', 'can_manage_incidents')
RESOUDRE = ('can_resolve_incidents', 'can_manage_incidents')
NIVEAUX = {'voir': VOIR, 'gerer': GERER, 'escalader': ESCALADER, 'resoudre': RESOUDRE}
OUVERTS = ('ouvert', 'en_cours', 'en_attente_approbation')
FINIS = ('resolu', 'ferme', 'rejete')

# Pages existantes → niveau exigé. « fiche » : voir, ou nommé sur l'incident.
# « modifier » / « escalader_i » / « resoudre_i » : le droit, ou le rôle tenu sur cet incident.
DROITS = {
    'liste_incidents': 'voir', 'dashboard_incidents_avance': 'voir', 'dashboard_ia_incidents': 'voir',
    'api_stats_incidents': 'voir', 'api_liste_incidents': 'voir', 'incidents_par_dispositif': 'voir',
    'incidents_escalade_attente': 'voir', 'export_incidents_excel': 'voir', 'export_incidents_csv': 'voir',
    'export_incidents_pdf': 'voir', 'analyse_ia_incident': 'fiche',
    'detail_incident': 'fiche', 'api_detail_incident': 'fiche', 'get_resolution_fichiers': 'fiche',
    'nouvel_incident': 'gerer', 'api_creer_incident': 'gerer', 'archiver_incident': 'gerer',
    'restaurer_incident': 'gerer', 'incidents_archives': 'gerer', 'api_incident_lier_dispositif': 'gerer',
    'api_lier_dispositif': 'gerer', 'api_dissocier_dispositif': 'gerer', 'api_restaurer_dispositif': 'gerer',
    'api_update_incident_direction': 'modifier', 'api_update_incident_service': 'modifier',
    'api_creer_plan_action_depuis_incident': 'gerer', 'api_supprimer_fichier_incident': 'modifier',
    'modifier_incident': 'modifier', 'api_modifier_incident': 'modifier', 'upload_fichier_incident': 'modifier',
    'escalader_incident': 'escalader_i', 'api_escalader_incident': 'escalader_i',
    'api_retro_escalader_incident': 'escalader_i',
    'resoudre_incident': 'resoudre_i', 'api_resoudre_incident': 'resoudre_i', 'upload_resolution_fichier': 'resoudre_i',
    'reouvrir_incident': 'resoudre', 'approuver_incident': 'fiche',     # l'approbation est vérifiée par la page
}
PARAM_ID = ('id', 'incident_id')


def _m():
    import models
    return models


# ---------------------------------------------------------------- droits
def peut(niveau, u=None):
    u = u or current_user
    if getattr(u, 'role', None) == 'super_admin':
        return True
    return a_permission(*NIVEAUX[niveau], u=u)


def _nomme(i, u):
    uid = getattr(u, 'id', None)
    return bool(i and uid and uid in (i.declare_par_id, i.responsable_resolution_id, i.superviseur_id,
                                      i.directeur_id, i.created_by))


def _meme_org(i, u):
    return i is not None and (getattr(u, 'role', None) == 'super_admin' or i.client_id == getattr(u, 'client_id', None))


def peut_voir(i, u=None):
    u = u or current_user
    return _meme_org(i, u) and (peut('voir', u) or _nomme(i, u))


def peut_modifier(i, u=None):
    u = u or current_user
    if not _meme_org(i, u) or i.is_archived:
        return False
    return peut('gerer', u) or getattr(u, 'id', None) in (i.responsable_resolution_id, i.created_by)


def peut_escalader(i, u=None):
    u = u or current_user
    if not _meme_org(i, u) or i.is_archived or (i.statut or '') in FINIS or (i.niveau_escalade or 1) >= 3:
        return False
    uid = getattr(u, 'id', None)
    return peut('escalader', u) or uid in (i.responsable_resolution_id, i.superviseur_id, i.directeur_id)


def peut_resoudre(i, u=None):
    u = u or current_user
    if not _meme_org(i, u) or i.is_archived or (i.statut or '') in FINIS:
        return False
    return peut('resoudre', u) or getattr(u, 'id', None) == i.responsable_resolution_id


def peut_approuver(i, u=None):
    u = u or current_user
    if not _meme_org(i, u) or not i.approbation_requise or i.approbation_statut != 'en_attente':
        return False
    if getattr(u, 'role', None) == 'super_admin':
        return True
    uid = getattr(u, 'id', None)
    if os.environ.get('EGALYX_INCIDENT_DOUBLE_REGARD', '1') == '1' and uid == i.responsable_resolution_id:
        return False                                  # on n'approuve pas sa propre résolution
    return uid in (i.superviseur_id, i.directeur_id) or peut('resoudre', u)


def peut_reouvrir(i, u=None):
    u = u or current_user
    return _meme_org(i, u) and not i.is_archived and (i.statut or '') in ('resolu', 'ferme') and peut('resoudre', u)


def peut_archiver(i, u=None):
    u = u or current_user
    return _meme_org(i, u) and (peut('gerer', u) or est_admin_client(u))


def _incident_de_la_requete():
    m = _m()
    for p in PARAM_ID:
        v = (request.view_args or {}).get(p)
        if isinstance(v, int):
            return m.db.session.get(m.Incident, v)
    return None


def droit(endpoint=None):
    """Remplace dans app.py les anciens contrôles « Gérer les audits » des pages incidents."""
    endpoint = endpoint or (request.endpoint if has_request_context() else None)
    niveau = DROITS.get(endpoint) or ('voir' if request.method in ('GET', 'HEAD') else 'gerer')
    if niveau in NIVEAUX:
        return peut(niveau)
    i = _incident_de_la_requete()
    if i is None:
        return peut('voir')                       # la page répondra « introuvable »
    return {'fiche': peut_voir, 'modifier': peut_modifier, 'escalader_i': peut_escalader,
            'resoudre_i': peut_resoudre}[niveau](i)


def _concerne(path, endpoint):
    return endpoint in DROITS or path.startswith(('/incident/', '/incidents', '/api/incident/', '/api/incidents'))


def _garde():
    ep = request.endpoint or ''
    if '.' in ep or not _concerne(request.path, ep):
        return None
    if not getattr(current_user, 'is_authenticated', False) or getattr(current_user, 'role', None) == 'super_admin':
        return None
    if droit(ep):
        refus = _risque_exige(ep)
        return refus
    return _refus("Vous n'avez pas la permission nécessaire pour cette page des incidents.")


def _refus(message, code=403):
    if request.path.startswith('/api/') or request.is_json or \
            'application/json' in (request.headers.get('Accept') or ''):
        return jsonify({'success': False, 'error': message}), code
    flash(message, 'warning')
    if peut('voir') and request.endpoint != 'liste_incidents':
        return redirect(url_for('liste_incidents'))
    return redirect(url_for('dashboard'))


def _risque_exige(ep):
    """Résoudre un incident exige de l'avoir rattaché à un risque (il nourrit la cartographie)."""
    if ep not in ('resoudre_incident', 'api_resoudre_incident') or request.method not in ('POST', 'PUT'):
        return None
    i = _incident_de_la_requete()
    if i is not None and not i.risque_id:
        message = ("Rattachez d'abord l'incident à un risque de la cartographie (bouton « Modifier ») : "
                   "un incident résolu sans risque ne nourrit pas l'évaluation des risques.")
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({'success': False, 'error': message}), 400
        flash(message, 'warning')
        return redirect(url_for('detail_incident', id=i.id))
    return None


# ---------------------------------------------------------------- délais (SLA)
_DERNIERE = {'t': 0.0}


def _gestionnaires(cid):
    m = _m()
    return [u.id for u in m.User.query.filter_by(client_id=cid, is_active=True).all()
            if not getattr(u, 'is_operateur', False) and u.has_permission('can_manage_incidents')]


def _notifier(destinataires, titre, message, i):
    m = _m()
    for uid in {d for d in destinataires if d}:
        m.db.session.add(m.Notification(destinataire_id=uid, type_notification='incident', titre=titre[:200],
                                        message=message, entite_type='incident', entite_id=i.id,
                                        client_id=i.client_id))


def verifier_delais(client_id=None):
    """Calcule les dates limites manquantes et marque les incidents dont le délai est dépassé (une seule fois,
    avec notification). Renvoie le nombre d'incidents nouvellement en dépassement."""
    m = _m()
    maintenant = datetime.utcnow()
    q = m.Incident.query.filter(m.Incident.is_archived.isnot(True))
    if client_id:
        q = q.filter(m.Incident.client_id == client_id)
    n = 0
    for i in q.filter(m.Incident.statut.notin_(FINIS)).all():
        if not i.sla_date_limite and i.sla_heures:
            depart = i.date_detection or i.created_at or maintenant
            i.sla_date_limite = depart + timedelta(hours=i.sla_heures)
        if i.sla_date_limite and i.sla_date_limite < maintenant and not i.sla_viole:
            i.sla_viole = True
            n += 1
            m.db.session.add(m.IncidentHistorique(incident_id=i.id, action='sla_depasse', created_at=maintenant,
                                                  details=f"Délai de traitement de {i.sla_heures} h dépassé "
                                                          f"(limite {i.sla_date_limite.strftime('%d/%m/%Y %H:%M')})."))
            retard = maintenant - i.sla_date_limite
            retard_txt = (f'{retard.days} j' if retard.days else f'{max(1, retard.seconds // 3600)} h')
            _notifier([i.responsable_resolution_id, i.superviseur_id] + _gestionnaires(i.client_id),
                      f'Délai dépassé : {i.reference}',
                      f"L'incident « {i.titre} » (gravité {i.gravite or 'non définie'}) n'est pas résolu dans le délai "
                      f"prévu de {i.sla_heures} h : limite le {i.sla_date_limite.strftime('%d/%m/%Y à %H:%M')} (UTC), "
                      f"retard de {retard_txt}.", i)
    # Résolu après la date limite : le dépassement est conservé pour les statistiques
    for i in q.filter(m.Incident.statut.in_(FINIS), m.Incident.sla_viole.isnot(True),
                      m.Incident.sla_date_limite.isnot(None), m.Incident.date_resolution.isnot(None)).all():
        if i.date_resolution > i.sla_date_limite:
            i.sla_viole = True
    m.db.session.commit()
    return n


def _verification_periodique():
    """Pendant l'utilisation : au plus une vérification des délais toutes les 10 minutes par processus."""
    if time.time() - _DERNIERE['t'] < 600 or request.endpoint in (None, 'static'):
        return None
    _DERNIERE['t'] = time.time()
    try:
        verifier_delais()
    except Exception as e:  # noqa: BLE001 — ne jamais bloquer une page pour ça
        _m().db.session.rollback()
        import logging
        logging.getLogger(__name__).warning('Vérification des délais des incidents : %s', e)
    return None


# ---------------------------------------------------------------- modèle
def _brancher_modele():
    m = _m()
    I = m.Incident
    if getattr(I, '_egalyx_incidents', False):
        return
    I.peut_modifier = lambda self, user=None: peut_modifier(self, user)
    I.peut_escalader = lambda self, user=None: peut_escalader(self, user)
    I.peut_approuver = lambda self, user=None: peut_approuver(self, user)
    I.peut_reouvrir = lambda self, user=None: peut_reouvrir(self, user)
    I.peut_archiver = lambda self, user=None: peut_archiver(self, user)
    I.peut_resoudre = lambda self, user=None: peut_resoudre(self, user)
    origine = I.to_dict

    def to_dict(self, user=None):
        """Les droits sont calculés pour l'utilisateur (avant : des fonctions, impossibles à mettre en JSON)."""
        d = origine(self)
        u = user or (current_user if has_request_context() and getattr(current_user, 'is_authenticated', False) else None)
        for cle, valeur in list(d.items()):
            if callable(valeur):
                d[cle] = bool(valeur(u)) if u is not None else None
        d['a_qualifier'] = not self.risque_id
        return d
    I.to_dict = to_dict
    I._egalyx_incidents = True


# ---------------------------------------------------------------- base : risque et dispositif facultatifs
def rendre_liens_facultatifs(app):
    """Les anciennes bases imposent un risque ET un dispositif à chaque incident (NOT NULL) : la conversion d'un
    signalement et la déclaration « sans risque » échouaient. On retire cette contrainte, sans rien perdre."""
    from sqlalchemy import inspect as sa_inspect, text
    m = _m()
    db = m.db
    with app.app_context():
        try:
            insp = sa_inspect(db.engine)
            if 'incidents' not in insp.get_table_names():
                return False
            obligatoires = [c['name'] for c in insp.get_columns('incidents')
                            if c['name'] in ('risque_id', 'dispositif_id') and not c.get('nullable', True)]
            if not obligatoires:
                return False
            dialecte = db.engine.dialect.name
            if dialecte == 'postgresql':
                with db.engine.begin() as cx:
                    for col in obligatoires:
                        cx.execute(text(f'ALTER TABLE incidents ALTER COLUMN {col} DROP NOT NULL'))
            elif dialecte in ('mysql', 'mariadb'):
                with db.engine.begin() as cx:
                    for col in obligatoires:
                        cx.execute(text(f'ALTER TABLE incidents MODIFY {col} INTEGER NULL'))
            elif dialecte == 'sqlite':
                _reconstruire_sqlite(db, obligatoires)
            else:
                app.logger.warning('Incidents : colonnes %s obligatoires, base %s non gérée.', obligatoires, dialecte)
                return False
            app.logger.info('Incidents : %s désormais facultatifs.', ', '.join(obligatoires))
            return True
        except Exception as e:  # noqa: BLE001
            app.logger.warning('Incidents : impossible de rendre risque/dispositif facultatifs (%s).', e)
            return False


def _reconstruire_sqlite(db, colonnes):
    """SQLite ne sait pas retirer un NOT NULL : la table est recopiée (procédure officielle SQLite)."""
    brut = db.engine.raw_connection()
    try:
        cur = brut.cursor()
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='incidents'")
        ddl = cur.fetchone()[0]
        nouveau = ddl
        for col in colonnes:
            nouveau = re.sub(r'(["`\[]?%s["`\]]?\s+INTEGER)\s+NOT\s+NULL' % col, r'\1', nouveau, flags=re.I)
        if nouveau == ddl:
            return
        nouveau = re.sub(r'CREATE\s+TABLE\s+["`\[]?incidents["`\]]?', 'CREATE TABLE incidents__nouv', nouveau, count=1,
                         flags=re.I)
        cur.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='incidents' AND sql IS NOT NULL")
        index = [r[0] for r in cur.fetchall()]
        cur.execute('PRAGMA foreign_keys=OFF')
        cur.execute('BEGIN')
        cur.execute(nouveau)
        cur.execute('INSERT INTO incidents__nouv SELECT * FROM incidents')
        cur.execute('DROP TABLE incidents')
        cur.execute('ALTER TABLE incidents__nouv RENAME TO incidents')
        for sql in index:
            cur.execute(sql)
        cur.execute('COMMIT')
        cur.execute('PRAGMA foreign_keys=ON')
    except Exception:
        try:
            brut.cursor().execute('ROLLBACK')
        except Exception:  # noqa: BLE001
            pass
        raise
    finally:
        brut.close()
    db.engine.dispose()


# ---------------------------------------------------------------- « Ma semaine »
def taches(u, ajout, horizon, aujourd_hui, lien):
    m = _m()
    if not u.client_id:
        return
    gerer = peut('gerer', u)
    q = m.Incident.query.filter(m.Incident.client_id == u.client_id, m.Incident.is_archived.isnot(True))
    for i in q.filter(m.Incident.statut.notin_(FINIS)).all():
        url = lien('detail_incident', id=i.id)
        echeance = i.sla_date_limite.date() if i.sla_date_limite else None
        if i.approbation_requise and i.approbation_statut == 'en_attente' and peut_approuver(i, u):
            ajout('Incident à approuver', i.titre, f'{i.reference} · résolution à valider', i.updated_at, url, 1)
            continue
        if i.responsable_resolution_id == u.id:
            ajout('Incident à traiter', i.titre, f'{i.reference} · gravité {i.gravite or "?"}'
                  + (' · délai dépassé' if i.sla_viole else ''), echeance, url, 1 if i.sla_viole else 2)
        elif gerer and not i.risque_id:
            ajout('Incident à qualifier', i.titre, f'{i.reference} · à rattacher à un risque', i.created_at, url, 1)
        elif gerer and (i.sla_viole or not i.responsable_resolution_id):
            ajout('Incident en souffrance', i.titre, f'{i.reference} · '
                  + ('délai dépassé' if i.sla_viole else 'sans responsable'), echeance, url, 1)
        elif u.id in (i.superviseur_id, i.directeur_id) and (i.niveau_escalade or 1) >= 2:
            ajout('Incident escaladé', i.titre, f'{i.reference} · niveau {i.niveau_escalade}', echeance, url, 1)


# ---------------------------------------------------------------- intégration
def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    exempter_controle_ancien(app, DROITS)
    _brancher_modele()
    app.before_request(_garde)
    app.before_request(_verification_periodique)
    rendre_liens_facultatifs(app)
    enregistrer_impacts(app)
    enregistrer_courriels()
    app.jinja_env.globals['incident_peut_resoudre'] = peut_resoudre

    @app.cli.command('verifier-incidents')
    def _cli():
        """Calcule les délais des incidents et marque les dépassements."""
        print(f'{verifier_delais()} incident(s) nouvellement en dépassement de délai.')


# ---------------------------------------------------------------- coûts et temps d'arrêt
# Ces champs existaient (fiche, tableaux de bord, totaux) mais aucun formulaire ni API ne permettait de les saisir :
# ils restaient « Non évalué » et les totaux à zéro. Ils sont saisis dans la déclaration, la modification et la
# résolution (templates/incidents/_impacts.html), et acceptés par l'API (cout_estime, temps_arret en minutes,
# impact_financier_reel).
SAISIE_IMPACTS = {'nouvel_incident', 'modifier_incident', 'resoudre_incident', 'api_creer_incident',
                  'api_modifier_incident', 'api_resoudre_incident'}
SYMBOLES = {'EUR': '€', 'XOF': 'FCFA', 'XAF': 'FCFA', 'USD': '$', 'GBP': '£', 'MAD': 'MAD', 'TND': 'TND', 'GNF': 'GNF',
            'CDF': 'FC', 'NGN': '₦', 'GHS': 'GH₵', 'KES': 'KSh', 'CHF': 'CHF', 'CAD': 'CA$'}


def _montant(texte):
    """« 1 500 000 », « 1500,50 », « 1.500.000 » → nombre ; vide → None ; invalide → ValueError."""
    t = (texte or '').strip().replace(' ', '').replace(' ', '').replace(' ', '')
    for symbole in ('€', 'FCFA', 'CFA', 'F', '$'):
        t = t.replace(symbole, '')
    if not t:
        return None
    if t.count('.') > 1 and ',' not in t:
        t = t.replace('.', '')
    if ',' in t and '.' in t:
        t = t.replace('.', '').replace(',', '.') if t.rfind(',') > t.rfind('.') else t.replace(',', '')
    t = t.replace(',', '.')
    v = float(t)
    if v < 0:
        raise ValueError('négatif')
    return v


def _entier(texte):
    t = (str(texte) if texte is not None else '').strip()
    if not t:
        return 0
    v = int(float(t.replace(',', '.')))
    if v < 0:
        raise ValueError('négatif')
    return v


def appliquer_impacts(incident, donnees, depuis_json=False):
    """Met à jour coût estimé, coût réel et temps d'arrêt à partir d'un formulaire ou d'un JSON.
    Un champ absent ne change rien ; un champ vidé efface la valeur."""
    erreurs = []
    for champ in ('cout_estime', 'impact_financier_reel'):
        if champ in donnees:
            try:
                setattr(incident, champ, _montant(str(donnees.get(champ) or '')))
            except ValueError:
                erreurs.append('coût estimé' if champ == 'cout_estime' else 'coût réel')
    try:
        if depuis_json and 'temps_arret' in donnees:
            incident.temps_arret = _entier(donnees.get('temps_arret')) or None
        elif 'temps_arret_heures' in donnees or 'temps_arret_minutes' in donnees:
            h, mn = _entier(donnees.get('temps_arret_heures')), _entier(donnees.get('temps_arret_minutes'))
            incident.temps_arret = (h * 60 + mn) or None
    except ValueError:
        erreurs.append("temps d'arrêt")
    return erreurs


def _impacts_avant_flush(session_, _ctx, _inst):
    if not has_request_context() or request.endpoint not in SAISIE_IMPACTS or request.method not in ('POST', 'PUT'):
        return
    m = _m()
    json_ = request.is_json
    donnees = (request.get_json(silent=True) or {}) if json_ else request.form
    if not any(k in donnees for k in ('cout_estime', 'impact_financier_reel', 'temps_arret', 'temps_arret_heures',
                                       'temps_arret_minutes')):
        return
    for obj in list(session_.new) + list(session_.dirty):
        if isinstance(obj, m.Incident) and not getattr(obj, '_egalyx_impacts_faits', False):
            obj._egalyx_impacts_faits = True
            erreurs = appliquer_impacts(obj, donnees, depuis_json=json_)
            if erreurs and not json_:
                flash("Montant ou durée ignoré (format non reconnu) : " + ', '.join(erreurs)
                      + ". Exemple : 1 500 000 ou 1500,50.", 'warning')


def devise_client(client_id=None):
    """Devise de l'organisation (celle de son abonnement), affichée avec son symbole usuel."""
    m = _m()
    cid = client_id or (getattr(current_user, 'client_id', None) if has_request_context() else None)
    code = None
    if cid and hasattr(m, 'AbonnementClient'):
        try:
            a = m.AbonnementClient.query.filter_by(client_id=cid).order_by(m.AbonnementClient.id.desc()).first()
            code = (a.devise or '').upper() if a else None
        except Exception:  # noqa: BLE001
            code = None
    code = code or os.environ.get('EGALYX_DEVISE', 'EUR').upper()
    return SYMBOLES.get(code, code)


def montant_affiche(v):
    """1500000.5 → « 1 500 000,50 » ; entier → sans décimales."""
    if v is None:
        return ''
    entier = float(v).is_integer()
    texte = f'{float(v):,.0f}' if entier else f'{float(v):,.2f}'
    return texte.replace(',', ' ').replace('.', ',')


def enregistrer_impacts(app):
    import models as m
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    if not getattr(m, '_egalyx_impacts_flush', False):
        event.listen(Session, 'before_flush', _impacts_avant_flush)
        m._egalyx_impacts_flush = True
    app.jinja_env.globals['devise_incidents'] = devise_client
    app.jinja_env.globals['montant_incident'] = montant_affiche


# ---------------------------------------------------------------- e-mails (délais dépassés, escalades)
# Les alertes restaient dans l'application. Une copie par e-mail est envoyée pour les notifications d'incident
# importantes (délai dépassé, escalade), après l'enregistrement et en arrière-plan, SEULEMENT si l'organisation l'a
# activée (Incidents → Alertes e-mail : événements, destinataires, désabonnement). Interrupteur général du serveur :
# EGALYX_INCIDENTS_EMAIL=0. Sans SMTP configuré (egalyx/courriel.py), rien n'est envoyé.
TYPES_COURRIEL = ('incident', 'escalade')


def _a_envoyer(n):
    if getattr(n, 'entite_type', None) != 'incident':
        return False
    titre = (getattr(n, 'titre', '') or '')
    return getattr(n, 'type_notification', None) in TYPES_COURRIEL or 'scalade' in titre or titre.startswith('Délai dépassé')


def _role_dans_incident(inc, uid):
    if inc is not None and uid == getattr(inc, 'responsable_resolution_id', None):
        return 'responsable'
    if inc is not None and uid in (getattr(inc, 'superviseur_id', None), getattr(inc, 'directeur_id', None)):
        return 'superviseur'
    return 'gestionnaire'


def _courriels_apres_flush(session_, _ctx):
    """Copie par e-mail selon les réglages de l'organisation (egalyx/alertes_incidents.py) : désactivée par défaut."""
    if os.environ.get('EGALYX_INCIDENTS_EMAIL', '1') != '1':
        return
    m = _m()
    nouvelles = [n for n in session_.new if isinstance(n, m.Notification) and _a_envoyer(n)]
    if not nouvelles:
        return
    from egalyx.alertes_incidents import reglages
    base = (os.environ.get('EGALYX_URL_PUBLIQUE') or '').rstrip('/')
    desabo = f'{base}/incidents/alertes/me-desabonner' if base else ''
    # Les délais dépassés sont regroupés : un seul e-mail par personne et par vérification (au premier passage,
    # tous les incidents anciens encore ouverts dépassent d'un coup : sans regroupement, une rafale d'e-mails).
    # les délais sont cumulés dans la session jusqu'au commit (verifier_delais peut provoquer plusieurs flushs)
    delais, autres, cache = session_.info.setdefault('egalyx_delais_incidents', {}), [], {}
    with session_.no_autoflush:
        for n in nouvelles:
            inc = session_.get(m.Incident, n.entite_id) if n.entite_id else None
            cid = n.client_id or getattr(inc, 'client_id', None)
            if cid not in cache:
                cache[cid] = reglages(cid, session_)
                try:
                    from egalyx.identite import nom_affiche
                    cache[('nom', cid)] = nom_affiche(cid) or 'Egalyx'
                except Exception:  # noqa: BLE001
                    cache[('nom', cid)] = 'Egalyx'
            r = cache[cid]
            prefixe = f"[{cache[('nom', cid)]}]"
            evenement = 'delai' if (n.titre or '').startswith('Délai dépassé') else 'escalade'
            if not r.get('actif') or evenement not in (r.get('evenements') or []):
                continue
            u = session_.get(m.User, n.destinataire_id) if n.destinataire_id else None
            lien = f'{base}/incident/{n.entite_id}' if base and n.entite_id else ''
            dests = []
            if (u is not None and getattr(u, 'email', None) and getattr(u, 'is_active', True) is not False
                    and u.id not in (r.get('desabonnes') or [])
                    and _role_dans_incident(inc, u.id) in (r.get('roles') or [])):
                dests.append(u.email.lower())
            # adresses supplémentaires : une fois par incident et par événement
            cle = (n.entite_id, evenement)
            if cle not in cache.setdefault(('vus', cid), set()):
                cache[('vus', cid)].add(cle)
                dests += [a for a in (r.get('adresses') or []) if a]
            for email in dests:
                if evenement == 'delai':
                    lot = delais.setdefault(email, [])
                    if all(x[0] != n.entite_id for x in lot):
                        lot.append((n.entite_id, n.titre or '', n.message or '', lien, prefixe))
                elif (email, n.entite_id, n.titre) not in [(e, x.entite_id, x.titre) for e, x, _l, _p in autres]:
                    autres.append((email, n, lien, prefixe))
    session_.info['egalyx_pied_incidents'] = pied = ("\n\nVous recevez cet e-mail selon les réglages d'alerte des incidents de votre organisation."
            + (f"\nNe plus recevoir ces e-mails : {desabo}" if desabo else '') + "\n\n— Egalyx Control")
    for email, n, lien, prefixe in autres:
        texte = f"{n.message or ''}\n\n{('Voir l’incident : ' + lien) if lien else ''}" + pied
        session_.info.setdefault('egalyx_courriels_incidents', []).append((email, f'{prefixe} {n.titre}', texte))


def _courriels_delais(delais, pied):
    """Un e-mail par personne : l'alerte seule, ou un récapitulatif si plusieurs incidents dépassent ensemble."""
    envois = []
    for email, lot in delais.items():
        prefixe = lot[0][4]
        if len(lot) == 1:
            _id, titre, message, lien, _p = lot[0]
            sujet = f'{prefixe} {titre}'
            corps = f"{message}\n\n{('Voir l’incident : ' + lien) if lien else ''}"
        else:
            sujet = f'{prefixe} {len(lot)} incidents ont dépassé leur délai de traitement'
            lignes = [f"- {titre.replace('Délai dépassé : ', '')} — {message}" + (f"\n  {lien}" if lien else '')
                      for _id, titre, message, lien, _p in lot[:50]]
            if len(lot) > 50:
                lignes.append(f'… et {len(lot) - 50} autre(s) : voir la liste des incidents dans Egalyx.')
            corps = 'Les incidents suivants ne sont pas résolus dans le délai prévu :\n\n' + '\n'.join(lignes)
        envois.append((email, sujet, corps + "\n\nUne seule alerte est envoyée par incident." + pied))
    return envois


def _courriels_apres_commit(session_):
    envois = session_.info.pop('egalyx_courriels_incidents', None) or []
    delais = session_.info.pop('egalyx_delais_incidents', None)
    pied = session_.info.pop('egalyx_pied_incidents', '')
    if delais:
        envois = envois + _courriels_delais(delais, pied)
    if not envois:
        return
    try:
        from egalyx import courriel
        if not courriel.est_configure():
            return
    except Exception:  # noqa: BLE001
        return
    import threading

    def _envoyer(lot):
        from egalyx import courriel
        for dest, sujet, texte in lot:
            try:
                courriel.envoyer([dest], sujet, texte)
            except Exception:  # noqa: BLE001
                pass
    threading.Thread(target=_envoyer, args=(envois,), daemon=True).start()


def _courriels_apres_rollback(session_):
    for k in ('egalyx_courriels_incidents', 'egalyx_delais_incidents', 'egalyx_pied_incidents'):
        session_.info.pop(k, None)


def enregistrer_courriels():
    import models as m
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    if not getattr(m, '_egalyx_incidents_courriels', False):
        event.listen(Session, 'after_flush', _courriels_apres_flush)
        event.listen(Session, 'after_commit', _courriels_apres_commit)
        event.listen(Session, 'after_soft_rollback', lambda s, _t: _courriels_apres_rollback(s))
        m._egalyx_incidents_courriels = True
