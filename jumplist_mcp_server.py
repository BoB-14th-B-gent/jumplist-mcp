"""
JumpList MCP Server v2.0 - With SQLite Caching

FastMCP-based MCP server for parsing Windows JumpList artifacts.
Enhanced with SQLite caching for better performance and memory efficiency.

Workflow Integration:
1. TSK MCP extracts files from disk image (E01/DD)
2. JumpList files extracted to directory
3. This MCP parses and caches results in SQLite
4. Results sent to Claude Desktop (Agent)
5. Optionally export to Elasticsearch (SIEM)

Environment:
- Windows 10/11
- CLI-based (no GUI)
- venv Python environment
- Claude Desktop Agent integration

Author: Digital Forensics Team
Version: 2.0.0
"""

import os
import sys
import subprocess
import csv
import json
import tempfile
import shutil
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Iterator
from dataclasses import dataclass, asdict

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("jumplist-mcp-v2")


@dataclass
class JumpListEvent:
    """Normalized JumpList timeline event"""
    source: str
    artifact: str
    timestamp_utc: str
    app_id: str
    target_path: str
    target_created_utc: Optional[str] = None
    target_modified_utc: Optional[str] = None
    target_accessed_utc: Optional[str] = None
    file_size: Optional[int] = None
    machine_id: Optional[str] = None
    volume_serial: Optional[str] = None
    entry_number: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values"""
        result = {}
        for key, value in asdict(self).items():
            if value is not None:
                result[key] = value
        return result


class JumpListCache:
    """SQLite-based cache for JumpList parsing results"""
    
    def __init__(self, cache_path: Optional[str] = None):
        """
        Initialize cache
        
        Args:
            cache_path: Path to SQLite database (defaults to ~/.jumplist_cache.db)
        """
        if cache_path is None:
            # Default cache location in project directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            cache_path = os.path.join(script_dir, '.jumplist_cache.db')
        
        self.cache_path = cache_path
        self.db = sqlite3.connect(cache_path)
        self.db.row_factory = sqlite3.Row
        self._init_database()
    
    def _init_database(self):
        """Create database schema"""
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS source_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filepath TEXT UNIQUE NOT NULL,
                file_hash TEXT NOT NULL,
                file_mtime INTEGER NOT NULL,
                parsed_at TEXT NOT NULL
            )
        ''')
        
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                artifact TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                app_id TEXT NOT NULL,
                target_path TEXT NOT NULL,
                target_created_utc TEXT,
                target_modified_utc TEXT,
                target_accessed_utc TEXT,
                file_size INTEGER,
                machine_id TEXT,
                volume_serial TEXT,
                entry_number INTEGER,
                FOREIGN KEY (source_file_id) REFERENCES source_files(id)
            )
        ''')
        
        # Create indexes for fast queries
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON events(timestamp_utc)')
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_app_id ON events(app_id)')
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_target_path ON events(target_path)')
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_source_file ON events(source_file_id)')
        
        self.db.commit()
    
    def _get_file_hash(self, filepath: str) -> str:
        """Calculate MD5 hash of file for change detection"""
        hasher = hashlib.md5()
        with open(filepath, 'rb') as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _is_file_cached(self, jumplist_dir: str) -> bool:
        """Check if directory is already cached and unchanged"""
        try:
            cache_key = os.path.join(jumplist_dir, "_combined_cache.marker")
            
            # For directory caching, we check if ANY jumplist files changed
            # Get modification time of most recent file in directory
            jumplist_files = []
            if os.path.isdir(jumplist_dir):
                for ext in ['*.automaticDestinations-ms', '*.customDestinations-ms']:
                    jumplist_files.extend(Path(jumplist_dir).glob(ext))
            
            if not jumplist_files:
                return False
            
            # Get most recent mtime
            latest_mtime = max(os.stat(f).st_mtime for f in jumplist_files)
            
            # Calculate hash of all files (simplified - just check mtimes)
            file_hash = hashlib.md5(
                str(sorted([(f.name, os.stat(f).st_mtime) for f in jumplist_files])).encode()
            ).hexdigest()
            
            cursor = self.db.execute('''
                SELECT id FROM source_files
                WHERE filepath = ? AND file_hash = ?
            ''', (cache_key, file_hash))
            
            return cursor.fetchone() is not None
        except Exception as e:
            print(f"Warning: Cache check failed: {e}", file=sys.stderr)
            return False
    
    def get_cached_events(self, jumplist_dir: str) -> Optional[List[JumpListEvent]]:
        """Get all cached events for a directory"""
        try:
            # Look for the synthetic cache marker
            cache_key = os.path.join(jumplist_dir, "_combined_cache.marker")
            
            cursor = self.db.execute('''
                SELECT e.* FROM events e
                JOIN source_files sf ON e.source_file_id = sf.id
                WHERE sf.filepath = ?
            ''', (cache_key,))
            
            rows = cursor.fetchall()
            if not rows:
                return None
            
            events = []
            for row in rows:
                event = JumpListEvent(
                    source=row['source'],
                    artifact=row['artifact'],
                    timestamp_utc=row['timestamp_utc'],
                    app_id=row['app_id'],
                    target_path=row['target_path'],
                    target_created_utc=row['target_created_utc'],
                    target_modified_utc=row['target_modified_utc'],
                    target_accessed_utc=row['target_accessed_utc'],
                    file_size=row['file_size'],
                    machine_id=row['machine_id'],
                    volume_serial=row['volume_serial'],
                    entry_number=row['entry_number']
                )
                events.append(event)
            
            print(f"✓ Loaded {len(events)} events from cache", file=sys.stderr)
            return events
        except Exception as e:
            print(f"Warning: Failed to get cached events: {e}", file=sys.stderr)
            return None
    
    def save_events(self, cache_key: str, events: List[JumpListEvent]):
        """Save parsed events to cache"""
        try:
            # For directory-based caching, calculate hash of all jumplist files
            jumplist_dir = os.path.dirname(cache_key)
            jumplist_files = []
            if os.path.isdir(jumplist_dir):
                for ext in ['*.automaticDestinations-ms', '*.customDestinations-ms']:
                    jumplist_files.extend(Path(jumplist_dir).glob(ext))
            
            if not jumplist_files:
                print(f"Warning: No jumplist files found in {jumplist_dir}", file=sys.stderr)
                return
            
            # Get latest mtime
            latest_mtime = int(max(os.stat(f).st_mtime for f in jumplist_files))
            
            # Calculate hash
            file_hash = hashlib.md5(
                str(sorted([(f.name, os.stat(f).st_mtime) for f in jumplist_files])).encode()
            ).hexdigest()
            
            # Delete old cache for this directory
            self.db.execute('DELETE FROM source_files WHERE filepath = ?', (cache_key,))
            
            # Insert source file record
            cursor = self.db.execute('''
                INSERT INTO source_files (filepath, file_hash, file_mtime, parsed_at)
                VALUES (?, ?, ?, ?)
            ''', (cache_key, file_hash, latest_mtime, datetime.utcnow().isoformat()))
            
            source_file_id = cursor.lastrowid
            
            # Insert events
            for event in events:
                self.db.execute('''
                    INSERT INTO events (
                        source_file_id, source, artifact, timestamp_utc, app_id, target_path,
                        target_created_utc, target_modified_utc, target_accessed_utc,
                        file_size, machine_id, volume_serial, entry_number
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    source_file_id, event.source, event.artifact, event.timestamp_utc,
                    event.app_id, event.target_path, event.target_created_utc,
                    event.target_modified_utc, event.target_accessed_utc, event.file_size,
                    event.machine_id, event.volume_serial, event.entry_number
                ))
            
            self.db.commit()
            print(f"✓ Successfully cached {len(events)} events", file=sys.stderr)
        
        except Exception as e:
            print(f"Warning: Failed to save cache: {e}", file=sys.stderr)
            self.db.rollback()
    
    def query_sql(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute custom SQL query"""
        cursor = self.db.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {}
        
        # Total events
        cursor = self.db.execute('SELECT COUNT(*) as count FROM events')
        stats['total_events'] = cursor.fetchone()['count']
        
        # Total files
        cursor = self.db.execute('SELECT COUNT(*) as count FROM source_files')
        stats['total_files'] = cursor.fetchone()['count']
        
        # Cache size
        stats['cache_size_mb'] = os.path.getsize(self.cache_path) / (1024 * 1024)
        
        # Unique apps
        cursor = self.db.execute('SELECT COUNT(DISTINCT app_id) as count FROM events')
        stats['unique_apps'] = cursor.fetchone()['count']
        
        return stats
    
    def clear_cache(self):
        """Clear all cached data"""
        self.db.execute('DELETE FROM events')
        self.db.execute('DELETE FROM source_files')
        self.db.commit()
        print("✓ Cache cleared", file=sys.stderr)


