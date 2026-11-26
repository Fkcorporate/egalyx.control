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
