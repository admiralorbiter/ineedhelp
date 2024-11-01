# models.py

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from enum import Enum
from flask_login import UserMixin

db = SQLAlchemy()

# Enums for user roles and sender types
class UserRole(Enum):
    STUDENT = 'student'
    TEACHER = 'teacher'
    SUPER_ADMIN = 'super_admin'

class SenderType(Enum):
    STUDENT = 'student'
    AI_TUTOR = 'ai_tutor'
    TEACHER = 'teacher'

# User model
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    role = db.Column(db.Enum(UserRole), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

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
class StudentProfile(db.Model):
    __tablename__ = 'student_profiles'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    daily_question_limit = db.Column(db.Integer, default=5)
    questions_asked_today = db.Column(db.Integer, default=0)
    last_question_reset = db.Column(db.Date, default=date.today)

    # Relationships
    user = db.relationship(
        'User',
        back_populates='student_profile',
        foreign_keys=[user_id]
    )
    teacher = db.relationship(
        'User',
        back_populates='students',
        foreign_keys=[teacher_id]
    )

    conversations = db.relationship(
        'Conversation',
        back_populates='student',
        foreign_keys='Conversation.student_id'
    )

    def __repr__(self):
        return f'<StudentProfile {self.user.username}>'

# TeacherProfile model
class TeacherProfile(db.Model):
    __tablename__ = 'teacher_profiles'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)

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
    student_id = db.Column(db.Integer, db.ForeignKey('student_profiles.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    student = db.relationship(
        'StudentProfile',
        back_populates='conversations',
        foreign_keys=[student_id]
    )
    messages = db.relationship(
        'Message',
        back_populates='conversation',
        order_by='Message.timestamp'
    )

    def __repr__(self):
        return f'<Conversation {self.id} by Student {self.student.user.username}>'

# Message model
class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False)
    sender_type = db.Column(db.Enum(SenderType), nullable=False)
    sender_id = db.Column(db.Integer, nullable=True)  # Null if sender is AI tutor
    message_content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

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
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<PromptCustomization {self.prompt_name}>'

# AuditLog model
class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(128), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    details = db.Column(db.Text)

    # Relationships
    user = db.relationship('User', back_populates='audit_logs')

    def __repr__(self):
        return f'<AuditLog {self.action} by User {self.user.username}>'

