"""
egalyx/c2n_cartographie.py — le contrôle interne N2 relié à la cartographie, avec une vraie méthode de test.

1. Rattachement : chaque contrôle du référentiel N2 désigne les RISQUES et les DISPOSITIFS DE MAÎTRISE qu'il teste
   (listes de choix, plus de texte libre seulement).

2. Effet sur la cartographie : quand une exécution N2 est VALIDÉE (dans le N2 ou depuis la campagne rattachée), chaque
   dispositif testé reçoit une vérification « Contrôle N2 » et la règle des dispositifs s'applique
   (egalyx/maitrise.apres_verification) :
       Conforme       → efficacité inchangée, prochaine vérification selon la fréquence
       À améliorer    → efficacité −1          À corriger → −1          Non conforme → −2, nouvelle vérification à 30 j
   Le résultat vient du taux de conformité ET de la gravité de la déficience (on retient le plus défavorable) :
       taux ≥ 95 % → Conforme · 80–95 % → À améliorer · 60–80 % → À corriger · < 60 % → Non conforme
       gravité mineure → Conforme · significative → À corriger · majeure → Non conforme
   Le niveau de maîtrise suggéré des risques concernés est recalculé. Tout est tracé (vérification, historique
   d'efficacité, trace sur l'exécution). Si l'exécution est ROUVERTE, l'effet est annulé (efficacité rétablie si
   personne ne l'a changée entre-temps) puis réappliqué à la nouvelle validation : jamais de double pénalité.

3. Méthode de test : type de test (conception / efficacité / les deux), taille d'échantillon recommandée selon la
   fréquence d'exécution du contrôle (repères usuels, à adapter au risque), gravité de la déficience (déduite des
   anomalies saisies — critique → majeure, majeur → significative, mineur → mineure — ou choisie par le contrôleur).
"""
from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

bp = Blueprint('c2n_reglages', __name__, url_prefix='/c2n/reglages')

# Repères usuels de taille d'échantillon selon la fréquence d'exécution du contrôle (fourchette, valeur proposée)
ECHANTILLON = [
    ('automatique', 'Automatique (système)', (1, 1), 1),
    ('plusieurs_par_jour', 'Plusieurs fois par jour / à chaque opération', (25, 60), 40),
    ('quotidien', 'Quotidien', (20, 40), 25),
    ('hebdomadaire', 'Hebdomadaire', (5, 15), 10),
    ('mensuel', 'Mensuel', (2, 5), 3),
    ('trimestriel', 'Trimestriel', (2, 2), 2),
    ('semestriel', 'Semestriel', (1, 2), 1),
    ('annuel', 'Annuel', (1, 1), 1),
]
FREQUENCES = {c: (l, f, v) for c, l, f, v in ECHANTILLON}
# Fréquences des dispositifs de maîtrise (cartographie) → fréquence d'exécution
DEPUIS_DISPOSITIF = {'permanent': 'plusieurs_par_jour', 'quotidien': 'quotidien', 'hebdomadaire': 'hebdomadaire',
                     'mensuel': 'mensuel', 'trimestriel': 'trimestriel', 'semestriel': 'semestriel',
                     'annuel': 'annuel', 'automatique': 'automatique'}
ORDRE_FREQ = [c for c, *_ in ECHANTILLON]

TYPES_TEST = [('efficacite', 'Test d\'efficacité', 'Le contrôle est-il appliqué ? (échantillon d\'opérations)'),
              ('conception', 'Test de conception', 'Le contrôle est-il bien conçu pour couvrir le risque ?'),
              ('les_deux', 'Conception et efficacité', 'Les deux, dans cet ordre')]
GRAVITES = [('aucune', 'Aucune déficience'), ('mineure', 'Mineure'), ('significative', 'Significative'),
            ('majeure', 'Majeure')]
