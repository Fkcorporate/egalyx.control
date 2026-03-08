# services/email_service.py - VERSION COMPLÈTE POUR HOSTINGER
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import os
from datetime import datetime
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailService:
    """Service d'email utilisant SMTP Hostinger"""
    
    def __init__(self):
        # Configuration Hostinger
        self.smtp_server = 'smtp.hostinger.com'  # Serveur SMTP Hostinger
        self.smtp_port = 465  # Port SSL (recommandé) ou 587 pour TLS
        
        # Vos identifiants Hostinger
        self.sender_email = 'contact@egalyx.com'  # Votre email chez Hostinger
        self.sender_name = 'Egalyx Control'
        self.password = os.environ.get('HOSTINGER_EMAIL_PASSWORD', '')
        
        # Mode simulation si pas de mot de passe
        if not self.password:
            logger.warning("⚠️ HOSTINGER_EMAIL_PASSWORD non défini - emails en mode simulation")
            self.simulation_mode = True
        else:
            self.simulation_mode = False
            logger.info(f"✅ Service email Hostinger configuré pour {self.sender_email}")
    
    def send_email(self, to_email, subject, body, html_body=None, cc=None, bcc=None):
        """Envoyer un email via SMTP Hostinger"""
        
        # Mode simulation
        if self.simulation_mode:
            logger.info(f"📧 [SIMULATION] Email à: {to_email}")
            logger.info(f"   Sujet: {subject}")
            logger.info(f"   Contenu: {body[:100]}...")
            return True
        
        try:
            # Créer le message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = formataddr((self.sender_name, self.sender_email))
            
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
            
            # Connexion SMTP avec SSL (port 465)
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context) as server:
                server.login(self.sender_email, self.password)
                server.send_message(msg, from_addr=self.sender_email, to_addrs=recipients)
            
            logger.info(f"✅ Email envoyé à {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur envoi email: {e}")
            # Fallback en mode simulation
            logger.info(f"📧 [FALLBACK] Email à: {to_email}")
            logger.info(f"   Sujet: {subject}")
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
        
        admin_sent = self.send_email(
            to_email='contact@egalyx.com',  # Votre email Hostinger
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
                .btn {{ display: inline-block; background: linear-gradient(135deg, #0066CC 0%, #3B82F6 100%); color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1 style="margin: 0; font-size: 28px;">✨ Egalyx Control</h1>
                <p style="margin: 10px 0 0; opacity: 0.9;">Confirmation de votre demande</p>
            </div>
            
            <div class="content">
                <h2 style="color: #0A1929;">Bonjour {nom_complet},</h2>
                
                <p style="font-size: 16px; line-height: 1.6;">Nous avons bien reçu votre demande et nous vous remercions de l'intérêt que vous portez à Egalyx Control.</p>
                
                <div class="info-box">
                    <p style="margin: 0 0 10px;"><strong style="color: #0066CC;">📎 Référence :</strong> {reference}</p>
                    <p style="margin: 0 0 10px;"><strong style="color: #0066CC;">📝 Sujet :</strong> {sujet}</p>
                    <p style="margin: 0;"><strong style="color: #0066CC;">📅 Date :</strong> {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>
                </div>
                
                <p style="font-size: 16px; line-height: 1.6;">Notre équipe vous contactera dans les plus brefs délais pour échanger sur vos besoins et organiser une démonstration personnalisée.</p>
                
                <div style="text-align: center;">
                    <a href="https://www.egalyx.com" class="btn">🌐 Visiter notre site</a>
                </div>
                
                <p style="font-size: 16px; line-height: 1.6;">En attendant, vous pouvez déjà découvrir nos fonctionnalités sur notre site web.</p>
                
                <p style="font-size: 16px; line-height: 1.6;">Cordialement,<br><strong>L'équipe Egalyx Control</strong></p>
            </div>
            
            <div class="footer">
                <p style="margin: 0;">© 2024 Egalyx Control. Tous droits réservés.</p>
                <p style="margin: 10px 0 0; font-size: 12px;">Cet email a été envoyé automatiquement, merci de ne pas y répondre.</p>
            </div>
        </body>
        </html>
        """
        
        client_body = f"""
        Confirmation de votre demande - Egalyx Control
        
        Bonjour {nom_complet},
        
        Nous avons bien reçu votre demande et nous vous remercions de l'intérêt que vous portez à Egalyx Control.
        
        Référence : {reference}
        Sujet : {sujet}
        Date : {datetime.now().strftime('%d/%m/%Y à %H:%M')}
        
        Notre équipe vous contactera dans les plus brefs délais pour échanger sur vos besoins.
        
        Cordialement,
        L'équipe Egalyx Control
        """
        
        client_sent = self.send_email(
            to_email=email,
            subject=client_subject,
            body=client_body,
            html_body=client_html
        )
        
        return admin_sent and client_sent

# Initialiser le service email
email_service = EmailService()
