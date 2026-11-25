"""
sections/risques.py — Risques : cartographies, risques, évaluations et campagnes d'évaluation, réévaluations, bibliothèque de risques, plans d'action des risques.

Partie d'app.py, déplacée telle quelle le 18/11/2026 (136 routes, 9443 lignes).
Ce fichier est exécuté DANS l'espace de noms d'app.py (voir _inclure_section dans app.py) : il utilise
les mêmes imports, modèles et fonctions que le reste d'app.py, sans rien importer lui-même. Les fonctions
gardent le même nom, les mêmes routes et le même comportement ; seules leurs lignes ont changé de fichier.
Les fonctions utilitaires partagées sont restées dans app.py.
"""
# flake8: noqa  (noms fournis par app.py)


# Route archivage risque
@app.route('/risque/<int:id>/archiver', methods=['POST'])
@login_required
def archiver_risque(id):
    """Archiver un risque"""
    risque = Risque.query.get_or_404(id)
    
    # Vérifier les permissions
    if not (current_user.has_permission('can_manage_risks') or 
            risque.created_by == current_user.id):
        flash('Vous n\'êtes pas autorisé à archiver ce risque', 'error')
        return redirect(url_for('detail_cartographie', id=risque.cartographie_id))
    
    # Formulaire d'archivage
    form = ArchiveRisqueForm()
    
    if request.method == 'POST':
        # Si un formulaire est soumis avec une raison
        if form.reason.data:
            raison = form.reason.data
        else:
            raison = 'Archivage manuel'
        
        # Archiver le risque
        risque.is_archived = True
        risque.archived_at = datetime.utcnow()
        risque.archived_by = current_user.id
        risque.archive_reason = raison
        
        db.session.commit()
        
        # 🔥 SYNCHRONISATION AUTOMATIQUE
        synchroniser_cartographie_apres_action(risque.cartographie_id, 'archivage_risque', current_user.id)
        declencher_mise_a_jour_risque(id, 'archivage', current_user.id, raison)
        
        flash('Risque archivé avec succès', 'success')
        return redirect(url_for('detail_cartographie', id=risque.cartographie_id))
    
    # Si GET, afficher le formulaire
    return render_template('cartographie/archiver_risque.html', form=form, risque=risque)


# Route restauration risque
# Modifiez votre route restaurer_risque pour désactiver CSRF
@app.route('/risque/<int:id>/restaurer', methods=['POST'])
@login_required
def restaurer_risque(id):
    risque = Risque.query.get_or_404(id)
    
    if current_user.role != 'admin' and current_user.id != risque.archived_by:
        flash('Vous n\'êtes pas autorisé à restaurer ce risque', 'error')
        return redirect(url_for('risques_archives'))
    
    risque.is_archived = False
    risque.archived_at = None
    risque.archived_by = None
    risque.archive_reason = None
    
    db.session.commit()
    
    # 🔥 SYNCHRONISATION AUTOMATIQUE
    synchroniser_cartographie_apres_action(risque.cartographie_id, 'restauration_risque', current_user.id)
    declencher_mise_a_jour_risque(id, 'restauration', current_user.id)
    
    flash('Risque restauré avec succès', 'success')
    return redirect(url_for('risques_archives'))


# Faites de même pour la route de suppression
@app.route('/risque/<int:id>/supprimer-definitivement', methods=['POST'])
@login_required
def supprimer_definitivement_risque(id):
    """Supprimer définitivement un risque archivé (admin seulement)"""
    if current_user.role != 'admin':
        flash('Accès non autorisé', 'error')
        return redirect(url_for('risques_archives'))
    
    risque = Risque.query.get_or_404(id)
    
    # Vérifier que le risque est bien archivé
    if not risque.is_archived:
        flash('Seuls les risques archivés peuvent être supprimés définitivement', 'error')
        return redirect(url_for('risques_archives'))
    
    cartographie_id = risque.cartographie_id
    
    # Supprimer les évaluations associées
    EvaluationRisque.query.filter_by(risque_id=id).delete()
    
    # Supprimer les KRI associés
    kri = KRI.query.filter_by(risque_id=id).first()
    if kri:
        MesureKRI.query.filter_by(kri_id=kri.id).delete()
        db.session.delete(kri)
    
    db.session.delete(risque)
    db.session.commit()
    flash('Risque supprimé définitivement avec succès', 'success')
    return redirect(url_for('risques_archives'))


@app.route('/risques/archives')
@login_required
def risques_archives():
    """Page listant tous les risques archivés"""
    risques_archives = Risque.query.filter_by(is_archived=True).all()
    return render_template('cartographie/risques_archives.html', risques=risques_archives)


@app.route('/risque/<int:risque_id>/champ/ajouter', methods=['POST'])
@login_required
def ajouter_champ_personnalise(risque_id):
    """Ajouter un champ personnalisé à un risque"""
    risque = Risque.query.get_or_404(risque_id)
    
    # Vérifier les permissions
    if not (current_user.has_permission('can_manage_risks') or 
            risque.created_by == current_user.id):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('detail_risque', id=risque_id))
    
    champ_config_id = request.form.get('champ_config_id')
    valeur = request.form.get('valeur')
    
    if not champ_config_id:
        flash('Veuillez sélectionner un champ', 'error')
        return redirect(url_for('detail_risque', id=risque_id))
    
    # Récupérer la configuration
    config = ConfigurationChampRisque.query.get(champ_config_id)
    if not config:
        flash('Configuration de champ non trouvée', 'error')
        return redirect(url_for('detail_risque', id=risque_id))
    
    # Vérifier si le champ existe déjà
    existing = ChampPersonnaliseRisque.query.filter_by(
        risque_id=risque_id,
        nom_technique=config.nom_technique
    ).first()
    
    if existing:
        # Mettre à jour la valeur existante
        existing.set_valeur(valeur)
        action = 'modification'
        message = 'Champ mis à jour'
    else:
        # Créer un nouveau champ
        champ = ChampPersonnaliseRisque(
            risque_id=risque_id,
            nom_technique=config.nom_technique
        )
        champ.set_valeur(valeur)
        db.session.add(champ)
        action = 'creation'
        message = 'Champ ajouté'
    
    db.session.commit()
    
    # 🔥 SYNCHRONISATION AUTOMATIQUE
    declencher_mise_a_jour_risque(risque_id, f'champ_personnalise_{action}', current_user.id, {
        'champ': config.nom_technique,
        'valeur': valeur
    })
    
    # Journaliser l'action
    log_activity(current_user.id, action, 
                f'{message} du champ {config.nom_technique} pour risque {risque.reference}', 
                'risque', risque_id)
    
    flash(message, 'success')
    return redirect(url_for('detail_risque', id=risque_id))


@app.route('/risque/champ/<int:id>/editer', methods=['GET'])
@login_required
def get_form_edition_champ(id):
    """Récupérer le formulaire d'édition d'un champ (pour modal AJAX)"""
    champ = ChampPersonnaliseRisque.query.get_or_404(id)
    
    # Vérifier les permissions
    if not (current_user.has_permission('can_manage_risks') or 
            champ.risque.created_by == current_user.id):
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    # Récupérer la configuration
    config = ConfigurationChampRisque.query.filter_by(
        nom_technique=champ.nom_technique
    ).first()
    
    valeur = champ.get_valeur()
    
    # Générer le formulaire selon le type
    html = f'''
    <form method="POST" action="/risque/champ/{id}/modifier">
        <input type="hidden" name="csrf_token" value="{{{{ csrf_token() }}}}">
        
        <div class="mb-3">
            <label class="form-label fw-bold">{config.nom_affichage if config else champ.nom_technique}</label>
    '''
    
    if config:
        if config.type_champ == 'texte':
            valeur_str = valeur or ''
            html += f'<input type="text" class="form-control" name="valeur" value="{valeur_str}">'
        elif config.type_champ == 'textarea':
            valeur_str = valeur or ''
            html += f'<textarea class="form-control" name="valeur" rows="4">{valeur_str}</textarea>'
        elif config.type_champ == 'select':
            html += f'<select class="form-select" name="valeur">'
            if config.valeurs_possibles:
                for option in config.valeurs_possibles:
                    selected = 'selected' if valeur == option else ''
                    html += f'<option value="{option}" {selected}>{option}</option>'
            html += '</select>'
        elif config.type_champ == 'checkbox':
            checked = 'checked' if valeur else ''
            html += f'<div class="form-check"><input type="checkbox" class="form-check-input" name="valeur" value="true" {checked}></div>'
        elif config.type_champ == 'date':
            date_str = valeur.strftime('%Y-%m-%d') if valeur else ''
            html += f'<input type="date" class="form-control" name="valeur" value="{date_str}">'
        elif config.type_champ == 'multiselect':
            html += f'<select class="form-select" name="valeur" multiple size="4">'
            if config.valeurs_possibles:
                for option in config.valeurs_possibles:
                    selected = 'selected' if valeur and option in valeur else ''
                    html += f'<option value="{option}" {selected}>{option}</option>'
            html += '</select>'
            html += '<small class="form-text text-muted">Maintenez Ctrl (Cmd sur Mac) pour sélectionner plusieurs valeurs</small>'
    else:
        # Configuration par défaut pour les champs non configurés
        valeur_str = valeur or ''
        html += f'<input type="text" class="form-control" name="valeur" value="{valeur_str}">'
    
    html += '''
        </div>
        <div class="d-flex justify-content-between">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
            <button type="submit" class="btn btn-primary">Enregistrer</button>
        </div>
    </form>
    '''
    
    return html


@app.route('/risque/champ/<int:id>/modifier', methods=['POST'])
@login_required
def modifier_champ_personnalise(id):
    """Modifier un champ personnalisé"""
    champ = ChampPersonnaliseRisque.query.get_or_404(id)
    
    # Vérifier les permissions
    if not (current_user.has_permission('can_manage_risks') or 
            champ.risque.created_by == current_user.id):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('detail_risque', id=champ.risque_id))
    
    valeur = request.form.get('valeur')
    
    # Gestion spéciale pour les checkbox
    if valeur == 'true':
        valeur = True
    elif valeur == 'false':
        valeur = False
    # Gestion spéciale pour les multiselect
    elif isinstance(valeur, str) and valeur.startswith('[') and valeur.endswith(']'):
        try:
            import json
            valeur = json.loads(valeur)
        except:
            valeur = [valeur]
    
    ancienne_valeur = champ.get_valeur()
    champ.set_valeur(valeur)
    db.session.commit()
    
    # 🔥 SYNCHRONISATION AUTOMATIQUE
    declencher_mise_a_jour_risque(champ.risque_id, 'champ_personnalise_modifie', current_user.id, {
        'champ': champ.nom_technique,
        'ancienne_valeur': ancienne_valeur,
        'nouvelle_valeur': valeur
    })
    
    # Journaliser l'action
    log_activity(current_user.id, 'modification', 
                f'Modification du champ {champ.nom_technique} pour risque {champ.risque.reference}', 
                'risque', champ.risque_id)
    
    flash('Champ modifié avec succès', 'success')
    return redirect(url_for('detail_risque', id=champ.risque_id))


@app.route('/risque/<int:risque_id>/fichier/ajouter', methods=['POST'])
@login_required
def ajouter_fichier_risque(risque_id):
    """Ajouter un fichier à un risque"""
    risque = Risque.query.get_or_404(risque_id)
    
    # Vérifier les permissions
    if not (current_user.has_permission('can_manage_risks') or 
            risque.created_by == current_user.id):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('detail_risque', id=risque_id))
    
    if 'fichier' not in request.files:
        flash('Aucun fichier sélectionné', 'error')
        return redirect(url_for('detail_risque', id=risque_id))
    
    fichier = request.files['fichier']
    
    if fichier.filename == '':
        flash('Aucun fichier sélectionné', 'error')
        return redirect(url_for('detail_risque', id=risque_id))
    
    # Vérifier l'extension
    allowed_extensions = app.config['ALLOWED_EXTENSIONS']
    if '.' in fichier.filename:
        extension = fichier.filename.rsplit('.', 1)[1].lower()
        if extension not in allowed_extensions:
            flash(f'Extension non autorisée: {extension}. Formats autorisés: {", ".join(allowed_extensions)}', 'error')
            return redirect(url_for('detail_risque', id=risque_id))
    
    # Vérifier la taille (max 10Mo par défaut)
    max_size = 10 * 1024 * 1024  # 10Mo en octets
    fichier.seek(0, 2)  # Aller à la fin du fichier
    size = fichier.tell()
    fichier.seek(0)  # Retourner au début
    
    if size > max_size:
        flash(f'Fichier trop volumineux ({size/1024/1024:.2f} Mo). Maximum: 10 Mo', 'error')
        return redirect(url_for('detail_risque', id=risque_id))
    
    # Sauvegarder le fichier
    nom_fichier = secure_filename(fichier.filename)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    nom_unique = f"{timestamp}_{nom_fichier}"
    
    dossier = os.path.join(app.config['UPLOAD_FOLDER_RISQUES'], str(risque_id))
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, nom_unique)
    
    fichier.save(chemin)
    
    # Enregistrer en base
    fichier_db = FichierRisque(
        risque_id=risque_id,
        nom_fichier=nom_fichier,
        chemin_fichier=chemin,
        type_fichier=fichier.content_type,
        taille=size,
        categorie=request.form.get('categorie', 'document'),
        description=request.form.get('description', ''),
        uploaded_by=current_user.id
    )
    
    db.session.add(fichier_db)
    db.session.commit()
    
    # 🔥 SYNCHRONISATION AUTOMATIQUE
    declencher_mise_a_jour_risque(risque_id, 'fichier_ajoute', current_user.id, {
        'fichier': nom_fichier,
        'categorie': request.form.get('categorie', 'document')
    })
    
    # Journaliser l'action
    log_activity(current_user.id, 'creation', 
                f'Ajout du fichier {nom_fichier} au risque {risque.reference}', 
                'risque', risque_id)
    
    flash('Fichier ajouté avec succès', 'success')
    return redirect(url_for('detail_risque', id=risque_id))


@app.route('/risque/fichier/<int:id>/telecharger')
@login_required
def telecharger_fichier_risque(id):
    """Télécharger un fichier attaché à un risque"""
    fichier = FichierRisque.query.get_or_404(id)
    
    # Vérifier les permissions
    if not (current_user.has_permission('can_manage_risks') or 
            fichier.risque.created_by == current_user.id or
            current_user.id == fichier.uploaded_by):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('dashboard'))
    
    # Journaliser le téléchargement
    log_activity(current_user.id, 'consultation', 
                f'Téléchargement du fichier {fichier.nom_fichier} du risque {fichier.risque.reference}', 
                'risque', fichier.risque_id)
    
    return send_file(fichier.chemin_fichier, 
                    as_attachment=True, 
                    download_name=fichier.nom_fichier)


@app.route('/risque/fichier/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_fichier_risque(id):
    """Supprimer un fichier attaché à un risque"""
    _journal(f"🔍 DEBUG: Route supprimer_fichier_risque appelée avec id={id}")
    
    fichier = FichierRisque.query.get_or_404(id)
    risque_id = fichier.risque_id
    
    _journal(f"🔍 DEBUG: Fichier {fichier.nom_fichier} trouvé pour risque {risque_id}")
    
    # Vérifier les permissions
    if not (current_user.has_permission('can_manage_risks') or 
            fichier.risque.created_by == current_user.id or
            current_user.id == fichier.uploaded_by):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('detail_risque', id=risque_id))
    
    try:
        # Supprimer le fichier physique
        if os.path.exists(fichier.chemin_fichier):
            os.remove(fichier.chemin_fichier)
            _journal(f"🔍 DEBUG: Fichier physique supprimé: {fichier.chemin_fichier}")
        
        # Journaliser l'action avant suppression
        log_activity(current_user.id, 'suppression_fichier', 
                    f'Suppression du fichier {fichier.nom_fichier} du risque {fichier.risque.reference}', 
                    'fichier_risque', id)
        
        # Supprimer l'enregistrement en base
        db.session.delete(fichier)
        db.session.commit()
        
        _journal(f"🔍 DEBUG: Enregistrement base supprimé avec succès")
        
        # Synchronisation automatique
        try:
            declencher_mise_a_jour_risque(risque_id, 'fichier_supprime', current_user.id, {
                'fichier': fichier.nom_fichier
            })
        except Exception as e:
            _journal(f"⚠️ Erreur synchronisation: {e}")
        
        flash('Fichier supprimé avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur suppression: {e}")
        flash(f'Erreur lors de la suppression: {str(e)}', 'error')
    
    return redirect(url_for('detail_risque', id=risque_id))


@app.route('/risque/<int:id>/exporter')
@login_required
def exporter_risque(id):
    """Exporter un risque spécifique au format PDF ou Excel"""
    risque = Risque.query.get_or_404(id)
    
    if not current_user.has_permission('can_export_data'):
        flash('Vous n\'avez pas la permission d\'exporter des données', 'error')
        return redirect(url_for('detail_risque', id=id))
    
    # Logique d'export ici
    # Pour l'instant, rediriger vers la page d'export générale
    flash('Fonction d\'export spécifique en développement', 'info')
    return redirect(url_for('detail_risque', id=id))


@app.route('/risque/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_risque(id):
    """Supprimer un risque (uniquement s'il n'a pas d'évaluations)"""
    risque = Risque.query.get_or_404(id)
    
    # Vérifier les permissions
    if current_user.id != risque.created_by and current_user.role != 'admin':
        flash('Vous n\'êtes pas autorisé à supprimer ce risque', 'error')
        return redirect(url_for('detail_risque', id=id))
    
    # Vérifier s'il y a des évaluations associées
    if risque.evaluations:
        flash('Impossible de supprimer ce risque car il a des évaluations associées. Archivez-le à la place.', 'error')
        return redirect(url_for('detail_risque', id=id))
    
    cartographie_id = risque.cartographie_id
    
    # Supprimer les KRI associés s'ils existent
    kri = KRI.query.filter_by(risque_id=id).first()
    if kri:
        MesureKRI.query.filter_by(kri_id=kri.id).delete()
        db.session.delete(kri)
    
    db.session.delete(risque)
    db.session.commit()
    flash('Risque supprimé avec succès', 'success')
    return redirect(url_for('detail_cartographie', id=cartographie_id))


@app.route('/cartographie')
@login_required
@permission_required('can_manage_risks')
def liste_cartographies():
    """Liste des cartographies avec isolation multi-tenant et filtres."""
    from sqlalchemy.orm import joinedload
    from models import CampagneEvaluation, EvaluationRisque

    # ===== VÉRIFICATION DE FORMULE =====
    if current_user.client and current_user.client.formule:
        formule = current_user.client.formule
        if not formule.can_access_module('cartographie'):
            try:
                all_formules = FormuleAbonnement.query.filter(
                    FormuleAbonnement.is_active == True
                ).all()
                upgrade_suggestions = [f for f in all_formules if f.modules.get('cartographie', False)]
                upgrade_suggestions.sort(key=lambda x: x.prix_mensuel or 0)
                return render_template('errors/formule_restricted.html',
                                     module_name='Cartographie des Risques',
                                     current_formule=formule,
                                     upgrade_suggestions=upgrade_suggestions[:3])
            except Exception as e:
                _journal(f"⚠️ Erreur formules upgrade: {e}")
                flash('Ce module n\'est pas inclus dans votre formule actuelle', 'error')
                return redirect(url_for('dashboard'))

    # ===== PARAMÈTRES =====
    mode_vue = request.args.get('mode', 'poles')
    pays_filter = request.args.get('pays', 'tous')
    pole_filter = request.args.get('pole', 'tous')
    direction_filter = request.args.get('direction', 'toutes')
    search_query = request.args.get('search', '')

    # ===== REQUÊTE DE BASE =====
    query = get_client_filter(Cartographie)\
        .filter_by(is_archived=False)\
        .options(
            joinedload(Cartographie.pole),
            joinedload(Cartographie.pole).joinedload(Pole.pays),
            joinedload(Cartographie.direction),
            joinedload(Cartographie.service),
        )

    # ===== FILTRES =====
    if mode_vue == 'pays' and pays_filter != 'tous' and pays_filter.isdigit():
        query = query.join(Cartographie.pole).filter(Pole.pays_id == int(pays_filter))
    if mode_vue == 'poles' and pole_filter != 'tous' and pole_filter.isdigit():
        query = query.filter(Cartographie.pole_id == int(pole_filter))
    if direction_filter != 'toutes' and direction_filter.isdigit():
        query = query.filter(Cartographie.direction_id == int(direction_filter))
    if search_query:
        query = query.filter(
            db.or_(
                Cartographie.nom.ilike(f'%{search_query}%'),
                Cartographie.description.ilike(f'%{search_query}%')
            )
        )

    cartographies = query.all()

    _journal(f"🔍 LISTE CARTOS — {len(cartographies)} cartographies")

    # ===== DONNÉES POUR FILTRES =====
    pays_list = get_client_filter(Pays).filter_by(is_archived=False).order_by(Pays.ordre, Pays.nom).all()
    poles = get_client_filter(Pole).filter_by(is_archived=False).order_by(Pole.ordre).all()
    directions = get_client_filter(Direction).filter_by(is_archived=False, is_active=True).all()

    # ===== ENRICHISSEMENT =====
    cartographies_data = []
    stats_poles = {}
    stats_pays = {}
    stats_globales = {
        'total_cartographies': 0,
        'total_risques': 0,
        'total_evalues': 0,
        'total_critiques': 0,
        'total_eleves': 0,
        'total_moyens': 0,
        'total_faibles': 0,
        'total_non_evalues': 0,
        'niveau_max': 'Faible',
    }

    for cartographie in cartographies:
        # --------------------------------------------
        # 1. CAMPAGNE ACTIVE
        # --------------------------------------------
        campagne_active = CampagneEvaluation.query\
            .filter_by(cartographie_id=cartographie.id, statut='en_cours')\
            .order_by(CampagneEvaluation.created_at.desc())\
            .first()

        # --------------------------------------------
        # 2. RISQUES ACTIFS
        # --------------------------------------------
        risques_actifs = get_client_filter(Risque)\
            .filter_by(cartographie_id=cartographie.id, is_archived=False)\
            .all()

        nb_risques_actifs = len(risques_actifs)

        # --------------------------------------------
        # 3. NIVEAUX BASÉS SUR CAMPAGNE ACTIVE
        # --------------------------------------------
        niveaux = {'Critique': 0, 'Élevé': 0, 'Moyen': 0, 'Faible': 0, 'Non évalué': 0}
        nb_evalues = 0
        derniere_date_eval = None
        nb_a_revaluer = 0

        for risque in risques_actifs:
            evaluation = None

            # Éval campagne active
            if campagne_active:
                evaluation = EvaluationRisque.query\
                    .filter_by(
                        risque_id=risque.id,
                        campagne_id=campagne_active.id
                    )\
                    .order_by(EvaluationRisque.created_at.desc())\
                    .first()

            # Détection réévaluation (N-1)
            if not evaluation:
                eval_n_moins_1 = EvaluationRisque.query\
                    .filter(
                        EvaluationRisque.risque_id == risque.id,
                        EvaluationRisque.date_confirmation.isnot(None)
                    )\
                    .first()
                if eval_n_moins_1:
                    nb_a_revaluer += 1

            if evaluation:
                # Niveau NET avec fallback
                niveau = evaluation.niveau_risque_net or evaluation.niveau_risque

                if niveau in niveaux:
                    niveaux[niveau] += 1
                else:
                    niveaux['Non évalué'] += 1
                nb_evalues += 1

                # Date dernière éval
                date_ev = (evaluation.date_confirmation
                           or evaluation.date_validation
                           or evaluation.date_pre_evaluation)
                if date_ev:
                    if derniere_date_eval is None or date_ev > derniere_date_eval:
                        derniere_date_eval = date_ev
            else:
                niveaux['Non évalué'] += 1

        # --------------------------------------------
        # 4. STATS PAR PÔLE
        # --------------------------------------------
        if cartographie.pole_id:
            if cartographie.pole_id not in stats_poles:
                stats_poles[cartographie.pole_id] = {'total': 0, 'risques': 0}
            stats_poles[cartographie.pole_id]['total'] += 1
            stats_poles[cartographie.pole_id]['risques'] += nb_risques_actifs

        # --------------------------------------------
        # 5. STATS GLOBALES
        # --------------------------------------------
        stats_globales['total_cartographies'] += 1
        stats_globales['total_risques'] += nb_risques_actifs
        stats_globales['total_evalues'] += nb_evalues
        stats_globales['total_critiques'] += niveaux['Critique']
        stats_globales['total_eleves'] += niveaux['Élevé']
        stats_globales['total_moyens'] += niveaux['Moyen']
        stats_globales['total_faibles'] += niveaux['Faible']
        stats_globales['total_non_evalues'] += niveaux['Non évalué']

        # --------------------------------------------
        # 6. DONNÉES ENRICHIES
        # --------------------------------------------
        cartographies_data.append({
            'cartographie': cartographie,
            'nb_risques_actifs': nb_risques_actifs,
            'nb_evalues': nb_evalues,
            'nb_a_revaluer': nb_a_revaluer,
            'risques_actifs': risques_actifs,
            'niveaux_risques': niveaux,
            'campagne_active': campagne_active,
            'derniere_date_eval': derniere_date_eval,
            'pourcentage_evaluation': round((nb_evalues / nb_risques_actifs * 100), 1) if nb_risques_actifs > 0 else 0,
        })

    # ===== STATS PAR PAYS =====
    if mode_vue == 'pays':
        for pays in pays_list:
            cartos_pays = [c for c in cartographies_data
                           if c['cartographie'].pole and c['cartographie'].pole.pays_id == pays.id]
            stats_pays[pays.id] = {
                'total': len(cartos_pays),
                'risques': sum(c['nb_risques_actifs'] for c in cartos_pays) if cartos_pays else 0
            }

    # ===== NIVEAU MAX GLOBAL =====
    for niveau in ['Critique', 'Élevé', 'Moyen', 'Faible']:
        if stats_globales[f'total_{niveau.lower().replace("é", "e")}s' if niveau != 'Critique' else 'total_critiques'] > 0:
            stats_globales['niveau_max'] = niveau
            break

    return render_template(
        'cartographie/liste.html',
        cartographies=cartographies_data,
        poles=poles,
        pays_list=pays_list,
        directions=directions,
        stats_poles=stats_poles,
        stats_pays=stats_pays,
        stats=stats_globales,
        mode_vue=mode_vue,
        pays_filter=pays_filter,
        pole_filter=pole_filter,
        direction_filter=direction_filter,
        search_query=search_query,
        current_user=current_user
    )


@app.route('/cartographie/<int:id>/dupliquer', methods=['POST'])
@login_required
def dupliquer_cartographie(id):
    """Dupliquer une cartographie avec tous ses risques et évaluations"""
    try:
        # CORRECTION : Vérifier l'accès à la cartographie source
        cartographie_source = Cartographie.query.get_or_404(id)
        if not check_client_access(cartographie_source):
            flash('Accès non autorisé à cette cartographie', 'error')
            return redirect(url_for('liste_cartographies'))
        
        from utils import dupliquer_cartographie_complete
        
        # Utiliser la fonction améliorée de duplication
        nouvelle_cartographie_id = dupliquer_cartographie_complete(id, current_user.id)
        
        if nouvelle_cartographie_id:
            # CORRECTION : Vérifier que la nouvelle cartographie a bien le client_id
            nouvelle_carto = Cartographie.query.get(nouvelle_cartographie_id)
            if nouvelle_carto:
                if current_user.role != 'super_admin':
                    nouvelle_carto.client_id = current_user.client_id
                db.session.commit()
            
            flash('Cartographie dupliquée avec succès avec tous ses risques et évaluations', 'success')
            return redirect(url_for('liste_cartographies'))
        else:
            flash('Erreur lors de la duplication de la cartographie', 'error')
            return redirect(url_for('liste_cartographies'))
            
    except Exception as e:
        flash(f'Erreur lors de la duplication : {str(e)}', 'error')
        return redirect(url_for('liste_cartographies'))


@app.route('/cartographie/<int:id>/archiver', methods=['POST'])
@login_required
def archiver_cartographie(id):
    """Archiver une cartographie et tous ses risques"""
    cartographie = Cartographie.query.get_or_404(id)
    
    # CORRECTION : Vérifier l'accès multi-tenant
    if not check_client_access(cartographie):
        flash('Accès non autorisé à cette cartographie', 'error')
        return redirect(url_for('liste_cartographies'))
    
    # Vérifier les permissions
    if current_user.role != 'admin' and current_user.id != cartographie.created_by:
        flash('Vous n\'êtes pas autorisé à archiver cette cartographie', 'error')
        return redirect(url_for('liste_cartographies'))
    
    # Vérifier si déjà archivée
    if getattr(cartographie, 'is_archived', False):
        flash('Cette cartographie est déjà archivée', 'warning')
        return redirect(url_for('liste_cartographies'))
    
    try:
        _journal(f"🔄 Archivage de la cartographie {id}: {cartographie.nom}")
        
        # 1. Compter et archiver tous les risques NON archivés de la cartographie
        risques_archives = 0
        for risque in cartographie.risques:
            # CORRECTION : Vérifier l'accès au risque
            if not check_client_access(risque):
                _journal(f"   ⚠️ Risque {risque.reference} inaccessible, ignoré")
                continue
                
            if not getattr(risque, 'is_archived', False):  # Seulement si pas déjà archivé
                _journal(f"   📝 Archivage du risque {risque.id}: {risque.reference}")
                
                # Mettre à jour les champs d'archivage
                risque.is_archived = True
                risque.archived_at = datetime.utcnow()
                risque.archived_by = current_user.id
                risque.archive_reason = f"Cartographie '{cartographie.nom}' archivée"
                
                risques_archives += 1
            else:
                _journal(f"   ⚠️ Risque {risque.reference} déjà archivé, ignoré")
        
        # 2. Archiver la cartographie elle-même
        cartographie.is_archived = True
        cartographie.archived_at = datetime.utcnow()
        cartographie.archived_by = current_user.id
        cartographie.archive_reason = f"Archivée par {current_user.username}"
        
        db.session.commit()
        _journal(f"✅ Cartographie {id} archivée avec {risques_archives} risques")
        
        flash(f'Cartographie archivée avec succès ({risques_archives} risques archivés)', 'success')
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur lors de l\'archivage : {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erreur lors de l\'archivage : {str(e)}', 'error')
    
    return redirect(url_for('liste_cartographies'))


@app.route('/cartographie/<int:id>/restaurer', methods=['POST'])
@login_required
def restaurer_cartographie(id):
    """Restaurer une cartographie archivée et ses risques"""
    cartographie = Cartographie.query.get_or_404(id)
    
    # CORRECTION : Vérifier l'accès multi-tenant
    if not check_client_access(cartographie):
        flash('Accès non autorisé à cette cartographie', 'error')
        return redirect(url_for('cartographies_archives'))
    
    # Vérifier les permissions
    if current_user.role != 'admin' and current_user.id != cartographie.created_by:
        flash('Vous n\'êtes pas autorisé à restaurer cette cartographie', 'error')
        return redirect(url_for('cartographies_archives'))
    
    if not getattr(cartographie, 'is_archived', False):
        flash('Cette cartographie n\'est pas archivée', 'warning')
        return redirect(url_for('liste_cartographies'))
    
    try:
        _journal(f"🔄 Restauration de la cartographie {id}: {cartographie.nom}")
        
        # 1. Restaurer la cartographie
        cartographie.is_archived = False
        cartographie.archived_at = None
        cartographie.archived_by = None
        cartographie.archive_reason = None
        
        # 2. Restaurer tous les risques associés
        risques_restaures = 0
        for risque in cartographie.risques:
            # CORRECTION : Vérifier l'accès au risque
            if not check_client_access(risque):
                continue
                
            if getattr(risque, 'is_archived', False):
                risque.is_archived = False
                risque.archived_at = None
                risque.archived_by = None
                risque.archive_reason = None
                risques_restaures += 1
        
        db.session.commit()
        
        _journal(f"✅ Cartographie {id} restaurée avec {risques_restaures} risques")
        flash(f'Cartographie restaurée avec succès ({risques_restaures} risques restaurés)', 'success')
        
        # Rediriger vers la liste principale
        return redirect(url_for('liste_cartographies'))
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur lors de la restauration : {str(e)}")
        flash(f'Erreur lors de la restauration : {str(e)}', 'error')
        return redirect(url_for('cartographies_archives'))


@app.route('/cartographies/archives')
@login_required
def cartographies_archives():
    """Afficher les cartographies archivées"""
    # CORRECTION : Utiliser get_client_filter
    cartographies_archivees = get_client_filter(Cartographie)\
        .filter_by(is_archived=True)\
        .order_by(Cartographie.archived_at.desc())\
        .all()
    
    # Pour chaque cartographie archivée, récupérer ses risques archivés
    archives_data = []
    for cartographie in cartographies_archivees:
        # Compter les risques archivés
        risques_archives = [r for r in cartographie.risques 
                           if getattr(r, 'is_archived', False) and check_client_access(r)]
        
        # Récupérer l'utilisateur qui a archivé
        archive_user = None
        if cartographie.archived_by:
            archive_user = User.query.get(cartographie.archived_by)
        
        archives_data.append({
            'cartographie': cartographie,
            'risques_archives': risques_archives,
            'nb_risques_archives': len(risques_archives),
            'archive_user': archive_user,
            'date_archivage': cartographie.archived_at
        })
    
    return render_template('cartographie/archives.html',
                         archives_data=archives_data,
                         current_user=current_user)


@app.route('/cartographie/archive/<int:cartographie_id>/supprimer-definitivement', methods=['POST'])
@login_required
def supprimer_definitivement_cartographie_archive(cartographie_id):
    """Supprimer définitivement une cartographie archivée"""
    if current_user.role != 'admin' and not current_user.is_client_admin:
        flash('Accès non autorisé. Admin uniquement.', 'error')
        return redirect(url_for('cartographies_archives'))
    
    cartographie = Cartographie.query.get_or_404(cartographie_id)
    
    # CORRECTION : Vérifier l'accès multi-tenant
    if not check_client_access(cartographie):
        flash('Accès non autorisé à cette cartographie', 'error')
        return redirect(url_for('cartographies_archives'))
    
    # Vérifier que la cartographie est bien archivée
    if not getattr(cartographie, 'is_archived', False):
        flash('Cette cartographie n\'est pas archivée', 'error')
        return redirect(url_for('liste_cartographies'))
    
    try:
        # Récupérer le nom avant suppression pour le message
        nom_cartographie = cartographie.nom
        
        # Récupérer tous les risques archivés de cette cartographie
        risques_archives = [r for r in cartographie.risques 
                           if getattr(r, 'is_archived', False) and check_client_access(r)]
        nb_risques = len(risques_archives)
        
        # Supprimer les données associées
        for risque in risques_archives:
            # Supprimer les évaluations
            EvaluationRisque.query.filter_by(risque_id=risque.id).delete()
            
            # Supprimer les KRI et mesures
            kri = KRI.query.filter_by(risque_id=risque.id).first()
            if kri:
                MesureKRI.query.filter_by(kri_id=kri.id).delete()
                db.session.delete(kri)
            
            # Supprimer les champs personnalisés (gérer les contraintes NOT NULL)
            try:
                from models import ChampPersonnaliseRisque
                ChampPersonnaliseRisque.query.filter_by(risque_id=risque.id).delete()
            except:
                pass  # Ignorer si la table n'existe pas
            
            # Supprimer le risque
            db.session.delete(risque)
        
        # Supprimer les campagnes d'évaluation associées
        CampagneEvaluation.query.filter_by(cartographie_id=cartographie_id).delete()
        
        # Supprimer la cartographie
        db.session.delete(cartographie)
        
        db.session.commit()
        
        flash(f'Cartographie "{nom_cartographie}" supprimée définitivement ({nb_risques} risques)', 'success')
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur lors de la suppression : {str(e)}")
        flash(f'Erreur lors de la suppression : {str(e)}', 'error')
    
    return redirect(url_for('cartographies_archives'))


@app.route('/cartographie/archive/tout-supprimer', methods=['POST'])
@login_required
def supprimer_toutes_archives_cartographies():
    """Supprimer toutes les cartographies archivées"""
    if current_user.role != 'admin' and not current_user.is_client_admin:
        flash('Accès non autorisé. Admin uniquement.', 'error')
        return redirect(url_for('cartographies_archives'))
    
    try:
        # CORRECTION : Utiliser get_client_filter
        cartographies_archivees = get_client_filter(Cartographie)\
            .filter_by(is_archived=True)\
            .all()
        
        total_cartos = len(cartographies_archivees)
        total_risques = 0
        
        for cartographie in cartographies_archivees:
            # Compter les risques accessibles
            risques_archives = [r for r in cartographie.risques 
                               if getattr(r, 'is_archived', False) and check_client_access(r)]
            total_risques += len(risques_archives)
            
            # Supprimer les données
            for risque in risques_archives:
                EvaluationRisque.query.filter_by(risque_id=risque.id).delete()
                
                kri = KRI.query.filter_by(risque_id=risque.id).first()
                if kri:
                    MesureKRI.query.filter_by(kri_id=kri.id).delete()
                    db.session.delete(kri)
                
                try:
                    from models import ChampPersonnaliseRisque
                    ChampPersonnaliseRisque.query.filter_by(risque_id=risque.id).delete()
                except:
                    pass
                
                db.session.delete(risque)
            
            # Supprimer les campagnes
            CampagneEvaluation.query.filter_by(cartographie_id=cartographie.id).delete()
            
            # Supprimer la cartographie
            db.session.delete(cartographie)
        
        db.session.commit()
        
        flash(f'Toutes les archives ont été supprimées ({total_cartos} cartographies, {total_risques} risques)', 'success')
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur lors de la suppression globale : {str(e)}")
        flash(f'Erreur lors de la suppression globale : {str(e)}', 'error')
    
    return redirect(url_for('cartographies_archives'))


@app.route('/risque/choisir-cartographie')
@login_required
def choisir_cartographie_risque():
    """Page pour choisir une cartographie avant de créer un risque"""
    # CORRECTION : Utiliser get_client_filter
    cartographies = get_client_filter(Cartographie).all()
    
    if not cartographies:
        flash('Aucune cartographie disponible. Veuillez d\'abord créer une cartographie.', 'warning')
        return redirect(url_for('nouvelle_cartographie'))
    
    if len(cartographies) == 1:
        # Si une seule cartographie, rediriger directement
        return redirect(url_for('nouveau_risque', cartographie_id=cartographies[0].id))
    
    return render_template('cartographie/choisir_cartographie.html', 
                         cartographies=cartographies,
                         current_user=current_user)


@app.route('/risque/nouveau-sans-cartographie', methods=['GET', 'POST'])
@login_required
def nouveau_risque_sans_cartographie():
    """Créer un risque sans cartographie spécifique (utilise la première disponible)"""
    # CORRECTION : Utiliser get_client_filter
    cartographies = get_client_filter(Cartographie).all()
    
    if not cartographies:
        flash('Aucune cartographie disponible. Veuillez d\'abord créer une cartographie.', 'error')
        return redirect(url_for('nouvelle_cartographie'))
    
    # Utiliser la première cartographie disponible
    cartographie_id = cartographies[0].id
    
    # CORRECTION : Rediriger avec vérification d'accès
    cartographie = Cartographie.query.get(cartographie_id)
    if cartographie and check_client_access(cartographie):
        return redirect(url_for('nouveau_risque', cartographie_id=cartographie_id))
    else:
        flash('Aucune cartographie accessible', 'error')
        return redirect(url_for('liste_cartographies'))


@app.route('/risque/nouveau', methods=['GET'])
@login_required
def nouveau_risque_sans_carto():
    """Rediriger vers le formulaire de création avec la première cartographie disponible"""
    # Récupérer les cartographies accessibles
    cartographies = get_client_filter(Cartographie).filter_by(is_archived=False).all()
    
    if not cartographies:
        flash('Aucune cartographie disponible. Veuillez d\'abord créer une cartographie.', 'error')
        return redirect(url_for('liste_cartographies'))
    
    # Utiliser la première cartographie
    return redirect(url_for('nouveau_risque', cartographie_id=cartographies[0].id))


@app.route('/cartographie/<int:cartographie_id>/telecharger-rapport-pdf')
@login_required
def telecharger_rapport_cartographie_pdf(cartographie_id):
    """Télécharger un rapport PDF complet de la cartographie avec toutes les campagnes"""
    
    _journal(f"\n📊 DÉBUT GÉNÉRATION RAPPORT PDF - Cartographie ID: {cartographie_id}")
    
    # Récupérer la cartographie avec vérification d'accès
    cartographie = get_client_filter(Cartographie)\
        .filter_by(id=cartographie_id)\
        .first_or_404()
    
    if not check_client_access(cartographie):
        flash('Accès non autorisé à cette cartographie', 'error')
        return redirect(url_for('liste_cartographies'))
    
    _journal(f"✅ Cartographie trouvée: {cartographie.nom}")
    
    # Récupérer toutes les campagnes de cette cartographie
    try:
        campagnes = get_client_filter(CampagneEvaluation)\
            .filter_by(cartographie_id=cartographie_id)\
            .order_by(CampagneEvaluation.date_debut.desc())\
            .all()
        _journal(f"✅ {len(campagnes)} campagnes trouvées")
    except Exception as e:
        _journal(f"❌ Erreur récupération campagnes: {e}")
        campagnes = []
    
    # Récupérer les risques avec leurs évaluations et dispositifs
    try:
        risques_query = get_client_filter(Risque)\
            .filter_by(cartographie_id=cartographie_id, is_archived=False)
        
        # Essayer de charger les relations si elles existent
        try:
            risques_query = risques_query.options(
                joinedload(Risque.dispositifs_maitrise)
            )
        except Exception as e:
            _journal(f"⚠️ Impossible de charger dispositifs_maitrise: {e}")
        
        try:
            risques_query = risques_query.options(
                joinedload(Risque.evaluations).joinedload(EvaluationRisque.campagne)
            )
        except Exception as e:
            _journal(f"⚠️ Impossible de charger evaluations: {e}")
        
        risques = risques_query.all()
        _journal(f"✅ {len(risques)} risques trouvés")
        
    except Exception as e:
        _journal(f"❌ Erreur récupération risques: {e}")
        risques = []
    
    # Structure pour stocker les données
    campagnes_data = []
    tous_risques_avec_evaluations = []
    dispositifs_par_risque = {}
    total_dispositifs = 0
    
    # Pour chaque campagne, récupérer les évaluations
    for campagne in campagnes:
        _journal(f"📊 Traitement campagne: {campagne.nom}")
        evaluations_campagne = []
        
        for risque in risques:
            try:
                # Récupérer l'évaluation pour cette campagne
                evaluation = None
                if hasattr(risque, 'evaluations'):
                    evaluation = next(
                        (e for e in risque.evaluations if e.campagne_id == campagne.id), 
                        None
                    )
                
                if evaluation:
                    # Calculer le score et le niveau
                    cot = cotation_regle.depuis_evaluation(evaluation)
                    evaluations_campagne.append({
                        'risque': risque,
                        'evaluation': evaluation,
                        'score': cot['score_net'] or 0,          # NET = référence
                        'niveau': cot['niveau_net'],
                        'niveau_classe': cotation_regle.qualifier(cot['score_net'])[1],
                        'score_brut': cot['score_brut'] or 0,
                        'niveau_brut': cot['niveau_brut'],
                        'score_net': cot['score_net'] or 0,
                        'niveau_net': cot['niveau_net'],
                        'taux_reduction': cot['taux_reduction'],
                        'impact': cot['impact'],
                        'probabilite': cot['probabilite']
                    })
            except Exception as e:
                _journal(f"⚠️ Erreur traitement risque {risque.id} pour campagne {campagne.id}: {e}")
                continue
        
        # Statistiques de la campagne
        stats = {
            'total': len(risques),
            'evalues': len(evaluations_campagne),
            'non_evalues': len(risques) - len(evaluations_campagne),
            'critiques': len([e for e in evaluations_campagne if e['niveau'] == 'Critique']),
            'eleves': len([e for e in evaluations_campagne if e['niveau'] == 'Élevé']),
            'moyens': len([e for e in evaluations_campagne if e['niveau'] == 'Moyen']),
            'faibles': len([e for e in evaluations_campagne if e['niveau'] == 'Faible'])
        }
        
        campagnes_data.append({
            'campagne': campagne,
            'evaluations': evaluations_campagne,
            'stats': stats
        })
        
        _journal(f"   → {stats['evalues']}/{stats['total']} risques évalués")
    
    # Préparer les données pour tous les risques (toutes campagnes confondues)
    for risque in risques:
        try:
            # Récupérer les dispositifs
            dispositifs = []
            if hasattr(risque, 'dispositifs_maitrise') and risque.dispositifs_maitrise:
                dispositifs = risque.dispositifs_maitrise
                dispositifs_par_risque[risque.id] = dispositifs
                total_dispositifs += len(dispositifs)
            
            # Récupérer les plans d'action
            plans_risque = []
            try:
                from models import PlanAction
                plans_risque = get_client_filter(PlanAction)\
                    .filter_by(risque_id=risque.id)\
                    .all()
            except Exception as e:
                _journal(f"⚠️ Erreur récupération plans pour risque {risque.id}: {e}")
            
            # Récupérer les évaluations
            evaluations_risque = []
            if hasattr(risque, 'evaluations'):
                for e in risque.evaluations:
                    try:
                        cot = cotation_regle.depuis_evaluation(e)
                        evaluations_risque.append({
                            'campagne': e.campagne,
                            'evaluation': e,
                            'score': cot['score_net'] or 0,      # NET = référence
                            'niveau': cot['niveau_net'],
                            'score_brut': cot['score_brut'] or 0,
                            'niveau_brut': cot['niveau_brut'],
                            'score_net': cot['score_net'] or 0,
                            'niveau_net': cot['niveau_net'],
                            'taux_reduction': cot['taux_reduction'],
                            'probabilite_ajustee': cot['probabilite_ajustee'],
                        })
                    except Exception as e:
                        _journal(f"⚠️ Erreur traitement évaluation {e.id}: {e}")
                        continue
            
            tous_risques_avec_evaluations.append({
                'risque': risque,
                'dispositifs': dispositifs,
                'plans': plans_risque,
                'plans_actifs': plans_risque,  # Pour compatibilité avec le template
                'est_evalue': len(evaluations_risque) > 0,
                'evaluations': evaluations_risque,
                'evaluation': evaluations_risque[0] if evaluations_risque else None,
                'score': evaluations_risque[0]['score'] if evaluations_risque else 0,
                'niveau': evaluations_risque[0]['niveau'] if evaluations_risque else "Non évalué",
                'score_brut': evaluations_risque[0]['score_brut'] if evaluations_risque else 0,
                'niveau_brut': evaluations_risque[0]['niveau_brut'] if evaluations_risque else "Non évalué",
                'score_net': evaluations_risque[0]['score_net'] if evaluations_risque else 0,
                'niveau_net': evaluations_risque[0]['niveau_net'] if evaluations_risque else "Non évalué",
                'taux_reduction': evaluations_risque[0]['taux_reduction'] if evaluations_risque else 0,
                'probabilite_ajustee': evaluations_risque[0]['probabilite_ajustee'] if evaluations_risque else None,
            })
            
        except Exception as e:
            _journal(f"⚠️ Erreur traitement risque {risque.id}: {e}")
            continue
    
    _journal(f"✅ Total dispositifs: {total_dispositifs}")
    
    # Compter le total des plans
    total_plans = sum(len(r['plans']) for r in tous_risques_avec_evaluations)
    _journal(f"✅ Total plans: {total_plans}")
    
    # Statistiques globales des plans
    stats_plans = {
        'total': total_plans,
        'en_cours': 0,
        'termines': 0,
        'en_retard': 0
    }
    
    for item in tous_risques_avec_evaluations:
        for plan in item['plans']:
            if plan.statut == 'en_cours':
                stats_plans['en_cours'] += 1
            elif plan.statut == 'termine':
                stats_plans['termines'] += 1
            
            # Vérifier les retards
            if hasattr(plan, 'date_fin_prevue') and plan.date_fin_prevue:
                try:
                    if plan.date_fin_prevue < _aujourdhui() and plan.statut != 'termine':
                        stats_plans['en_retard'] += 1
                except Exception as e:
                    _journal(f"⚠️ Erreur vérification retard plan {plan.id}: {e}")
    
    # Calculer le tableau de Bordeaux
    tableau_bordeaux = {
        'actions_prioritaires': [],
        'surveillance_renforcee': [],
        'surveillance_courante': [],
        'actions_limitees': []
    }
    
    for item in tous_risques_avec_evaluations:
        if item['est_evalue'] and item['score'] > 0:
            niveau = item['niveau']
            if niveau == 'Critique':
                tableau_bordeaux['actions_prioritaires'].append(item)
            elif niveau == 'Élevé':
                tableau_bordeaux['surveillance_renforcee'].append(item)
            elif niveau == 'Moyen':
                tableau_bordeaux['surveillance_courante'].append(item)
            elif niveau == 'Faible':
                tableau_bordeaux['actions_limitees'].append(item)
    
    # Générer la matrice (si disponible)
    matrice_classique = None
    matrice_criticite = None
    matrice_priorisation = None
    
    if campagnes and len(campagnes) > 0:
        try:
            from utils import generer_matrice_risques, generer_matrice_criticite, generer_matrice_priorisation
            matrice_classique = generer_matrice_risques(cartographie, campagnes[0])
            matrice_criticite = generer_matrice_criticite(cartographie, campagnes[0])
            matrice_priorisation = generer_matrice_priorisation(cartographie, campagnes[0])
            _journal("✅ Matrices générées avec succès")
        except ImportError as e:
            _journal(f"⚠️ Fonction de matrice non trouvée: {e}")
        except Exception as e:
            _journal(f"⚠️ Erreur génération matrice: {e}")
    
    # Calculer la progression
    nb_risques_total = len(risques)
    nb_risques_evalues = sum(1 for r in tous_risques_avec_evaluations if r['est_evalue'])
    progression = (nb_risques_evalues / nb_risques_total * 100) if nb_risques_total > 0 else 0
    
    _journal(f"📊 Statistiques finales:")
    _journal(f"   - Risques: {nb_risques_total}")
    _journal(f"   - Évalués: {nb_risques_evalues}")
    _journal(f"   - Progression: {progression}%")
    _journal(f"   - Campagnes: {len(campagnes)}")
    _journal(f"   - Dispositifs: {total_dispositifs}")
    _journal(f"   - Plans: {total_plans}")
    
    # FORCER LE RECHARGEMENT DU TEMPLATE
    template_path = 'rapports/cartographie_pdf.html'
    _journal(f"📝 Chargement du template: {template_path}")
    
    # Vider le cache Jinja2
    app.jinja_env.cache = {}
    _journal("🧹 Cache Jinja2 vidé")
    
    # Vérifier le contenu du template
    try:
        import os
        template_full_path = os.path.join(app.root_path, 'templates', template_path)
        if os.path.exists(template_full_path):
            with open(template_full_path, 'r') as f:
                template_content = f.read()
                _journal(f"📄 Template trouvé: {template_full_path}")
                
                # Vérifier si "campagne.nom" est présent
                if "campagne.nom" in template_content:
                    _journal("⚠️ ATTENTION: 'campagne.nom' trouvé dans le template!")
                    # Remplacer automatiquement
                    template_content = template_content.replace(
                        'Campagne {{ campagne.nom }}',
                        '{% if campagnes and campagnes|length > 0 %}Campagne {{ campagnes[0].nom }}{% else %}Rapport complet{% endif %}'
                    )
                    template_content = template_content.replace(
                        '{{ campagne.nom }}',
                        '{% if campagnes and campagnes|length > 0 %}{{ campagnes[0].nom }}{% else %}Rapport complet{% endif %}'
                    )
                    # Sauvegarder
                    with open(template_full_path, 'w') as f:
                        f.write(template_content)
                    _journal("✅ Template corrigé automatiquement")
        else:
            _journal(f"❌ Template non trouvé: {template_full_path}")
    except Exception as e:
        _journal(f"⚠️ Erreur vérification template: {e}")
    
    # Contexte pour le template
    context = {
        'cartographie': cartographie,
        'campagnes': campagnes,
        'campagnes_data': campagnes_data,
        'tous_risques_avec_evaluations': tous_risques_avec_evaluations,
        'risques_avec_evaluation': tous_risques_avec_evaluations,  # Alias pour compatibilité
        'total_dispositifs': total_dispositifs,
        'dispositifs_par_risque': dispositifs_par_risque,
        'total_plans': total_plans,
        'stats_plans': stats_plans,
        'tableau_bordeaux': tableau_bordeaux,
        'matrice_classique': matrice_classique,
        'matrice_criticite': matrice_criticite,
        'matrice_priorisation': matrice_priorisation,
        'date_generation': datetime.now(),
        'current_user': current_user,
        'nb_risques_total': nb_risques_total,
        'nb_risques_evalues': nb_risques_evalues,
        'progression_campagne': round(progression, 1),
        'has_matrices': matrice_classique is not None,
        # Compteurs par niveau NET (page de garde et synthèse) : absents ici, le rapport complet plantait
        'compteurs_net': {cle: len((tableau_bordeaux or {}).get(source) or [])
                          for cle, source in (('critique', 'actions_prioritaires'), ('eleve', 'surveillance_renforcee'),
                                              ('moyen', 'surveillance_courante'), ('faible', 'actions_limitees'))},
        'stats_dispositifs': {
            'total': total_dispositifs,
            'efficaces': sum(1 for ds in dispositifs_par_risque.values() for d in ds if d.efficacite_reelle and d.efficacite_reelle >= 4),
            'a_evaluer': sum(1 for ds in dispositifs_par_risque.values() for d in ds if not d.efficacite_reelle),
        },
        # Solution de secours: ajouter campagne = None pour éviter l'erreur
        'campagne': None
    }
    
    # Rendre le template PDF
    try:
        from weasyprint import HTML
        from flask import make_response
        
        _journal("🎯 Rendu du template...")
        rendered = render_template(template_path, **context)
        _journal(f"✅ Template rendu, taille: {len(rendered)} caractères")
        
        # Sauvegarder le HTML pour débogage
        debug_path = f"/tmp/debug_rapport_{cartographie_id}.html"
        with open(debug_path, 'w') as f:
            f.write(rendered)
        _journal(f"💾 HTML sauvegardé dans {debug_path}")
        
        _journal("🎯 Génération du PDF...")
        pdf = HTML(string=rendered).write_pdf()
        _journal(f"✅ PDF généré, taille: {len(pdf)} bytes")
        
        filename = f"rapport_complet_{cartographie.nom}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filename = filename.replace(' ', '_').replace('/', '-')
        
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        _journal(f"✅ Rapport PDF généré avec succès: {filename}")
        return response
        
    except Exception as e:
        _journal(f"❌ Erreur génération PDF: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Erreur lors de la génération du PDF: {str(e)}', 'error')
        return redirect(url_for('detail_cartographie', id=cartographie_id))


@app.route('/telecharger_rapport_cartographie_pdf_campagne/<int:cartographie_id>/<int:campagne_id>')
@login_required
def telecharger_rapport_cartographie_pdf_campagne(cartographie_id, campagne_id):
    """Générer un rapport PDF pour une cartographie et une campagne spécifique."""
    # (règle unique : calculer_scores_risque et calculer_maitrise_depuis_dmr viennent de app.py / cotation.py)
    from datetime import datetime

    # ============================================
    # 1. RÉCUPÉRATION CARTOGRAPHIE + CAMPAGNE
    # ============================================
    cartographie = get_client_filter(Cartographie)\
        .filter_by(id=cartographie_id).first_or_404()

    if not check_client_access(cartographie):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_cartographies'))

    campagne = get_client_filter(CampagneEvaluation)\
        .filter_by(id=campagne_id, cartographie_id=cartographie_id)\
        .first_or_404()

    if not check_client_access(campagne):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('detail_cartographie', id=cartographie_id))

    _journal(f"\n📊 Génération rapport PDF")
    _journal(f"   Cartographie: {cartographie.nom}")
    _journal(f"   Campagne: {campagne.nom} (ID={campagne.id})")

    # ============================================
    # 2. RÉCUPÉRATION RISQUES + ÉVALUATIONS
    # ============================================
    risques = get_client_filter(Risque)\
        .filter_by(cartographie_id=cartographie_id, is_archived=False)\
        .order_by(Risque.reference.asc())\
        .all()

    risques_avec_evaluation = []
    dispositifs_par_risque = {}
    total_dispositifs = 0

    for risque in risques:
        if not check_client_access(risque):
            continue

        # ============================================
        # 🔥 ÉVALUATION DE LA CAMPAGNE SPÉCIFIÉE
        # ============================================
        evaluation = get_client_filter(EvaluationRisque)\
            .filter_by(risque_id=risque.id, campagne_id=campagne_id)\
            .order_by(EvaluationRisque.created_at.desc())\
            .first()

        # ============================================
        # 🔥 EXTRACTION DES SCORES ISO (NET PRIORITAIRE)
        # ============================================
        score_brut = 0
        score_net = 0
        niveau_brut = "Non évalué"
        niveau_net = "Non évalué"
        impact_final = None
        probabilite_final = None
        niveau_maitrise = None
        taux_reduction = 0
        probabilite_ajustee = None

        if evaluation:
            impact_final = (evaluation.impact_conf or evaluation.impact_val 
                            or evaluation.impact_pre)
            probabilite_final = (evaluation.probabilite_conf 
                                 or evaluation.probabilite_val 
                                 or evaluation.probabilite_pre)
            niveau_maitrise = (evaluation.niveau_maitrise_conf 
                               or evaluation.niveau_maitrise_val 
                               or evaluation.niveau_maitrise_pre)

            if impact_final and probabilite_final:
                # 🔥 Utiliser le moteur ISO
                scores = calculer_scores_risque(
                    impact_final, probabilite_final, niveau_maitrise
                )
                score_brut = scores['score_brut']
                niveau_brut = scores['niveau_brut']
                score_net = scores['score_net']
                niveau_net = scores['niveau_net']
                taux_reduction = scores['taux_reduction']
                probabilite_ajustee = scores['probabilite_ajustee']

        # ============================================
        # 🔥 DISPOSITIFS (uniquement non archivés)
        # ============================================
        dispositifs = get_client_filter(DispositifMaitrise)\
            .filter_by(risque_id=risque.id, is_archived=False)\
            .all()

        if dispositifs:
            dispositifs_par_risque[risque.id] = dispositifs
            total_dispositifs += len(dispositifs)

        # ============================================
        # 🔥 DMR
        # ============================================
        try:
            niveau_maitrise_dmr = calculer_maitrise_depuis_dmr(dispositifs)
        except Exception:
            niveau_maitrise_dmr = None

        ecart_maitrise = None
        if niveau_maitrise_dmr and niveau_maitrise:
            ecart_maitrise = abs(float(niveau_maitrise) - float(niveau_maitrise_dmr))

        risques_avec_evaluation.append({
            'risque': risque,
            'evaluation': evaluation,
            'est_evalue': evaluation is not None,
            # 🔥 Scores ISO
            'score_brut': score_brut,
            'niveau_brut': niveau_brut,
            'score_net': score_net,
            'niveau_net': niveau_net,
            'score': score_net,             # rétrocompat (utiliser NET)
            'niveau': niveau_net,           # rétrocompat
            'taux_reduction': taux_reduction,
            'probabilite_ajustee': probabilite_ajustee,
            'impact': impact_final,
            'probabilite': probabilite_final,
            'niveau_maitrise': niveau_maitrise,
            'niveau_maitrise_dmr': niveau_maitrise_dmr,
            'ecart_maitrise': ecart_maitrise,
            'dispositifs': dispositifs,
            'nb_dispositifs': len(dispositifs),
        })

    # ============================================
    # 3. MATRICE
    # ============================================
    matrice_classique = None
    matrice_criticite = None
    matrice_priorisation = None

    evaluations_valides = [
        item['evaluation'] for item in risques_avec_evaluation
        if item['est_evalue'] and item['impact'] and item['probabilite']
    ]

    _journal(f"   📊 {len(evaluations_valides)} évaluations valides")

    if evaluations_valides:
        try:
            from utils import (
                generer_matrice_classique_propre,
                generer_matrice_criticite_propre,
                generer_matrice_priorisation_propre,
            )
            matrice_classique = generer_matrice_classique_propre(evaluations_valides)
            matrice_criticite = generer_matrice_criticite_propre(evaluations_valides)
            matrice_priorisation = generer_matrice_priorisation_propre(evaluations_valides)
            _journal(f"   ✅ 3 matrices générées")
        except Exception as e:
            _journal(f"   ❌ Erreur matrice: {e}")
            import traceback
            traceback.print_exc()

    # ============================================
    # 4. TABLEAU DE BORDEAUX (basé sur NET)
    # ============================================
    tableau_bordeaux = {
        'actions_prioritaires': [],
        'surveillance_renforcee': [],
        'surveillance_courante': [],
        'actions_limitees': []
    }

    for item in risques_avec_evaluation:
        if not item['est_evalue']:
            continue

        niveau = item['niveau_net']
        if niveau == 'Critique':
            tableau_bordeaux['actions_prioritaires'].append(item)
        elif niveau == 'Élevé':
            tableau_bordeaux['surveillance_renforcee'].append(item)
        elif niveau == 'Moyen':
            tableau_bordeaux['surveillance_courante'].append(item)
        elif niveau == 'Faible':
            tableau_bordeaux['actions_limitees'].append(item)

    # Tri par score NET décroissant
    for cat in tableau_bordeaux:
        tableau_bordeaux[cat].sort(
            key=lambda x: -(x['score_net'] or 0)
        )

    # ============================================
    # 5. STATISTIQUES PLANS D'ACTION
    # ============================================
    total_plans = 0
    stats_plans = {'total': 0, 'en_cours': 0, 'termines': 0, 'en_retard': 0}
    aujourdhui = _aujourdhui()

    for item in risques_avec_evaluation:
        plans = get_client_filter(PlanAction)\
            .filter_by(risque_id=item['risque'].id, is_archived=False)\
            .all()

        item['plans_actifs'] = plans
        total_plans += len(plans)
        stats_plans['total'] += len(plans)

        for plan in plans:
            if plan.statut == 'en_cours':
                stats_plans['en_cours'] += 1
            elif plan.statut == 'termine':
                stats_plans['termines'] += 1

            if (plan.date_fin_prevue and plan.date_fin_prevue < aujourdhui
                and plan.statut != 'termine'):
                stats_plans['en_retard'] += 1

    # ============================================
    # 6. STATISTIQUES DISPOSITIFS
    # ============================================
    stats_dispositifs = {
        'total': total_dispositifs,
        'efficaces': 0,
        'a_evaluer': 0,
    }
    for dispositifs in dispositifs_par_risque.values():
        for d in dispositifs:
            if d.efficacite_reelle and d.efficacite_reelle >= 4:
                stats_dispositifs['efficaces'] += 1
            if not d.efficacite_reelle:
                stats_dispositifs['a_evaluer'] += 1

    # ============================================
    # 7. CONTEXTE
    # ============================================
    nb_risques_total = len(risques_avec_evaluation)
    nb_risques_evalues = sum(1 for r in risques_avec_evaluation if r['est_evalue'])
    progression = (nb_risques_evalues / nb_risques_total * 100) if nb_risques_total > 0 else 0

    # Compteurs par niveau NET
    compteurs_net = {
        'critique': len(tableau_bordeaux['actions_prioritaires']),
        'eleve': len(tableau_bordeaux['surveillance_renforcee']),
        'moyen': len(tableau_bordeaux['surveillance_courante']),
        'faible': len(tableau_bordeaux['actions_limitees']),
    }

    context = {
        'cartographie': cartographie,
        'campagne': campagne,
        'campagnes': [campagne],
        'date_generation': datetime.now(),
        'current_user': current_user,

        # Stats
        'nb_risques_total': nb_risques_total,
        'nb_risques_evalues': nb_risques_evalues,
        'progression_campagne': round(progression, 1),
        'compteurs_net': compteurs_net,

        # Données
        'risques_avec_evaluation': risques_avec_evaluation,
        'tableau_bordeaux': tableau_bordeaux,
        'total_dispositifs': total_dispositifs,
        'dispositifs_par_risque': dispositifs_par_risque,
        'stats_dispositifs': stats_dispositifs,

        # Plans
        'total_plans': total_plans,
        'stats_plans': stats_plans,

        # Matrices
        'matrice_classique': matrice_classique,
        'matrice_criticite': matrice_criticite,
        'matrice_priorisation': matrice_priorisation,
        'has_matrices': matrice_classique is not None,
    }

    _journal(f"   ✅ {nb_risques_evalues}/{nb_risques_total} risques évalués")

    # ============================================
    # 8. GÉNÉRATION PDF
    # ============================================
    try:
        from weasyprint import HTML
        from flask import make_response

        rendered = render_template('rapports/cartographie_pdf.html', **context)
        pdf = HTML(string=rendered).write_pdf()

        filename = (f"rapport_{cartographie.nom}_{campagne.nom}_"
                    f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        filename = filename.replace(' ', '_').replace('/', '-')

        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'

        _journal(f"   ✅ PDF généré: {filename}")
        return response

    except Exception as e:
        _journal(f"   ❌ Erreur PDF: {e}")
        import traceback
        traceback.print_exc()
        flash('Erreur lors de la génération du PDF', 'error')
        return redirect(url_for('detail_cartographie', id=cartographie_id))


@app.route('/campagne/<int:campagne_id>/activer', methods=['POST'])
@login_required
def activer_campagne(campagne_id):
    """Activer une campagne comme campagne active de la cartographie"""
    
    campagne = CampagneEvaluation.query.get_or_404(campagne_id)
    cartographie = campagne.cartographie
    
    if not check_client_access(cartographie):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_cartographies'))
    
    # Vérifier les permissions
    if not current_user.has_permission('can_manage_risks'):
        flash('Vous n\'avez pas la permission de gérer les campagnes', 'error')
        return redirect(url_for('liste_campagnes_cartographie', cartographie_id=cartographie.id))
    
    try:
        # 1. Désactiver l'ancienne campagne active
        ancienne_active = cartographie.get_campagne_active()
        if ancienne_active:
            # On garde le statut de l'ancienne campagne (ne pas la modifier)
            pass
        
        # 2. Définir la nouvelle campagne comme active
        cartographie.campagne_active_id = campagne.id
        
        # 3. S'assurer que la campagne est en cours
        if campagne.statut != 'en_cours':
            campagne.statut = 'en_cours'
        
        campagne.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # 4. Log
        log_activity(
            current_user.id,
            'activation_campagne',
            f"Campagne '{campagne.nom}' activée pour la cartographie '{cartographie.nom}'",
            'campagne',
            campagne.id
        )
        
        flash(f'✅ Campagne "{campagne.nom}" activée avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur lors de l'activation: {str(e)}")
        flash(f'❌ Erreur lors de l\'activation: {str(e)}', 'error')
    
    return redirect(url_for('liste_campagnes_cartographie', cartographie_id=cartographie.id))


@app.route('/cartographie/<int:cartographie_id>/campagnes')
@login_required
def liste_campagnes_cartographie(cartographie_id):
    """Afficher toutes les campagnes d'une cartographie"""
    cartographie = Cartographie.query.get_or_404(cartographie_id)
    
    if not check_client_access(cartographie):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_cartographies'))
    
    # Vérifier si on veut voir les archives
    voir_archives = request.args.get('archives', 'non') == 'oui'
    
    # Construire la requête
    query = CampagneEvaluation.query.filter_by(cartographie_id=cartographie_id)
    
    # Filtrer selon si on veut voir les archives ou non
    if voir_archives:
        # Si on veut voir les archives, on ne filtre QUE les archives
        campagnes = query.filter(CampagneEvaluation.statut == 'archivee')\
                         .order_by(CampagneEvaluation.date_debut.desc()).all()
    else:
        # Si on veut voir les actives, on exclut les archives
        campagnes = query.filter(CampagneEvaluation.statut != 'archivee')\
                         .order_by(CampagneEvaluation.date_debut.desc()).all()
    
    # Calculer les statistiques - CORRECTION ICI
    total_risques = Risque.query\
        .filter_by(cartographie_id=cartographie_id, is_archived=False)\
        .count()
    
    campagnes_data = []
    for campagne in campagnes:
        risques_evalues = EvaluationRisque.query\
            .join(Risque)\
            .filter(
                Risque.cartographie_id == cartographie_id,
                Risque.is_archived == False,
                EvaluationRisque.campagne_id == campagne.id
            )\
            .count()
        
        progression = (risques_evalues / total_risques * 100) if total_risques > 0 else 0
        
        campagnes_data.append({
            'campagne': campagne,
            'total_risques': total_risques,
            'risques_evalues': risques_evalues,
            'progression': progression,
            'est_active': (campagne.id == cartographie.campagne_active_id) if hasattr(cartographie, 'campagne_active_id') else False
        })
    
    # Statistiques globales - CALCUL CORRECT
    # Pour calculer correctement, il faut toutes les campagnes
    toutes_campagnes = CampagneEvaluation.query\
        .filter_by(cartographie_id=cartographie_id)\
        .all()
    
    stats = {
        'total': len([c for c in toutes_campagnes if c.statut != 'archivee']),
        'archives': len([c for c in toutes_campagnes if c.statut == 'archivee']),
        'en_cours': len([c for c in toutes_campagnes if c.statut == 'en_cours']),
        'terminees': len([c for c in toutes_campagnes if c.statut == 'terminee'])
    }
    
    return render_template('campagnes/liste.html',
                         cartographie=cartographie,
                         campagnes_data=campagnes_data,
                         stats=stats,
                         voir_archives=voir_archives,
                         current_user=current_user)


@app.route('/cartographie/<int:cartographie_id>/campagnes/supprimer-toutes-archives', methods=['POST'])
@login_required
def supprimer_toutes_campagnes_archivees(cartographie_id):
    """Supprimer toutes les campagnes archivées"""
    if current_user.role != 'admin' and not current_user.is_client_admin:
        flash('Accès non autorisé. Admin uniquement.', 'error')
        return redirect(url_for('liste_campagnes_cartographie', cartographie_id=cartographie_id))
    
    try:
        # Récupérer toutes les campagnes archivées
        campagnes_archivees = CampagneEvaluation.query\
            .filter_by(cartographie_id=cartographie_id, is_archived=True)\
            .all()
        
        count = 0
        for campagne in campagnes_archivees:
            # Vérifier s'il y a des évaluations
            evaluations_count = EvaluationRisque.query.filter_by(campagne_id=campagne.id).count()
            if evaluations_count == 0:  # Ne supprimer que si pas d'évaluations
                db.session.delete(campagne)
                count += 1
        
        db.session.commit()
        flash(f'{count} campagne(s) archivée(s) supprimée(s)', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
    
    return redirect(url_for('liste_campagnes_cartographie', cartographie_id=cartographie_id, archives='oui'))


@app.route('/cartographie/<int:cartographie_id>/cloturer-campagne/<int:campagne_id>')
@login_required
def cloturer_campagne_specifique(cartographie_id, campagne_id):
    """Clôturer une campagne spécifique"""
    from egalyx.commun import jeton_lien_valide
    if not jeton_lien_valide():
        flash("Lien expiré ou invalide : relancez l'action depuis la page.", 'warning')
        return redirect(url_for('detail_cartographie', id=cartographie_id))
    campagne = CampagneEvaluation.query.get_or_404(campagne_id)
    
    if campagne.cartographie_id != cartographie_id or not check_client_access(campagne.cartographie):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_cartographies'))
    
    if campagne.statut != 'en_cours':
        flash('Seules les campagnes en cours peuvent être clôturées', 'error')
        return redirect(url_for('liste_campagnes_cartographie', cartographie_id=cartographie_id))
    
    campagne.statut = 'terminee'
    campagne.date_fin = _aujourdhui()
    campagne.updated_at = datetime.utcnow()
    
    db.session.commit()
    flash(f'Campagne "{campagne.nom}" clôturée avec succès', 'success')
    return redirect(url_for('liste_campagnes_cartographie', cartographie_id=cartographie_id))


@app.route('/campagne/<int:campagne_id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_campagne(campagne_id):
    """Modifier une campagne d'évaluation"""
    campagne = CampagneEvaluation.query.get_or_404(campagne_id)
    cartographie = campagne.cartographie
    
    if not check_client_access(cartographie):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_cartographies'))
    
    # Vérifier les permissions
    if not current_user.has_permission('can_manage_risks'):
        flash('Vous n\'avez pas la permission de modifier les campagnes', 'error')
        return redirect(url_for('liste_campagnes_cartographie', cartographie_id=cartographie.id))
    
    form = CampagneForm(obj=campagne)
    
    if form.validate_on_submit():
        campagne.nom = form.nom.data
        campagne.description = form.description.data
        campagne.date_debut = form.date_debut.data
        campagne.date_fin = form.date_fin.data
        
        # Ne pas permettre de modifier le statut si la campagne est terminée
        if campagne.statut != 'terminee':
            campagne.statut = form.statut.data
        
        campagne.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Campagne modifiée avec succès', 'success')
        return redirect(url_for('liste_campagnes_cartographie', cartographie_id=cartographie.id))
    
    return render_template('campagnes/form_modifier.html',
                         form=form,
                         campagne=campagne,
                         cartographie=cartographie)


@app.route('/campagne/<int:campagne_id>/archiver', methods=['POST'])
@login_required
def archiver_campagne(campagne_id):
    """Archiver une campagne d'évaluation - VERSION CORRIGÉE"""
    campagne = CampagneEvaluation.query.get_or_404(campagne_id)
    cartographie = campagne.cartographie
    
    if not check_client_access(cartographie):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_cartographies'))
    
    # Vérifier les permissions
    if not current_user.has_permission('can_archive_data'):
        flash('Vous n\'avez pas la permission d\'archiver', 'error')
        return redirect(url_for('liste_campagnes_cartographie', cartographie_id=cartographie.id))
    
    _journal(f"🔍 DEBUG - Archivage campagne {campagne_id}: {campagne.nom}")
    _journal(f"🔍 DEBUG - Statut AVANT: '{campagne.statut}'")
    
    try:
        # CORRECTION ICI : Il faut changer le statut en 'archivee'
        campagne.statut = 'archivee'  # <-- CE CHANGEMENT EST CRUCIAL !
        campagne.archived_at = datetime.utcnow()
        campagne.archived_by = current_user.id
        campagne.updated_at = datetime.utcnow()
        
        _journal(f"🔍 DEBUG - Statut APRÈS: '{campagne.statut}'")
        
        db.session.commit()
        
        # Vérifier
        campagne_refresh = CampagneEvaluation.query.get(campagne_id)
        _journal(f"🔍 DEBUG - Vérification après commit: statut='{campagne_refresh.statut}'")
        
        flash(f'Campagne "{campagne.nom}" archivée avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur lors de l'archivage: {str(e)}")
        flash(f'Erreur lors de l\'archivage: {str(e)}', 'error')
    
    return redirect(url_for('liste_campagnes_cartographie', cartographie_id=cartographie.id))


@app.route('/campagne/<int:campagne_id>/desarchiver', methods=['POST'])
@login_required
def desarchiver_campagne(campagne_id):
    """Désarchiver une campagne d'évaluation - VERSION CORRIGÉE"""
    campagne = CampagneEvaluation.query.get_or_404(campagne_id)
    cartographie = campagne.cartographie
    
    if not check_client_access(cartographie):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_cartographies'))
    
    # Vérifier les permissions
    if not current_user.has_permission('can_archive_data'):
        flash('Vous n\'avez pas la permission de désarchiver', 'error')
        return redirect(url_for('liste_campagnes_cartographie', cartographie_id=cartographie.id))
    
    _journal(f"🔍 DEBUG - Désarchivage campagne {campagne_id}: {campagne.nom}")
    _journal(f"🔍 DEBUG - Statut AVANT: '{campagne.statut}'")
    
    try:
        # CORRECTION ICI : Remettre un statut actif
        campagne.statut = 'en_cours'  # ou 'terminee' selon ce qu'elle était avant
        campagne.archived_at = None
        campagne.archived_by = None
        campagne.updated_at = datetime.utcnow()
        
        _journal(f"🔍 DEBUG - Statut APRÈS: '{campagne.statut}'")
        
        db.session.commit()
        
        flash(f'Campagne "{campagne.nom}" désarchivée avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur lors du désarchivage: {str(e)}")
        flash(f'Erreur lors du désarchivage: {str(e)}', 'error')
    
    return redirect(url_for('liste_campagnes_cartographie', cartographie_id=cartographie.id, archives='oui'))


@app.route('/campagne/<int:campagne_id>/supprimer', methods=['POST'])
@login_required
def supprimer_campagne(campagne_id):
    """Supprimer une campagne d'évaluation"""
    campagne = CampagneEvaluation.query.get_or_404(campagne_id)
    cartographie = campagne.cartographie
    
    if not check_client_access(cartographie):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_cartographies'))
    
    # Vérifier les permissions
    if current_user.role != 'admin' and not current_user.is_client_admin:
        flash('Seuls les administrateurs peuvent supprimer des campagnes', 'error')
        return redirect(url_for('liste_campagnes_cartographie', cartographie_id=cartographie.id))
    
    # Vérifier si la campagne est active
    if hasattr(cartographie, 'campagne_active_id') and cartographie.campagne_active_id == campagne_id:
        flash('Impossible de supprimer la campagne active. Changez d\'abord de campagne active.', 'error')
        return redirect(url_for('liste_campagnes_cartographie', cartographie_id=cartographie.id))
    
    # Vérifier s'il y a des évaluations associées
    evaluations_count = EvaluationRisque.query.filter_by(campagne_id=campagne_id).count()
    
    try:
        nom_campagne = campagne.nom
        
        if evaluations_count > 0:
            # Option 1 : Supprimer aussi les évaluations
            # Supprimer les évaluations associées
            EvaluationRisque.query.filter_by(campagne_id=campagne_id).delete()
            
            # Supprimer la campagne
            db.session.delete(campagne)
            
            flash(f'Campagne "{nom_campagne}" supprimée avec succès ({evaluations_count} évaluation(s) supprimée(s))', 'success')
        else:
            # Option 2 : Si pas d'évaluations, suppression simple
            db.session.delete(campagne)
            flash(f'Campagne "{nom_campagne}" supprimée avec succès', 'success')
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur lors de la suppression: {str(e)}")
        flash(f'Erreur lors de la suppression: {str(e)}', 'error')
    
    # Rediriger vers la bonne page (archives ou actives)
    if campagne.statut == 'archivee':
        return redirect(url_for('liste_campagnes_cartographie', cartographie_id=cartographie.id, archives='oui'))
    else:
        return redirect(url_for('liste_campagnes_cartographie', cartographie_id=cartographie.id))


@app.route('/risque/<int:risque_id>/dispositif/nouveau', methods=['GET', 'POST'])
@login_required
def nouveau_dispositif(risque_id):
    """Créer un nouveau dispositif de maîtrise"""
    risque = Risque.query.get_or_404(risque_id)
    
    if not check_client_access(risque):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('detail_risque', id=risque_id))
    
    form = DispositifMaitriseForm()
    
    # Pré-remplir les choix
    utilisateurs = get_client_filter(User).filter_by(is_active=True).all()
    form.responsable_id.choices = [(0, 'Non assigné')] + \
        [(u.id, f"{u.username} - {u.role}") for u in utilisateurs]
    
    directions = get_client_filter(Direction).all()
    form.direction_id.choices = [(0, 'Non spécifié')] + \
        [(d.id, d.nom) for d in directions]
    
    services = get_client_filter(Service).all()
    form.service_id.choices = [(0, 'Non spécifié')] + \
        [(s.id, s.nom) for s in services]
    
    if form.validate_on_submit():
        # Générer une référence automatique
        try:
            dernier_dispositif = DispositifMaitrise.query\
                .filter(DispositifMaitrise.reference.like(f'DM-{risque.reference}-%'))\
                .order_by(DispositifMaitrise.reference.desc())\
                .first()
            
            if dernier_dispositif:
                try:
                    num = int(dernier_dispositif.reference.split('-')[-1]) + 1
                except:
                    num = 1
            else:
                num = 1
        except:
            num = 1
        
        reference = f"DM-{risque.reference}-{num:03d}"
        
        # 🔴 CORRECTION CRITIQUE : Forcer le client_id à partir du risque
        client_id = risque.client_id or current_user.client_id
        
        # Créer le dispositif
        dispositif = DispositifMaitrise(
            risque_id=risque_id,
            reference=reference,
            nom=form.nom.data,
            description=form.description.data,
            type_dispositif=form.type_dispositif.data,
            nature=form.nature.data,
            frequence=form.frequence.data,
            responsable_id=form.responsable_id.data if form.responsable_id.data != 0 else None,
            direction_id=form.direction_id.data if form.direction_id.data != 0 else None,
            service_id=form.service_id.data if form.service_id.data != 0 else None,
            efficacite_attendue=form.efficacite_attendue.data if form.efficacite_attendue.data != 0 else None,
            date_mise_en_place=form.date_mise_en_place.data,
            statut='actif',
            created_by=current_user.id,
            client_id=client_id  # ← CORRIGÉ
        )
        
        db.session.add(dispositif)
        db.session.commit()
        
        flash('Dispositif de maîtrise créé avec succès', 'success')
        return redirect(url_for('liste_dispositifs_risque', risque_id=risque_id))
    
    return render_template('dispositifs/form.html',
                         form=form,
                         risque=risque,
                         action='creer')


@app.route('/risque/<int:risque_id>/plan-action/nouveau', methods=['GET', 'POST'])
@login_required
def nouveau_plan_action_pour_risque(risque_id):
    """Créer un nouveau plan d'action pour un risque - VERSION CORRIGÉE"""
    
    _journal(f"\n📝 CRÉATION PLAN D'ACTION POUR RISQUE {risque_id}")
    _journal(f"   Utilisateur: {current_user.username}")
    _journal(f"   Rôle: {current_user.role}")
    _journal(f"   Client ID: {current_user.client_id}")
    
    # 1. Vérifier l'accès au risque
    risque = Risque.query.get_or_404(risque_id)
    
    if not check_client_access(risque):
        _journal(f"   ❌ Accès non autorisé au risque {risque_id}")
        flash('Accès non autorisé', 'error')
        return redirect(url_for('detail_risque', id=risque_id))
    
    _journal(f"   ✅ Risque accédé: {risque.reference}")
    
    # 2. Vérifier les permissions utilisateur
    if not current_user.has_permission('can_manage_action_plans'):
        _journal(f"   ❌ Permission 'can_manage_action_plans' manquante")
        
        # Autoriser les admins et managers automatiquement
        if current_user.role in ['admin', 'super_admin', 'manager']:
            _journal(f"   🔧 Forçage de la permission pour {current_user.role}")
            if current_user.permissions is None:
                current_user.permissions = {}
            current_user.permissions['can_manage_action_plans'] = True
            marquer_json_modifie(current_user, 'permissions')
            current_user.permissions['can_view_action_plans'] = True
            marquer_json_modifie(current_user, 'permissions')
            try:
                db.session.commit()
                flash('🔧 Permissions ajustées automatiquement', 'info')
            except:
                db.session.rollback()
        else:
            flash('Permission "Gérer les plans d\'action" requise', 'error')
            return redirect(url_for('detail_risque', id=risque_id))
    
    # 3. Vérifier l'accès au module plans d'action
    if current_user.role != 'super_admin' and current_user.client and current_user.client.formule:
        formule = current_user.client.formule
        
        # Vérifier l'accès au module plans d'action
        module_names_to_check = ['plans_action', 'audit_interne', 'audit']
        has_access = False
        
        for module_name in module_names_to_check:
            if module_name in formule.modules:
                if formule.modules[module_name]:
                    has_access = True
                    _journal(f"   ✅ Module trouvé: '{module_name}'")
                    break
        
        if not has_access:
            _journal(f"   ❌ Aucun module plans d'action activé")
            flash('Le module "Plans d\'action" n\'est pas inclus dans votre formule', 'error')
            return redirect(url_for('detail_risque', id=risque_id))
    
    # 4. Initialiser le formulaire
    form = SimplePlanActionForm()
    
    # 5. Pré-remplir les choix des utilisateurs
    utilisateurs = get_client_filter(User).filter_by(is_active=True).all()
    form.responsable_id.choices = [(0, 'Non assigné')] + \
        [(u.id, f"{u.username} - {u.role}") for u in utilisateurs]
    
    # 6. Pré-remplir les valeurs par défaut (GET request)
    if request.method == 'GET':
        dispositif_id = request.args.get('dispositif_id')
        
        if dispositif_id:
            form.dispositif_id.data = dispositif_id
            dispositif = DispositifMaitrise.query.get(dispositif_id)
            
            if dispositif and check_client_access(dispositif):
                form.nom.data = f"Amélioration dispositif {dispositif.reference}"
                form.description.data = f"Plan d'action pour améliorer le dispositif de maîtrise {dispositif.reference}: {dispositif.nom}\n\nObjectif: Augmenter l'efficacité du dispositif."
        
        # Pré-remplir l'ID du risque
        form.risque_id.data = risque_id
        
        # Définir les dates par défaut
        aujourdhui = _aujourdhui()
        form.date_debut.data = aujourdhui
        form.date_echeance.data = aujourdhui + timedelta(days=30)  # 30 jours par défaut
    
    # 7. Traiter la soumission du formulaire (POST request)
    if form.validate_on_submit():
        _journal(f"\n✅ FORMULAIRE VALIDÉ")
        _journal(f"   Nom: {form.nom.data}")
        _journal(f"   Risque ID: {form.risque_id.data}")
        _journal(f"   Responsable ID: {form.responsable_id.data}")
        _journal(f"   Date début: {form.date_debut.data}")
        _journal(f"   Date échéance: {form.date_echeance.data}")
        
        # 7.1 Générer une référence automatique
        try:
            dernier_plan = get_client_filter(PlanAction)\
                .filter(PlanAction.reference.like(f'PA-{risque.reference}-%'))\
                .order_by(PlanAction.reference.desc())\
                .first()
            
            if dernier_plan:
                try:
                    num = int(dernier_plan.reference.split('-')[-1]) + 1
                except:
                    num = 1
            else:
                num = 1
        except Exception as e:
            _journal(f"   ⚠️ Erreur génération référence: {e}")
            num = 1
        
        reference = f"PA-{risque.reference}-{num:03d}"
        _journal(f"   📝 Référence générée: {reference}")
        
        # 7.2 Créer le plan d'action - IMPORTANT: audit_id = NULL
        plan_action = PlanAction(
            reference=reference,
            nom=form.nom.data,
            description=form.description.data,
            risque_id=risque_id,  # ✅ Directement lié au risque
            dispositif_id=form.dispositif_id.data if form.dispositif_id.data else None,
            responsable_id=form.responsable_id.data if form.responsable_id.data != 0 else None,
            date_debut=form.date_debut.data,
            date_fin_prevue=form.date_echeance.data,
            date_fin_reelle=None,
            statut='en_cours',
            priorite=form.priorite.data if hasattr(form, 'priorite') else 'moyenne',
            pourcentage_realisation=0,
            created_by=current_user.id,
            client_id=current_user.client_id
            # ✅ audit_id reste NULL - c'est autorisé par votre modèle
        )
        
        _journal(f"   🏗️ Plan d'action créé (sans audit)")
        
        try:
            # 7.3 Sauvegarder le plan d'action
            db.session.add(plan_action)
            db.session.commit()
            _journal(f"   💾 Plan d'action sauvegardé: ID {plan_action.id}")
            
            # 7.4 Lier le dispositif au plan créé (si spécifié)
            dispositif_id = form.dispositif_id.data
            if dispositif_id:
                dispositif = DispositifMaitrise.query.get(dispositif_id)
                if dispositif and check_client_access(dispositif):
                    dispositif.plan_action_id = plan_action.id
                    db.session.commit()
                    _journal(f"   🔗 Dispositif lié: {dispositif.reference}")
            
            # 7.5 Créer une notification pour le responsable
            try:
                if plan_action.responsable_id and plan_action.responsable_id != current_user.id:
                    notification = Notification(
                        type_notification=Notification.TYPE_PLAN,
                        titre=f"Nouveau plan d'action: {plan_action.nom}",
                        message=f"Vous avez été assigné comme responsable du plan d'action '{plan_action.nom}' pour le risque {risque.reference}",
                        destinataire_id=plan_action.responsable_id,
                        entite_type='plan_action',
                        entite_id=plan_action.id,
                        urgence=Notification.URGENCE_NORMAL,
                        client_id=current_user.client_id
                    )
                    db.session.add(notification)
                    db.session.commit()
                    _journal(f"   🔔 Notification créée pour responsable")
            except Exception as e:
                _journal(f"   ⚠️ Erreur création notification: {e}")
            
            # 7.6 Journaliser l'action
            try:
                # Convertir le dictionnaire en JSON
                import json
                details_json = json.dumps({
                    'plan_id': plan_action.id,
                    'plan_nom': plan_action.nom,
                    'risque_id': risque.id,
                    'risque_reference': risque.reference,
                    'dispositif_id': dispositif_id if dispositif_id else None
                }, ensure_ascii=False)
                
                journal = JournalActivite(
                    utilisateur_id=current_user.id,
                    action=f"Création plan d'action risque: {plan_action.reference}",
                    details=details_json,  # Maintenant c'est une chaîne JSON
                    entite_type='plan_action',
                    entite_id=plan_action.id,
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string,
                    client_id=current_user.client_id
                )
                db.session.add(journal)
                db.session.commit()
                _journal(f"   📝 Journal d'activité créé")
            except Exception as e:
                _journal(f"   ⚠️ Erreur journal: {e}")
            
            flash(f'✅ Plan d\'action "{plan_action.nom}" créé avec succès', 'success')
            _journal(f"   🎉 REDIRECTION vers détails du plan")
            
            # 7.7 Rediriger vers le détail du nouveau plan
            return redirect(url_for('detail_plan_action_risque', plan_id=plan_action.id))
            
        except Exception as e:
            db.session.rollback()
            _journal(f"   ❌ ERREUR CRITIQUE lors de la création: {str(e)}")
            _journal(f"   Traceback: {traceback.format_exc()}")
            flash(f'❌ Erreur lors de la création du plan d\'action: {str(e)}', 'error')
    
    # 8. Afficher le formulaire (GET ou formulaire invalide)
    _journal(f"\n📋 AFFICHAGE FORMULAIRE")
    
    return render_template('plans_action/form_simple.html',
                         form=form,
                         risque=risque,
                         action='creer',
                         current_user=current_user)


@app.route('/plan-action-risque/<int:plan_id>')
@login_required
def detail_plan_action_risque(plan_id):
    """Détail d'un plan d'action lié à un risque"""
    plan_action = PlanAction.query.get_or_404(plan_id)
    
    if not check_client_access(plan_action):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('dashboard'))
    
    # Récupérer les sous-actions triées par date de création
    sous_actions = SousAction.query\
        .filter_by(plan_action_id=plan_id)\
        .order_by(SousAction.created_at.asc())\
        .all()
    
    # Récupérer les étapes triées par ordre
    etapes = EtapePlanAction.query\
        .filter_by(plan_action_id=plan_id)\
        .order_by(EtapePlanAction.ordre.asc())\
        .all()
    
    # Calculer l'avancement basé sur les sous-actions
    total_sous_actions = len(sous_actions)
    sous_actions_terminees = sum(1 for s in sous_actions if s.statut == 'termine')
    pourcentage_avancement = (sous_actions_terminees / total_sous_actions * 100) if total_sous_actions > 0 else 0
    
    return render_template('plans_action/detail_risque.html',
                         plan=plan_action,
                         sous_actions=sous_actions,
                         etapes=etapes,
                         pourcentage_avancement=pourcentage_avancement,
                         sous_actions_terminees=sous_actions_terminees,
                         total_sous_actions=total_sous_actions,
                         is_risque_plan=True,
                         datetime=datetime)


@app.route('/plan-action-risque/<int:plan_id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_plan_action_risque(plan_id):
    """Modifier un plan d'action lié à un risque"""
    plan_action = PlanAction.query.get_or_404(plan_id)
    
    if not check_client_access(plan_action):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))
    
    # Vérifier les permissions
    if (not __import__('egalyx.maitrise', fromlist=['droit']).droit()):
        flash('Vous n\'êtes pas autorisé à modifier ce plan d\'action', 'error')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))
    
    form = SimplePlanActionForm(obj=plan_action)
    
    # Pré-remplir les choix
    utilisateurs = get_client_filter(User).filter_by(is_active=True).all()
    form.responsable_id.choices = [(0, 'Non assigné')] + \
        [(u.id, f"{u.username} - {u.role}") for u in utilisateurs]
    
    # Pré-remplir la date d'échéance et l'ID du risque
    if request.method == 'GET':
        form.date_echeance.data = plan_action.date_fin_prevue
        form.priorite.data = getattr(plan_action, 'priorite', 'moyenne')
        form.risque_id.data = plan_action.risque_id
    
    if form.validate_on_submit():
        plan_action.nom = form.nom.data
        plan_action.description = form.description.data
        plan_action.responsable_id = form.responsable_id.data if form.responsable_id.data != 0 else None
        plan_action.date_debut = form.date_debut.data
        plan_action.date_fin_prevue = form.date_echeance.data
        
        # Mettre à jour la priorité si le champ existe
        if hasattr(plan_action, 'priorite'):
            plan_action.priorite = form.priorite.data
        
        plan_action.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Plan d\'action modifié avec succès', 'success')
        # REDIRECTION VERS LE DÉTAIL DU PLAN
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))
    
    return render_template('plans_action/form_simple.html',
                         form=form,
                         risque=plan_action.risque,
                         action='modifier',
                         plan=plan_action)


@app.route('/plan-action-risque/<int:plan_id>/sous-action/nouveau', methods=['GET', 'POST'])
@login_required
def nouveau_sous_action_risque(plan_id):
    """Ajouter une sous-action à un plan d'action risque"""
    plan_action = PlanAction.query.get_or_404(plan_id)
    
    if not check_client_access(plan_action):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))
    
    # Vérifier les permissions
    if (not __import__('egalyx.maitrise', fromlist=['droit']).droit()):
        flash('Vous n\'êtes pas autorisé à ajouter des sous-actions', 'error')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))
    
    # Utilisez le formulaire AVEC commentaire
    form = SousActionForm()
    
    # Pré-remplir les choix
    utilisateurs = get_client_filter(User).filter_by(is_active=True).all()
    form.responsable_id.choices = [(0, 'Non assigné')] + \
        [(u.id, f"{u.username} - {u.role}") for u in utilisateurs]
    
    if request.method == 'GET':
        # Définir les dates par défaut
        form.date_debut.data = _aujourdhui()
        form.date_fin_prevue.data = (datetime.now() + timedelta(days=14)).date()
    
    if form.validate_on_submit():
        # Trouver le prochain ordre
        dernier_sous_action = SousAction.query\
            .filter_by(plan_action_id=plan_id)\
            .order_by(SousAction.created_at.desc())\
            .first()
        
        # Générer une référence
        reference = f"SA-{plan_action.reference}-{(dernier_sous_action.id + 1) if dernier_sous_action else 1:03d}"
        
        # Créer la sous-action - UTILISEZ SEULEMENT LES CHAMPS DISPONIBLES
        sous_action = SousAction(
            plan_action_id=plan_id,
            reference=reference,
            description=form.description.data,
            # Ne pas utiliser form.commentaire.data si le champ n'existe pas
            # commentaire=form.commentaire.data if hasattr(form, 'commentaire') else None,
            date_debut=form.date_debut.data,
            date_fin_prevue=form.date_fin_prevue.data,
            responsable_id=form.responsable_id.data if form.responsable_id.data != 0 else None,
            statut='a_faire',
            pourcentage_realisation=0,
            client_id=current_user.client_id
        )
        
        db.session.add(sous_action)
        db.session.commit()
        
        flash('Sous-action ajoutée avec succès', 'success')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))
    
    return render_template('plans_action/form_sous_action.html',
                         form=form,
                         plan=plan_action,
                         action='creer')


# ============================================================================
# ROUTES POUR LES PLANS D'ACTION RISQUE
# ============================================================================
@app.route('/plan-action-risque/<int:plan_id>/archiver', methods=['POST'])
@login_required
def archiver_plan_risque(plan_id):
    """Archiver un plan d'action risque - VERSION CORRIGÉE"""
    plan_action = PlanAction.query.get_or_404(plan_id)
    
    if not check_client_access(plan_action):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))
    
    # Vérifier les permissions
    if (not __import__('egalyx.maitrise', fromlist=['droit']).droit()):
        flash('Vous n\'êtes pas autorisé à archiver ce plan', 'error')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))
    
    try:
        # Vérifier si déjà archivé
        if plan_action.is_archived:
            flash('Ce plan est déjà archivé', 'warning')
            return redirect(url_for('voir_plans_action_risque', 
                                  risque_id=plan_action.risque_id,
                                  archives='oui'))
        
        _journal(f"🔍 DEBUG - Archivage plan {plan_id}")
        _journal(f"🔍 DEBUG - AVANT: is_archived={plan_action.is_archived}, statut_archive={plan_action.statut_archive}")
        
        # Archiver le plan
        plan_action.archiver(current_user.id, "Archivé manuellement")
        
        _journal(f"🔍 DEBUG - APRÈS: is_archived={plan_action.is_archived}, statut_archive={plan_action.statut_archive}")
        
        # Journalisation (facultatif)
        try:
            from models import JournalActivite
            journal = JournalActivite(
                utilisateur_id=current_user.id,
                action='archivage_plan',
                details=json.dumps({
                    'plan_id': plan_id,
                    'plan_reference': plan_action.reference
                }),
                entite_type='plan_action',
                entite_id=plan_id,
                client_id=current_user.client_id
            )
            db.session.add(journal)
        except Exception as e:
            _journal(f"⚠️ Erreur journalisation: {e}")
        
        db.session.commit()
        _journal(f"✅ Plan {plan_id} archivé avec succès")
        
        flash(f'Plan "{plan_action.reference}" archivé avec succès', 'success')
        
        # Vérifier la requête AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': 'Plan archivé avec succès',
                'redirect': url_for('voir_plans_action_risque', 
                                  risque_id=plan_action.risque_id)
            })
        
        # Redirection normale
        return redirect(url_for('voir_plans_action_risque', 
                              risque_id=plan_action.risque_id))
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur archivage: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Erreur lors de l\'archivage: {str(e)}', 'error')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))


@app.route('/plan-action-risque/<int:plan_id>/desarchiver', methods=['POST'])
@login_required
def desarchiver_plan_risque(plan_id):
    """Désarchiver un plan d'action risque - VERSION CORRIGÉE"""
    plan_action = PlanAction.query.get_or_404(plan_id)
    
    if not check_client_access(plan_action):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))
    
    # Vérifier les permissions
    if (not __import__('egalyx.maitrise', fromlist=['droit']).droit()):
        flash('Vous n\'êtes pas autorisé à désarchiver ce plan', 'error')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))
    
    try:
        # Vérifier si déjà désarchivé
        if not plan_action.is_archived:
            flash('Ce plan n\'est pas archivé', 'warning')
            return redirect(url_for('voir_plans_action_risque', 
                                  risque_id=plan_action.risque_id))
        
        _journal(f"🔍 DEBUG - Désarchivage plan {plan_id}")
        _journal(f"🔍 DEBUG - AVANT: is_archived={plan_action.is_archived}, statut_archive={plan_action.statut_archive}")
        
        # Désarchiver le plan
        plan_action.desarchiver()
        
        _journal(f"🔍 DEBUG - APRÈS: is_archived={plan_action.is_archived}, statut_archive={plan_action.statut_archive}")
        
        # Journalisation (facultatif)
        try:
            from models import JournalActivite
            journal = JournalActivite(
                utilisateur_id=current_user.id,
                action='desarchivage_plan',
                details=json.dumps({
                    'plan_id': plan_id,
                    'plan_reference': plan_action.reference
                }),
                entite_type='plan_action',
                entite_id=plan_id,
                client_id=current_user.client_id
            )
            db.session.add(journal)
        except Exception as e:
            _journal(f"⚠️ Erreur journalisation: {e}")
        
        db.session.commit()
        _journal(f"✅ Plan {plan_id} désarchivé avec succès")
        
        flash(f'Plan "{plan_action.reference}" désarchivé avec succès', 'success')
        
        # Vérifier la requête AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': 'Plan désarchivé avec succès',
                'redirect': url_for('voir_plans_action_risque', 
                                  risque_id=plan_action.risque_id)
            })
        
        # Redirection normale - retourner aux archives pour voir le changement
        return redirect(url_for('voir_plans_action_risque', 
                              risque_id=plan_action.risque_id,
                              archives='oui'))
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur désarchivage: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Erreur lors du désarchivage: {str(e)}', 'error')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))


@app.route('/plan-action-risque/<int:plan_id>/supprimer', methods=['DELETE'])
@login_required
def supprimer_plan_risque(plan_id):
    """Supprimer définitivement un plan d'action risque"""
    plan_action = PlanAction.query.get_or_404(plan_id)
    
    if not check_client_access(plan_action):
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    # Vérifier les permissions
    if current_user.role != 'admin' and current_user.id != plan_action.created_by:
        return jsonify({'error': 'Vous n\'êtes pas autorisé à supprimer ce plan'}), 403
    
    try:
        # Supprimer d'abord les sous-actions
        SousAction.query.filter_by(plan_action_id=plan_id).delete()
        
        # Supprimer le plan
        db.session.delete(plan_action)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Plan supprimé avec succès',
            'redirect': url_for('voir_plans_action_risque', risque_id=plan_action.risque_id)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/risque/<int:risque_id>/plans-action/liste')
@login_required
def voir_plans_action_risque(risque_id):
    """Voir tous les plans d'action d'un risque - VERSION CORRIGÉE"""
    risque = Risque.query.get_or_404(risque_id)
    
    if not check_client_access(risque):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('detail_risque', id=risque_id))
    
    # Vérifier si on veut voir les archives ou non
    voir_archives = request.args.get('archives', 'non') == 'oui'
    
    # Construire la requête
    query = get_client_filter(PlanAction)\
        .filter_by(risque_id=risque_id)
    
    # Filtrer selon statut_archive
    if voir_archives:
        plans_action = query.filter(PlanAction.statut_archive == 'archive')\
                           .order_by(PlanAction.updated_at.desc())\
                           .all()
    else:
        plans_action = query.filter(PlanAction.statut_archive == 'actif')\
                           .order_by(PlanAction.created_at.desc())\
                           .all()
    
    # Préparer les données pour le template
    plans_with_attrs = []
    for plan in plans_action:
        # Assurez-vous que statut_archive existe
        statut_archive_value = getattr(plan, 'statut_archive', 'actif')
        plans_with_attrs.append({
            'plan': plan,
            'statut_archive': statut_archive_value,
            'has_statut_archive': hasattr(plan, 'statut_archive')
        })
    
    # Récupérer TOUS les plans pour calculer les statistiques
    tous_plans = get_client_filter(PlanAction)\
        .filter_by(risque_id=risque_id)\
        .all()
    
    # Calcul des statistiques
    plans_actifs = [p for p in tous_plans if getattr(p, 'statut_archive', 'actif') == 'actif']
    plans_archives = [p for p in tous_plans if getattr(p, 'statut_archive', 'actif') == 'archive']
    
    stats = {
        'total': len(plans_actifs),
        'en_cours': len([p for p in plans_actifs if p.statut == 'en_cours']),
        'termines': len([p for p in plans_actifs if p.statut == 'termine']),
        'en_retard': len([p for p in plans_actifs if getattr(p, 'est_en_retard', False)]),
        'archives': len(plans_archives)
    }
    
    # Récupérer les responsables uniques
    responsables_uniques = []
    for plan in plans_action:
        if plan.responsable and plan.responsable not in responsables_uniques:
            responsables_uniques.append(plan.responsable)
    
    # Convertir en JSON pour les graphiques
    plans_action_json = [plan.to_dict() for plan in plans_action]
    
    return render_template('plans_action/liste_risque.html',
                         risque=risque,
                         plans_with_attrs=plans_with_attrs,  # Changé ici
                         plans_action=plans_action,  # Garder pour compatibilité
                         plans_action_json=plans_action_json,
                         stats=stats,
                         responsables_uniques=responsables_uniques,
                         voir_archives=voir_archives)


@app.route('/api/cartographie/<int:cartographie_id>/couverture')
@login_required
def api_couverture_cartographie(cartographie_id):
    """API: Analyse de couverture d'une cartographie"""
    try:
        cartographie = Cartographie.query.get_or_404(cartographie_id)
        
        if not check_client_access(cartographie):
            return jsonify({'error': 'Accès non autorisé'}), 403
        
        from services.dispositif_service import DispositifService
        rapport = DispositifService.generer_rapport_couverture(cartographie_id)
        
        return jsonify({
            'success': True,
            'rapport': rapport
        })
        
    except Exception as e:
        _journal(f"❌ Erreur API couverture: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/plan-action-risque/<int:plan_id>/progression-detail')
@login_required
def progression_detail_plan_risque(plan_id):
    """API: Détail de la progression d'un plan"""
    plan_action = PlanAction.query.get_or_404(plan_id)
    
    if not check_client_access(plan_action):
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    # CORRECTION : Utilisez get_progression_detaillee() si c'est le bon nom
    # OU créez une méthode qui calcule les détails
    try:
        if hasattr(plan_action, 'get_progression_detaillee'):
            details = plan_action.get_progression_detaillee()
        else:
            # Calcul manuel des détails
            sous_actions = plan_action.sous_actions
            total = len(sous_actions)
            terminees = len([sa for sa in sous_actions if sa.statut == 'termine'])
            en_cours = len([sa for sa in sous_actions if sa.statut == 'en_cours'])
            a_faire = len([sa for sa in sous_actions if sa.statut == 'a_faire'])
            retardees = len([sa for sa in sous_actions if sa.est_en_retard])
            
            details = {
                'total': total,
                'terminees': terminees,
                'en_cours': en_cours,
                'a_faire': a_faire,
                'retardees': retardees,
                'progression': plan_action.pourcentage_realisation,
                'sous_actions': [
                    {
                        'id': sa.id,
                        'reference': sa.reference,
                        'description': sa.description,
                        'statut': sa.statut,
                        'progression': sa.pourcentage_realisation
                    }
                    for sa in sous_actions
                ]
            }
    except Exception as e:
        details = {
            'total': 0,
            'terminees': 0,
            'en_cours': 0,
            'a_faire': 0,
            'retardees': 0,
            'progression': 0,
            'sous_actions': [],
            'error': str(e)
        }
    
    return jsonify({
        'success': True,
        'details': details,
        'plan': {
            'reference': plan_action.reference,
            'nom': plan_action.nom,
            'statut': plan_action.statut,
            'progression': plan_action.pourcentage_realisation
        }
    })


@app.route('/plan-action-risque/<int:plan_id>/changer-statut-rapide', methods=['POST'])
@login_required
def changer_statut_plan_risque_rapide(plan_id):
    """Changer rapidement le statut d'un plan d'action"""
    plan_action = PlanAction.query.get_or_404(plan_id)
    
    if not check_client_access(plan_action):
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    data = request.get_json()
    nouveau_statut = data.get('statut')
    ancien_statut = data.get('ancien_statut', plan_action.statut)
    
    if not nouveau_statut:
        return jsonify({'error': 'Statut manquant'}), 400
    
    # Valider le statut
    statuts_valides = ['en_attente', 'en_cours', 'termine', 'suspendu', 'annule']
    if nouveau_statut not in statuts_valides:
        return jsonify({'error': 'Statut invalide'}), 400
    
    # Enregistrer l'ancien statut
    ancien_statut_plan = plan_action.statut
    
    # Changer le statut
    plan_action.statut = nouveau_statut
    plan_action.updated_at = datetime.utcnow()
    
    # Journalisation CORRIGÉE - convertir dict en string JSON
    try:
        from models import JournalActivite
        journal = JournalActivite(
            utilisateur_id=current_user.id,
            action='changement_statut_plan',
            details=json.dumps({  # CONVERTIR EN STRING JSON
                'plan_id': plan_id,
                'plan_reference': plan_action.reference,
                'ancien_statut': ancien_statut_plan,
                'nouveau_statut': nouveau_statut
            }),
            entite_type='plan_action',
            entite_id=plan_id,
            client_id=current_user.client_id
        )
        db.session.add(journal)
    except Exception as e:
        _journal(f"⚠️ Erreur journalisation: {e}")
        # Ne pas bloquer si le journal échoue
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Statut changé de {ancien_statut_plan} à {nouveau_statut}',
        'nouveau_statut': nouveau_statut
    })


@app.route('/plan-action-risque/<int:plan_id>/changer-statut', methods=['POST'])
@login_required
def changer_statut_plan_risque(plan_id):
    """Changer le statut d'un plan d'action risque - VERSION CORRIGÉE"""
    plan_action = PlanAction.query.get_or_404(plan_id)
    
    if not check_client_access(plan_action):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))
    
    # Vérifier les permissions
    if (not __import__('egalyx.maitrise', fromlist=['droit']).droit()):
        flash('Vous n\'êtes pas autorisé à modifier ce plan', 'error')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))
    
    # Récupérer les données du formulaire
    nouveau_statut = request.form.get('statut')
    commentaire = request.form.get('commentaire', '')
    
    if nouveau_statut not in ['en_attente', 'en_cours', 'termine', 'suspendu', 'annule']:
        flash('Statut invalide', 'error')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))
    
    try:
        ancien_statut = plan_action.statut
        plan_action.statut = nouveau_statut
        plan_action.updated_at = datetime.utcnow()
        
        # ============================================================
        # CALCUL AUTOMATIQUE DE LA PROGRESSION BASÉE SUR LE STATUT
        # ============================================================
        if nouveau_statut == 'termine':
            # Si le plan est marqué comme terminé
            plan_action.date_fin_reelle = _aujourdhui()
            plan_action.pourcentage_realisation = 100
            
            # Marquer TOUTES les sous-actions comme terminées à 100%
            for sous_action in plan_action.sous_actions:
                sous_action.statut = 'termine'
                sous_action.pourcentage_realisation = 100
                if not sous_action.date_fin_reelle:
                    sous_action.date_fin_reelle = _aujourdhui()
                sous_action.updated_at = datetime.utcnow()
                
        elif nouveau_statut == 'en_cours':
            # Si le plan passe en cours
            if plan_action.pourcentage_realisation == 0:
                plan_action.pourcentage_realisation = 10  # Valeur initiale
            
            # Marquer les sous-actions sans statut comme "en_cours"
            for sous_action in plan_action.sous_actions:
                if sous_action.statut == 'a_faire' or sous_action.statut is None:
                    sous_action.statut = 'en_cours'
                    if sous_action.pourcentage_realisation == 0:
                        sous_action.pourcentage_realisation = 50  # Valeur moyenne
                    sous_action.updated_at = datetime.utcnow()
                    
        elif nouveau_statut == 'en_attente':
            # Si le plan revient en attente
            plan_action.pourcentage_realisation = 0
            plan_action.date_fin_reelle = None
            
            # Remettre toutes les sous-actions en attente
            for sous_action in plan_action.sous_actions:
                sous_action.statut = 'a_faire'
                sous_action.pourcentage_realisation = 0
                sous_action.date_fin_reelle = None
                sous_action.updated_at = datetime.utcnow()
                
        elif nouveau_statut == 'suspendu':
            # Suspendu : progression inchangée, seulement le statut change
            # Ne pas toucher à la progression
            pass
            
        elif nouveau_statut == 'annule':
            # Si le plan est annulé
            plan_action.pourcentage_realisation = 0
            
            # Annuler toutes les sous-actions
            for sous_action in plan_action.sous_actions:
                sous_action.statut = 'annule'
                sous_action.pourcentage_realisation = 0
                sous_action.updated_at = datetime.utcnow()
        # ============================================================
        
        # Calculer la progression réelle (basée sur les sous-actions)
        # Cette méthode devrait mettre à jour plan_action.pourcentage_realisation
        plan_action.progression_reelle
        
        # Enregistrer un historique si nécessaire
        if commentaire:
            # Vous pourriez stocker ce commentaire dans un champ dédié
            # ou créer une table d'historique
            pass
        
        db.session.commit()
        
        flash(f'Statut changé de "{ancien_statut}" à "{nouveau_statut}". Progression: {plan_action.pourcentage_realisation}%', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
    
    return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))


@app.route('/plan-action-risque/<int:plan_id>/changer-progression', methods=['POST'])
@login_required
def changer_progression_plan(plan_id):
    """Changer manuellement la progression d'un plan (0, 25, 50, 75, 100%) - VERSION MULTI-TENANT"""
    plan = PlanAction.query.get_or_404(plan_id)
    
    # VÉRIFICATION MULTI-TENANT
    if not check_client_access(plan):
        return jsonify({'success': False, 'error': 'Accès non autorisé'}), 403
    
    data = request.get_json()
    progression = data.get('progression')
    
    # Accepter seulement les valeurs fixes
    if progression not in [0, 25, 50, 75, 100]:
        return jsonify({'success': False, 'error': 'Progression invalide. Valeurs acceptées: 0, 25, 50, 75, 100%'}), 400
    
    # Vérifier les permissions
    if not (current_user.is_client_admin or 
            current_user.id == plan.created_by or 
            current_user.id == plan.responsable_id or
            __import__('egalyx.maitrise', fromlist=['droit']).droit()):
        return jsonify({'success': False, 'error': 'Permission insuffisante'}), 403
    
    try:
        ancienne_progression = plan.pourcentage_realisation
        plan.pourcentage_realisation = progression
        plan.updated_at = datetime.utcnow()
        
        # Ajuster automatiquement le statut basé sur la progression
        if progression == 100:
            plan.statut = 'termine'
            plan.date_fin_reelle = _aujourdhui()
        elif progression >= 50 and plan.statut == 'en_attente':
            plan.statut = 'en_cours'
        elif progression == 0 and plan.statut != 'en_attente':
            plan.statut = 'en_attente'
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Progression changée de {ancienne_progression}% à {progression}%',
            'progression': progression,
            'statut': plan.statut
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/plan-action-risque/<int:plan_id>/changer-responsable-rapide', methods=['POST'])
@login_required
def changer_responsable_plan_rapide(plan_id):
    """Changer le responsable d'un plan d'action rapidement"""
    plan = PlanAction.query.get_or_404(plan_id)
    
    if not check_client_access(plan):
        return jsonify({'success': False, 'error': 'Accès non autorisé'}), 403
    
    if not current_user.can_edit_plan(plan):
        return jsonify({'success': False, 'error': 'Permission insuffisante'}), 403
    
    data = request.get_json()
    responsable_id = data.get('responsable_id')
    
    # Vérifier que le responsable existe dans le même client
    responsable = User.query.filter_by(id=responsable_id, client_id=current_user.client_id).first()
    if not responsable:
        return jsonify({'success': False, 'error': 'Responsable non trouvé'}), 404
    
    ancien_responsable = plan.responsable_id
    plan.responsable_id = responsable_id
    plan.updated_at = datetime.utcnow()
    
    # Journaliser le changement
    journal = JournalActivite(
        utilisateur_id=current_user.id,
        action='changement_responsable_plan',
        details={
            'plan_id': plan.id,
            'plan_reference': plan.reference,
            'ancien_responsable': ancien_responsable,
            'nouveau_responsable': responsable_id
        },
        entite_type='plan_action',
        entite_id=plan.id,
        client_id=current_user.client_id
    )
    
    try:
        db.session.add(journal)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Responsable mis à jour'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/sous-action-risque/<int:sous_action_id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_sous_action_risque(sous_action_id):
    """Modifier une sous-action d'un plan risque"""
    sous_action = SousAction.query.get_or_404(sous_action_id)
    plan_action = sous_action.plan_action
    
    if not check_client_access(plan_action):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_action.id))
    
    # Vérifier les permissions
    if (current_user.id != plan_action.created_by and 
        current_user.id != sous_action.responsable_id and
        not __import__('egalyx.maitrise', fromlist=['droit']).droit()):
        flash('Vous n\'êtes pas autorisé à modifier cette sous-action', 'error')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_action.id))
    
    form = SousActionForm(obj=sous_action)
    
    # Pré-remplir les choix
    utilisateurs = get_client_filter(User).filter_by(is_active=True).all()
    form.responsable_id.choices = [(0, 'Non assigné')] + \
        [(u.id, f"{u.username} - {u.role}") for u in utilisateurs]
    
    if form.validate_on_submit():
        sous_action.description = form.description.data
        sous_action.date_debut = form.date_debut.data
        sous_action.date_fin_prevue = form.date_fin_prevue.data
        sous_action.responsable_id = form.responsable_id.data if form.responsable_id.data != 0 else None
        
        # Si le formulaire a un champ commentaire
        if hasattr(form, 'commentaire') and hasattr(sous_action, 'commentaire'):
            sous_action.commentaire = form.commentaire.data
            
        sous_action.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Sous-action modifiée avec succès', 'success')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_action.id))
    
    return render_template('plans_action/form_sous_action.html',
                         form=form,
                         plan=plan_action,
                         action='modifier',
                         sous_action=sous_action)


@app.route('/plan-action-risque/<int:plan_id>/terminer', methods=['POST'])
@login_required
def terminer_plan_complet_risque(plan_id):
    """Terminer complètement un plan d'action (toutes les sous-actions)"""
    plan_action = PlanAction.query.get_or_404(plan_id)
    
    if not check_client_access(plan_action):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))
    
    # Vérifier les permissions
    if (not __import__('egalyx.maitrise', fromlist=['droit']).droit()):
        flash('Vous n\'êtes pas autorisé à terminer ce plan', 'error')
        return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))
    
    try:
        # Marquer le plan comme terminé
        plan_action.statut = 'termine'
        plan_action.date_fin_reelle = _aujourdhui()
        plan_action.pourcentage_realisation = 100
        
        # Marquer toutes les sous-actions comme terminées
        sous_actions = SousAction.query.filter_by(plan_action_id=plan_id).all()
        for sous_action in sous_actions:
            sous_action.statut = 'termine'
            sous_action.pourcentage_realisation = 100
            if not sous_action.date_fin_reelle:
                sous_action.date_fin_reelle = _aujourdhui()
        
        plan_action.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash('Plan d\'action terminé avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
    
    return redirect(url_for('detail_plan_action_risque', plan_id=plan_id))


@app.route('/sous-action-risque/<int:sous_action_id>/terminer', methods=['POST'])
@login_required
def terminer_sous_action_risque(sous_action_id):
    """Terminer une sous-action d'un plan risque"""
    sous_action = SousAction.query.get_or_404(sous_action_id)
    
    if not check_client_access(sous_action):
        return jsonify({'success': False, 'error': 'Accès non autorisé'}), 403
    
    try:
        from datetime import timezone
        
        # Marquer comme terminé
        sous_action.statut = 'termine'
        sous_action.pourcentage_realisation = 100
        sous_action.date_fin_reelle = datetime.now(timezone.utc).date()
        sous_action.updated_at = datetime.now(timezone.utc)
        
        # Recalculer la progression du plan
        if sous_action.plan_action:
            sous_action.plan_action.progression_reelle
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Sous-action terminée avec succès'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/sous-action-risque/<int:sous_action_id>/supprimer', methods=['DELETE', 'POST'])
@login_required
def supprimer_sous_action_risque(sous_action_id):
    """Supprimer une sous-action d'un plan risque"""
    sous_action = SousAction.query.get_or_404(sous_action_id)
    plan_action = sous_action.plan_action
    
    if not check_client_access(sous_action):
        return jsonify({'success': False, 'error': 'Accès non autorisé'}), 403
    
    # Vérifier les permissions
    if (not __import__('egalyx.maitrise', fromlist=['droit']).droit()):
        return jsonify({'success': False, 'error': 'Permission insuffisante'}), 403
    
    try:
        # Sauvegarder l'ID du plan pour la redirection
        plan_id = plan_action.id
        
        # Supprimer les commentaires associés
        CommentairePlanAction.query.filter_by(sous_action_id=sous_action_id).delete()
        
        # Supprimer les fichiers associés
        fichiers = FichierPlanAction.query.filter_by(sous_action_id=sous_action_id).all()
        for fichier in fichiers:
            # Supprimer le fichier physique
            import os
            if os.path.exists(fichier.chemin):
                os.remove(fichier.chemin)
            db.session.delete(fichier)
        
        # Supprimer la sous-action
        db.session.delete(sous_action)
        db.session.commit()
        
        # Recalculer la progression du plan
        if plan_action:
            plan_action.progression_reelle
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Sous-action supprimée avec succès',
            'plan_id': plan_id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/plan-action-risque/<int:plan_id>/reorganiser-sous-actions', methods=['POST'])
@login_required
def reorganiser_sous_actions_risque(plan_id):
    """Réorganiser l'ordre des sous-actions"""
    plan_action = PlanAction.query.get_or_404(plan_id)
    
    if not check_client_access(plan_action):
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    data = request.get_json()
    ids = data.get('ids', [])
    
    try:
        # Mettre à jour l'ordre (vous pourriez avoir un champ 'ordre' dans SousAction)
        for index, sous_action_id in enumerate(ids, 1):
            sous_action = SousAction.query.get(sous_action_id)
            if sous_action and sous_action.plan_action_id == plan_id:
                # Si vous avez un champ 'ordre' dans le modèle
                if hasattr(sous_action, 'ordre'):
                    sous_action.ordre = index
                sous_action.updated_at = datetime.utcnow()
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# ROUTES POUR LES SOUS-ACTIONS (AJAX)
# ============================================================================
@app.route('/sous-action-risque/<int:sous_action_id>/changer-statut', methods=['POST'])
@login_required
def changer_statut_sous_action(sous_action_id):
    """Changer le statut d'une sous-action"""
    sous_action = SousAction.query.get_or_404(sous_action_id)
    plan = sous_action.plan_action
    
    if not check_client_access(plan):
        return jsonify({'success': False, 'error': 'Accès non autorisé'}), 403
    
    data = request.get_json()
    nouveau_statut = data.get('statut')
    progression = data.get('progression')
    
    if nouveau_statut not in ['a_faire', 'en_cours', 'termine', 'retarde']:
        return jsonify({'success': False, 'error': 'Statut invalide'}), 400
    
    try:
        ancien_statut = sous_action.statut
        sous_action.statut = nouveau_statut
        
        if progression is not None:
            sous_action.pourcentage_realisation = progression
        
        # Ajuster automatiquement la progression basée sur le statut
        if nouveau_statut == 'termine' and sous_action.pourcentage_realisation < 100:
            sous_action.pourcentage_realisation = 100
            sous_action.date_fin_reelle = _aujourdhui()
        elif nouveau_statut == 'en_cours' and sous_action.pourcentage_realisation < 50:
            sous_action.pourcentage_realisation = 50
        elif nouveau_statut == 'a_faire' and sous_action.pourcentage_realisation > 0:
            sous_action.pourcentage_realisation = 25
        
        sous_action.updated_at = datetime.utcnow()
        
        # Recalculer la progression du plan
        plan.progression_reelle
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Statut changé à {nouveau_statut}',
            'progression': sous_action.pourcentage_realisation,
            'statut': sous_action.statut,
            'couleur': 'success' if sous_action.pourcentage_realisation >= 100 else 
                      'warning' if sous_action.pourcentage_realisation >= 50 else 'danger',
            'plan_progression': plan.pourcentage_realisation
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/sous-action-risque/<int:sous_action_id>/changer-progression', methods=['POST'])
@login_required
def changer_progression_sous_action(sous_action_id):
    """Changer la progression d'une sous-action (0, 25, 50, 75, 100)"""
    sous_action = SousAction.query.get_or_404(sous_action_id)
    plan = sous_action.plan_action
    
    if not check_client_access(plan):
        return jsonify({'success': False, 'error': 'Accès non autorisé'}), 403
    
    data = request.get_json()
    progression = data.get('progression')
    
    # Accepter seulement les valeurs fixes
    if progression not in [0, 25, 50, 75, 100]:
        return jsonify({'success': False, 'error': 'Progression invalide. Valeurs: 0, 25, 50, 75, 100%'}), 400
    
    try:
        ancienne_progression = sous_action.pourcentage_realisation
        sous_action.pourcentage_realisation = progression
        
        # Ajuster automatiquement le statut basé sur la progression
        if progression == 100:
            sous_action.statut = 'termine'
            sous_action.date_fin_reelle = _aujourdhui()
        elif progression >= 50 and sous_action.statut == 'a_faire':
            sous_action.statut = 'en_cours'
        elif progression < 50 and sous_action.statut == 'termine':
            sous_action.statut = 'a_faire'
        
        sous_action.updated_at = datetime.utcnow()
        
        # Recalculer la progression du plan
        plan.progression_reelle
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Progression changée de {ancienne_progression}% à {progression}%',
            'progression': progression,
            'statut': sous_action.statut,
            'plan_progression': plan.pourcentage_realisation
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/cartographie/nouvelle', methods=['GET', 'POST'])
@login_required
def nouvelle_cartographie():
    """Créer une nouvelle cartographie - VERSION AVEC PAYS"""
    form = CartographieForm()
    
    # ==================== CHARGEMENT DES DONNÉES ====================
    
    # 🔥 CHARGER LES PAYS
    pays_list = get_client_filter(Pays).filter_by(is_archived=False)\
        .order_by(Pays.ordre, Pays.nom).all()
    
    pays_choices = [(0, '--- Aucun pays ---')] + [
        (p.id, f"{p.drapeau or '🌍'} {p.nom} ({p.code})" if p.code else p.nom)
        for p in pays_list
    ]
    form.pays_id.choices = pays_choices
    
    # Charger les pôles
    poles = get_client_filter(Pole).filter_by(is_archived=False)\
        .order_by(Pole.ordre).all()
    poles_choices = [(0, '--- Aucun pôle ---')] + [(p.id, p.nom) for p in poles]
    form.pole_id.choices = poles_choices
    
    # Charger les directions
    directions = get_client_filter(Direction)\
        .filter_by(is_archived=False, is_active=True).all()
    directions_choices = [(0, '--- Sélectionner une direction ---')]
    for d in directions:
        label = d.nom
        if d.pole:
            label += f" ({d.pole.nom})"
        directions_choices.append((d.id, label))
    form.direction_id.choices = directions_choices
    
    form.service_id.choices = [(0, '--- Sélectionnez d\'abord une direction ---')]
    
    # Dictionnaires pour le JS
    direction_poles = {d.id: d.pole_id for d in directions if d.pole_id}
    
    # 🔥 AJOUT : Mapping pôle -> pays pour filtrage JS
    pole_pays = {p.id: p.pays_id for p in poles if p.pays_id}
    
    if form.validate_on_submit():
        type_cartographie = request.form.get('type_cartographie', 'direction')
        
        # 🔥 RÉCUPÉRATION DU PAYS
        pays_id = form.pays_id.data if form.pays_id.data and form.pays_id.data != 0 else None
        pole_id = form.pole_id.data if form.pole_id.data and form.pole_id.data != 0 else None
        direction_id = form.direction_id.data if form.direction_id.data and form.direction_id.data != 0 else None
        service_id = form.service_id.data if type_cartographie == 'service' and form.service_id.data and form.service_id.data != 0 else None
        
        # ==================== VALIDATIONS ====================
        
        # Validation pays
        if pays_id:
            pays = Pays.query.get(pays_id)
            if pays and not check_client_access(pays):
                flash('Accès non autorisé à ce pays', 'error')
                return redirect(url_for('liste_cartographies'))
        
        # Validation pôle
        if pole_id:
            pole = Pole.query.get(pole_id)
            if pole and not check_client_access(pole):
                flash('Accès non autorisé à ce pôle', 'error')
                return redirect(url_for('liste_cartographies'))
            
            # 🔥 Vérifier cohérence pays ↔ pôle
            if pays_id and pole and pole.pays_id and pole.pays_id != pays_id:
                flash('Le pôle sélectionné n\'appartient pas au pays choisi', 'error')
                return render_template('cartographie/form.html', 
                                     form=form, poles=poles, directions=directions,
                                     pays_list=pays_list,
                                     direction_poles=direction_poles,
                                     pole_pays=pole_pays,
                                     action='creation')
        
        # Validation direction
        if direction_id:
            direction = Direction.query.get(direction_id)
            if direction and not check_client_access(direction):
                flash('Accès non autorisé à cette direction', 'error')
                return redirect(url_for('liste_cartographies'))
            
            if pole_id and direction and direction.pole_id != pole_id:
                flash('La direction sélectionnée n\'appartient pas au pôle choisi', 'error')
                return render_template('cartographie/form.html', 
                                     form=form, poles=poles, directions=directions,
                                     pays_list=pays_list,
                                     direction_poles=direction_poles,
                                     pole_pays=pole_pays,
                                     action='creation')
        
        # Validation service
        if service_id:
            service = Service.query.get(service_id)
            if service and not check_client_access(service):
                flash('Accès non autorisé à ce service', 'error')
                return redirect(url_for('liste_cartographies'))
            
            if direction_id and service and service.direction_id != direction_id:
                flash('Le service sélectionné n\'appartient pas à la direction choisie', 'error')
                return render_template('cartographie/form.html', 
                                     form=form, poles=poles, directions=directions,
                                     pays_list=pays_list,
                                     direction_poles=direction_poles,
                                     pole_pays=pole_pays,
                                     action='creation')
        
        # ==================== CRÉATION ====================
        cartographie = Cartographie(
            nom=form.nom.data,
            description=form.description.data,
            pays_id=pays_id,           # 🔥 AJOUT
            pole_id=pole_id,
            direction_id=direction_id,
            service_id=service_id,
            type_cartographie=type_cartographie,
            created_by=current_user.id,
            client_id=current_user.client_id
        )
        
        db.session.add(cartographie)
        db.session.flush()
        
        # Notification avec hiérarchie complète
        try:
            from services.notification_service import NotificationService
            from models import Notification
            
            hierarchie = []
            if pays_id:
                hierarchie.append(pays.nom)
            if pole_id and pole:
                hierarchie.append(pole.nom)
            if direction_id and direction:
                hierarchie.append(direction.nom)
            if service_id and service:
                hierarchie.append(service.nom)
            
            message = f"La cartographie '{cartographie.nom}' a été créée"
            if hierarchie:
                message += f" dans {' > '.join(hierarchie)}"
            
            NotificationService.create(
                destinataire_id=current_user.id,
                type_notif=Notification.TYPE_SUCCESS,
                titre=f"Nouvelle cartographie: {cartographie.nom}",
                message=message,
                entite_type='cartographie',
                entite_id=cartographie.id,
                user_id=current_user.id
            )
        except ImportError:
            from models import Notification
            notif = Notification(
                type_notification='success',
                titre=f"Cartographie créée",
                message=f"La cartographie '{cartographie.nom}' a été créée",
                destinataire_id=current_user.id,
                entite_type='cartographie',
                entite_id=cartographie.id
            )
            db.session.add(notif)
        
        db.session.commit()
        
        flash(f'✅ Cartographie "{cartographie.nom}" créée avec succès', 'success')
        return redirect(url_for('liste_cartographies'))
    
    return render_template('cartographie/form.html', 
                         form=form, 
                         poles=poles, 
                         directions=directions,
                         pays_list=pays_list,          # 🔥 AJOUT
                         direction_poles=direction_poles,
                         pole_pays=pole_pays,          # 🔥 AJOUT
                         action='creation')


# app.py - detail_cartographie (CORRIGÉ)
@app.route('/cartographie/<int:id>')
@login_required
def detail_cartographie(id):
    """
    Détail d'une cartographie avec intégration complète :
    - Évaluations triphase ISO 31000 (brut/net/DMR)
    - Dispositifs de maîtrise
    - 4 matrices (classique / criticité / priorisation / surbrillance)
    - Tableau de Bordeaux basé sur le NET
    - Détection d'anomalies
    """
    from models import DemandeReevaluation, Constatation, DispositifMaitrise
    from utils import (
        calculer_maitrise_depuis_dmr,
        calculer_scores_risque,
        generer_matrice_risques,
        generer_matrice_risque_specifique,
        detecter_anomalies_risque,
    )

    # ============================================
    # 1. RÉCUPÉRATION + SÉCURITÉ
    # ============================================
    cartographie = Cartographie.query.get_or_404(id)

    if not check_client_access(cartographie):
        flash('Accès non autorisé à cette cartographie', 'error')
        return redirect(url_for('liste_cartographies'))

    _journal(f"\n🔍 Chargement cartographie: {cartographie.nom} (ID: {id})")

    # ============================================
    # 2. GESTION CAMPAGNE ACTIVE
    # ============================================
    campagne_active = get_client_filter(CampagneEvaluation)\
        .filter_by(cartographie_id=id, statut='en_cours').first()

    if not campagne_active:
        annee_courante = datetime.now().year
        campagne_active = CampagneEvaluation(
            cartographie_id=id,
            nom=f"Campagne {annee_courante}",
            description=f"Évaluation annuelle {annee_courante}",
            date_debut=_aujourdhui(),
            statut='en_cours',
            created_by=current_user.id
        )

        if current_user.role != 'super_admin' and hasattr(current_user, 'client_id'):
            campagne_active.client_id = current_user.client_id
        elif current_user.role == 'super_admin':
            campagne_active.client_id = cartographie.client_id

        db.session.add(campagne_active)
        db.session.commit()
        _journal(f"✅ Campagne par défaut créée: {campagne_active.nom}")

    # ============================================
    # 3. CAMPAGNES POUR SÉLECTEUR
    # ============================================
    campagnes = get_client_filter(CampagneEvaluation)\
        .filter_by(cartographie_id=id)\
        .order_by(CampagneEvaluation.created_at.desc()).all()

    # ============================================
    # 4. RISQUES + ÉVALUATIONS + DISPOSITIFS
    # ============================================
    risques_avec_evaluation = []
    evaluations_campagne = []
    total_dispositifs = 0
    dispositifs_par_risque = {}
    total_evaluations = 0

    for risque in cartographie.risques:
        # Ignorer risques archivés
        if getattr(risque, 'is_archived', False):
            continue
        if not check_client_access(risque):
            continue

        # --- Évaluation de la campagne active ---
        evaluation = get_client_filter(EvaluationRisque)\
            .filter_by(risque_id=risque.id, campagne_id=campagne_active.id)\
            .order_by(EvaluationRisque.created_at.desc()).first()

        # --- Dispositifs de maîtrise ---
        try:
            dispositifs_risque = get_client_filter(DispositifMaitrise)\
                .filter_by(risque_id=risque.id, is_archived=False)\
                .order_by(DispositifMaitrise.reference.asc()).all()
        except Exception as e:
            _journal(f"⚠️ Erreur dispositifs risque {risque.id}: {e}")
            dispositifs_risque = []

        dispositifs_par_risque[risque.id] = dispositifs_risque
        total_dispositifs += len(dispositifs_risque)
        risque.dispositifs_maitrise_list = dispositifs_risque

        # --- Valeurs par défaut ---
        est_evalue = False
        impact = probabilite = niveau_maitrise = None
        score_net = score_brut = 0.0
        niveau_net = niveau_brut = None
        taux_reduction = 0.0
        probabilite_ajustee = None
        niveau_maitrise_dmr = None
        ecart_maitrise = None
        anomalies = []

        # --- Traitement de l'évaluation ---
        if evaluation:
            impact = (evaluation.impact_conf or evaluation.impact_val or evaluation.impact_pre)
            probabilite = (evaluation.probabilite_conf or evaluation.probabilite_val
                           or evaluation.probabilite_pre)
            niveau_maitrise = (evaluation.niveau_maitrise_conf
                               or evaluation.niveau_maitrise_val
                               or evaluation.niveau_maitrise_pre)

            if impact and probabilite and impact > 0 and probabilite > 0:

                # ============================================
                # ✅ COTATION ISO 31000 (source unique de vérité)
                # ============================================
                scores = calculer_scores_risque(impact, probabilite, niveau_maitrise)
                score_brut = scores['score_brut']
                niveau_brut = scores['niveau_brut']
                score_net = scores['score_net']
                niveau_net = scores['niveau_net']
                probabilite_ajustee = scores['probabilite_ajustee']
                taux_reduction = scores['taux_reduction']

                # --- DMR calcul ---
                try:
                    niveau_maitrise_dmr = calculer_maitrise_depuis_dmr(dispositifs_risque)
                    if niveau_maitrise_dmr is not None and niveau_maitrise:
                        ecart_maitrise = abs(float(niveau_maitrise) - float(niveau_maitrise_dmr))
                except Exception as e:
                    _journal(f"⚠️ DMR calcul {risque.reference}: {e}")
                    niveau_maitrise_dmr = None
                    ecart_maitrise = None

                # ============================================
                # 🔥 SYNCHRONISATION de l'évaluation
                # ============================================
                evaluation.score_risque_brut = score_brut
                evaluation.niveau_risque_brut = niveau_brut
                evaluation.score_risque_net = score_net
                evaluation.niveau_risque_net = niveau_net
                evaluation.probabilite_ajustee = probabilite_ajustee
                evaluation.taux_reduction_maitrise = taux_reduction
                evaluation.niveau_maitrise_dmr = niveau_maitrise_dmr
                evaluation.ecart_maitrise = ecart_maitrise
                # Rétrocompatibilité
                evaluation.score_risque = score_net
                evaluation.niveau_risque = niveau_net

                est_evalue = True
                evaluations_campagne.append(evaluation)
                total_evaluations += 1

                # --- Détection d'anomalies ---
                try:
                    anomalies = detecter_anomalies_risque(risque)
                except Exception as e:
                    _journal(f"⚠️ Anomalies {risque.reference}: {e}")
                    anomalies = []
            else:
                _journal(f"⚠️ Évaluation incomplète: {risque.reference}")

        # ============================================
        # 🔥 DICT COMPLET POUR LE TEMPLATE
        # ============================================
        risques_avec_evaluation.append({
            'risque': risque,
            'evaluation': evaluation,
            'est_evalue': est_evalue,
            # Scores ISO
            'score': score_net,                 # NET (rétrocompat)
            'niveau': niveau_net,               # NET (rétrocompat)
            'score_brut': score_brut,
            'niveau_brut': niveau_brut,
            'score_net': score_net,
            'niveau_net': niveau_net,
            'taux_reduction': taux_reduction,
            'probabilite_ajustee': probabilite_ajustee,
            # Cotations
            'impact': impact,
            'probabilite': probabilite,
            'niveau_maitrise': niveau_maitrise,
            'niveau_maitrise_dmr': niveau_maitrise_dmr,
            'ecart_maitrise': ecart_maitrise,
            # Dispositifs
            'dispositifs': dispositifs_risque,
            'nb_dispositifs': len(dispositifs_risque),
            # Anomalies
            'anomalies': anomalies,
        })

    # ============================================
    # COMMIT des synchronisations ISO
    # ============================================
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        _journal(f"⚠️ Commit ISO échoué: {e}")

    _journal(f"📊 {total_evaluations} évaluations valides / {len(risques_avec_evaluation)} risques")
    _journal(f"🛡️ {total_dispositifs} dispositifs")

    # ============================================
    # 5. TABLEAU DE BORDEAUX (basé sur NET)
    # ============================================
    tableau_bordeaux = {
        'actions_prioritaires': [],
        'surveillance_renforcee': [],
        'surveillance_courante': [],
        'actions_limitees': []
    }

    for item in risques_avec_evaluation:
        if not item['est_evalue'] or not item['niveau_net']:
            continue

        risque_data = {
            'risque': item['risque'],
            'evaluation': item['evaluation'],
            'score': item['score_net'],
            'score_brut': item['score_brut'],
            'niveau': item['niveau_net'],
            'niveau_brut': item['niveau_brut'],
            'taux_reduction': item['taux_reduction'],
            'nb_dispositifs': item['nb_dispositifs'],
        }

        if item['niveau_net'] == 'Critique':
            tableau_bordeaux['actions_prioritaires'].append(risque_data)
        elif item['niveau_net'] == 'Élevé':
            tableau_bordeaux['surveillance_renforcee'].append(risque_data)
        elif item['niveau_net'] == 'Moyen':
            tableau_bordeaux['surveillance_courante'].append(risque_data)
        else:
            tableau_bordeaux['actions_limitees'].append(risque_data)

    # Tri par score NET décroissant
    for cat in tableau_bordeaux:
        tableau_bordeaux[cat].sort(key=lambda x: x['score'], reverse=True)

    # ============================================
    # 6. MATRICES (4 versions)
    # ============================================
    matrice_classique = matrice_criticite = matrice_priorisation = matrice_surbrillance = None

    if evaluations_campagne:
        try:
            _journal(f"🔄 Génération de 3 matrices ({len(evaluations_campagne)} évals)…")
            matrice_classique = generer_matrice_risques(evaluations_campagne, 'classique')
            matrice_criticite = generer_matrice_risques(evaluations_campagne, 'criticite')
            matrice_priorisation = generer_matrice_risques(evaluations_campagne, 'priorisation')

            # Surbrillance = risque le plus critique NET
            risque_surbrillance = None
            if tableau_bordeaux['actions_prioritaires']:
                risque_surbrillance = tableau_bordeaux['actions_prioritaires'][0]['risque']
            elif tableau_bordeaux['surveillance_renforcee']:
                risque_surbrillance = tableau_bordeaux['surveillance_renforcee'][0]['risque']

            if risque_surbrillance:
                _journal(f"🎯 Surbrillance: {risque_surbrillance.reference}")
                matrice_surbrillance = generer_matrice_risque_specifique(
                    evaluations_campagne, risque_surbrillance
                )
        except Exception as e:
            _journal(f"❌ Erreur matrices: {e}")
            import traceback
            traceback.print_exc()

    # ============================================
    # 7. STATISTIQUES GLOBALES
    # ============================================
    nb_risques_total = len([
        r for r in cartographie.risques
        if not getattr(r, 'is_archived', False) and check_client_access(r)
    ])
    nb_risques_evalues = sum(1 for r in risques_avec_evaluation if r['est_evalue'])
    progression_campagne = int(
        (nb_risques_evalues / nb_risques_total * 100) if nb_risques_total > 0 else 0
    )

    # ============================================
    # 8. DEMANDES DE RÉÉVALUATION
    # ============================================
    risque_ids = [r['risque'].id for r in risques_avec_evaluation]
    demandes_reevaluation = []
    nb_demandes_attente = nb_demandes_validees = nb_demandes_rejetees = 0

    if risque_ids:
        demandes_reevaluation = get_client_filter(DemandeReevaluation)\
            .filter(DemandeReevaluation.risque_id.in_(risque_ids))\
            .order_by(DemandeReevaluation.date_demande.desc()).all()

        nb_demandes_attente = sum(1 for d in demandes_reevaluation if d.statut == 'en_attente')
        nb_demandes_validees = sum(1 for d in demandes_reevaluation if d.statut == 'validee')
        nb_demandes_rejetees = sum(1 for d in demandes_reevaluation if d.statut == 'rejetee')

    # ============================================
    # 9. STATISTIQUES DISPOSITIFS
    # ============================================
    stats_dispositifs = {
        'total': total_dispositifs,
        'par_type': {},
        'efficaces': 0,
        'a_verifier': 0,
        'non_evalues': 0,
        'par_risque': {}
    }

    aujourdhui = _aujourdhui()
    for risque_id, dispositifs in dispositifs_par_risque.items():
        stats_dispositifs['par_risque'][risque_id] = len(dispositifs)
        for d in dispositifs:
            if d.type_dispositif:
                stats_dispositifs['par_type'][d.type_dispositif] = \
                    stats_dispositifs['par_type'].get(d.type_dispositif, 0) + 1
            if d.efficacite_reelle and d.efficacite_reelle >= 4:
                stats_dispositifs['efficaces'] += 1
            if d.efficacite_reelle is None:
                stats_dispositifs['non_evalues'] += 1
            if (d.prochaine_verification and d.prochaine_verification <= aujourdhui) \
               or not d.prochaine_verification:
                stats_dispositifs['a_verifier'] += 1

    # ============================================
    # 10. ANALYSE DE COUVERTURE
    # ============================================
    analyse_couverture = []
    for item in risques_avec_evaluation:
        risque = item['risque']
        dispositifs = dispositifs_par_risque.get(risque.id, [])
        efficacites = [d.efficacite_reelle for d in dispositifs
                       if d.efficacite_reelle is not None]
        efficacite_moyenne = (sum(efficacites) / len(efficacites)) if efficacites else None

        analyse_couverture.append({
            'risque_id': risque.id,
            'reference': risque.reference,
            'nb_dispositifs': len(dispositifs),
            'efficacite_moyenne': efficacite_moyenne,
            'niveau_risque': item['niveau_net'],
            'niveau_brut': item['niveau_brut'],
            'score': item['score_net'],
            'score_brut': item['score_brut']
        })

    # ============================================
    # 11. CONSTATS D'AUDIT
    # ============================================
    constats_audit = []
    nb_constats_ouverts = 0
    if risque_ids:
        constats_audit = get_client_filter(Constatation)\
            .join(Constatation.risque)\
            .filter(Risque.cartographie_id == id, Constatation.statut != 'clos')\
            .all()
        nb_constats_ouverts = len(constats_audit)

    # ============================================
    # 12. TRI FINAL
    # ============================================
    risques_avec_evaluation_tries = sorted(
        risques_avec_evaluation,
        key=lambda x: (x['score_net'] if x['score_net'] else 0, x['risque'].reference),
        reverse=True
    )

    # ============================================
    # 13. ANOMALIES GLOBALES (agrégées)
    # ============================================
    anomalies_globales = []
    for item in risques_avec_evaluation:
        for a in item.get('anomalies', []):
            anomalies_globales.append({
                'risque': item['risque'],
                'niveau': a['niveau'],
                'message': a['message'],
                'label': a.get('label', ''),
                'action': a.get('action'),
            })

    # Trier par gravité
    ordre_gravite = {'danger': 0, 'warning': 1, 'info': 2}
    anomalies_globales.sort(key=lambda x: ordre_gravite.get(x['niveau'], 3))

    _journal(f"✅ Préparation terminée: {len(risques_avec_evaluation_tries)} risques, "
          f"{total_dispositifs} dispositifs, {len(anomalies_globales)} anomalies")

    # ============================================
    # 14. RENDU
    # ============================================
    return render_template(
        'cartographie/detail.html',
        # Données principales
        cartographie=cartographie,
        campagne_active=campagne_active,
        campagnes=campagnes,

        # Risques et évaluations (avec TOUS les champs ISO)
        risques_avec_evaluation=risques_avec_evaluation_tries,

        # Statistiques
        nb_risques_total=nb_risques_total,
        nb_risques_evalues=nb_risques_evalues,
        progression_campagne=progression_campagne,

        # Matrices
        matrice_classique=matrice_classique,
        matrice_criticite=matrice_criticite,
        matrice_priorisation=matrice_priorisation,
        matrice_surbrillance=matrice_surbrillance,

        # Tableau de Bordeaux
        tableau_bordeaux=tableau_bordeaux,

        # Dispositifs de maîtrise
        total_dispositifs=total_dispositifs,
        dispositifs_par_risque=dispositifs_par_risque,
        stats_dispositifs=stats_dispositifs,
        analyse_couverture=analyse_couverture,

        # Réévaluations
        demandes_reevaluation=demandes_reevaluation,
        nb_demandes_attente=nb_demandes_attente,
        nb_demandes_validees=nb_demandes_validees,
        nb_demandes_rejetees=nb_demandes_rejetees,

        # Constats d'audit
        constats_audit=constats_audit,
        nb_constats_ouverts=nb_constats_ouverts,

        # Anomalies globales (nouveau)
        anomalies_globales=anomalies_globales,

        # Utilitaires
        now=datetime.now,
        current_user=current_user
    )


@app.route('/api/cartographie/<int:cartographie_id>/demandes-reevaluation')
@login_required
def api_demandes_reevaluation_cartographie(cartographie_id):
    """API pour récupérer les demandes de réévaluation d'une cartographie en temps réel"""
    from models import DemandeReevaluation, Risque
    
    cartographie = get_client_object_or_404(Cartographie, cartographie_id)
    
    if not check_client_access(cartographie):
        return jsonify({'success': False, 'error': 'Accès non autorisé'}), 403
    
    # Récupérer les IDs des risques de la cartographie
    risques = get_client_filter(Risque)\
        .filter_by(cartographie_id=cartographie_id, is_archived=False)\
        .all()
    risque_ids = [r.id for r in risques]
    
    if not risque_ids:
        return jsonify({
            'success': True,
            'demandes': [],
            'nb_attente': 0,
            'nb_validees': 0,
            'nb_rejetees': 0,
            'total': 0
        })
    
    # Récupérer les demandes
    demandes = get_client_filter(DemandeReevaluation)\
        .filter(DemandeReevaluation.risque_id.in_(risque_ids))\
        .order_by(DemandeReevaluation.date_demande.desc())\
        .all()
    
    # Statistiques
    nb_attente = len([d for d in demandes if d.statut == 'en_attente'])
    nb_validees = len([d for d in demandes if d.statut == 'validee'])
    nb_rejetees = len([d for d in demandes if d.statut == 'rejetee'])
    
    # Formater les données
    demandes_data = []
    for d in demandes[:10]:  # Limiter à 10 pour l'API
        demandes_data.append({
            'id': d.id,
            'reference': d.reference,
            'risque_id': d.risque_id,
            'risque_reference': d.risque.reference if d.risque else 'N/A',
            'risque_intitule': d.risque.intitule if d.risque else 'N/A',
            'impact_propose': d.impact_propose,
            'probabilite_propose': d.probabilite_propose,
            'score_propose': d.score_propose,
            'niveau_risque_propose': d.niveau_risque_propose,
            'statut': d.statut,
            'statut_label': d.get_statut_label(),
            'demandeur': d.demandeur.username if d.demandeur else 'Système',
            'date_demande': d.date_demande.strftime('%d/%m/%Y %H:%M') if d.date_demande else '',
            'audit_id': d.audit_id
        })
    
    return jsonify({
        'success': True,
        'demandes': demandes_data,
        'nb_attente': nb_attente,
        'nb_validees': nb_validees,
        'nb_rejetees': nb_rejetees,
        'total': len(demandes)
    })


@app.route('/cartographie/<int:cartographie_id>/evaluer-tous/<int:campagne_id>')
@login_required
def evaluer_tous_risques(cartographie_id, campagne_id):
    """Page pour évaluer tous les risques d'une campagne avec isolation"""
    
    # 1. Récupérer la cartographie avec vérification d'accès
    cartographie = Cartographie.query.get_or_404(cartographie_id)
    
    if not check_client_access(cartographie):
        flash('Accès non autorisé à cette cartographie', 'error')
        return redirect(url_for('liste_cartographies'))
    
    # 2. Récupérer la campagne - SOLUTION SIMPLE SANS get_client_filter()
    if current_user.role == 'super_admin':
        # Super admin peut tout voir
        campagne = CampagneEvaluation.query.get_or_404(campagne_id)
    else:
        # Client normal : filtrer par client_id
        campagne = CampagneEvaluation.query.filter_by(
            id=campagne_id,
            client_id=current_user.client_id
        ).first_or_404()
    
    # Vérification supplémentaire de sécurité
    if not check_client_access(campagne):
        flash('Accès non autorisé à cette campagne', 'error')
        return redirect(url_for('detail_cartographie', id=cartographie_id))
    
    # 3. Vérifier que la campagne appartient à la cartographie
    if campagne.cartographie_id != cartographie_id:
        flash('Cette campagne ne correspond pas à cette cartographie', 'error')
        return redirect(url_for('detail_cartographie', id=cartographie_id))
    
    # 4. Récupérer tous les risques non archivés ET accessibles
    risques = []
    for risque in cartographie.risques:
        # Ignorer les risques archivés
        if hasattr(risque, 'is_archived') and risque.is_archived:
            continue
            
        # Vérifier l'accès
        if check_client_access(risque):
            risques.append(risque)
    
    # 5. Pour chaque risque, vérifier s'il a une évaluation dans cette campagne
    risques_avec_evaluation = []
    for risque in risques:
        # Récupérer l'évaluation avec filtre client
        if current_user.role == 'super_admin':
            evaluation = EvaluationRisque.query.filter_by(
                risque_id=risque.id,
                campagne_id=campagne_id
            ).first()
        else:
            evaluation = EvaluationRisque.query.filter_by(
                risque_id=risque.id,
                campagne_id=campagne_id,
                client_id=current_user.client_id
            ).first()
        
        # Vérification de sécurité supplémentaire
        if evaluation and not check_client_access(evaluation):
            evaluation = None
        
        risques_avec_evaluation.append({
            'risque': risque,
            'evaluation': evaluation,
            'est_evalue': evaluation is not None
        })
    
    return render_template('cartographie/evaluer_tous.html',
                         cartographie=cartographie,
                         campagne=campagne,
                         risques_avec_evaluation=risques_avec_evaluation)


@app.route('/risque/nouveau/<int:cartographie_id>', methods=['GET', 'POST'])
@login_required
def nouveau_risque(cartographie_id):
    """Créer un nouveau risque avec isolation"""
    
    # CORRECTION : Utiliser get_client_filter pour la cartographie
    cartographie = get_client_filter(Cartographie).filter_by(id=cartographie_id).first_or_404()
    
    # Vérifier l'accès à la cartographie
    if not check_client_access(cartographie):
        flash('Accès non autorisé à cette cartographie', 'error')
        return redirect(url_for('liste_cartographies'))
    
    # Vérifier les permissions
    if not current_user.has_permission('can_manage_risks'):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('dashboard'))
    
    form = RisqueForm()
    
    # CORRECTION : Récupérer les configurations de listes déroulantes avec isolation
    categories_liste = get_client_filter(ConfigurationListeDeroulante)\
        .filter_by(nom_technique='categorie')\
        .first()
    
    types_risque_liste = get_client_filter(ConfigurationListeDeroulante)\
        .filter_by(nom_technique='type_risque')\
        .first()
    
    # CORRECTION : Récupérer les champs configurés avec isolation
    champs_configures = get_client_filter(ConfigurationChampRisque)\
        .filter_by(est_actif=True)\
        .order_by('section', 'ordre_affichage')\
        .all()
    
    # Configuration fichiers
    config_fichiers = {
        'extensions': list(app.config.get('ALLOWED_EXTENSIONS', {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'png', 'txt'})),
        'taille_max_mo': app.config.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024) // (1024 * 1024),
        'categories': ['document', 'image', 'analyse', 'autre']
    }
    
    if form.validate_on_submit():
        try:
            # CORRECTION : Générer une référence automatique avec isolation client
            dernier_risque = get_client_filter(Risque)\
                .order_by(Risque.id.desc())\
                .first()
            
            # Format de référence tenant-aware
            if current_user.role == 'super_admin':
                prefix = "RISQ"
            else:
                client_ref = current_user.client.reference if current_user.client else "CLIENT"
                prefix = f"RISQ-{client_ref}"
            
            nouvelle_ref = f"{prefix}-{(dernier_risque.id + 1) if dernier_risque else 1:04d}"
            
            # Créer le risque avec client_id automatique
            risque = Risque(
                reference=nouvelle_ref,
                intitule=form.intitule.data,
                description=form.description.data,
                processus_concerne=form.processus_concerne.data,
                categorie=request.form.get('categorie', form.categorie.data) if categories_liste else form.categorie.data,
                type_risque=request.form.get('type_risque', form.type_risque.data) if types_risque_liste else form.type_risque.data,
                cause_racine=form.cause_racine.data,
                consequences=form.consequences.data,
                cartographie_id=cartographie_id,
                created_by=current_user.id
            )
            
            # CORRECTION : Ajouter automatiquement client_id pour les clients normaux
            if current_user.role != 'super_admin' and hasattr(current_user, 'client_id'):
                risque.client_id = current_user.client_id
            
            db.session.add(risque)
            db.session.flush()  # Pour obtenir l'ID du risque
            
            # Gérer les champs personnalisés
            for champ in champs_configures:
                field_name = f'champ_{champ.nom_technique}'
                fichier_name = f'fichier_{champ.nom_technique}'
                
                if champ.type_champ == 'fichier':
                    # Gestion des fichiers
                    if fichier_name in request.files:
                        fichier = request.files[fichier_name]
                        if fichier and fichier.filename:
                            nom_fichier = secure_filename(fichier.filename)
                            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                            nom_unique = f"{timestamp}_{nom_fichier}"
                            
                            dossier = os.path.join(app.config['UPLOAD_FOLDER'], 'risques', str(risque.id))
                            os.makedirs(dossier, exist_ok=True)
                            chemin = os.path.join(dossier, nom_unique)
                            
                            fichier.save(chemin)
                            
                            champ_perso = ChampPersonnaliseRisque(
                                risque_id=risque.id,
                                nom_technique=champ.nom_technique
                            )
                            
                            # CORRECTION : Ajouter client_id
                            if current_user.role != 'super_admin' and hasattr(current_user, 'client_id'):
                                champ_perso.client_id = current_user.client_id
                            
                            champ_perso.set_valeur(nom_fichier)
                            db.session.add(champ_perso)
                else:
                    # Gestion des autres types de champs
                    if field_name in request.form:
                        valeur = request.form[field_name]
                        
                        if champ.type_champ == 'checkbox':
                            valeur = valeur == 'true'
                        elif champ.type_champ == 'multiselect':
                            valeurs = request.form.getlist(field_name)
                            valeur = valeurs
                        
                        # Ne créer le champ que si valeur non vide ou champ obligatoire
                        if valeur or (champ.est_obligatoire and valeur != ''):
                            champ_perso = ChampPersonnaliseRisque(
                                risque_id=risque.id,
                                nom_technique=champ.nom_technique
                            )
                            
                            # CORRECTION : Ajouter client_id
                            if current_user.role != 'super_admin' and hasattr(current_user, 'client_id'):
                                champ_perso.client_id = current_user.client_id
                            
                            champ_perso.set_valeur(valeur)
                            db.session.add(champ_perso)
            
            # Gérer les fichiers additionnels
            for i in range(10):
                fichier_key = f'fichier_additionnel_{i}'
                categorie_key = f'categorie_fichier_{i}'
                description_key = f'description_fichier_{i}'
                
                if fichier_key in request.files:
                    fichier = request.files[fichier_key]
                    if fichier and fichier.filename:
                        nom_fichier = secure_filename(fichier.filename)
                        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                        nom_unique = f"{timestamp}_{nom_fichier}"
                        
                        dossier = os.path.join(app.config['UPLOAD_FOLDER'], 'risques', str(risque.id))
                        os.makedirs(dossier, exist_ok=True)
                        chemin = os.path.join(dossier, nom_unique)
                        
                        fichier.save(chemin)
                        
                        fichier_db = FichierRisque(
                            risque_id=risque.id,
                            nom_fichier=nom_fichier,
                            chemin_fichier=chemin,
                            type_fichier=fichier.content_type,
                            taille=os.path.getsize(chemin),
                            categorie=request.form.get(categorie_key, 'document'),
                            description=request.form.get(description_key, ''),
                            uploaded_by=current_user.id
                        )
                        
                        # CORRECTION : Ajouter client_id
                        if current_user.role != 'super_admin' and hasattr(current_user, 'client_id'):
                            fichier_db.client_id = current_user.client_id
                        
                        db.session.add(fichier_db)
            
            db.session.commit()
            
            # 🔥 DÉCLENCHEMENT AUTOMATIQUE DES MISES À JOUR
            if 'declencher_mise_a_jour_risque' in globals():
                declencher_mise_a_jour_risque(risque.id, 'creation', current_user.id)
            
            # ==================== NOTIFICATION POUR LE CRÉATEUR ====================
            try:
                if 'Notification' in globals():
                    notification = Notification(
                        destinataire_id=current_user.id,
                        type_notification=Notification.TYPE_SYSTEME,
                        titre=f"Nouveau risque créé: {risque.reference}",
                        message=f"Le risque '{risque.intitule}' a été créé avec succès dans la cartographie '{cartographie.nom}'.",
                        urgence=Notification.URGENCE_NORMAL,
                        entite_type='risque',
                        entite_id=risque.id,
                        donnees_supplementaires={
                            'cartographie_id': cartographie_id,
                            'cartographie_nom': cartographie.nom,
                            'createur': current_user.username
                        }
                    )
                    
                    # CORRECTION : Ajouter client_id
                    if current_user.role != 'super_admin' and hasattr(current_user, 'client_id'):
                        notification.client_id = current_user.client_id
                    
                    db.session.add(notification)
                    db.session.commit()
            except Exception as e:
                _journal(f"Erreur création notification risque: {e}")
            # ===============================================================================
            
            flash('Risque créé avec succès', 'success')
            return redirect(url_for('detail_cartographie', id=cartographie_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la création du risque: {str(e)}', 'error')
            _journal(f"❌ Erreur création risque: {e}")
            import traceback
            traceback.print_exc()
    
    return render_template('cartographie/risque_form.html',
                         form=form,
                         cartographie=cartographie,
                         action='creer',
                         categories_liste=categories_liste,
                         types_risque_liste=types_risque_liste,
                         champs_configures=champs_configures,
                         valeurs_existantes={},
                         config_fichiers=config_fichiers)


@app.route('/cartographie/<int:cartographie_id>/risque/<int:risque_id>/matrice')
@login_required
def matrice_risque_specifique(cartographie_id, risque_id):
    """Matrice de risque spécifique avec isolation"""
    
    # CORRECTION : Vérifier l'accès avec get_client_filter
    cartographie = get_client_filter(Cartographie)\
        .filter_by(id=cartographie_id)\
        .first_or_404()
    
    # Vérifier l'accès à la cartographie
    if not check_client_access(cartographie):
        flash('Accès non autorisé à cette cartographie', 'error')
        return redirect(url_for('liste_cartographies'))
    
    # CORRECTION : Vérifier l'accès au risque
    risque_cible = get_client_filter(Risque)\
        .filter_by(id=risque_id, cartographie_id=cartographie_id)\
        .first_or_404()
    
    if not check_client_access(risque_cible):
        flash('Accès non autorisé à ce risque', 'error')
        return redirect(url_for('detail_cartographie', id=cartographie_id))
    
    # Vérifier que le risque appartient à la cartographie (sécurité supplémentaire)
    if risque_cible.cartographie_id != cartographie_id:
        flash('Ce risque ne fait pas partie de cette cartographie', 'error')
        return redirect(url_for('detail_cartographie', id=cartographie_id))
    
     # ============================================================
    # RÉCUPÉRER LA CAMPAGNE ACTIVE
    # ============================================================
    from models import CampagneEvaluation, EvaluationRisque

    # Campagne passée en paramètre URL ?campagne=X (prioritaire)
    campagne_id_url = request.args.get('campagne', type=int)

    campagne_active = None

    if campagne_id_url:
        # Utiliser la campagne spécifiée en URL
        campagne_active = get_client_filter(CampagneEvaluation)\
            .filter_by(id=campagne_id_url, cartographie_id=cartographie_id)\
            .first()
        _journal(f"📌 Campagne spécifiée (URL): {campagne_active.nom if campagne_active else 'N/A'} (ID={campagne_id_url})")

    if not campagne_active:
        # Fallback : campagne en_cours
        campagne_active = get_client_filter(CampagneEvaluation)\
            .filter_by(cartographie_id=cartographie_id, statut='en_cours')\
            .order_by(CampagneEvaluation.created_at.desc())\
            .first()
        _journal(f"📌 Campagne active: {campagne_active.nom if campagne_active else 'AUCUNE'} (ID={campagne_active.id if campagne_active else 'N/A'})")

    # ============================================================
    # RÉCUPÉRER LES RISQUES DE LA CARTOGRAPHIE
    # ============================================================
    risques_cartographie = get_client_filter(Risque)\
        .filter_by(cartographie_id=cartographie_id, is_archived=False)\
        .all()

    _journal(f"🎯 Matrice spécifique - Cartographie: {cartographie.nom} (ID: {cartographie_id})")
    _journal(f"🎯 Risque cible: {risque_cible.reference} (ID: {risque_id})")
    _journal(f"📊 Total risques dans cartographie: {len(risques_cartographie)}")

    # ============================================================
    # 🔥 UNE SEULE ÉVALUATION PAR RISQUE
    # ============================================================
    evaluations = []

    for risque in risques_cartographie:
        # Vérifier l'accès au risque
        if not check_client_access(risque):
            _journal(f"⚠️ Risque {risque.reference} inaccessible — ignoré")
            continue

        # Ignorer les risques archivés (double vérification)
        if getattr(risque, 'is_archived', False):
            _journal(f"❌ Risque {risque.reference} archivé — ignoré")
            continue

        # 🔥 Priorité 1 : éval de la campagne active/spécifiée
        evaluation = None
        if campagne_active:
            evaluation = get_client_filter(EvaluationRisque)\
                .filter_by(
                    risque_id=risque.id,
                    campagne_id=campagne_active.id
                )\
                .order_by(EvaluationRisque.created_at.desc())\
                .first()

        # 🔥 Priorité 2 : fallback sur la dernière éval confirmée (N-1)
        if not evaluation:
            evaluation = get_client_filter(EvaluationRisque)\
                .filter_by(risque_id=risque.id)\
                .filter(EvaluationRisque.date_confirmation.isnot(None))\
                .order_by(EvaluationRisque.created_at.desc())\
                .first()

            if evaluation:
                _journal(f"   ⚠️ {risque.reference}: fallback N-1 (éval {evaluation.id})")

        # Aucune éval trouvée → passer
        if not evaluation:
            _journal(f"   ❌ {risque.reference}: aucune éval")
            continue

        # Vérifier l'accès à l'évaluation
        if not check_client_access(evaluation):
            continue

        # Vérifier que l'évaluation a des valeurs valides
        impact = (evaluation.impact_conf or evaluation.impact_val 
                  or evaluation.impact_pre)
        probabilite = (evaluation.probabilite_conf 
                       or evaluation.probabilite_val 
                       or evaluation.probabilite_pre)

        if impact and probabilite and impact > 0 and probabilite > 0:
            evaluations.append(evaluation)
            _journal(f"   ✅ {risque.reference}: Impact={impact}, Proba={probabilite}, "
                  f"campagne={evaluation.campagne_id}")

    _journal(f"📊 Total évaluations à afficher: {len(evaluations)} (au lieu de {len(risques_cartographie)} risques × N évals)")
    
    # ============================================================
    # GÉNÉRATION DE LA MATRICE — IMPORT EXPLICITE
    # ============================================================
    matrice_surbrillance = None

    try:
        # 🔥 Import explicite (fiable, pas de globals())
        from utils import generer_matrice_risque_specifique

        _journal(f"🎨 Génération matrice surbrillance pour {risque_cible.reference}")
        matrice_surbrillance = generer_matrice_risque_specifique(evaluations, risque_cible)

        _journal(f"✅ Matrice générée ({len(matrice_surbrillance) if matrice_surbrillance else 0} chars)")

    except ImportError as e:
        _journal(f"❌ Import impossible: {e}")
        _journal(f"   → Vérifie que generer_matrice_risque_specifique existe dans utils.py")
        flash('Fonction de génération de matrice indisponible', 'error')
        return redirect(url_for('detail_cartographie', id=cartographie_id))

    except Exception as e:
        _journal(f"❌ Erreur génération matrice spécifique: {e}")
        import traceback
        traceback.print_exc()
        flash('Erreur lors de la génération de la matrice', 'error')
        return redirect(url_for('detail_cartographie', id=cartographie_id))
    
    # Ajouter des statistiques pour le template
    stats = {
        'total_risques': len(risques_cartographie),
        'total_evaluations': len(evaluations),
        'risque_cible_nom': risque_cible.intitule,
        'risque_cible_reference': risque_cible.reference
    }
    
    # Récupérer l'éval du risque cible pour la campagne affichée
    derniere_evaluation_cible = None
    if campagne_active:
        derniere_evaluation_cible = get_client_filter(EvaluationRisque)\
            .filter_by(risque_id=risque_cible.id, campagne_id=campagne_active.id)\
            .order_by(EvaluationRisque.created_at.desc())\
            .first()

    # Fallback N-1
    if not derniere_evaluation_cible:
        derniere_evaluation_cible = get_client_filter(EvaluationRisque)\
            .filter_by(risque_id=risque_cible.id)\
            .filter(EvaluationRisque.date_confirmation.isnot(None))\
            .order_by(EvaluationRisque.created_at.desc())\
            .first()

    # Récupérer toutes les campagnes
    campagnes_disponibles = get_client_filter(CampagneEvaluation)\
        .filter_by(cartographie_id=cartographie_id)\
        .order_by(CampagneEvaluation.created_at.desc())\
        .all()

    return render_template(
        'cartographie/matrice_risque.html',
        cartographie=cartographie,
        risque_cible=risque_cible,
        matrice_surbrillance=matrice_surbrillance,
        stats=stats,
        campagne_active=campagne_active,
        campagnes_disponibles=campagnes_disponibles,
        derniere_evaluation_cible=derniere_evaluation_cible,   # 🔥 NOUVEAU
        current_user=current_user,
    )


@app.route('/risque/<int:risque_id>/evaluer-campagne/<int:campagne_id>', methods=['GET', 'POST'])
@login_required
def evaluer_risque_campagne(risque_id, campagne_id):
    """Évaluer un risque dans une campagne spécifique"""
    risque = Risque.query.get_or_404(risque_id)
    campagne = CampagneEvaluation.query.get_or_404(campagne_id)
    
    # Vérifier la cohérence
    if risque.cartographie_id != campagne.cartographie_id:
        flash('Le risque et la campagne ne correspondent pas à la même cartographie', 'error')
        return redirect(url_for('detail_cartographie', id=risque.cartographie_id))
    
    # S'assurer que cette campagne est active
    # Désactiver les autres campagnes actives de cette cartographie
    CampagneEvaluation.query.filter_by(
        cartographie_id=risque.cartographie_id,
        statut='en_cours'
    ).update({'statut': 'terminee'})
    
    # Activer cette campagne
    campagne.statut = 'en_cours'
    db.session.commit()
    
    # Rediriger vers l'évaluation triphasée
    flash(f'Campagne "{campagne.nom}" activée', 'success')
    return redirect(url_for('evaluer_risque_triphase', id=risque_id))


@app.route('/risque/<int:id>/evaluation', methods=['GET', 'POST'])
@login_required
def evaluer_risque(id):
    """Évaluation d'un risque avec vérification d'accès"""
    
    # CORRECTION : Récupérer avec vérification d'accès
    risque = Risque.query.get_or_404(id)
    
    # Vérifier l'accès au risque
    if not check_client_access(risque):
        flash('Accès non autorisé à ce risque', 'error')
        return redirect(url_for('liste_risques'))
    
    form = EvaluationForm()
    
    if form.validate_on_submit():
        score_risque = form.impact.data * form.probabilite.data
        niveau_risque, couleur = calculer_niveau_risque(form.impact.data, form.probabilite.data)
        
        evaluation = EvaluationRisque(
            risque_id=id,
            type_evaluation='pre_evaluation',
            evaluateur_id=current_user.id,
            impact=form.impact.data,
            probabilite=form.probabilite.data,
            niveau_maitrise=form.niveau_maitrise.data,
            commentaire=form.commentaire.data,
            score_risque=score_risque,
            niveau_risque=niveau_risque
        )
        
        # CORRECTION : Ajouter automatiquement client_id
        if current_user.role != 'super_admin' and hasattr(current_user, 'client_id'):
            evaluation.client_id = current_user.client_id
        
        db.session.add(evaluation)
        db.session.commit()
        
        # 🔥 DÉCLENCHEMENT AUTOMATIQUE DES MISES À JOUR
        donnees_evaluation = {
            'niveau_risque': niveau_risque,
            'score_risque': score_risque,
            'impact': form.impact.data,
            'probabilite': form.probabilite.data
        }
        declencher_mise_a_jour_risque(id, 'evaluation', current_user.id, donnees_evaluation)
        
        # 🔥 SYNCHRONISATION SPÉCIFIQUE DES MATRICES
        synchroniser_matrices_apres_evaluation(risque.cartographie_id)
        
        flash('Évaluation enregistrée avec succès', 'success')
        return redirect(url_for('detail_cartographie', id=risque.cartographie_id))
    
    return render_template('cartographie/evaluation.html', form=form, risque=risque)


@app.route('/api/risque/<int:risque_id>/generer-kris-ia', methods=['GET'])
@login_required
def generer_kris_ia(risque_id):
    """Générer des suggestions de KRI via IA pour un risque"""
    try:
        # Récupérer le risque avec vérification d'accès
        risque = get_client_object_or_404(Risque, risque_id)
        
        # Préparer les données du risque de manière sécurisée
        risque_data = {
            'id': risque.id,
            'reference': risque.reference,
            'intitule': risque.intitule,
            'description': risque.description,
            'categorie': risque.categorie,
            'probabilite': getattr(risque, 'probabilite', 'Non évaluée'),
            'impact': getattr(risque, 'impact', 'Non évalué'),
            'score_risque': getattr(risque, 'score_risque', 'Non calculé'),
        }
        
        # Ajouter les infos de processus si disponible (avec vérification)
        try:
            if hasattr(risque, 'processus') and risque.processus:
                if hasattr(risque.processus, 'nom'):
                    risque_data['processus'] = {'nom': risque.processus.nom}
                elif isinstance(risque.processus, dict):
                    risque_data['processus'] = risque.processus
                else:
                    risque_data['processus'] = {'nom': str(risque.processus)}
            else:
                risque_data['processus'] = None
        except Exception as e:
            _journal(f"⚠️ Erreur récupération processus: {e}")
            risque_data['processus'] = None
        
        # Ajouter le responsable si disponible (avec vérification)
        try:
            if hasattr(risque, 'responsable') and risque.responsable:
                if hasattr(risque.responsable, 'username'):
                    risque_data['responsable'] = {'username': risque.responsable.username}
                elif isinstance(risque.responsable, dict):
                    risque_data['responsable'] = risque.responsable
                else:
                    risque_data['responsable'] = {'username': str(risque.responsable)}
            else:
                risque_data['responsable'] = None
        except Exception as e:
            _journal(f"⚠️ Erreur récupération responsable: {e}")
            risque_data['responsable'] = None
        
        # Générer les KRI via IA
        from services.kri_ia_service import kri_ia_service
        suggestions = kri_ia_service.generer_kris_pour_risque(risque_data)
        
        return jsonify({
            'success': True,
            'risque_id': risque_id,
            'risque_reference': risque.reference,
            'suggestions': suggestions,
            'count': len(suggestions),
            'metadata': {
                'generated_at': datetime.utcnow().isoformat(),
                'mode': 'simulation' if kri_ia_service.mode_simulation else 'reel'
            }
        })
        
    except Exception as e:
        _journal(f"❌ Erreur génération KRI IA: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Erreur lors de la génération des suggestions'
        }), 500


@app.route('/api/risque/<int:risque_id>/kris/suggestions', methods=['GET'])
@login_required
def suggestions_kris_fallback(risque_id):
    """Suggestions de KRI (fallback si IA échoue)"""
    try:
        # Récupérer le risque
        risque = get_client_object_or_404(Risque, risque_id)
        
        # Suggestions génériques qui fonctionnent toujours
        suggestions = [
            {
                "nom": f"Taux d'occurrence - {risque.reference}",
                "description": f"Mesure la fréquence d'apparition du risque : {risque.intitule}",
                "formule_calcul": "(Nombre d'occurrences / Période) × 100",
                "unite_mesure": "%",
                "categorie": "operationnel",
                "seuil_alerte": 5.0,
                "seuil_critique": 10.0,
                "sens_evaluation_seuil": "superieur",
                "frequence_mesure": "mensuel",
                "justification": "Indicateur de base pour surveiller la fréquence du risque"
            },
            {
                "nom": f"Impact moyen - {risque.reference}",
                "description": f"Impact financier moyen du risque {risque.intitule}",
                "formule_calcul": "Somme des impacts / Nombre d'occurrences",
                "unite_mesure": "€",
                "categorie": "financier",
                "seuil_alerte": 5000.0,
                "seuil_critique": 10000.0,
                "sens_evaluation_seuil": "superieur",
                "frequence_mesure": "trimestriel",
                "justification": "Mesure l'impact financier du risque"
            }
        ]
        
        # Ajouter une suggestion basée sur la catégorie
        categorie = getattr(risque, 'categorie', '').lower()
        
        if 'securite' in categorie or 'conformite' in categorie:
            suggestions.append({
                "nom": f"Taux de conformité - {risque.reference}",
                "description": "Pourcentage de conformité aux exigences",
                "formule_calcul": "(Nombre de contrôles conformes / Total des contrôles) × 100",
                "unite_mesure": "%",
                "categorie": "conformite",
                "seuil_alerte": 90.0,
                "seuil_critique": 80.0,
                "sens_evaluation_seuil": "inferieur",
                "frequence_mesure": "trimestriel",
                "justification": "Surveille le niveau de conformité"
            })
        
        # Ajouter des métadonnées
        for suggestion in suggestions:
            suggestion['_metadata'] = {
                'generated_at': datetime.utcnow().isoformat(),
                'mode': 'fallback',
                'score_confiance': 85.0
            }
        
        return jsonify({
            'success': True,
            'risque_id': risque_id,
            'risque_reference': risque.reference,
            'suggestions': suggestions,
            'count': len(suggestions),
            'metadata': {
                'generated_at': datetime.utcnow().isoformat(),
                'mode': 'fallback',
                'note': 'Suggestions génériques (IA non disponible)'
            }
        })
        
    except Exception as e:
        _journal(f"❌ Erreur suggestions fallback: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/risque/<int:id>/kri/ia', methods=['GET'])
@login_required
def creer_kri_ia_depuis_risque(id):
    """Créer un KRI via IA depuis un risque existant"""
    risque = get_client_object_or_404(Risque, id)
    
    # Vérifier les permissions
    if not current_user.has_permission('can_manage_kri'):
        flash('Vous n\'avez pas les permissions pour créer un KRI', 'error')
        return redirect(url_for('detail_risque', id=id))
    
    # Vérifier s'il y a déjà un KRI
    kri_existant = get_client_filter(KRI).filter_by(
        risque_id=id, 
        type_indicateur='kri',
        est_actif=True
    ).first()
    
    if kri_existant:
        flash(f'Un KRI existe déjà pour ce risque: {kri_existant.nom}', 'warning')
        return redirect(url_for('detail_risque', id=id))
    
    # Rediriger vers le formulaire avec pré-remplissage IA
    return redirect(url_for('nouveau_kri', risque_id=id))


@app.route('/risque/<int:id>/evaluation-triphase', methods=['GET', 'POST'])
@login_required
def evaluer_risque_triphase(id):
    """
    Évaluation triphase d'un risque (ISO 31000 / 31010).

    RÈGLE CRITIQUE :
        Une évaluation est UNIQUE par (risque_id, campagne_id).
        La campagne active est :
            1. Une campagne 'en_cours' de la cartographie
            2. Sinon, la campagne pointée par carto.campagne_active_id
            3. Sinon, création d'une nouvelle campagne
        Un pointeur vers une campagne 'terminee' est IGNORÉ.
    """
    from datetime import datetime, timezone
    # (règle unique : calculer_scores_risque et calculer_maitrise_depuis_dmr viennent de app.py / cotation.py)

    _journal(f"\n{'='*70}")
    _journal(f"🎯 EVALUATION TRIPHASE — Risque ID={id}")
    _journal(f"   URL: {request.url}")
    _journal(f"   Méthode: {request.method}")
    _journal(f"{'='*70}")

    # ============================================
    # 1. RISQUE + SÉCURITÉ
    # ============================================
    risque = Risque.query.get_or_404(id)

    if not check_client_access(risque):
        flash('Accès non autorisé à ce risque', 'error')
        return redirect(url_for('dashboard'))

    _journal(f"📌 Risque: {risque.reference}")
    _journal(f"📌 Cartographie ID: {risque.cartographie_id}")
    _journal(f"📌 User: {current_user.username} (role={current_user.role})")

    # ============================================
    # 2. DISPOSITIFS + DMR
    # ============================================
    dispositifs = DispositifMaitrise.query\
        .filter_by(risque_id=id, is_archived=False)\
        .order_by(DispositifMaitrise.created_at.desc())\
        .all()

    niveau_maitrise_dmr = calculer_maitrise_depuis_dmr(dispositifs)

    dispositifs_evalues = [d for d in dispositifs if d.efficacite_reelle]
    stats_dmr = {
        'nb': len(dispositifs),
        'nb_evalues': len(dispositifs_evalues),
        'efficacite_moyenne': round(
            sum(d.efficacite_reelle for d in dispositifs_evalues) /
            max(len(dispositifs_evalues), 1), 1
        ) if dispositifs_evalues else 0,
        'couverture_moyenne': round(
            sum(d.couverture or 0 for d in dispositifs_evalues) /
            max(len(dispositifs_evalues), 1), 1
        ) if dispositifs_evalues else 0,
    }

    _journal(f"🛡️ Dispositifs: {stats_dmr['nb']} ({stats_dmr['nb_evalues']} évalués)")
    _journal(f"🎯 DMR: {niveau_maitrise_dmr}/5")

    # ============================================
    # 3. FORMULAIRE + UTILISATEURS
    # ============================================
    form = EvaluationTriPhaseForm()

    if current_user.role == 'super_admin':
        users = User.query.filter(User.is_active == True).all()
    else:
        users = get_client_filter(User).filter(User.is_active == True).all()

    form.referent_pre_evaluation_id.choices = [(0, 'Sélectionnez un référent...')] + [
        (u.id, f"{u.username} - {u.role}") for u in users
    ]

    risques_cartographie = get_client_filter(Risque)\
        .filter_by(cartographie_id=risque.cartographie_id)\
        .order_by(Risque.is_archived.asc(), Risque.reference.asc())\
        .all()

    # ============================================
    # 4. CAMPAGNE ACTIVE — LOGIQUE STRICTE
    # ============================================
    carto = Cartographie.query.get(risque.cartographie_id)
    campagne_active = None

    _journal(f"\n🔍 RECHERCHE CAMPAGNE ACTIVE")
    _journal(f"   carto.campagne_active_id = {carto.campagne_active_id if carto else 'N/A'}")

    # Priorité 1 : campagne 'en_cours' de la carto (LA SEULE SOURCE DE VÉRITÉ)
    campagne_active = CampagneEvaluation.query\
        .filter_by(cartographie_id=risque.cartographie_id, statut='en_cours')\
        .order_by(CampagneEvaluation.created_at.desc())\
        .first()

    if campagne_active:
        _journal(f"   ✅ Campagne 'en_cours' trouvée : {campagne_active.nom} (ID={campagne_active.id})")
    else:
        _journal(f"   ⚠️ Aucune campagne 'en_cours' trouvée")

    # Priorité 2 : si aucune en_cours, utiliser le pointeur carto MAIS uniquement si EN_COURS
    if not campagne_active and carto and carto.campagne_active_id:
        candidate = CampagneEvaluation.query.get(carto.campagne_active_id)
        if candidate and candidate.statut == 'en_cours':
            campagne_active = candidate
            _journal(f"   ✅ Campagne via pointeur carto : {campagne_active.nom} (ID={campagne_active.id})")
        elif candidate:
            _journal(f"   ⚠️ Pointeur carto vers campagne '{candidate.nom}' "
                  f"(statut={candidate.statut}) → IGNORÉ")

    # Priorité 3 : aucune campagne en cours → on ne crée plus de campagne en douce (ouvrir une page ne doit rien créer) :
    # l'utilisateur est invité à ouvrir une campagne d'évaluation, ce qui clôture proprement la précédente.
    if not campagne_active and carto is not None:
        flash("Aucune campagne d'évaluation en cours pour cette cartographie : ouvrez-en une pour évaluer ce risque.", 'warning')
        if current_user.has_permission('can_manage_risks'):
            return redirect(url_for('nouvelle_campagne_cartographie', id=carto.id))
        return redirect(url_for('detail_risque', id=id))
    if not campagne_active:
        annee_courante = datetime.now().year
        campagne_active = CampagneEvaluation(
            cartographie_id=risque.cartographie_id,
            nom=f"Campagne {annee_courante}",
            description=f"Évaluation annuelle {annee_courante}",
            date_debut=_aujourdhui(),
            statut='en_cours',
            created_by=current_user.id,
            client_id=risque.client_id or current_user.client_id
        )
        db.session.add(campagne_active)
        db.session.flush()
        _journal(f"   ✅ Campagne créée : {campagne_active.nom} (ID={campagne_active.id})")

    # Sync pointeur carto
    if carto and carto.campagne_active_id != campagne_active.id:
        carto.campagne_active_id = campagne_active.id
        try:
            db.session.commit()
            _journal(f"   🔗 carto.campagne_active_id → {campagne_active.id}")
        except Exception as e:
            db.session.rollback()
            _journal(f"   ⚠️ Sync échouée: {e}")

    _journal(f"\n📌 Campagne active FINALE : {campagne_active.nom} (ID={campagne_active.id})")

    # ============================================
    # 5. RÉCUPÉRATION DE L'ÉVALUATION — STRICT
    # ============================================
    evaluation_id = request.args.get('evaluation_id', type=int)

    if evaluation_id:
        evaluation_reelle = EvaluationRisque.query.filter_by(
            id=evaluation_id,
            risque_id=id,
            campagne_id=campagne_active.id
        ).first()
        if evaluation_reelle:
            _journal(f"📌 Éval spécifiée (ID={evaluation_id}) sur campagne {campagne_active.id}")
        else:
            _journal(f"⚠️ Éval {evaluation_id} introuvable pour campagne {campagne_active.id}")
    else:
        # 🔥 UNIQUEMENT l'éval de la campagne active
        evaluation_reelle = EvaluationRisque.query\
            .filter_by(risque_id=id, campagne_id=campagne_active.id)\
            .order_by(EvaluationRisque.created_at.desc())\
            .first()

    # Debug complet
    toutes_evals = EvaluationRisque.query.filter_by(risque_id=id).all()
    _journal(f"\n🔍 DEBUG ÉVALS POUR RISQUE {id}")
    _journal(f"   Total évals: {len(toutes_evals)}")
    for ev in toutes_evals:
        marker = " 👈 SÉLECTIONNÉE" if evaluation_reelle and ev.id == evaluation_reelle.id else ""
        _journal(f"      Éval {ev.id}: campagne_id={ev.campagne_id}, "
              f"campagne_nom={ev.campagne_nom}, statut={ev.statut_validation}{marker}")

    if evaluation_reelle:
        _journal(f"\n📌 ✅ Éval SÉLECTIONNÉE: ID={evaluation_reelle.id}")
        _journal(f"   campagne_id={evaluation_reelle.campagne_id}")
        _journal(f"   statut_validation={evaluation_reelle.statut_validation}")
        _journal(f"   date_validation={evaluation_reelle.date_validation}")
        _journal(f"   date_confirmation={evaluation_reelle.date_confirmation}")
    else:
        _journal(f"\n📌 ❌ AUCUNE éval pour campagne {campagne_active.id} → CRÉATION À VENIR")

    # ============================================
    # 6. HELPERS
    # ============================================
    def initialiser_metadonnees(evaluation):
        if evaluation.metadonnees is None:
            evaluation.metadonnees = {}
        if 'historique_modifications' not in evaluation.metadonnees:
            evaluation.metadonnees['historique_modifications'] = []
            marquer_json_modifie(evaluation, 'metadonnees')
        if 'commentaires' not in evaluation.metadonnees:
            evaluation.metadonnees['commentaires'] = []
            marquer_json_modifie(evaluation, 'metadonnees')
        return evaluation.metadonnees

    def ajouter_historique(evaluation, action, details=None):
        metadonnees = initialiser_metadonnees(evaluation)
        metadonnees['historique_modifications'].append({
            'date': datetime.now(timezone.utc).isoformat(),
            'action': action,
            'utilisateur': current_user.username,
            'details': details or ''
        })
        return metadonnees

    def ajouter_commentaire(evaluation, phase, commentaire):
        if commentaire and commentaire.strip():
            metadonnees = initialiser_metadonnees(evaluation)
            metadonnees['commentaires'].append({
                'date': datetime.now(timezone.utc).isoformat(),
                'phase': phase,
                'utilisateur': current_user.username,
                'commentaire': commentaire.strip()
            })
        return evaluation

    def appliquer_cotation_iso(evaluation, impact, probabilite, niveau_maitrise):
        scores = calculer_scores_risque(impact, probabilite, niveau_maitrise)

        evaluation.score_risque_brut = scores['score_brut']
        evaluation.niveau_risque_brut = scores['niveau_brut']
        evaluation.score_risque_net = scores['score_net']
        evaluation.niveau_risque_net = scores['niveau_net']
        evaluation.probabilite_ajustee = scores['probabilite_ajustee']
        evaluation.taux_reduction_maitrise = scores['taux_reduction']
        evaluation.score_risque = scores['score_net']
        evaluation.niveau_risque = scores['niveau_net']

        evaluation.niveau_maitrise_dmr = niveau_maitrise_dmr
        if niveau_maitrise_dmr is not None and niveau_maitrise:
            evaluation.ecart_maitrise = abs(
                float(niveau_maitrise) - float(niveau_maitrise_dmr)
            )
        else:
            evaluation.ecart_maitrise = None

        _journal(f"💰 BRUT={scores['score_brut']} → NET={scores['score_net']} "
              f"(maîtrise {niveau_maitrise}/5, −{scores['taux_reduction']*100:.0f}%)")
        return scores

    # ============================================
    # 7. DummyEvaluation
    # ============================================
    class DummyEvaluation:
        def __init__(self):
            self.id = None
            self.date_pre_evaluation = None
            self.impact_pre = 0
            self.probabilite_pre = 0
            self.niveau_maitrise_pre = 3
            self.commentaire_pre_evaluation = ''
            self.referent_pre_evaluation_id = 0
            self.date_validation = None
            self.impact_val = 0
            self.probabilite_val = 0
            self.niveau_maitrise_val = 0
            self.statut_validation = 'en_attente'
            self.commentaire_validation = ''
            self.date_confirmation = None
            self.impact_conf = 0
            self.probabilite_conf = 0
            self.niveau_maitrise_conf = 0
            self.commentaire_confirmation = ''
            self.niveau_risque = None
            self.score_risque = 0
            self.score_risque_brut = 0
            self.niveau_risque_brut = None
            self.score_risque_net = 0
            self.niveau_risque_net = None
            self.probabilite_ajustee = None
            self.taux_reduction_maitrise = 0
            self.niveau_maitrise_dmr = None
            self.ecart_maitrise = None
            self.validateur_id = None
            self.validateur = None
            self.evaluateur_final_id = None
            self.evaluateur_final = None
            self.referent_pre_evaluation = None
            self.campagne_id = campagne_active.id if campagne_active else None
            self.campagne_nom = campagne_active.nom if campagne_active else ''
            self.campagne_date_debut = campagne_active.date_debut if campagne_active else None
            self.campagne_date_fin = campagne_active.date_fin if campagne_active else None
            self.campagne_objectif = campagne_active.description if campagne_active else ''
            self.metadonnees = {'historique_modifications': [], 'commentaires': []}
            self.origine = 'manuel'
            self.audit_source = None
            self.constat_source = None
            self.client_id = (
                getattr(current_user, 'client_id', None)
                or (risque.client_id if risque else None)
            )
            self.created_by = current_user.id
            self.created_at = datetime.now(timezone.utc)
            self.updated_at = datetime.now(timezone.utc)

        def get_origine_label(self): return 'Manuel'
        def get_origine_css(self): return 'secondary'
        def get_coherence_statut(self): return 'info'
        def get_coherence_message(self): return "Aucune évaluation."
        def get_pourcentage_reduction(self): return 0

        def get_valeurs_finales(self):
            return {
                'impact': 0, 'probabilite': 0, 'niveau_maitrise': 3,
                'score': 0, 'niveau_risque': None, 'phase': 'pre_evaluation'
            }

        def get_scores_complets(self):
            return {
                'score_brut': 0, 'niveau_brut': None,
                'score_net': 0, 'niveau_net': None,
                'taux_reduction': 0, 'probabilite_ajustee': None,
            }

        def get_score_affichage(self):
            return {
                'brut': {'score': 0, 'niveau': 'Non évalué', 'couleur': 'secondary'},
                'net': {'score': 0, 'niveau': 'Non évalué', 'couleur': 'secondary'},
                'reduction': {'pourcentage': 0, 'taux': 0},
                'probabilite_ajustee': None,
            }

    if evaluation_reelle:
        initialiser_metadonnees(evaluation_reelle)
        evaluation_en_cours = evaluation_reelle
    else:
        evaluation_en_cours = DummyEvaluation()

    # ============================================
    # 8. TRAITEMENT DU POST
    # ============================================
    if request.method == 'POST':
        _journal(f"\n📨 POST par {current_user.username}")

        try:
            bouton_soumis = None
            rediriger_vers_fiche = False

            for key, value in request.form.items():
                if key == 'submit_phase1':
                    bouton_soumis = 'submit_phase1'
                    rediriger_vers_fiche = request.form.get('redirect_fiche') == 'true'
                    break
                elif key == 'submit_phase2':
                    bouton_soumis = 'submit_phase2'
                    rediriger_vers_fiche = request.form.get('redirect_fiche') == 'true'
                    break
                elif key == 'submit_phase3':
                    bouton_soumis = 'submit_phase3'
                    rediriger_vers_fiche = True
                    break

            if not bouton_soumis:
                if 'impact_conf' in request.form or 'campagne_nom' in request.form:
                    bouton_soumis = 'submit_phase3'
                    rediriger_vers_fiche = True
                elif 'impact_val' in request.form or 'statut_validation' in request.form:
                    bouton_soumis = 'submit_phase2'
                elif 'impact_pre' in request.form:
                    bouton_soumis = 'submit_phase1'

            _journal(f"🔘 Bouton: {bouton_soumis}")

            score_brut_pour_flash = 0
            score_net_pour_flash = 0
            niveau_brut_pour_flash = None
            niveau_net_pour_flash = None

            # ============================================
            # PHASE 1 — PRÉ-ÉVALUATION
            # ============================================
            if bouton_soumis == 'submit_phase1':
                _journal("🔄 Phase 1...")

                try:
                    impact_pre = int(request.form.get('impact_pre', 0))
                    probabilite_pre = int(request.form.get('probabilite_pre', 0))
                    niveau_maitrise_str = request.form.get('niveau_maitrise_pre', '3')
                    niveau_maitrise_pre = 3 if niveau_maitrise_str in ['None', '', None] \
                        else int(niveau_maitrise_str)
                except (ValueError, TypeError) as e:
                    _journal(f"❌ Conversion: {e}")
                    flash('Valeurs invalides', 'error')
                    return redirect(url_for('evaluer_risque_triphase', id=id))

                referent_id = request.form.get('referent_pre_evaluation_id')
                commentaire = request.form.get('commentaire_pre_evaluation', '')

                _journal(f"📊 Impact={impact_pre}, Proba={probabilite_pre}, Maîtrise={niveau_maitrise_pre}")

                if impact_pre == 0 or probabilite_pre == 0:
                    flash('Impact et probabilité requis', 'error')
                    return redirect(url_for('evaluer_risque_triphase', id=id))

                # 🔥 RE-VÉRIFIER qu'il n'y a pas déjà une éval pour cette campagne
                # (au cas où une autre session en aurait créé une entre temps)
                if not evaluation_reelle:
                    existing = EvaluationRisque.query.filter_by(
                        risque_id=id,
                        campagne_id=campagne_active.id
                    ).first()
                    if existing:
                        evaluation_reelle = existing
                        _journal(f"⚠️ Éval existante détectée: ID={existing.id}")

                if evaluation_reelle:
                    # ========== MISE À JOUR ==========
                    _journal(f"📝 MISE À JOUR éval ID={evaluation_reelle.id} "
                          f"(campagne={evaluation_reelle.campagne_id})")

                    # Vérifier que l'éval est bien sur la campagne active
                    if evaluation_reelle.campagne_id != campagne_active.id:
                        _journal(f"🚨 BUG: éval sur campagne {evaluation_reelle.campagne_id} "
                              f"≠ active {campagne_active.id}")
                        flash('Erreur: évaluation dans une autre campagne. Rechargez.', 'error')
                        return redirect(url_for('evaluer_risque_triphase', id=id))

                    # Sauvegarder version antérieure
                    if evaluation_reelle.impact_pre:
                        initialiser_metadonnees(evaluation_reelle)
                        evaluation_reelle.metadonnees.setdefault('versions_anterieures', [])
                        marquer_json_modifie(evaluation_reelle, 'metadonnees')
                        evaluation_reelle.metadonnees['versions_anterieures'].append({
                            'date': evaluation_reelle.date_pre_evaluation.isoformat() if evaluation_reelle.date_pre_evaluation else None,
                            'impact': evaluation_reelle.impact_pre,
                            'probabilite': evaluation_reelle.probabilite_pre,
                            'niveau_maitrise': evaluation_reelle.niveau_maitrise_pre,
                            'score_brut': evaluation_reelle.score_risque_brut,
                            'score_net': evaluation_reelle.score_risque_net,
                            'utilisateur': current_user.username
                        })
                        marquer_json_modifie(evaluation_reelle, 'metadonnees')

                    evaluation_reelle.referent_pre_evaluation_id = (
                        int(referent_id) if referent_id and referent_id != '0' else None
                    )
                    evaluation_reelle.date_pre_evaluation = datetime.now(timezone.utc)
                    evaluation_reelle.impact_pre = impact_pre
                    evaluation_reelle.probabilite_pre = probabilite_pre
                    evaluation_reelle.niveau_maitrise_pre = niveau_maitrise_pre
                    evaluation_reelle.commentaire_pre_evaluation = commentaire
                    evaluation_reelle.updated_at = datetime.now(timezone.utc)

                    evaluation_reelle.campagne_nom = campagne_active.nom
                    evaluation_reelle.campagne_date_debut = campagne_active.date_debut
                    evaluation_reelle.campagne_date_fin = campagne_active.date_fin
                    evaluation_reelle.campagne_objectif = campagne_active.description

                    if evaluation_reelle.statut_validation == 'a_revoir':
                        _journal(f"🔄 statut: a_revoir → en_attente")
                        evaluation_reelle.statut_validation = 'en_attente'

                    scores = appliquer_cotation_iso(
                        evaluation_reelle, impact_pre, probabilite_pre, niveau_maitrise_pre
                    )

                    score_brut_pour_flash = scores['score_brut']
                    score_net_pour_flash = scores['score_net']
                    niveau_brut_pour_flash = scores['niveau_brut']
                    niveau_net_pour_flash = scores['niveau_net']

                    initialiser_metadonnees(evaluation_reelle)
                    ajouter_historique(
                        evaluation_reelle,
                        'Phase 1 - Pré-évaluation',
                        f"Impact={impact_pre}, Proba={probabilite_pre}, Maîtrise={niveau_maitrise_pre}, "
                        f"BRUT={score_brut_pour_flash}, NET={score_net_pour_flash}"
                    )
                    ajouter_commentaire(evaluation_reelle, 'Pré-évaluation', commentaire)

                    evaluation_en_cours = evaluation_reelle

                else:
                    # ========== CRÉATION ==========
                    _journal(f"✅ CRÉATION nouvelle éval pour campagne {campagne_active.nom} (ID={campagne_active.id})")

                    evaluation = EvaluationRisque(
                        risque_id=id,
                        campagne_id=campagne_active.id,
                        cartographie_id=risque.cartographie_id,
                        referent_pre_evaluation_id=(
                            int(referent_id) if referent_id and referent_id != '0' else None
                        ),
                        date_pre_evaluation=datetime.now(timezone.utc),
                        impact_pre=impact_pre,
                        probabilite_pre=probabilite_pre,
                        niveau_maitrise_pre=niveau_maitrise_pre,
                        commentaire_pre_evaluation=commentaire,
                        statut_validation='en_attente',
                        created_by=current_user.id,
                        campagne_nom=campagne_active.nom,
                        campagne_date_debut=campagne_active.date_debut,
                        campagne_date_fin=campagne_active.date_fin,
                        campagne_objectif=campagne_active.description,
                        metadonnees={'historique_modifications': [], 'commentaires': []}
                    )

                    if current_user.role != 'super_admin' and hasattr(current_user, 'client_id'):
                        evaluation.client_id = current_user.client_id
                    elif risque.client_id:
                        evaluation.client_id = risque.client_id
                    elif campagne_active.client_id:
                        evaluation.client_id = campagne_active.client_id

                    scores = appliquer_cotation_iso(
                        evaluation, impact_pre, probabilite_pre, niveau_maitrise_pre
                    )

                    score_brut_pour_flash = scores['score_brut']
                    score_net_pour_flash = scores['score_net']
                    niveau_brut_pour_flash = scores['niveau_brut']
                    niveau_net_pour_flash = scores['niveau_net']

                    db.session.add(evaluation)
                    db.session.flush()

                    initialiser_metadonnees(evaluation)
                    ajouter_historique(
                        evaluation,
                        'Phase 1 - Pré-évaluation (création)',
                        f"Impact={impact_pre}, Proba={probabilite_pre}, Maîtrise={niveau_maitrise_pre}, "
                        f"BRUT={score_brut_pour_flash}, NET={score_net_pour_flash}"
                    )
                    ajouter_commentaire(evaluation, 'Pré-évaluation', commentaire)

                    evaluation_reelle = evaluation
                    evaluation_en_cours = evaluation
                    _journal(f"✅ Nouvelle éval créée (ID={evaluation.id}, campagne={evaluation.campagne_id})")

                db.session.commit()
                _journal(f"💾 Commit OK")

                flash(
                    f'✅ Pré-évaluation enregistrée '
                    f'(BRUT : {score_brut_pour_flash}/25 [{niveau_brut_pour_flash}] → '
                    f'NET : {score_net_pour_flash}/25 [{niveau_net_pour_flash}])',
                    'success'
                )

                if rediriger_vers_fiche:
                    return redirect(url_for('detail_risque', id=id))
                return redirect(url_for('evaluer_risque_triphase', id=id))

            # ============================================
            # PHASE 2 — VALIDATION
            # ============================================
            elif bouton_soumis == 'submit_phase2':
                _journal("🔄 Phase 2...")

                if not evaluation_reelle:
                    flash('❌ Aucune évaluation. Complétez la Phase 1.', 'error')
                    return redirect(url_for('evaluer_risque_triphase', id=id))


                statut_validation = request.form.get('statut_validation', 'en_attente')

                try:
                    impact_val = int(request.form.get('impact_val', 0))
                    probabilite_val = int(request.form.get('probabilite_val', 0))
                    niveau_maitrise_val = int(request.form.get('niveau_maitrise_val', 0))
                except (ValueError, TypeError):
                    impact_val = probabilite_val = niveau_maitrise_val = 0

                commentaire_validation = request.form.get('commentaire_validation', '')

                impact_final = impact_val if impact_val > 0 else (evaluation_reelle.impact_pre or 0)
                probabilite_final = probabilite_val if probabilite_val > 0 else (evaluation_reelle.probabilite_pre or 0)

                if niveau_maitrise_val > 0:
                    niveau_maitrise_final = niveau_maitrise_val
                elif evaluation_reelle.niveau_maitrise_pre:
                    niveau_maitrise_final = evaluation_reelle.niveau_maitrise_pre
                elif niveau_maitrise_dmr is not None:
                    niveau_maitrise_final = round(niveau_maitrise_dmr)
                else:
                    niveau_maitrise_final = 3

                _journal(f"🎯 Phase 2 — Impact={impact_final}, Proba={probabilite_final}, "
                      f"Maîtrise={niveau_maitrise_final}, Statut={statut_validation}")

                evaluation_reelle.validateur_id = current_user.id
                evaluation_reelle.impact_val = impact_val if impact_val > 0 else None
                evaluation_reelle.probabilite_val = probabilite_val if probabilite_val > 0 else None
                evaluation_reelle.niveau_maitrise_val = (
                    niveau_maitrise_val if niveau_maitrise_val > 0 else niveau_maitrise_final
                )
                evaluation_reelle.commentaire_validation = commentaire_validation
                evaluation_reelle.statut_validation = statut_validation
                try:
                    from egalyx.parametres_risque import valideur_operateurs
                    _ref = User.query.get(evaluation_reelle.referent_pre_evaluation_id) if evaluation_reelle.referent_pre_evaluation_id else None
                    if (statut_validation == 'valide' and _ref is not None and getattr(_ref, 'is_operateur', False)
                            and valideur_operateurs(current_user.client_id, risque.cartographie_id) is not None):
                        evaluation_reelle.statut_validation = 'en_attente_admin'   # puis confirmation par l'administrateur
                except Exception as _e:
                    _journal(f"⚠️ Valideur des opérateurs : {_e}")
                evaluation_reelle.updated_at = datetime.now(timezone.utc)

                evaluation_reelle.campagne_nom = campagne_active.nom
                evaluation_reelle.campagne_date_debut = campagne_active.date_debut
                evaluation_reelle.campagne_date_fin = campagne_active.date_fin
                evaluation_reelle.campagne_objectif = campagne_active.description

                if statut_validation == 'a_revoir':
                    _journal(f"⚠️ Marqué À REVOIR")
                    evaluation_reelle.date_validation = None
                    evaluation_reelle.date_confirmation = None
                    evaluation_reelle.evaluateur_final_id = None

                    if evaluation_reelle.referent_pre_evaluation_id:
                        try:
                            from models import Notification
                            notif = Notification(
                                destinataire_id=evaluation_reelle.referent_pre_evaluation_id,
                                type_notification='evaluation_a_revoir',
                                titre=f'Risque {risque.reference} à revoir',
                                message=f'Votre évaluation a été marquée "à revoir" par '
                                        f'{current_user.username}. '
                                        f'Motif : {commentaire_validation or "Non précisé"}',
                                urgence='important',
                                entite_type='evaluation',
                                entite_id=evaluation_reelle.id,
                                client_id=evaluation_reelle.client_id
                            )
                            db.session.add(notif)
                            _journal(f"📢 Notification envoyée à user {evaluation_reelle.referent_pre_evaluation_id}")
                        except Exception as e:
                            _journal(f"⚠️ Notification échouée: {e}")

                    initialiser_metadonnees(evaluation_reelle)
                    ajouter_historique(
                        evaluation_reelle,
                        'Phase 2 - À REVOIR',
                        f"Motif: {commentaire_validation or 'Non précisé'}"
                    )
                    ajouter_commentaire(evaluation_reelle, 'Validation (à revoir)', commentaire_validation)

                else:
                    evaluation_reelle.date_validation = datetime.now(timezone.utc)

                    scores = appliquer_cotation_iso(
                        evaluation_reelle, impact_final, probabilite_final, niveau_maitrise_final
                    )

                    score_brut_pour_flash = scores['score_brut']
                    score_net_pour_flash = scores['score_net']
                    niveau_brut_pour_flash = scores['niveau_brut']
                    niveau_net_pour_flash = scores['niveau_net']

                    initialiser_metadonnees(evaluation_reelle)
                    ajouter_historique(
                        evaluation_reelle,
                        'Phase 2 - Validation',
                        f"Statut={statut_validation}, Impact={impact_final}, "
                        f"Proba={probabilite_final}, Maîtrise={niveau_maitrise_final}, "
                        f"BRUT={score_brut_pour_flash}, NET={score_net_pour_flash}"
                    )
                    ajouter_commentaire(evaluation_reelle, 'Validation', commentaire_validation)

                db.session.commit()
                evaluation_en_cours = evaluation_reelle

                if statut_validation == 'a_revoir':
                    flash('⚠️ Évaluation marquée "À revoir". L\'opérateur a été notifié.', 'warning')
                else:
                    flash(
                        f'✅ Évaluation validée '
                        f'(BRUT : {score_brut_pour_flash}/25 [{niveau_brut_pour_flash}] → '
                        f'NET : {score_net_pour_flash}/25 [{niveau_net_pour_flash}])',
                        'success'
                    )

                if rediriger_vers_fiche:
                    return redirect(url_for('detail_risque', id=id))
                return redirect(url_for('evaluer_risque_triphase', id=id))

            # ============================================
            # PHASE 3 — CONFIRMATION
            # ============================================
            elif bouton_soumis == 'submit_phase3':
                _journal("🔄 Phase 3...")

                if not evaluation_reelle:
                    flash('❌ Aucune évaluation. Complétez les Phases 1 et 2.', 'error')
                    return redirect(url_for('evaluer_risque_triphase', id=id))


                if evaluation_reelle.statut_validation == 'a_revoir':
                    _journal("🚫 Confirmation bloquée — éval à revoir")
                    flash('⚠️ Impossible de confirmer : évaluation marquée "À revoir". '
                          'Attendez la correction de l\'opérateur.', 'warning')
                    return redirect(url_for('evaluer_risque_triphase', id=id))

                try:
                    impact_conf = int(request.form.get('impact_conf', 0))
                    probabilite_conf = int(request.form.get('probabilite_conf', 0))
                    niveau_maitrise_conf = int(request.form.get('niveau_maitrise_conf', 0))
                except (ValueError, TypeError):
                    impact_conf = probabilite_conf = niveau_maitrise_conf = 0

                commentaire_confirmation = request.form.get('commentaire_confirmation', '')

                impact_val = evaluation_reelle.impact_val or evaluation_reelle.impact_pre or 0
                probabilite_val = evaluation_reelle.probabilite_val or evaluation_reelle.probabilite_pre or 0
                niveau_maitrise_val = (
                    evaluation_reelle.niveau_maitrise_val or
                    evaluation_reelle.niveau_maitrise_pre or 0
                )

                impact_final = impact_conf if impact_conf > 0 else impact_val
                probabilite_final = probabilite_conf if probabilite_conf > 0 else probabilite_val

                if niveau_maitrise_conf > 0:
                    niveau_maitrise_final = niveau_maitrise_conf
                elif niveau_maitrise_val:
                    niveau_maitrise_final = niveau_maitrise_val
                elif niveau_maitrise_dmr is not None:
                    niveau_maitrise_final = round(niveau_maitrise_dmr)
                else:
                    niveau_maitrise_final = 3

                _journal(f"🎯 Phase 3 — Impact={impact_final}, Proba={probabilite_final}, "
                      f"Maîtrise={niveau_maitrise_final}")

                evaluation_reelle.impact_conf = impact_conf if impact_conf > 0 else None
                evaluation_reelle.probabilite_conf = probabilite_conf if probabilite_conf > 0 else None
                evaluation_reelle.niveau_maitrise_conf = (
                    niveau_maitrise_conf if niveau_maitrise_conf > 0 else niveau_maitrise_final
                )
                evaluation_reelle.evaluateur_final_id = current_user.id
                evaluation_reelle.date_confirmation = datetime.now(timezone.utc)

                if commentaire_confirmation and commentaire_confirmation.strip():
                    evaluation_reelle.commentaire_confirmation = commentaire_confirmation

                evaluation_reelle.updated_at = datetime.now(timezone.utc)

                evaluation_reelle.campagne_nom = campagne_active.nom
                evaluation_reelle.campagne_date_debut = campagne_active.date_debut
                evaluation_reelle.campagne_date_fin = campagne_active.date_fin
                evaluation_reelle.campagne_objectif = campagne_active.description

                scores = appliquer_cotation_iso(
                    evaluation_reelle, impact_final, probabilite_final, niveau_maitrise_final
                )

                score_brut_pour_flash = scores['score_brut']
                score_net_pour_flash = scores['score_net']
                niveau_brut_pour_flash = scores['niveau_brut']
                niveau_net_pour_flash = scores['niveau_net']

                initialiser_metadonnees(evaluation_reelle)
                ajouter_historique(
                    evaluation_reelle,
                    'Phase 3 - Confirmation finale',
                    f"Impact={impact_final}, Proba={probabilite_final}, "
                    f"Maîtrise={niveau_maitrise_final}, "
                    f"BRUT={score_brut_pour_flash}, NET={score_net_pour_flash}, "
                    f"Niveau={niveau_net_pour_flash}"
                )
                ajouter_commentaire(evaluation_reelle, 'Confirmation finale', commentaire_confirmation)

                risque.derniere_evaluation_date = datetime.now(timezone.utc)
                risque.dernier_score_risque = score_net_pour_flash
                risque.dernier_niveau_risque = niveau_net_pour_flash

                db.session.commit()
                evaluation_en_cours = evaluation_reelle

                flash(
                    f'🎉 Évaluation confirmée ! '
                    f'BRUT : {score_brut_pour_flash}/25 ({niveau_brut_pour_flash}) → '
                    f'NET : {score_net_pour_flash}/25 ({niveau_net_pour_flash})',
                    'success'
                )

                return redirect(url_for('detail_risque', id=id))

            else:
                _journal(f"⚠️ Bouton inconnu: {bouton_soumis}")
                flash('Action non reconnue', 'warning')
                return redirect(url_for('evaluer_risque_triphase', id=id))

        except Exception as e:
            db.session.rollback()
            _journal(f"❌ Erreur POST: {e}")
            import traceback
            traceback.print_exc()
            flash(f'❌ Erreur: {str(e)}', 'error')
            return redirect(url_for('evaluer_risque_triphase', id=id))

    # ============================================
    # 9. PHASE ACTUELLE
    # ============================================
    phase_actuelle = 'phase1'
    if evaluation_reelle:
        if evaluation_reelle.date_confirmation:
            phase_actuelle = 'termine'
        elif evaluation_reelle.statut_validation == 'a_revoir':
            phase_actuelle = 'a_revoir'
        elif evaluation_reelle.date_validation:
            phase_actuelle = 'phase3'
        elif evaluation_reelle.date_pre_evaluation:
            phase_actuelle = 'phase2'

    _journal(f"\n🎯 PHASE ACTUELLE: {phase_actuelle}")
    _journal(f"🎯 CAMPAGNE: {campagne_active.nom}")
    _journal(f"🎯 RISQUE: {risque.reference}")
    _journal(f"{'='*70}\n")

    # ============================================
    # 10. PRÉ-REMPLIR LE FORMULAIRE
    # ============================================
    if evaluation_reelle:
        form.referent_pre_evaluation_id.data = evaluation_reelle.referent_pre_evaluation_id or 0
        form.impact_pre.data = evaluation_reelle.impact_pre or 0
        form.probabilite_pre.data = evaluation_reelle.probabilite_pre or 0
        form.niveau_maitrise_pre.data = evaluation_reelle.niveau_maitrise_pre or 0
        form.commentaire_pre_evaluation.data = evaluation_reelle.commentaire_pre_evaluation or ''

    if not evaluation_reelle or not evaluation_reelle.niveau_maitrise_val:
        if niveau_maitrise_dmr is not None:
            try:
                if hasattr(form, 'niveau_maitrise_val'):
                    form.niveau_maitrise_val.data = int(round(niveau_maitrise_dmr))
            except Exception as e:
                _journal(f"⚠️ Pré-remplissage: {e}")

    # ============================================
    # 11. RENDU
    # ============================================
    return render_template(
        'cartographie/evaluation_triphase.html',
        form=form,
        risque=risque,
        dispositifs=dispositifs,
        niveau_maitrise_dmr=niveau_maitrise_dmr,
        stats_dmr=stats_dmr,
        campagne_active=campagne_active,
        evaluation_en_cours=evaluation_en_cours,
        phase_actuelle=phase_actuelle,
        referents=users,
        risques_cartographie=risques_cartographie,
    )


@app.route('/cartographie/<int:id>/nouvelle-campagne', methods=['GET', 'POST'])
@login_required
def nouvelle_campagne_cartographie(id):
    """Créer une nouvelle campagne d'évaluation pour une cartographie"""
    cartographie = Cartographie.query.get_or_404(id)
    
    if not check_client_access(cartographie):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_cartographies'))
    
    if request.method == 'POST':
        nom = request.form.get('nom', '').strip()
        if not nom:
            flash('Le nom de la campagne est obligatoire', 'error')
            return redirect(url_for('nouvelle_campagne_cartographie', id=id))
        
        _journal(f"\n{'='*60}")
        _journal(f"🎯 Création nouvelle campagne: {nom}")
        _journal(f"{'='*60}")
        
        # 1. Clôturer TOUTES les anciennes campagnes en_cours
        anciennes = CampagneEvaluation.query.filter_by(
            cartographie_id=id,
            statut='en_cours'
        ).all()
        
        for ancienne in anciennes:
            ancienne.statut = 'terminee'
            ancienne.date_fin = _aujourdhui()
            _journal(f"✅ Campagne '{ancienne.nom}' (ID={ancienne.id}) clôturée")
        
        # 2. Créer la nouvelle
        nouvelle_campagne = CampagneEvaluation(
            cartographie_id=id,
            nom=nom,
            description=request.form.get('description', ''),
            date_debut=_aujourdhui(),
            statut='en_cours',
            created_by=current_user.id,
            client_id=cartographie.client_id
        )
        db.session.add(nouvelle_campagne)
        db.session.flush()  # Pour obtenir l'ID
        
        # 🔥 POINT CLÉ : mettre à jour le pointeur de la cartographie
        cartographie.campagne_active_id = nouvelle_campagne.id
        cartographie.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        _journal(f"✅ Nouvelle campagne '{nom}' (ID={nouvelle_campagne.id}) créée")
        _journal(f"✅ carto.campagne_active_id → {nouvelle_campagne.id}")
        _journal(f"{'='*60}\n")
        
        flash(f'✅ Campagne "{nom}" créée et activée', 'success')
        return redirect(url_for('detail_cartographie', id=id))
    
    return render_template('cartographie/nouvelle_campagne_cartographie.html', cartographie=cartographie)


@app.route('/cartographie/<int:cartographie_id>/changer-campagne/<int:campagne_id>')
@login_required
def changer_campagne_cartographie(cartographie_id, campagne_id):
    """Changer la campagne active d'une cartographie"""
    from egalyx.commun import jeton_lien_valide
    if not jeton_lien_valide():
        flash("Lien expiré ou invalide : relancez l'action depuis la page.", 'warning')
        return redirect(url_for('detail_cartographie', id=cartographie_id))
    cartographie = Cartographie.query.get_or_404(cartographie_id)
    campagne = CampagneEvaluation.query.get_or_404(campagne_id)
    
    # Vérifier que la campagne appartient à la cartographie
    if campagne.cartographie_id != cartographie_id:
        flash('Cette campagne ne correspond pas à cette cartographie', 'error')
        return redirect(url_for('detail_cartographie', id=cartographie_id))
    
    # Activer cette campagne (et désactiver les autres)
    CampagneEvaluation.query.filter_by(
        cartographie_id=cartographie_id,
        statut='en_cours'
    ).update({'statut': 'terminee'})
    
    campagne.statut = 'en_cours'
    db.session.commit()
    
    flash(f'✅ Campagne "{campagne.nom}" activée', 'success')
    return redirect(url_for('detail_cartographie', id=cartographie_id))


@app.route('/cartographie/<int:cartographie_id>/cloturer-campagne')
@login_required
def cloturer_campagne_cartographie(cartographie_id):
    """Clôturer la campagne active d'une cartographie"""
    from egalyx.commun import jeton_lien_valide
    if not jeton_lien_valide():
        flash("Lien expiré ou invalide : relancez l'action depuis la page.", 'warning')
        return redirect(url_for('detail_cartographie', id=cartographie_id))
    cartographie = Cartographie.query.get_or_404(cartographie_id)
    if not check_client_access(cartographie):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_cartographies'))
    
    campagne_active = CampagneEvaluation.query.filter_by(
        cartographie_id=cartographie_id,
        statut='en_cours'
    ).first()
    
    if not campagne_active:
        flash('Aucune campagne active à clôturer', 'error')
        return redirect(url_for('detail_cartographie', id=cartographie_id))
    
    campagne_active.statut = 'terminee'
    campagne_active.date_fin = _aujourdhui()
    db.session.commit()
    
    flash(f'✅ Campagne "{campagne_active.nom}" clôturée', 'success')
    return redirect(url_for('detail_cartographie', id=cartographie_id))


@app.route('/risque/modifier-reference/<int:id>', methods=['POST'])
@login_required
def modifier_reference_risque(id):
    """Modifier la référence d'un risque"""
    risque = Risque.query.get_or_404(id)
    nouvelle_reference = request.form.get('reference', '').strip()
    
    if nouvelle_reference:
        risque.reference = nouvelle_reference
        db.session.commit()
        flash('Référence modifiée avec succès', 'success')
    else:
        flash('La référence ne peut pas être vide', 'error')
    
    return redirect(url_for('detail_risque', id=id))


@app.route('/risque/<int:id>/nouvelle-campagne', methods=['GET', 'POST'])
@login_required
def nouvelle_campagne_evaluation(id):
    """Démarrer une nouvelle campagne d'évaluation"""
    risque = Risque.query.get_or_404(id)
    
    # Créer un formulaire simple pour la nouvelle campagne
    from flask_wtf import FlaskForm
    from wtforms import StringField, DateField, TextAreaField, SubmitField
    from wtforms.validators import DataRequired
    
    class NouvelleCampagneForm(FlaskForm):
        campagne_nom = StringField('Nom de la campagne', validators=[DataRequired()])
        campagne_date_debut = DateField('Date de début', format='%Y-%m-%d')
        campagne_date_fin = DateField('Date de fin (optionnel)', format='%Y-%m-%d')
        campagne_objectif = TextAreaField('Objectif (optionnel)')
        submit = SubmitField('Créer la campagne')
    
    form = NouvelleCampagneForm()
    
    if request.method == 'POST':
        # Créer une nouvelle évaluation
        evaluation = EvaluationRisque(
            risque_id=id,
            campagne_nom=request.form.get('campagne_nom', ''),
            statut_validation='en_attente',
            created_by=current_user.id
        )
        
        # Si une date de début est fournie
        if request.form.get('campagne_date_debut'):
            evaluation.campagne_date_debut = datetime.strptime(
                request.form.get('campagne_date_debut'), 
                '%Y-%m-%d'
            ).date()
        
        # Si une date de fin est fournie
        if request.form.get('campagne_date_fin'):
            evaluation.campagne_date_fin = datetime.strptime(
                request.form.get('campagne_date_fin'), 
                '%Y-%m-%d'
            ).date()
        
        # Objectif
        evaluation.campagne_objectif = request.form.get('campagne_objectif', '')
        
        db.session.add(evaluation)
        db.session.commit()
        
        flash('✅ Nouvelle campagne d\'évaluation créée', 'success')
        return redirect(url_for('evaluer_risque_triphase', id=id))
    
    return render_template('cartographie/nouvelle_campagne.html', 
                         risque=risque, 
                         form=form)  # AJOUTER form ici


@app.route('/api/risque/<int:risque_id>/kri')
@login_required
def api_kri_risque(risque_id):
    """API pour récupérer les KRI d'un risque spécifique"""
    try:
        risque = Risque.query.get_or_404(risque_id)
        kri = KRI.query.filter_by(risque_id=risque_id).first()
        
        if kri:
            # Récupérer les dernières mesures
            derniere_mesure = MesureKRI.query.filter_by(kri_id=kri.id).order_by(MesureKRI.date_mesure.desc()).first()
            
            kri_data = {
                'existe': True,
                'id': kri.id,
                'nom': kri.nom,
                'description': kri.description,
                'unite_mesure': kri.unite_mesure,
                'frequence_mesure': kri.frequence_mesure,
                'seuil_alerte': kri.seuil_alerte,
                'seuil_critique': kri.seuil_critique,
                'responsable_mesure': kri.responsable_mesure.username if kri.responsable_mesure else None,
                'est_actif': kri.est_actif,
                'derniere_mesure': {
                    'valeur': derniere_mesure.valeur if derniere_mesure else None,
                    'date_mesure': derniere_mesure.date_mesure.isoformat() if derniere_mesure else None,
                    'commentaire': derniere_mesure.commentaire if derniere_mesure else None
                } if derniere_mesure else None,
                'tendance': calculer_tendance_kri(kri.mesures) if kri.mesures else 'stable'
            }
        else:
            kri_data = {
                'existe': False,
                'message': 'Aucun KRI associé à ce risque'
            }
        
        return jsonify({
            'success': True,
            'risque_reference': risque.reference,
            'kri': kri_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/risque/<int:id>/nouvelle-evaluation', methods=['POST'])
@login_required
def nouvelle_evaluation_risque(id):
    """Créer une nouvelle évaluation - DUPLICATION PROPRE"""
    risque = Risque.query.get_or_404(id)
    evaluation_id = request.form.get('evaluation_id')
    
    try:
        campagne_active = get_client_filter(CampagneEvaluation)\
            .filter_by(cartographie_id=risque.cartographie_id, statut='en_cours')\
            .first()
        
        if not campagne_active:
            flash('Aucune campagne active.', 'error')
            return redirect(url_for('detail_risque', id=id))
        
        if evaluation_id:
            evaluation_source = EvaluationRisque.query.get_or_404(evaluation_id)
            
            if not evaluation_source.impact_pre or not evaluation_source.probabilite_pre:
                flash('❌ L\'évaluation source est incomplète.', 'error')
                return redirect(url_for('detail_risque', id=id))
            
            # ✅ CRÉER UNE NOUVELLE ÉVALUATION - UNIQUEMENT Phase 1
            nouvelle_evaluation = EvaluationRisque(
                risque_id=id,
                campagne_id=campagne_active.id,
                campagne_nom=campagne_active.nom,
                campagne_date_debut=campagne_active.date_debut,
                campagne_date_fin=campagne_active.date_fin,
                campagne_objectif=campagne_active.description,
                
                # ✅ UNIQUEMENT Phase 1 - Copier les valeurs
                impact_pre=evaluation_source.impact_pre,
                probabilite_pre=evaluation_source.probabilite_pre,
                niveau_maitrise_pre=evaluation_source.niveau_maitrise_pre,
                commentaire_pre_evaluation=f"🔄 Dupliqué depuis {evaluation_source.campagne_nom or 'évaluation du ' + evaluation_source.created_at.strftime('%d/%m/%Y')}",
                referent_pre_evaluation_id=evaluation_source.referent_pre_evaluation_id,
                date_pre_evaluation=datetime.now(timezone.utc),
                
                # ✅ Phase 2 - TOUT RÉINITIALISER
                impact_val=None,
                probabilite_val=None,
                niveau_maitrise_val=None,
                commentaire_validation='',
                statut_validation='en_attente',
                date_validation=None,
                validateur_id=None,
                
                # ✅ Phase 3 - TOUT RÉINITIALISER (LE PLUS IMPORTANT !)
                impact_conf=None,  # ✅ PAS DE COPIE !
                probabilite_conf=None,  # ✅ PAS DE COPIE !
                niveau_maitrise_conf=None,  # ✅ PAS DE COPIE !
                commentaire_confirmation='',  # ✅ PAS DE COPIE !
                date_confirmation=None,  # ✅ PAS DE COPIE !
                evaluateur_final_id=None,  # ✅ PAS DE COPIE !
                
                # ✅ Recalculer le score avec les valeurs de Phase 1
                score_risque=evaluation_source.impact_pre * evaluation_source.probabilite_pre,
                niveau_risque=calculer_niveau_risque(evaluation_source.impact_pre, evaluation_source.probabilite_pre)[0],
                
                created_by=current_user.id,
                metadonnees={
                    'historique_modifications': [
                        {
                            'date': datetime.now(timezone.utc).isoformat(),
                            'action': 'Duplication',
                            'utilisateur': current_user.username,
                            'details': f'Dupliqué depuis l\'évaluation #{evaluation_source.id}'
                        }
                    ],
                    'commentaires': [
                        {
                            'date': datetime.now(timezone.utc).isoformat(),
                            'phase': 'Duplication',
                            'utilisateur': current_user.username,
                            'commentaire': f'Évaluation dupliquée depuis l\'historique'
                        }
                    ],
                    'source_evaluation_id': evaluation_source.id,
                    'source_campagne': evaluation_source.campagne_nom,
                    'date_duplication': datetime.now(timezone.utc).isoformat()
                }
            )
            
            if current_user.role != 'super_admin' and hasattr(current_user, 'client_id'):
                nouvelle_evaluation.client_id = current_user.client_id
            elif risque.client_id:
                nouvelle_evaluation.client_id = risque.client_id
            elif campagne_active.client_id:
                nouvelle_evaluation.client_id = campagne_active.client_id
            
            db.session.add(nouvelle_evaluation)
            db.session.commit()
            
            flash(f'✅ Nouvelle évaluation créée (campagne: {campagne_active.nom})', 'success')
            return redirect(url_for('evaluer_risque_triphase', id=id))
        
        else:
            flash('💡 Commencez une nouvelle évaluation en remplissant le formulaire', 'info')
            return redirect(url_for('evaluer_risque_triphase', id=id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Erreur: {str(e)}', 'error')
        return redirect(url_for('detail_risque', id=id))


@app.route('/api/evaluation/<int:evaluation_id>/details')
@login_required
def api_details_evaluation(evaluation_id):
    """API pour récupérer les détails d'une évaluation spécifique"""
    evaluation = EvaluationRisque.query.get_or_404(evaluation_id)
    
    return jsonify({
        'success': True,
        'impact_pre': evaluation.impact_pre,
        'probabilite_pre': evaluation.probabilite_pre,
        'niveau_maitrise_pre': evaluation.niveau_maitrise_pre,
        'commentaire_pre_evaluation': evaluation.commentaire_pre_evaluation,
        'impact_val': evaluation.impact_val,
        'probabilite_val': evaluation.probabilite_val,
        'statut_validation': evaluation.statut_validation,
        'commentaire_validation': evaluation.commentaire_validation,
        'impact_conf': evaluation.impact_conf,
        'probabilite_conf': evaluation.probabilite_conf,
        'score_risque': evaluation.score_risque,
        'niveau_risque': evaluation.niveau_risque,
        'date_confirmation': evaluation.date_confirmation.isoformat() if evaluation.date_confirmation else None,
        'url_modification': url_for('evaluer_risque_triphase', id=evaluation.risque_id)
    })


# API pour les données
@app.route('/api/risques/critiques')
@login_required
def api_risques_critiques():
    risques_critiques = []
    for risque in Risque.query.all():
        evaluation = EvaluationRisque.query.filter_by(
            risque_id=risque.id, 
            statut='valide'
        ).order_by(EvaluationRisque.created_at.desc()).first()
        
        if evaluation and evaluation.niveau_risque in ['Élevé', 'Critique']:
            risques_critiques.append({
                'id': risque.id,
                'reference': risque.reference,
                'intitule': risque.intitule,
                'niveau_risque': evaluation.niveau_risque,
                'score': evaluation.score_risque
            })
    
    return jsonify(risques_critiques)


# Routes pour l'administration
@app.route('/risques')
@login_required
def liste_risques():
    """Liste des risques avec isolation multi-tenant et filtres par cartographie/campagne"""
    from sqlalchemy.orm import joinedload
    from sqlalchemy import func
    
    # ========================
    # 1. RÉCUPÉRATION DES FILTRES
    # ========================
    cartographie_id = request.args.get('cartographie_id', type=int)
    campagne_id = request.args.get('campagne_id', type=int)
    filtre_niveau = request.args.get('niveau')
    filtre_statut = request.args.get('statut')
    
    # ========================
    # 2. FILTRE PRINCIPAL
    # ========================
    base_query = get_client_filter(Risque).filter_by(is_archived=False)
    
    # Filtre par cartographie
    if cartographie_id:
        base_query = base_query.filter_by(cartographie_id=cartographie_id)
    
    # ========================
    # 3. SOUS-REQUÊTE POUR LES ÉVALUATIONS PAR CAMPAGNE
    # ========================
    if campagne_id:
        risques_avec_eval_campagne = db.session.query(EvaluationRisque.risque_id)\
            .filter(EvaluationRisque.campagne_id == campagne_id)\
            .subquery()
        
        base_query = base_query.filter(Risque.id.in_(risques_avec_eval_campagne))
    
    # ========================
    # 4. OPTIMISATION DES JOINTURES
    # ========================
    risques_query = base_query\
        .options(
            joinedload(Risque.cartographie),
            joinedload(Risque.createur),
            joinedload(Risque.kri),
            joinedload(Risque.evaluations)
        )\
        .order_by(Risque.reference)
    
    # ========================
    # 5. PAGINATION
    # ========================
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    risques = risques_query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    # ========================
    # 6. STATISTIQUES
    # ========================
    # Sous-requête pour les dernières évaluations
    derniere_eval_subq = db.session.query(
        EvaluationRisque.risque_id,
        func.max(EvaluationRisque.created_at).label('max_date')
    ).group_by(EvaluationRisque.risque_id).subquery()
    
    # Compter les risques critiques
    risques_critiques_query = db.session.query(Risque.id).join(
        EvaluationRisque, Risque.id == EvaluationRisque.risque_id
    ).join(
        derniere_eval_subq,
        (EvaluationRisque.risque_id == derniere_eval_subq.c.risque_id) &
        (EvaluationRisque.created_at == derniere_eval_subq.c.max_date)
    ).filter(
        Risque.is_archived == False,
        EvaluationRisque.niveau_risque == 'Critique'
    )
    
    # Appliquer les mêmes filtres aux stats
    stats_query = get_client_filter(Risque).filter_by(is_archived=False)
    if cartographie_id:
        stats_query = stats_query.filter_by(cartographie_id=cartographie_id)
    
    stats = {
        'total': stats_query.count(),
        'critiques': risques_critiques_query.distinct().count(),
        'avec_evaluations': stats_query.filter(Risque.evaluations.any()).count(),
        'sans_evaluations': stats_query.filter(~Risque.evaluations.any()).count(),
        'avec_kri': stats_query.filter(Risque.kri.has()).count(),
        'sans_kri': stats_query.filter(~Risque.kri.has()).count(),
        'archives': get_client_filter(Risque).filter_by(is_archived=True).count()
    }
    
    # ========================
    # 7. RÉCUPÉRER LES LISTES POUR LES FILTRES
    # ========================
    cartographies = get_client_filter(Cartographie).filter_by(is_archived=False).all()
    
    # Récupérer les campagnes disponibles (si une cartographie est sélectionnée)
    campagnes = []
    if cartographie_id:
        campagnes = CampagneEvaluation.query\
            .filter_by(cartographie_id=cartographie_id)\
            .filter(CampagneEvaluation.statut != 'archivee')\
            .order_by(CampagneEvaluation.date_debut.desc())\
            .all()
    
    # ========================
    # 8. AJOUTER LA DERNIÈRE ÉVALUATION ET INFOS DE CAMPAGNE
    # ========================
    for risque in risques.items:
        # 🔴 CORRECTION : Ne pas assigner directement à la propriété
        # Utiliser une variable temporaire ou un attribut dynamique
        
        # Dernière évaluation globale
        if risque.evaluations:
            risque._derniere_evaluation = max(risque.evaluations, key=lambda x: x.created_at)
        else:
            risque._derniere_evaluation = None
        
        # Si une campagne spécifique est sélectionnée, trouver l'évaluation pour cette campagne
        risque._evaluation_campagne = None
        if campagne_id and risque.evaluations:
            for eval in risque.evaluations:
                if eval.campagne_id == campagne_id:
                    risque._evaluation_campagne = eval
                    break
        
        risque.nb_kri_actifs = 1 if risque.kri and getattr(risque.kri, 'est_actif', True) else 0
    
    # ========================
    # 9. RENDU
    # ========================
    return render_template('risque/liste.html',
                         risques=risques,
                         stats=stats,
                         cartographies=cartographies,
                         campagnes=campagnes,
                         cartographie_id=cartographie_id,
                         campagne_id=campagne_id,
                         filtre_niveau=filtre_niveau,
                         filtre_statut=filtre_statut,
                         page=page,
                         per_page=per_page,
                         current_user=current_user)


@app.route('/evaluation/<int:evaluation_id>/supprimer', methods=['POST'])
@login_required
def supprimer_evaluation_risque(evaluation_id):
    """Supprimer une évaluation - UNIQUEMENT si non confirmée"""
    evaluation = EvaluationRisque.query.get_or_404(evaluation_id)
    risque = evaluation.risque
    
    # Vérifier l'accès
    if not check_client_access(risque):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('dashboard'))
    
    # ✅ Vérifier les permissions
    if not (current_user.has_permission('can_manage_risks') or 
            current_user.id == evaluation.created_by):
        flash('Vous n\'avez pas la permission de supprimer cette évaluation', 'error')
        return redirect(url_for('detail_risque', id=risque.id))
    
    # ✅ NE PAS SUPPRIMER UNE ÉVALUATION CONFIRMÉE
    if evaluation.date_confirmation:
        flash('❌ Impossible de supprimer une évaluation confirmée', 'error')
        return redirect(url_for('detail_risque', id=risque.id))
    
    try:
        # ✅ Supprimer l'évaluation
        db.session.delete(evaluation)
        db.session.commit()
        flash('✅ Évaluation supprimée avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Erreur lors de la suppression: {str(e)}', 'error')
    
    return redirect(url_for('detail_risque', id=risque.id))


@app.route('/risque/<int:id>')
@login_required
def detail_risque(id):
    """
    Page de détail d'un risque — avec accès sécurisés aux colonnes ISO.
    """
    from datetime import datetime
    # (règle unique : calculer_scores_risque et calculer_maitrise_depuis_dmr viennent de app.py / cotation.py)

    # ============================================
    # 1. FILTRE MULTI-TENANT
    # ============================================
    if current_user.role == 'super_admin' and session.get('viewing_client_id'):
        client_id = session['viewing_client_id']
    else:
        client_id = current_user.client_id

    # ============================================
    # 2. RÉCUPÉRATION DU RISQUE
    # ============================================
    risque = Risque.query.filter_by(
        id=id,
        client_id=client_id
    ).first_or_404()

    if risque.is_archived:
        flash('Ce risque est archivé', 'warning')
        return redirect(url_for('risques_archives'))

    # Vérification des permissions
    if not (current_user.has_permission('can_manage_risks') or
            risque.created_by == current_user.id or
            current_user.id in [e.evaluateur_final_id for e in risque.evaluations if e and e.evaluateur_final_id] or
            current_user.id in [e.validateur_id for e in risque.evaluations if e and e.validateur_id]):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('dashboard'))

    _journal(f"\n{'='*70}")
    _journal(f"🔍 detail_risque — Risque {risque.reference} (ID={id})")
    _journal(f"{'='*70}")

    # ============================================
    # 3. CHAMPS PERSONNALISÉS
    # ============================================
    champs_personnalises = []
    for champ in risque.champs_personnalises:
        config = ConfigurationChampRisque.query.filter_by(
            nom_technique=champ.nom_technique,
            client_id=client_id
        ).first()
        champ.config = config
        champs_personnalises.append(champ)

    fichiers = FichierRisque.query.filter_by(
        risque_id=id,
        client_id=client_id
    ).order_by(FichierRisque.created_at.desc()).all()

    champs_disponibles = ConfigurationChampRisque.query.filter_by(
        est_actif=True,
        client_id=client_id
    ).order_by('section', 'ordre_affichage').all()

    champs_deja_ajoutes = [c.nom_technique for c in risque.champs_personnalises]
    champs_disponibles = [
        c for c in champs_disponibles
        if c.nom_technique not in champs_deja_ajoutes
    ]

    config_fichiers = {
        'extensions': list(app.config.get('ALLOWED_EXTENSIONS',
                                          {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'png'})),
        'taille_max_mo': app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024) / (1024 * 1024),
        'categories': ['document', 'image', 'analyse', 'autre']
    }

    champs_par_section = {
        'general': [],
        'analyse': [],
        'evaluation': [],
        'documentation': [],
        'personnalise': []
    }

    for champ in champs_personnalises:
        if champ.config and champ.config.section in champs_par_section:
            champs_par_section[champ.config.section].append(champ)
        else:
            champs_par_section['personnalise'].append(champ)

    # ============================================
    # 4. DISPOSITIFS DE MAÎTRISE
    # ============================================
    try:
        dispositifs = DispositifMaitrise.query.filter_by(
            risque_id=id,
            is_archived=False,
            client_id=client_id
        ).order_by(DispositifMaitrise.reference.asc()).all()
    except Exception as e:
        _journal(f"⚠️ Table dispositifs_maitrise non disponible: {e}")
        dispositifs = []

    # ============================================
    # 5. CAMPAGNE ACTIVE
    # ============================================
    carto = Cartographie.query.get(risque.cartographie_id)
    campagne_active = None

    if carto and carto.campagne_active_id:
        campagne_candidate = CampagneEvaluation.query.get(carto.campagne_active_id)
        if campagne_candidate and campagne_candidate.statut != 'archivee':
            campagne_active = campagne_candidate

    if not campagne_active:
        campagne_active = CampagneEvaluation.query\
            .filter_by(cartographie_id=risque.cartographie_id, statut='en_cours')\
            .order_by(CampagneEvaluation.created_at.desc())\
            .first()

    _journal(f"📌 Campagne active: {campagne_active.nom if campagne_active else 'Aucune'}")

    # ============================================
    # 6. FILTRE CAMPAGNE
    # ============================================
    campagne_filter_id = request.args.get('campagne_id', type=int)

    # ============================================
    # 7. RÉCUPÉRATION DES ÉVALUATIONS
    # ============================================
    toutes_evaluations = EvaluationRisque.query\
        .filter_by(risque_id=id, client_id=client_id)\
        .order_by(EvaluationRisque.created_at.desc())\
        .all()

    toutes_evaluations = [e for e in toutes_evaluations if e is not None]
    _journal(f"📌 Total évals: {len(toutes_evaluations)}")

    # ============================================
    # 8. ÉVALUATION À AFFICHER
    # ============================================
    derniere_evaluation = None
    evaluation_campagne_active = None
    evaluation_anterieure = None

    for ev in toutes_evaluations:
        if campagne_active and ev.campagne_id == campagne_active.id:
            if not evaluation_campagne_active:
                evaluation_campagne_active = ev
        elif ev.date_confirmation and not evaluation_anterieure:
            evaluation_anterieure = ev

    if campagne_filter_id:
        for ev in toutes_evaluations:
            if ev.campagne_id == campagne_filter_id:
                derniere_evaluation = ev
                break
    else:
        derniere_evaluation = evaluation_campagne_active or evaluation_anterieure

    if derniere_evaluation:
        _journal(f"📌 Éval affichée: ID={derniere_evaluation.id}")

    # ============================================
    # 9. CALCUL DES SCORES (AVEC ACCÈS SÉCURISÉS)
    # ============================================
    impact_final = None
    probabilite_final = None
    niveau_maitrise_final = None
    score_final = None
    niveau_risque_final = None
    score_brut_final = None
    niveau_brut_final = None
    score_net_final = None
    niveau_net_final = None
    taux_reduction_final = 0.0
    probabilite_ajustee_final = None
    niveau_maitrise_dmr = None
    ecart_maitrise = None
    campagne_info = None
    statut_evaluation = 'non_evalue'

    if derniere_evaluation:
        impact_final = (
            derniere_evaluation.impact_conf
            or derniere_evaluation.impact_val
            or derniere_evaluation.impact_pre
        )
        probabilite_final = (
            derniere_evaluation.probabilite_conf
            or derniere_evaluation.probabilite_val
            or derniere_evaluation.probabilite_pre
        )
        niveau_maitrise_final = (
            derniere_evaluation.niveau_maitrise_conf
            or derniere_evaluation.niveau_maitrise_val
            or derniere_evaluation.niveau_maitrise_pre
        )

        if impact_final and probabilite_final and impact_final > 0 and probabilite_final > 0:
            try:
                scores = calculer_scores_risque(
                    impact_final, probabilite_final, niveau_maitrise_final
                )
                score_brut_final = scores['score_brut']
                niveau_brut_final = scores['niveau_brut']
                score_net_final = scores['score_net']
                niveau_net_final = scores['niveau_net']
                taux_reduction_final = scores['taux_reduction']
                probabilite_ajustee_final = scores['probabilite_ajustee']

                score_final = score_net_final
                niveau_risque_final = niveau_net_final
            except Exception as e:
                _journal(f"⚠️ Erreur calcul ISO: {e}")
                score_brut_final = impact_final * probabilite_final
                score_net_final = score_brut_final
                score_final = score_brut_final
                niveau_risque_final = _qualifier_score_basique(score_final)
                niveau_brut_final = niveau_risque_final
                niveau_net_final = niveau_risque_final

        # DMR avec accès sécurisé
        try:
            niveau_maitrise_dmr = calculer_maitrise_depuis_dmr(dispositifs)
            if niveau_maitrise_dmr is not None and niveau_maitrise_final:
                ecart_maitrise = abs(
                    float(niveau_maitrise_final) - float(niveau_maitrise_dmr)
                )
        except Exception as e:
            _journal(f"⚠️ Erreur calcul DMR: {e}")

        # Campagne info
        campagne_info = {
            'nom': derniere_evaluation.campagne_nom,
            'date_debut': derniere_evaluation.campagne_date_debut,
            'date_fin': derniere_evaluation.campagne_date_fin,
            'objectif': derniere_evaluation.campagne_objectif
        }

        # Statut
        if derniere_evaluation.date_confirmation:
            statut_evaluation = 'termine'
        elif derniere_evaluation.statut_validation == 'a_revoir':
            statut_evaluation = 'a_revoir'
        elif derniere_evaluation.date_validation:
            statut_evaluation = 'valide'
        elif derniere_evaluation.impact_pre:
            statut_evaluation = 'pre_evalue'

    # ============================================
    # 10. DÉTECTION RÉÉVALUATION (SÉCURISÉ)
    # ============================================
    est_revaluation = (
        evaluation_campagne_active is None
        and evaluation_anterieure is not None
    )
    score_n_moins_1 = None
    niveau_n_moins_1 = None

    if evaluation_anterieure:
        # 🔥 UTILISATION DES PROPRIÉTÉS SAFE
        score_n_moins_1 = evaluation_anterieure.score_net_safe
        niveau_n_moins_1 = evaluation_anterieure.niveau_net_safe

    # ============================================
    # 11. LISTE DES CAMPAGNES
    # ============================================
    campagnes_disponibles = CampagneEvaluation.query\
        .filter_by(cartographie_id=risque.cartographie_id)\
        .order_by(CampagneEvaluation.created_at.desc())\
        .all()

    # ============================================
    # 12. ÉVALUATIONS À AFFICHER (HISTORIQUE)
    # ============================================
    evaluations_a_afficher = []
    for ev in toutes_evaluations:
        if ev is None:
            continue
        phase1_complete = (
            ev.impact_pre is not None and ev.impact_pre > 0 and
            ev.probabilite_pre is not None and ev.probabilite_pre > 0
        )
        phase_avancee = (
            ev.date_validation is not None or
            ev.date_confirmation is not None or
            ev.statut_validation == 'a_revoir'
        )
        if phase1_complete or phase_avancee:
            evaluations_a_afficher.append(ev)

    evaluations_a_afficher.sort(
        key=lambda x: x.created_at or datetime.min,
        reverse=True
    )

    # ============================================
    # 13. KRI
    # ============================================
    kris = KRI.query.filter_by(
        risque_id=id,
        client_id=client_id
    ).order_by(KRI.created_at.desc()).all()

    # ============================================
    # 14. LISTES DÉROULANTES
    # ============================================
    categories_liste = ConfigurationListeDeroulante.query.filter_by(
        nom_technique='categories_risque',
        client_id=client_id
    ).first()

    types_risque_liste = ConfigurationListeDeroulante.query.filter_by(
        nom_technique='types_risque',
        client_id=client_id
    ).first()

    # ============================================
    # 15. PERMISSION MODIFICATION
    # ============================================
    peut_modifier_evaluation = False
    if derniere_evaluation:
        peut_modifier_evaluation = (
            current_user.has_permission('can_manage_risks') or
            current_user.id == derniere_evaluation.created_by or
            (derniere_evaluation.referent_pre_evaluation_id and
             current_user.id == derniere_evaluation.referent_pre_evaluation_id) or
            (derniere_evaluation.validateur_id and
             current_user.id == derniere_evaluation.validateur_id) or
            (derniere_evaluation.evaluateur_final_id and
             current_user.id == derniere_evaluation.evaluateur_final_id)
        )

    # ============================================
    # 16. RENDU
    # ============================================
    return render_template(
        'cartographie/risque_detail.html',
        risque=risque,
        derniere_evaluation=derniere_evaluation,
        evaluation_campagne_active=evaluation_campagne_active,
        evaluation_anterieure=evaluation_anterieure,
        est_revaluation=est_revaluation,
        score_n_moins_1=score_n_moins_1,
        niveau_n_moins_1=niveau_n_moins_1,
        toutes_evaluations=evaluations_a_afficher,
        historique_evaluations=evaluations_a_afficher,
        kris=kris,
        campagne_info=campagne_info,
        statut_evaluation=statut_evaluation,
        peut_modifier_evaluation=peut_modifier_evaluation,

        # Filtrage
        campagne_active=campagne_active,
        campagne_filter_id=campagne_filter_id,
        campagnes_disponibles=campagnes_disponibles,

        # Valeurs calculées ISO
        impact_final=impact_final,
        probabilite_final=probabilite_final,
        niveau_maitrise_final=niveau_maitrise_final,
        score_final=score_final,
        niveau_risque_final=niveau_risque_final,
        score_brut_final=score_brut_final,
        niveau_brut_final=niveau_brut_final,
        score_net_final=score_net_final,
        niveau_net_final=niveau_net_final,
        taux_reduction_final=taux_reduction_final,
        probabilite_ajustee_final=probabilite_ajustee_final,
        niveau_maitrise_dmr=niveau_maitrise_dmr,
        ecart_maitrise=ecart_maitrise,

        # Champs personnalisés
        champs_personnalises=champs_personnalises,
        champs_par_section=champs_par_section,
        fichiers=fichiers,
        champs_disponibles=champs_disponibles,
        config_fichiers=config_fichiers,
        categories_liste=categories_liste,
        types_risque_liste=types_risque_liste,

        # Dispositifs
        dispositifs=dispositifs,

        # Utilitaires
        datetime=datetime,
        client_id=client_id,
        current_user=current_user
    )


@app.route('/api/evaluation/<int:evaluation_id>/details')
@login_required
def api_evaluation_details(evaluation_id):
    """API pour récupérer les détails d'une évaluation"""
    evaluation = EvaluationRisque.query.get_or_404(evaluation_id)
    
    if not check_client_access(evaluation.risque):
        return jsonify({'success': False, 'error': 'Accès non autorisé'}), 403
    
    # ✅ Récupérer le nom de l'évaluateur final
    evaluateur_nom = None
    if evaluation.evaluateur_final:
        evaluateur_nom = evaluation.evaluateur_final.username
    
    return jsonify({
        'success': True,
        # Phase 1
        'impact_pre': evaluation.impact_pre,
        'probabilite_pre': evaluation.probabilite_pre,
        'niveau_maitrise_pre': evaluation.niveau_maitrise_pre,
        'commentaire_pre_evaluation': evaluation.commentaire_pre_evaluation,
        'date_pre_evaluation': evaluation.date_pre_evaluation.isoformat() if evaluation.date_pre_evaluation else None,
        'referent_pre_evaluation_nom': evaluation.referent_pre_evaluation.username if evaluation.referent_pre_evaluation else None,
        
        # Phase 2
        'impact_val': evaluation.impact_val,
        'probabilite_val': evaluation.probabilite_val,
        'niveau_maitrise_val': evaluation.niveau_maitrise_val,
        'commentaire_validation': evaluation.commentaire_validation,
        'statut_validation': evaluation.statut_validation,
        'date_validation': evaluation.date_validation.isoformat() if evaluation.date_validation else None,
        'validateur_nom': evaluation.validateur.username if evaluation.validateur else None,
        
        # ✅ Phase 3 - CORRIGÉ : envoyer les bonnes valeurs
        'impact_conf': evaluation.impact_conf,  # ✅ 5
        'probabilite_conf': evaluation.probabilite_conf,  # ✅ 5
        'niveau_maitrise_conf': evaluation.niveau_maitrise_conf,
        'commentaire_confirmation': evaluation.commentaire_confirmation,  # ✅ "propre Dieu"
        'date_confirmation': evaluation.date_confirmation.isoformat() if evaluation.date_confirmation else None,
        'evaluateur_final_nom': evaluateur_nom,  # ✅ "admin_madoodds"
        
        # Résultats
        'score_risque': evaluation.score_risque,  # ✅ 25
        'niveau_risque': evaluation.niveau_risque,  # ✅ "Critique"
    })


# ============================================
# ROUTES IA - ANALYSE INTELLIGENTE
# ============================================
@app.route('/cartographie/<int:cartographie_id>/ajouter-risque-suggere', methods=['POST'])
@login_required
def ajouter_risque_suggere(cartographie_id):
    """Ajouter un risque suggéré par l'IA - CORRIGÉ"""
    from models import Cartographie, Risque
    
    cartographie = Cartographie.query.get_or_404(cartographie_id)
    
    if not check_client_access(cartographie):
        return jsonify({'success': False, 'error': 'Accès non autorisé'}), 403
    
    # ✅ Récupérer les données (depuis FormData)
    reference = request.form.get('reference')
    intitule = request.form.get('intitule')
    description = request.form.get('description')
    categorie = request.form.get('categorie')
    type_risque = request.form.get('type_risque', 'residuel')
    impact_propose = request.form.get('impact_propose', 3)
    probabilite_propose = request.form.get('probabilite_propose', 3)
    
    # ✅ Vérifier les données
    _journal(f"📥 Réception: reference={reference}, intitule={intitule}, categorie={categorie}")
    
    if not reference or not intitule:
        return jsonify({'success': False, 'error': 'Référence et intitulé requis'}), 400
    
    # Vérifier si la référence existe déjà
    existant = Risque.query.filter_by(
        cartographie_id=cartographie_id,
        reference=reference,
        client_id=current_user.client_id
    ).first()
    
    if existant:
        return jsonify({'success': False, 'error': f'Le risque {reference} existe déjà'}), 400
    
    try:
        nouveau_risque = Risque(
            reference=reference,
            intitule=intitule,
            description=description or '',
            categorie=categorie or 'Général',
            type_risque=type_risque,
            cartographie_id=cartographie_id,
            client_id=current_user.client_id,
            created_by=current_user.id
        )
        
        db.session.add(nouveau_risque)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'✅ Risque {reference} ajouté avec succès',
            'risque_id': nouveau_risque.id,
            'reference': nouveau_risque.reference
        })
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cartographie/<int:cartographie_id>/ajouter-tous-risques-suggeres', methods=['POST'])
@login_required
def api_ajouter_tous_risques_suggeres(cartographie_id):
    """Ajouter tous les risques suggérés par l'IA en une fois"""
    from models import Cartographie, Risque
    
    cartographie = Cartographie.query.get_or_404(cartographie_id)
    
    if not check_client_access(cartographie):
        return jsonify({'success': False, 'error': 'Accès non autorisé'}), 403
    
    data = request.get_json()
    risques = data.get('risques', [])
    
    if not risques:
        return jsonify({'success': False, 'error': 'Aucun risque à ajouter'}), 400
    
    ajoutes = []
    erreurs = []
    
    for risque_data in risques:
        reference = risque_data.get('reference')
        intitule = risque_data.get('intitule')
        description = risque_data.get('description')
        categorie = risque_data.get('categorie')
        type_risque = risque_data.get('type_risque', 'residuel')
        
        if not reference or not intitule:
            erreurs.append(f"Risque sans référence ou intitulé")
            continue
        
        # Vérifier si la référence existe déjà
        existant = Risque.query.filter_by(
            cartographie_id=cartographie_id,
            reference=reference,
            client_id=current_user.client_id
        ).first()
        
        if existant:
            erreurs.append(f"Le risque {reference} existe déjà")
            continue
        
        try:
            nouveau_risque = Risque(
                reference=reference,
                intitule=intitule,
                description=description,
                categorie=categorie,
                type_risque=type_risque,
                cartographie_id=cartographie_id,
                client_id=current_user.client_id,
                created_by=current_user.id
            )
            
            db.session.add(nouveau_risque)
            ajoutes.append(reference)
            
        except Exception as e:
            erreurs.append(f"{reference}: {str(e)}")
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    
    return jsonify({
        'success': True,
        'ajoutes': ajoutes,
        'erreurs': erreurs,
        'message': f"{len(ajoutes)} risque(s) ajouté(s), {len(erreurs)} erreur(s)"
    })


@app.route('/cartographie/<int:id>/analyse-ia-ultra')
@login_required
def analyse_ia_ultra(id):
    """Analyse IA Ultra - Système hybride complet"""
    from models import Cartographie, Risque, EvaluationRisque, DispositifMaitrise, Incident
    from models import DemandeReevaluation, Constatation
    try:
        from services.analyse_hybride import AnalyseHybrideService
    except ImportError:
        flash("Le service d'analyse IA (services/analyse_hybride.py) n'est pas installé sur ce serveur.", 'warning')
        return redirect(url_for('detail_cartographie', id=id))
    
    cartographie = Cartographie.query.get_or_404(id)
    
    if not check_client_access(cartographie):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_cartographies'))
    
    client_id = current_user.client_id if current_user.role != 'super_admin' else cartographie.client_id
    
    # ============================================================
    # 1. RÉCUPÉRER TOUTES LES DONNÉES
    # ============================================================
    
    risques = Risque.query.filter_by(
        cartographie_id=id,
        is_archived=False,
        client_id=client_id
    ).all()
    
    evaluations = EvaluationRisque.query.join(
        Risque, EvaluationRisque.risque_id == Risque.id
    ).filter(
        Risque.cartographie_id == id,
        Risque.is_archived == False,
        Risque.client_id == client_id
    ).all()
    
    dispositifs = DispositifMaitrise.query.join(
        Risque, DispositifMaitrise.risque_id == Risque.id
    ).filter(
        Risque.cartographie_id == id,
        Risque.is_archived == False,
        Risque.client_id == client_id,
        DispositifMaitrise.is_archived == False
    ).all()
    
    incidents = Incident.query.filter(
        Incident.risque_id.in_([r.id for r in risques]),
        Incident.is_archived == False
    ).all()
    
    demandes_reevaluation = DemandeReevaluation.query.filter(
        DemandeReevaluation.risque_id.in_([r.id for r in risques])
    ).all()
    
    constats_audit = Constatation.query.filter(
        Constatation.risque_id.in_([r.id for r in risques])
    ).all()
    
    # ============================================================
    # 2. LANCER L'ANALYSE HYBRIDE
    # ============================================================
    
    resultat = AnalyseHybrideService.analyser_complet(
        cartographie=cartographie,
        risques=risques,
        evaluations=evaluations,
        dispositifs=dispositifs,
        incidents=incidents,
        demandes_reevaluation=demandes_reevaluation,
        constats_audit=constats_audit
    )
    
    # ============================================================
    # 3. STATISTIQUES POUR LE TEMPLATE
    # ============================================================
    
    # Risques évalués = risques DISTINCTS ayant au moins une évaluation confirmée
    # (avant : nombre d'évaluations, qui dépassait 100 % dès la 2e campagne)
    risques_evalues = {e.risque_id for e in evaluations if e.date_confirmation}
    stats = {
        'risques_total': len(risques),
        'risques_evalues': len(risques_evalues),
        'dispositifs_total': len(dispositifs),
        'incidents_recents': len([i for i in incidents if i.date_occurrence and i.date_occurrence >= datetime.now() - timedelta(days=365)]),
        'taux_evaluation': int(len(risques_evalues) / len(risques) * 100) if risques else 0,
        'taux_couverture': int((len(set([d.risque_id for d in dispositifs])) / len(risques) * 100) if risques else 0)
    }
    
    campagne_active = cartographie.get_campagne_active()
    
    return render_template('cartographie/analyse_ia_ultra.html',
                         cartographie=cartographie,
                         campagne_active=campagne_active,
                         stats=stats,
                         resultat_ia=resultat,
                         now=datetime.now)


@app.route('/cartographie/<int:id>/analyse-ia/export')
@login_required
def export_analyse_ia(id):
    """Export de l'analyse IA : ouvre la page d'analyse en mode impression (« Enregistrer en PDF »)."""
    return redirect(url_for('analyse_ia_cartographie', id=id, imprimer=1))


@app.route('/cartographie/<int:cartographie_id>/plans-action')
@login_required
def plans_action_cartographie(cartographie_id):
    """Liste des plans d'action liés à une cartographie"""
    from models import Cartographie, PlanAction, Risque
    
    cartographie = Cartographie.query.get_or_404(cartographie_id)
    
    if not check_client_access(cartographie):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_cartographies'))
    
    client_id = current_user.client_id if current_user.role != 'super_admin' else cartographie.client_id
    
    # Récupérer les plans d'action via les risques de la cartographie
    plans_action = PlanAction.query\
        .join(Risque, PlanAction.risque_id == Risque.id)\
        .filter(
            Risque.cartographie_id == cartographie_id,
            Risque.is_archived == False,
            PlanAction.is_archived == False,
            PlanAction.client_id == client_id
        )\
        .order_by(PlanAction.created_at.desc())\
        .all()
    
    # Statistiques
    stats = {
        'total': len(plans_action),
        'en_cours': len([p for p in plans_action if p.statut == 'en_cours']),
        'termines': len([p for p in plans_action if p.statut == 'termine']),
        'en_retard': len([p for p in plans_action if p.statut == 'en_cours' and p.date_fin_prevue and p.date_fin_prevue < _aujourdhui()])
    }
    
    return render_template('cartographie/plans_action.html',
                         cartographie=cartographie,
                         plans_action=plans_action,
                         stats=stats,
                         now=datetime.now)


@app.route('/cartographie/<int:id>/analyse-ia')
@login_required
def analyse_ia_cartographie(id):
    """Page d'analyse IA pour une cartographie"""
    from models import Cartographie, Risque, EvaluationRisque, DispositifMaitrise, Incident, PlanAction
    from datetime import datetime, timedelta
    from services.ia_cartographie_service import IACartographieService
    
    cartographie = Cartographie.query.get_or_404(id)
    
    if not check_client_access(cartographie):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_cartographies'))
    
    # Récupérer les données
    client_id = current_user.client_id if current_user.role != 'super_admin' else cartographie.client_id
    
    # 1. Récupérer les risques
    risques = Risque.query.filter_by(
        cartographie_id=id,
        is_archived=False,
        client_id=client_id
    ).all()
    
    total_risques = len(risques)
    
    # 2. Évaluations
    evaluations = EvaluationRisque.query.join(
        Risque, EvaluationRisque.risque_id == Risque.id
    ).filter(
        Risque.cartographie_id == id,
        Risque.is_archived == False,
        Risque.client_id == client_id
    ).all()
    
    risques_evalues = len([e for e in evaluations if e.date_confirmation])
    taux_evaluation = int((risques_evalues / total_risques * 100) if total_risques > 0 else 0)
    
    # 3. Dispositifs
    dispositifs = DispositifMaitrise.query.join(
        Risque, DispositifMaitrise.risque_id == Risque.id
    ).filter(
        Risque.cartographie_id == id,
        Risque.is_archived == False,
        Risque.client_id == client_id,
        DispositifMaitrise.is_archived == False
    ).all()
    
    total_dispositifs = len(dispositifs)
    dispositifs_efficaces = len([d for d in dispositifs if d.efficacite_reelle and d.efficacite_reelle >= 4])
    
    # 4. Risques critiques
    risques_critiques = []
    risques_avec_niveau = []
    distribution_niveaux = {}
    
    for r in risques:
        eval = EvaluationRisque.query.filter_by(risque_id=r.id).order_by(EvaluationRisque.created_at.desc()).first()
        if eval and eval.niveau_risque:
            distribution_niveaux[eval.niveau_risque] = distribution_niveaux.get(eval.niveau_risque, 0) + 1
            risques_avec_niveau.append(r)
            if eval.niveau_risque == 'Critique':
                risques_critiques.append(r)
    
    # 5. Catégories
    categories = {}
    for r in risques:
        if r.categorie:
            categories[r.categorie] = categories.get(r.categorie, 0) + 1
    
    # 6. Types
    types = {}
    for r in risques:
        if r.type_risque:
            types[r.type_risque] = types.get(r.type_risque, 0) + 1
    
    # 7. Incidents récents
    date_limite = datetime.now() - timedelta(days=365)
    incidents = Incident.query.filter(
        Incident.risque_id.in_([r.id for r in risques]),
        Incident.date_occurrence >= date_limite,
        Incident.is_archived == False
    ).all()
    
    # 8. Plans d'action
    plans_action = PlanAction.query\
        .join(Risque, PlanAction.risque_id == Risque.id)\
        .filter(
            Risque.cartographie_id == id,
            Risque.is_archived == False,
            PlanAction.is_archived == False,
            PlanAction.client_id == client_id
        )\
        .count()
    
    # 9. Préparer les données pour l'IA
    cartographie_data = {
        'nom': cartographie.nom,
        'description': cartographie.description,
        'total_risques': total_risques,
        'risques_evalues': risques_evalues,
        'taux_evaluation': taux_evaluation,
        'total_dispositifs': total_dispositifs,
        'taux_couverture': int((total_dispositifs / total_risques * 100) if total_risques > 0 else 0),
        'incidents_recents': len(incidents),
        'distribution_niveaux': distribution_niveaux,
        'categories': categories,
        'types': types,
        'risques_critiques': [{'reference': r.reference, 'intitule': r.intitule} for r in risques_critiques]
    }
    
    # 10. Appeler le service IA
    resultat_ia = IACartographieService.analyser_cartographie(cartographie_data)
    
    stats = {
        'risques_total': total_risques,
        'risques_evalues': risques_evalues,
        'risques_a_evaluer': total_risques - risques_evalues,
        'dispositifs_total': total_dispositifs,
        'dispositifs_efficaces': dispositifs_efficaces,
        'taux_evaluation': taux_evaluation,
        'taux_couverture': int((total_dispositifs / total_risques * 100) if total_risques > 0 else 0),
        'risques_sans_dispositif': total_risques - len(set([d.risque_id for d in dispositifs])),
        'incidents_recents': len(incidents),
        'plans_action': plans_action
    }
    
    # Récupérer la campagne active
    campagne_active = cartographie.get_campagne_active()
    
    # Extraire les suggestions et le score
    suggestions = resultat_ia.get('suggestions', [])
    score_global = resultat_ia.get('score_global', {
        'score': 0,
        'niveau': 'faible',
        'niveau_label': 'Faible',
        'message': 'Analyse en cours...'
    })
    risques_proposes = resultat_ia.get('risques_proposes', [])
    
    return render_template('cartographie/analyse_ia.html',
                         cartographie=cartographie,
                         campagne_active=campagne_active,
                         stats=stats,
                         suggestions=suggestions,
                         score_global=score_global,
                         total_risques=total_risques,
                         distribution_niveaux=distribution_niveaux,
                         risques_critiques=risques_critiques,
                         categories=categories,
                         types=types,
                         risques_proposes=risques_proposes,
                         now=datetime.now)


@app.route('/api/risque/<int:risque_id>/associer-processus', methods=['POST'])
@login_required
def api_associer_risque_processus_route(risque_id):
    """Associer un risque à un processus"""
    from models import Risque, ProcessusMetier
    
    risque = get_client_filter(Risque).filter_by(id=risque_id, is_archived=False).first_or_404()
    
    data = request.get_json()
    processus_id = data.get('processus_id')
    
    if not processus_id:
        return jsonify({'success': False, 'error': 'ID du processus requis'}), 400
    
    processus = get_client_filter(ProcessusMetier).filter_by(id=processus_id).first_or_404()
    
    risque.processus_metier_associe_id = processus_id
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Risque associé au processus'})


@app.route('/api/risque/<int:risque_id>/dissocier-processus', methods=['POST'])
@login_required
def api_dissocier_risque_processus_route(risque_id):
    """Dissocier un risque de son processus"""
    from models import Risque
    
    risque = get_client_filter(Risque).filter_by(id=risque_id, is_archived=False).first_or_404()
    
    risque.processus_metier_associe_id = None
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Risque dissocié du processus'})


@app.route('/risque/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_risque(id):
    """Modifier un risque existant"""
    risque = Risque.query.get_or_404(id)
    
    # Vérifier les permissions
    if not (current_user.has_permission('can_manage_risks') or 
            risque.created_by == current_user.id):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('dashboard'))
    
    form = RisqueForm(obj=risque)
    
    # Récupérer les configurations de listes déroulantes
    categories_liste = get_client_filter(ConfigurationListeDeroulante).filter_by(
        nom_technique='categorie'
    ).first()
    
    types_risque_liste = get_client_filter(ConfigurationListeDeroulante).filter_by(
        nom_technique='type_risque'
    ).first()
    
    # Récupérer les champs configurés (cloisonnement par organisation)
    champs_configures = get_client_filter(ConfigurationChampRisque).filter_by(
        est_actif=True
    ).order_by('section', 'ordre_affichage').all()
    
    # Récupérer les valeurs existantes des champs personnalisés
    valeurs_existantes = {}
    for champ in risque.champs_personnalises:
        valeurs_existantes[champ.nom_technique] = champ.get_valeur()
    
    # Configuration fichiers pour le template
    config_fichiers = {
        'extensions': list(app.config.get('ALLOWED_EXTENSIONS', {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'png', 'txt'})),
        'taille_max_mo': app.config.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024) // (1024 * 1024),
        'categories': ['document', 'image', 'analyse', 'autre']
    }
    
    if form.validate_on_submit():
        # Mettre à jour les champs de base
        risque.intitule = form.intitule.data
        risque.description = form.description.data
        risque.processus_concerne = form.processus_concerne.data
        
        # Mettre à jour les listes déroulantes
        if categories_liste:
            risque.categorie = request.form.get('categorie', '')
        else:
            risque.categorie = form.categorie.data
            
        if types_risque_liste:
            risque.type_risque = request.form.get('type_risque', '')
        else:
            risque.type_risque = form.type_risque.data
            
        risque.cause_racine = form.cause_racine.data
        risque.consequences = form.consequences.data
        
        # Gérer les champs personnalisés
        for champ in champs_configures:
            field_name = f'champ_{champ.nom_technique}'
            fichier_name = f'fichier_{champ.nom_technique}'
            
            if champ.type_champ == 'fichier':
                # Gestion des fichiers
                if fichier_name in request.files:
                    fichier = request.files[fichier_name]
                    if fichier and fichier.filename:
                        # Supprimer l'ancien fichier si demandé
                        if request.form.get(f'supprimer_fichier_{champ.nom_technique}') == 'true':
                            ancien_champ = ChampPersonnaliseRisque.query.filter_by(
                                risque_id=risque.id,
                                nom_technique=champ.nom_technique
                            ).first()
                            if ancien_champ and ancien_champ.get_valeur():
                                # Supprimer le fichier physique
                                chemin_fichier = os.path.join(
                                    app.config['UPLOAD_FOLDER'], 
                                    'risques', 
                                    str(risque.id), 
                                    ancien_champ.get_valeur()
                                )
                                if os.path.exists(chemin_fichier):
                                    os.remove(chemin_fichier)
                            
                            # Supprimer l'enregistrement
                            if ancien_champ:
                                db.session.delete(ancien_champ)
                        
                        # Sauvegarder le nouveau fichier
                        nom_fichier = secure_filename(fichier.filename)
                        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                        nom_unique = f"{timestamp}_{nom_fichier}"
                        
                        dossier = os.path.join(app.config['UPLOAD_FOLDER'], 'risques', str(risque.id))
                        os.makedirs(dossier, exist_ok=True)
                        chemin = os.path.join(dossier, nom_unique)
                        
                        fichier.save(chemin)
                        
                        # Créer ou mettre à jour le champ
                        champ_perso = ChampPersonnaliseRisque.query.filter_by(
                            risque_id=risque.id,
                            nom_technique=champ.nom_technique
                        ).first()
                        
                        if not champ_perso:
                            champ_perso = ChampPersonnaliseRisque(
                                risque_id=risque.id,
                                nom_technique=champ.nom_technique
                            )
                        
                        champ_perso.set_valeur(nom_fichier)
                        db.session.add(champ_perso)
            else:
                # Gestion des autres types de champs
                if field_name in request.form:
                    valeur = request.form[field_name]
                    
                    # Pour les checkbox, valeur peut être "true" ou absente
                    if champ.type_champ == 'checkbox':
                        valeur = valeur == 'true'
                    
                    # Pour les multiselect, récupérer toutes les valeurs
                    elif champ.type_champ == 'multiselect':
                        valeurs = request.form.getlist(field_name)
                        valeur = valeurs
                    
                    champ_perso = ChampPersonnaliseRisque.query.filter_by(
                        risque_id=risque.id,
                        nom_technique=champ.nom_technique
                    ).first()
                    
                    if not champ_perso and valeur:
                        # Créer un nouveau champ seulement si valeur non vide
                        champ_perso = ChampPersonnaliseRisque(
                            risque_id=risque.id,
                            nom_technique=champ.nom_technique
                        )
                        champ_perso.set_valeur(valeur)
                        db.session.add(champ_perso)
                    elif champ_perso:
                        if valeur or (champ.est_obligatoire and valeur != ''):
                            champ_perso.set_valeur(valeur)
                            db.session.add(champ_perso)
                        else:
                            # Supprimer le champ si vide et non obligatoire
                            db.session.delete(champ_perso)
        
        # Gérer les fichiers additionnels
        for i in range(10):  # Limite de 10 fichiers additionnels
            fichier_key = f'fichier_additionnel_{i}'
            categorie_key = f'categorie_fichier_{i}'
            description_key = f'description_fichier_{i}'
            
            if fichier_key in request.files:
                fichier = request.files[fichier_key]
                if fichier and fichier.filename:
                    # Sauvegarder le fichier
                    nom_fichier = secure_filename(fichier.filename)
                    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                    nom_unique = f"{timestamp}_{nom_fichier}"
                    
                    dossier = os.path.join(app.config['UPLOAD_FOLDER'], 'risques', str(risque.id))
                    os.makedirs(dossier, exist_ok=True)
                    chemin = os.path.join(dossier, nom_unique)
                    
                    fichier.save(chemin)
                    
                    # Enregistrer en base
                    fichier_db = FichierRisque(
                        risque_id=risque.id,
                        nom_fichier=nom_fichier,
                        chemin_fichier=chemin,
                        type_fichier=fichier.content_type,
                        taille=os.path.getsize(chemin),
                        categorie=request.form.get(categorie_key, 'document'),
                        description=request.form.get(description_key, ''),
                        uploaded_by=current_user.id
                    )
                    db.session.add(fichier_db)
        
        db.session.commit()
        
        # 🔥 SYNCHRONISATION AUTOMATIQUE
        declencher_mise_a_jour_risque(risque.id, 'modification', current_user.id)
        synchroniser_matrices_apres_modification(risque.cartographie_id)
        
        flash('Risque modifié avec succès', 'success')
        return redirect(url_for('detail_risque', id=risque.id))
    
    return render_template('cartographie/risque_form.html',
                         form=form,
                         risque=risque,
                         action='modifier',
                         categories_liste=categories_liste,
                         types_risque_liste=types_risque_liste,
                         champs_configures=champs_configures,
                         valeurs_existantes=valeurs_existantes,
                         config_fichiers=config_fichiers)


@app.route('/risque/<int:id>/nouvelle-evaluation', methods=['POST'])
@login_required
def demarrer_nouvelle_evaluation(id):
    """Démarrer une nouvelle évaluation pour un risque"""
    risque = Risque.query.get_or_404(id)
    
    try:
        # Vérifier s'il y a une évaluation en cours
        evaluation_en_cours = EvaluationRisque.query.filter_by(
            risque_id=id, 
            statut_validation='en_attente'
        ).first()
        
        if evaluation_en_cours:
            flash('❌ Une évaluation est déjà en cours pour ce risque', 'error')
            return redirect(url_for('detail_risque', id=id))
        
        # Créer une nouvelle évaluation avec référence unique
        derniere_eval = EvaluationRisque.query.filter_by(risque_id=id).order_by(EvaluationRisque.created_at.desc()).first()
        numero_evaluation = (derniere_eval.id + 1) if derniere_eval else 1
        
        nouvelle_evaluation = EvaluationRisque(
            risque_id=id,
            type_evaluation=f'evaluation_{numero_evaluation}',
            statut_validation='en_attente',
            created_by=current_user.id
        )
        
        db.session.add(nouvelle_evaluation)
        db.session.commit()
        
        # 🔄 SYNCHRONISATION AUTOMATIQUE
        synchroniser_evaluation_triphase(id)
        
        flash('🆕 Nouvelle évaluation démarrée avec succès', 'success')
        return redirect(url_for('evaluer_risque_triphase', id=id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Erreur lors du démarrage: {str(e)}', 'error')
        return redirect(url_for('detail_risque', id=id))


@app.route('/risque/<int:id>/dupliquer')
@login_required
def dupliquer_risque(id):
    """Dupliquer un risque existant"""
    risque_original = Risque.query.get_or_404(id)
    
    # Générer une nouvelle référence
    dernier_risque = Risque.query.order_by(Risque.id.desc()).first()
    nouvelle_ref = f"RISQ-{(dernier_risque.id + 1) if dernier_risque else 1:04d}"
    
    # Créer la copie du risque
    nouveau_risque = Risque(
        reference=nouvelle_ref,
        intitule=f"{risque_original.intitule} (Copie)",
        description=risque_original.description,
        processus_concerne=risque_original.processus_concerne,
        categorie=risque_original.categorie,
        type_risque=risque_original.type_risque,
        cause_racine=risque_original.cause_racine,
        consequences=risque_original.consequences,
        cartographie_id=risque_original.cartographie_id,
        created_by=current_user.id
    )
    
    db.session.add(nouveau_risque)
    db.session.commit()
    
    flash('Risque dupliqué avec succès', 'success')
    return redirect(url_for('detail_cartographie', id=risque_original.cartographie_id))


@app.route('/risque/<int:id>/kri/creer-rapide', methods=['POST'])
@login_required
def creer_kri_rapide(id):
    """Créer un KRI rapide pour un risque (version simplifiée)"""
    # CORRECTION : Utiliser get_client_object_or_404
    risque = get_client_object_or_404(Risque, id)
    
    # Vérifier les permissions
    if not current_user.has_permission('can_manage_kri'):
        flash('Vous n\'avez pas les permissions pour créer un KRI', 'error')
        return redirect(url_for('detail_risque', id=id))
    
    # Vérifier si un KRI existe déjà
    kri_existant = get_client_filter(KRI).filter_by(
        risque_id=id, 
        type_indicateur='kri',
        est_actif=True
    ).first()
    
    if kri_existant:
        flash(f'Un KRI existe déjà pour ce risque: {kri_existant.nom}', 'warning')
        return redirect(url_for('detail_risque', id=id))
    
    # Récupération des données du formulaire
    nom = request.form.get('nom', f"KRI - {risque.reference}")
    unite_mesure = request.form.get('unite_mesure', '')
    seuil_alerte = request.form.get('seuil_alerte')
    seuil_critique = request.form.get('seuil_critique')
    description = request.form.get('description', f"Indicateur de risque pour {risque.intitule}")
    
    # Validation minimale
    if not nom:
        flash('Le nom du KRI est obligatoire', 'error')
        return redirect(url_for('detail_risque', id=id))
    
    # Création du KRI
    kri = KRI(
        type_indicateur='kri',  # Toujours KRI pour cette route
        risque_id=id,
        nom=nom,
        description=description,
        unite_mesure=unite_mesure,
        frequence_mesure='mensuel',  # Valeur par défaut
        seuil_alerte=float(seuil_alerte) if seuil_alerte else None,
        seuil_critique=float(seuil_critique) if seuil_critique else None,
        seuil_cible=None,  # Pas de cible pour les KRI
        sens_evaluation_seuil='superieur',  # Valeur par défaut
        responsable_mesure_id=current_user.id,
        categorie='operationnel',  # Valeur par défaut
        source_donnees='Création rapide',
        notes_internes=f"Créé rapidement depuis le risque {risque.reference}",
        created_by=current_user.id,
        client_id=risque.client_id  # Hérite du client du risque
    )
    
    try:
        db.session.add(kri)
        db.session.commit()
        
        # Journaliser l'action
        from models import log_activity
        log_activity(current_user.id, 'creation_kri_rapide',
                    f"Création rapide du KRI {kri.nom} pour le risque {risque.reference}",
                    'kri', kri.id)
        
        flash(f'KRI "{kri.nom}" créé avec succès pour le risque {risque.reference}', 'success')
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur création rapide KRI: {e}")
        flash(f'Erreur lors de la création: {str(e)}', 'error')
    
    return redirect(url_for('detail_risque', id=id))


@app.route('/api/risque/<int:id>/statut')
@login_required
def api_statut_risque(id):
    """API pour récupérer le statut d'un risque"""
    risque = Risque.query.get_or_404(id)
    
    derniere_eval = EvaluationRisque.query.filter_by(
        risque_id=id
    ).order_by(EvaluationRisque.created_at.desc()).first()
    
    kri = KRI.query.filter_by(risque_id=id).first()
    
    return jsonify({
        'reference': risque.reference,
        'intitule': risque.intitule,
        'est_evalue': derniere_eval is not None,
        'niveau_risque': derniere_eval.niveau_risque if derniere_eval else 'Non évalué',
        'score': derniere_eval.score_risque if derniere_eval else 0,
        'a_kri': kri is not None,
        'is_archived': risque.is_archived if hasattr(risque, 'is_archived') else False
    })


@app.route('/cartographie/<int:id>/export/matrice')
@login_required
def export_matrice_cartographie(id):
    """Exporter la matrice de risques d'une cartographie"""
    cartographie = Cartographie.query.get_or_404(id)
    
    # Récupérer toutes les évaluations des risques de cette cartographie
    evaluations = []
    for risque in cartographie.risques:
        if hasattr(risque, 'is_archived') and risque.is_archived:
            continue
        if risque.evaluations:
            derniere_evaluation = max(risque.evaluations, key=lambda x: x.created_at)
            evaluations.append(derniere_evaluation)
    
    # Générer la matrice
    matrice_image = generer_matrice_risques(evaluations, 'classique')
    
    # Retourner l'image en réponse directe
    from flask import Response
    import base64
    image_data = base64.b64decode(matrice_image)
    
    response = Response(image_data, mimetype='image/png')
    response.headers['Content-Disposition'] = f'attachment; filename=matrice_{cartographie.nom}_{datetime.now().strftime("%Y%m%d")}.png'
    
    return response


@app.route('/cartographie/<int:id>/risques/non-evalues')
@login_required
def risques_non_evalues(id):
    """Risques non évalués d'une cartographie."""
    cartographie = Cartographie.query.get_or_404(id)
    if not check_client_access(cartographie):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_cartographies'))
    risques_non_evalues = [r for r in cartographie.risques
                           if not getattr(r, 'is_archived', False) and not r.evaluations]
    return render_template('cartographie/risques_non_evalues.html',
                           cartographie=cartographie, risques_non_evalues=risques_non_evalues)


@app.route('/risque/evaluation/multiple', methods=['POST'])
@login_required
def evaluation_multiple_risques():
    """Évaluation multiple de risques"""
    risque_ids = request.form.getlist('risque_ids')
    impact = int(request.form.get('impact', 0))
    probabilite = int(request.form.get('probabilite', 0))
    commentaire = request.form.get('commentaire', 'Évaluation multiple')
    
    if not risque_ids or impact == 0 or probabilite == 0:
        flash('Veuillez sélectionner des risques et des niveaux d\'évaluation', 'error')
        return redirect(request.referrer or url_for('dashboard'))
    
    risques_evalues = 0
    for risque_id in risque_ids:
        risque = Risque.query.get(int(risque_id))
        if risque:
            # Calculer le score et le niveau
            score_risque = impact * probabilite
            niveau_risque, couleur = calculer_niveau_risque(impact, probabilite)
            
            evaluation = EvaluationRisque(
                risque_id=risque.id,
                type_evaluation='multiple',
                evaluateur_id=current_user.id,
                impact=impact,
                probabilite=probabilite,
                niveau_maitrise=3,
                commentaire=f"{commentaire} - {risque.reference}",
                score_risque=score_risque,
                niveau_risque=niveau_risque,
                statut='valide'
            )
            
            db.session.add(evaluation)
            risques_evalues += 1
    
    db.session.commit()
    flash(f'{risques_evalues} risques évalués avec succès', 'success')
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/api/cartographie/<int:id>/stats')
@login_required
def api_stats_cartographie(id):
    """API pour les statistiques d'une cartographie"""
    cartographie = Cartographie.query.get_or_404(id)
    
    stats = {
        'total_risques': 0,
        'risques_evalues': 0,
        'risques_non_evalues': 0,
        'repartition_niveaux': {
            'Critique': 0,
            'Élevé': 0,
            'Moyen': 0,
            'Faible': 0
        },
        'moyenne_scores': 0
    }
    
    scores = []
    for risque in cartographie.risques:
        if hasattr(risque, 'is_archived') and risque.is_archived:
            continue
            
        stats['total_risques'] += 1
        
        if risque.evaluations:
            stats['risques_evalues'] += 1
            derniere_eval = max(risque.evaluations, key=lambda x: x.created_at)
            niveau = derniere_eval.niveau_risque
            stats['repartition_niveaux'][niveau] += 1
            scores.append(derniere_eval.score_risque)
        else:
            stats['risques_non_evalues'] += 1
    
    if scores:
        stats['moyenne_scores'] = round(sum(scores) / len(scores), 2)
    
    return jsonify(stats)


@app.route('/risques/dashboard')
@login_required
def dashboard_risques():
    """
    Tableau de bord consolidé des risques.
    
    LOGIQUE :
        - Critiques NET campagne active (comptés séparément)
        - Critiques NET N-1 à réévaluer (comptés séparément)
        - Total à surveiller = somme des deux
    """
    from models import Risque, EvaluationRisque, Cartographie, CampagneEvaluation
    from datetime import datetime, timedelta
    from sqlalchemy import func, and_, or_

    _journal(f"\n{'='*70}")
    _journal(f"📊 dashboard_risques — {current_user.username}")
    _journal(f"{'='*70}")

    # ============================================
    # 1. FILTRES
    # ============================================
    niveau_filtre = request.args.get('niveau', '')

    # ============================================
    # 2. MULTI-TENANT
    # ============================================
    if current_user.role == 'super_admin':
        risques_query = Risque.query.filter_by(is_archived=False)
        cartographies = Cartographie.query.filter_by(is_archived=False).all()
    else:
        risques_query = get_client_filter(Risque).filter_by(is_archived=False)
        cartographies = get_client_filter(Cartographie).filter_by(is_archived=False).all()

    tous_risques = risques_query.all()

    _journal(f"   Total risques : {len(tous_risques)}")

    # ============================================
    # 3. CAMPAGNES ACTIVES PAR CARTOGRAPHIE
    # ============================================
    campagnes_actives_par_carto = {}
    for carto in cartographies:
        campagne = CampagneEvaluation.query\
            .filter_by(cartographie_id=carto.id, statut='en_cours')\
            .order_by(CampagneEvaluation.created_at.desc())\
            .first()
        campagnes_actives_par_carto[carto.id] = campagne

    # ============================================
    # 4. ENRICHISSEMENT DE CHAQUE RISQUE
    # ============================================
    risques_enrichis = []

    for risque in tous_risques:
        # Campagne active de sa cartographie
        campagne_active = campagnes_actives_par_carto.get(risque.cartographie_id)

        # Éval dans la campagne ACTIVE
        evaluation = None
        if campagne_active:
            evaluation = EvaluationRisque.query.filter_by(
                risque_id=risque.id,
                campagne_id=campagne_active.id
            ).order_by(EvaluationRisque.created_at.desc()).first()

        # Détection réévaluation (N-1)
        eval_n_moins_1 = None
        if not evaluation:
            eval_n_moins_1 = EvaluationRisque.query\
                .filter(
                    EvaluationRisque.risque_id == risque.id,
                    EvaluationRisque.date_confirmation.isnot(None)
                )\
                .order_by(EvaluationRisque.created_at.desc())\
                .first()

        est_revaluation = eval_n_moins_1 is not None

        # Extraction valeurs
        impact = probabilite = maitrise = None
        score_brut = score_net = None
        niveau_brut = niveau_net = None
        taux_reduction = None
        date_eval = None
        statut_eval = 'non_evalue'

        # Éval à afficher (campagne active en priorité, sinon N-1)
        eval_affichee = evaluation or eval_n_moins_1

        if eval_affichee:
            impact = (eval_affichee.impact_conf or eval_affichee.impact_val 
                      or eval_affichee.impact_pre)
            probabilite = (eval_affichee.probabilite_conf 
                           or eval_affichee.probabilite_val 
                           or eval_affichee.probabilite_pre)
            maitrise = (eval_affichee.niveau_maitrise_conf 
                        or eval_affichee.niveau_maitrise_val 
                        or eval_affichee.niveau_maitrise_pre)

            score_brut = eval_affichee.score_risque_brut or (impact * probabilite if impact and probabilite else 0)
            score_net = eval_affichee.score_risque_net or eval_affichee.score_risque
            niveau_brut = eval_affichee.niveau_risque_brut
            niveau_net = eval_affichee.niveau_risque_net or eval_affichee.niveau_risque
            taux_reduction = eval_affichee.taux_reduction_maitrise
            date_eval = (eval_affichee.date_confirmation 
                         or eval_affichee.date_validation 
                         or eval_affichee.date_pre_evaluation)

        # Statut
        if evaluation:
            if evaluation.date_confirmation:
                statut_eval = 'termine'
            elif evaluation.statut_validation == 'a_revoir':
                statut_eval = 'a_revoir'
            elif evaluation.statut_validation == 'en_attente_admin':
                statut_eval = 'en_attente_admin'
            elif evaluation.impact_pre:
                statut_eval = 'en_cours'
        elif est_revaluation:
            statut_eval = 'a_revaluer'
        elif not campagne_active:
            statut_eval = 'non_evaluable'

        risques_enrichis.append({
            'risque': risque,
            'campagne_active': campagne_active,
            'campagne_nom': (campagne_active.nom if campagne_active 
                             else (eval_n_moins_1.campagne_nom if eval_n_moins_1 else None)),
            'evaluation': evaluation,
            'eval_n_moins_1': eval_n_moins_1,
            'eval_affichee': eval_affichee,
            'est_revaluation': est_revaluation,
            'statut': statut_eval,
            # Scores ISO
            'impact': impact,
            'probabilite': probabilite,
            'maitrise': maitrise,
            'score_brut': score_brut,
            'score_net': score_net,
            'niveau_brut': niveau_brut,
            'niveau_net': niveau_net,
            'taux_reduction': taux_reduction,
            'date_eval': date_eval,
        })

    # ============================================
    # 5. STATISTIQUES GLOBALES
    # ============================================
    total_risques = len(risques_enrichis)
    risques_evalues = [r for r in risques_enrichis if r['evaluation']]
    total_risques_evalues = len(risques_evalues)

    # ============================================
    # 6. COMPTAGE PAR NIVEAU (distinction N vs N-1)
    # ============================================
    compteur_niveaux = {
        'critique': 0,
        'critique_n_moins_1': 0,      # 🔥 Critique N-1 (à réévaluer)
        'eleve': 0,
        'moyen': 0,
        'faible': 0,
        'non_evalue': 0
    }

    scores_totaux = []

    for item in risques_enrichis:
        niveau = item['niveau_net']
        score = item['score_net']
        est_reval = item['est_revaluation']

        if niveau == 'Critique':
            if est_reval:
                compteur_niveaux['critique_n_moins_1'] += 1
            else:
                compteur_niveaux['critique'] += 1
            if score: scores_totaux.append(score)
        elif niveau == 'Élevé':
            compteur_niveaux['eleve'] += 1
            if score: scores_totaux.append(score)
        elif niveau == 'Moyen':
            compteur_niveaux['moyen'] += 1
            if score: scores_totaux.append(score)
        elif niveau == 'Faible':
            compteur_niveaux['faible'] += 1
            if score: scores_totaux.append(score)
        else:
            compteur_niveaux['non_evalue'] += 1

    risques_critiques_count = compteur_niveaux['critique']
    risques_critiques_n_moins_1 = compteur_niveaux['critique_n_moins_1']
    total_critiques = risques_critiques_count + risques_critiques_n_moins_1

    score_risque_moyen = round(sum(scores_totaux) / len(scores_totaux), 1) if scores_totaux else 0

    niveaux_data = {
        'critique': risques_critiques_count,
        'critique_n_moins_1': risques_critiques_n_moins_1,
        'eleve': compteur_niveaux['eleve'],
        'moyen': compteur_niveaux['moyen'],
        'faible': compteur_niveaux['faible'],
        'non_evalue': compteur_niveaux['non_evalue'],
    }

    _journal(f"   📊 Niveaux NET :")
    _journal(f"      Critique (active)   : {risques_critiques_count}")
    _journal(f"      Critique (N-1)      : {risques_critiques_n_moins_1}")
    _journal(f"      Élevé               : {compteur_niveaux['eleve']}")
    _journal(f"      Moyen               : {compteur_niveaux['moyen']}")
    _journal(f"      Faible              : {compteur_niveaux['faible']}")
    _journal(f"      Non évalué          : {compteur_niveaux['non_evalue']}")
    _journal(f"   📊 Score NET moyen : {score_risque_moyen}")

    # ============================================
    # 7. FILTRAGE POUR AFFICHAGE
    # ============================================
    risques_filtres_data = []

    for item in risques_enrichis:
        niveau = item['niveau_net']
        est_reval = item['est_revaluation']

        inclure = True
        if niveau_filtre:
            if niveau_filtre == 'non_evalue':
                inclure = niveau is None
            elif niveau_filtre == 'critique':
                # 🔥 Inclure les 2 types de critiques
                inclure = (niveau == 'Critique')
            elif niveau_filtre == 'critique_active':
                # 🔥 Uniquement critiques campagne active
                inclure = (niveau == 'Critique' and not est_reval)
            elif niveau_filtre == 'critique_n_moins_1':
                # 🔥 Uniquement critiques N-1
                inclure = (niveau == 'Critique' and est_reval)
            elif niveau_filtre == 'eleve':
                inclure = niveau == 'Élevé'
            elif niveau_filtre == 'moyen':
                inclure = niveau == 'Moyen'
            elif niveau_filtre == 'faible':
                inclure = niveau == 'Faible'
            elif niveau_filtre == 'a_revaluer':
                inclure = est_reval

        if inclure:
            risques_filtres_data.append(item)

    # ============================================
    # 8. STATISTIQUES PAR CATÉGORIE
    # ============================================
    categories_counts = {}
    for item in risques_enrichis:
        cat = item['risque'].categorie or 'Autre'
        categories_counts[cat] = categories_counts.get(cat, 0) + 1

    repartition_categories = sorted(
        categories_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )[:8]

    # ============================================
    # 9. TOP CARTOGRAPHIES
    # ============================================
    cartographies_stats = []
    for carto in cartographies:
        risques_carto = [r for r in risques_enrichis if r['risque'].cartographie_id == carto.id]
        nb_risques = len(risques_carto)

        if nb_risques == 0:
            continue

        scores_carto = [r['score_net'] for r in risques_carto if r['score_net']]
        score_moyen = round(sum(scores_carto) / len(scores_carto), 1) if scores_carto else None

        nb_revaluer = len([r for r in risques_carto if r['est_revaluation']])
        nb_critiques = len([r for r in risques_carto if r['niveau_net'] == 'Critique'])

        cartographies_stats.append({
            'cartographie': carto,
            'nb_risques': nb_risques,
            'score_moyen': score_moyen,
            'nb_revaluer': nb_revaluer,
            'nb_critiques': nb_critiques,
        })

    cartographies_stats.sort(key=lambda x: x['nb_risques'], reverse=True)

    # ============================================
    # 10. RISQUES CRITIQUES RÉCENTS
    # ============================================
    date_limite = datetime.now() - timedelta(days=30)
    risques_critiques_recents = []

    for item in risques_enrichis:
        if item['niveau_net'] in ['Critique', 'Élevé']:
            date_ev = item['date_eval']
            if date_ev:
                try:
                    if date_ev.tzinfo is None:
                        est_recent = date_ev >= date_limite
                    else:
                        from datetime import timezone
                        est_recent = date_ev >= date_limite.replace(tzinfo=timezone.utc)
                    if est_recent:
                        risques_critiques_recents.append(item)
                except TypeError:
                    pass

    # ============================================
    # 11. TRI PAR SCORE NET DÉCROISSANT
    # ============================================
    def _priority(item):
        # Critiques campagne active en premier
        if item['niveau_net'] == 'Critique' and not item['est_revaluation']:
            return (0, -(item['score_net'] or 0))
        # Puis critiques N-1
        if item['niveau_net'] == 'Critique' and item['est_revaluation']:
            return (1, -(item['score_net'] or 0))
        # Puis le reste par score
        return (2, -(item['score_net'] or 0))

    risques_filtres_data.sort(key=_priority)

    # ============================================
    # 12. RENDU
    # ============================================
    _journal(f"   Total affichés : {len(risques_filtres_data)}")
    _journal(f"{'='*70}\n")

    return render_template(
        'dashboard_risques.html',
        total_risques=total_risques,
        total_risques_evalues=total_risques_evalues,
        risques_critiques_count=risques_critiques_count,
        risques_critiques_n_moins_1=risques_critiques_n_moins_1,
        total_critiques=total_critiques,
        score_risque_moyen=score_risque_moyen,
        risques_critiques_recents=risques_critiques_recents[:5],
        repartition_categories=repartition_categories,
        cartographies_actives=cartographies_stats[:5],
        risques_filtres=risques_filtres_data,
        niveaux_data=niveaux_data,
        niveau_filtre=niveau_filtre,
    )


@app.route('/risques/recherche')
@login_required
def recherche_risques():
    """Recherche avancée dans les risques - Version multi-tenant"""
    from models import Risque, Cartographie
    from sqlalchemy import or_
    
    query = request.args.get('q', '')
    categorie = request.args.get('categorie', '')
    niveau_risque = request.args.get('niveau_risque', '')
    cartographie_id = request.args.get('cartographie_id', '')
    
    # ✅ MULTI-TENANT : Utiliser get_client_filter
    if current_user.role == 'super_admin':
        risques_query = Risque.query.filter_by(is_archived=False)
        cartographies = Cartographie.query.filter_by(is_archived=False).all()
    else:
        risques_query = get_client_filter(Risque).filter_by(is_archived=False)
        cartographies = get_client_filter(Cartographie).filter_by(is_archived=False).all()
    
    # Filtres
    if query:
        risques_query = risques_query.filter(
            or_(
                Risque.reference.ilike(f'%{query}%'),
                Risque.intitule.ilike(f'%{query}%'),
                Risque.description.ilike(f'%{query}%')
            )
        )
    
    if categorie:
        risques_query = risques_query.filter_by(categorie=categorie)
    
    if cartographie_id:
        risques_query = risques_query.filter_by(cartographie_id=int(cartographie_id))
    
    risques = risques_query.all()
    
    # Filtre par niveau de risque (post-requête car dépend de la dernière évaluation)
    if niveau_risque:
        risques_filtres = []
        for risque in risques:
            if risque.evaluations:
                derniere_eval = max(risque.evaluations, key=lambda x: x.created_at)
                if niveau_risque == 'Non évalué':
                    # Déjà exclu car a des évaluations
                    continue
                elif derniere_eval.niveau_risque == niveau_risque:
                    risques_filtres.append(risque)
            else:
                if niveau_risque == 'Non évalué':
                    risques_filtres.append(risque)
        risques = risques_filtres
    
    # Options pour les filtres
    categories = db.session.query(Risque.categorie).filter_by(is_archived=False).distinct().all()
    categories = [c for c in categories if c[0] is not None]
    
    return render_template('recherche_risques.html',
                         risques=risques,
                         query=query,
                         categories=categories,
                         cartographies=cartographies,
                         selected_categorie=categorie,
                         selected_niveau=niveau_risque,
                         selected_cartographie=cartographie_id)


@app.route('/api/guide-evaluation')
@login_required
def api_guide_evaluation():
    """API pour récupérer le guide d'évaluation"""
    try:
        sections = GuideEvaluation.query.filter_by(est_actif=True).order_by('ordre').all()
        
        return jsonify({
            'success': True,
            'sections': [{
                'id': section.id,
                'section': section.section,
                'titre': section.titre,
                'contenu': section.contenu,
                'ordre': section.ordre,
                'est_actif': section.est_actif
            } for section in sections]
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/cartographie/<int:cartographie_id>/actualiser', methods=['POST'])
@login_required
def actualiser_cartographie(cartographie_id):
    """
    API pour actualiser COMPLÈTEMENT une cartographie
    """
    try:
        start_time = datetime.utcnow()
        
        # 1. Récupérer la cartographie
        cartographie = get_client_filter(Cartographie).filter_by(id=cartographie_id).first_or_404()
        
        if not check_client_access(cartographie):
            return jsonify({'success': False, 'error': 'Accès non autorisé'}), 403
        
        # 2. Campagne active
        campagne_active = CampagneEvaluation.query.filter_by(
            cartographie_id=cartographie_id,
            statut='en_cours'
        ).first()
        
        if not campagne_active:
            campagne_active = creer_campagne_par_defaut(cartographie_id, current_user.id)
            _journal(f"✅ Campagne par défaut créée: {campagne_active.nom}")
        
        # 3. Récupérer tous les risques non archivés
        risques = get_client_filter(Risque)\
            .filter_by(cartographie_id=cartographie_id, is_archived=False)\
            .all()
        
        _journal(f"🎯 Traitement de {len(risques)} risques")
        
        # 4. Pour chaque risque, utiliser actualisation_super_intelligente
        resultats_risques = []
        for risque in risques:
            resultat = actualisation_super_intelligente(risque.id, campagne_active.id)
            if resultat and resultat.get('success'):
                
                # ✅ Adapter le format selon le statut retourné
                if resultat.get('statut') == 'verrouillee':
                    # Évaluation déjà confirmée
                    resultats_risques.append({
                        'risque_id': risque.id,
                        'risque_reference': risque.reference,
                        'score_avant': resultat.get('score_actuel', 'N/A'),
                        'score_apres': resultat.get('score_actuel', 'N/A'),
                        'niveau': resultat.get('niveau', 'Verrouillée'),
                        'incidents': resultat.get('incidents_analyses', 0),
                        'statut': 'verrouillee'
                    })
                    
                elif resultat.get('statut') == 'suggestion':
                    # Suggestion générée sans modification
                    resultats_risques.append({
                        'risque_id': risque.id,
                        'risque_reference': risque.reference,
                        'score_avant': resultat.get('score_actuel', 'N/A'),
                        'score_apres': resultat.get('score_suggere', 'N/A'),
                        'niveau': resultat.get('niveau_actuel', 'Non évalué'),
                        'niveau_suggere': resultat.get('niveau_suggere', 'Non évalué'),
                        'incidents': resultat.get('incidents_analyses', 0),
                        'statut': 'suggestion'
                    })
                    
                else:
                    # Cas par défaut
                    resultats_risques.append({
                        'risque_id': risque.id,
                        'risque_reference': risque.reference,
                        'score_avant': resultat.get('score_actuel', 'N/A'),
                        'score_apres': resultat.get('score_suggere', 'N/A'),
                        'niveau': resultat.get('niveau_actuel', 'Non évalué'),
                        'incidents': resultat.get('incidents_analyses', 0),
                        'statut': resultat.get('statut', 'inconnu')
                    })
        
        # 5. Regénérer les matrices
        evaluations = get_client_filter(EvaluationRisque)\
            .filter_by(campagne_id=campagne_active.id)\
            .all()
        
        matrice_classique = generer_matrice_risques(evaluations, 'classique')
        matrice_criticite = generer_matrice_risques(evaluations, 'criticite')
        matrice_priorisation = generer_matrice_risques(evaluations, 'priorisation')
        
        # 6. Statistiques
        nb_risques_total = len(risques)
        nb_risques_evalues = len([r for r in risques if r.evaluations])
        progression_campagne = int((nb_risques_evalues / nb_risques_total * 100) if nb_risques_total > 0 else 0)
        
        end_time = datetime.utcnow()
        duree_ms = int((end_time - start_time).total_seconds() * 1000)
        
        _journal(f"⏱️ Actualisation terminée en {duree_ms}ms")
        
        return jsonify({
            'success': True,
            'message': f'Cartographie actualisée avec succès. {len(resultats_risques)} risques traités.',
            'stats': {
                'risques_totaux': nb_risques_total,
                'risques_traites': len(resultats_risques),
                'progression': progression_campagne,
                'duree_ms': duree_ms
            },
            'details_risques': resultats_risques[:20],
            'matrices': {
                'classique': matrice_classique,
                'criticite': matrice_criticite,
                'priorisation': matrice_priorisation
            }
        })
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur actualisation: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/risque/<int:risque_id>/plans-action')
@login_required
def plans_action_risque(risque_id):
    """Liste des plans d'action liés à un risque"""
    risque = Risque.query.get_or_404(risque_id)
    plans_action = PlanAction.query.filter_by(risque_id=risque_id).all()
    
    return render_template('audit/plans_action_risque.html',
                         risque=risque,
                         plans_action=plans_action)


@app.route('/risque/<int:risque_id>/plan-action/nouveau', methods=['GET', 'POST'])
@login_required
def nouveau_plan_action_risque(risque_id):
    """Créer un plan d'action directement lié à un risque."""
    risque = Risque.query.get_or_404(risque_id)
    if not check_client_access(risque):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('dashboard'))
    form = PlanActionForm()
    utilisateurs = User.query.filter_by(client_id=risque.client_id, is_active=True).order_by(User.username).all()
    if hasattr(form, 'responsable_id'):
        form.responsable_id.choices = [(0, 'Sélectionnez un responsable')] + [(u.id, u.username) for u in utilisateurs]
    if form.validate_on_submit():
        try:
            responsable = getattr(form, 'responsable_id', None)
            plan_action = PlanAction(
                nom=form.nom.data,
                description=form.description.data,
                date_debut=form.date_debut.data,
                date_fin_prevue=form.date_fin_prevue.data,
                risque_id=risque_id,
                responsable_id=(responsable.data or None) if responsable else None,
                created_by=current_user.id,
                client_id=risque.client_id,
            )
            db.session.add(plan_action)
            db.session.commit()
            flash("Plan d'action créé avec succès pour le risque", 'success')
            return redirect(url_for('plans_action_risque', risque_id=risque_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la création : {e}', 'error')
    return render_template('audit/form_plan_action_risque.html', form=form, risque=risque)


@app.route('/api/risques/actifs')
@login_required
def api_risques_actifs():
    """API pour récupérer les risques actifs"""
    risques = Risque.query.filter_by(is_archived=False).all()
    
    risques_data = []
    for risque in risques:
        risques_data.append({
            'id': risque.id,
            'reference': risque.reference,
            'intitule': risque.intitule,
            'categorie': risque.categorie
        })
    
    return jsonify(risques_data)


@app.route('/api/risques/non-associes-processus')
@login_required
def api_risques_non_associes_processus():
    """
    Récupérer les risques non associés à un processus métier
    Utilisé dans les modals d'association processus ↔ risque
    """
    from models import Risque, EvaluationRisque
    
    # Récupérer tous les risques du client qui ne sont pas archivés
    # et qui n'ont PAS de processus_metier_associe_id
    risques = get_client_filter(Risque).filter_by(
        is_archived=False,
        processus_metier_associe_id=None
    ).all()
    
    # Construire la réponse avec les infos d'évaluation
    resultats = []
    for risque in risques:
        niveau = 'non_evalue'
        niveau_couleur = 'secondary'
        score = None
        derniere_eval = None
        
        # Récupérer la dernière évaluation
        if risque.evaluations:
            derniere_eval = max(risque.evaluations, key=lambda x: x.created_at)
            if derniere_eval.niveau_risque:
                niveau = derniere_eval.niveau_risque.lower()
                niveau_couleur = {
                    'critique': 'danger',
                    'élevé': 'warning',
                    'moyen': 'info',
                    'faible': 'success'
                }.get(niveau, 'secondary')
                score = derniere_eval.score_risque
        
        resultats.append({
            'id': risque.id,
            'reference': risque.reference,
            'intitule': risque.intitule,
            'description': risque.description or '',
            'categorie': risque.categorie or 'Non catégorisé',
            'niveau': niveau,
            'niveau_couleur': niveau_couleur,
            'score': score,
            'date_evaluation': derniere_eval.created_at.strftime('%d/%m/%Y') if derniere_eval and derniere_eval.created_at else None
        })
    
    # Trier par niveau de risque (critique en premier)
    ordre_niveau = {'critique': 0, 'eleve': 1, 'moyen': 2, 'faible': 3, 'non_evalue': 4}
    resultats.sort(key=lambda x: ordre_niveau.get(x['niveau'], 5))
    
    return jsonify({
        'success': True,
        'total': len(resultats),
        'risques': resultats
    })


@app.route('/zone-risque/<int:id>/modifier', methods=['POST'])
@login_required
def modifier_zone_risque(id):
    zone_risque = ZoneRisqueProcessus.query.get_or_404(id)
    
    zone_risque.nom = request.form['nom']
    zone_risque.description = request.form.get('description')
    zone_risque.type_risque = request.form['type_risque']
    zone_risque.niveau_risque = request.form['niveau_risque']
    zone_risque.impact = request.form.get('impact')
    zone_risque.mesures_controle = request.form.get('mesures_controle')
    zone_risque.responsable_id = request.form.get('responsable_id') or None
    
    db.session.commit()
    
    # Synchronisation automatique
    synchroniser_processus_apres_modification(zone_risque.processus_id, 'modification_zone_risque', current_user.id)
    
    flash('Zone de risque modifiée avec succès', 'success')
    return redirect(url_for('detail_processus', id=zone_risque.processus_id))


@app.route('/zone-risque/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_zone_risque(id):
    zone_risque = ZoneRisqueProcessus.query.get_or_404(id)
    processus_id = zone_risque.processus_id
    
    db.session.delete(zone_risque)
    db.session.commit()
    
    # Synchronisation automatique
    synchroniser_processus_apres_modification(processus_id, 'suppression_zone_risque', current_user.id)
    
    flash('Zone de risque supprimée avec succès', 'success')
    return redirect(url_for('detail_processus', id=processus_id))


@app.route('/cartographie/<int:id>/synchroniser', methods=['POST'])
@login_required
def synchroniser_cartographie(id):
    """Synchroniser manuellement une cartographie"""
    from utils import synchroniser_cartographie_complete
    
    success = synchroniser_cartographie_complete(id)
    
    if success:
        flash('Cartographie synchronisée avec succès', 'success')
    else:
        flash('Erreur lors de la synchronisation', 'error')
    
    return redirect(url_for('detail_cartographie', id=id))


@app.route('/cartographie/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_cartographie(id):
    """Modifier une cartographie avec synchronisation automatique"""
    from utils import synchroniser_cartographie_complete
    
    cartographie = Cartographie.query.get_or_404(id)
    
    # Vérifier l'accès
    if not check_client_access(cartographie):
        flash('Accès non autorisé à cette cartographie', 'error')
        return redirect(url_for('liste_cartographies'))
    
    form = CartographieForm(obj=cartographie)
    
    # ===== CHARGER LES DONNÉES POUR LES LISTES DÉROULANTES =====
    poles = get_client_filter(Pole).filter_by(is_archived=False).order_by(Pole.ordre).all()
    directions = get_client_filter(Direction).filter_by(is_archived=False, is_active=True).all()
    services = get_client_filter(Service).filter_by(is_archived=False, is_active=True).all()
    
    # Configurer les choix
    form.pole_id.choices = [(0, '--- Aucun pôle ---')] + [(p.id, p.nom) for p in poles]
    form.direction_id.choices = [(0, '--- Sélectionner une direction ---')] + [
        (d.id, f"{d.nom}" + (f" ({d.pole.nom})" if d.pole else "")) for d in directions
    ]
    form.service_id.choices = [(0, '--- Sélectionner un service ---')] + [
        (s.id, f"{s.nom} ({s.direction.nom})") for s in services
    ]
    
    if form.validate_on_submit():
        type_cartographie = request.form.get('type_cartographie', 'direction')
        
        # Gérer les valeurs
        pole_id = form.pole_id.data if form.pole_id.data and form.pole_id.data != 0 else None
        direction_id = form.direction_id.data if form.direction_id.data and form.direction_id.data != 0 else None
        service_id = form.service_id.data if type_cartographie == 'service' and form.service_id.data and form.service_id.data != 0 else None
        
        # Validation
        if not direction_id:
            flash('Veuillez sélectionner une direction', 'error')
            return render_template('cartographie/form.html', 
                                 form=form, 
                                 cartographie=cartographie,
                                 poles=poles,
                                 action='modifier')
        
        # Vérifier la cohérence pôle/direction
        if pole_id and direction_id:
            direction = Direction.query.get(direction_id)
            if direction and direction.pole_id != pole_id:
                flash('La direction sélectionnée n\'appartient pas au pôle choisi', 'error')
                return render_template('cartographie/form.html', 
                                     form=form, 
                                     cartographie=cartographie,
                                     poles=poles,
                                     action='modifier')
        
        # Mettre à jour la cartographie
        cartographie.nom = form.nom.data
        cartographie.description = form.description.data
        cartographie.pole_id = pole_id
        cartographie.direction_id = direction_id
        cartographie.service_id = service_id
        cartographie.type_cartographie = type_cartographie
        cartographie.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # 🔥 SYNCHRONISATION AUTOMATIQUE
        try:
            synchroniser_cartographie_complete(id)
            flash('Cartographie modifiée et synchronisée avec succès', 'success')
        except Exception as e:
            _journal(f"⚠️ Erreur synchronisation: {e}")
            flash('Cartographie modifiée mais erreur lors de la synchronisation', 'warning')
        
        return redirect(url_for('liste_cartographies'))
    
    # Pré-remplir les valeurs existantes pour l'affichage GET
    if request.method == 'GET':
        form.nom.data = cartographie.nom
        form.description.data = cartographie.description
        form.pole_id.data = cartographie.pole_id if cartographie.pole_id else 0
        
        if cartographie.direction_id:
            form.direction_id.data = cartographie.direction_id
        else:
            form.direction_id.data = 0
            
        if cartographie.service_id:
            form.service_id.data = cartographie.service_id
            form.type_cartographie.data = 'service'
        else:
            form.service_id.data = 0
            form.type_cartographie.data = 'direction'
    
    return render_template('cartographie/form.html', 
                         form=form, 
                         cartographie=cartographie,
                         poles=poles,
                         action='modifier')


@app.route('/cartographie/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_cartographie(id):
    """Supprimer une cartographie avec synchronisation"""
    from models import db, Risque, EvaluationRisque, KRI, MesureKRI
    
    cartographie = Cartographie.query.get_or_404(id)
    
    # Vérifier les permissions
    if current_user.role != 'admin' and current_user.id != cartographie.created_by:
        flash('Vous n\'êtes pas autorisé à supprimer cette cartographie', 'error')
        return redirect(url_for('liste_cartographies'))
    
    try:
        # Récupérer tous les risques de cette cartographie
        risques = Risque.query.filter_by(cartographie_id=id).all()
        
        for risque in risques:
            # Supprimer les évaluations
            EvaluationRisque.query.filter_by(risque_id=risque.id).delete()
            
            # Supprimer les KRI et mesures
            kri = KRI.query.filter_by(risque_id=risque.id).first()
            if kri:
                MesureKRI.query.filter_by(kri_id=kri.id).delete()
                db.session.delete(kri)
            
            # Supprimer le risque
            db.session.delete(risque)
        
        # Supprimer la cartographie
        db.session.delete(cartographie)
        db.session.commit()
        
        # 🔥 SYNCHRONISATION GLOBALE
        from utils import synchroniser_donnees_globales
        synchroniser_donnees_globales()
        
        flash('Cartographie supprimée avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la suppression: {str(e)}', 'error')
    
    return redirect(url_for('liste_cartographies'))


@app.route('/cartographie/<int:id>/verifier-incoherences')
@login_required
def verifier_incoherences_cartographie(id):
    """Vérifier les incohérences d'une cartographie."""
    from utils import verifier_incoherences_cartographie as check_incoherences
    cartographie = Cartographie.query.get_or_404(id)
    if not check_client_access(cartographie):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_cartographies'))
    result = check_incoherences(id)
    return render_template('cartographie/verifier_incoherences.html',
                           result=result, cartographie_id=id, cartographie=cartographie)


# Dans app.py
@app.route('/api/cartographie/<int:carto_id>/risques')
@login_required
def api_cartographie_risques(carto_id):
    """Récupérer les risques d'une cartographie (filtré par client)"""
    
    # 🔥 Vérifier l'accès à la cartographie
    cartographie = get_client_object_or_404(Cartographie, carto_id)
    
    risques = []
    for risque in cartographie.risques:
        if not risque.is_archived:
            risques.append({
                'id': risque.id,
                'reference': risque.reference,
                'intitule': risque.intitule,
                'description': risque.description,
                'categorie': risque.categorie,
                'type_risque': risque.type_risque
            })
    
    return jsonify({'success': True, 'risques': risques})


@app.route('/bibliotheque-risques')
@login_required
def bibliotheque_risques():
    """Page principale de la bibliothèque - tous secteurs"""
    
    secteurs = SecteurActivite.query.filter_by(est_actif=True).order_by(SecteurActivite.ordre).all()
    cartographies = get_client_filter(Cartographie).filter_by(is_archived=False).all()
    
    return render_template('bibliotheque_risques/index.html',
                         secteurs=secteurs,
                         secteur=None,
                         direction=None,
                         cartographies=cartographies)


@app.route('/bibliotheque-risques/secteur/<secteur_code>')
@login_required
def bibliotheque_risques_secteur(secteur_code):
    """Page d'un secteur spécifique"""
    
    secteur = SecteurActivite.query.filter_by(code=secteur_code, est_actif=True).first_or_404()
    directions = DirectionSecteur.query.filter_by(secteur_id=secteur.id, est_actif=True).order_by(DirectionSecteur.ordre).all()
    cartographies = get_client_filter(Cartographie).filter_by(is_archived=False).all()
    
    return render_template('bibliotheque_risques/index.html',
                         secteurs=[secteur],
                         secteur=secteur,
                         directions=directions,
                         direction=None,
                         cartographies=cartographies)


@app.route('/bibliotheque-risques/direction/<secteur_code>/<int:direction_id>')
@login_required
def bibliotheque_risques_direction(secteur_code, direction_id):
    """Page des risques d'une direction spécifique"""
    
    secteur = SecteurActivite.query.filter_by(code=secteur_code, est_actif=True).first_or_404()
    direction = DirectionSecteur.query.get_or_404(direction_id)
    risques = BibliothequeRisque.query.filter_by(
        direction_id=direction_id,
        est_publie=True
    ).order_by(BibliothequeRisque.nb_utilisations.desc()).all()
    
    cartographies = get_client_filter(Cartographie).filter_by(is_archived=False).all()
    
    return render_template('bibliotheque_risques/index.html',
                         secteur=secteur,
                         direction=direction,
                         risques=risques,
                         cartographies=cartographies)


@app.route('/bibliotheque-risques/recherche')
@login_required
def bibliotheque_risques_recherche():
    """Recherche de risques dans toute la bibliothèque"""
    
    q = request.args.get('q', '')
    risques = []
    
    if q:
        risques = BibliothequeRisque.query.filter(
            db.or_(
                BibliothequeRisque.intitule.ilike(f'%{q}%'),
                BibliothequeRisque.description.ilike(f'%{q}%'),
                BibliothequeRisque.mots_cles.cast(db.String).ilike(f'%{q}%')
            ),
            BibliothequeRisque.est_publie == True
        ).order_by(BibliothequeRisque.nb_utilisations.desc()).all()
    
    cartographies = get_client_filter(Cartographie).filter_by(is_archived=False).all()
    
    return render_template('bibliotheque_risques/index.html',
                         risques=risques,
                         recherche=q,
                         cartographies=cartographies,
                         secteur=None,
                         direction=None)


@app.route('/bibliotheque-risques/categorie/<categorie>')
@login_required
def bibliotheque_risques_categorie(categorie):
    """Page d'une catégorie de risques"""
    
    risques = BibliothequeRisque.query.filter_by(
        categorie=categorie,
        est_publie=True
    ).order_by(BibliothequeRisque.nb_utilisations.desc()).all()
    
    # Récupérer les cartographies de l'utilisateur
    cartographies = get_client_filter(Cartographie).filter_by(is_archived=False).all()
    
    return render_template('bibliotheque_risques/categorie.html',
                         risques=risques,
                         categorie=categorie,
                         cartographies=cartographies)


@app.route('/api/bibliotheque-risques/recherche')
@login_required
def api_recherche_bibliotheque_risques():
    """API de recherche dans la bibliothèque"""
    
    q = request.args.get('q', '')
    categorie = request.args.get('categorie', '')
    limit = request.args.get('limit', 10, type=int)
    
    query = BibliothequeRisque.query.filter_by(est_publie=True)
    
    if q:
        query = query.filter(
            db.or_(
                BibliothequeRisque.intitule.ilike(f'%{q}%'),
                BibliothequeRisque.mots_cles.cast(db.String).ilike(f'%{q}%')
            )
        )
    
    if categorie:
        query = query.filter_by(categorie=categorie)
    
    risques = query.order_by(BibliothequeRisque.nb_utilisations.desc()).limit(limit).all()
    
    return jsonify({
        'success': True,
        'risques': [r.to_dict() for r in risques]
    })


@app.route('/api/bibliotheque-risques/suggestions')
@login_required
def api_suggestions_bibliotheque():
    """Suggestions de risques basées sur le contexte"""
    
    contexte = request.args.get('contexte', '')
    secteur = request.args.get('secteur', '')
    mots_cles = request.args.get('mots_cles', '')
    
    suggestions = []
    
    # 1. Suggestions basées sur les mots-clés
    if mots_cles:
        for mot in mots_cles.split(','):
            risques = BibliothequeRisque.query.filter(
                BibliothequeRisque.mots_cles.cast(db.String).ilike(f'%{mot.strip()}%'),
                BibliothequeRisque.est_publie == True
            ).limit(3).all()
            suggestions.extend(risques)
    
    # 2. Suggestions basées sur la popularité
    if len(suggestions) < 5:
        risques_populaires = BibliothequeRisque.query.filter_by(
            est_publie=True
        ).order_by(BibliothequeRisque.nb_utilisations.desc()).limit(5).all()
        suggestions.extend(risques_populaires)
    
    # Éliminer les doublons
    suggestions_uniques = list({s.id: s for s in suggestions}.values())
    
    return jsonify({
        'success': True,
        'suggestions': [s.to_dict() for s in suggestions_uniques[:10]]
    })


@app.route('/api/bibliotheque-risques/liste', methods=['GET'])
@login_required
def api_bibliotheque_risques_liste():
    """Récupérer la liste des risques de la bibliothèque"""
    
    categorie = request.args.get('categorie', '')
    recherche = request.args.get('recherche', '')
    secteur_id = request.args.get('secteur_id', type=int)
    direction_id = request.args.get('direction_id', type=int)
    
    query = BibliothequeRisque.query.filter_by(est_publie=True)
    
    if categorie:
        query = query.filter_by(categorie=categorie)
    if secteur_id:
        query = query.filter_by(secteur_id=secteur_id)
    if direction_id:
        query = query.filter_by(direction_id=direction_id)
    if recherche:
        query = query.filter(
            db.or_(
                BibliothequeRisque.intitule.ilike(f'%{recherche}%'),
                BibliothequeRisque.description.ilike(f'%{recherche}%')
            )
        )
    
    risques = query.order_by(BibliothequeRisque.nb_utilisations.desc()).all()
    
    return jsonify({
        'success': True,
        'risques': [r.to_dict() for r in risques]
    })


@app.route('/api/bibliotheque-risques/appliquer', methods=['POST'])
@login_required
def api_appliquer_risque_bibliotheque():
    """Appliquer un risque de la bibliothèque à une cartographie"""
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Données JSON requises'}), 400
        
        risque_id = data.get('risque_id')
        cartographie_id = data.get('cartographie_id')
        
        if not risque_id or not cartographie_id:
            return jsonify({'success': False, 'error': 'Paramètres manquants (risque_id, cartographie_id)'}), 400
        
        # Récupérer le risque de la bibliothèque
        risque_biblio = BibliothequeRisque.query.get(risque_id)
        if not risque_biblio:
            return jsonify({'success': False, 'error': 'Risque non trouvé dans la bibliothèque'}), 404
        
        # Récupérer la cartographie
        cartographie = Cartographie.query.get(cartographie_id)
        if not cartographie:
            return jsonify({'success': False, 'error': 'Cartographie non trouvée'}), 404
        
        # Vérifier l'accès à la cartographie
        if not check_client_access(cartographie):
            return jsonify({'success': False, 'error': 'Accès non autorisé à cette cartographie'}), 403
        
        # Générer une référence unique
        annee = datetime.now().year
        count = Risque.query.filter(
            Risque.reference.like(f'RIS-{annee}-%'),
            Risque.client_id == current_user.client_id
        ).count()
        reference = f"RIS-{annee}-{count + 1:04d}"
        
        # Créer le risque
        risque = Risque(
            reference=reference,
            intitule=risque_biblio.intitule,
            description=risque_biblio.description,
            categorie=risque_biblio.categorie,
            cartographie_id=cartographie_id,
            client_id=current_user.client_id,
            created_by=current_user.id
        )
        
        db.session.add(risque)
        
        # Incrémenter le compteur d'utilisations
        risque_biblio.nb_utilisations = (risque_biblio.nb_utilisations or 0) + 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Risque "{risque_biblio.intitule}" ajouté avec succès',
            'risque_id': risque.id,
            'redirect_url': url_for('detail_risque', id=risque.id)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bibliotheque-risques/secteurs', methods=['GET'])
@login_required
def api_bibliotheque_risques_secteurs():
    """Récupérer la liste des secteurs avec leurs directions"""
    
    secteurs = SecteurActivite.query.filter_by(est_actif=True).order_by(SecteurActivite.ordre).all()
    
    result = []
    for secteur in secteurs:
        directions = DirectionSecteur.query.filter_by(
            secteur_id=secteur.id,
            est_actif=True
        ).order_by(DirectionSecteur.ordre).all()
        
        result.append({
            'id': secteur.id,
            'code': secteur.code,
            'nom': secteur.nom,
            'icone': secteur.icone,
            'couleur': secteur.couleur,
            'directions': [{
                'id': d.id,
                'nom': d.nom,
                'nb_risques': BibliothequeRisque.query.filter_by(direction_id=d.id).count()
            } for d in directions]
        })
    
    return jsonify({'success': True, 'secteurs': result})


@app.route('/api/risques/cartographie/<int:cartographie_id>')
@login_required
def api_risques_par_cartographie(cartographie_id):
    """API pour récupérer les risques d'une cartographie spécifique"""
    cartographie = Cartographie.query.get_or_404(cartographie_id)
    risques = Risque.query.filter_by(cartographie_id=cartographie_id, is_archived=False).all()
    
    risques_data = []
    for risque in risques:
        derniere_eval = EvaluationRisque.query.filter_by(risque_id=risque.id).order_by(EvaluationRisque.created_at.desc()).first()
        
        risque_info = {
            'id': risque.id,
            'reference': risque.reference,
            'intitule': risque.intitule,
            'categorie': risque.categorie,
            'cartographie_nom': cartographie.nom,
            'evaluation': {
                'niveau_risque': derniere_eval.niveau_risque if derniere_eval else 'Non évalué',
                'score': derniere_eval.score_risque if derniere_eval else 0,
                'impact': derniere_eval.impact if derniere_eval else None,
                'probabilite': derniere_eval.probabilite if derniere_eval else None
            } if derniere_eval else None
        }
        risques_data.append(risque_info)
    
    return jsonify(risques_data)


@app.route('/demande-reevaluation/<int:demande_id>/valider', methods=['POST'])
@login_required
def valider_demande_reevaluation(demande_id):
    """Valider une demande de réévaluation et créer l'évaluation"""
    from models import DemandeReevaluation, Notification, User, PlanAction, EvaluationRisque, db
    from datetime import datetime, timedelta
    
    demande = get_client_object_or_404(DemandeReevaluation, demande_id)
    
    # Vérifier les permissions
    _ok, _pourquoi = _peut_decider_risque(getattr(demande, 'demandeur_id', None) or getattr(demande, 'created_by', None))
    if not _ok:
        flash(_pourquoi, 'error')
        return redirect(url_for('liste_demandes_reevaluation'))
    
    # Vérifier que la demande est en attente
    if demande.statut != 'en_attente':
        flash('Cette demande n\'est plus en attente de validation', 'error')
        return redirect(url_for('detail_demande_reevaluation', demande_id=demande.id))
    
    commentaire = request.form.get('commentaire', '').strip()
    
    success, result = demande.valider(current_user.id, commentaire)
    
    if success:
        nouvelle_evaluation = result
        
        # Mettre à jour le constat
        if demande.constat:
            demande.constat.reevaluation_statut = 'validee'
            demande.constat.updated_at = datetime.utcnow()
        
        # Si le risque devient critique, créer un plan d'action automatique
        if demande.niveau_risque_propose == 'Critique':
            plan_action = PlanAction(
                reference=f"PA-REEVAL-{demande.id}",
                nom=f"Plan d'action suite réévaluation {demande.risque.reference}",
                description=f"Plan d'action généré automatiquement suite à la réévaluation du risque {demande.risque.reference}.\n"
                            f"Nouveau niveau: Critique (était {demande.risque.niveau_criticite or 'Non défini'})\n"
                            f"Recommandations: {', '.join([r['message'] for r in demande.recommandations_generees])}",
                risque_id=demande.risque_id,
                priorite='haute',
                statut='en_cours',
                date_debut=_aujourdhui(),
                date_fin_prevue=_aujourdhui() + timedelta(days=30),
                created_by=current_user.id,
                client_id=current_user.client_id,
                demande_reevaluation_id=demande.id,
                # Jamais de plan sans responsable : le responsable du risque, à défaut le valideur.
                responsable_id=(getattr(demande.risque, 'responsable_id', None)
                                or getattr(demande.risque, 'proprietaire_id', None) or current_user.id)
            )
            db.session.add(plan_action)
        
        # Notifier l'auditeur
        notification = Notification(
            destinataire_id=demande.demandeur_id,
            type_notification='reevaluation_validee',
            titre=f"✅ Réévaluation validée: {demande.risque.reference}",
            message=f"Votre demande de réévaluation pour le risque {demande.risque.reference} a été validée.\n"
                    f"Nouveau niveau: {demande.niveau_risque_propose}\n"
                    f"Score: {demande.score_propose}",
            entite_type='demande_reevaluation',
            entite_id=demande.id,
            client_id=current_user.client_id
        )
        db.session.add(notification)
        
        db.session.commit()
        
        flash(f'✅ Demande validée - Évaluation créée (Réf: {nouvelle_evaluation.id})', 'success')
        return redirect(url_for('evaluer_risque_triphase', 
                               id=demande.risque_id, 
                               demande_reevaluation_id=demande.id,
                               audit_id=demande.audit_id))
    else:
        flash(f'❌ Erreur: {result}', 'error')
        return redirect(url_for('detail_demande_reevaluation', demande_id=demande.id))


@app.route('/demande-reevaluation/<int:demande_id>/rejeter', methods=['POST'])
@login_required
def rejeter_demande_reevaluation(demande_id):
    """Rejeter une demande de réévaluation"""
    from models import DemandeReevaluation, Notification, User, db
    from datetime import datetime
    
    demande = get_client_object_or_404(DemandeReevaluation, demande_id)
    
    # Vérifier les permissions
    _ok, _pourquoi = _peut_decider_risque(getattr(demande, 'demandeur_id', None) or getattr(demande, 'created_by', None))
    if not _ok:
        flash(_pourquoi, 'error')
        return redirect(url_for('liste_demandes_reevaluation'))
    
    commentaire = request.form.get('commentaire', '').strip()
    
    if not commentaire:
        flash('Un commentaire est obligatoire pour le rejet', 'error')
        return redirect(url_for('detail_demande_reevaluation', demande_id=demande.id))
    
    if demande.rejeter(current_user.id, commentaire):
        # Mettre à jour le constat
        if demande.constat:
            demande.constat.reevaluation_statut = 'rejetee'
            demande.constat.updated_at = datetime.utcnow()
        
        # Notifier l'auditeur
        notification = Notification(
            destinataire_id=demande.demandeur_id,
            type_notification='reevaluation_rejetee',
            titre=f"❌ Réévaluation rejetée: {demande.risque.reference}",
            message=f"Votre demande de réévaluation pour le risque {demande.risque.reference} a été rejetée.\n"
                    f"Motif: {commentaire}",
            entite_type='demande_reevaluation',
            entite_id=demande.id,
            client_id=current_user.client_id
        )
        db.session.add(notification)
        
        db.session.commit()
        flash('✅ Demande rejetée', 'warning')
    else:
        flash('❌ Erreur lors du rejet', 'error')
    
    return redirect(url_for('detail_demande_reevaluation', demande_id=demande.id))


@app.route('/risque/<int:risque_id>/valider', methods=['POST'])
@login_required
def valider_nouveau_risque(risque_id):
    """Valider un nouveau risque proposé"""
    from models import Risque, Notification, User, db
    from datetime import datetime
    
    risque = get_client_object_or_404(Risque, risque_id)
    
    # Vérifier les permissions
    _ok, _pourquoi = _peut_decider_risque(getattr(risque, 'created_by', None))
    if not _ok:
        flash(_pourquoi, 'error')
        return redirect(url_for('detail_cartographie', id=risque.cartographie_id))
    
    # Vérifier que le risque est en validation
    if risque.statut != 'en_validation':
        flash('Ce risque n\'est pas en attente de validation', 'error')
        return redirect(url_for('detail_cartographie', id=risque.cartographie_id))
    
    # Activer le risque
    risque.statut = 'actif'
    risque.updated_at = datetime.utcnow()
    
    # Mettre à jour la métadonnée
    if risque.metadonnees:
        risque.metadonnees['date_validation'] = datetime.utcnow().isoformat()
        marquer_json_modifie(risque, 'metadonnees')
        risque.metadonnees['valide_par'] = current_user.username
        marquer_json_modifie(risque, 'metadonnees')
    
    # Récupérer la demande associée
    demande = DemandeReevaluation.query.filter_by(risque_id=risque_id, statut='en_attente').first()
    if demande:
        demande.statut = 'validee'
        demande.date_validation = datetime.utcnow()
        demande.validateur_id = current_user.id
    
    db.session.commit()
    
    flash(f'✅ Risque {risque.reference} validé et intégré à la cartographie', 'success')
    return redirect(url_for('detail_cartographie', id=risque.cartographie_id))


@app.route('/risque/<int:risque_id>/rejeter', methods=['POST'])
@login_required
def rejeter_nouveau_risque(risque_id):
    """Rejeter un nouveau risque proposé"""
    from models import Risque, Notification, User, db
    from datetime import datetime
    
    risque = get_client_object_or_404(Risque, risque_id)
    
    # Vérifier les permissions
    _ok, _pourquoi = _peut_decider_risque(getattr(risque, 'created_by', None))
    if not _ok:
        flash(_pourquoi, 'error')
        return redirect(url_for('detail_cartographie', id=risque.cartographie_id))
    
    # Vérifier que le risque est en validation
    if risque.statut != 'en_validation':
        flash('Ce risque n\'est pas en attente de validation', 'error')
        return redirect(url_for('detail_cartographie', id=risque.cartographie_id))
    
    # Récupérer le motif
    motif = request.form.get('motif', '').strip()
    if not motif:
        flash('Un motif de rejet est obligatoire', 'error')
        return redirect(url_for('detail_cartographie', id=risque.cartographie_id))
    
    # Archiver le risque (soft delete)
    risque.is_archived = True
    risque.archived_at = datetime.utcnow()
    risque.archived_by = current_user.id
    risque.archive_reason = motif
    risque.statut = 'rejete'
    
    # Récupérer la demande associée
    demande = DemandeReevaluation.query.filter_by(risque_id=risque_id, statut='en_attente').first()
    if demande:
        demande.statut = 'rejetee'
        demande.date_traitement = datetime.utcnow()
        demande.validateur_id = current_user.id
        demande.commentaire_validation = motif
    
    db.session.commit()
    
    flash(f'❌ Risque {risque.reference} rejeté', 'warning')
    return redirect(url_for('detail_cartographie', id=risque.cartographie_id))


@app.route('/demandes-reevaluation')
@login_required
def liste_demandes_reevaluation():
    """Liste toutes les demandes de réévaluation"""
    from models import DemandeReevaluation, User, db
    from sqlalchemy import or_
    
    if not current_user.has_permission('can_manage_risks'):
        flash('Permission requise', 'error')
        return redirect(url_for('dashboard'))
    
    statut = request.args.get('statut', '')
    recherche = request.args.get('recherche', '')
    cartographie_id = request.args.get('cartographie_id', type=int)
    
    query = DemandeReevaluation.query.filter_by(client_id=current_user.client_id)
    
    # Filtrer par cartographie
    if cartographie_id:
        from models import Risque
        risques_ids = get_client_filter(Risque)\
            .filter_by(cartographie_id=cartographie_id, is_archived=False)\
            .with_entities(Risque.id)\
            .all()
        risque_ids = [r[0] for r in risques_ids]
        if risque_ids:
            query = query.filter(DemandeReevaluation.risque_id.in_(risque_ids))
        else:
            query = query.filter(DemandeReevaluation.risque_id == -1)  # Aucun résultat
    
    if statut:
        query = query.filter_by(statut=statut)
    
    if recherche:
        query = query.filter(
            or_(
                DemandeReevaluation.titre.ilike(f'%{recherche}%'),
                DemandeReevaluation.reference.ilike(f'%{recherche}%'),
                DemandeReevaluation.justification.ilike(f'%{recherche}%')
            )
        )
    
    # liste découpée en pages (egalyx/pagination.py) ; compteurs calculés par la base
    from egalyx.pagination import paginer
    page = paginer(query.order_by(DemandeReevaluation.date_demande.desc()))
    demandes = page.items
    
    # Statistiques
    stats = {
        'total': query.count(),
        'en_attente': query.filter_by(statut='en_attente').count(),
        'validees': query.filter_by(statut='validee').count(),
        'rejetees': query.filter_by(statut='rejetee').count(),
        'annulees': query.filter_by(statut='annulee').count()
    }
    
    # Calculer le temps moyen de traitement
    temps_moyen = 0
    demandes_traitees = query.filter(DemandeReevaluation.statut.in_(['validee', 'rejetee']),
                                     DemandeReevaluation.date_validation.isnot(None)).all()
    if demandes_traitees:
        temps_total = sum((d.date_validation - d.date_demande).total_seconds() / 3600 for d in demandes_traitees)
        temps_moyen = round(temps_total / len(demandes_traitees), 1)
    
    return render_template('reevaluation/liste.html',
                         demandes=demandes,
                         page=page,
                         stats=stats,
                         statut=statut,
                         recherche=recherche,
                         temps_moyen=temps_moyen,
                         cartographie_id=cartographie_id,
                         current_user=current_user)


@app.route('/demande-reevaluation/<int:demande_id>')
@login_required
def detail_demande_reevaluation(demande_id):
    """Affiche le détail d'une demande de réévaluation"""
    from models import DemandeReevaluation, User, db
    
    demande = get_client_object_or_404(DemandeReevaluation, demande_id)
    
    # Vérifier les permissions
    if not (current_user.has_permission('can_manage_risks') or 
            current_user.id == demande.demandeur_id):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_demandes_reevaluation'))
    
    # Récupérer le constat associé
    constat = demande.constat if demande.constat else None
    
    # Récupérer l'audit associé
    audit = demande.audit if demande.audit else None
    
    # Récupérer les plans d'action générés
    plans_action = []
    if demande.id:
        from models import PlanAction
        plans_action = PlanAction.query.filter_by(
            demande_reevaluation_id=demande.id,
            client_id=current_user.client_id
        ).all()
    
    return render_template('reevaluation/detail.html',
                         demande=demande,
                         constat=constat,
                         audit=audit,
                         plans_action=plans_action,
                         current_user=current_user)


@app.route('/demande-reevaluation/<int:demande_id>/annuler-validation', methods=['POST'])
@login_required
def annuler_validation_reevaluation(demande_id):
    """Annuler la validation d'une demande de réévaluation"""
    from models import DemandeReevaluation, Notification, User, db
    from datetime import datetime
    
    demande = get_client_object_or_404(DemandeReevaluation, demande_id)
    
    # Vérifier les permissions
    if not current_user.role in ['admin', 'responsable_risques', 'manager', 'super_admin']:
        flash('Vous n\'avez pas les droits pour annuler cette validation', 'error')
        return redirect(url_for('detail_demande_reevaluation', demande_id=demande.id))
    
    # Vérifier que la demande est validée ou rejetée
    if demande.statut not in ['validee', 'rejetee']:
        flash('Cette demande n\'est pas dans un état validé ou rejeté', 'error')
        return redirect(url_for('detail_demande_reevaluation', demande_id=demande.id))
    
    # Récupérer le commentaire
    commentaire = request.form.get('commentaire', '').strip()
    ancien_statut = demande.statut
    
    # 🔥 ANNULER LA VALIDATION
    demande.statut = 'en_attente'
    demande.date_validation = None
    demande.validateur_id = None
    demande.commentaire_validation = commentaire or f"Validation annulée par {current_user.username}"
    demande.updated_at = datetime.utcnow()
    
    # Si c'était une validation, supprimer/annuler l'évaluation associée
    if ancien_statut == 'validee':
        from models import EvaluationRisque
        evaluation = EvaluationRisque.query.filter_by(
            demande_reevaluation_id=demande.id
        ).first()
        if evaluation:
            # Marquer comme annulée
            evaluation.statut_validation = 'annulee'
            evaluation.commentaire_pre_evaluation = (evaluation.commentaire_pre_evaluation or '') + \
                f"\n\n⚠️ ANNULÉE par {current_user.username} le {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} - Motif: {commentaire or 'Non spécifié'}"
    
    # Mettre à jour le constat associé
    if demande.constat:
        demande.constat.reevaluation_statut = 'demandee'
        demande.constat.updated_at = datetime.utcnow()
    
    # Notifier le demandeur
    notification = Notification(
        destinataire_id=demande.demandeur_id,
        type_notification='reevalidation_annulee',
        titre=f"🔄 Validation annulée: {demande.risque.reference}",
        message=f"La validation de votre demande de réévaluation pour le risque {demande.risque.reference} a été annulée par {current_user.username}.\n"
                f"Motif: {commentaire or 'Non spécifié'}",
        entite_type='demande_reevaluation',
        entite_id=demande.id,
        client_id=current_user.client_id,
        urgence='info'
    )
    db.session.add(notification)
    
    db.session.commit()
    
    flash(f'✅ Validation annulée - La demande est de nouveau "En attente"', 'warning')
    
    # Rediriger vers la page de détail ou la liste selon la provenance
    referrer = request.referrer or url_for('liste_demandes_reevaluation')
    if '/detail/' in referrer:
        return redirect(url_for('detail_demande_reevaluation', demande_id=demande.id))
    else:
        return redirect(url_for('liste_demandes_reevaluation'))


@app.route('/api/risques/liste')
@login_required
def api_liste_risques():
    """Récupérer la liste des risques disponibles pour association"""
    from models import Risque, EvaluationRisque
    from sqlalchemy import desc
    
    # Récupérer les risques du client
    risques = get_client_filter(Risque).filter_by(is_archived=False).all()
    
    risques_data = []
    for risque in risques:
        # Récupérer la dernière évaluation
        derniere_eval = EvaluationRisque.query.filter_by(
            risque_id=risque.id
        ).order_by(desc(EvaluationRisque.created_at)).first()
        
        risques_data.append({
            'id': risque.id,
            'reference': risque.reference,
            'intitule': risque.intitule,
            'description': risque.description or '',
            'categorie': risque.categorie or '',
            'niveau_criticite': derniere_eval.niveau_risque if derniere_eval else 'Non évalué',
            'score': derniere_eval.score_risque if derniere_eval else 0,
            'cartographie_id': risque.cartographie_id,
            'cartographie_nom': risque.cartographie.nom if risque.cartographie else 'Non définie',
            'created_by': risque.createur.username if risque.createur else 'Système',
            'created_at': risque.created_at.strftime('%d/%m/%Y') if risque.created_at else ''
        })
    
    return jsonify({'success': True, 'risques': risques_data})


@app.route('/api/risques/creer-demo')
@login_required
def creer_risque_demo():
    """Créer un risque de démonstration pour tester"""
    from models import Risque, Cartographie
    
    # Vérifier si une cartographie existe
    cartographie = get_client_filter(Cartographie).filter_by(is_archived=False).first()
    if not cartographie:
        return jsonify({'success': False, 'error': 'Aucune cartographie disponible'}), 400
    
    # Compter les risques existants
    count = get_client_filter(Risque).count()
    reference = f"RIS-DEMO-{count + 1:04d}"
    
    risque = Risque(
        reference=reference,
        intitule="Risque de démonstration",
        description="Ce risque a été créé automatiquement pour tester l'association",
        categorie="operationnel",
        cartographie_id=cartographie.id,
        client_id=current_user.client_id,
        created_by=current_user.id
    )
    
    db.session.add(risque)
    db.session.commit()
    
    return jsonify({'success': True, 'risque': {'id': risque.id, 'reference': risque.reference, 'intitule': risque.intitule}})


@app.route('/api/cartographies/liste')
@login_required
def api_cartographies_liste():
    """Récupérer la liste des cartographies pour créer un risque"""
    from models import Cartographie
    
    # Utiliser get_client_filter pour le multi-tenant
    cartographies = get_client_filter(Cartographie).filter_by(is_archived=False).all()
    
    # Compter le nombre de risques pour chaque cartographie (optionnel)
    cartographies_data = []
    for c in cartographies:
        # Compter les risques non archivés de cette cartographie
        nb_risques = 0
        if hasattr(c, 'risques'):
            try:
                # SQLAlchemy count() sans paramètre
                nb_risques = c.risques.filter_by(is_archived=False).count()
            except:
                nb_risques = len([r for r in c.risques if not getattr(r, 'is_archived', False)])
        
        cartographies_data.append({
            'id': c.id,
            'nom': c.nom,
            'description': c.description or '',
            'nb_risques': nb_risques,
            'date_creation': c.created_at.strftime('%d/%m/%Y') if c.created_at else None
        })
    
    return jsonify({
        'success': True,
        'cartographies': cartographies_data
    })


@app.route('/api/risques/creer-rapide', methods=['POST'])
@login_required
def api_creer_risque_rapide():
    """Créer un risque rapide sans test associé"""
    from models import Risque, Cartographie
    
    data = request.get_json()
    
    intitule = data.get('intitule')
    if not intitule:
        return jsonify({'success': False, 'error': 'Intitulé requis'}), 400
    
    cartographie_id = data.get('cartographie_id')
    if not cartographie_id:
        return jsonify({'success': False, 'error': 'Veuillez sélectionner une cartographie'}), 400
    
    cartographie = get_client_object_or_404(Cartographie, cartographie_id)
    
    # Générer référence unique
    count = Risque.query.filter_by(client_id=current_user.client_id, is_archived=False).count() + 1
    reference = f"RIS-{count:04d}"
    
    nouveau_risque = Risque(
        reference=reference,
        intitule=intitule,
        description=data.get('description', ''),
        categorie=data.get('categorie', ''),
        cartographie_id=cartographie_id,
        client_id=current_user.client_id,
        created_by=current_user.id
    )
    
    db.session.add(nouveau_risque)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Risque "{intitule}" créé',
        'risque': {
            'id': nouveau_risque.id,
            'reference': nouveau_risque.reference,
            'intitule': nouveau_risque.intitule,
            'categorie': nouveau_risque.categorie
        }
    })


@app.route('/api/risques/<int:risque_id>')
@login_required
def api_risque_detail(risque_id):
    """Récupérer les détails d'un risque"""
    from models import Risque, EvaluationRisque
    from sqlalchemy import desc
    
    risque = get_client_object_or_404(Risque, risque_id)
    
    derniere_eval = EvaluationRisque.query.filter_by(
        risque_id=risque_id
    ).order_by(desc(EvaluationRisque.created_at)).first()
    
    niveau = 'Non évalué'
    score = 0
    if derniere_eval:
        niveau = derniere_eval.niveau_risque or 'Non évalué'
        score = derniere_eval.score_risque or 0
    
    return jsonify({
        'success': True,
        'risque': {
            'id': risque.id,
            'reference': risque.reference,
            'intitule': risque.intitule,
            'description': risque.description or '',
            'categorie': risque.categorie or '',
            'niveau_criticite': niveau,
            'score': score,
            'cartographie_id': risque.cartographie_id,
            'cartographie_nom': risque.cartographie.nom if risque.cartographie else 'Non définie',
            'created_by': risque.createur.username if risque.createur else 'Système',
            'created_at': risque.created_at.strftime('%d/%m/%Y') if risque.created_at else '',
            'mots_cles': getattr(risque, 'mots_cles', ''),
            'metriques_associees': getattr(risque, 'metriques_associees', '')
        }
    })


@app.route('/api/risques/processus/<int:processus_id>')
@login_required
def api_risques_par_processus(processus_id):
    processus = Processus.query.get_or_404(processus_id)
    risques = Risque.query.filter(Risque.processus_concerne.ilike(f"%{processus.nom}%")).all()
    return jsonify([{'id': r.id, 'reference': r.reference, 'intitule': r.intitule} for r in risques])


@app.route('/cartographie/<int:cartographie_id>/definir-campagne-active/<int:campagne_id>', methods=['POST'])
@login_required
def definir_campagne_active(cartographie_id, campagne_id):
    """Définit la campagne active pour une cartographie"""
    
    cartographie = Cartographie.query.get_or_404(cartographie_id)
    
    if not check_client_access(cartographie):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_cartographies'))
    
    # Vérifier les permissions
    if not current_user.has_permission('can_manage_risks') and current_user.role != 'admin':
        flash('Vous n\'avez pas la permission de gérer les campagnes', 'error')
        return redirect(url_for('liste_cartographies'))
    
    campagne = CampagneEvaluation.query.get_or_404(campagne_id)
    
    if campagne.cartographie_id != cartographie_id:
        flash('❌ Cette campagne n\'appartient pas à cette cartographie', 'error')
        return redirect(url_for('detail_cartographie', id=cartographie_id))
    
    # ✅ Définir la campagne active
    if cartographie.set_campagne_active(campagne_id):
        flash(f'✅ Campagne "{campagne.nom}" définie comme active', 'success')
    else:
        flash('❌ Erreur lors de la définition de la campagne active', 'error')
    
    return redirect(url_for('detail_cartographie', id=cartographie_id))
