from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from flask_login import login_required, current_user
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
    # FILTRE SAAS: Historique de MA pharmacie
    sales = Sale.query.filter_by(pharmacy_id=current_user.pharmacy_id).order_by(Sale.timestamp.desc()).all()
    return render_template('pos/history.html', sales=sales)

@bp_pos.route('/sale/delete/<int:sale_id>', methods=['POST'])
@login_required
@admin_required
def delete_sale(sale_id):
    # Sécurité: Vérifier l'appartenance
    sale = Sale.query.filter_by(id=sale_id, pharmacy_id=current_user.pharmacy_id).first_or_404()
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
    sale = Sale.query.filter_by(id=sale_id, pharmacy_id=current_user.pharmacy_id).first_or_404()
    payment_method = request.form.get('payment_method')
    if payment_method:
        sale.payment_method = payment_method
        db.session.commit()
    return redirect(url_for('pos.history'))

@bp_pos.route('/invoice/<int:sale_id>')
@login_required
def invoice(sale_id):
    sale = Sale.query.filter_by(id=sale_id, pharmacy_id=current_user.pharmacy_id).first_or_404()
    return render_template('pos/invoice.html', sale=sale)

@bp_pos.route('/api/medicines', methods=['GET'])
@login_required
def get_medicines():
    # FILTRE SAAS: Catalogue de MA pharmacie
    medicines = Medicine.query.filter_by(pharmacy_id=current_user.pharmacy_id).all()
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
    # SÉCURITÉ SAAS: Vérification de l'abonnement
    from datetime import datetime
    if current_user.pharmacy.subscription_end_date and current_user.pharmacy.subscription_end_date < datetime.utcnow():
        return jsonify({"error": "Abonnement expiré. Veuillez contacter le Super-Admin pour renouveler."}), 403

    data = request.json
    if not data or 'items' not in data:
        return jsonify({"error": "Données invalides"}), 400

    try:
        # 1. Création de la vente SaaS
        sale = Sale(
            user_id=current_user.id, 
            total_amount=0.0,
            payment_method=data.get('payment_method', 'Cash'),
            pharmacy_id=current_user.pharmacy_id # SAE
        )
        db.session.add(sale)
        db.session.flush() 

        total_amount = 0.0

        # 2. Itération sur les produits
        for item in data['items']:
            med_id = item['medicine_id']
            qty = item['quantity']
            
            # Vérifier l'appartenance du médicament
            medicine = Medicine.query.filter_by(id=med_id, pharmacy_id=current_user.pharmacy_id).first_or_404()

            # 3. EXÉCUTION DU MOTEUR FEFO
            process_fefo_deduction(
                sale_id=sale.id, 
                medicine_id=medicine.id, 
                required_quantity=qty, 
                unit_price=medicine.default_price
            )
            
            total_amount += (qty * medicine.default_price)

        # 4. ALERTE RÉAPPROVISIONNEMENT SaaS
        total_stock = sum(b.quantity for b in medicine.batches if b.quantity > 0 and b.expiry_date >= date.today())
        
        if total_stock < medicine.min_stock_level:
            from app.models import PurchaseOrder
            existing_order = PurchaseOrder.query.filter_by(
                medicine_id=medicine.id, 
                pharmacy_id=current_user.pharmacy_id,
                status="Auto-Généré"
            ).first()
            
            if not existing_order:
                po = PurchaseOrder(
                    supplier_id=medicine.supplier_id,
                    medicine_id=medicine.id,
                    pharmacy_id=current_user.pharmacy_id,
                    requested_quantity=100,
                    status="Auto-Généré"
                )
                db.session.add(po)

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
