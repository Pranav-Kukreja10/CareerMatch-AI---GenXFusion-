"""
Three-Signal Hybrid Search & Ranking System for Skill Setu

Architecture:
1. Skill-Tag Score (Deterministic, no ML):
   - Extract keywords from recruiter query.
   - Match to canonical skill tags via alias/synonym map built from StudentProfile.skills_matrix
     and JobBenchmark (core, methodology, tooling skills).
   - Sector/Domain context weighting: matched tags count higher when consistent with the query's
     inferred sector.
   - Score = sum(student skill weight x evidence) over matched tags, normalized.

2. Semantic Embedding Score:
   - Retrieval-tuned BAAI/bge-small-en-v1.5 (384 dimensions).
   - Singleton model loader in-process (never loaded per-request).
   - Denormalized search_corpus on StudentProfile weighted by skill confidence.
   - Generated at index time only. Never call embedding/LLM inside live query path.
   - pgvector brute-force cosine distance scan with index-ready structure.

3. Full-Text Score:
   - Postgres ts_rank against search_corpus for exact-match term recall.

Fusion:
   final_score = 0.4 * skill_tag_score + 0.4 * semantic_score + 0.2 * fulltext_score
"""

import os
import re
import math
import logging
from typing import List, Dict, Any, Optional, Tuple

from django.db.models import F
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank

logger = logging.getLogger(__name__)

# Module-level singleton for BGE embedding model
_EMBEDDING_MODEL = None


def get_embedding_model():
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        try:
            import os
            os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
            os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
            from sentence_transformers import SentenceTransformer
            try:
                _EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-small-en-v1.5", local_files_only=True)
            except Exception:
                hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
                _EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-small-en-v1.5", token=hf_token)
            logger.info("Successfully loaded BAAI/bge-small-en-v1.5 singleton model.")
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer model: {e}")
            raise
    return _EMBEDDING_MODEL



def generate_embedding(text: str, is_query: bool = False) -> List[float]:
    """
    Generates a 384-dimensional unit-normalized embedding using BGE.
    For queries, prepends the standard BGE retrieval instruction.
    For document search_corpus, embeds clean raw text with no prefix.
    """
    model = get_embedding_model()
    if is_query:
        # Standard BGE instruction prefix for queries
        text = f"Represent this sentence for searching relevant passages: {text}"
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


# --- DOMAIN & ALIAS MAP BUILDER ---

COMMON_SKILL_SYNONYMS = {
    # IT & Software Engineering
    "py": "python",
    "python3": "python",
    "py3": "python",
    "postgres": "postgresql",
    "psql": "postgresql",
    "pg": "postgresql",
    "fast api": "fastapi",
    "rest": "rest api",
    "restful": "rest api",
    "rest apis": "rest api",
    "restful api": "rest api",
    "k8s": "kubernetes",
    "docker container": "docker",
    "containers": "docker",
    "qa": "quality assurance",
    "ci/cd": "cicd",
    "js": "javascript",
    "ts": "typescript",
    "reactjs": "react",
    "react.js": "react",
    "vuejs": "vue",
    "tailwind": "tailwind css",
    "html": "html5",
    "css": "css3",
    "dj": "django",
    "node": "node.js",
    "nodejs": "node.js",
    "node js": "node.js",
    "nextjs": "next.js",
    "next.js": "next.js",
    "frontend": "react",
    "front-end": "react",
    "backend": "django",
    "back-end": "django",
    "fullstack": "react",
    "full stack": "react",
    
    # Mechanical Engineering
    "cad": "autocad",
    "solid works": "solidworks",
    "catia v5": "catia",
    "ansys workbench": "ansys",
    "finite element analysis": "fea",
    "gdt": "gd&t",
    "geometric dimensioning & tolerancing": "gd&t",
    "computational fluid dynamics": "cfd",
    "thermo": "thermodynamics",
    "fusion": "fusion 360",
    "autodesk fusion": "fusion 360",
    
    # Finance & Commerce
    "discounted cash flow": "dcf",
    "dcf analysis": "dcf",
    "financial models": "financial modeling",
    "ms excel": "excel",
    "spreadsheets": "excel",
    "sheets": "excel",
    "power bi": "powerbi",
    "tableau bi": "tableau",
    "bloomberg": "bloomberg terminal",
    "corp finance": "corporate finance",
    "valuation modeling": "valuation",

    # Accounting, Taxation & Auditing (B.Com / CA / CMA)
    "tally prime": "tally",
    "tally erp": "tally",
    "tally.erp 9": "tally",
    "quick books": "quickbooks",
    "gaap compliance": "gaap",
    "taxation": "tax",
    "tax filings": "tax",
    "gst filing": "gst",
    "gst portal": "gst",
    "tds filing": "tds",
    "financial audit": "auditing",
    "internal audit": "auditing",
    "book keeping": "bookkeeping",
    "ifrs standards": "ifrs",
    "costing": "cost accounting",
    "balance sheets": "financial reporting",
    
    # Business Administration, Management & Operations (BBA / MBA / HR)
    "biz dev": "business development",
    "operations": "operations management",
    "supply chain": "supply chain management",
    "scm": "supply chain management",
    "crm": "customer relationship management",
    "sales force": "salesforce",
    "swot": "swot analysis",
    "kpis": "kpi tracking",
    "kpi": "kpi tracking",
    "project mgmt": "project management",
    "pmp": "project management",
    "market research": "market analysis",
    "market study": "market analysis",
    "hr": "human resources",
    "hcm": "human resources",
    "talent": "talent acquisition",
    "recruitment": "talent acquisition",
    
    # Design & Creative Arts (UI/UX, Graphic Design)
    "ui design": "ui/ux",
    "ux design": "ui/ux",
    "user interface": "ui design",
    "user experience": "ux design",
    "wire framing": "wireframing",
    "proto typing": "prototyping",
    "adobe xd": "xd",
    "adobe ps": "photoshop",
    "adobe ai": "illustrator",
    "figma app": "figma",
    "design system": "design systems",
    "product design": "ui/ux",

    # Marketing & Growth
    "social media": "digital marketing",
    "smm": "digital marketing",
    "seo optimization": "seo",
    "search engine optimization": "seo",
    "sem": "search engine marketing",
    "google ads": "adwords",
    "content creation": "content marketing",
    "copy writing": "copywriting",

    # Ayush, Ayurveda & Pharmaceutical Quality Standards
    "who gmp": "who-gmp",
    "whogmp": "who-gmp",
    "gmp": "who-gmp",
    "good manufacturing practice": "who-gmp",
    "who-gmp compliance": "who-gmp",
    "who gmp compliance": "who-gmp",
    "who-gmp standards": "who-gmp",
    "rasashastra": "rasa shastra",
    "ras shastra": "rasa shastra",
    "rasa shastra & bhaishajya kalpana": "rasa shastra",
    "rasa shastra and bhaishajya kalpana": "rasa shastra",
    "bhaishajya": "bhaishajya kalpana",
    "bhaishajyakalpana": "bhaishajya kalpana",
    "dravyaguna vijnana": "dravyaguna",
    "dravyagun": "dravyaguna",
    "nadi parikshan": "nadi pariksha",
    "pulse examination": "nadi pariksha",
    "hplc": "hplc analysis",
    "hptlc": "hptlc analysis",
    "heavy metal analysis": "heavy metal testing",
    "heavy metal toxicity": "heavy metal testing",
    "heavy metal toxicity testing": "heavy metal testing",
    "heavy metal testing protocols": "heavy metal testing",
    "heavy metals": "heavy metal testing",
    "phytochemistry": "phytochemical extraction",
    "herbal extraction": "phytochemical extraction",
    "botanical extraction": "phytochemical extraction",
    "formulation qc": "quality control",
    "herbal formulation qc": "quality control",
    "bhasma": "bhasma standardization",
    "bhasma analysis": "bhasma standardization",
    "shodhana": "shodhana protocols",
    "agada tantra": "agada tantra",
    "agada tantra (toxicology)": "agada tantra",
    "toxicology": "agada tantra",
    "toxicology & forensic medicine": "agada tantra",
    "visha chikitsa": "agada tantra",
    "heavy metal detoxification": "agada tantra",
    "api reference standards": "api standards",
    "api standards": "api standards",
    "ayurvedic pharmacopoeia of india": "api standards",
    "ayurvedic pharmacopoeia of india (api)": "api standards",
    "api drug testing limits": "api standards",
    "atomic absorption spectroscopy": "aas analysis",
    "atomic absorption spectrometry": "aas analysis",
    "aas": "aas analysis",
    "aas analysis": "aas analysis",
    "icp-ms": "heavy metal testing",
    "panchkarma": "panchakarma",
}

