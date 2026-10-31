import os
from io import BytesIO
from pypdf import PdfReader
import docx
from students.models import JobBenchmark

# --- IN-MEMORY MULTI-FILE PARSERS ---

def parse_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    extracted_text = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            extracted_text.append(text)
    return "\n".join(extracted_text)

def parse_docx(file_bytes: bytes) -> str:
    doc = docx.Document(BytesIO(file_bytes))
    extracted_text = []
    for paragraph in doc.paragraphs:
        if paragraph.text:
            extracted_text.append(paragraph.text)
    return "\n".join(extracted_text)

def parse_plain_text(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1")

def extract_text_from_file(file) -> str:
    file_name = file.name.lower()
    file_bytes = file.read()
    
    if file_name.endswith('.pdf'):
        return parse_pdf(file_bytes).strip()
    elif file_name.endswith('.docx'):
        return parse_docx(file_bytes).strip()
    elif file_name.endswith(('.txt', '.md')):
        return parse_plain_text(file_bytes).strip()
    else:
        raise ValueError("Unsupported file format. Please upload a PDF, DOCX, TXT, or MD file.")


# --- DYNAMIC MULTI-DOMAIN BENCHMARKING MATCHING ENGINE ---

def calculate_role_score(skills_matrix: dict, benchmark: JobBenchmark) -> int:
    """
    Calculates a normalized score (0-100) comparing the weighted skills matrix 
    against database benchmarks.
    """
    # Keys of skills_matrix are already lowercase skill names
    extracted_lower = [s.lower() for s in skills_matrix.keys()]
    
    def get_skill_score_sum(benchmark_list):
        if not benchmark_list:
            return 0
        total_weight = 0
        match_count = 0
        for skill in benchmark_list:
            skill_lower = skill.lower().strip()
            # Substring intersection checks
            matched_key = next((ext for ext in extracted_lower if skill_lower in ext or ext in skill_lower), None)
            if matched_key:
                match_count += 1
                total_weight += skills_matrix[matched_key].get("weight", 50)
                
        match_ratio = match_count / len(benchmark_list)
        avg_weight = (total_weight / match_count) if match_count > 0 else 0
        # Incorporate skill weight alignment directly into math rating
        return (match_ratio * avg_weight)

    core_score = get_skill_score_sum(benchmark.core_skills)
    method_score = get_skill_score_sum(benchmark.methodology_skills)
    tooling_score = get_skill_score_sum(benchmark.tooling_skills)
    
    # Weighted Scoring Matrix: 50% Core Skills, 30% Methodologies, 20% Tooling & Software
    final_score = int((0.5 * core_score) + (0.3 * method_score) + (0.2 * tooling_score))
    return min(final_score, 100)

def generate_role_fit_matrix(skills_matrix: dict, current_designation: str = "", target_roles: list = None, degree: str = "") -> dict:
    matrix = {}
    benchmarks = JobBenchmark.objects.select_related('sector').all()
    
    for benchmark in benchmarks:
        score = calculate_role_score(skills_matrix, benchmark)
        
        if score <= 5:
            continue
        
        if score >= 75:
            fit_level = "High Match"
        elif score >= 40:
            fit_level = "Medium Match"
        else:
            fit_level = "Low Match"
            
        matrix[benchmark.role_title] = {
            "score": score,
            "fit_level": fit_level,
            "sector": benchmark.sector.name,
            "verified_confidence_score": None
        }

    if not matrix and (current_designation or target_roles or degree):
        candidate_terms = set()
        if current_designation:
            candidate_terms.update([w.lower() for w in current_designation.split() if len(w) > 2])
        if target_roles:
            for tr in target_roles:
                candidate_terms.update([w.lower() for w in tr.split() if len(w) > 2])
        if degree:
            candidate_terms.update([w.lower() for w in degree.split() if len(w) > 2])

        for benchmark in benchmarks:
            bench_words = set(benchmark.role_title.lower().split())
            if candidate_terms & bench_words:
                matrix[benchmark.role_title] = {
                    "score": 25,
                    "fit_level": "Foundational Aspirant (Skills Needed)",
                    "sector": benchmark.sector.name,
                    "verified_confidence_score": 0
                }

    return matrix


# --- SKILL CREDENTIAL BOOST & CANDIDATE PROFILE STRENGTH ---

def build_skills_matrix(extracted_skills_list: list, certifications: list = None, github_verified_skills: list = None) -> dict:
    """
    Builds candidate skills matrix Ws = 0.6*Pe + 0.4*Er.
    - If a skill is covered by an active industry certification: applies +15% credential boost.
    - If a skill is verified in candidate's GitHub repositories: applies +15 Project Evidence boost.
    """
    certifications = certifications or []
    certified_keywords = set()
    for cert in certifications:
        if isinstance(cert, dict):
            cert_name = cert.get("name", "").lower()
            if cert_name:
                certified_keywords.add(cert_name)
            for sc in cert.get("skills_covered", []):
                if sc:
                    certified_keywords.add(sc.lower().strip())

    github_skills_lower = {s.lower().strip() for s in (github_verified_skills or [])}

    matrix = {}
    for s in extracted_skills_list:
        name_lower = s.get("name", "").lower().strip()
        if not name_lower:
            continue
        pe = s.get("project_evidence_score", 50)
        er = s.get("experience_recency_score", 50)

        # Check if skill verified in GitHub codebases
        is_github_verified = any(
            gs and (gs in name_lower or name_lower in gs)
            for gs in github_skills_lower
        )
        if is_github_verified:
            pe = min(100, pe + 15)

        base_weight = int((0.6 * pe) + (0.4 * er))
        
        # Check if skill matches any certified keyword
        is_certified = any(
            kw and (kw in name_lower or name_lower in kw)
            for kw in certified_keywords
        )
        boosted_weight = min(100, int(round(base_weight * 1.15))) if is_certified else base_weight

        matrix[name_lower] = {
            "weight": boosted_weight,
            "project_evidence": pe,
            "experience_recency": er,
            "is_certified": is_certified,
            "credential_bonus": 1.15 if is_certified else 1.0,
            "is_github_verified": is_github_verified
        }
    return matrix


def compute_profile_strength(profile) -> tuple:
    """
    Computes candidate profile strength (0-100) using the approved industry standard:
    P_overall = 0.45 * S_cognitive + 0.30 * S_projects_exp + 0.15 * S_certifications + 0.10 * S_academics
    Enriches S_projects_exp with verified GitHub engineering score when available.
    Brand new profiles with no skills or assessments get default score 0.0.
    Returns (profile_strength_score, breakdown_dict).
    """
    # 1. Cognitive Assessment Score (45%)
    s_cognitive = float(profile.overall_confidence_score or 0.0)
    
    # 2. Projects & Applied Experience Score (30%)
    weights = [
        v.get("weight", 0.0) 
        for v in (profile.skills_matrix or {}).values() 
        if isinstance(v, dict) and v.get("weight") is not None
    ]
    mean_skills_weight = float(sum(weights) / len(weights)) if weights else 0.0

    # Enrich with GitHub Engineering Production Score if screened
    gh_metrics = getattr(profile, "github_metrics", {}) or {}
    eng_score = float(gh_metrics.get("engineering_score", 0.0)) if isinstance(gh_metrics, dict) else 0.0

    if eng_score > 0:
        s_projects_exp = round((0.70 * mean_skills_weight) + (0.30 * eng_score), 2)
    else:
        s_projects_exp = round(mean_skills_weight, 2)
    
    # 3. Industry Certifications Score (15%)
    cert_count = len(profile.certifications or [])
    if cert_count >= 3:
        s_cert = 100.0
    elif cert_count == 2:
        s_cert = 85.0
    elif cert_count == 1:
        s_cert = 70.0
    else:
        s_cert = 0.0
        
    # 4. Academic Performance Score (10%)
    if profile.cgpa is not None:
        s_academics = min(100.0, float(profile.cgpa) * 10.0)
    else:
        s_academics = 0.0  # default 0 for unupdated profile
        
    # Brand new users with no skills, assessments, certifications, or GPA get default 0.0
    if not weights and s_cognitive == 0.0 and s_cert == 0.0 and s_academics == 0.0:
        p_overall = 0.0
    else:
        p_overall = round(
            (0.45 * s_cognitive) +
            (0.30 * s_projects_exp) +
            (0.15 * s_cert) +
            (0.10 * s_academics),
            2
        )
    
    breakdown = {
        "cognitive_score": round(s_cognitive, 2),
        "projects_experience_score": round(s_projects_exp, 2),
        "certifications_score": round(s_cert, 2),
        "academics_score": round(s_academics, 2),
        "github_engineering_score": round(eng_score, 2)
    }
    return p_overall, breakdown


SEMANTIC_BRIDGE_ONTOLOGY = {
    # Healthcare & Ayush
    "rasa shastra": {"classical": "Rasa Shastra", "industrial": "Herbal Formulation QC & WHO-GMP", "domain": "Ayush"},
    "dravyaguna": {"classical": "Dravyaguna", "industrial": "Phytochemical Extraction & Pharmacognosy", "domain": "Ayush"},
    "kayachikitsa": {"classical": "Kayachikitsa", "industrial": "Internal Medicine & Bedside Diagnostics", "domain": "Ayush"},
    "agada tantra": {"classical": "Agada Tantra", "industrial": "Toxicology & Pharmacovigilance Protocols", "domain": "Ayush"},
    "nadi pariksha": {"classical": "Nadi Pariksha", "industrial": "Radial Arterial Waveform Assessment", "domain": "Ayush"},
    "panchakarma": {"classical": "Panchakarma", "industrial": "Therapeutic Detoxification Protocols", "domain": "Ayush"},
    "shalya tantra": {"classical": "Shalya Tantra", "industrial": "Minor Surgical & Wound Care Management", "domain": "Ayush"},
    # Technology & Engineering
    "data structures": {"classical": "Data Structures", "industrial": "Algorithmic Efficiency & Memory Optimization", "domain": "Technology"},
    "algorithms": {"classical": "Algorithms", "industrial": "High-Throughput Optimization & Scale", "domain": "Technology"},
    "operating systems": {"classical": "Operating Systems", "industrial": "Concurrency Control & System Architecture", "domain": "Technology"},
    "database management systems": {"classical": "DBMS", "industrial": "ACID Transaction Design & Query Optimization", "domain": "Technology"},
    "dbms": {"classical": "DBMS", "industrial": "ACID Transaction Design & Query Optimization", "domain": "Technology"},
    # Commerce & Accounting
    "corporate accounting": {"classical": "Corporate Accounting", "industrial": "Statutory Compliance & IFRS/GAAP Audit", "domain": "Commerce"},
    "cost accounting": {"classical": "Cost Accounting", "industrial": "Variance Analysis & Unit Margin Optimization", "domain": "Commerce"},
    "financial management": {"classical": "Financial Management", "industrial": "Capital Allocation & Cash Flow Modeling", "domain": "Commerce"},
    # Design
    "human computer interaction": {"classical": "HCI", "industrial": "Usability Engineering & WCAG Accessibility", "domain": "Design"},
    "hci": {"classical": "HCI", "industrial": "Usability Engineering & WCAG Accessibility", "domain": "Design"},
}


def get_semantic_bridges(skills_matrix_or_list) -> list:
    """
    Dynamically generates clean, domain-agnostic semantic bridge mappings for a candidate's skills.
    Maps traditional or academic disciplines into their modern functional industrial counterparts
    without marketing jargon or AI buzzwords.
    """
    if not skills_matrix_or_list:
        return []

    if isinstance(skills_matrix_or_list, dict):
        skill_names = list(skills_matrix_or_list.keys())
    elif isinstance(skills_matrix_or_list, list):
        skill_names = [s if isinstance(s, str) else (s.get("name", "") if isinstance(s, dict) else str(s)) for s in skills_matrix_or_list]
    else:
        return []

    bridges = []
    seen = set()
    for s in skill_names:
        s_clean = s.strip().lower()
        for key, bridge in SEMANTIC_BRIDGE_ONTOLOGY.items():
            if key in s_clean or s_clean in key:
                if bridge["classical"] not in seen:
                    seen.add(bridge["classical"])
                    bridges.append(bridge)
                    break
    return bridges

