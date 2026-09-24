# Keeping the public post accurate

The kit is described publicly in a polarize.tech blog post. When the kit changes, the post changes with it, in the same piece of work.

| | |
|---|---|
| Site repo | `polarizetech/polarize.tech`, checked out at `~/Sites/polarize.tech` |
| Post (slug) | `adaptive-preregistration-predict-first-then-run-the-code` |
| File | `_posts/2026-09-24-adaptive-preregistration-predict-first-then-run-the-code.md` (published 2026-09-24) |
| Title | "Adaptive preregistration: predict first, then run the code" |
| Live | https://polarize.tech/blog/adaptive-preregistration-predict-first-then-run-the-code/ |

## When the post needs updating

After any change in this repo, check whether it alters something the post states. These are the post's sections and the kit sources behind them:

| Post section | Kit source |
|---|---|
| The five rules, What makes it adaptive, What the preregistration contains, Rules for whoever runs it, Limits | `modules/prereg/protocols/PREREG_PROTOCOL.md` |
| The record (tags, branch and PR per experiment, receipts) | `modules/experiment-pr-log/`: protocol and `tools/` |
| The record (conversation log) | `modules/convo-log/`: protocol and `tools/convo-log` |
| How it reaches every project (`kit_ap`, `.agents/`, `AGENTS.md`/`CLAUDE.md`, hooks, commit guard, update check) | `bin/kit_ap`, `modules/*/hooks/`, `modules/core/`, `README.md` |

Update the post if the change alters any of these: a rule, a tag or file name, what a tool or hook does, which tools are supported, a default, or a stated limit. Refactors, tests and wording-only changes to the kit don't need a post change.

## How to update it

Work in `~/Sites/polarize.tech` and follow its `CLAUDE.md`. It governs over this file.

1. **Keep the post's framing.** It's about keeping simulations and research software honest, whoever or whatever runs them. Coding assistants get a passing mention; don't turn it back into a post about AI agents.
2. **Keep to that site's rules.** The post is tier `A`, `project: method`, with no claims or citations. Don't add author names, years or DOIs in prose; its gate rejects them. A source can only be cited once it is in the research ledger, by key.
3. **It is published,** so never change a published statement silently. Update the text so it describes the kit as it now is, and add a dated note at the end of the post saying what changed:
   ```markdown
   ## Update — 2026-10-02
   The kit now also does X; the section on Y was revised to match. Previously it said Z.
   ```
   If the post was wrong when published, as opposed to the kit having changed since, write `## Correction — <date>` instead. That repo requires correction notes for errors.
4. **Run its gates** and fix anything they report for this post:
   ```bash
   cd ~/Sites/polarize.tech
   python3 scripts/validate_posts.py --drafts
   python3 scripts/check_design.py
   ```
5. **Commit there** with a message that names the kit commit it tracks, for example `Post: update adaptive-preregistration post for kit_ap bc00df1`.
6. **Don't push or publish without the user's go-ahead.** Pushing polarize.tech's `main` publishes the site.

In the kit commit that made the change, say whether the post was updated. If it wasn't, say why.
