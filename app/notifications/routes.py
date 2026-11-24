"""Notifications routes"""
from flask import render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from app.notifications import bp
from app.extensions import db
from app.models.notification import Notification


@bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template('notifications/index.html', title='Notifications',
                           notifications=notifications)


@bp.route('/mark-read/<int:notif_id>', methods=['POST'])
@login_required
def mark_read(notif_id):
    n = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first_or_404()
    n.mark_read()
    db.session.commit()
    return redirect(request.referrer or url_for('notifications.index'))


@bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    from datetime import datetime
    Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).update({'is_read': True, 'read_at': datetime.utcnow()})
    db.session.commit()
    return redirect(url_for('notifications.index'))


@bp.route('/api/unread-count')
@login_required
def api_unread_count():
    count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()
    return jsonify({'count': count})

