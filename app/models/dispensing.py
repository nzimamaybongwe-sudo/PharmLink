"""Dispensing models"""
from datetime import datetime
from app.extensions import db


class DispensingRecord(db.Model):
    """A single dispensing event for a prescription"""
    __tablename__ = 'dispensing_records'

    id = db.Column(db.Integer, primary_key=True)
    dispensing_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id', ondelete='CASCADE'), nullable=False)
    pharmacist_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete='SET NULL'), nullable=True)
    
    dispensed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Was this via QR scan?
    via_qr = db.Column(db.Boolean, default=False)
    
    is_partial = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    prescription = db.relationship('Prescription', back_populates='dispensing_records')
    pharmacist = db.relationship('User', foreign_keys=[pharmacist_id])
    organisation = db.relationship('Organisation')
    items = db.relationship('DispensingItem', back_populates='record',
                             lazy='dynamic', cascade='all, delete-orphan')

    @staticmethod
    def generate_number():
        year = datetime.utcnow().year
        last = DispensingRecord.query.filter(
            DispensingRecord.dispensing_number.like(f'DIS-{year}-%')
        ).order_by(DispensingRecord.id.desc()).first()
        seq = (int(last.dispensing_number.split('-')[-1]) + 1) if last else 1
        return f'DIS-{year}-{seq:06d}'

    def __repr__(self):
        return f'<DispensingRecord {self.dispensing_number}>'


class DispensingItem(db.Model):
    """Individual medicine dispensed in a DispensingRecord"""
    __tablename__ = 'dispensing_items'

    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey('dispensing_records.id', ondelete='CASCADE'), nullable=False)
    prescription_item_id = db.Column(db.Integer, db.ForeignKey('prescription_items.id', ondelete='CASCADE'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('medicine_batches.id', ondelete='RESTRICT'), nullable=False)
    
    quantity_dispensed = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Numeric(12, 2))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    record = db.relationship('DispensingRecord', back_populates='items')
    prescription_item = db.relationship('PrescriptionItem', back_populates='dispensing_items')
    batch = db.relationship('MedicineBatch')

    def __repr__(self):
        return f'<DispensingItem qty={self.quantity_dispensed}>'

