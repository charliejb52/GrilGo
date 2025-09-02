import calendar
from datetime import date

def get_month_range(year, month):
    """Return the first and last date objects for a given month."""
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    return first_day, last_day