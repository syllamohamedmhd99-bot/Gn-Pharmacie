import os
from app import create_app
from app.extensions import db
from app.models import Pharmacy, User, SubscriptionRecord, SystemLog

app = create_app()
with app.app_context():
    print("--- DESTRUCTION DES DONNÉES DÉMO ---")
    
    # Recherche des pharmacies démo
    demo_pharmacies = Pharmacy.query.filter(Pharmacy.name.ilike('%Démo%')).all()
    
    if not demo_pharmacies:
        print("Aucune pharmacie contenant 'Démo' n'a été trouvée.")
    else:
        for p in demo_pharmacies:
            print(f"Suppression de la pharmacie : {p.name} (ID: {p.id})")
            
            # Note: cascades (cascade='all, delete-orphan') in models.py should handle 
            # Users, Medicines, Sales, Suppliers, Payments (SubscriptionRecord), 
            # Customers, Tasks, Leaves.
            
            db.session.delete(p)
            
        try:
            db.session.commit()
            print("\nSUCCÈS : Toutes les données démo ont été supprimées définitivement.")
        except Exception as e:
            db.session.rollback()
            print(f"\nERREUR lors de la suppression : {str(e)}")
    
    # Optionnel : Nettoyage des logs système liés aux démos
    # (Si les cascades ne l'ont pas déjà fait via pharmacy_id)
    SystemLog.query.filter(SystemLog.details.ilike('%Démo%')).delete(synchronize_session=False)
    db.session.commit()
    print("Logs système nettoyés.")
