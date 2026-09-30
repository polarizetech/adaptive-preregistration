## Tool scope

Scope a tool with the user before building anything scientific in it, following `.agents/protocols/SCOPE_PROTOCOL.md`:

- In a tool repository (`TOOL.toml` says `kind = "tool"`) this applies automatically to the tool itself, with its record at `SCOPE.toml` in the root. In a study repository it applies to every folder under `tools/`, each with its record in `tools/<name>/SCOPE.toml`. Anywhere else, scope a tool only when the user asks.
- Settle the claim first, in the user's exact words, with what would count against it. Build nothing before that.
- Propose; never substitute. The user's claim, design and decisions are recorded as they give them.
- Infrastructure is yours to decide, following the organisation's conventions. Anything that implements a research concept, or presents a result in a way that changes what someone would conclude, is science.
- Build no scientific feature until it has an evidence basis and the user's decision is recorded. A gap blocks that feature only.
- Ask one decision at a time. If you disagree, say so once, with evidence; then record and follow the user's choice.
- Never count a source you couldn't verify. `.agents/tools/scope-status` shows what is open and what blocks production.
