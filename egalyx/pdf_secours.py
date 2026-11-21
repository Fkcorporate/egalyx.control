"""
egalyx/pdf_secours.py — exports PDF quand WeasyPrint n'est pas installé sur le serveur.

Une dizaine d'exports (rapport d'audit « élégant », audit qualité, fiches risque, KRI…) produisent leur PDF avec
WeasyPrint, absent de requirements.txt (il demande des bibliothèques système). Sans lui, certains exports
tombaient en erreur 500. Ici, si WeasyPrint manque, on installe un remplaçant minimal : le document HTML préparé
pour le PDF est affiché tel quel, avec un bandeau « Imprimer / Enregistrer en PDF » (le navigateur fait le PDF).
Si WeasyPrint est installé, ce module ne fait rien.
Certaines pages attrapent toutes les erreurs (« except Exception ») et renvoient vers une autre page avec un message
d'échec : le document préparé est alors gardé pour la requête (g) et affiché quand même, sans ce message.
"""
import importlib.util
import sys
import types

from flask import Response, g, has_request_context, session

BANDEAU = """<div id="eg-pdf-secours" style="position:sticky;top:0;z-index:9999;display:flex;gap:12px;align-items:center;
padding:10px 16px;background:#FFF7E6;border-bottom:1px solid #F5D9A8;font:14px/1.4 Inter,system-ui,sans-serif;color:#14202E">
<span>Le PDF se fait avec votre navigateur sur ce serveur : cliquez sur <b>Imprimer</b>, puis choisissez
<b>« Enregistrer au format PDF »</b>.</span>
<button onclick="window.print()" style="margin-left:auto;padding:6px 14px;border-radius:6px;border:1px solid #0B5FD3;
background:#0B5FD3;color:#fff;font-weight:500;cursor:pointer">Imprimer / Enregistrer en PDF</button>
<button onclick="history.back()" style="padding:6px 14px;border-radius:6px;border:1px solid #C9D2DD;background:#fff;
color:#14202E;cursor:pointer">Retour</button></div>
<style media="print">#eg-pdf-secours{display:none!important}</style>"""


class PdfIndisponible(Exception):
    """Levée par le remplaçant au moment d'écrire le PDF ; porte le HTML du document."""

    def __init__(self, html):
        super().__init__('WeasyPrint absent')
        self.html = html or ''


class _HTML:
    def __init__(self, string=None, filename=None, url=None, base_url=None, **_):
        self.html = string
        if self.html is None and filename:
            try:
                with open(filename, encoding='utf-8') as f:
                    self.html = f.read()
            except OSError:
                self.html = ''

    def _lever(self):
        if has_request_context():
            g._egalyx_pdf_secours = (self.html, len(session.get('_flashes') or []))
        raise PdfIndisponible(self.html)

    def write_pdf(self, *a, **k):
        self._lever()

    def render(self, *a, **k):
        self._lever()


class _Neutre:
    def __init__(self, *a, **k):
        pass


def _module_remplacant():
    m = types.ModuleType('weasyprint')
    m.HTML, m.CSS, m.__egalyx_remplacant__ = _HTML, _Neutre, True
    texte = types.ModuleType('weasyprint.text')
    polices = types.ModuleType('weasyprint.text.fonts')
    polices.FontConfiguration = _Neutre
    texte.fonts = polices
    m.text = texte
    return {'weasyprint': m, 'weasyprint.text': texte, 'weasyprint.text.fonts': polices}


def page_imprimable(e):
    html = e.html or '<p>Document vide.</p>'
    if '<body' in html:
        debut = html.index('<body')
        fin = html.index('>', debut) + 1
        html = html[:fin] + BANDEAU + html[fin:]
    else:
        html = BANDEAU + html
    return Response(html, mimetype='text/html')


def enregistrer(app):
    try:
        present = importlib.util.find_spec('weasyprint') is not None
    except (ImportError, ValueError):
        present = False
    if present:
        return
    for nom, module in _module_remplacant().items():
        sys.modules.setdefault(nom, module)
    app.register_error_handler(PdfIndisponible, page_imprimable)

    @app.after_request
    def _pdf_secours_rattrape(reponse):
        """La page a avalé l'erreur (redirection ou erreur) : on montre quand même le document à imprimer."""
        en_attente = g.pop('_egalyx_pdf_secours', None)
        if en_attente is None or not (300 <= reponse.status_code < 400 or reponse.status_code >= 500):
            return reponse
        html, nb_messages = en_attente
        messages = session.get('_flashes') or []
        if len(messages) > nb_messages:
            session['_flashes'] = messages[:nb_messages]
        return page_imprimable(PdfIndisponible(html))
