"""Recette : analyse IA d'une cartographie — score calculé, recommandations, rédaction IA vérifiée et mémorisée."""
import datetime as dt
import socle
from socle import Muet
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
import objets
import models as M
from models import db
from egalyx import ia_cartographie as IA
with Muet():
    try: objets.peupler_objets(A, ids)
    except TypeError: objets.peupler_objets(A)

with A.app.app_context():
    ua = db.session.get(M.User, ids['admin_a']); cid = ua.client_id
    vide = M.Cartographie(nom='Carto vide', client_id=cid); db.session.add(vide); db.session.commit(); vide_id = vide.id
    carto = M.Cartographie(nom='Carto test IA', client_id=cid); db.session.add(carto); db.session.commit(); cid_carto = carto.id
    now = dt.datetime.utcnow()
    def risque(ref, titre, cat='Opérationnel'):
        r = M.Risque(reference=ref, intitule=titre, categorie=cat, cartographie_id=cid_carto, client_id=cid, is_archived=False)
        db.session.add(r); db.session.flush(); return r
    r1 = risque('R-001', 'Fraude au paiement fournisseur', 'Fraude')
    r2 = risque('R-002', 'Panne du système central', 'SI')
    r3 = risque('R-003', '<script>alert(1)</script> Non-conformité', None)
    r4 = risque('R-004', 'Départ de personnes clés', 'RH')
    for r, niv, d in ((r1, 'Critique', now), (r2, 'Faible', now), (r4, 'Élevé', now - dt.timedelta(days=500))):
        db.session.add(M.EvaluationRisque(risque_id=r.id, client_id=cid, niveau_risque=niv, niveau_risque_net=niv,
                                          date_confirmation=d, statut_validation='valide'))
    db.session.add(M.DispositifMaitrise(risque_id=r2.id, client_id=cid, nom='Sauvegarde', reference='D-1', is_archived=False))
    db.session.add(M.PlanAction(risque_id=r4.id, client_id=cid, nom='Plan succession', reference='PA-1', statut='en_cours',
                                date_fin_prevue=(now - dt.timedelta(days=10)).date(), is_archived=False))
    db.session.add(M.Incident(risque_id=r2.id, client_id=cid, titre='Panne', reference='INC-1', date_occurrence=now - dt.timedelta(days=20),
                              is_archived=False))
    db.session.commit()
    ids_r = {'R-001': r1.id, 'R-002': r2.id}

c = socle.navigateur(A, ids['admin_a'])

# --- carto vide : score 0
r = c.get(f'/cartographie/{vide_id}/analyse-ia'); t = r.get_data(as_text=True)
verif('cartographie vide : page OK et score 0', r.status_code == 200 and '<strong>0</strong>' in t and 'Construire la cartographie' in t,
      f'{r.status_code} {socle.cause(A)}')

