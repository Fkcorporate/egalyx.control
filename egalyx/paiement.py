"""
egalyx/paiement.py — paiement en ligne de l'abonnement.

Deux prestataires, chacun actif seulement si ses clés sont définies :
  CinetPay (Mobile Money Orange / MTN / Moov / Wave, cartes — Afrique de l'Ouest et centrale), en XOF :
      CINETPAY_APIKEY, CINETPAY_SITE_ID
  Stripe (cartes, Europe), en EUR :
      STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
  EGALYX_URL_PUBLIQUE : adresse publique de l'application (URL de retour et de notification).

Règle : un paiement n'est jamais considéré réussi sur la seule foi du navigateur ; le statut
est toujours revérifié auprès du prestataire (API de vérification CinetPay, session Stripe
ou webhook signé). La validation est idempotente.
"""
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from egalyx import calculs
from egalyx.commun import admin_client_requis, client_id_courant, journaliser

bp = Blueprint('paiement', __name__)

CINETPAY_INIT = 'https://api-checkout.cinetpay.com/v2/payment'
CINETPAY_VERIF = 'https://api-checkout.cinetpay.com/v2/payment/check'
STRIPE_API = 'https://api.stripe.com/v1'


def prestataires():
    p = []
    if os.environ.get('CINETPAY_APIKEY') and os.environ.get('CINETPAY_SITE_ID'):
        p.append({'code': 'cinetpay', 'nom': 'Mobile Money ou carte (CinetPay)', 'devise': 'XOF',
                  'detail': 'Orange Money, MTN, Moov, Wave, Visa/Mastercard — paiement en francs CFA'})
    if os.environ.get('STRIPE_SECRET_KEY'):
        p.append({'code': 'stripe', 'nom': 'Carte bancaire (Stripe)', 'devise': 'EUR',
                  'detail': 'Visa, Mastercard, American Express — paiement en euros'})
    return p


def _url(endpoint, **k):
    base = (os.environ.get('EGALYX_URL_PUBLIQUE') or '').rstrip('/')
    return base + url_for(endpoint, **k) if base else url_for(endpoint, _external=True, **k)


def _http(url, donnees=None, json_corps=None, entetes=None, methode=None):
    entetes = dict(entetes or {})
    corps = None
    if json_corps is not None:
        corps = json.dumps(json_corps).encode()
        entetes['Content-Type'] = 'application/json'
    elif donnees is not None:
        corps = urllib.parse.urlencode(donnees).encode()
        entetes['Content-Type'] = 'application/x-www-form-urlencoded'
    req = urllib.request.Request(url, data=corps, headers=entetes, method=methode)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode() or '{}')
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode() or '{}')
        except ValueError:
            return {'erreur_http': e.code}


def montant_pour(formule, periode, devise):
    eur = float(formule.prix_annuel if periode == 'annuel' else formule.prix_mensuel or 0)
    return calculs.montant_xof(eur) if devise == 'XOF' else round(eur, 2)


# ------------------------------------------------------------------ validation
def valider(p, reponse=None, reference_prestataire=None):
    """Paiement confirmé par le prestataire : prolonge l'abonnement (une seule fois)."""
    from models import db, AbonnementClient, Client, marquer_json_modifie
    if p.statut == 'reussi':
        return False
    p.statut, p.paye_le = 'reussi', datetime.utcnow()
    if reference_prestataire:
        p.reference_prestataire = reference_prestataire
    if reponse is not None:
        p.reponse = reponse
        marquer_json_modifie(p, 'reponse')
    client = db.session.get(Client, p.client_id)
    aujourd_hui = date.today()
    echeance = client.date_expiration.date() if client.date_expiration else None
    # Abonnement en cours : la nouvelle période commence le lendemain de l'échéance ; sinon aujourd'hui.
    debut = echeance + timedelta(days=1) if echeance and echeance >= aujourd_hui else aujourd_hui
    fin = calculs.periode_abonnement(debut, p.periode)
    ab = AbonnementClient(client_id=p.client_id, formule_id=p.formule_id, date_debut=debut, date_fin=fin,
                          periode=p.periode, statut='actif', is_renouvellement_auto=False, montant=p.montant,
                          devise=p.devise, methode_paiement=p.prestataire, reference_paiement=p.reference,
                          date_prochain_paiement=fin)
    db.session.add(ab)
    db.session.flush()
    p.abonnement_id = ab.id
    client.formule_id = p.formule_id
    client.date_expiration = datetime.combine(fin, datetime.max.time().replace(microsecond=0))
    client.is_active = True
    if not client.date_activation:
        client.date_activation = datetime.utcnow()
    journaliser('abonnement_paye', {'paiement': p.reference, 'montant': p.montant, 'devise': p.devise,
                                    'fin': fin.isoformat()}, client_id=p.client_id)
    return True


