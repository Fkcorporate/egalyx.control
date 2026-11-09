"""
egalyx/tiers.py — connaissance des tiers (KYC), LCB-FT et évaluation des fournisseurs.

- Fiche tiers : identification, pays, PPE, secteur, bénéficiaires effectifs, canal, montant.
- Score LCB-FT transparent (egalyx/calculs.score_lcb) avec listes du GAFI et secteurs
  modifiables par organisation (Paramètres > Risques) => niveau de vigilance et date de revue.
- Criblage contre les listes de sanctions importées par le super administrateur
  (fichier CSV : ONU, UE, OFAC, liste nationale…) ; chaque correspondance est
  confirmée ou écartée par un humain, avec trace.
- Fournisseurs : criticité (impact d'un arrêt, dépendance, substituabilité, note) et
  historique des évaluations.
"""
import csv
import io
from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, Response
from flask_login import current_user

from egalyx import calculs
from egalyx.commun import a_permission, client_id_courant, decimal, entier, journaliser, permission_requise, super_admin_requis

VOIR = ('can_view_tiers', 'can_manage_tiers')
GERER = ('can_manage_tiers',)

bp = Blueprint('tiers', __name__, url_prefix='/conformite/tiers')

NATURES = {'personne_morale': 'Personne morale', 'personne_physique': 'Personne physique'}
CANAUX = {'presentiel': 'En présentiel', 'distance': 'À distance'}
IMPACTS = {1: 'Faible', 2: 'Modéré', 3: 'Important', 4: 'Bloquant'}
CRITICITES = {'faible': 'Faible', 'moyenne': 'Moyenne', 'elevee': 'Élevée', 'critique': 'Critique'}
STATUTS = {'en_cours': 'En cours de vérification', 'valide': 'Relation validée', 'refuse': 'Relation refusée',
           'suspendu': 'Relation suspendue'}
SEUIL_CRIBLAGE = 0.85


def _listes(cid):
    from egalyx.parametres_risque import objet_parametres
    p = objet_parametres(cid)
    if p is None:
        return None, None, None, None
    return (p.pays_liste_noire if p.pays_liste_noire else None,
            p.pays_liste_grise if p.pays_liste_grise else None,
            p.secteurs_sensibles if p.secteurs_sensibles else None,
            p.seuil_montant_lcb)


def evaluer(t):
    """Recalcule score LCB-FT, vigilance, criticité fournisseur et prochaine revue (sans commit)."""
    noire, grise, secteurs, montant = _listes(t.client_id)
    r = calculs.score_lcb(t, noire, grise, secteurs, montant)
    t.score_lcb, t.niveau_vigilance, t.facteurs_lcb = r['score'], r['niveau'], [list(f) for f in r['facteurs']]
    if t.type_tiers == 'fournisseur' and t.impact_arret:
        t.criticite_score, t.criticite = calculs.criticite_fournisseur(
            t.impact_arret, t.dependance_pct, t.substituable, t.note_evaluation)
    else:
        t.criticite_score = t.criticite = None
    base = t.date_derniere_revue or date.today()
    t.date_prochaine_revue = calculs.ajouter_mois(base, r['delai_revue_mois'])
    return r


def cribler(t, auteur_id=None):
    """Compare le tiers et ses bénéficiaires effectifs aux listes de sanctions. Retourne le CriblageTiers créé."""
    from models import db, EntreeSanction, CriblageTiers
    entrees = EntreeSanction.query.all()
    liste = [{'nom': e.nom, 'alias': e.alias, 'source': e.source, 'programme': e.programme,
              'pays': e.pays, 'id': e.id} for e in entrees]
    noms = [('Tiers', t.nom)] + ([('Sigle', t.sigle)] if t.sigle else []) + \
           [('Bénéficiaire effectif', b.get('nom')) for b in (t.beneficiaires_effectifs or []) if b.get('nom')]
    correspondances = []
    for role, nom in noms:
        for c in calculs.cribler(nom, liste, seuil=SEUIL_CRIBLAGE):
            correspondances.append({'nom_controle': nom, 'role': role, 'nom_liste': c['nom_liste'],
                                    'nom_correspondant': c['nom_correspondant'], 'source': c['source'],
                                    'programme': c.get('programme'), 'pays': c.get('pays'),
                                    'score': round(c['score'], 3)})
    cr = CriblageTiers(client_id=t.client_id, tiers_id=t.id, correspondances=correspondances,
                       nb_entrees_controlees=len(entrees), realise_par=auteur_id,
                       statut='a_verifier' if correspondances else 'aucune_correspondance')
    db.session.add(cr)
    return cr


