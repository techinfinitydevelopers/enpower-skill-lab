"""Letter grades for scores on the 1-10 scale.

The client sent the bands on 2026-10-15:

    Avg Score   Grade
    9 - 10      A+
    7 - 8.9     A
    5 - 6.9     B
    3 - 4.9     C
    0 - 2.9     D

Written as ranges they leave hairline gaps -- 8.95 sits between "7 - 8.9" and
"9 - 10". Averages are shown to one decimal so that never surfaces, but the
code has to answer for every number, so each band is read as "this value and
up" and the gaps close.

A grade is only ever a way of printing a number. Nothing is stored as a letter:
the scores stay out of ten in the database, and the report turns them into
letters at the moment it draws them. That means a school can change its mind
and every report it has already published follows along.
"""

# Lowest average that earns each grade, best first. Order matters.
BANDS = [
    (9.0, 'A+'),
    (7.0, 'A'),
    (5.0, 'B'),
    (3.0, 'C'),
    (0.0, 'D'),
]


def grade_for(score):
    """The letter for a score out of ten, or None if there is no score.

    None in, None out: an unscored assessment has no grade, and must not come
    back as a D. A D is something a student earned; a blank is not.
    """
    if score is None:
        return None
    try:
        value = float(score)
    except (TypeError, ValueError):
        return None
    for floor, letter in BANDS:
        if value >= floor:
            return letter
    # Only reachable for a negative score, which the 1-10 scale cannot produce.
    return 'D'


def band_table():
    """The bands as the client wrote them, for showing on screen."""
    return [
        ('9.0 - 10', 'A+'),
        ('7.0 - 8.9', 'A'),
        ('5.0 - 6.9', 'B'),
        ('3.0 - 4.9', 'C'),
        ('0 - 2.9', 'D'),
    ]


def shows_grade(assessment, school):
    """Has this school chosen grades for this assessment?

    A Project carries no school -- it is filtered by grade and framework, so
    one project runs in every school on that framework, and its Assessments are
    shared along with it. A single flag on the Assessment would therefore let a
    coach in one school rewrite the reports of every other school's children.
    The choice is stored per school for that reason.

    Returns False when either side is missing, which is the old behaviour:
    scores out of ten.
    """
    if assessment is None or school is None:
        return False
    from .models import AssessmentGradeDisplay

    assessment_id = getattr(assessment, 'id', assessment)
    school_id = getattr(school, 'id', school)
    return AssessmentGradeDisplay.objects.filter(
        assessment_id=assessment_id, school_id=school_id, show_grade=True
    ).exists()


def grade_display_map(assessment_ids, school):
    """{assessment_id: True} for the assessments this school grades.

    One query for a whole report, rather than one per assessment card.
    """
    if not assessment_ids or school is None:
        return {}
    from .models import AssessmentGradeDisplay

    school_id = getattr(school, 'id', school)
    return {
        row_id: True
        for row_id in AssessmentGradeDisplay.objects.filter(
            assessment_id__in=list(assessment_ids),
            school_id=school_id,
            show_grade=True,
        ).values_list('assessment_id', flat=True)
    }
