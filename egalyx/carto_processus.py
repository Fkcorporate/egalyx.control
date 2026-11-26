"""
egalyx/carto_processus.py — cartographie des processus (carte de type ISO 9001 : pilotage / réalisation / support).

Module « sur activation » : fermé tant que le super admin ne l'a pas coché pour le client
(page Super admin > client > Modules ; voir egalyx/modules_client.SUR_ACTIVATION).

  - La carte se construit à partir du référentiel des processus métier (models.ProcessusMetier) : pas de
    double saisie. Type « stratégique » -> pilotage, « métier » -> réalisation, « support » -> support,
    « réglementaire » -> bande conformité (masquée si vide). Les sous-processus s'affichent dans leur parent.
  - Trois lectures : simple, risques (niveau du risque le plus élevé rattaché au processus), couverture d'audit
    (date du dernier audit, recommandations ouvertes).
  - Interactions entre processus (flèches « A alimente B : données… »), ordre et bande de chaque processus,
    libellés de la carte : réglages de l'organisation, gardés dans ClientConfiguration.preferences['carto_processus']
    (pas de nouvelle table).
  - Processus ajoutés / modifiés ici = les mêmes que dans « Processus métier » (module Processus), le module
    fonctionne donc seul. Modèles types (générique, banque, industrie / mines) pour démarrer.
  - Droits : can_view_carto_processus (voir), can_manage_carto_processus (organiser) ; les administrateurs de
    l'organisation ont les deux dès que le module est activé.
"""
import re
import unicodedata
import uuid
from datetime import date, datetime

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from egalyx.commun import client_id_courant, est_super_admin, journaliser, nom_personne

bp = Blueprint('carto_processus', __name__, url_prefix='/carte-processus')
CODE_MODULE = 'carto_processus'
CLE = 'carto_processus'

# bande -> (type ProcessusMetier, libellé par défaut)
BANDES = [
    ('pilotage', 'strategique', 'Processus de pilotage'),
    ('realisation', 'metier', 'Processus de réalisation'),
    ('support', 'support', 'Processus support'),
    ('reglementaire', 'reglementaire', 'Processus de conformité'),
]
TYPE_DE_BANDE = {b: t for b, t, _l in BANDES}
BANDE_DU_TYPE = {t: b for b, t, _l in BANDES}

DEFAUT = {
    'titre': 'Cartographie des processus',
    'entree': 'Besoins et exigences des clients et parties intéressées',
    'sortie': 'Satisfaction des clients et parties intéressées',
    'bandes': {b: l for b, _t, l in BANDES},
    'sous_processus': True,
    'ordre': {},          # {bande: [id, …]}
    'flux': [],           # [{'id', 'de', 'vers', 'libelle'}]
}
LONGUEUR = {'titre': 120, 'entree': 140, 'sortie': 140, 'bande': 60, 'flux': 80}

