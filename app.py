from flask import Flask, render_template, request, redirect, url_for, Blueprint, jsonify
from models import db, Worker, Shift, User, generate_random_password
import calendar
from helpers import get_month_range
from datetime import datetime, date, timedelta
from sqlalchemy import extract, event
from sqlalchemy.engine import Engine
import sqlite3
from ai_scheduler import build_monthly_optimizer
from flask_login import login_user, logout_user, login_required, current_user
import json
from collections import defaultdict



app = Flask(__name__)
app.secret_key = 'yo-gabba-gabba'
from flask import flash
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///schedule.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Enable foreign key constraints in SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

# Define User class and methods


    
from flask_login import LoginManager

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            flash('Logged in successfully.')
            if user.role == 'manager':
                return redirect(url_for('dashboard_manager'))
            else:
                return redirect(url_for('dashboard_employee'))
        flash('Invalid username or password.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.')
    return redirect(url_for('login'))

@app.route('/dashboard_employee')
@login_required
def dashboard_employee():
    current_worker = Worker.query.filter_by(user_id=current_user.id).first()

    today = date.today()
    year = today.year
    month = today.month

    # Build month days
    first_day, last_day = get_month_range(year, month)
    day_count = (last_day - first_day).days + 1
    days = [first_day + timedelta(days=i) for i in range(day_count)]
    first_weekday = first_day.weekday()  # Monday=0

    # Prepare next/previous month navigation
    prev_month = month - 1 or 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    # Query all shifts for the month
    shifts = Shift.query.filter(
        extract('year', Shift.date) == year,
        extract('month', Shift.date) == month
    ).all()

    # Group shifts by date
    shifts_by_day = defaultdict(list)
    for s in shifts:
        shifts_by_day[s.date].append(s)  # s.date should be a date object

    return render_template(
        'employee_calendar.html',
        current_worker=current_worker,
        days=days,
        first_weekday=first_weekday,
        shifts_by_day=shifts_by_day,
        year=year,
        month=month,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year
    )

@app.route("/dashboard/manager")
@login_required
def dashboard_manager():
    # Get year and month from query params, fallback to today
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)

    today = date.today()
    if not year or not month:
        year, month = today.year, today.month

    # Get month range
    first_day, last_day = get_month_range(year, month)
    day_count = (last_day - first_day).days + 1
    first_weekday = first_day.weekday()

    days = [first_day + timedelta(days=i) for i in range(day_count)]

    # Fetch shifts
    shifts = Shift.query.filter(
        db.extract("year", Shift.date) == year,
        db.extract("month", Shift.date) == month
    ).all()

    # Map shifts by day
    shifts_map = {}
    for shift in shifts:
        shifts_map.setdefault(shift.date.day, []).append(shift)

    # Compute previous/next months
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    return render_template(
        "employee_calendar.html",
        year=year,
        month=month,
        days=days,
        day_count=day_count,
        first_weekday=first_weekday,
        shifts_map=shifts_map,
        current_worker=current_user.worker,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month
    )

@app.route('/add_shift', methods=['GET', 'POST'])
def add_shift():
    workers = Worker.query.all()

    if request.method == 'POST':
        # Raw strings from form
        date_str = request.form['date']
        start_time_str = request.form['start_time']
        end_time_str = request.form['end_time']
        worker_id = request.form['worker_id']

        # Convert strings to proper types
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        start_time = datetime.strptime(start_time_str, "%H:%M").time()
        end_time = datetime.strptime(end_time_str, "%H:%M").time()

        new_shift = Shift(date=date,
                          start_time=start_time,
                          end_time=end_time,
                          worker_id=worker_id)

        db.session.add(new_shift)
        db.session.commit()
        return redirect(url_for('dashboard_manager'))

    return render_template('add_shift.html', workers=workers)

@app.route("/workers", methods=["GET", "POST"])
def manage_workers():
    if request.method == "POST":
        name = request.form.get("name")

        new_worker = Worker(name=name)
        new_user = User(username=name, role="employee")
        password = generate_random_password()
        new_user.set_password(password)
        new_worker.user = new_user

        db.session.add(new_worker)
        db.session.commit()

        flash(f"Worker created. Username: {name}, Password: {password}", "success")

        return redirect(url_for("manage_workers"))

    workers = Worker.query.all()
    return render_template("manage_workers.html", workers=workers)

