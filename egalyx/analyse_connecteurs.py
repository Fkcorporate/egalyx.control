"""
egalyx/analyse_connecteurs.py — connecteurs de l'analyse de données (lot 3) : lire les données d'audit directement
dans les systèmes du client, sans export manuel.

Trois familles :
  - Bases de données (lecture seule, requête SELECT) : PostgreSQL, MySQL / MariaDB, SQL Server, Oracle. C'est la voie
    pour les systèmes sans interface en ligne : Sage 100 / Saari (SQL Server), systèmes bancaires centraux (Temenos T24,
    Oracle Flexcube, Sopra Amplitude…) au travers de vues préparées par la DSI. Des modèles de requêtes sont fournis.
  - Fichiers déposés : SFTP, lien https d'export, SharePoint / OneDrive (Microsoft 365), Google Drive.
  - Logiciels de gestion par leur API officielle : Odoo, Microsoft Dynamics 365 Business Central, Xero, QuickBooks Online,
    Zoho Books. Les données arrivent déjà rangées dans les colonnes de l'outil.

Le connecteur ne fait que LIRE et rendre un tableau (en-têtes + lignes) ou un fichier ; la suite (correspondance des
colonnes, contrôle de qualité, empreinte, tests) est celle de l'import manuel (egalyx/analyse_moteur.py).

Sécurité :
  - adresses : https uniquement pour les API ; domaines officiels pour les logiciels en ligne ; pour les bases, SFTP et
    liens https, l'hôte doit être PUBLIC (jamais une adresse interne du serveur) sauf EGALYX_SOURCES_RESEAU_PRIVE=1
    (installation dans le réseau du client) ;
  - aucune redirection suivie (sauf le lien de téléchargement Microsoft, vérifié) ; délais et tailles maximaux ;
  - requêtes SQL : une seule instruction SELECT / WITH, transaction en lecture seule quand la base le permet, délai
    maximal ; utilisez un compte de base en lecture seule ;
  - secrets chiffrés en base (EGALYX_CLE_CHIFFREMENT), jamais réaffichés ; messages d'erreur sans secret.
"""
import base64
import csv
import fnmatch
import io
import json
import os
import re
import time
from datetime import date, datetime, timedelta
from urllib.parse import quote, urlparse

from egalyx import analyse_moteur as am

DELAI = 30
TAILLE_MAX = 15 * 1024 * 1024
LIGNES_MAX = am.MAX_LIGNES
PAGES_MAX = 400


class ErreurSource(Exception):
    """Message destiné à l'utilisateur (sans donnée sensible)."""


class Extraction:
    """Résultat d'une extraction : soit un fichier (octets + nom), soit un tableau (en-têtes + lignes)."""

    def __init__(self, octets=None, nom=None, entetes=None, lignes=None, correspondance=None, secrets_a_jour=None, info=''):
        self.octets, self.nom = octets, nom
        self.entetes, self.lignes = entetes, lignes
        self.correspondance = correspondance or {}
        self.secrets_a_jour = secrets_a_jour or {}       # jetons renouvelés par l'éditeur (à réenregistrer)
        self.info = info

    def en_octets(self):
        """Contenu figé, pour l'empreinte et la conservation : le fichier, ou le tableau en CSV."""
        if self.octets is not None:
            return self.octets
        b = io.StringIO()
        w = csv.writer(b, delimiter=';')
        w.writerow(self.entetes)
        for l in self.lignes:
            w.writerow(['' if v is None else (v.isoformat() if isinstance(v, (date, datetime)) else v) for v in l])
        return b.getvalue().encode('utf-8')

    def nom_fichier(self, source, jeu):
        return self.nom or f'{source}_{jeu}_{datetime.utcnow():%Y%m%d_%H%M}.csv'


# ====================================================================== sécurité réseau
def reseau_prive_autorise():
    return os.environ.get('EGALYX_SOURCES_RESEAU_PRIVE') == '1'


def verifier_hote(hote, libelle='Serveur'):
    hote = (hote or '').strip().lower()
    if not re.fullmatch(r'[a-z0-9.\-:\[\]]{1,253}', hote):
        raise ErreurSource(f'{libelle} : adresse invalide.')
    if reseau_prive_autorise():
        return hote
    from egalyx.kri_sources_securite import SourceRefusee, hote_public
    try:
        public = hote_public(hote)
    except SourceRefusee:
        raise ErreurSource(f'{libelle} : adresse introuvable.')
    if not public:
        raise ErreurSource(f'{libelle} : adresse interne ou privée refusée. Ouvrez l’accès depuis Internet (pare-feu limité aux '
                           'adresses du serveur Egalyx), ou installez Egalyx dans votre réseau.')
    return hote


def verifier_url(url, domaines=None, libelle='Adresse'):
    u = urlparse((url or '').strip())
    if u.scheme != 'https' or not u.hostname:
        raise ErreurSource(f'{libelle} : seules les adresses https:// sont acceptées.')
    if u.username or u.password:
        raise ErreurSource(f'{libelle} : pas d’identifiants dans l’adresse, utilisez les champs prévus.')
    h = u.hostname.lower()
    if domaines is not None:
        if not any(h == d or h.endswith('.' + d) for d in domaines):
            raise ErreurSource(f'{libelle} : seul le domaine officiel est accepté ({", ".join(domaines)}).')
        return url
    verifier_hote(h, libelle)
    return url


def http(methode, url, domaines=None, entetes=None, params=None, donnees=None, json_=None, auth=None, libelle='Service',
         binaire=False, suivre=None):
    """Appel https contrôlé. `suivre` : domaines vers lesquels une redirection est acceptée (téléchargements)."""
    import requests
    verifier_url(url, domaines, libelle)
    for _essai in range(3):
        try:
            r = requests.request(methode, url, headers=dict({'User-Agent': 'Egalyx-Analyse/1.0'}, **(entetes or {})), params=params,
                                 data=donnees, json=json_, auth=auth, timeout=DELAI, allow_redirects=False, stream=True)
        except requests.Timeout:
            raise ErreurSource(f'{libelle} : pas de réponse dans les {DELAI} secondes.')
        except requests.RequestException:
            raise ErreurSource(f'{libelle} : connexion impossible (adresse incorrecte ou service indisponible).')
        if r.status_code in (301, 302, 303, 307, 308) and suivre:
            url = r.headers.get('Location', '')
            verifier_url(url, suivre, libelle)
            methode, params, donnees, json_, auth = 'GET', None, None, None, None
            entetes = {}
            continue
        if r.status_code == 429:
            time.sleep(min(int(r.headers.get('Retry-After') or 2), 5))
            continue
        break
    code = r.status_code
    if code in (401, 403):
        raise ErreurSource(f'{libelle} : identifiants refusés ou droits insuffisants (lecture).')
    if code == 404:
        raise ErreurSource(f'{libelle} : élément introuvable (vérifiez l’adresse, la société, le chemin ou l’identifiant).')
    if 300 <= code < 400:
        raise ErreurSource(f'{libelle} : l’adresse redirige ailleurs (vérifiez-la).')
    if code >= 400:
        detail = ''
        try:
            corps = r.json()
            if isinstance(corps, dict):
                detail = str(corps.get('error_description') or corps.get('message') or corps.get('Message') or corps.get('error')
                             or corps.get('Detail') or '')[:200]
        except ValueError:
            pass
        raise ErreurSource(f'{libelle} : requête refusée ({code}).' + (f' Message du service : {detail}' if detail else ''))
    contenu = b''
    for bloc in r.iter_content(65536):
        contenu += bloc
        if len(contenu) > TAILLE_MAX:
            raise ErreurSource(f'{libelle} : réponse trop volumineuse (15 Mo au plus) ; réduisez la période.')
    if binaire:
        return contenu, r.headers
    try:
        return json.loads(contenu.decode('utf-8') or 'null')
    except ValueError:
        raise ErreurSource(f'{libelle} : réponse inattendue (pas du JSON).')


def jeton_oauth(url_jeton, domaines, donnees, auth=None, libelle='Service'):
    r = http('POST', url_jeton, domaines, donnees=donnees, auth=auth, libelle=libelle,
             entetes={'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'})
    if not isinstance(r, dict) or not r.get('access_token'):
        raise ErreurSource(f'{libelle} : jeton d’accès non obtenu (vérifiez les identifiants de l’application).')
    return r


# ====================================================================== utilitaires
def requis(p, cle, libelle):
    v = (p.get(cle) or '').strip() if isinstance(p.get(cle), str) else p.get(cle)
    if not v:
        raise ErreurSource(f'« {libelle} » est obligatoire.')
    return v


def tableau(jeu, enregistrements):
    """Tableau aux colonnes de l'outil : en-têtes = libellés des champs, correspondance exacte."""
    codes = [c[0] for c in am.champs(jeu) if any(c[0] in e for e in enregistrements)] or [c[0] for c in am.champs(jeu)]
    libs = {c[0]: c[1] for c in am.champs(jeu)}
    if len(enregistrements) > LIGNES_MAX:
        raise ErreurSource(f'Plus de {LIGNES_MAX:,} lignes : réduisez la période.'.replace(',', ' '))
    return Extraction(entetes=[libs[c] for c in codes], lignes=[[e.get(c) for c in codes] for e in enregistrements],
                      correspondance={c: libs[c] for c in codes})


