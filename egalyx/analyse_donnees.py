"""
egalyx/analyse_donnees.py — Analyse des données d'audit (lot 1 : achats, fournisseurs, paiements).

Sur la fiche d'une mission d'audit, en trois étapes :
  1. Données   : import Excel / CSV par type de données, correspondance des colonnes (proposée
                 automatiquement, ou par l'IA à partir des seuls noms de colonnes), contrôle de qualité,
                 empreinte SHA-256 du fichier d'origine (preuve d'intégrité) ;
  2. Tests     : bibliothèque de 21 tests (egalyx/analyse_moteur.py), seuils réglables ;
  3. Résultats : anomalies par ordre de priorité, export Excel, puis en un clic : feuille de travail
                 (test exhaustif sur les anomalies), échantillon traçable, constat (5 C) à relire.

Le cœur ne dépend d'aucune IA : même fichier + mêmes réglages = même résultat. L'IA (fonction « Analyse
de données » chez le super admin) ne voit jamais les fichiers : seulement les noms de colonnes (correspondance),
les chiffres agrégés et quelques anomalies masquées (synthèse, rédaction du constat).

Garde-fous : module « sur activation » (le super admin le coche pour le client) + permission « Analyse de
données » ; équipe de la mission ou gestionnaires de l'audit, dans leur organisation ; fichiers chiffrés sur le
disque (EGALYX_CLE_CHIFFREMENT) et supprimés à l'échéance de conservation (résultats conservés) ; dossier figé
après le rapport définitif ; tout est journalisé.
"""
import io
import os
import re
import time
from datetime import datetime, timedelta

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, send_file,
                   url_for)
from flask_login import current_user, login_required

from egalyx import analyse_moteur as am
from egalyx.commun import est_super_admin, journaliser, nom_personne

bp = Blueprint('analyse_donnees', __name__, url_prefix='/analyse-donnees')

CODE_MODULE = 'analyse_donnees'
PERMISSION = 'can_use_analyse_donnees'
FONCTION_IA = 'analyse_donnees'
TAILLE_MAX = 15 * 1024 * 1024
CONSERVATION_DEFAUT = 90
CONSERVATIONS = (30, 60, 90, 180, 365, 730)
GRAVITE_DU_NIVEAU = {'eleve': 'majeure', 'moyen': 'moyenne', 'faible': 'mineure'}
PREFIXE_CHIFFRE = b'EGXAD1'
PROCESSUS_DU_DOMAINE = {'Factures': 'Achats, fournisseurs et paiements', 'Paiements': 'Achats, fournisseurs et paiements',
                        'Achats': 'Achats, fournisseurs et paiements', 'Fournisseurs': 'Achats, fournisseurs et paiements',
                        'Analyse des montants': 'Achats, fournisseurs et paiements', 'Comptabilité': 'Comptabilité et clôture des comptes',
                        'Ventes et encaissements': 'Ventes, facturation et encaissements', 'Paie': 'Ressources humaines et paie',
                        'Habilitations informatiques': 'Sécurité des systèmes d’information', 'Crédit': 'Crédit et engagements',
                        'LCB-FT': 'Conformité LCB-FT', 'Analyse statistique': 'Analyse des montants'}


def _m():
    import models
    return models


def _ap():
    from egalyx import audit_plus
    return audit_plus


def _moteur_ia():
    from egalyx import ia_moteur
    return ia_moteur


def ia_active():
    try:
        from egalyx.ia import fonction_active
        return fonction_active(FONCTION_IA)
    except Exception:  # noqa: BLE001
        return False


# ====================================================================== droits
def module_actif(cid):
    from egalyx.modules_client import module_sur_activation_actif
    m = _m()
    client = m.db.session.get(m.Client, cid) if cid else None
    return module_sur_activation_actif(client, CODE_MODULE)


def _est_admin_org(u):
    return getattr(u, 'role', None) == 'admin' or bool(getattr(u, 'is_client_admin', False))


def peut_utiliser(u=None, cid=None):
    u = u or current_user
    if not getattr(u, 'is_authenticated', False):
        return False
    if est_super_admin(u):
        return True
    if not module_actif(cid or getattr(u, 'client_id', None)):
        return False
    # permission dédiée, ou gestion des missions d'audit (le chef de mission l'a sans réglage supplémentaire)
    return _est_admin_org(u) or u.has_permission(PERMISSION) or u.has_permission('can_manage_audit')


def peut_sur_audit(audit, u=None):
    u = u or current_user
    try:
        from egalyx.ia_audit import peut_travailler
        return peut_utiliser(u, audit.client_id) and peut_travailler(audit, u)
    except Exception:  # noqa: BLE001
        return False


def _audit(audit_id):
    a = _ap().charger_audit(audit_id)              # organisation + module Audit interne, sinon 404
    if not peut_utiliser(cid=a.client_id):
        abort(404)
    if not peut_sur_audit(a):
        abort(403)
    return a


def _analyse(analyse_id):
    m = _m()
    an = m.db.session.get(m.AnalyseDonnees, analyse_id)
    if an is None:
        abort(404)
    a = _audit(an.audit_id)
    if an.client_id != a.client_id:
        abort(404)
    return an, a


def _fige(audit):
    try:
        from egalyx.dossier_fige import est_fige
        return est_fige(audit)
    except Exception:  # noqa: BLE001
        return False


def _modifiable(an, audit):
    """Refuse toute modification d'un dossier figé (rapport définitif émis)."""
    if _fige(audit):
        flash('Le rapport définitif est émis : le dossier est figé, l’analyse ne peut plus être modifiée.', 'warning')
        return False
    return True


# ====================================================================== réglages (conservation)
def _conf(cid, creer=False):
    m = _m()
    conf = m.ClientConfiguration.query.filter_by(client_id=cid).first()
    if conf is None and creer:
        conf = m.ClientConfiguration(client_id=cid, couleurs={}, preferences={})
        m.db.session.add(conf)
    return conf


def conservation_jours(cid):
    conf = _conf(cid)
    v = ((conf.preferences or {}).get('analyse_donnees') or {}).get('conservation_jours') if conf else None
    return v if v in CONSERVATIONS else CONSERVATION_DEFAUT


def _ecrire_conservation(cid, jours):
    conf = _conf(cid, creer=True)
    prefs = dict(conf.preferences or {})
    prefs['analyse_donnees'] = dict(prefs.get('analyse_donnees') or {}, conservation_jours=jours)
    conf.preferences = prefs
    try:
        from models import marquer_json_modifie
        marquer_json_modifie(conf, 'preferences')
    except Exception:  # noqa: BLE001
        pass


# ====================================================================== stockage chiffré
def dossier_stockage():
    base = os.environ.get('EGALYX_DOSSIER_ANALYSES')
    if not base:
        up = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        base = os.path.join(up if os.path.isabs(up) else os.path.join(current_app.root_path, up), 'analyses_donnees')
    return base


def _chemin(cid, an_id, nom):
    d = os.path.join(dossier_stockage(), str(int(cid)), str(int(an_id)))
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, nom)


def ecrire_fichier(chemin, octets):
    """Écrit le contenu, chiffré si EGALYX_CLE_CHIFFREMENT est définie. Renvoie True si chiffré."""
    f = _m()._fernet()
    donnees = PREFIXE_CHIFFRE + f.encrypt(octets) if f is not None else octets
    tmp = chemin + '.tmp'
    with open(tmp, 'wb') as fh:
        fh.write(donnees)
    os.replace(tmp, chemin)
    return f is not None