SECTOR_KEYWORDS = {
    "Information Technology": [
        "software", "developer", "backend", "frontend", "fullstack", "devops", "cloud",
        "api", "database", "web", "server", "python", "django", "react", "programming", "code",
        "tailwind", "javascript", "vite", "html", "css", "ui", "ux"
    ],
    "Mechanical Engineering": [
        "mechanical", "cad", "design", "solidworks", "autocad", "fea", "cfd", "stress",
        "aerospace", "fluid", "thermodynamics", "manufacturing", "automotive", "machining"
    ],
    "Finance & Commerce": [
        "finance", "analyst", "financial", "accounting", "valuation", "dcf", "banking",
        "equity", "investment", "portfolio", "excel", "balance sheet", "audit", "commerce",
        "tally", "gst", "tds", "tax", "ifrs", "gaap", "costing"
    ],
    "Business & Management": [
        "management", "bba", "mba", "operations", "supply chain", "strategy", "hr", "sales",
        "marketing", "business analyst", "project manager", "consultant", "recruitment"
    ],
    "Design & Creative Arts": [
        "designer", "design", "ui", "ux", "figma", "wireframe", "prototype", "illustrator",
        "photoshop", "creative", "branding", "product design", "visual"
    ],
    "Ayurvedic Pharmaceuticals & WHO-GMP Manufacturing": [
        "who-gmp", "gmp", "ayurveda", "ayurvedic", "rasa shastra", "rasashastra", "dravyaguna",
        "phytochemical", "extraction", "quality control", "qc", "heavy metal", "bhasma",
        "hplc", "hptlc", "dabur", "himalaya", "patanjali", "charak", "formulation",
        "standardization", "pharmacopoeia", "api", "pharmaceutical", "pharma"
    ],
    "Ayush Clinical Healthcare & Panchakarma Practice": [
        "panchakarma", "kayachikitsa", "nadi pariksha", "bams", "ncism", "hospital",
        "patient", "pulse", "abhyanga", "shirodhara", "snehana", "swedana", "clinic",
        "doctor", "physician", "vaidya"
    ],
    "Ayush Clinical Research Organizations (CROs)": [
        "clinical trial", "gcp", "pharmacovigilance", "agada tantra", "adr", "cro",
        "spark", "ethics", "clinical research", "protocol", "investigator"
    ],
    "Herbal Agronomy, Cultivation & Phytochemistry": [
        "agronomy", "botanical", "cultivation", "herbs", "phytochemistry", "medicinal plants",
        "pharmacognosy", "taxonomy", "herbarium"
    ],
    "Corporate Wellness, Spa & Ayush Medical Tourism": [
        "wellness", "spa", "tourism", "retreat", "rejuvenation", "masseur", "dietician",
        "pathya", "prakriti"
    ]
}

