import os
from app import create_app
from app.extensions import db
from app.models import User

def reactivate():
    app = create_app()
    with app.app_context():
        # Trouver tous les super-admins
        super_admins = User.query.filter_by(is_super_admin=True).all()
        
        if not super_admins:
            print("Aucun compte Super-Admin trouvé en base de données.")
            return

        for admin in super_admins:
            if not admin.is_active:
                print(f"Réactivation de l'utilisateur : {admin.email}")
                admin.is_active = True
            else:
                print(f"L'utilisateur {admin.email} est déjà actif.")
        
        db.session.commit()
        print("\nTerminé. Tous les Super-Admins sont désormais actifs.")

if __name__ == "__main__":
    reactivate()
