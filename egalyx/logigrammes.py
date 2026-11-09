"""
egalyx/logigrammes.py — gouvernance des logigrammes (procédures).

1. Versions et validation : brouillon → en validation → validé (version n, copie figée consultable).
   Toute modification d'un logigramme validé le repasse en brouillon : la version validée reste
   « en vigueur » et consultable jusqu'à la validation suivante. Rejet motivé. Revue annuelle :
   date de revue = validation + 12 mois ; « Confirmer la revue » sans modification est tracé.
   L'auteur peut valider sa propre procédure (tracé « auto-validation ») ;
   EGALYX_LOGIGRAMME_DOUBLE_REGARD=1 impose un second gestionnaire (sauf s'il est seul).
2. Couloirs : liste ordonnée d'acteurs ; chaque étape appartient au couloir où elle est dessinée.
3. Vérification du dessin : erreurs bloquantes pour la soumission (pas de début / de fin, étape isolée,
   décision à une seule sortie) et avertissements (sorties de décision non libellées, étapes inaccessibles,
   contrôle non rattaché au référentiel, étape hors couloir…).
4. Conversion d'un ancien « Processus » (étapes + liens) en logigramme, une seule fois, en gardant le lien.
"""
import os
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from egalyx.commun import a_permission, client_id_courant, entier, journaliser

bp = Blueprint('logigrammes', __name__, url_prefix='/logigrammes-suivi')

GERER = ('can_manage_logigram',)
STATUTS = {'brouillon': 'Brouillon', 'en_validation': 'En validation', 'valide': 'Validé'}
HAUTEUR_COULOIR = 170
TYPES_FLUX = ('debut', 'action', 'decision', 'controle', 'fin')
TYPES_DECOR = ('titre', 'organisation')
REVUE_MOIS = 12


def _m():
    import models
    return models


def statut(a):
    return a.statut_validation or 'brouillon'


# ---------------------------------------------------------------- accès
def module_actif():
    from egalyx.modules_client import modules_du_client
    m = _m()
    cid = client_id_courant()
    try:
        actifs = modules_du_client(m.db.session.get(m.Client, cid) if cid else None)
    except Exception:
        return True
    return actifs is None or 'processus' in actifs


def charger(activite_id):
    m = _m()
    a = m.db.session.get(m.ProcessusActivite, activite_id)
    if a is None:
        abort(404)
    if getattr(current_user, 'role', None) != 'super_admin':
        if a.client_id != client_id_courant() or not module_actif():
            abort(404)
    return a


def est_gestionnaire(u=None):
    u = u or current_user
    return getattr(u, 'role', None) == 'super_admin' or a_permission(*GERER, u=u)


def peut_voir(a, u=None):
    u = u or current_user
    return est_gestionnaire(u) or a.proprietaire_id == u.id


# ---------------------------------------------------------------- contenu, couloirs, vérification
def contenu(a):
    """Copie complète et autonome du logigramme (pour figer une version)."""
    m = _m()
    els = m.ElementLogigramme.query.filter_by(activite_id=a.id).order_by(m.ElementLogigramme.id).all()
    ids = [e.id for e in els]
    liens = m.LienLogigramme.query.filter_by(activite_id=a.id).all()
    risques, controles = {}, {}
    if ids:
        for x in m.RisqueElementLogigramme.query.filter(m.RisqueElementLogigramme.element_logigramme_id.in_(ids)).all():
            r = m.db.session.get(m.Risque, x.risque_id)
            risques.setdefault(x.element_logigramme_id, []).append(r.reference if r else f'#{x.risque_id}')
        for x in m.ControleElementLogigramme.query.filter(m.ControleElementLogigramme.element_logigramme_id.in_(ids)).all():
            c = m.db.session.get(m.ControleProcessus, x.controle_id)
            controles.setdefault(x.element_logigramme_id, []).append((c.reference or c.nom) if c else f'#{x.controle_id}')
    acteurs = list(a.acteurs or [])
    return {
        'nom': a.nom, 'description': a.description, 'acteurs': acteurs,
        'elements': [{'id': e.id, 'type': e.type_element, 'libelle': e.libelle, 'description': e.description,
                      'x': e.position_x or 0, 'y': e.position_y or 0,
                      'l': (e.style or {}).get('width') or (4 if e.type_element == 'organisation' else 120),
                      'h': (e.style or {}).get('height') or (200 if e.type_element == 'organisation' else 70),
                      'acteur': acteur_de(e, acteurs), 'risques': risques.get(e.id, []), 'controles': controles.get(e.id, [])}
                     for e in els],
        'liens': [{'source': l.element_source_id, 'cible': l.element_cible_id, 'libelle': _libelle_lien(l)} for l in liens],
    }


