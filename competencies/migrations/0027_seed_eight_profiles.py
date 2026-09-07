from django.db import migrations

# The client confirmed 8 skill profiles. Migration 0004 seeded 15 placeholder
# names, so a fresh database (the server was wiped) would otherwise come up
# with the old list. Nothing points a foreign key at Profile - a report stores
# its matches in ProjectReport.top_3_profiles as JSON - so dropping the extras
# is safe.
PROFILES = [
    (1, 'Tech Explorer'),
    (2, 'Data Detective'),
    (3, 'Young Entrepreneur'),
    (4, 'Creative Innovator'),
    (5, 'Skilled Maker'),
    (6, 'Digital Navigator'),
    (7, 'Community Builder'),
    (8, 'Confident Communicator'),
]


def seed(apps, schema_editor):
    Profile = apps.get_model('competencies', 'Profile')

    # number is unique, so a placeholder already sitting on 1-8 is renamed
    # rather than inserted alongside. Competency mappings are left alone.
    for number, name in PROFILES:
        Profile.objects.update_or_create(number=number, defaults={'name': name})

    Profile.objects.exclude(number__in=[n for n, _ in PROFILES]).delete()


def unseed(apps, schema_editor):
    # 0004's own seed is the state to fall back to; it runs get_or_create, so
    # reversing this migration and re-running forwards is not lossy beyond the
    # names themselves.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('competencies', '0026_framework_has_profiling'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
