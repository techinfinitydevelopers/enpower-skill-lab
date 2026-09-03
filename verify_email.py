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

# ── 3b. The branded HTML ────────────────────────────────────────────────
# Every message goes out as multipart/alternative with the plain text intact,
# plus the logo as an inline part. A template that fails to render, or a cid
# that does not match the attachment, produces an email with a broken image —
# which nobody notices until a principal receives one.
print('\nHTML TEMPLATES')
settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
try:
    built = {}
    mail.outbox = []
    emails.send_onboarding(
        to='t@example.com', name='Anjali Nair', login_id='BV-SA-2026-004',
        password='Enpower@2026', role='SCHOOL_ADMIN',
        school_name='Bright Valley International School', program_name='FSL Programme')
    built['onboarding'] = mail.outbox[0]

    mail.outbox = []
    emails.send_announcement(
        to='t@example.com', name='Rahul Mehta', title='Showcase on 12 September',
        details='Grade 6 and 7 projects will be presented.', role='THINKING_COACH',
        school_name='Bright Valley International School')
    built['announcement'] = mail.outbox[0]

    mail.outbox = []
    emails.send_password_reset(
        to='t@example.com', name='Priya Sharma', role='PROGRAM_COORDINATOR',
        reset_link='https://enpower.techinfinity.link/reset/Mg/abc-123/')
    built['password_reset'] = mail.outbox[0]

    for name, msg in built.items():
        html = msg.alternatives[0][0] if msg.alternatives else ''
        check(f'{name}: has an HTML alternative', bool(html))
        check(f'{name}: keeps the plain-text body', len(msg.body) > 80)
        check(f'{name}: no unrendered template syntax',
              not any(t in html for t in ('{{', '{%', '{#')))
        check(f'{name}: loads the logo over https',
              f'src="{settings.SITE_URL}/static/{emails.LOGO_STATIC_PATH}"' in html)
        # A cid: part is what made Gmail show an attachment chip on every mail.
        check(f'{name}: sends no attachment', not msg.attachments and 'cid:' not in html)
        check(f'{name}: no localhost link', '127.0.0.1' not in html and 'localhost' not in html)
        check(f'{name}: header colour matches the badge tile', '#3a1149' in html)

    ob = built['onboarding'].alternatives[0][0]
    check('onboarding HTML shows the login ID', 'BV-SA-2026-004' in ob)
    check('onboarding HTML shows the password', 'Enpower@2026' in ob)
    check('onboarding HTML names the role and school',
          'School Admin' in ob and 'Bright Valley International School' in ob)
    check('onboarding text also carries the login link', '/login/' in built['onboarding'].body)
    check('reset HTML carries the reset link', 'abc-123' in
          built['password_reset'].alternatives[0][0])
    from pathlib import Path
    badge = Path(settings.BASE_DIR) / 'static' / emails.LOGO_STATIC_PATH
    check('badge file exists in static/', badge.exists(), str(badge))
    collected = Path(settings.STATIC_ROOT) / emails.LOGO_STATIC_PATH
    check('badge is collected into STATIC_ROOT (run collectstatic if not)',
          collected.exists(), str(collected))
finally:
    settings.EMAIL_BACKEND = real_backend
    mail.outbox = []

# ── 3c. The client's wording, line for line ─────────────────────────────
# The client supplied these three templates. Everything below is their copy
# with the placeholders filled in; the assertions exist because the wording is
# theirs to change, not ours, and it has already drifted once (a redesign
# quietly turned "Regards," into "Warm regards,").
print("\nCLIENT'S WORDING  (plain-text body, line for line)")
CLIENT_COPY = {
    'onboarding': [
        'Dear [Recipient Name],',
        'Welcome to [Program Name] – ENpower Skill Lab!',
        'You have been onboarded as School Admin for [School Name].',
        'Your login credentials are:',
        'Login ID: [Email ID]',
        'One-Time Password: [OTP]',
        'Please log in using the above credentials and reset your password after '
        'your first login.',
        'Regards,',
        'Team ENpower Skill Lab',
    ],
    'announcement': [
        'Dear [Recipient Name],',
        'Here’s an important update for [Program Name].',
        '[Announcement Title]',
        '[Brief announcement or event details.]',
        'Program: [Program Name]',
        'School: [School Name]',
        'Your Role: School Admin',
        'For more details, please log in to your ENpower Skill Lab dashboard.',
        'Regards,',
        'Team ENpower Skill Lab',
    ],
    'password_reset': [
        'Dear [Recipient Name],',
        'Your password reset request for [Program Name] – ENpower Skill Lab has '
        'been received.',
        'School: [School Name]',
        'Your Role: School Admin',
        'Please use the link below to reset your password:',
        'Reset Password: [Reset Link]',
        'If you did not request this, please ignore this email.',
        'Regards,',
        'Team ENpower Skill Lab',
    ],
}

settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
try:
    bodies = {}
    bodies_html = {}
    mail.outbox = []
    emails.send_onboarding(
        to='t@example.com', name='[Recipient Name]', login_id='[Email ID]',
        password='[OTP]', role='SCHOOL_ADMIN',
        school_name='[School Name]', program_name='[Program Name]')
    bodies['onboarding'] = mail.outbox[0].body
    bodies_html['onboarding'] = mail.outbox[0].alternatives[0][0]

    mail.outbox = []
    emails.send_announcement(
        to='t@example.com', name='[Recipient Name]', title='[Announcement Title]',
        details='[Brief announcement or event details.]', role='SCHOOL_ADMIN',
        school_name='[School Name]', program_name='[Program Name]')
    bodies['announcement'] = mail.outbox[0].body
    bodies_html['announcement'] = mail.outbox[0].alternatives[0][0]

    mail.outbox = []
    emails.send_password_reset(
        to='t@example.com', name='[Recipient Name]', reset_link='[Reset Link]',
        role='SCHOOL_ADMIN', school_name='[School Name]',
        program_name='[Program Name]')
    bodies['password_reset'] = mail.outbox[0].body
    bodies_html['password_reset'] = mail.outbox[0].alternatives[0][0]

    for name, lines in CLIENT_COPY.items():
        body_lines = [l.strip() for l in bodies[name].splitlines() if l.strip()]
        missing = [l for l in lines if l not in body_lines]
        check(f'{name}: every line of the client copy is present',
              not missing, '; '.join(m[:48] for m in missing[:2]))

        # Anything we added on top, so a reviewer can see it rather than
        # discovering it in a principal's inbox.
        extra = [l for l in body_lines if l not in lines]
        if extra:
            print(f'         (added by us: {" | ".join(e[:60] for e in extra)})')

        # The HTML is a second copy of the same message and had already drifted
        # once: the text said 'Regards,' while the footer still said 'Warm
        # regards,'. Both come from the client's document, so both must match.
        html = bodies_html[name]
        check(f'{name}: HTML sign-off matches the text',
              'Warm regards' not in html and 'Regards,' in html)
finally:
    settings.EMAIL_BACKEND = real_backend
    mail.outbox = []

# ── 4. No path around the gate ──────────────────────────────────────────
# Walks the tree rather than shelling out to `git grep`: this suite is also run
# inside the deployed container, which has the source but no git binary.
print('\nNO BYPASS')
import pathlib                                          # noqa: E402

SKIP_DIRS = {'venv', '.venv', '__pycache__', '.git', 'node_modules', 'staticfiles'}
ALLOWED = {'competencies/emails.py', 'verify_email.py'}

offenders = []
for path in pathlib.Path(settings.BASE_DIR).rglob('*.py'):
    rel = path.relative_to(settings.BASE_DIR).as_posix()
    if any(part in SKIP_DIRS for part in path.parts) or rel in ALLOWED:
        continue
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except OSError:
        continue
    for n, line in enumerate(text.splitlines(), 1):
        if 'send_mail(' in line:
            offenders.append(f'{rel}:{n}')

check('no view calls send_mail directly', not offenders, '; '.join(offenders[:3]))

# ── 5. Every onboarding path is branded, and names the right role ───────
# The gate only helps if the caller passes the role it actually onboards, and
# the branding only helps if every path uses a template: a view that builds its
# own body would quietly send bare text while everything else looks designed.
print('\nONBOARDING PATHS')
import re                                                # noqa: E402

