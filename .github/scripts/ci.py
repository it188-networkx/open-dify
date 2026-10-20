"""Conservative PR scope and fail-closed aggregate gate."""
import os
import subprocess
import sys


def git(*args):
    return subprocess.check_output(["git", *args])


def changed():
    base = os.environ.get("CI_BASE_SHA")
    if not base and os.environ.get("ACT") == "true":
        base = "origin/main"
    if not base:
        raise ValueError("CI_BASE_SHA is required")
    base = git("merge-base", base, "HEAD").decode().strip()
    # No renames exposes both sides of moves; NUL handles spaces and newlines.
    return [p.decode() for p in git("diff", "--name-only", "--no-renames", "-z", base, "HEAD").split(b"\0") if p]


def scopes(files):
    selected = dict.fromkeys(("api", "web", "vdb", "migration"), not files)
    workflow_scopes = {
        ".github/workflows/api-tests.yml": ("api",),
        ".github/workflows/web-tests.yml": ("web",),
        ".github/workflows/vdb-tests.yml": ("vdb",),
        ".github/workflows/db-migration-test.yml": ("migration",),
        ".github/workflows/style.yml": ("api", "web"),
    }
    for path in files:
        if path in {"README.md", "AGENTS.md"}:
            continue
        if path in workflow_scopes:
            keys = workflow_scopes[path]
        elif path.startswith("web/"):
            keys = ("web",)
        elif path.startswith("api/"):
            keys = ["api"]
            if path.startswith("api/migrations/"):
                keys.append("migration")
            if path.startswith(("api/core/rag/datasource/", "api/tests/integration_tests/vdb/")):
                keys.append("vdb")
            if path in {"api/uv.lock", "api/pyproject.toml"} or path.startswith(("api/configs/", "api/extensions/", "api/models/")):
                keys.extend(("vdb", "migration"))
        else:
            keys = selected
        for key in keys:
            selected[key] = True
    return selected


def gate(jobs):
    if jobs["check-changes"]["result"] != "success":
        return False
    flags = jobs["check-changes"]["outputs"]
    if any(flags.get(name + "-changed") not in ("true", "false")
           for name in ("api", "web", "vdb", "migration")):
        return False
    for job, scope in [("api-tests", "api"), ("web-tests", "web"),
                       ("vdb-tests", "vdb"), ("db-migration-test", "migration")]:
        expected = "success" if flags[scope + "-changed"] == "true" else "skipped"
        if jobs[job]["result"] != expected:
            return False
    style = flags["api-changed"] == "true" or flags["web-changed"] == "true"
    return jobs["style-check"]["result"] == ("success" if style else "skipped")


if __name__ == "__main__":
    if sys.argv[1] == "plan":
        flags = scopes([] if os.environ.get("ACT") == "true" else changed())
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            for key, value in flags.items():
                output.write(key + "=" + str(value).lower() + "\n")
    elif sys.argv[1] == "gate":
        import json
        if not gate(json.loads(os.environ["RESULTS"])):
            raise SystemExit("Required PR checks failed or did not complete")
    else:
        raise SystemExit("Unknown command")
