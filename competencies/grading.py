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

A grade is only ever a way of printing a number. Nothing is stored as a
letter: the scores stay out of ten in the database, where the coach reads them
and every average is still worked out from them, and the family's pages turn
them into letters as they are drawn.

The client's reason, in their words: "The idea is to not let parents see the
actual score so they don't compare too much... But while showing in parents
and students, let's keep grades only." The coach keeps the number, and sees
the grade beside it.
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
