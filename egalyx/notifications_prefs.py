"""
egalyx/notifications_prefs.py — « Mes notifications » : chacun choisit comment il est prévenu.

Pour chaque type d'événement : dans l'application (toujours), e-mail immédiat, résumé quotidien.
  - Par défaut : application seulement (aucun e-mail tant que la personne ou son organisation ne l'a pas choisi).
  - L'administrateur de l'organisation peut IMPOSER l'e-mail immédiat ou le résumé pour un type d'événement : la
    ligne apparaît alors verrouillée chez chacun.
  - Les e-mails partent vers l'adresse du compte (jamais une autre adresse saisie ici : pas de fuite possible).
  - Le résumé quotidien, à l'heure choisie : les nouvelles notifications des types retenus + « Ma semaine »
    (en retard, à faire sous 7 jours). Un seul par jour et par personne.
  - Les alertes « délai dépassé » et « escalade » des incidents gardent leurs réglages d'organisation
    (Incidents → Alertes e-mail) : elles ne sont pas envoyées deux fois.
Remplace l'ancienne page /notifications/preferences, dont les choix n'étaient utilisés par aucun envoi ; ses
réglages sont conservés dans le même champ (users.preferences_notifications, clé « canaux »).
EGALYX_EMAIL_NOTIFICATIONS=0 coupe tous ces e-mails sur le serveur.
"""
import os
import threading
import time
from datetime import date, datetime, timedelta

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import event

EVENEMENTS = [
    ('incident', 'Incident déclaré, assigné ou résolu', 'Incidents'),
    ('a_valider', 'Élément à valider (contrôle N2, campagne, évaluation, PCA, qualité…)', 'Validations'),
    ('echeance', 'Échéance proche ou dépassée (plans d\'action, recommandations, dispositifs)', 'Échéances'),
    ('signalement', 'Nouveau signalement ou réponse à un signalement', 'Signalements'),
    ('kri', 'KRI en alerte ou critique', 'KRI'),
    ('incident_alerte', 'Incident : délai dépassé ou escalade', 'Incidents'),
    ('autres', 'Autres notifications', 'Divers'),
]
LIBELLES = {c: l for c, l, _g in EVENEMENTS}
HEURES = [7, 8, 12, 17]
CLE = 'canaux'
CLE_IMPOSES = 'notifications_imposees'


def _m():
    import models
    return models


def _base():
    return (os.environ.get('EGALYX_URL_PUBLIQUE') or 'https://egalyx.com').rstrip('/')


# ---------------------------------------------------------------- classement
def evenement(n):
    t = (getattr(n, 'type_notification', None) or '').lower()
    titre = (getattr(n, 'titre', None) or '').lower()
    try:
        from egalyx.incidents import _a_envoyer
        if _a_envoyer(n) and ('délai dépassé' in titre or 'scalade' in titre or t == 'escalade'):
            return 'incident_alerte'
    except Exception:  # noqa: BLE001
        pass
    if t == 'escalade':
        return 'incident_alerte'
    if t in ('incident', 'resolution') or getattr(n, 'entite_type', None) == 'incident':
        return 'incident'
    if t == 'signalement':
        return 'signalement'
    if t.startswith('kri'):
        return 'kri'
    if t in ('echeance_proche', 'retard') or 'échéance' in titre or 'en retard' in titre:
        return 'echeance'
    if t in ('evaluation_a_valider', 'alerte_approbation', 'reevaluation_demandee', 'nouveau_risque_propose',
             'validation', 'a_valider', 'soumission') or 'à valider' in titre or 'valider' in titre or 'soumis' in titre:
        return 'a_valider'
    return 'autres'


# ---------------------------------------------------------------- préférences
def _prefs_brutes(u):
    p = getattr(u, 'preferences_notifications', None)
    return p if isinstance(p, dict) else {}