class JLECmdParser:
    """Wrapper for JLECmd.exe execution and CSV parsing"""
    
    def __init__(self, jlecmd_path: Optional[str] = None):
        """Initialize JLECmd parser"""
        self.jlecmd_path = jlecmd_path or self._find_jlecmd()
        
    def _find_jlecmd(self) -> str:
        """Find JLECmd.exe in PATH or environment variable"""
        # Check environment variable
        env_path = os.environ.get('JLECMD_PATH')
        if env_path and os.path.exists(env_path):
            return env_path
        
        # Check relative path (project directory)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        default_path = os.path.join(script_dir, 'tools', 'JLECmd', 'JLECmd.exe')
        if os.path.exists(default_path):
            return default_path
        
        # Check system PATH
        if sys.platform == "win32":
            cmd = "JLECmd.exe"
        else:
            cmd = "JLECmd.exe"
        
        if shutil.which(cmd):
            return cmd
            
        # Check common locations
        common_paths = [
            r"C:\Tools\JLECmd.exe",
            r"C:\Tools\JLECmd\JLECmd.exe",
            r"C:\Program Files\JLECmd\JLECmd.exe"
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
                
        raise FileNotFoundError(
            "JLECmd.exe not found. Please install it or specify path. "
            "Download from: https://ericzimmerman.github.io/"
        )
    
    def parse_jumplist_dir(self, jumplist_dir: str, output_dir: str) -> str:
        """Execute JLECmd.exe on jumplist directory"""
        if not os.path.isdir(jumplist_dir):
            raise ValueError(f"JumpList directory not found: {jumplist_dir}")
        
        cmd = [
            self.jlecmd_path,
            "-d", jumplist_dir,
            "--csv", output_dir,
            "-q"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                raise RuntimeError(
                    f"JLECmd.exe failed with code {result.returncode}\n"
                    f"STDERR: {result.stderr}"
                )
            
            csv_files = list(Path(output_dir).glob("*.csv"))
            
            if not csv_files:
                raise RuntimeError("JLECmd.exe did not generate any CSV files")
            
            return str(csv_files[0]) if len(csv_files) == 1 else self._merge_csv_files(csv_files)
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("JLECmd.exe execution timed out (5 minutes)")
        except FileNotFoundError:
            raise FileNotFoundError(f"JLECmd.exe not found at: {self.jlecmd_path}")
    
    def _merge_csv_files(self, csv_files: List[Path]) -> str:
        """Merge multiple CSV files"""
        merged_file = csv_files[0].parent / "merged_jumplist.csv"
        
        with open(merged_file, 'w', newline='', encoding='utf-8') as outfile:
            writer = None
            
            for csv_file in csv_files:
                with open(csv_file, 'r', encoding='utf-8') as infile:
                    reader = csv.DictReader(infile)
                    
                    if writer is None:
                        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
                        writer.writeheader()
                    
                    for row in reader:
                        writer.writerow(row)
        
        return str(merged_file)
    
    def csv_to_events(self, csv_path: str) -> List[JumpListEvent]:
        """Parse JLECmd CSV output into normalized events"""
        events = []
        
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                try:
                    event = self._parse_csv_row(row)
                    if event:
                        events.append(event)
                except Exception as e:
                    print(f"Warning: Failed to parse row: {e}", file=sys.stderr)
                    continue
        
        return events
    
    def _parse_csv_row(self, row: Dict[str, str]) -> Optional[JumpListEvent]:
        """Parse a single CSV row into JumpListEvent"""
        if not row.get('Path'):
            return None
        
        timestamp = self._parse_timestamp(
            row.get('TargetModified') or row.get('TargetAccessed') or row.get('TargetCreated')
        )
        
        if not timestamp:
            return None
        
        event = JumpListEvent(
            source="jumplist",
            artifact="recent_item",
            timestamp_utc=timestamp,
            app_id=row.get('AppId', 'unknown'),
            target_path=row.get('Path', ''),
            target_created_utc=self._parse_timestamp(row.get('TargetCreated')),
            target_modified_utc=self._parse_timestamp(row.get('TargetModified')),
            target_accessed_utc=self._parse_timestamp(row.get('TargetAccessed')),
            file_size=self._parse_int(row.get('FileSize')),
            machine_id=row.get('MachineID'),
            volume_serial=row.get('VolumeSerialNumber'),
            entry_number=self._parse_int(row.get('EntryNumber'))
        )
        
        return event
    
    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[str]:
        """Parse timestamp string to ISO8601 UTC format"""
        if not timestamp_str or timestamp_str.strip() == '':
            return None
        
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %I:%M:%S %p",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(timestamp_str.strip(), fmt)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue
        
        print(f"Warning: Could not parse timestamp: {timestamp_str}", file=sys.stderr)
        return timestamp_str
    
    def _parse_int(self, value: Optional[str]) -> Optional[int]:
        """Safely parse integer value"""
        if not value or value.strip() == '':
            return None
        try:
            return int(value.strip())
        except ValueError:
            return None


def filter_events_by_time(
    events: List[JumpListEvent],
    time_from: Optional[str],
    time_to: Optional[str]
) -> List[JumpListEvent]:
    """Filter events by timestamp range"""
    if not time_from and not time_to:
        return events
    
    filtered = []
    time_from_dt = datetime.fromisoformat(time_from.replace('Z', '+00:00')) if time_from else None
    time_to_dt = datetime.fromisoformat(time_to.replace('Z', '+00:00')) if time_to else None
    
    for event in events:
        try:
            event_dt = datetime.fromisoformat(event.timestamp_utc.replace('Z', '+00:00'))
            
            if time_from_dt and event_dt < time_from_dt:
                continue
            if time_to_dt and event_dt > time_to_dt:
                continue
            
            filtered.append(event)
            
        except Exception as e:
            print(f"Warning: Could not parse event timestamp: {e}", file=sys.stderr)
            continue
    
    return filtered


@mcp.tool()
def parse_jumplists(
    jumplist_dir: str,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    jlecmd_path: Optional[str] = None,
    limit: Optional[int] = 100,
    sort_by: str = "timestamp",
    use_cache: bool = True
) -> List[Dict[str, Any]]:
    """
    Parse Windows JumpList files with SQLite caching
    
    Workflow:
    1. Check SQLite cache for unchanged files
    2. Parse only new/modified files with JLECmd.exe
    3. Cache results for future queries
    4. Return limited, sorted results
    
    Args:
        jumplist_dir: Directory containing JumpList files (from TSK extraction)
        time_from: Optional ISO8601 UTC start time
        time_to: Optional ISO8601 UTC end time
        jlecmd_path: Optional path to JLECmd.exe
        limit: Maximum number of events (default: 100, 0 for unlimited)
        sort_by: Sort order - "timestamp" or "path"
        use_cache: Use SQLite cache (default: True)
    
    Returns:
        List of normalized JumpList events
    
    Example:
        >>> events = parse_jumplists(
        ...     jumplist_dir="D:/tsk_extracted/jumplists",
        ...     time_from="2025-12-01T00:00:00Z",
        ...     limit=50
        ... )
    """
    # Validate input
    if not os.path.isdir(jumplist_dir):
        raise ValueError(f"JumpList directory not found: {jumplist_dir}")
    
    # Initialize cache
    cache = JumpListCache() if use_cache else None
    
    # Try to get from cache
    if cache:
        cached_events = cache.get_cached_events(jumplist_dir)
        if cached_events:
            print(f"✓ Loaded {len(cached_events)} events from cache", file=sys.stderr)
            events = cached_events
        else:
            # Parse and cache
            events = _parse_and_cache(jumplist_dir, jlecmd_path, cache)
    else:
        # Parse without cache
        events = _parse_without_cache(jumplist_dir, jlecmd_path)
    
    # Filter by time
    events = filter_events_by_time(events, time_from, time_to)
    
    # Sort
    if sort_by == "timestamp":
        events.sort(key=lambda e: e.timestamp_utc, reverse=True)
    elif sort_by == "path":
        events.sort(key=lambda e: e.target_path)
    
    # Apply limit
    if limit and limit > 0:
        total_count = len(events)
        events = events[:limit]
        if total_count > limit:
            print(f"Note: Showing {limit} of {total_count} events", file=sys.stderr)
    
    return [event.to_dict() for event in events]


def _parse_and_cache(jumplist_dir: str, jlecmd_path: Optional[str], cache: JumpListCache) -> List[JumpListEvent]:
    """Parse JumpLists and cache results"""
    with tempfile.TemporaryDirectory() as temp_dir:
        parser = JLECmdParser(jlecmd_path)
        csv_path = parser.parse_jumplist_dir(jumplist_dir, temp_dir)
        events = parser.csv_to_events(csv_path)
        
        # Cache results - use a synthetic "combined" filepath
        # Since JLECmd processes entire directory, we store as one entry
        if events:
            # Create a synthetic filepath representing the entire directory
            cache_key = os.path.join(jumplist_dir, "_combined_cache.marker")
            cache.save_events(cache_key, events)
            print(f"✓ Cached {len(events)} events from {jumplist_dir}", file=sys.stderr)
        
        return events


def _parse_without_cache(jumplist_dir: str, jlecmd_path: Optional[str]) -> List[JumpListEvent]:
    """Parse JumpLists without caching"""
    with tempfile.TemporaryDirectory() as temp_dir:
        parser = JLECmdParser(jlecmd_path)
        csv_path = parser.parse_jumplist_dir(jumplist_dir, temp_dir)
        return parser.csv_to_events(csv_path)


@mcp.tool()
def get_jumplist_statistics(
    jumplist_dir: str,
    jlecmd_path: Optional[str] = None,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Get comprehensive statistics about JumpList artifacts
    
    Args:
        jumplist_dir: Directory containing JumpList files
        jlecmd_path: Optional path to JLECmd.exe
        use_cache: Use SQLite cache
    
    Returns:
        Statistics including TOP 10 apps, file types, recent files
    """
    # Parse all events (no limit)
    events_dict = parse_jumplists(
        jumplist_dir,
        jlecmd_path=jlecmd_path,
        limit=0,
        use_cache=use_cache
    )
    events = [JumpListEvent(**e) for e in events_dict]
    
    if not events:
        return {
            "total_events": 0,
            "unique_apps": 0,
            "date_range": None,
            "top_apps": [],
            "top_extensions": [],
            "recent_files": []
        }
    
    # Calculate statistics
    unique_apps = set(e.app_id for e in events)
    
    # Count app usage
    app_counts = {}
    for e in events:
        app_counts[e.app_id] = app_counts.get(e.app_id, 0) + 1
    
    # TOP 10 apps
    top_apps = sorted(app_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Parse timestamps for date range
    timestamps = []
    for e in events:
        try:
            dt = datetime.fromisoformat(e.timestamp_utc.replace('Z', '+00:00'))
            timestamps.append(dt)
        except:
            continue
    
    date_range = None
    if timestamps:
        date_range = {
            "earliest": min(timestamps).isoformat(),
            "latest": max(timestamps).isoformat()
        }
    
    # Count file extensions
    file_extensions = {}
    for e in events:
        if e.target_path:
            ext = Path(e.target_path).suffix.lower()
            if ext:
                file_extensions[ext] = file_extensions.get(ext, 0) + 1
    
    # TOP 10 extensions
    top_extensions = sorted(file_extensions.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Most recent 10 files
    events_sorted = sorted(events, key=lambda e: e.timestamp_utc, reverse=True)
    recent_files = [
        {
            "timestamp": e.timestamp_utc,
            "app": e.app_id,
            "path": e.target_path
        }
        for e in events_sorted[:10]
    ]
    
    return {
        "total_events": len(events),
        "unique_apps": len(unique_apps),
        "date_range": date_range,
        "top_apps": [{"app": app, "count": count} for app, count in top_apps],
        "top_extensions": [{"extension": ext, "count": count} for ext, count in top_extensions],
        "recent_files": recent_files,
        "app_list": sorted(list(unique_apps))
    }


@mcp.tool()
def search_jumplists(
    jumplist_dir: str,
    keyword: str,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    jlecmd_path: Optional[str] = None,
    limit: Optional[int] = 50,
    use_cache: bool = True
) -> List[Dict[str, Any]]:
    """
    Search JumpList events by keyword in file path
    
    Args:
        jumplist_dir: Directory containing JumpList files
        keyword: Keyword to search (case-insensitive)
        time_from: Optional start time
        time_to: Optional end time
        jlecmd_path: Optional path to JLECmd.exe
        limit: Maximum results (default: 50)
        use_cache: Use SQLite cache
    
    Returns:
        List of matching events
    """
    # Parse all events
    events = parse_jumplists(
        jumplist_dir=jumplist_dir,
        time_from=time_from,
        time_to=time_to,
        jlecmd_path=jlecmd_path,
        limit=0,
        use_cache=use_cache
    )
    
    # Filter by keyword
    keyword_lower = keyword.lower()
    matching = [
        e for e in events
        if keyword_lower in e.get('target_path', '').lower()
    ]
    
    # Sort by timestamp (newest first)
    matching.sort(key=lambda e: e.get('timestamp_utc', ''), reverse=True)
    
    # Apply limit
    if limit and limit > 0:
        matching = matching[:limit]
    
    return matching


@mcp.tool()
def get_cache_info() -> Dict[str, Any]:
    """
    Get SQLite cache information and statistics
    
    Returns:
        Cache statistics including size, event count, file count
    """
    cache = JumpListCache()
    return cache.get_statistics()


@mcp.tool()
def clear_cache() -> Dict[str, str]:
    """
    Clear all cached JumpList data
    
    Returns:
        Status message
    """
    cache = JumpListCache()
    cache.clear_cache()
    return {"status": "success", "message": "Cache cleared"}


if __name__ == "__main__":
    # Run the MCP server
    # Supports STDIO transport for Claude Desktop
    mcp.run()
