from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Conversation, User, UserRole, StudentProfile, db
from werkzeug.security import generate_password_hash
from io import StringIO
import csv

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    if current_user.role != UserRole.TEACHER:
        flash('Access denied: You are not an admin.', 'danger')
        return redirect(url_for('auth.index'))
    
    # Query all students with their profiles
    students = User.query.filter_by(role=UserRole.STUDENT).all()
    
    # Ensure all students have profiles and skill levels
    for student in students:
        if not student.student_profile:
            profile = StudentProfile(
                user_id=student.id,
                daily_question_limit=20,
                questions_asked_today=0,
                skill_level='beginner',  # Default skill level
                reading_level='G6'  # Default to Grade 6
            )
            db.session.add(profile)
    
    db.session.commit()
    return render_template('admin_dashboard.html', students=students)

@admin_bp.route('/create_student', methods=['POST'])
@login_required
def create_student():
    if current_user.role != UserRole.TEACHER:
        flash('Access denied: You are not authorized to create students.', 'danger')
        return redirect(url_for('auth.index'))

    try:
        # Create new student user
        new_student = User(
            username=request.form['email'],
            email=request.form['email'],
            first_name=request.form['firstName'],
            last_name=request.form['lastName'],
            password_hash=generate_password_hash(request.form['password']),
            role=UserRole.STUDENT
        )

        db.session.add(new_student)
        db.session.flush()

        # Create associated student profile
        student_profile = StudentProfile(
            user_id=new_student.id,
            daily_question_limit=20,
            questions_asked_today=0,
            reading_level='G6'  # Default to Grade 6
        )
        db.session.add(student_profile)
        
        db.session.commit()
        flash('Student account created successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error creating student account. Please try again.', 'danger')
        print(f"Error: {str(e)}")

    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    if current_user.role != UserRole.TEACHER:
        flash('Access denied: You are not authorized to edit students.', 'danger')
        return redirect(url_for('auth.index'))
    
    student = User.query.get_or_404(student_id)
    
    if request.method == 'POST':
        try:
            student.first_name = request.form['firstName']
            student.last_name = request.form['lastName']
            student.email = request.form['email']
            student.username = request.form['email']
            
            # Update profiles
            if student.student_profile:
                student.student_profile.skill_level = request.form['skill_level']
                student.student_profile.reading_level = request.form['reading_level']
            else:
                profile = StudentProfile(
                    user_id=student.id,
                    skill_level=request.form['skill_level'],
                    reading_level=request.form['reading_level']
                )
                db.session.add(profile)
            
            # Only update password if a new one is provided
            if request.form['password']:
                student.password_hash = generate_password_hash(request.form['password'])
            
            db.session.commit()
            flash('Student information updated successfully!', 'success')
            return redirect(url_for('admin.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating student information. Please try again.', 'danger')
            print(f"Error: {str(e)}")
    
    return render_template('edit_student.html', student=student)

@admin_bp.route('/delete_student/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    if current_user.role != UserRole.TEACHER:
        flash('Access denied: You are not authorized to delete students.', 'danger')
        return redirect(url_for('auth.index'))
    
    student = User.query.get_or_404(student_id)
    try:
        db.session.delete(student)
        db.session.commit()
        flash('Student account deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting student account. Please try again.', 'danger')
        print(f"Error: {str(e)}")
    
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/bulk_create_students', methods=['POST'])
@login_required
def bulk_create_students():
    if current_user.role != UserRole.TEACHER:
        return jsonify({'error': 'Unauthorized'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be CSV format'}), 400

    try:
        # Read CSV file
        stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.reader(stream)
        
        success_count = 0
        error_count = 0
        errors = []

        for row in csv_reader:
            try:
                if len(row) != 4:
                    continue
                
                first_name, last_name, email, password = row
                
                # Create new student user
                new_student = User(
                    username=email,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password_hash=generate_password_hash(password),
                    role=UserRole.STUDENT
                )

                db.session.add(new_student)
                db.session.flush()

                # Create associated student profile
                student_profile = StudentProfile(
                    user_id=new_student.id,
                    daily_question_limit=20,
                    questions_asked_today=0
                )
                db.session.add(student_profile)
                success_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"Error with {email}: {str(e)}")
                continue

        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Successfully created {success_count} students. {error_count} errors.',
            'errors': errors
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/adjust_questions/<int:student_id>/<action>', methods=['POST'])
@login_required
def adjust_questions(student_id, action):
    if current_user.role != UserRole.TEACHER:
        flash('Access denied: You are not authorized to adjust questions.', 'danger')
        return redirect(url_for('auth.index'))
    
    student = User.query.get_or_404(student_id)
    if not student.student_profile:
        flash('Student profile not found.', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    try:
        if action == 'add':
            # Add 5 to daily limit
            student.student_profile.daily_question_limit += 5
            flash(f'Added 5 questions to {student.first_name}\'s daily limit.', 'success')
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash('Error adjusting questions. Please try again.', 'danger')
        print(f"Error: {str(e)}")
    
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/student/history/<int:student_id>')
@login_required
def student_history(student_id):
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