def lire_fichier(chemin):
    if not chemin or not os.path.exists(chemin):
        return None
    with open(chemin, 'rb') as fh:
        donnees = fh.read()
    if donnees.startswith(PREFIXE_CHIFFRE):
        f = _m()._fernet()
        if f is None:
            return None
        return f.decrypt(donnees[len(PREFIXE_CHIFFRE):])
    return donnees


def _effacer(*chemins):
    for c in chemins:
        if c and os.path.exists(c):
            try:
                os.remove(c)
            except OSError:
                pass


def supprimer_contenu(jeu, statut='supprime'):
    _effacer(jeu.chemin_brut, jeu.chemin_normalise)
    jeu.chemin_brut = jeu.chemin_normalise = None
    jeu.statut = statut
    jeu.supprime_le = datetime.utcnow()


def purger(cid=None):
    """Supprime le contenu des fichiers arrivés à échéance (les résultats et empreintes restent)."""
    m = _m()
    q = m.JeuDonneesAnalyse.query.filter(m.JeuDonneesAnalyse.statut != 'supprime', m.JeuDonneesAnalyse.expire_le < datetime.utcnow())
    if cid:
        q = q.filter(m.JeuDonneesAnalyse.client_id == cid)
    n = 0
    for j in q.limit(200).all():
        supprimer_contenu(j)
        n += 1
    if n:
        journaliser('analyse_donnees_purge', {'jeux': n}, client_id=cid)
        m.db.session.commit()
    return n


# ====================================================================== utilitaires
def _jeux(an):
    m = _m()
    res = {}
    for j in m.JeuDonneesAnalyse.query.filter_by(analyse_id=an.id).order_by(m.JeuDonneesAnalyse.id).all():
        res[j.type_jeu] = j                       # le plus récent l'emporte
    return res


def _donnees(an, jeux=None):
    """Tableaux normalisés des jeux prêts : {type: DataFrame}, plus la liste de ce qui n'a pas pu être relu."""
    jeux = jeux or _jeux(an)
    res, illisibles = {}, []
    for t, j in jeux.items():
        if j.statut != 'pret':
            continue
        octets = lire_fichier(j.chemin_normalise)
        if octets is None:
            illisibles.append(am.JEUX[t]['libelle'])
            continue
        res[t] = am.depuis_octets(t, octets)
    return res, illisibles


def _reference(cid):
    m = _m()
    annee = datetime.now().year
    n = m.AnalyseDonnees.query.filter(m.AnalyseDonnees.client_id == cid, m.AnalyseDonnees.reference.like(f'AD-{annee}-%')).count() + 1
    while m.AnalyseDonnees.query.filter_by(client_id=cid, reference=f'AD-{annee}-{n:03d}').first():
        n += 1
    return f'AD-{annee}-{n:03d}'


def _devise(audit):
    """Symbole de la devise de l'organisation (FCFA, €…), d'après ses réglages « Heure et devise »."""
    try:
        from egalyx.localisation import devise
        return (devise(audit.client_id) or 'FCFA')[:10]
    except Exception:  # noqa: BLE001
        return 'FCFA'


def _pr():
    from egalyx import profil_reglementaire
    return profil_reglementaire


def _json(obj, champ):
    try:
        from models import marquer_json_modifie
        marquer_json_modifie(obj, champ)
    except Exception:  # noqa: BLE001
        pass


def montant_fr(x, devise=''):
    return am._fr(x, devise)


def cloture_de(an):
    """Date de clôture enregistrée pour l'analyse (datetime.date) ou None."""
    v = ((an.parametres or {}).get('_general') or {}).get('cloture')
    try:
        return datetime.strptime(v, '%Y-%m-%d').date() if v else None
    except (TypeError, ValueError):
        return None


def cloture_proposee(donnees):
    """Fin du mois de la date la plus fréquente de fin de période : dernier jour du mois de la dernière écriture de la période
    (hors écritures de l'exercice suivant), proposée à l'auditeur qui la confirme."""
    import calendar
    for jeu in ('grand_livre', 'ventes', 'factures', 'paiements'):
        df = donnees.get(jeu)
        if df is None or 'date' not in df.columns or not df['date'].notna().any():
            continue
        par_mois = df['date'].dropna().dt.to_period('M').value_counts().sort_index()
        mois = par_mois[par_mois >= max(3, par_mois.median() * 0.3)]      # écarte les quelques écritures de l'exercice suivant
        if len(mois):
            m = mois.index.max()
            return datetime(m.year, m.month, calendar.monthrange(m.year, m.month)[1]).date()
    return None


# ====================================================================== pages
@bp.route('/')
@login_required
def toutes():
    """Toutes les analyses de l'organisation (rubrique Audit interne), et création depuis une mission."""
    from egalyx.commun import client_id_courant
    cid = client_id_courant()
    if not cid or not peut_utiliser(cid=cid):
        abort(404)
    purger(cid)
    m = _m()
    ap = _ap()
    audits = [a for a in m.Audit.query.filter_by(client_id=cid).order_by(m.Audit.id.desc()).all() if peut_sur_audit(a)]
    ids = {a.id for a in audits}
    analyses = [x for x in m.AnalyseDonnees.query.filter_by(client_id=cid).order_by(m.AnalyseDonnees.id.desc()).all() if x.audit_id in ids]
    par_id = {a.id: a for a in audits}
    return render_template('egalyx/analyse_donnees_toutes.html', analyses=analyses, audit=par_id.get, audits=[a for a in audits if not _fige(a)],
                           nom=lambda uid: nom_personne(m.db.session.get(m.User, uid)) if uid else '', gestionnaire=ap.est_gestionnaire_audit(current_user))


@bp.route('/nouvelle', methods=['POST'])
@login_required
def nouvelle_depuis_liste():
    try:
        audit_id = int(request.form.get('audit_id') or 0)
    except ValueError:
        abort(404)
    return nouvelle(audit_id)


@bp.route('/audit/<int:audit_id>')
@login_required
def liste(audit_id):
    a = _audit(audit_id)
    purger(a.client_id)
    m = _m()
    analyses = m.AnalyseDonnees.query.filter_by(audit_id=a.id).order_by(m.AnalyseDonnees.id.desc()).all()
    if len(analyses) == 1 and request.args.get('liste') != '1':
        return redirect(url_for('.page', analyse_id=analyses[0].id))
    return render_template('egalyx/analyse_donnees_liste.html', audit=a, analyses=analyses, fige=_fige(a))


@bp.route('/audit/<int:audit_id>/nouvelle', methods=['POST'])
@login_required
def nouvelle(audit_id):
    a = _audit(audit_id)
    if not _modifiable(None, a):
        return redirect(url_for('detail_audit', id=a.id))
    m = _m()
    titre = re.sub(r'\s+', ' ', request.form.get('titre') or '').strip()[:200] or 'Analyse des données de la mission'
    an = m.AnalyseDonnees(client_id=a.client_id, audit_id=a.id, reference=_reference(a.client_id), titre=titre, devise=_devise(a),
                          tests_choisis=[t['code'] for t in am.TESTS], parametres={}, liens={}, created_by=current_user.id)
    m.db.session.add(an)
    m.db.session.flush()
    journaliser('analyse_donnees_creee', {'audit': a.id, 'analyse': an.id}, client_id=a.client_id)
    m.db.session.commit()
    return redirect(url_for('.page', analyse_id=an.id))