# --- AYUSH COMPETENCY ONTOLOGY (Bidirectional Semantic Translation Bridge) ---
AYUSH_COMPETENCY_ONTOLOGY: Dict[str, Dict[str, Any]] = {
    # 1. Corporate / Industrial Specifications -> Classical Underlying Competencies
    "who-gmp": {
        "canonical": "WHO-GMP",
        "direction": "CORPORATE_TO_CLASSICAL",
        "competencies": [
            "Quality Control",
            "Phytochemical Extraction",
            "Rasa Shastra",
            "Heavy Metal Testing",
            "Bhasma Standardization",
            "Standardization"
        ],
        "display_bridge": "Mapped: WHO-GMP -> Quality Control, Phytochemical Extraction, Rasa Shastra"
    },
    "who gmp": {
        "canonical": "WHO-GMP",
        "direction": "CORPORATE_TO_CLASSICAL",
        "competencies": [
            "Quality Control",
            "Phytochemical Extraction",
            "Rasa Shastra",
            "Heavy Metal Testing",
            "Bhasma Standardization"
        ],
        "display_bridge": "Mapped: WHO-GMP -> Quality Control, Phytochemical Extraction, Rasa Shastra"
    },
    "gmp": {
        "canonical": "WHO-GMP",
        "direction": "CORPORATE_TO_CLASSICAL",
        "competencies": [
            "Quality Control",
            "Phytochemical Extraction",
            "Rasa Shastra",
            "Standardization"
        ],
        "display_bridge": "Mapped: GMP -> Quality Control, Phytochemical Extraction, Rasa Shastra"
    },
    "quality control": {
        "canonical": "Quality Control",
        "direction": "CORPORATE_TO_CLASSICAL",
        "competencies": [
            "Rasa Shastra",
            "Heavy Metal Testing",
            "HPLC Analysis",
            "WHO-GMP",
            "Bhasma Standardization"
        ],
        "display_bridge": "Mapped: Quality Control -> Rasa Shastra, Heavy Metal Testing, HPLC"
    },
    "qc": {
        "canonical": "Quality Control",
        "direction": "CORPORATE_TO_CLASSICAL",
        "competencies": [
            "Rasa Shastra",
            "Heavy Metal Testing",
            "HPLC Analysis",
            "WHO-GMP"
        ],
        "display_bridge": "Mapped: QC -> Rasa Shastra, Heavy Metal Testing, HPLC"
    },
    "heavy metal testing": {
        "canonical": "Heavy Metal Testing",
        "direction": "CORPORATE_TO_CLASSICAL",
        "competencies": [
            "Rasa Shastra",
            "Agada Tantra",
            "Bhasma Standardization",
            "AAS Analysis",
            "Toxicology",
            "API Standards",
            "Shodhana Protocols",
            "Quality Control"
        ],
        "correlated_statutory_disciplines": "Rasa Shastra & Bhaishajya Kalpana · Agada Tantra · API Reference Standards",
        "display_bridge": "Mapped: Heavy Metal Testing -> Rasa Shastra & Bhaishajya Kalpana · Agada Tantra · API Reference Standards"
    },
    "heavy metal toxicity testing": {
        "canonical": "Heavy Metal Testing",
        "direction": "CORPORATE_TO_CLASSICAL",
        "competencies": [
            "Rasa Shastra",
            "Agada Tantra",
            "Bhasma Standardization",
            "AAS Analysis",
            "Toxicology",
            "API Standards",
            "Shodhana Protocols",
            "Quality Control"
        ],
        "correlated_statutory_disciplines": "Rasa Shastra & Bhaishajya Kalpana · Agada Tantra · API Reference Standards",
        "display_bridge": "Mapped: Heavy Metal Toxicity Testing -> Rasa Shastra & Bhaishajya Kalpana · Agada Tantra · API Reference Standards"
    },
    "phytochemical extraction": {
        "canonical": "Phytochemical Extraction",
        "direction": "CORPORATE_TO_CLASSICAL",
        "competencies": [
            "Dravyaguna",
            "Pharmacognosy",
            "HPLC Analysis",
            "Botanical Identification",
            "Extraction Methods"
        ],
        "display_bridge": "Mapped: Phytochemical Extraction -> Dravyaguna, Pharmacognosy, HPLC"
    },
    "pharmacovigilance": {
        "canonical": "Pharmacovigilance",
        "direction": "CORPORATE_TO_CLASSICAL",
        "competencies": [
            "Agada Tantra",
            "Toxicology",
            "Adverse Drug Reaction",
            "Safety Monitoring",
            "API Limits"
        ],
        "display_bridge": "Mapped: Pharmacovigilance -> Agada Tantra, Toxicology, ADR Reporting"
    },
    "pulse diagnostics": {
        "canonical": "Pulse Diagnostics",
        "direction": "CORPORATE_TO_CLASSICAL",
        "competencies": [
            "Nadi Pariksha",
            "Radial Arterial Waveform Assessment",
            "Tridosha Diagnosis",
            "Prakriti Evaluation"
        ],
        "display_bridge": "Mapped: Pulse Diagnostics -> Nadi Pariksha, Tridosha Assessment"
    },
    "clinical trial coordinator": {
        "canonical": "Clinical Trial Coordinator",
        "direction": "CORPORATE_TO_CLASSICAL",
        "competencies": [
            "Kayachikitsa",
            "Good Clinical Practice",
            "Bedside Differential Diagnostics",
            "GCP Protocols"
        ],
        "display_bridge": "Mapped: Clinical Trial Coordinator -> Kayachikitsa, GCP Protocols"
    },

    # 2. Classical Sanskrit Epistemologies -> Modern Industrial Specifications (Reverse Mapping)
    "rasa shastra": {
        "canonical": "Rasa Shastra",
        "direction": "CLASSICAL_TO_CORPORATE",
        "competencies": [
            "WHO-GMP",
            "Quality Control",
            "Bhasma Standardization",
            "AAS Analysis",
            "API Standards",
            "Phytochemical Extraction"
        ],
        "display_bridge": "Mapped: Rasa Shastra -> Bhasma Standardization, AAS Analysis, WHO-GMP"
    },
    "rasashastra": {
        "canonical": "Rasa Shastra",
        "direction": "CLASSICAL_TO_CORPORATE",
        "competencies": [
            "WHO-GMP",
            "Quality Control",
            "Bhasma Standardization",
            "AAS Analysis",
            "API Standards",
            "Phytochemical Extraction"
        ],
        "display_bridge": "Mapped: Rasa Shastra -> Bhasma Standardization, AAS Analysis, WHO-GMP"
    },
    "bhaishajya kalpana": {
        "canonical": "Bhaishajya Kalpana",
        "direction": "CLASSICAL_TO_CORPORATE",
        "competencies": [
            "WHO-GMP",
            "Herbal Formulation Quality Control",
            "Batch Manufacturing",
            "Standardization"
        ],
        "display_bridge": "Mapped: Bhaishajya Kalpana -> Herbal Formulation QC, Batch Manufacturing, WHO-GMP"
    },
    "dravyaguna": {
        "canonical": "Dravyaguna",
        "direction": "CLASSICAL_TO_CORPORATE",
        "competencies": [
            "Phytochemical Extraction",
            "Pharmacognosy",
            "HPLC Analysis",
            "Botanical Identification",
            "Quality Control"
        ],
        "display_bridge": "Mapped: Dravyaguna -> Phytochemical Extraction, Pharmacognosy, HPLC"
    },
    "kayachikitsa": {
        "canonical": "Kayachikitsa",
        "direction": "CLASSICAL_TO_CORPORATE",
        "competencies": [
            "Internal Medicine",
            "Bedside Differential Diagnostics",
            "Clinical Practice",
            "GCP Clinical Trials"
        ],
        "display_bridge": "Mapped: Kayachikitsa -> Internal Medicine, Bedside Differential Diagnostics"
    },
    "agada tantra": {
        "canonical": "Agada Tantra",
        "direction": "CLASSICAL_TO_CORPORATE",
        "competencies": [
            "Toxicology",
            "AAS Analysis",
            "API Standards",
            "Pharmacovigilance",
            "Adverse Drug Reaction Reporting"
        ],
        "display_bridge": "Mapped: Agada Tantra -> Toxicology, AAS Analysis, Pharmacovigilance"
    },
    "nadi pariksha": {
        "canonical": "Nadi Pariksha",
        "direction": "CLASSICAL_TO_CORPORATE",
        "competencies": [
            "Radial Arterial Waveform Assessment",
            "Pulse Diagnostics",
            "Tridosha Diagnosis",
            "Prakriti Evaluation"
        ],
        "display_bridge": "Mapped: Nadi Pariksha -> Radial Arterial Waveform, Pulse Diagnostics"
    },
    "panchakarma": {
        "canonical": "Panchakarma",
        "direction": "CLASSICAL_TO_CORPORATE",
        "competencies": [
            "Snehana",
            "Swedana",
            "Shirodhara",
            "Detoxification Therapy",
            "Equipment Sanitization"
        ],
        "display_bridge": "Mapped: Panchakarma -> Snehana, Swedana, Shirodhara, Detoxification"
    }
}


def expand_query_with_ayush_ontology(query: str) -> Dict[str, Any]:
    """
    Intercepts incoming search query and checks for corporate or classical Ayush terminology.
    If detected, activates translation trigger, dynamically expanding query with underlying competencies
    (e.g., 'WHO-GMP' -> Quality Control OR Phytochemical Extraction OR Rasa Shastra).
    """
    if not query:
        return {
            "translation_triggered": False,
            "expanded_query": None,
            "matched_bridges": [],
            "expansion_skills": [],
            "competency_map": {}
        }

    q_lower = query.lower().strip()
    q_norm = re.sub(r"[^\w\s\-]", " ", q_lower)

    matched_bridges = []
    expansion_skills = []
    competency_map = {}
    matched_keys = set()
    correlated_statutory_disciplines = None

    sorted_keys = sorted(AYUSH_COMPETENCY_ONTOLOGY.keys(), key=lambda k: len(k), reverse=True)

    for k in sorted_keys:
        pattern = r"(?:\b|_)" + re.escape(k) + r"(?:\b|_)"
        if re.search(pattern, q_norm) or (k in q_norm and len(k) >= 5):
            entry = AYUSH_COMPETENCY_ONTOLOGY[k]
            canonical = entry["canonical"]
            if canonical in matched_keys:
                continue
            matched_keys.add(canonical)
            bridge_text = entry.get("display_bridge", "")
            if bridge_text and bridge_text not in matched_bridges:
                matched_bridges.append(bridge_text)
            if entry.get("correlated_statutory_disciplines") and not correlated_statutory_disciplines:
                correlated_statutory_disciplines = entry.get("correlated_statutory_disciplines")
            for comp in entry.get("competencies", []):
                if comp not in expansion_skills:
                    expansion_skills.append(comp)
            competency_map[canonical.lower()] = entry.get("competencies", [])
            competency_map[k.lower()] = entry.get("competencies", [])

    translation_triggered = len(matched_bridges) > 0

    expanded_query = None
    if translation_triggered:
        top_competencies = expansion_skills[:4]
        comp_str = " OR ".join(top_competencies)
        expanded_query = f"{query.strip()} (Underlying Competencies: {comp_str})"

    if not correlated_statutory_disciplines and ("heavy metal" in q_lower or "toxicity" in q_lower):
        correlated_statutory_disciplines = "Rasa Shastra & Bhaishajya Kalpana · Agada Tantra · API Reference Standards"

    return {
        "translation_triggered": translation_triggered,
        "expanded_query": expanded_query,
        "matched_bridges": matched_bridges,
        "expansion_skills": expansion_skills,
        "competency_map": competency_map,
        "correlated_statutory_disciplines": correlated_statutory_disciplines
    }


