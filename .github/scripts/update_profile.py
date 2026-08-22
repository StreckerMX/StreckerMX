from __future__ import annotations

# Regenerates the public profile SVG from live FrameView Analyzer repository data.
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

template_path = Path("assets/profile-hero.template.svg")
out_path = Path("assets/profile-hero.svg")
text = template_path.read_text(encoding="utf-8")
for token, value in replacements.items():
    text = text.replace(token, esc(value))

out_path.write_text(text, encoding="utf-8")
print("Updated", out_path)
for token, value in replacements.items():
    print(token, "=", value)