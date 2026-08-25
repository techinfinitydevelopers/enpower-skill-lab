"""
neoRiSE Skill Passport — Calculation Engine
============================================
Implements the full scoring + profiling logic as documented in SKILL_PASSPORT_LOGIC.md
"""

from collections import defaultdict
from .models import (
    Project, Assessment, AssessmentCompetency,
    ScoreEntry, Profile, ProjectReport
)

# --- Constants ---
SECONDARY_COMPETENCY_WEIGHT = 0.10
MIN_PRIMARY_FOR_UNLOCK      = 2
TOP_PROFILES_COUNT          = 3
TOP_COMPETENCIES_COUNT      = 5


def attach_competency_descriptions(*score_lists):
    """Fill in `competency_desc` on competency-score dicts, in place.

    Reports generated before descriptions were stored have no `competency_desc`
    key, so student-facing pages would silently show codes only. Looking the
    descriptions up at render time means old reports display correctly without
    having to be regenerated. One query covers every list passed in.
    """
    from .models import Competency

    rows = [row for lst in score_lists if lst for row in lst]
    missing = {row.get('competency_id') for row in rows if not row.get('competency_desc')}
    missing.discard(None)
    if not missing:
        return

    descriptions = dict(
        Competency.objects.filter(id__in=missing).values_list('id', 'description')
    )
    for row in rows:
        if not row.get('competency_desc'):
            row['competency_desc'] = descriptions.get(row.get('competency_id'), '')


# ─────────────────────────────────────────────
# STEP 1: Collect final competency scores
# ─────────────────────────────────────────────

def get_competency_scores_for_project(student, project, include_kb=False):
    """
    Returns a dict: { competency_id: final_score }

    If project has a linked Plug-In:
      - Calculate plugin scores separately
      - Calculate project scores separately
      - Merge: if same competency in both → average; else use whichever has it
    If no Plug-In:
      - Just average scores per competency across all assessments in project

    By default, KB (Kaushal Bodh) competencies are EXCLUDED from the result.
    Pass include_kb=True to get KB scores (for KB-only reports).
    """
    project_scores  = _scores_for_single_project(student, project)
    plugin          = project.plugins.filter(status='Active').first()

    if plugin:
        plugin_scores = _scores_for_single_project(student, plugin)
        merged = _merge_scores(project_scores, plugin_scores)
    else:
        merged = project_scores

    if not include_kb:
        merged = _exclude_kb_scores(merged)

    return merged


def get_per_assessment_breakdown(student, project, include_kb=False):
    """Per-assessment score breakdown for one student on one project.

    The project report otherwise only shows the aggregated final score per
    competency, which hides whether the student improved across the project's
    assessments. This returns one entry per assessment, in assessment order,
    so the report can show progress over time.

    Returns a list of dicts:
        [{'assessment_id', 'assessment_name', 'assessment_type', 'order',
          'average', 'scored_count', 'total_count',
          'competencies': [{'competency_id', 'competency_code',
                            'competency_name', 'competency_desc', 'score'}]}]

    Assessments with no scores yet are included with average=None, so the
    student sees which assessments are still pending rather than a gap.
    """
    from .models import Assessment, AssessmentCompetency, ScoreEntry, Competency

    # Plug-in assessments belong to the plug-in project but merge into the parent
    project_ids = [project.id]
    plugin = project.plugins.filter(status='Active').first()
    if plugin:
        project_ids.append(plugin.id)

    assessments = list(
        Assessment.objects.filter(project_id__in=project_ids).order_by('order', 'id')
    )
    if not assessments:
        return []

    mappings = list(
        AssessmentCompetency.objects
        .filter(assessment_id__in=[a.id for a in assessments])
        .select_related('competency', 'competency__sub_pillar__pillar')
        .order_by('order', 'id')
    )
    if not include_kb:
        mappings = [m for m in mappings if not m.competency.sub_pillar.pillar.is_kb]
    if not mappings:
        return []

    scores = {
        se.assessment_competency_id: se.score
        for se in ScoreEntry.objects.filter(
            student=student, assessment_competency_id__in=[m.id for m in mappings]
        )
    }

    by_assessment = defaultdict(list)
    for m in mappings:
        by_assessment[m.assessment_id].append(m)

    breakdown = []
    for a in assessments:
        rows = []
        vals = []
        for m in by_assessment.get(a.id, []):
            score = scores.get(m.id)
            if score is not None:
                vals.append(score)
            rows.append({
                'competency_id':   m.competency_id,
                'competency_code': m.competency.code,
                'competency_name': m.competency.name,
                'competency_desc': m.competency.description,
                'score':           score,
            })
        if not rows:
            continue
        breakdown.append({
            'assessment_id':   a.id,
            'assessment_name': a.name,
            'assessment_type': a.assessment_type,
            'order':           a.order,
            'average':         round(sum(vals) / len(vals), 1) if vals else None,
            'scored_count':    len(vals),
            'total_count':     len(rows),
            'competencies':    rows,
        })

    return breakdown


