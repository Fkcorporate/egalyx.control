"""
egalyx/circuit_controle.py — un seul circuit pour les campagnes de contrôle et le contrôle interne N2.

Une campagne est l'exécution terrain d'une planification N2 (si elle y est rattachée).
Règles communes, quel que soit l'écran utilisé (campagne côté opérateur, campagne côté
administration, « À valider » du N2) :

  soumission   l'opérateur soumet → l'exécution N2 reçoit les volumes À JOUR (créée ou mise à jour),
               la planification passe « soumise », la campagne « en attente de validation » ;
               le validateur est celui de la campagne, à défaut celui de la planification, à défaut
               les gestionnaires des campagnes ; ils sont notifiés.
  décision     une seule décision, prise une fois, par le validateur désigné ou un gestionnaire,
               jamais par la personne qui a soumis ni par le contrôleur ; elle vaut pour la
               campagne ET la planification, qu'elle soit prise d'un côté ou de l'autre.
  validation   les anomalies retenues deviennent des non-conformités N2 (pas avant).
  rejet        aucune non-conformité ; celles créées à tort par l'ancien circuit (ouvertes, sans
               plan d'action) sont retirées ; l'opérateur corrige puis resoumet.
  réouverture  après validation ou rejet : gestionnaires seulement pour une campagne validée ;
               3 réouvertures au maximum (règle du N2), comptées des deux côtés.

Droits : permissions des campagnes (« gérer les campagnes ») et du N2 (« gérer le contrôle
interne N2 ») ; la permission « gérer les audits » n'intervient plus.
"""
from datetime import datetime

from flask import url_for

STATUTS_ANOMALIES_RETENUES = ('a_traiter', 'confirmee')
MAX_REOUVERTURES = 3


def _m():
    import models
    return models


# ----------------------------------------------------------------------
# Droits
# ----------------------------------------------------------------------
def _perm(u, p):
    try:
        return bool(u.has_permission(p))
    except Exception:
        return False


def est_gestionnaire(u):
    """Administrateur de l'organisation ou gestionnaire des campagnes / du N2."""
    if u is None or not getattr(u, 'is_authenticated', True):
        return False
    return (getattr(u, 'role', None) in ('super_admin', 'admin') or bool(getattr(u, 'is_client_admin', False))
            or _perm(u, 'can_manage_campaigns') or _perm(u, 'can_manage_controle_interne_n2'))


def _meme_client(u, campagne):
    return getattr(u, 'role', None) == 'super_admin' or getattr(u, 'client_id', None) == campagne.client_id


def planification(campagne):
    pid = getattr(campagne, 'planification_c2n_id', None)
    return _m().PlanificationControle.query.get(pid) if pid else None


def auteurs(campagne):
    """Personnes qui ont exécuté / soumis la campagne : elles ne décident pas."""
    return {i for i in (getattr(campagne, 'soumis_par_id', None), getattr(campagne, 'evaluateur_id', None)) if i}


def validateur_designe(campagne, pl=None):
    pl = pl if pl is not None else planification(campagne)
    return campagne.valideur_id or (pl.validateur_requis_id if pl else None)


def peut_decider(u, campagne):
    """(bool, raison) : valider ou rejeter cette campagne."""
    if campagne.statut != 'en_attente_validation':
        return False, "Cette campagne n'est pas en attente de validation."
    if not _meme_client(u, campagne):
        return False, "Accès non autorisé."
    if u.id in auteurs(campagne):
        return False, "On ne valide pas une campagne que l'on a soi-même réalisée ou soumise."
    pl = planification(campagne)
    if pl is not None:
        if pl.controleur_id == u.id:
            return False, "Le contrôleur de la planification N2 ne peut pas la valider."
        if pl.statut == 'soumis' and not u.peut_valider_planification(pl) and not est_gestionnaire(u):
            return False, "Vous n'êtes ni le validateur désigné ni gestionnaire des campagnes."
    designe = validateur_designe(campagne, pl)
    if designe == u.id or est_gestionnaire(u):
        return True, None
    return False, "Seul le validateur désigné ou un gestionnaire des campagnes peut décider."


