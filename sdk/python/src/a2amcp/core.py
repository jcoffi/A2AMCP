"""
A2AMCP Python SDK - Core Client Library

Provides high-level abstractions for A2AMCP communication.
"""

import asyncio
import builtins
import json
import logging
import os
import subprocess
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class TodoStatus(Enum):
    """Todo item status enumeration"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class MessageType(Enum):
    """Message type enumeration"""

    QUERY = "query"
    BROADCAST = "broadcast"
    RESPONSE = "response"
    EVENT = "event"


class ConflictStrategy(Enum):
    """File conflict resolution strategies"""

    WAIT = "wait"
    QUEUE = "queue"
    ABORT = "abort"
    FORCE = "force"
    NEGOTIATE = "negotiate"


@dataclass
class AgentInfo:
    """Information about an active agent"""

    session_name: str
    task_id: str
    branch: str
    description: str
    status: str
    started_at: str
    project_id: Optional[str] = None


@dataclass
class Todo:
    """Todo item representation"""

    id: str
    text: str
    status: TodoStatus
    priority: int
    created_at: str
    completed_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Todo":
        return cls(
            id=data["id"],
            text=data["text"],
            status=TodoStatus(data["status"]),
            priority=data["priority"],
            created_at=data["created_at"],
            completed_at=data.get("completed_at"),
        )


@dataclass
class FileConflict:
    """File conflict information"""

    file_path: str
    locked_by: str
    locked_at: str
    change_type: str
    description: str

    @property
    def agent(self) -> str:
        """Alias for locked_by"""
        return self.locked_by


@dataclass
class Interface:
    """Shared interface definition"""

    name: str
    definition: str
    registered_by: str
    file_path: Optional[str]
    timestamp: str


if hasattr(builtins, "_A2AMCPError"):
    A2AMCPError = builtins._A2AMCPError
else:

    class A2AMCPError(Exception):
        """Base exception for A2AMCP SDK"""

        pass

    builtins._A2AMCPError = A2AMCPError


class ConnectionError(A2AMCPError):
    """Connection-related errors"""

    pass


class ConflictError(A2AMCPError):
    """File conflict errors"""

    def __init__(self, message: str, conflict: FileConflict):
        super().__init__(message)
        self.conflict = conflict


class TimeoutError(A2AMCPError):
    """Operation timeout errors"""

    pass


class A2AMCPClient:
    """Main client for A2AMCP communication"""

    def __init__(
        self,
        server_url: str = "localhost:5000",
        docker_container: Optional[str] = "a2amcp-server",
    ):
        """
        Initialize A2AMCP client.

        Args:
            server_url: A2AMCP server URL
            docker_container: Docker container name if using Docker
        """
        self.server_url = server_url
        self.docker_container = docker_container
        self._mcp_available = self._check_mcp_availability()

    def _check_mcp_availability(self) -> bool:
        """Check if MCP tools are available"""
        # This would check if we're in an MCP-enabled environment
        # For now, return True for testing
        return True

    def _call_mcp_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Call an MCP tool with given parameters.

        This is a placeholder - in real implementation, this would
        interface with the actual MCP runtime.
        """
        # In real implementation, this would call the MCP tool
        # For now, we'll simulate it
        logger.debug(f"Calling MCP tool: {tool_name} with {kwargs}")

        # Simulate tool call based on tool name
        if tool_name == "register_agent":
            return json.dumps(
                {
                    "status": "registered",
                    "project_id": kwargs["project_id"],
                    "session_name": kwargs["session_name"],
                    "other_active_agents": [],
                    "message": "Successfully registered.",
                }
            )

        # Add other tool simulations as needed
        return json.dumps({"status": "ok"})

    def _parse_response(self, response: str) -> dict:
        """Parse JSON response from MCP tool"""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse response: {response}")
            raise A2AMCPError(f"Invalid response format: {response}")

    async def call_tool(self, tool_name: str, **kwargs) -> dict:
        """
        Async wrapper for MCP tool calls.

        Args:
            tool_name: Name of the MCP tool
            **kwargs: Tool parameters

        Returns:
            Parsed response dictionary
        """
        response = await asyncio.to_thread(self._call_mcp_tool, tool_name, **kwargs)
        return self._parse_response(response)


