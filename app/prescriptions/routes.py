"""Prescription routes"""
from flask import render_template, redirect, url_for, flash, request, abort, jsonify, current_app
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, date, timedelta
import os
import qrcode
from app.prescriptions import bp
from app.extensions import db
from app.models.prescription import Prescription, PrescriptionItem
from app.models.patient import Patient
from app.models.consultation import Consultation
from app.models.medicine import Medicine
from app.models.qr_token import QRToken
from app.models.audit import log_action
from app.models.notification import create_notification


def doctor_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.has_any_role('platform_admin', 'hospital_admin', 'doctor'):
            abort(403)
        return f(*args, **kwargs)
    return login_required(decorated)


def pharmacy_access(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.has_any_role(
            'platform_admin', 'hospital_admin', 'doctor',
            'internal_pharmacist', 'external_pharmacist'
        ):
            abort(403)
        return f(*args, **kwargs)
    return login_required(decorated)


def _generate_qr_image(prescription, token_str):
    """Generate and save QR code image for a prescription."""
    qr_dir = current_app.config['QR_UPLOAD_FOLDER']
    os.makedirs(qr_dir, exist_ok=True)
    
    # The QR code only contains the token - never raw patient data
    qr_url = url_for('prescriptions.scan_qr', token=token_str, _external=True)
    
    img = qrcode.make(qr_url)
    filename = f'qr_{prescription.prescription_number}.png'
    img.save(os.path.join(qr_dir, filename))
    return filename


@bp.route('/')
@pharmacy_access
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    
    org = current_user.primary_organisation
    query = Prescription.query
    
    if not current_user.is_platform_admin():
        if org:
            query = query.filter_by(organisation_id=org.id)
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    if search:
        query = query.join(Patient).filter(
            db.or_(
                Prescription.prescription_number.ilike(f'%{search}%'),
                Patient.first_name.ilike(f'%{search}%'),
                Patient.last_name.ilike(f'%{search}%'),
                Patient.patient_number.ilike(f'%{search}%'),
            )
        )
    
    prescriptions = query.order_by(
        Prescription.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    
    statuses = ['pending', 'issued', 'partially_dispensed', 'fully_dispensed',
                'referred', 'cancelled', 'expired']
    return render_template('prescriptions/index.html', title='Prescriptions',
                           prescriptions=prescriptions, search=search,
                           status_filter=status_filter, statuses=statuses)


@bp.route('/create', methods=['GET', 'POST'])
@doctor_required
def create():
    patient_id = request.args.get('patient_id', type=int)
    consultation_id = request.args.get('consultation_id', type=int)
    patient = Patient.query.get(patient_id) if patient_id else None
    consultation = Consultation.query.get(consultation_id) if consultation_id else None
    
    if request.method == 'POST':
        p_id = request.form.get('patient_id', type=int)
        c_id = request.form.get('consultation_id', type=int)
        patient = Patient.query.get_or_404(p_id)
        
        org = current_user.primary_organisation
        
        # Validity period
        validity_days = int(request.form.get('validity_days', 30))
        expiry = date.today() + timedelta(days=validity_days)
        
        prescription = Prescription(
            prescription_number=Prescription.generate_number(),
            patient_id=patient.id,
            doctor_id=current_user.id,
            consultation_id=c_id or None,
            organisation_id=org.id if org else None,
            prescription_date=date.today(),
            expiry_date=expiry,
            status='issued',
            notes=request.form.get('notes') or None,
        )
        db.session.add(prescription)
        db.session.flush()
        
        # Medicine items
        medicine_ids = request.form.getlist('medicine_id')
        quantities = request.form.getlist('quantity')
        dosages = request.form.getlist('dosage')
        frequencies = request.form.getlist('frequency')
        durations = request.form.getlist('duration')
        instructions_list = request.form.getlist('instructions')
        
        if not medicine_ids:
            flash('At least one medicine is required on a prescription.', 'danger')
            db.session.rollback()
            return redirect(request.url)
        
        for i, med_id in enumerate(medicine_ids):
            if not med_id:
                continue
            med = Medicine.query.get(int(med_id))
            if not med:
                continue
            qty = int(quantities[i]) if i < len(quantities) and quantities[i] else 1
            item = PrescriptionItem(
                prescription_id=prescription.id,
                medicine_id=med.id,
                medicine_name=med.name,
                strength=med.strength,
                dosage_form=med.dosage_form,
                dosage=dosages[i] if i < len(dosages) else None,
                frequency=frequencies[i] if i < len(frequencies) else None,
                duration=durations[i] if i < len(durations) else None,
                quantity=qty,
                quantity_dispensed=0,
                instructions=instructions_list[i] if i < len(instructions_list) else None,
            )
            db.session.add(item)
        
        # Generate QR token
        token_str = QRToken.generate_token()
        qr_token = QRToken(
            token=token_str,
            prescription_id=prescription.id,
            expires_at=datetime.combine(expiry, datetime.min.time()),
            is_active=True,
        )
        db.session.add(qr_token)
        db.session.flush()
        prescription.qr_token_id = qr_token.id
        
        # Generate QR image
        try:
            _generate_qr_image(prescription, token_str)
        except Exception as e:
            current_app.logger.warning(f'QR image generation failed: {e}')
        
        log_action('create_prescription', module='prescriptions',
                   target_type='prescription', target_id=prescription.id,
                   description=f'Prescription {prescription.prescription_number} for {patient.full_name}',
                   user_id=current_user.id,
                   organisation_id=org.id if org else None)
        
        db.session.commit()
        flash(f'Prescription {prescription.prescription_number} created successfully.', 'success')
        return redirect(url_for('prescriptions.view', prescription_id=prescription.id))
    
    # Build medicine list for form
    org = current_user.primary_organisation
    medicines = []
    if org:
        medicines = Medicine.query.filter_by(
            organisation_id=org.id, is_active=True
        ).order_by(Medicine.name).all()
    
    patients = []
    if not patient:
        if org:
            patients = Patient.query.filter_by(
                registered_organisation_id=org.id, is_active=True, deleted_at=None
            ).order_by(Patient.last_name).all()
    
    return render_template('prescriptions/create.html', title='Create Prescription',
                           patient=patient, consultation=consultation,
                           patients=patients, medicines=medicines)


@bp.route('/<int:prescription_id>')
@pharmacy_access
def view(prescription_id):
    prescription = Prescription.query.get_or_404(prescription_id)
    # Check org-level access
    if not current_user.is_platform_admin():
        org = current_user.primary_organisation
        if org and prescription.organisation_id != org.id:
            abort(403)
    
    # Check expiry
    if prescription.is_expired and prescription.status not in ('cancelled', 'expired', 'fully_dispensed'):
        prescription.status = 'expired'
        db.session.commit()
    
    return render_template('prescriptions/view.html',
                           title=f'Prescription {prescription.prescription_number}',
                           prescription=prescription)


@bp.route('/qr/<string:token>')
@login_required
def scan_qr(token):
    """QR code scan endpoint - validates and redirects to prescription"""
    qr_token = QRToken.query.filter_by(token=token).first_or_404()
    
    if not qr_token.is_valid:
        flash('This QR code is no longer valid.', 'danger')
        return redirect(url_for('prescriptions.index'))
    
    prescription = qr_token.prescription
    if not prescription:
        flash('Prescription not found.', 'danger')
        return redirect(url_for('prescriptions.index'))
    
    if prescription.status in ('cancelled', 'expired', 'fully_dispensed'):
        flash(f'Prescription is {prescription.status.replace("_", " ")} and cannot be processed.', 'warning')
        return redirect(url_for('prescriptions.view', prescription_id=prescription.id))
    
    # Record scan
    qr_token.record_scan(user_id=current_user.id, ip_address=request.remote_addr)
    db.session.commit()
    
    flash(f'QR code verified. Prescription {prescription.prescription_number} loaded.', 'success')
    return redirect(url_for('prescriptions.view', prescription_id=prescription.id))


@bp.route('/<int:prescription_id>/cancel', methods=['POST'])
@doctor_required
def cancel(prescription_id):
    prescription = Prescription.query.get_or_404(prescription_id)
    if prescription.status == 'fully_dispensed':
        flash('Cannot cancel a fully dispensed prescription.', 'danger')
        return redirect(url_for('prescriptions.view', prescription_id=prescription.id))
    
    reason = request.form.get('reason', '').strip()
    prescription.status = 'cancelled'
    prescription.cancelled_reason = reason
    prescription.cancelled_by_id = current_user.id
    prescription.cancelled_at = datetime.utcnow()
    
    if prescription.qr_token_id:
        prescription.qr_token.is_active = False
    
    log_action('cancel_prescription', module='prescriptions',
               target_type='prescription', target_id=prescription.id,
               description=f'Cancelled: {reason}', user_id=current_user.id)
    db.session.commit()
    flash('Prescription cancelled.', 'info')
    return redirect(url_for('prescriptions.view', prescription_id=prescription.id))


@bp.route('/api/search-patient')
@login_required
def api_search_patient():
    """AJAX patient search"""
    q = request.args.get('q', '').strip()
    org = current_user.primary_organisation
    
    query = Patient.query.filter(
        Patient.deleted_at == None,
        Patient.is_active == True,
    )
    if org and not current_user.is_platform_admin():
        query = query.filter_by(registered_organisation_id=org.id)
    if q:
        query = query.filter(
            db.or_(
                Patient.first_name.ilike(f'%{q}%'),
                Patient.last_name.ilike(f'%{q}%'),
                Patient.patient_number.ilike(f'%{q}%'),
            )
        )
    patients = query.limit(10).all()
    return jsonify([{
        'id': p.id,
        'name': p.full_name,
        'number': p.patient_number,
        'dob': str(p.date_of_birth) if p.date_of_birth else '',
    } for p in patients])