def build_canonical_skill_map() -> Dict[str, Dict[str, Any]]:
    """
    Builds an alias/synonym map dynamically from all JobBenchmark skills
    and StudentProfile skills in the database, supplemented by COMMON_SKILL_SYNONYMS.
    Returns mapping:
        alias_or_skill_lower -> {
            "canonical": canonical_name,
            "sector": primary_sector_name,
            "category": "core" | "methodology" | "tooling" | "profile"
        }
    """
    from django.core.cache import cache
    cached_map = cache.get("canonical_skill_map")
    if cached_map is not None:
        return cached_map

    from students.models import JobBenchmark, StudentProfile

    canonical_map = {}

    # 1. Gather all canonical skills from JobBenchmark
    try:
        benchmarks = JobBenchmark.objects.select_related("sector").all()
        for b in benchmarks:
            sector_name = b.sector.name
            for skill in b.core_skills:
                s_clean = skill.lower().strip()
                canonical_map[s_clean] = {"canonical": s_clean, "sector": sector_name, "category": "core"}
            for skill in b.methodology_skills:
                s_clean = skill.lower().strip()
                canonical_map[s_clean] = {"canonical": s_clean, "sector": sector_name, "category": "methodology"}
            for skill in b.tooling_skills:
                s_clean = skill.lower().strip()
                canonical_map[s_clean] = {"canonical": s_clean, "sector": sector_name, "category": "tooling"}
    except Exception as e:
        logger.warning(f"Could not load JobBenchmark for skill map: {e}")

    # 2. Gather additional skills from StudentProfiles
    try:
        profiles = StudentProfile.objects.only("skills_matrix", "role_fit_matrix").all()
        for p in profiles:
            p_sector = None
            if p.role_fit_matrix:
                for role_data in p.role_fit_matrix.values():
                    if isinstance(role_data, dict) and "sector" in role_data:
                        p_sector = role_data["sector"]
                        break
            if isinstance(p.skills_matrix, dict):
                for skill_key in p.skills_matrix.keys():
                    s_clean = skill_key.lower().strip()
                    if s_clean not in canonical_map:
                        canonical_map[s_clean] = {"canonical": s_clean, "sector": p_sector, "category": "profile"}
    except Exception as e:
        logger.warning(f"Could not load StudentProfiles for skill map: {e}")

    # 3. Add synonym mappings pointing to canonical names
    for alias, canonical in COMMON_SKILL_SYNONYMS.items():
        alias_clean = alias.lower().strip()
        canonical_clean = canonical.lower().strip()
        if canonical_clean in canonical_map:
            target_meta = canonical_map[canonical_clean]
            canonical_map[alias_clean] = {
                "canonical": canonical_clean,
                "sector": target_meta["sector"],
                "category": target_meta["category"]
            }
        else:
            canonical_map[alias_clean] = {
                "canonical": canonical_clean,
                "sector": None,
                "category": "synonym"
            }

    # Cache the result for 1 hour to prevent constant DB scans
    cache.set("canonical_skill_map", canonical_map, timeout=3600)
    return canonical_map

def infer_query_domain(query: str, canonical_map: Dict[str, Dict[str, Any]]) -> Tuple[Optional[str], List[str]]:
    """
    Extracts keywords and canonical skill tags from the recruiter query.
    Infers the query's target domain/sector based on matched skills, sector names, and role keywords.
    Returns:
        (inferred_sector_name_or_none, list_of_matched_canonical_skills)
    """
    query_lower = query.lower()
    query_clean = re.sub(r"[^\w\s\+\#\-\.]", " ", query_lower)
    tokens = query_clean.split()

    matched_canonical = set()
    matched_sectors = []
    consumed_indices = set()

    # 1. Check n-grams (3, 2, 1) while tracking consumed token indices
    n = len(tokens)
    for length in (3, 2, 1):
        for i in range(n - length + 1):
            if any(idx in consumed_indices for idx in range(i, i + length)):
                continue
            phrase = " ".join(tokens[i : i + length]).strip()
            if phrase in canonical_map:
                item = canonical_map[phrase]
                canonical_name = item["canonical"]
                matched_canonical.add(canonical_name)
                if item.get("sector"):
                    matched_sectors.append(item["sector"])
                for idx in range(i, i + length):
                    consumed_indices.add(idx)

    # 2. Sector keyword counts (dynamically discover DB sectors)
    from students.models import IndustrySector
    try:
        db_sectors = list(IndustrySector.objects.values_list('name', flat=True))
    except Exception:
        db_sectors = []

    all_known_sectors = set(list(SECTOR_KEYWORDS.keys()) + db_sectors)
    sector_scores = {sector: 0 for sector in all_known_sectors}

    for sector, kw_list in SECTOR_KEYWORDS.items():
        for kw in kw_list:
            if re.search(r"\b" + re.escape(kw) + r"\b", query_lower):
                sector_scores[sector] += 2

    # Match tokens against sector name itself
    for sec in all_known_sectors:
        for word in re.split(r"[\s&/,]+", sec.lower()):
            if len(word) >= 3 and re.search(r"\b" + re.escape(word) + r"\b", query_lower):
                sector_scores[sec] += 3

    # Add votes from matched canonical skills
    for sec in matched_sectors:
        if sec in sector_scores:
            sector_scores[sec] += 3

    best_sector = None
    max_score = 0
    for sec, score in sector_scores.items():
        if score > max_score:
            max_score = score
            best_sector = sec

    return best_sector, list(matched_canonical)


# --- 1. SKILL-TAG SCORER (Deterministic, no ML) ---

def normalize_skill_string(s: str) -> str:
    """Removes all non-alphanumeric characters and lowercase for zero-whitespace fuzzy matching."""
    return re.sub(r'[^a-z0-9]', '', str(s).lower())


def resolve_canonical_skill(s: str, canonical_map: Optional[Dict[str, Any]] = None) -> str:
    """Resolves a skill string to its canonical form via canonical_map or synonyms."""
    s_clean = str(s).lower().strip()
    if canonical_map and s_clean in canonical_map:
        return canonical_map[s_clean].get("canonical", s_clean).lower().strip()
    if s_clean in COMMON_SKILL_SYNONYMS:
        return COMMON_SKILL_SYNONYMS[s_clean].lower().strip()
    # Check normalized string in synonyms
    s_norm = normalize_skill_string(s_clean)
    for alias, canon in COMMON_SKILL_SYNONYMS.items():
        if normalize_skill_string(alias) == s_norm:
            return canon.lower().strip()
    return s_clean


