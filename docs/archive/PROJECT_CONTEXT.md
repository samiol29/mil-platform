> **Archived**: superseded by `docs/architecture/ARCHITECTURE.md` and `specs/`. Describes an early prototype
> stack (Celery/Redis, Tailwind+Axios, `users`/`customers` tables) that no longer matches
> the current codebase. Kept for historical reference only.

# Speckit — Mortgage Underwriting & Fraud Detection

Purpose
-------
Provide a concise single-source project context for the Mortgage Underwriting & Fraud Detection system. This document consolidates architecture, data model, APIs, workflows, components, security notes, and next steps.

Quick Facts
-----------
- Type: Multi-page web application (Frontend + Backend)
- Frontend: React + Tailwind CSS + Axios
- Backend: FastAPI + SQLAlchemy
- DB: PostgreSQL
- OCR: pdfplumber + Tesseract (fallback)
- Auth: JWT based
- Storage: Local disk or S3 for PDF files

High-level Architecture
-----------------------
- Frontend (separate app) communicates with Backend over REST (HTTPS).
- Backend exposes auth, customer, application, document, OCR/verification, fraud, decision, and audit APIs.
- Background worker (Celery/Redis or FastAPI BackgroundTasks) processes OCR and heavy tasks asynchronously.
- PostgreSQL stores customers, applications, documents metadata, fraud flags, decisions, and audit logs.

Data Model (key tables)
-----------------------
- users(id, username, password_hash, role, created_at)
- customers(id (uuid), customer_id, full_name, age, pan, aadhaar, salary, address, created_at)
- applications(id (uuid), customer_id, status, risk_score, decision, created_by, created_at)
- documents(id(uuid), application_id, doc_type, file_path, extracted_text, extracted_fields JSONB, uploaded_at)
- fraud_flags(id, application_id, flag_type, severity, details JSONB, created_at)
- audit_logs(id, application_id, actor, action, payload JSONB, created_at)

Core REST API Endpoints (representative)
----------------------------------------
- POST /api/auth/register — create user
- POST /api/auth/login — returns JWT
- GET /api/customers?customer_id=... — search
- POST /api/customers — create customer
- POST /api/applications — create application
- POST /api/applications/{app_id}/documents — upload PDF(s) (multipart)
- POST /api/applications/{app_id}/process — trigger processing
- GET /api/applications/{app_id} — get results, flags, decision
- GET /api/audit?application_id=... — audit trail

Authentication & Roles
----------------------
- JWT tokens used for auth; `Authorization: Bearer <token>` header on protected routes.
- Role `loan_officer` required for application processing and uploads; admin role for config.

OCR Workflow
------------
1. Upload PDF via `/documents` endpoint (validate MIME/size). Store file and create `documents` row.
2. Enqueue OCR job.
3. OCR job: use `pdfplumber` to extract text; if text not found, convert pages to images and run Tesseract.
4. Normalize extracted text and run field extractors (Name, PAN, Aadhaar, Salary, Employer, Address).
5. Persist `extracted_text` and `extracted_fields` in `documents`.
6. Trigger verification & decision workflows for the parent application.

Verification Workflow
---------------------
- Normalize DB values and extracted values for comparisons (strip punctuation, lowercase).
- Use regex (PAN, Aadhaar) and fuzzy matching (token set/Levenshtein) for names and addresses.
- For salary numeric comparisons, parse amounts and compute relative deltas.
- Produce per-field match scores and a verification summary saved to the application record.

Fraud Detection Rules
---------------------
- Rule-based detection with configurable severities:
  - PAN mismatch (high severity)
  - Aadhaar mismatch (high severity)
  - Name fuzzy-match below threshold
  - Salary difference above threshold
  - Address token overlap low
  - Missing required documents
- Aggregate flags into a `fraud_score` (0-100) using weighted sum.

Loan Decision Engine
--------------------
- Combine `fraud_score`, `verification completeness`, and `income risk` into `risk_score` (0-100).
- Example weights (configurable): fraud 60%, completeness 20%, income 20%.
- Thresholds: risk_score <= 30 -> APPROVE; 30-60 -> MANUAL_REVIEW; >60 -> REJECT.
- Decision stored in `applications` with explanation (top contributing flags).

Frontend Pages
--------------
- Login / Register
- Search (Customer ID)
- Customer Profile (view/edit customer)
- New Application (upload PDFs, enter meta)
- Processing / Results (extracted fields, matching table, fraud flags, risk badge, decision)
- Audit / History

Backend Services & Modules
--------------------------
- `auth` (JWT, bcrypt)
- `customers` CRUD
- `applications` orchestration
- `documents` upload & storage
- `ocr` module (pdfplumber + tesseract wrapper)
- `verification` (parsers & fuzzy comparators)
- `fraud` engine (rule runner)
- `decision` engine (scoring & thresholds)
- `audit` logging
- `storage` abstraction (local/S3)
- `workers` (Celery tasks or background tasks)

Security & Compliance
---------------------
- Hash passwords (`bcrypt`).
- Use HTTPS and secure JWT secrets.
- Validate and sanitize all uploads; limit file size.
- Encrypt PII at rest when required by policy.
- Role-based access control and audit logging of actions.

Operational Notes
-----------------
- Use Docker and `docker-compose` for local dev: Postgres, Redis, backend, frontend.
- Use Alembic for migrations.
- Monitor background workers and retry OCR failures.

Project Folder Structure (recommended)
------------------------------------
- frontend/
  - src/pages/, src/components/, src/services/api.js, package.json
- backend/
  - app/main.py, models.py, schemas.py, auth.py, customers.py, applications.py, documents.py, ocr.py, verification.py, fraud.py, decision.py, audit.py
  - workers/tasks.py
  - requirements.txt, Dockerfile
- infra/
  - docker-compose.yml
- docs/ (api.md, architecture.md, schema.sql)

Next Steps
----------
1. Scaffold backend: FastAPI app with auth, DB models, and migrations.
2. Implement OCR module with unit tests for field extractors.
3. Scaffold frontend: React pages and API integration.
4. Add Celery+Redis worker for async OCR processing (optional for scale).
5. Harden security: password hashing, HTTPS, input validation.

Contact
-------
This document is the canonical single-project context for planning and implementation. Save and reference while building the system.
