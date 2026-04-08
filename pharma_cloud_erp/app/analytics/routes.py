from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Sale, SaleItem, Medicine, User
from sqlalchemy import func
from datetime import datetime, timedelta

bp_analytics = Blueprint('analytics', __name__)

@bp_analytics.route('/reports')
@login_required
def reports():
    # Saas Filter
    pharmacy_id = current_user.pharmacy_id
    
    # Statistiques de ventes (30 derniers jours)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    sales_count = Sale.query.filter(Sale.pharmacy_id == pharmacy_id, Sale.timestamp >= thirty_days_ago).count()
    revenue = db.session.query(func.sum(Sale.total_amount)).filter(Sale.pharmacy_id == pharmacy_id, Sale.timestamp >= thirty_days_ago).scalar() or 0
    
    # Top Médicaments
    top_medicines = db.session.query(Medicine.name, func.sum(SaleItem.quantity).label('total'))\
        .join(SaleItem, Medicine.id == SaleItem.medicine_id)\
        .join(Sale, Sale.id == SaleItem.sale_id)\
        .filter(Sale.pharmacy_id == pharmacy_id)\
        .group_by(Medicine.name)\
        .order_by(func.sum(SaleItem.quantity).desc())\
        .limit(5).all()
        
    return render_template('analytics/reports.html', 
                           sales_count=sales_count, 
                           revenue=revenue,
                           top_medicines=top_medicines)
