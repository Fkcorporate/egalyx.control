# tasks.py

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class CollecteScheduler:
    """Planificateur intelligent des collectes"""
    
    def __init__(self, app, db):
        self.app = app
        self.db = db
        self.scheduler = BackgroundScheduler()
        self.jobs = {}
        
    def demarrer(self):
        """Démarre le planificateur"""
        self.scheduler.start()
        logger.info("✅ Planificateur de collectes démarré")
        self._programmer_toutes_sources()
        
    def _programmer_toutes_sources(self):
        """Programme toutes les sources actives"""
        with self.app.app_context():
            from models import SourceDonnee
            
            sources = SourceDonnee.query.filter_by(statut='actif').all()
            logger.info(f"Programmation de {len(sources)} sources...")
            
            for source in sources:
                self._programmer_source(source)
    
    def _programmer_source(self, source):
        """Programme une source spécifique"""
        job_id = f"source_{source.id}"
        
        # Définir le trigger
        if source.frequence_rafraichissement < 3600:
            # Moins d'une heure -> toutes les X minutes
            minutes = max(1, source.frequence_rafraichissement // 60)
            trigger = IntervalTrigger(minutes=minutes)
        elif source.frequence_rafraichissement < 86400:
            # Moins d'un jour -> toutes les X heures
            heures = max(1, source.frequence_rafraichissement // 3600)
            trigger = IntervalTrigger(hours=heures)
        else:
            # Par défaut, tous les jours à 2h du matin
            trigger = CronTrigger(hour=2, minute=0)
        
        # Ajouter le job
        job = self.scheduler.add_job(
            func=self._executer_collecte,
            trigger=trigger,
            args=[source.id],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=60
        )
        
        self.jobs[source.id] = job
        logger.info(f"✅ Source {source.nom} programmée (ID: {job_id})")
    
    def _executer_collecte(self, source_id):
        """Exécute une collecte (appelé par le scheduler)"""
        with self.app.app_context():
            from models import SourceDonnee
            from collecte_engine import CollecteEngine
            
            source = SourceDonnee.query.get(source_id)
            if not source or source.statut != 'actif':
                return
            
            logger.info(f"🔄 Exécution auto: {source.nom}")
            
            engine = CollecteEngine(self.app, self.db)
            resultat = engine.collecter_source(source_id)
            
            if resultat['erreurs']:
                logger.warning(f"⚠️ Source {source.nom}: {len(resultat['erreurs'])} erreur(s)")
            else:
                logger.info(f"✅ Source {source.nom}: {len(resultat['kri_collectes'])} KRI mis à jour")
    
    def arreter(self):
        """Arrête le planificateur"""
        self.scheduler.shutdown()
        logger.info("⏹️ Planificateur arrêté")