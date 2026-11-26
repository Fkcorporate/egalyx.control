"""
egalyx/profil_reglementaire.py — profil réglementaire de chaque organisation : « Côte d'Ivoire / UEMOA » ou
« France / Union européenne ».

Le super admin le choisit sur la fiche Réglages de l'organisation (/super-admin/client/<id>/reglages). Il prérègle
l'outil sans rien bloquer (chaque réglage reste modifiable par l'organisation) :
  - devise et fuseau horaire (proposés à l'application du profil) ;
  - référentiel comptable (SYSCOHADA révisé / plan comptable général et FEC), comptes sensibles et d'attente ;
  - jours fériés (fêtes fixes et chrétiennes mobiles calculées ; les fêtes musulmanes, fixées chaque année, sont à ajouter) ;
  - lutte contre le blanchiment (CENTIF et loi uniforme UEMOA / Tracfin, Code monétaire et financier, ACPR), crédit
    (dispositif prudentiel BCEAO / règles européennes de défaut), données personnelles (ARTCI / RGPD) ;
  - seuils des tests de l'analyse de données convertis dans la devise (valeurs rondes, à adapter) ;
  - textes de la bibliothèque de tests et des constats, consignes de l'IA (références réglementaires du profil).
Stockage : ClientConfiguration.preferences['profil_reglementaire'] (pas de nouvelle table). Sans choix : profil déduit
de la devise de l'organisation (EUR → France / UE, sinon Côte d'Ivoire / UEMOA).
"""
from datetime import date, timedelta

from flask import Blueprint, abort, flash, redirect, request, url_for

from egalyx.commun import est_super_admin, journaliser

bp = Blueprint('profil_reglementaire', __name__)


def _paques(an):
    """Dimanche de Pâques (algorithme de Meeus / Jones / Butcher)."""
    a, b, c = an % 19, an // 100, an % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mois = (h + l_ - 7 * m + 114) // 31
    jour = ((h + l_ - 7 * m + 114) % 31) + 1
    return date(an, mois, jour)


def feries_mobiles(annees):
    res = []
    for an in annees:
        p = _paques(an)
        res += [p + timedelta(days=1), p + timedelta(days=39), p + timedelta(days=50)]   # lundi de Pâques, Ascension, lundi de Pentecôte
    return res


def _feries(fixes, annees=None):
    annees = annees or range(date.today().year - 2, date.today().year + 2)
    return fixes + ' ' + ' '.join(d.strftime('%d/%m/%Y') for d in feries_mobiles(annees))


PROFILS = {
    'uemoa': {
        'libelle': 'Côte d’Ivoire / UEMOA (OHADA)', 'court': 'Côte d’Ivoire / UEMOA', 'drapeau': 'CI',
        'devise': 'XOF', 'fuseau': 'Africa/Abidjan', 'symbole': 'FCFA',
        'comptable': 'SYSCOHADA révisé (Acte uniforme OHADA relatif au droit comptable)', 'format_compta': 'export du grand livre SYSCOHADA',
        'feries_fixes': '01/01 01/05 07/08 15/08 01/11 15/11 25/12', 'feries_note': 'Fêtes de Côte d’Ivoire ; ajoutez les fêtes musulmanes de l’année (Ramadan, Tabaski, Maouloud)',
        'comptes_sensibles': '47, 52, 57, 58, 46', 'comptes_libelle': 'SYSCOHADA : 46 associés, 47 attente, 52 banques, 57 caisse, 58 virements internes',
        'attente_libelle': 'SYSCOHADA : 471 à 476',
        'lcb_cellule': 'CENTIF', 'lcb_texte': 'loi uniforme relative à la LBC/FT dans l’UEMOA et instructions de la BCEAO',
        'regulateur': 'BCEAO et Commission bancaire de l’UMOA', 'credit': 'dispositif prudentiel de la BCEAO (créances en souffrance)',
        'donnees': 'loi ivoirienne n° 2013-450 sur la protection des données à caractère personnel (ARTCI)',
        'references': ['Normes internationales d’audit interne (IIA, 2024)', 'COSO 2013', 'Actes uniformes OHADA', 'SYSCOHADA révisé',
                       'Réglementation BCEAO et Commission bancaire de l’UMOA', 'Loi uniforme LBC/FT (CENTIF)', 'Loi ivoirienne sur les données personnelles (ARTCI)'],
        'facteur': 1.0,
    },
    'france': {
        'libelle': 'France / Union européenne', 'court': 'France / UE', 'drapeau': 'FR',
        'devise': 'EUR', 'fuseau': 'Europe/Paris', 'symbole': '€',
        'comptable': 'plan comptable général (règlement ANC) et Code de commerce', 'format_compta': 'fichier des écritures comptables (FEC)',
        'feries_fixes': '01/01 01/05 08/05 14/07 15/08 01/11 11/11 25/12', 'feries_note': 'Fêtes de France (lundi de Pâques, Ascension et lundi de Pentecôte calculés)',
        'comptes_sensibles': '455, 47, 512, 53, 58', 'comptes_libelle': 'PCG : 455 associés, 47 attente, 512 banques, 53 caisse, 58 virements internes',
        'attente_libelle': 'PCG : 471 à 476',
        'lcb_cellule': 'Tracfin', 'lcb_texte': 'Code monétaire et financier (articles L.561-1 et suivants) et ACPR',
        'regulateur': 'ACPR et AMF', 'credit': 'règles européennes de défaut (règlement CRR, retard de plus de 90 jours)',
        'donnees': 'RGPD et loi Informatique et Libertés (CNIL)',
        'references': ['Normes internationales d’audit interne (IIA, 2024)', 'COSO 2013', 'Code de commerce et plan comptable général',
                       'Code monétaire et financier (LCB-FT, Tracfin, ACPR)', 'RGPD (CNIL)', 'DORA et NIS2 selon le secteur'],
        'facteur': 1 / 655.957,
    },
}
ORDRE = ['uemoa', 'france']

