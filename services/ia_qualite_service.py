# services/ia_qualite_service.py
"""Assistant du module Qualité.

Chaque fonction essaie d'abord la vraie IA (egalyx.ia_moteur : modèle actuel, interrupteur super-admin respecté).
Si l'IA n'est pas disponible, elle applique des règles fixes et le signale (origine « automatique ») :
plus aucun tirage au hasard — deux clics donnent la même proposition.
"""
from datetime import datetime, timedelta

from flask import current_app

from models import ActionAmeliorationQualite, PlanQualiteFonction

try:
    from egalyx import ia_moteur as moteur
except ImportError:                                    # installation sans le module commun
    moteur = None

CONSIGNES = """Tu es un expert en management de la qualité (ISO 9001, amélioration continue, contrôle interne).
Tu aides à rédiger un plan d'assurance et d'amélioration qualité. Français professionnel, concret, sans jargon inutile.
N'invente ni référence de document existant, ni chiffre constaté : propose des cibles réalistes présentées comme des cibles."""

OBJECTIFS_TYPES = [
    "Atteindre un taux de conformité de 95 % sur les processus critiques d'ici la fin de l'exercice.",
    "Réduire de 30 % le nombre de non-conformités majeures dans les 6 prochains mois.",
    "Former 100 % du personnel concerné aux procédures qualité dans les 3 mois suivant leur validation.",
]
INDICATEURS_TYPES = [
    {"nom": "Taux de conformité des processus", "cible": "≥ 95 %", "unite": "%"},
    {"nom": "Nombre de non-conformités majeures", "cible": "≤ 5 par trimestre", "unite": "nb"},
    {"nom": "Taux de réalisation des actions correctives dans les délais", "cible": "100 %", "unite": "%"},
]
ASSURANCE_TYPE = {
    'procedures': "Gestion des non-conformités\nAudit interne\nMaîtrise des documents\nTraitement des réclamations",
    'documents': "Politique qualité\nCartographie des processus\nMatrice de conformité réglementaire\nPlan d'audit annuel",
    'controles': "Validation des documents avant diffusion\nRevue mensuelle des indicateurs\nContrôle croisé des dossiers sensibles",
    'frequence': 'trimestriel',
}
FREQUENCES = ('mensuel', 'trimestriel', 'semestriel', 'annuel')


def _ia(consignes, donnees, max_tokens=900):
    """Réponse JSON de l'IA, ou None si elle n'est pas disponible (l'appelant applique alors ses règles)."""
    if moteur is None:
        return None
    try:
        return moteur.demander_json(CONSIGNES + "\n" + consignes, donnees, max_tokens=max_tokens)
    except moteur.IndisponibleIA:
        return None


def _auto():
    if moteur is not None:
        moteur.marquer(moteur.AUTO)


def _t(v, n=600):
    return moteur.texte(v, n) if moteur else str(v or '')[:n]