def _charger(tid):
    from models import Tiers
    t = Tiers.query.filter_by(id=tid, client_id=client_id_courant()).first()
    if not t:
        abort(404)
    return t


def _nouvelle_reference(cid):
    from models import Tiers
    n = Tiers.query.filter_by(client_id=cid).count() + 1
    while Tiers.query.filter_by(client_id=cid, reference=f'TRS-{n:04d}').first():
        n += 1
    return f'TRS-{n:04d}'


# ----------------------------------------------------------------------- pages
@bp.route('/')
@permission_requise(*VOIR)
def liste():
    from models import Tiers
    cid = client_id_courant()
    q = Tiers.query.filter_by(client_id=cid, is_archived=False)
    type_t, vig, filtre = request.args.get('type'), request.args.get('vigilance'), request.args.get('filtre')
    if type_t in Tiers.TYPES:
        q = q.filter_by(type_tiers=type_t)
    if vig in Tiers.VIGILANCES:
        q = q.filter_by(niveau_vigilance=vig)
    recherche = (request.args.get('q') or '').strip()
    if recherche:
        q = q.filter(Tiers.nom.ilike(f'%{recherche}%') | Tiers.reference.ilike(f'%{recherche}%'))
    tiers = q.order_by(Tiers.score_lcb.desc().nullslast(), Tiers.nom).all()
    tous = Tiers.query.filter_by(client_id=cid, is_archived=False).all()
    if filtre == 'revue':
        tiers = [t for t in tiers if t.revue_en_retard]
    elif filtre == 'criblage':
        tiers = [t for t in tiers if t.criblages and t.criblages[0].statut == 'a_verifier']
    ind = {
        'total': len(tous),
        'renforcee': sum(1 for t in tous if t.niveau_vigilance in ('renforcee', 'refus')),
        'revue': sum(1 for t in tous if t.revue_en_retard),
        'criblage': sum(1 for t in tous if t.criblages and t.criblages[0].statut == 'a_verifier'),
        'fournisseurs_critiques': sum(1 for t in tous if t.criticite in ('elevee', 'critique')),
    }
    return render_template('egalyx/tiers_liste.html', tiers=tiers, ind=ind, Tiers=Tiers, peut_gerer=a_permission(*GERER),
                           type_t=type_t, vig=vig, filtre=filtre, recherche=recherche, CRITICITES=CRITICITES)


def _lire_formulaire(t, f):
    t.type_tiers = f.get('type_tiers') if f.get('type_tiers') in ('client', 'fournisseur', 'partenaire', 'intermediaire') else 'client'
    t.nature = f.get('nature') if f.get('nature') in NATURES else 'personne_morale'
    t.nom = (f.get('nom') or '').strip()[:200]
    for champ, n in (('sigle', 100), ('numero_identification', 100), ('pays', 100), ('pays_residence', 100),
                     ('secteur', 150)):
        setattr(t, champ, (f.get(champ) or '').strip()[:n] or None)
    t.commentaire = (f.get('commentaire') or '').strip() or None
    try:
        t.date_naissance = datetime.strptime(f.get('date_naissance'), '%Y-%m-%d').date() if f.get('date_naissance') else None
    except ValueError:
        t.date_naissance = None
    t.est_ppe = f.get('est_ppe') == '1'
    t.structure_complexe = f.get('structure_complexe') == '1'
    t.canal = f.get('canal') if f.get('canal') in CANAUX else 'presentiel'
    t.montant_relation = decimal(f.get('montant_relation'))
    t.impact_arret = entier(f.get('impact_arret'), None, 1, 4)
    t.dependance_pct = decimal(f.get('dependance_pct'))
    t.substituable = f.get('substituable', '1') == '1'
    t.responsable_id = entier(f.get('responsable_id'))
    benef = []
    for i in range(10):
        nom = (f.get(f'be_nom_{i}') or '').strip()
        if nom:
            benef.append({'nom': nom[:200], 'part': decimal(f.get(f'be_part_{i}')),
                          'pays': (f.get(f'be_pays_{i}') or '').strip()[:100], 'ppe': f.get(f'be_ppe_{i}') == '1'})
    t.beneficiaires_effectifs = benef
    if any(b['ppe'] for b in benef):
        t.est_ppe = True
    return [] if t.nom else ['Le nom ou la raison sociale est obligatoire.']


def _utilisateurs(cid):
    from models import User
    return User.query.filter_by(client_id=cid, is_active=True).order_by(User.username).all()


