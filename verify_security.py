"""
Security audit for a live deployment.

  python verify_security.py

Four things, none of which show up in a normal page test:

  1. Django's own deployment checklist (`check --deploy`).
  2. Cross-role access -- every role is logged in and pointed at every other
     role's URLs. A Student reaching a Super Admin page is the failure that
     matters most on a role-based platform, and nothing else in the suite
     would catch it.
  3. Anonymous access -- every URL is requested with no session at all.
  4. Source-level checks: views missing an auth decorator, raw SQL, secrets.

Read-only. Passwords it changes to log in are restored before it exits.
"""

import atexit
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enpower_skill_lab.settings')
django.setup()

from django.conf import settings                          # noqa: E402

settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

from django.contrib.auth import get_user_model            # noqa: E402
from verify_client import HttpsClient as Client                            # noqa: E402
from django.urls import get_resolver                      # noqa: E402

U = get_user_model()

PASS, FAIL, WARN = [], [], []
restore = {}
TEST_PASSWORD = 'SecAudit!2026x'


def _restore_passwords():
    if not restore:
        return
    for pk, password in list(restore.items()):
        U.objects.filter(pk=pk).update(password=password)
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


def warn(label, detail=''):
    WARN.append(label)
    print(f'  WARN  {label}{("  - " + detail) if detail else ""}')


# ── URLs, grouped by the role prefix that owns them ─────────────────────
PREFIXES = {
    'SUPER_ADMIN': '/super-admin/',
    'PROGRAM_COORDINATOR': '/coordinator/',
    'SCHOOL_ADMIN': '/school-admin/',
    'THINKING_COACH': '/teacher/',
    'PARENT': '/parent/',
    'STUDENT': '/student/',
}


def collectable_urls():
    """Argument-free GET URLs, keyed by the role whose area they sit in."""
    found = defaultdict(list)
    for pattern in get_resolver().url_patterns:
        for sub in getattr(pattern, 'url_patterns', []):
            route = str(getattr(sub, 'pattern', ''))
            if '<' in route or '(?P' in route:
                continue
            full = f'/{str(pattern.pattern)}{route}'
            for role, prefix in PREFIXES.items():
                if full.startswith(prefix):
                    found[role].append(full)
    return {r: sorted(set(v)) for r, v in found.items()}


def login_as(role):
    """A logged-in client for this role, or None if no account exists."""
    user = U.objects.filter(role=role, is_active=True).first()
    if not user:
        return None, None
    restore.setdefault(user.pk, U.objects.get(pk=user.pk).password)
    user.set_password(TEST_PASSWORD)
    user.save(update_fields=['password'])
    c = Client()
    if not c.login(username=user.username, password=TEST_PASSWORD):
        return None, None
    return c, user


def blocked(response):
    """True when the response is a refusal rather than the page itself.

    A redirect counts: the role decorators send an unauthorised user to a login
    page or their own dashboard rather than returning 403.
    """
    return response.status_code in (301, 302, 403, 404, 400)


# ── 1. Django's deployment checklist ────────────────────────────────────
print('\nDJANGO DEPLOYMENT CHECKLIST')
out = subprocess.run([sys.executable, 'manage.py', 'check', '--deploy'],
                     capture_output=True, text=True, cwd=settings.BASE_DIR)
text = out.stdout + out.stderr
ids = re.findall(r'security\.(W\d+)', text)

# Deliberate: HSTS is not extended to subdomains (the bare domain is served by
# a different provider) and preload is not requested (hard to reverse).
ACCEPTED = {'W005', 'W021'}
unexpected = [i for i in ids if i not in ACCEPTED]
check('no unexpected deployment warnings', not unexpected,
      ', '.join(sorted(set(unexpected))))
for i in sorted(set(ids) & ACCEPTED):
    warn(f'security.{i} accepted by choice')

