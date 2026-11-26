"""
egalyx/analyse_sources.py — analyse de données, lot 3 : sources de données et analyses programmées (audit continu).

1. Sources (/analyse-donnees/sources) : l'administrateur de l'organisation connecte ses systèmes (bases de données en
   lecture seule, SFTP, lien https, SharePoint / OneDrive, Google Drive, Odoo, Business Central, Xero, QuickBooks,
   Zoho Books — egalyx/analyse_connecteurs.py). « Tester la connexion » ne lit qu'un minimum de données.
2. Dans une analyse de mission : chaque type de données peut être lu « depuis une source » pour une période ; la suite
   est celle de l'import manuel (correspondance, qualité, empreinte, tests).
3. Analyses programmées (/analyse-donnees/programmes) : source + tests + période glissante + fréquence. À chaque
   exécution (automatique toutes les 15 minutes pour celles arrivées à échéance, ou « Exécuter maintenant ») :
     - les données de la période sont lues et contrôlées, les tests lancés, l'historique conservé avec les empreintes ;
     - contrôle de 2e niveau : les NOUVELLES anomalies deviennent des éléments « en anomalie » de la planification N2
       de la période (référentiel choisi), à examiner par le contrôleur puis à soumettre au validateur : même circuit
       qu'un contrôle manuel (anomalies détectées, non-conformités à la validation) ;
     - KRI : le nombre d'anomalies, le montant ou le taux d'un test devient une mesure du KRI choisi (alertes de seuil
       existantes) ;
     - le responsable est prévenu (notification) des nouvelles anomalies et des erreurs.
Droits : module « Analyse de données » activé par le super admin ; sources : administrateurs de l'organisation ;
analyses programmées : administrateurs, gestionnaires du contrôle de 2e niveau ou de l'audit.
"""
import logging
import os
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from egalyx import analyse_connecteurs as ac
from egalyx import analyse_donnees as ad
from egalyx import analyse_moteur as am
from egalyx.commun import client_id_courant, est_super_admin, journaliser, nom_personne

journal = logging.getLogger('egalyx.analyse_sources')
bp = Blueprint('analyse_sources', __name__, url_prefix='/analyse-donnees')
FREQUENCES = [('quotidienne', 'Chaque jour', 1), ('hebdomadaire', 'Chaque semaine', 7), ('mensuelle', 'Chaque mois', 30)]
MESURES = [('nb', 'Nombre de lignes en anomalie'), ('cas', 'Nombre de cas'), ('montant', 'Montant concerné'), ('taux', 'Taux d’anomalie (%)')]
ELEMENTS_MAX = 300
CRITICITE_N2 = {'eleve': 'majeur', 'moyen': 'mineur', 'faible': 'mineur'}


def _m():
    import models
    return models


# ====================================================================== droits
def _cid():
    cid = client_id_courant()
    if not cid:
        abort(404)
    return cid


def peut_gerer_sources(u=None, cid=None):
    u = u or current_user
    if not getattr(u, 'is_authenticated', False):
        return False
    cid = cid or getattr(u, 'client_id', None) or client_id_courant()
    if est_super_admin(u):
        return bool(cid)
    return ad.module_actif(cid) and ad._est_admin_org(u)


def peut_programmer(u=None, cid=None):
    u = u or current_user
    if not getattr(u, 'is_authenticated', False):
        return False
    cid = cid or getattr(u, 'client_id', None) or client_id_courant()
    if est_super_admin(u):
        return bool(cid)
    if not ad.module_actif(cid):
        return False
    return (ad._est_admin_org(u) or u.has_permission('can_manage_controle_interne_n2') or u.has_permission('can_manage_audit')
            or u.has_permission(ad.PERMISSION))


def _source(sid, cid):
    m = _m()
    s = m.db.session.get(m.SourceAnalyse, sid)
    if s is None or s.client_id != cid:
        abort(404)
    return s


def _programme(pid, cid):
    m = _m()
    p = m.db.session.get(m.AnalyseProgrammee, pid)
    if p is None or p.client_id != cid:
        abort(404)
    return p


# ====================================================================== secrets
def secrets_de(source):
    from models import dechiffrer_secret
    res = {}
    for k, v in (source.secrets or {}).items():
        try:
            res[k] = dechiffrer_secret(v)
        except Exception:  # noqa: BLE001
            res[k] = None
    return {k: v for k, v in res.items() if v}


