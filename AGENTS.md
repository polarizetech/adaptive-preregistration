# Working on KIT Adaptive Preregistration

This repo is the source of the agent protocols that other repos install. Read `README.md` first. It covers the layout, the module conventions, and how updates reach projects.

- Everything in `modules/` ships into other repos. A change here changes how agents behave everywhere once those repos update, so keep changes deliberate and describe the behavioural change in the commit message.
- `modules/*/instructions.md` goes into every session in every project. Keep it short: rules and pointers, not explanations. Long-form material belongs in `protocols/`.
- `bin/kit_ap` and the module tools use stdlib Python 3.9+ or POSIX shell only, and must work on macOS and Linux. Hooks and tools must never block an agent: on failure they warn and exit 0.
- Keep installs backward compatible. An old vendored `.agents/bin/kit_ap` runs `update`, then hands off to the new kit's CLI through `_apply`. Don't change the `update` → `_apply` interface or the `kit_ap.lock` fields without handling older locks.
- Run `python3 -m unittest discover tests` before committing. Add a test for any new install behaviour.
- Don't install KIT Adaptive Preregistration into this repo itself. The kit is the source, not a consumer.
