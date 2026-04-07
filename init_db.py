import os
from app import create_app
from app.extensions import db
from app.models import User
from werkzeug.security import generate_password_hash

def init_production_db():
    print("--- INITIALISATION BASE DE DONNÉES CLOUD ---")
    app = create_app('production')
    with app.app_context():
        # Création des tables si manquantes (PostgreSQL)
        db.create_all()
        print("Tables vérifiées/créées.")

        # Vérifier l'admin
        admin_email = 'syllamohamedmhd99@gmail.com'
        admin = User.query.filter_by(email=admin_email).first()
        if not admin:
            print(f"Création de l'admin par défaut: {admin_email}")
            admin = User(
                email=admin_email,
                password_hash=generate_password_hash('Dainahdj5@'),
                first_name='Super',
                last_name='Admin',
                role='Admin',
                is_active=True
            )
            db.session.add(admin)
            db.session.commit()
            print("Compte Admin prêt (admin123).")
        else:
            # S'assurer qu'il est actif et Admin
            admin.is_active = True
            admin.role = 'Admin'
            db.session.commit()
            print("Compte Admin déjà présent et activé.")

if __name__ == "__main__":
    init_production_db()
