"""
egalyx/c2n_echantillon.py — l'échantillon d'un contrôle N2, élément par élément.

Page « Échantillon » d'une planification N2 (/c2n/planification/<id>/echantillon) :
  - tirage aléatoire tracé : on colle la population (une référence par ligne, ou un export), on indique la taille
    (proposée selon la fréquence du contrôle) ; le tirage est reproductible (graine conservée avec la taille de la
    population, la date et l'auteur) — c'est ce qu'un auditeur demande pour vérifier qu'on n'a pas choisi les dossiers ;
  - ou ajout manuel d'éléments ;
  - pour chaque élément : résultat (conforme / anomalie), motif et criticité de l'anomalie, commentaire, preuve jointe ;
  - les totaux de l'exécution (contrôlés, conformes, anomalies, taux) sont calculés depuis l'échantillon, et chaque
    élément en anomalie devient une anomalie détectée de l'exécution (même circuit qu'avant : validation, NC) ;
  - export CSV de l'échantillon (piste d'audit).
Modifiable tant que la planification est « à faire » ou « en cours », par qui peut l'exécuter ; en lecture ensuite.
"""
import csv
import io
import os
import random
import re
import secrets
import uuid
from datetime import datetime

from flask import (Blueprint, Response, abort, current_app, flash, redirect, render_template, request, send_file,
                   url_for)
from flask_login import current_user

bp = Blueprint('c2n_echantillon', __name__)

RESULTATS = [('a_tester', 'À tester'), ('conforme', 'Conforme'), ('anomalie', 'Anomalie')]
CRITICITES = [('mineur', 'Mineure'), ('majeur', 'Majeure'), ('critique', 'Critique')]
EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.webp', '.xlsx', '.xls', '.docx', '.doc', '.csv', '.txt', '.msg', '.eml', '.zip'}
TAILLE_PREUVE = 15 * 1024 * 1024
POPULATION_MAX = 100000


def _m():
    import models
    return models


def _planification(pid):
    m = _m()
    pl = m.db.session.get(m.PlanificationControle, pid)
    if pl is None:
        abort(404)
    if current_user.role != 'super_admin' and pl.client_id != current_user.client_id:
        abort(404)
    return pl


def peut_modifier(pl):
    try:
        return pl.statut in ('a_faire', 'en_cours') and current_user.peut_executer_planification(pl)
    except Exception:  # noqa: BLE001
        return False


def peut_voir(pl):
    if current_user.role == 'super_admin' or peut_modifier(pl):
        return True
    try:
        return bool(current_user.has_permission('can_view_controle_interne_n2')
                    or current_user.has_permission('can_manage_controle_interne_n2')
                    or pl.controleur_id == current_user.id or pl.validateur_requis_id == current_user.id)
    except Exception:  # noqa: BLE001
        return False


def _execution(pl, creer=False):
    m = _m()
    ex = pl.execution
    if ex is None and creer:
        ex = m.ExecutionControle(volume_previsionnel=pl.taille_echantillon or 0, volume_controle=0, nb_conformes=0,
                                 nb_anomalies=0, execute_par_id=current_user.id, client_id=pl.client_id,
                                 date_execution=datetime.utcnow())
        m.db.session.add(ex)
        m.db.session.flush()
        pl.execution_id = ex.id
    return ex


def elements(ex):
    if ex is None:
        return []
    m = _m()
    return m.ElementEchantillonN2.query.filter_by(execution_id=ex.id).order_by(m.ElementEchantillonN2.numero,
                                                                              m.ElementEchantillonN2.id).all()


