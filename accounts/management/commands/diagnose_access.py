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
        parser.add_argument(
            '--sweep', action='store_true',
            help='Find every account and every classroom with the same fault, '
                 'and say whether lowercasing the logins would collide.')
        parser.add_argument(
            '--recent', nargs='?', const=6, type=int, metavar='HOURS',
            help='Every username anyone has failed to sign in with lately. '
                 'Use when a person says they cannot get in but nothing is '
                 'recorded against the address you were given.')
        parser.add_argument(
            '--uploads', nargs='?', const=10, type=int, metavar='COUNT',
            help='The latest student project uploads, and whether each one '
                 'actually reached a student who can sign in and see it.')

    def handle(self, *args, **opts):
        for spec in opts['account']:
            email, _, password = spec.partition('=')
            self.account(email.strip(), password)
        for spec in opts['classroom']:
            self.classroom(spec)
        if opts['sweep']:
            self.sweep()
        if opts['recent']:
            self.recent(opts['recent'])
        if opts['uploads']:
            self.uploads(opts['uploads'])
        if not any((opts['account'], opts['classroom'], opts['sweep'],
                    opts['recent'], opts['uploads'])):
            print('  Nothing asked for. See --help.')

    # --------------------------------------------------------------- uploads

    def uploads(self, count):
        """Did the coach's upload actually reach a student's dashboard?

        The student dashboard shows `student.project_uploads`, so an upload
        with nobody tagged reaches nobody. The form drops any student who does
        not belong to the coach's own school, and it does so silently -- the
        coach still sees "uploaded successfully" and the row still appears
        under Recent Uploads. That is the one way this can look fine from the
        coach's side and be empty from the student's.
        """
        from attendance.models import StudentProjectUpload
        from student.models import Student

        rule(f'UPLOADS  the latest {count} student project upload(s)')

        rows = (StudentProjectUpload.objects
                .select_related('school', 'created_by')
                .prefetch_related('students')
                .order_by('-created_at')[:count])
        if not rows:
            print('  None recorded at all.')
            return

        for up in rows:
            tagged = list(up.students.all())
            print(f'\n  #{up.id}  {up.title!r}')
            print(f'    uploaded {up.created_at:%d %b %Y %H:%M} by '
                  f'{up.created_by.username if up.created_by else "(unknown)"}')
            print(f'    school {up.school.school_name!r}  '
                  f'grade {up.grade!r} division {up.division!r}')
            print(f'    file: {up.file.name or "(none)" if up.file else "(none)"}'
                  f'   video: {up.video_link or "(none)"}')
            print(f'    students tagged: {len(tagged)}')

            if not tagged:
                # Nobody tagged still shows for the whole class, so say whether
                # that fallback finds anyone before calling it lost.
                fallback = Student.objects.filter(
                    school=up.school, student_class=str(up.grade),
                    division=up.division, is_active=True).count()
                print(f'      NOBODY TAGGED. The dashboard falls back to the '
                      f'whole class, which matches {fallback} student(s).')
                if not fallback:
                    print('      So this upload reaches no one. The coach was '
                          'still told it succeeded.')
                continue

            for s in tagged[:6]:
                reachable = bool(s.user_id) and s.is_active
                same_school = s.school_id == up.school_id
                print(f'      {s.full_name}  {s.skill_lab_reg_id!r}  '
                      f'class {s.student_class!r}{s.division!r}  '
                      f'has login: {bool(s.user_id)}  active: {s.is_active}'
                      f'{"" if same_school else "   DIFFERENT SCHOOL"}')
                if not reachable:
                    print('        -> cannot sign in, so cannot see it')
            if len(tagged) > 6:
                print(f'      ... and {len(tagged) - 6} more')

    # ---------------------------------------------------------------- recent

    def recent(self, hours):
        """What is actually being typed into the form.

        An address with no failures against it, belonging to someone who says
        they cannot get in, means one of two things: they are typing a
        different address, or they are picking the wrong role -- which the
        view rejects before it records anything, so it leaves no trace at all.
        This separates the two by showing every spelling that has been tried.
        """
        from accounts.models import LoginAttempt

        rule(f'RECENT  everything typed in the last {hours} hour(s)')

        since = timezone.now() - timedelta(hours=hours)
        rows = (LoginAttempt.objects.filter(created_at__gte=since)
                .order_by('-created_at'))
        if not rows.exists():
            print('  Nothing at all. Either everyone got in first time, or '
                  'whoever is stuck is being turned away by the role check, '
                  'which records nothing.')
            return

        grouped = (rows.values('username')
                   .annotate(n=Count('id'))
                   .order_by('-n'))
        print(f'  {rows.count()} failed attempt(s) across '
              f'{grouped.count()} spelling(s)\n')
        for g in grouped:
            same = rows.filter(username=g['username'])
            ips = sorted(set(same.values_list('ip_address', flat=True)))
            first = same.order_by('created_at').first()
            last = same.order_by('-created_at').first()
            known = U.objects.filter(username=g['username']).exists()
            print(f'    {g["username"]!r}  x{g["n"]}')
            print(f'      {first.created_at:%d %b %H:%M} -> '
                  f'{last.created_at:%d %b %H:%M}   from {", ".join(ips)}')
            print(f'      an account with this exact username exists: {known}')
            if not known:
                near = U.objects.filter(
                    username__icontains=g['username'].split('@')[0][:6])[:3]
                for u in near:
                    print(f'        did they mean {u.username!r}? '
                          f'role={u.role}')

    # ----------------------------------------------------------------- sweep

    def sweep(self):
        """How wide are the two faults, and what would a normalisation break?

        Sujeet's login and BKG's Grade 6 C are the same fault seen twice: a
        value arrived in a different case from the one the lookup asks for,
        and every lookup here is exact. This finds the rest of them before
        anything is changed.
        """
        from collections import defaultdict

        from attendance.models import Timetable
        from student.models import Student
        from teacher.models import Teacher

        rule('SWEEP 1/4  logins that are not already lowercase')
        # Students and parents log in with a generated registration ID, which
        # is uppercase on purpose -- BI-RM-8A-235-25-stu. Lowercasing those
        # would break the logins it was meant to fix, so the two kinds are
        # counted apart and only the email-shaped ones are candidates.
        odd = [u for u in U.objects.all() if u.username != u.username.lower()]
        emails = [u for u in odd if '@' in u.username]
        reg_ids = [u for u in odd if '@' not in u.username]
        print(f'  {len(odd)} of {U.objects.count()} logins carry an uppercase '
              f'letter')
        print(f'    email-shaped (these are the ones to normalise): {len(emails)}')
        print(f'    registration IDs (leave alone, uppercase on purpose): '
              f'{len(reg_ids)}')
        if reg_ids:
            by_role = defaultdict(int)
            for u in reg_ids:
                by_role[u.role] += 1
            print(f'      {dict(by_role)}')
        for u in emails[:40]:
            print(f'    {u.username!r:<44} role={u.role:<20} active={u.is_active}')
        if len(emails) > 40:
            print(f'    ... and {len(emails) - 40} more')

        rule('SWEEP 2/4  would lowercasing the email logins collide?')
        # A collision is two rows that become the same username. That is the
        # one thing that stops a normalisation, so it is worth its own pass.
        # Registration IDs are excluded because they are not being changed.
        buckets = defaultdict(list)
        for u in U.objects.filter(username__contains='@'):
            buckets[u.username.lower()].append(u)
        clashes = {k: v for k, v in buckets.items() if len(v) > 1}
        if clashes:
            print(f'  {len(clashes)} collision(s) — these must be settled first:')
            for name, rows in clashes.items():
                print(f'    {name!r}')
                for u in rows:
                    seen = (f'{u.last_login:%Y-%m-%d}' if u.last_login
                            else 'never signed in')
                    print(f'      id={u.pk:<6} {u.username!r:<44} '
                          f'role={u.role:<20} active={u.is_active}  {seen}')
        else:
            print('  none. Lowercasing every login would collide with nothing.')

        rule('SWEEP 3/4  coach profiles whose address differs from the login')
        mismatched = []
        for t in Teacher.objects.select_related('user').exclude(user=None):
            a = (t.official_email or '').strip()
            b = t.user.username
            if a and a != b:
                mismatched.append((t, a, b))
        print(f'  {len(mismatched)} coach profile(s) disagree with their login')
        for t, a, b in mismatched[:25]:
            same = ' (same but for case)' if a.lower() == b.lower() else ''
            print(f'    {t.full_name}: profile={a!r} login={b!r}{same}')

        rule('SWEEP 4/4  every classroom whose roster comes out empty')
        empty = []
        for tt in (Timetable.objects.select_related('school', 'thinking_coach')
                   .order_by('school__school_name', 'grade', 'division')):
            n = Student.objects.filter(
                school=tt.school, student_class=str(tt.grade),
                division=tt.division, is_active=True).count()
            if n:
                continue
            loose = Student.objects.filter(
                school=tt.school, student_class=str(tt.grade),
                division__iexact=tt.division, is_active=True).count()
            empty.append((tt, loose))

        print(f'  {len(empty)} of {Timetable.objects.count()} classrooms build '
              f'an empty roster')
        for tt, loose in empty:
            coach = tt.thinking_coach.username if tt.thinking_coach else '(no coach)'
            cause = (f'{loose} student(s) match if case is ignored — '
                     f'the division is stored in the other case'
                     if loose else 'no student matches even ignoring case')
            print(f'\n    {tt.school.school_name} — {tt.program or "?"} '
                  f'{tt.grade}-{tt.division}  (timetable {tt.id})')
            print(f'      coach: {coach}')
            print(f'      {cause}')
            if loose:
                held = (Student.objects
                        .filter(school=tt.school, student_class=str(tt.grade),
                                division__iexact=tt.division, is_active=True)
                        .values_list('division', flat=True).distinct())
                print(f'      students hold division={sorted(set(held))}, '
                      f'the timetable asks for {tt.division!r}')

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
            seen = (f'{user.last_login:%Y-%m-%d %H:%M}' if user.last_login
                    else 'never')
            print(f'  last_login  : {seen}')

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
