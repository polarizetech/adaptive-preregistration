## Preregistration

Read and obey `.agents/protocols/PREREG_PROTOCOL.md` before running, modifying, or reporting any experiment, and `.agents/protocols/SCOPE_PROTOCOL.md` before building anything in a unit (an app, sim, tool, calculator, …; a folder with `preregistrations/`, or the repository itself).

- **A claim, or an exploratory label.** A unit starts with a falsifiable claim in the user's own words and what would count against it, recorded in its `SCOPE.toml`: one question, and the rest of the claim is stated when its first experiment is preregistered. If the user says a unit is exploratory, don't ask for a claim: record what is being built (`stage = "exploratory"`), label the unit exploratory, and build. Nothing an exploratory unit shows is a finding, and it gets its claim before its first experiment.
- Propose; never substitute. The user's claim, design and decisions are recorded as they give them.
- Infrastructure is yours to decide, following the organisation's conventions. Anything that implements a research concept, or presents a result in a way that changes what someone would conclude, is science: once the unit has a claim, build it only after it has an evidence basis and the user's recorded decision. A gap blocks that feature only.
- Ask one decision at a time. If you disagree, say so once, with evidence; then record and follow the user's choice.
- Never count a source you couldn't verify. `.agents/tools/scope-status` shows unscoped units and what is open.
