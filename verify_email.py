"""
Check the email setup end to end.

  python verify_email.py                 # config + suppression gate, sends nothing
  python verify_email.py you@example.com # the above, then a real test send

The first form is safe to run any time. The second actually hands a message to
ZeptoMail, so use an inbox you can open.
"""

import os
import sys

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enpower_skill_lab.settings')
django.setup()

from django.conf import settings                       # noqa: E402
from django.core import mail                           # noqa: E402

from competencies import emails                        # noqa: E402

PASS, FAIL = [], []


def check(label, ok, detail=''):
    (PASS if ok else FAIL).append(label)
    print(f'  {"PASS" if ok else "FAIL"}  {label}{("  - " + detail) if detail else ""}')


def masked(value):
    if not value:
        return '(empty)'
    return value if len(value) <= 8 else f'{value[:6]}...{value[-4:]} ({len(value)} chars)'


# ── 1. What is configured ───────────────────────────────────────────────
print('\nCONFIGURATION')
print(f'  backend    {settings.EMAIL_BACKEND}')
print(f'  host       {settings.EMAIL_HOST}:{settings.EMAIL_PORT}'
      f'  TLS={settings.EMAIL_USE_TLS} SSL={settings.EMAIL_USE_SSL}')
print(f'  user       {settings.EMAIL_HOST_USER}')
print(f'  password   {masked(settings.EMAIL_HOST_PASSWORD)}')
print(f'  from       {settings.DEFAULT_FROM_EMAIL}')
print(f'  timeout    {getattr(settings, "EMAIL_TIMEOUT", None)}s')
print(f'  site URL   {getattr(settings, "SITE_URL", None)}')
print(f'  suppressed {sorted(settings.EMAIL_SUPPRESSED_ROLES)}')

print('\nCONFIG CHECKS')
check('password is set', bool(settings.EMAIL_HOST_PASSWORD),
      'set EMAIL_HOST_PASSWORD in .env')
check('not still on Mailtrap sandbox', 'mailtrap' not in settings.EMAIL_HOST.lower(),
      settings.EMAIL_HOST)
check('TLS and SSL are not both on',
      not (settings.EMAIL_USE_TLS and settings.EMAIL_USE_SSL))
check('a timeout is set', bool(getattr(settings, 'EMAIL_TIMEOUT', None)))
check('site URL is absolute and not localhost',
      str(getattr(settings, 'SITE_URL', '')).startswith('http')
      and '127.0.0.1' not in str(getattr(settings, 'SITE_URL', ''))
      and 'localhost' not in str(getattr(settings, 'SITE_URL', '')),
      str(getattr(settings, 'SITE_URL', '')))

# ── 2. The gate ─────────────────────────────────────────────────────────
print('\nSUPPRESSION GATE  (who is emailed, who is not)')
BLOCK = ['STUDENT', 'Student', 'student', 'PARENT', 'Parent', 'parent']
ALLOW = ['SCHOOL_ADMIN', 'School Admin', 'THINKING_COACH', 'Thinking Coach',
         'PROGRAM_COORDINATOR', 'Program Coordinator', 'SUPER_ADMIN']

for role in BLOCK:
    check(f'blocked: {role!r}', emails.is_suppressed(role))
for role in ALLOW:
    check(f'allowed: {role!r}', not emails.is_suppressed(role))

