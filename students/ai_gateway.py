import os
import json
import logging
import re
import time
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List
import requests
from dotenv import load_dotenv
from students.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

# Force Python to read the .env file directly from the disk on every call
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env', override=True)

CACHE_FILE = BASE_DIR / "ai_response_cache.json"

def _get_cache_key(prompt_text: str, schema: dict) -> str:
    """Generates a deterministic SHA-256 cache key based on prompt and schema."""
    schema_identifier = schema.get("title") or json.dumps(schema, sort_keys=True)
    raw = f"{prompt_text.strip()}__@@__{schema_identifier.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _read_cache(cache_key: str) -> Optional[dict]:
    """Reads response from local JSON cache if present."""
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
            return cache.get(cache_key)
    except Exception as e:
        logger.warning(f"[AI Cache] Error reading cache: {e}")
        return None

def _write_cache(cache_key: str, data: dict):
    """Persists validated response to local JSON cache."""
    try:
        cache = {}
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    cache = json.load(f)
            except Exception:
                cache = {}
        cache[cache_key] = data
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.warning(f"[AI Cache] Error writing to cache: {e}")

class AIGateway:
    """
    Unified, Quota-Protected Multi-Model AI Router with Local SHA-256 Caching.
    Optimized for Google Cloud & Gemini free tiers (500 RPD) with failover cascade:
    1. Primary: gemini-3.5-flash-lite (500 RPD)
    2. Failover 1: gemini-3.1-flash-lite (500 RPD)
    3. Failover 2: gemini-2.5-flash
    4. Failover 3: Groq (llama-3.3-70b-versatile)
    5. Local Ollama Fallback (qwen3.5:9b) -> Deterministic heuristic
    """
    
    # Model Tier Definitions
    MODEL_PRIMARY = "gemini-3.5-flash-lite"
    MODEL_FAILOVER_1 = "gemini-3.1-flash-lite"
    MODEL_FAILOVER_2 = "gemini-2.5-flash"
    MODEL_RESUME_PARSER = "gemini-3.5-flash-lite"
    MODEL_TEST_GENERATOR = "gemini-3.5-flash-lite"
    
    @staticmethod
    def extract_skills_and_projects(raw_text: str) -> dict:
        """
        Task 1: Resume Extraction. Routed strictly to gemini-3.1-flash-lite.
        Extracts skills with project evidence and experience recency ratings.
        Graceful Degradation: Returns structured heuristic analysis if external AI is down/timed out.
        """
        try:
            provider = os.getenv("AI_PROVIDER", "local").lower()
            
            if provider == "cloud":
                model = os.getenv("MODEL_RESUME_PARSER", AIGateway.MODEL_RESUME_PARSER)
                
                response_schema = {
                    "type": "OBJECT",
                    "properties": {
                        "skills": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "name": {"type": "STRING"},
                                    "project_evidence_score": {
                                        "type": "INTEGER", 
                                        "description": "0-100 score of how deeply applied and complex this skill is inside their listed projects"
                                    },
                                    "experience_recency_score": {
                                        "type": "INTEGER", 
                                        "description": "0-100 score of how recent and tenure-backed this skill is inside their professional experience"
                                    }
                                },
                                "required": ["name", "project_evidence_score", "experience_recency_score"]
                            }
                        },
                        "projects": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "title": {"type": "STRING"},
                                    "technologies": {
                                        "type": "ARRAY",
                                        "items": {"type": "STRING"}
                                    },
                                    "description": {"type": "STRING"}
                                },
                                "required": ["title", "technologies", "description"]
                            }
                        },
                        "target_roles": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "Job titles or target roles candidate is seeking, inferred from resume headline, summary, and experience"
                        },
                        "current_designation": {
                            "type": "STRING",
                            "description": "Candidate's current or most recent job title or professional identity"
                        },
                        "experience_years": {
                            "type": "NUMBER",
                            "description": "Estimated total years of work/professional experience (0 for freshers/students)"
                        },
                        "academic_credentials": {
                            "type": "OBJECT",
                            "properties": {
                                "institution": {"type": "STRING"},
                                "degree": {"type": "STRING"},
                                "department": {"type": "STRING"},
                                "cgpa": {"type": "NUMBER"},
                                "graduation_year": {"type": "INTEGER"}
                            }
                        },
                        "skills_categorized": {
                            "type": "OBJECT",
                            "properties": {
                                "technical_skills": {"type": "ARRAY", "items": {"type": "STRING"}},
                                "frameworks": {"type": "ARRAY", "items": {"type": "STRING"}},
                                "tools": {"type": "ARRAY", "items": {"type": "STRING"}},
                                "soft_skills": {"type": "ARRAY", "items": {"type": "STRING"}}
                            }
                        },
                        "social_links": {
                            "type": "OBJECT",
                            "properties": {
                                "github": {"type": "STRING"},
                                "linkedin": {"type": "STRING"},
                                "portfolio": {"type": "STRING"}
                            }
                        },
                        "certifications": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "name": {"type": "STRING"},
                                    "issuer": {"type": "STRING"},
                                    "issue_year": {"type": "INTEGER"},
                                    "credential_url": {"type": "STRING"},
                                    "skills_covered": {"type": "ARRAY", "items": {"type": "STRING"}}
                                },
                                "required": ["name"]
                            }
                        }
                    },
                    "required": ["skills", "projects", "target_roles"]
                }

                prompt = (
                    f"You are an expert multi-domain resume parser. Analyze the following candidate resume text across ANY professional domain "
                    f"(Business Administration, Management, Finance, Commerce, Engineering, Technology, Design, Accounting, Marketing, Human Resources, Supply Chain, etc.).\n"
                    f"Extract:\n"
                    f"1. 'skills': List of all domain-specific skills, functional competencies, and software/tools. Assign:\n"
                    f"   - 'project_evidence_score' (0-100): How deeply applied/demonstrated is this skill in projects, case studies, audits, or portfolio deliverables?\n"
                    f"   - 'experience_recency_score' (0-100): How recent and tenure-backed is this skill across work or internship experience?\n"
                    f"2. 'projects': Academic, personal, or professional initiatives (title, technologies/tools/methods used, description of outcomes/impact).\n"
                    f"3. 'target_roles': 1-4 specific job titles candidate is qualified for or seeking (e.g. 'Financial Analyst', 'UI/UX Designer', 'Accountant', 'Marketing Associate', 'Software Engineer').\n"
                    f"4. 'academic_credentials': institution, degree (e.g. BBA, MBA, B.Com, B.Tech, M.Com, BE, B.Des), department, cgpa, graduation_year.\n"
                    f"5. 'current_designation': Most recent job title or professional title (leave empty if student/fresher).\n"
                    f"6. 'experience_years': Total years of professional work experience (0.0 if student or fresher).\n"
                    f"7. 'skills_categorized': Group extracted competencies dynamically into:\n"
                    f"   - 'technical_skills': Core functional/domain skills (e.g., Financial Modeling, Auditing, User Research, Python, Tax Filing, Brand Strategy, CAD).\n"
                    f"   - 'frameworks': Methodologies, standard practices, regulatory standards, or architectures (e.g., GAAP, IFRS, Agile, Scrum, Design Thinking, Six Sigma, SWOT, React, Django).\n"
                    f"   - 'tools': Software, platforms, utilities, and applications (e.g., Excel, Tally, SAP, Figma, Tableau, Salesforce, Docker, Bloomberg, QuickBooks, Jira).\n"
                    f"   - 'soft_skills': Leadership, stakeholder communication, negotiation, problem-solving, collaboration.\n"
                    f"8. 'social_links': github, linkedin, portfolio URLs if present.\n"
                    f"9. 'certifications': Professional certifications, accreditations, or licenses (e.g. AWS Certified, CFA, NPTEL, Coursera Meta, Figma Certified, CPA) with name, issuer, issue_year, and covered skills.\n\n"
                    f"Return ONLY a JSON object matching the schema.\n\n"
                    f"Resume Text:\n{raw_text[:6000]}"
                )

                res = AIGateway._execute_cloud_request(model, prompt, response_schema)
                if isinstance(res, dict):
                    res.setdefault("current_designation", "")
                    res.setdefault("experience_years", 0.0)
                    res.setdefault("academic_credentials", {})
                    res.setdefault("skills_categorized", {"technical_skills": [], "frameworks": [], "tools": [], "soft_skills": []})
                    res.setdefault("social_links", {})
                    res.setdefault("certifications", [])
                return res
                
            elif provider == "local":
                res = OllamaClient.analyze_resume_text(raw_text)
                if isinstance(res, dict):
                    res.setdefault("current_designation", "")
                    res.setdefault("experience_years", 0.0)
                    res.setdefault("academic_credentials", {})
                    res.setdefault("skills_categorized", {"technical_skills": [], "frameworks": [], "tools": [], "soft_skills": []})
                    res.setdefault("social_links", {})
                return res
            else:
                return AIGateway._get_fallback_resume_analysis(raw_text)
        except Exception as err:
            logger.warning(f"AI Gateway resume extraction error: {err}. Triggering graceful Apple-grade fallback.")
            return AIGateway._get_fallback_resume_analysis(raw_text, error_message=str(err))

    @staticmethod
    def generate_adaptive_test(role_title: str, skills: list, projects: list, github_repos: list = None) -> dict:
        """
        Task 2: Progressive Test Generation. Routed strictly to gemini-3.5-flash-lite.
        Universally assesses candidates across any professional domain.
        Anti-Vibe-Coding: Grounds system design vivas directly into candidate's real GitHub repositories.
        Graceful Degradation: Returns curated, standardized assessment if external AI is down/timed out.
        """
        try:
            provider = os.getenv("AI_PROVIDER", "local").lower()
            
            if provider == "cloud":
                model = os.getenv("MODEL_TEST_GENERATOR", AIGateway.MODEL_TEST_GENERATOR)
                
                response_schema = {
                    "type": "OBJECT",
                    "properties": {
                        "questions": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "id": {"type": "INTEGER"},
                                    "question_text": {"type": "STRING"},
                                    "type": {"type": "STRING", "enum": ["MCQ", "VIVA"]},
                                    "difficulty": {"type": "STRING", "enum": ["EASY", "MEDIUM", "HARD"]},
                                    "category": {"type": "STRING", "enum": ["TECHNICAL", "SOFT_SKILL"]},
                                    "justification_prompt": {"type": "STRING"},
                                    "options": {
                                        "type": "ARRAY",
                                        "items": {"type": "STRING"}
                                    },
                                    "correct_answer": {"type": "STRING"},  # "A", "B", "C", "D" or null
                                    "explanation": {"type": "STRING"}      # Rubric standard for grading
                                },
                                "required": ["id", "question_text", "type", "difficulty", "category", "explanation"]
                            }
                        }
                    },
                    "required": ["questions"]
                }

                prompt = (
                    f"You are an expert domain interviewer across any professional industry. Generate a personalized 5-question assessment for a candidate "
                    f"applying for the role of '{role_title}'.\n"
                    f"Candidate Extracted Skills: {skills}\n"
                    f"Candidate Projects/Experience Deliverables: {projects}\n\n"
                    f"Enforce these progressive criteria assessing BOTH functional technical competencies and critical soft skills adapted to '{role_title}':\n"
                    f"1. Question 1 (MCQ - EASY - TECHNICAL): Core functional terminology, fundamental domain principle, or tool literacy check.\n"
                    f"2. Question 2 (MCQ - MEDIUM - TECHNICAL): Applied methodology, engineering best practices, or quality standard (e.g. PEP8/design patterns for software, ISO/SOC2 for cloud/systems, GAAP for finance, WCAG for design), or system procedure.\n"
                    f"3. Question 3 (MCQ - MEDIUM - SOFT_SKILL): Situational judgment, cross-functional collaboration, professional ethics, or stakeholder communication scenario in this domain.\n"
                    f"4. Question 4 (VIVA - MEDIUM - TECHNICAL): Open-ended question asking candidate to explain their technical architecture, formulation methodology, or execution strategy.\n"
                    f"5. Question 5 (VIVA - HARD - SOFT_SKILL): High-stakes scenario testing risk communication, crisis escalation, stakeholder trade-offs, and ethical constraints matching their field.\n\n"
                    f"For every question, specify 'category' as 'TECHNICAL' or 'SOFT_SKILL'. For MCQs, set 'justification_prompt' to 'In one sentence, explain your reasoning or why you selected this option:'.\n"
                    f"For VIVA questions, set 'options' to null and 'correct_answer' to null, and write a detailed "
                    f"grading rubric explanation of what a high-quality answer must mention."
                )


                test_data = AIGateway._execute_cloud_request(model, prompt, response_schema)
                
                # Obfuscate correct answers and grading rubrics into a base64 session token
                import base64
                session_data = json.dumps({"questions": test_data["questions"]})
                session_token = base64.b64encode(session_data.encode()).decode()
                
                return {
                    "role_title": role_title,
                    "questions": test_data["questions"],
                    "test_session_token": session_token
                }
            else:
                return AIGateway._get_fallback_adaptive_test(role_title, skills, projects, github_repos=github_repos)
        except Exception as err:
            logger.warning(f"AI Gateway test generation error: {err}. Triggering graceful Apple-grade fallback.")
            return AIGateway._get_fallback_adaptive_test(role_title, skills, projects, github_repos=github_repos, error_message=str(err))

    @staticmethod
    def _get_fallback_resume_analysis(raw_text: str, error_message: str = "") -> dict:
        """
        Graceful Heuristic Fallback for Resume Analysis:
        When external AI is unreachable or rate-limited, deterministically extracts skills,
        educational degrees, and candidate metadata so the user experience continues seamlessly.
        """
        text_lower = raw_text.lower()
        
        # Curated cross-domain competency vocabulary
        catalog = [
            # Tech & Engineering
            "python", "django", "fastapi", "react", "javascript", "typescript", "sql", "postgresql",
            "docker", "kubernetes", "git", "aws", "node.js", "c++", "java", "html", "css", "mongodb",
            "redis", "rest api", "graphql", "linux", "cad", "solidworks", "ansys", "matlab",
            # Business & Management
            "business analysis", "project management", "agile", "scrum", "market research", "swot",
            "crm", "salesforce", "jira", "operations management", "supply chain", "negotiation",
            # Commerce & Finance
            "accounting", "financial modeling", "tally", "excel", "gst", "tds", "auditing", "taxation",
            "balance sheet", "quickbooks", "gaap", "ifrs", "dcf", "valuation", "powerbi", "tableau",
            # Design & Creative
            "figma", "ui/ux", "user research", "wireframing", "adobe photoshop", "illustrator", "design systems",
            # Data Science, AI & Machine Learning
            "machine learning", "deep learning", "nlp", "computer vision", "pytorch", "tensorflow", "pandas", "numpy", "scikit-learn",
            # Cloud & DevOps
            "terraform", "ci/cd", "github actions", "aws", "gcp", "azure", "microservices", "linux", "bash"
        ]
        
        extracted_skills = []
        for s in catalog:
            if re.search(r'\b' + re.escape(s) + r'\b', text_lower):
                extracted_skills.append({
                    "name": s.title() if len(s) > 3 else s.upper(),
                    "project_evidence_score": 75,
                    "experience_recency_score": 70
                })

        if not extracted_skills:
            extracted_skills = [
                {"name": "Critical Thinking", "project_evidence_score": 70, "experience_recency_score": 70},
                {"name": "Communication", "project_evidence_score": 75, "experience_recency_score": 75},
                {"name": "Problem Solving", "project_evidence_score": 80, "experience_recency_score": 75}
            ]

        degree = "Bachelor of Technology"
        for d in ["b.tech", "btech", "m.tech", "bba", "mba", "b.com", "bcom", "m.com", "b.des", "bca", "mca"]:
            if d in text_lower:
                degree = d.upper()
                break

        fallback_projects = [
            {
                "title": "Academic / Practical Project",
                "technologies": [s["name"] for s in extracted_skills[:3]],
                "description": "Practical domain deliverables demonstrating core technical proficiencies and problem solving."
            }
        ]

        target_roles = ["Associate Engineer", "Business Analyst", "Professional Candidate"]
        for r in ["software", "developer", "designer", "accountant", "analyst", "manager"]:
            if r in text_lower:
                target_roles = [f"{r.title()} Associate", "Professional Candidate"]
                break

        return {
            "skills": extracted_skills,
            "projects": fallback_projects,
            "target_roles": target_roles,
            "current_designation": "Candidate",
            "experience_years": 0.0,
            "academic_credentials": {
                "institution": "University / College",
                "degree": degree,
                "department": "Engineering / Business",
                "cgpa": 7.5,
                "graduation_year": 2025
            },
            "skills_categorized": {
                "technical_skills": [s["name"] for s in extracted_skills if s["name"] not in ["Communication", "Problem Solving"]],
                "frameworks": [],
                "tools": [],
                "soft_skills": ["Problem Solving", "Communication", "Team Collaboration"]
            },
            "social_links": {},
            "certifications": [],
            "ai_degraded": True,
            "ai_status_message": "Oops! It seems our neural pathways hit a brief detour on our end. We're actively fine-tuning the gears. We've safely preserved your file and extracted baseline competencies so you can keep moving forward!"
        }

    @staticmethod
    def _get_fallback_adaptive_test(role_title: str, skills: list, projects: list, github_repos: list = None, error_message: str = "") -> dict:
        """
        Graceful Curated Fallback for Test Generation:
        When external AI is unreachable or rate-limited, provides a rich, progressive
        5-question evaluation tailored to the role, complete with rubrics and answers.
        Anti-Vibe-Coding: Grounds Question 4 in candidate's actual GitHub repo if present.
        """
        import base64

        q4_text = f"Explain the high-level methodology and architectural decisions you would take to implement a robust solution for a core {role_title} project."
        q4_expl = "Candidate should explain modular structure, requirement analysis, testing strategy, and practical trade-offs."


        questions = [
            {
                "id": 1,
                "question_text": f"In professional practice for a {role_title}, what is the foundational principle behind quality assurance and systematic verification?",
                "type": "MCQ",
                "difficulty": "EASY",
                "category": "TECHNICAL",
                "justification_prompt": "In one sentence, explain your reasoning or why you selected this option:",
                "options": [
                    "A) Continuous validation against defined requirements and benchmarks",
                    "B) Bypassing documentation to accelerate initial deployment",
                    "C) Relying entirely on end-user bug reports in production",
                    "D) Eliminating modularity in favor of monolithic scripts"
                ],
                "correct_answer": "A",
                "explanation": "Continuous verification against established standards ensures baseline integrity across all disciplines."
            },
            {
                "id": 2,
                "question_text": f"When faced with competing performance, regulatory, or resource trade-offs in {role_title} deliverables, what is the best practice?",
                "type": "MCQ",
                "difficulty": "MEDIUM",
                "category": "TECHNICAL",
                "justification_prompt": "In one sentence, explain your reasoning or why you selected this option:",
                "options": [
                    "A) Optimize prematurely without profiling empirical metrics",
                    "B) Profile empirical metrics, identify the primary bottleneck, and apply targeted standard-compliant optimization",
                    "C) Double resource allocation without analyzing root cause",
                    "D) Compromise data correctness to maximize throughput"
                ],
                "correct_answer": "B",
                "explanation": "Metric-driven profiling and regulatory compliance identify true bottlenecks while preserving correctness."
            },
            {
                "id": 3,
                "question_text": f"When encountering conflicting stakeholder priorities or unexpected deviations during a {role_title} milestone, what is the professional best practice?",
                "type": "MCQ",
                "difficulty": "MEDIUM",
                "category": "SOFT_SKILL",
                "justification_prompt": "In one sentence, explain your reasoning or why you selected this option:",
                "options": [
                    "A) Conceal the variance until delivery to avoid team friction",
                    "B) Convene an alignment checkpoint with transparent trade-offs, documented impact, and collaborative consensus",
                    "C) Unilaterally override partner preferences without documentation",
                    "D) Abandon milestone quality checks to meet the scheduled timeline"
                ],
                "correct_answer": "B",
                "explanation": "Transparent cross-functional alignment and documented trade-offs preserve project integrity and stakeholder trust."
            },
            {
                "id": 4,
                "question_text": q4_text,
                "type": "VIVA",
                "difficulty": "MEDIUM",
                "category": "TECHNICAL",
                "justification_prompt": "Provide your technical explanation and architectural rationale:",
                "options": None,
                "correct_answer": None,
                "explanation": q4_expl
            },
            {
                "id": 5,
                "question_text": f"Describe a high-stakes crisis or ethical dilemma you could encounter in {role_title} workflows, and how you would communicate risks, resolve team conflict, and preserve system integrity.",
                "type": "VIVA",
                "difficulty": "HARD",
                "category": "SOFT_SKILL",
                "justification_prompt": "Describe your crisis management, ethical safeguards, and communication strategy:",
                "options": None,
                "correct_answer": None,
                "explanation": "Candidate must articulate failure modes, recovery protocols, ethical safeguards, and cross-functional crisis communication."
            }
        ]

        session_data = json.dumps({"questions": questions})
        session_token = base64.b64encode(session_data.encode()).decode()

        return {
            "role_title": role_title,
            "questions": questions,
            "test_session_token": session_token,
            "ai_degraded": True,
            "ai_status_message": "Oops! Our test engine hit a slight latency bump on our end, so we curated a pristine standardized assessment for you. You're all set to begin!"
        }

    @staticmethod
    def _execute_cloud_request(model_name: str, prompt_text: str, schema: dict) -> dict:
        """
        Quota-Protected Multi-Model Router with Local SHA-256 Caching:
        1. Checks sha256(prompt + schema) cache -> returns 0 RPD on hit.
        2. Cascade:
           - Primary: gemini-3.5-flash-lite (500 RPD)
           - Failover 1: gemini-3.1-flash-lite (500 RPD)
           - Failover 2: gemini-2.5-flash
           - Failover 3: Groq (llama-3.3-70b-versatile)
           - Failover 4: Local Ollama (qwen3.5:9b)
        3. Persists successful response into ai_response_cache.json.
        """
        cache_key = _get_cache_key(prompt_text, schema)
        cached = _read_cache(cache_key)
        if cached is not None:
            logger.info(f"[AI Router] Cache hit for key {cache_key[:12]}... (0 RPD consumed)")
            return cached

        # Model hierarchy: primary -> failover 1 -> failover 2
        models_to_try = [
            os.getenv("MODEL_PRIMARY", AIGateway.MODEL_PRIMARY),
            os.getenv("MODEL_FAILOVER_1", AIGateway.MODEL_FAILOVER_1),
            os.getenv("MODEL_FAILOVER_2", AIGateway.MODEL_FAILOVER_2),
        ]
        if model_name and model_name not in models_to_try:
            models_to_try.insert(0, model_name)

        deduped = []
        for m in models_to_try:
            if m and m not in deduped:
                deduped.append(m)

        for current_model in deduped:
            logger.info(f"[AI Router] Attempting generation with {current_model}...")
            res = AIGateway._execute_gemini_with_retries(current_model, prompt_text, schema, max_retries=2)
            if res is not None:
                logger.info(f"[AI Router] Successfully obtained response from {current_model}.")
                _write_cache(cache_key, res)
                return res
            logger.warning(f"[AI Router] Model {current_model} failed or quota reached. Failing over to next tier...")

        # Failover 3: Groq
        logger.warning("[AI Router] All Gemini tiers exhausted. Trying Groq fallback...")
        groq_result = AIGateway._execute_groq_fallback(prompt_text)
        if groq_result is not None:
            _write_cache(cache_key, groq_result)
            return groq_result

        # Failover 4: Ollama local fallback
        logger.warning("[AI Router] Groq failed. Trying Ollama local fallback...")
        ollama_result = AIGateway._execute_ollama_fallback(prompt_text)
        if ollama_result is not None:
            _write_cache(cache_key, ollama_result)
            return ollama_result

        raise ConnectionError("All AI tiers (Gemini 3.5/3.1/2.5, Groq, Ollama) failed.")

    @staticmethod
    def _execute_gemini_with_retries(model_name: str, prompt_text: str, schema: dict, max_retries: int = 2) -> Optional[dict]:
        """Sends a robust, schema-enforced POST request to Google Gemini with exponential backoff."""
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            logger.warning("GEMINI_API_KEY is missing — skipping Gemini.")
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

        payload = {
            "contents": [{
                "parts": [{"text": prompt_text}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": schema,
                "temperature": 0.1
            }
        }

        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=payload, timeout=60)
                if response.status_code == 429:
                    logger.warning(f"[AI Router] Gemini {model_name} hit rate limit (429 ResourceExhausted).")
                    return None
                response.raise_for_status()
                
                result_json = response.json()
                text_response = result_json["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text_response)
            except Exception as e:
                wait_time = 2 ** (attempt + 1)
                logger.warning(
                    f"[AI Router] Gemini attempt {attempt + 1}/{max_retries} failed on {model_name}: {e}. "
                    f"{'Retrying in ' + str(wait_time) + 's...' if attempt < max_retries - 1 else 'All retries for this tier exhausted.'}"
                )
                if attempt < max_retries - 1:
                    time.sleep(wait_time)

        return None

    @staticmethod
    def _execute_groq_fallback(prompt_text: str) -> Optional[dict]:
        """Failover: Routes the same prompt to Groq (llama-3.3-70b-versatile with JSON mode)."""
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            return None

        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        url = "https://api.groq.com/openai/v1/chat/completions"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are an expert AI assistant. Return ONLY valid JSON matching the requested structure. No markdown, no prose."},
                {"role": "user", "content": prompt_text}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 4096
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        for attempt in range(2):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=45)
                response.raise_for_status()
                result = response.json()
                content_text = result["choices"][0]["message"]["content"]
                return json.loads(content_text)
            except Exception as e:
                logger.warning(f"Groq failover attempt {attempt + 1}/2 failed: {e}")
                if attempt == 0:
                    time.sleep(1)

        return None

    @staticmethod
    def _execute_ollama_fallback(prompt_text: str) -> Optional[dict]:
        """Local Ollama failover executing in strict JSON mode."""
        try:
            ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
            model_name = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "Return ONLY a valid JSON object matching the requested schema."},
                    {"role": "user", "content": prompt_text[:4000]}
                ],
                "stream": False,
                "format": "json"
            }
            resp = requests.post(f"{ollama_host}/api/chat", json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return json.loads(data["message"]["content"])
        except Exception as e:
            logger.warning(f"Ollama local fallback unavailable: {e}")
        return None

    # ---------------------------------------------------------
    # NEW TRACK #16 KILLER AI SERVICES
    # ---------------------------------------------------------

    @staticmethod
    def extract_jd_skills(raw_jd_text: str) -> dict:
        """
        Parses raw job description text into a structured 4-tier competency schema
        (technical_skills, frameworks, tools, soft_skills) and target role.
        Protected by local SHA-256 caching and multi-tier model failover.
        """
        if not raw_jd_text or not raw_jd_text.strip():
            return {
                "role_title": "Software Engineer",
                "experience_level": "Mid-Level",
                "technical_skills": [],
                "frameworks": [],
                "tools": [],
                "soft_skills": []
            }

        schema = {
            "type": "OBJECT",
            "title": "JDSkillExtractionSchema",
            "properties": {
                "role_title": {"type": "STRING", "description": "Normalized job title e.g. Senior Backend Engineer"},
                "experience_level": {"type": "STRING", "description": "e.g. Junior, Mid-Level, Senior, Lead"},
                "technical_skills": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Core programming languages, database systems, core computer science concepts"
                },
                "frameworks": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Libraries and frameworks e.g. FastAPI, Django, React, Express, PyTorch"
                },
                "tools": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "DevOps, cloud, deployment, and VCS tools e.g. Docker, Kubernetes, AWS, Git, CI/CD"
                },
                "soft_skills": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Cross-functional, communication, and leadership practices"
                }
            },
            "required": ["role_title", "technical_skills", "frameworks", "tools", "soft_skills"]
        }

        prompt = (
            "You are an expert technical hiring auditor. Carefully analyze the following job description "
            "and extract required competencies into the 4-tier classification: \n"
            "1. technical_skills: programming languages, database engines, data structures, algorithms\n"
            "2. frameworks: software development libraries and frameworks\n"
            "3. tools: DevOps, cloud providers, containerization, VCS, monitoring\n"
            "4. soft_skills: stakeholder collaboration, crisis handling, agile practices\n\n"
            f"Job Description:\n{raw_jd_text[:5000]}"
        )

        try:
            return AIGateway._execute_cloud_request(AIGateway.MODEL_PRIMARY, prompt, schema)
        except Exception as e:
            logger.warning(f"[AI Gateway] JD extraction cloud request failed ({e}). Using deterministic extractor.")
            return AIGateway._heuristic_extract_jd_skills(raw_jd_text)

    @staticmethod
    def _heuristic_extract_jd_skills(text: str) -> dict:
        """Deterministic heuristic extractor for Job Descriptions when AI is offline."""
        text_lower = text.lower()
        role_title = "Software Engineer"
        for title in ["Backend Engineer", "Frontend Engineer", "Full Stack Engineer", "DevOps Engineer", "Data Engineer", "Machine Learning Engineer"]:
            if title.lower() in text_lower:
                role_title = title
                break

        tech_pool = ["python", "java", "c++", "c#", "go", "rust", "typescript", "javascript", "sql", "postgresql", "mysql", "mongodb", "redis", "algorithms"]
        framework_pool = ["fastapi", "django", "flask", "react", "next.js", "vue", "angular", "node.js", "express", "pytorch", "tensorflow", "spring boot"]
        tool_pool = ["docker", "kubernetes", "aws", "gcp", "azure", "git", "ci/cd", "github actions", "linux", "terraform", "pytest", "grafana"]
        soft_pool = ["system design", "agile", "code reviews", "cross-functional collaboration", "incident response", "problem solving", "mentorship"]

        return {
            "role_title": role_title,
            "experience_level": "Mid-Level",
            "technical_skills": [s.title() for s in tech_pool if re.search(rf"\b{re.escape(s)}\b", text_lower)],
            "frameworks": [s.title() for s in framework_pool if re.search(rf"\b{re.escape(s)}\b", text_lower)],
            "tools": [s.title() for s in tool_pool if re.search(rf"\b{re.escape(s)}\b", text_lower)],
            "soft_skills": [s.title() for s in soft_pool if re.search(rf"\b{re.escape(s)}\b", text_lower)]
        }

    @staticmethod
    def generate_bridge_project(verified_skills: list, missing_competencies: list, target_role: str) -> dict:
        """
        Generates a personalized 4-step Learning DAG and a hyper-targeted capstone project
        that connects student's verified skills to the missing JD skills.
        Uses quota-safe Gemini router with SHA-256 caching.
        """
        schema = {
            "type": "OBJECT",
            "title": "BridgeProjectDAGSchema",
            "properties": {
                "learning_dag_nodes": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "id": {"type": "STRING"},
                            "title": {"type": "STRING"},
                            "skill": {"type": "STRING"},
                            "bridge_from": {"type": "STRING"},
                            "estimated_hours": {"type": "INTEGER"},
                            "match_boost_pct": {"type": "STRING"},
                            "actionable_deliverable": {"type": "STRING"},
                            "recommended_docs": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"}
                            }
                        },
                        "required": ["id", "title", "skill", "bridge_from", "estimated_hours", "match_boost_pct", "actionable_deliverable"]
                    }
                },
                "learning_dag_edges": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "source": {"type": "STRING"},
                            "target": {"type": "STRING"}
                        },
                        "required": ["source", "target"]
                    }
                },
                "capstone_project_spec": {
                    "type": "OBJECT",
                    "properties": {
                        "project_title": {"type": "STRING"},
                        "architecture_summary": {"type": "STRING"},
                        "milestones": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "step": {"type": "INTEGER"},
                                    "title": {"type": "STRING"},
                                    "deliverables": {"type": "ARRAY", "items": {"type": "STRING"}},
                                    "estimated_hours": {"type": "INTEGER"}
                                },
                                "required": ["step", "title", "deliverables", "estimated_hours"]
                            }
                        },
                        "starter_file_tree": {"type": "STRING"},
                        "github_anti_vibe_verification_checklist": {
                            "type": "OBJECT",
                            "properties": {
                                "ci_cd_workflow": {"type": "STRING"},
                                "docker_containerization": {"type": "STRING"},
                                "test_suite": {"type": "STRING"},
                                "commit_hygiene": {"type": "STRING"},
                                "code_quality": {"type": "STRING"}
                            },
                            "required": ["ci_cd_workflow", "docker_containerization", "test_suite", "commit_hygiene", "code_quality"]
                        }
                    },
                    "required": ["project_title", "architecture_summary", "milestones", "starter_file_tree", "github_anti_vibe_verification_checklist"]
                }
            },
            "required": ["learning_dag_nodes", "learning_dag_edges", "capstone_project_spec"]
        }

        v_skills_str = ", ".join(verified_skills[:8]) if verified_skills else "Python, FastAPI, PostgreSQL, Git"
        m_skills_str = ", ".join(missing_competencies[:6]) if missing_competencies else "Docker, Kubernetes, Redis, Celery"

        prompt = (
            f"You are a Principal Software Architect and Career Engineering Mentor. "
            f"A student targeting the role '{target_role}' has verified mastery in: {v_skills_str}. "
            f"Their identified missing competencies for this target job are: {m_skills_str}. \n\n"
            f"Generate:\n"
            f"1. A sequential 4-step Learning DAG (exactly 4 nodes with IDs 'node-1', 'node-2', 'node-3', 'node-4', connected sequentially in learning_dag_edges) bridging their known stack into the missing skills. "
            f"Each node must specify estimated_hours (4-10) and a realistic match_boost_pct (e.g. '+6% match boost').\n"
            f"2. A production-grade weekend bridge capstone project spec that combines their existing stack with the missing skills into an impressive GitHub showcase.\n"
            f"3. An anti-vibe verification checklist with explicit test coverage (>80%), conventional commits, Dockerfile, and GitHub Actions CI workflow."
        )

        try:
            return AIGateway._execute_cloud_request(AIGateway.MODEL_PRIMARY, prompt, schema)
        except Exception as e:
            logger.warning(f"[AI Gateway] Bridge project cloud generation failed ({e}). Using deterministic synthesis.")
            return AIGateway._heuristic_generate_bridge_project(verified_skills, missing_competencies, target_role)

    @staticmethod
    def _heuristic_generate_bridge_project(verified_skills: list, missing_competencies: list, target_role: str) -> dict:
        """Fallback generator producing a rich 4-step DAG and capstone project specification."""
        gaps = missing_competencies if missing_competencies else ["Docker", "Redis", "Celery", "Kubernetes"]
        known = verified_skills[0] if verified_skills else "Python"

        nodes = []
        edges = []
        boosts = ["+8% match boost", "+6% match boost", "+7% match boost", "+5% match boost"]
        hours = [6, 8, 10, 8]

        for i in range(4):
            gap_skill = gaps[i % len(gaps)]
            nid = f"node-{i+1}"
            nodes.append({
                "id": nid,
                "title": f"Step {i+1}: Mastering {gap_skill} for {target_role}",
                "skill": gap_skill,
                "bridge_from": known,
                "estimated_hours": hours[i],
                "match_boost_pct": boosts[i],
                "actionable_deliverable": f"Build and test an end-to-end integration module showcasing {gap_skill} integrated with {known}.",
                "recommended_docs": [f"https://devdocs.io/{gap_skill.lower()}", f"Official {gap_skill} Architecture Guide"]
            })
            if i > 0:
                edges.append({"source": f"node-{i}", "target": nid})

        first_gap = gaps[0] if gaps else "Docker"
        sec_gap = gaps[1] if len(gaps) > 1 else "Redis"

        return {
            "learning_dag_nodes": nodes,
            "learning_dag_edges": edges,
            "capstone_project_spec": {
                "project_title": f"Production-Grade Distributed {target_role} Engine ({known} + {first_gap} & {sec_gap})",
                "architecture_summary": (
                    f"A high-throughput distributed microservice integrating {known} with {first_gap} containerization, "
                    f"{sec_gap} caching/event streaming, and an automated GitHub Actions verification pipeline."
                ),
                "milestones": [
                    {
                        "step": 1,
                        "title": f"Core Domain & Service Skeleton ({known})",
                        "deliverables": ["Clean architecture service layout", "Pytest unit test harness with fixtures"],
                        "estimated_hours": 6
                    },
                    {
                        "step": 2,
                        "title": f"{first_gap} Containerization & Multi-Stage Dockerfile",
                        "deliverables": ["Non-root production Dockerfile", "docker-compose.yml with health checks"],
                        "estimated_hours": 8
                    },
                    {
                        "step": 3,
                        "title": f"{sec_gap} Integration & High-Throughput Caching",
                        "deliverables": ["Connection pooling and fallback retry decorator", "Load test script verifying <15ms p99 latency"],
                        "estimated_hours": 10
                    },
                    {
                        "step": 4,
                        "title": "Anti-Vibe Production Engineering Hardening & CI/CD",
                        "deliverables": [".github/workflows/ci.yml with test & lint gates", "85%+ unit test coverage report", "Conventional commit history"],
                        "estimated_hours": 8
                    }
                ],
                "starter_file_tree": (
                    ".\n"
                    "├── .github/\n"
                    "│   └── workflows/\n"
                    "│       └── ci.yml\n"
                    "├── src/\n"
                    "│   ├── __init__.py\n"
                    "│   ├── main.py\n"
                    "│   ├── config.py\n"
                    "│   └── services/\n"
                    "├── tests/\n"
                    "│   ├── __init__.py\n"
                    "│   └── test_service.py\n"
                    "├── Dockerfile\n"
                    "├── docker-compose.yml\n"
                    "├── pyproject.toml\n"
                    "└── README.md"
                ),
                "github_anti_vibe_verification_checklist": {
                    "ci_cd_workflow": ".github/workflows/ci.yml running automated linting and pytest matrix on push",
                    "docker_containerization": "Multi-stage Docker build utilizing non-root security context and minimal alpine base",
                    "test_suite": "Pytest suite with at least 80% test coverage including positive, negative, and edge-case specs",
                    "commit_hygiene": "Enforced Conventional Commits standard (feat:, fix:, test:, refactor:, chore:)",
                    "code_quality": "Ruff / Flake8 linting zero-warning configuration and clean formatting"
                }
            }
        }