class Project:
    """Project context for A2AMCP operations"""

    def __init__(self, client: A2AMCPClient, project_id: str):
        """
        Initialize project context.

        Args:
            client: A2AMCP client instance
            project_id: Unique project identifier
        """
        self.client = client
        self.project_id = project_id
        self.agents = AgentManager(self)
        self.interfaces = InterfaceManager(self)
        self.todos = TodoManager(self)

    async def get_active_agents(self) -> Dict[str, AgentInfo]:
        """Get all active agents in the project"""
        response = await self.client.call_tool(
            "list_active_agents", project_id=self.project_id
        )
        AgentCommunication._raise_for_tool_error(response)
        payload = AgentCommunication._payload(response)

        agents = {}
        for data in payload.get("agents", []):
            session_name = data["session_name"]
            agents[session_name] = AgentInfo(
                session_name=session_name,
                task_id=data["task_id"],
                branch=data["branch"],
                description=data["description"],
                status=data.get("status", "active"),
                started_at=data.get("started_at", ""),
                project_id=self.project_id,
            )

        return agents

    async def get_recent_changes(self, limit: int = 20) -> List[dict]:
        """Get recent file changes in the project"""
        response = await self.client.call_tool(
            "get_recent_changes", project_id=self.project_id, minutes=limit
        )
        AgentCommunication._raise_for_tool_error(response)
        payload = AgentCommunication._payload(response)
        changes = payload.get("changes")
        return changes if isinstance(changes, list) else []

    async def broadcast(
        self, from_session: str, message_type: str, content: str
    ) -> int:
        """
        Broadcast a message to all agents.

        Returns:
            Number of recipients
        """
        response = await self.client.call_tool(
            "broadcast_message",
            project_id=self.project_id,
            session_name=from_session,
            message_type=message_type,
            content=content,
        )
        AgentCommunication._raise_for_tool_error(response)
        payload = AgentCommunication._payload(response)
        return payload.get("recipients", 0)

    @asynccontextmanager
    async def monitor(self):
        """Context manager for monitoring project events"""
        monitor = ProjectMonitor(self)
        await monitor.start()
        try:
            yield monitor
        finally:
            await monitor.stop()


class AgentManager:
    """Manages agents within a project"""

    def __init__(self, project: Project):
        self.project = project

    async def list(self) -> Dict[str, AgentInfo]:
        """List all active agents"""
        return await self.project.get_active_agents()

    async def get(self, session_name: str) -> Optional[AgentInfo]:
        """Get a specific agent by session name"""
        agents = await self.list()
        return agents.get(session_name)

    async def find(self, predicate: Callable[[AgentInfo], bool]) -> Optional[AgentInfo]:
        """Find first agent matching predicate"""
        agents = await self.list()
        for agent in agents.values():
            if predicate(agent):
                return agent
        return None

    async def find_all(self, predicate: Callable[[AgentInfo], bool]) -> List[AgentInfo]:
        """Find all agents matching predicate"""
        agents = await self.list()
        return [agent for agent in agents.values() if predicate(agent)]


