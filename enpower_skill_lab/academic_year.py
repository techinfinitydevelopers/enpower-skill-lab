"""What academic year is it right now.

Nothing in this project knew. Four model fields and two views each carried the
literal string '2025-2026' as their default, so every class, timetable and
session created after June 2026 was stamped a year behind -- which is why the
Super Admin's 2026-2027 filter found nothing and the School Admin's Class
Overview still read 2025-2026. The dropdowns were right; the rows were not.

Indian school years run April to March, so April is the turn. A date in
January 2027 still belongs to 2026-2027.

Deliberately free of model imports: `schools` and `attendance` both hold a
copy of the choices list and neither imports the other, so this has to sit
below both.
"""

from datetime import date

# The month the new year begins in. April is the Indian convention; schools
# whose sessions start in June are still inside the April-March year.
START_MONTH = 4


def current_academic_year(today=None):
    """'2026-2027' for any date from April 2026 to March 2027."""
    today = today or date.today()
    start = today.year if today.month >= START_MONTH else today.year - 1
    return f'{start}-{start + 1}'


def academic_year_for(when):
    """The year a given date falls in, or None when there is no date.

    Used to tell what a row *should* say when it was stamped with a default
    instead of a real year -- a timetable running from June 2026 belongs to
    2026-2027 whatever its stored value claims.
    """
    return current_academic_year(when) if when else None


def academic_year_choices(back=3, forward=1, today=None):
    """Years worth offering in a dropdown, oldest first.

    Generated rather than typed out, because a hand-written list is a list
    that stops: both Class List dropdowns ran out at 2025-2026 while the
    schools had already moved on.
    """
    start = int(current_academic_year(today).split('-')[0])
    return [(f'{y}-{y + 1}', f'{y}-{y + 1}')
            for y in range(start - back, start + forward + 1)]
