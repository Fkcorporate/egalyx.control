"""
Mini « ORM » en mémoire pour tester les routes des modules v4 sans SQLAlchemy
(non installable ici). Couvre uniquement ce que ces routes utilisent.
"""
import itertools
from datetime import datetime


class _Pred:
    def __init__(self, f):
        self.f = f

    def __call__(self, o):
        return self.f(o)

    def __or__(self, autre):
        return _Pred(lambda o: self.f(o) or autre.f(o))


class _Tri:
    def __init__(self, nom, inverse=False):
        self.nom, self.inverse = nom, inverse

    def nullslast(self):
        return self


class Champ:
    def __init__(self, defaut=None):
        self.defaut = defaut

    def __set_name__(self, owner, nom):
        self.nom = nom

    def __get__(self, obj, owner):
        if obj is None:
            return _ChampClasse(self.nom)
        if self.nom not in obj.__dict__:
            d = self.defaut() if callable(self.defaut) else self.defaut
            obj.__dict__[self.nom] = d
        return obj.__dict__[self.nom]

    def __set__(self, obj, v):
        obj.__dict__[self.nom] = v


class _ChampClasse:
    def __init__(self, nom):
        self.nom = nom

    def __eq__(self, v):
        return _Pred(lambda o: getattr(o, self.nom) == v)

    def __ne__(self, v):
        return _Pred(lambda o: getattr(o, self.nom) != v)

    def in_(self, valeurs):
        valeurs = list(valeurs)
        return _Pred(lambda o: getattr(o, self.nom) in valeurs)

    def notin_(self, valeurs):
        valeurs = list(valeurs)
        return _Pred(lambda o: getattr(o, self.nom) not in valeurs)

    def ilike(self, motif):
        m = motif.strip('%').lower()
        return _Pred(lambda o: m in str(getattr(o, self.nom) or '').lower())

    def desc(self):
        return _Tri(self.nom, True)

    def asc(self):
        return _Tri(self.nom)

    __hash__ = object.__hash__


class _Lower:
    def __init__(self, champ):
        self.champ = champ

    def __eq__(self, v):
        return _Pred(lambda o: str(getattr(o, self.champ.nom) or '').lower() == v)


class Requete:
    def __init__(self, modele, elements=None):
        self.modele = modele
        self.elements = list(elements if elements is not None else modele._registre)

    def filter_by(self, **kw):
        return Requete(self.modele, [o for o in self.elements if all(getattr(o, k, None) == v for k, v in kw.items())])

    def filter(self, *preds):
        el = self.elements
        for p in preds:
            el = [o for o in el if p(o)]
        return Requete(self.modele, el)

    def order_by(self, *tris):
        el = list(self.elements)
        for t in reversed(tris):
            if isinstance(t, _ChampClasse):
                t = _Tri(t.nom)
            el.sort(key=lambda o: (getattr(o, t.nom) is None, getattr(o, t.nom) or 0), reverse=t.inverse)
        return Requete(self.modele, el)

    def limit(self, n):
        return Requete(self.modele, self.elements[:n])

    def all(self):
        return list(self.elements)

    def first(self):
        return self.elements[0] if self.elements else None

    def first_or_404(self):
        from flask import abort
        return self.first() or abort(404)

    def count(self):
        return len(self.elements)

    def get(self, ident):
        return next((o for o in self.modele._registre if o.id == ident), None)

    def delete(self):
        for o in self.elements:
            self.modele._registre.remove(o)
        return len(self.elements)

    def __iter__(self):
        return iter(self.elements)


class _MetaModele(type):
    @property
    def query(cls):
        return Requete(cls)


class Modele(metaclass=_MetaModele):
    _compteurs = {}

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        cls._registre = []
        Modele._compteurs[cls] = itertools.count(1)

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _Session:
    def __init__(self):
        self.ajouts = []
        self.commits = 0

    def add(self, o):
        if o not in type(o)._registre:
            if getattr(o, 'id', None) is None:
                o.id = next(Modele._compteurs[type(o)])
            if hasattr(type(o), 'created_at') and getattr(o, 'created_at', None) is None:
                o.created_at = datetime.utcnow()
            type(o)._registre.append(o)

    def add_all(self, l):
        for o in l:
            self.add(o)

    def bulk_save_objects(self, l):
        self.add_all(l)

    def flush(self):
        pass

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def get(self, modele, ident):
        return Requete(modele).get(ident)


class _Func:
    @staticmethod
    def lower(champ):
        return _Lower(champ)


class FauxDB:
    func = _Func()

    def __init__(self):
        self.session = _Session()
