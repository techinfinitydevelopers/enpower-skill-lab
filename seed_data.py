"""
Idempotent seed-data script for Enpower Skill Lab.
Run:  venv\Scripts\python manage.py shell < seed_data.py
Safe to re-run: uses get_or_create everywhere.
"""
import os, django, datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enpower_skill_lab.settings')
try:
    django.setup()
except Exception:
    pass  # already configured when run via `manage.py shell`

from django.contrib.auth import get_user_model
from accounts.models import User as _U  # noqa
from coordinator.models import ProgramCoordinator
from teacher.models import Teacher
from school_admin.models import SchoolAdmin
from student.models import Student
from parent.models import Parent
from schools.models import School, Class
from competencies.models import (
    Framework, Pillar, SubPillar, Competency, Profile,
    Project, Assessment, AssessmentCompetency,
)

User = get_user_model()
PWD = "Test@123"
AY = "2025-2026"

created = {}
def bump(k, c):
    created[k] = created.get(k, 0) + (1 if c else 0)

def mkuser(username, role, email, first, last):
    u, c = User.objects.get_or_create(
        username=username,
        defaults={'role': role, 'email': email, 'first_name': first, 'last_name': last,
                  'is_active': True},
    )
    # always (re)set password so re-runs keep known creds
    u.set_password(PWD)
    u.role = role
    u.email = email
    u.save()
    bump('User', c)
    return u

# ============================================================ USERS
coord_u   = mkuser('coordinator1', 'PROGRAM_COORDINATOR', 'coordinator1@example.com', 'Cathy', 'Coord')
teacher_u = mkuser('teacher1',     'THINKING_COACH',      'teacher1@example.com',     'Tina',  'Teach')
admin_u   = mkuser('principal1',   'SCHOOL_ADMIN',        'principal1@example.com',   'Paul',  'Principal')

student_us = []
for i in range(1, 5):
    student_us.append(mkuser(f'student{i}', 'STUDENT', f'student{i}@example.com', f'Stud{i}', 'Kumar'))

parent_us = []
for i in range(1, 3):
    parent_us.append(mkuser(f'parent{i}', 'PARENT', f'parent{i}@example.com', f'Par{i}', 'Kumar'))

# ============================================================ FRAMEWORK
fw, c = Framework.objects.get_or_create(
    name='FSL', defaults={'prefix': 'SP', 'is_fixed': True, 'order': 1})
bump('Framework', c)

# ============================================================ SCHOOL
school, c = School.objects.get_or_create(
    school_code='SV001',
    defaults={
        'school_name': 'Shiv Vani Public School',
        'board': 'cbse',
        'school_type': 'private',
        'medium': 'english',
        'school_email': 'info@shivvani.example.com',
        'school_phone': '9876543210',
        'principal_name': 'Paul Principal',
        'principal_phone': '9876543211',
        'principal_email': 'principal1@example.com',
        'branch_address': '12 MG Road',
        'city': 'Pune',
        'state': 'Maharashtra',
        'pincode': '411001',
        'emergency_contact_person': 'Front Office',
        'emergency_phone': '9876543212',
        'skill_program': 'fsl',
        'program_academic_year': AY,
        'framework_ref': fw,
        'framework_type': 'FSL',
        'srm': coord_u,
        'trainer_assigned': teacher_u,
        'school_admin': admin_u,
        'is_active': True,
        'onboarding_completed': True,
    },
)
bump('School', c)
# ensure assignments on re-run
School.objects.filter(pk=school.pk).update(
    srm=coord_u, trainer_assigned=teacher_u, school_admin=admin_u,
    skill_program='fsl', program_academic_year=AY, framework_ref=fw)
school.refresh_from_db()

# ============================================================ PROFILE ROWS
def dob(y, m=1, d=1):
    return datetime.date(y, m, d)

coord, c = ProgramCoordinator.objects.get_or_create(
    user=coord_u,
    defaults={
        'full_name': 'Cathy Coord', 'gender': 'female', 'date_of_birth': dob(1990),
        'nationality': 'Indian', 'employee_id': 'PC001',
        'aadhar_number': '100000000001', 'pan_number': 'ABCPC0001A',
        'designation': 'Program Coordinator', 'qualification': 'M.Ed',
        'specialization': 'Operations', 'total_experience': '8 years',
        'languages_known': 'English, Hindi',
        'mobile_number': '9876500001', 'official_email': 'coordinator1@example.com',
        'current_address': '1 Coordinator Lane', 'city': 'Pune', 'state': 'Maharashtra',
        'pincode': '411001', 'joining_date': dob(2022, 6, 1), 'employment_type': 'Full-time',
        'bank_name': 'SBI', 'branch_name': 'Pune Main', 'account_number': '00011112222',
        'ifsc_code': 'SBIN0000123',
    },
)
bump('ProgramCoordinator', c)
coord.schools_assigned.add(school)

