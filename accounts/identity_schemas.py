from ninja import Schema
from typing import Optional, List, Dict, Any

class DigitalIdentityCardOut(Schema):
    card_type: str  # STUDENT, FACULTY, COLLEGE_ADMIN, INSTITUTION, RECRUITER, COMPANY, ADMIN
    unique_id_number: str  # e.g. SS-STU-2026-00142, SS-FAC-00088, SS-REC-00034
    cardholder_name: str
    username: str
    email: str
    role_title: str
    designation: Optional[str] = ""
    organization_name: Optional[str] = ""
    organization_code: Optional[str] = ""  # AISHE code / CIN / Registration Code
    department_or_major: Optional[str] = ""
    degree_program: Optional[str] = ""
    enrollment_number: Optional[str] = ""  # Enrollment No / APAAR ID / ABC ID / Employee ID
    apaar_id: Optional[str] = ""
    avatar_url: Optional[str] = ""
    qr_payload_url: str
    verification_status: str  # VERIFIED, PENDING, ACTIVE
    is_verified: bool = True
    issued_date: str
    valid_until: str
    phone_number: Optional[str] = ""
    dob: Optional[str] = ""
    security_hash: str
    theme_accent: str = "blue"  # blue, emerald, purple, amber, cyan
