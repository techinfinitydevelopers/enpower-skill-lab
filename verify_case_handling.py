"""A capital letter must not lock anyone out, or empty a class.

Two live faults on 30 September 2026, one root cause. A coach onboarded as
SUJITKUMAR5305@GMAIL.COM could not sign in by typing his address the way he
reads it, because `ModelBackend` compares `username` exactly. A school whose
sheet spelt the section 'c' against a timetable holding 'C' showed its coach an
empty class of 41 students, because the roster compared that exactly too.

Everything here runs inside a transaction that is rolled back, so the database
is unchanged whether it passes or fails.

Run with:  python verify_case_handling.py
"""

import datetime
import os

import django

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'enpower_skill_lab.settings'
    django.setup()

from django.conf import settings

settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

from django.contrib.auth import get_user_model
from django.db import transaction

from accounts import throttle
from accounts.logins import login_exists, normalise_login, resolve_login
from attendance.models import Timetable
from schools.models import School
from student.models import Student
from teacher.views import _class_students
from verify_client import HttpsClient as Client

U = get_user_model()
DOB = datetime.date(2014, 5, 1)
PASSWORD = 'Zz!2026pw'

PASS, FAIL = [], []


def check(label, ok, detail=''):
    (PASS if ok else FAIL).append(label)
    print(f'  {"PASS" if ok else "FAIL"}  {label}'
          f'{("  — " + str(detail)) if detail else ""}')


class Rollback(Exception):
    """Raised once the checks are done, to undo everything they created."""


def sign_in(username, password=PASSWORD):
    """Post the login form the way a browser would, and say where it landed."""
    r = Client().post('/login/', {'role': 'THINKING_COACH',
                                  'username': username,
                                  'password': password}, follow=True)
    return r.request['PATH_INFO']


def check_address_case(coach):
    print('\n1. signing in with an address, in any capitalisation')
    check('the exact spelling still works',
          sign_in(coach.username) == '/teacher/dashboard/')
    check('lower case reaches the same account',
          sign_in(coach.username.lower()) == '/teacher/dashboard/',
          sign_in(coach.username.lower()))
    check('a mixed spelling reaches it too',
          sign_in('Zz.Caps@Example.Com') == '/teacher/dashboard/')
    check('a wrong password is still refused',
          sign_in(coach.username, 'not-the-password') == '/login/')
    check('an address nobody holds is still refused',
          sign_in('zz.nobody@example.com') == '/login/')


def check_reg_ids_untouched():
    print('\n2. registration-ID logins are left exactly as they are')
    U.objects.create_user(username='ZZ-RG-6A-111-27-stu', email='',
                          password=PASSWORD, role='STUDENT')
    check('the exact reg ID signs in',
          Client().login(username='ZZ-RG-6A-111-27-stu', password=PASSWORD))
    check('a lower-cased reg ID resolves to nothing',
          resolve_login('zz-rg-6a-111-27-stu') is None)
    check('normalise_login leaves a reg ID alone',
          normalise_login(' ZZ-RG-6A-111-27-stu ') == 'ZZ-RG-6A-111-27-stu')


def check_lockout_cannot_be_walked(coach):
    print('\n3. the lock-out counts a person, not a spelling')
    ip = '203.0.113.9'
    spellings = (coach.username, coach.username.lower(), 'Zz.Caps@Example.Com')
    for spelling in spellings:
        for _ in range(4):
            throttle.record_failure(spelling, ip)
    n = throttle.recent_failures(coach.username.lower(), ip)
    check(f'{4 * len(spellings)} attempts across {len(spellings)} spellings '
          f'count as one', n == 4 * len(spellings), n)
    check('which is enough to lock the account',
          throttle.is_locked(coach.username, ip))
    throttle.clear(coach.username.lower(), ip)
    check('a correct password clears every spelling',
          throttle.recent_failures(coach.username, ip) == 0)


def check_duplicates_refused(coach):
    print('\n4. an account one keystroke apart is refused')
    check('login_exists ignores case for an address',
          login_exists(coach.username.lower()))
    check('normalise_login lowers an address and trims it',
          normalise_login('  ZZ.Caps@Example.Com ') == 'zz.caps@example.com')
    check('a free address is still free', not login_exists('zz.free@example.com'))


def check_roster_finds_the_other_case(coach):
    print('\n5. the roster finds a section stored in the other case')
    school = School.objects.create(school_name='ZZ Case School',
                                   school_code='ZZCASE')
    Timetable.objects.create(school=school, thinking_coach=coach, grade='6',
                             division='C', program='ZZ Program')
    for i in range(3):
        Student.objects.create(first_name=f'Zed{i}', last_name='Probe',
                               school=school, date_of_birth=DOB,
                               enrollment_date=DOB, student_class='6',
                               division='c', is_active=True,
                               skill_lab_reg_id=f'ZZCASE-{i}')
    check('students holding \'c\' answer a timetable asking for \'C\'',
          _class_students(school, '6', 'C').count() == 3,
          _class_students(school, '6', 'C').count())
    check('a genuinely different section is still excluded',
          _class_students(school, '6', 'D').count() == 0)
    check('an inactive student is still excluded',
          (Student.objects.filter(skill_lab_reg_id='ZZCASE-0')
           .update(is_active=False) or True)
          and _class_students(school, '6', 'C').count() == 2)


def run():
    try:
        with transaction.atomic():
            coach = U.objects.create_user(
                username='ZZ.CAPS@EXAMPLE.COM', email='ZZ.CAPS@EXAMPLE.COM',
                password=PASSWORD, role='THINKING_COACH')

            check_address_case(coach)
            check_reg_ids_untouched()
            check_lockout_cannot_be_walked(coach)
            check_duplicates_refused(coach)
            check_roster_finds_the_other_case(coach)
            raise Rollback
    except Rollback:
        pass

    left = (U.objects.filter(username__istartswith='zz').count()
            + School.objects.filter(school_code='ZZCASE').count()
            + Student.objects.filter(skill_lab_reg_id__startswith='ZZCASE').count())
    check('\n  nothing this suite created survived', left == 0, left)

    print(f'\n{"=" * 60}\nPASS {len(PASS)}   FAIL {len(FAIL)}')
    for f in FAIL:
        print(f'  FAILED: {f.strip()}')


if __name__ == '__main__':
    run()