def nb_reouvertures(campagne, pl=None):
    pl = pl if pl is not None else planification(campagne)
    h_c = sum(1 for h in (campagne.historique_actions or []) if h.get('action') == 'reouverture')
    h_p = sum(1 for h in (pl.historique_actions or []) if h.get('action') == 'reouverture') if pl else 0
    return max(h_c, h_p)


def peut_rouvrir(u, campagne):
    if campagne.statut not in ('en_attente_validation', 'termine', 'rejete'):
        return False, "Cette campagne ne peut pas être rouverte dans son état actuel."
    if not _meme_client(u, campagne):
        return False, "Accès non autorisé."
    proprietaire = u.id in ({campagne.createur_id} | auteurs(campagne))
    if campagne.statut == 'termine' and not est_gestionnaire(u):
        return False, "Seul un gestionnaire des campagnes peut rouvrir une campagne validée."
    if not (proprietaire or est_gestionnaire(u)):
        return False, "Vous n'êtes pas autorisé à rouvrir cette campagne."
    if campagne.statut in ('termine', 'rejete') and nb_reouvertures(campagne) >= MAX_REOUVERTURES:
        return False, f"Limite de {MAX_REOUVERTURES} réouvertures atteinte : contactez un administrateur."
    return True, None


def url_detail(campagne, u):
    try:
        if getattr(u, 'is_operateur', False):
            return url_for('operateur_detail_campagne', campagne_id=campagne.id)
        return url_for('detail_campagne_controle', campagne_id=campagne.id)
    except Exception:
        return '/'


# ----------------------------------------------------------------------
# Outils
# ----------------------------------------------------------------------
def _historique(objet, action, u, details='', **extra):
    m = _m()
    h = list(objet.historique_actions or [])
    h.append({'date': datetime.utcnow().isoformat(), 'action': action, 'utilisateur_id': getattr(u, 'id', None),
              'utilisateur_nom': getattr(u, 'username', ''), 'details': details, **extra})
    objet.historique_actions = h
    m.marquer_json_modifie(objet, 'historique_actions')


def _notifier(destinataires, campagne, titre, message, type_, urgence='normal'):
    m = _m()
    for d in {d for d in destinataires if d}:
        m.db.session.add(m.Notification(destinataire_id=d, type_notification=type_, titre=titre, message=message[:500],
                                        entite_type='campagne', entite_id=campagne.id, urgence=urgence,
                                        client_id=campagne.client_id))


def _gestionnaires(campagne, exclure=()):
    """Utilisateurs de l'organisation qui peuvent décider (à défaut de validateur désigné)."""
    m = _m()
    ids = []
    try:
        for u in m.User.query.filter_by(client_id=campagne.client_id, is_active=True).limit(500).all():
            if u.id not in exclure and est_gestionnaire(u):
                ids.append(u.id)
    except Exception:
        pass
    return ids[:20]


def _execution_a_jour(campagne, u):
    """Crée ou met à jour l'exécution N2 avec les volumes actuels de la campagne."""
    m = _m()
    ex = m.ExecutionControle.query.get(campagne.execution_c2n_id) if campagne.execution_c2n_id else None
    if ex is None:
        ex = m.ExecutionControle(client_id=campagne.client_id)
        m.db.session.add(ex)
    ex.volume_previsionnel = campagne.nb_dossiers_prevus or 0
    ex.volume_controle = campagne.nb_dossiers_controles or 0
    ex.nb_conformes = campagne.nb_conformes or 0
    ex.nb_anomalies = campagne.nb_anomalies or 0
    ex.resultats = f"Résultats de la campagne {campagne.reference}"
    ex.commentaires = campagne.commentaire_general
    ex.conclusion = campagne.conclusion
    ex.execute_par_id = getattr(u, 'id', None)
    ex.date_execution = datetime.utcnow()
    try:
        ex.calculer_taux()
    except Exception:
        pass
    m.db.session.flush()
    campagne.execution_c2n_id = ex.id
    campagne.a_ete_executee_c2n = True
    campagne.date_synchronisation_c2n = datetime.utcnow()
    return ex


