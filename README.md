# Resume Parser & User Management API

FastAPI backend for both internship assignments:

1. User registration, JWT authentication, password management, and owner-only profiles.
2. Authenticated PDF/DOCX resume uploads using the existing hybrid parser (regex + Gemini), with the uploaded file and parsed JSON stored in SQLite.

## Folder structure

```text
AI_INTERNSHIP_APPLICATION_AGENT/
├── main.py                    # FastAPI app, existing parser pipeline, CLI
├── extract_text.py             # Existing PDF/DOCX text extraction
├── regex_extractor.py          # Existing deterministic contact extraction
├── llm_extractor.py            # Existing Gemini structured extraction
├── merge.py                    # Existing regex + LLM merge logic
├── schemas.py                  # Parser schemas plus API request/response schemas
├── database.py                 # SQLAlchemy engine/session setup
├── models.py                   # User, UserProfile, Resume tables and relationships
├── auth.py                     # bcrypt hashing and JWT helpers
├── crud.py                     # Reusable database functions
├── dependencies.py             # DB session and authenticated-user dependencies
├── routers/
│   ├── auth_routes.py          # Authentication and password routes
│   ├── profile_routes.py       # Owner-only profile/account routes
│   └── resume_routes.py        # Protected resume upload route
├── uploads/                    # Received resume files (created automatically)
├── parsed_json/                # Reserved for JSON exports
└── requirements.txt
```

## Installation

Install Python 3.12+ and, from this project directory, run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell prevents activation, run `Set-ExecutionPolicy -Scope Process Bypass` once for that terminal, then activate again.

## Environment variables

Set these before starting the API. Never put API keys or production secrets in source code.

```powershell
$env:GEMINI_API_KEY="your_google_ai_studio_key"
$env:JWT_SECRET_KEY="replace-with-a-long-random-secret"
```

Create a Gemini key in [Google AI Studio](https://aistudio.google.com/app/apikey). Optional configuration:

```powershell
$env:GEMINI_MODEL="gemini-3.6-flash"
$env:ACCESS_TOKEN_EXPIRE_MINUTES="60"
$env:MAX_UPLOAD_BYTES="5242880"  # 5 MB
```

For permanent Windows variables use `setx GEMINI_API_KEY "..."` and `setx JWT_SECRET_KEY "..."`, then open a new terminal.

## Database and server

No manual database command is needed. At startup, the app creates `resume_parser.db` and its tables automatically.

```powershell
uvicorn main:app --reload
```

Open Swagger UI at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). APIs are grouped as **Authentication**, **Profile**, and **Resume**. Login first, copy `access_token`, click **Authorize**, and enter `Bearer YOUR_TOKEN`.

You can still run the original parser CLI (without database storage):

```powershell
python main.py "C:\Users\your-name\Downloads\resume.pdf"
```

## API workflow

1. `POST /register`
2. `POST /login` and copy `access_token`
3. Add `Authorization: Bearer <access_token>` to protected requests.
4. Optionally create/update your profile.
5. Upload with `POST /resume/upload`. The API saves the file in `uploads/`, calls the existing parser modules, then stores the final JSON in the `resumes` table.

## Sample requests and responses

Set a token after login for the commands below:

```powershell
$token = "paste_access_token_here"
```

### Register — `POST /register`

```powershell
curl.exe -X POST "http://127.0.0.1:8000/register" -H "Content-Type: application/json" -d "{\"username\":\"asha\",\"email\":\"asha@example.com\",\"password\":\"SecurePass123\"}"
```

```json
{"id": 1, "username": "asha", "email": "asha@example.com", "is_active": true, "created_at": "2026-08-07T10:00:00Z"}
```

### Login — `POST /login`

```powershell
curl.exe -X POST "http://127.0.0.1:8000/login" -H "Content-Type: application/json" -d "{\"email\":\"asha@example.com\",\"password\":\"SecurePass123\"}"
```

```json
{"access_token": "eyJ...", "token_type": "bearer"}
```

### Create profile — `POST /profile`

```powershell
curl.exe -X POST "http://127.0.0.1:8000/profile" -H "Authorization: Bearer $token" -H "Content-Type: application/json" -d "{\"full_name\":\"Asha Sharma\",\"phone\":\"+91 98765 43210\",\"skills\":[\"Python\",\"FastAPI\"]}"
```