def _maj_secrets(source, nouveaux):
    """Jetons renouvelés par l'éditeur (Xero, QuickBooks) et empreinte SFTP vue au premier contact."""
    from models import chiffrer_secret
    if not nouveaux:
        return
    p = dict(source.parametres or {})
    if nouveaux.get('_empreinte_hote') and not p.get('empreinte_hote'):
        p['empreinte_hote'] = nouveaux['_empreinte_hote']
        source.parametres = p
        ad._json(source, 'parametres')
    sec = {k: v for k, v in nouveaux.items() if not k.startswith('_')}
    if sec:
        s = dict(source.secrets or {})
        s.update({k: chiffrer_secret(v) for k, v in sec.items()})
        source.secrets = s
        ad._json(source, 'secrets')


def extraire(source, jeu, debut=None, fin=None):
    ext = ac.extraire(source.connecteur, source.parametres or {}, secrets_de(source), jeu, debut, fin)
    if ext.secrets_a_jour:
        _maj_secrets(source, ext.secrets_a_jour)
        _m().db.session.commit()            # jeton renouvelé : à garder même si la suite échoue (l'ancien ne vaut plus)
    return ext


def sources_pour(cid, jeu=None):
    m = _m()
    res = m.SourceAnalyse.query.filter_by(client_id=cid, actif=True).order_by(m.SourceAnalyse.nom).all()
    return [s for s in res if s.connecteur in ac.PAR_CODE and (jeu is None or jeu in ac.PAR_CODE[s.connecteur]['jeux'])]


# ====================================================================== 1. sources
@bp.route('/sources')
@login_required
def sources():
    cid = _cid()
    if not peut_gerer_sources(cid=cid):
        abort(403)
    m = _m()
    liste = m.SourceAnalyse.query.filter_by(client_id=cid).order_by(m.SourceAnalyse.nom).all()
    return render_template('egalyx/analyse_sources.html', liste=liste, CONNECTEURS=ac.CONNECTEURS, PAR_CODE=ac.PAR_CODE, FAMILLES=ac.FAMILLES,
                           JEUX=am.JEUX, prive=ac.reseau_prive_autorise())


def _formulaire(source, connecteur):
    c = ac.PAR_CODE[connecteur]
    secrets = set((source.secrets or {}).keys()) if source else set()
    return render_template('egalyx/analyse_source_form.html', s=source, c=c, p=(source.parametres if source else {}) or {}, secrets=secrets,
                           JEUX=am.JEUX, ORDRE=[j for j in am.ORDRE_JEUX if j in c['jeux']],
                           modeles=ac.MODELES_REQUETES.get(c.get('modeles') or '', {}), vues=ac.MODELES_REQUETES['vues'])


@bp.route('/sources/nouvelle', methods=['GET', 'POST'])
@bp.route('/sources/<int:sid>/modifier', methods=['GET', 'POST'])
@login_required
def source_form(sid=None):
    cid = _cid()
    if not peut_gerer_sources(cid=cid):
        abort(403)
    m = _m()
    s = _source(sid, cid) if sid else None
    connecteur = s.connecteur if s else (request.values.get('connecteur') or '')
    if connecteur not in ac.PAR_CODE:
        flash('Choisissez un type de source.', 'warning')
        return redirect(url_for('.sources'))
    if request.method == 'GET':
        return _formulaire(s, connecteur)
    from models import chiffrer_secret
    c = ac.PAR_CODE[connecteur]
    f = request.form
    nom = (f.get('nom') or '').strip()[:150]
    if not nom:
        flash('Donnez un nom à la source.', 'warning')
        return _formulaire(s, connecteur)
    p = dict((s.parametres if s else {}) or {})
    sec = dict((s.secrets if s else {}) or {})
    for ch in c['champs']:
        v = (f.get('f_' + ch['code']) or '').strip()
        if ch['secret']:
            if f.get('effacer_' + ch['code']):
                sec.pop(ch['code'], None)
            elif v:
                sec[ch['code']] = chiffrer_secret(v)
        else:
            p[ch['code']] = v[:500]
    extractions = {}
    for j in c['jeux']:
        v = (f.get('x_' + j) or '').strip()
        if v:
            if c['extraction'] == 'requete':
                try:
                    ac.verifier_requete(v)
                except ac.ErreurSource as e:
                    flash(f'{am.JEUX[j]["libelle"]} : {e}', 'warning')
                    return _formulaire(s, connecteur)
            extractions[j] = {{'requete': 'requete', 'chemin': 'chemin', 'url': 'url', 'fichier': 'fichier'}.get(c['extraction'], 'valeur'): v[:6000]}
    if c['extraction'] != 'api':
        p['extractions'] = extractions
    if s is None:
        s = m.SourceAnalyse(client_id=cid, connecteur=connecteur, created_by=current_user.id, actif=True)
        m.db.session.add(s)
    s.nom, s.parametres, s.secrets = nom, p, sec
    ad._json(s, 'parametres')
    ad._json(s, 'secrets')
    m.db.session.flush()
    journaliser('analyse_source_enregistree', {'source': s.id, 'connecteur': connecteur}, client_id=cid)
    m.db.session.commit()
    if f.get('action') == 'tester':
        return redirect(url_for('.source_tester', sid=s.id, go=1))
    flash('Source enregistrée. Testez la connexion.', 'success')
    return redirect(url_for('.sources'))


