# ARIA — AI CRM Agent

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![Gemini](https://img.shields.io/badge/Google%20Gemini-2.5%20Flash-4285F4?logo=google&logoColor=white)
![Sheets](https://img.shields.io/badge/Google%20Sheets-Live%20DB-34A853?logo=googlesheets&logoColor=white)
![Gmail](https://img.shields.io/badge/Gmail%20API-Live-EA4335?logo=gmail&logoColor=white)
![Calendar](https://img.shields.io/badge/Google%20Calendar-Live-4285F4?logo=googlecalendar&logoColor=white)
![Render](https://img.shields.io/badge/Deployed-Render-46E3B7?logo=render&logoColor=white)

ARIA is a full-stack AI-powered CRM I built from scratch. You type in plain English. ARIA figures out what you want to do, confirms it with you, then actually does it — sending a real Gmail, booking a real Calendar event, updating a real Google Sheet. No mock APIs, no fake data, no simulated responses.

**Live demo:** https://ai-crm-agent-ol9e.onrender.com/aria

---

## What it does

The core idea is simple: instead of clicking through forms to manage your pipeline, you just tell ARIA what you need.

> "Create a client for Sarah Mitchell at TechFlow, high priority, AI automation service"

> "Draft a follow-up email for CL-00A3F2 thanking them for yesterday's meeting"

> "Schedule a 30-minute consultation with James next Friday at 2pm and send him a calendar invite"

> "Score all my high priority clients and tell me who's most likely to close"

ARIA handles 13 distinct CRM actions, always confirms before doing anything destructive, and lets you say "undo" to reverse the last change.

Beyond the chat interface, there's a full 10-page web app for managing clients, drafts, meetings, reports, and bulk imports.

---

## Tech stack

| Layer | Tech | Why |
|---|---|---|
| Backend | Python 3.11 + FastAPI | Async-first, Pydantic validation, clean API design |
| AI | Google Gemini 2.5 Flash | Fast inference, strong instruction following, cost efficient |
| Database | Google Sheets | Zero infra, spreadsheet as a live DB with full audit trail |
| Email | Gmail API | Send and draft real emails from the CRM |
| Calendar | Google Calendar API | Schedule and manage real meetings with client invites |
| Documents | python-docx | Generate branded Word docs (reports, contracts, invoices, proposals) |
| Frontend | Vanilla JS | 10 pages, 12 JS modules, zero framework overhead |
| Deployment | Render | Free tier, persistent web service, env var secrets |

I used Google Sheets as the database intentionally. It gives you a human-readable audit trail, lets non-technical users inspect the data directly, and removes the need to manage a database server. For a CRM at this scale it works well.

---

## Features

### ARIA Chat
The main interface. Supports 13 actions:

- Create, update, archive, and permanently delete clients
- Update pipeline stage and follow-up dates
- Send emails and save Gmail drafts
- Schedule Google Calendar meetings with optional client invites
- Score a client with AI (lead score, churn risk, close probability, sentiment)
- Rollback the last change or a specific field
- Restore a deleted client within a 1-hour undo window

ARIA always asks for confirmation before doing anything that can't be undone. It also accepts file attachments: PDF, Excel, CSV, and Word. Drop in a spreadsheet and it imports the clients. Drop in a PDF and it reads and answers questions about it.

There's a topic firewall that blocks off-topic requests (no, ARIA won't write you Python code or explain quantum physics). It uses a fast keyword auto-pass for common CRM terms, then falls back to a Gemini classifier for ambiguous cases. Conversation history is preserved across the session so follow-up messages like "generate it" or "go ahead" work as expected.

### Client Management
Standard CRUD with a few extras:

- Full audit trail on every field change
- 1-hour soft-delete undo window
- Rollback last change or rollback a specific field to its previous value
- Archive vs permanent delete (separate operations)
- Bulk import from Excel or CSV with live SSE progress stream, duplicate detection, and a preview step before committing

### Intelligence
AI-powered analysis using Gemini:

- Per-client scoring: lead score (0-10), churn risk, estimated close probability, sentiment, best next action, talking points
- Pipeline health score across all clients
- Pattern detection: segments, bottlenecks, growth opportunities
- Revenue forecast: 30-day and 90-day projections by stage probability
- Win/loss analysis: what separates won deals from lost ones
- Daily recommendations: AI-prioritized list of who to contact today and why
- Stale client detection: anyone with no activity in 14+ days

### Documents
6 branded Word document types generated on demand:

- Client intake report (AI analysis + client data)
- Pipeline summary report
- Weekly performance report
- Monthly pipeline report
- Client acquisition report
- Agent activity report
- Service contract
- Invoice
- Proposal (manual or AI-generated from client data)

### Email and Calendar
- AI-drafted emails with your name in the sign-off, saved directly to Gmail drafts
- Send emails directly from the CRM
- Gmail draft management (list, delete)
- Schedule meetings with title, location, description, start/end time
- Optional calendar invite to the client's email
- Add notes to existing calendar events
- View all upcoming meetings filtered by time range

### Smart Search
Two modes:

- Natural language search: "high priority clients interested in AI automation"
- Smart filter: "clients stuck in proposal stage for more than 2 weeks"

Both use Gemini to interpret the query against your actual client list.

---

## Architecture

```
app/
├── main.py              # FastAPI app, 50+ endpoints, ARIA chat endpoint
├── agent.py             # LLM functions: analyze, score, draft, search, forecast
├── auth.py              # HTTP Basic Auth with constant-time compare
├── config.py            # Pydantic settings from env vars
├── models.py            # Request/response models with validation
├── logger.py            # Structured logging
└── services/
    ├── sheets.py        # Google Sheets: CRUD, audit, rollback, cache
    ├── llm.py           # Gemini client with thread pool executor
    ├── gmail.py         # Gmail: send, draft, list, delete
    ├── calendar.py      # Google Calendar: schedule, update, cancel, notes
    ├── importer.py      # Excel/CSV parser + bulk import with SSE streaming
    ├── document.py      # Client and pipeline Word report generation
    ├── reports.py       # Weekly, monthly, acquisition, activity reports
    ├── contracts.py     # Contract, invoice, proposal generation
    ├── scoring.py       # AI lead scoring with Gemini
    ├── search.py        # Natural language search and smart filter
    └── pdf.py           # PDF text extraction for chat file uploads

app/static/
├── css/aria.css         # Full design system (light theme, custom tokens)
├── js/
│   ├── api.js           # Central HTTP module (auth, upload, SSE streaming)
│   ├── utils.js         # Shared helpers (Toast, Icons, modal, formatting)
│   ├── nav.js           # Topbar + sidebar injection, pipeline cache
│   ├── dashboard.js
│   ├── clients.js
│   ├── chat.js
│   ├── calendar.js
│   ├── email.js
│   ├── intel.js
│   ├── reports.js
│   ├── search.js
│   ├── import.js
│   └── login.js
└── pages/               # 10 HTML files, pure markup, zero inline JS
```

The ARIA chat endpoint does three things per message in sequence:

1. Topic firewall: keyword check first, Gemini classifier if needed
2. Intent detection: one Gemini call to extract action type and parameters as JSON
3. Action execution: runs the action against Sheets/Gmail/Calendar if confirmed
4. Response generation: one Gemini call to write the reply with context

The Google APIs all run non-blocking with `asyncio.to_thread`. Sheets has a 30s TTL cache on pipeline reads to avoid hammering the API on every page load.

---

## Setup

You need a Google Cloud project with these APIs enabled:
- Google Sheets API
- Gmail API
- Google Calendar API

And a service account with a credentials JSON for Sheets (the service account needs editor access on your spreadsheet). For Gmail and Calendar you need an OAuth2 token since those require user-level permissions.

### Environment variables

```env
GEMINI_API_KEY=your_gemini_api_key
SPREADSHEET_ID=your_google_sheets_id
API_USERNAME=admin
API_PASSWORD=your_password
GMAIL_ADDRESS=your@gmail.com
GOOGLE_CREDENTIALS={"type":"service_account",...}  # full JSON as string
GMAIL_TOKEN={"token":"...","refresh_token":"..."}   # OAuth2 token as string
```

### Run locally

```bash
pip install -r requirements.txt
python run.py
```

Then open http://localhost:10000/aria

### Deploy to Render

The `render.yaml` is already configured. Push to GitHub, connect the repo on Render, add the env vars, and deploy. First boot takes 2-3 minutes because Render pulls dependencies.

---

## The frontend

I built the frontend in plain Vanilla JS with no framework. Each page loads exactly 4 script tags: `api.js`, `utils.js`, `nav.js`, and the page-specific module. The HTML files are pure markup with `id` and `data-*` attributes only. Zero `onclick=""`, zero `onchange=""`, zero inline handlers.

The topbar and sidebar are injected by `nav.js` on every page from a single source of truth, so icon changes and nav updates only need to happen in one place. Event delegation handles dynamic content so there's no rebinding on re-render.

Session state in the chat (history, pending actions, last discussed client) lives in `sessionStorage` and survives page focus changes but clears when the tab closes.

---

## Security

- HTTP Basic Auth with `hmac.compare_digest` to prevent timing attacks
- XHR header on all requests to suppress native browser auth popups on 401
- Rate limiting on the chat endpoint (20 requests/minute) via slowapi
- Server-side file size enforcement (10MB chat uploads, 25MB import)
- Pydantic field validation with max lengths on all text inputs
- Prompt injection hardening: client data in LLM prompts is labeled as read-only reference data
- Topic firewall prevents the LLM from being used as a general-purpose assistant
- CORS locked to the production origin

---

## Numbers

- 50+ REST endpoints
- 13 ARIA chat actions
- 3 live Google APIs integrated simultaneously
- 10 frontend pages
- 12 JS modules
- 6 Word document types
- 5,000 row bulk import cap
- 25MB file size limit (server-enforced)
- 1-hour undo window on deleted records
- 30s TTL cache on pipeline reads
- Last 10 messages passed as conversation history to LLM
- 6 pipeline stages tracked

---

## What I learned

A few things that weren't obvious going in:

**Google Sheets as a database is underrated for the right use case.** Schema changes are instant, non-technical teammates can see the data, and you get a human-readable audit trail for free. The main downside is you have to implement your own indexes and caching, which I did with an in-memory dict and TTL timestamps.

**LLM pipelines need structure.** The first version of the intent detector was one big prompt that tried to do everything. It was inconsistent. Breaking it into a firewall step, an intent step, and a response step made each call simpler and more reliable. The JSON extraction fallback with regex saved a lot of headaches.

**Non-blocking Google API calls matter more than you'd think.** The first version of `sheets.py` used synchronous gspread calls. Under any real load the event loop would block and the UI would feel sluggish. Wrapping everything in `asyncio.to_thread` and adding caching made a noticeable difference.

**SSE streaming is not complicated but feels great.** The bulk import live log was one of those features where the implementation took 2 hours and users react to it like it's magic. Worth it.

---

## License

MIT