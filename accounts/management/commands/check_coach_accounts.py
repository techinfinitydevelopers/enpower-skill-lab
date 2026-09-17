"""Report Thinking Coaches whose login and profile disagree.

Two screens read two different tables. The Thinking Coaches list reads
Teacher; the timetable's coach dropdown read User.role. A row present in one
table and not the other therefore shows up on one screen and not the other,
which is how a coach came to be assignable on a timetable while the list that
manages coaches had never heard of them.

The dropdown now reads both, so the disagreement no longer leaks into the UI.
This command exists to find the rows that are already inconsistent, because
nothing on screen will show them any more.

    python manage.py check_coach_accounts
    python manage.py check_coach_accounts --fix-orphan-logins
    python manage.py check_coach_accounts --delete-orphan-logins

Which of the two to use turns on one fact that is easy to miss: onboarding
refuses an email that any account already holds, and it does not check whether
that account is active. Deactivating an orphan therefore leaves the person
un-onboardable under their own address; only deleting it frees them.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Report (and optionally deactivate) coach logins with no Teacher profile.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix-orphan-logins', action='store_true',
            help='Deactivate coach logins that have no Teacher profile. '
                 'Deactivates, never deletes -- the account may be a person '
                 'whose profile was removed by mistake. Note this does NOT '
                 'free the email address for re-onboarding.')
        parser.add_argument(
            '--delete-orphan-logins', action='store_true',
            help='Delete them outright, freeing the email address so the '
                 'person can be onboarded properly. Every reference to them '
                 'is SET_NULL, so anything they were assigned to becomes '
                 'unassigned rather than being deleted -- the counts printed '
                 'above say how much.')

    def handle(self, *args, **options):
        from teacher.models import Teacher

        User = get_user_model()

        profiled = set(
            Teacher.objects.filter(user__isnull=False)
            .values_list('user_id', flat=True))
        coaches = list(User.objects.filter(role='THINKING_COACH'))

        # A login that says Thinking Coach with no profile behind it. This is
        # what the deleted-profile path used to leave: the FK is SET_NULL, so
        # removing a Teacher left the User untouched.
        orphan_logins = [u for u in coaches if u.id not in profiled]

        # And the reverse: a profile whose login cannot act as a coach, so the
        # person is listed but can never be assigned or sign in as one.
        unusable = []
        for t in Teacher.objects.select_related('user'):
            if t.user is None:
                unusable.append((t, 'no login account'))
            elif t.user.role != 'THINKING_COACH':
                unusable.append((t, f'login role is {t.user.role or "(blank)"}'))

        self.stdout.write('')
        self.stdout.write(f'  coach logins        : {len(coaches)}')
        self.stdout.write(f'  Teacher profiles    : {Teacher.objects.count()}')
        self.stdout.write('')

        if orphan_logins:
            self.stdout.write(self.style.WARNING(
                f'  {len(orphan_logins)} login(s) with NO Teacher profile '
                f'-- these used to appear in the timetable dropdown only:'))
            for u in orphan_logins:
                name = u.get_full_name() or '(no name)'
                self.stdout.write(
                    f'     id={u.id:<6} {u.username:<38} {name:<26} '
                    f'active={u.is_active}')
                # Every reference is SET_NULL, so deleting the login unassigns
                # these rather than removing them. Worth knowing the number
                # before choosing between deactivate and delete.
                for label, count in self._references(u):
                    if count:
                        self.stdout.write(f'               assigned to {count} {label}')
            self.stdout.write('')
            self.stdout.write(
                '  Deactivating keeps the email taken, so onboarding the same '
                'person again will still be refused.')
            self.stdout.write(
                '  Deleting frees it. Nothing cascades: every reference above '
                'is SET_NULL and simply becomes unassigned.')
        else:
            self.stdout.write(self.style.SUCCESS(
                '  every coach login has a Teacher profile'))

        self.stdout.write('')
        if unusable:
            self.stdout.write(self.style.WARNING(
                f'  {len(unusable)} Teacher profile(s) that cannot act as a coach '
                f'-- listed on screen, but not assignable:'))
            for t, why in unusable:
                self.stdout.write(f'     {t.full_name:<30} {why}')
        else:
            self.stdout.write(self.style.SUCCESS(
                '  every Teacher profile has a usable coach login'))

        if options['fix_orphan_logins'] and orphan_logins:
            self.stdout.write('')
            with transaction.atomic():
                count = User.objects.filter(
                    id__in=[u.id for u in orphan_logins]).update(is_active=False)
            self.stdout.write(self.style.SUCCESS(
                f'  deactivated {count} orphan login(s). Nothing was deleted; '
                f'reactivate from the admin if a profile should be restored.'))
        elif options['delete_orphan_logins'] and orphan_logins:
            self.stdout.write('')
            with transaction.atomic():
                count, _ = User.objects.filter(
                    id__in=[u.id for u in orphan_logins]).delete()
            self.stdout.write(self.style.SUCCESS(
                f'  deleted {len(orphan_logins)} orphan login(s). Their email '
                f'addresses are free; onboard the people who should be coaches '
                f'through Onboard Thinking Coaches.'))
        elif orphan_logins:
            self.stdout.write('')
            self.stdout.write(
                '  --fix-orphan-logins   deactivate (email stays taken)')
            self.stdout.write(
                '  --delete-orphan-logins  delete (email freed, assignments '
                'become unassigned)')
        self.stdout.write('')

    def _references(self, user):
        """What this login is attached to. All SET_NULL, so all unassignable."""
        from attendance.models import (AttendanceSession, DailySessionFeedback,
                                       Timetable, WeeklySessionFeedback)
        from schools.models import Class

        return [
            ('class(es)', Class.objects.filter(thinking_coach=user).count()),
            ('timetable(s)', Timetable.objects.filter(thinking_coach=user).count()),
            ('attendance session(s)',
             AttendanceSession.objects.filter(thinking_coach=user).count()),
            ('daily feedback row(s)',
             DailySessionFeedback.objects.filter(thinking_coach=user).count()),
            ('weekly feedback row(s)',
             WeeklySessionFeedback.objects.filter(thinking_coach=user).count()),
        ]
