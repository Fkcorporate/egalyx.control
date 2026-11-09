"""
egalyx/parametres_risque.py — paramétrage des risques par organisation.

- Seuils de cotation (Faible / Moyen / Élevé) et taux de réduction par niveau de maîtrise :
  branchés dans cotation.py via cotation.definir_fournisseur(). Sans paramétrage, la règle
  par défaut de cotation.py s'applique (4 / 10 / 16).
- Appétence au risque : score net maximal accepté, global et par catégorie.
- Listes LCB-FT (GAFI, secteurs sensibles) utilisées par le module Tiers.
"""
import threading
import time
from datetime import date

from flask import Blueprint, current_app, flash, g, has_app_context, has_request_context, redirect, render_template, request, url_for
from flask_login import current_user

import cotation
from egalyx import calculs
from egalyx.commun import entier, client_id_courant, decimal, journaliser, permission_requise

bp = Blueprint('parametres_risque', __name__, url_prefix='/parametres/risques')

# Cache par processus : {client_id: (instant, valeurs)} — 5 minutes, vidé à l'enregistrement.
_CACHE = {}
_VERROU = threading.Lock()
_DUREE_CACHE = 300


def _charger(client_id):
    """Lit les paramètres par une connexion séparée : utilisable pendant un flush SQLAlchemy
    (l'écouteur de cotation s'exécute pendant l'enregistrement d'une évaluation)."""
    from sqlalchemy import text
    from models import db
    with db.engine.connect() as cnx:
        ligne = cnx.execute(text(
            "SELECT seuil_faible, seuil_moyen, seuil_eleve, taux_maitrise FROM parametres_risque WHERE client_id = :c"),
            {'c': client_id}).mappings().first()
    if not ligne:
        return None
    taux_brut = ligne['taux_maitrise']
    if isinstance(taux_brut, str):
        import json
        try:
            taux_brut = json.loads(taux_brut)
        except ValueError:
            taux_brut = None
    taux = dict(cotation.TAUX_REDUCTION_MAITRISE)
    for k, v in (taux_brut or {}).items():
        try:
            taux[int(k)] = float(v)
        except (TypeError, ValueError):
            pass
    seuils = tuple(float(x) if x is not None else d for x, d in
                   zip((ligne['seuil_faible'], ligne['seuil_moyen'], ligne['seuil_eleve']), cotation.SEUILS))
    if calculs.valider_seuils(*seuils):
        seuils = cotation.SEUILS
    return {'seuils': seuils, 'taux': taux}


def parametres_client(client_id):
    if not client_id:
        return None
    maintenant = time.time()
    with _VERROU:
        en_cache = _CACHE.get(client_id)
        if en_cache and maintenant - en_cache[0] < _DUREE_CACHE:
            return en_cache[1]
    try:
        valeurs = _charger(client_id)
    except Exception as e:   # table absente avant migration, base indisponible…
        current_app.logger.debug("Paramètres de risque indisponibles (%s) : %s", client_id, e)
        valeurs = None
    with _VERROU:
        _CACHE[client_id] = (maintenant, valeurs)
    return valeurs


def vider_cache(client_id=None):
    with _VERROU:
        if client_id is None:
            _CACHE.clear()
        else:
            _CACHE.pop(client_id, None)


def _client_contexte():
    """Organisation concernée par le calcul en cours : fixée explicitement (recalcul) ou utilisateur connecté."""
    if has_app_context() and getattr(g, 'cotation_client_id', None):
        return g.cotation_client_id
    if has_request_context():
        try:
            if current_user.is_authenticated:
                return client_id_courant()
        except Exception:
            return None
    return None


def fournisseur():
    if not has_app_context():
        return None
    return parametres_client(_client_contexte())


# --------------------------------------------------------------------- appétence
def objet_parametres(client_id):
    from models import ParametresRisque
    return ParametresRisque.query.filter_by(client_id=client_id).first()


def etat_appetence(score_net, categorie, p):
    """None si pas d'appétence définie ; sinon {seuil, depasse, ecart}."""
    if p is None or score_net is None:
        return None
    seuil = calculs.seuil_appetence(categorie, p.appetence_score_net, p.appetence_par_categorie)
    if seuil is None:
        return None
    return {'seuil': seuil, 'depasse': float(score_net) > seuil, 'ecart': round(float(score_net) - seuil, 1)}


