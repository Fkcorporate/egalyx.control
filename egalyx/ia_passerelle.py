"""
egalyx/ia_passerelle.py — passage obligé de TOUS les appels d'IA de l'outil.

Toutes les fonctions d'IA d'Egalyx (anciennes et nouvelles) passent par la bibliothèque openai
(client.chat.completions.create). Cette passerelle se place à cet endroit unique, dès le démarrage, et :
  1. envoie la demande au fournisseur choisi par le super admin :
       - OpenAI (États-Unis)              OPENAI_API_KEY      modèle EGALYX_IA_MODELE            (gpt-4o-mini)
       - Anthropic, Claude (États-Unis)   ANTHROPIC_API_KEY   modèle EGALYX_IA_MODELE_ANTHROPIC  (claude-sonnet-5-5)
         API native « Messages » (la couche compatible OpenAI d'Anthropic est prévue pour des essais) :
         la passerelle traduit la demande (messages, outils, JSON) et la réponse ;
       - Mistral AI (France, point d'accès européen api.eu.mistral.ai, traitement dans l'UE)
                                          MISTRAL_API_KEY     modèle EGALYX_IA_MODELE_MISTRAL    (mistral-medium-latest)
       - DeepSeek (Chine : données stockées en Chine selon sa politique de confidentialité)
                                          DEEPSEEK_API_KEY    modèle EGALYX_IA_MODELE_DEEPSEEK   (deepseek-flash)
     Si la clé du fournisseur choisi manque, un autre fournisseur ayant une clé est utilisé — jamais DeepSeek,
     qui n'est utilisé que s'il est choisi explicitement ;
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
               'modele_env': 'EGALYX_IA_MODELE', 'modele': 'gpt-4o-mini', 'mode': 'openai'},
    'anthropic': {'libelle': 'Anthropic (Claude)', 'pays': 'États-Unis', 'cle': 'ANTHROPIC_API_KEY',
                  'base_url': 'https://api.anthropic.com', 'modele_env': 'EGALYX_IA_MODELE_ANTHROPIC',
                  'modele': 'claude-sonnet-5-5', 'mode': 'anthropic'},
    'mistral': {'libelle': 'Mistral AI', 'pays': 'France — traitement dans l’Union européenne', 'cle': 'MISTRAL_API_KEY',
                'base_url': 'https://api.eu.mistral.ai/v1', 'modele_env': 'EGALYX_IA_MODELE_MISTRAL',
                'modele': 'mistral-medium-latest', 'mode': 'compatible'},
    'deepseek': {'libelle': 'DeepSeek', 'pays': 'Chine — données stockées en Chine', 'cle': 'DEEPSEEK_API_KEY',
                 'base_url': 'https://api.deepseek.com', 'modele_env': 'EGALYX_IA_MODELE_DEEPSEEK',
                 'modele': 'deepseek-flash', 'mode': 'compatible'},
}
# Fournisseurs de secours (clé du fournisseur choisi absente), dans cet ordre ; DeepSeek n'y figure pas.
SECOURS = ('mistral', 'openai', 'anthropic')
# Valeur posée dans OPENAI_API_KEY quand seul un autre fournisseur est configuré : les anciennes fonctions qui
# vérifient « une clé OpenAI existe » au démarrage restent actives, et la passerelle envoie tout au fournisseur
# choisi (jamais à OpenAI).
SUBSTITUT = 'sk-egalyx-passerelle-mistral-0000000000'
PARAMETRES_COMPATIBLES = {'messages', 'model', 'temperature', 'top_p', 'max_tokens', 'stream', 'response_format', 'tools',
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
    return v if len(v) >= 20 and v != SUBSTITUT else None


def choisi():
    f = _reglages().get('ia_fournisseur') or os.environ.get('EGALYX_IA_FOURNISSEUR') or 'openai'
    return f if f in FOURNISSEURS else 'openai'


def effectif():
    """Fournisseur réellement utilisé : le choix du super admin s'il a une clé, sinon l'autre s'il en a une."""
    c = choisi()
    if cle(c):
        return c
    return next((f for f in SECOURS if f != c and cle(f)), None)


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
    """Appelé à l'import d'egalyx (avant app.py) : pas de clé OpenAI mais un autre fournisseur -> substitut."""
    if not os.environ.get('OPENAI_API_KEY') and any(cle(f) for f in FOURNISSEURS if f != 'openai'):
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


