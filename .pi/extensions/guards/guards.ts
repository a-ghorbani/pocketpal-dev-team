// Maps pi tool calls onto the repo's shell guards. No pi imports here, so this
// file can be exercised directly with node --experimental-strip-types.
import { spawnSync } from "node:child_process"
import { homedir } from "node:os"
import { isAbsolute, resolve } from "node:path"
import { fileURLToPath } from "node:url"

export const TOOLS = fileURLToPath(new URL("../../../tools/", import.meta.url))
const TIMEOUT_MS = 30_000

export const BEFORE: Record<string, string[]> = {
  Bash: [
    "block-commit-to-main.sh",
    "guard-worktree-ops.sh",
    "guard-submodule-git.sh",
    "guard-secrets-read.sh",
    "guard-push-to-main.sh",
  ],
  Edit: ["guard-submodule-edit.sh"],
  Write: ["guard-submodule-edit.sh"],
  Read: ["guard-secrets-read.sh"],
  Grep: ["guard-secrets-read.sh"],
}
export const AFTER: Record<string, string[]> = {
  Bash: ["post-worktree-copy-env.sh"],
}

export type HookCall = { tool_name: string; tool_input: Record<string, unknown> }

// A guard checking a path must see the same path the tool will act on.
export function absolutePath(raw: unknown, cwd: string): string | undefined {
  if (typeof raw !== "string" || raw === "") return undefined
  const expanded = raw.startsWith("~") ? resolve(homedir(), raw.slice(1).replace(/^[/\\]/, "")) : raw
  return isAbsolute(expanded) ? expanded : resolve(cwd, expanded)
}

export function toHookCalls(tool: string, input: Record<string, any>, cwd: string): HookCall[] {
  switch (tool) {
    case "bash":
    case "powershell":
      return [{ tool_name: "Bash", tool_input: { command: input.command } }]
    case "edit":
      return [{ tool_name: "Edit", tool_input: { file_path: absolutePath(input.path, cwd) } }]
    case "write":
      return [{ tool_name: "Write", tool_input: { file_path: absolutePath(input.path, cwd) } }]
    case "read":
      return [{ tool_name: "Read", tool_input: { file_path: absolutePath(input.path, cwd) } }]
    case "grep":
    case "find":
    case "ls":
      return [
        {
          tool_name: "Grep",
          tool_input: {
            path: absolutePath(input.path, cwd),
            pattern: input.pattern,
            glob: input.glob ?? input.include,
          },
        },
      ]
    default:
      return []
  }
}

/** Returns the block reason, or undefined when every guard allows the call. */
export function runGuards(table: Record<string, string[]>, call: HookCall, cwd: string): string | undefined {
  const payload = JSON.stringify({ ...call, cwd })
  for (const script of table[call.tool_name] ?? []) {
    const result = spawnSync(TOOLS + script, { cwd, input: payload, encoding: "utf8", timeout: TIMEOUT_MS })
    // Fail closed: a guard that times out or cannot run has not cleared the call.
    if (result.error || result.signal) return `${script}: ${result.error?.message ?? result.signal}`
    if (result.status === 2) return (result.stderr || result.stdout || `${script} blocked the call`).trim()
  }
  return undefined
}

export function checkToolCall(tool: string, input: Record<string, any>, cwd: string): string | undefined {
  for (const call of toHookCalls(tool, input, cwd)) {
    const reason = runGuards(BEFORE, call, cwd)
    if (reason) return reason
  }
  return undefined
}

export function afterToolCall(tool: string, input: Record<string, any>, cwd: string): void {
  for (const call of toHookCalls(tool, input, cwd)) runGuards(AFTER, call, cwd)
}
