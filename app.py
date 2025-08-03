from flask import Flask, render_template, request, redirect, url_for
from models import db, Worker, Shift
import calendar
from datetime import datetime, date, timedelta
from sqlalchemy import extract, event
from sqlalchemy.engine import Engine
import sqlite3
from ai_scheduler import build_optimizer



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

@app.route('/')
def calendar_view():
    year = request.args.get('year', type=int, default=datetime.now().year)
    month = request.args.get('month', type=int, default=datetime.now().month)

    # Fix month overflow
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    # get how many days in month
    num_days = calendar.monthrange(year, month)[1]
    first_day = date(year, month, 1)
    start_weekday = first_day.weekday()  # Monday=0

    # build weeks matrix of date objects
    weeks = []
    day_counter = 1
    for _ in range(6):  # max 6 weeks in a month
        week = []
        for i in range(7):
            if len(weeks) == 0 and i < start_weekday:
                week.append(None)
            elif day_counter > num_days:
                week.append(None)
            else:
                week.append(date(year, month, day_counter))
                day_counter += 1
        weeks.append(week)

    # Query shifts for this month
    shifts = Shift.query.filter(
        extract('year', Shift.date) == year,
        extract('month', Shift.date) == month
    ).all()

    # Group shifts by day number
    shifts_by_day = {}
    for shift in shifts:
        day = shift.date.day
        if day not in shifts_by_day:
            shifts_by_day[day] = []
        shifts_by_day[day].append(shift)

    return render_template('calendar.html',
                           weeks=weeks,
                           month=month,
                           year=year,
                           shifts_by_day=shifts_by_day,
                           calendar=calendar)

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
        return redirect(url_for('calendar_view'))

    return render_template('add_shift.html', workers=workers)

@app.route('/add_worker', methods=['GET', 'POST'])
def add_worker():
    if request.method == 'POST':
        name = request.form['name']
        availability = []

        for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
            if request.form.get(f'{day}_off'):
                availability.append(f"{day.capitalize()}:off")
            else:
                start = request.form.get(f'{day}_start')
                end = request.form.get(f'{day}_end')
                if start and end:
                    availability.append(f"{day.capitalize()}:{start}-{end}")

        if name.strip():  # basic validation
            new_worker = Worker(name=name, availability=','.join(availability))
            db.session.add(new_worker)
            db.session.commit()

        return redirect(url_for('add_worker'))

    workers = Worker.query.order_by(Worker.name).all()
    return render_template('manage_workers.html', workers=workers)

@app.route('/delete_worker/<int:worker_id>', methods=['POST'])
def delete_worker(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    db.session.delete(worker)
    db.session.commit()
    return redirect(url_for('add_worker'))

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
        return redirect(url_for('calendar_view'))

    return render_template('add_shift_for_date.html', date=date, workers=workers)

@app.route('/clear_schedule', methods=['POST'])
def clear_schedule():
    date_str = request.form.get('start_date')
    if not date_str:
        flash('No date provided.', 'error')
        return redirect(url_for('calendar_view'))

    try:
        start_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        end_date = start_date + timedelta(days=7)

        Shift.query.filter(Shift.date >= start_date, Shift.date < end_date).delete()
        db.session.commit()
        flash(f'Schedule cleared for week starting {start_date}.', 'success')
    except Exception as e:
        flash(f'Error clearing schedule: {str(e)}', 'error')

    return redirect(url_for('calendar_view'))

@app.route('/generate', methods=['GET', 'POST'])
def generate():
    if request.method == 'POST':
        # Parse the selected date from form
        start_date_str = request.form['start_date']
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            return "Invalid date format", 400

        if start_date.weekday() != 0:  # 0 = Monday
            return "Start date must be a Monday", 400

        build_optimizer(start_date)
        return redirect(url_for('calendar_view'))  # or your schedule view

    return render_template('choose_starting_date.html')

print(app.url_map)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5001)


