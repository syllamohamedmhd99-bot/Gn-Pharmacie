import os
import sys

# Ajoute le dossier pharma_cloud_erp au chemin de recherche Python
# Cela permet d'importer 'app' depuis le sous-dossier
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app_dir = os.path.join(root_dir, 'pharma_cloud_erp')
sys.path.append(app_dir)

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
