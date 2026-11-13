"""
egalyx/compression.py — pages compressées (gzip) avant l'envoi au navigateur.

Exemple mesuré : fiche d'une cartographie de 80 risques, 1 606 Ko → 65 Ko (10 ms de calcul).
Appliqué tout à la fin (intergiciel WSGI, après tous les traitements Flask), seulement si :
  - le navigateur accepte gzip ;
  - la réponse est du texte (HTML, JSON, CSS, JavaScript, SVG) de plus de 2 Ko ;
  - elle n'est pas déjà compressée, ni un flux continu (text/event-stream), ni un téléchargement.
Désactivable avec la variable d'environnement EGALYX_COMPRESSION=0.
"""
import gzip
import os

TYPES = ('text/html', 'application/json', 'text/css', 'application/javascript', 'text/javascript', 'image/svg+xml',
         'application/manifest+json', 'text/plain', 'text/csv')
MINIMUM = 2048


class Compression:
    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        if 'gzip' not in environ.get('HTTP_ACCEPT_ENCODING', '').lower() or environ.get('REQUEST_METHOD') == 'HEAD':
            return self.application(environ, start_response)
        etat = {}

        def debut(statut, entetes, exc_info=None):
            etat['statut'], etat['entetes'], etat['exc'] = statut, entetes, exc_info
            h = {k.lower(): v for k, v in entetes}
            type_ = h.get('content-type', '').split(';')[0].strip().lower()
            etat['compresser'] = (type_ in TYPES and 'content-encoding' not in h
                                  and 'attachment' not in h.get('content-disposition', '').lower()
                                  and statut[:3] not in ('204', '206', '304'))
            if not etat['compresser']:
                return start_response(statut, entetes, exc_info)
            return lambda _donnees: None                           # write() historique : non utilisé par Flask

        corps = self.application(environ, debut)
        if not etat.get('compresser'):
            return corps
        try:
            donnees = b''.join(corps)
        finally:
            if hasattr(corps, 'close'):
                corps.close()
        entetes = [(k, v) for k, v in etat['entetes'] if k.lower() != 'content-length']
        if len(donnees) >= MINIMUM:
            donnees = gzip.compress(donnees, 6)
            entetes.append(('Content-Encoding', 'gzip'))
            vary = [v for k, v in entetes if k.lower() == 'vary']
            entetes = [(k, v) for k, v in entetes if k.lower() != 'vary']
            entetes.append(('Vary', ', '.join(vary + ['Accept-Encoding']) if vary else 'Accept-Encoding'))
        entetes.append(('Content-Length', str(len(donnees))))
        start_response(etat['statut'], entetes, etat['exc'])
        return [donnees]


def enregistrer(app):
    if os.environ.get('EGALYX_COMPRESSION', '1') == '0' or getattr(app.wsgi_app, '_egalyx_compression', False):
        return False
    app.wsgi_app = Compression(app.wsgi_app)
    app.wsgi_app._egalyx_compression = True
    return True
