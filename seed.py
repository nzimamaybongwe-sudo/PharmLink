"""
PharmLink Database Seed Script
=============================
Creates default roles, pilot hospital, internal pharmacy, departments,
dummy staff accounts, medicine categories, sample medicines, and batches.

Usage:
    python seed.py
"""
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.extensions import db
from app.models.user import User, Role, UserRole
from app.models.organisation import Organisation, Department
from app.models.patient import Patient
from app.models.medicine import Medicine, MedicineCategory, Supplier
from app.models.inventory import MedicineBatch, StockMovement


ROLES = [
    ('platform_admin', 'Platform Administrator', 'Manages the overall PharmLink platform and organisations'),
    ('hospital_admin', 'Hospital Administrator', 'Manages hospital staff, departments, and operations'),
    ('doctor', 'Doctor / Medical Practitioner', 'Conducts consultations and issues prescriptions'),
    ('internal_pharmacist', 'Internal Pharmacist', 'Dispenses medicines and manages hospital pharmacy'),
    ('external_pharmacist', 'External Pharmacist', 'Fulfils authorised referrals at registered pharmacies'),
    ('inventory_officer', 'Inventory Officer', 'Manages medicine stock, batches, and expiry tracking'),
    ('finance_officer', 'Finance Officer', 'Manages billing, payments, and government-funded referrals'),
    ('patient', 'Patient', 'Views personal profile, prescriptions, and QR codes'),
]

CATEGORIES = [
    ('Antibiotics', 'Antibacterial and antimicrobial medications'),
    ('Analgesics', 'Pain relief and anti-inflammatory medications'),
    ('Antihypertensives', 'Blood pressure management medications'),
    ('Antidiabetics', 'Blood glucose management medications'),
    ('Antiretrovirals', 'HIV/AIDS antiretroviral therapy'),
    ('Respiratory', 'Asthma and respiratory tract medications'),
]


