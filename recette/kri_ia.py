"""Recette : projection calculée et « Analyser avec l'IA » sur la fiche KRI, soumis à l'interrupteur IA du super-admin."""
import datetime as dt
import os
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
os.environ['OPENAI_API_KEY'] = 'sk-proj-' + 'x' * 40
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
from egalyx import kri_ia, kri_fiche, ia as interrupteur
with Muet():
    try: objets.peupler_objets(A, ids)
    except TypeError: objets.peupler_objets(A)
interrupteur.ecrire_reglage('ia_active', True)
os.environ['OPENAI_API_KEY'] = 'sk-proj-' + 'x' * 40   # après le chargement de l'application (qui lit son .env)
now = dt.datetime.utcnow()
with A.app.app_context():
    cid = db.session.get(M.User, ids['admin_a']).client_id
    r = M.Risque.query.filter_by(client_id=cid).first()
    def kri(nom, valeurs, a=8, c=12, sens='superieur'):
        k = M.KRI(nom=nom, client_id=cid, type_indicateur='kri', seuil_alerte=a, seuil_critique=c, sens_evaluation_seuil=sens,
                  unite_mesure='%', risque_id=r.id if r else None)
        db.session.add(k); db.session.flush()
        for i, v in enumerate(valeurs):
            db.session.add(M.MesureKRI(kri_id=k.id, valeur=v, date_mesure=now - dt.timedelta(days=30 * (len(valeurs) - 1 - i)),
                                       client_id=cid, commentaire='Départs au service comptable' if i == len(valeurs) - 1 else ''))
        db.session.commit(); return k.id
    k_hausse = kri('Rotation du personnel', [4, 5, 6, 7])
    k_stable = kri('Écarts de caisse', [3, 3, 3.01, 3])
    k_crit = kri('Incidents SI', [9, 11, 13])
    k_bas = kri('Taux de sauvegardes réussies', [99, 97, 95, 93], a=90, c=85, sens='inferieur')
    proj = lambda kid: kri_fiche.projection(db.session.get(M.KRI, kid), sorted(M.MesureKRI.query.filter_by(kri_id=kid), key=lambda m: m.date_mesure))
    p1, p2, p3, p4 = proj(k_hausse), proj(k_stable), proj(k_crit), proj(k_bas)
verif('projection hausse : alerte puis critique', p1 and "seuil d'alerte" in p1['texte'] and 'seuil critique' in p1['texte'], p1 and p1['texte'])
verif('projection : environ 30 j avant l\'alerte (+1/mois, 7 → 8)', p1 and 25 <= p1['jours_alerte'] <= 35, p1 and str(p1['jours_alerte']))
verif('projection stable : pas de dépassement', p2 and 'aucun dépassement' in p2['texte'], p2 and p2['texte'])
verif('projection déjà critique', p3 and 'Déjà au-delà' in p3['texte'])
verif('projection sens « inférieur » (baisse = risque)', p4 and 'seuil' in p4['texte'] and p4['jours_alerte'] and p4['jours_alerte'] > 0, p4 and p4['texte'])

adm = socle.navigateur(A, ids['admin_a'])
t = adm.get(f'/kri/{k_hausse}/detail').get_data(as_text=True)
verif('fiche : projection affichée', 'Au rythme actuel' in t, socle.cause(A))
verif('fiche : carte « Analyse IA » (IA active)', 'id="kf-ia-lancer"' in t)
t = adm.get(f'/kri/{k_crit}/detail').get_data(as_text=True)
verif('KRI critique : bouton mis en avant', 'kf-ia kf-ia-urgent' in t)

appels = []
def faux(envoi):
    appels.append(envoi)
    return {'lecture': 'La rotation progresse de 1 point par mois.', 'causes_possibles': ['Départs au service comptable'],
            'actions': [{'titre': 'Entretiens de départ', 'detail': 'Identifier les motifs.'}], 'qualite_indicateur': [],
            'chiffre_invente': 999}
