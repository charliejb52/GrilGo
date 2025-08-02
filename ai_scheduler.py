from datetime import datetime, timedelta, time
from app import db, Worker, Shift
import calendar

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


def generate_schedule(start_date):
    workers = Worker.query.all()
    print(f"Found {len(workers)} workers in the system.\n")

    worker_data = {
        w.id: {
            'obj': w,
            'availability': parse_worker_availability(w),
            'assigned_shifts': [],
            'total_hours': 0
        } for w in workers
    }

    for w_id, data in worker_data.items():
        print(f"{data['obj'].name} availability:")
        for day, hours in data['availability'].items():
            print(f"  {day}: {hours}")
        print()

    for i in range(7):  # Loop over 7 days
        current_date = start_date + timedelta(days=i)
        weekday = DAYS[current_date.weekday()]
        print(f"\n=== {weekday} ({current_date}) ===")

        for shift_name, (start_time, end_time) in SHIFT_TYPES.items():
            print(f"Trying to assign shift: {shift_name} ({start_time} - {end_time})")
            shift_duration = (datetime.combine(current_date, end_time) -
                              datetime.combine(current_date, start_time)).seconds / 3600

            assigned = False
            for w_id, w_data in worker_data.items():
                worker = w_data['obj']
                avail = w_data['availability'].get(weekday)

                if not avail:
                    print(f"  {worker.name} is OFF")
                    continue

                avail_start, avail_end = avail
                print(f"  {worker.name} available: {avail_start} - {avail_end}")

                if not (avail_start <= start_time and avail_end >= end_time):
                    print(f"    ✖ Shift not fully within availability")
                    continue

                if len(w_data['assigned_shifts']) >= 5:
                    print(f"    ✖ Max shifts reached")
                    continue

                if w_data['total_hours'] + shift_duration > 20:
                    print(f"    ✖ Would exceed 20 hours/week")
                    continue

                conflict = False
                for existing_shift in w_data['assigned_shifts']:
                    gap = abs((datetime.combine(current_date, start_time) -
                               datetime.combine(existing_shift['date'], existing_shift['end'])).total_seconds()) / 3600
                    if gap < 12:
                        conflict = True
                        print(f"    ✖ Conflict with another shift (gap = {gap:.1f}h)")
                        break
                if conflict:
                    continue

                # ✅ Assign shift
                shift = Shift(
                    date=current_date,
                    start_time=start_time,
                    end_time=end_time,
                    worker_id=w_id
                )
                db.session.add(shift)
                w_data['assigned_shifts'].append({'date': current_date, 'start': start_time, 'end': end_time})
                w_data['total_hours'] += shift_duration
                print(f"    ✔ Assigned to {worker.name}")
                assigned = True
                break

            if not assigned:
                print(f"  ⚠ No available worker for {shift_name} on {weekday}")

    db.session.commit()
    print("\n✅ Schedule generation complete.")