from datetime import datetime
from flask import render_template, redirect, url_for, request, flash, abort
from sqlalchemy import desc
from website import app, db, bcrypt, mail
from website.forms import TaskForm, RegistrationForm, LoginForm, RequestResetForm, ResetPasswordForm
from website.models import Task, User
from flask_login import current_user, login_user, logout_user, login_required
from flask_mail import Message


@app.context_processor
def inject_year():
    current_year = datetime.now().year
    return dict(year=current_year)


@app.route('/')
@app.route('/home')
def home():
    if current_user.is_authenticated:
        flash('Your are already logged in.', 'info')
        return redirect(url_for('create_task'))
    return render_template('home.html')


@app.route('/create_task', methods=['GET', 'POST'])
@login_required
def create_task():
    form = TaskForm()
    current_date = datetime.now().date()
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    page = request.args.get('page', 1, type=int)
    tasks = None
    date = None
    if 'submit_task' in request.form:
        if form.validate_on_submit():
            task = Task(task=form.task.data, date=form.date.data, author=current_user)
            db.session.add(task)
            db.session.commit()
            return redirect(url_for('create_task'))
    elif start_date and end_date and 'show_task' in request.form:
        tasks = Task.query.filter_by(user_id=current_user.id).filter(Task.date.between(start_date, end_date)).order_by(Task.date, desc(Task.star), Task.color).paginate(page=page, per_page=10)
        date = f"{start_date} to {end_date}"
    elif 'show_all_task' in request.form:
        tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.date, desc(Task.star), Task.color).paginate(page=page, per_page=10)
        date = "All"
    else:
        tasks = Task.query.filter_by(user_id=current_user.id).filter(Task.date == current_date).order_by(Task.date, desc(Task.star), Task.color).paginate(page=page, per_page=10)
        date = "Today"
    return render_template('create_task.html', form=form, tasks=tasks, title='New Task', legend=date)


@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        flash('Your are already logged in.', 'info')
        return redirect(url_for('create_task'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash('Your are already logged in.', 'info')
        return redirect(url_for('create_task'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('create_task'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/update_task/<int:task_id>', methods=['POST'])
@login_required
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.author != current_user:
        abort(403)
    if 'complete_task' in request.form:
        task.complete = True
    else:
        task.complete = False

    if 'color_task' in request.form:
        task.color = request.form.get('color_task')

    if 'star_task' in request.form:
        task.star = True
    elif 'color_task' in request.form and 'star_task' not in request.form:
        task.star = False

    db.session.commit()
    return redirect(url_for('create_task'))


@app.route("/update_task/<int:task_id>/delete", methods=['GET', 'POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.author != current_user:
        abort(403)
    db.session.delete(task)
    db.session.commit()
    flash('Your task has been deleted!', 'success')
    return redirect(url_for('create_task'))


@app.route('/delete_period/<string:period>', methods=['GET', 'POST'])
@login_required
def delete_period(period):
    if period == 'Today':
        current_date = datetime.now().date()
        tasks_to_delete = Task.query.filter_by(user_id=current_user.id, date=current_date).all()
        flash('The tasks of Today have been deleted!', 'success')
    elif period == 'All':
        tasks_to_delete = Task.query.filter_by(user_id=current_user.id).all()
        flash('All tasks have been deleted!', 'success')
    else:
        start_date, end_date = period.split(" to ")
        tasks_to_delete = Task.query.filter_by(user_id=current_user.id).filter(Task.date.between(start_date, end_date)).all()
        flash('The selected period has been deleted!', 'success')
    for task in tasks_to_delete:
        db.session.delete(task)
    db.session.commit()
    return redirect(url_for('create_task'))


def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request',
                  sender='noreply@gmail.com',
                  recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
{url_for('reset_token', token=token, _external=True)}

If you did not make this request then simply ignore this email and no changes will be made.
'''
    mail.send(msg)


@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        flash('Your are already logged in.', 'info')
        return redirect(url_for('home'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash('An email has been sent with instructions to reset your password.', 'info')
        return redirect(url_for('login'))
    return render_template('reset_request.html', title='Reset Password', form=form)


@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        flash('Your are already logged in.', 'info')
        return redirect(url_for('home'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash('Your password has been updated! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('reset_token.html', title='Reset Password', form=form)


@app.errorhandler(403)
def error_403(error):
    return render_template('403.html'), 403


@app.errorhandler(404)
def error_404(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def error_500(error):
    return render_template('500.html'), 500