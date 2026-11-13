"""
egalyx/kri_connecteurs.py — collecte automatique des KRI depuis les outils du marché.

12 connecteurs prêts à l'emploi : Jira, ServiceNow, Zendesk, Freshdesk, GitHub, GitLab, HubSpot,
Odoo, PagerDuty, Datadog, Google Sheets, Airtable.

- Réglage par l'ADMINISTRATEUR de l'organisation (ou le super-admin), depuis la fiche du KRI :
  « Connecter un outil » → choix de l'outil → identifiants + requête → « Tester » (valeur lue tout de
  suite, rien n'est enregistré) → « Enregistrer » (première mesure créée immédiatement).
- Sécurité : chaque connecteur n'appelle QUE l'adresse officielle de l'outil (sous-domaine contrôlé),
  en https, jamais une adresse interne (contrôles d'egalyx/kri_sources_securite.py). Les jetons sont
  chiffrés en base (EGALYX_CLE_CHIFFREMENT) et ne sont jamais réaffichés.
- Collecte automatique : toutes les 15 minutes, les sources arrivées à échéance sont relevées
  (une seule fois même avec plusieurs processus serveur). Coupure : EGALYX_COLLECTE_AUTO=0.
"""
import json
import logging
import re
from datetime import datetime, timedelta
from urllib.parse import quote, urlparse

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

journal = logging.getLogger('egalyx.kri_connecteurs')
DELAI = 15
TAILLE_MAX = 2 * 1024 * 1024
FREQUENCES = [(3600, 'Toutes les heures'), (6 * 3600, 'Toutes les 6 heures'), (86400, 'Une fois par jour'),
              (7 * 86400, 'Une fois par semaine'), (30 * 86400, 'Une fois par mois')]
PAR_FREQUENCE_KRI = {'quotidien': 86400, 'quotidienne': 86400, 'journalier': 86400, 'hebdomadaire': 7 * 86400,
                     'mensuel': 30 * 86400, 'mensuelle': 30 * 86400, 'trimestriel': 30 * 86400}


class ErreurConnecteur(Exception):
    """Message destiné à l'administrateur (sans donnée sensible). Toujours préfixé « Connecteur … »."""


# ======================================================================== outils de validation
SOUS_DOMAINE = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')
NOM_HOTE = re.compile(r'^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$')


def _sous_domaine(v, suffixe, libelle):
    v = (v or '').strip().lower()
    if '://' in v or '.' in v:
        h = urlparse(v if '://' in v else 'https://' + v).hostname or ''
        if h.endswith('.' + suffixe):
            v = h[:-(len(suffixe) + 1)]
    if not SOUS_DOMAINE.match(v):
        raise ErreurConnecteur(f"Connecteur : {libelle} invalide (exemple : monentreprise)")
    return v


def _hote(v, libelle, defaut=None):
    v = (v or defaut or '').strip().lower()
    h = urlparse(v if '://' in v else 'https://' + v).hostname or ''
    if not NOM_HOTE.match(h):
        raise ErreurConnecteur(f"Connecteur : {libelle} invalide (exemple : monentreprise.odoo.com)")
    return h


def _requis(p, cle, libelle, maxi=1000):
    v = (p.get(cle) or '').strip()
    if not v:
        raise ErreurConnecteur(f"Connecteur : « {libelle} » est obligatoire")
    if len(v) > maxi:
        raise ErreurConnecteur(f"Connecteur : « {libelle} » est trop long")
    return v


def nombre(v):
    """'12,5 %' → 12.5 ; '1 234' → 1234 ; True → 1. Lève ErreurConnecteur si ce n'est pas un nombre."""
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v if v is not None else '').strip().replace(' ', '').replace('\xa0', '').replace(' ', '')
    t = t.rstrip('%€$').replace(',', '.')
    try:
        return float(t)
    except ValueError:
        raise ErreurConnecteur("Connecteur : la valeur lue n'est pas un nombre")


def _chemin(d, *cles):
    for c in cles:
        try:
            d = d[c]
        except (KeyError, IndexError, TypeError):
            raise ErreurConnecteur("Connecteur : réponse inattendue de l'outil (la valeur attendue est absente)")
    return d


# ======================================================================== catalogue
# Chaque connecteur : champs du formulaire, construction de la requête, lecture de la valeur.
def _jira(p, s):
    site = _sous_domaine(p.get('site'), 'atlassian.net', 'Site Jira')
    return {'methode': 'POST', 'url': f'https://{site}.atlassian.net/rest/api/3/search/approximate-count',
            'json': {'jql': _requis(p, 'jql', 'Requête JQL', 2000)},
            'auth': (_requis(p, 'email', 'E-mail du compte', 200), s['jeton'])}


