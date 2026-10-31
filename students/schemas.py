from ninja import Schema
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- PHASE 1 & 2 SCHEMAS (Resume Upload, Review & Profile) ---

class ResumeUploadOutSchema(Schema):
    success: bool
    message: str
    raw_text: str

class ResumeAnalysisInSchema(Schema):
    raw_text: str

class CertificationSchema(Schema):
    name: str
    issuer: Optional[str] = ""
    issue_year: Optional[int] = None
    credential_url: Optional[str] = ""
    skills_covered: List[str] = []

class ProfileStrengthBreakdownSchema(Schema):
    cognitive_score: float = 0.0
    projects_experience_score: float = 0.0
    certifications_score: float = 0.0
    academics_score: float = 0.0

class ResumePreviewOutSchema(Schema):
    success: bool
    raw_text: str
    current_designation: Optional[str] = ""
    experience_years: Optional[float] = 0.0
    academic_credentials: Dict[str, Any] = {}
    skills_categorized: Dict[str, List[str]] = {}
    skills_matrix: Dict[str, Any] = {}
    projects: List[Dict[str, Any]] = []
    certifications: List[Dict[str, Any]] = []
    target_roles: List[str] = []
    social_links: Dict[str, str] = {}

# --- GRANULAR PREFERENCES & PERSONALISATION SCHEMAS ---

class CommonPreferencesSchema(Schema):
    theme: str = "system"  # system, light, dark
    language: str = "en"
    timezone: str = "Asia/Kolkata"
    email_alerts: bool = True
    in_app_alerts: bool = True
    high_contrast: bool = False
    reduce_motion: bool = False

class NotificationPreferencesSchema(Schema):
    opportunity_alerts: bool = True
    deadline_reminders: bool = True
    scheme_alerts: bool = True
    application_status_updates: bool = True

class FeaturePreferencesSchema(Schema):
    show_affirmative_action_schemes: bool = True
    show_diversity_job_badges: bool = True
    smart_roadmap_recommendations: bool = True
    reverse_matching_radar: bool = True

class PrivacyPreferencesSchema(Schema):
    participate_in_diversity_hiring: bool = True
    share_profile_with_verified_recruiters: bool = True
    auto_share_github_verified_badge: bool = True
    allow_digilocker_credit_sharing: bool = True

class CareerDiscoveryPreferencesSchema(Schema):
    preferred_work_arrangement: str = "ALL"  # ALL, REMOTE, HYBRID, ON_SITE
    minimum_desired_stipend_or_ctc: str = ""
    target_domains: List[str] = []

class StudentPreferencesSchema(Schema):
    common: CommonPreferencesSchema = CommonPreferencesSchema()
    notifications: NotificationPreferencesSchema = NotificationPreferencesSchema()
    features: FeaturePreferencesSchema = FeaturePreferencesSchema()
    privacy: PrivacyPreferencesSchema = PrivacyPreferencesSchema()
    career_discovery: CareerDiscoveryPreferencesSchema = CareerDiscoveryPreferencesSchema()

class StudentPreferencesUpdateIn(Schema):
    common: Optional[Dict[str, Any]] = None
    notifications: Optional[Dict[str, Any]] = None
    features: Optional[Dict[str, Any]] = None
    privacy: Optional[Dict[str, Any]] = None
    career_discovery: Optional[Dict[str, Any]] = None

class StudentProfileInSchema(Schema):
    username: Optional[str] = None
    title: Optional[str] = ""
    honorific: Optional[str] = ""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    gender: Optional[str] = None
    current_designation: Optional[str] = None
    experience_years: Optional[float] = None
    institution: Optional[str] = None
    department: Optional[str] = None
    degree: Optional[str] = None
    cgpa: Optional[float] = None
    graduation_year: Optional[int] = None
    github_handle: Optional[str] = None
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    certifications: Optional[List[Dict[str, Any]]] = None
    skills_matrix: Optional[Dict[str, Any]] = None
    skills_categorized: Optional[Dict[str, Any]] = None
    target_roles: Optional[List[str]] = None
    projects: Optional[List[Dict[str, Any]]] = None
    internships: Optional[List[Dict[str, Any]]] = None
    achievements: Optional[List[Dict[str, Any]]] = None
    academic_records: Optional[List[Dict[str, Any]]] = None
    placement_status: Optional[str] = "UNPLACED"
    preferences: Optional[Dict[str, Any]] = None
    apaar_id: Optional[str] = None
    abc_id: Optional[str] = None
    minor_specialization: Optional[str] = None
    nheqf_level: Optional[str] = None

