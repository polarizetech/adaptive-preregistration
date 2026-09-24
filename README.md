# agentkit

One set of protocols for how LLM agents work in my repos, written once here and installed into every project. It works with Claude Code, Codex, Copilot (VS Code and the coding agent), Cursor, Gemini, and plain chat tools.

A project doesn't link to this repo at runtime. `agentkit` **copies** the protocols into the project (`.agents/`) and records the exact kit commit in a lockfile. One command pulls the latest version. Agents always read files that are really in the repo, so the protocols also work in cloud sandboxes, offline, and for collaborators.

```
this repo (the kit)                         a project that uses it
─────────────────────                       ───────────────────────────────────────────
modules/core/          ──agentkit init──▶   AGENTS.md        managed block: always-on rules
modules/convo-log/                          CLAUDE.md        "@AGENTS.md" (Claude Code import)
modules/prereg/        ◀─agentkit update──  .agents/         protocols/, tools/, bin/agentkit, kit.lock
modules/experiment-pr-log/                  .claude/settings.json, .github/hooks/   hooks, merged
```

## Quick start

```bash
git clone git@github.com:polarizetech/agentkit.git ~/Sites/agentkit
~/Sites/agentkit/bin/agentkit init /path/to/project          # core + default modules
cd /path/to/project && git add .agents AGENTS.md CLAUDE.md .claude .github && git commit -m "Add agentkit"
```

From then on the project carries its own copy of the CLI, so you don't need the kit clone:

```bash
.agents/bin/agentkit status               # installed version, modules, up to date?
.agents/bin/agentkit update               # pull the latest kit and re-apply
.agents/bin/agentkit add prereg           # add a module (dependencies come with it)
.agents/bin/agentkit remove prereg        # remove one: its files, hooks and instructions
agentkit list                             # what modules exist (run from the kit)
```

Requirements: Python 3.9+ and git. Individual modules may need more (convo-log needs `gh`); `init` prints those notes.

## How each tool picks it up

| Tool | Reads the rules from | Hooks |
|---|---|---|
| Codex (CLI, IDE, cloud) | `AGENTS.md` | Codex CLI `notify` for convo-log (global, see note printed at install) |
| GitHub Copilot (VS Code, coding agent) | `AGENTS.md` | `.github/hooks/agentkit-*.json` (VS Code agent hooks, preview) |
| Cursor | `AGENTS.md` | none; the rules tell agents what to run by hand |
| Claude Code | `CLAUDE.md` → `@AGENTS.md` | `.claude/settings.json` |
| Gemini CLI | `GEMINI.md` by default. Set `context.fileName` to `["AGENTS.md", "GEMINI.md"]` in `.gemini/settings.json` | none |
| ChatGPT, Claude.ai, other chat UIs | Paste or attach `AGENTS.md` | none; manual steps are in each protocol |

`AGENTS.md` is the single source every tool reads. The managed part sits between `<!-- agentkit:start -->` and `<!-- agentkit:end -->`. Anything you write outside the markers is project-specific and is never touched.

## Staying up to date

- Each install records `source`, `ref`, `commit` and a sha256 of every managed file in `.agents/kit.lock`.
- The `core` module adds a **session-start hook** that runs `agentkit check --hook`. If the kit has moved on, or someone edited a managed file, the agent is told to mention it. It never updates on its own. The network check is cached for 6 hours and fails silently when offline.
- `update` fetches the kit into `~/.cache/agentkit/` and applies it with **the fetched kit's own CLI**, so changes to the installer ship with the protocols.
- `update`, `add` and `remove` **refuse to run if a managed file was edited in the project**. The fix goes into the kit, or use `--force` to discard the local edit. This keeps projects from drifting quietly.
- `add` and `remove` use the version the project is pinned to, so they never upgrade other modules as a side effect.

## Modules

| Module | Default | What it does |
|---|---|---|
| `core` | always | Where protocols live, how conflicts are handled, "don't edit `.agents/`", the session-start update check. |
| `convo-log` | ✓ | Mirrors every LLM conversation to the branch's PR and a committed JSONL log. [Protocol](modules/convo-log/protocols/CONVERSATIONS.md) |
| `prereg` | | Adaptive preregistration for model experiments. [Protocol](modules/prereg/protocols/PREREG_PROTOCOL.md) |
| `experiment-pr-log` | | One branch + draft PR per experiment, tag receipts on the PR, commit guard. Requires `convo-log`. [Protocol](modules/experiment-pr-log/protocols/EXPERIMENT_PR_LOG.md) |

## Writing a module

A module is a folder in `modules/`. Layout is by convention:

```
modules/<name>/
  module.json        {"name", "title", "description", "default": bool, "requires": [...], "notes": [...]}
  instructions.md    added to the AGENTS.md block, in dependency order. Keep it short: rules + pointers.
  hooks/claude.json  {"hooks": {...}} merged into .claude/settings.json
  hooks/copilot.json copied to .github/hooks/agentkit-<name>.json
  anything else      copied into .agents/ at the same relative path, keeping the executable bit
                     (conventions: protocols/, tools/, githooks/, config/)
```

Rules that keep the kit portable:
- Put long-form protocols in `protocols/`, and give `instructions.md` a one-line pointer plus the rules an agent must follow even if it reads nothing else. Every token in the block is read in every session of every project.
- Hook commands must reference `.agents/bin/…` or `.agents/tools/…`. That's how agentkit recognises its own hooks when it updates or removes them.
- Tools must never break the agent: exit 0 on failure, and use only stdlib Python or POSIX shell (macOS and Linux).
- `notes` are printed once, when the module is first added. `{repo}` expands to the project path.
- Two modules can't ship the same file. For shared config, use a `.d/` folder (see `config/convo-log.d/`).

Then add a test in `tests/test_agentkit.py` and run:

```bash
python3 -m unittest discover tests
```

Try it for real against a scratch repo with `bin/agentkit init --force /tmp/scratch`. From a kit checkout it installs your working tree, uncommitted changes included, and the lock marks it `dirty`.
