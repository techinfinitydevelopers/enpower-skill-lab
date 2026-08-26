"""
Seed the neoRiSE framework content — pillars, sub-pillars, competencies.

Follows the reporting-logic deck (Dashboard Slide.pptx):
  slide 4    FSL board
  slide 5    CSL+  = 3 pillars, 13 sub-pillars, KaushalBodh (KB1-KB3) inside it
  slide 6    CSL Foundation = KaushalBodh
  slide 7    3-6 competencies under each sub-pillar, SP1..SP17 numbering

Kaushal Bodh deliberately lives under the CSL frameworks, not FSL — profiling
is disabled for CSL (slide 16), which is what keeps KB out of career matches.

Run with:  python manage.py shell < seed_frameworks.py
        or  python seed_frameworks.py
"""

import os
import django

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'enpower_skill_lab.settings'
    django.setup()

from competencies.models import Framework, Pillar, SubPillar, Competency

# ── Framework definitions ────────────────────────────────────────────────
# is_fixed=True means the pillar codes are stable AND profiling runs
# (competencies/engine.py profiling_enabled).
FRAMEWORKS = [
    {'name': 'FSL',            'prefix': 'SP',      'is_fixed': True,  'order': 1},
    {'name': 'CSL+',           'prefix': 'CSL-SP',  'is_fixed': False, 'order': 2},
    {'name': 'CSL Foundation', 'prefix': 'CSLF',    'is_fixed': False, 'order': 3},
]

# ── Competency wording ───────────────────────────────────────────────────
# Four competencies per sub-pillar, each phrased as an observable behaviour so
# the rubric bands on slide 11 have something to grade against.
VERBS = [
    ('Identifies',  'Identifies and describes {topic} in familiar situations'),
    ('Applies',     'Applies {topic} to solve a defined problem with guidance'),
    ('Analyses',    'Analyses {topic} and explains the reasoning behind choices'),
    ('Evaluates',   'Evaluates {topic} independently and justifies the outcome'),
]

# ── FSL: 5 pillars, 17 sub-pillars (SP1..SP17) ──────────────────────────
FSL_PILLARS = [
    ('01', 'Self Exploration',     'purple', [
        ('Knowing Self',                     'self-awareness of strengths, interests and values'),
        ('Building Self',                    'goal setting, resilience and self-regulation'),
        ('Connect with the World',           'how personal identity relates to community and society'),
    ]),
    ('02', 'Foundational Literacy', 'teal', [
        ('Language & Communication',         'reading, writing and speaking to convey meaning'),
        ('Numeracy & Quantitative Reasoning','number sense, measurement and estimation'),
        ('Digital Literacy',                 'safe and purposeful use of digital tools'),
    ]),
    ('03', 'Tech of the Future',   'blue', [
        ('Computational Thinking',           'decomposition, patterns and algorithmic steps'),
        ('Data & AI Awareness',              'how data is collected, represented and used by AI'),
        ('Making & Prototyping',             'building, testing and iterating on a prototype'),
    ]),
    ('04', 'Human Skills',         'orange', [
        ('Collaboration',                    'shared goals, role-taking and group accountability'),
        ('Critical Thinking',                'questioning claims and weighing evidence'),
        ('Creativity & Innovation',          'generating and refining original ideas'),
        ('Empathy & Social Awareness',       'perspective-taking and responding to others’ needs'),
    ]),
    ('05', 'Future Competencies',  'green', [
        ('Entrepreneurial Mindset',          'spotting opportunity and taking calculated initiative'),
        ('Financial Literacy',               'budgeting, value and financial decision-making'),
        ('Sustainability & Environment',     'environmental impact and responsible choices'),
        ('Emerging Tech',                    'emerging technologies and their societal effects'),
    ]),
]

# ── CSL+: 3 pillars, 13 sub-pillars (slide 5) ───────────────────────────
CSL_PLUS_PILLARS = [
    ('01', 'KaushalBodh',          'amber',  True, [
        ('Practical Skills',                 'hands-on tool use, accuracy and task sequencing'),
        ('Workplace Awareness',              'safety, coordination and time discipline at work'),
        ('Essential Values',                 'responsibility, dignity of labour and respect for work'),
    ]),
    ('02', 'Future Competencies',  'green',  False, [
        ('Readiness for Future of Work',     'workplace readiness and adaptability'),
        ('Entrepreneurial Thinking',         'identifying a need and proposing a viable response'),
        ('Financial Awareness',              'earning, saving and cost of choices'),
        ('Sustainability Practices',         'resource use and waste reduction in practice'),
        ('Civic Responsibility',             'contribution to community and shared spaces'),
    ]),
    ('03', 'Tech of Future',       'blue',   False, [
        ('Digital Tools',                    'everyday digital tools for real tasks'),
        ('Computational Basics',             'step-wise logic and simple automation'),
        ('Data Awareness',                   'reading, recording and interpreting simple data'),
        ('Automation & Robotics',            'machines that sense, decide and act'),
        ('Emerging Tech Exposure',           'new technologies encountered in work and life'),
    ]),
]

# ── CSL Foundation: KaushalBodh only (slide 6) ──────────────────────────
CSL_FOUNDATION_PILLARS = [
    ('01', 'KaushalBodh',          'amber',  True, [
        ('Practical Skills',                 'basic tool handling and careful task completion'),
        ('Workplace Awareness',              'safe habits and working alongside others'),
        ('Essential Values',                 'responsibility and respect for all kinds of work'),
    ]),
]

