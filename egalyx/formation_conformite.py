"""
egalyx/formation_conformite.py — Formation à la conformité (e-learning), lot 1.

  - Modules : un contenu à lire (texte mis en forme simplement) et, si besoin, une vidéo (YouTube, Vimeo) ou un lien,
    puis un quiz noté (une ou plusieurs bonnes réponses par question) avec un score minimum pour valider ;
  - Campagnes : un module, des personnes concernées (tout le monde, des directions, des rôles ou une liste de
    personnes), une date limite ; chaque personne reçoit une notification ; relance des retardataires en un clic ;
  - Mes formations : chaque personne voit ce qu'elle doit suivre, le suit, passe le quiz (tentatives illimitées,
    les bonnes réponses ne sont montrées qu'une fois le module validé) ;
  - Suivi : taux de réalisation, retards, scores, export Excel (preuve pour le régulateur ou l'auditeur).

Garde-fous : module « sur activation » (le super admin le coche pour le client, page « Modules » du client) ;
gestion réservée à l'administrateur de l'organisation et à la permission « Gérer les formations à la conformité » ;
suivi en lecture avec « Voir le suivi des formations » ; chacun ne suit que ses propres formations ; tout est cloisonné
par organisation et journalisé. Le super admin peut tout faire, pour l'organisation qu'il consulte.
"""
import io
import json
import re
from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from markupsafe import Markup, escape

from egalyx.commun import client_id_courant, est_super_admin, journaliser, nom_personne

bp = Blueprint('formation_conformite', __name__, url_prefix='/formation-conformite')

CODE_MODULE = 'formation_conformite'
PERM_GERER = 'can_manage_formation_conformite'
PERM_VOIR = 'can_view_formation_conformite'
MAX_QUESTIONS, MAX_CHOIX = 50, 8
CATEGORIES = [('lcb_ft', 'Lutte contre le blanchiment (LCB-FT)'), ('anticorruption', 'Anticorruption'),
              ('donnees', 'Protection des données (RGPD)'), ('cyber', 'Cybersécurité'), ('ethique', 'Éthique et alerte'),
              ('controle_interne', 'Contrôle interne'), ('autre', 'Autre')]
CATEGORIE = dict(CATEGORIES)
STATUTS = {'a_faire': 'À faire', 'en_cours': 'Commencé', 'reussi': 'Validé', 'en_retard': 'En retard'}


def _m():
    import models
    return models


# ====================================================================== droits
def module_actif(cid):
    from egalyx.modules_client import module_sur_activation_actif
    m = _m()
    client = m.db.session.get(m.Client, cid) if cid else None
    return module_sur_activation_actif(client, CODE_MODULE)


def _admin_org(u):
    return getattr(u, 'role', None) == 'admin' or bool(getattr(u, 'is_client_admin', False))


def peut_gerer(u=None, cid=None):
    u = u or current_user
    if not getattr(u, 'is_authenticated', False):
        return False
    if est_super_admin(u):
        return True
    return module_actif(cid or getattr(u, 'client_id', None)) and (_admin_org(u) or u.has_permission(PERM_GERER))


def peut_voir_suivi(u=None, cid=None):
    u = u or current_user
    return peut_gerer(u, cid) or (getattr(u, 'is_authenticated', False)
                                  and module_actif(cid or getattr(u, 'client_id', None)) and u.has_permission(PERM_VOIR))


def peut_suivre(u=None):
    u = u or current_user
    return bool(getattr(u, 'is_authenticated', False) and getattr(u, 'client_id', None) and module_actif(u.client_id))


def _cid():
    cid = client_id_courant()
    if not cid:
        abort(404)
    return cid


def _exiger_gestion():
    cid = _cid()
    if not peut_gerer(cid=cid):
        abort(403)
    return cid


def _exiger_suivi():
    cid = _cid()
    if not peut_voir_suivi(cid=cid):
        abort(403)
    return cid


def _module(cid, mid):
    m = _m()
    mod = m.db.session.get(m.ModuleFormationConformite, mid)
    if mod is None or mod.client_id != cid:
        abort(404)
    return mod


def _campagne(cid, kid):
    m = _m()
    c = m.db.session.get(m.CampagneFormationConformite, kid)
    if c is None or c.client_id != cid:
        abort(404)
    return c


# ====================================================================== contenu
_GRAS = re.compile(r'\*\*(.+?)\*\*')


def _ligne(t):
    return Markup(_GRAS.sub(lambda x: f'<strong>{x.group(1)}</strong>', str(escape(t))))


ENCADRES = {'à retenir': ('retenir', 'À retenir'), 'a retenir': ('retenir', 'À retenir'), 'attention': ('attention', 'Attention'),
            'exemple': ('exemple', 'Exemple'), 'bon à savoir': ('savoir', 'Bon à savoir'), 'bon a savoir': ('savoir', 'Bon à savoir'),
            'astuce': ('savoir', 'Astuce'), 'à éviter': ('attention', 'À éviter'), 'a eviter': ('attention', 'À éviter')}
_IMAGE = re.compile(r'^!\[([^\]]{0,200})\]\((https://[^\s()<>"\']{1,500})\)$')


