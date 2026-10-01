# Validation record

Validated on **October 1, 2026**, using Python **3.14.0** on Windows. Dependency versions are recorded in `requirements.lock.txt`.

| Check | Result |
| --- | --- |
| Unit / ingestion / API / LLM adapter / report tests | **41 passed** |
| Ruff lint | Passed |
| Ruff format check | Passed, all project Python files |
| Seeded demo export | 640 records, 8 taxonomy themes, 36 customer-language phrases |
| Top seeded campaign | Get your Mondays back; 148 supporting records; priority 56.1/100 |
| Browser navigation | All 8 views rendered without Streamlit exceptions |
| Browser report download | Downloaded Markdown; synthetic-data label verified |
| Browser segment filtering | Operations manager scope successfully applied |
| Dashboard screenshots | Real local Chrome captures; desktop and mobile viewports |
| Live paid LLM request | Not run; HTTP transport, credentials, malformed responses, timeouts, and evidence validation tested with mocks |
| Docker build / Compose execution | Not run; Docker is unavailable on this workstation |
| CI Python 3.11 / 3.12 / 3.14 matrix | Workflow included; remote CI has not been executed |

The installed Starlette version emits a deprecation warning about its TestClient's httpx compatibility. The suite passes; no warnings are suppressed. Docker and cross-version results are not claimed as verified.

The standard README ports were occupied by existing applications. The local preview uses **API 8011** and **dashboard 8511** without modifying those applications. The README and Compose retain conventional ports 8000 / 8501.

## Reproduce

```bash
python -m pip install -c requirements.lock.txt -e '.[dev]'
python -m pytest -q
ruff check .
ruff format --check .
python scripts/export_demo.py

# With FastAPI and Streamlit already running:
python scripts/capture_dashboard.py --channel chrome
```

Use `--url http://127.0.0.1:8511` if reproducing against this session's preview. For environments without Chrome, install Playwright Chromium and omit `--channel chrome`.

Tests make temporary SQLite databases and perform no live provider calls. Browser verification uses only the fictional demo and a loopback API. The screenshot script overwrites its own screenshots and saves a temporary report download, which is excluded from Git.
