# A2AMCP Server Setup Guide

## Overview
The A2AMCP (Agent-to-Agent Model Context Protocol) server enables communication between AI agents working on the SplitMind platform. It uses Redis for state management and communicates via MCP's STDIO protocol.

**Latest Update:** Server now uses modern MCP SDK 1.9.3 with proper `@server.list_tools()` and `@server.call_tool()` decorators, eliminating connection hanging issues.

## Running the Server

1. **Start the Docker containers:**
   ```bash
   docker-compose up -d
   ```

2. **Verify containers are running:**
   ```bash
   docker ps | grep splitmind
   ```

   You should see:
   - `splitmind-mcp-server` - The MCP server container
   - `splitmind-redis` - Redis for state storage

3. **Check server logs:**
   ```bash
   docker logs splitmind-mcp-server
   ```

## Configuring Claude Desktop

Add the following to your Claude Desktop MCP configuration file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "splitmind-a2amcp": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "splitmind-mcp-server",
        "python",
        "/app/mcp-server-redis.py"
      ],
      "env": {
        "REDIS_URL": "redis://redis:6379"
      }
    }
  }
}
```

## Available MCP Tools

The server implements **16+ A2AMCP API tools** using modern MCP SDK patterns:

### Agent Management
- **register_agent** - Register an agent for a project
- **unregister_agent** - Unregister an agent when done
- **list_active_agents** - List all active agents
- **heartbeat** - Keep agent alive

### Todo Management
- **add_todo** - Add a todo item
- **update_todo** - Update todo status
- **get_my_todos** - Get agent's todos

### Communication
- **query_agent** - Send query to another agent
- **check_messages** - Check and retrieve messages
- **respond_to_query** - Respond to a specific query

Note: some docs and SDK helpers mention `broadcast_message` and `get_all_todos`,
but those are not currently exposed by the Redis MCP server in this repository.

Communication tools use the standard MCP wrapper response format:
`{"status": str, "message": str, "data": {...}}`.
For `check_messages`, the message list is returned in `data.messages`.

### File Coordination
- **announce_file_change** - Lock a file before editing
- **release_file_lock** - Release file lock after editing
- **get_recent_changes** - Get recent file changes

### Shared Definitions
- **register_interface** - Share a type/interface definition
- **query_interface** - Get shared interface definition
- **list_interfaces** - List all shared interfaces

### Task Completion
- **mark_task_completed** - Signal task completion to orchestrator

**Technical Implementation:**
- Uses `@server.list_tools()` to register available tools
- Uses `@server.call_tool()` to handle tool execution
- Proper A2AMCP response format with status, message, and data
- No connection hanging issues with modern MCP SDK 1.9.3

## Testing

Run the test script to verify all endpoints:
```bash
python test_endpoints.py
```

## Ports
- **5050** - MCP server (mapped from internal 5000)
- **6379** - Redis
- **8081** - Redis Commander UI (optional, with `--profile debug`)

## Troubleshooting

1. **Server keeps restarting:**
   - This is normal for STDIO-based MCP servers
   - The server only runs when Claude connects to it

2. **Connection issues:**
   - Ensure Docker is running
   - Check Redis is healthy: `docker exec splitmind-redis redis-cli ping`
   - Verify port 5050 is not in use

3. **View Redis data:**
   ```bash
   docker-compose --profile debug up -d
   ```
   Then open http://localhost:8081 for Redis Commander UI