def imposes(client_id, session_=None):
    """{code: {'email': bool, 'resume': bool}} imposé par l'organisation."""
    if not client_id:
        return {}
    try:
        m = _m()
        s = session_ or m.db.session
        conf = s.query(m.ClientConfiguration).filter_by(client_id=client_id).first()
        return ((conf.preferences or {}).get(CLE_IMPOSES) if conf else None) or {}
    except Exception:  # noqa: BLE001
        return {}


def reglages(u, session_=None):
    p = (_prefs_brutes(u).get(CLE) or {})
    imp = imposes(getattr(u, 'client_id', None), session_)
    ev = {}
    for code, _l, _g in EVENEMENTS:
        choix = (p.get('evenements') or {}).get(code) or {}
        i = imp.get(code) or {}
        ev[code] = {'email': bool(choix.get('email')) or bool(i.get('email')),
                    'resume': bool(choix.get('resume')) or bool(i.get('resume')),
                    'email_impose': bool(i.get('email')), 'resume_impose': bool(i.get('resume'))}
    heure = p.get('heure_resume', 7)
    return {'evenements': ev, 'heure_resume': heure if heure in HEURES else 7,
            'dernier_resume': p.get('dernier_resume')}


def _ecrire(u, nouveaux):
    p = dict(_prefs_brutes(u))
    c = dict(p.get(CLE) or {})
    c.update(nouveaux)
    p[CLE] = c
    u.preferences_notifications = p            # nouvelle valeur : le changement du JSON est bien détecté


# ---------------------------------------------------------------- e-mail immédiat
def _apres_flush(session_, _ctx):
    if os.environ.get('EGALYX_EMAIL_NOTIFICATIONS', '1') != '1':
        return
    m = _m()
    nouvelles = [n for n in session_.new if isinstance(n, m.Notification) and n.destinataire_id]
    if not nouvelles:
        return
    cache = {}
    with session_.no_autoflush:
        for n in nouvelles:
            code = evenement(n)
            if code == 'incident_alerte':          # déjà envoyé selon les réglages d'alertes de l'organisation
                continue
            u = session_.get(m.User, n.destinataire_id)
            if u is None or not getattr(u, 'email', None) or getattr(u, 'is_active', True) is False:
                continue
            if u.id not in cache:
                cache[u.id] = reglages(u, session_)
            if not cache[u.id]['evenements'][code]['email']:
                continue
            nom = None
            try:
                from egalyx.identite import nom_affiche
                nom = nom_affiche(u.client_id) if u.client_id else None
            except Exception:  # noqa: BLE001
                pass
            prefixe = f'[{nom or "Egalyx"}]'
            lien = f"{_base()}/notifications/notification/{n.id}/lire" if n.id else _base()
            texte = (f"{n.message or n.titre}\n\nOuvrir : {lien}\n\nVous recevez cet e-mail selon vos préférences "
                     f"(Mes notifications : {_base()}/notifications/preferences).\n— Egalyx Control")
            session_.info.setdefault('egalyx_notif_envois', []).append((u.email, f'{prefixe} {n.titre}', texte))


def _apres_commit(session_):
    envois = session_.info.pop('egalyx_notif_envois', None)
    if not envois:
        return
    from egalyx import courriel
    if not courriel.est_configure():
        return

    def envoyer():
        for dest, sujet, texte in envois:
            try:
                courriel.envoyer([dest], sujet, texte)
            except Exception:  # noqa: BLE001
                pass
    threading.Thread(target=envoyer, daemon=True).start()


def _apres_rollback(session_):
    session_.info.pop('egalyx_notif_envois', None)


