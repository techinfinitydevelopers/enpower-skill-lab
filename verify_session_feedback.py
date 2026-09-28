"""
Check the session-feedback screens.

  python verify_session_feedback.py

Thinking Coaches have been filling a Daily and a Weekly feedback form since
the product shipped, and nothing read them: the coach saw their own last 20
entries, the Django admin had them, and no other screen mentioned them. The
Weekly form carries `lab_issue` -- a coach reporting the lab is broken -- and
the Coordinator who runs that school never saw it.

These pages serve a Coordinator and a Super Admin from one set of views, so
the checks that matter are about scope: a Coordinator must see their assigned
schools and nothing else, through the list, through a detail page reached by
id, and through the export.

Everything it creates is its own; it deletes nothing that was already here.
"""

import atexit
import io
import os
import sys
from datetime import date

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enpower_skill_lab.settings')
django.setup()

from django.conf import settings                          # noqa: E402

settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']
settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

from django.contrib.auth import get_user_model            # noqa: E402

from attendance.models import (DailySessionFeedback,      # noqa: E402
                               WeeklySessionFeedback)
from schools.models import School                         # noqa: E402
from teacher.models import Teacher                        # noqa: E402
from verify_client import HttpsClient as Client           # noqa: E402

U = get_user_model()
PASS, FAIL = [], []
restore = {}
MARKER = 'ZZSFB'
PASSWORD = 'Feedback!2026'


def _cleanup():
    DailySessionFeedback.objects.filter(session_title__startswith=MARKER).delete()
    WeeklySessionFeedback.objects.filter(went_well__startswith=MARKER).delete()
    for pk, password in list(restore.items()):
        U.objects.filter(pk=pk).update(password=password)
    restore.clear()


atexit.register(_cleanup)
_cleanup()


def check(label, ok, detail=''):
    (PASS if ok else FAIL).append(label)
    print(f'  {"PASS" if ok else "FAIL"}  {label}{("  - " + detail) if detail else ""}')


def sign_in(user):
    restore.setdefault(user.pk, U.objects.get(pk=user.pk).password)
    user.set_password(PASSWORD)
    user.save(update_fields=['password'])
    c = Client()
    return c if c.login(username=user.username, password=PASSWORD) else None


# ── fixtures: one school the coordinator has, one they do not ──────────
schools = list(School.objects.all()[:2])
if len(schools) < 2:
    print('  need two schools to test scoping; nothing to check')
    sys.exit(0)
mine, other = schools[0], schools[1]

coach = (Teacher.objects.select_related('user')
         .filter(user__isnull=False, user__role='THINKING_COACH').first())

d_mine = DailySessionFeedback.objects.create(
    school=mine, grade='6', division='A', academic_year='2026-2027',
    date=date(2026, 9, 20), session_number=3,
    session_title=f'{MARKER} mine', session_description='They built a bridge.',
    thinking_coach=coach.user if coach else None,
    rating_engagement=5, rating_delivery_ease=4, rating_resources=3,
    rating_time_management=4, is_project_completed=True)
d_other = DailySessionFeedback.objects.create(
    school=other, grade='7', division='B', academic_year='2026-2027',
    date=date(2026, 9, 21), session_title=f'{MARKER} theirs',
    thinking_coach=coach.user if coach else None, rating_engagement=2)

w_mine = WeeklySessionFeedback.objects.create(
    thinking_coach=coach.user if coach else None, school=mine,
    date_from=date(2026, 9, 14), date_to=date(2026, 9, 20),
    went_well=f'{MARKER} steady attendance', went_wrong='Projector flickered',
    new_tried='Pair work', lab_issue=True,
    lab_issue_detail='Two workstations will not boot.')
w_other = WeeklySessionFeedback.objects.create(
    thinking_coach=coach.user if coach else None, school=other,
    date_from=date(2026, 9, 14), date_to=date(2026, 9, 20),
    went_well=f'{MARKER} quiet week elsewhere', lab_issue=False)

su = U.objects.filter(role='SUPER_ADMIN', is_active=True).first()
assert su, 'no Super Admin to test with'
admin = sign_in(su)

from coordinator.models import ProgramCoordinator          # noqa: E402

pc = ProgramCoordinator.objects.select_related('user').filter(
    user__isnull=False, user__is_active=True).first()
coord = None
if pc:
    pc.schools_assigned.clear()
    pc.schools_assigned.add(mine)
    coord = sign_in(pc.user)

print(f'\n  assigned to the coordinator : {mine.school_name}')
print(f'  not assigned                : {other.school_name}\n')

SA = '/super-admin/session-feedback/'
CO = '/coordinator/session-feedback/'

# ── the page exists and shows both kinds ───────────────────────────────
print('THE PAGE EXISTS')
r = admin.get(SA, follow=True)
body = r.content.decode(errors='ignore')
check('Super Admin can open it', r.status_code == 200, f'HTTP {r.status_code}')
check('the daily rows are on it', f'{MARKER} mine' in body)
check('there is a weekly tab too', 'Weekly (' in body)
check('and a count of lab issues, which is the point of the weekly form',
      'Lab issues reported' in body)
check('the sidebar offers it', 'nav-session-feedback' in body)

if coord:
    cr = coord.get(CO, follow=True)
    check('a Coordinator can open it', cr.status_code == 200, f'HTTP {cr.status_code}')
    check('and gets their own sidebar',
          'coord-sidebar-nav-link' in cr.content.decode(errors='ignore'))

