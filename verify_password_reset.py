"""
Exercise the forgot-password flow end to end.

  python verify_password_reset.py

Drives the real URLs with the test client and sends nothing: the email backend
is swapped for locmem, so the reset link is read out of the outbox exactly as a
recipient would read it out of their inbox. Every password this touches is put
back before the script exits.
"""

import atexit
import os
import re
import sys

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enpower_skill_lab.settings')
django.setup()

from django.conf import settings                          # noqa: E402

settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']
settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

from django.contrib.auth.tokens import default_token_generator   # noqa: E402
from django.core import mail                              # noqa: E402
from verify_client import HttpsClient as Client                            # noqa: E402
from django.utils.encoding import force_bytes             # noqa: E402
from django.utils.http import urlsafe_base64_encode       # noqa: E402

from accounts.models import User                          # noqa: E402
from accounts.password_reset import RESET_ALLOWED_ROLES   # noqa: E402

PASS, FAIL = [], []
restore = {}          # pk -> original password hash


def _restore_passwords():
    if not restore:
        return
    for pk, password in list(restore.items()):
        User.objects.filter(pk=pk).update(password=password)
    print(f'\n  restored original passwords for {len(restore)} user(s)')
    restore.clear()


# Registered with atexit rather than called at the end. A crash part-way
# through used to leave a real account on the audit password -- which is
# exactly what happened when this suite hit a missing `git` binary inside
# the container and died before the restore line. atexit still runs when
# an exception propagates out.
atexit.register(_restore_passwords)


def check(label, ok, detail=''):
    (PASS if ok else FAIL).append(label)
    print(f'  {"PASS" if ok else "FAIL"}  {label}{("  - " + detail) if detail else ""}')


def remember(user):
    restore.setdefault(user.pk, User.objects.get(pk=user.pk).password)


def request_reset(email):
    """POST the forgot-password form, return (response, reset link or None)."""
    mail.outbox = []
    c = Client()
    r = c.post('/forgot-password/', {'email': email}, follow=True)
    link = None
    if mail.outbox:
        found = re.search(r'https?://\S*/reset-password/[^\s"<]+', mail.outbox[0].body)
        link = found.group(0).rstrip('/') + '/' if found else None
    return r, link


def path_of(link):
    return '/' + link.split('/', 3)[3] if link else None


# ── pages exist ─────────────────────────────────────────────────────────
print('\nPAGES')
c = Client()
r = c.get('/forgot-password/')
check('/forgot-password/ loads', r.status_code == 200, f'status {r.status_code}')
body = r.content.decode()
check('page says who may reset',
      'School Admin' in body and 'Thinking Coach' in body and 'Program Coordinator' in body)
check('page tells Students and Parents what to do instead',
      'Students and Parents' in body)
check('no unrendered template syntax',
      not any(t in body for t in ('{{', '{%', '{#')))

login = c.get('/login/').content.decode()
check('login page Forgot Password link is wired',
      'href="/forgot-password/"' in login,
      'still href="#"' if 'fg-text' in login and '#"' in login else '')

# ── each allowed role can reset ─────────────────────────────────────────
print('\nALLOWED ROLES  (real POST, link read from the outbox)')
for role in RESET_ALLOWED_ROLES:
    user = User.objects.filter(role=role, is_active=True).exclude(email='').first()
    if not user:
        check(f'{role}: an account exists to test with', False, 'no user seeded')
        continue
    remember(user)

    r, link = request_reset(user.email)
    check(f'{role}: request accepted', r.status_code == 200, f'status {r.status_code}')
    check(f'{role}: one email sent', len(mail.outbox) == 1, f'outbox={len(mail.outbox)}')
    check(f'{role}: email carries a reset link', bool(link), str(link))
    if not link:
        continue
    check(f'{role}: link is absolute and points at the site',
          link.startswith(settings.SITE_URL), link[:60])
    html = mail.outbox[0].alternatives[0][0] if mail.outbox[0].alternatives else ''
    check(f'{role}: email is branded', '#3a1149' in html and link in html)

    fresh = Client()
    page = fresh.get(path_of(link))
    check(f'{role}: link opens the reset form', page.status_code == 200
          and 'Set a new password' in page.content.decode())

    new_pw = 'ResetCheck!2026x'
    done = fresh.post(path_of(link),
                      {'new_password': new_pw, 'confirm_password': new_pw}, follow=True)
    check(f'{role}: new password is accepted', done.status_code == 200)
    check(f'{role}: the new password actually works',
          Client().login(username=user.username, password=new_pw))

    # A used link must not work a second time.
    again = Client().get(path_of(link))
    check(f'{role}: the link dies after one use',
          'no longer works' in again.content.decode())

# ── blocked roles ───────────────────────────────────────────────────────
print('\nBLOCKED ROLES  (no email, and the same reply either way)')
for role in ('STUDENT', 'PARENT', 'SUPER_ADMIN'):
    user = User.objects.filter(role=role, is_active=True).exclude(email='').first()
    if not user:
        print(f'  ..    {role}: no account to test with, skipped')
        continue
    r, link = request_reset(user.email)
    check(f'{role}: no reset email sent', len(mail.outbox) == 0, f'outbox={len(mail.outbox)}')
    check(f'{role}: reply does not reveal the account exists',
          'is on its way' in r.content.decode())

    # And a hand-made link for a blocked role must be refused.
    forged = (f'/reset-password/{urlsafe_base64_encode(force_bytes(user.pk))}/'
              f'{default_token_generator.make_token(user)}/')
    check(f'{role}: a forged link is refused',
          'no longer works' in Client().get(forged).content.decode())

# ── unknown address ─────────────────────────────────────────────────────
print('\nUNKNOWN ADDRESS')
r, _ = request_reset('definitely-not-registered-91af@example.com')
check('nothing is sent', len(mail.outbox) == 0)
check('reply is identical to the success case', 'is on its way' in r.content.decode())

print('\nTAMPERED LINKS')
victim = User.objects.filter(role='SCHOOL_ADMIN', is_active=True).exclude(email='').first()
if victim:
    uid = urlsafe_base64_encode(force_bytes(victim.pk))
    for label, url in [
        ('a made-up token', f'/reset-password/{uid}/abc123-notarealtoken/'),
        ('a made-up uid', f'/reset-password/{urlsafe_base64_encode(force_bytes(999999))}/'
                          f'{default_token_generator.make_token(victim)}/'),
        ('rubbish in the uid', '/reset-password/!!!!/abc-123/'),
    ]:
        page = Client().get(url)
        check(f'{label} is refused',
              page.status_code == 200 and 'no longer works' in page.content.decode(),
              f'status {page.status_code}')

print('\nSETTINGS')
check('reset links expire', bool(getattr(settings, 'PASSWORD_RESET_TIMEOUT', None)),
      f'{getattr(settings, "PASSWORD_RESET_TIMEOUT", 0) / 3600:.0f} hours')

# ── put every password back ─────────────────────────────────────────────
_restore_passwords()

print('\n' + '=' * 60)
print(f'PASS {len(PASS)}   FAIL {len(FAIL)}')
for f in FAIL:
    print('  FAILED:', f)
sys.exit(1 if FAIL else 0)
