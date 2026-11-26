"""
egalyx/ia_masque.py — masquage des données sensibles avant tout envoi à un fournisseur d'IA.

Avant l'envoi, les données identifiantes sont remplacées par des repères ([PERSONNE_1], [EMAIL_2]…) ;
la réponse de l'IA est ensuite « démasquée » : l'utilisateur voit les vrais noms, le fournisseur ne les a jamais reçus.

Masqué :
  - adresses e-mail, IBAN, numéros de téléphone, numéros longs (comptes, cartes, dossiers : 9 chiffres et plus) ;
  - noms et prénoms des utilisateurs de l'organisation, leurs identifiants de connexion composés (awa.kone) ;
  - personnes désignées par une civilité (M. Traoré, Mme Kouassi, Monsieur Yao…) ;
  - le nom de l'organisation.
Non masqué : montants, dates, intitulés de risques et de processus (nécessaires à l'analyse).
Limite assumée : un nom propre cité sans civilité et qui n'est pas un utilisateur de l'outil n'est pas reconnu.
"""
import copy
import re

NOTE_IA = ("Les repères entre crochets (de la forme [PERSONNE_n], [EMAIL_n], [ORGANISATION]…) remplacent des données masquées "
           "pour la confidentialité : recopie-les exactement tels quels là où ils sont utiles, n'invente pas ce qu'ils cachent.")

_EMAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
_IBAN = re.compile(r'\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,7}(?:[ ]?[A-Z0-9]{1,4})?\b')
_TEL = re.compile(r'(?<![\w+])(?:\+\d{1,3}[ .-]?)?(?:\(0\)[ .-]?)?0?\d(?:[ .-]?\d{2}){4}(?![\d])')
_NUMERO = re.compile(r'(?<![\w])\d{9,}(?![\w])')
_CIVILITE = re.compile(r"\b(?:M\.|Mme|Mlle|Mr\.?|Monsieur|Madame|Mademoiselle|Me|Maître|Dr\.?|Docteur)\s+"
                       r"((?:[A-ZÀ-ÖØ-Ý][\w'’-]+)(?:\s+[A-ZÀ-ÖØ-Ý][\w'’-]+){0,2})")
_JETON = re.compile(r'\[(?:PERSONNE|EMAIL|IBAN|TELEPHONE|NUMERO|ORGANISATION)(?:_\d+)?\]')
# mots qui ne sont jamais masqués même s'ils servent de prénom ou de nom à un utilisateur
_COMMUNS = {'admin', 'audit', 'test', 'user', 'client', 'super', 'support', 'banque', 'service', 'direction', 'contrôle',
            'controle', 'gestion', 'risque', 'risques', 'qualité', 'qualite', 'achat', 'achats', 'caisse', 'credit', 'crédit',
            'france', 'paris', 'abidjan', 'dakar', 'marie', 'rose', 'grace', 'grâce', 'espoir', 'paix', 'roi', 'reine',
            'blanc', 'noir', 'petit', 'grand', 'martin', 'bon', 'bonne', 'saint', 'sainte'}


