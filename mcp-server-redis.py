#!/usr/bin/env python3
"""
Complete SplitMind Agent Communication MCP Server with Redis Backend
Implements full A2AMCP API specification
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
import redis.asyncio as redis

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("splitmind-mcp")


class AgentCommunicationServer:
    """Complete MCP Server implementing full A2AMCP API with Redis backend"""

    def __init__(self):
        self.server = Server("splitmind-coordination")
        self.redis_client: Optional[redis.Redis] = None
        self._setup_tools()

    async def initialize(self):
        """Initialize Redis connection and wait for readiness"""
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        logger.info(f"Connecting to Redis at: {redis_url}")

        self.redis_client = redis.from_url(redis_url, decode_responses=True)

        # Wait for Redis to be ready
        max_retries = 30
        for i in range(max_retries):
            try:
                await self.redis_client.ping()
                logger.info("Connected to Redis successfully")
                break
            except Exception as e:
                if i < max_retries - 1:
                    logger.info(f"Waiting for Redis... ({i + 1}/{max_retries})")
                    await asyncio.sleep(1)
                else:
                    logger.error(
                        f"Failed to connect to Redis after {max_retries} attempts: {e}"
                    )
                    raise

    async def cleanup(self):
        """Clean up Redis connection"""
        if self.redis_client:
            await self.redis_client.aclose()

    def _get_key(self, project_id: str, *parts: str) -> str:
        """Generate Redis key with proper namespace"""
        return f"splitmind:{project_id}:{':'.join(parts)}"

    def _response(self, status: str, message: str, data: Any = None) -> str:
        """Generate A2AMCP response format"""
        response = {"status": status, "message": message, "data": data or {}}
        return json.dumps(response)

    @staticmethod
    def _first_present(arguments: Dict[str, Any], *names: str) -> Optional[Any]:
        """Return the first non-empty argument value from a list of aliases."""
        for name in names:
            value = arguments.get(name)
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _coerce_bool(value: Any, default: bool = False) -> bool:
        """Coerce tool argument values into booleans."""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _setup_tools(self):
        """Register all MCP tools according to A2AMCP API specification"""

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return [
                # Agent Management
                Tool(
                    name="register_agent",
                    description="Register an agent for a specific project",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "session_name": {"type": "string"},
                            "task_id": {"type": "string"},
                            "branch": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": [
                            "project_id",
                            "session_name",
                            "task_id",
                            "branch",
                            "description",
                        ],
                    },
                ),
                Tool(
                    name="unregister_agent",
                    description="Unregister agent and clean up",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "session_name": {"type": "string"},
                        },
                        "required": ["project_id", "session_name"],
                    },
                ),
                Tool(
                    name="heartbeat",
                    description="Send periodic heartbeat",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "session_name": {"type": "string"},
                        },
                        "required": ["project_id", "session_name"],
                    },
                ),
                Tool(
                    name="list_active_agents",
                    description="List all active agents in a project",
                    inputSchema={
                        "type": "object",
                        "properties": {"project_id": {"type": "string"}},
                        "required": ["project_id"],
                    },
                ),
                # Todo Management
                Tool(
                    name="add_todo",
                    description="Add a todo item",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "session_name": {"type": "string"},
                            "task": {"type": "string"},
                            "priority": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                                "default": "medium",
                            },
                        },
                        "required": ["project_id", "session_name", "task"],
                    },
                ),
                Tool(
                    name="update_todo",
                    description="Update todo status",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "session_name": {"type": "string"},
                            "todo_id": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": [
                                    "pending",
                                    "in_progress",
                                    "completed",
                                    "cancelled",
                                ],
                            },
                        },
                        "required": ["project_id", "session_name", "todo_id", "status"],
                    },
                ),
                Tool(
                    name="get_my_todos",
                    description="Get agent's todos",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "session_name": {"type": "string"},
                        },
                        "required": ["project_id", "session_name"],
                    },
                ),
                # Communication
                Tool(
                    name="query_agent",
                    description="Send query to another agent",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "session_name": {
                                "type": "string",
                                "description": "Legacy alias for from_session",
                            },
                            "from_session": {
                                "type": "string",
                                "description": "Session sending the query",
                            },
                            "target_session": {
                                "type": "string",
                                "description": "Legacy alias for to_session",
                            },
                            "to_session": {
                                "type": "string",
                                "description": "Session receiving the query",
                            },
                            "query_type": {"type": "string", "default": "query"},
                            "query": {"type": "string"},
                            "wait_for_response": {"type": "boolean", "default": False},
                            "timeout": {"type": "integer", "default": 30},
                        },
                        "required": ["project_id", "query"],
                    },
                ),
                Tool(
                    name="check_messages",
                    description="Check and retrieve messages",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "session_name": {"type": "string"},
                        },
                        "required": ["project_id", "session_name"],
                    },
                ),
                Tool(
                    name="respond_to_query",
                    description="Respond to a specific query",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "session_name": {
                                "type": "string",
                                "description": "Legacy alias for from_session",
                            },
                            "from_session": {
                                "type": "string",
                                "description": "Session sending the response",
                            },
                            "to_session": {
                                "type": "string",
                                "description": "Original querying session; inferred from message_id/query_id when omitted",
                            },
                            "query_id": {
                                "type": "string",
                                "description": "Legacy alias for message_id",
                            },
                            "message_id": {
                                "type": "string",
                                "description": "ID of the original query",
                            },
                            "response": {"type": "string"},
                        },
                        "required": ["project_id", "response"],
                    },
                ),
                # File Coordination
                Tool(
                    name="announce_file_change",
                    description="Lock a file before editing",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "session_name": {"type": "string"},
                            "file_path": {"type": "string"},
                            "operation": {
                                "type": "string",
                                "enum": ["create", "modify", "delete"],
                            },
                        },
                        "required": [
                            "project_id",
                            "session_name",
                            "file_path",
                            "operation",
                        ],
                    },
                ),
                Tool(
                    name="release_file_lock",
                    description="Release file lock after editing",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "session_name": {"type": "string"},
                            "file_path": {"type": "string"},
                        },
                        "required": ["project_id", "session_name", "file_path"],
                    },
                ),
                Tool(
                    name="get_recent_changes",
                    description="Get recent file changes",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "minutes": {"type": "integer", "default": 30},
                        },
                        "required": ["project_id"],
                    },
                ),
                # Shared Definitions
                Tool(
                    name="register_interface",
                    description="Share a type/interface definition",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "session_name": {"type": "string"},
                            "name": {"type": "string"},
                            "definition": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": [
                            "project_id",
                            "session_name",
                            "name",
                            "definition",
                        ],
                    },
                ),
                Tool(
                    name="query_interface",
                    description="Get shared interface definition",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "name": {"type": "string"},
                        },
                        "required": ["project_id", "name"],
                    },
                ),
                Tool(
                    name="list_interfaces",
                    description="List all shared interfaces",
                    inputSchema={
                        "type": "object",
                        "properties": {"project_id": {"type": "string"}},
                        "required": ["project_id"],
                    },
                ),
                # Task Completion
                Tool(
                    name="mark_task_completed",
                    description="Mark a task as completed",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "session_name": {"type": "string"},
                            "task_id": {"type": "string"},
                        },
                        "required": ["project_id", "session_name", "task_id"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> List[TextContent]:
            try:
                result = ""

                if name == "register_agent":
                    project_id = arguments["project_id"]
                    session_name = arguments["session_name"]
                    task_id = arguments["task_id"]
                    branch = arguments["branch"]
                    description = arguments["description"]

                    agent_data = {
                        "task_id": task_id,
                        "branch": branch,
                        "description": description,
                        "status": "active",
                        "started_at": datetime.now().isoformat(),
                        "project_id": project_id,
                    }

                    agents_key = self._get_key(project_id, "agents")
                    await self.redis_client.hset(
                        agents_key, session_name, json.dumps(agent_data)
                    )

                    heartbeat_key = self._get_key(project_id, "heartbeat")
                    await self.redis_client.hset(
                        heartbeat_key, session_name, datetime.now().isoformat()
                    )

                    result = self._response(
                        "success",
                        f"Agent {session_name} registered successfully",
                        {"agent_id": session_name, "project_id": project_id},
                    )

                elif name == "unregister_agent":
                    project_id = arguments["project_id"]
                    session_name = arguments["session_name"]

                    # Clean up agent data
                    agents_key = self._get_key(project_id, "agents")
                    await self.redis_client.hdel(agents_key, session_name)

                    heartbeat_key = self._get_key(project_id, "heartbeat")
                    await self.redis_client.hdel(heartbeat_key, session_name)

                    # Clean up todos, messages, file locks
                    todos_key = self._get_key(project_id, "todos", session_name)
                    await self.redis_client.delete(todos_key)

                    messages_key = self._get_key(project_id, "messages", session_name)
                    await self.redis_client.delete(messages_key)

                    result = self._response(
                        "success", f"Agent {session_name} unregistered successfully"
                    )

                elif name == "heartbeat":
                    project_id = arguments["project_id"]
                    session_name = arguments["session_name"]

                    heartbeat_key = self._get_key(project_id, "heartbeat")
                    await self.redis_client.hset(
                        heartbeat_key, session_name, datetime.now().isoformat()
                    )

                    result = self._response("success", "Heartbeat recorded")

                elif name == "list_active_agents":
                    project_id = arguments["project_id"]

                    agents_key = self._get_key(project_id, "agents")
                    agents = await self.redis_client.hgetall(agents_key)

                    active_agents = []
                    for session, data in agents.items():
                        agent_info = json.loads(data)
                        active_agents.append(
                            {
                                "session_name": session,
                                "task_id": agent_info["task_id"],
                                "description": agent_info["description"],
                                "branch": agent_info["branch"],
                            }
                        )

                    result = self._response(
                        "success",
                        f"Found {len(active_agents)} active agents",
                        {"agents": active_agents},
                    )

                elif name == "add_todo":
                    project_id = arguments["project_id"]
                    session_name = arguments["session_name"]
                    task = arguments["task"]
                    priority = arguments.get("priority", "medium")

                    todo_id = f"todo_{int(datetime.now().timestamp() * 1000)}"
                    todo_data = {
                        "id": todo_id,
                        "task": task,
                        "priority": priority,
                        "status": "pending",
                        "created_at": datetime.now().isoformat(),
                    }

                    todos_key = self._get_key(project_id, "todos", session_name)
                    await self.redis_client.hset(
                        todos_key, todo_id, json.dumps(todo_data)
                    )

                    result = self._response(
                        "success", "Todo added successfully", {"todo_id": todo_id}
                    )

                elif name == "update_todo":
                    project_id = arguments["project_id"]
                    session_name = arguments["session_name"]
                    todo_id = arguments["todo_id"]
                    status = arguments["status"]

                    todos_key = self._get_key(project_id, "todos", session_name)
                    todo_data = await self.redis_client.hget(todos_key, todo_id)

                    if todo_data:
                        todo = json.loads(todo_data)
                        todo["status"] = status
                        todo["updated_at"] = datetime.now().isoformat()
                        await self.redis_client.hset(
                            todos_key, todo_id, json.dumps(todo)
                        )
                        result = self._response(
                            "success", f"Todo {todo_id} updated to {status}"
                        )
                    else:
                        result = self._response("error", f"Todo {todo_id} not found")

                elif name == "get_my_todos":
                    project_id = arguments["project_id"]
                    session_name = arguments["session_name"]

                    todos_key = self._get_key(project_id, "todos", session_name)
                    todos = await self.redis_client.hgetall(todos_key)

                    todo_list = []
                    for todo_id, todo_data in todos.items():
                        todo = json.loads(todo_data)
                        todo_list.append(todo)

                    result = self._response(
                        "success",
                        f"Retrieved {len(todo_list)} todos",
                        {"todos": todo_list},
                    )

                elif name == "mark_task_completed":
                    project_id = arguments["project_id"]
                    session_name = arguments["session_name"]
                    task_id = arguments["task_id"]

                    completion_key = self._get_key(project_id, "completed_tasks")
                    completion_data = {
                        "task_id": task_id,
                        "session_name": session_name,
                        "completed_at": datetime.now().isoformat(),
                    }
                    await self.redis_client.hset(
                        completion_key, task_id, json.dumps(completion_data)
                    )

                    result = self._response(
                        "success", f"Task {task_id} marked as completed"
                    )

                elif name == "get_recent_changes":
                    project_id = arguments["project_id"]
                    minutes = arguments.get("minutes", 30)

                    changes_key = self._get_key(project_id, "recent_changes")
                    all_changes = await self.redis_client.lrange(changes_key, 0, -1)

                    cutoff_time = datetime.now() - timedelta(minutes=minutes)
                    recent_changes = []

                    for change_str in all_changes:
                        change = json.loads(change_str)
                        change_time = datetime.fromisoformat(change["timestamp"])
                        if change_time >= cutoff_time:
                            recent_changes.append(change)

                    result = self._response(
                        "success",
                        f"Found {len(recent_changes)} changes in last {minutes} minutes",
                        {"changes": recent_changes},
                    )

                elif name == "query_agent":
                    project_id = arguments["project_id"]
                    session_name = self._first_present(
                        arguments, "from_session", "session_name"
                    )
                    target_session = self._first_present(
                        arguments, "to_session", "target_session"
                    )
                    query = arguments["query"]
                    query_type = arguments.get("query_type", "query")
                    wait_for_response = self._coerce_bool(
                        arguments.get("wait_for_response"), default=False
                    )
                    timeout = int(arguments.get("timeout", 30))

                    if not session_name:
                        result = self._response(
                            "error", "Missing from_session/session_name"
                        )
                    elif not target_session:
                        result = self._response(
                            "error", "Missing to_session/target_session"
                        )
                    else:
                        # Check if target agent exists
                        agents_key = self._get_key(project_id, "agents")
                        if not await self.redis_client.hexists(
                            agents_key, target_session
                        ):
                            result = self._response(
                                "error", f"Agent {target_session} not found"
                            )
                        else:
                            query_id = f"query_{int(datetime.now().timestamp() * 1000)}"
                            query_data = {
                                "id": query_id,
                                "from": session_name,
                                "to": target_session,
                                "type": "query",
                                "query_type": query_type,
                                "content": query,
                                "query": query,
                                "requires_response": True,
                                "timestamp": datetime.now().isoformat(),
                            }

                            queries_key = self._get_key(project_id, "queries")
                            await self.redis_client.hset(
                                queries_key, query_id, json.dumps(query_data)
                            )

                            messages_key = self._get_key(
                                project_id, "messages", target_session
                            )
                            await self.redis_client.rpush(
                                messages_key, json.dumps(query_data)
                            )

                            if wait_for_response:
                                responses_key = self._get_key(project_id, "responses")
                                deadline = datetime.now() + timedelta(seconds=timeout)

                                while datetime.now() < deadline:
                                    response_data = await self.redis_client.hget(
                                        responses_key, query_id
                                    )
                                    if response_data:
                                        await self.redis_client.hdel(
                                            responses_key, query_id
                                        )
                                        parsed_response = json.loads(response_data)
                                        result = self._response(
                                            "success",
                                            f"Response received from {parsed_response['from']}",
                                            {
                                                "status": "received",
                                                "query_id": query_id,
                                                "response": parsed_response["response"],
                                                "response_data": parsed_response,
                                            },
                                        )
                                        break
                                    await asyncio.sleep(0.1)
                                else:
                                    result = self._response(
                                        "success",
                                        f"Timed out waiting for response from {target_session}",
                                        {
                                            "status": "timeout",
                                            "query_id": query_id,
                                        },
                                    )
                            else:
                                result = self._response(
                                    "success",
                                    f"Query sent to {target_session}",
                                    {
                                        "status": "sent",
                                        "query_id": query_id,
                                    },
                                )

                elif name == "check_messages":
                    project_id = arguments["project_id"]
                    session_name = arguments["session_name"]

                    messages_key = self._get_key(project_id, "messages", session_name)
                    if hasattr(self.redis_client, "pipeline"):
                        pipeline = self.redis_client.pipeline(transaction=True)
                        pipeline.lrange(messages_key, 0, -1)
                        pipeline.delete(messages_key)
                        messages, _ = await pipeline.execute()
                    else:
                        messages = await self.redis_client.lrange(messages_key, 0, -1)

                        # Fallback for test doubles without pipeline support.
                        await self.redis_client.delete(messages_key)

                    message_list = []
                    for msg_str in messages:
                        message_list.append(json.loads(msg_str))

                    result = self._response(
                        "success",
                        f"Retrieved {len(message_list)} messages",
                        {"messages": message_list},
                    )

                elif name == "respond_to_query":
                    project_id = arguments["project_id"]
                    session_name = self._first_present(
                        arguments, "from_session", "session_name"
                    )
                    query_id = self._first_present(arguments, "message_id", "query_id")
                    response = arguments["response"]
                    target_session = self._first_present(arguments, "to_session")

                    if not session_name:
                        result = self._response(
                            "error", "Missing from_session/session_name"
                        )
                    elif not query_id:
                        result = self._response("error", "Missing message_id/query_id")
                    else:
                        query_record = None
                        queries_key = self._get_key(project_id, "queries")
                        stored_query = await self.redis_client.hget(
                            queries_key, query_id
                        )
                        if stored_query:
                            query_record = json.loads(stored_query)
                            target_session = target_session or query_record.get("from")

                        if not target_session:
                            result = self._response(
                                "error",
                                f"Could not determine response recipient for {query_id}",
                            )
                        else:
                            response_data = {
                                "id": f"response_{query_id}",
                                "from": session_name,
                                "to": target_session,
                                "type": "response",
                                "response": response,
                                "content": response,
                                "query_id": query_id,
                                "in_response_to": query_id,
                                "timestamp": datetime.now().isoformat(),
                            }

                            messages_key = self._get_key(
                                project_id, "messages", target_session
                            )
                            await self.redis_client.rpush(
                                messages_key, json.dumps(response_data)
                            )

                            responses_key = self._get_key(project_id, "responses")
                            await self.redis_client.hset(
                                responses_key, query_id, json.dumps(response_data)
                            )

                            if stored_query:
                                await self.redis_client.hdel(queries_key, query_id)

                            result = self._response(
                                "success",
                                "Response sent",
                                {
                                    "status": "response_sent",
                                    "response_id": response_data["id"],
                                    "to": target_session,
                                    "query_id": query_id,
                                },
                            )

                elif name == "announce_file_change":
                    project_id = arguments["project_id"]
                    session_name = arguments["session_name"]
                    file_path = arguments["file_path"]
                    operation = arguments["operation"]

                    locks_key = self._get_key(project_id, "file_locks")
                    existing_lock = await self.redis_client.hget(locks_key, file_path)

                    if existing_lock:
                        lock_info = json.loads(existing_lock)
                        if lock_info["session"] != session_name:
                            result = self._response(
                                "error",
                                f"File is locked by {lock_info['session']}",
                                {"lock_info": lock_info},
                            )
                        else:
                            result = self._response(
                                "success", "File already locked by you"
                            )
                    else:
                        lock_data = {
                            "session": session_name,
                            "operation": operation,
                            "locked_at": datetime.now().isoformat(),
                        }
                        await self.redis_client.hset(
                            locks_key, file_path, json.dumps(lock_data)
                        )

                        # Add to recent changes
                        changes_key = self._get_key(project_id, "recent_changes")
                        change_record = {
                            "session": session_name,
                            "file_path": file_path,
                            "operation": operation,
                            "timestamp": datetime.now().isoformat(),
                        }
                        await self.redis_client.lpush(
                            changes_key, json.dumps(change_record)
                        )
                        await self.redis_client.ltrim(
                            changes_key, 0, 99
                        )  # Keep last 100

                        result = self._response(
                            "success", f"File {file_path} locked for {operation}"
                        )

                elif name == "release_file_lock":
                    project_id = arguments["project_id"]
                    session_name = arguments["session_name"]
                    file_path = arguments["file_path"]

                    locks_key = self._get_key(project_id, "file_locks")
                    existing_lock = await self.redis_client.hget(locks_key, file_path)

                    if not existing_lock:
                        result = self._response("error", "File is not locked")
                    else:
                        lock_info = json.loads(existing_lock)
                        if lock_info["session"] != session_name:
                            result = self._response(
                                "error",
                                f"File is locked by {lock_info['session']}, not you",
                            )
                        else:
                            await self.redis_client.hdel(locks_key, file_path)
                            result = self._response(
                                "success", f"File {file_path} lock released"
                            )

                elif name == "register_interface":
                    project_id = arguments["project_id"]
                    session_name = arguments["session_name"]
                    name_param = arguments["name"]
                    definition = arguments["definition"]
                    description = arguments.get("description", "")

                    interfaces_key = self._get_key(project_id, "interfaces")
                    interface_data = {
                        "definition": definition,
                        "description": description,
                        "registered_by": session_name,
                        "timestamp": datetime.now().isoformat(),
                    }

                    await self.redis_client.hset(
                        interfaces_key, name_param, json.dumps(interface_data)
                    )
                    result = self._response(
                        "success", f"Interface {name_param} registered"
                    )

                elif name == "query_interface":
                    project_id = arguments["project_id"]
                    name_param = arguments["name"]

                    interfaces_key = self._get_key(project_id, "interfaces")
                    interface_data = await self.redis_client.hget(
                        interfaces_key, name_param
                    )

                    if interface_data:
                        interface = json.loads(interface_data)
                        result = self._response(
                            "success",
                            f"Found interface {name_param}",
                            {"interface": interface},
                        )
                    else:
                        # Try to find similar names
                        all_interfaces = await self.redis_client.hkeys(interfaces_key)
                        similar = [
                            n for n in all_interfaces if name_param.lower() in n.lower()
                        ]
                        result = self._response(
                            "error",
                            f"Interface {name_param} not found",
                            {"similar": similar},
                        )

                elif name == "list_interfaces":
                    project_id = arguments["project_id"]

                    interfaces_key = self._get_key(project_id, "interfaces")
                    all_interfaces = await self.redis_client.hgetall(interfaces_key)

                    interfaces_list = {}
                    for name, data in all_interfaces.items():
                        interfaces_list[name] = json.loads(data)

                    result = self._response(
                        "success",
                        f"Found {len(interfaces_list)} interfaces",
                        {"interfaces": interfaces_list},
                    )

                else:
                    result = self._response(
                        "error", f"Tool '{name}' not yet implemented"
                    )

                return [TextContent(type="text", text=result)]

            except Exception as e:
                logger.error(f"Error calling tool {name}: {e}")
                error_response = self._response(
                    "error", f"Tool execution failed: {str(e)}"
                )
                return [TextContent(type="text", text=error_response)]

    async def run(self):
        """Run the MCP server"""
        logger.info("Starting Complete SplitMind Agent Communication Server with Redis")

        await self.initialize()

        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options(),
                )
        finally:
            await self.cleanup()


async def run_server():
    """Run the server"""
    server = AgentCommunicationServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(run_server())
