# -------------------------------
# Modular Smart File Classifier (MCP tools - non-recursive + 3-tier pipeline)
# -------------------------------
import os
import json
import mimetypes
import hashlib
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# CONFIG (adjustable)
AI_MAX_FILE_SIZE_MB = 50  # skip AI for files larger than this
AI_SAMPLE_KB = 8          # how many KB to sample for AI payload
CATEGORIES = {
    "images": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".tiff"],
    "videos": [".mp4", ".mkv", ".mov", ".avi", ".webm"],
    "audio": [".mp3", ".wav", ".flac", ".aac", ".m4a"],
    "documents": [".pdf", ".docx", ".doc", ".xlsx", ".pptx", ".txt", ".md", ".rtf"],
    "archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "executables": [".exe", ".msi", ".dmg", ".apk"],
    "code": [".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs", ".php"],
    "fonts": [".ttf", ".otf", ".woff", ".woff2"],
    "configs": [".json", ".yaml", ".yml", ".ini", ".cfg"],
    "models": [".pth", ".pt", ".bin", ".safetensors"],
    "unknown": []
}

server = FastMCP("File Organizer MCP Server")

# -------------------------------
# Helper utilities (internal)
# -------------------------------

def _filesize_mb(path):
    try:
        return os.path.getsize(path) / (1024.0 * 1024.0)
    except:
        return 0.0

def _read_magic_bytes(path, n=16):
    try:
        with open(path, "rb") as f:
            raw = f.read(n)
        return raw
    except:
        return b""

def _hex_preview(b: bytes, length=48):
    return b.hex()[:length]

def _is_text_like(path, sample_bytes: bytes) -> bool:
    # quick heuristic: try decode, check ratio of printable chars
    try:
        s = sample_bytes.decode("utf-8", errors="ignore")
        if not s:
            return False
        printable = sum(1 for ch in s if ch.isprintable() or ch.isspace())
        ratio = printable / max(1, len(s))
        return ratio > 0.7
    except:
        return False

