from manage import app, seed
from app.extensions import db

if __name__ == "__main__":
    with app.app_context():
        print("--- INITIALISATION PROD PHARMACLOUD ---")
        try:
            # S'assurer que les tables existent
            db.create_all()
            # Lancer le seeding (création/reset du SuperAdmin)
            seed()
            print("--- INITIALISATION RÉUSSIE ---")
        except Exception as e:
            print(f"--- ERREUR INITIALISATION : {str(e)} ---")
