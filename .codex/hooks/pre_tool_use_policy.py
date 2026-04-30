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


PROTECTED_SOURCE_SEGMENT = "repos/pocketpal-ai"
DEV_TEAM_ROOT = Path(__file__).resolve().parents[2]
SENSITIVE_PATTERNS = (
    re.compile(r"(^|/)\.env($|\.)"),
    re.compile(r"(^|/)GoogleService-Info\.plist$"),
    re.compile(r"(^|/)Env\.xcconfig$"),
    re.compile(r"(^|/)google-services\.json$"),
    re.compile(r"(^|/)pocketpal-release-key\.keystore$"),
    re.compile(r"(^|/)secrets(/|$)"),
)

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
    "tee",
    "touch",
    "truncate",
    "vim",
    "vi",
}
BLOCKED_COMMAND_PATTERNS = (
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

    resolved = path.resolve(strict=False)

    try:
        return resolved.relative_to(DEV_TEAM_ROOT).as_posix()
    except Exception:
        return raw.replace(os.sep, "/")


def normalize_relative_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def is_protected_source_path(path: str) -> bool:
    normalized = normalize_relative_path(path)
    return normalized == PROTECTED_SOURCE_SEGMENT or normalized.startswith(
        PROTECTED_SOURCE_SEGMENT + "/"
    )


def is_sensitive_path(path: str) -> bool:
    normalized = normalize_relative_path(path)
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


def explicit_tool_paths(tool_input: Any) -> list[tuple[str, str]]:
    if not isinstance(tool_input, dict):
        return []

    paths: list[tuple[str, str]] = []
    for key in ("file_path", "path"):
        value = tool_input.get(key)
        if isinstance(value, str):
            paths.append((value, "explicit"))

    command = tool_input.get("command")
    if isinstance(command, str):
        paths.extend((path, "patch") for path in patch_paths(command))

    return paths


def shell_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def command_mentions_sensitive_path(tokens: list[str], cwd: str) -> bool:
    return any(
        is_sensitive_path(token) or is_sensitive_path(normalize_path(token, cwd))
        for token in tokens
    )


def command_mentions_protected_source_path(tokens: list[str], cwd: str) -> bool:
    return any(
        is_protected_source_path(token)
        or is_protected_source_path(normalize_path(token, cwd))
        for token in tokens
    )


def sed_is_mutating(tokens: list[str]) -> bool:
    return any(token == "-i" or token.startswith("-i") for token in tokens[1:])


def command_uses_sensitive_redirection(command: str) -> bool:
    return bool(re.search(r"(^|\s)(>|>>|<)\s*(\.?/)?(\.env($|\.)|.*?/\.env($|\.)|.*?/secrets(/|$))", command))


def command_uses_protected_source_output_redirection(command: str) -> bool:
    return bool(
        re.search(
            rf"(^|\s)(>|>>)\s*(\.?/)?{re.escape(PROTECTED_SOURCE_SEGMENT)}(/|$)",
            command,
        )
    )


def should_block_shell(command: str, cwd: str) -> str | None:
    for pattern, reason in BLOCKED_COMMAND_PATTERNS:
        if pattern.search(command):
            return reason

    tokens = shell_tokens(command)
    if not tokens:
        return None

    executable = Path(tokens[0]).name
    mentions_sensitive = command_mentions_sensitive_path(tokens, cwd)
    mentions_protected_source = command_mentions_protected_source_path(tokens, cwd)

    if mentions_sensitive:
        return "BLOCKED: shell command may read or modify a sensitive path. Do not read .env files or secrets."

    if mentions_protected_source and (
        executable in SHELL_WRITE_COMMANDS
        or (executable == "sed" and sed_is_mutating(tokens))
    ):
        return "BLOCKED: shell command may modify a protected path. Work in worktrees/ and do not edit repos/pocketpal-ai, .env files, or secrets."

    if command_uses_sensitive_redirection(command):
        return "BLOCKED: shell redirection references .env or secrets paths."

    if command_uses_protected_source_output_redirection(command):
        return "BLOCKED: shell redirection may modify repos/pocketpal-ai. Create/use a worktree instead."

    if PROTECTED_SOURCE_SEGMENT in command and re.search(r"\b(git\s+-C|git)\b", command):
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

    for raw_path, path_kind in explicit_tool_paths(tool_input):
        normalized = normalize_path(raw_path, cwd)
        if is_sensitive_path(normalized):
            deny(
                "BLOCKED: Codex cannot read or modify sensitive paths: .env files or secrets."
            )
        if path_kind == "patch" and is_protected_source_path(normalized):
            deny(
                "BLOCKED: Codex cannot modify repos/pocketpal-ai directly. Create/use a worktree instead."
            )

    if tool_name == "Bash" and isinstance(tool_input, dict):
        command = tool_input.get("command")
        if isinstance(command, str):
            reason = should_block_shell(command, cwd)
            if reason:
                deny(reason)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
