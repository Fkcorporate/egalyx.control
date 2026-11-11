"""
egalyx/import_cartographie.py — importer une cartographie Excel « telle quelle ».

Le client dépose son fichier (xlsx ou csv) tel qu'il l'utilise aujourd'hui :
  1. la ligne d'en-tête est trouvée automatiquement, chaque colonne est rapprochée d'un champ Egalyx par son titre
     (« Risque », « Libellé du risque », « Gravité », « Probabilité », « Contrôles existants », « Propriétaire »…) ;
  2. un aperçu montre ce qui sera créé, avec les anomalies (intitulé manquant, cotation illisible, doublon) ;
     chaque correspondance de colonne peut être corrigée ;
  3. l'import crée les risques (cotation de départ : impact et probabilité ramenés sur 1 à 5, quelle que soit
     l'échelle du fichier : 1-4, 1-5, 1-10 ou des mots) et, pour chaque contrôle listé, un dispositif de maîtrise
     non évalué, rattaché au responsable s'il est reconnu parmi les utilisateurs.
Rien n'est créé avant la confirmation ; le fichier analysé est conservé 24 h dans instance/imports_cartographie.
"""
import csv
import io
import json
import math
import os
import re
import time
import unicodedata
import uuid
from datetime import datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user

from egalyx.commun import client_id_courant, journaliser, permission_requise

bp = Blueprint('import_carto', __name__, url_prefix='/cartographie-import')

TAILLE_MAX = 10 * 1024 * 1024
LIGNES_MAX = 5000
DUREE_S = 24 * 3600


def norm(texte):
    t = unicodedata.normalize('NFKD', str(texte or '')).encode('ascii', 'ignore').decode().lower()
    t = re.sub(r'[^a-z0-9]+', ' ', t)
    return ' '.join(t.split())


# Champs Egalyx et titres de colonnes reconnus (comparés sans accents ni ponctuation)
CHAMPS = [
    ('reference', 'Référence', ['reference', 'ref', 'code', 'code risque', 'numero', 'n', 'no', 'id', 'identifiant']),
    ('intitule', 'Intitulé du risque *', ['risque', 'intitule', 'intitule du risque', 'libelle', 'libelle du risque',
                                          'nom du risque', 'evenement', 'evenement redoute', 'titre', 'risques',
                                          'description du risque', 'risque identifie']),
    ('description', 'Description', ['description', 'detail', 'details', 'commentaire', 'commentaires', 'observations']),
    ('categorie', 'Catégorie', ['categorie', 'famille', 'type', 'type de risque', 'nature', 'nature du risque',
                                'categorie de risque', 'famille de risque', 'domaine']),
    ('cause', 'Causes', ['cause', 'causes', 'cause racine', 'causes racines', 'facteurs', 'facteur de risque', 'origine']),
    ('consequences', 'Conséquences', ['consequence', 'consequences', 'effets', 'effet', 'impacts potentiels',
                                      'impact potentiel', 'consequences potentielles']),
    ('processus', 'Processus', ['processus', 'activite', 'macro processus', 'processus concerne', 'sous processus']),
    ('impact', 'Impact (gravité)', ['impact', 'gravite', 'severite', 'cotation impact', 'niveau d impact', 'i',
                                    'impact brut', 'gravite brute']),
    ('probabilite', 'Probabilité', ['probabilite', 'frequence', 'occurrence', 'vraisemblance', 'p', 'probabilite brute',
                                    'probabilite d occurrence']),
    ('maitrise', 'Niveau de maîtrise', ['maitrise', 'niveau de maitrise', 'efficacite des controles', 'dmr',
                                        'evaluation des controles', 'qualite du controle', 'niveau de controle']),
    ('controles', 'Contrôles / dispositifs', ['controles', 'controle', 'controles existants', 'dispositif',
                                              'dispositifs', 'dispositifs de maitrise', 'dispositif de maitrise',
                                              'mesures', 'mesures de maitrise', 'mesures existantes', 'actions de maitrise']),
    ('responsable', 'Responsable', ['responsable', 'proprietaire', 'proprietaire du risque', 'owner', 'pilote',
                                    'porteur', 'responsable du risque', 'risk owner']),
    ('direction', 'Direction / service', ['direction', 'departement', 'service', 'entite', 'structure', 'unite']),
]
LIBELLES = {c: l for c, l, _s in CHAMPS}

