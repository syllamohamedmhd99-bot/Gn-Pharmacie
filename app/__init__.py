from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from sqlalchemy import text
from config import config
from app.extensions import db, migrate, login_manager, mail, sess
from app.models import User, Medicine, Batch, Sale, SaleItem, Pharmacy, SubscriptionPlan
from flask_login import current_user
from datetime import datetime, timedelta

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialiser les extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Configuration spécifique pour Flask-Session avec SQLAlchemy
    app.config['SESSION_SQLALCHEMY'] = db
    
    @app.context_processor
    def inject_global_vars():
        from app.models import Pharmacy
        now = datetime.utcnow()
        pending_count = 0
        if current_user.is_authenticated and current_user.is_super_admin:
            try:
                pending_count = Pharmacy.query.filter_by(is_active=False).count()
            except:
                pass
        return {'pending_count': pending_count, 'now': now}

    login_manager.init_app(app)
    mail.init_app(app)
    sess.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    # Enregistrement des Blueprints
    from app.hr_management.routes import bp_hr
    from app.inventory_fefo.routes import bp_inventory
    from app.pos_sales.routes import bp_pos
    from app.auth.routes import bp_auth
    from app.crm.routes import bp_crm
    from app.productivity.routes import bp_productivity
    from app.analytics.routes import bp_analytics
    from app.superadmin import bp_superadmin

    app.register_blueprint(bp_hr, url_prefix='/hr')
    app.register_blueprint(bp_inventory, url_prefix='/inventory')
    app.register_blueprint(bp_pos, url_prefix='/pos')
    app.register_blueprint(bp_auth, url_prefix='/auth')
    app.register_blueprint(bp_crm, url_prefix='/crm')
    app.register_blueprint(bp_productivity, url_prefix='/productivity')
    app.register_blueprint(bp_analytics, url_prefix='/analytics')
    app.register_blueprint(bp_superadmin, url_prefix='/superadmin')

    @app.route('/test')
    def test_direct():
        return "Test Réussi - Le serveur fonctionne !"

    # Global Dashboard route
    @app.route('/')
    def index():
        if not current_user.is_authenticated:
            return render_template('marketing/landing.html')
            
        if current_user.is_super_admin:
            return redirect(url_for('superadmin.dashboard'))

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

    @app.before_request
    def check_subscription():
        # Ne s'applique qu'aux utilisateurs connectés qui ne sont pas Super-Admin
        if current_user.is_authenticated and not current_user.is_super_admin:
            # Ignorer pour les routes essentielles (logout, static, index, settings)
            if request.endpoint in ['auth.logout', 'static', 'index', 'inventory.settings']:
                return

            pharma = current_user.pharmacy
            if not pharma.is_active:
                msg = "Votre compte pharmacie est inactif. Veuillez contacter le support."
                if request.is_json or request.path.startswith('/api') or request.path.startswith('/pos/checkout'):
                    return jsonify({"error": msg}), 403
                flash(msg, "warning")
                return redirect(url_for('index'))
                
            from datetime import datetime
            if pharma.subscription_end_date and pharma.subscription_end_date < datetime.utcnow():
                # On laisse l'accès aux paramètres pour qu'ils voient l'expiration
                if request.endpoint != 'inventory.settings':
                    msg = "Votre abonnement a expiré."
                    if request.is_json or request.path.startswith('/api') or request.path.startswith('/pos/checkout'):
                        return jsonify({"error": msg}), 403
                    flash(msg, "danger")
                    return redirect(url_for('inventory.settings'))

    # L'initialisation de la base sera gérée par la commande de démarrage
    return app


    # L'initialisation de la base sera gérée par la commande de démarrage
    return app
