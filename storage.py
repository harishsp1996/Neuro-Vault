"""
Storage module for HelperGPT
File upload, storage, and retrieval operations
"""

import os
import aiofiles
import shutil
from pathlib import Path
from typing import Optional
from fastapi import UploadFile, HTTPException
import logging
import hashlib
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

UPLOAD_FOLDER = "uploads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.doc', '.docx'}

async def ensure_upload_directory():
    """Ensure upload directory structure exists"""
    try:
        Path(UPLOAD_FOLDER).mkdir(exist_ok=True)
        logger.info(f"Upload directory ensured: {UPLOAD_FOLDER}")
    except Exception as e:
        logger.error(f"Error creating upload directory: {str(e)}")
        raise

async def validate_file(file: UploadFile) -> bool:
    """Validate uploaded file"""
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file_ext} not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size ({file_size} bytes) exceeds limit ({MAX_FILE_SIZE} bytes)"
        )

    return True

async def save_uploaded_file(file: UploadFile, team: str, project: str) -> str:
    """Save uploaded file to storage"""
    try:
        await ensure_upload_directory()
        await validate_file(file)

        # Create team/project directory structure
        team_dir = Path(UPLOAD_FOLDER) / team
        project_dir = team_dir / project
        project_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename to avoid conflicts
        file_ext = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
        file_path = project_dir / unique_filename

        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)

        logger.info(f"File saved: {file_path}")
        return str(file_path)

    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

def get_file_path(filename: str, team: str, project: str) -> str:
    """Get full path for a file"""
    return os.path.join(UPLOAD_FOLDER, team, project, filename)

async def delete_file(file_path: str) -> bool:
    """Delete a file from storage"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"File deleted: {file_path}")
            return True
        else:
            logger.warning(f"File not found for deletion: {file_path}")
            return False
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        return False

async def get_file_info(file_path: str) -> Optional[dict]:
    """Get file information"""
    try:
        if not os.path.exists(file_path):
            return None

        stat = os.stat(file_path)
        return {
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime),
            "exists": True
        }
    except Exception as e:
        logger.error(f"Error getting file info: {str(e)}")
        return None

async def calculate_file_hash(file_path: str) -> str:
    """Calculate MD5 hash of file for duplicate detection"""
    try:
        hash_md5 = hashlib.md5()
        async with aiofiles.open(file_path, 'rb') as f:
            async for chunk in f:
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating file hash: {str(e)}")
        return ""

async def get_storage_stats() -> dict:
    """Get storage utilization statistics"""
    try:
        total_size = 0
        file_count = 0

        for root, dirs, files in os.walk(UPLOAD_FOLDER):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    total_size += os.path.getsize(file_path)
                    file_count += 1
                except OSError:
                    continue

        return {
            "total_files": file_count,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "upload_folder": UPLOAD_FOLDER
        }
    except Exception as e:
        logger.error(f"Error getting storage stats: {str(e)}")
        return {}

async def cleanup_orphaned_files():
    """Remove files that don't have database records"""
    try:
        from app.database import get_db_connection

        # Get all file paths from database
        async with get_db_connection() as db:
            cursor = await db.execute("SELECT file_path FROM documents")
            db_files = {row[0] for row in await cursor.fetchall()}

        # Get all physical files
        physical_files = set()
        for root, dirs, files in os.walk(UPLOAD_FOLDER):
            for file in files:
                physical_files.add(os.path.join(root, file))

        # Find orphaned files
        orphaned_files = physical_files - db_files

        # Delete orphaned files
        deleted_count = 0
        for file_path in orphaned_files:
            try:
                os.remove(file_path)
                deleted_count += 1
                logger.info(f"Deleted orphaned file: {file_path}")
            except OSError as e:
                logger.warning(f"Could not delete orphaned file {file_path}: {str(e)}")

        logger.info(f"Cleanup complete. Deleted {deleted_count} orphaned files.")
        return deleted_count

    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        return 0

# File type detection utilities
def get_file_type(filename: str) -> str:
    """Get file type from filename"""
    return Path(filename).suffix.lower().replace('.', '')

def is_supported_file_type(filename: str) -> bool:
    """Check if file type is supported"""
    file_ext = Path(filename).suffix.lower()
    return file_ext in ALLOWED_EXTENSIONS

async def create_backup(source_path: str, backup_dir: str = "backups") -> str:
    """Create backup of important files"""
    try:
        backup_path = Path(backup_dir)
        backup_path.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}_{Path(source_path).name}"
        backup_file_path = backup_path / backup_filename

        shutil.copy2(source_path, backup_file_path)
        logger.info(f"Backup created: {backup_file_path}")

        return str(backup_file_path)
    except Exception as e:
        logger.error(f"Backup creation error: {str(e)}")
        raise
