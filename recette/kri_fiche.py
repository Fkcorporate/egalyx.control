"""Recette : fiche KRI (nouvelle présentation) et nettoyage des sources en erreur."""
import datetime as dt
import os
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
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
with Muet():
    try: objets.peupler_objets(A, ids)
    except TypeError: objets.peupler_objets(A)
with A.app.app_context():
    cid = db.session.get(M.User, ids['admin_a']).client_id
    r = M.Risque.query.filter_by(client_id=cid).first()
    k = M.KRI(nom='Taux de rotation du personnel', client_id=cid, type_indicateur='kri', seuil_alerte=8, seuil_critique=12,
              sens_evaluation_seuil='superieur', unite_mesure='%', frequence_mesure='mensuel', risque_id=r.id if r else None,
              description='Départs / effectif moyen', responsable_mesure_id=ids['gestionnaire'])
    vide = M.KRI(nom='KRI sans mesure', client_id=cid, type_indicateur='kri', seuil_alerte=1, seuil_critique=2)
    db.session.add_all([k, vide]); db.session.commit(); kid, vid = k.id, vide.id
    base = dt.datetime.utcnow() - dt.timedelta(days=150)
    for i, v in enumerate((5, 6.5, 7, 9, 13)):
        db.session.add(M.MesureKRI(kri_id=kid, valeur=v, date_mesure=base + dt.timedelta(days=30 * i), client_id=cid,
                                   commentaire='Collecte auto: Google Sheets — x' if i == 4 else 'Saisie RH', created_by=ids['admin_a']))
    db.session.commit()
    m_id = M.MesureKRI.query.filter_by(kri_id=kid).order_by(M.MesureKRI.date_mesure).first().id

