"""
egalyx/masquage.py — ce qui n'est pas disponible n'apparaît nulle part.

Sur chaque page HTML servie à un utilisateur connecté (hors super admin), avant l'envoi :
  - les liens (<a>), boutons de navigation et formulaires qui mènent vers une fonction NON DISPONIBLE sont retirés :
      * module non souscrit par l'organisation ;
      * aucune permission de l'utilisateur sur ce module ;
      * intelligence artificielle désactivée (plateforme, organisation ou permission) ;
  - les lignes cliquables (data-href) vers ces fonctions perdent leur lien ;
  - côté navigateur, les blocs (cartes) dont le titre désigne un module indisponible sont masqués
    (ex. « Indicateurs de risque (KRI) » sur la fiche d'un risque quand le module KRI n'est pas souscrit).
Les adresses restent de toute façon bloquées côté serveur : ce filtre évite d'afficher des liens morts.
Désactivation d'urgence : EGALYX_MASQUAGE=0.
"""
import json
import os
import re
from functools import lru_cache

from flask import request
from flask_login import current_user

A_RE = re.compile(r'<a\b([^>]*)>(.*?)</a\s*>', re.S | re.I)
FORM_RE = re.compile(r'<form\b([^>]*)>(.*?)</form\s*>', re.S | re.I)
BOUTON_RE = re.compile(r'<button\b([^>]*)>(.*?)</button\s*>', re.S | re.I)
ATTR_RE = lambda nom: re.compile(r'\b' + nom + r'\s*=\s*("([^"]*)"|\'([^\']*)\')', re.I)
HREF, ACTION, METHOD, CLASSE, ONCLICK, DATAHREF = (ATTR_RE('href'), ATTR_RE('action'), ATTR_RE('method'), ATTR_RE('class'),
                                                   ATTR_RE('onclick'), ATTR_RE('data-href'))
LOC_RE = re.compile(r"""location(?:\.href)?\s*=\s*['"`](/[^'"`]*)""")
LI_VIDE = re.compile(r'<li\b[^>]*>\s*</li\s*>', re.I)
CLASSES_ELEMENT = re.compile(r'\b(btn|nav-link|dropdown-item|list-group-item|card-link|pg-ref|ds-ref|badge)\b')

# Titres de blocs qui désignent un module (masquage des cartes côté navigateur)
TITRES_MODULES = {
    'kri': r"\bKRI\b|indicateurs? (cl[ée]s? )?de risques?",
    'incidents': r"\bincidents?\b",
    'pca': r"\bPCA\b|continuit[ée] d.activit[ée]",
    'veille': r"veille r[ée]glementaire",
    'processus': r"logigrammes?",
    'campagnes': r"campagnes? de contr[ôo]le",
    'controle_n2': r"contr[ôo]le interne (de )?(N2|niveau 2|2e niveau)|\bC2N\b",
    'qualite': r"plans? qualit[ée]|audits? qualit[ée]",
    'questionnaires': r"\bquestionnaires?\b",
    'tiers': r"\btiers\b|LCB-?FT",
    'alertes': r"dispositif d.alerte|lanceurs? d.alerte",
    'plans_action': r"plans? d.action",
    'recommandations': r"registre des recommandations",
    'programme_audit': r"programme d.audit",
    'pilotage': r"tableau de bord strat[ée]gique|rapport au comit[ée]",
}



def _avant_fin_body(html, ajout):
    """Insère avant le DERNIER </body> : le premier peut se trouver dans une chaîne JavaScript
    (fenêtre d'impression…), et y insérer un <script> casse le script de la page."""
    i = html.rfind('</body>')
    return html if i < 0 else html[:i] + ajout + html[i:]

def _actif():
    return os.environ.get('EGALYX_MASQUAGE', '1') == '1'


