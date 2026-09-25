# ARCHIVING.md — Depositing a repository with an archive

**Applies to:** anyone archiving a preregistration (`<EID>-prereg`) or a software release from this repo.
**Installed by:** the KIT Adaptive Preregistration `prereg` module. `PREREG_PROTOCOL.md` §2 points here.
**License:** CC BY 4.0, from [KIT Adaptive Preregistration](https://github.com/polarizetech/kit-adaptive-preregistration). Reuse it with credit.

Git history and PR receipts show the order of events, but they can be changed or deleted. An archive gives a
preregistration or a release an independent, permanent timestamp and a persistent identifier that others
can cite. This file is the step-by-step for doing that when a project is ready. Until then, `PREREG.md` §11
says "none: local git history only", which is honest and allowed.

---

## 1. Pick the archive

| Archive | Identifier | Suits | Notes |
|---|---|---|---|
| **Zenodo** | DOI | Software releases and preregistration snapshots of a GitHub repo | Its GitHub integration archives each GitHub *release* automatically once switched on. |
| **OSF Registrations** | DOI | Preregistrations as documents | Upload or link `PREREG.md` and freeze it as a registration. |
| **Software Heritage** | SWHID | Long-term preservation of the code itself | Archives the whole repository history on request; no citation metadata needed. |

Zenodo is the usual choice for a GitHub repo. The rest of this file describes it.

## 2. Before the first Zenodo release

1. **Metadata.** Add a `.zenodo.json` at the repository root. Zenodo uses it in preference to
   `CITATION.cff`, which it otherwise converts, and that conversion is strict (this kit's own first attempt,
   from a `CITATION.cff` with two licenses and a group author, failed). Keep `.zenodo.json` minimal:

   ```json
   {
     "title": "<Project name>",
     "upload_type": "software",
     "description": "<One paragraph: what it is and what the release contains.>",
     "creators": [
       {"name": "<Family>, <Given>", "orcid": "<0000-0000-0000-0000>"}
     ],
     "license": "<one license identifier from Zenodo's list, e.g. mit or cc-by-4.0>",
     "keywords": ["preregistration", "reproducibility"]
   }
   ```

   One license only: pick the one that covers what people will cite (for a preregistration, the documents;
   for software, the code) and keep the full terms in `LICENSE`.
2. **Switch the repository on.** Sign in at zenodo.org with GitHub, open
   <https://zenodo.org/account/settings/github/>, and turn the repository on (**Sync now** if it isn't listed).
   This adds a webhook to the GitHub repository. It only reacts to releases published *after* it is on.
3. **Protect release tags** (a GitHub ruleset on `v*` or `*-prereg`), so an archived tag can't later be moved
   away from what was deposited.

## 3. Archive a release

1. Tag the commit (`vX.Y.Z` for software; `<EID>-prereg` for a preregistration, via `.agents/tools/tag` if
   installed) and push the tag.
2. Publish a GitHub release for that tag: `gh release create <tag> --notes-file <notes> --verify-tag`.
3. Open the repository's row at <https://zenodo.org/account/settings/github/>. The release should turn green
   with a DOI within a few minutes. If it shows **Failed**, open the **Errors** tab. (The **Citation File** tab
   shows a generic example, not your file.)
4. A failed release can't be retried under the same tag if tags are protected. Fix the metadata and publish
   the next version.

## 4. Record the identifier

- **Preregistration:** the DOI only exists after the tag is released, so it can't be in the frozen
  `PREREG.md`. Write the archive route in §11 before tagging ("Zenodo, from the GitHub release of
  `<EID>-prereg`"), then record the DOI in the experiment's row of `EXPERIMENTS.md` and in `RESULTS.md`.
- **Software:** add `doi:` to `CITATION.cff` (use the *concept* DOI, which always resolves to the latest
  version) and a DOI badge to the README.

## 5. Stopping

To stop archiving, turn the repository off on the Zenodo page, or delete the Zenodo webhook from the GitHub
repository's settings. Records already published stay published, as they should.
