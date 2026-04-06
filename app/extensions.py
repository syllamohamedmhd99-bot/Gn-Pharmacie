from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

# Setup login logic
login_manager.login_view = 'auth.login' # Dedicated auth blueprint
login_manager.login_message = "Veuillez vous authentifier pour accéder à cette page."
