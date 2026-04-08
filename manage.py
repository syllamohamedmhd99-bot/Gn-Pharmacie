import os
import click
from app import create_app
from app.extensions import db
from app.models import User, Pharmacy, SubscriptionPlan, SubscriptionRecord, Customer, Task
from datetime import datetime, timedelta
from sqlalchemy import text

app = create_app(os.getenv('FLASK_ENV') or 'default')

@app.cli.command("seed")
def seed():
    """Initialise la base de données avec les données par défaut."""
    print("--- DÉMARRAGE DU SEEDING PHARMACLOUD ---")
    try:
        db.create_all()
        print("[1/4] Structure des tables vérifiée.")

        # 1. Plans par défaut
        print("[2/4] Vérification des plans d'abonnement...")
        default_plans = [
            {'name': 'Mensuel', 'price': 150000, 'duration_days': 30, 'description': 'Accès complet 1 mois'},
            {'name': 'Trimestriel', 'price': 250000, 'duration_days': 90, 'description': 'Accès complet 3 mois'},
            {'name': 'Semestriel', 'price': 500000, 'duration_days': 180, 'description': 'Accès complet 6 mois'},
            {'name': 'Annuel', 'price': 950000, 'duration_days': 365, 'description': 'Accès complet 1 an'}
        ]
        for p_data in default_plans:
            existing_plan = SubscriptionPlan.query.filter_by(name=p_data['name']).first()
            if not existing_plan:
                new_plan = SubscriptionPlan(**p_data)
                db.session.add(new_plan)
        db.session.commit()

        # 2. Création de la pharmacie par défaut si aucune n'existe
        pharma = Pharmacy.query.first()
        if not pharma:
            pharma = Pharmacy(name="Ma Pharmacie Démo", is_active=True, subscription_plan="Annuel", 
                            subscription_end_date=datetime.utcnow() + timedelta(days=365))
            db.session.add(pharma)
            db.session.commit()
            print("[3/4] Pharmacie de démonstration créée.")
        else:
            print(f"[3/4] Pharmacie existante : {pharma.name}")

        # 3. Création du Super-Admin par défaut (Mohamed)
        admin_email = 'syllamohamedmhd99@gmail.com'
        admin = User.query.filter_by(email=admin_email).first()
        if not admin:
            admin = User(
                email=admin_email,
                role='Admin',
                pharmacy_id=pharma.id,
                is_active=True,
                is_super_admin=True,
                first_name="Mohamed",
                last_name="Sylla"
            )
            print(f"[4/4] Création du compte Super-Admin ({admin_email})...")
        else:
            admin.is_super_admin = True
            admin.is_active = True
            print(f"[4/4] Mise à jour et réinitialisation du compte Super-Admin ({admin_email})...")
        
        # On force le mot de passe dans tous les cas pour garantir l'accès
        admin.set_password("admin123")
        if not admin.id:
            db.session.add(admin)
        
        db.session.commit()

        print("--- SEEDING TERMINÉ AVEC SUCCÈS ---")
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        print(f"!!! ERREUR LORS DU SEEDING : {str(e)} !!!")

if __name__ == '__main__':
    # Ceci n'est pas utilisé par Flask CLI mais utile pour exécution directe
    pass
