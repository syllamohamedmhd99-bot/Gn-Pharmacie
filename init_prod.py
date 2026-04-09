from manage import app, seed
from app.extensions import db
from sqlalchemy import text

if __name__ == "__main__":
    with app.app_context():
        print("--- INITIALISATION PROD PHARMACLOUD (AVEC RÉPARATION) ---")
        try:
            # 1. Création des nouvelles tables (SystemLog, SupportTicket, etc.)
            db.create_all()
            print("[OK] Tables vérifiées.")

            # 2. Réparation manuelle des colonnes si déjà existantes (Migration Flash)
            try:
                # Ajout de is_super_admin au cas où la table User existait déjà
                db.session.execute(text("ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS is_super_admin BOOLEAN DEFAULT FALSE"))
                db.session.commit()
                print("[OK] Colonne is_super_admin vérifiée/ajoutée.")
            except Exception as e_col:
                db.session.rollback()
                print(f"[INFO] Migration manuelle User: {str(e_col)}")

            # 3. Lancer le seeding (création/reset du SuperAdmin)
            seed()
            print("--- INITIALISATION RÉUSSIE ---")
        except Exception as e:
            db.session.rollback()
            print(f"--- ERREUR INITIALISATION : {str(e)} ---")