# Modèles pour démarrer : (bande, code, nom, [sous-processus])
MODELES = {
    'generique': ('Organisation (modèle ISO 9001)', [
        ('pilotage', 'PIL-01', 'Stratégie et pilotage', ['Planification stratégique', 'Revue de direction']),
        ('pilotage', 'PIL-02', 'Management des risques et du contrôle interne', ['Cartographie des risques', 'Contrôle interne']),
        ('pilotage', 'PIL-03', 'Amélioration continue et audit interne', []),
        ('realisation', 'REA-01', 'Commercial et relation client', ['Prospection', 'Contractualisation']),
        ('realisation', 'REA-02', 'Achats et approvisionnements', []),
        ('realisation', 'REA-03', 'Production / réalisation de la prestation', []),
        ('realisation', 'REA-04', 'Livraison et service après-vente', []),
        ('support', 'SUP-01', 'Ressources humaines', ['Recrutement', 'Formation', 'Paie']),
        ('support', 'SUP-02', 'Finance et comptabilité', []),
        ('support', 'SUP-03', "Systèmes d'information", []),
        ('support', 'SUP-04', 'Juridique', []),
        ('support', 'SUP-05', 'Moyens généraux et logistique', []),
    ]),
    'banque': ('Banque / microfinance', [
        ('pilotage', 'PIL-01', 'Gouvernance et stratégie', ['Conseil d’administration', 'Comités']),
        ('pilotage', 'PIL-02', 'Gestion des risques', ['Risque de crédit', 'Risques opérationnels', 'Risque de liquidité']),
        ('pilotage', 'PIL-03', 'Conformité et LCB-FT', []),
        ('pilotage', 'PIL-04', 'Contrôle permanent et audit interne', []),
        ('realisation', 'REA-01', 'Entrée en relation et KYC', []),
        ('realisation', 'REA-02', 'Collecte de l’épargne et dépôts', []),
        ('realisation', 'REA-03', 'Octroi et gestion des crédits', ['Instruction', 'Décaissement', 'Recouvrement']),
        ('realisation', 'REA-04', 'Moyens de paiement et transferts', []),
        ('realisation', 'REA-05', 'Trésorerie et marchés', []),
        ('support', 'SUP-01', 'Ressources humaines', []),
        ('support', 'SUP-02', 'Comptabilité et reporting réglementaire', []),
        ('support', 'SUP-03', "Systèmes d'information et sécurité", []),
        ('support', 'SUP-04', 'Juridique et contentieux', []),
        ('support', 'SUP-05', 'Achats et moyens généraux', []),
    ]),
    'industrie': ('Industrie / mines', [
        ('pilotage', 'PIL-01', 'Direction générale et stratégie', []),
        ('pilotage', 'PIL-02', 'Hygiène, sécurité, environnement (HSE)', []),
        ('pilotage', 'PIL-03', 'Qualité, risques et audit interne', []),
        ('realisation', 'REA-01', 'Exploration et études', []),
        ('realisation', 'REA-02', 'Exploitation et production', ['Extraction', 'Traitement']),
        ('realisation', 'REA-03', 'Maintenance des installations', []),
        ('realisation', 'REA-04', 'Ventes et expéditions', []),
        ('support', 'SUP-01', 'Achats et logistique', []),
        ('support', 'SUP-02', 'Ressources humaines', []),
        ('support', 'SUP-03', 'Finance et comptabilité', []),
        ('support', 'SUP-04', "Systèmes d'information", []),
        ('support', 'SUP-05', 'Juridique, foncier et relations communautaires', []),
    ]),
}


def _m():
    import models
    return models


# ------------------------------------------------------------------ droits
def _module_actif(cid):
    from egalyx.modules_client import module_sur_activation_actif
    m = _m()
    client = m.db.session.get(m.Client, cid) if cid else None
    return module_sur_activation_actif(client, CODE_MODULE)


def _est_admin_org(u):
    return getattr(u, 'role', None) == 'admin' or bool(getattr(u, 'is_client_admin', False))


def peut_voir(u=None):
    u = u or current_user
    if not getattr(u, 'is_authenticated', False):
        return False
    if est_super_admin(u):
        return True
    if not _module_actif(getattr(u, 'client_id', None)):
        return False
    return _est_admin_org(u) or u.has_permission('can_view_carto_processus') or u.has_permission('can_manage_carto_processus')


def peut_gerer(u=None):
    u = u or current_user
    if not getattr(u, 'is_authenticated', False):
        return False
    if est_super_admin(u):
        return True
    if not _module_actif(getattr(u, 'client_id', None)):
        return False
    return _est_admin_org(u) or u.has_permission('can_manage_carto_processus')


def _cid_ou_404():
    cid = client_id_courant()
    if not cid and est_super_admin():
        flash("Choisissez d'abord l'organisation à consulter.", 'info')
        abort(redirect(url_for('super_admin_clients')))
    if not cid:
        abort(404)
    if est_super_admin() and not _module_actif(cid):
        # le super admin peut regarder, mais on lui rappelle que le client ne la voit pas
        flash("Ce module n'est pas activé pour cette organisation : ses utilisateurs ne voient pas cette page.", 'info')
    return cid