class InterfaceManager:
    """Manages shared interfaces within a project"""

    def __init__(self, project: Project):
        self.project = project

    async def register(
        self,
        session_name: str,
        name: str,
        definition: str,
        file_path: Optional[str] = None,
    ) -> None:
        """Register a new interface"""
        await self.project.client.call_tool(
            "register_interface",
            project_id=self.project.project_id,
            session_name=session_name,
            name=name,
            definition=definition,
            description=file_path or "",
        )

    async def get(self, name: str) -> Optional[Interface]:
        """Get an interface by name"""
        response = await self.project.client.call_tool(
            "query_interface", project_id=self.project.project_id, name=name
        )

        if response.get("status") == "error":
            return None

        payload = AgentCommunication._payload(response)
        interface = payload.get("interface")
        if not isinstance(interface, dict):
            return None

        return Interface(
            name=name,
            definition=interface["definition"],
            registered_by=interface["registered_by"],
            file_path=interface.get("file_path"),
            timestamp=interface["timestamp"],
        )

    async def list(self) -> Dict[str, Interface]:
        """List all interfaces"""
        response = await self.project.client.call_tool(
            "list_interfaces", project_id=self.project.project_id
        )
        AgentCommunication._raise_for_tool_error(response)
        payload = AgentCommunication._payload(response)

        interfaces = {}
        for name, data in payload.get("interfaces", {}).items():
            interfaces[name] = Interface(
                name=name,
                definition=data["definition"],
                registered_by=data["registered_by"],
                file_path=data.get("file_path"),
                timestamp=data["timestamp"],
            )

        return interfaces

    async def require(self, name: str, timeout: int = 30) -> Interface:
        """
        Require an interface, waiting if necessary.

        Raises:
            TimeoutError: If interface not available within timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            interface = await self.get(name)
            if interface:
                return interface

            await asyncio.sleep(1)

        raise TimeoutError(f"Interface '{name}' not available after {timeout}s")


class TodoManager:
    """Manages todos across all agents in a project"""

    def __init__(self, project: Project):
        self.project = project

    async def get_all(self) -> Dict[str, dict]:
        """Get todos for all agents"""
        response = await self.project.client.call_tool(
            "get_all_todos", project_id=self.project.project_id
        )
        AgentCommunication._raise_for_tool_error(response)
        return AgentCommunication._payload(response)

    async def get_agent_todos(self, session_name: str) -> List[Todo]:
        """Get todos for a specific agent"""
        response = await self.project.client.call_tool(
            "get_my_todos",
            project_id=self.project.project_id,
            session_name=session_name,
        )
        AgentCommunication._raise_for_tool_error(response)
        payload = AgentCommunication._payload(response)

        todos = []
        for todo_data in payload.get("todos", []):
            todos.append(Todo.from_dict(todo_data))

        return todos

    async def find_by_text(self, pattern: str) -> List[tuple[str, Todo]]:
        """Find todos matching text pattern across all agents"""
        all_todos = await self.get_all()
        matches = []

        for agent, data in all_todos.items():
            for todo_data in data.get("todos", []):
                todo = Todo.from_dict(todo_data)
                if pattern.lower() in todo.text.lower():
                    matches.append((agent, todo))

        return matches


class Agent:
    """Represents an A2AMCP agent"""

    def __init__(
        self,
        project: Project,
        task_id: str,
        branch: str,
        description: str,
        session_name: Optional[str] = None,
    ):
        """
        Initialize an agent.

        Args:
            project: Project context
            task_id: Task identifier
            branch: Git branch name
            description: Task description
            session_name: Optional session name (auto-generated if not provided)
        """
        self.project = project
        self.task_id = task_id
        self.branch = branch
        self.description = description
        self.session_name = session_name or f"task-{task_id}"
        self._registered = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._message_handlers: Dict[str, List[Callable]] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
        self.todos = AgentTodoManager(self)
        self.files = FileCoordinator(self)
        self.communication = AgentCommunication(self)

    async def register(self) -> Dict[str, Any]:
        """Register the agent with A2AMCP server"""
        response = await self.project.client.call_tool(
            "register_agent",
            project_id=self.project.project_id,
            session_name=self.session_name,
            task_id=self.task_id,
            branch=self.branch,
            description=self.description,
        )

        self._registered = True

        # Start heartbeat
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        return response

    async def unregister(self) -> Dict[str, Any]:
        """Unregister the agent"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        response = await self.project.client.call_tool(
            "unregister_agent",
            project_id=self.project.project_id,
            session_name=self.session_name,
        )

        self._registered = False
        return response

    async def _heartbeat_loop(self):
        """Send periodic heartbeats"""
        while self._registered:
            try:
                await self.project.client.call_tool(
                    "heartbeat",
                    project_id=self.project.project_id,
                    session_name=self.session_name,
                )
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")
                await asyncio.sleep(5)

    async def __aenter__(self):
        """Async context manager entry"""
        await self.register()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.unregister()

    def on(self, event_type: str):
        """Decorator for event handlers"""

        def decorator(func):
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(func)
            return func

        return decorator

    def handles(self, message_type: str):
        """Decorator for message handlers"""

        def decorator(func):
            if message_type not in self._message_handlers:
                self._message_handlers[message_type] = []
            self._message_handlers[message_type].append(func)
            return func

        return decorator

    async def process_messages(self):
        """Process incoming messages"""
        messages = await self.communication.check_messages()

        for message in messages:
            msg_type = message.get("type", message.get("query_type"))
            handlers = self._message_handlers.get(msg_type, [])

            for handler in handlers:
                try:
                    result = await handler(message)

                    # If it's a query requiring response
                    if message.get("requires_response") and result is not None:
                        await self.communication.respond(
                            to_session=message["from"],
                            message_id=message["id"],
                            response=str(result),
                        )
                except Exception as e:
                    logger.error(f"Message handler error: {e}")


