"""Copying an assessment from one project into another.

    "In project configuration, option to clone/copy existing assessment from
     other projects and edit them."  -- Phase 2 deck, Super Admin small
     change 1

Built because the same project exists under more than one framework and the
assessments were only ever written under one of them. BKG Global School sits
on CSL +, where the Grade 6 and Grade 7 projects had no assessments at all,
while their FSL twins had four each -- so the coach's Assessment dropdown was
empty and no student list would load.

**The whole thing turns on matching competencies by name.** Each framework
owns its own competency rows: FSL spells one 'Skills-SP1.C1' and CSL + spells
the same competency 'KB1.C1'. Copying ids across frameworks would map to
nothing; copying codes would map to nothing either. The names are what the
two have in common, and that is what the checks below hold.

A competency with no counterpart is skipped, not guessed at, and the page
says which ones -- a silently thinner copy is the one outcome nobody would
notice.

Everything runs inside a transaction that is rolled back.

Run with:  python verify_clone_assessment.py
"""

import os

import django

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'enpower_skill_lab.settings'
    django.setup()

from django.conf import settings

settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

from django.contrib.auth import get_user_model
from django.db import transaction

from competencies.models import (Assessment, AssessmentCompetency, Competency,
                                 Framework, Pillar, Project, SubPillar)
from verify_client import HttpsClient as Client

U = get_user_model()
PASSWORD = 'Zz!2026pw'
PA = '/super-admin/skill-passport/project-assessment/'

# The same three competencies, named identically, coded differently -- which
# is exactly how FSL and CSL + hold them in production.
SHARED = ['Zz Tool Usage', 'Zz Task Planning', 'Zz Digital Ethics']

PASS, FAIL = [], []


def check(label, ok, detail=''):
    (PASS if ok else FAIL).append(label)
    print(f'  {"PASS" if ok else "FAIL"}  {label}'
          f'{("  - " + str(detail)) if detail else ""}')


class Rollback(Exception):
    """Raised once the checks are done, to undo everything they created."""


def sign_in(user):
    user.set_password(PASSWORD)
    user.save(update_fields=['password'])
    client = Client()
    assert client.login(username=user.username, password=PASSWORD), user.username
    return client


def page(client, url):
    return client.get(url, follow=True).content.decode('utf-8', 'replace')


# ------------------------------------------------------------------ fixtures

def framework_with_competencies(name, prefix, code_prefix, sp_number,
                                extra=None):
    """A framework carrying SHARED by name, under its own codes."""
    fw = Framework.objects.create(name=name, prefix=prefix)
    pillar = Pillar.objects.create(name=f'{name} Pillar', number='1',
                                   color='teal', order=1, framework_ref=fw)
    sub = SubPillar.objects.create(pillar=pillar, sp_number=sp_number,
                                   name=f'{name} Sub')
    comps = {}
    for i, label in enumerate(SHARED + (extra or []), start=1):
        comps[label] = Competency.objects.create(
            sub_pillar=sub, code=f'{code_prefix}.C{i}', name=label,
            stage='Middle', status='Active')
    return fw, comps


def build():
    """Two frameworks, a filled source project and an empty target."""
    # sp_number is unique across the table, so these sit well clear of the
    # seeded 1-17.
    source_fw, source_comps = framework_with_competencies(
        'ZZ Source FW', 'ZZSRC', 'ZZSRC-SP1', 901,
        extra=['Zz Only Here'])
    target_fw, target_comps = framework_with_competencies(
        'ZZ Target FW', 'ZZTGT', 'ZZTGT-SP1', 902)

    source = Project.objects.create(title='Zz Source Project', grade='7',
                                    status='Active', framework_ref=source_fw,
                                    sequence_number=1)
    target = Project.objects.create(title='Zz Target Project', grade='7',
                                    status='Active', framework_ref=target_fw,
                                    sequence_number=1)

    first = Assessment.objects.create(
        project=source, name='Zz Viva', assessment_type='Oral/Portfolio',
        placement_after_challenge=2, output_descriptor='Zz descriptor',
        additional_instructions='Zz instructions', order=0)
    second = Assessment.objects.create(
        project=source, name='Zz Written', assessment_type='Written', order=1)

    # The first carries all four, one of which the target framework lacks.
    for i, label in enumerate(SHARED + ['Zz Only Here']):
        AssessmentCompetency.objects.create(
            assessment=first, competency=source_comps[label],
            comp_type='group' if i == 0 else 'individual', order=i)
    AssessmentCompetency.objects.create(
        assessment=second, competency=source_comps[SHARED[0]],
        comp_type='individual', order=0)

    boss = U.objects.create_user(
        username='zz.clone.super@example.com', password=PASSWORD,
        email='zz.clone.super@example.com', role='SUPER_ADMIN',
        is_staff=True, is_superuser=True)

    return source, target, source_comps, target_comps, boss


def copy(client, target, source, which='all'):
    return client.post(f'{PA}?project={target.id}', {
        'action': 'clone_assessment',
        'source_project': source.id,
        'source_assessment': which,
    }, follow=True)


