"""Inventory management routes"""
from flask import render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, date
from app.inventory import bp
from app.extensions import db
from app.models.medicine import Medicine, MedicineCategory, Supplier
from app.models.inventory import MedicineBatch, StockMovement
from app.models.audit import log_action


def inventory_access(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.has_any_role(
            'platform_admin', 'hospital_admin',
            'inventory_officer', 'internal_pharmacist'
        ):
            abort(403)
        return f(*args, **kwargs)
    return login_required(decorated)


@bp.route('/dashboard')
@inventory_access
def dashboard():
    org = current_user.primary_organisation
    org_id = org.id if org else None
    
    today = date.today()
    
    if org_id:
        total_medicines = Medicine.query.filter_by(
            organisation_id=org_id, is_active=True
        ).count()
        
        all_medicines = Medicine.query.filter_by(
            organisation_id=org_id, is_active=True
        ).all()
        
        low_stock = [m for m in all_medicines if m.is_low_stock]
        
        expired_batches = MedicineBatch.query.filter(
            MedicineBatch.organisation_id == org_id,
            MedicineBatch.expiry_date < today,
            MedicineBatch.quantity_remaining > 0,
            MedicineBatch.is_active == True,
        ).count()
        
        expiring_soon = MedicineBatch.query.filter(
            MedicineBatch.organisation_id == org_id,
            MedicineBatch.expiry_date >= today,
            MedicineBatch.expiry_date <= date.fromordinal(today.toordinal() + 90),
            MedicineBatch.quantity_remaining > 0,
            MedicineBatch.is_active == True,
        ).count()
        
        total_batches = MedicineBatch.query.filter_by(
            organisation_id=org_id, is_active=True
        ).count()
    else:
        total_medicines = 0
        low_stock = []
        expired_batches = 0
        expiring_soon = 0
        total_batches = 0
    
    recent_movements = StockMovement.query.filter_by(
        organisation_id=org_id
    ).order_by(StockMovement.created_at.desc()).limit(10).all() if org_id else []
    
    stats = {
        'total_medicines': total_medicines,
        'low_stock': len(low_stock),
        'expired_batches': expired_batches,
        'expiring_soon': expiring_soon,
        'total_batches': total_batches,
    }
    
    return render_template('inventory/dashboard.html', title='Inventory Dashboard',
                           stats=stats, low_stock_items=low_stock[:8],
                           recent_movements=recent_movements)


@bp.route('/medicines')
@inventory_access
def medicines():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    category_id = request.args.get('category', type=int)
    
    org = current_user.primary_organisation
    query = Medicine.query.filter_by(is_active=True)
    
    if org and not current_user.is_platform_admin():
        query = Medicine.query.filter_by(organisation_id=org.id, is_active=True)
    
    if search:
        query = query.filter(
            db.or_(
                Medicine.name.ilike(f'%{search}%'),
                Medicine.generic_name.ilike(f'%{search}%'),
                Medicine.medicine_code.ilike(f'%{search}%'),
                Medicine.barcode.ilike(f'%{search}%'),
            )
        )
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    medicines = query.order_by(Medicine.name).paginate(
        page=page, per_page=20, error_out=False
    )
    categories = MedicineCategory.query.filter_by(is_active=True).all()
    return render_template('inventory/medicines.html', title='Medicine Catalogue',
                           medicines=medicines, search=search, categories=categories,
                           category_id=category_id)


@bp.route('/medicines/add', methods=['GET', 'POST'])
@inventory_access
def add_medicine():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Medicine name is required.', 'danger')
            return redirect(request.url)
        
        org = current_user.primary_organisation
        
        medicine = Medicine(
            medicine_code=Medicine.generate_code(),
            name=name,
            generic_name=request.form.get('generic_name') or None,
            brand_name=request.form.get('brand_name') or None,
            category_id=request.form.get('category_id', type=int),
            strength=request.form.get('strength') or None,
            dosage_form=request.form.get('dosage_form') or None,
            unit_of_measurement=request.form.get('unit_of_measurement') or None,
            description=request.form.get('description') or None,
            barcode=request.form.get('barcode') or None,
            reorder_level=request.form.get('reorder_level', type=int, default=10),
            is_controlled=request.form.get('is_controlled') == '1',
            organisation_id=org.id if org else None,
        )
        db.session.add(medicine)
        log_action('add_medicine', module='inventory', target_type='medicine',
                   description=f'Added medicine: {name}', user_id=current_user.id)
        db.session.commit()
        flash(f'Medicine "{name}" added. Code: {medicine.medicine_code}', 'success')
        return redirect(url_for('inventory.medicines'))
    
    categories = MedicineCategory.query.filter_by(is_active=True).all()
    return render_template('inventory/add_medicine.html', title='Add Medicine',
                           categories=categories)


@bp.route('/medicines/<int:medicine_id>/batches')
@inventory_access
def batches(medicine_id):
    medicine = Medicine.query.get_or_404(medicine_id)
    org = current_user.primary_organisation
    
    batch_query = MedicineBatch.query.filter_by(medicine_id=medicine_id)
    if org and not current_user.is_platform_admin():
        batch_query = batch_query.filter_by(organisation_id=org.id)
    
    batches = batch_query.order_by(MedicineBatch.expiry_date).all()
    return render_template('inventory/batches.html', title=f'Batches - {medicine.name}',
                           medicine=medicine, batches=batches)


@bp.route('/medicines/<int:medicine_id>/receive-stock', methods=['GET', 'POST'])
@inventory_access
def receive_stock(medicine_id):
    medicine = Medicine.query.get_or_404(medicine_id)
    org = current_user.primary_organisation
    
    if request.method == 'POST':
        batch_number = request.form.get('batch_number', '').strip()
        qty = request.form.get('quantity', type=int, default=0)
        expiry_str = request.form.get('expiry_date', '')
        
        if not batch_number or not qty or not expiry_str:
            flash('Batch number, quantity and expiry date are required.', 'danger')
            return redirect(request.url)
        
        expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
        if expiry_date <= date.today():
            flash('Cannot receive stock that is already expired.', 'danger')
            return redirect(request.url)
        
        # Check for duplicate batch
        existing = MedicineBatch.query.filter_by(
            medicine_id=medicine.id,
            batch_number=batch_number,
            organisation_id=org.id if org else None,
        ).first()
        if existing:
            flash(f'Batch number "{batch_number}" already exists for this medicine.', 'danger')
            return redirect(request.url)
        
        batch = MedicineBatch(
            medicine_id=medicine.id,
            organisation_id=org.id if org else None,
            batch_number=batch_number,
            quantity_received=qty,
            quantity_remaining=qty,
            manufacture_date=datetime.strptime(
                request.form['manufacture_date'], '%Y-%m-%d'
            ).date() if request.form.get('manufacture_date') else None,
            expiry_date=expiry_date,
            supplier_id=request.form.get('supplier_id', type=int),
            purchase_cost=request.form.get('purchase_cost', type=float),
            selling_price=request.form.get('selling_price', type=float),
            date_received=date.today(),
            received_by_id=current_user.id,
            notes=request.form.get('notes') or None,
        )
        db.session.add(batch)
        db.session.flush()
        
        # Record stock movement
        sm = StockMovement(
            batch_id=batch.id,
            medicine_id=medicine.id,
            organisation_id=org.id if org else None,
            movement_type='received',
            quantity=qty,
            quantity_before=0,
            quantity_after=qty,
            reference_type='stock_receipt',
            performed_by_id=current_user.id,
            notes=f'Initial receipt of batch {batch_number}',
        )
        db.session.add(sm)
        
        log_action('receive_stock', module='inventory', target_type='medicine_batch',
                   target_id=batch.id,
                   description=f'Received {qty} units of {medicine.name}, batch {batch_number}',
                   user_id=current_user.id)
        db.session.commit()
        flash(f'Stock received: {qty} units of {medicine.name} (Batch: {batch_number})', 'success')
        return redirect(url_for('inventory.batches', medicine_id=medicine.id))
    
    suppliers = Supplier.query.filter_by(is_active=True).all()
    return render_template('inventory/receive_stock.html', title='Receive Stock',
                           medicine=medicine, suppliers=suppliers)


@bp.route('/movements')
@inventory_access
def movements():
    page = request.args.get('page', 1, type=int)
    org = current_user.primary_organisation
    org_id = org.id if org else None
    
    query = StockMovement.query
    if org_id and not current_user.is_platform_admin():
        query = query.filter_by(organisation_id=org_id)
    
    movements = query.order_by(
        StockMovement.created_at.desc()
    ).paginate(page=page, per_page=30, error_out=False)
    return render_template('inventory/movements.html', title='Stock Movements',
                           movements=movements)


@bp.route('/categories', methods=['GET', 'POST'])
@inventory_access
def categories():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            cat = MedicineCategory(name=name, description=request.form.get('description'))
            db.session.add(cat)
            db.session.commit()
            flash(f'Category "{name}" added.', 'success')
    categories = MedicineCategory.query.order_by(MedicineCategory.name).all()
    return render_template('inventory/categories.html', title='Medicine Categories',
                           categories=categories)


@bp.route('/suppliers', methods=['GET', 'POST'])
@inventory_access
def suppliers():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            supplier = Supplier(
                name=name,
                contact_person=request.form.get('contact_person') or None,
                email=request.form.get('email') or None,
                phone=request.form.get('phone') or None,
                address=request.form.get('address') or None,
            )
            db.session.add(supplier)
            db.session.commit()
            flash(f'Supplier "{name}" added.', 'success')
    suppliers_list = Supplier.query.order_by(Supplier.name).all()
    return render_template('inventory/suppliers.html', title='Suppliers',
                           suppliers=suppliers_list)


@bp.route('/api/medicine-stock/<int:medicine_id>')
@login_required
def api_medicine_stock(medicine_id):
    """AJAX - available batches for a medicine (FEFO order)"""
    org = current_user.primary_organisation
    batches = MedicineBatch.query.filter(
        MedicineBatch.medicine_id == medicine_id,
        MedicineBatch.organisation_id == org.id if org else MedicineBatch.organisation_id,
        MedicineBatch.quantity_remaining > 0,
        MedicineBatch.expiry_date > date.today(),
        MedicineBatch.is_active == True,
    ).order_by(MedicineBatch.expiry_date.asc()).all()
    return jsonify([{
        'id': b.id,
        'batch_number': b.batch_number,
        'quantity_remaining': b.quantity_remaining,
        'expiry_date': str(b.expiry_date),
    } for b in batches])