@app.route("/add_worker", methods=["POST"])
def add_worker():
    name = request.form["name"]
    is_cart_staff = "is_cart_staff" in request.form
    is_turn_grill_staff = "is_turn_grill_staff" in request.form

    # 1️⃣ Create the user
    password = generate_random_password()  # function you already have
    new_user = User(username=name, role="employee")
    new_user.set_password(password)  # hashes the password

    # 2️⃣ Create the worker and link to user
    new_worker = Worker(
        name=name,
        is_cart_staff=is_cart_staff,
        is_turn_grill_staff=is_turn_grill_staff,
        user=new_user
    )

    db.session.add(new_worker)
    db.session.commit()

    flash(f"Worker created. Username: {name}, Password: {password}", "success")
    return redirect(url_for("manage_workers"))

@app.route('/manage/view-passwords')
@login_required
def view_passwords():

    users = User.query.filter(User.role == 'employee').all()
    return render_template('view_passwords.html', users=users)

@app.route('/delete_worker/<int:worker_id>', methods=['POST'])
def delete_worker(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    db.session.delete(worker)
    db.session.commit()
    return redirect(url_for('manage_workers'))

@app.route('/add_shift/<date>', methods=['GET', 'POST'])
def add_shift_with_date(date):
    workers = Worker.query.all()
    if request.method == 'POST':
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        worker_id = request.form['worker_id']

        new_shift = Shift(
            date=datetime.strptime(date, '%Y-%m-%d').date(),
            start_time=datetime.strptime(start_time, '%H:%M').time(),
            end_time=datetime.strptime(end_time, '%H:%M').time(),
            worker_id=worker_id
        )
        db.session.add(new_shift)
        db.session.commit()
        return redirect(url_for('dashboard_manager'))

    return render_template('add_shift_for_date.html', date=date, workers=workers)

@app.route('/clear_schedule', methods=['POST'])
def clear_schedule():
    date_str = request.form.get('start_date')
    if not date_str:
        flash('No date provided.', 'error')
        return redirect(url_for('dashboard_manager'))

    try:
        start_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        end_date = start_date + timedelta(days=7)

        Shift.query.filter(Shift.date >= start_date, Shift.date < end_date).delete()
        db.session.commit()
        flash(f'Schedule cleared for week starting {start_date}.', 'success')
    except Exception as e:
        flash(f'Error clearing schedule: {str(e)}', 'error')

    return redirect(url_for('dashboard_manager'))

@app.route('/generate', methods=['GET', 'POST'])
def generate():
    if request.method == 'POST':
        # Get month and year from the form
        month_str = request.form.get('month')
        year_str = request.form.get('year')

        # Validate input
        try:
            month = int(month_str)
            year = int(year_str)
            if not (1 <= month <= 12):
                raise ValueError
        except (ValueError, TypeError):
            return "Invalid month or year", 400

        # Call your monthly optimizer
        build_monthly_optimizer(year, month)

        return redirect(url_for('dashboard_manager'))  # Or wherever you want to display results

    # Defaults for month/year selector
    current_year = datetime.now().year
    current_month = datetime.now().month

    return render_template(
        'choose_month.html',
        current_month=current_month,
        current_year=current_year
    )

@app.route("/availability", methods=["GET", "POST"])
@login_required
def set_availability():
    # Find the worker profile linked to this user
    worker = Worker.query.filter_by(user_id=current_user.id).first()
    if not worker:
        flash("No worker profile found for this account.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        # Get JSON list from request
        unavailable_days = request.form.get("unavailable_days", "[]")
        try:
            parsed_days = json.loads(unavailable_days)
        except json.JSONDecodeError:
            parsed_days = []
            flash("Invalid date data submitted.", "danger")

        # Save to database as JSON string
        worker.unavailable_days = json.dumps(parsed_days)
        db.session.commit()

        flash("Availability updated successfully.", "success")
        return redirect(url_for("set_availability"))

    # If GET, load existing unavailable days
    try:
        unavailable_days = json.loads(worker.unavailable_days or "[]")
    except json.JSONDecodeError:
        unavailable_days = []

    return render_template("availability.html", unavailable_days=unavailable_days)

@app.route('/toggle_cart_staff/<int:worker_id>', methods=['POST'])
def toggle_cart_staff(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    worker.is_cart_staff = not worker.is_cart_staff
    db.session.commit()
    return redirect(url_for('manage_workers'))

@app.route('/toggle_turn_grill_staff/<int:worker_id>', methods=['POST'])
def toggle_turn_grill_staff(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    worker.is_turn_grill_staff = not worker.is_turn_grill_staff
    db.session.commit()
    return redirect(url_for('manage_workers'))

print(app.url_map)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5001)


