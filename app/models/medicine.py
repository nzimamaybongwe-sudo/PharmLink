"""Medicine, MedicineCategory, Supplier models"""
from datetime import datetime
from app.extensions import db


class MedicineCategory(db.Model):
    """Drug/medicine classification"""
    __tablename__ = 'medicine_categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    medicines = db.relationship('Medicine', back_populates='category', lazy='dynamic')

    def __repr__(self):
        return f'<MedicineCategory {self.name}>'


class Supplier(db.Model):
    """Supplier / pharmaceutical distributor"""
    __tablename__ = 'suppliers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    contact_person = db.Column(db.String(200))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    registration_number = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    batches = db.relationship('MedicineBatch', back_populates='supplier', lazy='dynamic')

    def __repr__(self):
        return f'<Supplier {self.name}>'


class Medicine(db.Model):
    """Master medicine catalogue"""
    __tablename__ = 'medicines'

    id = db.Column(db.Integer, primary_key=True)
    medicine_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    generic_name = db.Column(db.String(255))
    brand_name = db.Column(db.String(255))
    
    category_id = db.Column(db.Integer, db.ForeignKey('medicine_categories.id', ondelete='SET NULL'), nullable=True)
    
    strength = db.Column(db.String(100))          # e.g. "500mg", "250mg/5ml"
    dosage_form = db.Column(db.String(100))        # e.g. "tablet", "syrup", "injection"
    unit_of_measurement = db.Column(db.String(50)) # e.g. "tablet", "ml", "vial"
    
    description = db.Column(db.Text)
    barcode = db.Column(db.String(100), unique=True)
    
    # Stock control
    reorder_level = db.Column(db.Integer, default=10)
    
    # Controlled substance flag
    is_controlled = db.Column(db.Boolean, default=False)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    
    # Organisation context (each facility manages its own catalogue)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete='SET NULL'), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    category = db.relationship('MedicineCategory', back_populates='medicines')
    batches = db.relationship('MedicineBatch', back_populates='medicine',
                               lazy='dynamic', cascade='all, delete-orphan')
    prescription_items = db.relationship('PrescriptionItem', back_populates='medicine', lazy='dynamic')

    @property
    def total_stock(self):
        """Sum of all active, non-expired batch quantities"""
        from datetime import date
        from app.models.inventory import MedicineBatch
        total = db.session.query(
            db.func.sum(MedicineBatch.quantity_remaining)
        ).filter(
            MedicineBatch.medicine_id == self.id,
            MedicineBatch.quantity_remaining > 0,
            MedicineBatch.expiry_date > date.today(),
            MedicineBatch.is_active == True,
        ).scalar()
        return total or 0

    @property
    def is_low_stock(self):
        return self.total_stock <= self.reorder_level

    @staticmethod
    def generate_code():
        last = Medicine.query.order_by(Medicine.id.desc()).first()
        seq = (last.id + 1) if last else 1
        return f'MED-{seq:05d}'

    def __repr__(self):
        return f'<Medicine {self.medicine_code}: {self.name}>'

