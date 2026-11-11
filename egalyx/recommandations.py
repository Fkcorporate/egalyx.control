"""
egalyx/recommandations.py — registre unique des recommandations.

Rassemble, sans les déplacer, les recommandations :
  - d'audit interne (models.Recommandation),
  - du contrôle interne N2 (models.RecommandationC2N),
  - externes : commissaire aux comptes, régulateur, inspection, auditeur externe (models.RecommandationExterne).

Circuit commun :
  le responsable déclare l'avancement (commentaire, preuve jointe) depuis « Mes recommandations »
  (aussi dans l'espace opérateur) ; à 100 % il DEMANDE la clôture ; un gestionnaire, qui n'est ni le
  responsable ni le demandeur, valide ou refuse (motif obligatoire). Tout est tracé (SuiviRecommandation).

Indicateurs de comité : taux de mise en œuvre, échues, ancienneté moyenne, répartition par source.
"""
import os
import uuid
from datetime import date, datetime

from flask import (Blueprint, abort, current_app, flash, redirect, render_template, request, send_file,
                   url_for)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from egalyx.commun import a_permission, client_id_courant, entier, journaliser, permission_requise

bp = Blueprint('recommandations', __name__, url_prefix='/recommandations')

# Module « Registre des recommandations » (catalogue des modules) et ses deux permissions
VOIR = ('can_view_recommandations', 'can_manage_recommandations')
GERER = ('can_manage_recommandations',)
# Par origine : module du client qui doit être actif ; droits pour décider de la clôture
MODULE_DE = {'audit': 'audit', 'c2n': 'controle_n2', 'externe': 'recommandations'}
VOIR_DE = {'audit': VOIR, 'c2n': VOIR, 'externe': VOIR}
GERER_DE = {'audit': ('can_manage_audit',) + GERER, 'c2n': ('can_manage_controle_interne_n2',) + GERER, 'externe': GERER}

SOURCES = {'audit': 'Audit interne', 'c2n': 'Contrôle interne N2', 'cac': 'Commissaire aux comptes',
           'regulateur': 'Régulateur', 'inspection': 'Inspection', 'externe': 'Auditeur externe'}
SOURCES_EXTERNES = ('cac', 'regulateur', 'inspection', 'externe')
STATUTS = {'proposee': 'Proposée', 'ouverte': 'Ouverte', 'en_cours': 'En cours', 'a_valider': 'Clôture à valider',
           'cloturee': 'Clôturée', 'rejetee': 'Rejetée'}
PRIORITES = {'faible': 'Faible', 'moyenne': 'Moyenne', 'haute': 'Haute', 'critique': 'Critique'}
EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv', 'msg', 'eml', 'zip'}
TAILLE_MAX = 15 * 1024 * 1024


def _m():
    import models
    return models


# ---------------------------------------------------------------- normalisation
def _statut_audit(r):
    s = (r.statut or 'a_traiter')
    if s == 'termine':
        return 'cloturee'
    if r.demande_cloture_le:
        return 'a_valider'
    return 'ouverte' if s == 'a_traiter' else 'en_cours'


def _statut_c2n(r):
    s = (r.statut or 'proposee')
    if s == 'realisee':
        return 'cloturee'
    if s == 'rejetee':
        return 'rejetee'
    if r.demande_cloture_le:
        return 'a_valider'
    return 'proposee' if s == 'proposee' else 'en_cours'


def _statut_externe(r):
    if r.statut in ('cloturee', 'rejetee'):
        return r.statut
    if r.demande_cloture_le:
        return 'a_valider'
    return r.statut or 'ouverte'


URGENCES = {1: 'faible', 2: 'moyenne', 3: 'haute', 4: 'critique', 5: 'critique'}


def _url(endpoint, **valeurs):
    """Lien, ou None hors requête (tâches planifiées, calculs d'indicateurs)."""
    try:
        return url_for(endpoint, **valeurs)
    except Exception:
        return None