@lru_cache(maxsize=4096)
def _cible(chemin, methode):
    """(endpoint, module, vise_un_objet) d'une adresse de l'application, ou (None, None, False)."""
    from flask import current_app
    from egalyx.modules_client import module_de_la_requete
    try:
        adaptateur = current_app.url_map.bind('localhost')
        endpoint, args = adaptateur.match(chemin, method=methode)
    except Exception:
        return None, None, False
    try:
        return endpoint, module_de_la_requete(endpoint, chemin), bool(args)
    except Exception:
        return endpoint, None, bool(args)


class Contexte:
    """Ce que l'utilisateur courant peut voir (calculé une fois par page)."""

    def __init__(self):
        from egalyx.modules_client import MODULES, modules_du_client
        from egalyx import ia
        self.operateur = bool(getattr(current_user, 'is_operateur', False))
        try:
            self.actifs = modules_du_client(getattr(current_user, 'client', None))
        except Exception:
            self.actifs = None
        self.ia = ia.ia_autorisee()
        self.endpoints_ia = ia.ENDPOINTS_IA
        self.motifs_ia = ia.MOTIFS_ADRESSES
        self.MODULES = MODULES
        self._droits = {}

    def module_visible(self, code):
        if code is None:
            return True
        if code == 'ia':
            return self.ia
        if self.actifs is not None and code not in self.actifs:
            return False
        if self.operateur:            # les opérateurs ont leurs propres droits (pages operateur_…)
            return True
        if code not in self._droits:
            perms = self.MODULES.get(code, (None,) * 5)[4] or ()
            try:
                self._droits[code] = any(current_user.has_permission(p) for p in perms) if perms else True
            except Exception:
                self._droits[code] = True
        return self._droits[code]

    def adresse_visible(self, url, methode='GET'):
        if not url:
            return True
        u = url.strip()
        if u.startswith(('http://', 'https://')):
            hote = request.host_url.rstrip('/')
            if not u.startswith(hote):
                return True
            u = u[len(hote):]
        if not u.startswith('/') or u.startswith('//') or u.startswith('/static/'):
            return True
        chemin = u.split('#', 1)[0].split('?', 1)[0] or '/'
        if not self.ia and any(m in chemin.lower() for m in self.motifs_ia):
            return False
        endpoint, module, objet = _cible(chemin, methode)
        if endpoint in self.endpoints_ia and not self.ia:
            return False
        if module is None:
            return True
        if self.actifs is not None and module not in self.actifs:
            return False                  # module non souscrit : jamais visible
        if self.operateur or (objet and methode == 'GET'):
            # Lien vers UN élément précis (son plan d'action, sa recommandation…) : la personne qui en a la charge
            # y a accès même sans la permission du module ; la page elle-même vérifie les droits.
            return True
        return self.module_visible(module)

    def modules_caches(self):
        codes = [c for c in TITRES_MODULES if not self.module_visible(c)]
        if not self.ia:
            codes.append('ia')
        return codes


def _attr(rx, attrs):
    m = rx.search(attrs)
    return (m.group(2) if m.group(2) is not None else m.group(3)) if m else None


def filtrer_html(html, ctx):
    def lien(m):
        attrs, corps = m.group(1), m.group(2)
        href = _attr(HREF, attrs)
        if href is None or ctx.adresse_visible(href):
            return m.group(0)
        classes = _attr(CLASSE, attrs) or ''
        if CLASSES_ELEMENT.search(classes) or not re.sub(r'<[^>]+>', '', corps).strip():
            return ''                     # bouton, entrée de menu, icône : retiré
        return f'<span>{corps}</span>'    # lien dans une phrase : le texte reste, le lien disparaît

    def formulaire(m):
        attrs = m.group(1)
        if len(m.group(0)) > 6000:        # formulaire englobant une page entière : on n'y touche pas
            return m.group(0)
        action = _attr(ACTION, attrs)
        methode = (_attr(METHOD, attrs) or 'GET').upper()
        if action and not ctx.adresse_visible(action, 'POST' if methode == 'POST' else 'GET'):
            return ''
        return m.group(0)

    def bouton(m):
        attrs = m.group(1)
        onclick = _attr(ONCLICK, attrs) or ''
        cible = LOC_RE.search(onclick)
        if cible and not ctx.adresse_visible(cible.group(1)):
            return ''
        return m.group(0)

    def ligne_cliquable(m):
        valeur = m.group(2) if m.group(2) is not None else m.group(3)
        return m.group(0) if ctx.adresse_visible(valeur) else ''

    html = A_RE.sub(lien, html)
    html = FORM_RE.sub(formulaire, html)
    html = BOUTON_RE.sub(bouton, html)
    html = DATAHREF.sub(ligne_cliquable, html)
    html = LI_VIDE.sub('', html)
    return html


