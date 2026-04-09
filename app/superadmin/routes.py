from flask import render_template, redirect, url_for, flash, request, make_response, jsonify
from flask_login import login_required, current_user
from app.superadmin import bp_superadmin
from app.models import User, Pharmacy, SubscriptionPlan, SubscriptionRecord, Sale, SystemLog, SupportTicket
from app.extensions import db, mail
from datetime import datetime, timedelta
from sqlalchemy import func
import csv
from io import StringIO
from flask_mail import Message

def log_action(action, details=None, pharmacy_id=None):
    """Enregistre une action dans les logs système."""
    try:
        log = SystemLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            pharmacy_id=pharmacy_id or (current_user.pharmacy_id if current_user.is_authenticated else None),
            action=action,
            details=details,
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Erreur logging: {e}")

@bp_superadmin.app_context_processor
def inject_superadmin_vars():
    """Injecte le compteur de demandes en attente dans toutes les vues SuperAdmin."""
    if current_user.is_authenticated and current_user.is_super_admin:
        pending_count = Pharmacy.query.filter_by(is_active=False).count()
        return dict(pending_count=pending_count)
    return dict(pending_count=0)

def check_super_admin():
    if not current_user.is_authenticated or not current_user.is_super_admin:
        flash("Accès réservé au Super-Administrateur.", "danger")
        return False
    return True

@bp_superadmin.route('/optimize-db')
@login_required
def optimize_db():
    if not current_user.is_authenticated or not current_user.is_super_admin:
        return "Accès interdit", 403
        
    try:
        # Liste des index à créer
        indexes = [
            ("idx_users_pharmacy_id", "users", "pharmacy_id"),
            ("idx_medicines_pharmacy_id", "medicines", "pharmacy_id"),
            ("idx_batches_pharmacy_id", "batches", "pharmacy_id"),
            ("idx_batches_expiry_date", "batches", "expiry_date"),
            ("idx_suppliers_pharmacy_id", "suppliers", "pharmacy_id"),
            ("idx_purchase_orders_pharmacy_id", "purchase_orders", "pharmacy_id"),
            ("idx_sales_pharmacy_id", "sales", "pharmacy_id"),
            ("idx_sale_items_pharmacy_id", "sale_items", "pharmacy_id"),
            ("idx_shifts_pharmacy_id", "shifts", "pharmacy_id"),
            ("idx_time_clocks_pharmacy_id", "time_clocks", "pharmacy_id"),
            ("idx_payroll_records_pharmacy_id", "payroll_records", "pharmacy_id"),
            ("idx_salary_advances_pharmacy_id", "salary_advances", "pharmacy_id"),
            ("idx_subscription_records_pharmacy_id", "subscription_records", "pharmacy_id"),
            ("idx_customers_pharmacy_id", "customers", "pharmacy_id"),
            ("idx_tasks_pharmacy_id", "tasks", "pharmacy_id"),
            ("idx_leave_requests_pharmacy_id", "leave_requests", "pharmacy_id"),
            ("idx_system_logs_pharmacy_id", "system_logs", "pharmacy_id"),
            ("idx_support_tickets_pharmacy_id", "support_tickets", "pharmacy_id"),
            ("idx_pharmacies_is_active", "pharmacies", "is_active")
        ]
        
        from sqlalchemy import text
        for idx_name, table, column in indexes:
            try:
                sql = text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})")
                db.session.execute(sql)
            except Exception as e:
                print(f"Erreur sur {idx_name}: {e}")
        
        db.session.commit()
        log_action("Database Optimization", "Indexation de masse effectuée avec succès.")
        flash("La base de données a été optimisée avec succès ! Le site devrait être beaucoup plus rapide.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de l'optimisation : {e}", "danger")
        
    return redirect(url_for('superadmin.dashboard'))
    
@bp_superadmin.route('/check-schema')
@login_required
def check_schema():
    if not current_user.is_authenticated or not current_user.is_super_admin:
        return "Accès interdit", 403
        
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        result = {}
        for table in inspector.get_table_names():
            result[table] = [c['name'] for c in inspector.get_columns(table)]
        return jsonify(result)
    except Exception as e:
        return str(e), 500


