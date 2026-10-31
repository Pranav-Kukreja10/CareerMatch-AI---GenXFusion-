from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from pgvector.django import VectorField, HnswIndex

class IndustrySector(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="e.g. IT, Mechanical, Finance")
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'skillsetu_industry_sectors'
        
    def __str__(self):
        return self.name

class JobBenchmark(models.Model):
    sector = models.ForeignKey(IndustrySector, on_delete=models.CASCADE, related_name="benchmarks")
    role_title = models.CharField(max_length=100, unique=True, help_text="e.g. Backend Engineer, CAD Designer")
    
    # Required skills lists mapped directly to native JSONB fields in PostgreSQL
    core_skills = models.JSONField(default=list, help_text="List of mandatory core skills")
    methodology_skills = models.JSONField(default=list, help_text="List of methodology/architectural practices")
    tooling_skills = models.JSONField(default=list, help_text="List of tools/software utilities")

    class Meta:
        db_table = 'skillsetu_job_benchmarks'

    def __str__(self):
        return f"{self.role_title} ({self.sector.name})"

class StudentProfile(models.Model):
    class PlacementStatus(models.TextChoices):
        UNPLACED = 'UNPLACED', 'Unplaced'
        PLACED = 'PLACED', 'Placed'
        OPEN_TO_INTERN = 'OPEN_TO_INTERN', 'Open to Internships'

    class NHEQFLevel(models.TextChoices):
        LEVEL_4_5 = 'LEVEL_4_5', 'NHEQF Level 4.5: UG Certificate (Year 1 Exit)'
        LEVEL_5_0 = 'LEVEL_5_0', 'NHEQF Level 5.0: UG Diploma (Year 2 Exit)'
        LEVEL_5_5 = 'LEVEL_5_5', 'NHEQF Level 5.5: Bachelor Degree 3-Year'
        LEVEL_6_0 = 'LEVEL_6_0', 'NHEQF Level 6.0: Bachelor Degree 4-Year / Honours'
        LEVEL_6_5 = 'LEVEL_6_5', 'NHEQF Level 6.5: Post-Graduate Diploma / Honours with Research'
        LEVEL_7_0 = 'LEVEL_7_0', 'NHEQF Level 7.0: Master Degree (M.Tech, MBA, M.Com, M.Des)'
        LEVEL_8_0 = 'LEVEL_8_0', 'NHEQF Level 8.0: Doctoral / Ph.D.'

    class InstitutionStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending College Admin Approval'
        APPROVED = 'APPROVED', 'Enrolled & Verified by College'
        REJECTED = 'REJECTED', 'Registration Rejected by College'
        UNATTACHED = 'UNATTACHED', 'Unattached / Independent Candidate'

    class Gender(models.TextChoices):
        FEMALE = 'FEMALE', 'Female'
        MALE = 'MALE', 'Male'
        NON_BINARY = 'NON_BINARY', 'Non-Binary'
        PREFER_NOT_TO_SAY = 'PREFER_NOT_TO_SAY', 'Prefer not to say'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_profile')
    title = models.CharField(max_length=20, blank=True, default='', help_text="Professional title or honorific (e.g. Mr., Ms., Eng., Prof.)")
    honorific = models.CharField(max_length=20, blank=True, default='', help_text="Alias for title")
    github_handle = models.CharField(max_length=255, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)

    # Demographic attributes for affirmative action & government scheme matching
    gender = models.CharField(
        max_length=20,
        choices=Gender.choices,
        default=Gender.PREFER_NOT_TO_SAY,
        blank=True,
        help_text="Self-identified gender for demographic opportunity matching and affirmative action schemes"
    )

    # Granular profile personalisation & notification preferences
    preferences = models.JSONField(
        default=dict,
        blank=True,
        help_text="Granular feature and notification toggles: notifications, features, and privacy preferences"
    )
    
    # Store multi-dimensional skills with AI-graded evidence weights
    skills_matrix = models.JSONField(default=dict, blank=True)
    projects = models.JSONField(default=list, blank=True)
    
    # Multi-Role Fitment Score Matrix (e.g. {"Backend Engineer": {"score": 85, "fit_level": "High Match"}})
    role_fit_matrix = models.JSONField(default=dict, blank=True)
    
    placement_status = models.CharField(
        max_length=20,
        choices=PlacementStatus.choices,
        default=PlacementStatus.UNPLACED
    )
    
    # Target job roles candidate is seeking (e.g. ['Backend Engineer', 'DevOps Engineer'])
    target_roles = models.JSONField(default=list, blank=True, help_text="Target job roles candidate is seeking")
    
    # Data Provenance: Preserved un-normalized raw string identifiers extracted directly from candidate resume
    raw_extracted_skills = models.JSONField(default=list, blank=True, help_text="Preserved raw resume string identifiers")
    
    # Institutional attributes for academic faculty reporting
    institution = models.CharField(max_length=255, blank=True, default='', help_text="College or University name")
    institution_ref_id = models.IntegerField(null=True, blank=True, db_column='institution_ref_id')
    institution_status = models.CharField(
        max_length=20,
        choices=InstitutionStatus.choices,
        default=InstitutionStatus.APPROVED,
        db_index=True,
        help_text="Approval/enrollment status by the designated College Administrator"
    )
    institution_approved_at = models.DateTimeField(null=True, blank=True)
    institution_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_student_enrollments'
    )
    institution_rejection_reason = models.TextField(blank=True, default='')
    department = models.CharField(max_length=150, blank=True, default='', help_text="Academic department/branch (e.g. Computer Science, Mechanical)")
    degree = models.CharField(max_length=100, blank=True, default='', help_text="Academic degree e.g. B.Tech, B.S., M.S.")
    cgpa = models.FloatField(null=True, blank=True, help_text="Cumulative Grade Point Average (0.0 - 10.0)")
    graduation_year = models.IntegerField(null=True, blank=True, help_text="Graduation Year e.g. 2026")

    # NEP 2020 National Credit Framework (NCrF) & Academic Bank of Credits (ABC) Attributes
    apaar_id = models.CharField(
        max_length=20,
        blank=True,
        default='',
        help_text="12-digit One Nation One Student ID (APAAR/ABC, e.g. '9823-4412-8901')"
    )
    abc_id = models.CharField(
        max_length=25,
        blank=True,
        default='',
        help_text="Academic Bank of Credits account ID (e.g. 'ABC-782-901-44')"
    )
    minor_specialization = models.CharField(
        max_length=150,
        blank=True,
        default='',
        help_text="NEP 2020 Multidisciplinary Minor (e.g. Data Analytics, FinTech, UI/UX, Business Analysis)"
    )
    nheqf_level = models.CharField(
        max_length=25,
        choices=NHEQFLevel.choices,
        default='',
        blank=True,
        help_text="National Higher Education Qualifications Framework level"
    )

    # Candidate professional experience & current designation
    current_designation = models.CharField(max_length=150, blank=True, default='', help_text="Current or most recent professional role (e.g. Senior Accountant, UI Designer)")
    experience_years = models.FloatField(default=0.0, blank=True, help_text="Total years of work experience (0 for students/freshers)")

    # Social & portfolio URLs
    github_url = models.URLField(max_length=500, blank=True, default='', help_text="GitHub profile URL")
    linkedin_url = models.URLField(max_length=500, blank=True, default='', help_text="LinkedIn profile URL")
    portfolio_url = models.URLField(max_length=500, blank=True, default='', help_text="Personal portfolio or website URL")

    # GitHub Engineering & Anti-Vibe-Coding Screening Radar
    github_metrics = models.JSONField(
        default=dict,
        blank=True,
        help_text="Analyzed GitHub signals: engineering_score, anti_vibe_index, CI/CD, tests, conventional commits, top repos"
    )
    github_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of latest GitHub profile screening"
    )

    # Structured industry certifications & credentials
    certifications = models.JSONField(
        default=list,
        blank=True,
        help_text="Industry certifications: [{'name': '...', 'issuer': '...', 'issue_year': 2024, 'credential_url': '...', 'skills_covered': []}]"
    )

    # Structured 4-tier skill categorization (technical_skills, frameworks, tools, soft_skills)
    skills_categorized = models.JSONField(
        default=dict,
        blank=True,
        help_text="Categorized skills: {'technical_skills': [], 'frameworks': [], 'tools': [], 'soft_skills': []}"
    )

    # PS Requirement: Digital Portfolio - Verified Internships & Experience
    internships = models.JSONField(
        default=list,
        blank=True,
        help_text="Completed internships: [{'company': '...', 'role': '...', 'duration': '...', 'mentor_feedback': '...', 'mentor_rating': 4.5, 'certificate_url': '...'}]"
    )

    # PS Requirement: Digital Portfolio - Verified Achievements & Honors
    achievements = models.JSONField(
        default=list,
        blank=True,
        help_text="Hackathons, awards, honors, publications: [{'title': '...', 'issuer': '...', 'year': 2024, 'description': '...'}]"
    )

    # PS Requirement: Academic Records & Transcripts
    academic_records = models.JSONField(
        default=list,
        blank=True,
        help_text="Semester GPA records & academic transcripts: [{'semester': 1, 'sgpa': 8.8, 'credits': 24}]"
    )
    
    overall_confidence_score = models.FloatField(default=0.0)
    profile_strength_score = models.FloatField(default=0.0, blank=True, help_text="Calculated profile strength score (0-100) based on 45/30/15/10 industry weighting")
    is_verified = models.BooleanField(default=False)

    # Assigned Faculty Mentor for clinical sign-offs & academic oversight
    assigned_mentor_id = models.IntegerField(null=True, blank=True, db_column='assigned_mentor_id')

    # Pending mentor assignment request (student-requested, awaiting HOD approval)
    mentor_request_pending_id = models.IntegerField(null=True, blank=True, db_column='mentor_request_pending_id')

    # Denormalized text corpus & 384-dim BGE dense embedding for hybrid search
    search_corpus = models.TextField(blank=True, default='')
    embedding = VectorField(dimensions=384, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'skillsetu_student_profiles'
        indexes = [
            HnswIndex(
                name='student_profile_hnsw_idx',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_cosine_ops'],
            ),
        ]

    def get_preferences(self) -> dict:
        defaults = {
            "common": {
                "theme": "system",
                "language": "en",
                "timezone": "Asia/Kolkata",
                "email_alerts": True,
                "in_app_alerts": True,
                "high_contrast": False,
                "reduce_motion": False,
            },
            "notifications": {
                "opportunity_alerts": True,
                "deadline_reminders": True,
                "scheme_alerts": True,
                "application_status_updates": True,
            },
            "features": {
                "show_affirmative_action_schemes": True,
                "show_diversity_job_badges": True,
                "smart_roadmap_recommendations": True,
                "reverse_matching_radar": True,
            },
            "privacy": {
                "participate_in_diversity_hiring": True,
                "share_profile_with_verified_recruiters": True,
                "auto_share_github_verified_badge": True,
                "allow_digilocker_credit_sharing": True,
            },
            "career_discovery": {
                "preferred_work_arrangement": "ALL",  # ALL, REMOTE, HYBRID, ON_SITE
                "minimum_desired_stipend_or_ctc": "",
                "target_domains": [],
            }
        }
        current = self.preferences or {}
        merged = {}
        for section, sec_defaults in defaults.items():
            merged[section] = {**sec_defaults, **current.get(section, {})}
        return merged

    def calculate_ncrf_credits(self) -> dict:
        """
        National Credit Framework (NCrF) Credit Calculator (NEP 2020 Mandate):
        - 1 Academic Credit = ~30 learning/practical training hours.
        - 4-week verified internship (80-120 hrs) = 2 NCrF Credits.
        - 8-week verified internship (160-240 hrs) = 4 NCrF Credits.
        - 12-week verified internship (240+ hrs) = 6 NCrF Credits.
        - Verified Industry Certification = 1 NCrF Credit.
        """
        internships_list = self.internships or []
        internship_credits = 0
        total_internship_hours = 0

        for intern in internships_list:
            hours = intern.get("hours_worked") or intern.get("hours_logged") or 0
            duration_str = str(intern.get("duration", "")).lower()
            
            if hours > 0:
                intern_creds = max(1, int(hours / 30))
                internship_credits += intern_creds
                total_internship_hours += hours
            elif "12 week" in duration_str or "3 month" in duration_str:
                internship_credits += 6
                total_internship_hours += 240
            elif "8 week" in duration_str or "2 month" in duration_str:
                internship_credits += 4
                total_internship_hours += 160
            elif "6 week" in duration_str:
                internship_credits += 3
                total_internship_hours += 120
            elif "4 week" in duration_str or "1 month" in duration_str:
                internship_credits += 2
                total_internship_hours += 80
            else:
                internship_credits += 2
                total_internship_hours += 80

        certs_count = len(self.certifications or [])
        certification_credits = certs_count * 1
        total_credits = internship_credits + certification_credits

        return {
            "total_ncrf_credits": total_credits,
            "internship_credits": internship_credits,
            "certification_credits": certification_credits,
            "total_internship_hours": total_internship_hours
        }

    def calculate_aicte_activity_points(self) -> dict:
        """
        AICTE Internship & Activity Points Calculator:
        - AICTE mandates 75 - 100 Activity Points for undergraduate degree qualification.
        - 40 hours of verified internship / field innovation = 10 Activity Points.
        - Capped at maximum 100 points.
        """
        ncrf = self.calculate_ncrf_credits()
        hours = ncrf["total_internship_hours"]
        points = min(100, (hours // 40) * 10)
        target = 100
        pct = round((points / target) * 100, 1)

        return {
            "points_earned": points,
            "target_points": target,
            "completion_percentage": pct,
            "verified_hours": hours,
            "is_target_met": points >= 75
        }

    def get_parakh_holistic_assessment(self) -> dict:
        """
        PARAKH (NEP 2020 Clause 4.35) 360-Degree Holistic Competency Assessment:
        Multidimensional assessment covering Cognitive, Practical, Vocational, and Academic domains.
        """
        from students.services import compute_profile_strength
        p_overall, breakdown = compute_profile_strength(self)

        grade = "Exemplary (A+)" if p_overall >= 80 else ("Proficient (A)" if p_overall >= 65 else "Developing (B)")

        return {
            "overall_holistic_score": p_overall,
            "parakh_grade": grade,
            "cognitive_domain_score": breakdown.get("cognitive_score", 0.0),
            "practical_domain_score": breakdown.get("projects_experience_score", 0.0),
            "vocational_domain_score": breakdown.get("certifications_score", 0.0),
            "academic_domain_score": breakdown.get("academics_score", 0.0),
            "parakh_standard": "National Assessment Centre (PARAKH) NEP 2020 Framework"
        }

    def get_nep_passport(self) -> dict:
        """Assembles the complete NEP 2020 Academic & Credit Passport."""
        ncrf = self.calculate_ncrf_credits()
        aicte = self.calculate_aicte_activity_points()
        parakh = self.get_parakh_holistic_assessment()

        clean_apaar = (self.apaar_id or "").replace("-", "").strip()
        is_apaar_valid = bool(clean_apaar and len(clean_apaar) == 12 and clean_apaar.isdigit())

        return {
            "apaar_id": self.apaar_id or None,
            "abc_id": self.abc_id or None,
            "is_apaar_verified": is_apaar_valid,
            "nheqf_level": self.nheqf_level or None,
            "nheqf_level_display": (self.get_nheqf_level_display() if hasattr(self, 'get_nheqf_level_display') else self.nheqf_level) if self.nheqf_level else None,
            "major_degree": self.degree or None,
            "minor_specialization": self.minor_specialization or None,
            "ncrf_credits": ncrf,
            "aicte_activity_points": aicte,
            "parakh_assessment": parakh
        }

    def get_github_radar(self) -> dict:
        """
        Returns structured GitHub Engineering Radar for Digital Portfolio.
        """
        metrics = self.github_metrics or {}
        if not metrics:
            handle = self.github_handle or (self.github_url.rstrip('/').split('/')[-1] if self.github_url else '')
            return {
                "github_handle": handle or "",
                "is_screened": False,
                "is_presentation_fallback": False,
                "engineering_score": 0.0,
                "anti_vibe_index": 0.0,
                "badge": "Unscreened",
                "summary": "GitHub profile has not been screened yet. Click 'Sync GitHub' to evaluate repositories and commit hygiene.",
                "public_repos_count": 0,
                "total_stars": 0,
                "total_commits_analyzed": 0,
                "conventional_commits_pct": 0.0,
                "has_ci_cd": False,
                "has_docker": False,
                "has_tests": False,
                "has_linter": False,
                "top_languages": [],
                "top_repositories": [],
                "synergy_skills_verified": [],
                "synced_at": None
            }
        return metrics

    def __str__(self):
        return f"{self.user.username}'s Profile"

class Notification(models.Model):
    class NotificationType(models.TextChoices):
        STATUS_CHANGE = 'STATUS_CHANGE', 'Status Change'
        INTERVIEW_SCHEDULED = 'INTERVIEW_SCHEDULED', 'Interview Scheduled'
        NEW_OPPORTUNITY = 'NEW_OPPORTUNITY', 'New Opportunity'
        DEADLINE_APPROACHING = 'DEADLINE_APPROACHING', 'Deadline Approaching'
        APPLICATION_REVIEW = 'APPLICATION_REVIEW', 'Application Review'
        NEW_SCHEME = 'NEW_SCHEME', 'New Government / Diversity Scheme'
        CLINICAL_SIGNOFF_REQUEST = 'CLINICAL_SIGNOFF_REQUEST', 'Clinical Sign-Off Request'
        EMAIL_VERIFICATION = 'EMAIL_VERIFICATION', 'Email Verification'
        MENTOR_ALLOCATED = 'MENTOR_ALLOCATED', 'Mentor Allocated'
        MENTOR_REQUEST = 'MENTOR_REQUEST', 'Mentor Assignment Request'
        ENROLLMENT_REQUEST = 'ENROLLMENT_REQUEST', 'Student Enrollment Request'
        ENROLLMENT_APPROVED = 'ENROLLMENT_APPROVED', 'Enrollment Approved'
        ENROLLMENT_REJECTED = 'ENROLLMENT_REJECTED', 'Enrollment Rejected'
        SYSTEM = 'SYSTEM', 'System Alert'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=35,
        choices=NotificationType.choices,
        default=NotificationType.STATUS_CHANGE
    )
    related_application_id = models.IntegerField(null=True, blank=True)
    related_listing_id = models.IntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'skillsetu_notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.title} [{self.notification_type}]"


class GovernmentScheme(models.Model):
    """
    Universal Multi-Domain Government & Affirmative Action Schemes
    Empowers candidates (especially women in STEM, finance, management, design)
    with direct portal access, verified grants, scholarships, and corporate DEI initiatives.
    """
    class Domain(models.TextChoices):
        CLINICAL = 'CLINICAL', 'Clinical Medicine & Panchakarma'
        RESEARCH = 'RESEARCH', 'Applied Research & Fellowships'
        PHARMA = 'PHARMA', 'Dravyaguna & Herbal Pharmaceutics'
        WELLNESS = 'WELLNESS', 'Swasthavritta & Yoga Wellness'
        MANAGEMENT = 'MANAGEMENT', 'Technology & Industry Administration'
        ALL = 'ALL', 'All Engineering & Cross-Domain Disciplines'
        # Backward compatibility aliases
        TECH = 'TECH', 'Applied Research & Technology'
        FINANCE = 'FINANCE', 'Ayush Trade & Economics'
        DESIGN = 'DESIGN', 'Ayush Formulation Design'

    class SchemeType(models.TextChoices):
        SCHOLARSHIP = 'SCHOLARSHIP', 'Scholarship & Financial Aid'
        INTERNSHIP = 'INTERNSHIP', 'Corporate Diversity Internship'
        MENTORSHIP = 'MENTORSHIP', 'Mentorship & Upskilling'
        RESEARCH_GRANT = 'RESEARCH_GRANT', 'Research Grant / Fellowship'
        INNOVATION_CHALLENGE = 'INNOVATION_CHALLENGE', 'Innovation Challenge / Hackathon'

    class TargetGender(models.TextChoices):
        FEMALE_ONLY = 'FEMALE_ONLY', 'Women / Female Candidates'
        ALL = 'ALL', 'All Eligible Candidates'

    class SchemeStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active / Open for Application'
        UPCOMING = 'UPCOMING', 'Upcoming'
        EXPIRED = 'EXPIRED', 'Application Closed'

    title = models.CharField(max_length=255)
    sponsoring_agency = models.CharField(max_length=255, help_text="e.g. AICTE / Ministry of Education, Amazon India, ICICI Bank")
    domain = models.CharField(max_length=30, choices=Domain.choices, default=Domain.ALL)
    scheme_type = models.CharField(max_length=30, choices=SchemeType.choices, default=SchemeType.SCHOLARSHIP)
    target_gender = models.CharField(max_length=20, choices=TargetGender.choices, default=TargetGender.FEMALE_ONLY)
    benefit_summary = models.CharField(max_length=255, help_text="e.g. INR 50,000/year + Tuition Waiver")
    description = models.TextField(help_text="Full program guidelines, eligibility, and deliverables")
    eligible_degrees = models.JSONField(default=list, blank=True, help_text="e.g. ['B.Tech', 'BCA', 'B.Com', 'MBA', 'B.Des']")
    min_cgpa = models.FloatField(null=True, blank=True)
    application_deadline = models.DateTimeField(null=True, blank=True)
    official_portal_url = models.URLField(max_length=500, help_text="Official portal or registration URL")
    status = models.CharField(max_length=20, choices=SchemeStatus.choices, default=SchemeStatus.ACTIVE)
    badge_color = models.CharField(max_length=30, default="purple", help_text="UI badge accent color")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'skillsetu_government_schemes'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} [{self.domain}] ({self.status})"

class TestSession(models.Model):
    student_profile = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="test_sessions")
    target_role = models.CharField(max_length=100)
    questions_data = models.JSONField(help_text="Stores the full generated test, correct answers, and rubrics")
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'skillsetu_test_sessions'

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_student_profile(sender, instance, created, **kwargs):
    if created and instance.role in ['STUDENT', 'CANDIDATE']:
        StudentProfile.objects.get_or_create(user=instance)


