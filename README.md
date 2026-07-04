# LM Studio MCP Server

A robust Model Context Protocol (MCP) server for LM Studio integration, featuring safety-first file operations, persistent memory management, and comprehensive tooling.

![Sample](mcp-lmstudio.png)

## 🌟 Features

- **Safety-First Operations**
  - `dry_run` enforcement before all destructive actions (delete/move/rename/backup)
  - `read-before-write` policy prevents accidental data loss
  - Automatic error handling with structured response patterns
  
- **Comprehensive Toolset** (5 routers, 30+ tools)
  - `file_op`: move, copy, read, open, list, compare, find_items
  - `dir_op`: create_folder, delete_file/folder, rename, backup, safe_delete, copy_folder
  - `util_op`: zip, unzip, file_hash (SHA256), clean_temp
  - `data_op`: read/write_json, write_file, csv_preview/stats/filter_by_date, search_text
  - `sys_op`: get_time, parse_datetime
  
- **Code Execution Tools**
  - `python_eval()`: Safe single-line Python expressions with captured output and variables
  - `python_exec()`: Multi-line code blocks with serializable result filtering
  - `shell()`: System shell command execution for quick queries

- **Persistent Memory Protocol**
  - Learn across sessions via `memory.json` knowledge base
  - `list` before new tasks (check past lessons)
  - `add` after solutions/bug fixes (<20 words summary limit)
  
- **Portable Design**
  - All paths relative to script location (`BASE_DIR`)
  - No hardcoded absolute paths
  - Works across OS environments
  
- **Error Recovery**
  - Clear error messages with retry guidance
  - Path validation before operations
  - Graceful degradation on failures

## 📁 Project Structure

```
lm-studio-mcp-server/
├── mcp_server.py              # Main router-based MCP server (file_op, dir_op, etc.)
├── git_mcp_server.py          # Git integration tools
├── mcp_file_organizer.py      # File organization utilities
├── mcp_webscraper.py          # Web search & current_time via SearXNG
├── config/
│   ├── mcp.json               # LM Studio MCP server configuration
│   └── AgentTools.preset.json # System prompt for router-based tools
├── MIT-LICENSE.txt            # License and attribution
├── README.md                  # This file
├── .gitignore                 # Git ignore patterns
├── requirements.txt          # Python dependencies
└── pyproject.toml            # Project config / packages

```

## 🚀 Installation

### 1. Clone Repository

```bash
cd D:\Scripts\lm-studio-mcp-server
python -m venv venv
venv\Scripts\activate

# Option 1: requirements.txt
pip install -r requirements.txt

# Option 2: pyproject.toml (Do not use both option 1 and 2)
pip install .
```

### 2. Configure LM Studio MCP Servers

Add all servers to `.user/.lmstudio/mcp.json`:

```json
{
  "mcpServers": {
    // Main router-based server (required)
    "Local Utility MCP": {
      "command": "D:\Scripts\lm-studio-mcp-server\venv\Scripts\python.exe",
      "args": [
        "D:\Scripts\lm-studio-mcp-server\mcp_server.py"
      ],
      "env": {"PYTHONUNBUFFERED": "1"},
      "timeout": 180000
    },
    
    // Optional: Web search & current_time via SearXNG (requires SearXNG at localhost:8080)
    "Web Browser MCP": {
      "command": "D:\Scripts\lm-studio-mcp-server\venv\Scripts\python.exe",
      "args": ["D:\Scripts\lm-studio-mcp-server\mcp_webscraper.py"],
      "env": {"PYTHONUNBUFFERED": "1"}
    },

    // Optional: Git integration tools
    "Git MCP": {
      "command": "D:\Scripts\lm-studio-mcp-server\venv\Scripts\python.exe",
      "args": ["D:\Scripts\lm-studio-mcp-server\git_mcp_server.py"],
      "env": {"PYTHONUNBUFFERED": "1"}
    }

  }
}
```

### 3. Set Up System Prompt

Copy `config/AgentTools.preset.json` content to LM Studio's system prompt field, or manually paste the tool documentation for router-based tools.

## ⚙️ Configuration

### Memory Path (Default)

By default, memory is stored relative to script location:
```
{project_root}/memory.json  → D:\Scripts\lm-studio-mcp-server\memory.json
```

No environment variables required - paths are always relative!

### Backup Root (Optional)

For `dir_op` backup operations, backups store here by default:
```
{project_root}/backups/     → D:\Scripts\lm-studio-mcp-server\backups
```

## 🛠️ Usage Examples

### Example 1: File Operations with Safety

```python
# Find all Python files recursively
universal_router(
    router="file_op", 
    action="find_items", 
    params={
        "paths": ["D:\Projects"],
        "pattern": "*.py",
        "max_results": 10,
        "recursive": True,
        "include_files": True,
        "include_folders": False
    }
)

# Move files (dry_run=True recommended first)
universal_router(
    router="file_op",
    action="move",
    params={
        "src": ["D:\Projects\old_file.py"],
        "dst": "D:\Archived"
    }
)
```

