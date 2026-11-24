"""Referral models"""
from datetime import datetime
from app.extensions import db


class Referral(db.Model):
    """Medicine referral from one facility to another"""
    __tablename__ = 'referrals'

    id = db.Column(db.Integer, primary_key=True)
    referral_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id', ondelete='CASCADE'), nullable=False)
    
    # Origin
    originating_organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete='SET NULL'), nullable=True)
    referring_pharmacist_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    # Destination
    receiving_organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete='SET NULL'), nullable=True)
    
    status = db.Column(
        db.Enum('draft', 'pending', 'sent', 'accepted', 'rejected',
                'partially_fulfilled', 'fulfilled', 'cancelled', 'expired',
                name='referral_status'),
        default='draft', nullable=False
    )
    
    reason = db.Column(db.Text)
    rejection_reason = db.Column(db.Text)
    expiry_date = db.Column(db.Date)
    
    # Funding
    funding_type = db.Column(
        db.Enum('patient_funded', 'government_funded', 'insurance', 'other', name='funding_type_enum'),
        default='patient_funded'
    )
    funding_reference = db.Column(db.String(100))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at = db.Column(db.DateTime)
    accepted_at = db.Column(db.DateTime)
    fulfilled_at = db.Column(db.DateTime)

    # Relationships
    prescription = db.relationship('Prescription', back_populates='referrals')
    originating_organisation = db.relationship('Organisation',
                                                 foreign_keys=[originating_organisation_id])
    receiving_organisation = db.relationship('Organisation',
                                              foreign_keys=[receiving_organisation_id])
    referring_pharmacist = db.relationship('User', foreign_keys=[referring_pharmacist_id])
    items = db.relationship('ReferralItem', back_populates='referral',
                             lazy='dynamic', cascade='all, delete-orphan')
    fulfilments = db.relationship('ReferralFulfilment', back_populates='referral',
                                   lazy='dynamic', cascade='all, delete-orphan')

    @staticmethod
    def generate_number():
        year = datetime.utcnow().year
        last = Referral.query.filter(
            Referral.referral_number.like(f'REF-{year}-%')
        ).order_by(Referral.id.desc()).first()
        seq = (int(last.referral_number.split('-')[-1]) + 1) if last else 1
        return f'REF-{year}-{seq:06d}'

    def __repr__(self):
        return f'<Referral {self.referral_number}>'


class ReferralItem(db.Model):
    """Individual medicine line in a referral"""
    __tablename__ = 'referral_items'

    id = db.Column(db.Integer, primary_key=True)
    referral_id = db.Column(db.Integer, db.ForeignKey('referrals.id', ondelete='CASCADE'), nullable=False)
    prescription_item_id = db.Column(db.Integer, db.ForeignKey('prescription_items.id', ondelete='CASCADE'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id', ondelete='RESTRICT'), nullable=False)
    
    quantity_requested = db.Column(db.Integer, nullable=False)
    quantity_fulfilled = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    referral = db.relationship('Referral', back_populates='items')
    prescription_item = db.relationship('PrescriptionItem')
    medicine = db.relationship('Medicine')

    @property
    def quantity_remaining(self):
        return self.quantity_requested - self.quantity_fulfilled


class ReferralFulfilment(db.Model):
    """Record of fulfilment action by receiving pharmacy"""
    __tablename__ = 'referral_fulfilments'

    id = db.Column(db.Integer, primary_key=True)
    referral_id = db.Column(db.Integer, db.ForeignKey('referrals.id', ondelete='CASCADE'), nullable=False)
    referral_item_id = db.Column(db.Integer, db.ForeignKey('referral_items.id', ondelete='CASCADE'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('medicine_batches.id', ondelete='RESTRICT'), nullable=True)
    
    pharmacist_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    quantity_dispensed = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    referral = db.relationship('Referral', back_populates='fulfilments')
    referral_item = db.relationship('ReferralItem')
    batch = db.relationship('MedicineBatch')
    pharmacist = db.relationship('User', foreign_keys=[pharmacist_id])

