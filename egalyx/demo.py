"""
egalyx/demo.py — organisation de démonstration complète, en un clic (super admin) ou par
`flask creer-demo`.

« Sahel Finance (démonstration) » : établissement fictif présent en Côte d'Ivoire et au Sénégal,
avec organisation, utilisateurs, cartographies, risques évalués sur 6 mois (tendances visibles),
dispositifs de maîtrise, plans d'action (dont en retard), incidents, KRI avec historique,
deux audits avec constatations et recommandations, tiers LCB-FT, un signalement, un processus
avec son organigramme et ses contrôles, et l'appétence au risque.

Chaque partie est créée dans sa propre transaction imbriquée : si l'une échoue (modèle
différent dans votre version), les autres sont conservées et l'erreur est signalée.
Toutes les données sont fictives.
"""
import random
import secrets
from datetime import date, datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for

from egalyx.commun import super_admin_requis

bp = Blueprint('demo', __name__, url_prefix='/super-admin/demo')

DIRECTIONS = [  # (pays, pôle, direction, secteur de la bibliothèque, catégories prises)
    ('CIV', 'Exploitation', 'Direction du crédit', 'banque', ('Crédit',)),
    ('CIV', 'Exploitation', 'Direction des opérations', 'banque', ('Opérationnel', 'Fraude', 'Externalisation')),
    ('CIV', 'Fonctions support', 'Direction financière', 'banque', ('Financier', 'Marché')),
    ('CIV', 'Fonctions support', 'Direction des systèmes d’information', 'transverse', ("Systèmes d'information",)),
    ('SEN', 'Conformité et contrôle', 'Direction de la conformité', 'banque', ('Conformité', 'LCB-FT')),
    ('SEN', 'Conformité et contrôle', 'Direction des ressources humaines', 'transverse', ('Ressources humaines', 'Éthique', 'Santé et sécurité')),
]


def _mot_de_passe():
    return 'Demo-' + secrets.token_hex(4) + 'Kx7!'


