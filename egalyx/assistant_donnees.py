"""
egalyx/assistant_donnees.py — l'assistant répond aux questions sur les données (IA, étape 3).

L'assistant d'app.py (moteur local sans IA + IA avec « outils ») existait déjà. Ce module :
  1. donne à l'IA TOUS les outils de lecture : seuls 8 sur 22 lui étaient déclarés (elle ne pouvait pas lire les
     recommandations, constats, contrôles N2, campagnes, PCA, « mes tâches », la recherche…) ;
  2. ajoute trois outils d'analyse :
       - couverture_audit      : processus / entités jamais audités ou dont l'échéance est dépassée, avec leur risque
                                 (univers d'audit ; à défaut, cartographie des processus) ;
       - indicateurs_audit     : indicateurs de la fonction d'audit (mêmes calculs que la page « Qualité de la fonction ») ;
       - lister_recommandations: filtres priorité, direction du responsable, retard, mot-clé ;
  3. apprend ces trois questions au moteur local (réponses sans IA, aucune donnée ne sort) ;
  4. place la partie IA de l'assistant sous l'interrupteur du super admin « Assistant : réponses avec l'IA »
     (avant : variable cachée ASSISTANT_IA_EXTERNE=1). ASSISTANT_IA_EXTERNE=0 la coupe toujours.
Règles inchangées : organisation imposée par la session, permission vérifiée par chaque outil, lecture seule ;
les échanges avec l'IA passent par la passerelle (fournisseur choisi, données masquées).
"""
import re
import sys
from datetime import date

CODE = 'assistant_donnees'
PRIORITES = {'critique': 80, 'haute': 60, 'moyenne': 40, 'basse': 0}
NIVEAUX_ENTITE = {'eleve': 3, 'moyen': 2, 'faible': 1}


def _m():
    import models
    return models


def _norm(t):
    import unicodedata
    t = unicodedata.normalize('NFD', (t or '').lower())
    return ''.join(c for c in t if unicodedata.category(c) != 'Mn')


