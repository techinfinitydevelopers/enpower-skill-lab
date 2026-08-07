"""Backfill structured onboarding IDs for existing students & parents.

Converts old / random IDs to the spec format:
    Student  ->  SV-RG-6A-222-26-stu
    Parent   ->  SV-RG-6A-222-26-par   (shares the child's base)

The ID doubles as the login username and the initial password (spec:
"Password can be same as id"). Accounts that already have the correct
`-stu` / `-par` suffix are left untouched.

Usage:
    python manage.py backfill_structured_ids            # DRY RUN (no changes)
    python manage.py backfill_structured_ids --apply    # actually update

ALWAYS back up db.sqlite3 before running with --apply.
"""
import re
from django.core.management.base import BaseCommand
from django.db import transaction

_RANDOM_PARENT_ID = re.compile(r'^P[A-Z0-9]{5}$')


class Command(BaseCommand):
    help = "Backfill structured -stu / -par IDs (and login username+password) for existing students & parents."

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Actually write changes. Without this flag the command is a dry run.',
        )

    def handle(self, *args, **options):
        from student.models import Student
        from parent.models import Parent
        from accounts.onboarding_ids import student_id_for, parent_id_from_student

        apply = options['apply']
        mode = 'APPLY' if apply else 'DRY RUN'
        self.stdout.write(self.style.WARNING(f'=== Backfill structured IDs — {mode} ==='))

        student_changes = []
        parent_changes = []
        students_no_user = 0
        parents_no_child = 0

        with transaction.atomic():
            # ----- Students -----
            for s in Student.objects.select_related('school', 'user').all():
                cur = (s.skill_lab_reg_id or '').strip()
                if cur.endswith('-stu'):
                    continue
                new_id = student_id_for(
                    s.school, s.first_name, s.last_name, s.student_class, s.division,
                    s.date_of_birth, s.academic_year, fallback_school_name=(s.school_name or ''),
                )
                student_changes.append((s.full_name, cur or '(blank)', new_id))
                if apply:
                    s.skill_lab_reg_id = new_id
                    s.save(update_fields=['skill_lab_reg_id'])
                    if s.user:
                        s.user.username = new_id
                        s.user.set_password(new_id)
                        s.user.save(update_fields=['username', 'password'])
                    else:
                        students_no_user += 1
                elif not s.user:
                    students_no_user += 1

            # ----- Parents (only those linked to a student) -----
            for p in Parent.objects.select_related('user').prefetch_related('students').all():
                cur = (p.parent_id or '').strip()
                if cur.endswith('-par'):
                    continue
                child = p.students.first()
                if not child:
                    parents_no_child += 1
                    continue
                new_id = parent_id_from_student(child)
                parent_changes.append((p.full_name, cur or '(blank)', new_id))
                if apply:
                    p.parent_id = new_id
                    p.save(update_fields=['parent_id'])
                    if p.user:
                        p.user.username = new_id
                        p.user.set_password(new_id)
                        p.user.save(update_fields=['username', 'password'])

            if not apply:
                # Dry run — undo anything (nothing was written, but be safe).
                transaction.set_rollback(True)

        # ----- Report -----
        self.stdout.write(f'\nStudents to update: {len(student_changes)} '
                          f'(without a linked user account: {students_no_user})')
        for name, old, new in student_changes:
            self.stdout.write(f'  {old}  ->  {new}   | {name}')
        self.stdout.write(f'\nParents to update: {len(parent_changes)} '
                          f'(skipped, no linked child: {parents_no_child})')
        for name, old, new in parent_changes:
            self.stdout.write(f'  {old}  ->  {new}   | {name}')

        if apply:
            self.stdout.write(self.style.SUCCESS('\nDONE — changes written.'))
        else:
            self.stdout.write(self.style.WARNING(
                '\nDRY RUN — nothing changed. Re-run with --apply to write these changes.'))