@bp.route('/sources/<int:sid>/tester', methods=['GET', 'POST'])
@login_required
def source_tester(sid):
    cid = _cid()
    if not peut_gerer_sources(cid=cid):
        abort(403)
    if request.method == 'GET' and not request.args.get('go'):
        return redirect(url_for('.sources'))
    s = _source(sid, cid)
    try:
        ext = ac.tester(s.connecteur, s.parametres or {}, secrets_de(s))
        _maj_secrets(s, ext.secrets_a_jour)
        s.dernier_test_ok, s.dernier_message = True, (ext.info or 'Connexion établie.')[:500]
        flash(f'{s.nom} : {s.dernier_message}', 'success')
    except ac.ErreurSource as e:
        s.dernier_test_ok, s.dernier_message = False, str(e)[:500]
        flash(f'{s.nom} : {e}', 'warning')
    s.dernier_test_le = datetime.utcnow()
    journaliser('analyse_source_test', {'source': s.id, 'ok': s.dernier_test_ok}, client_id=cid)
    _m().db.session.commit()
    return redirect(url_for('.sources'))


@bp.route('/sources/<int:sid>/supprimer', methods=['POST'])
@login_required
def source_supprimer(sid):
    cid = _cid()
    if not peut_gerer_sources(cid=cid):
        abort(403)
    m = _m()
    s = _source(sid, cid)
    if m.AnalyseProgrammee.query.filter_by(source_id=s.id).count():
        s.actif, s.secrets = False, {}
        flash('Source désactivée et identifiants effacés (des analyses programmées y font référence).', 'success')
    else:
        m.db.session.delete(s)
        flash('Source supprimée.', 'success')
    journaliser('analyse_source_supprimee', {'source': sid}, client_id=cid)
    m.db.session.commit()
    return redirect(url_for('.sources'))


# ====================================================================== 2. lecture dans une analyse de mission
def _date(v):
    d = am.lire_date((v or '').strip())
    return None if d in (None, 'ERREUR') else d


@bp.route('/<int:analyse_id>/jeu/<type_jeu>/source', methods=['POST'])
@login_required
def lire_dans_analyse(analyse_id, type_jeu):
    an, a = ad._analyse(analyse_id)
    if type_jeu not in am.JEUX:
        abort(404)
    retour = redirect(url_for('analyse_donnees.page', analyse_id=an.id, etape='donnees') + f'#jeu-{type_jeu}')
    if not ad._modifiable(an, a):
        return retour
    try:
        s = _source(int(request.form.get('source_id') or 0), a.client_id)
    except ValueError:
        abort(404)
    if not s.actif:
        flash('Source désactivée.', 'warning')
        return retour
    debut, fin = _date(request.form.get('debut')), _date(request.form.get('fin'))
    try:
        ext = extraire(s, type_jeu, debut, fin)
        entetes, lignes, infos = ac.vers_tableau(ext)
    except (ac.ErreurSource, am.ErreurFichier) as e:
        _m().db.session.commit()
        flash(f'{s.nom} : {e}', 'warning')
        return retour
    if not lignes:
        flash(f'{s.nom} : aucune ligne pour cette période.', 'info')
        return retour
    octets = ext.en_octets()
    nom = ext.nom_fichier(s.connecteur, type_jeu)
    infos = dict(infos, lignes_brutes=lignes)
    if ext.octets is None:                       # tableau du connecteur : relu ensuite comme un CSV
        entetes, lignes, infos = am.lire_fichier(octets, nom)
    corr = ext.correspondance or None
    ad.creer_jeu(an, a, type_jeu, octets, nom, entetes, infos, correspondance=corr,
                 origine={'source': s.nom, 'connecteur': s.connecteur, 'debut': debut.isoformat() if debut else None,
                          'fin': fin.isoformat() if fin else None})
    flash(f'{am.JEUX[type_jeu]["libelle"]} : {len(lignes)} ligne(s) lue(s) dans « {s.nom} ». Vérifiez la correspondance des colonnes.', 'success')
    return redirect(url_for('analyse_donnees.colonnes', analyse_id=an.id, type_jeu=type_jeu))


