"""Prescription and PrescriptionItem models"""
from datetime import datetime, date, timedelta
from app.extensions import db


class Prescription(db.Model):
    """Prescription issued by a doctor"""
    __tablename__ = 'prescriptions'

    id = db.Column(db.Integer, primary_key=True)
    prescription_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    consultation_id = db.Column(db.Integer, db.ForeignKey('consultations.id', ondelete='SET NULL'), nullable=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete='SET NULL'), nullable=True)
    
    # Validity
    prescription_date = db.Column(db.Date, default=date.today, nullable=False)
    expiry_date = db.Column(db.Date)
    
    # Status
    status = db.Column(
        db.Enum('pending', 'issued', 'partially_dispensed', 'fully_dispensed',
                'referred', 'cancelled', 'expired', name='prescription_status'),
        default='pending', nullable=False
    )
    
    # QR
    qr_token_id = db.Column(db.Integer, db.ForeignKey('qr_tokens.id', ondelete='SET NULL'), nullable=True)
    
    notes = db.Column(db.Text)
    cancelled_reason = db.Column(db.Text)
    cancelled_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    cancelled_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = db.relationship('Patient', back_populates='prescriptions')
    doctor = db.relationship('User', foreign_keys=[doctor_id])
    consultation = db.relationship('Consultation', back_populates='prescriptions')
    organisation = db.relationship('Organisation')
    items = db.relationship('PrescriptionItem', back_populates='prescription',
                             lazy='dynamic', cascade='all, delete-orphan')
    dispensing_records = db.relationship('DispensingRecord', back_populates='prescription',
                                          lazy='dynamic')
    referrals = db.relationship('Referral', back_populates='prescription', lazy='dynamic')
    qr_token = db.relationship('QRToken', foreign_keys=[qr_token_id])

    @staticmethod
    def generate_number():
        year = datetime.utcnow().year
        last = Prescription.query.filter(
            Prescription.prescription_number.like(f'RX-{year}-%')
        ).order_by(Prescription.id.desc()).first()
        seq = (int(last.prescription_number.split('-')[-1]) + 1) if last else 1
        return f'RX-{year}-{seq:06d}'

    @property
    def is_expired(self):
        if self.expiry_date:
            return date.today() > self.expiry_date
        return False

    @property
    def is_processable(self):
        """Can this prescription still be dispensed?"""
        return self.status not in ('fully_dispensed', 'cancelled', 'expired')

    def update_status(self):
        """Recalculate status based on dispensed quantities"""
        total_prescribed = sum(i.quantity for i in self.items)
        total_dispensed = sum(i.quantity_dispensed for i in self.items)
        
        if total_dispensed == 0:
            if self.status not in ('cancelled', 'expired'):
                self.status = 'issued'
        elif total_dispensed < total_prescribed:
            self.status = 'partially_dispensed'
        else:
            self.status = 'fully_dispensed'

    def __repr__(self):
        return f'<Prescription {self.prescription_number}>'


class PrescriptionItem(db.Model):
    """Individual medicine line on a prescription"""
    __tablename__ = 'prescription_items'

    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id', ondelete='CASCADE'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id', ondelete='RESTRICT'), nullable=False)
    
    medicine_name = db.Column(db.String(255), nullable=False)  # Snapshot at prescription time
    strength = db.Column(db.String(100))
    dosage_form = db.Column(db.String(100))
    
    dosage = db.Column(db.String(100))      # e.g. "2 tablets"
    frequency = db.Column(db.String(100))   # e.g. "twice daily"
    duration = db.Column(db.String(100))    # e.g. "7 days"
    quantity = db.Column(db.Integer, nullable=False)
    quantity_dispensed = db.Column(db.Integer, default=0, nullable=False)
    
    instructions = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    prescription = db.relationship('Prescription', back_populates='items')
    medicine = db.relationship('Medicine', back_populates='prescription_items')
    dispensing_items = db.relationship('DispensingItem', back_populates='prescription_item',
                                        lazy='dynamic', cascade='all, delete-orphan')

    @property
    def quantity_remaining(self):
        return self.quantity - self.quantity_dispensed

    @property
    def is_fully_dispensed(self):
        return self.quantity_dispensed >= self.quantity

    def __repr__(self):
        return f'<PrescriptionItem {self.medicine_name} qty={self.quantity}>'

