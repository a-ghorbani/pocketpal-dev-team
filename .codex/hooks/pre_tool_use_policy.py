#!/usr/bin/env python3
"""Codex PreToolUse guardrails for the PocketPal dev-team repo."""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any


PROTECTED_SEGMENT = "repos/pocketpal-ai"
SENSITIVE_PATTERNS = (
    re.compile(r"(^|/)\.env($|\.)"),
    re.compile(r"(^|/)secrets(/|$)"),
)

SHELL_READ_COMMANDS = {
    "awk",
    "bat",
    "cat",
    "grep",
    "head",
    "less",
    "more",
    "nl",
    "rg",
    "sed",
    "tail",
}
SHELL_WRITE_COMMANDS = {
    "chmod",
    "chown",
    "cp",
    "install",
    "mkdir",
    "mv",
    "perl",
    "python",
    "python3",
    "ruby",
    "sed",
    "tee",
    "touch",
    "truncate",
    "vim",
    "vi",
}
BLOCKED_COMMAND_PATTERNS = (
    (
        re.compile(r"(^|[;&|]\s*)curl\b"),
        "BLOCKED: direct curl usage is blocked for this repo.",
    ),
    (
        re.compile(r"(^|[;&|]\s*)wget\b"),
        "BLOCKED: direct wget usage is blocked for this repo.",
    ),
    (
        re.compile(r"(^|[;&|]\s*)rm\s+-(?:[^\s-]*r[^\s-]*f|[^\s-]*f[^\s-]*r)\b"),
        "BLOCKED: destructive recursive deletion is blocked. Use ./tools/remove-worktree.sh for explicit worktree cleanup.",
    ),
    (
        re.compile(r"(^|[;&|]\s*)git\s+push\s+(-f|--force)\b"),
        "BLOCKED: force pushes are blocked.",
    ),
    (
        re.compile(r"(^|[;&|]\s*)git\s+push\s+origin\s+(main|master)\b"),
        "BLOCKED: direct pushes to origin main/master are blocked.",
    ),
)


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def normalize_path(raw: str, cwd: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""

    path = Path(raw)
    if not path.is_absolute():
        path = Path(cwd) / path

    try:
        repo = Path(cwd).resolve()
        resolved = path.resolve(strict=False)
        return resolved.relative_to(repo).as_posix()
    except Exception:
        return raw.replace(os.sep, "/")


def is_sensitive_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized == PROTECTED_SEGMENT or normalized.startswith(PROTECTED_SEGMENT + "/"):
        return True
    return any(pattern.search(normalized) for pattern in SENSITIVE_PATTERNS)


def patch_paths(patch_text: str) -> list[str]:
    paths: list[str] = []
    markers = (
        "*** Add File: ",
        "*** Update File: ",
        "*** Delete File: ",
        "*** Move to: ",
    )
    for line in patch_text.splitlines():
        for marker in markers:
            if line.startswith(marker):
                paths.append(line.removeprefix(marker).strip())
    return paths


def explicit_tool_paths(tool_input: Any) -> list[str]:
    if not isinstance(tool_input, dict):
        return []

    paths: list[str] = []
    for key in ("file_path", "path"):
        value = tool_input.get(key)
        if isinstance(value, str):
            paths.append(value)

    command = tool_input.get("command")
    if isinstance(command, str):
        paths.extend(patch_paths(command))

    return paths


def shell_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def command_mentions_protected_path(tokens: list[str]) -> bool:
    return any(is_sensitive_path(token) for token in tokens)


def command_uses_sensitive_redirection(command: str) -> bool:
    return bool(re.search(r"(^|\s)(>|>>|<)\s*(\.?/)?(\.env($|\.)|.*?/\.env($|\.)|.*?/secrets(/|$))", command))


def should_block_shell(command: str) -> str | None:
    for pattern, reason in BLOCKED_COMMAND_PATTERNS:
        if pattern.search(command):
            return reason

    tokens = shell_tokens(command)
    if not tokens:
        return None

    executable = Path(tokens[0]).name
    mentioned = command_mentions_protected_path(tokens)

    if mentioned and executable in SHELL_WRITE_COMMANDS:
        return "BLOCKED: shell command may modify a protected path. Work in worktrees/ and do not edit repos/pocketpal-ai, .env files, or secrets."

    if mentioned and executable in SHELL_READ_COMMANDS:
        return "BLOCKED: shell command may read a protected path. Do not read .env files or secrets, and only inspect repos/pocketpal-ai through non-mutating source reads when needed."

    if command_uses_sensitive_redirection(command):
        return "BLOCKED: shell redirection references .env or secrets paths."

    if PROTECTED_SEGMENT in command and re.search(r"\b(git\s+-C|git)\b", command):
        mutating_git = re.search(
            r"\bgit\b(?:\s+-C\s+\S+)?\s+(add|am|apply|branch|checkout|clean|commit|merge|mv|pull|push|rebase|reset|restore|rm|switch|worktree)\b",
            command,
        )
        if mutating_git:
            return "BLOCKED: mutating git command targets repos/pocketpal-ai. Create/use a worktree instead."

    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    cwd = event.get("cwd") or os.getcwd()
    tool_name = event.get("tool_name") or ""
    tool_input = event.get("tool_input") or {}

    for raw_path in explicit_tool_paths(tool_input):
        normalized = normalize_path(raw_path, cwd)
        if is_sensitive_path(normalized):
            deny(
                "BLOCKED: Codex cannot read or modify protected paths: repos/pocketpal-ai, .env files, or secrets."
            )

    if tool_name == "Bash" and isinstance(tool_input, dict):
        command = tool_input.get("command")
        if isinstance(command, str):
            reason = should_block_shell(command)
            if reason:
                deny(reason)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
