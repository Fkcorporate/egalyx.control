"""
egalyx/automatismes.py — liens automatiques entre modules et relances.

1. Incident grave rattaché à un risque  -> notification « réévaluer le risque » aux administrateurs
   et au dernier évaluateur du risque.
2. Mesure de KRI au-delà du seuil d'alerte ou critique -> notification au responsable du KRI et
   aux administrateurs.
3. Relances par e-mail (si l'e-mail est configuré ; EGALYX_RELANCES_AUTO=0 pour couper) :
   - chaque lundi : récapitulatif « Ma semaine » à chaque utilisateur qui a des tâches en retard ou à échéance ;
   - chaque jour : rappel aux référents des signalements dont l'accusé de réception arrive à échéance.
"""
import logging
import os
from datetime import datetime, timedelta

journal = logging.getLogger('egalyx.automatismes')

GRAVITES_ALERTE = ('elevee', 'élevée', 'haute', 'critique', 'majeure', 'majeur', 'grave', 'tres_grave')


# ------------------------------------------------------------------ fonctions pures (testées)
def etat_kri(valeur, seuil_alerte, seuil_critique, sens='superieur'):
    if valeur is None:
        return 'inconnu'
    if sens == 'inferieur':
        if seuil_critique is not None and valeur <= seuil_critique:
            return 'critique'
        if seuil_alerte is not None and valeur <= seuil_alerte:
            return 'alerte'
        return 'normal'
    if seuil_critique is not None and valeur >= seuil_critique:
        return 'critique'
    if seuil_alerte is not None and valeur >= seuil_alerte:
        return 'alerte'
    return 'normal'


def destinataires(connexion, client_id, autres=()):
    from sqlalchemy import text
    ids = {r[0] for r in connexion.execute(text(
        "SELECT id FROM \"user\" WHERE client_id = :c AND is_active = :v AND (role = 'admin' OR is_client_admin = :v)"),
        {'c': client_id, 'v': True})}
    return sorted(ids | {i for i in autres if i})


def _notifier(connexion, client_id, ids, type_, titre, message, entite_type, entite_id, urgence='important'):
    from models import Notification
    t = Notification.__table__
    for uid in ids:
        connexion.execute(t.insert().values(type_notification=type_, titre=titre[:200], message=message,
                                            urgence=urgence, destinataire_id=uid, entite_type=entite_type,
                                            entite_id=entite_id, client_id=client_id, created_at=datetime.utcnow(),
                                            est_lue=False, actions_possibles=[], donnees_supplementaires={}))


# ------------------------------------------------------------------ écouteurs
def _incident_cree(mapper, connexion, incident):
    try:
        if not incident.risque_id or str(incident.gravite or '').lower() not in GRAVITES_ALERTE:
            return
        from sqlalchemy import text
        r = connexion.execute(text("SELECT reference, intitule, client_id FROM risques WHERE id = :r"),
                              {'r': incident.risque_id}).first()
        if not r:
            return
        evaluateur = connexion.execute(text(
            "SELECT evaluateur_final_id FROM evaluations_risque WHERE risque_id = :r ORDER BY created_at DESC LIMIT 1"),
            {'r': incident.risque_id}).scalar()
        cid = incident.client_id or r.client_id
        _notifier(connexion, cid, destinataires(connexion, cid, [evaluateur]), 'reevaluation_risque',
                  f"Incident {incident.gravite} sur le risque {r.reference} : réévaluation recommandée",
                  f"L'incident « {incident.titre} » ({incident.reference}) touche le risque « {r.intitule} ». "
                  f"Vérifiez que sa probabilité et l'efficacité des dispositifs de maîtrise sont toujours justes.",
                  'risque', incident.risque_id)
    except Exception as e:     # ne jamais bloquer l'enregistrement d'un incident
        journal.warning("Notification incident non créée : %s", e)


def _mesure_kri_creee(mapper, connexion, mesure):
    try:
        from sqlalchemy import text
        k = connexion.execute(text(
            "SELECT id, nom, seuil_alerte, seuil_critique, sens_evaluation_seuil, responsable_mesure_id, client_id, unite_mesure "
            "FROM kri WHERE id = :k"), {'k': mesure.kri_id}).first()
        if not k:
            return
        etat = etat_kri(mesure.valeur, k.seuil_alerte, k.seuil_critique, k.sens_evaluation_seuil or 'superieur')
        if etat not in ('alerte', 'critique'):
            return
        cid = k.client_id or mesure.client_id
        seuil = k.seuil_critique if etat == 'critique' else k.seuil_alerte
        _notifier(connexion, cid, destinataires(connexion, cid, [k.responsable_mesure_id]), 'kri_alerte',
                  f"KRI « {k.nom} » en {etat}",
                  f"Mesure du {mesure.date_mesure:%d/%m/%Y} : {mesure.valeur:g} {k.unite_mesure or ''} "
                  f"(seuil {etat} : {seuil:g}). Le risque associé est peut-être à réévaluer.",
                  'kri', k.id, 'urgent' if etat == 'critique' else 'important')
    except Exception as e:
        journal.warning("Notification KRI non créée : %s", e)


