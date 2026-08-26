"""
Seed schools onto frameworks, then projects / assessments / scores / feedback.

Deck references:
  slide 8   Project form: grade, title, project form, 3 projects + plug-ins per grade
  slide 8   Assessment: up to 6 per project, up to 8 competencies each, Type,
            Output Descriptor, Additional Instructions, placement after challenge #
  slide 11  Rubric grid — 4 bands per competency
  slide 16  Profiling reset per project; disabled for CSL+
  slide 24  Plug-In merges into the next project (average per competency)

Scores are seeded deliberately, not randomly: every student is given a "target
profile", whose primary competencies score 9-10 and secondary 7-8, while
everything else scores 3-6. That makes the output checkable — the student's top
career match should come out as their target profile. Any other result means the
profiling engine is wrong.

Run with:  python seed_projects.py
"""

import os
import django

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'enpower_skill_lab.settings'
    django.setup()

from competencies.models import (
    Framework, Competency, Profile, Project, Assessment, AssessmentCompetency,
    ScoreEntry, RubricCriterion, StudentAssessmentFeedback,
    StudentProjectFeedback, ProjectReport,
)
from schools.models import School
from student.models import Student

# ── School -> framework ─────────────────────────────────────────────────
# Matched on a substring of school_name so the same script works on any
# environment. Unlisted schools default to FSL.
SCHOOL_FRAMEWORK_RULES = [
    ('Sacred',               'FSL'),
    ('National',             'CSL+'),
    ('Gurunanak',            'CSL Foundation'),
    ('Mumbai High',          'CSL+'),
    ('International Senior', 'CSL Foundation'),
]
DEFAULT_FRAMEWORK = 'FSL'

# ── Project shapes per grade (slide 8: "3 project + plug-ins") ──────────
PROJECT_SHAPES = [
    # (title suffix,        project_type,           sequence_number, has_plugin)
    ('Bio Conservation',    'Life Form',            1, True),
    ('Wearable Tech',       'Machines & Materials', 2, False),
    ('Community Kitchen',   'Final Project',        3, False),
]

ASSESSMENT_SHAPES = [
    # (name,                  type,             after challenge #)
    ('Assessment 1',          'Presentation',    2),
    ('Assessment 2',          'Written',         5),
    ('Assessment 3',          'Oral/Portfolio',  8),
    ('Assessment 4',          'Presentation',   11),
]
MAX_COMPETENCIES_PER_ASSESSMENT = 8      # slide 8

BANDS = [
    'Attempts the task with prompting; key steps are missing or incorrect.',
    'Completes most of the task; reasoning is partly explained.',
    'Completes the task accurately and explains the reasoning clearly.',
    'Completes the task independently and extends it beyond what was asked.',
]

PROJECT_FEEDBACK = (
    'Worked steadily through the project and responded well to feedback between '
    'assessments. Strongest when explaining reasoning out loud; next step is to '
    'show the same clarity in written work.'
)
ASSESSMENT_FEEDBACK = (
    'Clear effort on this output. Reasoning was mostly sound — tighten the '
    'evidence you use to back each claim.'
)


def assign_school_frameworks(keep_existing=False):
    """Point schools at a framework.

    `keep_existing=True` only fills in schools that have none. Framework choice
    is real configuration, not seed data — on an environment where someone has
    already set it deliberately, overwriting it by name-matching would quietly
    move schools between programmes.
    """
    frameworks = {f.name: f for f in Framework.objects.all()}
    print(f'Assigning schools to frameworks{" (keeping existing)" if keep_existing else ""}')
    changed = kept = 0
    for school in School.objects.all():
        if keep_existing and school.framework_ref_id:
            kept += 1
            continue
        target = DEFAULT_FRAMEWORK
        for needle, fw_name in SCHOOL_FRAMEWORK_RULES:
            if needle.lower() in school.school_name.lower():
                target = fw_name
                break
        fw = frameworks[target]
        school.framework_ref = fw
        school.framework_type = fw.name
        school.save(update_fields=['framework_ref', 'framework_type'])
        changed += 1
        print(f'  {school.school_name[:38]:40} -> {fw.name}')
    if kept:
        print(f'  kept {kept} school(s) on their existing framework, set {changed}')


def attach_orphan_students():
    """A student with no school has no framework, so no project matches them."""
    home = School.objects.filter(school_name__icontains='Sacred').first() \
        or School.objects.first()
    orphans = Student.objects.filter(school__isnull=True)
    for s in orphans:
        s.school = home
        s.save(update_fields=['school'])
        print(f'  attached {s.first_name} {s.last_name or ""} -> {home.school_name}')


