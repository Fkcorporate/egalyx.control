"""Recette : profil réglementaire par organisation (Côte d'Ivoire / UEMOA, France / UE).

Choix par le super admin (devise et fuseau appliqués), lecture seule pour l'organisation, profil déduit de la devise,
adaptation de l'analyse de données (seuils en euros, jours fériés, comptes, textes), contexte réglementaire de l'IA."""
import os
import re
from datetime import date

os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
import models as M
from models import db
from egalyx import profil_reglementaire as pr, analyse_moteur as am

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


def jeton(c, url):
    t = appel(c, 'get', url).data.decode(errors='ignore')
    m = re.search(r'name="csrf_token" value="([^"]+)"', t) or re.search(r'name="csrf-token" content="([^"]+)"', t)
    return m.group(1) if m else ''


sa, admin, gest, admin_b = (socle.navigateur(A, ids[r]) for r in ('superadmin', 'admin_a', 'gestionnaire', 'admin_b'))

print('--- 1. Profil par défaut')
verif('Pâques 2026 : 5 avril (lundi de Pâques 06/04, Ascension 14/05, Pentecôte 25/05)', pr._paques(2026) == date(2026, 4, 5)
      and [d.isoformat() for d in pr.feries_mobiles([2026])] == ['2026-04-06', '2026-05-14', '2026-05-25'])
with A.app.app_context():
    c = db.session.get(M.Client, 1); c.devise = None; db.session.get(M.Client, 2).devise = 'EUR'; db.session.commit()
    verif('sans choix : déduit de la devise (aucune → Côte d’Ivoire / UEMOA ; EUR → France / UE)', pr.code_profil(1) == 'uemoa' and pr.code_profil(2) == 'france')

print('--- 2. Choix par le super admin')
r = appel(sa, 'get', '/super-admin/client/1/reglages')
verif('réglages de l’organisation : carte « Profil réglementaire » avec les deux profils', r.status_code == 200
      and 'Côte d’Ivoire / UEMOA (OHADA)'.encode() in r.data and 'France / Union européenne'.encode() in r.data and b'name="profil"' in r.data)
r = appel(admin, 'post', '/super-admin/client/1/profil-reglementaire', data={'csrf_token': jeton(admin, '/dashboard'), 'profil': 'france'})
verif('administrateur de l’organisation : changement refusé', r.status_code == 403, r.status_code)
r = appel(sa, 'post', '/super-admin/client/1/profil-reglementaire', data={'csrf_token': jeton(sa, '/super-admin/client/1/reglages'), 'profil': 'france',
                                                                          'appliquer_localisation': '1'})
with A.app.app_context():
    c = db.session.get(M.Client, 1)
    verif('profil France / UE appliqué, avec l’euro et le fuseau de Paris', pr.code_profil(1) == 'france' and pr.choisi(1)
          and c.devise == 'EUR' and c.fuseau_horaire == 'Europe/Paris', (c.devise, c.fuseau_horaire))
r = appel(sa, 'get', '/super-admin/organisations/reglages')
verif('vue d’ensemble : colonne « Profil réglementaire »', r.status_code == 200 and 'Profil réglementaire'.encode() in r.data and b'France / UE' in r.data)
r = appel(admin, 'get', '/organisation/heure-devise')
if r.status_code in (301, 302):
    r = appel(admin, 'get', r.location)
verif('organisation : profil affiché en lecture seule', r.status_code == 200 and 'France / Union européenne'.encode() in r.data
      and b'name="profil"' not in r.data, r.status_code)

