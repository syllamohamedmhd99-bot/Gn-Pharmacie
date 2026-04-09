import os
import sys
import traceback

print("--- DIAGNOSTIC DES BOOTSTRAP PharmaCloud ---")

try:
    print("1. Vérification des variables d'environnement...")
    db_url_int = os.environ.get('DATABASE_URL')
    db_url_pub = os.environ.get('DATABASE_PUBLIC_URL')
    print(f"   DATABASE_URL (Interne) présent : {bool(db_url_int)}")
    print(f"   DATABASE_PUBLIC_URL (Publique) présent : {bool(db_url_pub)}")
    
    active_url = db_url_pub or db_url_int
    if active_url:
        print(f"   URL active détectée : {active_url.split('@')[-1]}") # On cache les accès pour securité
    
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
