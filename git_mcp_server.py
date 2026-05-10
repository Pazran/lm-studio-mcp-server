import subprocess
from mcp.server.fastmcp import FastMCP

# Create a dedicated Git MCP server
server = FastMCP("Git MCP Server")

# -----------------------------
# Git Tools
# -----------------------------

@server.tool()
def git_init(repo_path: str) -> str:
    """Initialize git repository."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "init"],
            capture_output=True,
            text=True
        )
        return result.stdout or result.stderr
    except Exception as e:
        return f"Error running git_status: {e}"

@server.tool()
def git_status(repo_path: str) -> str:
    """Return 'git status' output for the repository."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "status"],
            capture_output=True,
            text=True
        )
        return result.stdout or result.stderr
    except Exception as e:
        return f"Error running git_status: {e}"

@server.tool()
def git_diff(repo_path: str, staged: bool = False) -> str:
    """Show unstaged or staged diff for the repository."""
    try:
        cmd = ["git", "-C", repo_path, "diff"]
        if staged:
            cmd.append("--staged")
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout or result.stderr
    except Exception as e:
        return f"Error running git_diff: {e}"


@server.tool()
def git_add(repo_path: str, path: str = ".") -> str:
    """Stage files. Default: stage all changes."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "add", path],
            capture_output=True,
            text=True
        )
        return result.stdout or result.stderr
    except Exception as e:
        return f"Error running git_add: {e}"


@server.tool()
def git_commit(repo_path: str, message: str) -> str:
    """Commit staged changes with a message."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "commit", "-m", message],
            capture_output=True,
            text=True
        )
        return result.stdout or result.stderr
    except Exception as e:
        return f"Error running git_commit: {e}"


@server.tool()
def git_log(repo_path: str, max_entries: int = 20) -> str:
    """Show recent commit history."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "log", f"--max-count={max_entries}", "--pretty=oneline"],
            capture_output=True,
            text=True
        )
        return result.stdout or result.stderr
    except Exception as e:
        return f"Error running git_log: {e}"

@server.tool()
def git_push(repo_path: str, remote: str = "origin", branch: str = "main") -> str:
    """
    Push local commits to a remote repository.
    Defaults to 'origin' remote and 'main' branch.
    """
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "push", remote, branch],
            capture_output=True,
            text=True
        )
        return result.stdout or result.stderr
    except Exception as e:
        return f"Error running git_push: {e}"

# -------------------------------
# Separate code execution tools
# -------------------------------
@server.tool()
def shell(cmd: str) -> str:
    """Run shell command."""
    import subprocess
    try:
        return subprocess.getoutput(cmd)
    except Exception as e:
        return f"Shell error: {e}"

@server.tool()
def python_eval(code: str) -> str:
    """Run Python code."""
    try:
        return str(eval(code))
    except Exception as e:
        return f"Python eval error: {e}"

# -----------------------------
# Run server
# -----------------------------
if __name__ == "__main__":
    #print("[Tools Prvdr.] All Git tools registered, MCP server ready")
    server.run()
