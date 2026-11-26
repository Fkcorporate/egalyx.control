"""
egalyx/rapport_contenu.py — contenu des rapports choisi par chaque organisation (niveau 2 de la personnalisation).

Pour le rapport d'audit (PDF) et le rapport au comité d'audit, l'administrateur de l'organisation choisit :
  - le titre du document ;
  - les sections affichées (la numérotation et le sommaire suivent) ;
  - un texte d'introduction et un texte de conclusion types, avec des champs remplis automatiquement
    ({organisation}, {date}, et pour l'audit {reference}, {mission}) ;
  - les signataires en fin de rapport (fonction et, si on veut, nom).
La présentation (couleur, logo, mention, pied de page) reste dans egalyx/identite.py.

Stockage : ClientConfiguration.preferences['identite']['contenu'][<rapport>] — aucune nouvelle table.
Sans réglage, chaque rapport reste exactement comme avant (contenu_rapport() rend les valeurs d'origine).
Lecture dans un gabarit : {% set ct = contenu_rapport('audit', valeurs={...}) %} puis ct.montre('tests'),
ct.numero('tests'), ct.titre, ct.introduction, ct.conclusion, ct.signataires.
"""
import re

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from egalyx.commun import client_id_courant, client_requis, est_super_admin, journaliser

bp = Blueprint('rapport_contenu', __name__, url_prefix='/organisation/rapports')

TITRE_MAX = 80
TEXTE_MAX = 1500
SIGNATAIRES_MAX = 4
CHAMP_MAX = 80

# Sections de chaque rapport, dans l'ordre. numerotee=False : pas de numéro (sommaire, encadré…).
RAPPORTS = {
    'audit': {
        'libelle': 'Rapport d’audit (PDF et Word)',
        'titre': "Rapport d'Audit",
        'champs': ('organisation', 'date', 'reference', 'mission'),
        'sections': [
            ('sommaire', 'Sommaire', False),
            ('resume', 'Résumé exécutif', True),
            ('tests', 'Tests de contrôle', True),
            ('constatations', 'Constatations', True),
            ('recommandations', 'Recommandations', True),
            ('plans', "Plans d'action", True),
            ('validation', 'Validation et signatures', True),
        ],
        'signataires': [('Auditeur principal', ''), ('Responsable Qualité', '')],
    },
    'comite': {
        'libelle': 'Rapport au comité d’audit',
        'titre': 'Rapport au comité d’audit',
        'champs': ('organisation', 'date'),
        'sections': [
            ('synthese', 'Synthèse', True),
            ('decisions', 'Décisions attendues du comité', False),
            ('chiffres', 'Chiffres clés', True),
            ('profil', 'Profil de risque', True),
            ('top_risques', 'Risques les plus élevés', False),
            ('appetence', 'Risques au-delà de l’appétence', True),
            ('plans', 'Plans d’action en retard', True),
            ('incidents', 'Incidents graves', True),
            ('kri', 'Indicateurs en alerte', True),
            ('audit', 'Audit interne (12 mois)', True),
            ('conformite', 'Conformité', True),
            ('methode', 'Méthode', True),
        ],
        'signataires': [],
    },
}
SOMMAIRE = {'audit': {'validation': 'Validation'}}   # libellé du sommaire quand il diffère de celui du réglage
OBLIGATOIRES = {'audit': {'resume'}, 'comite': {'synthese'}}
INTRO_LIBELLE = {'audit': 'Introduction', 'comite': 'Introduction'}
CHAMPS_LIBELLES = {'organisation': 'nom de l’organisation', 'date': 'date du rapport',
                   'reference': 'référence de la mission', 'mission': 'titre de la mission'}


def _identite():
    from egalyx import identite
    return identite


def _brut(cid, rapport):
    prefs = _identite()._preferences(cid) if cid else {}
    return dict(((prefs.get('contenu') or {}).get(rapport) or {}))


