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
from accounts.logins import (login_exists, normalise_login, resolve_login,
                            sync_login_email)
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


def check_login_follows_the_profile():
    """Changing a profile's address has to move the login with it.

    The three edit forms wrote the new address onto the profile row and
    stopped. Sign-in reads `User.username`, so the list showed one address
    while a different one was the only one that worked, and the person got
    "Invalid credentials" -- the same words as a wrong password.

    BKG Global School's principal lived in that gap for two months: her
    profile read principal@bkgglobalschool.com and no account by that name
    existed at all.
    """
    print('\n6. the login follows the profile address')

    user = U.objects.create_user(username='zz.old@example.com',
                                 email='zz.old@example.com',
                                 password=PASSWORD, role='SCHOOL_ADMIN')

    moved = sync_login_email(user, 'ZZ.New@Example.com')
    user.refresh_from_db()
    check('the username moves to the new address', moved
          and user.username == 'zz.new@example.com', user.username)
    check('and so does the email field', user.email == 'zz.new@example.com',
          user.email)
    check('the new address can sign in',
          Client().login(username='zz.new@example.com', password=PASSWORD))
    check('the old one cannot, which is the point',
          not Client().login(username='zz.old@example.com',
                             password=PASSWORD))
    check('the password is untouched by the move',
          user.check_password(PASSWORD))

    check('saying the same address again changes nothing',
          sync_login_email(user, 'zz.new@example.com') is False)

    # A registration ID is not an address and must never be overwritten by
    # one, so the helper refuses anything that is not email-shaped.
    student = U.objects.create_user(username='ZZCASE-9-stu',
                                    password=PASSWORD, role='STUDENT')
    check('a blank address is ignored', sync_login_email(student, '') is False)
    check('and so is something that is not an address',
          sync_login_email(student, 'not-an-address') is False)
    student.refresh_from_db()
    check('the registration ID is still the login',
          student.username == 'ZZCASE-9-stu', student.username)

    # Two people cannot share a login. Letting the save fail on the unique
    # constraint would show the Super Admin a database error, not a reason.
    other = U.objects.create_user(username='zz.taken@example.com',
                                  email='zz.taken@example.com',
                                  password=PASSWORD, role='THINKING_COACH')
    try:
        sync_login_email(user, 'ZZ.Taken@Example.com')
        check('an address another account holds is refused', False)
    except ValueError as e:
        check('an address another account holds is refused', True)
        check('and the message names who holds it',
              'already the login' in str(e), str(e)[:70])
    user.refresh_from_db()
    check('the refused move left the login alone',
          user.username == 'zz.new@example.com', user.username)
    other.delete()

    # A profile switched off while its login stays on is not switched off.
    sync_login_email(user, 'zz.new@example.com', is_active=False)
    user.refresh_from_db()
    check('deactivating the profile deactivates the login',
          not user.is_active)
    check('and a deactivated login cannot sign in',
          not Client().login(username='zz.new@example.com',
                             password=PASSWORD))
    sync_login_email(user, 'zz.new@example.com', is_active=True)
    user.refresh_from_db()
    check('switching it back on lets them in again',
          user.is_active
          and Client().login(username='zz.new@example.com',
                             password=PASSWORD))

    # And the forms have to call it, or none of the above reaches anybody.
    views = open('superadmin/views.py', encoding='utf-8').read()
    check('all three edit forms move the login',
          views.count('sync_login_email(') == 3,
          str(views.count('sync_login_email(')))
    check('the coordinator form no longer moves the email on its own',
          'coordinator.user.email = coordinator.official_email' not in views)


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
            check_login_follows_the_profile()
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