# ------------------------------------------------------------------ réglages
def _texte(v, n, defaut=''):
    v = re.sub(r'\s+', ' ', str(v or '')).strip()
    return v[:n] if v else defaut


def normaliser(brut):
    brut = brut if isinstance(brut, dict) else {}
    r = {
        'titre': _texte(brut.get('titre'), LONGUEUR['titre'], DEFAUT['titre']),
        'entree': _texte(brut.get('entree'), LONGUEUR['entree'], DEFAUT['entree']),
        'sortie': _texte(brut.get('sortie'), LONGUEUR['sortie'], DEFAUT['sortie']),
        'bandes': {b: _texte((brut.get('bandes') or {}).get(b), LONGUEUR['bande'], l) for b, _t, l in BANDES},
        'sous_processus': brut.get('sous_processus', True) is not False,
        'ordre': {}, 'flux': [],
    }
    for b, ids in (brut.get('ordre') or {}).items():
        if b in TYPE_DE_BANDE and isinstance(ids, list):
            r['ordre'][b] = [int(i) for i in ids if str(i).isdigit()]
    for f in brut.get('flux') or []:
        try:
            de, vers = int(f.get('de')), int(f.get('vers'))
        except (TypeError, ValueError, AttributeError):
            continue
        if de != vers:
            r['flux'].append({'id': str(f.get('id') or uuid.uuid4().hex[:10])[:16], 'de': de, 'vers': vers,
                              'libelle': _texte(f.get('libelle'), LONGUEUR['flux'])})
    return r


def _conf(cid, creer=False):
    m = _m()
    conf = m.ClientConfiguration.query.filter_by(client_id=cid).first()
    if conf is None and creer:
        conf = m.ClientConfiguration(client_id=cid, couleurs={}, preferences={})
        m.db.session.add(conf)
    return conf


def lire(cid):
    conf = _conf(cid)
    return normaliser(((conf.preferences or {}).get(CLE) if conf else None) or {})


def ecrire(cid, r):
    conf = _conf(cid, creer=True)
    prefs = dict(conf.preferences or {})
    prefs[CLE] = normaliser(r)
    conf.preferences = prefs
    try:
        from models import marquer_json_modifie
        marquer_json_modifie(conf, 'preferences')
    except Exception:  # noqa: BLE001
        pass


# ------------------------------------------------------------------ données de la carte
def _sans_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', (s or '').lower()) if unicodedata.category(c) != 'Mn')


def rang_niveau(niveau):
    """Niveau de risque (texte libre selon les paramètres du client) -> 0 inconnu, 1 faible … 4 critique."""
    n = _sans_accents(niveau)
    if not n:
        return 0
    if 'crit' in n or 'extreme' in n or 'inaccept' in n:
        return 4
    if 'eleve' in n or 'fort' in n or 'haut' in n or 'majeur' in n or 'important' in n:
        return 3
    if 'moy' in n or 'modere' in n or 'significatif' in n:
        return 2
    if 'faib' in n or 'bas' in n or 'mineur' in n or 'negligeable' in n:
        return 1
    return 0


NIVEAUX = {0: ('Non évalué', 'secondary'), 1: ('Faible', 'success'), 2: ('Moyen', 'warning'), 3: ('Élevé', 'orange'), 4: ('Critique', 'danger')}
STATUTS_RECO_CLOS = {'termine', 'terminee', 'cloture', 'cloturee', 'clos', 'close', 'abandonne', 'abandonnee', 'realise', 'realisee'}


def _date_audit(a):
    return a.date_fin_reelle or a.date_fin_prevue or a.date_debut_reelle or a.date_debut_prevue or (
        a.created_at.date() if getattr(a, 'created_at', None) else None)