teacher, c = Teacher.objects.get_or_create(
    user=teacher_u,
    defaults={
        'school': school, 'employee_id': 'TC001', 'full_name': 'Tina Teach',
        'gender': 'female', 'date_of_birth': dob(1992), 'nationality': 'Indian',
        'designation': 'enpower-trainer', 'qualification': 'B.Ed',
        'total_experience': '5 years', 'mobile_number': '9876500002',
        'official_email': 'teacher1@example.com', 'current_address': '2 Coach Street',
        'city': 'Pune', 'state': 'Maharashtra', 'pin_code': '411001',
        'joining_date': dob(2023, 6, 1), 'employment_type': 'full-time',
        'emergency_contact_name': 'Raj Teach', 'emergency_relation': 'spouse',
        'emergency_mobile': '9876500099', 'dashboard_role': 'coach',
    },
)
bump('Teacher', c)
Teacher.objects.filter(pk=teacher.pk).update(school=school)

sa, c = SchoolAdmin.objects.get_or_create(
    user=admin_u,
    defaults={
        'full_name': 'Paul Principal', 'email': 'principal1@example.com',
        'phone': '9876500003', 'gender': 'male', 'school': school,
        'account_status': 'active', 'is_active': True, 'password_changed': True,
    },
)
bump('SchoolAdmin', c)
SchoolAdmin.objects.filter(pk=sa.pk).update(school=school)

# ============================================================ CLASS
klass, c = Class.objects.get_or_create(
    school=school, grade='6', division='A', academic_year=AY,
    defaults={
        'class_name': 'Std 6A', 'thinking_coach': teacher_u,
        'is_active': True, 'created_by': admin_u,
    },
)
bump('Class', c)
Class.objects.filter(pk=klass.pk).update(thinking_coach=teacher_u)

# ============================================================ STUDENTS
students = []
for i, su in enumerate(student_us, start=1):
    st, c = Student.objects.get_or_create(
        gr_number=f'GR600{i}',
        defaults={
            'user': su, 'first_name': f'Stud{i}', 'last_name': 'Kumar',
            'gender': 'male' if i % 2 else 'female', 'date_of_birth': dob(2013, 3, i),
            'nationality': 'Indian', 'school': school, 'school_name': school.school_name,
            'student_class': '6', 'division': 'A', 'roll_number': str(i),
            'academic_year': AY, 'school_board': 'CBSE',
            'school_email': f'student{i}@example.com',
            'skill_lab_reg_id': f'SL600{i}', 'enrollment_date': dob(2025, 6, 1),
            'attendance_status': 'active',
            'emergency_name': 'Guardian Kumar', 'emergency_relationship': 'father',
            'emergency_mobile': f'987650100{i}',
        },
    )
    bump('Student', c)
    Student.objects.filter(pk=st.pk).update(school=school, user=su,
                                            student_class='6', division='A')
    students.append(st)

# ============================================================ PARENTS (M2M each -> 2 students)
parent_links = [students[0:2], students[2:4]]
for i, pu in enumerate(parent_us, start=1):
    p, c = Parent.objects.get_or_create(
        email=f'parent{i}@example.com',
        defaults={
            'user': pu, 'full_name': f'Par{i} Kumar', 'relation_to_student': 'father',
            'mobile_number': f'987650200{i}', 'residential_address': f'{i} Parent Colony',
            'city': 'Pune', 'state': 'Maharashtra', 'pin_code': '411001',
            'emergency_name': 'Relative Kumar', 'emergency_relation': 'uncle',
            'emergency_phone': f'987650300{i}', 'account_status': 'active',
        },
    )
    bump('Parent', c)
    Parent.objects.filter(pk=p.pk).update(user=pu)
    p.students.set(parent_links[i - 1])

# ============================================================ PILLARS / SUBPILLARS / COMPETENCIES
pillar_defs = [
    ('Cognitive Skills', '1', 'teal', 1),
    ('Social Skills',     '2', 'blue', 2),
]
pillars = []
for name, num, color, order in pillar_defs:
    pl, c = Pillar.objects.get_or_create(
        framework_ref=fw, number=num,
        defaults={'name': name, 'color': color, 'order': order, 'framework': 'FSL'},
    )
    bump('Pillar', c)
    pillars.append(pl)