def _servicenow(p, s):
    inst = _sous_domaine(p.get('instance'), 'service-now.com', 'Instance ServiceNow')
    table = (p.get('table') or 'incident').strip()
    if not re.match(r'^[a-z0-9_]{1,80}$', table):
        raise ErreurConnecteur("Connecteur : nom de table ServiceNow invalide (exemple : incident)")
    params = {'sysparm_count': 'true'}
    if (p.get('requete') or '').strip():
        params['sysparm_query'] = p['requete'].strip()[:2000]
    return {'methode': 'GET', 'url': f'https://{inst}.service-now.com/api/now/stats/{table}', 'params': params,
            'auth': (_requis(p, 'utilisateur', 'Utilisateur', 200), s['jeton'])}


def _zendesk(p, s):
    sd = _sous_domaine(p.get('sous_domaine'), 'zendesk.com', 'Sous-domaine Zendesk')
    return {'methode': 'GET', 'url': f'https://{sd}.zendesk.com/api/v2/search/count',
            'params': {'query': _requis(p, 'requete', 'Requête', 1000)},
            'auth': (_requis(p, 'email', 'E-mail de l\'agent', 200) + '/token', s['jeton'])}


def _freshdesk(p, s):
    d = _sous_domaine(p.get('domaine'), 'freshdesk.com', 'Domaine Freshdesk')
    q = _requis(p, 'requete', 'Requête', 500).strip('"')
    if '"' in q:
        raise ErreurConnecteur("Connecteur : la requête Freshdesk ne doit pas contenir de guillemets doubles")
    return {'methode': 'GET', 'url': f'https://{d}.freshdesk.com/api/v2/search/tickets', 'params': {'query': f'"{q}"'},
            'auth': (s['jeton'], 'X')}


def _github(p, s):
    return {'methode': 'GET', 'url': 'https://api.github.com/search/issues',
            'params': {'q': _requis(p, 'recherche', 'Recherche', 1000), 'per_page': 1},
            'entetes': {'Authorization': f"Bearer {s['jeton']}", 'Accept': 'application/vnd.github+json',
                        'X-GitHub-Api-Version': '2022-11-28'}}


def _gitlab(p, s):
    hote = _hote(p.get('adresse'), 'Adresse GitLab', 'gitlab.com')
    projet = _requis(p, 'projet', 'Projet', 300)
    params = {}
    if (p.get('etiquettes') or '').strip():
        params['labels'] = p['etiquettes'].strip()[:300]
    return {'methode': 'GET', 'url': f'https://{hote}/api/v4/projects/{quote(projet, safe="")}/issues_statistics',
            'params': params, 'entetes': {'PRIVATE-TOKEN': s['jeton']}}


def _hubspot(p, s):
    objet = (p.get('objet') or 'tickets').strip()
    if objet not in ('tickets', 'deals', 'contacts', 'companies'):
        raise ErreurConnecteur("Connecteur : objet HubSpot invalide")
    filtres = []
    if (p.get('propriete') or '').strip():
        f = {'propertyName': p['propriete'].strip()[:100], 'operator': (p.get('operateur') or 'EQ').strip()}
        if f['operator'] not in ('EQ', 'NEQ', 'LT', 'LTE', 'GT', 'GTE', 'HAS_PROPERTY', 'NOT_HAS_PROPERTY', 'CONTAINS_TOKEN'):
            raise ErreurConnecteur("Connecteur : opérateur HubSpot invalide")
        if f['operator'] not in ('HAS_PROPERTY', 'NOT_HAS_PROPERTY'):
            f['value'] = (p.get('valeur') or '').strip()[:200]
        filtres.append(f)
    return {'methode': 'POST', 'url': f'https://api.hubapi.com/crm/v3/objects/{objet}/search',
            'json': {'filterGroups': [{'filters': filtres}] if filtres else [], 'limit': 1},
            'entetes': {'Authorization': f"Bearer {s['jeton']}"}}


def _odoo(p, s):
    hote = _hote(p.get('adresse'), 'Adresse Odoo')
    modele = _requis(p, 'modele', 'Modèle', 100)
    if not re.match(r'^[a-z][a-z0-9_.]{1,99}$', modele):
        raise ErreurConnecteur("Connecteur : modèle Odoo invalide (exemple : account.move)")
    try:
        domaine = json.loads((p.get('domaine') or '[]').strip() or '[]')
        assert isinstance(domaine, list)
    except (ValueError, AssertionError):
        raise ErreurConnecteur('Connecteur : filtre Odoo invalide (exemple : [["state", "=", "posted"]])')
    entetes = {'Authorization': f"bearer {s['jeton']}"}
    if (p.get('base') or '').strip():
        entetes['X-Odoo-Database'] = p['base'].strip()[:100]
    return {'methode': 'POST', 'url': f'https://{hote}/json/2/{modele}/search_count', 'json': {'domain': domaine},
            'entetes': entetes}