def periode_iso(d):
    return d.isoformat() if isinstance(d, (date, datetime)) else (d or '')


def _premier(v, i=0):
    """Odoo renvoie [id, "nom"] pour une relation ; False si vide."""
    return v[i] if isinstance(v, (list, tuple)) and len(v) > i else ('' if v in (False, None) else v)


# ====================================================================== 1. bases de données
REQUETE_INTERDITE = re.compile(r'\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|exec|execute|call|into|'
                               r'attach|pragma|copy|lock|set|commit|rollback|begin|declare|xp_\w+|sp_\w+|dbms_\w+|utl_\w+)\b', re.I)


def verifier_requete(sql):
    s = (sql or '').strip().rstrip(';').strip()
    if not s:
        raise ErreurSource('Requête vide.')
    sans_textes = re.sub(r"'(?:[^']|'')*'", "''", re.sub(r'--[^\n]*|/\*.*?\*/', ' ', s, flags=re.S))
    if ';' in sans_textes:
        raise ErreurSource('Une seule requête, sans « ; ».')
    if not re.match(r'^\s*(select|with)\b', sans_textes, re.I):
        raise ErreurSource('La requête doit commencer par SELECT (ou WITH … SELECT).')
    m = REQUETE_INTERDITE.search(sans_textes)
    if m:
        raise ErreurSource(f'Mot interdit dans une requête de lecture : « {m.group(0).upper()} ».')
    return s


PILOTES = {
    'postgresql': ('postgresql+psycopg2', 5432, 'psycopg2'),
    'mysql': ('mysql+pymysql', 3306, 'pymysql'),
    'sqlserver': ('mssql+pymssql', 1433, 'pymssql'),
    'oracle': ('oracle+oracledb', 1521, 'oracledb'),
}


def _moteur_sql(code, p, s):
    """Moteur SQLAlchemy (remplaçable dans les recettes)."""
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    dialecte, port_defaut, module = PILOTES[code]
    try:
        __import__(module)
    except ImportError:
        raise ErreurSource(f'Pilote « {module} » non installé sur le serveur (requirements.txt).')
    hote = verifier_hote(requis(p, 'hote', 'Serveur'), 'Serveur de base de données')
    args = {}
    if code == 'oracle':
        url = URL.create(dialecte, username=requis(p, 'utilisateur', 'Utilisateur'), password=s.get('mot_de_passe') or '',
                         host=hote, port=int(p.get('port') or port_defaut), query={'service_name': requis(p, 'base', 'Service Oracle')})
    else:
        url = URL.create(dialecte, username=requis(p, 'utilisateur', 'Utilisateur'), password=s.get('mot_de_passe') or '',
                         host=hote, port=int(p.get('port') or port_defaut), database=requis(p, 'base', 'Base'))
    if code == 'postgresql':
        args = {'connect_timeout': 15, 'options': '-c statement_timeout=120000 -c default_transaction_read_only=on',
                'sslmode': 'require' if p.get('ssl', True) not in (False, 'non', '0') else 'prefer'}
    elif code == 'mysql':
        args = {'connect_timeout': 15, 'read_timeout': 120}
    elif code == 'sqlserver':
        args = {'login_timeout': 15, 'timeout': 120}
    return create_engine(url, connect_args=args, pool_pre_ping=False, poolclass=__import__('sqlalchemy.pool', fromlist=['NullPool']).NullPool)


MOTEUR_SQL = {'fabrique': _moteur_sql}


def _sql(code):
    def lire(p, s, jeu, debut=None, fin=None, essai=False):
        from sqlalchemy import text
        extr = (p.get('extractions') or {}).get(jeu) or {}
        if not essai and not (extr.get('requete') or '').strip():
            raise ErreurSource(f'Aucune requête pour « {am.JEUX[jeu]["libelle"]} » dans cette source : complétez-la.')
        sql = verifier_requete(extr.get('requete') if not essai else (extr.get('requete') or ('SELECT 1 AS ok FROM dual' if code == 'oracle' else 'SELECT 1 AS ok')))
        moteur = MOTEUR_SQL['fabrique'](code, p, s)
        valeurs = {}
        if ':debut' in sql:
            valeurs['debut'] = debut
        if ':fin' in sql:
            valeurs['fin'] = fin
        try:
            with moteur.connect() as cx:
                if code == 'mysql':
                    cx.exec_driver_sql('SET SESSION TRANSACTION READ ONLY')
                    cx.exec_driver_sql('SET SESSION MAX_EXECUTION_TIME=120000')
                elif code == 'oracle':
                    cx.exec_driver_sql('SET TRANSACTION READ ONLY')
                res = cx.execute(text(sql), valeurs)
                entetes = [str(c) for c in res.keys()]
                lignes = []
                for l in res:
                    lignes.append(list(l))
                    if len(lignes) > LIGNES_MAX or (essai and len(lignes) >= 5):
                        break
        except ErreurSource:
            raise
        except Exception as e:  # noqa: BLE001
            nom = type(e).__name__
            msg = str(getattr(e, 'orig', e)).split('\n')[0][:160]
            for secret in (s.get('mot_de_passe'),):
                if secret:
                    msg = msg.replace(secret, '***')
            connexion = re.search(r'connect|timeout|timed out|refused|login failed|authentication|password|host|resolve|network|ORA-12|ORA-01017',
                                  msg, re.I) and not re.search(r'no such|does not exist|invalid object|ORA-00942|doesn.t exist|syntax', msg, re.I)
            raise ErreurSource(f'Base de données : {"connexion impossible" if connexion else "requête refusée"} ({msg}).')
        finally:
            moteur.dispose()
        if len(lignes) > LIGNES_MAX:
            raise ErreurSource(f'Plus de {LIGNES_MAX:,} lignes : ajoutez un filtre de période (:debut, :fin).'.replace(',', ' '))
        return Extraction(entetes=entetes, lignes=lignes, info=f'{len(lignes)} ligne(s)')
    return lire


# Modèles de requêtes proposés (à adapter par la DSI) : Sage 100 Comptabilité (SQL Server) et vues génériques.
MODELES_REQUETES = {
    'sage100': {
        'libelle': 'Sage 100 Comptabilité / Gestion commerciale (SQL Server)',
        'requetes': {
            'grand_livre': "SELECT e.EC_No AS [N° écriture], e.EC_Date AS [Date], e.CG_Num AS [Compte], "
                           "CASE WHEN e.EC_Sens = 0 THEN e.EC_Montant END AS [Débit], CASE WHEN e.EC_Sens = 1 THEN e.EC_Montant END AS [Crédit], "
                           "e.EC_Intitule AS [Libellé], e.JO_Num AS [Journal], e.EC_Piece AS [Pièce], e.cbCreateur AS [Saisi par], "
                           "e.cbCreation AS [Date de saisie], e.CT_Num AS [Compte de tiers], e.EC_Lettrage AS [Lettrage] "
                           "FROM F_ECRITUREC e WHERE e.EC_Date BETWEEN :debut AND :fin",
            'fournisseurs': "SELECT t.CT_Num AS [Code fournisseur], t.CT_Intitule AS [Nom], b.BT_Struct + ' ' + b.BT_Banque + ' ' + b.BT_Guichet + ' ' + b.BT_Compte + ' ' + b.BT_Cle AS [RIB], "
                            "t.CT_DateCreate AS [Date de création], t.cbCreateur AS [Créé par], t.CT_Adresse AS [Adresse], t.CT_Telephone AS [Téléphone], "
                            "t.CT_Identifiant AS [NIF], CASE WHEN t.CT_Sommeil = 1 THEN 'Inactif' ELSE 'Actif' END AS [Statut] "
                            "FROM F_COMPTET t LEFT JOIN F_BANQUET b ON b.CT_Num = t.CT_Num AND b.BT_Num = t.BT_Num WHERE t.CT_Type = 1",
            'clients': "SELECT t.CT_Num AS [Code client], t.CT_Intitule AS [Nom], CASE WHEN t.CT_Sommeil = 1 THEN 'Inactif' "
                       "WHEN t.CT_ControlEnc = 2 THEN 'Bloqué' ELSE 'Actif' END AS [Statut], t.CT_Encours AS [Limite de crédit], "
                       "t.CT_DateCreate AS [Date de création] FROM F_COMPTET t WHERE t.CT_Type = 0",
            'factures': "SELECT d.DO_Piece AS [N° facture], d.DO_Tiers AS [Code fournisseur], d.DO_Date AS [Date facture], d.DO_TotalTTC AS [Montant TTC], "
                        "d.DO_Ref AS [Bon de commande], d.cbCreation AS [Date de saisie], d.cbCreateur AS [Saisi par] "
                        "FROM F_DOCENTETE d WHERE d.DO_Domaine = 1 AND d.DO_Type IN (16, 17) AND d.DO_Date BETWEEN :debut AND :fin",
            'ventes': "SELECT d.DO_Piece AS [N° facture], d.DO_Tiers AS [Code client], d.DO_Date AS [Date], "
                      "CASE WHEN d.DO_Type = 7 THEN -d.DO_TotalTTC ELSE d.DO_TotalTTC END AS [Montant TTC], "
                      "CASE WHEN d.DO_Type = 7 THEN 'Avoir' ELSE 'Facture' END AS [Type], d.DO_Ref AS [Facture d'origine] "
                      "FROM F_DOCENTETE d WHERE d.DO_Domaine = 0 AND d.DO_Type IN (6, 7) AND d.DO_Date BETWEEN :debut AND :fin",
        }},
    'vues': {
        'libelle': 'Vues préparées par la DSI (système bancaire, ERP maison)',
        'requetes': {j: f"SELECT * FROM egalyx_{j} WHERE date BETWEEN :debut AND :fin" if am.JEUX[j]['date'] and j not in ('fournisseurs', 'clients', 'salaries')
                     else f"SELECT * FROM egalyx_{j}" for j in am.ORDRE_JEUX},
    },
}


