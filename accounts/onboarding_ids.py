"""Structured student & parent onboarding ID generator.

Implements the ID scheme from the onboarding flow spec (slide 2):

    Student: SV-RG-6A-222-26-stu
    Parent : SV-RG-6A-222-26-par

Component breakdown for the example (Shiv Vani, Riddhima Guruji, grade 6A,
born 22 Feb, academic year 2026):
    SV   school initials (first letter of first two words of the school name)
    RG   student initials (first letter of first + last name)
    6A   grade + division
    222  birth date = day + month (22 + 2)
    26   academic year, last two digits
    stu  role suffix (par for the parent)

The parent shares the child's base so the two IDs line up. The generated ID is
used as the login username AND the initial password (changeable after first
login), and is stored on Student.skill_lab_reg_id / Parent.parent_id.
"""

import re
from datetime import date, datetime


def _coerce_date(value):
    """Accept a date/datetime or a string in a few common formats."""
    if isinstance(value, (date, datetime)):
        return value
    if not value:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def _school_prefix(school, fallback_name=''):
    """Two uppercase letters identifying the school (e.g. 'Shiv Vani' -> 'SV')."""
    name = (getattr(school, 'school_name', '') or '') if school is not None else ''
    if not name:
        name = fallback_name or ''
    words = [w for w in re.split(r'\s+', name.strip()) if w]
    if len(words) >= 2:
        letters = words[0][:1] + words[1][:1]
    elif len(words) == 1:
        letters = words[0][:2]
    else:
        letters = ''
    letters = re.sub(r'[^A-Za-z]', '', letters).upper()
    if len(letters) < 2 and school is not None:
        code = re.sub(r'[^A-Za-z]', '', getattr(school, 'school_code', '') or '').upper()
        letters = (letters + code)[:2]
    return (letters or 'XX')[:2]


def _initials(first_name, last_name):
    """Student initials, e.g. ('Riddhima', 'Guruji') -> 'RG'."""
    ini = (first_name or '').strip()[:1] + (last_name or '').strip()[:1]
    ini = re.sub(r'[^A-Za-z]', '', ini).upper()
    return ini or 'X'


def _dob_part(dob):
    """Birth date as day+month with no zero-padding, e.g. 22 Feb -> '222'."""
    d = _coerce_date(dob)
    return f"{d.day}{d.month}" if d else '0'


def _year_part(academic_year):
    """Last two digits of the academic year, e.g. '2025-2026' -> '26'."""
    s = str(academic_year or '')
    years = re.findall(r'\d{4}', s)
    if years:
        return years[-1][-2:]
    two = re.findall(r'\d{2}', s)
    if two:
        return two[-1]
    return datetime.now().strftime('%y')


def build_id_base(school, first_name, last_name, student_class, division,
                  dob, academic_year, fallback_school_name=''):
    """Build the shared ID base (everything before the -stu/-par suffix)."""
    sch = _school_prefix(school, fallback_school_name)
    ini = _initials(first_name, last_name)
    grade = re.sub(r'\s+', '', str(student_class or '').strip())
    div = re.sub(r'\s+', '', str(division or '').strip()).upper()
    return f"{sch}-{ini}-{grade}{div}-{_dob_part(dob)}-{_year_part(academic_year)}"


def _resolve_unique(base, suffix, exists):
    """Return `{base}-{suffix}`, inserting a counter before the suffix on clash."""
    candidate = f"{base}-{suffix}"
    if not exists(candidate):
        return candidate
    n = 2
    while True:
        candidate = f"{base}-{n}-{suffix}"
        if not exists(candidate):
            return candidate
        n += 1


def generate_student_id(base):
    """Unique student ID (`base-stu`) not colliding with any username/reg id."""
    from accounts.models import User
    from student.models import Student

    def exists(cid):
        return (User.objects.filter(username=cid).exists()
                or Student.objects.filter(skill_lab_reg_id=cid).exists())

    return _resolve_unique(base, 'stu', exists)


def generate_parent_id(base):
    """Unique parent ID (`base-par`) not colliding with any username/parent id."""
    from accounts.models import User
    from parent.models import Parent

    def exists(cid):
        return (User.objects.filter(username=cid).exists()
                or Parent.objects.filter(parent_id=cid).exists())

    return _resolve_unique(base, 'par', exists)


def student_id_for(school, first_name, last_name, student_class, division,
                   dob, academic_year, fallback_school_name=''):
    """Convenience: build base from fields and return a unique student ID."""
    base = build_id_base(school, first_name, last_name, student_class, division,
                         dob, academic_year, fallback_school_name)
    return generate_student_id(base)


def parent_id_from_student(student):
    """Parent ID derived from the child's own details (shares the child's base)."""
    base = build_id_base(
        getattr(student, 'school', None),
        getattr(student, 'first_name', ''),
        getattr(student, 'last_name', ''),
        getattr(student, 'student_class', ''),
        getattr(student, 'division', ''),
        getattr(student, 'date_of_birth', None),
        getattr(student, 'academic_year', ''),
        fallback_school_name=getattr(student, 'school_name', '') or '',
    )
    return generate_parent_id(base)
