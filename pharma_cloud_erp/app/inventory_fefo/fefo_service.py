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
    Algorithme FEFO (First Expiring, First Out) SAE.
    """
    from flask_login import current_user
    
    # 1. Requête avec verrouillage Pessimiste ET Filtre SaaS
    available_batches = Batch.query.with_for_update().filter(
        Batch.medicine_id == medicine_id,
        Batch.pharmacy_id == current_user.pharmacy_id, # SAE
        Batch.quantity > 0
    ).order_by(
        Batch.expiry_date.asc()
    ).all()

    remaining_to_deduct = required_quantity
    sale_items = []

    for batch in available_batches:
        if remaining_to_deduct <= 0:
            break

        if batch.expiry_date < date.today():
             continue 

        if batch.quantity >= remaining_to_deduct:
             deduction = remaining_to_deduct
        else:
             deduction = batch.quantity

        batch.quantity -= deduction
        remaining_to_deduct -= deduction

        sale_item = SaleItem(
             sale_id=sale_id,
             pharmacy_id=current_user.pharmacy_id, # SAE
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
