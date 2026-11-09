"""
egalyx/kri_suivi.py — fiabilité des KRI.

1. Fraîcheur : une mesure est attendue selon la fréquence du KRI ; au-delà (avec une marge), le KRI est
   « mesure en retard ». Un KRI jamais mesuré l'est aussi. Un KRI non mesuré n'est PAS un KRI « normal ».
2. Seuils cohérents : sens « au-dessus » => seuil d'alerte < seuil critique ; sens « en dessous » => l'inverse.
   Refusé à l'enregistrement, quel que soit l'écran utilisé.
3. Seuils historisés : quand un seuil change, l'ancien jeu est conservé avec sa date de fin.
   Une mesure passée est jugée avec les seuils de son époque (get_etat_alerte(valeur, a_la_date=...)).
4. KRI critique => les gestionnaires des risques sont prévenus et invités à réévaluer le risque lié ;
   le tableau de bord stratégique signale un risque coté Faible/Moyen dont le KRI est critique.
"""
from datetime import datetime, timedelta

from flask_login import current_user

PERIODES = {  # jours entre deux mesures (valeurs du formulaire et variantes rencontrées en base)
    'quotidien': 1, 'quotidienne': 1, 'journalier': 1, 'journaliere': 1,
    'hebdomadaire': 7, 'bimensuel': 15, 'bimensuelle': 15,
    'mensuel': 31, 'mensuelle': 31, 'trimestriel': 92, 'trimestrielle': 92,
    'semestriel': 183, 'semestrielle': 183, 'annuel': 366, 'annuelle': 366,
}
ETATS_GRAVES = ('critique', 'hors_cible')


def periode_jours(kri):
    return PERIODES.get((getattr(kri, 'frequence_mesure', None) or 'mensuel').strip().lower(), 31)


def _jour(d):
    return d.date() if hasattr(d, 'date') and callable(d.date) else d


def fraicheur(kri, aujourd_hui=None):
    """{'etat': 'a_jour' | 'en_retard' | 'jamais', 'derniere', 'attendue_le', 'retard_jours'}"""
    aujourd_hui = aujourd_hui or datetime.utcnow().date()
    m = kri.get_derniere_mesure() if hasattr(kri, 'get_derniere_mesure') else None
    if m is None or not m.date_mesure:
        return {'etat': 'jamais', 'derniere': None, 'attendue_le': None, 'retard_jours': None}
    p = periode_jours(kri)
    derniere = _jour(m.date_mesure)
    attendue = derniere + timedelta(days=p)
    marge = max(3, round(p * 0.2))
    retard = (aujourd_hui - attendue).days
    etat = 'en_retard' if retard > marge else 'a_jour'
    return {'etat': etat, 'derniere': derniere, 'attendue_le': attendue, 'retard_jours': max(0, retard)}


def seuils_incoherents(sens, alerte, critique):
    """Message d'erreur, ou None si les seuils sont cohérents (ou incomplets)."""
    if alerte is None or critique is None:
        return None
    try:
        alerte, critique = float(alerte), float(critique)
    except (TypeError, ValueError):
        return None
    if (sens or 'superieur') == 'inferieur':
        if alerte <= critique:
            return (f"Seuils incohérents : le risque augmente quand la valeur BAISSE, donc le seuil d'alerte ({alerte:g}) "
                    f"doit être au-dessus du seuil critique ({critique:g}).")
    elif alerte >= critique:
        return (f"Seuils incohérents : le risque augmente quand la valeur MONTE, donc le seuil d'alerte ({alerte:g}) "
                f"doit être en dessous du seuil critique ({critique:g}).")
    return None