def appetence_risque(risque):
    """Pour la fiche risque : état d'appétence de la dernière évaluation (ou None)."""
    try:
        from models import EvaluationRisque
        p = objet_parametres(risque.client_id) if risque is not None and risque.client_id else None
        if p is None:
            return None
        ev = (EvaluationRisque.query.filter_by(risque_id=risque.id)
              .order_by(EvaluationRisque.created_at.desc()).first())
        if ev is None:
            return None
        c = cotation.depuis_evaluation(ev)
        if not c or not c.get('evalue'):
            return None
        return etat_appetence(c['score_net'], risque.categorie, p)
    except Exception as e:
        current_app.logger.warning("Appétence non calculée : %s", e)
        return None


def risques_hors_appetence(client_id, top_risques_complets):
    """top_risques_complets : liste [{risque, cot}] (tableau de bord stratégique)."""
    p = objet_parametres(client_id)
    if p is None or (p.appetence_score_net is None and not p.appetence_par_categorie):
        return None
    hors = []
    for t in top_risques_complets:
        e = etat_appetence(t['cot'].get('score_net'), getattr(t['risque'], 'categorie', None), p)
        if e and e['depasse']:
            hors.append(dict(t, appetence=e))
    hors.sort(key=lambda x: x['appetence']['ecart'], reverse=True)
    return {'nombre': len(hors), 'risques': hors[:10], 'seuil_global': p.appetence_score_net}


# --------------------------------------------------------------------- page
def _lignes(texte):
    return [l.strip() for l in (texte or '').replace(';', '\n').splitlines() if l.strip()]


@bp.route('/', methods=['GET', 'POST'])
@permission_requise('can_manage_settings')
def page():
    from models import db, ParametresRisque, Risque, marquer_json_modifie
    cid = client_id_courant()
    p = objet_parametres(cid)
    categories = sorted({(r[0] or '').strip() for r in db.session.query(Risque.categorie)
                         .filter(Risque.client_id == cid, Risque.is_archived == False).distinct()  # noqa: E712
                         if r[0] and r[0].strip()})

    if request.method == 'POST':
        action = request.form.get('action', 'enregistrer')
        if p is None:
            p = ParametresRisque(client_id=cid)
            db.session.add(p)
        if action == 'listes_gafi':
            p.pays_liste_noire = list(calculs.GAFI_LISTE_NOIRE_2026_06)
            p.pays_liste_grise = list(calculs.GAFI_LISTE_GRISE_2026_06)
            p.listes_gafi_maj_le = date(2026, 6, 19)
            marquer_json_modifie(p, 'pays_liste_noire'); marquer_json_modifie(p, 'pays_liste_grise')
            p.updated_by = current_user.id
            db.session.commit()
            flash('Listes du GAFI (19 juin 2026) rétablies. Vérifiez les mises à jour publiées depuis sur fatf-gafi.org.', 'success')
            return redirect(url_for('.page'))

        f, m, e = (decimal(request.form.get(k)) for k in ('seuil_faible', 'seuil_moyen', 'seuil_eleve'))
        erreurs = calculs.valider_seuils(f, m, e)
        taux = {}
        for n in range(1, 6):
            v = decimal(request.form.get(f'taux_{n}'))
            if v is None or not 0 <= v <= 90:
                erreurs.append(f'Taux du niveau {n} : nombre entre 0 et 90 %.')
            else:
                taux[str(n)] = round(v / 100.0, 4)
        if taux and [taux[str(n)] for n in range(1, 6)] != sorted(taux[str(n)] for n in range(1, 6)):
            erreurs.append('Les taux doivent croître avec le niveau de maîtrise.')
        appetence = decimal(request.form.get('appetence_score_net'))
        if appetence is not None and not 1 <= appetence <= 25:
            erreurs.append("L'appétence globale doit être comprise entre 1 et 25.")
        par_cat = {}
        for i, cat in enumerate(categories):
            v = decimal(request.form.get(f'appetence_cat_{i}'))
            if v is not None:
                if 1 <= v <= 25:
                    par_cat[cat] = v
                else:
                    erreurs.append(f'Appétence « {cat} » : entre 1 et 25.')
        if erreurs:
            for x in erreurs:
                flash(x, 'danger')
            db.session.rollback()
            return render_template('egalyx/parametres_risque.html', p=p, form=request.form,
                                   categories=categories, defaut=_defauts(), en_erreur=True)

        anciens = (p.seuil_faible, p.seuil_moyen, p.seuil_eleve, p.taux_maitrise)
        p.seuil_faible, p.seuil_moyen, p.seuil_eleve = f, m, e
        p.taux_maitrise = taux
        p.appetence_score_net = appetence
        p.appetence_par_categorie = par_cat
        p.appetence_declaration = (request.form.get('appetence_declaration') or '').strip() or None
        p.pays_liste_noire = _lignes(request.form.get('pays_liste_noire'))
        p.pays_liste_grise = _lignes(request.form.get('pays_liste_grise'))
        p.secteurs_sensibles = _lignes(request.form.get('secteurs_sensibles'))
        p.seuil_montant_lcb = decimal(request.form.get('seuil_montant_lcb'))
        for champ in ('taux_maitrise', 'appetence_par_categorie', 'pays_liste_noire', 'pays_liste_grise', 'secteurs_sensibles'):
            marquer_json_modifie(p, champ)
        p.updated_by = current_user.id
        journaliser('parametres_risque_modifies', {'seuils': [f, m, e], 'taux': taux, 'appetence': appetence})
        db.session.commit()
        vider_cache(cid)

        if anciens != (f, m, e, taux):
            recalcul = current_app.extensions.get('egalyx_recalcul_cotations')
            if recalcul:
                g.cotation_client_id = cid
                try:
                    lues, modifiees = recalcul(client_id=cid)
                    flash(f'Paramètres enregistrés. {lues} évaluation(s) recalculée(s), {modifiees} modifiée(s).', 'success')
                finally:
                    g.cotation_client_id = None
            else:
                flash('Paramètres enregistrés.', 'success')
        else:
            flash('Paramètres enregistrés.', 'success')
        return redirect(url_for('.page'))

    return render_template('egalyx/parametres_risque.html', p=p, form=None, categories=categories,
                           defaut=_defauts(), en_erreur=False)