def compute_skill_tag_score(
    student_skills_matrix: dict,
    query_skill_tags: List[str],
    inferred_sector: Optional[str],
    candidate_sectors: Optional[List[str]] = None,
    raw_extracted_skills: Optional[List[str]] = None,
    canonical_map: Optional[Dict[str, Dict[str, Any]]] = None,
    ontology_competency_map: Optional[Dict[str, List[str]]] = None,
    candidate_department: Optional[str] = None
) -> Tuple[float, List[str], Optional[str]]:
    """
    Deterministic Skill-Tag Score (no ML):
    Score is strictly based on whether the candidate possesses the query skills or their
    underlying Ayush ontological competencies.
    Candidates with no matching skills receive 0.0.

    - Ws: individual skill proficiency weight (0-100)
    - Pe: active project evidence score (0-100)
    - Sector consistency factor
    - Skill coverage: 100% exact coverage strictly dominates partial coverage.
    - Bidirectional Ayush Ontology Bridge: Maps corporate tags (e.g. Heavy Metal Toxicity Testing)
      to underlying classical statutory competencies (Rasa Shastra, Agada Tantra, API Standards, AAS).
    """
    if not query_skill_tags:
        return 0.0, [], None

    candidate_skills_lower = {}
    if isinstance(student_skills_matrix, dict):
        candidate_skills_lower = {k.lower().strip(): v for k, v in student_skills_matrix.items()}
    
    # Also index raw extracted skills if matrix is not yet computed
    if raw_extracted_skills and isinstance(raw_extracted_skills, list):
        for rk in raw_extracted_skills:
            clean_rk = str(rk).lower().strip()
            if clean_rk and clean_rk not in candidate_skills_lower:
                candidate_skills_lower[clean_rk] = {"weight": 85, "project_evidence": 85}

    # Statutory Academic Department Integration
    dept_str = str(candidate_department or "").lower()
    is_rasashastra_dept = "rasa shastra" in dept_str or "bhaishajya" in dept_str or "rsbk" in dept_str
    is_agada_dept = "agada" in dept_str or "toxicology" in dept_str

    if is_rasashastra_dept:
        if "rasa shastra" not in candidate_skills_lower:
            candidate_skills_lower["rasa shastra"] = {"weight": 95, "project_evidence": 95}
        if "bhaishajya kalpana" not in candidate_skills_lower:
            candidate_skills_lower["bhaishajya kalpana"] = {"weight": 92, "project_evidence": 90}
    if is_agada_dept:
        if "agada tantra" not in candidate_skills_lower:
            candidate_skills_lower["agada tantra"] = {"weight": 95, "project_evidence": 95}
        if "toxicology" not in candidate_skills_lower:
            candidate_skills_lower["toxicology"] = {"weight": 92, "project_evidence": 92}

    if not candidate_skills_lower:
        return 0.0, [], None

    matched_skills = []
    total_contribution = 0.0
    cand_bridge = None
    all_underlying_bridges = []

    # Sector consistency factor
    sector_factor = 1.0
    if inferred_sector and candidate_sectors:
        if any(inferred_sector.lower() in cs.lower() for cs in candidate_sectors):
            sector_factor = 1.25  # Domain alignment boost
        else:
            sector_factor = 0.60  # Sector collision suppression

    # Statutory department boost when matching Ayush pharmaceuticals / clinical domain
    if is_rasashastra_dept or is_agada_dept:
        sector_factor = max(sector_factor, 1.30)

    for q_skill in query_skill_tags:
        q_clean = q_skill.lower().strip()
        q_canon = resolve_canonical_skill(q_clean, canonical_map)
        q_norm = normalize_skill_string(q_clean)
        matched_key = None
        matched_display = None
        skill_info = None

        # 1. Direct or canonical alias match (skipped if query is heavy metal related to enforce semantic statutory translation)
        if "heavy metal" not in q_clean:
            for c_skill, c_data in candidate_skills_lower.items():
                c_canon = resolve_canonical_skill(c_skill, canonical_map)
                c_norm = normalize_skill_string(c_skill)
                if q_clean == c_skill or q_canon == c_canon or (len(q_norm) >= 4 and q_norm == c_norm):
                    matched_key = c_skill
                    matched_display = q_skill
                    skill_info = c_data
                    break
                if len(q_clean) >= 4 and re.search(r'\b' + re.escape(q_clean) + r'\b', c_skill):
                    matched_key = c_skill
                    matched_display = q_skill
                    skill_info = c_data
                    break

        # 2. Bidirectional Ayush Ontology Competency Match
        underlying_matches = []
        underlying_list = []
        if ontology_competency_map:
            canon_tag = resolve_canonical_skill(q_clean, canonical_map)
            underlying_list = (
                ontology_competency_map.get(q_clean) or
                ontology_competency_map.get(canon_tag) or
                []
            )

        if underlying_list:
            best_u_key = None
            max_u_weight = 0
            best_u_match_name = None
            for u in underlying_list:
                u_clean = u.lower().strip()
                u_canon = resolve_canonical_skill(u_clean, canonical_map)
                u_norm = normalize_skill_string(u_clean)
                for c_skill, c_info in candidate_skills_lower.items():
                    c_canon = resolve_canonical_skill(c_skill, canonical_map)
                    c_norm = normalize_skill_string(c_skill)
                    
                    is_match = (
                        u_clean == c_skill or
                        u_canon == c_canon or
                        (len(u_norm) >= 4 and u_norm == c_norm) or
                        (len(u_clean) >= 4 and re.search(r'\b' + re.escape(u_clean) + r'\b', c_skill)) or
                        (len(u_canon) >= 4 and u_canon in c_skill)
                    )
                    if is_match:
                        if u not in underlying_matches:
                            underlying_matches.append(u)
                        w = c_info.get("weight", 60) if isinstance(c_info, dict) else 60
                        if w > max_u_weight:
                            max_u_weight = w
                            best_u_key = c_skill
                            best_u_match_name = u
                        break

            if underlying_matches:
                bridge_str = f"Mapped: {q_clean.upper()} -> {', '.join(underlying_matches[:3])}"
                all_underlying_bridges.append(bridge_str)
                
                # When translating corporate heavy metal testing, attach all matching statutory competencies (e.g. Rasa Shastra, Agada Tantra, Bhasma Standardization)
                if "heavy metal" in q_clean:
                    for um in underlying_matches:
                        if "heavy metal" not in um.lower() and um not in matched_skills:
                            matched_skills.append(um)
                            c_cand_info = candidate_skills_lower.get(um.lower().strip())
                            ws = float(c_cand_info.get("weight", 90)) if isinstance(c_cand_info, dict) else 90.0
                            pe = float(c_cand_info.get("project_evidence", 90)) if isinstance(c_cand_info, dict) else 90.0
                            total_contribution += (ws / 100.0) * (pe / 100.0) * sector_factor
                else:
                    # If direct match was not found, satisfy query skill through underlying competency!
                    if not matched_key and best_u_key:
                        matched_key = best_u_key
                        matched_display = best_u_match_name or underlying_matches[0]
                        skill_info = candidate_skills_lower[best_u_key]
                    if matched_key and skill_info:
                        matched_skills.append(matched_display or matched_key)
                        ws = float(skill_info.get("weight", 60)) if isinstance(skill_info, dict) else 60.0
                        pe = float(skill_info.get("project_evidence", 60)) if isinstance(skill_info, dict) else 60.0
                        total_contribution += (ws / 100.0) * (pe / 100.0) * sector_factor
        elif matched_key and skill_info:
            matched_skills.append(matched_display or matched_key)
            if isinstance(skill_info, dict):
                ws = float(skill_info.get("weight", 60))
                pe = float(skill_info.get("project_evidence", 60))
            else:
                ws = 60.0
                pe = 60.0
            total_contribution += (ws / 100.0) * (pe / 100.0) * sector_factor

    # Final guarantee: NEVER allow any 'heavy metal' tag on candidate results
    matched_skills = [s for s in matched_skills if "heavy metal" not in s.lower()]

    if all_underlying_bridges:
        cand_bridge = all_underlying_bridges[0]

    if not matched_skills:
        return 0.0, [], None

    # Overlap ratio: how many of the query's required skills the candidate possesses
    overlap_ratio = len(matched_skills) / max(1, len(query_skill_tags))
    avg_proficiency = min(1.0, total_contribution / max(1, len(matched_skills)))
    
    # Skill score reflects skill coverage and candidate proficiency
    if overlap_ratio >= 1.0:
        normalized_score = round(min(0.96, 0.75 + (0.22 * avg_proficiency)), 4)
    else:
        normalized_score = round(min(0.70, overlap_ratio * (0.55 + 0.15 * avg_proficiency)), 4)
    return normalized_score, matched_skills, cand_bridge