# ====================================================================== 3. analyses programmées
def prochaine_nuit(maintenant=None):
    n = maintenant or datetime.utcnow()
    d = n.replace(hour=2, minute=0, second=0, microsecond=0)
    return d if d > n else d + timedelta(days=1)


def _prochaine(frequence, depuis=None):
    jours = {f: n for f, _l, n in FREQUENCES}.get(frequence, 30)
    d = (depuis or datetime.utcnow()) + timedelta(days=jours)
    return d.replace(hour=2, minute=0, second=0, microsecond=0)        # la nuit (heure du serveur)


@bp.route('/programmes')
@login_required
def programmes():
    cid = _cid()
    if not peut_programmer(cid=cid):
        abort(403)
    m = _m()
    liste = m.AnalyseProgrammee.query.filter_by(client_id=cid).order_by(m.AnalyseProgrammee.nom).all()
    return render_template('egalyx/analyse_programmes.html', liste=liste, sources=sources_pour(cid), FREQ={f: l for f, l, _n in FREQUENCES},
                           PERIODES=dict(ac.PERIODES), peut_sources=peut_gerer_sources(cid=cid),
                           source=lambda sid: m.db.session.get(m.SourceAnalyse, sid))


def _choix_formulaire(cid):
    m = _m()
    referentiels = m.ReferentielControle.query.filter_by(client_id=cid).order_by(m.ReferentielControle.code_controle).all() \
        if hasattr(m, 'ReferentielControle') else []
    referentiels = [r for r in referentiels if not getattr(r, 'is_archived', False)]
    kris = m.KRI.query.filter_by(client_id=cid).order_by(m.KRI.id).all() if hasattr(m.KRI, 'client_id') else []
    users = m.User.query.filter_by(client_id=cid, is_active=True).order_by(m.User.username).all()
    analyses = m.AnalyseDonnees.query.filter_by(client_id=cid).order_by(m.AnalyseDonnees.id.desc()).limit(50).all()
    return dict(referentiels=referentiels, kris=kris, users=users, analyses=analyses, nom=nom_personne)


@bp.route('/programmes/nouveau', methods=['GET', 'POST'])
@bp.route('/programmes/<int:pid>/modifier', methods=['GET', 'POST'])
@login_required
def programme_form(pid=None):
    cid = _cid()
    if not peut_programmer(cid=cid):
        abort(403)
    m = _m()
    p = _programme(pid, cid) if pid else None
    srcs = sources_pour(cid)
    if request.method == 'POST':
        f = request.form
        try:
            src = _source(int(f.get('source_id') or 0), cid)
        except ValueError:
            abort(404)
        c = ac.PAR_CODE.get(src.connecteur)
        jeux = [j for j in f.getlist('jeux') if j in (c['jeux'] if c else [])]
        tests = [t['code'] for t in am.TESTS if f.get('t_' + t['code'])]
        nom = (f.get('nom') or '').strip()[:200]
        if not (nom and jeux and tests):
            flash('Indiquez un nom, au moins un type de données et au moins un test.', 'warning')
            return render_template('egalyx/analyse_programme_form.html', p=p, form=f, sources=srcs, **_vars_form(cid))
        params = {}
        modele = f.get('modele_parametres')
        if modele:
            try:
                an = m.db.session.get(m.AnalyseDonnees, int(modele))
                if an is not None and an.client_id == cid:
                    params = dict(an.parametres or {})
                    params.pop('_general', None)
            except ValueError:
                pass
        elif p is not None:
            params = dict(p.parametres or {})
        liens = []
        for i in range(3):
            k, t, mes = f.get(f'kri_{i}'), f.get(f'kri_test_{i}'), f.get(f'kri_mesure_{i}')
            if k and t in am.TESTS_PAR_CODE and mes in dict(MESURES):
                kri = m.db.session.get(m.KRI, int(k)) if str(k).isdigit() else None
                if kri is not None and getattr(kri, 'client_id', None) == cid:
                    liens.append({'kri_id': kri.id, 'test': t, 'mesure': mes})
        ref = f.get('referentiel_id')
        referentiel = m.db.session.get(m.ReferentielControle, int(ref)) if ref and ref.isdigit() else None
        if referentiel is not None and referentiel.client_id != cid:
            referentiel = None
        uids = {u.id for u in m.User.query.filter_by(client_id=cid).all()}
        ctrl = int(f.get('controleur_id')) if (f.get('controleur_id') or '').isdigit() and int(f.get('controleur_id')) in uids else None
        resp = int(f.get('responsable_id')) if (f.get('responsable_id') or '').isdigit() and int(f.get('responsable_id')) in uids else None
        nouveau = p is None
        if nouveau:
            p = m.AnalyseProgrammee(client_id=cid, created_by=current_user.id, etat={})
            m.db.session.add(p)
        frequence = f.get('frequence') if f.get('frequence') in {x for x, _l, _n in FREQUENCES} else 'mensuelle'
        p.nom, p.source_id, p.jeux, p.tests, p.parametres = nom, src.id, jeux, tests, params
        p.periode = f.get('periode') if f.get('periode') in dict(ac.PERIODES) else 'mois_precedent'
        if p.frequence != frequence or p.prochaine_execution is None:
            p.prochaine_execution = prochaine_nuit()
        p.frequence = frequence
        p.referentiel_id = referentiel.id if referentiel else None
        p.controleur_id, p.responsable_id = ctrl, resp
        p.kri_liens, p.actif = liens, bool(f.get('actif'))
        for ch in ('jeux', 'tests', 'parametres', 'kri_liens'):
            ad._json(p, ch)
        m.db.session.flush()
        journaliser('analyse_programmee_enregistree', {'programme': p.id, 'nouveau': nouveau}, client_id=cid)
        m.db.session.commit()
        flash('Analyse programmée enregistrée.' + (' Elle s’exécutera automatiquement à la prochaine échéance.' if p.actif else ''), 'success')
        return redirect(url_for('.programme', pid=p.id))
    if not srcs:
        flash('Connectez d’abord une source de données (administrateur de l’organisation).', 'info')
        return redirect(url_for('.programmes'))
    return render_template('egalyx/analyse_programme_form.html', p=p, form={}, sources=srcs, **_vars_form(cid))


