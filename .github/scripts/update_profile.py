from __future__ import annotations

import base64
import gzip
import html
import json
import os
import textwrap
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OWNER = "StreckerMX"
REPO = "FrameView-Analyzer"
BASE = f"https://api.github.com/repos/{OWNER}/{REPO}"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Self-contained Windows Terminal profile template (gzip + base64).
# Keeping the rendered design here means scheduled refreshes cannot drift back
# to an older visual template while updating live telemetry.
TEMPLATE_GZ_B64 = (
    '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'
)


def api(path: str):
    base_headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "StreckerMX-profile-updater",
    }
    attempts = [
        {**base_headers, **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {})},
        base_headers,
    ]
    last_error = None
    for headers in attempts:
        try:
            req = urllib.request.Request(BASE + path, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if not TOKEN or exc.code not in (403, 404):
                raise
    raise last_error


def safe_api(path: str, default):
    try:
        return api(path)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return default


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def date_only(value: str | None) -> str:
    if not value:
        return "N/A"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return value[:10]


repo = safe_api("", {})
release = safe_api("/releases/latest", {})
commits = safe_api("/commits?sha=main&per_page=1", [])
runs = safe_api("/actions/runs?branch=main&status=completed&per_page=10", {"workflow_runs": []})
pulls = safe_api("/pulls?state=open&per_page=100", [])
languages = safe_api("/languages", {})

latest_commit = commits[0] if commits else {}
commit_data = latest_commit.get("commit", {})
commit_message = (commit_data.get("message") or "No commit data").splitlines()[0]
commit_message = textwrap.shorten(commit_message, width=58, placeholder="…")
commit_date = (commit_data.get("committer") or {}).get("date") or (commit_data.get("author") or {}).get("date")

workflow_runs = runs.get("workflow_runs", []) if isinstance(runs, dict) else []
ci_conclusion = next((r.get("conclusion") for r in workflow_runs if r.get("conclusion")), None)
ci_status = {
    "success": "PASSING",
    "failure": "FAILING",
    "cancelled": "CANCELLED",
    "timed_out": "TIMED OUT",
    "action_required": "ACTION REQUIRED",
    "neutral": "NEUTRAL",
    "skipped": "SKIPPED",
}.get(ci_conclusion, "UNKNOWN")

primary_language = max(languages, key=languages.get) if languages else repo.get("language") or "C#"
latest_release = release.get("tag_name") or release.get("name") or "No release"
release_date = date_only(release.get("published_at") or release.get("created_at"))

replacements = {
    "{{LATEST_RELEASE}}": latest_release,
    "{{STARS}}": repo.get("stargazers_count", 0),
    "{{CI_STATUS}}": ci_status,
    "{{OPEN_PRS}}": len(pulls) if isinstance(pulls, list) else 0,
    "{{PRIMARY_LANGUAGE}}": primary_language,
    "{{RELEASE_DATE}}": release_date,
    "{{LAST_COMMIT_SHA}}": (latest_commit.get("sha") or "N/A")[:7],
    "{{LAST_COMMIT_MSG}}": commit_message,
    "{{LAST_COMMIT_DATE}}": date_only(commit_date),
    "{{SYNC_DATE}}": datetime.now(timezone.utc).strftime("%Y-%m-%d UTC"),
}

text = gzip.decompress(base64.b64decode(TEMPLATE_GZ_B64)).decode("utf-8")
for token, value in replacements.items():
    text = text.replace(token, esc(value))

out_path = Path("assets/profile-hero.svg")
out_path.write_text(text, encoding="utf-8")
print("Updated", out_path)
for token, value in replacements.items():
    print(token, "=", value)