def _pagerduty(p, s):
    hote = 'api.eu.pagerduty.com' if (p.get('region') or '') == 'eu' else 'api.pagerduty.com'
    statuts = [x for x in (p.get('statuts') or 'triggered,acknowledged').split(',') if x in ('triggered', 'acknowledged', 'resolved')]
    params = {'statuses[]': statuts or ['triggered', 'acknowledged'], 'total': 'true', 'limit': 1, 'date_range': 'all'}
    services = [x.strip() for x in (p.get('services') or '').split(',') if re.match(r'^[A-Z0-9]{5,10}$', x.strip())]
    if services:
        params['service_ids[]'] = services
    return {'methode': 'GET', 'url': f'https://{hote}/incidents', 'params': params,
            'entetes': {'Authorization': f"Token token={s['jeton']}", 'Accept': 'application/vnd.pagerduty+json;version=2'}}


SITES_DATADOG = ('datadoghq.com', 'datadoghq.eu', 'us3.datadoghq.com', 'us5.datadoghq.com', 'ap1.datadoghq.com',
                 'ap2.datadoghq.com', 'ddog-gov.com')


def _datadog(p, s):
    site = (p.get('site') or 'datadoghq.eu').strip()
    if site not in SITES_DATADOG:
        raise ErreurConnecteur("Connecteur : site Datadog invalide")
    fen = {'1h': 3600, '24h': 86400, '7j': 7 * 86400}.get(p.get('fenetre') or '1h', 3600)
    fin = int(datetime.utcnow().timestamp())
    if not s.get('jeton2'):
        raise ErreurConnecteur("Connecteur : la clé d'application Datadog est obligatoire")
    return {'methode': 'GET', 'url': f'https://api.{site}/api/v1/query',
            'params': {'from': fin - fen, 'to': fin, 'query': _requis(p, 'requete', 'Requête de métrique', 1000)},
            'entetes': {'DD-API-KEY': s['jeton'], 'DD-APPLICATION-KEY': s['jeton2']}}


def _lire_datadog(r, p):
    series = _chemin(r, 'series')
    if not series:
        raise ErreurConnecteur("Connecteur : aucune donnée Datadog sur la période (vérifiez la requête)")
    points = [pt for pt in (series[0].get('pointlist') or []) if pt and pt[-1] is not None]
    if not points:
        raise ErreurConnecteur("Connecteur : aucune donnée Datadog sur la période (vérifiez la requête)")
    return points[-1][-1]


def _google_sheets(p, s):
    cid = (p.get('classeur') or '').strip()
    m = re.search(r'/spreadsheets/d/([A-Za-z0-9_-]{20,})', cid)
    cid = m.group(1) if m else cid
    if not re.match(r'^[A-Za-z0-9_-]{20,100}$', cid):
        raise ErreurConnecteur("Connecteur : lien ou identifiant du classeur Google invalide")
    plage = _requis(p, 'cellule', 'Cellule', 100)
    return {'methode': 'GET', 'url': f'https://sheets.googleapis.com/v4/spreadsheets/{cid}/values/{quote(plage, safe="")}',
            'params': {'key': s['jeton']}}


def _lire_sheets(r, p):
    vals = r.get('values') if isinstance(r, dict) else None
    if not vals or not vals[0]:
        raise ErreurConnecteur("Connecteur : la cellule Google Sheets est vide")
    return vals[0][0]


def _airtable(p, s):
    base = _requis(p, 'base', 'Base', 40)
    rec = _requis(p, 'enregistrement', 'Enregistrement', 40)
    if not re.match(r'^app[A-Za-z0-9]{10,}$', base) or not re.match(r'^rec[A-Za-z0-9]{10,}$', rec):
        raise ErreurConnecteur("Connecteur : identifiants Airtable invalides (base appXXXX, enregistrement recXXXX)")
    table = _requis(p, 'table', 'Table', 100)
    return {'methode': 'GET', 'url': f'https://api.airtable.com/v0/{base}/{quote(table, safe="")}/{rec}',
            'entetes': {'Authorization': f"Bearer {s['jeton']}"}}


def _lire_airtable(r, p):
    champs = _chemin(r, 'fields')
    nom = (p.get('champ') or '').strip()
    if nom not in champs:
        raise ErreurConnecteur(f"Connecteur : le champ « {nom} » est vide ou introuvable dans l'enregistrement")
    return champs[nom]


F = lambda nom, libelle, **k: dict(nom=nom, libelle=libelle, **k)  # noqa: E731
JETON = lambda libelle='Jeton d\'API', aide=None: F('jeton', libelle, type='secret', aide=aide)  # noqa: E731

