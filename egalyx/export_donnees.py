"""
egalyx/export_donnees.py — export complet des données d'une organisation (réversibilité,
droit à la portabilité, fin de contrat).

Archive ZIP : un fichier JSON et un fichier CSV par table, plus un manifeste.
Contenu : toutes les tables portant client_id = organisation, puis, de proche en proche,
les tables qui leur sont rattachées par clé étrangère (évaluations, étapes, commentaires…).
Exclus : secrets et empreintes (mots de passe, clés d'API, jetons, 2FA, accès serveurs),
et les signalements d'alerte (confidentialité : export séparé par le référent si besoin).
"""
import csv
import io
import json
import re
import tempfile
import zipfile
from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, render_template, request, send_file

from egalyx.commun import admin_client_requis, client_id_courant, journaliser, permission_requise

bp = Blueprint('export_donnees', __name__, url_prefix='/parametres/export')

TABLES_EXCLUES = {'signalements', 'messages_signalement', 'user_sessions', 'user_session', 'api_keys',
                  'api_key_usage_logs', 'environnements_client', 'paiements_en_ligne_secrets'}
COLONNES_SENSIBLES = re.compile(
    r'(password|mot_de_passe|secret|token|jeton|api_key|apikey|totp|ssh_key|private_key|cle_privee|key_hash|otp)', re.I)
COLONNES_AUTORISEES = {'password_changed_at', 'password_expires_at'}


def _valeur(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        return None
    return v


def colonnes_exportables(table):
    return [c for c in table.columns if c.name in COLONNES_AUTORISEES or not COLONNES_SENSIBLES.search(c.name)]


def plan_export(metadata):
    """Ordre : tables avec client_id, puis tables filles rattachées par clé étrangère."""
    tables = [t for t in metadata.sorted_tables if t.name not in TABLES_EXCLUES]
    directes = [t for t in tables if 'client_id' in t.c]
    retenues = {t.name for t in directes}
    filles = []
    for _ in range(3):
        ajout = False
        for t in tables:
            if t.name in retenues:
                continue
            liens = [(fk.parent.name, fk.column.table.name, fk.column.name) for fk in t.foreign_keys
                     if fk.column.table.name in retenues and fk.column.table.name not in ('user', 'clients')]
            if liens:
                filles.append((t, liens))
                retenues.add(t.name)
                ajout = True
        if not ajout:
            break
    return directes, filles


def construire_archive(db, cid):
    from sqlalchemy import select, or_
    directes, filles = plan_export(db.metadata)
    ids = {}
    tmp = tempfile.SpooledTemporaryFile(max_size=50 * 1024 * 1024)
    manifeste = {'organisation_id': cid, 'genere_le': datetime.utcnow().isoformat() + 'Z',
                 'format': 'Un fichier JSON (liste d\'objets) et un CSV (séparateur ;) par table, UTF-8.',
                 'tables': {}}
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        def ecrire(table, lignes, cols):
            noms = [c.name for c in cols]
            donnees = [{n: _valeur(l[n]) for n in noms} for l in lignes]
            z.writestr(f'json/{table.name}.json', json.dumps(donnees, ensure_ascii=False, indent=1, default=str))
            s = io.StringIO()
            w = csv.writer(s, delimiter=';')
            w.writerow(noms)
            for d in donnees:
                w.writerow([json.dumps(d[n], ensure_ascii=False) if isinstance(d[n], (dict, list)) else
                            ('' if d[n] is None else d[n]) for n in noms])
            z.writestr(f'csv/{table.name}.csv', '﻿' + s.getvalue())
            manifeste['tables'][table.name] = len(donnees)
            if 'id' in table.c:
                ids[table.name] = {d['id'] for d in donnees if 'id' in d}

        for t in directes:
            cols = colonnes_exportables(t)
            lignes = db.session.execute(select(*cols).where(t.c.client_id == cid)).mappings().all()
            ecrire(t, lignes, cols)
        # La fiche de l'organisation elle-même
        if 'clients' in db.metadata.tables:
            t = db.metadata.tables['clients']
            cols = colonnes_exportables(t)
            ecrire(t, db.session.execute(select(*cols).where(t.c.id == cid)).mappings().all(), cols)
        for t, liens in filles:
            conditions = [t.c[col].in_(list(ids.get(parent, set())) or [-1]) for col, parent, _ in liens]
            cols = colonnes_exportables(t)
            lignes = db.session.execute(select(*cols).where(or_(*conditions))).mappings().all()
            ecrire(t, lignes, cols)
        manifeste['exclus'] = {'tables': sorted(TABLES_EXCLUES),
                               'colonnes': 'mots de passe, secrets, jetons, clés d\'API, double authentification'}
        z.writestr('manifeste.json', json.dumps(manifeste, ensure_ascii=False, indent=2))
        z.writestr('LISEZMOI.txt',
                   "Export des données Egalyx Control\n\n"
                   "json/ : une table par fichier (liste d'objets JSON).\n"
                   "csv/  : mêmes données, séparateur « ; », encodage UTF-8 avec BOM (ouvrable dans Excel).\n"
                   "manifeste.json : nombre de lignes par table et éléments exclus.\n"
                   "Les relations entre tables se font par les colonnes *_id.\n")
    tmp.seek(0)
    return tmp, manifeste


@bp.route('/', methods=['GET', 'POST'])
@admin_client_requis
@permission_requise('can_export_data')
def page():
    from models import db, Client
    cid = client_id_courant()
    if request.method == 'POST':
        archive, manifeste = construire_archive(db, cid)
        org = db.session.get(Client, cid)
        journaliser('export_complet_donnees', {'tables': len(manifeste['tables']),
                                               'lignes': sum(manifeste['tables'].values())})
        db.session.commit()
        nom = f"egalyx-export-{(org.reference if org else cid)}-{datetime.utcnow():%Y%m%d-%H%M}.zip"
        return send_file(archive, mimetype='application/zip', as_attachment=True, download_name=nom)
    directes, filles = plan_export(db.metadata)
    return render_template('egalyx/export_donnees.html', nb_tables=len(directes) + len(filles) + 1)


def enregistrer(app):
    app.register_blueprint(bp)
