#!/usr/bin/env python3
"""Run deterministic source, generated-artifact, and placeholder policy checks."""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import subprocess
import sys
import tokenize
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def _run(name: str, command: list[str], *, env: dict[str, str] | None = None) -> Check:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), **(env or {})},
        capture_output=True,
        text=True,
        check=False,
    )
    detail = ((completed.stdout or "") + (completed.stderr or "")).strip()[-4000:]
    return Check(name, "passed" if completed.returncode == 0 else "failed", detail)


def _production_python_files() -> Iterable[Path]:
    for root in [ROOT / "src", ROOT / "services", ROOT / "workers", ROOT / "tools"]:
        for path in sorted(root.rglob("*.py")):
            if any(part in {"__pycache__", ".build", "node_modules"} for part in path.parts):
                continue
            yield path


def _source_policy() -> Check:
    findings: list[str] = []
    forbidden_markers = ("TODO", "FIXME", "XXX", "HACK")
    for path in _production_python_files():
        relative = path.relative_to(ROOT)
        source = path.read_text(encoding="utf-8")
        try:
            tokens = tokenize.generate_tokens(io.StringIO(source).readline)
            for token in tokens:
                if token.type == tokenize.COMMENT and any(marker in token.string for marker in forbidden_markers):
                    findings.append(f"{relative}:{token.start[0]}: placeholder marker in comment")
        except (tokenize.TokenError, IndentationError) as exc:
            findings.append(f"{relative}: tokenization error: {exc}")
        try:
            tree = ast.parse(source, filename=str(relative))
        except SyntaxError as exc:
            findings.append(f"{relative}:{exc.lineno}: syntax error: {exc.msg}")
            continue
        parent: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parent[child] = node
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = list(node.body)
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                    body = body[1:]
                decorators = {
                    item.id if isinstance(item, ast.Name) else item.attr if isinstance(item, ast.Attribute) else ""
                    for item in node.decorator_list
                }
                owner = parent.get(node)
                protocol_owner = isinstance(owner, ast.ClassDef) and any(
                    (isinstance(base, ast.Name) and base.id in {"Protocol", "ABC"})
                    or (isinstance(base, ast.Attribute) and base.attr in {"Protocol", "ABC"})
                    for base in owner.bases
                )
                exempt = protocol_owner or bool(decorators & {"abstractmethod", "overload"})
                if not exempt and body and all(isinstance(item, ast.Pass) for item in body):
                    findings.append(f"{relative}:{node.lineno}: function body is only pass")
                if not exempt and body and all(
                    isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant) and item.value.value is Ellipsis
                    for item in body
                ):
                    findings.append(f"{relative}:{node.lineno}: function body is only ellipsis")
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                called = node.exc.func
                if isinstance(called, ast.Name) and called.id == "NotImplementedError":
                    findings.append(f"{relative}:{node.lineno}: NotImplementedError in production source")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                findings.append(f"{relative}:{node.lineno}: dynamic {node.func.id} is forbidden")
    detail = "\n".join(findings[:100]) if findings else "no production placeholders, empty function bodies, or dynamic eval/exec"
    return Check("source-policy", "failed" if findings else "passed", detail)


def run() -> dict[str, object]:
    checks = [
        _source_policy(),
        _run("python-compile", [sys.executable, "-m", "compileall", "-q", "src", "services", "workers", "tools"]),
        _run("schema-drift", [sys.executable, "-m", "tools.schema_codegen.generate", "--check", "--root", "."]),
        _run("compose-worker-drift", [sys.executable, "tools/sync_compose_workers.py", "--check"]),
        _run("traceability-map-drift", [sys.executable, "tools/build_traceability_map.py", "--check"]),
        _run("requirements-drift", [sys.executable, "tools/update_requirements.py", "--check"]),
        _run("third-party-lock-drift", [sys.executable, "tools/generate_third_party_lock.py", "--check"]),
        _run("infrastructure-policy", [sys.executable, "tools/validate_infrastructure.py", "--output", "build/reports/infrastructure-static-validation.json"]),
    ]
    return {
        "schema": "sip.static-checks/v1",
        "status": "passed" if all(item.status == "passed" for item in checks) else "failed",
        "checks": [asdict(item) for item in checks],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/reports/static-checks.json")
    args = parser.parse_args()
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
