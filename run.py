print("--- INITIALISATION PHARMACLOUD SYSTEM ---")
from app import create_app
from app.extensions import db
import os

# Determiner l'environnement, sinon defaut
app = create_app(os.getenv('FLASK_ENV') or 'default')

if __name__ == '__main__':
    # Création des tables automatiques en Dev si elles n'existent pas
    with app.app_context():
        db.create_all()
        
    app.run(host='0.0.0.0', port=5000)