def synchroniser(ex, pl):
    """Totaux de l'exécution et anomalies détectées, depuis l'échantillon. Ne fait rien s'il n'y a pas d'échantillon."""
    m = _m()
    els = elements(ex)
    if not els:
        return False
    testes = [e for e in els if e.resultat in ('conforme', 'anomalie')]
    anomalies = [e for e in els if e.resultat == 'anomalie']
    for e in els:
        a = m.db.session.get(m.AnomalieDetectee, e.anomalie_id) if e.anomalie_id else None
        if e.resultat == 'anomalie':
            motif = (e.motif or 'Anomalie relevée sur l\'échantillon').strip()
            if a is None:
                a = m.AnomalieDetectee(execution_id=ex.id, motif=motif, description=e.commentaire,
                                       element_concerne=e.reference[:200], criticite=e.criticite or 'mineur',
                                       nombre_ecarts=1, statut='a_traiter', client_id=pl.client_id,
                                       created_by=current_user.id)
                m.db.session.add(a)
                m.db.session.flush()
                e.anomalie_id = a.id
            elif a.statut in ('a_traiter', 'confirmee'):
                a.motif, a.description = motif, e.commentaire
                a.element_concerne, a.criticite = e.reference[:200], e.criticite or 'mineur'
        elif a is not None:
            if a.statut == 'a_traiter' and not a.non_conformite_id:
                m.db.session.delete(a)
            e.anomalie_id = None
    ex.volume_controle = len(testes)
    ex.nb_conformes = len(testes) - len(anomalies)
    ex.nb_anomalies = len(anomalies)
    ex.volume_previsionnel = max(ex.volume_previsionnel or 0, len(els))
    try:
        ex.calculer_taux()
    except Exception:  # noqa: BLE001
        ex.taux_conformite = round(100.0 * ex.nb_conformes / len(testes), 1) if testes else None
    return True


def _dossier_preuves(cid):
    d = os.path.join(current_app.instance_path, 'preuves_c2n', str(int(cid or 0)))
    os.makedirs(d, exist_ok=True)
    return d


def _enregistrer_preuve(f, e, cid):
    nom = os.path.basename(f.filename or '')
    ext = os.path.splitext(nom.lower())[1]
    if ext not in EXTENSIONS:
        raise ValueError(f'« {nom} » : type de fichier non accepté.')
    contenu = f.read(TAILLE_PREUVE + 1)
    if len(contenu) > TAILLE_PREUVE:
        raise ValueError(f'« {nom} » : 15 Mo au maximum.')
    if e.preuve_fichier:
        try:
            os.remove(os.path.join(_dossier_preuves(cid), e.preuve_fichier))
        except OSError:
            pass
    fichier = f'{uuid.uuid4().hex}{ext}'
    with open(os.path.join(_dossier_preuves(cid), fichier), 'wb') as sortie:
        sortie.write(contenu)
    e.preuve_fichier, e.preuve_nom = fichier, nom[:200]


def _references(texte):
    """Une référence par ligne (ou séparées par ; / tabulation) ; doublons retirés, ordre conservé."""
    vus, refs = set(), []
    for brut in re.split(r'[\r\n;\t]+', texte or ''):
        r = brut.strip().strip(',').strip()
        if r and r.lower() not in vus:
            vus.add(r.lower())
            refs.append(r[:200])
    return refs


