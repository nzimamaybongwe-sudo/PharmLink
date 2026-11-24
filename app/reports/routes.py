"""Reports routes"""
import csv
import io
from flask import render_template, request, abort, make_response, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps
from datetime import date, timedelta
from app.reports import bp
from app.extensions import db
from app.models.prescription import Prescription
from app.models.inventory import StockMovement, MedicineBatch
from app.models.medicine import Medicine
from app.models.patient import Patient
from app.models.consultation import Consultation
from app.models.dispensing import DispensingRecord


def reports_access(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.has_any_role(
            'platform_admin', 'hospital_admin', 'inventory_officer', 'finance_officer'
        ):
            abort(403)
        return f(*args, **kwargs)
    return login_required(decorated)


@bp.route('/')
@reports_access
def index():
    return render_template('reports/index.html', title='Reports')


@bp.route('/prescriptions')
@reports_access
def prescription_report():
    org = current_user.primary_organisation
    org_id = org.id if org else None
    
    date_from = request.args.get('date_from', str(date.today() - timedelta(days=30)))
    date_to = request.args.get('date_to', str(date.today()))
    
    query = Prescription.query
    if org_id and not current_user.is_platform_admin():
        query = query.filter_by(organisation_id=org_id)
    
    try:
        query = query.filter(
            Prescription.prescription_date >= date_from,
            Prescription.prescription_date <= date_to,
        )
    except Exception:
        pass
    
    prescriptions = query.order_by(Prescription.prescription_date.desc()).all()
    
    if request.args.get('export') == 'csv':
        return _export_prescriptions_csv(prescriptions)
    
    return render_template('reports/prescriptions.html', title='Prescription Report',
                           prescriptions=prescriptions, date_from=date_from, date_to=date_to)


@bp.route('/inventory')
@reports_access
def inventory_report():
    org = current_user.primary_organisation
    org_id = org.id if org else None
    
    medicines = Medicine.query.filter_by(
        organisation_id=org_id, is_active=True
    ).all() if org_id else Medicine.query.filter_by(is_active=True).all()
    
    report_data = []
    today = date.today()
    for med in medicines:
        total_stock = med.total_stock
        batches = MedicineBatch.query.filter_by(
            medicine_id=med.id, organisation_id=org_id or None, is_active=True
        ).all()
        expired = sum(1 for b in batches if b.is_expired)
        near_expiry = sum(1 for b in batches if not b.is_expired and b.days_to_expiry <= 90)
        report_data.append({
            'medicine': med,
            'total_stock': total_stock,
            'is_low': med.is_low_stock,
            'expired_batches': expired,
            'near_expiry_batches': near_expiry,
        })
    
    if request.args.get('export') == 'csv':
        return _export_inventory_csv(report_data)
    
    return render_template('reports/inventory.html', title='Inventory Report',
                           report_data=report_data)


def _export_prescriptions_csv(prescriptions):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Prescription #', 'Patient', 'Patient #', 'Doctor', 'Date', 'Status', 'Items'])
    for p in prescriptions:
        writer.writerow([
            p.prescription_number,
            p.patient.full_name if p.patient else '',
            p.patient.patient_number if p.patient else '',
            p.doctor.full_name if p.doctor else '',
            str(p.prescription_date),
            p.status,
            p.items.count(),
        ])
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=prescriptions_report.csv'
    return response


def _export_inventory_csv(report_data):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Code', 'Medicine', 'Generic Name', 'Strength', 'Form',
                     'Total Stock', 'Reorder Level', 'Low Stock', 'Expired Batches', 'Near Expiry'])
    for d in report_data:
        m = d['medicine']
        writer.writerow([
            m.medicine_code, m.name, m.generic_name or '', m.strength or '',
            m.dosage_form or '', d['total_stock'], m.reorder_level,
            'YES' if d['is_low'] else 'NO',
            d['expired_batches'], d['near_expiry_batches'],
        ])
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=inventory_report.csv'
    return response