# -------------------------------------------------------------------- checks

def check_form(client, target, source):
    print('\n1. the option is on the page')
    html = page(client, f'{PA}?project={target.id}')
    check('a Copy control is offered', 'clone_assessment' in html)
    check('the source project is listed as a choice',
          'Zz Source Project' in html)
    check('its framework is named, so two same-titled projects can be told apart',
          'ZZ Source FW' in html)


def check_copy_all(client, target, source, target_comps):
    print('\n2. copying every assessment across frameworks')
    copy(client, target, source)

    made = list(target.assessments.order_by('order', 'id'))
    check('both assessments arrived', len(made) == 2, len(made))
    if len(made) != 2:
        return None

    first, second = made
    check('the name came with it', first.name == 'Zz Viva', first.name)
    check('the type came with it',
          first.assessment_type == 'Oral/Portfolio', first.assessment_type)
    check('the placement came with it',
          first.placement_after_challenge == 2,
          first.placement_after_challenge)
    check('the output descriptor came with it',
          first.output_descriptor == 'Zz descriptor', first.output_descriptor)
    check('the teacher instructions came with it',
          first.additional_instructions == 'Zz instructions',
          first.additional_instructions)
    check('order is kept', [a.order for a in made] == [0, 1],
          [a.order for a in made])
    return first


def check_mapping_by_name(first, target_comps):
    print('\n3. competencies are matched by name, not by code')
    if first is None:
        check('an assessment to inspect', False)
        return

    rows = list(first.competency_mappings.select_related('competency')
                .order_by('order'))
    names = [r.competency.name for r in rows]

    check('the three shared competencies mapped', names == SHARED, names)
    check('they are the TARGET framework rows, not the source ones',
          all(r.competency_id == target_comps[r.competency.name].id
              for r in rows))
    check('their codes are the target framework codes',
          all(r.competency.code.startswith('ZZTGT') for r in rows),
          [r.competency.code for r in rows])
    check('individual/group is carried over',
          [r.comp_type for r in rows] == ['group', 'individual', 'individual'],
          [r.comp_type for r in rows])
    check('the competency with no counterpart was left out, not guessed',
          'Zz Only Here' not in names)


def check_warning_said_so(client, target, source):
    print('\n4. a skipped competency is reported, not swallowed')
    target.assessments.all().delete()
    response = copy(client, target, source)
    body = response.content.decode('utf-8', 'replace')
    check('the page names the competency it could not match',
          'Zz Only Here' in body)


def check_one_at_a_time(client, target, source):
    print('\n5. a single assessment, and copies add rather than replace')
    target.assessments.all().delete()

    only = source.assessments.get(name='Zz Written')
    copy(client, target, source, which=only.id)
    check('just the one arrived', target.assessments.count() == 1,
          target.assessments.count())

    viva = source.assessments.get(name='Zz Viva')
    copy(client, target, source, which=viva.id)
    check('a second copy is added, not swapped in',
          target.assessments.count() == 2, target.assessments.count())
    check('and it is placed after the first',
          list(target.assessments.order_by('order')
               .values_list('name', flat=True)) == ['Zz Written', 'Zz Viva'],
          list(target.assessments.order_by('order')
               .values_list('name', flat=True)))


def check_refusals(client, target, source):
    print('\n6. what it refuses')
    before = target.assessments.count()

    copy(client, target, target)
    check('copying a project into itself does nothing',
          target.assessments.count() == before, target.assessments.count())

    client.post(f'{PA}?project={target.id}',
                {'action': 'clone_assessment', 'source_project': '',
                 'source_assessment': 'all'}, follow=True)
    check('no source chosen does nothing',
          target.assessments.count() == before, target.assessments.count())

    empty = Project.objects.create(title='Zz Empty Project', grade='7',
                                   status='Active')
    copy(client, target, empty)
    check('a source with no assessments does nothing',
          target.assessments.count() == before, target.assessments.count())


# ---------------------------------------------------------------------- run

def run():
    print('=' * 60)
    print('Copy an assessment from another project')
    print('=' * 60)

    try:
        with transaction.atomic():
            source, target, source_comps, target_comps, boss = build()
            client = sign_in(boss)
            check_form(client, target, source)
            first = check_copy_all(client, target, source, target_comps)
            check_mapping_by_name(first, target_comps)
            check_warning_said_so(client, target, source)
            check_one_at_a_time(client, target, source)
            check_refusals(client, target, source)
            raise Rollback
    except Rollback:
        pass

    print('\nNothing survives')
    left = (Project.objects.filter(title__startswith='Zz ').count()
            + Framework.objects.filter(name__startswith='ZZ ').count()
            + Competency.objects.filter(name__startswith='Zz ').count()
            + U.objects.filter(username__startswith='zz.clone.').count())
    check('no row this suite created survived', left == 0, left)

    print(f'\n{"=" * 60}\nPASS {len(PASS)}   FAIL {len(FAIL)}')
    for f in FAIL:
        print(f'  FAILED: {f.strip()}')


if __name__ == '__main__':
    run()