sp_defs = [(pillars[0], 1, 'Critical Thinking'), (pillars[1], 2, 'Collaboration')]
subpillars = []
for pl, spn, name in sp_defs:
    sp, c = SubPillar.objects.get_or_create(
        sp_number=spn, defaults={'pillar': pl, 'name': name})
    bump('SubPillar', c)
    subpillars.append(sp)

comp_defs = [
    (subpillars[0], 'SP1.C1', 'Analytical Reasoning'),
    (subpillars[0], 'SP1.C2', 'Problem Solving'),
    (subpillars[0], 'SP1.C3', 'Decision Making'),
    (subpillars[1], 'SP2.C1', 'Teamwork'),
    (subpillars[1], 'SP2.C2', 'Communication'),
    (subpillars[1], 'SP2.C3', 'Empathy'),
]
comps = {}
for sp, code, name in comp_defs:
    cp, c = Competency.objects.get_or_create(
        code=code,
        defaults={'sub_pillar': sp, 'name': name, 'stage': 'Middle', 'status': 'Active'},
    )
    bump('Competency', c)
    comps[code] = cp

# ============================================================ PROFILES
prof_defs = [
    (1, 'The Analyst',     ['SP1.C1', 'SP1.C2'], ['SP2.C1', 'SP2.C2']),
    (2, 'The Collaborator',['SP2.C1', 'SP2.C2'], ['SP1.C1', 'SP1.C3']),
]
for num, name, prim, sec in prof_defs:
    pr, c = Profile.objects.get_or_create(number=num, defaults={'name': name})
    bump('Profile', c)
    pr.primary_competencies.set([comps[x] for x in prim])
    pr.secondary_competencies.set([comps[x] for x in sec])

# ============================================================ PROJECTS  (grade = STAGE value 'Middle')
proj_defs = [('Bio Conservation', 1), ('Eco Build', 2)]
projects = {}
for title, seq in proj_defs:
    pj, c = Project.objects.get_or_create(
        title=title,
        defaults={
            'project_type': 'Life Form', 'grade': 'Middle', 'framework_ref': fw,
            'framework': 'FSL', 'status': 'Active', 'sequence_number': seq,
        },
    )
    bump('Project', c)
    Project.objects.filter(pk=pj.pk).update(status='Active', sequence_number=seq,
                                            grade='Middle', framework_ref=fw)
    projects[title] = pj

# ============================================================ ASSESSMENT + AssessmentCompetency
asmt, c = Assessment.objects.get_or_create(
    project=projects['Bio Conservation'], name='Assessment 1',
    defaults={'assessment_type': 'Written Assignment', 'order': 1},
)
bump('Assessment', c)
for order, code in enumerate(['SP1.C1', 'SP1.C2', 'SP2.C1'], start=1):
    ac, c = AssessmentCompetency.objects.get_or_create(
        assessment=asmt, competency=comps[code],
        defaults={'comp_type': 'individual', 'order': order},
    )
    bump('AssessmentCompetency', c)

# ============================================================ REPORT
print("\n" + "=" * 70)
print("SEED COMPLETE — created counts (0 = already existed)")
print("=" * 70)
for k in sorted(created):
    print(f"  {k:<22}: {created[k]}")

print("\n" + "=" * 70)
print("CREDENTIALS  (password for ALL = Test@123)")
print("=" * 70)
rows = [
    ('admin',        '(existing)', 'SUPER_ADMIN',         '/super-admin/dashboard/'),
    ('coordinator1', PWD,          'PROGRAM_COORDINATOR', '/coordinator/dashboard/'),
    ('teacher1',     PWD,          'THINKING_COACH',      '/teacher/dashboard/'),
    ('principal1',   PWD,          'SCHOOL_ADMIN',        '/school-admin/dashboard/'),
    ('student1',     PWD,          'STUDENT',             '/student/dashboard/'),
    ('student2',     PWD,          'STUDENT',             '/student/dashboard/'),
    ('student3',     PWD,          'STUDENT',             '/student/dashboard/'),
    ('student4',     PWD,          'STUDENT',             '/student/dashboard/'),
    ('parent1',      PWD,          'PARENT',              '/parent/dashboard/'),
    ('parent2',      PWD,          'PARENT',              '/parent/dashboard/'),
]
print(f"{'username':<14}{'password':<12}{'role':<22}{'dashboard'}")
print("-" * 70)
for u, pw, r, d in rows:
    print(f"{u:<14}{pw:<12}{r:<22}{d}")

print("\nparent1 -> student1, student2   |   parent2 -> student3, student4")
print("School: Shiv Vani Public School (SV001) | Class: Std 6A | Project assessment: Bio Conservation")