# ====================================================================== 2. fichiers déposés
def _motif(chemin, debut=None, fin=None):
    d = fin or date.today()
    return (chemin or '').replace('{AAAA}', f'{d:%Y}').replace('{MM}', f'{d:%m}').replace('{JJ}', f'{d:%d}')


def _sftp_client(p, s):
    """Session SFTP (remplaçable dans les recettes). Vérifie l'empreinte de la clé du serveur si elle est connue."""
    try:
        import paramiko
    except ImportError:
        raise ErreurSource('Pilote « paramiko » non installé sur le serveur (requirements.txt).')
    hote = verifier_hote(requis(p, 'hote', 'Serveur SFTP'), 'Serveur SFTP')
    t = paramiko.Transport((hote, int(p.get('port') or 22)))
    t.banner_timeout = t.auth_timeout = 20
    try:
        t.start_client(timeout=20)
        cle = t.get_remote_server_key()
        empreinte = 'SHA256:' + base64.b64encode(__import__('hashlib').sha256(cle.asbytes()).digest()).decode().rstrip('=')
        attendue = (p.get('empreinte_hote') or '').strip()
        if attendue and attendue != empreinte:
            raise ErreurSource('SFTP : la clé du serveur a changé (empreinte différente). Vérifiez avec votre DSI avant de continuer.')
        if s.get('cle_privee'):
            k = paramiko.PKey.from_private_key(io.StringIO(s['cle_privee'])) if hasattr(paramiko.PKey, 'from_private_key') \
                else paramiko.RSAKey.from_private_key(io.StringIO(s['cle_privee']))
            t.auth_publickey(requis(p, 'utilisateur', 'Utilisateur'), k)
        else:
            t.auth_password(requis(p, 'utilisateur', 'Utilisateur'), s.get('mot_de_passe') or '')
        return paramiko.SFTPClient.from_transport(t), empreinte, t
    except ErreurSource:
        t.close()
        raise
    except Exception as e:  # noqa: BLE001
        t.close()
        raise ErreurSource(f'SFTP : connexion refusée ({type(e).__name__}). Vérifiez le serveur, l’utilisateur et le mot de passe ou la clé.')


SFTP = {'client': _sftp_client}


def _sftp(p, s, jeu, debut=None, fin=None, essai=False):
    sftp, empreinte, transport = SFTP['client'](p, s)
    try:
        if essai:
            sftp.listdir('.')
            return Extraction(info=f'Connexion établie. Empreinte du serveur : {empreinte}', secrets_a_jour={'_empreinte_hote': empreinte})
        chemin = _motif(requis((p.get('extractions') or {}).get(jeu) or {}, 'chemin', 'Chemin du fichier'), debut, fin)
        dossier, motif = os.path.split(chemin)
        if any(c in motif for c in '*?['):
            noms = [a for a in sftp.listdir_attr(dossier or '.') if fnmatch.fnmatch(a.filename, motif)]
            if not noms:
                raise ErreurSource(f'SFTP : aucun fichier ne correspond à « {chemin} ».')
            plus_recent = max(noms, key=lambda a: a.st_mtime or 0)
            chemin = (dossier + '/' if dossier else '') + plus_recent.filename
        taille = sftp.stat(chemin).st_size or 0
        if taille > TAILLE_MAX:
            raise ErreurSource('SFTP : fichier trop volumineux (15 Mo au plus).')
        with sftp.open(chemin, 'rb') as f:
            octets = f.read(TAILLE_MAX + 1)
        return Extraction(octets=octets, nom=os.path.basename(chemin), secrets_a_jour={'_empreinte_hote': empreinte})
    except ErreurSource:
        raise
    except FileNotFoundError:
        raise ErreurSource('SFTP : fichier introuvable (vérifiez le chemin).')
    except Exception as e:  # noqa: BLE001
        raise ErreurSource(f'SFTP : lecture impossible ({type(e).__name__}).')
    finally:
        try:
            transport.close()
        except Exception:  # noqa: BLE001
            pass


def _nom_depuis(entetes, url, defaut):
    cd = (entetes or {}).get('Content-Disposition') or ''
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd)
    nom = m.group(1) if m else os.path.basename(urlparse(url).path)
    return nom if re.search(r'\.(xlsx|xlsm|csv|txt)$', nom or '', re.I) else defaut


def _https(p, s, jeu, debut=None, fin=None, essai=False):
    extr = (p.get('extractions') or {}).get(jeu) or {}
    url = _motif((extr.get('url') if not essai else (extr.get('url') or p.get('url_essai'))) or '', debut, fin)
    url = requis({'u': url}, 'u', 'Adresse du fichier')
    ent = {}
    if s.get('jeton'):
        ent[(p.get('entete') or 'Authorization').strip()] = ((p.get('prefixe') or 'Bearer') + ' ' + s['jeton']).strip()
    octets, h = http('GET', url, entetes=ent, libelle='Lien https', binaire=True)
    if essai:
        return Extraction(info=f'Fichier lu ({len(octets)} octets).')
    return Extraction(octets=octets, nom=_nom_depuis(h, url, f'{jeu}.csv'))


MS_DOMAINES = ('login.microsoftonline.com', 'graph.microsoft.com')
MS_TELECHARGEMENT = ('sharepoint.com', 'sharepoint.us', '1drv.ms', 'files.1drv.com', 'onedrive.live.com', 'graph.microsoft.com')


def _jeton_microsoft(p, s, portee):
    tenant = requis(p, 'tenant', 'Identifiant du locataire (tenant)').strip()
    if not re.fullmatch(r'[A-Za-z0-9.\-]{3,100}', tenant):
        raise ErreurSource('Identifiant du locataire invalide.')
    return jeton_oauth(f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token', MS_DOMAINES,
                       {'grant_type': 'client_credentials', 'client_id': requis(p, 'client_id', 'ID de l’application'),
                        'client_secret': requis(s, 'secret', 'Secret de l’application'), 'scope': portee},
                       libelle='Microsoft 365')['access_token']


def _m365(p, s, jeu, debut=None, fin=None, essai=False):
    jeton = _jeton_microsoft(p, s, 'https://graph.microsoft.com/.default')
    ent = {'Authorization': f'Bearer {jeton}'}
    site = (p.get('site') or '').strip()
    if site:
        u = urlparse(site if '://' in site else 'https://' + site)
        if not (u.hostname or '').endswith(('.sharepoint.com', '.sharepoint.us')):
            raise ErreurSource('Site SharePoint : adresse du type https://votresociete.sharepoint.com/sites/Finance.')
        info = http('GET', f'https://graph.microsoft.com/v1.0/sites/{u.hostname}:{u.path.rstrip("/") or "/"}', MS_DOMAINES, ent, libelle='SharePoint')
        base = f'https://graph.microsoft.com/v1.0/sites/{info["id"]}/drive'
    else:
        base = f'https://graph.microsoft.com/v1.0/users/{quote(requis(p, "utilisateur", "Utilisateur OneDrive (e-mail)"))}/drive'
    if essai:
        http('GET', base, MS_DOMAINES, ent, libelle='Microsoft 365')
        return Extraction(info='Connexion établie, bibliothèque de documents accessible.')
    chemin = _motif(requis((p.get('extractions') or {}).get(jeu) or {}, 'chemin', 'Chemin du fichier'), debut, fin).strip('/')
    octets, h = http('GET', f'{base}/root:/{quote(chemin)}:/content', MS_DOMAINES, ent, libelle='Microsoft 365', binaire=True,
                     suivre=MS_TELECHARGEMENT)
    return Extraction(octets=octets, nom=os.path.basename(chemin))


GOOGLE_DOMAINES = ('oauth2.googleapis.com', 'www.googleapis.com')


