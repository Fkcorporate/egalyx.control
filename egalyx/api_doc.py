"""
egalyx/api_doc.py — documentation de l'API publique /api/v1.

  /api/v1/openapi.json   spécification OpenAPI 3.0 (décrit exactement les réponses du code)
  /api/v1/docs           même spécification (ancienne adresse conservée)
  /api/documentation     page lisible (connexion requise), avec exemples curl
"""
import os

from flask import Blueprint, jsonify, render_template, request

from egalyx.commun import permission_requise

bp = Blueprint('api_doc', __name__)


def _liste(schema_ref):
    return {'type': 'object', 'properties': {'success': {'type': 'boolean', 'example': True},
                                             'data': {'type': 'array', 'items': {'$ref': schema_ref}}}}


def _get(resume, permission, schema, parametres=None, description=None):
    op = {'summary': resume, 'description': (description or '') + f"\n\nPermission de la clé : `{permission}`.",
          'security': [{'cleApi': []}],
          'responses': {'200': {'description': 'Succès', 'content': {'application/json': {'schema': schema}}},
                        '401': {'$ref': '#/components/responses/NonAuthentifie'},
                        '403': {'$ref': '#/components/responses/PermissionManquante'}}}
    if parametres:
        op['parameters'] = parametres
    return op


AUDIT_ID = {'name': 'audit_id', 'in': 'query', 'required': False, 'schema': {'type': 'integer'},
            'description': "Limiter aux éléments d'un audit"}


def _s(**props):
    return {'type': 'object', 'properties': {k: ({'type': v} if isinstance(v, str) else v) for k, v in props.items()}}


D = {'type': 'string', 'format': 'date', 'nullable': True}
DT = {'type': 'string', 'format': 'date-time', 'nullable': True}
N = {'type': 'number', 'nullable': True}


