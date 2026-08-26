"""
Seed the 15 profile -> competency mappings (deck slide 3).

Slide 3: "There are 15 profiles. Each profile is mapped to a max of 2-3 primary
competency and 2 secondary competency."

Without these mappings the profiling engine can never unlock a profile, so the
Skill Passport renders with no career matches at all. Mappings point at FSL
competencies — profiling only runs for FSL (engine.profiling_enabled).

Run with:  python seed_profiles.py
"""

import os
import django

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'enpower_skill_lab.settings'
    django.setup()

from competencies.models import Profile, Competency

# (number, name, [primary codes], [secondary codes])
#
# Related profiles deliberately SHARE a primary competency — the deck's own
# worked example (slide 21/22) has SP1.C3 running through several profiles, and
# step 5 asks for the "common strengths" across a student's top matches. With
# fully disjoint primaries there is nothing for that step to report.
# Profiles are grouped in threes because a project is built around one trio.
PROFILES = [
    # trio 1 — shares SP11.C3 (Research/Design) and SP9.C2 (Design/Creative)
    (1,  'Research Scholar',        ['SP11.C3', 'SP8.C2',  'SP4.C3'],  ['SP6.C2',  'SP17.C1']),
    (2,  'Design Thinker',          ['SP11.C3', 'SP9.C2',  'SP12.C3'], ['SP10.C2', 'SP13.C2']),
    (3,  'Creative Maker',          ['SP9.C2',  'SP12.C2', 'SP7.C2'],  ['SP6.C3',  'SP17.C2']),
    # trio 2 — shares SP11.C4 (Analyst/Communicator) and SP3.C3 (Communicator/Environment)
    (4,  'Critical Analyst',        ['SP11.C4', 'SP8.C3',  'SP5.C3'],  ['SP4.C2',  'SP7.C3']),
    (5,  'Global Communicator',     ['SP11.C4', 'SP4.C4',  'SP3.C3'],  ['SP10.C3', 'SP6.C2']),
    (6,  'Environmental Champion',  ['SP3.C3',  'SP16.C3', 'SP12.C1'], ['SP11.C1', 'SP10.C1']),
    # trio 3 — shares SP14.C2 (Steward/Entrepreneur) and SP2.C4 (Well-Being/Entrepreneur)
    (7,  'Financial Steward',       ['SP14.C2', 'SP15.C3', 'SP5.C4'],  ['SP11.C2', 'SP2.C3']),
    (8,  'Well-Being Navigator',    ['SP2.C4',  'SP1.C3',  'SP13.C4'], ['SP3.C1',  'SP10.C2']),
    (9,  'Entrepreneur',            ['SP14.C2', 'SP2.C4',  'SP15.C2'], ['SP10.C4', 'SP11.C3']),
    # trio 4 — shares SP7.C3 (Digital/Community) and SP6.C4 (Digital/Data)
    (10, 'Digital Navigator',       ['SP7.C3',  'SP6.C4',  'SP17.C3'], ['SP8.C1',  'SP9.C1']),
    (11, 'Community Builder',       ['SP7.C3',  'SP10.C4', 'SP13.C1'], ['SP4.C1',  'SP16.C1']),
    (12, 'Data Storyteller',        ['SP6.C4',  'SP8.C4',  'SP5.C2'],  ['SP6.C1',  'SP11.C4']),
    # trio 5 — shares SP11.C3 (Systems/Reflective) and SP7.C4 (Systems/Tech)
    (13, 'Systems Thinker',         ['SP11.C3', 'SP7.C4',  'SP16.C2'], ['SP8.C2',  'SP12.C3']),
    (14, 'Reflective Learner',      ['SP11.C3', 'SP1.C4',  'SP2.C2'],  ['SP13.C3', 'SP4.C4']),
    (15, 'Tech Innovator',          ['SP7.C4',  'SP17.C4', 'SP9.C4'],  ['SP12.C2', 'SP6.C3']),
]


def run():
    by_code = {c.code: c for c in Competency.objects.all()}
    missing = set()

    print('Seeding 15 profile mappings')
    # Numbers are unique, so a stale profile sitting on a number we want would
    # block update_or_create. Clear the table and rebuild it deterministically.
    Profile.objects.all().delete()

    for number, name, primary, secondary in PROFILES:
        p_objs = [by_code[c] for c in primary   if c in by_code]
        s_objs = [by_code[c] for c in secondary if c in by_code]
        missing.update(c for c in primary + secondary if c not in by_code)

        profile = Profile.objects.create(number=number, name=name)
        profile.primary_competencies.set(p_objs)
        profile.secondary_competencies.set(s_objs)

    if missing:
        print(f'  WARNING: competency codes not found: {sorted(missing)}')

    print('\nVerification')
    ok = 0
    for p in Profile.objects.prefetch_related('primary_competencies', 'secondary_competencies'):
        np, ns = p.primary_competencies.count(), p.secondary_competencies.count()
        good = 2 <= np <= 3 and ns == 2
        ok += good
        print(f'  {"OK " if good else "BAD"} {p.number:2}. {p.name:24} primary={np} secondary={ns}  '
              f'{[c.code for c in p.primary_competencies.all()]}')
    print(f'\n  {ok}/{Profile.objects.count()} profiles correctly mapped (2-3 primary, 2 secondary)')


if __name__ == '__main__':
    run()