class AgentTodoManager:
    """Manages todos for a specific agent"""

    def __init__(self, agent: Agent):
        self.agent = agent

    async def add(self, text: str, priority: int = 1) -> str:
        """Add a new todo"""
        response = await self.agent.project.client.call_tool(
            "add_todo",
            project_id=self.agent.project.project_id,
            session_name=self.agent.session_name,
            todo_item=text,
            priority=priority,
        )
        return response["todo_id"]

    async def update(self, todo_id: str, status: Union[str, TodoStatus]) -> None:
        """Update todo status"""
        if isinstance(status, TodoStatus):
            status = status.value

        await self.agent.project.client.call_tool(
            "update_todo",
            project_id=self.agent.project.project_id,
            session_name=self.agent.session_name,
            todo_id=todo_id,
            status=status,
        )

    async def list(self) -> List[Todo]:
        """List agent's todos"""
        return await self.agent.project.todos.get_agent_todos(self.agent.session_name)

    async def complete(self, todo_id: str) -> None:
        """Mark todo as completed"""
        await self.update(todo_id, TodoStatus.COMPLETED)

    async def block(self, todo_id: str) -> None:
        """Mark todo as blocked"""
        await self.update(todo_id, TodoStatus.BLOCKED)

    async def start(self, todo_id: str) -> None:
        """Mark todo as in progress"""
        await self.update(todo_id, TodoStatus.IN_PROGRESS)


class FileCoordinator:
    """Coordinates file access for an agent"""

    def __init__(self, agent: Agent):
        self.agent = agent

    async def lock(
        self,
        file_path: str,
        change_type: str = "modify",
        description: str = "",
        strategy: ConflictStrategy = ConflictStrategy.WAIT,
        timeout: int = 60,
    ) -> None:
        """
        Lock a file with conflict resolution.

        Args:
            file_path: Path to the file
            change_type: Type of change (create, modify, delete, refactor)
            description: Description of planned changes
            strategy: Conflict resolution strategy
            timeout: Maximum time to wait for lock

        Raises:
            ConflictError: If file is locked and strategy fails
            TimeoutError: If timeout exceeded
        """
        start_time = time.time()

        while True:
            response = await self.agent.project.client.call_tool(
                "announce_file_change",
                project_id=self.agent.project.project_id,
                session_name=self.agent.session_name,
                file_path=file_path,
                operation=change_type,
            )

            payload = AgentCommunication._payload(response)

            if response["status"] == "success":
                return

            if response["status"] == "error":
                lock_info = payload.get("lock_info", {})
                conflict = FileConflict(
                    file_path=file_path,
                    locked_by=lock_info.get("session", "unknown"),
                    locked_at=lock_info.get("locked_at", ""),
                    change_type=lock_info.get("operation", change_type),
                    description=description,
                )

                if strategy == ConflictStrategy.ABORT:
                    raise ConflictError(f"File {file_path} is locked", conflict)

                elif strategy == ConflictStrategy.FORCE:
                    # In real implementation, might need admin override
                    raise NotImplementedError("Force strategy not yet implemented")

                elif strategy == ConflictStrategy.NEGOTIATE:
                    # Query the other agent
                    response = await self.agent.communication.query(
                        conflict.locked_by,
                        "status",
                        f"When will you be done with {file_path}?",
                    )
                    # Parse response and decide...

                # For WAIT and QUEUE strategies
                if time.time() - start_time > timeout:
                    raise TimeoutError(
                        f"Could not acquire lock on {file_path} after {timeout}s"
                    )

                await asyncio.sleep(5)

    async def release(self, file_path: str) -> None:
        """Release a file lock"""
        response = await self.agent.project.client.call_tool(
            "release_file_lock",
            project_id=self.agent.project.project_id,
            session_name=self.agent.session_name,
            file_path=file_path,
        )
        AgentCommunication._raise_for_tool_error(response)

    @asynccontextmanager
    async def coordinate(
        self,
        file_path: str,
        change_type: str = "modify",
        description: str = "",
        **lock_kwargs,
    ):
        """
        Context manager for file coordination.

        Usage:
            async with agent.files.coordinate('src/models.py') as file:
                # File is locked
                # ... make changes ...
            # File is automatically released
        """
        try:
            await self.lock(file_path, change_type, description, **lock_kwargs)
            yield file_path
        finally:
            await self.release(file_path)