# seuils de l'analyse de données pour le profil France / UE (en euros, valeurs rondes à adapter)
SEUILS_EUR = {
    ('FRACTIONNEMENT', 'seuil'): 10_000, ('DELEGATION', 'seuil'): 2_000, ('MONTANTS_RONDS', 'multiple'): 1_000,
    ('MONTANTS_RONDS', 'montant_min'): 5_000, ('GL_SENSIBLES', 'montant_min'): 5_000, ('GL_RONDS', 'multiple'): 10_000,
    ('GL_RONDS', 'montant_min'): 50_000, ('GL_EXTOURNES', 'montant_min'): 10_000, ('CRD_DELEGATION', 'seuil'): 10_000,
    ('CRD_FRACTIONNEMENT', 'seuil'): 50_000, ('CRD_SANS_GARANTIE', 'seuil'): 25_000, ('LCB_FRACTIONNEMENT', 'seuil'): 10_000,
    ('LCB_PEP', 'seuil'): 15_000, ('LCB_DORMANTS', 'montant_min'): 2_000, ('LCB_TRANSIT', 'montant_min'): 10_000,
}


def _m():
    import models
    return models


def code_profil(cid):
    """Profil de l'organisation : choisi par le super admin, sinon déduit de la devise."""
    if not cid:
        return 'uemoa'
    m = _m()
    conf = m.ClientConfiguration.query.filter_by(client_id=cid).first()
    choisi = ((conf.preferences or {}).get('profil_reglementaire') if conf else None)
    if choisi in PROFILS:
        return choisi
    c = m.db.session.get(m.Client, cid)
    return 'france' if (getattr(c, 'devise', None) or '').upper() == 'EUR' else 'uemoa'


def profil(cid):
    return dict(PROFILS[code_profil(cid)], code=code_profil(cid))


def choisi(cid):
    m = _m()
    conf = m.ClientConfiguration.query.filter_by(client_id=cid).first()
    return ((conf.preferences or {}).get('profil_reglementaire') if conf else None) in PROFILS


# ---------------------------------------------------------------------- analyse de données
REMPLACEMENTS = {
    'france': [
        ('Fêtes fixes de Côte d’Ivoire par défaut ; ajoutez les fêtes mobiles de la période', 'Fêtes de France (fêtes mobiles calculées)'),
        ('SYSCOHADA : 46 associés, 47 attente, 52 banques, 57 caisse, 58 virements internes', PROFILS['france']['comptes_libelle']),
        ('SYSCOHADA : 471 à 476', PROFILS['france']['attente_libelle']),
        ('(principe de la partie double, SYSCOHADA)', '(principe de la partie double, plan comptable général)'),
        ('(Acte uniforme OHADA relatif au droit comptable)', '(Code de commerce et plan comptable général)'),
        ('(loi uniforme LBC/FT, instructions BCEAO)', '(Code monétaire et financier, ACPR)'),
        ('(dispositif prudentiel BCEAO / COBAC)', '(règles européennes de défaut, règlement CRR)'),
        ('déclarer à la CENTIF', 'déclarer à Tracfin'), ('CENTIF', 'Tracfin'),
        ('export du grand livre (SYSCOHADA)', 'fichier des écritures comptables (FEC)'),
    ],
}


def _remplacer(texte, code):
    if not isinstance(texte, str):
        return texte
    for a, b in REMPLACEMENTS.get(code, []):
        texte = texte.replace(a, b)
    return texte


