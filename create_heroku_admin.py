from getpass import getpass
import sys
from models import db, User, UserRole
from werkzeug.security import generate_password_hash
from flask import Flask
from dotenv import load_dotenv
import os

def create_admin():
    # Load environment variables from .env file
    load_dotenv()

    # Retrieve database credentials from environment variables
    db_host = os.environ.get('DATABASE_HOST')
    db_name = os.environ.get('DATABASE_NAME')
    db_user = os.environ.get('DATABASE_USER')
    db_password = os.environ.get('DATABASE_PASSWORD')
    db_port = os.environ.get('DATABASE_PORT', '5432')

    if not all([db_host, db_name, db_user, db_password]):
        print('Error: Missing database credentials in environment variables.')
        sys.exit(1)

    # Construct the database URI
    database_uri = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    # Adjust URI if necessary (replace 'postgres://' with 'postgresql://')
    if database_uri.startswith('postgres://'):
        database_uri = database_uri.replace('postgres://', 'postgresql://', 1)

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize the database
    db.init_app(app)

    with app.app_context():
        username = input('Enter username: ').strip()
        email = input('Enter email: ').strip()

        if User.query.filter_by(username=username).first():
            print('Error: Username already exists.')
            sys.exit(1)

        if User.query.filter_by(email=email).first():
            print('Error: Email already exists.')
            sys.exit(1)

        password = getpass('Enter password: ')
        password2 = getpass('Confirm password: ')

        if password != password2:
            print('Error: Passwords do not match.')
            sys.exit(1)

        if not password:
            print('Error: Password cannot be empty.')
            sys.exit(1)

        new_admin = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role=UserRole.TEACHER
        )

        db.session.add(new_admin)
        db.session.commit()
        print('Admin account created successfully.')

if __name__ == '__main__':
    create_admin()