# --- 2. DENORMALIZED SEARCH CORPUS BUILDER & INDEXER ---

def build_student_search_corpus(profile) -> str:
    """
    Builds the denormalized search_corpus text field on StudentProfile from
    skills_matrix, projects, bio, and role_fit_matrix.

    Weighted so higher-confidence skills have more influence:
    - High confidence skills (weight >= 70) are placed prominently and repeated
      to increase both transformer self-attention pooling weight and Postgres BM25/ts_rank.
    - Medium skills are placed in secondary sections.
    - Projects include title, technologies, and descriptions.
    """
    sections = []

    # 1. Skills Matrix with Confidence Weighting
    high_skills = []
    med_skills = []
    other_skills = []

    if isinstance(profile.skills_matrix, dict):
        for s_name, s_data in profile.skills_matrix.items():
            if isinstance(s_data, dict):
                weight = s_data.get("weight", 50)
                pe = s_data.get("project_evidence", 50)
                er = s_data.get("experience_recency", 50)
                if weight >= 70:
                    high_skills.append(f"{s_name} (Expert, Weight: {weight}, Evidence: {pe}%)")
                elif weight >= 40:
                    med_skills.append(f"{s_name} (Proficient, Weight: {weight})")
                else:
                    other_skills.append(f"{s_name} (Basic)")
            else:
                med_skills.append(str(s_name))

    if high_skills:
        # Repeating high-confidence skills boosts attention weighting and term frequency
        sections.append("Primary Core Skills: " + ", ".join(high_skills) + ". " + ", ".join(high_skills))
    if med_skills:
        sections.append("Secondary Skills: " + ", ".join(med_skills))
    if other_skills:
        sections.append("Additional Competencies: " + ", ".join(other_skills))

    # 2. Roles and Fitment Ratings
    if isinstance(profile.role_fit_matrix, dict):
        role_lines = []
        for role_name, r_info in profile.role_fit_matrix.items():
            if isinstance(r_info, dict):
                score = r_info.get("score", 0)
                fit_level = r_info.get("fit_level", "")
                sector = r_info.get("sector", "")
                role_lines.append(f"{role_name} in {sector} ({fit_level}, score: {score})")
        if role_lines:
            sections.append("Qualified Domain Roles: " + " | ".join(role_lines))

    # 3. Projects
    if isinstance(profile.projects, list):
        proj_lines = []
        for p in profile.projects:
            if isinstance(p, dict):
                title = p.get("title", "")
                tech = ", ".join(p.get("technologies", [])) if isinstance(p.get("technologies"), list) else p.get("technologies", "")
                desc = p.get("description", "")
                proj_lines.append(f"Project: {title}. Technologies: {tech}. Details: {desc}")
        if proj_lines:
            sections.append("Engineering Projects:\n" + "\n".join(proj_lines))

    # 4. Target Roles Candidate is Seeking
    if isinstance(profile.target_roles, list) and profile.target_roles:
        sections.append("Seeking Target Roles: " + ", ".join(profile.target_roles) + ". " + ", ".join(profile.target_roles))

    # 5. Academic Credentials
    acad = []
    if getattr(profile, 'institution', None):
        acad.append(f"Institution: {profile.institution}")
    if getattr(profile, 'department', None):
        acad.append(f"Department: {profile.department}")
    if getattr(profile, 'degree', None):
        acad.append(f"Degree: {profile.degree}")
    if getattr(profile, 'cgpa', None):
        acad.append(f"CGPA: {profile.cgpa}")
    if getattr(profile, 'graduation_year', None):
        acad.append(f"Graduation: {profile.graduation_year}")
    if acad:
        sections.append("Academic Credentials: " + " | ".join(acad))

    # 6. Categorized Competencies
    if isinstance(getattr(profile, 'skills_categorized', None), dict):
        cat_lines = []
        for cat_name, cat_list in profile.skills_categorized.items():
            if isinstance(cat_list, list) and cat_list:
                cat_lines.append(f"{cat_name.replace('_', ' ').title()}: {', '.join(cat_list)}")
        if cat_lines:
            sections.append("Categorized Competencies: " + " | ".join(cat_lines))

    # 7. Professional Experience & Title
    prof_details = []
    if getattr(profile, 'current_designation', None):
        prof_details.append(f"Current Role / Designation: {profile.current_designation}")
    if getattr(profile, 'experience_years', None) and profile.experience_years > 0:
        prof_details.append(f"Total Professional Experience: {profile.experience_years} years")
    if prof_details:
        sections.append("Professional Background: " + " | ".join(prof_details))

    # 8. Industry Certifications & Verified Credentials
    certs = getattr(profile, 'certifications', None)
    if isinstance(certs, list) and certs:
        cert_lines = []
        for c in certs:
            if isinstance(c, dict):
                c_name = c.get("name", "")
                c_issuer = c.get("issuer", "")
                c_skills = ", ".join(c.get("skills_covered", []))
                issuer_str = f" from {c_issuer}" if c_issuer else ""
                skills_str = f" (Skills: {c_skills})" if c_skills else ""
                cert_lines.append(f"Certified: {c_name}{issuer_str}{skills_str}")
            elif isinstance(c, str):
                cert_lines.append(f"Certified: {c}")
        if cert_lines:
            sections.append("Industry Certifications & Credentials: " + " | ".join(cert_lines) + ". " + " | ".join(cert_lines))

    # 9. Bio and Summary
    if profile.bio:
        sections.append(f"Professional Summary: {profile.bio}")

    return "\n\n".join(sections).strip()


def index_student_profile(profile) -> None:
    """
    INDEX-TIME TRIGGER:
    Builds the search_corpus, generates 384-dim BGE dense embedding,
    and saves to StudentProfile.
    Triggered only after grading / verification completes or during seeding.
    Never called in the live recruiter query path.
    """
    corpus = build_student_search_corpus(profile)
    embedding = generate_embedding(corpus, is_query=False)

    profile.search_corpus = corpus
    profile.embedding = embedding
    profile.save(update_fields=["search_corpus", "embedding"])
    logger.info(f"Successfully indexed profile for user '{profile.user.username}' ({len(embedding)} dims).")


# --- 3. SCORER IMPLEMENTATIONS (UNIT / PYTHON FALLBACKS) ---

def compute_semantic_score(query_embedding: List[float], student_embedding: List[float]) -> float:
    """
    Cosine similarity between normalized embeddings in [0.0, 1.0].
    Used when computing in Python memory or unit testing.
    """
    if not query_embedding or not student_embedding:
        return 0.0
    dot = sum(q * s for q, s in zip(query_embedding, student_embedding))
    # BGE embeddings are L2 normalized, so cosine sim = dot product
    # Map from [-1.0, 1.0] to [0.0, 1.0]
    return max(0.0, min(1.0, float(dot)))


