from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect, render

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

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.role != role:
                messages.error(request, "Invalid role for this account.")
                return redirect('login')

            login(request, user)

            target = ROLE_DASHBOARDS.get(role)
            if target:
                return redirect(target)
            # A role with no dashboard should not leave the user on a blank
            # page; send them back with something to read.
            messages.error(request, "No dashboard is configured for this role.")
            return redirect('login')

        else:
            messages.error(request, "Invalid credentials")
            return redirect('login')

    return render(request, 'accounts/login.html')
