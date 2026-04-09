import os
import sys

# Ajoute le dossier racine du projet au chemin de recherche Python
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

# Importe l'application Flask
from app import create_app

# Point d'entrée pour Vercel
try:
    db_test = os.environ.get('DATABASE_URL')
    print(f"DIAGNOSTIC: DATABASE_URL is set: {bool(db_test)}")
    if db_test:
        print(f"DIAGNOSTIC: DATABASE_URL protocol: {db_test.split(':')[0] if ':' in db_test else 'INVALID'}")
    
    app = create_app('production')
    print("DIAGNOSTIC: App created successfully")
except Exception as e:
    print(f"DIAGNOSTIC: ERROR DURING BOOTSTRAP: {str(e)}")
    raise e