def _ligne(source, r):
    """Vue commune d'une recommandation, quelle que soit sa source."""
    m = _m()
    if source == 'audit':
        audit = getattr(r, 'audit', None)
        return dict(source='audit', type='audit', id=r.id, reference=r.reference,
                    titre=(r.description or '')[:160], description=r.description,
                    priorite=URGENCES.get(r.urgence or 1, 'moyenne'), responsable_id=r.responsable_id,
                    responsable=r.responsable, echeance=r.date_echeance, progression=r.taux_avancement or 0,
                    statut=_statut_audit(r), cree_le=r.created_at, origine=(audit.reference if audit else ''),
                    lien=_url('detail_audit', id=r.audit_id) if r.audit_id else None,
                    client_id=r.client_id or (audit.client_id if audit else None), objet=r,
                    demandeur_id=r.demande_cloture_par_id, motif_refus=r.motif_refus_cloture)
    if source == 'c2n':
        pl = m.db.session.get(m.PlanificationControle, r.planification_id) if r.planification_id else None
        return dict(source='c2n', type='c2n', id=r.id, reference=f'N2-REC-{r.id}', titre=r.titre, description=r.description,
                    priorite=(r.priorite or 'moyenne'), responsable_id=r.responsable_id,
                    responsable=m.db.session.get(m.User, r.responsable_id) if r.responsable_id else None,
                    echeance=r.date_echeance, progression=r.progression or 0, statut=_statut_c2n(r),
                    cree_le=r.created_at, origine=(pl.reference if pl else ''),
                    lien=_url('c2n_detail_planification', id=r.planification_id) if r.planification_id else None, client_id=r.client_id, objet=r,
                    demandeur_id=r.demande_cloture_par_id, motif_refus=r.motif_refus_cloture)
    return dict(source=r.source, type='externe', id=r.id, reference=r.reference, titre=r.titre, description=r.description,
                priorite=r.priorite or 'moyenne', responsable_id=r.responsable_id, responsable=r.responsable,
                echeance=r.date_echeance, progression=r.progression or 0, statut=_statut_externe(r),
                cree_le=r.created_at, origine=r.emetteur or '', lien=_url('recommandations.externe', reco_id=r.id),
                client_id=r.client_id, objet=r, demandeur_id=r.demande_cloture_par_id, motif_refus=r.motif_refus_cloture)


def module_actif(type_, client=None):
    """L'origine est-elle permise par les modules du client ? (externes : toujours)"""
    code = MODULE_DE.get(type_)
    if code is None:
        return True
    from egalyx.modules_client import modules_du_client
    if client is None:
        m = _m()
        cid = client_id_courant()
        client = m.db.session.get(m.Client, cid) if cid else None
    try:
        actifs = modules_du_client(client)
    except Exception:
        return True
    return actifs is None or code in actifs


def _a(perms, u):
    return any(u.has_permission(p) for p in perms) if hasattr(u, 'has_permission') else False


def registre_disponible(u=None):
    """Module « Registre des recommandations » souscrit ET permission de le voir."""
    u = u or current_user
    if getattr(u, 'role', None) == 'super_admin':
        return True
    return module_actif('externe') and _a(VOIR, u)


def types_visibles(u=None):
    """Origines visibles dans le registre : registre disponible, et module de chaque origine souscrit."""
    u = u or current_user
    if not registre_disponible(u):
        return set()
    sa = getattr(u, 'role', None) == 'super_admin'
    return {t for t in ('audit', 'c2n', 'externe') if sa or module_actif(t)}