@bp.route('/nouveau', methods=['GET', 'POST'])
@bp.route('/<int:tid>/modifier', methods=['GET', 'POST'])
@permission_requise(*GERER)
def formulaire(tid=None):
    from models import db, Tiers, marquer_json_modifie
    cid = client_id_courant()
    t = _charger(tid) if tid else Tiers(client_id=cid, type_tiers=request.args.get('type') or 'client')
    if request.method == 'POST':
        erreurs = _lire_formulaire(t, request.form)
        if erreurs:
            for e in erreurs:
                flash(e, 'danger')
        else:
            nouveau = t.id is None
            if nouveau:
                t.reference = _nouvelle_reference(cid)
                t.created_by = current_user.id
                db.session.add(t)
            marquer_json_modifie(t, 'beneficiaires_effectifs')
            db.session.flush()
            evaluer(t)
            marquer_json_modifie(t, 'facteurs_lcb')
            cr = cribler(t, current_user.id)
            journaliser('tiers_cree' if nouveau else 'tiers_modifie', {'tiers': t.id, 'score': t.score_lcb})
            db.session.commit()
            if cr.statut == 'a_verifier':
                flash(f'{len(cr.correspondances)} correspondance(s) possible(s) avec une liste de sanctions : à vérifier.', 'warning')
            flash(f'Tiers {t.reference} enregistré — vigilance {Tiers.VIGILANCES.get(t.niveau_vigilance, "")}.', 'success')
            return redirect(url_for('.detail', tid=t.id))
    return render_template('egalyx/tiers_formulaire.html', fiche=t, NATURES=NATURES, CANAUX=CANAUX, IMPACTS=IMPACTS,
                           Tiers=Tiers, utilisateurs=_utilisateurs(cid))


@bp.route('/<int:tid>')
@permission_requise(*VOIR)
def detail(tid):
    from models import Tiers
    t = _charger(tid)
    return render_template('egalyx/tiers_detail.html', fiche=t, Tiers=Tiers, STATUTS=STATUTS, CRITICITES=CRITICITES, peut_gerer=a_permission(*GERER),
                           IMPACTS=IMPACTS, NATURES=NATURES, CANAUX=CANAUX, bareme=calculs.BAREME_LCB)


@bp.route('/<int:tid>/action', methods=['POST'])
@permission_requise(*GERER)
def action(tid):
    from models import db, CriblageTiers, RevueTiers, marquer_json_modifie
    t = _charger(tid)
    a = request.form.get('action')
    commentaire = (request.form.get('commentaire') or '').strip() or None
    if a == 'cribler':
        cr = cribler(t, current_user.id)
        flash('Criblage effectué : ' + (f'{len(cr.correspondances)} correspondance(s) à vérifier.'
                                        if cr.correspondances else 'aucune correspondance.'),
              'warning' if cr.correspondances else 'success')
    elif a in ('confirme', 'faux_positif'):
        cr = CriblageTiers.query.filter_by(id=request.form.get('criblage_id', type=int), tiers_id=t.id).first_or_404()
        if not commentaire:
            flash('Justifiez la décision (source consultée, éléments d\'identification comparés).', 'danger')
            return redirect(url_for('.detail', tid=t.id))
        cr.statut, cr.commentaire = a, commentaire
        cr.verifie_par, cr.verifie_le = current_user.id, datetime.utcnow()
        t.sanction_confirmee = a == 'confirme' or any(c.statut == 'confirme' for c in t.criblages if c.id != cr.id)
        if a == 'confirme':
            t.statut = 'refuse'
        evaluer(t)
        marquer_json_modifie(t, 'facteurs_lcb')
        flash('Décision enregistrée.' + (' Relation refusée : gel et déclaration à la cellule de renseignement '
                                         'financier (CENTIF / Tracfin) selon votre réglementation.' if a == 'confirme' else ''),
              'warning' if a == 'confirme' else 'success')
    elif a == 'revue':
        note = decimal(request.form.get('note'))
        type_revue = 'evaluation_fournisseur' if request.form.get('type_revue') == 'evaluation_fournisseur' else 'kyc'
        if type_revue == 'evaluation_fournisseur':
            if note is None or not 0 <= note <= 5:
                flash('Note de 0 à 5 attendue.', 'danger')
                return redirect(url_for('.detail', tid=t.id))
            t.note_evaluation = note
        t.date_derniere_revue = date.today()
        evaluer(t)
        marquer_json_modifie(t, 'facteurs_lcb')
        db.session.add(RevueTiers(client_id=t.client_id, tiers_id=t.id, type_revue=type_revue, note=note,
                                  niveau_vigilance=t.niveau_vigilance, score_lcb=t.score_lcb,
                                  commentaire=commentaire, auteur_id=current_user.id))
        flash(f'Revue enregistrée. Prochaine revue : {t.date_prochaine_revue:%d/%m/%Y}.', 'success')
    elif a == 'statut' and request.form.get('statut') in STATUTS:
        if request.form['statut'] == 'valide' and t.sanction_confirmee:
            flash('Impossible de valider une relation avec une correspondance de sanction confirmée.', 'danger')
            return redirect(url_for('.detail', tid=t.id))
        t.statut = request.form['statut']
        flash('Statut mis à jour.', 'success')
    elif a == 'archiver':
        t.is_archived = True
        flash('Tiers archivé.', 'success')
        journaliser('tiers_archive', {'tiers': t.id})
        db.session.commit()
        return redirect(url_for('.liste'))
    else:
        abort(400)
    journaliser('tiers_' + a, {'tiers': t.id})
    db.session.commit()
    return redirect(url_for('.detail', tid=t.id))