def _exclude_kb_scores(scores):
    """Remove KB (Kaushal Bodh) competency scores from the dict."""
    if not scores:
        return scores
    from .models import Competency
    kb_comp_ids = set(
        Competency.objects.filter(sub_pillar__pillar__is_kb=True)
        .values_list('id', flat=True)
    )
    return {cid: s for cid, s in scores.items() if cid not in kb_comp_ids}


def get_kb_scores_for_project(student, project):
    """Get ONLY KB competency scores for a project (for KB report)."""
    all_scores = _scores_for_single_project(student, project)
    plugin = project.plugins.filter(status='Active').first()
    if plugin:
        plugin_scores = _scores_for_single_project(student, plugin)
        all_scores = _merge_scores(all_scores, plugin_scores)

    from .models import Competency
    kb_comp_ids = set(
        Competency.objects.filter(sub_pillar__pillar__is_kb=True)
        .values_list('id', flat=True)
    )
    return {cid: s for cid, s in all_scores.items() if cid in kb_comp_ids}


def _scores_for_single_project(student, project):
    """
    For a single project (or plugin), collect all ScoreEntry records and
    return { competency_id: average_score } (averaging if same competency
    appears in multiple assessments).
    """
    entries = (
        ScoreEntry.objects
        .filter(
            student=student,
            assessment_competency__assessment__project=project,
            score__isnull=False
        )
        .select_related('assessment_competency__competency')
    )

    scores_by_comp = defaultdict(list)
    for entry in entries:
        comp_id = entry.assessment_competency.competency_id
        scores_by_comp[comp_id].append(entry.score)

    return {
        comp_id: sum(scores) / len(scores)
        for comp_id, scores in scores_by_comp.items()
    }


def _merge_scores(project_scores, plugin_scores):
    """
    Merge project + plugin scores:
      - Both have it → average
      - Only one has it → use that
    """
    all_comp_ids = set(project_scores) | set(plugin_scores)
    merged = {}
    for comp_id in all_comp_ids:
        in_project = comp_id in project_scores
        in_plugin  = comp_id in plugin_scores
        if in_project and in_plugin:
            merged[comp_id] = (project_scores[comp_id] + plugin_scores[comp_id]) / 2
        elif in_project:
            merged[comp_id] = project_scores[comp_id]
        else:
            merged[comp_id] = plugin_scores[comp_id]
    return merged


# ─────────────────────────────────────────────
# STEP 2–4: Profiling Engine
# ─────────────────────────────────────────────

def run_profiling_engine(competency_scores):
    """
    competency_scores: { competency_id: score }

    Returns list of dicts sorted by score desc:
    [
      {
        'profile_id': ...,
        'profile_name': ...,
        'score': ...,
        'weightage': { competency_id: weight },
      },
      ...
    ]
    Only includes unlocked profiles.
    """
    profiles = Profile.objects.prefetch_related(
        'primary_competencies', 'secondary_competencies'
    ).all()

    results = []
    for profile in profiles:
        result = _calculate_profile_score(profile, competency_scores)
        if result is not None:
            results.append(result)

    results.sort(key=lambda x: x['score'], reverse=True)
    return results


def _calculate_profile_score(profile, competency_scores):
    """
    Returns profile score dict or None if profile is locked.
    """
    primary_comps   = list(profile.primary_competencies.all())
    secondary_comps = list(profile.secondary_competencies.all())

    # Step 1: Unlock check — need >= MIN_PRIMARY_FOR_UNLOCK assessed
    assessed_primaries = [c for c in primary_comps if c.id in competency_scores]
    if len(assessed_primaries) < MIN_PRIMARY_FOR_UNLOCK:
        return None

    # Step 2: Weightage
    # Only competencies that were actually assessed get a weight, so the
    # applied weights always sum to 1.0. An unassessed secondary must not
    # steal 10% from the primary pool (it would deflate the profile score).
    assessed_secondaries = [c for c in secondary_comps if c.id in competency_scores]
    secondary_total = len(assessed_secondaries) * SECONDARY_COMPETENCY_WEIGHT
    # Clamp so a misconfigured profile with too many secondaries can't
    # produce negative primary weights.
    remaining       = max(0.0, 1.0 - secondary_total)
    primary_weight  = remaining / len(assessed_primaries) if assessed_primaries else 0

    weightage = {}
    for c in assessed_primaries:
        weightage[c.id] = primary_weight
    for c in assessed_secondaries:
        weightage[c.id] = SECONDARY_COMPETENCY_WEIGHT

    # Step 3: Profile score
    score = 0.0
    for comp_id, weight in weightage.items():
        if comp_id in competency_scores:
            score += competency_scores[comp_id] * weight

    return {
        'profile_id':   profile.id,
        'profile_name': profile.name,
        'profile_number': profile.number,
        'score':        round(score, 2),
        'weightage':    weightage,
    }


