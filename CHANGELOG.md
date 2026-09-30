# Changelog

Notable changes, newest first. Versions follow [semantic versioning](https://semver.org/): a new major
version changes what the protocol requires or breaks installed projects; a minor version adds to it.
Every entry says whether it changes **behaviour in installed projects**, because an update applies it
there.

## [0.7.0] — 2026-10-01

A new module for releasing tools, and tool repositories keep their research elsewhere.

- **New module `tool-versioning`** (not a default), for a repo that is a tool whose output other people's
  research consumes. `TOOL_VERSIONING.md` sets eight rules: a tool holds only the tool; one SemVer version
  source (`pyproject.toml`, a single `__version__`, or `TOOL.toml`) mirrored in `CITATION.cff` and `TOOL.toml`,
  released as annotated `vX.Y.Z` tags never moved; a release that changes an output bumps MINOR and lists it
  under `### Outputs changed`, naming the consumers to re-run; consumers pin tags and are listed with what they
  use; one-way dependencies enforced by a test; separately versioned extensions with tested ranges; siloed
  experimental features; claims about the tool preregistered in a research repo against a pinned tag.
  `.agents/tools/release-check` checks the mechanical parts. It installs alongside `prereg`. Built from a
  draft in an earlier session. Behaviour in installed projects: none unless the module is added.
- **A tool repository's overrides are preregistered in the research corpus,** not in the tool. A repository
  that is a tool (`TOOL.toml` with `kind = "tool"`, or `**Kind:** tool`) holds no research: an override in its
  `SCOPE.toml` links to an experiment preregistered in the corpus project (`corpus_project`), and findings stay
  there. Units inside a study are unchanged. Behaviour in installed projects: yes, after update, for tool
  repositories only.

## [0.6.0] — 2026-09-30

Preregistration works per unit, and every unit starts with a falsifiable claim. `tool-scope` is merged into `prereg`.
Run `.agents/bin/kit_ap update` in each project.

- **Preregistration works per unit.** A repository that holds several units (apps, sims, tools, calculators,
  dataset analyses) gives each its own experiments in `<unit>/preregistrations/<EID>/`, its own claim and its
  own versions; a unit is any folder with a `preregistrations/` folder, and any other repository is one unit.
  `EXPERIMENTS.md` stays at the root, with a Unit column; EIDs are unique per repository; version tags start
  with the unit's folder name when a repository has more than one versioned unit. The earlier root
  `experiments/<EID>/` layout still works. The commit guard, tag receipts and status line find an
  experiment's folder by its EID. Behaviour in installed projects: yes, after update.
- **Claim first, for every unit.** `tool-scope` is merged into `prereg`: every unit starts with a falsifiable
  claim, settled with the user and recorded verbatim, before anything is built in it. The claim step now also
  asks, one question at a time, for what the terms mean, how it will be measured, the smallest effect that
  would matter, and what a test assumes, following the derivation-chain and smallest-effect literature
  (Scheel et al. 2021; Lakens 2022; both read in full, passages checked). Overrides are preregistered in the
  unit's own `preregistrations/`. `SCOPE.toml` is format 2 (`unit` instead of `tool`, optional claim details);
  format 1 is still read. `scope-status` lists unscoped units. Projects with `tool-scope` drop it on their next
  update and keep its files through `prereg`. Behaviour in installed projects: yes, after update.
## [0.5.0] — 2026-09-30

**Behaviour in installed projects:** `tool-scope` now also applies automatically to a repository that is
itself a tool. Projects with the module get it on `.agents/bin/kit_ap update`.

- **`tool-scope` applies automatically to a tool repository.** A repository whose `TOOL.toml` says
  `kind = "tool"` (or whose README carries `**Kind:** tool`) is scoped without being asked, with its record at
  `SCOPE.toml` in the root; `scope-status` reports it as unscoped until that record exists. Tools under a
  study's `tools/` are scoped as before.

## [0.4.0] — 2026-09-30

`tool-scope` now applies automatically to every tool in a study. Projects with the module get it on `.agents/bin/kit_ap update`.

- **`tool-scope` applies automatically to a study's tools.** In a study repository (`STUDY.toml` with
  `kind = "study"`, or the README kind line `**Kind:** study`), every folder under `tools/` is a tool and is
  scoped before anything scientific is built in it, with its record at `tools/<name>/SCOPE.toml`. Anywhere
  else, scoping runs only when the user asks. `scope-status`, run at a study's root, lists tool folders with no
  record as unscoped; `--check` no longer fails when there is nothing to check. Behaviour in installed projects:
  yes, after update, for projects with `tool-scope`.

## [0.3.0] — 2026-09-29

Adds the `tool-scope` module. Nothing changes in a project until it runs `.agents/bin/kit_ap add tool-scope`.