# --- sans clé : page complète, partie IA « non configurée »
IA.cle_api = lambda: None
r = c.get(f'/cartographie/{cid_carto}/analyse-ia'); t = r.get_data(as_text=True)
verif('sans clé : page OK', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')
verif('sans clé : message clair, recommandations présentes', "pas configurée" in t and 'sans dispositif de maîtrise' in t)
verif('intitulé piégé échappé', '<script>alert(1)</script>' not in t)
with A.app.app_context():
    l = IA.collecter(db.session.get(M.Cartographie, cid_carto)); s1 = IA.score(l); s2 = IA.score(IA.collecter(db.session.get(M.Cartographie, cid_carto)))
    codes = {x['code'] for x in IA.recommandations(cid_carto, l)}
verif('score reproductible', s1 == s2, str(s1['score']))
verif('score = somme des critères', s1['score'] == int(round(sum(c_['points'] for c_ in s1['criteres']))))
verif('score cohérent (3 évalués sur 4, 1 couvert)', 20 <= s1['score'] <= 60, str(s1['score']))
for code in ('hauts_sans_dispositif', 'hauts_sans_plan', 'incidents_sous_cotes', 'plans_retard', 'non_evalues',
             'evaluations_anciennes', 'critiques_sans_kri', 'sans_categorie'):
    verif(f'recommandation calculée : {code}', code in codes)
verif('niveaux normalisés', IA.niveau_normalise('Très élevé') == 'critique' and IA.niveau_normalise('Elevé') == 'eleve'
      and IA.niveau_normalise('Modéré') == 'moyen' and IA.niveau_normalise('Faible') == 'faible')

# --- avec IA (simulée) : références inventées retirées, mémoire, recalcul si données changent, rafraîchir
appels = []
def faux_ia(envoi):
    appels.append(envoi)
    return {'synthese': 'Synthèse de test.', 'points_forts': ['Sauvegardes en place'],
            'priorites': [{'titre': 'Traiter la fraude', 'pourquoi': 'Critique sans contrôle', 'actions': ['Double validation'],
                           'references': ['R-001', 'R-999-INVENTE']}]}
IA.cle_api = lambda: 'sk-proj-' + 'x' * 40
IA.appeler_ia = faux_ia
r = c.get(f'/cartographie/{cid_carto}/analyse-ia'); t = r.get_data(as_text=True)
verif('avec IA : synthèse affichée et signalée', r.status_code == 200 and 'Synthèse de test.' in t and "Rédigé par l&#39;IA" in t or "Rédigé par l'IA" in t)
verif('référence vérifiée : R-001 en lien', f'/risque/{ids_r["R-001"]}' in t)
verif('référence inventée retirée', 'R-999-INVENTE' not in t)
verif('données envoyées : pas de description ni de nom de personne', all(set(x) <= {'reference', 'intitule', 'categorie', 'niveau', 'dispositifs',
      'plans_ouverts', 'plans_en_retard', 'incidents_12_mois', 'kri'} for x in appels[0]['risques_prioritaires']))
c.get(f'/cartographie/{cid_carto}/analyse-ia')
verif('2e ouverture : mémoire utilisée (pas de nouvel appel)', len(appels) == 1, str(len(appels)))
with A.app.app_context():
    db.session.add(M.DispositifMaitrise(risque_id=ids_r['R-001'], client_id=cid, nom='Double validation', reference='D-2', is_archived=False))
    db.session.commit()
c.get(f'/cartographie/{cid_carto}/analyse-ia')
verif('données modifiées : nouvelle analyse', len(appels) == 2, str(len(appels)))
r = c.post(f'/api/ia/analyse/{cid_carto}/rafraichir', json={})
verif('Rafraîchir relance vraiment', r.status_code == 200 and r.get_json()['success'] and len(appels) == 3, f'{r.status_code} {len(appels)}')

# --- panne de l'IA : la précédente analyse reste affichée ; sans précédente, page complète
def panne(envoi):
    raise TimeoutError('délai dépassé')
IA.appeler_ia = panne
r = c.post(f'/api/ia/analyse/{cid_carto}/rafraichir', json={})
t = c.get(f'/cartographie/{cid_carto}/analyse-ia').get_data(as_text=True)
verif('panne IA : analyse précédente conservée', 'Synthèse de test.' in t)
r = c.get(f'/cartographie/{vide_id}/analyse-ia'); verif('panne IA : page vide toujours OK', r.status_code == 200)

# --- ignorer / rétablir, enregistré pour toute l'organisation
rid = f'{cid_carto}-plans_retard'
r = c.post(f'/api/ia/suggestion/{rid}/ignorer', json={}); verif('ignorer : OK', r.status_code == 200 and r.get_json()['success'])
c2 = socle.navigateur(A, ids['admin_a'])
t = c2.get(f'/cartographie/{cid_carto}/analyse-ia').get_data(as_text=True)
verif('ignorée : masquée, même dans une nouvelle session', 'plan(s) d&#39;action en retard' not in t.split('masquée(s)')[0] and '1 recommandation(s) masquée(s)' in t)
r = c.post(f'/api/ia/suggestion/{rid}/retablir', json={}); t = c.get(f'/cartographie/{cid_carto}/analyse-ia').get_data(as_text=True)
verif('rétablir : de nouveau visible', r.status_code == 200 and 'masquée(s)' not in t)

# --- cloisonnement et droits
b = socle.navigateur(A, ids['admin_b'])
r = b.get(f'/cartographie/{cid_carto}/analyse-ia'); verif('autre organisation : refusé', r.status_code in (302, 403, 404), str(r.status_code))
r = b.post(f'/api/ia/suggestion/{rid}/ignorer', json={}); verif('autre organisation : ne peut pas masquer', r.status_code in (302, 403, 404), str(r.status_code))
r = b.post(f'/api/ia/analyse/{cid_carto}/rafraichir', json={}); verif('autre organisation : ne peut pas rafraîchir', r.status_code in (302, 403, 404), str(r.status_code))
lec = socle.navigateur(A, ids['lecteur'])
r = lec.get(f'/cartographie/{cid_carto}/analyse-ia'); verif('sans permission IA : bloqué', r.status_code in (302, 403), str(r.status_code))
r = c.get(f'/cartographie/{cid_carto}/analyse-ia?imprimer=1'); verif('version PDF : OK', r.status_code == 200 and 'window.print' in r.get_data(as_text=True))
r = c.get(f'/cartographie/{cid_carto}/analyse-ia/export'); verif('ancien lien export : redirige', r.status_code == 302)
print(f'\n{sum(res)}/{len(res)}')
