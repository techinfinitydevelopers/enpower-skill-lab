"""Seed Framework objects and link existing Pillars, Projects, Schools."""
from django.db import migrations


def seed_and_link(apps, schema_editor):
    Framework = apps.get_model('competencies', 'Framework')
    Pillar = apps.get_model('competencies', 'Pillar')
    Project = apps.get_model('competencies', 'Project')
    School = apps.get_model('schools', 'School')

    # Create frameworks
    fsl, _ = Framework.objects.get_or_create(
        name='FSL', defaults={'prefix': 'SP', 'is_fixed': True, 'order': 1}
    )
    csl, _ = Framework.objects.get_or_create(
        name='CSL+', defaults={'prefix': 'CSL-SP', 'is_fixed': False, 'order': 2}
    )

    # Link pillars: old CharField 'CSL' → CSL+, everything else → FSL
    for pillar in Pillar.objects.all():
        if pillar.framework == 'CSL':
            pillar.framework_ref = csl
        else:
            pillar.framework_ref = fsl
        pillar.save()

    # Link projects: old CharField 'CSL' → CSL+, else → FSL
    for project in Project.objects.all():
        if project.framework == 'CSL':
            project.framework_ref = csl
        else:
            project.framework_ref = fsl
        project.save()

    # Link schools: old CharField 'CSL' → CSL+, else → FSL
    for school in School.objects.all():
        if school.framework_type == 'CSL':
            school.framework_ref = csl
        else:
            school.framework_ref = fsl
        school.save()


def reverse_seed(apps, schema_editor):
    Framework = apps.get_model('competencies', 'Framework')
    Framework.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('competencies', '0017_dynamic_framework'),
        ('schools', '0005_dynamic_framework'),
    ]

    operations = [
        migrations.RunPython(seed_and_link, reverse_seed),
    ]