@bp.route('/export.csv')
@permission_requise(*VOIR)
def export_csv():
    from models import Tiers
    sortie = io.StringIO()
    w = csv.writer(sortie, delimiter=';')
    w.writerow(['Référence', 'Type', 'Nom', 'Pays', 'PPE', 'Secteur', 'Score LCB-FT', 'Vigilance', 'Criticité',
                'Statut', 'Dernière revue', 'Prochaine revue'])
    for t in Tiers.query.filter_by(client_id=client_id_courant(), is_archived=False).order_by(Tiers.reference):
        w.writerow([t.reference, Tiers.TYPES.get(t.type_tiers, t.type_tiers), t.nom, t.pays or '',
                    'oui' if t.est_ppe else 'non', t.secteur or '', t.score_lcb if t.score_lcb is not None else '',
                    Tiers.VIGILANCES.get(t.niveau_vigilance, ''), CRITICITES.get(t.criticite, ''),
                    STATUTS.get(t.statut, t.statut), t.date_derniere_revue or '', t.date_prochaine_revue or ''])
    return Response('﻿' + sortie.getvalue(), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': 'attachment; filename=tiers.csv'})


# ----------------------------------------------------------------- listes de sanctions
def lire_csv_sanctions(contenu):
    """CSV (; ou ,) avec en-têtes : nom (obligatoire), alias, pays, programme, type. Retourne une liste de dicts."""
    texte = contenu.decode('utf-8-sig', errors='replace') if isinstance(contenu, bytes) else contenu
    echantillon = texte[:2000]
    sep = ';' if echantillon.count(';') >= echantillon.count(',') else ','
    lignes = []
    for ligne in csv.DictReader(io.StringIO(texte), delimiter=sep):
        l = {(k or '').strip().lower(): (v or '').strip() for k, v in ligne.items()}
        if l.get('nom'):
            lignes.append({'nom': l['nom'][:300], 'alias': l.get('alias') or None, 'pays': l.get('pays') or None,
                           'programme': (l.get('programme') or '')[:200] or None,
                           'type_entite': (l.get('type') or '')[:30] or None})
    return lignes


@bp.route('/sanctions', methods=['GET', 'POST'])
@super_admin_requis
def sanctions():
    from models import db, EntreeSanction
    if request.method == 'POST':
        source = (request.form.get('source') or '').strip().upper()[:50]
        fichier = request.files.get('fichier')
        if not source or not fichier:
            flash('Indiquez la source et le fichier CSV.', 'danger')
            return redirect(url_for('.sanctions'))
        lignes = lire_csv_sanctions(fichier.read())
        if not lignes:
            flash('Aucune ligne exploitable : la colonne « nom » est obligatoire.', 'danger')
            return redirect(url_for('.sanctions'))
        EntreeSanction.query.filter_by(source=source).delete()
        db.session.bulk_save_objects([EntreeSanction(source=source, **l) for l in lignes])
        db.session.commit()
        flash(f'Liste {source} remplacée : {len(lignes)} entrée(s).', 'success')
        return redirect(url_for('.sanctions'))
    sources = db.session.query(EntreeSanction.source, db.func.count(EntreeSanction.id),
                               db.func.max(EntreeSanction.date_import)).group_by(EntreeSanction.source).all()
    return render_template('egalyx/sanctions.html', sources=sources)


def enregistrer(app):
    app.register_blueprint(bp)