GRAVITE_DEPUIS_ANOMALIE = {'critique': 'majeure', 'majeur': 'significative', 'mineur': 'mineure'}
ORDRE_GRAVITE = ['aucune', 'mineure', 'significative', 'majeure']
RESULTATS = ['Conforme', 'À améliorer', 'À corriger', 'Non conforme']          # du meilleur au pire
RESULTAT_GRAVITE = {'aucune': 'Conforme', 'mineure': 'Conforme', 'significative': 'À corriger',
                    'majeure': 'Non conforme'}


def _m():
    import models
    return models


# ---------------------------------------------------------------- réglages par organisation
SEUILS_DEFAUT = {'conforme': 95, 'ameliorer': 80, 'corriger': 60}
CLE_REGLAGES = 'c2n'


def reglages(client_id):
    """Seuils et tailles d'échantillon de l'organisation (valeurs par défaut sinon)."""
    r = {'seuils': dict(SEUILS_DEFAUT), 'echantillons': {c: v for c, _l, _f, v in ECHANTILLON}, 'personnalise': False}
    if not client_id:
        return r
    try:
        m = _m()
        conf = m.ClientConfiguration.query.filter_by(client_id=client_id).first()
        sauve = ((conf.preferences or {}).get(CLE_REGLAGES) if conf else None) or {}
        for k, v in (sauve.get('seuils') or {}).items():
            if k in r['seuils'] and isinstance(v, (int, float)):
                r['seuils'][k] = v
        for k, v in (sauve.get('echantillons') or {}).items():
            if k in r['echantillons'] and isinstance(v, int) and v > 0:
                r['echantillons'][k] = v
        r['personnalise'] = bool(sauve)
    except Exception:  # noqa: BLE001
        pass
    return r


def enregistrer_reglages(client_id, seuils, echantillons):
    m = _m()
    conf = m.ClientConfiguration.query.filter_by(client_id=client_id).first()
    if conf is None:
        conf = m.ClientConfiguration(client_id=client_id, couleurs={}, preferences={})
        m.db.session.add(conf)
    prefs = dict(conf.preferences or {})
    prefs[CLE_REGLAGES] = {'seuils': seuils, 'echantillons': echantillons}
    conf.preferences = prefs


# ---------------------------------------------------------------- méthode
def normaliser_frequence(v):
    t = (v or '').strip().lower().replace('é', 'e').replace('è', 'e')
    if t in FREQUENCES:
        return t
    return DEPUIS_DISPOSITIF.get(t)


def dispositifs(ref):
    m = _m()
    ids = [int(i) for i in (getattr(ref, 'dispositifs_ids', None) or []) if str(i).isdigit()]
    if not ids:
        return []
    return m.DispositifMaitrise.query.filter(m.DispositifMaitrise.id.in_(ids),
                                             m.DispositifMaitrise.client_id == ref.client_id).all()


def risques(ref):
    m = _m()
    ids = {int(i) for i in (getattr(ref, 'risques_ids', None) or []) if str(i).isdigit()}
    ids |= {d.risque_id for d in dispositifs(ref) if d.risque_id}
    if not ids:
        return []
    return m.Risque.query.filter(m.Risque.id.in_(ids), m.Risque.client_id == ref.client_id).all()


def frequence_execution(ref):
    """Fréquence d'exécution du contrôle : celle saisie, sinon la plus fréquente des dispositifs rattachés."""
    f = normaliser_frequence(getattr(ref, 'frequence_execution', None)) if ref is not None else None
    if f:
        return f
    candidates = [normaliser_frequence(d.frequence) for d in dispositifs(ref)] if ref is not None else []
    candidates = [c for c in candidates if c]
    return min(candidates, key=ORDRE_FREQ.index) if candidates else None


def echantillon_recommande(ref):
    """(taille proposée, fourchette, libellé de fréquence) ou (None, None, None)."""
    f = frequence_execution(ref)
    if not f:
        return None, None, None
    libelle, fourchette, valeur = FREQUENCES[f]
    valeur = reglages(getattr(ref, 'client_id', None))['echantillons'].get(f, valeur)
    return valeur, fourchette, libelle


