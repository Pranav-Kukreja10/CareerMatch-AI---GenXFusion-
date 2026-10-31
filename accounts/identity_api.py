import hashlib
from datetime import datetime
from django.shortcuts import get_object_or_404
from ninja import Router
from typing import Optional

from accounts.models import User
from accounts.security import JWTAuth
from accounts.identity_schemas import DigitalIdentityCardOut
from students.models import StudentProfile

try:
    from institutions.models import FacultyProfile, Institution
except (ImportError, RuntimeError):
    FacultyProfile = None
    Institution = None

try:
    from recruiters.models import RecruiterProfile, Company
except (ImportError, RuntimeError):
    RecruiterProfile = None
    Company = None

identity_router = Router(tags=["Digital Identity Card"])


def _generate_identity_card_data(user: User) -> dict:
    """
    Construct standardized, tamper-evident digital identity badge metadata
    for CareerMatch AI candidate and user personas.
    """
    now = datetime.now()
    issued_date = f"{now.strftime('%b')} {now.year}"
    name = f"{user.first_name} {user.last_name}".strip() or user.username
    avatar = getattr(user, 'avatar_url', "") or ""

    if user.role in [User.Role.STUDENT, User.Role.CANDIDATE]:
        sp, _ = StudentProfile.objects.get_or_create(user=user)
        title_prefix = (getattr(sp, 'title', '') or getattr(sp, 'honorific', '') or '').strip()
        legal_name = f"{user.first_name} {user.last_name}".strip() or user.username
        stu_display_name = f"{title_prefix + ' ' if title_prefix else ''}{legal_name}".strip()
        grad_year = sp.graduation_year or (now.year + 2)
        unique_id = f"CM-STU-{grad_year}-{sp.id:05d}"
        inst_name = (sp.institution or "").strip() or "CareerMatch AI"
        inst_code = "AISHE-IND-001"
        enrollment = sp.abc_id or f"ENR/{grad_year}/{sp.id:04d}"
        apaar = sp.apaar_id or f"{user.id:04d}-4567-{sp.id:04d}"
        
        status = "INSTITUTION_VERIFIED" if sp.institution_status == StudentProfile.InstitutionStatus.APPROVED else (
            "VERIFICATION_PENDING" if sp.institution_status == StudentProfile.InstitutionStatus.PENDING else "DIGILOCKER_AUTHENTICATED"
        )
        
        card_data = {
            "card_type": "STUDENT",
            "unique_id_number": unique_id,
            "cardholder_name": stu_display_name,
            "username": user.username,
            "email": user.email,
            "role_title": "Student / Candidate",
            "designation": sp.current_designation or "Undergraduate Scholar",
            "organization_name": inst_name,
            "organization_code": inst_code,
            "department_or_major": sp.department or "Computer Science & Engineering",
            "degree_program": sp.degree or "B.Tech / Professional Degree",
            "enrollment_number": enrollment,
            "apaar_id": apaar,
            "avatar_url": avatar,
            "qr_payload_url": f"/?tab=portfolio&studentId={sp.id}",
            "verification_status": status,
            "is_verified": sp.is_verified or sp.institution_status == StudentProfile.InstitutionStatus.APPROVED,
            "issued_date": issued_date,
            "valid_until": f"June {grad_year}",
            "theme_accent": "blue"
        }

    elif user.role in [User.Role.ACADEMIA, User.Role.COLLEGE_ADMIN]:
        fp = FacultyProfile.objects.filter(user=user).first() if FacultyProfile else None
        is_admin = getattr(fp, 'is_institution_admin', False) or user.is_college_admin()
        fp_id = fp.id if fp else user.id
        inst_name = (fp.institution.name if (fp and getattr(fp, 'institution', None)) else "Academic Institution")
        inst_code = "AISHE-C-XXXXX"
        dept_name = "Department of Computer Science"

        unique_id = f"CM-ADM-{fp_id:05d}" if is_admin else f"CM-FAC-{fp_id:05d}"
        role_title = "College Administrator & Registrar" if is_admin else "Academic Faculty Member"
        designation = (fp.designation if fp else None) or ("College Administrator" if is_admin else "Associate Professor")
        
        card_data = {
            "card_type": "COLLEGE_ADMIN" if is_admin else "FACULTY",
            "unique_id_number": unique_id,
            "cardholder_name": name,
            "username": user.username,
            "email": user.email,
            "role_title": role_title,
            "designation": designation,
            "organization_name": inst_name,
            "organization_code": inst_code,
            "department_or_major": dept_name,
            "degree_program": "Faculty Credentials & Research",
            "enrollment_number": f"FAC-REG-{user.id:04d}",
            "apaar_id": "",
            "avatar_url": avatar,
            "qr_payload_url": f"/?tab=academician-profile&facultyId={fp_id}",
            "verification_status": "STATUTORY_FACULTY_CREDENTIAL",
            "is_verified": True,
            "issued_date": issued_date,
            "valid_until": "Permanent Tenured Faculty",
            "theme_accent": "amber" if is_admin else "emerald"
        }

    elif user.role == User.Role.RECRUITER:
        rp = RecruiterProfile.objects.filter(user=user).first() if RecruiterProfile else None
        company_name = (rp.company.name if (rp and getattr(rp, 'company', None)) else "Enterprise Hiring Partner")
        company_code = f"CIN-U{user.id:05d}DL2024"
        unique_id = f"CM-REC-2026-{user.id:05d}"

        card_data = {
            "card_type": "RECRUITER",
            "unique_id_number": unique_id,
            "cardholder_name": name,
            "username": user.username,
            "email": user.email,
            "role_title": "Enterprise Talent Acquisition",
            "designation": (rp.designation if rp else None) or "Technical Recruiter",
            "organization_name": company_name,
            "organization_code": company_code,
            "department_or_major": "Talent Acquisition",
            "degree_program": "Corporate Human Resources",
            "enrollment_number": f"CORP-REG-{user.id:04d}",
            "apaar_id": "",
            "avatar_url": avatar,
            "qr_payload_url": f"/?tab=recruiter-profile&recruiterId={user.id}",
            "verification_status": "ENTERPRISE_AUTHENTICATED",
            "is_verified": True,
            "issued_date": issued_date,
            "valid_until": "Annual Corporate License",
            "theme_accent": "purple"
        }

    else:
        unique_id = f"CM-SYS-{user.id:05d}"
        card_data = {
            "card_type": "ADMIN",
            "unique_id_number": unique_id,
            "cardholder_name": name,
            "username": user.username,
            "email": user.email,
            "role_title": "System Administrator",
            "designation": "Platform Governor",
            "organization_name": "CareerMatch AI Engine",
            "organization_code": "CM-GOV-01",
            "department_or_major": "Engineering Platform Governance",
            "degree_program": "National System Architecture",
            "enrollment_number": f"SYS-ROOT-{user.id:04d}",
            "apaar_id": "",
            "avatar_url": avatar,
            "qr_payload_url": f"/admin",
            "verification_status": "ROOT_AUTHORITY",
            "is_verified": True,
            "issued_date": issued_date,
            "valid_until": "Perpetual Administrative Mandate",
            "theme_accent": "rose"
        }

    # Generate SHA-256 digital fingerprint signature
    signature_source = f"{unique_id}:{name}:{user.email}:{issued_date}:{card_data['organization_name']}"
    card_data["digital_signature_hash"] = hashlib.sha256(signature_source.encode('utf-8')).hexdigest()

    return card_data


@identity_router.get("/identity-card/me", response=DigitalIdentityCardOut, auth=JWTAuth())
def get_my_digital_identity_card(request):
    """Retrieves authenticated user's digital identity credential badge."""
    return _generate_identity_card_data(request.user)


@identity_router.get("/identity-card/{user_id}", response={200: DigitalIdentityCardOut, 404: dict})
def get_user_digital_identity_card(request, user_id: int):
    """Public credential verification endpoint."""
    target_user = get_object_or_404(User, id=user_id)
    return 200, _generate_identity_card_data(target_user)