def _vers_compatible(kwargs, fournisseur):
    """Fournisseurs à l'API compatible OpenAI (Mistral, DeepSeek) : modèle du fournisseur, paramètres reconnus."""
    k = dict(kwargs)
    if 'max_completion_tokens' in k:
        k['max_tokens'] = k.pop('max_completion_tokens')
    k['model'] = modele(fournisseur)
    return {c: v for c, v in k.items() if c in PARAMETRES_COMPATIBLES}


def _vers_mistral(kwargs):                      # compatibilité (tests, appels existants)
    return _vers_compatible(kwargs, 'mistral')


# ------------------------------------------------------------------ Anthropic (API native « Messages »)
ANTHROPIC_VERSION = '2023-06-01'
ANTHROPIC_MARGE_REFLEXION = 4000     # les modèles Claude 5 réfléchissent par défaut : jetons comptés dans max_tokens
CONSIGNE_JSON = "Réponds uniquement par un objet JSON valide, sans texte avant ou après, sans bloc de code."


def _texte_contenu(c):
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return '\n'.join(p.get('text', '') for p in c if isinstance(p, dict) and p.get('type') == 'text')
    return '' if c is None else str(c)


def _bloc_image(p):
    url = ((p.get('image_url') or {}).get('url') or '') if isinstance(p.get('image_url'), dict) else str(p.get('image_url') or '')
    if url.startswith('data:') and ';base64,' in url:
        media, donnees = url[5:].split(';base64,', 1)
        return {'type': 'image', 'source': {'type': 'base64', 'media_type': media, 'data': donnees}}
    if url.startswith('http'):
        return {'type': 'image', 'source': {'type': 'url', 'url': url}}
    return None


def vers_anthropic(kwargs):
    """Demande au format chat OpenAI -> corps de requête de l'API Messages d'Anthropic."""
    import json
    systeme, messages = [], []

    def ajouter(role, blocs):
        if not blocs:
            return
        if messages and messages[-1]['role'] == role:
            messages[-1]['content'].extend(blocs)
        else:
            messages.append({'role': role, 'content': list(blocs)})

    for m in kwargs.get('messages') or []:
        role = m.get('role')
        if role in ('system', 'developer'):
            t = _texte_contenu(m.get('content'))
            if t:
                systeme.append(t)
        elif role == 'user':
            c = m.get('content')
            if isinstance(c, list):
                blocs = []
                for p in c:
                    if isinstance(p, dict) and p.get('type') == 'text' and p.get('text'):
                        blocs.append({'type': 'text', 'text': p['text']})
                    elif isinstance(p, dict) and p.get('type') == 'image_url':
                        b = _bloc_image(p)
                        if b:
                            blocs.append(b)
            else:
                blocs = [{'type': 'text', 'text': c}] if c else []
            ajouter('user', blocs)
        elif role == 'assistant':
            blocs = []
            t = _texte_contenu(m.get('content'))
            if t:
                blocs.append({'type': 'text', 'text': t})
            for tc in m.get('tool_calls') or []:
                fn = tc.get('function') or {}
                try:
                    entree = json.loads(fn.get('arguments') or '{}')
                except (TypeError, ValueError):
                    entree = {}
                blocs.append({'type': 'tool_use', 'id': tc.get('id'), 'name': fn.get('name'), 'input': entree if isinstance(entree, dict) else {}})
            ajouter('assistant', blocs)
        elif role == 'tool':
            ajouter('user', [{'type': 'tool_result', 'tool_use_id': m.get('tool_call_id'), 'content': _texte_contenu(m.get('content')) or '(vide)'}])
    if not messages or messages[0]['role'] != 'user':
        messages.insert(0, {'role': 'user', 'content': [{'type': 'text', 'text': '(début de la conversation)'}]})
    rf = kwargs.get('response_format') or {}
    if isinstance(rf, dict) and rf.get('type') in ('json_object', 'json_schema'):
        systeme.append(CONSIGNE_JSON)
    demande = int(kwargs.get('max_completion_tokens') or kwargs.get('max_tokens') or 1024)
    corps = {'model': modele('anthropic'), 'max_tokens': min(64000, demande + ANTHROPIC_MARGE_REFLEXION), 'messages': messages}
    if systeme:
        corps['system'] = '\n\n'.join(systeme)
    if kwargs.get('temperature') is not None:
        corps['temperature'] = kwargs['temperature']
    outils = []
    for t in kwargs.get('tools') or []:
        fn = t.get('function') if isinstance(t, dict) else None
        if fn and fn.get('name'):
            outils.append({'name': fn['name'], 'description': fn.get('description') or '',
                           'input_schema': fn.get('parameters') or {'type': 'object', 'properties': {}}})
    if outils:
        corps['tools'] = outils
        tc = kwargs.get('tool_choice')
        if tc == 'none':
            corps['tool_choice'] = {'type': 'none'}
        elif tc == 'required':
            corps['tool_choice'] = {'type': 'any'}
        elif isinstance(tc, dict) and (tc.get('function') or {}).get('name'):
            corps['tool_choice'] = {'type': 'tool', 'name': tc['function']['name']}
    if kwargs.get('stop'):
        corps['stop_sequences'] = [kwargs['stop']] if isinstance(kwargs['stop'], str) else list(kwargs['stop'])
    return corps