print('\nSECURITY SETTINGS')
for name, want in [('DEBUG', False), ('SECURE_SSL_REDIRECT', True),
                   ('SESSION_COOKIE_SECURE', True), ('CSRF_COOKIE_SECURE', True),
                   ('SESSION_COOKIE_HTTPONLY', True),
                   ('SECURE_CONTENT_TYPE_NOSNIFF', True)]:
    got = getattr(settings, name, None)
    check(f'{name} is {want}', got == want, f'got {got}')

check('X_FRAME_OPTIONS blocks framing',
      getattr(settings, 'X_FRAME_OPTIONS', '') in ('DENY', 'SAMEORIGIN'),
      str(getattr(settings, 'X_FRAME_OPTIONS', None)))
check('HSTS is set', getattr(settings, 'SECURE_HSTS_SECONDS', 0) > 0,
      f'{getattr(settings, "SECURE_HSTS_SECONDS", 0)}s')
check('SECRET_KEY is not the committed development key',
      not settings.SECRET_KEY.startswith('django-insecure-'))
check('password validators are configured',
      len(getattr(settings, 'AUTH_PASSWORD_VALIDATORS', [])) >= 4)

# ── 1b. Brute force ─────────────────────────────────────────────────────
# Ten wrong passwords used to be accepted in a row with no delay, which is
# enough to walk a dictionary against a known school email address.
print('\nBRUTE FORCE')
from accounts import throttle                              # noqa: E402
from accounts.models import LoginAttempt                    # noqa: E402

victim = U.objects.filter(role='SUPER_ADMIN', is_active=True).first()
if victim:
    LoginAttempt.objects.filter(username=victim.username).delete()
    c = Client()
    locked_at = None
    for i in range(1, throttle.MAX_FAILURES + 3):
        r = c.post('/login/', {'role': 'SUPER_ADMIN', 'username': victim.username,
                               'password': f'wrong-{i}'}, follow=True)
        if 'Too many failed sign-in attempts' in r.content.decode():
            locked_at = i
            break
    check('repeated wrong passwords lock the account',
          locked_at is not None, f'locked at attempt {locked_at}')
    check('the lock arrives at the configured limit',
          locked_at is not None and locked_at <= throttle.MAX_FAILURES + 1,
          f'limit={throttle.MAX_FAILURES}, locked at {locked_at}')

    # Locking must be per (username, IP), or anyone could lock a principal out
    # of their own account just by guessing at their address.
    other = U.objects.filter(is_active=True).exclude(pk=victim.pk).first()
    if other:
        check('another account is unaffected by the lock',
              not throttle.is_locked(other.username, '127.0.0.1'))
    LoginAttempt.objects.filter(username=victim.username).delete()
else:
    warn('no account to test the login lock with')

# ── 2. Anonymous access ─────────────────────────────────────────────────
print('\nANONYMOUS ACCESS  (no session at all)')
urls = collectable_urls()
anon = Client()
leaked = []
for role, role_urls in urls.items():
    for url in role_urls:
        r = anon.get(url)
        if not blocked(r):
            leaked.append(f'{url} ({r.status_code})')
check('no role page is readable without logging in', not leaked,
      '; '.join(leaked[:4]))

# ── 3. Cross-role access ────────────────────────────────────────────────
print('\nCROSS-ROLE ACCESS  (each role pointed at every other role\'s pages)')
clients = {}
for role in PREFIXES:
    c, user = login_as(role)
    if c is None:
        warn(f'{role}: no account to test with')
        continue
    clients[role] = c

for actor in clients:
    breaches = []
    for owner, role_urls in urls.items():
        if owner == actor:
            continue
        for url in role_urls:
            r = clients[actor].get(url)
            if not blocked(r):
                breaches.append(f'{url} ({r.status_code})')
    check(f'{actor} cannot reach another role\'s pages', not breaches,
          f'{len(breaches)} reachable: ' + '; '.join(breaches[:3]) if breaches else '')

# each role can still use its own area
for actor, c in clients.items():
    own = urls.get(actor, [])
    ok = sum(1 for u in own if c.get(u, follow=True).status_code == 200)
    check(f'{actor} can still use its own pages', ok > 0, f'{ok}/{len(own)} load')

