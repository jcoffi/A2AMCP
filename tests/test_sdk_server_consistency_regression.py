import asyncio
import importlib.util
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_core_module(module_name: str = "test_sdk_core_consistency_module"):
    spec = importlib.util.spec_from_file_location(
        module_name, ROOT / "sdk/python/src/a2amcp/core.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RecordingClient:
    def __init__(self, response=None, handler=None):
        self.response = response
        self.handler = handler
        self.calls = []

    async def call_tool(self, tool_name, **kwargs):
        self.calls.append((tool_name, kwargs))
        if self.handler is not None:
            return self.handler(tool_name, kwargs)
        return self.response


class DummyAgent:
    def __init__(self, core, client):
        self.session_name = "sender-agent"
        self.project = core.Project(client, "project-under-test")
        self.communication = types.SimpleNamespace(query=None)


def test_project_broadcast_surfaces_unsupported_tool_failure():
    core = _load_core_module("test_sdk_core_broadcast_module")
    client = RecordingClient(
        response={
            "status": "error",
            "message": "Tool 'broadcast_message' not yet implemented",
        }
    )
    project = core.Project(client, "project-under-test")

    with pytest.raises(core.A2AMCPError, match="broadcast_message"):
        asyncio.run(project.broadcast("sender-agent", "info", "hello team"))


def test_todo_manager_get_all_surfaces_unsupported_tool_failure():
    core = _load_core_module("test_sdk_core_todos_module")
    client = RecordingClient(
        response={
            "status": "error",
            "message": "Tool 'get_all_todos' not yet implemented",
        }
    )
    project = core.Project(client, "project-under-test")

    with pytest.raises(core.A2AMCPError, match="get_all_todos"):
        asyncio.run(project.todos.get_all())


def test_project_get_recent_changes_uses_minutes_and_unwraps_changes_list():
    core = _load_core_module("test_sdk_core_recent_changes_module")
    client = RecordingClient(
        handler=lambda tool_name, kwargs: {
            "status": "success",
            "message": "Found 1 changes in last 15 minutes",
            "data": {
                "changes": [
                    {
                        "session": "sender-agent",
                        "file_path": "src/main.py",
                        "operation": "modify",
                    }
                ]
            },
        }
    )
    project = core.Project(client, "project-under-test")

    changes = asyncio.run(project.get_recent_changes(15))
    tool_name, kwargs = client.calls[0]

    assert tool_name == "get_recent_changes"
    assert kwargs["project_id"] == "project-under-test"
    assert kwargs["minutes"] == 15
    assert "limit" not in kwargs
    assert changes == [
        {
            "session": "sender-agent",
            "file_path": "src/main.py",
            "operation": "modify",
        }
    ]


def test_file_coordinator_lock_uses_operation_schema_and_wrapped_success():
    core = _load_core_module("test_sdk_core_file_lock_module")

    def handler(tool_name, kwargs):
        assert tool_name == "announce_file_change"
        assert kwargs["project_id"] == "project-under-test"
        assert kwargs["session_name"] == "sender-agent"
        assert kwargs["file_path"] == "src/main.py"
        assert kwargs["operation"] == "modify"
        assert "change_type" not in kwargs
        assert "description" not in kwargs
        return {
            "status": "success",
            "message": "File src/main.py locked for modify",
            "data": {},
        }

    client = RecordingClient(handler=handler)
    coordinator = core.FileCoordinator(DummyAgent(core, client))

    asyncio.run(
        asyncio.wait_for(coordinator.lock("src/main.py", timeout=0.01), timeout=0.05)
    )


def test_file_coordinator_release_surfaces_wrapped_runtime_error():
    core = _load_core_module("test_sdk_core_file_release_module")
    client = RecordingClient(
        response={
            "status": "error",
            "message": "File is locked by other-agent, not you",
        }
    )
    coordinator = core.FileCoordinator(DummyAgent(core, client))

    with pytest.raises(core.A2AMCPError, match="locked by other-agent"):
        asyncio.run(coordinator.release("src/main.py"))
