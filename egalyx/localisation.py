"""
egalyx/localisation.py — heure et devise de chaque organisation.

Réglages (table clients) : fuseau_horaire (ex. Africa/Abidjan) et devise (code ISO : EUR, XOF…).
Le super admin les règle pour chaque organisation (/super-admin/client/<id>/localisation) ; l'administrateur
de l'organisation peut aussi régler les siens (/client-admin/localisation).

Ce que ça change :
  - HEURES : l'application enregistre les heures en temps universel (UTC). À l'affichage, toute heure est
    convertie dans le fuseau de l'organisation de la personne connectée : dans les gabarits (x.strftime(...)
    avec une heure, x.hour, filtres format_datetime, datetime…) sans avoir à modifier les pages.
    Une date seule (sans heure) n'est jamais décalée. Les heures SAISIES par l'utilisateur (date d'occurrence
    d'un incident, ouverture d'un questionnaire, publication d'un article) sont déjà à l'heure locale :
    elles sont repérées au chargement et ne sont pas converties.
  - AUJOURD'HUI : aujourdhui() / maintenant() donnent la date et l'heure locales de l'organisation, pour les
    échéances (« en retard », « à faire cette semaine »…).
  - MONTANTS : filtre {{ x|montant }} -> « 1 500 000 FCFA », « 1 500,50 € » ; {{ devise() }} -> symbole.
"""
import logging
from datetime import date, datetime, timedelta, timezone

journal = logging.getLogger('egalyx.localisation')

try:
    from zoneinfo import ZoneInfo, available_timezones
except ImportError:  # pragma: no cover
    ZoneInfo = None
    available_timezones = lambda: set()  # noqa: E731

# code -> (symbole, décimales, symbole avant le montant ?, libellé)
DEVISES = {
    'EUR': ('€', 2, False, 'Euro'),
    'XOF': ('FCFA', 0, False, 'Franc CFA (UEMOA)'),
    'XAF': ('FCFA', 0, False, 'Franc CFA (CEMAC)'),
    'USD': ('$', 2, True, 'Dollar américain'),
    'CAD': ('$ CA', 2, False, 'Dollar canadien'),
    'GBP': ('£', 2, True, 'Livre sterling'),
    'CHF': ('CHF', 2, False, 'Franc suisse'),
    'MAD': ('DH', 2, False, 'Dirham marocain'),
    'TND': ('DT', 3, False, 'Dinar tunisien'),
    'DZD': ('DA', 2, False, 'Dinar algérien'),
    'GNF': ('GNF', 0, False, 'Franc guinéen'),
    'CDF': ('FC', 2, False, 'Franc congolais'),
    'MGA': ('Ar', 0, False, 'Ariary malgache'),
    'MUR': ('Rs', 2, False, 'Roupie mauricienne'),
    'NGN': ('₦', 2, True, 'Naira'),
    'GHS': ('GH₵', 2, True, 'Cedi'),
    'KES': ('KSh', 2, True, 'Shilling kényan'),
    'RWF': ('FRw', 0, False, 'Franc rwandais'),
    'XPF': ('F CFP', 0, False, 'Franc Pacifique'),
}
# fuseaux proposés en premier (tous les fuseaux IANA restent acceptés)
FUSEAUX_COURANTS = [
    ('Africa/Abidjan', "Abidjan, Dakar, Bamako, Ouagadougou, Lomé, Conakry (UTC+0)"),
    ('Africa/Lagos', "Cotonou, Lagos, Niamey, Douala, Libreville, Brazzaville, Kinshasa (UTC+1)"),
    ('Africa/Casablanca', "Casablanca, Rabat"),
    ('Africa/Algiers', "Alger (UTC+1)"),
    ('Africa/Tunis', "Tunis (UTC+1)"),
    ('Africa/Lubumbashi', "Lubumbashi, Kigali, Bujumbura (UTC+2)"),
    ('Africa/Johannesburg', "Johannesburg (UTC+2)"),
    ('Africa/Nairobi', "Nairobi (UTC+3)"),
    ('Indian/Antananarivo', "Antananarivo (UTC+3)"),
    ('Indian/Mauritius', "Port-Louis (UTC+4)"),
    ('Europe/Paris', "Paris, Bruxelles, Luxembourg, Genève (UTC+1 / été UTC+2)"),
    ('Europe/London', "Londres (UTC+0 / été UTC+1)"),
    ('America/Toronto', "Montréal, Toronto (UTC−5 / été UTC−4)"),
    ('America/New_York', "New York (UTC−5 / été UTC−4)"),
    ('UTC', "Temps universel (UTC)"),
]
DEFAUT_FUSEAU = 'Europe/Paris'


