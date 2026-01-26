// Scripts JavaScript pour l'application
document.addEventListener('DOMContentLoaded', function() {
    // Initialisation des tooltips Bootstrap
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });

    // Gestion des formulaires dynamiques
    const directionSelect = document.getElementById('direction_id');
    const serviceSelect = document.getElementById('service_id');
    
    if (directionSelect && serviceSelect) {
        directionSelect.addEventListener('change', function() {
            const directionId = this.value;
            
            // Réinitialiser les services
            serviceSelect.innerHTML = '<option value="">Sélectionnez un service</option>';
            
            if (directionId) {
                // Charger les services de la direction sélectionnée
                fetch(`/api/services/${directionId}`)
                    .then(response => response.json())
                    .then(services => {
                        services.forEach(service => {
                            const option = document.createElement('option');
                            option.value = service.id;
                            option.textContent = service.nom;
                            serviceSelect.appendChild(option);
                        });
                    });
            }
        });
    }

    // Graphiques pour le dashboard
    const ctx = document.getElementById('riskChart');
    if (ctx) {
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Faible', 'Moyen', 'Élevé', 'Critique'],
                datasets: [{
                    data: [12, 19, 3, 5],
                    backgroundColor: [
                        '#28a745',
                        '#ffc107',
                        '#fd7e14',
                        '#dc3545'
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                    }
                }
            }
        });
    }
});

// Fonctions utilitaires
function confirmerSuppression(message) {
    return confirm(message || 'Êtes-vous sûr de vouloir supprimer cet élément ?');
}

function afficherChargement() {
    const loader = document.createElement('div');
    loader.className = 'loading-overlay';
    loader.innerHTML = `
        <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">Chargement...</span>
        </div>
    `;
    document.body.appendChild(loader);
}

function cacherChargement() {
    const loader = document.querySelector('.loading-overlay');
    if (loader) {
        loader.remove();
    }
}
// Scripts JavaScript pour l'application de contrôle interne

document.addEventListener('DOMContentLoaded', function() {
    // Initialisation des tooltips Bootstrap
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });

    // Initialisation des popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'))
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl)
    });

    // Gestion des formulaires dynamiques
    initialiserFormulairesDynamiques();
    
    // Configuration des graphiques
    initialiserGraphiques();
    
    // Gestion des filtres
    initialiserFiltres();
});

function initialiserFormulairesDynamiques() {
    // Chargement dynamique des services selon la direction
    const directionSelect = document.getElementById('direction_id');
    const serviceSelect = document.getElementById('service_id');
    
    if (directionSelect && serviceSelect) {
        directionSelect.addEventListener('change', function() {
            const directionId = this.value;
            
            // Réinitialiser les services
            serviceSelect.innerHTML = '<option value="">Sélectionnez un service</option>';
            
            if (directionId) {
                afficherChargement();
                
                fetch(`/api/services/${directionId}`)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Erreur réseau');
                        }
                        return response.json();
                    })
                    .then(services => {
                        services.forEach(service => {
                            const option = document.createElement('option');
                            option.value = service.id;
                            option.textContent = service.nom;
                            serviceSelect.appendChild(option);
                        });
                        cacherChargement();
                    })
                    .catch(error => {
                        console.error('Erreur:', error);
                        cacherChargement();
                        showToast('Erreur lors du chargement des services', 'error');
                    });
            }
        });
    }

    // Calcul automatique du score de risque
    const impactSelect = document.getElementById('impact');
    const probabiliteSelect = document.getElementById('probabilite');
    
    if (impactSelect && probabiliteSelect) {
        const updateScore = function() {
            const impact = parseInt(impactSelect.value);
            const probabilite = parseInt(probabiliteSelect.value);
            
            if (impact && probabilite) {
                const score = impact * probabilite;
                let niveau = '';
                let couleur = '';
                
                if (score <= 4) {
                    niveau = 'Faible';
                    couleur = 'success';
                } else if (score <= 10) {
                    niveau = 'Moyen';
                    couleur = 'warning';
                } else if (score <= 16) {
                    niveau = 'Élevé';
                    couleur = 'danger';
                } else {
                    niveau = 'Critique';
                    couleur = 'dark';
                }
                
                const scorePreview = document.getElementById('scorePreview');
                if (scorePreview) {
                    scorePreview.innerHTML = `
                        <h4 class="text-${couleur}">Score: ${score}</h4>
                        <span class="badge bg-${couleur}">${niveau}</span>
                        <p class="small text-muted mt-2">Impact (${impact}) × Probabilité (${probabilite})</p>
                    `;
                }
            }
        };
        
        impactSelect.addEventListener('change', updateScore);
        probabiliteSelect.addEventListener('change', updateScore);
        
        // Déclencher une première mise à jour
        updateScore();
    }
}

