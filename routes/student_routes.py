from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from models import User, UserRole, Conversation

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/history/<int:student_id>')
@login_required
def history(student_id):
    if current_user.role != UserRole.TEACHER:
        flash('Access denied: You are not authorized to view student history.', 'danger')
        return redirect(url_for('auth.index'))
    
    # Get the student
    student = User.query.get_or_404(student_id)
    if student.role != UserRole.STUDENT:
        flash('Invalid student ID.', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    # Get all conversations for this student
    conversations = Conversation.query.filter_by(
        user_id=student.id
    ).order_by(Conversation.created_at.desc()).all()
    
    return render_template('student_history.html', 
                         student=student, 
                         conversations=conversations)