def _vars_form(cid):
    return dict(_choix_formulaire(cid), TESTS=am.TESTS, DOMAINES=am.DOMAINES, JEUX=am.JEUX, ORDRE=am.ORDRE_JEUX, PAR_CODE=ac.PAR_CODE,
                FREQUENCES=FREQUENCES, PERIODES=ac.PERIODES, MESURES=MESURES)


@bp.route('/programmes/<int:pid>')
@login_required
def programme(pid):
    cid = _cid()
    if not peut_programmer(cid=cid):
        abort(403)
    m = _m()
    p = _programme(pid, cid)
    execs = m.ExecutionAnalyseProgrammee.query.filter_by(programme_id=p.id).order_by(m.ExecutionAnalyseProgrammee.id.desc()).limit(30).all()
    ex = execs[0] if execs else None
    if request.args.get('execution'):
        try:
            ex = next(e for e in execs if e.id == int(request.args['execution']))
        except (StopIteration, ValueError):
            pass
    pl = m.db.session.get(m.PlanificationControle, (p.etat or {}).get('planification_id')) if (p.etat or {}).get('planification_id') else None
    return render_template('egalyx/analyse_programme.html', p=p, execs=execs, ex=ex, src=m.db.session.get(m.SourceAnalyse, p.source_id),
                           FREQ={f: l for f, l, _n in FREQUENCES}, PERIODES=dict(ac.PERIODES), JEUX=am.JEUX, NIVEAUX=am.NIVEAUX,
                           TESTS=am.TESTS_PAR_CODE, MESURES=dict(MESURES), fr=ad.montant_fr, pl=pl,
                           kri=lambda i: m.db.session.get(m.KRI, i), nom=lambda uid: nom_personne(m.db.session.get(m.User, uid)) if uid else '',
                           referentiel=m.db.session.get(m.ReferentielControle, p.referentiel_id) if p.referentiel_id else None,
                           resultats=sorted(((ex.resultats or {}).values() if ex else []), key=am.priorite))


@bp.route('/programmes/<int:pid>/executer', methods=['POST'])
@login_required
def programme_executer(pid):
    cid = _cid()
    if not peut_programmer(cid=cid):
        abort(403)
    p = _programme(pid, cid)
    ex = executer_programme(p, declenchement='manuel', par_id=current_user.id)
    flash(('Exécution terminée : ' + (ex.message or '')) if ex.statut == 'ok' else f'Exécution en erreur : {ex.message}',
          'success' if ex.statut == 'ok' else 'warning')
    return redirect(url_for('.programme', pid=p.id))


