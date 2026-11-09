"""Socle de la recette : démarre la vraie application sur une base SQLite de test vide,
crée deux organisations et un utilisateur par rôle, et donne un navigateur connecté par rôle."""
import os, sys, io, contextlib, logging
ICI = os.path.dirname(os.path.abspath(__file__))
APP = os.environ.get('EGALYX_APP', os.path.join(ICI, '..'))   # le dossier recette/ se place à la racine du projet
BASE = os.environ.get('EGALYX_BASE_TEST', os.path.join(ICI, 'recette.db'))
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.abspath(BASE)
os.environ.setdefault('SECRET_KEY', 'recette-' + 'x' * 40)
os.environ.pop('OPENAI_API_KEY', None)
os.environ['EGALYX_2FA_OBLIGATOIRE_ADMINS'] = '0'   # test seulement : la 2FA est testée à part
sys.path.insert(0, os.path.abspath(APP)); sys.path.insert(0, ICI)
os.chdir(os.path.abspath(APP))

import re
MDP = 'Recette-Egalyx-2026!'
DANGER = re.compile(r'logout|deconnex|supprim|delete|archiv|reset|clotur|activer|desactiv|purge|vider|reinit|bloquer|'
                    r'debloquer|restaur|langue|suspend|reactiv|fix|repair|migr|init|seed|demo|generer|import|sync|test|'
                    r'recalcul|nettoy|envoyer|relanc|cron|planifi|lancer|execut|demarr|convertir|dupliquer|copier|forcer|'
                    r'impersonat|se_connecter_en|switch|basculer|changer', re.I)

TOUT = None   # rempli au chargement

def charger(reinitialiser=True):
    if reinitialiser and os.path.exists(BASE):
        os.remove(BASE)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        import app as A
    logging.disable(logging.WARNING)
    A.app.config.update(TESTING=False, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=False,
                        SERVER_NAME=None, RATELIMIT_ENABLED=False)
    import traceback
    DERNIERE = A.app.config.setdefault('_RECETTE_EXC', [])
    orig_u, orig_e = A.app.handle_user_exception, A.app.handle_exception
    def capt_u(e):
        from werkzeug.exceptions import HTTPException
        if not isinstance(e, HTTPException):
            DERNIERE.append(traceback.format_exception(e))
        return orig_u(e)
    def capt_e(e):
        DERNIERE.append(traceback.format_exception(e)); return orig_e(e)
    A.app.handle_user_exception, A.app.handle_exception = capt_u, capt_e
    try:
        A.scheduler.shutdown(wait=False)
    except Exception:
        pass
    return A

def perms(*oui):
    from models import User
    base = dict(User.permissions.default.arg) if hasattr(User.permissions.default, 'arg') else {}
    base = {k: False for k in base if k.startswith('can_')} | {k: v for k, v in base.items() if k.startswith('module_')}
    for k in base:
        if k.startswith('module_'):
            base[k] = True
    base.update({'can_view_dashboard': True, 'can_view_reports': True})
    base.update({k: True for k in oui})
    return base

GESTION = ['can_manage_risks', 'can_manage_kri', 'can_manage_audit', 'can_manage_regulatory', 'can_manage_logigram',
           'can_export_data', 'can_archive_data', 'can_validate_risks', 'can_confirm_evaluations', 'can_manage_action_plans',
           'can_view_action_plans', 'can_view_controle_interne_n2', 'can_manage_controle_interne_n2', 'can_manage_quality',
           'can_manage_campaigns', 'can_view_campaigns', 'can_conduct_campaigns', 'can_manage_bcp', 'can_view_bcp',
           'can_manage_incidents', 'can_view_incidents', 'can_manage_audit_program', 'can_view_audit_program',
           'can_plan_audits', 'can_manage_questionnaires', 'can_create_questionnaires', 'can_view_responses',
           'can_view_departments', 'can_view_tableau_bord_strategique', 'can_view_recommandations', 'can_manage_recommandations']

