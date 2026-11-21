"""Recette : fichiers déposés conservés d'un déploiement à l'autre (disque persistant Render)."""
import os
import shutil
import sys
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from flask import Flask
from egalyx import stockage_persistant as sp

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


base = tempfile.mkdtemp(prefix='egalyx_sp_')
disque = os.path.join(base, 'var_data')


def deployer(n, fichiers_depot=None):
    """Nouveau déploiement : dossier de projet vierge (comme Render), avec les fichiers livrés par le dépôt."""
    racine = os.path.join(base, f'deploiement_{n}')
    os.makedirs(os.path.join(racine, 'static', 'uploads', 'logos'))
    os.makedirs(os.path.join(racine, 'uploads'))
    for chemin, contenu in (fichiers_depot or {}).items():
        os.makedirs(os.path.dirname(os.path.join(racine, chemin)), exist_ok=True)
        open(os.path.join(racine, chemin), 'w').write(contenu)
    app = Flask('essai', root_path=racine, instance_path=os.path.join(racine, 'instance'))
    return app, racine


print('--- Sans dossier de données : rien ne change')
os.environ.pop('EGALYX_DONNEES', None)
os.environ.pop('RENDER', None)
app, racine = deployer(0)
verif('poste local : aucune opération', sp.preparer(app) == [] and not os.path.islink(os.path.join(racine, 'uploads')))
os.environ['RENDER'] = 'true'
verif('Render sans disque monté : aucune opération', sp.dossier_donnees() is None)
os.environ.pop('RENDER')

print('--- Premier déploiement')
os.environ['EGALYX_DONNEES'] = disque
app, racine = deployer(1, {'static/uploads/logos/defaut.png': 'logo livré', 'uploads/lisez-moi.txt': 'dépôt'})
faits = sp.preparer(app)
verif('trois dossiers reliés au disque', len(faits) == 3 and all('→' in f for f in faits), faits)
verif('instance/ est un lien vers le disque', os.path.realpath(app.instance_path) == os.path.realpath(os.path.join(disque, 'instance')))
verif('fichiers livrés recopiés sur le disque', open(os.path.join(disque, 'static_uploads', 'logos', 'defaut.png')).read() == 'logo livré'
      and os.path.exists(os.path.join(disque, 'uploads', 'lisez-moi.txt')))
# l'application écrit des fichiers par les chemins habituels
os.makedirs(os.path.join(app.instance_path, 'logos'), exist_ok=True)
open(os.path.join(app.instance_path, 'logos', '1.png'), 'w').write('logo client 1')
open(os.path.join(racine, 'uploads', 'preuve.pdf'), 'w').write('preuve')
open(os.path.join(racine, 'static', 'uploads', 'logos', 'defaut.png'), 'w').write('logo modifié par le client')
verif('écriture par les chemins habituels → sur le disque', os.path.exists(os.path.join(disque, 'instance', 'logos', '1.png')))
verif('deuxième démarrage du même déploiement : rien à refaire', all('déjà relié' in f for f in sp.preparer(app)))

print('--- Redéploiement (dossier de projet vierge)')
shutil.rmtree(racine)
app2, racine2 = deployer(2, {'static/uploads/logos/defaut.png': 'logo livré', 'uploads/nouveau.txt': 'nouveau fichier du dépôt'})
sp.preparer(app2)
verif('logo du client conservé', open(os.path.join(app2.instance_path, 'logos', '1.png')).read() == 'logo client 1')
verif('pièce jointe conservée', open(os.path.join(racine2, 'uploads', 'preuve.pdf')).read() == 'preuve')
verif('fichier modifié sur le disque jamais écrasé par celui du dépôt',
      open(os.path.join(racine2, 'static', 'uploads', 'logos', 'defaut.png')).read() == 'logo modifié par le client')
verif('nouveau fichier du dépôt ajouté', os.path.exists(os.path.join(racine2, 'uploads', 'nouveau.txt')))

print('--- Plusieurs processus au démarrage (gunicorn)')
app3, racine3 = deployer(3)
erreurs = []
fils = [threading.Thread(target=lambda: erreurs.extend(f for f in sp.preparer(app3) if '⚠️' in f)) for _ in range(4)]
[f.start() for f in fils]; [f.join() for f in fils]
verif('démarrages simultanés sans erreur', not erreurs and os.path.islink(os.path.join(racine3, 'uploads')), erreurs)

print('--- Un problème ne bloque pas le démarrage')
app4, racine4 = deployer(4)
os.rmdir(os.path.join(racine4, 'uploads')); open(os.path.join(racine4, 'uploads'), 'w').write('fichier au lieu d\'un dossier')
faits = sp.preparer(app4)
verif('erreur signalée dans le journal, les autres dossiers reliés', any('⚠️' in f for f in faits) and os.path.islink(app4.instance_path), faits)

os.environ.pop('EGALYX_DONNEES', None)
shutil.rmtree(base, ignore_errors=True)
print(f'\n{sum(res)}/{len(res)} vérifications réussies')
