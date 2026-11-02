"""Send a set of accounts their login details again, and say whether it worked.

The principals at several schools reported never receiving the credentials
they were onboarded with. Nothing in the product could answer that, for two
reasons, and both are worth knowing before reading the output below.

First, no send is recorded anywhere. ``competencies.emails._send`` catches
every exception, writes one line to the log and returns False; there is no
table, and the host keeps logs for days, not months. An email sent a month ago
cannot be confirmed or denied from inside this system -- only the mail
provider's own delivery log can do that.

Second, the two places that onboard a School Admin and a Program Coordinator
ignored that return value and reported "Credentials sent to ..." either way,
so whoever onboarded them was told it had worked even when it had not. That is
fixed now, but it was true when these accounts were made.

So this command does the one thing that can be known for certain: it sends
now, and reports the result of this send, per person.

    python manage.py resend_credentials --role SCHOOL_ADMIN
    python manage.py resend_credentials --role SCHOOL_ADMIN --check
    python manage.py resend_credentials --role SCHOOL_ADMIN --link --apply
    python manage.py resend_credentials a@x.com b@y.com --apply

Two ways to send, and which is right depends on the person:

    --link      a reset link. Their current password keeps working until they
                use it, and it expires after 24 hours. Safe for someone who is
                already signed in and working -- they lose nothing if the mail
                goes astray again.
    (default)   a new password, set immediately and emailed. The only option
                for someone who never got in, and the wrong one for someone
                who did: it takes away the password they are using today.

Nothing is changed or sent without --apply. Run it bare first: the audit it
prints -- last login, status, whether a password was ever changed -- is the
evidence for who needs which.
"""

import smtplib

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.management.base import BaseCommand, CommandError
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .reset_password_for import make_password_text

U = get_user_model()


