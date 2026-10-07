"""Stamp rows with the year they actually belong to. Dry run unless told.

Nothing in the project knew what year it was: four model fields and two views
each carried the literal string '2025-2026' as their default. So every class,
timetable and session created after April 2026 was stamped a year behind --
which is why the Super Admin's 2026-2027 filter found nothing and the School
Admin's Class Overview still read 2025-2026. The dropdowns were right; the
rows were not.

The defaults compute the year now, so new rows are correct. This is for the
ones already stored, and it never guesses: each row is judged against a date
it carries itself.

    Timetable              its start_date
    AttendanceSession      the session date
    DailySessionFeedback   the feedback date
    StudentProjectUpload   when it was uploaded
    Class                  the timetable it mirrors, matched on
                           school + grade + division

A row with no date of its own, and a Class with no timetable behind it, is
left exactly as it is and reported, because there is nothing to judge it by.

    python manage.py fix_academic_year            # show, change nothing
    python manage.py fix_academic_year --apply
"""

from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from enpower_skill_lab.academic_year import academic_year_for


def rule(title):
    print(f'\n{"=" * 68}\n{title}\n{"=" * 68}')


class Command(BaseCommand):
    help = 'Re-stamp academic years from each row\'s own date. Dry run by default.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Actually write. Without this nothing is changed.')

    def handle(self, *args, **opts):
        apply_it = opts['apply']
        print('  MODE: ' + ('APPLYING CHANGES' if apply_it
                            else 'dry run — nothing will be written'))

        plans = []
        plans += self.plan_dated()
        plans += self.plan_classes()

        total = sum(p['n'] for p in plans)
        rule('WHAT WOULD CHANGE' if not apply_it else 'APPLYING')
        if not total:
            print('  Nothing to change. Every row already agrees with its own date.')
            return
        for p in plans:
            print(f'    {p["summary"]}')
        print(f'\n    {total} row(s) in all')

        if not apply_it:
            print('\n  Re-run with --apply to make these changes.')
            return

        with transaction.atomic():
            for p in plans:
                p['do']()
        print('\n  Done. Verifying...')
        self.verify()

    # ------------------------------------------------------- rows with a date

    def plan_dated(self):
        """Models that carry the date they happened on."""
        from attendance.models import (AttendanceSession, DailySessionFeedback,
                                       StudentProjectUpload, Timetable)

        targets = [
            (Timetable, 'start_date', 'timetables'),
            (AttendanceSession, 'date', 'attendance sessions'),
            (DailySessionFeedback, 'date', 'daily feedbacks'),
            (StudentProjectUpload, 'created_at', 'project uploads'),
        ]

        plans = []
        for model, field, label in targets:
            rule(f'{label.upper()}  judged by their own {field}')
            wrong, undated = {}, 0
            for row in model.objects.all().only('id', field, 'academic_year'):
                when = getattr(row, field, None)
                when = getattr(when, 'date', lambda: when)() if hasattr(
                    when, 'date') else when
                should = academic_year_for(when)
                if should is None:
                    undated += 1
                    continue
                if row.academic_year != should:
                    wrong.setdefault((row.academic_year, should), []).append(row.id)

            print(f'  {model.objects.count()} row(s); '
                  f'{undated} with no {field} to judge by, left alone')
            if not wrong:
                print('  every dated row already agrees with its own date')
            for (was, should), ids in sorted(wrong.items()):
                print(f'    {len(ids):>5} say {was!r} but their {field} '
                      f'says {should!r}')
                plans.append({
                    'n': len(ids),
                    'summary': f'{len(ids)} {label}: {was!r} -> {should!r}',
                    'do': (lambda m=model, ids=ids, s=should:
                           m.objects.filter(id__in=ids).update(academic_year=s)),
                })
        return plans

    # -------------------------------------------------------------- the rest

    def plan_classes(self):
        """Class rows mirror a timetable, so they follow one."""
        from attendance.models import Timetable
        from schools.models import Class

        rule('CLASSES  judged by the timetable they mirror')

        by_key = {}
        for tt in Timetable.objects.exclude(start_date=None):
            key = (tt.school_id, str(tt.grade), tt.division)
            should = academic_year_for(tt.start_date)
            by_key.setdefault(key, set()).add(should)

        wrong, orphan, disputed = {}, 0, 0
        for row in Class.objects.all():
            key = (row.school_id, str(row.grade), row.division)
            years = by_key.get(key)
            if not years:
                orphan += 1
                continue
            if len(years) > 1:
                # Two timetables for one class disagreeing is not something to
                # settle by picking one.
                disputed += 1
                continue
            should = next(iter(years))
            if row.academic_year != should:
                wrong.setdefault((row.academic_year, should), []).append(row.id)

        print(f'  {Class.objects.count()} class(es); {orphan} with no dated '
              f'timetable behind them, left alone')
        if disputed:
            print(f'  {disputed} matched by timetables that disagree — left alone')
        if not wrong:
            print('  every class already agrees with its timetable')

        plans = []
        for (was, should), ids in sorted(wrong.items()):
            print(f'    {len(ids):>5} say {was!r} but their timetable '
                  f'says {should!r}')
            plans.append({
                'n': len(ids),
                'summary': f'{len(ids)} classes: {was!r} -> {should!r}',
                'do': (lambda ids=ids, s=should:
                       Class.objects.filter(id__in=ids).update(academic_year=s)),
            })
        return plans

    # ---------------------------------------------------------------- verify

    def verify(self):
        from attendance.models import Timetable
        from schools.models import Class

        for model, label in ((Class, 'classes'), (Timetable, 'timetables')):
            spread = Counter(model.objects.values_list('academic_year', flat=True))
            print(f'    {label}: {dict(sorted(spread.items()))}')