def _libelle_lien(l):
    if l.libelle:
        return l.libelle
    t = (l.style or {}).get('type')
    return {'oui': 'Oui', 'non': 'Non'}.get(t, '')


def acteur_de(e, acteurs):
    """Acteur du couloir dans lequel l'étape est dessinée (selon le centre vertical de l'étape)."""
    if not acteurs:
        return None
    h = ((e.style or {}).get('height') or 70) if hasattr(e, 'style') else 70
    centre = (e.position_y or 0) + h / 2
    i = int(centre // HAUTEUR_COULOIR)
    return acteurs[i] if 0 <= i < len(acteurs) else None


def verifier(a):
    """{'erreurs': [...], 'avertissements': [...]} — chaque point : {'message', 'elements': [ids]}"""
    m = _m()
    els = m.ElementLogigramme.query.filter_by(activite_id=a.id).all()
    liens = m.LienLogigramme.query.filter_by(activite_id=a.id).all()
    flux = {e.id: e for e in els if e.type_element in TYPES_FLUX}
    erreurs, avert = [], []
    def point(liste, message, ids=()):
        liste.append({'message': message, 'elements': list(ids)})
    if not flux:
        point(erreurs, "Le logigramme est vide : dessinez au moins un début, des étapes et une fin.")
        return {'erreurs': erreurs, 'avertissements': avert, 'ok': False}
    entrees, sorties = {}, {}
    for l in liens:
        sorties.setdefault(l.element_source_id, []).append(l)
        entrees.setdefault(l.element_cible_id, []).append(l)
    debuts = [e for e in flux.values() if e.type_element == 'debut']
    fins = [e for e in flux.values() if e.type_element == 'fin']
    if not debuts:
        point(erreurs, "Aucun « Début » : indiquez où commence la procédure.")
    if not fins:
        point(erreurs, "Aucune « Fin » : indiquez où s'arrête la procédure.")
    isoles = [e for e in flux.values() if e.id not in entrees and e.id not in sorties]
    if isoles and len(flux) > 1:
        point(erreurs, f"{len(isoles)} étape(s) reliée(s) à rien : " + ', '.join(f"« {e.libelle} »" for e in isoles[:5]),
              [e.id for e in isoles])
    for e in flux.values():
        if e.type_element == 'decision':
            s = sorties.get(e.id, [])
            if len(s) < 2:
                point(erreurs, f"La décision « {e.libelle} » doit avoir au moins deux sorties (ex. Oui / Non).", [e.id])
            elif any(not (l.libelle or (l.style or {}).get('type') in ('oui', 'non')) for l in s):
                point(avert, f"Libellez les sorties de la décision « {e.libelle} » (Oui / Non…).", [e.id])
        if e.type_element == 'fin' and sorties.get(e.id):
            point(avert, f"La fin « {e.libelle} » a une flèche sortante.", [e.id])
        if e.type_element == 'debut' and entrees.get(e.id):
            point(avert, f"Le début « {e.libelle} » a une flèche entrante.", [e.id])
        if e.type_element not in ('fin',) and e.id in entrees and not sorties.get(e.id) and e.type_element != 'debut':
            point(avert, f"« {e.libelle} » est une impasse : aucune suite et ce n'est pas une fin.", [e.id])
    if debuts:
        vus, pile = set(), [d.id for d in debuts]
        while pile:
            x = pile.pop()
            if x in vus:
                continue
            vus.add(x)
            pile += [l.element_cible_id for l in sorties.get(x, [])]
        hors = [e for e in flux.values() if e.id not in vus and e not in isoles]
        if hors:
            point(avert, f"{len(hors)} étape(s) inaccessible(s) depuis le début : " + ', '.join(f"« {e.libelle} »" for e in hors[:5]),
                  [e.id for e in hors])
    ctrl = [e for e in flux.values() if e.type_element == 'controle']
    if ctrl:
        lies = {x.element_logigramme_id for x in m.ControleElementLogigramme.query.filter(
            m.ControleElementLogigramme.element_logigramme_id.in_([e.id for e in ctrl])).all()}
        sans = [e for e in ctrl if e.id not in lies]
        if sans:
            point(avert, f"{len(sans)} contrôle(s) dessiné(s) sans contrôle du référentiel rattaché : " +
                  ', '.join(f"« {e.libelle} »" for e in sans[:5]), [e.id for e in sans])
    if a.acteurs:
        hors = [e for e in flux.values() if acteur_de(e, a.acteurs) is None]
        if hors:
            point(avert, f"{len(hors)} étape(s) en dehors des couloirs d'acteurs.", [e.id for e in hors])
    return {'erreurs': erreurs, 'avertissements': avert, 'ok': not erreurs}


# ---------------------------------------------------------------- notifications
def _gestionnaires(cid):
    m = _m()
    out = []
    for u in m.User.query.filter_by(client_id=cid, is_active=True).all():
        if getattr(u, 'is_operateur', False):
            continue
        try:
            if u.has_permission('can_manage_logigram'):
                out.append(u.id)
        except Exception:
            pass
    return out


def _notifier(ids, titre, message, a):
    m = _m()
    for uid in {i for i in ids if i and i != current_user.id}:
        m.db.session.add(m.Notification(destinataire_id=uid, type_notification='logigramme', titre=titre[:200],
                                        message=message[:500], entite_type='logigramme', entite_id=a.id, client_id=a.client_id))


# ---------------------------------------------------------------- page de suivi
@bp.route('/<int:activite_id>')
@login_required
def suivi(activite_id):
    m = _m()
    a = charger(activite_id)
    if not peut_voir(a):
        abort(403)
    versions = (m.VersionLogigramme.query.filter_by(activite_id=a.id)
                .order_by(m.VersionLogigramme.created_at.desc()).all())
    utilisateurs = m.User.query.filter_by(client_id=a.client_id, is_active=True).order_by(m.User.username).all()
    noms = {u.id: u.username for u in utilisateurs}
    return render_template('egalyx/logigramme_suivi.html', a=a, statut=statut(a), statuts=STATUTS, versions=versions,
                           verif=verifier(a), utilisateurs=utilisateurs, noms=noms, gest=est_gestionnaire(),
                           aujourd_hui=date.today(), peut_valider=peut_valider(a))


def peut_valider(a, u=None):
    u = u or current_user
    if statut(a) != 'en_validation' or not est_gestionnaire(u):
        return False
    if getattr(u, 'role', None) == 'super_admin':
        return True
    if os.environ.get('EGALYX_LOGIGRAMME_DOUBLE_REGARD', '0') == '1' and u.id in (a.soumis_par_id, a.created_by):
        return len(_gestionnaires(a.client_id)) <= 1
    return True


@bp.route('/<int:activite_id>/proprietaire', methods=['POST'])
@login_required
def proprietaire(activite_id):
    m = _m()
    a = charger(activite_id)
    if not est_gestionnaire():
        abort(403)
    uid = entier(request.form.get('proprietaire_id'))
    u = m.db.session.get(m.User, uid) if uid else None
    a.proprietaire_id = u.id if u and u.client_id == a.client_id else None
    m.db.session.commit()
    flash('Propriétaire enregistré.', 'success')
    return redirect(url_for('logigrammes.suivi', activite_id=a.id))


@bp.route('/<int:activite_id>/acteurs', methods=['GET', 'POST'])
@login_required
def acteurs(activite_id):
    m = _m()
    a = charger(activite_id)
    if request.method == 'GET':
        if not (peut_voir(a) or a_permission('can_manage_logigram')):
            abort(403)
        return jsonify({'acteurs': list(a.acteurs or []), 'hauteur': HAUTEUR_COULOIR})
    if not est_gestionnaire():
        abort(403)
    lignes = [x.strip()[:60] for x in (request.form.get('acteurs') or '').splitlines() if x.strip()]
    vus, liste = set(), []
    for x in lignes:
        if x.lower() not in vus:
            vus.add(x.lower()); liste.append(x)
    a.acteurs = liste[:12] or None
    if statut(a) != 'brouillon':
        a.statut_validation = 'brouillon'
    m.db.session.commit()
    flash(f"{len(liste)} couloir(s) d'acteurs enregistré(s). Placez chaque étape dans le couloir de celui qui la réalise.", 'success')
    return redirect(request.referrer or url_for('logigrammes.suivi', activite_id=a.id))


@bp.route('/<int:activite_id>/verification')
@login_required
def verification(activite_id):
    a = charger(activite_id)
    if not (peut_voir(a) or a_permission('can_manage_logigram')):
        abort(403)
    return jsonify(verifier(a))


@bp.route('/<int:activite_id>/soumettre', methods=['POST'])
@login_required
def soumettre(activite_id):
    m = _m()
    a = charger(activite_id)
    if not (est_gestionnaire() or a.proprietaire_id == current_user.id):
        abort(403)
    if statut(a) != 'brouillon':
        flash('Seul un brouillon peut être soumis à validation.', 'info')
        return redirect(url_for('logigrammes.suivi', activite_id=a.id))
    v = verifier(a)
    if v['erreurs']:
        flash('Corrigez d\'abord le dessin : ' + ' · '.join(x['message'] for x in v['erreurs']), 'warning')
        return redirect(url_for('logigrammes.suivi', activite_id=a.id))
    a.statut_validation = 'en_validation'
    a.soumis_le, a.soumis_par_id, a.motif_rejet = datetime.utcnow(), current_user.id, None
    _notifier(_gestionnaires(a.client_id), f'Procédure à valider : {a.nom}',
              f'{current_user.username} soumet la procédure « {a.nom} » à validation.', a)
    m.db.session.commit()
    journaliser('logigramme_soumis', {'id': a.id})
    flash('Procédure soumise à validation.', 'success')
    return redirect(url_for('logigrammes.suivi', activite_id=a.id))


@bp.route('/<int:activite_id>/valider', methods=['POST'])
@login_required
def valider(activite_id):
    m = _m()
    a = charger(activite_id)
    if not peut_valider(a):
        flash("Vous ne pouvez pas valider cette procédure (gestionnaire des logigrammes requis"
              + (", autre que son auteur" if os.environ.get('EGALYX_LOGIGRAMME_DOUBLE_REGARD', '0') == '1' else '') + ').', 'warning')
        return redirect(url_for('logigrammes.suivi', activite_id=a.id))
    if verifier(a)['erreurs']:
        flash('Le dessin contient des erreurs : il ne peut pas être validé.', 'warning')
        return redirect(url_for('logigrammes.suivi', activite_id=a.id))
    auto = current_user.id in (a.soumis_par_id, a.created_by)
    a.version_courante = (a.version_courante or 0) + 1
    a.statut_validation = 'valide'
    a.valide_le, a.valide_par_id = datetime.utcnow(), current_user.id
    a.date_revue_prevue = date.today() + timedelta(days=365 * REVUE_MOIS // 12)
    m.db.session.add(m.VersionLogigramme(client_id=a.client_id, activite_id=a.id, version=a.version_courante,
                                         nature='auto_validation' if auto else 'validation', contenu=contenu(a),
                                         commentaire=(request.form.get('commentaire') or '').strip() or None,
                                         user_id=current_user.id))
    _notifier([a.soumis_par_id, a.proprietaire_id], f'Procédure validée : {a.nom} (v{a.version_courante})',
              f'Version {a.version_courante} validée par {current_user.username}.', a)
    m.db.session.commit()
    journaliser('logigramme_valide', {'id': a.id, 'version': a.version_courante, 'auto': auto})
    flash(f'Version {a.version_courante} validée. Prochaine revue : {a.date_revue_prevue.strftime("%d/%m/%Y")}.', 'success')
    return redirect(url_for('logigrammes.suivi', activite_id=a.id))


@bp.route('/<int:activite_id>/rejeter', methods=['POST'])
@login_required
def rejeter(activite_id):
    m = _m()
    a = charger(activite_id)
    if statut(a) != 'en_validation' or not est_gestionnaire():
        abort(403)
    motif = (request.form.get('motif') or '').strip()
    if len(motif) < 10:
        flash('Expliquez ce qui doit être corrigé (10 caractères au moins).', 'warning')
        return redirect(url_for('logigrammes.suivi', activite_id=a.id))
    a.statut_validation, a.motif_rejet = 'brouillon', motif
    _notifier([a.soumis_par_id, a.proprietaire_id], f'Procédure à corriger : {a.nom}', motif, a)
    m.db.session.commit()
    flash('Procédure renvoyée en brouillon.', 'info')
    return redirect(url_for('logigrammes.suivi', activite_id=a.id))


@bp.route('/<int:activite_id>/revue', methods=['POST'])
@login_required
def revue(activite_id):
    """Revue annuelle sans modification : la version en vigueur est confirmée pour un an."""
    m = _m()
    a = charger(activite_id)
    if not (est_gestionnaire() or a.proprietaire_id == current_user.id):
        abort(403)
    if statut(a) != 'valide':
        flash("La revue sans modification concerne une procédure validée et non modifiée depuis.", 'warning')
        return redirect(url_for('logigrammes.suivi', activite_id=a.id))
    a.date_revue_prevue = date.today() + timedelta(days=365)
    m.db.session.add(m.VersionLogigramme(client_id=a.client_id, activite_id=a.id, version=a.version_courante or 0,
                                         nature='revue', commentaire=(request.form.get('commentaire') or '').strip()
                                         or 'Revue annuelle : procédure toujours à jour', user_id=current_user.id))
    m.db.session.commit()
    flash(f'Revue enregistrée. Prochaine revue : {a.date_revue_prevue.strftime("%d/%m/%Y")}.', 'success')
    return redirect(url_for('logigrammes.suivi', activite_id=a.id))


@bp.route('/<int:activite_id>/version/<int:version_id>')
@login_required
def version(activite_id, version_id):
    m = _m()
    a = charger(activite_id)
    if not (peut_voir(a) or a_permission('can_manage_logigram')):
        abort(403)
    v = m.db.session.get(m.VersionLogigramme, version_id)
    if v is None or v.activite_id != a.id or not v.contenu:
        abort(404)
    c = v.contenu
    els = c.get('elements', [])
    largeur = max([e['x'] + e['l'] for e in els] + [600]) + 60
    hauteur = max([e['y'] + e['h'] for e in els] + [len(c.get('acteurs') or []) * HAUTEUR_COULOIR, 300]) + 60
    par_id = {e['id']: e for e in els}
    return render_template('egalyx/logigramme_version.html', a=a, v=v, c=c, largeur=largeur, hauteur=hauteur,
                           par_id=par_id, hauteur_couloir=HAUTEUR_COULOIR)


# ---------------------------------------------------------------- conversion d'un ancien « Processus »
TYPES_ETAPE = {'action': 'action', 'decision': 'decision', 'controle': 'controle', 'attente': 'action', 'fin': 'fin'}


@bp.route('/convertir-processus/<int:processus_id>', methods=['POST'])
@login_required
def convertir(processus_id):
    m = _m()
    p = m.db.session.get(m.Processus, processus_id)
    if p is None or (getattr(current_user, 'role', None) != 'super_admin' and p.client_id != client_id_courant()):
        abort(404)
    if not est_gestionnaire() or not module_actif():
        abort(403)
    deja = m.ProcessusActivite.query.filter_by(processus_source_id=p.id).first()
    if deja:
        flash('Ce processus a déjà été converti : voici son logigramme.', 'info')
        return redirect(url_for('editer_logigramme', id=deja.id))
    etapes = (m.EtapeProcessus.query.filter_by(processus_id=p.id)
              .filter(m.db.or_(m.EtapeProcessus.is_archived == False, m.EtapeProcessus.is_archived.is_(None)))  # noqa: E712
              .order_by(m.EtapeProcessus.ordre).all())
    noms = {}
    for e in etapes:
        if e.responsable_id and e.responsable_id not in noms:
            u = m.db.session.get(m.User, e.responsable_id)
            noms[e.responsable_id] = u.username if u else f'Acteur {len(noms) + 1}'
    acteurs = list(dict.fromkeys(noms.values()))
    a = m.ProcessusActivite(nom=p.nom, description=p.description, direction_id=p.direction_id, client_id=p.client_id,
                            created_by=current_user.id, statut_validation='brouillon', version_courante=0,
                            proprietaire_id=p.responsable_id, acteurs=acteurs or None, processus_source_id=p.id)
    m.db.session.add(a)
    m.db.session.flush()

    def y_pour(resp_id):
        if acteurs and resp_id in noms:
            return acteurs.index(noms[resp_id]) * HAUTEUR_COULOIR + 50
        return 50

    debut = m.ElementLogigramme(activite_id=a.id, type_element='debut', libelle='Début', position_x=20,
                                position_y=y_pour(etapes[0].responsable_id) if etapes else 50, client_id=p.client_id)
    m.db.session.add(debut)
    m.db.session.flush()
    correspondance = {}
    for i, e in enumerate(etapes, start=1):
        x = m.ElementLogigramme(activite_id=a.id, type_element=TYPES_ETAPE.get(e.type_etape or 'action', 'action'),
                                libelle=e.nom[:200], description=e.description, position_x=20 + i * 170,
                                position_y=y_pour(e.responsable_id), client_id=p.client_id)
        m.db.session.add(x)
        m.db.session.flush()
        correspondance[e.id] = x.id
    liens = m.LienProcessus.query.filter_by(processus_id=p.id).all()
    if liens:
        for l in liens:
            if l.etape_source_id in correspondance and l.etape_cible_id in correspondance:
                m.db.session.add(m.LienLogigramme(activite_id=a.id, element_source_id=correspondance[l.etape_source_id],
                                                  element_cible_id=correspondance[l.etape_cible_id], libelle=l.label or '',
                                                  client_id=p.client_id))
    else:
        suite = [correspondance[e.id] for e in etapes]
        for s_, c_ in zip(suite, suite[1:]):
            m.db.session.add(m.LienLogigramme(activite_id=a.id, element_source_id=s_, element_cible_id=c_, client_id=p.client_id))
    if etapes:
        m.db.session.add(m.LienLogigramme(activite_id=a.id, element_source_id=debut.id,
                                          element_cible_id=correspondance[etapes[0].id], client_id=p.client_id))
        if (etapes[-1].type_etape or '') != 'fin':
            fin = m.ElementLogigramme(activite_id=a.id, type_element='fin', libelle='Fin',
                                      position_x=20 + (len(etapes) + 1) * 170, position_y=y_pour(etapes[-1].responsable_id),
                                      client_id=p.client_id)
            m.db.session.add(fin)
            m.db.session.flush()
            m.db.session.add(m.LienLogigramme(activite_id=a.id, element_source_id=correspondance[etapes[-1].id],
                                              element_cible_id=fin.id, client_id=p.client_id))
    m.db.session.commit()
    journaliser('processus_converti_logigramme', {'processus_id': p.id, 'logigramme_id': a.id})
    flash(f"Processus converti : {len(etapes)} étape(s), {len(acteurs)} couloir(s). Vérifiez le dessin puis soumettez-le à validation.", 'success')
    return redirect(url_for('editer_logigramme', id=a.id))


# ---------------------------------------------------------------- modification => brouillon
def _avant_flush(session, _ctx, _inst):
    m = _m()
    touches = set()
    for obj in list(session.new) + list(session.dirty) + list(session.deleted):
        if isinstance(obj, (m.ElementLogigramme, m.LienLogigramme)) and getattr(obj, 'activite_id', None):
            if obj in session.dirty and not session.is_modified(obj, include_collections=False):
                continue
            touches.add(obj.activite_id)
        if isinstance(obj, (m.RisqueElementLogigramme, m.ControleElementLogigramme)):
            el = session.get(m.ElementLogigramme, obj.element_logigramme_id) if obj.element_logigramme_id else None
            if el is not None:
                touches.add(el.activite_id)
    for aid in touches:
        a = session.get(m.ProcessusActivite, aid)
        if a is not None and (a.statut_validation or 'brouillon') != 'brouillon':
            a.statut_validation = 'brouillon'       # la version validée reste consultable dans l'historique


def resume(a):
    """Petit résumé pour les listes et l'éditeur."""
    st = statut(a)
    retard = bool(a.date_revue_prevue and a.date_revue_prevue < date.today())
    return {'statut': st, 'libelle': STATUTS[st], 'version': a.version_courante or 0, 'revue': a.date_revue_prevue,
            'revue_en_retard': retard, 'acteurs': list(a.acteurs or [])}


def enregistrer(app):
    import models as m
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    app.register_blueprint(bp)
    if not getattr(m, '_egalyx_logigramme_flush', False):
        event.listen(Session, 'before_flush', _avant_flush)
        m._egalyx_logigramme_flush = True
    app.jinja_env.globals['logigramme_resume'] = resume
    app.jinja_env.globals['hauteur_couloir_logigramme'] = HAUTEUR_COULOIR
