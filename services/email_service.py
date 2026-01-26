# services/email_service.py
from flask_mail import Message
from flask import current_app
from extensions import mail

def envoyer_identifiants_client(client, admin_user, mot_de_passe):
    """Envoie les identifiants au client"""
    
    msg = Message(
        subject=f"Bienvenue sur FabriceKonan Corporate Intelligence - {client.nom}",
        recipients=[client.contact_email],
        sender=current_app.config['MAIL_DEFAULT_SENDER']
    )
    
    msg.html = f"""
    <h2>Bienvenue sur FabriceKonan Corporate Intelligence !</h2>
    
    <p>Cher {client.contact_nom},</p>
    
    <p>Votre environnement client a été créé avec succès.</p>
    
    <h3>Informations d'accès :</h3>
    <ul>
        <li><strong>URL de connexion :</strong> https://{client.domaine or client.reference + '.votreplateforme.com'}</li>
        <li><strong>Identifiant admin :</strong> {admin_user.username}</li>
        <li><strong>Mot de passe temporaire :</strong> {mot_de_passe}</li>
    </ul>
    
    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <h4>Premières étapes recommandées :</h4>
        <ol>
            <li>Connectez-vous avec les identifiants ci-dessus</li>
            <li>Changez votre mot de passe immédiatement</li>
            <li>Créez vos premiers utilisateurs</li>
            <li>Configurez vos directions et services</li>
            <li>Commencer la cartographie des risques</li>
        </ol>
    </div>
    
    <p><strong>Support technique :</strong> support@votreentreprise.com</p>
    
    <p>Cordialement,<br>
    L'équipe FabriceKonan Corporate Intelligence</p>
    """
    
    try:
        mail.send(msg)
        return True
    except Exception as e:
        print(f"❌ Erreur envoi email: {e}")
        return False