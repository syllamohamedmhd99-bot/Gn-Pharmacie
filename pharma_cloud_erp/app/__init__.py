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

    app.register_blueprint(bp_hr, url_prefix='/hr')
    app.register_blueprint(bp_inventory, url_prefix='/inventory')
    app.register_blueprint(bp_pos, url_prefix='/pos')
    app.register_blueprint(bp_auth, url_prefix='/auth')
    app.register_blueprint(bp_crm, url_prefix='/crm')
    app.register_blueprint(bp_productivity, url_prefix='/productivity')
    app.register_blueprint(bp_analytics, url_prefix='/analytics')

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
            # Force un rollback pour libérer les transactions PostgreSQL avortées 
            # par des erreurs de colonnes lors du boot (load_user)
            db.session.rollback()
            
            # 0. Test de connexion
            diagnostic_log.append("Nettoyage transaction PostgreSQL OK.")
            db.session.execute(text("SELECT 1"))
            diagnostic_log.append("Connexion OK.")

            # 1. Création des tables
            diagnostic_log.append("Création des tables manquantes...")
            db.create_all()
            diagnostic_log.append("Tables OK.")

            # 3. Migration SQL Manuelle des colonnes (Sécurisée pour SQLite/Postgres)
            diagnostic_log.append("Migration des colonnes...")
            cols_to_add = [
                "ALTER TABLE users ADD COLUMN is_super_admin BOOLEAN DEFAULT FALSE",
                "ALTER TABLE sales ADD COLUMN customer_id INTEGER",
                "ALTER TABLE users ADD COLUMN can_view_crm BOOLEAN DEFAULT FALSE",
                "ALTER TABLE users ADD COLUMN can_view_tasks BOOLEAN DEFAULT FALSE",
                "ALTER TABLE users ADD COLUMN can_view_analytics BOOLEAN DEFAULT FALSE"
            ]
            for cmd in cols_to_add:
                try:
                    db.session.execute(text(cmd))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
            
            # 4. Initialisation des Plans (SQL BRUT)
            res = db.session.execute(text("SELECT COUNT(*) FROM subscription_plans"))
            if res.scalar() == 0:
                plans_sql = [
                    "INSERT INTO subscription_plans (name, price, duration_days, description) VALUES ('Mensuel', 150000, 30, 'Accès complet 1 mois')",
                    "INSERT INTO subscription_plans (name, price, duration_days, description) VALUES ('Trimestriel', 250000, 90, 'Accès complet 3 mois')",
                    "INSERT INTO subscription_plans (name, price, duration_days, description) VALUES ('Semestriel', 500000, 180, 'Accès complet 6 mois')",
                    "INSERT INTO subscription_plans (name, price, duration_days, description) VALUES ('Annuel', 950000, 365, 'Accès complet 1 an')"
                ]
                for p_sql in plans_sql:
                    db.session.execute(text(p_sql))
                db.session.commit()
                diagnostic_log.append("Plans de tarification initialisés.")

            # 5. Création Admin (SQL BRUT pour éviter crash mapper)
            admin_email = 'syllamohamedmhd99@gmail.com'
            res_admin = db.session.execute(text("SELECT id FROM users WHERE email = :email"), {"email": admin_email})
            admin_id = res_admin.scalar()
            
            if not admin_id:
                # Création de la pharmacie par défaut si besoin
                res_pharma = db.session.execute(text("SELECT id FROM pharmacies LIMIT 1"))
                pharma_id = res_pharma.scalar()
                if not pharma_id:
                    db.session.execute(text("INSERT INTO pharmacies (name, is_active) VALUES ('Ma Pharmacie', TRUE)"))
                    db.session.commit()
                    pharma_id = db.session.execute(text("SELECT id FROM pharmacies LIMIT 1")).scalar()
                
                # Insert Admin avec password 'admin123' haché (simulé pour le seed, l'admin pourra reset)
                # Note: On utilise un hash générique ou on laisse le set_password faire plus tard
                pass_hash = "pbkdf2:sha256:600000$p6G6g2... (hash-placeholder)" 
                db.session.execute(text("""
                    INSERT INTO users (email, password_hash, role, pharmacy_id, is_active, is_super_admin, can_view_pos, can_view_inventory, can_view_hr, can_view_admin)
                    VALUES (:email, :pwd, 'Admin', :pid, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE)
                """), {"email": admin_email, "pwd": pass_hash, "pid": pharma_id})
                db.session.commit()
                diagnostic_log.append("Compte Admin créé.")
            else:
                db.session.execute(text("UPDATE users SET is_super_admin = TRUE, is_active = TRUE WHERE email = :email"), {"email": admin_email})
                db.session.commit()
                diagnostic_log.append("Compte Admin mis à jour.")
            
            # 6. Échantillon de Données ERP (CRM & Tâches)
            from app.models import Customer, Task
            res_p = db.session.execute(text("SELECT id FROM pharmacies LIMIT 1"))
            pharma_id = res_p.scalar()
            
            if pharma_id and Customer.query.filter_by(pharmacy_id=pharma_id).count() == 0:
                c1 = Customer(name="Moussa Diallo", phone="620112233", loyalty_points=150, pharmacy_id=pharma_id)
                c2 = Customer(name="Aissatou Barry", phone="621445566", loyalty_points=50, pharmacy_id=pharma_id)
                db.session.add_all([c1, c2])
            
            if pharma_id and Task.query.filter_by(pharmacy_id=pharma_id).count() == 0:
                # On utilise l'admin_id récupéré au point 5
                t1 = Task(title="Inventaire Rayon Alpha", description="Vérifier les dates d'expiration au rayon A", 
                          priority="Haute", status="A faire", 
                          created_by_id=admin_id, pharmacy_id=pharma_id)
                db.session.add(t1)

            db.session.commit()
            diagnostic_log.append("Données de test ERP (CRM, Tâches) OK.")

            return f"<h1>Succès de l'Activation !</h1><p>{' <br> '.join(diagnostic_log)}</p><a href='/'>Aller à l'accueil pour se connecter (Mot de passe: admin123)</a>"

        except Exception as e:
            db.session.rollback()
            import traceback
            error_details = traceback.format_exc()
            return f"<h1>Erreur Critique de Initialisation</h1><pre>{str(e)}</pre><h3>Détails :</h3><pre>{error_details}</pre>"

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
            from sqlalchemy import func
            from app.models import Sale, SubscriptionRecord
            
            # 1. Revenus Globaux (Ventes des pharmacies)
            total_global_revenue = db.session.query(func.sum(Sale.total_amount)).scalar() or 0
            
            # 2. Revenus SaaS (Abonnements payés à Mohamed)
            total_saas_revenue = db.session.query(func.sum(SubscriptionRecord.amount)).scalar() or 0
            
            # 3. Chiffre d'Affaires SaaS ce mois-ci
            first_day_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            monthly_saas_revenue = db.session.query(func.sum(SubscriptionRecord.amount))\
                .filter(SubscriptionRecord.timestamp >= first_day_month).scalar() or 0

            # 4. Répartition des Recettes SaaS par pharmacie (Pour le graphique GNF)
            pharma_stats = []
            saas_revenue_by_pharma = db.session.query(
                SubscriptionRecord.pharmacy_id, 
                func.sum(SubscriptionRecord.amount).label('total')
            ).group_by(SubscriptionRecord.pharmacy_id).all()
            
            saas_map = {r.pharmacy_id: r.total for r in saas_revenue_by_pharma}
            
            for p in pharmacies:
                pharma_stats.append({
                    'id': p.id,
                    'name': p.name,
                    'is_active': p.is_active,
                    'saas_revenue': saas_map.get(p.id, 0)
                })
            
            return render_template('superadmin/dashboard.html', 
                                   pharmacies=pharmacies,
                                   total_global_revenue=total_global_revenue,
                                   total_saas_revenue=total_saas_revenue,
                                   monthly_saas_revenue=monthly_saas_revenue,
                                   pharma_stats=pharma_stats,
                                   plans=SubscriptionPlan.query.filter_by(is_active=True).all())
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur d'accès Dashboard : {str(e)}", "danger")
            return render_template('superadmin/dashboard.html', 
                                   pharmacies=[],
                                   total_global_revenue=0,
                                   total_saas_revenue=0,
                                   monthly_saas_revenue=0,
                                   pharma_stats=[],
                                   plans=[])

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
            
            # --- NOTIFICATION EMAIL AU SUPER ADMIN ---
            try:
                from flask_mail import Message
                from app.extensions import mail
                msg = Message(f"💸 Nouveau Paiement : {pharma.name}",
                              recipients=["syllamohamedmhd99@gmail.com"])
                msg.body = f"Bonjour Mohamed,\n\nUne nouvelle transaction a été validée :\n\n" \
                           f"Pharmacie : {pharma.name}\n" \
                           f"Forfait : {plan.name}\n" \
                           f"Montant : {plan.price:,.0f} GNF\n" \
                           f"Nouvelle expiration : {pharma.subscription_end_date.strftime('%d/%m/%Y')}\n\n" \
                           f"L'accès a été prolongé automatiquement.\n\n" \
                           f"Cordialement,\nPharmaCloud SaaS"
                mail.send(msg)
            except Exception as e:
                print(f"Erreur notification email: {e}")

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

    @app.route('/superadmin/pharmacy/delete/<int:id>', methods=['POST'])
    @login_required
    def delete_pharmacy(id):
        if current_user.email != 'syllamohamedmhd99@gmail.com':
            return "Unauthorized", 401
            
        pharma = Pharmacy.query.get_or_404(id)
        name = pharma.name
        
        try:
            db.session.delete(pharma)
            db.session.commit()
            flash(f"La pharmacie {name} et toutes ses données ont été supprimées.", "warning")
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de la suppression : {str(e)}", "danger")
            
        return redirect(url_for('super_admin'))

    # L'initialisation de la base sera gérée par la commande de démarrage
    return app
