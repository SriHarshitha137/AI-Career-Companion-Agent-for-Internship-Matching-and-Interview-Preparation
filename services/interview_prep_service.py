"""AI-Powered Interview Preparation Service.

Provides grounded interview preparation tailored to the candidate's parsed resume,
role recommendations, technical/HR/project question generation, answer guidance,
roadmaps, skill-gap analysis, PDF/DOCX document RAG, and conversational memory.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from extract_text import extract_text
from models import InterviewDocument, Resume
from services.internship_index import _dot, _embed, _terms

DEFAULT_MODEL = "gemini-3.5-flash-lite"
FALLBACK_MODELS = ["gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-flash-latest"]
DOCUMENT_CHUNK_SIZE = 750

# Recognized product question keywords and patterns for InternSphere platform features
PRODUCT_PATTERNS = [
    r"how (do|can) i apply",
    r"how to apply",
    r"apply for (an )?internship",
    r"withdraw( an)? application",
    r"how (do|can) i withdraw",
    r"generate (a )?cover letter",
    r"how (do|can) i generate (a )?cover letter",
    r"download (the )?cover letter",
    r"where (can i see|are) my applications",
    r"how (do|can) i update my profile",
    r"upload profile (picture|photo)",
    r"how does (the )?matching( page)? work",
    r"internship matching (algorithm|page|system)",
    r"what does my match (percentage|score) mean",
    r"how does resume parsing work in internsphere",
    r"how do i use (this|the) (app|platform|internsphere|website)",
]

# Unrelated trivia / out-of-scope patterns
OUT_OF_SCOPE_PATTERNS = [
    r"capital of \w+",
    r"who is the president",
    r"recipe for",
    r"weather in",
    r"sports score",
    r"who won the",
    r"movie recommendation",
    r"tell me a joke",
    r"write a poem about",
    r"lyrics to",
]


class InterviewPrepError(Exception):
    """Base exception for interview prep service errors."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_latest_user_resume(db: Session, user_id: int) -> Resume | None:
    """Retrieve the authenticated user's latest successfully uploaded resume."""
    return db.scalars(
        select(Resume).where(Resume.user_id == user_id).order_by(Resume.uploaded_at.desc())
    ).first()


def extract_resume_profile(resume: Resume | None) -> dict[str, Any]:
    """Extract structured, normalized candidate details from parsed resume JSON."""
    if not resume or not resume.parsed_json:
        return {}

    parsed = resume.parsed_json
    skills = [str(s).strip() for s in (parsed.get("technical_skills") or []) if s]
    soft_skills = [str(s).strip() for s in (parsed.get("soft_skills") or []) if s]
    projects = parsed.get("projects") or []
    experience = parsed.get("work_experience") or []
    internships = parsed.get("internships") or []
    education = parsed.get("education") or []
    certifications = parsed.get("certifications") or []
    achievements = parsed.get("achievements") or []

    # Clean project objects
    clean_projects = []
    for p in projects:
        if isinstance(p, dict):
            clean_projects.append({
                "name": p.get("name") or "Unnamed Project",
                "description": p.get("description") or "",
                "technologies": p.get("technologies") or [],
            })
        elif isinstance(p, str):
            clean_projects.append({"name": p, "description": "", "technologies": []})

    # Clean education objects
    clean_education = []
    for e in education:
        if isinstance(e, dict):
            clean_education.append({
                "institution": e.get("institution") or "",
                "degree": e.get("degree") or "",
                "field_of_study": e.get("field_of_study") or "",
                "grade": e.get("grade") or "",
            })

    return {
        "full_name": parsed.get("full_name") or "Candidate",
        "professional_summary": parsed.get("professional_summary") or "",
        "technical_skills": skills,
        "soft_skills": soft_skills,
        "projects": clean_projects,
        "experience": experience,
        "internships": internships,
        "education": clean_education,
        "certifications": certifications,
        "achievements": achievements,
    }


