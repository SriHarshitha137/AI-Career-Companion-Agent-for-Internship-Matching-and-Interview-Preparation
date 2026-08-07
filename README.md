# Hybrid Resume Parsing System

This Python project parses `.pdf` and `.docx` resumes with a hybrid approach:

- Regex extracts deterministic contact data: name (best effort), email, Indian/standard phone, LinkedIn, and GitHub.
- Gemini extracts contextual data: summary, skills, education, experience, projects, and more.
- Pydantic validates Gemini's JSON. If it is invalid, the app asks Gemini to repair it once.

## 1. Install Python and dependencies

Install Python 3.10 or later from [python.org](https://www.python.org/downloads/). In this project folder, run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks virtual-environment activation, either run `Set-ExecutionPolicy -Scope Process Bypass`, or use the virtual environment's Python executable directly: `.\.venv\Scripts\python.exe`.

## 2. Configure the Gemini API key

Create an API key in [Google AI Studio](https://aistudio.google.com/app/apikey). For the current PowerShell session:

```powershell
$env:GEMINI_API_KEY="your_google_ai_studio_key_here"
```

To save it for future Windows terminals (open a new terminal afterward):

```powershell
setx GEMINI_API_KEY "your_google_ai_studio_key_here"
```

The default model is `gemini-3.6-flash`. To use an account-approved different Gemini model:

```powershell
$env:GEMINI_MODEL="your-model-id"
```

## 3. Run against a local resume

```powershell
python main.py "C:\path\to\candidate_resume.pdf"
```

DOCX works too:

```powershell
python main.py "C:\path\to\candidate_resume.docx"
```

The command prints prettified JSON. Typical output is:

```json
{
  "full_name": "Asha Sharma",
  "professional_summary": "Machine-learning student with internship experience.",
  "technical_skills": ["Python", "FastAPI", "SQL"],
  "soft_skills": ["Communication"],
  "education": [{"institution": "Example University", "degree": "B.Tech", "field_of_study": "Computer Science", "start_date": "2022", "end_date": "2026", "grade": null}],
  "work_experience": [],
  "projects": [],
  "certifications": [],
  "internships": [],
  "achievements": [],
  "languages": ["English", "Hindi"],
  "publications": [],
  "email": "asha@example.com",
  "phone": "+91 98765 43210",
  "linkedin": "linkedin.com/in/asha-sharma",
  "github": "github.com/asha-sharma"
}
```

Missing text fields are `null`; missing collection fields are `[]`. On errors, the CLI prints e.g. `{"error":{"message":"..."}}` instead of crashing.

## 4. Run the FastAPI server

```powershell
python main.py --serve
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs), expand `POST /parse-resume`, click **Try it out**, then upload a resume.

Or call the endpoint from PowerShell with curl:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/parse-resume" -F "file=@C:\path\to\candidate_resume.pdf"
```

The API returns the same JSON as the CLI. Unsupported, empty, corrupt, OCR-only, or Gemini API failures return clear JSON in the form `{"error":{"message":"..."}}` with an appropriate HTTP status.

## Project layout

- `extract_text.py`: PDF/DOCX reading with `pdfplumber` and `python-docx`.
- `regex_extractor.py`: readable deterministic contact regexes.
- `llm_extractor.py`: Gemini call, strict prompt, Pydantic validation, one repair retry.
- `schemas.py`: strict, consistent Pydantic data contracts.
- `merge.py`: precedence rules for the final response.
- `main.py`: shared pipeline, FastAPI endpoint, and CLI.
