"""Modèles de test (doubles en mémoire) reprenant les champs utilisés par egalyx/."""
import json
from datetime import datetime, timedelta

from faux_orm import Champ, FauxDB, Modele

db = FauxDB()

PREFIXE = 'enc1:'


def chiffrer_secret(v):
    if v in (None, ''):
        return v
    return PREFIXE + json.dumps(v)[::-1]          # réversible, illisible en clair : suffit pour les tests


def dechiffrer_secret(v):
    if not v or not str(v).startswith(PREFIXE):
        return v
    return json.loads(v[len(PREFIXE):][::-1])


def marquer_json_modifie(obj, champ):
    pass


class User(Modele):
    id = Champ(); username = Champ(); email = Champ(); role = Champ('utilisateur'); client_id = Champ()
    is_active = Champ(True); is_client_admin = Champ(False); is_blocked = Champ(False); deleted_at = Champ()
    totp_secret_chiffre = Champ(); totp_actif = Champ(False); totp_active_le = Champ(); totp_dernier_pas = Champ()
    totp_codes_secours = Champ(); mot_de_passe = Champ('secret'); last_login = Champ(); failed_login_attempts = Champ(0)
    password_changed_at = Champ(); can_manage_users = Champ(False)
    is_authenticated = True
    is_anonymous = False

    def check_password(self, p):
        return p == self.mot_de_passe

    droits = Champ()          # None = tous les droits (tests existants) ; sinon ensemble de permissions

    def has_permission(self, p):
        if self.role == 'super_admin':
            return True
        from egalyx.modules_client import permission_autorisee_par_module   # même ordre que models.py
        if not permission_autorisee_par_module(self, p):
            return False
        return True if self.droits is None else p in self.droits

    @property
    def client(self):
        return Client.query.get(self.client_id)

    def get_id(self):
        return str(self.id)


class Client(Modele):
    id = Champ(); nom = Champ(); reference = Champ(); is_active = Champ(True); contact_email = Champ(); contact_nom = Champ()
    formule_id = Champ(); date_expiration = Champ(); date_activation = Champ(); plan = Champ('standard')
    modules_actifs = Champ()

    @property
    def formule(self):
        return FormuleAbonnement.query.get(self.formule_id)


class JournalActiviteClient(Modele):
    id = Champ(); client_id = Champ(); utilisateur_id = Champ(); action = Champ(); details = Champ(); ip_address = Champ()
    user_agent = Champ(); created_at = Champ()


class Signalement(Modele):
    id = Champ(); client_id = Champ(); code_suivi = Champ(); mot_de_passe_hash = Champ(); categorie = Champ()
    _description = Champ(); date_faits = Champ(); lieu = Champ(); _personnes = Champ(); anonyme = Champ(True)
    _identite = Champ(); statut = Champ('recu'); recevable = Champ(); referent_id = Champ()
    date_accuse_reception = Champ(); date_retour_information = Champ(); motif_cloture = Champ()
    created_at = Champ(); updated_at = Champ()
    STATUTS = {'recu': 'Reçu', 'recevable': 'Recevable', 'en_instruction': 'En instruction',
               'cloture_fonde': 'Clôturé — fondé', 'cloture_non_fonde': 'Clôturé — non fondé', 'irrecevable': 'Irrecevable'}
    CATEGORIES = {'fraude': 'Fraude, détournement', 'corruption': "Corruption, trafic d'influence", 'autre': 'Autre'}

    description = property(lambda s: dechiffrer_secret(s._description), lambda s, v: setattr(s, '_description', chiffrer_secret(v)))
    personnes_impliquees = property(lambda s: dechiffrer_secret(s._personnes), lambda s, v: setattr(s, '_personnes', chiffrer_secret(v)))
    identite = property(lambda s: dechiffrer_secret(s._identite) or {}, lambda s, v: setattr(s, '_identite', chiffrer_secret(v) if v else None))
    statut_libelle = property(lambda s: s.STATUTS.get(s.statut, s.statut))
    categorie_libelle = property(lambda s: s.CATEGORIES.get(s.categorie, s.categorie))
    est_cloture = property(lambda s: s.statut in ('cloture_fonde', 'cloture_non_fonde', 'irrecevable'))
    echeance_accuse = property(lambda s: s.created_at + timedelta(days=7))
    echeance_retour = property(lambda s: (s.date_accuse_reception or s.created_at) + timedelta(days=90))
    referent = property(lambda s: User.query.get(s.referent_id))
    messages = property(lambda s: MessageSignalement.query.filter_by(signalement_id=s.id).order_by(MessageSignalement.created_at).all())


class MessageSignalement(Modele):
    id = Champ(); signalement_id = Champ(); auteur = Champ(); referent_id = Champ(); _contenu = Champ(); interne = Champ(False)
    created_at = Champ()
    contenu = property(lambda s: dechiffrer_secret(s._contenu), lambda s, v: setattr(s, '_contenu', chiffrer_secret(v)))
    referent = property(lambda s: User.query.get(s.referent_id))


class FormuleAbonnement(Modele):
    id = Champ(); nom = Champ(); code = Champ(); description = Champ(); prix_mensuel = Champ(0); prix_annuel = Champ(0)
    max_utilisateurs = Champ(10)


class AbonnementClient(Modele):
    id = Champ(); client_id = Champ(); formule_id = Champ(); date_debut = Champ(); date_fin = Champ(); periode = Champ()
    statut = Champ(); is_renouvellement_auto = Champ(); montant = Champ(); devise = Champ(); methode_paiement = Champ()
    reference_paiement = Champ(); date_prochain_paiement = Champ(); created_at = Champ()


class PaiementEnLigne(Modele):
    id = Champ(); client_id = Champ(); formule_id = Champ(); periode = Champ('mensuel'); montant = Champ(); devise = Champ()
    prestataire = Champ(); reference = Champ(); reference_prestataire = Champ(); statut = Champ('initie'); reponse = Champ()
    abonnement_id = Champ(); initie_par = Champ(); created_at = Champ(); paye_le = Champ()
    formule = property(lambda s: FormuleAbonnement.query.get(s.formule_id))
