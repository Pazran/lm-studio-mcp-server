import io
import sys
import os
import subprocess
import platform
import shutil
import zipfile
import json
import send2trash
import difflib
import pandas as pd
import inspect
import fnmatch
from pypdf import PdfReader
from difflib import get_close_matches
from typing import Dict, Union, List, Optional
from hashlib import sha256
from shutil import move
from datetime import datetime
from mcp.server.fastmcp import FastMCP
from typing import Union, List

# -------------------------------
# CONFIGURATION
# -------------------------------
#BASE_DIR = os.path.dirname(os.path.abspath(__file__))
#DB_PATH = os.path.join(BASE_DIR, "file_index.db")  # absolute path

# Create MCP server
server = FastMCP("Local Utility MCP Server")

# -------------------------------
# Internal helpers for file_op
# -------------------------------
"""
def _normalize_action(router: str, action: str) -> str:
    aliases = action_aliases.get(router, {})
    for canonical, names in aliases.items():
        if action in names:
            return canonical
    return action

def _normalize_params(router: str, action: str, params: dict) -> dict:
    "Convert LLM param names to helper param names."
    mapping = param_aliases.get(router, {}).get(action, {})
    return {mapping.get(k, k): v for k, v in params.items()}"""

def _match(name, pattern):
    name = name.lower()
    pattern = pattern.lower()
    if "*" in pattern or "?" in pattern:
        return fnmatch.fnmatch(name, pattern)
    return pattern in name


def _find_items(
    paths: Union[str, List[str]],
    pattern: str = "*",
    max_results: int = 50,
    recursive: bool = True,
    include_files: bool = True,
    include_folders: bool = True,
) -> Dict:
    results = []
    seen = set()

    if isinstance(paths, str):
        paths = [paths]

    for root in paths:
        if not os.path.isdir(root):
            continue

        walker = os.walk(root) if recursive else [(root, [], os.listdir(root))]

        for current_path, dirs, files in walker:

            if include_folders:
                for d in dirs:
                    if _match(d, pattern):
                        full_path = os.path.join(current_path, d)
                        if full_path not in seen:
                            results.append({"path": full_path, "type": "folder"})
                            seen.add(full_path)

            if include_files:
                for f in files:
                    if _match(f, pattern):
                        full_path = os.path.join(current_path, f)
                        if full_path not in seen:
                            results.append({"path": full_path, "type": "file"})
                            seen.add(full_path)

            if len(results) >= max_results:
                return {"count": len(results), "truncated": True, "results": results}

    return {"count": len(results), "results": results}

def _map_params_to_signature(handler, params: Dict):
    """
    Map LLM parameters to the internal function’s expected arguments.
    Automatically matches close names if LLM uses slightly different keys.
    """
    sig = inspect.signature(handler)
    mapped = {}
    for name in sig.parameters:
        if name in params:
            mapped[name] = params[name]
        else:
            # try to find a close match (case-insensitive, underscores ignored)
            candidate = get_close_matches(
                name.lower(), [k.lower().replace("-", "_") for k in params.keys()], n=1
            )
            if candidate:
                original_key = next(
                    k for k in params.keys() if k.lower().replace("-", "_") == candidate[0]
                )
                mapped[name] = params[original_key]
    return mapped

def _normalize_paths(paths: Union[str, List[str]]) -> List[str]:
    """Ensure we always return a list of paths."""
    if isinstance(paths, str):
        return [paths]
    elif isinstance(paths, list):
        return paths
    else:
        raise TypeError("paths must be a string or list of strings")

def _read_file(paths: Union[str, List[str]]) -> str:
    paths = _normalize_paths(paths)
    result = []
    for p in paths:
        with open(p, 'r', encoding='utf-8') as f:
            result.append(f"=== {p} ===\n" + f.read())
    return "\n".join(result)

def _write_file(paths: Union[str, List[str]], content: Union[str, List[str]]) -> str:
    paths = _normalize_paths(paths)
    if isinstance(content, str):
        content = [content] * len(paths)
    elif isinstance(content, list) and len(content) != len(paths):
        return "Error: length of content list must match number of paths"

    for p, c in zip(paths, content):
        with open(p, 'w', encoding='utf-8') as f:
            f.write(c)
    return f"Wrote {len(paths)} file(s)"

