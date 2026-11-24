"""AuditLog model"""
from datetime import datetime
from app.extensions import db


class AuditLog(db.Model):
    """Immutable audit trail for sensitive operations"""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id', ondelete='SET NULL'), nullable=True)
    
    action = db.Column(db.String(100), nullable=False)   # e.g. 'login', 'dispense', 'create_prescription'
    module = db.Column(db.String(50))                    # e.g. 'auth', 'pharmacy', 'inventory'
    
    # What was affected
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.Integer)
    
    # Data snapshot
    old_values = db.Column(db.Text)  # JSON string
    new_values = db.Column(db.Text)  # JSON string
    
    description = db.Column(db.Text)
    
    # Request context
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship('User', foreign_keys=[user_id])
    organisation = db.relationship('Organisation', foreign_keys=[organisation_id])

    def __repr__(self):
        return f'<AuditLog {self.action} by user_id={self.user_id}>'


def log_action(action, module=None, target_type=None, target_id=None,
               old_values=None, new_values=None, description=None,
               user_id=None, organisation_id=None, ip_address=None, user_agent=None):
    """Helper to record an audit log entry"""
    import json
    from app.extensions import db
    
    entry = AuditLog(
        user_id=user_id,
        organisation_id=organisation_id,
        action=action,
        module=module,
        target_type=target_type,
        target_id=target_id,
        old_values=json.dumps(old_values) if old_values else None,
        new_values=json.dumps(new_values) if new_values else None,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.session.add(entry)
    return entry

