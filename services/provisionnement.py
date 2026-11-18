
# --- Journal (remplace les anciens print()) : erreurs -> WARNING (journaux du serveur) ; le reste -> DEBUG,
#     visible seulement avec EGALYX_TRACES=1. Ajouté le 18/11/2026 (ménage).
import logging as _logging_journal
import os as _os_journal
_JOURNAL = _logging_journal.getLogger('egalyx.services.provisionnement')
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
import os
import subprocess
import paramiko
from datetime import datetime
import secrets
import json

class ServiceProvisionnement:
    """Service pour provisionner les environnements clients"""
    
    def __init__(self):
        self.config = {
            'serveur_master': os.environ.get('MASTER_SERVER', 'localhost'),
            'chemin_ansible': os.environ.get('ANSIBLE_PATH', '/opt/ansible'),
            'chemin_terraform': os.environ.get('TERRAFORM_PATH', '/opt/terraform'),
            'db_master_host': os.environ.get('DB_MASTER_HOST', 'localhost'),
            'db_master_user': os.environ.get('DB_MASTER_USER', 'postgres'),
            'db_master_password': os.environ.get('DB_MASTER_PASSWORD', '')
        }
    
    def creer_client(self, client_data, provision_serveur=False):
        """Crée un nouveau client avec son environnement"""
        
        # 1. Générer les identifiants API
        api_key = secrets.token_urlsafe(32)
        secret_key = secrets.token_urlsafe(64)
        
        # 2. Créer la base de données client
        db_name = f"client_{client_data['reference'].lower()}"
        db_user = f"user_{client_data['reference'].lower()}"
        db_password = secrets.token_urlsafe(16)
        
        # 3. Provisionner le serveur si demandé
        if provision_serveur:
            environnement = self.provisionner_serveur(client_data)
        else:
            # Utiliser le serveur partagé
            environnement = {
                'sous_domaine': f"{client_data['reference']}.votreplateforme.com",
                'url_acces': f"https://{client_data['reference']}.votreplateforme.com",
                'db_host': self.config['db_master_host'],
                'db_name': db_name,
                'db_user': db_user,
                'db_password': db_password,
                'server_ip': self.config['serveur_master'],
                'statut': 'actif'
            }
        
        # 4. Créer l'admin client
        admin_data = {
            'username': f"admin_{client_data['reference']}",
            'email': client_data['contact_email'],
            'role': 'admin',
            'client_id': None,  # Sera rempli après création du client
            'is_client_admin': True
        }
        
        return {
            'client': client_data,
            'environnement': environnement,
            'admin': admin_data,
            'identifiants': {
                'api_key': api_key,
                'secret_key': secret_key,
                'db_credentials': {
                    'host': environnement['db_host'],
                    'database': db_name,
                    'user': db_user,
                    'password': db_password
                }
            }
        }
    
    def provisionner_serveur(self, client_data):
        """Provisionne un serveur dédié pour le client"""
        
        # Utilisation d'Ansible pour provisionner
        playbook_path = f"{self.config['chemin_ansible']}/provision_client.yml"
        
        # Variables pour Ansible
        vars_ansible = {
            'client_reference': client_data['reference'],
            'client_domaine': client_data.get('domaine', f"{client_data['reference']}.votreplateforme.com"),
            'db_name': f"client_{client_data['reference'].lower()}",
            'db_user': f"user_{client_data['reference'].lower()}",
            'db_password': secrets.token_urlsafe(16)
        }
        
        try:
            # Exécuter Ansible
            cmd = [
                'ansible-playbook',
                playbook_path,
                '--extra-vars', json.dumps(vars_ansible)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return {
                    'sous_domaine': vars_ansible['client_domaine'],
                    'url_acces': f"https://{vars_ansible['client_domaine']}",
                    'db_host': 'localhost',  # Base locale au serveur
                    'db_name': vars_ansible['db_name'],
                    'db_user': vars_ansible['db_user'],
                    'db_password': vars_ansible['db_password'],
                    'server_ip': self.get_server_ip(vars_ansible['client_domaine']),
                    'statut': 'actif',
                    'details_ansible': result.stdout
                }
            else:
                raise Exception(f"Erreur Ansible: {result.stderr}")
                
        except Exception as e:
            _journal(f"❌ Erreur provisionnement: {e}")
            return None
    
    def get_server_ip(self, domaine):
        """Résout l'IP d'un domaine"""
        import socket
        try:
            return socket.gethostbyname(domaine)
        except:
            return 'N/A'
    
    def suspendre_client(self, client_id):
        """Suspend un client (mise en pause)"""
        # Logique de suspension
        pass
    
    def reactiver_client(self, client_id):
        """Réactive un client suspendu"""
        # Logique de réactivation
        pass
    
    def supprimer_client(self, client_id):
        """Supprime complètement un client"""
        # Logique de suppression sécurisée
        pass