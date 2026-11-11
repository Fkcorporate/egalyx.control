"""
egalyx/ma_semaine.py — « Ma semaine » : tout ce que l'utilisateur doit faire, trié par urgence,
et démarrage guidé d'une organisation (liste de mise en route).
"""
from datetime import date, datetime, timedelta

from flask import Blueprint, current_app, render_template, url_for
from flask_login import current_user

from egalyx.commun import admin_client_requis, client_id_courant, connexion_requise, est_admin_client

bp = Blueprint('ma_semaine', __name__)

TERMINES = ('termine', 'terminee', 'annule', 'realise', 'realisee', 'cloture', 'clos')


def _jour(d):
    if d is None:
        return None
    return d.date() if isinstance(d, datetime) else d


def _lien(endpoint, **k):
    try:
        return url_for(endpoint, **k)
    except Exception:
        return None


def taches(u, aujourd_hui=None):
    """Liste de tâches {type, titre, sous_titre, echeance, retard_jours, lien, priorite} de l'utilisateur u."""
    aujourd_hui = aujourd_hui or date.today()
    horizon = aujourd_hui + timedelta(days=14)
    t = []

    def ajout(type_, titre, sous_titre, echeance, lien, priorite_base=2):
        e = _jour(echeance)
        retard = (aujourd_hui - e).days if e and e < aujourd_hui else 0
        prio = 0 if retard else (1 if e and e <= aujourd_hui + timedelta(days=7) else priorite_base)
        t.append({'type': type_, 'titre': titre, 'sous_titre': sous_titre, 'echeance': e,
                  'retard_jours': retard, 'lien': lien, 'priorite': prio})

    def bloc(nom, fonction):
        try:
            fonction()
        except Exception as e:  # un module en erreur ne doit pas vider la page
            current_app.logger.warning("Ma semaine — %s : %s", nom, e)

    def plans():
        from models import PlanAction
        for p in PlanAction.query.filter_by(responsable_id=u.id, is_archived=False).all():
            if (p.statut or '') in TERMINES:
                continue
            ajout("Plan d'action", p.nom, f"{p.reference} · {p.pourcentage_realisation or 0} % réalisé",
                  p.date_fin_prevue, _lien('detail_plan_action', plan_id=p.id))

    def recommandations():
        # Toutes origines (audit, N2, externes) via le registre commun ; lien vers la fiche de suivi
        from egalyx.recommandations import registre, peut_decider_cloture, est_gestionnaire, module_actif
        if not u.client_id:
            return
        avec_registre = module_actif('externe')
        for l in registre(u.client_id, responsable_id=u.id):
            if l['statut'] in ('ouverte', 'en_cours'):
                lien = (_lien('recommandations.fiche', source=l['type'], reco_id=l['id']) if avec_registre else l['lien'])
                ajout('Recommandation', l['titre'][:120], f"{l['reference']} · {l['progression']} %", l['echeance'], lien)
        if est_gestionnaire(u):
            for l in registre(u.client_id):
                if peut_decider_cloture(l, u):
                    ajout('Clôture à valider', l['titre'][:120], l['reference'], l['echeance'],
                          _lien('recommandations.fiche', source=l['type'], reco_id=l['id']), 1)

    def evaluations():
        from models import EvaluationRisque
        q = EvaluationRisque.query.filter(EvaluationRisque.statut_validation.in_(['en_attente', 'a_revoir']),
                                          EvaluationRisque.referent_pre_evaluation_id == u.id).all()
        if est_admin_client(u):
            q += [e for e in EvaluationRisque.query.filter_by(statut_validation='en_attente_admin').all()
                  if e.risque and e.risque.client_id == u.client_id]
        # Valideur désigné des évaluations des opérateurs (Paramètres > Risques)
        from egalyx.parametres_risque import est_valideur_operateurs, valideur_de_l_evaluation
        from models import User
        if u.client_id and est_valideur_operateurs(u):
            for e in EvaluationRisque.query.filter_by(statut_validation='en_attente', client_id=u.client_id).all():
                ref = User.query.get(e.referent_pre_evaluation_id) if e.referent_pre_evaluation_id else None
                v = valideur_de_l_evaluation(e)
                if (ref is not None and getattr(ref, 'is_operateur', False) and v is not None and v.id == u.id
                        and e not in q):
                    e.statut_validation_affiche = 'a_valider'
                    q.append(e)
        for e in q:
            r = e.risque
            if r is None:
                continue
            fin = e.campagne_date_fin or (e.created_at + timedelta(days=15) if e.created_at else None)
            libelle = 'à valider' if getattr(e, 'statut_validation_affiche', None) == 'a_valider' else \
                {'a_revoir': 'à revoir', 'en_attente_admin': 'à valider'}.get(e.statut_validation, 'à évaluer')
            ajout('Évaluation de risque', r.intitule, f"{r.reference} · {libelle}", fin,
                  (_lien('operateur_evaluer_risque', risque_id=r.id) if getattr(u, 'is_operateur', False)
                   else _lien('evaluer_risque_triphase', id=r.id)), 1)

    def kri():
        from models import KRI
        for k in KRI.query.filter_by(responsable_mesure_id=u.id, est_actif=True).all():
            m = k.get_derniere_mesure()
            from egalyx.kri_suivi import periode_jours   # « mensuel », « trimestriel »… (les anciennes clés au féminin ne correspondaient pas au formulaire)
            periode = periode_jours(k)
            derniere = _jour(m.date_mesure) if m else None
            echeance = (derniere + timedelta(days=periode)) if derniere else aujourd_hui
            if echeance <= horizon:
                ajout('Mesure de KRI', k.nom, f"Dernière mesure : {derniere.strftime('%d/%m/%Y') if derniere else 'jamais'}",
                      echeance, _lien('detail_kri', kri_id=k.id))

    def tiers_revues():
        from models import Tiers
        for x in Tiers.query.filter_by(responsable_id=u.id, is_archived=False).all():
            if x.date_prochaine_revue and x.date_prochaine_revue <= horizon:
                ajout('Revue de tiers', x.nom, f"{x.reference} · vigilance {x.niveau_vigilance or '—'}",
                      x.date_prochaine_revue, _lien('tiers.detail', tid=x.id))

    def alertes():
        from egalyx.alerte import est_referent
        from models import Signalement
        if not est_referent(u):
            return
        for s in Signalement.query.filter_by(client_id=u.client_id).all():
            if s.est_cloture:
                continue
            if not s.date_accuse_reception:
                ajout('Alerte interne', 'Accuser réception du signalement ' + s.code_suivi, s.categorie_libelle,
                      s.echeance_accuse, _lien('alertes.detail', sid=s.id), 0)
            elif not s.date_retour_information:
                ajout('Alerte interne', "Informer le lanceur d'alerte des suites — " + s.code_suivi, s.categorie_libelle,
                      s.echeance_retour, _lien('alertes.detail', sid=s.id))

    def campagnes():
        from egalyx.circuit_controle import campagnes_a_valider
        for c in campagnes_a_valider(u):
            ajout('Campagne à valider', c.nom, c.reference, c.date_soumission,
                  _lien('detail_campagne_controle', campagne_id=c.id), 1)

    def procedures():
        from models import ProcessusActivite
        if not u.client_id:
            return
        gest = u.has_permission('can_manage_logigram')
        for a in ProcessusActivite.query.filter_by(client_id=u.client_id, is_archived=False).all():
            st = a.statut_validation or 'brouillon'
            if gest and st == 'en_validation' and a.soumis_par_id != u.id:
                ajout('Procédure à valider', a.nom, 'Logigramme soumis à validation', a.soumis_le,
                      _lien('logigrammes.suivi', activite_id=a.id), 1)
            if a.proprietaire_id == u.id and a.date_revue_prevue and a.date_revue_prevue <= horizon:
                ajout('Revue de procédure', a.nom, f"Version {a.version_courante or 0} · revue annuelle", a.date_revue_prevue,
                      _lien('logigrammes.suivi', activite_id=a.id))

    def pca():
        from egalyx import pca as _pca
        _pca.taches(u, ajout, horizon, aujourd_hui, _lien)

    def qualite():
        from egalyx import qualite as _q
        _q.taches(u, ajout, horizon, aujourd_hui, _lien)

    def dispositifs():
        from egalyx import maitrise as _d
        _d.taches(u, ajout, horizon, aujourd_hui, _lien)

    def incidents():
        from egalyx import incidents as _i
        _i.taches(u, ajout, horizon, aujourd_hui, _lien)

    def signalements():
        from egalyx import signalements as _s
        _s.taches(u, ajout, horizon, aujourd_hui, _lien)

    from egalyx.modules_client import permission_autorisee_par_module as module_ok
    # Une tâche n'apparaît que si le module correspondant est activé pour l'organisation
    for nom, f, perm in (('plans', plans, 'can_view_action_plans'), ('recommandations', recommandations, 'can_view_dashboard'),
                         ('évaluations', evaluations, 'can_manage_risks'), ('KRI', kri, 'can_manage_kri'),
                         ('tiers', tiers_revues, 'can_view_tiers'), ('alertes', alertes, 'can_manage_alertes'),
                         ('campagnes', campagnes, 'can_manage_campaigns'), ('procédures', procedures, 'can_manage_logigram'),
                         ('PCA', pca, 'can_manage_bcp'), ('qualité', qualite, 'can_manage_quality'),
                         ('incidents', incidents, 'can_view_incidents'), ('dispositifs', dispositifs, 'can_manage_risks'), ('signalements', signalements, 'can_view_tickets')):
        if module_ok(u, perm):
            bloc(nom, f)
    t.sort(key=lambda x: (x['priorite'], x['echeance'] or date.max))
    return t


