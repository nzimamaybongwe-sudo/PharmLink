"""Auth routes"""
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
from datetime import datetime
from app.auth import bp
from app.auth.forms import LoginForm, ChangePasswordForm, EditProfileForm
from app.extensions import db
from app.models.user import User
from app.models.audit import log_action


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact your administrator.', 'danger')
                return redirect(url_for('auth.login'))
            login_user(user, remember=form.remember_me.data)
            user.last_login_at = datetime.utcnow()
            user.last_login_ip = request.remote_addr
            log_action('login', module='auth', target_type='user', target_id=user.id,
                       description=f'User {user.email} logged in',
                       user_id=user.id, ip_address=request.remote_addr,
                       user_agent=request.user_agent.string[:500])
            db.session.commit()
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.first_name}!', 'success')
            return redirect(next_page or url_for('main.dashboard'))
        flash('Invalid email or password. Please try again.', 'danger')
    return render_template('auth/login.html', title='Sign In', form=form)


@bp.route('/logout')
@login_required
def logout():
    log_action('logout', module='auth', target_type='user', target_id=current_user.id,
               description=f'User {current_user.email} logged out',
               user_id=current_user.id, ip_address=request.remote_addr)
    db.session.commit()
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = EditProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.first_name = form.first_name.data.strip()
        current_user.last_name = form.last_name.data.strip()
        current_user.phone = form.phone.data
        current_user.profession = form.profession.data
        current_user.licence_number = form.licence_number.data
        current_user.updated_at = datetime.utcnow()
        log_action('update_profile', module='auth', target_type='user',
                   target_id=current_user.id, description='User updated profile',
                   user_id=current_user.id, ip_address=request.remote_addr)
        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('auth.profile'))
    return render_template('auth/profile.html', title='My Profile', form=form)


@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
            return render_template('auth/change_password.html', form=form)
        current_user.set_password(form.new_password.data)
        log_action('change_password', module='auth', target_type='user',
                   target_id=current_user.id, description='User changed password',
                   user_id=current_user.id, ip_address=request.remote_addr)
        db.session.commit()
        flash('Password updated successfully.', 'success')
        return redirect(url_for('auth.profile'))
    return render_template('auth/change_password.html', title='Change Password', form=form)

