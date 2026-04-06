from datetime import date
from app.extensions import db
from app.models import Batch, SaleItem

class OutOfStockError(Exception):
    """Exception levée lorsque le stock est insuffisant sur tous les lots."""
    pass

class ExpiredMedicineError(Exception):
    """Exception levée lorsque le seul stock restant est périmé."""
    pass

def process_fefo_deduction(sale_id, medicine_id, required_quantity, unit_price):
    """
    Algorithme FEFO (First Expiring, First Out).
    Déduit dynamiquement la quantité requise à travers plusieurs lots
    en donnant la priorité aux lots qui expirent le plus tôt, tout en
    échappant aux lots déjà périmés.
    """
    
    # 1. Requête avec verrouillage Pessimiste : FOR UPDATE
    # Cela empêche d'autres caissiers de prélever simultanément sur ces mêmes lots 
    # avant la fin de la transaction, évitant les stocks négatifs.
    available_batches = Batch.query.with_for_update().filter(
        Batch.medicine_id == medicine_id,
        Batch.quantity > 0
    ).order_by(
        Batch.expiry_date.asc() # Plus c'est proche de périmer, plus ça remonte en haut
    ).all()

    remaining_to_deduct = required_quantity
    sale_items = []

    for batch in available_batches:
        if remaining_to_deduct <= 0:
            break

        # Verification Sécurité : Interdiction absolue de vendre un lot expiré
        if batch.expiry_date < date.today():
             continue # On ignore ce lot et on passe au suivant

        if batch.quantity >= remaining_to_deduct:
             # Ce lot peut couvrir toute la demande (ou le reste de la demande)
             deduction = remaining_to_deduct
        else:
             # Le lot n'a pas assez, on le vide complètement et on continue
             deduction = batch.quantity

        # Mise à jour du lot
        batch.quantity -= deduction
        remaining_to_deduct -= deduction

        # Création de la trace dans la Vente (Ligne de ticket de Caisse lié au Lot précis)
        sale_item = SaleItem(
             sale_id=sale_id,
             batch_id=batch.id,
             quantity=deduction,
             unit_price=unit_price
        )
        db.session.add(sale_item)
        sale_items.append(sale_item)

    # Si on a épuisé tous les lots et qu'il reste de la demande
    if remaining_to_deduct > 0:
         # On fait un rollback en émettant une erreur pour le contrôleur
         db.session.rollback()
         raise OutOfStockError(f"Stock insuffisant. Il manque {remaining_to_deduct} unités de ce médicament.")

    return sale_items