def _encadre(lignes):
    texte = ' '.join(lignes).strip()
    genre, titre = 'savoir', None
    m = re.match(r'^([^:]{2,20})\s*:\s*(.*)$', texte)
    if m and m.group(1).strip().lower() in ENCADRES:
        genre, titre = ENCADRES[m.group(1).strip().lower()]
        texte = m.group(2)
    tete = f'<p class="fe-titre">{escape(titre)}</p>' if titre else ''
    return f'<aside class="fe fe-{genre}">{tete}<p>{_ligne(texte)}</p></aside>'


def rendre_contenu(texte):
    """Texte simple → HTML sûr : « ## » titre, « - » liste, « 1. » liste numérotée, **gras**, lignes vides = paragraphes,
    « > À retenir : … » (ou Attention, Exemple, Bon à savoir, Astuce, À éviter) = encadré,
    « ![légende](https://…) » seul sur sa ligne = image (adresses https uniquement)."""
    if not texte:
        return Markup('')
    html, liste, para, citation = [], None, [], []

    def fermer_para():
        if para:
            html.append('<p>' + '<br>'.join(str(_ligne(x)) for x in para) + '</p>')
            para.clear()

    def fermer_liste():
        nonlocal liste
        if liste:
            html.append(f'</{liste}>')
            liste = None

    def fermer_citation():
        if citation:
            html.append(_encadre(citation))
            citation.clear()

    for brut in texte.replace('\r\n', '\n').split('\n'):
        ligne = brut.strip()
        if ligne.startswith('>'):
            fermer_para(); fermer_liste()
            citation.append(ligne.lstrip('>').strip())
            continue
        fermer_citation()
        if not ligne:
            fermer_para(); fermer_liste()
            continue
        img = _IMAGE.match(ligne)
        if img:
            fermer_para(); fermer_liste()
            legende = escape(img.group(1).strip())
            html.append(f'<figure class="fe-image"><img src="{escape(img.group(2))}" alt="{legende}" loading="lazy" referrerpolicy="no-referrer">'
                        + (f'<figcaption>{legende}</figcaption>' if legende else '') + '</figure>')
            continue
        if ligne.startswith('## ') or ligne.startswith('# '):
            fermer_para(); fermer_liste()
            html.append(f'<h3>{_ligne(ligne.lstrip("#").strip())}</h3>')
            continue
        m_ul = re.match(r'^[-•*]\s+(.*)$', ligne)
        m_ol = re.match(r'^\d+[.)]\s+(.*)$', ligne)
        if m_ul or m_ol:
            fermer_para()
            genre = 'ul' if m_ul else 'ol'
            if liste != genre:
                fermer_liste()
                html.append(f'<{genre}>')
                liste = genre
            html.append(f'<li>{_ligne((m_ul or m_ol).group(1))}</li>')
            continue
        fermer_liste()
        para.append(ligne)
    fermer_citation(); fermer_para(); fermer_liste()
    return Markup('\n'.join(html))


def chapitres(texte):
    """Découpe le contenu en chapitres sur les intertitres « ## » : [{'titre', 'html'}]. Le texte avant le premier
    intertitre devient « Introduction »."""
    blocs, titre, courant = [], None, []
    for brut in (texte or '').replace('\r\n', '\n').split('\n'):
        s_ = brut.strip()
        if s_.startswith('## ') or (s_.startswith('# ') and not s_.startswith('##')):
            if titre is not None or any(x.strip() for x in courant):
                blocs.append((titre or 'Introduction', '\n'.join(courant)))
            titre, courant = s_.lstrip('#').strip(), []
        else:
            courant.append(brut)
    if titre is not None or any(x.strip() for x in courant):
        blocs.append((titre or 'Introduction', '\n'.join(courant)))
    return [{'titre': t, 'html': rendre_contenu(c)} for t, c in blocs if t or c.strip()]


def video_integree(url):
    """Adresse d'intégration pour YouTube ou Vimeo ; None pour les autres liens (affichés comme lien)."""
    if not url:
        return None
    m = re.match(r'^https://(?:www\.)?(?:youtube\.com/watch\?(?:.*&)?v=|youtu\.be/|youtube\.com/embed/)([A-Za-z0-9_-]{6,20})', url)
    if m:
        return f'https://www.youtube-nocookie.com/embed/{m.group(1)}'
    m = re.match(r'^https://(?:www\.)?(?:player\.)?vimeo\.com/(?:video/)?(\d{5,12})', url)
    if m:
        return f'https://player.vimeo.com/video/{m.group(1)}'
    return None


