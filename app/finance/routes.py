"""Finance routes"""
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
from app.finance import bp
from app.extensions import db
from app.models.payment import Payment, PaymentTransaction
from app.models.prescription import Prescription
from app.models.referral import Referral
from app.models.audit import log_action


def finance_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.has_any_role('platform_admin', 'hospital_admin', 'finance_officer'):
            abort(403)
        return f(*args, **kwargs)
    return login_required(decorated)


@bp.route('/dashboard')
@finance_required
def dashboard():
    org = current_user.primary_organisation
    org_id = org.id if org else None
    
    query = Payment.query.filter_by(organisation_id=org_id) if org_id else Payment.query
    
    stats = {
        'total_payments': query.count(),
        'pending': query.filter_by(status='pending').count(),
        'paid': query.filter_by(status='paid').count(),
        'government_funded': query.filter_by(funding_type='government_funded').count(),
    }
    recent_payments = query.order_by(Payment.created_at.desc()).limit(10).all()
    return render_template('finance/dashboard.html', title='Finance Dashboard',
                           stats=stats, recent_payments=recent_payments)


@bp.route('/payments')
@finance_required
def payments():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    funding = request.args.get('funding', '')
    
    org = current_user.primary_organisation
    org_id = org.id if org else None
    
    query = Payment.query.filter_by(organisation_id=org_id) if org_id else Payment.query
    if status:
        query = query.filter_by(status=status)
    if funding:
        query = query.filter_by(funding_type=funding)
    
    payments = query.order_by(Payment.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template('finance/payments.html', title='Payments',
                           payments=payments, status_filter=status, funding_filter=funding)


@bp.route('/payments/record', methods=['GET', 'POST'])
@finance_required
def record_payment():
    if request.method == 'POST':
        org = current_user.primary_organisation
        payment = Payment(
            payment_reference=Payment.generate_reference(),
            prescription_id=request.form.get('prescription_id', type=int),
            referral_id=request.form.get('referral_id', type=int),
            patient_id=request.form.get('patient_id', type=int),
            organisation_id=org.id if org else None,
            amount_due=request.form.get('amount_due', type=float, default=0),
            amount_paid=request.form.get('amount_paid', type=float, default=0),
            currency=request.form.get('currency', 'SZL'),
            funding_type=request.form.get('funding_type', 'patient_funded'),
            funding_reference=request.form.get('funding_reference') or None,
            status='pending',
            notes=request.form.get('notes') or None,
            recorded_by_id=current_user.id,
        )
        db.session.add(payment)
        log_action('record_payment', module='finance', target_type='payment',
                   description=f'Payment {payment.payment_reference}',
                   user_id=current_user.id)
        db.session.commit()
        flash(f'Payment {payment.payment_reference} recorded.', 'success')
        return redirect(url_for('finance.payments'))
    return render_template('finance/record_payment.html', title='Record Payment')