# ---------------------------------------------------------------- résumé quotidien
def contenu_resume(u, depuis):
    """(sujet, texte) du résumé de u, ou None s'il n'y a rien à dire."""
    m = _m()
    r = reglages(u)
    codes = {c for c, v in r['evenements'].items() if v['resume']}
    if not codes:
        return None
    notifs = [n for n in m.Notification.query.filter(m.Notification.destinataire_id == u.id,
                                                     m.Notification.created_at >= depuis)
              .order_by(m.Notification.created_at.desc()).limit(200).all() if evenement(n) in codes]
    taches = []
    try:
        from egalyx.ma_semaine import taches as calcul
        aujourd_hui = date.today()
        taches = [t for t in calcul(u) if t.get('retard_jours') or (t.get('echeance') and t['echeance'] <= aujourd_hui + timedelta(days=7))]
    except Exception:  # noqa: BLE001
        taches = []
    if not notifs and not taches:
        return None
    lignes = [f"Bonjour {u.username},", '']
    if taches:
        en_retard = [t for t in taches if t.get('retard_jours')]
        lignes.append(f"Ma semaine : {len(taches)} point(s) à traiter" + (f", dont {len(en_retard)} en retard" if en_retard else '') + '.')
        for t in taches[:10]:
            e = t['echeance'].strftime('%d/%m') if t.get('echeance') else ''
            etat = f"en retard de {t['retard_jours']} j" if t.get('retard_jours') else f"échéance {e}"
            lignes.append(f"  - {t['type']} : {t['titre']} ({etat})")
        if len(taches) > 10:
            lignes.append(f"  … et {len(taches) - 10} autre(s).")
        lignes.append(f"  {_base()}/ma-semaine")
        lignes.append('')
    if notifs:
        lignes.append(f"Nouvelles notifications ({len(notifs)}) :")
        for n in notifs[:15]:
            lignes.append(f"  - {n.titre}")
        if len(notifs) > 15:
            lignes.append(f"  … et {len(notifs) - 15} autre(s).")
        lignes.append('')
    lignes.append(f"Régler ce résumé : {_base()}/notifications/preferences")
    lignes.append('— Egalyx Control')
    nom = None
    try:
        from egalyx.identite import nom_affiche
        nom = nom_affiche(u.client_id) if u.client_id else None
    except Exception:  # noqa: BLE001
        pass
    sujet = f"[{nom or 'Egalyx'}] Votre résumé du {date.today().strftime('%d/%m')}" + \
        (f" : {len(taches)} point(s) à traiter" if taches else '')
    return sujet, '\n'.join(lignes)


def envoyer_resumes(maintenant=None, forcer=False):
    """Envoie les résumés dus. Retourne le nombre d'e-mails préparés."""
    m = _m()
    from egalyx import courriel
    maintenant = maintenant or datetime.now()
    aujourd_hui = maintenant.date().isoformat()
    candidats = [u for u in m.User.query.filter(m.User.is_active.is_(True), m.User.client_id.isnot(None)).all()
                 if getattr(u, 'email', None)]
    envois = []
    for u in candidats:
        r = reglages(u)
        if not any(v['resume'] for v in r['evenements'].values()):
            continue
        if not forcer and (r['dernier_resume'] == aujourd_hui or maintenant.hour < r['heure_resume']):
            continue
        depuis = datetime.utcnow() - timedelta(days=1)
        if r['dernier_resume']:
            try:
                depuis = max(depuis - timedelta(days=6), datetime.fromisoformat(r['dernier_resume']))
            except ValueError:
                pass
        _ecrire(u, {'dernier_resume': aujourd_hui})      # d'abord : jamais deux résumés le même jour
        m.db.session.commit()
        c = contenu_resume(u, depuis)
        if c:
            envois.append((u.email, c[0], c[1]))
    if envois and courriel.est_configure():
        def envoyer():
            for dest, sujet, texte in envois:
                try:
                    courriel.envoyer([dest], sujet, texte)
                except Exception:  # noqa: BLE001
                    pass
        threading.Thread(target=envoyer, daemon=True).start()
    return len(envois)


_DERNIERE = {'t': 0.0}


