from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.auth.decorators import admin_required, permission_required
from app.extensions import db
from app.models import TimeClock, Shift, User, PayrollRecord, SalaryAdvance
import os
from werkzeug.utils import secure_filename
from datetime import datetime

bp_hr = Blueprint('hr', __name__)

@bp_hr.route('/dashboard')
@login_required
@permission_required('can_view_hr')
def dashboard():
    # FILTRE SAAS: Seulement MA pharmacie
    users = User.query.filter_by(pharmacy_id=current_user.pharmacy_id).all()
    recent_clocks = TimeClock.query.filter_by(pharmacy_id=current_user.pharmacy_id).order_by(TimeClock.timestamp.desc()).limit(10).all()
    shifts = Shift.query.filter_by(pharmacy_id=current_user.pharmacy_id).order_by(Shift.date.asc()).all()
    
    return render_template('hr/dashboard.html', 
                           users=users,
                           recent_clocks=recent_clocks,
                           shifts=shifts)

@bp_hr.route('/directory')
@login_required
@admin_required
def directory():
    # FILTRE SAAS: Seulement mon annuaire
    users = User.query.filter_by(pharmacy_id=current_user.pharmacy_id).all()
    from datetime import datetime
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    from app.hr_management.payroll_service import calculate_monthly_hours
    
    for u in users:
        u.monthly_hours = calculate_monthly_hours(u.id, current_year, current_month)
        
    return render_template('hr/directory.html', users=users, month=current_month, year=current_year)

@bp_hr.route('/history')
@login_required
@admin_required
def history():
    clocks = TimeClock.query.filter_by(pharmacy_id=current_user.pharmacy_id).order_by(TimeClock.timestamp.desc()).all()
    return render_template('hr/history.html', clocks=clocks)

@bp_hr.route('/timeclock/delete/<int:clock_id>', methods=['POST'])
@login_required
@admin_required
def delete_clock(clock_id):
    clock = TimeClock.query.filter_by(id=clock_id, pharmacy_id=current_user.pharmacy_id).first_or_404()
    db.session.delete(clock)
    db.session.commit()
    flash("Pointage supprimé avec succès.", "success")
    return redirect(url_for('hr.history'))

@bp_hr.route('/timeclock/edit/<int:clock_id>', methods=['POST'])
@login_required
@admin_required
def edit_clock(clock_id):
    clock = TimeClock.query.get_or_404(clock_id)
    new_action = request.form.get('action_type')
    new_time_str = request.form.get('timestamp') # Format attntu: YYYY-MM-DDTHH:MM
    
    if new_action:
        clock.action_type = new_action
    
    if new_time_str:
        from datetime import datetime
        try:
             clock.timestamp = datetime.strptime(new_time_str, '%Y-%m-%dT%H:%M')
        except ValueError:
             flash("Format de date invalide.", "danger")
             return redirect(url_for('hr.history'))
             
    db.session.commit()
    flash("Pointage modifié avec succès.", "success")
    return redirect(url_for('hr.history'))

