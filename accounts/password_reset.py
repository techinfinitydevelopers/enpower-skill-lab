"""
Forgot-password flow.

Open to School Admins, Thinking Coaches and Program Coordinators only.
Students and Parents are deliberately excluded: their login IDs are generated
by the system and handed over by the school, they cannot change their own
password, and they are never emailed -- so a reset link has nowhere to go.
Super Admins are excluded too; that account is recovered by a developer.

Two views:

  forgot_password   ask for the email address, send the link
  reset_password    accept the link, set a new password

The request form always reports the same thing whether or not the address
belongs to an account. Saying "no such user" would let anyone test which email
addresses are registered, and the set of school staff is easy to guess.

Tokens come from Django's default_token_generator, which folds the current
password hash and last_login into the token: using a link once, or logging in,
invalidates it. PASSWORD_RESET_TIMEOUT bounds how long it lives.
"""

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.shortcuts import redirect, render
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from competencies.emails import send_password_reset

from .models import User

logger = logging.getLogger('enpower.email')

# Kept here rather than in settings: this is not a deployment knob, it is what
# the flow is for. Changing it means changing who may reset a password.
RESET_ALLOWED_ROLES = ('SCHOOL_ADMIN', 'THINKING_COACH', 'PROGRAM_COORDINATOR')

# Shown whether or not the address matched, so the form cannot be used to
# discover which addresses are registered.
SENT_MESSAGE = ('If that email address belongs to a School Admin, Thinking '
                'Coach or Program Coordinator account, a reset link is on its '
                'way. Please check your inbox, and your spam folder.')


def _school_name(user):
    """School for the email body, if this user's profile carries one.

    A Program Coordinator is mapped to many schools, so no single name applies
    and the line is simply left out of the email.
    """
    for attr in ('school_admin_profile', 'teacher_profile'):
        try:
            profile = getattr(user, attr, None)
        except ObjectDoesNotExist:
            continue
        school = getattr(profile, 'school', None) if profile else None
        if school is not None:
            return getattr(school, 'school_name', None)
    return None


def _reset_link(request, user):
    base = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    if not base:
        # Falls back to the host actually being served, so a link is never
        # emailed pointing at nothing.
        base = f'{request.scheme}://{request.get_host()}'
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f'{base}/reset-password/{uid}/{token}/'


def forgot_password(request):
    """Ask for an email address and send the reset link."""
    if request.method != 'POST':
        return render(request, 'accounts/forgot-password.html',
                      {'allowed_roles': RESET_ALLOWED_ROLES})

    email = (request.POST.get('email') or '').strip()
    if not email:
        messages.error(request, 'Please enter your email address.')
        return redirect('forgot_password')

    # An address could in principle sit on more than one account; mail each one
    # that is actually eligible rather than picking one arbitrarily.
    recipients = User.objects.filter(
        email__iexact=email, role__in=RESET_ALLOWED_ROLES, is_active=True)

    for user in recipients:
        send_password_reset(
            to=user.email,
            name=user.get_full_name() or user.username,
            reset_link=_reset_link(request, user),
            role=user.role,
            school_name=_school_name(user),
        )

    if not recipients:
        # Worth knowing about in the log even though the page will not say so.
        logger.info('Password reset requested for %s - no eligible account', email)

    messages.success(request, SENT_MESSAGE)
    return redirect('forgot_password')


def _user_from_token(uidb64, token):
    """The user this link belongs to, or None if the link is no longer good."""
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return None
    # Re-checked at use, not only when the link was made: a role can change in
    # between, and an expired or already-used token must not still work.
    if user.role not in RESET_ALLOWED_ROLES or not user.is_active:
        return None
    if not default_token_generator.check_token(user, token):
        return None
    return user


def reset_password(request, uidb64, token):
    """Accept a reset link and set the new password."""
    user = _user_from_token(uidb64, token)
    if user is None:
        return render(request, 'accounts/reset-password.html', {'invalid': True})

    if request.method != 'POST':
        return render(request, 'accounts/reset-password.html', {'invalid': False})

    new = request.POST.get('new_password') or ''
    confirm = request.POST.get('confirm_password') or ''

    if new != confirm:
        messages.error(request, 'The two passwords do not match.')
        return render(request, 'accounts/reset-password.html', {'invalid': False})

    try:
        validate_password(new, user)
    except ValidationError as e:
        for problem in e.messages:
            messages.error(request, problem)
        return render(request, 'accounts/reset-password.html', {'invalid': False})

    user.set_password(new)
    user.save(update_fields=['password'])
    # Changing the password rewrites the hash the token was built from, so the
    # link is now dead -- which is what we want after a single use.
    update_session_auth_hash(request, user)

    messages.success(request, 'Your password has been reset. Please sign in with it.')
    return redirect('login')