@bp.route('/c2n/planification/<int:pid>/echantillon', methods=['GET', 'POST'])
def page(pid):
    from egalyx.commun import journaliser
    from egalyx.c2n_cartographie import echantillon_recommande
    m = _m()
    if not getattr(current_user, 'is_authenticated', False):
        abort(401)
    pl = _planification(pid)
    if not peut_voir(pl):
        abort(403)
    modifiable = peut_modifier(pl)
    retour = url_for('.page', pid=pid)
    if request.method == 'POST':
        if not modifiable:
            flash('Échantillon en lecture seule : la planification n\'est plus à faire ni en cours, ou vous ne l\'exécutez pas.', 'warning')
            return redirect(retour)
        action = request.form.get('action')
        ex = _execution(pl, creer=True)
        try:
            if action == 'tirer':
                population = _references(request.form.get('population'))[:POPULATION_MAX]
                try:
                    taille = int(request.form.get('taille') or 0)
                except ValueError:
                    taille = 0
                if len(population) < 1 or taille < 1:
                    flash('Collez la population (une référence par ligne) et indiquez la taille de l\'échantillon.', 'warning')
                    return redirect(retour)
                if any(e.resultat != 'a_tester' for e in elements(ex)):
                    flash('Des éléments ont déjà été testés : le tirage remplacerait l\'échantillon. Ajoutez des éléments '
                          'à la main, ou remettez-les « à tester » avant de tirer à nouveau.', 'warning')
                    return redirect(retour)
                taille = min(taille, len(population))
                graine = secrets.randbits(32)
                tires = random.Random(graine).sample(population, taille)
                for e in elements(ex):
                    m.db.session.delete(e)
                for i, ref in enumerate(tires, 1):
                    m.db.session.add(m.ElementEchantillonN2(execution_id=ex.id, client_id=pl.client_id, numero=i,
                                                            reference=ref, resultat='a_tester'))
                ex.tirage_echantillon = {'population': len(population), 'taille': taille, 'graine': graine,
                                         'le': datetime.utcnow().isoformat(timespec='seconds'),
                                         'par': current_user.username, 'methode': 'aléatoire simple sans remise'}
                if not pl.taille_echantillon:
                    pl.taille_echantillon = taille
                journaliser('c2n_echantillon_tirage', {'planification': pl.reference, 'population': len(population),
                                                       'taille': taille, 'graine': graine}, client_id=pl.client_id)
                m.db.session.flush()
                synchroniser(ex, pl)
                m.db.session.commit()
                flash(f'{taille} élément(s) tiré(s) au hasard parmi {len(population)} (graine {graine}, tirage reproductible).', 'success')
                return redirect(retour)
            if action == 'ajouter':
                refs = _references(request.form.get('references'))
                if not refs:
                    flash('Indiquez au moins une référence.', 'warning')
                    return redirect(retour)
                n = max([e.numero or 0 for e in elements(ex)] or [0])
                existantes = {e.reference.lower() for e in elements(ex)}
                ajout = 0
                for ref in refs:
                    if ref.lower() in existantes:
                        continue
                    n += 1
                    ajout += 1
                    m.db.session.add(m.ElementEchantillonN2(execution_id=ex.id, client_id=pl.client_id, numero=n,
                                                            reference=ref, resultat='a_tester'))
                m.db.session.flush()
                synchroniser(ex, pl)
                m.db.session.commit()
                flash(f'{ajout} élément(s) ajouté(s).', 'success')
                return redirect(retour)
            if action == 'enregistrer':
                erreurs = []
                for e in elements(ex):
                    if request.form.get(f'suppr_{e.id}') == '1':
                        if e.preuve_fichier:
                            try:
                                os.remove(os.path.join(_dossier_preuves(pl.client_id), e.preuve_fichier))
                            except OSError:
                                pass
                        if e.anomalie_id:
                            a = m.db.session.get(m.AnomalieDetectee, e.anomalie_id)
                            if a is not None and a.statut == 'a_traiter' and not a.non_conformite_id:
                                m.db.session.delete(a)
                        m.db.session.delete(e)
                        continue
                    res = request.form.get(f'res_{e.id}')
                    if res in dict(RESULTATS):
                        if res != e.resultat and res != 'a_tester':
                            e.teste_par_id, e.teste_le = current_user.id, datetime.utcnow()
                        e.resultat = res
                    e.motif = (request.form.get(f'motif_{e.id}') or '').strip()[:300] or None
                    crit = request.form.get(f'crit_{e.id}')
                    e.criticite = crit if crit in dict(CRITICITES) else ('mineur' if e.resultat == 'anomalie' else None)
                    e.commentaire = (request.form.get(f'com_{e.id}') or '').strip() or None
                    if e.resultat == 'anomalie' and not e.motif:
                        erreurs.append(f'{e.reference} : indiquez le motif de l\'anomalie.')
                    f = request.files.get(f'preuve_{e.id}')
                    if f and f.filename:
                        try:
                            _enregistrer_preuve(f, e, pl.client_id)
                        except ValueError as err:
                            erreurs.append(str(err))
                m.db.session.flush()
                synchroniser(ex, pl)
                journaliser('c2n_echantillon_saisie', {'planification': pl.reference}, client_id=pl.client_id)
                m.db.session.commit()
                for err in erreurs[:5]:
                    flash(err, 'warning')
                flash('Échantillon enregistré : totaux de l\'exécution mis à jour.', 'success')
                return redirect(retour)
        except Exception:
            m.db.session.rollback()
            raise
        return redirect(retour)
    ex = _execution(pl)
    els = elements(ex)
    taille, fourchette, freq = echantillon_recommande(pl.referentiel)
    stats = {'total': len(els), 'testes': sum(1 for e in els if e.resultat != 'a_tester'),
             'anomalies': sum(1 for e in els if e.resultat == 'anomalie'),
             'preuves': sum(1 for e in els if e.preuve_fichier)}
    return render_template('egalyx/c2n_echantillon.html', pl=pl, ex=ex, elements=els, modifiable=modifiable,
                           resultats=RESULTATS, criticites=CRITICITES, stats=stats,
                           taille_proposee=pl.taille_echantillon or taille, fourchette=fourchette, frequence=freq)