def verifier_cinetpay(p):
    r = _http(CINETPAY_VERIF, json_corps={'apikey': os.environ.get('CINETPAY_APIKEY'),
                                          'site_id': os.environ.get('CINETPAY_SITE_ID'),
                                          'transaction_id': p.reference})
    data = r.get('data') or {}
    statut = data.get('status')
    if r.get('code') == '00' and statut == 'ACCEPTED':
        try:
            montant_ok = int(float(data.get('amount'))) >= int(p.montant) and (data.get('currency') or 'XOF') == p.devise
        except (TypeError, ValueError):
            montant_ok = False
        if montant_ok:
            return 'reussi', r, data.get('payment_method')
        return 'echoue', r, None
    if statut in ('REFUSED', 'CANCELED') or r.get('code') in ('600', '627'):
        return 'echoue', r, None
    return 'initie', r, None


def verifier_stripe(p):
    if not p.reference_prestataire:
        return 'initie', {}, None
    r = _http(f"{STRIPE_API}/checkout/sessions/{urllib.parse.quote(p.reference_prestataire)}",
              entetes={'Authorization': f"Bearer {os.environ.get('STRIPE_SECRET_KEY')}"})
    if r.get('payment_status') == 'paid' and r.get('client_reference_id') == p.reference \
            and r.get('amount_total') == calculs.montant_centimes(p.montant) and (r.get('currency') or '').upper() == p.devise:
        return 'reussi', {'id': r.get('id'), 'payment_intent': r.get('payment_intent')}, r.get('id')
    if r.get('status') == 'expired':
        return 'echoue', {'id': r.get('id'), 'status': 'expired'}, None
    return 'initie', {}, None


def actualiser(p):
    from models import db, marquer_json_modifie
    if p.statut != 'initie':
        return p.statut
    statut, reponse, ref = (verifier_cinetpay if p.prestataire == 'cinetpay' else verifier_stripe)(p)
    if statut == 'reussi':
        valider(p, reponse, ref if p.prestataire == 'stripe' else None)
    elif statut == 'echoue':
        p.statut, p.reponse = 'echoue', reponse
        marquer_json_modifie(p, 'reponse')
    db.session.commit()
    return p.statut


# ------------------------------------------------------------------ pages
@bp.route('/abonnement')
@admin_client_requis
def abonnement():
    from models import Client, FormuleAbonnement, PaiementEnLigne, AbonnementClient
    cid = client_id_courant()
    client = Client.query.get(cid)
    formules = [f for f in FormuleAbonnement.query.order_by(FormuleAbonnement.prix_mensuel).all()
                if getattr(f, 'is_active', True) is not False and (f.prix_mensuel or f.prix_annuel)]
    paiements = PaiementEnLigne.query.filter_by(client_id=cid).order_by(PaiementEnLigne.created_at.desc()).limit(30).all()
    abonnements = AbonnementClient.query.filter_by(client_id=cid).order_by(AbonnementClient.date_debut.desc()).limit(10).all()
    return render_template('egalyx/abonnement.html', client=client, formules=formules, paiements=paiements,
                           abonnements=abonnements, prestataires=prestataires(), xof=calculs.montant_xof,
                           aujourd_hui=date.today())


