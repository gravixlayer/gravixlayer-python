"""
Tests for runtime type definitions.

Covers: Runtime dataclass, from_api(), create() classmethod, input validation,
Execution wrapper, CodeRunResponse, CommandRunResponse, and all supporting types.
"""

import io
import pytest
from unittest.mock import MagicMock, patch

from gravixlayer.types.runtime import (
    Runtime,
    RuntimeList,
    RuntimeMetrics,
    RuntimeTimeout,
    RuntimeTimeoutResponse,
    RuntimeHostURL,
    RuntimeKillResponse,
    SSHInfo,
    SSHStatus,
    FileReadResponse,
    FileWriteResponse,
    FileInfo,
    FileListResponse,
    FileDeleteResponse,
    DirectoryCreateResponse,
    FileUploadResponse,
    WriteEntry,
    WriteResult,
    WriteFilesResponse,
    CommandRunResponse,
    CodeRunResponse,
    CodeContext,
    CodeContextDeleteResponse,
    ExecutionResult,
    ExecutionError,
    ExecutionLogs,
    Execution,
    Template,
    TemplateList,
    _validate_runtime_id,
    _validate_path,
    _validate_template_id,
)


# ===================================================================
# Input Validation
# ===================================================================


class TestValidateRuntimeId:
    def test_valid_uuid(self):
        _validate_runtime_id("12345678-1234-5678-1234-567812345678")

    def test_valid_uuid_uppercase(self):
        _validate_runtime_id("ABCDEF12-3456-7890-ABCD-EF1234567890")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Invalid runtime_id"):
            _validate_runtime_id("")

    def test_none_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _validate_runtime_id(None)

    def test_short_string_raises(self):
        with pytest.raises(ValueError, match="Invalid runtime_id"):
            _validate_runtime_id("not-a-uuid")

    def test_missing_hyphens_raises(self):
        with pytest.raises(ValueError, match="Invalid runtime_id"):
            _validate_runtime_id("12345678123456781234567812345678")


class TestValidatePath:
    def test_valid_path(self):
        _validate_path("/home/user/file.py")

    def test_relative_path(self):
        _validate_path("file.py")

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            _validate_path("")

    def test_null_bytes_raises(self):
        with pytest.raises(ValueError, match="null bytes"):
            _validate_path("/home/user/file\x00.py")

    def test_traversal_absolute_normalized(self):
        # os.path.normpath resolves /home/../../../etc/passwd to /etc/passwd
        # so the .. is eliminated — this path passes validation.
        _validate_path("/home/../../../etc/passwd")  # normpath removes ..

    def test_relative_dotdot_raises(self):
        with pytest.raises(ValueError, match="traversal"):
            _validate_path("../secret")