print('--- 3. Analyse de données adaptée')
with A.app.app_context():
    tf = pr.tests_par_code(1)
    feries = dict((c_, d) for c_, _l, d, _a in tf['WEEKEND']['params'])['feries']
    verif('France : jours fériés français (14/07, 11/11, lundi de Pâques calculé)', '14/07' in feries and '11/11' in feries and '06/04/2026' in feries
          and '07/08' not in feries)
    verif('France : comptes sensibles du plan comptable général (455, 512, 53)', dict((c_, d) for c_, _l, d, _a in tf['GL_SENSIBLES']['params'])['comptes'].startswith('455'))
    verif('France : seuils en euros (fractionnement 10 000 €, dépôts en espèces 10 000 €)',
          dict((c_, d) for c_, _l, d, _a in tf['FRACTIONNEMENT']['params'])['seuil'] == 10_000
          and dict((c_, d) for c_, _l, d, _a in tf['LCB_FRACTIONNEMENT']['params'])['seuil'] == 10_000)
    verif('France : textes adaptés (Tracfin, Code monétaire et financier, plan comptable général)', 'Tracfin' in tf['LCB_FRACTIONNEMENT']['recommandation']
          and 'Code monétaire et financier' in tf['KYC_INCOMPLET']['critere'] and 'plan comptable général' in tf['GL_DESEQUILIBRE']['critere']
          and 'CENTIF' not in str(tf))
    c = db.session.get(M.Client, 1); conf = M.ClientConfiguration.query.filter_by(client_id=1).first()
    conf.preferences = dict(conf.preferences, profil_reglementaire='uemoa'); db.session.commit()
    tu = pr.tests_par_code(1)
    verif('Côte d’Ivoire : CENTIF, BCEAO, SYSCOHADA, seuils en FCFA, fêtes ivoiriennes', 'CENTIF' in tu['LCB_FRACTIONNEMENT']['recommandation']
          and 'BCEAO' in tu['CRD_SOUFFRANCE']['critere'] and 'SYSCOHADA' in tu['GL_DESEQUILIBRE']['critere']
          and dict((c_, d) for c_, _l, d, _a in tu['FRACTIONNEMENT']['params'])['seuil'] == 5_000_000
          and '07/08' in dict((c_, d) for c_, _l, d, _a in tu['WEEKEND']['params'])['feries'])
    conf.preferences = dict(conf.preferences, profil_reglementaire='france'); db.session.commit()
    import pandas as pd
    df = pd.DataFrame({'_ligne': [2, 3], 'numero': ['A', 'B'], 'fournisseur': ['F1', 'F1'], 'date': pd.to_datetime(['2026-03-02', '2026-03-03']),
                       'montant': [6000.0, 5000.0], 'commande': ['', ''], 'date_saisie': pd.NaT, 'saisi_par': ['', ''], 'devise': ['', '']})
    r = am.executer({'factures': df}, ['FRACTIONNEMENT'], {}, devise='€', defauts=pr.defauts_tests(1))
    verif('exécution : seuil du profil appliqué (2 factures de 6 000 et 5 000 € → fractionnement sous 10 000 €)',
          r['FRACTIONNEMENT']['parametres']['seuil'] == 10_000 and r['FRACTIONNEMENT']['cas'] == 1, r['FRACTIONNEMENT']['parametres'])
    from egalyx.localisation import devise
    verif('symbole de la devise pour les montants : €', devise(1) == '€')

print('--- 4. IA : références du profil')
with A.app.test_request_context():
    from flask_login import login_user
    login_user(db.session.get(M.User, ids['admin_a']))
    from egalyx.ia_moteur import _contexte_reglementaire
    t = _contexte_reglementaire()
    verif('consignes de l’IA : contexte France (Tracfin, RGPD), jamais la CENTIF', 'Tracfin' in t and 'RGPD' in t and 'CENTIF' not in t)
with A.app.test_request_context():
    from flask_login import login_user
    login_user(db.session.get(M.User, ids['admin_b']))
    conf2 = M.ClientConfiguration.query.filter_by(client_id=2).first()
    if conf2 is None:
        conf2 = M.ClientConfiguration(client_id=2, couleurs={}, preferences={}); db.session.add(conf2)
    conf2.preferences = dict(conf2.preferences or {}, profil_reglementaire='uemoa'); db.session.commit()
    t = _contexte_reglementaire()
    verif('autre organisation (Côte d’Ivoire) : CENTIF, SYSCOHADA', 'CENTIF' in t and 'SYSCOHADA' in t)

print('--- 5. Aide')
from egalyx.aide_contenu import ARTICLES
verif('centre d’aide : article « Profil réglementaire »', any(a['id'] == 'profil_reglementaire' for a in ARTICLES))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
raise SystemExit(0 if all(res) else 1)