@bp.route('/<int:analyse_id>')
@login_required
def page(analyse_id):
    an, a = _analyse(analyse_id)
    purger(a.client_id)
    jeux = _jeux(an)
    etape = request.args.get('etape')
    if etape not in ('donnees', 'tests', 'resultats'):
        etape = 'resultats' if an.resultats else 'tests' if any(j.statut == 'pret' for j in jeux.values()) else 'donnees'
    resultats = sorted((an.resultats or {}).values(), key=am.priorite)
    applicables, cloture, cloture_auto = {}, cloture_de(an), False
    if etape == 'tests':
        donnees, _ill = _donnees(an, jeux)
        c = am.Contexte(donnees)
        applicables = {t['code']: am.manquants(t, c) for t in am.TESTS}
        if cloture is None:
            cloture, cloture_auto = cloture_proposee(donnees), True
    return render_template('egalyx/analyse_donnees.html', audit=a, an=an, jeux=jeux, etape=etape, fige=_fige(a),
                           JEUX=am.JEUX, ORDRE=am.ORDRE_JEUX, TESTS=_pr().tests(a.client_id), DOMAINES=am.DOMAINES, NIVEAUX=am.NIVEAUX,
                           resultats=resultats, applicables=applicables, ia_ok=ia_active(), fr=montant_fr, CYCLES=am.CYCLES,
                           cloture=cloture, cloture_auto=cloture_auto,
                           conservation=conservation_jours(a.client_id), conservations=CONSERVATIONS,
                           chiffrement=_m()._fernet() is not None, peut_regler=_ap().est_gestionnaire_audit(current_user),
                           nom=lambda uid: nom_personne(_m().db.session.get(_m().User, uid)) if uid else '',
                           parametres=lambda t: am.parametres_effectifs(t, (an.parametres or {}).get(t['code'])),
                           profil=_pr().profil(a.client_id))


# ---------------------------------------------------------------------- 1. import
@bp.route('/<int:analyse_id>/jeu/<type_jeu>/importer', methods=['POST'])
@login_required
def importer(analyse_id, type_jeu):
    an, a = _analyse(analyse_id)
    if type_jeu not in am.JEUX:
        abort(404)
    retour = redirect(url_for('.page', analyse_id=an.id, etape='donnees'))
    if not _modifiable(an, a):
        return retour
    fichier = request.files.get('fichier')
    if not fichier or not fichier.filename:
        flash('Choisissez un fichier Excel (.xlsx) ou CSV.', 'warning')
        return retour
    octets = fichier.read(TAILLE_MAX + 1)
    if len(octets) > TAILLE_MAX:
        flash('Fichier trop volumineux (15 Mo au plus) : découpez-le par période, ou enregistrez-le en .xlsx (plus compact que le CSV).', 'warning')
        return retour
    nom = os.path.basename(fichier.filename)[:255]
    try:
        entetes, _lignes, infos = am.lire_fichier(octets, nom, feuille=(request.form.get('feuille') or '').strip() or None)
    except am.ErreurFichier as e:
        flash(str(e), 'warning')
        return retour
    j = creer_jeu(an, a, type_jeu, octets, nom, entetes, infos)
    return redirect(url_for('.colonnes', analyse_id=an.id, type_jeu=type_jeu))


def creer_jeu(an, a, type_jeu, octets, nom, entetes, infos, correspondance=None, origine=None):
    """Enregistre un fichier (importé ou lu par un connecteur) : empreinte, contenu chiffré, correspondance proposée."""
    m = _m()
    ancien = _jeux(an).get(type_jeu)
    j = m.JeuDonneesAnalyse(analyse_id=an.id, client_id=a.client_id, type_jeu=type_jeu, nom_fichier=nom[:255], empreinte=am.empreinte(octets),
                            taille=len(octets), format=infos['format'], feuille=infos.get('feuille') or None, entetes=entetes,
                            correspondance=correspondance or am.proposer_correspondance(type_jeu, entetes), nb_lignes=len(infos['lignes_brutes']),
                            statut='a_valider', importe_par=current_user.id,
                            expire_le=datetime.utcnow() + timedelta(days=conservation_jours(a.client_id)),
                            qualite={'infos': dict({k: v for k, v in infos.items() if k != 'lignes_brutes'}, **({'origine': origine} if origine else {}))})
    m.db.session.add(j)
    m.db.session.flush()
    j.chemin_brut = _chemin(a.client_id, an.id, f'jeu{j.id}_origine.bin')
    j.chiffre = ecrire_fichier(j.chemin_brut, octets)
    if ancien is not None:
        supprimer_contenu(ancien, statut='remplace')
    journaliser('analyse_donnees_import', {'analyse': an.id, 'jeu': type_jeu, 'fichier': nom, 'empreinte': j.empreinte,
                                           'lignes': j.nb_lignes, 'origine': origine or 'fichier'}, client_id=a.client_id)
    m.db.session.commit()
    return j


def _jeu(an, type_jeu):
    if type_jeu not in am.JEUX:
        abort(404)
    j = _jeux(an).get(type_jeu)
    if j is None or j.statut in ('supprime', 'remplace'):
        abort(404)
    return j


def _relire(j):
    octets = lire_fichier(j.chemin_brut)
    if octets is None:
        return None
    return am.lire_fichier(octets, j.nom_fichier, feuille=j.feuille)


@bp.route('/<int:analyse_id>/jeu/<type_jeu>/colonnes', methods=['GET', 'POST'])
@login_required
def colonnes(analyse_id, type_jeu):
    an, a = _analyse(analyse_id)
    j = _jeu(an, type_jeu)
    lu = _relire(j)
    if lu is None:
        flash('Le fichier d’origine n’est plus disponible (conservation échue ou clé de chiffrement changée) : importez-le à nouveau.', 'warning')
        return redirect(url_for('.page', analyse_id=an.id, etape='donnees'))
    entetes, lignes, infos = lu
    if request.method == 'POST':
        if not _modifiable(an, a):
            return redirect(url_for('.page', analyse_id=an.id))
        corr = {}
        for code, *_r in am.champs(type_jeu):
            v = request.form.get('c_' + code) or ''
            if v in entetes:
                corr[code] = v
        manque = am.obligatoires_manquants(type_jeu, corr)
        if manque:
            flash('Colonnes indispensables à indiquer : ' + ', '.join(manque) + '.', 'warning')
            j.correspondance = corr
            _json(j, 'correspondance')
            _m().db.session.commit()
            return redirect(url_for('.colonnes', analyse_id=an.id, type_jeu=type_jeu))
        df, qualite = am.normaliser(type_jeu, entetes, infos['lignes_brutes'], corr, infos['premiere_ligne'])
        qualite['infos'] = (j.qualite or {}).get('infos', {})
        j.correspondance, j.qualite, j.nb_lignes = corr, qualite, qualite['lignes']
        j.chemin_normalise = _chemin(a.client_id, an.id, f'jeu{j.id}_normalise.bin')
        ecrire_fichier(j.chemin_normalise, am.vers_octets(df))
        j.statut = 'pret'
        _json(j, 'qualite')
        journaliser('analyse_donnees_colonnes', {'analyse': an.id, 'jeu': type_jeu, 'lignes': qualite['lignes'],
                                                 'avertissements': len(qualite['avertissements'])}, client_id=a.client_id)
        _m().db.session.commit()
        flash(f'{am.JEUX[type_jeu]["libelle"]} : {qualite["lignes"]} lignes prêtes pour l’analyse.'
              + (' Lisez les points de vigilance du contrôle de qualité.' if qualite['avertissements'] else ''), 'success')
        return redirect(url_for('.page', analyse_id=an.id, etape='donnees') + f'#jeu-{type_jeu}')
    apercu = [[am.texte(v)[:60] for v in l] for l in lignes[:6]]
    return render_template('egalyx/analyse_donnees_colonnes.html', audit=a, an=an, j=j, info=am.JEUX[type_jeu], champs=am.champs(type_jeu),
                           entetes=entetes, apercu=apercu, infos=infos, ia_ok=ia_active(), fige=_fige(a))


