# Ensuring Claude Code Uses MCP Communication Tools

This guide explains how to ensure Claude Code agents will properly use the MCP communication tools in your SplitMind multi-agent system.

## The Challenge

Claude Code needs to:
1. Know the MCP server exists
2. Have access to the tools
3. Be prompted to use them

## Configuration Methods

### Method 1: Claude Code Configuration File

Claude Code reads MCP server configs from its configuration file:

**Location**: `~/.config/claude-code/config.json`

**Configuration**:
```json
{
  "mcpServers": {
    "splitmind-agent-comm": {
      "command": "docker",
      "args": ["exec", "-i", "splitmind-mcp-server", "python", "/app/mcp_server_redis.py"],
      "env": {}
    }
  }
}
```

### Method 2: Environment Variable

When spawning Claude Code in tmux, set the MCP_SERVERS environment variable:

```bash
export MCP_SERVERS='{
  "splitmind-agent-comm": {
    "command": "docker",
    "args": ["exec", "-i", "splitmind-mcp-server", "python", "/app/mcp_server_redis.py"]
  }
}'

claude-code "your prompt here"
```

## Critical: Prompt Engineering

The most important part is providing explicit instructions in the agent prompt. Claude Code needs to be told exactly what tools to use and when.

### Complete Prompt Template

```python
def generate_agent_prompt(task, project_id):
    session_name = f"task-{task['task_id']}"
    
    # The actual task
    task_prompt = task['description']
    
    # CRITICAL: Explicit MCP instructions
    mcp_instructions = f"""
MANDATORY: You MUST use the MCP communication tools. These are required for coordination.

BEFORE doing anything else, you MUST:
1. Register yourself using the register_agent tool:
   register_agent("{project_id}", "{session_name}", "{task['task_id']}", "{task['branch']}", "{task['description']}")

2. If registration fails, STOP and report the error.

THROUGHOUT your work, you MUST:
- Send heartbeat every 30 seconds: heartbeat("{project_id}", "{session_name}")
- Check messages every few steps: `result = check_messages("{project_id}", "{session_name}")` then iterate `result["data"]["messages"]`
- Before modifying ANY file: announce_file_change("{project_id}", "{session_name}", "filepath", "operation")
- After modifying: release_file_lock("{project_id}", "{session_name}", "filepath")

CREATE YOUR TODO LIST:
After registering, break down your task into todos:
- add_todo("{project_id}", "{session_name}", "Research approach", 1)
- add_todo("{project_id}", "{session_name}", "Implement feature", 1)
- Update as you progress: update_todo("{project_id}", "{session_name}", "todo_id", "in_progress")

COORDINATE WITH OTHERS:
- See who's active: list_active_agents("{project_id}")
- Check a specific agent's progress with the raw Redis MCP server: get_my_todos("{project_id}", "target_session")
- Ask questions: `query_agent(project_id="{project_id}", from_session="{session_name}", to_session="target", query_type="type", query="question")`
- When replying, use: `respond_to_query(project_id="{project_id}", from_session="{session_name}", to_session=msg["from"], message_id=msg["id"], response="answer")`

Communication tool results are wrapped as `{ "status": ..., "message": ..., "data": ... }`.

If you cannot access these tools, STOP and report that MCP tools are not available.
"""
    
    return f"{mcp_instructions}\n\nYour task:\n{task_prompt}"
```

## Verification Strategies

### 1. Built-in Verification

Include verification as the first required action:

```python
def spawn_agent_with_verification(task, project_id):
    session_name = f"task-{task['task_id']}"
    
    # Include verification in prompt
    prompt = f"""
FIRST ACTION - Verify MCP tools are available:
1. Run: register_agent("{project_id}", "{session_name}", "{task['task_id']}", "{task['branch']}", "Testing MCP connection")
2. If this fails or the tool is not found, output: "ERROR: MCP tools not available"
3. If successful, you should see "Successfully registered" in the response

{generate_agent_prompt(task, project_id)}
"""
    
    # Spawn the agent with this prompt
```

### 2. Pre-flight Check Script

Create a test script to verify MCP connectivity before spawning agents:

```bash
#!/bin/bash
# test-mcp-connection.sh

echo "Testing MCP connection..."

# Test if MCP server is reachable
if docker ps | grep -q splitmind-mcp-server; then
    echo "✓ MCP server container is running"
else
    echo "✗ MCP server not running!"
    echo "Run: docker-compose up -d"
    exit 1
fi

# Test Redis
if docker exec splitmind-redis redis-cli ping > /dev/null 2>&1; then
    echo "✓ Redis is responding"
else
    echo "✗ Redis not responding!"
    exit 1
fi

echo "✓ MCP infrastructure is ready"
```

### 3. Local File Fallback

Create a local instruction file as a fallback:

```python
# Save instructions to a file the agent can read
instructions_file = f"/tmp/agent-{session_name}-mcp.txt"
with open(instructions_file, 'w') as f:
    f.write(f"""
MCP Server: localhost:5000
Project ID: {project_id}
Session Name: {session_name}
Required Tools: register_agent, heartbeat, add_todo, query_agent, etc.

If tools are not available, check:
1. Is Docker container running? (docker ps | grep splitmind-mcp-server)
2. Can you reach the server? (curl localhost:5000)
3. Check Claude Code config at ~/.config/claude-code/config.json
""")

# Reference in prompt
prompt = f"Read {instructions_file} for MCP setup instructions. {task_prompt}"
```

## Example Orchestrator Integration

```python
class MCPEnabledOrchestrator:
    def spawn_agent(self, task, project_id):
        """Spawn an agent with MCP communication enforced"""
        
        session_name = f"task-{task['task_id']}"
        worktree_path = self.create_worktree(task['branch'])
        
        # Generate prompt with mandatory MCP instructions
        prompt = self.generate_agent_prompt(task, project_id)
        
        # Save prompt to file to avoid shell escaping
        prompt_file = f"/tmp/prompt-{session_name}.txt"
        with open(prompt_file, 'w') as f:
            f.write(prompt)
        
        # Create tmux session with MCP configuration
        commands = f"""
        tmux new-session -d -s {session_name} -c {worktree_path}
        tmux send-keys -t {session_name} "export PROJECT_ID={project_id}" Enter
        tmux send-keys -t {session_name} "export SESSION_NAME={session_name}" Enter
        tmux send-keys -t {session_name} "export MCP_SERVERS='{{\"splitmind-agent-comm\":{{\"command\":\"docker\",\"args\":[\"exec\",\"-i\",\"splitmind-mcp-server\",\"python\",\"/app/mcp_server_redis.py\"]}}}}'" Enter
        tmux send-keys -t {session_name} "claude-code --file {prompt_file}" Enter
        """
        
        for cmd in commands.strip().split('\n'):
            subprocess.run(cmd.strip(), shell=True)
```

## Troubleshooting

### If agents aren't using MCP tools:

1. **Check MCP Server**:
   ```bash
   docker ps | grep splitmind-mcp-server
   docker logs splitmind-mcp-server
   ```

2. **Verify Claude Code Config**:
   ```bash
   cat ~/.config/claude-code/config.json
   ```

3. **Test Manual Registration**:
   - Start Claude Code manually
   - Try to run: `register_agent("test", "test-session", "001", "test", "Testing")`
   - If it fails, the MCP connection isn't working

4. **Check Environment**:
   ```bash
   # In the tmux session
   echo $MCP_SERVERS
   ```

5. **Review Agent Output**:
   - Look for "MCP tools not available" errors
   - Check if registration succeeded
   - Monitor heartbeat calls

## Best Practices

1. **Always Start with Registration**: Make it the mandatory first action
2. **Use Explicit Instructions**: Be very clear about tool usage requirements
3. **Include Examples**: Show exact tool calls in the prompt
4. **Add Verification**: Check tool availability before proceeding
5. **Monitor Usage**: Watch Redis to ensure agents are communicating
6. **Fail Fast**: If MCP isn't working, agent should stop immediately

## Key Success Factors

1. **Configuration**: Either config file OR environment variable must be set
2. **Docker Running**: MCP server container must be active
3. **Explicit Prompts**: Clear, mandatory instructions for tool usage
4. **First Action**: Registration must succeed before any other work
5. **Continuous Usage**: Heartbeats, message checks, and coordination throughout

By following these guidelines, your Claude Code agents will reliably use the MCP communication tools to coordinate their work effectively.
