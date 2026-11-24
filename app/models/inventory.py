"""Inventory: MedicineBatch and StockMovement models"""
from datetime import datetime, date
from app.extensions import db


class MedicineBatch(db.Model):
    """Individual stock batch for a medicine"""
    __tablename__ = 'medicine_batches'

    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id', ondelete='CASCADE'), nullable=False)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete='CASCADE'), nullable=False)
    
    batch_number = db.Column(db.String(100), nullable=False)
    
    quantity_received = db.Column(db.Integer, nullable=False, default=0)
    quantity_remaining = db.Column(db.Integer, nullable=False, default=0)
    
    manufacture_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date, nullable=False)
    
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id', ondelete='SET NULL'), nullable=True)
    purchase_cost = db.Column(db.Numeric(12, 2))
    selling_price = db.Column(db.Numeric(12, 2))
    
    date_received = db.Column(db.Date, default=date.today)
    received_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    medicine = db.relationship('Medicine', back_populates='batches')
    organisation = db.relationship('Organisation')
    supplier = db.relationship('Supplier', back_populates='batches')
    received_by = db.relationship('User', foreign_keys=[received_by_id])
    stock_movements = db.relationship('StockMovement', back_populates='batch',
                                       lazy='dynamic', cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('medicine_id', 'batch_number', 'organisation_id', name='uq_batch'),
    )

    @property
    def is_expired(self):
        return self.expiry_date < date.today()

    @property
    def days_to_expiry(self):
        return (self.expiry_date - date.today()).days

    @property
    def is_near_expiry(self, threshold_days=90):
        return 0 < self.days_to_expiry <= threshold_days

    @property
    def status_badge(self):
        if self.is_expired:
            return 'danger'
        elif self.days_to_expiry <= 90:
            return 'warning'
        elif self.quantity_remaining == 0:
            return 'secondary'
        return 'success'

    def __repr__(self):
        return f'<MedicineBatch {self.batch_number} qty={self.quantity_remaining}>'


class StockMovement(db.Model):
    """Every change to stock quantity is recorded here"""
    __tablename__ = 'stock_movements'

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('medicine_batches.id', ondelete='CASCADE'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id', ondelete='CASCADE'), nullable=False)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete='CASCADE'), nullable=False)
    
    movement_type = db.Column(
        db.Enum('received', 'dispensed', 'adjustment_in', 'adjustment_out',
                'returned', 'expired_removed', 'transferred_out', 'transferred_in',
                name='movement_type_enum'),
        nullable=False
    )
    
    quantity = db.Column(db.Integer, nullable=False)
    quantity_before = db.Column(db.Integer, nullable=False)
    quantity_after = db.Column(db.Integer, nullable=False)
    
    reference_type = db.Column(db.String(50))  # 'dispensing', 'prescription', 'referral', 'adjustment'
    reference_id = db.Column(db.Integer)
    
    notes = db.Column(db.Text)
    performed_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    batch = db.relationship('MedicineBatch', back_populates='stock_movements')
    medicine = db.relationship('Medicine')
    organisation = db.relationship('Organisation')
    performed_by = db.relationship('User', foreign_keys=[performed_by_id])

    def __repr__(self):
        return f'<StockMovement {self.movement_type} qty={self.quantity}>'