function initialiserGraphiques() {
    // Graphiques seront initialisés dans leurs templates respectifs
}

function initialiserFiltres() {
    // Filtrage des tableaux
    const filtres = document.querySelectorAll('[data-filter]');
    filtres.forEach(filtre => {
        filtre.addEventListener('click', function() {
            const cible = this.getAttribute('data-filter');
            const valeur = this.getAttribute('data-value');
            
            if (cible && valeur) {
                filtrerTableau(cible, valeur);
            }
        });
    });
}

function filtrerTableau(tableauId, valeur) {
    const lignes = document.querySelectorAll(`#${tableauId} tbody tr`);
    
    lignes.forEach(ligne => {
        if (valeur === 'tous' || ligne.getAttribute('data-categorie') === valeur) {
            ligne.style.display = '';
        } else {
            ligne.style.display = 'none';
        }
    });
}

// Fonctions utilitaires
function afficherChargement() {
    const loader = document.createElement('div');
    loader.className = 'loading-overlay';
    loader.innerHTML = `
        <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">Chargement...</span>
        </div>
    `;
    document.body.appendChild(loader);
}

function cacherChargement() {
    const loader = document.querySelector('.loading-overlay');
    if (loader) {
        loader.remove();
    }
}

function showToast(message, type = 'info') {
    // Créer un toast Bootstrap
    const toastContainer = document.getElementById('toastContainer') || createToastContainer();
    
    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : type} border-0`;
    toastEl.setAttribute('role', 'alert');
    
    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl);
    toast.show();
    
    // Nettoyer après fermeture
    toastEl.addEventListener('hidden.bs.toast', function() {
        toastEl.remove();
    });
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '9999';
    document.body.appendChild(container);
    return container;
}

function confirmerSuppression(message = 'Êtes-vous sûr de vouloir supprimer cet élément ?') {
    return confirm(message);
}

function exporterDonnees(format) {
    afficherChargement();
    
    let endpoint = '';
    switch(format) {
        case 'csv':
            endpoint = '/export/risques/csv';
            break;
        case 'excel':
            endpoint = '/export/risques/excel';
            break;
        case 'pdf':
            endpoint = '/export/rapport/pdf';
            break;
        default:
            endpoint = '/export/risques';
    }
    
    fetch(endpoint)
        .then(response => {
            if (!response.ok) {
                throw new Error('Erreur lors de l\'export');
            }
            return response.blob();
        })
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `export_risques.${format}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            cacherChargement();
            showToast('Export réalisé avec succès', 'success');
        })
        .catch(error => {
            console.error('Erreur:', error);
            cacherChargement();
            showToast('Erreur lors de l\'export', 'error');
        });
}

// Gestion des modales dynamiques
function ouvrirModal(modalId) {
    const modal = new bootstrap.Modal(document.getElementById(modalId));
    modal.show();
}

// Formatage des dates
function formaterDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('fr-FR');
}

// Validation des formulaires
function validerFormulaire(formId) {
    const formulaire = document.getElementById(formId);
    if (!formulaire.checkValidity()) {
        formulaire.reportValidity();
        return false;
    }
    return true;
}

// Recherche en temps réel
function initialiserRecherche(inputId, tableauId) {
    const inputRecherche = document.getElementById(inputId);
    if (inputRecherche) {
        inputRecherche.addEventListener('input', function() {
            const terme = this.value.toLowerCase();
            const lignes = document.querySelectorAll(`#${tableauId} tbody tr`);
            
            lignes.forEach(ligne => {
                const texte = ligne.textContent.toLowerCase();
                ligne.style.display = texte.includes(terme) ? '' : 'none';
            });
        });
    }
}