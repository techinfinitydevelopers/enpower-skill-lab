"""
Seed the 8 skill profiles the client confirmed.

Migration 0027 already puts these 8 in place, so a fresh database does not need
this script; it exists to put the list back after the profiles have been edited
or wiped by hand.

Only the names are seeded. The earlier version of this file also wrote a
competency mapping for each of 15 placeholder profiles - those mappings were
invented to give the profiling engine something to work with and do not apply
to the confirmed names, so they are gone. Until the Super Admin maps each
profile on Skill Passport > Profiles & Competencies, the profiling engine can
unlock nothing and the Skill Passport shows no career matches.

Profiling only runs for FSL (engine.profiling_enabled), so these are the FSL
profiles; the model has no per-framework profile split.

Run with:  python seed_profiles.py
"""

import os
import django

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'enpower_skill_lab.settings'
    django.setup()

from competencies.models import Profile

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


def run():
    print('Seeding the 8 skill profiles')

    # number is unique, so a profile already sitting on 1-8 is renamed rather
    # than inserted alongside. Whatever mapping it carries is left alone.
    for number, name in PROFILES:
        profile, created = Profile.objects.update_or_create(
            number=number, defaults={'name': name})
        print(f"  {'created' if created else 'updated'}  {number}. {name}")

    stale = Profile.objects.exclude(number__in=[n for n, _ in PROFILES])
    if stale.exists():
        print('\nRemoving profiles beyond the confirmed 8:')
        for profile in stale:
            print(f"  removed  {profile.number}. {profile.name}")
        stale.delete()

    print('\nMapping check')
    unmapped = 0
    for p in Profile.objects.prefetch_related('primary_competencies',
                                              'secondary_competencies'):
        np = p.primary_competencies.count()
        ns = p.secondary_competencies.count()
        if np < 2:
            unmapped += 1
        print(f'  {p.number}. {p.name:24} primary={np} secondary={ns}')

    if unmapped:
        print(f'\n  {unmapped} profile(s) have fewer than 2 primary '
              f'competencies and can never unlock. Map them on '
              f'Skill Passport > Profiles & Competencies.')


if __name__ == '__main__':
    run()