def seed():
    app = create_app()
    with app.app_context():
        db.create_all()

        # 1. Roles
        role_map = {}
        for name, display, desc in ROLES:
            role = Role.query.filter_by(name=name).first()
            if not role:
                role = Role(name=name, display_name=display, description=desc)
                db.session.add(role)
            role_map[name] = role
        db.session.flush()

        # 2. Pilot Hospital & Internal Pharmacy
        hospital = Organisation.query.filter_by(registration_number='HOSP-SZ-001').first()
        if not hospital:
            hospital = Organisation(
                name='Mbabane Pilot Hospital',
                org_type='hospital',
                registration_number='HOSP-SZ-001',
                licence_number='LIC-MOH-001',
                email='info@mbabanepilot.sz',
                phone='+268 2404 0000',
                physical_address='Hospital Hill, Mbabane',
                town='Mbabane',
                region='Hhohho',
                country='Eswatini',
                is_active=True,
                is_verified=True,
            )
            db.session.add(hospital)
            db.session.flush()

        internal_pharm = Organisation.query.filter_by(registration_number='PHARM-INT-001').first()
        if not internal_pharm:
            internal_pharm = Organisation(
                name='Mbabane Pilot Hospital Pharmacy',
                org_type='internal_pharmacy',
                registration_number='PHARM-INT-001',
                licence_number='LIC-PHARM-001',
                parent_id=hospital.id,
                town='Mbabane',
                region='Hhohho',
                country='Eswatini',
                is_active=True,
                is_verified=True,
            )
            db.session.add(internal_pharm)
            db.session.flush()

        # 3. Departments
        for dept_name, code in [('Outpatient Department', 'OPD'), ('General Medicine', 'MED'), ('Paediatrics', 'PAED')]:
            if not Department.query.filter_by(organisation_id=hospital.id, code=code).first():
                db.session.add(Department(organisation_id=hospital.id, name=dept_name, code=code))

        # 4. Dummy Pilot Users (for testing only)
        users_spec = [
            ('Platform', 'Admin', 'platform@pharmlink.sz', 'platform_admin', None, 'System Administrator'),
            ('Hospital', 'Admin', 'admin@mbabanepilot.sz', 'hospital_admin', hospital.id, 'Hospital Administrator'),
            ('Sipho', 'Dlamini', 'doctor@mbabanepilot.sz', 'doctor', hospital.id, 'Medical Officer'),
            ('Nomsa', 'Nkosi', 'pharmacist@mbabanepilot.sz', 'internal_pharmacist', hospital.id, 'Senior Pharmacist'),
            ('Thabo', 'Mamba', 'inventory@mbabanepilot.sz', 'inventory_officer', hospital.id, 'Inventory Officer'),
            ('Lindiwe', 'Simelane', 'finance@mbabanepilot.sz', 'finance_officer', hospital.id, 'Finance Officer'),
        ]

        for first, last, email, role_name, org_id, prof in users_spec:
            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(
                    first_name=first,
                    last_name=last,
                    email=email,
                    profession=prof,
                    primary_organisation_id=org_id,
                    is_active=True,
                    is_verified=True,
                )
                user.set_password('PharmLink@123')
                db.session.add(user)
                db.session.flush()
                db.session.add(UserRole(
                    user_id=user.id,
                    role_id=role_map[role_name].id,
                    organisation_id=org_id,
                ))

        # 5. Categories
        cat_map = {}
        for cname, cdesc in CATEGORIES:
            cat = MedicineCategory.query.filter_by(name=cname).first()
            if not cat:
                cat = MedicineCategory(name=cname, description=cdesc)
                db.session.add(cat)
            cat_map[cname] = cat
        db.session.flush()

        # 6. Supplier
        supplier = Supplier.query.filter_by(name='Eswatini Central Medical Stores').first()
        if not supplier:
            supplier = Supplier(
                name='Eswatini Central Medical Stores',
                contact_person='Supply Desk',
                email='cms@health.sz',
                phone='+268 2518 0000',
                address='Matsapha Industrial Site',
            )
            db.session.add(supplier)
            db.session.flush()

        # 7. Sample Medicines & Batches
        medicines_spec = [
            ('MED-00001', 'Amoxicillin', 'Amoxicillin Trihydrate', 'Antibiotics', '500mg', 'Capsule', 'capsule', 50, 'BATCH-AMX-01', 500, 365),
            ('MED-00002', 'Paracetamol', 'Acetaminophen', 'Analgesics', '500mg', 'Tablet', 'tablet', 100, 'BATCH-PCM-01', 1000, 540),
            ('MED-00003', 'Metformin', 'Metformin Hydrochloride', 'Antidiabetics', '850mg', 'Tablet', 'tablet', 40, 'BATCH-MET-01', 300, 270),
            ('MED-00004', 'Amlodipine', 'Amlodipine Besylate', 'Antihypertensives', '5mg', 'Tablet', 'tablet', 30, 'BATCH-AML-01', 250, 400),
        ]
        for code, name, generic, cat_name, strength, form, unit, reorder, batch_no, qty, exp_days in medicines_spec:
            med = Medicine.query.filter_by(medicine_code=code).first()
            if not med:
                med = Medicine(
                    medicine_code=code,
                    name=name,
                    generic_name=generic,
                    category_id=cat_map[cat_name].id,
                    strength=strength,
                    dosage_form=form,
                    unit_of_measurement=unit,
                    reorder_level=reorder,
                    organisation_id=hospital.id,
                )
                db.session.add(med)
                db.session.flush()

                batch = MedicineBatch(
                    medicine_id=med.id,
                    organisation_id=hospital.id,
                    batch_number=batch_no,
                    quantity_received=qty,
                    quantity_remaining=qty,
                    expiry_date=date.today() + timedelta(days=exp_days),
                    supplier_id=supplier.id,
                    date_received=date.today(),
                )
                db.session.add(batch)
                db.session.flush()

                db.session.add(StockMovement(
                    batch_id=batch.id,
                    medicine_id=med.id,
                    organisation_id=hospital.id,
                    movement_type='received',
                    quantity=qty,
                    quantity_before=0,
                    quantity_after=qty,
                    reference_type='seed',
                    notes='Initial pilot seed stock',
                ))

        # 8. Sample Dummy Patient
        if not Patient.query.filter_by(patient_number='PL-2026-00001').first():
            db.session.add(Patient(
                patient_number='PL-2026-00001',
                first_name='Test',
                last_name='Patient',
                date_of_birth=date(1990, 5, 15),
                gender='female',
                phone='+268 7600 0001',
                town='Mbabane',
                region='Hhohho',
                registered_organisation_id=hospital.id,
            ))

        db.session.commit()
        print('Seed completed successfully.')


if __name__ == '__main__':
    seed()
