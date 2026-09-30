"""Put a value back in the case the lookup asks for. Dry run unless told.

BKG GLOBAL SCHOOL's Grade 6 C students were uploaded with the section stored
as a lowercase 'c', while the timetable for that class holds 'C'. The
attendance roster matches the section exactly, so it found nobody -- 41
students, and the coach could not mark attendance at all.

Sujeet's login is the same fault in a different column: the address was saved
as SUJITKUMAR5305@GMAIL.COM and sign-in compares exactly.

Two things this deliberately does NOT do:

  * It never touches skill_lab_reg_id. Students and parents sign in with that
    ID and it embeds the section, so a 6c student keeps a 6c login. Changing
    it would break the logins this is meant to protect. There is no save()
    override and no signal on Student, so updating division cannot regenerate
    it by accident either -- but it is worth saying out loud.

  * It leaves logins alone unless --logins is passed. Sujeet can sign in
    today by typing his address in capitals, so he is not blocked; lowercasing
    it now would take that away before the case-insensitive sign-in ships, and
    the client has already been told to use capitals.

    python manage.py fix_case_drift              # show, change nothing
    python manage.py fix_case_drift --apply
    python manage.py fix_case_drift --logins --apply
"""

from collections import defaultdict

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

U = get_user_model()


def rule(title):
    print(f'\n{"=" * 68}\n{title}\n{"=" * 68}')