def framework_grades():
    """{framework_name: sorted grades that actually have students}"""
    out = {}
    for s in Student.objects.select_related('school__framework_ref'):
        fw = getattr(getattr(s.school, 'framework_ref', None), 'name', None)
        if not fw or not s.student_class:
            continue
        out.setdefault(fw, set()).add(str(s.student_class).strip())
    return {k: sorted(v, key=lambda g: int(g) if g.isdigit() else 99)
            for k, v in out.items()}


def competency_pool(framework):
    """Ordered competencies for a framework, KB last so non-KB fills first."""
    comps = list(
        Competency.objects
        .filter(sub_pillar__pillar__framework_ref=framework, status='Active')
        .select_related('sub_pillar__pillar')
    )
    comps.sort(key=lambda c: (c.sub_pillar.pillar.is_kb, c.sub_pillar.sp_number, c.code))
    return comps


def profile_triplet(index, profiles):
    """Three profiles whose competencies a project will be built around."""
    if not profiles:
        return []
    start = (index * 3) % len(profiles)
    return [profiles[(start + i) % len(profiles)] for i in range(3)]


def build_project(framework, grade, shape, shape_index, profiles, fallback_pool):
    """Create one project (+ its plug-in) with assessments and competencies.

    Returns (project, [target profiles], plugin_or_None).
    """
    suffix, ptype, seq, has_plugin = shape
    title = f'{suffix} — Grade {grade}'

    project = Project.objects.create(
        title=title, project_type=ptype, grade=str(grade),
        framework_ref=framework, framework=framework.name,
        status='Active', sequence_number=seq,
    )

    trio = profile_triplet(shape_index, profiles)
    if trio:
        # Cover every mapped competency of the three profiles, so each student
        # on this project can have one of them as their target.
        comps, seen = [], set()
        for p in trio:
            for c in list(p.primary_competencies.all()) + list(p.secondary_competencies.all()):
                if c.id not in seen:
                    seen.add(c.id)
                    comps.append(c)
    else:
        # CSL frameworks have no profile mapping — take a rolling slice of the
        # framework's own competencies, KB included.
        size = 12
        start = (shape_index * size) % max(1, len(fallback_pool))
        comps = [fallback_pool[(start + i) % len(fallback_pool)] for i in range(min(size, len(fallback_pool)))]

    _attach_assessments(project, comps)

    plugin = None
    if has_plugin:
        plugin = Project.objects.create(
            title=f'{suffix} Plug-In — Grade {grade}', project_type='Plug In',
            grade=str(grade), framework_ref=framework, framework=framework.name,
            status='Active', sequence_number=None, linked_project=project,
        )
        # Slide 24: the plug-in re-scores a slice of the parent's competencies,
        # which the engine then averages with the parent's own scores.
        _attach_assessments(plugin, comps[:4], names=['Plug-In Output'])

    return project, trio, plugin


