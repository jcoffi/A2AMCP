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


def test_interface_manager_register_surfaces_wrapped_tool_errors():
    core = _load_core_module("test_sdk_core_interface_register_module")
    client = RecordingClient(
        response={
            "status": "error",
            "message": "Interface registration failed",
        }
    )
    project = core.Project(client, "project-under-test")

    with pytest.raises(core.A2AMCPError, match="registration failed"):
        asyncio.run(
            project.interfaces.register(
                "sender-agent", "User", "interface User {}", "models/user.ts"
            )
        )


def test_interface_manager_get_maps_description_back_to_file_path():
    core = _load_core_module("test_sdk_core_interface_get_module")
    client = RecordingClient(
        response={
            "status": "success",
            "message": "Found interface User",
            "data": {
                "interface": {
                    "definition": "interface User {}",
                    "description": "models/user.ts",
                    "registered_by": "sender-agent",
                    "timestamp": "2026-04-09T00:00:00",
                }
            },
        }
    )
    project = core.Project(client, "project-under-test")

    interface = asyncio.run(project.interfaces.get("User"))

    assert interface is not None
    assert interface.file_path == "models/user.ts"


def test_todo_manager_get_agent_todos_parses_server_task_shape():
    core = _load_core_module("test_sdk_core_todo_shape_module")
    client = RecordingClient(
        response={
            "status": "success",
            "message": "Retrieved 1 todos",
            "data": {
                "todos": [
                    {
                        "id": "todo-1",
                        "task": "Implement API",
                        "status": "pending",
                        "priority": "high",
                        "created_at": "2026-04-09T00:00:00",
                    }
                ]
            },
        }
    )
    project = core.Project(client, "project-under-test")

    todos = asyncio.run(project.todos.get_agent_todos("sender-agent"))

    assert len(todos) == 1
    assert todos[0].text == "Implement API"
    assert todos[0].priority == 1


def test_agent_todo_manager_add_uses_task_and_wrapped_todo_id():
    core = _load_core_module("test_sdk_core_agent_todo_add_module")

    def handler(tool_name, kwargs):
        assert tool_name == "add_todo"
        assert kwargs["task"] == "Implement API"
        assert kwargs["priority"] == "medium"
        assert "todo_item" not in kwargs
        return {
            "status": "success",
            "message": "Todo added successfully",
            "data": {"todo_id": "todo-123"},
        }

    client = RecordingClient(handler=handler)
    manager = core.AgentTodoManager(DummyAgent(core, client))

    todo_id = asyncio.run(manager.add("Implement API", priority=2))

    assert todo_id == "todo-123"


def test_agent_todo_manager_update_surfaces_wrapped_tool_errors():
    core = _load_core_module("test_sdk_core_agent_todo_update_module")
    client = RecordingClient(
        response={
            "status": "error",
            "message": "Todo todo-123 not found",
        }
    )
    manager = core.AgentTodoManager(DummyAgent(core, client))

    with pytest.raises(core.A2AMCPError, match="todo-123 not found"):
        asyncio.run(manager.update("todo-123", core.TodoStatus.COMPLETED))


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


def test_file_coordinator_lock_raises_runtime_error_without_conflict_payload():
    core = _load_core_module("test_sdk_core_file_lock_error_module")
    client = RecordingClient(
        response={
            "status": "error",
            "message": "announce_file_change validation failed",
        }
    )
    coordinator = core.FileCoordinator(DummyAgent(core, client))

    with pytest.raises(core.A2AMCPError, match="validation failed"):
        asyncio.run(coordinator.lock("src/main.py", timeout=0.01))
