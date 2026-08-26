"""
Score Viewing for the Thinking Coach — spec slide 14.

The slide lays out four views over the same scores:

    Student Level                 Class Level
      - Project Wise                - Percentile Competency
      - Agg Competency Wise         - Project Level Aggregate Comparative

plus three details it calls out explicitly:
  * "Repeated competencies to be aggregated" — the same competency assessed in
    more than one assessment counts once, averaged.
  * "Pending [Add score]" — unscored competencies stay visible instead of being
    dropped, with a link straight to score entry.
  * "Generate Profile Report" — kick off report generation from here.

Kept out of teacher/views.py, which is already long.
"""

from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render

from student.models import Student
from .views import is_teacher, _teacher_school

# (key, group, label) — group drives the two column headings on slide 14
SCORE_VIEWS = [
    ('project_wise',   'Student Level', 'Project Wise'),
    ('agg_competency', 'Student Level', 'Agg Competency Wise'),
    ('percentile',     'Class Level',   'Percentile Competency'),
    ('comparative',    'Class Level',   'Project Level Aggregate Comparative'),
]
VIEW_KEYS = {k for k, _, _ in SCORE_VIEWS}
VIEW_LABELS = {k: lbl for k, _, lbl in SCORE_VIEWS}
STUDENT_LEVEL_VIEWS = {'project_wise', 'agg_competency'}


def _band(score):
    """Score bands from spec slides 22/23."""
    if score is None:
        return ''
    if score >= 8:
        return 'Very Strong'
    if score >= 6:
        return 'Strong'
    if score >= 4:
        return 'Emerging'
    return 'Skill to work on'


def _percentile_of(value, population):
    """Percentage of the class scoring at or below `value`."""
    if value is None or not population:
        return None
    return int(round(sum(1 for v in population if v <= value) / len(population) * 100))