def format_resume_context(profile: dict[str, Any]) -> str:
    """Format candidate profile into a structured context string for LLM prompts."""
    if not profile:
        return "No resume provided."

    sections = [
        f"Candidate Name: {profile.get('full_name', 'Candidate')}",
        f"Professional Summary: {profile.get('professional_summary') or 'Not provided'}",
        f"Technical Skills: {', '.join(profile.get('technical_skills', [])) or 'None specified'}",
        f"Soft Skills: {', '.join(profile.get('soft_skills', [])) or 'None specified'}",
    ]

    edu = profile.get("education", [])
    if edu:
        edu_strs = [
            f"{e.get('degree', '')} in {e.get('field_of_study', '')} at {e.get('institution', '')}"
            for e in edu
            if isinstance(e, dict)
        ]
        sections.append(f"Education: {'; '.join(filter(None, edu_strs))}")

    projs = profile.get("projects", [])
    if projs:
        proj_strs = []
        for p in projs:
            if isinstance(p, dict):
                techs = f" (Tech: {', '.join(p.get('technologies', []))})" if p.get("technologies") else ""
                proj_strs.append(f"- {p.get('name', 'Project')}: {p.get('description', '')}{techs}")
        sections.append("Projects:\n" + "\n".join(proj_strs))

    exp = profile.get("experience", []) + profile.get("internships", [])
    if exp:
        exp_strs = []
        for x in exp:
            if isinstance(x, dict):
                exp_strs.append(f"- {x.get('title', 'Intern')} at {x.get('company', 'Company')}: {', '.join(x.get('responsibilities', []))}")
        sections.append("Work & Internship Experience:\n" + "\n".join(exp_strs))

    certs = profile.get("certifications", [])
    if certs:
        cert_strs = [c.get("name") if isinstance(c, dict) else str(c) for c in certs]
        sections.append(f"Certifications: {', '.join(filter(None, cert_strs))}")

    return "\n\n".join(sections)


def call_gemini(prompt: str, fallback_text: str = "") -> str:
    """Invoke Gemini with automatic fallback models and error sanitization."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key.startswith("paste_your_"):
        return fallback_text

    try:
        from google import genai

        configured_model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        models = [configured_model] + [m for m in FALLBACK_MODELS if m != configured_model]
        client = genai.Client(api_key=api_key)

        for model in models:
            try:
                response = client.models.generate_content(model=model, contents=prompt)
                text = (getattr(response, "text", None) or "").strip()
                if text:
                    return text
            except Exception:
                continue
    except Exception:
        pass

    return fallback_text


def check_product_intent(question: str) -> bool:
    """Detect if question is specifically asking about InternSphere product operations."""
    q = question.strip().lower()
    for pattern in PRODUCT_PATTERNS:
        if re.search(pattern, q):
            return True
    return False


def check_out_of_scope_intent(question: str) -> bool:
    """Detect if question is general world trivia or completely unrelated to careers."""
    q = question.strip().lower()
    for pattern in OUT_OF_SCOPE_PATTERNS:
        if re.search(pattern, q):
            return True
    # If the user asks something like "what is 2+2" or "who wrote hamlet"
    trivia_keywords = [
        "capital of", "recipe for", "who invented", "lyrics", "weather today",
        "who directed", "movie plot", "sports league", "premier league", "cricket score"
    ]
    return any(kw in q for kw in trivia_keywords)


# ----------------------------------------------------------------------
# Core Capabilities
# ----------------------------------------------------------------------

def recommend_roles(profile: dict[str, Any]) -> dict[str, Any]:
    """Analyze resume profile and recommend tailored internship roles."""
    if not profile or not profile.get("technical_skills"):
        raise InterviewPrepError(
            "Please upload and parse your resume first. Your resume is required to personalize interview preparation.",
            400,
        )

    skills_lower = [s.lower() for s in profile.get("technical_skills", [])]
    skills_text = ", ".join(profile.get("technical_skills", []))

    # Rule-based fallback recommendations
    recommended: list[str] = []
    if any(s in skills_lower for s in ["python", "fastapi", "django", "flask", "sql", "postgresql", "node", "express"]):
        recommended.append("Backend Developer Intern")
    if any(s in skills_lower for s in ["react", "vue", "angular", "html", "css", "javascript", "typescript"]):
        recommended.append("Frontend Developer Intern")
    if any(s in skills_lower for s in ["python", "machine learning", "ml", "tensorflow", "pytorch", "rag", "deep learning", "nlp", "llm"]):
        recommended.append("AI/ML Intern")
    if any(s in skills_lower for s in ["pandas", "numpy", "data analysis", "sql", "power bi", "tableau"]):
        recommended.append("Data Science Intern")
    if any(s in skills_lower for s in ["docker", "kubernetes", "aws", "gcp", "azure", "ci/cd", "linux"]):
        recommended.append("Cloud/DevOps Intern")
    if any(s in skills_lower for s in ["python"]):
        recommended.append("Python Developer Intern")
    if any(s in skills_lower for s in ["java", "spring", "springboot"]):
        recommended.append("Java Developer Intern")

    # Ensure Software Engineer Intern is present if engineering skills exist
    if not recommended or "Backend Developer Intern" in recommended or "Frontend Developer Intern" in recommended:
        recommended.insert(0, "Software Engineer Intern")

    # Deduplicate and cap
    deduped = list(dict.fromkeys(recommended))[:5]
    fallback_reasoning = f"Recommended based on your validated resume skills ({skills_text}) and demonstrated projects."

    prompt = f"""You are an expert career counselor and technical hiring manager.
