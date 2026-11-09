"""
egalyx/courriel.py — envoi d'e-mails par SMTP, paramétré par variables d'environnement.

    SMTP_HOTE          (défaut smtp.hostinger.com)
    SMTP_PORT          (défaut 465 si SMTP_SECURITE=ssl, sinon 587)
    SMTP_SECURITE      ssl | starttls | aucune      (défaut ssl)
    SMTP_UTILISATEUR   (défaut = SMTP_EXPEDITEUR)
    SMTP_MOT_DE_PASSE  (ancien nom accepté : HOSTINGER_EMAIL_PASSWORD)
    SMTP_EXPEDITEUR    (défaut contact@egalyx.com)
    SMTP_NOM_EXPEDITEUR (défaut Egalyx Control)
    SMTP_CA_FICHIER    certificat d'autorité supplémentaire (serveur interne), facultatif

Les certificats du serveur sont TOUJOURS vérifiés. Sans mot de passe, les e-mails
sont seulement journalisés (mode simulation) et envoyer() renvoie False.
"""
import logging
import os
import smtplib
import ssl
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, make_msgid, formatdate

journal = logging.getLogger('egalyx.courriel')


def configuration():
    securite = (os.environ.get('SMTP_SECURITE') or 'ssl').strip().lower()
    if securite not in ('ssl', 'starttls', 'aucune'):
        securite = 'ssl'
    expediteur = os.environ.get('SMTP_EXPEDITEUR') or 'contact@egalyx.com'
    port_defaut = 465 if securite == 'ssl' else 587
    try:
        port = int(os.environ.get('SMTP_PORT') or port_defaut)
    except ValueError:
        port = port_defaut
    return {
        'hote': os.environ.get('SMTP_HOTE') or 'smtp.hostinger.com',
        'port': port,
        'securite': securite,
        'utilisateur': os.environ.get('SMTP_UTILISATEUR') or expediteur,
        'mot_de_passe': os.environ.get('SMTP_MOT_DE_PASSE') or os.environ.get('HOSTINGER_EMAIL_PASSWORD') or '',
        'expediteur': expediteur,
        'nom': os.environ.get('SMTP_NOM_EXPEDITEUR') or 'Egalyx Control',
        'ca': os.environ.get('SMTP_CA_FICHIER') or None,
    }


def est_configure():
    return bool(configuration()['mot_de_passe'])


def _contexte_tls(cfg):
    ctx = ssl.create_default_context(cafile=cfg['ca']) if cfg['ca'] else ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def construire_message(cfg, destinataires, sujet, texte, html=None, cc=None):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = str(Header(sujet, 'utf-8'))
    msg['From'] = formataddr((str(Header(cfg['nom'], 'utf-8')), cfg['expediteur']))
    msg['To'] = ', '.join(destinataires)
    if cc:
        msg['Cc'] = ', '.join(cc)
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain=cfg['expediteur'].split('@')[-1])
    msg.attach(MIMEText(texte or '', 'plain', 'utf-8'))
    if html:
        msg.attach(MIMEText(html, 'html', 'utf-8'))
    return msg


def _liste(v):
    if not v:
        return []
    return [x for x in (v if isinstance(v, (list, tuple)) else [v]) if x]


def envoyer(destinataires, sujet, texte, html=None, cc=None, bcc=None):
    cfg = configuration()
    a, c, b = _liste(destinataires), _liste(cc), _liste(bcc)
    if not a:
        return False
    if not cfg['mot_de_passe']:
        journal.warning("[SIMULATION — SMTP_MOT_DE_PASSE absent] e-mail « %s » à %s non envoyé", sujet, ', '.join(a))
        return False
    msg = construire_message(cfg, a, sujet, texte, html, c)
    try:
        if cfg['securite'] == 'ssl':
            with smtplib.SMTP_SSL(cfg['hote'], cfg['port'], timeout=30, context=_contexte_tls(cfg)) as s:
                s.login(cfg['utilisateur'], cfg['mot_de_passe'])
                s.send_message(msg, to_addrs=a + c + b)
        else:
            with smtplib.SMTP(cfg['hote'], cfg['port'], timeout=30) as s:
                s.ehlo()
                if cfg['securite'] == 'starttls':
                    s.starttls(context=_contexte_tls(cfg))
                    s.ehlo()
                s.login(cfg['utilisateur'], cfg['mot_de_passe'])
                s.send_message(msg, to_addrs=a + c + b)
        journal.info("E-mail « %s » envoyé à %s", sujet, ', '.join(a))
        return True
    except Exception as e:
        journal.error("Échec d'envoi de « %s » à %s : %s", sujet, ', '.join(a), e)
        return False