def registre(cid, responsable_id=None, types=None):
    """Recommandations de l'organisation (ou d'un responsable), au format commun.
    types : origines à inclure ('audit', 'c2n', 'externe') ; par défaut celles dont le module est actif."""
    m = _m()
    if types is None:
        client = m.db.session.get(m.Client, cid) if cid else None
        types = {t for t in ('audit', 'c2n', 'externe') if module_actif(t, client)}
    lignes = []
    if 'audit' in types:
        lignes += _recos_audit(cid, responsable_id)
    if 'c2n' in types:
        q = m.RecommandationC2N.query.filter_by(client_id=cid)
        if responsable_id:
            q = q.filter_by(responsable_id=responsable_id)
        lignes += [_ligne('c2n', r) for r in q.all()]
    if 'externe' in types:
        q = m.RecommandationExterne.query.filter_by(client_id=cid)
        if responsable_id:
            q = q.filter_by(responsable_id=responsable_id)
        lignes += [_ligne('externe', r) for r in q.all()]
    return _finaliser(lignes)


def _recos_audit(cid, responsable_id):
    m = _m()
    q = m.Recommandation.query.outerjoin(m.Audit, m.Recommandation.audit_id == m.Audit.id).filter(
        m.db.or_(m.Recommandation.client_id == cid, m.Audit.client_id == cid))
    if responsable_id:
        q = q.filter(m.Recommandation.responsable_id == responsable_id)
    return [_ligne('audit', r) for r in q.all()]


def _finaliser(lignes):
    auj = date.today()
    for l in lignes:
        ech = l['echeance'].date() if isinstance(l['echeance'], datetime) else l['echeance']
        l['echeance'] = ech
        l['echue'] = bool(ech and ech < auj and l['statut'] not in ('cloturee', 'rejetee'))
        l['retard_jours'] = (auj - ech).days if l['echue'] else 0
    lignes.sort(key=lambda l: (l['statut'] in ('cloturee', 'rejetee'), not l['echue'], l['echeance'] or date.max))
    return lignes


def indicateurs(lignes):
    """Chiffres pour le comité d'audit. Les recommandations proposées (pas encore retenues) et rejetées sont exclues."""
    retenues = [l for l in lignes if l['statut'] not in ('proposee', 'rejetee')]
    cloturees = [l for l in retenues if l['statut'] == 'cloturee']
    ouvertes = [l for l in retenues if l['statut'] != 'cloturee']
    echues = [l for l in ouvertes if l['echue']]
    maintenant = datetime.utcnow()
    ages = [(maintenant - l['cree_le'].replace(tzinfo=None)).days for l in ouvertes if l['cree_le']]
    par_source = {}
    for l in retenues:
        s = par_source.setdefault(l['source'], {'total': 0, 'cloturees': 0, 'echues': 0})
        s['total'] += 1
        s['cloturees'] += l['statut'] == 'cloturee'
        s['echues'] += l['echue']
    return {
        'total': len(retenues), 'cloturees': len(cloturees), 'ouvertes': len(ouvertes), 'echues': len(echues),
        'a_valider': len([l for l in ouvertes if l['statut'] == 'a_valider']),
        'taux_mise_en_oeuvre': round(100 * len(cloturees) / len(retenues)) if retenues else None,
        'anciennete_moyenne': round(sum(ages) / len(ages)) if ages else None,
        'plus_de_180_jours': len([a for a in ages if a > 180]),
        'par_source': par_source,
    }


# ---------------------------------------------------------------- accès
def charger(source, reco_id):
    """Recommandation de l'organisation courante, sinon 404 (jamais celle d'une autre organisation)."""
    m = _m()
    modele = {'audit': m.Recommandation, 'c2n': m.RecommandationC2N, 'externe': m.RecommandationExterne}.get(source)
    if modele is None:
        abort(404)
    r = m.db.session.get(modele, reco_id)
    if r is None:
        abort(404)
    ligne = _ligne(source, r)
    if getattr(current_user, 'role', None) != 'super_admin':
        if ligne['client_id'] != client_id_courant() or not module_actif(source):
            abort(404)        # autre organisation, ou module non souscrit
    return r, ligne


def est_gestionnaire(u=None, type_=None):
    """Gestionnaire des recommandations, pour une origine donnée (audit : gérer les audits ; N2 : gérer le N2 ;
    externes : l'un ou l'autre). L'admin client passe par has_permission, qui respecte les modules du client."""
    u = u or current_user
    if getattr(u, 'role', None) == 'super_admin':
        return True
    if not module_actif('externe') or (type_ and not module_actif(type_)):
        return False
    return _a(GERER_DE.get(type_, GERER), u)


