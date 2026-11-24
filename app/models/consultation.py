"""Consultation and Diagnosis models"""
from datetime import datetime
from app.extensions import db


class Consultation(db.Model):
    """Patient consultation record"""
    __tablename__ = 'consultations'

    id = db.Column(db.Integer, primary_key=True)
    consultation_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete='SET NULL'), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True)
    
    # Clinical data
    chief_complaint = db.Column(db.Text, nullable=False)
    symptoms = db.Column(db.Text)
    clinical_notes = db.Column(db.Text)
    examination_findings = db.Column(db.Text)
    treatment_plan = db.Column(db.Text)
    follow_up_date = db.Column(db.Date)
    follow_up_notes = db.Column(db.Text)
    
    # Vitals
    blood_pressure = db.Column(db.String(20))
    pulse_rate = db.Column(db.String(20))
    temperature = db.Column(db.String(10))
    weight = db.Column(db.Numeric(5, 2))
    height = db.Column(db.Numeric(5, 2))
    
    # Status
    status = db.Column(
        db.Enum('open', 'in_progress', 'completed', 'cancelled', name='consultation_status'),
        default='open', nullable=False
    )
    
    consultation_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = db.relationship('Patient', back_populates='consultations')
    doctor = db.relationship('User', foreign_keys=[doctor_id])
    organisation = db.relationship('Organisation')
    department = db.relationship('Department')
    diagnoses = db.relationship('Diagnosis', back_populates='consultation',
                                 lazy='dynamic', cascade='all, delete-orphan')
    prescriptions = db.relationship('Prescription', back_populates='consultation', lazy='dynamic')

    @staticmethod
    def generate_number():
        year = datetime.utcnow().year
        last = Consultation.query.filter(
            Consultation.consultation_number.like(f'CON-{year}-%')
        ).order_by(Consultation.id.desc()).first()
        seq = (int(last.consultation_number.split('-')[-1]) + 1) if last else 1
        return f'CON-{year}-{seq:06d}'

    def __repr__(self):
        return f'<Consultation {self.consultation_number}>'


class Diagnosis(db.Model):
    """Diagnosis attached to a consultation"""
    __tablename__ = 'diagnoses'

    id = db.Column(db.Integer, primary_key=True)
    consultation_id = db.Column(db.Integer, db.ForeignKey('consultations.id', ondelete='CASCADE'), nullable=False)
    
    icd_code = db.Column(db.String(20))
    description = db.Column(db.Text, nullable=False)
    diagnosis_type = db.Column(
        db.Enum('primary', 'secondary', 'differential', name='diagnosis_type_enum'),
        default='primary'
    )
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    consultation = db.relationship('Consultation', back_populates='diagnoses')

    def __repr__(self):
        return f'<Diagnosis {self.icd_code}: {self.description[:30]}>'

