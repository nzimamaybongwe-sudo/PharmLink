"""Patient routes"""
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
from app.patients import bp
from app.extensions import db
from app.models.patient import Patient
from app.models.audit import log_action


def clinical_required(f):
    """Doctors, admins, pharmacists can access patients."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.has_any_role(
            'platform_admin', 'hospital_admin', 'doctor',
            'internal_pharmacist', 'external_pharmacist'
        ):
            abort(403)
        return f(*args, **kwargs)
    return login_required(decorated)


@bp.route('/')
@clinical_required
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    
    query = Patient.query.filter_by(deleted_at=None, is_active=True)
    
    # Scope to organisation for non-platform admins
    if not current_user.is_platform_admin():
        org = current_user.primary_organisation
        if org:
            query = query.filter_by(registered_organisation_id=org.id)
    
    if search:
        query = query.filter(
            db.or_(
                Patient.first_name.ilike(f'%{search}%'),
                Patient.last_name.ilike(f'%{search}%'),
                Patient.patient_number.ilike(f'%{search}%'),
                Patient.national_id.ilike(f'%{search}%'),
                Patient.phone.ilike(f'%{search}%'),
            )
        )
    
    patients = query.order_by(Patient.last_name).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template('patients/index.html', title='Patients',
                           patients=patients, search=search)


@bp.route('/register', methods=['GET', 'POST'])
@clinical_required
def register():
    if request.method == 'POST':
        # Validate required fields
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        if not first_name or not last_name:
            flash('First name and last name are required.', 'danger')
            return render_template('patients/register.html', title='Register Patient')
        
        org = current_user.primary_organisation
        
        patient = Patient(
            patient_number=Patient.generate_patient_number(),
            first_name=first_name,
            last_name=last_name,
            date_of_birth=datetime.strptime(request.form['date_of_birth'], '%Y-%m-%d').date()
                if request.form.get('date_of_birth') else None,
            gender=request.form.get('gender') or None,
            national_id=request.form.get('national_id') or None,
            phone=request.form.get('phone') or None,
            email=request.form.get('email') or None,
            physical_address=request.form.get('physical_address') or None,
            town=request.form.get('town') or None,
            region=request.form.get('region') or None,
            emergency_name=request.form.get('emergency_name') or None,
            emergency_phone=request.form.get('emergency_phone') or None,
            emergency_relationship=request.form.get('emergency_relationship') or None,
            blood_type=request.form.get('blood_type') or None,
            allergies=request.form.get('allergies') or None,
            chronic_conditions=request.form.get('chronic_conditions') or None,
            registered_organisation_id=org.id if org else None,
            registered_by_id=current_user.id,
        )
        db.session.add(patient)
        log_action('register_patient', module='patients', target_type='patient',
                   description=f'Registered patient: {patient.full_name}',
                   user_id=current_user.id,
                   organisation_id=org.id if org else None)
        db.session.commit()
        flash(f'Patient {patient.full_name} registered. Number: {patient.patient_number}', 'success')
        return redirect(url_for('patients.view', patient_id=patient.id))
    return render_template('patients/register.html', title='Register Patient')


@bp.route('/<int:patient_id>')
@clinical_required
def view(patient_id):
    patient = Patient.query.filter_by(id=patient_id, deleted_at=None).first_or_404()
    
    # Org-level access check
    if not current_user.is_platform_admin():
        org = current_user.primary_organisation
        if org and patient.registered_organisation_id != org.id:
            abort(403)
    
    consultations = patient.consultations.order_by(
        db.text('consultation_date DESC')
    ).limit(10).all()
    prescriptions = patient.prescriptions.order_by(
        db.text('prescription_date DESC')
    ).limit(10).all()
    return render_template('patients/view.html', title=patient.full_name,
                           patient=patient, consultations=consultations,
                           prescriptions=prescriptions)


@bp.route('/<int:patient_id>/edit', methods=['GET', 'POST'])
@clinical_required
def edit(patient_id):
    patient = Patient.query.filter_by(id=patient_id, deleted_at=None).first_or_404()
    if not current_user.is_platform_admin():
        org = current_user.primary_organisation
        if org and patient.registered_organisation_id != org.id:
            abort(403)
    
    if request.method == 'POST':
        patient.first_name = request.form.get('first_name', patient.first_name).strip()
        patient.last_name = request.form.get('last_name', patient.last_name).strip()
        if request.form.get('date_of_birth'):
            patient.date_of_birth = datetime.strptime(request.form['date_of_birth'], '%Y-%m-%d').date()
        patient.gender = request.form.get('gender') or patient.gender
        patient.national_id = request.form.get('national_id') or patient.national_id
        patient.phone = request.form.get('phone') or patient.phone
        patient.email = request.form.get('email') or patient.email
        patient.physical_address = request.form.get('physical_address') or patient.physical_address
        patient.town = request.form.get('town') or patient.town
        patient.emergency_name = request.form.get('emergency_name') or patient.emergency_name
        patient.emergency_phone = request.form.get('emergency_phone') or patient.emergency_phone
        patient.blood_type = request.form.get('blood_type') or patient.blood_type
        patient.allergies = request.form.get('allergies') or patient.allergies
        patient.chronic_conditions = request.form.get('chronic_conditions') or patient.chronic_conditions
        patient.updated_at = datetime.utcnow()
        log_action('update_patient', module='patients', target_type='patient',
                   target_id=patient.id, user_id=current_user.id)
        db.session.commit()
        flash('Patient record updated.', 'success')
        return redirect(url_for('patients.view', patient_id=patient.id))
    return render_template('patients/edit.html', title='Edit Patient', patient=patient)


@bp.route('/my-profile')
@login_required
def my_profile():
    """Patient views their own profile"""
    if not current_user.has_role('patient'):
        abort(403)
    patient = Patient.query.filter_by(user_id=current_user.id, deleted_at=None).first_or_404()
    prescriptions = patient.prescriptions.order_by(
        db.text('prescription_date DESC')
    ).limit(10).all()
    return render_template('patients/my_profile.html', title='My Profile',
                           patient=patient, prescriptions=prescriptions)

