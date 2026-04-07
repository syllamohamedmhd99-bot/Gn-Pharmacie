from app import create_app
from app.extensions import db
from app.models import User, Pharmacy
from datetime import datetime, timedelta

app = create_app()
with app.app_context():
    # 1. S'assurer que la pharmacie par défaut existe
    default_pharma = Pharmacy.query.filter_by(id=1).first()
    if not default_pharma:
        default_pharma = Pharmacy(
            id=1,
            name="Pharmacie SaaS Master",
            is_active=True,
            subscription_plan='Annuel',
            subscription_end_date=datetime.utcnow() + timedelta(days=365)
        )
        db.session.add(default_pharma)
        db.session.commit()
    
    # 2. Réinitialiser le Super-Admin
    admin = User.query.filter_by(email='admin@pharma.com').first()
    if not admin:
        admin = User(
            email='admin@pharma.com',
            role='Admin',
            pharmacy_id=default_pharma.id,
            first_name='Admin',
            last_name='SaaS',
            can_view_admin=True,
            can_view_pos=True,
            can_view_inventory=True,
            can_view_hr=True
        )
        db.session.add(admin)
    
    admin.is_active = True
    admin.set_password('admin123')
    db.session.commit()
    
    print("--- RÉSULTAT DU SECOURS ---")
    print("Email : admin@pharma.com")
    print("Mot de passe : admin123")
    print("Statut : ACTIF & PRÊT")
    print("---------------------------")
