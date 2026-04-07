from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from config import config
from app.extensions import db, migrate, login_manager, mail
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
    mail.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    # Enregistrement des Blueprints
    from app.hr_management.routes import bp_hr
    from app.inventory_fefo.routes import bp_inventory
    from app.pos_sales.routes import bp_pos
    from app.auth.routes import bp_auth

    app.register_blueprint(bp_hr, url_prefix='/hr')
    app.register_blueprint(bp_inventory, url_prefix='/inventory')
    app.register_blueprint(bp_pos, url_prefix='/pos')
    app.register_blueprint(bp_auth, url_prefix='/auth')

    @app.route('/test')
    def test_direct():
        return "Test Réussi - Le serveur fonctionne !"

    # Global Dashboard route
    @app.route('/')
    def index():
        if not current_user.is_authenticated:
            return render_template('marketing/landing.html')
            
        if current_user.email == 'syllamohamedmhd99@gmail.com':
            return redirect(url_for('super_admin'))

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
        admin_email = 'syllamohamedmhd99@gmail.com'
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
        if current_user.email != 'syllamohamedmhd99@gmail.com':
            flash("Accès réservé au Super-Administrateur.", "danger")
            return redirect(url_for('index'))
            
        try:
            pharmacies = Pharmacy.query.all()
            
            # ANALYTICS SAAS
            from sqlalchemy import func
            # On s'assure d'importer Sale ici par sécurité
            from app.models import Sale
            
            total_global_revenue = db.session.query(func.sum(Sale.total_amount)).scalar() or 0
            
            # Répartition par pharmacie (Top Performance)
            pharma_stats = []
            for p in pharmacies:
                rev = db.session.query(func.sum(Sale.total_amount)).filter_by(pharmacy_id=p.id).scalar() or 0
                pharma_stats.append({
                    'name': p.name,
                    'revenue': rev
                })
            
            return render_template('superadmin/dashboard.html', 
                                   pharmacies=pharmacies,
                                   total_global_revenue=total_global_revenue,
                                   pharma_stats=pharma_stats,
                                   now=datetime.utcnow())
        except Exception as e:
            flash(f"Erreur d'accès Dashboard : {str(e)}", "danger")
            # Version de secours sans stats si ça échoue
            return render_template('superadmin/dashboard.html', 
                                   pharmacies=Pharmacy.query.all(),
                                   total_global_revenue=0,
                                   pharma_stats=[])

    @app.before_request
    def check_subscription():
        # Ne s'applique qu'au utilisateurs connectés qui ne sont pas Super-Admin
        if current_user.is_authenticated and current_user.email != 'syllamohamedmhd99@gmail.com':
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

    @app.route('/superadmin/toggle_pharmacy/<int:id>', methods=['POST'])
    @login_required
    def toggle_pharmacy(id):
        if current_user.email != 'syllamohamedmhd99@gmail.com':
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
        if current_user.email != 'syllamohamedmhd99@gmail.com':
            return "Unauthorized", 401
            
        pharma = Pharmacy.query.get_or_404(id)
        plan = request.form.get('plan')
        
        # Logique de prix et durée
        days = 0
        amount = 0
        if plan == 'Mensuel': 
            days = 30
            amount = 150000
        elif plan == 'Trimestriel': 
            days = 90
            amount = 250000
        elif plan == 'Semestriel': 
            days = 180
            amount = 500000
        elif plan == 'Annuel': 
            days = 365
            amount = 950000
        
        if days > 0:
            # Enregistrement de la transaction
            from app.models import SubscriptionRecord
            record = SubscriptionRecord(
                pharmacy_id=pharma.id,
                plan_name=plan,
                amount=amount
            )
            db.session.add(record)

            # Mise à jour de la pharmacie
            start_date = pharma.subscription_end_date if pharma.subscription_end_date and pharma.subscription_end_date > datetime.utcnow() else datetime.utcnow()
            pharma.subscription_end_date = start_date + timedelta(days=days)
            pharma.subscription_plan = plan
            pharma.is_active = True
            
            for u in pharma.users:
                if u.role == 'Admin':
                    u.is_active = True
            
            db.session.commit()
            flash(f"Abonnement {plan} activé pour {pharma.name}. Transaction enregistrée.", "success")
        
        return redirect(url_for('super_admin'))

    @app.route('/superadmin/reports')
    @login_required
    def super_admin_reports():
        if current_user.email != 'syllamohamedmhd99@gmail.com':
            return redirect(url_for('index'))
        
        from app.models import SubscriptionRecord
        history = SubscriptionRecord.query.order_by(SubscriptionRecord.timestamp.desc()).all()
        return render_template('superadmin/reports.html', history=history)

    @app.route('/superadmin/export/payments')
    @login_required
    def export_payments():
        if current_user.email != 'syllamohamedmhd99@gmail.com':
            return "Unauthorized", 401
        
        import csv
        from io import StringIO
        from flask import make_response
        from app.models import SubscriptionRecord
        
        history = SubscriptionRecord.query.all()
        
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(['ID', 'Pharmacie', 'Forfait', 'Montant (GNF)', 'Date'])
        
        for record in history:
            pharma_name = Pharmacy.query.get(record.pharmacy_id).name
            cw.writerow([record.id, pharma_name, record.plan_name, record.amount, record.timestamp.strftime('%d/%m/%Y %H:%M')])
        
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=rapport_paiements_saas.csv"
        output.headers["Content-type"] = "text/csv"
        return output

    @app.route('/superadmin/subscriptions')
    @login_required
    def super_admin_subscriptions():
        if current_user.email != 'syllamohamedmhd99@gmail.com':
            return redirect(url_for('index'))
            
        pharmacies = Pharmacy.query.order_by(Pharmacy.id.desc()).all()
        return render_template('superadmin/subscriptions.html', pharmacies=pharmacies, now=datetime.utcnow())

    @app.route('/superadmin/approve_pharmacy/<int:id>', methods=['POST'])
    @login_required
    def approve_pharmacy(id):
        if current_user.email != 'syllamohamedmhd99@gmail.com':
            return "Unauthorized", 401
            
        pharma = Pharmacy.query.get_or_404(id)
        pharma.is_active = True
        
        # Activer tous les utilisateurs de cette pharmacie
        for user in pharma.users:
            user.is_active = True
            
        db.session.commit()
        flash(f"La pharmacie {pharma.name} a été validée avec succès !", "success")
        return redirect(url_for('super_admin_subscriptions'))

    # Auto-initialisation de la base (SaaS)
    with app.app_context():
        db.create_all()
    
    return app
