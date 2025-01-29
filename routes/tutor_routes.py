from flask import Blueprint, current_app, render_template, request, jsonify, send_from_directory
from flask_login import login_required, current_user
from models import Conversation, Message, SenderType, StudentProfile, TeacherProfile, UserRole, db
from datetime import datetime, timezone
from openai import OpenAI
import os
from utils.embeddings import find_relevant_knowledge
from utils.adaptive_prompt import AdaptivePromptManager
from werkzeug.utils import secure_filename

tutor_bp = Blueprint('tutor', __name__, url_prefix='/tutor')

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'py'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@tutor_bp.route('/')
@login_required
def chat():
    # Get the appropriate profile based on role
    profile = None
    if current_user.role == UserRole.STUDENT:
        profile = current_user.student_profile
        if not profile:
            profile = StudentProfile(user_id=current_user.id)
            db.session.add(profile)
            db.session.commit()
    else:  # Teacher or other roles
        profile = current_user.teacher_profile
        if not profile:
            profile = TeacherProfile(user_id=current_user.id)
            db.session.add(profile)
            db.session.commit()
    
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

@tutor_bp.route('/send_message', methods=['POST'])
@login_required
def send_message():
    message = request.form.get('message', '')
    conversation_id = request.form.get('conversation_id')
    
    # Handle file upload
    file_path = None
    if 'file' in request.files:
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Include user ID in path for security
            user_folder = str(current_user.id)
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], user_folder)
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save file with user ID prefix
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
            
            # Update message with file path including user ID
            relative_path = f"{user_folder}/{filename}"
            if message:
                message += f"\n[Attached file: {relative_path}]"
            else:
                message = f"[Attached file: {relative_path}]"
    
    # Get student profile
    profile = current_user.student_profile
    
    # Initialize adaptive prompt manager
    prompt_manager = AdaptivePromptManager(profile)
    
    # Load and adapt the Socratic prompt
    try:
        with open('socratic_prompt.md', 'r') as f:
            base_prompt = f.read()
        adapted_prompt = prompt_manager.generate_adaptive_prompt(base_prompt)
    except Exception as e:
        print(f"Error loading Socratic prompt: {str(e)}")
        adapted_prompt = "You are a Socratic-style tutor specializing in Python programming."
    
    # Find relevant knowledge base entries
    relevant_knowledge = find_relevant_knowledge(message)
    
    # Add knowledge context to the prompt
    knowledge_context = ""
    if relevant_knowledge:
        knowledge_context = "\n\nRelevant information from our knowledge base:\n"
        for entry in relevant_knowledge:
            knowledge_context += f"- {entry.title}: {entry.content}\n"
    
    # Combine Socratic prompt with knowledge context in a single system message
    combined_prompt = f"""{adapted_prompt}

{knowledge_context}

Remember:
1. Always ask probing questions instead of giving direct answers
2. Guide the student to discover the solution themselves
3. If you have relevant knowledge base information, use it to form questions that lead the student to understand the concept
4. Break down complex problems into smaller, manageable questions
5. Validate student's correct thinking and gently correct misconceptions through questions"""

    # Build the messages list from conversation history
    messages = [{"role": "system", "content": combined_prompt}]
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
            messages=messages
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

@tutor_bp.route('/get_conversation/<int:conversation_id>')
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

@tutor_bp.route('/interaction_feedback', methods=['POST'])
@login_required
def interaction_feedback():
    if current_user.role != UserRole.STUDENT:
        return jsonify({'error': 'Only students can provide interaction feedback'}), 403
        
    data = request.json
    message_id = data.get('message_id')
    was_helpful = data.get('was_helpful', False)
    understood_concept = data.get('understood_concept', False)
    
    try:
        # Get the student profile
        profile = current_user.student_profile
        if not profile:
            return jsonify({'error': 'Student profile not found'}), 404
            
        # Update metrics
        profile.total_questions += 1
        if understood_concept:
            profile.successful_interactions += 1
            profile.consecutive_successes += 1
            profile.consecutive_failures = 0
        else:
            profile.consecutive_failures += 1
            profile.consecutive_successes = 0
            
        # Update skill level based on new metrics
        profile.update_skill_level()
        
        # Update topic proficiency if provided
        topic = data.get('topic')
        if topic:
            current_proficiency = profile.topic_proficiency.get(topic, {})
            current_proficiency['attempts'] = current_proficiency.get('attempts', 0) + 1
            current_proficiency['successes'] = current_proficiency.get('successes', 0) + (1 if understood_concept else 0)
            profile.topic_proficiency[topic] = current_proficiency
            
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating interaction feedback: {str(e)}")
        return jsonify({'error': 'Failed to update feedback'}), 500

@tutor_bp.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    # Get user ID from the path
    user_id = filename.split('/')[0]
    
    # Security check - only allow access to own files
    if str(current_user.id) != user_id:
        return jsonify({'error': 'Unauthorized'}), 403
        
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'])
    return send_from_directory(upload_dir, filename)