def lire_questions(brut):
    """JSON envoyé par l'éditeur → liste propre ; lève ValueError avec un message clair."""
    try:
        donnees = json.loads(brut or '[]')
    except ValueError:
        raise ValueError('Les questions n’ont pas pu être lues : rechargez la page et recommencez.')
    if not isinstance(donnees, list):
        raise ValueError('Format des questions incorrect.')
    if len(donnees) > MAX_QUESTIONS:
        raise ValueError(f'{MAX_QUESTIONS} questions au maximum.')
    propres = []
    for i, q in enumerate(donnees, 1):
        texte = str((q or {}).get('texte') or '').strip()[:500]
        choix = [str(c).strip()[:300] for c in ((q or {}).get('choix') or []) if str(c).strip()][:MAX_CHOIX]
        bonnes = sorted({int(b) for b in ((q or {}).get('bonnes') or []) if str(b).lstrip('-').isdigit()})
        if not texte and not choix:
            continue
        if not texte:
            raise ValueError(f'Question {i} : écrivez la question.')
        if len(choix) < 2:
            raise ValueError(f'Question {i} : il faut au moins deux réponses possibles.')
        bonnes = [b for b in bonnes if 0 <= b < len(choix)]
        if not bonnes:
            raise ValueError(f'Question {i} : cochez au moins une bonne réponse.')
        propres.append({'texte': texte, 'choix': choix, 'bonnes': bonnes,
                        'explication': str((q or {}).get('explication') or '').strip()[:800]})
    return propres


def noter(questions, reponses):
    """reponses : {indice question: set(indices choisis)} → (score en %, [bonne réponse ? par question]).
    Une question est juste si la personne a coché exactement les bonnes réponses."""
    if not questions:
        return 100, []
    justes = [set(reponses.get(i, set())) == set(q['bonnes']) for i, q in enumerate(questions)]
    return round(100 * sum(justes) / len(questions)), justes


# ====================================================================== campagnes
def utilisateurs_cibles(cid, cible):
    m = _m()
    q = m.User.query.filter(m.User.client_id == cid, m.User.is_active.is_(True))
    if hasattr(m.User, 'deleted_at'):
        q = q.filter(m.User.deleted_at.is_(None))
    if hasattr(m.User, 'is_blocked'):
        q = q.filter((m.User.is_blocked.is_(False)) | (m.User.is_blocked.is_(None)))
    genre, valeurs = (cible or {}).get('type', 'tous'), (cible or {}).get('valeurs') or []
    if genre == 'directions':
        q = q.filter(m.User.direction_id.in_([int(v) for v in valeurs if str(v).isdigit()] or [-1]))
    elif genre == 'roles':
        q = q.filter(m.User.role.in_([str(v) for v in valeurs] or ['-']))
    elif genre == 'utilisateurs':
        q = q.filter(m.User.id.in_([int(v) for v in valeurs if str(v).isdigit()] or [-1]))
    return q.order_by(m.User.nom, m.User.prenom, m.User.username).all()


def _notifier(cid, uids, titre, message, campagne_id, urgence='normal'):
    m = _m()
    for uid in uids:
        try:
            n = m.Notification(type_notification='info' if urgence == 'normal' else 'warning', titre=titre[:200], message=message,
                               destinataire_id=uid, entite_type='formation_campagne', entite_id=campagne_id, urgence=urgence,
                               est_lue=False, created_at=datetime.utcnow(),
                               donnees_supplementaires={'url': url_for('formation_conformite.mes_formations')})
            n.client_id = cid
            m.db.session.add(n)
        except Exception:  # noqa: BLE001
            pass


def synchroniser(c, notifier=True):
    """Ajoute les personnes qui correspondent à la cible et ne sont pas encore dans la campagne. Renvoie le nombre ajouté."""
    m = _m()
    deja = {a.user_id for a in m.AffectationFormationConformite.query.filter_by(campagne_id=c.id)}
    nouveaux = [u for u in utilisateurs_cibles(c.client_id, c.cible) if u.id not in deja]
    for u in nouveaux:
        m.db.session.add(m.AffectationFormationConformite(client_id=c.client_id, campagne_id=c.id, user_id=u.id,
                                                          statut='a_faire', tentatives=0, historique=[]))
    if notifier and nouveaux:
        limite = f' avant le {c.date_limite.strftime("%d/%m/%Y")}' if c.date_limite else ''
        _notifier(c.client_id, [u.id for u in nouveaux], f'Formation à suivre : {c.titre}',
                  f'Vous avez une formation à suivre{limite}. Retrouvez-la dans « Mes formations ».', c.id)
    return len(nouveaux)


def statut_effectif(a, c, aujourd_hui=None):
    if a.statut == 'reussi':
        return 'reussi'
    if c.date_limite and (aujourd_hui or date.today()) > c.date_limite:
        return 'en_retard'
    return a.statut or 'a_faire'


def chiffres(c, affectations=None, aujourd_hui=None):
    m = _m()
    aff = affectations if affectations is not None else m.AffectationFormationConformite.query.filter_by(campagne_id=c.id).all()
    st = [statut_effectif(a, c, aujourd_hui) for a in aff]
    total = len(aff)
    r = {k: st.count(k) for k in STATUTS}
    r['total'] = total
    r['taux'] = round(100 * r['reussi'] / total) if total else 0
    scores = [a.meilleur_score for a in aff if a.meilleur_score is not None]
    r['score_moyen'] = round(sum(scores) / len(scores)) if scores else None
    return r


