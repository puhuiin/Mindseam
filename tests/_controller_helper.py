import io
import os
import shutil
import sys
import importlib.util
from pathlib import Path

# Bootstrap the controller's import path here, not in each importer:
# this helper is the one module that needs both ``verify_suite`` and
# ``mindseam``, and relying on whichever test file happens to import
# first to have inserted the path broke collection the moment a
# lexicographically-earlier file (test_history_*, test_info_*) picked
# the helper up. A duplicate insert is harmless to importers that
# bootstrap themselves.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mindseam" / "scripts"))
import verify_suite


def _clear_mindseam(workspace):
    mindseam_dir = os.path.join(workspace, ".mindseam")
    if os.path.isdir(mindseam_dir):
        for name in os.listdir(mindseam_dir):
            p = os.path.join(mindseam_dir, name)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                os.remove(p)


def run_controller(workspace, *args, stdin=None):
    return _RunControllerResult.call(workspace, *args, stdin=stdin)


def invoke_cli(workspace, args, stdin=None, env=None, drop_env=()):
    """Run the controller in-process, returning a subprocess.run-shaped result.

    Drop-in for the per-file ``_invoke`` wrappers: same ``returncode`` /
    ``stdout`` / ``stderr`` attributes, no child process. A real spawn costs
    ~400 ms, nearly all of it interpreter startup plus the 9k-line module
    import, and the suite was spending ~99% of its wall time waiting on
    children that do ~30 ms of actual work. The child boundary itself is
    still covered end-to-end by the tests that need it -- r128 pins
    verify_suite's own subprocess encoding, and the from-stdin baseline
    exercises the real stdin pipe.

    ``drop_env`` / ``env`` reproduce the environment the old helpers built:
    the intensity overrides start from a clean ``MINDSEAM_INTENSITY`` so a
    value leaking in from the outer shell cannot change a test's default.
    """
    saved = {}

    def _stage(key, value):
        if key not in saved:
            saved[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    try:
        for key in drop_env:
            _stage(key, None)
        for key, value in (env or {}).items():
            _stage(key, value)
        return run_controller(workspace, *args, stdin=stdin)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run_verify_suite(repo_path):
    repo_path = Path(repo_path)
    verify_suite.find_repo()
    old_pass, old_fail = verify_suite.PASS, verify_suite.FAIL
    verify_suite.PASS = 0
    verify_suite.FAIL = 0

    script_path = repo_path / "scripts" / "mindseam.py"
    spec = importlib.util.spec_from_file_location("mindseam_copied", str(script_path))
    mindseam_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mindseam_mod)

    old_out, old_err = sys.stdout, sys.stderr
    out_buf, err_buf = io.StringIO(), io.StringIO()
    sys.stdout, sys.stderr = out_buf, err_buf
    rc = 0
    try:
        verify_suite.check_integrity(mindseam_mod, repo_path)
        if verify_suite.FAIL:
            rc = 1
    except SystemExit as exc:
        rc = exc.code if isinstance(exc.code, int) else (2 if exc.code else 0)
    finally:
        sys.stdout, sys.stderr = old_out, old_err
        verify_suite.PASS, verify_suite.FAIL = old_pass, old_fail

    return rc, out_buf.getvalue(), err_buf.getvalue()


class _RunControllerResult:
    @staticmethod
    def call(workspace, *args, stdin=None):
        original = os.getcwd()
        prev_stdin = sys.stdin
        prev_out, prev_err = sys.stdout, sys.stderr
        out_buf, err_buf = [], []
        try:
            os.chdir(workspace)
            if stdin is not None:
                sys.stdin = io.StringIO(stdin)
            sys.stdout = _Tee(out_buf)
            sys.stderr = _Tee(err_buf)
            import mindseam
            try:
                rc = mindseam.main([*args])
            except SystemExit as exc:
                rc = exc.code if isinstance(exc.code, int) else (2 if exc.code else 0)
        finally:
            sys.stdout, sys.stderr = prev_out, prev_err
            sys.stdin = prev_stdin
            os.chdir(original)
        return _ControllerNamespace(rc, "".join(out_buf), "".join(err_buf))

    @staticmethod
    def call_bytes(workspace, *args, stdin=None):
        original = os.getcwd()
        prev_stdin = sys.stdin.buffer if hasattr(sys.stdin, "buffer") else sys.stdin
        prev_out, prev_err = sys.stdout, sys.stderr
        out_buf, err_buf = [], []
        try:
            os.chdir(workspace)
            if isinstance(stdin, bytes):
                sys.stdin = io.TextIOWrapper(io.BytesIO(stdin), encoding="utf-8")
            sys.stdout = _Tee(out_buf)
            sys.stderr = _Tee(err_buf)
            import mindseam
            rc = mindseam.main([*args])
        finally:
            sys.stdout, sys.stderr = prev_out, prev_err
            sys.stdin = prev_stdin
            os.chdir(original)
        return _ControllerBytesNamespace(rc, "".join(out_buf).encode(), "".join(err_buf).encode())


class _Tee:
    def __init__(self, buf):
        self._buf = buf
        self._buf.append("")

    def write(self, data):
        self._buf[0] += data

    def flush(self):
        pass


class _ControllerNamespace:
    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _ControllerBytesNamespace:
    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
