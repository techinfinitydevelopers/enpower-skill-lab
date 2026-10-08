"""Give one account a new password, or a link to choose one, and email it.

The forgot-password form only mails School Admins, Thinking Coaches and
Program Coordinators -- a Super Admin asking for a reset gets the same "a link
is on its way" as everyone else and no email, because the page must not reveal
which addresses are registered. That is correct for a public form and useless
when the person asking is standing next to you.

Two ways round it, and the safer one is the default-adjacent flag:

    --link      send a reset link. Nothing changes until they use it, it stops
                working after 24 hours, and no password is ever written down.
    (default)   generate a password, set it, and email it. Quicker, but the
                password then lives in a mailbox for as long as that mailbox
                does.

Nothing is changed or sent without --apply, so the command can be run first to
see who it would touch.

    python manage.py reset_password_for someone@example.com
    python manage.py reset_password_for someone@example.com --link --apply
    python manage.py reset_password_for someone@example.com --apply
"""

import secrets
import string

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.management.base import BaseCommand, CommandError
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

U = get_user_model()

# No look-alike characters: this gets read off a screen and typed back in.
ALPHABET = ''.join(c for c in string.ascii_letters + string.digits
                   if c not in 'Il1O0')


def make_password_text(length=14):
    return ''.join(secrets.choice(ALPHABET) for _ in range(length)) + '!'


class Command(BaseCommand):
    help = 'Email one account a new password, or a link to set one. Needs --apply.'

    def add_arguments(self, parser):
        parser.add_argument('email', help='The account to act on.')
        parser.add_argument(
            '--link', action='store_true',
            help='Send a reset link instead of setting a password. Nothing '
                 'changes until they use it.')
        parser.add_argument(
            '--apply', action='store_true',
            help='Actually change it and send. Without this, nothing happens.')

    def handle(self, *args, **opts):
        from django.conf import settings

        email = opts['email'].strip()
        user = (U.objects.filter(username__iexact=email).first()
                or U.objects.filter(email__iexact=email).first())
        if user is None:
            raise CommandError(f'No account for {email!r}.')
        if not user.is_active:
            raise CommandError(
                f'{user.username} is deactivated. Reactivate it first, or a '
                f'new password will not let them in either.')

        name = user.get_full_name() or user.username
        to = (user.email or '').strip() or user.username
        if '@' not in to:
            raise CommandError(
                f'{user.username} has no email address to send to.')

        print(f'  account : {user.username}  ({user.role})')
        print(f'  send to : {to}')
        print(f'  method  : {"reset link" if opts["link"] else "new password"}')

        if not opts['apply']:
            print('\n  Nothing done. Re-run with --apply.')
            return

        if opts['link']:
            self.send_link(user, name, to)
        else:
            self.send_new_password(user, name, to)

    # ------------------------------------------------------------------ link

    def send_link(self, user, name, to):
        from django.conf import settings

        from competencies.emails import send_password_reset

        base = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
        if not base:
            raise CommandError(
                'SITE_URL is not set, so the link would point at nothing. '
                'Set it, or use the password form of this command.')
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        link = f'{base}/reset-password/{uid}/{token}/'

        sent = send_password_reset(to=to, name=name, reset_link=link,
                                   role=user.role)
        print(f'\n  link  : {link}')
        self.report(sent, to)
        print('  Nothing has changed yet — the password only moves when they '
              'use that link, and it stops working after 24 hours.')

    # -------------------------------------------------------------- password

    def send_new_password(self, user, name, to):
        from competencies.emails import send_notice

        password = make_password_text()
        user.set_password(password)
        user.save(update_fields=['password'])

        sent = send_notice(
            to=to, name=name, role=user.role,
            subject='Your ENpower Skill Lab password has been reset',
            heading='Your password has been reset',
            paragraphs=[
                'Your ENpower Skill Lab password has been reset at your '
                'request. Please sign in with the details below and change it '
                'from My Account.',
            ],
            facts=[('Login ID', user.username), ('New Password', password)],
            closing='If you did not ask for this, tell us straight away.')

        # Printed as well as emailed: if the mail bounces, the password has
        # still been changed, and nobody can get in without this line.
        print(f'\n  new password: {password}')
        print('  (the password is already changed, emailed or not)')
        self.report(sent, to)

    # ---------------------------------------------------------------- shared

    def report(self, sent, to):
        if sent:
            print(f'  email : sent to {to}')
        else:
            print(f'  email : NOT SENT to {to} — look for "Email FAILED" in '
                  f'the log for the reason.')
