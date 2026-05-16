// ============================================
// GESTION DES TICKETS SUPPORT
// ============================================

// Archiver un ticket
function archiverTicket(ticketId, reference) {
    if (!confirm(`Archiver le ticket ${reference} ?\n\nL'incident restera consultable dans les archives.`)) {
        return;
    }
    
    const btn = event.currentTarget;
    const originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    
    fetch(`/support/ticket/${ticketId}/archiver`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('✅ Ticket archivé avec succès', 'success');
            setTimeout(() => location.reload(), 1500);
        } else {
            showNotification('❌ Erreur: ' + data.error, 'danger');
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    })
    .catch(error => {
        showNotification('❌ Erreur de communication', 'danger');
        btn.disabled = false;
        btn.innerHTML = originalHtml;
    });
}

// Supprimer définitivement un ticket
function supprimerTicket(ticketId, reference) {
    if (!confirm(`⚠️ SUPPRESSION DÉFINITIVE ⚠️\n\nSupprimer définitivement le ticket ${reference} ?\n\nCette action est irréversible.`)) {
        return;
    }
    
    fetch(`/support/ticket/${ticketId}/supprimer-definitivement`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('✅ Ticket supprimé définitivement', 'success');
            setTimeout(() => location.reload(), 1500);
        } else {
            showNotification('❌ Erreur: ' + data.error, 'danger');
        }
    })
    .catch(error => {
        showNotification('❌ Erreur: ' + error, 'danger');
    });
}

// Restaurer un ticket archivé
function restaurerTicket(ticketId, reference) {
    if (!confirm(`Restaurer le ticket ${reference} ?`)) return;
    
    fetch(`/support/ticket/${ticketId}/restaurer`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('✅ Ticket restauré', 'success');
            location.reload();
        } else {
            showNotification('❌ Erreur: ' + data.error, 'danger');
        }
    })
    .catch(error => showNotification('❌ Erreur: ' + error, 'danger'));
}

// Notification toast
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} position-fixed top-0 end-0 m-3`;
    notification.style.zIndex = '9999';
    notification.style.minWidth = '300px';
    notification.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'} me-2"></i>
            <div>${message}</div>
            <button type="button" class="btn-close ms-auto" onclick="this.parentElement.parentElement.remove()"></button>
        </div>
    `;
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 3000);
}