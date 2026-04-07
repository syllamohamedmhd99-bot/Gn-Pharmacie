from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.auth.decorators import permission_required
from app.extensions import db
from app.models import Medicine, Batch, Supplier, PurchaseOrder
from datetime import datetime

bp_inventory = Blueprint('inventory', __name__)

@bp_inventory.route('/dashboard')
@login_required
@permission_required('can_view_inventory')
def dashboard():
    medicines = Medicine.query.all()
    batches = Batch.query.order_by(Batch.expiry_date.asc()).all()
    
    total_stock_value = sum(b.quantity * b.medicine.default_price for b in batches)
    
    from datetime import date, timedelta
    today_date = date.today()
    near_date = today_date + timedelta(days=30)
    
    suppliers_list = Supplier.query.all()
    
    return render_template('inventory/dashboard.html', 
                           medicines=medicines, 
                           batches=batches, 
                           total_value=total_stock_value,
                           today_date=today_date,
                           near_date=near_date,
                           suppliers_list=suppliers_list)


@bp_inventory.route('/medicine/add', methods=['POST'])
def add_medicine():
    name = request.form.get('name')
    price = request.form.get('price')
    min_stock = request.form.get('min_stock', 10)
    barcode = request.form.get('barcode', None)
    supplier_id = request.form.get('supplier_id')
    
    if name and price:
        med = Medicine(name=name, default_price=float(price), 
                       min_stock_level=int(min_stock), barcode=barcode)
        if supplier_id:
            med.supplier_id = int(supplier_id)
        db.session.add(med)
        db.session.commit()
        flash("Médicament ajouté avec succès", "success")
    return redirect(url_for('inventory.dashboard'))

@bp_inventory.route('/medicine/delete/<int:id>', methods=['POST'])
def delete_medicine(id):
    med = Medicine.query.get_or_404(id)
    # Delete associated batches first
    Batch.query.filter_by(medicine_id=id).delete()
    db.session.delete(med)
    db.session.commit()
    flash("Médicament supprimé", "success")
    return redirect(url_for('inventory.dashboard'))

@bp_inventory.route('/batch/add', methods=['POST'])
def add_batch():
    medicine_id = request.form.get('medicine_id')
    batch_number = request.form.get('batch_number')
    quantity = request.form.get('quantity')
    expiry_date_str = request.form.get('expiry_date')
    
    if medicine_id and batch_number and quantity and expiry_date_str:
        expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
        batch = Batch(medicine_id=int(medicine_id), 
                      batch_number=batch_number, 
                      quantity=int(quantity), 
                      expiry_date=expiry_date)
        db.session.add(batch)
        db.session.commit()
        flash("Lot ajouté avec succès", "success")
    return redirect(url_for('inventory.dashboard'))

@bp_inventory.route('/batch/delete/<int:id>', methods=['POST'])
def delete_batch(id):
    batch = Batch.query.get_or_404(id)
    db.session.delete(batch)
    db.session.commit()
    flash("Lot supprimé", "success")
    return redirect(url_for('inventory.dashboard'))

@bp_inventory.route('/suppliers')
@login_required
def suppliers():
    suppliers = Supplier.query.all()
    orders = PurchaseOrder.query.order_by(PurchaseOrder.id.desc()).all()
    medicines = Medicine.query.all()
    return render_template('inventory/suppliers.html', suppliers=suppliers, orders=orders, medicines=medicines)

@bp_inventory.route('/supplier/add', methods=['POST'])
@login_required
def add_supplier():
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    address = request.form.get('address')
    contact_person = request.form.get('contact_person')
    description = request.form.get('description')
    
    if name and email:
        sup = Supplier(name=name, email=email, phone=phone, 
                       address=address, contact_person=contact_person, 
                       description=description)
        db.session.add(sup)
        db.session.commit()
        flash(f"Fournisseur {name} ajouté avec succès", "success")
    return redirect(url_for('inventory.suppliers'))

@bp_inventory.route('/supplier/delete/<int:id>', methods=['POST'])
@login_required
def delete_supplier(id):
    sup = Supplier.query.get_or_404(id)
    # Détacher les médicaments
    Medicine.query.filter_by(supplier_id=id).update({Medicine.supplier_id: None})
    db.session.delete(sup)
    db.session.commit()
    flash(f"Fournisseur {sup.name} supprimé", "warning")
    return redirect(url_for('inventory.suppliers'))

@bp_inventory.route('/order/update_status/<int:id>', methods=['POST'])
@login_required
def update_order_status(id):
    order = PurchaseOrder.query.get_or_404(id)
    new_status = request.form.get('status')
    if new_status in ['Sent', 'Received', 'Cancelled']:
        order.status = new_status
        db.session.commit()
        flash(f"Statut de la commande #{id} mis à jour : {new_status}", "info")
    return redirect(url_for('inventory.suppliers'))
