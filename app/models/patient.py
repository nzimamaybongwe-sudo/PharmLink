"""Patient model"""
import uuid
from datetime import datetime, date
from app.extensions import db


class Patient(db.Model):
    """Patient record"""
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True)
    patient_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    
    # Personal
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.Enum('male', 'female', 'other', name='gender_enum'))
    national_id = db.Column(db.String(50), unique=True)
    
    # Contact
    phone = db.Column(db.String(20))
    email = db.Column(db.String(255))
    physical_address = db.Column(db.Text)
    town = db.Column(db.String(100))
    region = db.Column(db.String(100))
    
    # Emergency contact
    emergency_name = db.Column(db.String(200))
    emergency_phone = db.Column(db.String(20))
    emergency_relationship = db.Column(db.String(50))
    
    # Medical info
    blood_type = db.Column(db.String(5))
    allergies = db.Column(db.Text)
    chronic_conditions = db.Column(db.Text)
    
    # Organisation context
    registered_organisation_id = db.Column(
        db.Integer, db.ForeignKey('organisations.id', ondelete='SET NULL'), nullable=True
    )
    registered_by_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    
    # Linked user account (optional)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)

    # Relationships
    registered_organisation = db.relationship('Organisation', foreign_keys=[registered_organisation_id])
    registered_by = db.relationship('User', foreign_keys=[registered_by_id])
    user_account = db.relationship('User', foreign_keys=[user_id])
    consultations = db.relationship('Consultation', back_populates='patient',
                                     lazy='dynamic', cascade='all, delete-orphan')
    prescriptions = db.relationship('Prescription', back_populates='patient',
                                     lazy='dynamic', cascade='all, delete-orphan')

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def age(self):
        if self.date_of_birth:
            today = date.today()
            dob = self.date_of_birth
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return None

    @staticmethod
    def generate_patient_number():
        """Generate a unique patient number like PL-2026-00001"""
        year = datetime.utcnow().year
        last = Patient.query.filter(
            Patient.patient_number.like(f'PL-{year}-%')
        ).order_by(Patient.id.desc()).first()
        if last:
            seq = int(last.patient_number.split('-')[-1]) + 1
        else:
            seq = 1
        return f'PL-{year}-{seq:05d}'

    def __repr__(self):
        return f'<Patient {self.patient_number}: {self.full_name}>'

