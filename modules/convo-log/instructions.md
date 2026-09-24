## Conversation logging

This repo logs LLM conversations to the branch's PR and to `conversations/` via `.agents/tools/convo-log` (see `.agents/protocols/CONVERSATIONS.md`).
- Work on a branch, not `main`. Before the first reply on a new branch, open a draft PR so the log has somewhere to post:
  `git commit --allow-empty -m "start: <topic>" && git push -u origin HEAD && gh pr create --draft --fill`
- Include the branch's conversation log file in your commits.
- Never edit, rewrite, or delete conversation logs or their PR comments.
- If your tool has no hooks (see CONVERSATIONS.md §4), at the end of each turn run:
  ```bash
  .agents/tools/convo-log add --role user --tool <tool> --no-sync <<'MSG'
  <the user's message, verbatim>
  MSG
  .agents/tools/convo-log add --role assistant --tool <tool> <<'MSG'
  <your final reply, verbatim>
  MSG
  ```
