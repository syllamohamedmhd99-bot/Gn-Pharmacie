from datetime import datetime
from app.extensions import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# PILIER 1: Utilisateurs & RH
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False) # Admin, Pharmacien, Caissier
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    contract_type = db.Column(db.String(50), nullable=True) # CDI, CDD, Stagiaire
    hire_date = db.Column(db.Date, default=datetime.utcnow)
    base_salary = db.Column(db.Float, default=0.0)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=False) # Admin validation required
    image_url = db.Column(db.String(255), nullable=True) # Photo de profil
    
    # Granular Permissions (ACL)
    can_view_pos = db.Column(db.Boolean, default=True)
    can_view_inventory = db.Column(db.Boolean, default=False)
    can_view_hr = db.Column(db.Boolean, default=True)
    can_view_admin = db.Column(db.Boolean, default=False)
    
    shifts = db.relationship('Shift', backref='user', lazy=True, cascade="all, delete-orphan")
    timeclocks = db.relationship('TimeClock', backref='user', lazy=True, cascade="all, delete-orphan")
    sales = db.relationship('Sale', backref='cashier', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# PILIER 2: Stocks & FEFO
class Medicine(db.Model):
    __tablename__ = 'medicines'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    barcode = db.Column(db.String(100), unique=True, nullable=True)
    default_price = db.Column(db.Float, nullable=False)
    
    # Nouveaux champs pour logistique
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    min_stock_level = db.Column(db.Integer, default=10) # Seuil d'alerte
    
    batches = db.relationship('Batch', backref='medicine', lazy=True)

    @property
    def total_stock(self):
        return sum(batch.quantity for batch in self.batches)


class Batch(db.Model):
    __tablename__ = 'batches'
    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id'), nullable=False)
    batch_number = db.Column(db.String(50), nullable=False)
    expiry_date = db.Column(db.Date, nullable=False) # CRITICAL FOR FEFO
    quantity = db.Column(db.Integer, nullable=False, default=0)

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)

class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id'), nullable=True)
    requested_quantity = db.Column(db.Integer, default=100) # Qté recommandée
    status = db.Column(db.String(50), default='Draft') # Draft (Auto-Généré), Sent, Received
    
# PILIER 3: Ventes (POS)
class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    total_amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False) # Cash, OrangeMoney, MTN
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    items = db.relationship('SaleItem', backref='sale', lazy=True)

class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'), nullable=False) # FEFO point
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    
    batch = db.relationship('Batch', backref='sale_items', lazy=True)
    
# PILIER 1: Ressources Humaines (SIRH)
class Shift(db.Model):
    __tablename__ = 'shifts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

class TimeClock(db.Model):
    __tablename__ = 'time_clocks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now())
    action_type = db.Column(db.String(10), nullable=False) # "IN" ou "OUT"
    ip_address = db.Column(db.String(50), nullable=True)

class PayrollRecord(db.Model):
    __tablename__ = 'payroll_records'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    worked_hours = db.Column(db.Float, nullable=False)
    base_salary = db.Column(db.Float, nullable=False)
    total_paid = db.Column(db.Float, nullable=False)
    advance_deducted = db.Column(db.Float, default=0.0)
    proof_url = db.Column(db.String(255), nullable=True)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='Paid') # Paid, Pending
    
    employee = db.relationship('User', backref='payroll_history', lazy=True)

class SalaryAdvance(db.Model):
    __tablename__ = 'salary_advances'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(50), default='Pending') # Pending (En cours), Deducted (Déduite du salaire)

    user = db.relationship('User', backref='advances', lazy=True)