class Command(BaseCommand):
    help = 'Repair case drift in student sections (and optionally logins). Dry run by default.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Actually write. Without this nothing is changed.')
        parser.add_argument(
            '--logins', action='store_true',
            help='Also lowercase email-shaped usernames. Off by default -- '
                 'see the note at the top of this file.')

    def handle(self, *args, **opts):
        apply_it = opts['apply']
        print('  MODE: ' + ('APPLYING CHANGES' if apply_it
                            else 'dry run — nothing will be written'))

        plan = self.plan_sections()
        if opts['logins']:
            plan += self.plan_logins()

        if not plan:
            print('\n  Nothing to change.')
            return

        rule('WHAT WOULD CHANGE' if not apply_it else 'APPLYING')
        for line in plan:
            print(f'    {line["summary"]}')

        if not apply_it:
            print('\n  Re-run with --apply to make these changes.')
            return

        with transaction.atomic():
            for item in plan:
                item['do']()
        print('\n  Done. Verifying...')
        self.verify(plan)

    # -------------------------------------------------------------- sections

    def plan_sections(self):
        """Students whose section differs only in case from their timetable's."""
        from attendance.models import AttendanceSession, Timetable
        from student.models import Student

        rule('SECTIONS  rosters that are empty only because of letter case')

        wanted = defaultdict(set)   # student id -> the divisions asked of it
        targets = []

        for tt in (Timetable.objects.select_related('school')
                   .order_by('school__school_name', 'grade', 'division')):
            exact = Student.objects.filter(
                school=tt.school, student_class=str(tt.grade),
                division=tt.division, is_active=True)
            if exact.exists():
                continue
            loose = Student.objects.filter(
                school=tt.school, student_class=str(tt.grade),
                division__iexact=tt.division, is_active=True)
            if not loose.exists():
                continue

            ids = list(loose.values_list('id', flat=True))
            for sid in ids:
                wanted[sid].add(tt.division)
            held = sorted(set(loose.values_list('division', flat=True)))
            targets.append({'tt': tt, 'ids': ids, 'held': held})
            print(f'\n  {tt.school.school_name} — {tt.program or "?"} '
                  f'{tt.grade}-{tt.division}  (timetable {tt.id})')
            print(f'    {len(ids)} student(s) hold division={held}, '
                  f'timetable asks for {tt.division!r}')
            for s in loose.order_by('first_name')[:3]:
                print(f'      e.g. {s.first_name} {s.last_name}  '
                      f'reg_id={s.skill_lab_reg_id!r}  (reg_id is NOT touched)')

            # Sessions are keyed on the timetable's own value, so they should
            # already be 'C'. One stored in the other case would be stranded
            # by this change, so say so rather than find out later.
            odd = (AttendanceSession.objects
                   .filter(school=tt.school, grade=str(tt.grade),
                           division__iexact=tt.division)
                   .exclude(division=tt.division))
            if odd.exists():
                print(f'    NOTE {odd.count()} attendance session(s) are '
                      f'stored as {sorted(set(odd.values_list("division", flat=True)))} '
                      f'and would no longer line up. Left alone — check these.')
            else:
                print('    attendance sessions for this class: all already in '
                      'the timetable\'s case, nothing stranded')

        # One student pulled two ways means two timetables disagree; refuse
        # rather than let the last one win.
        conflicts = {sid: d for sid, d in wanted.items() if len(d) > 1}
        if conflicts:
            print(f'\n  REFUSING: {len(conflicts)} student(s) are claimed by '
                  f'timetables that disagree on the section:')
            for sid, divs in list(conflicts.items())[:10]:
                print(f'    student {sid} -> {sorted(divs)}')
            return []

        # A student can also be claimed by a timetable that is working fine
        # today -- one whose division already matches theirs. Moving them would
        # empty that roster to fill this one, trading one broken class for
        # another, so refuse there too. Looking only at empty rosters above
        # misses this entirely.
        stolen = defaultdict(set)
        for t in targets:
            for s in Student.objects.filter(id__in=t['ids']).only(
                    'id', 'school_id', 'student_class', 'division'):
                others = Timetable.objects.filter(
                    school_id=s.school_id, grade=str(s.student_class),
                    division=s.division).exclude(division=t['tt'].division)
                for other in others:
                    stolen[s.id].add((other.id, other.program, other.division,
                                      t['tt'].id, t['tt'].division))
        if stolen:
            print(f'\n  REFUSING: {len(stolen)} student(s) are already matched '
                  f'by a timetable that works today:')
            for sid, rows in list(stolen.items())[:10]:
                for oid, prog, odiv, tid, tdiv in rows:
                    print(f'    student {sid}: timetable {oid} ({prog} '
                          f'{odiv!r}) has them now; timetable {tid} wants '
                          f'{tdiv!r}. Moving them would empty {oid}.')
            return []

        if not targets:
            print('  No roster is empty for this reason.')
            return []

        plan = []
        for t in targets:
            tt, ids, held = t['tt'], t['ids'], t['held']
            plan.append({
                'summary': (f'{len(ids)} student(s) at {tt.school.school_name} '
                            f'grade {tt.grade}: division {held} -> '
                            f'{tt.division!r}'),
                'do': (lambda ids=ids, div=tt.division:
                       Student.objects.filter(id__in=ids).update(division=div)),
                'check': (lambda tt=tt, n=len(ids): self.roster_now(tt, n)),
            })
        return plan

    def roster_now(self, tt, expected):
        from student.models import Student
        n = Student.objects.filter(
            school=tt.school, student_class=str(tt.grade),
            division=tt.division, is_active=True).count()
        ok = n == expected
        print(f'    {tt.school.school_name} {tt.grade}-{tt.division}: '
              f'roster now {n} (expected {expected})  {"OK" if ok else "MISMATCH"}')
        return ok

    # ---------------------------------------------------------------- logins

    def plan_logins(self):
        """Email-shaped usernames carrying an uppercase letter."""
        rule('LOGINS  email-shaped usernames that are not lowercase')

        rows = [u for u in U.objects.filter(username__contains='@')
                if u.username != u.username.lower()]
        if not rows:
            print('  None.')
            return []

        # Two rows that would become the same username cannot both be changed.
        taken = set(U.objects.values_list('username', flat=True))
        plan = []
        for u in rows:
            low = u.username.lower()
            if low in taken and low != u.username:
                print(f'  SKIPPING {u.username!r}: {low!r} already exists. '
                      f'Settle that pair by hand first.')
                continue
            print(f'  {u.username!r} -> {low!r}   role={u.role} '
                  f'active={u.is_active}')
            plan.append({
                'summary': f'login {u.username!r} -> {low!r} (and its email, '
                           f'and any coach profile holding the same address)',
                'do': (lambda pk=u.pk, low=low, old=u.username:
                       self.lower_login(pk, low, old)),
                'check': lambda low=low: self.login_now(low),
            })
        return plan

    def lower_login(self, pk, low, old):
        from teacher.models import Teacher

        U.objects.filter(pk=pk).update(username=low, email=low)
        # The coach profile holds the address separately; leaving it in the
        # old case is how the two drift apart in the first place.
        Teacher.objects.filter(user_id=pk, official_email=old).update(
            official_email=low)

    def login_now(self, low):
        ok = U.objects.filter(username=low).exists()
        print(f'    login {low!r} present: {ok}')
        return ok

    # ---------------------------------------------------------------- verify

    def verify(self, plan):
        results = [item['check']() for item in plan if 'check' in item]
        if all(results):
            print('\n  All checks passed.')
        else:
            print('\n  SOME CHECKS FAILED — read the lines above.')
