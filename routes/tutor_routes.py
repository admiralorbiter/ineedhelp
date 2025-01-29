from flask import Blueprint, current_app, render_template, request, jsonify, send_from_directory
from flask_login import login_required, current_user
from models import Conversation, Message, SenderType, StudentProfile, TeacherProfile, UserRole, db
from datetime import datetime, timezone
from openai import OpenAI
import os
from utils.embeddings import find_relevant_knowledge
from utils.adaptive_prompt import AdaptivePromptManager
from werkzeug.utils import secure_filename
from enum import Enum
from typing import Optional
import base64
from werkzeug.datastructures import FileStorage

tutor_bp = Blueprint('tutor', __name__, url_prefix='/tutor')

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'py'}

class AIModel(Enum):
    GPT35 = "gpt-3.5-turbo"          # Default model for text conversations
    GPT4_TURBO = "gpt-4o-mini"  # For file and image analysis

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def select_model(file: Optional[FileStorage] = None) -> AIModel:
    """
    Select appropriate AI model based on input type
    """
    try:
        if file and file.filename:
            # Use GPT4 Turbo for any file processing (images or code)
            return AIModel.GPT4_TURBO
        # Default to GPT-3.5 for text-only conversations
        return AIModel.GPT35
    except Exception as e:
        print(f"Error selecting model: {str(e)}")
        # Fallback to GPT-3.5 if any error occurs
        return AIModel.GPT35

def prepare_messages(message: str, file: Optional[FileStorage], base_messages: list) -> list:
    """
    Prepare messages for the AI model, including file content if present
    """
    if not file or not file.filename:
        return base_messages + [{"role": "user", "content": message}]

    if file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        # Prepare vision-enabled message
        file_content = file.read()
        file.seek(0)  # Reset file pointer for later use
        return base_messages + [{
            "role": "user",
            "content": [
                {"type": "text", "text": message},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64.b64encode(file_content).decode()}"
                    }
                }
            ]
        }]
    
    return base_messages + [{"role": "user", "content": message}]

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
    try:
        message = request.form.get('message', '')
        conversation_id = request.form.get('conversation_id')
        file = request.files.get('file')
        
        # Debug logging
        print(f"Received message: {message}")
        print(f"Conversation ID: {conversation_id}")
        print(f"File: {file.filename if file else None}")
        
        # Get student profile for adaptive prompting
        profile = current_user.student_profile
        if not profile:
            # Create profile if it doesn't exist
            profile = StudentProfile(user_id=current_user.id)
            db.session.add(profile)
            db.session.commit()
        
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
        try:
            relevant_knowledge = find_relevant_knowledge(message)
            knowledge_context = ""
            if relevant_knowledge:
                knowledge_context = "\n\nRelevant information from our knowledge base:\n"
                for entry in relevant_knowledge:
                    knowledge_context += f"- {entry.title}: {entry.content}\n"
        except Exception as e:
            print(f"Error finding relevant knowledge: {str(e)}")
            knowledge_context = ""
        
        # Combine prompts
        combined_prompt = f"""{adapted_prompt}

{knowledge_context}

Remember:
1. Always ask probing questions instead of giving direct answers
2. Guide the student to discover the solution themselves
3. If you have relevant knowledge base information, use it to form questions that lead the student to understand the concept
4. Break down complex problems into smaller, manageable questions
5. Validate student's correct thinking and gently correct misconceptions through questions"""

        # Handle file upload
        file_path = None
        if file and allowed_file(file.filename):
            try:
                filename = secure_filename(file.filename)
                user_folder = str(current_user.id)
                upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], user_folder)
                os.makedirs(upload_dir, exist_ok=True)
                
                file_path = os.path.join(upload_dir, filename)
                relative_path = f"{user_folder}/{filename}"
                
                # Update message with file reference
                if message:
                    message += f"\n[Attached file: {relative_path}]"
                else:
                    message = f"[Attached file: {relative_path}]"
            except Exception as e:
                print(f"Error handling file upload: {str(e)}")
                return jsonify({'error': 'Failed to process file upload'}), 500

        # Select appropriate model
        model = select_model(file)
        print(f"Selected model: {model.value}")
        
        # Build base messages
        base_messages = [{"role": "system", "content": combined_prompt}]
        if conversation_id:
            conversation = Conversation.query.get(conversation_id)
            if conversation:
                for msg in conversation.messages:
                    role = "assistant" if msg.sender_type == SenderType.AI_TUTOR else "user"
                    base_messages.append({
                        "role": role,
                        "content": msg.message_content
                    })

        # Prepare final messages
        messages = prepare_messages(message, file, base_messages)

        # Get OpenAI response
        try:
            client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            if not client.api_key:
                raise ValueError("OpenAI API key not found")
                
            response = client.chat.completions.create(
                model=model.value,
                messages=messages,
                max_tokens=500 if model == AIModel.GPT4_TURBO else None
            )
            
            # Save the file after successful API call
            if file_path:
                file.save(file_path)

            ai_response = response.choices[0].message.content
            
            # Create new conversation if none exists
            if not conversation_id:
                conversation = Conversation(user_id=current_user.id)
                db.session.add(conversation)
                db.session.flush()
            
            # Save messages to database
            user_message = Message(
                conversation_id=conversation.id,
                sender_type=SenderType.STUDENT,
                sender_id=current_user.id,
                message_content=message
            )
            ai_message = Message(
                conversation_id=conversation.id,
                sender_type=SenderType.AI_TUTOR,
                message_content=ai_response
            )
            
            db.session.add_all([user_message, ai_message])
            db.session.commit()

            return jsonify({
                'success': True,
                'conversation_id': conversation.id,
                'messages': [
                    {'role': 'user', 'content': message},
                    {
                        'role': 'assistant', 
                        'content': ai_response,
                        'model': model.value
                    }
                ]
            })

        except Exception as e:
            print(f"Error in OpenAI API call: {str(e)}")
            return jsonify({'error': f'OpenAI API error: {str(e)}'}), 500

    except Exception as e:
        db.session.rollback()
        print(f"Unexpected error in send_message: {str(e)}")
        return jsonify({'error': 'Failed to process message'}), 500

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
