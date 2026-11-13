"""
egalyx/application_mobile.py — Egalyx installable sur téléphone et ordinateur (application web, sans magasin).

  - /manifest.webmanifest : nom, couleurs, icônes, page de départ (« Ma semaine » sur téléphone) ;
  - /application/icone-<taille>.png : icônes générées (bouclier Egalyx) et mises en cache dans instance/ ;
  - /sw.js : service worker minimal — le réseau d'abord, et une page « hors ligne » si la connexion manque.
    Aucune page de données n'est mise en cache (rien de confidentiel ne reste sur le téléphone) ;
  - /hors-ligne : page affichée sans réseau ;
  - bouton « Installer l'application » dans le menu du compte quand le navigateur le propose (Android, Chrome,
    Edge) ; sur iPhone : Partager → « Sur l'écran d'accueil » (expliqué dans l'aide).
L'ancien lien /static/favicon/site.webmanifest (fichier absent : 404 à chaque page) est remplacé.
"""
import io
import json
import os

from flask import Blueprint, Response, current_app, render_template, send_file

bp = Blueprint('application_mobile', __name__)

BLEU_NUIT = '#13294B'
TAILLES = (192, 512, 180)

SW = r"""
const VERSION = 'egalyx-v3';
const HORS_LIGNE = '/hors-ligne';
self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll([HORS_LIGNE, '/application/icone-192.png'])).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
// Notifications reçues (egalyx/notifications_push.py) : affichage + pastille sur l'icône de l'application.
self.addEventListener('push', e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (x) { d = {corps: e.data ? e.data.text() : ''}; }
  const travaux = [self.registration.showNotification(d.titre || 'Egalyx', {
    body: d.corps || '', icon: '/application/icone-192.png', badge: '/application/icone-192.png',
    tag: d.tag || 'egalyx', renotify: true, data: {url: d.url || '/notifications'}
  })];
  const nav = self.navigator;
  if (nav && 'setAppBadge' in nav) {
    if (d.pastille && d.non_lues > 0) travaux.push(nav.setAppBadge(d.non_lues).catch(() => {}));
    else if (d.pastille === false) travaux.push(nav.clearAppBadge().catch(() => {}));
  }
  e.waitUntil(Promise.all(travaux));
});
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || '/', self.location.origin).href;
  e.waitUntil(clients.matchAll({type: 'window', includeUncontrolled: true}).then(fenetres => {
    for (const f of fenetres) {
      if (f.url.startsWith(self.location.origin) && 'focus' in f) {
        return ('navigate' in f ? f.navigate(url).catch(() => f) : Promise.resolve(f)).then(x => (x || f).focus());
      }
    }
    return clients.openWindow(url);
  }));
});
self.addEventListener('fetch', e => {
  // En ligne : le service worker ne touche à RIEN, le navigateur charge les pages normalement
  // (connexion, double authentification, redirections). Hors ligne seulement : page « Pas de connexion ».
  if (e.request.mode !== 'navigate' || e.request.method !== 'GET') return;
  if (self.navigator && self.navigator.onLine === false) {
    e.respondWith(caches.match(HORS_LIGNE).then(r => r || fetch(e.request)));
  }
});
"""


def _icone(taille):
    d = os.path.join(current_app.instance_path, 'application')
    os.makedirs(d, exist_ok=True)
    chemin = os.path.join(d, f'icone-{taille}.png')
    if os.path.exists(chemin):
        return chemin
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    img = Image.new('RGB', (taille, taille), BLEU_NUIT)
    dr = ImageDraw.Draw(img)
    s = taille / 512.0
    # bouclier
    pts = [(256, 96), (396, 148), (396, 262), (380, 330), (330, 392), (256, 430), (182, 392), (132, 330), (116, 262),
           (116, 148)]
    dr.polygon([(x * s, y * s) for x, y in pts], fill='#93C5FD')
    pts2 = [(256, 140), (360, 178), (360, 262), (346, 318), (306, 366), (256, 392), (206, 366), (166, 318), (152, 262),
            (152, 178)]
    dr.polygon([(x * s, y * s) for x, y in pts2], fill=BLEU_NUIT)
    # coche
    dr.line([(200 * s, 266 * s), (244 * s, 310 * s), (318 * s, 222 * s)], fill='#FFFFFF', width=max(2, int(30 * s)),
            joint='curve')
    img.save(chemin, 'PNG', optimize=True)
    return chemin


@bp.route('/application/icone-<int:taille>.png')
def icone(taille):
    if taille not in TAILLES:
        taille = 192
    chemin = _icone(taille)
    if chemin is None:
        return Response(status=404)
    return send_file(chemin, mimetype='image/png', max_age=7 * 86400)


@bp.route('/manifest.webmanifest')
def manifeste():
    m = {
        'name': 'Egalyx Control',
        'short_name': 'Egalyx',
        'description': 'Risques, contrôles, incidents et audit',
        'lang': 'fr',
        'start_url': '/ma-semaine?source=application',
        'scope': '/',
        'display': 'standalone',
        'orientation': 'any',
        'background_color': '#F5F6F8',
        'theme_color': BLEU_NUIT,
        'icons': [
            {'src': '/application/icone-192.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any maskable'},
            {'src': '/application/icone-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'},
        ],
        'shortcuts': [
            {'name': 'Signaler un incident', 'url': '/signalements/nouveau', 'icons': [{'src': '/application/icone-192.png', 'sizes': '192x192'}]},
            {'name': 'Ma semaine', 'url': '/ma-semaine'},
        ],
    }
    return Response(json.dumps(m, ensure_ascii=False), mimetype='application/manifest+json',
                    headers={'Cache-Control': 'public, max-age=86400'})


@bp.route('/sw.js')
def service_worker():
    return Response(SW, mimetype='application/javascript',
                    headers={'Cache-Control': 'no-cache', 'Service-Worker-Allowed': '/'})


@bp.route('/hors-ligne')
def hors_ligne():
    return render_template('egalyx/hors_ligne.html')


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    app.register_blueprint(bp)
    publics = {'application_mobile.icone', 'application_mobile.manifeste', 'application_mobile.service_worker',
               'application_mobile.hors_ligne'}
    exempter_controle_ancien(app, publics)
    # pages libres : chargées par le navigateur avant / sans connexion, sans aucune donnée
    try:
        from egalyx import double_auth
        double_auth._LIBRES.update(publics)
    except Exception:  # noqa: BLE001
        pass
