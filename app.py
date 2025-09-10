from flask import Flask, render_template, request, redirect, url_for, Blueprint, jsonify
from models import db, Worker, Shift, User, ShiftTemplate, generate_random_password
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
import random, string



app = Flask(__name__)
app.secret_key = 'yo-gabba-gabba'
from flask import flash
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///schedule.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

from flask_migrate import Migrate
from models import db  # or however you import db

migrate = Migrate(app, db)

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
    month = request.args.get('month', type=int, default=date.today().month)
    year = request.args.get('year', type=int, default=date.today().year)

    # Build month days
    first_day, last_day = get_month_range(year, month)
    day_count = (last_day - first_day).days + 1
    days = [first_day + timedelta(days=i) for i in range(day_count)]
    first_weekday = first_day.weekday()  # Monday=0

    # Prepare next/previous month navigation
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year

    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year

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
    current_worker = Worker.query.filter_by(user_id=current_user.id).first()

    today = date.today()
    month = request.args.get('month', type=int, default=date.today().month)
    year = request.args.get('year', type=int, default=date.today().year)

    # Build month days
    first_day, last_day = get_month_range(year, month)
    day_count = (last_day - first_day).days + 1
    days = [first_day + timedelta(days=i) for i in range(day_count)]
    first_weekday = first_day.weekday()  # Monday=0

    # Prepare next/previous month navigation
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year

    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year

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
        'manager_calendar.html',
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

def generate_unique_username(base_name):
    username = base_name.lower().replace(" ", "")
    candidate = username
    counter = 1
    while User.query.filter_by(username=candidate).first():
        candidate = f"{username}{counter}"
        counter += 1
    return candidate

@app.route("/add_worker", methods=["POST"])
def add_worker():
    name = request.form["name"]
    is_cart_staff = "is_cart_staff" in request.form
    is_turn_grill_staff = "is_turn_grill_staff" in request.form

    # 1️⃣ Create the user
    username = generate_unique_username(name)
    password = generate_random_password()  # function you already have
    new_user = User(username=username, role="employee")
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

    flash(f"Worker created. Username: {username}, Password: {password}", "success")
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

@app.route('/clear_month_schedule/<int:year>/<int:month>', methods=['POST'])
@login_required
def clear_month_schedule(year, month):
    year = int(year)
    month = int(month)
    shifts = Shift.query.filter(
        extract("year", Shift.date) == year,
        extract("month", Shift.date) == month
    ).all()

    for shift in shifts:
        shift.worker_id = None  # unassign worker
    
    db.session.commit()
    flash("All shifts have been unassigned for this month.", "info")
    return redirect(url_for("dashboard_manager"))

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

@app.route("/plan_schedule/<int:year>/<int:month>", methods=["GET", "POST"])
def plan_schedule(year, month):
    if request.method == "POST":
        shift_date = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date()
        template_id = request.form.get("template_id")
        template = ShiftTemplate.query.get(template_id) if template_id else None

        if template:
            new_shift = Shift(
                date=shift_date,
                start_time=template.start_time,
                end_time=template.end_time,
                role_type=template.role_type
            )
            db.session.add(new_shift)
            db.session.commit()

        return redirect(url_for("plan_schedule", year=year, month=month))

    # build calendar days
    days = list(calendar.Calendar().itermonthdates(year, month))

    # query shifts for that month
    shifts = Shift.query.filter(
        extract("year", Shift.date) == year,
        extract("month", Shift.date) == month
    ).all()

    # group shifts by day
    shifts_by_day = {}
    for s in shifts:
        key = s.date.strftime("%Y-%m-%d") if isinstance(s.date, date) else s.date.date().strftime("%Y-%m-%d")
        shifts_by_day.setdefault(key, []).append(s)

    # nav
    prev_month = month - 1 or 12
    next_month = month + 1 if month < 12 else 1
    prev_year = year - 1 if month == 1 else year
    next_year = year + 1 if month == 12 else year

    # ✅ also load available templates for the dropdown
    templates = ShiftTemplate.query.all()

    return render_template(
        "plan_schedule.html",
        year=year,
        month=month,
        days=days,
        shifts_by_day=shifts_by_day,
        prev_month=prev_month,
        next_month=next_month,
        prev_year=prev_year,
        next_year=next_year,
        templates=templates  # pass to template
    )

@app.route("/shift_templates", methods=["GET", "POST"])
def shift_templates():
    if request.method == "POST":
        name = request.form.get("name")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")
        role_type = request.form.get("role_type", "normal")

        template = ShiftTemplate(
            name=name,
            start_time=datetime.strptime(start_time, "%H:%M").time(),
            end_time=datetime.strptime(end_time, "%H:%M").time(),
            role_type=role_type
        )
        db.session.add(template)
        db.session.commit()
        return redirect(url_for("shift_templates"))

    templates = ShiftTemplate.query.all()
    return render_template("shift_templates.html", templates=templates, now=date.today())

@app.route("/add_weekday_shifts/<int:year>/<int:month>", methods=["POST"])
def add_weekday_shifts(year, month):
    weekday = int(request.form.get("weekday"))  # 0=Mon, 6=Sun
    template_id = request.form.get("template_id")
    template = ShiftTemplate.query.get(template_id)

    if not template:
        flash("Invalid template selected.", "danger")
        return redirect(url_for("plan_schedule", year=year, month=month))

    # build all days in this month
    days = list(calendar.Calendar().itermonthdates(year, month))

    # add a shift for each matching weekday that’s in the current month
    for d in days:
        if d.month == month and d.weekday() == weekday:
            new_shift = Shift(
                date=d,
                start_time=template.start_time,
                end_time=template.end_time,
                role_type=template.role_type,
                worker_id=None
            )
            db.session.add(new_shift)

    db.session.commit()
    flash(f"Added {template.name} to all {calendar.day_name[weekday]}s in {month}/{year}.", "success")
    return redirect(url_for("plan_schedule", year=year, month=month))

@app.route("/delete_shift/<int:shift_id>", methods=["POST"])
def delete_shift(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    year = shift.date.year
    month = shift.date.month

    db.session.delete(shift)
    db.session.commit()
    flash("Shift deleted.", "success")

    return redirect(url_for("plan_schedule", year=year, month=month))

@app.route("/delete_all_shifts/<int:year>/<int:month>", methods=["POST"])
def delete_all_shifts(year, month):
    # Delete all shifts in this year/month
    Shift.query.filter(
        extract("year", Shift.date) == year,
        extract("month", Shift.date) == month
    ).delete(synchronize_session=False)

    db.session.commit()
    flash(f"All shifts for {month}/{year} deleted.", "warning")

    return redirect(url_for("plan_schedule", year=year, month=month))

print(app.url_map)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5001)