# sp_number is globally unique across frameworks, so each framework gets its
# own band. The displayed code comes from SubPillar.code, not from this number.
SP_NUMBER_BASE = {'FSL': 1, 'CSL+': 101, 'CSL Foundation': 201}

# Competency codes must be globally unique. FSL keeps the plain SP1.C1 form the
# deck uses; CSL frameworks are prefixed so their KB1.C1 rows cannot collide.
CODE_PREFIX = {'FSL': '', 'CSL+': 'CSL-', 'CSL Foundation': 'CSLF-'}

STAGE_FOR_SP = 'Middle'   # the program runs for grades 6-9


def wipe():
    """Remove existing framework content so the seed is deterministic.

    Pillar deletion cascades: SubPillar -> Competency -> AssessmentCompetency
    -> ScoreEntry. Projects and reports are rebuilt by seed_projects.py, so
    that data is expected to go with it.
    """
    n_pillars = Pillar.objects.count()
    n_comps   = Competency.objects.count()
    Pillar.objects.all().delete()
    print(f'  wiped {n_pillars} pillars / {n_comps} competencies')


def seed_frameworks():
    out = {}
    for spec in FRAMEWORKS:
        fw, created = Framework.objects.update_or_create(
            name=spec['name'],
            defaults={'prefix': spec['prefix'], 'is_fixed': spec['is_fixed'],
                      'order': spec['order']},
        )
        out[fw.name] = fw
        print(f'  {"created" if created else "updated"} framework {fw.name:16} '
              f'prefix={fw.prefix:8} is_fixed={fw.is_fixed}')
    return out


def seed_pillars(framework, pillar_specs, has_kb_flag):
    """Create pillars, sub-pillars and competencies for one framework.

    Two passes: SubPillar.code is derived from the sub-pillar's index across the
    whole framework, so every sub-pillar must exist before any competency code
    is built from it — otherwise a mid-loop code would be off by however many
    sub-pillars are still to come.
    """
    sp_num  = SP_NUMBER_BASE[framework.name]
    prefix  = CODE_PREFIX[framework.name]
    topics  = {}
    made    = {'pillars': 0, 'sub_pillars': 0, 'competencies': 0}

    # Pass 1 — pillars and sub-pillars
    for spec in pillar_specs:
        if has_kb_flag:
            number, name, color, is_kb, sub_pillars = spec
        else:
            number, name, color, sub_pillars = spec
            is_kb = False

        pillar = Pillar.objects.create(
            name=name, number=number, color=color, order=int(number),
            framework_ref=framework, framework=framework.name, is_kb=is_kb,
        )
        made['pillars'] += 1

        for sp_name, topic in sub_pillars:
            sp = SubPillar.objects.create(
                pillar=pillar, sp_number=sp_num, name=sp_name)
            topics[sp.id] = topic
            sp_num += 1
            made['sub_pillars'] += 1

    # Pass 2 — competencies, coded off the now-stable sub-pillar codes
    for sp in SubPillar.objects.filter(pillar__framework_ref=framework):
        # KB sub-pillars carry the framework-agnostic KB1/KB2/KB3 code, so they
        # need the framework prefix added to stay globally unique. Non-KB codes
        # already start with the framework prefix.
        label = sp.code if sp.code.startswith(framework.prefix) else f'{prefix}{sp.code}'
        for i, (verb, template) in enumerate(VERBS, start=1):
            Competency.objects.create(
                sub_pillar=sp,
                code=f'{label}.C{i}',
                name=f'{verb} {sp.name}',
                description=template.format(topic=topics[sp.id]),
                stage=STAGE_FOR_SP,
                status='Active',
            )
            made['competencies'] += 1

    print(f'  {framework.name:16} pillars={made["pillars"]:2} '
          f'sub-pillars={made["sub_pillars"]:2} competencies={made["competencies"]:3}')
    return made


def run():
    print('Seeding framework content')
    wipe()
    fws = seed_frameworks()
    seed_pillars(fws['FSL'], FSL_PILLARS, has_kb_flag=False)
    seed_pillars(fws['CSL+'], CSL_PLUS_PILLARS, has_kb_flag=True)
    seed_pillars(fws['CSL Foundation'], CSL_FOUNDATION_PILLARS, has_kb_flag=True)

    print('\nVerification')
    for fw in Framework.objects.all():
        sps = SubPillar.objects.filter(pillar__framework_ref=fw)
        comps = Competency.objects.filter(sub_pillar__pillar__framework_ref=fw)
        kb = Pillar.objects.filter(framework_ref=fw, is_kb=True).count()
        print(f'  {fw.name:16} pillars={fw.pillars.count():2} sub-pillars={sps.count():2} '
              f'competencies={comps.count():3} kb_pillars={kb}')

    print('\n  sub-pillar codes')
    for sp in SubPillar.objects.select_related('pillar__framework_ref'):
        fw = sp.pillar.framework_ref.name if sp.pillar.framework_ref else '-'
        first = sp.competencies.first()
        print(f'    [{fw:14}] {sp.code:10} {sp.name:32} first_comp={first.code if first else "-"}')


if __name__ == '__main__':
    run()
