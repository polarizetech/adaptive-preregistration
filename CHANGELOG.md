# Changelog

Notable changes, newest first. Versions follow [semantic versioning](https://semver.org/): a new major
version changes what the protocol requires or breaks installed projects; a minor version adds to it.
Every entry says whether it changes **behaviour in installed projects**, because an update applies it
there.

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