# ─────────────────────────────────────────────
# STEP 5: Build Report Data
# ─────────────────────────────────────────────

def build_report_data(student, project):
    """
    Full pipeline: scores → profiling → report data dict.
    Returns dict ready to store in ProjectReport.
    """
    from .models import Competency

    competency_scores = get_competency_scores_for_project(student, project)

    if not competency_scores:
        return None

    profile_results = run_profiling_engine(competency_scores)

    # Top 3 profiles
    top_3 = profile_results[:TOP_PROFILES_COUNT]

    # All competency scores with names
    comp_ids  = list(competency_scores.keys())
    comp_objs = {c.id: c for c in Competency.objects.filter(id__in=comp_ids)}

    all_comp_scores = [
        {
            'competency_id':   comp_id,
            'competency_code': comp_objs[comp_id].code if comp_id in comp_objs else '',
            'competency_name': comp_objs[comp_id].name if comp_id in comp_objs else '',
            'competency_desc': comp_objs[comp_id].description if comp_id in comp_objs else '',
            'score':           round(score, 2),
        }
        for comp_id, score in competency_scores.items()
    ]
    all_comp_scores.sort(key=lambda x: x['score'], reverse=True)

    # Top 5 competencies
    top_5 = all_comp_scores[:TOP_COMPETENCIES_COUNT]

    # Skills to work on (bottom 3)
    skills_to_work_on = sorted(all_comp_scores, key=lambda x: x['score'])[:3]

    return {
        'top_3_profiles':        top_3,
        'top_5_competencies':    top_5,
        'skills_to_work_on':     skills_to_work_on,
        'all_competency_scores': all_comp_scores,
    }


# ─────────────────────────────────────────────
# Generate / Regenerate ProjectReport
# ─────────────────────────────────────────────

def generate_project_report(student, project):
    """
    Runs the full engine and saves/updates the ProjectReport.
    Returns (report, error_message).
    """
    # If someone accidentally passes a Plug-In project, use its parent instead
    if project.project_type == 'Plug In' and project.linked_project:
        project = project.linked_project

    data = build_report_data(student, project)

    if data is None:
        return None, "No scores found for this student in this project."

    report, _ = ProjectReport.objects.update_or_create(
        student=student,
        project=project,
        defaults={
            'top_3_profiles':        data['top_3_profiles'],
            'top_5_competencies':    data['top_5_competencies'],
            'skills_to_work_on':     data['skills_to_work_on'],
            'all_competency_scores': data['all_competency_scores'],
            'is_outdated':           False,
        }
    )
    return report, None


# ─────────────────────────────────────────────
# Annual Skill Passport
# ─────────────────────────────────────────────

def get_annual_passport_scores(student):
    """
    Annual Passport: per competency, take the score from the latest project
    (highest sequence_number) where it was assessed.

    Returns { competency_id: score }
    """
    # Get all projects with sequence_number, ordered latest first
    projects = Project.objects.filter(
        sequence_number__isnull=False,
        status='Active'
    ).order_by('-sequence_number')

    annual_scores = {}
    for project in projects:
        scores = get_competency_scores_for_project(student, project)  # KB already excluded by default
        for comp_id, score in scores.items():
            if comp_id not in annual_scores:
                # First time we see this competency = latest project (desc order)
                annual_scores[comp_id] = score

    return annual_scores


def get_annual_kb_scores(student):
    """Annual Kaushal Bodh scores, reported separately from the Skill Passport.

    KB competencies are deliberately kept out of the passport calculation and
    profiling (see `_exclude_kb_scores`), so they need their own read path or
    they never surface anywhere. Same latest-project-wins rule as the passport.

    Returns a list of dicts sorted by score (desc):
        [{'competency_id', 'competency_code', 'competency_name',
          'competency_desc', 'score'}]
    """
    from .models import Competency

    kb_comp_ids = set(
        Competency.objects.filter(sub_pillar__pillar__is_kb=True).values_list('id', flat=True)
    )
    if not kb_comp_ids:
        return []

    projects = Project.objects.filter(
        sequence_number__isnull=False, status='Active'
    ).order_by('-sequence_number')

    kb_scores = {}
    for project in projects:
        scores = get_competency_scores_for_project(student, project, include_kb=True)
        for comp_id, score in scores.items():
            if comp_id in kb_comp_ids and comp_id not in kb_scores:
                kb_scores[comp_id] = score

    if not kb_scores:
        return []

    comp_objs = {c.id: c for c in Competency.objects.filter(id__in=kb_scores.keys())}
    rows = [
        {
            'competency_id':   comp_id,
            'competency_code': comp_objs[comp_id].code if comp_id in comp_objs else '',
            'competency_name': comp_objs[comp_id].name if comp_id in comp_objs else '',
            'competency_desc': comp_objs[comp_id].description if comp_id in comp_objs else '',
            'sub_pillar':      _sub_pillar_label(comp_objs.get(comp_id)),
            'score':           round(score, 2),
        }
        for comp_id, score in kb_scores.items()
    ]
    rows.sort(key=lambda x: x['score'], reverse=True)
    return rows