MOTS_IMPACT = [('tres faible', 1), ('negligeable', 1), ('insignifiant', 1), ('faible', 2), ('mineur', 2),
               ('limite', 2), ('moyen', 3), ('modere', 3), ('significatif', 3), ('tres eleve', 5), ('tres fort', 5),
               ('critique', 5), ('catastrophique', 5), ('extreme', 5), ('tres grave', 5), ('eleve', 4), ('fort', 4),
               ('majeur', 4), ('important', 4), ('grave', 4)]
MOTS_PROBA = [('tres rare', 1), ('tres peu probable', 1), ('improbable', 1), ('exceptionnel', 1), ('rare', 2),
              ('peu probable', 2), ('faible', 2), ('possible', 3), ('occasionnel', 3), ('moyen', 3), ('modere', 3),
              ('tres probable', 5), ('quasi certain', 5), ('certain', 5), ('tres frequent', 5), ('tres eleve', 5),
              ('probable', 4), ('frequent', 4), ('eleve', 4), ('fort', 4)]
MOTS_MAITRISE = [('inexistant', 1), ('aucun', 1), ('tres faible', 1), ('insuffisant', 2), ('faible', 2),
                 ('partiel', 3), ('moyen', 3), ('acceptable', 3), ('tres bon', 5), ('excellent', 5), ('optimal', 5),
                 ('satisfaisant', 4), ('bon', 4), ('fort', 4), ('efficace', 4)]


def _mots(liste):
    return sorted(liste, key=lambda x: -len(x[0]))


MOTS = {'impact': _mots(MOTS_IMPACT), 'probabilite': _mots(MOTS_PROBA), 'maitrise': _mots(MOTS_MAITRISE)}


# ---------------------------------------------------------------- lecture du fichier
def lire_fichier(nom, contenu):
    """Renvoie {'feuilles': {nom: [[cellules texte]]}}. Formats : xlsx / xlsm / csv / txt."""
    ext = os.path.splitext(nom.lower())[1]
    if ext in ('.xlsx', '.xlsm'):
        import openpyxl
        classeur = openpyxl.load_workbook(io.BytesIO(contenu), read_only=True, data_only=True)
        feuilles = {}
        for ws in classeur.worksheets:
            lignes = []
            for ligne in ws.iter_rows(values_only=True):
                lignes.append(['' if v is None else (str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)).strip()
                               for v in ligne])
                if len(lignes) > LIGNES_MAX + 30:
                    break
            feuilles[ws.title] = _nettoyer(lignes)
        return feuilles
    if ext in ('.csv', '.txt'):
        for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
            try:
                texte = contenu.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        try:
            dialecte = csv.Sniffer().sniff(texte[:5000], delimiters=';,\t|')
        except csv.Error:
            dialecte = csv.excel
            dialecte.delimiter = ';' if texte.count(';') > texte.count(',') else ','
        lignes = [[c.strip() for c in l] for l in csv.reader(io.StringIO(texte), dialecte)]
        return {'Feuille 1': _nettoyer(lignes[:LIGNES_MAX + 30])}
    if ext == '.xls':
        raise ValueError("Ancien format Excel (.xls) : enregistrez le fichier au format .xlsx (Fichier → Enregistrer sous) "
                         "puis déposez-le à nouveau.")
    raise ValueError('Format non pris en charge : déposez un fichier Excel (.xlsx) ou CSV.')


