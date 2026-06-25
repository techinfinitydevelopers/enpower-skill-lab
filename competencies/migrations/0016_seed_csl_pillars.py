"""Seed CSL+ framework with same pillars and sub-pillars as FSL (all editable)."""
from django.db import migrations
from django.db.models import Max


CSL_PILLARS = [
    {'number': 'C1', 'name': 'Self Exploration',       'color': 'teal',   'order': 1},
    {'number': 'C2', 'name': 'Foundational Literacy',  'color': 'purple', 'order': 2},
    {'number': 'C3', 'name': 'Tech of the Future',     'color': 'blue',   'order': 3},
    {'number': 'C4', 'name': 'Human Skills',           'color': 'orange', 'order': 4},
    {'number': 'C5', 'name': 'Future Competencies',    'color': 'green',  'order': 5},
]

CSL_SUB_PILLARS = [
    {'pillar_idx': 0, 'name': 'Self-discovery, Interest & Values'},
    {'pillar_idx': 0, 'name': 'Personality Development & Communication'},
    {'pillar_idx': 0, 'name': 'Connecting to the World'},
    {'pillar_idx': 1, 'name': 'Digital, Media & Data Literacy'},
    {'pillar_idx': 1, 'name': 'Financial & Economic Literacy'},
    {'pillar_idx': 1, 'name': 'Environmental & Sustainability Literacy'},
    {'pillar_idx': 2, 'name': 'Smart Systems, IoT'},
    {'pillar_idx': 2, 'name': 'AI, Coding, ML, Robotics'},
    {'pillar_idx': 2, 'name': 'Design, Emerging Tech'},
    {'pillar_idx': 3, 'name': 'Critical Thinking & Problem Solving'},
    {'pillar_idx': 3, 'name': 'Creativity & Innovation'},
    {'pillar_idx': 3, 'name': 'Collaboration'},
    {'pillar_idx': 3, 'name': 'Emotional Intelligence (SEL)'},
    {'pillar_idx': 4, 'name': 'Design Thinking'},
    {'pillar_idx': 4, 'name': 'Entrepreneurial Mindset'},
    {'pillar_idx': 4, 'name': 'Global Citizenship & Cross-cultural Awareness'},
    {'pillar_idx': 4, 'name': 'Readiness for Future of Work'},
]


def seed_csl(apps, schema_editor):
    Pillar = apps.get_model('competencies', 'Pillar')
    SubPillar = apps.get_model('competencies', 'SubPillar')

    if Pillar.objects.filter(framework='CSL').exists():
        return

    max_sp = SubPillar.objects.aggregate(Max('sp_number'))['sp_number__max'] or 17
    next_sp = max_sp + 1

    created_pillars = []
    for p_data in CSL_PILLARS:
        pillar = Pillar.objects.create(
            name=p_data['name'], number=p_data['number'],
            color=p_data['color'], order=p_data['order'],
            framework='CSL', is_kb=False,
        )
        created_pillars.append(pillar)

    for sp_data in CSL_SUB_PILLARS:
        pillar = created_pillars[sp_data['pillar_idx']]
        SubPillar.objects.create(
            pillar=pillar, sp_number=next_sp, name=sp_data['name'],
        )
        next_sp += 1


def reverse_csl(apps, schema_editor):
    Pillar = apps.get_model('competencies', 'Pillar')
    Pillar.objects.filter(framework='CSL').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('competencies', '0015_add_framework_support'),
    ]

    operations = [
        migrations.RunPython(seed_csl, reverse_csl),
    ]
