# services/email_service.py - VERSION CORRIGÉE POUR HOSTINGER
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
    """Service d'email utilisant SMTP Hostinger - Version robuste"""
    
    def __init__(self):
        # Configuration Hostinger
        self.smtp_server = 'smtp.hostinger.com'
        
        # === OPTION 1: TLS sur le port 587 (recommandé) ===
        self.smtp_port_tls = 587
        self.use_tls = True  # Utiliser STARTTLS
        
        # === OPTION 2: SSL direct sur le port 465 (fallback) ===
        self.smtp_port_ssl = 465
        
        # Vos identifiants Hostinger
        self.sender_email = 'contact@egalyx.com'
        self.sender_name = 'Egalyx Control'
        self.password = os.environ.get('HOSTINGER_EMAIL_PASSWORD', '')
        
        # Timeout de connexion
        self.timeout = 30  # secondes
        
        # Mode simulation si pas de mot de passe
        if not self.password:
            logger.warning("⚠️ HOSTINGER_EMAIL_PASSWORD non défini - emails en mode simulation")
            self.simulation_mode = True
        else:
            self.simulation_mode = False
            logger.info(f"✅ Service email Hostinger configuré pour {self.sender_email}")
    
    def test_smtp_connection(self):
        """Teste la connexion SMTP avant envoi"""
        try:
            # Test avec TLS (port 587)
            logger.info("🔄 Test connexion SMTP TLS (port 587)...")
            with smtplib.SMTP(self.smtp_server, self.smtp_port_tls, timeout=self.timeout) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(self.sender_email, self.password)
                logger.info("✅ Connexion TLS réussie")
                return 'tls', server
            
        except Exception as e_tls:
            logger.warning(f"⚠️ Connexion TLS échouée: {e_tls}")
            
            try:
                # Fallback avec SSL (port 465)
                logger.info("🔄 Test connexion SMTP SSL (port 465)...")
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port_ssl, timeout=self.timeout, context=context) as server:
                    server.login(self.sender_email, self.password)
                    logger.info("✅ Connexion SSL réussie")
                    return 'ssl', server
                    
            except Exception as e_ssl:
                logger.error(f"❌ Toutes les connexions ont échoué: {e_ssl}")
                return None, None
    
    def send_email(self, to_email, subject, body, html_body=None, cc=None, bcc=None, max_retries=3):
        """Envoyer un email via SMTP Hostinger avec mécanisme de retry"""
        
        # Mode simulation
        if self.simulation_mode:
            logger.info(f"📧 [SIMULATION] Email à: {to_email}")
            logger.info(f"   Sujet: {subject}")
            return True
        
        # Tentatives multiples
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"📨 Tentative {attempt}/{max_retries} d'envoi à {to_email}")
                
                # Créer le message
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
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
                msg.attach(text_part)
                
                # Partie HTML si fournie
                if html_body:
                    html_part = MIMEText(html_body, 'html', 'utf-8')
                    msg.attach(html_part)
                
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
                
            except smtplib.SMTPAuthenticationError as e:
                logger.error(f"❌ Erreur d'authentification SMTP: {e}")
                logger.error("   Vérifiez votre mot de passe dans les variables d'environnement")
                if attempt == max_retries:
                    return False
                time.sleep(2 ** attempt)  # Exponential backoff
                
            except smtplib.SMTPException as e:
                logger.error(f"❌ Erreur SMTP: {e}")
                if attempt == max_retries:
                    return False
                time.sleep(2 ** attempt)
                
            except socket.error as e:
                logger.error(f"❌ Erreur réseau: {e}")
                if attempt == max_retries:
                    return False
                time.sleep(2 ** attempt)
                
            except Exception as e:
                logger.error(f"❌ Erreur inattendue: {e}")
                if attempt == max_retries:
                    return False
                time.sleep(2 ** attempt)
        
        return False
    
    def send_contact_confirmation(self, nom_complet, email, societe, telephone, sujet, message, reference):
        """Envoyer les emails pour une demande de contact"""
        
        # 1. Email à l'administrateur (notification)
        admin_subject = f"🔔 Nouvelle demande: {sujet[:50]}"
        admin_body = f"""
        NOUVELLE DEMANDE DE CONTACT
        ===========================
        
        📋 Informations :
        - Nom complet : {nom_complet}
        - Email : {email}
        - Société : {societe or 'Non spécifié'}
        - Téléphone : {telephone or 'Non spécifié'}
        
        📝 Sujet : {sujet}
        
        💬 Message :
        {message}
        
        📎 Référence : {reference}
        📅 Date : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        """
        
        logger.info(f"📧 Envoi notification admin pour {reference}")
        admin_sent = self.send_email(
            to_email='contact@egalyx.com',
            subject=admin_subject,
            body=admin_body
        )
        
        # 2. Email de confirmation au client
        client_subject = "Confirmation de votre demande - Egalyx Control"
        client_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #0A1929 0%, #1A3C6B 100%); color: white; padding: 40px 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ padding: 40px 30px; background: #f8fafc; border-radius: 0 0 10px 10px; }}
                .info-box {{ background: white; padding: 25px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #0066CC; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }}
                .footer {{ text-align: center; padding: 30px; color: #666; font-size: 14px; border-top: 1px solid #e2e8f0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1 style="margin: 0; font-size: 28px;">Egalyx Control</h1>
                <p style="margin: 10px 0 0; opacity: 0.9;">Confirmation de votre demande</p>
            </div>
            
            <div class="content">
                <h2 style="color: #0A1929;">Bonjour {nom_complet},</h2>
                
                <p>Nous avons bien reçu votre demande.</p>
                
                <div class="info-box">
                    <p><strong>Référence :</strong> {reference}</p>
                    <p><strong>Sujet :</strong> {sujet}</p>
                    <p><strong>Date :</strong> {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>
                </div>
                
                <p>Notre équipe vous contactera dans les plus brefs délais.</p>
                
                <p>Cordialement,<br><strong>L'équipe Egalyx Control</strong></p>
            </div>
            
            <div class="footer">
                <p>© 2024 Egalyx Control</p>
            </div>
        </body>
        </html>
        """
        
        client_body = f"""
        Confirmation de votre demande - Egalyx Control
        
        Bonjour {nom_complet},
        
        Nous avons bien reçu votre demande.
        
        Référence : {reference}
        Sujet : {sujet}
        Date : {datetime.now().strftime('%d/%m/%Y à %H:%M')}
        
        Notre équipe vous contactera dans les plus brefs délais.
        
        Cordialement,
        L'équipe Egalyx Control
        """
        
        logger.info(f"📧 Envoi confirmation client à {email} pour {reference}")
        client_sent = self.send_email(
            to_email=email,
            subject=client_subject,
            body=client_body,
            html_body=client_html
        )
        
        if admin_sent and client_sent:
            logger.info(f"✅ Tous les emails envoyés avec succès pour {reference}")
        else:
            logger.warning(f"⚠️ Certains emails n'ont pas pu être envoyés pour {reference}")
        
        return admin_sent and client_sent

# Route de test pour diagnostiquer
@app.route('/test-smtp')
def test_smtp():
    """Route de test pour vérifier la configuration SMTP"""
    results = []
    
    results.append("🔧 TEST CONNEXION SMTP HOSTINGER")
    results.append("=" * 50)
    
    # Vérifier la variable d'environnement
    password = os.environ.get('HOSTINGER_EMAIL_PASSWORD', '')
    if password:
        results.append(f"✅ HOSTINGER_EMAIL_PASSWORD: Défini ({'*' * len(password)})")
    else:
        results.append("❌ HOSTINGER_EMAIL_PASSWORD: Non défini")
    
    # Tester la connexion
    try:
        # Test TLS (port 587)
        results.append(f"\n🔄 Test TLS sur smtp.hostinger.com:587...")
        with smtplib.SMTP('smtp.hostinger.com', 587, timeout=10) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            results.append("✅ Connexion TLS établie")
            
            # Test login
            if password:
                server.login('contact@egalyx.com', password)
                results.append("✅ Authentification réussie")
            else:
                results.append("⚠️ Login non testé (pas de mot de passe)")
    except Exception as e:
        results.append(f"❌ Erreur TLS: {str(e)}")
    
    try:
        # Test SSL (port 465)
        results.append(f"\n🔄 Test SSL sur smtp.hostinger.com:465...")
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL('smtp.hostinger.com', 465, timeout=10, context=context) as server:
            results.append("✅ Connexion SSL établie")
            
            # Test login
            if password:
                server.login('contact@egalyx.com', password)
                results.append("✅ Authentification réussie")
            else:
                results.append("⚠️ Login non testé (pas de mot de passe)")
    except Exception as e:
        results.append(f"❌ Erreur SSL: {str(e)}")
    
    return "<pre>" + "\n".join(results) + "</pre>"

# Initialiser le service email
email_service = EmailService()