- **New module: `tool-scope`** (opt-in; requires `prereg`). Before an assistant builds software that
  explores a research claim, it scopes the tool with the user step by step: the claim first, recorded in the
  user's words with what would count against it; then features; then, for every scientific feature, an
  evidence basis (`established`, `supported`, `derived`, `override`, `gap`) and the user's decision, one at a
  time. The basis extends `PREREG_PROTOCOL.md`'s parameter tags to features, and every override is drafted as a
  prediction for a preregistered experiment. Each tool keeps a `SCOPE.toml` record whose format is a
  documented contract (`SCOPE_PROTOCOL.md` §9) that other tools can validate without dependencies;
  `.agents/tools/scope-status` prints its state and, with `--check`, gates CI. Behaviour in installed
  projects: none unless the module is added.

## [0.2.0] — 2026-09-29

Conversation logging is gone, and archiving with OSF or Zenodo is documented. Run `.agents/bin/kit_ap update`
in each project to pick it up.

- **Conversation logging (`convo-log`) is removed from the kit.** Conversations should no longer be recorded to
  pull requests or committed logs. `experiment-pr-log` no longer depends on it. Projects that have it drop it on
  their next `update`: its tool, protocol and hooks are deleted and the reason is printed; adding it again is
  refused. Existing logs and PR comments are not touched. Behaviour in installed projects: yes, on update.
- The repository is renamed `polarizetech/adaptive-preregistration` (was `kit-adaptive-preregistration`); the
  project is still called KIT Adaptive Preregistration and the CLI is still `kit_ap`. GitHub redirects the old
  URL. `kit_ap` treats the old URL as the default source, and `update` records the new one in the lock.
  Behaviour in installed projects: their lock's source changes on the next update; nothing else.
- `ARCHIVING.md` (in the `prereg` module): when a preregistration or release qualifies for an OSF
  Registration, a Zenodo deposit, both or neither, the gates before anything goes public, and the steps for
  each (OSF Registration; Zenodo from GitHub releases; Zenodo manual deposit; funder repositories). Platform
  facts checked against OSF's and Zenodo's documentation on 2026-09-25 and cited. `PREREG.md` §11 now names
  the archive route; the identifier goes in `EXPERIMENTS.md` once issued. Behaviour in installed projects:
  yes, a new protocol document after update.
- Zenodo archiving of this repo is switched off until projects are ready to move there; the v0.1.1 attempt
  failed and no record was created.

## [0.1.1] — 2026-09-24

No change in behaviour for installed projects. It was meant to be the first release archived on Zenodo;
the archiving failed and was switched off (see Unreleased).

- `CITATION.cff` carries the author's ORCID.
- Tests no longer pick up a `gh` installed on the machine (CI runners ship one).
- Release tags are protected: a `v*` tag can't be moved or deleted once pushed.

## [0.1.0] — 2026-09-24

First public release.

### Protocol
- `PREREG.md` has eleven sections. New: estimands, performance measures and Monte Carlo uncertainty in the
  pass criteria; a justified number of runs and a stopping rule; a sensitivity analysis whose "not robust"
  rule is fixed in advance; a section on prior knowledge of the target data and calibration vs validation
  targets; decision rules for adaptive stages.
- `EXPERIMENTS.md` registry: every experiment ID is listed, with the one it replaces, so a pass after earlier
  failures is always reported as one attempt among several.
- Pilot runs before `-prereg` are defined (non-preregistered seeds or synthetic inputs, under
  `exploratory/pilot/`, never cited).
- `DEVIATIONS.md` adds an "unregistered steps" table.
- The record's limits are stated plainly: tags can be moved unless signed and protected, PR receipts are
  evidence of existence rather than an archive, and only an archive deposit gives an immutable timestamp.
- References corrected and completed, each marked with how deeply it was read. "Adaptive" is now described
  as Gould et al. use it, including where this protocol differs on purpose.

### kit_ap
- Every change is computed and validated before anything is written; the lockfile is written last. It stops,
  changing nothing, on damaged `AGENTS.md` markers (previously this could delete text outside the block), an
  unparseable `.claude/settings.json`, or a file it doesn't manage that it would overwrite.
- Auto-commit skips gitignored paths instead of failing and leaving changes staged.
- `--ref` accepts tags as well as branches.
- The session-start check can't fail or print a traceback, and caches failed checks, so an offline session
  doesn't wait for the timeout every time.
- `update` prints the source and commit range it's about to run, and warns when the source isn't this repo.
- Re-running `init --force` keeps the installed modules.
- `prereg` is now a default module.

### Tools
- `convo-log`: redacts many more credential formats (bearer tokens, JWTs, Stripe, Google, Hugging Face, URL
  passwords, `*_SECRET*=` / `*_PASSWORD=` settings). Posting no longer holds the log lock, so a slow upload
  can't make the next prompt's hook time out and drop it. Runs unlocked instead of crashing on native Windows.
- `prereg-receipt`, `tag`: usage messages, a `sha256sum` fallback, and posting errors reported as they are.
- `pre-commit` guard: handles any file name.
- `EXPERIMENT_PR_LOG.md` no longer promises a "deviations echo" that was never implemented.

### Project
- Licensed: code under MIT, protocol documents under CC BY 4.0. `CITATION.cff`, CI (tests on Linux and macOS,
  Python 3.9 and 3.13; ruff; shellcheck), `CONTRIBUTING.md`.
