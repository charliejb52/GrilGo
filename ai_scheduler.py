from datetime import datetime, timedelta, time
from app import db, Worker, Shift
import calendar
from pulp import LpProblem, LpVariable, LpBinary, lpSum, LpMinimize

# Define the 4 standard shifts
SHIFT_TYPES = {
    "Opener": (time(9, 0), time(15, 0)),
    "Morning Support": (time(11, 0), time(16, 0)),
    "Evening Support": (time(15, 0), time(19, 0)),
    "Closer": (time(15, 0), time(21, 0))
}

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

DAY_MAP = {
    'Mon': 'Monday',
    'Tue': 'Tuesday',
    'Wed': 'Wednesday',
    'Thu': 'Thursday',
    'Fri': 'Friday',
    'Sat': 'Saturday',
    'Sun': 'Sunday'
}

def parse_worker_availability(worker):
    avail = {}
    if worker.availability:
        for entry in worker.availability.split(','):
            if ':' not in entry:
                continue  # Skip malformed entry
            try:
                day_abbr, value = entry.split(':', 1)
                day = DAY_MAP.get(day_abbr.strip(), day_abbr.strip())
                if value.strip().lower() == 'off':
                    avail[day] = None
                else:
                    start_str, end_str = value.split('-')
                    avail[day] = (
                        datetime.strptime(start_str.strip(), '%H:%M').time(),
                        datetime.strptime(end_str.strip(), '%H:%M').time()
                    )
            except ValueError:
                continue  # Skip any badly formatted availability
    return avail

def generate_week_shifts(start_date):
    all_shifts = []
    for i in range(7):
        current_date = start_date + timedelta(days=i)
        for shift_type, (start, end) in SHIFT_TYPES.items():
            all_shifts.append({
                'date': current_date,
                'type': shift_type,
                'start': start,
                'end': end
            })
    return all_shifts

def build_optimizer(start_date):
    workers = Worker.query.all()
    shifts = generate_week_shifts(start_date)

    # Parse availability once
    worker_avail = {
        w.id: parse_worker_availability(w)
        for w in workers
    }

    prob = LpProblem("Shift_Scheduling", LpMinimize)  # We’ll define the objective later

    # Binary decision variables: x[(w.id, i)] = 1 if worker w is assigned to shift i
    x = {}
    for i, shift in enumerate(shifts):
        shift_day = shift['date'].strftime('%A')  # e.g., 'Monday'
        for w in workers:
            avail = worker_avail[w.id].get(shift_day)
            if not avail:
                continue  # worker is OFF that day

            avail_start, avail_end = avail
            if avail_start <= shift['start'] and avail_end >= shift['end']:
                x[(w.id, i)] = LpVariable(f"x_{w.id}_{i}", cat=LpBinary)

    return prob, x, workers, shifts, worker_avail