def gravite(ex):
    """Gravité retenue : celle choisie, sinon déduite des anomalies retenues de l'exécution."""
    if ex is None:
        return None
    if getattr(ex, 'gravite_deficience', None) in ORDRE_GRAVITE:
        return ex.gravite_deficience
    m = _m()
    try:
        anomalies = m.AnomalieDetectee.query.filter(m.AnomalieDetectee.execution_id == ex.id,
                                                   m.AnomalieDetectee.statut != 'ecartee').all()
    except Exception:  # noqa: BLE001
        anomalies = []
    niveaux = [GRAVITE_DEPUIS_ANOMALIE.get((a.criticite or '').lower()) for a in anomalies]
    niveaux = [n for n in niveaux if n]
    if niveaux:
        return max(niveaux, key=ORDRE_GRAVITE.index)
    return 'aucune' if (ex.nb_anomalies or 0) == 0 else None


def taux(ex):
    if ex is None:
        return None
    if ex.taux_conformite is not None:
        return float(ex.taux_conformite)
    total = (ex.nb_conformes or 0) + (ex.nb_anomalies or 0)
    if total:
        return round(100.0 * (ex.nb_conformes or 0) / total, 1)
    return None


def resultat(pl):
    """(résultat de vérification, explication) pour l'exécution d'une planification."""
    ex = pl.execution
    g = gravite(ex)
    t = taux(ex)
    candidats, raisons = [], []
    if t is not None and pl.type_test != 'conception':
        sl = reglages(getattr(pl, 'client_id', None))['seuils']
        r = 'Conforme' if t >= sl['conforme'] else 'À améliorer' if t >= sl['ameliorer'] else \
            'À corriger' if t >= sl['corriger'] else 'Non conforme'
        candidats.append(r)
        raisons.append(f'taux de conformité {t:g} %')
    if g:
        candidats.append(RESULTAT_GRAVITE[g])
        raisons.append(f'déficience {dict(GRAVITES)[g].lower()}')
    if not candidats:
        return 'Conforme', 'aucune anomalie relevée'
    pire = max(candidats, key=RESULTATS.index)
    return pire, ', '.join(raisons)


# ---------------------------------------------------------------- effet sur la cartographie
def appliquer(pl, u):
    """À la validation : vérification « Contrôle N2 » sur chaque dispositif testé. Idempotent."""
    m = _m()
    ex, ref = pl.execution, pl.referentiel
    if ex is None or ref is None:
        return 0
    deja = ex.impact_cartographie or {}
    if deja.get('applique'):
        return 0
    from egalyx.maitrise import apres_verification
    res, pourquoi = resultat(pl)
    jour = (pl.date_validation or datetime.utcnow()).date()
    trace = {'applique': True, 'resultat': res, 'explication': pourquoi, 'le': datetime.utcnow().isoformat(),
             'par': getattr(u, 'id', None), 'dispositifs': {}}
    for d in dispositifs(ref):
        avant = d.efficacite_reelle
        v = m.VerificationDispositif(dispositif_id=d.id, date_verification=jour, type_verification='Contrôle N2',
                                     resultat=res, verificateur_id=getattr(u, 'id', None), client_id=d.client_id,
                                     commentaire=f"Contrôle N2 {pl.reference} ({ref.code_controle}) validé : {pourquoi}.")
        m.db.session.add(v)
        m.db.session.flush()
        d.date_derniere_verification = jour
        apres_verification(d, res, jour, getattr(u, 'id', None))
        trace['dispositifs'][str(d.id)] = {'avant': avant, 'apres': d.efficacite_reelle, 'verification_id': v.id}
    ex.impact_cartographie = trace
    return len(trace['dispositifs'])


