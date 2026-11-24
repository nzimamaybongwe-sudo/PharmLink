"""PharmLink Flask Application Factory"""
import os
from flask import Flask
from config import config
from app.extensions import db, migrate, login_manager, csrf, mail


def create_app(config_name=None):
    """Application factory pattern."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Ensure upload directories exist
    for folder in [
        app.config['UPLOAD_FOLDER'],
        app.config['QR_UPLOAD_FOLDER'],
        app.config['BARCODE_UPLOAD_FOLDER'],
    ]:
        os.makedirs(folder, exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    
    # Register blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    from app.patients import bp as patients_bp
    app.register_blueprint(patients_bp, url_prefix='/patients')
    
    from app.consultations import bp as consultations_bp
    app.register_blueprint(consultations_bp, url_prefix='/consultations')
    
    from app.prescriptions import bp as prescriptions_bp
    app.register_blueprint(prescriptions_bp, url_prefix='/prescriptions')
    
    from app.pharmacy import bp as pharmacy_bp
    app.register_blueprint(pharmacy_bp, url_prefix='/pharmacy')
    
    from app.inventory import bp as inventory_bp
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    
    from app.referrals import bp as referrals_bp
    app.register_blueprint(referrals_bp, url_prefix='/referrals')
    
    from app.finance import bp as finance_bp
    app.register_blueprint(finance_bp, url_prefix='/finance')
    
    from app.notifications import bp as notifications_bp
    app.register_blueprint(notifications_bp, url_prefix='/notifications')
    
    from app.reports import bp as reports_bp
    app.register_blueprint(reports_bp, url_prefix='/reports')
    
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register template context processors
    register_context_processors(app)
    
    return app


def register_error_handlers(app):
    from flask import render_template

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500


def register_context_processors(app):
    from flask_login import current_user
    from app.models.notification import Notification

    @app.context_processor
    def inject_globals():
        unread_count = 0
        if current_user and current_user.is_authenticated:
            try:
                unread_count = Notification.query.filter_by(
                    user_id=current_user.id, is_read=False
                ).count()
            except Exception:
                pass
        return {
            'app_name': app.config.get('APP_NAME', 'PharmLink'),
            'app_version': app.config.get('APP_VERSION', '1.0.0'),
            'unread_notifications': unread_count,
        }

