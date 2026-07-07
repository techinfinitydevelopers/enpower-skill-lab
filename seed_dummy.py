"""
Dummy assignable data for Enpower Skill Lab.
Creates several Thinking Coaches, Schools, Coordinators, School Admins,
Classes and Students — but LEAVES School.trainer_assigned and
Class.thinking_coach EMPTY so you can assign them yourself from the dashboard.

Run:  venv\\Scripts\\python manage.py shell < seed_dummy.py
Safe to re-run: uses get_or_create everywhere. Password for all users: Test@123
"""
import datetime
from django.contrib.auth import get_user_model
from coordinator.models import ProgramCoordinator
from teacher.models import Teacher
from school_admin.models import SchoolAdmin
from student.models import Student
from schools.models import School, Class
from competencies.models import Framework

User = get_user_model()
PWD = "Test@123"
AY = "2025-2026"

def dob(y, m=1, d=1):
    return datetime.date(y, m, d)

created = {}
def bump(k, c):
    created[k] = created.get(k, 0) + (1 if c else 0)

def mkuser(username, role, email, first, last):
    u, c = User.objects.get_or_create(
        username=username,
        defaults={'role': role, 'email': email, 'first_name': first,
                  'last_name': last, 'is_active': True},
    )
    u.set_password(PWD); u.role = role; u.email = email; u.save()
    bump('User', c)
    return u

fw = Framework.objects.filter(name='FSL').first() or Framework.objects.first()

# ============================================================ SCHOOLS (3)
# NOTE: trainer_assigned intentionally left NULL — assign from dashboard.
school_defs = [
    ('DUM01', 'Greenwood International School', 'Mumbai', 'Maharashtra', '400001'),
    ('DUM02', 'Sunrise Public Academy',        'Delhi',  'Delhi',       '110001'),
    ('DUM03', 'Blue Valley High School',       'Bengaluru', 'Karnataka', '560001'),
]
schools = []
for i, (code, name, city, state, pin) in enumerate(school_defs, start=1):
    s, c = School.objects.get_or_create(
        school_code=code,
        defaults={
            'school_name': name, 'board': 'cbse', 'school_type': 'private',
            'medium': 'english', 'school_email': f'info@{code.lower()}.example.com',
            'school_phone': f'900000000{i}', 'principal_name': f'Principal {name.split()[0]}',
            'principal_phone': f'900000010{i}', 'principal_email': f'principal@{code.lower()}.example.com',
            'branch_address': f'{i} Main Road', 'city': city, 'state': state, 'pincode': pin,
            'emergency_contact_person': 'Front Office', 'emergency_phone': f'900000020{i}',
            'skill_program': 'fsl', 'program_academic_year': AY,
            'framework_ref': fw, 'framework_type': 'FSL',
            'is_active': True, 'onboarding_completed': True,
        },
    )
    bump('School', c)
    schools.append(s)

# ============================================================ THINKING COACHES (6)
# Created active so they appear in the trainer/coach dropdowns.
coach_defs = [
    ('Arjun Mehta', 'male'), ('Priya Sharma', 'female'), ('Rahul Verma', 'male'),
    ('Sneha Iyer', 'female'), ('Vikram Singh', 'male'), ('Anjali Nair', 'female'),
]
coaches = []
for i, (full, gender) in enumerate(coach_defs, start=1):
    first, last = full.split()[0], full.split()[1]
    u = mkuser(f'coach{i:02d}', 'THINKING_COACH', f'coach{i:02d}@example.com', first, last)
    t, c = Teacher.objects.get_or_create(
        user=u,
        defaults={
            'school': schools[(i - 1) % len(schools)], 'employee_id': f'DTC{i:03d}',
            'full_name': full, 'gender': gender, 'date_of_birth': dob(1990, 1, i),
            'nationality': 'Indian', 'designation': 'enpower-trainer', 'qualification': 'B.Ed',
            'total_experience': f'{i} years', 'mobile_number': f'900010000{i}',
            'official_email': f'coach{i:02d}@example.com', 'current_address': f'{i} Coach Lane',
            'city': 'Pune', 'state': 'Maharashtra', 'pin_code': '411001',
            'joining_date': dob(2023, 6, 1), 'employment_type': 'full-time',
            'emergency_contact_name': 'Relative', 'emergency_relation': 'sibling',
            'emergency_mobile': f'900019000{i}', 'dashboard_role': 'coach',
        },
    )
    bump('Teacher', c)
    coaches.append(t)

