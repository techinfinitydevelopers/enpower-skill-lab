"""
Brute-force protection for the login form.

Ten wrong passwords in a row were all accepted with no delay, which is enough
to walk a dictionary against a known school email address.

Attempts are recorded in the database rather than the cache on purpose: the
cache backend here is per-process, so with three gunicorn workers a cache
counter would let roughly three times the intended number of guesses through.

Locking is keyed on (username, IP) rather than username alone. Locking on the
username by itself would let anyone lock a principal out of their own account
by guessing at their address from somewhere else.
"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import LoginAttempt

# Ten wrong guesses inside the window locks that pair out for the same window.
MAX_FAILURES = int(getattr(settings, 'LOGIN_MAX_FAILURES', 10))
WINDOW = timedelta(minutes=int(getattr(settings, 'LOGIN_FAILURE_WINDOW_MINUTES', 15)))


def client_ip(request):
    """Caller's address, honouring the proxy header the platform sits behind.

    X-Forwarded-For is a list; the left-most entry is the original client. It
    is spoofable in general, which is why this is only ever used to *narrow* a
    lock, never to widen access.
    """
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()[:45]
    return (request.META.get('REMOTE_ADDR') or '')[:45]


def recent_failures(username, ip):
    return LoginAttempt.objects.filter(
        username=username[:150], ip_address=ip,
        created_at__gte=timezone.now() - WINDOW,
    ).count()


def is_locked(username, ip):
    """True when this username/IP pair has spent its attempts."""
    if not username:
        return False
    return recent_failures(username, ip) >= MAX_FAILURES


def record_failure(username, ip):
    LoginAttempt.objects.create(username=(username or '')[:150], ip_address=ip)


def clear(username, ip):
    """Drop the record after a correct password, so the count starts fresh."""
    LoginAttempt.objects.filter(username=(username or '')[:150], ip_address=ip).delete()


def minutes_remaining(username, ip):
    """How long until the oldest attempt in the window falls out of it."""
    oldest = LoginAttempt.objects.filter(
        username=username[:150], ip_address=ip,
        created_at__gte=timezone.now() - WINDOW,
    ).order_by('created_at').first()
    if not oldest:
        return 0
    left = (oldest.created_at + WINDOW) - timezone.now()
    return max(1, int(left.total_seconds() // 60) + 1)


def purge_old(keep=timedelta(days=7)):
    """Housekeeping so the table does not grow without bound."""
    LoginAttempt.objects.filter(created_at__lt=timezone.now() - keep).delete()