@bp.route('/programmes/<int:pid>/supprimer', methods=['POST'])
@login_required
def programme_supprimer(pid):
    cid = _cid()
    if not peut_programmer(cid=cid):
        abort(403)
    m = _m()
    p = _programme(pid, cid)
    for e in m.ExecutionAnalyseProgrammee.query.filter_by(programme_id=p.id).all():
        m.db.session.delete(e)
    m.db.session.delete(p)
    journaliser('analyse_programmee_supprimee', {'programme': pid}, client_id=cid)
    m.db.session.commit()
    flash('Analyse programmée supprimée (les planifications N2 et mesures KRI créées sont conservées).', 'success')
    return redirect(url_for('.programmes'))


# ====================================================================== exécution
def _cle(a, code):
    return f'{code}|{a["jeu"]}|{a["ref"]}|{a["tiers"]}|{a["motif"]}'


def _notifier(prog, titre, message, urgence='normal'):
    m = _m()
    for uid in {prog.responsable_id, prog.controleur_id} - {None}:
        try:
            n = m.Notification(type_notification='warning' if urgence != 'normal' else 'info', titre=titre[:200], message=message,
                               destinataire_id=uid, entite_type='analyse_programmee', entite_id=prog.id, urgence=urgence, est_lue=False,
                               created_at=datetime.utcnow())
            if hasattr(n, 'client_id'):
                n.client_id = prog.client_id
            m.db.session.add(n)
        except Exception as e:  # noqa: BLE001
            journal.warning('Notification non créée : %r', e)


def _planification(prog, debut, fin, par_id):
    """Planification N2 de la période en cours de traitement (créée au besoin)."""
    m = _m()
    etat = dict(prog.etat or {})
    pl = m.db.session.get(m.PlanificationControle, etat.get('planification_id')) if etat.get('planification_id') else None
    if pl is not None and pl.statut in ('a_faire', 'en_cours') and pl.referentiel_id == prog.referentiel_id:
        return pl
    aujourd_hui = date.today()
    ref = f'AD{prog.id}-{aujourd_hui:%Y%m%d}'
    n = 1
    while m.PlanificationControle.query.filter_by(client_id=prog.client_id, reference=ref).first():
        n += 1
        ref = f'AD{prog.id}-{aujourd_hui:%Y%m%d}-{n}'
    pl = m.PlanificationControle(reference=ref, annee=aujourd_hui.year, mois=aujourd_hui.month, date_prevue=aujourd_hui, statut='en_cours',
                                 referentiel_id=prog.referentiel_id, controleur_id=prog.controleur_id or prog.responsable_id,
                                 client_id=prog.client_id, created_by=par_id or prog.created_by,
                                 perimetre=f'Analyse de données automatique « {prog.nom} » — données du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}'[:500])
    m.db.session.add(pl)
    m.db.session.flush()
    etat['planification_id'] = pl.id
    prog.etat = etat
    ad._json(prog, 'etat')
    return pl


def _alimenter_n2(prog, nouvelles, debut, fin, par_id):
    """Ajoute les nouvelles anomalies comme éléments « en anomalie » de l'échantillon de la planification N2."""
    from flask_login import login_user
    from egalyx import c2n_echantillon as ce
    m = _m()
    pl = _planification(prog, debut, fin, par_id)
    acteur = m.db.session.get(m.User, par_id or pl.controleur_id or prog.created_by)
    with current_app.test_request_context():
        if acteur is not None:
            login_user(acteur)
        ex = ce._execution(pl, creer=True)
        numero = m.ElementEchantillonN2.query.filter_by(execution_id=ex.id).count()
        for code, a in nouvelles[:ELEMENTS_MAX]:
            numero += 1
            t = am.TESTS_PAR_CODE[code]
            details = ' · '.join(x for x in (a['tiers'], a['date'], ad.montant_fr(a['montant']) if a['montant'] else '') if x)
            m.db.session.add(m.ElementEchantillonN2(
                execution_id=ex.id, client_id=prog.client_id, numero=numero, reference=(a['ref'] or a['tiers'] or '—')[:200],
                resultat='anomalie', motif=f'{t["titre"]} : {a["motif"]}'[:300], criticite=CRITICITE_N2.get(t['niveau'], 'mineur'),
                commentaire=f'{details}\nRelevé automatiquement par l’analyse programmée « {prog.nom} » (ligne {a["ligne"]} du fichier). '
                            'Examinez l’élément : passez-le en « conforme » s’il est justifié.'))
        m.db.session.flush()
        ce.synchroniser(ex, pl)
        ex.commentaires = ((ex.commentaires or '') + f'\n{datetime.utcnow():%d/%m/%Y %H:%M} — analyse « {prog.nom} » : '
                           f'{min(len(nouvelles), ELEMENTS_MAX)} nouvelle(s) anomalie(s) ajoutée(s).').strip()
    return pl, min(len(nouvelles), ELEMENTS_MAX)