```json
{"id": 1, "user_id": 1, "full_name": "Asha Sharma", "phone": "+91 98765 43210", "address": null, "bio": null, "linkedin": null, "github": null, "skills": ["Python", "FastAPI"], "education": [], "experience": [], "created_at": "2026-08-07T10:01:00Z", "updated_at": "2026-08-07T10:01:00Z"}
```

### Get profile — `GET /profile`

```powershell
curl.exe "http://127.0.0.1:8000/profile" -H "Authorization: Bearer $token"
```

Response: the same profile JSON shown above.

### Update profile — `PUT /profile`

```powershell
curl.exe -X PUT "http://127.0.0.1:8000/profile" -H "Authorization: Bearer $token" -H "Content-Type: application/json" -d "{\"bio\":\"Computer science student\",\"skills\":[\"Python\",\"SQL\"]}"
```

Response: updated profile JSON with the new `bio` and `skills`.

### Upload resume — `POST /resume/upload`

```powershell
curl.exe -X POST "http://127.0.0.1:8000/resume/upload" -H "Authorization: Bearer $token" -F "file=@C:\Users\your-name\Downloads\resume.pdf"
```

```json
{"id": 1, "original_filename": "resume.pdf", "stored_filename": "uuid.pdf", "parsed_json": {"full_name": "Asha Sharma", "technical_skills": ["Python"], "email": "asha@example.com"}, "uploaded_at": "2026-08-07T10:05:00Z"}
```

### Change password — `POST /change-password`

```powershell
curl.exe -X POST "http://127.0.0.1:8000/change-password" -H "Authorization: Bearer $token" -H "Content-Type: application/json" -d "{\"current_password\":\"SecurePass123\",\"new_password\":\"NewSecure456\"}"
```

```json
{"message": "Password changed successfully.", "reset_token": null}
```

### Forgot password — `POST /forgot-password`

```powershell
curl.exe -X POST "http://127.0.0.1:8000/forgot-password" -H "Content-Type: application/json" -d "{\"email\":\"asha@example.com\"}"
```

```json
{"message": "If the email exists, a reset token has been created.", "reset_token": "eyJ..."}
```

This starter app returns the reset token only to make local testing possible. In production, send it by email and never include it in the response.

### Reset password — `POST /reset-password`

```powershell
curl.exe -X POST "http://127.0.0.1:8000/reset-password" -H "Content-Type: application/json" -d "{\"reset_token\":\"paste_reset_token\",\"new_password\":\"NewSecure456\"}"
```

```json
{"message": "Password reset successfully.", "reset_token": null}
```

### Logout — `POST /logout`

```powershell
curl.exe -X POST "http://127.0.0.1:8000/logout" -H "Authorization: Bearer $token"
```

```json
{"message": "Logged out successfully. Discard the access token on the client.", "reset_token": null}
```

### Delete user — `DELETE /user`

```powershell
curl.exe -X DELETE "http://127.0.0.1:8000/user" -H "Authorization: Bearer $token"
```

```json
{"message": "User account, profile, and resume records deleted successfully.", "reset_token": null}
```

`DELETE /delete-user` is also supported as a compatibility alias.

## Error responses

All application errors have a stable envelope:

```json
{"error": {"message": "Only .pdf and .docx files are accepted."}}
```

- `400`: incorrect current password.
- `401`: missing, invalid, expired, or wrong-type JWT/reset token.
- `403`: inactive account.
- `404`: missing profile or user.
- `409`: duplicate account or profile already exists.
- `413`: file over the configured size limit.
- `415`: unsupported upload type.
- `422`: invalid request, empty file, corrupted document, or unreadable/OCR-only PDF.
- `500`: database or file-storage failure.
- `502`: Gemini/API parsing failure.

## Postman

Use the same URLs, JSON request bodies, and Bearer token shown above. For resume upload select **Body → form-data**, use key `file`, set its type to **File**, and select a `.pdf` or `.docx` document.

## Security notes

Passwords are bcrypt hashes; plain passwords are never stored. JWTs are stateless, so logout tells the client to discard its token. A production deployment should use a strong `JWT_SECRET_KEY`, HTTPS, a production database, an email provider for reset links, and a JWT token blacklist if immediate server-side logout/revocation is required.