CATALOGUE = [
    {'code': 'jira', 'nom': 'Jira', 'icone': 'fab fa-jira', 'couleur': '#0052CC', 'famille': 'Projets & tickets',
     'mesure': 'Nombre de tickets correspondant à une requête JQL',
     'exemples': ['Vulnérabilités ouvertes de priorité haute', 'Demandes de changement non approuvées', 'Anomalies en production non résolues'],
     'champs': [F('site', 'Site Jira', exemple='monentreprise', aide='La partie avant « .atlassian.net »'),
                F('email', 'E-mail du compte', exemple='controle@monentreprise.com'),
                JETON('Jeton d\'API', 'id.atlassian.com › Sécurité › Créer un jeton d\'API (jeton classique, sans portée)'),
                F('jql', 'Requête JQL', type='zone', exemple='project = SEC AND statusCategory != Done AND priority in (Highest, High)')],
     'construire': _jira, 'lire': lambda r, p: _chemin(r, 'count')},
    {'code': 'servicenow', 'nom': 'ServiceNow', 'icone': 'fas fa-headset', 'couleur': '#62D84E', 'famille': 'Projets & tickets',
     'mesure': "Nombre d'enregistrements d'une table (incidents, changements, problèmes…)",
     'exemples': ['Incidents P1 ouverts', 'Changements d\'urgence du mois', 'Problèmes sans cause racine'],
     'champs': [F('instance', 'Instance', exemple='monentreprise', aide='La partie avant « .service-now.com »'),
                F('utilisateur', 'Utilisateur (compte de service en lecture)'), JETON('Mot de passe'),
                F('table', 'Table', exemple='incident', defaut='incident'),
                F('requete', 'Filtre (requête encodée)', exemple='active=true^priority=1',
                  aide='Dans une liste ServiceNow : clic droit sur le filtre › « Copy query »')],
     'construire': _servicenow, 'lire': lambda r, p: _chemin(r, 'result', 'stats', 'count')},
    {'code': 'zendesk', 'nom': 'Zendesk', 'icone': 'fas fa-life-ring', 'couleur': '#03363D', 'famille': 'Relation client',
     'mesure': 'Nombre de tickets correspondant à une recherche',
     'exemples': ['Réclamations clients non résolues', 'Tickets urgents en attente', 'Plaintes du mois'],
     'champs': [F('sous_domaine', 'Sous-domaine', exemple='monentreprise', aide='La partie avant « .zendesk.com »'),
                F('email', "E-mail de l'agent"), JETON('Jeton d\'API', 'Centre d\'administration › Applications et intégrations › API Zendesk'),
                F('requete', 'Recherche', exemple='type:ticket status<solved tags:reclamation')],
     'construire': _zendesk, 'lire': lambda r, p: _chemin(r, 'count')},
    {'code': 'freshdesk', 'nom': 'Freshdesk', 'icone': 'fas fa-ticket', 'couleur': '#25C16F', 'famille': 'Relation client',
     'mesure': 'Nombre de tickets correspondant à un filtre',
     'exemples': ['Tickets ouverts priorité urgente', 'Réclamations en attente', 'Tickets en retard de SLA'],
     'champs': [F('domaine', 'Domaine', exemple='monentreprise', aide='La partie avant « .freshdesk.com »'),
                JETON('Clé API', 'Photo de profil › Paramètres du profil › Votre clé API'),
                F('requete', 'Filtre', exemple='status:2 AND priority:4', aide='Statuts : 2 ouvert, 3 en attente, 4 résolu, 5 fermé. Priorités : 1 basse à 4 urgente')],
     'construire': _freshdesk, 'lire': lambda r, p: _chemin(r, 'total')},
    {'code': 'github', 'nom': 'GitHub', 'icone': 'fab fa-github', 'couleur': '#24292F', 'famille': 'Informatique & sécurité',
     'mesure': 'Nombre de tickets ou demandes de fusion correspondant à une recherche',
     'exemples': ['Failles de sécurité ouvertes', 'Anomalies critiques non corrigées', 'Demandes de fusion en attente de revue'],
     'champs': [JETON('Jeton d\'accès (fine-grained, lecture seule)', 'Settings › Developer settings › Personal access tokens'),
                F('recherche', 'Recherche', type='zone', exemple='repo:monorg/monappli is:issue is:open label:securite',
                  aide='Même syntaxe que la barre de recherche GitHub ; « is:issue » ou « is:pr » est obligatoire')],
     'construire': _github, 'lire': lambda r, p: _chemin(r, 'total_count')},
    {'code': 'gitlab', 'nom': 'GitLab', 'icone': 'fab fa-gitlab', 'couleur': '#FC6D26', 'famille': 'Informatique & sécurité',
     'mesure': "Nombre de tickets d'un projet (ouverts, fermés ou tous), filtrés par étiquette",
     'exemples': ['Failles ouvertes', 'Incidents de production ouverts', 'Dette technique critique'],
     'champs': [F('adresse', 'Adresse GitLab', exemple='gitlab.com', defaut='gitlab.com', aide='gitlab.com ou votre GitLab hébergé (adresse publique)'),
                F('projet', 'Projet', exemple='monorg/monappli', aide='Chemin du projet ou son numéro'),
                JETON('Jeton d\'accès (read_api)'),
                F('etiquettes', 'Étiquettes (facultatif)', exemple='securite,critique'),
                F('etat', 'Tickets à compter', type='liste', choix=[('opened', 'Ouverts'), ('closed', 'Fermés'), ('all', 'Tous')], defaut='opened')],
     'construire': _gitlab, 'lire': lambda r, p: _chemin(r, 'statistics', 'counts', p.get('etat') or 'opened')},
    {'code': 'hubspot', 'nom': 'HubSpot', 'icone': 'fab fa-hubspot', 'couleur': '#FF7A59', 'famille': 'Relation client',
     'mesure': "Nombre de tickets, affaires, contacts ou entreprises correspondant à un filtre",
     'exemples': ['Réclamations ouvertes', 'Affaires sans propriétaire', 'Contacts sans consentement'],
     'champs': [JETON("Jeton d'application privée", 'Paramètres › Intégrations › Applications privées (droits en lecture)'),
                F('objet', 'Objet', type='liste', choix=[('tickets', 'Tickets'), ('deals', 'Affaires'), ('contacts', 'Contacts'), ('companies', 'Entreprises')], defaut='tickets'),
                F('propriete', 'Propriété filtrée (facultatif)', exemple='hs_pipeline_stage'),
                F('operateur', 'Condition', type='liste', choix=[('EQ', 'est égal à'), ('NEQ', 'est différent de'), ('GT', 'est supérieur à'),
                                                                 ('LT', 'est inférieur à'), ('HAS_PROPERTY', 'est renseignée'), ('NOT_HAS_PROPERTY', "n'est pas renseignée")], defaut='EQ'),
                F('valeur', 'Valeur', exemple='1')],
     'construire': _hubspot, 'lire': lambda r, p: _chemin(r, 'total')},
    {'code': 'odoo', 'nom': 'Odoo', 'icone': 'fas fa-cubes', 'couleur': '#714B67', 'famille': 'Gestion & finance',
     'mesure': "Nombre d'enregistrements Odoo correspondant à un filtre (factures, achats, stocks…)",
     'exemples': ['Factures clients échues impayées', 'Factures fournisseurs non validées', 'Bons de commande sans réception'],
     'champs': [F('adresse', 'Adresse Odoo', exemple='monentreprise.odoo.com'),
                F('base', 'Base de données (facultatif)', exemple='monentreprise'),
                JETON('Clé API', 'Mon profil › Sécurité du compte › Nouvelle clé API (Odoo 19 ou plus, offre « Custom »)'),
                F('modele', 'Modèle', exemple='account.move'),
                F('domaine', 'Filtre (domaine Odoo)', type='zone',
                  exemple='[["move_type", "=", "out_invoice"], ["payment_state", "=", "not_paid"], ["invoice_date_due", "<", "2026-11-13"]]')],
     'construire': _odoo, 'lire': lambda r, p: r},
    {'code': 'pagerduty', 'nom': 'PagerDuty', 'icone': 'fas fa-bell', 'couleur': '#06AC38', 'famille': 'Informatique & sécurité',
     'mesure': "Nombre d'incidents déclenchés ou en cours de traitement",
     'exemples': ['Incidents de production ouverts', 'Alertes non acquittées', 'Incidents d\'un service critique'],
     'champs': [JETON("Clé d'API REST (lecture seule)", 'Integrations › API Access Keys'),
                F('region', 'Région du compte', type='liste', choix=[('us', 'États-Unis'), ('eu', 'Europe')], defaut='eu'),
                F('statuts', 'Incidents à compter', type='liste',
                  choix=[('triggered,acknowledged', 'Ouverts (déclenchés + acquittés)'), ('triggered', 'Non acquittés'), ('acknowledged', 'Acquittés')],
                  defaut='triggered,acknowledged'),
                F('services', 'Services (facultatif)', exemple='PABC123,PXYZ789', aide='Identifiants des services, séparés par des virgules')],
     'construire': _pagerduty, 'lire': lambda r, p: _chemin(r, 'total')},
    {'code': 'datadog', 'nom': 'Datadog', 'icone': 'fas fa-dog', 'couleur': '#632CA6', 'famille': 'Informatique & sécurité',
     'mesure': "Dernière valeur d'une métrique (disponibilité, erreurs, temps de réponse…)",
     'exemples': ["Taux d'erreur de l'application", 'Disponibilité du site', 'Espace disque restant'],
     'champs': [F('site', 'Site Datadog', type='liste', choix=[(x, x) for x in SITES_DATADOG], defaut='datadoghq.eu'),
                JETON("Clé d'API", 'Organization Settings › API Keys'),
                F('jeton2', "Clé d'application", type='secret', aide='Organization Settings › Application Keys (portée timeseries_query)'),
                F('requete', 'Requête de métrique', exemple='avg:trace.http.request.errors{env:prod}.as_rate()'),
                F('fenetre', 'Période analysée', type='liste', choix=[('1h', 'Dernière heure'), ('24h', 'Dernières 24 h'), ('7j', '7 derniers jours')], defaut='1h')],
     'construire': _datadog, 'lire': _lire_datadog},
    {'code': 'google_sheets', 'nom': 'Google Sheets', 'icone': 'fas fa-table', 'couleur': '#0F9D58', 'famille': 'Tableurs',
     'mesure': "Valeur d'une cellule (n'importe quel indicateur déjà calculé dans un tableur)",
     'exemples': ['Taux de rotation du personnel', 'Écarts de caisse du mois', 'Ratio de liquidité'],
     'champs': [F('classeur', 'Lien du classeur', exemple='https://docs.google.com/spreadsheets/d/1AbC…/edit',
                  aide='Partage : « Tous les utilisateurs disposant du lien » en lecture'),
                F('cellule', 'Cellule', exemple='KRI!B2', aide='Nom de l\'onglet, point d\'exclamation, cellule'),
                JETON('Clé API Google', 'console.cloud.google.com › API et services › Identifiants (API Google Sheets activée, clé restreinte à cette API)')],
     'construire': _google_sheets, 'lire': _lire_sheets},
    {'code': 'airtable', 'nom': 'Airtable', 'icone': 'fas fa-border-all', 'couleur': '#18BFFF', 'famille': 'Tableurs',
     'mesure': "Valeur d'un champ d'un enregistrement (par exemple un champ calculé « Total »)",
     'exemples': ['Nombre de non-conformités ouvertes', 'Montant des pertes du trimestre', 'Délai moyen de traitement'],
     'champs': [JETON("Jeton d'accès personnel", 'airtable.com/create/tokens (portée data.records:read, base choisie)'),
                F('base', 'Base', exemple='appXXXXXXXXXXXXXX', aide='Dans l\'adresse de la base : la partie qui commence par « app »'),
                F('table', 'Table', exemple='Indicateurs'),
                F('enregistrement', 'Enregistrement', exemple='recXXXXXXXXXXXXXX', aide='Développer l\'enregistrement : l\'adresse se termine par « rec… »'),
                F('champ', 'Champ', exemple='Total')],
     'construire': _airtable, 'lire': _lire_airtable},
]
PAR_CODE = {c['code']: c for c in CATALOGUE}
FAMILLES = []
for _c in CATALOGUE:
    if _c['famille'] not in FAMILLES:
        FAMILLES.append(_c['famille'])


