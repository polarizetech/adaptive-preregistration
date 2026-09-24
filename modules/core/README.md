# .agents — managed by agentkit

Everything in this folder was installed by [agentkit](https://github.com/polarizetech/agentkit) from the kit recorded in `kit.lock`.
Don't edit these files here. Updates overwrite them, and `update` refuses to run while they differ from what was installed.
Change the kit instead, then pull the change in:

```bash
.agents/bin/agentkit update           # pull the latest kit and re-apply
.agents/bin/agentkit status           # installed version, modules, whether it's current
.agents/bin/agentkit add <module>     # or: remove <module>
```