@bp.route('/c2n/echantillon/preuve/<int:eid>')
def preuve(eid):
    m = _m()
    if not getattr(current_user, 'is_authenticated', False):
        abort(404)
    e = m.db.session.get(m.ElementEchantillonN2, eid)
    if e is None or not e.preuve_fichier:
        abort(404)
    ex = m.db.session.get(m.ExecutionControle, e.execution_id)
    pl = m.PlanificationControle.query.filter_by(execution_id=ex.id).first() if ex else None
    if pl is None or (current_user.role != 'super_admin' and pl.client_id != current_user.client_id) or not peut_voir(pl):
        abort(404)
    chemin = os.path.join(_dossier_preuves(pl.client_id), os.path.basename(e.preuve_fichier))
    if not os.path.exists(chemin):
        abort(404)
    return send_file(chemin, as_attachment=True, download_name=e.preuve_nom or e.preuve_fichier)


@bp.route('/c2n/planification/<int:pid>/echantillon.csv')
def export(pid):
    if not getattr(current_user, 'is_authenticated', False):
        abort(401)
    pl = _planification(pid)
    if not peut_voir(pl):
        abort(403)
    m = _m()
    sortie = io.StringIO()
    w = csv.writer(sortie, delimiter=';')
    t = (pl.execution.tirage_echantillon or {}) if pl.execution is not None else {}
    w.writerow([f'Contrôle N2 {pl.reference}', pl.referentiel.code_controle if pl.referentiel else ''])
    if t:
        w.writerow([f"Tirage aléatoire : {t.get('taille')} sur {t.get('population')}, graine {t.get('graine')}, "
                    f"le {t.get('le')} par {t.get('par')}"])
    w.writerow(['N°', 'Référence', 'Résultat', 'Motif', 'Criticité', 'Commentaire', 'Preuve', 'Testé par', 'Testé le'])
    noms = {}
    for e in elements(pl.execution):
        if e.teste_par_id and e.teste_par_id not in noms:
            u = m.db.session.get(m.User, e.teste_par_id)
            noms[e.teste_par_id] = u.username if u else ''
        w.writerow([e.numero, e.reference, dict(RESULTATS).get(e.resultat, e.resultat), e.motif or '',
                    dict(CRITICITES).get(e.criticite, '') if e.resultat == 'anomalie' else '', e.commentaire or '',
                    e.preuve_nom or '', noms.get(e.teste_par_id, ''),
                    e.teste_le.strftime('%d/%m/%Y %H:%M') if e.teste_le else ''])
    return Response('﻿' + sortie.getvalue(), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename=echantillon_{pl.reference}.csv'})


def resume(pl):
    """Pour l'exécution, le détail et les rapports."""
    ex = pl.execution
    els = elements(ex)
    if not els:
        return None
    return {'total': len(els), 'testes': sum(1 for e in els if e.resultat != 'a_tester'),
            'anomalies': sum(1 for e in els if e.resultat == 'anomalie'),
            'preuves': sum(1 for e in els if e.preuve_fichier),
            'tirage': (ex.tirage_echantillon or {}) if ex is not None else {}}


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    app.register_blueprint(bp)
    exempter_controle_ancien(app, {'c2n_echantillon.page', 'c2n_echantillon.preuve', 'c2n_echantillon.export'})
    app.jinja_env.globals['c2n_echantillon_resume'] = resume