def _nettoyer(lignes):
    """Garde les lignes vides intérieures : les numéros de ligne restent ceux d'Excel."""
    while lignes and not any(c for c in lignes[-1]):
        lignes.pop()
    if not lignes:
        return []
    largeur = max(len(l) for l in lignes)
    # retire les colonnes entièrement vides à droite
    while largeur > 0 and not any(len(l) >= largeur and l[largeur - 1] for l in lignes):
        largeur -= 1
    return [(l + [''] * largeur)[:largeur] for l in lignes]


def detecter_entete(lignes):
    meilleure, score_max = 0, 0
    for i, l in enumerate(lignes[:25]):
        score = sum(1 for c in l if c and _meilleur_champ(c)[1] >= 2)
        if score > score_max:
            meilleure, score_max = i, score
    return meilleure


def _meilleur_champ(titre):
    """(champ, score) : 3 = titre identique à un synonyme, 2 = synonyme contenu dans le titre ; à score égal, le
    synonyme le plus long l'emporte (« Mesures de maîtrise existantes » → contrôles, pas niveau de maîtrise)."""
    t = norm(titre)
    if not t:
        return None, 0
    meilleur, cle = None, (0, 0)
    for code, _l, synonymes in CHAMPS:
        for s in synonymes:
            if t == s:
                sc = 3
            elif len(s) > 2 and (' ' + s + ' ') in (' ' + t + ' '):
                sc = 2
            else:
                continue
            if (sc, len(s)) > cle:
                meilleur, cle = code, (sc, len(s))
    return meilleur, cle[0]


def correspondance_auto(entetes):
    """{champ: index de colonne} — chaque colonne ne sert qu'une fois, la meilleure correspondance gagne."""
    candidats = []
    for i, titre in enumerate(entetes):
        code, score = _meilleur_champ(titre)
        if code:
            candidats.append((score, -i, code, i))
    resultat, colonnes_prises = {}, set()
    for score, _ni, code, i in sorted(candidats, reverse=True):
        if code not in resultat and i not in colonnes_prises:
            resultat[code] = i
            colonnes_prises.add(i)
    return resultat


# ---------------------------------------------------------------- valeurs
def _nombre(v):
    try:
        return float(str(v).replace(',', '.').strip())
    except (TypeError, ValueError):
        return None


def echelle(valeurs, titre=''):
    """Échelle de la colonne : annoncée dans le titre (« Impact (1-4) », « Gravité /10 »), sinon 5 — ou 10 si une
    valeur dépasse 5. Une colonne sur 1 à 5 dont personne n'atteint 5 n'est donc pas prise pour une échelle sur 4."""
    m = re.search(r'(?:\b1\s*(?:-|à|a|–)\s*|/\s*|sur\s+)(\d{1,3})\b', str(titre or '').lower())
    if m and int(m.group(1)) in (3, 4, 5, 6, 10, 20, 100):
        return float(m.group(1))
    nombres = [n for n in (_nombre(v) for v in valeurs) if n is not None]
    if not nombres:
        return None
    haut = max(nombres)
    return 5.0 if haut <= 5 else (10.0 if haut <= 10 else haut)


def niveau(valeur, champ, maxi):
    """Ramène une cotation sur 1 à 5. Renvoie (niveau ou None, message d'anomalie ou None)."""
    v = (valeur or '').strip()
    if not v:
        return None, None
    n = _nombre(v)
    if n is not None:
        if maxi is not None and maxi <= 3:
            n = {1: 1, 2: 3, 3: 5}.get(int(round(n)), n)
        elif maxi is not None and maxi <= 4:
            n = {1: 1, 2: 2, 3: 4, 4: 5}.get(int(round(n)), n)
        elif maxi is not None and maxi > 5:
            if n > maxi:
                return None, f"« {v} » hors échelle (sur {int(maxi)})"
            n = max(1, math.ceil(n * 5 / maxi))
        n = int(round(n))
        if 1 <= n <= 5:
            return n, None
        return None, f"« {v} » hors échelle"
    t = norm(v)
    for mot, niv in MOTS[champ]:
        if (' ' + mot + ' ') in (' ' + t + ' '):
            return niv, None
    return None, f"« {v} » non reconnu"