# ====================================================================== pages : gestion
@bp.route('/')
@login_required
def accueil():
    cid = _exiger_suivi()
    m = _m()
    modules = m.ModuleFormationConformite.query.filter_by(client_id=cid).order_by(
        m.ModuleFormationConformite.statut.desc(), m.ModuleFormationConformite.titre).all()
    campagnes = m.CampagneFormationConformite.query.filter_by(client_id=cid).order_by(
        m.CampagneFormationConformite.created_at.desc()).all()
    par_module = {mod.id: mod for mod in modules}
    stats = {c.id: chiffres(c) for c in campagnes}
    actives = [c for c in campagnes if c.statut == 'active']
    tot = sum(stats[c.id]['total'] for c in actives)
    ok = sum(stats[c.id]['reussi'] for c in actives)
    retard = sum(stats[c.id]['en_retard'] for c in actives)
    from egalyx import formation_conformite_lot2 as lot2
    gerer = peut_gerer(cid=cid)
    bib = lot2.vue_client(cid) if gerer else None
    return render_template('egalyx/formation_accueil.html', modules=modules, campagnes=campagnes, par_module=par_module, bib=bib,
                           stats=stats, kpi=dict(publies=sum(1 for x in modules if x.statut == 'publie'), actives=len(actives),
                                                 taux=round(100 * ok / tot) if tot else None, retard=retard),
                           CATEGORIE=CATEGORIE, gerer=peut_gerer(cid=cid))


@bp.route('/module/nouveau', methods=['GET', 'POST'])
@bp.route('/module/<int:mid>', methods=['GET', 'POST'])
@login_required
def module_form(mid=None):
    cid = _exiger_gestion()
    m = _m()
    mod = _module(cid, mid) if mid else None
    if request.method == 'POST':
        f = request.form
        titre = (f.get('titre') or '').strip()[:200]
        try:
            questions = lire_questions(f.get('questions_json'))
        except ValueError as e:
            flash(str(e), 'danger')
            return render_template('egalyx/formation_module_form.html', mod=mod, saisie=f, questions=f.get('questions_json') or '[]',
                                   CATEGORIES=CATEGORIES)
        if not titre:
            flash('Donnez un titre au module.', 'danger')
            return render_template('egalyx/formation_module_form.html', mod=mod, saisie=f, questions=json.dumps(questions),
                                   CATEGORIES=CATEGORIES)
        video = (f.get('video_url') or '').strip()[:500]
        if video and not video.startswith('https://'):
            flash('Le lien de la vidéo doit commencer par https://', 'danger')
            return render_template('egalyx/formation_module_form.html', mod=mod, saisie=f, questions=json.dumps(questions),
                                   CATEGORIES=CATEGORIES)
        nouveau = mod is None
        if nouveau:
            mod = m.ModuleFormationConformite(client_id=cid, created_by=current_user.id, version=1, statut='brouillon')
            m.db.session.add(mod)
        avant = (mod.contenu, mod.questions) if not nouveau else None
        mod.titre = titre
        mod.resume = (f.get('resume') or '').strip()[:2000]
        mod.contenu = (f.get('contenu') or '').strip()[:100000]
        mod.video_url = video or None
        mod.categorie = f.get('categorie') if f.get('categorie') in CATEGORIE else 'autre'
        mod.duree_minutes = max(1, min(600, f.get('duree_minutes', type=int) or 15))
        mod.score_min = max(0, min(100, f.get('score_min', type=int) if f.get('score_min') not in (None, '') else 80))
        mod.questions = questions
        if not nouveau and mod.statut == 'publie' and avant != (mod.contenu, mod.questions):
            mod.version = (mod.version or 1) + 1
        if f.get('action') == 'publier':
            if not mod.contenu and not mod.video_url:
                flash('Ajoutez un contenu ou une vidéo avant de publier.', 'warning')
            else:
                mod.statut = 'publie'
        m.db.session.flush()
        journaliser('formation_module_enregistre', {'module_id': mod.id, 'titre': mod.titre, 'statut': mod.statut}, client_id=cid)
        m.db.session.commit()
        flash('Module publié.' if mod.statut == 'publie' and f.get('action') == 'publier' else 'Module enregistré.', 'success')
        return redirect(url_for('formation_conformite.module_form', mid=mod.id))
    maj_bib = None
    if mod and mod.origine:
        b = m.ModuleBibliothequeFormation.query.filter_by(code=mod.origine, statut='publie').first()
        if b and (b.version or 1) > (mod.origine_version or 0):
            maj_bib = b
    return render_template('egalyx/formation_module_form.html', mod=mod, saisie=None, maj_bib=maj_bib,
                           questions=json.dumps((mod.questions if mod else []) or [], ensure_ascii=False), CATEGORIES=CATEGORIES)


@bp.route('/module/<int:mid>/apercu')
@login_required
def module_apercu(mid):
    cid = _exiger_suivi()
    mod = _module(cid, mid)
    return render_template('egalyx/formation_suivre.html', mod=mod, a=None, c=None, apercu=True, resultat=None,
                           contenu=rendre_contenu(mod.contenu), chapitres=chapitres(mod.contenu), today=date.today(), CATEGORIE=CATEGORIE, video=video_integree(mod.video_url))


