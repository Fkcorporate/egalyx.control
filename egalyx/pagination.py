"""
egalyx/pagination.py — listes découpées en pages (au lieu de tout charger).

  page = paginer(requete_sqlalchemy)        # la base ne renvoie que la page demandée (LIMIT / OFFSET)
  page = paginer(liste_python)              # liste déjà construite : seule la page est affichée
  {% include "_partials/pagination.html" %} (variable « page »)

Paramètres d'adresse : ?page=2&par_page=50 (25, 50, 100 ou 200 ; 50 par défaut). Les autres paramètres
(filtres, tri) sont conservés dans les liens de page.
"""
from math import ceil

from flask import request, url_for

TAILLES = (25, 50, 100, 200)
PAR_DEFAUT = 50


class Page:
    def __init__(self, items, numero, par_page, total):
        self.items, self.numero, self.par_page, self.total = items, numero, par_page, total
        self.pages = max(1, ceil(total / par_page)) if par_page else 1
        self.debut = 0 if total == 0 else (numero - 1) * par_page + 1
        self.fin = min(total, numero * par_page)
        self.tailles = TAILLES

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    @property
    def a_precedente(self):
        return self.numero > 1

    @property
    def a_suivante(self):
        return self.numero < self.pages

    def lien(self, numero=None, par_page=None):
        args = request.args.to_dict(flat=True)
        args.update(request.view_args or {})
        args['page'] = numero or self.numero
        args['par_page'] = par_page or self.par_page
        if args['page'] == 1:
            args.pop('page')
        if args['par_page'] == PAR_DEFAUT:
            args.pop('par_page')
        return url_for(request.endpoint, **args)

    def numeros(self, autour=2):
        """1 … 4 5 [6] 7 8 … 20"""
        vus, out = set(), []
        for n in [1, *range(self.numero - autour, self.numero + autour + 1), self.pages]:
            if 1 <= n <= self.pages and n not in vus:
                if out and n - out[-1] > 1:
                    out.append(None)
                out.append(n); vus.add(n)
        return out


def parametres():
    par_page = request.args.get('par_page', type=int) or PAR_DEFAUT
    par_page = par_page if par_page in TAILLES else PAR_DEFAUT
    numero = max(1, request.args.get('page', type=int) or 1)
    return numero, par_page


def paginer(source, total=None):
    numero, par_page = parametres()
    if isinstance(source, (list, tuple)):
        total = len(source)
        pages = max(1, ceil(total / par_page))
        numero = min(numero, pages)
        return Page(list(source[(numero - 1) * par_page:numero * par_page]), numero, par_page, total)
    total = source.order_by(None).count() if total is None else total
    pages = max(1, ceil(total / par_page))
    numero = min(numero, pages)
    return Page(source.limit(par_page).offset((numero - 1) * par_page).all(), numero, par_page, total)
