
# --- Journal (remplace les anciens print()) : erreurs -> WARNING (journaux du serveur) ; le reste -> DEBUG,
#     visible seulement avec EGALYX_TRACES=1. Ajouté le 18/11/2026 (ménage).
import logging as _logging_journal
import os as _os_journal
_JOURNAL = _logging_journal.getLogger('egalyx.services.email_service')
_MOTS_ALERTE = ('\u274c', '\u26a0', 'ERREUR', 'Erreur', 'erreur', 'ERROR', 'Error', 'error', 'Exception', 'chec', 'Traceback', 'CRITIQUE')
if _os_journal.environ.get('EGALYX_TRACES') == '1' and not _JOURNAL.handlers:
    _JOURNAL.setLevel(_logging_journal.DEBUG)
    _h = _logging_journal.StreamHandler()
    _h.setFormatter(_logging_journal.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
    _JOURNAL.addHandler(_h)
    _JOURNAL.propagate = False


def _journal(*args, sep=' ', **_ignore):
    """Ancien print() : écrit dans le journal au lieu de la sortie standard."""
    try:
        texte = sep.join(str(a) for a in args)
    except Exception:  # noqa: BLE001
        return
    if any(m in texte for m in _MOTS_ALERTE) and not texte.lstrip().startswith(('\u2705', '\u2713')):
        _JOURNAL.warning(texte)
    elif _JOURNAL.isEnabledFor(_logging_journal.DEBUG):
        _JOURNAL.debug(texte)
# --- fin du journal
# services/email_service.py - VERSION POUR DÉVELOPPEMENT LOCAL
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import os
from datetime import datetime
import logging
import socket
import time

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailService:
    """Service d'email - Version développement local"""
    
    def __init__(self):
        # Configuration par défaut (Hostinger)
        self.smtp_server = 'smtp.hostinger.com'
        self.smtp_port_tls = 587
        self.smtp_port_ssl = 465
        self.sender_email = 'contact@egalyx.com'
        self.sender_name = 'Egalyx Control'
        self.password = os.environ.get('HOSTINGER_EMAIL_PASSWORD', '')
        self.timeout = 30
        
        # === MODE DÉVELOPPEMENT LOCAL ===
        # Détection automatique de l'environnement
        self.is_local = self._detect_local_environment()
        
        if self.is_local:
            logger.info("🖥️ Mode développement local détecté")
            # Utiliser un serveur SMTP de test ou affichage console
            self.use_file_output = True  # Sauvegarder dans des fichiers
            self.use_console_output = True  # Afficher dans la console
            self.email_output_dir = os.path.join(os.getcwd(), 'emails_saved')
            
            # Créer le dossier de sauvegarde
            if self.use_file_output and not os.path.exists(self.email_output_dir):
                os.makedirs(self.email_output_dir)
                logger.info(f"📁 Dossier créé: {self.email_output_dir}")
        else:
            logger.info("☁️ Mode production détecté")
            self.use_file_output = False
            self.use_console_output = False
        
        # Mode simulation (si pas de mot de passe en production)
        if not self.password and not self.is_local:
            logger.warning("⚠️ HOSTINGER_EMAIL_PASSWORD non défini - emails en mode simulation")
            self.simulation_mode = True
        else:
            self.simulation_mode = False
    
    def _detect_local_environment(self):
        """Détecte si on est en environnement local"""
        import platform
        
        hostname = socket.gethostname()
        
        # Indices d'environnement local
        local_indicators = [
            'localhost',
            '127.0.0.1',
            '::1',
            'desktop',
            'laptop',
            'MacBook',
            'PC',
            'LAPTOP',
            'Mac'
        ]
        
        # Vérifier le hostname
        for indicator in local_indicators:
            if indicator.lower() in hostname.lower():
                return True
        
        # Vérifier si on est sur Windows/Mac (probablement local)
        if platform.system() in ['Windows', 'Darwin']:
            return True
        
        return False
    
    def _save_email_to_file(self, to_email, subject, body, html_body):
        """Sauvegarde l'email dans un fichier pour développement"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"email_{timestamp}_{to_email.replace('@', '_').replace('.', '_')}.html"
            filepath = os.path.join(self.email_output_dir, filename)
            
            # Créer un fichier HTML complet pour visualisation
            full_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Email sauvegardé</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                    .email-container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }}
                    .email-header {{ background: #0A1929; color: white; padding: 20px; }}
                    .email-meta {{ background: #f0f0f0; padding: 15px; border-bottom: 1px solid #ddd; }}
                    .email-meta p {{ margin: 5px 0; }}
                    .email-body {{ padding: 20px; }}
                    .label {{ font-weight: bold; color: #555; }}
                </style>
            </head>
            <body>
                <div class="email-container">
                    <div class="email-header">
                        <h2>Email sauvegardé - {timestamp}</h2>
                    </div>
                    <div class="email-meta">
                        <p><span class="label">À:</span> {to_email}</p>
                        <p><span class="label">Sujet:</span> {subject}</p>
                        <p><span class="label">Date:</span> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
                    </div>
                    <div class="email-body">
                        <h3>Version HTML:</h3>
                        <hr>
                        {html_body if html_body else '<p>Aucun contenu HTML</p>'}
                        
                        <hr>
                        <h3>Version texte:</h3>
                        <pre>{body}</pre>
                    </div>
                </div>
            </body>
            </html>
            """
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(full_html)
            
            logger.info(f"💾 Email sauvegardé: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde email: {e}")
            return None
    
    def _print_email_to_console(self, to_email, subject, body, html_body):
        """Affiche l'email dans la console pour développement"""
        _journal("\n" + "="*80)
        _journal(f"📧 EMAIL ENVOYÉ (MODE LOCAL)")
        _journal("="*80)
        _journal(f"À: {to_email}")
        _journal(f"Sujet: {subject}")
        _journal(f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        _journal("-"*40)
        _journal("TEXTE:")
        _journal(body[:500] + "..." if len(body) > 500 else body)
        _journal("-"*40)
        if html_body:
            _journal("HTML: [contenu HTML disponible]")
        _journal("="*80 + "\n")
    
    def send_email(self, to_email, subject, body, html_body=None, cc=None, bcc=None, max_retries=3,
                   attachments=None, reply_to=None, inline_images=None):
        """attachments : [(nom, octets, type MIME)] ; inline_images : [(cid, octets, sous-type)] pour <img src="cid:…"> ;
        reply_to : adresse de réponse (ex. le chef de mission)."""
        """Envoyer un email - adaptable selon l'environnement"""
        
        # === MODE DÉVELOPPEMENT LOCAL ===
        if self.is_local:
            # Afficher dans la console
            if self.use_console_output:
                self._print_email_to_console(to_email, subject, body, html_body)
            
            # Sauvegarder dans un fichier
            if self.use_file_output:
                self._save_email_to_file(to_email, subject, body, html_body)
            self.dernier_envoi = {'to': to_email, 'cc': cc, 'subject': subject, 'html': html_body, 'reply_to': reply_to,
                                  'attachments': [(a[0], len(a[1])) for a in (attachments or [])]}
            
            logger.info(f"📧 [LOCAL] Email simulé à: {to_email}")
            return True
        
        # === MODE SIMULATION (pas de mot de passe) ===
        if self.simulation_mode:
            self.dernier_envoi = {'to': to_email, 'cc': cc, 'subject': subject, 'html': html_body, 'reply_to': reply_to,
                                  'attachments': [(a[0], len(a[1])) for a in (attachments or [])], 'simulation': True}
            logger.info(f"📧 [SIMULATION] Email à: {to_email}")
            logger.info(f"   Sujet: {subject}")
            return True
        
        # === MODE PRODUCTION RÉEL ===
        # Tentatives multiples
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"📨 Tentative {attempt}/{max_retries} d'envoi à {to_email}")
                
                # Créer le message (pièces jointes / images intégrées : enveloppe « mixed » / « related »)
                alternative = MIMEMultipart('alternative')
                if attachments or inline_images:
                    msg = MIMEMultipart('mixed')
                else:
                    msg = alternative
                msg['Subject'] = subject
                if reply_to:
                    msg['Reply-To'] = reply_to
                msg['From'] = formataddr((self.sender_name, self.sender_email))
                msg['Message-ID'] = f"<{datetime.now().timestamp()}@{self.smtp_server}>"
                
                # Gérer les destinataires
                if isinstance(to_email, list):
                    msg['To'] = ', '.join(to_email)
                    recipients = to_email
                else:
                    msg['To'] = to_email
                    recipients = [to_email]
                
                # Ajouter CC si spécifié
                if cc:
                    if isinstance(cc, list):
                        msg['Cc'] = ', '.join(cc)
                        recipients.extend(cc)
                    else:
                        msg['Cc'] = cc
                        recipients.append(cc)
                
                # Ajouter BCC si spécifié
                if bcc:
                    if isinstance(bcc, list):
                        recipients.extend(bcc)
                    else:
                        recipients.append(bcc)
                
                # Partie texte
                text_part = MIMEText(body, 'plain', 'utf-8')
                alternative.attach(text_part)
                
                # Partie HTML si fournie
                if html_body:
                    html_part = MIMEText(html_body, 'html', 'utf-8')
                    if inline_images:
                        from email.mime.image import MIMEImage
                        related = MIMEMultipart('related')
                        related.attach(html_part)
                        for cid_img, octets, sous_type in inline_images:
                            img = MIMEImage(octets, _subtype=sous_type or 'png')
                            img.add_header('Content-ID', f'<{cid_img}>')
                            img.add_header('Content-Disposition', 'inline', filename=f'{cid_img}.{sous_type or "png"}')
                            related.attach(img)
                        alternative.attach(related)
                    else:
                        alternative.attach(html_part)
                if msg is not alternative:
                    msg.attach(alternative)
                    from email.mime.application import MIMEApplication
                    for nom, octets, type_mime in (attachments or []):
                        partie = MIMEApplication(octets, _subtype=(type_mime or 'application/octet-stream').split('/')[-1])
                        partie.add_header('Content-Disposition', 'attachment', filename=nom)
                        msg.attach(partie)
                
                # Essayer TLS d'abord
                try:
                    logger.info(f"🔄 Connexion TLS sur {self.smtp_server}:{self.smtp_port_tls}")
                    with smtplib.SMTP(self.smtp_server, self.smtp_port_tls, timeout=self.timeout) as server:
                        server.ehlo()
                        server.starttls(context=ssl.create_default_context())
                        server.ehlo()
                        server.login(self.sender_email, self.password)
                        server.send_message(msg, from_addr=self.sender_email, to_addrs=recipients)
                    
                except Exception as tls_error:
                    logger.warning(f"⚠️ TLS échoué, tentative SSL: {tls_error}")
                    
                    # Fallback SSL
                    logger.info(f"🔄 Connexion SSL sur {self.smtp_server}:{self.smtp_port_ssl}")
                    context = ssl.create_default_context()
                    with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port_ssl, timeout=self.timeout, context=context) as server:
                        server.login(self.sender_email, self.password)
                        server.send_message(msg, from_addr=self.sender_email, to_addrs=recipients)
                
                logger.info(f"✅ Email envoyé avec succès à {to_email}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Erreur tentative {attempt}: {e}")
                if attempt == max_retries:
                    return False
                time.sleep(2 ** attempt)  # Exponential backoff
        
        return False

# Initialiser le service email
email_service = EmailService()
