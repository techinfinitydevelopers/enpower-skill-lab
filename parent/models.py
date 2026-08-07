from django.db import models
from django.conf import settings
from student.models import Student


class Parent(models.Model):
    """
    Parent/Guardian model for onboarding and managing parent information
    """
    RELATION_CHOICES = [
        ('mother', 'Mother'),
        ('father', 'Father'),
        ('guardian', 'Guardian'),
    ]

    SECONDARY_RELATION_CHOICES = [
        ('mother', 'Mother'),
        ('father', 'Father'),
        ('guardian', 'Guardian'),
        ('grandparent', 'Grandparent'),
        ('uncle', 'Uncle'),
        ('aunt', 'Aunt'),
    ]

    EDUCATION_LEVEL_CHOICES = [
        ('high-school', 'High School'),
        ('diploma', 'Diploma'),
        ('graduate', 'Graduate'),
        ('post-graduate', 'Post Graduate'),
        ('doctorate', 'Doctorate'),
        ('other', 'Other'),
    ]

    PREFERRED_CONTACT_CHOICES = [
        ('primary', 'Primary Parent/Guardian'),
        ('secondary', 'Secondary Parent/Guardian'),
        ('both', 'Both'),
    ]

    CONTACT_METHOD_CHOICES = [
        ('call', 'Phone Call'),
        ('whatsapp', 'WhatsApp'),
        ('sms', 'SMS'),
        ('email', 'Email'),
    ]

    LANGUAGE_CHOICES = [
        ('english', 'English'),
        ('hindi', 'Hindi'),
        ('marathi', 'Marathi'),
        ('gujarati', 'Gujarati'),
        ('tamil', 'Tamil'),
        ('telugu', 'Telugu'),
        ('kannada', 'Kannada'),
        ('other', 'Other'),
    ]

    FEE_CATEGORY_CHOICES = [
        ('regular', 'Regular'),
        ('scholarship', 'Scholarship'),
        ('concession', 'Concession'),
    ]

    PAYMENT_MODE_CHOICES = [
        ('online', 'Online Payment'),
        ('bank-transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('cash', 'Cash'),
        ('upi', 'UPI'),
    ]

    EMERGENCY_RELATION_CHOICES = [
        ('grandparent', 'Grandparent'),
        ('uncle', 'Uncle'),
        ('aunt', 'Aunt'),
        ('sibling', 'Sibling'),
        ('neighbor', 'Neighbor'),
        ('family-friend', 'Family Friend'),
        ('other', 'Other'),
    ]

    MEETING_AVAILABILITY_CHOICES = [
        ('online', 'Online Only'),
        ('offline', 'Offline Only'),
        ('both', 'Both Online and Offline'),
        ('not-available', 'Not Available'),
    ]

    ACCOUNT_STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('inactive', 'Inactive'),
    ]

    # Parent ID (auto-generated)
    parent_id = models.CharField(max_length=30, unique=True, blank=True)

    # User Account Link
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='parent_profile')

    # A. Primary Parent / Guardian Details
    profile_photo = models.ImageField(upload_to='parents/photos/', blank=True, null=True)
    full_name = models.CharField(max_length=200)
    relation_to_student = models.CharField(max_length=20, choices=RELATION_CHOICES)
    mobile_number = models.CharField(max_length=15)
    alternate_mobile = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(unique=True)
    occupation = models.CharField(max_length=100, blank=True, null=True)
    organization = models.CharField(max_length=200, blank=True, null=True)
    education_level = models.CharField(max_length=20, choices=EDUCATION_LEVEL_CHOICES, blank=True, null=True)
    id_proof = models.CharField(max_length=20, blank=True, null=True)

    # B. Secondary Parent / Guardian
    secondary_full_name = models.CharField(max_length=200, blank=True, null=True)
    secondary_relation = models.CharField(max_length=20, choices=SECONDARY_RELATION_CHOICES, blank=True, null=True)
    secondary_mobile = models.CharField(max_length=15, blank=True, null=True)
    secondary_email = models.EmailField(blank=True, null=True)
    secondary_occupation = models.CharField(max_length=100, blank=True, null=True)
    preferred_contact = models.CharField(max_length=20, choices=PREFERRED_CONTACT_CHOICES, default='primary')

    # C. Contact & Address
    residential_address = models.TextField()
    landmark = models.CharField(max_length=200, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pin_code = models.CharField(max_length=6)
    permanent_address = models.TextField(blank=True, null=True)

    # D. Communication Preferences
    contact_method = models.CharField(max_length=20, choices=CONTACT_METHOD_CHOICES, default='whatsapp')
    preferred_language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default='english')
    dnd_timings = models.CharField(max_length=100, blank=True, null=True)
    whatsapp_consent = models.BooleanField(default=True)
    photo_consent = models.BooleanField(default=True)

    # E. Financial & Administrative
    fee_category = models.CharField(max_length=20, choices=FEE_CATEGORY_CHOICES, default='regular')
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, blank=True, null=True)
    billing_email = models.EmailField(blank=True, null=True)
    gst_number = models.CharField(max_length=20, blank=True, null=True)

    # F. Emergency Contacts
    emergency_name = models.CharField(max_length=100)
    emergency_relation = models.CharField(max_length=20, choices=EMERGENCY_RELATION_CHOICES)
    emergency_phone = models.CharField(max_length=15)
    emergency_address = models.TextField(blank=True, null=True)

    # G. Parent Involvement
    meeting_availability = models.CharField(max_length=20, choices=MEETING_AVAILABILITY_CHOICES, blank=True, null=True)
    volunteer_interest = models.CharField(max_length=10, blank=True, null=True)
    parent_skills = models.TextField(blank=True, null=True)

    # Linked Students (Many-to-Many relationship)
    students = models.ManyToManyField(Student, related_name='parents', blank=True)

    # Account Status
    account_status = models.CharField(max_length=20, choices=ACCOUNT_STATUS_CHOICES, default='pending')

    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='parents_created')

    class Meta:
        db_table = 'parents'
        verbose_name = 'Parent'
        verbose_name_plural = 'Parents'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} - {self.parent_id}"

    def save(self, *args, **kwargs):
        if not self.parent_id:
            import random
            import string
            self.parent_id = 'P' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        super().save(*args, **kwargs)

    @property
    def initials(self):
        """Get initials from full name"""
        words = self.full_name.strip().split()
        if len(words) >= 2:
            return (words[0][0] + words[1][0]).upper()
        return self.full_name[:2].upper()

    @property
    def children_names(self):
        """Get comma-separated list of children names"""
        return ', '.join([s.full_name for s in self.students.all()])

    @property
    def children_grades(self):
        """Get comma-separated list of children grades"""
        return ', '.join([f"Grade {s.student_class}" for s in self.students.all()])
