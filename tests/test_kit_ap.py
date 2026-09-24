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

    def log(self):
        return sh("git", "log", "--format=%s", cwd=self.repo, check=False).stdout.split("\n")

    def committed(self):
        return sh("git", "show", "--name-only", "--format=", "HEAD", cwd=self.repo).stdout.split()

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
        self.kit("add", "prereg")
        self.assertEqual(self.log()[0], "Add KIT Adaptive Preregistration module: prereg")
        self.kit("remove", "prereg")
        self.assertEqual(self.log()[0], "Remove KIT Adaptive Preregistration module: prereg")
        self.assertIn(".agents/protocols/PREREG_PROTOCOL.md", self.committed())  # the deletion is committed

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

    def test_convo_log_routes_from_module_config(self):
        self.kit("init", "--source", self.src, "--modules", "experiment-pr-log")
        sh("git", "checkout", "-qb", "experiment/E001", cwd=self.repo)
        sh(sys.executable, ".agents/tools/convo-log", "add", "--role", "user", "--tool", "test", "--no-sync",
           cwd=self.repo, env=self.env, inp="hello")
        self.assertTrue(os.path.exists(os.path.join(self.repo, "experiments/E001/conversation.jsonl")))

    def _receipt(self, tag, gh=True):
        """Run prereg-receipt with a stub `gh` that records the comment body; returns (body or None, stderr)."""
        stub = os.path.join(self.tmp, "stubbin")
        os.makedirs(stub, exist_ok=True)
        out = os.path.join(self.tmp, "gh_body.txt")
        with open(os.path.join(stub, "gh"), "w") as f:
            f.write('#!/usr/bin/env bash\nwhile [ $# -gt 0 ]; do [ "$1" = "--body" ] && printf "%%s" "$2" > "%s"; shift; done\n' % out)
        os.chmod(os.path.join(stub, "gh"), 0o755)
        path = (stub + os.pathsep if gh else "") + "/usr/bin:/bin"
        if os.path.exists(out):
            os.remove(out)
        r = sh("bash", ".agents/tools/prereg-receipt", tag, cwd=self.repo, env={**self.env, "PATH": path})
        return (open(out).read() if os.path.exists(out) else None), r.stderr

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
        body, err = self._receipt("E01-stentor-map-prereg", gh=False)
        self.assertIsNone(body)
        self.assertIn("gh not found", err)


if __name__ == "__main__":
    unittest.main()
