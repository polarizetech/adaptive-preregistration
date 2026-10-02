"""End-to-end tests: install the kit into throwaway repos and check what lands there.

Run: python3 -m unittest discover tests
"""
import json, os, shutil, subprocess, sys, tempfile, unittest

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Keep the developer's global git config (commit signing, credential helpers) out of the tests.
os.environ.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})


def sh(*cmd, cwd=None, check=True, env=None, inp=""):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, input=inp)
    if check and r.returncode:
        raise AssertionError(f"{' '.join(cmd)} failed ({r.returncode}):\n{r.stdout}\n{r.stderr}")
    return r


# Absolute locations the tools also search for gh. A real gh there (as on CI runners) can't be hidden from a test.
GH_FIXED_LOCATIONS = ("/opt/homebrew/bin/gh", "/usr/local/bin/gh", "/home/linuxbrew/.linuxbrew/bin/gh")
SYSTEM_GH = any(os.access(p, os.X_OK) for p in GH_FIXED_LOCATIONS)


def minimal_path(tmp):
    """A PATH with only the programs the tools need, so a gh elsewhere on the machine isn't picked up."""
    d = os.path.join(tmp, "minbin")
    if not os.path.isdir(d):
        os.makedirs(d)
        for tool in ("git", "bash", "env", "cut", "shasum", "sha256sum", "perl", "date", "cat", "tr", "wc", "dirname", "awk"):
            found = shutil.which(tool)
            if found:
                os.symlink(found, os.path.join(d, tool))
    return d


def git_init(path):
    os.makedirs(path, exist_ok=True)
    sh("git", "init", "-q", "-b", "main", cwd=path)
    sh("git", "config", "user.email", "test@example.com", cwd=path)
    sh("git", "config", "user.name", "Test", cwd=path)


