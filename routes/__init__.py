from flask import Blueprint
from .auth_routes import auth_bp
from .admin_routes import admin_bp
from .tutor_routes import tutor_bp
from .student_routes import student_bp
from .knowledge_routes import knowledge_bp

def init_routes(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(tutor_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(knowledge_bp)