@bp.route('/module/<int:mid>/etat', methods=['POST'])
@login_required
def module_etat(mid):
    cid = _exiger_gestion()
    m = _m()
    mod = _module(cid, mid)
    action = request.form.get('action')
    if action == 'archiver':
        mod.statut = 'archive'
        flash('Module archivé : il ne peut plus être utilisé pour une nouvelle campagne.', 'success')
    elif action == 'retablir':
        mod.statut = 'brouillon'
        flash('Module rétabli en brouillon.', 'success')
    elif action == 'dupliquer':
        copie = m.ModuleFormationConformite(client_id=cid, titre=(f'Copie de {mod.titre}')[:200], resume=mod.resume,
                                            contenu=mod.contenu, video_url=mod.video_url, categorie=mod.categorie,
                                            duree_minutes=mod.duree_minutes, score_min=mod.score_min,
                                            questions=list(mod.questions or []), statut='brouillon', version=1,
                                            origine=mod.origine, created_by=current_user.id)
        m.db.session.add(copie)
        m.db.session.flush()
        journaliser('formation_module_duplique', {'module_id': mod.id, 'copie_id': copie.id}, client_id=cid)
        m.db.session.commit()
        flash('Copie créée.', 'success')
        return redirect(url_for('formation_conformite.module_form', mid=copie.id))
    elif action == 'supprimer':
        if m.CampagneFormationConformite.query.filter_by(module_id=mod.id).count():
            flash('Ce module est utilisé par une campagne : archivez-le plutôt (les preuves de formation sont conservées).', 'warning')
            return redirect(url_for('formation_conformite.module_form', mid=mod.id))
        journaliser('formation_module_supprime', {'module_id': mod.id, 'titre': mod.titre}, client_id=cid)
        m.db.session.delete(mod)
        m.db.session.commit()
        flash('Module supprimé.', 'success')
        return redirect(url_for('formation_conformite.accueil'))
    else:
        abort(400)
    journaliser('formation_module_' + action, {'module_id': mod.id}, client_id=cid)
    m.db.session.commit()
    return redirect(url_for('formation_conformite.module_form', mid=mod.id))


@bp.route('/campagne/nouvelle', methods=['GET', 'POST'])
@login_required
def campagne_form():
    cid = _exiger_gestion()
    m = _m()
    modules = m.ModuleFormationConformite.query.filter_by(client_id=cid, statut='publie').order_by(
        m.ModuleFormationConformite.titre).all()
    directions = []
    if hasattr(m, 'Direction'):
        try:
            q = m.Direction.query
            if hasattr(m.Direction, 'client_id'):
                q = q.filter_by(client_id=cid)
            directions = q.order_by(m.Direction.nom).all()
        except Exception:  # noqa: BLE001
            directions = []
    personnes = utilisateurs_cibles(cid, {'type': 'tous'})
    roles = sorted({u.role for u in personnes if u.role})
    from egalyx import formation_bibliotheque as fbib
    from egalyx import formation_conformite_lot2 as lot2
    parcours = [(code, titre, len(lot2._modules_parcours(cid, code))) for code, (titre, _d) in fbib.PARCOURS.items()]
    parcours = [x for x in parcours if x[2]]
    kris = m.KRI.query.filter_by(client_id=cid).order_by(m.KRI.nom).all() if hasattr(m, 'KRI') else []
    if request.method == 'POST':
        f = request.form
        choix = f.get('module_id') or ''
        code_parcours = choix.split(':', 1)[1] if choix.startswith('parcours:') else None
        mod = next((x for x in modules if str(x.id) == choix), None)
        titre = (f.get('titre') or '').strip()[:200] or (mod.titre if mod else '')
        genre = f.get('cible_type') if f.get('cible_type') in ('tous', 'directions', 'roles', 'utilisateurs') else 'tous'
        valeurs = f.getlist('cible_' + genre) if genre != 'tous' else []
        limite = None
        if f.get('date_limite'):
            try:
                limite = datetime.strptime(f.get('date_limite'), '%Y-%m-%d').date()
            except ValueError:
                limite = None
        erreur = None
        kri_id = f.get('kri_id', type=int)
        if kri_id and not any(k.id == kri_id for k in kris):
            kri_id = None
        relances = f.get('relances_auto') == '1'
        if code_parcours and code_parcours in fbib.PARCOURS:
            erreur = None if (genre == 'tous' or valeurs) else 'Choisissez au moins une direction, un rôle ou une personne.'
            if not erreur and limite and limite < date.today():
                erreur = 'La date limite est déjà passée.'
            if not erreur:
                total, lancees = 0, []
                for b in lot2._modules_parcours(cid, code_parcours):
                    mp, _nouveau = lot2.importer(cid, b)
                    if mp.statut != 'publie':
                        continue
                    c = m.CampagneFormationConformite(client_id=cid, module_id=mp.id, titre=f'{fbib.PARCOURS[code_parcours][0]} — {mp.titre}'[:200],
                                                      message=(f.get('message') or '').strip()[:2000], date_limite=limite,
                                                      cible={'type': genre, 'valeurs': valeurs}, statut='active', relances_auto=relances,
                                                      kri_id=kri_id, created_by=current_user.id)
                    m.db.session.add(c)
                    m.db.session.flush()
                    total = max(total, synchroniser(c))
                    lancees.append(c.id)
                journaliser('formation_parcours_lance', {'parcours': code_parcours, 'campagnes': lancees, 'personnes': total}, client_id=cid)
                m.db.session.commit()
                flash(f'Parcours lancé : {len(lancees)} module(s), {total} personne(s) concernée(s).', 'success')
                return redirect(url_for('formation_conformite.accueil'))
            flash(erreur, 'danger')
            return render_template('egalyx/formation_campagne_form.html', modules=modules, directions=directions, personnes=personnes,
                                   roles=roles, saisie=request.form, choisi=None, parcours=parcours, kris=kris)
        if mod is None:
            erreur = 'Choisissez un module publié.'
        elif genre != 'tous' and not valeurs:
            erreur = 'Choisissez au moins une direction, un rôle ou une personne.'
        elif limite and limite < date.today():
            erreur = 'La date limite est déjà passée.'
        if erreur:
            flash(erreur, 'danger')
        else:
            c = m.CampagneFormationConformite(client_id=cid, module_id=mod.id, titre=titre, message=(f.get('message') or '').strip()[:2000],
                                              date_limite=limite, cible={'type': genre, 'valeurs': valeurs}, statut='active',
                                              relances_auto=relances, kri_id=kri_id, created_by=current_user.id)
            m.db.session.add(c)
            m.db.session.flush()
            n = synchroniser(c)
            journaliser('formation_campagne_lancee', {'campagne_id': c.id, 'module_id': mod.id, 'personnes': n}, client_id=cid)
            m.db.session.commit()
            flash(f'Campagne lancée : {n} personne(s) concernée(s), prévenue(s) par notification.', 'success')
            return redirect(url_for('formation_conformite.campagne', kid=c.id))
    choisi = request.args.get('module_id', type=int)
    if request.args.get('parcours') in fbib.PARCOURS:
        choisi = 'parcours:' + request.args.get('parcours')
    return render_template('egalyx/formation_campagne_form.html', modules=modules, directions=directions, personnes=personnes,
                           roles=roles, saisie=request.form if request.method == 'POST' else None, choisi=choisi,
                           parcours=parcours, kris=kris)


