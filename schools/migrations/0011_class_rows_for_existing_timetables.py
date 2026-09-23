"""Give every existing Timetable the Class row the parent screens read.

Class and Timetable hold the same four facts and nothing joined them. The
parent's "who teaches my child" and the School Admin's "what does this coach
teach" both read Class; the coach's own schedule and attendance read
Timetable. So a coordinator who filled in 50 timetables left parents seeing
"-" for the coach, because the Class rows were never created.

A post_save signal now carries the coach across whenever either is saved, but
rows written before it do not fix themselves. This creates what is missing.

Additive only: an existing Class is left alone apart from filling in a coach
it does not have. Nothing is deleted and no Timetable is touched. Reversing
is a no-op -- there is no way to tell which Class rows were made here from
the ones that were always there, and deleting the wrong ones would take real
data with them.
"""

import random

from django.db import migrations


def _class_code(existing_codes, grade, division, academic_year):
    """Mirror Class.save()'s generator; historical models have no methods."""
    year = (academic_year or '2025-2026').split('-')[0]
    stem = f'CLS-{year}-{grade}{(division or "").upper()}'
    for _ in range(50):
        code = f'{stem}-{random.randint(100, 999):03d}'
        if code not in existing_codes:
            return code
    # Vanishingly unlikely, but a collision must not abort a deploy.
    return f'{stem}-{len(existing_codes) + 1:04d}'


def backfill(apps, schema_editor):
    Class = apps.get_model('schools', 'Class')
    Timetable = apps.get_model('attendance', 'Timetable')

    codes = set(Class.objects.values_list('class_code', flat=True))
    made = linked = 0

    for tt in Timetable.objects.select_related(None).iterator():
        if not (tt.school_id and tt.grade and tt.division):
            continue
        match = Class.objects.filter(
            school_id=tt.school_id, grade=tt.grade, division=tt.division,
            academic_year=tt.academic_year,
        ).first()

        if match is None:
            code = _class_code(codes, tt.grade, tt.division, tt.academic_year)
            codes.add(code)
            Class.objects.create(
                school_id=tt.school_id,
                grade=tt.grade,
                division=tt.division,
                academic_year=tt.academic_year,
                thinking_coach_id=tt.thinking_coach_id,
                class_name=f'Std {tt.grade}{tt.division.upper()}',
                class_code=code,
            )
            made += 1
        elif match.thinking_coach_id is None and tt.thinking_coach_id:
            # Only fill a gap. An existing coach on the Class was put there
            # deliberately and is not this migration's to overwrite.
            match.thinking_coach_id = tt.thinking_coach_id
            match.save(update_fields=['thinking_coach'])
            linked += 1

    if made or linked:
        print(f'\n    created {made} Class row(s), '
              f'filled the coach on {linked} existing one(s)')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('schools', '0010_trim_school_names'),
        ('attendance', '0002_timetable_end_date_timetable_start_date_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
