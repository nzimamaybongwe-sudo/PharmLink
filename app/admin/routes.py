"""Admin routes - platform and hospital admin dashboards and management"""
from flask import render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime, date
from functools import wraps
from app.admin import bp
from app.extensions import db
from app.models.user import User, Role, UserRole
from app.models.organisation import Organisation, Department
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.consultation import Consultation
from app.models.inventory import MedicineBatch
from app.models.medicine import Medicine
from app.models.referral import Referral
from app.models.audit import log_action, AuditLog


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.has_any_role('platform_admin', 'hospital_admin'):
            abort(403)
        return f(*args, **kwargs)
    return login_required(decorated)


def platform_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.has_role('platform_admin'):
            abort(403)
        return f(*args, **kwargs)
    return login_required(decorated)


# ── Platform Admin ─────────────────────────────────────────────────────────────

@bp.route('/platform')
@platform_admin_required
def platform_dashboard():
    stats = {
        'total_organisations': Organisation.query.filter_by(deleted_at=None).count(),
        'hospitals': Organisation.query.filter_by(org_type='hospital', deleted_at=None).count(),
        'pharmacies': Organisation.query.filter(
            Organisation.org_type.in_(['community_pharmacy', 'private_pharmacy', 'internal_pharmacy']),
            Organisation.deleted_at == None
        ).count(),
        'active_users': User.query.filter_by(is_active=True, deleted_at=None).count(),
        'recent_activity': AuditLog.query.order_by(AuditLog.created_at.desc()).limit(15).all(),
    }
    organisations = Organisation.query.filter_by(deleted_at=None).order_by(Organisation.name).all()
    return render_template('admin/platform_dashboard.html',
                           title='Platform Dashboard', stats=stats,
                           organisations=organisations)


@bp.route('/organisations')
@platform_admin_required
def organisations():
    orgs = Organisation.query.filter_by(deleted_at=None).order_by(Organisation.name).all()
    return render_template('admin/organisations.html', title='Organisations', organisations=orgs)


@bp.route('/organisations/create', methods=['GET', 'POST'])
@platform_admin_required
def create_organisation():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        org_type = request.form.get('org_type', '').strip()
        if not name or not org_type:
            flash('Name and type are required.', 'danger')
            return redirect(url_for('admin.create_organisation'))
        
        org = Organisation(
            name=name,
            org_type=org_type,
            registration_number=request.form.get('registration_number') or None,
            licence_number=request.form.get('licence_number') or None,
            email=request.form.get('email') or None,
            phone=request.form.get('phone') or None,
            physical_address=request.form.get('physical_address') or None,
            town=request.form.get('town') or None,
            region=request.form.get('region') or None,
        )
        db.session.add(org)
        log_action('create_organisation', module='admin', target_type='organisation',
                   description=f'Created organisation: {name}', user_id=current_user.id)
        db.session.commit()
        flash(f'Organisation "{name}" created successfully.', 'success')
        return redirect(url_for('admin.organisations'))
    return render_template('admin/create_organisation.html', title='Create Organisation')


# ── Hospital Admin ─────────────────────────────────────────────────────────────

@bp.route('/hospital')
@admin_required
def hospital_dashboard():
    org = current_user.primary_organisation
    if not org and not current_user.is_platform_admin():
        flash('No organisation assigned to your account.', 'warning')
        return redirect(url_for('auth.profile'))
    
    # Get stats scoped to this hospital
    org_id = org.id if org else None
    
    stats = {
        'total_patients': Patient.query.filter_by(
            registered_organisation_id=org_id, deleted_at=None
        ).count() if org_id else Patient.query.count(),
        'total_consultations': Consultation.query.filter_by(
            organisation_id=org_id
        ).count() if org_id else Consultation.query.count(),
        'prescriptions_today': Prescription.query.filter(
            Prescription.organisation_id == org_id,
            db.func.date(Prescription.prescription_date) == date.today()
        ).count() if org_id else 0,
        'pending_prescriptions': Prescription.query.filter_by(
            organisation_id=org_id, status='issued'
        ).count() if org_id else 0,
        'pending_referrals': Referral.query.filter_by(
            originating_organisation_id=org_id, status='sent'
        ).count() if org_id else 0,
    }
    
    # Low stock alert
    if org_id:
        low_stock = db.session.query(Medicine).join(MedicineBatch).filter(
            Medicine.organisation_id == org_id,
            Medicine.is_active == True,
        ).all()
        low_stock = [m for m in low_stock if m.is_low_stock]
    else:
        low_stock = []
    
    recent_prescriptions = Prescription.query.filter_by(
        organisation_id=org_id
    ).order_by(Prescription.created_at.desc()).limit(10).all() if org_id else []
    
    return render_template('admin/hospital_dashboard.html',
                           title='Hospital Dashboard',
                           stats=stats,
                           low_stock=low_stock[:5],
                           recent_prescriptions=recent_prescriptions,
                           organisation=org)