def _mesures_kri(prog, resultats, par_id):
    m = _m()
    faites = []
    for l in prog.kri_liens or []:
        r = resultats.get(l['test'])
        kri = m.db.session.get(m.KRI, l['kri_id'])
        if r is None or kri is None or r['statut'] not in ('ok', 'anomalies'):
            continue
        v = {'nb': r['nb'], 'cas': r['cas'], 'montant': r['montant'] or 0,
             'taux': round(100.0 * r['nb'] / r['population'], 2) if r['population'] else 0}[l['mesure']]
        m.db.session.add(m.MesureKRI(kri_id=kri.id, valeur=float(v), date_mesure=datetime.utcnow(), client_id=prog.client_id,
                                     created_by=par_id or prog.responsable_id or prog.created_by,
                                     commentaire=f'Analyse programmée « {prog.nom} » — {r["titre"]} ({dict(MESURES)[l["mesure"]].lower()})'))
        faites.append({'kri_id': kri.id, 'valeur': v, 'mesure': l['mesure'], 'test': l['test']})
    return faites


def executer_programme(prog, declenchement='automatique', par_id=None, aujourd_hui=None):
    """Lit les données de la période, lance les tests, alimente N2 et KRI, prévient le responsable. Ne lève pas d'erreur."""
    m = _m()
    debut, fin = ac.periode(prog.periode or 'mois_precedent', aujourd_hui)
    ex = m.ExecutionAnalyseProgrammee(programme_id=prog.id, client_id=prog.client_id, debut=datetime.utcnow(), declenchement=declenchement,
                                      periode_debut=debut, periode_fin=fin, par_id=par_id)
    m.db.session.add(ex)
    source = m.db.session.get(m.SourceAnalyse, prog.source_id)
    try:
        if source is None or not source.actif or source.client_id != prog.client_id:
            raise ac.ErreurSource('Source de données désactivée ou supprimée.')
        donnees, jeux = {}, []
        for j in prog.jeux or []:
            ext = extraire(source, j, debut, fin)
            if ext.octets is None and not ext.lignes:
                jeux.append({'type': j, 'libelle': am.JEUX[j]['libelle'], 'lignes': 0, 'empreinte': '', 'avertissements': ['Aucune ligne sur la période.']})
                continue
            entetes, lignes, infos = ac.vers_tableau(ext)
            octets = ext.en_octets()
            if ext.octets is None:
                entetes, _l, infos = am.lire_fichier(octets, 'extraction.csv')
                lignes = infos['lignes_brutes']
            corr = ext.correspondance or ((prog.etat or {}).get('correspondances') or {}).get(j) or am.proposer_correspondance(j, entetes)
            manque = am.obligatoires_manquants(j, {k: v for k, v in corr.items() if v in entetes})
            if manque:
                raise ac.ErreurSource(f'{am.JEUX[j]["libelle"]} : colonnes indispensables introuvables ({", ".join(manque)}). '
                                      'Nommez les colonnes de la requête ou du fichier comme dans le modèle.')
            df, q = am.normaliser(j, entetes, lignes, corr, infos.get('premiere_ligne', 2))
            donnees[j] = df
            jeux.append({'type': j, 'libelle': am.JEUX[j]['libelle'], 'lignes': q['lignes'], 'empreinte': am.empreinte(octets),
                         'avertissements': q['avertissements'][:5], 'total': q.get('total')})
        from egalyx import profil_reglementaire as pr
        resultats = am.executer(donnees, prog.tests or [], prog.parametres or {}, devise=_devise(prog.client_id), limite=200, cloture=fin,
                                defauts=pr.defauts_tests(prog.client_id))
        precedentes = set((prog.etat or {}).get('cles') or [])
        actuelles, nouvelles = set(), []
        for code, r in resultats.items():
            for a in r['anomalies']:
                k = _cle(a, code)
                actuelles.add(k)
                if k not in precedentes:
                    nouvelles.append((code, a))
        suites = {}
        if prog.referentiel_id and nouvelles:
            pl, nb = _alimenter_n2(prog, nouvelles, debut, fin, par_id)
            suites['n2'] = {'planification_id': pl.id, 'reference': pl.reference, 'elements': nb}
        mes = _mesures_kri(prog, resultats, par_id)
        if mes:
            suites['kri'] = mes
        etat = dict(prog.etat or {})
        etat['cles'] = sorted(precedentes | actuelles)[-20000:]
        prog.etat = etat
        ad._json(prog, 'etat')
        avec = sum(1 for r in resultats.values() if r['statut'] == 'anomalies')
        ex.statut, ex.jeux, ex.resultats, ex.nouvelles, ex.suites = 'ok', jeux, resultats, len(nouvelles), suites
        ex.message = (f'{sum(x["lignes"] for x in jeux)} ligne(s) lue(s), {len(resultats)} test(s), {avec} avec des anomalies, '
                      f'{len(nouvelles)} nouvelle(s) anomalie(s)' + (f', ajoutée(s) au contrôle {suites["n2"]["reference"]}' if 'n2' in suites else '')
                      + (f', {len(mes)} mesure(s) KRI' if mes else '') + '.')
        if nouvelles:
            _notifier(prog, f'Analyse « {prog.nom} » : {len(nouvelles)} nouvelle(s) anomalie(s)', ex.message, 'important')
    except Exception as e:  # noqa: BLE001
        m.db.session.rollback()
        ex = m.ExecutionAnalyseProgrammee(programme_id=prog.id, client_id=prog.client_id, debut=datetime.utcnow(), declenchement=declenchement,
                                          periode_debut=debut, periode_fin=fin, par_id=par_id, statut='erreur',
                                          message=str(e)[:1000] if isinstance(e, (ac.ErreurSource, am.ErreurFichier))
                                          else f'Erreur inattendue ({type(e).__name__}). Le détail est dans le journal du serveur.')
        if not isinstance(e, (ac.ErreurSource, am.ErreurFichier)):
            journal.exception('Analyse programmée %s', prog.id)
        m.db.session.add(ex)
        prog = m.db.session.get(m.AnalyseProgrammee, prog.id)
        _notifier(prog, f'Analyse « {prog.nom} » : exécution en erreur', ex.message, 'important')
    ex.fin = datetime.utcnow()
    prog.derniere_execution, prog.dernier_statut, prog.dernier_message = ex.fin, ex.statut, (ex.message or '')[:500]
    if declenchement == 'automatique' or prog.prochaine_execution is None:
        prog.prochaine_execution = _prochaine(prog.frequence, ex.fin)
    try:
        journaliser('analyse_programmee_executee', {'programme': prog.id, 'statut': ex.statut, 'nouvelles': ex.nouvelles or 0}, client_id=prog.client_id)
    except Exception:  # noqa: BLE001
        pass
    m.db.session.commit()
    return ex


