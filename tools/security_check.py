#!/usr/bin/env python3
"""Run deterministic security controls without claiming unavailable external scans."""
from __future__ import annotations

import argparse
import ast
import base64
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (
    ROOT / "src",
    ROOT / "services",
    ROOT / "workers",
    ROOT / "tools",
    ROOT / "infrastructure",
    ROOT / "apps",
    ROOT / "schemas",
    ROOT / ".github",
)
TEXT_SUFFIXES = {
    ".py", ".sh", ".yaml", ".yml", ".json", ".toml", ".tf", ".md", ".ts", ".tsx", ".js", ".mjs", ".swift", ".proto"
}
EXCLUDED_PARTS = {".git", ".build", ".next", "node_modules", "__pycache__", "spec", "build", "runtime"}


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    path: str
    line: int | None
    message: str


@dataclass(frozen=True)
class Control:
    name: str
    status: str
    detail: str
    required: bool = True


def _files() -> Iterable[Path]:
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts):
                continue
            if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"Dockerfile", "Makefile", "justfile", "CODEOWNERS"}:
                yield path


def _secret_findings() -> list[Finding]:
    patterns = [
        ("PRIVATE_KEY_MATERIAL", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private key material is committed"),
        ("AWS_ACCESS_KEY", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), "AWS access-key-shaped value is committed"),
        ("GITHUB_TOKEN", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b"), "GitHub token-shaped value is committed"),
        ("SLACK_TOKEN", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"), "Slack token-shaped value is committed"),
        ("STRIPE_SECRET", re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{20,}\b"), "Stripe secret-shaped value is committed"),
    ]
    findings: list[Finding] = []
    for path in _files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = str(path.relative_to(ROOT))
        for line_number, line in enumerate(text.splitlines(), start=1):
            for code, pattern, message in patterns:
                if pattern.search(line):
                    findings.append(Finding(code, "error", relative, line_number, message))
    return findings


def _python_findings() -> list[Finding]:
    findings: list[Finding] = []
    for path in _files():
        if path.suffix != ".py":
            continue
        relative = str(path.relative_to(ROOT))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except SyntaxError as exc:
            findings.append(Finding("PYTHON_SYNTAX", "error", relative, exc.lineno, exc.msg))
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                owner = node.func.value.id if isinstance(node.func.value, ast.Name) else ""
                name = f"{owner}.{node.func.attr}" if owner else node.func.attr
            keywords = {item.arg: item.value for item in node.keywords if item.arg}
            if name in {"eval", "exec"}:
                findings.append(Finding("DYNAMIC_CODE_EXECUTION", "error", relative, node.lineno, f"{name} is prohibited"))
            if name in {"pickle.load", "pickle.loads", "marshal.load", "marshal.loads"}:
                findings.append(Finding("UNSAFE_DESERIALIZATION", "error", relative, node.lineno, f"{name} is prohibited in production source"))
            if name in {"subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_call", "subprocess.check_output"}:
                value = keywords.get("shell")
                if isinstance(value, ast.Constant) and value.value is True:
                    findings.append(Finding("SHELL_EXECUTION", "error", relative, node.lineno, "subprocess shell=True is prohibited"))
            if name in {"requests.get", "requests.post", "requests.put", "requests.delete", "requests.request"}:
                value = keywords.get("verify")
                if isinstance(value, ast.Constant) and value.value is False:
                    findings.append(Finding("TLS_VERIFICATION_DISABLED", "error", relative, node.lineno, "TLS verification cannot be disabled"))
            if name in {"yaml.load", "load"}:
                owner = node.func.value.id if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) else ""
                if owner == "yaml" and "Loader" not in keywords:
                    findings.append(Finding("UNSAFE_YAML_LOAD", "error", relative, node.lineno, "yaml.load requires an explicit safe loader"))
    return findings


def _permission_findings() -> list[Finding]:
    findings: list[Finding] = []
    secret_root = ROOT / "infrastructure" / "compose" / "secrets"
    if not secret_root.exists():
        return findings
    for path in sorted(secret_root.iterdir()):
        if not path.is_file() or path.name in {".gitignore", "README.md"}:
            continue
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            findings.append(Finding("SECRET_FILE_PERMISSIONS", "error", str(path.relative_to(ROOT)), None, f"secret file mode {mode:o} must be 600 or stricter"))
    return findings


def _runtime_controls() -> list[Control]:
    snippet = """
import base64, os
from sip.config import Settings
from sip.security import SignedTokenCodec

for name in list(os.environ):
    if name.startswith('SIP_'):
        os.environ.pop(name)
os.environ['SIP_ENV'] = 'production'
try:
    Settings.from_env()
except ValueError:
    pass
else:
    raise SystemExit('production accepted missing cryptographic keys')

key = b'k' * 32
codec = SignedTokenCodec(key)
token = codec.encode({'token_type':'principal','principal':{'subject_id':'subject','tenant_id':'tenant','project_ids':[],'roles':[],'purposes':[],'audience':'private','attributes':{}}}, ttl_seconds=60)
body, signature = token.split('.', 1)
mutated = body[:-1] + ('A' if body[-1] != 'A' else 'B') + '.' + signature
try:
    codec.decode(mutated)
except Exception:
    pass
else:
    raise SystemExit('tampered signed token was accepted')
"""
    completed = subprocess.run(
        [sys.executable, "-c", snippet],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": f"{ROOT / 'src'}:{ROOT}"},
        capture_output=True,
        text=True,
        check=False,
    )
    detail = ((completed.stdout or "") + (completed.stderr or "")).strip()
    return [Control("fail-closed-runtime-security", "passed_complete" if completed.returncode == 0 else "failed", detail or "production key and token-tamper checks passed")]


def _external_controls(*, release: bool) -> list[Control]:
    commands = {
        "dependency-vulnerability-scan": ("pip-audit", ["pip-audit", "--strict", "--format", "json"]),
        "secret-history-scan": ("gitleaks", ["gitleaks", "detect", "--no-banner", "--source", str(ROOT)]),
        "container-vulnerability-scan": ("trivy", ["trivy", "fs", "--quiet", "--severity", "HIGH,CRITICAL", "--exit-code", "1", str(ROOT)]),
    }
    controls: list[Control] = []
    for name, (tool, command) in commands.items():
        if shutil.which(tool) is None:
            controls.append(Control(name, "blocked", f"{tool} is not installed", required=release))
            continue
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False, timeout=300)
        detail = ((completed.stdout or "") + (completed.stderr or ""))[-8000:]
        controls.append(Control(name, "passed_complete" if completed.returncode == 0 else "failed", detail, required=True))
    return controls


def run(*, release: bool = False) -> dict[str, object]:
    started = time.perf_counter()
    findings = [*_secret_findings(), *_python_findings(), *_permission_findings()]
    controls = [*_runtime_controls(), *_external_controls(release=release)]
    errors = [item for item in findings if item.severity == "error"]
    failures = [item for item in controls if item.status == "failed"]
    blocked = [item for item in controls if item.status == "blocked"]
    status = "failed" if errors or failures else ("blocked" if release and blocked else ("passed_with_external_gaps" if blocked else "passed_complete"))
    return {
        "schema": "sip.security-report/v1",
        "mode": "release" if release else "development",
        "status": status,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "scanned_files": sum(1 for _ in _files()),
        "findings": [asdict(item) for item in findings],
        "controls": [asdict(item) for item in controls],
        "external_validation_required": [item.name for item in controls if item.status == "blocked"],
        "limitations": [
            "Static scanning does not replace dependency-database, container-image, penetration, or independent security review.",
            "External controls remain explicit and fail the release profile when their approved tools are unavailable.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "build/reports/security-report.json")
    args = parser.parse_args()
    report = run(release=args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] in {"passed_complete", "passed_with_external_gaps"} else 1)


if __name__ == "__main__":
    main()
