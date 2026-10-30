# ADR-0002: Localize every shipped skill under a `kb-` prefix

**Date:** 2026-10-29
**Status:** Accepted
**Deciders:** Tim Niles
**Consulted Skills:** `/grill-with-docs`

---

## 1. Context & Problem Statement
Kahnban ships skills copied from pstack (cursor/plugins, MIT) and from mattpocock/skills (MIT) under their upstream names. The copies have drifted from upstream. Some reference skills and agents that Kahnban does not ship (`comment-sicko`, `poteto-mode`, `build-the-lever`). `kahnban skills install --source mattpocock` can install upstream skills under the same names with different behaviour. Nothing records where each copy came from.

## 2. Options considered
1. **Keep the upstream names and re-sync the copies to upstream.** This keeps the drift problem and the name clash, and it leaves Kahnban unable to improve the skills.
2. **Rename only the forks that have drifted.** This gives an inconsistent naming scheme, so it isn't clear which skills are ours.
3. **Localize all of them under a `kb-` prefix (chosen).** Each imported skill starts from the latest upstream: mattpocock/skills v1.3.2 and cursor/plugins@c742dd6. Kahnban re-applies only the adaptations its gates need, records provenance in `skills.lock.json`, and imports the missing referenced skills and the `comment-sicko` agent (as `kahnban-comment-sicko`). It does not import pstack's `poteto-mode` router.

## 3. Decision Outcome
Option 3. Every skill Kahnban ships, its own included, is named `kb-*`. Imported agents follow the existing `kahnban-*` agent pattern. Updating from upstream is a manual, deliberate edit. `skills install` removes skills it previously installed that are no longer shipped, so the rename leaves no old copies behind.

### Consequences
- **Positive:** It is clear which skills are ours, upstream installs can't clash with them, Kahnban can improve them freely, and MIT attribution is in place.
- **Negative:** It is a one-time breaking rename for existing adopters (`/tdd` becomes `/kb-tdd`). Later upstream improvements have to be merged by hand.
