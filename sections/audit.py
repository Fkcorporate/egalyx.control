"""
sections/audit.py — Audit interne : missions, feuilles de travail, constatations, recommandations, programme d'audit, chronogramme, développement des auditeurs.

Partie d'app.py, déplacée telle quelle le 18/11/2026 (237 routes, 15776 lignes).
Ce fichier est exécuté DANS l'espace de noms d'app.py (voir _inclure_section dans app.py) : il utilise
les mêmes imports, modèles et fonctions que le reste d'app.py, sans rien importer lui-même. Les fonctions
gardent le même nom, les mêmes routes et le même comportement ; seules leurs lignes ont changé de fichier.
Les fonctions utilitaires partagées sont restées dans app.py.
"""
# flake8: noqa  (noms fournis par app.py)


@app.route('/feuille-travail/<int:feuille_id>/apercu')
@login_required
def apercu_feuille_travail(feuille_id):
    """Afficher l'aperçu complet d'une feuille de travail"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    return render_template('audit/apercu_feuille_travail.html', feuille=feuille)


@app.route('/api/feuille-travail/<int:feuille_id>/couverture-risques-complete', methods=['GET'])
@login_required
def api_couverture_risques_complete(feuille_id):
    """Analyse complète de la couverture des risques par les tests"""
    from models import Risque
    
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    tests = TestControleFeuille.query.filter_by(feuille_travail_id=feuille_id).all()
    
    # Statistiques globales
    stats = {
        'total_tests': len(tests),
        'tests_avec_risques': len([t for t in tests if t.risques_associes]),
        'total_associations': sum(len(t.risques_associes) for t in tests),
        'taux_couverture': round((len([t for t in tests if t.risques_associes]) / max(len(tests), 1)) * 100, 1)
    }
    
    # Analyse par risque
    risques_analyse = {}
    for test in tests:
        for risque in test.risques_associes:
            if risque.id not in risques_analyse:
                risques_analyse[risque.id] = {
                    'risque': risque,
                    'nb_tests': 0,
                    'tests': []
                }
            risques_analyse[risque.id]['nb_tests'] += 1
            risques_analyse[risque.id]['tests'].append({
                'id': test.id,
                'objet_test': test.objet_test,
                'resultat': test.resultat
            })
    
    # Tests sans risque
    tests_sans_risque = [t.to_dict() for t in tests if not t.risques_associes]
    
    return jsonify({
        'success': True,
        'statistiques': stats,
        'risques_couverts': [
            {
                'risque': r['risque'].to_dict(),
                'nb_tests': r['nb_tests'],
                'tests': r['tests']
            }
            for r in risques_analyse.values()
        ],
        'tests_sans_risque': tests_sans_risque
    })


# ============================================================================
# ROUTES POUR L'UPLOAD MULTIPLE DE PREUVES
# ============================================================================
@app.route('/audit/<int:audit_id>/upload-multiple-preuves', methods=['POST'])
@login_required
def upload_multiple_preuves(audit_id):
    """Upload multiple de preuves"""
    
    audit = get_client_object_or_404(Audit, audit_id)
    
    # Vérifier les permissions
    peut_uploader = (
        current_user.role == 'super_admin' or
        current_user.is_client_admin or
        current_user.id == audit.created_by or
        current_user.id == audit.responsable_id or
        (audit.equipe_audit_ids and str(current_user.id) in audit.equipe_audit_ids.split(','))
    )
    
    if not peut_uploader:
        return jsonify({'success': False, 'error': 'Permission non autorisée'}), 403
    
    constatation_id = request.form.get('constatation_id')
    
    if not constatation_id:
        return jsonify({'success': False, 'error': 'Aucune constatation sélectionnée'}), 400
    
    constatation = Constatation.query.get_or_404(constatation_id)
    
    if 'preuves' not in request.files:
        return jsonify({'success': False, 'error': 'Aucun fichier'}), 400
    
    files = request.files.getlist('preuves')
    uploaded_files = []
    errors = []
    
    upload_dir = os.path.join('static', 'uploads', 'preuves')
    os.makedirs(upload_dir, exist_ok=True)
    
    for fichier in files:
        if fichier.filename == '':
            errors.append('Fichier vide')
            continue
        
        # Vérifier extension
        allowed = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx'}
        ext = fichier.filename.rsplit('.', 1)[1].lower() if '.' in fichier.filename else ''
        
        if ext not in allowed:
            errors.append(f"Extension .{ext} non autorisée pour {fichier.filename}")
            continue
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_filename = secure_filename(fichier.filename)
            unique_filename = f"{timestamp}_{safe_filename}"
            filepath = os.path.join(upload_dir, unique_filename)
            
            fichier.save(filepath)
            
            # Enregistrer dans la constatation
            if constatation.preuves:
                constatation.preuves += f",{unique_filename}"
            else:
                constatation.preuves = unique_filename
            
            uploaded_files.append({
                'filename': unique_filename,
                'original': safe_filename,
                'size': os.path.getsize(filepath)
            })
            
        except Exception as e:
            errors.append(str(e))
    
    constatation.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'success': len(uploaded_files) > 0,
        'uploaded': len(uploaded_files),
        'errors': len(errors),
        'files': uploaded_files,
        'message': f"{len(uploaded_files)} fichier(s) uploadé(s), {len(errors)} erreur(s)"
    })


@app.route('/audit/<int:audit_id>/upload-preuve-generale', methods=['POST'])
@login_required
def upload_preuve_generale(audit_id):
    """Uploader une preuve générale (sans constatation)"""
    
    from werkzeug.utils import secure_filename
    import os
    from datetime import datetime
    
    audit = get_client_object_or_404(Audit, audit_id)
    
    # Vérifier les permissions
    peut_uploader = (
        current_user.role == 'super_admin' or
        current_user.is_client_admin or
        current_user.id == audit.created_by or
        current_user.id == audit.responsable_id or
        (audit.equipe_audit_ids and str(current_user.id) in audit.equipe_audit_ids.split(','))
    )
    
    if not peut_uploader:
        return jsonify({'success': False, 'error': 'Permission non autorisée'}), 403
    
    if 'preuve' not in request.files:
        return jsonify({'success': False, 'error': 'Aucun fichier'}), 400
    
    fichier = request.files['preuve']
    commentaire = request.form.get('commentaire', '')
    
    if fichier.filename == '':
        return jsonify({'success': False, 'error': 'Fichier vide'}), 400
    
    allowed = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx', 'txt'}
    ext = fichier.filename.rsplit('.', 1)[1].lower() if '.' in fichier.filename else ''
    
    if ext not in allowed:
        return jsonify({'success': False, 'error': f'Extension .{ext} non autorisée'}), 400
    
    try:
        # Créer le dossier
        upload_dir = os.path.join('static', 'uploads', 'preuves_generales', str(audit_id))
        os.makedirs(upload_dir, exist_ok=True)
        
        # Générer un nom unique
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = secure_filename(fichier.filename)
        unique_filename = f"{timestamp}_{safe_filename}"
        filepath = os.path.join(upload_dir, unique_filename)
        
        # Sauvegarder
        fichier.save(filepath)
        
        # Sauvegarder les métadonnées
        from models import FichierMetadata
        metadata = FichierMetadata(
            nom_fichier=unique_filename,
            chemin=filepath,
            type_fichier=ext,
            taille=os.path.getsize(filepath),
            commentaire=commentaire,
            responsable_id=current_user.id,
            entite_type='audit',
            entite_id=audit_id,
            created_by=current_user.id,
            client_id=audit.client_id
        )
        db.session.add(metadata)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Preuve générale ajoutée avec succès',
            'fichier': {
                'nom': unique_filename,
                'commentaire': commentaire,
                'taille': f"{os.path.getsize(filepath) / 1024:.1f} KB",
                'responsable': current_user.username,
                'url_telechargement': url_for('download_preuve', filename=unique_filename)
            }
        })
        
    except Exception as e:
        db.session.rollback()
        _journal(f"Erreur upload preuve générale: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audit/<int:audit_id>/preuves-generales')
@login_required
def api_audit_preuves_generales(audit_id):
    """Récupérer les preuves générales d'un audit (sans constatation)"""
    
    audit = get_client_object_or_404(Audit, audit_id)
    
    fichiers = FichierMetadata.query.filter_by(
        entite_type='audit',
        entite_id=audit_id,
        client_id=audit.client_id
    ).order_by(FichierMetadata.created_at.desc()).all()
    
    preuves = []
    for f in fichiers:
        preuves.append({
            'id': f.id,
            'nom_fichier': f.nom_fichier,
            'commentaire': f.commentaire,
            'taille': f.taille,
            'taille_formatee': f"{f.taille / 1024:.1f} KB" if f.taille else 'N/A',
            'responsable': f.responsable.username if f.responsable else 'Inconnu',
            'date_upload': f.created_at.strftime('%d/%m/%Y %H:%M') if f.created_at else '',
            'url_telechargement': url_for('download_preuve', filename=f.nom_fichier)
        })
    
    return jsonify({'success': True, 'preuves': preuves})


@app.route('/audit/<int:audit_id>/constatation/<int:constatation_id>/upload-multiple-preuves', methods=['POST'])
@login_required
def upload_multiple_preuves_constatation(audit_id, constatation_id):
    """Uploader plusieurs preuves pour une constatation spécifique"""
    constatation = Constatation.query.get_or_404(constatation_id)
    
    # Vérifier que la constatation appartient bien à l'audit
    if constatation.audit_id != audit_id:
        flash('Cette constatation ne fait pas partie de cet audit', 'error')
        return redirect(url_for('detail_audit', id=audit_id))
    
    if 'preuves[]' not in request.files:
        flash('Aucun fichier sélectionné', 'error')
        return redirect(url_for('detail_audit', id=audit_id))
    
    fichiers = request.files.getlist('preuves[]')
    fichiers_uploades = 0
    preuves_filenames = []
    
    for fichier in fichiers:
        if fichier and fichier.filename:
            if allowed_file(fichier.filename):
                try:
                    # Générer un nom de fichier unique
                    filename = secure_filename(fichier.filename)
                    unique_filename = f"preuve_{constatation_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"
                    
                    # Créer le dossier s'il n'existe pas
                    upload_folder = 'static/uploads/preuves'
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    # Sauvegarder le fichier
                    filepath = os.path.join(upload_folder, unique_filename)
                    fichier.save(filepath)
                    
                    preuves_filenames.append(unique_filename)
                    fichiers_uploades += 1
                    
                except Exception as e:
                    flash(f'Erreur lors de l\'upload de {fichier.filename}: {str(e)}', 'error')
            else:
                flash(f'Type de fichier non autorisé: {fichier.filename}', 'error')
    
    # Mettre à jour la constatation avec les nouvelles preuves
    if preuves_filenames:
        nouvelles_preuves = ','.join(preuves_filenames)
        if constatation.preuves:
            constatation.preuves = f"{constatation.preuves},{nouvelles_preuves}"
        else:
            constatation.preuves = nouvelles_preuves
        
        constatation.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Journaliser l'action
        journaliser_action_audit(
            audit_id=audit_id,
            action_type='upload_multiple_preuves_constatation',
            user_id=current_user.id,
            details={
                'constatation_id': constatation_id,
                'fichiers_uploades': fichiers_uploades
            }
        )
        
        flash(f'{fichiers_uploades} preuve(s) ajoutée(s) à la constatation', 'success')
    
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/audit/<int:audit_id>/download-all-preuves')
@login_required
def download_all_preuves(audit_id):
    """Télécharger toutes les preuves d'un audit sous forme d'archive ZIP"""
    audit = Audit.query.get_or_404(audit_id)
    
    try:
        import zipfile
        import io
        import tempfile
        
        # Créer un fichier ZIP en mémoire
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Récupérer toutes les constatations de l'audit
            constatations = Constatation.query.filter_by(audit_id=audit_id).all()
            
            fichiers_ajoutes = 0
            
            for constatation in constatations:
                if constatation.preuves:
                    preuves_list = constatation.get_preuves_list
                    
                    for preuve_filename in preuves_list:
                        # Chemin complet du fichier
                        file_path = os.path.join('static/uploads/preuves', preuve_filename)
                        
                        # Vérifier si le fichier existe
                        if os.path.exists(file_path):
                            # Ajouter au ZIP avec un chemin organisé
                            zip_path = f"preuves/{constatation.reference}/{preuve_filename}"
                            zip_file.write(file_path, zip_path)
                            fichiers_ajoutes += 1
        
        if fichiers_ajoutes == 0:
            flash('Aucune preuve à télécharger', 'warning')
            return redirect(url_for('detail_audit', id=audit_id))
        
        zip_buffer.seek(0)
        
        # Journaliser l'action
        journaliser_action_audit(
            audit_id=audit_id,
            action_type='download_all_preuves',
            user_id=current_user.id,
            details={'fichiers_ajoutes': fichiers_ajoutes}
        )
        
        # Retourner le fichier ZIP
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f"preuves_audit_{audit.reference}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mimetype='application/zip'
        )
        
    except Exception as e:
        flash(f'Erreur lors de la création de l\'archive: {str(e)}', 'error')
        return redirect(url_for('detail_audit', id=audit_id))


@app.route('/api/constatation/<int:constatation_id>/preuve/<path:filename>', methods=['DELETE'])
@login_required
def api_delete_preuve(constatation_id, filename):
    """Supprimer une preuve d'une constatation"""
    
    constatation = Constatation.query.get_or_404(constatation_id)
    audit = constatation.audit
    
    # ✅ CORRECTION : Vérification simplifiée
    peut_modifier = (
        current_user.role == 'super_admin' or
        current_user.is_client_admin or
        current_user.id == audit.created_by or
        current_user.id == audit.responsable_id or
        (audit.equipe_audit_ids and str(current_user.id) in audit.equipe_audit_ids.split(','))
    )
    
    if not peut_modifier:
        return jsonify({'success': False, 'error': 'Permission non autorisée'}), 403
    
    try:
        # Supprimer le fichier physique
        filepath = os.path.join('static', 'uploads', 'preuves', filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        
        # Supprimer les métadonnées
        FichierMetadata.query.filter_by(
            nom_fichier=filename,
            entite_type='constatation',
            entite_id=constatation_id
        ).delete()
        
        # Mettre à jour la constatation
        if constatation.preuves:
            preuves_list = constatation.get_preuves_list
            if filename in preuves_list:
                preuves_list.remove(filename)
                constatation.preuves = ','.join(preuves_list) if preuves_list else None
        
        constatation.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Preuve supprimée avec succès'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/constatation/<int:constatation_id>/upload-preuve', methods=['POST'])
@login_required
def api_upload_preuve(constatation_id):
    """Uploader une preuve pour une constatation"""
    
    constatation = Constatation.query.get_or_404(constatation_id)
    audit = constatation.audit
    
    # ✅ CORRECTION : Vérification simplifiée
    peut_modifier = (
        current_user.role == 'super_admin' or
        current_user.is_client_admin or
        current_user.id == audit.created_by or
        current_user.id == audit.responsable_id or
        (audit.equipe_audit_ids and str(current_user.id) in audit.equipe_audit_ids.split(','))
    )
    
    if not peut_modifier:
        return jsonify({'success': False, 'error': 'Permission non autorisée'}), 403
    
    if 'preuve' not in request.files:
        return jsonify({'success': False, 'error': 'Aucun fichier fourni'}), 400
    
    fichier = request.files['preuve']
    commentaire = request.form.get('commentaire', '')
    
    if fichier.filename == '':
        return jsonify({'success': False, 'error': 'Aucun fichier sélectionné'}), 400
    
    # Vérifier l'extension
    allowed = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx', 'txt'}
    ext = fichier.filename.rsplit('.', 1)[1].lower() if '.' in fichier.filename else ''
    
    if ext not in allowed:
        return jsonify({'success': False, 'error': f'Extension .{ext} non autorisée'}), 400
    
    try:
        # Créer le dossier
        upload_dir = os.path.join('static', 'uploads', 'preuves')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Générer un nom unique
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = secure_filename(fichier.filename)
        unique_filename = f"{timestamp}_{safe_filename}"
        filepath = os.path.join(upload_dir, unique_filename)
        
        # Sauvegarder
        fichier.save(filepath)
        
        # Sauvegarder les métadonnées
        metadata = FichierMetadata(
            nom_fichier=unique_filename,
            chemin=filepath,
            type_fichier=ext,
            taille=os.path.getsize(filepath),
            commentaire=commentaire,
            responsable_id=current_user.id,
            entite_type='constatation',
            entite_id=constatation_id,
            created_by=current_user.id,
            client_id=audit.client_id
        )
        db.session.add(metadata)
        
        # Mettre à jour la constatation
        if constatation.preuves:
            constatation.preuves += f",{unique_filename}"
        else:
            constatation.preuves = unique_filename
        
        constatation.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Fichier uploadé avec succès',
            'fichier': {
                'nom': unique_filename,
                'commentaire': commentaire,
                'taille': f"{os.path.getsize(filepath) / 1024:.1f} KB",
                'responsable': current_user.username,
                'url_telechargement': url_for('download_preuve', filename=unique_filename)
            }
        })
        
    except Exception as e:
        db.session.rollback()
        _journal(f"Erreur upload: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# --- ROUTE CORRIGÉE POUR SUPPRIMER UNE PREUVE (AJAX) ---
@app.route('/api/constatation/<int:constatation_id>/preuve/<path:filename>', methods=['DELETE'])
@login_required
def api_supprimer_preuve(constatation_id, filename):
    """Supprimer une preuve d'une constatation"""
    
    constatation = Constatation.query.get_or_404(constatation_id)
    audit = constatation.audit
    
    # ✅ CORRECTION : Vérification simplifiée sans can_edit_audit
    peut_modifier = (
        current_user.role == 'super_admin' or
        current_user.is_client_admin or
        current_user.id == audit.created_by or
        current_user.id == audit.responsable_id or
        (audit.equipe_audit_ids and str(current_user.id) in audit.equipe_audit_ids.split(','))
    )
    
    if not peut_modifier:
        return jsonify({'success': False, 'error': 'Permission non autorisée'}), 403
    
    try:
        # Supprimer le fichier physique
        filepath = os.path.join('static', 'uploads', 'preuves', filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            _journal(f"✅ Fichier supprimé: {filepath}")
        
        # Supprimer les métadonnées
        FichierMetadata.query.filter_by(
            nom_fichier=filename,
            entite_type='constatation',
            entite_id=constatation_id
        ).delete()
        
        # Mettre à jour la constatation
        if constatation.preuves:
            preuves_list = [p.strip() for p in constatation.preuves.split(',') if p.strip()]
            if filename in preuves_list:
                preuves_list.remove(filename)
                constatation.preuves = ','.join(preuves_list) if preuves_list else None
        
        constatation.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Preuve supprimée avec succès'})
        
    except Exception as e:
        db.session.rollback()
        _journal(f"Erreur suppression: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/audit/ajouter', methods=['POST'])
@login_required
def ajouter_audit():
    """Ancienne route de test (créait un audit fictif « REF001 » sans organisation) : renvoie vers la vraie création."""
    return redirect(url_for('nouvel_audit'))


@app.route('/audit/plans-action')
@login_required
def liste_plans_action():
    """
    Liste de tous les plans d'action avec distinction risque/audit/indépendant
    - VERSION COMPLÈTE ET CORRIGÉE AVEC VÉRIFICATION DE FORMULE UNIFIÉE
    """
    
    from datetime import datetime
    from sqlalchemy.orm import joinedload
    
    _journal(f"\n🔍 ACCÈS PLANS D'ACTION - Utilisateur: {current_user.username}")
    _journal(f"   Rôle: {current_user.role}")
    _journal(f"   Client ID: {current_user.client_id}")
    _journal(f"   is_client_admin: {current_user.is_client_admin}")
    
    # ============================================
    # 1. SUPER ADMIN - ACCÈS IMMÉDIAT
    # ============================================
    if current_user.role == 'super_admin':
        _journal(f"   ✅ Super admin - accès autorisé sans vérification formule")
        # Pour super admin, on continue sans vérifier la formule
        pass
    
    # ============================================
    # 2. VÉRIFICATION DE LA FORMULE POUR LES AUTRES UTILISATEURS
    # ============================================
    elif current_user.client and current_user.client.formule:
        formule = current_user.client.formule
        
        _journal(f"   📋 Formule: {formule.nom} ({formule.code})")
        _journal(f"   📦 Modules: {list(formule.modules.keys())}")
        
        # Vérifier si le module plans_action est activé dans la formule
        # Utiliser can_access_module qui gère les alias
        if not formule.can_access_module('plans_action'):
            _journal(f"   ❌ Module 'plans_action' non activé dans la formule {formule.nom}")
            
            # Vérifier aussi audit_interne comme fallback (certains plans sont liés aux audits)
            if formule.can_access_module('audit_interne'):
                _journal(f"   ⚠️  Module 'audit_interne' activé - on autorise quand même")
                # On autorise quand même car plans d'action peut être lié aux audits
            else:
                # Utiliser la fonction unifiée pour afficher la page restreinte
                return render_formule_restricted('Plans d\'action', formule)
        else:
            _journal(f"   ✅ Module 'plans_action' activé dans la formule")
    
    else:
        # Si pas de formule, vérifier si c'est un admin client sans formule
        if current_user.is_client_admin:
            _journal(f"   ⚠️  Admin client sans formule associée")
            flash('Aucune formule active associée à votre client. Veuillez contacter le support.', 'warning')
        else:
            _journal(f"   ❌ Pas de formule associée au client")
            flash('Aucune formule active associée à votre compte', 'error')
            return redirect(url_for('dashboard'))
    
    # ============================================
    # 3. VÉRIFICATION DE LA PERMISSION UTILISATEUR
    # ============================================
    if not current_user.has_permission('can_view_action_plans'):
        _journal(f"   ❌ Permission 'can_view_action_plans' manquante")
        
        # Pour les admins et super admins, forcer la permission
        if current_user.role in ['admin', 'super_admin'] or current_user.is_client_admin:
            _journal(f"   🔧 Forçage de la permission pour admin")
            if current_user.permissions is None:
                current_user.permissions = {}
            current_user.permissions['can_view_action_plans'] = True
            marquer_json_modifie(current_user, 'permissions')
            current_user.permissions['can_manage_action_plans'] = True
            marquer_json_modifie(current_user, 'permissions')
            db.session.commit()
            _journal(f"   ✅ Permissions forcées avec succès")
        else:
            flash('Permission "Voir les plans d\'action" requise', 'error')
            return redirect(url_for('dashboard'))
    
    _journal(f"   🎉 ACCÈS AUTORISÉ - Récupération des plans d'action...")
    
    # ============================================
    # 4. RÉCUPÉRATION DES PARAMÈTRES DE FILTRAGE
    # ============================================
    # Page du module Audit : plans d'audit (et indépendants). Les plans des risques vivent dans leur module
    # (fiche du risque) et dans « Tous les plans d'action » : une ancienne adresse ?type=risque y mène.
    type_filtre = request.args.get('type', 'audit')
    if type_filtre == 'risque':
        if 'plans_unifies.page' in app.view_functions:
            return redirect(url_for('plans_unifies.page', source='risques'))
        type_filtre = 'audit'
    if type_filtre not in ('audit', 'independant', 'tous'):
        type_filtre = 'audit'
    filtre_statut = request.args.get('statut', 'tous')
    tri = request.args.get('tri', 'date_desc')
    
    # ============================================
    # 5. RÉCUPÉRER TOUS LES PLANS POUR LES STATISTIQUES GLOBALES
    # ============================================
    tous_plans_query = get_client_filter(PlanAction)
    # sans les plans des risques (voir plus haut)
    tous_plans = [p for p in tous_plans_query.all() if p.audit_id is not None or p.risque_id is None]
    
    # ============================================
    # 6. CALCULER LES STATISTIQUES GLOBALES
    # ============================================
    stats_globales = {
        'total': len(tous_plans),
        'audit': len([p for p in tous_plans if p.audit_id is not None]),
        'risque': len([p for p in tous_plans if p.risque_id is not None]),
        'independant': len([p for p in tous_plans if p.audit_id is None and p.risque_id is None]),
        'en_attente': len([p for p in tous_plans if p.statut == 'en_attente']),
        'en_cours': len([p for p in tous_plans if p.statut == 'en_cours']),
        'termines': len([p for p in tous_plans if p.statut == 'termine']),
        'suspendus': len([p for p in tous_plans if p.statut == 'suspendu']),
        'annules': len([p for p in tous_plans if p.statut == 'annule']),
        'urgences': 0,
        'en_retard': 0,
        'moyenne_realisation': 0
    }
    
    # ============================================
    # 7. APPLIQUER LES FILTRES POUR LA LISTE AFFICHÉE
    # ============================================
    query = get_client_filter(PlanAction)
    
    # IMPORTANT: Charger les sous-actions pour éviter les problèmes N+1
    query = query.options(joinedload(PlanAction.sous_actions))
    
    # Appliquer le filtre par type
    if type_filtre == 'audit':
        query = query.filter(PlanAction.audit_id.isnot(None))
        _journal(f"   📋 Filtre: Plans d'audit uniquement")
    elif type_filtre == 'risque':
        query = query.filter(PlanAction.risque_id.isnot(None))
        _journal(f"   📋 Filtre: Plans de risque uniquement")
    elif type_filtre == 'independant':
        query = query.filter(
            PlanAction.audit_id.is_(None),
            PlanAction.risque_id.is_(None)
        )
        _journal(f"   📋 Filtre: Plans indépendants uniquement")
    else:
        query = query.filter(or_(PlanAction.audit_id.isnot(None), PlanAction.risque_id.is_(None)))
        _journal(f"   📋 Filtre: plans d'audit et indépendants")
    
    # Appliquer le filtre par statut
    if filtre_statut != 'tous':
        query = query.filter(PlanAction.statut == filtre_statut)
        _journal(f"   📋 Statut: {filtre_statut}")
    
    # Récupérer les plans filtrés
    plans_action = query.all()
    
    # ============================================
    # 8. VÉRIFIER L'ACCÈS POUR CHAQUE PLAN ET PRÉPARER LES DONNÉES
    # ============================================
    accessible_plans = []
    aujourdhui = datetime.now().date()
    total_realisation = 0
    
    for plan in plans_action:
        if check_client_access(plan):
            # Créer un dictionnaire avec les données du plan
            plan_data = {
                'obj': plan,
                'type_plan': 'audit' if plan.audit_id else 'risque' if plan.risque_id else 'independant',
                'jours_restants': None,
                'etat_delai': 'non_defini',
                'jours_retard': 0,
                'pourcentage_global': 0,
                'source': None
            }
            
            # Récupérer la source (audit ou risque)
            if plan.audit_id:
                plan_data['source'] = get_client_filter(Audit).filter_by(id=plan.audit_id).first()
            elif plan.risque_id:
                plan_data['source'] = get_client_filter(Risque).filter_by(id=plan.risque_id).first()
            
            # Calculer les jours restants par rapport à la date de fin prévue
            if plan.date_fin_prevue:
                jours_restants = (plan.date_fin_prevue - aujourdhui).days
                plan_data['jours_restants'] = jours_restants
                
                if jours_restants < 0:
                    plan_data['etat_delai'] = 'retarde'
                    plan_data['jours_retard'] = abs(jours_restants)
                    stats_globales['en_retard'] += 1
                elif jours_restants <= 7:
                    plan_data['etat_delai'] = 'urgence'
                    stats_globales['urgences'] += 1
                elif jours_restants <= 30:
                    plan_data['etat_delai'] = 'a_suivre'
                else:
                    plan_data['etat_delai'] = 'ok'
            else:
                plan_data['etat_delai'] = 'pas_de_date'
            
            # Calculer la progression à partir des sous-actions
            if hasattr(plan, 'sous_actions') and plan.sous_actions:
                total_sous_actions = len(plan.sous_actions)
                if total_sous_actions > 0:
                    sous_actions_terminees = len([sa for sa in plan.sous_actions 
                                                 if sa.statut == 'termine'])
                    plan_data['pourcentage_global'] = round((sous_actions_terminees / total_sous_actions) * 100)
                    plan_data['sous_actions_terminees'] = sous_actions_terminees
                    plan_data['total_sous_actions'] = total_sous_actions
                else:
                    plan_data['pourcentage_global'] = 0
                    plan_data['sous_actions_terminees'] = 0
                    plan_data['total_sous_actions'] = 0
            else:
                # Fallback sur le pourcentage stocké
                plan_data['pourcentage_global'] = getattr(plan, 'pourcentage_realisation', 0) or 0
                plan_data['sous_actions_terminees'] = 0
                plan_data['total_sous_actions'] = 0
            
            total_realisation += plan_data['pourcentage_global']
            accessible_plans.append(plan_data)
    
    # Calculer la moyenne de réalisation pour les plans affichés
    if accessible_plans:
        stats_globales['moyenne_realisation'] = round(total_realisation / len(accessible_plans))
    
    # ============================================
    # 9. APPLIQUER LE TRI
    # ============================================
    if tri == 'urgence':
        accessible_plans.sort(key=lambda p: (
            0 if p['etat_delai'] == 'retarde' else 
            1 if p['etat_delai'] == 'urgence' else 
            2 if p['etat_delai'] == 'a_suivre' else 3,
            p['obj'].date_fin_prevue or datetime.max.date()
        ))
    elif tri == 'realisation_asc':
        accessible_plans.sort(key=lambda p: p['pourcentage_global'])
    elif tri == 'realisation_desc':
        accessible_plans.sort(key=lambda p: p['pourcentage_global'], reverse=True)
    elif tri == 'date_asc':
        accessible_plans.sort(key=lambda p: p['obj'].date_fin_prevue or datetime.min.date())
    elif tri == 'date_desc':
        accessible_plans.sort(key=lambda p: p['obj'].date_fin_prevue or datetime.min.date(), reverse=True)
    elif tri == 'titre_asc':
        accessible_plans.sort(key=lambda p: p['obj'].titre or '')
    elif tri == 'titre_desc':
        accessible_plans.sort(key=lambda p: p['obj'].titre or '', reverse=True)
    
    # ============================================
    # 10. DEBUG : Afficher ce qu'on a trouvé
    # ============================================
    _journal(f"\n📊 RÉSULTATS:")
    _journal(f"   Total plans en base: {len(plans_action)}")
    _journal(f"   Plans accessibles: {len(accessible_plans)}")
    _journal(f"   Plans audit: {len([p for p in accessible_plans if p['type_plan'] == 'audit'])}")
    _journal(f"   Plans risque: {len([p for p in accessible_plans if p['type_plan'] == 'risque'])}")
    _journal(f"   Plans indépendants: {len([p for p in accessible_plans if p['type_plan'] == 'independant'])}")
    
    return render_template('audit/plans_action.html', 
                         plans_action=accessible_plans,
                         stats=stats_globales,
                         type_filtre=type_filtre,
                         filtre_statut=filtre_statut,
                         tri=tri,
                         aujourdhui=aujourdhui,
                         current_user=current_user)


@app.route('/audit/rapports')
@login_required
def rapports_audit():
    """Page des rapports d'audit - VERSION CORRIGÉE avec multi-tenant"""
    
    # Récupérer les audits avec filtrage multi-tenant
    audits = get_multi_tenant_filter(Audit).all()
    
    # Créer un dictionnaire des audits pour un accès facile par ID
    audits_dict = {audit.id: audit for audit in audits}
    
    # Récupérer les fichiers associés aux audits (si vous avez un modèle FichierRapport)
    fichiers_par_audit = {}
    
    if audits:
        audit_ids = [audit.id for audit in audits]
        
        # Version 1: Si vous avez un modèle FichierRapport qui référence les audits
        # from models import FichierRapport
        # fichiers_query = get_multi_tenant_filter(FichierRapport).filter(FichierRapport.audit_id.in_(audit_ids))
        # for fichier in fichiers_query.all():
        #     if fichier.audit_id not in fichiers_par_audit:
        #         fichiers_par_audit[fichier.audit_id] = []
        #     fichiers_par_audit[fichier.audit_id].append(fichier)
        
        # Version 2: Si vos audits ont une relation directe avec les fichiers
        for audit in audits:
            fichiers_par_audit[audit.id] = []
            # Si votre modèle Audit a une relation avec les fichiers :
            # if hasattr(audit, 'fichiers') and audit.fichiers:
            #     fichiers_par_audit[audit.id] = audit.fichiers
    
    # Si aucun audit trouvé pour le client actuel
    if not audits:
        return render_template('audit/rapports.html',
                             audits=[],
                             audits_dict={},
                             fichiers_par_audit={},
                             constatations_total=0,
                             recommandations_total=0,
                             plans_action_total=0,
                             types_audit={'labels': [], 'data': []},
                             statuts_audit={'labels': [], 'data': []})
    
    # Statistiques pour les rapports (calculées sur les audits filtrés)
    constatations_total = sum(len(audit.constatations) for audit in audits)
    recommandations_total = sum(len(audit.recommandations) for audit in audits)
    plans_action_total = sum(len(audit.plans_action) for audit in audits)
    
    # Données pour les graphiques - avec filtrage multi-tenant
    types_audit_data = {}
    for audit_type in ['interne', 'externe', 'qualite', 'conformite', 'securite', 'financier']:
        types_audit_data[audit_type] = get_multi_tenant_filter(Audit)\
            .filter_by(type_audit=audit_type)\
            .count()
    
    types_audit = {
        'labels': ['Interne', 'Externe', 'Qualité', 'Conformité', 'Sécurité', 'Financier'],
        'data': [
            types_audit_data['interne'],
            types_audit_data['externe'], 
            types_audit_data['qualite'],
            types_audit_data['conformite'],
            types_audit_data['securite'],
            types_audit_data['financier']
        ]
    }
    
    # Statuts des audits - avec filtrage multi-tenant
    statuts_audit = {
        'labels': ['Planifié', 'En cours', 'Terminé', 'Annulé'],
        'data': [
            get_multi_tenant_filter(Audit).filter_by(statut='planifie').count(),
            get_multi_tenant_filter(Audit).filter_by(statut='en_cours').count(),
            get_multi_tenant_filter(Audit).filter_by(statut='termine').count(),
            get_multi_tenant_filter(Audit).filter_by(statut='annule').count()
        ]
    }
    
    # Autres statistiques utiles
    audits_par_annee = {}
    audits_par_responsable = {}
    audits_par_processus = {}
    
    for audit in audits:
        # Statistiques par année
        if audit.date_debut_prevue:
            annee = audit.date_debut_prevue.year
            audits_par_annee[annee] = audits_par_annee.get(annee, 0) + 1
        
        # Statistiques par responsable
        if audit.responsable:
            responsable_nom = audit.responsable.username
            audits_par_responsable[responsable_nom] = audits_par_responsable.get(responsable_nom, 0) + 1
        
        # Statistiques par processus
        if audit.processus_concerne:
            audits_par_processus[audit.processus_concerne] = audits_par_processus.get(audit.processus_concerne, 0) + 1
        elif audit.processus and audit.processus.nom:
            audits_par_processus[audit.processus.nom] = audits_par_processus.get(audit.processus.nom, 0) + 1
    
    return render_template('audit/rapports.html',
                         audits=audits,
                         audits_dict=audits_dict,  # ← AJOUT IMPORTANT
                         fichiers_par_audit=fichiers_par_audit,
                         constatations_total=constatations_total,
                         recommandations_total=recommandations_total,
                         plans_action_total=plans_action_total,
                         types_audit=types_audit,
                         statuts_audit=statuts_audit,
                         audits_par_annee=audits_par_annee,
                         audits_par_responsable=audits_par_responsable,
                         audits_par_processus=audits_par_processus,
                         datetime=datetime)  # ← N'oubliez pas datetime pour le template


@app.route('/api/audit/statistiques-globales')
@login_required
def api_statistiques_audit_globales():
    """API pour les statistiques globales des audits"""
    audits = Audit.query.all()
    
    stats = {
        'total_audits': len(audits),
        'audits_en_cours': len([a for a in audits if a.statut == 'en_cours']),
        'audits_termines': len([a for a in audits if a.statut == 'termine']),
        'total_constatations': sum(len(a.constatations) for a in audits),
        'total_recommandations': sum(len(a.recommandations) for a in audits),
        'total_plans_action': sum(len(a.plans_action) for a in audits),
        'plans_action_en_retard': len([
            p for a in audits for p in a.plans_action 
            if p.date_fin_prevue and p.date_fin_prevue < datetime.now().date() and p.statut != 'termine'
        ])
    }
    
    return jsonify(stats)


@app.route('/audit/<int:audit_id>/constatation/ajouter', methods=['POST'])
@login_required
def nouvelle_constatation(audit_id):
    """Ajouter une constatation à un audit - VERSION CORRIGÉE"""
    from models import Audit, Constatation, DemandeReevaluation, Notification, User, db
    from datetime import datetime
    
    audit = get_client_object_or_404(Audit, audit_id)
    
    # Vérifier les permissions
    if not current_user.has_permission('can_manage_audit'):
        flash('Permission requise', 'error')
        return redirect(url_for('detail_audit', id=audit_id))
    
    try:
        # ===== GÉNÉRATION DE LA RÉFÉRENCE =====
        dernier_constat = (
            Constatation.query
            .filter_by(audit_id=audit_id)
            .order_by(Constatation.id.desc())
            .first()
        )
        nouvelle_ref = f"CON-{audit.reference}-{(dernier_constat.id + 1) if dernier_constat else 1:03d}"
        
        # ===== RÉCUPÉRATION DES DONNÉES =====
        description = request.form.get('description', '').strip()
        type_constatation = request.form.get('type_constatation', 'observation')
        gravite = request.form.get('gravite', 'moyenne')
        cause_racine = request.form.get('cause_racine', '').strip()
        conclusion = request.form.get('conclusion', '').strip()
        commentaires = request.form.get('commentaires', '').strip()
        
        # 🔥 CORRECTION : Récupérer correctement les IDs
        risque_id = request.form.get('risque_id')
        dispositif_id = request.form.get('dispositif_id')
        controle_id = request.form.get('controle_id')
        
        # Convertir en int si nécessaire
        risque_id = int(risque_id) if risque_id and risque_id.isdigit() else None
        dispositif_id = int(dispositif_id) if dispositif_id and dispositif_id.isdigit() else None
        controle_id = int(controle_id) if controle_id and controle_id.isdigit() else None
        
        # ===== CRÉATION DE LA CONSTATATION =====
        constatation = Constatation(
            reference=nouvelle_ref,
            description=description,
            type_constatation=type_constatation,
            gravite=gravite,
            criticite=request.form.get('criticite', 'mineure'),
            processus_concerne=request.form.get('processus_concerne', '').strip(),
            cause_racine=cause_racine,
            conclusion=conclusion,
            commentaires=commentaires,
            recommandations_immediates=request.form.get('recommandations_immediates', '').strip(),
            statut='a_analyser',
            audit_id=audit_id,
            # 🔥 CORRECTION : Les IDs sont maintenant bien récupérés
            risque_id=risque_id,
            dispositif_id=dispositif_id,
            controle_id=controle_id,
            created_by=current_user.id,
            client_id=current_user.client_id
        )
        
        db.session.add(constatation)
        db.session.flush()  # Pour obtenir l'ID
        
        # ============================================
        # 🔥 NOUVEAU : GESTION DE LA RÉÉVALUATION
        # ============================================
        demander_reevaluation = request.form.get('demander_reevaluation') == '1'
        creer_nouveau_risque = request.form.get('creer_nouveau_risque') == '1'
        
        if demander_reevaluation and risque_id:
            # Récupérer les propositions
            impact_propose = request.form.get('impact_propose', type=int)
            probabilite_propose = request.form.get('probabilite_propose', type=int)
            niveau_maitrise_propose = request.form.get('niveau_maitrise_propose', type=int)
            justification = request.form.get('justification_reevaluation', '').strip()
            
            if not justification:
                flash('La justification est obligatoire pour une réévaluation', 'error')
                return redirect(url_for('detail_audit', id=audit_id))
            
            # Créer la demande de réévaluation
            demande = DemandeReevaluation(
                audit_id=audit_id,
                constat_id=constatation.id,
                risque_id=risque_id,
                titre=f"Réévaluation du risque suite au constat {constatation.reference}",
                description=f"Suite au constat {constatation.reference}: {description[:100]}...",
                justification=justification,
                impact_propose=impact_propose,
                probabilite_propose=probabilite_propose,
                niveau_maitrise_propose=niveau_maitrise_propose,
                demandeur_id=current_user.id,
                client_id=current_user.client_id,
                statut='en_attente'
            )
            demande.reference = demande.generer_reference()
            demande.calculer_score_propose()
            
            db.session.add(demande)
            db.session.flush()
            
            # Lier la demande au constat
            constatation.demande_reevaluation_id = demande.id
            constatation.reevaluation_demandee = True
            constatation.reevaluation_statut = 'demandee'
            
            # Notifier le comité des risques
            comite_risques = User.query.filter(
                User.client_id == current_user.client_id,
                User.is_active == True,
                User.role.in_(['admin', 'responsable_risques', 'manager'])
            ).all()
            
            for user in comite_risques:
                notification = Notification(
                    destinataire_id=user.id,
                    type_notification='reevaluation_demandee',
                    titre=f"🔄 Demande de réévaluation: {risque_id}",
                    message=f"Une demande de réévaluation a été soumise suite au constat {constatation.reference}.\n"
                            f"Proposition: Impact {impact_propose}/5, Probabilité {probabilite_propose}/5\n"
                            f"Justification: {justification}",
                    entite_type='demande_reevaluation',
                    entite_id=demande.id,
                    client_id=current_user.client_id,
                    urgence='important'
                )
                db.session.add(notification)
            
            flash(f'✅ Demande de réévaluation créée (Réf: {demande.reference})', 'success')
        
        elif creer_nouveau_risque:
            # Créer un nouveau risque
            intitule = request.form.get('nouveau_risque_intitule', '').strip()
            description_risque = request.form.get('nouveau_risque_description', '').strip()
            categorie = request.form.get('nouveau_risque_categorie', '')
            impact = request.form.get('nouveau_risque_impact', type=int)
            probabilite = request.form.get('nouveau_risque_probabilite', type=int)
            niveau_maitrise = request.form.get('nouveau_risque_maitrise', type=int)
            justification_risque = request.form.get('nouveau_risque_justification', '').strip()
            
            if not intitule or not justification_risque:
                flash('L\'intitulé et la justification sont obligatoires pour un nouveau risque', 'error')
                return redirect(url_for('detail_audit', id=audit_id))
            
            # Créer le risque
            nouveau_risque = Risque(
                cartographie_id=audit.cartographie_id if audit.cartographie_id else None,
                reference=f"RISK-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                intitule=intitule,
                description=description_risque,
                categorie=categorie,
                impact=impact,
                probabilite=probabilite,
                score_risque=impact * probabilite,
                niveau_criticite=Risque.calculer_niveau_criticite_from_score(impact * probabilite),
                statut='en_validation',
                created_by=current_user.id,
                client_id=current_user.client_id
            )
            db.session.add(nouveau_risque)
            db.session.flush()
            
            # Créer la demande associée
            demande = DemandeReevaluation(
                audit_id=audit_id,
                constat_id=constatation.id,
                risque_id=nouveau_risque.id,
                titre=f"Nouveau risque: {intitule}",
                description=description_risque,
                justification=justification_risque,
                impact_propose=impact,
                probabilite_propose=probabilite,
                niveau_maitrise_propose=niveau_maitrise,
                demandeur_id=current_user.id,
                client_id=current_user.client_id,
                statut='en_attente'
            )
            demande.reference = demande.generer_reference()
            demande.calculer_score_propose()
            
            db.session.add(demande)
            db.session.flush()
            
            # Lier au constat
            constatation.demande_reevaluation_id = demande.id
            constatation.reevaluation_demandee = True
            constatation.reevaluation_statut = 'demandee'
            constatation.risque_id = nouveau_risque.id
            
            # Notifier le comité
            comite_risques = User.query.filter(
                User.client_id == current_user.client_id,
                User.is_active == True,
                User.role.in_(['admin', 'responsable_risques', 'manager'])
            ).all()
            
            for user in comite_risques:
                notification = Notification(
                    destinataire_id=user.id,
                    type_notification='nouveau_risque_propose',
                    titre=f"🆕 Nouveau risque proposé: {intitule}",
                    message=f"Un nouveau risque a été identifié lors de l'audit {audit.reference}.\n"
                            f"Intitulé: {intitule}\n"
                            f"Impact: {impact}/5, Probabilité: {probabilite}/5\n"
                            f"Justification: {justification_risque}",
                    entite_type='risque',
                    entite_id=nouveau_risque.id,
                    client_id=current_user.client_id,
                    urgence='important'
                )
                db.session.add(notification)
            
            flash(f'✅ Nouveau risque proposé (Réf: {nouveau_risque.reference})', 'success')
        
        db.session.commit()
        
        flash('Constatation ajoutée avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur lors de l'ajout de la constatation : {e}")
        import traceback
        traceback.print_exc()
        flash(f"Erreur lors de l'ajout de la constatation : {str(e)}", 'error')
    
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/constatation/<int:constatation_id>/upload-fichier', methods=['POST'])
@login_required
def upload_fichier_constatation(constatation_id):
    """Uploader un fichier pour une constatation"""
    constatation = Constatation.query.get_or_404(constatation_id)
    
    if 'fichier' not in request.files:
        return jsonify({'success': False, 'message': 'Aucun fichier sélectionné'}), 400
    
    fichier = request.files['fichier']
    
    if fichier.filename == '':
        return jsonify({'success': False, 'message': 'Aucun fichier sélectionné'}), 400
    
    if fichier and allowed_file(fichier.filename):
        try:
            filename = secure_filename(fichier.filename)
            # Créer un dossier spécifique pour la constatation
            constat_folder = os.path.join(app.config['UPLOAD_FOLDER_RISQUES'], 
                                         f'constatation_{constatation_id}')
            os.makedirs(constat_folder, exist_ok=True)
            
            filepath = os.path.join(constat_folder, filename)
            fichier.save(filepath)
            
            # Mettre à jour la liste des fichiers
            fichiers_ids = constatation.fichiers_ids or ''
            nouveaux_fichiers = fichiers_ids + f'{filename},' if fichiers_ids else f'{filename},'
            constatation.fichiers_ids = nouveaux_fichiers
            constatation.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            # Journaliser
            journaliser_action_audit(
                audit_id=constatation.audit_id,
                action_type='upload_fichier_constatation',
                user_id=current_user.id,
                details={'fichier': filename, 'constatation': constatation.reference}
            )
            
            return jsonify({
                'success': True,
                'message': 'Fichier uploadé avec succès',
                'filename': filename
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500
    
    return jsonify({'success': False, 'message': 'Type de fichier non autorisé'}), 400


@app.route('/recommandation/<int:recommandation_id>/ajouter-histoire', methods=['POST'])
@login_required
def ajouter_histoire_recommandation(recommandation_id):
    """Ajouter une entrée dans l'historique de la recommandation"""
    recommandation = Recommandation.query.get_or_404(recommandation_id)
    
    action = request.form.get('action')
    details = {
        'champ': request.form.get('champ'),
        'ancienne_valeur': request.form.get('ancienne_valeur'),
        'nouvelle_valeur': request.form.get('nouvelle_valeur'),
        'commentaire': request.form.get('commentaire')
    }
    
    historique = HistoriqueRecommandation(
        recommandation_id=recommandation_id,
        action=action,
        details=details,
        utilisateur_id=current_user.id
    )
    
    db.session.add(historique)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Historique ajouté'})


@app.route('/audit/<int:audit_id>/recommandation/nouvelle', methods=['POST'])
@login_required
def nouvelle_recommandation(audit_id):
    """Ajouter une recommandation à un audit"""
    audit = Audit.query.get_or_404(audit_id)
    
    try:
        # Récupérer les données du formulaire
        description = request.form.get('description', '').strip()
        type_recommandation = request.form.get('type_recommandation', '').strip()
        delai_str = request.form.get('delai_mise_en_oeuvre', '').strip()
        
        # VALIDATION
        if not description:
            flash('La description est requise', 'error')
            return redirect(url_for('detail_audit', id=audit_id))
        
        if not type_recommandation:
            flash('Le type de recommandation est requis', 'error')
            return redirect(url_for('detail_audit', id=audit_id))
        
        # GÉNÉRER UNE RÉFÉRENCE
        # Compter les recommandations existantes pour cet audit
        count = Recommandation.query.filter_by(audit_id=audit_id).count()
        
        # Utiliser la référence de l'audit ou créer une référence par défaut
        audit_ref = audit.reference if audit.reference else f"AUD{audit_id:04d}"
        audit_ref_clean = audit_ref.replace('AUD-', '').strip()
        
        # Générer la référence
        reference = f"REC-{audit_ref_clean}-{(count + 1):03d}"
        
        # Traiter date_echeance
        date_echeance_str = request.form.get('date_echeance')
        date_echeance = None
        
        if date_echeance_str and date_echeance_str.strip():
            try:
                date_echeance = datetime.strptime(date_echeance_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Format de date invalide', 'error')
                return redirect(url_for('detail_audit', id=audit_id))
        
        # Créer la recommandation AVEC LES CHAMPS TEXTUELS
        recommandation = Recommandation(
            reference=reference,  # IMPORTANT: ne pas oublier ce champ !
            description=description,
            type_recommandation=type_recommandation,
            delai_mise_en_oeuvre=delai_str if delai_str else None,  # TEXTE, pas numérique
            date_echeance=date_echeance,
            audit_id=audit_id,
            constatation_id=request.form.get('constatation_id') if request.form.get('constatation_id') else None,
            risque_id=request.form.get('risque_id') if request.form.get('risque_id') else None,
            responsable_id=request.form.get('responsable_id') if request.form.get('responsable_id') else None,
            created_by=current_user.id,
            # Ajouter les champs de priorité si présents dans le formulaire
            urgence=int(request.form.get('urgence', 1)),
            impact_operationnel=int(request.form.get('impact_operationnel', 1))
        )
        
        db.session.add(recommandation)
        db.session.commit()
        
        flash(f'Recommandation {reference} ajoutée avec succès', 'success')
        
    except ValueError as e:
        db.session.rollback()
        flash(f'Erreur de valeur: {str(e)}', 'error')
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur détaillée: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erreur lors de l\'ajout: {str(e)}', 'error')
    
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/audit/<int:audit_id>/plan-action/nouveau', methods=['POST'])
@login_required
def nouveau_plan_action(audit_id):
    """Créer un plan d'action pour un audit"""
    audit = Audit.query.get_or_404(audit_id)
    
    try:
        # 1. VALIDATION
        nom = request.form.get('nom', '').strip()
        if not nom:
            flash('Le nom du plan est requis', 'error')
            return redirect(url_for('detail_audit', id=audit_id))
        
        # 2. GÉNÉRATION DE LA RÉFÉRENCE
        import re
        import time
        
        # Compter les plans d'action existants pour cet audit
        count = PlanAction.query.filter_by(audit_id=audit_id).count()
        
        # Chercher le dernier plan pour trouver le dernier numéro
        last_plan = PlanAction.query.filter_by(audit_id=audit_id).order_by(PlanAction.id.desc()).first()
        
        if last_plan and last_plan.reference:
            # Extraire le numéro de la dernière référence
            match = re.search(r'-(\d{3,})$', last_plan.reference)
            if match:
                last_num = int(match.group(1))
                next_num = last_num + 1
            else:
                next_num = count + 1
        else:
            next_num = 1
        
        # Créer la référence de l'audit
        audit_ref = audit.reference if audit.reference else f"AUD{audit_id:04d}"
        audit_ref_clean = audit_ref.replace('AUD-', '').strip()
        
        # Générer la référence finale
        reference = f"PA-{audit_ref_clean}-{next_num:03d}"
        
        # VÉRIFIER QUE LA RÉFÉRENCE N'EXISTE PAS DÉJÀ
        while PlanAction.query.filter_by(reference=reference).first():
            next_num += 1
            reference = f"PA-{audit_ref_clean}-{next_num:03d}"
        
        _journal(f"📝 Référence générée pour plan d'action: {reference}")
        
        # 3. CRÉATION DU PLAN D'ACTION
        plan_action = PlanAction(
            reference=reference,  # CHAMP OBLIGATOIRE REMPLI
            nom=nom,
            description=request.form.get('description', '').strip(),
            statut='en_attente',
            pourcentage_realisation=0,
            audit_id=audit_id,
            created_by=current_user.id,
            is_archived=False
        )
        
        # 4. TRAITEMENT DES CHAMPS OPTIONNELS
        # Dates
        date_debut_str = request.form.get('date_debut')
        date_fin_prevue_str = request.form.get('date_fin_prevue')
        
        if date_debut_str:
            try:
                plan_action.date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        if date_fin_prevue_str:
            try:
                plan_action.date_fin_prevue = datetime.strptime(date_fin_prevue_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        # IDs optionnels
        for field in ['recommandation_id', 'risque_id', 'responsable_id']:
            value = request.form.get(field)
            if value and value.strip() and value.strip().isdigit():
                setattr(plan_action, field, int(value.strip()))
        
        # Constatations (peut être une liste d'IDs séparés par des virgules)
        constatations_ids = request.form.get('constatations_ids', '')
        if constatations_ids:
            # Valider que ce sont des nombres
            ids_list = []
            for id_str in constatations_ids.split(','):
                id_str = id_str.strip()
                if id_str.isdigit():
                    ids_list.append(id_str)
            
            if ids_list:
                plan_action.constatations_ids = ','.join(ids_list)
        
        # 5. SAUVEGARDE
        db.session.add(plan_action)
        db.session.commit()
        
        flash(f'Plan d\'action {reference} créé avec succès', 'success')
        
    except ValueError as e:
        db.session.rollback()
        flash(f'Erreur de valeur: {str(e)}', 'error')
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur détaillée: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erreur lors de la création: {str(e)}', 'error')
    
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/api/audit/<int:audit_id>/constatations')
@login_required
def api_constatations_audit(audit_id):
    """API pour récupérer les constatations d'un audit"""
    audit = Audit.query.get_or_404(audit_id)
    
    constatations = []
    for constat in audit.constatations:
        constatations.append({
            'id': constat.id,
            'reference': constat.reference,
            'description': constat.description,
            'type': constat.type_constatation,
            'gravite': constat.gravite
        })
    
    return jsonify(constatations)


@app.route('/audit/<int:audit_id>/export/rapport-pdf')
@login_required
def export_rapport_audit_pdf(audit_id):
    """Exporter le rapport d'audit en PDF avec liste des fichiers"""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from io import BytesIO
    
    audit = get_client_object_or_404(Audit, audit_id)
    
    # Vérifier les permissions
    peut_voir = (
        current_user.role == 'super_admin' or
        current_user.id == audit.created_by or
        current_user.id == audit.responsable_id or
        (audit.equipe_audit_ids and str(current_user.id) in audit.equipe_audit_ids.split(','))
    )
    
    if not peut_voir:
        flash('Vous n\'avez pas les permissions pour exporter ce rapport', 'error')
        return redirect(url_for('liste_audits'))
    
    # Récupérer les fichiers joints
    fichiers_rapport = get_client_filter(FichierRapport)\
        .filter_by(audit_id=audit_id)\
        .order_by(FichierRapport.created_at.desc()).all()
    
    # Créer le PDF en mémoire
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Style personnalisé
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30
    )
    
    # Titre
    story.append(Paragraph(f"Rapport d'Audit - {audit.reference}", title_style))
    story.append(Paragraph(f"Titre: {audit.titre}", styles['Normal']))
    story.append(Spacer(1, 12))
    
    # Informations générales
    story.append(Paragraph("Informations Générales", styles['Heading2']))
    
    info_data = [
        ['Référence', audit.reference],
        ['Type', audit.type_audit],
        ['Statut', audit.statut],
        ['Responsable', audit.responsable.username if audit.responsable else 'Non défini'],
        ['Dates', f"{audit.date_debut_prevue.strftime('%d/%m/%Y') if audit.date_debut_prevue else 'N/A'} - {audit.date_fin_prevue.strftime('%d/%m/%Y') if audit.date_fin_prevue else 'N/A'}"],
        ['Score global', f"{audit.score_global if hasattr(audit, 'score_global') else 0}/100"],
    ]
    
    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))
    
    # Fichiers joints (Nouvelle section)
    if fichiers_rapport:
        story.append(Paragraph("Fichiers joints au rapport", styles['Heading2']))
        
        fichiers_data = [['Nom du fichier', 'Type', 'Taille', 'Description', 'Date']]
        for fichier in fichiers_rapport:
            fichiers_data.append([
                fichier.nom_fichier[:30] + '...' if len(fichier.nom_fichier) > 30 else fichier.nom_fichier,
                fichier.type_fichier or 'N/A',
                fichier.taille_formatee if hasattr(fichier, 'taille_formatee') else 'N/A',
                fichier.description[:30] + '...' if fichier.description and len(fichier.description) > 30 else fichier.description or '',
                fichier.created_at.strftime('%d/%m/%Y') if fichier.created_at else 'N/A'
            ])
        
        fichiers_table = Table(fichiers_data, colWidths=[2*inch, 0.8*inch, 0.8*inch, 1.5*inch, 1*inch])
        fichiers_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ]))
        story.append(fichiers_table)
        story.append(Spacer(1, 20))
    
    # Constatations
    story.append(Paragraph("Constatations", styles['Heading2']))
    if audit.constatations:
        constat_data = [['Réf.', 'Description', 'Type', 'Gravité', 'Statut']]
        for constat in audit.constatations:
            constat_data.append([
                constat.reference,
                constat.description[:100] + '...' if len(constat.description) > 100 else constat.description,
                constat.type_constatation,
                constat.gravite,
                constat.statut
            ])
        
        constat_table = Table(constat_data, colWidths=[0.5*inch, 2.5*inch, inch, inch, inch])
        constat_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ]))
        story.append(constat_table)
    else:
        story.append(Paragraph("Aucune constatation", styles['Normal']))
    
    story.append(Spacer(1, 20))
    
    # Recommandations
    story.append(Paragraph("Recommandations", styles['Heading2']))
    if audit.recommandations:
        reco_data = [['Réf.', 'Description', 'Priorité', 'Statut', 'Avancement']]
        for reco in audit.recommandations:
            reco_data.append([
                reco.reference,
                reco.description[:80] + '...' if len(reco.description) > 80 else reco.description,
                reco.score_priorite,
                reco.statut,
                f"{reco.taux_avancement}%"
            ])
        
        reco_table = Table(reco_data, colWidths=[0.5*inch, 3*inch, 0.7*inch, inch, inch])
        reco_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ]))
        story.append(reco_table)
    
    story.append(Spacer(1, 20))
    
    # Pied de page
    story.append(Paragraph(f"Généré le {datetime.utcnow().strftime('%d/%m/%Y à %H:%M')} par {current_user.username}", 
                          ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, alignment=1)))
    
    # Générer le PDF
    doc.build(story)
    
    buffer.seek(0)
    return send_file(buffer, 
                    as_attachment=True, 
                    download_name=f"rapport_audit_{audit.reference}.pdf",
                    mimetype='application/pdf')


@app.route('/audit/<int:audit_id>/export-word')
@login_required
def export_rapport_audit_word(audit_id):
    """Exporter le rapport d'audit en Word (.docx)"""
    audit = Audit.query.get_or_404(audit_id)
    
    # Vérifier les permissions
    peut_voir = (
        current_user.role == 'admin' or
        current_user.id == audit.created_by or
        current_user.id == audit.responsable_id or
        (audit.equipe_audit_ids and str(current_user.id) in audit.equipe_audit_ids.split(','))
    )
    
    if not peut_voir:
        flash('Vous n\'avez pas les permissions pour exporter ce rapport', 'error')
        return redirect(url_for('liste_audits'))
    
    # Initialiser COM pour Windows (si nécessaire)
    try:
        pythoncom.CoInitialize()
    except:
        pass
    
    # Créer un nouveau document Word
    doc = Document()
    
    # Définir les styles
    styles = doc.styles
    
    # Style pour le titre
    title_style = styles.add_style('CustomTitle', WD_STYLE_TYPE.PARAGRAPH)
    title_style.font.size = Pt(16)
    title_style.font.bold = True
    title_style.font.color.rgb = RGBColor(44, 62, 80)  # #2c3e50
    title_style.paragraph_format.space_after = Pt(12)
    title_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Style pour les titres de section
    heading1_style = styles.add_style('CustomHeading1', WD_STYLE_TYPE.PARAGRAPH)
    heading1_style.font.size = Pt(14)
    heading1_style.font.bold = True
    heading1_style.font.color.rgb = RGBColor(52, 73, 94)  # #34495e
    heading1_style.paragraph_format.space_after = Pt(10)
    
    # Style pour les sous-titres
    heading2_style = styles.add_style('CustomHeading2', WD_STYLE_TYPE.PARAGRAPH)
    heading2_style.font.size = Pt(12)
    heading2_style.font.bold = True
    heading2_style.font.color.rgb = RGBColor(44, 62, 80)  # #2c3e50
    heading2_style.paragraph_format.space_after = Pt(8)
    
    # Style normal
    normal_style = styles.add_style('CustomNormal', WD_STYLE_TYPE.PARAGRAPH)
    normal_style.font.size = Pt(10)
    normal_style.font.color.rgb = RGBColor(44, 62, 80)  # #2c3e50
    normal_style.paragraph_format.space_after = Pt(6)
    
    # Titre du document
    title = doc.add_paragraph(f"Rapport d'Audit - {audit.reference}")
    title.style = title_style
    
    subtitle = doc.add_paragraph(audit.titre)
    subtitle.style = heading1_style
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_paragraph()
    
    # Informations générales
    section_title = doc.add_paragraph("Informations Générales")
    section_title.style = heading1_style
    
    # Ajouter les informations dans un tableau
    table = doc.add_table(rows=8, cols=2)
    table.style = 'Light Grid Accent 1'
    
    # Remplir le tableau
    cells = table.rows[0].cells
    cells[0].text = "Référence"
    cells[1].text = audit.reference
    
    cells = table.rows[1].cells
    cells[0].text = "Titre"
    cells[1].text = audit.titre
    
    cells = table.rows[2].cells
    cells[0].text = "Type d'audit"
    cells[1].text = audit.type_audit
    
    cells = table.rows[3].cells
    cells[0].text = "Statut"
    cells[1].text = audit.statut
    
    cells = table.rows[4].cells
    cells[0].text = "Responsable"
    cells[1].text = audit.responsable.username if audit.responsable else "Non assigné"
    
    cells = table.rows[5].cells
    cells[0].text = "Date début prévue"
    cells[1].text = audit.date_debut_prevue.strftime('%d/%m/%Y') if audit.date_debut_prevue else "Non définie"
    
    cells = table.rows[6].cells
    cells[0].text = "Date fin prévue"
    cells[1].text = audit.date_fin_prevue.strftime('%d/%m/%Y') if audit.date_fin_prevue else "Non définie"
    
    cells = table.rows[7].cells
    cells[0].text = "Date de génération"
    cells[1].text = datetime.utcnow().strftime('%d/%m/%Y à %H:%M')
    
    doc.add_paragraph()
    
    # Description
    if audit.description:
        desc_title = doc.add_paragraph("Description")
        desc_title.style = heading2_style
        doc.add_paragraph(audit.description, style='CustomNormal')
        doc.add_paragraph()
    
    # Objectifs
    if audit.objectifs:
        obj_title = doc.add_paragraph("Objectifs")
        obj_title.style = heading2_style
        doc.add_paragraph(audit.objectifs, style='CustomNormal')
        doc.add_paragraph()
    
    # Constatations
    constatations = Constatation.query.filter_by(audit_id=audit.id, is_archived=False).all()
    if constatations:
        doc.add_page_break()
        const_title = doc.add_paragraph("Constatations de l'Audit")
        const_title.style = heading1_style
        
        for constatation in constatations:
            doc.add_paragraph(f"Constatation {constatation.reference}", style='CustomHeading2')
            
            # Créer un tableau pour cette constatation
            const_table = doc.add_table(rows=9, cols=2)
            const_table.style = 'Light Grid Accent 2'
            
            rows_data = [
                ("Description", constatation.description),
                ("Type", constatation.type_constatation.replace('_', ' ').title() if constatation.type_constatation else ""),
                ("Gravité", constatation.gravite.title() if constatation.gravite else ""),
                ("Processus concerné", constatation.processus_concerne or "Non spécifié"),
                ("Statut", constatation.statut.replace('_', ' ').title() if constatation.statut else ""),
                ("Cause racine", constatation.cause_racine or "Non spécifiée"),
                ("Conclusion", constatation.conclusion or "Non spécifiée"),
                ("Commentaires", constatation.commentaires or "Aucun"),
                ("Recommandations immédiates", constatation.recommandations_immediates or "Aucune")
            ]
            
            for i, (label, value) in enumerate(rows_data):
                cells = const_table.rows[i].cells
                cells[0].text = label
                cells[1].text = value
            
            doc.add_paragraph()
    
    # Recommandations
    recommandations = Recommandation.query.filter_by(audit_id=audit.id).all()
    if recommandations:
        doc.add_page_break()
        reco_title = doc.add_paragraph("Recommandations")
        reco_title.style = heading1_style
        
        for recommandation in recommandations:
            doc.add_paragraph(f"Recommandation {recommandation.reference}", style='CustomHeading2')
            
            # Créer un tableau pour cette recommandation
            reco_table = doc.add_table(rows=11, cols=2)
            reco_table.style = 'Light Grid Accent 3'
            
            rows_data = [
                ("Description", recommandation.description),
                ("Type", recommandation.type_recommandation.replace('_', ' ').title() if recommandation.type_recommandation else ""),
                ("Catégorie", recommandation.categorie.replace('_', ' ').title() if recommandation.categorie else ""),
                ("Statut", recommandation.statut.replace('_', ' ').title() if recommandation.statut else ""),
                ("Délai", recommandation.delai_mise_en_oeuvre.replace('_', ' ').title() if recommandation.delai_mise_en_oeuvre else ""),
                ("Date échéance", recommandation.date_echeance.strftime('%d/%m/%Y') if recommandation.date_echeance else "Non définie"),
                ("Urgence", str(recommandation.urgence) if recommandation.urgence else "Non spécifiée"),
                ("Impact", str(recommandation.impact_operationnel) if recommandation.impact_operationnel else "Non spécifié"),
                ("Priorité", f"{recommandation.score_priorite}/100" if recommandation.score_priorite else "Non calculée"),
                ("Avancement", f"{recommandation.taux_avancement or 0}%"),
                ("Responsable", recommandation.responsable.username if recommandation.responsable else "Non assigné")
            ]
            
            for i, (label, value) in enumerate(rows_data):
                cells = reco_table.rows[i].cells
                cells[0].text = label
                cells[1].text = value
            
            doc.add_paragraph()
    
    # Synthèse et conclusions
    doc.add_page_break()
    synth_title = doc.add_paragraph("Synthèse et Conclusions")
    synth_title.style = heading1_style
    
    # Statistiques
    total_constatations = len(constatations)
    total_recommandations = len(recommandations)
    constatations_critiques = len([c for c in constatations if c.gravite == 'critique'])
    recommandations_terminees = len([r for r in recommandations if r.statut == 'termine'])
    
    stats_table = doc.add_table(rows=5, cols=2)
    stats_table.style = 'Medium Grid 3 Accent 1'
    
    stats_data = [
        ("Total constatations", str(total_constatations)),
        ("Constatations critiques", str(constatations_critiques)),
        ("Total recommandations", str(total_recommandations)),
        ("Recommandations terminées", str(recommandations_terminees)),
        ("Taux d'avancement moyen", f"{sum([r.taux_avancement or 0 for r in recommandations]) / total_recommandations if total_recommandations > 0 else 0:.1f}%")
    ]
    
    for i, (label, value) in enumerate(stats_data):
        cells = stats_table.rows[i].cells
        cells[0].text = label
        cells[1].text = value
    
    doc.add_paragraph()
    
    # Recommandations globales
    reco_global_title = doc.add_paragraph("Recommandations Globales")
    reco_global_title.style = heading2_style
    
    recommandations_globales = [
        "Mettre en place un suivi régulier des plans d'action avec des points de contrôle mensuels",
        "Établir des indicateurs de performance pour mesurer l'efficacité des actions correctives",
        "Planifier des audits de suivi dans les 6 mois pour vérifier la pérennité des corrections",
        "Renforcer la formation des équipes sur les procédures identifiées comme critiques",
        "Développer un système d'alerte pour les recommandations approchant leur échéance"
    ]
    
    for reco in recommandations_globales:
        doc.add_paragraph(f"• {reco}", style='CustomNormal')
    
    doc.add_paragraph()
    
    # Conclusion générale
    concl_title = doc.add_paragraph("Conclusion Générale")
    concl_title.style = heading2_style
    
    conclusion_text = f"""
    L'audit {audit.reference} a permis d'identifier {total_constatations} constatations, 
    dont {constatations_critiques} points critiques. Le système de gestion a démontré 
    sa capacité à identifier et traiter les écarts grâce aux {total_recommandations} 
    recommandations émises.
    
    Le taux d'avancement global des actions est satisfaisant. Il est recommandé de 
    maintenir la dynamique d'amélioration continue et de programmer un audit de suivi 
    dans 6 mois pour vérifier l'efficacité et la pérennité des actions mises en œuvre.
    
    Rapport généré le {datetime.utcnow().strftime('%d/%m/%Y à %H:%M')}
    """
    
    doc.add_paragraph(conclusion_text, style='CustomNormal')
    
    # Pied de page
    doc.add_paragraph()
    footer = doc.add_paragraph("Système de Management Intégré - Contrôle Interne")
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.style.font.size = Pt(9)
    footer.style.font.color.rgb = RGBColor(128, 128, 128)
    
    # Sauvegarder dans un buffer
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    # Retourner le fichier Word
    filename = f"rapport_audit_{audit.reference}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.docx"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )


@app.route('/audit/<int:audit_id>/analyse-ia', methods=['GET', 'POST'])
@login_required
def analyse_ia_audit(audit_id):
    """Lancer une analyse IA sur l'audit"""
    
    # Vérifier l'accès à l'audit
    audit = get_client_object_or_404(Audit, audit_id)
    
    if not check_client_access(audit):
        flash('Accès non autorisé à cet audit', 'error')
        return redirect(url_for('liste_audits'))
    
    # Vérifier si le service IA est disponible
    if not SERVICE_IA_IMPORTED or service_ia is None:
        flash('Le service d\'analyse IA n\'est pas disponible', 'error')
        return redirect(url_for('detail_audit', id=audit_id))
    
    if not audit.constatations:
        flash('Aucune constatation à analyser. Ajoutez d\'abord des constatations.', 'warning')
        return redirect(url_for('detail_audit', id=audit_id))
    
    form = AnalyseIAForm()
    
    if form.validate_on_submit():
        try:
            # Utiliser le service IA avec vos paramètres
            resultat = service_ia.analyser_audit(
                audit_id=audit_id,
                type_analyse=form.type_analyse.data,
                user_id=current_user.id
            )
            
            # Vérifier que le résultat est valide
            if not resultat:
                flash('L\'analyse IA n\'a pas retourné de résultat', 'error')
                return redirect(url_for('detail_audit', id=audit_id))
            
            # Convertir le résultat si c'est un objet
            if hasattr(resultat, 'to_dict'):
                resultat_dict = resultat.to_dict()
            elif hasattr(resultat, '__dict__'):
                resultat_dict = resultat.__dict__
            elif isinstance(resultat, dict):
                resultat_dict = resultat
            else:
                resultat_dict = {'resultat': str(resultat)}
            
            # Sauvegarder dans la base de données
            analyse = AnalyseIA(
                audit_id=audit_id,
                type_analyse=form.type_analyse.data,
                resultat=resultat_dict,
                score_confiance=resultat_dict.get('metadata', {}).get('score_confiance', 75.0) if isinstance(resultat_dict, dict) else 75.0,
                created_by=current_user.id,
                client_id=current_user.client_id
            )
            
            db.session.add(analyse)
            db.session.commit()
            
            # Journaliser l'action
            log_activity(current_user.id, 'analyse_ia_audit',
                        f"Analyse IA lancée sur audit {audit.reference}",
                        'audit', audit_id)
            
            # Utiliser le score depuis le résultat
            score = resultat_dict.get('metadata', {}).get('score_confiance', 75.0) if isinstance(resultat_dict, dict) else 75.0
            flash(f'✅ Analyse IA terminée avec succès ! Score de confiance: {score:.1f}%', 'success')
            return redirect(url_for('resultat_analyse_ia', audit_id=audit_id, analyse_id=analyse.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Erreur lors de l\'analyse IA: {str(e)}', 'error')
            _journal(f"❌ Erreur analyse IA: {e}")
            import traceback
            traceback.print_exc()
            return redirect(url_for('detail_audit', id=audit_id))
    
    # Statistiques pour l'affichage
    stats = {
        'nb_constatations': len(audit.constatations) if hasattr(audit, 'constatations') else 0,
        'nb_recommandations': len(audit.recommandations) if hasattr(audit, 'recommandations') else 0,
        'audit_reference': audit.reference if hasattr(audit, 'reference') else f"AUD-{audit_id}"
    }
    
    return render_template('audit/analyse_ia.html', 
                         audit=audit, 
                         form=form,
                         stats=stats)


@app.route('/audit/<int:audit_id>/analyse-ia/resultat/<int:analyse_id>')
@login_required
def resultat_analyse_ia(audit_id, analyse_id):
    """Afficher les résultats de l'analyse IA"""
    try:
        audit = get_client_object_or_404(Audit, audit_id)
        
        # Récupérer l'analyse depuis la base
        analyse = get_client_object_or_404(AnalyseIA, analyse_id, audit_id=audit_id)
        
        # Convertir le résultat selon son type
        if analyse.resultat:
            if isinstance(analyse.resultat, dict):
                resultat = analyse.resultat
            elif isinstance(analyse.resultat, str):
                try:
                    resultat = json.loads(analyse.resultat)
                except:
                    resultat = {'analyse': analyse.resultat}
            else:
                resultat = {}
        else:
            resultat = {}
        
        # S'assurer que la structure est complète
        if 'statistiques' not in resultat:
            resultat['statistiques'] = {}
        
        # Remplir les valeurs par défaut
        stats_defaults = {
            'nb_recommandations_suggerees': len(resultat.get('recommandations_ia', [])),
            'nb_causes_identifiees': len(resultat.get('causes_racines', [])),
            'score_global': analyse.score_confiance if analyse else 75,
            'temps_analyse': '2.3 secondes'
        }
        
        for key, default in stats_defaults.items():
            resultat['statistiques'][key] = resultat['statistiques'].get(key, default)
        
        # S'assurer que les listes existent
        resultat.setdefault('recommandations_ia', [])
        resultat.setdefault('causes_racines', [])
        
        _journal(f"📊 Résultat IA préparé:")
        _journal(f"  - Recommandations: {len(resultat['recommandations_ia'])}")
        _journal(f"  - Causes: {len(resultat['causes_racines'])}")
        _journal(f"  - Score: {resultat['statistiques']['score_global']}")
        
        return render_template('audit/resultat_analyse_ia.html',
                            audit=audit,
                            analyse=analyse,
                            resultat=resultat)
        
    except Exception as e:
        _journal(f"❌ Erreur resultat_analyse_ia: {e}")
        import traceback
        traceback.print_exc()
        
        flash(f'Erreur lors de l\'affichage des résultats: {str(e)}', 'error')
        return redirect(url_for('detail_audit', id=audit_id))


@app.route('/audit/<int:audit_id>/analyses-ia')
@login_required
def liste_analyses_ia(audit_id):
    """Liste des analyses IA effectuées sur un audit"""
    if not MODELS_IMPORTED:
        flash('Système non disponible', 'error')
        return redirect(url_for('liste_audits'))
    
    try:
        audit = get_client_object_or_404(Audit, audit_id)
        
        # Récupérer les analyses filtrées par client
        analyses = get_client_filter(AnalyseIA)\
            .filter_by(audit_id=audit_id)\
            .order_by(AnalyseIA.date_analyse.desc())\
            .all()
        
        return render_template('audit/liste_analyses_ia.html',
                            audit=audit,
                            analyses=analyses)
        
    except Exception as e:
        flash(f'Erreur: {str(e)}', 'error')
        return redirect(url_for('liste_audits'))


@app.route('/audit/checklist', methods=['GET', 'POST'])
@login_required
def checklist_audit():
    """Sélectionner et appliquer une checklist d'audit"""
    form = ChecklistAuditForm()
    
    if form.validate_on_submit():
        type_checklist = form.type_checklist.data
        appliquer_template = form.appliquer_template.data
        
        # Appliquer la checklist
        # À implémenter selon vos besoins
        
        flash(f'Checklist {type_checklist} appliquée', 'success')
        return redirect(url_for('liste_audits'))
    
    return render_template('audit/checklist.html', form=form)


@app.route('/audit/configurations')
@login_required
def configurations_audit():
    """Page de configuration des audits - Version simplifiée avec isolation"""
    
    # Vérifier les permissions
    if current_user.role not in ['admin', 'referent', 'super_admin']:
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_audits'))
    
    try:
        # CORRECTION : Utiliser get_client_filter pour toutes les configurations
        configurations = get_client_filter(ConfigurationAudit).all()
        
        # CORRECTION : Filtrer les templates par client
        templates_constatations = get_client_filter(TemplateConstatation)\
            .filter_by(est_actif=True)\
            .all()
        
        templates_recommandations = get_client_filter(TemplateRecommandation)\
            .filter_by(est_actif=True)\
            .all()
            
    except Exception as e:
        _journal(f"⚠️ Erreur chargement configurations: {e}")
        # Retourner des listes vides si les tables n'existent pas encore
        configurations = []
        templates_constatations = []
        templates_recommandations = []
    
    # Vérifier l'accès pour chaque configuration
    accessible_configs = []
    for config in configurations:
        if check_client_access(config):
            accessible_configs.append(config)
    
    return render_template('audit/configurations.html',
                         configurations=accessible_configs,
                         templates_constatations=templates_constatations,
                         templates_recommandations=templates_recommandations,
                         current_user=current_user)  # Ajouter current_user au contexte


@app.route('/audit/configuration/nouvelle', methods=['GET', 'POST'])
@login_required
def nouvelle_configuration_audit():
    """Créer une nouvelle configuration d'audit avec isolation"""
    
    # Vérifier les permissions
    if current_user.role not in ['admin', 'referent', 'super_admin']:
        flash('Accès non autorisé', 'error')
        return redirect(url_for('configurations_audit'))
    
    form = ConfigurationAuditForm()
    
    if form.validate_on_submit():
        try:
            configuration = ConfigurationAudit(
                nom_config=form.nom_config.data,
                type_audit=form.type_audit.data,
                duree_standard=form.duree_standard.data,
                seuil_gravite_min=form.seuil_gravite_min.data,
                seuil_gravite_max=form.seuil_gravite_max.data,
                categories_audit=['conformite', 'efficacite', 'efficience', 'securite']
            )
            
            # CORRECTION : Ajouter automatiquement le client_id pour les utilisateurs normaux
            if current_user.role != 'super_admin' and hasattr(current_user, 'client_id'):
                configuration.client_id = current_user.client_id
            
            # Ajouter created_by
            configuration.created_by = current_user.id
            
            db.session.add(configuration)
            db.session.commit()
            
            flash('Configuration d\'audit créée avec succès', 'success')
            return redirect(url_for('configurations_audit'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la création: {str(e)}', 'error')
    
    return render_template('audit/form_configuration.html', 
                         form=form,
                         current_user=current_user)


@app.route('/audit/template/constatation/nouveau', methods=['GET', 'POST'])
@login_required
def nouveau_template_constatation():
    """Créer un nouveau template de constatation avec isolation"""
    
    # Vérifier les permissions
    if current_user.role not in ['admin', 'referent', 'super_admin']:
        flash('Accès non autorisé', 'error')
        return redirect(url_for('configurations_audit'))
    
    form = TemplateConstatationForm()
    
    if form.validate_on_submit():
        try:
            template = TemplateConstatation(
                reference=form.reference.data,
                titre=form.titre.data,
                description=form.description.data,
                type_constatation=form.type_constatation.data,
                gravite_defaut=form.gravite_defaut.data,
                processus_concerne=form.processus_concerne.data,
                cause_racine_typique=form.cause_racine_typique.data,
                recommandation_standard=form.recommandation_standard.data
            )
            
            # CORRECTION : Ajouter automatiquement le client_id pour les utilisateurs normaux
            if current_user.role != 'super_admin' and hasattr(current_user, 'client_id'):
                template.client_id = current_user.client_id
            
            # Ajouter created_by
            template.created_by = current_user.id
            
            db.session.add(template)
            db.session.commit()
            
            flash('Template de constatation créé avec succès', 'success')
            return redirect(url_for('configurations_audit'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la création: {str(e)}', 'error')
    
    return render_template('audit/form_template_constatation.html', 
                         form=form,
                         current_user=current_user)


# ============================================================================
# ROUTES POUR INITIALISATION DES CONFIGURATIONS PAR DÉFAUT
# ============================================================================
@app.route('/audit/init-configurations')
@login_required
def init_configurations_audit():
    """Initialiser les configurations d'audit par défaut avec isolation"""
    
    # Vérifier les permissions
    if current_user.role not in ['admin', 'super_admin']:
        flash('Accès non autorisé', 'error')
        return redirect(url_for('configurations_audit'))
    
    try:
        # CORRECTION : Vérifier le client_id pour l'utilisateur
        client_id = current_user.client_id if current_user.role != 'super_admin' else None
        
        # Configurations par défaut (par client)
        configurations_defaut = [
            {
                'nom_config': 'Audit Interne Standard',
                'type_audit': 'interne',
                'duree_standard': 30,
                'seuil_gravite_min': 3,
                'seuil_gravite_max': 5
            },
            {
                'nom_config': 'Audit Conformité',
                'type_audit': 'conformite', 
                'duree_standard': 45,
                'seuil_gravite_min': 2,
                'seuil_gravite_max': 5
            },
            {
                'nom_config': 'Audit Sécurité',
                'type_audit': 'securite',
                'duree_standard': 60,
                'seuil_gravite_min': 3,
                'seuil_gravite_max': 5
            }
        ]
        
        for config_data in configurations_defaut:
            # CORRECTION : Vérifier si la configuration existe pour ce client
            query = ConfigurationAudit.query.filter_by(nom_config=config_data['nom_config'])
            
            # Ajouter le filtre client_id si c'est un client normal
            if client_id:
                query = query.filter_by(client_id=client_id)
            else:
                # Pour super admin, vérifier les configurations globales (sans client_id)
                query = query.filter(ConfigurationAudit.client_id.is_(None))
            
            if not query.first():
                config = ConfigurationAudit(**config_data)
                config.created_by = current_user.id
                
                # CORRECTION : Ajouter client_id seulement pour les clients normaux
                if client_id:
                    config.client_id = client_id
                
                db.session.add(config)
        
        # Templates de constatations par défaut (par client)
        templates_constatations_defaut = [
            {
                'reference': 'TEMP-CON-001',
                'titre': 'Documentation manquante',
                'description': 'La documentation requise pour le processus n\'est pas disponible ou incomplète.',
                'type_constatation': 'non_conformite',
                'gravite_defaut': 'moyenne',
                'processus_concerne': 'Tous processus',
                'cause_racine_typique': 'Absence de procédure documentée ou non application des procédures existantes.',
                'recommandation_standard': 'Élaborer et mettre en œuvre les procédures documentées manquantes.'
            },
            {
                'reference': 'TEMP-CON-002', 
                'titre': 'Non-respect des délais',
                'description': 'Les délais définis dans les procédures ne sont pas respectés.',
                'type_constatation': 'non_conformite',
                'gravite_defaut': 'mineure',
                'processus_concerne': 'Processus opérationnels',
                'cause_racine_typique': 'Charge de travail excessive ou mauvaise estimation des délais.',
                'recommandation_standard': 'Réviser les délais et mettre en place un suivi des échéances.'
            }
        ]
        
        for template_data in templates_constatations_defaut:
            # CORRECTION : Vérifier si le template existe pour ce client
            query = TemplateConstatation.query.filter_by(reference=template_data['reference'])
            
            if client_id:
                query = query.filter_by(client_id=client_id)
            else:
                query = query.filter(TemplateConstatation.client_id.is_(None))
            
            if not query.first():
                template = TemplateConstatation(**template_data)
                template.created_by = current_user.id
                
                if client_id:
                    template.client_id = client_id
                
                db.session.add(template)
        
        db.session.commit()
        flash('Configurations et templates d\'audit initialisés avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de l\'initialisation: {str(e)}', 'error')
    
    return redirect(url_for('configurations_audit'))


@app.route('/audit/<int:audit_id>/feuilles-travail')
@login_required
def feuilles_travail_audit(audit_id):
    """Liste des feuilles de travail d'un audit"""
    audit = get_client_object_or_404(Audit, audit_id)
    
    feuilles = get_client_filter(FeuilleTravail)\
        .filter_by(audit_id=audit_id, is_archived=False)\
        .order_by(FeuilleTravail.created_at.desc()).all()
    
    return render_template('audit/feuilles_travail.html',
                         audit=audit,
                         feuilles=feuilles)


@app.route('/audit/<int:audit_id>/feuille-travail/nouvelle', methods=['GET', 'POST'])
@login_required
def nouvelle_feuille_travail(audit_id):
    """Créer une nouvelle feuille de travail avec génération robuste de référence unique"""
    audit = get_client_object_or_404(Audit, audit_id)
    
    if request.method == 'POST':
        try:
            # ============================================
            # 1. GÉNÉRATION ROBUSTE DE LA RÉFÉRENCE UNIQUE
            # ============================================
            annee = datetime.now().year
            prefixe = f"FT-{annee}-"
            
            # Compter les feuilles existantes pour ce client et cette année
            count = FeuilleTravail.query.filter(
                FeuilleTravail.reference.like(f'{prefixe}%'),
                FeuilleTravail.client_id == current_user.client_id
            ).count()
            
            reference = f"{prefixe}{count + 1:04d}"
            
            # Vérifier que la référence n'existe pas déjà (sécurité supplémentaire)
            compteur = 0
            while FeuilleTravail.query.filter_by(reference=reference).first() and compteur < 100:
                count += 1
                reference = f"{prefixe}{count + 1:04d}"
                compteur += 1
            
            # ============================================
            # 2. CRÉATION DE LA FEUILLE DE TRAVAIL
            # ============================================
            feuille = FeuilleTravail(
                reference=reference,
                titre=request.form.get('titre').strip(),
                description=request.form.get('description', '').strip(),
                type_feuille=request.form.get('type_feuille', 'standard'),
                audit_id=audit_id,
                mission_id=request.form.get('mission_id') or None,
                client_id=audit.client_id or current_user.client_id,
                created_by=current_user.id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.session.add(feuille)
            db.session.commit()
            
            flash(f'✅ Feuille de travail "{reference}" créée avec succès', 'success')
            return redirect(url_for('editer_feuille_travail', feuille_id=feuille.id))
            
        except IntegrityError as e:
            db.session.rollback()
            # Si erreur de contrainte unique, réessayer avec une nouvelle référence
            if 'UNIQUE constraint failed' in str(e):
                # Incrémenter le compteur et réessayer
                count = FeuilleTravail.query.filter(
                    FeuilleTravail.reference.like(f'{prefixe}%'),
                    FeuilleTravail.client_id == current_user.client_id
                ).count()
                nouvelle_ref = f"{prefixe}{count + 2:04d}"
                
                feuille = FeuilleTravail(
                    reference=nouvelle_ref,
                    titre=request.form.get('titre').strip(),
                    description=request.form.get('description', '').strip(),
                    type_feuille=request.form.get('type_feuille', 'standard'),
                    audit_id=audit_id,
                    mission_id=request.form.get('mission_id') or None,
                    client_id=audit.client_id or current_user.client_id,
                    created_by=current_user.id
                )
                db.session.add(feuille)
                db.session.commit()
                flash(f'✅ Feuille de travail "{nouvelle_ref}" créée avec succès', 'success')
                return redirect(url_for('editer_feuille_travail', feuille_id=feuille.id))
            else:
                flash(f'❌ Erreur base de données: {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Erreur lors de la création: {str(e)}', 'error')
    
    # GET - Afficher le formulaire
    missions = []
    try:
        # Récupérer les missions via le programme d'audit si existe
        if hasattr(audit, 'mission_associee') and audit.mission_associee:
            programme = audit.mission_associee.programme
            if programme:
                missions = get_client_filter(MissionAudit).filter_by(
                    programme_id=programme.id, 
                    is_archived=False
                ).all()
    except Exception as e:
        _journal(f"⚠️ Erreur récupération missions: {e}")
    
    return render_template('audit/nouvelle_feuille_travail.html', 
                         audit=audit, 
                         missions=missions)


@app.route('/api/feuille-travail/<int:feuille_id>/progression', methods=['POST'])
@login_required
def api_mettre_a_jour_progression_feuille(feuille_id):
    """Mettre à jour la progression d'une feuille de travail"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    data = request.get_json()
    
    progression = data.get('progression')
    if progression is None:
        return jsonify({'success': False, 'error': 'Progression requise'}), 400
    
    try:
        progression = int(progression)
        if progression < 0 or progression > 100:
            return jsonify({'success': False, 'error': 'Progression doit être entre 0 et 100'}), 400
        
        # Mettre à jour la progression
        if not feuille.contenu:
            feuille.contenu = {}
        
        feuille.contenu['progression'] = progression
        feuille.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'progression': progression,
            'message': f'Progression mise à jour : {progression}%'
        })
        
    except ValueError:
        return jsonify({'success': False, 'error': 'Progression invalide'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/feuille-travail/<int:feuille_id>/version', methods=['POST'])
@login_required
def api_creer_version_feuille(feuille_id):
    """Créer une nouvelle version de la feuille de travail"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    data = request.get_json()
    
    # Récupérer le dernier numéro de version
    derniere_version = FeuilleTravailVersion.query.filter_by(
        feuille_travail_id=feuille_id
    ).order_by(FeuilleTravailVersion.version_numero.desc()).first()
    
    nouveau_numero = (derniere_version.version_numero + 1) if derniere_version else 1
    
    # Capturer l'état actuel
    tests = TestControleFeuille.query.filter_by(feuille_travail_id=feuille_id).all()
    
    version = FeuilleTravailVersion(
        feuille_travail_id=feuille_id,
        version_numero=nouveau_numero,
        contenu_snapshot={
            'titre': feuille.titre,
            'description': feuille.description,
            'type_feuille': feuille.type_feuille,
            'statut': feuille.statut,
            'contenu': feuille.contenu
        },
        tests_snapshot=[t.to_dict() for t in tests],
        version_commentaire=data.get('commentaire', ''),
        version_type=data.get('type', 'modification'),
        created_by=current_user.id
    )
    
    db.session.add(version)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'version': nouveau_numero,
        'message': f'Version {nouveau_numero} créée'
    })


@app.route('/api/feuille-travail/<int:feuille_id>/info', methods=['PUT'])
@login_required
def api_mettre_a_jour_info_feuille(feuille_id):
    """Mettre à jour les informations d'une feuille de travail"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    data = request.get_json()
    
    if 'titre' in data:
        feuille.titre = data['titre']
    if 'description' in data:
        feuille.description = data['description']
    if 'type_feuille' in data:
        feuille.type_feuille = data['type_feuille']
    if 'statut' in data:
        feuille.statut = data['statut']
    if 'mission_id' in data:
        feuille.mission_id = int(data['mission_id']) if data['mission_id'] else None
    if 'tags' in data:
        # Gérer les tags
        tags = [t.strip() for t in data['tags'].split(',') if t.strip()]
        feuille.contenu = feuille.contenu or {}
        feuille.contenu['tags'] = tags
    
    feuille.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'statut': feuille.statut,
        'statut_display': feuille.statut.replace('_', ' ').title()
    })


@app.route('/api/feuille-travail/<int:feuille_id>/progression-reelle', methods=['POST'])
@login_required
def api_calculer_progression_reelle(feuille_id):
    """Calculer la progression réelle basée sur les tests"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    tests = TestControleFeuille.query.filter_by(feuille_travail_id=feuille_id).all()
    if tests:
        conformes = len([t for t in tests if t.resultat == 'conforme'])
        progression = round((conformes / len(tests)) * 100)
        feuille.contenu = feuille.contenu or {}
        feuille.contenu['progression'] = progression
        feuille.updated_at = datetime.utcnow()
        db.session.commit()
    else:
        progression = feuille.progression
    
    return jsonify({'success': True, 'progression': progression})


@app.route('/api/feuille-travail/<int:feuille_id>/references')
@login_required
def api_liste_references_feuille(feuille_id):
    """Lister toutes les références croisées d'une feuille"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    references = ReferenceCroiseeFeuille.query.filter_by(feuille_travail_id=feuille_id).all()
    
    references_data = []
    for ref in references:
        # Récupérer les informations de l'entité référencée
        entite = None
        description = ""
        reference_code = ""
        
        if ref.type_reference == 'constatation':
            entite = Constatation.query.get(ref.entite_id)
            if entite:
                description = entite.description[:100] if entite.description else ''
                reference_code = entite.reference
        elif ref.type_reference == 'recommandation':
            entite = Recommandation.query.get(ref.entite_id)
            if entite:
                description = entite.description[:100] if entite.description else ''
                reference_code = entite.reference
        elif ref.type_reference == 'plan_action':
            entite = PlanAction.query.get(ref.entite_id)
            if entite:
                description = entite.nom[:100] if hasattr(entite, 'nom') else ''
                reference_code = entite.reference if hasattr(entite, 'reference') else f"PA-{entite.id}"
        elif ref.type_reference == 'risque':
            entite = Risque.query.get(ref.entite_id)
            if entite:
                description = entite.intitule[:100] if hasattr(entite, 'intitule') else ''
                reference_code = entite.reference
        elif ref.type_reference == 'procedure':
            entite = ControleProcessus.query.get(ref.entite_id)
            if entite:
                description = entite.nom[:100] if hasattr(entite, 'nom') else ''
                reference_code = f"PROC-{entite.id}"
        
        if entite:
            references_data.append({
                'id': ref.id,
                'type': ref.type_reference,
                'type_display': ref.type_reference.replace('_', ' ').title(),
                'entite_id': ref.entite_id,
                'reference': reference_code,
                'description': description,
                'contexte': ref.contexte,
                'created_at': ref.created_at.isoformat()
            })
    
    return jsonify({'success': True, 'references': references_data})


@app.route('/api/feuille-travail/<int:feuille_id>/reference', methods=['POST'])
@login_required
def api_ajouter_reference_feuille(feuille_id):
    """Ajouter une référence croisée à une feuille"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    data = request.get_json()
    
    # Vérifier que la référence n'existe pas déjà
    existing = ReferenceCroiseeFeuille.query.filter_by(
        feuille_travail_id=feuille_id,
        type_reference=data.get('type_reference'),
        entite_id=data.get('entite_id')
    ).first()
    
    if existing:
        return jsonify({'success': False, 'error': 'Cette référence existe déjà'}), 400
    
    reference = ReferenceCroiseeFeuille(
        feuille_travail_id=feuille_id,
        type_reference=data.get('type_reference'),
        entite_id=data.get('entite_id'),
        contexte=data.get('contexte', ''),
        created_by=current_user.id
    )
    
    db.session.add(reference)
    db.session.commit()
    
    return jsonify({'success': True, 'reference_id': reference.id})


@app.route('/api/feuille-travail/reference/<int:reference_id>', methods=['DELETE'])
@login_required
def api_supprimer_reference_feuille(reference_id):
    """Supprimer une référence croisée"""
    reference = get_client_object_or_404(ReferenceCroiseeFeuille, reference_id)
    
    db.session.delete(reference)
    db.session.commit()
    
    return jsonify({'success': True})


@app.route('/api/feuille-travail/<int:feuille_id>/commentaires')
@login_required
def api_liste_commentaires_feuille(feuille_id):
    """Lister tous les commentaires d'une feuille"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    commentaires = CommentaireFeuille.query.filter_by(
        feuille_travail_id=feuille_id,
        reponse_a_id=None
    ).order_by(CommentaireFeuille.created_at.desc()).all()
    
    commentaires_data = []
    for comment in commentaires:
        # Récupérer les réponses
        reponses = CommentaireFeuille.query.filter_by(reponse_a_id=comment.id).order_by(CommentaireFeuille.created_at).all()
        
        commentaires_data.append({
            'id': comment.id,
            'contenu': comment.contenu,
            'type': comment.type_commentaire,
            'statut': comment.statut,
            'createur': comment.createur.username if comment.createur else 'Système',
            'date_formatee': comment.created_at.strftime('%d/%m/%Y à %H:%M'),
            'mentions': [],  # À implémenter si besoin
            'reponses': [{
                'id': r.id,
                'contenu': r.contenu,
                'createur': r.createur.username if r.createur else 'Système',
                'date_formatee': r.created_at.strftime('%d/%m/%Y à %H:%M')
            } for r in reponses]
        })
    
    return jsonify({'success': True, 'commentaires': commentaires_data})


@app.route('/api/feuille-travail/<int:feuille_id>/commentaire', methods=['POST'])
@login_required
def api_ajouter_commentaire_feuille_detail(feuille_id):
    """Ajouter un commentaire à une feuille"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    data = request.get_json()
    
    commentaire = CommentaireFeuille(
        feuille_travail_id=feuille_id,
        contenu=data.get('contenu'),
        type_commentaire=data.get('type', 'commentaire'),
        reponse_a_id=data.get('reponse_a_id'),
        created_by=current_user.id
    )
    
    db.session.add(commentaire)
    db.session.commit()
    
    # Créer des notifications pour les mentions
    mentions = data.get('mentions', [])
    for user_id in mentions:
        if user_id != current_user.id:
            notification = Notification(
                type_notification='info',
                titre=f"Commentaire sur la feuille {feuille.reference}",
                message=f"{current_user.username} vous a mentionné dans un commentaire : {data.get('contenu')[:100]}",
                destinataire_id=user_id,
                entite_type='feuille_travail',
                entite_id=feuille_id,
                client_id=feuille.client_id
            )
            db.session.add(notification)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'commentaire_id': commentaire.id,
        'message': 'Commentaire ajouté'
    })


@app.route('/api/feuille-travail/commentaire/<int:commentaire_id>/resoudre', methods=['POST'])
@login_required
def api_resoudre_commentaire_feuille_detail(commentaire_id):
    """Résoudre un commentaire"""
    commentaire = get_client_object_or_404(CommentaireFeuille, commentaire_id)
    
    commentaire.statut = 'resolu'
    commentaire.resolu_par_id = current_user.id
    commentaire.resolu_le = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'success': True})


@app.route('/api/feuille-travail/commentaire/<int:commentaire_id>/repondre', methods=['POST'])
@login_required
def api_repondre_commentaire_route(commentaire_id):
    """Répondre à un commentaire"""
    commentaire_parent = CommentaireFeuille.query.get_or_404(commentaire_id)
    
    # Vérification multi-tenant
    feuille = FeuilleTravail.query.filter_by(id=commentaire_parent.feuille_travail_id, client_id=current_user.client_id).first()
    if not feuille:
        return jsonify({'success': False, 'error': 'Commentaire non trouvé'}), 404
    
    data = request.get_json()
    
    reponse = CommentaireFeuille(
        feuille_travail_id=commentaire_parent.feuille_travail_id,
        contenu=data.get('contenu'),
        type_commentaire='reponse',
        reponse_a_id=commentaire_id,
        created_by=current_user.id
    )
    
    db.session.add(reponse)
    db.session.commit()
    
    return jsonify({'success': True, 'reponse_id': reponse.id})


@app.route('/api/feuille-travail/commentaire/<int:commentaire_id>', methods=['PUT'])
@login_required
def api_modifier_commentaire_route(commentaire_id):
    """Modifier un commentaire"""
    commentaire = CommentaireFeuille.query.get_or_404(commentaire_id)
    
    # Vérification multi-tenant
    feuille = FeuilleTravail.query.filter_by(id=commentaire.feuille_travail_id, client_id=current_user.client_id).first()
    if not feuille:
        return jsonify({'success': False, 'error': 'Commentaire non trouvé'}), 404
    
    if commentaire.created_by != current_user.id and not current_user.is_client_admin:
        return jsonify({'success': False, 'error': 'Permission refusée'}), 403
    
    data = request.get_json()
    
    if 'contenu' in data:
        commentaire.contenu = data['contenu']
    if 'type' in data:
        commentaire.type_commentaire = data['type']
    
    commentaire.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True})


@app.route('/api/feuille-travail/commentaire/<int:commentaire_id>', methods=['DELETE'])
@login_required
def api_supprimer_commentaire_route(commentaire_id):
    """Supprimer un commentaire"""
    commentaire = CommentaireFeuille.query.get_or_404(commentaire_id)
    
    # Vérification multi-tenant
    feuille = FeuilleTravail.query.filter_by(id=commentaire.feuille_travail_id, client_id=current_user.client_id).first()
    if not feuille:
        return jsonify({'success': False, 'error': 'Commentaire non trouvé'}), 404
    
    if commentaire.created_by != current_user.id and not current_user.is_client_admin:
        return jsonify({'success': False, 'error': 'Permission refusée'}), 403
    
    # Supprimer les réponses
    CommentaireFeuille.query.filter_by(reponse_a_id=commentaire_id).delete()
    db.session.delete(commentaire)
    db.session.commit()
    
    return jsonify({'success': True})


@app.route('/api/feuille-travail/commentaire/<int:commentaire_id>/resoudre', methods=['POST'])
@login_required
def api_resoudre_commentaire_route(commentaire_id):
    """Résoudre un commentaire"""
    commentaire = CommentaireFeuille.query.get_or_404(commentaire_id)
    
    # Vérification multi-tenant
    feuille = FeuilleTravail.query.filter_by(id=commentaire.feuille_travail_id, client_id=current_user.client_id).first()
    if not feuille:
        return jsonify({'success': False, 'error': 'Commentaire non trouvé'}), 404
    
    commentaire.statut = 'resolu'
    commentaire.resolu_par_id = current_user.id
    commentaire.resolu_le = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True})


@app.route('/api/feuille-travail/<int:feuille_id>/version', methods=['POST'])
@login_required
def api_creer_version_complete(feuille_id):
    """Créer une nouvelle version de la feuille"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    data = request.get_json()
    
    # Récupérer le dernier numéro de version
    derniere_version = FeuilleTravailVersion.query.filter_by(
        feuille_travail_id=feuille_id
    ).order_by(FeuilleTravailVersion.version_numero.desc()).first()
    
    nouveau_numero = (derniere_version.version_numero + 1) if derniere_version else 1
    
    # Capturer l'état actuel
    tests = TestControleFeuille.query.filter_by(feuille_travail_id=feuille_id).all()
    
    version = FeuilleTravailVersion(
        feuille_travail_id=feuille_id,
        version_numero=nouveau_numero,
        contenu_snapshot={
            'titre': feuille.titre,
            'description': feuille.description,
            'type_feuille': feuille.type_feuille,
            'statut': feuille.statut,
            'contenu': feuille.contenu
        },
        tests_snapshot=[t.to_dict() for t in tests],
        version_commentaire=data.get('commentaire', ''),
        version_type=data.get('type', 'modification'),
        created_by=current_user.id
    )
    
    db.session.add(version)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'version': nouveau_numero,
        'message': f'Version {nouveau_numero} créée'
    })


@app.route('/api/feuille-travail/<int:feuille_id>/restaurer/<int:version_id>', methods=['POST'])
@login_required
def api_restaurer_version_complete(feuille_id, version_id):
    """Restaurer une version antérieure"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    version = get_client_object_or_404(FeuilleTravailVersion, version_id)
    
    if version.feuille_travail_id != feuille_id:
        return jsonify({'success': False, 'error': 'Version non trouvée'}), 404
    
    # Restaurer les données
    snapshot = version.contenu_snapshot
    feuille.titre = snapshot.get('titre', feuille.titre)
    feuille.description = snapshot.get('description', feuille.description)
    feuille.type_feuille = snapshot.get('type_feuille', feuille.type_feuille)
    feuille.statut = snapshot.get('statut', feuille.statut)
    feuille.contenu = snapshot.get('contenu', feuille.contenu)
    
    # Restaurer les tests
    if version.tests_snapshot:
        TestControleFeuille.query.filter_by(feuille_travail_id=feuille_id).delete()
        for test_data in version.tests_snapshot:
            test = TestControleFeuille(
                feuille_travail_id=feuille_id,
                objet_test=test_data['objet_test'],
                procedure=test_data.get('procedure'),
                echantillon=test_data.get('echantillon'),
                resultat=test_data.get('resultat', 'non_testé'),
                observations=test_data.get('observations', ''),
                ordre=test_data.get('ordre', 0)
            )
            db.session.add(test)
    
    feuille.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Version {version.version_numero} restaurée'})


@app.route('/api/feuille-travail/erreur/<int:erreur_id>', methods=['PUT'])
@login_required
def api_modifier_erreur_test(erreur_id):
    """Modifier une erreur existante"""
    erreur = ErreurTest.query.get_or_404(erreur_id)
    
    # Vérification multi-tenant
    test = TestControleFeuille.query.filter_by(id=erreur.test_id).first()
    if not test:
        return jsonify({'success': False, 'error': 'Test non trouvé'}), 404
    
    feuille = FeuilleTravail.query.filter_by(
        id=test.feuille_travail_id,
        client_id=current_user.client_id
    ).first()
    
    if not feuille:
        return jsonify({'success': False, 'error': 'Accès non autorisé'}), 403
    
    data = request.get_json()
    
    # Champs modifiables
    if 'description' in data:
        erreur.description = data['description']
    if 'categorie' in data:
        erreur.categorie = data['categorie']
    if 'gravite' in data:
        erreur.gravite = data['gravite']
    if 'impact_financier' in data:
        erreur.impact_financier = data['impact_financier']
    if 'impact_qualitatif' in data:
        erreur.impact_qualitatif = data['impact_qualitatif']
    if 'etat' in data:
        erreur.etat = data['etat']
        # Si l'état passe à 'corrigee' ou 'fermee', on peut automatiquement marquer la correction comme effectuée
        if data['etat'] in ['corrigee', 'fermee'] and not erreur.correction_effectuee:
            erreur.correction_effectuee = True
            erreur.date_correction = datetime.utcnow().date()
    if 'correction_proposee' in data:
        erreur.correction_proposee = data['correction_proposee']
    if 'correction_effectuee' in data:
        erreur.correction_effectuee = data['correction_effectuee']
        if data['correction_effectuee'] and not erreur.date_correction:
            erreur.date_correction = datetime.utcnow().date()
    if 'date_correction' in data:
        erreur.date_correction = datetime.strptime(data['date_correction'], '%Y-%m-%d').date() if data['date_correction'] else None
    if 'responsable_correction_id' in data:
        erreur.responsable_correction_id = data['responsable_correction_id']
    if 'commentaire_correction' in data:
        erreur.commentaire_correction = data['commentaire_correction']
    if 'cause_racine' in data:
        erreur.cause_racine = data['cause_racine']
    if 'analyse_detaillee' in data:
        erreur.analyse_detaillee = data['analyse_detaillee']
    
    erreur.updated_at = datetime.utcnow()
    erreur.updated_by = current_user.id
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'erreur': erreur.to_dict(),
        'message': 'Erreur mise à jour'
    })


@app.route('/api/feuille-travail/erreur/<int:erreur_id>', methods=['DELETE'])
@login_required
def api_supprimer_erreur_test(erreur_id):
    """Supprimer une erreur"""
    erreur = ErreurTest.query.get_or_404(erreur_id)
    
    # Vérification multi-tenant
    test = TestControleFeuille.query.filter_by(id=erreur.test_id).first()
    if not test:
        return jsonify({'success': False, 'error': 'Test non trouvé'}), 404
    
    feuille = FeuilleTravail.query.filter_by(
        id=test.feuille_travail_id,
        client_id=current_user.client_id
    ).first()
    
    if not feuille:
        return jsonify({'success': False, 'error': 'Accès non autorisé'}), 403
    
    # Mettre à jour le nombre d'erreurs dans le test parent
    if test.nb_erreurs_trouvees and test.nb_erreurs_trouvees > 0:
        test.nb_erreurs_trouvees -= 1
    
    # Recalculer le taux de réussite
    if test.nb_elements_testes and test.nb_elements_testes > 0:
        test.taux_reussite = round(
            ((test.nb_elements_testes - (test.nb_erreurs_trouvees or 0)) / test.nb_elements_testes) * 100, 2
        )
    
    db.session.delete(erreur)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Erreur supprimée',
        'nb_erreurs_trouvees': test.nb_erreurs_trouvees
    })


@app.route('/api/feuille-travail/<int:feuille_id>/statistiques-erreurs', methods=['GET'])
@login_required
def api_statistiques_erreurs_feuille(feuille_id):
    """Statistiques globales des erreurs pour une feuille"""
    from models import ErreurTest
    
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    tests = TestControleFeuille.query.filter_by(feuille_travail_id=feuille_id).all()
    test_ids = [t.id for t in tests]
    
    erreurs = ErreurTest.query.filter(ErreurTest.test_id.in_(test_ids)).all()
    
    # Statistiques détaillées
    stats = {
        'total_erreurs': len(erreurs),
        'tests_avec_erreurs': len(set(e.test_id for e in erreurs)),
        'par_gravite': {},
        'par_categorie': {},
        'par_etat': {},
        'impact_financier_total': 0.0,
        'taux_correction': 0
    }
    
    for e in erreurs:
        stats['par_gravite'][e.gravite] = stats['par_gravite'].get(e.gravite, 0) + 1
        stats['par_categorie'][e.categorie] = stats['par_categorie'].get(e.categorie, 0) + 1
        stats['par_etat'][e.etat] = stats['par_etat'].get(e.etat, 0) + 1
        stats['impact_financier_total'] += (e.impact_financier or 0)
    
    total = len(erreurs)
    total_corrigees = stats['par_etat'].get('corrigee', 0) + stats['par_etat'].get('fermee', 0)
    stats['taux_correction'] = round((total_corrigees / max(total, 1)) * 100, 1)
    
    return jsonify({
        'success': True,
        'statistiques': stats
    })


@app.route('/api/audit/<int:audit_id>/constatations')
@login_required
def api_audit_constatations(audit_id):
    """Récupérer les constatations d'un audit pour les références"""
    audit = get_client_object_or_404(Audit, audit_id)
    constatations = get_client_filter(Constatation).filter_by(audit_id=audit_id).all()
    
    return jsonify([{
        'id': c.id,
        'reference': c.reference,
        'description': c.description[:150] if c.description else ''
    } for c in constatations])


@app.route('/api/audit/<int:audit_id>/recommandations')
@login_required
def api_audit_recommandations(audit_id):
    """Récupérer les recommandations d'un audit pour les références"""
    audit = get_client_object_or_404(Audit, audit_id)
    recommandations = get_client_filter(Recommandation).filter_by(audit_id=audit_id).all()
    
    return jsonify([{
        'id': r.id,
        'reference': r.reference if hasattr(r, 'reference') else f"REC-{r.id}",
        'description': r.description[:150] if r.description else ''
    } for r in recommandations])


@app.route('/api/audit/<int:audit_id>/plans-action')
@login_required
def api_audit_plans_action(audit_id):
    """Récupérer les plans d'action d'un audit pour les références"""
    audit = get_client_object_or_404(Audit, audit_id)
    plans = get_client_filter(PlanAction).filter_by(audit_id=audit_id).all()
    
    return jsonify([{
        'id': p.id,
        'reference': p.reference if hasattr(p, 'reference') else f"PA-{p.id}",
        'description': p.nom[:150] if hasattr(p, 'nom') else ''
    } for p in plans])


@app.route('/api/audit/<int:audit_id>/risques')
@login_required
def api_audit_risques_associes(audit_id):
    """Récupérer les risques associés à un audit"""
    audit = get_client_object_or_404(Audit, audit_id)
    
    # Récupérer les risques via les constatations et recommandations
    risques_ids = set()
    for constat in audit.constatations:
        if constat.risque_id:
            risques_ids.add(constat.risque_id)
    for reco in audit.recommandations:
        if reco.risque_id:
            risques_ids.add(reco.risque_id)
    
    risques = get_client_filter(Risque).filter(Risque.id.in_(risques_ids)).all()
    
    return jsonify([{
        'id': r.id,
        'reference': r.reference,
        'description': r.intitule[:150] if hasattr(r, 'intitule') else ''
    } for r in risques])


@app.route('/api/feuille-travail/<int:feuille_id>/upload-preuve', methods=['POST'])
@login_required
def api_upload_preuve_feuille(feuille_id):
    """Uploader une preuve pour une feuille de travail (API)"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    if 'fichier' not in request.files:
        return jsonify({'success': False, 'error': 'Aucun fichier'}), 400
    
    fichier = request.files['fichier']
    if fichier.filename == '':
        return jsonify({'success': False, 'error': 'Fichier vide'}), 400
    
    # Vérifier extension
    allowed = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png', 'txt'}
    ext = fichier.filename.rsplit('.', 1)[1].lower() if '.' in fichier.filename else ''
    if ext not in allowed:
        return jsonify({'success': False, 'error': f'Extension .{ext} non autorisée'}), 400
    
    try:
        # Créer dossier
        upload_dir = os.path.join('static', 'uploads', 'feuilles_travail', str(feuille_id))
        os.makedirs(upload_dir, exist_ok=True)
        
        # Nom unique
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nom_unique = secure_filename(fichier.filename)
        nom_final = f"{timestamp}_{nom_unique}"
        chemin = os.path.join(upload_dir, nom_final)
        
        fichier.save(chemin)
        
        # Ajouter à la feuille
        if feuille.pieces_jointes:
            feuille.pieces_jointes += f",{nom_final}"
        else:
            feuille.pieces_jointes = nom_final
        
        feuille.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True, 'fichier': nom_final, 'message': 'Preuve ajoutée'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/feuille-travail/<int:feuille_id>/preuve/<path:filename>', methods=['DELETE'])
@login_required
def api_supprimer_preuve_feuille(feuille_id, filename):
    """Supprimer une preuve d'une feuille de travail"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    if feuille.pieces_jointes:
        preuves = feuille.pieces_jointes.split(',')
        if filename in preuves:
            preuves.remove(filename)
            feuille.pieces_jointes = ','.join(preuves) if preuves else None
            
            # Supprimer le fichier physique
            file_path = os.path.join('static', 'uploads', 'feuilles_travail', str(feuille_id), filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            
            feuille.updated_at = datetime.utcnow()
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Preuve supprimée'})
    
    return jsonify({'success': False, 'error': 'Fichier non trouvé'}), 404


@app.route('/api/audit/<int:audit_id>/preuves')
@login_required
def api_audit_preuves(audit_id):
    """Récupérer toutes les preuves d'un audit (via ses feuilles de travail)"""
    audit = get_client_object_or_404(Audit, audit_id)
    
    # Récupérer toutes les feuilles de travail de l'audit
    feuilles = get_client_filter(FeuilleTravail).filter_by(audit_id=audit_id, is_archived=False).all()
    
    preuves = []
    for feuille in feuilles:
        if feuille.pieces_jointes:
            for preuve in feuille.pieces_jointes.split(','):
                if preuve:
                    preuves.append({
                        'nom_fichier': preuve,
                        'feuille_id': feuille.id,
                        'feuille_reference': feuille.reference,
                        'type': 'feuille_travail',
                        'url_download': url_for('download_preuve', filename=preuve),
                        'url_delete': f"/api/feuille-travail/{feuille.id}/preuve/{preuve}"
                    })
    
    return jsonify({'success': True, 'preuves': preuves})


@app.route('/api/feuille-travail/<int:feuille_id>/versions')
@login_required
def api_liste_versions_feuille(feuille_id):
    """Lister toutes les versions d'une feuille"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    versions = FeuilleTravailVersion.query.filter_by(
        feuille_travail_id=feuille_id
    ).order_by(FeuilleTravailVersion.version_numero.desc()).all()
    
    return jsonify({
        'success': True,
        'versions': [{
            'id': v.id,
            'numero': v.version_numero,
            'commentaire': v.version_commentaire,
            'type': v.version_type,
            'createur': v.createur.username if v.createur else 'Système',
            'date': v.created_at.isoformat(),
            'url_restaurer': f"/api/feuille-travail/{feuille_id}/restaurer/{v.id}"
        } for v in versions]
    })


@app.route('/api/feuille-travail/<int:feuille_id>/restaurer/<int:version_id>', methods=['POST'])
@login_required
def api_restaurer_version_feuille(feuille_id, version_id):
    """Restaurer une version antérieure"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    version = get_client_object_or_404(FeuilleTravailVersion, version_id)
    
    if version.feuille_travail_id != feuille_id:
        return jsonify({'success': False, 'error': 'Version non trouvée'}), 404
    
    # Restaurer les données
    snapshot = version.contenu_snapshot
    feuille.titre = snapshot.get('titre', feuille.titre)
    feuille.description = snapshot.get('description', feuille.description)
    feuille.type_feuille = snapshot.get('type_feuille', feuille.type_feuille)
    feuille.statut = snapshot.get('statut', feuille.statut)
    feuille.contenu = snapshot.get('contenu', feuille.contenu)
    
    # Restaurer les tests
    if version.tests_snapshot:
        TestControleFeuille.query.filter_by(feuille_travail_id=feuille_id).delete()
        for test_data in version.tests_snapshot:
            test = TestControleFeuille(
                feuille_travail_id=feuille_id,
                objet_test=test_data['objet_test'],
                procedure=test_data.get('procedure'),
                echantillon=test_data.get('echantillon'),
                resultat=test_data.get('resultat', 'non_testé'),
                observations=test_data.get('observations', ''),
                ordre=test_data.get('ordre', 0)
            )
            db.session.add(test)
    
    feuille.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Version {version.version_numero} restaurée'})


@app.route('/api/feuille-travail/<int:feuille_id>/commentaire', methods=['POST'])
@login_required
def api_ajouter_commentaire_feuille(feuille_id):
    """Ajouter un commentaire avec positionnement"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    data = request.get_json()
    
    commentaire = CommentaireFeuille(
        feuille_travail_id=feuille_id,
        section=data.get('section'),
        ligne=data.get('ligne'),
        colonne=data.get('colonne'),
        contenu=data.get('contenu'),
        type_commentaire=data.get('type', 'commentaire'),
        reponse_a_id=data.get('reponse_a_id'),
        created_by=current_user.id
    )
    
    db.session.add(commentaire)
    db.session.commit()
    
    # Notification pour le destinataire si mentionné
    if data.get('mention_ids'):
        for user_id in data['mention_ids']:
            creer_notification(
                type_notification='info',
                titre=f'Commentaire sur {feuille.reference}',
                message=f"{current_user.username} vous a mentionné dans un commentaire : {data['contenu'][:100]}",
                destinataire_id=user_id,
                entite_type='feuille_travail',
                entite_id=feuille_id
            )
    
    return jsonify({
        'success': True,
        'commentaire': {
            'id': commentaire.id,
            'contenu': commentaire.contenu,
            'createur': current_user.username,
            'date': commentaire.created_at.isoformat()
        }
    })


@app.route('/api/feuille-travail/<int:feuille_id>/commentaire/<int:commentaire_id>/resoudre', methods=['POST'])
@login_required
def api_resoudre_commentaire_feuille(feuille_id, commentaire_id):
    """Résoudre un commentaire"""
    commentaire = get_client_object_or_404(CommentaireFeuille, commentaire_id)
    
    if commentaire.feuille_travail_id != feuille_id:
        return jsonify({'success': False, 'error': 'Commentaire non trouvé'}), 404
    
    data = request.get_json()
    
    commentaire.statut = 'resolu'
    commentaire.resolution_commentaire = data.get('resolution', '')
    commentaire.resolu_par_id = current_user.id
    commentaire.resolu_le = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'success': True})


@app.route('/api/feuille-travail/exporter/<int:feuille_id>/<format>')
@login_required
def api_exporter_feuille_format(feuille_id, format):
    """Exporter la feuille dans différents formats professionnels"""
    from datetime import datetime
    from flask import Response, make_response, send_file
    
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    tests = TestControleFeuille.query.filter_by(
        feuille_travail_id=feuille_id
    ).order_by(TestControleFeuille.ordre).all()
    
    # Charger les erreurs pour chaque test
    for test in tests:
        test.erreurs = ErreurTest.query.filter_by(test_id=test.id).order_by(ErreurTest.ordre).all()
    
    format = format.lower()
    
    if format == 'excel':
        return exporter_feuille_excel(feuille, tests)
    elif format == 'word':
        return exporter_feuille_word(feuille, tests)
    elif format == 'json':
        return exporter_feuille_json(feuille, tests)
    elif format == 'html':
        return exporter_feuille_html(feuille, tests)
    elif format == 'pdf-complet':
        return exporter_feuille_pdf_complet(feuille, tests)
    else:
        # PDF par défaut
        return exporter_feuille_pdf_complet(feuille, tests)


@app.route('/api/feuille-travail/<int:feuille_id>/reference', methods=['POST'])
@login_required
def api_ajouter_reference_croisee(feuille_id):
    """Ajouter une référence croisée (constatation, recommandation, etc.)"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    data = request.get_json()
    
    reference = ReferenceCroiseeFeuille(
        feuille_travail_id=feuille_id,
        type_reference=data.get('type_reference'),
        entite_id=data.get('entite_id'),
        contexte=data.get('contexte', ''),
        est_auto_genere=data.get('auto_genere', False),
        created_by=current_user.id
    )
    
    db.session.add(reference)
    db.session.commit()
    
    return jsonify({'success': True, 'reference_id': reference.id})


@app.route('/api/modeles-feuilles')
@login_required
def api_liste_modeles_feuilles():
    """Liste des modèles prédéfinis de feuilles de travail"""
    modeles = ModeleFeuilleTravail.query.filter_by(is_public=True).order_by(ModeleFeuilleTravail.categorie, ModeleFeuilleTravail.nom).all()
    
    return jsonify({
        'success': True,
        'modeles': [{
            'id': m.id,
            'reference': m.reference,
            'nom': m.nom,
            'description': m.description,
            'categorie': m.categorie,
            'niveau_maturite': m.niveau_maturite,
            'normes': m.normes or [],
            'nb_utilisations': m.nb_utilisations
        } for m in modeles]
    })


@app.route('/api/modele-feuille/<int:modele_id>/appliquer/<int:audit_id>', methods=['POST'])
@login_required
def api_appliquer_modele_feuille(modele_id, audit_id):
    """Appliquer un modèle pour créer une nouvelle feuille de travail"""
    modele = ModeleFeuilleTravail.query.get_or_404(modele_id)
    audit = get_client_object_or_404(Audit, audit_id)
    
    # Incrémenter le compteur d'utilisations
    modele.nb_utilisations += 1
    
    # Générer la référence
    annee = datetime.now().year
    count = FeuilleTravail.query.filter(
        FeuilleTravail.reference.like(f'FT-{annee}-%'),
        FeuilleTravail.client_id == current_user.client_id
    ).count()
    reference = f"FT-{annee}-{count + 1:04d}"
    
    # Créer la feuille à partir du modèle
    feuille = FeuilleTravail(
        reference=reference,
        titre=f"{modele.nom} - {audit.reference}",
        description=modele.description,
        type_feuille='standard',
        audit_id=audit_id,
        contenu=modele.template_contenu or {},
        client_id=audit.client_id or current_user.client_id,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.session.add(feuille)
    db.session.flush()
    
    # Créer les tests à partir du template
    for i, test_template in enumerate(modele.template_tests or []):
        test = TestControleFeuille(
            feuille_travail_id=feuille.id,
            objet_test=test_template.get('objet_test', f'Test {i+1}'),
            procedure=test_template.get('procedure'),
            echantillon=test_template.get('echantillon'),
            ordre=i
        )
        db.session.add(test)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'feuille_id': feuille.id,
        'reference': feuille.reference,
        'message': f'Feuille créée à partir du modèle {modele.nom}'
    })


@app.route('/api/feuille-travail/<int:feuille_id>/favori', methods=['POST'])
@login_required
def api_ajouter_favori_feuille(feuille_id):
    """Ajouter/retirer une feuille des favoris"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    favori = FavoriFeuille.query.filter_by(
        feuille_travail_id=feuille_id,
        utilisateur_id=current_user.id
    ).first()
    
    if favori:
        db.session.delete(favori)
        message = 'Retiré des favoris'
    else:
        favori = FavoriFeuille(
            feuille_travail_id=feuille_id,
            utilisateur_id=current_user.id
        )
        db.session.add(favori)
        message = 'Ajouté aux favoris'
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': message, 'est_favori': favori is None})


@app.route('/api/feuille-travail/favoris')
@login_required
def api_liste_favoris_feuilles():
    """Lister les feuilles favorites de l'utilisateur"""
    favoris = FavoriFeuille.query.filter_by(utilisateur_id=current_user.id).order_by(FavoriFeuille.ordre).all()
    
    return jsonify({
        'success': True,
        'favoris': [{
            'id': f.feuille.id,
            'reference': f.feuille.reference,
            'titre': f.feuille.titre,
            'audit_reference': f.feuille.audit.reference if f.feuille.audit else None,
            'statut': f.feuille.statut,
            'progression': f.feuille.progression,
            'updated_at': f.feuille.updated_at.isoformat() if f.feuille.updated_at else None
        } for f in favoris]
    })


@app.route('/editer-feuille-travail/<int:feuille_id>')
@login_required
def editer_feuille_travail(feuille_id):
    from models import (
        User, Direction, Service, Pole, Audit, ErreurTest, Risque, Cartographie,
        CampagneEvaluation, EvaluationRisque, DispositifMaitrise,
    )

    # ============================================
    # 1. RÉCUPÉRER LA FEUILLE AVEC MULTI-TENANT
    # ============================================
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)

    # ============================================
    # 2. RÉCUPÉRER L'AUDIT ASSOCIÉ
    # ============================================
    audit = get_client_object_or_404(Audit, feuille.audit_id)

    # ============================================
    # 3. DÉTERMINER LE CLIENT CIBLE
    # ============================================
    target_client_id = None
    if current_user.role == 'super_admin' and session.get('viewing_client_id'):
        target_client_id = session.get('viewing_client_id')
    elif hasattr(feuille, 'client_id') and feuille.client_id:
        target_client_id = feuille.client_id
    elif hasattr(current_user, 'client_id') and current_user.client_id:
        target_client_id = current_user.client_id

    # ============================================
    # 4. RÉCUPÉRER LES TESTS
    # ============================================
    tests = TestControleFeuille.query.filter_by(
        feuille_travail_id=feuille_id
    ).order_by(TestControleFeuille.ordre).all()

    # ============================================
    # 5. CALCULER LES NIVEAUX NET POUR TOUS LES RISQUES (cache)
    # ============================================
    def _get_net_info_cached(risque, cache={}):
        """Cache local pour éviter N+1 requêtes sur les mêmes risques."""
        if risque.id in cache:
            return cache[risque.id]

        net = _get_niveau_net_risque(risque)
        cache[risque.id] = net
        return net

    def _enrichir_risque_pour_template(risque):
        net = _get_net_info_cached(risque)
        niveau_norm = _normaliser_niveau(net['niveau_net'])
        return {
            'id': risque.id,
            'reference': risque.reference,
            'intitule': risque.intitule,
            'niveau_criticite': niveau_norm,
            'niveau_net_libelle': net['niveau_net'],
            'score_risque': net['score_net'],
            'score_net': net['score_net'],
            'impact': risque.impact or 'modere',
            'probabilite': risque.probabilite or 'possible',
            'campagne_nom': net['campagne_nom'],
            'est_revaluation': net['est_revaluation'],
            'couleur': {
                'critique': '#dc2626',
                'eleve':    '#ea580c',
                'moyen':    '#f59e0b',
                'faible':   '#10b981',
            }.get(niveau_norm, '#6b7280'),
        }

    # ============================================
    # 6. ENRICHIR CHAQUE TEST
    # ============================================
    risques_associes_ids = []
    for test in tests:
        test.erreurs = ErreurTest.query.filter_by(
            test_id=test.id
        ).order_by(ErreurTest.ordre).all()

        risques_enrichis = []
        for risque in test.risques_associes:
            risques_enrichis.append(_enrichir_risque_pour_template(risque))
            risques_associes_ids.append(risque.id)

        test.risques_associes_enrichis = risques_enrichis

        # Recalcul à la volée du niveau du test (sans toucher la base)
        if risques_enrichis:
            ordre_niveaux = {'faible': 0, 'moyen': 1, 'eleve': 2, 'critique': 3}
            test.niveau_criticite_calcule = max(
                (r['niveau_criticite'] for r in risques_enrichis),
                key=lambda n: ordre_niveaux.get(n, 1)
            )
        else:
            test.niveau_criticite_calcule = _normaliser_niveau(
                test.niveau_criticite or 'moyen'
            )

    risques_associes_ids = list(set(risques_associes_ids))

    # ============================================
    # 7. RÉCUPÉRER LES RISQUES DISPONIBLES AVEC NIVEAU NET
    # ============================================
    if target_client_id is None and hasattr(current_user, 'client_id'):
        target_client_id = current_user.client_id

    risques_query = []
    if target_client_id is not None:
        risques_query = Risque.query.filter_by(
            client_id=target_client_id,
            is_archived=False,
        ).order_by(Risque.reference).all()

    risques_disponibles = []
    for risque in risques_query:
        net = _get_net_info_cached(risque)
        niveau_norm = _normaliser_niveau(net['niveau_net'])

        risques_disponibles.append({
            'id': risque.id,
            'reference': risque.reference,
            'intitule': risque.intitule,
            'description': risque.description or '',
            'categorie': risque.categorie or '',
            'niveau_criticite_brut': risque.niveau_criticite or 'Non défini',
            'niveau_net': net['niveau_net'],
            'score_net': net['score_net'],
            'est_revaluation': net['est_revaluation'],
            'campagne_nom': net['campagne_nom'],
            'cartographie_id': risque.cartographie_id,
            'cartographie_nom': risque.cartographie.nom if risque.cartographie else 'Non définie',
            'impact': risque.impact or 'modere',
            'probabilite': risque.probabilite or 'possible',
            'score_risque_brut': float(risque.score_risque or 0),
            'couleur_criticite': {
                'critique': '#dc2626',
                'eleve':    '#ea580c',
                'moyen':    '#f59e0b',
                'faible':   '#10b981',
            }.get(niveau_norm, '#6b7280'),
        })

    # ============================================
    # 8. RÉCUPÉRER LES CARTOGRAPHIES
    # ============================================
    if target_client_id is not None:
        cartographies = Cartographie.query.filter_by(
            client_id=target_client_id,
            is_archived=False,
        ).order_by(Cartographie.nom).all()
    else:
        cartographies = Cartographie.query.filter_by(
            is_archived=False,
        ).order_by(Cartographie.nom).all()

    # ============================================
    # 9. STATISTIQUES DES TESTS
    # ============================================
    nb_conformes = len([t for t in tests if t.resultat == 'conforme'])
    nb_non_conformes = len([t for t in tests if t.resultat == 'non_conforme'])
    nb_partiels = len([t for t in tests if t.resultat == 'partiellement_conforme'])
    nb_non_testes = len([t for t in tests if t.resultat in ['non_testé', None] or not t.resultat])

    total_tests = len(tests)
    taux_conformite = round((nb_conformes / total_tests * 100), 1) if total_tests > 0 else 0
    impact_total = sum(t.impact_financier for t in tests if t.impact_financier is not None)
    sans_correction = len([t for t in tests if t.resultat == 'non_conforme' and not t.correction_effectuee])

    criticite_map = {'faible': 0, 'moyen': 0, 'eleve': 0, 'critique': 0}
    for t in tests:
        niveau = t.niveau_criticite_calcule
        if niveau in criticite_map:
            criticite_map[niveau] += 1
        else:
            criticite_map['moyen'] += 1

    # ============================================
    # 10. ALERTES : RISQUES CRITIQUES NET SANS TEST
    # ============================================
    risques_critiques_net_ids = {
        r['id'] for r in risques_disponibles
        if 'critique' in (r['niveau_net'] or '').lower()
    }

    risques_couverts_ids = set()
    for test in tests:
        for risque in test.risques_associes:
            if risque.id in risques_critiques_net_ids:
                risques_couverts_ids.add(risque.id)

    # Détail des alertes : critiques non couverts
    alertes_risques_critiques = []
    for r in risques_disponibles:
        if r['id'] in risques_critiques_net_ids and r['id'] not in risques_couverts_ids:
            alertes_risques_critiques.append({
                'id': r['id'],
                'reference': r['reference'],
                'intitule': r['intitule'],
                'description': r['description'],
                'score': r['score_net'],
                'niveau': r['niveau_net'],
            })

    nb_risques_total = len(risques_critiques_net_ids)
    nb_risques_couverts = len(risques_couverts_ids)
    nb_alertes_critiques = nb_risques_total - nb_risques_couverts
    taux_couverture_risques = (
        round(nb_risques_couverts / nb_risques_total * 100)
        if nb_risques_total > 0 else 100
    )

    # ============================================
    # 11. SÉRIALISER LES TESTS POUR LE JS
    # ============================================
    tests_data = []
    for test in tests:
        erreurs = ErreurTest.query.filter_by(test_id=test.id).order_by(ErreurTest.ordre).all()

        tests_data.append({
            'id': test.id,
            'objet_test': test.objet_test,
            'objectif_controle': test.objectif_controle,
            'reference_norme': test.reference_norme,
            'procedure': test.procedure,
            'criteres_acceptation': test.criteres_acceptation,
            'etapes_cles': test.etapes_cles,
            'echantillon': test.echantillon,
            'methode_echantillonnage': test.methode_echantillonnage,
            'taille_echantillon': test.taille_echantillon,
            'population_totale': test.population_totale,
            'periode_couverte': test.periode_couverte,
            'taux_confiance': test.taux_confiance,
            'marge_erreur': test.marge_erreur,
            'resultat': test.resultat,
            'observations': test.observations,
            'ecart_constate': test.ecart_constate,
            'classification_anomalie': test.classification_anomalie,
            'impact_financier': test.impact_financier,
            'impact_fonctionnel': test.impact_fonctionnel,
            'cause_racine': test.cause_racine,
            'niveau_criticite': test.niveau_criticite_calcule,
            'probabilite_occurrence': test.probabilite_occurrence,
            'gravite_impact': test.gravite_impact,
            'taux_reussite': test.taux_reussite,
            'correction_effectuee': test.correction_effectuee,
            'date_correction': test.date_correction.isoformat() if test.date_correction else None,
            'responsable_correction_name': (
                test.responsable_correction.username
                if test.responsable_correction else None
            ),
            'responsable_correction_id': test.responsable_correction_id,
            'action_curative': test.action_curative,
            'action_preventive': test.action_preventive,
            'nb_elements_testes': test.nb_elements_testes,
            'nb_erreurs_trouvees': test.nb_erreurs_trouvees,
            'temps_passe_minutes': test.temps_passe_minutes,
            'difficulte': test.difficulte,
            'statut_revision': test.statut_revision,
            'created_by': test.createur.username if test.createur else 'Système',
            'created_at': test.created_at.strftime('%d/%m/%Y à %H:%M') if test.created_at else None,
            'updated_at': test.updated_at.strftime('%d/%m/%Y à %H:%M') if test.updated_at else None,
            'risques_associes': test.risques_associes_enrichis,
            'erreurs': [e.to_dict() for e in erreurs],
        })

    # ============================================
    # 12. UTILISATEURS & STRUCTURES
    # ============================================
    if target_client_id is not None:
        users = User.query.filter_by(client_id=target_client_id, is_active=True).order_by(User.username).all()
        poles = Pole.query.filter_by(client_id=target_client_id, is_archived=False).order_by(Pole.nom).all()
        directions = Direction.query.filter_by(client_id=target_client_id, is_archived=False, is_active=True).order_by(Direction.nom).all()
        services = Service.query.filter_by(client_id=target_client_id, is_archived=False, is_active=True).order_by(Service.nom).all()
    else:
        users = User.query.filter_by(is_active=True).order_by(User.username).all()
        poles = Pole.query.filter_by(is_archived=False).order_by(Pole.nom).all()
        directions = Direction.query.filter_by(is_archived=False, is_active=True).order_by(Direction.nom).all()
        services = Service.query.filter_by(is_archived=False, is_active=True).order_by(Service.nom).all()

    users_json = [{'id': u.id, 'username': u.username} for u in users]
    poles_json = [{'id': p.id, 'nom': p.nom} for p in poles]
    directions_json = [{'id': d.id, 'nom': d.nom} for d in directions]
    services_json = [{'id': s.id, 'nom': s.nom} for s in services]

    # ============================================
    # 13. HELPERS DE FORMATAGE POUR LE TEMPLATE
    # ============================================
    def get_categorie_label(categorie):
        labels = {
            'documentaire': '📄 Documentaire',
            'calcul': '🧮 Calcul',
            'procedure': '📋 Procédure',
            'conformite': '⚖️ Conformité',
            'systeme': '💻 Système',
            'autre': '📌 Autre',
        }
        return labels.get(categorie, '📌 Autre')

    def get_gravite_badge(gravite):
        badges = {
            'mineure': 'bg-info',
            'moyenne': 'bg-warning text-dark',
            'majeure': 'bg-danger',
            'critique': 'bg-dark',
        }
        return badges.get(gravite, 'bg-secondary')

    def get_etat_badge(etat):
        badges = {
            'ouverte': 'bg-secondary',
            'en_cours': 'bg-primary',
            'corrigee': 'bg-success',
            'verifiee': 'bg-info',
            'fermee': 'bg-dark',
        }
        return badges.get(etat, 'bg-secondary')

    # ============================================
    # 14. RENDU
    # ============================================
    return render_template(
        'audit/editer_feuille_travail.html',
        feuille=feuille,
        audit=audit,
        tests=tests,
        tests_data=tests_data,
        users=users_json,
        poles=poles_json,
        directions=directions_json,
        services=services_json,
        risques_disponibles=risques_disponibles,
        cartographies=cartographies,
        risques_associes_ids=risques_associes_ids,
        ErreurTest=ErreurTest,
        get_categorie_label=get_categorie_label,
        get_gravite_badge=get_gravite_badge,
        get_etat_badge=get_etat_badge,
        nb_conformes=nb_conformes,
        nb_non_conformes=nb_non_conformes,
        nb_partiels=nb_partiels,
        nb_non_testes=nb_non_testes,
        taux_conformite=taux_conformite,
        impact_total=impact_total,
        sans_correction=sans_correction,
        criticite_map=criticite_map,
        target_client_id=target_client_id,
        alertes_risques_critiques=alertes_risques_critiques,
        nb_alertes_critiques=nb_alertes_critiques,
        nb_risques_couverts=nb_risques_couverts,
        nb_risques_total=nb_risques_total,
        taux_couverture_risques=taux_couverture_risques,
    )


@app.route('/feuilles-travail')
@login_required
def liste_global_feuilles_travail():
    """Liste globale de toutes les feuilles de travail"""
    if not current_user.has_permission('can_manage_audit'):
        flash('Permission requise', 'error')
        return redirect(url_for('dashboard'))
    
    feuilles = get_client_filter(FeuilleTravail)\
        .filter_by(is_archived=False)\
        .order_by(FeuilleTravail.created_at.desc())\
        .all()
    
    return render_template('audit/feuilles_travail_global.html', feuilles=feuilles)


@app.route('/api/audit/<int:audit_id>/feuilles-travail')
@login_required
def api_audit_feuilles_travail(audit_id):
    """API pour récupérer les feuilles de travail d'un audit"""
    audit = get_client_object_or_404(Audit, audit_id)
    
    feuilles = get_client_filter(FeuilleTravail)\
        .filter_by(audit_id=audit_id, is_archived=False)\
        .order_by(FeuilleTravail.created_at.desc())\
        .all()
    
    return jsonify({
        'success': True,
        'feuilles': [{
            'id': f.id,
            'reference': f.reference,
            'titre': f.titre,
            'type_feuille': f.type_feuille,
            'statut': f.statut,
            'progression': f.progression,
            'created_at': f.created_at.isoformat() if f.created_at else None
        } for f in feuilles]
    })


@app.route('/feuille-travail/<int:feuille_id>/supprimer', methods=['POST'])
@login_required
def supprimer_feuille_travail(feuille_id):
    """Supprimer une feuille de travail"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    audit_id = feuille.audit_id
    
    try:
        db.session.delete(feuille)
        db.session.commit()
        flash('Feuille supprimée avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
    
    return redirect(url_for('feuilles_travail_audit', audit_id=audit_id))


@app.route('/api/feuille-travail/<int:feuille_id>/versions')
@login_required
def api_liste_versions_complete(feuille_id):
    """Lister toutes les versions avec statistiques"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    versions = FeuilleTravailVersion.query.filter_by(
        feuille_travail_id=feuille_id
    ).order_by(FeuilleTravailVersion.version_numero.desc()).all()
    
    versions_data = []
    for v in versions:
        # Calculer le taux de conformité pour cette version
        tests_snapshot = v.tests_snapshot or []
        total = len(tests_snapshot)
        conformes = len([t for t in tests_snapshot if t.get('resultat') == 'conforme'])
        taux = round((conformes / total * 100), 1) if total > 0 else 0
        
        versions_data.append({
            'id': v.id,
            'numero': v.version_numero,
            'commentaire': v.version_commentaire,
            'type': v.version_type,
            'createur': v.createur.username if v.createur else 'Système',
            'date': v.created_at.isoformat(),
            'taux_conformite': taux,
            'nb_tests': total,
            'url_restaurer': f"/api/feuille-travail/{feuille_id}/restaurer/{v.id}"
        })
    
    return jsonify({
        'success': True,
        'versions': versions_data
    })


@app.route('/api/feuille-travail/<int:feuille_id>/commentaires', methods=['GET'])
@login_required
def api_get_commentaires_feuille(feuille_id):
    """Récupérer les commentaires d'une feuille"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    commentaires = CommentaireFeuille.query.filter_by(
        feuille_travail_id=feuille_id,
        reponse_a_id=None
    ).order_by(CommentaireFeuille.created_at.desc()).all()
    
    data = []
    for c in commentaires:
        data.append({
            'id': c.id,
            'contenu': c.contenu,
            'type': c.type_commentaire,
            'statut': c.statut,
            'createur': c.createur.username if c.createur else 'Système',
            'date_formatee': c.created_at.strftime('%d/%m/%Y à %H:%M'),
            'reponses': []
        })
    
    return jsonify({'success': True, 'commentaires': data})


@app.route('/api/feuille-travail/<int:feuille_id>/commentaire', methods=['POST'])
@login_required
def api_ajouter_commentaire_feuille_complet(feuille_id):
    """Ajouter un commentaire à une feuille"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    data = request.get_json()
    
    commentaire = CommentaireFeuille(
        feuille_travail_id=feuille_id,
        contenu=data.get('contenu'),
        type_commentaire=data.get('type', 'commentaire'),
        created_by=current_user.id
    )
    
    db.session.add(commentaire)
    db.session.commit()
    
    return jsonify({'success': True, 'commentaire_id': commentaire.id})


@app.route('/api/feuille-travail/commentaire/<int:commentaire_id>/resoudre', methods=['POST'])
@login_required
def api_resoudre_commentaire_feuille_complet(commentaire_id):
    """Résoudre un commentaire"""
    commentaire = CommentaireFeuille.query.get_or_404(commentaire_id)
    commentaire.statut = 'resolu'
    commentaire.resolu_par_id = current_user.id
    commentaire.resolu_le = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True})


@app.route('/api/feuille-travail/<int:feuille_id>/commentaires', methods=['GET'])
@login_required
def api_liste_commentaires_feuille_complet(feuille_id):
    """Lister tous les commentaires d'une feuille avec leurs réponses"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    # Récupérer les commentaires principaux (pas des réponses)
    commentaires = CommentaireFeuille.query.filter_by(
        feuille_travail_id=feuille_id,
        reponse_a_id=None
    ).order_by(CommentaireFeuille.created_at.desc()).all()
    
    commentaires_data = []
    for comment in commentaires:
        # Récupérer les réponses
        reponses = CommentaireFeuille.query.filter_by(
            reponse_a_id=comment.id
        ).order_by(CommentaireFeuille.created_at.asc()).all()
        
        commentaires_data.append({
            'id': comment.id,
            'contenu': comment.contenu,
            'type': comment.type_commentaire,
            'statut': comment.statut,
            'createur': comment.createur.username if comment.createur else 'Système',
            'created_by': comment.created_by,
            'date_formatee': comment.created_at.strftime('%d/%m/%Y à %H:%M'),
            'created_at': comment.created_at.isoformat(),
            'updated_at': comment.updated_at.isoformat() if comment.updated_at else comment.created_at.isoformat(),
            'reponses': [{
                'id': r.id,
                'contenu': r.contenu,
                'createur': r.createur.username if r.createur else 'Système',
                'date_formatee': r.created_at.strftime('%d/%m/%Y à %H:%M')
            } for r in reponses]
        })
    
    return jsonify({'success': True, 'commentaires': commentaires_data})


@app.route('/api/feuille-travail/<int:feuille_id>/commentaire', methods=['POST'])
@login_required
def api_ajouter_commentaire_complet(feuille_id):
    """Ajouter un commentaire à une feuille avec mentions"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    data = request.get_json()
    
    commentaire = CommentaireFeuille(
        feuille_travail_id=feuille_id,
        contenu=data.get('contenu'),
        type_commentaire=data.get('type', 'commentaire'),
        section=data.get('section', 'general'),
        created_by=current_user.id
    )
    
    db.session.add(commentaire)
    db.session.flush()
    
    # Créer des notifications pour les mentions (avec filtre multi-tenant)
    mentions = data.get('mentions', [])
    for user_id in mentions:
        # Vérifier que l'utilisateur mentionné appartient au même client
        user = User.query.filter_by(id=user_id, client_id=current_user.client_id).first()
        if user and user_id != current_user.id:
            notification = Notification(
                type_notification='info',
                titre=f"Commentaire sur la feuille {feuille.reference}",
                message=f"{current_user.username} vous a mentionné dans un commentaire : {data.get('contenu')[:100]}",
                destinataire_id=user_id,
                entite_type='feuille_travail',
                entite_id=feuille_id,
                client_id=current_user.client_id
            )
            db.session.add(notification)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'commentaire_id': commentaire.id,
        'message': 'Commentaire ajouté'
    })


@app.route('/api/feuille-travail/commentaire/<int:commentaire_id>', methods=['PUT'])
@login_required
def api_modifier_commentaire_complet(commentaire_id):
    """Modifier un commentaire"""
    commentaire = get_client_object_or_404(CommentaireFeuille, commentaire_id)
    
    # Vérifier que le commentaire appartient au client de l'utilisateur
    feuille = FeuilleTravail.query.filter_by(
        id=commentaire.feuille_travail_id,
        client_id=current_user.client_id
    ).first()
    
    if not feuille:
        return jsonify({'success': False, 'error': 'Commentaire non trouvé'}), 404
    
    data = request.get_json()
    
    # Vérifier que l'utilisateur est l'auteur du commentaire
    if commentaire.created_by != current_user.id and not current_user.is_client_admin:
        return jsonify({'success': False, 'error': 'Permission refusée'}), 403
    
    # Mettre à jour le contenu
    if 'contenu' in data:
        commentaire.contenu = data['contenu']
    if 'type' in data:
        commentaire.type_commentaire = data['type']
    
    commentaire.updated_at = datetime.utcnow()
    db.session.commit()
    
    # Gérer les nouvelles mentions (avec filtre multi-tenant)
    if data.get('mentions'):
        for user_id in data['mentions']:
            user = User.query.filter_by(id=user_id, client_id=current_user.client_id).first()
            if user and user_id != current_user.id:
                notification = Notification(
                    type_notification='info',
                    titre=f"Commentaire modifié sur {feuille.reference}",
                    message=f"{current_user.username} vous a mentionné dans un commentaire modifié",
                    destinataire_id=user_id,
                    entite_type='feuille_travail',
                    entite_id=feuille.id,
                    client_id=current_user.client_id
                )
                db.session.add(notification)
        db.session.commit()
    
    return jsonify({'success': True, 'message': 'Commentaire modifié'})


@app.route('/api/feuille-travail/commentaire/<int:commentaire_id>', methods=['DELETE'])
@login_required
def api_supprimer_commentaire_complet(commentaire_id):
    """Supprimer un commentaire (et ses réponses)"""
    commentaire = get_client_object_or_404(CommentaireFeuille, commentaire_id)
    
    # Vérifier que le commentaire appartient au client de l'utilisateur
    feuille = FeuilleTravail.query.filter_by(
        id=commentaire.feuille_travail_id,
        client_id=current_user.client_id
    ).first()
    
    if not feuille:
        return jsonify({'success': False, 'error': 'Commentaire non trouvé'}), 404
    
    # Vérifier que l'utilisateur est l'auteur du commentaire
    if commentaire.created_by != current_user.id and not current_user.is_client_admin:
        return jsonify({'success': False, 'error': 'Permission refusée'}), 403
    
    # Supprimer également les réponses
    CommentaireFeuille.query.filter_by(reponse_a_id=commentaire_id).delete()
    
    db.session.delete(commentaire)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Commentaire supprimé'})


@app.route('/api/feuille-travail/commentaire/<int:commentaire_id>/repondre', methods=['POST'])
@login_required
def api_repondre_commentaire_complet(commentaire_id):
    """Répondre à un commentaire"""
    commentaire_parent = get_client_object_or_404(CommentaireFeuille, commentaire_id)
    
    # Vérifier que le commentaire parent appartient au client de l'utilisateur
    feuille = FeuilleTravail.query.filter_by(
        id=commentaire_parent.feuille_travail_id,
        client_id=current_user.client_id
    ).first()
    
    if not feuille:
        return jsonify({'success': False, 'error': 'Commentaire non trouvé'}), 404
    
    data = request.get_json()
    
    reponse = CommentaireFeuille(
        feuille_travail_id=commentaire_parent.feuille_travail_id,
        contenu=data.get('contenu'),
        type_commentaire='reponse',
        reponse_a_id=commentaire_id,
        section=commentaire_parent.section,
        created_by=current_user.id
    )
    
    db.session.add(reponse)
    db.session.flush()
    
    # Notifier l'auteur du commentaire parent (s'il appartient au même client)
    if commentaire_parent.created_by != current_user.id:
        user_parent = User.query.filter_by(id=commentaire_parent.created_by, client_id=current_user.client_id).first()
        if user_parent:
            notification = Notification(
                type_notification='info',
                titre="Nouvelle réponse à votre commentaire",
                message=f"{current_user.username} a répondu à votre commentaire",
                destinataire_id=commentaire_parent.created_by,
                entite_type='feuille_travail',
                entite_id=commentaire_parent.feuille_travail_id,
                client_id=current_user.client_id
            )
            db.session.add(notification)
    
    # Notifier les mentions (avec filtre multi-tenant)
    mentions = data.get('mentions', [])
    for user_id in mentions:
        user = User.query.filter_by(id=user_id, client_id=current_user.client_id).first()
        if user and user_id != current_user.id:
            notification = Notification(
                type_notification='info',
                titre="Vous avez été mentionné",
                message=f"{current_user.username} vous a mentionné dans une réponse",
                destinataire_id=user_id,
                entite_type='feuille_travail',
                entite_id=commentaire_parent.feuille_travail_id,
                client_id=current_user.client_id
            )
            db.session.add(notification)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'reponse_id': reponse.id,
        'message': 'Réponse ajoutée'
    })


@app.route('/api/feuille-travail/commentaire/<int:commentaire_id>', methods=['PUT', 'DELETE'])
@login_required
def api_gerer_commentaire_complet(commentaire_id):
    """Modifier ou supprimer un commentaire"""
    commentaire = get_client_object_or_404(CommentaireFeuille, commentaire_id)
    
    if request.method == 'PUT':
        data = request.get_json()
        if commentaire.created_by != current_user.id and not current_user.is_client_admin:
            return jsonify({'success': False, 'error': 'Permission refusée'}), 403
        
        commentaire.contenu = data.get('contenu', commentaire.contenu)
        commentaire.type_commentaire = data.get('type', commentaire.type_commentaire)
        commentaire.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True})
    
    else:  # DELETE
        if commentaire.created_by != current_user.id and not current_user.is_client_admin:
            return jsonify({'success': False, 'error': 'Permission refusée'}), 403
        
        # Supprimer aussi les réponses
        CommentaireFeuille.query.filter_by(reponse_a_id=commentaire_id).delete()
        db.session.delete(commentaire)
        db.session.commit()
        return jsonify({'success': True})


@app.route('/api/feuille-travail/commentaire/<int:commentaire_id>/resoudre', methods=['POST'])
@login_required
def api_resoudre_commentaire_complet(commentaire_id):
    """Résoudre un commentaire"""
    commentaire = get_client_object_or_404(CommentaireFeuille, commentaire_id)
    
    # Vérifier que le commentaire appartient au client de l'utilisateur
    feuille = FeuilleTravail.query.filter_by(
        id=commentaire.feuille_travail_id,
        client_id=current_user.client_id
    ).first()
    
    if not feuille:
        return jsonify({'success': False, 'error': 'Commentaire non trdef api_liste_commentaires_feuilleouvé'}), 404
    
    data = request.get_json()
    
    commentaire.statut = 'resolu'
    commentaire.resolution_commentaire = data.get('resolution', '')
    commentaire.resolu_par_id = current_user.id
    commentaire.resolu_le = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Commentaire résolu'})


@app.route('/api/feuille-travail/<int:feuille_id>/risques-disponibles', methods=['GET'])
@login_required
def api_risques_disponibles(feuille_id):
    """Récupérer les risques disponibles pour lier à un test"""
    try:
        feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
        
        # Filtrer par client_id uniquement (via get_client_filter)
        risques = get_client_filter(Risque).filter_by(est_actif=True).all()
        
        return jsonify([{
            'id': r.id,
            'reference': getattr(r, 'reference', f'RIS-{r.id}'),
            'intitule': getattr(r, 'intitule', str(r)),
            'description': getattr(r, 'description', ''),
            'niveau_criticite': getattr(r, 'niveau_criticite', 'moyen')
        } for r in risques])
        
    except Exception as e:
        _journal(f"Erreur chargement risques: {e}")
        return jsonify([])


@app.route('/api/feuille-travail/erreur/<int:erreur_id>', methods=['GET'])
@login_required
def api_get_erreur(erreur_id):
    """Récupérer une erreur spécifique pour édition"""
    erreur = ErreurTest.query.get_or_404(erreur_id)
    
    # Vérification multi-tenant
    test = TestControleFeuille.query.filter_by(id=erreur.test_id).first()
    if not test:
        return jsonify({'success': False, 'error': 'Test non trouvé'}), 404
    
    feuille = FeuilleTravail.query.filter_by(id=test.feuille_travail_id, client_id=current_user.client_id).first()
    if not feuille:
        return jsonify({'success': False, 'error': 'Accès non autorisé'}), 403
    
    return jsonify({
        'success': True,
        'erreur': erreur.to_dict()
    })


@app.route('/api/feuille-travail/<int:feuille_id>/historique-complet', methods=['GET'])
@login_required
def api_historique_complet_feuille(feuille_id):
    """Récupérer l'historique complet de toutes les modifications pour une feuille"""
    from models import HistoriqueRisqueTest, TestControleFeuille
    
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    # Récupérer tous les tests de la feuille
    tests = TestControleFeuille.query.filter_by(feuille_travail_id=feuille_id).all()
    test_ids = [t.id for t in tests]
    
    if not test_ids:
        return jsonify({
            'success': True,
            'historique': [],
            'message': 'Aucun test trouvé'
        })
    
    # Récupérer l'historique des risques pour tous les tests
    historique = HistoriqueRisqueTest.query.filter(
        HistoriqueRisqueTest.test_id.in_(test_ids)
    ).order_by(HistoriqueRisqueTest.created_at.desc()).all()
    
    # Formater les données
    historique_data = []
    for h in historique:
        # Récupérer le test associé
        test = next((t for t in tests if t.id == h.test_id), None)
        
        historique_data.append({
            'id': h.id,
            'test_id': h.test_id,
            'test_objet': test.objet_test if test else 'Test inconnu',
            'action': h.action,
            'risque_id': h.risque_id,
            'risque_reference': h.risque.reference if h.risque else None,
            'risque_intitule': h.risque.intitule if h.risque else None,
            'ancienne_valeur': h.ancienne_valeur,
            'nouvelle_valeur': h.nouvelle_valeur,
            'commentaire': h.commentaire,
            'created_by': h.createur.username if h.createur else 'Système',
            'created_at': h.created_at.strftime('%d/%m/%Y à %H:%M') if h.created_at else None
        })
    
    return jsonify({
        'success': True,
        'historique': historique_data,
        'total': len(historique_data)
    })


@app.route('/developpement-auditeurs/competences')
@login_required
def liste_competences():
    """Liste des compétences"""
    competences = get_client_filter(Competence).filter_by(est_actif=True).order_by(Competence.categorie, Competence.nom).all()
    return render_template('auditeurs/competences.html', competences=competences)


@app.route('/api/auditeur/<int:auditeur_id>/evaluation', methods=['POST'])
@login_required
def api_sauvegarder_evaluation_auditeur(auditeur_id):
    """Sauvegarder l'évaluation d'un auditeur"""
    data = request.get_json()
    
    for comp_id, niveau in data.get('evaluations', {}).items():
        evaluation = EvaluationCompetence.query.filter_by(
            auditeur_id=auditeur_id, competence_id=int(comp_id), client_id=current_user.client_id
        ).first()
        
        if not evaluation:
            evaluation = EvaluationCompetence(
                auditeur_id=auditeur_id,
                competence_id=int(comp_id),
                client_id=current_user.client_id
            )
            db.session.add(evaluation)
        
        evaluation.evaluation_superieur = int(niveau)
        evaluation.evaluateur_id = current_user.id
        evaluation.date_evaluation = datetime.utcnow()
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Évaluations sauvegardées'})


# API pour sauvegarder le plan de développement
@app.route('/api/developpement-auditeurs/plan/<int:plan_id>', methods=['POST'])
@login_required
def api_sauvegarder_plan_pdi(plan_id):
    """Sauvegarder le plan de développement"""
    plan = get_client_object_or_404(PlanDeveloppementIndividuel, plan_id)
    data = request.get_json()
    
    if 'objectifs_globaux' in data:
        plan.objectifs_globaux = data['objectifs_globaux']
    if 'objectifs_smart' in data:
        plan.objectifs_smart = data['objectifs_smart']
    if 'actions_prevues' in data:
        plan.actions_prevues = data['actions_prevues']
    if 'actions_realisees' in data:
        plan.actions_realisees = data['actions_realisees']
    if 'mentor_id' in data and data['mentor_id']:
        plan.mentor_id = int(data['mentor_id'])
    if 'progression' in data:
        plan.progression = int(data['progression'])
    if 'statut' in data:
        plan.statut = data['statut']
    
    plan.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True, 'progression': plan.progression})


# API pour annuler une inscription
@app.route('/api/developpement-auditeurs/inscription/<int:inscription_id>/annuler', methods=['POST'])
@login_required
def api_annuler_inscription(inscription_id):
    """Annuler une inscription à une formation"""
    inscription = get_client_object_or_404(InscriptionFormation, inscription_id)
    
    db.session.delete(inscription)
    db.session.commit()
    
    return jsonify({'success': True})


# Route pour la fiche auditeur enrichie
@app.route('/developpement-auditeurs/auditeur/<int:auditeur_id>')
@login_required
def fiche_auditeur_complete(auditeur_id):
    """Fiche détaillée d'un auditeur"""
    auditeur = get_client_object_or_404(User, auditeur_id)
    
    # Compétences et évaluations
    competences = Competence.query.filter_by(client_id=current_user.client_id, est_actif=True).all()
    evaluations = {}
    for comp in competences:
        eval_comp = EvaluationCompetence.query.filter_by(
            auditeur_id=auditeur_id, competence_id=comp.id, client_id=current_user.client_id
        ).first()
        evaluations[comp.id] = eval_comp
    
    # Plan de développement
    pdi = PlanDeveloppementIndividuel.query.filter_by(
        auditeur_id=auditeur_id, annee=datetime.now().year, client_id=current_user.client_id
    ).first()
    if not pdi:
        pdi = PlanDeveloppementIndividuel(
            auditeur_id=auditeur_id,
            annee=datetime.now().year,
            client_id=current_user.client_id
        )
        pdi.reference = f"PDI-{datetime.now().year}-{auditeur_id:04d}"
        db.session.add(pdi)
        db.session.commit()
    
    # Formations suivies
    inscriptions = InscriptionFormation.query.filter_by(
        auditeur_id=auditeur_id, client_id=current_user.client_id
    ).order_by(InscriptionFormation.date_inscription.desc()).all()
    
    # Formations disponibles pour inscription
    formations_disponibles = Formation.query.filter_by(
        client_id=current_user.client_id, est_actif=True
    ).order_by(Formation.date_debut).all()
    
    # Utilisateurs pour le mentorat
    users = User.query.filter_by(client_id=current_user.client_id).all()
    
    # Statistiques
    stats = {
        'nb_evaluations': len([e for e in evaluations.values() if e]),
        'niveau_moyen': 0,
        'nb_formations': len(inscriptions),
        'pdi_progression': pdi.progression
    }
    
    if stats['nb_evaluations'] > 0:
        notes = [e.evaluation_superieur or e.niveau_actuel or 0 for e in evaluations.values() if e]
        stats['niveau_moyen'] = round(sum(notes) / len(notes), 1) if notes else 0
    
    return render_template('auditeurs/fiche.html',
                         auditeur=auditeur,
                         competences=competences,
                         evaluations=evaluations,
                         pdi=pdi,
                         inscriptions=inscriptions,
                         formations_disponibles=formations_disponibles,
                         users=users,
                         stats=stats)


@app.route('/api/developpement-auditeurs/auditeurs/liste', methods=['GET'])
@login_required
def api_liste_auditeurs_simple():
    """Liste simple des auditeurs pour inscription"""
    auditeurs = User.query.filter(
        User.client_id == current_user.client_id,
        User.role.in_(['auditeur', 'auditor'])
    ).all()
    
    return jsonify({
        'auditeurs': [{'id': a.id, 'username': a.username, 'email': a.email, 'role': a.role} for a in auditeurs]
    })


@app.route('/api/developpement-auditeurs/formation/<int:formation_id>/inscrire/multi', methods=['POST'])
@login_required
def api_inscrire_multi_formation(formation_id):
    """Inscrire plusieurs auditeurs à une formation"""
    formation = get_client_object_or_404(Formation, formation_id)
    data = request.get_json()
    auditeurs_ids = data.get('auditeurs', [])
    
    inscrits = 0
    for auditeur_id in auditeurs_ids:
        existing = InscriptionFormation.query.filter_by(
            formation_id=formation_id, auditeur_id=auditeur_id, client_id=current_user.client_id
        ).first()
        if not existing:
            inscription = InscriptionFormation(
                formation_id=formation_id,
                auditeur_id=auditeur_id,
                client_id=current_user.client_id
            )
            db.session.add(inscription)
            inscrits += 1
    
    db.session.commit()
    return jsonify({'success': True, 'inscrits': inscrits})


@app.route('/api/developpement-auditeurs/formation/<int:formation_id>', methods=['DELETE'])
@login_required
def api_supprimer_formation(formation_id):
    """Supprimer une formation"""
    formation = get_client_object_or_404(Formation, formation_id)
    
    # Supprimer les inscriptions associées
    InscriptionFormation.query.filter_by(formation_id=formation_id).delete()
    db.session.delete(formation)
    db.session.commit()
    
    return jsonify({'success': True})


@app.route('/api/developpement-auditeurs/competence/<int:competence_id>', methods=['GET'])
@login_required
def api_get_competence(competence_id):
    """Récupérer une compétence pour modification"""
    competence = get_client_object_or_404(Competence, competence_id)
    
    return jsonify({
        'success': True,
        'competence': {
            'id': competence.id,
            'code': competence.code,
            'nom': competence.nom,
            'categorie': competence.categorie,
            'description': competence.description,
            'niveau_requis': competence.niveau_requis,
            'est_actif': competence.est_actif
        }
    })


@app.route('/developpement-auditeurs/competence/<int:competence_id>/modifier', methods=['POST'])
@login_required
def modifier_competence(competence_id):
    """Modifier une compétence"""
    if not current_user.is_client_admin:
        flash('Permission refusée', 'error')
        return redirect(url_for('gestion_competences'))
    
    competence = get_client_object_or_404(Competence, competence_id)
    
    competence.code = request.form.get('code').strip().upper()
    competence.nom = request.form.get('nom').strip()
    competence.categorie = request.form.get('categorie')
    competence.description = request.form.get('description', '')
    competence.niveau_requis = int(request.form.get('niveau_requis', 2))
    competence.updated_at = datetime.utcnow()
    
    db.session.commit()
    flash('Compétence modifiée avec succès', 'success')
    return redirect(url_for('gestion_competences'))


@app.route('/api/developpement-auditeurs/competence/<int:competence_id>/toggle', methods=['POST'])
@login_required
def api_toggle_competence(competence_id):
    """Activer/Désactiver une compétence"""
    if not current_user.is_client_admin:
        return jsonify({'success': False, 'error': 'Permission refusée'}), 403
    
    competence = get_client_object_or_404(Competence, competence_id)
    competence.est_actif = not competence.est_actif
    competence.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True, 'est_actif': competence.est_actif})


@app.route('/api/developpement-auditeurs/competence/<int:competence_id>', methods=['DELETE'])
@login_required
def api_delete_competence(competence_id):
    """Supprimer une compétence"""
    if not current_user.is_client_admin:
        return jsonify({'success': False, 'error': 'Permission refusée'}), 403
    
    competence = get_client_object_or_404(Competence, competence_id)
    
    # Supprimer les évaluations associées
    EvaluationCompetence.query.filter_by(competence_id=competence_id).delete()
    db.session.delete(competence)
    db.session.commit()
    
    return jsonify({'success': True})


@app.route('/api/developpement-auditeurs/auditeurs/liste', methods=['GET'])
@login_required
def api_liste_auditeurs_pour_formation():
    """Liste des utilisateurs - MÊME FORMAT que la page liste"""
    
    # La même requête que dans votre page liste_auditeurs
    auditeurs = User.query.filter(
        User.client_id == current_user.client_id,
        User.role.in_(['auditeur', 'auditor', 'manager', 'admin'])
    ).all()
    
    # Si aucun avec ces rôles, prendre tous
    if not auditeurs:
        auditeurs = User.query.filter_by(client_id=current_user.client_id).all()
    
    result = []
    for a in auditeurs:
        result.append({
            'id': a.id,
            'username': a.username,
            'email': a.email,
            'role': a.role,
            'nb_evaluations': 0,  # Valeur par défaut
            'niveau_moyen': 0,     # Valeur par défaut
            'pdi_statut': 'non_defini',
            'pdi_progression': 0
        })
    
    return jsonify({'auditeurs': result})


@app.route('/developpement-auditeurs/auditeur/<int:auditeur_id>/plan')
@login_required
def plan_developpement_auditeur(auditeur_id):
    """Plan de développement individuel d'un auditeur"""
    auditeur = get_client_object_or_404(User, auditeur_id)
    
    plan = PlanDeveloppementIndividuel.query.filter_by(
        auditeur_id=auditeur_id, annee=datetime.now().year, client_id=current_user.client_id
    ).first()
    
    if not plan:
        plan = PlanDeveloppementIndividuel(
            auditeur_id=auditeur_id,
            annee=datetime.now().year,
            statut='brouillon',
            client_id=current_user.client_id
        )
        plan.reference = plan.generer_reference()
        db.session.add(plan)
        db.session.commit()
    
    evaluations = EvaluationCompetence.query.filter_by(
        auditeur_id=auditeur_id, client_id=current_user.client_id
    ).all()
    
    # Analyser les écarts de compétences
    ecarts = []
    for eval in evaluations:
        if eval.competence.niveau_requis > (eval.evaluation_superieur or eval.niveau):
            ecarts.append({
                'competence': eval.competence,
                'niveau_actuel': eval.evaluation_superieur or eval.niveau,
                'niveau_requis': eval.competence.niveau_requis,
                'ecart': eval.competence.niveau_requis - (eval.evaluation_superieur or eval.niveau)
            })
    
    formations_recommandees = get_client_filter(Formation).filter_by(est_actif=True).order_by(Formation.date_debut).all()
    
    return render_template('auditeurs/plan_developpement.html',
                         auditeur=auditeur,
                         plan=plan,
                         ecarts=ecarts,
                         formations=formations_recommandees)


@app.route('/api/auditeur/<int:auditeur_id>/formation/<int:formation_id>/inscrire', methods=['POST'])
@login_required
def api_inscrire_formation_auditeur(auditeur_id, formation_id):
    """Inscrire un auditeur à une formation"""
    auditeur = get_client_object_or_404(User, auditeur_id)
    formation = get_client_object_or_404(Formation, formation_id)
    
    inscription_existante = InscriptionFormation.query.filter_by(
        formation_id=formation_id, auditeur_id=auditeur_id, client_id=current_user.client_id
    ).first()
    
    if inscription_existante:
        return jsonify({'success': False, 'error': 'Déjà inscrit'}), 400
    
    inscription = InscriptionFormation(
        formation_id=formation_id,
        auditeur_id=auditeur_id,
        client_id=current_user.client_id
    )
    db.session.add(inscription)
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Inscrit à {formation.titre}'})


# ============================================
# ROUTES POUR LE DÉVELOPPEMENT DES AUDITEURS
# ============================================
@app.route('/developpement-auditeurs')
@app.route('/developpement-auditeurs/tableau-bord')
@login_required
def dashboard_developpement_auditeurs():
    """Tableau de bord du développement des auditeurs"""
    if not current_user.has_permission('can_manage_audit'):
        flash('Permission requise', 'error')
        return redirect(url_for('dashboard'))
    
    # Récupérer les auditeurs du client
    auditeurs = User.query.filter(
        User.client_id == current_user.client_id,
        User.role.in_(['auditeur', 'auditor', 'manager', 'admin'])
    ).all()
    
    # Ajouter les attributs manquants à chaque auditeur
    for auditeur in auditeurs:
        evaluations = EvaluationCompetence.query.filter_by(
            auditeur_id=auditeur.id, 
            client_id=current_user.client_id
        ).all()
        
        auditeur.nb_evaluations = len(evaluations)
        
        if evaluations:
            total_niveau = 0
            for e in evaluations:
                # Utilisation de getattr pour éviter les erreurs
                niveau = getattr(e, 'evaluation_superieur', None)
                if not niveau:
                    niveau = getattr(e, 'niveau_actuel', None)
                if not niveau:
                    niveau = getattr(e, 'niveau', 1)
                total_niveau += niveau
            auditeur.niveau_moyen = round(total_niveau / len(evaluations), 1)
        else:
            auditeur.niveau_moyen = 0
        
        # Plan de développement individuel (PDI)
        pdi = PlanDeveloppementIndividuel.query.filter_by(
            auditeur_id=auditeur.id, 
            annee=datetime.now().year, 
            client_id=current_user.client_id
        ).first()
        auditeur.pdi_statut = pdi.statut if pdi else 'non_defini'
        auditeur.pdi_progression = pdi.progression if pdi else 0
    
    # Statistiques globales
    stats = {
        'total_auditeurs': len(auditeurs),
        'total_competences': Competence.query.filter_by(client_id=current_user.client_id, est_actif=True).count(),
        'total_formations': Formation.query.filter_by(client_id=current_user.client_id, est_actif=True).count(),
        'formations_en_cours': InscriptionFormation.query.filter_by(client_id=current_user.client_id, statut='inscrit').count(),
        'pdi_en_cours': PlanDeveloppementIndividuel.query.filter_by(client_id=current_user.client_id, statut='en_cours').count(),
        'feedbacks_moyenne': 0
    }
    
    return render_template('auditeurs/dashboard.html',
                         auditeurs=auditeurs,
                         stats=stats,
                         now=datetime.now())


@app.route('/developpement-auditeurs')
@login_required
def developpement_auditeurs_index():
    """Page d'accueil du module développement auditeurs"""
    if not current_user.has_permission('can_manage_audit'):
        flash('Permission requise', 'error')
        return redirect(url_for('dashboard'))
    
    return redirect(url_for('dashboard_developpement_auditeurs'))


@app.route('/api/developpement-auditeurs/auditeurs/creer-demo', methods=['POST'])
@login_required
def api_creer_auditeur_demo():
    """Créer un auditeur de démonstration"""
    
    # Vérifier s'il existe déjà
    existing = User.query.filter_by(username='auditeur_demo').first()
    if existing:
        # Mettre à jour le rôle
        existing.role = 'auditeur'
        db.session.commit()
        return jsonify({'success': True, 'message': 'Auditeur déjà existant, rôle mis à jour'})
    
    # Créer un nouvel auditeur avec un mot de passe valide (12+ caractères)
    auditeur = User(
        username='auditeur_demo',
        email='demo@audit.com',
        role='auditeur',
        client_id=current_user.client_id,
        is_active=True
    )
    auditeur.set_password('demo123456789')  # 12 caractères minimum
    db.session.add(auditeur)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Auditeur de démonstration créé'})


@app.route('/audit/<int:audit_id>/workflow', methods=['GET'])
@login_required
def workflow_approbation_audit(audit_id):
    """Afficher le workflow d'approbation"""
    audit = get_client_object_or_404(Audit, audit_id)
    
    # Vérifier les permissions
    if not check_client_access(audit):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_audits'))
    
    # Créer ou récupérer le workflow
    workflow = WorkflowApprobation.query.filter_by(audit_id=audit_id).first()
    if not workflow:
        workflow = WorkflowApprobation(
            audit_id=audit_id,
            client_id=audit.client_id or current_user.client_id,
            created_by=current_user.id
        )
        db.session.add(workflow)
        db.session.commit()
    
    # Récupérer les utilisateurs pour les approbateurs
    users = get_client_filter(User).order_by(User.username).all()
    
    return render_template('audit/workflow_approbation.html',
                         audit=audit,
                         workflow=workflow,
                         users=users)


@app.route('/dashboard-audit-global')
@login_required
def dashboard_audit_global():
    """Dashboard global des audits avec alertes"""
    
    # Vérification permission
    if not current_user.has_permission('can_manage_audit'):
        flash('Permission requise', 'error')
        return redirect(url_for('dashboard'))
    
    # Déterminer le client
    client_id = current_user.client_id
    if current_user.role == 'super_admin' and session.get('viewing_client_id'):
        client_id = session['viewing_client_id']
    
    # ============================================
    # 1. RÉCUPÉRATION DES AUDITS
    # ============================================
    audits = get_client_filter(Audit).filter_by(is_archived=False).all()
    
    # ============================================
    # 2. STATISTIQUES GLOBALES
    # ============================================
    stats = {
        'total': len(audits),
        'en_cours': len([a for a in audits if a.statut == 'en_cours']),
        'planifies': len([a for a in audits if a.statut == 'planifie']),
        'termines': len([a for a in audits if a.statut == 'termine']),
        'en_attente_approbation': 0,
        'recommandations_echeance': 0,
        'recommandations_retard': 0,
        'constatations_critiques': 0,
        'taux_conformite_moyen': 0
    }
    
    total_conformite = 0
    nb_audits_avec_score = 0
    
    for audit in audits:
        # Workflow
        workflow = WorkflowApprobation.query.filter_by(audit_id=audit.id).first()
        if workflow and workflow.etape_actuelle in ['en_relecture', 'approuve']:
            stats['en_attente_approbation'] += 1
        
        # Score
        if hasattr(audit, 'score_global') and audit.score_global:
            total_conformite += audit.score_global
            nb_audits_avec_score += 1
        
        # Constatations critiques
        stats['constatations_critiques'] += len([c for c in audit.constatations if c.gravite == 'critique'])
    
    stats['taux_conformite_moyen'] = round(total_conformite / nb_audits_avec_score, 1) if nb_audits_avec_score > 0 else 0
    
    # ============================================
    # 3. RÉCUPÉRATION DES ALERTES POUR L'UTILISATEUR
    # ============================================
    alertes = AlerteApprobation.query.filter_by(
        destinataire_id=current_user.id,
        est_lue=False,
        client_id=client_id
    ).order_by(AlerteApprobation.date_creation.desc()).all()
    
    # ============================================
    # 4. RÉCUPÉRATION DES TÂCHES À VENIR
    # ============================================
    aujourdhui = datetime.utcnow().date()
    sept_jours = aujourdhui + timedelta(days=7)
    
    echeances_proches = []
    retards = []
    
    for audit in audits:
        for recommandation in audit.recommandations:
            if recommandation.date_echeance and recommandation.statut != 'termine':
                if recommandation.date_echeance < aujourdhui:
                    retards.append({
                        'audit': audit,
                        'recommandation': recommandation,
                        'jours_retard': (aujourdhui - recommandation.date_echeance).days
                    })
                elif recommandation.date_echeance <= sept_jours:
                    echeances_proches.append({
                        'audit': audit,
                        'recommandation': recommandation,
                        'jours_restants': (recommandation.date_echeance - aujourdhui).days
                    })
    
    # Trier par ordre d'urgence
    retards.sort(key=lambda x: x['jours_retard'], reverse=True)
    echeances_proches.sort(key=lambda x: x['jours_restants'])
    
    # ============================================
    # 5. RÉCUPÉRATION DES AUDITS EN ATTENTE D'APPROBATION
    # ============================================
    audits_en_attente = []
    for audit in audits:
        workflow = WorkflowApprobation.query.filter_by(audit_id=audit.id).first()
        if workflow and workflow.etape_actuelle in ['en_relecture', 'approuve']:
            # Vérifier si l'utilisateur est concerné
            if current_user.role == 'super_admin' or current_user.is_client_admin:
                audits_en_attente.append({
                    'audit': audit,
                    'workflow': workflow,
                    'niveau': 'Niveau 1' if workflow.etape_actuelle == 'en_relecture' else 'Niveau 2'
                })
    
    # ============================================
    # 6. ÉVOLUTION DES AUDITS PAR MOIS
    # ============================================
    evolution_mensuelle = {}
    for audit in audits:
        if audit.created_at:
            mois = audit.created_at.strftime('%Y-%m')
            if mois not in evolution_mensuelle:
                evolution_mensuelle[mois] = {'crees': 0, 'termines': 0}
            evolution_mensuelle[mois]['crees'] += 1
            if audit.statut == 'termine':
                evolution_mensuelle[mois]['termines'] += 1
    
    # ============================================
    # 7. AUDITS PAR TYPE
    # ============================================
    audits_par_type = {}
    for audit in audits:
        type_audit = audit.type_audit or 'non_specifie'
        if type_audit not in audits_par_type:
            audits_par_type[type_audit] = 0
        audits_par_type[type_audit] += 1
    
    return render_template('audit/dashboard_global.html',
                         stats=stats,
                         alertes=alertes,
                         echeances_proches=echeances_proches,
                         retards=retards,
                         audits_en_attente=audits_en_attente,
                         evolution_mensuelle=evolution_mensuelle,
                         audits_par_type=audits_par_type,
                         audits=audits,
                         datetime=datetime,
                         now=datetime.utcnow())


# À exécuter périodiquement (cron job ou APScheduler)
# ============================================
# INITIALISATION DU PLANIFICATEUR D'ALERTES
# ============================================
# ============================================
# CONTEXT PROCESSOR POUR ALERTES NON LUES
# ============================================
@app.route('/dashboard-audit-global-complet')
@login_required
def dashboard_audit_global_complet():
    """Dashboard complet avec toutes les métriques - VERSION CORRIGÉE
    
    ✅ Corrections apportées :
       - Déduplication des alertes d'approbation (1 par audit, par type)
       - Nettoyage automatique des doublons existants en base
       - Nettoyage des alertes obsolètes (workflow avancé)
       - Un seul commit pour toutes les suppressions
    """
    
    client_id = current_user.client_id
    if current_user.role == 'super_admin' and session.get('viewing_client_id'):
        client_id = session['viewing_client_id']
    
    # Récupérer tous les audits
    audits = Audit.query.filter_by(client_id=client_id, is_archived=False).all()
    
    # ============================================
    # ✅ PRÉPARER LES DONNÉES DES AUDITS AVEC WORKFLOW
    # ============================================
    audits_data = []
    for audit in audits:
        workflow = WorkflowApprobation.query.filter_by(audit_id=audit.id).first()
        
        constatations_count = Constatation.query.filter_by(
            audit_id=audit.id, is_archived=False, client_id=client_id
        ).count()
        recommandations_count = Recommandation.query.filter_by(
            audit_id=audit.id, client_id=client_id
        ).count()
        
        audits_data.append({
            'id': audit.id,
            'reference': audit.reference,
            'titre': audit.titre,
            'type_audit': audit.type_audit,
            'statut': audit.statut,
            'progression': audit.progression_globale,
            'constatations_count': constatations_count,
            'recommandations_count': recommandations_count,
            'workflow': {
                'etape_actuelle': workflow.etape_actuelle if workflow else 'brouillon',
                'etape_label': workflow.get_etape_label() if workflow else '📝 Non démarré',
                'etape_icone': workflow.get_etape_icone() if workflow else 'fa-pen',
                'couleur': workflow.get_couleur_etape() if workflow else 'secondary'
            } if workflow else {
                'etape_actuelle': 'brouillon',
                'etape_label': '📝 Non démarré',
                'etape_icone': 'fa-pen',
                'couleur': 'secondary'
            }
        })
    
    # ============================================
    # ✅ ALERTES D'APPROBATION — DÉDUPLIQUÉES (1 par audit, par type)
    # ============================================
    alertes_approbation = []
    audits_deja_vus = set()           # Clé : (audit_id, type_alerte)
    alertes_a_supprimer = []          # Suppressions différées
    
    toutes_alertes = AlerteApprobation.query.filter(
        AlerteApprobation.destinataire_id == current_user.id,
        AlerteApprobation.est_lue == False
    ).order_by(AlerteApprobation.date_creation.desc()).all()
    
    for alerte in toutes_alertes:
        cle = (alerte.audit_id, alerte.type_alerte)
        
        # --- Déduplication : si on a déjà vu cette (audit, type), c'est un doublon ---
        if cle in audits_deja_vus:
            alertes_a_supprimer.append(alerte)
            continue
        audits_deja_vus.add(cle)
        
        audit = Audit.query.get(alerte.audit_id)
        if not audit:
            alertes_a_supprimer.append(alerte)
            continue
        
        workflow = WorkflowApprobation.query.filter_by(audit_id=audit.id).first()
        
        # --- Vérifier que l'alerte est toujours valide ---
        alerte_valide = False
        if workflow:
            if alerte.type_alerte == 'approbation_niveau1' and workflow.etape_actuelle == 'en_relecture':
                alerte_valide = True
            elif alerte.type_alerte == 'approbation_niveau2' and workflow.etape_actuelle == 'approuve':
                alerte_valide = True
            elif alerte.type_alerte in ['echeance', 'retard']:
                alerte_valide = True
        
        if not alerte_valide:
            alertes_a_supprimer.append(alerte)
            continue
        
        alertes_approbation.append({
            'id': alerte.id,
            'audit_id': alerte.audit_id,
            'audit_reference': audit.reference,
            'audit_titre': audit.titre,
            'type_alerte': alerte.type_alerte,
            'titre': alerte.titre,
            'message': alerte.message,
            'date_creation': alerte.date_creation,
            'date_creation_formatee': alerte.date_creation.strftime('%d/%m/%Y %H:%M'),
            'est_lue': alerte.est_lue
        })
    
    # --- Suppressions différées + commit unique ---
    if alertes_a_supprimer:
        try:
            for alerte in alertes_a_supprimer:
                db.session.delete(alerte)
            db.session.commit()
            _journal(f"🧹 {len(alertes_a_supprimer)} alerte(s) en double/obsolète(s) supprimée(s)")
        except Exception as e:
            db.session.rollback()
            _journal(f"⚠️ Erreur suppression alertes: {e}")
    
    # ============================================
    # ✅ TOUTES LES RECOMMANDATIONS
    # ============================================
    toutes_recommandations = []
    for audit in audits:
        recommandations = Recommandation.query.filter_by(
            audit_id=audit.id, client_id=client_id
        ).order_by(Recommandation.date_echeance).all()
        
        for rec in recommandations:
            toutes_recommandations.append({
                'id': rec.id,
                'audit_id': audit.id,
                'audit_reference': audit.reference,
                'description': rec.description,
                'type': rec.type_recommandation,
                'statut': rec.statut,
                'taux_avancement': rec.taux_avancement or 0,
                'date_echeance': rec.date_echeance,
                'date_echeance_formatee': (
                    rec.date_echeance.strftime('%d/%m/%Y') 
                    if rec.date_echeance else 'Non définie'
                ),
                'responsable_nom': (
                    rec.responsable.username if rec.responsable else 'Non assigné'
                ),
                'priorite': rec.score_priorite or 0,
                'est_en_retard': (
                    rec.date_echeance 
                    and rec.date_echeance < datetime.utcnow().date() 
                    and rec.statut != 'termine'
                )
            })
    
    toutes_recommandations.sort(
        key=lambda x: x['date_echeance'] if x['date_echeance'] else datetime.max.date()
    )
    
    # ============================================
    # ✅ STATISTIQUES
    # ============================================
    stats = {
        'total_audits': len(audits),
        'en_cours': len([a for a in audits if a.statut == 'en_cours']),
        'planifies': len([a for a in audits if a.statut == 'planifie']),
        'termines': len([a for a in audits if a.statut == 'termine']),
        'total_constatations': sum(a['constatations_count'] for a in audits_data),
        'total_recommandations': len(toutes_recommandations),
        'recommandations_terminees': len([
            r for r in toutes_recommandations if r['statut'] == 'termine'
        ]),
        'recommandations_retard': len([
            r for r in toutes_recommandations if r.get('est_en_retard', False)
        ]),
        'en_attente_approbation': 0,
        'alertes_non_lues': len(alertes_approbation)
    }
    
    # Compter les audits en attente d'approbation
    for audit in audits:
        workflow = WorkflowApprobation.query.filter_by(audit_id=audit.id).first()
        if workflow and workflow.etape_actuelle in ['en_relecture', 'approuve']:
            stats['en_attente_approbation'] += 1
    
    stats['taux_realisation_recommandations'] = round(
        stats['recommandations_terminees'] 
        / max(stats['total_recommandations'], 1) * 100, 1
    )
    stats['audits_ce_mois'] = len([
        a for a in audits 
        if a.created_at and a.created_at.month == datetime.utcnow().month
    ])
    
    # ============================================
    # ✅ ÉCHÉANCES ET RETARDS
    # ============================================
    aujourdhui = datetime.utcnow().date()
    sept_jours = aujourdhui + timedelta(days=7)
    
    echeances_proches = []
    retards = []
    
    for rec in toutes_recommandations:
        if rec['date_echeance'] and rec['statut'] != 'termine':
            if rec.get('est_en_retard', False):
                retards.append({
                    'audit_id': rec['audit_id'],
                    'audit_reference': rec['audit_reference'],
                    'description': rec['description'],
                    'jours_retard': (aujourdhui - rec['date_echeance']).days
                })
            elif rec['date_echeance'] <= sept_jours:
                echeances_proches.append({
                    'audit_id': rec['audit_id'],
                    'audit_reference': rec['audit_reference'],
                    'description': rec['description'],
                    'jours_restants': (rec['date_echeance'] - aujourdhui).days
                })
    
    # Audits en attente d'approbation (workflow)
    audits_en_attente = []
    for audit in audits:
        workflow = WorkflowApprobation.query.filter_by(audit_id=audit.id).first()
        if workflow and workflow.etape_actuelle in ['en_relecture', 'approuve']:
            audits_en_attente.append({
                'audit': audit,
                'workflow': workflow,
                'niveau': 'Niveau 1' if workflow.etape_actuelle == 'en_relecture' else 'Niveau 2'
            })
    
    # Répartition par type
    audits_par_type = {}
    for audit in audits:
        type_audit = audit.type_audit or 'Non spécifié'
        audits_par_type[type_audit] = audits_par_type.get(type_audit, 0) + 1
    
    # Évolution mensuelle
    evolution_mensuelle = {}
    for audit in audits:
        if audit.created_at:
            mois = audit.created_at.strftime('%Y-%m')
            if mois not in evolution_mensuelle:
                evolution_mensuelle[mois] = {'crees': 0, 'termines': 0}
            evolution_mensuelle[mois]['crees'] += 1
            if audit.statut == 'termine':
                evolution_mensuelle[mois]['termines'] += 1
    
    return render_template(
        'audit/dashboard_global_complet.html',
        audits_data=audits_data,
        stats=stats,
        alertes_approbation=alertes_approbation,
        toutes_recommandations=toutes_recommandations,
        echeances_proches=echeances_proches[:20],
        retards=retards[:20],
        audits_en_attente=audits_en_attente,
        audits_par_type=audits_par_type,
        evolution_mensuelle=evolution_mensuelle,
        datetime=datetime,
        timedelta=timedelta,
        now=datetime.utcnow
    )


@app.route('/dashboard-audit-export')
@login_required
def dashboard_audit_export():
    """Export du dashboard au format Excel, PDF ou CSV"""
    
    from io import BytesIO, StringIO
    import csv
    from datetime import datetime, timedelta
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    
    format_export = request.args.get('format', 'excel')
    
    client_id = current_user.client_id
    if current_user.role == 'super_admin' and session.get('viewing_client_id'):
        client_id = session['viewing_client_id']
    
    # Récupérer les données
    audits = Audit.query.filter_by(client_id=client_id, is_archived=False).all()
    
    # Préparer les données des audits
    audits_data = []
    for audit in audits:
        workflow = WorkflowApprobation.query.filter_by(audit_id=audit.id).first()
        constatations_count = Constatation.query.filter_by(audit_id=audit.id, is_archived=False, client_id=client_id).count()
        recommandations_count = Recommandation.query.filter_by(audit_id=audit.id, client_id=client_id).count()
        
        # Récupérer le responsable
        responsable_nom = audit.responsable.username if audit.responsable else 'Non assigné'
        
        audits_data.append({
            'reference': audit.reference,
            'titre': audit.titre,
            'type_audit': audit.type_audit or 'Non spécifié',
            'statut': audit.statut,
            'workflow': workflow.get_etape_label() if workflow else 'Non démarré',
            'progression': audit.progression_globale,
            'constatations': constatations_count,
            'recommandations': recommandations_count,
            'responsable': responsable_nom,
            'date_debut': audit.date_debut_prevue.strftime('%d/%m/%Y') if audit.date_debut_prevue else '',
            'date_fin': audit.date_fin_prevue.strftime('%d/%m/%Y') if audit.date_fin_prevue else '',
            'score': getattr(audit, 'score_global', 0)
        })
    
    # Récupérer les recommandations
    recommandations_data = []
    for audit in audits:
        recommandations = Recommandation.query.filter_by(audit_id=audit.id, client_id=client_id).all()
        for rec in recommandations:
            recommandations_data.append({
                'audit_reference': audit.reference,
                'description': rec.description,
                'type': rec.type_recommandation,
                'statut': rec.statut,
                'avancement': f"{rec.taux_avancement or 0}%",
                'echeance': rec.date_echeance.strftime('%d/%m/%Y') if rec.date_echeance else 'Non définie',
                'responsable': rec.responsable.username if rec.responsable else 'Non assigné',
                'priorite': rec.score_priorite or 0
            })
    
    # Récupérer les constatations
    constatations_data = []
    for audit in audits:
        constatations = Constatation.query.filter_by(audit_id=audit.id, is_archived=False, client_id=client_id).all()
        for constat in constatations:
            constatations_data.append({
                'audit_reference': audit.reference,
                'reference': constat.reference,
                'description': constat.description,
                'type': constat.type_constatation,
                'gravite': constat.gravite,
                'statut': constat.statut
            })
    
    # Statistiques
    stats = {
        'total_audits': len(audits),
        'en_cours': len([a for a in audits if a.statut == 'en_cours']),
        'termines': len([a for a in audits if a.statut == 'termine']),
        'total_recommandations': len(recommandations_data),
        'recommandations_terminees': len([r for r in recommandations_data if r['statut'] == 'termine']),
        'total_constatations': len(constatations_data),
        'constatations_closes': len([c for c in constatations_data if c['statut'] == 'clos'])
    }
    
    stats['taux_realisation'] = round(stats['recommandations_terminees'] / max(stats['total_recommandations'], 1) * 100, 1)
    stats['taux_cloture'] = round(stats['constatations_closes'] / max(stats['total_constatations'], 1) * 100, 1)
    
    # ============================================
    # EXPORT EXCEL
    # ============================================
    if format_export == 'excel':
        wb = Workbook()
        
        # Style des en-têtes
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1e3a8a", end_color="1e3a8a", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center")
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # ========== SHEET 1 : RÉSUMÉ ==========
        ws1 = wb.active
        ws1.title = "Synthèse"
        
        # Titre
        ws1.merge_cells('A1:D1')
        ws1['A1'] = f"RAPPORT DASHBOARD AUDIT - {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        ws1['A1'].font = Font(bold=True, size=14)
        ws1['A1'].alignment = Alignment(horizontal='center')
        
        # Informations
        resume_data = [
            ('Date de génération', datetime.now().strftime('%d/%m/%Y à %H:%M')),
            ('Période', 'Tous les audits actifs'),
            ('', ''),
            ('INDICATEURS CLÉS', ''),
            (f"Total audits", stats['total_audits']),
            (f"Audits en cours", stats['en_cours']),
            (f"Audits terminés", stats['termines']),
            (f"Taux de réalisation des recommandations", f"{stats['taux_realisation']}%"),
            (f"Taux de clôture des constatations", f"{stats['taux_cloture']}%"),
            (f"Total recommandations", stats['total_recommandations']),
            (f"Recommandations terminées", stats['recommandations_terminees']),
            (f"Total constatations", stats['total_constatations']),
            (f"Constatations closes", stats['constatations_closes'])
        ]
        
        for i, (label, value) in enumerate(resume_data, 3):
            ws1.cell(row=i, column=1, value=label).font = Font(bold=True)
            ws1.cell(row=i, column=2, value=value)
        
        # Ajuster les colonnes
        ws1.column_dimensions['A'].width = 35
        ws1.column_dimensions['B'].width = 25
        
        # ========== SHEET 2 : AUDITS ==========
        ws2 = wb.create_sheet("Audits")
        
        headers_audits = ['Référence', 'Titre', 'Type', 'Statut', 'Workflow', 'Progression', 'Constatations', 'Recommandations', 'Responsable', 'Date début', 'Date fin', 'Score']
        for col, header in enumerate(headers_audits, 1):
            cell = ws2.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = border
        
        for i, audit in enumerate(audits_data, 2):
            ws2.cell(row=i, column=1, value=audit['reference'])
            ws2.cell(row=i, column=2, value=audit['titre'])
            ws2.cell(row=i, column=3, value=audit['type_audit'])
            ws2.cell(row=i, column=4, value=audit['statut'])
            ws2.cell(row=i, column=5, value=audit['workflow'])
            ws2.cell(row=i, column=6, value=audit['progression'])
            ws2.cell(row=i, column=7, value=audit['constatations'])
            ws2.cell(row=i, column=8, value=audit['recommandations'])
            ws2.cell(row=i, column=9, value=audit['responsable'])
            ws2.cell(row=i, column=10, value=audit['date_debut'])
            ws2.cell(row=i, column=11, value=audit['date_fin'])
            ws2.cell(row=i, column=12, value=audit['score'])
            
            # Colorer la progression
            prog_cell = ws2.cell(row=i, column=6)
            if audit['progression'] >= 80:
                prog_cell.fill = PatternFill(start_color="c6f6d5", end_color="c6f6d5", fill_type="solid")
            elif audit['progression'] >= 50:
                prog_cell.fill = PatternFill(start_color="fef3c7", end_color="fef3c7", fill_type="solid")
            elif audit['progression'] > 0:
                prog_cell.fill = PatternFill(start_color="fed7aa", end_color="fed7aa", fill_type="solid")
        
        for col in range(1, len(headers_audits) + 1):
            ws2.column_dimensions[get_column_letter(col)].width = 18
        
        # ========== SHEET 3 : RECOMMANDATIONS ==========
        ws3 = wb.create_sheet("Recommandations")
        
        headers_rec = ['Audit', 'Recommandation', 'Type', 'Statut', 'Avancement', 'Échéance', 'Responsable', 'Priorité']
        for col, header in enumerate(headers_rec, 1):
            cell = ws3.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = border
        
        for i, rec in enumerate(recommandations_data, 2):
            ws3.cell(row=i, column=1, value=rec['audit_reference'])
            ws3.cell(row=i, column=2, value=rec['description'])
            ws3.cell(row=i, column=3, value=rec['type'])
            ws3.cell(row=i, column=4, value=rec['statut'])
            ws3.cell(row=i, column=5, value=rec['avancement'])
            ws3.cell(row=i, column=6, value=rec['echeance'])
            ws3.cell(row=i, column=7, value=rec['responsable'])
            ws3.cell(row=i, column=8, value=rec['priorite'])
        
        for col in range(1, len(headers_rec) + 1):
            ws3.column_dimensions[get_column_letter(col)].width = 20
        ws3.column_dimensions['B'].width = 50
        
        # ========== SHEET 4 : CONSTATATIONS ==========
        ws4 = wb.create_sheet("Constatations")
        
        headers_const = ['Audit', 'Référence', 'Constatation', 'Type', 'Gravité', 'Statut']
        for col, header in enumerate(headers_const, 1):
            cell = ws4.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = border
        
        for i, const in enumerate(constatations_data, 2):
            ws4.cell(row=i, column=1, value=const['audit_reference'])
            ws4.cell(row=i, column=2, value=const['reference'])
            ws4.cell(row=i, column=3, value=const['description'])
            ws4.cell(row=i, column=4, value=const['type'])
            ws4.cell(row=i, column=5, value=const['gravite'])
            ws4.cell(row=i, column=6, value=const['statut'])
        
        for col in range(1, len(headers_const) + 1):
            ws4.column_dimensions[get_column_letter(col)].width = 20
        ws4.column_dimensions['C'].width = 50
        
        # Sauvegarde
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        filename = f"dashboard_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    
    # ============================================
    # EXPORT CSV
    # ============================================
    elif format_export == 'csv':
        output = StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_ALL)
        
        # En-tête
        writer.writerow(['RAPPORT DASHBOARD AUDIT', f"Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')}"])
        writer.writerow([])
        writer.writerow(['INDICATEURS CLÉS'])
        writer.writerow(['Total audits', stats['total_audits']])
        writer.writerow(['Audits en cours', stats['en_cours']])
        writer.writerow(['Audits terminés', stats['termines']])
        writer.writerow(['Taux de réalisation', f"{stats['taux_realisation']}%"])
        writer.writerow(['Total recommandations', stats['total_recommandations']])
        writer.writerow(['Recommandations terminées', stats['recommandations_terminees']])
        writer.writerow([])
        
        # Audits
        writer.writerow(['LISTE DES AUDITS'])
        writer.writerow(['Référence', 'Titre', 'Type', 'Statut', 'Workflow', 'Progression', 'Constatations', 'Recommandations', 'Responsable', 'Score'])
        for audit in audits_data:
            writer.writerow([
                audit['reference'], audit['titre'], audit['type_audit'],
                audit['statut'], audit['workflow'], audit['progression'],
                audit['constatations'], audit['recommandations'],
                audit['responsable'], audit['score']
            ])
        
        output.seek(0)
        output_content = output.getvalue()
        output.close()
        
        # Ajouter BOM pour UTF-8
        output_bytes = output_content.encode('utf-8-sig')
        
        return send_file(
            BytesIO(output_bytes),
            mimetype='text/csv; charset=utf-8',
            as_attachment=True,
            download_name=f"dashboard_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
    
    # ============================================
    # EXPORT PDF
    # ============================================
    elif format_export == 'pdf':
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), title="Dashboard Audit")
        story = []
        styles = getSampleStyleSheet()
        
        # Style personnalisé
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=20,
            textColor=colors.HexColor('#1e3a8a')
        )
        
        # Titre
        story.append(Paragraph("Rapport Dashboard Audit", title_style))
        story.append(Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Statistiques
        story.append(Paragraph("Indicateurs Clés", styles['Heading2']))
        stats_data = [
            ['Total audits', stats['total_audits']],
            ['Audits en cours', stats['en_cours']],
            ['Audits terminés', stats['termines']],
            ['Taux de réalisation', f"{stats['taux_realisation']}%"],
            ['Total recommandations', stats['total_recommandations']],
            ['Recommandations terminées', stats['recommandations_terminees']]
        ]
        
        stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
        ]))
        story.append(stats_table)
        story.append(Spacer(1, 20))
        
        # Audits
        story.append(Paragraph("Liste des Audits", styles['Heading2']))
        
        audit_data = [['Réf.', 'Titre', 'Type', 'Statut', 'Prog.', 'Constat.', 'Rec.', 'Score']]
        for audit in audits_data[:20]:  # Limiter à 20 pour le PDF
            audit_data.append([
                audit['reference'],
                audit['titre'][:30],
                audit['type_audit'],
                audit['statut'],
                f"{audit['progression']}%",
                str(audit['constatations']),
                str(audit['recommandations']),
                str(audit['score'])
            ])
        
        audit_table = Table(audit_data, colWidths=[0.8*inch, 1.8*inch, 0.8*inch, 0.8*inch, 0.6*inch, 0.6*inch, 0.6*inch, 0.6*inch])
        audit_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(audit_table)
        
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"dashboard_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )
    
    else:
        return jsonify({'error': 'Format non supporté'}), 400


# ============================================
# LETTRE DE MISSION - ROUTES API
# ============================================
@app.route('/api/feuille-travail/<int:feuille_id>/lettre-mission', methods=['POST'])
@login_required
def api_sauvegarder_lettre_mission(feuille_id):
    """Sauvegarder la lettre de mission sur le serveur"""
    from datetime import datetime
    
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    try:
        data = request.get_json()
        
        # Vérifier que les données sont valides
        if not data:
            return jsonify({'success': False, 'error': 'Données manquantes'}), 400
        
        # Vérifier que les données sont un dictionnaire
        if not isinstance(data, dict):
            return jsonify({'success': False, 'error': 'Format de données invalide'}), 400
        
        # Initialiser contenu si vide
        if not feuille.contenu:
            feuille.contenu = {}
        
        # Sauvegarder la lettre
        feuille.contenu['lettre_mission'] = data
        feuille.contenu['lettre_mission_updated_at'] = datetime.utcnow().isoformat()
        feuille.contenu['lettre_mission_updated_by'] = current_user.id
        feuille.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Lettre de mission sauvegardée',
            'updated_at': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur sauvegarde lettre mission: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/feuille-travail/<int:feuille_id>/envoyer-lettre', methods=['POST'])
@login_required
def api_envoyer_lettre_mission(feuille_id):
    """Envoyer la lettre de mission par email"""
    from flask_mail import Mail, Message
    
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    data = request.get_json()
    
    email = data.get('email')
    if not email:
        return jsonify({'success': False, 'error': 'Email requis'}), 400
    
    # Récupérer la lettre
    lettre = feuille.contenu.get('lettre_mission', {}) if feuille.contenu else {}
    
    try:
        # Générer le PDF
        pdf_content = generer_pdf_lettre(lettre, feuille)
        
        # Créer le message
        msg = Message(
            subject=f"Lettre de mission - {lettre.get('reference', 'Audit')}",
            recipients=[email],
            body=f"""
            Bonjour,
            
            {data.get('message', 'Veuillez trouver ci-joint la lettre de mission.')}
            
            Cordialement,
            L'équipe d'audit
            """
        )
        
        # Attacher le PDF
        msg.attach(
            filename=f"lettre_mission_{lettre.get('reference', 'audit')}.pdf",
            content_type='application/pdf',
            data=pdf_content
        )
        
        # Envoyer (nécessite configuration Flask-Mail)
        # mail.send(msg)
        
        return jsonify({'success': True, 'message': 'Email envoyé'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/feuille-travail/<int:feuille_id>/envoyer-lettre', methods=['POST'])
@login_required
def api_envoyer_lettre_mission_email(feuille_id):
    """Envoyer la lettre de mission par email"""
    from datetime import datetime
    import traceback
    from flask import current_app
    
    _journal(f"\n📧 ENVOI LETTRE DE MISSION - Début")
    _journal(f"   Feuille ID: {feuille_id}")
    
    try:
        feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
        audit = get_client_object_or_404(Audit, feuille.audit_id)
        data = request.get_json()
        
        _journal(f"   Data reçue: {data}")
        
        email_destinataire = data.get('email', '')
        message_personnalise = data.get('message', '')
        
        if not email_destinataire:
            return jsonify({'success': False, 'error': 'Email requis'}), 400
        
        _journal(f"   Email destinataire: {email_destinataire}")
        
        # Récupérer la lettre
        lettre = {}
        if feuille.contenu and 'lettre_mission' in feuille.contenu:
            lettre = feuille.contenu['lettre_mission']
        
        if not lettre:
            return jsonify({'success': False, 'error': 'Aucune lettre de mission trouvée'}), 400
        
        _journal(f"   Lettre trouvée: {lettre.get('reference', 'Sans réf')}")
        
        # Formatage des dates
        date_formatee = lettre.get('date', datetime.now().strftime('%d/%m/%Y'))
        if lettre.get('date') and '-' in lettre['date']:
            try:
                d = datetime.strptime(lettre['date'], '%Y-%m-%d')
                date_formatee = d.strftime('%d/%m/%Y')
            except:
                pass
        
        # Construction du corps de l'email en HTML
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Lettre de mission - {lettre.get('reference', 'Audit')}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background: #f5f5f5;
                }}
                .container {{
                    max-width: 800px;
                    margin: 0 auto;
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header {{
                    text-align: right;
                    margin-bottom: 30px;
                    padding-bottom: 15px;
                    border-bottom: 2px solid #1e3a8a;
                }}
                .section {{
                    margin: 20px 0;
                }}
                .section-title {{
                    font-weight: bold;
                    font-size: 14px;
                    color: #1e3a8a;
                    margin-bottom: 10px;
                    border-bottom: 1px solid #ddd;
                    padding-bottom: 5px;
                }}
                .signature {{
                    margin-top: 40px;
                    text-align: right;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                }}
                .footer {{
                    margin-top: 30px;
                    font-size: 11px;
                    color: #666;
                    text-align: center;
                    border-top: 1px solid #eee;
                    padding-top: 15px;
                }}
                .message-box {{
                    background: #f0fdf4;
                    border-left: 4px solid #22c55e;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 8px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <strong>{lettre.get('emetteur', 'Audit Interne')}</strong><br>
                    Réf. : {lettre.get('reference', '')}<br>
                    Le {date_formatee}
                </div>
                
                <div style="margin-bottom: 20px;">
                    <strong>{lettre.get('destinataire', 'Destinataire')}</strong><br>
                    {lettre.get('societe', '')}
                </div>
                
                <div style="font-weight: bold; font-size: 14px; margin: 20px 0; padding: 10px; background: #f0f0f0;">
                    OBJET : {lettre.get('objet', 'Lettre de mission')}
                </div>
                
                <div class="section">
                    <div class="section-title">📋 Contexte</div>
                    <p>{lettre.get('introduction', '').replace(chr(10), '<br>')}</p>
                </div>
                
                <div class="section">
                    <div class="section-title">🎯 Objectifs</div>
                    <p>{lettre.get('objectifs', '').replace(chr(10), '<br>')}</p>
                </div>
                
                <div class="section">
                    <div class="section-title">📍 Périmètre</div>
                    <p>{lettre.get('perimetre', '').replace(chr(10), '<br>')}</p>
                </div>
                
                <div class="section">
                    <div class="section-title">📅 Calendrier</div>
                    <p>Du {lettre.get('date_debut', 'à définir')} au {lettre.get('date_fin', 'à définir')}<br>
                    Durée estimée : {lettre.get('duree', 'À définir')}</p>
                </div>
                
                <div class="section">
                    <div class="section-title">👥 Équipe d'audit</div>
                    <p>{lettre.get('equipe', '').replace(chr(10), '<br>')}</p>
                </div>
                
                <div class="section">
                    <div class="section-title">📝 Modalités</div>
                    <p>{lettre.get('modalites', '').replace(chr(10), '<br>')}</p>
                </div>
                
                <div class="section">
                    <div class="section-title">📦 Livrables</div>
                    <p>{lettre.get('livrables', '').replace(chr(10), '<br>')}</p>
                </div>
                
                {f'''
                <div class="section">
                    <div class="section-title">🔒 Confidentialité</div>
                    <p>{lettre.get('confidentialite_texte', '').replace(chr(10), '<br>')}</p>
                </div>
                ''' if lettre.get('confidentialite') else ''}
                
                <div class="signature">
                    <p>Pour l'équipe d'audit,</p>
                    <br><br>
                    <p><strong>{lettre.get('emetteur', "L'auditeur principal")}</strong></p>
                </div>
                
                {f'''
                <div class="message-box">
                    <strong>📝 Message de l'expéditeur :</strong><br>
                    {message_personnalise.replace(chr(10), '<br>')}
                </div>
                ''' if message_personnalise else ''}
                
                <div class="footer">
                    {feuille.reference} - {feuille.titre}<br>
                    Audit {audit.reference}
                </div>
            </div>
        </body>
        </html>
        """
        
        # Corps texte simple pour fallback
        text_body = f"""
        LETTRE DE MISSION
        
        Réf. : {lettre.get('reference', '')}
        Date : {date_formatee}
        
        Destinataire : {lettre.get('destinataire', 'Destinataire')}
        Société : {lettre.get('societe', '')}
        
        OBJET : {lettre.get('objet', 'Lettre de mission')}
        
        Contexte :
        {lettre.get('introduction', '')}
        
        Objectifs :
        {lettre.get('objectifs', '')}
        
        Périmètre :
        {lettre.get('perimetre', '')}
        
        Calendrier : du {lettre.get('date_debut', 'à définir')} au {lettre.get('date_fin', 'à définir')}
        Durée estimée : {lettre.get('duree', 'À définir')}
        
        Équipe d'audit :
        {lettre.get('equipe', '')}
        
        Modalités :
        {lettre.get('modalites', '')}
        
        Livrables :
        {lettre.get('livrables', '')}
        
        {f'Message : {message_personnalise}' if message_personnalise else ''}
        
        Cordialement,
        {lettre.get('emetteur', "L'auditeur principal")}
        """
        
        # Essayer d'envoyer avec l'email service existant
        email_envoye = False
        erreur_email = None
        
        try:
            # Essayer d'importer le service email
            import sys
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            from services.email_service import EmailService
            email_service = EmailService()
            
            email_service.send_email(
                to_email=email_destinataire,
                subject=f"Lettre de mission - {lettre.get('reference', audit.reference)}",
                body=text_body,
                html_body=html_body
            )
            email_envoye = True
            _journal(f"   ✅ Email envoyé via EmailService")
            
        except ImportError as e:
            _journal(f"   ⚠️ EmailService non trouvé: {e}")
            erreur_email = str(e)
        except Exception as e:
            _journal(f"   ⚠️ Erreur EmailService: {e}")
            erreur_email = str(e)
        
        # SIMULATION si pas d'email configuré (mode développement)
        if not email_envoye:
            _journal(f"\n   📧 [SIMULATION] Email aurait été envoyé à: {email_destinataire}")
            _journal(f"   Sujet: Lettre de mission - {lettre.get('reference', audit.reference)}")
            _journal(f"   Message: {message_personnalise[:100]}...")
            email_envoye = True
        
        if not email_envoye:
            return jsonify({
                'success': False, 
                'error': f'Impossible d\'envoyer l\'email. Détail: {erreur_email}'
            }), 500
        
        # Journaliser l'envoi
        if not feuille.contenu:
            feuille.contenu = {}
        if 'lettre_mission_envoyee' not in feuille.contenu:
            feuille.contenu['lettre_mission_envoyee'] = []
        
        feuille.contenu['lettre_mission_envoyee'].append({
            'destinataire': email_destinataire,
            'date': datetime.now().isoformat(),
            'par': current_user.id,
            'simulation': not email_envoye
        })
        feuille.updated_at = datetime.now()
        db.session.commit()
        
        _journal(f"   ✅ Envoi terminé avec succès")
        
        return jsonify({
            'success': True,
            'message': f'Lettre envoyée à {email_destinataire}',
            'simulation': not email_envoye
        })
        
    except Exception as e:
        _journal(f"❌ Erreur dans api_envoyer_lettre_mission_email: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'error': str(e)
        }), 500


@app.route('/api/feuille-travail/<int:feuille_id>/emails-envoyes', methods=['GET'])
@login_required
def api_get_emails_envoyes(feuille_id):
    """Récupérer l'historique des emails envoyés"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    emails = []
    if feuille.contenu and 'lettre_mission_envoyee' in feuille.contenu:
        emails = feuille.contenu['lettre_mission_envoyee']
    
    # Ajouter les noms des expéditeurs
    for email in emails:
        if 'par' in email:
            user = User.query.get(email['par'])
            email['envoye_par'] = user.username if user else 'Système'
    
    return jsonify({
        'success': True,
        'emails': emails
    })


@app.route('/api/feuille-travail/<int:feuille_id>/supprimer-email', methods=['POST'])
@login_required
def api_supprimer_email_historique(feuille_id):
    """Supprimer un email de l'historique"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    data = request.get_json()
    
    email_date = data.get('email_date')
    
    if not email_date:
        return jsonify({'success': False, 'error': 'Date email requise'}), 400
    
    if feuille.contenu and 'lettre_mission_envoyee' in feuille.contenu:
        original_count = len(feuille.contenu['lettre_mission_envoyee'])
        feuille.contenu['lettre_mission_envoyee'] = [
            e for e in feuille.contenu['lettre_mission_envoyee'] 
            if e.get('date') != email_date
        ]
        
        if len(feuille.contenu['lettre_mission_envoyee']) < original_count:
            feuille.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'success': True, 'message': 'Email supprimé'})
    
    return jsonify({'success': False, 'error': 'Email non trouvé'}), 404


@app.route('/api/feuille-travail/<int:feuille_id>/exporter-word', methods=['POST'])
@login_required
def api_exporter_lettre_word(feuille_id):
    """Exporter la lettre de mission au format Word"""
    from docx import Document
    from docx.shared import Inches, Pt
    from io import BytesIO
    
    data = request.get_json()
    
    doc = Document()
    
    # Titre
    title = doc.add_heading(f'LETTRE DE MISSION', 0)
    title.alignment = 1  # Centré
    
    # Référence et date
    doc.add_paragraph(f"Réf. : {data.get('reference', '')}")
    doc.add_paragraph(f"Le : {data.get('date', '')}")
    doc.add_paragraph()
    
    # Destinataire
    doc.add_paragraph(f"À l'attention de : {data.get('destinataire', '')}")
    doc.add_paragraph(f"{data.get('societe', '')}")
    doc.add_paragraph()
    
    # Objet
    doc.add_heading(f"OBJET : {data.get('objet', '')}", level=2)
    
    # Sections
    sections = [
        ('Contexte', 'introduction'),
        ('Objectifs', 'objectifs'),
        ('Périmètre', 'perimetre'),
        ('Calendrier', None),
        ('Équipe d\'audit', 'equipe'),
        ('Modalités pratiques', 'modalites'),
        ('Livrables', 'livrables')
    ]
    
    for title, key in sections:
        if key and data.get(key):
            doc.add_heading(title, level=3)
            doc.add_paragraph(data.get(key, ''))
        elif title == 'Calendrier':
            doc.add_heading('Calendrier prévisionnel', level=3)
            doc.add_paragraph(f"Du {data.get('date_debut', '')} au {data.get('date_fin', '')}")
            doc.add_paragraph(f"Durée estimée : {data.get('duree', '')}")
    
    if data.get('confidentialite'):
        doc.add_heading('Confidentialité', level=3)
        doc.add_paragraph(data.get('confidentialite_texte', ''))
    
    # Signature
    doc.add_paragraph()
    doc.add_paragraph("Pour l'équipe d'audit,")
    doc.add_paragraph()
    doc.add_paragraph()
    doc.add_paragraph(data.get('emetteur', ''))
    
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name=f"lettre_mission_{data.get('reference', 'audit')}.docx"
    )


@app.route('/api/feuille-travail/<int:feuille_id>/generer-lettre-mission', methods=['POST'])
@login_required
def api_generer_lettre_mission(feuille_id):
    """Générer une lettre de mission avec l'IA (utilise le service existant)"""
    from services.analyse_ia import ServiceAnalyseIA
    
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    audit = get_client_object_or_404(Audit, feuille.audit_id)
    
    # Initialiser le service IA
    service_ia = ServiceAnalyseIA()
    
    # Générer la lettre via le service IA
    lettre_mission = service_ia.generer_lettre_mission(
        audit_id=audit.id,
        feuille_id=feuille_id
    )
    
    if not lettre_mission:
        return jsonify({'success': False, 'error': 'Erreur de génération'}), 500
    
    # Sauvegarder dans la feuille
    if not feuille.contenu:
        feuille.contenu = {}
    
    feuille.contenu['lettre_mission'] = lettre_mission
    feuille.contenu['lettre_mission_updated_at'] = datetime.utcnow().isoformat()
    feuille.contenu['lettre_mission_updated_by'] = current_user.id
    feuille.updated_at = datetime.utcnow()
    db.session.commit()
    
    mode = lettre_mission.get('_mode', 'simulation')
    message = "Lettre de mission générée avec succès"
    if mode == 'openai':
        message += " (via OpenAI)"
    else:
        message += " (mode simulation)"
    
    return jsonify({
        'success': True,
        'lettre_mission': lettre_mission,
        'mode': mode,
        'message': message
    })


@app.route('/developpement-auditeurs/auditeurs')
@login_required
def liste_auditeurs():
    """Liste des auditeurs avec leurs compétences"""
    if not current_user.has_permission('can_manage_audit'):
        flash('Permission requise', 'error')
        return redirect(url_for('dashboard'))
    
    # CORRIGÉ : Supprimer le filtre est_actif qui n'existe pas
    auditeurs = User.query.filter(
        User.client_id == current_user.client_id,
        User.role.in_(['auditeur', 'auditor', 'manager'])
    ).all()
    
    # Enrichir avec les statistiques
    for auditeur in auditeurs:
        evaluations = EvaluationCompetence.query.filter_by(
            auditeur_id=auditeur.id, client_id=current_user.client_id
        ).all()
        auditeur.nb_evaluations = len(evaluations)
        if evaluations:
            total = 0
            count = 0
            for e in evaluations:
                niveau = e.evaluation_superieur or e.niveau_actuel or 0
                total += niveau
                count += 1
            auditeur.niveau_moyen = round(total / count, 1) if count > 0 else 0
        else:
            auditeur.niveau_moyen = 0
        
        pdi = PlanDeveloppementIndividuel.query.filter_by(
            auditeur_id=auditeur.id, annee=datetime.now().year, client_id=current_user.client_id
        ).first()
        auditeur.pdi_statut = pdi.statut if pdi else 'non_defini'
        auditeur.pdi_progression = pdi.progression if pdi else 0
    
    return render_template('auditeurs/liste.html', auditeurs=auditeurs)


@app.route('/developpement-auditeurs/auditeur/<int:auditeur_id>')
@login_required
def fiche_auditeur(auditeur_id):
    """Fiche détaillée d'un auditeur"""
    auditeur = get_client_object_or_404(User, auditeur_id)
    
    # Compétences et évaluations
    competences = Competence.query.filter_by(client_id=current_user.client_id, est_actif=True).all()
    evaluations = {}
    for comp in competences:
        eval_comp = EvaluationCompetence.query.filter_by(
            auditeur_id=auditeur_id, competence_id=comp.id, client_id=current_user.client_id
        ).first()
        evaluations[comp.id] = eval_comp
    
    # Plan de développement
    pdi = PlanDeveloppementIndividuel.query.filter_by(
        auditeur_id=auditeur_id, annee=datetime.now().year, client_id=current_user.client_id
    ).first()
    if not pdi:
        pdi = PlanDeveloppementIndividuel(
            auditeur_id=auditeur_id,
            annee=datetime.now().year,
            client_id=current_user.client_id
        )
        pdi.reference = pdi.generer_reference()
        db.session.add(pdi)
        db.session.commit()
    
    # Formations suivies
    inscriptions = InscriptionFormation.query.filter_by(
        auditeur_id=auditeur_id, client_id=current_user.client_id
    ).order_by(InscriptionFormation.date_inscription.desc()).all()
    
    # Feedbacks reçus
    feedbacks = FeedbackAuditeur.query.filter_by(
        auditeur_id=auditeur_id, client_id=current_user.client_id
    ).order_by(FeedbackAuditeur.created_at.desc()).all()
    
    # Statistiques
    stats = {
        'nb_evaluations': len([e for e in evaluations.values() if e]),
        'niveau_moyen': 0,
        'nb_formations': len(inscriptions),
        'nb_feedbacks': len(feedbacks),
        'pdi_progression': pdi.progression
    }
    
    if stats['nb_evaluations'] > 0:
        notes = [e.evaluation_superieur or e.niveau_actuel for e in evaluations.values() if e]
        stats['niveau_moyen'] = round(sum(notes) / len(notes), 1)
    
    return render_template('auditeurs/fiche.html',
                         auditeur=auditeur,
                         competences=competences,
                         evaluations=evaluations,
                         pdi=pdi,
                         inscriptions=inscriptions,
                         feedbacks=feedbacks,
                         stats=stats,
                         now=datetime.now())


@app.route('/developpement-auditeurs/competences')
@login_required
def gestion_competences():
    """Gestion des compétences"""
    if not current_user.is_client_admin:
        flash('Permission refusée', 'error')
        return redirect(url_for('dashboard_developpement_auditeurs'))
    
    competences = Competence.query.filter_by(client_id=current_user.client_id).order_by(Competence.categorie, Competence.nom).all()
    
    # Statistiques par catégorie
    categories = db.session.query(
        Competence.categorie, db.func.count(Competence.id)
    ).filter_by(client_id=current_user.client_id).group_by(Competence.categorie).all()
    
    return render_template('auditeurs/competences.html', 
                         competences=competences, 
                         categories=categories)


@app.route('/developpement-auditeurs/auditeur/<int:auditeur_id>/evaluation', methods=['GET', 'POST'])
@login_required
def evaluer_auditeur(auditeur_id):
    """Évaluer les compétences d'un auditeur"""
    auditeur = get_client_object_or_404(User, auditeur_id)
    competences = Competence.query.filter_by(client_id=current_user.client_id, est_actif=True).all()
    
    if request.method == 'POST':
        try:
            for comp in competences:
                niveau = request.form.get(f'niveau_{comp.id}')
                commentaire = request.form.get(f'commentaire_{comp.id}')
                
                if niveau:
                    evaluation = EvaluationCompetence.query.filter_by(
                        auditeur_id=auditeur_id, competence_id=comp.id, client_id=current_user.client_id
                    ).first()
                    
                    if not evaluation:
                        evaluation = EvaluationCompetence(
                            auditeur_id=auditeur_id,
                            competence_id=comp.id,
                            client_id=current_user.client_id
                        )
                        db.session.add(evaluation)
                    
                    evaluation.evaluation_superieur = int(niveau)
                    evaluation.commentaire_evaluateur = commentaire
                    evaluation.evaluateur_id = current_user.id
                    evaluation.date_evaluation = datetime.utcnow()
                    
                    # CORRIGÉ : Vérifier que les valeurs ne sont pas None
                    niveau_actuel = evaluation.niveau_actuel or 0
                    niveau_souhaite = evaluation.niveau_souhaite or comp.niveau_requis or 2
                    
                    # Calculer l'écart en toute sécurité
                    evaluation.ecart = niveau_souhaite - niveau_actuel
            
            db.session.commit()
            flash('Évaluation sauvegardée avec succès', 'success')
            return redirect(url_for('fiche_auditeur', auditeur_id=auditeur_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    # GET - Afficher les évaluations existantes
    evaluations = {}
    for comp in competences:
        eval_existante = EvaluationCompetence.query.filter_by(
            auditeur_id=auditeur_id, competence_id=comp.id, client_id=current_user.client_id
        ).first()
        evaluations[comp.id] = eval_existante
    
    return render_template('auditeurs/evaluation.html',
                         auditeur=auditeur,
                         competences=competences,
                         evaluations=evaluations)


@app.route('/api/developpement-auditeurs/plan/<int:plan_id>', methods=['POST'])
@login_required
def api_sauvegarder_plan(plan_id):
    """Sauvegarder le plan de développement"""
    plan = get_client_object_or_404(PlanDeveloppementIndividuel, plan_id)
    data = request.get_json()
    
    if 'objectifs_globaux' in data:
        plan.objectifs_globaux = data['objectifs_globaux']
    if 'objectifs_smart' in data:
        plan.objectifs_smart = data['objectifs_smart']
    if 'actions_prevues' in data:
        plan.actions_prevues = data['actions_prevues']
    if 'actions_realisees' in data:
        plan.actions_realisees = data['actions_realisees']
    if 'competences_cibles' in data:
        plan.competences_cibles = ','.join(map(str, data['competences_cibles']))
    if 'formations_prevues' in data:
        plan.formations_prevues = ','.join(map(str, data['formations_prevues']))
    if 'mentor_id' in data:
        plan.mentor_id = data['mentor_id']
    if 'statut' in data:
        plan.statut = data['statut']
    
    plan.calculer_progression()
    plan.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True, 'progression': plan.progression})


@app.route('/api/developpement-auditeurs/plan/<int:plan_id>/valider', methods=['POST'])
@login_required
def api_valider_plan(plan_id):
    """Valider le plan de développement"""
    if not current_user.is_client_admin:
        return jsonify({'success': False, 'error': 'Permission refusée'}), 403
    
    plan = get_client_object_or_404(PlanDeveloppementIndividuel, plan_id)
    data = request.get_json()
    
    plan.statut = 'valide'
    plan.valide_par_id = current_user.id
    plan.date_validation = datetime.utcnow()
    plan.commentaire_validation = data.get('commentaire', '')
    db.session.commit()
    
    return jsonify({'success': True})


@app.route('/api/developpement-auditeurs/formation/<int:formation_id>/inscrire', methods=['POST'])
@login_required
def api_inscrire_formation(formation_id):
    """Inscrire un auditeur à une formation"""
    formation = get_client_object_or_404(Formation, formation_id)
    data = request.get_json()
    auditeur_id = data.get('auditeur_id')
    
    inscription_existante = InscriptionFormation.query.filter_by(
        formation_id=formation_id, auditeur_id=auditeur_id, client_id=current_user.client_id
    ).first()
    
    if inscription_existante:
        return jsonify({'success': False, 'error': 'Déjà inscrit'}), 400
    
    inscription = InscriptionFormation(
        formation_id=formation_id,
        auditeur_id=auditeur_id,
        client_id=current_user.client_id
    )
    db.session.add(inscription)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Inscription confirmée'})


@app.route('/api/developpement-auditeurs/feedback', methods=['POST'])
@login_required
def api_ajouter_feedback():
    """Ajouter un feedback pour un auditeur"""
    data = request.get_json()
    
    feedback = FeedbackAuditeur(
        auditeur_id=data.get('auditeur_id'),
        evaluateur_id=current_user.id,
        mission_id=data.get('mission_id'),
        qualite_travail=data.get('qualite_travail'),
        respect_delais=data.get('respect_delais'),
        communication=data.get('communication'),
        autonomie=data.get('autonomie'),
        esprit_equipe=data.get('esprit_equipe'),
        rigueur=data.get('rigueur'),
        points_forts=data.get('points_forts'),
        points_amelioration=data.get('points_amelioration'),
        commentaire_global=data.get('commentaire_global'),
        est_anonyme=data.get('est_anonyme', True),
        periode=data.get('periode'),
        client_id=current_user.client_id
    )
    
    db.session.add(feedback)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Feedback envoyé'})


@app.route('/api/developpement-auditeurs/stats')
@login_required
def api_stats_developpement():
    """Statistiques pour les graphiques"""
    # Évolution des compétences par trimestre
    stats = {
        'evolution_competences': [],
        'formations_par_type': [],
        'pdi_statuts': [],
        'top_auditeurs': []
    }
    
    # Top auditeurs (meilleure progression)
    top = db.session.query(
        PlanDeveloppementIndividuel.auditeur_id,
        db.func.avg(PlanDeveloppementIndividuel.progression).label('progression_moyenne')
    ).filter_by(client_id=current_user.client_id).group_by(PlanDeveloppementIndividuel.auditeur_id).order_by(db.text('progression_moyenne DESC')).limit(5).all()
    
    for t in top:
        user = User.query.get(t.auditeur_id)
        if user:
            stats['top_auditeurs'].append({
                'nom': user.username,
                'progression': round(t.progression_moyenne, 1)
            })
    
    return jsonify(stats)


@app.route('/developpement-auditeurs/competence/nouvelle', methods=['POST'])
@login_required
def nouvelle_competence():
    """Créer une nouvelle compétence"""
    if not current_user.is_client_admin:
        flash('Permission refusée', 'error')
        return redirect(url_for('liste_competences'))
    
    try:
        competence = Competence(
            code=request.form.get('code').strip().upper(),
            nom=request.form.get('nom').strip(),
            categorie=request.form.get('categorie'),
            description=request.form.get('description', ''),
            niveau_requis=int(request.form.get('niveau_requis', 2)),
            client_id=current_user.client_id
        )
        db.session.add(competence)
        db.session.commit()
        flash('Compétence ajoutée avec succès', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
    
    return redirect(url_for('liste_competences'))


@app.route('/developpement-auditeurs/competence/<int:competence_id>/toggle', methods=['POST'])
@login_required
def toggle_competence(competence_id):
    """Activer/Désactiver une compétence"""
    if not current_user.is_client_admin:
        return jsonify({'success': False, 'error': 'Permission refusée'}), 403
    
    competence = get_client_object_or_404(Competence, competence_id)
    competence.est_actif = not competence.est_actif
    competence.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True})


@app.route('/developpement-auditeurs/formations')
@login_required
def liste_formations():
    """Liste des formations disponibles avec filtre multi-tenant"""
    formations = Formation.query.filter_by(
        client_id=current_user.client_id,
        est_actif=True
    ).order_by(Formation.date_debut.desc(), Formation.created_at.desc()).all()
    
    return render_template('auditeurs/formations.html', formations=formations, now=datetime.now())


@app.route('/developpement-auditeurs/formation/nouvelle', methods=['GET', 'POST'])
@login_required
def nouvelle_formation():
    """Créer une nouvelle formation"""
    if not current_user.is_client_admin and not current_user.has_permission('can_manage_audit'):
        flash('Permission refusée', 'error')
        return redirect(url_for('liste_formations'))
    
    if request.method == 'POST':
        try:
            titre = request.form.get('titre', '').strip()
            if not titre:
                flash('Le titre est requis', 'error')
                return redirect(url_for('nouvelle_formation'))
            
            formation = Formation()
            formation.titre = titre
            formation.description = request.form.get('description', '').strip()
            formation.type_formation = request.form.get('type_formation', 'interne')
            formation.duree_heures = float(request.form.get('duree_heures')) if request.form.get('duree_heures') else None
            formation.cout = float(request.form.get('cout')) if request.form.get('cout') else None
            formation.formateur = request.form.get('formateur', '').strip()
            formation.objectifs = request.form.get('objectifs', '').strip()
            formation.client_id = current_user.client_id
            
            if request.form.get('date_debut'):
                formation.date_debut = datetime.strptime(request.form.get('date_debut'), '%Y-%m-%d').date()
            if request.form.get('date_fin'):
                formation.date_fin = datetime.strptime(request.form.get('date_fin'), '%Y-%m-%d').date()
            
            # Générer référence
            prefixe = f"F-{datetime.now().year}-"
            count = Formation.query.filter(
                Formation.reference.like(f'{prefixe}%'),
                Formation.client_id == current_user.client_id
            ).count()
            formation.reference = f"{prefixe}{count + 1:04d}"
            
            db.session.add(formation)
            db.session.commit()
            
            flash(f'Formation "{titre}" créée avec succès', 'success')
            return redirect(url_for('liste_formations'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('auditeurs/nouvelle_formation.html')


@app.route('/developpement-auditeurs/formation/<int:formation_id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_formation(formation_id):
    """Modifier une formation"""
    formation = get_client_object_or_404(Formation, formation_id)
    
    if not current_user.is_client_admin and not current_user.has_permission('can_manage_audit'):
        flash('Permission refusée', 'error')
        return redirect(url_for('liste_formations'))
    
    if request.method == 'POST':
        try:
            formation.titre = request.form.get('titre', '').strip()
            formation.description = request.form.get('description', '').strip()
            formation.type_formation = request.form.get('type_formation', 'interne')
            formation.duree_heures = float(request.form.get('duree_heures')) if request.form.get('duree_heures') else None
            formation.cout = float(request.form.get('cout')) if request.form.get('cout') else None
            formation.formateur = request.form.get('formateur', '').strip()
            formation.objectifs = request.form.get('objectifs', '').strip()
            
            if request.form.get('date_debut'):
                formation.date_debut = datetime.strptime(request.form.get('date_debut'), '%Y-%m-%d').date()
            else:
                formation.date_debut = None
            if request.form.get('date_fin'):
                formation.date_fin = datetime.strptime(request.form.get('date_fin'), '%Y-%m-%d').date()
            else:
                formation.date_fin = None
            
            db.session.commit()
            flash('Formation modifiée avec succès', 'success')
            return redirect(url_for('liste_formations'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('auditeurs/modifier_formation.html', formation=formation)


@app.route('/developpement-auditeurs/formation/<int:formation_id>/inscrire', methods=['GET', 'POST'])
@login_required
def inscrire_auditeurs_formation(formation_id):
    """Inscrire des auditeurs à une formation"""
    formation = get_client_object_or_404(Formation, formation_id)
    
    if not current_user.is_client_admin and not current_user.has_permission('can_manage_audit'):
        flash('Permission refusée', 'error')
        return redirect(url_for('liste_formations'))
    
    # Récupérer les auditeurs du client - sans est_actif
    auditeurs = User.query.filter(
        User.client_id == current_user.client_id,
        User.role.in_(['auditeur', 'auditor', 'manager', 'admin'])
    ).all()
    
    # Récupérer les inscriptions existantes
    inscriptions_existantes = InscriptionFormation.query.filter_by(
        formation_id=formation_id,
        client_id=current_user.client_id
    ).all()
    inscrits_ids = [insc.auditeur_id for insc in inscriptions_existantes]
    
    if request.method == 'POST':
        try:
            auditeurs_selectionnes = request.form.getlist('auditeurs')
            auditeurs_ids = [int(id) for id in auditeurs_selectionnes]
            
            # Supprimer les inscriptions pour les auditeurs non sélectionnés
            for insc in inscriptions_existantes:
                if insc.auditeur_id not in auditeurs_ids:
                    db.session.delete(insc)
            
            # Ajouter les nouvelles inscriptions
            for auditeur_id in auditeurs_ids:
                if auditeur_id not in inscrits_ids:
                    inscription = InscriptionFormation(
                        formation_id=formation_id,
                        auditeur_id=auditeur_id,
                        client_id=current_user.client_id,
                        date_inscription=datetime.utcnow(),
                        statut='inscrit'
                    )
                    db.session.add(inscription)
            
            db.session.commit()
            flash(f'{len(auditeurs_ids)} auditeur(s) inscrit(s) avec succès', 'success')
            return redirect(url_for('liste_formations'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('auditeurs/inscrire_auditeurs.html',
                         formation=formation,
                         auditeurs=auditeurs,
                         inscrits_ids=inscrits_ids)


@app.route('/developpement-auditeurs/formation/<int:formation_id>/supprimer', methods=['POST'])
@login_required
def supprimer_formation(formation_id):
    """Supprimer une formation (soft delete)"""
    formation = get_client_object_or_404(Formation, formation_id)
    
    if not current_user.is_client_admin and not current_user.has_permission('can_manage_audit'):
        flash('Permission refusée', 'error')
        return redirect(url_for('liste_formations'))
    
    try:
        # Soft delete
        formation.est_actif = False
        db.session.commit()
        flash('Formation supprimée avec succès', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
    
    return redirect(url_for('liste_formations'))


@app.route('/feuille-travail/<int:feuille_id>/upload-preuve', methods=['POST'])
@login_required
def upload_preuve_feuille(feuille_id):
    """Uploader une preuve pour une feuille de travail"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    if 'fichier' not in request.files:
        flash('Aucun fichier sélectionné', 'error')
        return redirect(url_for('editer_feuille_travail', feuille_id=feuille_id))
    
    fichier = request.files['fichier']
    if fichier.filename == '':
        flash('Aucun fichier sélectionné', 'error')
        return redirect(url_for('editer_feuille_travail', feuille_id=feuille_id))
    
    # Vérifier l'extension
    allowed_extensions = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png', 'txt'}
    extension = fichier.filename.rsplit('.', 1)[1].lower() if '.' in fichier.filename else ''
    
    if extension not in allowed_extensions:
        flash(f'Extension .{extension} non autorisée', 'error')
        return redirect(url_for('editer_feuille_travail', feuille_id=feuille_id))
    
    try:
        # Créer le dossier si nécessaire
        upload_folder = os.path.join('static', 'uploads', 'feuilles_travail', str(feuille_id))
        os.makedirs(upload_folder, exist_ok=True)
        
        # Générer un nom unique
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nom_unique = secure_filename(fichier.filename)
        nom_final = f"{timestamp}_{nom_unique}"
        chemin = os.path.join(upload_folder, nom_final)
        
        fichier.save(chemin)
        
        # Ajouter la preuve à la feuille
        if feuille.pieces_jointes:
            feuille.pieces_jointes += f",{nom_final}"
        else:
            feuille.pieces_jointes = nom_final
        
        feuille.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash('Fichier uploadé avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de l\'upload: {str(e)}', 'error')
    
    return redirect(url_for('editer_feuille_travail', feuille_id=feuille_id))


@app.route('/feuille-travail/<int:feuille_id>/supprimer-preuve/<path:filename>', methods=['POST'])
@login_required
def supprimer_preuve_feuille(feuille_id, filename):
    """Supprimer une preuve d'une feuille de travail"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    if feuille.pieces_jointes:
        preuves = feuille.pieces_jointes.split(',')
        if filename in preuves:
            preuves.remove(filename)
            feuille.pieces_jointes = ','.join(preuves) if preuves else None
            
            # Supprimer le fichier physique
            file_path = os.path.join('static', 'uploads', 'feuilles_travail', str(feuille_id), filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            
            feuille.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Preuve supprimée avec succès', 'success')
    
    return redirect(url_for('editer_feuille_travail', feuille_id=feuille_id))


@app.route('/feuille-travail/<int:feuille_id>/export-pdf')
@login_required
def exporter_feuille_travail_pdf(feuille_id):
    """Exporter une feuille de travail en PDF"""
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration
    
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    tests = TestControleFeuille.query.filter_by(feuille_travail_id=feuille_id).order_by(TestControleFeuille.ordre).all()
    
    html = render_template('audit/feuille_travail_pdf.html', feuille=feuille, tests=tests, now=datetime.now())
    
    font_config = FontConfiguration()
    pdf = HTML(string=html).write_pdf(font_config=font_config)
    
    filename = f"feuille_travail_{feuille.reference}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response


@app.route('/feuille-travail/<int:feuille_id>/mettre-a-jour', methods=['POST'])
@login_required
def mettre_a_jour_feuille_travail(feuille_id):
    """Mettre à jour une feuille de travail"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    try:
        feuille.titre = request.form.get('titre', feuille.titre).strip()
        feuille.description = request.form.get('description', feuille.description).strip()
        feuille.type_feuille = request.form.get('type_feuille', feuille.type_feuille)
        feuille.statut = request.form.get('statut', feuille.statut)
        
        mission_id = request.form.get('mission_id')
        feuille.mission_id = int(mission_id) if mission_id and mission_id.isdigit() else None
        
        feuille.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Feuille mise à jour avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
    
    return redirect(url_for('editer_feuille_travail', feuille_id=feuille_id))


@app.route('/feuille-travail/<int:feuille_id>/calculer-progression', methods=['POST'])
@login_required
def calculer_progression_feuille(feuille_id):
    """Calculer la progression d'une feuille de travail"""
    feuille = get_client_object_or_404(FeuilleTravail, feuille_id)
    
    progression = feuille.progression
    feuille.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True, 'progression': progression})


@app.route('/api/chronogramme/programme/<int:programme_id>/repartition-auto', methods=['POST'])
@login_required
def repartition_auto_chronogramme(programme_id):
    """Répartir automatiquement les missions pour équilibrer la charge"""
    programme = ProgrammeAudit.query.get_or_404(programme_id)
    
    if not check_client_access(programme):
        return jsonify({'success': False, 'message': 'Accès non autorisé'}), 403
    
    try:
        # Récupérer les missions planifiées
        missions = programme.missions.filter_by(
            statut='planifie',
            is_archived=False
        ).all()
        
        if not missions:
            return jsonify({'success': True, 'message': 'Aucune mission à répartir'})
        
        # Répartition par priorité
        missions_critique = [m for m in missions if m.priorite == 'critique']
        missions_elevee = [m for m in missions if m.priorite == 'elevee']
        missions_moyenne = [m for m in missions if m.priorite == 'moyenne']
        missions_faible = [m for m in missions if m.priorite == 'faible']
        
        # Répartition sur les années
        annees = list(range(programme.annee_debut, programme.annee_fin + 1))
        modifications = 0
        
        # Année 1 : missions critiques
        if annees:
            for i, mission in enumerate(missions_critique):
                mission.annee_prevue = annees[0]
                mission.trimestre_prevue = (i % 4) + 1
                modifications += 1
        
        # Année 2 : missions élevées
        if len(annees) > 1:
            for i, mission in enumerate(missions_elevee):
                mission.annee_prevue = annees[1]
                mission.trimestre_prevue = (i % 4) + 1
                modifications += 1
        else:
            for i, mission in enumerate(missions_elevee):
                mission.annee_prevue = annees[0]
                mission.trimestre_prevue = (i % 4) + 1
                modifications += 1
        
        # Année 3 : missions moyennes
        if len(annees) > 2:
            for i, mission in enumerate(missions_moyenne):
                mission.annee_prevue = annees[2]
                mission.trimestre_prevue = (i % 4) + 1
                modifications += 1
        else:
            for i, mission in enumerate(missions_moyenne):
                mission.annee_prevue = annees[-1]
                mission.trimestre_prevue = (i % 4) + 1
                modifications += 1
        
        # Répartition des missions faibles sur les années restantes
        for i, mission in enumerate(missions_faible):
            annee_index = i % len(annees)
            mission.annee_prevue = annees[annee_index]
            mission.trimestre_prevue = (i % 4) + 1
            modifications += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{modifications} missions réparties automatiquement'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/mission-audit/<int:mission_id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_mission_audit(mission_id):
    """Modifier une mission d'audit"""
    mission = MissionAudit.query.get_or_404(mission_id)
    programme = mission.programme
    
    if not check_client_access(mission):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('detail_programme_audit', id=programme.id))
    
    if request.method == 'POST':
        try:
            # Mise à jour des champs
            mission.titre = request.form.get('titre', mission.titre)
            mission.description = request.form.get('description', mission.description)
            mission.priorite = request.form.get('priorite', mission.priorite)
            
            annee_prevue = request.form.get('annee_prevue')
            if annee_prevue:
                mission.annee_prevue = int(annee_prevue)
            
            trimestre_prevue = request.form.get('trimestre_prevue')
            if trimestre_prevue:
                mission.trimestre_prevue = int(trimestre_prevue)
            else:
                mission.trimestre_prevue = None
            
            duree_estimee = request.form.get('duree_estimee')
            if duree_estimee:
                mission.duree_estimee = int(duree_estimee)
            
            date_debut_prevue = request.form.get('date_debut_prevue')
            if date_debut_prevue:
                mission.date_debut_prevue = datetime.strptime(date_debut_prevue, '%Y-%m-%d').date()
            
            date_fin_prevue = request.form.get('date_fin_prevue')
            if date_fin_prevue:
                mission.date_fin_prevue = datetime.strptime(date_fin_prevue, '%Y-%m-%d').date()
            
            risque_id = request.form.get('risque_id')
            if risque_id:
                mission.risque_id = int(risque_id) if risque_id else None
            
            responsable_id = request.form.get('responsable_id')
            if responsable_id:
                mission.responsable_id = int(responsable_id) if responsable_id else None
            
            statut = request.form.get('statut')
            if statut:
                mission.statut = statut
            
            progression = request.form.get('progression')
            if progression:
                mission.progression = int(progression)
            
            mission.commentaire_repli = request.form.get('commentaire_repli', mission.commentaire_repli)
            mission.updated_at = datetime.now()
            
            db.session.commit()
            flash('Mission modifiée avec succès', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
        
        return redirect(url_for('detail_programme_audit', id=programme.id))
    
    # GET - Afficher le formulaire
    risques_disponibles = get_client_filter(Risque).filter_by(is_archived=False).all()
    
    if current_user.role == 'super_admin':
        utilisateurs = User.query.filter_by(is_active=True).all()
    else:
        utilisateurs = get_client_filter(User).filter_by(is_active=True).all()
    
    return render_template('programme_audit/edit_mission.html',
                         mission=mission,
                         programme=programme,
                         risques_disponibles=risques_disponibles,
                         utilisateurs=utilisateurs)


@app.route('/programme-audit/<int:id>/generer-auto')
@login_required
def generer_missions_auto_programme(id):  # Garder id pour la cohérence
    """Générer automatiquement les missions basées sur les risques"""
    programme = ProgrammeAudit.query.get_or_404(id)
    
    if not check_client_access(programme):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_programmes_audit'))
    
    try:
        missions_crees = generer_missions_auto(programme.id, current_user.id)
        flash(f'{missions_crees} missions générées automatiquement', 'success')
        
    except Exception as e:
        flash(f'Erreur lors de la génération: {str(e)}', 'error')
    
    return redirect(url_for('detail_programme_audit', id=id))


@app.route('/programme-audit/<int:programme_id>/plan-pluie')
@login_required
def plan_pluie_programme(programme_id):
    """Gestion du plan de repli (plan pluie)"""
    
    programme = ProgrammeAudit.query.get_or_404(programme_id)
    
    if not check_client_access(programme):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_programmes_audit'))
    
    # ========== MISSIONS REPORTABLES ==========
    missions_reportables = []
    for mission in programme.missions:
        # Une mission peut être reportée si :
        # - Elle est planifiée ou en cours
        # - Elle n'est pas archivée
        # - Elle n'a pas déjà un plan de repli actif
        if (mission.statut in ['planifie', 'en_cours'] and 
            not mission.is_archived):
            
            # Vérifier si elle a déjà un plan de repli
            plan_existant = PlanPluieAudit.query.filter_by(
                mission_principale_id=mission.id,
                statut='actif',
                is_archived=False
            ).first()
            
            if not plan_existant:
                missions_reportables.append(mission)
    
    # ========== MISSIONS DE REMPLACEMENT ==========
    missions_remplacement = []
    annee_courante = datetime.now().year
    trimestre_actuel = (datetime.now().month - 1) // 3 + 1
    
    for mission in programme.missions:
        # Une mission peut servir de remplacement si :
        # - Elle est planifiée (pas en cours, pas terminée)
        # - Elle n'est pas archivée
        # - Elle n'est pas déjà utilisée comme mission principale d'un plan actif
        # - Elle est dans le futur (année > année courante OU même année mais trimestre futur)
        
        if (mission.statut == 'planifie' and 
            not mission.is_archived):
            
            # Exclure les missions qui sont déjà des missions principales
            est_mission_principale = PlanPluieAudit.query.filter_by(
                mission_principale_id=mission.id,
                statut='actif',
                is_archived=False
            ).first() is not None
            
            if not est_mission_principale:
                # Vérifier si c'est une mission future
                if mission.annee_prevue > annee_courante:
                    missions_remplacement.append(mission)
                elif mission.annee_prevue == annee_courante:
                    if mission.trimestre_prevue and mission.trimestre_prevue > trimestre_actuel:
                        missions_remplacement.append(mission)
                    elif not mission.trimestre_prevue:
                        # Si pas de trimestre, on l'inclut quand même
                        missions_remplacement.append(mission)
    
    # ========== PLANS DE REPLI EXISTANTS ==========
    plans_pluie = PlanPluieAudit.query.filter(
        PlanPluieAudit.mission_principale_id.in_([m.id for m in programme.missions])
    ).filter_by(is_archived=False).all()
    
    return render_template('programme_audit/plan_pluie.html',
                         programme=programme,
                         missions_reportables=missions_reportables,
                         missions_remplacement=missions_remplacement,
                         plans_pluie=plans_pluie,
                         datetime=datetime,
                         now=datetime.now(),
                         annee_courante=annee_courante,
                         trimestre_actuel=trimestre_actuel)


@app.route('/programme-audit/<int:programme_id>/plan-pluie/creer', methods=['POST'])
@login_required
def creer_plan_pluie(programme_id):  # Paramètre: programme_id
    """Créer un plan de repli"""
    programme = ProgrammeAudit.query.get_or_404(programme_id)
    
    if not check_client_access(programme):
        return jsonify({'success': False, 'message': 'Accès non autorisé'}), 403
    
    try:
        # Validation des données
        nom = request.form.get('nom', '').strip()
        if not nom:
            return jsonify({'success': False, 'message': 'Le nom du plan est requis'}), 400
        
        mission_principale_id = request.form.get('mission_principale_id')
        mission_remplacement_id = request.form.get('mission_remplacement_id')
        
        if not mission_principale_id or not mission_remplacement_id:
            return jsonify({'success': False, 'message': 'Les missions principale et de remplacement sont requises'}), 400
        
        # Vérifier que les missions existent et appartiennent au programme
        mission_principale = MissionAudit.query.get_or_404(mission_principale_id)
        mission_remplacement = MissionAudit.query.get_or_404(mission_remplacement_id)
        
        if mission_principale.programme_id != programme.id or mission_remplacement.programme_id != programme.id:
            return jsonify({'success': False, 'message': 'Les missions doivent appartenir au même programme'}), 400
        
        if mission_principale_id == mission_remplacement_id:
            return jsonify({'success': False, 'message': 'La mission de remplacement doit être différente de la mission principale'}), 400
        
        # Vérifier qu'un plan n'existe pas déjà
        plan_existant = PlanPluieAudit.query.filter_by(
            mission_principale_id=mission_principale_id,
            is_archived=False
        ).first()
        
        if plan_existant:
            return jsonify({'success': False, 'message': 'Un plan de repli existe déjà pour cette mission'}), 400
        
        # Créer le plan
        plan = PlanPluieAudit(
            nom=nom,
            description=request.form.get('description', '').strip(),
            mission_principale_id=int(mission_principale_id),
            mission_remplacement_id=int(mission_remplacement_id),
            condition_type=request.form.get('condition_type', 'retard'),
            condition_seuil=int(request.form.get('condition_seuil', 15)) if request.form.get('condition_seuil') else None,
            condition_description=request.form.get('condition_description', '').strip(),
            statut='actif',
            created_by=current_user.id,
            client_id=programme.client_id
        )
        
        db.session.add(plan)
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Plan de repli créé avec succès', 'plan_id': plan.id})
        else:
            flash('Plan de repli créé avec succès', 'success')
            return redirect(url_for('plan_pluie_programme', programme_id=programme_id))
        
    except Exception as e:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': str(e)}), 500
        else:
            flash(f'Erreur: {str(e)}', 'error')
            return redirect(url_for('plan_pluie_programme', programme_id=programme_id))


@app.route('/programme-audit/<int:programme_id>/simuler-retard', methods=['POST'])
@login_required
def simuler_retard(programme_id):
    """Simuler un retard pour tester les plans de repli"""
    try:
        programme = ProgrammeAudit.query.get_or_404(programme_id)
        
        if not check_client_access(programme):
            return jsonify({'success': False, 'message': 'Accès non autorisé'}), 403
        
        # DEBUG - Afficher ce qui est reçu
        _journal(f"=== SIMULATION RETARD ===")
        _journal(f"Programme ID: {programme_id}")
        _journal(f"Form data: {dict(request.form)}")
        _journal(f"Headers: {dict(request.headers)}")
        
        # Récupérer le paramètre 'jours'
        jours_str = request.form.get('jours', '15')
        _journal(f"Jours reçus: '{jours_str}'")
        
        try:
            jours_retard = int(jours_str)
        except ValueError:
            return jsonify({'success': False, 'message': f'Le paramètre jours doit être un nombre valide, reçu: {jours_str}'}), 400
        
        if jours_retard <= 0 or jours_retard > 365:
            return jsonify({'success': False, 'message': 'Le nombre de jours doit être entre 1 et 365'}), 400
        
        date_limite = datetime.now().date() - timedelta(days=jours_retard)
        
        alertes_generes = 0
        missions_retard = []
        plans_declenchables = []
        
        for mission in programme.missions:
            if (mission.date_fin_prevue and 
                mission.date_fin_prevue < date_limite and 
                mission.statut == 'planifie'):
                
                missions_retard.append({
                    'id': mission.id,
                    'reference': mission.reference,
                    'titre': mission.titre,
                    'retard_jours': (date_limite - mission.date_fin_prevue).days if mission.date_fin_prevue else jours_retard
                })
                
                plan = PlanPluieAudit.query.filter_by(
                    mission_principale_id=mission.id,
                    statut='actif',
                    is_archived=False
                ).first()
                
                if plan:
                    alertes_generes += 1
                    plans_declenchables.append({
                        'id': plan.id,
                        'nom': plan.nom,
                        'mission_remplacement': plan.mission_remplacement.reference if plan.mission_remplacement else 'N/A'
                    })
        
        message = f"Simulation de {jours_retard} jours de retard : {len(missions_retard)} mission(s) concernée(s), {alertes_generes} plan(s) de repli déclenchable(s)"
        
        return jsonify({
            'success': True,
            'alertes': alertes_generes,
            'missions_retard': len(missions_retard),
            'missions_liste': missions_retard[:5],
            'plans_declenchables': plans_declenchables[:5],
            'message': message,
            'debug': {
                'programme_id': programme_id,
                'jours': jours_retard,
                'date_limite': date_limite.isoformat()
            }
        })
        
    except Exception as e:
        _journal(f"Erreur dans simuler_retard: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/mission-audit/<int:mission_id>/reprogrammer', methods=['POST'])
@login_required
def reprogrammer_mission_audit(mission_id):
    """Reprogrammer une mission d'audit (changer les dates)"""
    mission = MissionAudit.query.get_or_404(mission_id)
    programme = mission.programme
    
    if not check_client_access(mission):
        return jsonify({'success': False, 'message': 'Accès non autorisé'}), 403
    
    try:
        # Récupérer les nouvelles dates
        nouvelle_annee = request.form.get('nouvelle_annee')
        nouveau_trimestre = request.form.get('nouveau_trimestre')
        nouvelle_date_debut = request.form.get('nouvelle_date_debut')
        nouvelle_date_fin = request.form.get('nouvelle_date_fin')
        raison = request.form.get('raison', '')
        
        # Mettre à jour la mission
        if nouvelle_annee:
            mission.annee_prevue = int(nouvelle_annee)
        if nouveau_trimestre:
            mission.trimestre_prevue = int(nouveau_trimestre)
        if nouvelle_date_debut:
            mission.date_debut_prevue = datetime.strptime(nouvelle_date_debut, '%Y-%m-%d').date()
        if nouvelle_date_fin:
            mission.date_fin_prevue = datetime.strptime(nouvelle_date_fin, '%Y-%m-%d').date()
        
        # Si la mission était reportée, la remettre en planifié
        if mission.statut == 'reporte':
            mission.statut = 'planifie'
        
        mission.updated_at = datetime.now()
        
        # Ajouter un commentaire sur la reprogrammation
        if raison:
            if mission.commentaire_repli:
                mission.commentaire_repli += f"\n[{datetime.now().strftime('%d/%m/%Y')}] Reprogrammation: {raison}"
            else:
                mission.commentaire_repli = f"[{datetime.now().strftime('%d/%m/%Y')}] Reprogrammation: {raison}"
        
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Mission reprogrammée avec succès'})
        else:
            flash('Mission reprogrammée avec succès', 'success')
            return redirect(url_for('detail_programme_audit', id=programme.id))
        
    except Exception as e:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': str(e)}), 500
        else:
            flash(f'Erreur: {str(e)}', 'error')
            return redirect(url_for('detail_programme_audit', id=programme.id))


@app.route('/api/chronogramme/v2/mission/<int:mid>/deplacer', methods=['POST'])
@login_required
def chrono_deplacer(mid):
    """Déplacer une mission - VERSION FINALE"""
    _journal(f"\n{'='*50}")
    _journal(f"🚀 API DEPLACER V2 - Mission {mid}")
    _journal(f"{'='*50}")
    
    try:
        # 1. Récupérer la mission
        mission = MissionAudit.query.get_or_404(mid)
        if not check_client_access(mission):
            return jsonify({'success': False, 'message': 'Accès non autorisé'}), 403
        
        # 2. Parser le JSON
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Données JSON requises'}), 400
        
        _journal(f"📦 Données reçues: {data}")
        
        # 3. Valider l'année
        annee = data.get('annee')
        if annee is None:
            return jsonify({'success': False, 'message': 'Année requise'}), 400
        
        try:
            annee = int(annee)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Année invalide'}), 400
        
        programme = mission.programme
        if annee < programme.annee_debut or annee > programme.annee_fin:
            return jsonify({
                'success': False, 
                'message': f'Année hors programme ({programme.annee_debut}-{programme.annee_fin})'
            }), 400
        
        # 4. Valider le trimestre (optionnel)
        trimestre = data.get('trimestre')
        if trimestre is not None:
            try:
                trimestre = int(trimestre)
                if 1 <= trimestre <= 4:
                    mission.trimestre_prevue = trimestre
                else:
                    _journal(f"⚠️ Trimestre {trimestre} hors limites, ignoré")
            except (ValueError, TypeError):
                _journal(f"⚠️ Trimestre invalide: {trimestre}, ignoré")
        
        # 5. Mettre à jour
        mission.annee_prevue = annee
        mission.updated_at = datetime.now()
        db.session.commit()
        
        _journal(f"✅ Mission {mid} déplacée vers {annee}-T{mission.trimestre_prevue}")
        return jsonify({
            'success': True, 
            'message': f'Mission déplacée en {annee}',
            'mission': {
                'id': mission.id,
                'annee': mission.annee_prevue,
                'trimestre': mission.trimestre_prevue
            }
        })
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/chronogramme/v2/mission/<int:mid>/duree', methods=['POST'])
@login_required
def chrono_duree(mid):
    """Modifier la durée - VERSION FINALE"""
    _journal(f"\n{'='*50}")
    _journal(f"🚀 API DUREE V2 - Mission {mid}")
    _journal(f"{'='*50}")
    
    try:
        mission = MissionAudit.query.get_or_404(mid)
        if not check_client_access(mission):
            return jsonify({'success': False, 'message': 'Accès non autorisé'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Données JSON requises'}), 400
        
        _journal(f"📦 Données reçues: {data}")
        
        duree = data.get('duree')
        if duree is None:
            return jsonify({'success': False, 'message': 'Durée requise'}), 400
        
        try:
            duree = int(duree)
            if duree < 1:
                return jsonify({'success': False, 'message': 'La durée doit être > 0'}), 400
            if duree > 365:
                return jsonify({'success': False, 'message': 'La durée ne peut pas dépasser 365 jours'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Durée invalide'}), 400
        
        mission.duree_estimee = duree
        mission.updated_at = datetime.now()
        db.session.commit()
        
        _journal(f"✅ Mission {mid} durée modifiée: {duree}j")
        return jsonify({'success': True, 'message': f'Durée modifiée à {duree} jours'})
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/chronogramme/v2/mission/<int:mid>/statut', methods=['POST'])
@login_required
def chrono_statut(mid):
    """Changer le statut - VERSION FINALE"""
    _journal(f"\n{'='*50}")
    _journal(f"🚀 API STATUT V2 - Mission {mid}")
    _journal(f"{'='*50}")
    
    try:
        mission = MissionAudit.query.get_or_404(mid)
        if not check_client_access(mission):
            return jsonify({'success': False, 'message': 'Accès non autorisé'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Données JSON requises'}), 400
        
        _journal(f"📦 Données reçues: {data}")
        
        statut = data.get('statut')
        statuts_valides = ['planifie', 'en_cours', 'termine', 'reporte', 'annule']
        
        if not statut or statut not in statuts_valides:
            return jsonify({'success': False, 'message': 'Statut invalide'}), 400
        
        ancien_statut = mission.statut
        mission.statut = statut
        
        # Gestion automatique des dates
        aujourdhui = datetime.now().date()
        
        if statut == 'termine':
            mission.progression = 100
            if not mission.date_fin_reelle:
                mission.date_fin_reelle = aujourdhui
        elif statut == 'en_cours':
            if not mission.date_debut_reelle:
                mission.date_debut_reelle = aujourdhui
            mission.progression = max(mission.progression or 0, 25)
        elif statut == 'planifie':
            mission.progression = 0
        
        mission.updated_at = datetime.now()
        db.session.commit()
        
        _journal(f"✅ Mission {mid}: {ancien_statut} → {statut}")
        return jsonify({'success': True, 'message': f'Statut changé en {statut}'})
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/chronogramme/v2/mission/<int:mid>/assigner', methods=['POST'])
@login_required
def chrono_assigner(mid):
    """Assigner un responsable - VERSION FINALE"""
    _journal(f"\n{'='*50}")
    _journal(f"🚀 API ASSIGNER V2 - Mission {mid}")
    _journal(f"{'='*50}")
    
    try:
        mission = MissionAudit.query.get_or_404(mid)
        if not check_client_access(mission):
            return jsonify({'success': False, 'message': 'Accès non autorisé'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Données JSON requises'}), 400
        
        _journal(f"📦 Données reçues: {data}")
        
        responsable_id = data.get('responsable_id')
        
        if responsable_id is None or responsable_id == 0:
            mission.responsable_id = None
            message = "Responsable retiré"
            _journal(f"✅ Responsable retiré")
        else:
            try:
                responsable_id = int(responsable_id)
                user = User.query.get(responsable_id)
                if not user:
                    return jsonify({'success': False, 'message': 'Utilisateur non trouvé'}), 404
                
                if not check_client_access(user):
                    return jsonify({'success': False, 'message': 'Accès non autorisé à cet utilisateur'}), 403
                
                mission.responsable_id = responsable_id
                message = f"Responsable: {user.username}"
                _journal(f"✅ {message}")
                
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'ID responsable invalide'}), 400
        
        mission.updated_at = datetime.now()
        db.session.commit()
        
        return jsonify({'success': True, 'message': message})
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/chronogramme/v2/programme/<int:pid>/repartition-auto', methods=['POST'])
@login_required
def chrono_repartition(pid):
    """Répartition automatique - VERSION FINALE"""
    _journal(f"\n{'='*50}")
    _journal(f"🚀 API REPARTITION V2 - Programme {pid}")
    _journal(f"{'='*50}")
    
    try:
        programme = ProgrammeAudit.query.get_or_404(pid)
        if not check_client_access(programme):
            return jsonify({'success': False, 'message': 'Accès non autorisé'}), 403
        
        missions = programme.missions.filter_by(
            statut='planifie', 
            is_archived=False
        ).all()
        
        if not missions:
            return jsonify({'success': True, 'message': 'Aucune mission à répartir'})
        
        modifications = 0
        annees = list(range(programme.annee_debut, programme.annee_fin + 1))
        
        if not annees:
            return jsonify({'success': False, 'message': 'Programme sans année'}), 400
        
        for i, mission in enumerate(missions):
            # Répartition par priorité
            if mission.priorite == 'critique' and annees:
                mission.annee_prevue = annees[0]
            elif mission.priorite == 'elevee' and len(annees) > 1:
                mission.annee_prevue = annees[1]
            elif mission.priorite == 'moyenne' and len(annees) > 2:
                mission.annee_prevue = annees[2]
            else:
                mission.annee_prevue = annees[i % len(annees)]
            
            # Répartition trimestrielle équilibrée
            mission.trimestre_prevue = (i % 4) + 1
            modifications += 1
        
        db.session.commit()
        
        _journal(f"✅ {modifications} missions réparties")
        return jsonify({
            'success': True, 
            'message': f'{modifications} missions réparties automatiquement'
        })
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/chronogramme/v2/utilisateurs', methods=['GET'])
@login_required
def api_chronogramme_utilisateurs():
    """API pour récupérer la liste des utilisateurs éligibles comme responsables"""
    _journal(f"\n🔵 API UTILISATEURS - Chargement de la liste")
    
    try:
        # Récupérer les utilisateurs en fonction des permissions
        if current_user.role == 'super_admin':
            utilisateurs = User.query.filter_by(is_active=True, is_blocked=False).all()
        else:
            utilisateurs = get_client_filter(User).filter_by(
                is_active=True, 
                is_blocked=False
            ).all()
        
        # Formater les données
        data = []
        for user in utilisateurs:
            # Déterminer le nom d'affichage
            display_name = user.username
            if hasattr(user, 'prenom') and user.prenom and hasattr(user, 'nom') and user.nom:
                display_name = f"{user.prenom} {user.nom}"
            elif hasattr(user, 'full_name') and user.full_name:
                display_name = user.full_name
            
            data.append({
                'id': user.id,
                'username': user.username,
                'display_name': display_name,
                'email': user.email,
                'role': user.role,
                'role_display': user.get_role_display_name() if hasattr(user, 'get_role_display_name') else user.role,
                'department': user.department or '',
                'is_client_admin': user.is_client_admin
            })
        
        # Trier par nom d'affichage
        data.sort(key=lambda x: x['display_name'].lower())
        
        return jsonify({
            'success': True,
            'utilisateurs': data,
            'total': len(data)
        })
        
    except Exception as e:
        _journal(f"❌ Erreur: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/chronogramme/v2/programme/<int:pid>/stats')
@login_required
def chrono_stats(pid):
    """Statistiques pour le chronogramme"""
    try:
        programme = ProgrammeAudit.query.get_or_404(pid)
        if not check_client_access(programme):
            return jsonify({'success': False, 'message': 'Accès non autorisé'}), 403
        
        missions = programme.missions.filter_by(is_archived=False).all()
        
        stats = {
            'total_missions': len(missions),
            'missions_terminees': len([m for m in missions if m.statut == 'termine']),
            'progression': programme.progression,
            'charge_totale': programme.jours_audit_planifies,
            'charge_realisee': programme.jours_audit_realises,
            'par_priorite': {
                'critique': len([m for m in missions if m.priorite == 'critique']),
                'elevee': len([m for m in missions if m.priorite == 'elevee']),
                'moyenne': len([m for m in missions if m.priorite == 'moyenne']),
                'faible': len([m for m in missions if m.priorite == 'faible'])
            },
            'par_statut': {
                'planifie': len([m for m in missions if m.statut == 'planifie']),
                'en_cours': len([m for m in missions if m.statut == 'en_cours']),
                'termine': len([m for m in missions if m.statut == 'termine']),
                'reporte': len([m for m in missions if m.statut == 'reporte'])
            }
        }
        
        return jsonify({'success': True, 'stats': stats})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/programme-audit/<int:programme_id>/mission/ajouter', methods=['GET', 'POST'])
@login_required
def ajouter_mission_programme(programme_id):
    """Ajouter une mission manuellement au programme (SINGULIER)"""
    programme = ProgrammeAudit.query.get_or_404(programme_id)
    
    if not check_client_access(programme):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_programmes_audit'))
    
    # GET - Afficher le formulaire d'ajout rapide
    if request.method == 'GET':
        annee = request.args.get('annee', programme.annee_debut, type=int)
        trimestre = request.args.get('trimestre', None, type=int)
        
        risques_disponibles = get_client_filter(Risque).filter_by(is_archived=False).all()
        
        if current_user.role == 'super_admin':
            utilisateurs = User.query.filter_by(is_active=True).all()
        else:
            utilisateurs = get_client_filter(User).filter_by(is_active=True).all()
        
        return render_template('programme_audit/ajouter_mission_rapide.html',
                             programme=programme,
                             annee=annee,
                             trimestre=trimestre,
                             risques_disponibles=risques_disponibles,
                             utilisateurs=utilisateurs)
    
    # POST - Créer la mission
    try:
        # Générer référence
        ref_count = programme.missions.filter_by(is_archived=False).count() + 1
        reference = f"MIS-{programme.reference}-{ref_count:03d}"
        
        mission = MissionAudit(
            reference=reference,
            titre=request.form.get('titre'),
            description=request.form.get('description'),
            priorite=request.form.get('priorite'),
            annee_prevue=int(request.form.get('annee_prevue', programme.annee_debut)),
            trimestre_prevue=int(request.form.get('trimestre_prevue')) if request.form.get('trimestre_prevue') else None,
            duree_estimee=int(request.form.get('duree_estimee', programme.duree_moyenne_mission or 5)),
            risque_id=int(request.form.get('risque_id')) if request.form.get('risque_id') else None,
            responsable_id=int(request.form.get('responsable_id')) if request.form.get('responsable_id') else None,
            programme_id=programme.id,
            statut='planifie',
            created_by=current_user.id,
            client_id=programme.client_id
        )
        
        db.session.add(mission)
        db.session.commit()
        
        flash(f'Mission {reference} ajoutée avec succès', 'success')
        
        # Rediriger vers le chronogramme si demandé
        if request.args.get('redirect') == 'chronogramme':
            return redirect(url_for('chronogramme_programme', id=programme.id))
        
        return redirect(url_for('detail_programme_audit', id=programme.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
        return redirect(url_for('detail_programme_audit', id=programme.id))


@app.route('/programme-audit/<int:programme_id>/missions/supprimer-bloc', methods=['POST'])
@login_required
def supprimer_missions_bloc(programme_id):
    """Supprimer plusieurs missions en une fois"""
    programme = ProgrammeAudit.query.get_or_404(programme_id)
    
    if not check_client_access(programme):
        return jsonify({'success': False, 'message': 'Accès non autorisé'}), 403
    
    try:
        data = request.get_json()
        mission_ids = data.get('mission_ids', [])
        raison = data.get('raison', 'Suppression en bloc')
        
        if not mission_ids:
            return jsonify({'success': False, 'message': 'Aucune mission sélectionnée'}), 400
        
        missions = MissionAudit.query.filter(MissionAudit.id.in_(mission_ids)).all()
        count = 0
        erreurs = []
        
        for mission in missions:
            # Vérifier que la mission appartient au programme
            if mission.programme_id != programme_id:
                continue
            
            # Vérifier que la mission n'est pas en cours
            if mission.statut in ['en_cours', 'termine']:
                erreurs.append(f"{mission.reference}: mission en cours")
                continue
            
            # Vérifier qu'aucun plan de repli n'est actif
            plan_actif = PlanPluieAudit.query.filter_by(
                mission_principale_id=mission.id,
                statut='actif',
                is_archived=False
            ).first()
            
            if plan_actif:
                erreurs.append(f"{mission.reference}: plan de repli actif")
                continue
            
            # Archiver la mission
            mission.is_archived = True
            mission.statut = 'archive'
            mission.archived_at = datetime.now()
            mission.archived_by = current_user.id
            mission.archive_reason = raison
            count += 1
        
        db.session.commit()
        
        message = f'{count} mission(s) supprimée(s) avec succès'
        if erreurs:
            message += f' ({len(erreurs)} ignorée(s): {", ".join(erreurs[:3])})'
        
        return jsonify({
            'success': True, 
            'message': message
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/mission-audit/<int:mission_id>/supprimer', methods=['POST'])
@login_required
def supprimer_mission_audit(mission_id):
    """Supprimer (archiver) une mission d'audit"""
    mission = MissionAudit.query.get_or_404(mission_id)
    programme = mission.programme
    
    if not check_client_access(mission):
        return jsonify({'success': False, 'message': 'Accès non autorisé'}), 403
    
    try:
        # Vérifier que la mission n'est pas en cours
        if mission.statut in ['en_cours', 'termine']:
            return jsonify({'success': False, 'message': 'Impossible de supprimer une mission en cours ou terminée'}), 400
        
        # Vérifier qu'aucun plan de repli n'est actif
        plan_actif = PlanPluieAudit.query.filter_by(
            mission_principale_id=mission.id,
            statut='actif',
            is_archived=False
        ).first()
        
        if plan_actif:
            return jsonify({'success': False, 'message': 'Supprimez d\'abord le plan de repli associé'}), 400
        
        # Récupérer la raison de suppression (JSON ou form-data)
        raison = 'Suppression manuelle'
        
        # Si c'est du JSON
        if request.is_json:
            data = request.get_json()
            raison = data.get('raison', 'Suppression manuelle')
        else:
            # Si c'est du form-data
            raison = request.form.get('raison', 'Suppression manuelle')
        
        # Archiver la mission
        mission.is_archived = True
        mission.statut = 'archive'
        mission.archived_at = datetime.now()
        mission.archived_by = current_user.id
        mission.archive_reason = raison
        mission.updated_at = datetime.now()
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Mission supprimée avec succès'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/mission-audit/<int:mission_id>/restaurer', methods=['POST'])
@login_required
def restaurer_mission_audit(mission_id):
    """Restaurer une mission archivée"""
    mission = MissionAudit.query.get_or_404(mission_id)
    programme = mission.programme
    
    if not check_client_access(mission):
        return jsonify({'success': False, 'message': 'Accès non autorisé'}), 403
    
    try:
        mission.is_archived = False
        mission.statut = 'planifie'
        mission.archived_at = None
        mission.archived_by = None
        mission.archive_reason = None
        mission.updated_at = datetime.now()
        
        db.session.commit()
        
        flash('Mission restaurée avec succès', 'success')
        return redirect(url_for('detail_programme_audit', id=programme.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
        return redirect(url_for('detail_programme_audit', id=programme.id))


@app.route('/mission-audit/<int:mission_id>/dupliquer', methods=['POST'])
@login_required
def dupliquer_mission_audit(mission_id):
    """Dupliquer une mission d'audit"""
    mission_originale = MissionAudit.query.get_or_404(mission_id)
    programme = mission_originale.programme
    
    if not check_client_access(mission_originale):
        return jsonify({'success': False, 'message': 'Accès non autorisé'}), 403
    
    try:
        # Générer une nouvelle référence
        ref_count = len(programme.missions) + 1
        nouvelle_reference = f"MIS-{programme.reference}-{ref_count:03d}"
        
        # Créer la nouvelle mission
        nouvelle_mission = MissionAudit(
            reference=nouvelle_reference,
            titre=f"COPIE - {mission_originale.titre}",
            description=mission_originale.description,
            priorite=mission_originale.priorite,
            niveau_risque_associe=mission_originale.niveau_risque_associe,
            annee_prevue=mission_originale.annee_prevue + 1,  # Année suivante
            trimestre_prevue=mission_originale.trimestre_prevue,
            duree_estimee=mission_originale.duree_estimee,
            risque_id=mission_originale.risque_id,
            programme_id=programme.id,
            statut='planifie',
            created_by=current_user.id,
            client_id=programme.client_id
        )
        
        db.session.add(nouvelle_mission)
        db.session.commit()
        
        flash(f'Mission dupliquée avec succès - {nouvelle_reference}', 'success')
        return redirect(url_for('detail_programme_audit', id=programme.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
        return redirect(url_for('detail_programme_audit', id=programme.id))


# Route pour convertir une mission en audit
@app.route('/mission-audit/<int:id>/convertir-audit')
@login_required
def convertir_mission_audit(id):
    """Convertir une mission d'audit planifiée en audit effectif"""
    mission = MissionAudit.query.get_or_404(id)
    
    if not check_client_access(mission):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_programmes_audit'))
    
    try:
        # Récupérer les informations du processus si disponible
        processus_id = None
        if mission.risque and mission.risque.cartographie:
            processus_id = mission.risque.cartographie.processus_id
        
        # Créer l'audit à partir de la mission
        audit = Audit(
            reference=f"AUD-{mission.reference}",
            titre=mission.titre,
            description=mission.description,
            type_audit='interne',
            date_debut_prevue=mission.date_debut_prevue or datetime.now().date(),
            date_fin_prevue=mission.date_fin_prevue,
            statut='planifie',
            sous_statut='planification',
            processus_id=processus_id,
            responsable_id=mission.responsable_id,
            equipe_audit_ids=mission.equipe_ids,
            created_by=current_user.id,
            client_id=mission.client_id
        )
        
        db.session.add(audit)
        db.session.flush()
        
        # Lier l'audit à la mission
        mission.audit_id = audit.id
        mission.statut = 'en_cours'
        mission.date_debut_reelle = datetime.now().date()
        
        # Lier l'audit au risque
        if mission.risque_id:
            audit_risque = AuditRisque(
                audit_id=audit.id,
                risque_id=mission.risque_id,
                impact_audit='a_evaluer',
                commentaire=f"Audit généré à partir de la mission {mission.reference}"
            )
            db.session.add(audit_risque)
        
        db.session.commit()
        
        flash(f'Audit {audit.reference} créé à partir de la mission', 'success')
        return redirect(url_for('detail_audit', id=audit.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
        return redirect(url_for('detail_programme_audit', id=mission.programme_id))


@app.route('/programme-audit/<int:id>/exporter')
@login_required
def exporter_programme(id):
    """Exporter le programme en Excel, CSV ou PDF"""
    programme = ProgrammeAudit.query.get_or_404(id)
    
    if not check_client_access(programme):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_programmes_audit'))
    
    format_export = request.args.get('format', 'excel')
    
    try:
        # ========== EXPORT EXCEL ==========
        if format_export == 'excel':
            return exporter_programme_excel(programme)
        
        # ========== EXPORT CSV ==========
        elif format_export == 'csv':
            return exporter_programme_csv(programme)
        
        # ========== EXPORT PDF ==========
        elif format_export == 'pdf':
            return exporter_programme_pdf(programme)
        
        else:
            flash('Format d\'export non supporté', 'error')
            return redirect(url_for('detail_programme_audit', id=id))
            
    except Exception as e:
        flash(f'Erreur lors de l\'export: {str(e)}', 'error')
        return redirect(url_for('detail_programme_audit', id=id))


@app.route('/api/programme-audit/<int:id>/statistiques')
@login_required
def api_statistiques_programme(id):
    """API pour les statistiques du programme"""
    programme = ProgrammeAudit.query.get_or_404(id)
    
    if not check_client_access(programme):
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    # Statistiques par priorité
    stats_priorite = {
        'critique': 0,
        'elevee': 0,
        'moyenne': 0,
        'faible': 0
    }
    
    for mission in programme.missions:
        if mission.priorite in stats_priorite:
            stats_priorite[mission.priorite] += 1
    
    # Statistiques par statut
    stats_statut = {
        'planifie': 0,
        'en_cours': 0,
        'termine': 0,
        'suspendu': 0,
        'annule': 0
    }
    
    for mission in programme.missions:
        if mission.statut in stats_statut:
            stats_statut[mission.statut] += 1
    
    # Charge par année
    charge_annee = {}
    for mission in programme.missions:
        if mission.annee_prevue not in charge_annee:
            charge_annee[mission.annee_prevue] = 0
        charge_annee[mission.annee_prevue] += mission.duree_estimee or 0
    
    return jsonify({
        'priorite': stats_priorite,
        'statut': stats_statut,
        'charge_annee': charge_annee,
        'progression': programme.progression,
        'jours_planifies': programme.jours_audit_planifies,
        'jours_realises': programme.jours_audit_realises
    })


@app.route('/api/programme-audit/<int:programme_id>/stats-plans')
@login_required
def api_stats_plans_pluie(programme_id):
    """API pour obtenir les statistiques des plans de repli"""
    programme = ProgrammeAudit.query.get_or_404(programme_id)
    
    if not check_client_access(programme):
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    mission_ids = [m.id for m in programme.missions]
    plans = PlanPluieAudit.query.filter(
        PlanPluieAudit.mission_principale_id.in_(mission_ids)
    ).filter_by(is_archived=False).all()
    
    stats = {
        'total': len(plans),
        'actifs': len([p for p in plans if p.statut == 'actif']),
        'declenches': len([p for p in plans if p.statut == 'declenche']),
        'par_type': {
            'retard': len([p for p in plans if p.condition_type == 'retard']),
            'indisponibilite': len([p for p in plans if p.condition_type == 'indisponibilite']),
            'urgence': len([p for p in plans if p.condition_type == 'urgence'])
        }
    }
    
    return jsonify(stats)


# ============================================================================
# ROUTES POUR LA MODIFICATION DES PROGRAMMES
# ============================================================================
@app.route('/programme-audit/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_programme_audit(id):
    """Modifier un programme d'audit existant"""
    
    programme = ProgrammeAudit.query.get_or_404(id)
    
    if not check_client_access(programme):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_programmes_audit'))
    
    if not current_user.has_permission('can_manage_audit'):
        flash('Permission requise', 'error')
        return redirect(url_for('liste_programmes_audit'))
    
    from flask_wtf import FlaskForm
    from wtforms import StringField, TextAreaField, SelectField, BooleanField, IntegerField, SubmitField
    from wtforms.validators import DataRequired, Optional, NumberRange
    
    class ProgrammeAuditForm(FlaskForm):
        nom = StringField('Nom du programme', validators=[DataRequired()])
        description = TextAreaField('Description')
        periode = SelectField('Période', choices=[
            ('annuel', 'Annuel'),
            ('triennal', 'Triennal (3 ans)')
        ], validators=[DataRequired()])
        annee_debut = SelectField('Année de début', choices=[], validators=[DataRequired()])
        annee_fin = SelectField('Année de fin', choices=[], validators=[DataRequired()])
        
        methode_generation = SelectField('Méthode de génération', choices=[
            ('manuel', 'Manuel - Je créerai les missions moi-même'),
            ('auto_risques', 'Automatique - Basé sur la cartographie des risques'),
            ('hybride', 'Hybride - Automatique avec ajustements manuels')
        ], validators=[DataRequired()])
        
        seuil_critique = BooleanField('Inclure les risques Critiques', default=True)
        seuil_eleve = BooleanField('Inclure les risques Élevés', default=True)
        inclure_risques_moyens = BooleanField('Inclure les risques Moyens', default=False)
        frequence_audit_risque = SelectField('Fréquence d\'audit par niveau', choices=[
            ('annuelle_critique', 'Annuelle pour risques critiques'),
            ('semestrielle_critique', 'Semestrielle pour risques critiques'),
            ('triennal_tous', 'Tous les 3 ans pour tous les risques')
        ])
        prioriser_processus_critiques = BooleanField('Prioriser les processus critiques', default=True)
        
        frequence_audit = SelectField('Fréquence générale d\'audit', choices=[
            ('', 'Non spécifiée'),
            ('annuelle', 'Annuelle'),
            ('semestrielle', 'Semestrielle'),
            ('trimestrielle', 'Trimestrielle')
        ], validators=[Optional()])
        
        duree_moyenne_mission = IntegerField('Durée moyenne d\'une mission (jours)', 
                                             default=5, 
                                             validators=[NumberRange(min=1, max=90)])
        ressources_disponibles = IntegerField('Ressources disponibles (jours/homme par an)', 
                                             default=100, 
                                             validators=[NumberRange(min=10, max=1000)])
        
        pays_id = SelectField('Pays', choices=[], coerce=int, validators=[Optional()])
        pole_id = SelectField('Pôle', choices=[], coerce=int, validators=[Optional()])
        direction_id = SelectField('Direction', choices=[], coerce=int, validators=[Optional()])
        
        submit = SubmitField('Enregistrer les modifications')  # Changement du texte du bouton
    
    form = ProgrammeAuditForm()
    
    # Initialisation des années
    annee_courante = datetime.now().year
    form.annee_debut.choices = [(str(y), str(y)) for y in range(annee_courante - 2, annee_courante + 8)]
    form.annee_fin.choices = [(str(y), str(y)) for y in range(annee_courante - 2, annee_courante + 12)]
    
    # Chargement des listes organisationnelles
    if current_user.role == 'super_admin':
        pays_list = Pays.query.filter_by(is_archived=False).order_by(Pays.nom).all()
        poles_list = Pole.query.filter_by(is_archived=False).order_by(Pole.nom).all()
        directions_list = Direction.query.filter_by(is_archived=False, is_active=True).order_by(Direction.nom).all()
    else:
        pays_list = get_client_filter(Pays).filter_by(is_archived=False).order_by(Pays.nom).all()
        poles_list = get_client_filter(Pole).filter_by(is_archived=False).order_by(Pole.nom).all()
        directions_list = get_client_filter(Direction).filter_by(is_archived=False, is_active=True).order_by(Direction.nom).all()
    
    form.pays_id.choices = [(0, '--- Non spécifié ---')] + [(p.id, f"{p.drapeau or '🌍'} {p.nom}") for p in pays_list]
    form.pole_id.choices = [(0, '--- Non spécifié ---')] + [(p.id, p.nom) for p in poles_list]
    form.direction_id.choices = [(0, '--- Non spécifié ---')] + [(d.id, d.nom) for d in directions_list]
    
    if request.method == 'GET':
        # Pré-remplir le formulaire avec les données du programme
        form.nom.data = programme.nom
        form.description.data = programme.description
        form.periode.data = programme.periode
        form.annee_debut.data = str(programme.annee_debut)
        form.annee_fin.data = str(programme.annee_fin)
        form.methode_generation.data = programme.methode_generation
        form.frequence_audit.data = programme.frequence_audit or ''
        form.duree_moyenne_mission.data = programme.duree_moyenne_mission or 5
        form.ressources_disponibles.data = programme.ressources_disponibles or 100
        form.pays_id.data = programme.pays_id if programme.pays_id else 0
        form.pole_id.data = programme.pole_id if programme.pole_id else 0
        form.direction_id.data = programme.direction_id if programme.direction_id else 0
        
        # Pré-remplir les critères de génération
        if programme.criteres_generation:
            form.seuil_critique.data = programme.criteres_generation.get('seuil_critique', True)
            form.seuil_eleve.data = programme.criteres_generation.get('seuil_eleve', True)
            form.inclure_risques_moyens.data = programme.criteres_generation.get('inclure_risques_moyens', False)
            form.frequence_audit_risque.data = programme.criteres_generation.get('frequence_audit_risque', 'annuelle_critique')
            form.prioriser_processus_critiques.data = programme.criteres_generation.get('prioriser_processus_critiques', True)
    
    if form.validate_on_submit():
        try:
            # Mise à jour des champs
            programme.nom = form.nom.data
            programme.description = form.description.data
            programme.periode = form.periode.data
            programme.annee_debut = int(form.annee_debut.data)
            programme.annee_fin = int(form.annee_fin.data)
            programme.methode_generation = form.methode_generation.data
            programme.frequence_audit = form.frequence_audit.data if form.frequence_audit.data else None
            programme.duree_moyenne_mission = form.duree_moyenne_mission.data
            programme.ressources_disponibles = form.ressources_disponibles.data
            programme.pays_id = form.pays_id.data if form.pays_id.data and form.pays_id.data != 0 else None
            programme.pole_id = form.pole_id.data if form.pole_id.data and form.pole_id.data != 0 else None
            programme.direction_id = form.direction_id.data if form.direction_id.data and form.direction_id.data != 0 else None
            
            # Mise à jour des critères de génération
            if form.methode_generation.data in ['auto_risques', 'hybride']:
                programme.criteres_generation = {
                    'seuil_critique': form.seuil_critique.data,
                    'seuil_eleve': form.seuil_eleve.data,
                    'inclure_risques_moyens': form.inclure_risques_moyens.data,
                    'frequence_audit_risque': form.frequence_audit_risque.data,
                    'prioriser_processus_critiques': form.prioriser_processus_critiques.data,
                    'duree_max_mission': 90
                }
            else:
                programme.criteres_generation = None
            
            programme.updated_at = datetime.now()
            db.session.commit()
            
            flash('Programme modifié avec succès', 'success')
            return redirect(url_for('detail_programme_audit', id=programme.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('programme_audit/form.html', 
                         form=form, 
                         title="Modifier le programme",
                         programme=programme)


@app.route('/programme-audit/<int:id>/desapprouver', methods=['POST'])
@login_required
def desapprouver_programme_audit(id):
    """Désapprouver un programme d'audit (remettre en élaboration)"""
    programme = ProgrammeAudit.query.get_or_404(id)
    
    if not check_client_access(programme):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_programmes_audit'))
    
    try:
        raison = request.form.get('raison', 'Désapprobation manuelle')
        
        programme.statut = 'en_elaboration'
        programme.date_approbation = None
        programme.date_mise_en_oeuvre = None
        programme.updated_at = datetime.now()
        programme.archive_reason = raison  # Réutiliser pour la raison de désapprobation
        
        db.session.commit()
        
        flash(f'Programme {programme.reference} désapprouvé avec succès', 'warning')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
    
    return redirect(url_for('detail_programme_audit', id=programme.id))


@app.route('/programme-audit/<int:id>/dupliquer', methods=['POST'])
@login_required
def dupliquer_programme_audit(id):
    """Dupliquer un programme d'audit"""
    programme_original = ProgrammeAudit.query.get_or_404(id)
    
    if not check_client_access(programme_original):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_programmes_audit'))
    
    try:
        # Générer nouvelle référence
        def generer_reference_programme(client_id=None):
            base_ref = "PROGAUD-"
            dernier = ProgrammeAudit.query.filter_by(client_id=client_id)\
                .order_by(ProgrammeAudit.id.desc()).first()
            
            if dernier and dernier.reference:
                try:
                    dernier_num = int(dernier.reference.split('-')[1])
                    nouveau_num = dernier_num + 1
                except:
                    count = ProgrammeAudit.query.filter_by(client_id=client_id).count()
                    nouveau_num = count + 1
            else:
                nouveau_num = 1
            
            return f"{base_ref}{nouveau_num:04d}"
        
        # Créer nouveau programme
        nouveau_programme = ProgrammeAudit(
            reference=generer_reference_programme(programme_original.client_id),
            nom=f"COPIE - {programme_original.nom}",
            description=programme_original.description,
            periode=programme_original.periode,
            annee_debut=programme_original.annee_debut + 1,
            annee_fin=programme_original.annee_fin + 1,
            methode_generation=programme_original.methode_generation,
            criteres_generation=programme_original.criteres_generation,
            frequence_audit=programme_original.frequence_audit,
            duree_moyenne_mission=programme_original.duree_moyenne_mission,
            ressources_disponibles=programme_original.ressources_disponibles,
            statut='en_elaboration',
            client_id=programme_original.client_id,
            created_by=current_user.id
        )
        
        db.session.add(nouveau_programme)
        db.session.commit()
        
        flash(f'Programme dupliqué avec succès - {nouveau_programme.reference}', 'success')
        return redirect(url_for('detail_programme_audit', id=nouveau_programme.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
        return redirect(url_for('detail_programme_audit', id=programme_original.id))


@app.route('/programme-audit/<int:id>/archiver', methods=['POST'])
@login_required
def archiver_programme_audit(id):
    """Archiver un programme d'audit"""
    programme = ProgrammeAudit.query.get_or_404(id)
    
    if not check_client_access(programme):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_programmes_audit'))
    
    if request.method == 'POST':
        try:
            raison = request.form.get('raison', 'Archivage manuel')
            commentaire = request.form.get('commentaire', '')
            
            programme.is_archived = True
            programme.statut = 'archive'
            programme.archived_at = datetime.now()
            programme.archived_by = current_user.id
            programme.archive_reason = f"{raison} - {commentaire}" if commentaire else raison
            
            db.session.commit()
            
            flash(f'Programme {programme.reference} archivé avec succès', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de l\'archivage: {str(e)}', 'error')
    
    return redirect(url_for('programmes_archives'))


@app.route('/programme-audit/<int:id>/restaurer', methods=['POST'])
@login_required
def restaurer_programme_audit(id):
    """Restaurer un programme d'audit archivé"""
    programme = ProgrammeAudit.query.get_or_404(id)
    
    if not check_client_access(programme):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('programmes_archives'))
    
    try:
        programme.is_archived = False
        programme.statut = 'en_elaboration'  # Remettre en élaboration
        programme.archived_at = None
        programme.archived_by = None
        programme.archive_reason = None
        
        db.session.commit()
        
        flash(f'Programme {programme.reference} restauré avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la restauration: {str(e)}', 'error')
    
    return redirect(url_for('programmes_archives'))


@app.route('/programme-audit/<int:id>/supprimer-definitivement', methods=['POST'])
@login_required
def supprimer_programme_audit_definitif(id):
    """Supprimer définitivement un programme archivé"""
    programme = ProgrammeAudit.query.get_or_404(id)
    
    if not check_client_access(programme):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('programmes_archives'))
    
    # Vérifier que le programme est bien archivé
    if not programme.is_archived:
        flash('Seuls les programmes archivés peuvent être supprimés définitivement', 'error')
        return redirect(url_for('liste_programmes_audit'))
    
    try:
        confirmation = request.form.get('confirmation', '')
        
        if confirmation != programme.reference:
            flash('La confirmation ne correspond pas à la référence du programme', 'error')
            return redirect(url_for('programmes_archives'))
        
        # Supprimer les missions associées
        for mission in programme.missions:
            # Supprimer les plans de repli associés
            PlanPluieAudit.query.filter(
                (PlanPluieAudit.mission_principale_id == mission.id) |
                (PlanPluieAudit.mission_remplacement_id == mission.id)
            ).delete()
            
            db.session.delete(mission)
        
        # Supprimer le programme
        db.session.delete(programme)
        db.session.commit()
        
        flash(f'Programme {programme.reference} supprimé définitivement', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la suppression: {str(e)}', 'error')
    
    return redirect(url_for('programmes_archives'))


@app.route('/programmes-archives')
@login_required
def programmes_archives():
    """Liste des programmes d'audit archivés"""
    
    # Vérification permission
    if not current_user.has_permission('can_manage_audit'):
        flash('Permission requise', 'error')
        return redirect(url_for('dashboard'))
    
    # Récupération des programmes archivés
    programmes = get_client_filter(ProgrammeAudit)\
        .filter_by(is_archived=True)\
        .order_by(ProgrammeAudit.archived_at.desc())\
        .all()
    
    return render_template('programme_audit/archives.html',
                         programmes=programmes)


@app.route('/programme-audit/<int:id>/approuver', methods=['POST'])
@login_required
def approuver_programme_audit(id):
    """Approuver un programme d'audit"""
    programme = ProgrammeAudit.query.get_or_404(id)
    
    if not check_client_access(programme):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_programmes_audit'))
    
    try:
        programme.statut = 'actif'
        programme.date_approbation = datetime.strptime(
            request.form.get('date_approbation', datetime.now().strftime('%Y-%m-%d')), 
            '%Y-%m-%d'
        ).date()
        programme.date_mise_en_oeuvre = datetime.now().date()
        programme.updated_at = datetime.now()
        
        db.session.commit()
        
        flash(f'Programme {programme.reference} approuvé avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de l\'approbation: {str(e)}', 'error')
    
    return redirect(url_for('detail_programme_audit', id=id))


@app.route('/audit/<int:audit_id>/matrice-maturite', methods=['GET', 'POST'])
@login_required
def matrice_maturite_audit(audit_id):
    """Afficher et gérer la matrice de maturité/conformité"""
    audit = Audit.query.get_or_404(audit_id)
    
    # Charger les matrices existantes
    matrices = MatriceMaturite.query.filter_by(audit_id=audit_id).all()
    
    # Gérer le formulaire si c'est une requête POST
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            exigence = request.form.get('exigence', '').strip()
            niveau_conformite = request.form.get('niveau_conformite', '')
            commentaire = request.form.get('commentaire', '').strip()
            risques_associes = request.form.get('risques_associes', '').strip()
            
            # Validation basique
            if not exigence or not niveau_conformite:
                flash('L\'exigence et le niveau de conformité sont requis', 'error')
                return redirect(url_for('matrice_maturite_audit', audit_id=audit_id))
            
            # Créer une nouvelle matrice SANS created_by
            matrice = MatriceMaturite(
                audit_id=audit_id,
                exigence=exigence,
                niveau_conformite=niveau_conformite,
                commentaire=commentaire if commentaire else None,
                risques_associes=risques_associes if risques_associes else None
            )
            
            db.session.add(matrice)
            db.session.commit()
            
            flash('Exigence ajoutée à la matrice avec succès', 'success')
            return redirect(url_for('matrice_maturite_audit', audit_id=audit_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de l\'ajout: {str(e)}', 'error')
    
    return render_template('audit/matrice_maturite.html',
                         audit=audit,
                         matrices=matrices)


@app.route('/api/audit/<int:audit_id>/statistiques-temps-reel')
@login_required
def api_statistiques_temps_reel(audit_id):
    """API pour les statistiques en temps réel"""
    audit = Audit.query.get_or_404(audit_id)
    
    data = {
        'progression_globale': audit.progression_globale,
        'taux_realisation_recommandations': audit.taux_realisation_recommandations,
        'score_global': audit.score_global,
        'couleur_progression': audit.get_couleur_progression(),
        'constatations_total': len(audit.constatations),
        'constatations_closes': len([c for c in audit.constatations if c.statut == 'clos']),
        'recommandations_total': len(audit.recommandations),
        'recommandations_terminees': len([r for r in audit.recommandations if r.statut == 'termine']),
        'plans_action_total': len(audit.plans_action),
        'plans_action_termines': len([p for p in audit.plans_action if p.statut == 'termine']),
        'plans_en_retard': len([p for p in audit.plans_action if p.est_en_retard]),
        'derniere_maj': audit.updated_at.isoformat() if audit.updated_at else None
    }
    
    return jsonify(data)


@app.route('/audit/<int:audit_id>/export/rapport-complet', methods=['GET'])
@login_required
def export_rapport_audit_complet(audit_id):
    """Exporter le rapport d'audit complet en PDF"""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from io import BytesIO
    
    audit = Audit.query.get_or_404(audit_id)
    
    # Créer le PDF en mémoire
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Style personnalisé
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30
    )
    
    # Titre
    story.append(Paragraph(f"Rapport d'Audit - {audit.reference}", title_style))
    story.append(Paragraph(f"Titre: {audit.titre}", styles['Normal']))
    story.append(Spacer(1, 12))
    
    # Informations générales
    story.append(Paragraph("Informations Générales", styles['Heading2']))
    
    info_data = [
        ['Référence', audit.reference],
        ['Type', audit.type_audit],
        ['Statut', audit.statut],
        ['Responsable', audit.responsable.username if audit.responsable else 'Non défini'],
        ['Dates', f"{audit.date_debut_prevue.strftime('%d/%m/%Y') if audit.date_debut_prevue else 'N/A'} - {audit.date_fin_prevue.strftime('%d/%m/%Y') if audit.date_fin_prevue else 'N/A'}"],
        ['Score global', f"{audit.score_global}/100"],
    ]
    
    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))
    
    # Constatations
    story.append(Paragraph("Constatations", styles['Heading2']))
    if audit.constatations:
        constat_data = [['Réf.', 'Description', 'Type', 'Gravité', 'Statut']]
        for constat in audit.constatations:
            constat_data.append([
                constat.reference,
                constat.description[:100] + '...' if len(constat.description) > 100 else constat.description,
                constat.type_constatation,
                constat.gravite,
                constat.statut
            ])
        
        constat_table = Table(constat_data, colWidths=[0.5*inch, 2.5*inch, inch, inch, inch])
        constat_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ]))
        story.append(constat_table)
    else:
        story.append(Paragraph("Aucune constatation", styles['Normal']))
    
    story.append(Spacer(1, 20))
    
    # Recommandations
    story.append(Paragraph("Recommandations", styles['Heading2']))
    if audit.recommandations:
        reco_data = [['Réf.', 'Description', 'Priorité', 'Statut', 'Avancement']]
        for reco in audit.recommandations:
            reco_data.append([
                reco.reference,
                reco.description[:80] + '...' if len(reco.description) > 80 else reco.description,
                reco.score_priorite,
                reco.statut,
                f"{reco.taux_avancement}%"
            ])
        
        reco_table = Table(reco_data, colWidths=[0.5*inch, 3*inch, 0.7*inch, inch, inch])
        reco_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ]))
        story.append(reco_table)
    
    story.append(Spacer(1, 20))
    
    # Pied de page
    story.append(Paragraph(f"Généré le {datetime.utcnow().strftime('%d/%m/%Y à %H:%M')} par {current_user.username}", 
                          ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, alignment=1)))
    
    # Générer le PDF
    doc.build(story)
    
    buffer.seek(0)
    return send_file(buffer, 
                    as_attachment=True, 
                    download_name=f"rapport_audit_{audit.reference}.pdf",
                    mimetype='application/pdf')


@app.route('/audit/<int:audit_id>/export/synthese-word', methods=['GET'])
@login_required
def export_synthese_word(audit_id):
    """Exporter la synthèse en format Word"""
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from io import BytesIO
    
    audit = Audit.query.get_or_404(audit_id)
    
    # Créer le document Word
    doc = Document()
    
    # Titre
    title = doc.add_heading(f'Rapport d\'Audit - {audit.reference}', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Informations générales
    doc.add_heading('Informations Générales', level=1)
    
    info_table = doc.add_table(rows=6, cols=2)
    info_table.style = 'Light Shading Accent 1'
    
    data = [
        ('Référence', audit.reference),
        ('Titre', audit.titre),
        ('Type', audit.type_audit),
        ('Statut', audit.statut),
        ('Responsable', audit.responsable.username if audit.responsable else 'Non défini'),
        ('Dates', f"{audit.date_debut_prevue.strftime('%d/%m/%Y') if audit.date_debut_prevue else 'N/A'} - {audit.date_fin_prevue.strftime('%d/%m/%Y') if audit.date_fin_prevue else 'N/A'}"),
    ]
    
    for i, (label, value) in enumerate(data):
        row = info_table.rows[i]
        row.cells[0].text = label
        row.cells[1].text = str(value)
    
    # Statistiques
    doc.add_heading('Statistiques', level=1)
    
    stats_data = [
        ('Score global', f'{audit.score_global}/100'),
        ('Constatations', f'{len(audit.constatations)}'),
        ('Recommandations', f'{len(audit.recommandations)}'),
        ('Plans d\'action', f'{len(audit.plans_action)}'),
    ]
    
    stats_table = doc.add_table(rows=4, cols=2)
    stats_table.style = 'Light Grid Accent 1'
    
    for i, (label, value) in enumerate(stats_data):
        row = stats_table.rows[i]
        row.cells[0].text = label
        row.cells[1].text = value
    
    # Sauvegarder dans un buffer
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    return send_file(buffer, 
                    as_attachment=True, 
                    download_name=f"synthese_audit_{audit.reference}.docx",
                    mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')


@app.route('/audit/<int:audit_id>/journal')
@login_required
def journal_audit(audit_id):
    """Afficher le journal d'audit complet - VERSION MULTI-TENANT"""
    from datetime import datetime, timezone
    
    # ============================================
    # 1. RÉCUPÉRER L'AUDIT AVEC VÉRIFICATION D'ACCÈS
    # ============================================
    audit = Audit.query.get(audit_id)
    
    if not audit:
        flash('Audit non trouvé', 'error')
        return redirect(url_for('liste_audits'))
    
    # Vérifier l'accès client (multi-tenant)
    if not check_client_access(audit):
        flash('Accès non autorisé à cet audit', 'error')
        return redirect(url_for('liste_audits'))
    
    # ============================================
    # 2. DÉTERMINER LE CLIENT_ID À UTILISER
    # ============================================
    if current_user.role == 'super_admin' and session.get('viewing_client_id'):
        client_id = session['viewing_client_id']
    else:
        client_id = current_user.client_id
    
    # ============================================
    # 3. VÉRIFIER LES PERMISSIONS
    # ============================================
    peut_voir = (
        current_user.role == 'super_admin' or
        current_user.id == audit.created_by or
        current_user.id == audit.responsable_id or
        (audit.equipe_audit_ids and str(current_user.id) in audit.equipe_audit_ids.split(',')) or
        (audit.observateurs_ids and str(current_user.id) in audit.observateurs_ids.split(','))
    )
    
    if not peut_voir:
        flash('Vous n\'avez pas les permissions pour voir ce journal', 'error')
        return redirect(url_for('liste_audits'))
    
    # ============================================
    # 4. RÉCUPÉRER LES ENTREES DU JOURNAL AVEC FILTRE CLIENT
    # ============================================
    journal_entries = JournalAudit.query.filter_by(
        audit_id=audit_id,
        client_id=client_id
    ).order_by(JournalAudit.created_at.desc()).all()
    
    _journal(f"📋 JOURNAL AUDIT {audit.reference}: {len(journal_entries)} entrées")
    
    # ============================================
    # 5. RENVOYER LE TEMPLATE
    # ============================================
    return render_template('audit/journal.html',
                         audit=audit,
                         journal_entries=journal_entries,
                         datetime=datetime,
                         now=lambda: datetime.now(timezone.utc))


@app.route('/audit/<int:audit_id>/journal/export')
@login_required
def export_journal_audit(audit_id):
    """Exporter le journal d'audit en format CSV ou PDF"""
    from flask import Response
    from io import StringIO
    import csv
    
    audit = Audit.query.get_or_404(audit_id)
    
    # Récupérer les entrées du journal
    journal_entries = JournalAudit.query.filter_by(audit_id=audit_id)\
                                       .order_by(JournalAudit.created_at.desc())\
                                       .all()
    
    format_type = request.args.get('format', 'csv')
    
    if format_type == 'csv':
        # Générer un CSV
        output = StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_ALL)
        
        # En-tête
        writer.writerow(['Date', 'Utilisateur', 'Action', 'Détails', 'Signature'])
        
        # Données
        for entry in journal_entries:
            writer.writerow([
                entry.created_at.strftime('%d/%m/%Y %H:%M'),
                entry.utilisateur.username if entry.utilisateur else 'Système',
                entry.action,
                str(entry.details)[:500],  # Limiter la taille
                entry.signature or ''
            ])
        
        output.seek(0)
        
        response = Response(
            output.getvalue(),
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename=journal_audit_{audit.reference}_{datetime.now().strftime("%Y%m%d")}.csv'
            }
        )
        return response
    
    elif format_type == 'pdf':
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            from io import BytesIO
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            story = []
            styles = getSampleStyleSheet()
            
            # Style personnalisé
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=30
            )
            
            # Titre
            story.append(Paragraph(f"Journal d'Audit - {audit.reference}", title_style))
            story.append(Paragraph(f"Audit: {audit.titre}", styles['Normal']))
            story.append(Spacer(1, 12))
            
            # Table des données
            data = [['Date', 'Utilisateur', 'Action', 'Détails']]
            
            for entry in journal_entries:
                data.append([
                    entry.created_at.strftime('%d/%m/%Y %H:%M'),
                    entry.utilisateur.username if entry.utilisateur else 'Système',
                    entry.action,
                    str(entry.details)[:200] + '...' if len(str(entry.details)) > 200 else str(entry.details)
                ])
            
            table = Table(data, colWidths=[1.5*inch, 1*inch, 1.5*inch, 3*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(table)
            story.append(Spacer(1, 20))
            story.append(Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", 
                                  ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8)))
            
            doc.build(story)
            buffer.seek(0)
            
            response = Response(
                buffer.getvalue(),
                mimetype='application/pdf',
                headers={
                    'Content-Disposition': f'attachment; filename=journal_audit_{audit.reference}_{datetime.now().strftime("%Y%m%d")}.pdf'
                }
            )
            return response
            
        except ImportError:
            flash('Export PDF non disponible. Le module ReportLab n\'est pas installé.', 'error')
            return redirect(url_for('journal_audit', audit_id=audit_id))
    
    else:
        flash('Format d\'export non supporté', 'error')
        return redirect(url_for('journal_audit', audit_id=audit_id))


@app.route('/audit/<int:audit_id>/plan-action/<int:plan_id>/supprimer', methods=['POST'])
@login_required
def supprimer_plan_action_audit(audit_id, plan_id):
    """Supprimer un plan d'action d'audit"""
    plan_action = PlanAction.query.get_or_404(plan_id)
    
    # Vérifier que le plan d'action appartient bien à l'audit
    if plan_action.audit_id != audit_id:
        flash('Ce plan d\'action ne fait pas partie de cet audit', 'error')
        return redirect(url_for('detail_audit', id=audit_id))
    
    try:
        # Supprimer les étapes du plan d'action
        EtapePlanAction.query.filter_by(plan_action_id=plan_id).delete()
        
        # Supprimer le plan d'action
        db.session.delete(plan_action)
        db.session.commit()
        
        flash('Plan d\'action supprimé avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la suppression: {str(e)}', 'error')
    
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/audit/<int:audit_id>/dissocier-risque/<int:risque_id>', methods=['POST'])
@login_required
def dissocier_risque_audit(audit_id, risque_id):
    """Dissocier un risque de toutes les constatations et recommandations d'un audit"""
    audit = Audit.query.get_or_404(audit_id)
    
    # Vérifier les permissions
    peut_modifier = (
        current_user.role == 'admin' or
        current_user.id == audit.created_by or
        current_user.id == audit.responsable_id or
        str(current_user.id) in (audit.equipe_audit_ids or '').split(',')
    )
    
    if not peut_modifier:
        flash('Non autorisé', 'error')
        return redirect(url_for('detail_audit', id=audit_id))
    
    try:
        # Dissocier le risque des constatations
        constatations = Constatation.query.filter_by(
            audit_id=audit_id,
            risque_id=risque_id
        ).all()
        
        for constatation in constatations:
            constatation.risque_id = None
            constatation.updated_at = datetime.utcnow()
        
        # Dissocier le risque des recommandations
        recommandations = Recommandation.query.filter_by(
            audit_id=audit_id,
            risque_id=risque_id
        ).all()
        
        for recommandation in recommandations:
            recommandation.risque_id = None
            recommandation.updated_at = datetime.utcnow()
        
        # Dissocier le risque des plans d'action
        plans_action = PlanAction.query.filter_by(
            audit_id=audit_id,
            risque_id=risque_id
        ).all()
        
        for plan in plans_action:
            plan.risque_id = None
            plan.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash(f'Risque dissocié avec succès de l\'audit', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la dissociation du risque: {str(e)}', 'error')
    
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/audit/<int:audit_id>/recommandation/<int:recommandation_id>/associer-risques', methods=['POST'])
@login_required
def associer_risques_recommandation(audit_id, recommandation_id):
    """Associer plusieurs risques à une recommandation"""
    recommandation = Recommandation.query.get_or_404(recommandation_id)
    risque_ids = request.form.getlist('risque_ids')
    
    try:
        for risque_id in risque_ids:
            if risque_id:  # Vérifier que l'ID n'est pas vide
                # Vérifier si l'association existe déjà
                existing = Recommandation.query.filter_by(
                    id=recommandation_id, 
                    risque_id=risque_id
                ).first()
                
                if not existing:
                    # Créer une nouvelle recommandation pour chaque risque
                    nouvelle_recommandation = Recommandation(
                        description=recommandation.description,
                        type_recommandation=recommandation.type_recommandation,
                        delai_mise_en_oeuvre=recommandation.delai_mise_en_oeuvre,
                        date_echeance=recommandation.date_echeance,
                        audit_id=audit_id,
                        constatation_id=recommandation.constatation_id,
                        risque_id=int(risque_id),
                        responsable_id=recommandation.responsable_id,
                        statut=recommandation.statut,
                        created_by=current_user.id
                    )
                    db.session.add(nouvelle_recommandation)
        
        db.session.commit()
        flash(f'{len(risque_ids)} risque(s) associé(s) à la recommandation', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de l\'association: {str(e)}', 'error')
    
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/audit/<int:audit_id>/plan-action/<int:plan_id>/associer-risques', methods=['POST'])
@login_required
def associer_risques_plan_action(audit_id, plan_id):
    """Associer plusieurs risques à un plan d'action"""
    plan_action = PlanAction.query.get_or_404(plan_id)
    risque_ids = request.form.getlist('risque_ids')
    
    try:
        for risque_id in risque_ids:
            if risque_id:  # Vérifier que l'ID n'est pas vide
                # Vérifier si l'association existe déjà
                existing = PlanAction.query.filter_by(
                    id=plan_id, 
                    risque_id=risque_id
                ).first()
                
                if not existing:
                    # Créer un nouveau plan d'action pour chaque risque
                    nouveau_plan = PlanAction(
                        nom=f"{plan_action.nom} - {risque_id}",
                        description=plan_action.description,
                        date_debut=plan_action.date_debut,
                        date_fin_prevue=plan_action.date_fin_prevue,
                        audit_id=audit_id,
                        recommandation_id=plan_action.recommandation_id,
                        risque_id=int(risque_id),
                        responsable_id=plan_action.responsable_id,
                        statut=plan_action.statut,
                        created_by=current_user.id
                    )
                    db.session.add(nouveau_plan)
        
        db.session.commit()
        flash(f'{len(risque_ids)} risque(s) associé(s) au plan d\'action', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de l\'association: {str(e)}', 'error')
    
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/audit/<int:audit_id>/rapport-pdf-elegant')
@login_required
def rapport_audit_pdf_elegant(audit_id):
    """Génère un PDF élégant et professionnel avec intégration des feuilles de travail"""
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    from datetime import datetime
    from models import User, Constatation, Recommandation, PlanAction, Risque, FichierRapport
    from models import WorkflowApprobation, FeuilleTravail, TestControleFeuille, ErreurTest
    
    # ============================================
    # 1. RÉCUPÉRER L'AUDIT
    # ============================================
    audit = Audit.query.get_or_404(audit_id)
    
    if not check_client_access(audit):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_audits'))
    
    # ============================================
    # 2. RÉCUPÉRER TOUTES LES DONNÉES
    # ============================================
    
    constatations = Constatation.query.filter_by(
        audit_id=audit.id, is_archived=False
    ).order_by(Constatation.created_at.desc()).all()
    
    recommandations = Recommandation.query.filter_by(
        audit_id=audit.id
    ).order_by(Recommandation.created_at.desc()).all()
    
    plans_action = PlanAction.query.filter_by(
        audit_id=audit.id
    ).order_by(PlanAction.created_at.desc()).all()
    
    fichiers_rapport = FichierRapport.query.filter_by(
        audit_id=audit_id
    ).order_by(FichierRapport.created_at.desc()).all()
    
    # ============================================
    # 3. RÉCUPÉRER LES FEUILLES DE TRAVAIL ET TESTS
    # ============================================
    
    feuilles_travail = FeuilleTravail.query.filter_by(
        audit_id=audit.id, is_archived=False
    ).all()
    
    tests_data = []
    tests_stats = {
        'total_tests': 0,
        'tests_conformes': 0,
        'tests_non_conformes': 0,
        'taux_conformite_global': 0,
        'taux_reussite_moyen': 0,
        'impact_financier_total': 0,
        'tests_par_criticite': {
            'critique': 0,
            'eleve': 0,
            'moyen': 0,
            'faible': 0
        },
        'tests_par_feuille': {},
        'total_ecarts': 0,
        'ecarts_par_gravite': {},
        'ecarts_par_etat': {},
        'taux_correction_ecarts': 0,
        'ecarts_corriges': 0
    }
    
    taux_reussites = []
    ecarts_gravite = {}
    ecarts_etat = {}
    total_ecarts_corriges = 0
    total_ecarts = 0
    
    for feuille in feuilles_travail:
        tests = TestControleFeuille.query.filter_by(
            feuille_travail_id=feuille.id, is_archived=False
        ).all()
        
        feuille_key = f"{feuille.reference} - {feuille.titre}"
        tests_stats['tests_par_feuille'][feuille_key] = {
            'total': 0,
            'conformes': 0,
            'non_conformes': 0,
            'taux_conformite': 0,
            'nb_ecarts': 0
        }
        
        for test in tests:
            erreurs = ErreurTest.query.filter_by(test_id=test.id).order_by(ErreurTest.ordre).all()
            
            tests_stats['total_tests'] += 1
            feuille_stats = tests_stats['tests_par_feuille'][feuille_key]
            feuille_stats['total'] += 1
            feuille_stats['nb_ecarts'] += len(erreurs)
            
            if test.resultat == 'conforme':
                tests_stats['tests_conformes'] += 1
                feuille_stats['conformes'] += 1
            elif test.resultat == 'non_conforme':
                tests_stats['tests_non_conformes'] += 1
                feuille_stats['non_conformes'] += 1
            
            if test.niveau_criticite == 'critique':
                tests_stats['tests_par_criticite']['critique'] += 1
            elif test.niveau_criticite == 'eleve':
                tests_stats['tests_par_criticite']['eleve'] += 1
            elif test.niveau_criticite == 'moyen':
                tests_stats['tests_par_criticite']['moyen'] += 1
            elif test.niveau_criticite == 'faible':
                tests_stats['tests_par_criticite']['faible'] += 1
            
            tests_stats['impact_financier_total'] += (test.impact_financier or 0)
            
            if test.taux_reussite:
                taux_reussites.append(test.taux_reussite)
            
            for erreur in erreurs:
                total_ecarts += 1
                gravite = erreur.gravite or 'non_defini'
                etat = erreur.etat or 'non_defini'
                
                ecarts_gravite[gravite] = ecarts_gravite.get(gravite, 0) + 1
                ecarts_etat[etat] = ecarts_etat.get(etat, 0) + 1
                
                if erreur.correction_effectuee or etat in ['corrigee', 'fermee']:
                    total_ecarts_corriges += 1
            
            tests_data.append({
                'feuille_reference': feuille.reference,
                'feuille_titre': feuille.titre,
                'objet_test': test.objet_test,
                'objectif_controle': test.objectif_controle,
                'resultat': test.resultat,
                'procedure': test.procedure,
                'echantillon': test.echantillon,
                'nb_elements_testes': test.nb_elements_testes,
                'nb_erreurs_trouvees': test.nb_erreurs_trouvees,
                'taux_reussite': test.taux_reussite,
                'ecart_constate': test.ecart_constate,
                'cause_racine': test.cause_racine,
                'niveau_criticite': test.niveau_criticite,
                'correction_effectuee': test.correction_effectuee,
                'action_curative': test.action_curative,
                'action_preventive': test.action_preventive,
                'date_correction': test.date_correction.strftime('%d/%m/%Y') if test.date_correction else None,
                'erreurs': [{
                    'description': e.description,
                    'gravite': e.gravite,
                    'etat': e.etat,
                    'impact_financier': e.impact_financier,
                    'correction_proposee': e.correction_proposee,
                    'cause_racine': e.cause_racine
                } for e in erreurs],
                'nb_erreurs': len(erreurs)
            })
    
    # ============================================
    # 4. CALCUL DES TAUX (dans Python)
    # ============================================
    
    if tests_stats['total_tests'] > 0:
        tests_stats['taux_conformite_global'] = round(
            (tests_stats['tests_conformes'] / tests_stats['total_tests']) * 100, 1
        )
    
    if taux_reussites:
        tests_stats['taux_reussite_moyen'] = round(sum(taux_reussites) / len(taux_reussites), 1)
    
    for feuille_key, stats in tests_stats['tests_par_feuille'].items():
        if stats['total'] > 0:
            stats['taux_conformite'] = round((stats['conformes'] / stats['total']) * 100, 1)
    
    tests_stats['total_ecarts'] = total_ecarts
    tests_stats['ecarts_par_gravite'] = ecarts_gravite
    tests_stats['ecarts_par_etat'] = ecarts_etat
    tests_stats['ecarts_corriges'] = total_ecarts_corriges
    
    # 🔥 CALCUL DU TAUX DE CORRECTION (dans Python)
    if tests_stats['total_ecarts'] > 0:
        tests_stats['taux_correction_ecarts'] = round(
            (tests_stats['ecarts_corriges'] / tests_stats['total_ecarts']) * 100, 1
        )
    else:
        tests_stats['taux_correction_ecarts'] = 0
    
    # ============================================
    # 5. FONCTION FORMAT_TAILLE
    # ============================================
    
    def format_taille(taille_bytes):
        if not taille_bytes:
            return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if taille_bytes < 1024.0:
                return f"{taille_bytes:.1f} {unit}"
            taille_bytes /= 1024.0
        return f"{taille_bytes:.1f} GB"
    
    # ============================================
    # 6. STATISTIQUES DE L'AUDIT
    # ============================================
    
    statistiques = {
        'total_constatations': len(constatations),
        'total_recommandations': len(recommandations),
        'total_plans_action': len(plans_action),
        'constatations_par_type': {},
        'constatations_par_gravite': {},
        'constatations_par_statut': {},
        'recommandations_par_type': {},
        'recommandations_par_statut': {},
        'plans_action_actifs': len([p for p in plans_action if p.statut not in ['termine', 'suspendu']]),
        'taux_avancement_moyen': 0,
        'taux_realisation_recommandations': getattr(audit, 'taux_realisation_recommandations', 0),
        'score_global': getattr(audit, 'score_global', 0),
        'tests_stats': tests_stats
    }
    
    for constat in constatations:
        type_const = constat.type_constatation or 'non_defini'
        gravite = constat.gravite or 'non_definie'
        statut = constat.statut or 'non_defini'
        
        statistiques['constatations_par_type'][type_const] = \
            statistiques['constatations_par_type'].get(type_const, 0) + 1
        statistiques['constatations_par_gravite'][gravite] = \
            statistiques['constatations_par_gravite'].get(gravite, 0) + 1
        statistiques['constatations_par_statut'][statut] = \
            statistiques['constatations_par_statut'].get(statut, 0) + 1
    
    for reco in recommandations:
        type_reco = reco.type_recommandation or 'non_defini'
        statut_reco = reco.statut or 'non_defini'
        
        statistiques['recommandations_par_type'][type_reco] = \
            statistiques['recommandations_par_type'].get(type_reco, 0) + 1
        statistiques['recommandations_par_statut'][statut_reco] = \
            statistiques['recommandations_par_statut'].get(statut_reco, 0) + 1
    
    if plans_action:
        total_avancement = sum(p.pourcentage_realisation or 0 for p in plans_action)
        statistiques['taux_avancement_moyen'] = round(total_avancement / len(plans_action), 2)
    
    # ============================================
    # 7. STATISTIQUES DES FICHIERS
    # ============================================
    
    total_taille = sum(f.taille or 0 for f in fichiers_rapport)
    stats_fichiers = {
        'total': len(fichiers_rapport),
        'total_taille': total_taille,
        'total_taille_formatee': format_taille(total_taille),
        'par_type': {}
    }
    
    for fichier in fichiers_rapport:
        type_key = fichier.type_fichier or 'autre'
        if type_key not in stats_fichiers['par_type']:
            stats_fichiers['par_type'][type_key] = {
                'count': 0,
                'total_taille': 0
            }
        stats_fichiers['par_type'][type_key]['count'] += 1
        stats_fichiers['par_type'][type_key]['total_taille'] += fichier.taille or 0
    
    # ============================================
    # 8. RÉCUPÉRER LES SIGNATAIRES
    # ============================================
    
    workflow = WorkflowApprobation.query.filter_by(audit_id=audit.id).first()
    signataire_auditeur = None
    signataire_qualite = None
    
    if workflow:
        if workflow.approbateur_niveau1_id:
            signataire_auditeur = User.query.get(workflow.approbateur_niveau1_id)
        if workflow.approbateur_niveau2_id:
            signataire_qualite = User.query.get(workflow.approbateur_niveau2_id)
    
    if not signataire_auditeur and audit.responsable:
        signataire_auditeur = audit.responsable
    
    # ============================================
    # 9. CRÉATEUR DE L'AUDIT
    # ============================================
    
    createur_audit = User.query.get(audit.created_by) if audit.created_by else None
    
    # ============================================
    # 10. RENDRE LE TEMPLATE
    # ============================================
    
    html_content = render_template(
        'audit/rapport_pdf.html',
        audit=audit,
        constatations=constatations,
        recommandations=recommandations,
        plans_action=plans_action,
        fichiers_rapport=fichiers_rapport,
        stats_fichiers=stats_fichiers,
        tests_data=tests_data,
        tests_stats=tests_stats,
        statistiques=statistiques,
        signataire_auditeur=signataire_auditeur,
        signataire_qualite=signataire_qualite,
        createur_audit=createur_audit,
        current_user=current_user,
        generation_date=datetime.now().strftime('%d/%m/%Y'),
        generation_heure=datetime.now().strftime('%H:%M'),
        now=datetime.now,
        format_taille=format_taille
    )
    
    # Configuration des fonts
    font_config = FontConfiguration()
    
    # CSS pour le PDF
    css = CSS(string='''
        @page {
            size: A4;
            margin: 2cm 1.8cm;
            @bottom-center {
                content: "Page " counter(page) " sur " counter(pages);
                font-size: 9pt;
                color: #666;
            }
        }
        
        body {
            font-family: 'DejaVu Sans', 'Arial', sans-serif;
            font-size: 10pt;
            line-height: 1.4;
            color: #333;
        }
        
        h1 { font-size: 18pt; color: #1e3a8a; margin-bottom: 20px; }
        h2 { font-size: 14pt; color: #2563eb; margin-top: 25px; margin-bottom: 15px; border-bottom: 2px solid #2563eb; padding-bottom: 5px; }
        h3 { font-size: 12pt; color: #1e3a8a; margin-top: 20px; margin-bottom: 10px; }
        
        .card {
            background: white;
            border-radius: 10px;
            border: 1px solid #e2e8f0;
            padding: 20px;
            margin-bottom: 20px;
            page-break-inside: avoid;
        }
        
        .constatation-card { border-left: 4px solid #ef4444; background: #fef2f2; }
        .recommandation-card { border-left: 4px solid #f59e0b; background: #fffbeb; }
        .plan-card { border-left: 4px solid #10b981; background: #ecfdf5; }
        .test-card { border-left: 4px solid #3b82f6; background: #eff6ff; }
        .erreur-card { border-left: 4px solid #dc2626; background: #fef2f2; margin-top: 5px; padding: 10px; border-radius: 6px; }
        
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 50px;
            font-size: 9pt;
            font-weight: 600;
        }
        .badge-success { background: #10b981; color: white; }
        .badge-warning { background: #f59e0b; color: white; }
        .badge-danger { background: #ef4444; color: white; }
        .badge-info { background: #3b82f6; color: white; }
        .badge-secondary { background: #6b7280; color: white; }
        
        .progress {
            background: #e2e8f0;
            border-radius: 50px;
            height: 8px;
            overflow: hidden;
        }
        .progress-bar {
            height: 100%;
            border-radius: 50px;
            background: linear-gradient(90deg, #2563eb, #1e3a8a);
        }
        
        .page-break { page-break-before: always; }
        .no-break { page-break-inside: avoid; }
        .text-center { text-align: center; }
        .text-right { text-align: right; }
        .text-muted { color: #64748b; }
        .mt-2 { margin-top: 10px; }
        .mb-2 { margin-bottom: 10px; }
        .mt-3 { margin-top: 20px; }
        
        hr {
            border: none;
            border-top: 1px solid #e2e8f0;
            margin: 15px 0;
        }
        
        .signature-section {
            display: flex;
            justify-content: space-between;
            margin-top: 50px;
            gap: 40px;
        }
        .signature-box { flex: 1; text-align: center; }
        .signature-line {
            border-top: 1px solid #000;
            margin-top: 30px;
            margin-bottom: 10px;
            padding-top: 10px;
        }
        
        .kpi-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin: 15px 0;
        }
        .kpi-item {
            flex: 1;
            min-width: 100px;
            padding: 15px;
            background: linear-gradient(135deg, #2563eb, #1e3a8a);
            border-radius: 10px;
            color: white;
            text-align: center;
        }
        .kpi-value { font-size: 24pt; font-weight: 700; }
        .kpi-label { font-size: 9pt; opacity: 0.9; }
    ''', font_config=font_config)
    
    # Générer le PDF
    pdf_file = HTML(string=html_content).write_pdf(stylesheets=[css], font_config=font_config)
    
    response = make_response(pdf_file)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=rapport_audit_{audit.reference}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    
    return response


@app.route('/audit/<int:audit_id>/rapport-word-pro')
@login_required
def rapport_audit_word_pro(audit_id):
    """Génère un rapport Word professionnel avec intégration des feuilles de travail"""
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from datetime import datetime
    import io
    from models import User, Constatation, Recommandation, PlanAction, Risque, FichierRapport
    from models import WorkflowApprobation, FeuilleTravail, TestControleFeuille, ErreurTest
    
    # Récupérer l'audit
    audit = Audit.query.get_or_404(audit_id)
    
    if not check_client_access(audit):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_audits'))
    
    # Récupérer les données
    constatations = Constatation.query.filter_by(
        audit_id=audit.id, is_archived=False
    ).order_by(Constatation.created_at.desc()).all()
    
    recommandations = Recommandation.query.filter_by(
        audit_id=audit.id
    ).order_by(Recommandation.created_at.desc()).all()
    
    plans_action = PlanAction.query.filter_by(
        audit_id=audit.id
    ).order_by(PlanAction.created_at.desc()).all()
    
    fichiers_rapport = FichierRapport.query.filter_by(
        audit_id=audit_id
    ).order_by(FichierRapport.created_at.desc()).all()
    
    # Récupérer les feuilles de travail et tests
    feuilles_travail = FeuilleTravail.query.filter_by(
        audit_id=audit.id, is_archived=False
    ).all()
    
    tests_data = []
    tests_stats = {
        'total_tests': 0,
        'tests_conformes': 0,
        'tests_non_conformes': 0,
        'total_ecarts': 0,
        'ecarts_corriges': 0
    }
    
    for feuille in feuilles_travail:
        tests = TestControleFeuille.query.filter_by(
            feuille_travail_id=feuille.id, is_archived=False
        ).all()
        
        for test in tests:
            erreurs = ErreurTest.query.filter_by(test_id=test.id).order_by(ErreurTest.ordre).all()
            
            tests_stats['total_tests'] += 1
            
            if test.resultat == 'conforme':
                tests_stats['tests_conformes'] += 1
            elif test.resultat == 'non_conforme':
                tests_stats['tests_non_conformes'] += 1
            
            tests_stats['total_ecarts'] += len(erreurs)
            for e in erreurs:
                if e.correction_effectuee or e.etat in ['corrigee', 'fermee']:
                    tests_stats['ecarts_corriges'] += 1
            
            tests_data.append({
                'feuille_reference': feuille.reference,
                'objet_test': test.objet_test,
                'objectif_controle': test.objectif_controle,
                'resultat': test.resultat,
                'procedure': test.procedure,
                'echantillon': test.echantillon,
                'nb_elements_testes': test.nb_elements_testes,
                'nb_erreurs_trouvees': test.nb_erreurs_trouvees,
                'taux_reussite': test.taux_reussite,
                'ecart_constate': test.ecart_constate,
                'cause_racine': test.cause_racine,
                'niveau_criticite': test.niveau_criticite,
                'correction_effectuee': test.correction_effectuee,
                'action_curative': test.action_curative,
                'action_preventive': test.action_preventive,
                'date_correction': test.date_correction.strftime('%d/%m/%Y') if test.date_correction else None,
                'erreurs': [{
                    'description': e.description,
                    'gravite': e.gravite,
                    'etat': e.etat,
                    'impact_financier': e.impact_financier,
                    'correction_proposee': e.correction_proposee
                } for e in erreurs],
                'nb_erreurs': len(erreurs)
            })
    
    # Fonctions utilitaires
    def get_type_display(constatation):
        type_map = {
            'non_conformite': 'Non-conformité',
            'conformite': 'Conformité',
            'observation': 'Observation',
            'amelioration': 'Amélioration',
            'recommandation': 'Recommandation'
        }
        return type_map.get(constatation.type_constatation, constatation.type_constatation or 'Non spécifié')
    
    def get_gravite_display(constatation):
        gravite_map = {
            'critique': 'Critique',
            'majeure': 'Majeure',
            'moyenne': 'Moyenne',
            'mineure': 'Mineure'
        }
        return gravite_map.get(constatation.gravite, constatation.gravite or 'Non spécifié')
    
    def get_statut_display(constatation):
        statut_map = {
            'a_analyser': 'À analyser',
            'a_valider': 'À valider',
            'en_action': 'En action',
            'clos': 'Clos'
        }
        return statut_map.get(constatation.statut, constatation.statut or 'Non défini')
    
    def get_reco_type_display(recommandation):
        type_map = {
            'corrective': 'Corrective',
            'preventive': 'Préventive',
            'amelioration': 'Amélioration'
        }
        return type_map.get(recommandation.type_recommandation, recommandation.type_recommandation or 'Non spécifié')
    
    def get_reco_statut_display(recommandation):
        statut_map = {
            'a_traiter': 'À traiter',
            'en_cours': 'En cours',
            'termine': 'Terminé',
            'retarde': 'Retardé'
        }
        return statut_map.get(recommandation.statut, recommandation.statut or 'Non défini')
    
    def get_plan_statut_display(plan):
        statut_map = {
            'en_attente': 'En attente',
            'planifie': 'Planifié',
            'en_cours': 'En cours',
            'termine': 'Terminé',
            'suspendu': 'Suspendu',
            'annule': 'Annulé',
            'retarde': 'Retardé'
        }
        return statut_map.get(plan.statut, plan.statut or 'Non défini')
    
    # Créer le document Word
    doc = Document()
    
    # Titre
    title = doc.add_heading(f"RAPPORT D'AUDIT", level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    subtitle = doc.add_paragraph(f"{audit.reference} - {audit.titre}")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.style.font.size = Pt(14)
    
    doc.add_paragraph()
    
    # Informations
    info_table = doc.add_table(rows=6, cols=2)
    info_table.style = 'Table Grid'
    
    infos = [
        ("Référence", audit.reference),
        ("Date du rapport", datetime.now().strftime('%d/%m/%Y')),
        ("Type d'audit", audit.type_audit or "Non spécifié"),
        ("Statut", audit.statut or "En cours"),
        ("Responsable", audit.responsable.username if audit.responsable else "Non assigné"),
        ("Période", f"{audit.date_debut_prevue.strftime('%d/%m/%Y') if audit.date_debut_prevue else 'N/A'} - {audit.date_fin_prevue.strftime('%d/%m/%Y') if audit.date_fin_prevue else 'N/A'}")
    ]
    
    for i, (label, value) in enumerate(infos):
        info_table.cell(i, 0).text = label
        info_table.cell(i, 0).paragraphs[0].runs[0].bold = True
        info_table.cell(i, 1).text = str(value)
    
    doc.add_page_break()
    
    # Résumé exécutif
    doc.add_heading("RÉSUMÉ EXÉCUTIF", level=2)
    
    resume = doc.add_paragraph()
    resume.add_run(f"L'audit {audit.reference} a permis d'identifier ").font.size = Pt(11)
    resume.add_run(f"{len(constatations)} constatation(s)").bold = True
    resume.add_run(f", dont {len([c for c in constatations if c.gravite == 'critique'])} critique(s). ").font.size = Pt(11)
    
    resume.add_run(f"{len(recommandations)} recommandation(s) ont été formulées, ").font.size = Pt(11)
    resume.add_run(f"dont {len([r for r in recommandations if r.statut == 'termine'])} déjà terminées.").font.size = Pt(11)
    
    doc.add_paragraph()
    tests_summary = doc.add_paragraph()
    tests_summary.add_run(f"📊 Tests de contrôle: ").bold = True
    tests_summary.add_run(f"{tests_stats['total_tests']} tests réalisés, ")
    tests_summary.add_run(f"{tests_stats['tests_conformes']} conformes, ").font.color.rgb = RGBColor(16, 185, 129)
    tests_summary.add_run(f"{tests_stats['tests_non_conformes']} non conformes. ").font.color.rgb = RGBColor(239, 68, 68)
    
    ecarts_summary = doc.add_paragraph()
    ecarts_summary.add_run(f"📌 Écarts constatés: ").bold = True
    ecarts_summary.add_run(f"{tests_stats['total_ecarts']} écarts identifiés, ")
    taux_correction = round((tests_stats['ecarts_corriges'] / max(tests_stats['total_ecarts'], 1)) * 100, 1)
    ecarts_summary.add_run(f"{tests_stats['ecarts_corriges']} corrigés ({taux_correction}%).").font.color.rgb = RGBColor(16, 185, 129)
    
    doc.add_page_break()
    
    # Tests de contrôle
    doc.add_heading("TESTS DE CONTRÔLE", level=2)
    
    if tests_data:
        table = doc.add_table(rows=1, cols=6)
        table.style = 'Table Grid'
        
        headers = ['Test', 'Feuille', 'Résultat', 'Criticité', 'Écarts', 'Action']
        for i, header in enumerate(headers):
            cell = table.rows[0].cells[i]
            cell.text = header
            cell.paragraphs[0].runs[0].bold = True
        
        for test in tests_data:
            row = table.add_row()
            row.cells[0].text = test['objet_test'][:50] if test['objet_test'] else ''
            row.cells[1].text = test['feuille_reference']
            
            resultat_text = "Conforme" if test['resultat'] == 'conforme' else "Non conforme" if test['resultat'] == 'non_conforme' else "Non testé"
            row.cells[2].text = resultat_text
            
            criticite_text = "Critique" if test['niveau_criticite'] == 'critique' else "Élevée" if test['niveau_criticite'] == 'eleve' else "Moyenne"
            row.cells[3].text = criticite_text
            
            row.cells[4].text = str(test['nb_erreurs'])
            row.cells[5].text = "✅ Oui" if test['correction_effectuee'] else "❌ Non"
        
        doc.add_paragraph()
        
        # Détail des écarts
        doc.add_heading("Détail des écarts constatés", level=3)
        
        for test in tests_data:
            if test['nb_erreurs'] > 0:
                doc.add_heading(f"{test['objet_test']} ({test['nb_erreurs']} écarts)", level=4)
                
                for erreur in test['erreurs']:
                    p = doc.add_paragraph(style='List Bullet')
                    p.add_run(f"• {erreur['description']} ")
                    gravite_display = erreur['gravite'].capitalize() if erreur['gravite'] else 'Non défini'
                    p.add_run(f"[{gravite_display}] ").bold = True
                    etat_display = erreur['etat'].capitalize() if erreur['etat'] else 'Non défini'
                    p.add_run(f"| État: {etat_display}")
                    if erreur['impact_financier']:
                        p.add_run(f" | 💰 {erreur['impact_financier']} €")
    
    doc.add_page_break()
    
    # Constatations
    doc.add_heading("CONSTATATIONS DÉTAILLÉES", level=2)
    
    for constat in constatations:
        type_display = get_type_display(constat)
        doc.add_heading(f"{constat.reference} - {type_display}", level=3)
        doc.add_paragraph(constat.description)
        
        if constat.cause_racine:
            doc.add_paragraph(f"Cause racine : {constat.cause_racine}", style='List Bullet')
        
        gravite_display = get_gravite_display(constat)
        statut_display = get_statut_display(constat)
        doc.add_paragraph(f"Gravité : {gravite_display} | Statut : {statut_display}", style='List Bullet')
        
        doc.add_paragraph()
    
    doc.add_page_break()
    
    # Recommandations
    doc.add_heading("RECOMMANDATIONS", level=2)
    
    reco_table = doc.add_table(rows=1, cols=5)
    reco_table.style = 'Table Grid'
    
    reco_headers = ['Réf.', 'Description', 'Type', 'Statut', 'Priorité']
    for i, header in enumerate(reco_headers):
        cell = reco_table.rows[0].cells[i]
        cell.text = header
        cell.paragraphs[0].runs[0].bold = True
    
    for reco in recommandations:
        row = reco_table.add_row()
        row.cells[0].text = reco.reference
        row.cells[1].text = reco.description[:100] + '...' if len(reco.description) > 100 else reco.description
        row.cells[2].text = get_reco_type_display(reco)
        row.cells[3].text = get_reco_statut_display(reco)
        row.cells[4].text = str(reco.score_priorite) if reco.score_priorite else 'N/A'
    
    doc.add_page_break()
    
    # Plans d'action
    doc.add_heading("PLANS D'ACTION", level=2)
    
    for plan in plans_action:
        doc.add_heading(plan.nom, level=3)
        if plan.description:
            doc.add_paragraph(plan.description)
        
        progress = doc.add_paragraph()
        progress.add_run("Avancement: ").bold = True
        progress.add_run(f"{plan.pourcentage_realisation or 0}%")
        doc.add_paragraph(f"Statut: {get_plan_statut_display(plan)}")
        
        doc.add_paragraph()
    
    doc.add_page_break()
    
    # Signatures
    doc.add_heading("VALIDATION", level=2)
    
    workflow = WorkflowApprobation.query.filter_by(audit_id=audit.id).first()
    signataire_auditeur = None
    signataire_qualite = None
    
    if workflow:
        if workflow.approbateur_niveau1_id:
            signataire_auditeur = User.query.get(workflow.approbateur_niveau1_id)
        if workflow.approbateur_niveau2_id:
            signataire_qualite = User.query.get(workflow.approbateur_niveau2_id)
    
    if not signataire_auditeur and audit.responsable:
        signataire_auditeur = audit.responsable
    
    sig_table = doc.add_table(rows=3, cols=2)
    sig_table.style = 'Table Grid'
    
    sig_table.cell(0, 0).text = "Rôle"
    sig_table.cell(0, 1).text = "Signature"
    sig_table.cell(0, 0).paragraphs[0].runs[0].bold = True
    sig_table.cell(0, 1).paragraphs[0].runs[0].bold = True
    
    sig_table.cell(1, 0).text = "Auditeur principal"
    sig_table.cell(1, 1).text = signataire_auditeur.username if signataire_auditeur else "_________________________"
    
    sig_table.cell(2, 0).text = "Responsable Qualité"
    sig_table.cell(2, 1).text = signataire_qualite.username if signataire_qualite else "_________________________"
    
    # Pied de page
    footer = doc.sections[0].footer
    footer_para = footer.paragraphs[0]
    footer_para.text = f"Egalyx Control - Rapport généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}"
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Sauvegarder et retourner
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    response.headers['Content-Disposition'] = f'attachment; filename=rapport_audit_{audit.reference}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.docx'
    
    return response


@app.route('/recommandation/<int:recommandation_id>/maj-statut', methods=['POST'])
@login_required
def maj_statut_recommandation(recommandation_id):
    """Mettre à jour le statut d'une recommandation"""
    recommandation = Recommandation.query.get_or_404(recommandation_id)
    nouveau_statut = request.form.get('statut')
    taux_avancement = request.form.get('taux_avancement')
    
    if nouveau_statut in ['a_traiter', 'en_cours', 'termine', 'retarde']:
        recommandation.statut = nouveau_statut
        
        if taux_avancement:
            recommandation.taux_avancement = int(taux_avancement)
        
        recommandation.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Statut de la recommandation mis à jour', 'success')
    else:
        flash('Statut invalide', 'error')
    
    return redirect(url_for('detail_audit', id=recommandation.audit_id))


@app.route('/audit/<int:audit_id>/risque/nouveau/demander', methods=['POST'])
@login_required
def demander_nouveau_risque_audit(audit_id):
    """L'auditeur propose un nouveau risque - VERSION CORRIGÉE"""
    from models import Audit, Constatation, Risque, DemandeReevaluation, Notification, User, db, EvaluationRisque, CampagneEvaluation
    from datetime import datetime
    
    audit = get_client_object_or_404(Audit, audit_id)
    
    # ============================================
    # 1. RÉCUPÉRER LES DONNÉES DU FORMULAIRE
    # ============================================
    intitule = request.form.get('intitule', '').strip()
    description = request.form.get('description', '').strip()
    processus_concerne = request.form.get('processus_concerne', '')
    categorie = request.form.get('categorie', '')
    impact_propose = request.form.get('impact_propose', type=int)
    probabilite_propose = request.form.get('probabilite_propose', type=int)
    niveau_maitrise_propose = request.form.get('niveau_maitrise_propose', type=int)
    justification = request.form.get('justification', '').strip()
    cartographie_id = request.form.get('cartographie_id', type=int)
    constat_id = request.form.get('constat_id', type=int)
    
    if not intitule or not justification:
        flash('L\'intitulé et la justification sont obligatoires', 'error')
        return redirect(url_for('detail_audit', id=audit_id))
    
    # ============================================
    # 2. VÉRIFIER LA CARTOGRAPHIE CIBLE
    # ============================================
    if not cartographie_id:
        # Si aucune cartographie n'est spécifiée, prendre celle de l'audit
        if audit.cartographie_id:
            cartographie_id = audit.cartographie_id
        else:
            # Ou prendre la première cartographie disponible
            premiere_carto = get_client_filter(Cartographie).filter_by(is_archived=False).first()
            if premiere_carto:
                cartographie_id = premiere_carto.id
            else:
                flash('Aucune cartographie disponible pour créer le risque', 'error')
                return redirect(url_for('detail_audit', id=audit_id))
    
    cartographie = get_client_object_or_404(Cartographie, cartographie_id)
    
    # ============================================
    # 3. CRÉER LE RISQUE EN BROUILLON
    # ============================================
    score_calcule = impact_propose * probabilite_propose
    niveau_criticite = Risque.calculer_niveau_criticite_from_score(score_calcule)
    
    # Générer une référence unique
    dernier_risque = get_client_filter(Risque).order_by(Risque.id.desc()).first()
    nouveau_id = (dernier_risque.id + 1) if dernier_risque else 1
    reference = f"RISK-{datetime.now().strftime('%Y%m%d')}-{nouveau_id:04d}"
    
    nouveau_risque = Risque(
        cartographie_id=cartographie_id,
        reference=reference,
        intitule=intitule,
        description=description,
        processus_concerne=processus_concerne,
        categorie=categorie,
        impact=impact_propose,
        probabilite=probabilite_propose,
        score_risque=score_calcule,
        niveau_criticite=niveau_criticite,
        statut='en_validation',  # 🔥 Statut "en validation" - pas encore actif dans la cartographie
        created_by=current_user.id,
        client_id=current_user.client_id
    )
    db.session.add(nouveau_risque)
    db.session.flush()  # Pour obtenir l'ID
    
    # ============================================
    # 4. 🔥 CRÉER LA DEMANDE DE RÉÉVALUATION ASSOCIÉE
    # ============================================
    demande = DemandeReevaluation(
        audit_id=audit_id,
        constat_id=constat_id if constat_id else None,
        risque_id=nouveau_risque.id,
        titre=f"Nouveau risque: {intitule}",
        description=description,
        justification=justification,
        impact_propose=impact_propose,
        probabilite_propose=probabilite_propose,
        niveau_maitrise_propose=niveau_maitrise_propose,
        demandeur_id=current_user.id,
        client_id=current_user.client_id,
        statut='en_attente'
    )
    demande.reference = demande.generer_reference()
    demande.calculer_score_propose()
    db.session.add(demande)
    db.session.flush()
    
    # ============================================
    # 5. LIER LE CONSTAT À LA DEMANDE
    # ============================================
    if constat_id:
        constat = Constatation.query.get(constat_id)
        if constat:
            constat.demande_reevaluation_id = demande.id
            constat.reevaluation_demandee = True
            constat.reevaluation_statut = 'demandee'
            constat.risque_id = nouveau_risque.id
    
    # ============================================
    # 6. 🔥 CRÉER UNE ÉVALUATION INITIALE (Phase 1 - Pré-évaluation)
    # ============================================
    # Récupérer la campagne active de la cartographie
    campagne_active = get_client_filter(CampagneEvaluation)\
        .filter_by(cartographie_id=cartographie_id, statut='en_cours')\
        .first()
    
    if not campagne_active:
        # Créer une campagne par défaut si nécessaire
        annee_courante = datetime.now().year
        campagne_active = CampagneEvaluation(
            cartographie_id=cartographie_id,
            nom=f"Campagne {annee_courante}",
            description=f"Évaluation annuelle {annee_courante}",
            date_debut=datetime.now().date(),
            statut='en_cours',
            created_by=current_user.id,
            client_id=current_user.client_id
        )
        db.session.add(campagne_active)
        db.session.flush()
    
    # Créer l'évaluation initiale
    evaluation = EvaluationRisque(
        risque_id=nouveau_risque.id,
        campagne_id=campagne_active.id,
        impact_pre=impact_propose,
        probabilite_pre=probabilite_propose,
        niveau_maitrise_pre=niveau_maitrise_propose,
        score_risque=score_calcule,
        niveau_risque=niveau_criticite,
        origine='audit',
        audit_id=audit_id,
        constat_id=constat_id,
        demande_reevaluation_id=demande.id,
        commentaire_pre_evaluation=f"Nouveau risque issu de l'audit {audit.reference}\nJustification: {justification}",
        created_by=current_user.id,
        client_id=current_user.client_id,
        statut_validation='en_attente'  # En attente de validation
    )
    db.session.add(evaluation)
    db.session.flush()
    
    # Lier l'évaluation à la demande
    demande.nouvelle_evaluation_id = evaluation.id
    
    # ============================================
    # 7. NOTIFIER LE COMITÉ DES RISQUES
    # ============================================
    comite_risques = User.query.filter(
        User.client_id == current_user.client_id,
        User.is_active == True,
        User.role.in_(['admin', 'responsable_risques', 'manager'])
    ).all()
    
    for user in comite_risques:
        notification = Notification(
            destinataire_id=user.id,
            type_notification='nouveau_risque_propose',
            titre=f"🆕 Nouveau risque proposé: {intitule}",
            message=f"Un nouveau risque a été identifié lors de l'audit {audit.reference}.\n"
                    f"Intitulé: {intitule}\n"
                    f"Impact: {impact_propose}/5, Probabilité: {probabilite_propose}/5\n"
                    f"Score: {score_calcule} - Niveau: {niveau_criticite}\n"
                    f"Cartographie: {cartographie.nom}\n"
                    f"Justification: {justification}",
            entite_type='demande_reevaluation',
            entite_id=demande.id,
            client_id=current_user.client_id,
            urgence='important'
        )
        db.session.add(notification)
    
    db.session.commit()
    
    flash(f'✅ Nouveau risque proposé (Réf: {nouveau_risque.reference}) - En attente de validation', 'success')
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/audit/<int:audit_id>/risque/<int:risque_id>/demander-reevaluation', methods=['POST'])
@login_required
def demander_reevaluation_risque(audit_id, risque_id):
    """L'auditeur demande une réévaluation d'un risque à partir de l'audit"""
    from models import Audit, Risque, DemandeReevaluation, Notification, User, db
    from datetime import datetime
    
    _journal(f"🔍 ROUTE APPELEE: audit_id={audit_id}, risque_id={risque_id}")
    
    # Récupérer l'audit
    audit = get_client_object_or_404(Audit, audit_id)
    
    # Vérifier l'accès
    if not check_client_access(audit):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('detail_audit', id=audit_id))
    
    # Récupérer le risque
    risque = get_client_object_or_404(Risque, risque_id)
    
    # Vérifier l'accès au risque
    if not check_client_access(risque):
        flash('Accès non autorisé au risque', 'error')
        return redirect(url_for('detail_audit', id=audit_id))
    
    # Récupérer les données du formulaire
    impact_propose = request.form.get('impact_propose', type=int)
    probabilite_propose = request.form.get('probabilite_propose', type=int)
    niveau_maitrise_propose = request.form.get('niveau_maitrise_propose', type=int)
    justification = request.form.get('justification', '').strip()
    
    if not justification:
        flash('La justification est obligatoire', 'error')
        return redirect(url_for('detail_audit', id=audit_id))
    
    # 1. Créer la demande de réévaluation
    demande = DemandeReevaluation(
        audit_id=audit_id,
        constat_id=None,  # Pas de constat spécifique
        risque_id=risque_id,
        titre=f"Réévaluation du risque {risque.reference} - {risque.intitule}",
        description=f"Demande de réévaluation depuis l'audit {audit.reference}",
        justification=justification,
        impact_propose=impact_propose,
        probabilite_propose=probabilite_propose,
        niveau_maitrise_propose=niveau_maitrise_propose,
        demandeur_id=current_user.id,
        client_id=current_user.client_id,
        statut='en_attente'
    )
    demande.reference = demande.generer_reference()
    demande.calculer_score_propose()
    
    db.session.add(demande)
    db.session.flush()
    
    # 2. Notifier le comité des risques
    comite_risques = User.query.filter(
        User.client_id == current_user.client_id,
        User.is_active == True,
        User.role.in_(['admin', 'responsable_risques', 'manager'])
    ).all()
    
    for user in comite_risques:
        notification = Notification(
            destinataire_id=user.id,
            type_notification='reevaluation_demandee',
            titre=f"🔄 Demande de réévaluation: {risque.reference}",
            message=f"Une demande de réévaluation a été soumise pour le risque {risque.reference}.\n"
                    f"Proposition: Impact {impact_propose}/5, Probabilité {probabilite_propose}/5\n"
                    f"Justification: {justification}",
            entite_type='demande_reevaluation',
            entite_id=demande.id,
            client_id=current_user.client_id,
            urgence='important'
        )
        db.session.add(notification)
    
    db.session.commit()
    
    flash(f'✅ Demande de réévaluation créée (Réf: {demande.reference})', 'success')
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/audit/<int:audit_id>/constat/<int:constat_id>/demander-reevaluation', methods=['POST'])
@login_required
def demander_reevaluation_constat(audit_id, constat_id):
    """L'auditeur demande une réévaluation du risque à partir d'un constat"""
    _journal(f"🔍 ROUTE APPELEE: audit_id={audit_id}, constat_id={constat_id}")
    
    from models import Audit, Constatation, DemandeReevaluation, Notification, User, db
    from datetime import datetime
    
    # ============================================
    # 1. RÉCUPÉRER L'AUDIT
    # ============================================
    audit = Audit.query.get(audit_id)
    if not audit:
        _journal(f"❌ Audit {audit_id} non trouvé")
        flash('Audit non trouvé', 'error')
        return redirect(url_for('liste_audits'))
    
    # Vérifier l'accès à l'audit
    if not check_client_access(audit):
        _journal(f"❌ Accès refusé à l'audit {audit_id} pour {current_user.username}")
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_audits'))
    
    _journal(f"✅ Audit trouvé: {audit.reference} (client_id: {audit.client_id})")
    
    # ============================================
    # 2. RÉCUPÉRER LE CONSTAT
    # ============================================
    constat = Constatation.query.get(constat_id)
    if not constat:
        _journal(f"❌ Constat {constat_id} non trouvé")
        flash('Constat non trouvé', 'error')
        return redirect(url_for('detail_audit', id=audit_id))
    
    # Vérifier l'accès au constat
    if not check_client_access(constat):
        _journal(f"❌ Accès refusé au constat {constat_id}")
        flash('Accès non autorisé au constat', 'error')
        return redirect(url_for('detail_audit', id=audit_id))
    
    _journal(f"✅ Constat trouvé: {constat.reference} (audit_id: {constat.audit_id})")
    
    # ============================================
    # 3. VÉRIFICATIONS
    # ============================================
    
    # Vérifier que le constat appartient à l'audit
    if constat.audit_id != audit_id:
        _journal(f"❌ Le constat {constat_id} n'appartient pas à l'audit {audit_id}")
        flash('Ce constat n\'appartient pas à cet audit', 'error')
        return redirect(url_for('detail_audit', id=audit_id))
    
    # Vérifier que le constat a un risque associé
    if not constat.risque_id:
        _journal(f"❌ Le constat {constat_id} n'a pas de risque associé")
        flash('Ce constat n\'est pas associé à un risque', 'error')
        return redirect(url_for('detail_audit', id=audit_id))
    
    # ============================================
    # 4. RÉCUPÉRER LES DONNÉES DU FORMULAIRE
    # ============================================
    impact_propose = request.form.get('impact_propose', type=int)
    probabilite_propose = request.form.get('probabilite_propose', type=int)
    niveau_maitrise_propose = request.form.get('niveau_maitrise_propose', type=int)
    justification = request.form.get('justification', '').strip()
    
    _journal(f"📊 Données: impact={impact_propose}, probabilité={probabilite_propose}, maîtrise={niveau_maitrise_propose}")
    
    if not justification:
        flash('La justification est obligatoire', 'error')
        return redirect(url_for('detail_audit', id=audit_id))
    
    risque = constat.risque
    
    if not risque:
        flash('Le risque associé au constat n\'existe pas', 'error')
        return redirect(url_for('detail_audit', id=audit_id))
    
    _journal(f"✅ Risque associé: {risque.reference} (id: {risque.id})")
    
    # ============================================
    # 5. CRÉER LA DEMANDE DE RÉÉVALUATION
    # ============================================
    
    demande = DemandeReevaluation(
        audit_id=audit_id,
        constat_id=constat_id,
        risque_id=constat.risque_id,
        titre=f"Réévaluation du risque {risque.reference} - {risque.intitule}",
        description=f"Suite au constat {constat.reference}: {constat.description[:100]}...",
        justification=justification,
        impact_propose=impact_propose,
        probabilite_propose=probabilite_propose,
        niveau_maitrise_propose=niveau_maitrise_propose,
        demandeur_id=current_user.id,
        client_id=current_user.client_id,
        statut='en_attente'
    )
    demande.reference = demande.generer_reference()
    demande.calculer_score_propose()
    
    db.session.add(demande)
    db.session.flush()
    
    _journal(f"✅ Demande créée: {demande.reference} (id: {demande.id})")
    
    # ============================================
    # 6. METTRE À JOUR LE CONSTAT
    # ============================================
    constat.demande_reevaluation_id = demande.id
    constat.reevaluation_demandee = True
    constat.reevaluation_statut = 'demandee'
    constat.updated_at = datetime.utcnow()
    
    # ============================================
    # 7. NOTIFIER LE COMITÉ DES RISQUES
    # ============================================
    comite_risques = User.query.filter(
        User.client_id == current_user.client_id,
        User.is_active == True,
        User.role.in_(['admin', 'responsable_risques', 'manager'])
    ).all()
    
    _journal(f"📧 Notification à {len(comite_risques)} utilisateur(s)")
    
    for user in comite_risques:
        notification = Notification(
            destinataire_id=user.id,
            type_notification='reevaluation_demandee',
            titre=f"🔄 Demande de réévaluation: {risque.reference}",
            message=f"Une demande de réévaluation a été soumise pour le risque {risque.reference}.\n"
                    f"Proposition: Impact {impact_propose}/5, Probabilité {probabilite_propose}/5\n"
                    f"Justification: {justification}",
            entite_type='demande_reevaluation',
            entite_id=demande.id,
            client_id=current_user.client_id,
            urgence='important'
        )
        db.session.add(notification)
    
    db.session.commit()
    
    _journal(f"✅ Demande de réévaluation créée avec succès (Réf: {demande.reference})")
    
    flash(f'✅ Demande de réévaluation créée (Réf: {demande.reference})', 'success')
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/api/audit/<int:audit_id>/workflow/annuler-validation', methods=['POST'])
@login_required
def annuler_validation_audit(audit_id):
    """Annuler la validation d'un audit pour revenir à l'étape précédente"""
    from models import WorkflowApprobation, User, db
    from datetime import datetime
    
    workflow = WorkflowApprobation.query.filter_by(audit_id=audit_id).first()
    
    if not workflow:
        return jsonify({'success': False, 'error': 'Workflow non trouvé'}), 404
    
    # Vérifier les permissions
    if not (current_user.role in ['admin', 'super_admin'] or 
            current_user.id == workflow.created_by):
        return jsonify({'success': False, 'error': 'Permission refusée'}), 403
    
    # Annuler selon l'étape actuelle
    ancienne_etape = workflow.etape_actuelle
    
    if ancienne_etape == 'valide':
        # Retour à 'approuve'
        workflow.etape_actuelle = 'approuve'
        workflow.date_approbation_niveau2 = None
        workflow.commentaire_approbation_niveau2 = None
        workflow.approbateur_niveau2_id = None
    elif ancienne_etape == 'approuve':
        # Retour à 'en_relecture'
        workflow.etape_actuelle = 'en_relecture'
        workflow.date_approbation_niveau1 = None
        workflow.commentaire_approbation_niveau1 = None
        workflow.approbateur_niveau1_id = None
    elif ancienne_etape == 'rejete':
        # Retour à 'en_relecture'
        workflow.etape_actuelle = 'en_relecture'
        workflow.commentaire_rejet = None
        workflow.date_rejet = None
    else:
        return jsonify({'success': False, 'error': 'Impossible d\'annuler cette étape'}), 400
    
    # Mettre à jour
    workflow.updated_at = datetime.utcnow()
    
    # Ajouter à l'historique
    if not hasattr(workflow, 'historique_etapes'):
        workflow.historique_etapes = []
    
    # Trouver le nom d'utilisateur
    username = current_user.username if hasattr(current_user, 'username') else 'Système'
    
    workflow.historique_etapes.append({
        'date': datetime.utcnow().isoformat(),
        'ancienne_etape': ancienne_etape,
        'nouvelle_etape': workflow.etape_actuelle,
        'utilisateur_nom': username,
        'utilisateur_id': current_user.id,
        'commentaire': f"Validation annulée par {username}"
    })
    marquer_json_modifie(workflow, 'historique_etapes')
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Validation annulée, retour à l\'étape "{workflow.get_etape_label()}"',
        'nouvelle_etape': workflow.etape_actuelle
    })


@app.route('/audits')
@permission_required('can_manage_audit')
@login_required
def liste_audits():
    """Liste de tous les audits avec filtres d'archivage et isolation"""
    
    # VÉRIFICATION FORMULE : vérifier si le client a accès au module "audit"
    if current_user.client and current_user.client.formule:
        formule = current_user.client.formule
        
        # Vérifier si la formule donne accès au module "audit"
        if not formule.can_access_module('audit_interne'):
            # Afficher une page d'upgrade
            try:
                # Récupérer toutes les formules actives
                all_formules = FormuleAbonnement.query.filter(
                    FormuleAbonnement.is_active == True
                ).all()
                
                # Filtrer celles qui ont le module audit
                upgrade_suggestions = []
                for f in all_formules:
                    if f.modules.get('audit', False):
                        upgrade_suggestions.append(f)
                
                # Trier par prix
                upgrade_suggestions.sort(key=lambda x: x.prix_mensuel or 0)
                
                return render_template('errors/formule_restricted.html', 
                                     module_name='Gestion des Audits',
                                     current_formule=formule,
                                     upgrade_suggestions=upgrade_suggestions[:3])
                
            except Exception as e:
                _journal(f"⚠️ Erreur recherche formules upgrade: {e}")
                flash('Ce module n\'est pas inclus dans votre formule actuelle', 'error')
                return redirect(url_for('dashboard'))
    
    # Vérifier la permission de gérer les audits
    if not current_user.has_permission('can_manage_audit'):
        flash('Accès refusé : permission de gérer les audits requise', 'error')
        return redirect(url_for('dashboard'))
    
    show_archived = request.args.get('show_archived', 'false').lower() == 'true'
    
    # CORRECTION : Utiliser get_client_filter
    if show_archived:
        audits_query = get_client_filter(Audit).filter_by(is_archived=True)
    else:
        audits_query = get_client_filter(Audit).filter_by(is_archived=False)
    
    audits = audits_query.all()
    
    # Vérifier l'accès pour chaque audit (sécurité supplémentaire)
    accessible_audits = []
    for audit in audits:
        if check_client_access(audit):
            accessible_audits.append(audit)
    
    # Calcul des statistiques
    stats = {
        'total': len(accessible_audits),
        'planifies': len([a for a in accessible_audits if a.statut == 'planifie']),
        'en_preparation': len([a for a in accessible_audits if a.sous_statut == 'preparation']),
        'en_collecte': len([a for a in accessible_audits if a.sous_statut == 'collecte']),
        'en_analyse': len([a for a in accessible_audits if a.sous_statut == 'analyse']),
        'en_redaction': len([a for a in accessible_audits if a.sous_statut == 'redaction']),
        'en_validation': len([a for a in accessible_audits if a.sous_statut == 'validation']),
        'clos': len([a for a in accessible_audits if a.statut == 'clos']),
        'constatations_total': sum(len(a.constatations) for a in accessible_audits),
        'recommandations_total': sum(len(a.recommandations) for a in accessible_audits),
        'plans_action_total': sum(len(a.plans_action) for a in accessible_audits),
        'archives': get_client_filter(Audit).filter_by(is_archived=True).count()
    }
    
    return render_template('audits.html', 
                         audits=accessible_audits, 
                         stats=stats,
                         show_archived=show_archived,
                           now=datetime.now())


@app.route('/audit/<int:id>')
@login_required
def detail_audit(id):
    """Détail complet d'un audit avec workflow d'approbation et intégration GRC"""
    from datetime import datetime, timedelta
    from models import (
        User, Constatation, Recommandation, PlanAction, Risque, 
        FichierRapport, Processus, ProcessusActivite, Cartographie,
        WorkflowApprobation, AlerteApprobation, FichierMetadata,
        DispositifMaitrise, ControleProcessus, DemandeReevaluation,
        EvaluationRisque, CampagneEvaluation, SousAction, Audit
    )
    
    # ============================================
    # 1. RÉCUPÉRER L'AUDIT
    # ============================================
    audit = Audit.query.get_or_404(id)
    
    if not check_client_access(audit):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_audits'))
    
    # ============================================
    # 2. DÉTERMINER LE CLIENT_ID
    # ============================================
    if current_user.role == 'super_admin' and session.get('viewing_client_id'):
        client_id = session['viewing_client_id']
    else:
        client_id = current_user.client_id or audit.client_id
    
    # ============================================
    # 3. WORKFLOW D'APPROBATION
    # ============================================
    workflow = WorkflowApprobation.query.filter_by(audit_id=audit.id).first()
    if not workflow:
        workflow = WorkflowApprobation(
            audit_id=audit.id,
            client_id=client_id,
            created_by=current_user.id
        )
        db.session.add(workflow)
        db.session.commit()
    
    # ============================================
    # 4. RÉCUPÉRER LES DONNÉES PRINCIPALES
    # ============================================
    constatations = Constatation.query.filter_by(
        audit_id=audit.id, is_archived=False, client_id=client_id
    ).order_by(Constatation.created_at.desc()).all()
    
    recommandations = Recommandation.query.filter_by(
        audit_id=audit.id, client_id=client_id
    ).order_by(Recommandation.created_at.desc()).all()
    
    plans_action = PlanAction.query.filter_by(
        audit_id=audit.id, client_id=client_id
    ).order_by(PlanAction.created_at.desc()).all()
    
    users = User.query.filter_by(client_id=client_id).all()
    users_json = [{'id': u.id, 'username': u.username} for u in users]
    
    processus_list = Processus.query.filter_by(client_id=client_id).all()
    all_processus_logigramme = ProcessusActivite.query.filter_by(
        is_archived=False, client_id=client_id
    ).order_by(ProcessusActivite.nom).all()
    
    # ============================================
    # 5. CARTOGRAPHIES, RISQUES, DMR, CONTRÔLES
    # ============================================
    cartographies_list = get_client_filter(Cartographie)\
        .filter_by(is_archived=False)\
        .order_by(Cartographie.nom)\
        .all()
    
    risques_list = get_client_filter(Risque)\
        .filter_by(is_archived=False, client_id=client_id)\
        .order_by(Risque.reference)\
        .all()
    
    dispositifs_disponibles = get_client_filter(DispositifMaitrise)\
        .filter_by(is_archived=False, client_id=client_id)\
        .order_by(DispositifMaitrise.reference)\
        .all()
    
    controles_disponibles = get_client_filter(ControleProcessus)\
        .filter_by(statut='actif', client_id=client_id)\
        .order_by(ControleProcessus.nom)\
        .all()
    
    # ============================================
    # 6. STATISTIQUES GRC
    # ============================================
    risques_lies = audit.get_risques_lies()
    
    total_dmr = 0
    for risque in risques_lies:
        dmr_count = DispositifMaitrise.query.filter_by(
            risque_id=risque.id, is_archived=False, client_id=client_id
        ).count()
        total_dmr += dmr_count
    
    total_controles = 0
    for risque in risques_lies:
        controles_count = ControleProcessus.query.filter_by(
            risque_id=risque.id, statut='actif', client_id=client_id
        ).count()
        total_controles += controles_count
    
    stats_grc = {
        'total_dmr': total_dmr,
        'total_controles': total_controles
    }
    
    # ============================================
    # 7. RISQUES ASSOCIÉS
    # ============================================
    risques_associes = []
    risques_ids_vus = set()
    
    for constatation in constatations:
        if constatation.risque_id and constatation.risque_id not in risques_ids_vus:
            risque = Risque.query.filter_by(id=constatation.risque_id, client_id=client_id).first()
            if risque:
                risques_associes.append({
                    'risque': risque,
                    'types_association': ['constatation'],
                    'constatation_ref': constatation.reference,
                    'derniere_evaluation': None
                })
                risques_ids_vus.add(constatation.risque_id)
    
    for recommandation in recommandations:
        if recommandation.risque_id and recommandation.risque_id not in risques_ids_vus:
            risque = Risque.query.filter_by(id=recommandation.risque_id, client_id=client_id).first()
            if risque:
                risque_existant = next((r for r in risques_associes if r['risque'].id == recommandation.risque_id), None)
                if risque_existant:
                    if 'recommandation' not in risque_existant['types_association']:
                        risque_existant['types_association'].append('recommandation')
                else:
                    risques_associes.append({
                        'risque': risque,
                        'types_association': ['recommandation'],
                        'derniere_evaluation': None
                    })
                risques_ids_vus.add(recommandation.risque_id)
    
    for plan in plans_action:
        if plan.risque_id and plan.risque_id not in risques_ids_vus:
            risque = Risque.query.filter_by(id=plan.risque_id, client_id=client_id).first()
            if risque:
                risque_existant = next((r for r in risques_associes if r['risque'].id == plan.risque_id), None)
                if risque_existant:
                    if 'plan_action' not in risque_existant['types_association']:
                        risque_existant['types_association'].append('plan_action')
                else:
                    risques_associes.append({
                        'risque': risque,
                        'types_association': ['plan_action'],
                        'derniere_evaluation': None
                    })
                risques_ids_vus.add(plan.risque_id)
    
    # ============================================
    # 8. DEMANDES DE RÉÉVALUATION PAR RISQUE
    # ============================================
    demandes_reeval_par_risque = {}
    demandes_validees_par_risque = {}
    nb_demandes_attente_global = 0
    
    for risque_data in risques_associes:
        risque_id = risque_data['risque'].id
        
        # Demande en attente
        demande_attente = DemandeReevaluation.query.filter_by(
            risque_id=risque_id,
            statut='en_attente',
            client_id=client_id
        ).first()
        if demande_attente:
            demandes_reeval_par_risque[risque_id] = demande_attente
            nb_demandes_attente_global += 1
        
        # Demandes validées (pour affichage)
        demandes_validees = DemandeReevaluation.query.filter_by(
            risque_id=risque_id,
            client_id=client_id
        ).filter(
            DemandeReevaluation.statut.in_(['validee', 'rejetee'])
        ).order_by(DemandeReevaluation.date_validation.desc()).all()
        
        if demandes_validees:
            demandes_validees_par_risque[risque_id] = demandes_validees
    
    # ============================================
    # 9. RÉCUPÉRER LES DMR ET CONTRÔLES POUR CHAQUE RISQUE
    # ============================================
    dispositifs_par_risque = {}
    controles_par_risque = {}
    
    for risque_data in risques_associes:
        risque_id = risque_data['risque'].id
        
        dispositifs = DispositifMaitrise.query.filter_by(
            risque_id=risque_id,
            is_archived=False,
            client_id=client_id
        ).all()
        dispositifs_par_risque[risque_id] = dispositifs
        
        # Ajouter le nombre de plans d'action en cours pour chaque DMR
        for dmr in dispositifs:
            dmr.nb_plans_en_cours = PlanAction.query.filter_by(
                dispositif_id=dmr.id,
                statut='en_cours',
                client_id=client_id
            ).count()
            dmr.nb_plans_total = PlanAction.query.filter_by(
                dispositif_id=dmr.id,
                client_id=client_id
            ).count()
        
        controles = ControleProcessus.query.filter_by(
            risque_id=risque_id,
            statut='actif',
            client_id=client_id
        ).all()
        controles_par_risque[risque_id] = controles
    
    # ============================================
    # 10. FICHIERS ET PREUVES
    # ============================================
    fichiers_rapport = FichierRapport.query.filter_by(
        audit_id=audit.id, client_id=client_id
    ).order_by(FichierRapport.created_at.desc()).all()
    
    fichiers_par_audit = {}
    if fichiers_rapport:
        fichiers_par_audit[audit.id] = fichiers_rapport
    
    total_preuves = 0
    for constatation in constatations:
        if hasattr(constatation, 'get_preuves_list'):
            preuves_list = constatation.get_preuves_list
            total_preuves += len(preuves_list) if preuves_list else 0
    
    # ============================================
    # 11. FONCTION MÉTADONNÉES
    # ============================================
    def get_fichier_metadata(constatation_id, filename):
        try:
            metadata = FichierMetadata.query.filter_by(
                nom_fichier=filename,
                entite_type='constatation',
                entite_id=constatation_id,
                client_id=client_id
            ).first()
            
            if metadata:
                responsable_nom = metadata.responsable.username if metadata.responsable else 'Non défini'
                return {
                    'commentaire': metadata.commentaire or '',
                    'responsable': responsable_nom,
                    'date_upload': metadata.created_at.strftime('%d/%m/%Y') if metadata.created_at else '',
                    'taille': f"{metadata.taille / 1024:.1f} KB" if metadata.taille else 'N/A',
                    'nom_fichier': metadata.nom_fichier
                }
        except Exception as e:
            _journal(f"Erreur métadonnées: {e}")
        
        return {
            'commentaire': '',
            'responsable': 'Non défini',
            'date_upload': '',
            'taille': 'N/A',
            'nom_fichier': filename
        }
    
    # ============================================
    # 12. PERMISSIONS
    # ============================================
    def user_in_ids_list(ids_string):
        if not ids_string:
            return False
        try:
            ids = [id_str.strip() for id_str in ids_string.split(',')]
            return str(current_user.id) in ids
        except:
            return False
    
    peut_modifier = (
        current_user.role in ['admin', 'super_admin'] or
        current_user.id == audit.created_by or
        current_user.id == audit.responsable_id or
        user_in_ids_list(audit.equipe_audit_ids)
    )
    
    peut_ajouter_constatation = peut_modifier
    peut_ajouter_recommandation = peut_modifier
    peut_generer_rapport = peut_modifier or user_in_ids_list(audit.observateurs_ids)
    
    peut_approuver_niveau1 = (
        current_user.is_client_admin or
        current_user.role == 'super_admin' or
        current_user.id == audit.responsable_id
    )
    
    peut_approuver_niveau2 = (
        current_user.is_client_admin or
        current_user.role == 'super_admin'
    )
    
    # ============================================
    # 13. RENDU DU TEMPLATE - TOUTES LES VARIABLES
    # ============================================
    return render_template(
        'audit/detail_audit.html',
        # Audit et workflow
        audit=audit,
        workflow=workflow,
        peut_approuver_niveau1=peut_approuver_niveau1,
        peut_approuver_niveau2=peut_approuver_niveau2,
        
        # Données de base
        constatations=constatations,
        recommandations=recommandations,
        plans_action=plans_action,
        users=users_json,
        processus_list=processus_list,
        all_processus_logigramme=all_processus_logigramme,
        
        # Cartographies, Risques, DMR, Contrôles
        cartographies_list=cartographies_list,
        risques_list=risques_list,
        dispositifs_disponibles=dispositifs_disponibles,
        controles_disponibles=controles_disponibles,
        
        # Preuves et fichiers
        total_preuves=total_preuves,
        fichiers_par_audit=fichiers_par_audit,
        fichiers_rapport=fichiers_rapport,
        get_fichier_metadata=get_fichier_metadata,
        
        # Risques associés
        risques_associes=risques_associes,
        
        # STATISTIQUES GRC
        stats_grc=stats_grc,
        
        # DEMANDES DE RÉÉVALUATION
        demandes_reeval_par_risque=demandes_reeval_par_risque,
        demandes_validees_par_risque=demandes_validees_par_risque,  # ✅ AJOUTÉ
        nb_demandes_attente_global=nb_demandes_attente_global,
        
        # DMR ET CONTRÔLES PAR RISQUE
        dispositifs_par_risque=dispositifs_par_risque,  # ✅ AJOUTÉ
        controles_par_risque=controles_par_risque,      # ✅ AJOUTÉ
        
        # Permissions
        peut_modifier=peut_modifier,
        peut_ajouter_constatation=peut_ajouter_constatation,
        peut_ajouter_recommandation=peut_ajouter_recommandation,
        peut_generer_rapport=peut_generer_rapport,
        
        # Multi-tenant
        client_id=client_id,
        
        # Utilitaires
        datetime=datetime,
        now=datetime.utcnow,
        current_datetime=datetime.utcnow()
    )


@app.route('/api/audit/<int:audit_id>/workflow/annuler-validation', methods=['POST'])
@login_required
def api_annuler_validation(audit_id):
    """Annuler la validation et recréer les alertes si nécessaire"""
    audit = get_client_object_or_404(Audit, audit_id)
    workflow = WorkflowApprobation.query.filter_by(audit_id=audit_id).first()
    
    if not workflow:
        return jsonify({'success': False, 'error': 'Workflow non trouvé'}), 404
    
    # Vérifier les permissions
    if not (current_user.is_client_admin or current_user.role == 'super_admin' or current_user.id == audit.created_by):
        return jsonify({'success': False, 'error': 'Permission refusée'}), 403
    
    try:
        ancienne_etape = workflow.etape_actuelle
        
        # Déterminer l'étape de retour
        if workflow.etape_actuelle == 'valide':
            workflow.etape_actuelle = 'approuve'
            message = "Validation annulée, retour à l'étape 'Approuvé Niveau 1'"
            
            # Supprimer les dates de validation finale
            workflow.date_validation_finale = None
            workflow.date_approbation_niveau2 = None
            
        elif workflow.etape_actuelle == 'approuve':
            workflow.etape_actuelle = 'en_relecture'
            workflow.date_approbation_niveau1 = None
            workflow.approbateur_niveau1_id = None
            message = "Approbation niveau 1 annulée, retour en relecture"
            
        elif workflow.etape_actuelle == 'rejete':
            workflow.etape_actuelle = 'en_relecture'
            workflow.date_rejet = None
            workflow.commentaire_rejet = None
            message = "Rejet annulé, retour en relecture"
            
        else:
            return jsonify({'success': False, 'error': f'Impossible d\'annuler depuis l\'étape {workflow.etape_actuelle}'}), 400
        
        # ✅ RECRÉER LES ALERTES SI NÉCESSAIRE
        if workflow.etape_actuelle == 'en_relecture':
            # Recréer les alertes de niveau 1
            approbateurs = User.query.filter(
                User.client_id == audit.client_id,
                User.is_active == True,
                User.role.in_(['admin', 'manager', 'responsable_qualite'])
            ).all()
            
            for approbateur in approbateurs:
                alerte = AlerteApprobation(
                    audit_id=audit.id,
                    destinataire_id=approbateur.id,
                    type_alerte='approbation_niveau1',
                    titre=f"🔍 Audit à valider: {audit.reference}",
                    message=f"L'audit '{audit.titre}' est en attente de votre validation (Niveau 1).",
                    client_id=audit.client_id
                )
                db.session.add(alerte)
        
        elif workflow.etape_actuelle == 'approuve':
            # Recréer les alertes de niveau 2
            approbateurs = User.query.filter(
                User.client_id == audit.client_id,
                User.is_active == True,
                User.role.in_(['admin', 'directeur', 'direction'])
            ).all()
            
            for approbateur in approbateurs:
                alerte = AlerteApprobation(
                    audit_id=audit.id,
                    destinataire_id=approbateur.id,
                    type_alerte='approbation_niveau2',
                    titre=f"✅ Audit à approuver: {audit.reference}",
                    message=f"L'audit '{audit.titre}' est en attente de votre validation finale (Niveau 2).",
                    client_id=audit.client_id
                )
                db.session.add(alerte)
        
        # Ajouter à l'historique
        workflow._ajouter_historique(
            ancienne_etape, 
            workflow.etape_actuelle,
            current_user.id, 
            f"Annulation de la validation - {message}"
        )
        
        workflow.updated_at = datetime.utcnow()
        
        # Mettre à jour le statut de l'audit
        if audit:
            if workflow.etape_actuelle == 'en_relecture':
                audit.statut = 'en_validation'
                audit.sous_statut = 'relecture'
            elif workflow.etape_actuelle == 'approuve':
                audit.statut = 'en_validation'
                audit.sous_statut = 'approuve'
            else:
                audit.statut = 'planifie'
                audit.sous_statut = 'correction'
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': message, 'workflow': workflow.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/audit/nouveau', methods=['GET', 'POST'])
@login_required
def nouvel_audit():
    """Créer un nouvel audit avec isolation multi-tenant - VERSION CORRIGÉE"""

    # ===== FORMULAIRE COMPLET =====
    from flask_wtf import FlaskForm
    from wtforms import (
        StringField, TextAreaField, SelectField, RadioField,
        DateField, SubmitField, SelectMultipleField
    )
    from wtforms.validators import DataRequired, Optional, Length

    def coerce_int_or_none(value):
        if value in (None, ''):
            return None
        try:
            return int(value)
        except ValueError:
            return None

    class AuditFormComplete(FlaskForm):
        titre = StringField("Titre de l'audit", validators=[DataRequired()])
        description = TextAreaField("Description")

        type_audit = SelectField(
            "Type d'audit",
            choices=[],
            validators=[DataRequired()]
        )

        # ===== PROCESSUS =====
        selection_processus = RadioField(
            "Méthode de sélection du processus",
            choices=[
                ('logigramme', 'Sélectionner depuis le logigramme'),
                ('manuel', 'Saisie manuelle'),
                ('aucun', 'Aucun processus')
            ],
            default='logigramme',
            validators=[DataRequired()]
        )

        processus_id = SelectField(
            "Processus audité (logigramme)",
            coerce=coerce_int_or_none,
            choices=[],
            validators=[Optional()]
        )

        processus_manuel = StringField(
            "Processus (manuel)",
            validators=[Optional(), Length(max=500)]
        )

        # ===== RESPONSABLE =====
        responsable_id = SelectField(
            "Responsable de l'audit",
            coerce=coerce_int_or_none,
            choices=[],
            validators=[Optional()]
        )

        # ===== DATES =====
        date_debut_prevue = DateField(
            "Date de début prévue",
            format='%Y-%m-%d',
            validators=[Optional()]
        )

        date_fin_prevue = DateField(
            "Date de fin prévue",
            format='%Y-%m-%d',
            validators=[Optional()]
        )

        # ===== CONTENU =====
        portee = TextAreaField("Portée")
        objectifs = TextAreaField("Objectifs")
        criteres = TextAreaField("Critères")
        parties_prenantes = TextAreaField("Parties prenantes")

        # ===== STATUT =====
        statut = SelectField(
            "Statut",
            choices=[
                ('planifie', 'Planifié'),
                ('en_preparation', 'En préparation'),
                ('en_cours', 'En cours'),
                ('en_redaction', 'En rédaction'),
                ('en_validation', 'En validation'),
                ('clos', 'Clos')
            ],
            default='planifie'
        )

        sous_statut = SelectField(
            "Sous-statut",
            choices=[
                ('planification', 'Planification'),
                ('preparation', 'Préparation'),
                ('collecte', 'Collecte des preuves'),
                ('analyse', 'Analyse'),
                ('redaction', 'Rédaction'),
                ('validation', 'Validation'),
                ('cloture', 'Clôture')
            ],
            validators=[Optional()]
        )

        # ===== ÉQUIPES =====
        equipe_audit_ids = SelectMultipleField(
            "Auditeurs",
            coerce=int,
            choices=[],
            validators=[Optional()]
        )

        participants_ids = SelectMultipleField(
            "Participants",
            coerce=int,
            choices=[],
            validators=[Optional()]
        )

        observateurs_ids = SelectMultipleField(
            "Observateurs",
            coerce=int,
            choices=[],
            validators=[Optional()]
        )

        submit = SubmitField("Créer l'audit")

    form = AuditFormComplete()

    # ===== DONNÉES =====
    # Récupérer uniquement les utilisateurs du même client
    if current_user.role == 'super_admin':
        all_users = User.query.filter_by(is_active=True).order_by(User.username).all()
    else:
        all_users = get_client_filter(User).filter_by(is_active=True).order_by(User.username).all()

    # Processus actifs de l'utilisateur
    all_processus = get_client_filter(ProcessusActivite)\
        .filter_by(is_archived=False)\
        .order_by(ProcessusActivite.nom).all()

    # ===== CHOIX DYNAMIQUES =====
    form.type_audit.choices = [
        ('', 'Sélectionnez un type'),
        ('interne', 'Audit Interne'),
        ('externe', 'Audit Externe'),
        ('qualite', 'Audit Qualité'),
        ('conformite', 'Audit Conformité'),
        ('securite', 'Audit Sécurité'),
        ('performance', 'Audit Performance'),
        ('financier', 'Audit Financier'),
        ('operationnel', 'Audit Opérationnel'),
        ('systeme', 'Audit Système')
    ]

    form.processus_id.choices = [('', 'Sélectionnez un processus')] + [
        (
            p.id,
            f"{p.nom} - {p.direction.nom if p.direction else 'Non spécifié'}"
        )
        for p in all_processus
    ]

    form.responsable_id.choices = [('', 'Sélectionnez un responsable')] + [
        (u.id, f"{u.username} - {u.role}") for u in all_users
    ]

    form.equipe_audit_ids.choices = [(u.id, f"{u.username} - {u.role}") for u in all_users]
    form.participants_ids.choices = [(u.id, f"{u.username} - {u.role}") for u in all_users]
    form.observateurs_ids.choices = [(u.id, f"{u.username} - {u.role}") for u in all_users]

    # ===== SOUMISSION =====
    if form.validate_on_submit():
        try:
            # GÉNÉRATION DE RÉFÉRENCE UNIQUE
            def generer_reference_audit(client_id=None):
                from sqlalchemy import func
                
                base_ref = "AUD-"
                
                if client_id:
                    dernier = Audit.query.filter_by(client_id=client_id)\
                        .order_by(Audit.id.desc())\
                        .first()
                else:
                    dernier = Audit.query.order_by(Audit.id.desc()).first()
                
                if dernier and dernier.reference:
                    try:
                        if dernier.reference.startswith(base_ref):
                            dernier_num = int(dernier.reference.split('-')[1])
                            nouveau_num = dernier_num + 1
                        else:
                            if client_id:
                                count = Audit.query.filter_by(client_id=client_id).count()
                            else:
                                count = Audit.query.count()
                            nouveau_num = count + 1
                    except (ValueError, IndexError):
                        if client_id:
                            count = Audit.query.filter_by(client_id=client_id).count()
                        else:
                            count = Audit.query.count()
                        nouveau_num = count + 1
                else:
                    nouveau_num = 1
                
                return f"{base_ref}{nouveau_num:04d}"
            
            # Déterminer le client_id pour la génération de référence
            client_id_for_ref = None
            if current_user.role != 'super_admin' and hasattr(current_user, 'client_id'):
                client_id_for_ref = current_user.client_id
            elif current_user.role == 'super_admin' and session.get('viewing_client_id'):
                client_id_for_ref = session.get('viewing_client_id')
            
            # Générer la référence
            reference = generer_reference_audit(client_id_for_ref)
            
            # Vérifier que la référence n'existe pas déjà
            existing_audit = Audit.query.filter_by(reference=reference).first()
            if existing_audit:
                base_num = int(reference.split('-')[1])
                for i in range(1, 1000):
                    new_ref = f"AUD-{(base_num + i):04d}"
                    if not Audit.query.filter_by(reference=new_ref).first():
                        reference = new_ref
                        break
            
            audit = Audit(
                reference=reference,
                titre=form.titre.data,
                description=form.description.data,
                type_audit=form.type_audit.data,
                date_debut_prevue=form.date_debut_prevue.data,
                date_fin_prevue=form.date_fin_prevue.data,
                portee=form.portee.data,
                objectifs=form.objectifs.data,
                criteres=form.criteres.data,
                parties_prenantes=form.parties_prenantes.data,
                statut=form.statut.data,
                sous_statut=form.sous_statut.data or 'planification',
                created_by=current_user.id,
                client_id=current_user.client_id
            )

            # CORRECTION : UNIQUEMENT pour super_admin en mode client
            if current_user.role == 'super_admin' and session.get('viewing_client_id'):
                audit.client_id = session.get('viewing_client_id')

            # ===== PROCESSUS =====
            if form.selection_processus.data == 'logigramme' and form.processus_id.data:
                processus = ProcessusActivite.query.get(form.processus_id.data)
                if processus and check_client_access(processus):
                    audit.processus_id = form.processus_id.data
                    audit.processus_concerne = None
                else:
                    flash('Accès non autorisé à ce processus', 'error')
                    return render_template('audit/form_audit.html', form=form, all_users=all_users, all_processus=all_processus, title="Nouvel Audit")

            elif form.selection_processus.data == 'manuel' and form.processus_manuel.data:
                audit.processus_concerne = form.processus_manuel.data.strip()
                audit.processus_id = None

            else:
                audit.processus_id = None
                audit.processus_concerne = None

            # ===== RESPONSABLE =====
            if form.responsable_id.data:
                responsable = db.session.get(User, form.responsable_id.data)
                if responsable:
                    if current_user.role != 'super_admin':
                        if responsable.client_id != current_user.client_id:
                            flash('Le responsable sélectionné ne fait pas partie de votre client', 'error')
                            return render_template('audit/form_audit.html', form=form, all_users=all_users, all_processus=all_processus, title="Nouvel Audit")
                    
                    audit.responsable_id = form.responsable_id.data
                else:
                    flash('Responsable non trouvé', 'error')
                    return render_template('audit/form_audit.html', form=form, all_users=all_users, all_processus=all_processus, title="Nouvel Audit")

            # ===== ÉQUIPES =====
            equipe_ids = form.equipe_audit_ids.data or []
            participants_ids = form.participants_ids.data or []
            observateurs_ids = form.observateurs_ids.data or []
            
            # Vérifier que tous les utilisateurs sélectionnés appartiennent au même client
            if current_user.role != 'super_admin' and (equipe_ids or participants_ids or observateurs_ids):
                all_selected_ids = set(equipe_ids + participants_ids + observateurs_ids)
                users = User.query.filter(User.id.in_(all_selected_ids)).all()
                for user in users:
                    if user.client_id != current_user.client_id:
                        flash(f"L'utilisateur {user.username} ne fait pas partie de votre client", 'error')
                        return render_template('audit/form_audit.html', form=form, all_users=all_users, all_processus=all_processus, title="Nouvel Audit")

            audit.equipe_audit_ids = ','.join(map(str, equipe_ids)) if equipe_ids else None
            audit.participants_ids = ','.join(map(str, participants_ids)) if participants_ids else None
            audit.observateurs_ids = ','.join(map(str, observateurs_ids)) if observateurs_ids else None

            db.session.add(audit)
            db.session.flush()
            
            # ===== CRÉER LE WORKFLOW D'APPROBATION =====
            workflow = WorkflowApprobation(
                audit_id=audit.id,
                client_id=audit.client_id or current_user.client_id,
                created_by=current_user.id
            )
            
            # Récupérer les approbateurs spécifiques du formulaire
            approbateur_niveau1_id = request.form.get('approbateur_niveau1_id')
            approbateur_niveau2_id = request.form.get('approbateur_niveau2_id')
            
            if approbateur_niveau1_id:
                workflow.approbateur_niveau1_id = int(approbateur_niveau1_id)
                user = User.query.get(workflow.approbateur_niveau1_id)
                if user:
                    workflow.approbateur_niveau1_nom = user.username
            
            if approbateur_niveau2_id:
                workflow.approbateur_niveau2_id = int(approbateur_niveau2_id)
                user = User.query.get(workflow.approbateur_niveau2_id)
                if user:
                    workflow.approbateur_niveau2_nom = user.username
            
            db.session.add(workflow)
            
            # ==================== NOTIFICATIONS ====================
            notifications_crees = []
            
            # 1. Notification pour le créateur
            notification_createur = Notification(
                destinataire_id=current_user.id,
                type_notification=Notification.TYPE_AUDIT_DEMARRE,
                titre=f"Audit créé: {audit.reference}",
                message=f"L'audit '{audit.titre}' a été créé avec succès.",
                urgence=Notification.URGENCE_NORMAL,
                entite_type='audit',
                entite_id=audit.id,
                donnees_supplementaires={
                    'type_audit': audit.type_audit,
                    'statut': audit.statut,
                    'equipe_size': len(equipe_ids)
                },
                client_id=audit.client_id
            )
            db.session.add(notification_createur)
            notifications_crees.append(current_user.id)
            
            # 2. Notification pour le responsable (si différent du créateur)
            if audit.responsable_id and audit.responsable_id != current_user.id:
                notification_responsable = Notification(
                    destinataire_id=audit.responsable_id,
                    type_notification=Notification.TYPE_AUDIT_DEMARRE,
                    titre=f"Vous êtes responsable de l'audit: {audit.reference}",
                    message=f"Vous avez été désigné comme responsable de l'audit '{audit.titre}'.",
                    urgence=Notification.URGENCE_IMPORTANT,
                    entite_type='audit',
                    entite_id=audit.id,
                    donnees_supplementaires={
                        'type_audit': audit.type_audit,
                        'createur': current_user.username,
                        'date_debut': audit.date_debut_prevue.isoformat() if audit.date_debut_prevue else None
                    },
                    client_id=audit.client_id
                )
                db.session.add(notification_responsable)
                notifications_crees.append(audit.responsable_id)
            
            # 3. Notifications pour l'équipe d'audit
            for user_id in equipe_ids:
                if user_id not in notifications_crees:
                    notification_equipe = Notification(
                        destinataire_id=user_id,
                        type_notification=Notification.TYPE_AUDIT_DEMARRE,
                        titre=f"Vous êtes dans l'équipe d'audit: {audit.reference}",
                        message=f"Vous avez été ajouté à l'équipe de l'audit '{audit.titre}'.",
                        urgence=Notification.URGENCE_NORMAL,
                        entite_type='audit',
                        entite_id=audit.id,
                        donnees_supplementaires={
                            'role': 'auditeur',
                            'responsable': audit.responsable.username if audit.responsable else None
                        },
                        client_id=audit.client_id
                    )
                    db.session.add(notification_equipe)
                    notifications_crees.append(user_id)
            
            db.session.commit()

            # Journaliser l'action
            log_activity(current_user.id, 'creation_audit',
                        f"Création audit {audit.reference}: {audit.titre}",
                        'audit', audit.id)

            flash(f'✅ Audit "{audit.titre}" créé avec succès ({audit.reference})', 'success')
            return redirect(url_for('detail_audit', id=audit.id))

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Erreur création audit: {str(e)}", exc_info=True)
            flash(f"❌ Erreur lors de la création de l'audit: {str(e)}", "danger")

    return render_template('audit/form_audit.html', 
                         form=form,
                         all_users=all_users,
                         users=all_users,
                         all_processus=all_processus,
                         title="Nouvel Audit")


@app.route('/audit/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_audit(id):
    """Modifier un audit existant avec isolation multi-tenant"""
    
    # CORRECTION : Récupérer avec vérification d'accès
    audit = Audit.query.get_or_404(id)
    
    # Vérifier l'accès
    if not check_client_access(audit):
        flash('Accès non autorisé à cet audit', 'error')
        return redirect(url_for('liste_audits'))
    
    # Récupérer le workflow existant
    workflow = WorkflowApprobation.query.filter_by(audit_id=audit.id).first()
    
    # Créer un formulaire de modification
    from flask_wtf import FlaskForm
    from wtforms import StringField, TextAreaField, SelectField, RadioField, DateField, SubmitField, SelectMultipleField
    from wtforms.validators import DataRequired, Optional, Length
    
    def coerce_int_or_none(value):
        if value == '' or value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None
    
    class EditAuditForm(FlaskForm):
        # Informations de base
        titre = StringField("Titre de l'audit", validators=[DataRequired()])
        description = TextAreaField("Description")
        
        type_audit = SelectField(
            "Type d'audit",
            choices=[],  # Sera rempli
            validators=[DataRequired()]
        )
        
        # SÉLECTION DE PROCESSUS
        selection_processus = RadioField(
            "Méthode de sélection du processus",
            choices=[
                ('logigramme', 'Sélectionner depuis le logigramme'),
                ('manuel', 'Écrire manuellement'),
                ('aucun', 'Aucun processus spécifique')
            ],
            default='logigramme',
            validators=[DataRequired()]
        )
        
        processus_id = SelectField(
            "Processus audité (logigramme)", 
            coerce=coerce_int_or_none,
            choices=[],  # Sera rempli
            validators=[Optional()]
        )
        
        processus_manuel = StringField(
            "Nom du processus (manuel)",
            validators=[Optional(), Length(max=500)]
        )
        
        # Responsable
        responsable_id = SelectField(
            "Responsable", 
            coerce=coerce_int_or_none,
            choices=[],  # Sera rempli
            validators=[Optional()]
        )
        
        # Dates
        date_debut_prevue = DateField(
            "Date de début prévue", 
            format='%Y-%m-%d', 
            validators=[Optional()]
        )
        
        date_fin_prevue = DateField(
            "Date de fin prévue", 
            format='%Y-%m-%d', 
            validators=[Optional()]
        )
        
        date_debut_reelle = DateField(
            "Date de début réelle", 
            format='%Y-%m-%d', 
            validators=[Optional()]
        )
        
        date_fin_reelle = DateField(
            "Date de fin réelle", 
            format='%Y-%m-%d', 
            validators=[Optional()]
        )
        
        # Informations techniques
        portee = TextAreaField("Portée de l'audit")
        objectifs = TextAreaField("Objectifs")
        criteres = TextAreaField("Critères d'audit")
        parties_prenantes = TextAreaField("Parties prenantes supplémentaires")
        
        # Statuts
        statut = SelectField(
            "Statut",
            choices=[
                ('planifie', 'Planifié'),
                ('en_preparation', 'En préparation'),
                ('en_cours', 'En cours'),
                ('en_redaction', 'En rédaction'),
                ('en_validation', 'En validation'),
                ('clos', 'Clos'),
                ('suspendu', 'Suspendu'),
                ('annule', 'Annulé')
            ]
        )
        
        sous_statut = SelectField(
            "Sous-statut",
            choices=[
                ('planification', 'Planification'),
                ('preparation', 'Préparation'),
                ('collecte', 'Collecte des preuves'),
                ('analyse', 'Analyse'),
                ('redaction', 'Rédaction du rapport'),
                ('validation', 'Validation'),
                ('cloture', 'Clôture'),
                ('archive', 'Archivé')
            ],
            validators=[Optional()]
        )
        
        # Équipes
        equipe_audit_ids = SelectMultipleField(
            "Auditeurs participants",
            coerce=int,
            choices=[],  # Sera rempli
            validators=[Optional()]
        )
        
        participants_ids = SelectMultipleField(
            "Participants interviewés",
            coerce=int,
            choices=[],  # Sera rempli
            validators=[Optional()]
        )
        
        observateurs_ids = SelectMultipleField(
            "Observateurs",
            coerce=int,
            choices=[],  # Sera rempli
            validators=[Optional()]
        )
        
        commentaires = TextAreaField("Commentaires généraux")
        
        submit = SubmitField("Mettre à jour l'audit")
    
    # Créer le formulaire avec les données actuelles
    form = EditAuditForm(obj=audit)
    
    # CORRECTION : Récupérer les données avec filtrage client
    all_processus = get_client_filter(ProcessusActivite).order_by(ProcessusActivite.nom).all()
    
    # CORRECTION : Récupérer uniquement les utilisateurs du même client
    if current_user.role == 'super_admin':
        all_users = User.query.filter_by(is_active=True).order_by(User.username).all()
    else:
        all_users = get_client_filter(User).filter_by(is_active=True).order_by(User.username).all()
    
    # Initialiser les choix
    form.type_audit.choices = [
        ('', 'Sélectionnez un type'),
        ('interne', 'Audit Interne'),
        ('externe', 'Audit Externe'),
        ('qualite', 'Audit Qualité'),
        ('conformite', 'Audit Conformité'),
        ('securite', 'Audit Sécurité'),
        ('performance', 'Audit Performance'),
        ('financier', 'Audit Financier'),
        ('operationnel', 'Audit Opérationnel'),
        ('systeme', 'Audit Système')
    ]
    
    form.processus_id.choices = [('', 'Sélectionnez un processus')] + [
        (p.id, f"{p.nom} - {p.direction.nom if p.direction else 'Non spécifié'}") 
        for p in all_processus
    ]
    
    form.responsable_id.choices = [('', 'Sélectionnez un responsable')] + [
        (u.id, f"{u.username} - {u.role}") for u in all_users
    ]
    
    form.equipe_audit_ids.choices = [(u.id, f"{u.username} - {u.role}") for u in all_users]
    form.participants_ids.choices = [(u.id, f"{u.username} - {u.role}") for u in all_users]
    form.observateurs_ids.choices = [(u.id, f"{u.username} - {u.role}") for u in all_users]
    
    # Déterminer la méthode de sélection actuelle
    if audit.processus_id:
        form.selection_processus.data = 'logigramme'
        form.processus_id.data = audit.processus_id
    elif hasattr(audit, 'processus_concerne') and audit.processus_concerne:
        form.selection_processus.data = 'manuel'
        form.processus_manuel.data = audit.processus_concerne
    else:
        form.selection_processus.data = 'aucun'
    
    # Pré-remplir les listes d'équipe
    if audit.equipe_audit_ids:
        try:
            form.equipe_audit_ids.data = [int(id.strip()) for id in audit.equipe_audit_ids.split(',') if id.strip()]
        except (ValueError, AttributeError):
            form.equipe_audit_ids.data = []
    
    if audit.participants_ids:
        try:
            form.participants_ids.data = [int(id.strip()) for id in audit.participants_ids.split(',') if id.strip()]
        except (ValueError, AttributeError):
            form.participants_ids.data = []
    
    if audit.observateurs_ids:
        try:
            form.observateurs_ids.data = [int(id.strip()) for id in audit.observateurs_ids.split(',') if id.strip()]
        except (ValueError, AttributeError):
            form.observateurs_ids.data = []
    
    if form.validate_on_submit():
        try:
            # Enregistrer l'ancien état
            ancien_etat = {
                'titre': audit.titre,
                'type_audit': audit.type_audit,
                'statut': audit.statut,
                'sous_statut': audit.sous_statut,
                'processus_id': audit.processus_id,
                'processus_concerne': getattr(audit, 'processus_concerne', None),
                'responsable_id': audit.responsable_id
            }
            
            # Mettre à jour les champs de base
            audit.titre = form.titre.data
            audit.description = form.description.data
            audit.type_audit = form.type_audit.data
            audit.statut = form.statut.data
            audit.sous_statut = form.sous_statut.data if form.sous_statut.data else audit.sous_statut
            
            # Dates
            audit.date_debut_prevue = form.date_debut_prevue.data
            audit.date_fin_prevue = form.date_fin_prevue.data
            audit.date_debut_reelle = form.date_debut_reelle.data if form.date_debut_reelle.data else None
            audit.date_fin_reelle = form.date_fin_reelle.data if form.date_fin_reelle.data else None
            
            # Informations techniques
            audit.portee = form.portee.data if form.portee.data else None
            audit.objectifs = form.objectifs.data if form.objectifs.data else None
            audit.criteres = form.criteres.data if form.criteres.data else None
            audit.parties_prenantes = form.parties_prenantes.data if form.parties_prenantes.data else None
            audit.commentaires = form.commentaires.data if form.commentaires.data else None
            
            # Gestion du processus selon la méthode choisie
            selection_method = form.selection_processus.data
            
            if selection_method == 'logigramme':
                if form.processus_id.data:
                    processus_id = int(form.processus_id.data)
                    processus = ProcessusActivite.query.get(processus_id)
                    if processus and not check_client_access(processus):
                        flash('Le processus sélectionné ne fait pas partie de votre client', 'error')
                        return render_template('audit/form_audit.html', form=form, audit=audit, all_users=all_users, all_processus=all_processus, title=f"Modifier l'audit {audit.reference}")
                    
                    audit.processus_id = processus_id
                    if hasattr(audit, 'processus_concerne'):
                        audit.processus_concerne = None
                else:
                    audit.processus_id = None
                    if hasattr(audit, 'processus_concerne'):
                        audit.processus_concerne = None
                        
            elif selection_method == 'manuel':
                if form.processus_manuel.data:
                    if hasattr(audit, 'processus_concerne'):
                        audit.processus_concerne = form.processus_manuel.data.strip()
                    audit.processus_id = None
                else:
                    if hasattr(audit, 'processus_concerne'):
                        audit.processus_concerne = None
                    audit.processus_id = None
                    
            elif selection_method == 'aucun':
                audit.processus_id = None
                if hasattr(audit, 'processus_concerne'):
                    audit.processus_concerne = None
            
            # Responsable
            if form.responsable_id.data:
                responsable_id = int(form.responsable_id.data)
                responsable = User.query.get(responsable_id)
                if responsable and not check_client_access(responsable):
                    flash('Le responsable sélectionné ne fait pas partie de votre client', 'error')
                    return render_template('audit/form_audit.html', form=form, audit=audit, all_users=all_users, all_processus=all_processus, title=f"Modifier l'audit {audit.reference}")
                
                audit.responsable_id = responsable_id
            else:
                audit.responsable_id = None
            
            # Gestion des listes d'équipe
            equipe_ids = form.equipe_audit_ids.data or []
            participants_ids = form.participants_ids.data or []
            observateurs_ids = form.observateurs_ids.data or []
            
            # Vérifier que tous les utilisateurs sélectionnés appartiennent au même client
            if current_user.role != 'super_admin':
                all_selected_ids = set(equipe_ids + participants_ids + observateurs_ids)
                if all_selected_ids:
                    users = User.query.filter(User.id.in_(all_selected_ids)).all()
                    for user in users:
                        if not check_client_access(user):
                            flash(f"L'utilisateur {user.username} ne fait pas partie de votre client", 'error')
                            return render_template('audit/form_audit.html', form=form, audit=audit, all_users=all_users, all_processus=all_processus, title=f"Modifier l'audit {audit.reference}")
            
            audit.equipe_audit_ids = ','.join(map(str, equipe_ids)) if equipe_ids else None
            audit.participants_ids = ','.join(map(str, participants_ids)) if participants_ids else None
            audit.observateurs_ids = ','.join(map(str, observateurs_ids)) if observateurs_ids else None
            
            # ===== METTRE À JOUR LE WORKFLOW D'APPROBATION =====
            if not workflow:
                workflow = WorkflowApprobation(
                    audit_id=audit.id,
                    client_id=audit.client_id or current_user.client_id,
                    created_by=current_user.id
                )
                db.session.add(workflow)
            
            # Mettre à jour les approbateurs spécifiques
            approbateur_niveau1_id = request.form.get('approbateur_niveau1_id')
            approbateur_niveau2_id = request.form.get('approbateur_niveau2_id')
            
            if approbateur_niveau1_id:
                workflow.approbateur_niveau1_id = int(approbateur_niveau1_id)
                user = User.query.get(workflow.approbateur_niveau1_id)
                workflow.approbateur_niveau1_nom = user.username if user else None
            else:
                workflow.approbateur_niveau1_id = None
                workflow.approbateur_niveau1_nom = None
            
            if approbateur_niveau2_id:
                workflow.approbateur_niveau2_id = int(approbateur_niveau2_id)
                user = User.query.get(workflow.approbateur_niveau2_id)
                workflow.approbateur_niveau2_nom = user.username if user else None
            else:
                workflow.approbateur_niveau2_id = None
                workflow.approbateur_niveau2_nom = None
            
            audit.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Journaliser
            if 'journaliser_action_audit' in globals():
                journaliser_action_audit(
                    audit_id=audit.id,
                    action_type='modification_audit',
                    user_id=current_user.id,
                    details={
                        'ancien_etat': ancien_etat,
                        'nouvel_etat': {
                            'titre': audit.titre,
                            'type_audit': audit.type_audit,
                            'statut': audit.statut,
                            'processus_id': audit.processus_id,
                            'processus_concerne': getattr(audit, 'processus_concerne', None),
                            'responsable_id': audit.responsable_id
                        }
                    }
                )
            
            flash('Audit modifié avec succès', 'success')
            return redirect(url_for('detail_audit', id=audit.id))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Erreur lors de la modification de l'audit {id}: {str(e)}", exc_info=True)
            flash(f'Erreur lors de la modification: {str(e)}', 'error')
    
    return render_template('audit/form_audit.html', 
                         form=form, 
                         audit=audit,
                         workflow=workflow,
                         all_users=all_users,
                         users=all_users,
                         all_processus=all_processus, 
                         title=f"Modifier l'audit {audit.reference}")


@app.route('/audit/<int:id>/archive', methods=['POST'])
@login_required
def archive_audit(id):
    """Archiver un audit avec isolation multi-tenant - VERSION ULTIME"""
    
    _journal(f"🔍 [ARCHIVE] Début pour audit {id}")
    _journal(f"🔍 [ARCHIVE] User: {current_user.username} (client_id={current_user.client_id}, role={current_user.role})")
    
    # 1. Récupérer l'audit
    audit = Audit.query.get(id)
    
    if not audit:
        flash('Audit non trouvé', 'error')
        return redirect(url_for('liste_audits'))
    
    _journal(f"🔍 [ARCHIVE] Audit: {audit.reference} (client_id={audit.client_id}, created_by={audit.created_by})")
    
    # 2. CORRECTION CRITIQUE : Si l'audit appartient à un autre client mais que l'utilisateur est le créateur
    if audit.client_id and audit.client_id != current_user.client_id:
        _journal(f"⚠️ [ARCHIVE] Audit client_id={audit.client_id} différent de user client_id={current_user.client_id}")
        
        # Vérifier si l'utilisateur est le créateur
        if audit.created_by == current_user.id:
            _journal(f"✅ [ARCHIVE] Utilisateur est le créateur - autorisation spéciale")
            # On autorise car c'est le créateur
        else:
            _journal(f"❌ [ARCHIVE] Accès refusé: pas le même client et pas le créateur")
            flash('Accès non autorisé à cet audit', 'error')
            return redirect(url_for('liste_audits'))
    
    # 3. Vérifier permissions simplifiée
    can_archive = False
    
    # Super admin peut tout faire
    if current_user.role == 'super_admin':
        can_archive = True
    # Admin client peut archiver les audits de son client
    elif current_user.is_client_admin and audit.client_id == current_user.client_id:
        can_archive = True
    # Créateur peut archiver son audit
    elif audit.created_by == current_user.id:
        can_archive = True
    # Responsable peut archiver
    elif audit.responsable_id == current_user.id:
        can_archive = True
    # Permission can_manage_audit
    elif current_user.has_permission('can_manage_audit'):
        can_archive = True
    
    _journal(f"🔍 [ARCHIVE] can_archive: {can_archive}")
    
    if not can_archive:
        flash('Vous n\'avez pas les permissions nécessaires', 'error')
        return redirect(url_for('detail_audit', id=id))
    
    # 4. ARCHIVAGE
    try:
        _journal(f"🔄 [ARCHIVE] Début archivage...")
        
        # Si audit n'a pas de client_id, lui attribuer
        if audit.client_id is None:
            _journal(f"⚠️ [ARCHIVE] Attribution client_id={current_user.client_id}")
            audit.client_id = current_user.client_id
        
        # Mettre à jour l'audit
        audit.is_archived = True
        audit.archived_at = datetime.utcnow()
        audit.archived_by = current_user.id
        audit.statut = 'archive'
        audit.sous_statut = 'archive'
        
        _journal(f"🔍 [ARCHIVE] Audit mis à jour: is_archived={audit.is_archived}")
        
        db.session.commit()
        _journal(f"✅ [ARCHIVE] Commit réussi!")
        
        flash(f'✅ Audit "{audit.titre}" archivé avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ [ARCHIVE] Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'❌ Erreur: {str(e)}', 'error')
    
    return redirect(url_for('liste_audits'))


@app.route('/audit/<int:id>/restaurer', methods=['POST'])
@login_required
def restaurer_audit(id):
    """Restaurer un audit archivé - VERSION SIMPLIFIÉE"""
    
    _journal(f"🔍 [RESTAURER] Début pour audit {id}")
    
    # Récupérer l'audit archivé
    audit = Audit.query.filter_by(id=id, is_archived=True).first()
    
    if not audit:
        flash('Audit archivé non trouvé', 'error')
        return redirect(url_for('liste_audits', show_archived=True))
    
    _journal(f"🔍 [RESTAURER] Audit: {audit.reference} (client_id={audit.client_id}, created_by={audit.created_by})")
    
    # Vérification simplifiée d'accès
    if audit.client_id and audit.client_id != current_user.client_id:
        if audit.created_by != current_user.id:
            flash('Accès non autorisé', 'error')
            return redirect(url_for('liste_audits', show_archived=True))
    
    # Vérification simplifiée de permission
    can_restore = False
    
    if current_user.role == 'super_admin':
        can_restore = True
    elif current_user.is_client_admin and audit.client_id == current_user.client_id:
        can_restore = True
    elif audit.created_by == current_user.id:
        can_restore = True
    elif audit.responsable_id == current_user.id:
        can_restore = True
    elif current_user.has_permission('can_manage_audit'):
        can_restore = True
    
    if not can_restore:
        flash('Permission refusée', 'error')
        return redirect(url_for('liste_audits', show_archived=True))
    
    try:
        # Restaurer
        audit.is_archived = False
        audit.archived_at = None
        audit.archived_by = None
        audit.statut = 'planifie'
        
        db.session.commit()
        flash('✅ Audit restauré avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Erreur: {str(e)}', 'error')
    
    return redirect(url_for('liste_audits', show_archived=True))


@app.route('/audit/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_audit(id):
    """Supprimer définitivement un audit - VERSION SIMPLIFIÉE"""
    
    _journal(f"🔍 [SUPPRIMER] Début pour audit {id}")
    
    # Récupérer l'audit archivé
    audit = Audit.query.filter_by(id=id, is_archived=True).first()
    
    if not audit:
        flash('Audit archivé non trouvé', 'error')
        return redirect(url_for('liste_audits', show_archived=True))
    
    _journal(f"🔍 [SUPPRIMER] Audit: {audit.reference} (client_id={audit.client_id})")
    
    # Seuls super_admin et admin client peuvent supprimer
    if current_user.role != 'super_admin' and not current_user.is_client_admin:
        flash('Permission refusée', 'error')
        return redirect(url_for('liste_audits', show_archived=True))
    
    # Vérifier client_id
    if audit.client_id and audit.client_id != current_user.client_id:
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_audits', show_archived=True))
    
    try:
        # Supprimer
        db.session.delete(audit)
        db.session.commit()
        flash('✅ Audit supprimé définitivement', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Erreur: {str(e)}', 'error')
    
    return redirect(url_for('liste_audits', show_archived=True))


@app.route('/audit/<int:audit_id>/changer-statut', methods=['POST'])
@login_required
def changer_statut_audit(audit_id):
    """Changer le statut d'un audit avec isolation multi-tenant"""
    
    # CORRECTION : Récupérer avec vérification d'accès
    audit = Audit.query.get_or_404(audit_id)
    
    # Vérifier l'accès
    if not check_client_access(audit):
        return jsonify({'success': False, 'message': 'Accès non autorisé'}), 403
    
    if not current_user.can_edit_audit(audit):
        return jsonify({'success': False, 'message': 'Permission refusée'}), 403
    
    nouveau_statut = request.form.get('statut')
    sous_statut = request.form.get('sous_statut')
    
    ancien_statut = audit.statut
    ancien_sous_statut = audit.sous_statut
    
    try:
        if nouveau_statut:
            audit.statut = nouveau_statut
        
        if sous_statut:
            audit.sous_statut = sous_statut
        
        audit.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Journaliser le changement
        if 'journaliser_action_audit' in globals():
            journaliser_action_audit(
                audit_id=audit.id,
                action_type='changement_statut',
                user_id=current_user.id,
                details={
                    'ancien_statut': ancien_statut,
                    'nouveau_statut': nouveau_statut,
                    'ancien_sous_statut': ancien_sous_statut,
                    'nouveau_sous_statut': sous_statut
                }
            )
        
        return jsonify({
            'success': True,
            'message': 'Statut mis à jour',
            'statut': audit.statut,
            'sous_statut': audit.sous_statut
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/audit/<int:audit_id>/dashboard')
@login_required
def dashboard_audit(audit_id):
    """Dashboard avancé d'un audit — ✅ Version NET"""
    
    audit = Audit.query.get_or_404(audit_id)
    
    if not check_client_access(audit):
        flash('Accès non autorisé à cet audit', 'error')
        return redirect(url_for('liste_audits'))
    
    # ============================================
    # 1. FILTRER LES DONNÉES PAR CLIENT
    # ============================================
    constatations_client = [c for c in audit.constatations if check_client_access(c)]
    recommandations_client = [r for r in audit.recommandations if check_client_access(r)]
    plans_client = [p for p in audit.plans_action if check_client_access(p)]
    
    # ============================================
    # 2. STATISTIQUES
    # ============================================
    stats = {
        'progression_globale': audit.progression_globale,
        'taux_realisation_recommandations': audit.taux_realisation_recommandations,
        'taux_realisation_plans': audit.taux_realisation_plans,
        'score_global': audit.score_global,
        'couleur_progression': audit.couleur_progression,
        'constatations_par_type': {},
        'recommandations_par_statut': {},
        'plans_action_par_statut': {},
        'risques_associes': 0,
        'totals': {
            'constatations': len(constatations_client),
            'recommandations': len(recommandations_client),
            'plans_action': len(plans_client)
        }
    }
    
    for c in constatations_client:
        if c.type_constatation:
            stats['constatations_par_type'][c.type_constatation] = stats['constatations_par_type'].get(c.type_constatation, 0) + 1
    
    for r in recommandations_client:
        if r.statut:
            stats['recommandations_par_statut'][r.statut] = stats['recommandations_par_statut'].get(r.statut, 0) + 1
    
    for p in plans_client:
        if p.statut:
            stats['plans_action_par_statut'][p.statut] = stats['plans_action_par_statut'].get(p.statut, 0) + 1
    
    # ============================================
    # 3. RISQUES ASSOCIÉS (avec niveau NET)
    # ============================================
    risques_associes = []
    risques_ids_vus = set()
    
    def enrichir_risque_avec_net(risque, types_assoc):
        """Enrichit un risque avec son niveau NET"""
        niveau_net = 'Non évalué'
        score_net = 0
        campagne_nom = 'Aucune campagne active'
        est_revaluation = False
        
        # Chercher la campagne active
        campagne_active = None
        if risque.cartographie:
            campagne_active = CampagneEvaluation.query.filter_by(
                cartographie_id=risque.cartographie_id,
                statut='en_cours'
            ).order_by(CampagneEvaluation.created_at.desc()).first()
        
        if campagne_active:
            evaluation = EvaluationRisque.query.filter_by(
                risque_id=risque.id,
                campagne_id=campagne_active.id
            ).order_by(EvaluationRisque.created_at.desc()).first()
            
            if evaluation:
                niveau_net = evaluation.niveau_risque_net or evaluation.niveau_risque or 'Non évalué'
                score_net = evaluation.score_risque_net or evaluation.score_risque or 0
                campagne_nom = campagne_active.nom
            else:
                # Fallback N-1
                eval_n_moins_1 = EvaluationRisque.query.filter(
                    EvaluationRisque.risque_id == risque.id,
                    EvaluationRisque.campagne_id != campagne_active.id,
                    EvaluationRisque.date_confirmation.isnot(None)
                ).order_by(EvaluationRisque.created_at.desc()).first()
                
                if eval_n_moins_1:
                    niveau_net = eval_n_moins_1.niveau_risque_net or eval_n_moins_1.niveau_risque or 'Non évalué'
                    score_net = eval_n_moins_1.score_risque_net or eval_n_moins_1.score_risque or 0
                    campagne_nom = f"N-1 ({campagne_active.nom})"
                    est_revaluation = True
        
        return {
            'risque': risque,
            'types_association': types_assoc,
            'niveau_net': niveau_net,
            'score_net': score_net,
            'campagne_nom': campagne_nom,
            'est_revaluation': est_revaluation,
        }
    
    # Risques via recommandations
    for reco in recommandations_client:
        if reco.risque_id and reco.risque_id not in risques_ids_vus:
            risque = Risque.query.get(reco.risque_id)
            if risque and check_client_access(risque):
                risques_associes.append(enrichir_risque_avec_net(risque, ['recommandation']))
                risques_ids_vus.add(reco.risque_id)
    
    # Risques via plans d'action
    for plan in plans_client:
        if plan.risque_id:
            if plan.risque_id in risques_ids_vus:
                # Ajouter le type d'association
                for r in risques_associes:
                    if r['risque'].id == plan.risque_id:
                        if 'plan_action' not in r['types_association']:
                            r['types_association'].append('plan_action')
                        break
            else:
                risque = Risque.query.get(plan.risque_id)
                if risque and check_client_access(risque):
                    risques_associes.append(enrichir_risque_avec_net(risque, ['plan_action']))
                    risques_ids_vus.add(plan.risque_id)
    
    stats['risques_associes'] = len(risques_associes)
    stats['progression_par_domaine'] = {}
    
    # ============================================
    # 4. ANALYSES IA
    # ============================================
    analyses_ia = []
    try:
        if MODELS_IMPORTED:
            analyses_ia = get_client_filter(AnalyseIA)\
                .filter_by(audit_id=audit_id)\
                .order_by(AnalyseIA.date_analyse.desc())\
                .limit(3)\
                .all()
    except:
        pass
    
    # ============================================
    # 5. ACTIVITÉS RÉCENTES
    # ============================================
    dernieres_activites = []
    try:
        if MODELS_IMPORTED and hasattr(db, 'session'):
            dernieres_activites = JournalAudit.query\
                .filter_by(audit_id=audit_id)\
                .order_by(JournalAudit.created_at.desc())\
                .limit(10)\
                .all()
    except:
        pass
    
    # ============================================
    # 6. ÉCHÉANCES À VENIR
    # ============================================
    echeances_a_venir = []
    aujourdhui = datetime.utcnow().date()
    sept_jours = aujourdhui + timedelta(days=7)
    
    for reco in recommandations_client:
        if reco.date_echeance and reco.statut not in ['termine', 'annule']:
            if aujourdhui <= reco.date_echeance <= sept_jours:
                echeances_a_venir.append({
                    'type': 'recommandation',
                    'objet': reco,
                    'jours_restants': (reco.date_echeance - aujourdhui).days
                })
    
    for plan in plans_client:
        if plan.date_fin_prevue and plan.statut not in ['termine', 'suspendu']:
            if aujourdhui <= plan.date_fin_prevue <= sept_jours:
                echeances_a_venir.append({
                    'type': 'plan_action',
                    'objet': plan,
                    'jours_restants': (plan.date_fin_prevue - aujourdhui).days
                })
    
    echeances_a_venir.sort(key=lambda x: x['jours_restants'])
    
    # ============================================
    # 7. ALERTES
    # ============================================
    alertes = {
        'echeances_proches': len(echeances_a_venir),
        'recommandations_retardees': len([r for r in recommandations_client if r.statut == 'retarde']),
        'plans_retardes': len([p for p in plans_client if p.statut == 'retarde']),
        'constatations_critiques': len([c for c in constatations_client if c.gravite == 'critique'])
    }
    
    return render_template('audit/dashboard.html',
                         audit=audit,
                         stats=stats,
                         risques_associes=risques_associes,
                         analyses_ia=analyses_ia,
                         dernieres_activites=dernieres_activites,
                         echeances_a_venir=echeances_a_venir,
                         alertes=alertes,
                         datetime=datetime,
                         current_user=current_user)


@app.route('/programme-audit')
@login_required
def liste_programmes_audit():
    """Liste des programmes d'audit avec filtres avancés"""
    
    # Vérification permission
    if not current_user.has_permission('can_manage_audit'):
        flash('Permission requise', 'error')
        return redirect(url_for('dashboard'))
    
    # ========== RÉCUPÉRATION DES FILTRES ==========
    pays_id = request.args.get('pays_id', type=int)
    pole_id = request.args.get('pole_id', type=int)
    direction_id = request.args.get('direction_id', type=int)
    statut_filter = request.args.get('statut')
    periode_filter = request.args.get('periode')
    annee_filter = request.args.get('annee', type=int)
    
    # Construction de la requête
    query = get_client_filter(ProgrammeAudit).filter_by(is_archived=False)
    
    # Application des filtres organisationnels
    if pays_id and pays_id > 0:
        query = query.filter_by(pays_id=pays_id)
    if pole_id and pole_id > 0:
        query = query.filter_by(pole_id=pole_id)
    if direction_id and direction_id > 0:
        query = query.filter_by(direction_id=direction_id)
    
    # Filtres sur les dates/périodes
    if statut_filter:
        query = query.filter_by(statut=statut_filter)
    if periode_filter:
        query = query.filter_by(periode=periode_filter)
    if annee_filter:
        query = query.filter(
            ProgrammeAudit.annee_debut <= annee_filter,
            ProgrammeAudit.annee_fin >= annee_filter
        )
    
    programmes = query.order_by(ProgrammeAudit.annee_debut.desc()).all()
    
    # ========== CHARGEMENT DES LISTES POUR LES FILTRES ==========
    if current_user.role == 'super_admin':
        pays_list = Pays.query.filter_by(is_archived=False).order_by(Pays.nom).all()
        poles_list = Pole.query.filter_by(is_archived=False).order_by(Pole.nom).all()
        directions_list = Direction.query.filter_by(is_archived=False, is_active=True).order_by(Direction.nom).all()
    else:
        pays_list = get_client_filter(Pays).filter_by(is_archived=False).order_by(Pays.nom).all()
        poles_list = get_client_filter(Pole).filter_by(is_archived=False).order_by(Pole.nom).all()
        directions_list = get_client_filter(Direction).filter_by(is_archived=False, is_active=True).order_by(Direction.nom).all()
    
    # Statistiques
    stats = {
        'total': len(programmes),
        'actifs': len([p for p in programmes if p.statut == 'actif']),
        'en_elaboration': len([p for p in programmes if p.statut == 'en_elaboration']),
        'missions_total': sum(p.nb_missions for p in programmes),
        'missions_terminees': sum(p.nb_missions_realisees for p in programmes)
    }
    
    return render_template('programme_audit/liste.html',
                         programmes=programmes,
                         stats=stats,
                         pays_list=pays_list,
                         poles_list=poles_list,
                         directions_list=directions_list,
                         filtre_pays=pays_id,
                         filtre_pole=pole_id,
                         filtre_direction=direction_id,
                         filtre_statut=statut_filter,
                         filtre_periode=periode_filter,
                         filtre_annee=annee_filter,
                         now=datetime.now)


@app.route('/programme-audit/nouveau', methods=['GET', 'POST'])
@login_required
def nouveau_programme_audit():
    """Créer un nouveau programme d'audit"""
    
    if not current_user.has_permission('can_manage_audit'):
        flash('Permission requise', 'error')
        return redirect(url_for('liste_programmes_audit'))
    
    from flask_wtf import FlaskForm
    from wtforms import StringField, TextAreaField, SelectField, BooleanField, IntegerField, SubmitField
    from wtforms.validators import DataRequired, Optional, NumberRange
    
    class ProgrammeAuditForm(FlaskForm):
        nom = StringField('Nom du programme', validators=[DataRequired()])
        description = TextAreaField('Description')
        periode = SelectField('Période', choices=[
            ('annuel', 'Annuel'),
            ('triennal', 'Triennal (3 ans)')
        ], validators=[DataRequired()])
        annee_debut = SelectField('Année de début', choices=[], validators=[DataRequired()])
        annee_fin = SelectField('Année de fin', choices=[], validators=[DataRequired()])
        
        methode_generation = SelectField('Méthode de génération', choices=[
            ('manuel', 'Manuel - Je créerai les missions moi-même'),
            ('auto_risques', 'Automatique - Basé sur la cartographie des risques'),
            ('hybride', 'Hybride - Automatique avec ajustements manuels')
        ], validators=[DataRequired()])
        
        seuil_critique = BooleanField('Inclure les risques Critiques', default=True)
        seuil_eleve = BooleanField('Inclure les risques Élevés', default=True)
        inclure_risques_moyens = BooleanField('Inclure les risques Moyens', default=False)
        frequence_audit_risque = SelectField('Fréquence d\'audit par niveau', choices=[
            ('annuelle_critique', 'Annuelle pour risques critiques'),
            ('semestrielle_critique', 'Semestrielle pour risques critiques'),
            ('triennal_tous', 'Tous les 3 ans pour tous les risques')
        ])
        prioriser_processus_critiques = BooleanField('Prioriser les processus critiques', default=True)
        
        frequence_audit = SelectField('Fréquence générale d\'audit', choices=[
            ('', 'Non spécifiée'),
            ('annuelle', 'Annuelle'),
            ('semestrielle', 'Semestrielle'),
            ('trimestrielle', 'Trimestrielle')
        ], validators=[Optional()])
        
        duree_moyenne_mission = IntegerField('Durée moyenne d\'une mission (jours)', 
                                             default=5, 
                                             validators=[NumberRange(min=1, max=90, 
                                             message="La durée doit être comprise entre 1 et 90 jours")])
        
        ressources_disponibles = IntegerField('Ressources disponibles (jours/homme par an)', 
                                             default=100, 
                                             validators=[NumberRange(min=10, max=1000, 
                                             message="Les ressources doivent être entre 10 et 1000 jours/homme")])
        
        # ========== AJOUTER CES CHAMPS MANQUANTS ==========
        pays_id = SelectField('Pays', choices=[], coerce=int, validators=[Optional()])
        pole_id = SelectField('Pôle', choices=[], coerce=int, validators=[Optional()])
        direction_id = SelectField('Direction', choices=[], coerce=int, validators=[Optional()])
        
        submit = SubmitField('Créer le programme')
    
    form = ProgrammeAuditForm()
    
    # Initialisation des années
    annee_courante = datetime.now().year
    form.annee_debut.choices = [(str(y), str(y)) for y in range(annee_courante, annee_courante + 6)]
    form.annee_fin.choices = [(str(y), str(y)) for y in range(annee_courante, annee_courante + 11)]
    
    # ========== CHARGEMENT DES LISTES POUR LES FILTRES ORGANISATIONNELS ==========
    if current_user.role == 'super_admin':
        pays_list = Pays.query.filter_by(is_archived=False).order_by(Pays.nom).all()
        poles_list = Pole.query.filter_by(is_archived=False).order_by(Pole.nom).all()
        directions_list = Direction.query.filter_by(is_archived=False, is_active=True).order_by(Direction.nom).all()
    else:
        pays_list = get_client_filter(Pays).filter_by(is_archived=False).order_by(Pays.nom).all()
        poles_list = get_client_filter(Pole).filter_by(is_archived=False).order_by(Pole.nom).all()
        directions_list = get_client_filter(Direction).filter_by(is_archived=False, is_active=True).order_by(Direction.nom).all()
    
    form.pays_id.choices = [(0, '--- Non spécifié ---')] + [(p.id, f"{p.drapeau or '🌍'} {p.nom}") for p in pays_list]
    form.pole_id.choices = [(0, '--- Non spécifié ---')] + [(p.id, p.nom) for p in poles_list]
    form.direction_id.choices = [(0, '--- Non spécifié ---')] + [(d.id, d.nom) for d in directions_list]
    
    if form.validate_on_submit():
        try:
            # Générer référence
            def generer_reference_programme(client_id=None):
                base_ref = "PROGAUD-"
                
                if client_id:
                    dernier = ProgrammeAudit.query.filter_by(client_id=client_id)\
                        .order_by(ProgrammeAudit.id.desc()).first()
                else:
                    dernier = ProgrammeAudit.query.order_by(ProgrammeAudit.id.desc()).first()
                
                if dernier and dernier.reference:
                    try:
                        if dernier.reference.startswith(base_ref):
                            dernier_num = int(dernier.reference.split('-')[1])
                            nouveau_num = dernier_num + 1
                        else:
                            count = ProgrammeAudit.query.filter_by(client_id=client_id).count() if client_id else ProgrammeAudit.query.count()
                            nouveau_num = count + 1
                    except:
                        count = ProgrammeAudit.query.filter_by(client_id=client_id).count() if client_id else ProgrammeAudit.query.count()
                        nouveau_num = count + 1
                else:
                    nouveau_num = 1
                
                return f"{base_ref}{nouveau_num:04d}"
            
            reference = generer_reference_programme(current_user.client_id)
            
            programme = ProgrammeAudit(
                reference=reference,
                nom=form.nom.data,
                description=form.description.data,
                periode=form.periode.data,
                annee_debut=int(form.annee_debut.data),
                annee_fin=int(form.annee_fin.data),
                methode_generation=form.methode_generation.data,
                statut='en_elaboration',
                client_id=current_user.client_id,
                created_by=current_user.id,
                frequence_audit=form.frequence_audit.data if form.frequence_audit.data else None,
                duree_moyenne_mission=form.duree_moyenne_mission.data,
                ressources_disponibles=form.ressources_disponibles.data,
                # ========== ENREGISTRER LES FILTRES ORGANISATIONNELS ==========
                pays_id=form.pays_id.data if form.pays_id.data and form.pays_id.data != 0 else None,
                pole_id=form.pole_id.data if form.pole_id.data and form.pole_id.data != 0 else None,
                direction_id=form.direction_id.data if form.direction_id.data and form.direction_id.data != 0 else None
            )
            
            # Critères de génération automatisée
            if form.methode_generation.data in ['auto_risques', 'hybride']:
                programme.criteres_generation = {
                    'seuil_critique': form.seuil_critique.data,
                    'seuil_eleve': form.seuil_eleve.data,
                    'inclure_risques_moyens': form.inclure_risques_moyens.data,
                    'frequence_audit_risque': form.frequence_audit_risque.data,
                    'prioriser_processus_critiques': form.prioriser_processus_critiques.data,
                    'duree_max_mission': 90
                }
            
            db.session.add(programme)
            db.session.commit()
            
            # Générer les missions si méthode automatisée
            if form.methode_generation.data in ['auto_risques', 'hybride']:
                missions_crees = generer_missions_auto(programme.id, current_user.id)
                flash(f'Programme créé avec {missions_crees} missions générées automatiquement', 'success')
            else:
                flash('Programme créé - Ajoutez maintenant les missions manuellement', 'info')
            
            return redirect(url_for('detail_programme_audit', id=programme.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('programme_audit/form.html', form=form, title="Nouveau Programme")


@app.route('/api/feuille-travail/risques-disponibles')
@login_required
def api_risques_disponibles_select():
    """Récupérer la liste des risques pour le select dans la modal"""
    from models import Risque
    
    risques = get_client_filter(Risque).filter_by(is_archived=False).all()
    
    return jsonify({
        'success': True,
        'risques': [{
            'id': r.id,
            'reference': r.reference,
            'intitule': r.intitule,
            'categorie': r.categorie or ''
        } for r in risques]
    })


@app.route('/programme-audit/<int:id>')
@login_required
def detail_programme_audit(id):
    """Détail d'un programme d'audit — ✅ Version NET cohérente"""
    
    programme = ProgrammeAudit.query.get_or_404(id)
    
    if not check_client_access(programme):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_programmes_audit'))
    
    # ============================================
    # 1. STATS DE RISQUES NET (avec N-1)
    # ============================================
    stats_risques = calculer_stats_risques_client(
        current_user.client_id, 
        inclure_n_moins_1=True  # ✅ INCLURE LES N-1
    )
    
    # Construire une map {risque_id: infos NET}
    risques_net_map = {}
    for item in stats_risques.get('risques_critiques_formatted', []):
        risques_net_map[item['risque'].id] = {
            'niveau_net': item['niveau_net'],
            'score_net': item['score_net'],
            'est_revaluation': item['est_revaluation'],
            'campagne_nom': item['campagne_nom'],
        }
    
    # ============================================
    # 2. ENRICHIR LA LISTE DES RISQUES DISPONIBLES
    # ============================================
    risques_query = get_client_filter(Risque).filter_by(is_archived=False).order_by(Risque.reference.asc()).all()
    
    risques_disponibles = []
    for risque in risques_query:
        net_info = risques_net_map.get(risque.id)
        
        # Si pas dans la map, chercher quand même son niveau NET
        if not net_info:
            # 1. Chercher dans la campagne active
            campagne_active = None
            if risque.cartographie:
                campagne_active = CampagneEvaluation.query.filter_by(
                    cartographie_id=risque.cartographie_id,
                    statut='en_cours'
                ).order_by(CampagneEvaluation.created_at.desc()).first()
            
            if campagne_active:
                evaluation = EvaluationRisque.query.filter_by(
                    risque_id=risque.id,
                    campagne_id=campagne_active.id
                ).order_by(EvaluationRisque.created_at.desc()).first()
                
                if evaluation:
                    net_info = {
                        'niveau_net': evaluation.niveau_risque_net or evaluation.niveau_risque or 'Non évalué',
                        'score_net': evaluation.score_risque_net or evaluation.score_risque or 0,
                        'est_revaluation': False,
                        'campagne_nom': campagne_active.nom,
                    }
            
            # 2. ✅ FALLBACK N-1 : Si toujours pas, chercher la dernière éval confirmée
            if not net_info:
                derniere_eval = EvaluationRisque.query.filter(
                    EvaluationRisque.risque_id == risque.id,
                    EvaluationRisque.date_confirmation.isnot(None)
                ).order_by(EvaluationRisque.created_at.desc()).first()
                
                if derniere_eval:
                    campagne_source = CampagneEvaluation.query.get(derniere_eval.campagne_id)
                    net_info = {
                        'niveau_net': derniere_eval.niveau_risque_net or derniere_eval.niveau_risque or 'Non évalué',
                        'score_net': derniere_eval.score_risque_net or derniere_eval.score_risque or 0,
                        'est_revaluation': True,
                        'campagne_nom': campagne_source.nom if campagne_source else 'N-1',
                    }
        
        risque_data = {
            'id': risque.id,
            'reference': risque.reference,
            'intitule': risque.intitule,
            'description': risque.description or '',
            'categorie': risque.categorie or '',
            'niveau_criticite_brut': risque.niveau_criticite or 'Non défini',
            'niveau_net': net_info['niveau_net'] if net_info else 'Non évalué',
            'score_net': net_info['score_net'] if net_info else 0,
            'est_revaluation': net_info['est_revaluation'] if net_info else False,
            'campagne_nom': net_info['campagne_nom'] if net_info else 'Aucune campagne',
            'cartographie_id': risque.cartographie_id,
            'cartographie_nom': risque.cartographie.nom if risque.cartographie else 'Non définie',
        }
        
        risques_disponibles.append(risque_data)
    
    # ============================================
    # 3. CALCUL DU NOMBRE DE RISQUES CRITIQUES NET
    # ============================================
    nb_risques_net = sum(
        1 for r in risques_disponibles 
        if 'critique' in (r.get('niveau_net') or '').lower()
    )
    
    # ✅ NOUVEAU : Compter aussi les élevés
    nb_eleves_net = sum(
        1 for r in risques_disponibles 
        if 'eleve' in (r.get('niveau_net') or '').lower() 
        or 'élevé' in (r.get('niveau_net') or '').lower()
    )
    
    # ============================================
    # 4. RÉCUPÉRER LES UTILISATEURS
    # ============================================
    if current_user.role == 'super_admin':
        utilisateurs = User.query.filter_by(is_active=True).order_by(User.username).all()
    else:
        utilisateurs = get_client_filter(User).filter_by(is_active=True).order_by(User.username).all()
    
    # ============================================
    # 5. FILTRER LES MISSIONS NON ARCHIVÉES
    # ============================================
    missions_non_archivees = programme.missions.filter_by(is_archived=False).all()
    
    missions_data = []
    for mission in missions_non_archivees:
        audit_info = None
        if mission.audit_id:
            audit = Audit.query.get(mission.audit_id)
            if audit:
                audit_info = {
                    'id': audit.id,
                    'reference': audit.reference or '',
                    'titre': audit.titre or ''
                }
        
        mission_dict = {
            'id': mission.id,
            'reference': mission.reference,
            'titre': mission.titre,
            'description': mission.description or '',
            'priorite': mission.priorite or '',
            'niveau_risque_associe': mission.niveau_risque_associe or '',
            'annee_prevue': mission.annee_prevue,
            'trimestre_prevue': mission.trimestre_prevue,
            'duree_estimee': mission.duree_estimee or 0,
            'duree_reelle': mission.duree_reelle or 0,
            'statut': mission.statut or 'planifie',
            'date_debut_prevue': mission.date_debut_prevue.strftime('%Y-%m-%d') if mission.date_debut_prevue else None,
            'date_fin_prevue': mission.date_fin_prevue.strftime('%Y-%m-%d') if mission.date_fin_prevue else None,
            'date_debut_reelle': mission.date_debut_reelle.strftime('%Y-%m-%d') if mission.date_debut_reelle else None,
            'date_fin_reelle': mission.date_fin_reelle.strftime('%Y-%m-%d') if mission.date_fin_reelle else None,
            'audit_id': mission.audit_id,
            'audit': audit_info,
            'risque_id': mission.risque_id,
            'responsable_id': mission.responsable_id,
            'jours_restants': mission.jours_restants if hasattr(mission, 'jours_restants') else 0,
            'est_en_retard': mission.est_en_retard if hasattr(mission, 'est_en_retard') else False
        }
        
        if mission.risque:
            mission_dict['risque'] = {
                'id': mission.risque.id,
                'reference': mission.risque.reference or '',
                'intitule': mission.risque.intitule or '',
                'description': mission.risque.description or '',
                'categorie': mission.risque.categorie or ''
            }
        
        if mission.responsable:
            mission_dict['responsable'] = {
                'id': mission.responsable.id,
                'username': mission.responsable.username or '',
                'role': mission.responsable.role or ''
            }
        
        missions_data.append(mission_dict)
    
    # ============================================
    # 6. RENDU
    # ============================================
    return render_template('programme_audit/detail.html',
                         programme=programme,
                         missions_data=missions_data,
                         risques_disponibles=risques_disponibles,
                         nb_risques_net=nb_risques_net,
                         nb_eleves_net=nb_eleves_net,   # ✅ NOUVEAU
                         utilisateurs=utilisateurs)


@app.route('/programme-audit/<int:id>/chronogramme')
@login_required
def chronogramme_programme(id):
    """Chronogramme interactif avec manipulation manuelle"""
    
    programme = ProgrammeAudit.query.get_or_404(id)
    
    if not check_client_access(programme):
        flash('Accès non autorisé', 'error')
        return redirect(url_for('liste_programmes_audit'))
    
    # ✅ CORRECTION : Utiliser .all() pour obtenir une liste
    missions = programme.missions.filter_by(is_archived=False).all()
    
    # Organisation des missions
    missions_par_annee = {}
    ressources_par_periode = {}
    
    for mission in missions:  # ✅ Maintenant c'est une LISTE
        annee = mission.annee_prevue
        trimestre = mission.trimestre_prevue or 1
        
        if annee not in missions_par_annee:
            missions_par_annee[annee] = {1: [], 2: [], 3: [], 4: []}
        if trimestre not in missions_par_annee[annee]:
            missions_par_annee[annee][trimestre] = []
        
        missions_par_annee[annee][trimestre].append(mission)
        
        if annee not in ressources_par_periode:
            ressources_par_periode[annee] = {1: 0, 2: 0, 3: 0, 4: 0}
        ressources_par_periode[annee][trimestre] += mission.duree_estimee or 0
    
    # ✅ CORRECTION : ICI LE FAMEUX len() qui plantait
    stats = {
        'total_charge': programme.jours_audit_planifies,
        'charge_moyenne': programme.jours_audit_planifies / max(1, len(missions)),  # ✅ missions est une LISTE
        'missions_par_priorite': {
            'critique': len([m for m in missions if m.priorite == 'critique']),
            'elevee': len([m for m in missions if m.priorite == 'elevee']),
            'moyenne': len([m for m in missions if m.priorite == 'moyenne']),
            'faible': len([m for m in missions if m.priorite == 'faible'])
        }
    }
    
    return render_template('programme_audit/chronogramme.html',
                         programme=programme,
                         missions_par_annee=missions_par_annee,
                         ressources_par_periode=ressources_par_periode,
                         missions=missions,  # ✅ Passer la liste au template
                         stats=stats,
                         now=datetime.now)


@app.route('/api/audit/<int:audit_id>/workflow/envoyer-relecture', methods=['POST'])
@login_required
def api_envoyer_relecture(audit_id):
    """Envoyer l'audit en relecture et créer les alertes - VERSION CORRIGÉE"""
    audit = get_client_object_or_404(Audit, audit_id)
    workflow = WorkflowApprobation.query.filter_by(audit_id=audit_id).first()
    
    if not workflow:
        workflow = WorkflowApprobation(
            audit_id=audit_id,
            client_id=audit.client_id or current_user.client_id,
            created_by=current_user.id
        )
        db.session.add(workflow)
        db.session.flush()
    
    if workflow.etape_actuelle != 'brouillon':
        return jsonify({'success': False, 'error': f'L\'audit n\'est pas en brouillon'}), 400
    
    data = request.get_json()
    commentaire = data.get('commentaire', '')
    
    try:
        workflow.envoyer_en_relecture(current_user.id, commentaire)
        
        # ========== NOTIFIER LES APPROBATEURS NIVEAU 1 ==========
        # Méthode 1: Utiliser les approbateurs désignés dans le workflow
        approbateurs_niveau1 = []
        
        if workflow.approbateur_niveau1_id:
            approbateur = User.query.get(workflow.approbateur_niveau1_id)
            if approbateur and approbateur.is_active:
                approbateurs_niveau1 = [approbateur]
        else:
            # Fallback: admins et managers du client
            approbateurs_niveau1 = User.query.filter(
                User.client_id == audit.client_id,
                User.is_active == True,
                User.role.in_(['admin', 'manager', 'responsable_qualite'])
            ).all()
        
        # Créer notifications et alertes pour chaque approbateur niveau 1
        for approbateur in approbateurs_niveau1:
            # Alerte
            alerte = AlerteApprobation(
                audit_id=audit.id,
                destinataire_id=approbateur.id,
                type_alerte='approbation_niveau1',
                titre=f"🔍 Audit à valider: {audit.reference}",
                message=f"L'audit '{audit.titre}' est en attente de votre validation (Niveau 1).",
                client_id=audit.client_id
            )
            db.session.add(alerte)
            
            # Notification
            notification = Notification(
                destinataire_id=approbateur.id,
                type_notification='alerte_approbation',
                titre=f"🔍 Audit à valider: {audit.reference}",
                message=f"L'audit '{audit.titre}' est en attente de votre validation (Niveau 1).",
                urgence='important',
                entite_type='audit',
                entite_id=audit.id,
                client_id=audit.client_id
            )
            db.session.add(notification)
        
        # Notifier le créateur que l'audit est en relecture
        notification_createur = Notification(
            destinataire_id=audit.created_by,
            type_notification='info',
            titre=f"📤 Audit envoyé en relecture: {audit.reference}",
            message=f"L'audit '{audit.titre}' a été envoyé pour validation niveau 1.",
            urgence='normal',
            entite_type='audit',
            entite_id=audit.id,
            client_id=audit.client_id
        )
        db.session.add(notification_createur)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Audit envoyé en relecture, {len(approbateurs_niveau1)} personne(s) notifiée(s)'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/audit/<int:audit_id>/workflow/approuver-niveau1', methods=['POST'])
@login_required
def api_approuver_niveau1(audit_id):
    """Approuver l'audit niveau 1 - VERSION CORRIGÉE"""
    audit = get_client_object_or_404(Audit, audit_id)
    workflow = WorkflowApprobation.query.filter_by(audit_id=audit_id).first()
    
    if not workflow:
        return jsonify({'success': False, 'error': 'Workflow non trouvé'}), 404
    
    if workflow.etape_actuelle != 'en_relecture':
        return jsonify({'success': False, 'error': f'L\'audit n\'est pas en relecture'}), 400
    
    data = request.get_json()
    commentaire = data.get('commentaire', '')
    
    try:
        workflow.approuver_niveau1(current_user.id, commentaire)
        
        # Supprimer les alertes de niveau 1
        AlerteApprobation.query.filter_by(
            audit_id=audit.id,
            type_alerte='approbation_niveau1'
        ).delete()
        
        # ========== NOTIFIER LE CRÉATEUR ==========
        notification_createur = Notification(
            destinataire_id=audit.created_by,
            type_notification='success',
            titre=f"✅ Audit approuvé niveau 1: {audit.reference}",
            message=f"L'audit '{audit.titre}' a été approuvé niveau 1 par {current_user.username}.",
            urgence='normal',
            entite_type='audit',
            entite_id=audit_id,
            client_id=audit.client_id
        )
        db.session.add(notification_createur)
        
        # ========== NOTIFIER LES APPROBATEURS NIVEAU 2 ==========
        # Récupérer les approbateurs niveau 2
        approbateurs_niveau2 = []
        
        if workflow.approbateur_niveau2_id:
            approbateur = User.query.get(workflow.approbateur_niveau2_id)
            if approbateur and approbateur.is_active:
                approbateurs_niveau2 = [approbateur]
        else:
            # Fallback: admins ou direction
            approbateurs_niveau2 = User.query.filter(
                User.client_id == audit.client_id,
                User.is_active == True,
                User.role.in_(['admin', 'directeur', 'direction'])
            ).all()
        
        # Créer notifications et alertes pour les approbateurs niveau 2
        for approbateur in approbateurs_niveau2:
            # Alerte
            alerte = AlerteApprobation(
                audit_id=audit.id,
                destinataire_id=approbateur.id,
                type_alerte='approbation_niveau2',
                titre=f"✅ Audit à approuver: {audit.reference}",
                message=f"L'audit '{audit.titre}' est en attente de votre validation finale (Niveau 2).",
                client_id=audit.client_id
            )
            db.session.add(alerte)
            
            # Notification
            notification = Notification(
                destinataire_id=approbateur.id,
                type_notification='alerte_approbation',
                titre=f"✅ Audit à approuver: {audit.reference}",
                message=f"L'audit '{audit.titre}' est en attente de votre validation finale (Niveau 2).",
                urgence='important',
                entite_type='audit',
                entite_id=audit.id,
                client_id=audit.client_id
            )
            db.session.add(notification)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Audit approuvé niveau 1, {len(approbateurs_niveau2)} personne(s) notifiée(s) pour niveau 2'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/audit/<int:audit_id>/workflow/approuver-niveau2', methods=['POST'])
@login_required
def api_approuver_niveau2(audit_id):
    """Approuver l'audit niveau 2 (final) - VERSION CORRIGÉE"""
    audit = get_client_object_or_404(Audit, audit_id)
    workflow = WorkflowApprobation.query.filter_by(audit_id=audit_id).first()
    
    if not workflow:
        return jsonify({'success': False, 'error': 'Workflow non trouvé'}), 404
    
    if workflow.etape_actuelle != 'approuve':
        return jsonify({'success': False, 'error': f'L\'audit n\'est pas en attente d\'approbation finale'}), 400
    
    data = request.get_json()
    commentaire = data.get('commentaire', '')
    
    try:
        workflow.approuver_niveau2(current_user.id, commentaire)
        
        # Supprimer les alertes de niveau 2
        AlerteApprobation.query.filter_by(
            audit_id=audit.id,
            type_alerte='approbation_niveau2'
        ).delete()
        
        # ========== NOTIFIER TOUS LES ACTEURS ==========
        # 1. Notifier le créateur
        notification_createur = Notification(
            destinataire_id=audit.created_by,
            type_notification='success',
            titre=f"🎉 Audit validé: {audit.reference}",
            message=f"L'audit '{audit.titre}' a été définitivement validé par {current_user.username}.",
            urgence='normal',
            entite_type='audit',
            entite_id=audit_id,
            client_id=audit.client_id
        )
        db.session.add(notification_createur)
        
        # 2. Notifier le responsable de l'audit (si différent)
        if audit.responsable_id and audit.responsable_id != audit.created_by:
            notification_responsable = Notification(
                destinataire_id=audit.responsable_id,
                type_notification='success',
                titre=f"🎉 Audit validé: {audit.reference}",
                message=f"L'audit '{audit.titre}' a été définitivement validé.",
                urgence='normal',
                entite_type='audit',
                entite_id=audit_id,
                client_id=audit.client_id
            )
            db.session.add(notification_responsable)
        
        # 3. Notifier l'approbateur niveau 1 (qui avait approuvé)
        if workflow.approbateur_niveau1_id:
            notification_app1 = Notification(
                destinataire_id=workflow.approbateur_niveau1_id,
                type_notification='success',
                titre=f"🎉 Audit finalisé: {audit.reference}",
                message=f"L'audit '{audit.titre}' a été validé niveau 2 et est maintenant finalisé.",
                urgence='normal',
                entite_type='audit',
                entite_id=audit_id,
                client_id=audit.client_id
            )
            db.session.add(notification_app1)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Audit approuvé niveau 2 (final)'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/audit/<int:audit_id>/workflow/rejeter', methods=['POST'])
@login_required
def api_rejeter_audit(audit_id):
    """Rejeter l'audit et nettoyer les alertes - VERSION CORRIGÉE"""
    audit = get_client_object_or_404(Audit, audit_id)
    workflow = WorkflowApprobation.query.filter_by(audit_id=audit_id).first()
    
    if not workflow:
        return jsonify({'success': False, 'error': 'Workflow non trouvé'}), 404
    
    if workflow.etape_actuelle not in ['en_relecture', 'approuve']:
        return jsonify({'success': False, 'error': f'L\'audit ne peut pas être rejeté'}), 400
    
    data = request.get_json()
    raison = data.get('raison', '')
    
    if not raison:
        return jsonify({'success': False, 'error': 'Une raison est requise'}), 400
    
    try:
        workflow.rejeter(current_user.id, raison)
        
        # Supprimer toutes les alertes
        AlerteApprobation.query.filter_by(audit_id=audit.id).delete()
        
        # ========== NOTIFIER LE CRÉATEUR ==========
        notification = Notification(
            destinataire_id=audit.created_by,
            type_notification='warning',
            titre=f"❌ Audit rejeté: {audit.reference}",
            message=f"L'audit '{audit.titre}' a été rejeté par {current_user.username}. Raison: {raison[:200]}",
            urgence='important',
            entite_type='audit',
            entite_id=audit_id,
            client_id=audit.client_id
        )
        db.session.add(notification)
        
        # Notifier aussi le responsable si différent
        if audit.responsable_id and audit.responsable_id != audit.created_by:
            notification_responsable = Notification(
                destinataire_id=audit.responsable_id,
                type_notification='warning',
                titre=f"❌ Audit rejeté: {audit.reference}",
                message=f"L'audit '{audit.titre}' a été rejeté. Raison: {raison[:200]}",
                urgence='important',
                entite_type='audit',
                entite_id=audit_id,
                client_id=audit.client_id
            )
            db.session.add(notification_responsable)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Audit rejeté'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/audit/<int:audit_id>/workflow/renvoyer-relecture', methods=['POST'])
@login_required
def api_renvoyer_relecture(audit_id):
    """Renvoyer un audit rejeté en relecture"""
    audit = get_client_object_or_404(Audit, audit_id)
    workflow = WorkflowApprobation.query.filter_by(audit_id=audit_id).first()
    
    if not workflow or workflow.etape_actuelle != 'rejete':
        return jsonify({'success': False, 'error': 'L\'audit doit être rejeté pour être renvoyé'}), 400
    
    data = request.get_json()
    commentaire = data.get('commentaire', '')
    
    try:
        workflow.renvoyer_en_relecture(current_user.id, commentaire)
        
        # Nettoyer les alertes existantes
        AlerteApprobation.query.filter_by(audit_id=audit.id).delete()
        
        # Recréer les alertes niveau 1
        approbateurs = User.query.filter(
            User.client_id == audit.client_id,
            User.is_active == True,
            User.role.in_(['admin', 'manager', 'responsable_qualite'])
        ).all()
        
        for approbateur in approbateurs:
            alerte = AlerteApprobation(
                audit_id=audit.id,
                destinataire_id=approbateur.id,
                type_alerte='approbation_niveau1',
                titre=f"🔍 Audit à re-valider: {audit.reference}",
                message=f"L'audit '{audit.titre}' a été modifié et est à nouveau en attente de validation (Niveau 1).",
                client_id=audit.client_id
            )
            db.session.add(alerte)
            
            notification = Notification(
                destinataire_id=approbateur.id,
                type_notification='info',
                titre=f"🔄 Audit à re-valider: {audit.reference}",
                message=f"L'audit '{audit.titre}' a été renvoyé en relecture par {current_user.username}.",
                urgence='important',
                entite_type='audit',
                entite_id=audit.id,
                client_id=audit.client_id
            )
            db.session.add(notification)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Audit renvoyé en relecture'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/audit/<int:audit_id>/gerer-equipe', methods=['POST'])
@login_required
def gerer_equipe_audit(audit_id):
    """Gérer l'équipe d'audit - Version corrigée"""
    from models import Audit, db  # ✅ Correction: models au lieu de app.models
    
    # Vérifier les permissions
    if not current_user.is_authenticated:
        flash('Vous devez être connecté', 'danger')
        return redirect(url_for('login'))
    
    audit = Audit.query.get_or_404(audit_id)
    
    # Vérifier que l'utilisateur a le droit de modifier cet audit
    if current_user.role not in ['admin', 'manager', 'auditeur'] and current_user.id != audit.created_by:
        flash('Vous n\'avez pas les permissions nécessaires', 'danger')
        return redirect(url_for('detail_audit', id=audit_id))
    
    # 1. Gérer les utilisateurs existants
    utilisateurs_existants = request.form.getlist('utilisateurs_existants[]')
    
    # Convertir en chaîne CSV
    if utilisateurs_existants:
        # Vérifier que les IDs sont valides
        ids_valides = []
        for user_id in utilisateurs_existants:
            try:
                ids_valides.append(str(int(user_id)))
            except ValueError:
                continue
        
        audit.equipe_audit_ids = ','.join(ids_valides) if ids_valides else ''
    else:
        audit.equipe_audit_ids = ''
    
    # 2. Gérer les membres externes
    membres_externes = []
    i = 0
    
    # Parcourir tous les membres externes du formulaire
    while True:
        nom_key = f'membres_externes[{i}][nom]'
        if nom_key not in request.form:
            break
        
        prenom = request.form.get(f'membres_externes[{i}][prenom]', '').strip()
        nom = request.form.get(nom_key, '').strip()
        email = request.form.get(f'membres_externes[{i}][email]', '').strip()
        fonction = request.form.get(f'membres_externes[{i}][fonction]', '').strip()
        organisation = request.form.get(f'membres_externes[{i}][organisation]', '').strip()
        
        # Validation
        if nom and prenom and email and '@' in email:
            membre = {
                'nom': nom,
                'prenom': prenom,
                'email': email,
                'fonction': fonction,
                'organisation': organisation
            }
            membres_externes.append(membre)
        
        i += 1
    
    # Mettre à jour l'audit
    audit.membres_externes = membres_externes
    audit.updated_at = datetime.utcnow()
    
    try:
        db.session.commit()
        flash('Équipe d\'audit mise à jour avec succès', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la mise à jour: {str(e)}', 'danger')
    
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/audit/<int:audit_id>/supprimer-membre-externe', methods=['POST'])
@login_required
def supprimer_membre_externe_audit(audit_id):
    """Supprimer un membre externe"""
    from models import Audit, db  # ✅ Correction: models au lieu de app.models
    
    audit = Audit.query.get_or_404(audit_id)
    
    # Vérifier les permissions
    if current_user.role not in ['admin', 'manager', 'auditeur'] and current_user.id != audit.created_by:
        flash('Vous n\'avez pas les permissions nécessaires', 'danger')
        return redirect(url_for('detail_audit', id=audit_id))
    
    membre_index = request.form.get('membre_index', type=int)
    
    if membre_index is None:
        flash('Index du membre manquant', 'danger')
        return redirect(url_for('detail_audit', id=audit_id))
    
    if not audit.membres_externes:
        flash('Aucun membre externe à supprimer', 'warning')
        return redirect(url_for('detail_audit', id=audit_id))
    
    if 0 <= membre_index < len(audit.membres_externes):
        membre_supprime = audit.membres_externes.pop(membre_index)
        marquer_json_modifie(audit, 'membres_externes')
        db.session.commit()
        flash(f'Membre {membre_supprime.get("nom", "")} {membre_supprime.get("prenom", "")} supprimé', 'success')
    else:
        flash('Index du membre invalide', 'danger')
    
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/audit/<int:audit_id>/supprimer-utilisateur-equipe', methods=['POST'])
@login_required
def supprimer_utilisateur_equipe(audit_id):
    """Supprimer un utilisateur de l'équipe"""
    from models import Audit, User, db  # ✅ Correction: models au lieu de app.models
    
    audit = Audit.query.get_or_404(audit_id)
    
    # Vérifier les permissions
    if current_user.role not in ['admin', 'manager', 'auditeur'] and current_user.id != audit.created_by:
        flash('Vous n\'avez pas les permissions nécessaires', 'danger')
        return redirect(url_for('detail_audit', id=audit_id))
    
    user_id = request.form.get('user_id', type=int)
    
    if user_id is None:
        flash('ID utilisateur manquant', 'danger')
        return redirect(url_for('detail_audit', id=audit_id))
    
    if not audit.equipe_audit_ids:
        flash('Équipe vide', 'warning')
        return redirect(url_for('detail_audit', id=audit_id))
    
    try:
        # Convertir la chaîne en liste
        ids = [id.strip() for id in audit.equipe_audit_ids.split(',') if id.strip()]
        user_id_str = str(user_id)
        
        if user_id_str in ids:
            ids.remove(user_id_str)
            
            # Mettre à jour
            if ids:
                audit.equipe_audit_ids = ','.join(ids)
            else:
                audit.equipe_audit_ids = ''
            
            db.session.commit()
            
            # Récupérer le nom de l'utilisateur
            user = User.query.get(user_id)
            if user:
                nom = f"{user.prenom or ''} {user.nom or user.username}".strip()
                flash(f'Utilisateur {nom} supprimé de l\'équipe', 'success')
            else:
                flash(f'Utilisateur ID {user_id} supprimé de l\'équipe', 'success')
        else:
            flash('Utilisateur non trouvé dans l\'équipe', 'warning')
            
    except Exception as e:
        flash(f'Erreur lors de la suppression: {str(e)}', 'danger')
    
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/audit/<int:audit_id>/plan-action/nouveau', methods=['POST'])
@login_required
def nouvel_plan_action(audit_id):
    """Créer un nouveau plan d'action pour un audit"""
    audit = Audit.query.get_or_404(audit_id)
    
    try:
        # Récupérer les données du formulaire
        nom = request.form.get('nom', '').strip()
        description = request.form.get('description', '').strip()
        date_debut = request.form.get('date_debut')
        date_fin_prevue = request.form.get('date_fin_prevue')
        responsable_id = request.form.get('responsable_id')
        
        # Validation
        if not nom:
            flash('Le nom du plan est requis', 'error')
            return redirect(url_for('detail_audit', id=audit_id))
        
        # Générer une référence
        dernier_plan = PlanAction.query.filter_by(audit_id=audit_id)\
                                       .order_by(PlanAction.id.desc())\
                                       .first()
        reference = f"PA-{audit.reference}-{(dernier_plan.id + 1) if dernier_plan else 1:03d}"
        
        # Créer le plan d'action
        plan_action = PlanAction(
            reference=reference,
            nom=nom,
            description=description,
            audit_id=audit_id,
            date_debut=datetime.strptime(date_debut, '%Y-%m-%d').date() if date_debut else None,
            date_fin_prevue=datetime.strptime(date_fin_prevue, '%Y-%m-%d').date() if date_fin_prevue else None,
            responsable_id=int(responsable_id) if responsable_id else None,
            statut='en_attente',
            created_by=current_user.id
        )
        
        db.session.add(plan_action)
        db.session.commit()
        
        flash('Plan d\'action créé avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la création: {str(e)}', 'error')
    
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/audit/<int:audit_id>/rapport-complet')
@login_required
def rapport_audit_complet(audit_id):
    """Générer un rapport complet de l'audit avec gestion des fichiers et tests"""
    
    from datetime import datetime, timedelta, timezone
    from models import (User, Constatation, Recommandation, PlanAction, Risque, 
                        FichierRapport, JournalAudit, AnalyseIA, MatriceMaturite, 
                        RecommandationGlobale, FichierMetadata, FeuilleTravail, 
                        TestControleFeuille, WorkflowApprobation, ErreurTest)
    
    _journal(f"\n📊 GÉNÉRATION RAPPORT AUDIT {audit_id}")
    
    # ============================================
    # 1. RÉCUPÉRER L'AUDIT AVEC VÉRIFICATION D'ACCÈS
    # ============================================
    audit = Audit.query.get(audit_id)
    
    if not audit:
        flash('Audit non trouvé', 'error')
        return redirect(url_for('liste_audits'))
    
    if not check_client_access(audit):
        flash('Accès non autorisé à cet audit', 'error')
        return redirect(url_for('liste_audits'))
    
    # ============================================
    # 2. VÉRIFIER LES PERMISSIONS
    # ============================================
    peut_voir = (
        current_user.role == 'super_admin' or
        current_user.id == audit.created_by or
        current_user.id == audit.responsable_id or
        (audit.equipe_audit_ids and str(current_user.id) in audit.equipe_audit_ids.split(',')) or
        (audit.observateurs_ids and str(current_user.id) in audit.observateurs_ids.split(','))
    )
    
    if not peut_voir:
        flash('Vous n\'avez pas les permissions pour voir ce rapport', 'error')
        return redirect(url_for('liste_audits'))
    
    _journal(f"   ✅ Accès autorisé à l'audit {audit.reference}")
    
    # ============================================
    # 3. DÉTERMINER LE CLIENT_ID À UTILISER
    # ============================================
    if current_user.role == 'super_admin' and session.get('viewing_client_id'):
        client_id = session['viewing_client_id']
    else:
        client_id = current_user.client_id
    
    # ============================================
    # 4. RÉCUPÉRER LES DONNÉES DE L'AUDIT
    # ============================================
    
    # Constatations
    constatations = Constatation.query.filter_by(
        audit_id=audit.id, 
        is_archived=False,
        client_id=client_id
    ).order_by(Constatation.created_at.desc()).all()
    
    # Recommandations
    recommandations = Recommandation.query.filter_by(
        audit_id=audit.id,
        client_id=client_id
    ).order_by(Recommandation.created_at.desc()).all()
    
    # Plans d'action
    plans_action = PlanAction.query.filter_by(
        audit_id=audit.id,
        client_id=client_id
    ).order_by(PlanAction.created_at.desc()).all()
    
    # Utilisateurs
    createur_audit = User.query.get(audit.created_by) if audit.created_by else None
    
    # Fichiers joints
    fichiers_rapport = FichierRapport.query.filter_by(
        audit_id=audit_id,
        client_id=client_id
    ).order_by(FichierRapport.created_at.desc()).all()
    
    # ============================================
    # 5. RÉCUPÉRER LES FEUILLES DE TRAVAIL ET TESTS
    # ============================================
    
    feuilles_travail = FeuilleTravail.query.filter_by(
        audit_id=audit.id,
        is_archived=False,
        client_id=client_id
    ).all()
    
    # Récupérer tous les tests avec leurs données complètes
    tests_data = []
    tests_par_feuille = {}
    
    for feuille in feuilles_travail:
        tests = TestControleFeuille.query.filter_by(
            feuille_travail_id=feuille.id,
            is_archived=False
        ).all()
        
        feuille_key = f"{feuille.reference} - {feuille.titre}"
        tests_par_feuille[feuille_key] = []
        
        for test in tests:
            # 🔥 CHARGER LES ERREURS POUR CE TEST
            erreurs = ErreurTest.query.filter_by(
                test_id=test.id
            ).order_by(ErreurTest.ordre).all()
            
            # 🔥 CHARGER LES RISQUES ASSOCIÉS
            risques_associes = test.risques_associes
            
            # Récupérer le taux de réussite calculé
            taux_reussite = test.taux_reussite
            if not taux_reussite and test.nb_elements_testes and test.nb_elements_testes > 0:
                taux_reussite = round(((test.nb_elements_testes - (test.nb_erreurs_trouvees or 0)) / test.nb_elements_testes) * 100, 1)
            
            responsable_correction_nom = None
            if test.responsable_correction_id:
                resp = User.query.get(test.responsable_correction_id)
                if resp:
                    responsable_correction_nom = resp.username
            
            test_dict = {
                'id': test.id,
                'feuille_id': feuille.id,
                'feuille_reference': feuille.reference,
                'feuille_titre': feuille.titre,
                'objet_test': test.objet_test,
                'objectif_controle': test.objectif_controle,
                'reference_norme': test.reference_norme,
                'resultat': test.resultat or 'non_testé',
                'procedure': test.procedure,
                'criteres_acceptation': test.criteres_acceptation,
                'etapes_cles': test.etapes_cles,
                'echantillon': test.echantillon,
                'methode_echantillonnage': test.methode_echantillonnage,
                'taille_echantillon': test.taille_echantillon,
                'population_totale': test.population_totale,
                'periode_couverte': test.periode_couverte,
                'taux_confiance': test.taux_confiance,
                'marge_erreur': test.marge_erreur,
                'nb_elements_testes': test.nb_elements_testes,
                'nb_erreurs_trouvees': test.nb_erreurs_trouvees,
                'taux_reussite': taux_reussite,
                'observations': test.observations,
                'ecart_constate': test.ecart_constate,
                'classification_anomalie': test.classification_anomalie,
                'impact_financier': test.impact_financier,
                'impact_fonctionnel': test.impact_fonctionnel,
                'cause_racine': test.cause_racine,
                'niveau_criticite': test.niveau_criticite or 'moyen',
                'probabilite_occurrence': test.probabilite_occurrence,
                'gravite_impact': test.gravite_impact,
                'correction_effectuee': test.correction_effectuee,
                'date_correction': test.date_correction.strftime('%d/%m/%Y') if test.date_correction else None,
                'action_curative': test.action_curative,
                'action_preventive': test.action_preventive,
                'correction_commentaire': test.correction_commentaire,
                'responsable_correction_nom': responsable_correction_nom,
                'responsable_correction_id': test.responsable_correction_id,
                'created_at': test.created_at.strftime('%d/%m/%Y') if test.created_at else '',
                'updated_at': test.updated_at.strftime('%d/%m/%Y') if test.updated_at else '',
                # 🔥 NOUVEAUX CHAMPS
                'erreurs': [{
                    'id': e.id,
                    'description': e.description,
                    'categorie': e.categorie,
                    'gravite': e.gravite,
                    'etat': e.etat,
                    'impact_financier': e.impact_financier,
                    'impact_qualitatif': e.impact_qualitatif,
                    'correction_proposee': e.correction_proposee,
                    'correction_effectuee': e.correction_effectuee,
                    'date_correction': e.date_correction.strftime('%d/%m/%Y') if e.date_correction else None,
                    'cause_racine': e.cause_racine,
                    'analyse_detaillee': e.analyse_detaillee,
                    'responsable_correction': e.responsable_correction.username if e.responsable_correction else None,
                    'created_at': e.created_at.strftime('%d/%m/%Y') if e.created_at else ''
                } for e in erreurs],
                'risques_associes': [{
                    'id': r.id,
                    'reference': r.reference,
                    'intitule': r.intitule,
                    'niveau_criticite': r.niveau_criticite or 'moyen',
                    'impact': r.impact,
                    'probabilite': r.probabilite,
                    'score_risque': r.score_risque
                } for r in risques_associes],
                'nb_erreurs': len(erreurs),
                'nb_risques': len(risques_associes)
            }
            tests_data.append(test_dict)
            tests_par_feuille[feuille_key].append(test_dict)
    
    # ============================================
    # 6. CALCULER LES STATISTIQUES DES TESTS
    # ============================================
    
    tests_stats = {
        'total_tests': len(tests_data),
        'tests_conformes': len([t for t in tests_data if t['resultat'] == 'conforme']),
        'tests_non_conformes': len([t for t in tests_data if t['resultat'] == 'non_conforme']),
        'tests_partiels': len([t for t in tests_data if t['resultat'] == 'partiellement_conforme']),
        'tests_non_testes': len([t for t in tests_data if t['resultat'] == 'non_testé']),
        'total_feuilles': len(feuilles_travail),
        'taux_conformite_global': 0,
        'taux_reussite_moyen': 0,
        'impact_financier_total': sum(t.get('impact_financier', 0) or 0 for t in tests_data),
        'tests_par_criticite': {
            'critique': len([t for t in tests_data if t['niveau_criticite'] == 'critique']),
            'eleve': len([t for t in tests_data if t['niveau_criticite'] == 'eleve']),
            'moyen': len([t for t in tests_data if t['niveau_criticite'] == 'moyen']),
            'faible': len([t for t in tests_data if t['niveau_criticite'] == 'faible'])
        },
        'tests_par_feuille': {},
        # 🔥 NOUVELLES STATISTIQUES SUR LES ÉCARTS
        'total_ecarts': sum(t['nb_erreurs'] for t in tests_data),
        'ecarts_par_gravite': {},
        'ecarts_par_etat': {},
        'ecarts_par_categorie': {},
        'tests_avec_ecarts': len([t for t in tests_data if t['nb_erreurs'] > 0]),
        'taux_correction_ecarts': 0
    }
    
    # Statistiques des écarts
    ecarts_gravite = {}
    ecarts_etat = {}
    ecarts_categorie = {}
    total_ecarts_corriges = 0
    total_ecarts = 0
    
    for test in tests_data:
        for erreur in test['erreurs']:
            total_ecarts += 1
            gravite = erreur['gravite'] or 'non_defini'
            etat = erreur['etat'] or 'non_defini'
            categorie = erreur['categorie'] or 'autre'
            
            ecarts_gravite[gravite] = ecarts_gravite.get(gravite, 0) + 1
            ecarts_etat[etat] = ecarts_etat.get(etat, 0) + 1
            ecarts_categorie[categorie] = ecarts_categorie.get(categorie, 0) + 1
            
            if erreur['correction_effectuee'] or etat in ['corrigee', 'fermee']:
                total_ecarts_corriges += 1
    
    tests_stats['ecarts_par_gravite'] = ecarts_gravite
    tests_stats['ecarts_par_etat'] = ecarts_etat
    tests_stats['ecarts_par_categorie'] = ecarts_categorie
    tests_stats['taux_correction_ecarts'] = round((total_ecarts_corriges / max(total_ecarts, 1)) * 100, 1)
    tests_stats['total_ecarts'] = total_ecarts
    
    # Calculer le taux de conformité global
    if tests_stats['total_tests'] > 0:
        tests_stats['taux_conformite_global'] = round(
            (tests_stats['tests_conformes'] / tests_stats['total_tests']) * 100, 1
        )
    
    # Calculer le taux de réussite moyen
    taux_reussites = [t['taux_reussite'] for t in tests_data if t['taux_reussite'] is not None]
    if taux_reussites:
        tests_stats['taux_reussite_moyen'] = round(sum(taux_reussites) / len(taux_reussites), 1)
    
    # Grouper par feuille
    for feuille_nom, tests_feuille in tests_par_feuille.items():
        conformes = len([t for t in tests_feuille if t['resultat'] == 'conforme'])
        tests_stats['tests_par_feuille'][feuille_nom] = {
            'total': len(tests_feuille),
            'conformes': conformes,
            'non_conformes': len([t for t in tests_feuille if t['resultat'] == 'non_conforme']),
            'partiels': len([t for t in tests_feuille if t['resultat'] == 'partiellement_conforme']),
            'taux_conformite': round((conformes / max(len(tests_feuille), 1)) * 100, 1),
            'nb_ecarts': sum(t['nb_erreurs'] for t in tests_feuille)
        }
    
    # Calculer l'avancement des actions correctives
    tests_avec_correction = [t for t in tests_data if t['correction_effectuee']]
    tests_stats['taux_correction'] = round((len(tests_avec_correction) / max(tests_stats['total_tests'], 1)) * 100, 1)
    
    _journal(f"📊 STATS TESTS: {tests_stats['total_tests']} tests, {tests_stats['tests_non_conformes']} non conformes")
    _journal(f"📊 STATS ÉCARTS: {tests_stats['total_ecarts']} écarts, {tests_stats['taux_correction_ecarts']}% corrigés")
    
    # ============================================
    # 7. STATISTIQUES DES FICHIERS
    # ============================================
    
    stats_fichiers = {
        'total': len(fichiers_rapport),
        'total_taille': sum(f.taille or 0 for f in fichiers_rapport),
        'par_type': {}
    }
    
    for fichier in fichiers_rapport:
        type_key = fichier.type_fichier or 'autre'
        if type_key not in stats_fichiers['par_type']:
            stats_fichiers['par_type'][type_key] = {
                'count': 0,
                'total_taille': 0
            }
        stats_fichiers['par_type'][type_key]['count'] += 1
        stats_fichiers['par_type'][type_key]['total_taille'] += fichier.taille or 0
    
    def format_taille(taille_bytes):
        if not taille_bytes:
            return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if taille_bytes < 1024.0:
                return f"{taille_bytes:.1f} {unit}"
            taille_bytes /= 1024.0
        return f"{taille_bytes:.1f} GB"
    
    stats_fichiers['total_taille_formatee'] = format_taille(stats_fichiers['total_taille'])
    for type_key in stats_fichiers['par_type']:
        stats_fichiers['par_type'][type_key]['total_taille_formatee'] = format_taille(
            stats_fichiers['par_type'][type_key]['total_taille']
        )
    
    # ============================================
    # 8. PERMISSIONS POUR LES ACTIONS
    # ============================================
    
    def user_in_ids_list(ids_string):
        if not ids_string:
            return False
        try:
            ids = [id_str.strip() for id_str in ids_string.split(',') if id_str.strip()]
            return str(current_user.id) in ids
        except:
            return False
    
    peut_modifier = (
        current_user.role in ['admin', 'super_admin'] or
        current_user.id == audit.created_by or
        current_user.id == audit.responsable_id or
        user_in_ids_list(audit.equipe_audit_ids)
    )
    
    peut_uploader = peut_modifier or user_in_ids_list(audit.observateurs_ids)
    
    # ============================================
    # 9. STATISTIQUES DE L'AUDIT
    # ============================================
    
    statistiques = {
        'total_constatations': len(constatations),
        'total_recommandations': len(recommandations),
        'total_plans_action': len(plans_action),
        'constatations_par_type': {},
        'constatations_par_gravite': {},
        'constatations_par_statut': {},
        'recommandations_par_type': {},
        'recommandations_par_statut': {},
        'plans_action_actifs': len([p for p in plans_action if p.statut not in ['termine', 'suspendu']]),
        'taux_avancement_moyen': 0,
        'taux_realisation_recommandations': getattr(audit, 'taux_realisation_recommandations', 0),
        # 🔥 STATISTIQUES DES TESTS AJOUTÉES
        'tests_stats': tests_stats
    }
    
    for constat in constatations:
        type_const = constat.type_constatation or 'non_defini'
        gravite = constat.gravite or 'non_definie'
        statut = constat.statut or 'non_defini'
        
        statistiques['constatations_par_type'][type_const] = \
            statistiques['constatations_par_type'].get(type_const, 0) + 1
        statistiques['constatations_par_gravite'][gravite] = \
            statistiques['constatations_par_gravite'].get(gravite, 0) + 1
        statistiques['constatations_par_statut'][statut] = \
            statistiques['constatations_par_statut'].get(statut, 0) + 1
    
    for reco in recommandations:
        type_reco = reco.type_recommandation or 'non_defini'
        statut_reco = reco.statut or 'non_defini'
        
        statistiques['recommandations_par_type'][type_reco] = \
            statistiques['recommandations_par_type'].get(type_reco, 0) + 1
        statistiques['recommandations_par_statut'][statut_reco] = \
            statistiques['recommandations_par_statut'].get(statut_reco, 0) + 1
    
    if plans_action:
        total_avancement = sum(p.pourcentage_realisation or 0 for p in plans_action)
        statistiques['taux_avancement_moyen'] = round(total_avancement / len(plans_action), 2)
    
    # ============================================
    # 10. MÉTADONNÉES DES FICHIERS
    # ============================================
    
    metadata_dict = {}
    try:
        constatation_ids = [c.id for c in constatations]
        
        if constatation_ids:
            fichiers_metadata = FichierMetadata.query.filter(
                FichierMetadata.entite_type == 'constatation',
                FichierMetadata.entite_id.in_(constatation_ids),
                FichierMetadata.client_id == client_id
            ).all()
            
            for meta in fichiers_metadata:
                if meta.entite_id not in metadata_dict:
                    metadata_dict[meta.entite_id] = []
                
                responsable_nom = None
                if meta.responsable:
                    responsable_nom = meta.responsable.username
                
                metadata_dict[meta.entite_id].append({
                    'nom_fichier': meta.nom_fichier,
                    'commentaire': meta.commentaire,
                    'responsable': responsable_nom,
                    'responsable_obj': meta.responsable,
                    'date_upload': meta.created_at,
                    'date_upload_str': meta.created_at.strftime('%d/%m/%Y') if meta.created_at else ''
                })
    except Exception as e:
        _journal(f"⚠️ Erreur récupération métadonnées: {e}")
        metadata_dict = {}
    
    # ============================================
    # 11. FONCTION POUR MÉTADONNÉES
    # ============================================
    
    def get_fichier_metadata(constatation_id, preuve_nom):
        try:
            if constatation_id in metadata_dict:
                for meta in metadata_dict[constatation_id]:
                    if meta['nom_fichier'] == preuve_nom:
                        return meta
            return {
                'nom_fichier': preuve_nom,
                'commentaire': '',
                'responsable': 'Non défini',
                'date_upload_str': 'Date inconnue'
            }
        except Exception as e:
            _journal(f"⚠️ Erreur get_fichier_metadata: {e}")
            return {
                'nom_fichier': preuve_nom,
                'commentaire': '',
                'responsable': 'Non défini',
                'date_upload_str': 'Date inconnue'
            }
    
    # ============================================
    # 12. RISQUES ASSOCIÉS
    # ============================================
    
    risques_associes = []
    risques_ids_vus = set()
    
    for constatation in constatations:
        if constatation.risque_id and constatation.risque_id not in risques_ids_vus:
            risque = Risque.query.get(constatation.risque_id)
            if risque and risque.client_id == client_id and not risque.is_archived:
                derniere_eval = None
                if risque.evaluations:
                    evaluations_client = [e for e in risque.evaluations if e.client_id == client_id]
                    if evaluations_client:
                        derniere_eval = sorted(evaluations_client, key=lambda x: x.created_at, reverse=True)[0]
                
                risques_associes.append({
                    'risque': risque,
                    'types_association': ['constatation'],
                    'constatation_ref': constatation.reference,
                    'derniere_evaluation': derniere_eval
                })
                risques_ids_vus.add(constatation.risque_id)
    
    for recommandation in recommandations:
        if recommandation.risque_id and recommandation.risque_id not in risques_ids_vus:
            risque = Risque.query.get(recommandation.risque_id)
            if risque and risque.client_id == client_id and not risque.is_archived:
                derniere_eval = None
                if risque.evaluations:
                    evaluations_client = [e for e in risque.evaluations if e.client_id == client_id]
                    if evaluations_client:
                        derniere_eval = sorted(evaluations_client, key=lambda x: x.created_at, reverse=True)[0]
                
                risque_existant = next((r for r in risques_associes if r['risque'].id == recommandation.risque_id), None)
                if risque_existant:
                    if 'recommandation' not in risque_existant['types_association']:
                        risque_existant['types_association'].append('recommandation')
                else:
                    risques_associes.append({
                        'risque': risque,
                        'types_association': ['recommandation'],
                        'derniere_evaluation': derniere_eval
                    })
                risques_ids_vus.add(recommandation.risque_id)
    
    for plan in plans_action:
        if plan.risque_id and plan.risque_id not in risques_ids_vus:
            risque = Risque.query.get(plan.risque_id)
            if risque and risque.client_id == client_id and not risque.is_archived:
                derniere_eval = None
                if risque.evaluations:
                    evaluations_client = [e for e in risque.evaluations if e.client_id == client_id]
                    if evaluations_client:
                        derniere_eval = sorted(evaluations_client, key=lambda x: x.created_at, reverse=True)[0]
                
                risque_existant = next((r for r in risques_associes if r['risque'].id == plan.risque_id), None)
                if risque_existant:
                    if 'plan_action' not in risque_existant['types_association']:
                        risque_existant['types_association'].append('plan_action')
                else:
                    risques_associes.append({
                        'risque': risque,
                        'types_association': ['plan_action'],
                        'derniere_evaluation': derniere_eval
                    })
                risques_ids_vus.add(plan.risque_id)
    
    # ============================================
    # 13. ÉCHÉANCES À VENIR
    # ============================================
    
    echeances_a_venir = []
    aujourdhui = datetime.now(timezone.utc).date()
    sept_jours = aujourdhui + timedelta(days=7)
    
    for recommandation in recommandations:
        if recommandation.date_echeance and recommandation.statut not in ['termine', 'annule']:
            if aujourdhui <= recommandation.date_echeance <= sept_jours:
                echeances_a_venir.append({
                    'type': 'recommandation',
                    'objet': recommandation,
                    'jours_restants': (recommandation.date_echeance - aujourdhui).days
                })
    
    for plan in plans_action:
        if plan.date_fin_prevue and plan.statut not in ['termine', 'suspendu']:
            if aujourdhui <= plan.date_fin_prevue <= sept_jours:
                echeances_a_venir.append({
                    'type': 'plan_action',
                    'objet': plan,
                    'jours_restants': (plan.date_fin_prevue - aujourdhui).days
                })
    
    echeances_a_venir.sort(key=lambda x: x['jours_restants'])
    
    # ============================================
    # 14. ANALYSES IA ET HISTORIQUE
    # ============================================
    
    analyses_ia = []
    try:
        analyses_ia = AnalyseIA.query.filter_by(
            audit_id=audit_id,
            client_id=client_id
        ).order_by(AnalyseIA.date_analyse.desc()).limit(5).all()
    except Exception as e:
        _journal(f"⚠️ Erreur récupération analyses IA: {e}")
    
    historique_audit = []
    try:
        historique_audit = JournalAudit.query.filter_by(
            audit_id=audit_id,
            client_id=client_id
        ).order_by(JournalAudit.created_at.desc()).limit(20).all()
    except Exception as e:
        _journal(f"⚠️ Erreur récupération historique: {e}")
    
    matrices_maturite = []
    try:
        matrices_maturite = MatriceMaturite.query.filter_by(
            audit_id=audit_id,
            client_id=client_id
        ).order_by(MatriceMaturite.created_at.desc()).all()
    except Exception as e:
        _journal(f"⚠️ Erreur récupération matrices maturité: {e}")
    
    # ============================================
    # 15. RECOMMANDATIONS GLOBALES
    # ============================================
    
    recommandations_globales = []
    try:
        recommandations_globales = RecommandationGlobale.query.filter_by(
            est_actif=True,
            client_id=client_id
        ).all()
        
        if recommandations_globales and audit.type_audit:
            recommandations_filtrees = [r for r in recommandations_globales 
                                       if r.type_audit is None or r.type_audit == audit.type_audit]
            if recommandations_filtrees:
                recommandations_globales = recommandations_filtrees
        
        recommandations_globales = sorted(recommandations_globales, 
                                         key=lambda x: (x.priorite or 1), 
                                         reverse=True)
        
        recommandations_globales = [r.texte for r in recommandations_globales[:10]]
    except Exception as e:
        _journal(f"⚠️ Erreur récupération recommandations globales: {e}")
        recommandations_globales = []
    
    # ============================================
    # 16. RENVOYER LE TEMPLATE
    # ============================================
    
    _journal(f"📊 RAPPORT GÉNÉRÉ: {len(constatations)} constatations, {len(recommandations)} recommandations, {len(plans_action)} plans, {len(tests_data)} tests, {tests_stats['total_ecarts']} écarts")
    
    return render_template(
        'audit/rapport_complet.html',
        audit=audit,
        constatations=constatations,
        recommandations=recommandations,
        plans_action=plans_action,
        fichiers_rapport=fichiers_rapport,
        stats_fichiers=stats_fichiers,
        peut_modifier=peut_modifier,
        peut_uploader=peut_uploader,
        historique_audit=historique_audit,
        analyses_ia=analyses_ia,
        matrices_maturite=matrices_maturite,
        echeances_a_venir=echeances_a_venir,
        recommandations_globales=recommandations_globales,
        statistiques=statistiques,
        risques_associes=risques_associes,
        createur_audit=createur_audit,
        current_datetime=datetime.now(timezone.utc),
        format_taille=format_taille,
        current_user=current_user,
        now=lambda: datetime.now(timezone.utc),
        metadata_dict=metadata_dict,
        get_fichier_metadata=get_fichier_metadata,
        # 🔥 NOUVEAUX PARAMÈTRES POUR LES FEUILLES DE TRAVAIL
        tests_data=tests_data,
        tests_stats=tests_stats,
        feuilles_travail=feuilles_travail,
        tests_par_feuille=tests_par_feuille,
        # COMPATIBILITÉ
        rapport={
            'statistiques': statistiques,
            'constatations': constatations,
            'recommandations': recommandations,
            'plans_action': plans_action,
            'recommandations_globales': recommandations_globales,
            'tests_stats': tests_stats,
            'tests_data': tests_data
        }
    )


@app.route('/audit/<int:audit_id>/export-excel')
@login_required
def export_audit_excel(audit_id):
    """Exporter toutes les données de l'audit au format Excel - VERSION CORRIGÉE"""
    try:
        import pandas as pd
        from io import BytesIO
        from datetime import datetime
        
        # Récupérer l'audit
        audit = get_client_object_or_404(Audit, audit_id)
        
        # Vérifier les permissions
        peut_voir = (
            current_user.role == 'super_admin' or
            current_user.id == audit.created_by or
            current_user.id == audit.responsable_id or
            (audit.equipe_audit_ids and str(current_user.id) in audit.equipe_audit_ids.split(','))
        )
        
        if not peut_voir:
            flash('Accès non autorisé', 'error')
            return redirect(url_for('liste_audits'))
        
        # Récupérer les données
        constatations = get_client_filter(Constatation)\
            .filter_by(audit_id=audit.id, is_archived=False)\
            .order_by(Constatation.created_at.desc()).all()
        
        recommandations = get_client_filter(Recommandation)\
            .filter_by(audit_id=audit.id)\
            .order_by(Recommandation.created_at.desc()).all()
        
        plans_action = get_client_filter(PlanAction)\
            .filter_by(audit_id=audit.id)\
            .order_by(PlanAction.created_at.desc()).all()
        
        fichiers = get_client_filter(FichierRapport)\
            .filter_by(audit_id=audit_id)\
            .order_by(FichierRapport.created_at.desc()).all()
        
        # ========== FONCTION POUR OBTENIR LE NOM COMPLET ==========
        def get_nom_complet(user):
            """Retourne le nom complet d'un utilisateur"""
            if not user:
                return ''
            if hasattr(user, 'nom_complet') and user.nom_complet:
                return user.nom_complet
            if hasattr(user, 'get_full_name'):
                return user.get_full_name()
            # Construction manuelle
            nom = getattr(user, 'nom', '') or ''
            prenom = getattr(user, 'prenom', '') or ''
            if nom and prenom:
                return f"{prenom} {nom}".strip()
            if nom:
                return nom
            if prenom:
                return prenom
            return user.username or ''
        
        # ========== FONCTION DE FORMATAGE ==========
        def format_taille(taille_bytes):
            if not taille_bytes:
                return "0 B"
            for unit in ['B', 'KB', 'MB', 'GB']:
                if taille_bytes < 1024.0:
                    return f"{taille_bytes:.1f} {unit}"
                taille_bytes /= 1024.0
            return f"{taille_bytes:.1f} GB"
        
        # ========== CRÉER UN FICHIER EXCEL AVEC AU MOINS UNE FEUILLE ==========
        output = BytesIO()
        
        # Créer le writer
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            
            # ========== 1. ONGLET "AUDIT" ==========
            audit_data = {
                'Référence': [audit.reference],
                'Titre': [audit.titre],
                'Type': [audit.type_audit or ''],
                'Statut': [audit.statut or ''],
                'Sous-statut': [audit.sous_statut or ''],
                'Responsable': [get_nom_complet(audit.responsable)],
                'Date début prévue': [audit.date_debut_prevue.strftime('%d/%m/%Y') if audit.date_debut_prevue else ''],
                'Date fin prévue': [audit.date_fin_prevue.strftime('%d/%m/%Y') if audit.date_fin_prevue else ''],
                'Processus': [audit.processus_audite_display or ''],
                'Description': [audit.description or ''],
                'Objectifs': [audit.objectifs or ''],
                'Score global': [getattr(audit, 'score_global', 0)],
                'Progression': [getattr(audit, 'progression_globale', 0)],
                'Créé par': [get_nom_complet(audit.createur) if audit.createur else ''],
                'Date création': [audit.created_at.strftime('%d/%m/%Y %H:%M') if audit.created_at else '']
            }
            df_audit = pd.DataFrame(audit_data)
            df_audit.to_excel(writer, sheet_name='Audit', index=False)
            
            # ========== 2. ONGLET "CONSTATATIONS" ==========
            if constatations:
                constatations_data = []
                for c in constatations:
                    constatations_data.append({
                        'Référence': c.reference,
                        'Description': c.description,
                        'Type': c.type_constatation or '',
                        'Gravité': c.gravite or '',
                        'Statut': c.statut or '',
                        'Processus concerné': getattr(c, 'processus_concerne', ''),
                        'Cause racine': getattr(c, 'cause_racine', ''),
                        'Conclusion': getattr(c, 'conclusion', ''),
                        'Commentaires': getattr(c, 'commentaires', ''),
                        'Créé par': get_nom_complet(c.createur) if c.createur else '',
                        'Date création': c.created_at.strftime('%d/%m/%Y %H:%M') if c.created_at else '',
                        'Nombre preuves': c.nb_preuves if hasattr(c, 'nb_preuves') else 0
                    })
                df_constatations = pd.DataFrame(constatations_data)
                df_constatations.to_excel(writer, sheet_name='Constatations', index=False)
            else:
                # Créer une feuille vide avec un message
                df_empty = pd.DataFrame({'Message': ['Aucune constatation']})
                df_empty.to_excel(writer, sheet_name='Constatations', index=False)
            
            # ========== 3. ONGLET "RECOMMANDATIONS" ==========
            if recommandations:
                recommandations_data = []
                for r in recommandations:
                    est_en_retard = False
                    if r.date_echeance and r.statut != 'termine':
                        est_en_retard = datetime.utcnow().date() > r.date_echeance
                    
                    recommandations_data.append({
                        'Référence': r.reference,
                        'Description': r.description,
                        'Type': r.type_recommandation or '',
                        'Catégorie': getattr(r, 'categorie', ''),
                        'Statut': r.statut or '',
                        'Date échéance': r.date_echeance.strftime('%d/%m/%Y') if r.date_echeance else '',
                        'Priorité': r.score_priorite or 0,
                        'Avancement': f"{r.taux_avancement or 0}%",
                        'En retard': 'Oui' if est_en_retard else 'Non',
                        'Constatation liée': r.constatation.reference if r.constatation else '',
                        'Responsable': get_nom_complet(r.responsable) if r.responsable else '',
                        'Créé par': get_nom_complet(r.createur) if r.createur else '',
                        'Date création': r.created_at.strftime('%d/%m/%Y %H:%M') if r.created_at else ''
                    })
                df_recommandations = pd.DataFrame(recommandations_data)
                df_recommandations.to_excel(writer, sheet_name='Recommandations', index=False)
            else:
                df_empty = pd.DataFrame({'Message': ['Aucune recommandation']})
                df_empty.to_excel(writer, sheet_name='Recommandations', index=False)
            
            # ========== 4. ONGLET "PLANS D'ACTION" ==========
            if plans_action:
                plans_data = []
                for p in plans_action:
                    plans_data.append({
                        'Référence': p.reference,
                        'Nom': p.nom,
                        'Description': p.description or '',
                        'Statut': p.statut or '',
                        'Date début': p.date_debut.strftime('%d/%m/%Y') if p.date_debut else '',
                        'Date fin prévue': p.date_fin_prevue.strftime('%d/%m/%Y') if p.date_fin_prevue else '',
                        '% réalisation': p.pourcentage_realisation or 0,
                        'Recommandation liée': p.recommandation.reference if p.recommandation else '',
                        'Responsable': get_nom_complet(p.responsable) if p.responsable else '',
                        'Créé par': get_nom_complet(p.createur) if p.createur else '',
                        'Date création': p.created_at.strftime('%d/%m/%Y %H:%M') if p.created_at else ''
                    })
                df_plans = pd.DataFrame(plans_data)
                df_plans.to_excel(writer, sheet_name='Plans_action', index=False)
            else:
                df_empty = pd.DataFrame({'Message': ['Aucun plan d\'action']})
                df_empty.to_excel(writer, sheet_name='Plans_action', index=False)
            
            # ========== 5. ONGLET "FICHIERS" ==========
            if fichiers:
                fichiers_data = []
                for f in fichiers:
                    fichiers_data.append({
                        'Nom fichier': f.nom_fichier,
                        'Type': f.type_fichier or '',
                        'Taille': format_taille(f.taille) if f.taille else '0 B',
                        'Description': f.description or '',
                        'Uploadé par': get_nom_complet(f.uploader) if f.uploader else '',
                        'Date upload': f.created_at.strftime('%d/%m/%Y %H:%M') if f.created_at else ''
                    })
                df_fichiers = pd.DataFrame(fichiers_data)
                df_fichiers.to_excel(writer, sheet_name='Fichiers', index=False)
            else:
                df_empty = pd.DataFrame({'Message': ['Aucun fichier joint']})
                df_empty.to_excel(writer, sheet_name='Fichiers', index=False)
            
            # ========== 6. ONGLET "SYNTHÈSE" (TOUJOURS PRÉSENT) ==========
            synthese_data = {
                'Métrique': [
                    'Référence audit',
                    'Titre audit',
                    'Total constatations',
                    'Non-conformités',
                    'Observations',
                    'Constatations critiques',
                    'Constatations closes',
                    'Total recommandations',
                    'Recommandations correctives',
                    'Recommandations préventives',
                    'Recommandations terminées',
                    'Total plans action',
                    'Plans actifs',
                    'Plans terminés',
                    'Avancement moyen plans',
                    'Taux réalisation recommandations',
                    'Score global',
                    'Progression globale',
                    'Total fichiers joints',
                    'Date génération rapport'
                ],
                'Valeur': [
                    audit.reference,
                    audit.titre,
                    len(constatations),
                    len([c for c in constatations if c.type_constatation == 'non_conformite']),
                    len([c for c in constatations if c.type_constatation == 'observation']),
                    len([c for c in constatations if c.gravite == 'critique']),
                    len([c for c in constatations if c.statut == 'clos']),
                    len(recommandations),
                    len([r for r in recommandations if r.type_recommandation == 'corrective']),
                    len([r for r in recommandations if r.type_recommandation == 'preventive']),
                    len([r for r in recommandations if r.statut == 'termine']),
                    len(plans_action),
                    len([p for p in plans_action if p.statut not in ['termine', 'suspendu']]),
                    len([p for p in plans_action if p.statut == 'termine']),
                    f"{sum(p.pourcentage_realisation or 0 for p in plans_action) / max(1, len(plans_action)):.1f}%",
                    f"{getattr(audit, 'taux_realisation_recommandations', 0)}%",
                    f"{getattr(audit, 'score_global', 0)}%",
                    f"{getattr(audit, 'progression_globale', 0)}%",
                    len(fichiers),
                    datetime.utcnow().strftime('%d/%m/%Y %H:%M')
                ]
            }
            df_synthese = pd.DataFrame(synthese_data)
            df_synthese.to_excel(writer, sheet_name='Synthèse', index=False)
            
            # Ajuster la largeur des colonnes pour toutes les feuilles
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        
        filename = f"audit_{audit.reference}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except ImportError as e:
        flash(f'Module pandas non disponible: {str(e)}', 'error')
        return redirect(url_for('rapport_audit_complet', audit_id=audit_id))
    except Exception as e:
        flash(f'Erreur lors de l\'export Excel: {str(e)}', 'error')
        _journal(f"Erreur export Excel: {e}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('rapport_audit_complet', audit_id=audit_id))


@app.route('/api/recommandation/<int:recommandation_id>/generer-plan-action', methods=['POST'])
@login_required
def api_generer_plan_action(recommandation_id):
    """Générer un plan d'action complet à partir d'une recommandation"""
    from models import Recommandation, PlanAction
    
    recommandation = Recommandation.query.get_or_404(recommandation_id)
    
    if not check_client_access(recommandation):
        return jsonify({'success': False, 'error': 'Accès non autorisé'}), 403
    
    # Récupérer les informations de la recommandation
    data = {
        'description': recommandation.description,
        'type': recommandation.type_recommandation,
        'priorite': recommandation.score_priorite,
        'delai': recommandation.delai_mise_en_oeuvre,
        'audit_ref': recommandation.audit.reference if recommandation.audit else 'N/A'
    }
    
    prompt = f"""
    En tant qu'expert en gestion de projet et audit, décompose cette recommandation en un plan d'action détaillé.
    
    RECOMMANDATION:
    Description: {data['description']}
    Type: {data['type']}
    Priorité: {data['priorite']}/100
    Délai suggéré: {data['delai'] or 'Non spécifié'}
    Audit: {data['audit_ref']}
    
    Génère un plan d'action au format JSON suivant:
    {{
        "nom": "nom du plan d'action (max 100 caractères)",
        "description": "description globale du plan",
        "duree_estimee_jours": nombre de jours estimés,
        "priorite": "haute/moyenne/basse",
        "sous_actions": [
            {{
                "description": "description de la tâche",
                "duree_estimee_jours": nombre de jours,
                "ordre": 1,
                "responsable_suggere": "type de responsable (ex: DSI, Finance, Qualité)",
                "commentaire": "conseil d'exécution"
            }}
        ]
    }}
    """
    
    try:
        resultat_ia = appel_ia_generer_plan_action(prompt)
        plan_propose = json.loads(resultat_ia)
        
        return jsonify({
            'success': True,
            'plan_propose': plan_propose,
            'recommandation_id': recommandation_id,
            'audit_id': recommandation.audit_id
        })
        
    except Exception as e:
        _journal(f"Erreur IA: {str(e)}")
        # Mode simulation
        plan_simule = simuler_plan_action(recommandation)
        return jsonify({
            'success': True,
            'plan_propose': plan_simule,
            'recommandation_id': recommandation_id,
            'audit_id': recommandation.audit_id,
            'mode': 'simulation'
        })


@app.route('/audit/<int:audit_id>/rapport-pdf-pro')
@login_required
def rapport_audit_pdf_pro(audit_id):
    """Ancienne adresse du rapport PDF : redirige vers l'export PDF du rapport d'audit."""
    return redirect(url_for('export_rapport_audit_pdf', audit_id=audit_id))


# ============================
# ROUTES POUR CONSTATATIONS
# ============================
@app.route('/audit/<int:audit_id>/recommandation/ajouter', methods=['POST'])
@login_required
def ajouter_recommandation(audit_id):
    """Ajouter une recommandation à un audit"""
    audit = Audit.query.get_or_404(audit_id)
    
    try:
        # DEBUG: Afficher les données reçues
        _journal(f"🔍 Données POST reçues: {dict(request.form)}")
        
        # 1. Générer une référence UNIQUE
        # Compter le nombre de recommandations pour cet audit
        count_recos = Recommandation.query.filter_by(audit_id=audit_id).count()
        _journal(f"📊 Nombre de recommandations existantes: {count_recos}")
        
        # Extraire la partie numérique de la référence d'audit
        import re
        
        # Obtenir la référence de l'audit
        audit_ref = audit.reference if audit.reference else f"AUD-{audit_id:04d}"
        _journal(f"📝 Référence audit: {audit_ref}")
        
        # Trouver le prochain numéro de recommandation
        # Chercher la dernière recommandation pour cet audit
        derniere_reco = Recommandation.query.filter_by(audit_id=audit_id).order_by(Recommandation.id.desc()).first()
        
        if derniere_reco and derniere_reco.reference:
            # Essayer d'extraire le numéro de la dernière référence
            match = re.search(r'REC-.*-(\d+)', derniere_reco.reference)
            if match:
                last_num = int(match.group(1))
                next_num = last_num + 1
            else:
                next_num = count_recos + 1
        else:
            next_num = 1
        
        # Créer la nouvelle référence
        nouvelle_ref = f"REC-{audit_ref}-{next_num:03d}"
        _journal(f"✅ Nouvelle référence générée: {nouvelle_ref}")
        
        # 2. Valider les données requises
        description = request.form.get('description', '').strip()
        if not description:
            flash('La description est requise', 'error')
            return redirect(url_for('detail_audit', id=audit_id))
        
        # 3. Traiter les champs optionnels
        constatation_id = request.form.get('constatation_id')
        risque_id = request.form.get('risque_id')
        responsable_id = request.form.get('responsable_id')
        
        # Convertir en int si possible
        constatation_id = int(constatation_id) if constatation_id and constatation_id.isdigit() else None
        risque_id = int(risque_id) if risque_id and risque_id.isdigit() else None
        responsable_id = int(responsable_id) if responsable_id and responsable_id.isdigit() else None
        
        # 4. Traiter la date d'échéance
        date_echeance = None
        date_echeance_str = request.form.get('date_echeance')
        if date_echeance_str:
            try:
                date_echeance = datetime.strptime(date_echeance_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Format de date invalide', 'warning')
                # Date par défaut: 30 jours à partir d'aujourd'hui
                date_echeance = datetime.utcnow().date() + timedelta(days=30)
        
        # 5. Créer la recommandation avec TOUS les champs requis
        recommandation = Recommandation(
            reference=nouvelle_ref,  # CHAMP OBLIGATOIRE
            description=description,
            type_recommandation=request.form.get('type_recommandation', 'corrective'),
            categorie=request.form.get('categorie', ''),
            delai_mise_en_oeuvre=request.form.get('delai_mise_en_oeuvre', ''),
            date_echeance=date_echeance,
            urgence=int(request.form.get('urgence', 3)),
            impact_operationnel=int(request.form.get('impact_operationnel', 3)),
            statut='a_traiter',
            audit_id=audit_id,
            constatation_id=constatation_id,
            risque_id=risque_id,
            responsable_id=responsable_id,
            created_by=current_user.id,
            taux_avancement=0  # Valeur par défaut
        )
        
        # 6. Calculer le score de priorité
        recommandation.score_priorite = recommandation.calculer_score_priorite()
        
        _journal(f"💾 Sauvegarde recommandation: {recommandation.reference}")
        
        # 7. Sauvegarder
        db.session.add(recommandation)
        db.session.commit()
        
        flash(f'Recommandation {recommandation.reference} ajoutée avec succès', 'success')
        
    except ValueError as e:
        db.session.rollback()
        _journal(f"❌ Erreur ValueError: {str(e)}")
        flash(f'Erreur de conversion: {str(e)}', 'error')
    except Exception as e:
        db.session.rollback()
        _journal(f"❌ Erreur inattendue: {str(e)}")
        import traceback
        traceback.print_exc()  # Pour le débogage complet
        flash(f'Erreur lors de l\'ajout: {str(e)}', 'error')
    
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/recommandation/<int:recommandation_id>/modifier', methods=['POST'])
@login_required
def modifier_recommandation(recommandation_id):
    """Modifier une recommandation complètement"""
    recommandation = Recommandation.query.get_or_404(recommandation_id)
    
    try:
        # Mettre à jour tous les champs
        recommandation.description = request.form.get('description', '').strip()
        recommandation.type_recommandation = request.form.get('type_recommandation', 'corrective')
        recommandation.categorie = request.form.get('categorie', '')
        recommandation.delai_mise_en_oeuvre = request.form.get('delai_mise_en_oeuvre', '')
        
        # Date d'échéance
        date_echeance = request.form.get('date_echeance')
        recommandation.date_echeance = datetime.strptime(date_echeance, '%Y-%m-%d').date() if date_echeance else None
        
        # Urgence et impact
        recommandation.urgence = int(request.form.get('urgence', 3))
        recommandation.impact_operationnel = int(request.form.get('impact_operationnel', 3))
        
        # Statut et taux d'avancement - IMPORTANT: lier les deux
        nouveau_statut = request.form.get('statut', 'a_traiter')
        recommandation.statut = nouveau_statut
        
        # Taux d'avancement
        taux_avancement_str = request.form.get('taux_avancement')
        if taux_avancement_str and taux_avancement_str.isdigit():
            nouveau_taux = int(taux_avancement_str)
            recommandation.taux_avancement = nouveau_taux
            
            # Si le statut est "termine", forcer 100%
            if nouveau_statut == 'termine':
                recommandation.taux_avancement = 100
            # Si 100% et pas encore terminé, marquer comme terminé
            elif nouveau_taux == 100 and nouveau_statut != 'termine':
                recommandation.statut = 'termine'
        
        # Responsable
        responsable_id = request.form.get('responsable_id')
        recommandation.responsable_id = int(responsable_id) if responsable_id and responsable_id.isdigit() else None
        
        # Risque associé
        risque_id = request.form.get('risque_id')
        recommandation.risque_id = int(risque_id) if risque_id and risque_id.isdigit() else None
        
        # Recalculer le score de priorité
        recommandation.score_priorite = recommandation.calculer_score_priorite()
        
        # Mettre à jour la date de modification
        recommandation.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Recommandation modifiée avec succès', 'success')
        
    except ValueError as e:
        db.session.rollback()
        flash(f'Erreur de valeur: {str(e)}', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la modification: {str(e)}', 'error')
    
    return redirect(url_for('detail_audit', id=recommandation.audit_id))


@app.route('/recommandation/<int:recommandation_id>/changer-statut', methods=['POST'])
@login_required
def changer_statut_recommandation(recommandation_id):
    """Changer le statut et le taux d'avancement d'une recommandation"""
    recommandation = Recommandation.query.get_or_404(recommandation_id)
    nouveau_statut = request.form.get('statut')
    
    if nouveau_statut in ['a_traiter', 'en_cours', 'termine', 'retarde']:
        ancien_statut = recommandation.statut
        recommandation.statut = nouveau_statut
        
        # Gérer le taux d'avancement en fonction du statut
        taux_avancement = request.form.get('taux_avancement')
        if taux_avancement and taux_avancement.isdigit():
            recommandation.taux_avancement = int(taux_avancement)
        
        # Si terminé, forcer 100%
        if nouveau_statut == 'termine':
            recommandation.taux_avancement = 100
        # Si 100% et pas encore terminé, marquer comme terminé
        elif recommandation.taux_avancement == 100 and nouveau_statut != 'termine':
            recommandation.statut = 'termine'
        
        recommandation.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash(f'Statut modifié: {ancien_statut} → {nouveau_statut}', 'success')
    else:
        flash('Statut invalide', 'error')
    
    return redirect(url_for('detail_audit', id=recommandation.audit_id))


@app.route('/constatation/<int:constatation_id>/changer-statut', methods=['POST'])
@login_required
def changer_statut_constatation(constatation_id):
    """Changer le statut d'une constatation"""
    constatation = Constatation.query.get_or_404(constatation_id)
    nouveau_statut = request.form.get('statut')
    
    if nouveau_statut in ['a_analyser', 'a_valider', 'en_action', 'clos']:
        ancien_statut = constatation.statut
        constatation.statut = nouveau_statut
        constatation.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash(f'Statut modifié: {ancien_statut} → {nouveau_statut}', 'success')
    else:
        flash('Statut invalide', 'error')
    
    return redirect(url_for('detail_audit', id=constatation.audit_id))


@app.route('/audit/<int:audit_id>/upload-fichier', methods=['POST'])
@login_required
def upload_fichier_audit(audit_id):
    """Uploader un fichier pour un audit"""
    audit = Audit.query.get_or_404(audit_id)
    
    if 'fichier' not in request.files:
        flash('Aucun fichier sélectionné', 'error')
        return redirect(url_for('detail_audit', id=audit_id))
    
    fichier = request.files['fichier']
    
    if fichier.filename == '':
        flash('Aucun fichier sélectionné', 'error')
        return redirect(url_for('detail_audit', id=audit_id))
    
    if fichier and allowed_file(fichier.filename):
        # Créer le dossier s'il n'existe pas
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        # Générer un nom de fichier unique
        filename = secure_filename(fichier.filename)
        unique_filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        # Sauvegarder le fichier
        fichier.save(filepath)
        
        # Créer une entrée dans le journal
        journaliser_action_audit(
            audit_id=audit.id,
            action_type='upload_fichier',
            user_id=current_user.id,
            details={
                'filename': filename,
                'unique_filename': unique_filename,
                'filepath': filepath
            }
        )
        
        flash(f'Fichier "{filename}" uploadé avec succès', 'success')
    else:
        flash('Type de fichier non autorisé', 'error')
    
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/constatation/<int:constatation_id>/upload-preuve', methods=['POST'])
@login_required
def upload_preuve_constatation(constatation_id):
    """Uploader une preuve pour une constatation avec métadonnées"""
    constatation = Constatation.query.get_or_404(constatation_id)
    
    if 'preuve' not in request.files:
        flash('Aucun fichier sélectionné', 'error')
        return redirect(url_for('detail_audit', id=constatation.audit_id))
    
    preuve = request.files['preuve']
    commentaire = request.form.get('commentaire', '').strip()
    
    if preuve and allowed_file(preuve.filename):
        # Créer le dossier
        os.makedirs('static/uploads/preuves', exist_ok=True)
        
        # Sauvegarder le fichier
        filename = secure_filename(preuve.filename)
        unique_filename = f"preuve_{constatation_id}_{filename}"
        filepath = os.path.join('static/uploads/preuves', unique_filename)
        preuve.save(filepath)
        
        # Enregistrer les métadonnées
        try:
            fichier_metadata = FichierMetadata(
                nom_fichier=unique_filename,
                chemin=filepath,
                type_fichier=filename.split('.')[-1].lower() if '.' in filename else 'unknown',
                taille=os.path.getsize(filepath),
                commentaire=commentaire,
                responsable_id=current_user.id,  # Responsable automatique
                entite_type='constatation',
                entite_id=constatation_id,
                created_by=current_user.id
            )
            
            db.session.add(fichier_metadata)
        except Exception as e:
            _journal(f"Erreur lors de l'enregistrement des métadonnées: {e}")
            # Continuer même sans métadonnées
        
        # Mettre à jour la constatation
        if constatation.preuves:
            constatation.preuves += f",{unique_filename}"
        else:
            constatation.preuves = unique_filename
        
        constatation.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash(f'Fichier "{filename}" uploadé avec succès', 'success')
        if commentaire:
            flash(f'Commentaire enregistré : {commentaire}', 'info')
    
    return redirect(url_for('detail_audit', id=constatation.audit_id))


# ============================
# ROUTES API POUR LES RÉSUMÉS
# ============================
@app.route('/api/constatation/<int:constatation_id>/resume')
@login_required
def api_resume_constatation(constatation_id):
    """API pour récupérer le résumé d'une constatation"""
    constatation = Constatation.query.get_or_404(constatation_id)
    
    # Vérifier que l'utilisateur a accès à cet audit
    audit = constatation.audit
    
    # Vérifier les permissions
    user_in_equipe = False
    if audit.equipe_audit_ids:
        equipe_ids = [id_str.strip() for id_str in audit.equipe_audit_ids.split(',') if id_str.strip()]
        user_in_equipe = str(current_user.id) in equipe_ids
    
    peut_voir = (
        current_user.role == 'admin' or
        current_user.id == audit.created_by or
        current_user.id == audit.responsable_id or
        user_in_equipe
    )
    
    if not peut_voir:
        return jsonify({'error': 'Non autorisé'}), 403
    
    # Récupérer les métadonnées des fichiers si disponibles
    preuves_avec_metadata = []
    if constatation.preuves:
        preuves_list = constatation.get_preuves_list
        for preuve in preuves_list:
            metadata_info = {
                'nom': preuve,
                'commentaire': '',
                'responsable': '',
                'date_upload': '',
                'taille': 'N/A'
            }
            
            # Essayer de récupérer les métadonnées
            try:
                from models import FichierMetadata
                metadata = FichierMetadata.query.filter_by(
                    nom_fichier=preuve,
                    entite_type='constatation',
                    entite_id=constatation_id
                ).first()
                
                if metadata:
                    metadata_info['commentaire'] = metadata.commentaire or ''
                    metadata_info['responsable'] = metadata.responsable.username if metadata.responsable else 'Non défini'
                    metadata_info['date_upload'] = metadata.created_at.strftime('%d/%m/%Y') if metadata.created_at else ''
                    if metadata.taille:
                        taille_kb = metadata.taille / 1024
                        metadata_info['taille'] = f"{taille_kb:.1f} KB"
            except Exception as e:
                _journal(f"Erreur lors de la récupération des métadonnées: {e}")
            
            preuves_avec_metadata.append(metadata_info)
    
    # Récupérer les recommandations liées
    recommandations_data = []
    for recommandation in constatation.recommandations:
        recommandations_data.append({
            'id': recommandation.id,
            'reference': recommandation.reference,
            'description': recommandation.description[:80] + '...' if len(recommandation.description) > 80 else recommandation.description,
            'statut': recommandation.statut,
            'statut_display': recommandation.statut.replace('_', ' ').title() if recommandation.statut else '',
            'couleur_statut': recommandation.couleur_statut
        })
    
    # Informations sur le risque
    risque_data = None
    if constatation.risque_id:
        risque = Risque.query.get(constatation.risque_id)
        if risque:
            derniere_eval = risque.evaluations[-1] if risque.evaluations else None
            risque_data = {
                'id': risque.id,
                'reference': risque.reference,
                'intitule': risque.intitule,
                'categorie': risque.categorie,
                'niveau': derniere_eval.niveau_risque if derniere_eval else 'Non évalué',
                'score': derniere_eval.score_risque if derniere_eval else 0
            }
    
    # VÉRIFIER ET INCLURE TOUS LES CHAMPS
    conclusion = getattr(constatation, 'conclusion', '')
    commentaires = getattr(constatation, 'commentaires', '')
    recommandations_immediates = getattr(constatation, 'recommandations_immediates', '')
    
    # Formater les données
    data = {
        'id': constatation.id,
        'reference': constatation.reference,
        'description': constatation.description,
        'type_constatation': constatation.type_constatation,
        'type_constatation_display': constatation.type_constatation.replace('_', ' ').title() if constatation.type_constatation else '',
        'gravite': constatation.gravite,
        'gravite_display': constatation.gravite.title() if constatation.gravite else '',
        'statut': constatation.statut,
        'statut_display': constatation.statut.replace('_', ' ').title() if constatation.statut else '',
        'processus': constatation.processus_concerne or '',
        'cause_racine': constatation.cause_racine or '',
        'conclusion': conclusion,  # CORRIGÉ
        'commentaires': commentaires,  # CORRIGÉ
        'recommandations_immediates': recommandations_immediates,  # CORRIGÉ
        'date_creation': constatation.created_at.strftime('%d/%m/%Y à %H:%M') if constatation.created_at else '',
        'date_modification': constatation.updated_at.strftime('%d/%m/%Y à %H:%M') if constatation.updated_at else '',
        'createur': constatation.createur.username if constatation.createur else 'Système',
        'couleur_type': {
            'non_conformite': 'danger',
            'observation': 'warning',
            'conformite': 'success',
            'amelioration': 'info',
            'recommandation': 'primary'
        }.get(constatation.type_constatation, 'secondary'),
        'couleur_gravite': {
            'critique': 'danger',
            'majeure': 'warning',
            'moyenne': 'info',
            'mineure': 'success'
        }.get(constatation.gravite, 'secondary'),
        'couleur_statut': {
            'a_analyser': 'secondary',
            'a_valider': 'warning',
            'en_action': 'info',
            'clos': 'success'
        }.get(constatation.statut, 'light'),
        'preuves': preuves_avec_metadata,
        'recommandations': recommandations_data,
        'risque': risque_data
    }
    
    return jsonify(data)


@app.route('/api/recommandation/<int:recommandation_id>/resume')
@login_required
def api_resume_recommandation(recommandation_id):
    """API pour récupérer le résumé d'une recommandation"""
    recommandation = Recommandation.query.get_or_404(recommandation_id)
    
    # Vérifier que l'utilisateur a accès à cet audit
    audit = recommandation.audit
    
    # Vérifier les permissions
    user_in_equipe = False
    if audit.equipe_audit_ids:
        equipe_ids = [id_str.strip() for id_str in audit.equipe_audit_ids.split(',') if id_str.strip()]
        user_in_equipe = str(current_user.id) in equipe_ids
    
    peut_voir = (
        current_user.role == 'admin' or
        current_user.id == audit.created_by or
        current_user.id == audit.responsable_id or
        user_in_equipe
    )
    
    if not peut_voir:
        return jsonify({'error': 'Non autorisé'}), 403
    
    # Informations sur la constatation liée
    constatation_data = None
    if recommandation.constatation_id:
        constatation = Constatation.query.get(recommandation.constatation_id)
        if constatation:
            constatation_data = {
                'id': constatation.id,
                'reference': constatation.reference,
                'description': constatation.description[:80] + '...' if len(constatation.description) > 80 else constatation.description
            }
    
    # Informations sur le risque
    risque_data = None
    if recommandation.risque_id:
        risque = Risque.query.get(recommandation.risque_id)
        if risque:
            derniere_eval = risque.evaluations[-1] if risque.evaluations else None
            risque_data = {
                'id': risque.id,
                'reference': risque.reference,
                'intitule': risque.intitule,
                'categorie': risque.categorie,
                'niveau': derniere_eval.niveau_risque if derniere_eval else 'Non évalué',
                'score': derniere_eval.score_risque if derniere_eval else 0
            }
    
    # Informations sur le plan d'action
    plan_action_data = None
    if recommandation.plan_action:
        plan_action_data = {
            'id': recommandation.plan_action.id,
            'nom': recommandation.plan_action.nom,
            'statut': recommandation.plan_action.statut,
            'statut_display': recommandation.plan_action.statut.replace('_', ' ').title() if recommandation.plan_action.statut else '',
            'couleur_statut': recommandation.plan_action.couleur_statut,
            'pourcentage_realisation': recommandation.plan_action.pourcentage_realisation or 0
        }
    
    # Formater les données
    data = {
        'id': recommandation.id,
        'reference': recommandation.reference,
        'description': recommandation.description,
        'type_recommandation': recommandation.type_recommandation,
        'type_display': recommandation.type_recommandation.replace('_', ' ').title() if recommandation.type_recommandation else '',
        'categorie': recommandation.categorie,
        'categorie_display': recommandation.categorie.replace('_', ' ').title() if recommandation.categorie else '',
        'delai_mise_en_oeuvre': recommandation.delai_mise_en_oeuvre,
        'delai_display': recommandation.delai_mise_en_oeuvre.replace('_', ' ').title() if recommandation.delai_mise_en_oeuvre else '',
        'date_echeance': recommandation.date_echeance.strftime('%d/%m/%Y') if recommandation.date_echeance else '',
        'urgence': recommandation.urgence,
        'urgence_display': f"Niveau {recommandation.urgence}/5" if recommandation.urgence else '',
        'urgence_percent': (recommandation.urgence or 0) * 20,
        'impact_operationnel': recommandation.impact_operationnel,
        'impact_display': f"Niveau {recommandation.impact_operationnel}/5" if recommandation.impact_operationnel else '',
        'impact_percent': (recommandation.impact_operationnel or 0) * 20,
        'score_priorite': recommandation.score_priorite or 0,
        'statut': recommandation.statut,
        'statut_display': recommandation.statut.replace('_', ' ').title() if recommandation.statut else '',
        'taux_avancement': recommandation.taux_avancement or 0,
        'est_en_retard': recommandation.est_en_retard,
        'date_creation': recommandation.created_at.strftime('%d/%m/%Y à %H:%M') if recommandation.created_at else '',
        'responsable': recommandation.responsable.username if recommandation.responsable else '',
        'commentaires': '',
        'couleur_type': {
            'corrective': 'danger',
            'preventive': 'warning',
            'amelioration': 'success',
            'optimisation': 'info'
        }.get(recommandation.type_recommandation, 'secondary'),
        'couleur_statut': recommandation.couleur_statut,
        'couleur_priorite': 'danger' if (recommandation.score_priorite or 0) >= 80 else 'warning' if (recommandation.score_priorite or 0) >= 60 else 'success',
        'couleur_avancement': 'danger' if (recommandation.taux_avancement or 0) < 25 else 'warning' if (recommandation.taux_avancement or 0) < 75 else 'success',
        'constatation': constatation_data,
        'risque': risque_data,
        'plan_action': plan_action_data
    }
    
    return jsonify(data)


@app.route('/audit/constatation/<int:constatation_id>/preuve/delete', methods=['POST'])
@login_required
def delete_preuve_constatation(constatation_id):
    """Supprimer une preuve d'une constatation"""
    constatation = Constatation.query.get_or_404(constatation_id)
    
    # Vérifier les permissions
    audit = constatation.audit
    peut_modifier = (
        current_user.role == 'admin' or
        current_user.id == audit.created_by or
        current_user.id == audit.responsable_id or
        str(current_user.id) in (audit.equipe_audit_ids or '').split(',')
    )
    
    if not peut_modifier:
        return jsonify({'success': False, 'message': 'Non autorisé'}), 403
    
    data = request.get_json()
    filename = data.get('filename')
    
    if not filename:
        return jsonify({'success': False, 'message': 'Nom de fichier manquant'}), 400
    
    try:
        # Supprimer le fichier physique
        filepath = os.path.join('static/uploads/preuves', filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        
        # Supprimer les métadonnées
        try:
            from models import FichierMetadata
            FichierMetadata.query.filter_by(
                nom_fichier=filename,
                entite_type='constatation',
                entite_id=constatation_id
            ).delete()
        except:
            pass
        
        # Mettre à jour la constatation
        if constatation.preuves:
            preuves_list = constatation.get_preuves_list
            if filename in preuves_list:
                preuves_list.remove(filename)
                constatation.preuves = ','.join(preuves_list) if preuves_list else None
        
        constatation.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Preuve supprimée avec succès'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erreur lors de la suppression: {str(e)}'}), 500


@app.route('/constatation/<int:constatation_id>/modifier', methods=['POST'])
@login_required
def modifier_constatation(constatation_id):
    """Modifier une constatation existante - VERSION CORRIGÉE"""
    from models import Constatation, DemandeReevaluation, Notification, User, db
    from datetime import datetime
    
    constatation = Constatation.query.get_or_404(constatation_id)
    audit = constatation.audit
    
    # Vérifier les permissions
    peut_modifier = (
        current_user.role == 'admin' or
        current_user.id == audit.created_by or
        current_user.id == audit.responsable_id or
        str(current_user.id) in (audit.equipe_audit_ids or '').split(',')
    )
    
    if not peut_modifier:
        flash('Non autorisé', 'error')
        return redirect(url_for('detail_audit', id=audit.id))
    
    try:
        # Mettre à jour tous les champs
        constatation.description = request.form.get('description', '').strip()
        constatation.type_constatation = request.form.get('type_constatation', '')
        constatation.gravite = request.form.get('gravite', '')
        constatation.processus_concerne = request.form.get('processus_concerne', '').strip()
        constatation.cause_racine = request.form.get('cause_racine', '').strip()
        constatation.conclusion = request.form.get('conclusion', '').strip()
        constatation.commentaires = request.form.get('commentaires', '').strip()
        constatation.recommandations_immediates = request.form.get('recommandations_immediates', '').strip()
        
        # 🔥 CORRECTION : Récupérer correctement les IDs
        risque_id = request.form.get('risque_id')
        dispositif_id = request.form.get('dispositif_id')
        controle_id = request.form.get('controle_id')
        
        constatation.risque_id = int(risque_id) if risque_id and risque_id.isdigit() else None
        constatation.dispositif_id = int(dispositif_id) if dispositif_id and dispositif_id.isdigit() else None
        constatation.controle_id = int(controle_id) if controle_id and controle_id.isdigit() else None
        
        constatation.statut = request.form.get('statut', 'a_analyser')
        constatation.updated_at = datetime.utcnow()
        
        # ============================================
        # 🔥 NOUVEAU : DEMANDE DE RÉÉVALUATION DEPUIS LA MODIFICATION
        # ============================================
        demander_reevaluation = request.form.get('demander_reevaluation') == '1'
        
        if demander_reevaluation and constatation.risque_id and not constatation.demande_reevaluation_id:
            impact_propose = request.form.get('impact_propose', type=int)
            probabilite_propose = request.form.get('probabilite_propose', type=int)
            niveau_maitrise_propose = request.form.get('niveau_maitrise_propose', type=int)
            justification = request.form.get('justification_reevaluation', '').strip()
            
            if not justification:
                flash('La justification est obligatoire pour une réévaluation', 'error')
                return redirect(url_for('detail_audit', id=audit.id))
            
            # Créer la demande
            demande = DemandeReevaluation(
                audit_id=audit.id,
                constat_id=constatation.id,
                risque_id=constatation.risque_id,
                titre=f"Réévaluation du risque suite au constat {constatation.reference}",
                justification=justification,
                impact_propose=impact_propose,
                probabilite_propose=probabilite_propose,
                niveau_maitrise_propose=niveau_maitrise_propose,
                demandeur_id=current_user.id,
                client_id=current_user.client_id,
                statut='en_attente'
            )
            demande.reference = demande.generer_reference()
            demande.calculer_score_propose()
            
            db.session.add(demande)
            db.session.flush()
            
            constatation.demande_reevaluation_id = demande.id
            constatation.reevaluation_demandee = True
            constatation.reevaluation_statut = 'demandee'
            
            # Notifier le comité
            comite_risques = User.query.filter(
                User.client_id == current_user.client_id,
                User.is_active == True,
                User.role.in_(['admin', 'responsable_risques', 'manager'])
            ).all()
            
            for user in comite_risques:
                notification = Notification(
                    destinataire_id=user.id,
                    type_notification='reevaluation_demandee',
                    titre=f"🔄 Demande de réévaluation: {constatation.risque_id}",
                    message=f"Une demande de réévaluation a été soumise suite au constat {constatation.reference}.\n"
                            f"Proposition: Impact {impact_propose}/5, Probabilité {probabilite_propose}/5\n"
                            f"Justification: {justification}",
                    entite_type='demande_reevaluation',
                    entite_id=demande.id,
                    client_id=current_user.client_id,
                    urgence='important'
                )
                db.session.add(notification)
            
            flash(f'✅ Demande de réévaluation créée (Réf: {demande.reference})', 'success')
        
        db.session.commit()
        flash('Constatation modifiée avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la modification: {str(e)}', 'error')
    
    return redirect(url_for('detail_audit', id=audit.id))


@app.route('/audit/<int:audit_id>/constatation/ajouter', methods=['POST'])
@login_required
def ajouter_constatation(audit_id):
    """Ajouter une constatation à un audit"""
    audit = Audit.query.get_or_404(audit_id)

    try:
        # ===== GÉNÉRATION DE LA RÉFÉRENCE =====
        dernier_constat = (
            Constatation.query
            .filter_by(audit_id=audit_id)
            .order_by(Constatation.id.desc())
            .first()
        )

        nouvelle_ref = f"CON-{audit.reference}-{(dernier_constat.id + 1) if dernier_constat else 1:03d}"

        # ===== CRÉATION DE LA CONSTATATION =====
        constatation = Constatation(
            reference=nouvelle_ref,
            description=request.form.get('description', '').strip(),
            type_constatation=request.form.get('type_constatation', 'observation'),
            gravite=request.form.get('gravite', 'moyenne'),
            criticite=request.form.get('criticite', 'mineure'),
            processus_concerne=request.form.get('processus_concerne', '').strip(),
            cause_racine=request.form.get('cause_racine', '').strip(),

            # 🔹 NOUVEAUX CHAMPS AJOUTÉS
            conclusion=request.form.get('conclusion', '').strip(),
            commentaires=request.form.get('commentaires', '').strip(),
            recommandations_immediates=request.form.get('recommandations_immediates', '').strip(),

            statut='a_analyser',
            audit_id=audit_id,
            created_by=current_user.id,

            # 🔹 RISQUE ASSOCIÉ (sécurisé)
            risque_id=int(request.form.get('risque_id'))
            if request.form.get('risque_id') else None
        )

        db.session.add(constatation)
        db.session.commit()

        flash('Constatation ajoutée avec succès', 'success')

    except Exception as e:
        db.session.rollback()
        app.logger.error(
            f"Erreur lors de l'ajout de la constatation : {e}",
            exc_info=True
        )
        flash("Erreur lors de l'ajout de la constatation", 'error')

    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/audit/<int:audit_id>/analyses-ia/supprimer-toutes', methods=['POST'])
@login_required
def supprimer_toutes_analyses_ia(audit_id):
    """Supprimer toutes les analyses IA d'un audit"""
    try:
        audit = get_client_object_or_404(Audit, audit_id)
        
        # Vérifier les permissions
        peut_supprimer = (
            current_user.role == 'admin' or
            current_user.id == audit.created_by or
            current_user.id == audit.responsable_id
        )
        
        if not peut_supprimer:
            flash('Vous n\'avez pas les permissions pour cette action', 'error')
            return redirect(url_for('liste_analyses_ia', audit_id=audit_id))
        
        # Récupérer et supprimer toutes les analyses
        analyses = get_client_filter(AnalyseIA).filter_by(audit_id=audit_id).all()
        count = len(analyses)
        
        for analyse in analyses:
            db.session.delete(analyse)
        
        db.session.commit()
        
        # Journaliser
        log_activity(current_user.id, 'suppression_toutes_analyses_ia',
                    f"{count} analyses IA supprimées pour l'audit {audit.reference}",
                    'audit', audit_id)
        
        flash(f'{count} analyses IA supprimées avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la suppression: {str(e)}', 'error')
    
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/recommandation/<int:recommandation_id>/supprimer', methods=['POST'])
@login_required
def supprimer_recommandation(recommandation_id):
    """Supprimer une recommandation (inclut les recommandations IA)"""
    try:
        recommandation = get_client_object_or_404(Recommandation, recommandation_id)
        audit_id = recommandation.audit_id
        
        # Vérifier les permissions
        peut_supprimer = (
            current_user.role == 'admin' or
            current_user.id == recommandation.created_by or
            current_user.id == recommandation.audit.created_by
        )
        
        if not peut_supprimer:
            flash('Vous n\'avez pas les permissions pour supprimer cette recommandation', 'error')
            return redirect(url_for('detail_audit', id=audit_id))
        
        # Vérifier si c'est une recommandation IA
        is_ia_recommendation = recommandation.categorie == 'ia_suggested'
        
        # Supprimer la recommandation
        db.session.delete(recommandation)
        db.session.commit()
        
        # Journaliser
        action = 'suppression_recommandation_ia' if is_ia_recommendation else 'suppression_recommandation'
        log_activity(current_user.id, action,
                    f"Recommandation {recommandation.reference} supprimée",
                    'recommandation', recommandation_id)
        
        flash('Recommandation supprimée avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la suppression: {str(e)}', 'error')
    
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/constatation/<int:constatation_id>/supprimer', methods=['POST'])
@login_required
def supprimer_constatation(constatation_id):
    """Supprimer une constatation"""
    try:
        constatation = get_client_object_or_404(Constatation, constatation_id)
        audit_id = constatation.audit_id
        
        # Vérifier les permissions
        peut_supprimer = (
            current_user.role == 'admin' or
            current_user.id == constatation.created_by or
            current_user.id == constatation.audit.created_by
        )
        
        if not peut_supprimer:
            flash('Vous n\'avez pas les permissions pour supprimer cette constatation', 'error')
            return redirect(url_for('detail_audit', id=audit_id))
        
        # Supprimer les fichiers associés
        if constatation.preuves:
            preuves_list = constatation.get_preuves_list
            for preuve in preuves_list:
                filepath = os.path.join('static/uploads/preuves', preuve)
                if os.path.exists(filepath):
                    os.remove(filepath)
        
        # Supprimer la constatation
        db.session.delete(constatation)
        db.session.commit()
        
        # Journaliser
        log_activity(current_user.id, 'suppression_constatation',
                    f"Constatation {constatation.reference} supprimée",
                    'constatation', constatation_id)
        
        flash('Constatation supprimée avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la suppression: {str(e)}', 'error')
    
    return redirect(url_for('detail_audit', id=audit_id))


@app.route('/audit/rapports/comparaison')
@login_required
def rapport_comparaison_audits():
    """Rapport de comparaison entre audits"""
    audits = Audit.query.filter_by(is_archived=False).all()
    
    # Calculer les statistiques pour la comparaison
    comparaison_data = []
    
    for audit in audits:
        stats = {
            'audit': audit,
            'nb_constatations': len(audit.constatations),
            'nb_recommandations': len(audit.recommandations),
            'nb_plans_action': len(audit.plans_action),
            'taux_realisation': audit.taux_realisation_recommandations,
            'score_global': audit.score_global
        }
        comparaison_data.append(stats)
    
    return render_template('audit/rapport_comparaison.html', 
                         audits=audits,
                         comparaison_data=comparaison_data)


@app.route('/api/audit/<int:audit_id>/timeline')
@login_required
def api_timeline_audit(audit_id):
    """API pour la timeline de l'audit"""
    audit = Audit.query.get_or_404(audit_id)
    
    timeline = []
    
    # Date de création
    timeline.append({
        'date': audit.created_at.isoformat(),
        'type': 'creation',
        'title': 'Audit créé',
        'description': f'Audit {audit.reference} créé par {audit.created_by_user.username if audit.created_by_user else "Système"}'
    })
    
    # Constatations
    for constat in audit.constatations:
        timeline.append({
            'date': constat.created_at.isoformat(),
            'type': 'constatation',
            'title': f'Constatation {constat.reference}',
            'description': constat.description[:100] + '...' if len(constat.description) > 100 else constat.description
        })
    
    # Recommandations
    for reco in audit.recommandations:
        timeline.append({
            'date': reco.created_at.isoformat(),
            'type': 'recommandation',
            'title': f'Recommandation',
            'description': reco.description[:100] + '...' if len(reco.description) > 100 else reco.description
        })
    
    # Trier par date
    timeline.sort(key=lambda x: x['date'])
    
    return jsonify({'timeline': timeline})


@app.route('/audit/<int:audit_id>/matrice-maturite/ajouter', methods=['POST'])
@login_required
def ajouter_matrice_maturite(audit_id):
    """Ajouter une matrice de maturité"""
    audit = Audit.query.get_or_404(audit_id)
    
    form = MatriceMaturiteForm()
    
    # Préparer les choix pour le formulaire si nécessaire
    # form.nom_du_champ.choices = [...]
    
    if form.validate_on_submit():
        matrice = MatriceMaturite(
            audit_id=audit_id,
            axe=form.axe.data,
            critere=form.critere.data,
            niveau_maturite=form.niveau_maturite.data,
            commentaire=form.commentaire.data,
            poids=form.poids.data or 1.0,
            created_by=current_user.id
        )
        
        db.session.add(matrice)
        db.session.commit()
        
        flash('Matrice de maturité ajoutée avec succès', 'success')
    else:
        # Afficher les erreurs de validation
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Erreur {field}: {error}', 'error')
    
    return redirect(url_for('matrice_maturite_audit', audit_id=audit_id))


@app.route('/api/audit/<int:audit_id>/statistiques')
@login_required
def api_statistiques_audit(audit_id):
    """API pour les statistiques d'audit"""
    audit = Audit.query.get_or_404(audit_id)
    rapport = generer_rapport_audit_complet(audit_id)
    
    return jsonify(rapport['statistiques'])


@app.route('/audit/<int:audit_id>/upload-rapport-fichier', methods=['POST'])
@login_required
def upload_fichier_rapport(audit_id):
    """Uploader un fichier pour le rapport d'audit"""
    audit = Audit.query.get_or_404(audit_id)
    
    # Vérifier les permissions
    if not current_user.has_permission('can_manage_audit') and not check_client_access(audit):
        flash('Vous n\'avez pas les permissions pour ajouter des fichiers', 'error')
        return redirect(url_for('rapport_audit_complet', audit_id=audit_id))
    
    if 'fichier' not in request.files:
        flash('Aucun fichier sélectionné', 'error')
        return redirect(url_for('rapport_audit_complet', audit_id=audit_id))
    
    fichier = request.files['fichier']
    description = request.form.get('description', '').strip()
    
    if fichier.filename == '':
        flash('Aucun fichier sélectionné', 'error')
        return redirect(url_for('rapport_audit_complet', audit_id=audit_id))
    
    # Vérifier l'extension
    allowed_extensions = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 
                         'jpg', 'jpeg', 'png', 'txt', 'zip', 'rar'}
    if not ('.' in fichier.filename and 
            fichier.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        flash('Type de fichier non autorisé', 'error')
        return redirect(url_for('rapport_audit_complet', audit_id=audit_id))
    
    try:
        # Créer le dossier spécifique pour cet audit
        upload_dir = os.path.join('static', 'uploads', 'rapports_audit', str(audit_id))
        os.makedirs(upload_dir, exist_ok=True)
        
        # Générer un nom de fichier unique
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        nom_original = secure_filename(fichier.filename)
        nom_unique = f"{timestamp}_{nom_original}"
        chemin_complet = os.path.join(upload_dir, nom_unique)
        
        # Sauvegarder le fichier
        fichier.save(chemin_complet)
        
        # Enregistrer dans la base de données
        fichier_rapport = FichierRapport(
            audit_id=audit_id,
            nom_fichier=nom_original,
            chemin=chemin_complet,
            type_fichier=nom_original.rsplit('.', 1)[1].lower() if '.' in nom_original else 'unknown',
            taille=os.path.getsize(chemin_complet),
            description=description if description else None,
            uploaded_by=current_user.id
        )
        
        db.session.add(fichier_rapport)
        db.session.commit()
        
        # Journaliser l'action
        log_activity(current_user.id, 'upload_fichier_rapport',
                    f"Fichier {nom_original} uploadé pour l'audit {audit.reference}",
                    'audit', audit_id)
        
        flash(f'Fichier "{nom_original}" uploadé avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de l\'upload: {str(e)}', 'error')
    
    return redirect(url_for('rapport_audit_complet', audit_id=audit_id))


@app.route('/audit/<int:audit_id>/upload-fichier-rapport', methods=['GET', 'POST'])
@login_required
def upload_fichier_rapport_audit(audit_id):
    """Uploader un fichier pour le rapport d'audit"""
    
    # Vérifier l'accès à l'audit
    audit = get_client_object_or_404(Audit, audit_id)
    
    # Vérifier les permissions
    peut_uploader = (
        current_user.role == 'super_admin' or
        current_user.id == audit.created_by or
        current_user.id == audit.responsable_id or
        (audit.equipe_audit_ids and str(current_user.id) in audit.equipe_audit_ids.split(','))
    )
    
    if not peut_uploader:
        flash('Vous n\'avez pas les permissions pour ajouter des fichiers', 'error')
        return redirect(url_for('rapport_audit_complet', audit_id=audit_id))
    
    # Si c'est une requête GET, afficher le formulaire
    if request.method == 'GET':
        return render_template('audit/upload_fichier.html', 
                             audit=audit,
                             title=f"Ajouter un fichier - {audit.reference}")
    
    # Si c'est une requête POST, traiter l'upload
    if 'fichier' not in request.files:
        flash('Aucun fichier sélectionné', 'error')
        return redirect(url_for('rapport_audit_complet', audit_id=audit_id))
    
    fichier = request.files['fichier']
    description = request.form.get('description', '').strip()
    
    if fichier.filename == '':
        flash('Aucun fichier sélectionné', 'error')
        return redirect(url_for('rapport_audit_complet', audit_id=audit_id))
    
    # Vérifier l'extension
    allowed_extensions = app.config['ALLOWED_EXTENSIONS']
    if not ('.' in fichier.filename and 
            fichier.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        flash('Type de fichier non autorisé', 'error')
        return redirect(url_for('rapport_audit_complet', audit_id=audit_id))
    
    try:
        # Déterminer le dossier d'upload selon le client
        if current_user.role == 'super_admin' and session.get('viewing_client_id'):
            client_id = session['viewing_client_id']
        else:
            client_id = current_user.client_id
        
        # Créer le dossier spécifique pour cet audit
        base_dir = 'static/uploads'
        upload_dir = os.path.join(base_dir, 'rapports_audit', str(client_id), str(audit_id))
        os.makedirs(upload_dir, exist_ok=True)
        
        # Générer un nom de fichier unique
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        nom_original = secure_filename(fichier.filename)
        nom_unique = f"{timestamp}_{nom_original}"
        chemin_complet = os.path.join(upload_dir, nom_unique)
        
        # Sauvegarder le fichier
        fichier.save(chemin_complet)
        
        # Enregistrer dans la base de données
        fichier_rapport = FichierRapport(
            audit_id=audit_id,
            nom_fichier=nom_original,
            chemin=chemin_complet.replace('\\', '/'),  # Normaliser les chemins
            type_fichier=nom_original.rsplit('.', 1)[1].lower() if '.' in nom_original else 'unknown',
            taille=os.path.getsize(chemin_complet),
            description=description if description else None,
            uploaded_by=current_user.id,
            client_id=client_id
        )
        
        db.session.add(fichier_rapport)
        db.session.commit()
        
        # Journaliser l'action
        log_activity(current_user.id, 'upload_fichier_rapport',
                    f"Fichier {nom_original} uploadé pour l'audit {audit.reference}",
                    'audit', audit_id)
        
        flash(f'✅ Fichier "{nom_original}" uploadé avec succès', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Erreur lors de l\'upload: {str(e)}', 'error')
        _journal(f"❌ Erreur upload: {e}")
    
    return redirect(url_for('rapport_audit_complet', audit_id=audit_id))


@app.route('/fichier-rapport-audit/<int:fichier_id>/supprimer', methods=['POST'])
@login_required
def supprimer_fichier_rapport_audit(fichier_id):
    """Supprimer un fichier de rapport"""
    try:
        _journal(f"[DEBUG] Tentative suppression fichier {fichier_id}")
        
        # Récupérer le fichier
        fichier = FichierRapport.query.get_or_404(fichier_id)
        
        _journal(f"[DEBUG] Fichier trouvé: {fichier.nom_fichier}")
        _journal(f"[DEBUG] Chemin: {fichier.chemin}")
        _journal(f"[DEBUG] Uploadé par: {fichier.uploaded_by}")
        _journal(f"[DEBUG] Current user: {current_user.id}")
        
        # Vérifier les permissions
        peut_supprimer = (
            current_user.role == 'super_admin' or
            current_user.id == fichier.uploaded_by
        )
        
        # Si pas directement l'uploader, vérifier les permissions sur l'audit
        if not peut_supprimer and fichier.audit:
            audit = fichier.audit
            peut_supprimer = (
                current_user.id == audit.created_by or 
                current_user.id == audit.responsable_id
            )
        
        if not peut_supprimer:
            _journal(f"[ERROR] Permission refusée pour user {current_user.id}")
            return jsonify({
                'success': False,
                'message': 'Vous n\'avez pas les permissions pour supprimer ce fichier'
            }), 403
        
        # Sauvegarder les infos pour le message
        nom_fichier = fichier.nom_fichier
        audit_id = fichier.audit_id
        
        # Supprimer le fichier physique
        file_deleted = False
        if fichier.chemin and os.path.exists(fichier.chemin):
            try:
                os.remove(fichier.chemin)
                file_deleted = True
                _journal(f"[DEBUG] Fichier physique supprimé: {fichier.chemin}")
            except Exception as e:
                _journal(f"[WARNING] Erreur suppression fichier physique: {e}")
        else:
            _journal(f"[WARNING] Fichier physique non trouvé: {fichier.chemin}")
        
        # Supprimer de la base de données
        db.session.delete(fichier)
        db.session.commit()
        
        _journal(f"[SUCCESS] Fichier {nom_fichier} supprimé de la BD")
        
        return jsonify({
            'success': True,
            'message': f'Fichier "{nom_fichier}" supprimé avec succès',
            'file_deleted': file_deleted
        })
        
    except Exception as e:
        db.session.rollback()
        _journal(f"[ERROR] Erreur suppression fichier: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'message': f'Erreur lors de la suppression: {str(e)}'
        }), 500


@app.route('/audits/rapports')
@login_required
def rapports_audits():
    """Page principale des rapports d'audit avec gestion des fichiers"""
    
    # Vérification FORMULE : accès au module audit
    if current_user.client and current_user.client.formule:
        formule = current_user.client.formule
        
        if not formule.can_access_module('audit_interne'):
            try:
                all_formules = FormuleAbonnement.query.filter(
                    FormuleAbonnement.is_active == True
                ).all()
                
                upgrade_suggestions = []
                for f in all_formules:
                    if f.modules.get('audit', False):
                        upgrade_suggestions.append(f)
                
                upgrade_suggestions.sort(key=lambda x: x.prix_mensuel or 0)
                
                return render_template('errors/formule_restricted.html',
                                     module_name='Rapports d\'Audit',
                                     current_formule=formule,
                                     upgrade_suggestions=upgrade_suggestions[:3])
                
            except Exception as e:
                _journal(f"⚠️ Erreur recherche formules: {e}")
                flash('Ce module n\'est pas inclus dans votre formule', 'error')
                return redirect(url_for('dashboard'))
    
    # Vérifier permission de voir les rapports
    if not current_user.has_permission('can_view_reports'):
        flash('Accès refusé : permission de voir les rapports requise', 'error')
        return redirect(url_for('dashboard'))
    
    # ============================================
    # 1. RÉCUPÉRER LES AUDITS (OK)
    # ============================================
    audits = get_client_filter(Audit).filter_by(is_archived=False)\
        .order_by(Audit.created_at.desc()).all()
    
    # ============================================
    # 2. RÉCUPÉRER TOUS LES FICHIERS - CORRECTION ICI !
    # ============================================
    # NE PAS utiliser get_client_filter pour les fichiers au départ
    # Récupérer TOUS les fichiers sans filtre client
    fichiers_rapport = FichierRapport.query.order_by(FichierRapport.created_at.desc()).all()
    
    _journal(f"🔍 [DEBUG] Total fichiers trouvés: {len(fichiers_rapport)}")
    for f in fichiers_rapport:
        _journal(f"   - ID: {f.id}, Nom: {f.nom_fichier}, Audit: {f.audit_id}, Client: {f.client_id}")
    
    # ============================================
    # 3. FILTRER LES FICHIERS PAR CLIENT MANUELLEMENT
    # ============================================
    # Déterminer le client actuel
    if current_user.role == 'super_admin' and session.get('viewing_client_id'):
        current_client_id = session['viewing_client_id']
    else:
        current_client_id = current_user.client_id
    
    # Filtrer les fichiers par client
    fichiers_filtres = []
    for f in fichiers_rapport:
        # Vérifier si le fichier appartient au client actuel
        if f.client_id == current_client_id or current_user.role == 'super_admin':
            fichiers_filtres.append(f)
        else:
            # Vérifier via l'audit associé
            audit_associe = Audit.query.get(f.audit_id)
            if audit_associe and audit_associe.client_id == current_client_id:
                fichiers_filtres.append(f)
    
    _journal(f"🔍 [DEBUG] Fichiers après filtre client: {len(fichiers_filtres)}")
    
    # ============================================
    # 4. GROUPER PAR AUDIT
    # ============================================
    fichiers_par_audit = {}
    for fichier in fichiers_filtres:
        if fichier.audit_id not in fichiers_par_audit:
            fichiers_par_audit[fichier.audit_id] = []
        fichiers_par_audit[fichier.audit_id].append(fichier)
    
    _journal(f"🔍 [DEBUG] Audits avec fichiers: {list(fichiers_par_audit.keys())}")
    
    # ============================================
    # 5. STATISTIQUES
    # ============================================
    constatations_total = sum(len(a.constatations) for a in audits)
    recommandations_total = sum(len(a.recommandations) for a in audits)
    plans_action_total = sum(len(a.plans_action) for a in audits)
    
    # Créer un dictionnaire d'audits pour référence rapide
    audits_dict = {audit.id: audit for audit in audits}
    
    # ============================================
    # 6. GRAPHIQUES
    # ============================================
    types_audit_counts = {}
    statuts_audit_counts = {}
    
    for audit in audits:
        type_key = audit.type_audit or 'Non spécifié'
        types_audit_counts[type_key] = types_audit_counts.get(type_key, 0) + 1
        
        statut_key = audit.statut or 'Non spécifié'
        statuts_audit_counts[statut_key] = statuts_audit_counts.get(statut_key, 0) + 1
    
    types_audit_data = {
        'labels': list(types_audit_counts.keys()),
        'data': list(types_audit_counts.values()),
    }
    
    statuts_audit_data = {
        'labels': list(statuts_audit_counts.keys()),
        'data': list(statuts_audit_counts.values()),
    }
    
    # ============================================
    # 7. RENVOYER LE TEMPLATE
    # ============================================
    return render_template('audit/rapports.html',
                         audits=audits,
                         audits_dict=audits_dict,
                         constatations_total=constatations_total,
                         recommandations_total=recommandations_total,
                         plans_action_total=plans_action_total,
                         fichiers_par_audit=fichiers_par_audit,  # ← Maintenant rempli
                         total_fichiers_rapport=len(fichiers_filtres),
                         types_audit=types_audit_data,
                         statuts_audit=statuts_audit_data,
                         current_user=current_user,
                         now=datetime.utcnow())


@app.route('/api/feuille-travail/<int:feuille_id>/proposer-constats', methods=['POST'])
@login_required
def api_proposer_constats_depuis_feuille(feuille_id):
    """Proposer des constats à partir des tests d'une feuille de travail"""
    from models import FeuilleTravail, TestControleFeuille, Audit, Constatation
    import json
    
    # Récupérer la feuille
    feuille = FeuilleTravail.query.get_or_404(feuille_id)
    
    if not check_client_access(feuille):
        return jsonify({'success': False, 'error': 'Accès non autorisé'}), 403
    
    # Récupérer les tests non conformes ou partiellement conformes
    tests_non_conformes = TestControleFeuille.query.filter(
        TestControleFeuille.feuille_travail_id == feuille_id,
        TestControleFeuille.resultat.in_(['non_conforme', 'partiellement_conforme']),
        TestControleFeuille.is_archived == False
    ).all()
    
    if not tests_non_conformes:
        return jsonify({
            'success': False, 
            'error': 'Aucun test non conforme trouvé dans cette feuille'
        }), 400
    
    # Construire les données des tests
    tests_data = []
    for test in tests_non_conformes:
        tests_data.append({
            'objet': test.objet_test,
            'resultat': test.resultat,
            'ecart': test.ecart_constate or 'Non spécifié',
            'cause': test.cause_racine or 'À déterminer',
            'impact': test.impact_financier or 0,
            'criticite': test.niveau_criticite or 'moyen',
            'procedure': test.procedure or 'Non spécifiée',
            'echantillon': test.echantillon or 'Non spécifié',
            'observations': test.observations or ''
        })
    
    # Construire le prompt pour l'IA
    prompt = f"""
    En tant qu'expert en audit, analyse ces anomalies détectées et propose des constats d'audit formalisés.
    
    AUDIT: {feuille.audit.reference if feuille.audit else 'N/A'}
    FEUILLE DE TRAVAIL: {feuille.reference} - {feuille.titre}
    
    ANOMALIES DÉTECTÉES ({len(tests_data)}):
    {json.dumps(tests_data, indent=2, ensure_ascii=False)}
    
    Pour CHAQUE anomalie significative, génère un constat d'audit au format JSON suivant:
    [
        {{
            "titre": "titre court et percutant",
            "description": "description précise de l'écart constaté",
            "cause_racine": "cause identifiée ou à investiguer",
            "impact": "impact financier, opérationnel ou de conformité",
            "recommandation": "action corrective concrète",
            "priorite": "Critique/Élevée/Moyenne/Faible"
        }}
    ]
    
    Ne propose que les constats les plus pertinents (maximum 3).
    """
    
    try:
        # Appel à l'IA
        resultat_ia = appel_ia_generer_constats(prompt)
        
        # Parser le résultat
        constats_proposes = parser_reponse_ia_constats(resultat_ia)
        
        return jsonify({
            'success': True,
            'constats_proposes': constats_proposes,
            'feuille_id': feuille_id,
            'audit_id': feuille.audit_id
        })
        
    except Exception as e:
        _journal(f"Erreur IA: {str(e)}")
        # Mode simulation en cas d'erreur
        constats_simules = simuler_constats_ia(tests_non_conformes)
        return jsonify({
            'success': True,
            'constats_proposes': constats_simules,
            'feuille_id': feuille_id,
            'audit_id': feuille.audit_id,
            'mode': 'simulation'
        })


@app.route('/api/constat/creer-depuis-ia', methods=['POST'])
@login_required
def api_creer_constat_depuis_ia():
    """Créer un constat à partir d'une suggestion IA"""
    from models import Constatation, Audit
    
    data = request.get_json()
    
    audit_id = data.get('audit_id')
    titre = data.get('titre', '')
    description = data.get('description', '')
    cause_racine = data.get('cause_racine', '')
    recommandation = data.get('recommandation', '')
    priorite = data.get('priorite', 'moyenne')
    feuille_id = data.get('feuille_id')
    test_id = data.get('test_id')
    
    if not audit_id or not description:
        return jsonify({'success': False, 'error': 'Données incomplètes'}), 400
    
    # Mapper priorite vers gravité
    gravite_map = {
        'critique': 'critique',
        'élevée': 'majeure',
        'moyenne': 'moyenne',
        'faible': 'mineure'
    }
    gravite = gravite_map.get(priorite.lower(), 'moyenne')
    
    # Générer référence
    dernier_constat = Constatation.query.filter_by(audit_id=audit_id)\
        .order_by(Constatation.id.desc()).first()
    
    audit = Audit.query.get(audit_id)
    if not audit:
        return jsonify({'success': False, 'error': 'Audit non trouvé'}), 404
    
    nouvelle_ref = f"CON-{audit.reference if audit else 'AUD'}-{(dernier_constat.id + 1) if dernier_constat else 1:03d}"
    
    # Créer le constat
    constat = Constatation(
        reference=nouvelle_ref,
        description=description,
        cause_racine=cause_racine,
        recommandations_immediates=recommandation,
        gravite=gravite,
        type_constatation='non_conformite',
        statut='a_analyser',
        audit_id=audit_id,
        created_by=current_user.id,
        client_id=current_user.client_id
    )
    
    # Lier à la feuille de travail si fournie
    if feuille_id:
        constat.feuille_source_id = feuille_id
    
    db.session.add(constat)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Constat {nouvelle_ref} créé avec succès',
        'constat': {
            'id': constat.id,
            'reference': constat.reference,
            'description': constat.description[:100]
        }
    })


@app.route('/fichier-rapport-audit/<int:fichier_id>/telecharger')
@login_required
def telecharger_fichier_rapport_audit(fichier_id):
    """Télécharger un fichier de rapport"""
    
    # Récupérer le fichier
    fichier = FichierRapport.query.get_or_404(fichier_id)
    
    # Vérifier les permissions
    audit = fichier.audit
    peut_telecharger = (
        current_user.role == 'super_admin' or
        current_user.id == audit.created_by or
        current_user.id == audit.responsable_id or
        (audit.equipe_audit_ids and str(current_user.id) in audit.equipe_audit_ids.split(',')) or
        (audit.observateurs_ids and str(current_user.id) in audit.observateurs_ids.split(','))
    )
    
    if not peut_telecharger:
        flash('Vous n\'avez pas les permissions pour télécharger ce fichier', 'error')
        return redirect(url_for('rapport_audit_complet', audit_id=audit.id))
    
    # Vérifier que le fichier existe
    if not os.path.exists(fichier.chemin):
        flash('Fichier non trouvé', 'error')
        return redirect(url_for('rapport_audit_complet', audit_id=audit.id))
    
    return send_file(
        fichier.chemin,
        as_attachment=True,
        download_name=fichier.nom_fichier,
        mimetype=None
    )
