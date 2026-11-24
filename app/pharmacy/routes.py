"""Pharmacy dispensing routes"""
from flask import render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, date
from app.pharmacy import bp
from app.extensions import db
from app.models.prescription import Prescription, PrescriptionItem
from app.models.dispensing import DispensingRecord, DispensingItem
from app.models.inventory import MedicineBatch, StockMovement
from app.models.medicine import Medicine
from app.models.referral import Referral, ReferralItem
from app.models.audit import log_action
from app.models.notification import create_notification


def pharmacist_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.has_any_role(
            'platform_admin', 'hospital_admin',
            'internal_pharmacist', 'external_pharmacist'
        ):
            abort(403)
        return f(*args, **kwargs)
    return login_required(decorated)


@bp.route('/dashboard')
@pharmacist_required
def dashboard():
    org = current_user.primary_organisation
    org_id = org.id if org else None
    
    today = date.today()
    stats = {
        'pending': Prescription.query.filter_by(
            organisation_id=org_id, status='issued'
        ).count() if org_id else 0,
        'dispensed_today': DispensingRecord.query.filter(
            DispensingRecord.organisation_id == org_id,
            db.func.date(DispensingRecord.dispensed_at) == today,
        ).count() if org_id else 0,
        'partial': Prescription.query.filter_by(
            organisation_id=org_id, status='partially_dispensed'
        ).count() if org_id else 0,
        'pending_referrals': Referral.query.filter_by(
            originating_organisation_id=org_id, status='sent'
        ).count() if org_id else 0,
    }
    
    # Low stock and expiring
    if org_id:
        all_medicines = Medicine.query.filter_by(
            organisation_id=org_id, is_active=True
        ).all()
        low_stock = [m for m in all_medicines if m.is_low_stock]
        
        expiring_batches = MedicineBatch.query.filter(
            MedicineBatch.organisation_id == org_id,
            MedicineBatch.expiry_date <= date.fromordinal(today.toordinal() + 90),
            MedicineBatch.expiry_date >= today,
            MedicineBatch.quantity_remaining > 0,
            MedicineBatch.is_active == True,
        ).order_by(MedicineBatch.expiry_date).limit(10).all()
    else:
        low_stock = []
        expiring_batches = []
    
    pending_prescriptions = Prescription.query.filter(
        Prescription.organisation_id == org_id,
        Prescription.status.in_(['issued', 'partially_dispensed']),
    ).order_by(Prescription.created_at.desc()).limit(10).all() if org_id else []
    
    return render_template('pharmacy/dashboard.html', title='Pharmacy Dashboard',
                           stats=stats, low_stock=low_stock[:5],
                           expiring_batches=expiring_batches,
                           pending_prescriptions=pending_prescriptions)


