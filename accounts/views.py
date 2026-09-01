from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect, render

from . import throttle

# Where each role lands after signing in. Kept as one table because two places
# need it: the login view, and `home` below.
ROLE_DASHBOARDS = {
    'SUPER_ADMIN': '/super-admin/dashboard/',
    'PROGRAM_COORDINATOR': '/coordinator/dashboard/',
    'SCHOOL_ADMIN': '/school-admin/dashboard/',
    'THINKING_COACH': '/teacher/dashboard/',
    'PARENT': '/parent/dashboard/',
    'STUDENT': '/student/dashboard/',
}


def home(request):
    """The site root.

    Nothing was mapped here, so the main domain answered 404 — which is what a
    visitor saw after the apex redirect landed them on the bare hostname.
    Signed-in visitors go to their own dashboard, everyone else to the login
    page.
    """
    if request.user.is_authenticated:
        target = ROLE_DASHBOARDS.get(getattr(request.user, 'role', None))
        if target:
            return redirect(target)
    return redirect('login')


def login_view(request):
    if request.method == "POST":
        role = request.POST.get("role")
        username = request.POST.get("username")
        password = request.POST.get("password")

        ip = throttle.client_ip(request)

        # Checked before authenticate(), so a locked pair costs no password
        # hashing and gets no timing signal about whether the user exists.
        if throttle.is_locked(username, ip):
            messages.error(
                request,
                f"Too many failed sign-in attempts. Please try again in "
                f"{throttle.minutes_remaining(username, ip)} minutes, or use "
                f"Forgot Password.")
            return redirect('login')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.role != role:
                # The password was right, so this is the account's owner
                # picking the wrong role from the dropdown -- not an attack.
                messages.error(request, "Invalid role for this account.")
                return redirect('login')

            throttle.clear(username, ip)
            login(request, user)

            target = ROLE_DASHBOARDS.get(role)
            if target:
                return redirect(target)
            # A role with no dashboard should not leave the user on a blank
            # page; send them back with something to read.
            messages.error(request, "No dashboard is configured for this role.")
            return redirect('login')

        else:
            throttle.record_failure(username, ip)
            left = throttle.MAX_FAILURES - throttle.recent_failures(username, ip)
            if 0 < left <= 3:
                messages.error(
                    request,
                    f"Invalid credentials. {left} attempt(s) left before this "
                    f"account is locked for a while.")
            else:
                messages.error(request, "Invalid credentials")
            return redirect('login')

    return render(request, 'accounts/login.html')
