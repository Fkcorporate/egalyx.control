"""
egalyx/bibliotheque.py — import de risques types par secteur dans une cartographie.
"""
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from egalyx.bibliotheque_controles import controles_du_risque
from egalyx.bibliotheque_donnees import IMPACT_TXT, PROBA_TXT, SECTEURS, risques_du_secteur
from egalyx.commun import client_id_courant, journaliser, permission_requise

bp = Blueprint('bibliotheque', __name__, url_prefix='/risques/bibliotheque')

CODES = {'transverse': 'GEN', 'banque': 'BQ', 'microfinance': 'MF', 'assurance': 'AS', 'mines_energie': 'MIN',
         'telecoms': 'TEL', 'secteur_public': 'PUB', 'industrie_commerce': 'IND'}


def prochaine_reference(cid, prefixe, deja=None):
    from models import Risque
    deja = deja if deja is not None else set()
    existantes = {r[0] for r in Risque.query.with_entities(Risque.reference).filter(Risque.client_id == cid).all()} | deja
    n = 1
    while f'R-{prefixe}-{n:03d}' in existantes:
        n += 1
    return f'R-{prefixe}-{n:03d}'


def importer(cid, cartographie, secteur, indices, auteur_id=None, avec_controles=False):
    """Crée les risques choisis (sans commit). Retourne la liste des risques créés ; ignore les doublons d'intitulé.
    avec_controles : crée aussi les contrôles types de chaque risque (dispositifs à adapter et à évaluer)."""
    from models import db, Risque
    existants = {(r.intitule or '').strip().lower() for r in
                 Risque.query.filter_by(cartographie_id=cartographie.id, is_archived=False).all()}
    crees, refs = [], set()
    for r in risques_du_secteur(secteur):
        if r['index'] not in indices or r['intitule'].lower() in existants:
            continue
        ref = prochaine_reference(cid, CODES[secteur], refs)
        refs.add(ref)
        risque = Risque(reference=ref, intitule=r['intitule'], categorie=r['categorie'],
                        description=f"Risque type « {SECTEURS[secteur]['nom']} » — référentiel : {r['referentiel']}.",
                        cause_racine=r['cause'], consequences=r['consequences'],
                        impact=IMPACT_TXT[r['impact']], probabilite=PROBA_TXT[r['probabilite']],
                        cartographie_id=cartographie.id, client_id=cid, created_by=auteur_id, statut='actif')
        try:
            risque.metadonnees = {'source': 'bibliotheque', 'secteur': secteur, 'referentiel': r['referentiel'],
                                  'importe_le': datetime.utcnow().isoformat()}
        except Exception:
            pass
        risque.calculer_score_risque()
        risque.calculer_niveau_criticite()
        db.session.add(risque)
        crees.append(risque)
        if avec_controles:
            db.session.flush()
            creer_controles(cid, risque, r['intitule'], auteur_id)
    return crees


def creer_controles(cid, risque, intitule, auteur_id=None):
    """Dispositifs types du risque : non évalués (l'efficacité reste à mesurer), sans effet sur la cotation tant
    qu'ils ne sont pas évalués."""
    from models import db, DispositifMaitrise
    crees = []
    for n, c in enumerate(controles_du_risque(intitule), 1):
        d = DispositifMaitrise(reference=f'DM-{risque.reference}-{n:03d}', nom=c['nom'], type_dispositif=c['type'],
                               nature=c['nature'], frequence=c['frequence'], statut='actif', risque_id=risque.id,
                               client_id=cid, created_by=auteur_id,
                               description="Contrôle type proposé par la bibliothèque Egalyx : adaptez-le, désignez un "
                                           "responsable et évaluez son efficacité.")
        db.session.add(d)
        crees.append(d)
    return crees


@bp.route('/', methods=['GET', 'POST'])
@permission_requise('can_manage_risks')
def page():
    from models import db, Cartographie
    cid = client_id_courant()
    cartos = Cartographie.query.filter_by(client_id=cid, is_archived=False).order_by(Cartographie.nom).all()
    secteur = request.values.get('secteur') or 'transverse'
    if secteur not in SECTEURS:
        secteur = 'transverse'
    if request.method == 'POST':
        from models import Cartographie as _C
        indices = {int(x) for x in request.form.getlist('risques') if x.isdigit()}
        avec_controles = request.form.get('avec_controles') == '1'
        choix = request.form.get('cartographie_id') or ''
        if choix == 'nouvelle':
            nom = (request.form.get('nouvelle_nom') or '').strip() or f"Cartographie {SECTEURS[secteur]['nom']}"
            carto = _C(nom=nom[:200], client_id=cid, created_by=current_user.id,
                       description=f"Créée depuis la bibliothèque « {SECTEURS[secteur]['nom']} ».")
            if not indices:
                flash('Choisissez au moins un risque.', 'warning')
                return redirect(url_for('.page', secteur=secteur))
            db.session.add(carto)
            db.session.flush()
        else:
            carto = next((c for c in cartos if str(c.id) == choix), None)
        if not carto or not indices:
            flash('Choisissez une cartographie et au moins un risque.', 'warning')
            return redirect(url_for('.page', secteur=secteur))
        crees = importer(cid, carto, secteur, indices, current_user.id, avec_controles=avec_controles)
        nb_ctrl = sum(len(controles_du_risque(r.intitule)) for r in crees) if avec_controles else 0
        journaliser('bibliotheque_import', {'secteur': secteur, 'cartographie': carto.id, 'nombre': len(crees),
                                            'controles': nb_ctrl, 'nouvelle': choix == 'nouvelle'})
        db.session.commit()
        ignores = len(indices) - len(crees)
        flash(f"{len(crees)} risque(s)" + (f" et {nb_ctrl} contrôle(s) type(s)" if nb_ctrl else '')
              + f" ajouté(s) à « {carto.nom} »." + (f" {ignores} déjà présent(s), ignoré(s)." if ignores else '')
              + " Étape suivante : désignez les responsables des contrôles, puis évaluez les risques.", 'success')
        return redirect(url_for('detail_cartographie', id=carto.id))
    risques = risques_du_secteur(secteur)
    for r in risques:
        r['controles'] = controles_du_risque(r['intitule'])
    return render_template('egalyx/bibliotheque.html', secteurs=SECTEURS, secteur=secteur, risques=risques, cartos=cartos)


def enregistrer(app):
    app.register_blueprint(bp)