class KitBase(unittest.TestCase):
    """A committed copy of the kit (the \"remote\") and an empty project repo, plus helpers."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = {**os.environ, "XDG_CACHE_HOME": os.path.join(self.tmp, "cache")}
        # A committed copy of the kit, used as the "remote" source.
        self.src = os.path.join(self.tmp, "kit")
        shutil.copytree(KIT, self.src, ignore=shutil.ignore_patterns(".git", "__pycache__", "tests"))
        git_init(self.src)
        self.commit_src("kit")
        self.repo = os.path.join(self.tmp, "proj")
        git_init(self.repo)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def commit_src(self, msg):
        sh("git", "add", "-A", cwd=self.src)
        sh("git", "commit", "-qm", msg, cwd=self.src)
        return sh("git", "rev-parse", "HEAD", cwd=self.src).stdout.strip()

    def kit(self, *args, check=True):
        return sh(sys.executable, os.path.join(KIT, "bin", "kit_ap"), *args, cwd=self.repo, check=check, env=self.env)

    def vendored(self, *args, check=True):
        return sh(sys.executable, os.path.join(self.repo, ".agents", "bin", "kit_ap"), *args,
                  cwd=self.repo, check=check, env=self.env)

    def read(self, rel):
        with open(os.path.join(self.repo, rel)) as f:
            return f.read()

    def lock(self):
        return json.loads(self.read(".agents/kit_ap.lock"))

    def settings_commands(self):
        s = json.loads(self.read(".claude/settings.json"))
        return [h["command"] for groups in s.get("hooks", {}).values() for g in groups for h in g["hooks"]]

    def log(self):
        return sh("git", "log", "--format=%s", cwd=self.repo, check=False).stdout.split("\n")

    def committed(self):
        return sh("git", "show", "--name-only", "--format=", "HEAD", cwd=self.repo).stdout.split()


class KitTest(KitBase):

    def test_init_installs_defaults(self):
        self.kit("init", "--source", self.src)
        lock = self.lock()
        self.assertEqual(lock["modules"], ["core", "prereg"])
        self.assertEqual(lock["source"], self.src)
        for rel in (".agents/bin/kit_ap", ".agents/protocols/PREREG_PROTOCOL.md", ".agents/protocols/ARCHIVING.md",
                    ".agents/README.md", ".github/hooks/kit_ap-core.json"):
            self.assertTrue(os.path.exists(os.path.join(self.repo, rel)), rel)
        self.assertTrue(os.access(os.path.join(self.repo, ".agents/bin/kit_ap"), os.X_OK))
        agents = self.read("AGENTS.md")
        self.assertIn("<!-- kit_ap:start -->", agents)
        self.assertIn("## Preregistration", agents)
        self.assertTrue(self.read("CLAUDE.md").startswith("@AGENTS.md"))
        cmds = self.settings_commands()
        self.assertTrue(any("kit_ap\" check --hook" in c for c in cmds))

    def test_keeps_user_content_and_is_idempotent(self):
        os.makedirs(os.path.join(self.repo, ".claude"))
        with open(os.path.join(self.repo, ".claude/settings.json"), "w") as f:
            json.dump({"model": "opus", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "say done"}]}]}}, f)
        with open(os.path.join(self.repo, "AGENTS.md"), "w") as f:
            f.write("# My project\n\nUse pnpm.\n")
        with open(os.path.join(self.repo, "CLAUDE.md"), "w") as f:
            f.write("Claude-only note.\n")
        self.kit("init", "--source", self.src)
        snapshot = {p: self.read(p) for p in ("AGENTS.md", "CLAUDE.md", ".claude/settings.json")}
        self.assertIn("Use pnpm.", snapshot["AGENTS.md"])
        self.assertIn("Claude-only note.", snapshot["CLAUDE.md"])
        self.assertIn("say done", self.settings_commands())
        self.assertEqual(json.loads(snapshot[".claude/settings.json"])["model"], "opus")
        self.kit("add", "experiment-pr-log")
        self.kit("remove", "experiment-pr-log")
        for p, text in snapshot.items():
            self.assertEqual(self.read(p), text, p)

    def test_add_pulls_dependencies_and_remove_cleans_up(self):
        dep = os.path.join(self.src, "modules", "needs-pr-log")  # a module that depends on another
        os.makedirs(dep)
        with open(os.path.join(dep, "module.json"), "w") as f:
            json.dump({"name": "needs-pr-log", "requires": ["experiment-pr-log"]}, f)
        self.commit_src("add a dependent module")
        self.kit("init", "--source", self.src, "--modules", "")
        self.assertEqual(self.lock()["modules"], ["core"])
        self.kit("add", "needs-pr-log")
        self.assertEqual(self.lock()["modules"], ["core", "experiment-pr-log", "needs-pr-log"])
        self.assertTrue(os.path.exists(os.path.join(self.repo, ".agents/tools/tag")))
        self.assertTrue(any("prereg-status" in c for c in self.settings_commands()))
        r = self.kit("remove", "experiment-pr-log", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("requires experiment-pr-log", r.stderr)
        self.kit("remove", "needs-pr-log", "experiment-pr-log")
        self.assertEqual(self.lock()["modules"], ["core"])
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".agents/tools")))
        self.assertFalse(any("prereg-status" in c for c in self.settings_commands()))
        self.assertNotIn("Experiment branches", self.read("AGENTS.md"))

    def test_update_from_vendored_cli(self):
        self.kit("init", "--source", self.src)
        old = self.lock()["commit"]
        with open(os.path.join(self.src, "modules/core/instructions.md"), "a") as f:
            f.write("\n- New rule from the kit.\n")
        new = self.commit_src("new rule")
        out = self.vendored("check", check=False)
        self.assertIn("out of date", out.stdout)
        hook = self.vendored("check", "--hook")
        self.assertIn("[kit_ap]", hook.stdout)
        self.vendored("update")
        self.assertEqual(self.lock()["commit"], new)
        self.assertNotEqual(old, new)
        self.assertIn("New rule from the kit.", self.read("AGENTS.md"))
        self.assertIn("up to date", self.vendored("check").stdout)

    def test_edited_managed_file_blocks_update(self):
        self.kit("init", "--source", self.src)
        with open(os.path.join(self.repo, ".agents/protocols/PREREG_PROTOCOL.md"), "a") as f:
            f.write("local edit\n")
        r = self.vendored("update", "--force", check=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("local edit", self.read(".agents/protocols/PREREG_PROTOCOL.md"))
        with open(os.path.join(self.repo, ".agents/protocols/PREREG_PROTOCOL.md"), "a") as f:
            f.write("local edit\n")
        r = self.kit("add", "prereg", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("edited", r.stderr)

    def test_migrates_legacy_install(self):
        with open(os.path.join(self.repo, "AGENTS.md"), "w") as f:
            f.write("# Proj\n\n<!-- convo-log:start -->\nold rules\n<!-- convo-log:end -->\n")
        os.makedirs(os.path.join(self.repo, ".github/hooks"))
        with open(os.path.join(self.repo, ".github/hooks/convo-log.json"), "w") as f:
            f.write('{"hooks": {"Stop": [{"type": "command", "command": "python3 tools/convo-log capture vscode"}]}}')
        os.makedirs(os.path.join(self.repo, ".claude"))
        with open(os.path.join(self.repo, ".claude/settings.json"), "w") as f:
            json.dump({"hooks": {"Stop": [{"hooks": [{"type": "command",
                       "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/convo-log\" capture claude"}]}]}}, f)
        self.kit("init", "--source", self.src)
        self.assertNotIn("old rules", self.read("AGENTS.md"))
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".github/hooks/convo-log.json")))
        self.assertFalse(any("/tools/convo-log" in c and ".agents" not in c for c in self.settings_commands()))

    def test_commits_only_its_own_files(self):
        with open(os.path.join(self.repo, "work.txt"), "w") as f:
            f.write("unrelated work\n")
        sh("git", "add", "work.txt", cwd=self.repo)
        with open(os.path.join(self.repo, "notes.txt"), "w") as f:
            f.write("untracked\n")
        self.kit("init", "--source", self.src)  # first commit in a repo with no commits yet
        self.assertEqual(self.log()[0], "Add KIT Adaptive Preregistration")
        files = self.committed()
        self.assertIn(".agents/bin/kit_ap", files)
        self.assertIn("AGENTS.md", files)
        self.assertNotIn("work.txt", files)
        status = sh("git", "status", "--porcelain", cwd=self.repo).stdout
        self.assertIn("A  work.txt", status)      # still staged, not committed
        self.assertIn("?? notes.txt", status)
        self.assertNotIn(".agents", status)       # everything kit_ap wrote is committed
        self.kit("add", "experiment-pr-log")
        self.assertEqual(self.log()[0], "Add KIT Adaptive Preregistration module: experiment-pr-log")
        self.kit("remove", "experiment-pr-log")
        self.assertEqual(self.log()[0], "Remove KIT Adaptive Preregistration module: experiment-pr-log")
        self.assertIn(".agents/protocols/EXPERIMENT_PR_LOG.md", self.committed())  # the deletion is committed

    def test_update_commits(self):
        self.kit("init", "--source", self.src)
        with open(os.path.join(self.src, "modules/core/instructions.md"), "a") as f:
            f.write("\n- Another rule.\n")
        new = self.commit_src("rule")
        self.vendored("update")
        self.assertEqual(self.log()[0], f"Update KIT Adaptive Preregistration to {new[:7]}")
        self.assertEqual(sh("git", "status", "--porcelain", cwd=self.repo).stdout, "")

    def test_no_commit(self):
        self.kit("init", "--source", self.src, "--no-commit")
        self.assertEqual(sh("git", "rev-list", "--all", cwd=self.repo).stdout, "")
        self.assertIn("AGENTS.md", sh("git", "status", "--porcelain", cwd=self.repo).stdout)

    def _receipt(self, tag, gh=True):
        """Run prereg-receipt with a stub `gh` that records the comment body; returns (body or None, stderr)."""
        stub = os.path.join(self.tmp, "stubbin")
        os.makedirs(stub, exist_ok=True)
        out = os.path.join(self.tmp, "gh_body.txt")
        with open(os.path.join(stub, "gh"), "w") as f:
            f.write("#!/usr/bin/env bash\n"
                    f'while [ $# -gt 0 ]; do [ "$1" = "--body" ] && printf "%s" "$2" > "{out}"; shift; done\n')
        os.chmod(os.path.join(stub, "gh"), 0o755)
        path = (stub + os.pathsep if gh else "") + minimal_path(self.tmp)
        if os.path.exists(out):
            os.remove(out)
        env = {**self.env, "PATH": path}
        if not gh:                     # hide any real gh in the fallback locations too
            env["HOME"] = self.tmp
        r = sh("bash", ".agents/tools/prereg-receipt", tag, cwd=self.repo, env=env)
        if not os.path.exists(out):
            return None, r.stderr
        with open(out) as f:
            return f.read(), r.stderr

    def test_receipt_hashes_the_tagged_files_of_a_hyphenated_eid(self):
        import hashlib
        self.kit("init", "--source", self.src, "--modules", "experiment-pr-log")
        d = os.path.join(self.repo, "experiments", "E01-stentor-map")
        os.makedirs(d)
        for name, text in (("PREREG.md", "prereg v1\n"), ("ENV.lock", "numpy==1.0\n")):
            with open(os.path.join(d, name), "w") as f:
                f.write(text)
        sh("git", "add", "-A", cwd=self.repo)
        sh("git", "commit", "-qm", "prereg", cwd=self.repo)
        sh("git", "tag", "-a", "E01-stentor-map-prereg", "-m", "t", cwd=self.repo)
        sh("git", "tag", "-a", "E01-stentor-map-interim-1", "-m", "t", cwd=self.repo)
        sh("git", "tag", "-a", "model-v0.1.0", "-m", "t", cwd=self.repo)
        with open(os.path.join(d, "PREREG.md"), "w") as f:            # a later working-tree edit must not leak in
            f.write("edited after the tag\n")
        want = hashlib.sha256(b"prereg v1\n").hexdigest()
        for tag in ("E01-stentor-map-prereg", "E01-stentor-map-interim-1"):
            body, _ = self._receipt(tag)
            self.assertIn(want, body)
            self.assertIn(hashlib.sha256(b"numpy==1.0\n").hexdigest(), body)
            self.assertIn("experiment: E01-stentor-map", body)
        body, _ = self._receipt("model-v0.1.0")
        self.assertIn("none (not an experiment milestone tag)", body)
        self.assertNotIn(want, body)
        if not SYSTEM_GH:  # a real gh in a fixed location would (correctly) be used
            body, err = self._receipt("E01-stentor-map-prereg", gh=False)
            self.assertIsNone(body)
            self.assertIn("gh not found", err)

class SafetyTest(KitBase):
    """Failure modes a reviewer found: every one must leave the repo untouched or fail loudly."""

    def status(self):
        return sh("git", "status", "--porcelain", "--untracked-files=all", cwd=self.repo).stdout

    def write(self, rel, text):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def test_damaged_markers_refuse_instead_of_deleting_text(self):
        self.write("AGENTS.md", "# Proj\n\n<!-- kit_ap:start -->\nold block, end marker lost\n\nImportant user notes.\n")
        r = self.kit("init", "--source", self.src, check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("marker", r.stderr)
        self.assertIn("Important user notes.", self.read("AGENTS.md"))
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".agents")))

    def test_unparseable_settings_leave_nothing_half_installed(self):
        self.write(".claude/settings.json", "{ not json")
        r = self.kit("init", "--source", self.src, check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".agents")))
        self.assertFalse(os.path.exists(os.path.join(self.repo, "AGENTS.md")))

    def test_existing_unmanaged_file_is_not_overwritten_without_force(self):
        self.write(".agents/README.md", "my own notes\n")
        r = self.kit("init", "--source", self.src, check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(".agents/README.md", r.stderr)
        self.assertEqual(self.read(".agents/README.md"), "my own notes\n")
        self.kit("init", "--source", self.src, "--force")
        self.assertNotEqual(self.read(".agents/README.md"), "my own notes\n")

    def test_gitignored_claude_dir_still_commits_the_rest(self):
        self.write(".gitignore", ".claude/\n")
        sh("git", "add", ".gitignore", cwd=self.repo)
        sh("git", "commit", "-qm", "ignore", cwd=self.repo)
        self.kit("init", "--source", self.src)
        self.assertIn(".agents/bin/kit_ap", self.committed())
        self.assertEqual(self.status(), "")  # nothing left staged or dangling

    def test_reinit_keeps_installed_modules(self):
        self.kit("init", "--source", self.src, "--modules", "prereg")
        self.kit("init", "--source", self.src, "--force")
        self.assertIn("prereg", self.lock()["modules"])

    def test_follow_a_tag(self):
        sh("git", "tag", "-a", "v0.1.0", "-m", "v0.1.0", cwd=self.src)
        tagged = sh("git", "rev-parse", "HEAD", cwd=self.src).stdout.strip()
        self.kit("init", "--source", self.src, "--ref", "v0.1.0")
        self.assertEqual(self.lock()["commit"], tagged)
        self.assertEqual(self.lock()["ref"], "v0.1.0")
        self.assertIn("up to date", self.vendored("check").stdout)
        with open(os.path.join(self.src, "modules/core/instructions.md"), "a") as f:
            f.write("\n- Later rule.\n")
        self.commit_src("after the tag")  # main moves on; the tag doesn't
        self.assertIn("up to date", self.vendored("check").stdout)

    def test_hook_check_never_fails(self):
        self.kit("init", "--source", self.src)
        self.write(".agents/kit_ap.lock", "{}")  # damaged lock
        r = self.vendored("check", "--hook", check=False)
        self.assertEqual((r.returncode, r.stderr), (0, ""))


class RetirementTest(KitBase):
    """A module removed from the kit disappears from projects on their next update, instead of breaking it."""

    def test_retired_module_is_removed_on_update(self):
        mod = os.path.join(self.src, "modules", "convo-log")  # stands in for the real, removed module
        for rel, text in (("module.json", '{"name": "convo-log"}'),
                          ("tools/convo-log", "#!/bin/sh\nexit 0\n"),
                          ("hooks/claude.json", json.dumps({"hooks": {"Stop": [{"hooks": [
                              {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/.agents/tools/convo-log"'}]}]}})),
                          ("hooks/copilot.json", "{}")):
            os.makedirs(os.path.dirname(os.path.join(mod, rel)), exist_ok=True)
            with open(os.path.join(mod, rel), "w") as f:
                f.write(text)
        self.commit_src("a kit that still has convo-log")
        self.kit("init", "--source", self.src, "--modules", "prereg,convo-log")
        self.assertIn("convo-log", self.lock()["modules"])
        shutil.rmtree(mod)
        self.commit_src("retire convo-log")
        out = self.vendored("update").stdout
        self.assertIn("[convo-log] removed", out)
        self.assertEqual(self.lock()["modules"], ["core", "prereg"])
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".agents/tools/convo-log")))
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".github/hooks/kit_ap-convo-log.json")))
        self.assertFalse(any("convo-log" in c for c in self.settings_commands()))
        r = self.vendored("add", "convo-log", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("removed from the kit", r.stderr)


class SourceNameTest(unittest.TestCase):
    """The kit repo was renamed; projects installed under the old URL keep working and move to the new one."""

    def test_former_name_maps_to_the_current_default(self):
        import importlib.machinery, importlib.util
        loader = importlib.machinery.SourceFileLoader("kit_ap_cli", os.path.join(KIT, "bin", "kit_ap"))
        spec = importlib.util.spec_from_loader("kit_ap_cli", loader)
        cli = importlib.util.module_from_spec(spec)
        loader.exec_module(cli)
        for former in cli.FORMER_SOURCES:
            self.assertEqual(cli.canonical_source(former), cli.DEFAULT_SOURCE)
        self.assertEqual(cli.canonical_source("/some/local/kit"), "/some/local/kit")
        self.assertNotIn(cli.DEFAULT_SOURCE, cli.FORMER_SOURCES)



class ClaimFirstTest(KitBase):
    """Claim-first scoping is part of prereg; the old tool-scope module is retired into it."""

    SCOPE_FILES = (".agents/protocols/SCOPE_PROTOCOL.md", ".agents/templates/SCOPE.toml", ".agents/tools/scope-status")

    def test_prereg_ships_claim_first_scoping(self):
        self.kit("init", "--source", self.src)
        for rel in self.SCOPE_FILES:
            self.assertTrue(os.path.exists(os.path.join(self.repo, rel)), rel)
        self.assertTrue(os.access(os.path.join(self.repo, ".agents/tools/scope-status"), os.X_OK))
        self.assertIn("**Claim first.**", self.read("AGENTS.md"))

    def test_tool_scope_is_retired_into_prereg(self):
        # The kit as it was: the scoping files belonged to a separate tool-scope module.
        old = os.path.join(self.src, "modules", "tool-scope")
        for rel in ("protocols/SCOPE_PROTOCOL.md", "templates/SCOPE.toml", "tools/scope-status"):
            os.makedirs(os.path.dirname(os.path.join(old, rel)), exist_ok=True)
            shutil.move(os.path.join(self.src, "modules", "prereg", rel), os.path.join(old, rel))
        with open(os.path.join(old, "module.json"), "w") as f:
            json.dump({"name": "tool-scope", "requires": ["prereg"]}, f)
        self.commit_src("the kit before the merge")
        self.kit("init", "--source", self.src, "--modules", "tool-scope")
        self.assertIn("tool-scope", self.lock()["modules"])
        # The kit now: prereg ships them, tool-scope is gone.
        for rel in ("protocols/SCOPE_PROTOCOL.md", "templates/SCOPE.toml", "tools/scope-status"):
            shutil.move(os.path.join(old, rel), os.path.join(self.src, "modules", "prereg", rel))
        shutil.rmtree(old)
        self.commit_src("merge tool-scope into prereg")
        out = self.vendored("update").stdout
        self.assertIn("[tool-scope] removed: merged into prereg", out)
        self.assertEqual(self.lock()["modules"], ["core", "prereg"])
        for rel in self.SCOPE_FILES:
            self.assertTrue(os.path.exists(os.path.join(self.repo, rel)), rel)

    def test_adding_tool_scope_is_refused(self):
        self.kit("init", "--source", self.src)
        r = self.vendored("add", "tool-scope", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("merged into prereg", r.stderr)


class UnitExperimentTest(KitBase):
    """The commit guard and receipts find an experiment by its EID, in any unit."""

    def setUp(self):
        super().setUp()
        self.kit("init", "--source", self.src, "--modules", "experiment-pr-log")
        sh("git", "config", "core.hooksPath", ".agents/githooks", cwd=self.repo)
        self.exp = os.path.join(self.repo, "sims", "sound-propagation", "preregistrations", "E07-carry")
        os.makedirs(os.path.join(self.exp, "outputs"))

    def write(self, rel, text):
        with open(os.path.join(self.exp, rel), "w") as f:
            f.write(text)

    def commit(self, *paths):
        sh("git", "add", *paths, cwd=self.repo)
        return sh("git", "commit", "-qm", "x", cwd=self.repo, check=False)

    def test_guard_follows_the_unit(self):
        self.write("PREREG.md", "plan v1\n")
        self.write("outputs/run.csv", "1\n")
        r = self.commit("sims")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no E07-carry-prereg tag", r.stdout + r.stderr)
        sh("git", "reset", "-q", cwd=self.repo)
        self.assertEqual(self.commit(os.path.join(self.exp, "PREREG.md")).returncode, 0)
        sh("git", "tag", "-a", "E07-carry-prereg", "-m", "t", cwd=self.repo)
        self.assertEqual(self.commit(os.path.join(self.exp, "outputs")).returncode, 0)
        self.write("PREREG.md", "plan v2\n")
        r = self.commit(os.path.join(self.exp, "PREREG.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("frozen after E07-carry-prereg", r.stdout + r.stderr)

    def test_receipt_finds_the_unit_folder(self):
        import hashlib
        self.write("PREREG.md", "plan v1\n")
        self.write("ENV.lock", "numpy==2.0\n")
        self.commit(os.path.join(self.exp, "PREREG.md"), os.path.join(self.exp, "ENV.lock"))
        sh("git", "tag", "-a", "E07-carry-prereg", "-m", "t", cwd=self.repo)
        body, _ = KitTest._receipt(self, "E07-carry-prereg")
        self.assertIn("folder: sims/sound-propagation/preregistrations/E07-carry", body)
        self.assertIn(hashlib.sha256(b"plan v1\n").hexdigest(), body)
        self.assertIn(hashlib.sha256(b"numpy==2.0\n").hexdigest(), body)


SCOPE_RECORD = """\
format = 1
tool = "v1-demo"
stage = "exploratory"