def specification(serveur=None):
    serveur = serveur or ((os.environ.get('EGALYX_URL_PUBLIQUE') or request.host_url).rstrip('/') + '/api/v1')
    return {
        'openapi': '3.0.3',
        'info': {
            'title': 'API Egalyx Control', 'version': '1.0.0',
            'description': (
                "API REST de lecture (et de création d'audits) sur les données de **votre organisation**.\n\n"
                "Authentification : en-tête `X-API-Key` avec une clé créée dans Administration > Clés d'API. "
                "Chaque clé est rattachée à une organisation et porte des permissions (lecture / écriture par module). "
                "Toutes les réponses sont limitées à l'organisation de la clé. Chaque appel est journalisé.\n\n"
                "Dates : ISO 8601 (AAAA-MM-JJ). Encodage : UTF-8."),
        },
        'servers': [{'url': serveur}],
        'components': {
            'securitySchemes': {'cleApi': {'type': 'apiKey', 'in': 'header', 'name': 'X-API-Key'}},
            'responses': {
                'NonAuthentifie': {'description': 'Clé absente, invalide ou expirée',
                                   'content': {'application/json': {'schema': _s(error='string')}}},
                'PermissionManquante': {'description': 'La clé ne porte pas la permission requise',
                                        'content': {'application/json': {'schema': _s(error='string')}}},
            },
            'schemas': {
                'Audit': _s(id='integer', reference='string', titre='string', type_audit='string', statut='string',
                            date_debut_prevue=D, date_fin_prevue=D, score_global=N, progression=N, created_at=DT),
                'AuditDetail': _s(id='integer', reference='string', titre='string', description='string',
                                  type_audit='string', statut='string', sous_statut='string',
                                  date_debut_prevue=D, date_fin_prevue=D, date_debut_reelle=D, date_fin_reelle=D,
                                  portee='string', objectifs='string', criteres='string', score_global=N, progression=N,
                                  constatations={'type': 'array', 'items': _s(id='integer', reference='string',
                                                 description='string', type='string', gravite='string', statut='string')},
                                  recommandations={'type': 'array', 'items': _s(id='integer', reference='string',
                                                   description='string', type='string', statut='string', taux_avancement=N)}),
                'NouvelAudit': {'type': 'object', 'required': ['titre'], 'properties': {
                    'titre': {'type': 'string'}, 'description': {'type': 'string'},
                    'type_audit': {'type': 'string', 'default': 'interne'},
                    'statut': {'type': 'string', 'default': 'planifie'},
                    'date_debut_prevue': {'type': 'string', 'format': 'date'},
                    'date_fin_prevue': {'type': 'string', 'format': 'date'}}},
                'Constatation': _s(id='integer', reference='string', description='string', type='string',
                                   gravite='string', statut='string', audit_id='integer', created_at=DT),
                'Recommandation': _s(id='integer', reference='string', description='string', type='string',
                                     statut='string', taux_avancement=N, date_echeance=D, audit_id='integer'),
                'PlanAction': _s(id='integer', reference='string', nom='string', description='string', statut='string',
                                 pourcentage_realisation=N, date_debut=D, date_fin_prevue=D, audit_id='integer'),
                'Risque': _s(id='integer', reference='string', intitule='string', description='string',
                             categorie='string', type_risque='string'),
                'KRI': _s(id='integer', nom='string', description='string', type_indicateur='string',
                          unite_mesure='string', seuil_alerte=N, seuil_critique=N, derniere_valeur=N,
                          statut_alerte='string'),
                'Veille': _s(id='integer', titre='string', reference='string', type_reglementation='string',
                             organisme_emetteur='string', date_publication=D, date_application=D,
                             impact_estime='string', statut='string'),
            },
        },
        'paths': {
            '/health': {'get': {'summary': "État du service (sans authentification)", 'security': [],
                                'responses': {'200': {'description': 'Service disponible', 'content': {'application/json': {
                                    'schema': _s(status='string', version='string', timestamp='string')}}}}}},
            '/audits': {
                'get': _get('Liste des audits (non archivés)', 'read_audits', _liste('#/components/schemas/Audit')),
                'post': {'summary': 'Créer un audit', 'security': [{'cleApi': []}],
                         'description': "Permission de la clé : `write_audits`. La référence est générée (AUD-AAAA-NNNN).",
                         'requestBody': {'required': True, 'content': {'application/json': {
                             'schema': {'$ref': '#/components/schemas/NouvelAudit'}}}},
                         'responses': {'201': {'description': 'Audit créé', 'content': {'application/json': {
                             'schema': _s(success='boolean', data=_s(id='integer', reference='string', titre='string'))}}},
                             '400': {'description': 'Données manquantes ou invalides'},
                             '401': {'$ref': '#/components/responses/NonAuthentifie'},
                             '403': {'$ref': '#/components/responses/PermissionManquante'}}},
            },
            '/audits/{audit_id}': {'get': dict(_get("Détail d'un audit, avec constatations et recommandations",
                                                    'read_audits', _s(success='boolean',
                                                                      data={'$ref': '#/components/schemas/AuditDetail'})),
                                               parameters=[{'name': 'audit_id', 'in': 'path', 'required': True,
                                                            'schema': {'type': 'integer'}}])},
            '/constatations': {'get': _get('Constatations (plus récentes en premier)', 'read_constatations',
                                           _liste('#/components/schemas/Constatation'), [AUDIT_ID])},
            '/recommandations': {'get': _get('Recommandations', 'read_recommandations',
                                             _liste('#/components/schemas/Recommandation'), [AUDIT_ID])},
            '/plans-action': {'get': _get("Plans d'action (non archivés)", 'read_plans_action',
                                          _liste('#/components/schemas/PlanAction'), [AUDIT_ID])},
            '/risques': {'get': _get('Risques (non archivés)', 'read_risques', _liste('#/components/schemas/Risque'))},
            '/kri': {'get': _get('Indicateurs de risque actifs, avec dernière mesure et état', 'read_kri',
                                 _liste('#/components/schemas/KRI'))},
            '/veille': {'get': _get('Veille réglementaire active', 'read_veille', _liste('#/components/schemas/Veille'))},
        },
    }


@bp.route('/api/v1/openapi.json')
def openapi():
    return jsonify(specification())


@bp.route('/api/documentation')
@permission_requise('can_manage_api')
def page():
    spec = specification()
    return render_template('egalyx/api_documentation.html', spec=spec, serveur=spec['servers'][0]['url'])


def enregistrer(app, csrf=None):
    app.register_blueprint(bp)
    # Ancienne adresse /api/v1/docs : même spécification, à jour
    if 'api_docs' in app.view_functions:
        app.view_functions['api_docs'] = lambda: jsonify(specification())
    # L'API publique s'authentifie par clé (en-tête), pas par cookie : la protection CSRF ne s'y applique pas.
    if csrf is not None:
        for regle in app.url_map.iter_rules():
            if regle.rule.startswith('/api/v1/') and regle.endpoint in app.view_functions:
                csrf.exempt(app.view_functions[regle.endpoint])
