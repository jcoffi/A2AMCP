import asyncio
import importlib.util
import json
import sys
import types
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


class FakeRedisClient:
    def __init__(self):
        self.hashes = {}
        self.lists = {}

    async def hset(self, key, field, value):
        self.hashes.setdefault(key, {})[field] = value
        return 1

    async def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)

    async def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    async def hexists(self, key, field):
        return field in self.hashes.get(key, {})

    async def hdel(self, key, field):
        bucket = self.hashes.get(key, {})
        existed = field in bucket
        bucket.pop(field, None)
        return int(existed)

    async def hkeys(self, key):
        return list(self.hashes.get(key, {}).keys())

    async def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)
        return len(self.lists[key])

    async def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)
        return len(self.lists[key])

    async def lrange(self, key, start, end):
        values = self.lists.get(key, [])
        if end == -1:
            end = len(values) - 1
        return values[start : end + 1]

    async def ltrim(self, key, start, end):
        values = self.lists.get(key, [])
        if end == -1:
            end = len(values) - 1
        self.lists[key] = values[start : end + 1]

    async def delete(self, key):
        existed = key in self.hashes or key in self.lists
        self.hashes.pop(key, None)
        self.lists.pop(key, None)
        return int(existed)


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_mcp_server_module(monkeypatch):
    @dataclass
    class TextContent:
        type: str
        text: str

    @dataclass
    class Tool:
        name: str
        description: str
        inputSchema: dict

    class Server:
        def __init__(self, name):
            self.name = name
            self.list_tools_handler = None
            self.call_tool_handler = None

        def list_tools(self):
            def decorator(func):
                self.list_tools_handler = func
                return func

            return decorator

        def call_tool(self):
            def decorator(func):
                self.call_tool_handler = func
                return func

            return decorator

    @asynccontextmanager
    async def stdio_server():
        yield None, None

    redis_asyncio = types.ModuleType("redis.asyncio")
    redis_asyncio.Redis = FakeRedisClient
    redis_asyncio.from_url = lambda *args, **kwargs: FakeRedisClient()

    redis_module = types.ModuleType("redis")
    redis_module.asyncio = redis_asyncio

    mcp_server_stdio = types.ModuleType("mcp.server.stdio")
    mcp_server_stdio.stdio_server = stdio_server

    mcp_server = types.ModuleType("mcp.server")
    mcp_server.Server = Server
    mcp_server.stdio = mcp_server_stdio

    mcp_types = types.ModuleType("mcp.types")
    mcp_types.Tool = Tool
    mcp_types.TextContent = TextContent

    mcp_module = types.ModuleType("mcp")
    mcp_module.server = mcp_server
    mcp_module.types = mcp_types

    monkeypatch.setitem(sys.modules, "redis", redis_module)
    monkeypatch.setitem(sys.modules, "redis.asyncio", redis_asyncio)
    monkeypatch.setitem(sys.modules, "mcp", mcp_module)
    monkeypatch.setitem(sys.modules, "mcp.server", mcp_server)
    monkeypatch.setitem(sys.modules, "mcp.server.stdio", mcp_server_stdio)
    monkeypatch.setitem(sys.modules, "mcp.types", mcp_types)

    return _load_module(
        "test_mcp_server_redis_module",
        ROOT / "mcp-server-redis.py",
    )


def _make_server(monkeypatch):
    module = _load_mcp_server_module(monkeypatch)
    server = module.AgentCommunicationServer()
    server.redis_client = FakeRedisClient()
    return server


def _call_tool(server, name, arguments):
    async def invoke():
        result = await server.server.call_tool_handler(name, arguments)
        return json.loads(result[0].text)

    return asyncio.run(invoke())


def _register_agent(server, *, project_id, session_name):
    return _call_tool(
        server,
        "register_agent",
        {
            "project_id": project_id,
            "session_name": session_name,
            "task_id": f"task-{session_name}",
            "branch": "current",
            "description": f"agent {session_name}",
        },
    )


class SpyClient:
    def __init__(self, response=None):
        self.response = {} if response is None else response
        self.calls = []

    async def call_tool(self, tool_name, **kwargs):
        self.calls.append((tool_name, kwargs))
        return self.response


class ToolResponseClient:
    def __init__(self, responses=None):
        self.responses = {} if responses is None else responses
        self.calls = []

    async def call_tool(self, tool_name, **kwargs):
        self.calls.append((tool_name, kwargs))
        return self.responses.get(tool_name, {"status": "success", "data": {}})


class DummyProject:
    def __init__(self, client):
        self.project_id = "project-under-test"
        self.client = client


class DummyAgent:
    def __init__(self, client):
        self.session_name = "sender-agent"
        self.project = DummyProject(client)


