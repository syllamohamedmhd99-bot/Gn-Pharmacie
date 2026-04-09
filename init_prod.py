from manage import app, seed
from app.extensions import db
from sqlalchemy import text
from flask_migrate import stamp

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
                db.session.execute(text("ALTER TABLE \"users\" ADD COLUMN IF NOT EXISTS is_super_admin BOOLEAN DEFAULT FALSE"))
                db.session.commit()
                print("[OK] Colonne is_super_admin vérifiée/ajoutée.")
            except Exception as e_col:
                db.session.rollback()
                print(f"[INFO] Migration manuelle User: {str(e_col)}")

            # 3. Lancer le seeding (création/reset du SuperAdmin)
            seed()
            
            # 4. Synchroniser l'historique des migrations (Marquer comme à jour)
            try:
                stamp(revision='head')
                print("[OK] Historique des migrations synchronisé (Stamp: head).")
            except Exception as e_stamp:
                 print(f"[INFO] Stamp des migrations: {str(e_stamp)}")

            print("--- INITIALISATION RÉUSSIE ---")
        except Exception as e:
            db.session.rollback()
            print(f"--- ERREUR INITIALISATION : {str(e)} ---")