def couverture(derniere, aujourdhui=None):
    """Couverture d'audit d'un processus : (code, libellé)."""
    if derniere is None:
        return 'jamais', 'Jamais audité'
    mois = ((aujourdhui or date.today()) - derniere).days / 30.4
    if mois <= 12:
        return 'recent', 'Audité il y a moins de 12 mois'
    if mois <= 36:
        return 'ancien', 'Audité il y a 1 à 3 ans'
    return 'tres_ancien', 'Audité il y a plus de 3 ans'


def donnees(cid, r=None):
    """Tout ce qu'il faut pour dessiner la carte d'une organisation."""
    m = _m()
    r = r or lire(cid)
    tous = m.ProcessusMetier.query.filter_by(client_id=cid, is_archived=False).all()
    actifs = [p for p in tous if p.est_actif is not False]
    par_id = {p.id: p for p in actifs}
    racines = [p for p in actifs if not p.parent_id or p.parent_id not in par_id]
    enfants = {}
    for p in actifs:
        if p.parent_id in par_id:
            enfants.setdefault(p.parent_id, []).append(p)

    def famille(p):
        ids = [p.id]
        for e in enfants.get(p.id, []):
            ids += famille(e)
        return ids

    # risques rattachés (référentiel) ou désignés par le nom du processus
    risques = m.Risque.query.filter_by(client_id=cid, is_archived=False).all()
    nom_vers_id = {_sans_accents(p.nom): p.id for p in actifs}
    risques_de = {}
    for rq in risques:
        pid = getattr(rq, 'processus_metier_associe_id', None)
        if pid not in par_id:
            pid = nom_vers_id.get(_sans_accents(getattr(rq, 'processus_concerne', None)))
        if pid in par_id:
            risques_de.setdefault(pid, []).append(rq)

    audits = m.Audit.query.filter_by(client_id=cid).filter(m.Audit.is_archived.isnot(True)).all()
    logi_vers_id = {p.logigramme_id: p.id for p in actifs if p.logigramme_id}
    audits_de = {}
    for a in audits:
        pid = logi_vers_id.get(a.processus_id) if a.processus_id else None
        if pid is None:
            pid = nom_vers_id.get(_sans_accents(a.processus_concerne))
        if pid in par_id:
            audits_de.setdefault(pid, []).append(a)
    ids_audits = [a.id for lst in audits_de.values() for a in lst]
    recos_ouvertes = {}
    if ids_audits:
        for rec in m.Recommandation.query.filter(m.Recommandation.audit_id.in_(ids_audits)).all():
            if _sans_accents(rec.statut).replace(' ', '_') not in STATUTS_RECO_CLOS:
                recos_ouvertes[rec.audit_id] = recos_ouvertes.get(rec.audit_id, 0) + 1

    def fiche(p):
        fam = famille(p)
        rqs = [x for i in fam for x in risques_de.get(i, [])]
        rangs = [rang_niveau(getattr(x, 'dernier_niveau_risque', None)) for x in rqs]
        pire = max(rangs) if rangs else 0
        auds = sorted([a for i in fam for a in audits_de.get(i, [])], key=lambda a: _date_audit(a) or date.min, reverse=True)
        dernier = next((_date_audit(a) for a in auds if a.statut in ('termine', 'cloture', 'clos', 'en_cours', 'rapport')
                        or a.date_fin_reelle), None)
        cov, cov_lib = couverture(dernier)
        return {
            'id': p.id, 'code': p.code or p.reference, 'reference': p.reference, 'nom': p.nom,
            'description': (p.description or '')[:600],
            'proprietaire': nom_personne(p.proprietaire),
            'proprietaire_id': p.proprietaire_id, 'type': p.type_processus, 'parent_id': p.parent_id,
            'directions': [d.nom for d in (p.directions or [])][:6] if hasattr(p, 'directions') else [],
            'enfants': [{'id': e.id, 'nom': e.nom, 'code': e.code or e.reference} for e in sorted(enfants.get(p.id, []), key=lambda e: (e.code or e.reference or '', e.nom))],
            'nb_risques': len(rqs), 'niveau': pire, 'niveau_lib': NIVEAUX[pire][0],
            'risques': [{'ref': x.reference, 'intitule': (x.intitule or '')[:120], 'niveau': rang_niveau(getattr(x, 'dernier_niveau_risque', None)),
                         'niveau_lib': getattr(x, 'dernier_niveau_risque', None) or 'Non évalué'}
                        for x in sorted(rqs, key=lambda x: -rang_niveau(getattr(x, 'dernier_niveau_risque', None)))[:6]],
            'nb_audits': len(auds), 'dernier_audit': dernier.strftime('%d/%m/%Y') if dernier else '',
            'couverture': cov, 'couverture_lib': cov_lib,
            'recos_ouvertes': sum(recos_ouvertes.get(a.id, 0) for a in auds),
            'audits': [{'ref': a.reference, 'titre': (a.titre or '')[:90], 'date': (_date_audit(a).strftime('%d/%m/%Y') if _date_audit(a) else ''),
                        'statut': a.statut or ''} for a in auds[:4]],
            'logigramme': bool(p.logigramme_id), 'logigramme_id': p.logigramme_id,
        }

    bandes = {b: [] for b, _t, _l in BANDES}
    for p in racines:
        bandes[BANDE_DU_TYPE.get(p.type_processus, 'realisation')].append(p)
    rangs = {b: {pid: i for i, pid in enumerate(r['ordre'].get(b, []))} for b in bandes}
    sortie = {}
    for b, lst in bandes.items():
        lst.sort(key=lambda p: (rangs[b].get(p.id, 10_000), p.code or p.reference or '', p.nom))
        sortie[b] = [fiche(p) for p in lst]
    visibles = {f['id'] for lst in sortie.values() for f in lst}
    # une interaction vers un sous-processus est rattachée à son processus de 1er niveau sur la carte
    def racine(pid):
        vus = set()
        while pid in par_id and par_id[pid].parent_id in par_id and pid not in vus:
            vus.add(pid)
            pid = par_id[pid].parent_id
        return pid
    flux = []
    for f in r['flux']:
        de, vers = racine(f['de']), racine(f['vers'])
        if de in visibles and vers in visibles and de != vers:
            flux.append({**f, 'de_carte': de, 'vers_carte': vers,
                         'de_nom': par_id[f['de']].nom, 'vers_nom': par_id[f['vers']].nom})
    tous_tri = sorted(actifs, key=lambda p: (p.code or p.reference or '', p.nom))
    stats = {
        'processus': len(actifs), 'premier_niveau': len(racines),
        'sans_proprietaire': sum(1 for p in racines if not p.proprietaire_id),
        'sans_risque': sum(1 for lst in sortie.values() for f in lst if not f['nb_risques']),
        'jamais_audites': sum(1 for lst in sortie.values() for f in lst if f['couverture'] == 'jamais'),
    }
    return {'bandes': sortie, 'flux': flux, 'stats': stats,
            'liste': [{'id': p.id, 'nom': p.nom, 'code': p.code or p.reference, 'parent_id': p.parent_id,
                       'type': p.type_processus} for p in tous_tri]}


