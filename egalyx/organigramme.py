"""
egalyx/organigramme.py — éditeur graphique de l'organigramme d'un processus.

  GET  /processus/<id>/organigramme/editer   éditeur (glisser-déposer, liens, ajout d'étapes)
  POST /api/processus/<id>/organigramme       enregistrement (JSON)

Le format JSON envoyé :
  {"etapes": [{"id": 12 | "n1", "nom": "...", "x": 40, "y": 80, "largeur": 140, "hauteur": 60,
               "couleur": "#1A3C6B", "type": "action|decision|debut|fin"}],
   "liens":  [{"source": 12 | "n1", "cible": 13, "label": "oui"}]}
Les étapes existantes absentes de la liste ne sont PAS supprimées (suppression = fiche processus).
Les liens envoyés remplacent ceux du processus.
"""
import re
from datetime import datetime

from flask import Blueprint, abort, jsonify, render_template, request
from egalyx.commun import client_id_courant, est_super_admin, journaliser, permission_requise

bp = Blueprint('organigramme_editeur', __name__)

TYPES = ('action', 'decision', 'debut', 'fin')
COULEUR = re.compile(r'^#[0-9a-fA-F]{6}$')
MAX_ETAPES = 300


def _processus(pid):
    from models import Processus
    p = Processus.query.get(pid)
    if not p or (not est_super_admin() and p.client_id != client_id_courant()):
        abort(404)
    return p


def _borne(v, mini, maxi, defaut):
    try:
        return max(mini, min(maxi, int(round(float(v)))))
    except (TypeError, ValueError):
        return defaut


def donnees(p):
    from models import EtapeProcessus, LienProcessus
    etapes = EtapeProcessus.query.filter_by(processus_id=p.id).order_by(EtapeProcessus.ordre).all()
    liens = LienProcessus.query.filter_by(processus_id=p.id).all()
    return {
        'etapes': [{'id': e.id, 'ordre': e.ordre, 'nom': e.nom, 'x': e.position_x or 0, 'y': e.position_y or 0,
                    'largeur': e.largeur or 140, 'hauteur': e.hauteur or 60, 'couleur': e.couleur or '#1A3C6B',
                    'type': e.type_etape if e.type_etape in TYPES else 'action'} for e in etapes
                   if not getattr(e, 'is_archived', False)],
        'liens': [{'source': l.etape_source_id, 'cible': l.etape_cible_id, 'label': l.label or ''}
                  for l in liens if l.etape_source_id and l.etape_cible_id],
    }


@bp.route('/processus/<int:pid>/organigramme/editer')
@permission_requise('can_manage_logigram')
def editeur(pid):
    p = _processus(pid)
    return render_template('egalyx/organigramme_editeur.html', processus=p, donnees=donnees(p))


def appliquer(p, charge):
    """Valide et applique le JSON de l'éditeur (sans commit). Retourne (nb_etapes, nb_liens) ou lève ValueError."""
    from models import db, EtapeProcessus, LienProcessus
    etapes_in = charge.get('etapes') or []
    liens_in = charge.get('liens') or []
    if not isinstance(etapes_in, list) or not isinstance(liens_in, list) or len(etapes_in) > MAX_ETAPES:
        raise ValueError('Format invalide.')
    existantes = {e.id: e for e in EtapeProcessus.query.filter_by(processus_id=p.id).all()}
    correspondance = {}
    ordre_max = max([e.ordre or 0 for e in existantes.values()] or [0])
    for item in etapes_in:
        ident = item.get('id')
        if isinstance(ident, int) or (isinstance(ident, str) and ident.isdigit()):
            e = existantes.get(int(ident))
            if e is None:
                raise ValueError(f"Étape {ident} inconnue pour ce processus.")
        else:
            nom = (item.get('nom') or '').strip()
            if not nom:
                raise ValueError('Une nouvelle étape doit avoir un nom.')
            ordre_max += 1
            e = EtapeProcessus(processus_id=p.id, ordre=ordre_max, nom=nom[:200], client_id=p.client_id)
            db.session.add(e)
        if item.get('nom') and isinstance(item.get('nom'), str):
            e.nom = item['nom'].strip()[:200] or e.nom
        e.position_x = _borne(item.get('x'), 0, 20000, e.position_x or 0)
        e.position_y = _borne(item.get('y'), 0, 20000, e.position_y or 0)
        e.largeur = _borne(item.get('largeur'), 60, 600, e.largeur or 140)
        e.hauteur = _borne(item.get('hauteur'), 30, 400, e.hauteur or 60)
        if COULEUR.match(str(item.get('couleur') or '')):
            e.couleur = item['couleur']
        if item.get('type') in TYPES:
            e.type_etape = item['type']
        correspondance[str(ident)] = e
    db.session.flush()
    ids_valides = {e.id for e in existantes.values()} | {e.id for e in correspondance.values()}

    def resoudre(ref):
        if str(ref) in correspondance:
            return correspondance[str(ref)].id
        if isinstance(ref, int) and ref in ids_valides:
            return ref
        if isinstance(ref, str) and ref.isdigit() and int(ref) in ids_valides:
            return int(ref)
        raise ValueError(f'Lien vers une étape inconnue ({ref}).')

    vus = set()
    nouveaux = []
    for l in liens_in:
        s, c = resoudre(l.get('source')), resoudre(l.get('cible'))
        if s == c or (s, c) in vus:
            continue
        vus.add((s, c))
        nouveaux.append(LienProcessus(processus_id=p.id, etape_source_id=s, etape_cible_id=c,
                                      label=(str(l.get('label') or '')[:100]) or None, type_lien='sequence',
                                      client_id=p.client_id))
    LienProcessus.query.filter_by(processus_id=p.id).delete()
    db.session.add_all(nouveaux)
    p.nb_etapes = len(ids_valides)
    p.nb_liens = len(nouveaux)
    p.derniere_sync_organigramme = datetime.utcnow()
    p.a_besoin_sync = False
    return len(ids_valides), len(nouveaux)


@bp.route('/api/processus/<int:pid>/organigramme', methods=['POST'])
@permission_requise('can_manage_logigram')
def enregistrer_api(pid):
    from models import db
    p = _processus(pid)
    try:
        nb_e, nb_l = appliquer(p, request.get_json(silent=True) or {})
    except ValueError as e:
        db.session.rollback()
        return jsonify({'ok': False, 'erreur': str(e)}), 400
    journaliser('organigramme_modifie', {'processus': p.id, 'etapes': nb_e, 'liens': nb_l}, client_id=p.client_id)
    db.session.commit()
    return jsonify({'ok': True, 'etapes': nb_e, 'liens': nb_l, 'donnees': donnees(p)})


def enregistrer(app):
    app.register_blueprint(bp)
