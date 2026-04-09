from app import create_app
from app.extensions import db
from app.models import Pharmacy, SubscriptionRecord

app = create_app()
with app.app_context():
    print("--- Pharmacies ---")
    pharmas = Pharmacy.query.all()
    for p in pharmas:
        print(f"ID: {p.id}, Name: {p.name}")
    
    print("\n--- Subscription History ---")
    history = SubscriptionRecord.query.all()
    for h in history:
        pharma_name = "DELETED"
        if h.pharmacy:
            pharma_name = h.pharmacy.name
        print(f"ID: {h.id}, Pharma_id: {h.pharmacy_id}, Name: {pharma_name}, Plan: {h.plan_name}")
