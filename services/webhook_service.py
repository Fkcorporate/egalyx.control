# services/webhook_service.py
import requests
import json
import hmac
import hashlib
import time
from datetime import datetime
from flask import current_app

class WebhookService:
    """Service d'envoi de webhooks"""
    
    @staticmethod
    def send_webhook(webhook_id, event, data, entite_type=None, entite_id=None):
        """Envoyer un webhook"""
        from models import db, WebhookConfiguration, WebhookDeliveryLog
        
        webhook = WebhookConfiguration.query.get(webhook_id)
        if not webhook or not webhook.is_active:
            return False
        
        start_time = time.time()
        
        try:
            # Préparer le payload
            payload = {
                'event': event,
                'timestamp': datetime.utcnow().isoformat(),
                'data': data,
                'webhook_id': webhook.id,
                'webhook_name': webhook.name
            }
            
            # Préparer les headers
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Egalyx-Webhook/1.0'
            }
            
            # Ajouter les headers personnalisés
            for key, value in webhook.custom_headers.items():
                headers[key] = value
            
            # Ajouter la signature si un secret est défini
            if webhook.secret:
                signature = WebhookService._generate_signature(
                    webhook.secret, 
                    json.dumps(payload)
                )
                headers['X-Webhook-Signature'] = signature
            
            # Envoyer la requête
            if webhook.format == 'json':
                response = requests.post(
                    webhook.url,
                    json=payload,
                    headers=headers,
                    timeout=30
                )
            else:
                response = requests.post(
                    webhook.url,
                    data=payload,
                    headers=headers,
                    timeout=30
                )
            
            duration_ms = int((time.time() - start_time) * 1000)
            success = 200 <= response.status_code < 300
            
            # Enregistrer le log
            log = WebhookDeliveryLog(
                webhook_id=webhook.id,
                client_id=webhook.client_id,
                event=event,
                entite_type=entite_type,
                entite_id=entite_id,
                url=webhook.url,
                payload=payload,
                response_status=response.status_code,
                response_body=response.text[:1000],
                duration_ms=duration_ms,
                success=success,
                error_message=None if success else f"HTTP {response.status_code}"
            )
            db.session.add(log)
            
            # Mettre à jour les statistiques
            webhook.total_sent += 1
            if success:
                webhook.total_success += 1
            else:
                webhook.total_failed += 1
            webhook.last_sent_at = datetime.utcnow()
            if not success:
                webhook.last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            
            db.session.commit()
            
            return success
            
        except requests.exceptions.RequestException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            log = WebhookDeliveryLog(
                webhook_id=webhook.id,
                client_id=webhook.client_id,
                event=event,
                entite_type=entite_type,
                entite_id=entite_id,
                url=webhook.url,
                payload=payload if 'payload' in locals() else None,
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            )
            db.session.add(log)
            
            webhook.total_sent += 1
            webhook.total_failed += 1
            webhook.last_sent_at = datetime.utcnow()
            webhook.last_error = str(e)
            
            db.session.commit()
            
            return False
    
    @staticmethod
    def _generate_signature(secret, payload):
        """Générer une signature HMAC-SHA256"""
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    
    @staticmethod
    def trigger_event(event, data, entite_type=None, entite_id=None, client_id=None):
        """Déclencher tous les webhooks abonnés à un événement"""
        from models import db, WebhookConfiguration
        
        webhooks = WebhookConfiguration.query.filter_by(
            client_id=client_id,
            is_active=True
        ).all()
        
        results = []
        for webhook in webhooks:
            if event in webhook.events:
                success = WebhookService.send_webhook(
                    webhook.id, event, data, entite_type, entite_id
                )
                results.append({'webhook': webhook.name, 'success': success})
        
        return results