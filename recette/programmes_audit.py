"""Recette : programmes d'audit (liste, fiche, chronogramme) et fiche d'audit — nouvelle présentation."""
import datetime as dt, random
import socle
from socle import Muet
with Muet():
    A, ids = socle.preparer()
import objets, models as M
from models import db
with Muet():
    try: objets.peupler_objets(A, ids)
    except TypeError: objets.peupler_objets(A)
random.seed(4)
with A.app.app_context():
    uid = ids['admin_a']; cid = db.session.get(M.User, uid).client_id
    risques = M.Risque.query.filter_by(client_id=cid).all()
    p = M.ProgrammeAudit(reference='PA-2026-2028', nom="Programme pluriannuel d'audit 2026-2028", periode='triennal', annee_debut=2026, annee_fin=2028,
                         methode_generation='risques', statut='approuve', client_id=cid, created_by=uid, is_archived=False,
                         description="Programme fondé sur la cartographie des risques : priorité aux risques nets élevés et critiques.",
                         ressources_disponibles=4, capacite_max_trimestre=3, duree_moyenne_mission=20)
    p2 = M.ProgrammeAudit(reference='PA-2025', nom="Programme d'audit 2025", periode='annuel', annee_debut=2025, annee_fin=2025,
                          methode_generation='manuel', statut='cloture', client_id=cid, created_by=uid, is_archived=False)
    db.session.add_all([p, p2]); db.session.flush()
    titres = ['Achats et paiements fournisseurs', 'Trésorerie et rapprochements bancaires', 'Paie et gestion RH', 'Sécurité des systèmes d\'information',
              'Conformité LCB-FT', 'Gestion des stocks', 'Crédit et recouvrement', 'Continuité d\'activité', 'Protection des données (RGPD)', 'Contrôle de gestion']
    stats = ['termine', 'termine', 'en_cours', 'en_cours', 'planifie', 'planifie', 'planifie', 'planifie', 'reporte', 'planifie']
    for i, t in enumerate(titres):
        an = 2026 + i // 4; tr = i % 4 + 1
        deb = dt.date(an, (tr - 1) * 3 + 1, 10)
        db.session.add(M.MissionAudit(reference=f'MIS-{i + 1:02d}', titre=t, programme_id=p.id, client_id=cid, annee_prevue=an, trimestre_prevue=tr,
                                      date_debut_prevue=deb, date_fin_prevue=deb + dt.timedelta(days=25), duree_estimee=20, statut=stats[i],
                                      priorite=['critique', 'elevee', 'moyenne', 'elevee', 'critique', 'moyenne', 'elevee', 'moyenne', 'faible', 'faible'][i],
                                      progression=[100, 100, 60, 30, 0, 0, 0, 0, 0, 0][i], responsable_id=uid, is_archived=False, created_by=uid,
                                      risque_id=risques[i % len(risques)].id if risques else None))
    au = M.Audit(reference='AUD-2026-014', titre='Audit du processus achats et paiement fournisseurs', type_audit='interne', client_id=cid,
                 statut='en_cours', created_by=uid, responsable_id=uid, date_debut_prevue=dt.date(2026, 10, 5), date_fin_prevue=dt.date(2026, 11, 28),
                 description="Revue du cycle achats.", objectifs="Vérifier la séparation des tâches.", portee="Siège.", equipe_audit_ids=str(uid))
    db.session.add(au); db.session.commit()
    pid, aid = p.id, au.id
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


c = socle.navigateur(A, ids['admin_a'])
r = c.get('/programme-audit'); t = r.get_data(as_text=True)
verif('liste des programmes : OK', r.status_code == 200 and 'PA-2026-2028' in t and 'pl-table' in t, f'{r.status_code} {socle.cause(A)}')
verif('liste : actions conservées', all(x in t for x in ('openApproveModal', 'openArchiveModal', f'/programme-audit/{pid}/chronogramme', 'exporter')))
r = c.get(f'/programme-audit/{pid}'); t = r.get_data(as_text=True)
verif('fiche programme : OK (plantait dès qu\'une mission avait des dates)', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')
verif('fiche : 10 missions listées', t.count('class="form-check-input mission-checkbox"') == 10)
verif('fiche : modals des missions présents', f'editMissionModal' in t and 'reprogrammerMissionModal' in t and 'addMissionModal' in t)
verif('fiche : dates des missions dans les formulaires', 'name="nouvelle_date_debut" value="2026-' in t)
verif('fiche : mission terminée jamais « en retard »', 'MIS-01' in t and t.split('MIS-01')[1][:2500].count('En retard') == 0)
r = c.get(f'/programme-audit/{pid}/chronogramme'); t = r.get_data(as_text=True)
verif('chronogramme : OK', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')
verif('chronogramme : frise avec 10 barres', t.count('class="gt-barre"') == 10)
verif('chronogramme : glisser-déposer conservé', 'ondrop="drop(event)"' in t and 'draggable="true"' in t and 'function drop(e)' in t)
verif('chronogramme : capacité affichée', 'capacité 240 j' in t)
r = c.get(f'/audit/{aid}'); t = r.get_data(as_text=True)
verif('fiche audit : OK', r.status_code == 200 and 'au-tete' in t and 'au-kpis' in t, f'{r.status_code} {socle.cause(A)}')
verif('fiche audit : onglets et rapport conservés', 'id="auditTabs"' in t and '#modalRapport' in t and 'rapport-complet' in t)
verif('fiche audit : statut lisible', '>En cours<' in t and 'EN_COURS' not in t)
print(f'\n{sum(res)}/{len(res)}')