@bp.route('/campagne/<int:kid>')
@login_required
def campagne(kid):
    cid = _exiger_suivi()
    m = _m()
    c = _campagne(cid, kid)
    mod = m.db.session.get(m.ModuleFormationConformite, c.module_id)
    aff = m.AffectationFormationConformite.query.filter_by(campagne_id=c.id).all()
    users = {u.id: u for u in m.User.query.filter(m.User.id.in_([a.user_id for a in aff] or [-1]))}
    lignes = sorted(({'a': a, 'u': users.get(a.user_id), 'statut': statut_effectif(a, c)} for a in aff),
                    key=lambda x: (x['statut'] == 'reussi', nom_personne(x['u']) if x['u'] else ''))
    kris = m.KRI.query.filter_by(client_id=cid).order_by(m.KRI.nom).all() if hasattr(m, 'KRI') else []
    kri = next((k for k in kris if k.id == c.kri_id), None)
    return render_template('egalyx/formation_campagne.html', c=c, mod=mod, lignes=lignes, stats=chiffres(c, aff),
                           STATUTS=STATUTS, gerer=peut_gerer(cid=cid), nom_personne=nom_personne, kris=kris, kri=kri)


@bp.route('/campagne/<int:kid>/action', methods=['POST'])
@login_required
def campagne_action(kid):
    cid = _exiger_gestion()
    m = _m()
    c = _campagne(cid, kid)
    action = request.form.get('action')
    if action == 'relancer':
        if c.statut != 'active':
            abort(400)
        aff = m.AffectationFormationConformite.query.filter_by(campagne_id=c.id).all()
        cibles = [a.user_id for a in aff if a.statut != 'reussi']
        retard = c.date_limite and date.today() > c.date_limite
        limite = f' La date limite {"était" if retard else "est"} le {c.date_limite.strftime("%d/%m/%Y")}.' if c.date_limite else ''
        _notifier(cid, cibles, f'Rappel : formation à suivre — {c.titre}',
                  f'Votre formation n’est pas encore validée.{limite} Retrouvez-la dans « Mes formations ».', c.id,
                  urgence='important' if retard else 'normal')
        c.derniere_relance = datetime.utcnow()
        journaliser('formation_campagne_relance', {'campagne_id': c.id, 'personnes': len(cibles)}, client_id=cid)
        flash(f'{len(cibles)} personne(s) relancée(s).' if cibles else 'Tout le monde a validé : personne à relancer.', 'success')
    elif action == 'synchroniser':
        if c.statut != 'active':
            abort(400)
        n = synchroniser(c)
        journaliser('formation_campagne_personnes', {'campagne_id': c.id, 'ajoutes': n}, client_id=cid)
        flash(f'{n} nouvelle(s) personne(s) ajoutée(s).' if n else 'Aucune nouvelle personne ne correspond à la cible.', 'success')
    elif action == 'clore':
        c.statut = 'close'
        journaliser('formation_campagne_close', {'campagne_id': c.id}, client_id=cid)
        flash('Campagne close : les résultats sont conservés.', 'success')
    elif action == 'reglages':
        c.relances_auto = request.form.get('relances_auto') == '1'
        kri_id = request.form.get('kri_id', type=int)
        c.kri_id = kri_id if kri_id and m.KRI.query.filter_by(id=kri_id, client_id=cid).first() else None
        c.derniere_mesure_kri = None
        journaliser('formation_campagne_reglages', {'campagne_id': c.id, 'relances_auto': c.relances_auto, 'kri_id': c.kri_id}, client_id=cid)
        flash('Réglages enregistrés.', 'success')
    elif action == 'rouvrir':
        c.statut = 'active'
        journaliser('formation_campagne_rouverte', {'campagne_id': c.id}, client_id=cid)
        flash('Campagne rouverte.', 'success')
    else:
        abort(400)
    m.db.session.commit()
    return redirect(url_for('formation_conformite.campagne', kid=c.id))


