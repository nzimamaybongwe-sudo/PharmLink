"""Referral routes"""
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, date, timedelta
from app.referrals import bp
from app.extensions import db
from app.models.referral import Referral, ReferralItem, ReferralFulfilment
from app.models.prescription import Prescription, PrescriptionItem
from app.models.organisation import Organisation
from app.models.inventory import MedicineBatch, StockMovement
from app.models.audit import log_action


def pharmacy_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.has_any_role(
            'platform_admin', 'hospital_admin',
            'internal_pharmacist', 'external_pharmacist'
        ):
            abort(403)
        return f(*args, **kwargs)
    return login_required(decorated)


@bp.route('/')
@pharmacy_required
def index():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    org = current_user.primary_organisation
    org_id = org.id if org else None
    
    query = Referral.query
    if org_id and not current_user.is_platform_admin():
        query = query.filter(
            db.or_(
                Referral.originating_organisation_id == org_id,
                Referral.receiving_organisation_id == org_id,
            )
        )
    if status:
        query = query.filter_by(status=status)
    
    referrals = query.order_by(Referral.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    statuses = ['draft', 'pending', 'sent', 'accepted', 'rejected',
                'partially_fulfilled', 'fulfilled', 'cancelled', 'expired']
    return render_template('referrals/index.html', title='Referrals',
                           referrals=referrals, status_filter=status, statuses=statuses)


@bp.route('/create/<int:prescription_id>', methods=['GET', 'POST'])
@pharmacy_required
def create(prescription_id):
    prescription = Prescription.query.get_or_404(prescription_id)
    org = current_user.primary_organisation
    
    if request.method == 'POST':
        item_ids = request.form.getlist('item_id')
        quantities = request.form.getlist('quantity')
        receiving_org_id = request.form.get('receiving_org_id', type=int)
        
        if not item_ids:
            flash('Select at least one medicine to refer.', 'danger')
            return redirect(request.url)
        
        referral = Referral(
            referral_number=Referral.generate_number(),
            prescription_id=prescription.id,
            originating_organisation_id=org.id if org else None,
            referring_pharmacist_id=current_user.id,
            receiving_organisation_id=receiving_org_id,
            status='sent' if receiving_org_id else 'draft',
            reason=request.form.get('reason') or None,
            expiry_date=date.today() + timedelta(days=7),
            funding_type=request.form.get('funding_type', 'patient_funded'),
        )
        db.session.add(referral)
        db.session.flush()
        
        for i, item_id in enumerate(item_ids):
            item = PrescriptionItem.query.get(int(item_id))
            if not item:
                continue
            qty = int(quantities[i]) if i < len(quantities) and quantities[i] else item.quantity_remaining
            ri = ReferralItem(
                referral_id=referral.id,
                prescription_item_id=item.id,
                medicine_id=item.medicine_id,
                quantity_requested=min(qty, item.quantity_remaining),
            )
            db.session.add(ri)
        
        prescription.status = 'referred'
        log_action('create_referral', module='referrals', target_type='referral',
                   target_id=referral.id,
                   description=f'Referral {referral.referral_number}',
                   user_id=current_user.id)
        db.session.commit()
        flash(f'Referral {referral.referral_number} created.', 'success')
        return redirect(url_for('referrals.view', referral_id=referral.id))
    
    # Get pending items on this prescription
    pending_items = [i for i in prescription.items if not i.is_fully_dispensed]
    # Get registered pharmacies in the network
    pharmacies = Organisation.query.filter(
        Organisation.org_type.in_(['community_pharmacy', 'private_pharmacy']),
        Organisation.is_active == True,
        Organisation.deleted_at == None,
        Organisation.id != (org.id if org else 0),
    ).all()
    
    return render_template('referrals/create.html', title='Create Referral',
                           prescription=prescription, pending_items=pending_items,
                           pharmacies=pharmacies)


@bp.route('/<int:referral_id>')
@pharmacy_required
def view(referral_id):
    referral = Referral.query.get_or_404(referral_id)
    return render_template('referrals/view.html',
                           title=f'Referral {referral.referral_number}',
                           referral=referral)


@bp.route('/<int:referral_id>/accept', methods=['POST'])
@pharmacy_required
def accept(referral_id):
    referral = Referral.query.get_or_404(referral_id)
    if referral.status != 'sent':
        flash('Referral cannot be accepted in its current status.', 'danger')
        return redirect(url_for('referrals.view', referral_id=referral_id))
    referral.status = 'accepted'
    referral.accepted_at = datetime.utcnow()
    db.session.commit()
    flash('Referral accepted.', 'success')
    return redirect(url_for('referrals.view', referral_id=referral_id))


@bp.route('/<int:referral_id>/reject', methods=['POST'])
@pharmacy_required
def reject(referral_id):
    referral = Referral.query.get_or_404(referral_id)
    reason = request.form.get('reason', '').strip()
    referral.status = 'rejected'
    referral.rejection_reason = reason
    db.session.commit()
    flash('Referral rejected.', 'info')
    return redirect(url_for('referrals.view', referral_id=referral_id))

