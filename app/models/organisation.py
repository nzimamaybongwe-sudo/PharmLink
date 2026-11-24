"""Organisation and Facility models"""
from datetime import datetime
from app.extensions import db


class Organisation(db.Model):
    """Hospital, pharmacy, or other healthcare organisation"""
    __tablename__ = 'organisations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    org_type = db.Column(
        db.Enum('hospital', 'internal_pharmacy', 'community_pharmacy',
                'private_pharmacy', 'public_facility', name='org_type_enum'),
        nullable=False
    )
    registration_number = db.Column(db.String(100), unique=True)
    licence_number = db.Column(db.String(100))
    
    # Contact
    email = db.Column(db.String(255))
    phone = db.Column(db.String(20))
    website = db.Column(db.String(255))
    
    # Location
    physical_address = db.Column(db.Text)
    town = db.Column(db.String(100))
    region = db.Column(db.String(100))
    country = db.Column(db.String(100), default='Eswatini')
    gps_coordinates = db.Column(db.String(100))
    
    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    
    # Parent organisation (e.g. internal pharmacy belongs to a hospital)
    parent_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete='SET NULL'), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)

    # Relationships
    parent = db.relationship('Organisation', remote_side=[id], backref='children')
    facilities = db.relationship('Facility', back_populates='organisation',
                                  lazy='dynamic', cascade='all, delete-orphan')
    departments = db.relationship('Department', back_populates='organisation',
                                   lazy='dynamic', cascade='all, delete-orphan')

    @property
    def org_type_display(self):
        types = {
            'hospital': 'Hospital',
            'internal_pharmacy': 'Internal Pharmacy',
            'community_pharmacy': 'Community Pharmacy',
            'private_pharmacy': 'Private Pharmacy',
            'public_facility': 'Public Healthcare Facility',
        }
        return types.get(self.org_type, self.org_type)

    def __repr__(self):
        return f'<Organisation {self.name}>'


class Facility(db.Model):
    """A physical facility within an organisation (e.g. ward, clinic)"""
    __tablename__ = 'facilities'

    id = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    facility_type = db.Column(db.String(100))
    location = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organisation = db.relationship('Organisation', back_populates='facilities')

    def __repr__(self):
        return f'<Facility {self.name}>'


class Department(db.Model):
    """Hospital department"""
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(20))
    description = db.Column(db.Text)
    head_of_department_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organisation = db.relationship('Organisation', back_populates='departments')
    head = db.relationship('User', foreign_keys=[head_of_department_id])

    def __repr__(self):
        return f'<Department {self.name}>'

