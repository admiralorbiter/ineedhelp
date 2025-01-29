# models.py

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timezone
from enum import Enum
from flask_login import UserMixin

db = SQLAlchemy()

# Enums for user roles and sender types
class UserRole(Enum):
    STUDENT = 'student'
    TEACHER = 'teacher'
    SUPER_ADMIN = 'super_admin'

class SenderType(str, Enum):
    STUDENT = 'student'
    AI_TUTOR = 'ai_tutor'
    TEACHER = 'teacher'

# Add this mixin class for shared functionality
class QuestionLimitMixin:
    daily_question_limit = db.Column(db.Integer, nullable=False)
    questions_asked_today = db.Column(db.Integer, default=0)
    last_question_reset = db.Column(db.Date, default=date.today)

    def can_ask_question(self):
        """Check if user can ask more questions today."""
        today = date.today()
        
        if self.last_question_reset < today:
            self.questions_asked_today = 0
            self.last_question_reset = today
            db.session.commit()
            
        return self.questions_asked_today < self.daily_question_limit
    
    def increment_question_count(self):
        """Increment the questions asked counter."""
        if self.can_ask_question():
            self.questions_asked_today += 1
            db.session.commit()
            return True
        return False

# User model
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    role = db.Column(db.Enum(UserRole), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # One-to-one relationships
    student_profile = db.relationship(
        'StudentProfile',
        back_populates='user',
        uselist=False,
        foreign_keys='StudentProfile.user_id'
    )
    teacher_profile = db.relationship(
        'TeacherProfile',
        back_populates='user',
        uselist=False,
        foreign_keys='TeacherProfile.user_id'
    )

    # For teachers: relationship to their students
    students = db.relationship(
        'StudentProfile',
        back_populates='teacher',
        foreign_keys='StudentProfile.teacher_id'
    )

    # Relationships for messaging
    sent_admin_messages = db.relationship(
        'AdminMessage',
        foreign_keys='AdminMessage.sender_id',
        back_populates='sender'
    )
    received_admin_messages = db.relationship(
        'AdminMessage',
        foreign_keys='AdminMessage.recipient_id',
        back_populates='recipient'
    )

    # Audit logs
    audit_logs = db.relationship('AuditLog', back_populates='user')

    def __repr__(self):
        return f'<User {self.username}>'

# StudentProfile model
class StudentProfile(db.Model, QuestionLimitMixin):
    __tablename__ = 'student_profiles'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    daily_question_limit = db.Column(db.Integer, default=20)
    
    # New fields for adaptive prompting
    skill_level = db.Column(db.String(20), default='beginner')  # beginner, intermediate, advanced
    consecutive_successes = db.Column(db.Integer, default=0)
    consecutive_failures = db.Column(db.Integer, default=0)
    total_questions = db.Column(db.Integer, default=0)
    successful_interactions = db.Column(db.Integer, default=0)
    
    # Topic-specific proficiency (stored as JSON)
    topic_proficiency = db.Column(db.JSON, default=dict)
    
    # Learning preferences
    needs_detailed_explanations = db.Column(db.Boolean, default=True)
    prefers_examples = db.Column(db.Boolean, default=True)

    # Relationships
    user = db.relationship('User', back_populates='student_profile', foreign_keys=[user_id])
    teacher = db.relationship('User', back_populates='students', foreign_keys=[teacher_id])

    def update_skill_level(self):
        """Update skill level based on performance metrics"""
        success_rate = self.successful_interactions / max(self.total_questions, 1)
        
        if success_rate >= 0.8 and self.consecutive_successes >= 5:
            self.skill_level = 'advanced'
        elif success_rate >= 0.6 and self.consecutive_successes >= 3:
            self.skill_level = 'intermediate'
        else:
            self.skill_level = 'beginner'

    def __repr__(self):
        return f'<StudentProfile {self.user.username}>'

# TeacherProfile model
class TeacherProfile(db.Model, QuestionLimitMixin):
    __tablename__ = 'teacher_profiles'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    daily_question_limit = db.Column(db.Integer, default=50)

    # Relationships
    user = db.relationship(
        'User',
        back_populates='teacher_profile',
        foreign_keys=[user_id]
    )

    def __repr__(self):
        return f'<TeacherProfile {self.user.username}>'

# Conversation model
class Conversation(db.Model):
    __tablename__ = 'conversations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Update relationships
    user = db.relationship('User', backref='conversations')
    messages = db.relationship(
        'Message',
        back_populates='conversation',
        order_by='Message.timestamp'
    )

    def __repr__(self):
        return f'<Conversation {self.id} by User {self.user.username}>'

# Message model
class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False)
    sender_type = db.Column(db.Enum(SenderType, native_enum=False), nullable=False)
    sender_id = db.Column(db.Integer, nullable=True)  # Null if sender is AI tutor
    message_content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    conversation = db.relationship('Conversation', back_populates='messages')

    def __repr__(self):
        return f'<Message {self.id} in Conversation {self.conversation_id}>'

# AdminMessage model
class AdminMessage(db.Model):
    __tablename__ = 'admin_messages'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    message_content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    is_read = db.Column(db.Boolean, default=False)

    # Relationships
    sender = db.relationship(
        'User',
        foreign_keys=[sender_id],
        back_populates='sent_admin_messages'
    )
    recipient = db.relationship(
        'User',
        foreign_keys=[recipient_id],
        back_populates='received_admin_messages'
    )

    def __repr__(self):
        return f'<AdminMessage {self.id} from {self.sender.username} to {self.recipient.username}>'

# PromptCustomization model
class PromptCustomization(db.Model):
    __tablename__ = 'prompt_customizations'

    id = db.Column(db.Integer, primary_key=True)
    prompt_name = db.Column(db.String(128), unique=True, nullable=False)
    prompt_text = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f'<PromptCustomization {self.prompt_name}>'

# AuditLog model
class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(128), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    details = db.Column(db.Text)

    # Relationships
    user = db.relationship('User', back_populates='audit_logs')

    def __repr__(self):
        return f'<AuditLog {self.action} by User {self.user.username}>'

class KnowledgeBaseEntry(db.Model):
    __tablename__ = 'knowledge_base'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(128))
    tags = db.Column(db.JSON)
    entry_type = db.Column(db.String(50), nullable=False, default='text')  # 'text' or 'document'
    document_path = db.Column(db.String(512))  # S3 or file system path
    document_type = db.Column(db.String(50))  # 'pdf', 'docx', etc.
    embedding = db.Column(db.JSON)  # Store vector embeddings
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))