def reglages(cid, rapport):
    """Réglages enregistrés, nettoyés ; valeurs d'origine si rien n'est réglé."""
    d = RAPPORTS[rapport]
    r = _brut(cid, rapport)
    connues = {k for k, _, _ in d['sections']}
    masquees = [k for k in (r.get('masquees') or []) if k in connues and k not in OBLIGATOIRES[rapport]]
    sig = r.get('signataires')
    if isinstance(sig, list):
        signataires = [{'fonction': str(s.get('fonction') or '')[:CHAMP_MAX], 'nom': str(s.get('nom') or '')[:CHAMP_MAX]}
                       for s in sig if isinstance(s, dict) and (s.get('fonction') or '').strip()][:SIGNATAIRES_MAX]
        signataires_regles = True
    else:
        signataires = [{'fonction': f, 'nom': n} for f, n in d['signataires']]
        signataires_regles = False
    return {'titre': (r.get('titre') or '')[:TITRE_MAX], 'masquees': masquees,
            'introduction': (r.get('introduction') or '')[:TEXTE_MAX], 'conclusion': (r.get('conclusion') or '')[:TEXTE_MAX],
            'signataires': signataires, 'signataires_regles': signataires_regles}


def remplir(texte, valeurs):
    """Remplace {champ} par sa valeur ; un champ inconnu reste tel quel (rien d'autre n'est interprété)."""
    return re.sub(r'\{([a-z_]+)\}', lambda m: str(valeurs[m.group(1)]) if m.group(1) in valeurs else m.group(0), texte or '')


def redaction_validee(audit):
    """Résumé exécutif et conclusion rédigés pour cette mission et validés par l'auditeur (egalyx/ia_audit.py)."""
    r = getattr(audit, 'redaction_rapport', None) if audit is not None else None
    if not isinstance(r, dict) or r.get('etat') != 'valide':
        return None
    return {'resume': (r.get('resume') or '').strip(), 'conclusion': (r.get('conclusion') or '').strip()}


class Contenu:
    def __init__(self, rapport, r, valeurs, mission=None):
        d = RAPPORTS[rapport]
        self.rapport = rapport
        self.titre = r['titre'] or d['titre']
        self.titre_regle = bool(r['titre'])
        self.introduction = remplir(r['introduction'], valeurs).strip()
        self.conclusion = remplir(r['conclusion'], valeurs).strip()
        # texte propre à la mission (validé par l'auditeur) : en tête du résumé, et conclusion avant le texte type
        self.resume_mission = (mission or {}).get('resume', '')
        self.conclusion_mission = (mission or {}).get('conclusion', '')
        if self.conclusion_mission:
            self.conclusion = (self.conclusion_mission + ('\n\n' + self.conclusion if self.conclusion else '')).strip()
        self.signataires = r['signataires']
        self.signataires_regles = r['signataires_regles']
        self._masquees = set(r['masquees'])
        self._numeros, n = {}, 0
        if self.introduction:
            n += 1
            self._numeros['introduction'] = n
        for k, _, num in d['sections']:
            if num and k not in self._masquees:
                if k == 'validation' and self.conclusion:
                    n += 1
                    self._numeros['conclusion'] = n
                n += 1
                self._numeros[k] = n
        if self.conclusion and 'conclusion' not in self._numeros:
            n += 1
            self._numeros['conclusion'] = n

    def montre(self, cle):
        return cle not in self._masquees

    def numero(self, cle):
        return self._numeros.get(cle, '')

    def sommaire(self):
        """[(ancre, libellé numéroté)] dans l'ordre du rapport."""
        d = dict((k, lib) for k, lib, _ in RAPPORTS[self.rapport]['sections'])
        d['introduction'], d['conclusion'] = 'Introduction', 'Conclusion'
        d.update(SOMMAIRE.get(self.rapport, {}))
        return [(k, f'{n}. {d[k]}') for k, n in sorted(self._numeros.items(), key=lambda x: x[1])]


def contenu_rapport(rapport, cid=None, valeurs=None, audit=None):
    cid = cid if cid is not None else client_id_courant()
    v = {'organisation': '', 'date': ''}
    if cid:
        try:
            v['organisation'] = _identite().nom_affiche(cid) or ''
            m = _identite()._m()
            cl = m.db.session.get(m.Client, cid)
            v['organisation'] = cl.nom if cl else v['organisation']
        except Exception:
            pass
    try:
        from egalyx.localisation import aujourdhui
        v['date'] = aujourdhui().strftime('%d/%m/%Y')
    except Exception:
        from datetime import date
        v['date'] = date.today().strftime('%d/%m/%Y')
    v.update({k: ('' if x is None else x) for k, x in (valeurs or {}).items()})
    return Contenu(rapport, reglages(cid, rapport) if cid else reglages(None, rapport), v,
                   mission=redaction_validee(audit) if rapport == 'audit' else None)


