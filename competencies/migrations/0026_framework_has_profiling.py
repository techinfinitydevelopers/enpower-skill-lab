from django.db import migrations, models


def seed_has_profiling(apps, schema_editor):
    """Preserve today's behaviour, then switch FSL back on.

    Profiling used to be gated on `is_fixed`, so copying it across keeps every
    existing framework exactly where it was. FSL is then enabled explicitly:
    it is the framework that carries the neoRiSE profile mapping, and it lost
    profiling only because it was recreated through Manage Frameworks (which
    always writes is_fixed=False).
    """
    Framework = apps.get_model('competencies', 'Framework')
    for fw in Framework.objects.all():
        fw.has_profiling = fw.is_fixed
        fw.save(update_fields=['has_profiling'])
    Framework.objects.filter(name__iexact='FSL').update(has_profiling=True)


def unseed(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('competencies', '0025_projectreport_common_strengths_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='framework',
            name='has_profiling',
            field=models.BooleanField(default=False, help_text='Run profile mapping and Skill Passport for this framework'),
        ),
        migrations.RunPython(seed_has_profiling, unseed),
    ]
