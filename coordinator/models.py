from django.db import models
from django.contrib.auth.hashers import make_password
from accounts.models import User
from schools.models import School


class ProgramCoordinator(models.Model):
    """
    Program Coordinator model for onboarding and managing coordinator information
    """
    
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-'),
    ]
    
    DESIGNATION_CHOICES = [
        ('Program Coordinator', 'Program Coordinator'),
        ('Project Coordinator', 'Project Coordinator'),
    ]
    
    SPECIALIZATION_CHOICES = [
        ('Operations', 'Operations'),
        ('Education', 'Education'),
        ('Project Management', 'Project Management'),
        ('Others', 'Others'),
    ]
    
    EMPLOYMENT_TYPE_CHOICES = [
        ('Full-time', 'Full-time'),
        ('Contract', 'Contract'),
        ('Consultant', 'Consultant'),
    ]
    
    WORK_STYLE_CHOICES = [
        ('Field', 'Field'),
        ('Remote', 'Remote'),
        ('Hybrid', 'Hybrid'),
    ]
    
    YES_NO_CHOICES = [
        ('Yes', 'Yes'),
        ('No', 'No'),
    ]
    
    VERIFICATION_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
    ]
    
    # Link to User model
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='program_coordinator', null=True, blank=True)
    
    # Basic Information
    profile_photo = models.ImageField(upload_to='coordinator/profile_photos/', blank=True, null=True)
    full_name = models.CharField(max_length=255)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    date_of_birth = models.DateField()
    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUP_CHOICES, blank=True, null=True)
    nationality = models.CharField(max_length=100, default='Indian')
    employee_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    aadhar_number = models.CharField(max_length=12, unique=True)
    pan_number = models.CharField(max_length=10, unique=True)
    
    # Professional Details
    designation = models.CharField(max_length=50, choices=DESIGNATION_CHOICES)
    qualification = models.CharField(max_length=255)
    specialization = models.CharField(max_length=50, choices=SPECIALIZATION_CHOICES)
    total_experience = models.CharField(max_length=100)
    program_management_exp = models.CharField(max_length=100, blank=True, null=True)
    education_exp = models.CharField(max_length=100, blank=True, null=True)
    previous_organizations = models.TextField(blank=True, null=True)
    languages_known = models.CharField(max_length=255)
    certifications = models.CharField(max_length=500, blank=True, null=True)
    resume = models.FileField(upload_to='coordinator/resumes/', blank=True, null=True)
    
    # Contact Information
    mobile_number = models.CharField(max_length=15)
    alternate_number = models.CharField(max_length=15, blank=True, null=True)
    official_email = models.EmailField(unique=True)
    personal_email = models.EmailField(blank=True, null=True)
    
    # Address Details
    current_address = models.TextField()
    permanent_address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    
    # Compliance & Documentation
    id_proof = models.CharField(max_length=50, blank=True, null=True)
    address_proof = models.CharField(max_length=50, blank=True, null=True)
    police_verification = models.CharField(max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='Pending')
    passport_photo_uploaded = models.CharField(max_length=5, choices=YES_NO_CHOICES, default='No')
    contract_uploaded = models.CharField(max_length=5, choices=YES_NO_CHOICES, default='No')
    pan_aadhar_linked = models.CharField(max_length=5, choices=YES_NO_CHOICES, default='No')
    nda_signed = models.CharField(max_length=5, choices=YES_NO_CHOICES, default='No')
    
    # Program & Work Assignment Details
    program_assigned = models.CharField(max_length=100, blank=True, null=True)
    zone_assigned = models.CharField(max_length=100, blank=True, null=True)
    schools_assigned = models.ManyToManyField(School, related_name='program_coordinators', blank=True)
    branch_region = models.CharField(max_length=100, blank=True, null=True)
    reporting_manager = models.CharField(max_length=255, blank=True, null=True)
    login_role = models.CharField(max_length=50, blank=True, null=True)
    joining_date = models.DateField()
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES)
    contract_start_date = models.DateField(blank=True, null=True)
    contract_end_date = models.DateField(blank=True, null=True)
    
    # Bank & Payroll Details (optional — org uses its own payroll system)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    branch_name = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    ifsc_code = models.CharField(max_length=11, blank=True, null=True)
    bank_proof = models.FileField(upload_to='coordinator/bank_proofs/', blank=True, null=True)
    
    # Additional Optional Data
    strength_areas = models.TextField(blank=True, null=True)
    hobbies = models.TextField(blank=True, null=True)
    work_style = models.CharField(max_length=20, choices=WORK_STYLE_CHOICES, blank=True, null=True)
    tools_comfortable = models.CharField(max_length=500, blank=True, null=True)
    achievements = models.TextField(blank=True, null=True)
    career_aspirations = models.TextField(blank=True, null=True)
    
    # Metadata
    is_active = models.BooleanField(default=True)
    last_password_change = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_coordinators')
    
    class Meta:
        verbose_name = 'Program Coordinator'
        verbose_name_plural = 'Program Coordinators'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.full_name} ({self.employee_id or 'No ID'})"
    
    def set_password(self, raw_password):
        """Set password for the linked user account"""
        if self.user:
            self.user.password = make_password(raw_password)
            self.user.save()
