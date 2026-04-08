import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'super-secret-key-change-in-prod'
    
    # SQLALCHEMY Configuration
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.strip():
        # Nettoyage de l'URL pour la compatibilité avec psycopg2
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        
        # Supprime ?pgbouncer=true qui fait planter psycopg2
        if "?pgbouncer=true" in db_url:
            db_url = db_url.replace("?pgbouncer=true", "")
        elif "&pgbouncer=true" in db_url:
            db_url = db_url.replace("&pgbouncer=true", "")
            
        SQLALCHEMY_DATABASE_URI = db_url
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Flask-Session
    SESSION_TYPE = os.environ.get('SESSION_TYPE') or 'filesystem'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    
    # Mail Settings (Default: Gmail)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@pharma.com')

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    # In production, we'll use filesystem for now to avoid Redis timeouts on boot
    SESSION_TYPE = 'filesystem'
    
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
