"""
Check the bulk import: row numbers, streaming progress, and cancel.

  python verify_bulk_import.py

Three things were wrong and none of them showed up in any other suite:

  A failure reported "row 1" when the record was on spreadsheet row 3, because
  the number was the position in the parsed list, not the row in the file. On a
  1290-row upload that is the difference between finding the record and not.

  The progress bar was a timer that crept to 85% on random increments, and the
  row total came from splitting the file on newlines -- meaningless for a
  binary .xlsx.

  There was no way to stop a run.

Everything this creates is removed before it exits.
"""

import atexit
import io
import json
import os
import sys

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enpower_skill_lab.settings')
django.setup()

from django.conf import settings                          # noqa: E402

settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']
settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

from django.contrib.auth import get_user_model            # noqa: E402
from django.core.files.uploadedfile import SimpleUploadedFile   # noqa: E402

from superadmin.bulk_import import SAMPLE_DATA            # noqa: E402
from verify_client import HttpsClient as Client           # noqa: E402

U = get_user_model()
PASS, FAIL = [], []
restore = {}
MARKER = 'zz.bulkcheck'


def _cleanup():
    from school_admin.models import SchoolAdmin
    U.objects.filter(email__startswith=MARKER).delete()
    SchoolAdmin.objects.filter(email__startswith=MARKER).delete()
    for pk, password in list(restore.items()):
        U.objects.filter(pk=pk).update(password=password)
    restore.clear()


atexit.register(_cleanup)


def check(label, ok, detail=''):
    (PASS if ok else FAIL).append(label)
    print(f'  {"PASS" if ok else "FAIL"}  {label}{("  - " + detail) if detail else ""}')


def sheet_with(role, rows):
    """A real downloaded sample with these data rows appended."""
    from openpyxl import load_workbook
    r = admin.get(f'/super-admin/bulk-import/{role}/sample-csv/')
    wb = load_workbook(io.BytesIO(r.content))
    ws = wb.active
    fields = [str(cell.value or '').strip() for cell in ws[2]]
    ws.delete_rows(3, ws.max_row)
    for row in rows:
        ws.append([row.get(f, '') for f in fields])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return SimpleUploadedFile('t.xlsx', buf.read())


su = U.objects.filter(role='SUPER_ADMIN', is_active=True).first()
restore[su.pk] = U.objects.get(pk=su.pk).password
su.set_password('BulkCheck!2026')
su.save(update_fields=['password'])
admin = Client()
assert admin.login(username=su.username, password='BulkCheck!2026')

# ── the stream itself ───────────────────────────────────────────────────
print('\nSTREAMING RESPONSE')
good = {'full_name': 'ZZ Bulk A', 'email': f'{MARKER}.a@example.com',
        'phone': '9876500081', 'gender': 'Female', 'school_name': 'Nope'}
broken = {'full_name': '', 'email': f'{MARKER}.b@example.com',
          'phone': '9876500082', 'gender': 'Female', 'school_name': 'Nope'}
third = {'full_name': 'ZZ Bulk C', 'email': f'{MARKER}.c@example.com',
         'phone': '9876500083', 'gender': 'Male', 'school_name': 'Nope'}

r = admin.post('/super-admin/bulk-import/school_admin/upload-stream/',
               {'csv_file': sheet_with('school_admin', [good, broken, third])})
check('stream responds 200', r.status_code == 200, f'HTTP {r.status_code}')
check('served as ndjson', 'ndjson' in r.headers.get('Content-Type', ''),
      r.headers.get('Content-Type', ''))
check('proxies told not to buffer', r.headers.get('X-Accel-Buffering') == 'no')

events = [json.loads(line) for line in
          b''.join(r.streaming_content).decode().splitlines() if line.strip()]
rows = [e for e in events if e.get('type') == 'row']

check('opens with the row total',
      events[0].get('type') == 'start' and events[0].get('total') == 3,
      str(events[0]))
check('closes with a summary', events[-1].get('type') == 'done')
check('one event per row', len(rows) == 3, str(len(rows)))

# ── the row numbers, which is the whole complaint ───────────────────────
print('\nROW NUMBERS  (the spreadsheet\'s, not the list index)')
check('data rows are reported as 3, 4, 5',
      [e['row'] for e in rows] == [3, 4, 5], str([e['row'] for e in rows]))
failed = [e for e in rows if e['status'] == 'failed']
check('the broken row is named by its own number',
      any(e['row'] == 4 and 'full_name' in (e.get('reason') or '') for e in failed),
      '; '.join(f"row {e['row']}: {e.get('reason')}" for e in failed))
check('every failure carries a reason',
      all(e.get('reason') for e in failed))
check('every row carries the running counts',
      all('success' in e and 'failed' in e for e in rows))

# ── progress is countable from the stream ───────────────────────────────
print('\nPROGRESS')
check('counts only ever move forward',
      [e['success'] + e['failed'] for e in rows] == [1, 2, 3],
      str([e['success'] + e['failed'] for e in rows]))
check('the summary agrees with the rows',
      events[-1]['total'] == len(rows)
      and events[-1]['failed'] == len(failed))

# ── a rejected file still answers usefully ──────────────────────────────
print('\nREJECTED UPLOADS')
r = admin.post('/super-admin/bulk-import/school_admin/upload-stream/', {})
check('no file is refused as JSON, not a stream',
      r.status_code == 400 and 'json' in r.headers.get('Content-Type', ''),
      f'HTTP {r.status_code} {r.headers.get("Content-Type", "")}')
check('and says what was wrong',
      'No file' in json.loads(r.content).get('error', ''),
      json.loads(r.content).get('error', ''))

r = admin.post('/super-admin/bulk-import/school_admin/upload-stream/',
               {'csv_file': SimpleUploadedFile('x.txt', b'not a sheet')})
check('a wrong file type is refused', r.status_code == 400,
      f'HTTP {r.status_code}')

# ── access ──────────────────────────────────────────────────────────────
print('\nACCESS')
anon = Client()
check('anonymous cannot stream an import',
      anon.post('/super-admin/bulk-import/school_admin/upload-stream/',
                {}).status_code in (301, 302, 403, 404))

coach = U.objects.filter(role='THINKING_COACH', is_active=True).first()
if coach:
    restore[coach.pk] = U.objects.get(pk=coach.pk).password
    coach.set_password('BulkCheck!2026')
    coach.save(update_fields=['password'])
    c = Client()
    c.login(username=coach.username, password='BulkCheck!2026')
    check('a coach cannot stream a Super Admin import',
          c.post('/super-admin/bulk-import/school_admin/upload-stream/',
                 {}).status_code in (301, 302, 403, 404))

# ── the modals actually load the shared script ──────────────────────────
print('\nTHE MODALS ARE WIRED')
for url, needles in [
    ('/super-admin/students/', ['bulk-import.js', 'upload-stream', 'biCancelBtn']),
    ('/super-admin/bulk-upload/', ['bulk-import.js', 'upload-stream', 'biCancelBtn']),
]:
    r = admin.get(url, follow=True)
    if r.status_code != 200:
        check(f'{url} loads', False, f'HTTP {r.status_code}')
        continue
    body = r.content.decode(errors='ignore')
    for needle in needles:
        check(f'{url} carries {needle}', needle in body)
    check(f'{url} has no invented progress timer',
          'fakeProgress' not in body and 'readAsText' not in body)

_cleanup()

print('\n' + '=' * 62)
print(f'PASS {len(PASS)}   FAIL {len(FAIL)}')
for f in FAIL:
    print('  FAILED:', f)
sys.exit(1 if FAIL else 0)
