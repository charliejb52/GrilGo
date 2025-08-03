from datetime import datetime, timedelta, time
from models import db, Worker, Shift
import calendar
from pulp import LpProblem, LpVariable, LpBinary, lpSum, LpMinimize
from collections import defaultdict

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

    prob = LpProblem("Shift_Scheduling", LpMinimize)

    # Binary decision variables
    x = {}
    for i, shift in enumerate(shifts):
        shift_day = shift['date'].strftime('%A')
        for w in workers:
            avail = worker_avail[w.id].get(shift_day)
            if not avail:
                continue

            avail_start, avail_end = avail
            if avail_start <= shift['start'] and avail_end >= shift['end']:
                x[(w.id, i)] = LpVariable(f"x_{w.id}_{i}", cat=LpBinary)

    # OBJECTIVE: Minimize total number of assigned shifts (you can change this)
    prob += lpSum(x.values()), "Minimize_total_assignments"

    # CONSTRAINT 1: Every shift must be assigned to exactly one worker
    for i in range(len(shifts)):
        prob += lpSum(x[(w.id, i)] for w in workers if (w.id, i) in x) == 1, f"Shift_{i}_coverage"

    # CONSTRAINT 2: Max 5 shifts per worker
    for w in workers:
        prob += lpSum(x[(w.id, i)] for i in range(len(shifts)) if (w.id, i) in x) <= 5, f"Max_shifts_{w.id}"

    # CONSTRAINT 3: Max ~20 hours per worker (you can fine-tune this threshold)
    for w in workers:
        prob += lpSum(
            ((datetime.combine(start_date, shifts[i]['end']) -
              datetime.combine(start_date, shifts[i]['start'])).seconds / 3600) * x[(w.id, i)]
            for i in range(len(shifts)) if (w.id, i) in x
        ) <= 20, f"Max_hours_{w.id}"

    # CONSTRAINT 4: No worker can be assigned more than one shift per day
    for w in workers:
        shifts_by_day = defaultdict(list)
        for i, shift in enumerate(shifts):
            if (w.id, i) in x:
                shifts_by_day[shift['date']].append(x[(w.id, i)])
        for shift_date, vars_on_date in shifts_by_day.items():
            prob += lpSum(vars_on_date) <= 1, f"Max_one_shift_per_day_w{w.id}_{shift_date}"

    # SOLVE
    prob.solve()

    # SAVE assigned shifts to DB
    for (w_id, i), var in x.items():
        if var.varValue == 1:
            shift = shifts[i]
            new_shift = Shift(
                date=shift['date'],
                start_time=shift['start'],
                end_time=shift['end'],
                worker_id=w_id
            )
            db.session.add(new_shift)

    db.session.commit()
    print("✅ Optimized schedule saved.")