# ======================================================================== appel
def appel(connecteur, parametres, secrets):
    """Interroge l'outil et renvoie la valeur numérique. Lève ErreurConnecteur avec un message utile."""
    import requests
    from egalyx import kri_sources_securite as S
    c = PAR_CODE[connecteur]
    for ch in c['champs']:
        if ch.get('type') == 'secret' and ch['nom'] == 'jeton' and not secrets.get('jeton'):
            raise ErreurConnecteur(f"Connecteur {c['nom']} : « {ch['libelle']} » est obligatoire")
    req = c['construire'](parametres, secrets)
    try:
        S.verifier_url(req['url'])
    except S.SourceRefusee as e:
        raise ErreurConnecteur(f"Connecteur {c['nom']} : {e}")
    try:
        r = requests.request(req['methode'], req['url'], params=req.get('params'), json=req.get('json'),
                             headers=dict({'Accept': 'application/json', 'User-Agent': 'Egalyx-KRI/1.0'}, **req.get('entetes', {})),
                             auth=req.get('auth'), timeout=DELAI, allow_redirects=False, stream=True)
    except requests.Timeout:
        raise ErreurConnecteur(f"Connecteur {c['nom']} : l'outil n'a pas répondu dans les {DELAI} secondes")
    except requests.RequestException:
        raise ErreurConnecteur(f"Connecteur {c['nom']} : connexion impossible (adresse incorrecte ou outil indisponible)")
    code = r.status_code
    if code in (401, 403):
        raise ErreurConnecteur(f"Connecteur {c['nom']} : identifiants refusés (vérifiez le jeton, l'e-mail et les droits de lecture)")
    if code == 404:
        raise ErreurConnecteur(f"Connecteur {c['nom']} : élément introuvable (vérifiez l'adresse, le projet, la table ou la cellule)")
    if code == 429:
        raise ErreurConnecteur(f"Connecteur {c['nom']} : trop de requêtes, l'outil demande d'attendre (nouvel essai plus tard)")
    if 300 <= code < 400:
        raise ErreurConnecteur(f"Connecteur {c['nom']} : l'adresse redirige ailleurs (vérifiez le sous-domaine)")
    if code >= 400:
        detail = ''
        try:
            corps = r.json()
            detail = json.dumps(corps.get('errorMessages') or corps.get('message') or corps.get('error')
                                or corps.get('errors') or '', ensure_ascii=False)[:200] if isinstance(corps, dict) else ''
        except ValueError:
            pass
        raise ErreurConnecteur(f"Connecteur {c['nom']} : requête refusée ({code}). Vérifiez la requête ou le filtre."
                               + (f" Message de l'outil : {detail}" if detail and detail != '""' else ''))
    contenu = b''
    for bloc in r.iter_content(65536):
        contenu += bloc
        if len(contenu) > TAILLE_MAX:
            raise ErreurConnecteur(f"Connecteur {c['nom']} : réponse trop volumineuse")
    try:
        donnees = json.loads(contenu.decode('utf-8') or 'null')
    except ValueError:
        raise ErreurConnecteur(f"Connecteur {c['nom']} : réponse inattendue de l'outil (pas du JSON)")
    try:
        return nombre(c['lire'](donnees, parametres))
    except ErreurConnecteur as e:
        raise ErreurConnecteur(str(e).replace('Connecteur :', f"Connecteur {c['nom']} :", 1))