def peut_voir(ligne, u=None):
    u = u or current_user
    return (getattr(u, 'role', None) == 'super_admin' or ligne['responsable_id'] == u.id
            or ligne['type'] in types_visibles(u))


def peut_avancer(ligne, u=None):
    u = u or current_user
    if ligne['statut'] in ('cloturee', 'rejetee', 'proposee'):
        return False
    return ligne['responsable_id'] == u.id or est_gestionnaire(u, ligne['type'])


def peut_decider_cloture(ligne, u=None):
    """Valider ou refuser la clôture : gestionnaire de cette origine, ni responsable ni auteur de la demande."""
    u = u or current_user
    if ligne['statut'] != 'a_valider' or not est_gestionnaire(u, ligne['type']):
        return False
    if getattr(u, 'role', None) == 'super_admin':
        return True
    return u.id not in (ligne['responsable_id'], ligne['demandeur_id'])


def _suivi(source, r, action, progression=None, commentaire=None, fichier=None, nom_fichier=None):
    m = _m()
    cid = getattr(r, 'client_id', None) or client_id_courant()
    m.db.session.add(m.SuiviRecommandation(client_id=cid, source=source, recommandation_id=r.id, action=action,
                                           progression=progression, commentaire=commentaire, fichier=fichier,
                                           nom_fichier=nom_fichier, user_id=current_user.id))


def _notifier(destinataires, titre, message, lien_id, cid):
    m = _m()
    for d in {x for x in destinataires if x}:
        try:
            m.db.session.add(m.Notification(destinataire_id=d, type_notification='recommandation', titre=titre[:200],
                                            message=message[:500], entite_type='recommandation', entite_id=lien_id,
                                            client_id=cid))
        except Exception:
            pass


def _gestionnaires(cid, type_=None):
    m = _m()
    out = []
    for u in m.User.query.filter_by(client_id=cid, is_active=True).all():
        if getattr(u, 'is_operateur', False):
            continue
        try:
            if any(u.has_permission(p) for p in GERER_DE.get(type_, GERER)):
                out.append(u.id)
        except Exception:
            pass
    return out


def _ecrire_progression(source, r, valeur):
    if source == 'audit':
        r.taux_avancement = valeur
        if valeur > 0 and (r.statut or 'a_traiter') == 'a_traiter':
            r.statut = 'en_cours'
    elif source == 'c2n':
        r.progression = valeur
    else:
        r.progression = valeur
        if valeur > 0 and r.statut == 'ouverte':
            r.statut = 'en_cours'


def _enregistrer_preuve(fichier):
    if not fichier or not fichier.filename:
        return None, None
    nom = secure_filename(fichier.filename) or 'preuve'
    ext = nom.rsplit('.', 1)[-1].lower() if '.' in nom else ''
    if ext not in EXTENSIONS:
        raise ValueError(f"Type de fichier non accepté (.{ext or '?'}). Formats acceptés : PDF, images, Office, texte, ZIP.")
    fichier.stream.seek(0, os.SEEK_END)
    taille = fichier.stream.tell()
    fichier.stream.seek(0)
    if taille > TAILLE_MAX:
        raise ValueError('Fichier trop volumineux (15 Mo au maximum).')
    dossier = os.path.join(current_app.instance_path, 'preuves_recommandations', str(client_id_courant() or 0))
    os.makedirs(dossier, mode=0o750, exist_ok=True)
    chemin = os.path.join(dossier, f'{uuid.uuid4().hex}.{ext}')
    fichier.save(chemin)
    return os.path.relpath(chemin, current_app.instance_path), nom


# ---------------------------------------------------------------- pages
def _gabarit_base():
    return 'operateur/base_operateur.html' if getattr(current_user, 'is_operateur', False) else 'base.html'


