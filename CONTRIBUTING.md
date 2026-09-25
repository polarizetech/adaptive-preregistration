# Contributing

Issues and pull requests are welcome, especially from people who preregister simulation or modelling work
and can say where the protocol doesn't fit practice.

## Changing the protocol

- Protocol text (`modules/*/protocols/`, `modules/*/instructions.md`) is binding in every project that
  installs it. Say in the pull request what changes for someone following it, and add a `CHANGELOG.md` entry
  saying whether it changes behaviour in installed projects.
- Cite what a rule is based on in the protocol's references, with a resolvable DOI and how deeply it was read
  ([FT] full text, [AB] abstract).
- `instructions.md` goes into every session in every project that installs the module. Keep it to rules and
  pointers; explanations go in `protocols/`.

## Changing the code

- `bin/kit_ap` and the tools are stdlib Python 3.9+ or bash, and must work on macOS and Linux. Hooks and tools
  must never block a session: warn and exit 0.
- Keep installs backward compatible. An older vendored `.agents/bin/kit_ap` runs `update` and then hands off
  to the new kit's CLI through `_apply`. Only add optional arguments to `_apply`, and handle older
  `kit_ap.lock` files.
- Add a test for any new install behaviour or failure mode:

  ```bash
  python3 -m unittest discover tests
  uvx ruff check .
  ```

## Releases

Tag `vX.Y.Z` on `main`, move the `CHANGELOG.md` entries under that version, and update `version` and
`date-released` in `CITATION.cff`.

Release tags are protected by a repository ruleset: once pushed, a `v*` tag can't be moved or deleted, by
anyone. A mistake in a release is fixed with a new version, never by re-tagging.