# ------------------------------------------------------------------ relances
def _url_publique():
    return (os.environ.get('EGALYX_URL_PUBLIQUE') or 'http://localhost:5005').rstrip('/')


def recapitulatif_hebdomadaire(app):
    from egalyx import courriel
    from egalyx.ma_semaine import taches
    from models import User, Client
    envoyes = 0
    with app.test_request_context('/', base_url=_url_publique()):
        actifs = {c.id for c in Client.query.filter_by(is_active=True).all()}
        for u in User.query.filter_by(is_active=True).all():
            if u.client_id not in actifs or not u.email or getattr(u, 'is_blocked', False):
                continue
            lst = [t for t in taches(u) if t['priorite'] <= 1]
            if not lst:
                continue
            retard = [t for t in lst if t['retard_jours']]
            lignes = [f"- [{t['type']}] {t['titre']}" + (f" — en retard de {t['retard_jours']} j" if t['retard_jours']
                      else (f" — échéance {t['echeance']:%d/%m}" if t['echeance'] else '')) for t in lst[:20]]
            texte = (f"Bonjour {u.username},\n\nVoici vos priorités de la semaine dans Egalyx Control "
                     f"({len(retard)} en retard, {len(lst) - len(retard)} à échéance sous 7 jours) :\n\n" + '\n'.join(lignes) +
                     f"\n\nTout voir : {_url_publique()}/ma-semaine\n\nCe message est envoyé chaque lundi.")
            if courriel.envoyer(u.email, f"Vos priorités de la semaine — {len(lst)} élément(s)", texte):
                envoyes += 1
    journal.info("Récapitulatif hebdomadaire : %s e-mail(s)", envoyes)
    return envoyes


def rappel_alertes(app):
    from egalyx import courriel
    from egalyx.alerte import est_referent
    from models import Signalement, User
    envoyes = 0
    with app.app_context():
        limite = datetime.utcnow() + timedelta(days=2)
        par_client = {}
        for s in Signalement.query.filter(Signalement.date_accuse_reception.is_(None)).all():
            if not s.est_cloture and s.echeance_accuse <= limite:
                par_client.setdefault(s.client_id, []).append(s)
        for cid, lst in par_client.items():
            for r in User.query.filter_by(client_id=cid, is_active=True).all():
                if est_referent(r) and r.email and courriel.envoyer(
                        r.email, f"Dispositif d'alerte : {len(lst)} accusé(s) de réception à envoyer",
                        f"{len(lst)} signalement(s) attendent un accusé de réception (délai légal : 7 jours).\n"
                        f"Échéance la plus proche : {min(s.echeance_accuse for s in lst):%d/%m/%Y}.\n\n"
                        f"{_url_publique()}/conformite/alertes/"):
                    envoyes += 1
    return envoyes


def enregistrer(app):
    from sqlalchemy import event
    try:
        from models import Incident, MesureKRI
        event.listen(Incident, 'after_insert', _incident_cree)
        event.listen(MesureKRI, 'after_insert', _mesure_kri_creee)
    except Exception as e:
        print(f"⚠️ Automatismes incidents / KRI non branchés : {e}")
    planif = app.extensions.get('egalyx_planificateur')
    if planif is not None and os.environ.get('EGALYX_RELANCES_AUTO', '1') == '1':
        planif.add_job(lambda: recapitulatif_hebdomadaire(app), 'cron', day_of_week='mon', hour=7, minute=5,
                       id='egalyx_recap_hebdo', replace_existing=True, misfire_grace_time=6 * 3600, coalesce=True)
        planif.add_job(lambda: rappel_alertes(app), 'cron', hour=8, minute=3,
                       id='egalyx_rappel_alertes', replace_existing=True, misfire_grace_time=6 * 3600, coalesce=True)

    @app.cli.command('envoyer-relances')
    def _cli_relances():
        """Envoie maintenant le récapitulatif « Ma semaine » et les rappels du dispositif d'alerte."""
        print(f"Récapitulatifs : {recapitulatif_hebdomadaire(app)} · rappels alertes : {rappel_alertes(app)}")