kri_ia.appeler_ia = faux
r = adm.post(f'/kri/{k_hausse}/analyse-ia', json={}); d = r.get_json()
verif('analyse IA : réponse', r.status_code == 200 and d['success'] and d['analyse']['lecture'].startswith('La rotation'), str(r.status_code))
verif('analyse IA : champs inattendus retirés', 'chiffre_invente' not in d['analyse'])
verif('données envoyées : mesures, seuils, projection, risque', appels and appels[0]['projection_calculee'] and appels[0]['indicateur']['seuil_critique'] == 12
      and len(appels[0]['mesures_recentes']) == 4)
adm.post(f'/kri/{k_hausse}/analyse-ia', json={})
verif('2e demande : mémoire (pas de nouvel appel)', len(appels) == 1, str(len(appels)))
adm.post(f'/kri/{k_hausse}/analyse-ia', json={'forcer': True})
verif('« Relancer » : nouvel appel', len(appels) == 2)
r = adm.post(f'/kri/{k_hausse}/analyse-ia/commentaire', json={'texte': 'La rotation progresse.\n• Entretiens de départ'})
with A.app.app_context():
    m = M.MesureKRI.query.filter_by(kri_id=k_hausse).order_by(M.MesureKRI.date_mesure.desc()).first()
    verif('ajout au commentaire de la dernière mesure', r.get_json()['success'] and 'Analyse (IA, relue par admin_a' in m.commentaire
          and m.commentaire.startswith('Départs'))
b = socle.navigateur(A, ids['admin_b'])
verif('autre organisation : refusé', b.post(f'/kri/{k_hausse}/analyse-ia', json={}).status_code in (403, 404))
os.environ['OPENAI_API_KEY'] = ''
r = adm.post(f'/kri/{k_stable}/analyse-ia', json={})
verif('sans clé : message clair', r.status_code == 503 and 'pas configurée' in r.get_json()['error'])
os.environ['OPENAI_API_KEY'] = 'sk-proj-' + 'x' * 40

# ---- interrupteur du super-admin
sa = socle.navigateur(A, ids['superadmin'])
r = sa.post('/super-admin/ia/', data={'ia_active': '0'})
verif('super-admin coupe l\'IA', r.status_code in (200, 302) and not interrupteur.ia_plateforme_active(), str(r.status_code))
t = adm.get(f'/kri/{k_hausse}/detail').get_data(as_text=True)
verif('IA coupée : carte « Analyse IA » disparue', 'id="kf-ia-lancer"' not in t and 'Au rythme actuel' in t, socle.cause(A))
n = len(appels)
r = adm.post(f'/kri/{k_hausse}/analyse-ia', json={'forcer': True})
verif('IA coupée : adresse bloquée (403), aucun appel', r.status_code == 403 and len(appels) == n, str(r.status_code))
verif('IA coupée : ajout de commentaire IA bloqué', adm.post(f'/kri/{k_hausse}/analyse-ia/commentaire', json={'texte': 'x'}).status_code == 403)
with A.app.app_context():
    carto = M.Cartographie.query.filter_by(client_id=cid).first()
if carto:
    r = adm.get(f'/cartographie/{carto.id}/analyse-ia')
    verif('IA coupée : analyse de cartographie bloquée aussi', r.status_code in (302, 403), str(r.status_code))
r = sa.post('/super-admin/ia/', data={'ia_active': '1'})
t = adm.get(f'/kri/{k_hausse}/detail').get_data(as_text=True)
verif('super-admin réactive l\'IA : carte de retour', interrupteur.ia_plateforme_active() and 'id="kf-ia-lancer"' in t)
g = socle.navigateur(A, ids['gestionnaire'])   # pas la permission « Utiliser l'analyse IA » dans les données de recette
t = g.get(f'/kri/{k_hausse}/detail').get_data(as_text=True)
verif('sans la permission IA : pas de carte, adresse refusée', 'id="kf-ia-lancer"' not in t and g.post(f'/kri/{k_hausse}/analyse-ia', json={}).status_code == 403)
ST = 'file:///home/claude/e2e/app/static/'
open('/tmp/kf_ia.html', 'w').write(adm.get(f'/kri/{k_hausse}/detail').get_data(as_text=True).replace('src="/static/', 'src="' + ST).replace('href="/static/', 'href="' + ST))
print(f'\n{sum(res)}/{len(res)}')