class Command(BaseCommand):
    help = ('Resend login credentials to a role or to named addresses, and '
            'report what actually left the server. Needs --apply.')

    def add_arguments(self, parser):
        parser.add_argument(
            'emails', nargs='*',
            help='Specific addresses. Omit to use --role.')
        parser.add_argument(
            '--role', default=None,
            help='Every active account in this role, e.g. SCHOOL_ADMIN.')
        parser.add_argument(
            '--link', action='store_true',
            help='Send a reset link instead of a new password. Their current '
                 'password keeps working until they use it.')
        parser.add_argument(
            '--only-never-logged-in', action='store_true',
            help='Skip anyone who has signed in at least once.')
        parser.add_argument(
            '--check', action='store_true',
            help='Open a connection to the mail server and report whether it '
                 'accepts us, without sending anything to anybody.')
        parser.add_argument(
            '--apply', action='store_true',
            help='Actually change and send. Without this, nothing happens.')

    # ------------------------------------------------------------------ main

    def handle(self, *args, **opts):
        if opts['check']:
            self.check_mail_server()
            return

        users = self.collect(opts)
        if not users:
            raise CommandError('No accounts matched.')

        self.audit(users)

        if opts['only_never_logged_in']:
            users = [u for u in users if u.last_login is None]
            print(f'\n  --only-never-logged-in leaves {len(users)}.')
            if not users:
                return

        print(f'\n  method  : {"reset link" if opts["link"] else "new password"}')
        print(f'  to send : {len(users)}')

        if not opts['apply']:
            print('\n  Nothing done. Re-run with --apply.')
            return

        self.check_mail_server()

        print()
        sent = failed = 0
        for user in users:
            to = (user.email or '').strip() or user.username
            if '@' not in to:
                print(f'  SKIP    {user.username} -- no email address')
                failed += 1
                continue
            name = user.get_full_name() or user.username
            ok = (self.send_link(user, name, to) if opts['link']
                  else self.send_password(user, name, to))
            print(f'  {"SENT  " if ok else "FAILED"}  {to}'
                  f'{"" if ok else "  (see the log for the reason)"}')
            sent, failed = (sent + 1, failed) if ok else (sent, failed + 1)

        print(f'\n  sent {sent}, failed {failed}')
        if not opts['link']:
            print('  Every password above is already changed, emailed or not.')
        print('  Delivery is the mail provider\'s to confirm. SENT means the '
              'server accepted the message, not that it reached an inbox. '
              'Check the ZeptoMail delivery log for bounced or blocked.')

    # ------------------------------------------------------------- gathering

    def collect(self, opts):
        if opts['emails']:
            found = []
            for email in opts['emails']:
                email = email.strip()
                user = (U.objects.filter(username__iexact=email).first()
                        or U.objects.filter(email__iexact=email).first())
                if user is None:
                    print(f'  (no account for {email})')
                else:
                    found.append(user)
            return found
        if not opts['role']:
            raise CommandError('Give some addresses, or --role.')
        return list(U.objects.filter(role=opts['role'].strip().upper(),
                                     is_active=True).order_by('id'))

    # ----------------------------------------------------------------- audit

    def audit(self, users):
        """What is already known about each account, before anything is sent.

        ``last_login`` is the only honest answer to "did they ever get in".
        The Status column on the export is not: it turns Active when the
        password is changed, not when the person signs in, so someone who
        logged in and left the password alone still reads Pending.
        """
        print(f'\n  {len(users)} account(s)\n')
        head = f'  {"login":38} {"status":9} {"last login":17} pwd changed'
        print(head)
        print('  ' + '-' * (len(head) - 2))
        for user in users:
            profile = self.profile_for(user)
            status = getattr(profile, 'account_status', '-') if profile else '-'
            changed = getattr(profile, 'password_changed', None) if profile else None
            seen = (user.last_login.strftime('%Y-%m-%d %H:%M')
                    if user.last_login else 'NEVER')
            print(f'  {user.username[:38]:38} {str(status):9} {seen:17} '
                  f'{"yes" if changed else "no"}')

    def profile_for(self, user):
        # A reverse one-to-one that has no row raises RelatedObjectDoesNotExist,
        # which subclasses AttributeError, so getattr's default catches it.
        for attr in ('school_admin_profile', 'teacher_profile',
                     'program_coordinator'):
            profile = getattr(user, attr, None)
            if profile is not None:
                return profile
        return None

    # ----------------------------------------------------------- mail server

    def check_mail_server(self):
        """Prove the mail path works before trusting anything sent down it.

        Setting a new password for someone whose mail never arrives locks them
        out of an account that was working, and Forgot Password cannot rescue
        them because it travels the same path. So the connection is tested
        first, and a failure stops the run before a single password changes.
        """
        from django.conf import settings

        host, port = settings.EMAIL_HOST, settings.EMAIL_PORT
        print(f'\n  mail server : {host}:{port}')
        print(f'  from        : {settings.DEFAULT_FROM_EMAIL}')
        print('  credentials : '
              f'{"present" if settings.EMAIL_HOST_PASSWORD else "MISSING"}')
        backend = settings.EMAIL_BACKEND
        if 'locmem' in backend or 'console' in backend:
            print(f'  backend     : {backend} -- nothing leaves this machine')
            return
        if not settings.EMAIL_HOST_PASSWORD:
            raise CommandError(
                'EMAIL_HOST_PASSWORD is empty, so every send fails. That '
                'alone would explain credentials never arriving.')
        try:
            server = smtplib.SMTP(host, port, timeout=20)
            server.starttls()
            server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            server.quit()
        except Exception as e:
            raise CommandError(
                f'The mail server refused us: {type(e).__name__}: {e}. '
                f'Nothing has been sent. Fix this first -- while it is true, '
                f'Forgot Password does not work either.')
        print('  connection  : accepted')

    # --------------------------------------------------------------- senders

    def send_link(self, user, name, to):
        from django.conf import settings

        from competencies.emails import send_password_reset

        base = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
        if not base:
            raise CommandError('SITE_URL is not set; the link would go nowhere.')
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        link = f'{base}/reset-password/{uid}/{token}/'
        return bool(send_password_reset(to=to, name=name, reset_link=link,
                                        role=user.role))

    def send_password(self, user, name, to):
        from competencies.emails import send_onboarding

        password = make_password_text()
        user.set_password(password)
        user.save(update_fields=['password'])

        # SchoolAdmin.temporary_password is deliberately left alone. The two
        # onboarding paths disagree about it -- the form stores a hash, the
        # bulk importer stores the password as typed -- and writing a third
        # opinion from here would settle a question nobody has asked yet. The
        # password is printed below instead, which is where it is needed.
        profile = self.profile_for(user)

        school = getattr(getattr(profile, 'school', None), 'school_name', None)
        ok = bool(send_onboarding(
            to=to, name=name, login_id=user.username, password=password,
            role=user.role, school_name=school))
        print(f'          {user.username}  ->  {password}')
        return ok
