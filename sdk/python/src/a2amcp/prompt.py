"""
A2AMCP Python SDK - Prompt Builder

Generates optimal prompts for AI agents with MCP instructions.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Union
from textwrap import dedent


@dataclass
class TaskConfig:
    """Configuration for a task"""

    task_id: str
    branch: str
    description: str
    prompt: Optional[str] = None
    depends_on: List[str] = None
    shared_interfaces: List[str] = None
    required_files: List[str] = None

    def __post_init__(self):
        if self.depends_on is None:
            self.depends_on = []
        if self.shared_interfaces is None:
            self.shared_interfaces = []
        if self.required_files is None:
            self.required_files = []


class PromptBuilder:
    """Builds optimal prompts for A2AMCP agents"""

    def __init__(self, project_id: str):
        """
        Initialize prompt builder.

        Args:
            project_id: Project identifier
        """
        self.project_id = project_id
        self.task: Optional[TaskConfig] = None
        self._dependencies: List[str] = []
        self._interfaces: List[str] = []
        self._coordination_rules: List[str] = []
        self._error_handlers: List[str] = []
        self._custom_instructions: List[str] = []
        self._required_files: List[str] = []
        self._check_interval: int = 30
        self._heartbeat_interval: int = 45

    def with_task(self, task: Union[TaskConfig, dict]) -> "PromptBuilder":
        """Set the task configuration"""
        if isinstance(task, dict):
            task = TaskConfig(**task)
        self.task = task
        self._dependencies.extend(task.depends_on or [])
        self._interfaces.extend(task.shared_interfaces or [])
        self._required_files.extend(task.required_files or [])
        return self

    def with_dependencies(self, dependencies: List[str]) -> "PromptBuilder":
        """Add task dependencies"""
        self._dependencies.extend(dependencies)
        return self

    def with_shared_interfaces(self, interfaces: List[str]) -> "PromptBuilder":
        """Add required shared interfaces"""
        self._interfaces.extend(interfaces)
        return self

    def with_required_files(self, files: List[str]) -> "PromptBuilder":
        """Add files that need coordination"""
        self._required_files.extend(files)
        return self

    def with_coordination_rules(
        self, rules: Optional[List[str]] = None
    ) -> "PromptBuilder":
        """Add coordination rules"""
        if rules:
            self._coordination_rules.extend(rules)
        else:
            # Default coordination rules
            self._coordination_rules.extend(
                [
                    "Always check for existing work before starting",
                    "Query other agents when you need information",
                    "Share interfaces as soon as you create them",
                    "Release file locks promptly after changes",
                    "Update todos to show your progress",
                ]
            )
        return self

    def with_error_recovery(self) -> "PromptBuilder":
        """Add error recovery instructions"""
        self._error_handlers.extend(
            [
                "If registration fails, report the error and stop",
                "If a file is locked, query the owner about timeline",
                "If an interface is missing, ask who's creating it",
                "If you get no response to a query, try broadcasting",
                "Always clean up (unregister) even if errors occur",
            ]
        )
        return self

    def with_check_interval(self, seconds: int) -> "PromptBuilder":
        """Set message check interval"""
        self._check_interval = seconds
        return self

    def with_heartbeat_interval(self, seconds: int) -> "PromptBuilder":
        """Set heartbeat interval"""
        self._heartbeat_interval = seconds
        return self

    def add_instruction(self, instruction: str) -> "PromptBuilder":
        """Add custom instruction"""
        self._custom_instructions.append(instruction)
        return self

    def build(self) -> str:
        """Build the complete prompt"""
        if not self.task:
            raise ValueError("Task configuration is required")

        session_name = f"task-{self.task.task_id}"

        sections = []

        # Header
        sections.append(self._build_header())

        # MCP Configuration
        sections.append(self._build_mcp_config(session_name))

        # Registration
        sections.append(self._build_registration(session_name))

        # Todo Management
        sections.append(self._build_todo_section(session_name))

        # Coordination
        sections.append(self._build_coordination(session_name))

        # Dependencies
        if self._dependencies:
            sections.append(self._build_dependencies())

        # Required Interfaces
        if self._interfaces:
            sections.append(self._build_interfaces())

        # File Coordination
        if self._required_files:
            sections.append(self._build_file_coordination(session_name))

        # Communication
        sections.append(self._build_communication(session_name))

        # Error Handling
        if self._error_handlers:
            sections.append(self._build_error_handling())

        # Custom Instructions
        if self._custom_instructions:
            sections.append(self._build_custom_instructions())

        # Cleanup
        sections.append(self._build_cleanup(session_name))

        # Task Description
        sections.append(self._build_task_section())

        return "\n\n".join(sections)

    def _build_header(self) -> str:
        """Build prompt header"""
        return dedent("""
        # A2AMCP Agent Instructions
        
        You are an AI agent working as part of a coordinated team on a software project.
        You MUST use the MCP (Model Context Protocol) tools to communicate and coordinate
        with other agents working on related tasks.
        """).strip()

    def _build_mcp_config(self, session_name: str) -> str:
        """Build MCP configuration section"""
        return dedent(f"""
        ## Your Identity
        
        - Project ID: `{self.project_id}`
        - Session Name: `{session_name}`
        - Task ID: `{self.task.task_id}`
        - Git Branch: `{self.task.branch}`
        """).strip()

    def _build_registration(self, session_name: str) -> str:
        """Build registration instructions"""
        return dedent(f"""
        ## MANDATORY FIRST ACTION
        
        Before doing ANYTHING else, you MUST register yourself:
        
        ```
        register_agent("{self.project_id}", "{session_name}", "{self.task.task_id}", "{self.task.branch}", "{self.task.description}")
        ```
        
        If this fails:
        1. Output: "ERROR: Cannot access MCP tools"
        2. Check if you see available tools
        3. Do NOT proceed with the task
        
        Expected success response: "Successfully registered"
        """).strip()

    def _build_todo_section(self, session_name: str) -> str:
        """Build todo management instructions"""
        return dedent(f"""
        ## Task Breakdown
        
        After registering, create a todo list to track your progress:
        
        ```
        # Break down your task into specific todos
        add_todo("{self.project_id}", "{session_name}", "Research approach and best practices", 1)
        add_todo("{self.project_id}", "{session_name}", "Design the solution architecture", 1)
        add_todo("{self.project_id}", "{session_name}", "Implement core functionality", 1)
        add_todo("{self.project_id}", "{session_name}", "Add error handling", 2)
        add_todo("{self.project_id}", "{session_name}", "Write tests", 2)
        add_todo("{self.project_id}", "{session_name}", "Update documentation", 3)
        ```
        
        Update todos as you progress:
        - Starting work: `update_todo("{self.project_id}", "{session_name}", "todo_id", "in_progress")`
        - Completing: `update_todo("{self.project_id}", "{session_name}", "todo_id", "completed")`
        - Blocked: `update_todo("{self.project_id}", "{session_name}", "todo_id", "blocked")`
        """).strip()

    def _build_coordination(self, session_name: str) -> str:
        """Build coordination instructions"""
        rules = "\n".join(f"- {rule}" for rule in self._coordination_rules)

        return dedent(f"""
        ## Coordination Rules
        
        {rules}
        
        Check who else is working:
        ```
        list_active_agents("{self.project_id}")
        ```
        
        See everyone's progress:
        ```
        get_all_todos("{self.project_id}")
        ```
        """).strip()

    def _build_dependencies(self) -> str:
        """Build dependency instructions"""
        dep_list = "\n".join(f"- {dep}" for dep in self._dependencies)

        return dedent(f"""
        ## Task Dependencies
        
        This task depends on:
        {dep_list}
        
        Check if dependencies are ready:
        1. Use `get_all_todos("{self.project_id}")` to see their progress
        2. Query specific agents if you need information
        3. Wait for critical dependencies to complete
        """).strip()

    def _build_interfaces(self) -> str:
        """Build interface requirements"""
        interface_list = "\n".join(f"- {iface}" for iface in self._interfaces)

        return dedent(f"""
        ## Required Interfaces
        
        Your task requires these shared interfaces:
        {interface_list}
        
        For each interface:
        1. Check if it exists: `query_interface("{self.project_id}", "InterfaceName")`
        2. If missing, query who's creating it
        3. Wait for it to be available before proceeding
        4. Use the exact definition provided
        """).strip()

    def _build_file_coordination(self, session_name: str) -> str:
        """Build file coordination instructions"""
        file_list = "\n".join(f"- {f}" for f in self._required_files)

        return dedent(f"""
        ## File Coordination
        
        Files that require coordination:
        {file_list}
        
        BEFORE modifying any file:
        ```
        announce_file_change("{self.project_id}", "{session_name}", "path/to/file", "modify")
        ```
        
        If you get a conflict:
        - The file is locked by another agent
        - Query them: `query_agent(project_id="{self.project_id}", from_session="{session_name}", to_session="other-agent", query_type="status", query="When will path/to/file be available?", wait_for_response=True)`
        - Wait for their response or the lock to be released
        
        AFTER modifying:
        ```
        release_file_lock("{self.project_id}", "{session_name}", "path/to/file")
        ```
        
        Share any interfaces/types you create:
        ```
        register_interface("{self.project_id}", "{session_name}", "InterfaceName", "interface definition", "Optional description")
        ```
        """).strip()

    def _build_communication(self, session_name: str) -> str:
        """Build communication instructions"""
        return dedent(f"""
        ## Communication
        
        Throughout your work:
        
        1. **Send heartbeat every {self._heartbeat_interval} seconds**:
           ```
           heartbeat("{self.project_id}", "{session_name}")
           ```
        
        2. **Check messages every {self._check_interval} seconds**:
           ```
           result = check_messages("{self.project_id}", "{session_name}")
           messages = result["data"]["messages"]
           ```
            
            For each query message, respond appropriately:
            ```
            for msg in messages:
                if msg["type"] == "query" and msg.get("requires_response"):
                    respond_to_query(
                        project_id="{self.project_id}",
                        from_session="{session_name}",
                        to_session=msg["from"],
                        message_id=msg["id"],
                        response="Your response",
                    )
            ```
        
        3. **Query other agents when needed**:
           ```
           query_agent(
               project_id="{self.project_id}",
               from_session="{session_name}",
               to_session="target-agent",
               query_type="query_type",
               query="Your question",
               wait_for_response=True,
           )
           ```
            
            Query types: "interface", "api", "help", "status", "timeline"
         
         4. **Use direct queries or shared interfaces for coordination**:
            - `broadcast_message` is not currently exposed by the Redis MCP server in this repository.
         """).strip()

    def _build_error_handling(self) -> str:
        """Build error handling section"""
        handlers = "\n".join(f"- {handler}" for handler in self._error_handlers)

        return dedent(f"""
        ## Error Handling
        
        {handlers}
        
        If you encounter any MCP tool errors:
        1. Log the full error message
        2. Try the operation again after a short delay
        3. If persistent, broadcast for help
        """).strip()

    def _build_custom_instructions(self) -> str:
        """Build custom instructions section"""
        instructions = "\n".join(f"- {inst}" for inst in self._custom_instructions)

        return dedent(f"""
        ## Additional Instructions
        
        {instructions}
        """).strip()

    def _build_cleanup(self, session_name: str) -> str:
        """Build cleanup instructions"""
        return dedent(f"""
        ## MANDATORY CLEANUP
        
        When your task is complete (or if you must stop due to errors):
        
        ```
        unregister_agent("{self.project_id}", "{session_name}")
        ```
        
        This will:
        - Show your todo completion statistics
        - Release any remaining file locks
        - Notify other agents of your departure
        """).strip()

    def _build_task_section(self) -> str:
        """Build the actual task description"""
        task_prompt = self.task.prompt or self.task.description

        return dedent(f"""
        ## Your Task
        
        Branch: `{self.task.branch}`
        
        {task_prompt}
        
        Remember:
        1. Register first
        2. Create and update todos
        3. Coordinate on files
        4. Communicate with other agents
        5. Send heartbeats
        6. Unregister when done
        """).strip()


class AgentSpawner:
    """Spawns agents with optimal configuration"""

    def __init__(self, project: "Project"):
        """
        Initialize agent spawner.

        Args:
            project: Project context
        """
        self.project = project

    async def spawn(
        self,
        task: Union[TaskConfig, dict],
        worktree_path: str,
        claude_command: str = "claude-code",
        additional_env: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Spawn an agent for a task.

        Args:
            task: Task configuration
            worktree_path: Path to git worktree
            claude_command: Command to run Claude
            additional_env: Additional environment variables

        Returns:
            Session name of spawned agent
        """
        if isinstance(task, dict):
            task = TaskConfig(**task)

        session_name = f"task-{task.task_id}"

        # Build optimal prompt
        prompt = (
            PromptBuilder(self.project.project_id)
            .with_task(task)
            .with_coordination_rules()
            .with_error_recovery()
            .build()
        )

        # Save prompt to file to avoid shell escaping
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(prompt)
            prompt_file = f.name

        # Prepare environment
        env = {
            "PROJECT_ID": self.project.project_id,
            "SESSION_NAME": session_name,
            "TASK_ID": task.task_id,
            "GIT_BRANCH": task.branch,
        }

        if additional_env:
            env.update(additional_env)

        # Build tmux commands
        import subprocess

        # Create tmux session
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, "-c", worktree_path],
            check=True,
        )

        # Set environment variables
        for key, value in env.items():
            subprocess.run(
                [
                    "tmux",
                    "send-keys",
                    "-t",
                    session_name,
                    f'export {key}="{value}"',
                    "Enter",
                ],
                check=True,
            )

        # Run Claude with prompt file
        subprocess.run(
            [
                "tmux",
                "send-keys",
                "-t",
                session_name,
                f"{claude_command} --file {prompt_file}",
                "Enter",
            ],
            check=True,
        )

        return session_name

    async def spawn_multiple(
        self,
        tasks: List[Union[TaskConfig, dict]],
        worktree_base: str,
        stagger_delay: float = 2.0,
    ) -> List[str]:
        """
        Spawn multiple agents with staggered starts.

        Args:
            tasks: List of task configurations
            worktree_base: Base path for worktrees
            stagger_delay: Delay between agent starts

        Returns:
            List of session names
        """
        import asyncio

        sessions = []

        for task in tasks:
            if isinstance(task, dict):
                task = TaskConfig(**task)

            worktree_path = f"{worktree_base}/{task.branch}"
            session = await self.spawn(task, worktree_path)
            sessions.append(session)

            if stagger_delay > 0:
                await asyncio.sleep(stagger_delay)

        return sessions
