"""Source-contract characterization of the current WSL peer boundary.

NO cross-UID kernel probe is performed. These AST checks pin the source
preconditions behind the current PRIVATE state-root/socket incompatibility;
the DAC examples are a small mathematical simulation, not proof of a real
WSL/VM ACL, Windows SID mapping, mount namespace, or process isolation.

When a deliberately separate admission socket is implemented, retire the
current-layout characterization and replace it with real different-UID tests.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
PILOT = REPO / "src" / "veraos" / "wsl_pilot.py"
IPC = REPO / "src" / "veraos" / "wsl_ipc.py"


def _function(path: Path, *, name: str, owner: str | None = None) -> ast.AST:
    """Read source, never import or execute the target application."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    scope: ast.AST = tree
    if owner is not None:
        scope = next(node for node in tree.body
                     if isinstance(node, ast.ClassDef) and node.name == owner)
    return next(node for node in scope.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == name)


def _call_matches(node: ast.AST, target: str, *arguments: str,
                  **keywords: str) -> bool:
    if not isinstance(node, ast.Call) or ast.unparse(node.func) != target:
        return False
    if [ast.unparse(arg) for arg in node.args] != list(arguments):
        return False
    return {kw.arg: ast.unparse(kw.value) for kw in node.keywords} == keywords


def _dac_can_search(directory_mode: int, owner_uid: int, caller_uid: int,
                    *, owner_gid: int = 2000, caller_groups: tuple[int, ...] = ()) -> bool:
    """Simplified UNIX DAC execute-bit rule; excludes ACLs/caps/user namespaces."""
    if caller_uid == owner_uid:
        return bool(directory_mode & 0o100)
    if owner_gid in caller_groups:
        return bool(directory_mode & 0o010)
    return bool(directory_mode & 0o001)


def _dac_can_connect(socket_mode: int, owner_uid: int, caller_uid: int,
                     *, owner_gid: int = 2000, caller_groups: tuple[int, ...] = ()) -> bool:
    """Linux stream socket DAC write-bit approximation, not SO_PEERCRED."""
    if caller_uid == owner_uid:
        return bool(socket_mode & 0o200)
    if owner_gid in caller_groups:
        return bool(socket_mode & 0o020)
    return bool(socket_mode & 0o002)


class CurrentSameUIDBoundarySourceContract(unittest.TestCase):
    """Passing these tests documents a limitation, NOT a security success."""

    def test_private_state_root_mode_is_exactly_0700(self):
        init = _function(PILOT, name="init", owner="Pilot")
        calls = (node for node in ast.walk(init) if isinstance(node, ast.Call))
        self.assertTrue(any(_call_matches(call, "root.mkdir", mode="448")
                            for call in calls),
                        "Pilot.init no longer matches the reviewed 0700 root contract")

    def test_socket_path_is_derived_from_that_private_root(self):
        serve = _function(IPC, name="serve")
        assignments = [node for node in ast.walk(serve)
                       if isinstance(node, ast.Assign)
                       and len(node.targets) == 1
                       and isinstance(node.targets[0], ast.Name)
                       and node.targets[0].id == "path"]
        self.assertTrue(any(ast.unparse(node.value) ==
                            "Path(root).absolute() / SOCKET_NAME"
                            for node in assignments),
                        "current same-root socket path changed; reassess isolation")

    def test_socket_mode_is_owner_only_0600(self):
        serve = _function(IPC, name="serve")
        self.assertTrue(any(_call_matches(node, "os.chmod", "path", "384")
                            for node in ast.walk(serve)),
                        "socket permission contract changed; rerun boundary review")

    def test_peer_admission_is_exact_same_uid_not_role_or_sid(self):
        serve = _function(IPC, name="serve")
        self.assertTrue(any(isinstance(node, ast.If) and
                            ast.unparse(node.test) == "_peer_linux_uid(client) != _uid()"
                            for node in ast.walk(serve)),
                        "peer UID rule changed; do not assume reviewed boundary")

    def test_keyed_submission_principal_is_currently_server_uid(self):
        keyed = _function(IPC, name="_submit_keyed")
        self.assertTrue(any(isinstance(node, ast.Assign) and
                            any(isinstance(target, ast.Name) and
                                target.id == "principal" for target in node.targets) and
                            ast.unparse(node.value) == "_uid()"
                            for node in ast.walk(keyed)),
                        "idempotency principal changed; re-review credential binding")

    def test_inspect_and_digest_still_execute_in_one_pilot_process(self):
        run = _function(PILOT, name="_run_with_lease", owner="Pilot")
        calls = {ast.unparse(node.func) for node in ast.walk(run)
                 if isinstance(node, ast.Call)}
        self.assertIn("self._input", calls)
        self.assertIn("self._derive", calls)
        # Absence of these identifiers is only a source observation, not
        # proof a host process could not invoke ambient OS facilities.
        self.assertNotIn("os.setuid", calls)
        self.assertNotIn("os.unshare", calls)

    def test_different_uid_cannot_traverse_even_if_socket_group_is_opened(self):
        state_uid, worker_uid, shared_gid = 1000, 1001, 2000
        # The state directory is 0700. Even making its child socket 0660
        # would NOT let an enrolled group member traverse the parent.
        self.assertFalse(_dac_can_search(0o700, state_uid, worker_uid,
                                         owner_gid=shared_gid,
                                         caller_groups=(shared_gid,)))
        self.assertTrue(_dac_can_connect(0o660, state_uid, worker_uid,
                                         owner_gid=shared_gid,
                                         caller_groups=(shared_gid,)))
        self.assertFalse(_dac_can_connect(0o600, state_uid, worker_uid,
                                          owner_gid=shared_gid,
                                          caller_groups=(shared_gid,)))

    def test_separate_ipc_directory_can_expose_only_transport_not_database(self):
        state_uid, worker_uid, shared_gid = 1000, 1001, 2000
        # This is the PROPOSED separate-directory permission geometry,
        # not a claim that it exists in PR #73 or on Lappy.
        self.assertFalse(_dac_can_search(0o700, state_uid, worker_uid,
                                         owner_gid=shared_gid,
                                         caller_groups=(shared_gid,)))
        self.assertTrue(_dac_can_search(0o750, state_uid, worker_uid,
                                        owner_gid=shared_gid,
                                        caller_groups=(shared_gid,)))
        self.assertTrue(_dac_can_connect(0o660, state_uid, worker_uid,
                                         owner_gid=shared_gid,
                                         caller_groups=(shared_gid,)))
        # An unaffiliated UID gets neither traversal nor socket access.
        self.assertFalse(_dac_can_search(0o750, state_uid, 1002,
                                         owner_gid=shared_gid))
        self.assertFalse(_dac_can_connect(0o660, state_uid, 1002,
                                          owner_gid=shared_gid))


if __name__ == "__main__":
    unittest.main()