# ------------------------------------------------------------------ écriture des processus
def _prochaine_reference(cid):
    m = _m()
    nums = [int(x.group(1)) for (ref,) in m.db.session.query(m.ProcessusMetier.reference).filter_by(client_id=cid).all()
            for x in [re.match(r'PROC-(\d+)$', ref or '')] if x]
    n = max(nums, default=0) + 1
    while m.ProcessusMetier.query.filter_by(client_id=cid, reference=f'PROC-{n:04d}').first():
        n += 1
    return f'PROC-{n:04d}'


def _code_libre(cid, code, sauf_id=None):
    if not code:
        return None
    m = _m()
    q = m.ProcessusMetier.query.filter_by(client_id=cid, code=code)
    if sauf_id:
        q = q.filter(m.ProcessusMetier.id != sauf_id)
    return code if q.first() is None else None


def creer_processus(cid, nom, type_processus='metier', code=None, parent_id=None, proprietaire_id=None, description=None):
    m = _m()
    p = m.ProcessusMetier(client_id=cid, reference=_prochaine_reference(cid), nom=nom[:200], code=_code_libre(cid, (code or '')[:50]),
                          type_processus=type_processus if type_processus in BANDE_DU_TYPE else 'metier',
                          parent_id=parent_id, proprietaire_id=proprietaire_id, description=description, est_actif=True,
                          is_archived=False, created_by=getattr(current_user, 'id', None))
    m.db.session.add(p)
    m.db.session.flush()
    return p


