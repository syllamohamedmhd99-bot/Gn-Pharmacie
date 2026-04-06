from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from flask_login import login_required
from app.auth.decorators import admin_required, permission_required
from app.extensions import db
from app.models import Sale, Medicine, SaleItem
from app.inventory_fefo.fefo_service import process_fefo_deduction, OutOfStockError
from datetime import date

bp_pos = Blueprint('pos', __name__)

@bp_pos.route('/terminal')
@login_required
@permission_required('can_view_pos')
def terminal():
    return render_template('pos/terminal.html')

@bp_pos.route('/history')
@login_required
@permission_required('can_view_pos')
def history():
    sales = Sale.query.order_by(Sale.timestamp.desc()).all()
    return render_template('pos/history.html', sales=sales)

@bp_pos.route('/sale/delete/<int:sale_id>', methods=['POST'])
@login_required
@admin_required
def delete_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    # Restore quantities to batches
    for item in sale.items:
        if item.batch:
            item.batch.quantity += item.quantity
        db.session.delete(item)
    db.session.delete(sale)
    db.session.commit()
    return redirect(url_for('pos.history'))

@bp_pos.route('/sale/edit/<int:sale_id>', methods=['POST'])
@login_required
@admin_required
def edit_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    payment_method = request.form.get('payment_method')
    if payment_method:
        sale.payment_method = payment_method
        db.session.commit()
    return redirect(url_for('pos.history'))

@bp_pos.route('/invoice/<int:sale_id>')
@login_required
def invoice(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    return render_template('pos/invoice.html', sale=sale)

@bp_pos.route('/api/medicines', methods=['GET'])
def get_medicines():
    medicines = Medicine.query.all()
    result = []
    for m in medicines:
        # Simplification: we just return catalog info.
        total_qty = sum(b.quantity for b in m.batches if b.quantity > 0 and b.expiry_date >= date.today())
        result.append({
            'id': m.id,
            'name': m.name,
            'price': m.default_price,
            'barcode': m.barcode,
            'available_qty': total_qty
        })
    return jsonify(result)

@bp_pos.route('/checkout', methods=['POST'])
@login_required
def checkout():
    """
    Endpoint de vente au comptoir.
    Attend un payload: { user_id, payment_method, items: [{medicine_id, quantity}] }
    """
    data = request.json
    if not data or 'items' not in data:
        return jsonify({"error": "Données invalides"}), 400

    try:
        # 1. Création de la vente (état brouillon)
        sale = Sale(
            user_id=data.get('user_id', 1), # En prod, viendrait de current_user
            total_amount=0.0,
            payment_method=data.get('payment_method', 'Cash')
        )
        db.session.add(sale)
        db.session.flush() # Assigne un ID à `sale` sans commiter

        total_amount = 0.0

        # 2. Itération sur les produits scannés
        for item in data['items']:
            med_id = item['medicine_id']
            qty = item['quantity']
            
            # Recuperer le prix unitaire du medicament (catalogue)
            medicine = Medicine.query.get(med_id)
            if not medicine:
                db.session.rollback()
                return jsonify({"error": f"Médicament ID {med_id} introuvable"}), 404

            # 3. EXÉCUTION DU MOTEUR FEFO (Le point le plus complexe)
            # Cette fonction va déduire les lots et créer les "SaleItems"
            process_fefo_deduction(
                sale_id=sale.id, 
                medicine_id=medicine.id, 
                required_quantity=qty, 
                unit_price=medicine.default_price
            )
            
            total_amount += (qty * medicine.default_price)

        # 4. ALERTE RÉAPPROVISIONNEMENT (Stock de Sécurité)
        total_stock = sum(b.quantity for b in medicine.batches if b.quantity > 0 and b.expiry_date >= date.today())
        
        if total_stock < medicine.min_stock_level:
            # Vérifier s'il n'y a pas déjà une commande auto-générée en attente
            from app.models import PurchaseOrder
            existing_order = PurchaseOrder.query.filter_by(
                medicine_id=medicine.id, 
                status="Auto-Généré"
            ).first()
            
            if not existing_order:
                po = PurchaseOrder(
                    supplier_id=medicine.supplier_id,
                    medicine_id=medicine.id,
                    requested_quantity=100, # Quantité fixe pour l'exemple
                    status="Auto-Généré"
                )
                db.session.add(po)

        # 5. Finalisation
        sale.total_amount = total_amount
        db.session.commit()
        
        return jsonify({
            "success": True, 
            "message": "Vente validée ! Les stocks critiques ont généré des bons de commande auto.",
            "sale_id": sale.id,
            "total_gnf": total_amount
        }), 201

    except OutOfStockError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erreur critique serveur: " + str(e)}), 500
