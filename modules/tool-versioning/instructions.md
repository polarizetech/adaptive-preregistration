## Tool versioning

This repo is a tool: it holds no experiments and no results. Follow `.agents/protocols/TOOL_VERSIONING.md` before changing anything that alters the tool's output, its version or its releases:

- One version, in one source, mirrored in `CITATION.cff` (and `TOOL.toml`); releases are annotated `vX.Y.Z` tags, never moved.
- A release that changes an output bumps MINOR and lists it under `### Outputs changed` in `CHANGELOG.md`, naming the consumers to re-run. A PATCH never changes an output.
- Before changing anything a consumer uses, look it up in the consumers list. Run `python3 .agents/tools/release-check` before tagging.