@bp_superadmin.route('/dashboard')
@login_required
def dashboard():
    if not check_super_admin():
        return redirect(url_for('index'))
        
    try:
        pharmacies = Pharmacy.query.all()
        
        # 1. Revenus Globaux (Ventes des pharmacies)
        total_global_revenue = db.session.query(func.sum(Sale.total_amount)).scalar() or 0
        
        # 2. Revenus SaaS (Abonnements payés)
        total_saas_revenue = db.session.query(func.sum(SubscriptionRecord.amount)).scalar() or 0
        
        # 3. Chiffre d'Affaires SaaS ce mois-ci
        first_day_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_saas_revenue = db.session.query(func.sum(SubscriptionRecord.amount))\
            .filter(SubscriptionRecord.timestamp >= first_day_month).scalar() or 0

        # 4. Répartition des Recettes SaaS par pharmacie
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

@bp_superadmin.route('/toggle_pharmacy/<int:id>', methods=['POST'])
@login_required
def toggle_pharmacy(id):
    if not check_super_admin():
        return "Unauthorized", 401
        
    pharma = Pharmacy.query.get_or_404(id)
    pharma.is_active = not pharma.is_active
    
    # Activer/Désactiver tous les utilisateurs de cette pharmacie également
    for user in pharma.users:
        user.is_active = pharma.is_active
        
    db.session.commit()
    log_action("Toggle Pharmacy", f"Pharma {pharma.name} status set to {pharma.is_active}", pharma.id)
    status = "activée" if pharma.is_active else "désactivée"
    flash(f"La pharmacie {pharma.name} a été {status} avec succès.", "success")
    return redirect(url_for('superadmin.dashboard'))

@bp_superadmin.route('/update_subscription/<int:id>', methods=['POST'])
@login_required
def update_subscription(id):
    if not check_super_admin():
        return "Unauthorized", 401
        
    pharma = Pharmacy.query.get_or_404(id)
    plan_id = request.form.get('plan_id')
    plan = SubscriptionPlan.query.get(plan_id)
    
    if plan:
        # Enregistrement de la transaction
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
        
        try:
            db.session.commit()
            log_action("Subscription Update", f"Pharma {pharma.name} set to {plan.name} at {plan.price} GNF", pharma.id)
            flash(f"Abonnement {plan.name} activé pour {pharma.name}.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de la mise à jour : {str(e)}", "danger")
    else:
        flash("Plan de souscription non trouvé.", "danger")
    
    return redirect(request.referrer or url_for('superadmin.subscriptions'))

@bp_superadmin.route('/reports')
@login_required
def reports():
    if not check_super_admin():
        return redirect(url_for('index'))
    
    try:
        history = SubscriptionRecord.query.order_by(SubscriptionRecord.timestamp.desc()).all()
        return render_template('superadmin/reports.html', history=history)
    except Exception as e:
        log_action("Reports Error", f"Error loading reports: {str(e)}")
        flash("Une erreur est survenue lors du chargement des rapports.", "danger")
        return render_template('superadmin/reports.html', history=[])

@bp_superadmin.route('/reports/delete/<int:id>', methods=['POST'])
@login_required
def delete_subscription_record(id):
    if not check_super_admin():
        return "Unauthorized", 401
    
    record = SubscriptionRecord.query.get_or_404(id)
    try:
        db.session.delete(record)
        db.session.commit()
        log_action("Delete Subscription Record", f"Record #{id} deleted")
        flash(f"L'enregistrement #{id} a été supprimé.", "warning")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la suppression : {str(e)}", "danger")
    
    return redirect(url_for('superadmin.reports'))

@bp_superadmin.route('/export/payments')
@login_required
def export_payments():
    if not check_super_admin():
        return "Unauthorized", 401
    
    history = SubscriptionRecord.query.all()
    
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Pharmacie', 'Forfait', 'Montant (GNF)', 'Date'])
    
    for record in history:
        pharma = Pharmacy.query.get(record.pharmacy_id)
        pharma_name = pharma.name if pharma else "Inconnue"
        cw.writerow([record.id, pharma_name, record.plan_name, record.amount, record.timestamp.strftime('%d/%m/%Y %H:%M')])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=rapport_paiements_saas.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@bp_superadmin.route('/subscriptions')
