"""
Choisir un nouveau mot de passe pour un compte, directement sur le serveur (mot de passe oublié du super-admin…).

Usage (dans le dossier du projet) :
    python3 reinitialiser_mot_de_passe.py fabricekonan
    python3 reinitialiser_mot_de_passe.py fabricekonan --sans-2fa     (téléphone perdu aussi : double authentification
                                                                     remise à zéro, à réactiver à la connexion)
Le mot de passe est demandé deux fois, sans s'afficher ; il doit respecter les règles de l'outil (12 caractères,
majuscule, minuscule, chiffre, caractère spécial). Le compte est aussi débloqué (tentatives échouées remises à zéro).
Sur Render : onglet « Shell » du service, puis la même commande.
Seule une personne qui a accès au serveur peut l'utiliser : rien n'est exposé sur le site.
"""
import getpass
import os
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    sans_2fa = '--sans-2fa' in sys.argv
    if len(args) != 1:
        print(__doc__)
        sys.exit(1)
    nom = args[0].strip()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    print('Chargement de l\'application…')
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        from app import app
        from models import db, User
    with app.app_context():
        u = User.query.filter_by(username=nom).first()
        if u is None:
            proches = [x.username for x in User.query.filter(User.username.ilike(f'%{nom[:4]}%')).limit(5)]
            print(f'Aucun compte « {nom} ».' + (f' Comptes proches : {", ".join(proches)}' if proches else ''))
            sys.exit(2)
        print(f'Compte trouvé : {u.username} (rôle : {getattr(u, "role", "?")}, e-mail : {getattr(u, "email", "") or "—"})')
        for essai in range(3):
            mdp = getpass.getpass('Nouveau mot de passe : ')
            if mdp != getpass.getpass('Retapez-le : '):
                print('Les deux saisies sont différentes, recommencez.')
                continue
            try:
                u.set_password(mdp, check_history=False)
            except ValueError as e:
                print(f'Refusé : {e}')
                continue
            break
        else:
            print('Abandon.')
            sys.exit(3)
        for attr, val in (('failed_login_attempts', 0), ('is_blocked', False), ('locked_until', None),
                          ('lock_reason', None), ('blocked_reason', None), ('last_failed_login', None)):
            if hasattr(u, attr):
                setattr(u, attr, val)
        if hasattr(u, 'is_active') and not u.is_active:
            u.is_active = True
            print('Le compte était désactivé : il est réactivé.')
        if sans_2fa:
            try:
                from egalyx.double_auth import _reinitialiser
                _reinitialiser(u)
                print('Double authentification remise à zéro : vous la réactiverez à la prochaine connexion.')
            except Exception as e:  # noqa: BLE001
                print(f'Double authentification non modifiée ({e}).')
        db.session.commit()
        try:
            from egalyx.commun import journaliser
            journaliser('mot_de_passe_reinitialise_serveur', {'utilisateur': u.id, 'sans_2fa': sans_2fa}, client_id=u.client_id)
            db.session.commit()
        except Exception:  # noqa: BLE001
            db.session.rollback()
        assert u.check_password(mdp), 'vérification impossible'
        print(f'✅ Nouveau mot de passe enregistré pour {u.username}. Connectez-vous avec lui.')


if __name__ == '__main__':
    main()
