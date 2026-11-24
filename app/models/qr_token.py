"""QR Token model for prescription identification"""
import secrets
from datetime import datetime, date, timedelta
from app.extensions import db


class QRToken(db.Model):
    """Secure QR token for prescription identification"""
    __tablename__ = 'qr_tokens'

    id = db.Column(db.Integer, primary_key=True)
    
    token = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # What this token identifies
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id', ondelete='CASCADE'), nullable=True)
    
    # Validity
    is_active = db.Column(db.Boolean, default=True)
    expires_at = db.Column(db.DateTime)
    
    # Usage tracking
    scan_count = db.Column(db.Integer, default=0)
    last_scanned_at = db.Column(db.DateTime)
    last_scanned_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    last_scanned_ip = db.Column(db.String(45))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    prescription = db.relationship('Prescription', foreign_keys=[prescription_id],
                                    backref=db.backref('qr_code', uselist=False))
    last_scanned_by = db.relationship('User', foreign_keys=[last_scanned_by_id])

    @staticmethod
    def generate_token():
        """Generate a cryptographically secure URL-safe token"""
        return secrets.token_urlsafe(32)

    @property
    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True

    def record_scan(self, user_id=None, ip_address=None):
        self.scan_count += 1
        self.last_scanned_at = datetime.utcnow()
        self.last_scanned_by_id = user_id
        self.last_scanned_ip = ip_address

    def __repr__(self):
        return f'<QRToken {self.token[:16]}...>'

