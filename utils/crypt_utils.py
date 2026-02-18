# utils/crypt_utils.py

import base64
import json
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import os

# Clé de chiffrement (à stocker dans les variables d'environnement)
# Générer avec: Fernet.generate_key()
SECRET_KEY = os.environ.get('CRYPT_KEY', Fernet.generate_key())
cipher = Fernet(SECRET_KEY if isinstance(SECRET_KEY, bytes) else SECRET_KEY.encode())

def encrypt_value(value):
    """Chiffre une valeur"""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        value = json.dumps(value)
    return cipher.encrypt(str(value).encode()).decode()

def decrypt_value(encrypted_value):
    """Déchiffre une valeur"""
    if encrypted_value is None:
        return None
    try:
        return cipher.decrypt(encrypted_value.encode()).decode()
    except:
        return encrypted_value

def encrypt_dict(data):
    """Chiffre toutes les valeurs sensibles d'un dict"""
    if not data:
        return data
    encrypted = {}
    for key, value in data.items():
        if key in ['password', 'token', 'secret', 'api_key']:
            encrypted[key] = encrypt_value(value)
        else:
            encrypted[key] = value
    return encrypted

def decrypt_dict(data):
    """Déchiffre toutes les valeurs d'un dict"""
    if not data:
        return data
    decrypted = {}
    for key, value in data.items():
        if key in ['password', 'token', 'secret', 'api_key']:
            decrypted[key] = decrypt_value(value)
        else:
            decrypted[key] = value
    return decrypted