def annuler(pl, u, raison=''):
    """À la réouverture : rétablit l'efficacité (si personne ne l'a changée depuis) et retire la vérification N2."""
    m = _m()
    ex = pl.execution
    trace = (ex.impact_cartographie or {}) if ex is not None else {}
    if not trace.get('applique'):
        return 0
    n = 0
    for did, t in (trace.get('dispositifs') or {}).items():
        d = m.db.session.get(m.DispositifMaitrise, int(did))
        if d is None:
            continue
        if t.get('apres') != t.get('avant') and d.efficacite_reelle == t.get('apres'):
            d.efficacite_reelle = t.get('avant')
            m.db.session.add(m.DispositifHistoriqueEfficacite(
                dispositif_id=d.id, efficacite=t.get('avant'), ancienne_efficacite=t.get('apres'), reduction=0,
                cause='verification', date_changement=datetime.utcnow(),
                commentaire=f"Contrôle N2 {pl.reference} rouvert : effet annulé. {raison}".strip()))
        v = m.db.session.get(m.VerificationDispositif, t.get('verification_id')) if t.get('verification_id') else None
        if v is not None:
            m.db.session.delete(v)
        try:
            from egalyx.maitrise import recalculer_maitrise_suggeree
            recalculer_maitrise_suggeree(d.risque_id)
        except Exception:  # noqa: BLE001
            pass
        n += 1
    ex.impact_cartographie = None
    return n


# ---------------------------------------------------------------- écrans : données et enregistrement
def choix_cartographie(ref=None):
    """Risques de l'organisation et leurs dispositifs, pour la liste de choix du référentiel."""
    m = _m()
    cid = getattr(ref, 'client_id', None) or getattr(current_user, 'client_id', None)
    if not cid:
        try:
            from egalyx.commun import client_id_courant
            cid = client_id_courant()
        except Exception:  # noqa: BLE001
            cid = None
    if not cid:
        return {'risques': [], 'choisis_r': set(), 'choisis_d': set()}
    rs = m.Risque.query.filter(m.Risque.client_id == cid, m.Risque.is_archived.isnot(True)) \
        .order_by(m.Risque.reference).all()
    ds = m.DispositifMaitrise.query.filter(m.DispositifMaitrise.client_id == cid,
                                           m.DispositifMaitrise.is_archived.isnot(True)).all()
    par_risque = {}
    for d in ds:
        par_risque.setdefault(d.risque_id, []).append(d)
    choisis_r = {int(i) for i in (getattr(ref, 'risques_ids', None) or []) if str(i).isdigit()}
    choisis_d = {int(i) for i in (getattr(ref, 'dispositifs_ids', None) or []) if str(i).isdigit()}
    if ref is not None and not choisis_r and not choisis_d and getattr(ref, 'risques_couverts', None):
        texte = ref.risques_couverts                # anciens référentiels : « [R-001] intitulé » reconnu
        choisis_r = {r.id for r in rs if r.reference and f'[{r.reference}]' in texte}
    return {'risques': [{'r': r, 'dispositifs': sorted(par_risque.get(r.id, []), key=lambda x: x.reference or '')}
                        for r in rs], 'choisis_r': choisis_r, 'choisis_d': choisis_d}


def _ids(nom):
    return sorted({int(v) for v in request.form.getlist(nom) if str(v).isdigit()})


def enregistrer_referentiel(ref):
    m = _m()
    cid = ref.client_id
    dm = [d.id for d in m.DispositifMaitrise.query.filter(m.DispositifMaitrise.id.in_(_ids('dm_ids') or [-1]),
                                                          m.DispositifMaitrise.client_id == cid).all()]
    rk = [r.id for r in m.Risque.query.filter(m.Risque.id.in_(_ids('risque_ids') or [-1]),
                                              m.Risque.client_id == cid).all()]
    ref.dispositifs_ids, ref.risques_ids = dm, rk
    f = normaliser_frequence(request.form.get('frequence_execution'))
    ref.frequence_execution = f
    if rk and not (ref.risques_couverts or '').strip():
        ref.risques_couverts = '\n'.join(f'[{r.reference}] {r.intitule}' for r in risques(ref))


