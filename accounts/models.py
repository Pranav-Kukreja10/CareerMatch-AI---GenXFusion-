from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'STUDENT', 'Student / Candidate'
        CANDIDATE = 'CANDIDATE', 'Candidate / Job Seeker'
        RECRUITER = 'RECRUITER', 'Industry Recruiter'
        ACADEMIA = 'ACADEMIA', 'Academia Representative'
        COLLEGE_ADMIN = 'COLLEGE_ADMIN', 'College Administrator'
        ADMIN = 'ADMIN', 'System Administrator'

    class AuthProvider(models.TextChoices):
        LOCAL = 'LOCAL', 'Email & Password'
        GOOGLE = 'GOOGLE', 'Google OAuth2'
        GITHUB = 'GITHUB', 'GitHub OAuth2'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        help_text="Role classification to dictate portal workspace access"
    )
    auth_provider = models.CharField(
        max_length=20,
        choices=AuthProvider.choices,
        default=AuthProvider.LOCAL,
        help_text="Authentication identity provider"
    )
    provider_id = models.CharField(max_length=255, blank=True, null=True, help_text="External OAuth2 subject/user ID")
    avatar_url = models.URLField(max_length=500, blank=True, null=True, help_text="Profile picture from OAuth provider")
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    def is_student(self) -> bool:
        return self.role in [self.Role.STUDENT, self.Role.CANDIDATE]

    def is_candidate(self) -> bool:
        return self.role in [self.Role.STUDENT, self.Role.CANDIDATE]

    def is_recruiter(self) -> bool:
        return self.role == self.Role.RECRUITER

    def is_academia(self) -> bool:
        return self.role in [self.Role.ACADEMIA, self.Role.COLLEGE_ADMIN]

    def is_college_admin(self) -> bool:
        if self.role == self.Role.COLLEGE_ADMIN:
            return True
        if self.role == self.Role.ACADEMIA:
            fp = getattr(self, 'faculty_profile', None)
            return bool(fp and fp.is_institution_admin)
        return False

    is_email_verified = models.BooleanField(
        default=False,
        help_text="Designates whether the user has verified their email address"
    )

    class Meta:
        db_table = 'skillsetu_users'


class PasswordResetOTP(models.Model):
    email = models.EmailField(db_index=True)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'skillsetu_password_reset_otps'
        indexes = [
            models.Index(fields=['email', 'is_used', 'expires_at']),
        ]

    def __str__(self):
        return f"OTP for {self.email} (Used: {self.is_used})"


class EmailVerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_verifications')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = 'skillsetu_email_verification_tokens'
        indexes = [
            models.Index(fields=['token', 'is_used', 'expires_at']),
            models.Index(fields=['user', 'otp_code', 'is_used', 'expires_at']),
        ]

    def __str__(self):
        return f"Email Verification for {self.user.email} (Used: {self.is_used})"