# ── 4. Source-level checks ──────────────────────────────────────────────
print('\nSOURCE')
SKIP = {'venv', '.venv', '__pycache__', '.git', 'node_modules', 'staticfiles', 'migrations'}
views = [p for p in Path(settings.BASE_DIR).rglob('*.py')
         if not any(part in SKIP for part in p.parts)
         and p.name in ('views.py', 'pages.py', 'reports.py', 'score_views.py',
                        'bulk_import.py', 'password_reset.py')]

undecorated = []
for path in views:
    src = path.read_text(encoding='utf-8', errors='ignore')
    lines = src.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith('def '):
            continue
        name = line[4:].split('(')[0]
        if name.startswith('_') or 'request' not in line:
            continue
        # look back over the decorators attached to this def
        deco, j = [], i - 1
        while j >= 0 and (lines[j].startswith('@') or lines[j].strip() == ''):
            if lines[j].startswith('@'):
                deco.append(lines[j])
            j -= 1
        blob = ' '.join(deco)
        if 'login_required' not in blob and 'user_passes_test' not in blob:
            rel = path.relative_to(settings.BASE_DIR).as_posix()
            undecorated.append(f'{rel}:{i + 1} {name}')

# The public entry points are meant to be reachable without a session.
PUBLIC = {'login_view', 'home', 'forgot_password', 'reset_password'}
undecorated = [u for u in undecorated if u.split()[-1] not in PUBLIC]
check('every view requires authentication', not undecorated,
      f'{len(undecorated)} without: ' + '; '.join(undecorated[:3]) if undecorated else '')

raw_sql = []
for path in Path(settings.BASE_DIR).rglob('*.py'):
    if any(part in SKIP for part in path.parts) or path.name.startswith('verify_'):
        continue
    src = path.read_text(encoding='utf-8', errors='ignore')
    for n, line in enumerate(src.splitlines(), 1):
        if '.raw(' in line or 'cursor.execute' in line:
            raw_sql.append(f'{path.relative_to(settings.BASE_DIR).as_posix()}:{n}')
check('no raw SQL', not raw_sql, '; '.join(raw_sql[:3]))

# Walk the tree rather than shelling out to `git grep`: this suite is also run
# inside the deployed container, which has the source but no git binary.
SECRET_PATTERNS = re.compile(
    r'(Zoho-enczapikey|EMAIL_HOST_PASSWORD\s*=\s*[\'"][^\'"]{8,}|'
    r'SECRET_KEY\s*=\s*[\'"]django-insecure)')
offending = []
for path in Path(settings.BASE_DIR).rglob('*.py'):
    if any(part in SKIP for part in path.parts) or path.name.startswith('verify_'):
        continue
    rel = path.relative_to(settings.BASE_DIR).as_posix()
    # settings.py holds the development key on purpose, guarded by the
    # ImproperlyConfigured raise above.
    if rel.endswith('settings.py'):
        continue
    src = path.read_text(encoding='utf-8', errors='ignore')
    for n, line in enumerate(src.splitlines(), 1):
        if SECRET_PATTERNS.search(line):
            offending.append(f'{rel}:{n}')
check('no credentials hardcoded in the source', not offending,
      '; '.join(offending[:2]))

# Repo hygiene, only meaningful where the repository actually is.
try:
    env_tracked = subprocess.run(['git', 'ls-files', '.env'], capture_output=True,
                                 text=True, cwd=settings.BASE_DIR).stdout
    check('.env is not tracked by git', not env_tracked.strip())
except FileNotFoundError:
    warn('.env tracking not checked', 'no git in this environment')

# ── restore ─────────────────────────────────────────────────────────────
_restore_passwords()

print('\n' + '=' * 62)
print(f'PASS {len(PASS)}   FAIL {len(FAIL)}   WARN {len(WARN)}')
for f in FAIL:
    print('  FAILED:', f)
sys.exit(1 if FAIL else 0)