Analyze this candidate's verified resume data and recommend 4 to 5 highly fitting internship roles.

CANDIDATE RESUME:
{format_resume_context(profile)}

INSTRUCTIONS:
1. Recommend 4 to 5 specific, realistic internship roles matching the candidate's exact technologies, projects, and education.
2. Provide a 2-3 sentence explanation grounded solely in the resume facts.
3. Return ONLY a JSON object with this exact shape:
{{
  "roles": ["Software Engineer Intern", "Backend Developer Intern", ...],
  "reasoning": "..."
}}
Do NOT include Markdown fences or extra text."""

    llm_resp = call_gemini(prompt)
    if llm_resp:
        try:
            cleaned = re.sub(r"^```(?:json)?\s*", "", llm_resp.strip(), flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            data = json.loads(cleaned)
            if isinstance(data.get("roles"), list) and data["roles"]:
                return {
                    "roles": [str(r).strip() for r in data["roles"] if r],
                    "reasoning": str(data.get("reasoning") or fallback_reasoning),
                    "candidate_skills": profile.get("technical_skills", []),
                }
        except Exception:
            pass

    return {
        "roles": deduped,
        "reasoning": fallback_reasoning,
        "candidate_skills": profile.get("technical_skills", []),
    }


def get_strongest_skills(profile: dict[str, Any]) -> dict[str, Any]:
    """Identify candidate's strongest skills with resume-grounded evidence."""
    if not profile or not profile.get("technical_skills"):
        raise InterviewPrepError(
            "Please upload and parse your resume first. Your resume is required to personalize interview preparation.",
            400,
        )

    skills = profile.get("technical_skills", [])
    projects = profile.get("projects", [])

    # Local rule-based identification: check skills cited in projects or repeated
    evidence_list = []
    for skill in skills[:6]:
        matching_projs = [
            p.get("name", "Project")
            for p in projects
            if isinstance(p, dict)
            and any(skill.lower() in str(t).lower() for t in (p.get("technologies", []) + [p.get("description", "")]))
        ]
        if matching_projs:
            evidence_list.append({
                "skill": skill,
                "evidence": f"Demonstrated in {', '.join(matching_projs)}.",
            })
        else:
            evidence_list.append({
                "skill": skill,
                "evidence": "Highlighted as a core technical competency in your resume.",
            })

    fallback_explanation = (
        f"Your strongest skills ({', '.join([e['skill'] for e in evidence_list[:4]])}) "
        "are supported by your academic background and project implementations."
    )

    prompt = f"""You are a technical interview evaluator.
Identify the candidate's top 4 to 6 strongest technical skills strictly from their verified resume.

CANDIDATE RESUME:
{format_resume_context(profile)}

INSTRUCTIONS:
1. Select the standout technical skills where the candidate has tangible project evidence or experience.
2. For each skill, provide a short 1-sentence evidence note referring to specific projects or implementations in their resume.
3. Provide a concise 2-sentence summary explanation.
4. Return ONLY a JSON object:
{{
  "skills": ["Python", "FastAPI", ...],
  "explanation": "...",
  "evidence": [
    {{"skill": "Python", "evidence": "Used across multiple backend services..."}},
    ...
  ]
}}
Do NOT include markdown fences."""

    llm_resp = call_gemini(prompt)
    if llm_resp:
        try:
            cleaned = re.sub(r"^```(?:json)?\s*", "", llm_resp.strip(), flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            data = json.loads(cleaned)
            if isinstance(data.get("skills"), list) and data["skills"]:
                return {
                    "skills": data["skills"],
                    "explanation": data.get("explanation", fallback_explanation),
                    "evidence": data.get("evidence", evidence_list),
                }
        except Exception:
            pass

    return {
        "skills": [e["skill"] for e in evidence_list],
        "explanation": fallback_explanation,
        "evidence": evidence_list,
    }


def generate_interview_questions(
    profile: dict[str, Any],
    category: str = "technical",
    role: str | None = None,
    project_name: str | None = None,
) -> dict[str, Any]:
    """Generate technical, HR, or project-based questions grounded in candidate's resume."""
    if not profile:
        raise InterviewPrepError(
            "Please upload and parse your resume first. Your resume is required to personalize interview preparation.",
            400,
        )

    target_role = role or "Software Engineer Intern"
    skills = profile.get("technical_skills", [])
    projects = profile.get("projects", [])

    category_clean = category.lower().strip()
    if category_clean not in {"technical", "hr", "project"}:
        category_clean = "technical"

    # Default questions grounded in profile
    if category_clean == "technical":
        default_qs = [
            f"How have you utilized {skills[0] if skills else 'programming'} in your recent technical implementations?",
            "Explain the architecture of a REST API and how you handle error handling in your services.",
            "What considerations do you make when designing schemas for relational databases like PostgreSQL or SQLite?",
            "Can you explain the difference between synchronous and asynchronous request execution in modern frameworks?",
            "How do you test and validate your code before pushing it to production?",
        ]
        if any("rag" in s.lower() or "gemini" in s.lower() or "vector" in s.lower() for s in skills):
            default_qs.append("How does Retrieval-Augmented Generation (RAG) work, and how do embeddings enable semantic search?")
    elif category_clean == "hr":
        default_qs = [
            f"Tell me about yourself and what specifically interests you about the {target_role} position.",
            "Can you walk me through a challenging technical problem you faced in a project and how you resolved it?",
            "How do you prioritize your tasks when juggling academic deadlines and complex engineering projects?",
            "Describe a situation where you had to quickly learn a completely new technology or tool.",
            "Where do you see your technical growth progressing over the next 1-2 years?",
        ]
    else:  # project
        chosen_proj = project_name or (projects[0].get("name") if projects else "your key project")
        default_qs = [
            f"Walk me through the end-to-end architecture of {chosen_proj}.",
            f"Why did you choose the specific technology stack for {chosen_proj} over other alternatives?",
            f"What was the most difficult technical roadblock you encountered while building {chosen_proj}?",
            f"How did you design the data storage and handle edge cases or failures in {chosen_proj}?",
            f"If you had another month to work on {chosen_proj}, what optimizations or features would you add?",
        ]

    prompt = f"""You are a principal engineer conducting an interview for the role of {target_role}.
Generate 5 to 7 high-impact {category_clean.upper()} interview questions tailored directly to this candidate's verified resume.

CANDIDATE RESUME:
{format_resume_context(profile)}

ROLE: {target_role}
CATEGORY: {category_clean}
PROJECT TARGET: {project_name or 'All candidate projects'}

GUIDELINES:
- Every question must be grounded in the technologies, projects, or background present in the resume.
- For technical questions: focus on the candidate's actual technologies ({', '.join(skills[:8])}).
- For project questions: refer specifically to the named projects in their resume.
- For HR questions: personalize using candidate background and target role.
- Return ONLY a JSON object:
{{
  "category": "{category_clean}",
  "role": "{target_role}",
  "questions": [
    "Question 1...",
    "Question 2...",
    ...
  ],
  "context_summary": "Short 1-sentence note explaining how these questions connect to their resume."
}}
Do NOT include markdown fences."""

    llm_resp = call_gemini(prompt)
    if llm_resp:
        try:
            cleaned = re.sub(r"^```(?:json)?\s*", "", llm_resp.strip(), flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            data = json.loads(cleaned)
            if isinstance(data.get("questions"), list) and data["questions"]:
                return {
                    "category": category_clean,
                    "role": target_role,
                    "questions": [str(q).strip() for q in data["questions"] if q],
                    "context_summary": str(data.get("context_summary") or f"Personalized for {target_role}."),
                }
        except Exception:
            pass

    return {
        "category": category_clean,
        "role": target_role,
        "questions": default_qs,
        "context_summary": f"Personalized questions based on verified skills in your resume for {target_role}.",
    }


def generate_roadmap(profile: dict[str, Any], role: str) -> dict[str, Any]:
    """Generate a structured interview preparation roadmap for the selected role."""
    target_role = role or "Software Engineer Intern"
    skills = profile.get("technical_skills", []) if profile else []

    default_roadmap = [
        {
            "step": 1,
            "title": "Resume & Profile Fundamentals",
            "description": "Ensure your project architectures, quantified impact, and tech stack details are crisp and clear.",
            "topics": ["Project elevator pitch", "Role-relevant skill alignment", "STAR method review"],
        },
        {
            "step": 2,
            "title": "Core Programming & Data Structures",
            "description": f"Master problem-solving and algorithmic complexity using {skills[0] if skills else 'your primary language'}.",
            "topics": ["Arrays & HashMaps", "Strings & Two-Pointers", "Time & Space Complexity", "Recursion basics"],
        },
        {
            "step": 3,
            "title": "Database & Storage Concepts",
            "description": "Prepare for schema design, SQL queries, indexing, and transaction management.",
            "topics": ["Relational schemas", "JOINs and aggregations", "Transactions & ACID", "ORM vs raw SQL"],
        },
        {
            "step": 4,
            "title": f"Role-Specific Technologies ({target_role})",
            "description": f"Deep-dive into the architectural patterns and libraries essential for {target_role}.",
            "topics": ["API design & HTTP methods", "Authentication & Security", "Asynchronous processing", "State management"],
        },
        {
            "step": 5,
            "title": "Project Architecture & Deep Dive",
            "description": "Practice walking an interviewer through your code, trade-offs, and failure recovery.",
            "topics": ["System block diagram", "Why you chose your stack", "Bottlenecks & optimization", "Unit & integration testing"],
        },
        {
            "step": 6,
            "title": "Technical Interview Practice",
            "description": "Simulate live technical rounds answering questions with concise, correct code explanations.",
            "topics": ["Live whiteboard communication", "Edge cases & test cases", "Debugging in interview settings"],
        },
        {
            "step": 7,
            "title": "HR & Behavioral Preparation",
            "description": "Craft authentic answers for behavioral and cultural fit questions using STAR format.",
            "topics": ["Tell me about yourself", "Conflict & team challenges", "Handling tight deadlines", "Questions for interviewer"],
        },
        {
            "step": 8,
            "title": "Mock Interview & Final Revision",
            "description": "Run timed mock interviews, review feedback, and polish weak topics.",
            "topics": ["Mock peer interview", "Quick formula & cheat-sheet review", "Confidence and clarity drill"],
        },
    ]

    prompt = f"""You are a technical career advisor.
Generate a tailored 7-8 step interview preparation roadmap for a student targeting: {target_role}.

CANDIDATE CONTEXT:
{format_resume_context(profile) if profile else "No resume context."}

INSTRUCTIONS:
1. Adapt each step to the candidate's existing background and the specific requirements of {target_role}.
2. Return ONLY a JSON object:
{{
  "role": "{target_role}",
  "roadmap": [
    {{
      "step": 1,
      "title": "...",
      "description": "...",
      "topics": ["topic1", "topic2", ...]
    }},
    ...
  ]
}}
Do NOT include markdown fences."""

    llm_resp = call_gemini(prompt)
    if llm_resp:
        try:
            cleaned = re.sub(r"^```(?:json)?\s*", "", llm_resp.strip(), flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            data = json.loads(cleaned)
            if isinstance(data.get("roadmap"), list) and data["roadmap"]:
                return {"role": target_role, "roadmap": data["roadmap"]}
        except Exception:
            pass

    return {"role": target_role, "roadmap": default_roadmap}


def generate_skill_gap_and_path(profile: dict[str, Any], role: str) -> dict[str, Any]:
    """Identify skill gaps for interview prep and provide a phased learning path."""
    if not profile or not profile.get("technical_skills"):
        raise InterviewPrepError(
            "Please upload and parse your resume first. Your resume is required to personalize interview preparation.",
            400,
        )

    target_role = role or "Backend Developer Intern"
    user_skills = profile.get("technical_skills", [])
    user_skills_lower = {s.lower().strip() for s in user_skills}

    # Role standard skill benchmarks
    role_benchmarks: dict[str, list[str]] = {
        "backend developer": ["Python", "SQL", "FastAPI", "PostgreSQL", "Docker", "REST APIs", "Redis", "Git"],
        "frontend developer": ["JavaScript", "TypeScript", "React", "HTML5", "CSS3", "Git", "REST APIs", "Tailwind CSS"],
        "software engineer": ["Data Structures", "Algorithms", "Python", "SQL", "Git", "System Design Basics", "OOP", "Testing"],
        "ai/ml intern": ["Python", "Machine Learning", "PyTorch", "Pandas", "Scikit-Learn", "RAG", "Vector Databases", "Git"],
        "data science intern": ["Python", "SQL", "Pandas", "NumPy", "Data Visualization", "Machine Learning", "Statistics"],
    }

    # Match benchmark key
    matched_key = "software engineer"
    for k in role_benchmarks:
        if k in target_role.lower():
            matched_key = k
            break
    benchmark = role_benchmarks[matched_key]

    current: list[str] = []
    missing: list[str] = []
    for req in benchmark:
        if any(req.lower() in s or s in req.lower() for s in user_skills_lower):
            current.append(req)
        else:
            missing.append(req)

    # Skills to improve are current skills that need interview-depth mastery
    skills_to_improve = current[:3] if current else user_skills[:3]

    default_learning_path = [
        {
            "phase": "Phase 1 — Core Fundamentals",
            "title": "Solidify Foundational Knowledge",
            "skills": current[:3] or ["Programming Fundamentals", "SQL"],
            "description": "Deepen your understanding of core concepts and ensure you can explain execution mechanics.",
        },
        {
            "phase": "Phase 2 — Role Architecture",
            "title": "Master Architecture & Best Practices",
            "skills": missing[:2] or ["System Design Basics", "REST Standards"],
            "description": "Study architectural patterns, data modeling, and error-handling strategies.",
        },
        {
            "phase": "Phase 3 — Targeted Practice & Gaps",
            "title": "Bridge Key Missing Competencies",
            "skills": missing[2:] or ["Testing", "Deployment Basics"],
            "description": "Build small functional prototypes or mini-features showcasing these technologies.",
        },
        {
            "phase": "Phase 4 — Interview Synthesis",
            "title": "Live Problem Solving & Behavioral",
            "skills": ["Mock Technical Rounds", "System Walkthroughs"],
            "description": "Practice articulating trade-offs clearly under timed interview conditions.",
        },
    ]

    prompt = f"""You are a technical hiring evaluator.
Analyze this candidate's verified skills against the requirements for the role of {target_role}.

CANDIDATE RESUME SKILLS:
{', '.join(user_skills)}

TARGET ROLE: {target_role}

INSTRUCTIONS:
1. Identify:
   - "current_skills": Skills clearly present in the candidate's resume that are relevant to {target_role}. (Do NOT mark present skills as missing).
   - "skills_to_improve": Present skills that the candidate should deepen for interview readiness.
   - "missing_skills": Important industry skills for {target_role} that are NOT mentioned in the resume.
2. Formulate a 4-phase structured "learning_path" starting from their current skills and bridging the missing ones.
3. Return ONLY a JSON object:
{{
  "role": "{target_role}",
  "current_skills": ["..."],
  "skills_to_improve": ["..."],
  "missing_skills": ["..."],
  "learning_path": [
    {{
      "phase": "Phase 1 — ...",
      "title": "...",
      "skills": ["..."],
      "description": "..."
    }},
    ...
  ]
}}
Do NOT include markdown fences."""

    llm_resp = call_gemini(prompt)
    if llm_resp:
        try:
            cleaned = re.sub(r"^```(?:json)?\s*", "", llm_resp.strip(), flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            data = json.loads(cleaned)
            if isinstance(data.get("current_skills"), list) and isinstance(data.get("missing_skills"), list):
                return {
                    "role": target_role,
                    "current_skills": data["current_skills"],
                    "skills_to_improve": data.get("skills_to_improve", skills_to_improve),
                    "missing_skills": data["missing_skills"],
                    "learning_path": data.get("learning_path", default_learning_path),
                }
        except Exception:
            pass

    return {
        "role": target_role,
        "current_skills": current,
        "skills_to_improve": skills_to_improve,
        "missing_skills": missing,
        "learning_path": default_learning_path,
    }


# ----------------------------------------------------------------------
# Document Upload & RAG Processing
# ----------------------------------------------------------------------

def process_interview_document(
    file_bytes: bytes,
    original_filename: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Extract text from PDF/DOCX, clean, chunk, and embed."""
    suffix = os.path.splitext(original_filename)[1].lower()
    if suffix not in {".pdf", ".docx"}:
        raise InterviewPrepError("Only .pdf and .docx files are supported.", 415)

    raw_text = extract_text(file_bytes, suffix)
    if not raw_text.strip():
        raise InterviewPrepError("The uploaded document contains no readable text.", 422)

    # Clean text
    cleaned_text = re.sub(r"\s+", " ", raw_text).strip()

    # Split into chunks with overlap
    words = cleaned_text.split()
    chunks_text: list[str] = []
    start = 0
    words_per_chunk = max(30, DOCUMENT_CHUNK_SIZE // 6)
    overlap = max(10, words_per_chunk // 4)

    while start < len(words):
        piece = words[start : start + words_per_chunk]
        chunk_str = " ".join(piece)
        if chunk_str.strip():
            chunks_text.append(chunk_str)
        start += max(1, len(piece) - overlap)

    if not chunks_text:
        chunks_text = [cleaned_text]

    # Generate embeddings using existing embedding provider
    vectors = _embed(chunks_text)
    chunks: list[dict[str, Any]] = []
    for idx, (text_piece, vector) in enumerate(zip(chunks_text, vectors)):
        chunks.append({
            "chunk_index": idx,
            "content": text_piece,
            "embedding": vector,
        })

    return raw_text, chunks


def search_document_chunks(
    doc: InterviewDocument,
    query: str,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Retrieve top-k relevant chunks from an uploaded document."""
    if not doc.chunks:
        return []

    query_vector = _embed([query])[0]
    query_terms = set(_terms(query))

    scored: list[tuple[float, dict[str, Any]]] = []
    for chunk in doc.chunks:
        content = chunk.get("content", "")
        embedding = chunk.get("embedding", [])
        chunk_terms = set(_terms(content))

        lexical = len(query_terms & chunk_terms) / max(1, len(query_terms))
        semantic = max(0.0, _dot(query_vector, embedding)) if embedding else 0.0
        score = 0.6 * lexical + 0.4 * semantic
        if score > 0.04:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for score, chunk in scored[:top_k]]


# ----------------------------------------------------------------------
# Conversational Chat Agent with Grounded RAG & Intent Routing
# ----------------------------------------------------------------------

def find_previous_user_question(history: list[dict[str, Any]]) -> str | None:
    """Find the previous substantive user question before the current one."""
    user_questions = [msg["content"] for msg in history if msg.get("role") == "user"]
    if not user_questions:
        return None
    candidates = user_questions[:-1] if len(user_questions) >= 2 else user_questions
    followup_patterns = {"why", "why?", "why is that", "why is that?", "how", "how?", "tell me why", "explain"}
    for q in reversed(candidates):
        if q.strip().lower() not in followup_patterns and len(q.strip()) > 3:
            return q
    return candidates[-1] if candidates else None


def chat_with_agent(
    question: str,
    profile: dict[str, Any] | None,
    history: list[dict[str, Any]] | None = None,
    selected_role: str | None = None,
    document: InterviewDocument | None = None,
) -> tuple[str, list[str], bool, bool]:
    """Generate a grounded, contextual response with session memory and intent routing.

    Returns: (answer, sources, is_product_redirect, is_out_of_scope)
    """
    history = history or []
    q_clean = question.strip()
    q_norm = q_clean.lower()

    # 1. Product Question Intent Detection (Specification Item 25)
    if check_product_intent(q_clean):
        msg = (
            "This is a product-related question. Please ask this in the AI Assistant section.\n\n"
            "The AI Assistant is specialized in InternSphere platform features such as internship matching, "
            "application tracking, withdrawing applications, and generating cover letters."
        )
        return (msg, ["InternSphere AI Assistant"], True, False)

    # 2. Irrelevant / World Trivia Intent Detection (Specification Item 26)
    if check_out_of_scope_intent(q_clean):
        msg = (
            "This question is outside the scope of the Interview Preparation Agent. "
            "I can help with interview preparation, your resume, career roles, learning paths, or uploaded documents."
        )
        return (msg, [], False, True)

    # 3. Conversational Session Memory (Specification Item 23)
    # e.g., "What was my previous question?"
    if any(p in q_norm for p in [
        "what was my previous question",
        "what was my last question",
        "what did i ask previously",
        "what did i ask before",
        "repeat my previous question",
    ]):
        prev_q = find_previous_user_question(history)
        if prev_q:
            return (f'Your previous question was: "{prev_q}"', ["Session History"], False, False)
        else:
            return ("You have not asked any previous questions in this chat session yet.", ["Session History"], False, False)

    # 4. Check if resume is available (Specification Item 6)
    has_resume = bool(profile and profile.get("technical_skills"))
    # Allow document-only questions if document is present, otherwise require resume
    if not has_resume and not document:
        return (
            "Please upload and parse your resume first. Your resume is required to personalize interview preparation.",
            [],
            False,
            False,
        )

    # 5. Retrieve Context
    sources: list[str] = []
    resume_context_str = ""
    if has_resume:
        resume_context_str = format_resume_context(profile)
        sources.append("Candidate Resume")

    doc_context_str = ""
    if document:
        top_chunks = search_document_chunks(document, q_clean, top_k=4)
        if top_chunks:
            doc_context_str = "\n\n".join([f"Excerpt: {c.get('content')}" for c in top_chunks])
            sources.append(f"Document: {document.filename}")
        else:
            # Document exists but query terms didn't match closely
            doc_context_str = f"Document '{document.filename}' was searched, but no closely matching sections were found for this query."

    # Format history turns for context
    history_snippets = []
    for msg in history[-8:]:  # Last 4 turns
        role = "User" if msg.get("role") == "user" else "Assistant"
        history_snippets.append(f"{role}: {msg.get('content')}")
    history_str = "\n".join(history_snippets)

    active_role = selected_role or "Software Engineer Intern"

    # 6. Specific Document-Only Fallback check
    # If the user is specifically asking about the document and no document is attached or info is absent
    doc_query_words = ["document", "pdf", "file", "guide", "uploaded document", "this doc"]
    is_doc_query = any(w in q_norm for w in doc_query_words)

    if is_doc_query and not document:
        return (
            "You haven't attached or uploaded a document for this question. "
            "Please upload a PDF or DOCX file under Document Preparation, and I'll be happy to answer questions from it.",
            [],
            False,
            False,
        )

    # 7. Gemini Prompt Construction
    prompt = f"""You are the InternSphere AI Interview Preparation Coach.
You provide high-impact, professional, concise, and technically accurate interview preparation.

CANDIDATE RESUME CONTEXT:
{resume_context_str if resume_context_str else "No resume uploaded."}

UPLOADED DOCUMENT CONTEXT:
{doc_context_str if doc_context_str else "No document attached."}

ACTIVE TARGET ROLE:
{active_role}

RECENT CONVERSATION HISTORY (CURRENT SESSION ONLY):
{history_str if history_str else "No prior turns in this session."}

USER QUESTION:
{question}

CRITICAL GROUNDING RULES:
1. NEVER fabricate skills, projects, degrees, or experience not present in the candidate resume context. If a skill or detail is absent, do not claim they know it.
2. If the user asks about the uploaded document, ground your answer ONLY in the UPLOADED DOCUMENT CONTEXT. If the requested information is not in the document context, you MUST state:
   "I couldn't find that information in the uploaded document."
3. When answering questions like "What are my strongest skills?", provide the answer with short evidence from the resume.
4. When asked for answer guidance (e.g. "Give me the answer", "Answer question 2", "How should I answer this?"), provide a clear, concise, technically sound, interview-ready answer using STAR format or structured bullet points.
5. If both resume and document are available and the user asks for combined insights (e.g. "Based on my resume and this guide..."), synthesize both contexts seamlessly.
6. Maintain conversational continuity with recent messages in this session.
7. Format with clean markdown headers (###), bullet points, and numbered lists where appropriate. Keep answers professional and avoid excessive emojis.
"""

    fallback_answer = (
        f"Based on your resume for the {active_role} role, focus on explaining your demonstrated skills "
        f"({', '.join(profile.get('technical_skills', [])[:5]) if profile else 'core technologies'}), "
        "your project architectures, and handling technical trade-offs."
    )

    llm_answer = call_gemini(prompt, fallback_text=fallback_answer)
    return (llm_answer, sources, False, False)
