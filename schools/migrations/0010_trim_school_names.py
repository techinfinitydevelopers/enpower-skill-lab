"""Trim whitespace already stored in school names and codes.

A school saved as "Saint Capitanio " rejected 336 student rows that said
"Saint Capitanio". The two strings look identical on screen, and the import
matches exactly bar case, so nothing about the failure pointed at a space.

School.save() now strips, but rows written before it does not fix themselves:
they are only rewritten when someone edits them. This trims what is already
there.

Reversing is a no-op. The original whitespace carried no meaning and there is
nothing to restore it to.
"""

from django.db import migrations


def trim(apps, schema_editor):
    School = apps.get_model('schools', 'School')
    fixed = 0
    for school in School.objects.all().iterator():
        name = (school.school_name or '').strip()
        code = (school.school_code or '').strip()
        if name != school.school_name or code != school.school_code:
            school.school_name = name
            school.school_code = code
            # update_fields so nothing else on the row is touched.
            school.save(update_fields=['school_name', 'school_code'])
            fixed += 1
    if fixed:
        print(f'\n    trimmed {fixed} school name(s)/code(s)')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('schools', '0009_alter_class_thinking_coach'),
    ]

    operations = [
        migrations.RunPython(trim, noop),
    ]