def _reference_nc(client_id):
    m = _m()
    nc = m.NonConformiteC2N
    if hasattr(nc, 'generer_reference_unique'):
        return nc.generer_reference_unique(client_id=client_id)
    n = nc.query.filter_by(client_id=client_id).count() + 1
    while nc.query.filter_by(reference=f"NC-{n:05d}", client_id=client_id).first():
        n += 1
    return f"NC-{n:05d}"


def _creer_non_conformites(campagne, u):
    """Anomalies retenues → non-conformités N2 (une par anomalie, jamais deux fois)."""
    m = _m()
    ex = _execution_a_jour(campagne, u) if not campagne.execution_c2n_id else m.ExecutionControle.query.get(campagne.execution_c2n_id)
    creees = 0
    anomalies = m.AnomalieDetectee.query.filter(
        m.AnomalieDetectee.campagne_id == campagne.id,
        m.AnomalieDetectee.client_id == campagne.client_id,
        m.AnomalieDetectee.statut.in_(STATUTS_ANOMALIES_RETENUES)).all()
    for a in anomalies:
        if a.non_conformite_id:
            continue
        nc = m.NonConformiteC2N(
            execution_id=ex.id if ex else None, reference=_reference_nc(campagne.client_id), description=a.motif,
            nombre_ecarts=a.nombre_ecarts, niveau_criticite=a.criticite,
            impact=a.description or f"Anomalie relevée lors de la campagne {campagne.reference}",
            cause_racine="À analyser", statut='ouvert', client_id=campagne.client_id, created_by=getattr(u, 'id', None))
        m.db.session.add(nc)
        m.db.session.flush()
        a.statut = 'convertie_en_nc'
        a.non_conformite_id = nc.id
        a.updated_at = datetime.utcnow()
        creees += 1
    return creees


def _retirer_nc_ouvertes(campagne):
    """Retire les non-conformités ouvertes et sans plan d'action ; les autres sont conservées."""
    m = _m()
    retirees = conservees = 0
    for a in m.AnomalieDetectee.query.filter_by(campagne_id=campagne.id, statut='convertie_en_nc',
                                                client_id=campagne.client_id).all():
        nc = m.NonConformiteC2N.query.get(a.non_conformite_id) if a.non_conformite_id else None
        if nc is not None and not (nc.statut == 'ouvert' and not nc.plans_action.count()):
            conservees += 1
            continue
        if nc is not None:
            m.db.session.delete(nc)
            retirees += 1
        a.statut = 'a_traiter'
        a.non_conformite_id = None
        a.updated_at = datetime.utcnow()
    return retirees, conservees


class _SansPropagation:
    """Évite qu'une décision prise sur la campagne repasse par l'enveloppe de la planification."""
    def __init__(self, pl):
        self.pl = pl

    def __enter__(self):
        if self.pl is not None:
            self.pl._egalyx_sans_propagation = True

    def __exit__(self, *a):
        if self.pl is not None:
            self.pl._egalyx_sans_propagation = False