def _verification_periodique():
    if time.time() - _DERNIERE['t'] < 600 or request.endpoint in (None, 'static'):
        return None
    _DERNIERE['t'] = time.time()
    if os.environ.get('EGALYX_EMAIL_NOTIFICATIONS', '1') != '1':
        return None
    try:
        envoyer_resumes()
    except Exception as e:  # noqa: BLE001
        _m().db.session.rollback()
        print(f"⚠️ Résumés quotidiens : {e}")
    return None


# ---------------------------------------------------------------- page
def peut_imposer(u=None):
    u = u or current_user
    return getattr(u, 'role', None) in ('super_admin',) or bool(getattr(u, 'is_client_admin', False))


def page():
    from egalyx.commun import client_id_courant, journaliser
    m = _m()
    if not getattr(current_user, 'is_authenticated', False):
        abort(401)
    if request.method == 'POST':
        if request.form.get('action') == 'organisation':
            if not peut_imposer():
                abort(403)
            cid = client_id_courant() or current_user.client_id
            imp = {c: {'email': request.form.get(f'imp_email_{c}') == '1', 'resume': request.form.get(f'imp_resume_{c}') == '1'}
                   for c, _l, _g in EVENEMENTS if c != 'incident_alerte'}
            imp = {c: v for c, v in imp.items() if v['email'] or v['resume']}
            conf = m.ClientConfiguration.query.filter_by(client_id=cid).first()
            if conf is None:
                conf = m.ClientConfiguration(client_id=cid, couleurs={}, preferences={})
                m.db.session.add(conf)
            prefs = dict(conf.preferences or {})
            prefs[CLE_IMPOSES] = imp
            conf.preferences = prefs
            journaliser('notifications_imposees', imp, client_id=cid)
            m.db.session.commit()
            flash('Règles de l\'organisation enregistrées : elles s\'appliquent à tous ses utilisateurs.', 'success')
            return redirect(url_for('preferences_notifications'))
        ev = {c: {'email': request.form.get(f'email_{c}') == '1', 'resume': request.form.get(f'resume_{c}') == '1'}
              for c, _l, _g in EVENEMENTS if c != 'incident_alerte'}
        ev['incident_alerte'] = {'email': False, 'resume': request.form.get('resume_incident_alerte') == '1'}
        try:
            heure = int(request.form.get('heure_resume') or 7)
        except ValueError:
            heure = 7
        _ecrire(current_user, {'evenements': ev, 'heure_resume': heure if heure in HEURES else 7})
        m.db.session.commit()
        flash('Préférences enregistrées.', 'success')
        return redirect(url_for('preferences_notifications'))
    imp = imposes(current_user.client_id) if peut_imposer() else {}
    return render_template('egalyx/mes_notifications.html', r=reglages(current_user), evenements=EVENEMENTS,
                           heures=HEURES, peut_imposer=peut_imposer() and bool(current_user.client_id), imposes=imp)


def enregistrer(app):
    import models as m
    from sqlalchemy.orm import Session
    from egalyx.commun import exempter_controle_ancien
    if not getattr(m, '_egalyx_notif_prefs', False):
        event.listen(Session, 'after_flush', _apres_flush)
        event.listen(Session, 'after_commit', _apres_commit)
        event.listen(Session, 'after_soft_rollback', lambda s, _t: _apres_rollback(s))
        m._egalyx_notif_prefs = True
    vue = app.view_functions.get('preferences_notifications')
    if vue is not None and not getattr(vue, '_egalyx', False):
        def nouvelle(*a, **k):
            return page()
        nouvelle._egalyx = True
        nouvelle.__name__ = vue.__name__
        app.view_functions['preferences_notifications'] = nouvelle
        exempter_controle_ancien(app, {'preferences_notifications'})
    app.before_request(_verification_periodique)

    @app.cli.command('envoyer-resumes')
    def _cli():
        """Envoie les résumés quotidiens dus (à planifier toutes les heures si le serveur dort la nuit)."""
        n = envoyer_resumes()
        print(f'{n} résumé(s) préparé(s).')
