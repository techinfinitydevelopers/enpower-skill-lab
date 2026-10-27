"""Attendance as a family reads it: one badge, one year, no cancelled classes.

Three things the client reported on 2026-10-22, and one nobody had noticed.

    "The attendance badge shows 56 attendances, whereas his project report
     shows 46. Both figures should match."

They are two different windows -- this calendar month, and everything ever --
and only one of them was labelled. Worse, the card saying "this year" was
handed the all-time figure, which has no year in it; true today only because
no school here has a second year of data yet.

    "A student with 100% attendance has received all three badges -- Star,
     Champion and Legend -- instead of only the Legend badge."

The deck gives bands, not floors. 90-94, 95-98, 99-100. The old rule marked
every tier at or below the score, so perfect attendance earned the lot.

And the one found while reading: a coach marks a class "Class Cancelled", the
register saves anyway, and those absences were counting. Children were losing
attendance for classes that never ran.

Everything runs inside a transaction that is rolled back.

Run with:  python verify_attendance_display.py
"""

import os
import re
from datetime import date, timedelta

import django

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'enpower_skill_lab.settings'
    django.setup()

from django.conf import settings

settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

from django.db import transaction

from attendance.models import AttendanceRecord, AttendanceSession
from attendance.services import attendance_badge, student_attendance_stats
from enpower_skill_lab.academic_year import academic_year_for
from parent.models import Parent
from student.models import Student
from student.views import attendance_badge_tiers
from verify_client import HttpsClient as Client

PASSWORD = 'Zz!2026pw'
PASS, FAIL = [], []


def check(label, ok, detail=''):
    (PASS if ok else FAIL).append(label)
    print(f'  {"PASS" if ok else "FAIL"}  {label}'
          f'{("  — " + str(detail)) if detail else ""}')


class Rollback(Exception):
    """Raised once the checks are done, to undo everything they created."""


def sign_in(user):
    user.set_password(PASSWORD)
    user.save(update_fields=['password'])
    client = Client()
    assert client.login(username=user.username, password=PASSWORD), \
        f'could not sign in as {user.username}'
    return client


def text_of(html):
    html = re.sub(r'<(script|style)\b.*?</\1>', ' ', html, flags=re.S | re.I)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))


def earned(percent):
    return [t['name'] for t in attendance_badge_tiers(percent) if t['earned']]


# --------------------------------------------------------------- the badge

def check_bands():
    print('\n1. one badge, the one the score falls in')

    # Both sides of every boundary the deck names.
    expected = {
        100: 'Legend', 99: 'Legend',
        98: 'Champion', 96: 'Champion', 95: 'Champion',
        94: 'Star', 92: 'Star', 90: 'Star',
    }
    for percent, name in expected.items():
        check(f'{percent}% earns {name}', earned(percent) == [name],
              earned(percent))

    for percent in (89, 75, 50, 1, 0):
        check(f'{percent}% earns nothing', earned(percent) == [], earned(percent))

    # The reported fault, stated as the client stated it.
    check('100% no longer earns all three', len(earned(100)) == 1, earned(100))

    # Never two at once, anywhere on the scale.
    many = [p for p in range(0, 101) if len(earned(p)) > 1]
    check('no score anywhere earns more than one badge', not many, many[:5])

    # The bands must not leave a hole a real score could fall into.
    covered = {p for p in range(90, 101) if earned(p)}
    check('every score from 90 to 100 earns something',
          covered == set(range(90, 101)),
          sorted(set(range(90, 101)) - covered))

    # The dashboard's single badge and the page must name the same award.
    for percent in (100, 97, 93, 80):
        one = attendance_badge(percent)
        page = earned(percent)
        check(f'{percent}%: dashboard and badges page agree',
              (one['name'] if one else None) == (page[0] if page else None),
              f'{one and one["name"]} vs {page}')


# ------------------------------------------------------- cancelled classes

def seed_sessions(student, plan):
    """plan = [(days_ago, status, class_status)] -> created sessions."""
    made = []
    for days_ago, status, class_status in plan:
        session = AttendanceSession.objects.create(
            school=student.school, grade=str(student.student_class),
            division=student.division, date=date.today() - timedelta(days=days_ago),
            class_status=class_status)
        AttendanceRecord.objects.create(session=session, student=student,
                                        status=status)
        made.append(session)
    return made


def check_cancelled(student):
    print('\n2. a cancelled class is not a missed class')

    AttendanceRecord.objects.filter(student=student).delete()

    # Four classes held and attended; two cancelled and marked absent.
    seed_sessions(student, [(d, 'present', 'held') for d in (1, 2, 3, 4)]
                  + [(d, 'absent', 'cancelled') for d in (5, 6)])

    stats = student_attendance_stats(student)
    check('the cancelled classes are left out of the total',
          stats['total_sessions'] == 4, stats['total_sessions'])
    check('so attendance reads 100%, not 67%', stats['percent'] == 100,
          stats['percent'])
    check('the month figure leaves them out too',
          stats['monthly_percent'] == 100, stats['monthly_percent'])
    check('and so does the year figure', stats['year_percent'] == 100,
          stats['year_percent'])

    # A real absence still counts. The point is which classes happened, not
    # making everyone look good.
    seed_sessions(student, [(7, 'absent', 'held')])
    stats = student_attendance_stats(student)
    check('a genuine absence still counts', stats['percent'] == 80,
          stats['percent'])

    # Late is attendance, as it always was.
    seed_sessions(student, [(8, 'late', 'held')])
    stats = student_attendance_stats(student)
    check('late still counts as attended', stats['attended'] == 5,
          stats['attended'])


