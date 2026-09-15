# InternSphere — AI Career Companion Agent for Internship Matching and Interview Preparation

[![Python Version](https://img.shields.io/badge/Python-3.12%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-red.svg?logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-SDK%201.0%2B-8E75B2.svg?logo=google&logoColor=white)](https://ai.google.dev/)
[![Database](https://img.shields.io/badge/Database-SQLite%20%7C%20PostgreSQL-4169E1.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Web Speech API](https://img.shields.io/badge/Web%20Speech%20API-Voice%20Audio-green.svg)](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API)
[![License](https://img.shields.io/badge/License-Proprietary%20%2F%20Academic-lightgrey.svg)](#license)

> **An AI Career Companion Agent for Internship Matching and Interview Preparation that helps students discover relevant internships, analyze skill gaps, generate personalized cover letters, prepare for interviews, and interact with an AI career assistant.**

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Key Features](#2-key-features)
3. [Technology Stack](#3-technology-stack)
4. [System Architecture](#4-system-architecture)
5. [Repository Structure](#5-repository-structure)
6. [Prerequisites](#6-prerequisites)
7. [Cloning the Repository](#7-cloning-the-repository)
8. [Backend Setup](#8-backend-setup)
9. [Database Setup (SQLite & PostgreSQL)](#9-database-setup-sqlite--postgresql)
10. [Gemini / AI Configuration](#10-gemini--ai-configuration)
11. [Frontend Setup & Static Serving](#11-frontend-setup--static-serving)
12. [Running the Application (Quick Start)](#12-running-the-application-quick-start)
13. [Test Login Credentials](#13-test-login-credentials)
14. [First-Time User Flow (How to Test InternSphere)](#14-first-time-user-flow-how-to-test-internsphere)
15. [API Documentation](#15-api-documentation)
16. [Testing](#16-testing)
17. [RAG / Internship Matching Explanation](#17-rag--internship-matching-explanation)
18. [AI Assistant vs. Interview Preparation Agent](#18-ai-assistant-vs-interview-preparation-agent)
19. [File Uploads & Validation](#19-file-uploads--validation)
20. [Security Best Practices](#20-security-best-practices)
21. [Troubleshooting](#21-troubleshooting)
22. [Development Notes](#22-development-notes)
23. [Git & Environment Security](#23-git--environment-security)
24. [Future Scope](#24-future-scope)
25. [License](#25-license)

---

## 1. Project Overview

InternSphere is an intelligent, full-stack internship matching and career acceleration platform designed for **students, internship seekers, and fresh graduates**. 

Finding an internship is often inefficient: candidates struggle to match their skills with diverse job postings, assess their technical deficiencies, tailor cover letters for every application, and prepare for role-specific interview questions.

InternSphere addresses these hurdles by uniting deterministic parsing, semantic search (RAG), and Google Gemini LLMs into a unified, responsive single-page web dashboard:

- **End-to-End Career Support**: From resume ingestion and profile synchronization to automated cover letter writing and multi-turn interview coaching.
- **Explainable Matching**: Evaluates candidates against curated internship postings using hybrid scoring (semantic vector similarity + required/preferred skill ratios).
- **Domain-Isolated AI Agents**: Separates platform guidance (Product Assistant) from resume-tailored career coaching (Interview Preparation Agent).

---

## 2. Key Features

| Feature | What the User Can Do | How the System Processes It |
| :--- | :--- | :--- |
| **Authentication & Accounts** | Register, log in, change password, request reset tokens, manage account status. | Issues stateless JWT bearer tokens (`HS256`); securely hashes passwords using `bcrypt` via `passlib`. |
| **Profile Management** | Edit educational background, bio, social links, GPA, and upload profile photos. | Stores profile data in `user_profiles` with cascade relationships; persists photos in `uploads/profile_images/`. |
| **Hybrid Resume Parsing** | Upload `.pdf` or `.docx` resumes (up to 5 MB). View parsed JSON data. | `pdfplumber`/`python-docx` extracts text; deterministic regex identifies contacts/links; Gemini extracts structured entities; `merge.py` unifies them into the `resumes` table. |
| **Semantic Internship Retrieval** | Browse internship listings or trigger AI-driven matching. | Re-indexes dataset into a 384-dimensional vector store (`internship_vector_index.json`) using deterministic feature hashing or Gemini embeddings. |
| **Skill-Gap Analysis** | Inspect exact matching skills, missing required skills, and missing preferred skills. | Compares normalized candidate skill sets against listing requirements using canonical synonyms and calculates percentage matches. |
| **Application Tracking** | Track internship applications, update statuses, or withdraw active submissions. | Persists records in `applications` with unique constraints (`user_id`, `internship_id`) to prevent duplicate submissions. |
| **AI Cover Letter Generator** | Generate customized cover letters for any internship; edit inline; download PDF/TXT. | Feeds candidate facts and internship requirements to Gemini with anti-hallucination constraints; generates standard PDF-1.4 directly via Python without external dependencies. |
| **Product AI Assistant** | Ask questions about InternSphere features, navigation, and matching workflows. | Uses RAG over `data/product_knowledge.json` with persisted multi-turn chat sessions in SQLite/PostgreSQL (`chat_sessions`, `chat_messages`). |
| **Interview Preparation Agent** | Receive tailored role recommendations, technical/HR questions, roadmaps, and answer evaluations. | Evaluates parsed resume context, categorizes questions, isolates conversation threads, and handles out-of-scope queries. |
| **Voice Audio Read-Aloud** | Listen to interview coaching responses and model answers hands-free. | Leverages browser-native Web Speech API (`window.speechSynthesis`) with pulse animation and audio controls. |
| **Custom Study Document RAG** | Upload domain-specific study notes or job descriptions for interview grounding. | Extracts and chunks documents into `interview_documents` for vector-backed conversational retrieval during interview prep. |

---

## 3. Technology Stack

InternSphere is built strictly with the following verified technologies:

- **Frontend**:
  - **Core UI**: Vanilla HTML5, modern CSS3 (custom responsive design system, dark/light themes, glassmorphism modal dialogs).
  - **Logic**: Vanilla JavaScript (ES6+ modular, asynchronous `fetch`, dynamic DOM rendering).
  - **Voice API**: Browser-native Web Speech API (`window.speechSynthesis`).
  - *Note: The frontend is a clean Single Page Application (SPA) served directly by FastAPI static files. No Node.js runtime or npm build process is required.*
- **Backend**:
  - **Framework**: Python 3.12+, FastAPI (v0.115+), Uvicorn (v0.30+ ASGI server).
  - **Validation & Serialization**: Pydantic v2 (v2.8+), Email-Validator.
  - **Multipart Uploads**: `python-multipart`.
- **Database & ORM**:
  - **Database**: SQLite (default local development at `./resume_parser.db`) or PostgreSQL.
  - **ORM**: SQLAlchemy 2.0+ with declarative base, relational cascades, and schema update utilities.
- **Authentication & Security**:
  - **Tokens**: Stateless JWT (JSON Web Tokens) via `python-jose[cryptography]`.
  - **Hashing**: `passlib[bcrypt]` with bcrypt algorithms.
- **AI & Large Language Models (LLM)**:
  - **SDK**: Google GenAI official SDK (`google-genai>=1.0.0`).
  - **Models**: `gemini-3.5-flash-lite`, `gemini-3.6-flash`, `gemini-flash-latest`.
- **RAG & Vector Retrieval**:
  - **Vector Store**: Persisted JSON vector index (`data/internship_vector_index.json`, `data/product_knowledge_index.json`).
  - **Embedding Provider**: 
    - `local` (default): Deterministic 384-dimensional feature hashing using SHA-256 and word n-grams (zero external API calls required).
    - `gemini`: Gemini embeddings via `gemini-embedding-001`.
  - **Search**: Normalized Cosine Similarity vector search.
- **Document Processing**:
  - **PDF Extraction**: `pdfplumber`.
  - **DOCX Extraction**: `python-docx`.
  - **PDF Generation**: Custom pure-Python PDF-1.4 binary stream generator (`services/pdf_generator.py`).
- **Testing & Tooling**:
  - **Testing**: Python Standard Library `unittest`.
  - **Version Control**: Git / GitHub.

---

## 4. System Architecture

```text
                                  +-----------------------+
                                  |     Web Browser       |
                                  |  (HTML5 / CSS3 / JS)  |
                                  |   [Web Speech API]    |
                                  +-----------+-----------+
                                              |
                                     HTTP / REST Requests
                                     (Bearer JWT Header)
                                              |
                                              v
                                  +-----------------------+
                                  |    FastAPI Backend    |
                                  |   (Port 8000 / ASGI)  |
                                  +-----------+-----------+
                                              |
                    +-------------------------+-------------------------+
                    |                         |                         |
                    v                         v                         v
        +-----------------------+ +-----------------------+ +-----------------------+
        | Auth & Profile Engine | |  Parsing & Doc Engine | | RAG & Match Engine    |
        | - JWT verification    | | - pdfplumber (PDF)    | | - Cosine similarity   |
        | - bcrypt passlib      | | - python-docx (DOCX)  | | - Skill ratio scorer  |
        | - CRUD routers        | | - Regex + Gemini LLM  | | - Vector index JSON   |
        +-----------+-----------+ +-----------+-----------+ +-----------+-----------+
                    |                         |                         |
                    +-------------------------+-------------------------+
                                              |
                                              v
                              +-------------------------------+
                              |    SQLAlchemy 2.0 ORM Engine  |
                              +---------------+---------------+
                                              |
                       +----------------------+----------------------+
                       |                                             |
                       v                                             v
        +-------------------------------+             +-------------------------------+
        |      Database Storage         |             |      AI & Retrieval APIs      |
        | - SQLite (resume_parser.db)   |             | - Google GenAI SDK (Gemini)   |
        | - PostgreSQL (Production)     |             | - Local Feature Embeddings    |
        | - Uploaded files in uploads/  |             | - Gemini Embeddings API       |
        +-------------------------------+             +-------------------------------+
```

### Major Data Flows

#### A. Authentication Flow
1. User submits credentials to `POST /register` or `POST /login`.
2. Backend validates via `passlib[bcrypt]`.
3. Upon success, an access token is minted (`HS256`, 60 min expiration) via `auth.py`.
4. The client stores the token in memory/localStorage and passes it in the `Authorization: Bearer <token>` header on subsequent requests.

#### B. Resume Parsing Flow
1. Authenticated user uploads `.pdf` or `.docx` to `POST /resume/upload`.
2. File is validated (extension check and max 5 MB limit) and saved with a unique UUID in `uploads/`.
3. `extract_text.py` extracts raw text via `pdfplumber` or `python-docx`.
4. `regex_extractor.py` performs deterministic regex matching for emails, phones, and profile URLs.
5. `llm_extractor.py` sends raw text to Gemini to extract structured entities (skills, experience, education, projects).
6. `merge.py` reconciles deterministic and LLM outputs, storing the final JSON in the `resumes` table.

#### C. Internship Matching Flow
1. User requests recommendations via `POST /internships/match`.
2. Backend queries the candidate's active profile and latest parsed resume.
3. Candidate skills and project terms are synthesized into a search query.
4. Cosine similarity retrieves top-$k$ internship records from `data/internship_vector_index.json`.
5. Canonical skill matching calculates overlap ratios for required skills (80% weight) and preferred skills (20% weight).
6. Overall match score is computed: $\text{Score} = \min(100, 0.35 \times \text{Semantic} + 0.65 \times \text{SkillMatch})$.

#### D. AI Assistant Flow
1. User sends a question to `POST /assistant/chat` (with optional `session_id`).
2. Prior session conversation history is retrieved for memory context.
3. Relevant product documentation chunks are retrieved from `data/product_knowledge.json`.
4. Grounded prompt is sent to Gemini; response and source references are saved to `chat_messages` and returned.

#### E. Interview Preparation Flow
1. Candidate requests role recommendations or questions via `POST /interview-prep/questions`.
2. Candidate's parsed resume profile is retrieved from the database.
3. Gemini generates tailored questions split into **Technical**, **HR/Behavioral**, and **Project Deep-Dive**.
4. Multi-turn interview coaching is persisted in `interview_sessions` and `interview_messages`.
5. User can click "🔊 Listen" on any response to activate the browser's Web Speech API read-aloud playback.

#### F. Cover Letter Generation Flow
1. User requests a cover letter for a specific internship via `POST /cover-letters/generate`.
2. Backend fetches verified candidate profile facts and official internship requirements.
3. Gemini synthesizes a tailored cover letter using strict anti-hallucination instructions.
4. User can edit the text (`PUT /cover-letters/{id}`) and download it as `.txt` or a clean PDF-1.4 file (`GET /cover-letters/{id}/pdf`).

---

## 5. Repository Structure

```text
AI_INTERNSHIP_APPLICATION_AGENT/
├── main.py                       # FastAPI entry point, exception handlers, static SPA mount
├── database.py                   # SQLAlchemy engine, session maker, SQLite PRAGMA & safe migrations
├── models.py                     # 10 Declarative ORM models & table relationships
├── schemas.py                    # Pydantic v2 request/response validation schemas
├── config.py                     # Environment variable loader (.env integration)
├── auth.py                       # bcrypt password hashing & JWT token management
├── crud.py                       # Database helper functions for users, profiles, and resumes
├── dependencies.py               # Dependency injection: CurrentUser and DBSession
├── extract_text.py               # Raw text extraction from PDF (pdfplumber) and DOCX (python-docx)
├── regex_extractor.py            # Deterministic contact & skill regex parser
├── llm_extractor.py              # Gemini structured JSON resume extraction
├── merge.py                      # Reconciliation pipeline merging regex and LLM outputs
├── requirements.txt              # Core Python dependencies
├── .env.example                  # Environment configuration template
├── README.md                     # Comprehensive project documentation
├── data/
│   ├── internships.json          # Seed internship knowledge base dataset
│   ├── internship_vector_index.json # Persisted 384-d vector embeddings index
│   ├── product_knowledge.json    # Platform knowledge base for AI Assistant
│   └── product_knowledge_index.json # Vector index for platform documentation
├── routers/
│   ├── auth_routes.py            # /me, /register, /login, /forgot-password, /reset-password
│   ├── profile_routes.py         # /profile (CRUD), /profile/picture, /account deletion
│   ├── resume_routes.py          # /resume/upload, /resume/list, /resume/{id}/download
│   ├── internship_routes.py      # /internships, /internships/ingest, /internships/match
│   ├── applications_routes.py    # /applications (CRUD, status updates, withdrawal)
│   ├── cover_letter_routes.py    # /cover-letters/generate, edit, PDF/TXT export
│   ├── assistant_routes.py       # /assistant/sessions, /assistant/chat
│   └── interview_prep_routes.py  # /interview-prep/status, /questions, /chat, /documents
├── services/
│   ├── resume_service.py         # End-to-end resume extraction wrapper
│   ├── internship_index.py       # Vector indexing, chunking, and similarity search
│   ├── internship_matcher.py     # Canonical skill scoring & grounded recommendation explanations
│   ├── cover_letters.py          # Grounded cover letter prompt construction & generation
│   ├── product_assistant.py      # Grounded product assistant with conversational memory
│   ├── interview_prep_service.py # Tailored interview coach, roadmaps, question generation
│   └── pdf_generator.py          # Zero-dependency Python binary PDF-1.4 builder
├── tests/
│   ├── test_candidate_matching.py # Synthetic candidate profile matching tests
│   ├── test_matching.py          # Domain-specific behavior & skill gap checks
│   ├── test_interview_prep.py    # Interview coach prompt & evaluation tests
│   ├── test_interview_prep_api.py # Protected interview preparation endpoint tests
│   └── test_agent_sessions_and_corrections.py # Multi-turn session memory tests
├── web/
│   ├── index.html                # Single Page Application dashboard UI
│   ├── styles.css                # Custom CSS3 styles, theme variables, glassmorphic layout
│   └── app.js                    # Modular frontend state, API client, router, voice controls
└── uploads/                      # Auto-created storage for resumes and profile images
```

---

## 6. Prerequisites

Ensure the following runtimes and tools are installed on your system:

- **Python**: Version **3.12+** (required for modern type annotations and FastAPI compatibility).
- **Git**: Version 2.30+ for cloning and version management.
- **Google Gemini API Key**: Obtain a free API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
- **PostgreSQL** *(Optional)*: Version 14+ if choosing PostgreSQL over the default local SQLite database.
- **Modern Web Browser**: Google Chrome, Mozilla Firefox, Microsoft Edge, or Safari with Web Speech API support.
- *Node.js / npm: **Not required** — the web dashboard is served directly by FastAPI as optimized static assets.*

---

## 7. Cloning the Repository

Clone the project repository from GitHub:

```bash
git clone https://github.com/SriHarshitha137/AI-Career-Companion Agent for Internship Matching and Interview Preparation.git
cd AI_INTERNSHIP_APPLICATION_AGENT
```

### Checking Branches

The primary branches containing complete implementations are `main` and `final-implementation`:

```bash
# Verify available branches
git branch -a

# Ensure you are on the current working branch
git checkout final-implementation
```

---

## 8. Backend Setup

Follow these exact steps to set up the Python backend environment:

### Step 1: Create a Virtual Environment

- **Windows (PowerShell)**:
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```
  *(If PowerShell displays an execution policy error, run `Set-ExecutionPolicy -Scope Process Bypass` and activate again).*

- **Linux / macOS**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

### Step 2: Install Dependencies

Upgrade `pip` and install packages from `requirements.txt`:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

Copy `.env.example` to create your local `.env` file:

- **Windows (PowerShell)**:
  ```powershell
  Copy-Item .env.example .env
  ```
- **Linux / macOS**:
  ```bash
  cp .env.example .env
  ```

Open `.env` in an editor and set your configuration variables:

```ini
# Core AI & Security
GEMINI_API_KEY=your_google_ai_studio_key_here
JWT_SECRET_KEY=replace-with-a-long-random-secret-key-at-least-32-chars
GEMINI_MODEL=gemini-3.6-flash

# Database Connection (Default is SQLite)
DATABASE_URL=sqlite:///./resume_parser.db

# RAG & Embeddings
# Use "local" for deterministic zero-dependency offline embeddings.
# Set to "gemini" to use Gemini cloud embeddings.
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=gemini-embedding-001
INTERNSHIP_DATASET_PATH=data/internships.json
INTERNSHIP_INDEX_PATH=data/internship_vector_index.json
INTERNSHIP_CHUNK_SIZE=850
VECTOR_DIMENSIONS=384
PRODUCT_KNOWLEDGE_PATH=data/product_knowledge.json
```

---

## 9. Database Setup (SQLite & PostgreSQL)

InternSphere uses SQLAlchemy 2.0 ORM, offering seamless plug-and-play support for both SQLite and PostgreSQL.

### Option A: Local SQLite (Default — Recommended for Fast Start)
- **Zero Configuration**: No installation or manual table creation needed.
- On startup, `main.py` invokes `Base.metadata.create_all(bind=engine)` and `apply_safe_schema_updates()`, automatically creating `resume_parser.db` and all required tables with cascade rules.

### Option B: PostgreSQL Setup (Production & Relational Mode)
If you prefer a production PostgreSQL database:

1. **Install PostgreSQL** (via installer, package manager, or Docker).
2. **Create a Database** in PostgreSQL CLI (`psql`):
   ```sql
   CREATE DATABASE internsphere_db;
   ```
3. **Configure Connection String in `.env`**:
   ```ini
   DATABASE_URL=postgresql://postgres:your_password@localhost:5432/internsphere_db
   ```
   *(Ensure the `psycopg2-binary` or `asyncpg` driver is installed in your virtual environment if utilizing PostgreSQL).*
4. **Table Auto-Generation**: Tables are automatically built upon starting the application. No manual migration scripts are required.

### Seed & Vector Data
The repository ships with pre-populated internship listings in `data/internships.json` and a built vector index in `data/internship_vector_index.json`. If you wish to re-index at any time, log into the dashboard or invoke `POST /internships/ingest`.

---

## 10. Gemini / AI Configuration

InternSphere relies on Google Gemini for structured parsing, cover letter writing, grounded FAQ responses, and interview coaching.

1. **Get an API Key**: Visit [Google AI Studio](https://aistudio.google.com/app/apikey) and generate a free API key.
2. **Set in `.env`**:
   ```ini
   GEMINI_API_KEY=your_actual_api_key_here
   ```
3. **Model Selection**:
   - `gemini-3.5-flash-lite`: Fast, cost-efficient default for chat, interview coaching, and parsing.
   - `gemini-3.6-flash`: High reasoning capability for nuanced evaluation.
   - Automatic fallbacks are built into `product_assistant.py` and `interview_prep_service.py` (`gemini-3.5-flash-lite` $\rightarrow$ `gemini-3.6-flash` $\rightarrow$ `gemini-flash-latest`).

> [!CAUTION]
> Never commit your `.env` file or publish your Gemini API key to GitHub. The `.gitignore` file is pre-configured to keep your secrets private.

---

## 11. Frontend Setup & Static Serving

The InternSphere frontend is designed for instant accessibility without build tooling:

- **Location**: All client-side files reside in the `web/` directory (`index.html`, `styles.css`, `app.js`).
- **No Build Steps**: You **do not** need to execute `npm install` or `npm run build`.
- **Static Mounting**: FastAPI mounts `/web` at startup via `StaticFiles(directory="web")` and handles client-side SPA routing (`/dashboard`, `/profile`, `/resumes`, `/internships`, `/matches`, `/skill-gap`, `/applications`, `/cover-letters`, `/assistant`, `/interview-prep`).

---

## 12. Running the Application (Quick Start)

Launch the application with a single terminal command:

```powershell
# Activate virtual environment (if not already activated)
.\.venv\Scripts\Activate.ps1

# Run the Uvicorn ASGI server
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Access the application in your browser:

- **Web Dashboard**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive Swagger API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative ReDoc Docs**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 13. Test Login Credentials

> [!NOTE]
> **No Pre-Seeded Default Account**: To guarantee security and prevent hardcoded credentials across public clones, the repository does not ship with a hardcoded static demo user.

### How to Access the App:
1. Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.
2. Click **Create an Account** (or navigate to `/register`).
3. Enter your preferred username, email, and password (e.g., `testuser@example.com` / `TestPass@123`).
4. Click **Sign In** and use your new credentials.
5. **Initial Setup**: To test matching and interview preparation, navigate to **Profile** or **Resume Upload** to upload a sample resume.

---

## 14. First-Time User Flow (How to Test InternSphere)

Experience the complete end-to-end user journey in 10 simple steps:

1. **Register & Log In**: Create an account on the registration page and log in to obtain your session token.
2. **Complete Profile**: Go to **Profile**, add your educational background, college name, CGPA, and primary technical skills.
3. **Upload Resume**: Go to **Resume Upload** and upload a `.pdf` or `.docx` resume.
4. **Inspect Parsed Extraction**: Observe extracted technical skills, soft skills, contact info, and projects parsed by the hybrid regex/Gemini pipeline.
5. **Explore Internship Matches**: Navigate to **Matching**; the system analyzes your profile and resume against the dataset to rank recommendations with match percentages.
6. **Analyze Skill Gaps**: Click on any internship card to inspect exact matching skills, missing required skills, and missing preferred skills.
7. **Apply to an Internship**: Click **Apply** to link your parsed resume and submit an application tracked in **Applications**.
8. **Generate Cover Letter**: Under **Cover Letters**, select an internship and click **Generate**. Review the drafted letter, edit inline, and click **Download PDF** or **Download TXT**.
9. **Chat with AI Assistant**: Open the **AI Assistant** tab to ask questions about platform features, application statuses, or internship guidance.
10. **Prepare for Interviews**:
    - Open **Interview Prep**.
    - Review recommended roles based on your uploaded resume.
    - Generate role-specific interview questions (Technical, HR, and Project).
    - Review answer guidance and roadmaps.
    - Click **🔊 Listen** on any response to test browser voice audio synthesis.

---

## 15. API Documentation

FastAPI provides an auto-generated, interactive Swagger UI available at `http://127.0.0.1:8000/docs`.

### Primary API Route Groups

| Group | Method & Endpoint | Description |
| :--- | :--- | :--- |
| **Authentication** | `POST /register` | Create a new user account |
| | `POST /login` | Authenticate and receive a JWT access token |
| | `GET /me` | Retrieve the authenticated user's details |
| | `POST /forgot-password` | Request a password reset token |
| | `POST /reset-password` | Reset password using a valid token |
| **Profile** | `GET /profile` | Fetch owner profile details |
| | `PUT /profile` | Update profile information, skills, and education |
| | `POST /profile/picture` | Upload profile image (`.png`, `.jpg`, `.jpeg`, `.webp`) |
| **Resume** | `POST /resume/upload` | Upload and parse PDF/DOCX resume |
| | `GET /resume/list` | List all resumes belonging to the user |
| | `GET /resume/{id}/download` | Download stored original resume file |
| **Internships** | `GET /internships` | List all internships from the knowledge base |
| | `POST /internships/match` | Perform semantic vector matching + skill gap ranking |
| | `POST /internships/ingest` | Re-index vector embeddings from dataset |
| **Applications** | `POST /applications` | Submit application for an internship |
| | `GET /applications` | List user's active/past applications |
| | `POST /applications/{id}/withdraw` | Withdraw an application |
| **Cover Letters** | `POST /cover-letters/generate` | Generate Gemini cover letter using candidate facts |
| | `GET /cover-letters/{id}/pdf` | Download binary PDF-1.4 cover letter |
| **AI Assistant** | `POST /assistant/chat` | Ask platform questions with multi-turn session memory |
| | `GET /assistant/sessions` | Retrieve conversation session history |
| **Interview Prep** | `GET /interview-prep/status` | Check resume availability and role recommendations |
| | `POST /interview-prep/questions` | Generate tailored Technical, HR, and Project questions |
| | `POST /interview-prep/chat` | Interactive multi-turn coaching session |
| | `POST /interview-prep/documents/upload` | Upload custom study guide or job description for RAG |

---

## 16. Testing

The project uses Python's standard library `unittest` framework to validate business logic, RAG pipelines, and API routes without external testing dependencies.

### Running the Test Suite

Run all discovery tests from the project root:

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run tests
python -m unittest discover -s tests -p "test_*.py"
```

### Test Coverage Areas
- `tests/test_candidate_matching.py`: Validates recommendation algorithms across synthetic candidate profiles (Backend, ML, Generative AI).
- `tests/test_matching.py`: Verifies skill normalization, synonym dictionaries, and scoring edge cases.
- `tests/test_interview_prep.py`: Tests question generation, roadmap synthesis, and STAR answer guidance.
- `tests/test_interview_prep_api.py`: Validates protected interview routes, authorization checks, and payload schemas.
- `tests/test_agent_sessions_and_corrections.py`: Verifies session isolation and multi-turn conversational history.

---

## 17. RAG / Internship Matching Explanation

InternSphere implements a hybrid retrieval-augmented matching pipeline that pairs semantic vector retrieval with explicit requirement calculations:

```text
       Candidate Profile + Uploaded Resume
                       ↓
         Extract Structured Skills & Facts
                       ↓
             Generate Search Query
                       ↓
         Cosine Similarity Search (RAG)
        (384-dimensional Vector Embeddings)
                       ↓
        Candidate Internship Candidates (Top-K)
                       ↓
     Canonical Skill Overlap Ratio Evaluation
 (80% Required Skills Match + 20% Preferred Skills Match)
                       ↓
     Hybrid Weighted Scoring Function (0 - 100%)
                       ↓
    Ranked Recommendations with Grounded Explanations
```

### Matching Formula:
$$\text{Semantic Similarity} = \text{round}\Big(\min\big(100, \max(0, \text{CosineScore} \times 100)\big)\Big)$$
$$\text{Skill Match \%} = \text{round}\Big(100 \times \big(0.80 \times \text{RequiredRatio} + 0.20 \times \text{PreferredRatio}\big)\Big)$$
$$\text{Overall Match Score} = \text{round}\Big(\min\big(100, 0.35 \times \text{Semantic Similarity} + 0.65 \times \text{Skill Match \%}\big)\Big)$$

---

## 18. AI Assistant vs. Interview Preparation Agent

InternSphere maintains clear separation of concerns between its two AI engines:

| Dimension | AI Assistant (`/assistant`) | Interview Preparation Agent (`/interview-prep`) |
| :--- | :--- | :--- |
| **Primary Scope** | Platform guide, navigation, feature FAQs | In-depth career coaching & technical interview preparation |
| **Knowledge Base** | `data/product_knowledge.json` | Candidate's parsed resume + custom uploaded study PDFs/DOCXs |
| **Session Model** | `chat_sessions` & `chat_messages` | `interview_sessions` & `interview_messages` |
| **Key Outputs** | Platform navigation steps, matching explanations | Technical questions, HR questions, roadmaps, STAR guidance |
| **Voice Playback** | Text-only interface | Web Speech API (`window.speechSynthesis`) audio read-aloud |
| **Out-of-Scope Handling** | Redirects to general platform help | Re-routes platform queries to AI Assistant; politely rejects trivia |

---

## 19. File Uploads & Validation

- **Accepted File Formats**: `.pdf` (Portable Document Format) and `.docx` (Microsoft Word).
- **Size Restrictions**: Resumes default to **5 MB** max (`MAX_UPLOAD_BYTES`); study documents allow up to **10 MB** (`MAX_DOC_BYTES`).
- **Profile Pictures**: Supported image formats include `.png`, `.jpg`, `.jpeg`, `.webp` (stored in `uploads/profile_images/`).
- **Safety & Isolation**: Uploaded files are stored using random UUID filenames (`uuid4().hex`) to prevent path traversal attacks.

---

## 20. Security Best Practices

1. **Keep `.env` Private**: Never push `.env` to GitHub or public repositories.
2. **Rotate Secrets**: Always replace default `JWT_SECRET_KEY` placeholders with high-entropy cryptographic strings.
3. **Stateless JWT Handling**: Tokens are verified on every protected request. Logout invalidates client storage.
4. **Owner-Only Authorization**: All profile updates, resume views, applications, and chat sessions enforce owner isolation (`user_id == current_user.id`).
5. **Sanitized AI Outputs**: Error handlers automatically strip API keys and credential strings from Gemini diagnostics before returning responses.

---

## 21. Troubleshooting

| Issue | Likely Cause | Solution |
| :--- | :--- | :--- |
| `GEMINI_API_KEY is not configured` | Missing or placeholder key in `.env`. | Create a key in [Google AI Studio](https://aistudio.google.com/app/apikey) and place it in `.env`. |
| `Could not create user` / DB error | SQLite file locked or schema mismatch. | Check database permissions or delete `resume_parser.db` to let the app recreate fresh tables. |
| `Only .pdf and .docx files are accepted` | Invalid file format uploaded. | Ensure file has a `.pdf` or `.docx` extension. |
| `Add a profile or resume before finding matches` | Candidate profile is empty. | Upload a resume or populate skills in the **Profile** tab first. |
| `Address already in use` (Port 8000) | Another process is occupying port 8000. | Run `uvicorn main:app --port 8001` or terminate the existing process via Task Manager. |
| Audio read-aloud button does not speak | Browser audio permissions or speech synthesis unsupported. | Ensure browser volume is on and test in Google Chrome or Microsoft Edge. |

---

## 22. Development Notes

### Contributing Guidelines
1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make modular changes following existing patterns (Pydantic schemas in `schemas.py`, DB models in `models.py`, business logic in `services/`).
3. Run test verification before committing:
   ```bash
   python -m unittest discover -s tests -p "test_*.py"
   ```
4. Commit changes with clear, descriptive commit messages.

---

## 23. Git & Environment Security

- The repository `.gitignore` ensures that `.venv/`, `.env`, `*.db`, `uploads/`, and temporary caches (`__pycache__/`) are never checked into version control.
- Never hardcode API keys or database connection passwords in source files.

---

## 24. Future Scope

- **Real-Time Job Board Integration**: Connect with external job board APIs (LinkedIn, Indeed, Handshake) for live scraping.
- **Mock Video & Audio Interviews**: Integrate speech-to-text (Whisper) for full conversational voice interviews.
- **ATS Resume Optimization**: Automated formatting suggestions to improve applicant tracking system (ATS) scores.
- **Enterprise / Recruiter Portal**: Dashboard for recruiters to post internships and review candidate match rankings directly.

---

## 25. License

This project is proprietary and developed for academic and portfolio demonstration purposes. All rights reserved.
