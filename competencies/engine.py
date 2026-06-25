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
    secondary_total = len(secondary_comps) * SECONDARY_COMPETENCY_WEIGHT
    remaining       = 1.0 - secondary_total
    primary_weight  = remaining / len(assessed_primaries) if assessed_primaries else 0

    weightage = {}
    for c in assessed_primaries:
        weightage[c.id] = primary_weight
    for c in secondary_comps:
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