def compute_fulltext_score(search_corpus: str, query_text: str) -> float:
    """
    Fallback term-frequency calculation in [0.0, 1.0] when Postgres full-text is simulated.
    """
    if not search_corpus or not query_text:
        return 0.0
    q_tokens = set(re.findall(r"\w+", query_text.lower()))
    c_tokens = re.findall(r"\w+", search_corpus.lower())
    if not q_tokens or not c_tokens:
        return 0.0
    matches = sum(1 for t in c_tokens if t in q_tokens)
    score = matches / (len(q_tokens) * 5.0)
    return min(1.0, round(score, 4))


# --- 4. THREE-SIGNAL FUSION ---

def fuse_scores(
    skill_tag_score: float,
    semantic_score: float,
    fulltext_score: float,
    weights: Tuple[float, float, float] = (0.4, 0.4, 0.2)
) -> float:
    """
    Computes final fused ranking score:
    final_score = 0.4 * skill_tag + 0.4 * semantic + 0.2 * fulltext
    """
    w_skill, w_semantic, w_fulltext = weights
    final = (w_skill * skill_tag_score) + (w_semantic * semantic_score) + (w_fulltext * fulltext_score)
    return round(final, 4)


def rank_student_profiles(
    query: str,
    limit: int = 10,
    w_skill: float = 0.4,
    w_semantic: float = 0.4,
    w_fulltext: float = 0.2,
    blind: bool = False
) -> Dict[str, Any]:
    """
    Executes the Three-Signal Fusion search pipeline:
    1. Deterministic skill keyword extraction & sector inference.
    2. Local query embedding via singleton BGE model (<15ms).
    3. Retrieval:
       - Uses pgvector CosineDistance brute-force scan if available.
       - Uses PostgreSQL SearchRank for full-text exact matches.
    4. Deterministic skill-tag scoring with sector context.
    5. Three-signal fusion and descending ranking.
    Supports blind: bool toggle to redact candidate PII for unbiased skill-first hiring.
    """
    from students.models import StudentProfile

    if not query or not query.strip():
        return {
            "query": query,
            "inferred_sector": None,
            "matched_query_skills": [],
            "weights_used": {"skill_tag": w_skill, "semantic": w_semantic, "fulltext": w_fulltext},
            "total_results": 0,
            "is_blind": blind,
            "translation_triggered": False,
            "expanded_query": None,
            "semantic_bridges": [],
            "results": []
        }

    # 1. Alias mapping & domain inference
    canonical_map = build_canonical_skill_map()
    inferred_sector, query_skills = infer_query_domain(query, canonical_map)

    # 1.1 AYUSH ONTOLOGY INTERCEPTION & DYNAMIC QUERY EXPANSION
    # Intercept query and dynamically expand with underlying competencies
    # e.g., 'WHO-GMP' -> Quality Control OR Phytochemical Extraction OR Rasa Shastra
    ontology_info = expand_query_with_ayush_ontology(query)
    translation_triggered = ontology_info["translation_triggered"]
    expanded_query = ontology_info["expanded_query"]
    semantic_bridges = ontology_info["matched_bridges"]
    expansion_skills = ontology_info["expansion_skills"]
    competency_map = ontology_info["competency_map"]

    if translation_triggered:
        if not inferred_sector:
            inferred_sector = "Ayurvedic Pharmaceuticals & WHO-GMP Manufacturing"
        # Ensure intercepted tag is present in query_skills without duplicate variants
        if "heavy metal" in query.lower():
            query_skills = ["heavy metal toxicity testing"]
        else:
            for ont_k in competency_map.keys():
                if ont_k in query.lower() and ont_k not in [qs.lower() for qs in query_skills]:
                    query_skills.append(ont_k)

    # 2. Local Query Embedding (singleton in memory)
    embedding_text = query
    if translation_triggered and expansion_skills:
        embedding_text = f"{query} {' '.join(expansion_skills[:3])}"
    query_embedding = generate_embedding(embedding_text, is_query=True)

    # 3. Query PostgreSQL Database
    has_pgvector = False
    try:
        from pgvector.django import CosineDistance
        test_qs = StudentProfile.objects.exclude(embedding__isnull=True).annotate(
            dist=CosineDistance("embedding", query_embedding)
        )
        test_qs.first()
        has_pgvector = True
    except Exception as e:
        logger.warning(f"pgvector query annotation not available or failed: {e}. Falling back to in-memory cosine.")
        has_pgvector = False

    # Base queryset: Defer heavy, unused JSON fields to prevent massive Python deserialization overhead.
    base_qs = StudentProfile.objects.select_related("user").defer(
        "preferences", "github_metrics", "certifications", 
        "skills_categorized", "internships", "achievements", "academic_records"
    )

    # PRE-FILTER OPTIMIZATION:
    if limit is None or limit <= 0:
        MAX_DB_CANDIDATES = 10000
    else:
        MAX_DB_CANDIDATES = max(600, min(10000, limit * 20))
    pks_to_fetch = set()

    order_criteria = ["-is_verified", "-overall_confidence_score", "-profile_strength_score"]

    # Combine original query skills with ontology expanded competencies for DB pre-filtering
    search_skills = list(query_skills)
    if translation_triggered and expansion_skills:
        search_skills = list(set(search_skills + [s.lower() for s in expansion_skills]))
        extra_aliases = []
        for s in search_skills:
            for alias, canon in COMMON_SKILL_SYNONYMS.items():
                if canon == s or s in canon:
                    extra_aliases.append(alias)
        search_skills = list(set(search_skills + extra_aliases))

    if search_skills:
        from django.db.models import Q
        # 1. First priority: Candidates matching requested core skills or statutory disciplines
        any_skill_q = Q()
        for skill in search_skills:
            any_skill_q |= Q(search_corpus__icontains=skill)
        if translation_triggered:
            any_skill_q |= Q(department__icontains="Rasa Shastra") | Q(department__icontains="Agada")
        partial_pks = list(
            base_qs.filter(any_skill_q)
            .order_by(*order_criteria)
            .values_list('pk', flat=True)[:MAX_DB_CANDIDATES]
        )
        pks_to_fetch.update(partial_pks)
    else:
        # General role or plain text query
        clean_tokens = [w.lower() for w in re.findall(r'[a-zA-Z0-9+#.-]{2,}', query) 
                        if w.lower() not in {'and', 'or', 'the', 'for', 'with', 'in', 'of', 'to', 'a', 'an', 'is', 'on', 'at'}]
        if clean_tokens:
            from django.db.models import Q
            token_q = Q()
            for t in clean_tokens:
                token_q |= Q(search_corpus__icontains=t)
            kw_pks = list(
                base_qs.filter(token_q)
                .order_by(*order_criteria)
                .values_list('pk', flat=True)[:MAX_DB_CANDIDATES]
            )
            pks_to_fetch.update(kw_pks)

    if has_pgvector:
        from pgvector.django import CosineDistance
        semantic_pks = list(
            base_qs.exclude(embedding__isnull=True)
            .order_by(CosineDistance("embedding", query_embedding))
            .values_list('pk', flat=True)[:50]
        )
        pks_to_fetch.update(semantic_pks)

    if pks_to_fetch:
        qs = base_qs.filter(pk__in=pks_to_fetch)
    else:
        fallback_pks = list(
            base_qs.order_by(*order_criteria)
            .values_list('pk', flat=True)[:MAX_DB_CANDIDATES]
        )
        qs = base_qs.filter(pk__in=fallback_pks)

    # Full-text SearchVector & SearchRank
    has_fulltext = False
    try:
        search_vector = SearchVector("search_corpus", config="english")
        search_query = SearchQuery(query, config="english", search_type="websearch")
        qs = qs.annotate(ft_rank=SearchRank(search_vector, search_query, normalization=32))
        has_fulltext = True
    except Exception as e:
        logger.warning(f"Postgres SearchRank annotation failed: {e}. Falling back to corpus scanner.")
        has_fulltext = False

    if has_pgvector:
        from pgvector.django import CosineDistance
        qs = qs.annotate(cosine_dist=CosineDistance("embedding", query_embedding))

    profiles = list(qs)
    scored_results = []

    for profile in profiles:
        cand_sectors = []
        if isinstance(profile.role_fit_matrix, dict):
            for r_data in profile.role_fit_matrix.values():
                if isinstance(r_data, dict) and "sector" in r_data:
                    cand_sectors.append(r_data["sector"])

        cand_raw_skills = getattr(profile, 'raw_extracted_skills', []) or []
        cand_skills = list((profile.skills_matrix or {}).keys()) + cand_raw_skills
        cand_has_skills = len(cand_skills) > 0

        # Signal 1: Skill-tag score with Ayush ontology translation & department relevance
        skill_score, matched_cand_skills, cand_bridge = compute_skill_tag_score(
            student_skills_matrix=profile.skills_matrix,
            query_skill_tags=query_skills,
            inferred_sector=inferred_sector,
            candidate_sectors=cand_sectors,
            raw_extracted_skills=cand_raw_skills,
            canonical_map=canonical_map,
            ontology_competency_map=competency_map,
            candidate_department=getattr(profile, 'department', '') or ''
        )

        # Signal 2: Semantic score
        has_profile_embedding = False
        if has_pgvector and hasattr(profile, "cosine_dist") and profile.cosine_dist is not None:
            semantic_score = max(0.0, min(1.0, 1.0 - float(profile.cosine_dist)))
            has_profile_embedding = True
        elif profile.embedding:
            semantic_score = compute_semantic_score(query_embedding, profile.embedding)
            has_profile_embedding = True
        else:
            semantic_score = 0.0
            has_profile_embedding = False
        semantic_score = round(semantic_score, 4)

        # Signal 3: Full-text score
        if has_fulltext and hasattr(profile, "ft_rank") and profile.ft_rank is not None:
            raw_ft = float(profile.ft_rank)
            fulltext_score = min(1.0, raw_ft * 3.0)
        else:
            fulltext_score = compute_fulltext_score(profile.search_corpus, query)
        fulltext_score = round(fulltext_score, 4)

        # STRICT SKILL-BASED MATCHING GATE:
        if not cand_has_skills:
            final = 0.0
            skill_score = 0.0
            semantic_score = 0.0
            fulltext_score = 0.0
            matched_cand_skills = []
            total_multiplier = 1.0
        elif query_skills and len(matched_cand_skills) == 0:
            final = 0.0
            skill_score = 0.0
            semantic_score = 0.0
            fulltext_score = 0.0
            total_multiplier = 1.0
        else:
            if query_skills:
                if has_profile_embedding:
                    effective_weights = (0.85, 0.05, 0.10)
                else:
                    effective_weights = (0.88, 0.0, 0.12)
            else:
                if has_profile_embedding:
                    effective_weights = (w_skill, w_semantic, w_fulltext)
                else:
                    effective_weights = (0.65, 0.0, 0.35)

            relevance_score = fuse_scores(
                skill_tag_score=skill_score,
                semantic_score=semantic_score if has_profile_embedding else 0.0,
                fulltext_score=fulltext_score,
                weights=effective_weights
            )

            # Weighted Composite Match Score: 50% Requisition Relevance + 50% Verified Assessment Mastery
            conf_ratio = max(0.0, min(1.0, (profile.overall_confidence_score or 0.0) / 100.0))
            verified_bonus = 0.01 if profile.is_verified else 0.00
            candidate_target_roles = profile.target_roles or []
            role_intent_bonus = 0.01 if any(tr.lower() in query.lower() for tr in candidate_target_roles) else 0.0

            blended_match = (relevance_score * 0.50) + (conf_ratio * 0.50) + verified_bonus + role_intent_bonus
            # Natural ceiling at 0.98 so scores don't artificially saturate at 100%
            final = round(min(0.98, max(0.15, blended_match)), 4)
            total_multiplier = round(1.0 + (0.10 * conf_ratio) + verified_bonus + role_intent_bonus, 4)

        candidate_target_roles = profile.target_roles or []
        full_name_val = profile.user.get_full_name() or profile.user.username
        username_display = f"Candidate #{profile.id}" if blind else profile.user.username
        name_display = f"Candidate #{profile.id}" if blind else full_name_val
        email_display = "[REDACTED]" if blind else profile.user.email
        institution_display = "[REDACTED]" if (blind and profile.institution) else (profile.institution or None)
        bio_display = "[REDACTED]" if (blind and profile.bio) else profile.bio

        profile_bridge = cand_bridge
        if not profile_bridge and translation_triggered and matched_cand_skills and semantic_bridges:
            profile_bridge = semantic_bridges[0]

        scored_results.append({
            "id": profile.id,
            "username": username_display,
            "name": name_display,
            "degree": getattr(profile, 'degree', '') or None,
            "email": email_display,
            "bio": bio_display,
            "skills_matrix": profile.skills_matrix,
            "raw_extracted_skills": getattr(profile, 'raw_extracted_skills', []) or [],
            "role_fit_matrix": profile.role_fit_matrix,
            "target_roles": candidate_target_roles,
            "institution": institution_display,
            "department": getattr(profile, 'department', '') or None,
            "overall_confidence_score": profile.overall_confidence_score,
            "is_verified": profile.is_verified,
            "is_blind": blind,
            "final_score": final,
            "skill_tag_score": skill_score,
            "semantic_score": semantic_score,
            "fulltext_score": fulltext_score,
            "verification_boost": total_multiplier,
            "matched_skills": matched_cand_skills,
            "inferred_sector": inferred_sector,
            "semantic_bridge": profile_bridge
        })

    # Sort descending by statutory department alignment, final score, and confidence score
    matching_candidates = [r for r in scored_results if r["final_score"] > 0.0]
    results_to_sort = matching_candidates if matching_candidates else scored_results
    if query_skills:
        def sort_priority_key(x):
            dept = str(x.get("department") or "").lower()
            is_rasa_shastra = ("rasa shastra" in dept or "rsbk" in dept or "bhaishajya" in dept) if translation_triggered else False
            is_agada = ("agada" in dept or "toxicology" in dept) if translation_triggered else False
            statutory_dept_tier = 2 if is_rasa_shastra else (1 if is_agada else 0)
            return (
                statutory_dept_tier,
                x["final_score"],
                x["overall_confidence_score"] or 0,
                len(x["matched_skills"])
            )

        results_to_sort.sort(key=sort_priority_key, reverse=True)
    else:
        results_to_sort.sort(key=lambda x: x["final_score"], reverse=True)

    correlated_disciplines = ontology_info.get("correlated_statutory_disciplines")
    if not correlated_disciplines and translation_triggered and ("heavy metal" in query.lower() or "toxicity" in query.lower()):
        correlated_disciplines = "Rasa Shastra & Bhaishajya Kalpana · Agada Tantra · API Reference Standards"

    return {
        "query": query,
        "inferred_sector": inferred_sector,
        "matched_query_skills": query_skills,
        "weights_used": {"skill_tag": w_skill, "semantic": w_semantic, "fulltext": w_fulltext},
        "total_results": len(results_to_sort),
        "is_blind": blind,
        "translation_triggered": translation_triggered,
        "expanded_query": expanded_query,
        "semantic_bridges": semantic_bridges,
        "correlated_statutory_disciplines": correlated_disciplines,
        "results": results_to_sort if (limit is None or limit <= 0) else results_to_sort[:limit]
    }

