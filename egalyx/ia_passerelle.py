"""
egalyx/ia_passerelle.py — passage obligé de TOUS les appels d'IA de l'outil.

Toutes les fonctions d'IA d'Egalyx (anciennes et nouvelles) passent par la bibliothèque openai
(client.chat.completions.create). Cette passerelle se place à cet endroit unique, dès le démarrage, et :
  1. envoie la demande au fournisseur choisi par le super admin :
       - OpenAI (États-Unis)              clé OPENAI_API_KEY,  modèle EGALYX_IA_MODELE (gpt-4o-mini par défaut)
       - Mistral AI (France, point d'accès européen api.eu.mistral.ai, traitement dans l'UE)
                                          clé MISTRAL_API_KEY, modèle EGALYX_IA_MODELE_MISTRAL (mistral-medium-latest)
     Si la clé du fournisseur choisi manque, l'autre est utilisé s'il a une clé ;
  2. masque les données sensibles avant l'envoi et les restitue dans la réponse (egalyx/ia_masque.py),
     sauf si le super admin a coupé le masquage ;
  3. trace chaque appel dans le journal de l'organisation (fournisseur, modèle, nombre de données masquées,
     fonction de l'outil) — jamais le contenu.
Les interrupteurs (plateforme, organisation, permission, fonction) restent dans egalyx/ia.py.
"""
import copy
import logging
import os
import threading

journal = logging.getLogger('egalyx.ia_passerelle')

FOURNISSEURS = {
    'openai': {'libelle': 'OpenAI', 'pays': 'États-Unis', 'cle': 'OPENAI_API_KEY', 'base_url': None,
               'modele_env': 'EGALYX_IA_MODELE', 'modele': 'gpt-4o-mini'},
    'mistral': {'libelle': 'Mistral AI', 'pays': 'France — traitement dans l’Union européenne', 'cle': 'MISTRAL_API_KEY',
                'base_url': 'https://api.eu.mistral.ai/v1', 'modele_env': 'EGALYX_IA_MODELE_MISTRAL',
                'modele': 'mistral-medium-latest'},
}
# Valeur posée dans OPENAI_API_KEY quand seul Mistral est configuré : les anciennes fonctions qui vérifient
# « une clé OpenAI existe » au démarrage restent actives, et la passerelle envoie tout à Mistral (jamais à OpenAI).
SUBSTITUT = 'sk-egalyx-passerelle-mistral-0000000000'
PARAMETRES_MISTRAL = {'messages', 'model', 'temperature', 'top_p', 'max_tokens', 'stream', 'response_format', 'tools',
                      'tool_choice', 'stop', 'presence_penalty', 'frequency_penalty', 'n', 'timeout', 'extra_headers',
                      'extra_body', 'extra_query', 'parallel_tool_calls'}
_local = threading.local()
_etat = {'installe': False, 'origine': None}


# ------------------------------------------------------------------ réglages
def _reglages():
    try:
        from egalyx.ia import reglages
        return reglages()
    except Exception:  # noqa: BLE001
        return {}


def cle(fournisseur):
    v = (os.environ.get(FOURNISSEURS[fournisseur]['cle']) or '').strip()
    if fournisseur == 'openai':
        return v if v.startswith('sk-') and len(v) >= 30 and v != SUBSTITUT else None
    return v if len(v) >= 20 else None


def choisi():
    f = _reglages().get('ia_fournisseur') or os.environ.get('EGALYX_IA_FOURNISSEUR') or 'openai'
    return f if f in FOURNISSEURS else 'openai'


def effectif():
    """Fournisseur réellement utilisé : le choix du super admin s'il a une clé, sinon l'autre s'il en a une."""
    c = choisi()
    if cle(c):
        return c
    autre = next((f for f in FOURNISSEURS if f != c and cle(f)), None)
    return autre


def modele(fournisseur=None):
    f = FOURNISSEURS[fournisseur or effectif() or choisi()]
    return (os.environ.get(f['modele_env']) or f['modele']).strip()


def masquage_actif():
    return _reglages().get('ia_masquage', True) is not False


def etat():
    """Pour la page du super admin."""
    return {'choisi': choisi(), 'effectif': effectif(), 'modele': modele() if effectif() else None,
            'cles': {f: bool(cle(f)) for f in FOURNISSEURS}, 'masquage': masquage_actif(), 'installe': _etat['installe']}


# ------------------------------------------------------------------ démarrage
def preparer_environnement():
    """Appelé à l'import d'egalyx (avant app.py) : seul Mistral configuré -> substitut de clé OpenAI."""
    if not os.environ.get('OPENAI_API_KEY') and cle('mistral'):
        os.environ['OPENAI_API_KEY'] = SUBSTITUT


