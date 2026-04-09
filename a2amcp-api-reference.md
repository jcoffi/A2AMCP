# A2AMCP API Reference

## Table of Contents

1. [Overview](#overview)
2. [Core Concepts](#core-concepts)
3. [API Methods](#api-methods)
   - [Agent Management](#agent-management)
   - [Todo List Management](#todo-list-management)
   - [Communication](#communication)
   - [File Coordination](#file-coordination)
   - [Shared Definitions](#shared-definitions)
4. [Complete Examples](#complete-examples)
5. [Error Handling](#error-handling)
6. [Best Practices](#best-practices)

## Overview

A2AMCP provides MCP (Model Context Protocol) tools that AI agents use to communicate and coordinate. All methods follow a consistent pattern:

```python
tool_name(project_id: str, ...other_parameters) -> str
```

All responses are JSON-encoded strings containing status information and requested data.

## Core Concepts

### Project ID
Every API call requires a `project_id` to ensure isolation between different projects using the same A2AMCP server.

### Session Name
Each agent has a unique session name, typically formatted as `task-{task_id}` (e.g., `task-001`, `task-auth-123`).

### Response Format
All methods return JSON-encoded strings with at least a `status` field:
```json
{
  "status": "success|error|timeout|...",
  "message": "Human-readable message",
  "data": { ... }
}
```

## API Methods

### Agent Management

#### `register_agent`

Registers an agent with the A2AMCP server. This must be the first call made by any agent.

**Parameters:**
- `project_id` (str): Unique project identifier
- `session_name` (str): Unique session name for this agent
- `task_id` (str): Task identifier
- `branch` (str): Git branch name
- `description` (str): Brief description of the task

**Returns:**
```json
{
  "status": "registered",
  "project_id": "ecommerce-v2",
  "session_name": "task-001",
  "other_active_agents": ["task-002", "task-003"],
  "message": "Successfully registered. 2 other agents are active in this project."
}
```

**Example:**
```python
register_agent(
    "ecommerce-v2",
    "task-auth-001",
    "001",
    "feature/authentication",
    "Implement user authentication with JWT tokens"
)
```

---

#### `heartbeat`

Sends a keep-alive signal. Must be called every 30-60 seconds or the agent will be considered dead and cleaned up.

**Parameters:**
- `project_id` (str): Project identifier
- `session_name` (str): Agent's session name

**Returns:**
```json
{
  "status": "ok",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Example:**
```python
# In your agent's main loop
import time
while working:
    heartbeat("ecommerce-v2", "task-auth-001")
    time.sleep(30)
```

---

#### `list_active_agents`

Gets all currently active agents in the project.

**Parameters:**
- `project_id` (str): Project identifier

**Returns:**
```json
{
  "task-auth-001": {
    "task_id": "001",
    "branch": "feature/authentication",
    "description": "Implement user authentication with JWT tokens",
    "status": "active",
    "started_at": "2024-01-15T10:00:00Z"
  },
  "task-profile-002": {
    "task_id": "002",
    "branch": "feature/user-profiles",
    "description": "Create user profile management",
    "status": "active",
    "started_at": "2024-01-15T10:05:00Z"
  }
}
```

**Example:**
```python
agents = list_active_agents("ecommerce-v2")
print(f"Active agents: {len(agents)}")
for session, info in agents.items():
    print(f"  {session}: {info['description']}")
```

---

#### `unregister_agent`

Unregisters an agent when its task is complete. Shows todo completion summary.

**Parameters:**
- `project_id` (str): Project identifier
- `session_name` (str): Agent's session name

**Returns:**
```json
{
  "status": "unregistered",
  "todo_summary": {
    "total": 5,
    "completed": 4,
    "pending": 1,
    "in_progress": 0
  },
  "message": "Successfully unregistered. Completed 4/5 todos."
}
```

**Example:**
```python
# When agent completes its task
result = unregister_agent("ecommerce-v2", "task-auth-001")
print(f"Task complete: {result['message']}")
```

### Todo List Management

#### `add_todo`

Adds a todo item to the agent's task breakdown.

**Parameters:**
- `project_id` (str): Project identifier
- `session_name` (str): Agent's session name
- `todo_item` (str): Description of the todo
- `priority` (int): Priority level (1=high, 2=medium, 3=low)

**Returns:**
```json
{
  "status": "added",
  "todo_id": "todo-1705320600.123",
  "message": "Added todo: Research JWT libraries"
}
```

**Example:**
```python
# Break down your task into todos
add_todo("ecommerce-v2", "task-auth-001", "Research JWT best practices", 1)
add_todo("ecommerce-v2", "task-auth-001", "Design User database schema", 1)
add_todo("ecommerce-v2", "task-auth-001", "Implement password hashing", 1)
add_todo("ecommerce-v2", "task-auth-001", "Create login endpoint", 2)
add_todo("ecommerce-v2", "task-auth-001", "Write authentication tests", 2)
```

---

#### `update_todo`

Updates the status of a todo item.

**Parameters:**
- `project_id` (str): Project identifier
- `session_name` (str): Agent's session name
- `todo_id` (str): ID of the todo to update
- `status` (str): New status (`pending`, `in_progress`, `completed`, `blocked`)

**Returns:**
```json
{
  "status": "updated",
  "todo_id": "todo-1705320600.123",
  "new_status": "completed"
}
```

**Example:**
```python
# Start working on a todo
update_todo("ecommerce-v2", "task-auth-001", "todo-1705320600.123", "in_progress")

# Complete it
update_todo("ecommerce-v2", "task-auth-001", "todo-1705320600.123", "completed")

# Mark as blocked if waiting for another agent
update_todo("ecommerce-v2", "task-auth-001", "todo-1705320600.456", "blocked")
```

---

#### `get_my_todos`

Gets all todos for the current agent.

**Parameters:**
- `project_id` (str): Project identifier
- `session_name` (str): Agent's session name

**Returns:**
```json
{
  "session_name": "task-auth-001",
  "total": 5,
  "todos": [
    {
      "id": "todo-1705320600.123",
      "text": "Research JWT best practices",
      "status": "completed",
      "priority": 1,
      "created_at": "2024-01-15T10:00:00Z",
      "completed_at": "2024-01-15T10:30:00Z"
    },
    {
      "id": "todo-1705320600.456",
      "text": "Design User database schema",
      "status": "in_progress",
      "priority": 1,
      "created_at": "2024-01-15T10:00:00Z",
      "completed_at": null
    }
  ]
}
```

---

#### `get_all_todos`

`get_all_todos` is useful conceptually for coordination, but it is **not currently exposed by the Redis MCP server** in `mcp-server-redis.py`.

For raw MCP callers using the current Redis server, use this pattern instead:

```python
agents_result = list_active_agents("ecommerce-v2")
for agent in agents_result["data"]["agents"]:
    todos_result = get_my_todos("ecommerce-v2", agent["session_name"])
    todos = todos_result["data"]["todos"]
    print(agent["session_name"], len(todos))
```

### Communication

#### `query_agent`

Sends a query to another agent and optionally waits for a response.

**Parameters:**
- `project_id` (str): Project identifier
- `from_session` (str): Your session name
- `session_name` (str): Legacy alias for `from_session`
- `to_session` (str): Target agent's session name
- `target_session` (str): Legacy alias for `to_session`
- `query_type` (str): Type of query (e.g., "interface", "help", "status"). Defaults to `query`
- `query` (str): The actual question
- `wait_for_response` (bool): Whether to wait for response (default: False)
- `timeout` (int): Seconds to wait for response (default: 30)

**Returns:**
```json
{
  "status": "success",
  "message": "Response received from task-auth-001",
  "data": {
    "status": "received",
    "query_id": "query_1711638123456",
    "response": "The User interface has id, email, password, and role fields",
    "response_data": {
      "id": "response_query_1711638123456",
      "from": "task-auth-001",
      "to": "task-profile-002",
      "type": "response",
      "response": "The User interface has id, email, password, and role fields",
      "content": "The User interface has id, email, password, and role fields",
      "query_id": "query_1711638123456",
      "in_response_to": "query_1711638123456",
      "timestamp": "2024-01-15T10:31:00Z"
    }
  }
}
```

If `wait_for_response=False`, the tool still returns the same MCP wrapper, but `data.status` is `sent` and `data.query_id` is the correlation field.

**Example:**
```python
# Ask about an interface
response = query_agent(
    project_id="ecommerce-v2",
    from_session="task-profile-002",
    to_session="task-auth-001",
    query_type="interface",
    query="What fields does the User interface have? I need to extend it for profiles.",
    wait_for_response=True
)

# Ask for help
response = query_agent(
    project_id="ecommerce-v2",
    from_session="task-frontend-003",
    to_session="task-auth-001",
    query_type="help",
    query="How should I handle authentication tokens in the frontend?",
    wait_for_response=True,
    timeout=60  # Give more time for complex questions
)
```

---

#### `check_messages`

Checks for any messages sent to this agent. Clears the queue after reading.

**Parameters:**
- `project_id` (str): Project identifier
- `session_name` (str): Agent's session name

**Returns:**
```json
{
  "status": "success",
  "message": "Retrieved 2 messages",
  "data": {
    "messages": [
      {
        "id": "query_1711638123456",
        "from": "task-profile-002",
        "to": "task-auth-001",
        "type": "query",
        "query_type": "interface",
        "content": "What fields does the User interface have?",
        "query": "What fields does the User interface have?",
        "requires_response": true,
        "timestamp": "2024-01-15T10:30:00Z"
      },
      {
        "id": "response_query_1711638123456",
        "from": "task-auth-001",
        "to": "task-profile-002",
        "type": "response",
        "response": "User has: id, email, password, role, createdAt",
        "content": "User has: id, email, password, role, createdAt",
        "query_id": "query_1711638123456",
        "in_response_to": "query_1711638123456",
        "timestamp": "2024-01-15T10:31:00Z"
      }
    ]
  }
}
```

**Example:**
```python
# Check messages periodically
result = check_messages("ecommerce-v2", "task-auth-001")
messages = result["data"]["messages"]
for msg in messages:
    if msg['type'] == 'query' and msg.get('requires_response'):
        # Respond to the query
        if 'User interface' in msg['content']:
            respond_to_query(
                project_id="ecommerce-v2",
                from_session="task-auth-001",
                to_session=msg['from'],
                message_id=msg['id'],
                response="User has: id (string), email (string), password (hashed), role (string), createdAt (Date)"
            )
```

---

#### `respond_to_query`

Responds to a query from another agent.

**Parameters:**
- `project_id` (str): Project identifier
- `from_session` (str): Your session name
- `session_name` (str): Legacy alias for `from_session`
- `to_session` (str): Session that sent the query. Optional when it can be inferred from the stored query record.
- `message_id` (str): ID of the original query
- `query_id` (str): Legacy alias for `message_id`
- `response` (str): Your response

**Returns:**
```json
{
  "status": "success",
  "message": "Response sent",
  "data": {
    "status": "response_sent",
    "response_id": "response_query_1711638123456",
    "to": "task-profile-002",
    "query_id": "query_1711638123456"
  }
}
```

---

#### `broadcast_message`

`broadcast_message` appears in older design examples, but it is **not exposed by the current Redis MCP server** in `mcp-server-redis.py`.

If you are documenting or using the raw MCP toolset, treat this as unavailable unless the server implementation adds it. Use directed `query_agent(...)` calls instead.

### File Coordination

#### `announce_file_change`

Announces intention to modify a file. Prevents conflicts by locking the file.

**Parameters:**
- `project_id` (str): Project identifier
- `session_name` (str): Agent's session name
- `file_path` (str): Path to the file
- `operation` (str): Type of change ("create", "modify", "delete")

**Returns (success):**
```json
{
  "status": "success",
  "message": "File src/models/user.ts locked for create",
  "data": {}
}
```

**Returns (conflict):**
```json
{
  "status": "error",
  "message": "File is locked by task-profile-002",
  "data": {
    "lock_info": {
      "session": "task-profile-002",
      "operation": "modify",
      "locked_at": "2024-01-15T10:30:00Z"
    }
  },
}
```

**Example:**
```python
# Before modifying a file
result = announce_file_change(
    "ecommerce-v2",
    "task-auth-001",
    "src/models/user.ts",
    "create"
)

if result['status'] == 'error':
    # File is locked by another agent
    other_agent = result['data']['lock_info']['session']
    # Query them about timeline
    response = query_agent(
        project_id="ecommerce-v2",
        from_session="task-auth-001",
        to_session=other_agent,
        query_type="status",
        query=f"When will you be done with src/models/user.ts? I need to add auth fields.",
        wait_for_response=True
    )
else:
    # File is locked, safe to modify
    # ... do your work ...
    # Then release the lock
    release_file_lock("ecommerce-v2", "task-auth-001", "src/models/user.ts")
```

---

#### `release_file_lock`

Releases a file lock after completing changes.

**Parameters:**
- `project_id` (str): Project identifier
- `session_name` (str): Agent's session name
- `file_path` (str): Path to the file

**Returns:**
```json
{
  "status": "released",
  "file_path": "src/models/user.ts"
}
```

---

#### `get_recent_changes`

Gets recent file changes across all agents in the project.

**Parameters:**
- `project_id` (str): Project identifier
- `minutes` (int): Look back window in minutes (default: 30)

**Returns:**
```json
{
  "status": "success",
  "message": "Found 2 changes in last 30 minutes",
  "data": {
    "changes": [
      {
        "session": "task-auth-001",
        "file_path": "src/models/user.ts",
        "operation": "create",
        "timestamp": "2024-01-15T10:45:00Z"
      },
      {
        "session": "task-api-003",
        "file_path": "src/routes/auth.ts",
        "operation": "create",
        "timestamp": "2024-01-15T10:40:00Z"
      }
    ]
  }
}
```

**Example:**
```python
# Check what files were recently modified
result = get_recent_changes("ecommerce-v2", minutes=10)
changes = result["data"]["changes"]
for change in changes:
    print(f"{change['session']} {change['operation']} {change['file_path']}")
```

### Shared Definitions

#### `register_interface`

Registers a shared interface or type definition that other agents can use.

**Parameters:**
- `project_id` (str): Project identifier
- `session_name` (str): Agent's session name
- `interface_name` (str): Name of the interface/type
- `definition` (str): The complete definition
- `file_path` (str, optional): Where this interface is defined

**Returns:**
```json
{
  "status": "registered",
  "interface_name": "User",
  "message": "Interface registered and available to all agents"
}
```

**Example:**
```python
# After creating a TypeScript interface
register_interface(
    "ecommerce-v2",
    "task-auth-001",
    "User",
    """interface User {
  id: string;
  email: string;
  password: string;
  role: 'admin' | 'user' | 'guest';
  createdAt: Date;
  updatedAt: Date;
}""",
    "src/types/user.ts"
)

# Register a type
register_interface(
    "ecommerce-v2",
    "task-auth-001",
    "UserRole",
    "type UserRole = 'admin' | 'user' | 'guest';",
    "src/types/user.ts"
)

# Register an API response type
register_interface(
    "ecommerce-v2",
    "task-api-003",
    "LoginResponse",
    """interface LoginResponse {
  user: User;
  token: string;
  expiresIn: number;
}""",
    "src/types/api.ts"
)
```

---

#### `query_interface`

Gets a registered interface definition.

**Parameters:**
- `project_id` (str): Project identifier
- `interface_name` (str): Name of the interface to query

**Returns (found):**
```json
{
  "definition": "interface User { id: string; email: string; ... }",
  "registered_by": "task-auth-001",
  "file_path": "src/types/user.ts",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Returns (not found):**
```json
{
  "status": "not_found",
  "error": "Interface User not found",
  "similar": ["UserProfile", "UserRole"]
}
```

**Example:**
```python
# Get an interface definition
user_interface = query_interface("ecommerce-v2", "User")
if user_interface.get('status') != 'not_found':
    print(f"User interface: {user_interface['definition']}")
    print(f"Defined in: {user_interface['file_path']}")
else:
    # Interface doesn't exist yet
    similar = user_interface.get('similar', [])
    if similar:
        print(f"Did you mean: {', '.join(similar)}?")
```

---

#### `list_interfaces`

Lists all registered interfaces in the project.

**Parameters:**
- `project_id` (str): Project identifier

**Returns:**
```json
{
  "User": {
    "definition": "interface User { ... }",
    "registered_by": "task-auth-001",
    "file_path": "src/types/user.ts",
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "UserProfile": {
    "definition": "interface UserProfile extends User { ... }",
    "registered_by": "task-profile-002",
    "file_path": "src/types/profile.ts",
    "timestamp": "2024-01-15T10:45:00Z"
  }
}
```

## Complete Examples

### Example 1: Authentication Agent Workflow

```python
# Start of authentication agent
project_id = "ecommerce-v2"
session_name = "task-auth-001"

# 1. Register
register_agent(project_id, session_name, "001", "feature/auth", "Build authentication system")

# 2. Create todo list
todos = [
    ("Research JWT best practices", 1),
    ("Design User schema", 1),
    ("Implement password hashing", 1),
    ("Create login endpoint", 2),
    ("Create register endpoint", 2),
    ("Add authentication middleware", 2),
    ("Write tests", 3)
]

todo_ids = []
for text, priority in todos:
    result = add_todo(project_id, session_name, text, priority)
    todo_ids.append(result['todo_id'])

# 3. Start working
update_todo(project_id, session_name, todo_ids[0], "in_progress")

# 4. Check who else is active
agents = list_active_agents(project_id)
print(f"Working with {len(agents) - 1} other agents")

# 5. Create User model
result = announce_file_change(
    project_id, 
    session_name,
    "src/models/user.ts",
    "create"
)

if result['status'] == 'success':
    # Create the file...
    # Then register the interface
    register_interface(
        project_id,
        session_name,
        "User",
        """interface User {
  id: string;
  email: string;
  password: string;  // bcrypt hashed
  role: 'admin' | 'user' | 'guest';
  emailVerified: boolean;
  createdAt: Date;
  updatedAt: Date;
}""",
        "src/models/user.ts"
    )
    
    # Release the lock
    release_file_lock(project_id, session_name, "src/models/user.ts")
    
    # Update todo
    update_todo(project_id, session_name, todo_ids[1], "completed")
    
    # Notify specific agents with query_agent(...) if they need this update.

# 6. Periodically check messages and send heartbeat
import time
while working:
    # Send heartbeat
    heartbeat(project_id, session_name)
    
    # Check messages
    result = check_messages(project_id, session_name)
    messages = result["data"]["messages"]
    for msg in messages:
        if msg['type'] == 'query':
            if 'User' in msg['content']:
                respond_to_query(
                    project_id=project_id,
                    from_session=session_name,
                    to_session=msg['from'],
                    message_id=msg['id'],
                    response="User interface has: id, email, password (hashed), role, emailVerified, timestamps"
                )
    
    time.sleep(30)

# 7. Complete task
unregister_agent(project_id, session_name)
```

### Example 2: Frontend Agent Needing Backend Info

```python
# Frontend agent starting work
project_id = "ecommerce-v2"
session_name = "task-frontend-003"

# 1. Register
register_agent(project_id, session_name, "003", "feature/login-ui", "Build login interface")

# 2. Check what backend agents are doing
agents_result = list_active_agents(project_id)
auth_agent = None

for agent in agents_result["data"]["agents"]:
    if 'auth' in agent['description'].lower():
        auth_agent = agent['session_name']

# 3. Query for API details
if auth_agent:
    response = query_agent(
        project_id=project_id,
        from_session=session_name,
        to_session=auth_agent,
        query_type="api",
        query="What's the login endpoint URL and what data does it expect?",
        wait_for_response=True
    )
    print(f"Login API details: {response}")

# 4. Get User interface
user_interface = query_interface(project_id, "User")
if user_interface.get('status') != 'not_found':
    print(f"User interface available: {user_interface['definition']}")
else:
    # Wait or ask for it
    query_agent(
        project_id=project_id,
        from_session=session_name,
        to_session="task-auth-001",
        query_type="interface",
        query="I need the User interface to build the login form. Has anyone created it?"
    )

# 5. Work on login component
result = announce_file_change(
    project_id,
    session_name,
    "src/components/LoginForm.tsx",
    "create"
)

if result['status'] == 'success':
    # Build the component using the User interface
    # ...
    release_file_lock(project_id, session_name, "src/components/LoginForm.tsx")
```

### Example 3: Coordinating Multiple Agents

```python
# API agent needs to coordinate with both auth and database agents
project_id = "ecommerce-v2"
session_name = "task-api-004"

# 1. Register
register_agent(project_id, session_name, "004", "feature/user-api", "Build user management API")

# 2. Check all interfaces
interfaces = list_interfaces(project_id)
print(f"Available interfaces: {list(interfaces.keys())}")

# 3. See what everyone is working on
agents_result = list_active_agents(project_id)

# Find agents working on related features
auth_agent = None
db_agent = None

for agent in agents_result["data"]["agents"]:
    if 'auth' in agent['description'].lower():
        auth_agent = agent['session_name']
    elif 'database' in agent['description'].lower():
        db_agent = agent['session_name']

# 4. Query multiple agents
if auth_agent:
    auth_response = query_agent(
        project_id=project_id,
        from_session=session_name,
        to_session=auth_agent,
        query_type="interface",
        query="What auth middleware should I use for protecting user endpoints?",
        wait_for_response=True
    )

if db_agent:
    db_response = query_agent(
        project_id=project_id,
        from_session=session_name,
        to_session=db_agent,
        query_type="help",
        query="What's the database connection pattern we're using?",
        wait_for_response=True
    )

# 5. Register API contracts for others to use
register_interface(
    project_id,
    session_name,
    "UserAPI",
    """interface UserAPI {
  GET /api/users - List all users (admin only)
  GET /api/users/:id - Get user by ID
  PUT /api/users/:id - Update user
  DELETE /api/users/:id - Delete user (admin only)
  
  All endpoints require Authorization: Bearer <token>
}""",
    "src/routes/users.ts"
)

# 6. Check for conflicts before working on shared files
shared_files = ["src/app.ts", "src/routes/index.ts"]
for file_path in shared_files:
    result = announce_file_change(
        project_id,
        session_name,
        file_path,
        "modify"
    )
    
    if result['status'] == 'error':
        # Someone else is working on it
        lock_info = result['data']['lock_info']
        print(f"{file_path} is locked by {lock_info['session']}")
        print(f"They are: {lock_info['description']}")
        
        # Query them about timeline
        response = query_agent(
            project_id=project_id,
            from_session=session_name,
            to_session=lock_info['session'],
            query_type="status",
            query=f"When will you be done with {file_path}? I need to add user routes.",
            wait_for_response=True
        )
```

## Error Handling

### Common Error Responses

```python
# Agent not found
{
  "error": "Agent task-999 not found in project ecommerce-v2"
}

# File conflict
{
  "status": "conflict",
  "error": "File is locked by task-auth-001",
  "lock_info": { ... }
}

# Interface not found
{
  "status": "not_found",
  "error": "Interface UserProfile not found",
  "similar": ["User", "Profile"]
}

# Query timeout
{
  "status": "timeout",
  "error": "No response received within 30 seconds"
}
```

### Error Handling Pattern

```python
def safe_query_interface(project_id, interface_name):
    """Safely query an interface with fallback"""
    result = query_interface(project_id, interface_name)
    
    if isinstance(result, dict) and result.get('status') == 'not_found':
        # Interface doesn't exist
        similar = result.get('similar', [])
        if similar:
            print(f"Interface {interface_name} not found. Similar: {similar}")
            # Try the first similar one
            if similar:
                return query_interface(project_id, similar[0])
        return None
    
    return result

def safe_file_change(project_id, session_name, file_path, operation, max_retries=3):
    """Try to lock a file with retries"""
    for attempt in range(max_retries):
        result = announce_file_change(project_id, session_name, file_path, operation)
        
        if result['status'] == 'success':
            return True
        
        if result['status'] == 'error':
            print(f"Attempt {attempt + 1}: File locked by {result['data']['lock_info']['session']}")
            if attempt < max_retries - 1:
                time.sleep(10)  # Wait 10 seconds before retry
            else:
                return False
    
    return False
```

## Best Practices

### 1. Always Register First
```python
# ALWAYS do this first
register_agent(project_id, session_name, task_id, branch, description)
```

### 2. Maintain Heartbeat
```python
# In your main loop
while working:
    heartbeat(project_id, session_name)
    # Do work...
    time.sleep(30)
```

### 3. Create Detailed Todos
```python
# Good: Specific and actionable
add_todo(project_id, session_name, "Implement bcrypt password hashing with salt rounds=10", 1)

# Bad: Too vague
add_todo(project_id, session_name, "Do authentication", 1)
```

### 4. Check Messages Regularly
```python
# Check every 30-60 seconds
result = check_messages(project_id, session_name)
messages = result["data"]["messages"]
for msg in messages:
    # Process each message appropriately
    handle_message(msg)
```

### 5. Always Release Locks
```python
try:
    result = announce_file_change(project_id, session_name, file_path, "modify")
    if result['status'] == 'success':
        # Do your work
        modify_file(file_path)
finally:
    # ALWAYS release, even if error occurs
    release_file_lock(project_id, session_name, file_path)
```

### 6. Query Before Assuming
```python
# Don't assume an interface exists
user_interface = query_interface(project_id, "User")
if user_interface.get('status') == 'not_found':
    # Handle missing interface
    query_agent(
        project_id=project_id,
        from_session=session_name,
        to_session="task-auth-001",
        query_type="interface",
        query="Is the User interface ready?"
    )
```

### 7. Share Important Changes Deliberately
```python
# The Redis MCP server does not currently expose broadcast_message.
# Notify the specific sessions that need to know.
query_agent(
    project_id=project_id,
    from_session=session_name,
    to_session="task-auth-001",
    query_type="status",
    query="Heads up: User.id is changing from number to string UUID. Please update your code."
)
```

### 8. Clean Exit
```python
# Always unregister when done
result = unregister_agent(project_id, session_name)
print(f"Completed {result['todo_summary']['completed']} todos")
```

---

*This API reference is part of the A2AMCP project. For more information, visit [github.com/webdevtodayjason/A2AMCP](https://github.com/webdevtodayjason/A2AMCP)*