def decouper_controles(texte):
    if not texte:
        return []
    morceaux = re.split(r'\n|;|•|·|\s\|\s|(?:^|\s)-\s(?=[A-ZÀ-Ý])', texte)
    vus, res = set(), []
    for m in morceaux:
        m = re.sub(r'^\s*(?:[-*–]|\d+[.)])\s*', '', m or '').strip(' .')
        if len(m) >= 3 and m.lower() not in vus:
            vus.add(m.lower())
            res.append(m[:200])
    return res


# ---------------------------------------------------------------- analyse
def analyser(table, entete, mapping, cid):
    """Lignes prêtes à importer + anomalies, sans rien enregistrer."""
    from models import Risque, User
    corps = table[entete + 1:]
    col = lambda code: mapping.get(code)  # noqa: E731
    entetes = table[entete] if table else []
    maxi = {c: (echelle([l[col(c)] for l in corps], entetes[col(c)] if col(c) < len(entetes) else '')
                if col(c) is not None else None) for c in ('impact', 'probabilite', 'maitrise')}
    existants = {norm(r.intitule) for r in Risque.query.filter_by(client_id=cid, is_archived=False).all()}
    users = User.query.filter_by(client_id=cid, is_active=True).all()
    index_users = {}
    for u in users:
        for cle in (u.username, u.email, f"{getattr(u, 'prenom', '') or ''} {getattr(u, 'nom', '') or ''}",
                    f"{getattr(u, 'nom', '') or ''} {getattr(u, 'prenom', '') or ''}"):
            if cle and norm(cle):
                index_users[norm(cle)] = u
    lignes, vus = [], set()
    for n, l in enumerate(corps, start=entete + 2):
        val = lambda code: (l[col(code)].strip() if col(code) is not None and col(code) < len(l) else '')  # noqa: E731
        item = {'ligne': n, 'anomalies': [], 'ignoree': False}
        item['intitule'] = val('intitule')
        if not item['intitule']:
            if any(c for c in l):
                item.update(ignoree=True)
                item['anomalies'].append('intitulé manquant : ligne ignorée')
                lignes.append(item)
            continue
        for code in ('reference', 'description', 'categorie', 'cause', 'consequences', 'processus', 'direction',
                     'responsable'):
            item[code] = val(code)
        for code in ('impact', 'probabilite', 'maitrise'):
            item[code], err = niveau(val(code), code, maxi[code])
            if err:
                item['anomalies'].append(f"{LIBELLES[code].replace(' *', '')} {err}")
        item['controles'] = decouper_controles(val('controles'))
        u = index_users.get(norm(item['responsable'])) if item['responsable'] else None
        item['responsable_id'] = u.id if u else None
        if item['responsable'] and not u:
            item['anomalies'].append(f"responsable « {item['responsable']} » inconnu parmi les utilisateurs (noté sur le risque)")
        cle = norm(item['intitule'])
        if cle in existants:
            item['doublon'] = 'déjà dans Egalyx'
        elif cle in vus:
            item['doublon'] = 'en double dans le fichier'
        vus.add(cle)
        lignes.append(item)
    return lignes, maxi