class AgentCommunication:
    """Handles agent communication"""

    def __init__(self, agent: Agent):
        self.agent = agent

    @staticmethod
    def _payload(response: dict) -> dict:
        """Extract the data payload from an MCP tool response."""
        payload = response.get("data")
        return payload if isinstance(payload, dict) else response

    @staticmethod
    def _raise_for_tool_error(response: dict) -> None:
        """Raise when an MCP tool reports an error status."""
        payload = AgentCommunication._payload(response)
        status = payload.get("status", response.get("status"))
        if status == "error":
            raise A2AMCPError(
                response.get("message") or payload.get("message") or "A2AMCP tool error"
            )

    async def query(
        self,
        to_session: str,
        query_type: str,
        query: str,
        wait_for_response: bool = True,
        timeout: int = 30,
    ) -> Optional[str]:
        """Send a query to another agent"""
        response = await self.agent.project.client.call_tool(
            "query_agent",
            project_id=self.agent.project.project_id,
            from_session=self.agent.session_name,
            to_session=to_session,
            query_type=query_type,
            query=query,
            wait_for_response=wait_for_response,
            timeout=timeout,
        )

        self._raise_for_tool_error(response)
        payload = self._payload(response)
        status = payload.get("status", response.get("status"))

        if status == "received":
            return payload.get("response")
        if status == "timeout":
            raise TimeoutError(f"No response from {to_session}")

        return None

    async def broadcast(self, message_type: str, content: str) -> int:
        """Broadcast a message to all agents"""
        return await self.agent.project.broadcast(
            self.agent.session_name, message_type, content
        )

    async def check_messages(self) -> List[dict]:
        """Check for incoming messages"""
        response = await self.agent.project.client.call_tool(
            "check_messages",
            project_id=self.agent.project.project_id,
            session_name=self.agent.session_name,
        )
        self._raise_for_tool_error(response)
        payload = self._payload(response)
        messages = payload.get("messages")
        return messages if isinstance(messages, list) else []

    async def respond(self, to_session: str, message_id: str, response: str) -> None:
        """Respond to a query"""
        tool_response = await self.agent.project.client.call_tool(
            "respond_to_query",
            project_id=self.agent.project.project_id,
            from_session=self.agent.session_name,
            to_session=to_session,
            message_id=message_id,
            response=response,
        )
        self._raise_for_tool_error(tool_response)


class ProjectMonitor:
    """Monitors project events in real-time"""

    def __init__(self, project: Project):
        self.project = project
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start monitoring"""
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop(self):
        """Stop monitoring"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                # In real implementation, this would connect to
                # Redis pub/sub or similar for real-time events
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")

    async def events(self):
        """Async generator for project events"""
        # This would yield real-time events
        # For now, just a placeholder
        while self._running:
            await asyncio.sleep(1)
            # yield Event(...)
