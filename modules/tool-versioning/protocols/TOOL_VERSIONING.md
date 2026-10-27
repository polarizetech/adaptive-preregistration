# TOOL_VERSIONING.md — Versioning and releasing a research tool

**Applies to:** everyone who changes or releases this repo: people, scripts and coding assistants.
**Status of this file:** binding. If a task conflicts with it, stop and say so before doing the task.
**For:** tool repos (libraries, instruments, acquisition bridges, file-format code) whose output other people's
research consumes. A tool repo holds no experiments except **comparison units** (§1a): sims and dataset
analyses that compare the tool's functionality against other tools, including **bench sims** (§1b) that check
it against pinned reference implementations as part of its tests. It has the `prereg` module too, which
scopes the tool's scientific features claim first (`SCOPE_PROTOCOL.md`); this protocol governs the tool's
versions and releases, and nothing in the tool itself is preregistered outside its comparison units (§8).
**Installed by:** the KIT Adaptive Preregistration `tool-versioning` module, which also adds the one-line rule to `AGENTS.md`.
**License:** CC BY 4.0, from [KIT Adaptive Preregistration](https://github.com/polarizetech/adaptive-preregistration). Reuse it with credit.

---

## 0. The eight rules (read these even if you read nothing else)

1. **A tool holds only the tool, and its comparisons with other tools.** No experiments about the world, no
   measurements of anyone's particular device or subjects, no `experiments/` or `preregistrations/` at the root.
   The one exception is comparison units (§1a): `sims/<slug>/` and `datasets/<slug>/` that preregister
   predictions about the tool's output against other tools on declared inputs and check whether each run is
   correct, as an extension of the test suite, including bench sims (§1b), which check the tool against
   reference implementations in other repos, pinned by tag, within tolerances the owner fixed before
   scoring. Findings about the world live in the research repo that produced them, which cites the tool's
   version.
2. **One version, tagged.** SemVer, `0.MINOR.PATCH` until 1.0. The version lives in one place and is mirrored in
   `CITATION.cff` (and `TOOL.toml`, if the repo has one); they all agree. Every release is an annotated tag `vX.Y.Z` with the ISO date in its message,
   pushed, and never moved or deleted.
3. **A release that changes an output says so.** Any change to a number the tool produces bumps MINOR (before
   1.0), and its `CHANGELOG.md` entry has an `### Outputs changed` section listing exactly what changed and
   which consumers must re-run. A PATCH release never changes an output.
4. **Consumers pin a tag, never a branch.** The tool keeps a list of its consumers and what each one uses, so a
   change to those is known to affect someone the tool can't test.
5. **Dependencies point one way.** The tool never imports from a consumer or from its own extensions. A test
   enforces it.
6. **Extensions are versioned apart** and declare the tool versions they were tested against. A new MINOR of
   the tool refuses them until they are re-tested.
7. **Experimental features are siloed** and labelled experimental in code, UI and docs. Core never depends on
   them.
8. **Claims about the tool are experiments.** A comparison of the tool's output with other tools on declared
   inputs is preregistered in the tool's own comparison unit (§1a); any other claim (accuracy against the
   world, a device's noise floor, a biological interpretation) in a research repo, against a pinned tag.

---

## 1. What a tool holds

The tool repo holds code, its tests, its documentation, and fixtures that test the code (synthetic signals,
small reference files whose provenance is stated). It does not hold:

- experiments, `experiments/`, `preregistrations/`, `PREREG.md`, `RESULTS.md`, outside its comparison units (§1a);
- results: figures, tables or numbers about what the tool measured, outside its comparison units;
- measurements of a particular device, rig or subject, including "validation" runs of this copy of the
  hardware. A rig's noise floor is a finding about that rig; it belongs to the research repo that measured it;
- recordings, personal data, keys.

A finding about the tool's output (it is accurate to X, its timing drifts by Y) lives in the consuming research
repo, which states the tool version it ran against (`vX.Y.Z` and the commit). If a finding shows a bug, the fix
is a tool release, and the finding stays where it was made.

Documentation may state what the tool is *designed* to do (declared sample rate, algorithm, units). It may
not state measured performance unless it cites the research repo, or the comparison unit, and the tool
version that measured it.

## 1a. Comparison units

A tool repo may hold **sims** (`sims/<slug>/`) and **dataset analyses** (`datasets/<slug>/`) as long as they
are about comparing the tool's functionality against other tools: preregistering predictions based on inputs
and seeing whether the run is correct. They are an extension of the test suite, kept to the standard of an
experiment. Each one:

- **is a unit** (`PREREG_PROTOCOL.md` §1) with its own `SCOPE.toml`, which names what it compares:
  `compares = ["<this tool>", "<other tool> <version>", …]`, the tool itself and at least one other. It may be
  exploratory (`SCOPE_PROTOCOL.md` §2) until its first preregistered comparison.
- **predicts outputs, not the world.** Its claims and criteria are about what the tools compute on declared
  inputs: agreement, divergence, correctness against a reference implementation or an analytic answer. A
  claim about brains, subjects, devices or physical systems belongs in a research repo, even when a
  comparison unit motivated it.
- **keeps its preregistrations and results inside the unit** (`<unit>/preregistrations/<EID>/`), lists its
  EIDs in the root `EXPERIMENTS.md` (which then lists comparison units only), and records the tool version
  (`vX.Y.Z` or commit) and every other tool's pinned version that each run used.
- **depends on the tool, never the reverse** (§5). Its extra dependencies (another simulator, a reference
  library) stay out of the tool's runtime dependencies: a dev or optional dependency group.
- **is re-run when an output it predicts changes.** A release whose `### Outputs changed` touches a comparison
  unit's inputs or outputs names it there, like a consumer (§3), and its next result states the new version.

A comparison result is evidence about the tool's behaviour at a version. It is not a research finding and is
not written to the research corpus; a study that relies on it cites the unit, its EID and the tool version, or
reruns it.

## 1b. Bench sims

A **bench sim** is a sim in the tool's `sims/<slug>/` that runs like part of the test suite: it drives the tool
and one or more **reference implementations that live in another repository**, pinned by tag, on fixed inputs,
and passes or fails against tolerances the tool's owner chose before scoring. It is a sim like any other in the
tool's `sims/`, marked by `kind = "bench"` in its `SCOPE.toml`. A sim in a tool is a little different from a sim
in a study: in a study, a sim's prediction is preregistered and its outcome is a result either way; in a tool,
a bench sim's tolerances are its preregistration, and not meeting them is a failure of the tool, like a failing
test. So a bench sim has no claim and no `preregistrations/` folder. A comparison whose outcome is uncertain,
or that is meant to support a claim, is a preregistered comparison unit (§1a); one may become a bench sim
once its result is known, citing the unit and its EID.

Each bench sim:

- **declares its references** in its `SCOPE.toml`, one `[[references]]` table per external reference:

  ```toml
  format = 3
  unit = "mso-vs-goldwyn"
  kind = "bench"
  compares = ["teeter-neuron 0.4.0", "mso-goldwyn mso-goldwyn/v0.1.0"]

  [[references]]
  name = "mso-goldwyn"                         # how tolerances and results name it
  repo = "polarizetech/audio-evoked-potentials"
  tag = "mso-goldwyn/v0.1.0"                   # a tag, never a branch
  commit = "<the tag's full 40-character commit>"
  subdirectory = "sims/mso-goldwyn"            # where in the repo the reference is, if not at its root
  licence = "MIT"                              # the reference's licence, as its repo states it
  runs = "python"                              # python: installed in the sim's environment and imported
  package = "mso-goldwyn"                      #   (its distribution name)
  # runs = "process"                           # process: a separate program, never imported or linked
  # command = "octave --no-gui --eval run_case" #   (how it is invoked)
  ```

  `commit` makes a moved tag visible: the sim refuses to score if the code it fetched or installed is at
  another commit. A reference never comes from a branch, a local checkout or a vendored copy.
- **keeps its own environment.** A bench sim has its own dependency file (for Python, its own
  `pyproject.toml`). A `runs = "python"` reference is pinned there at the same tag
  (`pkg @ git+https://…@<tag>#subdirectory=…`, or the equivalent `[tool.uv.sources]` entry with `tag =`). None
  of its dependencies is a runtime dependency of the tool, and the tool never imports it (§5).
- **respects the reference's licence.** Code under a licence the tool can't take on (GPL code in an MIT
  tool, for instance) is `runs = "process"`: fetched at its tag into a cache the repo ignores, run as a
  separate process (Octave, a CLI, a container) that exchanges files with the sim, and never copied into the
  repo, imported or linked. The sim's results are data and stay under the tool's terms.
- **fixes its tolerances before scoring.** `tolerances.toml` names, for each metric and reference, the bound
  it must meet (`at_most` or `at_least`) and why, with who decided them (`decided_by`, a person) and when
  (`decided`). The owner chooses them; an assistant may propose values, never decide them. The sim scores
  nothing until they are decided and committed. A tolerance changed after a result was seen is a new
  decision: the owner records it in a `[[revisions]]` entry (the old value, the new one, why, the date), and
  the sim is re-run.
- **keeps its results in the unit**: one `results/<tool version>.json` per scored run, recording the tool's
  version and commit (and whether its tree had uncommitted changes), every reference's tag and the commit it
  ran, the hash of the `tolerances.toml` it scored against, each metric's value and bound, and pass or fail.
  A result scored against tolerances that have since changed is stale.
- **is run when a new version is tagged**, not automatically (not in CI, not on every commit): the code it
  covers changes only through a release, and an `### Outputs changed` line that touches what it compares
  names it, like a consumer (§3). The release commit carries its result for that version. A failing bench sim
  blocks the release unless the release's `CHANGELOG.md` entry names it under `### Benches` with why the
  release goes ahead (an accepted divergence, a reference bug); its result stays as it is.
- **is listed** in `TOOL.toml` under `[[comparisons]]` with `kind = "bench"`, beside the comparison units.

A tool has no `sims/` folder until its first sim. A passing bench sim is evidence that the tool agrees with
its references at a version, within the stated bounds. Like a comparison result, it is not a research
finding: a study that relies on it cites the sim, its result file and the tool version.

---

## 2. Versions and tags

- **SemVer** [1]. Before 1.0: `0.MINOR.PATCH`, where MINOR carries any change a consumer could notice in an
  output or an interface, and PATCH carries everything else. After 1.0, the usual rules apply, with rule 3
  applying to MAJOR/MINOR as SemVer does to breaking changes.
- **One version source.** The `version` field in `pyproject.toml` (`[project]`), else a single
  `__version__ = "X.Y.Z"` in the package, else, for a tool that is not a Python package, `version` in
  `TOOL.toml`. Nothing else hard-codes the version; code reads it from that source.
- **Mirrors agree with it.** `CITATION.cff` [2]: `version` equals the version source, and `date-released` is
  the tag's date. `TOOL.toml`, when present: its `version` equals it too. They change in the same commit.
- **`CHANGELOG.md`** has one `## [X.Y.Z] — YYYY-MM-DD` heading per release, newest first, and an
  `## [Unreleased]` heading for work since. A heading without a date is a release in preparation.
- **Tags.** Every release is `git tag -a vX.Y.Z -m "YYYY-MM-DD <summary>"` on the release commit, pushed.
  Tags are never moved or deleted. A mistake is fixed with a new version. Protect `v*` tags on the host
  (a GitHub ruleset) and sign them (`git config tag.gpgSign true`) so the rule is enforced, not just stated.

---

## 3. Releases that change outputs

An output is any number the tool produces or writes: a recorded or computed value, a field in an export, a
default constant (a gain, a sample rate, a threshold), a unit, a rounding, an algorithm, a file layout a
consumer parses.

- A change to an output bumps MINOR (before 1.0; MAJOR after, if it breaks consumers). PATCH releases don't
  change outputs. If a PATCH turns out to have changed one, release a new MINOR that says so; don't re-tag.
- The release's `CHANGELOG.md` entry has an `### Outputs changed` section:

  ```markdown
  ## [0.4.0] — 2026-10-02

  ### Outputs changed
  - `export_bids()`: `SamplingFrequency` is now the measured rate, not the declared one (was 256, now e.g. 255.87).
    Re-run: `lab/eeg-study` (uses `export_bids`), `lab/emg-atlas` (reads `*_eeg.json`).
  - Default notch filter 50 Hz → off. Re-run: none (no consumer uses the default).

  ### Changed
  - ...
  ```

  Each line names the function, route, field or constant, the old and new behaviour, and the consumers from
  the Consumers list (§4), the comparison units (§1a) and the bench sims (§1b) that must re-run, or `none`.
- A bench sim that fails at the release is named under `### Benches`, with why the release goes ahead (§1b).
- An `### Outputs changed` section is never empty. A release with no output change leaves the section out.

---

## 4. Consumers

- A consumer (a research repo, another tool, a pipeline) pins a tag: `tool @ v0.4.0`, a git submodule at the
  tag, or a lockfile entry with the tag's commit. Never a branch. A consumer's results cite the tag.
- The tool keeps a **Consumers** list in `TOOL.toml` or in a `## Consumers` section of `CLAUDE.md`/`AGENTS.md`
  (outside the kit's markers). For each consumer: where it is, the tag it pins if known, and what it uses
  (functions, routes, CLI commands, files, fields):

  ```toml
  [[consumers]]
  name = "eeg-study"
  repo = "your-org/eeg-study"
  pins = "v0.3.2"                 # optional: the tag it pins, if known
  uses = ["export_bids()", "GET /status", "sessions/*.json: rate_measured"]
  ```

- Before changing anything a consumer uses, look it up here. A change to a listed item has a consumer the tool
  can't test; it is an output change (§3) or an interface change, and the release says so.
- Keep the list current when a consumer starts or stops using something. A consumer the tool doesn't know
  about gets no warning; that is the consumer's risk, and the reason to be listed.

---

## 5. One-way dependency

The tool depends on nothing that depends on it. It never imports from a consumer, and core never imports from
its own extensions (§6) or experimental code (§7).

Enforce it with a test that fails on a forbidden import, for example by scanning the core package's imports:

```python
import ast, pathlib

FORBIDDEN = ("mytool_ext_", "mytool.experimental", "eeg_study")  # extensions, experimental, known consumers

def test_core_imports_only_downward():
    for path in pathlib.Path("mytool").rglob("*.py"):
        if "experimental" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            assert not any(n.startswith(FORBIDDEN) for n in names), f"{path}: imports {names}"
```

---

## 6. Extensions (optional)

If the tool can be extended by separate packages:

- Each extension is **versioned separately** and has its own `CHANGELOG.md`.
- Each declares the tool versions it was **tested against**, as a range from the tested version to the next
  MINOR: `>=0.4.0,<0.5.0`. Never an open upper bound.
- When the tool's MINOR is bumped, it **refuses** extensions whose range doesn't include it, until the
  extension's tests (its gate) are re-run against the new version and the range is widened in a new release of
  the extension.
- A **catalogue** (a file in the tool repo, or a page) indexes the known extensions: name, version, tested
  range, what it adds.

Reference pattern (Python): extensions register under an `importlib.metadata` entry-point group
`<tool>.extensions`, and their distribution names start with `<tool>-ext-`. The tool provides three calls:
`declare()` (an extension states its name, version and tested range), `require()` (the tool checks the range
against its own version and refuses on a mismatch, saying which gate to re-run), and `discover()` (lists the
installed extensions from the entry-point group, with their status). Core imports nothing from an extension
directly; it only goes through `discover()`.

---

## 7. Experimental features

Experimental features are allowed. They are:

- **siloed**: in their own module or folder (`experimental/`), switched off by default;
- **labelled**: `experimental` in their name or namespace, in any UI that shows them, and in the docs;
- **optional**: core runs and its tests pass with them removed. Core never imports them (§5);
- **not outputs**: a number from an experimental feature is not an output under §3 until the feature is
  promoted. Promoting one to core is a MINOR release, listed under `### Outputs changed` if it changes a number.

---

## 8. Claims about the tool

Predict-first still applies to anything *claimed* about the tool: accuracy, noise floor, timing, agreement
with a reference instrument or another tool. (Choosing *what* scientific features the tool implements, and on
what evidence, is a different step: `SCOPE_PROTOCOL.md`, whose overrides in a tool are preregistered in the
research corpus.) Such a claim is an experiment. A comparison of the tool's output with other tools on declared
inputs is preregistered in one of the tool's comparison units (§1a), and its results stay there. Any other claim
is preregistered in a research repo that uses `PREREG_PROTOCOL.md` (a validation study of the tool against the
world is research like any other), against a pinned tag of the tool, and its results stay there. The tool's
docs may link to either, with the tag it tested.

---

## 9. Release checklist

1. `CHANGELOG.md`: move the `[Unreleased]` entries under `## [X.Y.Z] — YYYY-MM-DD`; add `### Outputs changed`
   if any output changed (§3), naming the consumers to re-run (§4).
2. Bump the version source and `CITATION.cff` (`version`, `date-released`) in the same commit.
3. Run the tests, including the one-way dependency test (§5), then every bench sim (§1b) at the new version,
   committing each one's `results/<version>.json` (name any that fails under `### Benches`), then
   `python3 .agents/tools/release-check`.
4. `git tag -a vX.Y.Z -m "YYYY-MM-DD <summary>"`, then push the commit and the tag.
5. Tell the consumers listed under `### Outputs changed`.

`.agents/tools/release-check` (stdlib Python) checks what can be checked mechanically:

- the version source exists, is SemVer, and equals `CITATION.cff`'s `version` (and `TOOL.toml`'s, if present);
- `CHANGELOG.md` has a heading for that version;
- if that heading is dated (released), the annotated tag `vX.Y.Z` exists, and its message has an ISO date;
- a PATCH release has no `### Outputs changed` section;
- there is no `experiments/` or `preregistrations/` at the repo root, and no `preregistrations/` anywhere
  except directly inside a comparison unit (`sims/<slug>/` or `datasets/<slug>/`);
- every comparison unit has a `SCOPE.toml` whose `compares` names the tool and at least one other tool;
- a root `EXPERIMENTS.md` exists only when the repo has comparison units;
- every bench sim (`sims/<slug>/` with `kind = "bench"`) holds no `preregistrations/`, declares at least one
  `[[references]]` with a tag that is not a branch name and a full commit, and has a `tolerances.toml` once
  it has results;
- at a released version, every bench sim has `results/<version>.json`, and one that failed is named under
  `### Benches` in that version's `CHANGELOG.md` entry.

It exits 1 if any check fails. Run it before tagging and in CI. It can't tell whether an output changed; that
is the author's judgement, recorded in the changelog.

---

## 10. What this protocol does not give you

- **Knowing whether an output changed.** Nothing here detects it; regression tests on fixed fixtures help,
  and the rule is to say so when in doubt.
- **Protection for unlisted consumers.** A consumer that isn't in the list gets no warning.
- **Enforcement.** Only the dependency test and `release-check` check anything, and only if they are run. Tag
  protection on the host is what stops a moved tag.
- **Evidence about the tool's quality.** That comes from preregistered studies that pin a tag (§8).

---

## References

These are specifications, cited for the conventions used; they have no DOI.

1. Preston-Werner, T. *Semantic Versioning 2.0.0*. https://semver.org/spec/v2.0.0.html. Version numbers and
   the 0.y.z rule (§2).
2. Druskat, S., et al. *Citation File Format (CFF)*, version 1.2.0. https://citation-file-format.github.io/.
   `CITATION.cff` fields `version` and `date-released` (§2).
3. *Keep a Changelog* 1.1.0. https://keepachangelog.com/en/1.1.0/. `[Unreleased]` and dated release headings
   (§2, §3).
