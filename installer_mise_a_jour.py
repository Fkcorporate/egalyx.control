#!/usr/bin/env python3
"""
Installe une mise à jour Egalyx dans le dossier du projet, sans rien supprimer.

    python3 installer_mise_a_jour.py /Users/egalyx/zapata/controle_interne3

- Copie chaque fichier du paquet au même chemin dans le projet (les dossiers sont FUSIONNÉS, jamais remplacés).
- Garde une copie de chaque fichier remplacé dans <projet>/sauvegarde_maj_<date>/.
- Vérifie ensuite que les fichiers Python se compilent et que tous les modules attendus par egalyx/__init__.py
  sont présents.
Faites aussi une sauvegarde de la base avant (flask sauvegarder).
"""
import os
import py_compile
import re
import shutil
import sys
from datetime import datetime

ICI = os.path.dirname(os.path.abspath(__file__))
IGNORER = {'installer_mise_a_jour.py', 'A_LIRE_MISE_A_JOUR.txt', '.DS_Store'}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    projet = os.path.abspath(os.path.expanduser(sys.argv[1]))
    if not (os.path.isfile(os.path.join(projet, 'app.py')) and os.path.isdir(os.path.join(projet, 'egalyx'))):
        print(f"« {projet} » ne ressemble pas au dossier du projet (app.py et egalyx/ attendus).")
        sys.exit(1)
    sauvegarde = os.path.join(projet, 'sauvegarde_maj_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    copies, nouveaux = [], []
    for racine, _dossiers, fichiers in os.walk(ICI):
        for nom in fichiers:
            if nom in IGNORER or nom.endswith('.pyc'):
                continue
            source = os.path.join(racine, nom)
            rel = os.path.relpath(source, ICI)
            cible = os.path.join(projet, rel)
            if os.path.exists(cible):
                dest = os.path.join(sauvegarde, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(cible, dest)
                copies.append(rel)
            else:
                nouveaux.append(rel)
            os.makedirs(os.path.dirname(cible), exist_ok=True)
            shutil.copyfile(source, cible)      # date du jour : aucun cache .pyc ancien ne peut être repris
    print(f"{len(copies)} fichier(s) remplacé(s) (anciennes versions dans {os.path.basename(sauvegarde)}/), "
          f"{len(nouveaux)} nouveau(x) :")
    for rel in sorted(nouveaux):
        print('   +', rel)

    # caches Python compilés : supprimés pour que les nouveaux fichiers soient relus au démarrage
    for racine, dossiers, _f in os.walk(projet):
        if 'venv' in racine.split(os.sep) or '.venv' in racine.split(os.sep) or 'site-packages' in racine:
            continue
        if os.path.basename(racine) == '__pycache__' and os.path.relpath(racine, projet).split(os.sep)[0] in ('egalyx', '__pycache__'):
            shutil.rmtree(racine, ignore_errors=True)
    pyc_app = os.path.join(projet, '__pycache__')
    if os.path.isdir(pyc_app):
        shutil.rmtree(pyc_app, ignore_errors=True)

    erreurs = []
    import filecmp
    for rel in copies + nouveaux:
        if not filecmp.cmp(os.path.join(ICI, rel), os.path.join(projet, rel), shallow=False):
            erreurs.append(f'{rel} : la copie diffère du paquet (fichier verrouillé ? droits ?)')
    for rel in copies + nouveaux:
        if rel.endswith('.py'):
            try:
                py_compile.compile(os.path.join(projet, rel), doraise=True)
            except py_compile.PyCompileError as e:
                erreurs.append(f'{rel} : {e.msg}')
    init = open(os.path.join(projet, 'egalyx', '__init__.py'), encoding='utf-8').read()
    attendus = set()
    for ligne in re.findall(r'^\s*from egalyx import ([^\n#]+)', init, re.M):
        for nom in ligne.replace('(', ' ').replace(')', ' ').split(','):
            nom = nom.strip().split(' as ')[0].strip()
            if nom and nom.isidentifier() and nom != 'enregistrer_extensions':
                attendus.add(nom)
    for nom in sorted(attendus):
        if not (os.path.isfile(os.path.join(projet, 'egalyx', nom + '.py'))
                or os.path.isdir(os.path.join(projet, 'egalyx', nom))):
            erreurs.append(f'egalyx/{nom}.py manquant')
    if erreurs:
        print('\nPROBLÈMES :')
        for e in erreurs:
            print('   -', e)
        sys.exit(2)
    version = os.path.basename(ICI)
    print(f'\nInstallation vérifiée ({version}) : {len(copies) + len(nouveaux)} fichiers identiques au paquet.')
    print('ARRÊTEZ complètement le serveur (Ctrl+C) puis relancez-le : un serveur resté ouvert garde l\'ancien code.')


if __name__ == '__main__':
    main()
