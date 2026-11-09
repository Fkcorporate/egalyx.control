"""
egalyx/rapport_comite.py — rapport au comité d'audit / conseil, en un clic.

Assemble le tableau de bord stratégique, les audits, les plans d'action, l'appétence,
la LCB-FT et le dispositif d'alerte, et rédige une synthèse en langage clair.
La synthèse est produite par des règles explicites à partir des chiffres (pas d'IA) :
elle est donc reproductible et vérifiable. Impression / PDF par le navigateur.
"""
from datetime import date, datetime, timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from egalyx.commun import client_id_courant, journaliser, permission_requise

bp = Blueprint('rapport_comite', __name__, url_prefix='/rapports')

TERMINES = ('termine', 'terminee', 'annule', 'realise', 'realisee', 'cloture', 'clos')


def _pluriel(n, singulier, pluriel=None):
    return f"{n} {singulier if n in (0, 1) else (pluriel or singulier + 's')}"


def rediger_synthese(c):
    """c : dict de chiffres (voir chiffres_cles). Retourne une liste de paragraphes."""
    p = []
    if c.get('total_risques'):
        phrase = (f"Au {c['date']}, {_pluriel(c['evalues'], 'risque évalué', 'risques évalués')} "
                  f"sur {c['total_risques']} recensés ({c['couverture']} %).")
        if c['couverture'] is not None and c['couverture'] < 80:
            phrase += " La couverture de l'évaluation reste insuffisante pour une vision complète."
        p.append(phrase)
    else:
        p.append(f"Au {c['date']}, aucun risque n'est encore recensé : la cartographie est à construire.")
        return p
    crit, crit_brut = c.get('critiques', 0), c.get('critiques_bruts', 0)
    if crit:
        t = c.get('tendance_critiques')
        evol = ''
        if t and t['ecart'] > 0:
            evol = f", en hausse de {t['ecart']:g} sur la période"
        elif t and t['ecart'] < 0:
            evol = f", en baisse de {abs(t['ecart']):g} sur la période"
        p.append(f"{_pluriel(crit, 'risque reste', 'risques restent')} critique{'s' if crit > 1 else ''} après prise en compte "
                 f"des dispositifs de maîtrise{evol}. Avant maîtrise, {crit_brut} {'étaient' if crit_brut > 1 else 'était'} critique"
                 f"{'s' if crit_brut > 1 else ''}.")
    elif c.get('evalues'):
        p.append(f"Aucun risque critique après maîtrise ({crit_brut} avant maîtrise) : les dispositifs en place jouent leur rôle.")
    if c.get('hors_appetence') is not None:
        if c['hors_appetence']:
            p.append(f"{_pluriel(c['hors_appetence'], 'risque dépasse', 'risques dépassent')} l'appétence fixée par la direction "
                     f"et appelle{'nt' if c['hors_appetence'] > 1 else ''} une décision de traitement ou une acceptation formelle.")
        else:
            p.append("Tous les risques évalués se situent dans l'appétence fixée.")
    else:
        p.append("L'appétence au risque n'est pas encore formalisée : le comité est invité à la fixer.")
    if c.get('plans_ouverts'):
        if c['plans_retard']:
            p.append(f"{c['plans_retard']} plan{'s' if c['plans_retard'] > 1 else ''} d'action sur {c['plans_ouverts']} "
                     f"en cours {'sont' if c['plans_retard'] > 1 else 'est'} en retard"
                     + (f", le plus ancien de {c['retard_max']} jours." if c.get('retard_max') else '.'))
        else:
            p.append(f"Les {c['plans_ouverts']} plans d'action en cours respectent leurs échéances.")
    if c.get('incidents') is not None:
        txt = f"{_pluriel(c['incidents'], 'incident déclaré', 'incidents déclarés')} sur les {c['fenetre']} derniers jours"
        if c.get('incidents_graves'):
            txt += f", dont {c['incidents_graves']} grave{'s' if c['incidents_graves'] > 1 else ''}"
        p.append(txt + '.')
    if c.get('kri_alerte'):
        p.append(f"{_pluriel(c['kri_alerte'], 'indicateur de risque', 'indicateurs de risque')} sur {c['kri_actifs']} "
                 f"{'est' if c['kri_alerte'] == 1 else 'sont'} au-delà de {'son' if c['kri_alerte'] == 1 else 'leur'} seuil d'alerte.")
    if c.get('audits'):
        txt = (f"{_pluriel(c['audits'], 'mission d’audit', 'missions d’audit')} sur 12 mois, "
               f"{_pluriel(c['constatations'], 'constatation')} dont {c['constatations_majeures']} majeure"
               f"{'s' if c['constatations_majeures'] > 1 else ''}.")
        if c.get('recommandations_retard'):
            txt += (f" {c['recommandations_retard']} recommandation{'s' if c['recommandations_retard'] > 1 else ''} "
                    f"{'ont' if c['recommandations_retard'] > 1 else 'a'} dépassé {'leur' if c['recommandations_retard'] > 1 else 'son'} échéance.")
        p.append(txt)
    if c.get('tiers'):
        txt = f"{_pluriel(c['tiers'], 'tiers suivi', 'tiers suivis')} au titre de la LCB-FT, dont {c['tiers_renforces']} en vigilance renforcée"
        if c.get('criblages_a_verifier'):
            txt += f" ; {c['criblages_a_verifier']} correspondance{'s' if c['criblages_a_verifier'] > 1 else ''} avec les listes de sanctions à lever"
        p.append(txt + '.')
    if c.get('alertes') is not None and (c['alertes'] or c.get('alertes_ouvertes')):
        txt = f"Dispositif d'alerte : {_pluriel(c['alertes'], 'signalement reçu', 'signalements reçus')} sur 12 mois, {c['alertes_ouvertes']} en cours"
        if c.get('alertes_delais'):
            txt += f", {c['alertes_delais']} hors délai légal"
        p.append(txt + '.')
    return p


