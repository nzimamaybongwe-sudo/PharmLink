"""Consultation routes"""
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, date
from app.consultations import bp
from app.extensions import db
from app.models.consultation import Consultation, Diagnosis
from app.models.patient import Patient
from app.models.organisation import Department
from app.models.audit import log_action


def doctor_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.has_any_role('platform_admin', 'hospital_admin', 'doctor'):
            abort(403)
        return f(*args, **kwargs)
    return login_required(decorated)


@bp.route('/dashboard')
@doctor_required
def dashboard():
    org = current_user.primary_organisation
    org_id = org.id if org else None
    
    stats = {
        'my_consultations_today': Consultation.query.filter(
            Consultation.doctor_id == current_user.id,
            db.func.date(Consultation.consultation_date) == date.today()
        ).count(),
        'my_consultations_total': Consultation.query.filter_by(
            doctor_id=current_user.id
        ).count(),
        'open_consultations': Consultation.query.filter_by(
            doctor_id=current_user.id, status='open'
        ).count(),
    }
    recent = Consultation.query.filter_by(
        doctor_id=current_user.id
    ).order_by(Consultation.consultation_date.desc()).limit(10).all()
    return render_template('consultations/dashboard.html', title='Doctor Dashboard',
                           stats=stats, recent=recent)


@bp.route('/')
@doctor_required
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    
    org = current_user.primary_organisation
    query = Consultation.query
    
    if not current_user.is_platform_admin():
        if org:
            query = query.filter_by(organisation_id=org.id)
        if current_user.is_doctor():
            query = query.filter_by(doctor_id=current_user.id)
    
    if search:
        query = query.join(Patient).filter(
            db.or_(
                Patient.first_name.ilike(f'%{search}%'),
                Patient.last_name.ilike(f'%{search}%'),
                Consultation.consultation_number.ilike(f'%{search}%'),
            )
        )
    
    consultations = query.order_by(
        Consultation.consultation_date.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    return render_template('consultations/index.html', title='Consultations',
                           consultations=consultations, search=search)


@bp.route('/new', methods=['GET', 'POST'])
@doctor_required
def new_consultation():
    patient_id = request.args.get('patient_id', type=int)
    patient = Patient.query.get_or_404(patient_id) if patient_id else None
    
    if request.method == 'POST':
        p_id = request.form.get('patient_id', type=int)
        patient = Patient.query.get_or_404(p_id)
        
        org = current_user.primary_organisation
        
        consultation = Consultation(
            consultation_number=Consultation.generate_number(),
            patient_id=patient.id,
            doctor_id=current_user.id,
            organisation_id=org.id if org else None,
            department_id=request.form.get('department_id', type=int),
            chief_complaint=request.form.get('chief_complaint', '').strip(),
            symptoms=request.form.get('symptoms') or None,
            clinical_notes=request.form.get('clinical_notes') or None,
            examination_findings=request.form.get('examination_findings') or None,
            treatment_plan=request.form.get('treatment_plan') or None,
            blood_pressure=request.form.get('blood_pressure') or None,
            pulse_rate=request.form.get('pulse_rate') or None,
            temperature=request.form.get('temperature') or None,
            weight=request.form.get('weight', type=float),
            height=request.form.get('height', type=float),
            status='in_progress',
            consultation_date=datetime.utcnow(),
        )
        
        if not consultation.chief_complaint:
            flash('Chief complaint is required.', 'danger')
            return render_template('consultations/new.html', patient=patient)
        
        db.session.add(consultation)
        db.session.flush()
        
        # Save diagnoses
        diagnoses_desc = request.form.getlist('diagnosis_description')
        diagnoses_code = request.form.getlist('diagnosis_code')
        diagnoses_type = request.form.getlist('diagnosis_type')
        for i, desc in enumerate(diagnoses_desc):
            if desc.strip():
                diag = Diagnosis(
                    consultation_id=consultation.id,
                    icd_code=diagnoses_code[i] if i < len(diagnoses_code) else None,
                    description=desc.strip(),
                    diagnosis_type=diagnoses_type[i] if i < len(diagnoses_type) else 'primary',
                )
                db.session.add(diag)
        
        log_action('create_consultation', module='consultations',
                   target_type='consultation', target_id=consultation.id,
                   description=f'Consultation {consultation.consultation_number} for {patient.full_name}',
                   user_id=current_user.id,
                   organisation_id=org.id if org else None)
        db.session.commit()
        flash(f'Consultation {consultation.consultation_number} recorded.', 'success')
        return redirect(url_for('consultations.view', consultation_id=consultation.id))
    
    org = current_user.primary_organisation
    departments = []
    if org:
        departments = Department.query.filter_by(organisation_id=org.id, is_active=True).all()
    
    # Build patient list for dropdown if no patient pre-selected
    patients = []
    if not patient:
        org = current_user.primary_organisation
        if org:
            patients = Patient.query.filter_by(
                registered_organisation_id=org.id, deleted_at=None, is_active=True
            ).order_by(Patient.last_name).all()
    
    return render_template('consultations/new.html', title='New Consultation',
                           patient=patient, patients=patients, departments=departments)


@bp.route('/<int:consultation_id>')
@doctor_required
def view(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    return render_template('consultations/view.html',
                           title=f'Consultation {consultation.consultation_number}',
                           consultation=consultation)


@bp.route('/<int:consultation_id>/complete', methods=['POST'])
@doctor_required
def complete(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    if consultation.doctor_id != current_user.id and not current_user.is_platform_admin():
        abort(403)
    consultation.status = 'completed'
    db.session.commit()
    flash('Consultation marked as completed.', 'success')
    return redirect(url_for('consultations.view', consultation_id=consultation.id))