def _quantile(sorted_vals, q):
    """Linear-interpolated quantile. `sorted_vals` must be sorted ascending."""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 1)
    pos = (len(sorted_vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return round(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo), 1)


def _scored_projects(school):
    """Projects this school's students can be scored against.

    Plug-Ins are excluded — their scores merge into the parent project
    (spec slide 24), so they are not a separate row anywhere.
    """
    from competencies.models import Project

    qs = Project.objects.exclude(project_type='Plug In')
    framework = getattr(school, 'framework_ref', None)
    if framework:
        qs = qs.filter(framework_ref=framework)
    return qs.order_by('grade', 'sequence_number', 'title')


def _mappings_for(projects):
    from competencies.models import AssessmentCompetency

    return (AssessmentCompetency.objects
            .filter(assessment__project__in=projects)
            .select_related('competency', 'competency__sub_pillar__pillar',
                            'assessment', 'assessment__project'))


def _student_project_rows(student, projects):
    """'Project Wise' — one block per project, its competencies inside."""
    from competencies.models import ScoreEntry

    mappings = list(_mappings_for(projects))
    scores = {se.assessment_competency_id: se.score
              for se in ScoreEntry.objects.filter(
                  student=student, assessment_competency__in=mappings)}

    by_project = defaultdict(lambda: defaultdict(list))
    assessments = defaultdict(lambda: defaultdict(list))
    comp_of = {}
    for m in mappings:
        by_project[m.assessment.project_id][m.competency_id].append(scores.get(m.id))
        assessments[m.assessment.project_id][m.competency_id].append(m.assessment.name)
        comp_of[m.competency_id] = m.competency

    rows = []
    for project in projects:
        comps = by_project.get(project.id)
        if not comps:
            continue
        comp_rows, project_vals = [], []
        for cid, vals in comps.items():
            got = [v for v in vals if v is not None]
            avg = round(sum(got) / len(got), 1) if got else None
            if avg is not None:
                project_vals.append(avg)
            comp_rows.append({
                'competency':  comp_of[cid],
                'is_kb':       comp_of[cid].sub_pillar.pillar.is_kb,
                'score':       avg,
                'band':        _band(avg),
                'aggregated':  len(got) > 1,
                'assessments': assessments[project.id][cid],
                'pending':     avg is None,
            })
        comp_rows.sort(key=lambda r: (r['score'] is None, -(r['score'] or 0)))
        rows.append({
            'project':      project,
            'competencies': comp_rows,
            'average':      round(sum(project_vals) / len(project_vals), 1) if project_vals else None,
            'band':         _band(sum(project_vals) / len(project_vals) if project_vals else None),
            'scored':       len(project_vals),
            'total':        len(comp_rows),
        })
    return rows


def _student_competency_rows(student, projects):
    """'Agg Competency Wise' — one row per competency across every project.

    This is where slide 14's "repeated competencies to be aggregated" matters
    most: a competency taught in two projects shows a single averaged figure,
    with the contributing projects listed.
    """
    from competencies.models import ScoreEntry

    mappings = list(_mappings_for(projects))
    scores = {se.assessment_competency_id: se.score
              for se in ScoreEntry.objects.filter(
                  student=student, assessment_competency__in=mappings)}

    per_comp = defaultdict(list)
    projects_of = defaultdict(set)
    comp_of = {}
    for m in mappings:
        value = scores.get(m.id)
        per_comp[m.competency_id].append(value)
        comp_of[m.competency_id] = m.competency
        if value is not None:
            projects_of[m.competency_id].add(m.assessment.project.title)

    rows = []
    for cid, vals in per_comp.items():
        got = [v for v in vals if v is not None]
        avg = round(sum(got) / len(got), 1) if got else None
        competency = comp_of[cid]
        rows.append({
            'competency':     competency,
            'sub_pillar':     str(competency.sub_pillar),
            'is_kb':          competency.sub_pillar.pillar.is_kb,
            'score':          avg,
            'band':           _band(avg),
            'times_assessed': len(got),
            'aggregated':     len(got) > 1,
            'projects':       sorted(projects_of[cid]),
            'pending':        avg is None,
        })
    rows.sort(key=lambda r: (r['score'] is None, -(r['score'] or 0)))
    return rows


def _percentile_rows(students, projects, focus_student=None):
    """'Percentile Competency' — how the class is spread on each competency.

    Each student contributes one aggregated figure per competency, so a
    competency assessed twice cannot weight that student twice in the spread.
    When a student is selected, their own percentile is shown alongside.
    """
    from competencies.models import ScoreEntry

    mappings = list(_mappings_for(projects))
    entries = (ScoreEntry.objects
               .filter(student__in=students, assessment_competency__in=mappings,
                       score__isnull=False)
               .select_related('assessment_competency__competency'))

    per_comp = defaultdict(lambda: defaultdict(list))
    comp_of = {}
    for se in entries:
        competency = se.assessment_competency.competency
        per_comp[competency.id][se.student_id].append(se.score)
        comp_of[competency.id] = competency

    rows = []
    for cid, by_student in per_comp.items():
        averages = {sid: sum(v) / len(v) for sid, v in by_student.items()}
        vals = sorted(averages.values())
        focus = averages.get(focus_student.id) if focus_student else None
        p25, median, p75 = (_quantile(vals, 0.25), _quantile(vals, 0.50),
                            _quantile(vals, 0.75))
        # Bar geometry as percentages of the 0-10 scale. Django templates can't
        # subtract, so the p25..p75 box is measured here.
        rows.append({
            'competency':       comp_of[cid],
            'is_kb':            comp_of[cid].sub_pillar.pillar.is_kb,
            'class_avg':        round(sum(vals) / len(vals), 1),
            'p25':              p25,
            'median':           median,
            'p75':              p75,
            'box_left':         round(p25 * 10, 1),
            'box_width':        max(round((p75 - p25) * 10, 1), 1.5),
            'median_left':      round(median * 10, 1),
            'focus_left':       round(focus * 10, 1) if focus is not None else None,
            'lowest':           round(vals[0], 1),
            'highest':          round(vals[-1], 1),
            'students_scored':  len(vals),
            'focus_score':      round(focus, 1) if focus is not None else None,
            'focus_percentile': _percentile_of(focus, vals),
            'focus_band':       _band(focus),
        })
    rows.sort(key=lambda r: -r['class_avg'])
    return rows


def _comparative_rows(students, projects):
    """'Project Level Aggregate Comparative' — projects side by side.

    Each student contributes one average per project; the row reports the class
    spread plus how much of the class has actually been scored, so a flattering
    average built on three students is not mistaken for a class result.
    """
    from competencies.models import ScoreEntry

    mappings = list(_mappings_for(projects))
    project_of_mapping = {m.id: m.assessment.project_id for m in mappings}
    comps_in_project = defaultdict(set)
    for m in mappings:
        comps_in_project[m.assessment.project_id].add(m.competency_id)

    per_project = defaultdict(lambda: defaultdict(list))
    for se in ScoreEntry.objects.filter(student__in=students,
                                        assessment_competency__in=mappings,
                                        score__isnull=False):
        pid = project_of_mapping.get(se.assessment_competency_id)
        per_project[pid][se.student_id].append(se.score)

    total_students = len(students)
    rows = []
    for project in projects:
        if not comps_in_project.get(project.id):
            continue
        averages = sorted(sum(v) / len(v) for v in per_project.get(project.id, {}).values())
        class_avg = round(sum(averages) / len(averages), 1) if averages else None
        rows.append({
            'project':          project,
            'class_avg':        class_avg,
            'band':             _band(class_avg),
            'lowest':           round(averages[0], 1) if averages else None,
            'highest':          round(averages[-1], 1) if averages else None,
            'median':           _quantile(averages, 0.50),
            'students_scored':  len(averages),
            'students_total':   total_students,
            'coverage':         int(round(len(averages) / total_students * 100)) if total_students else 0,
            'competencies':     len(comps_in_project[project.id]),
        })

    scored = [r for r in rows if r['class_avg'] is not None]
    best = max(scored, key=lambda r: r['class_avg'])['project'].id if scored else None
    worst = min(scored, key=lambda r: r['class_avg'])['project'].id if scored else None
    for r in rows:
        r['is_best'] = len(scored) > 1 and r['project'].id == best
        r['is_worst'] = len(scored) > 1 and r['project'].id == worst
    return rows


@login_required
@user_passes_test(is_teacher)
def score_viewing(request):
    """Slide 14 Score Viewing — four views over one set of scores."""
    from competencies.models import ProjectReport

    school = _teacher_school(request.user)
    if not school:
        messages.error(request, 'No school assigned to your profile.')
        return redirect('teacher:teacher_dashboard')

    view = request.GET.get('view', 'project_wise')
    if view not in VIEW_KEYS:
        view = 'project_wise'

    students = Student.objects.filter(school=school, is_active=True).order_by(
        'student_class', 'division', 'first_name')

    grades = sorted({str(s.student_class) for s in students if s.student_class},
                    key=lambda g: int(g) if g.isdigit() else 99)
    grade = request.GET.get('grade', '').strip() or (grades[0] if grades else '')

    grade_students = [s for s in students if str(s.student_class) == grade]
    projects = list(_scored_projects(school).filter(grade=grade))

    requested_student = request.GET.get('student', '').strip()
    student = next((s for s in grade_students if str(s.id) == requested_student), None)
    if student is None and grade_students:
        student = grade_students[0]

    requested_project = request.GET.get('project', '').strip()
    project = next((p for p in projects if str(p.id) == requested_project), None)
    # The class-level comparative view is about comparing projects, so it always
    # spans all of them regardless of the project filter.
    shown = [project] if project else projects

    # Pre-grouped for the template: {% regroup %} can't key off a tuple index.
    view_groups = []
    for key, group_label, label in SCORE_VIEWS:
        if not view_groups or view_groups[-1]['label'] != group_label:
            view_groups.append({'label': group_label, 'items': []})
        view_groups[-1]['items'].append({'key': key, 'label': label})

    context = {
        'view_groups': view_groups,
        'active_view': view,
        'view_label': VIEW_LABELS.get(view, ''),
        'is_student_level': view in STUDENT_LEVEL_VIEWS,
        'school': school,
        'grades': grades, 'grade': grade,
        'students': grade_students, 'student': student,
        'projects': projects, 'project': project,
    }

    if view == 'project_wise' and student:
        context['project_rows'] = _student_project_rows(student, shown)
    elif view == 'agg_competency' and student:
        context['competency_rows'] = _student_competency_rows(student, shown)
    elif view == 'percentile':
        context['percentile_rows'] = _percentile_rows(grade_students, shown, student)
    elif view == 'comparative':
        context['comparative_rows'] = _comparative_rows(grade_students, projects)

    if student:
        context['student_reports'] = (ProjectReport.objects
                                      .filter(student=student, project__in=projects)
                                      .select_related('project')
                                      .order_by('project__sequence_number'))
    return render(request, 'teacher/score-viewing.html', context)