class Masque:
    def __init__(self, noms=(), organisation=None):
        self.original = {}            # repère -> texte d'origine
        self._repere = {}             # (genre, texte en minuscules) -> repère
        self._compte = {}
        noms = {n.strip() for n in noms if n and len(n.strip()) >= 3 and n.strip().lower() not in _COMMUNS}
        self._noms = re.compile(r'(?<![\w@.])(' + '|'.join(re.escape(n) for n in sorted(noms, key=len, reverse=True)) + r')(?![\w])',
                                re.I) if noms else None
        self._org = organisation.strip() if organisation and len(organisation.strip()) >= 3 else None
        self._org_re = re.compile(r'(?<![\w])' + re.escape(self._org) + r'(?![\w])', re.I) if self._org else None

    # ---------------------------------------------------------------- repères
    def _jeton(self, genre, texte, numerote=True):
        cle = (genre, texte.lower())
        if cle not in self._repere:
            if numerote:
                self._compte[genre] = self._compte.get(genre, 0) + 1
                j = f'[{genre}_{self._compte[genre]}]'
            else:
                j = f'[{genre}]'
            self._repere[cle] = j
            self.original[j] = texte
        return self._repere[cle]

    @property
    def nombre(self):
        return len(self.original)

    # ---------------------------------------------------------------- masquer
    def texte(self, s):
        if not isinstance(s, str) or not s:
            return s
        s = _EMAIL.sub(lambda m: self._jeton('EMAIL', m.group(0)), s)
        s = _IBAN.sub(lambda m: self._jeton('IBAN', m.group(0)), s)
        s = _TEL.sub(lambda m: self._jeton('TELEPHONE', m.group(0)), s)
        s = _NUMERO.sub(lambda m: self._jeton('NUMERO', m.group(0)), s)
        s = _CIVILITE.sub(lambda m: m.group(0)[:m.start(1) - m.start(0)] + self._jeton('PERSONNE', m.group(1)), s)
        if self._org_re:
            s = self._org_re.sub(lambda m: self._jeton('ORGANISATION', self._org, numerote=False), s)
        if self._noms:
            s = self._noms.sub(lambda m: self._jeton('PERSONNE', m.group(0)), s)
        return s

    def objet(self, o):
        """Masque toutes les chaînes d'une structure (dict, liste, texte) ; les clés des dictionnaires sont gardées."""
        if isinstance(o, str):
            return self.texte(o)
        if isinstance(o, dict):
            return {k: self.objet(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [self.objet(v) for v in o]
        return o

    def messages(self, messages):
        """Messages au format chat (rôle + contenu texte ou parties) ; ajoute la consigne sur les repères."""
        sortie = []
        for m in messages or []:
            m = copy.copy(m) if isinstance(m, dict) else m
            if isinstance(m, dict):
                c = m.get('content')
                if isinstance(c, str):
                    m['content'] = self.texte(c)
                elif isinstance(c, list):
                    m['content'] = [dict(p, text=self.texte(p.get('text'))) if isinstance(p, dict) and p.get('type') == 'text' else p
                                    for p in c]
            sortie.append(m)
        if self.nombre:
            if sortie and isinstance(sortie[0], dict) and sortie[0].get('role') == 'system' and isinstance(sortie[0].get('content'), str):
                sortie[0] = dict(sortie[0], content=sortie[0]['content'] + '\n' + NOTE_IA)
            else:
                sortie.insert(0, {'role': 'system', 'content': NOTE_IA})
        return sortie

    # ---------------------------------------------------------------- démasquer
    def restaurer(self, o):
        if isinstance(o, str):
            if not self.original or '[' not in o:
                return o
            return re.sub(r'\[[A-Z]+(?:_\d+)?\]', lambda m: self.original.get(m.group(0), m.group(0)), o)
        if isinstance(o, dict):
            return {k: self.restaurer(v) for k, v in o.items()}
        if isinstance(o, list):
            return [self.restaurer(v) for v in o]
        return o


def contient_des_reperes(s):
    return bool(_JETON.search(s or ''))


def pour_organisation(cid):
    """Masque construit avec les noms des utilisateurs et le nom de l'organisation."""
    noms, org = set(), None
    if cid:
        try:
            import models as m
            client = m.db.session.get(m.Client, cid)
            org = getattr(client, 'nom', None)
            for u in m.User.query.filter_by(client_id=cid).all():
                for v in (u.prenom, u.nom):
                    if v:
                        noms.add(v)
                if u.prenom and u.nom:
                    noms.add(f'{u.prenom} {u.nom}')
                    noms.add(f'{u.nom} {u.prenom}')
                if u.username and re.search(r'[._\-\d]', u.username):
                    noms.add(u.username)
                    noms.update(p for p in re.split(r'[._\-\d]+', u.username) if len(p) >= 3)
        except Exception:  # noqa: BLE001 — sans base, on masque au moins e-mails, téléphones, numéros, civilités
            pass
    return Masque(noms, org)