def peupler(A):
    from models import db, User, Client
    with A.app.app_context():
        db.create_all()
        ca = Client(nom='Banque Recette', reference='REC-A', is_active=True)
        cb = Client(nom='Autre Organisation', reference='REC-B', is_active=True)
        db.session.add_all([ca, cb]); db.session.flush()
        def u(nom, role='utilisateur', client=ca, **kw):
            p = kw.pop('perms', None)
            x = User(username=nom, email=f'{nom}@recette.test', role=role, client_id=client.id if client else None,
                     is_active=True, **kw)
            x.password_hash = __import__('werkzeug.security', fromlist=['x']).generate_password_hash(MDP)
            x.permissions = p if p is not None else perms()
            db.session.add(x); return x
        u('superadmin', role='super_admin', client=None, perms={k: True for k in perms()})
        u('admin_a', role='admin', is_client_admin=True, can_manage_users=True,
          perms={k: True for k in perms()})
        u('gestionnaire', perms=perms(*GESTION))
        u('validateur', perms=perms('can_view_recommandations', 'can_manage_recommandations', 'can_manage_campaigns', 'can_view_campaigns', 'can_manage_controle_interne_n2',
                                    'can_view_controle_interne_n2', 'can_validate_risks', 'can_manage_action_plans',
                                    'can_view_action_plans', 'can_manage_audit_program', 'can_view_audit_program'))
        u('operateur', is_operateur=True, perms=perms())
        u('lecteur', perms=perms())
        u('admin_b', role='admin', client=cb, is_client_admin=True, can_manage_users=True,
          perms={k: True for k in perms()})
        db.session.commit()
        return {x.username: x.id for x in User.query.all()}

def navigateur(A, uid):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s['_user_id'] = str(uid); s['_fresh'] = True
    return c

def preparer():
    A = charger()
    ids = peupler(A)
    return A, ids

def silence():
    return contextlib.ExitStack()

class Muet:
    """Coupe les très nombreux print() de l'application pendant une requête."""
    def __enter__(self):
        self._o, self._e = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = io.StringIO(); return self
    def __exit__(self, *a):
        sys.stdout, sys.stderr = self._o, self._e

def cause(A):
    """Dernière exception levée par l'application (fichier:ligne + message)."""
    L = A.app.config.get('_RECETTE_EXC') or []
    if not L:
        return ''
    tb = L[-1]; L.clear()
    lieu = [x for x in tb if 'File "' in x and '/app/' in x and '/lib/' not in x]
    import re
    loc = re.findall(r'app/([^"]+)", line (\d+), in (\w+)', lieu[-1]) if lieu else []
    return (f"{loc[0][0]}:{loc[0][1]} ({loc[0][2]}) " if loc else '') + tb[-1].strip()[:200]

def appel(c, methode, url, **kw):
    with Muet():
        try:
            return getattr(c, methode.lower())(url, **kw)
        except Exception as e:      # exception non rattrapée = erreur 500 pour l'utilisateur
            class R: status_code = 599; headers = {}; data = repr(e).encode(); location = None
            return R()

_n = [0]
def creer(Modele, **kw):
    """Crée un objet en remplissant automatiquement les colonnes obligatoires non fournies."""
    import datetime as dt
    from models import db
    import sqlalchemy as sa
    _n[0] += 1
    for col in Modele.__table__.columns:
        if col.primary_key or col.name in kw or col.nullable or col.default is not None or col.server_default is not None:
            continue
        cle = [a for a in Modele.__mapper__.column_attrs if a.columns[0] is col]
        nom = cle[0].key if cle else col.name
        if nom in kw:
            continue
        t = col.type
        if col.foreign_keys:
            continue
        if isinstance(t, (sa.Integer,)): kw[nom] = 2026
        elif isinstance(t, (sa.Float, sa.Numeric)): kw[nom] = 1
        elif isinstance(t, sa.DateTime): kw[nom] = dt.datetime.utcnow()
        elif isinstance(t, sa.Date): kw[nom] = dt.date.today()
        elif isinstance(t, sa.Boolean): kw[nom] = False
        elif isinstance(t, sa.JSON): kw[nom] = {}
        else: kw[nom] = f'{Modele.__name__[:6].upper()}-{_n[0]}'
    o = Modele(**kw)
    db.session.add(o); db.session.flush()
    return o
