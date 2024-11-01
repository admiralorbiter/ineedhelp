from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import User, UserRole, db
from werkzeug.security import check_password_hash, generate_password_hash
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

    @app.route('/admin/dashboard', methods=['GET'])
    @login_required
    def admin_dashboard():
        if current_user.role != UserRole.TEACHER:
            flash('Access denied: You are not an admin.', 'danger')
            return redirect(url_for('index'))
        
        # Query all students
        students = User.query.filter_by(role=UserRole.STUDENT).all()
        return render_template('admin_dashboard.html', students=students)

    @app.route('/create_student', methods=['POST'])
    @login_required
    def create_student():
        if current_user.role != UserRole.TEACHER:
            flash('Access denied: You are not authorized to create students.', 'danger')
            return redirect(url_for('index'))

        try:
            # Create new student user
            new_student = User(
                username=request.form['email'],  # Using email as username
                email=request.form['email'],
                first_name=request.form['firstName'],
                last_name=request.form['lastName'],
                password_hash=generate_password_hash(request.form['password']),
                role=UserRole.STUDENT
            )

            # Add and commit to database
            db.session.add(new_student)
            db.session.commit()

            flash('Student account created successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error creating student account. Please try again.', 'danger')
            print(f"Error: {str(e)}")  # For debugging

        return redirect(url_for('admin_dashboard'))

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('index')) 
    
    @app.route('/tutor')
    @login_required
    def tutor():
        return render_template('tutor.html')
    
    @app.route('/dashboard')
    @login_required
    def dashboard():
        return render_template('dashboard.html')