from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from sqlalchemy import text
from config import config
from app.extensions import db, migrate, login_manager, mail
from app.models import User, Medicine, Batch, Sale, SaleItem, Pharmacy, SubscriptionPlan
from flask_login import current_user
from datetime import datetime, timedelta

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialiser les extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    @app.context_processor
    def inject_now():
        from datetime import datetime
        return {'now': datetime.utcnow()}

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
            
        if current_user.is_super_admin:
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
        diagnostic_log = []
        try:
            # 0. Test de connexion
            diagnostic_log.append("Test de connexion...")
            db.session.execute(text("SELECT 1"))
            diagnostic_log.append("Connexion OK.")

            # 1. Création des tables
            diagnostic_log.append("Création des tables manquantes...")
            db.create_all()
            diagnostic_log.append("Tables OK.")

            # 2. Migration SQL Manuelle
            diagnostic_log.append("Migration is_super_admin...")
            db.session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_super_admin BOOLEAN DEFAULT FALSE;"))
            db.session.commit()
            diagnostic_log.append("Migration OK.")
            
            # 3. Initialisation des Plans de Tarification si vides
            if SubscriptionPlan.query.count() == 0:
                diagnostic_log.append("Initialisation des plans...")
                plans = [
                    SubscriptionPlan(name='Mensuel', price=150000, duration_days=30, description='Accès complet pour 1 mois'),
                    SubscriptionPlan(name='Trimestriel', price=250000, duration_days=90, description='Accès complet pour 3 mois (Économique)'),
                    SubscriptionPlan(name='Semestriel', price=500000, duration_days=180, description='Accès complet pour 6 mois'),
                    SubscriptionPlan(name='Annuel', price=950000, duration_days=365, description='Le meilleur choix (12 mois)')
                ]
                for p in plans:
                    db.session.add(p)
                db.session.commit()
                diagnostic_log.append("Plans créés.")

            # 4. Création de la Pharmacie par défaut
            default_pharma = Pharmacy.query.filter_by(name='Pharmacie de Démonstration').first()
            if not default_pharma:
                default_pharma = Pharmacy(
                    name='Pharmacie de Démonstration', 
                    address='Conakry, Guinée', 
                    license_number='DEMO-001',
                    is_active=True # Force l'activation
                )
                db.session.add(default_pharma)
                db.session.flush()
            else:
                default_pharma.is_active = True # Sécurité activation

            # 5. Gestion de l'Admin SaaS
            admin_email = 'syllamohamedmhd99@gmail.com'
            admin = User.query.filter_by(email=admin_email).first()
            if not admin:
                admin = User(
                    email=admin_email, 
                    role='Admin', 
                    pharmacy_id=default_pharma.id, 
                    is_active=True, 
                    is_super_admin=True,
                    can_view_pos=True,
                    can_view_inventory=True,
                    can_view_hr=True,
                    can_view_admin=True
                )
            else:
                admin.is_super_admin = True
                admin.is_active = True # Force activation
                if not admin.pharmacy_id: admin.pharmacy_id = default_pharma.id
            
            admin.set_password('admin123') # Reset temporaire pour débloquer
            db.session.add(admin)
            
            db.session.commit()
            diagnostic_log.append("Admin (ID: {} / Active: {}) OK.".format(admin.id, admin.is_active))
            return f"<h1>Succès de l'Activation !</h1><p>{' <br> '.join(diagnostic_log)}</p><a href='/'>Aller à l'accueil pour se connecter (Mot de passe: admin123)</a>"

        except Exception as e:
            db.session.rollback()
            import traceback
            error_details = traceback.format_exc()
            return f"<h1>Erreur Critique de Initialisation</h1><pre>{str(e)}</pre><h3>Détails :</h3><pre>{error_details}</pre>"

    # Route Super-Admin (Gestion Globale du SaaS)
    @app.route('/superadmin')
    @login_required
    def super_admin():
        # Sécurité : Flag en base de données privilégié
        if not current_user.is_super_admin:
            flash("Accès réservé au Super-Administrateur.", "danger")
            return redirect(url_for('index'))
            
        try:
            pharmacies = Pharmacy.query.all()
            
            # ANALYTICS SAAS
            from sqlalchemy import func
            # On s'assure d'importer Sale ici par sécurité
            from app.models import Sale
            
            total_global_revenue = db.session.query(func.sum(Sale.total_amount)).scalar() or 0
            
            # Optimisation: Répartition par pharmacie (Top Performance)
            pharma_stats = []
            revenue_by_pharma = db.session.query(
                Sale.pharmacy_id, 
                func.sum(Sale.total_amount).label('total')
            ).group_by(Sale.pharmacy_id).all()
            
            revenue_map = {r.pharmacy_id: r.total for r in revenue_by_pharma}
            
            for p in pharmacies:
                pharma_stats.append({
                    'id': p.id,
                    'name': p.name,
                    'is_active': p.is_active,
                    'revenue': revenue_map.get(p.id, 0)
                })
            
            return render_template('superadmin/dashboard.html', 
                                   pharmacies=pharmacies,
                                   total_global_revenue=total_global_revenue,
                                   pharma_stats=pharma_stats,
                                   plans=SubscriptionPlan.query.filter_by(is_active=True).all(),
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
        if not current_user.is_super_admin:
            return "Unauthorized", 401
            
        pharma = Pharmacy.query.get_or_404(id)
        plan_id = request.form.get('plan_id')
        plan = SubscriptionPlan.query.get(plan_id)
        
        if plan:
            # Enregistrement de la transaction
            from app.models import SubscriptionRecord
            record = SubscriptionRecord(
                pharmacy_id=pharma.id,
                plan_name=plan.name,
                amount=plan.price
            )
            db.session.add(record)

            # Mise à jour de la pharmacie
            start_date = pharma.subscription_end_date if pharma.subscription_end_date and pharma.subscription_end_date > datetime.utcnow() else datetime.utcnow()
            pharma.subscription_end_date = start_date + timedelta(days=plan.duration_days)
            pharma.subscription_plan = plan.name
            pharma.is_active = True
            
            for u in pharma.users:
                if u.role == 'Admin':
                    u.is_active = True
            
            db.session.commit()
            flash(f"Abonnement {plan.name} activé pour {pharma.name}.", "success")
        
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
        if not current_user.is_super_admin:
            return redirect(url_for('index'))
            
        pharmacies = Pharmacy.query.order_by(Pharmacy.id.desc()).all()
        plans = SubscriptionPlan.query.filter_by(is_active=True).all()
        return render_template('superadmin/subscriptions.html', pharmacies=pharmacies, plans=plans, now=datetime.utcnow())

    @app.route('/superadmin/plans')
    @login_required
    def super_admin_plans():
        if not current_user.is_super_admin:
            return redirect(url_for('index'))
        plans = SubscriptionPlan.query.all()
        return render_template('superadmin/plans.html', plans=plans)

    @app.route('/superadmin/plans/add', methods=['POST'])
    @login_required
    def add_plan():
        if not current_user.is_super_admin: return "Unauthorized", 401
        
        new_plan = SubscriptionPlan(
            name=request.form.get('name'),
            price=float(request.form.get('price')),
            duration_days=int(request.form.get('duration')),
            description=request.form.get('description')
        )
        db.session.add(new_plan)
        db.session.commit()
        flash("Nouveau forfait ajouté avec succès.", "success")
        return redirect(url_for('super_admin_plans'))

    @app.route('/superadmin/plans/delete/<int:id>')
    @login_required
    def delete_plan(id):
        if not current_user.is_super_admin: return "Unauthorized", 401
        plan = SubscriptionPlan.query.get_or_404(id)
        db.session.delete(plan)
        db.session.commit()
        flash("Forfait supprimé.", "warning")
        return redirect(url_for('super_admin_plans'))

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

    # L'initialisation de la base sera gérée par la commande de démarrage
    return app