def creer_demo(db, avec_alerte=True, graine=7):
    """Crée l'organisation de démonstration. Retourne (client, identifiants, rapport)."""
    import models as M
    from egalyx import calculs
    from egalyx.bibliotheque import importer
    from egalyx.bibliotheque_donnees import risques_du_secteur
    hasard = random.Random(graine)
    maintenant = datetime.utcnow()
    aujourd_hui = date.today()
    rapport = []

    n = 1
    while M.Client.query.filter_by(reference=f'DEMO{n:02d}').first():
        n += 1
    ref = f'DEMO{n:02d}'
    client = M.Client(nom='Sahel Finance (démonstration)', reference=ref, contact_nom='Awa Diallo',
                      contact_email=f'contact.{ref.lower()}@exemple.invalid', is_active=True,
                      date_activation=maintenant, date_expiration=maintenant + timedelta(days=365))
    db.session.add(client)
    db.session.flush()
    cid = client.id
    ctx = {'cid': cid}

    def etape(nom, fonction):
        sp = db.session.begin_nested()
        try:
            res = fonction()
            sp.commit()
            rapport.append((nom, True, res))
        except Exception as e:
            sp.rollback()
            rapport.append((nom, False, f'{type(e).__name__} : {e}'[:300]))

    # ---------------------------------------------------------------- utilisateurs
    identifiants = []

    def utilisateurs():
        profils = [('admin', 'Awa Diallo', 'admin', True), ('risques', 'Koffi Yao', 'manager', False),
                   ('auditeur', 'Mariam Ndiaye', 'auditeur', False), ('conformite', 'Ibrahima Sow', 'compliance', False)]
        for code, nom, role, est_admin in profils:
            mdp = _mot_de_passe()
            u = M.User(username=f'{code}_{ref.lower()}', email=f'{code}.{ref.lower()}@exemple.invalid', role=role,
                       client_id=cid, is_client_admin=est_admin, is_active=True, department=nom)
            try:
                u.set_password(mdp, check_history=False)
            except TypeError:
                u.set_password(mdp)
            db.session.add(u)
            db.session.flush()
            ctx['u_' + code] = u
            identifiants.append((u.username, mdp, role))
        return f'{len(profils)} comptes'
    etape('Utilisateurs', utilisateurs)
    admin_id = getattr(ctx.get('u_admin'), 'id', None)
    auteurs = [getattr(ctx.get('u_' + k), 'id', None) for k in ('admin', 'risques', 'auditeur', 'conformite')]

    # ---------------------------------------------------------------- organisation et cartographies
    def organisation():
        pays = {}
        for code, nom in (('CIV', "Côte d'Ivoire"), ('SEN', 'Sénégal')):
            p = M.Pays(nom=nom, code=code, client_id=cid, created_by=admin_id)
            db.session.add(p); db.session.flush(); pays[code] = p
        poles, cartos = {}, []
        for code_pays, nom_pole, nom_dir, secteur, cats in DIRECTIONS:
            cle = (code_pays, nom_pole)
            if cle not in poles:
                po = M.Pole(nom=nom_pole, pays_id=pays[code_pays].id, client_id=cid, created_by=admin_id)
                db.session.add(po); db.session.flush(); poles[cle] = po
            d = M.Direction(nom=nom_dir, pole_id=poles[cle].id, client_id=cid, is_active=True)
            db.session.add(d); db.session.flush()
            c = M.Cartographie(nom=f'Risques — {nom_dir}', description='Cartographie de démonstration.',
                               pays_id=pays[code_pays].id, pole_id=poles[cle].id, direction_id=d.id,
                               type_cartographie='direction', client_id=cid, created_by=admin_id)
            db.session.add(c); db.session.flush()
            cartos.append((c, secteur, cats, d))
        ctx['cartos'] = cartos
        return f'2 pays, {len(poles)} pôles, {len(cartos)} directions et cartographies'
    etape('Organisation', organisation)

    def risques():
        tous = []
        for c, secteur, cats, _d in ctx.get('cartos', []):
            indices = {r['index'] for r in risques_du_secteur(secteur) if r['categorie'] in cats}
            tous += importer(cid, c, secteur, indices, admin_id)
        db.session.flush()
        ctx['risques'] = tous
        return f'{len(tous)} risques issus de la bibliothèque'
    etape('Risques', risques)

    def evaluations():
        nb = 0
        for i, r in enumerate(ctx.get('risques', [])):
            base_i = {'negligeable': 1, 'mineur': 2, 'modere': 3, 'majeur': 4, 'critique': 5}.get(r.impact, 3)
            base_p = {'tres_rare': 1, 'rare': 2, 'possible': 3, 'probable': 4, 'frequente': 5}.get(r.probabilite, 3)
            # trois campagnes : 6 mois, 3 mois, il y a 10 jours ; certains risques se dégradent, d'autres s'améliorent
            tendance = hasard.choice([-1, 0, 0, 1])
            for k, jours in enumerate((170, 85, 10)):
                p = max(1, min(5, base_p + (tendance if k == 2 else 0) + hasard.choice([0, 0, -1, 1]) * (k == 0)))
                m = max(1, min(5, hasard.choice([2, 3, 3, 4]) + (1 if k == 2 and tendance < 0 else 0)))
                d = maintenant - timedelta(days=jours)
                ev = M.EvaluationRisque(risque_id=r.id, client_id=cid, impact_conf=base_i, probabilite_conf=p,
                                        niveau_maitrise_conf=m, impact_pre=base_i, probabilite_pre=p, niveau_maitrise_pre=m,
                                        statut_validation='valide', evaluateur_final_id=admin_id,
                                        referent_pre_evaluation_id=auteurs[1] or admin_id,
                                        date_pre_evaluation=d, date_confirmation=d, created_at=d,
                                        campagne_nom=f"Campagne {d:%m/%Y}", type_evaluation='confirmation')
                db.session.add(ev)
                nb += 1
        # Deux risques encore à évaluer (pour « Ma semaine »)
        for r in ctx.get('risques', [])[:2]:
            db.session.add(M.EvaluationRisque(risque_id=r.id, client_id=cid, statut_validation='en_attente',
                                              referent_pre_evaluation_id=auteurs[1] or admin_id,
                                              campagne_nom='Campagne en cours',
                                              campagne_date_fin=aujourd_hui + timedelta(days=5)))
        db.session.flush()
        return f'{nb} évaluations sur 6 mois'
    etape('Évaluations', evaluations)

    def parametres():
        db.session.add(M.ParametresRisque(
            client_id=cid, seuil_faible=4, seuil_moyen=10, seuil_eleve=16,
            taux_maitrise={'1': 0, '2': 0.1, '3': 0.25, '4': 0.4, '5': 0.6}, appetence_score_net=10,
            appetence_par_categorie={'Conformité': 6, 'LCB-FT': 6},
            appetence_declaration="Aucune tolérance pour les manquements de conformité et de LCB-FT. "
                                  "Tolérance modérée pour les risques opérationnels dès lors qu'ils sont suivis.",
            pays_liste_noire=list(calculs.GAFI_LISTE_NOIRE_2026_06), pays_liste_grise=list(calculs.GAFI_LISTE_GRISE_2026_06),
            listes_gafi_maj_le=date(2026, 6, 19), seuil_montant_lcb=100_000_000, updated_by=admin_id))
        db.session.flush()
        return 'appétence globale 10, conformité et LCB-FT 6'
    etape('Appétence au risque', parametres)

    def dispositifs_plans():
        rs = ctx.get('risques', [])
        disp = {}
        for i, r in enumerate(rs):
            d = M.DispositifMaitrise(risque_id=r.id, reference=f'DMR-{i + 1:03d}', nom=f'Contrôle clé — {r.intitule[:80]}',
                                     type_dispositif=hasard.choice(['preventif', 'detectif']), statut='actif',
                                     efficacite_attendue=4, efficacite_reelle=hasard.choice([2, 3, 3, 4]), client_id=cid)
            db.session.add(d)
            disp[r.id] = d
        db.session.flush()
        ctx['dispositifs'] = disp
        noms = ["Renforcer la séparation des tâches en agence", "Déployer le filtrage automatique des virements",
                "Mettre à jour la politique de crédit", "Tester le plan de continuité informatique",
                "Former les chargés de clientèle au KYC", "Automatiser les rapprochements bancaires",
                "Revoir les habilitations du système central", "Mettre en place la double validation des paiements"]
        responsables = [x for x in auteurs if x]
        for i, nom in enumerate(noms):
            fin = aujourd_hui + timedelta(days=[-45, -12, 20, 60, -3, 35, 90, 7][i])
            db.session.add(M.PlanAction(reference=f'PA-2026-{i + 1:03d}', nom=nom, description=nom + '.',
                                        date_debut=aujourd_hui - timedelta(days=90), date_fin_prevue=fin,
                                        statut='en_cours', pourcentage_realisation=[30, 55, 40, 10, 80, 25, 0, 60][i],
                                        priorite=['haute', 'haute', 'moyenne', 'moyenne', 'haute', 'basse', 'moyenne', 'haute'][i],
                                        risque_id=rs[i % len(rs)].id if rs else None,
                                        responsable_id=responsables[i % len(responsables)] if responsables else None,
                                        created_by=admin_id, client_id=cid))
        db.session.flush()
        return f'{len(disp)} dispositifs, {len(noms)} plans d’action (3 en retard)'
    etape('Dispositifs et plans d’action', dispositifs_plans)

    def incidents():
        rs, disp = ctx.get('risques', []), ctx.get('dispositifs', {})
        if not rs or not disp:
            return 'ignoré (pas de risque)'
        cas = [("Virement frauduleux après changement de RIB fournisseur", 'critique', 12, 18_500_000),
               ("Indisponibilité du système central pendant 6 heures", 'elevee', 25, 4_000_000),
               ("Écart de caisse en agence de Plateau", 'moyenne', 33, 750_000),
               ("Dossier de crédit accordé sans comité", 'elevee', 41, 0),
               ("Tentative d'hameçonnage ciblant la direction financière", 'faible', 50, 0),
               ("Retard de déclaration réglementaire", 'moyenne', 58, 1_200_000)]
        for i, (titre, grav, jours, cout) in enumerate(cas):
            r = rs[(i * 3) % len(rs)]
            db.session.add(M.Incident(reference=f'INC-2026-{i + 1:03d}', titre=titre, description=titre + '.',
                                      gravite=grav, statut='ouvert' if i < 3 else 'resolu', type_incident='operationnel',
                                      cout_estime=cout, date_occurrence=maintenant - timedelta(days=jours),
                                      date_detection=maintenant - timedelta(days=jours), risque_id=r.id,
                                      dispositif_id=disp[r.id].id, client_id=cid, created_by=admin_id))
        db.session.flush()
        return f'{len(cas)} incidents sur 60 jours'
    etape('Incidents', incidents)

    def kri():
        rs = ctx.get('risques', [])
        defs = [("Taux de créances en souffrance", '%', 8, 12, [6.1, 6.8, 7.4, 8.2, 9.0, 9.7]),
                ("Délai moyen de traitement des alertes LCB-FT", 'jours', 10, 20, [14, 12, 11, 9, 8, 7]),
                ("Disponibilité du système central", '%', 99, 97, [99.6, 99.4, 98.8, 99.2, 97.5, 99.1]),
                ("Nombre d'écarts de caisse", 'nb/mois', 5, 10, [3, 4, 6, 4, 7, 11])]
        for i, (nom, unite, alerte, critique, valeurs) in enumerate(defs):
            sens = 'inferieur' if critique < alerte else 'superieur'
            k = M.KRI(nom=nom, unite_mesure=unite, seuil_alerte=alerte, seuil_critique=critique, sens_evaluation_seuil=sens,
                      frequence_mesure='mensuelle', type_indicateur='kri', est_actif=True, client_id=cid,
                      risque_id=rs[i % len(rs)].id if rs else None, responsable_mesure_id=auteurs[1] or admin_id,
                      created_by=admin_id)
            db.session.add(k); db.session.flush()
            for m, v in enumerate(valeurs):
                db.session.add(M.MesureKRI(kri_id=k.id, valeur=v, client_id=cid, created_by=admin_id,
                                           date_mesure=maintenant - timedelta(days=30 * (len(valeurs) - 1 - m) + 2)))
        db.session.flush()
        return f'{len(defs)} KRI × 6 mois'
    etape('Indicateurs de risque (KRI)', kri)

    def audits():
        rs = ctx.get('risques', [])
        auditeur = auteurs[2] or admin_id
        missions = [("Audit du processus d'octroi de crédit", 'termine', -150, -110,
                     [("Comités de crédit tenus sans quorum pour 4 dossiers sur 25", 'majeure'),
                      ("Garanties non enregistrées pour 3 crédits immobiliers", 'majeure'),
                      ("Fiches de notation incomplètes", 'mineure')]),
                    ("Audit du dispositif LCB-FT", 'en_cours', -40, 20,
                     [("Mises à jour KYC en retard pour 18 % des clients à risque élevé", 'majeure'),
                      ("Scénarios de surveillance non revus depuis 2023", 'moyenne')])]
        nb_c = nb_r = 0
        for j, (titre, statut, debut, fin, constats) in enumerate(missions):
            a = M.Audit(reference=f'AUD-2026-{j + 1:03d}', titre=titre, type_audit='interne', statut=statut,
                        description=titre + '.', objectifs="Évaluer la conception et l'efficacité des contrôles clés.",
                        date_debut_prevue=aujourd_hui + timedelta(days=debut), date_fin_prevue=aujourd_hui + timedelta(days=fin),
                        responsable_id=auditeur, created_by=auditeur, client_id=cid)
            db.session.add(a); db.session.flush()
            for k, (texte, grav) in enumerate(constats):
                c = M.Constatation(reference=f'CST-{j + 1}-{k + 1:02d}', description=texte, type_constatation='non_conformite',
                                   gravite=grav, statut='valide', audit_id=a.id, client_id=cid, created_by=auditeur,
                                   risque_id=rs[(j * 5 + k) % len(rs)].id if rs else None)
                db.session.add(c); db.session.flush(); nb_c += 1
                db.session.add(M.Recommandation(reference=f'REC-{j + 1}-{k + 1:02d}', description='Corriger : ' + texte[0].lower() + texte[1:],
                                                type_recommandation='corrective', urgence=3 if grav == 'majeure' else 1,
                                                impact_operationnel=3 if grav == 'majeure' else 1,
                                                date_echeance=aujourd_hui + timedelta(days=[-20, 15, 45, -5, 30][nb_r % 5]),
                                                statut='en_cours', taux_avancement=[40, 20, 0, 60, 10][nb_r % 5],
                                                audit_id=a.id, constatation_id=c.id, responsable_id=auteurs[1] or admin_id,
                                                created_by=auditeur, client_id=cid))
                nb_r += 1
        db.session.flush()
        return f'{len(missions)} audits, {nb_c} constatations, {nb_r} recommandations'
    etape('Audits', audits)

    def tiers():
        from egalyx.tiers import evaluer
        fiches = [("Kouamé Négoce SARL", 'fournisseur', "Côte d'Ivoire", 'Négoce de métaux précieux', True, 4, 45, False),
                  ("Teranga Informatique SA", 'fournisseur', 'Sénégal', 'Services informatiques', False, 4, 70, False),
                  ("Groupe Baobab Immobilier", 'client', "Côte d'Ivoire", 'Promotion immobilière', False, None, None, True),
                  ("Sahara Trading FZE", 'client', 'Émirats arabes unis', 'Change et transfert d\'argent', False, None, None, True),
                  ("Imprimerie du Plateau", 'fournisseur', "Côte d'Ivoire", 'Imprimerie', False, 1, 5, True),
                  ("Fondation Lumière d'Afrique", 'partenaire', 'Mali', 'ONG / association', True, None, None, True)]
        for i, (nom, typ, pays, secteur, ppe, impact, dep, subst) in enumerate(fiches):
            t = M.Tiers(client_id=cid, reference=f'TRS-{i + 1:04d}', type_tiers=typ, nature='personne_morale', nom=nom,
                        pays=pays, secteur=secteur, est_ppe=ppe, canal='distance' if i == 3 else 'presentiel',
                        beneficiaires_effectifs=[] if i in (3,) else [{'nom': 'Bénéficiaire fictif', 'part': 60, 'pays': pays, 'ppe': ppe}],
                        impact_arret=impact, dependance_pct=dep, substituable=subst, montant_relation=[2e8, 9e7, 5e8, 3e8, 1e7, 2e7][i],
                        date_derniere_revue=aujourd_hui - timedelta(days=[400, 200, 30, 380, 100, 50][i]),
                        responsable_id=auteurs[3] or admin_id, created_by=admin_id, statut='en_cours')
            db.session.add(t); db.session.flush()
            evaluer(t)
        db.session.flush()
        return f'{len(fiches)} tiers évalués'
    etape('Tiers et LCB-FT', tiers)

    def alerte():
        if not avec_alerte:
            return 'non demandé'
        from egalyx.alerte import nouveau_code_suivi
        from werkzeug.security import generate_password_hash
        s = M.Signalement(client_id=cid, code_suivi=nouveau_code_suivi(), mot_de_passe_hash=generate_password_hash(secrets.token_hex(8)),
                          categorie='conflit_interets', anonyme=True, statut='en_instruction', recevable=True,
                          referent_id=auteurs[3], created_at=maintenant - timedelta(days=20),
                          date_accuse_reception=maintenant - timedelta(days=18))
        s.description = ("Un responsable des achats attribuerait les marchés de fournitures à une société dirigée par "
                         "un membre de sa famille. (Signalement fictif de démonstration.)")
        db.session.add(s); db.session.flush()
        for auteur, texte, jours in (('lanceur', 'Je peux transmettre les bons de commande concernés.', 15),
                                     ('referent', 'Merci. Déposez-les ici ; votre identité reste protégée.', 14)):
            m = M.MessageSignalement(signalement_id=s.id, auteur=auteur, created_at=maintenant - timedelta(days=jours),
                                     referent_id=auteurs[3] if auteur == 'referent' else None)
            m.contenu = texte
            db.session.add(m)
        db.session.flush()
        return '1 signalement en instruction'
    etape('Dispositif d’alerte', alerte)

    def processus():
        rs = ctx.get('risques', [])
        cartos = ctx.get('cartos', [])
        p = M.Processus(nom="Octroi de crédit aux entreprises", description="De la demande au décaissement.",
                        direction_id=cartos[0][3].id if cartos else None, responsable_id=auteurs[1], version='2.1',
                        statut='actif', client_id=cid)
        db.session.add(p); db.session.flush()
        etapes = [("Réception de la demande", 'debut'), ("Analyse financière", 'action'), ("Comité de crédit", 'decision'),
                  ("Prise de garanties", 'action'), ("Décaissement", 'fin')]
        objs = []
        for i, (nom, typ) in enumerate(etapes):
            e = M.EtapeProcessus(processus_id=p.id, ordre=i + 1, nom=nom, type_etape=typ, client_id=cid,
                                 position_x=40 + i * 200, position_y=60 + (40 if typ == 'decision' else 0),
                                 largeur=160, hauteur=70 if typ == 'decision' else 60,
                                 couleur='#b54708' if typ == 'decision' else '#1A3C6B')
            db.session.add(e); db.session.flush(); objs.append(e)
        for a, b in zip(objs, objs[1:]):
            db.session.add(M.LienProcessus(processus_id=p.id, etape_source_id=a.id, etape_cible_id=b.id,
                                           label='accordé' if a.type_etape == 'decision' else None, client_id=cid))
        if rs:
            for i, (nom, et) in enumerate((("Vérification du quorum du comité", 2), ("Contrôle de l'enregistrement des garanties", 3))):
                db.session.add(M.ControleProcessus(reference=f'CTL-2026-{i + 1:04d}', nom=nom, type_controle='preventif',
                                                   frequence='permanent', statut='actif', risque_id=rs[0].id,
                                                   processus_id=p.id, etape_id=objs[et].id, client_id=cid,
                                                   responsable_id=auteurs[1], createur_id=admin_id))
        p.nb_etapes, p.nb_liens = len(objs), len(objs) - 1
        db.session.flush()
        return '1 processus, 5 étapes, organigramme et 2 contrôles'
    etape('Processus et organigramme', processus)

    db.session.commit()
    return client, identifiants, rapport