def installer():
    """Se place devant client.chat.completions.create (une seule fois, pour tous les clients openai)."""
    if _etat['installe']:
        return True
    try:
        from openai.resources.chat.completions.completions import Completions
    except Exception:  # noqa: BLE001 — openai absent ou incomplet : aucune IA possible de toute façon
        try:
            from openai.resources.chat.completions import Completions
        except Exception:  # noqa: BLE001
            return False
    origine = Completions.create
    if getattr(origine, '_egalyx_passerelle', False):
        _etat['installe'] = True
        return True

    def create(self, *args, **kwargs):
        envoi = _etat['origine'] or origine          # _etat['origine'] : remplaçable par les recettes (faux fournisseur)
        if getattr(_local, 'dedans', False):
            return envoi(self, *args, **kwargs)
        return _appel(envoi, self, args, kwargs)
    create._egalyx_passerelle = True
    create.__wrapped__ = origine
    Completions.create = create
    _etat.update(installe=True, origine=origine)
    return True


# ------------------------------------------------------------------ appel
def _client(fournisseur, delai=None):
    from openai import OpenAI
    f = FOURNISSEURS[fournisseur]
    kw = {'api_key': cle(fournisseur), 'max_retries': 1}
    if f['base_url']:
        kw['base_url'] = f['base_url']
    if delai:
        kw['timeout'] = delai
    return OpenAI(**kw)


def _vers_mistral(kwargs):
    k = dict(kwargs)
    if 'max_completion_tokens' in k:
        k['max_tokens'] = k.pop('max_completion_tokens')
    k['model'] = modele('mistral')
    return {c: v for c, v in k.items() if c in PARAMETRES_MISTRAL}


def _organisation():
    try:
        from flask import has_request_context
        if not has_request_context():
            return None
        from egalyx.commun import client_id_courant
        return client_id_courant()
    except Exception:  # noqa: BLE001
        return None


def _masque(cid):
    try:
        from flask import g, has_request_context
        if has_request_context():
            cache = g.setdefault('_eg_masques', {})
            if cid not in cache:
                from egalyx.ia_masque import pour_organisation
                cache[cid] = pour_organisation(cid)
            return cache[cid]
    except Exception:  # noqa: BLE001
        pass
    from egalyx.ia_masque import pour_organisation
    return pour_organisation(cid)


def _restaurer_reponse(rep, masque):
    for ch in getattr(rep, 'choices', None) or []:
        msg = getattr(ch, 'message', None)
        if msg is None:
            continue
        if isinstance(getattr(msg, 'content', None), str):
            msg.content = masque.restaurer(msg.content)
        for tc in getattr(msg, 'tool_calls', None) or []:
            fn = getattr(tc, 'function', None)
            if fn is not None and isinstance(getattr(fn, 'arguments', None), str):
                fn.arguments = masque.restaurer(fn.arguments)
    return rep


def _tracer(cid, fournisseur, mod, nb_masques):
    try:
        from flask import has_request_context, request
        if not has_request_context() or not cid:
            return
        from egalyx.commun import journaliser
        journaliser('ia_appel', {'fournisseur': fournisseur, 'modele': mod, 'donnees_masquees': nb_masques,
                                 'fonction': request.endpoint or request.path}, client_id=cid)
    except Exception:  # noqa: BLE001
        pass


def _appel(origine, completions, args, kwargs):
    fournisseur = effectif()
    if fournisseur is None:                       # aucune clé : comportement d'origine (erreur → repli sans IA)
        return origine(completions, *args, **kwargs)
    kwargs = dict(kwargs)
    cid = _organisation()
    masque = None
    if masquage_actif() and kwargs.get('messages'):
        masque = _masque(cid)
        masque = copy.copy(masque)                # repères propres à cet appel, noms connus partagés
        masque.original, masque._repere, masque._compte = {}, {}, {}
        kwargs['messages'] = masque.messages(kwargs['messages'])
    delai = getattr(getattr(completions, '_client', None), 'timeout', None)
    if fournisseur == 'mistral':
        kwargs = _vers_mistral(kwargs)
        cible = _client('mistral', delai if isinstance(delai, (int, float)) else None).chat.completions
    else:
        actuelle = getattr(getattr(completions, '_client', None), 'api_key', None)
        base = str(getattr(getattr(completions, '_client', None), 'base_url', '') or '')
        if actuelle != cle('openai') or 'api.openai.com' not in base:
            cible = _client('openai', delai if isinstance(delai, (int, float)) else None).chat.completions
        else:
            cible = completions
        kwargs.setdefault('model', modele('openai'))
    _local.dedans = True
    try:
        rep = origine(cible, *args, **kwargs)
    finally:
        _local.dedans = False
    if masque is not None and masque.nombre and not kwargs.get('stream'):
        _restaurer_reponse(rep, masque)
    _tracer(cid, fournisseur, kwargs.get('model'), masque.nombre if masque else 0)
    return rep