def _processus_du_client(cid, pid):
    m = _m()
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    return m.ProcessusMetier.query.filter_by(id=pid, client_id=cid, is_archived=False).first()


def _utilisateur_du_client(cid, uid):
    m = _m()
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return None
    return m.User.query.filter_by(id=uid, client_id=cid).first() if uid else None


def _cree_un_cycle(p, parent):
    vus, x = set(), parent
    while x is not None and x.id not in vus:
        if x.id == p.id:
            return True
        vus.add(x.id)
        x = x.parent
    return False


# ------------------------------------------------------------------ pages
def _contexte(cid, impression=False):
    m = _m()
    r = lire(cid)
    d = donnees(cid, r)
    vue = request.args.get('vue') if request.args.get('vue') in ('simple', 'risques', 'audit') else 'simple'
    utilisateurs = m.User.query.filter_by(client_id=cid, is_active=True).order_by(m.User.username).all() if peut_gerer() else []
    try:
        from egalyx.modules_client import modules_du_client
        actifs = modules_du_client(m.db.session.get(m.Client, cid))
        fiche_processus = (actifs is None or 'processus' in actifs) and (est_super_admin() or current_user.has_permission('can_manage_logigram'))
    except Exception:  # noqa: BLE001
        fiche_processus = False
    client = m.db.session.get(m.Client, cid)
    return dict(r=r, d=d, vue=vue, bandes=BANDES, niveaux=NIVEAUX, gerer=peut_gerer(), utilisateurs=utilisateurs,
                modeles=MODELES, fiche_processus=fiche_processus, impression=impression,
                organisation=client.nom if client else '', aujourdhui=datetime.now().strftime('%d/%m/%Y'),
                cid_param={'client_id': cid} if est_super_admin() else {})


@bp.route('/')
@login_required
def page():
    if not peut_voir():
        abort(403)
    cid = _cid_ou_404()
    return render_template('egalyx/carto_processus.html', **_contexte(cid))


@bp.route('/imprimer')
@login_required
def imprimer():
    if not peut_voir():
        abort(403)
    cid = _cid_ou_404()
    return render_template('egalyx/carto_processus_imprimer.html', **_contexte(cid, impression=True))


def _retour(cid, **kw):
    if est_super_admin():
        kw['client_id'] = cid
    return redirect(url_for('.page', **kw))


def _gestion():
    if not peut_gerer():
        abort(403)
    cid = client_id_courant()
    if not cid:
        abort(404)
    return cid


@bp.route('/reglages', methods=['POST'])
@login_required
def reglages():
    cid = _gestion()
    r = lire(cid)
    f = request.form
    r.update({'titre': f.get('titre'), 'entree': f.get('entree'), 'sortie': f.get('sortie'),
              'sous_processus': f.get('sous_processus') == '1',
              'bandes': {b: f.get(f'bande_{b}') for b, _t, _l in BANDES}})
    ecrire(cid, r)
    journaliser('carto_processus_reglages', {'titre': lire(cid)['titre']}, client_id=cid)
    _m().db.session.commit()
    flash('Réglages de la carte enregistrés.', 'success')
    return _retour(cid)


