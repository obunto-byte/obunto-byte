# XEBAC HAT AI-IDS v2

<div align="center">
  <strong>Windows-first · FastAPI · SQLite · Session-aware defensive monitoring</strong>
  <br/>
  <a href="https://obunto-byte.github.io/">XEBAC HAT portfolio</a> ·
  <a href="https://github.com/obunto-byte">GitHub profile</a>
</div>

## Project overview

**XEBAC HAT AI-IDS v2** is a local defensive monitoring prototype for developers and lab operators. It accepts application telemetry, groups events into sessions, applies explainable behavioural rules, stores incident records in SQLite, and displays the results in a dark SOC-style web dashboard.

**Purpose:** help developers observe unusual activity in an application or authorized lab, understand why a session was flagged, and investigate it using a structured event trail.

This is a defensive tool. It does not exploit systems, automatically block accounts, or retaliate against hosts.

## Main capabilities

| Area | What it does |
| --- | --- |
| Event intake | Validates JSON telemetry using FastAPI and Pydantic |
| Session correlation | Groups events by session ID, with user ID / anonymous fallback |
| Behaviour scoring | Scores authentication failures, device/token/source changes, path/object diversity, privilege changes, and high request volume |
| Incident tracking | Stores risk, severity, rule reasons, features, event count, and status in SQLite |
| Analyst dashboard | Displays metrics, events, sessions, incidents, source observations, sensor status, and settings |
| Role-based access | Supports admin, analyst, and viewer roles |
| Windows host agent | Reports CPU, memory, and disk utilisation metadata |
| Passive network sensor | Optionally observes packet-header metadata; it does not intentionally collect packet payloads |
| Offline ML experiment | Trains an IsolationForest model from a prepared session-feature CSV |

## Architecture and workflow

1. Your own application or an optional local agent sends an event to the FastAPI intake endpoint.
2. The API validates the fields and persists the event in SQLite.
3. The correlator groups related events into a session.
4. The rule engine evaluates session history and produces a risk score from 0 to 100.
5. The API creates or updates an incident with the score and human-readable reasons.
6. The dashboard refreshes and presents current telemetry and investigation details.

### Explainable risk signals

| Observed pattern | Points |
| --- | ---: |
| 5 or more HTTP 401/403 responses | +25 |
| More than one device in a session | +18 |
| More than one token fingerprint | +24 |
| More than one source IP | +12 |
| 12 or more distinct paths | +16 |
| 15 or more distinct object IDs | +20 |
| A privilege-change event | +35 |
| 80 or more events within 60 seconds | +22 |
| Login followed by device/token-context change | +12 |
| Combined high event, path, and object diversity | +10 |

The score is capped at 100. Severity levels are Critical (80+), High (60–79), Medium (35–59), Low (15–34), and Info (below 15). These are prototype heuristics, not validated universal thresholds. The confidence value is heuristic, not a calibrated probability.

**ML status:** the bundled training script builds an offline IsolationForest model. The live API does not load or use that model; current real-time alerting is rule-based. The API reports live ML inference as disabled.

## Technology stack

- Python 3.10+
- FastAPI, Uvicorn, and Pydantic
- SQLite
- HTML, CSS, and JavaScript dashboard
- psutil for host-health metadata
- Scapy for optional passive packet-header metadata
- scikit-learn, pandas, and joblib for offline ML experiments

## Windows setup and run

Requirements: Windows 10/11, Python 3.10+ with the Python launcher enabled, and internet access for the first dependency installation.

1. Download the project source package from the original project attachment or the repository owner.
2. Extract it and open the **XEBAC_HAT_AI_IDS_V2** directory.
3. Double-click **run_windows.bat**.
4. On first run, the launcher creates a virtual environment, installs dependencies, generates a temporary JWT signing secret, and asks for an administrator username and password.
5. Use an administrator password of at least 14 characters.
6. Open **http://127.0.0.1:8001**.

API documentation: **http://127.0.0.1:8001/docs**  
Health check: **http://127.0.0.1:8001/api/health**

Keep the console running while using the dashboard. Stop the server with Ctrl+C.

### Manual PowerShell setup

Run from the extracted project directory:

~~~powershell
py -3 -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

$env:XEBAC_JWT_SECRET = (& ".\.venv\Scripts\python.exe" -c "import secrets; print(secrets.token_urlsafe(48))").Trim()
$env:XEBAC_ADMIN_USER = "admin"
$secure = Read-Host "Admin password (14+ characters)" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $env:XEBAC_ADMIN_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}

& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8001
~~~

The first administrator is created only if that username does not already exist. The current version does not include a password-reset workflow. Keep administrator credentials safe.

## Dashboard usage

1. Sign in with the administrator account created on first launch.
2. Review the Overview for event, session, and incident counts.
3. Select **Generate Demo** to create synthetic events and see a sample detection.
4. Review Events, Sessions, and Incidents for the telemetry and reasons behind each score.
5. Admin users can create accounts with admin, analyst, or viewer roles and update incident status.
6. The dashboard refreshes periodically; use Refresh for an immediate update.