@bp.route('/')
@permission_requise(*VOIR)
def registre_page():
    cid = client_id_courant()
    types = types_visibles()
    if not types:
        flash("Le registre des recommandations n'est pas disponible (module non souscrit ou permission manquante).", 'warning')
        return redirect(url_for('dashboard'))
    lignes = registre(cid, types=types)
    ind = indicateurs(lignes)
    f_source, f_statut, f_echues = request.args.get('source', ''), request.args.get('statut', ''), request.args.get('echues')
    vues = [l for l in lignes
            if (not f_source or l['source'] == f_source)
            and (not f_statut or l['statut'] == f_statut)
            and (not f_echues or l['echue'])]
    return render_template('egalyx/recommandations_registre.html', lignes=vues, ind=ind, sources=SOURCES,
                           statuts=STATUTS, priorites=PRIORITES, f_source=f_source, f_statut=f_statut,
                           f_echues=f_echues, peut_gerer=est_gestionnaire(type_='externe'), base_layout='base.html')


# l'ancien nom court sert dans les menus
bp.add_url_rule('/registre', 'registre', registre_page)


@bp.route('/miennes')
@login_required
def miennes():
    cid = client_id_courant()
    if not cid:
        abort(403)
    if not module_actif('externe'):
        flash("Le registre des recommandations n'est pas activé pour votre organisation.", 'info')
        return redirect(url_for('dashboard'))
    lignes = [l for l in registre(cid, responsable_id=current_user.id) if l['statut'] != 'proposee']
    a_decider = [l for l in registre(cid, types=types_visibles()) if peut_decider_cloture(l)]
    return render_template('egalyx/recommandations_miennes.html', lignes=lignes, a_decider=a_decider, sources=SOURCES,
                           statuts=STATUTS, priorites=PRIORITES, base_layout=_gabarit_base())


@bp.route('/externe/nouvelle', methods=['GET', 'POST'])
@permission_requise(*GERER)
def externe_nouvelle():
    return _formulaire_externe(None)


@bp.route('/externe/<int:reco_id>/modifier', methods=['GET', 'POST'])
@permission_requise(*GERER)
def externe_modifier(reco_id):
    r, _ = charger('externe', reco_id)
    return _formulaire_externe(r)


def _formulaire_externe(r):
    m = _m()
    cid = client_id_courant()
    utilisateurs = m.User.query.filter_by(client_id=cid, is_active=True).order_by(m.User.username).all()
    directions = m.Direction.query.filter_by(client_id=cid).order_by(m.Direction.nom).all()
    if request.method == 'POST':
        f = request.form
        titre = (f.get('titre') or '').strip()
        source = f.get('source') if f.get('source') in SOURCES_EXTERNES else 'cac'
        if len(titre) < 5:
            flash('Indiquez un intitulé (5 caractères au moins).', 'warning')
            return render_template('egalyx/recommandation_externe_form.html', r=r, f=f, sources=SOURCES,
                                   externes=SOURCES_EXTERNES, priorites=PRIORITES, utilisateurs=utilisateurs,
                                   directions=directions)
        nouveau = r is None
        if nouveau:
            n = m.RecommandationExterne.query.filter_by(client_id=cid).count() + 1
            r = m.RecommandationExterne(client_id=cid, created_by=current_user.id,
                                        reference=(f.get('reference') or '').strip() or f'EXT-{date.today().year}-{n:03d}')
            m.db.session.add(r)
        elif (f.get('reference') or '').strip():
            r.reference = f.get('reference').strip()[:60]
        r.source, r.titre = source, titre[:300]
        r.emetteur = (f.get('emetteur') or '').strip()[:200] or None
        r.description = (f.get('description') or '').strip() or None
        r.priorite = f.get('priorite') if f.get('priorite') in PRIORITES else 'moyenne'
        r.date_emission = _date(f.get('date_emission'))
        r.date_echeance = _date(f.get('date_echeance'))
        uid = entier(f.get('responsable_id'))
        r.responsable_id = uid if uid and any(u.id == uid for u in utilisateurs) else None
        did = entier(f.get('direction_id'))
        r.direction_id = did if did and any(d.id == did for d in directions) else None
        m.db.session.flush()
        if nouveau:
            _suivi('externe', r, 'creation', commentaire=f'Source : {SOURCES[source]}')
            if r.responsable_id:
                _notifier([r.responsable_id], f'Recommandation à mettre en œuvre : {r.reference}', r.titre, r.id, cid)
        m.db.session.commit()
        journaliser('recommandation_externe_' + ('creee' if nouveau else 'modifiee'), {'id': r.id})
        flash('Recommandation enregistrée.', 'success')
        return redirect(url_for('recommandations.externe', reco_id=r.id))
    return render_template('egalyx/recommandation_externe_form.html', r=r, f=None, sources=SOURCES,
                           externes=SOURCES_EXTERNES, priorites=PRIORITES, utilisateurs=utilisateurs, directions=directions)


