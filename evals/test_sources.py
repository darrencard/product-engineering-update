#!/usr/bin/env python3
"""Hold the version 0.6 converters to their promises: each system's own export, in its documented shape,
becomes an existing source, maps only fields that exist, and never guesses.

Usage:
  python3 -m unittest discover -s evals -v

Every fixture here is shaped like the vendor's documented response. None of these converters has run
on a live account yet.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_pipeline import script  # noqa: E402  (the shared helpers, beside this file)

Json = dict[str, Any]


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="peu-src-"))
        self.run = self.work / "run"

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def save(self, name: str, data: Any) -> str:
        path = self.work / name
        path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
        return str(path)

    def rows(self, source: str) -> list[Json]:
        return json.loads((self.run / "data" / f"{source}.json").read_text(encoding="utf-8"))["rows"]

    def ok(self, name: str, *args: str) -> str:
        done = script(name, *args, "--run", str(self.run))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return done.stdout

    def refused(self, name: str, *args: str) -> str:
        done = script(name, *args, "--run", str(self.run))
        self.assertNotEqual(done.returncode, 0)
        return done.stderr


class Sentry(Base):
    def releases(self) -> str:
        def release(version: str, finished: str, env: str = "production") -> Json:
            return {
                "version": version,
                "dateCreated": finished,
                "lastDeploy": {"id": version, "environment": env, "dateStarted": None, "dateFinished": finished},
            }

        return self.save(
            "releases.json",
            [
                release("app@1", "2026-07-02T10:00:00Z"),
                release("app@2", "2026-07-09T10:00:00Z"),
                release("app@3", "2026-07-16T10:00:00Z"),
                release("app@4", "2026-07-23T10:00:00Z"),
                release("app@3-staging", "2026-07-17T10:00:00Z", "staging"),
            ],
        )

    def test_a_new_error_after_a_release_or_named_by_it_flags_that_release(self) -> None:
        issues = self.save(
            "issues.json",
            [
                {"id": "1", "level": "error", "status": "unresolved", "count": "4", "firstSeen": "2026-07-10T12:00:00Z", "lastSeen": "2026-07-11T00:00:00Z"},
                {"id": "2", "level": "warning", "count": "9", "firstSeen": "2026-07-24T12:00:00Z"},
                {"id": "3", "level": "fatal", "count": "1", "firstSeen": "2026-06-01T00:00:00Z", "firstRelease": {"version": "app@4"}},
            ],
        )
        out = self.ok("from_sentry.py", "--releases", self.releases(), "--issues", issues, "--errors-from", "2026-07-05", "--organization", "acme")
        self.assertIn("4 releases deployed to production, 3 with a known outcome", out)
        flags = {r["id"]: r["troubled"] for r in self.rows("source_control")}
        self.assertEqual(flags, {"sentry-app@1": None, "sentry-app@2": True, "sentry-app@3": False, "sentry-app@4": True})
        self.assertIn("proxy for change failure rate", out)

    def test_no_production_release_is_refused(self) -> None:
        issues = self.save("issues.json", [])
        empty = self.save("none.json", [{"version": "x", "lastDeploy": {"environment": "staging", "dateFinished": "2026-07-02T10:00:00Z"}}])
        self.assertIn(
            "found no release deployed to production",
            self.refused("from_sentry.py", "--releases", empty, "--issues", issues, "--errors-from", "2026-07-01", "--organization", "acme"),
        )


if __name__ == "__main__":
    unittest.main()