def _make_communication(response=None):
    core = _load_module(
        "test_a2amcp_core_module", ROOT / "sdk/python/src/a2amcp/core.py"
    )
    client = SpyClient(response=response)
    communication = core.AgentCommunication(DummyAgent(client))
    return communication, client


def test_query_agent_places_query_in_recipient_inbox(monkeypatch):
    server = _make_server(monkeypatch)
    project_id = "project-1"

    _register_agent(server, project_id=project_id, session_name="origin")
    _register_agent(server, project_id=project_id, session_name="recipient")

    query_result = _call_tool(
        server,
        "query_agent",
        {
            "project_id": project_id,
            "session_name": "origin",
            "target_session": "recipient",
            "query": "Can you review the API contract?",
        },
    )

    inbox_result = _call_tool(
        server,
        "check_messages",
        {"project_id": project_id, "session_name": "recipient"},
    )

    messages = inbox_result["data"]["messages"]

    assert query_result["status"] == "success"
    assert len(messages) == 1
    assert messages[0]["id"] == query_result["data"]["query_id"]
    assert messages[0]["from"] == "origin"
    assert messages[0]["query"] == "Can you review the API contract?"


def test_query_agent_accepts_canonical_from_and_to_fields(monkeypatch):
    server = _make_server(monkeypatch)
    project_id = "project-canonical-query"

    _register_agent(server, project_id=project_id, session_name="origin")
    _register_agent(server, project_id=project_id, session_name="recipient")

    query_result = _call_tool(
        server,
        "query_agent",
        {
            "project_id": project_id,
            "from_session": "origin",
            "to_session": "recipient",
            "query_type": "status",
            "query": "Are you ready?",
            "wait_for_response": False,
        },
    )

    inbox_result = _call_tool(
        server,
        "check_messages",
        {"project_id": project_id, "session_name": "recipient"},
    )
    messages = inbox_result["data"]["messages"]

    assert query_result["status"] == "success"
    assert query_result["data"]["status"] == "sent"
    assert len(messages) == 1
    assert messages[0]["from"] == "origin"
    assert messages[0]["to"] == "recipient"
    assert messages[0]["type"] == "query"
    assert messages[0]["query_type"] == "status"
    assert messages[0]["content"] == "Are you ready?"
    assert messages[0]["requires_response"] is True


def test_respond_to_query_delivers_response_back_to_original_sender(monkeypatch):
    server = _make_server(monkeypatch)
    project_id = "project-2"

    _register_agent(server, project_id=project_id, session_name="origin")
    _register_agent(server, project_id=project_id, session_name="recipient")

    query_result = _call_tool(
        server,
        "query_agent",
        {
            "project_id": project_id,
            "session_name": "origin",
            "target_session": "recipient",
            "query": "What is your ETA?",
        },
    )
    query_id = query_result["data"]["query_id"]

    _call_tool(
        server,
        "respond_to_query",
        {
            "project_id": project_id,
            "session_name": "recipient",
            "query_id": query_id,
            "response": "Five minutes.",
        },
    )

    origin_inbox = _call_tool(
        server,
        "check_messages",
        {"project_id": project_id, "session_name": "origin"},
    )
    messages = origin_inbox["data"]["messages"]

    assert len(messages) == 1
    assert messages[0]["from"] == "recipient"
    assert messages[0]["query_id"] == query_id
    assert messages[0]["response"] == "Five minutes."


def test_respond_to_query_accepts_canonical_message_id_and_explicit_recipient(
    monkeypatch,
):
    server = _make_server(monkeypatch)
    project_id = "project-canonical-response"

    _register_agent(server, project_id=project_id, session_name="origin")
    _register_agent(server, project_id=project_id, session_name="recipient")

    response_result = _call_tool(
        server,
        "respond_to_query",
        {
            "project_id": project_id,
            "from_session": "recipient",
            "to_session": "origin",
            "message_id": "query-123",
            "response": "Done.",
        },
    )

    origin_inbox = _call_tool(
        server,
        "check_messages",
        {"project_id": project_id, "session_name": "origin"},
    )
    messages = origin_inbox["data"]["messages"]

    assert response_result["status"] == "success"
    assert response_result["data"]["status"] == "response_sent"
    assert response_result["data"]["to"] == "origin"
    assert response_result["data"]["query_id"] == "query-123"
    assert len(messages) == 1
    assert messages[0]["from"] == "recipient"
    assert messages[0]["to"] == "origin"
    assert messages[0]["type"] == "response"
    assert messages[0]["query_id"] == "query-123"
    assert messages[0]["in_response_to"] == "query-123"
    assert messages[0]["content"] == "Done."
    assert messages[0]["response"] == "Done."


def test_respond_to_query_reports_error_when_delivery_cannot_happen(monkeypatch):
    server = _make_server(monkeypatch)

    _register_agent(server, project_id="project-3", session_name="recipient")

    response = _call_tool(
        server,
        "respond_to_query",
        {
            "project_id": "project-3",
            "session_name": "recipient",
            "query_id": "missing-query-id",
            "response": "No destination should exist for this.",
        },
    )

    assert response["status"] == "error"


