from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from models import StudentProfile, User, UserRole, db, Conversation, Message, SenderType, TeacherProfile, KnowledgeBaseEntry
from werkzeug.security import check_password_hash, generate_password_hash
from forms import LoginForm
from datetime import datetime, timezone
import json
from openai import OpenAI
import os
import csv
from io import StringIO
from typing import List, Dict
import tiktoken

from utils.embeddings import find_relevant_knowledge, update_entry_embedding

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
                    return redirect(url_for('admin_dashboard'))  # Teachers still see admin first
                else:
                    return redirect(url_for('tutor'))  # All other roles go to tutor
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
                daily_question_limit=20,
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
        # Get the appropriate profile based on role
        profile = None
        if current_user.role == UserRole.STUDENT:
            profile = current_user.student_profile
            if not profile:
                profile = StudentProfile(user_id=current_user.id)
                db.session.add(profile)
                db.session.commit()  # Commit immediately after creating profile
        else:  # Teacher or other roles
            profile = current_user.teacher_profile
            if not profile:
                profile = TeacherProfile(user_id=current_user.id)
                db.session.add(profile)
                db.session.commit()  # Commit immediately after creating profile
        
        # Get user's chat history
        conversations = Conversation.query.filter_by(
            user_id=current_user.id
        ).order_by(Conversation.updated_at.desc()).all()
        
        chat_history = [{
            'id': conv.id,
            'title': conv.messages[0].message_content[:30] + "..." if conv.messages else "New Chat",
            'date': conv.created_at.strftime("%Y-%m-%d %H:%M")
        } for conv in conversations]

        return render_template('tutor.html', chat_history=chat_history, messages=[])

    @app.route('/tutor/send_message', methods=['POST'])
    @login_required
    def send_message():
        message = request.json.get('message')
        conversation_id = request.json.get('conversation_id')
        
        # Load Socratic prompt
        try:
            with open('socratic_prompt.md', 'r') as f:
                socratic_prompt = f.read()
        except Exception as e:
            print(f"Error loading Socratic prompt: {str(e)}")
            socratic_prompt = "You are a Socratic-style tutor specializing in Python programming."
        
        # Find relevant knowledge base entries
        relevant_knowledge = find_relevant_knowledge(message)
        
        # Add knowledge context to the prompt
        knowledge_context = ""
        if relevant_knowledge:
            knowledge_context = "\n\nRelevant information from our knowledge base:\n"
            for entry in relevant_knowledge:
                knowledge_context += f"- {entry.title}: {entry.content}\n"
        
        # Combine Socratic prompt with knowledge context in a single system message
        combined_prompt = f"""{socratic_prompt}

{knowledge_context}

Remember:
1. Always ask probing questions instead of giving direct answers
2. Guide the student to discover the solution themselves
3. If you have relevant knowledge base information, use it to form questions that lead the student to understand the concept
4. Break down complex problems into smaller, manageable questions
5. Validate student's correct thinking and gently correct misconceptions through questions"""

        # Build the messages list from conversation history
        messages = [{"role": "system", "content": combined_prompt}]  # Single, comprehensive system message
        if conversation_id:
            conversation = Conversation.query.get(conversation_id)
            if conversation:
                for msg in conversation.messages:
                    role = "assistant" if msg.sender_type == SenderType.AI_TUTOR else "user"
                    messages.append({
                        "role": role,
                        "content": msg.message_content
                    })
        
        messages.append({
            "role": "user",
            "content": message
        })
        
        # Get the appropriate profile
        profile = None
        if current_user.role == UserRole.STUDENT:
            profile = current_user.student_profile
            if not profile:
                profile = StudentProfile(user_id=current_user.id)
                db.session.add(profile)
                db.session.commit()
        else:
            profile = current_user.teacher_profile
            if not profile:
                profile = TeacherProfile(user_id=current_user.id)
                db.session.add(profile)
                db.session.commit()

        if not profile:
            return jsonify({'error': 'Profile not found'}), 404

        try:
            # Create new conversation if none exists
            if not conversation_id:
                if not profile.increment_question_count():
                    return jsonify({
                        'error': 'Daily question limit reached. Please try again tomorrow.'
                    }), 429

                conversation = Conversation(user_id=current_user.id)
                db.session.add(conversation)
                db.session.flush()
            else:
                conversation = Conversation.query.get(conversation_id)
                if not conversation or conversation.user_id != current_user.id:
                    return jsonify({'error': 'Invalid conversation'}), 404

            # Save user's message first
            user_message = Message(
                conversation_id=conversation.id,
                sender_type=SenderType.STUDENT,
                sender_id=current_user.id,
                message_content=message
            )
            db.session.add(user_message)
            db.session.flush()

            # Get OpenAI response
            client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages  # Now includes system prompt, history, knowledge context, and user message
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
                        'content': message
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
        if conversation.user_id != current_user.id:
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
            user_id=student.id  # Using user_id instead of student_id
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

    @app.route('/bulk_create_students', methods=['POST'])
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

    @app.route('/knowledge/list')
    @login_required
    def list_knowledge():
        if current_user.role != UserRole.TEACHER:
            flash('Access denied', 'danger')
            return redirect(url_for('index'))
        
        entries = KnowledgeBaseEntry.query.all()
        return render_template('knowledge_list.html', entries=entries)

    @app.route('/knowledge/add', methods=['POST'])
    @login_required
    def add_knowledge():
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
            return redirect(url_for('list_knowledge'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding entry: {str(e)}', 'danger')
            return redirect(url_for('admin_dashboard'))

    @app.route('/knowledge/delete/<int:entry_id>', methods=['POST'])
    @login_required
    def delete_knowledge(entry_id):
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
        
        return redirect(url_for('list_knowledge'))

def count_tokens(messages: List[Dict]) -> int:
    """Count tokens in a list of messages."""
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    num_tokens = 0
    for message in messages:
        # Every message follows {role: ..., content: ...} format
        num_tokens += 4  # Format tax per message
        for key, value in message.items():
            num_tokens += len(encoding.encode(str(value)))
    num_tokens += 2  # Every reply is primed with <im_start>assistant
    return num_tokens

def create_summary(conversation_id: int) -> str:
    """Create a summary of older messages in the conversation."""
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Get all messages except the 10 most recent
    older_messages = Message.query.filter_by(conversation_id=conversation_id)\
        .order_by(Message.timestamp.desc())\
        .offset(10)\
        .limit(50)\
        .all()
    
    if not older_messages:
        return None
        
    # Format messages for summarization
    messages_text = "\n".join([
        f"{'Student' if msg.sender_type == SenderType.STUDENT else 'Tutor'}: {msg.message_content}"
        for msg in older_messages
    ])
    
    # Get summary from OpenAI
    summary_response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Summarize the key points of this tutoring conversation, focusing on the main concepts discussed and questions asked."},
            {"role": "user", "content": messages_text}
        ]
    )
    
    return summary_response.choices[0].message.content