# ----------------------------------------------------------------------
# Transitions
# ----------------------------------------------------------------------
def soumettre(campagne, u):
    """Volumes et anomalies déjà enregistrés par l'appelant. Retourne (ok, message)."""
    if campagne.statut not in ('en_cours', 'en_preparation', 'rejete'):
        return False, "Cette campagne ne peut pas être soumise dans son état actuel."
    pl = planification(campagne)
    _execution_a_jour(campagne, u)
    if pl is not None:
        pl.execution_id = campagne.execution_c2n_id
        if pl.statut in ('a_faire', 'en_cours', 'rejete'):
            ancien = pl.statut
            pl.statut = 'soumis'
            pl.soumis_par_id = u.id
            pl.date_soumission = datetime.utcnow()
            pl.commentaire_soumission = f"Soumis depuis la campagne {campagne.reference}"
            pl.version = (pl.version or 1) + 1
            pl.updated_at = datetime.utcnow()
            pl._ajouter_historique('soumission', u.id, pl.commentaire_soumission, ancien, 'soumis')
        if not campagne.valideur_id and pl.validateur_requis_id:
            campagne.valideur_id = pl.validateur_requis_id
    campagne.statut = 'en_attente_validation'
    campagne.soumis_par_id = u.id
    campagne.date_soumission = datetime.utcnow()
    campagne.date_rejet = campagne.rejete_par_id = campagne.raison_rejet = None
    campagne.updated_at = datetime.utcnow()
    nb = sum(1 for _ in _m().AnomalieDetectee.query.filter(
        _m().AnomalieDetectee.campagne_id == campagne.id,
        _m().AnomalieDetectee.statut.in_(STATUTS_ANOMALIES_RETENUES)).all())
    _historique(campagne, 'soumission', u, f"Soumise avec {nb} anomalie(s) retenue(s)")
    dest = [campagne.valideur_id] if campagne.valideur_id else _gestionnaires(campagne, exclure=auteurs(campagne))
    _notifier([d for d in dest if d not in auteurs(campagne)], campagne,
              f"Campagne à valider : {campagne.reference}",
              f"« {campagne.nom} » a été soumise par {u.username} ({nb} anomalie(s) retenue(s)). "
              "Les non-conformités seront créées à la validation.", 'campagne_validation', 'important')
    return True, ("Campagne soumise pour validation. Les non-conformités seront créées dans le N2 "
                  "quand le validateur l'aura validée.")


def _finaliser_validation(campagne, u, commentaire):
    nb_nc = _creer_non_conformites(campagne, u)
    campagne.statut = 'termine'
    campagne.valide_par_id = u.id
    campagne.date_validation = datetime.utcnow()
    campagne.commentaire_validation = commentaire or None
    campagne.updated_at = datetime.utcnow()
    _historique(campagne, 'validation', u, commentaire or "Campagne validée", ncs_crees=nb_nc)
    _notifier(auteurs(campagne) | {campagne.createur_id} - {u.id}, campagne,
              f"Campagne validée : {campagne.reference}",
              (commentaire or "Votre campagne a été validée.") + f" {nb_nc} non-conformité(s) créée(s) dans le N2.",
              'campagne_approuve')
    return nb_nc


def _finaliser_rejet(campagne, u, raison):
    retirees, _ = _retirer_nc_ouvertes(campagne)
    campagne.statut = 'rejete'
    campagne.rejete_par_id = u.id
    campagne.date_rejet = datetime.utcnow()
    campagne.raison_rejet = raison
    campagne.updated_at = datetime.utcnow()
    _historique(campagne, 'rejet', u, raison, ncs_retirees=retirees)
    _notifier(auteurs(campagne) | {campagne.createur_id} - {u.id}, campagne,
              f"Campagne rejetée : {campagne.reference}", f"Raison : {raison}", 'campagne_rejete', 'urgent')


def valider(campagne, u, commentaire=''):
    """Retourne (ok, message)."""
    ok, raison = peut_decider(u, campagne)
    if not ok:
        return False, raison
    pl = planification(campagne)
    if pl is not None and pl.statut == 'soumis':
        with _SansPropagation(pl):
            ok, msg = pl.valider(u, commentaire)
        if not ok and est_gestionnaire(u) and pl.controleur_id != u.id:
            ancien = pl.statut                          # gestionnaire des campagnes sans rôle N2
            pl.statut, pl.valide_par_id, pl.date_validation = 'valide', u.id, datetime.utcnow()
            pl.commentaire_validation = commentaire
            pl._ajouter_historique('validation', u.id, commentaire or "Validée depuis la campagne", ancien, 'valide')
            ok = True
        if not ok:
            return False, msg
    nb_nc = _finaliser_validation(campagne, u, commentaire)
    return True, f"Campagne validée : {nb_nc} non-conformité(s) créée(s) dans le N2."


