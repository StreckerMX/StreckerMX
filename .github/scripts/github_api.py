"""Fetch the telemetry the profile card shows - and refuse to invent it.

The generator used to answer every failed request with a default, so a rate limit or a
timeout produced a card reading `stars: 0` / `No release` that looked exactly like a real
one. Nothing here has a default: a request either arrives and validates, or it raises
`TelemetryError`, and `profile_v3.py` then leaves `assets/profile-hero.svg` untouched and
exits non-zero.

**The rule that decides what is fatal.** Anything that would be rendered as a *plausible
value* - a star count, a release name, a commit SHA, a CI state, a PR count, a language -
is fatal when it cannot be obtained, because a wrong number and a missing number look the
same on the card. Anything that renders as an explicit marker (`N/A`, `No commit data`,
`UNKNOWN`, `No release`) is not fatal, because the marker cannot be mistaken for data.
A genuine `0` stars, a genuine `[]` of open pull requests and a genuine `404` on
`/releases/latest` are answers, not failures, and are kept as such.

**Authentication**, resolved once per process and never written anywhere by this module:

1. `GITHUB_TOKEN` - what GitHub Actions injects into the step.
2. `GH_TOKEN` - the name the GitHub CLI itself reads.
3. `gh auth token`, asked once per process, for a machine with the CLI logged in.
4. nothing - public access is attempted, and failures are reported rather than hidden.

**Rate limits, because the numbers get quoted wrong.** GitHub documents *1,000 requests
per hour per repository* for the automatic `GITHUB_TOKEN` in Actions, and 5,000 per hour
for a personal access token. An anonymous caller from one address gets 60 per hour, which
is what a local run without any of the above is up against. Every 403/429 is reported with
the `X-RateLimit-*` headers when the server sends them.

`PROFILE_API_BASE` overrides the API root. It exists so the tests can point the generator
at a local server; nothing else sets it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
import urllib.error
import urllib.request
from datetime import datetime, timezone

DEFAULT_REPO = "StreckerMX/FrameView-Analyzer"
DEFAULT_TIMEOUT = 25
RATE_HEADERS = ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset")

CI_STATES = {
    "success": "PASSING",
    "failure": "FAILING",
    "cancelled": "CANCELLED",
    "timed_out": "TIMED OUT",
}


class TelemetryError(RuntimeError):
    """A request failed, or answered something that cannot be used."""

    def __init__(self, message, *, url=None, status=None, headers=None):
        self.url = url
        self.status = status
        self.headers = headers or {}
        lines = [message]
        if status is not None:
            lines[0] += f" (HTTP {status})"
        if url:
            lines.append(f"  url: {url}")
        note = rate_limit_note(self.headers)
        if note:
            lines.append(f"  {note}")
        super().__init__("\n".join(lines))


def rate_limit_note(headers):
    """The X-RateLimit-* values, when the server sent them, plus a readable reset time."""
    if not headers:
        return ""
    parts = []
    for name in RATE_HEADERS:
        value = headers.get(name) if hasattr(headers, "get") else None
        if value is not None:
            parts.append(f"{name}={value}")
    reset = headers.get("X-RateLimit-Reset") if hasattr(headers, "get") else None
    if reset is not None and str(reset).isdigit():
        try:
            when = datetime.fromtimestamp(int(reset)).strftime("%Y-%m-%d %H:%M:%S")
            parts.append(f"reset at {when} (local time)")
        except (OverflowError, OSError, ValueError):
            pass
    retry = headers.get("Retry-After") if hasattr(headers, "get") else None
    if retry is not None:
        parts.append(f"Retry-After={retry}")
    return "rate limit: " + ", ".join(parts) if parts else ""


_TOKEN = None
_TOKEN_RESOLVED = False


def resolve_token(environ=None, runner=None):
    """GITHUB_TOKEN, then GH_TOKEN, then one `gh auth token` per process, else None."""
    global _TOKEN, _TOKEN_RESOLVED
    if _TOKEN_RESOLVED:
        return _TOKEN
    _TOKEN_RESOLVED = True

    env = os.environ if environ is None else environ
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = (env.get(name) or "").strip()
        if value:
            _TOKEN = value
            return _TOKEN

    run = subprocess.run if runner is None else runner
    gh = shutil.which("gh") or "gh"
    try:
        done = run([gh, "auth", "token"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode == 0:
        value = (done.stdout or "").strip()
        if value:
            _TOKEN = value
    return _TOKEN


def reset_token_cache():
    """Tests only: forget the per-process token so resolution runs again."""
    global _TOKEN, _TOKEN_RESOLVED
    _TOKEN = None
    _TOKEN_RESOLVED = False


def api_base(environ=None):
    """The API root, overridable so tests can serve it from localhost."""
    env = os.environ if environ is None else environ
    override = (env.get("PROFILE_API_BASE") or "").strip()
    return (override or f"https://api.github.com/repos/{DEFAULT_REPO}").rstrip("/")


class Client:
    """GETs one API root. Every failure is an exception; nothing is ever defaulted."""

    def __init__(self, base, token=None, opener=None, timeout=DEFAULT_TIMEOUT):
        self.base = base.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._open = opener or urllib.request.urlopen

    def _headers(self):
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "StreckerMX-profile",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get(self, path, *, allow_missing=False):
        """The decoded body, or None when a missing resource is a legitimate answer."""
        url = f"{self.base}{path}"
        request = urllib.request.Request(url, headers=self._headers())
        try:
            with self._open(request, timeout=self.timeout) as response:
                payload = response.read()
        except urllib.error.HTTPError as err:
            if allow_missing and err.code == 404:
                return None
            raise TelemetryError(f"request failed: {path or '/'}", url=url, status=err.code,
                                 headers=err.headers) from None
        except urllib.error.URLError as err:
            raise TelemetryError(f"request failed: {path or '/'}: {err.reason}", url=url) from None
        except TimeoutError:
            raise TelemetryError(f"timed out after {self.timeout}s: {path or '/'}", url=url) from None
        except OSError as err:
            raise TelemetryError(f"network failure: {path or '/'}: {err}", url=url) from None
        try:
            return json.loads(payload)
        except ValueError as err:
            raise TelemetryError(f"unparseable JSON from {path or '/'}: {err}", url=url) from None


def _object(payload, what):
    if not isinstance(payload, dict):
        raise TelemetryError(f"{what} answered {type(payload).__name__}, expected an object")
    return payload


def _array(payload, what):
    if not isinstance(payload, list):
        raise TelemetryError(f"{what} answered {type(payload).__name__}, expected a list")
    return payload


def _integer(source, field, what):
    value = source.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise TelemetryError(f"{what} did not return {field!r}")
    return value


def _text(source, field, what):
    value = source.get(field)
    if not isinstance(value, str) or not value.strip():
        raise TelemetryError(f"{what} did not return {field!r}")
    return value.strip()


def day(value):
    """A date as the card shows it, or the explicit marker when there is none to show."""
    try:
        return datetime.fromisoformat((value or "").replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return "N/A"


def fetch_telemetry(base=None, token=None, opener=None, timeout=DEFAULT_TIMEOUT, now=None):
    """Everything the card prints, or a TelemetryError. Never a default."""
    client = Client(base or api_base(),
                    token=resolve_token() if token is None else token,
                    opener=opener, timeout=timeout)

    repo = _object(client.get(""), "the repository")
    stars = _integer(repo, "stargazers_count", "the repository")

    release = client.get("/releases/latest", allow_missing=True)
    if release is None:
        rel = "No release"                      # a real 404: this repository has none
        rdate = "N/A"
    else:
        release = _object(release, "the latest release")
        rel = release.get("tag_name") or release.get("name")
        if not isinstance(rel, str) or not rel.strip():
            raise TelemetryError("the latest release returned neither tag_name nor name")
        rel = rel.strip()
        rdate = day(release.get("published_at") or release.get("created_at"))

    commits = _array(client.get("/commits?sha=main&per_page=1"), "the commit list")
    if commits:
        latest = _object(commits[0], "the latest commit")
        sha = _text(latest, "sha", "the latest commit")[:7]
        commit = _object(latest.get("commit"), "the latest commit's commit object")
        message = (commit.get("message") or "").strip()
        msg = textwrap.shorten(message.splitlines()[0], 58, placeholder="…") if message else "No commit data"
        cdate = day((commit.get("committer") or {}).get("date")
                    or (commit.get("author") or {}).get("date"))
    else:
        sha, msg, cdate = "N/A", "No commit data", "N/A"

    runs = _object(client.get("/actions/runs?branch=main&status=completed&per_page=10"),
                   "the workflow runs")
    workflow_runs = _array(runs.get("workflow_runs"), "the workflow runs")
    conclusion = next((run.get("conclusion") for run in workflow_runs
                       if isinstance(run, dict) and run.get("conclusion")), None)
    ci = CI_STATES.get(conclusion, "UNKNOWN")

    pulls = _array(client.get("/pulls?state=open&per_page=100"), "the open pull requests")
    langs = _object(client.get("/languages"), "the language breakdown")
    language = max(langs, key=langs.get) if langs else (repo.get("language") or "N/A")

    return {
        "rel": rel,
        "stars": stars,
        "ci": ci,
        "prs": len(pulls),
        "lang": language,
        "rdate": rdate,
        "sha": sha,
        "msg": msg,
        "cdate": cdate,
        "sync": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d UTC"),
    }