def _compute_sha256(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except:
        return None

def _mime_guess(path):
    mt, _ = mimetypes.guess_type(path)
    return mt or ""

# -------------------------------
# 1) list_files_nonrecursive(path)
# -------------------------------
@server.tool()
def list_files_nonrecursive(path: str) -> dict:
    """
    Return a list of files directly under `path` (non-recursive).
    Output:
      {"path": "...", "files": [{"name": "a.txt", "full": "...", "size_mb": 0.1}, ...]}
    """
    try:
        if not os.path.isdir(path):
            return {"error": f"Not a directory: {path}"}
        items = []
        for name in os.listdir(path):
            full = os.path.join(path, name)
            if os.path.isfile(full):
                items.append({
                    "name": name,
                    "full_path": full,
                    "size_mb": round(_filesize_mb(full), 4)
                })
        return {"path": path, "files": items}
    except Exception as e:
        return {"error": str(e)}

# -------------------------------
# 2) detect_type_quick(path)
#    Tier-1 + Tier-2 heuristics (fast)
# -------------------------------
@server.tool()
def detect_type_quick(path: str) -> dict:
    """
    Fast file type detection using:
      - extension mapping
      - magic bytes (small sample)
      - mimetype guess
      - text/binary heuristic
    Returns:
      {
        "file": path,
        "category": "images|videos|audio|documents|archives|code|configs|models|executables|unknown",
        "subtype": "jpeg|png|mp4|pdf|json|zip|text|binary|...",
        "confidence": float (0..1),
        "method": "quick",
        "details": { ... }  # debug info
      }
    """
    try:
        if not os.path.isfile(path):
            return {"error": f"Not a file: {path}"}

        name = os.path.basename(path)
        ext = os.path.splitext(name)[1].lower()
        size_mb = _filesize_mb(path)
        magic = _read_magic_bytes(path, n=32)
        mime = _mime_guess(path)
        is_text = _is_text_like(path, magic)

        # 1) Extension-based simple mapping (high confidence)
        for cat, exts in CATEGORIES.items():
            if ext in exts:
                return {
                    "file": path,
                    "category": cat if cat != "unknown" else "unknown",
                    "subtype": ext.lstrip("."),
                    "confidence": 0.95,
                    "method": "extension",
                    "details": {
                        "ext": ext,
                        "size_mb": round(size_mb, 4),
                        "mime_guess": mime,
                        "magic_hex": _hex_preview(magic)
                    }
                }

        # 2) Magic bytes header hints (medium-high confidence)
        # common signatures
        header = magic[:8]
        header_hex = header.hex()
        if magic.startswith(b"\xFF\xD8\xFF"):
            return {"file": path, "category": "images", "subtype": "jpeg", "confidence": 0.92, "method": "magic", "details":{"magic_hex": header_hex}}
        if magic.startswith(b"\x89PNG"):
            return {"file": path, "category": "images", "subtype": "png", "confidence": 0.92, "method": "magic", "details":{"magic_hex": header_hex}}
        if magic.startswith(b"%PDF"):
            return {"file": path, "category": "documents", "subtype": "pdf", "confidence": 0.96, "method": "magic", "details":{"magic_hex": header_hex}}
        if magic.startswith(b"PK\x03\x04"):
            # could be zip/docx/odt etc.
            return {"file": path, "category": "archives", "subtype": "zip/zip-derived", "confidence": 0.88, "method": "magic", "details":{"magic_hex": header_hex}}
        if b"ftyp" in magic or b"\x00\x00\x00\x18ftyp" in magic or b"moov" in magic:
            return {"file": path, "category": "videos", "subtype": "mp4/iso", "confidence": 0.88, "method": "magic", "details":{"magic_hex": header_hex}}
        if magic.startswith(b"RIFF") and b"WAVE" in magic:
            return {"file": path, "category": "audio", "subtype": "wav", "confidence": 0.88, "method": "magic", "details":{"magic_hex": header_hex}}
        if magic.startswith(b"OggS"):
            return {"file": path, "category": "audio", "subtype": "ogg", "confidence": 0.88, "method": "magic", "details":{"magic_hex": header_hex}}
        if magic.startswith(b"\x7fELF"):
            return {"file": path, "category": "executables", "subtype": "elf", "confidence": 0.9, "method": "magic", "details":{"magic_hex": header_hex}}
        if magic.startswith(b"MZ"):
            return {"file": path, "category": "executables", "subtype": "pe", "confidence": 0.9, "method": "magic", "details":{"magic_hex": header_hex}}

        # 3) Text-like file heuristics
        if is_text:
            # try to detect common structured text
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    sample = f.read(2048)
                if sample.lstrip().startswith("{") or sample.lstrip().startswith("["):
                    return {"file": path, "category": "configs", "subtype": "json-ish", "confidence": 0.86, "method": "heuristic", "details":{"sample_head": sample[:200]}}
                if "function " in sample or "def " in sample or "import " in sample:
                    return {"file": path, "category": "code", "subtype": "text-code", "confidence": 0.84, "method": "heuristic", "details":{"sample_head": sample[:200]}}
                # fallback text
                return {"file": path, "category": "documents", "subtype": "text", "confidence": 0.7, "method": "heuristic", "details":{"sample_head": sample[:200]}}
            except Exception:
                pass

        # 4) mime guess fallback
        if mime:
            if mime.startswith("image/"):
                return {"file": path, "category": "images", "subtype": mime.split("/")[-1], "confidence": 0.8, "method": "mimetype", "details":{"mime": mime}}
            if mime.startswith("video/"):
                return {"file": path, "category": "videos", "subtype": mime.split("/")[-1], "confidence": 0.8, "method": "mimetype", "details":{"mime": mime}}
            if mime.startswith("audio/"):
                return {"file": path, "category": "audio", "subtype": mime.split("/")[-1], "confidence": 0.8, "method": "mimetype", "details":{"mime": mime}}

        # 5) default unknown
        return {"file": path, "category": "unknown", "subtype": "unknown", "confidence": 0.35, "method": "fallback", "details":{"magic_hex": header_hex, "mime_guess": mime}}
    except Exception as e:
        return {"error": str(e)}

# -------------------------------
# 3) detect_type_ai_payload(path)
#    Prepare small sample & metadata for LLM-based classification
# -------------------------------
@server.tool()
def detect_type_ai_payload(path: str, max_sample_kb: int = AI_SAMPLE_KB, max_file_size_mb: int = AI_MAX_FILE_SIZE_MB) -> dict:
    """
    Prepare a compact payload for AI classification.
    - If file is larger than max_file_size_mb, AI is skipped and an indicator is returned.
    - Returns:
      {
        "file": path,
        "size_mb": float,
        "allow_ai": bool,
        "sample_bytes_hex": "...",  # hex of first N bytes (small)
        "sample_text": "...",       # text sample if decodable
        "magic_hex": "...",
        "quick": <detect_type_quick result>,
        "prompt_template": "..."    # a ready-to-send prompt for your LLM agent
      }
    """
    try:
        if not os.path.isfile(path):
            return {"error": f"Not a file: {path}"}

        size_mb = _filesize_mb(path)
        allow_ai = size_mb <= max_file_size_mb

        # Read sample bytes (small)
        sample_n = int(min(max_sample_kb * 1024, os.path.getsize(path)))
        sample_bytes = b""
        try:
            with open(path, "rb") as f:
                sample_bytes = f.read(sample_n)
        except:
            sample_bytes = b""

        sample_hex = _hex_preview(sample_bytes, length=2048)
        sample_text = ""
        if _is_text_like(path, sample_bytes):
            try:
                sample_text = sample_bytes.decode("utf-8", errors="ignore")
                # reduce length
                sample_text = sample_text[:2000]
            except:
                sample_text = ""

        quick = detect_type_quick(path)

        # build a prompt template the LLM can use (JSON only response)
        prompt = f"""
You are a file classifier. Given the filename, extension, quick-detection hints, and a small sample of bytes/text from the file, decide the best category for the file.
Return JSON ONLY with keys: category, subtype, confidence (0..1), reasoning (short).

Filename: {os.path.basename(path)}
Extension: {os.path.splitext(path)[1]}
Quick detection: {quick}
Magic bytes (hex sample): {sample_hex}
Text preview (if any): {sample_text}

Categories to choose from: images, videos, audio, documents, archives, executables, code, configs, models, fonts, unknown.

Respond with JSON only.
"""

        return {
            "file": path,
            "size_mb": round(size_mb, 4),
            "allow_ai": allow_ai,
            "sample_hex_preview": sample_hex,
            "sample_text_preview": sample_text,
            "quick_hint": quick,
            "prompt_template": prompt
        }
    except Exception as e:
        return {"error": str(e)}

# -------------------------------
# 4) decide_folder(category, base_path, explicit_map=None)
# -------------------------------
@server.tool()
def decide_folder(category: str, base_path: str, explicit_map: str = None) -> dict:
    """
    Decide on a folder path for a given category under base_path.
    - explicit_map: optional JSON string mapping category->foldername (relative to base_path)
    Returns:
      {"category": "...", "folder": "<full_path>", "created": bool}
    """
    try:
        folder_map = {}
        if explicit_map:
            try:
                folder_map = json.loads(explicit_map)
            except:
                folder_map = {}
        # default mapping (prefix with underscore to keep visible but separate)
        default_map = {
            "images": "_Images",
            "videos": "_Videos",
            "audio": "_Audio",
            "documents": "_Documents",
            "archives": "_Archives",
            "executables": "_Executables",
            "code": "_Code",
            "configs": "_Configs",
            "models": "_Models",
            "fonts": "_Fonts",
            "unknown": "_Unsorted"
        }
        name = folder_map.get(category, default_map.get(category, "_Unsorted"))
        full = os.path.join(base_path, name)
        created = False
        if not os.path.exists(full):
            os.makedirs(full, exist_ok=True)
            created = True
        return {"category": category, "folder": full, "created": created}
    except Exception as e:
        return {"error": str(e)}

# -------------------------------
# 5) organize_file_safe(src, dst_folder, dry_run=True, allow_overwrite=False)
# -------------------------------
@server.tool()
def organize_file_safe(src: str, dst_folder: str, dry_run: bool = True, allow_overwrite: bool = False) -> dict:
    """
    Safely organize all top-level files in any folder using AI-based detection.
    - Skips subfolders and files larger than AI_MAX_FILE_SIZE_MB (default 50MB)
    - Uses detect_type_ai_payload + decide_folder to choose destination folder
    - Avoids overwriting unless allowed, adds short SHA256 suffix if collision occurs
    - Supports dry_run to preview changes without moving files

    Args:
        src (str): Path to folder containing files to organize.
        dst_folder (str): Destination base folder path.
        dry_run (bool, optional): Simulate move without applying changes. Defaults to True.
        allow_overwrite (bool, optional): Overwrite existing files if True. Defaults to False.

    Returns:
        dict: Mapping of original file paths to proposed or actual destinations, with move status.
    """
    results = {}
    try:
        if not os.path.isdir(src):
            return {"error": f"Source folder does not exist: {src}"}

        # create dst_folder if missing
        if not os.path.exists(dst_folder):
            os.makedirs(dst_folder, exist_ok=True)

        # iterate top-level files
        for name in os.listdir(src):
            src_path = os.path.join(src, name)
            if not os.path.isfile(src_path):
                continue

            # skip large files
            size_mb = _filesize_mb(src_path)
            if size_mb > AI_MAX_FILE_SIZE_MB:
                results[src_path] = {"skipped": f"file > {AI_MAX_FILE_SIZE_MB}MB"}
                continue

            # AI payload detection
            ai_payload = detect_type_ai_payload(src_path)
            category = ai_payload.get("quick_hint", {}).get("category", "unknown")
            # use decide_folder to get target
            folder_info = decide_folder(category, dst_folder)
            target_folder = folder_info.get("folder", dst_folder)

            # proposed destination
            dst_path = os.path.join(target_folder, name)

            # handle collision
            if os.path.exists(dst_path) and not allow_overwrite:
                base, ext = os.path.splitext(name)
                h = _compute_sha256(src_path) or str(int(os.path.getmtime(src_path)))
                dst_path = os.path.join(target_folder, f"{base}_{h[:8]}{ext}")

            result_entry = {"src": src_path, "dst": dst_path, "moved": False}

            if dry_run:
                result_entry["note"] = "dry_run"
            else:
                try:
                    import shutil
                    shutil.move(src_path, dst_path)
                    result_entry["moved"] = True
                except Exception as e:
                    result_entry["error"] = f"move failed: {e}"

            results[src_path] = result_entry

        return results
    except Exception as e:
        return {"error": str(e)}


# -------------------------------
# Run MCP server
# -------------------------------
if __name__ == "__main__":
    #print(f"Starting MCP server using DB: {DB_PATH}")
    server.run()
