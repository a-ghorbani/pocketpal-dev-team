/**
 * PocketPal guards for pi.
 *
 * Runs the same `tools/guard-*.sh` scripts that Claude Code and Codex call as
 * hooks, and opencode calls from `.opencode/plugins/guards.ts`. The scripts read
 * Claude-shaped hook JSON on stdin and exit 2 to block.
 *
 * pi blocks the tool when a `tool_call` handler throws, so a broken shim fails
 * closed here.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"

import { afterToolCall, checkToolCall } from "./guards.ts"

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event: any, ctx: any) => {
    const reason = checkToolCall(event.toolName, event.input ?? {}, ctx.cwd)
    return reason ? { block: true, reason } : undefined
  })

  pi.on("tool_result", async (event: any, ctx: any) => {
    afterToolCall(event.toolName, event.input ?? {}, ctx.cwd)
    return undefined
  })
}