def get_top_project(student):
    """The student's single best-performing project, for the annual passport.

    Ranks the student's generated ProjectReports by the mean of their
    competency scores and returns the highest. The project's `project_type`
    is the "work firm category" (Life Form, Machines & Materials, Human
    Services, ...) the meeting asked to surface alongside it.

    Returns None when the student has no report with any scores yet.
    Returns:
        {'project_id', 'title', 'category', 'average', 'competency_count'}
    """
    from .models import ProjectReport

    best = None
    reports = (
        ProjectReport.objects
        .filter(student=student)
        .select_related('project')
    )

    for report in reports:
        values = [
            row['score'] for row in (report.all_competency_scores or [])
            if row.get('score') is not None
        ]
        if not values:
            continue

        average = sum(values) / len(values)
        # Tie-break on the later project so the most recent win is shown.
        rank = (average, report.project.sequence_number or 0)
        if best is None or rank > best[0]:
            best = (rank, {
                'project_id':       report.project_id,
                'title':            report.project.title,
                'category':         report.project.project_type,
                'average':          round(average, 1),
                'competency_count': len(values),
            })

    return best[1] if best else None


def _sub_pillar_label(competency):
    """Sub-pillar heading for a competency, e.g. "KB1: Practical Skills".

    Uses the sub-pillar's own code + name rather than deriving a number, so
    the report matches however the framework is actually set up.
    """
    sp = getattr(competency, 'sub_pillar', None) if competency else None
    if not sp:
        return 'Other'
    return str(sp) or 'Other'


def build_kb_report(student):
    """Standalone Kaushal Bodh report (spec slide 32: "Customised report (KB)").

    KB is excluded from the Skill Passport calculation, so it gets its own
    report rather than a line in the passport. Grouped by sub-pillar, matching
    the KB1/KB2/KB3 structure on slide 22.

    Returns {'groups': [{'name', 'rows', 'average'}], 'rows', 'overall', 'count'}
    or None when the student has no KB scores.
    """
    from collections import OrderedDict

    rows = get_annual_kb_scores(student)
    if not rows:
        return None

    grouped = OrderedDict()
    for row in sorted(rows, key=lambda r: (r['sub_pillar'], -r['score'])):
        grouped.setdefault(row['sub_pillar'], []).append(row)

    groups = []
    for name, items in grouped.items():
        vals = [i['score'] for i in items]
        groups.append({
            'name': name,
            'rows': items,
            'average': round(sum(vals) / len(vals), 1) if vals else None,
        })

    all_vals = [r['score'] for r in rows]
    return {
        'groups':  groups,
        'rows':    rows,
        'overall': round(sum(all_vals) / len(all_vals), 1) if all_vals else None,
        'count':   len(rows),
    }


def generate_annual_passport(student):
    """
    Runs the profiling engine on annual scores.
    Returns full report data dict (same structure as project report).
    """
    from .models import Competency

    competency_scores = get_annual_passport_scores(student)

    if not competency_scores:
        return None

    profile_results = run_profiling_engine(competency_scores)
    top_3           = profile_results[:TOP_PROFILES_COUNT]

    comp_ids  = list(competency_scores.keys())
    comp_objs = {c.id: c for c in Competency.objects.filter(id__in=comp_ids)}

    all_comp_scores = [
        {
            'competency_id':   comp_id,
            'competency_code': comp_objs[comp_id].code if comp_id in comp_objs else '',
            'competency_name': comp_objs[comp_id].name if comp_id in comp_objs else '',
            'competency_desc': comp_objs[comp_id].description if comp_id in comp_objs else '',
            'score':           round(score, 2),
        }
        for comp_id, score in competency_scores.items()
    ]
    all_comp_scores.sort(key=lambda x: x['score'], reverse=True)

    return {
        'top_3_profiles':        top_3,
        'top_5_competencies':    all_comp_scores[:TOP_COMPETENCIES_COUNT],
        'skills_to_work_on':     sorted(all_comp_scores, key=lambda x: x['score'])[:3],
        'all_competency_scores': all_comp_scores,
    }
