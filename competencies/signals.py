"""
Keep ProjectReport.is_outdated honest.

A ProjectReport is a frozen snapshot — it only changes when a coach presses
Generate. So the moment a score behind it changes, the stored report stops
matching the data and the student is looking at stale numbers.

The flag and its UI already existed (a banner on the student's report, an
"outdated" tag on the coach's Score Viewing table) but nothing ever set it to
True, so neither ever appeared. This wires it up.

A signal rather than a call inside the score-entry view: every write path —
score entry, bulk import, the admin, a shell session — has to mark the report,
and a signal cannot be forgotten by the next one added.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import ProjectReport, ScoreEntry


def _report_project_id(score_entry):
    """The project whose report this score feeds.

    Plug-In scores merge into the parent project (spec slide 24), so a Plug-In
    score must invalidate the parent's report — the Plug-In has none of its own.
    """
    project = score_entry.assessment_competency.assessment.project
    if project.project_type == 'Plug In' and project.linked_project_id:
        return project.linked_project_id
    return project.id


@receiver(post_save, sender=ScoreEntry)
@receiver(post_delete, sender=ScoreEntry)
def mark_report_outdated(sender, instance, **kwargs):
    # `created` is absent on post_delete, and a brand-new score invalidates an
    # existing report just as much as an edited one, so it isn't checked.
    try:
        project_id = _report_project_id(instance)
    except Exception:
        # A cascade delete can leave the related rows already gone; there is
        # nothing to invalidate in that case.
        return

    (ProjectReport.objects
     .filter(student_id=instance.student_id, project_id=project_id, is_outdated=False)
     .update(is_outdated=True))