[claim]
text = "The transform the cochlea uses can be run in reverse to turn a recording into audio."
counts_against = "Listeners can't tell two recordings apart better than chance."
candidates = ["a", "b"]
decided = "2026-09-29"

[[features]]
id = "F1"
name = "Inverse filterbank"
kind = "science"
does = "Inverts the cochlear filterbank"
counts_against = "Round-trip error above 10 %"
status = "accepted"
basis = "derived"
sources = ["claim:AEP-0003", "doi:10.1000/example [FT]"]
derivation = "invert each band's filter"
decision = "use-research"
decided = "2026-09-29"

[[features]]
id = "F2"
name = "Layout"
kind = "infrastructure"
does = "A two-column grid"
status = "accepted"

[[features]]
id = "F3"
name = "Band count"
kind = "science"
does = "Uses 24 bands"
counts_against = "Fewer bands lose the distinction"
status = "accepted"
basis = "override"
departs_from = "32 bands is the usual choice"
reasoning = "Fewer bands are \\"easier\\" to hear.\\nSecond line."
decision = "override"
decided = "2026-09-29"
experiments = ["projects/demo/experiments/E01-bands"]

[[features]]
id = "F4"
name = "Onset threshold"
kind = "science"
does = "Marks an onset above a threshold"
counts_against = "Onsets don't match the recording's events"
status = "accepted"
basis = "gap"
decision = "research-further"
decided = "2026-09-29"