def valideurs_possibles(cid):
    """Utilisateurs actifs de l'organisation pouvant valider les évaluations des opérateurs
    (un opérateur « valideur » est possible : il valide depuis l'espace opérationnel)."""
    from models import User
    return User.query.filter_by(client_id=cid, is_active=True).order_by(User.username).all()


def peut_regler_valideur(u=None):
    """Qui peut désigner le valideur : super admin, administrateur de l'organisation, ou gestionnaire
    (paramètres, validation ou confirmation des évaluations de risques)."""
    from egalyx.commun import a_permission, est_admin_client
    u = u or current_user
    if getattr(u, 'is_operateur', False) and not est_admin_client(u):
        return False
    return est_admin_client(u) or a_permission('can_manage_settings', 'can_validate_risks', 'can_confirm_evaluations', u=u)


def contexte_valideur(cid=None):
    """Données de la carte « valideur des opérateurs » (incluse dans plusieurs pages)."""
    cid = cid or client_id_courant()
    if not cid or not peut_regler_valideur():
        return None
    from models import Cartographie
    v = valideur_organisation(cid)
    q = Cartographie.query.filter_by(client_id=cid)
    if hasattr(Cartographie, 'is_archived'):
        q = q.filter(Cartographie.is_archived == False)  # noqa: E712
    return {'client_id': cid, 'valideurs': valideurs_possibles(cid), 'actuel': v,
            'actuel_id': v.id if v else None, 'cartographies': q.order_by(Cartographie.nom).all()}