adm = socle.navigateur(A, ids['admin_a'])
r = adm.get(f'/kri/{kid}/detail'); t = r.get_data(as_text=True)
verif('fiche KRI : page OK', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')
verif('dernière valeur et état critique', '>13<small>%</small>' in t.replace(' ', '') or '13<small>' in t, '')
verif('pastille « Critique »', 'Critique' in t)
verif('tendance « Se dégrade » (+4)', 'Se dégrade' in t and '+4' in t)
verif('jauge des seuils', 'kf-curseur' in t and 'alerte 8 · critique 12' in t)
verif('graphique avec seuils', 'kf-graphique' in t and "Seuil critique" in t)
verif('historique : 5 lignes, mesure auto signalée', t.count('id="mesure-') == 5 and 'kf-auto' in t)
verif('risque lié et responsable affichés', ('Risque' in t) and 'gestionnaire' in t)
verif('carte « Connecter un outil » (admin)', 'Connecter un outil' in t)
r = adm.get(f'/kri/{vid}/detail'); t = r.get_data(as_text=True)
verif('KRI sans mesure : page OK', r.status_code == 200 and 'Aucune mesure' in t and 'Pas de mesure' in t, f'{r.status_code} {socle.cause(A)}')
g = socle.navigateur(A, ids['gestionnaire']); t = g.get(f'/kri/{kid}/detail').get_data(as_text=True)
verif('gestionnaire : fiche OK, pas de bouton connecter', 'Taux de rotation' in t and 'Connecter un outil' not in t)
# saisie, modification, suppression
r = adm.post(f'/kri/{kid}/ajouter-mesure-periodique', data={'valeur': '10', 'date_mesure': dt.date.today().isoformat(), 'commentaire': 'ok'}, follow_redirects=True)
verif('saisie d\'une mesure', r.status_code == 200 and t.count('id="mesure-') <= r.get_data(as_text=True).count('id="mesure-'), socle.cause(A))
r = adm.post(f'/kri/mesure/{m_id}/modifier', data={'valeur': '4.5', 'date_mesure': (base).strftime('%Y-%m-%d'), 'commentaire': 'corrigé'})
with A.app.app_context():
    verif('modification d\'une mesure', db.session.get(M.MesureKRI, m_id).valeur == 4.5, f'{r.status_code}')
r = adm.post(f'/kri/mesure/{m_id}/supprimer')
with A.app.app_context():
    verif('suppression d\'une mesure', db.session.get(M.MesureKRI, m_id) is None, f'{r.status_code} {r.get_data(as_text=True)[:80]}')
verif('autre organisation : fiche refusée', socle.navigateur(A, ids['admin_b']).get(f'/kri/{kid}/detail').status_code in (302, 403, 404))
# sources en erreur : explication + suppression (super-admin)
with A.app.app_context():
    s = M.SourceDonnee(nom='API RH - Tableau de bord social', description='Source simulée', type_source='api', client_id=cid,
                       config_connexion={'url': 'http://api-rh.exemple.local/kpi'}, statut='erreur', frequence_rafraichissement=3600)
    db.session.add(s)
    from sqlalchemy.orm import Session
    try:
        db.session.commit(); sid = s.id
    except Exception:
        db.session.rollback()
        db.session.execute(db.text("INSERT INTO sources_donnees (nom, description, type_source, client_id, config_connexion, statut, frequence_rafraichissement) "
                                   "VALUES ('API RH - Tableau de bord social', 'Source simulée', 'api', :c, '{\"url\": \"http://api-rh.exemple.local/kpi\"}', 'erreur', 3600)"), {'c': cid})
        db.session.commit(); sid = db.session.execute(db.text('select max(id) from sources_donnees')).scalar()
    db.session.add(M.SourceKRILink(source_id=sid, kri_id=kid, chemin_donnee='$.x', est_actif=True)); db.session.commit()
sa = socle.navigateur(A, ids['superadmin'])
r = sa.get('/kri/sources'); t = r.get_data(as_text=True)
verif('sources : bandeau vers les connecteurs', r.status_code == 200 and 'Connecter un outil' in t, f'{r.status_code} {socle.cause(A)}')
verif('sources en erreur : raison en clair', 'source(s) en erreur' in t and 'https' in t and 'fictive' in t)
r = sa.get('/kri/sources/nouvelle'); verif('nouvelle source : bandeau', r.status_code == 200 and 'Connecter un outil' in r.get_data(as_text=True))
verif('admin client : ne peut pas supprimer une source', adm.post(f'/kri/sources/{sid}/supprimer').status_code == 403)
r = sa.post(f'/kri/sources/{sid}/supprimer', follow_redirects=True)
with A.app.app_context():
    verif('super-admin : source supprimée, mesures conservées', db.session.get(M.SourceDonnee, sid) is None
          and M.MesureKRI.query.filter_by(kri_id=kid).count() >= 4, socle.cause(A))
# ---- formulaires (création / modification) et PDF
r = adm.get('/kri/nouveau'); t = r.get_data(as_text=True)
verif('création : page OK, nouveau style', r.status_code == 200 and 'kx-form' in t and 'creer-depuis-liste' in t, f'{r.status_code} {socle.cause(A)}')
r = adm.get(f'/kri/{kid}/modifier'); t = r.get_data(as_text=True)
verif('modification : page OK, valeurs pré-remplies', r.status_code == 200 and 'value="Taux de rotation du personnel"' in t and 'value="12"' in t, f'{r.status_code} {socle.cause(A)}')
verif('modification : sans IA pas de faux exemples', "Taux d'incidents opérationnels" not in t)
r = adm.post('/kri/creer-depuis-liste', data={'type_indicateur': 'kpi', 'nom': 'Délai moyen de paiement', 'unite_mesure': 'jours',
     'frequence_mesure': 'mensuel', 'sens_evaluation_seuil': 'superieur', 'seuil_cible': '30', 'seuil_alerte': '45', 'seuil_critique': '60',
     'categorie': 'financier', 'risque_id': '', 'responsable_mesure_id': ''}, follow_redirects=True)
with A.app.app_context():
    nk = M.KRI.query.filter_by(nom='Délai moyen de paiement').first()
    verif('création : KPI enregistré avec ses champs', nk is not None and nk.type_indicateur == 'kpi' and nk.seuil_cible == 30 and nk.seuil_critique == 60, socle.cause(A))
r = adm.post(f'/kri/{kid}/modifier', data={'type_indicateur': 'kri', 'nom': 'Taux de rotation du personnel', 'unite_mesure': '%',
     'frequence_mesure': 'mensuel', 'sens_evaluation_seuil': 'superieur', 'seuil_alerte': '9', 'seuil_critique': '12',
     'risque_id': str(r.id) if False else '', 'description': 'Départs / effectif moyen', 'categorie': 'rh'}, follow_redirects=True)
with A.app.app_context():
    verif('modification : enregistrée', db.session.get(M.KRI, kid).seuil_alerte == 9, socle.cause(A))
LONG = 'Hausse due aux départs du service comptable. ' * 12 + 'FIN-DU-COMMENTAIRE'
with A.app.app_context():
    db.session.add(M.MesureKRI(kri_id=kid, valeur=11, date_mesure=dt.datetime.utcnow(), client_id=cid, commentaire=LONG)); db.session.commit()
r = adm.get(f'/kri/{kid}/rapport-pdf?html=1'); t = r.get_data(as_text=True)
verif('rapport : commentaire long en entier', r.status_code == 200 and 'FIN-DU-COMMENTAIRE' in t and '<svg' in t, f'{r.status_code} {socle.cause(A)}')
verif('rapport : autre organisation refusée', socle.navigateur(A, ids['admin_b']).get(f'/kri/{kid}/rapport-pdf').status_code == 404)
open('/tmp/kri_rapport.html', 'w').write(t)
ST = 'file:///home/claude/e2e/app/static/'
open('/tmp/kf_fiche.html', 'w').write(adm.get(f'/kri/{kid}/detail').get_data(as_text=True).replace('src="/static/', 'src="' + ST).replace('href="/static/', 'href="' + ST))
open('/tmp/kf_sources.html', 'w').write(sa.get('/kri/sources').get_data(as_text=True).replace('src="/static/', 'src="' + ST).replace('href="/static/', 'href="' + ST))
print(f'\n{sum(res)}/{len(res)}')