# ---------------------------------------------------------------- seuils à une date
def _seuils_a_la_date(kri, a_la_date):
    """(alerte, critique, sens) en vigueur à cette date, ou None si ce sont les seuils actuels."""
    if a_la_date is None or not getattr(kri, 'id', None):
        return None
    from models import HistoriqueSeuilKRI
    if not isinstance(a_la_date, datetime):
        a_la_date = datetime.combine(a_la_date, datetime.min.time())
    h = (HistoriqueSeuilKRI.query.filter(HistoriqueSeuilKRI.kri_id == kri.id,
                                         HistoriqueSeuilKRI.valable_jusqu_au > a_la_date)
         .order_by(HistoriqueSeuilKRI.valable_jusqu_au.asc()).first())
    return (h.seuil_alerte, h.seuil_critique, h.sens) if h else None


def _patcher_kri(KRI):
    if getattr(KRI, '_egalyx_kri_suivi', False):
        return
    orig_etat, orig_couleur, orig_libelle = KRI.get_etat_alerte, KRI.get_couleur_etat, KRI.get_libelle_etat

    def avec_seuils(self, seuils, fn, valeur):
        if not seuils:
            return fn(self, valeur)
        sauve = (self.seuil_alerte, self.seuil_critique, self.sens_evaluation_seuil)
        from sqlalchemy.orm import attributes
        # Lecture seule : on remet les valeurs ensuite et on efface toute trace de modification
        etat = attributes.instance_state(self)
        try:
            self.__dict__['seuil_alerte'], self.__dict__['seuil_critique'], self.__dict__['sens_evaluation_seuil'] = (
                seuils[0], seuils[1], seuils[2] or sauve[2])
            return fn(self, valeur)
        finally:
            self.__dict__['seuil_alerte'], self.__dict__['seuil_critique'], self.__dict__['sens_evaluation_seuil'] = sauve
            _ = etat

    def get_etat_alerte(self, valeur, a_la_date=None):
        return avec_seuils(self, _seuils_a_la_date(self, a_la_date), orig_etat, valeur)

    def get_couleur_etat(self, valeur, a_la_date=None):
        return avec_seuils(self, _seuils_a_la_date(self, a_la_date), orig_couleur, valeur)

    def get_libelle_etat(self, valeur, a_la_date=None):
        return avec_seuils(self, _seuils_a_la_date(self, a_la_date), orig_libelle, valeur)

    KRI.get_etat_alerte, KRI.get_couleur_etat, KRI.get_libelle_etat = get_etat_alerte, get_couleur_etat, get_libelle_etat
    KRI.fraicheur = fraicheur
    KRI._egalyx_kri_suivi = True


# ---------------------------------------------------------------- contrôle à l'enregistrement
class SeuilsIncoherents(ValueError):
    pass


def _avant_flush(session, _contexte, _instances):
    import models as m
    from sqlalchemy import inspect as sa_inspect
    maintenant = datetime.utcnow()
    for obj in list(session.new) + list(session.dirty):
        if not isinstance(obj, m.KRI):
            continue
        nouveau = obj in session.new or not obj.id
        insp = sa_inspect(obj)
        anciens, change = {}, False
        for champ in ('seuil_alerte', 'seuil_critique', 'sens_evaluation_seuil'):
            h = insp.attrs[champ].history
            if h.added and (not h.deleted or h.deleted[0] != h.added[0]):
                change = True
            anciens[champ] = h.deleted[0] if h.deleted else getattr(obj, champ)
        # Contrôle seulement quand on crée l'indicateur ou qu'on modifie ses seuils / son sens : un indicateur
        # déjà incohérent ne doit pas bloquer l'ouverture des pages (qui enregistrent son état, sa tendance…).
        if nouveau or change:
            message = seuils_incoherents(obj.sens_evaluation_seuil, obj.seuil_alerte, obj.seuil_critique)
            if message:
                raise SeuilsIncoherents(message)
        if not nouveau and obj.id:
            if change and any(insp.attrs[c].history.deleted for c in ('seuil_alerte', 'seuil_critique', 'sens_evaluation_seuil')):
                session.add(m.HistoriqueSeuilKRI(
                    kri_id=obj.id, seuil_alerte=anciens['seuil_alerte'], seuil_critique=anciens['seuil_critique'],
                    sens=anciens['sens_evaluation_seuil'], valable_jusqu_au=maintenant,
                    modifie_par_id=getattr(current_user, 'id', None) if _connecte() else None))
    for obj in list(session.new):
        if isinstance(obj, m.MesureKRI):
            _signaler_si_critique(session, m, obj)