# ── User Management ────────────────────────────────────────────────────────────

@bp.route('/users')
@admin_required
def users():
    org = current_user.primary_organisation
    if current_user.is_platform_admin():
        users_list = User.query.filter_by(deleted_at=None).order_by(User.last_name).all()
    else:
        # Show users in this org only
        org_id = org.id if org else None
        users_list = User.query.join(UserRole, User.id == UserRole.user_id).filter(
            UserRole.organisation_id == org_id,
            User.deleted_at == None,
        ).order_by(User.last_name).distinct().all()
    roles = Role.query.filter_by(is_active=True).all()
    organisations = Organisation.query.filter_by(deleted_at=None).all()
    return render_template('admin/users.html', title='User Management',
                           users=users_list, roles=roles, organisations=organisations)


@bp.route('/users/create', methods=['GET', 'POST'])
@admin_required
def create_user():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if User.query.filter_by(email=email).first():
            flash('A user with that email already exists.', 'danger')
            return redirect(url_for('admin.create_user'))
        
        user = User(
            first_name=request.form.get('first_name', '').strip(),
            last_name=request.form.get('last_name', '').strip(),
            email=email,
            phone=request.form.get('phone') or None,
            profession=request.form.get('profession') or None,
            is_active=True,
            is_verified=True,
        )
        password = request.form.get('password', 'PharmLink@123')
        user.set_password(password)
        
        org_id = request.form.get('organisation_id')
        if org_id:
            user.primary_organisation_id = int(org_id)
        
        db.session.add(user)
        db.session.flush()  # get user.id
        
        role_id = request.form.get('role_id')
        if role_id:
            ur = UserRole(
                user_id=user.id,
                role_id=int(role_id),
                organisation_id=int(org_id) if org_id else None,
                assigned_by=current_user.id,
            )
            db.session.add(ur)
        
        log_action('create_user', module='admin', target_type='user', target_id=user.id,
                   description=f'Created user: {user.email}', user_id=current_user.id)
        db.session.commit()
        flash(f'User {user.full_name} created successfully. Temporary password: {password}', 'success')
        return redirect(url_for('admin.users'))
    
    roles = Role.query.filter_by(is_active=True).all()
    organisations = Organisation.query.filter_by(deleted_at=None).all()
    return render_template('admin/create_user.html', title='Create User',
                           roles=roles, organisations=organisations)


@bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'danger')
        return redirect(url_for('admin.users'))
    user.is_active = not user.is_active
    action = 'activate_user' if user.is_active else 'deactivate_user'
    log_action(action, module='admin', target_type='user', target_id=user.id,
               user_id=current_user.id)
    db.session.commit()
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User {user.full_name} has been {status}.', 'success')
    return redirect(url_for('admin.users'))


# ── Departments ────────────────────────────────────────────────────────────────

@bp.route('/departments')
@admin_required
def departments():
    org = current_user.primary_organisation
    if org:
        depts = Department.query.filter_by(organisation_id=org.id).all()
    else:
        depts = Department.query.all()
    return render_template('admin/departments.html', title='Departments', departments=depts)


@bp.route('/departments/create', methods=['POST'])
@admin_required
def create_department():
    org = current_user.primary_organisation
    name = request.form.get('name', '').strip()
    if not name:
        flash('Department name is required.', 'danger')
        return redirect(url_for('admin.departments'))
    dept = Department(
        organisation_id=org.id if org else int(request.form.get('organisation_id', 0)),
        name=name,
        code=request.form.get('code') or None,
        description=request.form.get('description') or None,
    )
    db.session.add(dept)
    db.session.commit()
    flash(f'Department "{name}" created.', 'success')
    return redirect(url_for('admin.departments'))