class StudentProfileOutSchema(Schema):
    id: int
    username: str
    email: str
    title: Optional[str] = ""
    honorific: Optional[str] = ""
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    avatar_url: Optional[str] = ""
    gender: str = "PREFER_NOT_TO_SAY"
    bio: Optional[str] = None
    current_designation: Optional[str] = ""
    experience_years: Optional[float] = 0.0
    institution: Optional[str] = ""
    institution_status: Optional[str] = "UNATTACHED"
    institution_rejection_reason: Optional[str] = ""
    institution_id: Optional[int] = None
    institution_name: Optional[str] = ""
    department: Optional[str] = ""
    degree: Optional[str] = ""
    cgpa: Optional[float] = None
    graduation_year: Optional[int] = None
    apaar_id: Optional[str] = None
    abc_id: Optional[str] = None
    minor_specialization: Optional[str] = None
    nheqf_level: str = "LEVEL_6_0"
    github_handle: Optional[str] = None
    github_url: Optional[str] = ""
    linkedin_url: Optional[str] = ""
    portfolio_url: Optional[str] = ""
    certifications: List[Dict[str, Any]] = []
    projects: List[Dict[str, Any]] = []
    internships: List[Dict[str, Any]] = []
    achievements: List[Dict[str, Any]] = []
    academic_records: List[Dict[str, Any]] = []
    skills_matrix: Dict[str, Any] = {}
    skills_categorized: Dict[str, Any] = {}
    raw_extracted_skills: List[str] = []
    role_fit_matrix: Dict[str, Any] = {}
    target_roles: List[str] = []
    placement_status: str
    overall_confidence_score: float
    profile_strength_score: float = 0.0
    profile_strength_breakdown: Optional[ProfileStrengthBreakdownSchema] = None
    is_verified: bool
    preferences: Dict[str, Any] = {}
    github_metrics: Optional[Dict[str, Any]] = None
    github_synced_at: Optional[str] = None
    semantic_bridges: List[Dict[str, str]] = []

# --- NEP 2020 ACADEMIC CREDIT PASSPORT & PARAKH SCHEMAS ---

class NCRFCreditsBreakdownSchema(Schema):
    total_ncrf_credits: int
    internship_credits: int
    certification_credits: int
    total_internship_hours: int

class AICTEActivityPointsSchema(Schema):
    points_earned: int
    target_points: int = 100
    completion_percentage: float
    verified_hours: int
    is_target_met: bool

class PARAKHAssessmentSchema(Schema):
    overall_holistic_score: float
    parakh_grade: str
    cognitive_domain_score: float
    practical_domain_score: float
    vocational_domain_score: float
    academic_domain_score: float
    parakh_standard: str

class NEPPassportOutSchema(Schema):
    apaar_id: Optional[str] = None
    abc_id: Optional[str] = None
    is_apaar_verified: bool = False
    nheqf_level: str = "LEVEL_6_0"
    nheqf_level_display: Optional[str] = None
    major_degree: str = "General Studies"
    minor_specialization: Optional[str] = None
    ncrf_credits: NCRFCreditsBreakdownSchema
    aicte_activity_points: AICTEActivityPointsSchema
    parakh_assessment: PARAKHAssessmentSchema

class NEPTranscriptOutSchema(Schema):
    transcript_id: str
    apaar_id: str
    abc_id: str
    student_name: str
    institution: str
    degree_major: str
    minor_specialization: Optional[str] = None
    nheqf_level: str
    ncrf_credits_earned: int
    aicte_activity_points: int
    parakh_holistic_grade: str
    parakh_holistic_score: float
    verified_internship_records: List[Dict[str, Any]] = []
    verified_certifications: List[Dict[str, Any]] = []
    digilocker_verification_status: str = "AUTHENTIC_VERIFIED"
    digilocker_sha256_hash: str
    issued_at: str

# --- DIGITAL PORTFOLIO & INTERNSHIP MILESTONE SCHEMAS (PS REQUIREMENT) ---

class AchievementItemSchema(Schema):
    title: str
    issuer: Optional[str] = ""
    year: Optional[int] = None
    description: Optional[str] = ""
    proof_url: Optional[str] = ""

class AchievementsUpdateInSchema(Schema):
    achievements: List[AchievementItemSchema]

# --- GITHUB SCREENING & ANTI-VIBE-CODING RADAR SCHEMAS ---

