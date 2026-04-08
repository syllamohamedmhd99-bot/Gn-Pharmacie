from datetime import datetime
from app.extensions import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# PILIER 0: Multi-Tenancy (SaaS)
class Pharmacy(db.Model):
    __tablename__ = 'pharmacies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    license_number = db.Column(db.String(100), unique=True, nullable=True)
    address = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    
    # Identité Visuelle (Branding)
    logo_url = db.Column(db.String(255), nullable=True)
    invoice_header = db.Column(db.Text, nullable=True)
    invoice_footer = db.Column(db.Text, nullable=True)
    
    # Gestion des Abonnements
    subscription_plan = db.Column(db.String(50), default='Essai') # Essai, Mensuel, Trimestriel, Semestriel, Annuel
    subscription_end_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=False)

    # Relationships
    users = db.relationship('User', backref='pharmacy', lazy=True, cascade="all, delete-orphan")
    medicines = db.relationship('Medicine', backref='pharmacy', lazy=True, cascade="all, delete-orphan")
    sales = db.relationship('Sale', backref='pharmacy', lazy=True, cascade="all, delete-orphan")
    suppliers = db.relationship('Supplier', backref='pharmacy', lazy=True, cascade="all, delete-orphan")
    payments = db.relationship('SubscriptionRecord', backref='pharmacy', lazy=True, cascade="all, delete-orphan")
    
    # Nouveaux Modules
    customers = db.relationship('Customer', backref='pharmacy', lazy=True, cascade="all, delete-orphan")
    tasks = db.relationship('Task', backref='pharmacy', lazy=True, cascade="all, delete-orphan")
    leaves = db.relationship('LeaveRequest', backref='pharmacy', lazy=True, cascade="all, delete-orphan")

# PILIER 1: Utilisateurs & RH
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=True) # SaaS
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
    is_super_admin = db.Column(db.Boolean, default=False)
    
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
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=True) # SaaS
    name = db.Column(db.String(150), nullable=False)
    barcode = db.Column(db.String(100), nullable=True) # Not unique globally in SaaS
    purchase_price = db.Column(db.Float, default=0.0)
    default_price = db.Column(db.Float, nullable=False)
    
    # Nouveaux champs pour logistique
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    min_stock_level = db.Column(db.Integer, default=10) # Seuil d'alerte
    
    batches = db.relationship('Batch', backref='medicine', lazy=True, cascade="all, delete-orphan")

    @property
    def total_stock(self):
        return sum(batch.quantity for batch in self.batches)


class Batch(db.Model):
    __tablename__ = 'batches'
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=True) # SaaS
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id'), nullable=False)
    batch_number = db.Column(db.String(50), nullable=False)
    expiry_date = db.Column(db.Date, nullable=False) # CRITICAL FOR FEFO
    quantity = db.Column(db.Integer, nullable=False, default=0)

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=True) # SaaS
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    contact_person = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    
    # Relation pour voir tous les produits fournis par ce fournisseur
    products = db.relationship('Medicine', backref='provided_by', lazy=True)
    orders = db.relationship('PurchaseOrder', backref='to_supplier', lazy=True)

class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=True) # SaaS
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id'), nullable=True)
    requested_quantity = db.Column(db.Integer, default=100) # Qté recommandée
    status = db.Column(db.String(50), default='Draft') # Draft (Auto-Généré), Sent, Received
    
# PILIER 3: Ventes (POS)
class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=True) # SaaS
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    total_amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False) # Cash, OrangeMoney, MTN
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    
    items = db.relationship('SaleItem', backref='sale', lazy=True, cascade="all, delete-orphan")

class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=True) # SaaS
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'), nullable=False) # FEFO point
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    
    batch = db.relationship('Batch', backref='sale_items', lazy=True)
    
# PILIER 1: Ressources Humaines (SIRH)
class Shift(db.Model):
    __tablename__ = 'shifts'
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=True) # SaaS
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

class TimeClock(db.Model):
    __tablename__ = 'time_clocks'
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=True) # SaaS
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now())
    action_type = db.Column(db.String(10), nullable=False) # "IN" ou "OUT"
    ip_address = db.Column(db.String(50), nullable=True)

class PayrollRecord(db.Model):
    __tablename__ = 'payroll_records'
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=True) # SaaS
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
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=True) # SaaS
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(50), default='Pending') # Pending (En cours), Deducted (Déduite du salaire)

    user = db.relationship('User', backref='advances', lazy=True)
class SubscriptionPlan(db.Model):
    __tablename__ = 'subscription_plans'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True) # Mensuel, Annuel...
    price = db.Column(db.Float, nullable=False, default=0.0)
    duration_days = db.Column(db.Integer, nullable=False, default=30)
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Plan {self.name} - {self.price} GNF>'

class SubscriptionRecord(db.Model):
    __tablename__ = 'subscription_records'
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=False)
    plan_name = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, default=0.0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # La relation avec Pharmacy est gérée par le backref dans la classe Pharmacy

    def __repr__(self):
        return f'<SubscriptionRecord {self.plan_name} for Pharma {self.pharmacy_id}>'

# --- NOUVEAUX MODULES ERP ---

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    loyalty_points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sales = db.relationship('Sale', backref='customer', lazy=True)

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    priority = db.Column(db.String(20), default='Normal') # Basse, Normal, Haute, Urgent
    status = db.Column(db.String(20), default='A faire') # A faire, En cours, Terminé, Annulé
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('User', foreign_keys=[created_by_id], backref='tasks_created')
    assignee = db.relationship('User', foreign_keys=[assigned_to_id], backref='tasks_assigned')

class LeaveRequest(db.Model):
    __tablename__ = 'leave_requests'
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    leave_type = db.Column(db.String(50), nullable=False) # Congé, Maladie, Autre
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='En attente') # En attente, Approuvé, Refusé
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='leave_requests')