CONSIGNES_COLONNES = """Tu aides un auditeur à importer un fichier. On te donne les noms des colonnes d'un fichier (jamais les données)
et la liste des champs attendus. Associe à chaque champ la colonne qui lui correspond, ou "" s'il n'y en a pas.
Une colonne ne sert qu'une fois. N'invente aucun nom de colonne : reprends-les exactement.
Réponds uniquement par un objet JSON {"correspondance": {"code_du_champ": "nom exact de la colonne ou vide"}}."""


@bp.route('/<int:analyse_id>/jeu/<type_jeu>/colonnes/ia', methods=['POST'])
@login_required
def colonnes_ia(analyse_id, type_jeu):
    an, a = _analyse(analyse_id)
    j = _jeu(an, type_jeu)
    if not ia_active():
        return jsonify({'success': False, 'error': "L'IA n'est pas activée pour l'analyse de données."}), 403
    mo = _moteur_ia()
    entetes = list(j.entetes or [])
    champs_attendus = [{'code': c, 'libelle': lib, 'obligatoire': ob} for c, lib, ob, *_r in am.champs(type_jeu)]
    try:
        r = mo.demander_json(CONSIGNES_COLONNES, {'type_de_donnees': am.JEUX[type_jeu]['libelle'], 'colonnes_du_fichier': entetes,
                                                  'champs_attendus': champs_attendus}, max_tokens=800, temperature=0)
        prop = r.get('correspondance') if isinstance(r, dict) else None
        if not isinstance(prop, dict):
            raise mo.IndisponibleIA('réponse inattendue')
    except mo.IndisponibleIA:
        return jsonify({'success': True, 'correspondance': am.proposer_correspondance(type_jeu, entetes), 'origine': 'automatique',
                        'message': 'IA indisponible : correspondance proposée à partir des noms de colonnes.'})
    corr, pris = {}, set()
    for code, *_r in am.champs(type_jeu):
        v = prop.get(code)
        if isinstance(v, str) and v in entetes and v not in pris:
            corr[code] = v
            pris.add(v)
    journaliser('ia_analyse_colonnes', {'analyse': an.id, 'jeu': type_jeu}, client_id=a.client_id, valider=True)
    return jsonify({'success': True, 'correspondance': corr, 'origine': 'ia', 'message': 'Correspondance proposée par l’IA : vérifiez-la.'})


@bp.route('/<int:analyse_id>/jeu/<type_jeu>/supprimer', methods=['POST'])
@login_required
def supprimer_jeu(analyse_id, type_jeu):
    an, a = _analyse(analyse_id)
    if _modifiable(an, a):
        j = _jeu(an, type_jeu)
        supprimer_contenu(j)
        journaliser('analyse_donnees_jeu_supprime', {'analyse': an.id, 'jeu': type_jeu, 'empreinte': j.empreinte}, client_id=a.client_id)
        _m().db.session.commit()
        flash(f'{am.JEUX[type_jeu]["libelle"]} : fichier supprimé. Les résultats déjà obtenus restent dans l’analyse.', 'success')
    return redirect(url_for('.page', analyse_id=an.id, etape='donnees'))


