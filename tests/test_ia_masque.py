"""Masquage des données avant envoi à l'IA, et choix du fournisseur (sans base de données, sans réseau)."""
from egalyx import ia_passerelle as P
from egalyx.ia_masque import NOTE_IA, Masque


def test_masque_et_restitue():
    m = Masque(['Awa', 'Koné', 'Awa Koné', 'awa.kone'], 'Banque Horizon')
    t = ("Selon M. Traoré, awa.kone a validé 12 500 000 FCFA le 03/10/2026 sur le compte 0123456789012 "
         "(IBAN CI93 CI00 0101 0012 3456 7890 1234) ; awa.kone@horizon.ci, +225 07 08 09 10 11. Mme Kouassi Aya, Banque Horizon.")
    s = m.texte(t)
    for secret in ('Traoré', 'awa.kone', '0123456789012', 'CI93', 'horizon.ci', '07 08 09 10 11', 'Kouassi', 'Banque Horizon'):
        assert secret not in s, secret
    assert '12 500 000 FCFA' in s and '03/10/2026' in s            # montants et dates gardés
    assert m.restaurer(s) == t


def test_memes_donnees_meme_repere_et_structures():
    m = Masque(['Yao'])
    o = m.objet({'a': 'Yao signe', 'b': ['yao relit', 3], 'c': None})
    assert o['a'].split()[0] == o['b'][0].split()[0] == '[PERSONNE_1]'
    assert o['b'][1] == 3 and o['c'] is None
    assert m.restaurer(o) == {'a': 'Yao signe', 'b': ['Yao relit', 3], 'c': None}   # même personne : graphie de la 1re mention


def test_mots_courants_jamais_masques():
    m = Masque(['Martin', 'Audit', 'Grace', 'Ab'])
    assert m.texte("Le service audit et Martin") == "Le service audit et Martin"


def test_messages_note_ajoutee_seulement_si_masquage():
    m = Masque(['Yao'])
    msgs = m.messages([{'role': 'system', 'content': 'Consigne'}, {'role': 'user', 'content': 'Yao a signé'}])
    assert NOTE_IA in msgs[0]['content'] and '[PERSONNE_1]' in msgs[1]['content']
    m2 = Masque(['Yao'])
    msgs2 = m2.messages([{'role': 'user', 'content': 'Rien de sensible'}])
    assert len(msgs2) == 1 and msgs2[0]['content'] == 'Rien de sensible'
    m3 = Masque(['Yao'])
    msgs3 = m3.messages([{'role': 'user', 'content': [{'type': 'text', 'text': 'Yao'}, {'type': 'image_url', 'image_url': {'url': 'x'}}]}])
    assert msgs3[0]['role'] == 'system' and msgs3[1]['content'][0]['text'] == '[PERSONNE_1]'


def test_fournisseur_effectif(monkeypatch):
    monkeypatch.setattr(P, '_reglages', lambda: {'ia_fournisseur': 'mistral'})
    monkeypatch.delenv('MISTRAL_API_KEY', raising=False)
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-' + 'a' * 40)
    assert P.choisi() == 'mistral' and P.effectif() == 'openai'      # pas de clé Mistral : OpenAI
    monkeypatch.setenv('MISTRAL_API_KEY', 'm' * 32)
    assert P.effectif() == 'mistral' and P.modele() == 'mistral-medium-latest'
    monkeypatch.setenv('OPENAI_API_KEY', P.SUBSTITUT)
    monkeypatch.setattr(P, '_reglages', lambda: {'ia_fournisseur': 'openai'})
    assert P.cle('openai') is None and P.effectif() == 'mistral'     # le substitut n'est jamais une vraie clé OpenAI
    monkeypatch.delenv('MISTRAL_API_KEY')
    assert P.effectif() is None


def test_parametres_traduits_pour_mistral(monkeypatch):
    monkeypatch.delenv('EGALYX_IA_MODELE_MISTRAL', raising=False)
    k = P._vers_mistral({'model': 'gpt-4o-mini', 'messages': [], 'max_completion_tokens': 900, 'store': True, 'response_format': {'type': 'json_object'}})
    assert k == {'model': 'mistral-medium-latest', 'messages': [], 'max_tokens': 900, 'response_format': {'type': 'json_object'}}


