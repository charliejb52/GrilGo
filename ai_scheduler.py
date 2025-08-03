from datetime import datetime, timedelta, time
from models import db, Worker, Shift
import calendar
from pulp import LpProblem, LpVariable, LpBinary, lpSum, LpMinimize, PULP_CBC_CMD, LpStatus
from collections import defaultdict

# Define the 4 standard shifts
SHIFT_TYPES = {
    "Opener": (time(9, 0), time(15, 0)),
    "Morning Support": (time(11, 0), time(16, 0)),
    "Evening Support": (time(15, 0), time(19, 0)),
    "Closer": (time(15, 0), time(21, 0))
}

DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

DAY_MAP = {
    'Mon': 0,
    'Tue': 1,
    'Wed': 2,
    'Thu': 3,
    'Fri': 4,
    'Sat': 5,
    'Sun': 6
}

def parse_worker_availability(worker):
    avail = {}
    if worker.availability:
        for entry in worker.availability.split(','):
            if ':' not in entry:
                continue  # Skip malformed entry
            try:
                day_abbr, value = entry.split(':', 1)
                day_abbr = day_abbr.strip()
                day = DAY_MAP.get(day_abbr)
                if day is None:
                    continue  # Unknown day abbreviation

                if value.strip().lower() == 'off':
                    avail[day] = None
                else:
                    start_str, end_str = value.split('-')
                    avail[day] = (
                        datetime.strptime(start_str.strip(), '%H:%M').time(),
                        datetime.strptime(end_str.strip(), '%H:%M').time()
                    )
            except ValueError:
                continue  # Skip any malformed entry
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

    for i, shift in enumerate(shifts):
        print(f"Shift {i}: {shift['date']} {shift['start']}–{shift['end']}")

    # Parse availability once
    worker_avail = {
        w.id: parse_worker_availability(w)
        for w in workers
    }

    prob = LpProblem("Shift_Scheduling", LpMinimize)

    # Binary decision variables
    x = {}
    for i, shift in enumerate(shifts):
        for w in workers:
            avail = worker_avail[w.id].get(shift['date'].weekday())  # 0=Monday ... 6=Sunday
            if not avail:
                continue

            avail_start, avail_end = avail
            if avail_start <= shift['start'] and avail_end >= shift['end']:
                x[(w.id, i)] = LpVariable(f"x_{w.id}_{i}", cat=LpBinary)

    print(f"✅ Created {len(x)} eligible assignment variables.")

    for w in workers:
        print(f"Worker {w.id} ({w.name}) availability:")
        for day, times in worker_avail[w.id].items():
            print(f"  {day}: {times}")

    if not x:
        print("⚠️ No valid worker-shift combinations found. Check availability formats.")
        return

    # OBJECTIVE: MAXIMIZE total number of assigned shifts (you can change this)
    prob += lpSum(x.values())

    # CONSTRAINT: Every shift must be assigned to exactly one worker
    for i in range(len(shifts)):
        prob += lpSum(x[(w.id, i)] for w in workers if (w.id, i) in x) == 1, f"Shift_{i}_coverage"

    # CONSTRAINT: No worker can be assigned more than one shift per day
    for w in workers:
        for date in set(shift['date'] for shift in shifts):
            relevant_vars = [
                x[(w.id, i)]
                for i, shift in enumerate(shifts)
                if shift['date'] == date and (w.id, i) in x
            ]
            if relevant_vars:
                prob += lpSum(relevant_vars) <= 1, f"OneShiftPerDay_worker{w.id}_{date}"
    
    # SOLVE

    prob.solve(PULP_CBC_CMD())

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