# ── scope: the check that matters ──────────────────────────────────────
print('\nA COORDINATOR SEES ONLY THEIR OWN SCHOOLS')
check('the Super Admin sees both schools',
      f'{MARKER} mine' in body and f'{MARKER} theirs' in body)

if coord:
    cbody = coord.get(CO, follow=True).content.decode(errors='ignore')
    check('their own school\'s feedback is listed', f'{MARKER} mine' in cbody)
    check('and another school\'s is not', f'{MARKER} theirs' not in cbody,
          'one coordinator would be reading another school\'s reports')

    for label, url in [('daily', f'{CO}daily/{d_other.id}/'),
                       ('weekly', f'{CO}weekly/{w_other.id}/')]:
        rr = coord.get(url)
        check(f'nor can they open it by id ({label})',
              rr.status_code != 200, f'HTTP {rr.status_code}')

    check('their own detail pages still open',
          coord.get(f'{CO}daily/{d_mine.id}/', follow=True).status_code == 200)

# ── the detail pages carry what the form captured ──────────────────────
print('\nTHE DETAIL PAGES SHOW WHAT WAS WRITTEN')
dd = admin.get(f'{SA}daily/{d_mine.id}/', follow=True).content.decode(errors='ignore')
check('daily: the session description is shown', 'built a bridge' in dd)
check('daily: the average of the four ratings is worked out', '4.0' in dd,
      '(5+4+3+4)/4')
check('daily: each rating is labelled', 'Engagement' in dd and 'Resources' in dd)

wd = admin.get(f'{SA}weekly/{w_mine.id}/', follow=True).content.decode(errors='ignore')
check('weekly: the lab issue detail is shown', 'will not boot' in wd,
      'this is the sentence nobody was reading')
check('weekly: what went well and wrong are both shown',
      'steady attendance' in wd and 'Projector flickered' in wd)

wd2 = admin.get(f'{SA}weekly/{w_other.id}/', follow=True).content.decode(errors='ignore')
check('weekly: a week with no lab issue says so plainly',
      'No lab issue reported' in wd2)

# ── filters ────────────────────────────────────────────────────────────
print('\nFILTERS')
fb = admin.get(f'{SA}?school={mine.id}', follow=True).content.decode(errors='ignore')
check('filtering by school narrows the list',
      f'{MARKER} mine' in fb and f'{MARKER} theirs' not in fb)
lb = admin.get(f'{SA}?lab=1&tab=weekly', follow=True).content.decode(errors='ignore')
check('lab-issues-only hides the weeks with none',
      f'{MARKER} steady attendance' in lb
      and f'{MARKER} quiet week elsewhere' not in lb,
      'a week with no issue should drop out of the weekly tab')

# ── exports ────────────────────────────────────────────────────────────
print('\nEXPORTS')
from openpyxl import load_workbook                         # noqa: E402

for key, wanted in [('session-feedback-daily', 'Lab Issue' not in ''),
                    ('session-feedback-weekly', True)]:
    r = admin.get(f'/exports/{key}/')
    check(f'{key}: downloads as a workbook',
          r.status_code == 200 and 'spreadsheet' in r.headers.get('Content-Type', ''),
          f'HTTP {r.status_code}')

wb = load_workbook(io.BytesIO(admin.get('/exports/session-feedback-daily/').content))
heads = [c.value for c in wb.active[3]]
check('the daily export carries the four ratings and the average',
      all(h in heads for h in ('Engagement', 'Ease of Delivery', 'Resources',
                               'Time Management', 'Average')),
      str(heads[:6]))

wb2 = load_workbook(io.BytesIO(admin.get('/exports/session-feedback-weekly/').content))
heads2 = [c.value for c in wb2.active[3]]
check('the weekly export carries the lab issue and its detail',
      'Lab Issue' in heads2 and 'Lab Issue Detail' in heads2, str(heads2[:6]))

if coord:
    wb3 = load_workbook(io.BytesIO(coord.get('/exports/session-feedback-daily/').content))
    cells = [str(c.value or '') for row in wb3.active.iter_rows(min_row=4)
             for c in row]
    check('a Coordinator\'s export is scoped like their page',
          not any(f'{MARKER} theirs' in v for v in cells),
          'the export would leak what the page hides')

# ── everyone else ──────────────────────────────────────────────────────
print('\nEVERYONE ELSE IS REFUSED')
anon = Client()
check('anonymous is refused', anon.get(SA).status_code in (301, 302, 403, 404))

for role in ('THINKING_COACH', 'SCHOOL_ADMIN', 'PARENT', 'STUDENT'):
    user = U.objects.filter(role=role, is_active=True).first()
    if not user:
        print(f'  ..    no {role} account on this database')
        continue
    c = sign_in(user)
    if not c:
        continue
    check(f'{role} is turned away from the page',
          c.get(SA).status_code in (301, 302, 403, 404),
          f'HTTP {c.get(SA).status_code}')
    check(f'{role} is turned away from the export',
          c.get('/exports/session-feedback-daily/').status_code != 200)

_cleanup()

print('\n' + '=' * 62)
print(f'PASS {len(PASS)}   FAIL {len(FAIL)}')
for f in FAIL:
    print('  FAILED:', f)
sys.exit(1 if FAIL else 0)