class GitHubRepositoryDetailSchema(Schema):
    name: str
    description: Optional[str] = ""
    stars: int = 0
    forks: int = 0
    languages: List[str] = []
    has_ci_cd: bool = False
    has_docker: bool = False
    has_tests: bool = False
    has_linter: bool = False
    has_readme: bool = True
    relevance_tier: str = "SHOWCASE"
    is_academic: bool = False
    is_dormant: bool = False
    is_eligible_for_viva: bool = True
    is_selected_for_test: bool = True
    relevance_reason: Optional[str] = ""
    html_url: str

class GitHubRadarOutSchema(Schema):
    github_handle: str
    is_screened: bool = False
    is_presentation_fallback: bool = False
    engineering_score: float = 0.0
    anti_vibe_index: float = 0.0
    badge: Optional[str] = "Unscreened"
    summary: Optional[str] = ""
    public_repos_count: int = 0
    total_stars: int = 0
    total_commits_analyzed: int = 0
    conventional_commits_pct: float = 0.0
    has_ci_cd: bool = False
    has_docker: bool = False
    has_tests: bool = False
    has_linter: bool = False
    top_languages: List[str] = []
    top_repositories: List[GitHubRepositoryDetailSchema] = []
    synergy_skills_verified: List[str] = []
    synced_at: Optional[str] = None

class GitHubSyncInSchema(Schema):
    github_handle: Optional[str] = None
    github_token: Optional[str] = None
    selected_repos: Optional[List[str]] = None
    repo_urls: Optional[List[str]] = None  # Upfront list of showcase repositories (URLs, 'owner/repo', or repo names)

class StudentPortfolioOutSchema(Schema):
    id: int
    username: str
    email: str
    bio: Optional[str] = None
    current_designation: Optional[str] = ""
    experience_years: Optional[float] = 0.0
    institution: Optional[str] = ""
    institution_status: Optional[str] = "UNATTACHED"
    institution_rejection_reason: Optional[str] = ""
    institution_id: Optional[int] = None
    institution_name: Optional[str] = ""
    department: Optional[str] = ""
    degree: Optional[str] = ""
    cgpa: Optional[float] = None
    graduation_year: Optional[int] = None
    github_url: Optional[str] = ""
    linkedin_url: Optional[str] = ""
    portfolio_url: Optional[str] = ""
    is_verified: bool
    overall_confidence_score: float
    profile_strength_score: float = 0.0
    profile_strength_breakdown: Optional[ProfileStrengthBreakdownSchema] = None
    placement_status: str
    target_roles: List[str] = []
    skills_matrix: Dict[str, Any] = {}
    skills_categorized: Dict[str, Any] = {}
    role_fit_matrix: Dict[str, Any] = {}
    certifications: List[Dict[str, Any]] = []
    projects: List[Dict[str, Any]] = []
    internships: List[Dict[str, Any]] = []
    achievements: List[Dict[str, Any]] = []
    academic_records: List[Dict[str, Any]] = []
    active_internships: List[Dict[str, Any]] = []
    nep_passport: Optional[NEPPassportOutSchema] = None
    github_engineering_radar: Optional[GitHubRadarOutSchema] = None
    is_blind: bool = False
    semantic_bridges: List[Dict[str, str]] = []

class MilestoneLogCreateIn(Schema):
    week_number: int
    milestone_summary: str
    hours_logged: Optional[int] = 40
    deliverables_url: Optional[str] = ""

class ActiveInternshipDetailOut(Schema):
    application_id: int
    listing_id: int
    title: str
    company_name: str
    company_logo: Optional[str] = ""
    location: str
    stipend_or_ctc: str
    role_type: str
    internship_status: str
    mentor_name: Optional[str] = ""
    mentor_designation: Optional[str] = ""
    mentor_feedback: Optional[str] = ""
    mentor_rating: Optional[float] = None
    completion_certificate_url: Optional[str] = ""
    internship_report_url: Optional[str] = ""
    weekly_progress_logs: List[Dict[str, Any]] = []


# --- PHASE 3 SCHEMAS (Test Generation) ---

class QuestionOutSchema(Schema):
    id: int
    question_text: str
    type: str  # "MCQ" or "VIVA"
    difficulty: str  # "EASY", "MEDIUM", "HARD"
    category: Optional[str] = "TECHNICAL"  # "TECHNICAL" or "SOFT_SKILL"
    options: Optional[List[str]] = None  # Only populated for MCQ
    justification_prompt: Optional[str] = "In one sentence, explain your reasoning or why you selected this option:"

class TestGenerationOutSchema(Schema):
    role_title: str
    session_id: int
    questions: List[QuestionOutSchema]

