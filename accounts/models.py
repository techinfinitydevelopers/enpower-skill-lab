from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = [
        ('SUPER_ADMIN', 'Super Admin'),
        ('PROGRAM_COORDINATOR', 'Program Coordinator'),
        ('SCHOOL_ADMIN', 'School Admin'),
        ('THINKING_COACH', 'Thinking Coach'),
        ('PARENT', 'Parent'),
        ('STUDENT', 'Student'),
    ]

    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    
    # Additional fields for all users
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        verbose_name="Phone Number",
        help_text="Contact phone number"
    )
    
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        blank=True,
        null=True,
        verbose_name="Profile Picture"
    )

    def __str__(self):
        return f"{self.username} ({self.role})"
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"


class LoginAttempt(models.Model):
    """One failed sign-in.

    Rows are only written on failure and are deleted the moment the right
    password arrives, so this is a short-lived counter rather than a log. See
    accounts/throttle.py for why it lives in the database and not the cache.
    """

    username   = models.CharField(max_length=150, db_index=True)
    ip_address = models.CharField(max_length=45, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Login Attempt"
        verbose_name_plural = "Login Attempts"
        indexes = [models.Index(fields=['username', 'ip_address', 'created_at'])]

    def __str__(self):
        return f"{self.username} from {self.ip_address} at {self.created_at:%Y-%m-%d %H:%M}"