def appliquer(cid, rapport, form):
    """Enregistre les réglages d'un rapport depuis un formulaire (sans commit). Lève ValueError."""
    if rapport not in RAPPORTS:
        raise ValueError('Rapport inconnu.')
    d = RAPPORTS[rapport]
    affichees = set(form.getlist('sections'))
    masquees = [k for k, _, _ in d['sections'] if k not in affichees and k not in OBLIGATOIRES[rapport]]
    signataires = []
    for f, n in zip(form.getlist('sig_fonction'), form.getlist('sig_nom')):
        f, n = ' '.join(f.split())[:CHAMP_MAX], ' '.join(n.split())[:CHAMP_MAX]
        if f:
            signataires.append({'fonction': f, 'nom': n})
        elif n:
            raise ValueError('Chaque signataire doit avoir une fonction (ex. « Directeur de l’audit interne »).')
    if len(signataires) > SIGNATAIRES_MAX:
        raise ValueError(f'{SIGNATAIRES_MAX} signataires au maximum.')

    def texte(nom):
        t = '\n'.join(l.rstrip() for l in (form.get(nom) or '').replace('\r', '').split('\n')).strip()
        if len(t) > TEXTE_MAX:
            raise ValueError(f'Texte trop long : {TEXTE_MAX} caractères au maximum.')
        return t
    i = _identite()
    m = i._m()
    conf = m.ClientConfiguration.query.filter_by(client_id=cid).first()
    if conf is None:
        conf = m.ClientConfiguration(client_id=cid, couleurs={}, preferences={})
        m.db.session.add(conf)
    prefs = dict(conf.preferences or {})
    ident = dict(prefs.get(i.CLE) or {})
    contenu = dict(ident.get('contenu') or {})
    contenu[rapport] = {'titre': ' '.join((form.get('titre') or '').split())[:TITRE_MAX], 'masquees': masquees,
                        'introduction': texte('introduction'), 'conclusion': texte('conclusion'),
                        'signataires': signataires if form.get('sig_regles') == '1' else None}
    ident['contenu'] = contenu
    prefs[i.CLE] = ident
    conf.preferences = prefs
    g.pop('_egalyx_rapport', None)
    return contenu[rapport]


def reinitialiser(cid, rapport):
    i = _identite()
    m = i._m()
    conf = m.ClientConfiguration.query.filter_by(client_id=cid).first()
    if conf is None:
        return
    prefs = dict(conf.preferences or {})
    ident = dict(prefs.get(i.CLE) or {})
    contenu = dict(ident.get('contenu') or {})
    contenu.pop(rapport, None)
    ident['contenu'] = contenu
    prefs[i.CLE] = ident
    conf.preferences = prefs


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/<rapport>', methods=['GET', 'POST'])
@client_requis
def page(rapport='audit'):
    if not _identite().peut_regler():
        abort(403)
    if rapport not in RAPPORTS:
        abort(404)
    cid = client_id_courant()
    cible = {'client_id': cid} if est_super_admin() else {}
    if request.method == 'POST':
        m = _identite()._m()
        try:
            if request.form.get('action') == 'reinitialiser':
                reinitialiser(cid, rapport)
                message = 'Contenu d’origine rétabli.'
                details = {'rapport': rapport, 'reinitialise': True}
            else:
                details = {'rapport': rapport, **appliquer(cid, rapport, request.form)}
                message = 'Contenu du rapport enregistré.'
        except ValueError as e:
            m.db.session.rollback()
            flash(str(e), 'warning')
            return redirect(url_for('.page', rapport=rapport, **cible))
        journaliser('contenu_rapport', details, client_id=cid)
        m.db.session.commit()
        flash(message, 'success')
        return redirect(url_for('.page', rapport=rapport, **cible))
    r = reglages(cid, rapport)
    d = RAPPORTS[rapport]
    return render_template('egalyx/rapport_contenu.html', rapport=rapport, rapports=RAPPORTS, d=d, r=r,
                           obligatoires=OBLIGATOIRES[rapport], champs=[(c, CHAMPS_LIBELLES[c]) for c in d['champs']],
                           titre_max=TITRE_MAX, texte_max=TEXTE_MAX, sig_max=SIGNATAIRES_MAX, cible=cible)


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    app.register_blueprint(bp)
    exempter_controle_ancien(app, {'rapport_contenu.page'})
    app.jinja_env.globals['contenu_rapport'] = contenu_rapport