# ======================================================================== stockage
def _secrets(source):
    from models import dechiffrer_secret
    a = source.auth_config or {}
    return {k: dechiffrer_secret(a.get(k + '_chiffre')) for k in ('jeton', 'jeton2') if a.get(k + '_chiffre')}


def lire_source(source):
    cfg = source.config_connexion or {}
    return {'valeur': appel(cfg['connecteur'], cfg.get('parametres') or {}, _secrets(source)), 'outil': cfg['connecteur']}


def _patcher_moteur():
    try:
        import collecte_engine
    except ImportError:
        return
    M = collecte_engine.CollecteEngine
    if getattr(M, '_egalyx_connecteurs', False):
        return
    precedent = M._recuperer_donnees_brutes

    def _recuperer_donnees_brutes(self, source):
        cfg = source.config_connexion or {}
        if source.type_source == 'api' and cfg.get('connecteur') in PAR_CODE:
            try:
                return lire_source(source)
            except ErreurConnecteur as e:
                from egalyx import kri_sources_securite as S
                raise S.SourceRefusee(str(e))
        return precedent(self, source)
    M._recuperer_donnees_brutes = _recuperer_donnees_brutes
    M._egalyx_connecteurs = True


# ======================================================================== droits
def peut_connecter(kri):
    u = current_user
    if not getattr(u, 'is_authenticated', False) or kri is None:
        return False
    if getattr(u, 'is_super_admin', False):
        return True
    return (u.role == 'admin' or bool(getattr(u, 'is_client_admin', False))) and kri.client_id == u.client_id