def _envelopper(app, endpoint, apres):
    vue = app.view_functions.get(endpoint)
    if vue is None or getattr(vue, '_egalyx_c2n', False):
        return

    def enveloppe(*a, **k):
        reponse = vue(*a, **k)
        if request.method == 'POST' and getattr(reponse, 'status_code', 200) in (301, 302, 303):
            try:
                if apres(k):
                    _m().db.session.commit()
            except Exception as e:  # noqa: BLE001
                _m().db.session.rollback()
                flash(f'Complément N2 non enregistré : {e}', 'warning')
        return reponse
    enveloppe.__name__ = vue.__name__
    enveloppe._egalyx_c2n = True
    app.view_functions[endpoint] = enveloppe


def _apres_referentiel_nouveau(_k):
    m = _m()
    code = (request.form.get('code_controle') or '').strip().upper()
    ref = m.ReferentielControle.query.filter_by(code_controle=code, client_id=current_user.client_id) \
        .order_by(m.ReferentielControle.id.desc()).first()
    if ref is None:
        return False
    enregistrer_referentiel(ref)
    return True


def _apres_referentiel_modifier(k):
    m = _m()
    ref = m.db.session.get(m.ReferentielControle, k.get('id'))
    if ref is None or (current_user.role != 'super_admin' and ref.client_id != current_user.client_id):
        return False
    enregistrer_referentiel(ref)
    return True


def _methode_planification(pl):
    t = request.form.get('type_test')
    pl.type_test = t if t in dict((c, l) for c, l, _a in TYPES_TEST) else (pl.type_test or 'efficacite')
    v = (request.form.get('taille_echantillon') or '').strip()
    if v.isdigit():
        pl.taille_echantillon = max(1, int(v))
    elif not pl.taille_echantillon:
        pl.taille_echantillon = echantillon_recommande(pl.referentiel)[0]


def _apres_planification_nouvelle(_k):
    m = _m()
    pl = m.PlanificationControle.query.filter_by(created_by=current_user.id) \
        .order_by(m.PlanificationControle.id.desc()).first()
    if pl is None or (pl.created_at and (datetime.utcnow() - pl.created_at).total_seconds() > 120):
        return False
    _methode_planification(pl)
    return True


def _apres_planification_modifier(k):
    m = _m()
    pl = m.db.session.get(m.PlanificationControle, k.get('id'))
    if pl is None or (current_user.role != 'super_admin' and pl.client_id != current_user.client_id):
        return False
    _methode_planification(pl)
    return True


def _apres_execution(k):
    m = _m()
    pl = m.db.session.get(m.PlanificationControle, k.get('id'))
    if pl is None or pl.execution is None:
        return False
    g = request.form.get('gravite_deficience')
    pl.execution.gravite_deficience = g if g in ORDRE_GRAVITE else None
    try:                                    # volumes et anomalies : l'échantillon fait foi s'il existe
        from egalyx.c2n_echantillon import synchroniser
        synchroniser(pl.execution, pl)
    except Exception:  # noqa: BLE001
        pass
    return True


def echantillons_par_referentiel(ids):
    """{id: {taille, min, max, frequence, nb_dispositifs}} pour la page de planification (proposition dynamique)."""
    m = _m()
    out = {}
    ids = [int(i) for i in ids if str(i).isdigit() and int(i) > 0]
    for ref in (m.ReferentielControle.query.filter(m.ReferentielControle.id.in_(ids)).all() if ids else []):
        taille, fourchette, freq = echantillon_recommande(ref)
        out[ref.id] = {'taille': taille, 'min': fourchette[0] if fourchette else None,
                       'max': fourchette[1] if fourchette else None, 'frequence': freq,
                       'nb_dispositifs': len(ref.dispositifs_ids or [])}
    return out


