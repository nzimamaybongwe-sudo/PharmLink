"""PharmLink Automated Test Suite"""
import unittest
from datetime import date, timedelta
from app import create_app
from app.extensions import db
from app.models.user import User, Role, UserRole
from app.models.organisation import Organisation
from app.models.patient import Patient
from app.models.consultation import Consultation
from app.models.medicine import Medicine, MedicineCategory
from app.models.inventory import MedicineBatch, StockMovement
from app.models.prescription import Prescription, PrescriptionItem
from app.models.qr_token import QRToken
from app.models.referral import Referral, ReferralItem
from app.models.payment import Payment
from app.models.audit import AuditLog


class PharmLinkTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()
        self._seed_test_data()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _seed_test_data(self):
        # Roles
        for name, disp in [
            ('platform_admin', 'Platform Admin'),
            ('hospital_admin', 'Hospital Admin'),
            ('doctor', 'Doctor'),
            ('internal_pharmacist', 'Internal Pharmacist'),
            ('inventory_officer', 'Inventory Officer'),
            ('finance_officer', 'Finance Officer'),
            ('patient', 'Patient'),
        ]:
            db.session.add(Role(name=name, display_name=disp))
        db.session.flush()

        # Organisations
        self.org1 = Organisation(name='Hospital A', org_type='hospital', registration_number='H-001')
        self.org2 = Organisation(name='Hospital B', org_type='hospital', registration_number='H-002')
        db.session.add_all([self.org1, self.org2])
        db.session.flush()

        # Users
        self.doctor = User(first_name='Doc', last_name='One', email='doc@test.sz',
                           primary_organisation_id=self.org1.id, is_active=True)
        self.doctor.set_password('Password123!')
        self.pharmacist = User(first_name='Pharm', last_name='One', email='pharm@test.sz',
                               primary_organisation_id=self.org1.id, is_active=True)
        self.pharmacist.set_password('Password123!')
        self.other_doc = User(first_name='Doc', last_name='Two', email='doc2@test.sz',
                              primary_organisation_id=self.org2.id, is_active=True)
        self.other_doc.set_password('Password123!')
        db.session.add_all([self.doctor, self.pharmacist, self.other_doc])
        db.session.flush()

        doc_role = Role.query.filter_by(name='doctor').first()
        pharm_role = Role.query.filter_by(name='internal_pharmacist').first()
        db.session.add_all([
            UserRole(user_id=self.doctor.id, role_id=doc_role.id, organisation_id=self.org1.id),
            UserRole(user_id=self.pharmacist.id, role_id=pharm_role.id, organisation_id=self.org1.id),
            UserRole(user_id=self.other_doc.id, role_id=doc_role.id, organisation_id=self.org2.id),
        ])

        # Patient in org1
        self.patient = Patient(
            patient_number='PL-2026-00001', first_name='Jane', last_name='Doe',
            registered_organisation_id=self.org1.id, registered_by_id=self.doctor.id
        )
        db.session.add(self.patient)

        # Medicine & Batches (one expired, one near-expiry FEFO, one later expiry)
        cat = MedicineCategory(name='Antibiotics')
        db.session.add(cat)
        db.session.flush()

        self.med = Medicine(
            medicine_code='MED-00001', name='Amoxicillin', strength='500mg',
            dosage_form='Capsule', category_id=cat.id, organisation_id=self.org1.id
        )
        db.session.add(self.med)
        db.session.flush()

        self.expired_batch = MedicineBatch(
            medicine_id=self.med.id, organisation_id=self.org1.id,
            batch_number='EXP-01', quantity_received=50, quantity_remaining=50,
            expiry_date=date.today() - timedelta(days=5),
        )
        self.fefo_batch = MedicineBatch(
            medicine_id=self.med.id, organisation_id=self.org1.id,
            batch_number='FEFO-01', quantity_received=20, quantity_remaining=20,
            expiry_date=date.today() + timedelta(days=30),
        )
        self.later_batch = MedicineBatch(
            medicine_id=self.med.id, organisation_id=self.org1.id,
            batch_number='LATER-01', quantity_received=100, quantity_remaining=100,
            expiry_date=date.today() + timedelta(days=365),
        )
        db.session.add_all([self.expired_batch, self.fefo_batch, self.later_batch])
        db.session.commit()

    def _login(self, email, password='Password123!'):
        return self.client.post('/auth/login', data={
            'email': email, 'password': password
        }, follow_redirects=True)

    def test_password_hashing_and_login(self):
        self.assertTrue(self.doctor.check_password('Password123!'))
        self.assertFalse(self.doctor.check_password('wrong'))
        resp = self._login('doc@test.sz')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Doctor Dashboard', resp.data)
        self.assertIsNotNone(AuditLog.query.filter_by(action='login', user_id=self.doctor.id).first())

    def test_rbac_blocks_unauthorised_roles(self):
        self._login('doc@test.sz')
        # Doctor cannot access admin users or finance dashboard
        self.assertEqual(self.client.get('/admin/users').status_code, 403)
        self.assertEqual(self.client.get('/finance/dashboard').status_code, 403)

    def test_organisation_isolation(self):
        self._login('doc2@test.sz')
        resp = self.client.get(f'/patients/{self.patient.id}')
        self.assertEqual(resp.status_code, 403)

    def test_stock_excludes_expired_batches(self):
        # 50 expired + 20 fefo + 100 later -> total_stock must be 120
        self.assertEqual(self.med.total_stock, 120)

    def test_prescription_creation_and_qr_token(self):
        self._login('doc@test.sz')
        resp = self.client.post('/prescriptions/create', data={
            'patient_id': self.patient.id,
            'validity_days': 30,
            'medicine_id': [self.med.id],
            'quantity': [30],
            'dosage': ['1 capsule'],
            'frequency': ['3 times daily'],
            'duration': ['10 days'],
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        rx = Prescription.query.first()
        self.assertIsNotNone(rx)
        self.assertEqual(rx.status, 'issued')
        self.assertIsNotNone(rx.qr_token)
        self.assertTrue(rx.qr_token.is_valid)

    def test_partial_dispensing_and_validations(self):
        # Create prescription for 30 units
        rx = Prescription(
            prescription_number='RX-2026-000001',
            patient_id=self.patient.id,
            doctor_id=self.doctor.id,
            organisation_id=self.org1.id,
            prescription_date=date.today(),
            expiry_date=date.today() + timedelta(days=30),
            status='issued',
        )
        db.session.add(rx)
        db.session.flush()
        item = PrescriptionItem(
            prescription_id=rx.id, medicine_id=self.med.id,
            medicine_name=self.med.name, quantity=30, quantity_dispensed=0,
        )
        db.session.add(item)
        db.session.commit()

        self._login('pharm@test.sz')

        # 1. Attempt to dispense expired batch -> rejected
        resp = self.client.post(f'/pharmacy/dispense/{rx.id}', data={
            f'batch_{item.id}': self.expired_batch.id,
            f'qty_{item.id}': 10,
        }, follow_redirects=True)
        self.assertIn(b'expired', resp.data.lower())
        db.session.refresh(item)
        self.assertEqual(item.quantity_dispensed, 0)

        # 2. Attempt to dispense more than batch quantity (25 > 20) -> rejected
        resp = self.client.post(f'/pharmacy/dispense/{rx.id}', data={
            f'batch_{item.id}': self.fefo_batch.id,
            f'qty_{item.id}': 25,
        }, follow_redirects=True)
        self.assertIn(b'insufficient stock', resp.data.lower())

        # 3. Valid partial dispense of 20 from FEFO batch
        resp = self.client.post(f'/pharmacy/dispense/{rx.id}', data={
            f'batch_{item.id}': self.fefo_batch.id,
            f'qty_{item.id}': 20,
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        db.session.refresh(rx)
        db.session.refresh(item)
        db.session.refresh(self.fefo_batch)
        self.assertEqual(item.quantity_dispensed, 20)
        self.assertEqual(item.quantity_remaining, 10)
        self.assertEqual(self.fefo_batch.quantity_remaining, 0)
        self.assertEqual(rx.status, 'partially_dispensed')

        # 4. Complete remaining 10 from later batch
        resp = self.client.post(f'/pharmacy/dispense/{rx.id}', data={
            f'batch_{item.id}': self.later_batch.id,
            f'qty_{item.id}': 10,
        }, follow_redirects=True)
        db.session.refresh(rx)
        self.assertEqual(rx.status, 'fully_dispensed')

        # 5. Attempt to dispense already fully dispensed prescription -> blocked
        resp = self.client.get(f'/pharmacy/dispense/{rx.id}', follow_redirects=True)
        self.assertIn(b'cannot be dispensed', resp.data.lower())

    def test_referral_and_payment_models(self):
        rx = Prescription(
            prescription_number='RX-2026-000002',
            patient_id=self.patient.id,
            doctor_id=self.doctor.id,
            organisation_id=self.org1.id,
            status='issued',
        )
        db.session.add(rx)
        db.session.flush()
        ref = Referral(
            referral_number=Referral.generate_number(),
            prescription_id=rx.id,
            originating_organisation_id=self.org1.id,
            funding_type='government_funded',
            status='sent',
        )
        db.session.add(ref)
        db.session.flush()
        pay = Payment(
            payment_reference=Payment.generate_reference(),
            referral_id=ref.id,
            organisation_id=self.org1.id,
            amount_due=150.00,
            funding_type='government_funded',
            status='pending',
        )
        db.session.add(pay)
        db.session.commit()
        self.assertEqual(ref.funding_type, 'government_funded')
        self.assertEqual(pay.currency, 'SZL')


if __name__ == '__main__':
    unittest.main()