def test_broadcast_message_reports_unimplemented_tool(monkeypatch):
    server = _make_server(monkeypatch)
    project_id = "project-broadcast"

    _register_agent(server, project_id=project_id, session_name="origin")
    _register_agent(server, project_id=project_id, session_name="recipient-a")
    _register_agent(server, project_id=project_id, session_name="recipient-b")

    result = _call_tool(
        server,
        "broadcast_message",
        {
            "project_id": project_id,
            "session_name": "origin",
            "message_type": "info",
            "content": "Schema updated.",
        },
    )

    assert result["status"] == "error"
    assert "not yet implemented" in result["message"]


def test_get_all_todos_reports_unimplemented_tool(monkeypatch):
    server = _make_server(monkeypatch)
    project_id = "project-todos"

    _register_agent(server, project_id=project_id, session_name="agent-a")
    _register_agent(server, project_id=project_id, session_name="agent-b")
    _call_tool(
        server,
        "add_todo",
        {
            "project_id": project_id,
            "session_name": "agent-a",
            "task": "Implement API",
            "priority": "high",
        },
    )
    _call_tool(
        server,
        "add_todo",
        {
            "project_id": project_id,
            "session_name": "agent-b",
            "task": "Write docs",
            "priority": "medium",
        },
    )

    result = _call_tool(server, "get_all_todos", {"project_id": project_id})

    assert result["status"] == "error"
    assert "not yet implemented" in result["message"]


def test_project_get_recent_changes_uses_minutes_and_unwraps_changes_payload():
    core = _load_module(
        "test_a2amcp_core_recent_changes_module", ROOT / "sdk/python/src/a2amcp/core.py"
    )
    client = ToolResponseClient(
        {
            "get_recent_changes": {
                "status": "success",
                "data": {
                    "changes": [{"file_path": "src/app.py", "operation": "modify"}]
                },
            }
        }
    )
    project = core.Project(client, "project-recent-changes")

    changes = asyncio.run(project.get_recent_changes(15))

    assert client.calls == [
        (
            "get_recent_changes",
            {"project_id": "project-recent-changes", "minutes": 15},
        )
    ]
    assert changes == [{"file_path": "src/app.py", "operation": "modify"}]


def test_file_coordinator_lock_uses_operation_and_wrapper_success_semantics():
    core = _load_module(
        "test_a2amcp_core_file_lock_module", ROOT / "sdk/python/src/a2amcp/core.py"
    )
    client = ToolResponseClient(
        {
            "announce_file_change": {
                "status": "success",
                "message": "File src/app.py locked for delete",
                "data": {},
            }
        }
    )
    coordinator = core.FileCoordinator(DummyAgent(client))

    asyncio.run(coordinator.lock("src/app.py", change_type="delete"))

    assert client.calls == [
        (
            "announce_file_change",
            {
                "project_id": "project-under-test",
                "session_name": "sender-agent",
                "file_path": "src/app.py",
                "operation": "delete",
            },
        )
    ]


def test_sdk_query_returns_response_text_when_server_marks_query_received():
    communication, _client = _make_communication(
        response={
            "status": "success",
            "data": {
                "status": "received",
                "query_id": "query-1",
                "response": "The contract has been updated.",
            },
        }
    )

    result = asyncio.run(
        communication.query(
            to_session="recipient-agent",
            query_type="status",
            query="Do you have the latest schema?",
            wait_for_response=True,
        )
    )

    assert result == "The contract has been updated."


def test_sdk_respond_raises_when_delivery_fails_instead_of_succeeding_silently():
    core = _load_module(
        "test_a2amcp_core_error_module", ROOT / "sdk/python/src/a2amcp/core.py"
    )
    communication, _client = _make_communication(
        response={
            "status": "error",
            "message": "Could not determine response recipient for query-42",
        }
    )

    with pytest.raises(
        core.A2AMCPError, match="Could not determine response recipient"
    ):
        asyncio.run(
            communication.respond(
                to_session="origin-agent",
                message_id="query-42",
                response="I pushed the interface update.",
            )
        )


def test_sdk_check_messages_returns_message_list_from_tool_payload():
    communication, _client = _make_communication(
        response={
            "status": "success",
            "message": "Retrieved 1 messages",
            "data": {
                "messages": [
                    {
                        "id": "response-query-42",
                        "from": "recipient-agent",
                        "query_id": "query-42",
                        "response": "All set.",
                    }
                ]
            },
        }
    )

    messages = asyncio.run(communication.check_messages())

    assert messages == [
        {
            "id": "response-query-42",
            "from": "recipient-agent",
            "query_id": "query-42",
            "response": "All set.",
        }
    ]