def rejeter(campagne, u, raison):
    raison = (raison or '').strip()
    if len(raison) < 10:
        return False, "Veuillez fournir une raison de rejet (10 caractères minimum)."
    ok, msg = peut_decider(u, campagne)
    if not ok:
        return False, msg
    pl = planification(campagne)
    if pl is not None and pl.statut == 'soumis':
        with _SansPropagation(pl):
            ok, msg = pl.rejeter(u, raison)
        if not ok and est_gestionnaire(u) and pl.controleur_id != u.id:
            ancien = pl.statut
            pl.statut, pl.rejete_par_id, pl.date_rejet, pl.raison_rejet = 'rejete', u.id, datetime.utcnow(), raison
            pl._ajouter_historique('rejet', u.id, raison, ancien, 'rejete')
            ok = True
        if not ok:
            return False, msg
    _finaliser_rejet(campagne, u, raison)
    return True, "Campagne rejetée : l'opérateur a été prévenu et peut corriger puis resoumettre."


def rouvrir(campagne, u, raison):
    raison = (raison or '').strip()
    if len(raison) < 5:
        return False, "Veuillez indiquer la raison de la réouverture (5 caractères minimum)."
    ok, msg = peut_rouvrir(u, campagne)
    if not ok:
        return False, msg
    pl = planification(campagne)
    ancien = campagne.statut
    if pl is not None:
        if pl.statut in ('valide', 'rejete'):
            with _SansPropagation(pl):
                ok, msg = pl.rouvrir(u, raison)
            if not ok:
                return False, msg
        if pl.statut in ('a_faire', 'soumis'):
            avant = pl.statut
            pl.statut = 'en_cours'
            pl.soumis_par_id = pl.date_soumission = None
            pl._ajouter_historique('retrait' if avant == 'soumis' else 'reprise', u.id,
                                   f"Campagne {campagne.reference} rouverte : {raison}", avant, 'en_cours')
    retirees, conservees = _retirer_nc_ouvertes(campagne)
    _finaliser_reouverture(campagne, u, raison, ancien, retirees, conservees,
                           compter=ancien in ('termine', 'rejete'))
    texte = "Campagne rouverte."
    if retirees:
        texte += f" {retirees} non-conformité(s) retirée(s)."
    if conservees:
        texte += f" {conservees} non-conformité(s) conservée(s) (déjà traitées)."
    return True, texte


def _finaliser_reouverture(campagne, u, raison, ancien, retirees=0, conservees=0, compter=True):
    campagne.statut = 'en_cours'
    for champ in ('soumis_par_id', 'date_soumission', 'rejete_par_id', 'date_rejet', 'raison_rejet',
                  'valide_par_id', 'date_validation', 'commentaire_validation'):
        setattr(campagne, champ, None)
    campagne.raison_rouverture = raison
    campagne.date_rouverture = datetime.utcnow()
    campagne.rouvert_par_id = u.id
    campagne.updated_at = datetime.utcnow()
    _historique(campagne, 'reouverture' if compter else 'retrait', u, raison, ancien_statut=ancien,
                nouveau_statut='en_cours', ncs_supprimees=retirees, ncs_conservees=conservees)


# ----------------------------------------------------------------------
# Décisions prises dans le N2 → campagne rattachée
# ----------------------------------------------------------------------
def _campagne_de(pl):
    try:
        return _m().CampagneControle.query.filter_by(planification_c2n_id=pl.id, client_id=pl.client_id).first()
    except Exception:
        return None


def apres_validation_n2(pl, u, commentaire=None, *a, **k):
    c = _campagne_de(pl)
    if c is not None and c.statut == 'en_attente_validation':
        _finaliser_validation(c, u, commentaire)


def apres_rejet_n2(pl, u, raison=None, *a, **k):
    c = _campagne_de(pl)
    if c is not None and c.statut == 'en_attente_validation':
        _finaliser_rejet(c, u, raison or "Rejetée dans le contrôle interne N2")