### Example 2: Memory Protocol (Learn Across Sessions)

**Check existing lessons before starting new task:**
```python
manage_memory(action="list")
# Output shows all past lessons learned about similar tasks
```

**Save lesson after completing a complex operation:**
```python
manage_memory(
    action="add",
    topic="csv-date-filtering-2025",
    summary="Used ISO date format for csv_filter_by_date with correct column name"
)
```

### Example 3: CSV Data Processing

```python
# Preview first 10 rows of CSV
universal_router(
    router="data_op",
    action="read_csv_preview",
    params={
        "paths": ["D:\Data\sales.csv"],
        "n": 10
    }
)

# Filter by date range (ISO format: YYYY-MM-DD)
universal_router(
    router="data_op",
    action="csv_filter_by_date",
    params={
        "paths": ["D:\Data\sales.csv"],
        "date_column": "sale_date",
        "start": "2024-01-01",
        "end": "2024-12-31"
    }
)
```

### Example 4: File Comparison & Backup

```python
# Compare two versions of a file
universal_router(
    router="file_op",
    action="compare",
    params={
        "files1": ["D:\Projects\code.py"],
        "files2": ["D:\Backups\code_backup.py"]
    }
)

# Backup important files with SHA256 hash verification
universal_router(
    router="dir_op",
    action="backup",
    params={
        "name": "*.py",
        "backup_root": "D:\Backups"
    }
)
```

### Example 5: Write File Operations

```python
# Write to a single file
universal_router(
    router="data_op",
    action="write_file",
    params={
        "paths": ["D:\Projects\output.txt"],
        "content": "Hello, World! This is written content."
    }
)

# Write to multiple files with matching content list
universal_router(
    router="data_op",
    action="write_file",
    params={
        "paths": ["file1.txt", "file2.txt"],
        "content": ["Content for file 1", "Content for file 2"]
    }
)

# Direct Python usage (safe with proper context management)
with open("D:\Projects\output.txt", "w") as f:
    f.write("Direct write example")
```

## 🌐 Web Search Tool (Standalone)

The web search tool is a standalone server that runs independently of the main router system. It requires SearXNG running at `http://localhost:8080/search`.

**Usage:**
```python
# Direct call to standalone server
search_web(
    query="latest AI news",
    detail_level="brief",
    max_results=5,
    lang="en"
)

current_time()  # Returns ISO datetime string
```

**Note:** Do NOT use `universal_router()` for web search - it runs as a separate FastMCP instance. Use the tool name directly when configured in LM Studio.

## 📋 Core Rules (Always Follow)

1. **READ FIRST**: Before modifying any file, use `file_op:read` to verify content
2. **CANONICAL NAMES**: Use exact router/action names - variations cause errors
3. **SAFETY FIRST**: Set `dry_run=True` before all destructive operations
4. **NO REFORMATTING**: Tool outputs are authoritative data - don't reformat unless requested
5. **INCREMENTAL CHANGES**: Make small, focused updates preserving existing logic

## ⚠️ Common Pitfalls & Solutions

| Mistake | Solution |
|---------|----------|
| `file_op:delete_file(path="*.py")` | Use pattern in `find_items` first, then delete individual paths |
| Missing `dry_run=True` before deletions | Always verify with `list()` or preview results first |
| CSV date format mismatches | Check `csv_stats()` column names; use ISO dates (YYYY-MM-DD) |
| Hardcoded absolute paths | Use relative paths from script location (`BASE_DIR`) |

## 🔐 Error Handling Strategy

- **Router errors**: Verify router name is one of: `file_op`, `dir_op`, `util_op`, `data_op`, `sys_op`
- **File not found**: Confirm path exists with `list()` before attempting read/write
- **Permission errors**: Check directory permissions and try dry_run first

## 🧠 Memory Protocol (Manage Lessons)

### When to Call `manage_memory: list`

- New task initiation
- Before complex multi-step operations
- When referencing technical setup/preferences

### When to Call `manage_memory: add`

- After solving a bug or tricky problem
- After discovering user preferences/workflows
- After completing significant feature implementations

### Summary Limits

Max 20 words per lesson summary. Focus on actionable takeaways, not conversational details.

## 📄 License

This project is licensed under the [MIT License](MIT-LICENSE.txt).

### Attribution

The safety-first MCP tooling design patterns (read-before-write, dry_run enforcement, memory protocol) were developed by [@Pazran](https://github.com/Pazran). Please credit this work if you reuse or adapt any tooling in your own projects.

## 🤝 Contributing

This is a production-ready reference implementation. Key areas for potential enhancement:
- Additional router actions based on use cases discovered during operation
- Enhanced error recovery patterns
- Extended memory protocol capabilities

---

**Note**: This project is developed with Python 3.9+. Always test destructive operations with `dry_run=True` first. Web search tool requires SearXNG at localhost:8080.