[[features]]
id = "F5"
name = "Dropped idea"
kind = "science"
status = "dropped"

[[revisions]]
feature = "F3"
date = "2026-09-29"
from = "use-research"
to = "override"
outcome_known = "no"
reasoning = "Changed my mind."
"""


class ToolVersioningTest(KitBase):
    """The tool-versioning module: installs on request, alongside prereg, and its release-check tool."""

    RELEASE_CHECK = os.path.join(KIT, "modules", "tool-versioning", "tools", "release-check")

    def test_installs_its_protocol_tool_and_rules(self):
        self.kit("init", "--source", self.src, "--modules", "tool-versioning")
        self.assertIn("tool-versioning", self.lock()["modules"])
        self.assertIn(".agents/protocols/TOOL_VERSIONING.md", self.lock()["files"])
        self.assertIn(".agents/tools/release-check", self.lock()["files"])
        self.assertTrue(os.access(os.path.join(self.repo, ".agents/tools/release-check"), os.X_OK))
        agents = self.read("AGENTS.md")
        self.assertIn("## Tool versioning", agents)
        self.assertIn(".agents/protocols/TOOL_VERSIONING.md", agents)

    def test_not_a_default(self):
        self.kit("init", "--source", self.src)
        self.assertNotIn("tool-versioning", self.lock()["modules"])

    def test_installs_alongside_prereg(self):
        self.kit("init", "--source", self.src, "--modules", "prereg,tool-versioning")
        self.assertEqual(self.lock()["modules"], ["core", "prereg", "tool-versioning"])
        self.assertIn(".agents/protocols/SCOPE_PROTOCOL.md", self.lock()["files"])  # prereg carries scoping
        self.assertIn("## Tool versioning", self.read("AGENTS.md"))

    # ---- release-check

    def write(self, rel, text):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def release_check(self):
        return sh(sys.executable, self.RELEASE_CHECK, cwd=self.repo, check=False)

    def tool_repo(self, version="0.2.0", cff=None, heading=None):
        self.write("pyproject.toml", f'[build-system]\nrequires = ["setuptools"]\n\n[project]\nname = "t"\n'
                                     f'version = "{version}"\n\n[tool.x]\nversion = "9.9.9"\n')
        self.write("CITATION.cff", f"cff-version: 1.2.0\nversion: {cff or version}\n")
        self.write("CHANGELOG.md", "# Changelog\n\n## [Unreleased]\n\n"
                   + (heading or f"## [{version}] — 2026-09-20") + "\n\n- first\n\n## [0.1.0] — 2026-09-01\n\n- old\n")
        sh("git", "add", "-A", cwd=self.repo)
        sh("git", "commit", "-qm", "release", cwd=self.repo)

    def test_passes_on_a_tagged_release(self):
        self.tool_repo()
        sh("git", "tag", "-a", "v0.2.0", "-m", "2026-09-20 first minor", cwd=self.repo)
        r = self.release_check()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("released as v0.2.0", r.stdout)

    def test_an_unreleased_version_needs_no_tag(self):
        self.tool_repo(heading="## [0.2.0]")
        r = self.release_check()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("not released yet", r.stdout)

    def test_failures(self):
        self.tool_repo(cff="0.1.9")
        r = self.release_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("CITATION.cff version 0.1.9 != 0.2.0", r.stdout)
        self.assertIn("tag v0.2.0 doesn't exist", r.stdout)
        sh("git", "tag", "v0.2.0", cwd=self.repo)  # lightweight
        self.assertIn("lightweight", self.release_check().stdout)
        for research in ("experiments/E01/PREREG.md", "preregistrations/E01/PREREG.md"):
            self.write(research, "x\n")
            self.assertIn(f"{research.split('/')[0]} exists", self.release_check().stdout)

    def test_a_patch_may_not_change_outputs(self):
        self.tool_repo(version="0.2.1", heading="## [0.2.1]\n\n### Outputs changed\n- `rate` now measured")
        r = self.release_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("PATCH release", r.stdout)

    def test_dunder_version_and_a_missing_heading(self):
        self.write("pkg/__init__.py", '__version__ = "0.3.0"\n')
        self.write("CITATION.cff", "version: 0.3.0\n")
        self.write("CHANGELOG.md", "## [0.2.0] — 2026-09-20\n")
        sh("git", "add", "-A", cwd=self.repo)
        r = self.release_check()
        self.assertIn("__version__ in pkg/__init__.py", r.stdout)
        self.assertIn("no heading for 0.3.0", r.stdout)
        self.write("pkg/other.py", '__version__ = "0.3.1"\n')
        sh("git", "add", "-A", cwd=self.repo)
        self.assertIn("disagrees", self.release_check().stdout)

    def test_tool_toml_is_a_source_and_a_mirror(self):
        self.write("TOOL.toml", 'kind = "tool"\nname = "t"\nversion = "0.4.0"\n\n[[consumers]]\nversion = "9"\n')
        self.write("CITATION.cff", "version: 0.4.0\n")
        self.write("CHANGELOG.md", "## [0.4.0]\n")
        sh("git", "add", "-A", cwd=self.repo)
        r = self.release_check()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("version 0.4.0 (TOOL.toml version)", r.stdout)
        self.tool_repo(version="0.5.0", heading="## [0.5.0]")  # pyproject is now the source
        r = self.release_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("TOOL.toml version 0.4.0 != 0.5.0", r.stdout)


class ScopeStatusTest(unittest.TestCase):
    """scope-status implements the record contract in SCOPE_PROTOCOL.md section 9."""

    TOOL = os.path.join(KIT, "modules", "prereg", "tools", "scope-status")

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def status(self, record, *args, name="SCOPE.toml"):
        path = os.path.join(self.tmp, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(record)
        return sh(sys.executable, self.TOOL, *args, path, check=False)

    def test_valid_exploratory_record(self):
        r = self.status(SCOPE_RECORD, "--check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("Errors", r.stdout)
        self.assertIn("Blocked", r.stdout)
        self.assertIn("F4: research further", r.stdout)
        self.assertIn("F3: override's experiment has no recorded result", r.stdout)
        self.assertIn("The transform the cochlea uses", r.stdout)  # the claim, verbatim

    def test_production_needs_everything_resolved(self):
        production = SCOPE_RECORD.replace('stage = "exploratory"', 'stage = "production"')
        r = self.status(production, "--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("Before production", r.stdout)
        ready = production.split('[[features]]\nid = "F4"')[0].replace(
            'experiments = ["projects/demo/experiments/E01-bands"]',
            'experiments = ["projects/demo/experiments/E01-bands"]\nresult = "RESULTS.md: PASS; kept"')
        ready += SCOPE_RECORD[SCOPE_RECORD.index('[[features]]\nid = "F5"'):]
        r = self.status(ready, "--check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("Nothing open", r.stdout)

    def test_a_tool_repository_links_its_overrides_into_the_corpus(self):
        """A tool holds no research: its override's experiment lives in the corpus (SCOPE_PROTOCOL.md §1, §7)."""
        with open(os.path.join(self.tmp, "TOOL.toml"), "w") as f:
            f.write('kind = "tool"\nname = "demo"\n')
        ready = SCOPE_RECORD.replace('stage = "exploratory"', 'stage = "production"')
        ready = ready.split('[[features]]\nid = "F4"')[0].replace(
            'experiments = ["projects/demo/experiments/E01-bands"]',
            'experiments = ["corpus:demo/preregistrations/E01-bands"]\nresult = "corpus RESULTS.md: PASS; kept"')
        ready += SCOPE_RECORD[SCOPE_RECORD.index('[[features]]\nid = "F5"'):]
        r = self.status(ready, "--check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("preregistrations", os.listdir(self.tmp))

    def test_without_check_always_exits_zero(self):
        r = self.status(SCOPE_RECORD.replace('stage = "exploratory"', 'stage = "production"'))
        self.assertEqual(r.returncode, 0)

    def test_contract_errors(self):
        cases = {
            "established needs at least one source": SCOPE_RECORD.replace(
                'basis = "derived"\nsources = ["claim:AEP-0003", "doi:10.1000/example [FT]"]',
                'basis = "established"\nsources = []'),
            "needs an identifier": SCOPE_RECORD.replace('"doi:10.1000/example [FT]"', '"doi:10.1000/example"'),
            "override needs `reasoning`": SCOPE_RECORD.replace(
                'reasoning = "Fewer bands are \\"easier\\" to hear.\\nSecond line."\n', ""),
            "a gap can only be open": SCOPE_RECORD.replace(
                'basis = "gap"\ndecision = "research-further"', 'basis = "gap"\ndecision = "use-research"'),
            "duplicate id": SCOPE_RECORD.replace('id = "F2"', 'id = "F1"'),
            "decided must be YYYY-MM-DD": SCOPE_RECORD.replace('decided = "2026-09-29"\n\n[[features]]\nid = "F2"',
                                                             'decided = "29/09/2026"\n\n[[features]]\nid = "F2"'),
            "isn't in the record": SCOPE_RECORD.replace('feature = "F3"', 'feature = "F9"'),
            "kind must be one of": SCOPE_RECORD.replace('kind = "infrastructure"', 'kind = "ui"'),
        }
        for message, record in cases.items():
            with self.subTest(message):
                self.assertNotEqual(record, SCOPE_RECORD, "fixture replacement didn't apply")
                r = self.status(record, "--check")
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn(message, r.stdout)

    def test_missing_basis_is_open_not_an_error(self):
        record = SCOPE_RECORD.replace('basis = "derived"\n', "").replace('decision = "use-research"\n', "")
        r = self.status(record, "--check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("F1: no basis yet", r.stdout)

    def test_outside_the_toml_subset_is_rejected(self):
        for bad in ('reasoning = """two\nlines"""', 'meta = { a = 1 }', 'decided = 2026-09-29'):
            with self.subTest(bad):
                r = self.status(SCOPE_RECORD + "\n[extra]\n" + bad + "\n", "--check")
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("cannot read the record", r.stdout)

    def make_units(self, *units, scoped=()):
        """Unit folders (each gets a preregistrations/ folder); those in `scoped` also get a SCOPE.toml."""
        for u in units:
            os.makedirs(os.path.join(self.tmp, u, "preregistrations"), exist_ok=True)
            if u in scoped:
                with open(os.path.join(self.tmp, u, "SCOPE.toml"), "w") as f:
                    f.write(SCOPE_RECORD.replace('tool = "v1-demo"', f'tool = "{os.path.basename(u)}"'))
        return sh(sys.executable, self.TOOL, "--check", self.tmp, check=False)

    def test_units_are_found_by_their_preregistrations_folder(self):
        os.makedirs(os.path.join(self.tmp, "shared", "helpers"))  # not a unit: no preregistrations/
        r = self.make_units("sims/sound-propagation", "apps/v1-listener", "calculators/spl", scoped=("apps/v1-listener",))
        self.assertEqual(r.returncode, 0, r.stdout)  # unscoped is open, not a contract error
        self.assertIn("Unscoped units", r.stdout)
        self.assertIn("sims/sound-propagation: no SCOPE.toml yet", r.stdout)
        self.assertIn("calculators/spl: no SCOPE.toml yet", r.stdout)
        self.assertNotIn("apps/v1-listener: no SCOPE.toml", r.stdout)
        self.assertNotIn("shared", r.stdout)
        self.assertNotIn("the repository", r.stdout)  # a repo of units isn't itself a unit
        self.assertIn("v1-listener (exploratory)", r.stdout)  # its record is read

    def test_units_listed_in_a_study_manifest(self):
        with open(os.path.join(self.tmp, "STUDY.toml"), "w") as f:
            f.write('''kind = "study"
name = "demo"                    # a comment
stage = "SKETCH"

[corpus]
project = "demo"

[[apps]]
version = "v1"
slug = "first-look"
status = "superseded"

[[apps]]
version = "v2"
slug = "listener"

[[sims]]
slug = "propagation"
path = "projects/propagation"    # adopted where it already was

[[sims]]
slug = "chorus"
repo = "someone/chorus"
ref = "model-v0.2.0"

[[calculators]]
slug = "not-made-yet"
''')
        for d in ("apps/v1-first-look", "apps/v2-listener", "projects/propagation", "projects/unlisted"):
            os.makedirs(os.path.join(self.tmp, d))
        r = sh(sys.executable, self.TOOL, "--check", self.tmp, check=False)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("apps/v2-listener: no SCOPE.toml yet", r.stdout)       # declared, before any preregistration
        self.assertIn("projects/propagation: no SCOPE.toml yet", r.stdout)   # at its declared path
        for absent in ("v1-first-look", "chorus", "not-made-yet", "unlisted", "the repository"):
            self.assertNotIn(absent, r.stdout)

    def test_a_repo_without_units_is_one_unit(self):
        r = sh(sys.executable, self.TOOL, "--check", self.tmp, check=False)
        self.assertEqual(r.returncode, 0)
        self.assertIn("the repository: no SCOPE.toml yet", r.stdout)
        with open(os.path.join(self.tmp, "SCOPE.toml"), "w") as f:
            f.write(SCOPE_RECORD)
        r = sh(sys.executable, self.TOOL, "--check", self.tmp, check=False)
        self.assertNotIn("Unscoped", r.stdout)

    def test_tool_repository_is_one_unit_scoped_at_its_root(self):
        with open(os.path.join(self.tmp, "TOOL.toml"), "w") as f:
            f.write('kind = "tool"\nname = "demo"\n')
        os.makedirs(os.path.join(self.tmp, "tools", "scripts"))  # a tool's helper folder isn't a unit
        r = sh(sys.executable, self.TOOL, "--check", self.tmp, check=False)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("the repository: no SCOPE.toml yet", r.stdout)
        self.assertNotIn("tools/scripts", r.stdout)

    def test_earlier_root_experiments_layout_is_one_unit(self):
        os.makedirs(os.path.join(self.tmp, "experiments", "E01-x"))
        r = sh(sys.executable, self.TOOL, self.tmp, check=False)
        self.assertIn("the repository: no SCOPE.toml yet", r.stdout)

    def test_format_2_and_claim_details(self):
        record = SCOPE_RECORD.replace("format = 1\ntool = ", "format = 2\nunit = ").replace(
            'feature = "F3"', 'feature = "claim"')
        r = self.status(record, "--check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("v1-demo (exploratory)", r.stdout)
        self.assertIn("not yet stated: concepts, measure, smallest_effect, assumptions", r.stdout)
        r = self.status(record.replace("unit = ", "tool = "), "--check")  # format 2 names it `unit`
        self.assertIn("unit is empty", r.stdout)

    def test_finds_every_record_under_a_folder(self):
        for app in ("apps/v1-one", "apps/v2-two", ".agents/templates"):
            os.makedirs(os.path.join(self.tmp, app))
            with open(os.path.join(self.tmp, app, "SCOPE.toml"), "w") as f:
                f.write(SCOPE_RECORD.replace('tool = "v1-demo"', f'tool = "{os.path.basename(app)}"'))
        r = sh(sys.executable, self.TOOL, self.tmp, check=False)
        self.assertIn("v1-one", r.stdout)
        self.assertIn("v2-two", r.stdout)
        self.assertNotIn("templates", r.stdout)  # the vendored template is skipped


if __name__ == "__main__":
    unittest.main()