def _date(v):
    try:
        return datetime.strptime(v, '%Y-%m-%d').date() if v else None
    except ValueError:
        return None


@bp.route('/externe/<int:reco_id>')
@login_required
def externe(reco_id):
    return fiche('externe', reco_id)


@bp.route('/<source>/<int:reco_id>')
@login_required
def fiche(source, reco_id):
    m = _m()
    r, l = charger(source, reco_id)
    if not peut_voir(l):
        abort(403)
    suivis = (m.SuiviRecommandation.query.filter_by(source=source, recommandation_id=reco_id)
              .order_by(m.SuiviRecommandation.created_at.desc()).all())
    return render_template('egalyx/recommandation_fiche.html', l=l, suivis=suivis, sources=SOURCES, statuts=STATUTS,
                           priorites=PRIORITES, peut_avancer=peut_avancer(l), peut_decider=peut_decider_cloture(l),
                           est_gestionnaire=est_gestionnaire(type_=l['type']), base_layout=_gabarit_base(),
                           peut_effacer=peut_effacer_historique(l))


@bp.route('/<source>/<int:reco_id>/avancement', methods=['POST'])
@login_required
def avancement(source, reco_id):
    m = _m()
    r, l = charger(source, reco_id)
    if not peut_avancer(l):
        abort(403)
    valeur = entier(request.form.get('progression'), defaut=l['progression'], mini=0, maxi=100)
    commentaire = (request.form.get('commentaire') or '').strip()
    if not commentaire:
        flash("Décrivez ce qui a été fait : l'auditeur s'appuie sur ce commentaire.", 'warning')
        return redirect(url_for('recommandations.fiche', source=source, reco_id=reco_id))
    try:
        chemin, nom = _enregistrer_preuve(request.files.get('preuve'))
    except ValueError as e:
        flash(str(e), 'warning')
        return redirect(url_for('recommandations.fiche', source=source, reco_id=reco_id))
    demander = valeur >= 100 and request.form.get('demander_cloture') == '1'
    if demander and not chemin and not m.SuiviRecommandation.query.filter(
            m.SuiviRecommandation.source == source, m.SuiviRecommandation.recommandation_id == reco_id,
            m.SuiviRecommandation.fichier.isnot(None)).count():
        flash('Pour demander la clôture, joignez au moins une preuve de mise en œuvre.', 'warning')
        return redirect(url_for('recommandations.fiche', source=source, reco_id=reco_id))
    _ecrire_progression(source, r, valeur)
    _suivi(source, r, 'avancement', progression=valeur, commentaire=commentaire, fichier=chemin, nom_fichier=nom)
    if demander:
        r.demande_cloture_le, r.demande_cloture_par_id, r.motif_refus_cloture = datetime.utcnow(), current_user.id, None
        _suivi(source, r, 'demande_cloture', progression=100)
        cid = l['client_id']
        _notifier([g for g in _gestionnaires(cid, l['type']) if g != current_user.id],
                  f'Clôture à valider : {l["reference"]}', f'{current_user.username} demande la clôture de « {l["titre"]} ».',
                  reco_id, cid)
        flash("Clôture demandée : un gestionnaire va la valider.", 'success')
    else:
        flash('Avancement enregistré.', 'success')
    m.db.session.commit()
    return redirect(url_for('recommandations.fiche', source=source, reco_id=reco_id))