# --- PHASE 4 SCHEMAS (Test Submission & Grading) ---

class StudentAnswerInSchema(Schema):
    id: int
    answer_text: str
    justification: Optional[str] = ""
    time_taken_seconds: Optional[int] = 15
    questionId: Optional[int] = None
    timeSpent: Optional[int] = None
    selectedOption: Optional[str] = None
    confidenceDecay: Optional[float] = None
    scoreEfficiency: Optional[float] = None

class TestSubmissionInSchema(Schema):
    target_role: str
    session_id: int
    answers: List[StudentAnswerInSchema]
    clusterId: Optional[Any] = None
    candidateId: Optional[Any] = None
    infractionCount: Optional[int] = 0
    totalTimeSeconds: Optional[int] = 0

class FeedbackDetailSchema(Schema):
    id: int
    question_text: str
    type: str
    category: Optional[str] = "TECHNICAL"
    student_answer: str
    justification: Optional[str] = ""
    score: int
    feedback: str
    skill_gap: Optional[str] = None
    growth_tip: Optional[str] = None

class SkillGapItemSchema(Schema):
    skill: str
    category: str = "TECHNICAL"  # "TECHNICAL" or "SOFT_SKILL"
    identified_gap: str
    growth_recommendation: str

class TestGradingOutSchema(Schema):
    success: bool
    cognitive_score: int
    mcq_average: int
    viva_average: int
    confidence_score: int
    feedback_log: List[FeedbackDetailSchema] = []
    skill_gaps: List[SkillGapItemSchema] = []
    retest_required: bool = False
    fault_acknowledged: bool = False
    message: Optional[str] = ""
    retest_session_id: Optional[int] = None

class CompletedAssessmentOutSchema(Schema):
    session_id: int
    target_role: str
    is_completed: bool = True
    created_at: Optional[str] = None
    completed_date: str = "Verified"
    overall_score: float = 0.0
    confidence_score: float = 0.0
    mcq_accuracy: float = 100.0
    mcq_count: int = 0
    mcq_correct: int = 0
    viva_average: float = 0.0
    viva_count: int = 0
    is_verified: bool = True
    verification_badge: str = "Verified Ayush Specialist"
    anti_cheat_status: str = "Passed (Zero Padding Discrepancy)"
    questions: List[Dict[str, Any]] = []

# --- PHASE 5 SCHEMAS (Recruiter Hybrid Search & Ranking) ---

class RecruiterSearchQueryIn(Schema):
    query: str
    limit: Optional[int] = 10
    blind: Optional[bool] = False

class StudentSearchResultOut(Schema):
    id: int
    username: str
    email: str
    bio: Optional[str] = None
    skills_matrix: Dict[str, Any] = {}
    raw_extracted_skills: List[str] = []
    role_fit_matrix: Dict[str, Any] = {}
    target_roles: List[str] = []
    institution: Optional[str] = None
    department: Optional[str] = None
    overall_confidence_score: float
    is_verified: bool
    is_blind: bool = False
    final_score: float
    skill_tag_score: float
    semantic_score: float
    fulltext_score: float
    verification_boost: float = 1.0
    matched_skills: List[str] = []
    inferred_sector: Optional[str] = None
    semantic_bridge: Optional[str] = None
    name: Optional[str] = None
    degree: Optional[str] = None

class RecruiterSearchResponseOut(Schema):
    query: str
    inferred_sector: Optional[str] = None
    matched_query_skills: List[str] = []
    weights_used: Dict[str, float]
    total_results: int
    is_blind: bool = False
    translation_triggered: bool = False
    expanded_query: Optional[str] = None
    semantic_bridges: List[str] = []
    correlated_statutory_disciplines: Optional[str] = None
    results: List[StudentSearchResultOut]

# --- PHASE 6 SCHEMAS: DISCOVERY FEED, RECOMMENDATIONS, ROADMAP, NOTIFICATIONS ---

class JobDiscoveryItemOut(Schema):
    id: int
    title: str
    company_id: int
    company_name: str
    company_logo: Optional[str] = ""
    company_website: Optional[str] = ""
    recruiter_id: Optional[int] = None
    recruiter_name: Optional[str] = ""
    hiring_mode: str = "COMPANY"
    hiring_display_name: str = ""
    hiring_logo_url: Optional[str] = ""
    role_type: str
    location: str
    is_remote: bool
    stipend_or_ctc: str
    tenure: Optional[str] = ""
    open_positions: int
    required_skills: List[str] = []
    eligibility_criteria: Dict[str, Any] = {}
    application_deadline: Optional[datetime] = None
    description: str
    is_diversity_drive: bool = False
    target_gender: str = "ALL"
    dei_initiatives: List[str] = []
    created_at: datetime