@bp.route('/abonnement/payer', methods=['POST'])
@admin_client_requis
def payer():
    from models import db, Client, FormuleAbonnement, PaiementEnLigne
    cid = client_id_courant()
    prest = request.form.get('prestataire')
    periode = 'annuel' if request.form.get('periode') == 'annuel' else 'mensuel'
    formule = db.session.get(FormuleAbonnement, request.form.get('formule_id', type=int) or 0)
    dispo = {p['code']: p for p in prestataires()}
    if prest not in dispo or not formule:
        flash('Choisissez une formule et un moyen de paiement disponible.', 'danger')
        return redirect(url_for('.abonnement'))
    devise = dispo[prest]['devise']
    montant = montant_pour(formule, periode, devise)
    if montant <= 0:
        flash("Cette formule n'a pas de prix défini : contactez-nous.", 'warning')
        return redirect(url_for('.abonnement'))
    client = db.session.get(Client, cid)
    p = PaiementEnLigne(client_id=cid, formule_id=formule.id, periode=periode, montant=montant, devise=devise,
                        prestataire=prest, reference='EGX' + datetime.utcnow().strftime('%y%m%d') + secrets.token_hex(5).upper(),
                        initie_par=current_user.id)
    db.session.add(p)
    db.session.commit()
    libelle = f"Egalyx Control — {formule.nom} ({'12 mois' if periode == 'annuel' else '1 mois'})"
    try:
        if prest == 'cinetpay':
            r = _http(CINETPAY_INIT, json_corps={
                'apikey': os.environ['CINETPAY_APIKEY'], 'site_id': os.environ['CINETPAY_SITE_ID'],
                'transaction_id': p.reference, 'amount': int(montant), 'currency': 'XOF',
                'description': libelle[:100].replace('—', '-'), 'channels': 'ALL', 'lang': 'fr',
                'notify_url': _url('paiement.notification_cinetpay'),
                'return_url': _url('paiement.retour', reference=p.reference),
                'customer_name': (client.contact_nom or client.nom or '')[:100],
                'customer_email': client.contact_email or current_user.email,
                'metadata': f'client:{cid}'})
            url = (r.get('data') or {}).get('payment_url')
            if r.get('code') != '201' or not url:
                raise RuntimeError(r.get('description') or r.get('message') or 'refus CinetPay')
            p.reference_prestataire = (r.get('data') or {}).get('payment_token')
        else:
            r = _http(f'{STRIPE_API}/checkout/sessions', donnees={
                'mode': 'payment', 'client_reference_id': p.reference, 'metadata[reference]': p.reference,
                'line_items[0][quantity]': 1, 'line_items[0][price_data][currency]': 'eur',
                'line_items[0][price_data][unit_amount]': calculs.montant_centimes(montant),
                'line_items[0][price_data][product_data][name]': libelle,
                'customer_email': client.contact_email or current_user.email, 'locale': 'fr',
                'success_url': _url('paiement.retour', reference=p.reference),
                'cancel_url': _url('paiement.retour', reference=p.reference, annule=1)},
                entetes={'Authorization': f"Bearer {os.environ['STRIPE_SECRET_KEY']}"})
            url = r.get('url')
            if not url:
                raise RuntimeError((r.get('error') or {}).get('message') or 'refus Stripe')
            p.reference_prestataire = r.get('id')
    except Exception as e:
        p.statut, p.reponse = 'echoue', {'erreur': str(e)[:500]}
        db.session.commit()
        current_app.logger.error("Paiement %s non initialisé : %s", p.reference, e)
        flash("Le paiement n'a pas pu être lancé. Réessayez ou choisissez un autre moyen.", 'danger')
        return redirect(url_for('.abonnement'))
    db.session.commit()
    return redirect(url)


@bp.route('/abonnement/retour/<reference>')
@admin_client_requis
def retour(reference):
    from models import db, PaiementEnLigne
    p = PaiementEnLigne.query.filter_by(reference=reference, client_id=client_id_courant()).first_or_404()
    if request.args.get('annule') and p.statut == 'initie':
        p.statut = 'annule'
        db.session.commit()
    else:
        try:
            actualiser(p)
        except Exception as e:
            current_app.logger.warning("Vérification du paiement %s : %s", reference, e)
    return render_template('egalyx/paiement_retour.html', p=p)


@bp.route('/paiement/cinetpay/notification', methods=['GET', 'POST'])
def notification_cinetpay():
    """Appelé par CinetPay. On ne fait pas confiance au contenu : on revérifie par l'API."""
    from models import PaiementEnLigne
    if request.method == 'GET':
        return '', 200                       # test de disponibilité de l'URL par CinetPay
    ref = request.form.get('cpm_trans_id') or (request.get_json(silent=True) or {}).get('cpm_trans_id')
    if ref and (request.form.get('cpm_site_id') or os.environ.get('CINETPAY_SITE_ID')) == os.environ.get('CINETPAY_SITE_ID'):
        p = PaiementEnLigne.query.filter_by(reference=ref, prestataire='cinetpay').first()
        if p:
            try:
                actualiser(p)
            except Exception as e:
                current_app.logger.error("Notification CinetPay %s : %s", ref, e)
                return jsonify({'statut': 'erreur'}), 500
    return jsonify({'statut': 'ok'})


@bp.route('/paiement/stripe/webhook', methods=['POST'])
def webhook_stripe():
    from models import PaiementEnLigne
    secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    corps = request.get_data()
    if not secret or not calculs.verifier_signature_stripe(corps, request.headers.get('Stripe-Signature'), secret):
        abort(400)
    evt = json.loads(corps.decode())
    if evt.get('type') in ('checkout.session.completed', 'checkout.session.async_payment_succeeded',
                           'checkout.session.expired'):
        obj = (evt.get('data') or {}).get('object') or {}
        p = PaiementEnLigne.query.filter_by(reference=obj.get('client_reference_id'), prestataire='stripe').first()
        if p:
            if not p.reference_prestataire:
                p.reference_prestataire = obj.get('id')
            actualiser(p)
    return jsonify({'recu': True})


def enregistrer(app, csrf=None):
    app.register_blueprint(bp)
    if csrf is not None:
        csrf.exempt(notification_cinetpay)
        csrf.exempt(webhook_stripe)