@bp.route('/ma-semaine')
@connexion_requise
def page():
    lst = taches(current_user)
    resume = {'retard': sum(1 for x in lst if x['retard_jours']),
              'semaine': sum(1 for x in lst if not x['retard_jours'] and x['priorite'] == 1),
              'total': len(lst)}
    return render_template('egalyx/ma_semaine.html', taches=lst, resume=resume, aujourd_hui=date.today())


# ====================================================================== démarrage guidé
def etapes_demarrage(cid):
    """Étapes de mise en route d'une organisation, avec leur état réel en base."""
    from models import (User, Pole, Direction, Cartographie, Risque, EvaluationRisque, ParametresRisque,
                        Processus, Tiers, Audit)

    def compte(q):
        try:
            return q.count()
        except Exception:
            return 0
    admins = [u for u in User.query.filter_by(client_id=cid, is_active=True).all() if est_admin_client(u)]
    nb_risques = compte(Risque.query.filter_by(client_id=cid, is_archived=False))
    nb_eval = compte(EvaluationRisque.query.join(Risque, Risque.id == EvaluationRisque.risque_id)
                     .filter(Risque.client_id == cid))
    p = ParametresRisque.query.filter_by(client_id=cid).first()

    def nieme(q, colonne, rang=1):
        """Date du rang-ième objet (jalon : quand l'étape a été atteinte)."""
        try:
            r = q.filter(colonne.isnot(None)).order_by(colonne.asc()).offset(rang - 1).first()
            return getattr(r, colonne.key, None) if r is not None else None
        except Exception:
            return None
    date_eval = EvaluationRisque.date_pre_evaluation
    jalons = [
        min([d for d in (nieme(Direction.query.filter_by(client_id=cid), Direction.created_at),
                         nieme(Pole.query.filter_by(client_id=cid), Pole.created_at)) if d] or [None], key=lambda x: x or datetime.max),
        nieme(User.query.filter_by(client_id=cid, is_active=True), User.created_at, 2),
        None,
        nieme(Cartographie.query.filter_by(client_id=cid), Cartographie.created_at),
        nieme(Risque.query.filter_by(client_id=cid, is_archived=False), Risque.created_at, 10),
        nieme(EvaluationRisque.query.join(Risque, Risque.id == EvaluationRisque.risque_id).filter(Risque.client_id == cid),
              date_eval, max(1, min(nb_risques, 10))),
        getattr(p, 'updated_at', None),
        nieme(Processus.query.filter_by(client_id=cid), Processus.created_at),
        nieme(Tiers.query.filter_by(client_id=cid), Tiers.created_at),
        nieme(Audit.query.filter_by(client_id=cid), Audit.created_at),
    ]
    e = [
        ('Décrire l’organisation', 'Pays, pôles et directions : la base des cartographies et du tableau de bord par entité.',
         compte(Direction.query.filter_by(client_id=cid)) > 0 or compte(Pole.query.filter_by(client_id=cid)) > 0,
         _lien('admin_directions')),
        ('Inviter l’équipe', 'Au moins un autre utilisateur : propriétaires de risques, auditeurs, responsables d’actions.',
         compte(User.query.filter_by(client_id=cid, is_active=True)) > 1, _lien('client_admin_utilisateurs')),
        ('Sécuriser les comptes administrateurs', 'Double authentification activée pour chaque administrateur.',
         bool(admins) and all(getattr(a, 'totp_actif', False) for a in admins), _lien('securite_compte.index')),
        ('Créer une cartographie', 'Une cartographie par direction, processus ou entité.',
         compte(Cartographie.query.filter_by(client_id=cid, is_archived=False)) > 0, _lien('liste_cartographies')),
        ('Identifier au moins 10 risques', 'Importez votre cartographie Excel telle quelle, ou partez de la bibliothèque '
         'sectorielle (84 risques types et leurs contrôles).', nb_risques >= 10, _lien('import_carto.page') or _lien('bibliotheque.page')),
        ('Évaluer les risques', 'Impact, probabilité et niveau de maîtrise : cotation brute et nette.',
         nb_eval > 0 and nb_eval >= min(nb_risques, 10), _lien('liste_cartographies')),
        ('Fixer l’appétence au risque', 'Le score net maximal accepté par la direction, global et par catégorie.',
         bool(p and (p.appetence_score_net is not None or p.appetence_par_categorie)), _lien('parametres_risque.page')),
        ('Décrire un processus clé', 'Étapes, organigramme et contrôles rattachés aux risques.',
         compte(Processus.query.filter_by(client_id=cid)) > 0, _lien('liste_processus_metier')),
        ('Recenser les tiers sensibles', 'Fournisseurs critiques, clients et partenaires : vigilance LCB-FT et criblage.',
         compte(Tiers.query.filter_by(client_id=cid, is_archived=False)) > 0, _lien('tiers.liste')),
        ('Planifier un audit', 'Premier audit interne ou mission de contrôle.',
         compte(Audit.query.filter_by(client_id=cid)) > 0, _lien('nouvel_audit')),
    ]
    from models import Client
    client = Client.query.get(cid)
    ouverture = getattr(client, 'created_at', None)

    def jours(d):
        if not d or not ouverture:
            return None
        return max(0, (d - ouverture).days)
    etapes = [{'titre': a, 'aide': b, 'fait': bool(c), 'lien': d,
               'atteint_le': jalons[i] if c else None, 'jours': jours(jalons[i]) if c else None}
              for i, (a, b, c, d) in enumerate(e)]
    if _lien('bibliotheque.page') and etapes[4]['lien'] != _lien('bibliotheque.page'):
        etapes[4]['lien_bis'] = (_lien('bibliotheque.page'), 'Bibliothèque')
    faites = sum(1 for x in etapes if x['fait'])
    # Délai de mise en valeur : de l'ouverture du compte à la première cartographie évaluée
    valeur = etapes[5]['jours'] if etapes[5]['fait'] else None
    return {'etapes': etapes, 'faites': faites, 'total': len(etapes), 'ouverture': ouverture,
            'jours_ouverture': jours(datetime.utcnow()), 'delai_valeur': valeur,
            'pourcentage': round(100 * faites / len(etapes))}


@bp.route('/demarrage')
@admin_client_requis
def demarrage():
    return render_template('egalyx/demarrage.html', d=etapes_demarrage(client_id_courant()))


def enregistrer(app):
    app.register_blueprint(bp)
