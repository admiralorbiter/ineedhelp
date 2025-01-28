from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, send_file
from flask_login import login_required, current_user
from models import KnowledgeBaseEntry, UserRole, db
from utils.embeddings import update_entry_embedding
from utils.document_processor import DocumentProcessor
import os
from werkzeug.utils import secure_filename

knowledge_bp = Blueprint('knowledge', __name__, url_prefix='/knowledge')

@knowledge_bp.route('/')
@login_required
def list():
    if current_user.role != UserRole.TEACHER:
        flash('Access denied', 'danger')
        return redirect(url_for('auth.index'))
    
    entries = KnowledgeBaseEntry.query.all()
    return render_template('knowledge_list.html', entries=entries)

@knowledge_bp.route('/add', methods=['POST'])
@login_required
def add():
    if current_user.role != UserRole.TEACHER:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        if 'document' in request.files:
            file = request.files['document']
            if file and file.filename and DocumentProcessor.allowed_file(file.filename):
                # Process document
                content, doc_type = DocumentProcessor.process_document(file)
                
                # Save file
                filename = secure_filename(file.filename)
                # Ensure upload directory exists
                os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                entry = KnowledgeBaseEntry(
                    title=request.form['title'],
                    content=content,
                    category=request.form['category'],
                    tags=request.form['tags'].split(',') if request.form.get('tags') else [],
                    entry_type='document',
                    document_path=file_path,
                    document_type=doc_type
                )
            else:
                flash('Invalid file type or no file provided', 'danger')
                return redirect(url_for('knowledge.list'))
        else:
            # Handle text entry
            entry = KnowledgeBaseEntry(
                title=request.form['title'],
                content=request.form['content'],
                category=request.form['category'],
                tags=request.form['tags'].split(',') if request.form.get('tags') else [],
                entry_type='text'
            )
        
        db.session.add(entry)
        db.session.flush()
        
        # Create and store embedding
        update_entry_embedding(entry)
        
        db.session.commit()
        flash('Knowledge base entry added successfully', 'success')
        return redirect(url_for('knowledge.list'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding entry: {str(e)}', 'danger')
        return redirect(url_for('knowledge.list'))

@knowledge_bp.route('/delete/<int:entry_id>', methods=['POST'])
@login_required
def delete(entry_id):
    if current_user.role != UserRole.TEACHER:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        entry = KnowledgeBaseEntry.query.get_or_404(entry_id)
        db.session.delete(entry)
        db.session.commit()
        flash('Knowledge base entry deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting entry: {str(e)}', 'danger')
    
    return redirect(url_for('knowledge.list'))

# Add download route for documents
@knowledge_bp.route('/download/<int:entry_id>')
@login_required
def download(entry_id):
    if current_user.role != UserRole.TEACHER:
        flash('Access denied', 'danger')
        return redirect(url_for('auth.index'))
    
    entry = KnowledgeBaseEntry.query.get_or_404(entry_id)
    if not entry.document_path or not os.path.exists(entry.document_path):
        flash('Document not found', 'danger')
        return redirect(url_for('knowledge.list'))
    
    return send_file(
        entry.document_path,
        as_attachment=True,
        download_name=os.path.basename(entry.document_path)
    )