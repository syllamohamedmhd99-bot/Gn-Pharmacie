from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.auth.decorators import admin_required
from app.extensions import db
from app.models import Task, User
from datetime import datetime

bp_productivity = Blueprint('productivity', __name__)

@bp_productivity.route('/tasks')
@login_required
def tasks():
    # Saas Filter
    if current_user.role == 'Admin':
         tasks = Task.query.filter_by(pharmacy_id=current_user.pharmacy_id).order_by(Task.due_date.asc()).all()
         users = User.query.filter_by(pharmacy_id=current_user.pharmacy_id, is_active=True).all()
    else:
         tasks = Task.query.filter_by(pharmacy_id=current_user.pharmacy_id, assigned_to_id=current_user.id).order_by(Task.due_date.asc()).all()
         users = []
    return render_template('productivity/tasks.html', tasks=tasks, users=users)

@bp_productivity.route('/tasks/add', methods=['POST'])
@login_required
@admin_required
def add_task():
    title = request.form.get('title')
    description = request.form.get('description')
    assignee_id = request.form.get('assigned_to')
    due_date_str = request.form.get('due_date')
    priority = request.form.get('priority', 'Normal')

    if not title:
        flash("Le titre de la tâche est obligatoire.", "danger")
        return redirect(url_for('productivity.tasks'))

    due_date = None
    if due_date_str:
        due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')

    new_task = Task(
        title=title,
        description=description,
        assigned_to_id=int(assignee_id) if assignee_id else None,
        created_by_id=current_user.id,
        due_date=due_date,
        priority=priority,
        pharmacy_id=current_user.pharmacy_id
    )
    db.session.add(new_task)
    db.session.commit()
    flash(f"Tâche '{title}' assignée avec succès.", "success")
    return redirect(url_for('productivity.tasks'))

@bp_productivity.route('/tasks/update/<int:id>', methods=['POST'])
@login_required
def update_task_status(id):
    task = Task.query.filter_by(id=id, pharmacy_id=current_user.pharmacy_id).first_or_404()
    
    # Seul l'assigné ou l'admin peut modifier le statut
    if current_user.role != 'Admin' and task.assigned_to_id != current_user.id:
        flash("Non autorisé.", "danger")
        return redirect(url_for('productivity.tasks'))

    new_status = request.form.get('status')
    if new_status:
        task.status = new_status
        db.session.commit()
        flash(f"Statut de la tâche mis à jour : {new_status}", "info")
    
    return redirect(url_for('productivity.tasks'))

@bp_productivity.route('/calendar')
@login_required
def calendar():
    # Global View
    from app.models import Shift, LeaveRequest
    shifts = Shift.query.filter_by(pharmacy_id=current_user.pharmacy_id).all()
    leaves = LeaveRequest.query.filter_by(pharmacy_id=current_user.pharmacy_id, status='Approuvé').all()
    tasks = Task.query.filter_by(pharmacy_id=current_user.pharmacy_id).all()
    
    return render_template('productivity/calendar.html', shifts=shifts, leaves=leaves, tasks=tasks)