def synthese(pl):
    """Pour les écrans et rapports : méthode, résultat attendu et effet sur la cartographie."""
    ref = pl.referentiel
    taille, fourchette, freq = echantillon_recommande(ref)
    res, pourquoi = resultat(pl) if pl.execution is not None else (None, None)
    return {'type_test': dict((c, l) for c, l, _a in TYPES_TEST).get(pl.type_test or 'efficacite'),
            'taille_retenue': pl.taille_echantillon, 'taille_recommandee': taille, 'fourchette': fourchette,
            'frequence': freq, 'gravite': dict(GRAVITES).get(gravite(pl.execution)) if pl.execution is not None else None,
            'resultat': res, 'explication': pourquoi,
            'dispositifs': dispositifs(ref) if ref is not None else [], 'risques': risques(ref) if ref is not None else [],
            'impact': (pl.execution.impact_cartographie or {}) if pl.execution is not None else {}}


def section_rapport(pl):
    """Section HTML des rapports PDF du N2 : méthode, gravité, résultat, dispositifs et effet sur la cartographie."""
    from markupsafe import escape as e
    try:
        sy = synthese(pl)
    except Exception:  # noqa: BLE001
        return ''
    lignes = [f"<tr><td style='width:38%'><strong>Type de test</strong></td><td>{e(sy['type_test'] or '—')}</td></tr>"]
    if sy['taille_retenue'] or sy['taille_recommandee']:
        rep = ''
        if sy['fourchette']:
            a, b = sy['fourchette']
            rep = f" (repère pour un contrôle {e((sy['frequence'] or '').lower())} : {a}{'' if a == b else f' à {b}'})"
        lignes.append(f"<tr><td><strong>Échantillon</strong></td><td>{sy['taille_retenue'] or sy['taille_recommandee']}{rep}</td></tr>")
    try:
        from egalyx.c2n_echantillon import resume
        ech = resume(pl)
    except Exception:  # noqa: BLE001
        ech = None
    if ech:
        t = ech['tirage'] or {}
        tir = (f" ; tirage aléatoire de {t.get('taille')} parmi {t.get('population')} (graine {t.get('graine')}, "
               f"le {str(t.get('le', ''))[:10]}, par {e(t.get('par') or '')})") if t else ' ; éléments choisis'
        lignes.append(f"<tr><td><strong>Échantillon suivi</strong></td><td>{ech['testes']} élément(s) testé(s) sur "
                      f"{ech['total']}, {ech['anomalies']} anomalie(s), {ech['preuves']} preuve(s) jointe(s){tir}</td></tr>")
    if sy['gravite']:
        lignes.append(f"<tr><td><strong>Gravité de la déficience</strong></td><td>{e(sy['gravite'])}</td></tr>")
    if sy['resultat']:
        lignes.append(f"<tr><td><strong>Conclusion sur le contrôle</strong></td><td>{e(sy['resultat'])} — {e(sy['explication'] or '')}</td></tr>")
    impact = (sy['impact'] or {}).get('dispositifs') or {}
    dm = ''
    if sy['dispositifs']:
        items = []
        for d in sy['dispositifs']:
            t = impact.get(str(d.id))
            effet = ''
            if t:
                effet = (f" : efficacité {t.get('avant')} → {t.get('apres')}" if t.get('avant') != t.get('apres')
                         else ' : efficacité inchangée') + ', prochaine vérification ' + \
                    (d.prochaine_verification.strftime('%d/%m/%Y') if d.prochaine_verification else '—')
            items.append(f"<li>{e(d.reference)} · {e(d.nom)}{effet}</li>")
        dm = ("<p style='margin:10px 0 4px'><strong>Dispositifs de maîtrise testés"
              + (" (cartographie mise à jour à la validation)" if impact else " (mis à jour à la validation)")
              + "</strong></p><ul style='margin:0'>" + ''.join(items) + "</ul>")
    rk = ''
    if sy['risques']:
        rk = ("<p style='margin:10px 0 4px'><strong>Risques couverts</strong></p><ul style='margin:0'>"
              + ''.join(f"<li>{e(r.reference)} · {e(r.intitule)}</li>" for r in sy['risques']) + "</ul>")
    return ("<div class='section'><div class='section-title'>🧪 MÉTHODE DE TEST ET EFFET SUR LA CARTOGRAPHIE</div>"
            "<table style='width:100%;border-collapse:collapse' cellpadding='6'>" + ''.join(lignes) + "</table>"
            + dm + rk + "</div>")


