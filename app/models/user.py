"""User, Role, Permission models"""
import uuid
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login_manager


class Role(db.Model):
    """User roles: platform_admin, hospital_admin, doctor, internal_pharmacist,
    external_pharmacist, inventory_officer, finance_officer, patient"""
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user_roles = db.relationship('UserRole', back_populates='role', lazy='dynamic')
    permissions = db.relationship('Permission', back_populates='role', lazy='dynamic',
                                   cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Role {self.name}>'

    @staticmethod
    def get_by_name(name):
        return Role.query.filter_by(name=name).first()


class Permission(db.Model):
    """Granular permissions assigned to roles"""
    __tablename__ = 'permissions'

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False)
    module = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255))

    role = db.relationship('Role', back_populates='permissions')

    __table_args__ = (
        db.UniqueConstraint('role_id', 'module', 'action', name='uq_permission'),
    )


class UserRole(db.Model):
    """Many-to-many between users and roles, scoped to an organisation"""
    __tablename__ = 'user_roles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete='SET NULL'), nullable=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    user = db.relationship('User', back_populates='user_roles', foreign_keys=[user_id])
    role = db.relationship('Role', back_populates='user_roles')
    organisation = db.relationship('Organisation', foreign_keys=[organisation_id])

    __table_args__ = (
        db.UniqueConstraint('user_id', 'role_id', 'organisation_id', name='uq_user_role_org'),
    )


class User(UserMixin, db.Model):
    """Core user model"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    # Personal info
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(191), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20))
    
    # Auth
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    email_verified_at = db.Column(db.DateTime)
    
    # Organisation context
    primary_organisation_id = db.Column(
        db.Integer, db.ForeignKey('organisations.id', ondelete='SET NULL'), nullable=True
    )
    
    # Profile
    avatar = db.Column(db.String(255))
    profession = db.Column(db.String(100))
    licence_number = db.Column(db.String(100))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)
    last_login_ip = db.Column(db.String(45))
    
    # Soft delete
    deleted_at = db.Column(db.DateTime)

    # Relationships
    user_roles = db.relationship('UserRole', back_populates='user',
                                  foreign_keys='UserRole.user_id', lazy='dynamic',
                                  cascade='all, delete-orphan')
    primary_organisation = db.relationship('Organisation', foreign_keys=[primary_organisation_id])
    notifications = db.relationship('Notification', back_populates='user',
                                     foreign_keys='Notification.user_id', lazy='dynamic',
                                     cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def get_roles(self, organisation_id=None):
        """Get all roles for this user, optionally filtered by organisation."""
        query = self.user_roles.join(Role)
        if organisation_id:
            query = query.filter(UserRole.organisation_id == organisation_id)
        return [ur.role for ur in query.all()]

    def has_role(self, role_name, organisation_id=None):
        """Check if user has a specific role."""
        query = self.user_roles.join(Role).filter(Role.name == role_name)
        if organisation_id:
            query = query.filter(UserRole.organisation_id == organisation_id)
        return query.first() is not None

    def has_any_role(self, *role_names, organisation_id=None):
        """Check if user has any of the given roles."""
        return any(self.has_role(r, organisation_id) for r in role_names)

    @property
    def primary_role(self):
        """Get the most significant role for this user."""
        ur = self.user_roles.join(Role).first()
        return ur.role if ur else None

    @property
    def primary_role_name(self):
        role = self.primary_role
        return role.name if role else 'unknown'

    def is_platform_admin(self):
        return self.has_role('platform_admin')

    def is_hospital_admin(self):
        return self.has_role('hospital_admin')

    def is_doctor(self):
        return self.has_role('doctor')

    def is_pharmacist(self):
        return self.has_any_role('internal_pharmacist', 'external_pharmacist')

    def is_inventory_officer(self):
        return self.has_role('inventory_officer')

    def is_finance_officer(self):
        return self.has_role('finance_officer')

    def is_patient_role(self):
        return self.has_role('patient')

    def __repr__(self):
        return f'<User {self.email}>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