# ── 3. The gate actually stops a send ───────────────────────────────────
print('\nGATE UNDER A REAL CALL  (locmem backend, nothing leaves)')
real_backend = settings.EMAIL_BACKEND
settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
try:
    for role, should_send in [('STUDENT', False), ('PARENT', False),
                              ('Student', False), ('Parent', False),
                              ('SCHOOL_ADMIN', True), ('Thinking Coach', True),
                              ('PROGRAM_COORDINATOR', True)]:
        mail.outbox = []
        returned = emails.send_onboarding(
            to='gate-test@example.com', name='Test', login_id='TEST-001',
            password='pw', role=role, school_name='Test School')
        sent = len(mail.outbox)
        check(f'send_onboarding({role!r}) -> {"1 mail" if should_send else "no mail"}',
              sent == (1 if should_send else 0) and returned == should_send,
              f'outbox={sent}, returned={returned}')

    for role, should_send in [('STUDENT', False), ('SUPER_ADMIN', True)]:
        mail.outbox = []
        returned = emails.send_raw('Subject', 'Body', 'gate-test@example.com', role=role)
        check(f'send_raw({role!r}) -> {"1 mail" if should_send else "no mail"}',
              len(mail.outbox) == (1 if should_send else 0) and returned == should_send)

    mail.outbox = []
    emails.send_onboarding(to='', name='X', login_id='X', password='p', role='SUPER_ADMIN')
    check('a missing address sends nothing', len(mail.outbox) == 0)
finally:
    settings.EMAIL_BACKEND = real_backend
    mail.outbox = []

# ── 4. No path around the gate ──────────────────────────────────────────
print('\nNO BYPASS')
import subprocess                                       # noqa: E402
out = subprocess.run(
    ['git', 'grep', '-rn', '--', 'send_mail(', '*.py'],
    capture_output=True, text=True).stdout
offenders = [l for l in out.splitlines()
             if 'competencies/emails.py' not in l and 'verify_email.py' not in l]
check('no view calls send_mail directly', not offenders, '; '.join(offenders[:3]))

# ── 5. Each call site names the right role ──────────────────────────────
# The gate only helps if the caller passes the role it actually onboards. A
# typo here would quietly mail a Student, so the roles are asserted, not
# assumed.
print('\nCALL SITES  (superadmin/views.py)')
import re                                                # noqa: E402

src = open('superadmin/views.py', encoding='utf-8').read()
roles_used = re.findall(r"send_raw\((?:.|\n)*?role='([A-Z_]+)'", src)
expected = ['SCHOOL_ADMIN', 'SUPER_ADMIN', 'STUDENT', 'THINKING_COACH',
            'PARENT', 'PROGRAM_COORDINATOR']
check('all six onboarding sends name a role',
      sorted(roles_used) == sorted(expected),
      f'found {sorted(roles_used)}')

check('no onboarding email still links to localhost',
      '127.0.0.1:8000/login' not in src and 'localhost:8000/login' not in src)

# The two suppressed roles must show credentials on screen instead, or the
# admin never learns the password they are supposed to hand over.
for role, marker in [('Student', 'students are not emailed'),
                     ('Parent', 'parents are not emailed')]:
    check(f'{role} success message falls back to on-screen credentials',
          marker in src)

bulk = open('superadmin/bulk_import.py', encoding='utf-8').read()
check('bulk import routes through competencies.emails',
      'from competencies.emails import send_onboarding' in bulk
      and 'from django.core.mail import send_mail' not in bulk)

# ── 6. Optional live send ───────────────────────────────────────────────
if len(sys.argv) > 1:
    to = sys.argv[1]
    print(f'\nLIVE SEND  -> {to}')
    try:
        ok = emails.send_onboarding(
            to=to, name='Test Recipient', login_id='TEST-0001',
            password='TempPass@123', role='SCHOOL_ADMIN',
            school_name='Test School', program_name='ENpower Skill Lab')
        check('ZeptoMail accepted the message', ok, 'check the inbox, and spam')
    except Exception as e:
        check('ZeptoMail accepted the message', False, f'{type(e).__name__}: {e}')
else:
    print('\nLIVE SEND  skipped - pass an address to send one: '
          'python verify_email.py you@example.com')

print('\n' + '=' * 60)
print(f'PASS {len(PASS)}   FAIL {len(FAIL)}')
for f in FAIL:
    print('  FAILED:', f)
sys.exit(1 if FAIL else 0)
