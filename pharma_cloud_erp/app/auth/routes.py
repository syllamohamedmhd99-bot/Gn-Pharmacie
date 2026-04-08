from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User, Pharmacy
from app.extensions import db
from datetime import datetime, timedelta

bp_auth = Blueprint('auth', __name__)

@bp_auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not user.check_password(password):
            flash('Veuillez vérifier vos identifiants.', 'danger')
            return redirect(url_for('auth.login'))
            
        if not user.is_active:
             flash('Votre compte est en attente de validation.', 'warning')
             return redirect(url_for('auth.login'))
             
        if user.pharmacy and not user.pharmacy.is_active:
            flash('Le service pour cette pharmacie est suspendu ou en attente.', 'danger')
            return redirect(url_for('auth.login'))
             
        login_user(user, remember=remember)
        
        # Redirection directe pour le Super-Admin
        if user.is_super_admin:
            return redirect(url_for('superadmin.dashboard'))
            
        return redirect(url_for('index'))
        
    return render_template('auth/login.html')

@bp_auth.route('/register', methods=['GET', 'POST'])
def register():
    # Capturer le plan si fourni (Landing page)
    requested_plan = request.args.get('plan')
    if requested_plan:
        session['reg_plan'] = requested_plan

    # Étape 1 : Informations sur la Pharmacie
    if request.method == 'POST':
        name = request.form.get('pharmacy_name', '').strip()
        license_no = request.form.get('pharmacy_license', '').strip()
        
        # SÉCURITÉ SAAS : Vérification Robuste (Insensible à la casse + Espaces)
        from sqlalchemy import func
        existing = Pharmacy.query.filter(func.lower(Pharmacy.license_number) == license_no.lower()).first()
        
        if existing:
            flash(f"Désolé, la licence '{license_no}' est déjà utilisée par la pharmacie '{existing.name}'.", "warning")
            return redirect(url_for('auth.register'))
            
        session['reg_pharma_name'] = name
        session['reg_pharma_address'] = request.form.get('pharmacy_address', '').strip()
        session['reg_pharma_license'] = license_no
        return redirect(url_for('auth.register_admin'))
        
    return render_template('auth/register_pharmacy.html')

@bp_auth.route('/register/admin', methods=['GET', 'POST'])
def register_admin():
    # Étape 2 : Informations sur l'Administrateur
    if 'reg_pharma_name' not in session:
        return redirect(url_for('auth.register'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        
        if User.query.filter_by(email=email).first():
            flash('Cet email est déjà utilisé.', 'danger')
            return redirect(url_for('auth.register_admin'))
            
        # 1. Vérification de la Session (Sécurité)
        pharma_name = session.get('reg_pharma_name')
        if not pharma_name:
            flash("Informations de pharmacie manquantes. Veuillez recommencer l'étape 1.", "warning")
            return redirect(url_for('auth.register_pharma'))

        # 1. Créer la Pharmacie (Inactive par défaut + 30j essai)
        try:
            print(f"--- ETAPE 2 : Création de la pharmacie {pharma_name} ---")
            trial_end = datetime.utcnow() + timedelta(days=30)
            new_pharmacy = Pharmacy(
                name=pharma_name,
                address=session.get('reg_pharma_address'),
                license_number=session.get('reg_pharma_license'),
                subscription_plan=session.get('reg_plan', 'Essai'),
                subscription_end_date=trial_end,
                is_active=False # Verrouillé par défaut
            )
            db.session.add(new_pharmacy)
            db.session.flush() # Récupérer l'ID sans commiter tout de suite
            print(f"ID Pharmacie généré : {new_pharmacy.id}")
            
            # 2. Créer l'Utilisateur Admin (Inactif par défaut)
            print(f"--- ETAPE 2 : Création de l'utilisateur {email} ---")
            new_user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                role='Admin',
                pharmacy_id=new_pharmacy.id,
                is_active=False, # Validation Super-Admin requise
                can_view_pos=True,
                can_view_inventory=True,
                can_view_hr=True,
                can_view_admin=True
            )
            new_user.set_password(password)
            db.session.add(new_user)
            
            # 3. Finalisation en base
            db.session.commit()
            print("--- CRÉATION RÉUSSIE ---")
            
        except Exception as e:
            db.session.rollback()
            print(f"--- ERREUR CRITIQUE BASE DE DONNÉES : {str(e)} ---")
            flash("Une erreur est survenue lors de l'enregistrement de vos accès. Veuillez réessayer.", "danger")
            return redirect(url_for('auth.register'))
        
        # 4. Alerte Email aux Super-Admins
        try:
            from flask_mail import Message
            from app.extensions import mail
            # Récupérer les emails de tous les super-admins actifs
            super_admins = User.query.filter_by(is_super_admin=True, is_active=True).all()
            recipients = [sa.email for sa in super_admins] if super_admins else ["syllamohamedmhd99@gmail.com"]

            msg = Message("Nouvelle demande d'inscription - PharmaCloud",
                          recipients=recipients)
            msg.body = f"Bonjour,\n\nUne nouvelle pharmacie s'est inscrite sur la plateforme :\n" \
                       f"Nom : {pharma_name}\n" \
                       f"Admin : {first_name} {last_name} ({email})\n" \
                       f"Licence : {session.get('reg_pharma_license')}\n\n" \
                       f"Veuillez vous connecter à la console SaaS pour valider cet accès.\n\n" \
                       f"Cordialement,\nSystème PharmaCloud"
            mail.send(msg)
            print("Email d'alerte envoyé au Super-Admin.")
        except Exception as e:
            print(f"--- ERREUR CRITIQUE SMTP ---")
            print(f"Détail : {str(e)}")
            print(f"--- FIN ERREUR ---")
            # Ne bloque pas l'inscription
        session.pop('reg_pharma_name', None)
        session.pop('reg_pharma_address', None)
        session.pop('reg_pharma_license', None)
        
        flash('Demande d\'inscription envoyée !', 'success')
        return redirect(url_for('auth.registration_pending'))
        
    return render_template('auth/register_admin.html')

@bp_auth.route('/registration-pending')
def registration_pending():
    return render_template('auth/pending_activation.html')

@bp_auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@bp_auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name')
        current_user.last_name = request.form.get('last_name')
        current_user.phone = request.form.get('phone')
        current_user.address = request.form.get('address')
        
        # Gestion de la photo de profil
        file = request.files.get('photo')
        if file and file.filename:
            from werkzeug.utils import secure_filename
            import os
            filename = secure_filename(f"profile_{current_user.id}_{file.filename}")
            upload_path = os.path.join('app', 'static', 'uploads', 'profiles')
            if not os.path.exists(upload_path):
                os.makedirs(upload_path)
            file.save(os.path.join(upload_path, filename))
            current_user.image_url = f"uploads/profiles/{filename}"
            
        db.session.commit()
        flash('Profil mis à jour avec succès.', 'success')
        return redirect(url_for('auth.profile'))
        
    return render_template('auth/profile.html')