@bp.route('/campagne/<int:kid>/export.xlsx')
@login_required
def campagne_export(kid):
    cid = _exiger_suivi()
    m = _m()
    c = _campagne(cid, kid)
    mod = m.db.session.get(m.ModuleFormationConformite, c.module_id)
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    aff = m.AffectationFormationConformite.query.filter_by(campagne_id=c.id).all()
    users = {u.id: u for u in m.User.query.filter(m.User.id.in_([a.user_id for a in aff] or [-1]))}
    wb = Workbook()
    ws = wb.active
    ws.title = 'Suivi'
    gras, fond = Font(bold=True, color='FFFFFF'), PatternFill('solid', fgColor='1F4E79')
    st = chiffres(c, aff)
    ws.append(['Campagne', c.titre]); ws.append(['Module', mod.titre if mod else '']); ws.append(['Version du module', mod.version if mod else ''])
    ws.append(['Date limite', c.date_limite.strftime('%d/%m/%Y') if c.date_limite else '—'])
    ws.append(['Score minimum', f'{mod.score_min} %' if mod else '']); ws.append(['Taux de réalisation', f"{st['taux']} %"])
    ws.append(['Exporté le', datetime.now().strftime('%d/%m/%Y %H:%M')]); ws.append([])
    entete = ['Nom', 'E-mail', 'Fonction', 'Statut', 'Tentatives', 'Meilleur score (%)', 'Dernier score (%)',
              'Commencé le', 'Validé le', 'Version validée']
    ws.append(entete)
    for i in range(1, len(entete) + 1):
        cel = ws.cell(row=ws.max_row, column=i); cel.font, cel.fill = gras, fond
    for a in sorted(aff, key=lambda a: nom_personne(users.get(a.user_id)) if users.get(a.user_id) else ''):
        u = users.get(a.user_id)
        ws.append([nom_personne(u) if u else f'#{a.user_id}', getattr(u, 'email', ''), getattr(u, 'fonction', '') or '',
                   STATUTS[statut_effectif(a, c)], a.tentatives or 0, a.meilleur_score, a.dernier_score,
                   a.debut_le.strftime('%d/%m/%Y %H:%M') if a.debut_le else '', a.reussi_le.strftime('%d/%m/%Y %H:%M') if a.reussi_le else '',
                   a.version_module or ''])
    for col, larg in zip('ABCDEFGHIJ', (28, 30, 24, 12, 11, 18, 17, 17, 17, 15)):
        ws.column_dimensions[col].width = larg
    sortie = io.BytesIO()
    wb.save(sortie)
    sortie.seek(0)
    journaliser('formation_campagne_export', {'campagne_id': c.id}, client_id=cid, valider=True)
    nom = re.sub(r'[^A-Za-z0-9_-]+', '_', c.titre)[:60] or 'campagne'
    return send_file(sortie, as_attachment=True, download_name=f'formation_{nom}.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


# ====================================================================== pages : chaque personne
def _mes_affectations(u):
    m = _m()
    rows = (m.db.session.query(m.AffectationFormationConformite, m.CampagneFormationConformite)
            .join(m.CampagneFormationConformite, m.CampagneFormationConformite.id == m.AffectationFormationConformite.campagne_id)
            .filter(m.AffectationFormationConformite.user_id == u.id,
                    m.AffectationFormationConformite.client_id == u.client_id).all())
    return [(a, c) for a, c in rows if c.statut == 'active' or a.statut == 'reussi']


def nb_a_faire(u=None):
    u = u or current_user
    try:
        if not peut_suivre(u):
            return 0
        return sum(1 for a, c in _mes_affectations(u) if a.statut != 'reussi' and c.statut == 'active')
    except Exception:  # noqa: BLE001
        return 0


@bp.route('/mes-formations')
@login_required
def mes_formations():
    if not peut_suivre():
        abort(404)
    m = _m()
    lignes = []
    for a, c in _mes_affectations(current_user):
        mod = m.db.session.get(m.ModuleFormationConformite, c.module_id)
        lignes.append({'a': a, 'c': c, 'mod': mod, 'statut': statut_effectif(a, c)})
    lignes.sort(key=lambda x: (x['statut'] == 'reussi', x['c'].date_limite or date.max))
    return render_template('egalyx/formation_mes.html', lignes=lignes, STATUTS=STATUTS, CATEGORIE=CATEGORIE, today=date.today())


def _mon_affectation(aid):
    m = _m()
    a = m.db.session.get(m.AffectationFormationConformite, aid)
    if a is None or a.user_id != current_user.id or a.client_id != current_user.client_id or not peut_suivre():
        abort(404)
    c = m.db.session.get(m.CampagneFormationConformite, a.campagne_id)
    mod = m.db.session.get(m.ModuleFormationConformite, c.module_id)
    if c.statut != 'active' and a.statut != 'reussi':
        abort(404)
    return a, c, mod


@bp.route('/suivre/<int:aid>', methods=['GET', 'POST'])
@login_required
def suivre(aid):
    m = _m()
    a, c, mod = _mon_affectation(aid)
    resultat = None
    if a.statut == 'a_faire':
        a.statut, a.debut_le = 'en_cours', datetime.utcnow()
        m.db.session.commit()
    if request.method == 'POST':
        if c.statut != 'active':
            abort(400)
        questions = mod.questions or []
        reponses = {}
        for i, q in enumerate(questions):
            reponses[i] = {int(v) for v in request.form.getlist(f'q{i}') if v.isdigit() and int(v) < len(q['choix'])}
        if questions and any(not reponses[i] for i in range(len(questions))):
            flash('Répondez à toutes les questions avant de valider.', 'warning')
            return render_template('egalyx/formation_suivre.html', mod=mod, a=a, c=c, apercu=False, resultat=None,
                                   contenu=rendre_contenu(mod.contenu), chapitres=chapitres(mod.contenu), today=date.today(), CATEGORIE=CATEGORIE, video=video_integree(mod.video_url), choisis=reponses)
        score, justes = noter(questions, reponses)
        reussi = score >= (mod.score_min or 0)
        a.tentatives = (a.tentatives or 0) + 1
        a.dernier_score = score
        a.meilleur_score = max(score, a.meilleur_score or 0)
        a.historique = list(a.historique or []) + [{'le': datetime.utcnow().isoformat(timespec='seconds'), 'score': score,
                                                    'reussi': reussi, 'version': mod.version}]
        if reussi and a.statut != 'reussi':
            a.statut, a.reussi_le, a.version_module = 'reussi', datetime.utcnow(), mod.version
        journaliser('formation_quiz', {'affectation_id': a.id, 'campagne_id': c.id, 'score': score, 'reussi': reussi},
                    client_id=a.client_id)
        m.db.session.commit()
        resultat = {'score': score, 'reussi': reussi, 'justes': justes, 'reponses': reponses}
    return render_template('egalyx/formation_suivre.html', mod=mod, a=a, c=c, apercu=False, resultat=resultat,
                           contenu=rendre_contenu(mod.contenu), chapitres=chapitres(mod.contenu), today=date.today(), CATEGORIE=CATEGORIE, video=video_integree(mod.video_url), choisis=None)


@bp.route('/suivre/<int:aid>/sans-quiz', methods=['POST'])
@login_required
def valider_sans_quiz(aid):
    """Module sans quiz : « J'ai lu et compris » vaut validation (horodatée)."""
    m = _m()
    a, c, mod = _mon_affectation(aid)
    if mod.questions or c.statut != 'active':
        abort(400)
    if a.statut != 'reussi':
        a.statut, a.reussi_le, a.version_module = 'reussi', datetime.utcnow(), mod.version
        a.tentatives = (a.tentatives or 0) + 1
        a.meilleur_score = a.dernier_score = 100
        a.historique = list(a.historique or []) + [{'le': datetime.utcnow().isoformat(timespec='seconds'), 'score': 100,
                                                    'reussi': True, 'version': mod.version, 'lecture': True}]
        journaliser('formation_lecture_validee', {'affectation_id': a.id, 'campagne_id': c.id}, client_id=a.client_id)
        m.db.session.commit()
        flash('Formation validée.', 'success')
    return redirect(url_for('formation_conformite.suivre', aid=a.id))


# ====================================================================== enregistrement
def enregistrer(app):
    from egalyx import formation_conformite_lot2 as lot2      # ajoute ses routes au blueprint avant l'enregistrement
    if 'formation_conformite' not in app.blueprints:
        app.register_blueprint(bp)

    def _gestion_visible():
        try:
            cid = client_id_courant()
            return bool(cid) and peut_voir_suivi(cid=cid)
        except Exception:  # noqa: BLE001
            return False

    def _mes_visible():
        try:
            return peut_suivre() and bool(_mes_affectations(current_user))
        except Exception:  # noqa: BLE001
            return False

    app.jinja_env.globals['formation_gestion_visible'] = _gestion_visible
    app.jinja_env.globals['formation_mes_visible'] = _mes_visible
    app.jinja_env.globals['formation_a_faire'] = nb_a_faire
    from egalyx import formation_visuels
    formation_visuels.enregistrer(app)
    with app.app_context():
        try:
            m = _m()
            for t in (m.ModuleFormationConformite, m.CampagneFormationConformite, m.AffectationFormationConformite):
                t.__table__.create(m.db.engine, checkfirst=True)
        except Exception:  # noqa: BLE001
            pass
    lot2.enregistrer(app)
