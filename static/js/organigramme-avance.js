class OrganigrammeAvance {
    constructor(containerId, data) {
        this.container = document.getElementById(containerId);
        this.svg = document.getElementById('organigramme-svg');
        this.htmlLayer = document.getElementById('organigramme-html');
        this.data = data;
        this.zoomLevel = 1;
        this.panning = false;
        this.startPoint = { x: 0, y: 0 };
        this.offset = { x: 0, y: 0 };
        this.selectedElement = null;
        this.editMode = false;
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.render();
        this.enableDragAndDrop();
    }

    setupEventListeners() {
        // Zoom avec la molette
        this.container.addEventListener('wheel', (e) => {
            e.preventDefault();
            const delta = -e.deltaY / 1000;
            this.zoom(delta);
        });

        // Pan avec drag
        this.svg.addEventListener('mousedown', (e) => {
            if (e.button === 0) { // Clic gauche seulement
                this.panning = true;
                this.startPoint = { x: e.clientX - this.offset.x, y: e.clientY - this.offset.y };
            }
        });

        document.addEventListener('mousemove', (e) => {
            if (!this.panning) return;
            this.offset.x = e.clientX - this.startPoint.x;
            this.offset.y = e.clientY - this.startPoint.y;
            this.updateTransform();
        });

        document.addEventListener('mouseup', () => {
            this.panning = false;
        });
    }

    zoom(delta) {
        this.zoomLevel += delta;
        this.zoomLevel = Math.max(0.1, Math.min(3, this.zoomLevel));
        this.updateTransform();
    }

    updateTransform() {
        this.svg.style.transform = `translate(${this.offset.x}px, ${this.offset.y}px) scale(${this.zoomLevel})`;
        this.htmlLayer.style.transform = `translate(${this.offset.x}px, ${this.offset.y}px) scale(${this.zoomLevel})`;
    }

    render() {
        this.renderEtapes();
        this.renderLiens();
        this.renderZonesRisque();
    }

    renderEtapes() {
        // Nettoyer les étapes existantes
        this.svg.querySelectorAll('.etape-group').forEach(el => el.remove());
        this.htmlLayer.querySelectorAll('.etape-html').forEach(el => el.remove());

        this.data.etapes.forEach(etape => {
            this.renderEtape(etape);
        });
    }

    renderEtape(etape) {
        const x = etape.position_x || etape.ordre * 300;
        const y = etape.position_y || 100;

        // SVG elements
        const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        group.classList.add('etape-group');
        group.setAttribute('data-etape-id', etape.id);

        // Rectangle de l'étape
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('x', x);
        rect.setAttribute('y', y);
        rect.setAttribute('width', 200);
        rect.setAttribute('height', 80);
        rect.setAttribute('rx', 10);
        rect.setAttribute('ry', 10);
        rect.setAttribute('fill', '#ffffff');
        rect.setAttribute('stroke', '#007bff');
        rect.setAttribute('stroke-width', 2);
        rect.classList.add('etape-rect');

        // Texte
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', x + 100);
        text.setAttribute('y', y + 25);
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('fill', '#333333');
        text.setAttribute('font-size', '12');
        text.setAttribute('font-weight', 'bold');
        text.textContent = `Étape ${etape.ordre}: ${etape.nom}`;

        // Description
        const desc = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        desc.setAttribute('x', x + 100);
        desc.setAttribute('y', y + 45);
        desc.setAttribute('text-anchor', 'middle');
        desc.setAttribute('fill', '#666666');
        desc.setAttribute('font-size', '10');
        desc.textContent = etape.description ? etape.description.substring(0, 30) + '...' : '';

        group.appendChild(rect);
        group.appendChild(text);
        group.appendChild(desc);
        this.svg.appendChild(group);

        // Élément HTML pour l'interaction
        const htmlEtape = document.createElement('div');
        htmlEtape.classList.add('etape-html');
        htmlEtape.style.position = 'absolute';
        htmlEtape.style.left = x + 'px';
        htmlEtape.style.top = y + 'px';
        htmlEtape.style.width = '200px';
        htmlEtape.style.height = '80px';
        htmlEtape.style.pointerEvents = 'auto';
        htmlEtape.style.cursor = 'move';
        htmlEtape.setAttribute('data-etape-id', etape.id);

        if (this.editMode) {
            htmlEtape.addEventListener('dblclick', () => this.editEtape(etape.id));
            htmlEtape.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                this.showContextMenu(e, etape);
            });
        }

        this.htmlLayer.appendChild(htmlEtape);
    }

    renderLiens() {
        this.svg.querySelectorAll('.lien').forEach(el => el.remove());

        this.data.liens.forEach(lien => {
            this.renderLien(lien);
        });
    }

    renderLien(lien) {
        const sourceEtape = this.data.etapes.find(e => e.id === lien.etape_source_id);
        const targetEtape = this.data.etapes.find(e => e.id === lien.etape_cible_id);
        
        if (!sourceEtape || !targetEtape) return;

        const startX = (sourceEtape.position_x || sourceEtape.ordre * 300) + 100;
        const startY = (sourceEtape.position_y || 100) + 80;
        let endX, endY;

        switch(lien.direction) {
            case 'droite':
                endX = (targetEtape.position_x || targetEtape.ordre * 300) - 10;
                endY = (targetEtape.position_y || 100) + 40;
                break;
            case 'gauche':
                endX = (targetEtape.position_x || targetEtape.ordre * 300) + 210;
                endY = (targetEtape.position_y || 100) + 40;
                break;
            case 'haut':
                endX = (targetEtape.position_x || targetEtape.ordre * 300) + 100;
                endY = (targetEtape.position_y || 100) + 80;
                break;
            default: // bas
                endX = (targetEtape.position_x || targetEtape.ordre * 300) + 100;
                endY = (targetEtape.position_y || 100) - 10;
        }

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        let d = '';

        switch(lien.type_lien) {
            case 'laterale':
                d = `M ${startX} ${startY} 
                     C ${startX} ${startY + 50}, ${endX} ${endY - 50}, ${endX} ${endY}`;
                path.setAttribute('stroke', '#28a745');
                break;
            case 'fusion':
                d = `M ${startX} ${startY} 
                     L ${(startX + endX) / 2} ${startY}
                     L ${(startX + endX) / 2} ${endY}
                     L ${endX} ${endY}`;
                path.setAttribute('stroke', '#ffc107');
                break;
            case 'division':
                d = `M ${startX} ${startY} 
                     L ${endX} ${endY}`;
                path.setAttribute('stroke', '#dc3545');
                path.setAttribute('stroke-dasharray', '5,5');
                break;
            default: // normal
                d = `M ${startX} ${startY} L ${endX} ${endY}`;
                path.setAttribute('stroke', '#007bff');
        }

        path.setAttribute('d', d);
        path.setAttribute('fill', 'none');
        path.setAttribute('stroke-width', '2');
        path.setAttribute('marker-end', 'url(#arrowhead)');
        path.classList.add('lien');

        this.svg.appendChild(path);
    }

    renderZonesRisque() {
        this.svg.querySelectorAll('.zone-risque').forEach(el => el.remove());
        this.htmlLayer.querySelectorAll('.zone-risque-html').forEach(el => el.remove());

        this.data.zones_risque.forEach(zone => {
            this.renderZoneRisque(zone);
        });
    }

    renderZoneRisque(zone) {
        // Rectangle de zone de risque
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('x', zone.position_x);
        rect.setAttribute('y', zone.position_y);
        rect.setAttribute('width', zone.largeur);
        rect.setAttribute('height', zone.hauteur);
        rect.setAttribute('fill', this.getRiskColor(zone.niveau_risque));
        rect.setAttribute('stroke', '#dc3545');
        rect.setAttribute('stroke-width', '2');
        rect.setAttribute('stroke-dasharray', '5,5');
        rect.setAttribute('opacity', '0.3');
        rect.classList.add('zone-risque');

        // Texte
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', zone.position_x + zone.largeur / 2);
        text.setAttribute('y', zone.position_y + 20);
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('fill', '#dc3545');
        text.setAttribute('font-size', '11');
        text.setAttribute('font-weight', 'bold');
        text.textContent = `⚠️ ${zone.nom}`;

        const desc = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        desc.setAttribute('x', zone.position_x + zone.largeur / 2);
        desc.setAttribute('y', zone.position_y + 35);
        desc.setAttribute('text-anchor', 'middle');
        desc.setAttribute('fill', '#dc3545');
        desc.setAttribute('font-size', '9');
        desc.textContent = zone.type_risque;

        this.svg.appendChild(rect);
        this.svg.appendChild(text);
        this.svg.appendChild(desc);

        // Élément HTML pour l'interaction
        const htmlZone = document.createElement('div');
        htmlZone.classList.add('zone-risque-html');
        htmlZone.style.position = 'absolute';
        htmlZone.style.left = zone.position_x + 'px';
        htmlZone.style.top = zone.position_y + 'px';
        htmlZone.style.width = zone.largeur + 'px';
        htmlZone.style.height = zone.hauteur + 'px';
        htmlZone.style.pointerEvents = 'auto';
        htmlZone.style.cursor = 'move';
        htmlZone.setAttribute('data-zone-id', zone.id);

        if (this.editMode) {
            htmlZone.addEventListener('dblclick', () => this.editZoneRisque(zone.id));
            htmlZone.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                this.showZoneContextMenu(e, zone);
            });
        }

        this.htmlLayer.appendChild(htmlZone);
    }

    getRiskColor(niveau) {
        const colors = {
            'faible': 'rgba(40, 167, 69, 0.1)',
            'moyen': 'rgba(255, 193, 7, 0.1)',
            'eleve': 'rgba(253, 126, 20, 0.1)',
            'critique': 'rgba(220, 53, 69, 0.1)'
        };
        return colors[niveau] || 'rgba(108, 117, 125, 0.1)';
    }

    enableDragAndDrop() {
        if (!this.editMode) return;

        let draggedElement = null;
        let offset = { x: 0, y: 0 };

        this.htmlLayer.querySelectorAll('.etape-html, .zone-risque-html').forEach(element => {
            element.addEventListener('mousedown', (e) => {
                if (!this.editMode) return;
                
                draggedElement = element;
                const rect = element.getBoundingClientRect();
                offset.x = e.clientX - rect.left;
                offset.y = e.clientY - rect.top;
                
                element.style.zIndex = '1000';
                e.preventDefault();
            });
        });

        document.addEventListener('mousemove', (e) => {
            if (!draggedElement || !this.editMode) return;

            const containerRect = this.container.getBoundingClientRect();
            const x = e.clientX - containerRect.left - offset.x;
            const y = e.clientY - containerRect.top - offset.y;

            draggedElement.style.left = x + 'px';
            draggedElement.style.top = y + 'px';

            // Mettre à jour l'élément SVG correspondant
            this.updateElementPosition(draggedElement, x, y);
        });

        document.addEventListener('mouseup', () => {
            if (!draggedElement) return;

            if (this.editMode) {
                this.saveElementPosition(draggedElement);
            }

            draggedElement.style.zIndex = '';
            draggedElement = null;
        });
    }

    updateElementPosition(htmlElement, x, y) {
        const elementId = htmlElement.getAttribute('data-etape-id') || 
                         htmlElement.getAttribute('data-zone-id');
        const type = htmlElement.classList.contains('etape-html') ? 'etape' : 'zone';

        if (type === 'etape') {
            const svgElement = this.svg.querySelector(`[data-etape-id="${elementId}"]`);
            if (svgElement) {
                svgElement.querySelector('rect').setAttribute('x', x);
                svgElement.querySelector('rect').setAttribute('y', y);
                svgElement.querySelectorAll('text').forEach((text, index) => {
                    text.setAttribute('x', x + 100);
                    text.setAttribute('y', y + 25 + (index * 20));
                });
            }
        } else {
            const svgElement = this.svg.querySelector(`.zone-risque`);
            // Logique similaire pour les zones de risque
        }
    }

    async saveElementPosition(htmlElement) {
        const elementId = htmlElement.getAttribute('data-etape-id') || 
                         htmlElement.getAttribute('data-zone-id');
        const type = htmlElement.classList.contains('etape-html') ? 'etape' : 'zone';
        const x = parseInt(htmlElement.style.left);
        const y = parseInt(htmlElement.style.top);

        try {
            if (type === 'etape') {
                const response = await fetch(`/api/etape/${elementId}/position`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ x, y })
                });

                if (response.ok) {
                    console.log('Position sauvegardée');
                }
            }
            // Logique similaire pour les zones de risque
        } catch (error) {
            console.error('Erreur sauvegarde position:', error);
        }
    }

    editEtape(etapeId) {
        // Ouvrir le modal d'édition d'étape
        const modal = new bootstrap.Modal(document.getElementById('modalModifierEtape'));
        // Pré-remplir le formulaire avec les données de l'étape
        modal.show();
    }

    editZoneRisque(zoneId) {
        // Ouvrir le modal d'édition de zone de risque
        const modal = new bootstrap.Modal(document.getElementById('modalModifierZoneRisque'));
        modal.show();
    }

    showContextMenu(e, etape) {
        // Implémenter un menu contextuel pour les actions rapides
        e.preventDefault();
        // Créer et afficher le menu contextuel
    }

    showZoneContextMenu(e, zone) {
        e.preventDefault();
        // Menu contextuel pour les zones de risque
    }
}