def _jeton_google(s):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    try:
        compte = json.loads(requis(s, 'compte_service', 'Clé du compte de service (JSON)'))
        cle = serialization.load_pem_private_key(compte['private_key'].encode(), password=None)
    except (ValueError, KeyError, TypeError):
        raise ErreurSource('Clé du compte de service Google illisible (collez le fichier JSON téléchargé depuis Google Cloud).')
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b'=')  # noqa: E731
    maintenant = int(time.time())
    corps = b64(json.dumps({'alg': 'RS256', 'typ': 'JWT'}).encode()) + b'.' + b64(json.dumps({
        'iss': compte['client_email'], 'scope': 'https://www.googleapis.com/auth/drive.readonly',
        'aud': 'https://oauth2.googleapis.com/token', 'iat': maintenant, 'exp': maintenant + 3000}).encode())
    signature = b64(cle.sign(corps, padding.PKCS1v15(), hashes.SHA256()))
    return jeton_oauth('https://oauth2.googleapis.com/token', GOOGLE_DOMAINES,
                       {'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer', 'assertion': (corps + b'.' + signature).decode()},
                       libelle='Google Drive')['access_token']


def _google_drive(p, s, jeu, debut=None, fin=None, essai=False):
    ent = {'Authorization': f'Bearer {_jeton_google(s)}'}
    if essai:
        http('GET', 'https://www.googleapis.com/drive/v3/about', GOOGLE_DOMAINES, ent, params={'fields': 'user'}, libelle='Google Drive')
        return Extraction(info='Connexion établie. Partagez les fichiers avec l’adresse du compte de service.')
    ident = requis((p.get('extractions') or {}).get(jeu) or {}, 'fichier', 'Identifiant ou lien du fichier')
    m = re.search(r'/d/([A-Za-z0-9_-]{10,})', ident) or re.search(r'[?&]id=([A-Za-z0-9_-]{10,})', ident)
    fid = m.group(1) if m else ident.strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{10,200}', fid):
        raise ErreurSource('Identifiant de fichier Google Drive invalide.')
    meta = http('GET', f'https://www.googleapis.com/drive/v3/files/{fid}', GOOGLE_DOMAINES, ent,
                params={'fields': 'name,mimeType,size', 'supportsAllDrives': 'true'}, libelle='Google Drive')
    if meta.get('mimeType') == 'application/vnd.google-apps.spreadsheet':
        octets, _h = http('GET', f'https://www.googleapis.com/drive/v3/files/{fid}/export', GOOGLE_DOMAINES, ent, binaire=True, libelle='Google Drive',
                          params={'mimeType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
        return Extraction(octets=octets, nom=(meta.get('name') or jeu) + '.xlsx')
    octets, _h = http('GET', f'https://www.googleapis.com/drive/v3/files/{fid}', GOOGLE_DOMAINES, ent, binaire=True,
                      params={'alt': 'media', 'supportsAllDrives': 'true'}, libelle='Google Drive')
    return Extraction(octets=octets, nom=meta.get('name') or f'{jeu}.csv')


# ====================================================================== 3. logiciels de gestion
# ---- Odoo (API JSON-RPC, clé d'API d'un utilisateur en lecture)
def _odoo_session(p, s):
    url = (requis(p, 'url', 'Adresse Odoo')).strip().rstrip('/')
    if '://' not in url:
        url = 'https://' + url
    verifier_url(url, None if not urlparse(url).hostname.endswith('.odoo.com') else ('odoo.com',), 'Odoo')
    base, db, login, cle = url, requis(p, 'base', 'Base de données Odoo'), requis(p, 'utilisateur', 'Utilisateur (e-mail)'), requis(s, 'cle', 'Clé d’API')

    def rpc(service, methode, *args):
        r = http('POST', base + '/jsonrpc', None if not urlparse(base).hostname.endswith('.odoo.com') else ('odoo.com',),
                 json_={'jsonrpc': '2.0', 'method': 'call', 'params': {'service': service, 'method': methode, 'args': list(args)}, 'id': 1},
                 entetes={'Content-Type': 'application/json'}, libelle='Odoo')
        if isinstance(r, dict) and r.get('error'):
            msg = ((r['error'].get('data') or {}).get('message') or r['error'].get('message') or '')[:160]
            raise ErreurSource(f'Odoo : {msg or "erreur"}')
        return (r or {}).get('result')
    uid = rpc('common', 'authenticate', db, login, cle, {})
    if not uid:
        raise ErreurSource('Odoo : identifiants refusés (base, utilisateur ou clé d’API).')

    def lire(modele, domaine, champs):
        res, offset = [], 0
        for _ in range(PAGES_MAX):
            lot = rpc('object', 'execute_kw', db, uid, cle, modele, 'search_read', [domaine],
                      {'fields': champs, 'limit': 2000, 'offset': offset, 'order': 'id'})
            res += lot or []
            if not lot or len(lot) < 2000:
                return res
            offset += 2000
            if len(res) > LIGNES_MAX:
                raise ErreurSource(f'Odoo : plus de {LIGNES_MAX} lignes ; réduisez la période.')
        return res
    return lire


def _code_compte(v):
    t = str(_premier(v, 1) or '')
    return t.split(' ')[0] if t else ''


def _odoo(p, s, jeu, debut=None, fin=None, essai=False):
    lire = _odoo_session(p, s)
    if essai:
        lire('res.company', [], ['name'])
        return Extraction(info='Connexion établie.')
    per = lambda champ: ([(champ, '>=', periode_iso(debut))] if debut else []) + ([(champ, '<=', periode_iso(fin))] if fin else [])  # noqa: E731
    nom_u = lambda v: _premier(v, 1)  # noqa: E731
    if jeu in ('fournisseurs', 'clients'):
        rang = 'supplier_rank' if jeu == 'fournisseurs' else 'customer_rank'
        partenaires = lire('res.partner', [(rang, '>', 0), ('active', 'in', [True, False])],
                           ['id', 'ref', 'name', 'create_date', 'create_uid', 'vat', 'phone', 'street', 'city', 'active', 'bank_ids', 'credit_limit'])
        if jeu == 'clients':
            return tableau(jeu, [{'code': str(x['id']), 'nom': x['name'], 'statut': 'Actif' if x.get('active') else 'Inactif',
                                  'limite_credit': x.get('credit_limit') or None, 'date_creation': (x.get('create_date') or '')[:10]} for x in partenaires])
        banques = {}
        ids = [x['id'] for x in partenaires]
        if ids:
            for b in lire('res.partner.bank', [('partner_id', 'in', ids)], ['partner_id', 'acc_number', 'write_date']):
                banques.setdefault(_premier(b['partner_id']), b)
        return tableau(jeu, [{'code': str(x['id']), 'nom': x['name'], 'rib': (banques.get(x['id']) or {}).get('acc_number') or '',
                              'date_creation': (x.get('create_date') or '')[:10], 'cree_par': nom_u(x.get('create_uid')),
                              'date_modif_rib': ((banques.get(x['id']) or {}).get('write_date') or '')[:10],
                              'adresse': ' '.join(v for v in (x.get('street') or '', x.get('city') or '') if v), 'telephone': x.get('phone') or '',
                              'nif': x.get('vat') or '', 'statut': 'Actif' if x.get('active') else 'Inactif'} for x in partenaires])
    if jeu in ('factures', 'ventes'):
        types = ['in_invoice'] if jeu == 'factures' else ['out_invoice', 'out_refund']
        mv = lire('account.move', [('move_type', 'in', types), ('state', '=', 'posted')] + per('invoice_date'),
                  ['name', 'partner_id', 'invoice_date', 'amount_total', 'amount_total_signed', 'invoice_origin', 'create_date', 'create_uid',
                   'move_type', 'reversed_entry_id', 'invoice_user_id', 'currency_id'])
        if jeu == 'factures':
            return tableau(jeu, [{'numero': x['name'], 'fournisseur': str(_premier(x['partner_id'])), 'date': x['invoice_date'],
                                  'montant': x['amount_total'], 'commande': x.get('invoice_origin') or '', 'date_saisie': (x.get('create_date') or '')[:10],
                                  'saisi_par': nom_u(x.get('create_uid')), 'devise': nom_u(x.get('currency_id'))} for x in mv])
        return tableau(jeu, [{'numero': x['name'], 'client': str(_premier(x['partner_id'])), 'date': x['invoice_date'],
                              'montant': -abs(x['amount_total']) if x['move_type'] == 'out_refund' else x['amount_total'],
                              'type': 'Avoir' if x['move_type'] == 'out_refund' else 'Facture', 'facture_origine': nom_u(x.get('reversed_entry_id')),
                              'vendeur': nom_u(x.get('invoice_user_id'))} for x in mv])
    if jeu in ('paiements', 'encaissements'):
        sens = ('outbound', 'supplier') if jeu == 'paiements' else ('inbound', 'customer')
        pay = lire('account.payment', [('payment_type', '=', sens[0]), ('partner_type', '=', sens[1]), ('state', 'in', ['posted', 'paid'])] + per('date'),
                   ['name', 'partner_id', 'date', 'amount', 'partner_bank_id', 'write_uid', 'ref',
                    'reconciled_bill_ids' if jeu == 'paiements' else 'reconciled_invoice_ids', 'journal_id'])
        lies = sorted({i for x in pay for i in (x.get('reconciled_bill_ids') or x.get('reconciled_invoice_ids') or [])})
        noms = {m['id']: m['name'] for m in lire('account.move', [('id', 'in', lies)], ['name'])} if lies else {}
        if jeu == 'paiements':
            return tableau(jeu, [{'reference': x['name'], 'fournisseur': str(_premier(x['partner_id'])), 'date': x['date'], 'montant': x['amount'],
                                  'rib': str(nom_u(x.get('partner_bank_id')) or '').split(' - ')[0], 'approuve_par': nom_u(x.get('write_uid')),
                                  'facture': noms.get((x.get('reconciled_bill_ids') or [None])[0], ''), 'mode': nom_u(x.get('journal_id'))} for x in pay])
        return tableau(jeu, [{'reference': x['name'], 'client': str(_premier(x['partner_id'])), 'date': x['date'], 'montant': x['amount'],
                              'facture': noms.get((x.get('reconciled_invoice_ids') or [None])[0], ''), 'mode': nom_u(x.get('journal_id'))} for x in pay])
    if jeu == 'commandes':
        po = lire('purchase.order', [('state', 'in', ['purchase', 'done'])] + per('date_order'),
                  ['name', 'partner_id', 'date_order', 'date_approve', 'amount_total', 'user_id'])
        return tableau(jeu, [{'numero': x['name'], 'fournisseur': str(_premier(x['partner_id'])), 'date': (x.get('date_order') or '')[:10],
                              'montant': x['amount_total'], 'approuve_par': nom_u(x.get('user_id'))} for x in po])
    if jeu == 'grand_livre':
        ml = lire('account.move.line', [('parent_state', '=', 'posted')] + per('date'),
                  ['move_name', 'date', 'account_id', 'debit', 'credit', 'name', 'journal_id', 'ref', 'create_uid', 'create_date', 'partner_id', 'matching_number'])
        return tableau(jeu, [{'numero': x['move_name'], 'date': x['date'], 'compte': _code_compte(x['account_id']), 'debit': x['debit'] or None,
                              'credit': x['credit'] or None, 'libelle': x.get('name') or '', 'journal': nom_u(x.get('journal_id')), 'piece': x.get('ref') or '',
                              'saisi_par': nom_u(x.get('create_uid')), 'date_saisie': (x.get('create_date') or '').replace('T', ' ')[:19],
                              'tiers': str(_premier(x.get('partner_id')) or ''), 'lettrage': x.get('matching_number') or ''} for x in ml])
    raise ErreurSource(f'Odoo : données « {am.JEUX[jeu]["libelle"]} » non prises en charge.')


# ---- Microsoft Dynamics 365 Business Central (API v2.0, application Entra ID)
BC_DOMAINES = ('api.businesscentral.dynamics.com', 'login.microsoftonline.com')


def _bc(p, s, jeu, debut=None, fin=None, essai=False):
    jeton = _jeton_microsoft(p, s, 'https://api.businesscentral.dynamics.com/.default')
    env = requis(p, 'environnement', 'Environnement (ex. production)').strip()
    if not re.fullmatch(r'[A-Za-z0-9_\-]{1,50}', env):
        raise ErreurSource('Environnement invalide.')
    base = f'https://api.businesscentral.dynamics.com/v2.0/{p["tenant"].strip()}/{env}/api/v2.0'
    ent = {'Authorization': f'Bearer {jeton}', 'Accept': 'application/json'}
    if essai:
        r = http('GET', base + '/companies', BC_DOMAINES, ent, libelle='Business Central')
        noms = ', '.join(c.get('name', '') for c in (r.get('value') or [])[:5])
        return Extraction(info=f'Connexion établie. Sociétés : {noms}.')
    soc = requis(p, 'societe', 'Identifiant de la société').strip()
    if not re.fullmatch(r'[0-9a-fA-F-]{36}', soc):
        raise ErreurSource('Identifiant de société : GUID attendu (affiché par « Tester la connexion »).')
    racine = f'{base}/companies({soc})'

    def lire(entite, champ_date=None):
        params = {}
        if champ_date and (debut or fin):
            params['$filter'] = ' and '.join(x for x in ((f'{champ_date} ge {periode_iso(debut)}' if debut else ''),
                                                          (f'{champ_date} le {periode_iso(fin)}' if fin else '')) if x)
        url, res = f'{racine}/{entite}', []
        for _ in range(PAGES_MAX):
            r = http('GET', url, BC_DOMAINES, ent, params=params, libelle='Business Central')
            res += r.get('value') or []
            url, params = r.get('@odata.nextLink'), None
            if not url:
                return res
        return res

    def journaux(nom, entite):
        res = []
        for j in lire(nom):
            res += lire(f'{nom}({j["id"]})/{entite}', 'postingDate')
        return res
    if jeu == 'fournisseurs':
        return tableau(jeu, [{'code': x['number'], 'nom': x['displayName'], 'rib': '', 'adresse': x.get('addressLine1') or '',
                              'telephone': x.get('phoneNumber') or '', 'nif': x.get('taxRegistrationNumber') or '',
                              'statut': 'Bloqué' if (x.get('blocked') or '').strip() not in ('', ' ', '_x0020_') else 'Actif'} for x in lire('vendors')])
    if jeu == 'clients':
        return tableau(jeu, [{'code': x['number'], 'nom': x['displayName'],
                              'statut': 'Bloqué' if (x.get('blocked') or '').strip() not in ('', ' ', '_x0020_') else 'Actif'} for x in lire('customers')])
    if jeu == 'factures':
        return tableau(jeu, [{'numero': x['number'], 'fournisseur': x.get('vendorNumber'), 'date': x.get('invoiceDate'), 'montant': x.get('totalAmountIncludingTax'),
                              'commande': x.get('orderNumber') or '', 'devise': x.get('currencyCode') or ''} for x in lire('purchaseInvoices', 'invoiceDate')])
    if jeu == 'commandes':
        return tableau(jeu, [{'numero': x['number'], 'fournisseur': x.get('vendorNumber'), 'date': x.get('orderDate'),
                              'montant': x.get('totalAmountIncludingTax')} for x in lire('purchaseOrders', 'orderDate')])
    if jeu == 'paiements':
        return tableau(jeu, [{'reference': x.get('documentNumber') or x.get('id'), 'fournisseur': x.get('vendorNumber'), 'date': x.get('postingDate'),
                              'montant': abs(x.get('amount') or 0), 'rib': '', 'facture': x.get('appliesToInvoiceNumber') or ''}
                             for x in journaux('vendorPaymentJournals', 'vendorPayments')])
    if jeu == 'encaissements':
        return tableau(jeu, [{'reference': x.get('documentNumber') or x.get('id'), 'client': x.get('customerNumber'), 'date': x.get('postingDate'),
                              'montant': abs(x.get('amount') or 0), 'facture': x.get('appliesToInvoiceNumber') or ''}
                             for x in journaux('customerPaymentJournals', 'customerPayments')])
    if jeu == 'ventes':
        fv = [{'numero': x['number'], 'client': x.get('customerNumber'), 'date': x.get('invoiceDate'), 'montant': x.get('totalAmountIncludingTax'),
               'type': 'Facture', 'vendeur': x.get('salesperson') or ''} for x in lire('salesInvoices', 'invoiceDate')]
        av = [{'numero': x['number'], 'client': x.get('customerNumber'), 'date': x.get('creditMemoDate'), 'montant': -abs(x.get('totalAmountIncludingTax') or 0),
               'type': 'Avoir', 'facture_origine': x.get('invoiceNumber') or '', 'vendeur': x.get('salesperson') or ''}
              for x in lire('salesCreditMemos', 'creditMemoDate')]
        return tableau(jeu, fv + av)
    if jeu == 'grand_livre':
        return tableau(jeu, [{'numero': x.get('documentNumber') or x.get('entryNumber'), 'date': x.get('postingDate'), 'compte': x.get('accountNumber'),
                              'debit': x.get('debitAmount') or None, 'credit': x.get('creditAmount') or None, 'libelle': x.get('description') or '',
                              'journal': x.get('documentType') or '', 'piece': x.get('externalDocumentNumber') or x.get('documentNumber') or '',
                              'date_saisie': (x.get('lastModifiedDateTime') or '').replace('T', ' ')[:19]}
                             for x in lire('generalLedgerEntries', 'postingDate')])
    raise ErreurSource(f'Business Central : données « {am.JEUX[jeu]["libelle"]} » non prises en charge.')


# ---- jeton OAuth 2 renouvelable (Xero, QuickBooks, Zoho Books)
def _rafraichir(url, domaines, p, s, libelle, auth_basic=True):
    donnees = {'grant_type': 'refresh_token', 'refresh_token': requis(s, 'refresh_token', 'Jeton de renouvellement')}
    auth = None
    if auth_basic:
        auth = (requis(p, 'client_id', 'ID de l’application'), requis(s, 'secret', 'Secret de l’application'))
    else:
        donnees.update(client_id=requis(p, 'client_id', 'ID de l’application'), client_secret=requis(s, 'secret', 'Secret de l’application'))
    r = jeton_oauth(url, domaines, donnees, auth=auth, libelle=libelle)
    nouveau = {}
    if r.get('refresh_token') and r['refresh_token'] != s.get('refresh_token'):
        nouveau['refresh_token'] = r['refresh_token']             # l'éditeur renouvelle aussi le jeton de renouvellement
    return r['access_token'], nouveau


def _date_xero(v):
    m = re.match(r'/Date\((\d+)', str(v or ''))
    if m:
        return datetime.utcfromtimestamp(int(m.group(1)) / 1000).date().isoformat()
    return str(v or '')[:10]


XERO_DOMAINES = ('api.xero.com', 'identity.xero.com')


def _xero(p, s, jeu, debut=None, fin=None, essai=False):
    jeton, nouveau = _rafraichir('https://identity.xero.com/connect/token', XERO_DOMAINES, p, s, 'Xero')
    ent = {'Authorization': f'Bearer {jeton}', 'Accept': 'application/json'}
    if essai:
        r = http('GET', 'https://api.xero.com/connections', XERO_DOMAINES, ent, libelle='Xero')
        e = Extraction(info='Connexion établie. Organisations : ' + ', '.join(f'{c.get("tenantName")} ({c.get("tenantId")})' for c in (r or [])[:5]))
        e.secrets_a_jour = nouveau
        return e
    ent['xero-tenant-id'] = requis(p, 'organisation', 'Identifiant de l’organisation Xero (tenantId)')

    def lire(entite, cle, where=None):
        res = []
        for page in range(1, PAGES_MAX):
            params = {'page': page}
            if where:
                params['where'] = where
            r = http('GET', f'https://api.xero.com/api.xro/2.0/{entite}', XERO_DOMAINES, ent, params=params, libelle='Xero')
            lot = r.get(cle) or []
            res += lot
            if len(lot) < 100:
                break
        return res
    per = ''.join(x for x in ((f' && Date >= DateTime({debut.year},{debut.month},{debut.day})' if debut else ''),
                              (f' && Date <= DateTime({fin.year},{fin.month},{fin.day})' if fin else '')))
    if jeu in ('fournisseurs', 'clients'):
        cs = [c for c in lire('Contacts', 'Contacts') if c.get('IsSupplier' if jeu == 'fournisseurs' else 'IsCustomer')]
        if jeu == 'clients':
            ex = tableau(jeu, [{'code': c['ContactID'], 'nom': c.get('Name'), 'statut': 'Actif' if c.get('ContactStatus') == 'ACTIVE' else 'Inactif'} for c in cs])
        else:
            ex = tableau(jeu, [{'code': c['ContactID'], 'nom': c.get('Name'), 'rib': c.get('BankAccountDetails') or '', 'nif': c.get('TaxNumber') or '',
                                'telephone': ' '.join(x.get('PhoneNumber') or '' for x in (c.get('Phones') or [])[:1]),
                                'statut': 'Actif' if c.get('ContactStatus') == 'ACTIVE' else 'Inactif'} for c in cs])
    elif jeu in ('factures', 'ventes'):
        typ = 'ACCPAY' if jeu == 'factures' else 'ACCREC'
        fa = lire('Invoices', 'Invoices', f'Type=="{typ}" && Status!="DELETED" && Status!="VOIDED" && Status!="DRAFT"' + per)
        if jeu == 'factures':
            ex = tableau(jeu, [{'numero': x.get('InvoiceNumber') or x.get('InvoiceID'), 'fournisseur': (x.get('Contact') or {}).get('ContactID'),
                                'date': _date_xero(x.get('Date')), 'montant': x.get('Total'), 'commande': x.get('Reference') or '',
                                'devise': x.get('CurrencyCode') or ''} for x in fa])
        else:
            av = lire('CreditNotes', 'CreditNotes', 'Type=="ACCRECCREDIT" && Status!="DELETED" && Status!="VOIDED"' + per)
            ex = tableau(jeu, [{'numero': x.get('InvoiceNumber'), 'client': (x.get('Contact') or {}).get('ContactID'), 'date': _date_xero(x.get('Date')),
                                'montant': x.get('Total'), 'type': 'Facture'} for x in fa]
                         + [{'numero': x.get('CreditNoteNumber'), 'client': (x.get('Contact') or {}).get('ContactID'), 'date': _date_xero(x.get('Date')),
                             'montant': -abs(x.get('Total') or 0), 'type': 'Avoir',
                             'facture_origine': ((x.get('Allocations') or [{}])[0].get('Invoice') or {}).get('InvoiceNumber', '')} for x in av])
    elif jeu in ('paiements', 'encaissements'):
        typ = 'ACCPAY' if jeu == 'paiements' else 'ACCREC'
        pa = [x for x in lire('Payments', 'Payments', 'Status=="AUTHORISED"' + per) if (x.get('Invoice') or {}).get('Type') == typ]
        if jeu == 'paiements':
            ex = tableau(jeu, [{'reference': x.get('Reference') or x.get('PaymentID'), 'fournisseur': ((x.get('Invoice') or {}).get('Contact') or {}).get('ContactID'),
                                'date': _date_xero(x.get('Date')), 'montant': x.get('Amount'), 'rib': x.get('BankAccountNumber') or '',
                                'facture': (x.get('Invoice') or {}).get('InvoiceNumber') or ''} for x in pa])
        else:
            ex = tableau(jeu, [{'reference': x.get('Reference') or x.get('PaymentID'), 'client': ((x.get('Invoice') or {}).get('Contact') or {}).get('ContactID'),
                                'date': _date_xero(x.get('Date')), 'montant': x.get('Amount'), 'facture': (x.get('Invoice') or {}).get('InvoiceNumber') or ''}
                               for x in pa])
    elif jeu == 'commandes':
        ex = tableau(jeu, [{'numero': x.get('PurchaseOrderNumber'), 'fournisseur': (x.get('Contact') or {}).get('ContactID'), 'date': _date_xero(x.get('Date')),
                            'montant': x.get('Total')} for x in lire('PurchaseOrders', 'PurchaseOrders')
                           if (not debut or _date_xero(x.get('Date')) >= periode_iso(debut)) and (not fin or _date_xero(x.get('Date')) <= periode_iso(fin))])
    else:
        raise ErreurSource(f'Xero : données « {am.JEUX[jeu]["libelle"]} » non prises en charge (utilisez l’export du grand livre).')
    ex.secrets_a_jour = nouveau
    return ex


QB_DOMAINES = ('quickbooks.api.intuit.com', 'oauth.platform.intuit.com')


def _quickbooks(p, s, jeu, debut=None, fin=None, essai=False):
    jeton, nouveau = _rafraichir('https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer', QB_DOMAINES, p, s, 'QuickBooks')
    societe = requis(p, 'societe', 'Identifiant de la société (Realm ID)').strip()
    if not re.fullmatch(r'\d{1,30}', societe):
        raise ErreurSource('QuickBooks : Realm ID numérique attendu.')
    ent = {'Authorization': f'Bearer {jeton}', 'Accept': 'application/json'}
    base = f'https://quickbooks.api.intuit.com/v3/company/{societe}/query'

    def lire(entite, champ_date=None):
        cond = ''
        if champ_date and (debut or fin):
            cond = ' WHERE ' + ' AND '.join(x for x in ((f"{champ_date} >= '{periode_iso(debut)}'" if debut else ''),
                                                          (f"{champ_date} <= '{periode_iso(fin)}'" if fin else '')) if x)
        res, pos = [], 1
        for _ in range(PAGES_MAX):
            r = http('GET', base, QB_DOMAINES, ent, params={'query': f'SELECT * FROM {entite}{cond} STARTPOSITION {pos} MAXRESULTS 1000',
                                                            'minorversion': '70'}, libelle='QuickBooks')
            lot = (r.get('QueryResponse') or {}).get(entite) or []
            res += lot
            if len(lot) < 1000:
                return res
            pos += 1000
        return res
    if essai:
        lire('CompanyInfo')
        e = Extraction(info='Connexion établie.')
        e.secrets_a_jour = nouveau
        return e
    ref = lambda x, k: (x.get(k) or {}).get('value')  # noqa: E731
    lie = lambda x, t: next((l.get('TxnId') for li in (x.get('Line') or []) for l in (li.get('LinkedTxn') or []) if l.get('TxnType') == t), '')  # noqa: E731
    if jeu in ('fournisseurs', 'clients'):
        ent_ = 'Vendor' if jeu == 'fournisseurs' else 'Customer'
        cs = lire(ent_)
        if jeu == 'clients':
            ex = tableau(jeu, [{'code': c['Id'], 'nom': c.get('DisplayName'), 'statut': 'Actif' if c.get('Active', True) else 'Inactif',
                                'date_creation': ((c.get('MetaData') or {}).get('CreateTime') or '')[:10]} for c in cs])
        else:
            ex = tableau(jeu, [{'code': c['Id'], 'nom': c.get('DisplayName'), 'rib': c.get('AcctNum') or '', 'nif': c.get('TaxIdentifier') or '',
                                'telephone': (c.get('PrimaryPhone') or {}).get('FreeFormNumber') or '',
                                'date_creation': ((c.get('MetaData') or {}).get('CreateTime') or '')[:10],
                                'statut': 'Actif' if c.get('Active', True) else 'Inactif'} for c in cs])
    elif jeu == 'factures':
        ex = tableau(jeu, [{'numero': x.get('DocNumber') or x['Id'], 'fournisseur': ref(x, 'VendorRef'), 'date': x.get('TxnDate'), 'montant': x.get('TotalAmt'),
                            'date_saisie': ((x.get('MetaData') or {}).get('CreateTime') or '')[:10]} for x in lire('Bill', 'TxnDate')])
    elif jeu == 'paiements':
        bills = {b['Id']: b.get('DocNumber') or b['Id'] for b in lire('Bill', 'TxnDate')}
        ex = tableau(jeu, [{'reference': x.get('DocNumber') or x['Id'], 'fournisseur': ref(x, 'VendorRef'), 'date': x.get('TxnDate'), 'montant': x.get('TotalAmt'),
                            'rib': '', 'facture': bills.get(lie(x, 'Bill'), lie(x, 'Bill'))} for x in lire('BillPayment', 'TxnDate')])
    elif jeu == 'commandes':
        ex = tableau(jeu, [{'numero': x.get('DocNumber') or x['Id'], 'fournisseur': ref(x, 'VendorRef'), 'date': x.get('TxnDate'),
                            'montant': x.get('TotalAmt')} for x in lire('PurchaseOrder', 'TxnDate')])
    elif jeu == 'ventes':
        ex = tableau(jeu, [{'numero': x.get('DocNumber') or x['Id'], 'client': ref(x, 'CustomerRef'), 'date': x.get('TxnDate'), 'montant': x.get('TotalAmt'),
                            'type': 'Facture'} for x in lire('Invoice', 'TxnDate')]
                     + [{'numero': x.get('DocNumber') or x['Id'], 'client': ref(x, 'CustomerRef'), 'date': x.get('TxnDate'),
                         'montant': -abs(x.get('TotalAmt') or 0), 'type': 'Avoir'} for x in lire('CreditMemo', 'TxnDate')])
    elif jeu == 'encaissements':
        inv = {b['Id']: b.get('DocNumber') or b['Id'] for b in lire('Invoice', 'TxnDate')}
        ex = tableau(jeu, [{'reference': x.get('PaymentRefNum') or x['Id'], 'client': ref(x, 'CustomerRef'), 'date': x.get('TxnDate'),
                            'montant': x.get('TotalAmt'), 'facture': inv.get(lie(x, 'Invoice'), lie(x, 'Invoice'))} for x in lire('Payment', 'TxnDate')])
    else:
        raise ErreurSource(f'QuickBooks : données « {am.JEUX[jeu]["libelle"]} » non prises en charge (utilisez l’export du grand livre).')
    ex.secrets_a_jour = nouveau
    return ex


ZOHO_CENTRES = {'com': 'com', 'eu': 'eu', 'in': 'in', 'com.au': 'com.au', 'jp': 'jp', 'ca': 'zohocloud.ca', 'sa': 'sa'}


def _zoho(p, s, jeu, debut=None, fin=None, essai=False):
    dc = ZOHO_CENTRES.get((p.get('centre') or 'eu').strip(), 'eu')
    domaines = (f'accounts.zoho.{dc}', f'www.zohoapis.{dc}') if dc != 'zohocloud.ca' else ('accounts.zohocloud.ca', 'www.zohoapis.ca')
    jeton, nouveau = _rafraichir(f'https://{domaines[0]}/oauth/v2/token', domaines, p, s, 'Zoho Books', auth_basic=False)
    ent = {'Authorization': f'Zoho-oauthtoken {jeton}'}
    base = f'https://{domaines[1]}/books/v3'
    if essai:
        r = http('GET', base + '/organizations', domaines, ent, libelle='Zoho Books')
        e = Extraction(info='Connexion établie. Organisations : ' + ', '.join(f'{o.get("name")} ({o.get("organization_id")})' for o in (r.get('organizations') or [])[:5]))
        e.secrets_a_jour = nouveau
        return e
    org = requis(p, 'organisation', 'Identifiant de l’organisation Zoho')

    def lire(entite, cle, **filtres):
        res = []
        for page in range(1, PAGES_MAX):
            params = dict(organization_id=org, page=page, per_page=200, **filtres)
            if debut and entite not in ('contacts',):
                params['date_start'] = periode_iso(debut)
            if fin and entite not in ('contacts',):
                params['date_end'] = periode_iso(fin)
            r = http('GET', f'{base}/{entite}', domaines, ent, params=params, libelle='Zoho Books')
            res += r.get(cle) or []
            if not (r.get('page_context') or {}).get('has_more_page'):
                break
        return res
    if jeu in ('fournisseurs', 'clients'):
        cs = lire('contacts', 'contacts', contact_type='vendor' if jeu == 'fournisseurs' else 'customer')
        if jeu == 'clients':
            ex = tableau(jeu, [{'code': c['contact_id'], 'nom': c.get('contact_name'), 'statut': 'Actif' if c.get('status') == 'active' else 'Inactif',
                                'date_creation': (c.get('created_time') or '')[:10]} for c in cs])
        else:
            ex = tableau(jeu, [{'code': c['contact_id'], 'nom': c.get('contact_name'), 'rib': '', 'telephone': c.get('phone') or '',
                                'date_creation': (c.get('created_time') or '')[:10],
                                'statut': 'Actif' if c.get('status') == 'active' else 'Inactif'} for c in cs])
    elif jeu == 'factures':
        ex = tableau(jeu, [{'numero': x.get('bill_number'), 'fournisseur': x.get('vendor_id'), 'date': x.get('date'), 'montant': x.get('total'),
                            'commande': x.get('reference_number') or ''} for x in lire('bills', 'bills')])
    elif jeu == 'paiements':
        ex = tableau(jeu, [{'reference': x.get('payment_number') or x.get('payment_id'), 'fournisseur': x.get('vendor_id'), 'date': x.get('date'),
                            'montant': x.get('amount'), 'rib': '', 'facture': x.get('bill_numbers') or ''} for x in lire('vendorpayments', 'vendorpayments')])
    elif jeu == 'commandes':
        ex = tableau(jeu, [{'numero': x.get('purchaseorder_number'), 'fournisseur': x.get('vendor_id'), 'date': x.get('date'), 'montant': x.get('total')}
                           for x in lire('purchaseorders', 'purchaseorders')])
    elif jeu == 'ventes':
        ex = tableau(jeu, [{'numero': x.get('invoice_number'), 'client': x.get('customer_id'), 'date': x.get('date'), 'montant': x.get('total'),
                            'type': 'Facture', 'vendeur': x.get('salesperson_name') or ''} for x in lire('invoices', 'invoices')]
                     + [{'numero': x.get('creditnote_number'), 'client': x.get('customer_id'), 'date': x.get('date'), 'montant': -abs(x.get('total') or 0),
                         'type': 'Avoir', 'facture_origine': x.get('reference_number') or ''} for x in lire('creditnotes', 'creditnotes')])
    elif jeu == 'encaissements':
        ex = tableau(jeu, [{'reference': x.get('payment_number') or x.get('payment_id'), 'client': x.get('customer_id'), 'date': x.get('date'),
                            'montant': x.get('amount'), 'facture': x.get('invoice_numbers') or ''} for x in lire('customerpayments', 'customerpayments')])
    else:
        raise ErreurSource(f'Zoho Books : données « {am.JEUX[jeu]["libelle"]} » non prises en charge (utilisez l’export du grand livre).')
    ex.secrets_a_jour = nouveau
    return ex


# ====================================================================== catalogue
F = lambda code, libelle, secret=False, aide='', type_='texte', defaut='': dict(code=code, libelle=libelle, secret=secret, aide=aide, type=type_, defaut=defaut)  # noqa: E731
TOUS = list(am.ORDRE_JEUX)
CHAMPS_BD = [F('hote', 'Serveur (nom ou adresse publique)'), F('port', 'Port', type_='nombre'), F('base', 'Base de données'),
             F('utilisateur', 'Utilisateur (lecture seule)'), F('mot_de_passe', 'Mot de passe', secret=True)]
MS_APP = [F('tenant', 'Identifiant du locataire Microsoft Entra (tenant)', aide='GUID ou votresociete.onmicrosoft.com'),
          F('client_id', 'ID de l’application (client)'), F('secret', 'Secret de l’application', secret=True)]
OAUTH = [F('client_id', 'ID de l’application (client)'), F('secret', 'Secret de l’application', secret=True),
         F('refresh_token', 'Jeton de renouvellement (refresh token)', secret=True, aide='Obtenu une fois lors de l’autorisation de l’application')]
CONNECTEURS = [
    dict(code='postgresql', nom='PostgreSQL', famille='Base de données', f=_sql('postgresql'), jeux=TOUS, extraction='requete', champs=CHAMPS_BD,
         aide='Requête SELECT par type de données ; utilisez :debut et :fin pour la période.'),
    dict(code='mysql', nom='MySQL / MariaDB', famille='Base de données', f=_sql('mysql'), jeux=TOUS, extraction='requete', champs=CHAMPS_BD,
         aide='Requête SELECT par type de données ; utilisez :debut et :fin pour la période.'),
    dict(code='sqlserver', nom='Microsoft SQL Server (Sage 100, Saari…)', famille='Base de données', f=_sql('sqlserver'), jeux=TOUS, extraction='requete',
         champs=CHAMPS_BD, modeles='sage100', aide='Modèles de requêtes Sage 100 fournis ; à faire valider par votre DSI.'),
    dict(code='oracle', nom='Oracle Database (Flexcube, T24, ERP…)', famille='Base de données', f=_sql('oracle'), jeux=TOUS, extraction='requete',
         champs=[F('hote', 'Serveur'), F('port', 'Port', type_='nombre'), F('base', 'Nom du service Oracle'), F('utilisateur', 'Utilisateur (lecture seule)'),
                 F('mot_de_passe', 'Mot de passe', secret=True)],
         aide='Le plus simple : des vues préparées par la DSI (egalyx_fournisseurs, egalyx_paiements…).'),
    dict(code='sftp', nom='Serveur SFTP', famille='Fichiers déposés', f=_sftp, jeux=TOUS, extraction='chemin',
         champs=[F('hote', 'Serveur SFTP'), F('port', 'Port', type_='nombre'), F('utilisateur', 'Utilisateur'), F('mot_de_passe', 'Mot de passe', secret=True),
                 F('cle_privee', 'Ou clé privée (format PEM)', secret=True, type_='long'),
                 F('empreinte_hote', 'Empreinte de la clé du serveur', aide='Remplie au premier test ; toute modification ultérieure sera refusée')],
         aide='Chemin par type de données ; {AAAA}, {MM}, {JJ} et * acceptés (le fichier le plus récent est pris).'),
    dict(code='https', nom='Lien https d’export', famille='Fichiers déposés', f=_https, jeux=TOUS, extraction='url',
         champs=[F('jeton', 'Jeton d’accès (facultatif)', secret=True), F('entete', 'En-tête du jeton', defaut='Authorization'),
                 F('prefixe', 'Préfixe du jeton', defaut='Bearer'), F('url_essai', 'Adresse pour tester la connexion')],
         aide='Adresse https d’un fichier CSV ou Excel exporté automatiquement par votre logiciel.'),
    dict(code='m365', nom='SharePoint / OneDrive (Microsoft 365)', famille='Fichiers déposés', f=_m365, jeux=TOUS, extraction='chemin',
         champs=MS_APP + [F('site', 'Site SharePoint', aide='https://votresociete.sharepoint.com/sites/Finance'),
                          F('utilisateur', 'Ou OneDrive de l’utilisateur (e-mail)')],
         aide='Application Entra ID avec la permission Sites.Read.All (ou Files.Read.All).'),
    dict(code='google_drive', nom='Google Drive', famille='Fichiers déposés', f=_google_drive, jeux=TOUS, extraction='fichier',
         champs=[F('compte_service', 'Clé du compte de service (JSON)', secret=True, type_='long')],
         aide='Partagez les fichiers (lecture) avec l’adresse du compte de service ; les Google Sheets sont exportées en Excel.'),
    dict(code='odoo', nom='Odoo', famille='Logiciel de gestion', f=_odoo, extraction='api',
         jeux=['fournisseurs', 'factures', 'paiements', 'commandes', 'grand_livre', 'ventes', 'clients', 'encaissements'],
         champs=[F('url', 'Adresse Odoo', aide='https://votresociete.odoo.com'), F('base', 'Base de données'),
                 F('utilisateur', 'Utilisateur (e-mail)'), F('cle', 'Clé d’API', secret=True)],
         aide='Utilisateur en lecture seule sur la comptabilité et les achats ; clé d’API créée dans ses préférences.'),
    dict(code='business_central', nom='Microsoft Dynamics 365 Business Central', famille='Logiciel de gestion', f=_bc, extraction='api',
         jeux=['fournisseurs', 'factures', 'paiements', 'commandes', 'grand_livre', 'ventes', 'clients', 'encaissements'],
         champs=MS_APP + [F('environnement', 'Environnement', defaut='production'), F('societe', 'Identifiant de la société (GUID)')],
         aide='Application Entra ID autorisée dans Business Central (API.ReadWrite.All en lecture, ensemble de droits D365 READ).'),
    dict(code='xero', nom='Xero', famille='Logiciel de gestion', f=_xero, extraction='api',
         jeux=['fournisseurs', 'factures', 'paiements', 'commandes', 'ventes', 'clients', 'encaissements'],
         champs=OAUTH + [F('organisation', 'Identifiant de l’organisation (tenantId)', aide='Affiché par « Tester la connexion »')],
         aide='Application Xero (accounting.transactions.read, accounting.contacts.read, offline_access).'),
    dict(code='quickbooks', nom='QuickBooks Online', famille='Logiciel de gestion', f=_quickbooks, extraction='api',
         jeux=['fournisseurs', 'factures', 'paiements', 'commandes', 'ventes', 'clients', 'encaissements'],
         champs=OAUTH + [F('societe', 'Identifiant de la société (Realm ID)')],
         aide='Application Intuit (com.intuit.quickbooks.accounting).'),
    dict(code='zoho_books', nom='Zoho Books', famille='Logiciel de gestion', f=_zoho, extraction='api',
         jeux=['fournisseurs', 'factures', 'paiements', 'commandes', 'ventes', 'clients', 'encaissements'],
         champs=OAUTH + [F('centre', 'Centre de données', defaut='eu', aide='eu, com, in, com.au, jp, ca, sa'),
                         F('organisation', 'Identifiant de l’organisation', aide='Affiché par « Tester la connexion »')],
         aide='Client API Zoho (ZohoBooks.fullaccess.READ).'),
]
PAR_CODE = {c['code']: c for c in CONNECTEURS}
FAMILLES = ['Base de données', 'Fichiers déposés', 'Logiciel de gestion']


def extraire(code, parametres, secrets, jeu, debut=None, fin=None):
    c = PAR_CODE.get(code)
    if c is None:
        raise ErreurSource('Connecteur inconnu.')
    if jeu not in c['jeux']:
        raise ErreurSource(f'{c["nom"]} : données « {am.JEUX[jeu]["libelle"]} » non prises en charge.')
    return c['f'](parametres or {}, secrets or {}, jeu, debut, fin)


def tester(code, parametres, secrets):
    c = PAR_CODE.get(code)
    if c is None:
        raise ErreurSource('Connecteur inconnu.')
    return c['f'](parametres or {}, secrets or {}, (c['jeux'] or TOUS)[0], None, None, essai=True)


def vers_tableau(ext):
    """Extraction → (entetes, lignes_brutes, infos) comme lire_fichier (fichiers : lus par le moteur)."""
    if ext.octets is not None:
        e, _l, inf = am.lire_fichier(ext.octets, ext.nom or 'export.csv')
        return e, inf['lignes_brutes'], inf
    if not ext.lignes:
        raise ErreurSource('Aucune ligne pour cette période.')
    entetes = [am.texte(x) or f'Colonne {i + 1}' for i, x in enumerate(ext.entetes)]
    return entetes, ext.lignes, {'format': 'Connecteur', 'feuilles': [], 'feuille': '', 'separateur': '', 'encodage': '', 'premiere_ligne': 2}


# ====================================================================== périodes glissantes (analyses programmées)
PERIODES = [('mois_precedent', 'Mois précédent'), ('mois_en_cours', 'Mois en cours'), ('30_jours', '30 derniers jours'),
            ('trimestre_precedent', 'Trimestre précédent'), ('annee_en_cours', 'Année en cours'), ('annee_precedente', 'Année précédente')]


def periode(code, aujourd_hui=None):
    j = aujourd_hui or date.today()
    if code == 'mois_en_cours':
        return j.replace(day=1), j
    if code == '30_jours':
        return j - timedelta(days=30), j
    if code == 'trimestre_precedent':
        t = (j.month - 1) // 3
        an, t = (j.year, t - 1) if t else (j.year - 1, 3)
        debut = date(an, 3 * t + 1, 1)
        fin = (date(an + (t == 3), (3 * t + 3) % 12 + 1, 1) - timedelta(days=1))
        return debut, fin
    if code == 'annee_en_cours':
        return date(j.year, 1, 1), j
    if code == 'annee_precedente':
        return date(j.year - 1, 1, 1), date(j.year - 1, 12, 31)
    fin = j.replace(day=1) - timedelta(days=1)
    return fin.replace(day=1), fin