def _script_blocs(codes):
    motifs = [TITRES_MODULES[c] for c in codes if c in TITRES_MODULES]
    if 'ia' in codes:
        motifs.append(r"(^|[\s(«])(IA|AI)([\s)»:.,!]|$)|intelligence artificielle|analyse ia|ia[- ]ultra")
    if not motifs:
        return ''
    return """
<script>/* egalyx/masquage.py : blocs des modules indisponibles */
(function () {
  var RX = new RegExp(%s, 'i');
  var BLOCS = '.card, .fk-card, .section-card, .pg-carte, .ds-carte, .stat-card, .widget, .info-card, .kpi-card';
  var TITRES = 'h1, h2, h3, h4, h5, h6, .card-header, .card-title, .section-title, .pg-carte-titre, .ds-carte-titre, .fk-card-header';
  function masquer(racine) {
    if (!racine.querySelectorAll) return;
    racine.querySelectorAll(TITRES).forEach(function (t) {
      var txt = (t.textContent || '').trim();
      if (!txt || txt.length > 120 || !RX.test(txt)) return;
      if (t.closest('#egChat, .ad-cat, .ad-ligne, .sidebar, nav, [data-sans-masquage], form')) return;
      var bloc = t.closest(BLOCS);
      if (!bloc || bloc === document.body) return;
      // Le titre doit être CELUI du bloc (son premier titre), et le bloc ne doit pas être un conteneur de page :
      // pas de formulaire, pas d'autres blocs ni d'autres titres à l'intérieur.
      if (bloc.querySelector(TITRES) !== t) return;
      if (bloc.querySelector('form, input, select, textarea')) return;
      if (bloc.querySelector(BLOCS)) return;
      if (bloc.querySelectorAll(TITRES).length > 3) return;
      bloc.style.display = 'none';
    });
  }
  masquer(document);
  new MutationObserver(function (ms) { ms.forEach(function (m) { m.addedNodes.forEach(function (n) { if (n.nodeType === 1) masquer(n); }); }); })
    .observe(document.body, { childList: true, subtree: true });
})();
</script>""" % json.dumps('|'.join('(' + m + ')' for m in motifs))


def _apres_requete(reponse):
    if not _actif():
        return reponse
    try:
        if (reponse.mimetype != 'text/html' or reponse.direct_passthrough or reponse.is_streamed
                or reponse.status_code != 200 or request.path.startswith('/static/')):
            return reponse
        if not getattr(current_user, 'is_authenticated', False) or getattr(current_user, 'role', None) == 'super_admin':
            return reponse
        ctx = Contexte()
        html = reponse.get_data(as_text=True)
        nouveau = filtrer_html(html, ctx)
        # Pages d'administration (permissions, modules, paramètres) et centre d'aide : elles PARLENT des modules,
        # leurs titres ne doivent jamais être pris pour des blocs à masquer.
        admin = request.path.startswith(('/client-admin', '/super-admin', '/admin', '/aide', '/parametres', '/compte'))
        script = '' if admin else _script_blocs(ctx.modules_caches())
        if script and '</body>' in nouveau:
            nouveau = _avant_fin_body(nouveau, script)
        if nouveau != html:
            reponse.set_data(nouveau)
    except Exception as e:                    # ne jamais casser une page à cause du masquage
        from flask import current_app
        current_app.logger.warning('Masquage : %s', e)
    return reponse


def enregistrer(app):
    app.after_request(_apres_requete)