// Fonctions globales
function initOrganigramme() {
    window.organigramme = new OrganigrammeAvance('organigramme-container', organigrammeData);
}

function toggleEditMode() {
    window.organigramme.editMode = !window.organigramme.editMode;
    window.organigramme.enableDragAndDrop();
    
    const btn = document.querySelector('[onclick="toggleEditMode()"]');
    if (window.organigramme.editMode) {
        btn.classList.remove('btn-outline-info');
        btn.classList.add('btn-info');
        btn.innerHTML = '<i class="fas fa-edit"></i> Mode Édition (Activé)';
    } else {
        btn.classList.remove('btn-info');
        btn.classList.add('btn-outline-info');
        btn.innerHTML = '<i class="fas fa-edit"></i> Mode Édition';
    }
}

function zoomIn() {
    window.organigramme.zoom(0.1);
}

function zoomOut() {
    window.organigramme.zoom(-0.1);
}

function resetView() {
    window.organigramme.zoomLevel = 1;
    window.organigramme.offset = { x: 0, y: 0 };
    window.organigramme.updateTransform();
}

function exportOrganigramme() {
    // Implémenter l'export en PNG ou PDF
    html2canvas(document.querySelector('#organigramme-container')).then(canvas => {
        const link = document.createElement('a');
        link.download = `organigramme-${organigrammeData.processus.nom}.png`;
        link.href = canvas.toDataURL();
        link.click();
    });
}