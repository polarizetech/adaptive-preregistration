# KIT Adaptive Preregistration

A protocol for running simulations and research software honestly: write the predictions and pass criteria
down, tag them in git, *then* run the code. The plan can change between stages, but every change is dated,
says whether the result was already known, and can't turn a fail into a pass.

This repo holds the protocol and `kit_ap`, a small CLI that installs it into any git repository. Once
installed, the rules sit in the project itself, so a person, a script or a coding assistant (Claude Code,
Codex, Copilot, Cursor, Gemini) working there reads the same rules.

- **The method:** [Adaptive preregistration: predict first, then run the code](https://polarize.tech/blog/adaptive-preregistration-predict-first-then-run-the-code/)
- **The protocol itself:** [`PREREG_PROTOCOL.md`](modules/prereg/protocols/PREREG_PROTOCOL.md), with its references

## Quick start

```bash
git clone https://github.com/polarizetech/kit-adaptive-preregistration.git
cd /path/to/your/project
/path/to/kit-adaptive-preregistration/bin/kit_ap init                 # core, prereg, convo-log
/path/to/kit-adaptive-preregistration/bin/kit_ap add experiment-pr-log  # optional: branch/PR per experiment
```

After that the project carries its own copy of the CLI, so you don't need the clone:

```bash
.agents/bin/kit_ap status               # installed version, modules, up to date?
.agents/bin/kit_ap update               # pull the latest kit and re-apply
.agents/bin/kit_ap add experiment-pr-log   # add a module (dependencies come with it)
.agents/bin/kit_ap remove convo-log      # remove one: its files, hooks and instructions
.agents/bin/kit_ap list                 # what modules exist
```

Requirements: Python 3.9+ and git, on macOS or Linux (Windows via WSL). No other dependencies. Some modules
need more (`convo-log` and `experiment-pr-log` need the GitHub CLI, `gh`); `init` prints those notes.

## Modules

| Module | Default | What it does |
|---|---|---|
| `core` | always | Where the protocols live, how conflicts are handled, and a session-start check for updates. |
| `prereg` | ✓ | The preregistration protocol: `PREREG.md`, `DEVIATIONS.md`, `RESULTS.md`, the experiment registry and milestone tags. [Protocol](modules/prereg/protocols/PREREG_PROTOCOL.md) |
| `experiment-pr-log` | | One branch and draft PR per experiment, tag receipts posted to the PR, and an optional commit guard that refuses outputs before `-prereg` and edits to a frozen plan. Requires `convo-log`. [Protocol](modules/experiment-pr-log/protocols/EXPERIMENT_PR_LOG.md) |
| `convo-log` | ✓ | Records each prompt and reply of a coding-assistant session on the branch's PR and in a committed log, with best-effort secret redaction. [Protocol](modules/convo-log/protocols/CONVERSATIONS.md) |

## What gets installed

A project doesn't link to this repo at runtime. `kit_ap` **copies** the protocols into the project and pins
the exact kit commit in a lockfile. Everything is ordinary committed files, so it works in cloud sandboxes,
offline, and for collaborators.

```
this repo (the kit)                           a project that uses it
─────────────────────                         ───────────────────────────────────────────
modules/core/              ──kit_ap init──▶   AGENTS.md    managed block: always-on rules
modules/prereg/                               CLAUDE.md    "@AGENTS.md" (Claude Code import)
modules/experiment-pr-log/ ◀─kit_ap update─   .agents/     protocols/, tools/, bin/kit_ap, kit_ap.lock
modules/convo-log/                            .claude/settings.json, .github/hooks/   hooks, merged
```

| Tool | Reads the rules from | Hooks |
|---|---|---|
| Codex (CLI, IDE, cloud) | `AGENTS.md` | Codex CLI `notify` for convo-log (global; see the note printed at install) |
| GitHub Copilot (VS Code, coding agent) | `AGENTS.md` | `.github/hooks/kit_ap-*.json` (VS Code agent hooks, preview) |
| Cursor | `AGENTS.md` | none; the rules say what to run by hand |
| Claude Code | `CLAUDE.md` → `@AGENTS.md` | `.claude/settings.json` |
| Gemini CLI | `GEMINI.md` by default; set `context.fileName` to `["AGENTS.md", "GEMINI.md"]` in `.gemini/settings.json` | none |
| People, and chat tools without repo access | `AGENTS.md` and `.agents/protocols/` | none |

The managed part of `AGENTS.md` sits between `<!-- kit_ap:start -->` and `<!-- kit_ap:end -->`. Anything
outside the markers is yours and is kept. If the markers are damaged, `kit_ap` stops rather than guess.

## How changes are applied

- **Validated before anything is written.** `kit_ap` works out the complete change first and stops, touching
  nothing, if `.claude/settings.json` doesn't parse, the markers are damaged, or it would overwrite a file it
  doesn't manage (use `--force` to replace such files). The lockfile is written last.
- **Committed for you.** `init`, `add`, `remove` and `update` commit the paths they changed, and only those.
  Other staged or unstaged work is left as it was, and gitignored paths are skipped. `AGENTS.md`, `CLAUDE.md`
  and `.claude/settings.json` are committed whole, including any edits of yours outside the managed part. Pass
  `--no-commit` to review first.
- **Pinned.** `.agents/kit_ap.lock` records `source`, `ref` (a branch or a tag), `commit` and a sha256 of
  every managed file. `add` and `remove` use that pinned commit, so they never upgrade other modules as a side
  effect.
- **Drift is refused.** If a managed file was edited in the project, `update`, `add` and `remove` stop. Put
  the change in the kit, or use `--force` to discard it.
- **Update checks.** The `core` module adds a session-start hook that runs `kit_ap check --hook`. When the
  kit has moved on, the agent is told to mention it; it never updates on its own. The check is cached (6
  hours; 30 minutes after a failure), times out after 5 seconds, and never fails the session.

## Security model

`kit_ap update` downloads the kit from the `source` in the project's lockfile and **runs that kit's own
installer**, so changes to the installer ship with the protocols. That means updating executes code from that
source. `update` prints the source and the commit range before it applies, and warns when the source isn't
this repository. Review any change to `.agents/kit_ap.lock` in a pull request the way you would review a
change to a dependency, and pin a tag (`--ref v0.1.0`) if you want updates to be deliberate.

`convo-log` posts conversation text to pull requests, which are public on public repos. Its secret redaction
is best-effort pattern matching.

## Limits

- The protocol protects the *record*, not the idea: a well-preregistered experiment on a wrong model is still
  wrong.
- Most rules are instructions. Only the commit guard and the hooks enforce anything, and both can be bypassed
  (`git commit --no-verify`, tools without hooks). The record makes violations visible afterwards.
- A local git history isn't an independent timestamp. Archive `-prereg` tags (OSF, Zenodo, Software Heritage)
  when outsiders need to rely on the result; see [`PREREG_PROTOCOL.md` §2](modules/prereg/protocols/PREREG_PROTOCOL.md#2-versions-tags-and-the-record).

## Developing the kit

A module is a folder in `modules/`, laid out by convention:

```
modules/<name>/
  module.json        {"name", "title", "description", "default": bool, "requires": [...], "notes": [...]}
  instructions.md    added to the AGENTS.md block, in dependency order. Keep it short: rules + pointers.
  hooks/claude.json  {"hooks": {...}} merged into .claude/settings.json
  hooks/copilot.json copied to .github/hooks/kit_ap-<name>.json
  anything else      copied into .agents/ at the same relative path, keeping the executable bit
                     (conventions: protocols/, tools/, githooks/, config/)
```

- Long-form protocols go in `protocols/`; `instructions.md` holds a pointer plus the rules that must be
  followed even if nothing else is read. Every line of it is read in every session of every project.
- Hook commands must reference `.agents/bin/…` or `.agents/tools/…`. That's how `kit_ap` recognises its own
  hooks when it updates or removes them.
- Tools must never break the session: warn and exit 0 on failure. Stdlib Python 3.9+ or bash only.
- `notes` are printed once, when a module is first added. `{repo}` expands to the project path.
- Two modules can't ship the same file. For shared config, use a `.d/` folder (see `config/convo-log.d/`).

```bash
python3 -m unittest discover tests      # end-to-end tests against throwaway repos
bin/kit_ap init --force /tmp/scratch    # try a working-tree install; the lock marks it `dirty`
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the rules on changes, and [CHANGELOG.md](CHANGELOG.md) for what
changed between versions.

## Citing and license

If you use or adapt the protocol, please cite it; [CITATION.cff](CITATION.cff) has the details (GitHub's
"Cite this repository" button reads it). The protocol builds on published work listed in the
[references of `PREREG_PROTOCOL.md`](modules/prereg/protocols/PREREG_PROTOCOL.md#references).

License: code under MIT, protocol documents under CC BY 4.0. See [LICENSE](LICENSE).