def decisions_attendues(c):
    d = []
    if c.get('hors_appetence'):
        d.append(f"Arbitrer le traitement des {c['hors_appetence']} risque(s) au-delà de l'appétence (réduire, transférer, éviter ou accepter).")
    if c.get('hors_appetence') is None and c.get('total_risques'):
        d.append("Fixer et formaliser l'appétence au risque de l'organisation.")
    if c.get('plans_retard'):
        d.append(f"Obtenir des responsables un plan de rattrapage pour les {c['plans_retard']} plan(s) d'action en retard.")
    if c.get('recommandations_retard'):
        d.append(f"Faire le point sur les {c['recommandations_retard']} recommandation(s) d'audit échues.")
    if c.get('couverture') is not None and c['couverture'] < 80:
        d.append("Demander l'achèvement de l'évaluation des risques non encore évalués.")
    if c.get('criblages_a_verifier'):
        d.append("Faire lever les correspondances avec les listes de sanctions avant toute opération avec les tiers concernés.")
    if c.get('alertes_delais'):
        d.append("Rappeler aux référents les délais légaux du dispositif d'alerte.")
    return d


def collecter(cid, construire_dashboard):
    from models import Audit, Constatation, Recommandation, Tiers, Signalement, Client
    d = construire_dashboard(cid)
    k = d['kpi']
    aujourd_hui = date.today()
    il_y_a_un_an = datetime.utcnow() - timedelta(days=365)
    c = {'date': aujourd_hui.strftime('%d/%m/%Y'), 'fenetre': d['fenetre_jours'],
         'total_risques': k['couverture']['total'], 'evalues': k['couverture']['evalues'],
         'couverture': k['couverture']['valeur'], 'critiques': k['critiques']['valeur'],
         'critiques_bruts': k['critiques']['brut'], 'tendance_critiques': k['critiques']['tendance'],
         'plans_retard': k['plans_retard']['valeur'], 'plans_ouverts': k['plans_retard']['ouverts'],
         'retard_max': d['plans_retard'][0]['jours'] if d['plans_retard'] else None,
         'incidents': k['incidents']['valeur'], 'incidents_graves': k['incidents']['graves'],
         'kri_alerte': k['kri_alerte']['valeur'], 'kri_actifs': k['kri_alerte']['actifs'],
         'hors_appetence': d['appetence']['nombre'] if d.get('appetence') else None}

    audits = [a for a in Audit.query.filter_by(client_id=cid, is_archived=False).all()
              if (a.created_at and a.created_at >= il_y_a_un_an) or (a.date_debut_prevue and a.date_debut_prevue >= il_y_a_un_an.date())]
    ids = [a.id for a in audits]
    constats = Constatation.query.filter(Constatation.audit_id.in_(ids or [-1])).all()
    recos = Recommandation.query.filter_by(client_id=cid).all()
    reco_retard = [r for r in recos if r.date_echeance and r.date_echeance < aujourd_hui and (r.statut or '') not in TERMINES]
    majeurs = [x for x in constats if str(x.gravite or x.criticite or '').lower() in ('majeure', 'majeur', 'critique', 'elevee', 'eleve', 'haute')]
    c.update(audits=len(audits), constatations=len(constats), constatations_majeures=len(majeurs),
             recommandations_retard=len(reco_retard))

    tiers = Tiers.query.filter_by(client_id=cid, is_archived=False).all()
    c.update(tiers=len(tiers), tiers_renforces=sum(1 for t in tiers if t.niveau_vigilance in ('renforcee', 'refus')),
             criblages_a_verifier=sum(1 for t in tiers if t.criblages and t.criblages[0].statut == 'a_verifier'))

    sig = Signalement.query.filter_by(client_id=cid).all()
    maintenant = datetime.utcnow()
    c.update(alertes=sum(1 for s in sig if s.created_at and s.created_at >= il_y_a_un_an),
             alertes_ouvertes=sum(1 for s in sig if not s.est_cloture),
             alertes_delais=sum(1 for s in sig if not s.est_cloture and (
                 (not s.date_accuse_reception and s.echeance_accuse < maintenant) or
                 (not s.date_retour_information and s.echeance_retour and s.echeance_retour < maintenant))))
    audits_detail = []
    for a in sorted(audits, key=lambda a: a.date_debut_prevue or date.min, reverse=True):
        cs = [x for x in constats if x.audit_id == a.id]
        audits_detail.append({'audit': a, 'constatations': len(cs),
                              'majeures': sum(1 for x in cs if x in majeurs),
                              'recos': sum(1 for r in recos if r.audit_id == a.id),
                              'recos_retard': sum(1 for r in reco_retard if r.audit_id == a.id)})
    return {'d': d, 'c': c, 'synthese': rediger_synthese(c), 'decisions': decisions_attendues(c),
            'audits': audits_detail, 'reco_retard': sorted(reco_retard, key=lambda r: r.date_echeance)[:10],
            'client': Client.query.get(cid)}


@bp.route('/comite-audit')
@permission_requise('can_view_rapport_comite')
def page():
    from models import db
    construire = current_app.extensions.get('egalyx_dashboard_strategique')
    if not construire:
        flash('Le tableau de bord stratégique est indisponible.', 'danger')
        return redirect(url_for('dashboard'))
    cid = client_id_courant()
    donnees = collecter(cid, construire)
    journaliser('rapport_comite_genere', {'date': donnees['c']['date']})
    db.session.commit()
    return render_template('egalyx/rapport_comite.html', **donnees, genere_le=datetime.now(),
                           auteur=request.args.get('auteur') or '')


def enregistrer(app, construire_dashboard=None):
    app.register_blueprint(bp)
    if construire_dashboard:
        app.extensions['egalyx_dashboard_strategique'] = construire_dashboard
