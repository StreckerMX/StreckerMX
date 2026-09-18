"""Tests for the profile generator's telemetry: it must never invent data.

Everything runs offline. `_FakeGitHub` is a local HTTP server standing in for
api.github.com, so a rate limit is a 403 with the headers GitHub sends, a timeout is a
handler that sleeps, and a legitimately empty repository is a set of empty answers.

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import github_api  # noqa: E402

GENERATOR = SCRIPTS / "profile_v3.py"

# A payload set shaped like the real repository, so the golden values double as a check
# that the card's numbers still come from the same fields.
HEALTHY = {
    "/": (200, {}, {"stargazers_count": 4, "language": "C#"}),
    "/releases/latest": (200, {}, {"tag_name": "v4.1.0", "published_at": "2026-09-17T10:00:00Z"}),
    "/commits?sha=main&per_page=1": (200, {}, [{
        "sha": "8874738abcdef0123456789",
        "commit": {"message": "test: wait for multi reanalysis failure completion\n\nbody text",
                   "committer": {"date": "2026-09-17T09:30:00Z"}},
    }]),
    "/actions/runs?branch=main&status=completed&per_page=10": (200, {}, {"workflow_runs": [
        {"conclusion": "success"},
    ]}),
    "/pulls?state=open&per_page=100": (200, {}, []),
    "/languages": (200, {}, {"C#": 4270025, "HLSL": 12288}),
}

EMPTY = {
    "/": (200, {}, {"stargazers_count": 0, "language": None}),
    "/releases/latest": (404, {}, {"message": "Not Found"}),
    "/commits?sha=main&per_page=1": (200, {}, []),
    "/actions/runs?branch=main&status=completed&per_page=10": (200, {}, {"workflow_runs": []}),
    "/pulls?state=open&per_page=100": (200, {}, []),
    "/languages": (200, {}, {}),
}


class _FakeHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler's spelling
        fake = self.server.fake
        fake.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}})
        route = fake.routes.get(self.path)
        if route is None:
            self.send_error(404, "no route")
            return
        status, headers, body = route
        if fake.delay:
            time.sleep(fake.delay)
        payload = json.dumps(body).encode() if isinstance(body, (dict, list)) else str(body).encode()
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class _FakeGitHub:
    """A local stand-in for api.github.com that records what was asked of it."""

    def __init__(self, routes, delay=0.0):
        self.routes = routes
        self.delay = delay
        self.requests = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeHandler)
        self.server.fake = self
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base(self):
        host, port = self.server.server_address[:2]
        return f"http://{host}:{port}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    def sent_authorization(self):
        return [r["headers"].get("authorization") for r in self.requests if "authorization" in r["headers"]]


class ClientTests(unittest.TestCase):
    """The transport: every failure mode maps to an exception, never to a value."""

    def test_rate_limit_403_reports_the_headers(self):
        headers = {"X-RateLimit-Limit": "60", "X-RateLimit-Remaining": "0",
                   "X-RateLimit-Reset": "1789693554"}
        with _FakeGitHub({"/": (403, headers, {"message": "API rate limit exceeded"})}) as fake:
            with self.assertRaises(github_api.TelemetryError) as caught:
                github_api.Client(fake.base).get("")
        text = str(caught.exception)
        self.assertEqual(caught.exception.status, 403)
        for expected in ("X-RateLimit-Limit=60", "X-RateLimit-Remaining=0", "X-RateLimit-Reset=1789693554"):
            self.assertIn(expected, text)
        self.assertIn("reset at", text)

    def test_429_also_reports_retry_after(self):
        with _FakeGitHub({"/": (429, {"Retry-After": "60"}, "slow down")}) as fake:
            with self.assertRaises(github_api.TelemetryError) as caught:
                github_api.Client(fake.base).get("")
        self.assertEqual(caught.exception.status, 429)
        self.assertIn("Retry-After=60", str(caught.exception))

    def test_timeout_is_an_error_not_an_empty_answer(self):
        with _FakeGitHub({"/": (200, {}, {"stargazers_count": 1})}, delay=3.0) as fake:
            with self.assertRaises(github_api.TelemetryError) as caught:
                github_api.Client(fake.base, timeout=1).get("")
        self.assertIn("timed out", str(caught.exception))

    def test_invalid_json_is_an_error(self):
        with _FakeGitHub({"/": (200, {}, "<html>not json</html>")}) as fake:
            with self.assertRaises(github_api.TelemetryError) as caught:
                github_api.Client(fake.base).get("")
        self.assertIn("unparseable JSON", str(caught.exception))

    def test_http_500_is_an_error(self):
        with _FakeGitHub({"/": (500, {}, "boom")}) as fake:
            with self.assertRaises(github_api.TelemetryError) as caught:
                github_api.Client(fake.base).get("")
        self.assertEqual(caught.exception.status, 500)

    def test_404_is_none_only_when_it_is_allowed_to_be(self):
        with _FakeGitHub({"/releases/latest": (404, {}, {"message": "Not Found"})}) as fake:
            client = github_api.Client(fake.base)
            self.assertIsNone(client.get("/releases/latest", allow_missing=True))
            with self.assertRaises(github_api.TelemetryError):
                client.get("/releases/latest")

    def test_token_is_sent_when_present_and_absent_when_not(self):
        with _FakeGitHub({"/": (200, {}, {"stargazers_count": 1})}) as fake:
            github_api.Client(fake.base, token="s3cret-token").get("")
            self.assertEqual(fake.sent_authorization(), ["Bearer s3cret-token"])
            github_api.Client(fake.base).get("")
            self.assertIsNone(fake.requests[-1]["headers"].get("authorization"))


class TokenResolutionTests(unittest.TestCase):
    def setUp(self):
        github_api.reset_token_cache()
        self.addCleanup(github_api.reset_token_cache)

    def test_github_token_wins_and_gh_is_not_called(self):
        runner = mock.Mock(side_effect=AssertionError("gh must not be called"))
        token = github_api.resolve_token({"GITHUB_TOKEN": "from-actions", "GH_TOKEN": "from-gh"}, runner)
        self.assertEqual(token, "from-actions")

    def test_gh_token_is_used_when_github_token_is_absent(self):
        runner = mock.Mock(side_effect=AssertionError("gh must not be called"))
        self.assertEqual(github_api.resolve_token({"GH_TOKEN": "from-gh"}, runner), "from-gh")

    def test_blank_values_do_not_count_as_a_token(self):
        """A blank variable is not a token, so resolution moves on to `gh`."""
        calls = []

        def runner(argv, **kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="not logged in")

        self.assertIsNone(github_api.resolve_token({"GITHUB_TOKEN": "   ", "GH_TOKEN": ""}, runner))
        self.assertEqual(len(calls), 1, "gh is still asked when both variables are blank")

    def test_gh_auth_token_is_asked_once_per_process(self):
        calls = []

        def runner(argv, **kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, stdout="token-from-gh\n", stderr="")

        self.assertEqual(github_api.resolve_token({}, runner), "token-from-gh")
        self.assertEqual(github_api.resolve_token({}, runner), "token-from-gh")
        self.assertEqual(len(calls), 1, "gh auth token must be asked once per process")
        self.assertIn("auth", calls[0])

    def test_no_authentication_available_resolves_to_none(self):
        def runner(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="not logged in")

        self.assertIsNone(github_api.resolve_token({}, runner))

    def test_gh_missing_from_the_machine_is_not_an_error(self):
        def runner(argv, **kwargs):
            raise FileNotFoundError("gh is not installed")

        self.assertIsNone(github_api.resolve_token({}, runner))


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        github_api.reset_token_cache()
        self.addCleanup(github_api.reset_token_cache)
        self._no_proxy = os.environ.get("no_proxy")
        os.environ["no_proxy"] = "127.0.0.1,localhost"
        self.addCleanup(self._restore_proxy)

    def _restore_proxy(self):
        if self._no_proxy is None:
            os.environ.pop("no_proxy", None)
        else:
            os.environ["no_proxy"] = self._no_proxy

    def test_a_healthy_run_returns_the_values_the_card_shows(self):
        with _FakeGitHub(HEALTHY) as fake:
            data = github_api.fetch_telemetry(base=fake.base, token="t", now=_fixed_now())
        self.assertEqual(data, {
            "rel": "v4.1.0", "stars": 4, "ci": "PASSING", "prs": 0, "lang": "C#",
            "rdate": "2026-09-17", "sha": "8874738", "msg": "test: wait for multi reanalysis failure completion",
            "cdate": "2026-09-17", "sync": "2026-09-18 UTC",
        })

    def test_legitimately_empty_answers_are_kept_as_markers(self):
        """A real 404, a real 0 and a real [] are answers: they must not raise."""
        with _FakeGitHub(EMPTY) as fake:
            data = github_api.fetch_telemetry(base=fake.base, token="t", now=_fixed_now())
        self.assertEqual(data["stars"], 0, "a genuine zero star count is data, not a failure")
        self.assertEqual(data["prs"], 0)
        self.assertEqual(data["rel"], "No release")
        self.assertEqual(data["sha"], "N/A")
        self.assertEqual(data["msg"], "No commit data")
        self.assertEqual(data["cdate"], "N/A")
        self.assertEqual(data["ci"], "UNKNOWN")
        self.assertEqual(data["lang"], "N/A")

    def test_a_missing_star_count_is_fatal_not_zero(self):
        routes = dict(HEALTHY, **{"/": (200, {}, {"language": "C#"})})
        with _FakeGitHub(routes) as fake:
            with self.assertRaises(github_api.TelemetryError) as caught:
                github_api.fetch_telemetry(base=fake.base, token="t")
        self.assertIn("stargazers_count", str(caught.exception))

    def test_a_commit_without_a_sha_is_fatal(self):
        routes = dict(HEALTHY, **{"/commits?sha=main&per_page=1": (200, {}, [{"commit": {"message": "x"}}])})
        with _FakeGitHub(routes) as fake:
            with self.assertRaises(github_api.TelemetryError) as caught:
                github_api.fetch_telemetry(base=fake.base, token="t")
        self.assertIn("sha", str(caught.exception))

    def test_workflow_runs_of_the_wrong_shape_is_fatal(self):
        routes = dict(HEALTHY, **{"/actions/runs?branch=main&status=completed&per_page=10":
                                  (200, {}, {"workflow_runs": "nope"})})
        with _FakeGitHub(routes) as fake:
            with self.assertRaises(github_api.TelemetryError):
                github_api.fetch_telemetry(base=fake.base, token="t")

    def test_a_release_without_a_name_is_fatal(self):
        routes = dict(HEALTHY, **{"/releases/latest": (200, {}, {"assets": []})})
        with _FakeGitHub(routes) as fake:
            with self.assertRaises(github_api.TelemetryError) as caught:
                github_api.fetch_telemetry(base=fake.base, token="t")
        self.assertIn("tag_name", str(caught.exception))

    def test_an_error_never_carries_the_token(self):
        secret = "ghp_this_must_never_be_printed"
        with _FakeGitHub({"/": (403, {"X-RateLimit-Remaining": "0"}, "denied")}) as fake:
            with self.assertRaises(github_api.TelemetryError) as caught:
                github_api.fetch_telemetry(base=fake.base, token=secret)
        self.assertNotIn(secret, str(caught.exception))


class GeneratorProtectionTests(unittest.TestCase):
    """The script end to end: a failed run must leave the card exactly as it was."""

    EXISTING = "<svg><!-- the card as it was before this run --></svg>"

    def _run(self, routes, token="t"):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        work = Path(self.tmp.name)
        (work / "assets").mkdir()
        card = work / "assets" / "profile-hero.svg"
        card.write_text(self.EXISTING, encoding="utf-8")
        env = {k: v for k, v in os.environ.items()
               if k not in ("GITHUB_TOKEN", "GH_TOKEN", "PROFILE_API_BASE")}
        env.update({"PYTHONDONTWRITEBYTECODE": "1", "no_proxy": "127.0.0.1,localhost"})
        if token:
            env["GITHUB_TOKEN"] = token
        with _FakeGitHub(routes) as fake:
            env["PROFILE_API_BASE"] = fake.base
            done = subprocess.run([sys.executable, str(GENERATOR)], cwd=work, env=env,
                                  capture_output=True, text=True, timeout=120)
            return done, card, fake

    def test_the_card_is_not_written_when_the_api_fails(self):
        done, card, _ = self._run({"/": (500, {}, "boom")})
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(card.read_text(encoding="utf-8"), self.EXISTING)
        self.assertIn("profile telemetry unavailable", done.stderr)
        self.assertIn("request failed: /", done.stderr, "the diagnosis must name the endpoint")

    def test_the_card_is_not_written_on_a_rate_limit_and_the_headers_are_shown(self):
        routes = {"/": (403, {"X-RateLimit-Limit": "60", "X-RateLimit-Remaining": "0",
                              "X-RateLimit-Reset": "1789693554"}, "denied")}
        done, card, _ = self._run(routes)
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(card.read_text(encoding="utf-8"), self.EXISTING)
        for expected in ("X-RateLimit-Limit=60", "X-RateLimit-Remaining=0", "X-RateLimit-Reset=1789693554"):
            self.assertIn(expected, done.stderr)

    def test_a_failure_in_the_middle_of_the_run_still_protects_the_card(self):
        """The fifth call failing must be as harmless as the first."""
        routes = dict(HEALTHY, **{"/pulls?state=open&per_page=100": (500, {}, "boom")})
        done, card, _ = self._run(routes)
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(card.read_text(encoding="utf-8"), self.EXISTING)
        self.assertIn("/pulls", done.stderr)

    def test_a_healthy_run_writes_the_card_and_uses_the_token(self):
        done, card, fake = self._run(HEALTHY, token="s3cret-token")
        self.assertEqual(done.returncode, 0, done.stderr)
        written = card.read_text(encoding="utf-8")
        self.assertNotEqual(written, self.EXISTING)
        self.assertIn("v4.1.0", written)
        self.assertIn("Bearer s3cret-token", fake.sent_authorization())
        self.assertNotIn("s3cret-token", done.stdout + done.stderr)

    def test_a_legitimately_empty_repository_still_writes_the_card(self):
        done, card, _ = self._run(EMPTY)
        self.assertEqual(done.returncode, 0, done.stderr)
        written = card.read_text(encoding="utf-8")
        self.assertNotEqual(written, self.EXISTING)
        self.assertIn("No release", written)
        self.assertIn("No commit data", written)


def _fixed_now():
    from datetime import datetime, timezone
    return datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
