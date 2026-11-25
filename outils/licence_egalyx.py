#!/usr/bin/env python3
"""
outils/licence_egalyx.py — émission des clés de licence on-premise (à utiliser par Egalyx uniquement).

  1) Une seule fois, sur VOTRE ordinateur :
        python3 outils/licence_egalyx.py initialiser
     -> crée la clé privée dans ~/.egalyx_licence/cle_privee.txt (à garder secrète et à sauvegarder,
        par exemple sur une clé USB : sans elle vous ne pourrez plus émettre de licences)
     -> écrit la clé publique dans egalyx/licence_cle.py (celle-là se committe dans le dépôt, sans risque)

  2) Pour chaque client :
        python3 outils/licence_egalyx.py emettre --client "SODEMI" --fin 2027-12-31 --utilisateurs 25
     -> affiche une clé EGX1-… à transmettre au client (dans .env : EGALYX_LICENCE=…, ou page /licence)

  3) Pour relire une clé :
        python3 outils/licence_egalyx.py lire EGX1-…
"""
import argparse
import base64
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER_PUBLIC = RACINE / 'egalyx' / 'licence_cle.py'
DOSSIER = Path(os.environ.get('EGALYX_DOSSIER_LICENCE') or Path.home() / '.egalyx_licence')
PRIVEE = DOSSIER / 'cle_privee.txt'


def _b64(o):
    return base64.urlsafe_b64encode(o).decode().rstrip('=')


def _b64d(s):
    return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def _ecrire_publique(pub):
    FICHIER_PUBLIC.write_text(
        '"""Clé PUBLIQUE d\'Egalyx pour vérifier les licences on-premise (écrite par outils/licence_egalyx.py).\n'
        'Elle ne permet pas de fabriquer une licence : elle peut être committée sans risque."""\n'
        f"CLE_PUBLIQUE = '{pub}'\n", encoding='utf-8')


def initialiser(args):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    if PRIVEE.exists() and not args.forcer:
        print(f'Une clé privée existe déjà : {PRIVEE}\n'
              'La remplacer rendrait invalides toutes les licences déjà émises (ajoutez --forcer si c\'est voulu).')
        cle = Ed25519PrivateKey.from_private_bytes(_b64d(PRIVEE.read_text().strip()))
    else:
        cle = Ed25519PrivateKey.generate()
        DOSSIER.mkdir(mode=0o700, parents=True, exist_ok=True)
        brut = cle.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                 serialization.NoEncryption())
        PRIVEE.write_text(_b64(brut) + '\n')
        os.chmod(PRIVEE, 0o600)
        print(f'Clé privée créée : {PRIVEE}  (GARDEZ-LA SECRÈTE, sauvegardez-la, ne la mettez jamais dans git)')
    pub = cle.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    _ecrire_publique(_b64(pub))
    print(f'Clé publique écrite dans {FICHIER_PUBLIC.relative_to(RACINE)} : committez ce fichier.')


def emettre(args):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    if not PRIVEE.exists():
        sys.exit(f'Clé privée introuvable ({PRIVEE}) : lancez d\'abord « initialiser » sur cet ordinateur.')
    try:
        fin = date.fromisoformat(args.fin)
    except ValueError:
        sys.exit('--fin doit être une date AAAA-MM-JJ, ex. 2027-12-31')
    contenu = {'client': args.client.strip(), 'fin': fin.isoformat(), 'emis': date.today().isoformat()}
    if args.utilisateurs:
        contenu['utilisateurs'] = args.utilisateurs
    corps = _b64(json.dumps(contenu, ensure_ascii=False, separators=(',', ':')).encode())
    cle = Ed25519PrivateKey.from_private_bytes(_b64d(PRIVEE.read_text().strip()))
    print(f'EGX1-{corps}.{_b64(cle.sign(corps.encode()))}')
    print(f'\n(client : {contenu["client"]} — fin : {fin:%d/%m/%Y}'
          + (f' — {args.utilisateurs} utilisateurs' if args.utilisateurs else '') + ')', file=sys.stderr)


def lire(args):
    """Vérifie une clé avec la clé publique de egalyx/licence_cle.py (sans dépendre de l'application)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    texte = FICHIER_PUBLIC.read_text() if FICHIER_PUBLIC.exists() else ''
    m = re.search(r"CLE_PUBLIQUE = '([^']+)'", texte)
    if not m:
        sys.exit('Clé publique absente : lancez « initialiser ».')
    cle = ''.join(args.cle.split())
    try:
        assert cle.startswith('EGX1-') and cle.count('.') == 1
        corps, sig = cle[5:].split('.')
        Ed25519PublicKey.from_public_bytes(_b64d(m.group(1))).verify(_b64d(sig), corps.encode())
        lic = json.loads(_b64d(corps))
    except Exception:  # noqa: BLE001
        sys.exit('Clé refusée : modifiée, incomplète ou non émise avec votre clé privée.')
    fin = date.fromisoformat(lic['fin'])
    print(f"Valide — client : {lic['client']} — fin : {fin:%d/%m/%Y} — émise le {lic.get('emis')}"
          + (f" — {lic['utilisateurs']} utilisateurs" if lic.get('utilisateurs') else ''))


def main():
    ap = argparse.ArgumentParser(description='Licences on-premise Egalyx Control')
    sp = ap.add_subparsers(dest='cmd', required=True)
    a = sp.add_parser('initialiser', help='crée la paire de clés (une seule fois)')
    a.add_argument('--forcer', action='store_true')
    a.set_defaults(f=initialiser)
    a = sp.add_parser('emettre', help='émet une clé pour un client')
    a.add_argument('--client', required=True)
    a.add_argument('--fin', required=True, help='date de fin AAAA-MM-JJ')
    a.add_argument('--utilisateurs', type=int, default=0)
    a.set_defaults(f=emettre)
    a = sp.add_parser('lire', help='vérifie et affiche une clé')
    a.add_argument('cle')
    a.set_defaults(f=lire)
    args = ap.parse_args()
    args.f(args)


if __name__ == '__main__':
    main()