class JobDiscoveryFeedOut(Schema):
    total_jobs: int
    jobs: List[JobDiscoveryItemOut]

class PersonalizedRecommendationItemOut(Schema):
    listing_id: int
    title: str
    company_name: str
    company_logo: Optional[str] = ""
    recruiter_id: Optional[int] = None
    recruiter_name: Optional[str] = ""
    hiring_mode: str = "COMPANY"
    hiring_display_name: str = ""
    hiring_logo_url: Optional[str] = ""
    location: str
    is_remote: bool
    role_type: str
    min_nheqf_level: Optional[str] = "LEVEL_4_5"
    stipend_or_ctc: Optional[str] = "Competitive"
    tenure: Optional[str] = ""
    application_deadline: Optional[datetime] = None
    match_percentage: float
    fit_level: str
    candidate_tier: Optional[str] = "ENTERPRISE_VERIFIED"
    recommendation_reason: Optional[str] = None
    is_nep_multidisciplinary_match: bool = False
    nep_match_reason: Optional[str] = None
    matched_skills: List[str] = []
    missing_skills: List[str] = []
    required_skills: List[str] = []
    description: str

class PersonalizedRecommendationsFeedOut(Schema):
    candidate_id: int
    candidate_skills_count: int
    total_recommendations: int
    candidate_tier: Optional[str] = "ENTERPRISE_VERIFIED"
    tier_description: Optional[str] = None
    recommendations: List[PersonalizedRecommendationItemOut]

class MarketDemandSkillOut(Schema):
    skill: str
    market_demand_percentage: float
    candidate_proficiency: int
    status: str
    gap_delta: Optional[float] = 0.0
    status_label: Optional[str] = None

class SkillToBuildNextOut(Schema):
    skill: str
    priority: str
    market_demand_percentage: float
    expected_match_boost: str
    actionable_project: str

class SkillGapRoadmapOut(Schema):
    candidate_id: int
    target_role_analyzed: str
    total_jobs_analyzed: int
    candidate_verified_skills_count: int
    market_demand_breakdown: List[MarketDemandSkillOut]
    skills_to_build_next: List[SkillToBuildNextOut]

class NotificationItemOut(Schema):
    id: int
    title: str
    message: str
    notification_type: str
    related_application_id: Optional[int] = None
    related_listing_id: Optional[int] = None
    is_read: bool
    created_at: datetime

class NotificationsResponseOut(Schema):
    unread_count: int
    total_count: int
    notifications: List[NotificationItemOut]

class UpcomingInterviewOut(Schema):
    application_id: int
    listing_id: int
    listing_title: str
    company_name: str
    interview_date: datetime
    status: str

class UpcomingDeadlineOut(Schema):
    listing_id: int
    title: str
    company_name: str
    application_deadline: datetime
    stipend_or_ctc: str
    location: str

class DeadlinesHubOut(Schema):
    upcoming_interviews: List[UpcomingInterviewOut]
    upcoming_deadlines: List[UpcomingDeadlineOut]

# --- PHASE 7 SCHEMAS: MULTI-DOMAIN GOVERNMENT & AFFIRMATIVE ACTION SCHEMES ---

class GovernmentSchemeOutSchema(Schema):
    id: int
    title: str
    sponsoring_agency: str
    domain: str
    scheme_type: str
    target_gender: str
    benefit_summary: str
    description: str
    eligible_degrees: List[str] = []
    min_cgpa: Optional[float] = None
    application_deadline: Optional[datetime] = None
    official_portal_url: str
    status: str
    badge_color: str
    is_eligible: Optional[bool] = None
    match_reasons: List[str] = []
    created_at: datetime

class GovernmentSchemeCreateIn(Schema):
    title: str
    sponsoring_agency: str
    domain: Optional[str] = "ALL"
    scheme_type: Optional[str] = "SCHOLARSHIP"
    target_gender: Optional[str] = "FEMALE_ONLY"
    benefit_summary: str
    description: str
    eligible_degrees: Optional[List[str]] = []
    min_cgpa: Optional[float] = None
    application_deadline: Optional[datetime] = None
    official_portal_url: str
    badge_color: Optional[str] = "purple"

class LiveSchemesFeedOut(Schema):
    total_schemes: int
    user_gender: Optional[str] = None
    schemes: List[GovernmentSchemeOutSchema]
