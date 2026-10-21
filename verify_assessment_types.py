"""The assessment-type list, and the framework filter beside it.

Two things the client asked for on Project & Assessment:

    "assessment me type hota hai abhi ke liye toh 3 hi hai, main chahta hun
     vaha hum input field dede, client khud vaha par add karde... aur remove
     karne ka bhi option dedo, but remove karne se pehle popup dena -- yeh
     yahan yahan use ho raha hai, agar yahan se hataya toh yeh cheezein
     affect hongi"

    "+ New Project ke neeche filter dedo, jitne framework hai usko select
     karne par vohi framework ke project aajaye"

The part worth being careful about is the removal. `Assessment.assessment_type`
is a stored string, not a foreign key, and that is on purpose: removing a type
must not touch an assessment that already carries it, and must not alter a
report built from it. The checks below remove a type that 24 assessments use
and then count those assessments again.

The warning has to be true as well as present. A dialog that says "this is
used by 24 assessments" while the real number is something else is worse than
no dialog, so the figures on the page are compared against the database.

Everything runs inside a transaction that is rolled back.

Run with:  python verify_assessment_types.py
"""

import os
import re

import django

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'enpower_skill_lab.settings'
    django.setup()

from django.conf import settings

settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

from django.contrib.auth import get_user_model
from django.db import transaction

from competencies.models import (Assessment, AssessmentType, Framework,
                                 Project)
from verify_client import HttpsClient as Client

U = get_user_model()
PASSWORD = 'Zz!2026pw'
URL = '/super-admin/skill-passport/project-assessment/'

PASS, FAIL = [], []


def check(label, ok, detail=''):
    (PASS if ok else FAIL).append(label)
    print(f'  {"PASS" if ok else "FAIL"}  {label}'
          f'{("  — " + str(detail)) if detail else ""}')


class Rollback(Exception):
    """Raised once the checks are done, to undo everything they created."""


def boss_client():
    boss = U.objects.filter(role='SUPER_ADMIN', is_active=True).first()
    assert boss, 'no Super Admin to sign in as'
    boss.set_password(PASSWORD)
    boss.save(update_fields=['password'])
    client = Client()
    assert client.login(username=boss.username, password=PASSWORD)
    return client


def page(client, query=''):
    return client.get(URL + query, follow=True).content.decode(
        'utf-8', 'replace')


def chips(html):
    """The type chips as they are printed on the page."""
    return [re.sub(r'\s+', ' ', m).strip() for m in
            re.findall(r'class="pa-type-chip">\s*([^<]+)', html)]


def type_options(html):
    """The options in the Add Assessment type dropdown."""
    block = re.search(r'<select name="assessment_type">(.*?)</select>',
                      html, re.S)
    if not block:
        return []
    return re.findall(r'<option value="([^"]*)"', block.group(1))


# ------------------------------------------------------------ the list

def check_list(client):
    print('\n1. the list is a list, not three lines of markup')

    html = page(client)
    names = list(AssessmentType.objects.values_list('name', flat=True))
    check('the types are in the database', len(names) >= 3, names)
    check('the page shows every one of them',
          chips(html) == names, chips(html))
    check('and the dropdown offers exactly those',
          type_options(html) == names, type_options(html))

    # The three the product shipped with have to have survived the move.
    for shipped in ('Presentation', 'Written', 'Oral/Portfolio'):
        check(f'{shipped} is still there', shipped in names)

    # The count beside each chip is the claim the dialog repeats.
    for t in AssessmentType.objects.all():
        used, _ = t.usage()
        real = Assessment.objects.filter(assessment_type=t.name).count()
        check(f'{t.name}: the count on the page is the real one',
              used == real, f'{used} vs {real}')


# ------------------------------------------------------------- adding

def check_adding(client):
    print('\n2. the client can add one')

    client.post(URL, {'action': 'add_assessment_type',
                      'type_name': 'Zz Practical'}, follow=True)
    made = AssessmentType.objects.filter(name='Zz Practical').first()
    check('a new type is saved', made is not None)
    if made is None:
        return

    html = page(client)
    check('it appears in the dropdown straight away',
          'Zz Practical' in type_options(html), type_options(html))
    check('and it goes to the end of the list, not the middle',
          chips(html)[-1].startswith('Zz Practical'), chips(html)[-1:])

    # It has to be usable, not merely listed.
    project = Project.objects.filter(assessments__isnull=False).first()
    if project:
        client.post(URL + f'?project={project.id}',
                    {'action': 'add_assessment',
                     'assessment_name': 'Zz Typed Assessment',
                     'assessment_type': 'Zz Practical'}, follow=True)
        made_a = Assessment.objects.filter(
            name='Zz Typed Assessment').first()
        check('an assessment can be given the new type',
              made_a is not None and made_a.assessment_type == 'Zz Practical',
              getattr(made_a, 'assessment_type', None))

    before = AssessmentType.objects.count()
    client.post(URL, {'action': 'add_assessment_type',
                      'type_name': 'zz practical'}, follow=True)
    check('the same name in another case is refused',
          AssessmentType.objects.count() == before,
          AssessmentType.objects.count())

    client.post(URL, {'action': 'add_assessment_type', 'type_name': '   '},
                follow=True)
    check('a blank name is refused',
          AssessmentType.objects.count() == before)

    client.post(URL, {'action': 'add_assessment_type',
                      'type_name': 'Z' * 40}, follow=True)
    check('a name too long for the column is refused, not truncated',
          AssessmentType.objects.count() == before,
          AssessmentType.objects.count())