def _kri(kri_id):
    import models as M
    k = M.db.session.get(M.KRI, kri_id)
    if k is None or not peut_connecter(k):
        abort(404)
    return k


def liens_connecteur(kri):
    import models as M
    return [l for l in M.SourceKRILink.query.filter_by(kri_id=kri.id).all()
            if (l.source and (l.source.config_connexion or {}).get('connecteur') in PAR_CODE)]


# ======================================================================== pages
def page(kri_id):
    import models as M
    from models import chiffrer_secret, db
    kri = _kri(kri_id)
    code = request.values.get('outil')
    c = PAR_CODE.get(code)
    existants = liens_connecteur(kri)
    resultat, erreur = None, None
    valeurs = {ch['nom']: ch.get('defaut', '') for ch in (c['champs'] if c else []) if ch.get('type') != 'secret'}
    freq_defaut = PAR_FREQUENCE_KRI.get((kri.frequence_mesure or '').strip().lower(), 86400)
    frequence = freq_defaut
    if request.method == 'POST' and c:
        valeurs = {ch['nom']: (request.form.get(ch['nom']) or '').strip() for ch in c['champs'] if ch.get('type') != 'secret'}
        secrets = {ch['nom']: (request.form.get(ch['nom']) or '').strip() for ch in c['champs'] if ch.get('type') == 'secret'}
        try:
            frequence = int(request.form.get('frequence') or freq_defaut)
        except ValueError:
            frequence = freq_defaut
        if frequence not in dict(FREQUENCES):
            frequence = freq_defaut
        try:
            valeur = appel(code, valeurs, secrets)
        except ErreurConnecteur as e:
            erreur = str(e)
        else:
            if request.form.get('action') != 'enregistrer':
                resultat = valeur
            else:
                req = c['construire'](valeurs, secrets)
                src = M.SourceDonnee(
                    nom=f"{c['nom']} — {kri.nom}"[:100], description=f"Connecteur {c['nom']} pour le KRI « {kri.nom} »",
                    type_source='api', config_connexion={'connecteur': code, 'parametres': valeurs, 'url': req['url']},
                    auth_config={k + '_chiffre': chiffrer_secret(v) for k, v in secrets.items() if v},
                    frequence_rafraichissement=frequence, statut='actif', client_id=kri.client_id, created_by=current_user.id,
                    prochaine_execution=datetime.utcnow() + timedelta(seconds=frequence))
                db.session.add(src)
                db.session.flush()
                db.session.add(M.SourceKRILink(source_id=src.id, kri_id=kri.id, chemin_donnee='$.valeur', est_actif=True,
                                               mapping_config={}, validation_regles={}))
                db.session.commit()
                from collecte_engine import CollecteEngine
                res = CollecteEngine(None, db).collecter_source(src.id, force=True)
                try:
                    from egalyx.commun import journaliser
                    journaliser('kri_connecteur_ajoute', {'kri': kri.id, 'outil': code, 'source': src.id}, client_id=kri.client_id)
                except Exception:  # noqa: BLE001
                    pass
                if res.get('kri_collectes'):
                    flash(f"{c['nom']} est connecté : première mesure enregistrée ({res['kri_collectes'][0]['valeur']:g}). "
                          f"Relevé automatique : {dict(FREQUENCES)[frequence].lower()}.", 'success')
                else:
                    flash(f"{c['nom']} est connecté, mais la première mesure n'a pas pu être enregistrée : "
                          f"{(res.get('erreurs') or [{}])[0].get('error') or (res.get('erreurs') or [{}])[0].get('global') or 'voir la source'}", 'warning')
                return redirect(url_for('kri_connecteur', kri_id=kri.id))
    return render_template('egalyx/kri_connecteur.html', kri=kri, catalogue=CATALOGUE, familles=FAMILLES, c=c,
                           valeurs=valeurs, resultat=resultat, erreur=erreur, frequences=FREQUENCES, frequence=frequence,
                           existants=existants)