def installer(A):
    """A : le module app (fonctions _assistant_* et tables ASSISTANT_*)."""
    from flask_login import current_user

    exiger, client_id = A._assistant_exiger, A._assistant_exiger_client
    date_txt, MAX = A._assistant_date, A.ASSISTANT_MAX_LIGNES

    # ------------------------------------------------------------------ outils
    def lister_recommandations(en_retard_seulement=False, priorite=None, direction=None, recherche=None):
        exiger('can_manage_audit', 'can_view_recommandations')
        m = _m()
        cid = client_id()
        auj = A._aujourdhui()
        q = m.Recommandation.query.filter(m.Recommandation.client_id == cid,
                                          m.Recommandation.statut.notin_(['termine', 'annule', 'rejetee']))
        if en_retard_seulement:
            q = q.filter(m.Recommandation.date_echeance < auj)
        if priorite in PRIORITES:
            q = q.filter(m.Recommandation.score_priorite >= PRIORITES[priorite])
        recos = q.order_by(m.Recommandation.date_echeance.asc().nullslast()).all()
        noms_dir = {}
        if direction:
            d = _norm(direction).replace('direction', '').strip(" de'’ld")
            dirs = {x.id: x.nom for x in m.Direction.query.filter_by(client_id=cid).all() if d and d in _norm(x.nom)}
            uids = {u.id for u in m.User.query.filter(m.User.client_id == cid, m.User.direction_id.in_(list(dirs) or [-1])).all()}
            recos = [r for r in recos if r.responsable_id in uids]
            noms_dir = dirs
        if recherche:
            t = _norm(recherche)
            recos = [r for r in recos if t in _norm(r.description) or t in _norm(r.reference)]
        audits = {a.id: a.reference for a in m.Audit.query.filter(m.Audit.id.in_({r.audit_id for r in recos} or {-1})).all()}
        def resp(r):
            u = m.db.session.get(m.User, r.responsable_id) if r.responsable_id else None
            from egalyx.commun import nom_personne
            return nom_personne(u, 'sans responsable')
        items = recos[:MAX]
        return {'total': len(recos), 'affiches': len(items), 'filtres': {'priorite': priorite, 'direction': list(noms_dir.values()),
                                                                          'en_retard': bool(en_retard_seulement)},
                'elements': [{'titre': f"{r.reference} — {(r.description or '')[:80]}",
                              'sous_titre': f"Échéance {date_txt(r.date_echeance) or '—'} · {r.taux_avancement or 0} % · {resp(r)}"
                                            f" · priorité {r.score_priorite or 0}/100 · audit {audits.get(r.audit_id, '—')}",
                              'badge': 'en retard' if r.date_echeance and r.date_echeance < auj else r.statut,
                              'lien': f'/audit/recommandation/{r.id}'} for r in items]}

    def couverture_audit(etat='retard', niveau_min=None):
        exiger('can_manage_audit')
        cid = client_id()
        seuil = NIVEAUX_ENTITE.get(niveau_min or '', 0)
        lignes, source = [], ''
        try:
            from egalyx import fonction_audit as fa
            u = fa.univers(cid)
            for x in u['lignes']:
                e = x['e']
                if NIVEAUX_ENTITE.get(e.niveau_risque or 'moyen', 2) < seuil:
                    continue
                if etat in ('retard', 'bientot') and x['etat'] != etat:
                    continue
                lignes.append({'titre': e.nom, 'badge': x['libelle'], 'lien': '/fonction-audit/univers',
                               'sous_titre': f"Risque {e.niveau_risque or 'moyen'} · dernier audit {date_txt(x['dernier']) or 'aucun'}"
                                             f" · cycle {x['cycle']} an(s)" + (f" · échéance {date_txt(x['echeance'])}" if x['echeance'] else '')})
            source, taux = ('univers', u['couverture']) if u['lignes'] else ('', None)
        except Exception:  # noqa: BLE001 — module univers absent
            taux = None
        if not source:                                   # pas d'univers : cartographie des processus, si elle est utilisée
            from egalyx import carto_processus as cp
            d = cp.donnees(cid)
            fiches = [f for lst in d['bandes'].values() for f in lst]
            for f in sorted(fiches, key=lambda f: (-f['niveau'], f['nom'])):
                if f['niveau'] < {3: 3, 2: 2, 1: 1}.get(seuil, 0):
                    continue
                if etat == 'retard' and f['couverture'] not in ('jamais', 'tres_ancien'):
                    continue
                lignes.append({'titre': f"{f['code']} {f['nom']}", 'badge': f['couverture_lib'], 'lien': '/carte-processus/?vue=audit',
                               'sous_titre': f"Risque le plus élevé : {f['niveau_lib']} · {f['nb_risques']} risque(s) · dernier audit {f['dernier_audit'] or 'aucun'}"})
            source = 'processus' if fiches else ''
            taux = round(100 * sum(1 for f in fiches if f['couverture'] == 'recent') / len(fiches)) if fiches else None
        return {'total': len(lignes), 'affiches': min(len(lignes), MAX), 'source': source, 'couverture_pourcent': taux,
                'elements': lignes[:MAX]}

    def indicateurs_audit(annee=None):
        exiger('can_manage_audit')
        cid = client_id()
        from egalyx import fonction_audit as fa
        annee = int(annee) if str(annee or '').isdigit() else date.today().year
        ind = fa.indicateurs(cid, annee)
        def p(v):
            return '—' if v is None else f'{v} %'
        el = [('Programme d’audit réalisé', f"{ind['programme']['realisees']} / {ind['programme']['prevues']} mission(s) · {p(ind['programme']['taux'])}"),
              ('Rapports définitifs émis', f"{ind['rapports']['nb']} · délai moyen fin des travaux → rapport : "
                                           + (f"{ind['rapports']['delai_moyen']} j" if ind['rapports']['delai_moyen'] is not None else '—')),
              ('Recommandations échues mises en œuvre', f"{ind['recommandations']['mises_en_oeuvre']} / {ind['recommandations']['echues']} · {p(ind['recommandations']['taux'])}"),
              ('Indépendance documentée', f"{ind['independance']['completes']} / {ind['independance']['nb']} mission(s) · {p(ind['independance']['taux'])}"),
              ('Satisfaction des audités', (f"{ind['satisfaction']['moyenne']} / 5" if ind['satisfaction']['moyenne'] is not None
                                            else 'pas assez de réponses') + f" · {ind['satisfaction']['nb']} réponse(s)"),
              ('Couverture de l’univers d’audit', f"{p(ind['univers']['couverture'])} · {ind['univers']['retard']} entité(s) en retard dont "
                                                  f"{ind['univers']['eleve_retard']} à risque élevé")]
        return {'total': len(el), 'affiches': len(el), 'annee': annee,
                'elements': [{'titre': t, 'sous_titre': s, 'badge': None, 'lien': '/fonction-audit/qualite'} for t, s in el]}

    A.ASSISTANT_FONCTIONS.update({'lister_recommandations': lister_recommandations, 'couverture_audit': couverture_audit,
                                  'indicateurs_audit': indicateurs_audit})

    # ------------------------------------------------------------------ outils déclarés à l'IA
    o = A._assistant_outil
    nouveaux = [
        o('lister_recommandations', "Recommandations d'audit non clôturées, avec filtres.",
          {'en_retard_seulement': {'type': 'boolean'},
           'priorite': {'type': 'string', 'enum': list(PRIORITES), 'description': 'Priorité minimale (critique ≥ 80/100, haute ≥ 60, moyenne ≥ 40)'},
           'direction': {'type': 'string', 'description': 'Direction du responsable (ex. « crédits »)'},
           'recherche': {'type': 'string', 'description': 'Mot à chercher dans la recommandation'}}),
        o('couverture_audit', "Couverture d'audit : processus ou entités jamais audités ou à auditer (échéance dépassée), avec leur niveau de risque.",
          {'etat': {'type': 'string', 'enum': ['retard', 'bientot', 'tous']},
           'niveau_min': {'type': 'string', 'enum': ['eleve', 'moyen', 'faible'], 'description': 'Niveau de risque minimal'}}),
        o('indicateurs_audit', "Indicateurs de la fonction d'audit pour une année : programme réalisé, délai des rapports, "
                               "taux de mise en œuvre des recommandations, indépendance, satisfaction, couverture de l'univers.",
          {'annee': {'type': 'integer', 'minimum': 2000, 'maximum': 2100}}),
        o('lister_constatations', 'Constatations d’audit non clôturées.'),
        o('lister_dispositifs', 'Dispositifs de maîtrise des risques (option : seulement les peu efficaces).',
          {'efficacite_faible': {'type': 'boolean'}}),
        o('lister_nc_c2n', 'Non-conformités ouvertes du contrôle interne de 2e niveau.'),
        o('lister_planifications_c2n', 'Contrôles de 2e niveau planifiés.', {'statut': {'type': 'string'}}),
        o('lister_campagnes', 'Campagnes de contrôle en cours.'),
        o('lister_pca', 'Plans de continuité d’activité.'),
        o('lister_plans_qualite', 'Plans qualité.'),
        o('lister_tickets', 'Tickets de support et signalements.'),
        o('lister_cartographies', 'Cartographies des risques.'),
        o('lister_notifications', 'Notifications non lues de l’utilisateur.'),
        o('mes_taches', 'Ce que l’utilisateur doit faire : validations, actions, échéances qui le concernent.'),
        o('chercher_reference', 'Retrouve un élément par sa référence exacte (ex. AUD-2026-01, RSQ-2026-0012).',
          {'reference': {'type': 'string'}}, ['reference']),
        o('recherche_globale', 'Cherche un mot dans les intitulés de tous les modules accessibles.', {'texte': {'type': 'string'}}, ['texte']),
    ]
    deja = {s['function']['name'] for s in A.ASSISTANT_SCHEMAS}
    for s in nouveaux:
        nom = s['function']['name']
        if nom in A.ASSISTANT_FONCTIONS:
            if nom in deja:
                A.ASSISTANT_SCHEMAS[:] = [x for x in A.ASSISTANT_SCHEMAS if x['function']['name'] != nom]
            A.ASSISTANT_SCHEMAS.append(s)

    # ------------------------------------------------------------------ interrupteur du super admin
    def ia_externe_active():
        import os
        if os.environ.get('ASSISTANT_IA_EXTERNE') == '0':
            return False
        try:
            from egalyx import ia_passerelle
            from egalyx.ia import fonction_active
            return ia_passerelle.effectif() is not None and fonction_active(CODE)
        except Exception:  # noqa: BLE001
            return False
    A._assistant_ia_externe_active = ia_externe_active

    # ------------------------------------------------------------------ moteur local (sans IA)
    origine = A.assistant_moteur_local
    if getattr(origine, '_egalyx_donnees', False):
        return

    def liste(outil, args, phrase, vide, action, suggestions):
        return A._assistant_q_liste(outil, args, phrase, vide, action, suggestions, outil)

    def moteur(question):
        t = _norm(question)
        mots = set(re.findall(r'[a-z0-9]+', t))
        audit = bool(mots & {'audit', 'audits', 'audite', 'audites', 'auditee', 'auditees', 'auditer'})
        if audit and (mots & {'jamais', 'couverture', 'couvert', 'couverts', 'univers', 'retard'} and
                      mots & {'processus', 'entite', 'entites', 'jamais', 'couverture', 'univers'}):
            niveau = 'eleve' if mots & {'eleve', 'eleves', 'critique', 'critiques', 'fort', 'forts'} else None
            try:
                return liste('couverture_audit', {'etat': 'retard', 'niveau_min': niveau},
                             '{n} processus ou entité(s) ' + ('à risque élevé ' if niveau else '') + 'jamais audité(s) ou à auditer',
                             'Rien en retard : tout est couvert. 👍', ('Univers d’audit', 'fonction_audit.page_univers', 'fa-globe'),
                             ["Indicateurs de l'audit cette année ?", 'Quelles recommandations critiques sont en retard ?'])
            except Exception:  # noqa: BLE001
                pass
        if (mots & {'indicateur', 'indicateurs', 'kpi', 'taux', 'performance'} and (audit or mots & {'fonction', 'recommandations'})) \
                or 'mise en oeuvre' in t:
            an = re.search(r'\b(20\d\d)\b', t)
            try:
                return liste('indicateurs_audit', {'annee': int(an.group(1)) if an else None}, 'Indicateurs de la fonction d’audit',
                             'Aucun indicateur.', ('Qualité de la fonction', 'fonction_audit.page_qualite', 'fa-award'),
                             ['Quels processus n’ont jamais été audités ?'])
            except Exception:  # noqa: BLE001
                pass
        if mots & {'recommandation', 'recommandations', 'reco', 'recos'}:
            prio = ('critique' if mots & {'critique', 'critiques'} else 'haute' if mots & {'prioritaire', 'prioritaires', 'haute', 'hautes', 'urgentes', 'urgente'}
                    else None)
            md = re.search(r"direction\s+(?:des?\s+|du\s+|de\s+la\s+|de\s+l\s*)?([a-z0-9 ]{3,40}?)(?:\s+(?:en|qui|sont|est|a|ont)\b|[?.!]|$)", t)
            retard = bool(mots & {'retard', 'echues', 'echue', 'depassees', 'depassee'})
            if prio or md:
                args = {'en_retard_seulement': retard, 'priorite': prio, 'direction': md.group(1).strip() if md else None}
                try:
                    return liste('lister_recommandations', args,
                                 '{n} recommandation(s)' + (f' {prio}s' if prio else '') + (' en retard' if retard else ' en cours')
                                 + (f" — direction « {md.group(1).strip()} »" if md else ''),
                                 'Aucune recommandation ne correspond. 👍', ('Registre des recommandations', 'recommandations.registre', 'fa-list-check'),
                                 ['Quels processus n’ont jamais été audités ?'])
                except Exception:  # noqa: BLE001
                    pass
        return origine(question)
    moteur._egalyx_donnees = True
    A.assistant_moteur_local = moteur
    for s in ['Quels processus à risque élevé n’ont jamais été audités ?', 'Quelles recommandations critiques sont en retard ?']:
        if hasattr(A, 'ASSISTANT_SUGGESTIONS_DEFAUT') and s not in A.ASSISTANT_SUGGESTIONS_DEFAUT:
            A.ASSISTANT_SUGGESTIONS_DEFAUT.append(s)


def enregistrer(app):
    A = sys.modules.get(app.import_name)
    if A is None or not hasattr(A, 'ASSISTANT_FONCTIONS') or not hasattr(A, 'assistant_moteur_local'):
        return False
    installer(A)
    return True
