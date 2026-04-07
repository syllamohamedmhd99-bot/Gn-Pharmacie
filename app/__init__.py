from flask import Flask, render_template, redirect, url_for
from flask_login import login_required
from config import config
from app.extensions import db, migrate, login_manager
from app.models import User, Medicine, Batch, Sale, SaleItem, Pharmacy
from flask_login import current_user
from datetime import datetime, timedelta

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialiser les extensions
    db.init_app(app)
    migrate.init_app(app, db)
    

    login_manager.init_app(app)

    # Enregistrement des Blueprints
    from app.hr_management.routes import bp_hr
    from app.inventory_fefo.routes import bp_inventory
    from app.pos_sales.routes import bp_pos
    from app.auth.routes import bp_auth

    app.register_blueprint(bp_hr, url_prefix='/hr')
    app.register_blueprint(bp_inventory, url_prefix='/inventory')
    app.register_blueprint(bp_pos, url_prefix='/pos')
    app.register_blueprint(bp_auth, url_prefix='/auth')

    # Global Dashboard route
    @app.route('/')
    @login_required
    def index():
        # FILTRE SAAS: Statistiques de MA pharmacie
        total_medicines = Medicine.query.filter_by(pharmacy_id=current_user.pharmacy_id).count()
        total_users = User.query.filter_by(pharmacy_id=current_user.pharmacy_id).count()
        total_revenue = db.session.query(db.func.sum(Sale.total_amount))\
            .filter(Sale.pharmacy_id == current_user.pharmacy_id).scalar() or 0
        
        # Alert Logic SaaS
        today = datetime.utcnow()
        expired_count = Batch.query.filter(
            Batch.expiry_date < today, 
            Batch.quantity > 0,
            Batch.pharmacy_id == current_user.pharmacy_id
        ).count()
        
        low_stock = [m for m in Medicine.query.filter_by(pharmacy_id=current_user.pharmacy_id).all() 
                    if m.total_stock <= m.min_stock_level]
                
        return render_template('index.html', 
                               total_medicines=total_medicines,
                               total_users=total_users,
                               total_revenue=total_revenue,
                               expired_count=expired_count,
                               low_stock=low_stock)

    # Route SaaS: Initialisation / Migration
    @app.route('/seed')
    def seed():
        db.create_all()
        
        # 1. Création de la Pharmacie par défaut si nécessaire
        default_pharma = Pharmacy.query.filter_by(name='Pharmacie de Démonstration').first()
        if not default_pharma:
            default_pharma = Pharmacy(
                name='Pharmacie de Démonstration',
                address='Conakry, Guinée',
                license_number='DEMO-001'
            )
            db.session.add(default_pharma)
            db.session.flush()
            
        # 2. Gestion de l'Admin SaaS
        admin_email = 'admin@pharma.com'
        admin = User.query.filter_by(email=admin_email).first()
        
        if not admin:
            admin = User(
                email=admin_email, 
                role='Admin', 
                pharmacy_id=default_pharma.id,
                is_active=True, 
                first_name='Admin', 
                last_name='SaaS',
                can_view_pos=True, 
                can_view_inventory=True, 
                can_view_hr=True, 
                can_view_admin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
        else:
            # Migration: Rattaché à la pharmacie démo si orphelin
            if not admin.pharmacy_id:
                admin.pharmacy_id = default_pharma.id
        
        # 3. Migration des Médicaments orphelins
        orphaned_meds = Medicine.query.filter_by(pharmacy_id=None).all()
        for m in orphaned_meds:
            m.pharmacy_id = default_pharma.id
            
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return f"Erreur Migration SaaS : {str(e)}"

        return redirect(url_for('index'))

    # Route Super-Admin (Gestion Globale du SaaS)
    @app.route('/superadmin')
    @login_required
    def super_admin():
        # Sécurité : Seul l'admin maître peut voir tout
        if current_user.email != 'admin@pharma.com':
            flash("Accès réservé au Super-Administrateur.", "danger")
            return redirect(url_for('index'))
            
        pharmacies = Pharmacy.query.all()
        return render_template('superadmin/dashboard.html', pharmacies=pharmacies)

    return app