def importer(lignes, cid, cartographie, auteur_id, creer_dispositifs=True, ignorer_doublons=True):
    from models import db, Risque, DispositifMaitrise
    from egalyx.bibliotheque import prochaine_reference
    from egalyx.bibliotheque_donnees import IMPACT_TXT, PROBA_TXT
    refs_prises = {r[0] for r in Risque.query.with_entities(Risque.reference).filter(Risque.client_id == cid).all()}
    nb_r = nb_d = nb_ign = 0
    for it in lignes:
        if it.get('ignoree') or (ignorer_doublons and it.get('doublon')):
            nb_ign += 1
            continue
        ref = (it.get('reference') or '').strip()[:50]
        if not ref or ref in refs_prises:
            ref = prochaine_reference(cid, 'IMP', refs_prises)
        refs_prises.add(ref)
        notes = []
        if it.get('maitrise'):
            notes.append(f"Niveau de maîtrise indiqué dans le fichier : {it['maitrise']}/5.")
        if it.get('direction'):
            notes.append(f"Direction / service : {it['direction']}.")
        if it.get('responsable') and not it.get('responsable_id'):
            notes.append(f"Responsable indiqué : {it['responsable']}.")
        a_completer = not (it.get('impact') and it.get('probabilite'))
        if a_completer:
            notes.append("Cotation non fournie ou illisible dans le fichier : valeur moyenne provisoire, à revoir lors de "
                         "l'évaluation.")
        description = '\n'.join(x for x in [it.get('description') or '', ' '.join(notes)] if x)
        r = Risque(reference=ref, intitule=it['intitule'][:300], description=description or None,
                   categorie=(it.get('categorie') or None) and it['categorie'][:100], cause_racine=it.get('cause') or None,
                   consequences=it.get('consequences') or None,
                   processus_concerne=(it.get('processus') or None) and it['processus'][:200],
                   impact=IMPACT_TXT.get(it.get('impact') or 3), probabilite=PROBA_TXT.get(it.get('probabilite') or 3),
                   cartographie_id=cartographie.id, client_id=cid, created_by=auteur_id, statut='actif')
        try:
            r.metadonnees = {'source': 'import_excel', 'ligne': it['ligne'], 'importe_le': datetime.utcnow().isoformat(),
                             'maitrise_fichier': it.get('maitrise'), 'direction_fichier': it.get('direction') or None,
                             'responsable_fichier': it.get('responsable') or None, 'cotation_a_completer': a_completer}
        except Exception:  # noqa: BLE001
            pass
        try:
            r.calculer_score_risque()
            r.calculer_niveau_criticite()
        except Exception:  # noqa: BLE001
            pass
        db.session.add(r)
        db.session.flush()
        nb_r += 1
        if creer_dispositifs:
            for k, nom in enumerate(it.get('controles') or [], 1):
                db.session.add(DispositifMaitrise(
                    reference=f'DM-{ref}-{k:03d}', nom=nom, statut='actif', risque_id=r.id, client_id=cid,
                    created_by=auteur_id, responsable_id=it.get('responsable_id'),
                    description="Repris de la cartographie Excel : précisez le type, la fréquence et évaluez son efficacité."))
                nb_d += 1
    return nb_r, nb_d, nb_ign


# ---------------------------------------------------------------- stockage temporaire
def _dossier():
    d = os.path.join(current_app.instance_path, 'imports_cartographie')
    os.makedirs(d, exist_ok=True)
    maintenant = time.time()
    for f in os.listdir(d):
        p = os.path.join(d, f)
        try:
            if maintenant - os.path.getmtime(p) > DUREE_S:
                os.remove(p)
        except OSError:
            pass
    return d


def _charger(jeton):
    if not jeton or not re.fullmatch(r'[0-9a-f]{32}', jeton):
        return None
    p = os.path.join(_dossier(), jeton + '.json')
    if not os.path.exists(p):
        return None
    with open(p, encoding='utf-8') as f:
        d = json.load(f)
    if d.get('client_id') != client_id_courant() or d.get('user_id') != current_user.id:
        return None
    return d


def _sauver(d, jeton=None):
    jeton = jeton or uuid.uuid4().hex
    with open(os.path.join(_dossier(), jeton + '.json'), 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False)
    return jeton