def _json_seul(t):
    """Retire un éventuel bloc de code ou texte autour d'un objet JSON."""
    t = (t or '').strip()
    if t.startswith('```'):
        t = t.strip('`')
        t = t[4:] if t.lower().startswith('json') else t
    debut, fin = t.find('{'), t.rfind('}')
    return t[debut:fin + 1] if debut != -1 and fin > debut else t


def depuis_anthropic(donnees, json_attendu=False):
    """Réponse de l'API Messages -> objet au format de la bibliothèque openai (choices[0].message…)."""
    import json
    from types import SimpleNamespace as NS
    textes, appels = [], []
    for b in donnees.get('content') or []:
        if b.get('type') == 'text':
            textes.append(b.get('text') or '')
        elif b.get('type') == 'tool_use':
            appels.append(NS(id=b.get('id'), type='function',
                             function=NS(name=b.get('name'), arguments=json.dumps(b.get('input') or {}, ensure_ascii=False))))
    texte = ''.join(textes)
    if json_attendu and not appels:
        texte = _json_seul(texte)
    fin = {'end_turn': 'stop', 'stop_sequence': 'stop', 'max_tokens': 'length', 'tool_use': 'tool_calls'}.get(donnees.get('stop_reason'), 'stop')
    u = donnees.get('usage') or {}
    return NS(id=donnees.get('id'), model=donnees.get('model'), object='chat.completion',
              choices=[NS(index=0, finish_reason=fin, message=NS(role='assistant', content=texte or None, tool_calls=appels or None))],
              usage=NS(prompt_tokens=u.get('input_tokens'), completion_tokens=u.get('output_tokens'),
                       total_tokens=(u.get('input_tokens') or 0) + (u.get('output_tokens') or 0)))


def _envoyer_anthropic(corps, delai=None):
    """Appel HTTP de l'API Messages (remplaçable par les recettes via _etat['anthropic'])."""
    if _etat.get('anthropic'):
        return _etat['anthropic'](corps)
    import httpx
    r = httpx.post(FOURNISSEURS['anthropic']['base_url'] + '/v1/messages', json=corps, timeout=delai or 90,
                   headers={'x-api-key': cle('anthropic'), 'anthropic-version': ANTHROPIC_VERSION, 'content-type': 'application/json'})
    if r.status_code >= 400:
        raise RuntimeError(f'Anthropic {r.status_code} : {r.text[:300]}')
    return r.json()


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
    delai_s = delai if isinstance(delai, (int, float)) else None
    if fournisseur == 'anthropic':
        if kwargs.get('stream'):
            raise RuntimeError("Réponse en flux non prise en charge avec Anthropic dans la passerelle")
        corps = vers_anthropic(kwargs)
        rf = kwargs.get('response_format') or {}
        rep = depuis_anthropic(_envoyer_anthropic(corps, delai_s),
                               json_attendu=isinstance(rf, dict) and rf.get('type') in ('json_object', 'json_schema'))
        if masque is not None and masque.nombre:
            _restaurer_reponse(rep, masque)
        _tracer(cid, fournisseur, corps['model'], masque.nombre if masque else 0)
        return rep
    if FOURNISSEURS[fournisseur]['mode'] == 'compatible':
        kwargs = _vers_compatible(kwargs, fournisseur)
        cible = _client(fournisseur, delai_s).chat.completions
    else:
        actuelle = getattr(getattr(completions, '_client', None), 'api_key', None)
        base = str(getattr(getattr(completions, '_client', None), 'base_url', '') or '')
        if actuelle != cle('openai') or 'api.openai.com' not in base:
            cible = _client('openai', delai_s).chat.completions
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
