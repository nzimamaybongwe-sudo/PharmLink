"""Notification model"""
from datetime import datetime
from app.extensions import db


class Notification(db.Model):
    """In-app notifications for users"""
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    notification_type = db.Column(
        db.Enum(
            'prescription_created', 'prescription_ready', 'prescription_dispensed',
            'prescription_partially_dispensed', 'referral_submitted', 'referral_accepted',
            'referral_rejected', 'referral_fulfilled', 'low_stock', 'expiring_medicine',
            'account_created', 'account_updated', 'general',
            name='notification_type_enum'
        ),
        default='general'
    )
    
    # Optional link to a specific record
    reference_type = db.Column(db.String(50))
    reference_id = db.Column(db.Integer)
    action_url = db.Column(db.String(500))
    
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    read_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='notifications', foreign_keys=[user_id])

    def mark_read(self):
        self.is_read = True
        self.read_at = datetime.utcnow()

    def __repr__(self):
        return f'<Notification {self.title[:30]}>'


def create_notification(user_id, title, message, notification_type='general',
                         reference_type=None, reference_id=None, action_url=None):
    """Helper to create a notification"""
    from app.extensions import db
    n = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        reference_type=reference_type,
        reference_id=reference_id,
        action_url=action_url,
    )
    db.session.add(n)
    return n