def apres_reouverture_n2(pl, u, raison=None, *a, **k):
    c = _campagne_de(pl)
    if c is not None and c.statut in ('termine', 'rejete'):
        retirees, conservees = _retirer_nc_ouvertes(c)
        _finaliser_reouverture(c, u, raison or "Rouverte dans le contrôle interne N2", c.statut, retirees, conservees)
        pl.statut = 'en_cours'                   # la campagne reprend : la planification aussi


def _envelopper(cls, nom, apres, refuser_auteur):
    orig = getattr(cls, nom)
    if getattr(orig, '_egalyx_circuit', False):
        return
    def methode(self, user, *a, **k):
        if refuser_auteur and getattr(self, 'soumis_par_id', None) == getattr(user, 'id', None) \
                and getattr(user, 'role', None) != 'super_admin':
            return False, "On ne valide pas, ni ne rejette, ce que l'on a soi-même soumis."
        ok, msg = orig(self, user, *a, **k)
        if ok and not getattr(self, '_egalyx_sans_propagation', False):
            try:
                apres(self, user, *a, **k)
            except Exception as e:      # la décision N2 reste valable même si la campagne pose problème
                print(f"⚠️ Circuit contrôle : propagation à la campagne impossible ({e})")
        return ok, msg
    methode._egalyx_circuit = True
    methode.__doc__ = orig.__doc__
    setattr(cls, nom, methode)


def _droits_harmonises(user_cls):
    """Administration du N2 : rôle admin ou permission N2 (et non plus « gérer les audits »)."""
    def _is_admin_c2n(self):
        return (self.role in ('super_admin', 'admin') or bool(getattr(self, 'is_client_admin', False))
                or self.has_permission('can_manage_controle_interne_n2'))
    user_cls._is_admin_c2n = _is_admin_c2n


def campagnes_a_valider(u, limite=50):
    """Campagnes en attente que l'utilisateur peut décider."""
    try:
        m = _m()
        q = m.CampagneControle.query.filter_by(statut='en_attente_validation', is_archived=False)
        if getattr(u, 'role', None) != 'super_admin':
            q = q.filter_by(client_id=u.client_id)
        return [c for c in q.limit(500).all() if peut_decider(u, c)[0]][:limite]
    except Exception:
        return []


def enregistrer(app):
    m = _m()
    _envelopper(m.PlanificationControle, 'valider', apres_validation_n2, True)
    _envelopper(m.PlanificationControle, 'rejeter', apres_rejet_n2, True)
    _envelopper(m.PlanificationControle, 'rouvrir', apres_reouverture_n2, False)
    _droits_harmonises(m.User)

    def peut_etre_modifiee_par(self, user):
        if est_gestionnaire(user) and _meme_client(user, self):
            return self.statut != 'termine' or getattr(user, 'role', None) == 'super_admin'
        if getattr(user, 'is_operateur', False) and self.statut not in ('termine', 'en_attente_validation') \
                and not self.is_archived:
            return user.id in (self.createur_id, self.evaluateur_id)
        return False
    m.CampagneControle.peut_etre_modifiee_par = peut_etre_modifiee_par

    def circuit_campagne(campagne):
        from flask_login import current_user
        if not getattr(current_user, 'is_authenticated', False):
            return {}
        pl = planification(campagne)
        designe = validateur_designe(campagne, pl)
        nom = None
        if designe:
            v = m.User.query.get(designe)
            nom = getattr(v, 'username', None)
        decider, pourquoi = peut_decider(current_user, campagne)
        rouvrable, _ = peut_rouvrir(current_user, campagne)
        return {'peut_decider': decider, 'raison': pourquoi, 'validateur': nom, 'planification': pl,
                'peut_rouvrir': rouvrable, 'reouvertures': nb_reouvertures(campagne, pl), 'max_reouvertures': MAX_REOUVERTURES}
    app.jinja_env.globals['circuit_campagne'] = circuit_campagne
    app.jinja_env.globals['campagnes_a_valider'] = lambda: campagnes_a_valider(__import__('flask_login').current_user)