class TestValidateTemplateId:
    def test_valid_template_id(self):
        _validate_template_id("python-base-v1")

    def test_valid_uuid(self):
        _validate_template_id("12345678-1234-5678-1234-567812345678")

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            _validate_template_id("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            _validate_template_id("   ")


# ===================================================================
# Runtime Dataclass
# ===================================================================


class TestRuntimeDataclass:
    def test_basic_creation(self):
        rt = Runtime(runtime_id="abc-123", status="running")
        assert rt.runtime_id == "abc-123"
        assert rt.status == "running"
        assert rt.template is None
        assert rt.metadata is None

    def test_from_api(self):
        data = {
            "runtime_id": "uuid-1",
            "status": "running",
            "template": "python-base-v1",
            "cpu_count": 4,
            "memory_mb": 1024,
            "ip_address": "10.0.0.5",
        }
        rt = Runtime.from_api(data)
        assert rt.runtime_id == "uuid-1"
        assert rt.cpu_count == 4
        assert rt.memory_mb == 1024

    def test_from_api_ignores_unknown_fields(self):
        data = {
            "runtime_id": "uuid-2",
            "status": "running",
            "unknown_field": "should_be_ignored",
            "another_unknown": 42,
        }
        rt = Runtime.from_api(data)
        assert rt.runtime_id == "uuid-2"
        assert not hasattr(rt, "unknown_field")

    def test_post_init_sets_internal_state(self):
        rt = Runtime(runtime_id="uuid-3", status="running")
        assert rt._client is None
        assert rt._alive is True
        assert rt._timeout_seconds is None
        assert rt._owns_client is False

    def test_require_alive_no_client_raises(self):
        rt = Runtime(runtime_id="uuid-4", status="running")
        with pytest.raises(RuntimeError, match="Client not initialized"):
            rt._require_alive()

    def test_require_alive_terminated_raises(self):
        rt = Runtime(runtime_id="uuid-5", status="running")
        rt._alive = False
        with pytest.raises(RuntimeError, match="terminated"):
            rt._require_alive()

    def test_known_fields_cached(self):
        fields1 = Runtime._known_fields()
        fields2 = Runtime._known_fields()
        assert fields1 is fields2
        assert "runtime_id" in fields1
        assert "status" in fields1
        assert "_cached_fields" not in fields1

    def test_context_manager(self):
        rt = Runtime(runtime_id="uuid-6", status="running")
        with rt as r:
            assert r is rt

    def test_timeout_property(self):
        rt = Runtime(runtime_id="uuid-7", status="running")
        assert rt.timeout is None
        rt._timeout_seconds = 300
        assert rt.timeout == 300

    def test_show_info_prints(self, capsys):
        rt = Runtime(
            runtime_id="uuid-8", status="running", template="test-tmpl",
            cpu_count=2, memory_mb=512, started_at="2025-01-01T00:00:00Z",
            timeout_at=None,
        )
        rt.show_info()
        captured = capsys.readouterr()
        assert "uuid-8" in captured.out
        assert "test-tmpl" in captured.out
        assert "running" in captured.out


# ===================================================================
# Runtime Instance Methods (with mocked client)
# ===================================================================


class TestRuntimeInstanceMethods:
    def _make_runtime_with_client(self):
        rt = Runtime(runtime_id="12345678-1234-5678-1234-567812345678", status="running")
        mock_client = MagicMock()
        rt._client = mock_client
        return rt, mock_client

    def test_run_code_delegates(self):
        rt, mock_client = self._make_runtime_with_client()
        mock_client.runtime.run_code.return_value = CodeRunResponse(
            results=[ExecutionResult(text="42")],
            logs=ExecutionLogs(),
        )
        result = rt.run_code("print(42)")
        mock_client.runtime.run_code.assert_called_once_with(
            rt.runtime_id, code="print(42)", language="python"
        )
        assert isinstance(result, Execution)
        assert result.text == "42"

    def test_run_cmd_delegates(self):
        rt, mock_client = self._make_runtime_with_client()
        mock_client.runtime.run_cmd.return_value = CommandRunResponse(
            stdout="output", stderr="", exit_code=0, duration_ms=10, success=True
        )
        result = rt.run_cmd("ls -la")
        mock_client.runtime.run_cmd.assert_called_once()
        assert isinstance(result, Execution)
        assert result.stdout == "output"

    def test_run_command_is_alias(self):
        rt, mock_client = self._make_runtime_with_client()
        mock_client.runtime.run_cmd.return_value = CommandRunResponse(
            stdout="ok", stderr="", exit_code=0, duration_ms=5, success=True
        )
        result = rt.run_command("echo hi")
        assert isinstance(result, Execution)

    def test_write_file_delegates(self):
        rt, mock_client = self._make_runtime_with_client()
        rt.write_file("/tmp/test.py", "print('hello')")
        mock_client.runtime.write_file.assert_called_once_with(
            rt.runtime_id, path="/tmp/test.py", content="print('hello')"
        )

    def test_read_file_delegates(self):
        rt, mock_client = self._make_runtime_with_client()
        mock_client.runtime.read_file.return_value = FileReadResponse(content="hello world")
        content = rt.read_file("/tmp/test.txt")
        assert content == "hello world"

    def test_list_files_delegates(self):
        rt, mock_client = self._make_runtime_with_client()
        mock_client.runtime.list_files.return_value = FileListResponse(
            files=[FileInfo(name="file.py", size=100, is_dir=False)]
        )
        files = rt.list_files()
        assert len(files) == 1
        assert files[0].name == "file.py"

    def test_delete_file_delegates(self):
        rt, mock_client = self._make_runtime_with_client()
        rt.delete_file("/tmp/test.py")
        mock_client.runtime.delete_file.assert_called_once()

    def test_kill_marks_not_alive(self):
        rt, mock_client = self._make_runtime_with_client()
        rt.kill()
        assert rt._alive is False
        mock_client.runtime.kill.assert_called_once_with(rt.runtime_id)

    def test_kill_when_already_dead(self):
        rt, mock_client = self._make_runtime_with_client()
        rt._alive = False
        rt.kill()
        mock_client.runtime.kill.assert_not_called()

    def test_is_alive_true(self):
        rt, mock_client = self._make_runtime_with_client()
        mock_client.runtime.get.return_value = Runtime(runtime_id=rt.runtime_id, status="running")
        assert rt.is_alive() is True

    def test_is_alive_false_when_stopped(self):
        rt, mock_client = self._make_runtime_with_client()
        mock_client.runtime.get.return_value = Runtime(runtime_id=rt.runtime_id, status="stopped")
        assert rt.is_alive() is False

    def test_is_alive_false_on_error(self):
        rt, mock_client = self._make_runtime_with_client()
        mock_client.runtime.get.side_effect = Exception("connection lost")
        assert rt.is_alive() is False
        assert rt._alive is False

    def test_enable_ssh_delegates(self):
        rt, mock_client = self._make_runtime_with_client()
        mock_client.runtime.enable_ssh.return_value = SSHInfo(
            runtime_id=rt.runtime_id, enabled=True, port=22, username="user",
            connect_cmd="ssh user@host"
        )
        info = rt.enable_ssh()
        assert info.enabled is True

    def test_disable_ssh_delegates(self):
        rt, mock_client = self._make_runtime_with_client()
        rt.disable_ssh()
        mock_client.runtime.disable_ssh.assert_called_once()

    def test_ssh_status_delegates(self):
        rt, mock_client = self._make_runtime_with_client()
        mock_client.runtime.ssh_status.return_value = SSHStatus(
            runtime_id=rt.runtime_id, enabled=True, port=22, username="user", daemon_running=True
        )
        status = rt.ssh_status()
        assert status.daemon_running is True

    def test_pause_delegates(self):
        rt, mock_client = self._make_runtime_with_client()
        rt.pause()
        mock_client.runtime.pause.assert_called_once_with(rt.runtime_id)

    def test_resume_delegates(self):
        rt, mock_client = self._make_runtime_with_client()
        rt.resume()
        mock_client.runtime.resume.assert_called_once_with(rt.runtime_id)

    def test_write_delegates(self):
        rt, mock_client = self._make_runtime_with_client()
        mock_client.runtime.write.return_value = WriteResult(path="/tmp/f.py", name="f.py", type="file")
        result = rt.write("/tmp/f.py", "content")
        assert result.path == "/tmp/f.py"

    def test_write_files_delegates(self):
        rt, mock_client = self._make_runtime_with_client()
        entries = [WriteEntry(path="/tmp/a.py", data="code")]
        mock_client.runtime.write_files.return_value = WriteFilesResponse(
            files=[WriteResult(path="/tmp/a.py", name="a.py", type="file")],
            partial_failure=False,
        )
        resp = rt.write_files(entries)
        assert len(resp.files) == 1


# ===================================================================
# Execution Wrapper
# ===================================================================


class TestExecution:
    def test_code_execution_properties(self):
        code_resp = CodeRunResponse(
            results=[ExecutionResult(text="42")],
            logs=ExecutionLogs(stdout=["42"], stderr=[]),
            error=None,
        )
        ex = Execution(code_resp)
        assert ex.text == "42"
        assert ex.stdout == "42"
        assert ex.stderr == ""
        assert ex.exit_code == 0
        assert ex.success is True
        assert ex.error is None
        assert len(ex.results) == 1
        assert ex.duration_ms == 0
        assert "code" in repr(ex)

    def test_command_execution_properties(self):
        cmd_resp = CommandRunResponse(
            stdout="hello\nworld", stderr="warn", exit_code=0,
            duration_ms=150, success=True,
        )
        ex = Execution(cmd_resp)
        assert ex.text == "hello\nworld"
        assert ex.stdout == "hello\nworld"
        assert ex.stderr == "warn"
        assert ex.exit_code == 0
        assert ex.success is True
        assert ex.duration_ms == 150
        assert ex.results == []
        assert "command" in repr(ex)

    def test_failed_command(self):
        cmd_resp = CommandRunResponse(
            stdout="", stderr="error: not found", exit_code=1,
            duration_ms=5, success=False, error="command not found"
        )
        ex = Execution(cmd_resp)
        assert ex.success is False
        assert ex.exit_code == 1
        assert ex.error == "command not found"

    def test_code_with_error(self):
        code_resp = CodeRunResponse(
            results=[],
            logs=ExecutionLogs(stdout=[], stderr=["Traceback..."]),
            error=ExecutionError(name="NameError", value="x is not defined", traceback="..."),
        )
        ex = Execution(code_resp)
        assert ex.success is False
        assert ex.error.name == "NameError"

    def test_logs_dict_for_code(self):
        code_resp = CodeRunResponse(
            results=[],
            logs=ExecutionLogs(stdout=["line1", "line2"], stderr=["err1"]),
        )
        ex = Execution(code_resp)
        logs = ex.logs
        assert logs["stdout"] == ["line1", "line2"]
        assert logs["stderr"] == ["err1"]

    def test_logs_dict_for_command(self):
        cmd_resp = CommandRunResponse(
            stdout="line1\nline2", stderr="err", exit_code=0,
            duration_ms=10, success=True,
        )
        ex = Execution(cmd_resp)
        logs = ex.logs
        assert "line1" in logs["stdout"]
        assert "line2" in logs["stdout"]


# ===================================================================
# CodeRunResponse
# ===================================================================


class TestCodeRunResponse:
    def test_from_api_full(self):
        data = {
            "results": [{"text": "hello", "html": "<p>hello</p>"}],
            "logs": {"stdout": ["hello"], "stderr": []},
            "error": None,
        }
        resp = CodeRunResponse.from_api(data)
        assert resp.text == "hello"
        assert resp.success is True
        assert resp.results[0].html == "<p>hello</p>"

    def test_from_api_with_error_dict(self):
        data = {
            "results": [],
            "logs": {"stdout": [], "stderr": ["error"]},
            "error": {"name": "ValueError", "value": "bad", "traceback": "tb"},
        }
        resp = CodeRunResponse.from_api(data)
        assert resp.success is False
        assert resp.error.name == "ValueError"

    def test_from_api_with_error_string(self):
        data = {
            "results": [],
            "logs": {},
            "error": "something went wrong",
        }
        resp = CodeRunResponse.from_api(data)
        assert resp.success is False
        assert resp.error.value == "something went wrong"

    def test_from_api_missing_fields(self):
        data = {}
        resp = CodeRunResponse.from_api(data)
        assert resp.results == []
        assert resp.logs.stdout == []
        assert resp.error is None

    def test_stdout_text_property(self):
        resp = CodeRunResponse(
            results=[],
            logs=ExecutionLogs(stdout=["a", "b", "c"]),
        )
        assert resp.stdout_text == "a\nb\nc"

    def test_stderr_text_property(self):
        resp = CodeRunResponse(
            results=[],
            logs=ExecutionLogs(stderr=["err1", "err2"]),
        )
        assert resp.stderr_text == "err1\nerr2"

    def test_text_property_prefers_result(self):
        resp = CodeRunResponse(
            results=[ExecutionResult(text="from_result")],
            logs=ExecutionLogs(stdout=["from_stdout"]),
        )
        assert resp.text == "from_result"

    def test_text_property_fallback_to_stdout(self):
        resp = CodeRunResponse(
            results=[ExecutionResult(text="")],
            logs=ExecutionLogs(stdout=["fallback"]),
        )
        assert resp.text == "fallback"


# ===================================================================
# Supporting Dataclasses
# ===================================================================


class TestSupportingTypes:
    def test_runtime_list(self):
        rl = RuntimeList(runtimes=[], total=0)
        assert rl.total == 0

    def test_runtime_metrics(self):
        m = RuntimeMetrics(cpu_usage=50.0, memory_usage=256.0, memory_total=512.0)
        assert m.cpu_usage == 50.0

    def test_runtime_timeout(self):
        t = RuntimeTimeout(timeout=300)
        assert t.timeout == 300

    def test_runtime_timeout_response(self):
        r = RuntimeTimeoutResponse(message="Timeout updated", timeout=300, timeout_at="2025-01-01T01:00:00Z")
        assert r.message == "Timeout updated"

    def test_runtime_host_url(self):
        h = RuntimeHostURL(url="https://runtime.example.com:8080")
        assert h.url.startswith("https://")

    def test_runtime_kill_response(self):
        k = RuntimeKillResponse(message="Terminated", runtime_id="uuid-1")
        assert k.message == "Terminated"

    def test_ssh_info(self):
        info = SSHInfo(
            runtime_id="uuid-1", enabled=True, port=22,
            username="user", connect_cmd="ssh user@host",
            private_key="key-data", public_key="pub-data",
        )
        assert info.private_key == "key-data"

    def test_ssh_status(self):
        s = SSHStatus(runtime_id="uuid-1", enabled=True, port=22, username="user", daemon_running=True)
        assert s.daemon_running is True

    def test_file_read_response(self):
        r = FileReadResponse(content="file contents", path="/tmp/f.txt", size=13)
        assert r.content == "file contents"

    def test_file_write_response(self):
        r = FileWriteResponse(message="Written", path="/tmp/f.txt", bytes_written=5)
        assert r.bytes_written == 5

    def test_file_info(self):
        f = FileInfo(name="test.py", size=1024, is_dir=False, modified_at="2025-01-01", mode="0644")
        assert f.name == "test.py"
        assert f.is_dir is False

    def test_directory_create_response(self):
        r = DirectoryCreateResponse(message="Created", path="/tmp/newdir")
        assert r.path == "/tmp/newdir"

    def test_file_upload_response(self):
        r = FileUploadResponse(message="Uploaded", path="/tmp/f.bin", size=2048)
        assert r.size == 2048

    def test_write_entry(self):
        e = WriteEntry(path="/tmp/f.py", data="code", mode=0o755)
        assert e.mode == 0o755

    def test_write_result(self):
        r = WriteResult(path="/tmp/f.py", name="f.py", type="file", size=100)
        assert r.error is None

    def test_write_result_with_error(self):
        r = WriteResult(path="/tmp/f.py", name="f.py", type="file", error="permission denied")
        assert r.error == "permission denied"

    def test_write_files_response(self):
        r = WriteFilesResponse(
            files=[WriteResult(path="/tmp/a", name="a", type="file")],
            partial_failure=False,
        )
        assert len(r.files) == 1
        assert r.partial_failure is False

    def test_code_context(self):
        c = CodeContext(context_id="ctx-1", language="python", cwd="/home/user")
        assert c.context_id == "ctx-1"

    def test_code_context_delete_response(self):
        r = CodeContextDeleteResponse(message="Deleted", context_id="ctx-1")
        assert r.context_id == "ctx-1"

    def test_template(self):
        t = Template(
            id="tmpl-1", name="python-v1", description="Python template",
            vcpu_count=2, memory_mb=512, disk_size_mb=4096,
            visibility="public", created_at="2025-01-01", updated_at="2025-01-01",
        )
        assert t.name == "python-v1"

    def test_template_list(self):
        tl = TemplateList(templates=[], limit=100, offset=0)
        assert tl.limit == 100