def fuseau_valide(nom):
    if not nom or ZoneInfo is None:
        return False
    try:
        ZoneInfo(nom)
        return True
    except Exception:  # noqa: BLE001
        return False


def _client_id(client_id=None):
    if client_id:
        return client_id
    try:
        from flask import has_request_context
        if has_request_context():
            from egalyx.commun import client_id_courant      # super admin : l'organisation consultée
            return client_id_courant()
    except Exception:  # noqa: BLE001
        pass
    return None


def reglages(client_id=None):
    """(fuseau, code devise) de l'organisation ; mémorisé pour la requête en cours."""
    cid = _client_id(client_id)
    cle = f'_eg_loc_{cid}'
    try:
        from flask import g, has_request_context
        if has_request_context() and hasattr(g, cle):
            return getattr(g, cle)
    except Exception:  # noqa: BLE001
        pass
    fuseau, code = None, None
    if cid:
        try:
            import models as M
            # sans écriture anticipée : lire les réglages ne doit jamais enregistrer à moitié une modification en cours
            with M.db.session.no_autoflush:
                c = M.db.session.get(M.Client, cid)
                if c is not None:
                    fuseau = c.fuseau_horaire
                    code = (getattr(c, 'devise', None) or '').upper() or None
                    if not code and hasattr(M, 'AbonnementClient'):
                        a = M.AbonnementClient.query.filter_by(client_id=cid).order_by(M.AbonnementClient.id.desc()).first()
                        code = (a.devise or '').upper() if a and getattr(a, 'devise', None) else None
        except Exception as e:  # noqa: BLE001
            journal.debug('Réglages de l\'organisation %s illisibles : %s', cid, e)
    import os
    fuseau = fuseau if fuseau_valide(fuseau) else os.environ.get('EGALYX_FUSEAU', DEFAUT_FUSEAU)
    code = code or os.environ.get('EGALYX_DEVISE', 'EUR').upper()
    res = (fuseau, code)
    try:
        from flask import g, has_request_context
        if has_request_context():
            setattr(g, cle, res)
    except Exception:  # noqa: BLE001
        pass
    return res


# ------------------------------------------------------------------ heures
class DateLocale(datetime):
    """Heure saisie par l'utilisateur, déjà à l'heure locale : jamais convertie."""


def vers_local(dt, client_id=None):
    """Heure UTC (naïve, comme en base) -> heure locale de l'organisation (naïve)."""
    if not isinstance(dt, datetime) or isinstance(dt, DateLocale) or ZoneInfo is None:
        return dt
    fuseau = reglages(client_id)[0]
    base = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    try:
        return base.astimezone(ZoneInfo(fuseau)).replace(tzinfo=None)
    except Exception:  # noqa: BLE001
        return dt


def vers_utc(dt, client_id=None):
    """Heure locale saisie (naïve) -> UTC naïve, pour l'enregistrer comme le reste."""
    if not isinstance(dt, datetime) or ZoneInfo is None:
        return dt
    try:
        return dt.replace(tzinfo=ZoneInfo(reglages(client_id)[0])).astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:  # noqa: BLE001
        return dt


def maintenant(client_id=None):
    return vers_local(datetime.utcnow(), client_id)


def aujourdhui(client_id=None):
    return maintenant(client_id).date()


_AVEC_HEURE = ('%H', '%I', '%M', '%p', '%X', '%c', '%T', '%R')