class IAQualiteService:
    """Assistant du module Qualité (IA si disponible, sinon règles fixes signalées)."""

    @staticmethod
    def _is_ia_available():
        return bool(moteur and moteur.disponible())

    # 1. Description
    @staticmethod
    def generer_description_plan(plan_data):
        titre = _t(plan_data.get('titre'), 200)
        objectifs = [o for o in (plan_data.get('objectifs') or []) if o][:5]
        r = _ia('Rédige une description (2 à 3 phrases) qui explique le but et la valeur du plan. '
                'Réponds {"description": "..."}', {'titre_du_plan': titre, 'objectifs': objectifs}, 300)
        if r and _t(r.get('description')):
            return _t(r.get('description'), 900)
        _auto()
        if objectifs:
            return (f"Ce plan qualité vise à atteindre les objectifs suivants : {', '.join(map(str, objectifs[:2]))}. "
                    "Il combine des actions préventives d'assurance qualité et des actions correctives d'amélioration "
                    "continue pour garantir la conformité et la performance des processus.")
        return ("Ce plan d'assurance et d'amélioration qualité vise à renforcer la maîtrise des processus clés et à "
                "garantir la conformité réglementaire, dans une démarche d'amélioration continue"
                + (f" pour « {titre} »." if titre else "."))

    # 2. Objectifs SMART
    @staticmethod
    def generer_objectifs_smart(titre):
        r = _ia('Propose 3 objectifs SMART (spécifiques, mesurables, atteignables, réalistes, datés) adaptés au plan. '
                'Réponds {"objectifs": ["...", "...", "..."]}', {'titre_du_plan': _t(titre, 300)}, 500)
        objectifs = moteur.liste_textes((r or {}).get('objectifs'), 5, 300) if (r and moteur) else []
        if objectifs:
            return objectifs
        _auto()
        return list(OBJECTIFS_TYPES)

    # 3. Indicateurs
    @staticmethod
    def generer_indicateurs(titre, objectifs):
        r = _ia('Propose 3 indicateurs clés (KPI) qui mesurent l\'atteinte des objectifs. '
                'Réponds {"indicateurs": [{"nom": "...", "cible": "...", "unite": "..."}]}',
                {'titre_du_plan': _t(titre, 300), 'objectifs': list(objectifs or [])[:5]}, 600)
        res = []
        for i in ((r or {}).get('indicateurs') or [])[:5]:
            if isinstance(i, dict) and _t(i.get('nom')):
                res.append({'nom': _t(i.get('nom'), 160), 'cible': _t(i.get('cible'), 80), 'unite': _t(i.get('unite'), 20)})
        if res:
            return res
        _auto()
        return [dict(i) for i in INDICATEURS_TYPES]

    # 4. Maturité
    @staticmethod
    def suggerer_niveau_maturite(titre):
        r = _ia('Estime le niveau de maturité de départ le plus plausible (échelle CMMI 1 Initial, 2 Répétable, 3 Défini, '
                '4 Géré, 5 Optimisé) d\'après l\'intitulé. Réponds {"niveau": "1".."5"}', {'titre_du_plan': _t(titre, 300)}, 60)
        niveau = _t((r or {}).get('niveau'), 2)
        if niveau in ('1', '2', '3', '4', '5'):
            return niveau
        _auto()
        t = (titre or '').lower()
        for niveau, mots in (('1', ('initial', 'démarrage', 'création', 'mise en place')), ('2', ('répétable', 'standard', 'base')),
                             ('3', ('défini', 'structuré', 'formalisé')), ('4', ('géré', 'mesuré', 'piloté', 'performance')),
                             ('5', ('optimisé', 'excellence', 'amélioration continue'))):
            if any(m in t for m in mots):
                return niveau
        return '3'

    # 5. Section amélioration
    @staticmethod
    def generer_section_amelioration(titre):
        objectifs = IAQualiteService.generer_objectifs_smart(titre)
        return {'objectifs': objectifs, 'indicateurs': IAQualiteService.generer_indicateurs(titre, objectifs)}

    # 6. Assurance qualité
    @staticmethod
    def suggerer_assurance_qualite(titre):
        r = _ia('Propose le contenu de la section « assurance qualité » : procédures applicables (4 au plus, une par ligne, '
                'intitulés génériques sans numéro inventé), documents de référence (4 au plus), contrôles clés (4 au plus) et '
                'fréquence des contrôles (mensuel, trimestriel, semestriel ou annuel). '
                'Réponds {"procedures": ["..."], "documents": ["..."], "controles": ["..."], "frequence": "..."}',
                {'titre_du_plan': _t(titre, 300)}, 700)
        if r and moteur:
            res = {k: "\n".join(moteur.liste_textes(r.get(k), 4, 160)) for k in ('procedures', 'documents', 'controles')}
            if all(res.values()):
                f = _t(r.get('frequence'), 20).lower()
                res['frequence'] = f if f in FREQUENCES else 'trimestriel'
                return res
        _auto()
        return dict(ASSURANCE_TYPE)

    # 7. Plan complet
    @staticmethod
    def generer_plan_complet(titre):
        objectifs = IAQualiteService.generer_objectifs_smart(titre)
        assurance = IAQualiteService.suggerer_assurance_qualite(titre)
        return {
            'description': IAQualiteService.generer_description_plan({'titre': titre, 'objectifs': objectifs}),
            'objectifs': objectifs,
            'indicateurs': IAQualiteService.generer_indicateurs(titre, objectifs),
            'niveau_maturite': IAQualiteService.suggerer_niveau_maturite(titre),
            'procedures': assurance['procedures'], 'documents': assurance['documents'],
            'controles': assurance['controles'], 'frequence': assurance['frequence'],
            'date_prochaine_revue': (datetime.now() + timedelta(days=180)).strftime('%Y-%m-%d'),
        }

    # 8. Analyse d'un plan existant
    @staticmethod
    def analyser_plan_qualite(plan_id):
        try:
            plan = PlanQualiteFonction.query.get(plan_id)
            if not plan:
                return None
            actions = ActionAmeliorationQualite.query.filter_by(plan_qualite_id=plan_id, is_archived=False).all()
            en_retard = [a for a in actions if a.est_en_retard()]
            faites = sum(1 for a in actions if a.statut == 'terminee')
            progression = round(faites / len(actions) * 100) if actions else 0
            niveau = int(plan.niveau_maturite) if str(plan.niveau_maturite or '').isdigit() else 3

            donnees = {
                'plan': {'titre': plan.titre, 'description': _t(plan.description, 800), 'niveau_maturite': niveau,
                         'objectifs': plan.objectifs_qualite, 'indicateurs': plan.indicateurs_cles,
                         'date_prochaine_revue': plan.date_prochaine_revue},
                'actions': [{'intitule': _t(getattr(a, 'titre', None) or getattr(a, 'intitule', None), 160),
                             'statut': a.statut, 'en_retard': a.est_en_retard()} for a in actions[:30]],
                'progression_pourcentage': progression,
            }
            r = _ia('Analyse ce plan qualité et propose au plus 5 recommandations concrètes, de la plus urgente à la moins '
                    'urgente, fondées uniquement sur les données. Réponds {"recommandations": [{"titre": "...", '
                    '"description": "1 à 2 phrases", "priorite": "haute|moyenne|basse"}]}', donnees, 900)
            recos = []
            for x in ((r or {}).get('recommandations') or [])[:5]:
                if isinstance(x, dict) and _t(x.get('titre')):
                    recos.append({'titre': _t(x.get('titre'), 160), 'description': _t(x.get('description'), 500),
                                  'priorite': moteur.priorite(x.get('priorite'))})
            if recos:
                return recos

            _auto()
            if not plan.objectifs_qualite:
                recos.append({'titre': 'Définir des objectifs SMART', 'priorite': 'haute',
                              'description': "Le plan ne contient pas d'objectifs qualité mesurables."})
            if not plan.indicateurs_cles:
                recos.append({'titre': 'Mettre en place des indicateurs de performance', 'priorite': 'haute',
                              'description': "Le plan ne comporte aucun indicateur clé pour mesurer l'atteinte des objectifs."})
            if not actions:
                recos.append({'titre': 'Décliner les objectifs en actions concrètes', 'priorite': 'haute',
                              'description': "Aucune action d'amélioration n'est définie."})
            elif en_retard:
                recos.append({'titre': 'Traiter les actions en retard', 'priorite': 'haute',
                              'description': f"{len(en_retard)} action(s) sont en retard : priorisez leur traitement."})
            elif any(a.statut == 'bloquee' for a in actions):
                recos.append({'titre': 'Débloquer les actions bloquées', 'priorite': 'haute',
                              'description': "Certaines actions sont bloquées : identifiez les obstacles."})
            if niveau < 3:
                recos.append({'titre': 'Améliorer le niveau de maturité', 'priorite': 'moyenne',
                              'description': f"Niveau de maturité actuel : {niveau}/5. Formalisez les procédures et renforcez les contrôles."})
            if not plan.date_prochaine_revue:
                recos.append({'titre': 'Planifier la revue périodique', 'priorite': 'basse',
                              'description': "Aucune date de revue n'est planifiée."})
            if actions and progression < 30:
                recos.append({'titre': 'Accélérer la mise en œuvre', 'priorite': 'moyenne',
                              'description': f"La progression actuelle est de {progression} %."})
            if not recos:
                recos.append({'titre': 'Plan bien structuré', 'priorite': 'basse',
                              'description': "Aucun écart détecté par les règles automatiques : maintenez le suivi régulier."})
            return recos[:5]
        except Exception as e:
            current_app.logger.error(f"Erreur analyse plan qualité {plan_id}: {e}")
            return None


# Compatibilité : anciennes fonctions de module
suggerer_assurance_qualite = IAQualiteService.suggerer_assurance_qualite
generer_plan_complet = IAQualiteService.generer_plan_complet