src = open('superadmin/views.py', encoding='utf-8').read()

roles = re.findall(r"send_onboarding\((?:.|\n)*?role='([A-Z_]+)'", src)
check('all five manual onboarding paths use the branded template',
      sorted(roles) == ['PARENT', 'PROGRAM_COORDINATOR', 'SCHOOL_ADMIN',
                        'STUDENT', 'THINKING_COACH'],
      f'found {sorted(roles)}')
check('the password-change confirmation is branded too',
      'send_notice(' in src and "role='SUPER_ADMIN'" in src)
check('no view still hand-builds an email body',
      'email_subject' not in src and 'email_body' not in src)
check('no onboarding email links to localhost',
      '127.0.0.1:8000/login' not in src and 'localhost:8000/login' not in src)

for role, marker in [('Student', 'students are not emailed'),
                     ('Parent', 'parents are not emailed')]:
    check(f'{role} success message falls back to on-screen credentials',
          marker in src)

bulk = open('superadmin/bulk_import.py', encoding='utf-8').read()
check('bulk import routes through competencies.emails',
      'from competencies.emails import send_onboarding' in bulk
      and 'from django.core.mail import send_mail' not in bulk)

# Manual and bulk must produce the same email for one role, or a principal
# onboarded by hand receives a different message from one who was imported.
settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
try:
    mail.outbox = []
    emails.send_onboarding(to='a@example.com', name='A', login_id='ID-1',
                           password='p1', role='SCHOOL_ADMIN', school_name='S')
    manual = mail.outbox[0]
    check('manual and bulk share one template',
          bool(manual.alternatives) and '#3a1149' in manual.alternatives[0][0])

    mail.outbox = []
    emails.send_notice(to='a@example.com', name='A', role='SUPER_ADMIN',
                       heading='Your password has been changed',
                       paragraphs=['Done.'], facts=[('When', 'today')])
    notice = mail.outbox[0]
    check('send_notice renders branded HTML',
          bool(notice.alternatives) and '#3a1149' in notice.alternatives[0][0]
          and '{{' not in notice.alternatives[0][0])
finally:
    settings.EMAIL_BACKEND = real_backend
    mail.outbox = []

# ── 6. Optional live send ───────────────────────────────────────────────
if len(sys.argv) > 1:
    to = sys.argv[1]
    where = sys.argv[2] if len(sys.argv) > 2 else ''
    tag = f' [{where}]' if where else ''
    print(f'\nLIVE SEND  -> {to}')

    # All three templates, so the branding can be checked in a real client
    # rather than inferred from the markup.
    sends = [
        ('onboarding', lambda: emails.send_onboarding(
            to=to, name='Anjali Nair', login_id='BV-SA-2026-004',
            password='Enpower@2026', role='SCHOOL_ADMIN',
            school_name=f'Bright Valley International School{tag}',
            program_name='FSL Programme')),
        ('announcement', lambda: emails.send_announcement(
            to=to, name='Rahul Mehta',
            title=f'Annual Skill Passport Showcase - 12 September{tag}',
            details='All Grade 6 and 7 projects will be presented in the main '
                    'auditorium.\nPlease ensure scores are entered before 10 September.',
            role='THINKING_COACH', school_name='Bright Valley International School',
            program_name='FSL Programme')),
        ('password reset', lambda: emails.send_password_reset(
            to=to, name='Priya Sharma',
            reset_link=f'{getattr(settings, "SITE_URL", "")}/reset/Mg/sample-token/',
            role='PROGRAM_COORDINATOR', program_name='CSL+ Programme')),
    ]
    for label, fn in sends:
        try:
            check(f'ZeptoMail accepted: {label}', fn())
        except Exception as e:
            check(f'ZeptoMail accepted: {label}', False, f'{type(e).__name__}: {e}')
else:
    print('\nLIVE SEND  skipped - pass an address to send one: '
          'python verify_email.py you@example.com')

print('\n' + '=' * 60)
print(f'PASS {len(PASS)}   FAIL {len(FAIL)}')
for f in FAIL:
    print('  FAILED:', f)
sys.exit(1 if FAIL else 0)
