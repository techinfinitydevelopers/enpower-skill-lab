"""
Throttled wrapper around Django's admin login.

The lockout in accounts/views.py guards the platform's own login form. Django's
admin ships its own login view, so `/admin/login/` was a second door onto the
same accounts with no limit at all -- fifteen wrong passwords in a row were
accepted there while ten locked the front door.

This view is registered at the admin's login path *before* `admin.site.urls`,
so it takes precedence, applies the same lock, and then hands the request to
Django's view unchanged. Nothing about the admin's own behaviour is altered.
"""

from django.contrib import admin, messages
from django.shortcuts import redirect

from . import throttle


def throttled_admin_login(request, extra_context=None):
    username = (request.POST.get('username') or '').strip()
    ip = throttle.client_ip(request)

    # Checked before delegating, so a locked pair never reaches password
    # hashing and gets no timing signal about whether the account exists.
    if request.method == 'POST' and throttle.is_locked(username, ip):
        messages.error(
            request,
            f'Too many failed sign-in attempts. Please try again in '
            f'{throttle.minutes_remaining(username, ip)} minutes.')
        return redirect(request.path)

    response = admin.site.login(request, extra_context)

    if request.method == 'POST':
        # Django's admin login re-renders the form on failure and redirects on
        # success, so the session is the reliable signal either way.
        if request.user.is_authenticated:
            throttle.clear(username, ip)
        else:
            throttle.record_failure(username, ip)

    return response
