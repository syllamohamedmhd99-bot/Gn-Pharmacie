from flask import Flask, render_template, redirect, url_for
from flask_login import login_required
from config import config
from app.extensions import db, migrate, login_manager
from app.models import User, Medicine, Batch, Sale, SaleItem
from datetime import datetime, timedelta

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialiser les extensions
    db.init_app(app)
    migrate.init_app(app, db)
    

    login_manager.init_app(app)

    # Enregistrement des Blueprints
    from app.hr_management.routes import bp_hr
    from app.inventory_fefo.routes import bp_inventory
    from app.pos_sales.routes import bp_pos
    from app.auth.routes import bp_auth

    app.register_blueprint(bp_hr, url_prefix='/hr')
    app.register_blueprint(bp_inventory, url_prefix='/inventory')
    app.register_blueprint(bp_pos, url_prefix='/pos')
    app.register_blueprint(bp_auth, url_prefix='/auth')

    # Global Dashboard route
    @app.route('/')
    @login_required
    def index():
        total_medicines = Medicine.query.count()
        total_users = User.query.count()
        total_revenue = db.session.query(db.func.sum(Sale.total_amount)).scalar() or 0
        
        # Alert Logic
        from datetime import datetime
        today = datetime.utcnow()
        expired_count = Batch.query.filter(Batch.expiry_date < today, Batch.quantity > 0).count()
        low_stock = [m for m in Medicine.query.all() if m.total_stock <= m.min_stock_level]
                
        return render_template('index.html', 
                               total_medicines=total_medicines,
                               total_users=total_users,
                               total_revenue=total_revenue,
                               expired_count=expired_count,
                               low_stock=low_stock)

    # Temporary Seeding Route for Demo
    @app.route('/seed')
    def seed():
        db.create_all()
        # 1. Create default admin if not exists
        admin = User.query.filter_by(email='admin@pharma.com').first()
        if not admin:
            admin = User(email='admin@pharma.com', role='Admin', is_active=True, 
                         first_name='Admin', last_name='Titulaire',
                         can_view_pos=True, can_view_inventory=True, 
                         can_view_hr=True, can_view_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
        else:
            admin.is_active = True
            admin.role = 'Admin'
            admin.can_view_pos = True
            admin.can_view_inventory = True
            admin.can_view_hr = True
            admin.can_view_admin = True
            admin.set_password('admin123')
        db.session.commit()

        # 2. Add some medicines
        if Medicine.query.count() == 0:
            m1 = Medicine(name='Amoxicilline 1g', default_price=45000.0, min_stock_level=20)
            m2 = Medicine(name='Doliprane 1000', default_price=12000.0, min_stock_level=15)
            m3 = Medicine(name='Paracétamol Sirop', default_price=8000.0, min_stock_level=10)
            m4 = Medicine(name='Betadine Jaune', default_price=35000.0, min_stock_level=50) # ALERT TEST
            db.session.add_all([m1, m2, m3, m4])
            db.session.commit()

            # Add lots (batches)
            from datetime import timedelta
            b1 = Batch(medicine_id=m1.id, batch_number='LOT-AMX-001', quantity=100, expiry_date=datetime.utcnow() + timedelta(days=365))
            b2 = Batch(medicine_id=m2.id, batch_number='LOT-DOL-001', quantity=5, expiry_date=datetime.utcnow() + timedelta(days=15)) # EXPIRY ALERT
            b3 = Batch(medicine_id=m4.id, batch_number='LOT-BET-001', quantity=10, expiry_date=datetime.utcnow() + timedelta(days=200)) # STOCK ALERT
            db.session.add_all([b1, b2, b3])

            # 4. Add a dummy sale
            sale = Sale(user_id=1, total_amount=157000.0, payment_method='Cash')
            db.session.add(sale)

        db.session.commit()
        return redirect(url_for('index'))

    return app
