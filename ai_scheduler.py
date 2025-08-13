from datetime import datetime, timedelta, time, date
from models import db, Worker, Shift
import calendar
import json
from pulp import (
    LpProblem, LpVariable, LpBinary, lpSum, LpMinimize, PULP_CBC_CMD
)

# Define the 4 standard shifts
SHIFT_TYPES = {
    "Opener": (time(9, 0), time(15, 0)),
    "Morning Support": (time(11, 0), time(16, 0)),
    "Evening Support": (time(15, 0), time(19, 0)),
    "Closer": (time(15, 0), time(21, 0))
}

def get_month_range(year: int, month: int):
    """Return first_date, last_date of the month."""
    first_day = date(year, month, 1)
    _, last_day_num = calendar.monthrange(year, month)
    last_day = date(year, month, last_day_num)
    return first_day, last_day

def generate_month_shifts(year: int, month: int):
    """Generate all shifts for the month."""
    first_day, last_day = get_month_range(year, month)
    day_count = (last_day - first_day).days + 1

    all_shifts = []
    for i in range(day_count):
        current_date = first_day + timedelta(days=i)
        for shift_type, (start, end) in SHIFT_TYPES.items():
            all_shifts.append({
                'date': current_date,
                'type': shift_type,
                'start': start,
                'end': end
            })
    return all_shifts

def build_monthly_optimizer(year: int, month: int):
    """Build and solve the scheduling problem for a month."""
    workers = Worker.query.all()
    shifts = generate_month_shifts(year, month)

    # Parse unavailable days JSON for each worker
    worker_unavail = {}
    for w in workers:
        try:
            worker_unavail[w.id] = set(json.loads(w.unavailable_days or "[]"))
        except json.JSONDecodeError:
            worker_unavail[w.id] = set()

    prob = LpProblem("Monthly_Shift_Scheduling", LpMinimize)

    # Binary decision variables: x[(worker_id, shift_index)] = 1 if assigned
    x = {}
    for i, shift in enumerate(shifts):
        shift_date_str = shift['date'].strftime("%Y-%m-%d")
        for w in workers:
            if shift_date_str not in worker_unavail[w.id]:
                # Worker is available this day
                x[(w.id, i)] = LpVariable(f"x_{w.id}_{i}", cat=LpBinary)

    # OBJECTIVE: Maximize number of assigned shifts (negative cost = maximize)
    prob += lpSum(x.values())

    # CONSTRAINT: Each shift exactly once
    for i in range(len(shifts)):
        prob += lpSum(
            x[(w.id, i)] for w in workers if (w.id, i) in x
        ) == 1, f"Shift_{i}_coverage"

    # CONSTRAINT: Max 1 shift per worker per day
    for w in workers:
        dates_in_month = set(s['date'] for s in shifts)
        for d in dates_in_month:
            relevant_vars = [
                x[(w.id, i)]
                for i, s in enumerate(shifts)
                if s['date'] == d and (w.id, i) in x
            ]
            if relevant_vars:
                prob += lpSum(relevant_vars) <= 1, f"OneShiftPerDay_w{w.id}_{d}"

    # Solve
    prob.solve(PULP_CBC_CMD(msg=0))

    # Save results
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
    print("✅ Monthly schedule saved.")
