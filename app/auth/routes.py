from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app.extensions import db

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
             flash('Votre compte est en attente de validation par l\'administrateur.', 'warning')
             return redirect(url_for('auth.login'))
             
        login_user(user, remember=remember)
        return redirect(url_for('index'))
        
    return render_template('auth/login.html')

@bp_auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Les mots de passe ne correspondent pas.', 'danger')
            return redirect(url_for('auth.register'))
            
        user = User.query.filter_by(email=email).first()
        
        if user:
            flash('Cet email est déjà utilisé.', 'danger')
            return redirect(url_for('auth.register'))
            
        new_user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role='Vendeur', # Default role
            is_active=False  # Requires admin validation
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Inscription réussie ! Votre compte est en attente de validation.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/register.html')

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