# ============================================================ COORDINATORS (3)
coord_defs = ['Deepak Rao', 'Meera Joshi', 'Sanjay Gupta']
for i, full in enumerate(coord_defs, start=1):
    first, last = full.split()[0], full.split()[1]
    u = mkuser(f'coord{i:02d}', 'PROGRAM_COORDINATOR', f'coord{i:02d}@example.com', first, last)
    co, c = ProgramCoordinator.objects.get_or_create(
        user=u,
        defaults={
            'full_name': full, 'gender': 'male' if i % 2 else 'female', 'date_of_birth': dob(1988, 1, i),
            'nationality': 'Indian', 'employee_id': f'DPC{i:03d}',
            'aadhar_number': f'20000000000{i}', 'pan_number': f'DUMPC{i:03d}Z',
            'designation': 'Program Coordinator', 'qualification': 'M.Ed',
            'specialization': 'Operations', 'total_experience': f'{i+5} years',
            'languages_known': 'English, Hindi', 'mobile_number': f'900020000{i}',
            'official_email': f'coord{i:02d}@example.com', 'current_address': f'{i} Coord Lane',
            'city': 'Pune', 'state': 'Maharashtra', 'pincode': '411001',
            'joining_date': dob(2022, 6, 1), 'employment_type': 'Full-time',
            'bank_name': 'SBI', 'branch_name': 'Main', 'account_number': f'0001111{i:04d}',
            'ifsc_code': 'SBIN0000123',
        },
    )
    bump('ProgramCoordinator', c)
    # assign each coordinator to one school so their dashboard scope has schools
    co.schools_assigned.add(schools[(i - 1) % len(schools)])

# ============================================================ SCHOOL ADMINS (3)
sa_defs = ['Kavita Desai', 'Ramesh Pillai', 'Neha Kapoor']
for i, full in enumerate(sa_defs, start=1):
    first, last = full.split()[0], full.split()[1]
    u = mkuser(f'schooladmin{i:02d}', 'SCHOOL_ADMIN', f'schooladmin{i:02d}@example.com', first, last)
    sa, c = SchoolAdmin.objects.get_or_create(
        user=u,
        defaults={
            'full_name': full, 'email': f'schooladmin{i:02d}@example.com',
            'phone': f'900030000{i}', 'gender': 'female' if i % 2 else 'male',
            'school': schools[(i - 1) % len(schools)], 'account_status': 'active',
            'is_active': True, 'password_changed': True,
        },
    )
    bump('SchoolAdmin', c)

# ============================================================ CLASSES (unassigned coach)
# thinking_coach left NULL — assign from dashboard.
first_admin = SchoolAdmin.objects.first()
creator = first_admin.user if first_admin else User.objects.filter(role='SUPER_ADMIN').first()
for s in schools:
    for grade in ['5', '6', '7']:
        k, c = Class.objects.get_or_create(
            school=s, grade=grade, division='A', academic_year=AY,
            defaults={'class_name': f'Std {grade}A', 'is_active': True, 'created_by': creator},
        )
        bump('Class', c)

# ============================================================ STUDENTS (3 per school)
for si, s in enumerate(schools, start=1):
    for j in range(1, 4):
        gr = f'DGR{si}{j:02d}'
        u = mkuser(f'dstudent{si}{j:02d}', 'STUDENT', f'dstudent{si}{j:02d}@example.com', f'Stud{si}{j}', 'Dummy')
        st, c = Student.objects.get_or_create(
            gr_number=gr,
            defaults={
                'user': u, 'first_name': f'Stud{si}{j}', 'last_name': 'Dummy',
                'gender': 'male' if j % 2 else 'female', 'date_of_birth': dob(2013, 3, j),
                'nationality': 'Indian', 'school': s, 'school_name': s.school_name,
                'student_class': '6', 'division': 'A', 'roll_number': str(j),
                'academic_year': AY, 'school_board': 'CBSE',
                'school_email': f'dstudent{si}{j:02d}@example.com',
                'skill_lab_reg_id': f'DSL{si}{j:02d}', 'enrollment_date': dob(2025, 6, 1),
                'attendance_status': 'active',
                'emergency_name': 'Guardian', 'emergency_relationship': 'father',
                'emergency_mobile': f'90004{si}000{j}',
            },
        )
        bump('Student', c)

print("SEED_DUMMY_DONE created:", created)
print("Coaches available for assignment:", User.objects.filter(role='THINKING_COACH', is_active=True).count())
print("Schools:", School.objects.count(), "| Classes:", Class.objects.count())