@bp.route('/prescriptions')
@pharmacist_required
def prescriptions():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'issued')
    search = request.args.get('search', '').strip()
    
    org = current_user.primary_organisation
    org_id = org.id if org else None
    
    from app.models.patient import Patient
    query = Prescription.query.filter(
        Prescription.organisation_id == org_id,
        Prescription.status != 'cancelled',
    ) if org_id else Prescription.query
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    if search:
        query = query.join(Patient).filter(
            db.or_(
                Prescription.prescription_number.ilike(f'%{search}%'),
                Patient.last_name.ilike(f'%{search}%'),
                Patient.patient_number.ilike(f'%{search}%'),
            )
        )
    
    prescriptions = query.order_by(
        Prescription.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    
    return render_template('pharmacy/prescriptions.html', title='Pharmacy - Prescriptions',
                           prescriptions=prescriptions, status_filter=status_filter, search=search)


@bp.route('/dispense/<int:prescription_id>', methods=['GET', 'POST'])
@pharmacist_required
def dispense(prescription_id):
    prescription = Prescription.query.get_or_404(prescription_id)
    org = current_user.primary_organisation
    
    # Access check
    if org and prescription.organisation_id != org.id and not current_user.is_platform_admin():
        abort(403)
    
    # Validate prescription state
    if not prescription.is_processable:
        flash(f'Prescription cannot be dispensed. Status: {prescription.status.replace("_"," ")}', 'danger')
        return redirect(url_for('pharmacy.prescriptions'))
    
    if prescription.is_expired:
        prescription.status = 'expired'
        db.session.commit()
        flash('This prescription has expired and cannot be dispensed.', 'danger')
        return redirect(url_for('pharmacy.prescriptions'))
    
    # Get available batches for each pending item (FEFO order)
    items_with_batches = []
    for item in prescription.items:
        if item.is_fully_dispensed:
            continue
        batches = MedicineBatch.query.filter(
            MedicineBatch.medicine_id == item.medicine_id,
            MedicineBatch.organisation_id == org.id if org else MedicineBatch.organisation_id,
            MedicineBatch.quantity_remaining > 0,
            MedicineBatch.expiry_date > date.today(),
            MedicineBatch.is_active == True,
        ).order_by(MedicineBatch.expiry_date.asc()).all()  # FEFO
        items_with_batches.append({'item': item, 'batches': batches})
    
    if request.method == 'POST':
        # Collect dispensing quantities
        dispense_data = []
        
        for item_batch in items_with_batches:
            item = item_batch['item']
            batch_id = request.form.get(f'batch_{item.id}', type=int)
            qty = request.form.get(f'qty_{item.id}', type=int, default=0)
            
            if not batch_id or not qty or qty <= 0:
                continue
            
            batch = MedicineBatch.query.get(batch_id)
            if not batch:
                flash(f'Invalid batch selected for {item.medicine_name}.', 'danger')
                return redirect(request.url)
            
            # Validations
            if batch.is_expired:
                flash(f'Batch {batch.batch_number} is expired. Cannot dispense.', 'danger')
                return redirect(request.url)
            if qty > item.quantity_remaining:
                flash(f'Cannot dispense {qty} of {item.medicine_name}. Only {item.quantity_remaining} remaining on prescription.', 'danger')
                return redirect(request.url)
            if qty > batch.quantity_remaining:
                flash(f'Insufficient stock in batch {batch.batch_number}. Available: {batch.quantity_remaining}.', 'danger')
                return redirect(request.url)
            
            dispense_data.append({'item': item, 'batch': batch, 'qty': qty})
        
        if not dispense_data:
            flash('No items to dispense. Please enter quantities.', 'warning')
            return redirect(request.url)
        
        # All validations passed - commit in a transaction
        try:
            dispensing_record = DispensingRecord(
                dispensing_number=DispensingRecord.generate_number(),
                prescription_id=prescription.id,
                pharmacist_id=current_user.id,
                organisation_id=org.id if org else None,
                dispensed_at=datetime.utcnow(),
                via_qr=request.form.get('via_qr') == '1',
                notes=request.form.get('notes') or None,
            )
            db.session.add(dispensing_record)
            db.session.flush()
            
            for d in dispense_data:
                item, batch, qty = d['item'], d['batch'], d['qty']
                
                # Update prescription item
                old_qty = batch.quantity_remaining
                item.quantity_dispensed += qty
                batch.quantity_remaining -= qty
                
                # Dispensing item record
                di = DispensingItem(
                    record_id=dispensing_record.id,
                    prescription_item_id=item.id,
                    batch_id=batch.id,
                    quantity_dispensed=qty,
                )
                db.session.add(di)
                
                # Stock movement record
                sm = StockMovement(
                    batch_id=batch.id,
                    medicine_id=item.medicine_id,
                    organisation_id=org.id if org else None,
                    movement_type='dispensed',
                    quantity=qty,
                    quantity_before=old_qty,
                    quantity_after=batch.quantity_remaining,
                    reference_type='dispensing',
                    reference_id=dispensing_record.id,
                    performed_by_id=current_user.id,
                )
                db.session.add(sm)
            
            # Update dispensing_record is_partial flag
            is_partial = any(not d['item'].is_fully_dispensed for d in dispense_data)
            dispensing_record.is_partial = is_partial
            
            # Update prescription status
            prescription.update_status()
            
            log_action('dispense_prescription', module='pharmacy',
                       target_type='prescription', target_id=prescription.id,
                       description=f'Dispensing {dispensing_record.dispensing_number}',
                       user_id=current_user.id,
                       organisation_id=org.id if org else None)
            
            db.session.commit()
            flash(f'Dispensing {dispensing_record.dispensing_number} recorded successfully.', 'success')
            return redirect(url_for('prescriptions.view', prescription_id=prescription.id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Dispensing failed: {str(e)}', 'danger')
            return redirect(request.url)
    
    return render_template('pharmacy/dispense.html',
                           title=f'Dispense - {prescription.prescription_number}',
                           prescription=prescription,
                           items_with_batches=items_with_batches)

