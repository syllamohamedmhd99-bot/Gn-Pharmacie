from functools import wraps
from flask import abort, render_template
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'Admin':
            return render_template('errors/403.html'), 403
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission_attr):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return abort(401)
            if not getattr(current_user, permission_attr, False) and current_user.role != 'Admin':
                return render_template('errors/403.html'), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator
