from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import User, UserRole
from werkzeug.security import check_password_hash
from forms import LoginForm

def init_routes(app):
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            if user and check_password_hash(user.password_hash, form.password.data):
                if user.role == UserRole.TEACHER:
                    login_user(user)
                    flash('Logged in successfully.', 'success')
                    return redirect(url_for('admin_dashboard'))
                else:
                    flash('Access denied: You are not an admin.', 'danger')
            else:
                flash('Invalid username or password.', 'danger')
        return render_template('login.html', form=form)

    @app.route('/admin/dashboard')
    @login_required
    def admin_dashboard():
        if current_user.role != UserRole.TEACHER:
            flash('Access denied: You are not an admin.', 'danger')
            return redirect(url_for('index'))
        return render_template('admin_dashboard.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('index')) 