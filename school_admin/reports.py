"""
School Admin Reports — the four grade-wise panels plus a full Excel download.

The panels are the same shared component the other roles use, scoped to this
principal's own school. The download writes the same figures to a workbook, one
sheet per panel, so what is on screen and what leaves as a file cannot disagree.

View-only throughout, per the presentation: this login belongs to the principal.
"""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.shortcuts import render

from competencies import report_panels
from .pages import _school_or_redirect
from .views import is_school_admin


def _panels_for(request, school):
    return report_panels.build([school.id], month=(request.GET.get('month') or None))


@login_required
@user_passes_test(is_school_admin)
def download_reports(request):
    """The panels on screen, with a button that exports the same figures."""
    school, bail = _school_or_redirect(request)
    if bail:
        return bail

    if request.GET.get('export') == 'xlsx':
        return _export_workbook(school, _panels_for(request, school))

    return render(request, 'school_admin/download-reports.html', {
        'school': school,
        'panels': _panels_for(request, school),
        'page_title': 'Download Reports',
    })


def _export_workbook(school, panels):
    """One sheet per panel, matching what the screen shows."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    head_font = Font(bold=True, color='FFFFFF', size=11)
    head_fill = PatternFill('solid', start_color='5B1F6F', end_color='5B1F6F')
    title_font = Font(bold=True, size=13)

    def sheet(title, subtitle, headers, rows, first=False):
        ws = wb.active if first else wb.create_sheet()
        ws.title = title[:31]

        ws.cell(row=1, column=1, value=f'{school.school_name} — {subtitle}').font = title_font
        for col, h in enumerate(headers, 1):
            c = ws.cell(row=3, column=col, value=h)
            c.font, c.fill = head_font, head_fill
            c.alignment = Alignment(horizontal='center')
        for r_i, row in enumerate(rows, 4):
            for c_i, val in enumerate(row, 1):
                ws.cell(row=r_i, column=c_i, value=val)

        # Width from the longest cell, so nothing arrives as ####.
        for col in range(1, len(headers) + 1):
            longest = len(str(headers[col - 1]))
            for row in rows:
                if col - 1 < len(row):
                    longest = max(longest, len(str(row[col - 1])))
            ws.column_dimensions[get_column_letter(col)].width = min(longest + 4, 42)
        return ws

    d = panels['distribution']
    sheet('Student Distribution', 'Students by grade',
          ['Grade', 'Active students'],
          [[b['grade'], b['students']] for b in d['bars']] + [['Total', d['total']]],
          first=True)

    a = panels['attendance']
    month = panels.get('month_label') or 'all recorded months'
    sheet('Attendance', f'Attendance by grade — {month}',
          ['Grade', 'Attendance %'],
          [[b['grade'], b['percent']] for b in a['bars']]
          + ([['School average', a['school_average']]] if a['school_average'] is not None else []))

    c = panels['completion']
    sheet('Project Completion', 'Project completion by grade',
          ['Grade', 'Completion %'],
          [[b['grade'], b['percent']] for b in c['bars']]
          + ([['Overall', c['overall']]] if c['overall'] is not None else []))

    rows = []
    for row in (panels.get('profiles') or []):
        names = [p['name'] for p in row['profiles']] + [''] * 3
        counts = [p['students'] for p in row['profiles']] + [''] * 3
        rows.append([row['grade'], names[0], counts[0], names[1], counts[1], names[2], counts[2]])
    sheet('Top Skill Profiles', 'Top 3 skill profiles by grade',
          ['Grade', 'Profile 1', 'Students', 'Profile 2', 'Students', 'Profile 3', 'Students'],
          rows)

    filename = f'{school.school_name} reports.xlsx'.replace('/', '-')
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


# ── Individual student project reports ──────────────────────────────────
#
# "Provide access to individual student project reports by Grade, Section &
#  Name - Add under reports"  -- Phase 2 deck, small change 13
#
# The principal could see grade-wise panels and download a workbook, but not
# open one child's report, which is what a parent asks them about.

@login_required
@user_passes_test(is_school_admin)
def student_reports(request):
    """Pick a student by Grade, Section and Name, and see their reports."""
    from competencies.models import ProjectReport
    from student.models import Student

    school, bail = _school_or_redirect(request)
    if bail:
        return bail

    students = Student.objects.filter(school=school, is_active=True)

    grades = sorted(
        {str(g).strip() for g in students.values_list('student_class', flat=True)
         if str(g).strip()},
        key=lambda g: (not g.isdigit(), int(g) if g.isdigit() else 0, g))

    grade = (request.GET.get('grade') or '').strip()
    if grade not in grades:
        grade = ''
    if grade:
        students = students.filter(student_class=grade)

    # Sections are free text and have been stored in both cases, so they are
    # folded here and compared with __iexact below.
    divisions = sorted({(d or '').strip().upper()
                        for d in students.values_list('division', flat=True)
                        if (d or '').strip()})

    division = (request.GET.get('division') or '').strip().upper()
    if division not in divisions:
        division = ''
    if division:
        students = students.filter(division__iexact=division)

    name = (request.GET.get('name') or '').strip()
    if name:
        from django.db.models import Q
        students = students.filter(Q(first_name__icontains=name)
                                   | Q(last_name__icontains=name)
                                   | Q(skill_lab_reg_id__icontains=name))

    students = students.order_by('student_class', 'division',
                                 'first_name', 'last_name')

    # One query for the counts rather than one per student.
    counts = {}
    for sid in ProjectReport.objects.filter(
            student__in=students).values_list('student_id', flat=True):
        counts[sid] = counts.get(sid, 0) + 1

    rows = [{'student': s, 'reports': counts.get(s.id, 0)} for s in students]

    return render(request, 'school_admin/student-reports.html', {
        'school': school,
        'rows': rows,
        'grades': grades,
        'divisions': divisions,
        'selected_grade': grade,
        'selected_division': division,
        'name_query': name,
        'page_title': 'Student Reports',
    })


@login_required
@user_passes_test(is_school_admin)
def student_report_list(request, student_id):
    """Which project reports exist for one student of this school."""
    from django.shortcuts import get_object_or_404

    from competencies.report_context import project_report_rows
    from student.models import Student

    school, bail = _school_or_redirect(request)
    if bail:
        return bail

    # Scoped to the principal's own school, so a student id from elsewhere is
    # a 404 rather than another school's child.
    student = get_object_or_404(Student, id=student_id, school=school)

    return render(request, 'school_admin/student-report-list.html', {
        'school': school,
        'student': student,
        'reports': project_report_rows(student),
        'page_title': f'{student.first_name} — Reports',
    })


@login_required
@user_passes_test(is_school_admin)
def student_report_detail(request, student_id, project_id):
    """One project report, the same page the student and parent see."""
    from django.shortcuts import get_object_or_404
    from django.urls import reverse

    from competencies.report_context import build_project_report_context
    from student.models import Student

    school, bail = _school_or_redirect(request)
    if bail:
        return bail

    student = get_object_or_404(Student, id=student_id, school=school)

    context = build_project_report_context(
        student, project_id,
        nav_back_url=reverse('school_admin_student_report_list',
                             args=[student.id]),
        nav_back_label=f"Back to {student.first_name}'s Reports",
        nav_next_url='')
    context['school'] = school
    return render(request, 'school_admin/student-report-detail.html', context)
