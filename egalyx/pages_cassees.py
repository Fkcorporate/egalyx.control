"""Pages qui renvoyaient une erreur 500.

- /ci, /cote-divoire : le gabarit attendait des données jamais fournies (meta, contact) et le
  formulaire postait vers /api/contact-ci, qui n'existe pas. La page affichait aussi un bureau,
  des numéros et des témoignages non vérifiés. On redirige (301) vers l'accueil, rubrique contact,
  le temps de faire une vraie page Côte d'Ivoire avec vos informations exactes.
- /debug/create-user-form : outil de développement resté en production. Il n'a pas sa place sur
  le site public : on répond 404.
- /plan-action/<id>/gantt : corrigé dans templates/audit/gantt.html (bornes de dates).
"""
from flask import abort, redirect


def enregistrer(app):
    vues = app.view_functions

    if 'page_ci' in vues:
        def page_ci(*a, **k):
            return redirect('/#contact', code=301)
        vues['page_ci'] = page_ci

    if 'debug_create_user_form' in vues:
        def debug_create_user_form(*a, **k):
            abort(404)
        vues['debug_create_user_form'] = debug_create_user_form