@bp.route('/organiser', methods=['POST'])
@login_required
def organiser():
    """Ordre et bande des processus de 1er niveau après glisser-déposer : {"bandes": {"pilotage": [ids], …}}."""
    cid = _gestion()
    m = _m()
    corps = request.get_json(silent=True) or {}
    bandes = corps.get('bandes') if isinstance(corps.get('bandes'), dict) else {}
    r = lire(cid)
    ordre, changes = {}, 0
    for b, ids in bandes.items():
        if b not in TYPE_DE_BANDE or not isinstance(ids, list):
            continue
        ordre[b] = []
        for pid in ids:
            p = _processus_du_client(cid, pid)
            if p is None:
                continue
            ordre[b].append(p.id)
            if p.type_processus != TYPE_DE_BANDE[b]:
                p.type_processus = TYPE_DE_BANDE[b]
                for e in m.ProcessusMetier.query.filter_by(parent_id=p.id, client_id=cid).all():
                    e.type_processus = TYPE_DE_BANDE[b]
                changes += 1
    r['ordre'] = ordre
    ecrire(cid, r)
    journaliser('carto_processus_organisation', {'changements_de_bande': changes}, client_id=cid)
    m.db.session.commit()
    return jsonify({'success': True, 'changements': changes})


@bp.route('/processus', methods=['POST'])
@login_required
def enregistrer_processus():
    """Ajout ou modification d'un processus depuis la carte (mêmes processus que « Processus métier »)."""
    cid = _gestion()
    m = _m()
    f = request.form
    nom = _texte(f.get('nom'), 200)
    if not nom:
        flash('Le nom du processus est obligatoire.', 'warning')
        return _retour(cid)
    bande = f.get('bande') if f.get('bande') in TYPE_DE_BANDE else 'realisation'
    parent = _processus_du_client(cid, f.get('parent_id')) if f.get('parent_id') else None
    prop = _utilisateur_du_client(cid, f.get('proprietaire_id'))
    code = _texte(f.get('code'), 50)
    if f.get('id'):
        p = _processus_du_client(cid, f.get('id'))
        if p is None:
            abort(404)
        if parent is not None and _cree_un_cycle(p, parent):
            flash('Un processus ne peut pas être rangé sous lui-même ou sous un de ses sous-processus.', 'warning')
            return _retour(cid)
        if code and code != p.code and not _code_libre(cid, code, p.id):
            flash(f'Le code « {code} » est déjà utilisé par un autre processus.', 'warning')
            return _retour(cid)
        p.nom, p.code = nom, code or None
        p.description = _texte(f.get('description'), 2000) or None
        p.parent_id = parent.id if parent else None
        p.proprietaire_id = prop.id if prop else None
        p.type_processus = parent.type_processus if parent else TYPE_DE_BANDE[bande]
        action, msg = 'carto_processus_modifie', f'Processus « {nom} » mis à jour.'
    else:
        if code and not _code_libre(cid, code):
            flash(f'Le code « {code} » est déjà utilisé par un autre processus.', 'warning')
            return _retour(cid)
        if m.ProcessusMetier.query.filter_by(client_id=cid, nom=nom, is_archived=False).first():
            flash(f'Un processus « {nom} » existe déjà.', 'warning')
            return _retour(cid)
        p = creer_processus(cid, nom, parent.type_processus if parent else TYPE_DE_BANDE[bande], code,
                            parent.id if parent else None, prop.id if prop else None, _texte(f.get('description'), 2000) or None)
        action, msg = 'carto_processus_cree', f'Processus « {nom} » ajouté à la carte.'
    journaliser(action, {'processus': p.id, 'nom': nom}, client_id=cid)
    m.db.session.commit()
    flash(msg, 'success')
    return _retour(cid)


