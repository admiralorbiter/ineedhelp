from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import KnowledgeBaseEntry, UserRole, db
from utils.embeddings import update_entry_embedding

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
        entry = KnowledgeBaseEntry(
            title=request.form['title'],
            content=request.form['content'],
            category=request.form['category'],
            tags=request.form['tags'].split(',') if request.form['tags'] else []
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
        return redirect(url_for('admin.dashboard'))

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