@bp.route('/<source>/<int:reco_id>/cloture', methods=['POST'])
@login_required
def cloture(source, reco_id):
    m = _m()
    r, l = charger(source, reco_id)
    if not peut_decider_cloture(l):
        flash("Vous ne pouvez pas décider de cette clôture (il faut être gestionnaire, et ni le responsable "
              "ni l'auteur de la demande).", 'warning')
        return redirect(url_for('recommandations.fiche', source=source, reco_id=reco_id))
    decision = request.form.get('decision')
    commentaire = (request.form.get('commentaire') or '').strip()
    if decision == 'valider':
        maintenant = datetime.utcnow()
        r.cloture_validee_le, r.cloture_validee_par_id = maintenant, current_user.id
        if source == 'audit':
            r.statut, r.taux_avancement = 'termine', 100
        elif source == 'c2n':
            r.statut, r.progression = 'realisee', 100
            r.date_fin_reelle = maintenant.date()
        else:
            r.statut, r.progression = 'cloturee', 100
        _suivi(source, r, 'cloture_validee', progression=100, commentaire=commentaire or None)
        _notifier([l['responsable_id'], l['demandeur_id']], f'Clôture validée : {l["reference"]}', l['titre'], reco_id,
                  l['client_id'])
        flash('Recommandation clôturée.', 'success')
    elif decision == 'refuser':
        if len(commentaire) < 10:
            flash('Expliquez le refus (10 caractères au moins) : le responsable doit savoir quoi compléter.', 'warning')
            return redirect(url_for('recommandations.fiche', source=source, reco_id=reco_id))
        r.demande_cloture_le = r.demande_cloture_par_id = None
        r.motif_refus_cloture = commentaire
        _suivi(source, r, 'cloture_refusee', commentaire=commentaire)
        _notifier([l['responsable_id'], l['demandeur_id']], f'Clôture refusée : {l["reference"]}', commentaire, reco_id,
                  l['client_id'])
        flash('Clôture refusée : le responsable est prévenu.', 'info')
    else:
        abort(400)
    m.db.session.commit()
    return redirect(url_for('recommandations.fiche', source=source, reco_id=reco_id))


def _supprimer_preuve(s):
    if not s.fichier:
        return
    chemin = os.path.realpath(os.path.join(current_app.instance_path, s.fichier))
    racine = os.path.realpath(os.path.join(current_app.instance_path, 'preuves_recommandations'))
    if chemin.startswith(racine + os.sep) and os.path.exists(chemin):
        try:
            os.remove(chemin)
        except OSError:
            pass


def peut_effacer_historique(l, u=None):
    """Effacer l'historique : gestionnaire des recommandations de cette origine (ou admin de l'organisation)."""
    return est_gestionnaire(u, type_=l['type'])


@bp.route('/<source>/<int:reco_id>/historique/<int:suivi_id>/supprimer', methods=['POST'])
@login_required
def supprimer_suivi(source, reco_id, suivi_id):
    """Supprime une ligne de l'historique (et sa preuve jointe). L'état de la recommandation ne change pas ;
    la suppression elle-même reste inscrite au journal d'activité."""
    m = _m()
    _r, l = charger(source, reco_id)
    if not peut_effacer_historique(l):
        abort(403)
    s = m.db.session.get(m.SuiviRecommandation, suivi_id)
    if s is None or s.recommandation_id != reco_id or s.source != source or s.client_id != l['client_id']:
        abort(404)
    journaliser('historique_recommandation_supprime', {
        'recommandation': l['reference'], 'source': source, 'action': s.action, 'progression': s.progression,
        'commentaire': (s.commentaire or '')[:300], 'preuve': s.nom_fichier,
        'date': s.created_at.isoformat() if s.created_at else None}, client_id=l['client_id'])
    _supprimer_preuve(s)
    m.db.session.delete(s)
    m.db.session.commit()
    flash("Ligne d'historique supprimée.", 'success')
    return redirect(url_for('recommandations.fiche', source=source, reco_id=reco_id))