def action(kri_id, lien_id):
    import models as M
    from models import db
    kri = _kri(kri_id)
    lien = next((l for l in liens_connecteur(kri) if l.id == lien_id), None)
    if lien is None:
        abort(404)
    src = lien.source
    if request.form.get('action') == 'collecter':
        from collecte_engine import CollecteEngine
        res = CollecteEngine(None, db).collecter_source(src.id, force=True)
        if res.get('kri_collectes'):
            flash(f"Mesure relevée : {res['kri_collectes'][0]['valeur']:g}.", 'success')
        else:
            e = (res.get('erreurs') or [{}])[0]
            flash(f"Relevé impossible : {e.get('error') or e.get('global') or res.get('error') or 'erreur inconnue'}", 'warning')
    elif request.form.get('action') == 'supprimer':
        nom = (src.config_connexion or {}).get('connecteur')
        db.session.delete(lien)
        db.session.flush()
        if not M.SourceKRILink.query.filter_by(source_id=src.id).count():
            db.session.delete(src)
        db.session.commit()
        flash(f"Connexion {PAR_CODE.get(nom, {}).get('nom', '')} supprimée. Les mesures déjà relevées sont conservées.", 'success')
    return redirect(url_for('kri_connecteur', kri_id=kri.id))


# ======================================================================== relevé automatique
def relever_echeances(app, maintenant=None):
    """Relève les sources arrivées à échéance. Chaque source est « réservée » en base avant d'être relevée :
    deux processus serveur ne la relèvent jamais en même temps."""
    import models as M
    from models import db
    from sqlalchemy import or_
    with app.app_context():
        maintenant = maintenant or datetime.utcnow()
        dues = [s.id for s in M.SourceDonnee.query.filter(
            M.SourceDonnee.statut.in_(('actif', 'erreur')),
            or_(M.SourceDonnee.prochaine_execution.is_(None), M.SourceDonnee.prochaine_execution <= maintenant)).limit(200)]
        from collecte_engine import CollecteEngine
        moteur, faits = CollecteEngine(app, db), 0
        for sid in dues:
            pris = db.session.query(M.SourceDonnee).filter(
                M.SourceDonnee.id == sid,
                or_(M.SourceDonnee.prochaine_execution.is_(None), M.SourceDonnee.prochaine_execution <= maintenant)
            ).update({'prochaine_execution': maintenant + timedelta(minutes=30)}, synchronize_session=False)
            db.session.commit()
            if not pris:
                continue
            try:
                moteur.collecter_source(sid, force=True)
                faits += 1
            except Exception as e:  # noqa: BLE001
                journal.warning("Relevé de la source %s : %r", sid, e)
                db.session.rollback()
        return faits


def _demarrer_releve(app):
    import os
    if os.environ.get('EGALYX_COLLECTE_AUTO', '1') == '0' or app.config.get('TESTING') or getattr(app, '_egalyx_releve', False):
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        sch = BackgroundScheduler(daemon=True)
        sch.add_job(lambda: relever_echeances(app), 'interval', minutes=15, id='egalyx_releve_kri',
                    replace_existing=True, max_instances=1, coalesce=True, next_run_time=datetime.now() + timedelta(minutes=1))
        sch.start()
        app._egalyx_releve = True
    except Exception as e:  # noqa: BLE001
        journal.warning("Relevé automatique des KRI non démarré : %r", e)


# ======================================================================== enregistrement
def enregistrer(app):
    _patcher_moteur()
    app.add_url_rule('/kri/<int:kri_id>/connecteur', 'kri_connecteur', login_required(page), methods=['GET', 'POST'])
    app.add_url_rule('/kri/<int:kri_id>/connecteur/<int:lien_id>', 'kri_connecteur_action', login_required(action), methods=['POST'])
    app.jinja_env.globals['peut_connecter_kri'] = peut_connecter
    app.jinja_env.globals['connecteurs_kri'] = lambda kri: [(l, PAR_CODE[l.source.config_connexion['connecteur']])
                                                           for l in liens_connecteur(kri)] if kri is not None else []
    try:   # messages des connecteurs lisibles à l'écran (egalyx/kri_sources_securite masque les autres)
        from egalyx import kri_sources_securite as S
        if not getattr(S, '_prefixe_connecteur', False):
            ancien = S._message_public
            S._message_public = lambda m: str(m) if str(m or '').startswith('Connecteur') else ancien(m)
            S._prefixe_connecteur = True
    except ImportError:
        pass
    _demarrer_releve(app)