@bp_hr.route('/employee/add', methods=['POST'])
@login_required
@admin_required
def add_employee():
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    contract = request.form.get('contract_type')
    salary = float(request.form.get('base_salary', 0))
    
    if email and password and role:
        new_user = User(
            email=email,
            role=role,
            first_name=first_name,
            last_name=last_name,
            phone=request.form.get('phone'),
            address=request.form.get('address'),
            contract_type=contract,
            base_salary=salary,
            is_active=True,
            pharmacy_id=current_user.pharmacy_id # SAE
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash("Employé ajouté à l'annuaire avec succès", "success")
    else:
        flash("Les champs email, password et role sont obligatoires", "danger")
        
    return redirect(url_for('hr.directory'))

@bp_hr.route('/employee/toggle_status/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Vous ne pouvez pas désactiver votre propre compte.", "warning")
    else:
        user.is_active = not user.is_active
        db.session.commit()
        status_text = "activé" if user.is_active else "désactivé"
        flash(f"Compte de {user.first_name} {user.last_name} {status_text} avec succès.", "success")
    return redirect(url_for('hr.directory'))

@bp_hr.route('/employee/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Vous ne pouvez pas supprimer votre propre compte.", "danger")
    else:
        db.session.delete(user)
        db.session.commit()
        flash(f"Employé {user.first_name} supprimé définitivement.", "success")
    return redirect(url_for('hr.directory'))

@bp_hr.route('/employee/permissions/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def update_permissions(user_id):
    user = User.query.get_or_404(user_id)
    user.can_view_pos = 'can_view_pos' in request.form
    user.can_view_inventory = 'can_view_inventory' in request.form
    user.can_view_hr = 'can_view_hr' in request.form
    user.can_view_admin = 'can_view_admin' in request.form
    db.session.commit()
    flash(f"Permissions de {user.first_name} mises à jour.", "success")
    return redirect(url_for('hr.directory'))

@bp_hr.route('/payroll/history')
@login_required
@admin_required
def payroll_history():
    # FILTRE SAAS: Historique paie de MA pharmacie
    records = PayrollRecord.query.filter_by(pharmacy_id=current_user.pharmacy_id).order_by(PayrollRecord.payment_date.desc()).all()
    return render_template('hr/payroll_history.html', records=records)

@bp_hr.route('/payroll/process/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def process_payroll(user_id):
    from datetime import datetime
    now = datetime.now()
    # Sécurité SaaS
    user = User.query.filter_by(id=user_id, pharmacy_id=current_user.pharmacy_id).first_or_404()
    
    from app.hr_management.payroll_service import calculate_monthly_hours
    hours = calculate_monthly_hours(user_id, now.year, now.month)

    # Calcul simple du salaire au prorata des heures (ex: base_salary est le taux horaire ou fixe ?)
    # On va assumer ici que base_salary est le taux horaire pour la démo, ou un fixe mensuel.
    # On va stocker le fixe mensuel par défaut.
    
    # Calculer le montant des avances en cours (SAE)
    pending_advances = SalaryAdvance.query.filter_by(user_id=user_id, pharmacy_id=current_user.pharmacy_id, status='Pending').all()
    total_advance_amount = sum(adv.amount for adv in pending_advances)
    
    # Net à payer (Simplifié : Salaire de base - Avances)
    final_to_pay = user.base_salary - total_advance_amount
    
    record = PayrollRecord(
        user_id=user_id,
        pharmacy_id=current_user.pharmacy_id, # SAE
        month=now.month,
        year=now.year,
        worked_hours=hours,
        base_salary=user.base_salary,
        total_paid=final_to_pay,
        advance_deducted=total_advance_amount,
        status='Paid'
    )
    db.session.add(record)
    
    # Marquer les avances comme déduites
    for adv in pending_advances:
        adv.status = 'Deducted'
        
    db.session.commit()
    
    flash(f"Paie de {user.first_name} pour {now.month}/{now.year} validée avec succès.", "success")
    return redirect(url_for('hr.payroll_history'))

@bp_hr.route('/payroll/update/<int:record_id>', methods=['POST'])
@login_required
@admin_required
def update_payroll(record_id):
    record = PayrollRecord.query.get_or_404(record_id)
    try:
        record.total_paid = float(request.form.get('amount'))
        record.worked_hours = float(request.form.get('hours'))
        db.session.commit()
        flash("Enregistrement de paie mis à jour.", "success")
    except ValueError:
        flash("Valeurs invalides transmises.", "danger")
    return redirect(url_for('hr.payroll_history'))

@bp_hr.route('/payroll/delete/<int:record_id>', methods=['POST'])
@login_required
@admin_required
def delete_payroll(record_id):
    record = PayrollRecord.query.get_or_404(record_id)
    db.session.delete(record)
    db.session.commit()
    flash("Enregistrement de paie supprimé.", "success")
    return redirect(url_for('hr.payroll_history'))

@bp_hr.route('/timeclock', methods=['POST'])
@login_required
def timeclock():
    user_id = request.form.get('user_id')
    ip_address = request.remote_addr
    
    # VERIFICATION DE SECURITE LOCALE (GEOLOCALISATION/IP)
    # Dans la vraie vie on autorise localhost ou la plage réseau locale de la pharmacie.
    allowed_ips = ['127.0.0.1', '::1']
    if not (ip_address in allowed_ips or ip_address.startswith('192.168.')):
         flash(f"⚠️ Pointage refusé. Vous n'êtes pas sur le réseau WiFi de la pharmacie. (IP: {ip_address})", "danger")
         return redirect(url_for('hr.dashboard'))
    
    if not user_id:
        flash("Veuillez sélectionner un employé", "warning")
        return redirect(url_for('hr.dashboard'))
    
    user = User.query.get(user_id)
    
    last_clock = TimeClock.query.filter_by(user_id=user_id, pharmacy_id=current_user.pharmacy_id).order_by(TimeClock.timestamp.desc()).first()
    new_action = 'IN' if not last_clock or last_clock.action_type == 'OUT' else 'OUT'
    
    clock_record = TimeClock(
        user_id=int(user_id),
        pharmacy_id=current_user.pharmacy_id, # SAE
        action_type=new_action,
        ip_address=ip_address
    )
    db.session.add(clock_record)
    db.session.commit()
    
    flash(f"{user.email} : Pointage {new_action} enregistré à {datetime.now().strftime('%H:%M')} !", "success")
    return redirect(url_for('hr.dashboard'))

@bp_hr.route('/shift/add', methods=['POST'])
def add_shift():
    user_id = 1 # Simulation
    date_str = request.form.get('date')
    start_time_str = request.form.get('start_time')
    end_time_str = request.form.get('end_time')
    
    if date_str and start_time_str and end_time_str:
        from datetime import datetime
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
        st = datetime.strptime(start_time_str, '%H:%M').time()
        et = datetime.strptime(end_time_str, '%H:%M').time()
        
        shift = Shift(user_id=user_id, date=d, start_time=st, end_time=et)
        db.session.add(shift)
        db.session.commit()
        flash("Planning ajouté avec succès", "success")
        
    return redirect(url_for('hr.dashboard'))

@bp_hr.route('/employee/advance/add/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def add_advance(user_id):
    amount = float(request.form.get('amount', 0))
    reason = request.form.get('reason')
    
    if amount > 0:
        advance = SalaryAdvance(
            user_id=user_id, 
            amount=amount, 
            reason=reason,
            pharmacy_id=current_user.pharmacy_id # SAE
        )
        db.session.add(advance)
        db.session.commit()
        flash(f"Avance de {amount} GNF accordée.", "success")
    else:
        flash("Montant invalide.", "danger")
        
    return redirect(url_for('hr.directory'))

@bp_hr.route('/payroll/upload_proof/<int:record_id>', methods=['POST'])
@login_required
@admin_required
def upload_proof(record_id):
    record = PayrollRecord.query.get_or_404(record_id)
    file = request.files.get('proof')
    
    if file and file.filename:
        filename = secure_filename(f"proof_payroll_{record_id}_{file.filename}")
        upload_path = os.path.join('app', 'static', 'uploads', 'proofs')
        if not os.path.exists(upload_path):
            os.makedirs(upload_path)
            
        file.save(os.path.join(upload_path, filename))
        record.proof_url = f"uploads/proofs/{filename}"
        db.session.commit()
        flash("Preuve de paiement enregistrée.", "success")
        
    return redirect(url_for('hr.payroll_history'))

@bp_hr.route('/payroll/payslip/<int:record_id>')
@login_required
@admin_required
def view_payslip(record_id):
    record = PayrollRecord.query.get_or_404(record_id)
    return render_template('hr/payslip.html', record=record)

@bp_hr.route('/employee/upload_photo/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def upload_photo(user_id):
    user = User.query.get_or_404(user_id)
    file = request.files.get('photo')
    
    if file and file.filename:
        filename = secure_filename(f"profile_{user_id}_{file.filename}")
        upload_path = os.path.join('app', 'static', 'uploads', 'profiles')
        if not os.path.exists(upload_path):
            os.makedirs(upload_path)
            
        file.save(os.path.join(upload_path, filename))
        user.image_url = f"uploads/profiles/{filename}"
        db.session.commit()
        flash("La photo de profil a été mise à jour.", "success")
        
    return redirect(url_for('hr.directory'))