@bp.route('/<source>/<int:reco_id>/historique/vider', methods=['POST'])
@login_required
def vider_historique(source, reco_id):
    """Supprime tout l'historique d'une recommandation (et les preuves jointes)."""
    m = _m()
    _r, l = charger(source, reco_id)
    if not peut_effacer_historique(l):
        abort(403)
    suivis = m.SuiviRecommandation.query.filter_by(source=source, recommandation_id=reco_id,
                                                   client_id=l['client_id']).all()
    for s in suivis:
        _supprimer_preuve(s)
        m.db.session.delete(s)
    journaliser('historique_recommandation_vide', {'recommandation': l['reference'], 'source': source,
                                                   'lignes': len(suivis)}, client_id=l['client_id'])
    m.db.session.commit()
    flash(f"Historique vidé ({len(suivis)} ligne(s)).", 'success')
    return redirect(url_for('recommandations.fiche', source=source, reco_id=reco_id))


@bp.route('/preuve/<int:suivi_id>')
@login_required
def preuve(suivi_id):
    m = _m()
    s = m.db.session.get(m.SuiviRecommandation, suivi_id)
    if s is None or not s.fichier:
        abort(404)
    _r, l = charger(s.source if s.source in ('audit', 'c2n') else 'externe', s.recommandation_id)
    if not peut_voir(l):
        abort(403)
    chemin = os.path.realpath(os.path.join(current_app.instance_path, s.fichier))
    racine = os.path.realpath(os.path.join(current_app.instance_path, 'preuves_recommandations'))
    if not chemin.startswith(racine + os.sep) or not os.path.exists(chemin):
        abort(404)
    return send_file(chemin, as_attachment=True, download_name=s.nom_fichier or os.path.basename(chemin))


# ---------------------------------------------------------------- intégration
def _migrer_permissions(app):
    """Une seule fois : ceux qui géraient déjà les recommandations (droits d'audit ou du N2) reçoivent les nouvelles
    permissions du registre, pour que la création de ces permissions ne leur retire rien."""
    from egalyx.ia import reglages, ecrire_reglage
    with app.app_context():
        try:
            if reglages().get('migration_permissions_recommandations'):
                return
            m = _m()
            n = 0
            for u in m.User.query.all():
                p = dict(u.permissions or {})
                if 'can_view_recommandations' in p and p.get('can_view_recommandations') is True:
                    continue
                if p.get('can_manage_audit') or p.get('can_manage_controle_interne_n2'):
                    p['can_view_recommandations'] = True
                    p['can_manage_recommandations'] = True
                    u.permissions = p
                    n += 1
            m.db.session.commit()
            ecrire_reglage('migration_permissions_recommandations', True)
            if n:
                print(f"✅ Recommandations : permissions du registre données à {n} gestionnaire(s) d'audit ou du N2")
        except Exception as e:
            try:
                _m().db.session.rollback()
            except Exception:
                pass
            app.logger.warning('Migration des permissions du registre : %s', e)


def enregistrer(app):
    app.register_blueprint(bp)
    _migrer_permissions(app)

    @app.context_processor
    def _recos():
        def mes_recommandations_ouvertes():
            try:
                cid = client_id_courant()
                if not cid or not current_user.is_authenticated:
                    return 0
                return len([l for l in registre(cid, responsable_id=current_user.id)
                            if l['statut'] in ('ouverte', 'en_cours')])
            except Exception:
                return 0
        return {'mes_recommandations_ouvertes': mes_recommandations_ouvertes}
