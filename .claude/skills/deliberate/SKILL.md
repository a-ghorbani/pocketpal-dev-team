---
name: deliberate
description: Start a multi-agent technical discussion using propose-challenge-revise pattern. Two agents debate to find the best solution.
user-invocable: true
argument-hint: "[topic or question to deliberate]"
---

# Deliberate Workflow

You are orchestrating a structured technical debate between two agents for PocketPal AI development.

## Input
Topic: $ARGUMENTS

## The Deliberation Process

This is a **multi-agent debate**. You will orchestrate back-and-forth between:
- **pocketpal-proposer**: Proposes and defends solutions
- **pocketpal-challenger**: Challenges proposals to find weaknesses

```
┌─────────────────┐     proposal      ┌─────────────────┐
│    PROPOSER     │ ───────────────▶  │   CHALLENGER    │
│                 │                   │                 │
│  - Analyzes     │   challenges      │  - Finds flaws  │
│  - Proposes     │ ◀───────────────  │  - Questions    │
│  - Revises      │                   │  - Argues alts  │
│                 │   revised         │                 │
│                 │ ───────────────▶  │                 │
│                 │                   │                 │
│                 │   accept/reject   │                 │
│                 │ ◀───────────────  │                 │
└─────────────────┘                   └─────────────────┘
```

## Orchestration Steps

### Step 1: Gather Context (CRITICAL)

**You MUST gather source material before starting deliberation:**

1. If a story file, research doc, or issue is mentioned → READ IT FULLY
2. Extract the specific section relevant to the topic
3. This source material MUST be passed to both agents

```bash
# If story file mentioned
Read: [story file path]

# If issue mentioned
gh issue view [number] --repo pocketpal-ai/pocketpal-ai
```

**The source material is the ground truth. Both agents must work from it.**

### Step 2: Round 1 - Initial Proposal

Invoke the proposer with SOURCE MATERIAL:

```
Use pocketpal-proposer to propose a solution for: $ARGUMENTS

[If task context exists]
WORKTREE: [worktree path]
STORY: [story path]
TASK_ID: [task ID]

ROUND: 1

SOURCE MATERIAL (MUST READ AND QUOTE):
"""
[Paste the relevant section from story/research/issue here]
[This is the ground truth - proposer must align with this]
"""

INSTRUCTION:
1. First, GROUND yourself by quoting the key insight from the source material
2. State what problem we're actually solving
3. Then research the codebase and propose a solution
4. Ensure your proposal directly addresses the original insight
```

**Wait for proposer output before continuing.**

### Step 3: Round 1 - Challenge

Take the FULL proposal output and pass it to the challenger:

```
Use pocketpal-challenger to challenge this proposal:

TOPIC: $ARGUMENTS
ROUND: 1

PROPOSAL:
"""
[Paste the COMPLETE proposer output here]
"""

INSTRUCTION: Find weaknesses, challenge assumptions, argue for alternatives.
```

**Wait for challenger output before continuing.**

### Step 4: Round 2 - Proposer Responds

Take the FULL challenges and pass back to proposer:

```
Use pocketpal-proposer to respond to challenges:

TOPIC: $ARGUMENTS
ROUND: 2

ORIGINAL PROPOSAL:
"""
[The original proposal]
"""

CHALLENGES:
"""
[Paste the COMPLETE challenger output here]
"""

INSTRUCTION: Address each challenge. Revise proposal if warranted. Defend if challenges are invalid.
```

**Wait for proposer output before continuing.**

### Step 5: Round 2 - Challenger Evaluates

Take the revised proposal and pass to challenger:

```
Use pocketpal-challenger to evaluate the revised proposal:

TOPIC: $ARGUMENTS
ROUND: 2

REVISED PROPOSAL:
"""
[Paste the COMPLETE revised proposal here]
"""

PREVIOUS CHALLENGES:
"""
[The challenges from Round 1]
"""

INSTRUCTION: Evaluate if challenges were adequately addressed. Accept, request revision, or raise major concerns.
```

### Step 6: Check for Convergence

**If challenger says ACCEPT**: Deliberation complete. Proceed to synthesis.

**If challenger says NEEDS REVISION**:
- Run one more round (Steps 4-5)
- Maximum 3 total rounds to prevent infinite loops

**If challenger says MAJOR CONCERNS**:
- Escalate to human for decision
- Present both perspectives

### Step 7: Synthesis

After convergence (or max rounds), output the final summary:

```markdown
# Deliberation Complete: [Topic]

## Rounds: [N]
## Status: CONVERGED / MAX ROUNDS / ESCALATED

---

## Final Recommendation

[The final agreed-upon approach, or if not converged, the proposer's last position]

### Key Trade-offs Accepted
- [Trade-off 1]
- [Trade-off 2]

### Challenges That Shaped the Solution
1. [Challenge] → Led to [change]
2. [Challenge] → Addressed by [approach]

### Remaining Concerns
[Any unresolved issues, if applicable]

### Confidence: HIGH / MEDIUM / LOW

---

## Next Steps
1. [Concrete action]
2. [Another action]

---

## Full Deliberation Record

<details>
<summary>Round 1: Proposal</summary>

[Proposer's initial proposal]

</details>

<details>
<summary>Round 1: Challenges</summary>

[Challenger's challenges]

</details>

<details>
<summary>Round 2: Response & Revision</summary>

[Proposer's response]

</details>

<details>
<summary>Round 2: Evaluation</summary>

[Challenger's evaluation]

</details>
```

---

## Integration Points

### When Triggered by Planner

After deliberation completes, inform the planner:
```
Deliberation complete.
Recommendation: [summary]
Confidence: [level]

The planner should incorporate this into the story file.
```

### When Triggered by Implementer

After deliberation completes, inform the implementer:
```
Deliberation complete.
Recommendation: [summary]
Confidence: [level]

Proceed with implementation using this approach.
Update the story file with this deliberation outcome.
```

### When Triggered Manually

Output the full deliberation record. Offer:
- Save to decision log?
- Any follow-up actions?

---

## Example Orchestration

```
User: /deliberate "Should we use SQLite or MMKV for model metadata storage?"

You (orchestrator):
  → Call pocketpal-proposer with topic
  ← Receive proposal (recommends SQLite, lists alternatives)

  → Call pocketpal-challenger with proposal
  ← Receive challenges (questions SQLite complexity, argues for MMKV simplicity)

  → Call pocketpal-proposer with challenges
  ← Receive revised proposal (acknowledges MMKV simpler, but defends SQLite for query needs)

  → Call pocketpal-challenger to evaluate
  ← Receive evaluation: ACCEPT (SQLite justified for complex queries, MMKV too limited)

  → Output final synthesis
```

---

## Rules

1. **Always pass FULL outputs** - Don't summarize between agents, they need complete context
2. **Maximum 3 rounds** - Prevent infinite loops
3. **Don't inject your opinion** - Let the agents debate, you just orchestrate
4. **Preserve the record** - Include full deliberation in final output
5. **Clear convergence status** - Make it obvious if they agreed or not

## When NOT to Deliberate

If the topic is trivial, output:
```
This doesn't require deliberation: [reason]
Direct answer: [solution]
```

Examples of trivial topics:
- Typo fixes
- Single obvious approach
- Already established patterns
- Quick reversible changes
