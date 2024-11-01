# tests/test_models.py
from models import Conversation, Message, SenderType, db, User, UserRole, StudentProfile, TeacherProfile
from werkzeug.security import generate_password_hash

def test_create_user(app):
    with app.app_context():
        user = User(
            username='testuser',
            email='testuser@example.com',
            password_hash=generate_password_hash('password123'),
            role=UserRole.STUDENT
        )
        db.session.add(user)
        db.session.commit()

        fetched_user = User.query.filter_by(username='testuser').first()
        assert fetched_user is not None
        assert fetched_user.email == 'testuser@example.com'
        assert fetched_user.role == UserRole.STUDENT

def test_create_student_profile(app):
    with app.app_context():
        # Create user
        user = User(
            username='student1',
            email='student1@example.com',
            password_hash=generate_password_hash('password123'),
            role=UserRole.STUDENT
        )
        db.session.add(user)
        db.session.commit()

        # Create student profile
        student_profile = StudentProfile(
            user_id=user.id,
            daily_question_limit=5
        )
        db.session.add(student_profile)
        db.session.commit()

        # Fetch using Session.get()
        fetched_profile = db.session.get(StudentProfile, user.id)
        assert fetched_profile is not None
        assert fetched_profile.user.username == 'student1'

def test_teacher_student_relationship(app):
    with app.app_context():
        # Create teacher user and profile
        teacher_user = User(
            username='teacher1',
            email='teacher1@example.com',
            password_hash=generate_password_hash('password123'),
            role=UserRole.TEACHER
        )
        teacher_profile = TeacherProfile(user=teacher_user)
        db.session.add(teacher_user)
        db.session.add(teacher_profile)
        db.session.commit()

        # Create student user and profile
        student_user = User(
            username='student2',
            email='student2@example.com',
            password_hash=generate_password_hash('password123'),
            role=UserRole.STUDENT
        )
        db.session.add(student_user)
        db.session.commit()

        student_profile = StudentProfile(
            user=student_user,
            teacher=teacher_user
        )
        db.session.add(student_profile)
        db.session.commit()

        # Fetch and test relationships
        fetched_teacher = User.query.filter_by(username='teacher1').first()
        fetched_student = User.query.filter_by(username='student2').first()

        assert fetched_student.student_profile.teacher == fetched_teacher
        assert fetched_teacher.students[0] == fetched_student.student_profile

def test_conversation_and_messages(app):
    with app.app_context():
        # Create student user and profile
        student_user = User(
            username='student3',
            email='student3@example.com',
            password_hash=generate_password_hash('password123'),
            role=UserRole.STUDENT
        )
        db.session.add(student_user)
        db.session.commit()

        student_profile = StudentProfile(
            user=student_user
        )
        db.session.add(student_profile)
        db.session.commit()

        # Create a conversation
        conversation = Conversation(
            student=student_profile
        )
        db.session.add(conversation)
        db.session.commit()

        # Add messages to the conversation
        message1 = Message(
            conversation=conversation,
            sender_type=SenderType.STUDENT,
            sender_id=student_user.id,
            message_content='How do I write a loop in Python?'
        )
        message2 = Message(
            conversation=conversation,
            sender_type=SenderType.AI_TUTOR,
            message_content='Let me guide you through creating a loop...'
        )
        db.session.add(message1)
        db.session.add(message2)
        db.session.commit()

        # Fetch using Session.get()
        fetched_conversation = db.session.get(Conversation, conversation.id)
        assert fetched_conversation is not None
        assert len(fetched_conversation.messages) == 2
        assert fetched_conversation.messages[0].message_content == 'How do I write a loop in Python?'
        assert fetched_conversation.messages[1].sender_type == SenderType.AI_TUTOR

import sqlalchemy.exc

def test_unique_username(app):
    with app.app_context():
        user1 = User(
            username='uniqueuser',
            email='unique1@example.com',
            password_hash=generate_password_hash('password123'),
            role=UserRole.STUDENT
        )
        db.session.add(user1)
        db.session.commit()

        user2 = User(
            username='uniqueuser',
            email='unique2@example.com',
            password_hash=generate_password_hash('password123'),
            role=UserRole.STUDENT
        )
        db.session.add(user2)
        try:
            db.session.commit()
            assert False, "Expected IntegrityError due to duplicate username."
        except sqlalchemy.exc.IntegrityError:
            db.session.rollback()
