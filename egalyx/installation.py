"""
egalyx/installation.py — commandes pour installer Egalyx chez un client (on-premise) ou sur un nouveau serveur.

    flask creer-super-admin          premier compte super administrateur (questions posées une à une)
    flask verifier-installation      contrôle de l'installation : base, clé secrète, HTTPS, dossiers, e-mails…

Avec Docker :  docker compose exec web flask creer-super-admin
Sans Docker :  dans le dossier de l'application, avec l'environnement virtuel activé.
"""
import os
import sys

import click


def _ok(msg):
    click.echo(click.style('  ✅ ', fg='green') + msg)


def _alerte(msg):
    click.echo(click.style('  ⚠️  ', fg='yellow') + msg)


def _ko(msg):
    click.echo(click.style('  ❌ ', fg='red') + msg)


def enregistrer(app):

    @app.cli.command('creer-super-admin')
    @click.option('--identifiant', prompt="Identifiant de connexion", help="Nom d'utilisateur")
    @click.option('--email', prompt='Adresse e-mail', help='E-mail du compte')
    def creer_super_admin(identifiant, email):
        """Crée un compte super administrateur (mot de passe demandé sans s'afficher)."""
        from models import db, User
        identifiant = identifiant.strip()
        if not identifiant or '@' not in email:
            click.echo('Identifiant ou e-mail invalide.'); sys.exit(1)
        if User.query.filter((User.username == identifiant) | (User.email == email)).first():
            click.echo(f'Un compte « {identifiant} » ou « {email} » existe déjà. '
                       'Pour changer son mot de passe : python3 reinitialiser_mot_de_passe.py ' + identifiant)
            sys.exit(2)
        click.echo('Mot de passe : 12 caractères au moins, avec majuscule, minuscule, chiffre et caractère spécial.')
        u = User(username=identifiant, email=email.strip(), role='super_admin', is_active=True)
        for _ in range(3):
            mdp = click.prompt('Mot de passe', hide_input=True, confirmation_prompt='Retapez-le')
            try:
                u.set_password(mdp)
            except ValueError as e:
                click.echo(f'Refusé : {e}')
                continue
            break
        else:
            click.echo('Abandon.'); sys.exit(3)
        db.session.add(u)
        db.session.commit()
        try:
            from egalyx.commun import journaliser
            journaliser('super_admin_cree_serveur', {'utilisateur': u.id})
            db.session.commit()
        except Exception:  # noqa: BLE001
            db.session.rollback()
        click.echo(f'✅ Super administrateur « {identifiant} » créé. Connectez-vous, puis activez la double authentification.')

    @app.cli.command('verifier-installation')
    def verifier_installation():
        """Contrôle l'installation et indique ce qui manque (rien n'est modifié)."""
        erreurs = 0
        click.echo('\nEgalyx — vérification de l\'installation\n')

        prod = bool(os.environ.get('RENDER')) or os.environ.get('EGALYX_PRODUCTION') == '1'
        (_ok('Mode production actif') if prod and not app.debug else _ko('Mode production INACTIF : ajoutez EGALYX_PRODUCTION=1'))
        erreurs += 0 if prod and not app.debug else 1

        cle = app.config.get('SECRET_KEY') or ''
        if not cle or 'changer_en_production' in cle or len(cle) < 32:
            _ko('SECRET_KEY absente ou faible : mettez une valeur aléatoire de 50 caractères dans .env'); erreurs += 1
        else:
            _ok('Clé secrète définie')

        if app.config.get('SESSION_COOKIE_SECURE'):
            _ok('Cookies réservés à HTTPS')
        else:
            _alerte('Cookies non réservés à HTTPS (EGALYX_HTTPS=0 ?) : acceptable pour un essai seulement')

        uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        try:
            from models import db, User
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            _ok(f"Base de données joignable ({'PostgreSQL' if uri.startswith('postgres') else uri.split(':')[0]})")
            if not uri.startswith('postgres'):
                _alerte('Base SQLite : utilisez PostgreSQL chez un client')
            n = User.query.filter_by(role='super_admin').count()
            (_ok(f'{n} super administrateur(s)') if n else _ko('Aucun super administrateur : flask creer-super-admin'))
            erreurs += 0 if n else 1
        except Exception as e:  # noqa: BLE001
            _ko(f'Base de données injoignable : {e}'); erreurs += 1

        try:
            from egalyx.stockage_persistant import dossier_donnees
            d = dossier_donnees()
        except Exception:  # noqa: BLE001
            d = os.environ.get('EGALYX_DONNEES')
        if d and os.path.isdir(d) and os.access(d, os.W_OK):
            _ok(f'Dossier des fichiers déposés : {d}')
        else:
            _ko(f'Dossier des fichiers déposés absent ou non inscriptible ({d or "EGALYX_DONNEES non définie"})'); erreurs += 1

        sv = os.environ.get('EGALYX_DOSSIER_SAUVEGARDES')
        if sv and os.path.isdir(sv) and os.access(sv, os.W_OK):
            _ok(f'Dossier des sauvegardes : {sv}')
        else:
            _alerte('Dossier des sauvegardes non défini : EGALYX_DOSSIER_SAUVEGARDES')

        if os.environ.get('MAIL_SERVER') and os.environ.get('MAIL_USERNAME'):
            _ok(f"E-mails : {os.environ['MAIL_SERVER']}")
        else:
            _alerte('E-mails non configurés (MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD) : pas de notifications')

        for module, usage in (('pypdf', 'papiers à en-tête des rapports'), ('weasyprint', 'rapport PDF « élégant »'),
                              ('docx', 'exports Word'), ('openpyxl', 'exports Excel')):
            try:
                __import__(module)
                _ok(f'{module} présent ({usage})')
            except Exception:  # noqa: BLE001
                _alerte(f'{module} absent : {usage} indisponible')

        try:
            from egalyx import licence
            e = licence.etat(force=True)
            if e['statut'] == 'non_requise':
                _ok('Licence non requise sur cette installation')
            elif e.get('licence'):
                msg = f"Licence {e['licence']['client']} jusqu'au {e['licence']['fin']:%d/%m/%Y} ({e['jours']} jours)"
                (_ok(msg) if e['statut'] == 'valide' else _alerte(msg + ' : à renouveler'))
                if e['statut'] == 'expiree':
                    erreurs += 1
            else:
                _ko(e.get('message') or 'Licence absente'); erreurs += 1
        except Exception as ex:  # noqa: BLE001
            _alerte(f'Licence : vérification impossible ({ex})')

        click.echo('')
        if erreurs:
            click.echo(click.style(f'{erreurs} point(s) bloquant(s) à corriger.', fg='red')); sys.exit(1)
        click.echo(click.style('Installation prête.', fg='green'))
