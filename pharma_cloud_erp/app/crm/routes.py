from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Customer, Sale
from datetime import datetime

bp_crm = Blueprint('crm', __name__)

@bp_crm.route('/')
@login_required
def index():
    # Saas Filter
    customers = Customer.query.filter_by(pharmacy_id=current_user.pharmacy_id).order_by(Customer.name.asc()).all()
    return render_template('crm/index.html', customers=customers)

@bp_crm.route('/add', methods=['POST'])
@login_required
def add_customer():
    name = request.form.get('name')
    phone = request.form.get('phone')
    email = request.form.get('email')
    address = request.form.get('address')

    if not name:
        flash("Le nom du client est obligatoire.", "danger")
        return redirect(url_for('crm.index'))

    new_customer = Customer(
        name=name,
        phone=phone,
        email=email,
        address=address,
        pharmacy_id=current_user.pharmacy_id
    )
    db.session.add(new_customer)
    db.session.commit()
    flash(f"Client {name} ajouté avec succès.", "success")
    return redirect(url_for('crm.index'))

@bp_crm.route('/view/<int:id>')
@login_required
def view_customer(id):
    customer = Customer.query.filter_by(id=id, pharmacy_id=current_user.pharmacy_id).first_or_404()
    # Get last sales
    sales = Sale.query.filter_by(customer_id=id).order_by(Sale.timestamp.desc()).limit(10).all()
    return render_template('crm/view.html', customer=customer, sales=sales)

@bp_crm.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_customer(id):
    customer = Customer.query.filter_by(id=id, pharmacy_id=current_user.pharmacy_id).first_or_404()
    if customer.sales:
        flash("Impossible de supprimer un client ayant un historique d'achats.", "warning")
    else:
        db.session.delete(customer)
        db.session.commit()
        flash(f"Client {customer.name} supprimé avec succès.", "success")
    return redirect(url_for('crm.index'))
