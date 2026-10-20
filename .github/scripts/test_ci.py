import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("ci", Path(__file__).with_name("ci.py"))
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class PolicyTests(unittest.TestCase):
    def test_known_paths_select_the_affected_checks(self):
        cases = [
            ("web/app/page.tsx", {"web"}),
            ("api/services/app_service.py", {"api"}),
            ("api/migrations/versions/example.py", {"api", "migration"}),
            ("api/core/rag/datasource/vdb/example.py", {"api", "vdb"}),
            ("api/uv.lock", {"api", "vdb", "migration"}),
            ("api/configs/app_config.py", {"api", "vdb", "migration"}),
            ("api/pyproject.toml", {"api", "vdb", "migration"}),
            ("README.md", set()),
        ]
        for path, expected in cases:
            with self.subTest(path=path):
                self.assertEqual({key for key, value in ci.scopes([path]).items() if value}, expected)

    def test_unknown_paths_and_missing_diff_run_everything(self):
        for files in [[], ["unknown"], ["docker/compose.yml"], [".github/scripts/ci.py"],
                      [".github/workflows/main-ci.yml"], ["README.md", "deleted-code"]]:
            with self.subTest(files=files):
                self.assertTrue(all(ci.scopes(files).values()))

    def test_gate_requires_exact_planned_results(self):
        for run in (True, False):
            flags = {key + "-changed": str(run).lower() for key in ("api", "web", "vdb", "migration")}
            jobs = {"check-changes": {"result": "success", "outputs": flags}}
            for name in ("api-tests", "web-tests", "vdb-tests", "db-migration-test", "style-check"):
                jobs[name] = {"result": "success" if run else "skipped"}
            self.assertTrue(ci.gate(jobs))
            for name in jobs:
                original = jobs[name]["result"]
                for bad in ("failure", "cancelled", ""):
                    jobs[name]["result"] = bad
                    self.assertFalse(ci.gate(jobs), (name, bad))
                jobs[name]["result"] = original
            jobs["api-tests"]["result"] = "skipped" if run else "success"
            self.assertFalse(ci.gate(jobs))
            flags["api-changed"] = ""
            self.assertFalse(ci.gate(jobs))
