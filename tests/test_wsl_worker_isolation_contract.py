"""Read-only qualification harness for a FUTURE isolated VeraOS worker.

The normal test run performs one in-memory counterexample and skips all host
qualification gates. To opt in, an operator must first provision and authorize
four real, distinct Linux accounts in a disposable VM or other test host.

No test creates accounts, changes ACLs/mounts, launches Windows executables,
connects to a broker, writes user files, or grants an external effect. An
environment variable is only a test selector, never evidence of identity.
"""
from __future__ import annotations

from contextlib import closing
import errno
import os
from pathlib import Path
import sqlite3
import unittest

try:
    import pwd  # Unix-only; Windows discovery must still report SKIP.
except ImportError:  # pragma: no cover - exercised on Windows, not this host
    pwd = None


ENABLED = os.environ.get("VERAOS_ISO_QUALIFY") == "read-only"
ROLES = ("state", "inspect", "digest", "broker")


def _account_map() -> dict[str, pwd.struct_passwd]:
    """Resolve existing OS identities; never provision or impersonate them."""
    if pwd is None:
        raise AssertionError("real Linux account lookup unavailable")
    names = {role: os.environ.get(f"VERAOS_ISO_USER_{role.upper()}") for role in ROLES}
    if any(not name for name in names.values()):
        raise AssertionError("four pre-existing account names must be supplied")
    accounts = {role: pwd.getpwnam(name) for role, name in names.items()}
    if len({account.pw_uid for account in accounts.values()}) != len(ROLES):
        raise AssertionError("state, inspect, digest and broker UIDs must differ")
    if any(account.pw_uid == 0 for account in accounts.values()):
        raise AssertionError("root cannot be a test principal")
    return accounts


def _status_fields() -> dict[str, str]:
    """Read current process credentials without invoking a privileged action."""
    fields = {}
    for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key] = value.strip()
    return fields


def _attempt_open(path: Path, mode: int) -> None:
    """Opening an existing descriptor without O_CREAT/O_TRUNC makes no edits."""
    fd = os.open(path, mode | getattr(os, "O_NOFOLLOW", 0))
    os.close(fd)


class ExplicitUnqualifiedBaseline(unittest.TestCase):
    def test_same_uid_sqlite_append_only_triggers_are_not_tamper_proof(self):
        """Pure in-memory counterexample; not a live worker isolation test."""
        # sqlite3's context manager commits/rolls back but does not close;
        # explicit closing prevents a Python 3.14 ResourceWarning on finalization.
        with closing(sqlite3.connect(":memory:")) as db, db:
            db.executescript("""
                CREATE TABLE events (seq INTEGER PRIMARY KEY, code TEXT);
                CREATE TRIGGER events_no_delete BEFORE DELETE ON events
                    BEGIN SELECT RAISE(ABORT, 'append only'); END;
                INSERT INTO events VALUES (1, 'ORIGINAL');
            """)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM events WHERE seq=1")
            # The same SQL-writing principal can remove the trigger.
            db.execute("DROP TRIGGER events_no_delete")
            db.execute("DELETE FROM events WHERE seq=1")
            self.assertEqual(db.execute("SELECT count(*) FROM events").fetchone()[0], 0)


@unittest.skipUnless(ENABLED, "HOLD: requires separately authorized real Linux UIDs")
@unittest.skipUnless(os.name == "posix" and Path("/proc/self/status").exists(),
                     "requires a real Linux kernel process")
class ReadOnlyWorkerIsolationQualification(unittest.TestCase):
    """Run separately as EACH enrolled account; role variables are not auth."""

    @classmethod
    def setUpClass(cls):
        cls.accounts = _account_map()
        cls.role = os.environ.get("VERAOS_ISO_ROLE", "")
        if cls.role not in ROLES:
            raise AssertionError("VERAOS_ISO_ROLE must select an enrolled account")
        if os.geteuid() != cls.accounts[cls.role].pw_uid:
            raise AssertionError("effective kernel UID does not match selected role")
        cls.root_text = os.environ.get("VERAOS_ISO_STATE_ROOT", "")
        if not cls.root_text or not Path(cls.root_text).is_absolute():
            raise AssertionError("an exact absolute disposable state path is required")
        cls.root = Path(cls.root_text)
        if cls.root == Path("/") or cls.root.parts[:2] == ("/", "mnt"):
            raise AssertionError("refuse broad or Windows-root test paths")

    def test_kernel_uid_is_not_a_role_string(self):
        self.assertEqual(os.geteuid(), self.accounts[self.role].pw_uid)
        self.assertNotEqual(os.geteuid(), 0)
        self.assertEqual(len({a.pw_uid for a in self.accounts.values()}), 4)

    def test_only_state_owner_may_open_task_db(self):
        db = self.root / "pilot.sqlite3"
        if self.role == "state":
            # The state-owner run is a required positive witness that the
            # supplied fixture exists. No SQLite contents are read.
            _attempt_open(db, os.O_RDONLY)
            self.assertEqual(db.stat().st_uid, os.geteuid())
            return
        for mode in (os.O_RDONLY, os.O_WRONLY):
            with self.subTest(mode=mode):
                try:
                    _attempt_open(db, mode)
                except PermissionError as exc:
                    self.assertIn(exc.errno, (errno.EACCES, errno.EPERM))
                else:
                    self.fail("non-state principal can open the state database")
        # ENOENT and an absent fixture are errors, never a claimed denial.

    def test_inspect_worker_cannot_write_derived_directory(self):
        if self.role != "inspect":
            self.skipTest("inspector-specific negative permission probe")
        derived = self.root / "derived"
        # A missing/inaccessible path cannot establish why a write would
        # fail; the state-owner run must separately attest fixture existence.
        if os.access(derived, os.W_OK):
            self.fail("inspector has ambient derived-output write authority")

    def test_workers_have_no_windows_mount_or_interop_visibility(self):
        if self.role not in ("inspect", "digest"):
            self.skipTest("worker-specific mount namespace probe")
        text = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
        foreign_mounts = []
        for row in text.splitlines():
            if " - " not in row:
                self.fail("unparseable kernel mountinfo")
            detail = row.split(" - ", 1)[1].split()
            if detail and detail[0].lower() in ("drvfs", "9p"):
                foreign_mounts.append(detail[0])
        self.assertFalse(foreign_mounts, "host/shared 9p or DrvFS mount remains visible")
        self.assertFalse(os.environ.get("WSL_INTEROP"), "interop socket environment retained")
        self.assertFalse(os.access("/run/WSL", os.X_OK),
                         "worker can traverse WSL interop socket directory")
        for name in ("cmd.exe", "powershell.exe"):
            path = Path("/mnt/c/Windows/System32") / name
            self.assertFalse(os.access(path, os.X_OK),
                             "worker can execute an ordinary Windows host binary")

    def test_workers_lack_ambient_capabilities_and_privilege_escalation(self):
        if self.role not in ("inspect", "digest"):
            self.skipTest("worker-specific process privilege probe")
        fields = _status_fields()
        self.assertEqual(int(fields["CapEff"], 16), 0)
        self.assertEqual(fields["NoNewPrivs"], "1")
        # Record Seccomp/Landlock/namespace configuration in private evidence;
        # CapEff and NoNewPrivs alone do NOT demonstrate filesystem isolation.


if __name__ == "__main__":
    unittest.main()
