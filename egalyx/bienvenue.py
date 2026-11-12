"""
egalyx/bienvenue.py — e-mail de bienvenue automatique à chaque nouvel utilisateur d'une organisation.

Quand un compte est créé (par le super admin, l'administrateur du client ou un gestionnaire), la personne reçoit :
  - l'adresse d'accès de son organisation (https://<client>.egalyx.com) et son identifiant ;
  - jamais le mot de passe (communiqué par la personne qui a créé le compte) ;
  - si la double authentification lui sera demandée (administrateur, ou organisation qui l'exige pour tous) :
    l'application à installer et le lien du guide pas à pas.
Le compte administrateur créé avec un nouveau client n'est pas concerné : il reçoit déjà l'e-mail de création du
client (identifiants + guide). Sans SMTP configuré, rien n'est envoyé. EGALYX_EMAIL_BIENVENUE=0 désactive l'envoi.
Comme pour les alertes, les adresses sont préparées pendant l'enregistrement et l'envoi part après le commit.
"""
import os
import threading

from sqlalchemy import event

CLE = 'egalyx_bienvenue'


def _base():
    return (os.environ.get('EGALYX_URL_PUBLIQUE') or 'https://egalyx.com').rstrip('/')


def url_guide():
    return _base() + '/compte/securite/guide'


def texte_2fa_html():
    return ("<p style='margin-top:14px'><strong>🔐 Double authentification</strong><br>"
            "À votre première connexion, un code à 6 chiffres généré par votre téléphone vous sera demandé. "
            "Installez d'abord <strong>FreeOTP</strong>, <strong>Google Authenticator</strong> ou "
            "<strong>Microsoft Authenticator</strong>, puis suivez le guide : "
            f"<a href='{url_guide()}'>{url_guide()}</a></p>")


def texte_2fa():
    return ("\nDouble authentification : à votre première connexion, un code à 6 chiffres généré par votre téléphone "
            "vous sera demandé. Installez FreeOTP, Google Authenticator ou Microsoft Authenticator, puis suivez le "
            f"guide : {url_guide()}\n")


def _avant_flush(session_, _ctx, _inst):
    if os.environ.get('EGALYX_EMAIL_BIENVENUE', '1') != '1':
        return
    import models as m
    crees = session_.info.setdefault(CLE + '_clients_objets', [])
    crees.extend(o for o in session_.new if isinstance(o, m.Client))
    for o in session_.new:
        if isinstance(o, m.User) and (o.client_id is not None or getattr(o, 'client', None) is not None):
            if getattr(o, 'role', None) == 'super_admin':
                continue
            session_.info.setdefault(CLE + '_users', []).append(o)


def _apres_flush(session_, _ctx):
    users = session_.info.pop(CLE + '_users', None)
    if not users:
        return
    # clients créés dans cette même transaction : leur compte administrateur reçoit déjà l'e-mail de création du client
    clients_neufs = {c.id for c in session_.info.get(CLE + '_clients_objets', []) if getattr(c, 'id', None)}
    import models as m
    from egalyx.double_auth import obligatoire_pour
    from egalyx.gestion_clients import url_client
    try:
        from egalyx.identite import nom_affiche
    except Exception:  # noqa: BLE001
        nom_affiche = None
    with session_.no_autoflush:
        for u in users:
            if not getattr(u, 'email', None) or not u.id or u.client_id in clients_neufs:
                continue
            client = session_.get(m.Client, u.client_id) if u.client_id else None
            acces = (url_client(client) if client is not None else None) or _base()
            nom_org = (nom_affiche(client.id) if (nom_affiche and client is not None) else None) or \
                (client.nom if client is not None else 'Egalyx')
            avec_2fa = obligatoire_pour(u)
            sujet = f'[{nom_org}] Votre accès à Egalyx Control'
            texte = (f"Bonjour {u.username},\n\nUn compte Egalyx Control vient d'être créé pour vous ({nom_org}).\n\n"
                     f"Adresse : {acces}\nIdentifiant : {u.username}\n"
                     "Mot de passe : communiqué par la personne qui a créé votre compte (vous le changerez à la "
                     "première connexion).\n" + (texte_2fa() if avec_2fa else '') + "\n— Egalyx Control")
            html = (f"<p>Bonjour <strong>{u.username}</strong>,</p>"
                    f"<p>Un compte Egalyx Control vient d'être créé pour vous (<strong>{nom_org}</strong>).</p>"
                    f"<p>Adresse : <a href='{acces}'>{acces}</a><br>Identifiant : <strong>{u.username}</strong><br>"
                    "Mot de passe : communiqué par la personne qui a créé votre compte (vous le changerez à la "
                    "première connexion).</p>" + (texte_2fa_html() if avec_2fa else '')
                    + "<p style='color:#64748b;font-size:13px'>— Egalyx Control</p>")
            session_.info.setdefault(CLE + '_envois', []).append((u.email, sujet, texte, html))


def _apres_commit(session_):
    session_.info.pop(CLE + '_clients_objets', None)
    envois = session_.info.pop(CLE + '_envois', None)
    if not envois:
        return
    from egalyx import courriel
    if not courriel.est_configure():
        return

    def envoyer():
        for dest, sujet, texte, html in envois:
            try:
                courriel.envoyer([dest], sujet, texte, html=html)
            except Exception:  # noqa: BLE001
                pass
    threading.Thread(target=envoyer, daemon=True).start()


def _apres_rollback(session_):
    for k in (CLE + '_users', CLE + '_envois', CLE + '_clients_objets'):
        session_.info.pop(k, None)


def enregistrer(app):
    import models as m
    from sqlalchemy.orm import Session
    if getattr(m, '_egalyx_bienvenue', False):
        return
    event.listen(Session, 'before_flush', _avant_flush)
    event.listen(Session, 'after_flush', _apres_flush)
    event.listen(Session, 'after_commit', _apres_commit)
    event.listen(Session, 'after_soft_rollback', lambda sess, _t: _apres_rollback(sess))
    m._egalyx_bienvenue = True
