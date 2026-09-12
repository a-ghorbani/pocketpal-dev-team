// Runs the repo's shell guards (the same ones Claude Code and Codex call as
// PreToolUse/PostToolUse hooks) for opencode tool calls. The guards read
// Claude-shaped hook JSON on stdin and exit 2 to block.
import { spawnSync } from "node:child_process"
import { homedir } from "node:os"
import { isAbsolute, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const TOOLS = fileURLToPath(new URL("../../tools/", import.meta.url))

const BEFORE: Record<string, string[]> = {
  Bash: ["block-commit-to-main.sh", "guard-worktree-ops.sh", "guard-submodule-git.sh", "guard-secrets-read.sh", "guard-push-to-main.sh"],
  Edit: ["guard-submodule-edit.sh"],
  Write: ["guard-submodule-edit.sh"],
  Read: ["guard-secrets-read.sh"],
  Grep: ["guard-secrets-read.sh"],
}
const AFTER: Record<string, string[]> = {
  Bash: ["post-worktree-copy-env.sh"],
}

type HookCall = { tool_name: string; tool_input: Record<string, unknown> }

function absolutePath(raw: unknown, cwd: string): string | undefined {
  if (typeof raw !== "string" || raw === "") return undefined
  const expanded = raw.startsWith("~") ? resolve(homedir(), raw.slice(1).replace(/^[/\\]/, "")) : raw
  return isAbsolute(expanded) ? expanded : resolve(cwd, expanded)
}

function patchPaths(patch: string): string[] {
  const header = /^\*\*\* (?:Add|Update|Delete) File: (.+)$|^\*\*\* Move to: (.+)$/gm
  return [...patch.matchAll(header)].map((m) => (m[1] ?? m[2]).trim())
}

function toHookCalls(tool: string, args: Record<string, any>, cwd: string): HookCall[] {
  switch (tool) {
    case "bash":
      return [{ tool_name: "Bash", tool_input: { command: args.command } }]
    case "edit":
    case "multiedit":
      return [{ tool_name: "Edit", tool_input: { file_path: absolutePath(args.filePath, cwd) } }]
    case "write":
      return [{ tool_name: "Write", tool_input: { file_path: absolutePath(args.filePath, cwd) } }]
    case "patch":
    case "apply_patch":
      return patchPaths(String(args.patchText ?? args.patch ?? "")).map((path) => ({
        tool_name: "Edit",
        tool_input: { file_path: resolve(cwd, path) },
      }))
    case "read":
      return [{ tool_name: "Read", tool_input: { file_path: absolutePath(args.filePath, cwd) } }]
    case "grep":
      return [{ tool_name: "Grep", tool_input: { path: args.path, pattern: args.pattern, glob: args.include } }]
    default:
      return []
  }
}

function runGuards(table: Record<string, string[]>, call: HookCall, cwd: string): string | undefined {
  const payload = JSON.stringify({ ...call, cwd })
  for (const script of table[call.tool_name] ?? []) {
    const result = spawnSync(TOOLS + script, { cwd, input: payload, encoding: "utf8", timeout: 30_000 })
    // Fail closed: a guard that times out or cannot run has not cleared the call.
    if (result.error || result.signal) return `${script}: ${result.error?.message ?? result.signal}`
    if (result.status === 2) return (result.stderr || result.stdout || `${script} blocked the call`).trim()
  }
  return undefined
}

export const PocketPalGuards = async ({ directory }: { directory: string }) => ({
  "tool.execute.before": async (input: { tool: string }, output: { args: Record<string, any> }) => {
    const cwd = output.args.workdir ?? directory
    for (const call of toHookCalls(input.tool, output.args, cwd)) {
      const reason = runGuards(BEFORE, call, cwd)
      if (reason) throw new Error(reason)
    }
  },
  "tool.execute.after": async (input: { tool: string; args?: Record<string, any> }) => {
    if (input.tool !== "bash" || !input.args) return
    runGuards(AFTER, { tool_name: "Bash", tool_input: { command: input.args.command } }, input.args.workdir ?? directory)
  },
})
