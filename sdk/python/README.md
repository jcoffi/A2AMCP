# A2AMCP Python SDK

Official Python SDK for A2AMCP (Agent-to-Agent Model Context Protocol) - enabling seamless communication between AI agents working on parallel development tasks.

## Features

- **Simple Integration**: Get started with just a few lines of code
- **Automatic Lifecycle Management**: Registration, heartbeats, and cleanup handled automatically
- **Conflict Resolution**: Built-in strategies for handling file conflicts
- **Type Safety**: Full type hints for better IDE support
- **Async/Await**: Modern async Python for efficient operation
- **Prompt Generation**: Intelligent prompt builder for optimal agent instructions

## Installation

```bash
pip install a2amcp
```

## Quick Start

### Basic Agent

```python
import asyncio
from a2amcp import A2AMCPClient, Project, Agent

async def main():
    # Initialize client and project
    client = A2AMCPClient("localhost:5000")
    project = Project(client, "my-project")
    
    # Create and run an agent
    async with Agent(
        project=project,
        task_id="001",
        branch="feature/auth",
        description="Build authentication"
    ) as agent:
        # Add todos
        todo_id = await agent.todos.add("Implement login", priority=1)
        
        # Work with files
        async with agent.files.coordinate("src/auth.py") as file:
            # File is locked
            print(f"Working on {file}")
        # File automatically released
        
        # Mark todo complete
        await agent.todos.complete(todo_id)

asyncio.run(main())
```

### Orchestrator Spawning Agents

```python
from a2amcp import A2AMCPClient, Project, TaskConfig, AgentSpawner

async def spawn_agents():
    client = A2AMCPClient("localhost:5000")
    project = Project(client, "my-app")
    
    tasks = [
        TaskConfig(
            task_id="001",
            branch="feature/auth",
            description="Build authentication",
            shared_interfaces=["User"]
        ),
        TaskConfig(
            task_id="002", 
            branch="feature/profile",
            description="Build user profiles",
            depends_on=["001"]
        )
    ]
    
    spawner = AgentSpawner(project)
    sessions = await spawner.spawn_multiple(tasks, "/path/to/worktrees")
    print(f"Spawned {len(sessions)} agents")
```

### Agent with Message Handling

```python
from a2amcp import Agent

agent = Agent(project, "003", "feature/api", "Build API")

@agent.handles("interface")
async def handle_interface_query(message):
    if "User" in message['content']:
        return "User has: id, email, password, role"

@agent.on("todo_completed") 
async def on_todo_completed(event):
    print(f"Completed: {event['todo']['text']}")

async with agent:
    while True:
        await agent.process_messages()
        await asyncio.sleep(5)
```

## Core Concepts

### Project Context

All operations happen within a project context:

```python
project = Project(client, "project-id")

# Access managers
agents = await project.agents.list()
interfaces = await project.interfaces.list()
todos = await project.todos.get_all()
```

### Agent Lifecycle

Agents automatically handle:
- Registration on startup
- Heartbeats every 30-45 seconds
- Message checking
- Unregistration on shutdown

```python
# Automatic lifecycle management
async with Agent(project, "001", "feature", "description") as agent:
    # Agent is registered and heartbeat is running
    pass
# Agent is automatically unregistered
```

### File Coordination

Prevent conflicts with built-in file locking:

```python
# Simple coordination
async with agent.files.coordinate("src/models.py") as file:
    # File is locked
    pass
# File is released

# Advanced with conflict strategies
await agent.files.lock(
    "src/models.py",
    strategy=ConflictStrategy.WAIT,
    timeout=60
)
```

### Inter-Agent Communication

```python
# Query another agent
response = await agent.communication.query(
    "task-002",
    "interface", 
    "What fields does User have?"
)

# Broadcast to all
await agent.communication.broadcast(
    "info",
    "User model updated with new fields"
)

# Note: this helper expects a server implementation that exposes
# `broadcast_message`. The current Redis MCP server may not provide it.

# Check messages (SDK helper unwraps MCP data.messages for you)
messages = await agent.communication.check_messages()

# Respond to a query message
await agent.communication.respond(
    to_session=messages[0]["from"],
    message_id=messages[0]["id"],
    response="User has id, email, password, role, and timestamps"
)

# Likewise, higher-level helpers for cross-agent todo aggregation may depend on
# tools not exposed by the raw Redis MCP server. Raw MCP callers should prefer
# list_active_agents(...) + get_my_todos(...).
```

### Shared Interfaces

```python
# Register an interface
await project.interfaces.register(
    agent.session_name,
    "User",
    "interface User { id: string; email: string; }",
    "src/types/user.ts"
)

# Require an interface (waits if needed)
user = await project.interfaces.require("User", timeout=60)
```

### Todo Management

```python
# Add todos
todo1 = await agent.todos.add("Design schema", priority=1)
todo2 = await agent.todos.add("Write tests", priority=2)

# Update status
await agent.todos.start(todo1)
await agent.todos.complete(todo1)

# Check all todos in project
all_todos = await project.todos.get_all()
```

## Prompt Generation

Generate optimal prompts for agents:

```python
from a2amcp import PromptBuilder

prompt = PromptBuilder("project-id")\
    .with_task({
        "task_id": "001",
        "branch": "feature/auth",
        "description": "Build authentication",
        "depends_on": ["database"],
        "shared_interfaces": ["User", "Session"]
    })\
    .with_coordination_rules()\
    .with_error_recovery()\
    .add_instruction("Use bcrypt for passwords")\
    .build()
```

## Advanced Features

### Conflict Resolution Strategies

- `WAIT`: Wait for the lock to be released (default)
- `ABORT`: Raise exception immediately on conflict  
- `QUEUE`: Wait in line for the resource
- `NEGOTIATE`: Query the lock owner and negotiate

### Event Handling

```python
@agent.on('file_conflict')
async def handle_conflict(event):
    print(f"Conflict on {event['file']}")

@agent.on('interface_registered')
async def handle_new_interface(event):
    print(f"New interface: {event['name']}")
```

### Project Monitoring

```python
async with project.monitor() as monitor:
    async for event in monitor.events():
        print(f"Event: {event.type} - {event.data}")
```

## Error Handling

```python
from a2amcp import ConflictError, TimeoutError

try:
    await agent.files.lock("src/models.py", strategy=ConflictStrategy.ABORT)
except ConflictError as e:
    print(f"File locked by {e.conflict.agent}")
except TimeoutError:
    print("Could not acquire lock in time")
```

## Complete Examples

See the `examples/` directory for complete examples:

1. Basic agent registration and communication
2. Agent with message handlers
3. Orchestrator spawning multiple agents
4. Conflict resolution strategies
5. Working with shared interfaces
6. Advanced prompt generation
7. Todo-driven development
8. Project monitoring dashboard

## Requirements

- Python 3.8+
- A2AMCP server running (typically at localhost:5000)
- Docker (if using containerized A2AMCP server)

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](https://github.com/webdevtodayjason/A2AMCP/blob/main/CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](https://github.com/webdevtodayjason/A2AMCP/blob/main/LICENSE) for details.

## Links

- [A2AMCP Documentation](https://github.com/webdevtodayjason/A2AMCP)
- [API Reference](https://github.com/webdevtodayjason/A2AMCP/blob/main/API_REFERENCE.md)
- [Examples](https://github.com/webdevtodayjason/A2AMCP/tree/main/sdk/python/examples)

## Support

- GitHub Issues: [github.com/webdevtodayjason/A2AMCP/issues](https://github.com/webdevtodayjason/A2AMCP/issues)
- Discord: [Join our community](https://discord.gg/a2amcp)