def _devise(cid):
    from egalyx.localisation import devise
    return (devise(cid) or 'FCFA')[:10]


def relever_programmes(app, maintenant=None):
    """Exécute les analyses programmées arrivées à échéance. Chaque analyse est réservée en base avant d'être exécutée :
    deux processus serveur ne l'exécutent jamais en même temps."""
    import models as M
    from models import db
    with app.app_context():
        maintenant = maintenant or datetime.utcnow()
        dues = [p.id for p in M.AnalyseProgrammee.query.filter(M.AnalyseProgrammee.actif.is_(True),
                                                               M.AnalyseProgrammee.prochaine_execution <= maintenant).limit(50)]
        faites = 0
        for pid in dues:
            pris = db.session.query(M.AnalyseProgrammee).filter(M.AnalyseProgrammee.id == pid, M.AnalyseProgrammee.prochaine_execution <= maintenant) \
                .update({'prochaine_execution': maintenant + timedelta(hours=2)}, synchronize_session=False)
            db.session.commit()
            if not pris:
                continue
            p = db.session.get(M.AnalyseProgrammee, pid)
            if p is None or not ad.module_actif(p.client_id):
                continue
            executer_programme(p, 'automatique')
            faites += 1
        return faites


def _demarrer(app):
    if os.environ.get('EGALYX_COLLECTE_AUTO', '1') == '0' or app.config.get('TESTING') or getattr(app, '_egalyx_analyses_prog', False):
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        sch = BackgroundScheduler(daemon=True)
        sch.add_job(lambda: relever_programmes(app), 'interval', minutes=15, id='egalyx_analyses_programmees', replace_existing=True,
                    max_instances=1, coalesce=True, next_run_time=datetime.now() + timedelta(minutes=2))
        sch.start()
        app._egalyx_analyses_prog = True
    except Exception as e:  # noqa: BLE001
        journal.warning('Analyses programmées : planificateur non démarré (%r)', e)


def enregistrer(app):
    if 'analyse_sources' not in app.blueprints:
        app.register_blueprint(bp)
    app.jinja_env.globals['analyse_sources_pour'] = lambda cid, jeu=None: sources_pour(cid, jeu)
    app.jinja_env.globals['analyse_programmes_visible'] = lambda: peut_programmer()
    app.jinja_env.globals['analyse_sources_visible'] = lambda: peut_gerer_sources()
    _demarrer(app)
