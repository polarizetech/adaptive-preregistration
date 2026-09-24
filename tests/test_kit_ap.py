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
        self.assertEqual(lock["modules"], ["core", "convo-log", "prereg"])
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
        self.kit("add", "experiment-pr-log")
        self.kit("remove", "experiment-pr-log")
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
            f.write("#!/usr/bin/env bash\n"
                    f'while [ $# -gt 0 ]; do [ "$1" = "--body" ] && printf "%s" "$2" > "{out}"; shift; done\n')
        os.chmod(os.path.join(stub, "gh"), 0o755)
        path = (stub + os.pathsep if gh else "") + "/usr/bin:/bin"
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
        body, err = self._receipt("E01-stentor-map-prereg", gh=False)
        self.assertIsNone(body)
        self.assertIn("gh not found", err)

    def test_convo_log_finds_gh_off_path(self):
        """A hook's PATH often lacks ~/.local/bin; convo-log must still find gh there instead of queueing forever."""
        self.kit("init", "--source", self.src, "--modules", "experiment-pr-log")
        sh("git", "checkout", "-qb", "experiment/E002", cwd=self.repo)
        home = os.path.join(self.tmp, "home")
        stub = os.path.join(home, ".local", "bin")
        os.makedirs(stub)
        calls = os.path.join(self.tmp, "gh_calls.txt")
        with open(os.path.join(stub, "gh"), "w") as f:
            f.write("#!/usr/bin/env bash\n"
                    f'echo "$@" >> "{calls}"\n'
                    'if [ "$1 $2" = "pr view" ]; then echo \'{"number": 7, "url": "u"}\'; '
                    'else echo "https://x/pull/7#c1"; fi\n')
        os.chmod(os.path.join(stub, "gh"), 0o755)
        env = {**self.env, "PATH": "/usr/bin:/bin", "HOME": home}
        for role, text in (("user", "hi"), ("assistant", "hello")):
            sh(sys.executable, ".agents/tools/convo-log", "add", "--role", role, "--tool", "test", "--no-sync",
               cwd=self.repo, env=env, inp=text)
        r = sh(sys.executable, ".agents/tools/convo-log", "sync", cwd=self.repo, env=env)
        self.assertTrue(os.path.exists(calls), r.stderr)
        with open(calls) as f:
            self.assertIn("pr comment 7", f.read())
        env["HOME"] = os.path.join(self.tmp, "nohome")
        sh(sys.executable, ".agents/tools/convo-log", "add", "--role", "user", "--tool", "test", "--no-sync",
           cwd=self.repo, env=env, inp="again")
        r = sh(sys.executable, ".agents/tools/convo-log", "sync", "--flush", cwd=self.repo, env=env)
        self.assertIn("gh not found", r.stderr)



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


class RedactionTest(unittest.TestCase):
    """convo-log posts to PRs that may be public, so credentials must not survive."""

    @classmethod
    def setUpClass(cls):
        import importlib.machinery, importlib.util
        loader = importlib.machinery.SourceFileLoader("convo_log", os.path.join(KIT, "modules/convo-log/tools/convo-log"))
        spec = importlib.util.spec_from_loader("convo_log", loader)
        cls.mod = importlib.util.module_from_spec(spec)
        loader.exec_module(cls.mod)

    SECRETS = {
        "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY": "wJalrXUtnFEMI",
        "DATABASE_PASSWORD=hunter2hunter2": "hunter2",
        "Authorization: Bearer abcdef0123456789abcdef": "abcdef0123456789",
        "token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl": "eyJhbGci",
        "sk_live_abcdefghijklmnop1234": "abcdefghijklmnop",
        "AIzaSyA1234567890abcdefghijklmnopqrstuv": "AIzaSy",
        "postgres://admin:s3cretpw@db.example.com/x": "s3cretpw",
        'api_key: "a b c d e"': "a b c d e",
        "ghp_abcdefghijklmnopqrstuvwxyz0123456789": "ghp_",
        "hf_abcdefghijklmnopqrstuvwxyzABCDEF": "hf_abc",
        "sk-ant-api03-abcdefghijklmnopqrstuvwx": "api03",
    }

    def test_secrets_are_redacted(self):
        for text, secret in self.SECRETS.items():
            with self.subTest(text=text):
                out = self.mod.redact(text)
                self.assertNotIn(secret, out)
                self.assertIn("[redacted]", out)

    def test_ordinary_prose_is_left_alone(self):
        for text in ("the token budget is 10", "set a password policy", "secret: tbd", "see https://example.com/a:b@c"):
            with self.subTest(text=text):
                self.assertEqual(self.mod.redact(text), text)


if __name__ == "__main__":
    unittest.main()
