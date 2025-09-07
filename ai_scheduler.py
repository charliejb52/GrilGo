from datetime import date
from models import db, Worker, Shift
import json
from pulp import (
    LpProblem, LpVariable, LpBinary, lpSum, LpMinimize, PULP_CBC_CMD
)


def get_month_range(year: int, month: int):
    """Return first_date, last_date of the month."""
    import calendar
    first_day = date(year, month, 1)
    _, last_day_num = calendar.monthrange(year, month)
    last_day = date(year, month, last_day_num)
    return first_day, last_day


def build_monthly_optimizer(year: int, month: int):
    """
    Assigns workers to all shifts already created by the manager for a given month.
    Shifts must already exist in DB (with worker_id = NULL).
    """
    workers = Worker.query.all()

    # Get manager-created, unassigned shifts
    shifts = Shift.query.filter(
        db.extract('year', Shift.date) == year,
        db.extract('month', Shift.date) == month,
        Shift.worker_id.is_(None)
    ).all()

    if not shifts:
        print("⚠️ No unassigned shifts found for this month.")
        return

    # Parse unavailable days JSON for each worker
    worker_unavail = {}
    for w in workers:
        try:
            worker_unavail[w.id] = set(json.loads(w.unavailable_days or "[]"))
        except json.JSONDecodeError:
            worker_unavail[w.id] = set()

    prob = LpProblem("Monthly_Shift_Scheduling", LpMinimize)

    # Binary decision variables: x[(worker_id, shift.id)] = 1 if assigned
    x = {}
    for s in shifts:
        shift_date_str = s.date.strftime("%Y-%m-%d")
        for w in workers:
            # Skip if worker unavailable that day
            if shift_date_str in worker_unavail[w.id]:
                continue

            # Role eligibility filtering
            if s.role_type == "cart" and not getattr(w, "is_cart_staff", False):
                continue
            if s.role_type == "turn_grill" and not getattr(w, "is_turn_grill_staff", False):
                continue

            # If eligible, create decision var
            x[(w.id, s.id)] = LpVariable(f"x_{w.id}_{s.id}", cat=LpBinary)

    # OBJECTIVE: maximize number of assigned shifts
    prob += lpSum(x.values())

    # CONSTRAINT: Each shift exactly once
    for s in shifts:
        prob += lpSum(
            x[(w.id, s.id)] for w in workers if (w.id, s.id) in x
        ) == 1, f"Shift_{s.id}_coverage"

    # CONSTRAINT: Max 1 shift per worker per day
    for w in workers:
        dates_in_month = {s.date for s in shifts}
        for d in dates_in_month:
            relevant_vars = [
                x[(w.id, s.id)]
                for s in shifts
                if s.date == d and (w.id, s.id) in x
            ]
            if relevant_vars:
                prob += lpSum(relevant_vars) <= 1, f"OneShiftPerDay_w{w.id}_{d}"

    # Solve
    prob.solve(PULP_CBC_CMD(msg=0))

    # Save results to DB
    for (w_id, s_id), var in x.items():
        if var.varValue == 1:
            shift = Shift.query.get(s_id)
            shift.worker_id = w_id

    db.session.commit()
    print("✅ Monthly schedule updated with worker assignments.")