@bp.route('/', methods=['GET', 'POST'])
@super_admin_requis
def page():
    from models import db, Client
    if request.method == 'POST':
        try:
            client, ids, rapport = creer_demo(db)
        except Exception as e:
            db.session.rollback()
            flash(f'Démonstration non créée : {e}', 'danger')
            return redirect(url_for('.page'))
        return render_template('egalyx/demo.html', client=client, identifiants=ids, rapport=rapport, demos=None)
    demos = Client.query.filter(Client.reference.like('DEMO%')).order_by(Client.id.desc()).all()
    return render_template('egalyx/demo.html', client=None, identifiants=None, rapport=None, demos=demos)


def enregistrer(app):
    app.register_blueprint(bp)

    @app.cli.command('creer-demo')
    def _cli_demo():
        """Crée une organisation de démonstration complète (données fictives)."""
        from models import db
        client, ids, rapport = creer_demo(db)
        print(f"✅ Organisation de démonstration : {client.nom} ({client.reference})")
        for nom, ok, detail in rapport:
            print(f"  {'✅' if ok else '⚠️ '} {nom} : {detail}")
        print("Comptes (notez les mots de passe, ils ne seront plus affichés) :")
        for u, mdp, role in ids:
            print(f"  {u} / {mdp}  ({role})")