class _HeureLocale:
    """Ce que voit un gabarit à la place de dt.strftime : convertit si le format montre l'heure."""

    def __init__(self, dt):
        self.dt = dt

    def __call__(self, fmt='%d/%m/%Y %H:%M', *a, **k):
        cible = vers_local(self.dt) if any(t in str(fmt) for t in _AVEC_HEURE) else self.dt
        return datetime.strftime(cible, fmt, *a, **k)


def _getattr_local(env_getattr):
    def getattr_(obj, attribute):
        if type(obj) is datetime and obj.tzinfo is None:          # pas DateLocale, pas les dates seules
            if attribute == 'strftime':
                return _HeureLocale(obj)
            if attribute in ('hour', 'minute'):
                return getattr(vers_local(obj), attribute)
        return env_getattr(obj, attribute)
    return getattr_


def _filtre_local(f):
    def filtre(valeur, *a, **k):
        if type(valeur) is datetime and valeur.tzinfo is None:
            valeur = vers_local(valeur)
        return f(valeur, *a, **k)
    filtre.__name__ = getattr(f, '__name__', 'filtre')
    filtre._egalyx_local = True
    return filtre


# heures saisies à l'heure locale : marquées au chargement
SAISIES_LOCALES = {'Incident': ('date_occurrence',), 'Questionnaire': ('date_debut', 'date_fin'), 'Article': ('date_publication',)}


def _marquer(instance, *_a):
    for attr in SAISIES_LOCALES.get(type(instance).__name__, ()):
        v = instance.__dict__.get(attr)
        if type(v) is datetime:
            instance.__dict__[attr] = DateLocale(v.year, v.month, v.day, v.hour, v.minute, v.second, v.microsecond)


# ------------------------------------------------------------------ montants
def devise(client_id=None):
    """Symbole de la devise de l'organisation."""
    code = reglages(client_id)[1]
    return DEVISES.get(code, (code,))[0]


def montant(v, client_id=None, decimales=None, symbole=True):
    """1500000 -> « 1 500 000 FCFA » ; 1500.5 -> « 1 500,50 € » ; None -> ''."""
    if v is None or v == '':
        return ''
    try:
        x = float(v)
    except (TypeError, ValueError):
        return str(v)
    code = reglages(client_id)[1]
    sym, dec, avant, _ = DEVISES.get(code, (code, 2, False, code))
    if decimales is not None:
        dec = decimales
    elif dec and x.is_integer():
        dec = 0
    texte = f'{x:,.{dec}f}'.replace(',', ' ').replace('.', ',')
    if not symbole:
        return texte
    return f'{sym} {texte}' if avant else f'{texte} {sym}'


# ------------------------------------------------------------------ branchement
def enregistrer(app):
    env = app.jinja_env
    if not getattr(env, '_egalyx_heure_locale', False):
        env.getattr = _getattr_local(env.getattr)
        env._egalyx_heure_locale = True
    for nom in ('format_datetime', 'format_datetime_fr', 'datetime', 'local_datetime'):
        f = env.filters.get(nom)
        if f is not None and not getattr(f, '_egalyx_local', False):
            env.filters[nom] = _filtre_local(f)
    env.filters['montant'] = lambda v, decimales=None, symbole=True: montant(v, decimales=decimales, symbole=symbole)
    env.filters['heure_locale'] = vers_local
    env.globals.update(devise=devise, montant=montant, aujourdhui_local=aujourdhui, maintenant_local=maintenant,
                       DEVISES=DEVISES, FUSEAUX_COURANTS=FUSEAUX_COURANTS)
    # devise des incidents (egalyx/incidents.py) : désormais celle de l'organisation
    env.globals['devise_incidents'] = devise
    try:
        from egalyx import incidents as _inc
        _inc.devise_client = devise
    except Exception:  # noqa: BLE001
        pass
    import models as M
    from sqlalchemy import event
    for nom in SAISIES_LOCALES:
        modele = getattr(M, nom, None)
        if modele is not None and not getattr(modele, '_egalyx_saisie_locale', False):
            event.listen(modele, 'load', _marquer)
            event.listen(modele, 'refresh', _marquer)
            modele._egalyx_saisie_locale = True
