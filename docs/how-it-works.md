# How Kahnban Works

This page is one level down from the [board overview in the README](../README.md#how-it-works). It goes stage by stage through what happens in each column and what the gate out of it checks, then covers the deeper flows: the factory loop, the merge queue, the architecture and the learnings loop.

- [Stage by stage](#stage-by-stage): [backlog and refining](#backlog-and-refining), [ready](#ready), [in progress](#in-progress), [verifying](#verifying), [done](#done)
- [Deeper flows](#deeper-flows): [the factory loop](#the-factory-loop), [the merge queue](#the-merge-queue), [architecture](#architecture), [the learnings loop](#the-learnings-loop)

## Stage by stage

Every gate is one function in `core`, and the CLI, the MCP server and `kahnban run` all call that same function. When a check fails, the ticket stays where it is and the command says why. The diagrams show the checks; the [gate tables in the README](../README.md#what-verify-refuses) have the exact refusal rules.

### Backlog and refining

**Who:** a human, or the spec-analyst worker under `kahnban run`.

`capture`, `new` and `ingest` create tickets in `0-backlog`. Refining turns a ticket into a contract: acceptance criteria that each name the test that proves them, a blast radius listing the files the change may touch, and the feature and regression commands under `## Validation`. `ingest --ready` moves fresh tickets to `1-refining` and tries the gate straight away; `ready` also accepts a ticket that is still in `0-backlog`.

The ready gate checks everything and lists every problem at once:

```mermaid
---
config:
  flowchart:
    useMaxWidth: false
    rankSpacing: 15
    wrappingWidth: 400
---
flowchart TD
  from["0-backlog or<br/>1-refining"] --> gate
  subgraph gate["kahnban ready"]
    direction TB
    r1["acceptance criteria are checkboxes"]
    r2["blast radius lists files, not folders,<br/>at most max_blast_radius_files"]
    r3["not blocked, every dependency done"]
    r4["commands match allowed_commands<br/>(when set)"]
    r5["require_proof: each criterion names a test,<br/>the blast radius includes a test file"]
    r6["require_spec: the spec is approved<br/>and covers: names its requirements"]
    r1 ~~~ r2 ~~~ r3 ~~~ r4 ~~~ r5 ~~~ r6
  end
  gate --> to["2-ready<br/>contract frozen"]
  gate -.->|any check fails| stay["refused,<br/>every problem listed"]
```

Passing freezes the contract: a hash of the acceptance criteria, blast radius and validation sections, which `verify` checks later. In a repo with `.agents/` (from `init --agentic`) it also writes a handoff baton and fires the `post-ready` hook.

### Ready

**Who:** nobody yet. The ticket waits for a coder.

A ticket stays in `2-ready` until someone claims it, and it can only be claimed while no in-progress ticket touches the same files. That rule is what keeps parallel agents out of each other's way. Claim stops at the first check that fails:

```mermaid
---
config:
  flowchart:
    useMaxWidth: false
    rankSpacing: 15
    wrappingWidth: 400
---
flowchart TD
  from["2-ready"] --> gate
  subgraph gate["kahnban claim"]
    direction TB
    c1["ticket is in 2-ready"]
    c2["every dependency is done"]
    c3["under the WIP limit<br/>(a warning unless --strict-wip)"]
    c4["blast radius overlaps no<br/>3-in-progress ticket"]
    c1 ~~~ c2 ~~~ c3 ~~~ c4
  end
  gate --> to["3-in-progress"]
  gate -.->|any check fails| stay["refused,<br/>stays in 2-ready"]
```

Passing records a lease for the owner. With `--worktree` (which `kahnban run` always uses) it creates the worktree `.worktrees/<ID>` on branch `ticket/<ID>` and writes `.agents/HANDOFF.json` into it. In a repo with `.agents/` it also fires the `post-claim` hook.

### In progress

**Who:** the coder.

The coder works test-first inside the worktree and commits on `ticket/<ID>`. Board files never change on that branch. Verify tests the committed tip and runs its checks in order, stopping at the first failure:

```mermaid
---
config:
  flowchart:
    useMaxWidth: false
    rankSpacing: 15
    wrappingWidth: 400
---
flowchart TD
  from["3-in-progress"] --> gate
  subgraph gate["kahnban verify, in order"]
    direction TB
    v1["contract unchanged since ready"]
    v2["diff stays inside the blast radius"]
    v3["worktree clean, at the branch tip"]
    v4["feature tests pass"]
    v5["each criterion's test passes"]
    v6["regression tests pass"]
    v7["require_proof: the feature tests fail<br/>with the changed source reverted"]
    v1 --> v2 --> v3 --> v4 --> v5 --> v6 --> v7
  end
  gate --> to["4-verifying<br/>passing boxes ticked"]
  gate -.->|first failure| stay["stays in 3-in-progress,<br/>failure in the Log"]
```

A pass ticks the box of every criterion whose test passed, records the verified tip, clears any earlier approval and fires the `post-verify` hook. A failure is committed to the ticket's `## Log` with the output, so the next attempt can see what broke.

### Verifying

**Who:** the qa-reviewer, then the integrator.

The ticket stays in `4-verifying` through two gates. Only its records change: first an approval, then an integration commit.

```mermaid
---
config:
  flowchart:
    useMaxWidth: false
    rankSpacing: 15
    wrappingWidth: 400
---
flowchart TD
  verified["4-verifying<br/>verified"] --> approve
  subgraph approve["kahnban approve"]
    direction LR
    a1["reviewer is not the owner"] ~~~ a2["branch unchanged<br/>since verify"]
  end
  approve --> approved["4-verifying<br/>approved"] --> merge
  subgraph merge["kahnban merge"]
    direction LR
    m1["merges cleanly<br/>onto main"] ~~~ m2["tests pass on<br/>the merged result"]
  end
  merge --> integrated["4-verifying<br/>integrated"]
  verified -.->|kahnban reject| back["3-in-progress"]
```

A reviewer who finds a problem runs `reject` instead of `approve`. That sends the ticket back to `3-in-progress`, unticks every box, clears the verify, approval and integration records, and puts the reasons in the Log for the coder. A refused merge lands nothing; under `kahnban run` it is rejected back automatically. [The merge queue](#the-merge-queue) shows what `merge` does in git.

### Done

**Who:** the integrator (the runner, under `kahnban run`).

`done` collects every problem before it refuses:

```mermaid
---
config:
  flowchart:
    useMaxWidth: false
    rankSpacing: 15
    wrappingWidth: 400
---
flowchart TD
  from["4-verifying<br/>integrated"] --> gate
  subgraph gate["kahnban done"]
    direction TB
    d1["every acceptance box is ticked"]
    d2["approved by someone other than<br/>the owner, at the current tip"]
    d3["the merge commit is on main<br/>and contains the tip"]
    d1 ~~~ d2 ~~~ d3
  end
  gate --> to["5-done"]
  to -->|kahnban cleanup| gone["worktree and<br/>branch removed"]
  gate -.->|any check fails| stay["refused,<br/>stays in 4-verifying"]
```

The approval and merge checks apply under `require_review` and `require_integration`, which `kahnban init` turns on. Passing fires the `post-done` hook, which prompts a learnings reflection. `cleanup` then removes the worktree and the local ticket branch.

## Deeper flows

### The factory loop

`kahnban run` drives the board without a human in the loop. Each step it asks the dispatcher for the most urgent action, runs the gates itself, and starts an agent worker only for judgment work. When the action moves the board, the loop asks again:

```mermaid
---
config:
  flowchart:
    useMaxWidth: false
---
flowchart TD
  pick["dispatcher picks<br/>the next action"]
  pick -->|nothing to do| idle(["stop: report<br/>parked tickets"])
  pick -->|an action| act["runner runs the gates,<br/>and a worker if needed"]
  act -->|"no progress after<br/>max_attempts"| esc(["escalate<br/>to a human"])
  act -->|progress| commit["board changes<br/>(one commit)"]
  commit -->|next step| pick
```

The dispatcher takes the first row that matches, so finishing work comes before starting new work:

| # | When the board has | The runner | Worker |
| :--- | :--- | :--- | :--- |
| 1 | an approved ticket in `4-verifying` | runs merge, done and cleanup; a refused merge is rejected back | — |
| 1 | an unapproved ticket in `4-verifying` | starts a review, which approves or rejects | qa-reviewer |
| 2 | a `3-in-progress` ticket with no live lease | resumes it (or revises it after a rejection), then runs verify | coder |
| 3 | a learning seen twice or marked critical (once per run) | starts a curator, which files a fix ticket and promotes the learning | curator |
| 4 | a `2-ready` ticket whose blast radius is free | claims it into a worktree, then implements and verifies it | coder |
| 5 | a ticket in `0-backlog` or `1-refining` | starts refinement, then runs the ready gate | spec-analyst |

Escalating sets `blocked_on: human: <reason>` and fires the `on-escalate` hook; the dispatcher skips the ticket until someone runs `kahnban unblock`. Workers run with `KAHNBAN_ROLE` set, so [`kahnban guard`](../README.md#running-the-factory-kahnban-run) and the CLI refuse anything outside their role.

### The merge queue

The board and the code meet only here. `merge` merges the ticket branch onto the default branch in a scratch worktree, runs the feature and regression tests on that result, and fast-forwards the default branch only if they pass. It holds the board lock while the tests run, so each merge is tested against everything merged before it:

```mermaid
gitGraph
  commit id: "ready KB-001"
  commit id: "claim KB-001"
  branch ticket/KB-001
  checkout ticket/KB-001
  commit id: "failing test"
  commit id: "make it pass"
  checkout main
  commit id: "verify KB-001"
  commit id: "approve KB-001"
  merge ticket/KB-001 id: "merge, tests green"
  commit id: "integrated KB-001"
  commit id: "done KB-001"
```

### Architecture

Every way in reaches the same core, and the core is the only code that moves a ticket:

```mermaid
---
config:
  flowchart:
    useMaxWidth: false
---
flowchart TD
  ways["Ways in<br/>capture · new · ingest a plan or spec · spec approve"]
  clients["Clients<br/>kahnban CLI (including kahnban run) · MCP server"]
  core["core<br/>every gate and the one transition() writer"]
  ways --> clients --> core
  core -->|"git mv + commit"| board[("board<br/>plans/tickets/, on the default branch")]
  core -->|"claim · merge · cleanup"| code[("code<br/>.worktrees/ID, on ticket/ID")]
```

Agent workers go through the same clients as a human, with `KAHNBAN_ROLE` set. `spec approve` is blocked for every factory role: only a human approves intent.

### The learnings loop

Mistakes and friction are captured into `./learnings/`, where repeats cluster into one record instead of piling up. A record that recurs gets a structural fix:

```mermaid
flowchart TD
  cap["learnings capture"] --> match{"same pattern<br/>or location?"}
  match -->|no| new["new LRN record"]
  match -->|yes| bump["occurrences + 1<br/>keeps the higher severity"]
  new --> due{"occurrences ≥ 2<br/>or critical?"}
  bump --> due
  due -->|yes| cur("curator: a fix ticket<br/>on the board")
  cur --> promote["learnings promote<br/>--level 1-4 --artifact"]
  promote --> arch[("learnings/archive/")]
```

The four promotion levels, from architecture down to documentation, are described in the [README](../README.md#continuous-learning-subsystem-learnings).
