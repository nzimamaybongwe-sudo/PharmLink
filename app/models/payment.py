"""Payment and PaymentTransaction models"""
from datetime import datetime
from app.extensions import db


class Payment(db.Model):
    """Payment record for a prescription or referral"""
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    payment_reference = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # What is being paid for?
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id', ondelete='SET NULL'), nullable=True)
    referral_id = db.Column(db.Integer, db.ForeignKey('referrals.id', ondelete='SET NULL'), nullable=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='SET NULL'), nullable=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete='SET NULL'), nullable=True)
    
    # Amounts
    amount_due = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    amount_paid = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    currency = db.Column(db.String(10), default='SZL')
    
    # Funding
    funding_type = db.Column(
        db.Enum('patient_funded', 'government_funded', 'insurance', 'other', name='payment_funding_type'),
        default='patient_funded'
    )
    funding_reference = db.Column(db.String(100))
    approved_amount = db.Column(db.Numeric(12, 2))
    
    status = db.Column(
        db.Enum('pending', 'approved', 'rejected', 'paid', 'partially_paid', name='payment_status'),
        default='pending', nullable=False
    )
    
    notes = db.Column(db.Text)
    recorded_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    prescription = db.relationship('Prescription')
    referral = db.relationship('Referral')
    patient = db.relationship('Patient')
    organisation = db.relationship('Organisation')
    recorded_by = db.relationship('User', foreign_keys=[recorded_by_id])
    transactions = db.relationship('PaymentTransaction', back_populates='payment',
                                    lazy='dynamic', cascade='all, delete-orphan')

    @staticmethod
    def generate_reference():
        year = datetime.utcnow().year
        last = Payment.query.filter(
            Payment.payment_reference.like(f'PAY-{year}-%')
        ).order_by(Payment.id.desc()).first()
        seq = (int(last.payment_reference.split('-')[-1]) + 1) if last else 1
        return f'PAY-{year}-{seq:06d}'


class PaymentTransaction(db.Model):
    """Individual payment transactions (e.g. partial payments)"""
    __tablename__ = 'payment_transactions'

    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id', ondelete='CASCADE'), nullable=False)
    
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    payment_method = db.Column(db.String(50))  # cash, mobile_money, card, etc.
    transaction_reference = db.Column(db.String(100))
    notes = db.Column(db.Text)
    
    recorded_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)

    payment = db.relationship('Payment', back_populates='transactions')
    recorded_by = db.relationship('User', foreign_keys=[recorded_by_id])