# ---------------------------------------------------------------- pages
@bp.route('/', methods=['GET', 'POST'])
@permission_requise('can_manage_risks')
def page():
    from models import Cartographie
    cid = client_id_courant()
    if request.method == 'POST':
        f = request.files.get('fichier')
        if not f or not f.filename:
            flash('Choisissez un fichier Excel (.xlsx) ou CSV.', 'warning')
            return redirect(url_for('.page'))
        contenu = f.read(TAILLE_MAX + 1)
        if len(contenu) > TAILLE_MAX:
            flash('Fichier trop volumineux (10 Mo au maximum).', 'warning')
            return redirect(url_for('.page'))
        try:
            feuilles = lire_fichier(f.filename, contenu)
        except ValueError as e:
            flash(str(e), 'warning')
            return redirect(url_for('.page'))
        except Exception as e:  # noqa: BLE001
            current_app.logger.warning('Import cartographie : lecture impossible (%s)', e)
            flash("Le fichier n'a pas pu être lu. Vérifiez qu'il s'agit bien d'un classeur Excel (.xlsx) ou d'un CSV.", 'warning')
            return redirect(url_for('.page'))
        feuilles = {k: v for k, v in feuilles.items() if v}
        if not feuilles:
            flash('Le fichier est vide.', 'warning')
            return redirect(url_for('.page'))
        feuille = max(feuilles, key=lambda k: sum(1 for l in feuilles[k] if sum(1 for c in l if c) >= 2))
        table = feuilles[feuille]
        entete = detecter_entete(table)
        d = {'client_id': cid, 'user_id': current_user.id, 'nom_fichier': f.filename[:200], 'feuilles': feuilles,
             'feuille': feuille, 'entete': entete, 'mapping': correspondance_auto(table[entete]),
             'cree_le': time.time()}
        jeton = _sauver(d)
        journaliser('import_cartographie_analyse', {'fichier': f.filename[:200], 'lignes': len(table)})
        return redirect(url_for('.apercu', jeton=jeton))
    cartos = Cartographie.query.filter_by(client_id=cid, is_archived=False).order_by(Cartographie.nom).all()
    return render_template('egalyx/import_cartographie.html', cartos=cartos, champs=CHAMPS)


