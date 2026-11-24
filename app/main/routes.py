"""Main routes - redirect based on role"""
from flask import redirect, url_for
from flask_login import current_user, login_required
from app.main import bp


@bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@bp.route('/dashboard')
@login_required
def dashboard():
    role = current_user.primary_role_name
    if role == 'platform_admin':
        return redirect(url_for('admin.platform_dashboard'))
    elif role == 'hospital_admin':
        return redirect(url_for('admin.hospital_dashboard'))
    elif role == 'doctor':
        return redirect(url_for('consultations.dashboard'))
    elif role in ('internal_pharmacist', 'external_pharmacist'):
        return redirect(url_for('pharmacy.dashboard'))
    elif role == 'inventory_officer':
        return redirect(url_for('inventory.dashboard'))
    elif role == 'finance_officer':
        return redirect(url_for('finance.dashboard'))
    elif role == 'patient':
        return redirect(url_for('patients.my_profile'))
    return redirect(url_for('admin.hospital_dashboard'))
