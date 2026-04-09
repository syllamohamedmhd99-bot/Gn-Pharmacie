import os
import sys
import traceback

print("--- DIAGNOSTIC DES BOOTSTRAP PharmaCloud ---")

try:
    print("1. Vérification des variables d'environnement...")
    db_url = os.environ.get('DATABASE_URL')
    print(f"   DATABASE_URL présent : {bool(db_url)}")
    if db_url:
        print(f"   Protocole : {db_url.split(':')[0]}")
    
    print("\n2. Tentative d'import de l'application...")
    from app import create_app
    from app.extensions import db
    print("   Import réussi.")

    print("\n3. Création du contexte d'application (Production)...")
    app = create_app('production')
    
    with app.app_context():
        print("   Contexte créé avec succès.")
        
        print("\n4. Test de connexion à la base de données...")
        from sqlalchemy import text
        result = db.session.execute(text("SELECT 1")).scalar()
        print(f"   Connexion à la base : OK (résultat={result})")
        
        print("\n5. Liste des tables détectées...")
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"   Tables : {tables}")
        
    print("\n--- DIAGNOSTIC RÉUSSI : L'application devrait démarrer ---")

except Exception as e:
    print("\n!!! ERREUR DÉTECTÉE LORS DU DIAGNOSTIC !!!")
    print("-" * 40)
    traceback.print_exc()
    print("-" * 40)
    sys.exit(1)
