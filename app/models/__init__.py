"""
PharmLink Database Models
=========================
All models imported here so Flask-Migrate can discover them.
"""

from app.models.user import User, Role, Permission, UserRole
from app.models.organisation import Organisation, Facility, Department
from app.models.patient import Patient
from app.models.consultation import Consultation, Diagnosis
from app.models.medicine import Medicine, MedicineCategory, Supplier
from app.models.inventory import MedicineBatch, StockMovement
from app.models.prescription import Prescription, PrescriptionItem
from app.models.dispensing import DispensingRecord, DispensingItem
from app.models.referral import Referral, ReferralItem, ReferralFulfilment
from app.models.payment import Payment, PaymentTransaction
from app.models.notification import Notification
from app.models.audit import AuditLog
from app.models.qr_token import QRToken

__all__ = [
    'User', 'Role', 'Permission', 'UserRole',
    'Organisation', 'Facility', 'Department',
    'Patient',
    'Consultation', 'Diagnosis',
    'Medicine', 'MedicineCategory', 'Supplier',
    'MedicineBatch', 'StockMovement',
    'Prescription', 'PrescriptionItem',
    'DispensingRecord', 'DispensingItem',
    'Referral', 'ReferralItem', 'ReferralFulfilment',
    'Payment', 'PaymentTransaction',
    'Notification',
    'AuditLog',
    'QRToken',
]

