"""End-to-end tests: install the kit into throwaway repos and check what lands there.

Run: python3 -m unittest discover tests
"""
import json, os, shutil, subprocess, sys, tempfile, unittest

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sh(*cmd, cwd=None, check=True, env=None, inp=""):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, input=inp)
    if check and r.returncode:
        raise AssertionError(f"{' '.join(cmd)} failed ({r.returncode}):\n{r.stdout}\n{r.stderr}")
    return r


def git_init(path):
    os.makedirs(path, exist_ok=True)
    sh("git", "init", "-q", "-b", "main", cwd=path)
    sh("git", "config", "user.email", "test@example.com", cwd=path)
    sh("git", "config", "user.name", "Test", cwd=path)


class KitTest(unittest.TestCase):
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

    # ------------------------------------------------------------------ tests

    def test_init_installs_defaults(self):
        self.kit("init", "--source", self.src)
        lock = self.lock()
        self.assertEqual(lock["modules"], ["core", "convo-log"])
        self.assertEqual(lock["source"], self.src)
        for rel in (".agents/bin/kit_ap", ".agents/tools/convo-log", ".agents/protocols/CONVERSATIONS.md",
                    ".agents/README.md", ".github/hooks/kit_ap-core.json", ".github/hooks/kit_ap-convo-log.json"):
            self.assertTrue(os.path.exists(os.path.join(self.repo, rel)), rel)
        self.assertTrue(os.access(os.path.join(self.repo, ".agents/tools/convo-log"), os.X_OK))
        agents = self.read("AGENTS.md")
        self.assertIn("<!-- kit_ap:start -->", agents)
        self.assertIn("## Conversation logging", agents)
        self.assertTrue(self.read("CLAUDE.md").startswith("@AGENTS.md"))
        cmds = self.settings_commands()
        self.assertTrue(any("kit_ap\" check --hook" in c for c in cmds))
        self.assertTrue(any(".agents/tools/convo-log" in c for c in cmds))

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
        self.kit("add", "prereg")
        self.kit("remove", "prereg")
        for p, text in snapshot.items():
            self.assertEqual(self.read(p), text, p)

    def test_add_pulls_dependencies_and_remove_cleans_up(self):
        self.kit("init", "--source", self.src, "--modules", "")
        self.assertEqual(self.lock()["modules"], ["core"])
        self.kit("add", "experiment-pr-log")
        self.assertEqual(self.lock()["modules"], ["core", "convo-log", "experiment-pr-log"])
        self.assertTrue(os.path.exists(os.path.join(self.repo, ".agents/tools/tag")))
        self.assertTrue(any("prereg-status" in c for c in self.settings_commands()))
        r = self.kit("remove", "convo-log", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("requires convo-log", r.stderr)
        self.kit("remove", "experiment-pr-log", "convo-log")
        self.assertEqual(self.lock()["modules"], ["core"])
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".agents/tools")))
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".github/hooks/kit_ap-convo-log.json")))
        self.assertFalse(any("convo-log" in c or "prereg" in c for c in self.settings_commands()))
        self.assertNotIn("Conversation logging", self.read("AGENTS.md"))

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
        with open(os.path.join(self.repo, ".agents/protocols/CONVERSATIONS.md"), "a") as f:
            f.write("local edit\n")
        r = self.vendored("update", "--force", check=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("local edit", self.read(".agents/protocols/CONVERSATIONS.md"))
        with open(os.path.join(self.repo, ".agents/protocols/CONVERSATIONS.md"), "a") as f:
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

    def test_convo_log_routes_from_module_config(self):
        self.kit("init", "--source", self.src, "--modules", "experiment-pr-log")
        sh("git", "checkout", "-qb", "experiment/E001", cwd=self.repo)
        sh(sys.executable, ".agents/tools/convo-log", "add", "--role", "user", "--tool", "test", "--no-sync",
           cwd=self.repo, env=self.env, inp="hello")
        self.assertTrue(os.path.exists(os.path.join(self.repo, "experiments/E001/conversation.jsonl")))


if __name__ == "__main__":
    unittest.main()