def _connecte():
    try:
        return bool(current_user and current_user.is_authenticated)
    except Exception:
        return False


def _signaler_si_critique(session, m, mesure):
    kri = mesure.kri if getattr(mesure, 'kri', None) is not None else (
        session.get(m.KRI, mesure.kri_id) if mesure.kri_id else None)
    if kri is None or mesure.valeur is None:
        return
    etat = KRI_etat_brut(kri, mesure.valeur)
    if etat not in ETATS_GRAVES or not kri.risque_id:
        return
    risque = session.get(m.Risque, kri.risque_id)
    cid = kri.client_id or (risque.client_id if risque else None)
    if not cid:
        return
    destinataires = set()
    if kri.responsable_mesure_id:
        destinataires.add(kri.responsable_mesure_id)
    for u in m.User.query.filter_by(client_id=cid, is_active=True).all():
        try:
            if not u.is_operateur and (u.is_client_admin or u.has_permission('can_validate_risks')
                                       or u.has_permission('can_manage_risks')):
                destinataires.add(u.id)
        except Exception:
            continue
    titre = f"KRI critique : réévaluer le risque {risque.reference if risque else ''}".strip()
    texte = (f"« {kri.nom} » vaut {mesure.valeur:g}{(' ' + kri.unite_mesure) if kri.unite_mesure else ''} "
             f"(seuil critique {kri.seuil_critique:g}). La cotation du risque « {risque.intitule if risque else ''} » "
             f"doit être revue.") if kri.seuil_critique is not None else f"« {kri.nom} » est au niveau critique."
    for d in destinataires:
        session.add(m.Notification(destinataire_id=d, type_notification='kri_critique', titre=titre[:200], message=texte[:500],
                                   entite_type='kri', entite_id=kri.id, client_id=cid))


def KRI_etat_brut(kri, valeur):
    """État avec les seuils actuels, sans requête (utilisable pendant un flush)."""
    sens = kri.sens_evaluation_seuil or 'superieur'
    a, c = kri.seuil_alerte, kri.seuil_critique
    grave = 'critique' if (kri.type_indicateur or 'kri') == 'kri' else 'hors_cible'
    if sens == 'inferieur':
        if c is not None and valeur <= c:
            return grave
    elif c is not None and valeur >= c:
        return grave
    return 'autre'


def kri_du_client(cid):
    from models import KRI
    return KRI.query.filter_by(client_id=cid, est_actif=True).all()


def resume_fraicheur(kris):
    f = [fraicheur(k) for k in kris]
    return {'en_retard': sum(1 for x in f if x['etat'] == 'en_retard'), 'jamais': sum(1 for x in f if x['etat'] == 'jamais')}


def enregistrer(app):
    import models as m
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    _patcher_kri(m.KRI)
    if not getattr(m, '_egalyx_kri_flush', False):
        event.listen(Session, 'before_flush', _avant_flush)
        m._egalyx_kri_flush = True

    @app.errorhandler(SeuilsIncoherents)
    def _seuils(e):
        from flask import flash, redirect, request
        try:
            m.db.session.rollback()
        except Exception:
            pass
        if request.is_json or request.path.startswith('/api/'):
            from flask import jsonify
            return jsonify({'success': False, 'error': str(e)}), 400
        flash(str(e), 'warning')
        return redirect(request.referrer or request.path)

    app.jinja_env.globals['kri_fraicheur'] = fraicheur
    app.jinja_env.globals['kri_seuils_incoherents'] = lambda k: seuils_incoherents(
        getattr(k, 'sens_evaluation_seuil', None), getattr(k, 'seuil_alerte', None), getattr(k, 'seuil_critique', None))