## Send events from your own app

Send events only from an application you own or are explicitly authorized to monitor. Use pseudonymous IDs and fingerprints. Never send passwords, cookies, bearer tokens, API keys, or other secrets.

Example PowerShell event:

~~~powershell
$event = @{
  event_type = "api_request"
  timestamp = (Get-Date).ToUniversalTime().ToString("o")
  user_id = "demo-user-01"
  session_id = "session-demo-001"
  token_fingerprint = "fp-demo-rotating-01"
  device_id = "dev-laptop-01"
  client_app = "my-local-app"
  source_ip = "127.0.0.1"
  method = "GET"
  path = "/api/profile"
  status_code = 200
  bytes_in = 120
  bytes_out = 840
  latency_ms = 42
  action = "read"
  object_id = "profile-01"
  privilege_change = $false
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/events" -Method Post -ContentType "application/json" -Body $event
~~~

Endpoint: **POST /api/events**.

## Optional agents

### Windows host agent

With the API running, use a second PowerShell window in the project directory:

~~~powershell
& ".\.venv\Scripts\python.exe" agents\windows_host_agent.py --api http://127.0.0.1:8001/api/events --interval 30
~~~

It reports CPU, memory, and disk utilisation metadata. It does not execute shell commands or collect files.

### Passive network sensor

Only monitor an interface/network you own or are explicitly authorized to observe. Scapy, Npcap, and suitable permissions may be required:

~~~powershell
& ".\.venv\Scripts\python.exe" agents\network_sensor.py --interface "YOUR_INTERFACE_NAME" --api http://127.0.0.1:8001/api/events
~~~

It sends packet metadata such as source/destination addresses, protocol, ports, and packet length. Do not run it on public, shared, or third-party networks without permission.

## Offline ML experiment

Prepare a CSV with at least 100 session rows and these columns:

- events
- unique_paths
- failed_auth_events
- distinct_devices
- distinct_token_fingerprints
- distinct_sources
- distinct_object_ids
- session_span_seconds

Run:

~~~powershell
& ".\.venv\Scripts\python.exe" ml\train_model.py --input .\data\session_features.csv --output .\ml\behaviour_model.joblib
~~~

This model is an offline experiment only. It is not connected to live scoring in the current release. The generated model file is excluded from Git.

## API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | / | Dashboard |
| GET | /api/health | Service health |
| POST | /api/auth/login | Sign in |
| GET | /api/auth/me | Current user |
| GET / POST | /api/auth/users | List/create users (admin) |
| GET | /api/metrics | Dashboard metrics |
| POST | /api/events | Event ingestion |
| GET | /api/events | Recent events (authenticated) |
| GET | /api/sessions | Correlated sessions |
| GET | /api/incidents | Incident list |
| PATCH | /api/incidents/{id} | Update incident status (admin) |
| POST | /api/demo/generate | Synthetic demo events (admin) |
| GET | /api/sensor-health | Sensor status |
| GET | /api/ai/status | Rule/ML status |
| GET | /api/network/activity | Activity buckets |
| GET | /api/settings | Runtime settings |

## Security, privacy, and limitations

- This is a **local defensive prototype**, not a production-certified IDS, SIEM, EDR, or managed security service.
- The default bind address is **127.0.0.1**. Do not expose the server to the internet as-is.
- **POST /api/events is currently unauthenticated** for local sensor intake. Before remote ingestion, add per-agent authentication, TLS, rate limiting, input/logging controls, and network restrictions.
- Protect the SQLite database because telemetry may contain identifying metadata.
- Do not ingest raw passwords, tokens, cookies, API keys, private messages, or packet payloads.
- Use pseudonymous token fingerprints rather than raw token values.
- Restrict host/network collection to authorized devices and networks.
- Evaluate thresholds and false-positive/false-negative rates against representative test data.
- No automatic blocking, endpoint isolation, exploit execution, or retaliation is implemented.

## Repository contents

~~~text
XEBAC_HAT_AI_IDS_V2/
├── app/
│   ├── auth.py
│   ├── db.py
│   ├── detector.py
│   ├── main.py
│   └── static/index.html
├── agents/
│   ├── windows_host_agent.py
│   └── network_sensor.py
├── ml/
│   ├── README.md
│   └── train_model.py
├── data/.gitkeep
├── requirements.txt
├── run_windows.bat
├── run_windows.ps1
├── SECURITY.md
├── CONTRIBUTING.md
└── README.md
~~~

## Contributing and license

Read [SECURITY.md](SECURITY.md) and [CONTRIBUTING.md](CONTRIBUTING.md) before reporting issues or proposing changes. Never publish credentials, private telemetry, or sensitive infrastructure data.

No license file is included. Public visibility allows viewing the project page but does not itself grant permission to reuse, modify, or redistribute the code. Add an explicit license before allowing those uses.
