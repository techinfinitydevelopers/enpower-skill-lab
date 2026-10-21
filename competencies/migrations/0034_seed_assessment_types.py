"""Fill the assessment-type list from what is already in use.

The three shipped types go in, and so does every other value any Assessment
already carries -- a database seeded or imported with something else must not
find its own types missing from the dropdown the moment the list becomes a
table.
"""

from django.db import migrations

SHIPPED = ['Presentation', 'Written', 'Oral/Portfolio']


def seed(apps, schema_editor):
    AssessmentType = apps.get_model('competencies', 'AssessmentType')
    Assessment = apps.get_model('competencies', 'Assessment')

    in_use = [t for t in Assessment.objects
              .exclude(assessment_type='')
              .values_list('assessment_type', flat=True).distinct()
              if t]

    seen = set()
    names = [n for n in SHIPPED + sorted(in_use)
             if not (n in seen or seen.add(n))]

    for order, name in enumerate(names):
        AssessmentType.objects.get_or_create(
            name=name, defaults={'order': order})


def undo(apps, schema_editor):
    apps.get_model('competencies', 'AssessmentType').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [('competencies', '0033_assessmenttype')]

    operations = [migrations.RunPython(seed, undo)]
