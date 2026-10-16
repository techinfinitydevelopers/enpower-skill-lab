"""Printing a score as the letter grade a family sees.

The client's reason for grades, in their words: "so they don't compare too
much". That only holds if the number is gone everywhere a parent or a student
can look -- a report showing `A` in one place and `8/10` in another gives the
number back and the point with it.

A filter rather than a field on every view, because there is nothing to store:
the score stays out of ten in the database, where the coach reads it and every
average is still calculated from it.
"""

from django import template

from ..grading import grade_for

register = template.Library()


@register.filter(name='grade')
def grade(value):
    """The letter for a score, or an em dash when there is no score.

    A dash rather than an empty string: a blank cell reads as a page that
    failed to load, and a `D` would be an accusation against a child who was
    never assessed.
    """
    letter = grade_for(value)
    return letter if letter else '\u2014'