@bp.route('/processus/<int:pid>/retirer', methods=['POST'])
@login_required
def retirer_processus(pid):
    """Archive le processus (et ses sous-processus) : il disparaît de la carte, ses risques et audits restent."""
    cid = _gestion()
    m = _m()
    p = _processus_du_client(cid, pid)
    if p is None:
        abort(404)
    a_archiver, pile = [], [p]
    while pile:
        x = pile.pop()
        a_archiver.append(x)
        pile += m.ProcessusMetier.query.filter_by(parent_id=x.id, client_id=cid, is_archived=False).all()
    for x in a_archiver:
        x.is_archived = True
    journaliser('carto_processus_archive', {'processus': p.id, 'nom': p.nom, 'nb': len(a_archiver)}, client_id=cid)
    m.db.session.commit()
    flash(f'« {p.nom} » retiré de la carte ({len(a_archiver)} processus archivé(s), restaurables depuis « Processus métier »).', 'success')
    return _retour(cid)


@bp.route('/interactions', methods=['POST'])
@login_required
def ajouter_interaction():
    cid = _gestion()
    de = _processus_du_client(cid, request.form.get('de'))
    vers = _processus_du_client(cid, request.form.get('vers'))
    if de is None or vers is None or de.id == vers.id:
        flash('Choisissez deux processus différents.', 'warning')
        return _retour(cid)
    r = lire(cid)
    libelle = _texte(request.form.get('libelle'), LONGUEUR['flux'])
    if any(f['de'] == de.id and f['vers'] == vers.id and f['libelle'] == libelle for f in r['flux']):
        flash('Cette interaction existe déjà.', 'info')
        return _retour(cid)
    r['flux'].append({'id': uuid.uuid4().hex[:10], 'de': de.id, 'vers': vers.id, 'libelle': libelle})
    ecrire(cid, r)
    journaliser('carto_processus_interaction', {'de': de.id, 'vers': vers.id, 'libelle': libelle}, client_id=cid)
    _m().db.session.commit()
    flash(f'Interaction ajoutée : {de.nom} → {vers.nom}.', 'success')
    return _retour(cid, interactions=1)


@bp.route('/interactions/<fid>/supprimer', methods=['POST'])
@login_required
def supprimer_interaction(fid):
    cid = _gestion()
    r = lire(cid)
    avant = len(r['flux'])
    r['flux'] = [f for f in r['flux'] if f['id'] != fid]
    if len(r['flux']) != avant:
        ecrire(cid, r)
        journaliser('carto_processus_interaction_supprimee', {'id': fid}, client_id=cid)
        _m().db.session.commit()
        flash('Interaction supprimée.', 'success')
    return _retour(cid, interactions=1)


@bp.route('/modele', methods=['POST'])
@login_required
def appliquer_modele():
    """Crée les processus d'un modèle type (ceux dont le nom existe déjà sont gardés tels quels)."""
    cid = _gestion()
    m = _m()
    code = request.form.get('modele')
    if code not in MODELES:
        abort(400)
    existants = {_sans_accents(p.nom) for p in m.ProcessusMetier.query.filter_by(client_id=cid, is_archived=False).all()}
    n = 0
    for bande, pcode, nom, sous in MODELES[code][1]:
        if _sans_accents(nom) in existants:
            continue
        p = creer_processus(cid, nom, TYPE_DE_BANDE[bande], pcode)
        existants.add(_sans_accents(nom))
        n += 1
        for i, s in enumerate(sous, 1):
            if _sans_accents(s) not in existants:
                creer_processus(cid, s, TYPE_DE_BANDE[bande], f'{pcode}.{i}', p.id)
                existants.add(_sans_accents(s))
                n += 1
    journaliser('carto_processus_modele', {'modele': code, 'crees': n}, client_id=cid)
    m.db.session.commit()
    flash(f'Modèle « {MODELES[code][0]} » : {n} processus créé(s). Renommez, déplacez ou retirez-les librement.', 'success')
    return _retour(cid)


def enregistrer(app):
    if 'carto_processus' not in app.blueprints:
        app.register_blueprint(bp)
    app.jinja_env.globals['carto_processus_visible'] = peut_voir
