// static/js/formules.js
// Gestion des formules côté client

class FormuleManager {
    constructor() {
        this.currentFormule = null;
        this.init();
    }
    
    init() {
        // Récupérer les données de la formule actuelle
        this.loadCurrentFormule();
        
        // Écouter les changements
        this.bindEvents();
    }
    
    loadCurrentFormule() {
        // Cette fonction devrait être appelée avec des données injectées depuis Flask
        // Exemple : {{ current_user.client.formule|tojson|safe }}
        if (window.currentFormuleData) {
            this.currentFormule = window.currentFormuleData;
            this.updateUI();
        }
    }
    
    bindEvents() {
        // Surveiller les tentatives d'accès aux modules restreints
        document.addEventListener('click', (e) => {
            const restrictedLink = e.target.closest('[data-formule-restricted]');
            if (restrictedLink) {
                e.preventDefault();
                this.showRestrictedModal(restrictedLink.dataset.formuleRestricted);
            }
        });
    }
    
    updateUI() {
        if (!this.currentFormule) return;
        
        // Mettre à jour les badges
        this.updateBadges();
        
        // Désactiver les éléments non disponibles
        this.disableRestrictedElements();
        
        // Afficher les statistiques d'utilisation
        this.showUsageStats();
    }
    
    updateBadges() {
        const badges = document.querySelectorAll('.formule-badge');
        badges.forEach(badge => {
            badge.textContent = this.currentFormule.code.toUpperCase();
            badge.className = `badge badge-formule-${this.currentFormule.code}`;
        });
    }
    
    disableRestrictedElements() {
        // Désactiver les liens et boutons pour les modules non disponibles
        this.currentFormule.modules_not_included?.forEach(moduleCode => {
            const elements = document.querySelectorAll(`[data-module="${moduleCode}"]`);
            elements.forEach(element => {
                element.classList.add('disabled');
                element.style.opacity = '0.5';
                element.style.cursor = 'not-allowed';
                
                // Ajouter un tooltip
                element.title = `Module non inclus dans la formule ${this.currentFormule.nom}`;
            });
        });
    }
    
    showRestrictedModal(moduleName) {
        // Afficher une modal avec des options d'upgrade
        const modalHtml = `
            <div class="modal fade" id="restrictedModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Fonctionnalité restreinte</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="text-center mb-4">
                                <i class="fas fa-lock fa-3x text-warning"></i>
                            </div>
                            <p class="text-center">
                                La fonctionnalité <strong>${moduleName}</strong> n'est pas incluse 
                                dans votre formule <strong>${this.currentFormule.nom}</strong>.
                            </p>
                            <div class="alert alert-info">
                                <h6>Formules disponibles :</h6>
                                <!-- Les suggestions seraient injectées depuis le serveur -->
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                Fermer
                            </button>
                            <button type="button" class="btn btn-primary" onclick="location.href='/client-admin/usage'">
                                <i class="fas fa-chart-bar me-2"></i>Voir les options
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Ajouter la modal au DOM
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Afficher la modal
        const modal = new bootstrap.Modal(document.getElementById('restrictedModal'));
        modal.show();
        
        // Nettoyer après fermeture
        document.getElementById('restrictedModal').addEventListener('hidden.bs.modal', function () {
            this.remove();
        });
    }
    
    showUsageStats() {
        // Mettre à jour les compteurs d'utilisation
        const usageElements = document.querySelectorAll('.usage-counter');
        usageElements.forEach(element => {
            const type = element.dataset.usageType;
            const current = element.dataset.current;
            const limit = element.dataset.limit;
            
            const percent = (current / limit) * 100;
            element.textContent = `${current}/${limit} (${Math.round(percent)}%)`;
            
            // Ajouter une classe selon le pourcentage
            if (percent >= 90) {
                element.classList.add('text-danger');
            } else if (percent >= 70) {
                element.classList.add('text-warning');
            } else {
                element.classList.add('text-success');
            }
        });
    }
    
    // API calls
    async checkUsageLimit(type) {
        try {
            const response = await fetch(`/api/formule/check-limit/${type}`);
            const data = await response.json();
            
            if (data.near_limit) {
                this.showLimitWarning(type, data);
            }
            
            return data.can_proceed;
        } catch (error) {
            console.error('Erreur vérification limite:', error);
            return true;
        }
    }
    
    showLimitWarning(type, data) {
        const warningHtml = `
            <div class="alert alert-warning alert-dismissible fade show" role="alert">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <strong>Limite ${type} approchée !</strong>
                Vous avez utilisé ${data.used}/${data.limit} ${type}.
                ${data.percent >= 90 ? 'La limite sera bientôt atteinte.' : ''}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                <div class="mt-2">
                    <a href="/client-admin/usage" class="alert-link">
                        <i class="fas fa-chart-bar me-1"></i>Voir les options d'upgrade
                    </a>
                </div>
            </div>
        `;
        
        // Ajouter l'alerte au début du contenu principal
        const mainContent = document.querySelector('main');
        if (mainContent) {
            mainContent.insertAdjacentHTML('afterbegin', warningHtml);
        }
    }
}

// Initialiser quand le DOM est prêt
document.addEventListener('DOMContentLoaded', () => {
    window.formuleManager = new FormuleManager();
    
    // Injecter les données de la formule depuis Flask
    if (window.currentFormuleData) {
        window.formuleManager.currentFormule = window.currentFormuleData;
        window.formuleManager.updateUI();
    }
});

// Fonctions utilitaires
function checkModuleAccess(moduleCode) {
    if (!window.formuleManager?.currentFormule?.modules) {
        return true; // Pas de restriction si pas de formule
    }
    
    return window.formuleManager.currentFormule.modules[moduleCode] === true;
}

function showFormuleUpgradeModal(formuleId) {
    // Afficher un modal avec les détails de l'upgrade
    fetch(`/api/formule/${formuleId}/details`)
        .then(response => response.json())
        .then(formule => {
            // Afficher les détails de la formule
            // Cette fonction serait personnalisée selon vos besoins
        });
}