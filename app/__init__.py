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

    @app.route('/superadmin/toggle_pharmacy/<int:id>', methods=['POST'])
    @login_required
    def toggle_pharmacy(id):
        if current_user.email != 'admin@pharma.com':
            return "Unauthorized", 401
            
        pharma = Pharmacy.query.get_or_404(id)
        pharma.is_active = not pharma.is_active
        
        # Activer/Désactiver tous les utilisateurs de cette pharmacie également
        for user in pharma.users:
            user.is_active = pharma.is_active
            
        db.session.commit()
        status = "activée" if pharma.is_active else "désactivée"
        flash(f"La pharmacie {pharma.name} a été {status} avec succès.", "success")
        return redirect(url_for('super_admin'))

    @app.route('/superadmin/update_subscription/<int:id>', methods=['POST'])
    @login_required
    def update_subscription(id):
        if current_user.email != 'admin@pharma.com':
            return "Unauthorized", 401
            
        pharma = Pharmacy.query.get_or_404(id)
        plan = request.form.get('plan')
        
        # Logique de durée
        days = 0
        if plan == 'Mensuel': days = 30
        elif plan == 'Trimestriel': days = 90
        elif plan == 'Semestriel': days = 180
        elif plan == 'Annuel': days = 365
        
        if days > 0:
            # Si déjà actif, on ajoute à la date de fin. Sinon on part d'aujourd'hui.
            start_date = pharma.subscription_end_date if pharma.subscription_end_date and pharma.subscription_end_date > datetime.utcnow() else datetime.utcnow()
            pharma.subscription_end_date = start_date + timedelta(days=days)
            pharma.subscription_plan = plan
            pharma.is_active = True # Activer auto au paiement
            
            # Activer les admins
            for u in pharma.users:
                if u.role == 'Admin':
                    u.is_active = True
            
            db.session.commit()
            flash(f"Abonnement {plan} activé pour {pharma.name} jusqu'au {pharma.subscription_end_date.strftime('%d/%m/%Y')}", "success")
        
        return redirect(url_for('super_admin'))

    return app
