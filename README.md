# CareerShield – Explainable Multi-Evidence AI Framework for Recruitment Fraud Detection and Company Reputation Assessment

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)
[![Tailwind CSS](https://img.shields.io/badge/TailwindCSS-3.4-38B2AC.svg)](https://tailwindcss.com/)

---

## 1. Project Overview

**CareerShield** is an AI-powered cybersecurity and digital trust intelligence platform engineered to address modern employment fraud, phishing, corporate impersonation, and uncorroborated workplace rumors.

### Fundamental System Axioms:
1. **Dual-Axis Separation**: **Recruitment Risk ≠ Company Reputation**. A scammer may impersonate a legitimate enterprise (e.g., Google or Microsoft), while a legitimate company may suffer from poor workplace reviews.
2. **The Unknown Rule**: Lack of information (e.g., missing career page or minimal online presence for small local businesses) evaluates to `Unknown / Insufficient Evidence`, never automatically declared `Fraudulent`.
3. **The Corroboration Principle**: An isolated negative review does **not** validate a public allegation. Multi-source repetition, aspect alignment, and contradiction checks are strictly required.
4. **Graceful Degradation**: If the Hugging Face Inference API is unconfigured or unreachable, the local supervised NLP model and rule-based heuristic agents maintain continuous decision support without downtime.

---

The authenticated frontend includes Dashboard, Analyze Job, Company Intelligence, History, Model Transparency, and About & Whitepaper destinations. Navigation adapts to narrow screens through a mobile drawer.

## 2. High-Level Architecture

```
                    CAREERSHIELD
                         |
             +-----------+-----------+
             |                       |
      RECRUITMENT RISK       COMPANY INTELLIGENCE
             |                       |
       +-----+------+          +-----+------+
       |     |      |          |     |      |
      NLP  Scam  Recruiter   Reviews Claims Company
       |     |      |          |     |      |
       +-----+------+          +-----+------+
             |                       |
             +-----------+-----------+
                         |
                  EVIDENCE FUSION
                         |
                 EXPLAINABLE REPORT
                         |
             +-----------+-----------+
             |                       |
       Recruitment Risk      Company Reputation
```

---

## 3. Mathematical Evidence Fusion Formula

Rather than relying on an opaque black-box neural score, CareerShield computes a normalized multi-evidence fusion index:

$$E_f = \frac{\sum (w_i \times q_i \times e_i)}{\sum (w_i \times q_i)}$$

$$\text{Trust Score (TS)} = 50 + 50 \times E_f \quad (\text{Bounded: } [0, 100])$$

### Decision Thresholds:
- **75 – 100 : Likely Legitimate** (Green) — Verified identity, valid domain correlation, absence of fraud patterns.
- **50 – 74 : Uncertain** (Amber) — Sparse external data or slight anomalies requiring candidate caution.
- **0 – 49 : Likely Fraudulent** (Red) — Upfront fee demands, corporate impersonation, or high-risk scam triggers.

---

## 4. Directory Structure

```
CareerShield/
├── .env.example                     # Environment template (secrets omitted)
├── pytest.ini                       # Test configuration
├── README.md                        # Documentation
├── backend/
│   ├── app/
│   │   ├── config.py                # App configuration & directory management
│   │   ├── db.py                    # SQLAlchemy database engine (SQLite/PostgreSQL)
│   │   ├── main.py                  # FastAPI application entry point
│   │   ├── models.py                # ORM models (Analyses, Evidence, Reviews, Claims)
│   │   └── schemas.py               # Pydantic request/response schemas
│   ├── api/
│   │   └── routes.py                # REST API endpoints
│   ├── agents/
│   │   ├── scam_agent.py            # Upfront fees, crypto, PII theft, urgent hooks
│   │   ├── recruiter_agent.py       # Corporate domain matching, free-mail audits
│   │   ├── company_agent.py         # Entity profile, Unknown Rule enforcement
│   │   ├── website_agent.py         # HTTPS TLS, TLD risk analysis, web probes
│   │   ├── domain_agent.py          # DNS A records, MX mail routing verification
│   │   └── salary_agent.py          # Compensation realism relative to role complexity
│   ├── services/
│   │   ├── ml_service.py            # TF-IDF + Logistic Regression inference
│   │   ├── transformer_service.py   # Hugging Face API integration + fallback
│   │   ├── reputation_service.py    # Review indexing & 9 workplace aspect analysis
│   │   └── claim_service.py         # Multi-factor claim corroboration
│   ├── scoring.py                   # Evidence fusion mathematical engine
│   ├── utils/
│   │   ├── text_utils.py            # Text cleaning, concatenation, salary extraction
│   │   └── company_utils.py         # Company name normalization, domain parsing
│   ├── data/
│   │   ├── raw/                     # EMSCAD & review raw datasets
│   │   └── processed/               # Normalized job fraud & review datasets
│   ├── models/                      # Serialized ML joblib models
│   ├── artifacts/                   # Empirical metrics and dataset inspection reports
│   ├── sample_data/                 # Test scenarios (legit, payment scam, mismatch, etc.)
│   ├── scripts/
│   │   ├── download_data.py         # Dataset downloader & schema inspector
│   │   ├── prepare_job_data.py      # Job data preprocessor & label normalizer
│   │   ├── prepare_review_data.py   # Employee review normalizer
│   │   ├── train_model.py           # Supervised training (Logistic Regression & SVM)
│   │   └── evaluate_model.py        # Empirical evaluation metric reporter
│   ├── migrations/                  # Alembic schema revisions
│   └── tests/                       # Backend pytest suite (115 tests in the latest reported run)
└── frontend/
    ├── src/
    │   ├── components/              # StatCard, TrustScore, EvidenceCard, ClaimCard, etc.
    │   ├── pages/                   # Dashboard, AnalyzeJob, Result, Company, History, etc.
    │   ├── services/api.js          # Unified API client
    │   ├── App.jsx                  # Main application layout and routing
    │   ├── index.css                # Tailwind directives & dark theme
    │   └── main.jsx                 # Vite React entry point
    ├── tailwind.config.js           # Dark theme design system
    └── package.json
```

---

## 5. Installation & Setup

### Prerequisites:
- Python 3.10+ (the latest supplied QA report used Python 3.13.0; verify your local interpreter before installation)
- Node.js 18+ (Tested on Node.js v24.15.0)

### 1. Backend Setup:
```bash
# Windows, from the workspace root (or use the project virtual environment)
py -3.13 -m pip install -r requirements.txt

# Windows, from the backend directory (adjust the launcher version if needed)
py -3.13 -m pip install -r ..\requirements.txt

# macOS/Linux, from workspace root
python -m pip install -r requirements.txt
```

### 2. Database Migration and Authentication Configuration

Before the first backend start, back up the database selected by `DATABASE_URL`.
Then, from the workspace root, apply the reviewed additive migration chain:

```bash
py -3.12 -m alembic upgrade head
```

The migrations create the `users` and `auth_sessions` tables, add the nullable
`analyses.user_id` column only if it is missing, and add private company
investigation, evidence, and relationship tables. They do not delete, reassign,
or otherwise rewrite analysis records. Legacy records without an owner remain
hidden from user history; records with IDs created by the former browser-only
login are not automatically linked to new accounts. Any future account-to-record
mapping must be verified and migrated separately.
Relative SQLite `DATABASE_URL` paths are resolved from the project root, regardless
of whether Uvicorn or Alembic is launched from the repository root or `backend`.

The latest migrations, `20261031_07` and `20261031_08`, add the
`analyses.analysis_mode` field, the `external_verification_consents` table, and
bounded external-verification run recovery metadata. The table stores
per-analysis selected check names, consent/execution timestamps, run leases,
attempt counts, recovery reasons, and verification results; it does not store a
second copy of the email body. Existing analysis rows receive the `job` mode.
Review and back up the configured database before applying migrations.
Application startup does not apply migrations.

Configure `CORS_ORIGINS` to the exact frontend origin(s). For HTTPS deployments,
set `ENVIRONMENT=production` or `AUTH_COOKIE_SECURE=true`. `AUTH_COOKIE_SAMESITE`
defaults to `lax`; cross-site frontend/API deployments require `none` together
with Secure cookies, an HTTPS origin, and a shared cookie-visible host arrangement
for the CSRF cookie. The backend uses a 12-hour server-side
session by default and Argon2id password hashes. Session cookies are HttpOnly;
state-changing authenticated requests also require the CSRF cookie/header pair.

Authentication throttling uses an in-memory sliding window: by default, up to
30 login requests per source IP per 15 minutes, 5 failed attempts per normalized
account/IP pair per 15 minutes, and 5 registration attempts per source IP per
hour. Exceeded limits return a generic `429 Too Many Requests` response. These
counters are per process and reset when the process restarts; they are suitable
for the current single-process local setup only. Multi-worker or multi-instance
deployments must enforce equivalent limits in a shared rate-limit store or at a
trusted ingress before being exposed publicly.

By default, client IP is taken from the direct socket peer and all forwarded
headers are ignored. If deployed behind a reverse proxy, set `TRUSTED_PROXY_IPS`
to the proxy IPs/CIDRs only after ensuring the proxy strips untrusted incoming
`X-Forwarded-For` values and writes the verified chain. Never trust arbitrary
forwarded headers from untrusted peers.

### Gmail account connection (optional)

Gmail account connection uses a Google OAuth **Web application** client. Enable
the Gmail API in the Google Cloud project, configure the OAuth consent screen,
and register the exact value of `GMAIL_OAUTH_REDIRECT_URI` under **Authorized
redirect URIs**. For local development, the example callback is
`http://127.0.0.1:8000/api/gmail/oauth/callback`; production callbacks and
frontend return URLs must use HTTPS. The configured return URL must use an
origin listed in `CORS_ORIGINS`.

Set `GMAIL_OAUTH_CLIENT_ID`, `GMAIL_OAUTH_CLIENT_SECRET`,
`GMAIL_OAUTH_REDIRECT_URI`, and `GMAIL_OAUTH_RETURN_URL` in the private `.env`
file. Generate a Fernet key with the command shown in `.env.example`, then set
`GMAIL_TOKEN_ENCRYPTION_KEYS` to a JSON key-version map such as
`{"v1":"<generated-key>"}` and `GMAIL_TOKEN_ACTIVE_KEY_VERSION=v1`. Keep old
versioned keys available until ciphertext encrypted with them has been
re-encrypted. Store production credentials and keys in a managed secret store;
never commit them.

The connection requests only `openid`, `email`, and Gmail's
`https://www.googleapis.com/auth/gmail.readonly` scope. It does not request
write/send access. Connecting alone does not enable monitoring. Refresh tokens
are encrypted before database persistence and are never returned by account
status APIs. OAuth callback query values are redacted from Uvicorn access logs;
reverse proxies and hosting platforms must also be configured not to log
callback query strings.

### Gmail monitoring (explicit opt-in)

Gmail monitoring is off by default. After connecting an account, the account
owner must separately enable monitoring in the Gmail connection page and
confirm consent. Enabling or resuming records Gmail's current history cursor
as a fresh baseline; messages before that baseline are not scanned. Resuming
after a pause establishes another fresh baseline, so messages received while
paused are skipped. The backend polls Gmail history for newly added messages
using Gmail's read-only API. Expired history cursors are reset to the current
history ID without backfilling old mail.

New message text is analyzed in the existing private-email mode. Website,
company, recruiter, DNS/WHOIS, and external search checks are skipped. Complete
automatically monitored message bodies are held only in memory during analysis
and are not written to analysis history. Deduplication records store Gmail
message IDs and processing status; risk alerts retain only the subject, sender,
risk category, score, and a generic explanation. Disconnecting the account
removes its linked monitoring and deduplication records.

The monitoring lease adds nullable columns to
`email_monitoring_settings` in migration `20261031_06`, after migration
`20261031_05`. Back up the configured database and apply the approved migration
chain before using Gmail features:

```powershell
py -3.12 -m alembic upgrade head
```

The initial scheduler is one background loop in the FastAPI process and is
intended for a single-worker local demonstration. Database-backed expiring
leases and unique message IDs prevent overlapping claims, but multi-worker or
multi-instance deployments should run a dedicated poller or configure a
reviewed distributed-locking deployment rather than starting an independent
scheduler in each API worker. Shutdown waits for the current bounded Gmail API
request and stops before starting additional work. No email, browser, or
frontend notifications are sent; suspicious-risk records are stored for later
review.

Google classifies `gmail.readonly` as a **restricted** scope. Before public
production use, complete the applicable Google OAuth app verification and
consent-screen requirements. Apps that access restricted user data through a
server may also need an independent annual security assessment by a
Google-approved assessor. See Google's [web-server OAuth
guide](https://developers.google.com/identity/protocols/oauth2/web-server),
[Gmail API scopes](https://developers.google.com/workspace/gmail/api/auth/scopes),
[OpenID Connect guide](https://developers.google.com/identity/openid-connect/openid-connect),
and [restricted-scope verification
requirements](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification).

Company investigations are private to their creating account and limited to
five requests per user and source IP per hour by default. This is also an
in-memory limit, so use a shared rate-limit store or trusted upstream throttling
for multi-worker or multi-instance deployments. Investigation reports preserve
source attribution where the existing provider returns it; missing citations
and uncertain identity matches remain explicitly inconclusive. Optional contact
emails are used in memory for the recruiter-domain heuristic; only the contact
domain is retained in the investigation, and emails in search excerpts are
redacted. Investigation graph edges link to their evidence and remain scoped to
the owning investigation.

### 3. Dataset Setup & Machine Learning Training:
```bash
# 1. Download/Initialize datasets
python backend/scripts/download_data.py

# 2. Preprocess and normalize job postings
python backend/scripts/prepare_job_data.py

# 3. Preprocess and normalize employee reviews
python backend/scripts/prepare_review_data.py

# 4. Train Logistic Regression & Linear SVM models
python backend/scripts/train_model.py

# 5. Verify empirical metrics
python backend/scripts/evaluate_model.py
```

### 4. Frontend Setup:
```bash
cd frontend
npm install
npm run build   # Verifies bundling
```

---

## 6. Running the Application

### Start the FastAPI Backend:
```bash
# Windows, from the workspace root (select the Python version installed on your machine)
py -3.12 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# Windows, from the backend directory
py -3.12 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# macOS/Linux, from the workspace root
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation will be available at: `http://localhost:8000/docs`

### Start the React Frontend:
```bash
cd frontend
npm run dev
```
Dashboard will be available at: `http://localhost:5173`

---

## 7. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Create account and start a session |
| `POST` | `/api/auth/login` | Sign in and start a session |
| `GET` | `/api/auth/me` | Return the current authenticated user |
| `POST` | `/api/auth/logout` | Revoke the current session |
| `GET` | `/api/health` | Backend & database health status |
| `GET` | `/api/model/status` | ML models & Transformer API availability |
| `GET` | `/api/datasets/status` | Dataset row counts, features, and balance |
| `GET` | `/api/metrics` | Measured empirical model benchmark results |
| `POST` | `/api/analyze` | Full multi-evidence recruitment risk evaluation |
| `GET` | `/api/analysis/{id}` | Detailed investigation report by ID |
| `GET` | `/api/history` | Authenticated history; supports optional `risk` and `search` query parameters |
| `POST` | `/api/reviews/analyze` | Multi-aspect review credibility analysis (`company_name`, `review_text`, optional source/role/location metadata) |
| `POST` | `/api/company/reputation` | 9-aspect workplace reputation assessment |
| `GET` | `/api/company/{name}/reputation` | Cached corporate reputation lookup |
| `POST` | `/api/company/investigations` | Create a private, evidence-backed company investigation |
| `GET` | `/api/company/investigations` | List the authenticated user's investigations |
| `GET` | `/api/company/investigations/{id}` | Retrieve an owned investigation and report |
| `GET` | `/api/company/investigations/{id}/graph` | Retrieve its evidence-linked relationship graph |
| `DELETE` | `/api/company/investigations/{id}` | Delete an owned investigation and related graph/evidence |
| `POST` | `/api/company/claims` | Public claim corroboration against review evidence |

The history endpoint accepts optional query parameters: `risk` (`ALL`, `LEGITIMATE`, `UNCERTAIN`/`NEEDS VERIFICATION`, or `FRAUDULENT`) and `search` (case-insensitive job-title or company-name search). Example: `/api/history?risk=UNCERTAIN&search=engineer`.

---

## 8. Automated Testing

Run the backend pytest suite from the project root:
```bash
py -3.13 -m pytest -v
```

The latest supplied QA report recorded **115 passing tests**. Re-run the command in your current environment to confirm the present result; test counts may change as the suite evolves.
The suite covers preprocessing, ML prediction, agent logic, scoring, services,
API behavior, authentication, and record ownership. API tests use disposable
SQLite databases and stub network-dependent integrations.

---

## 9. Limitations & Future Roadmap
- **Limitations**: Network firewall restrictions may cause DNS or HTTP probes to return `Unknown` instead of `Verified`.
- **Future Roadmap**: Browser extensions for real-time LinkedIn/Indeed scraping, decentralized cryptographic credentials for verified hiring managers, and active learning feedback loops.

## Windows Quick Start

1. Install **Python 3.12** and **Node.js 22 LTS** (or a Vite 8-compatible Node.js release).
2. Extract this project folder to a location you can write to.
3. Double-click `setup_windows.bat` once. It creates a local Python virtual environment, installs Python and frontend dependencies, and creates `.env` from `.env.example` if needed.
4. Double-click `start_windows.bat` to start the API and Vite development server.
5. Open `http://127.0.0.1:5173`. API documentation is at `http://127.0.0.1:8000/docs`.

The quick-start scripts do not run database migrations, reset the SQLite database, retrain models, or replace model artifacts. For a new/empty database, follow the migration instructions below only after making a backup and confirming the intended database path.

### Multi-format Job Advertisement Upload

The Analyze Job page accepts PDF, PNG, JPG/JPEG, WEBP, DOCX, and UTF-8 TXT files
up to 10 MB by default. Text-based PDFs and Word/text documents are parsed
locally. Images and scanned PDF pages use the local Tesseract OCR engine. Review
and edit extracted text before analysis; the document itself is processed in
memory and is not retained. The existing analysis record/history behavior still
applies after you submit an analysis.

Document text uses the existing local fraud model and evidence agents. External
semantic inference and live domain/company verification are skipped for
document-derived content, so uploaded text is not sent to Hugging Face or
external reputation lookups. OCR is local and does not use a cloud API.

The Python OCR wrapper is installed by `setup_windows.bat`, but the Tesseract
executable must be installed separately on Windows. Set `TESSERACT_CMD` in the
root `.env` to the installed executable when it is not available on `PATH`:

1. Install Tesseract OCR using the Windows installer linked from
   [UB Mannheim's Tesseract documentation](https://github.com/UB-Mannheim/tesseract/wiki).
   Include the English language data.
2. Set `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe` in `.env`,
   or add the Tesseract installation folder to `PATH`.
3. Restart the backend. If Tesseract is unavailable, image and scanned-PDF
   uploads return a clear configuration error; text-based documents remain
   supported. Uploaded document contents and internal executable paths are not
   included in OCR error messages or application logs.

`MAX_UPLOAD_SIZE_BYTES` controls the backend upload limit and defaults to
`10485760` (10 MiB). For resource protection, PDFs are limited to 30 pages and
images to 40 megapixels. No database migration or model retraining is required.

### Gmail Chrome Extension

CareerShield includes a local Chrome Manifest V3 extension in
`extensions/careershield-gmail`. It adds a user-clicked action to an opened
Gmail message and submits the reviewed email to the existing `/api/analyze`
endpoint. It never scans the inbox or reads attachment contents. Document/email
mode skips external AI, WHOIS/DNS, and live company verification while using
the existing local fraud model and saving the analysis in the signed-in user's
history.

Private email results are available in the authenticated CareerShield website.
The extension does not perform external verification; **View report & review
optional checks** opens the analysis in the website, where the signed-in user
can inspect extracted fields and separately approve selected checks. The
website requires explicit per-analysis consent before any of those checks run.

### Private Email Mode and consent-based verification

Private Email Mode performs the initial scam analysis locally and skips live
company search, website probes, DNS/WHOIS, recruiter checks, and transformer
inference. It remains private by default. The Analyze page can also be switched
to **Private email analysis** before submitting an email or job text.

After private analysis, the authenticated report displays the extracted company,
website, recruiter domain/name, job title, location, and salary when available.
Extraction uses user-supplied fields and clearly labelled lines in the selected
message; absent values remain unavailable. For each category, the report lists
the exact details that can be used:

- **Company reputation:** company name is sent to the configured public
  company-search provider. The listing domain is compared with public search
  results locally.
- **Website and domain:** the company website URL is used for protected website
  reachability and domain checks. If no company website is available, the
  recruiter email domain is used for the domain check. The website probe
  retains public-IP, DNS-rebinding, redirect, TLS, and timeout safeguards.
- **Recruiter verification:** recruiter and company domains are compared
  locally. The complete recruiter email address is not sent to an external
  verification provider.
- **Salary verification:** job title, location, and salary are evaluated by
  the local salary heuristic; they are not sent to an external provider.

Each check starts unchecked. The user must approve the chosen categories for
that specific analysis and then separately confirm running them. Declining
leaves the private analysis and its score unchanged. Missing information
remains Unknown; declined checks are `Not Checked – User Declined`; failed
external services are Unavailable. Consent and execution state are recorded
against the authenticated user and analysis. A completed execution is
idempotent and is not submitted again. Each run has a two-minute lease and can
start at most twice (the initial attempt plus one user-initiated retry).
Category results are saved as each check finishes, so a retry skips saved
successful categories and only retries missing or unavailable categories.
Expired runs are marked recoverable when the user checks status or attempts a
run; recovery itself never repeats provider requests.

Exactly-once external requests cannot be guaranteed: a provider may complete a
request immediately before the application crashes and before that category's
result is saved. In that case the status is recorded as interrupted, and one
explicit retry may repeat that specific request. Automatic retries are not
performed, and the per-analysis attempt limit prevents repeated retry loops.

The complete email body, attachments, passwords, authentication tokens, and
unrelated personal data are never passed to external verification services.
Automatic Gmail monitoring remains off until consented and continues to run
private analysis only; it never triggers this external-verification workflow.
The extension still stores submitted email content in the user's local
CareerShield analysis history as described in its privacy documentation.

No new environment variables are required. The company-search integration
continues to use `SERPER_API_KEY` when configured; without it, that category is
Unavailable rather than treated as negative evidence. To apply the new schema
after review and backup, run from the project root:

```powershell
py -3.12 -m alembic upgrade head
```

This command is not run automatically by the application. Migration
`20261031_07` adds `analysis_mode` with an existing-row default of `job` and
creates `external_verification_consents` with ownership foreign keys and a
unique analysis constraint. Migration `20261031_08` adds lease expiry,
execution fencing, attempt count, and failure reason fields; existing
in-progress or failed runs are conservatively counted as an attempt.
Downgrades refuse to drop persisted consent or recovery data. Downgrading
`20261031_07` intentionally retains `analyses.analysis_mode` to avoid
discarding private-mode state.
Known limitations: local extraction is label-based and can miss unlabelled
details; recruiter and salary checks are local heuristics rather than identity
or market guarantees; external results depend on optional provider credentials
and public-source availability. CareerShield is a job-seeker decision-support
tool and does not guarantee that any company or job is legitimate.

For local installation, load `extensions/careershield-gmail` unpacked at
`chrome://extensions`, configure the exact `chrome-extension://<id>` origin in
`EXTENSION_ORIGINS`, restart the backend, then pair it from the signed-in
CareerShield website. Full setup, pairing, privacy, and troubleshooting
instructions are in [the Gmail extension README](./extensions/careershield-gmail/README.md).

### Manual commands

Backend (from the repository root):

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Frontend (in a second terminal):

```powershell
cd frontend
npm run dev -- --host 127.0.0.1
```

### Local development limitations

- The application is a decision-support prototype; its outputs are not definitive determinations of fraud or company legitimacy.
- External-source availability depends on network access and optional provider credentials. Missing or unavailable evidence must remain unknown/inconclusive, not be treated as proof of fraud.
- The application-level rate limiter is in-memory and intended for a single local process; multi-worker or multi-instance deployments require a shared rate-limit store or upstream throttling.
- Local test success does not by itself establish production readiness.