@bp.route('/valideur-operateurs', methods=['GET', 'POST'])
def valideur_page():
    """Désignation du valideur des évaluations faites par les opérateurs (page autonome, accessible
    à l'admin, au super admin et aux gestionnaires des risques)."""
    from models import db, ParametresRisque
    if not getattr(current_user, 'is_authenticated', False):
        return redirect(url_for('login', next=request.full_path))
    cid = client_id_courant()
    if not cid or not peut_regler_valideur():
        flash("Vous n'avez pas la permission de désigner le valideur des opérateurs.", 'warning')
        return redirect(url_for('dashboard'))
    suite = request.values.get('suite') or ''
    if not suite.startswith('/') or suite.startswith('//'):
        suite = url_for('.valideur_page', client_id=cid if request.args.get('client_id') else None)
    if request.method == 'POST':
        from models import Cartographie
        ids_ok = {u.id for u in valideurs_possibles(cid)}
        messages = []
        if 'valideur_evaluations_operateurs_id' in request.form:
            p = objet_parametres(cid)
            if p is None:
                p = ParametresRisque(client_id=cid)
                db.session.add(p)
            vid = entier(request.form.get('valideur_evaluations_operateurs_id'))
            ancien = p.valideur_evaluations_operateurs_id
            p.valideur_evaluations_operateurs_id = vid if vid in ids_ok else None
            p.updated_by = current_user.id
            if ancien != p.valideur_evaluations_operateurs_id:
                journaliser('valideur_operateurs_modifie', {'avant': ancien, 'apres': p.valideur_evaluations_operateurs_id,
                                                            'client_id': cid})
                messages.append('organisation')
        for cle in request.form:
            if not cle.startswith('carto_'):
                continue
            carto = db.session.get(Cartographie, entier(cle[6:]) or 0)
            if carto is None or carto.client_id != cid:
                continue
            vid = entier(request.form.get(cle))
            nouveau = vid if vid in ids_ok else None
            if carto.valideur_operateurs_id != nouveau:
                journaliser('valideur_operateurs_cartographie', {'cartographie_id': carto.id,
                                                                 'avant': carto.valideur_operateurs_id, 'apres': nouveau})
                carto.valideur_operateurs_id = nouveau
                messages.append(carto.nom)
        db.session.commit()
        vider_cache(cid)
        flash('Valideurs enregistrés.' if messages else 'Aucun changement.', 'success' if messages else 'info')
        return redirect(suite)
    return render_template('egalyx/valideur_operateurs.html', ctx=contexte_valideur(cid), suite=suite)


def _utilisateur_valide(uid, cid):
    if not uid:
        return None
    from models import db, User
    u = db.session.get(User, uid)
    return u if u is not None and u.is_active and u.client_id == cid else None


def valideur_organisation(cid):
    """Valideur par défaut de l'organisation (Paramètres > Risques), ou None."""
    p = objet_parametres(cid) if cid else None
    return _utilisateur_valide(getattr(p, 'valideur_evaluations_operateurs_id', None) if p else None, cid)


def valideur_operateurs(cid, cartographie_id=None):
    """Valideur des évaluations faites par les opérateurs : celui de la cartographie s'il est désigné,
    sinon celui de l'organisation, sinon None (fonctionnement habituel : l'opérateur valide lui-même)."""
    if not cid:
        return None
    if cartographie_id:
        from models import db, Cartographie
        c = db.session.get(Cartographie, cartographie_id)
        if c is not None and c.client_id == cid:
            v = _utilisateur_valide(getattr(c, 'valideur_operateurs_id', None), cid)
            if v is not None:
                return v
    return valideur_organisation(cid)


def valideur_de_l_evaluation(e):
    """Valideur applicable à une évaluation (selon la cartographie de son risque)."""
    carto = getattr(e, 'cartographie_id', None) or (e.risque.cartographie_id if getattr(e, 'risque', None) else None)
    return valideur_operateurs(getattr(e, 'client_id', None) or (e.risque.client_id if getattr(e, 'risque', None) else None), carto)


def est_valideur_operateurs(u=None):
    """Vrai si l'utilisateur est valideur des opérateurs pour l'organisation ou pour au moins une cartographie."""
    u = u or current_user
    cid = getattr(u, 'client_id', None)
    if not getattr(u, 'is_authenticated', False) or not cid:
        return False
    v = valideur_organisation(cid)
    if v is not None and v.id == u.id:
        return True
    from models import Cartographie
    return Cartographie.query.filter_by(client_id=cid, valideur_operateurs_id=u.id).first() is not None


def _defauts():
    return {'seuils': cotation.SEUILS, 'taux': cotation.TAUX_REDUCTION_MAITRISE,
            'noire': calculs.GAFI_LISTE_NOIRE_2026_06, 'grise': calculs.GAFI_LISTE_GRISE_2026_06,
            'secteurs': calculs.SECTEURS_SENSIBLES}


def enregistrer(app, recalculer=None):
    app.register_blueprint(bp)
    cotation.definir_fournisseur(fournisseur)
    if recalculer:
        app.extensions['egalyx_recalcul_cotations'] = recalculer
    app.jinja_env.globals['appetence_risque'] = appetence_risque
    app.jinja_env.globals['contexte_valideur_operateurs'] = contexte_valideur
    app.jinja_env.globals['valideur_operateurs'] = valideur_operateurs
    app.jinja_env.globals['est_valideur_operateurs'] = est_valideur_operateurs
    app.jinja_env.globals['peut_regler_valideur_operateurs'] = peut_regler_valideur
