"""Read-only answers to "why can't this person get in, or see their class".

Nothing here writes. No save(), no update(), no delete() -- it is safe to run
against production while people are using it.

Three questions it settles, in the order they came from the client:

  1. Does this login exist, is it active, and is the password we were given
     the password the account actually holds? Those three failures all show
     the user the same "Invalid credentials", so they cannot be told apart
     from the outside.
  2. Has the person even reached us? Failed attempts are recorded with an IP,
     so a person who is typing into the wrong place leaves no rows at all.
  3. Why is a classroom's student list empty? The list matches on exact
     strings -- school, student_class, division -- so this prints what the
     timetable asks for next to what the students actually hold.

    python manage.py diagnose_access --account someone@example.com
    python manage.py diagnose_access --account "someone@example.com=TheirPassword"
    python manage.py diagnose_access --classroom "CSL plus:6:C"

Both flags repeat. Passing a password makes it visible in the shell history
of whatever machine runs this, so drop it once the answer is known.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

U = get_user_model()


def rule(title):
    print(f'\n{"=" * 68}\n{title}\n{"=" * 68}')


class Command(BaseCommand):
    help = 'Read-only: diagnose a login failure or an empty classroom roster.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account', action='append', default=[], metavar='EMAIL[=PASSWORD]',
            help='Login to look up. Add =PASSWORD to test it. Repeatable.')
        parser.add_argument(
            '--classroom', action='append', default=[], metavar='PROGRAM:GRADE:DIVISION',
            help='Classroom whose roster is empty, e.g. "CSL plus:6:C". Repeatable.')

    def handle(self, *args, **opts):
        for spec in opts['account']:
            email, _, password = spec.partition('=')
            self.account(email.strip(), password)
        for spec in opts['classroom']:
            self.classroom(spec)
        if not opts['account'] and not opts['classroom']:
            print('  Nothing asked for. See --help.')

    # ---------------------------------------------------------------- logins

    def account(self, email, password):
        from accounts.models import LoginAttempt

        rule(f'ACCOUNT  {email}')

        user = U.objects.filter(username=email).first()
        if user is None:
            print('  No account with that username.')
            # The username is the email, so a near miss is usually a typo in
            # one or the other -- worth naming rather than leaving as "no".
            stem = email.split('@')[0][:6]
            near = U.objects.filter(username__icontains=stem)[:6]
            by_mail = U.objects.filter(email__iexact=email).exclude(username=email)[:6]
            for label, rows in (('similar username', near), ('same email field', by_mail)):
                for u in rows:
                    print(f'    {label}: {u.username!r}  role={u.role}  '
                          f'active={u.is_active}')
            if not near and not by_mail:
                print('    and nothing close to it either.')
        else:
            print(f'  exists      : yes  (id={user.pk})')
            print(f'  is_active   : {user.is_active}'
                  f'{"   <-- deactivated accounts get Invalid credentials" if not user.is_active else ""}')
            print(f'  role        : {user.role}')
            print(f'  email field : {user.email!r}')
            print(f'  date_joined : {user.date_joined:%Y-%m-%d %H:%M}')
            print(f'  last_login  : '
                  f'{user.last_login:%Y-%m-%d %H:%M} ' if user.last_login
                  else '  last_login  : never')

            if password:
                ok = user.check_password(password)
                print(f'  password we were given: '
                      f'{"MATCHES the account" if ok else "does NOT match"}')
                if ok and not user.is_active:
                    print('    -> right password, account switched off. '
                          'That is our end.')
                elif not ok:
                    print('    -> the account holds a different password. '
                          'It was changed, or the one we were given is wrong.')
            else:
                print('  password    : not tested (pass --account "email=pw")')

            teacher = getattr(user, 'teacher_profile', None)
            if teacher is None:
                from teacher.models import Teacher
                teacher = Teacher.objects.filter(user=user).first()
            if teacher is None:
                print('  Teacher row : MISSING — this is an orphan coach login. '
                      'check_coach_accounts --fix-orphan-logins deactivates these.')
            else:
                print(f'  Teacher row : {teacher.full_name}  '
                      f'active={teacher.is_active}  '
                      f'official_email={teacher.official_email!r}')
                if (teacher.official_email or '').strip().lower() != email.lower():
                    print('    -> the profile holds a different address than the login.')

        window = timezone.now() - timedelta(days=3)
        rows = (LoginAttempt.objects
                .filter(username=email, created_at__gte=window)
                .order_by('-created_at'))
        print(f'  failed attempts in the last 3 days: {rows.count()}')
        for r in rows[:8]:
            print(f'    {r.created_at:%d %b %H:%M}  from {r.ip_address}')
        if not rows.exists():
            print('    none — nobody has submitted this username lately, so '
                  'they may be typing a different address.')

    # ------------------------------------------------------------ classrooms

    def classroom(self, spec):
        from attendance.models import Timetable
        from student.models import Student

        parts = [p.strip() for p in spec.split(':')]
        program, grade, division = (parts + ['', '', ''])[:3]
        rule(f'CLASSROOM  program={program!r} grade={grade!r} division={division!r}')

        tts = Timetable.objects.select_related('school', 'thinking_coach').filter(
            grade=grade, division=division)
        if program:
            tts = tts.filter(program__icontains=program)
        if not tts.exists():
            print('  No timetable matches. Check the program spelling — the '
                  'label on screen is built from it.')
            return

        for tt in tts:
            coach = tt.thinking_coach
            print(f'\n  Timetable {tt.id}: {tt.program!r} {tt.grade}-{tt.division}  '
                  f'active={tt.is_active}')
            print(f'    school : id={tt.school_id}  {tt.school.school_name!r}')
            print(f'    coach  : '
                  f'{coach.username if coach else "(none assigned)"}')

            # This is exactly what api_attendance_students asks for.
            exact = Student.objects.filter(
                school=tt.school, student_class=str(tt.grade),
                division=tt.division, is_active=True)
            print(f'    roster the attendance page builds: {exact.count()} student(s)')

            in_school = Student.objects.filter(school=tt.school)
            print(f'    students at this school: {in_school.count()} '
                  f'({in_school.filter(is_active=True).count()} active)')
            shapes = (in_school
                      .values('student_class', 'division', 'is_active')
                      .annotate(n=Count('id'))
                      .order_by('student_class', 'division'))
            if shapes:
                print('    what those students actually hold:')
                for s in shapes[:25]:
                    flag = '' if s['is_active'] else '  (inactive)'
                    print(f'      student_class={s["student_class"]!r:<8} '
                          f'division={s["division"]!r:<6} {s["n"]:>4}{flag}')
            else:
                print('    this school has no students at all.')

            # The same grade and division under some other school row is the
            # signature of a duplicated school.
            elsewhere = (Student.objects
                         .filter(student_class=str(tt.grade), division=tt.division,
                                 is_active=True)
                         .exclude(school=tt.school)
                         .values('school_id', 'school__school_name')
                         .annotate(n=Count('id')))
            for e in elsewhere:
                print(f'    NOTE {e["n"]} matching student(s) sit under a '
                      f'different school: id={e["school_id"]} '
                      f'{e["school__school_name"]!r}')