def _copy_file(src: Union[str, List[str]], dst: Union[str, List[str]]) -> str:
    src = _normalize_paths(src)
    dst = _normalize_paths(dst)
    if len(dst) == 1 and len(src) > 1:
        dst = [os.path.join(dst[0], os.path.basename(s)) for s in src]
    if len(src) != len(dst):
        return "Error: number of src and dst paths must match"
    for s, d in zip(src, dst):
        shutil.copy2(s, d)
    return f"Copied {len(src)} file(s)"

def _move_file(src: Union[str, List[str]], dst: Union[str, List[str]]) -> str:
    src = _normalize_paths(src)
    dst = _normalize_paths(dst)
    if len(dst) == 1 and len(src) > 1:
        dst = [os.path.join(dst[0], os.path.basename(s)) for s in src]
    if len(src) != len(dst):
        return "Error: number of src and dst paths must match"
    for s, d in zip(src, dst):
        shutil.move(s, d)
    return f"Moved {len(src)} file(s)"



def _compare_files(files1: Union[str, List[str]], files2: Union[str, List[str]]) -> dict:
    """
    Compare single or multiple file pairs.
    If lists are given, they must be same length.
    Returns dict: {index: comparison_result}.
    """
    files1 = _normalize_paths(files1)
    files2 = _normalize_paths(files2)
    if len(files1) != len(files2):
        return {"error": "files1 and files2 must be the same length"}

    comparisons = {}

    def read_file(path: str) -> str:
        if not os.path.exists(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except:
            return ""

    for idx, (f1, f2) in enumerate(zip(files1, files2)):
        content1 = read_file(f1)
        content2 = read_file(f2)
        diff_lines = list(difflib.unified_diff(
            content1.splitlines(),
            content2.splitlines(),
            fromfile=f1,
            tofile=f2,
            lineterm=""
        ))
        comparisons[idx] = {
            "file1": f1,
            "file2": f2,
            "content1": content1,
            "content2": content2,
            "diff_lines": diff_lines,
            "done": True
        }

    return comparisons

def _list_directory(paths: Union[str, List[str]]) -> dict:
    """
    List contents of directory/directories.
    Returns dict: {path: [contents]}.
    """
    paths = _normalize_paths(paths)
    results = {}
    for p in paths:
        if os.path.isdir(p):
            try:
                results[p] = os.listdir(p)
            except Exception as e:
                results[p] = [f"Error listing directory: {e}"]
        else:
            results[p] = [f"Not a directory"]
    return results

def _open_file(paths: Union[str, List[str]]) -> str:
    """
    Open single or multiple files with default system application.
    Returns summary string.
    """
    paths = _normalize_paths(paths)
    results = []
    for path in paths:
        if not os.path.exists(path):
            results.append(f"File does not exist: {path}")
            continue
        try:
            system = platform.system()
            if system == "Windows":
                subprocess.Popen(["cmd", "/c", "start", "", path], close_fds=True)
            elif system == "Darwin":
                subprocess.Popen(["open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
            else:
                subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
            results.append(f"Opened file: {path}")
        except Exception as e:
            results.append(f"Failed to open file: {path}, {e}")
    return "\n".join(results)

# -------------------------------
# Internal helpers for dir_op
# -------------------------------

# -------------------------------
# Delete single or multiple files
# -------------------------------
def _delete_file(paths: Union[str, List[str]], dry_run: bool = False) -> dict:
    """
    Delete single or multiple files.
    dry_run=True will only simulate deletion.
    Returns dict per file with success/error info.
    """
    paths = _normalize_paths(paths)
    results = {}
    for p in paths:
        if not os.path.exists(p):
            results[p] = {"success": False, "error": "File not found"}
            continue
        if os.path.isdir(p):
            results[p] = {"success": False, "error": "Path is a directory, not a file"}
            continue
        if dry_run:
            results[p] = {"success": True, "dry_run": True}
            continue
        try:
            os.remove(p)
            results[p] = {"success": True, "message": "Deleted file"}
        except Exception as e:
            results[p] = {"success": False, "error": str(e)}
    return results

# -------------------------------
# Delete single or multiple folders
# -------------------------------
def _delete_folder(paths: Union[str, List[str]], dry_run: bool = False) -> dict:
    """
    Delete single or multiple folders.
    dry_run=True will only simulate deletion.
    Returns dict per folder with success/error info.
    """
    paths = _normalize_paths(paths)
    results = {}
    for p in paths:
        if not os.path.exists(p):
            results[p] = {"success": False, "error": "Folder not found"}
            continue
        if not os.path.isdir(p):
            results[p] = {"success": False, "error": "Path is not a directory"}
            continue
        if dry_run:
            results[p] = {"success": True, "dry_run": True}
            continue
        try:
            shutil.rmtree(p)
            results[p] = {"success": True, "message": "Deleted folder"}
        except Exception as e:
            results[p] = {"success": False, "error": str(e)}
    return results

def _rename_item(
    src: Union[str, List[str]],
    dst: Union[str, List[str]],
    dry_run: bool = False
) -> dict:
    """
    Rename or move single or multiple files/folders.
    Returns dict with results per item.
    """
    def _rename(s: str, d: str) -> dict:
        if not os.path.exists(s):
            return {"src": s, "dst": d, "success": False, "error": "Source not found"}
        if dry_run:
            return {"src": s, "dst": d, "success": True, "dry_run": True}
        try:
            os.rename(s, d)
            return {"src": s, "dst": d, "success": True}
        except Exception as e:
            return {"src": s, "dst": d, "success": False, "error": str(e)}

    src = _normalize_paths(src)
    dst = _normalize_paths(dst)

    if len(src) != len(dst) and len(dst) != 1:
        return {"error": "src and dst must both be lists of the same length or dst can be single path", "final": True}

    # If dst is single path and multiple src, apply dst folder rule
    if len(dst) == 1 and len(src) > 1:
        dst = [os.path.join(dst[0], os.path.basename(s)) for s in src]

    results = [_rename(s, d) for s, d in zip(src, dst)]
    return {
        "count": len(results),
        "results": results,
        "final": True,
        "message": "Rename completed" if not dry_run else "Dry run completed"
    }

# -------------------------------
# Backup workflow
# -------------------------------
def _backup_item(names: Union[str, List[str]], backup_root: str) -> dict:
    """
    Backup single or multiple files by name.
    Copies to backup_root and returns SHA256 hash per file.
    """
    def file_hash(path: str) -> str:
        h = sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    names = _normalize_paths(names)
    results = {}

    for name in names:
        files = _find_items(name)
        if not files.get(name):
            results[name] = {"status": "error", "message": "File not found"}
            continue
        for f in files[name]:
            rel_path = os.path.basename(f)
            dest = os.path.join(backup_root, rel_path)
            try:
                shutil.copy2(f, dest)
                results[f] = {"backup_path": dest, "hash": file_hash(dest)}
            except Exception as e:
                results[f] = {"status": "error", "message": str(e)}
    return results

# -------------------------------
# Safe delete (Recycle Bin)
# -------------------------------
def _safe_delete(paths: Union[str, List[str]]) -> dict:
    """
    Move single or multiple files/folders to Recycle Bin.
    Returns structured result per path.
    """
    paths = _normalize_paths(paths)
    results = {}
    for path in paths:
        if not os.path.exists(path):
            results[path] = {"success": False, "error": "Path not found"}
            continue
        try:
            send2trash.send2trash(path)
            results[path] = {"success": True, "message": "Moved to Recycle Bin"}
        except Exception as e:
            results[path] = {"success": False, "error": str(e)}
    return results

# -------------------------------
# Copy folder
# -------------------------------
def _copy_folder(src: Union[str, List[str]], dst: Union[str, List[str]]) -> dict:
    """
    Copy single or multiple folders.
    Returns dict per folder with success/error messages.
    """
    src = _normalize_paths(src)
    dst = _normalize_paths(dst)

    # If dst is single path and multiple src, copy into dst folder
    if len(dst) == 1 and len(src) > 1:
        dst = [os.path.join(dst[0], os.path.basename(s)) for s in src]

    if len(src) != len(dst):
        return {"error": "Number of src and dst folders must match"}

    results = {}
    for s, d in zip(src, dst):
        try:
            shutil.copytree(s, d)
            results[s] = {"success": True, "dst": d}
        except Exception as e:
            results[s] = {"success": False, "error": str(e)}
    return results

def _create_folder(paths: Union[str, List[str]]) -> dict:
    paths = _normalize_paths(paths)
    results = {}
    for p in paths:
        if os.path.exists(p):
            results[p] = {"success": False, "error": "Folder already exists"}
            continue
        try:
            os.makedirs(p)
            results[p] = {"success": True, "message": "Folder created"}
        except Exception as e:
            results[p] = {"success": False, "error": str(e)}
    return results

# _rename_item, _backup_item, _safe_delete, _copy_folder implemented similarly with list support

# -------------------------------
# Internal handlers for util_op
# -------------------------------

# -------------------------------
# Zip folder
# -------------------------------
def _zip_folder(src: Union[str, List[str]], dst: Union[str, List[str]]) -> dict:
    """
    Zip single or multiple folders into destination paths.
    Returns dict per folder.
    """
    src = _normalize_paths(src)
    dst = _normalize_paths(dst)
    if len(dst) == 1 and len(src) > 1:
        dst = [os.path.join(dst[0], os.path.basename(s) + ".zip") for s in src]
    if len(src) != len(dst):
        return {"error": "Number of src and dst must match"}

    results = {}
    for s, d in zip(src, dst):
        try:
            with zipfile.ZipFile(d, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(s):
                    for file in files:
                        file_path = os.path.join(root, file)
                        zipf.write(file_path, os.path.relpath(file_path, s))
            results[s] = {"success": True, "dst": d}
        except Exception as e:
            results[s] = {"success": False, "error": str(e)}
    return results

# -------------------------------
# Unzip folder
# -------------------------------
def _unzip(src: Union[str, List[str]], dst: Union[str, List[str]]) -> dict:
    """
    Unzip single or multiple zip files to destination folders.
    Returns dict per file.
    """
    src = _normalize_paths(src)
    dst = _normalize_paths(dst)
    if len(dst) == 1 and len(src) > 1:
        dst = [os.path.join(dst[0], os.path.splitext(os.path.basename(s))[0]) for s in src]
    if len(src) != len(dst):
        return {"error": "Number of src and dst must match"}

    results = {}
    for s, d in zip(src, dst):
        try:
            with zipfile.ZipFile(s, "r") as zipf:
                zipf.extractall(d)
            results[s] = {"success": True, "dst": d}
        except Exception as e:
            results[s] = {"success": False, "error": str(e)}
    return results

# -------------------------------
# File hashing
# -------------------------------
def _file_hash(paths: Union[str, List[str]]) -> dict:
    """
    Compute SHA256 hash for single or multiple files.
    Returns dict {path: hash}.
    """
    paths = _normalize_paths(paths)
    results = {}
    for p in paths:
        if not os.path.isfile(p):
            results[p] = {"success": False, "error": "Not a file"}
            continue
        try:
            h = sha256()
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            results[p] = {"success": True, "hash": h.hexdigest()}
        except Exception as e:
            results[p] = {"success": False, "error": str(e)}
    return results

# -------------------------------
# Clean temp folder
# -------------------------------
def _clean_temp(paths: Union[str, List[str]]) -> dict:
    """
    Clean temporary folders by deleting contents.
    Returns dict per folder.
    """
    paths = _normalize_paths(paths)
    results = {}
    for folder in paths:
        if not os.path.isdir(folder):
            results[folder] = {"success": False, "error": "Not a directory"}
            continue
        try:
            for item in os.listdir(folder):
                item_path = os.path.join(folder, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                else:
                    shutil.rmtree(item_path)
            results[folder] = {"success": True, "message": "Cleaned folder"}
        except Exception as e:
            results[folder] = {"success": False, "error": str(e)}
    return results

# -------------------------------
# Internal handlers for data_op
# -------------------------------

# -------------------------------
# Read JSON
# -------------------------------
def _read_json(paths: Union[str, List[str]]) -> dict:
    paths = _normalize_paths(paths)
    results = {}
    for p in paths:
        if not os.path.isfile(p):
            results[p] = {"success": False, "error": "Not a file"}
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                results[p] = {"success": True, "data": json.load(f)}
        except Exception as e:
            results[p] = {"success": False, "error": str(e)}
    return results

# -------------------------------
# Write JSON
# -------------------------------
def _write_json(paths: Union[str, List[str]], data: Union[dict, List[dict]]) -> dict:
    paths = _normalize_paths(paths)
    if isinstance(data, dict):
        data = [data] * len(paths)
    elif isinstance(data, list) and len(data) != len(paths):
        return {"error": "Length of data must match number of paths"}

    results = {}
    for p, d in zip(paths, data):
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=4)
            results[p] = {"success": True}
        except Exception as e:
            results[p] = {"success": False, "error": str(e)}
    return results

# -------------------------------
# CSV preview / stats / query
# -------------------------------
# -------------------------------
# CSV preview
# -------------------------------
def _read_csv_preview(paths: Union[str, List[str]], n: int = 5) -> dict:
    """
    Return the first n rows of single or multiple CSV files using pandas.
    """
    paths = _normalize_paths(paths)
    results = {}
    for p in paths:
        if not os.path.isfile(p):
            results[p] = {"success": False, "error": "Not a file"}
            continue
        try:
            df = pd.read_csv(p, nrows=n)
            results[p] = {"success": True, "preview": df.to_dict(orient="records")}
        except Exception as e:
            results[p] = {"success": False, "error": str(e)}
    return results

# -------------------------------
# CSV stats
# -------------------------------
def _read_csv_stats(paths: Union[str, List[str]]) -> dict:
    """
    Return row and column count of CSV files using pandas.
    """
    paths = _normalize_paths(paths)
    results = {}
    for p in paths:
        if not os.path.isfile(p):
            results[p] = {"success": False, "error": "Not a file"}
            continue
        try:
            df = pd.read_csv(p)
            results[p] = {"success": True, "rows": len(df), "columns": len(df.columns)}
        except Exception as e:
            results[p] = {"success": False, "error": str(e)}
    return results

# -------------------------------
# CSV filter by date
# -------------------------------
def _csv_filter_by_date(
    paths: Union[str, List[str]],
    date_column: str,
    start: str,
    end: str,
    date_format: str = "%Y-%m-%d"
) -> dict:
    """
    Filter rows by date column in single or multiple CSVs using pandas.
    Returns filtered rows per file.
    """
    paths = _normalize_paths(paths)
    results = {}
    start_dt = pd.to_datetime(start, format=date_format)
    end_dt = pd.to_datetime(end, format=date_format)

    for p in paths:
        if not os.path.isfile(p):
            results[p] = {"success": False, "error": "Not a file"}
            continue
        try:
            df = pd.read_csv(p, parse_dates=[date_column])
            filtered = df[(df[date_column] >= start_dt) & (df[date_column] <= end_dt)]
            results[p] = {"success": True, "filtered": filtered.to_dict(orient="records")}
        except Exception as e:
            results[p] = {"success": False, "error": str(e)}
    return results

def _search_text(paths: Union[str, List[str]], query: str) -> dict:
    """
    Search for a text string in single or multiple files.
    Returns dict of matching lines per file.
    """
    paths = _normalize_paths(paths)
    results = {}
    for p in paths:
        if not os.path.isfile(p):
            results[p] = {"success": False, "error": "Not a file"}
            continue
        matches = []
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                for idx, line in enumerate(f, 1):
                    if query in line:
                        matches.append({"line": idx, "content": line.strip()})
            results[p] = {"success": True, "matches": matches}
        except Exception as e:
            results[p] = {"success": False, "error": str(e)}
    return results

# =======================================================
# ---------------- System Helpers ----------------------
# =======================================================

def _get_current_time() -> str:
    return datetime.now().isoformat()

def _parse_datetime(date_str: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return datetime.strptime(date_str, fmt).isoformat()

# =======================================================
# ----------------- Routers for MCP --------------------
# =======================================================
@server.tool()
def universal_router(router: str, action: str, params: dict):
    """
    Universal MCP router that calls any internal handler.

    Args:
        router (str): Canonical router name (file_op, dir_op, util_op, data_op, sys_op)
        action (str): Canonical action name for the router
        params (dict): Parameters for the action

    Returns:
        dict: Structured result from the handler
    """
    routers = {
        "file_op": {
            "move": _move_file,
            "copy": _copy_file,
            "open": _open_file,
            "read": _read_file,
            "list": _list_directory,
            "compare": _compare_files,
            "find_items": _find_items
        },
        "dir_op": {
            "create_folder": _create_folder,
            "delete_file": _delete_file,
            "delete_folder": _delete_folder,
            "rename": _rename_item,
            "backup": _backup_item,
            "safe_delete": _safe_delete,
            "copy_folder": _copy_folder
        },
        "util_op": {
            "zip": _zip_folder,
            "unzip": _unzip,
            "file_hash": _file_hash,
            "clean_temp": _clean_temp
        },
        "data_op": {
            "read_json": _read_json,
            "write_json": _write_json,
            "read_csv_preview": _read_csv_preview,
            "csv_stats": _read_csv_stats,
            "csv_filter_by_date": _csv_filter_by_date,
            "search_text": _search_text,
            "compare_files": _compare_files
        },
        "sys_op": {
            "get_time": _get_current_time,
            "parse_datetime": _parse_datetime
        }
    }

    if router not in routers:
        return {"error": f"Unknown router: {router}"}
    if action not in routers[router]:
        return {"error": f"Unknown action for {router}: {action}"}

    handler = routers[router][action]

    try:
        mapped_params = _map_params_to_signature(handler, params)
        return handler(**mapped_params)
    except Exception as e:
        return {"error": str(e)}

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
"""
@server.tool()
def python_eval(code: str) -> str:
    ""Run single line Python expression.""
    try:
        return str(eval(code))
    except Exception as e:
        return f"Python eval error: {e}"

@server.tool()
def python_exec(code: str) -> dict:
    ""Execute a block of Python code.""
    try:
        local_vars = {}
        exec(code, {}, local_vars)
        return {"result": local_vars}
    except Exception as e:
        return {"error": str(e)}"""

@server.tool()
def python_eval(code: str) -> dict:
    """Run single line Python expression safely."""
    output_capture = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = output_capture
    
    try:
        result = eval(code)
        return {
            "result": str(result),
            "stdout": output_capture.getvalue()
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        sys.stdout = old_stdout

@server.tool()
def python_exec(code: str) -> dict:
    """Execute a block of Python code and return captured output and variables."""
    # Create a buffer to capture stdout
    output_capture = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = output_capture
    
    local_vars = {}
    try:
        # Execute the code
        exec(code, {}, local_vars)
        
        # Filter for serializable variables only
        serializable_vars = {
            k: v for k, v in local_vars.items() 
            if isinstance(v, (str, int, float, bool, list, dict, type(None)))
        }
        
        return {
            "result": serializable_vars,
            "stdout": output_capture.getvalue()
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        # Restore stdout regardless of success or failure
        sys.stdout = old_stdout

@server.tool()
def read_pdf_text(path: str, max_chars: int = 20000) -> str:
    """
    Read PDF file.
    Returns truncated text to avoid context overflow.
    """
    try:
        reader = PdfReader(path)
        text = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)

            if sum(len(t) for t in text) > max_chars:
                break

        content = "\n".join(text)
        return content[:max_chars] or "No extractable text found in PDF."
    except Exception as e:
        return f"Error reading PDF: {e}"

# MEMORY MANAGEMENT
@server.tool()
def manage_memory(action: str, topic: Optional[str] = None, summary: Optional[str] = None) -> str:
    """
    Manages a persistent JSON knowledge base for long-term learning.
    
    Args:
        action (str): Must be either 'list' to retrieve all lessons, 
                     or 'add' to record a new lesson.
        topic (str, optional): A short title/category for the lesson. Required for 'add'.
        summary (str, optional): A concise (max 20 words) explanation of the lesson. Required for 'add'.
        
    Returns:
        str: A confirmation message or a string representation of the stored lessons.
    """
    filepath = f"D:\AI_Lab\LLMs\LMStudio_Clara_Memory\memory.json"
    
    # 1. Ensure file exists with a base schema
    if not os.path.exists(filepath):
        with open(filepath, 'w') as f:
            json.dump({"lessons": []}, f)

    try:
        # 2. Read existing data
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # 3. Handle 'list' action
        if action == "list":
            return json.dumps(data.get("lessons", []), indent=2)
        
        # 4. Handle 'add' action
        elif action == "add":
            if not topic or not summary:
                return "Error: 'add' action requires both 'topic' and 'summary'."
            
            data["lessons"].append({"topic": topic, "summary": summary})
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            return f"Successfully saved lesson under topic: {topic}"
            
        return "Error: Invalid action. Use 'list' or 'add'."
        
    except Exception as e:
        return f"Error accessing memory file: {str(e)}"

# -------------------------------
# Run MCP server
# -------------------------------
if __name__ == "__main__":
    #print(f"Starting MCP server using DB: {DB_PATH}")
    server.run()
    #server.run(host="localhost", port=8080, enable_http=True)