# --------------------------------------------------------- "this year"

def check_year(student):
    print('\n3. "this year" means this academic year')

    AttendanceRecord.objects.filter(student=student).delete()

    today = date.today()
    this_year = academic_year_for(today)

    # One attended this year, and two from a year the student is no longer in.
    seed_sessions(student, [(1, 'present', 'held')])
    old = AttendanceSession.objects.create(
        school=student.school, grade=str(student.student_class),
        division=student.division, date=today - timedelta(days=400),
        class_status='held')
    AttendanceRecord.objects.create(session=old, student=student,
                                    status='absent')
    older = AttendanceSession.objects.create(
        school=student.school, grade=str(student.student_class),
        division=student.division, date=today - timedelta(days=500),
        class_status='held')
    AttendanceRecord.objects.create(session=older, student=student,
                                    status='absent')

    stats = student_attendance_stats(student)
    check('the year named is the current academic year',
          stats['academic_year'] == this_year, stats['academic_year'])
    check('last year is not counted in "this year"',
          stats['year_total'] == 1, stats['year_total'])
    check('so this year reads 100%', stats['year_percent'] == 100,
          stats['year_percent'])
    check('while the all-time figure still sees all three',
          stats['total_sessions'] == 3 and stats['percent'] == 33,
          f"{stats['total_sessions']} sessions, {stats['percent']}%")
    check('the two are different, which is the whole point',
          stats['year_percent'] != stats['percent'])


# ------------------------------------------------- what the pages print

def check_pages(student):
    print('\n4. the pages name which figure they are showing')

    AttendanceRecord.objects.filter(student=student).delete()
    # 3 of 4 this month -> 75%, which earns no badge and is easy to spot.
    seed_sessions(student, [(1, 'present', 'held'), (2, 'present', 'held'),
                            (3, 'present', 'held'), (4, 'absent', 'held')])
    # Plus a year the student has left behind, so the year figure and the
    # all-time figure are different numbers. Without this they are equal and
    # the card could be reading either one -- the check would pass while
    # testing nothing, which is exactly what it did first time.
    old_session = AttendanceSession.objects.create(
        school=student.school, grade=str(student.student_class),
        division=student.division, date=date.today() - timedelta(days=430),
        class_status='held')
    AttendanceRecord.objects.create(session=old_session, student=student,
                                    status='absent')

    stats = student_attendance_stats(student)
    check('the year and all-time figures differ, so the card proves which',
          stats['year_percent'] != stats['percent'],
          f"year {stats['year_percent']}, all-time {stats['percent']}")

    client = sign_in(student.user)

    html = client.get('/student/badges/', follow=True).content.decode(
        'utf-8', 'replace')
    body = text_of(html)
    check('the badges page says which month figure it used',
          f"This month: {stats['monthly_percent']}%" in body,
          body[body.find('This month'):][:40])
    check('and prints the year figure beside it',
          f"{stats['year_percent']}%" in body
          and 'Across the whole year' in body)
    check('and says that is the one on the project report',
          'that is the figure on your Project Report' in body)

    html = client.get('/student/reports/', follow=True).content.decode(
        'utf-8', 'replace')
    found = re.search(r'id="spAtt"[^>]*data-target="([^"]*)"', html)
    shown = found.group(1) if found else None
    check('the project report card shows the year figure',
          shown == str(stats['year_percent']),
          f"card {shown}, year {stats['year_percent']}")
    check('which is no longer the all-time figure by accident',
          'this year' in text_of(html))

    # The parent's copy has to say the same thing about the same child.
    parent = Parent.objects.filter(students=student,
                                   user__isnull=False).first()
    if parent is None:
        check('a parent to read the same child', False)
        return
    html = sign_in(parent.user).get(
        f'/parent/child/{student.id}/passport/', follow=True
    ).content.decode('utf-8', 'replace')
    found = re.search(r'id="spAtt"[^>]*data-target="([^"]*)"', html)
    shown = found.group(1) if found else None
    check("the parent's card shows the same year figure",
          shown == str(stats['year_percent']),
          f"parent {shown}, year {stats['year_percent']}")


def pick_student():
    for s in Student.objects.select_related('user', 'school').filter(
            user__isnull=False, school__isnull=False)[:200]:
        if Parent.objects.filter(students=s, user__isnull=False).exists():
            return s
    return Student.objects.filter(user__isnull=False,
                                  school__isnull=False).first()


def run():
    print('=' * 60)
    print('ATTENDANCE AS A FAMILY READS IT')
    print('=' * 60)

    check_bands()

    student = pick_student()
    if student is None:
        check('a student to work with', False)
    else:
        try:
            with transaction.atomic():
                check_cancelled(student)
                check_year(student)
                check_pages(student)
                raise Rollback
        except Rollback:
            pass

    left = AttendanceSession.objects.filter(
        date=date.today() - timedelta(days=500)).count()
    check('nothing this suite created survived', left == 0, left)

    print(f'\n{"=" * 60}\nPASS {len(PASS)}   FAIL {len(FAIL)}')
    for f in FAIL:
        print(f'  FAILED: {f}')


if __name__ == '__main__':
    run()
