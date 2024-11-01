# config.py
class Config:
    SECRET_KEY = 'your_secret_key'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Other common configurations

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///your_database.db'

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///test_database.db'
    WTF_CSRF_ENABLED = False  # Disable CSRF for testing
    # Other testing configurations

class ProductionConfig(Config):
    DEBUG = False
    # Use your production database URI
    SQLALCHEMY_DATABASE_URI = 'sqlite:///prod_database.db'