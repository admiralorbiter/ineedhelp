from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from models import StudentProfile, User, UserRole, db, Conversation, Message, SenderType
from werkzeug.security import check_password_hash, generate_password_hash
from forms import LoginForm
from datetime import datetime, timezone
import json
from openai import OpenAI
import os

def init_routes(app):
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            if user and check_password_hash(user.password_hash, form.password.data):
                login_user(user)
                flash('Logged in successfully.', 'success')
                # Redirect based on user role
                if user.role == UserRole.TEACHER:
                    return redirect(url_for('admin_dashboard'))
                elif user.role == UserRole.STUDENT:
                    return redirect(url_for('tutor'))
            else:
                flash('Invalid username or password.', 'danger')
        return render_template('login.html', form=form)

    @app.route('/admin/dashboard', methods=['GET'])
    @login_required
    def admin_dashboard():
        if current_user.role != UserRole.TEACHER:
            flash('Access denied: You are not an admin.', 'danger')
            return redirect(url_for('index'))
        
        # Query all students
        students = User.query.filter_by(role=UserRole.STUDENT).all()
        return render_template('admin_dashboard.html', students=students)

    @app.route('/create_student', methods=['POST'])
    @login_required
    def create_student():
        if current_user.role != UserRole.TEACHER:
            flash('Access denied: You are not authorized to create students.', 'danger')
            return redirect(url_for('index'))

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

            # Add user first
            db.session.add(new_student)
            db.session.flush()  # This assigns the ID to new_student

            # Create associated student profile
            student_profile = StudentProfile(
                user_id=new_student.id,
                daily_question_limit=5,
                questions_asked_today=0
            )
            db.session.add(student_profile)
            
            db.session.commit()
            flash('Student account created successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error creating student account. Please try again.', 'danger')
            print(f"Error: {str(e)}")

        return redirect(url_for('admin_dashboard'))

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('index')) 
    
    @app.route('/tutor')
    @login_required
    def tutor():
        # Get user's chat history
        chat_history = []
        if current_user.student_profile:
            conversations = Conversation.query.filter_by(
                student_id=current_user.student_profile.user_id
            ).order_by(Conversation.updated_at.desc()).all()
            
            chat_history = [{
                'id': conv.id,
                'title': conv.messages[0].message_content[:30] + "..." if conv.messages else "New Chat",
                'date': conv.created_at.strftime("%Y-%m-%d %H:%M")
            } for conv in conversations]

        # For now, return empty messages for new chat
        messages = []
        
        return render_template('tutor.html', chat_history=chat_history, messages=messages)

    @app.route('/tutor/send_message', methods=['POST'])
    @login_required
    def send_message():
        # Check if user is a student
        if current_user.role != UserRole.STUDENT:
            return jsonify({'error': 'Only students can use the tutor'}), 403

        # Ensure student profile exists
        if not hasattr(current_user, 'student_profile') or not current_user.student_profile:
            # Create student profile if it doesn't exist
            student_profile = StudentProfile(user_id=current_user.id)
            db.session.add(student_profile)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"Error creating student profile: {str(e)}")
                return jsonify({'error': 'Failed to create student profile'}), 500

        # Check quota before processing message
        if not current_user.student_profile.can_ask_question():
            return jsonify({
                'error': 'Daily question limit reached. Please try again tomorrow.'
            }), 429  # 429 Too Many Requests

        data = request.get_json()
        message_content = data.get('message')
        conversation_id = data.get('conversation_id')

        if not message_content:
            return jsonify({'error': 'Message content is required'}), 400

        try:
            # Create new conversation if none exists
            if not conversation_id:
                # Increment question count before creating new conversation
                if not current_user.student_profile.increment_question_count():
                    return jsonify({
                        'error': 'Daily question limit reached. Please try again tomorrow.'
                    }), 429

                conversation = Conversation(student_id=current_user.student_profile.user_id)
                db.session.add(conversation)
                db.session.flush()
            else:
                conversation = Conversation.query.get(conversation_id)
                if not conversation or conversation.student_id != current_user.student_profile.user_id:
                    return jsonify({'error': 'Invalid conversation'}), 404

            # Save user message
            user_message = Message(
                conversation_id=conversation.id,
                sender_type=SenderType.STUDENT,
                sender_id=current_user.id,
                message_content=message_content
            )
            db.session.add(user_message)

            # Make OpenAI API call
            client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "As a Python programming tutor, your role is to assist students in understanding concepts and solving problems without providing direct answers. Use the Socratic method by asking guiding questions that encourage critical thinking. Provide helpful hints, clarify concepts, and break down complex ideas into simpler parts. Focus on fostering the student's problem-solving skills and understanding of Python programming."},
                    {"role": "user", "content": message_content}
                ]
            )
            
            ai_response = response.choices[0].message.content

            # Save AI response
            ai_message = Message(
                conversation_id=conversation.id,
                sender_type=SenderType.AI_TUTOR,
                message_content=ai_response
            )
            db.session.add(ai_message)

            # Update conversation timestamp
            conversation.updated_at = datetime.now(timezone.utc)
            
            db.session.commit()

            return jsonify({
                'success': True,
                'conversation_id': conversation.id,
                'messages': [
                    {
                        'role': 'user',
                        'content': message_content
                    },
                    {
                        'role': 'assistant',
                        'content': ai_response
                    }
                ]
            })

        except Exception as e:
            db.session.rollback()
            print(f"Error: {str(e)}")
            return jsonify({'error': 'Failed to send message'}), 500

    @app.route('/tutor/get_conversation/<int:conversation_id>')
    @login_required
    def get_conversation(conversation_id):
        conversation = Conversation.query.get_or_404(conversation_id)
        
        # Verify the conversation belongs to the current user
        if conversation.student_id != current_user.student_profile.user_id:
            return jsonify({'error': 'Unauthorized'}), 403

        messages = [{
            'role': 'assistant' if msg.sender_type == SenderType.AI_TUTOR else 'user',
            'content': msg.message_content
        } for msg in conversation.messages]

        return jsonify({'messages': messages})

    @app.route('/dashboard')
    @login_required
    def dashboard():
        return render_template('dashboard.html')

    @app.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
    @login_required
    def edit_student(student_id):
        if current_user.role != UserRole.TEACHER:
            flash('Access denied: You are not authorized to edit students.', 'danger')
            return redirect(url_for('index'))
        
        student = User.query.get_or_404(student_id)
        
        if request.method == 'POST':
            try:
                student.first_name = request.form['firstName']
                student.last_name = request.form['lastName']
                student.email = request.form['email']
                student.username = request.form['email']  # Update username if email changes
                
                # Only update password if a new one is provided
                if request.form['password']:
                    student.password_hash = generate_password_hash(request.form['password'])
                
                db.session.commit()
                flash('Student information updated successfully!', 'success')
                return redirect(url_for('admin_dashboard'))
            except Exception as e:
                db.session.rollback()
                flash('Error updating student information. Please try again.', 'danger')
                print(f"Error: {str(e)}")  # For debugging
        
        return render_template('edit_student.html', student=student)

    @app.route('/delete_student/<int:student_id>', methods=['POST'])
    @login_required
    def delete_student(student_id):
        if current_user.role != UserRole.TEACHER:
            flash('Access denied: You are not authorized to delete students.', 'danger')
            return redirect(url_for('index'))
        
        student = User.query.get_or_404(student_id)
        try:
            db.session.delete(student)
            db.session.commit()
            flash('Student account deleted successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error deleting student account. Please try again.', 'danger')
            print(f"Error: {str(e)}")  # For debugging
        
        return redirect(url_for('admin_dashboard'))

    @app.route('/student/history/<int:student_id>')
    @login_required
    def student_history(student_id):
        if current_user.role != UserRole.TEACHER:
            flash('Access denied: You are not authorized to view student history.', 'danger')
            return redirect(url_for('index'))
        
        # Get the student
        student = User.query.get_or_404(student_id)
        if student.role != UserRole.STUDENT:
            flash('Invalid student ID.', 'danger')
            return redirect(url_for('admin_dashboard'))
        
        # Get all conversations for this student
        conversations = Conversation.query.filter_by(
            student_id=student.student_profile.user_id
        ).order_by(Conversation.created_at.desc()).all()
        
        return render_template('student_history.html', 
                             student=student, 
                             conversations=conversations)

    @app.route('/adjust_questions/<int:student_id>/<action>', methods=['POST'])
    @login_required
    def adjust_questions(student_id, action):
        if current_user.role != UserRole.TEACHER:
            flash('Access denied: You are not authorized to adjust questions.', 'danger')
            return redirect(url_for('index'))
        
        student = User.query.get_or_404(student_id)
        if not student.student_profile:
            flash('Student profile not found.', 'danger')
            return redirect(url_for('admin_dashboard'))
        
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
        
        return redirect(url_for('admin_dashboard'))