# ---------------------------------------------------------------- fournisseurs : Anthropic, DeepSeek
def test_secours_jamais_deepseek(monkeypatch):
    for f in P.FOURNISSEURS.values():
        monkeypatch.delenv(f['cle'], raising=False)
    monkeypatch.setattr(P, '_reglages', lambda: {'ia_fournisseur': 'anthropic'})
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'sk-' + 'd' * 30)
    assert P.effectif() is None                                  # seule une clé DeepSeek : pas de secours vers la Chine
    monkeypatch.setattr(P, '_reglages', lambda: {'ia_fournisseur': 'deepseek'})
    assert P.effectif() == 'deepseek' and P.modele() == 'deepseek-flash'
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-' + 'a' * 30)
    monkeypatch.setattr(P, '_reglages', lambda: {'ia_fournisseur': 'openai'})
    assert P.effectif() == 'anthropic' and P.modele() == 'claude-sonnet-5-5'


def test_parametres_deepseek(monkeypatch):
    monkeypatch.delenv('EGALYX_IA_MODELE_DEEPSEEK', raising=False)
    k = P._vers_compatible({'model': 'gpt-4o-mini', 'messages': [], 'max_completion_tokens': 500, 'tools': [1], 'seed': 3}, 'deepseek')
    assert k == {'model': 'deepseek-flash', 'messages': [], 'max_tokens': 500, 'tools': [1]}


def test_traduction_vers_anthropic(monkeypatch):
    monkeypatch.delenv('EGALYX_IA_MODELE_ANTHROPIC', raising=False)
    outil = {'type': 'function', 'function': {'name': 'lister_risques', 'description': 'Risques', 'parameters': {'type': 'object', 'properties': {'niveau': {'type': 'string'}}}}}
    c = P.vers_anthropic({
        'model': 'gpt-4o-mini', 'max_completion_tokens': 900, 'temperature': 0.2, 'response_format': {'type': 'json_object'},
        'tools': [outil], 'tool_choice': 'auto',
        'messages': [{'role': 'system', 'content': 'Consigne A'}, {'role': 'user', 'content': 'Question'},
                     {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 't1', 'type': 'function',
                                                                            'function': {'name': 'lister_risques', 'arguments': '{"niveau": "eleve"}'}}]},
                     {'role': 'tool', 'tool_call_id': 't1', 'content': '{"total": 2}'},
                     {'role': 'system', 'content': 'Consigne B'}]})
    assert c['model'] == 'claude-sonnet-5-5' and c['max_tokens'] == 900 + P.ANTHROPIC_MARGE_REFLEXION and c['temperature'] == 0.2
    assert c['system'].startswith('Consigne A') and 'Consigne B' in c['system'] and P.CONSIGNE_JSON in c['system']
    assert [m['role'] for m in c['messages']] == ['user', 'assistant', 'user']
    assert c['messages'][1]['content'][0] == {'type': 'tool_use', 'id': 't1', 'name': 'lister_risques', 'input': {'niveau': 'eleve'}}
    assert c['messages'][2]['content'][0] == {'type': 'tool_result', 'tool_use_id': 't1', 'content': '{"total": 2}'}
    assert c['tools'] == [{'name': 'lister_risques', 'description': 'Risques', 'input_schema': outil['function']['parameters']}]
    assert 'tool_choice' not in c                                # « auto » : valeur par défaut d'Anthropic


def test_traduction_depuis_anthropic():
    rep = P.depuis_anthropic({'id': 'm1', 'model': 'claude-sonnet-5-5', 'stop_reason': 'end_turn', 'usage': {'input_tokens': 10, 'output_tokens': 5},
                              'content': [{'type': 'thinking', 'thinking': '…'}, {'type': 'text', 'text': '```json\n{"a": 1}\n```'}]},
                             json_attendu=True)
    import json
    assert json.loads(rep.choices[0].message.content) == {'a': 1} and rep.choices[0].message.tool_calls is None
    rep = P.depuis_anthropic({'stop_reason': 'tool_use', 'content': [{'type': 'tool_use', 'id': 'u1', 'name': 'mes_taches', 'input': {}}]})
    tc = rep.choices[0].message.tool_calls[0]
    assert rep.choices[0].finish_reason == 'tool_calls' and tc.id == 'u1' and tc.function.name == 'mes_taches' and tc.function.arguments == '{}'