@login_required
def subscriptions():
    if not check_super_admin():
        return redirect(url_for('index'))
        
    pharmacies = Pharmacy.query.order_by(Pharmacy.id.desc()).all()
    plans = SubscriptionPlan.query.filter_by(is_active=True).all()
    return render_template('superadmin/subscriptions.html', pharmacies=pharmacies, plans=plans, now=datetime.utcnow())

@bp_superadmin.route('/plans')
@login_required
def plans():
    if not check_super_admin():
        return redirect(url_for('index'))
    plans = SubscriptionPlan.query.all()
    return render_template('superadmin/plans.html', plans=plans)

@bp_superadmin.route('/plans/add', methods=['POST'])
@login_required
def add_plan():
    if not check_super_admin():
        return "Unauthorized", 401
        
    try:
        name = request.form.get('name')
        price_str = request.form.get('price')
        duration_str = request.form.get('duration')
        description = request.form.get('description')

        if not name or not price_str or not duration_str:
            flash("Veuillez remplir tous les champs obligatoires.", "warning")
            return redirect(url_for('superadmin.plans'))

        new_plan = SubscriptionPlan(
            name=name,
            price=float(price_str),
            duration_days=int(duration_str),
            description=description
        )
        db.session.add(new_plan)
        db.session.commit()
        log_action("Add Plan", f"New plan {new_plan.name} created at {new_plan.price} GNF")
        flash("Nouveau forfait ajouté avec succès.", "success")
    except ValueError:
        flash("Erreur : Le prix et la durée doivent être des nombres valides.", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de l'ajout : {str(e)}", "danger")
        
    return redirect(url_for('superadmin.plans'))

@bp_superadmin.route('/plans/delete/<int:id>')
@login_required
def delete_plan(id):
    if not check_super_admin():
        return "Unauthorized", 401
    plan = SubscriptionPlan.query.get_or_404(id)
    name = plan.name
    db.session.delete(plan)
    db.session.commit()
    log_action("Delete Plan", f"Plan {name} deleted")
    flash("Forfait supprimé.", "warning")
    return redirect(url_for('superadmin.plans'))

@bp_superadmin.route('/plans/edit/<int:id>', methods=['POST'])
@login_required
def edit_plan(id):
    if not check_super_admin():
        return "Unauthorized", 401
        
    try:
        plan = SubscriptionPlan.query.get_or_404(id)
        name = request.form.get('name')
        price_str = request.form.get('price')
        duration_str = request.form.get('duration')
        
        if not name or not price_str or not duration_str:
            flash("Veuillez remplir tous les champs obligatoires.", "warning")
            return redirect(url_for('superadmin.plans'))

        plan.name = name
        plan.price = float(price_str)
        plan.duration_days = int(duration_str)
        plan.description = request.form.get('description')
        
        db.session.commit()
        log_action("Edit Plan", f"Plan {plan.name} updated")
        flash(f"Le forfait {plan.name} a été mis à jour.", "success")
    except ValueError:
        flash("Erreur : Le prix et la durée doivent être des nombres valides.", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la modification : {str(e)}", "danger")
        
    return redirect(url_for('superadmin.plans'))

@bp_superadmin.route('/plans/toggle/<int:id>')
@login_required
def toggle_plan(id):
    if not check_super_admin():
        return "Unauthorized", 401
    
    plan = SubscriptionPlan.query.get_or_404(id)
    plan.is_active = not plan.is_active
    db.session.commit()
    
    status = "activé" if plan.is_active else "désactivé"
    log_action("Toggle Plan", f"Plan {plan.name} set to {status}")
    flash(f"Le forfait {plan.name} est désormais {status}.", "info")
    return redirect(url_for('superadmin.plans'))

@bp_superadmin.route('/approve_pharmacy/<int:id>', methods=['POST'])
@login_required
def approve_pharmacy(id):
    if not check_super_admin():
        return "Unauthorized", 401
    try:
        pharma = Pharmacy.query.get_or_404(id)
        pharma.is_active = True
        
        # Activer les admins
        for user in pharma.users:
            if user.role == 'Admin':
                user.is_active = True
                
        db.session.commit()
        log_action("Approve Pharmacy", f"Pharma {pharma.name} approved and activated", pharma.id)
        flash(f"La pharmacie {pharma.name} a été approuvée.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de l'approbation : {str(e)}", "danger")
        
    return redirect(url_for('superadmin.subscriptions'))

@bp_superadmin.route('/pharmacy/delete/<int:id>', methods=['POST'])
@login_required
def delete_pharmacy(id):
    if not check_super_admin():
        return "Unauthorized", 401
        
    pharma = Pharmacy.query.get_or_404(id)
    name = pharma.name
    
    try:
        log_action("Delete Pharmacy", f"PERMANENT DELETE: Pharmacy {name}", pharma.id)
        db.session.delete(pharma)
        db.session.commit()
        flash(f"La pharmacie {name} et toutes ses données ont été supprimées.", "warning")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la suppression : {str(e)}", "danger")
        
    return redirect(url_for('superadmin.dashboard'))

@bp_superadmin.route('/users')
@login_required
def users():
    if not check_super_admin():
        return redirect(url_for('index'))
    
    all_users = User.query.order_by(User.id.desc()).all()
    pharmacies = Pharmacy.query.all()
    return render_template('superadmin/users.html', users=all_users, pharmacies=pharmacies)

@bp_superadmin.route('/logs')
@login_required
def logs():
    if not check_super_admin():
        return redirect(url_for('index'))
    
    all_logs = SystemLog.query.order_by(SystemLog.timestamp.desc()).limit(500).all()
    return render_template('superadmin/logs.html', logs=all_logs)

@bp_superadmin.route('/support')
@login_required
def support():
    if not check_super_admin():
        return redirect(url_for('index'))
    
    tickets = SupportTicket.query.order_by(SupportTicket.created_at.desc()).all()
    return render_template('superadmin/support.html', tickets=tickets)

@bp_superadmin.route('/settings')
@login_required
def settings():
    if not check_super_admin():
        return redirect(url_for('index'))
    
    # Paramètres fictifs pour le moment (SaaS Config) - Récupéré des variables d'env
    from os import environ
    config_vars = {
        'MAIL_SERVER': environ.get('MAIL_SERVER', 'smtp.gmail.com'),
        'MAINTENANCE_MODE': environ.get('MAINTENANCE_MODE', 'OFF'),
        'GLOBAL_ALERT': environ.get('GLOBAL_ALERT', '')
    }
    return render_template('superadmin/settings.html', config=config_vars)

@bp_superadmin.route('/settings/update', methods=['POST'])
@login_required
def update_settings():
    if not check_super_admin():
        return "Unauthorized", 401
    
    # Dans un vrai système, on sauvegarderait ça en base ou via une API de config
    # Pour l'instant, on simule le succès
    alert = request.form.get('global_alert')
    log_action("Update SaaS Settings", f"Global Alert updated to: {alert}")
    flash("Paramètres mis à jour avec succès (Note: L'alerte globale est simulée).", "success")
    return redirect(url_for('superadmin.settings'))

@bp_superadmin.route('/support/ticket/<int:id>/close', methods=['POST'])
@login_required
def close_ticket(id):
    if not check_super_admin():
        return "Unauthorized", 401
    
    ticket = SupportTicket.query.get_or_404(id)
    ticket.status = 'Closed'
    db.session.commit()
    log_action("Close Ticket", f"Ticket #{ticket.id} closed", ticket.pharmacy_id)
    flash(f"Le ticket #{id} a été fermé.", "info")
    return redirect(url_for('superadmin.support'))

@bp_superadmin.route('/user/toggle/<int:id>')
@login_required
def toggle_user(id):
    if not check_super_admin():
        return "Unauthorized", 401
        
    if current_user.id == id:
        flash("Sécurité : Vous ne pouvez pas désactiver votre propre compte.", "danger")
        return redirect(url_for('superadmin.users'))
        
    user = User.query.get_or_404(id)
    user.is_active = not user.is_active
    db.session.commit()
    
    status = "activé" if user.is_active else "désactivé"
    log_action("Toggle User", f"User {user.email} status set to {user.is_active}")
    flash(f"L'utilisateur {user.email} a été {status}.", "success")
    return redirect(url_for('superadmin.users'))