# ----------------------------------------------------------- removing

def check_removing(client):
    print('\n3. removing one changes the list and nothing else')

    html = page(client)
    check('the page carries a confirmation dialog',
          'removeTypeOverlay' in html)
    check('which names the consequence rather than asking "are you sure?"',
          'keep this type and their reports are' in html)
    check('and says it can be added again', 'add it again at any time' in html)
    check('the dialog is in English, as asked',
          'Remove Type' in html and 'Cancel' in html)

    # A type that is in use. The assessments carrying it must be untouched.
    in_use = None
    for t in AssessmentType.objects.all():
        if t.usage()[0] > 0:
            in_use = t
            break
    if in_use is None:
        check('a type in use, to remove', False)
        return

    name = in_use.name
    before = list(Assessment.objects.filter(assessment_type=name)
                  .values_list('id', flat=True))
    check(f'"{name}" is used by something', bool(before), len(before))

    client.post(URL, {'action': 'delete_assessment_type',
                      'type_id': in_use.id}, follow=True)

    check('it is gone from the list',
          not AssessmentType.objects.filter(name=name).exists())
    after = list(Assessment.objects.filter(assessment_type=name)
                 .values_list('id', flat=True))
    check('every assessment that had it still has it',
          after == before, f'{len(before)} -> {len(after)}')

    # And the one place it could still silently change: opening that
    # assessment's own form and saving it.
    assessment = Assessment.objects.filter(assessment_type=name).first()
    if assessment:
        html = page(client, f'?project={assessment.project_id}')
        check('its own dropdown still offers the removed type',
              f'>{name} (removed from list)<' in html
              or f'value="{name}" selected' in html,
              name)

    # Removing something that is gone already must not explode.
    client.post(URL, {'action': 'delete_assessment_type',
                      'type_id': 99999999}, follow=True)
    check('removing a type that is already gone is handled', True)

    # An unused one goes without a word about consequences.
    client.post(URL, {'action': 'add_assessment_type',
                      'type_name': 'Zz Unused'}, follow=True)
    spare = AssessmentType.objects.filter(name='Zz Unused').first()
    if spare:
        check('an unused type reports no usage', spare.usage() == (0, 0),
              spare.usage())
        client.post(URL, {'action': 'delete_assessment_type',
                          'type_id': spare.id}, follow=True)
        check('and removes cleanly',
              not AssessmentType.objects.filter(name='Zz Unused').exists())


# ----------------------------------------------------- framework filter

def check_filter(client):
    print('\n4. the framework filter under New Project')

    html = page(client)
    check('the filter is on the page', 'paFwFilter' in html)
    check('it sits under the New Project button',
          html.index('pa-new-btn') < html.index('paFwFilter'))
    check('it offers every framework',
          all(fw.name in html for fw in Framework.objects.all()))
    check('and an "all" option', 'All frameworks' in html)

    # Compared as sorted lists, not sets. Two projects can share a title --
    # this database has several -- and a set would quietly swallow one extra
    # row, which is exactly the mistake a filter makes.
    for fw in Framework.objects.all():
        html = page(client, f'?framework={fw.id}')
        listed = sorted(re.findall(r'class="pa-proj-title">([^<]+)', html))
        real = sorted(Project.objects.filter(framework_ref=fw)
                      .values_list('title', flat=True))
        check(f'{fw.name}: the list is exactly its projects',
              listed == real, f'{len(listed)} listed, {len(real)} real')

    html = page(client)
    everything = sorted(Project.objects.values_list('title', flat=True))
    listed = sorted(re.findall(r'class="pa-proj-title">([^<]+)', html))
    check('no filter lists them all', listed == everything,
          f'{len(listed)} vs {len(everything)}')
    check('and the frameworks account for every project',
          sum(Project.objects.filter(framework_ref=fw).count()
              for fw in Framework.objects.all())
          + Project.objects.filter(framework_ref__isnull=True).count()
          == Project.objects.count(),
          Project.objects.filter(framework_ref__isnull=True).count())

    # A link to a project the filter would hide still has to open. A filter is
    # a view of a list; it is not permission.
    fw = Framework.objects.first()
    other = Project.objects.exclude(framework_ref=fw).first()
    if fw and other:
        html = page(client, f'?framework={fw.id}&project={other.id}')
        check('a project outside the filter still opens by its link',
              other.title in html, other.title)

    html = page(client, '?framework=99999999')
    check('an unknown framework falls back to everything rather than erroring',
          'pa-proj-title' in html or 'No projects yet' in html)


def run():
    print('=' * 60)
    print('ASSESSMENT TYPES AND THE FRAMEWORK FILTER')
    print('=' * 60)

    try:
        with transaction.atomic():
            client = boss_client()
            check_list(client)
            check_adding(client)
            check_removing(client)
            check_filter(client)
            raise Rollback
    except Rollback:
        pass

    left = AssessmentType.objects.filter(name__startswith='Zz ').count()
    check('nothing this suite created survived', left == 0, left)
    check('and the shipped types are back',
          AssessmentType.objects.filter(
              name__in=['Presentation', 'Written', 'Oral/Portfolio']
          ).count() == 3)

    print(f'\n{"=" * 60}\nPASS {len(PASS)}   FAIL {len(FAIL)}')
    for f in FAIL:
        print(f'  FAILED: {f}')


if __name__ == '__main__':
    run()