def peut_regler(u=None):
    u = u or current_user
    if not getattr(u, 'is_authenticated', False):
        return False
    if getattr(u, 'role', None) in ('super_admin', 'admin') or getattr(u, 'is_client_admin', False):
        return True
    try:
        return bool(u.has_permission('can_manage_controle_interne_n2'))
    except Exception:  # noqa: BLE001
        return False


@bp.route('/', methods=['GET', 'POST'])
def page():
    from egalyx.commun import client_id_courant, journaliser
    if not peut_regler():
        abort(403)
    cid = client_id_courant()
    if not cid:
        abort(404)
    if request.method == 'POST':
        if request.form.get('action') == 'defaut':
            enregistrer_reglages(cid, dict(SEUILS_DEFAUT), {c: v for c, _l, _f, v in ECHANTILLON})
            m = _m()
            conf = m.ClientConfiguration.query.filter_by(client_id=cid).first()
            prefs = dict(conf.preferences or {})
            prefs.pop(CLE_REGLAGES, None)
            conf.preferences = prefs
            journaliser('c2n_reglages_defaut', {}, client_id=cid)
            m.db.session.commit()
            flash('Valeurs par défaut rétablies.', 'success')
            return redirect(url_for('.page', client_id=cid if current_user.role == 'super_admin' else None))
        try:
            seuils = {k: float(request.form.get('seuil_' + k, '').replace(',', '.')) for k in SEUILS_DEFAUT}
        except ValueError:
            flash('Seuils invalides : saisissez des pourcentages.', 'danger')
            return redirect(url_for('.page'))
        if not (0 < seuils['corriger'] < seuils['ameliorer'] < seuils['conforme'] <= 100):
            flash('Les seuils doivent être croissants : « à corriger » < « à améliorer » < « conforme » ≤ 100 %.', 'danger')
            return redirect(url_for('.page'))
        seuils = {k: int(v) if float(v).is_integer() else v for k, v in seuils.items()}
        ech = {}
        for c, _l, _f, v in ECHANTILLON:
            brut = (request.form.get('ech_' + c) or '').strip()
            ech[c] = max(1, min(1000, int(brut))) if brut.isdigit() else v
        enregistrer_reglages(cid, seuils, ech)
        journaliser('c2n_reglages', {'seuils': seuils, 'echantillons': ech}, client_id=cid)
        _m().db.session.commit()
        flash('Réglages du contrôle N2 enregistrés : ils s\'appliquent aux prochaines validations.', 'success')
        return redirect(url_for('.page', client_id=cid if current_user.role == 'super_admin' else None))
    return render_template('egalyx/c2n_reglages.html', r=reglages(cid), echantillon=ECHANTILLON, defaut=SEUILS_DEFAUT)


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    app.register_blueprint(bp)
    exempter_controle_ancien(app, {'c2n_reglages.page'})
    app.jinja_env.globals['c2n_peut_regler'] = peut_regler
    _envelopper(app, 'c2n_nouveau_referentiel', _apres_referentiel_nouveau)
    _envelopper(app, 'c2n_modifier_referentiel', _apres_referentiel_modifier)
    _envelopper(app, 'c2n_nouvelle_planification', _apres_planification_nouvelle)
    _envelopper(app, 'c2n_modifier_planification', _apres_planification_modifier)
    _envelopper(app, 'c2n_executer_planification', _apres_execution)
    app.jinja_env.globals.update(
        c2n_choix_cartographie=choix_cartographie, c2n_echantillon=echantillon_recommande, c2n_synthese=synthese,
        c2n_types_test=TYPES_TEST, c2n_gravites=GRAVITES, c2n_frequences=ECHANTILLON,
        c2n_frequence_execution=frequence_execution, c2n_echantillons_par_referentiel=echantillons_par_referentiel,
        c2n_section_rapport=section_rapport)