def _attach_assessments(project, comps, names=None):
    """Spread competencies over assessments, <=8 each.

    One competency is deliberately repeated in the next assessment so the
    "repeated competencies to be aggregated" rule (slide 14/21) is exercised.
    """
    shapes = ASSESSMENT_SHAPES
    if names:
        shapes = [(names[0], 'Presentation', 1)]

    per = max(1, min(MAX_COMPETENCIES_PER_ASSESSMENT,
                     -(-len(comps) // len(shapes))))
    chunks = [comps[i:i + per] for i in range(0, len(comps), per)] or [[]]

    for order, (name, atype, after) in enumerate(shapes, start=1):
        if order > len(chunks):
            break
        chunk = list(chunks[order - 1])
        # repeat the previous assessment's first competency
        if order > 1 and chunks[order - 2]:
            carry = chunks[order - 2][0]
            if carry not in chunk and len(chunk) < MAX_COMPETENCIES_PER_ASSESSMENT:
                chunk.append(carry)

        assessment = Assessment.objects.create(
            project=project, name=name, assessment_type=atype,
            placement_after_challenge=after, order=order,
            output_descriptor=f'Student output for {name.lower()} — evidence of applying '
                              f'the mapped competencies to the project brief.',
            additional_instructions='Score each competency 1-10 against the rubric. '
                                    'Leave blank only if the student was absent.',
        )
        for i, comp in enumerate(chunk):
            AssessmentCompetency.objects.create(
                assessment=assessment, competency=comp, order=i + 1,
                comp_type='group' if i % 3 == 2 else 'individual',
            )
            RubricCriterion.objects.create(
                assessment=assessment, competency=comp,
                band1_text=BANDS[0], band2_text=BANDS[1],
                band3_text=BANDS[2], band4_text=BANDS[3],
            )


def score_students(project, trio, plugin, teacher):
    """Score every student whose grade matches, biased toward a target profile."""
    students = list(
        Student.objects.filter(
            student_class=str(project.grade),
            school__framework_ref=project.framework_ref,
        )
    )
    if not students:
        return 0, []

    projects = [project] + ([plugin] if plugin else [])
    mappings = list(
        AssessmentCompetency.objects
        .filter(assessment__project__in=projects)
        .select_related('competency')
    )

    made = 0
    targets = []
    for student in students:
        target = trio[student.id % len(trio)] if trio else None
        targets.append((student, target))

        primary_ids   = {c.id for c in target.primary_competencies.all()}   if target else set()
        secondary_ids = {c.id for c in target.secondary_competencies.all()} if target else set()

        for m in mappings:
            cid = m.competency_id
            if cid in primary_ids:
                score = 9 + ((student.id + cid) % 2)          # 9-10
            elif cid in secondary_ids:
                score = 7 + ((student.id + cid) % 2)          # 7-8
            else:
                score = 3 + ((student.id + cid) % 4)          # 3-6
            ScoreEntry.objects.update_or_create(
                student=student, assessment_competency=m,
                defaults={'score': score, 'entered_by': teacher},
            )
            made += 1

        for p in projects:
            StudentProjectFeedback.objects.update_or_create(
                student=student, project=p,
                defaults={'feedback': PROJECT_FEEDBACK, 'entered_by': teacher},
            )
            for a in p.assessments.all():
                StudentAssessmentFeedback.objects.update_or_create(
                    student=student, assessment=a,
                    defaults={'feedback': ASSESSMENT_FEEDBACK, 'entered_by': teacher},
                )

    return made, targets


def run(keep_school_frameworks=False):
    from accounts.models import User

    assign_school_frameworks(keep_existing=keep_school_frameworks)
    print('\nAttaching students without a school')
    attach_orphan_students()

    print('\nClearing existing projects')
    n = Project.objects.count()
    Project.objects.all().delete()      # cascades assessments, mappings, scores, reports
    ProjectReport.objects.all().delete()
    print(f'  removed {n} projects and their reports')

    teacher = User.objects.filter(role='TEACHER').first()
    profiles = list(Profile.objects.prefetch_related(
        'primary_competencies', 'secondary_competencies'))
    frameworks = {f.name: f for f in Framework.objects.all()}
    grades_by_fw = framework_grades()

    print('\nGrades with students, per framework')
    for fw_name, grades in grades_by_fw.items():
        print(f'  {fw_name:16} {grades}')

    all_targets = []
    print('\nSeeding projects')
    for fw_name, grades in grades_by_fw.items():
        fw = frameworks[fw_name]
        pool = competency_pool(fw)
        if not pool:
            print(f'  {fw_name}: no competencies, skipped')
            continue
        # Profiling only runs for FSL, so only FSL projects are built around
        # profiles; CSL projects draw from their own competency pool.
        fw_profiles = profiles if fw.is_fixed else []

        for grade in grades:
            for idx, shape in enumerate(PROJECT_SHAPES):
                project, trio, plugin = build_project(
                    fw, grade, shape, idx, fw_profiles, pool)
                made, targets = score_students(project, trio, plugin, teacher)
                all_targets.extend(targets)
                print(f'  [{fw_name:14}] g{grade:<3} {project.title[:34]:36} '
                      f'ass={project.assessments.count()} '
                      f'plugin={"yes" if plugin else "no ":3} scores={made}')

    print('\nVerification')
    print(f'  projects={Project.objects.count()}  '
          f'assessments={Assessment.objects.count()}  '
          f'mappings={AssessmentCompetency.objects.count()}  '
          f'scores={ScoreEntry.objects.count()}  '
          f'rubric_rows={RubricCriterion.objects.count()}')

    print('\n  target profile per student (top career match should match this)')
    seen = set()
    for student, target in all_targets:
        key = (student.id, target.id if target else None)
        if key in seen:
            continue
        seen.add(key)
        fw = student.school.framework_ref.name if student.school and student.school.framework_ref else '-'
        print(f'    {student.first_name} {student.last_name or "":12} g{student.student_class}{student.division} '
              f'[{fw:14}] target={target.name if target else "(no profiling)"}')


if __name__ == '__main__':
    import sys
    run(keep_school_frameworks='--keep-school-frameworks' in sys.argv)