def defaut_parametre(code_test, code_param, defaut, code):
    """Valeur par défaut d'un réglage de test pour le profil (seuils dans la devise, jours fériés, comptes)."""
    p = PROFILS[code]
    if code_param == 'feries':
        return _feries(p['feries_fixes'])
    if code_test == 'GL_SENSIBLES' and code_param == 'comptes':
        return p['comptes_sensibles']
    if code == 'france' and isinstance(defaut, (int, float)) and not isinstance(defaut, bool):
        if (code_test, code_param) in SEUILS_EUR:
            return SEUILS_EUR[(code_test, code_param)]
    return defaut


def test_pour(t, code):
    """Copie d'un test de la bibliothèque adaptée au profil (textes et réglages par défaut)."""
    c = dict(t)
    for k in ('description', 'critere', 'consequence', 'recommandation', 'titre'):
        c[k] = _remplacer(t.get(k), code)
    c['params'] = [(pc, _remplacer(lib, code), defaut_parametre(t['code'], pc, d, code), _remplacer(aide, code)) for pc, lib, d, aide in t['params']]
    return c


def tests(cid):
    from egalyx import analyse_moteur as am
    code = code_profil(cid)
    return [test_pour(t, code) for t in am.TESTS]


def tests_par_code(cid):
    return {t['code']: t for t in tests(cid)}


def defauts_tests(cid):
    """{code_test: {param: défaut du profil}} pour am.executer."""
    return {t['code']: {pc: d for pc, _l, d, _a in t['params']} for t in tests(cid)}


def contexte_ia(cid):
    p = profil(cid)
    return (f"Contexte réglementaire de l'organisation : {p['libelle']}. Devise : {p['symbole']}. Comptabilité : {p['comptable']}. "
            f"Lutte contre le blanchiment : {p['lcb_texte']} (cellule de renseignement financier : {p['lcb_cellule']}). "
            f"Régulateur : {p['regulateur']}. Données personnelles : {p['donnees']}. "
            "Cite ces références plutôt que celles d'un autre pays.")


# ---------------------------------------------------------------------- choix par le super admin
@bp.route('/super-admin/client/<int:client_id>/profil-reglementaire', methods=['POST'])
def choisir(client_id):
    from flask_login import current_user
    if not getattr(current_user, 'is_authenticated', False) or not est_super_admin(current_user):
        abort(403)
    m = _m()
    c = m.db.session.get(m.Client, client_id)
    if c is None:
        abort(404)
    code = request.form.get('profil')
    if code not in PROFILS:
        flash('Profil inconnu.', 'warning')
        return redirect(url_for('lettre_mission.reglages_client', client_id=client_id))
    conf = m.ClientConfiguration.query.filter_by(client_id=client_id).first()
    if conf is None:
        conf = m.ClientConfiguration(client_id=client_id, couleurs={}, preferences={})
        m.db.session.add(conf)
    prefs = dict(conf.preferences or {})
    prefs['profil_reglementaire'] = code
    conf.preferences = prefs
    try:
        from models import marquer_json_modifie
        marquer_json_modifie(conf, 'preferences')
    except Exception:  # noqa: BLE001
        pass
    p = PROFILS[code]
    if request.form.get('appliquer_localisation'):
        c.devise, c.fuseau_horaire = p['devise'], p['fuseau']
        from flask import g
        for cle in [k for k in vars(g) if k.startswith('_eg_loc_')]:
            delattr(g, cle)
    journaliser('profil_reglementaire', {'profil': code, 'localisation': bool(request.form.get('appliquer_localisation'))}, client_id=client_id)
    m.db.session.commit()
    flash(f'Profil réglementaire « {p["libelle"]} » appliqué à {c.nom}.'
          + (f' Devise {p["symbole"]} et fuseau {p["fuseau"]} appliqués.' if request.form.get('appliquer_localisation') else ''), 'success')
    return redirect(url_for('lettre_mission.reglages_client', client_id=client_id) + '#profil')


def enregistrer(app):
    if 'profil_reglementaire' not in app.blueprints:
        app.register_blueprint(bp)
    from egalyx.commun import client_id_courant

    def _profil_courant():
        try:
            return profil(client_id_courant())
        except Exception:  # noqa: BLE001
            return dict(PROFILS['uemoa'], code='uemoa')
    app.jinja_env.globals['profil_reglementaire'] = _profil_courant
    app.jinja_env.globals['profil_de'] = lambda cid: profil(cid)
    app.jinja_env.globals['PROFILS_REGLEMENTAIRES'] = PROFILS
    app.jinja_env.globals['profil_choisi'] = choisi
