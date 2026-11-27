"""One project report, built once for whoever is looking at it.

The student, the parent and now the principal all open the same report
through the same partial (`student/_report_body.html`), and that partial
reads a long list of context keys. Each role used to assemble them itself,
which meant three copies of the same sixty lines and three chances for one of
them to drift -- a label refreshed in one place and not another shows the
same child two different reports.

The only thing that genuinely differs between the roles is the footer
navigation, so that is what the caller passes in.
"""

from django.shortcuts import get_object_or_404


def build_project_report_context(student, project_id, nav_back_url='',
                                 nav_back_label='', nav_next_url=''):
    """Everything `student/_report_body.html` needs for one project report."""
    from competencies.engine import (get_per_assessment_breakdown,
                                     group_by_sub_pillar,
                                     refresh_competency_labels)
    from competencies.grading import grade_for
    from competencies.models import (Profile, ProjectReport,
                                     StudentAssessmentFeedback,
                                     StudentProjectFeedback)

    report = get_object_or_404(ProjectReport, student=student,
                               project_id=project_id)

    all_scores = report.all_competency_scores or []
    # Every stored list that renders a competency name, so a rename shows the
    # same way here as in the live per-assessment breakdown below.
    refresh_competency_labels(all_scores, report.skills_to_work_on,
                              report.top_5_competencies,
                              report.common_strengths)

    def label(score):
        if score >= 8:
            return 'very_strong'
        if score >= 6:
            return 'strong'
        if score >= 4:
            return 'emerging'
        return 'skill_to_work_on'

    values = [c['score'] for c in all_scores if c.get('score') is not None]

    profiles = report.top_3_profiles or []
    prof_tags = {}
    prof_ids = [p['profile_id'] for p in profiles if p.get('profile_id')]
    if prof_ids:
        for pr in (Profile.objects.filter(id__in=prof_ids)
                   .prefetch_related('primary_competencies')):
            prof_tags[pr.id] = [c.name for c in pr.primary_competencies.all()[:3]]
    for p in profiles:
        p['match_percent'] = int(round((p.get('score') or 0) * 10))
        p['tags'] = prof_tags.get(p.get('profile_id'), [])

    overall = round(sum(values) / len(values), 1) if values else 0

    return {
        'student': student,          # the shared passport partials read this
        'child': student,            # and the parent's own template reads this
        'report': report,
        'very_strong': [c for c in all_scores if label(c['score']) == 'very_strong'],
        'strong':      [c for c in all_scores if label(c['score']) == 'strong'],
        'emerging':    [c for c in all_scores if label(c['score']) == 'emerging'],
        'feedbacks': StudentAssessmentFeedback.objects.filter(
            student=student, assessment__project_id=project_id
        ).select_related('entered_by').order_by('-updated_at'),
        # The coach's overall note on the project.
        'project_feedback': StudentProjectFeedback.objects.filter(
            student=student, project_id=project_id
        ).select_related('entered_by').first(),
        'overall_score': overall,
        'overall_grade': grade_for(overall) if values else None,
        'best_match': profiles[0]['match_percent'] if profiles else 0,
        'assessment_breakdown': get_per_assessment_breakdown(student,
                                                             report.project),
        'sub_pillar_groups': group_by_sub_pillar(all_scores),
        # Footer nav. The shared partial defaults to the student's own URLs,
        # which nobody else can open -- a parent following them was bounced to
        # /login.
        'nav_back_url':   nav_back_url,
        'nav_back_label': nav_back_label,
        'nav_next_url':   nav_next_url,
    }


def project_report_rows(student):
    """A student's generated project reports, one summary row each."""
    from competencies.models import ProjectReport

    rows = []
    for r in (ProjectReport.objects.filter(student=student)
              .select_related('project')
              .order_by('project__sequence_number', 'project__title')):
        values = [c['score'] for c in (r.all_competency_scores or [])
                  if c.get('score') is not None]
        rows.append({
            'project_id': r.project_id,
            'title': r.project.title,
            'category': r.project.project_type,
            'average': round(sum(values) / len(values), 1) if values else None,
            'competency_count': len(values),
            'generated_at': r.generated_at,
        })
    return rows
