# ============================================
# decorators/operateur.py
# ============================================

from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def operateur_required(f):
    """Décorateur pour vérifier les permissions opérationnelles"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Veuillez vous connecter', 'warning')
            return redirect(url_for('auth.login'))
        
        # Vérifier si l'utilisateur a des permissions opérationnelles
        if not current_user.est_operateur:
            flash('Accès non autorisé. Permissions opérationnelles requises.', 'error')
            return redirect(url_for('dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function