@bp.route('/modele/<type_jeu>.xlsx')
@login_required
def modele(type_jeu):
    if not peut_utiliser():
        abort(404)
    if type_jeu not in am.JEUX and type_jeu != 'tous':
        abort(404)
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    wb.remove(wb.active)
    gras, fond = Font(bold=True, color='FFFFFF'), PatternFill('solid', fgColor='1F4E79')
    notice = wb.create_sheet('Mode d’emploi')
    notice.append(['Modèle d’import — Analyse de données (achats, comptabilité, ventes)'])
    notice['A1'].font = Font(bold=True, size=13)
    notice.append(['Une ligne par élément. Les noms de colonnes peuvent être différents : vous indiquerez la correspondance à l’import.'])
    notice.append(['Dates au format jj/mm/aaaa ; montants sans symbole de devise (les espaces sont acceptés). Les lignes d’exemple sont fictives : supprimez-les.'])
    notice.append([])
    notice.append(['Données', 'Colonne', 'Indispensable', 'Format'])
    for c in notice[5]:
        c.font, c.fill = gras, fond
    formats = {'id': 'Identifiant', 'texte': 'Texte', 'nom': 'Nom de la personne', 'date': 'Date jj/mm/aaaa', 'montant': 'Montant',
               'nombre': 'Nombre', 'rib': 'RIB ou IBAN', 'telephone': 'Téléphone', 'horodatage': 'Date et heure jj/mm/aaaa hh:mm'}
    types = am.ORDRE_JEUX if type_jeu == 'tous' else [type_jeu]
    for t in types:
        for code, lib, ob, typ, _s in am.champs(t):
            notice.append([am.JEUX[t]['libelle'], lib, 'Oui' if ob else 'Non', formats.get(typ, typ)])
        ws = wb.create_sheet(am.JEUX[t]['libelle'][:31])
        ws.append([lib + (' *' if ob else '') for _c, lib, ob, *_r in am.champs(t)])
        for c in ws[1]:
            c.font, c.fill = gras, fond
        for l in am.exemple(t):
            ws.append(l)
        for k, col in enumerate(ws.columns):
            ws.column_dimensions[col[0].column_letter].width = max(14, min(36, len(str(ws.cell(1, k + 1).value)) + 4))
    for col, w in zip('ABCD', (24, 34, 14, 20)):
        notice.column_dimensions[col].width = w
    b = io.BytesIO()
    wb.save(b)
    b.seek(0)
    nom = 'modeles_analyse_donnees.xlsx' if type_jeu == 'tous' else f'modele_{type_jeu}.xlsx'
    return send_file(b, as_attachment=True, download_name=nom,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


# ---------------------------------------------------------------------- 2. tests
@bp.route('/<int:analyse_id>/executer', methods=['POST'])
@login_required
def executer(analyse_id):
    an, a = _analyse(analyse_id)
    if not _modifiable(an, a):
        return redirect(url_for('.page', analyse_id=an.id))
    f = request.form
    choix = [t['code'] for t in am.TESTS if f.get('t_' + t['code'])]
    parametres = {}
    for t in _pr().tests(a.client_id):
        brut = {code: f.get(f'p_{t["code"]}_{code}') for code, *_r in t['params'] if f.get(f'p_{t["code"]}_{code}') is not None}
        parametres[t['code']] = am.parametres_effectifs(t, brut)
    cloture = am.lire_date((f.get('cloture') or '').strip())
    if cloture == 'ERREUR':
        flash('Date de clôture illisible : saisissez-la au format jj/mm/aaaa.', 'warning')
        return redirect(url_for('.page', analyse_id=an.id, etape='tests'))
    parametres['_general'] = {'cloture': cloture.isoformat() if cloture else None}
    an.tests_choisis, an.parametres = choix, parametres
    _json(an, 'parametres')
    if not choix:
        _m().db.session.commit()
        flash('Cochez au moins un test.', 'warning')
        return redirect(url_for('.page', analyse_id=an.id, etape='tests'))
    jeux = _jeux(an)
    donnees, illisibles = _donnees(an, jeux)
    if not donnees:
        flash('Aucune donnée prête : importez au moins un fichier et validez la correspondance des colonnes.', 'warning')
        return redirect(url_for('.page', analyse_id=an.id, etape='donnees'))
    debut = time.time()
    resultats = am.executer(donnees, choix, parametres, devise=an.devise or 'FCFA', cloture=cloture, defauts=_pr().defauts_tests(a.client_id))
    an.resultats = resultats
    an.execution = {'le': datetime.utcnow().isoformat(timespec='seconds'), 'par': current_user.id, 'duree': round(time.time() - debut, 2),
                    'version': 'lot2-2026.11', 'illisibles': illisibles, 'cloture': cloture.isoformat() if cloture else None,
                    'jeux': [{'type': t, 'libelle': am.JEUX[t]['libelle'], 'fichier': j.nom_fichier, 'empreinte': j.empreinte,
                              'lignes': j.nb_lignes, 'periode': (j.qualite or {}).get('periode'), 'total': (j.qualite or {}).get('total')}
                             for t, j in jeux.items() if t in donnees]}
    an.synthese = None
    _json(an, 'resultats')
    _json(an, 'execution')
    nb = sum(1 for r in resultats.values() if r['statut'] == 'anomalies')
    journaliser('analyse_donnees_executee', {'analyse': an.id, 'tests': len(choix), 'avec_anomalies': nb,
                                             'empreintes': [x['empreinte'][:16] for x in an.execution['jeux']]}, client_id=a.client_id)
    _m().db.session.commit()
    flash(f'{len(choix)} test(s) exécuté(s) : {nb} avec des anomalies à examiner.', 'success')
    if illisibles:
        flash('Fichiers non relus (conservation échue ?) : ' + ', '.join(illisibles) + '. Importez-les à nouveau pour les inclure.', 'warning')
    return redirect(url_for('.page', analyse_id=an.id, etape='resultats'))


# ---------------------------------------------------------------------- 3. résultats
def _resultat(an, code):
    r = (an.resultats or {}).get(code)
    if r is None or code not in am.TESTS_PAR_CODE:
        abort(404)
    return r


def _jeu_principal(r):
    jeux = [x['jeu'] for x in r['anomalies']]
    return max(set(jeux), key=jeux.count) if jeux else None


@bp.route('/<int:analyse_id>/test/<code>')
@login_required
def detail_test(analyse_id, code):
    an, a = _analyse(analyse_id)
    r = _resultat(an, code)
    q = (request.args.get('q') or '').strip().lower()
    anomalies = [x for x in r['anomalies'] if not q or q in (x['ref'] + ' ' + x['tiers'] + ' ' + x['motif']).lower()]
    return render_template('egalyx/analyse_donnees_test.html', audit=a, an=an, r=r, test=_pr().tests_par_code(a.client_id)[code], anomalies=anomalies, q=q,
                           JEUX=am.JEUX, NIVEAUX=am.NIVEAUX, fr=montant_fr, fige=_fige(a), lien=(an.liens or {}).get(code, {}),
                           ia_ok=ia_active())


def _feuille(an, a, titre, description, contenu):
    from egalyx.ia_audit import _reference_feuille
    m = _m()
    f = m.FeuilleTravail(reference=_reference_feuille(a.client_id), audit_id=a.id, client_id=a.client_id, type_feuille='test',
                         statut='brouillon', titre=titre[:200], description=description, preparee_par_id=current_user.id,
                         created_by=current_user.id, contenu={'analyse_donnees': contenu})
    m.db.session.add(f)
    m.db.session.flush()
    return f


def _source(an, jeu):
    for x in (an.execution or {}).get('jeux', []):
        if x['type'] == jeu:
            return x
    return {}


def _texte_source(an, jeu):
    s = _source(an, jeu)
    if not s:
        return ''
    per = s.get('periode')
    return (f'fichier « {s["fichier"]} » ({s["lignes"]} lignes'
            + (f', du {_date_fr(per[0])} au {_date_fr(per[1])}' if per else '') + f', empreinte SHA-256 {s["empreinte"][:16]}…)')


def _date_fr(iso):
    try:
        return datetime.strptime(iso[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
    except (TypeError, ValueError):
        return iso or ''


def _lier(an, code, **valeurs):
    liens = dict(an.liens or {})
    liens[code] = dict(liens.get(code) or {}, **valeurs)
    an.liens = liens
    _json(an, 'liens')


@bp.route('/<int:analyse_id>/test/<code>/feuille', methods=['POST'])
@login_required
def creer_feuille(analyse_id, code):
    """Feuille de travail : test exhaustif par analyse de données, les anomalies étant les éléments à examiner."""
    an, a = _analyse(analyse_id)
    r = _resultat(an, code)
    t = _pr().tests_par_code(a.client_id)[code]
    if not _modifiable(an, a):
        return redirect(url_for('.detail_test', analyse_id=an.id, code=code))
    m = _m()
    jeu = _jeu_principal(r)
    params = ', '.join(f'{lib.lower()} : {r["parametres"].get(c)}' for c, lib, *_x in t['params'] if str(r['parametres'].get(c, '')).strip())
    f = _feuille(an, a, f'Analyse de données — {t["titre"]}',
                 f'Test exhaustif par analyse de données ({an.reference}). {t["description"]}', {
                     'analyse': an.id, 'reference': an.reference, 'test': code, 'execution': an.execution,
                     'anomalies': r['anomalies'][:500]})
    lignes = '\n'.join(f'- {x["ref"] or "—"} · {x["tiers"]} · {_date_fr(x["date"])} · {montant_fr(x["montant"], an.devise)} : {x["motif"]}'
                       for x in r['anomalies'][:40])
    test = m.TestControleFeuille(
        feuille_travail_id=f.id, objet_test=t['titre'][:200], objectif_controle=t['description'],
        procedure=('1. Données importées et contrôlées : ' + '; '.join(_texte_source(an, x['type']) for x in (an.execution or {}).get('jeux', [])) + '.\n'
                   f'2. Test exécuté le {_date_fr((an.execution or {}).get("le", ""))}' + (f' ({params})' if params else '') + '.\n'
                   f'3. Examiner chaque anomalie ({r["nb"]} ligne(s), {r["cas"]} cas) avec les pièces justificatives et les explications des audités.\n'
                   '4. Conclure pour chaque cas : justifié, erreur à corriger ou anomalie à porter au constat.'),
        criteres_acceptation=t['critere'],
        echantillon=(f'Population : {r["population"]} lignes analysées (100 %). Anomalies à examiner : {r["nb"]} ligne(s)'
                     + (f', montant concerné {montant_fr(r["montant"], an.devise)}' if r['montant'] else '') + '.\n' + lignes
                     + ('\n… (liste complète dans l’analyse ' + an.reference + ' et son export Excel)' if r['nb'] > 40 else '')),
        methode_echantillonnage='exhaustif', taille_echantillon=r['nb'] or None, niveau_criticite={'eleve': 'eleve', 'moyen': 'moyen'}.get(t['niveau'], 'faible'),
        periode_couverte=(' / '.join(f"{_date_fr(p[0])} – {_date_fr(p[1])}" for p in [_source(an, jeu).get('periode')] if p) if jeu else None) or None,
        ordre=0)
    m.db.session.add(test)
    _lier(an, code, feuille=f.reference, feuille_id=f.id)
    journaliser('analyse_donnees_feuille', {'analyse': an.id, 'test': code, 'feuille': f.reference}, client_id=a.client_id)
    m.db.session.commit()
    flash(f'Feuille de travail {f.reference} créée : les {r["nb"]} anomalies sont les éléments à examiner.', 'success')
    return redirect(url_for('.detail_test', analyse_id=an.id, code=code))


@bp.route('/<int:analyse_id>/echantillon', methods=['POST'])
@login_required
def echantillon(analyse_id):
    """Échantillon traçable tiré dans un fichier importé (aléatoire avec graine conservée, ou plus gros montants)."""
    an, a = _analyse(analyse_id)
    retour = redirect(url_for('.page', analyse_id=an.id, etape='resultats') + '#echantillon')
    if not _modifiable(an, a):
        return retour
    jeu = request.form.get('jeu')
    methode = 'montants' if request.form.get('methode') == 'montants' else 'aleatoire'
    try:
        taille = max(1, min(500, int(request.form.get('taille') or 25)))
    except ValueError:
        taille = 25
    graine = request.form.get('graine') or None
    if graine is not None and not str(graine).isdigit():
        graine = None
    donnees, _ill = _donnees(an)
    if jeu not in donnees:
        flash('Choisissez des données importées et prêtes.', 'warning')
        return retour
    if methode == 'montants' and not am.JEUX[jeu]['montant']:
        methode = 'aleatoire'
    choisis, graine = am.tirer_echantillon(donnees[jeu], jeu, taille, methode, graine)
    m = _m()
    j = _jeux(an)[jeu]
    libelle = am.JEUX[jeu]['libelle']
    desc_methode = (f'tirage aléatoire reproductible (graine {graine} : le même tirage peut être refait à l’identique)' if methode == 'aleatoire'
                    else f'les {len(choisis)} plus gros montants (sélection par jugement)')
    f = _feuille(an, a, f'Analyse de données — échantillon de {libelle.lower()}',
                 f'Échantillon tiré dans les données de l’analyse {an.reference} : {desc_methode}.',
                 {'analyse': an.id, 'reference': an.reference, 'echantillon': {'jeu': jeu, 'methode': methode, 'graine': graine,
                                                                               'taille': len(choisis), 'empreinte': j.empreinte, 'elements': choisis}})
    test = m.TestControleFeuille(
        feuille_travail_id=f.id, objet_test=f'Échantillon de {libelle.lower()}'[:200],
        objectif_controle='Vérifier sur pièces les éléments sélectionnés.',
        procedure=f'1. Population : {_texte_source(an, jeu) or libelle}.\n2. Sélection : {desc_methode}.\n'
                  '3. Pour chaque élément, obtenir la pièce justificative et vérifier la réalité, l’approbation et l’exactitude du montant.',
        criteres_acceptation='Chaque élément est justifié, approuvé selon les délégations et correctement enregistré.',
        echantillon='\n'.join(f'- ligne {x["ligne"]} · {x["ref"]} · {x["tiers"]} · {_date_fr(x["date"])} · {montant_fr(x["montant"], an.devise)}'
                              for x in choisis[:200]),
        methode_echantillonnage='aleatoire' if methode == 'aleatoire' else 'jugement', taille_echantillon=len(choisis),
        niveau_criticite='moyen', ordre=0)
    m.db.session.add(test)
    journaliser('analyse_donnees_echantillon', {'analyse': an.id, 'jeu': jeu, 'methode': methode, 'graine': graine,
                                                'taille': len(choisis), 'feuille': f.reference}, client_id=a.client_id)
    m.db.session.commit()
    flash(f'Échantillon de {len(choisis)} élément(s) enregistré dans la feuille de travail {f.reference}.', 'success')
    return retour


# ---------------------------------------------------------------------- constat
def constat_automatique(an, r):
    t = _pr().tests_par_code(an.client_id)[r['code']]
    jeu = _jeu_principal(r)
    exemples = '; '.join(f'{x["ref"] or x["tiers"]} ({_date_fr(x["date"])}{", " + montant_fr(x["montant"], an.devise) if x["montant"] else ""}) : {x["motif"]}'
                         for x in r['anomalies'][:5])
    lib = am.JEUX[jeu]['libelle'].lower() if jeu else 'données'
    src = _source(an, jeu) if jeu else {}
    per = src.get('periode')
    origine = (f' du fichier « {src["fichier"]} »' + (f' (période du {_date_fr(per[0])} au {_date_fr(per[1])}, empreinte SHA-256 {src["empreinte"][:16]}…)'
               if per else f' (empreinte SHA-256 {src["empreinte"][:16]}…)')) if src else ''
    cas = f'{r["cas"]} cas' + (f' ({r["nb"]} lignes)' if r['nb'] != r['cas'] else '')
    fait = (f'L’analyse exhaustive des {r["population"]} {lib}{origine} a relevé {cas}'
            + (f' pour un montant de {montant_fr(r["montant"], an.devise)}' if r['montant'] else '')
            + f'. {t["description"]} Exemples : {exemples}.')
    return {'titre': t['titre'], 'fait': re.sub(r'\s+', ' ', fait), 'critere': t['critere'],
            'cause': 'À compléter : cause identifiée avec les audités (absence de contrôle bloquant, procédure non appliquée…).',
            'consequence': t['consequence'], 'recommandation': t['recommandation'],
            'gravite': GRAVITE_DU_NIVEAU.get(t['niveau'], 'moyenne'), 'type': 'non_conformite',
            'points_a_verifier': ['Examiner chaque cas avec les pièces : certaines anomalies peuvent être justifiées.',
                                  'Confirmer le montant final après examen.', 'Recueillir la réponse des audités.']}


@bp.route('/<int:analyse_id>/test/<code>/constat', methods=['GET', 'POST'])
@login_required
def constat(analyse_id, code):
    an, a = _analyse(analyse_id)
    r = _resultat(an, code)
    if r['statut'] != 'anomalies':
        flash('Ce test ne présente pas d’anomalie.', 'info')
        return redirect(url_for('.detail_test', analyse_id=an.id, code=code))
    if request.method == 'POST':
        if not _modifiable(an, a):
            return redirect(url_for('.detail_test', analyse_id=an.id, code=code))
        m = _m()
        f = request.form
        fait = (f.get('fait') or '').strip()[:8000]
        if len(fait) < 10:
            flash('Le fait constaté est obligatoire.', 'warning')
            return redirect(url_for('.constat', analyse_id=an.id, code=code))
        dernier = m.Constatation.query.filter_by(audit_id=a.id).order_by(m.Constatation.id.desc()).first()
        ref = f"CON-{a.reference}-{(dernier.id + 1) if dernier else 1:03d}"
        gravite = f.get('gravite') if f.get('gravite') in ('mineure', 'moyenne', 'majeure', 'critique') else 'moyenne'
        titre = (f.get('titre') or '').strip()[:150]
        c = m.Constatation(reference=ref, description=(f'{titre} — ' if titre else '') + fait, type_constatation='non_conformite',
                           gravite=gravite, criticite=gravite, processus_concerne=PROCESSUS_DU_DOMAINE.get(r.get('domaine'), r.get('domaine') or ''),
                           cause_racine=(f.get('cause') or '').strip()[:4000] or None,
                           critere=(f.get('critere') or '').strip()[:4000] or None, consequence=(f.get('consequence') or '').strip()[:4000] or None,
                           recommandations_immediates=(f.get('recommandation') or '').strip()[:4000] or None,
                           commentaires=f'Issu de l’analyse de données {an.reference} (test « {r["titre"]} », {r["nb"]} anomalie(s)). '
                                        'Les cas sont à confirmer par les pièces justificatives.',
                           documents_justificatifs=f'Analyse de données {an.reference} — ' + '; '.join(
                               f'{x["fichier"]} (SHA-256 {x["empreinte"][:16]}…)' for x in (an.execution or {}).get('jeux', [])),
                           statut='a_analyser', audit_id=a.id, created_by=current_user.id, client_id=a.client_id)
        m.db.session.add(c)
        m.db.session.flush()
        _lier(an, code, constat=c.reference, constat_id=c.id)
        journaliser('analyse_donnees_constat', {'analyse': an.id, 'test': code, 'constat': c.reference, 'ia': f.get('ia') == '1'},
                    client_id=a.client_id)
        m.db.session.commit()
        flash(f'Constat {c.reference} créé sur la mission (statut « à analyser »).', 'success')
        return redirect(url_for('detail_audit', id=a.id) + '#constatations')
    return render_template('egalyx/analyse_donnees_constat.html', audit=a, an=an, r=r, test=_pr().tests_par_code(a.client_id)[code],
                           c=constat_automatique(an, r), ia_ok=ia_active(), fige=_fige(a), fr=montant_fr)


@bp.route('/<int:analyse_id>/test/<code>/constat/ia', methods=['POST'])
@login_required
def constat_ia(analyse_id, code):
    an, a = _analyse(analyse_id)
    r = _resultat(an, code)
    if not ia_active():
        return jsonify({'success': False, 'error': "L'IA n'est pas activée pour l'analyse de données."}), 403
    base = constat_automatique(an, r)
    t = _pr().tests_par_code(a.client_id)[code]
    notes = (f'Résultat d’un test d’analyse de données : {t["titre"]}. {base["fait"]}\nRègle attendue (bibliothèque) : {t["critere"]}\n'
             f'Risque (bibliothèque) : {t["consequence"]}')
    from egalyx.ia_audit import proposer_constat
    c, origine = proposer_constat(a, notes)
    if origine != _moteur_ia().IA:
        c = base
    journaliser('ia_analyse_constat', {'analyse': an.id, 'test': code, 'origine': origine}, client_id=a.client_id, valider=True)
    return jsonify({'success': True, 'constat': c, 'origine': origine, 'origine_libelle': _moteur_ia().libelle(origine)})


# ---------------------------------------------------------------------- synthèse
CONSIGNES_SYNTHESE = """Tu es auditeur interne senior (Normes IIA 2024). On te donne les résultats chiffrés d'une analyse de données
(achats, fournisseurs, paiements) : pour chaque test, la population analysée, le nombre d'anomalies, le montant concerné et
quelques exemples. Rédige en français, en JSON :
- "synthese" : 8 à 14 lignes pour le chef de mission : périmètre analysé, principaux résultats par ordre de priorité
  (en reprenant les chiffres exacts), ce qui semble relever d'un risque de fraude, d'erreur ou de faiblesse de contrôle ;
- "priorites" : 3 à 6 actions d'examen concrètes, par ordre de priorité (quels cas vérifier, avec quelles pièces) ;
- "tests_complementaires" : 2 à 4 tests ou vérifications complémentaires utiles.
Règles : un résultat d'analyse de données est une anomalie à examiner, pas une conclusion : ne qualifie jamais un cas de fraude
avérée ; n'invente aucun chiffre ; style professionnel, phrases courtes. Réponds uniquement par l'objet JSON."""


def _donnees_synthese(an):
    tests = []
    for r in sorted((an.resultats or {}).values(), key=am.priorite):
        tests.append({'test': r['titre'], 'niveau': am.NIVEAUX.get(r['niveau'], ('',))[0], 'statut': r['statut'], 'population': r['population'],
                      'anomalies': r['nb'], 'cas': r['cas'], 'montant': r['montant'], 'raison': r['raison'],
                      'exemples': [{'ref': x['ref'], 'date': x['date'], 'montant': x['montant'], 'motif': x['motif']} for x in r['anomalies'][:5]]})
    return {'devise': an.devise,
            'donnees': [{'type': x['libelle'], 'lignes': x['lignes'], 'periode': x.get('periode'), 'total': x.get('total')}
                        for x in (an.execution or {}).get('jeux', [])], 'tests': tests}


def synthese_automatique(an):
    res = sorted((an.resultats or {}).values(), key=am.priorite)
    avec = [r for r in res if r['statut'] == 'anomalies']
    na = [r for r in res if r['statut'] == 'non_applicable']
    jeux = (an.execution or {}).get('jeux', [])
    lignes = ['Périmètre : ' + ', '.join(f'{x["libelle"].lower()} ({x["lignes"]} lignes'
                                          + (f', {_date_fr(x["periode"][0])} – {_date_fr(x["periode"][1])}' if x.get('periode') else '') + ')'
                                          for x in jeux) + '.']
    lignes.append(f'{len(res)} test(s) exécuté(s) : {len(avec)} avec des anomalies, {len(res) - len(avec) - len(na)} sans anomalie, '
                  f'{len(na)} non applicable(s) faute de données.')
    for r in avec[:8]:
        lignes.append(f'- {r["titre"]} (risque {am.NIVEAUX[r["niveau"]][0].lower()}) : {r["cas"]} cas, {r["nb"]} ligne(s)'
                      + (f', {montant_fr(r["montant"], an.devise)}' if r['montant'] else '') + '.')
    prio = [f'Examiner en priorité les cas du test « {r["titre"]} » avec les pièces justificatives.' for r in avec if r['niveau'] == 'eleve'][:4]
    comp = [f'Importer les données manquantes pour « {r["titre"]} » ({r["raison"].replace("Données à importer : ", "")[:-1]}).' for r in na][:3]
    return {'synthese': '\n'.join(lignes), 'priorites': prio, 'tests_complementaires': comp}


@bp.route('/<int:analyse_id>/synthese', methods=['POST'])
@login_required
def synthese(analyse_id):
    an, a = _analyse(analyse_id)
    if not an.resultats:
        return jsonify({'success': False, 'error': 'Lancez d’abord les tests.'}), 400
    if _fige(a):
        return jsonify({'success': False, 'error': 'Le dossier est figé.'}), 403
    mo = _moteur_ia()
    origine = mo.AUTO
    s = None
    if ia_active() and request.form.get('mode') != 'auto':
        try:
            d = _donnees_synthese(an)
            d['mission'] = a.titre
            r = mo.demander_json(CONSIGNES_SYNTHESE, d, max_tokens=1500, temperature=0.2)
            s = {'synthese': str(r.get('synthese') or '').strip()[:5000],
                 'priorites': mo.liste_textes(r.get('priorites'), 6, 400), 'tests_complementaires': mo.liste_textes(r.get('tests_complementaires'), 4, 400)}
            if not s['synthese']:
                raise mo.IndisponibleIA('vide')
            origine = mo.IA
        except mo.IndisponibleIA:
            s = None
    if s is None:
        s = synthese_automatique(an)
    an.synthese = dict(s, origine=origine, le=datetime.utcnow().isoformat(timespec='seconds'), par=current_user.id)
    _json(an, 'synthese')
    journaliser('analyse_donnees_synthese', {'analyse': an.id, 'origine': origine}, client_id=a.client_id, valider=True)
    _m().db.session.commit()
    return jsonify({'success': True, **s, 'origine': origine, 'origine_libelle': mo.libelle(origine)})


# ---------------------------------------------------------------------- export Excel
@bp.route('/<int:analyse_id>/export.xlsx')
@login_required
def export(analyse_id):
    an, a = _analyse(analyse_id)
    if not an.resultats:
        flash('Lancez d’abord les tests.', 'info')
        return redirect(url_for('.page', analyse_id=an.id))
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    complet = {}
    tronques = [c for c, r in an.resultats.items() if r.get('tronque')]
    if tronques:                                 # liste complète si les fichiers sont encore là et identiques
        jeux = _jeux(an)
        if all(jeux.get(x['type']) and jeux[x['type']].empreinte == x['empreinte'] for x in (an.execution or {}).get('jeux', [])):
            donnees, ill = _donnees(an, jeux)
            if not ill:
                complet = am.executer(donnees, tronques, an.parametres or {}, an.devise or 'FCFA', limite=10 ** 7, cloture=cloture_de(an),
                                      defauts=_pr().defauts_tests(a.client_id))
    wb = Workbook()
    ws = wb.active
    ws.title = 'Synthèse'
    gras, fond = Font(bold=True, color='FFFFFF'), PatternFill('solid', fgColor='1F4E79')
    ws.append([f'Analyse de données {an.reference} — {an.titre}'])
    ws['A1'].font = Font(bold=True, size=13)
    ex = an.execution or {}
    ws.append([f'Mission : {a.reference} — {a.titre}'])
    ws.append([f'Exécutée le {_date_fr(ex.get("le", ""))} par {nom_personne(_m().db.session.get(_m().User, ex.get("par"))) if ex.get("par") else ""}'
               + (f' — date de clôture retenue : {_date_fr(ex["cloture"])}' if ex.get('cloture') else '')])
    ws.append([])
    ws.append(['Fichier analysé', 'Données', 'Lignes', 'Période', 'Total', 'Empreinte SHA-256'])
    for c in ws[ws.max_row]:
        c.font, c.fill = gras, fond
    for x in ex.get('jeux', []):
        per = x.get('periode')
        ws.append([x['fichier'], x['libelle'], x['lignes'], f'{_date_fr(per[0])} – {_date_fr(per[1])}' if per else '', x.get('total'), x['empreinte']])
    ws.append([])
    ws.append(['Test', 'Domaine', 'Niveau de risque', 'Statut', 'Population', 'Cas', 'Lignes', 'Montant concerné', 'Paramètres / remarque'])
    for c in ws[ws.max_row]:
        c.font, c.fill = gras, fond
    statuts = {'anomalies': 'Anomalies à examiner', 'ok': 'Aucune anomalie', 'non_applicable': 'Non applicable', 'erreur': 'Erreur'}
    for r in sorted(an.resultats.values(), key=am.priorite):
        ws.append([r['titre'], r['domaine'], am.NIVEAUX.get(r['niveau'], ('',))[0], statuts.get(r['statut'], r['statut']), r['population'],
                   r['cas'], r['nb'], r['montant'] or None,
                   r['raison'] or ', '.join(f'{k} = {v}' for k, v in (r.get('parametres') or {}).items() if str(v).strip())])
    for col, w in zip('ABCDEFGHI', (42, 18, 16, 22, 12, 8, 8, 18, 60)):
        ws.column_dimensions[col].width = w
    noms = set()
    for r in sorted(an.resultats.values(), key=am.priorite):
        if r['statut'] != 'anomalies':
            continue
        anomalies = (complet.get(r['code']) or r)['anomalies']
        nom = re.sub(r'[\[\]:*?/\\]', '', r['titre'])[:28]
        while nom in noms:
            nom = nom[:26] + str(len(noms))
        noms.add(nom)
        w = wb.create_sheet(nom)
        w.append([r['titre'], '', '', '', '', '', '', f'{r["nb"]} ligne(s), {r["cas"]} cas'])
        w['A1'].font = Font(bold=True, size=12)
        w.append(['Groupe', 'Données', 'Ligne du fichier', 'Référence', 'Tiers', 'Date', 'Montant', 'Motif', 'Conclusion de l’auditeur'])
        for c in w[2]:
            c.font, c.fill = gras, fond
        for x in anomalies:
            w.append([x['groupe'] or '', am.JEUX[x['jeu']]['libelle'], x['ligne'] or '', x['ref'], x['tiers'],
                      datetime.strptime(x['date'], '%Y-%m-%d') if x['date'] else '', x['montant'], x['motif'], ''])
            w.cell(w.max_row, 6).number_format = 'DD/MM/YYYY'
            w.cell(w.max_row, 7).number_format = '#,##0'
            w.cell(w.max_row, 8).alignment = Alignment(wrap_text=True, vertical='top')
        for col, wd in zip('ABCDEFGHI', (8, 18, 10, 18, 34, 12, 16, 70, 30)):
            w.column_dimensions[col].width = wd
        w.freeze_panes = 'A3'
    b = io.BytesIO()
    wb.save(b)
    b.seek(0)
    journaliser('analyse_donnees_export', {'analyse': an.id}, client_id=a.client_id)
    _m().db.session.commit()
    return send_file(b, as_attachment=True, download_name=f'{an.reference}_resultats.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


# ---------------------------------------------------------------------- gestion
@bp.route('/<int:analyse_id>/supprimer', methods=['POST'])
@login_required
def supprimer(analyse_id):
    an, a = _analyse(analyse_id)
    if not _modifiable(an, a):
        return redirect(url_for('.page', analyse_id=an.id))
    m = _m()
    for j in m.JeuDonneesAnalyse.query.filter_by(analyse_id=an.id).all():
        _effacer(j.chemin_brut, j.chemin_normalise)
        m.db.session.delete(j)
    journaliser('analyse_donnees_supprimee', {'analyse': an.id, 'reference': an.reference}, client_id=a.client_id)
    m.db.session.delete(an)
    m.db.session.commit()
    flash('Analyse supprimée (les feuilles de travail et constats déjà créés sont conservés).', 'success')
    return redirect(url_for('detail_audit', id=a.id))


@bp.route('/<int:analyse_id>/reglages', methods=['POST'])
@login_required
def reglages(analyse_id):
    an, a = _analyse(analyse_id)
    if not _ap().est_gestionnaire_audit(current_user):
        abort(403)
    try:
        jours = int(request.form.get('conservation_jours') or 0)
    except ValueError:
        jours = 0
    if jours in CONSERVATIONS:
        _ecrire_conservation(a.client_id, jours)
        journaliser('analyse_donnees_conservation', {'jours': jours}, client_id=a.client_id)
        _m().db.session.commit()
        flash(f'Conservation des fichiers importés : {jours} jours après l’import (nouveaux imports). Les résultats sont conservés avec le dossier.', 'success')
    return redirect(url_for('.page', analyse_id=an.id, etape='donnees'))


def enregistrer(app):
    if 'analyse_donnees' not in app.blueprints:
        app.register_blueprint(bp)
    app.jinja_env.globals['analyse_donnees_peut'] = lambda audit: peut_sur_audit(audit)

    def _visible():
        from egalyx.commun import client_id_courant
        try:
            cid = client_id_courant()
            return bool(cid) and peut_utiliser(cid=cid)
        except Exception:  # noqa: BLE001
            return False
    app.jinja_env.globals['analyse_donnees_visible'] = _visible