@bp.route('/<jeton>', methods=['GET', 'POST'])
@permission_requise('can_manage_risks')
def apercu(jeton):
    from models import db, Cartographie
    d = _charger(jeton)
    if d is None:
        flash("Cet import a expiré ou n'existe pas : déposez à nouveau le fichier.", 'warning')
        return redirect(url_for('.page'))
    cid = client_id_courant()
    if request.method == 'POST':
        feuille = request.form.get('feuille') or d['feuille']
        if feuille in d['feuilles'] and feuille != d['feuille']:
            d['feuille'] = feuille
            d['entete'] = detecter_entete(d['feuilles'][feuille])
            d['mapping'] = correspondance_auto(d['feuilles'][feuille][d['entete']])
        else:
            table = d['feuilles'][d['feuille']]
            e = request.form.get('entete', type=int)
            if e is not None and 1 <= e <= len(table) and e - 1 != d['entete']:
                d['entete'] = e - 1
                d['mapping'] = correspondance_auto(table[d['entete']])
            else:
                mapping = {}
                for code, _l, _s in CHAMPS:
                    v = request.form.get('col_' + code, '')
                    if v.isdigit() and int(v) < len(table[0]):
                        mapping[code] = int(v)
                d['mapping'] = mapping
        _sauver(d, jeton)
        if request.form.get('action') == 'importer':
            if 'intitule' not in d['mapping']:
                flash("Indiquez quelle colonne contient l'intitulé du risque.", 'warning')
                return redirect(url_for('.apercu', jeton=jeton))
            choix = request.form.get('cartographie_id') or ''
            if choix == 'nouvelle':
                nom = (request.form.get('nouvelle_nom') or '').strip() or os.path.splitext(d['nom_fichier'])[0]
                carto = Cartographie(nom=nom[:200], client_id=cid, created_by=current_user.id,
                                     description=f"Importée depuis le fichier « {d['nom_fichier']} ».")
                db.session.add(carto)
                db.session.flush()
            else:
                carto = Cartographie.query.filter_by(id=int(choix) if choix.isdigit() else -1, client_id=cid).first()
                if carto is None:
                    flash('Choisissez la cartographie de destination.', 'warning')
                    return redirect(url_for('.apercu', jeton=jeton))
            lignes, _m = analyser(d['feuilles'][d['feuille']], d['entete'], d['mapping'], cid)
            debut = time.time()
            nb_r, nb_d, nb_ign = importer(lignes, cid, carto, current_user.id,
                                          creer_dispositifs=request.form.get('creer_dispositifs') == '1',
                                          ignorer_doublons='1' in request.form.getlist('ignorer_doublons'))
            journaliser('import_cartographie', {'fichier': d['nom_fichier'], 'cartographie': carto.id, 'risques': nb_r,
                                                'dispositifs': nb_d, 'ignores': nb_ign,
                                                'duree_s': round(time.time() - debut, 1)})
            db.session.commit()
            try:
                os.remove(os.path.join(_dossier(), jeton + '.json'))
            except OSError:
                pass
            flash(f"Import terminé : {nb_r} risque(s)" + (f", {nb_d} dispositif(s) de maîtrise" if nb_d else '')
                  + f" dans « {carto.nom} »." + (f" {nb_ign} ligne(s) ignorée(s) (vides ou en double)." if nb_ign else '')
                  + " Étape suivante : complétez les dispositifs (type, responsable) puis lancez l'évaluation.", 'success')
            return redirect(url_for('detail_cartographie', id=carto.id))
        return redirect(url_for('.apercu', jeton=jeton))
    table = d['feuilles'][d['feuille']]
    lignes, maxi = analyser(table, d['entete'], d['mapping'], cid)
    retenues = [l for l in lignes if not l.get('ignoree')]
    cartos = Cartographie.query.filter_by(client_id=cid, is_archived=False).order_by(Cartographie.nom).all()
    resume = {'risques': len([l for l in retenues if not l.get('doublon')]),
              'doublons': len([l for l in retenues if l.get('doublon')]),
              'ignorees': len([l for l in lignes if l.get('ignoree')]),
              'controles': sum(len(l.get('controles') or []) for l in retenues if not l.get('doublon')),
              'anomalies': sum(1 for l in lignes if l['anomalies'])}
    return render_template('egalyx/import_cartographie_apercu.html', d=d, jeton=jeton, table=table,
                           entetes=table[d['entete']] if table else [], champs=CHAMPS, lignes=lignes[:200],
                           total=len(lignes), resume=resume, maxi=maxi, cartos=cartos,
                           nom_defaut=os.path.splitext(d['nom_fichier'])[0])


@bp.route('/modele.xlsx')
@permission_requise('can_manage_risks')
def modele():
    """Modèle vierge pour les organisations qui n'ont pas encore de cartographie."""
    import openpyxl
    from flask import send_file
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Cartographie'
    ws.append(['Référence', 'Risque', 'Catégorie', 'Causes', 'Conséquences', 'Processus', 'Impact (1-5)',
               'Probabilité (1-5)', 'Contrôles existants', 'Responsable', 'Direction'])
    ws.append(['R-001', 'Fraude aux paiements fournisseurs', 'Fraude', 'Changement de RIB sans contre-appel',
               'Paiement irrécupérable', 'Achats', 4, 3, 'Contre-appel avant changement de RIB ; double validation des paiements',
               '', 'Finance'])
    for c, l in zip('ABCDEFGHIJK', (12, 40, 16, 35, 35, 18, 12, 14, 50, 18, 16)):
        ws.column_dimensions[c].width = l
    tampon = io.BytesIO()
    wb.save(tampon)
    tampon.seek(0)
    return send_file(tampon, as_attachment=True, download_name='modele_cartographie_egalyx.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


def enregistrer(app):
    app.register_blueprint(bp)
