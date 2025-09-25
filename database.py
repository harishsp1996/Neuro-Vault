# Complete database.py file with all missing functions

"""
Database module for HelperGPT
SQLite database operations for document metadata and system data
"""

import sqlite3
import aiosqlite
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import os
from pathlib import Path
import json

logger = logging.getLogger(__name__)

DATABASE_PATH = "metadata.db"

async def init_db():
    """Initialize the SQLite database and create tables"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Create documents table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    team TEXT NOT NULL,
                    project TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_date TIMESTAMP,
                    chunk_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    uploaded_by TEXT,
                    description TEXT,
                    metadata TEXT
                )
            """)

            # Create document chunks table for embeddings
            await db.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL,
                    chunk_size INTEGER NOT NULL,
                    embedding_vector TEXT,
                    page_number INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
                )
            """)

            # Create queries table for logging user questions
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    answer TEXT,
                    confidence REAL,
                    response_time_ms INTEGER,
                    team_context TEXT,
                    project_context TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_session TEXT,
                    sources_used TEXT
                )
            """)

            # Create indexes for better query performance
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_team_project 
                ON documents(team, project)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id 
                ON document_chunks(document_id)
            """)

            await db.commit()
            logger.info("Database initialized successfully")

    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}")
        raise

async def get_db_connection():
    """Get database connection"""
    return await aiosqlite.connect(DATABASE_PATH)

async def insert_document(
    filename: str,
    original_filename: str,
    team: str,
    project: str,
    file_type: str,
    file_size: int,
    file_path: str,
    uploaded_by: str = "admin"
) -> int:
    """Insert document record and return document ID"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute("""
                INSERT INTO documents (
                    filename, original_filename, team, project, file_type,
                    file_size, file_path, uploaded_by, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (filename, original_filename, team, project, file_type, 
                  file_size, file_path, uploaded_by))

            document_id = cursor.lastrowid
            await db.commit()

            logger.info(f"Document inserted with ID: {document_id}")
            return document_id

    except Exception as e:
        logger.error(f"Error inserting document: {str(e)}")
        raise

async def insert_document_chunk(
    document_id: int,
    chunk_index: int,
    chunk_text: str,
    embedding_vector: str = None,
    page_number: int = None
) -> int:
    """Insert document chunk and return chunk ID"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute("""
                INSERT INTO document_chunks (
                    document_id, chunk_index, chunk_text, chunk_size,
                    embedding_vector, page_number
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (document_id, chunk_index, chunk_text, len(chunk_text),
                  embedding_vector, page_number))

            chunk_id = cursor.lastrowid
            await db.commit()

            logger.info(f"Document chunk inserted with ID: {chunk_id}")
            return chunk_id

    except Exception as e:
        logger.error(f"Error inserting document chunk: {str(e)}")
        raise

async def update_document_status(
    document_id: int,
    status: str,
    chunk_count: int = None
):
    """Update document processing status"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            if chunk_count is not None:
                await db.execute("""
                    UPDATE documents 
                    SET status = ?, chunk_count = ?, processed_date = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, chunk_count, document_id))
            else:
                await db.execute("""
                    UPDATE documents 
                    SET status = ?
                    WHERE id = ?
                """, (status, document_id))

            await db.commit()
            logger.info(f"Document {document_id} status updated to: {status}")

    except Exception as e:
        logger.error(f"Error updating document status: {str(e)}")
        raise

async def log_user_query(
    question: str,
    answer: str = None,
    confidence: float = None,
    response_time_ms: int = None,
    team_context: str = None,
    project_context: str = None,
    sources_used: List[int] = None,
    user_session: str = None
):
    """Log user query for analytics"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            sources_json = json.dumps(sources_used) if sources_used else None
            
            await db.execute("""
                INSERT INTO user_queries (
                    question, answer, confidence, response_time_ms,
                    team_context, project_context, sources_used, user_session
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (question, answer, confidence, response_time_ms,
                  team_context, project_context, sources_json, user_session))

            await db.commit()
            logger.info("User query logged successfully")

    except Exception as e:
        logger.error(f"Error logging user query: {str(e)}")

async def get_documents_by_team_project(team: str = None, project: str = None) -> List[Dict]:
    """Get documents filtered by team and/or project"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            query = "SELECT * FROM documents"
            params = []

            if team or project:
                conditions = []
                if team:
                    conditions.append("team = ?")
                    params.append(team)
                if project:
                    conditions.append("project = ?")
                    params.append(project)
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY upload_date DESC"

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

            documents = []
            for row in rows:
                documents.append({
                    "id": row[0],
                    "filename": row[1],
                    "original_filename": row[2],
                    "team": row[3],
                    "project": row[4],
                    "file_type": row[5],
                    "file_size": row[6],
                    "file_path": row[7],
                    "upload_date": row[8],
                    "processed_date": row[9],
                    "chunk_count": row[10],
                    "status": row[11],
                    "uploaded_by": row[12],
                    "description": row[13],
                    "metadata": row[14]
                })

            return documents

    except Exception as e:
        logger.error(f"Error getting documents: {str(e)}")
        return []

async def get_document_by_id(document_id: int) -> Optional[Dict]:
    """Get document by ID"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
            row = await cursor.fetchone()

            if row:
                return {
                    "id": row[0],
                    "filename": row[1],
                    "original_filename": row[2],
                    "team": row[3],
                    "project": row[4],
                    "file_type": row[5],
                    "file_size": row[6],
                    "file_path": row[7],
                    "upload_date": row[8],
                    "processed_date": row[9],
                    "chunk_count": row[10],
                    "status": row[11],
                    "uploaded_by": row[12],
                    "description": row[13],
                    "metadata": row[14]
                }
            return None

    except Exception as e:
        logger.error(f"Error getting document by ID: {str(e)}")
        return None

async def delete_document_by_id(document_id: int) -> bool:
    """Delete document and its chunks"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Delete chunks first (foreign key constraint)
            await db.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))
            
            # Delete document
            cursor = await db.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            await db.commit()

            return cursor.rowcount > 0

    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        return False

async def get_database_stats() -> Dict[str, Any]:
    """Get database statistics"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            stats = {}

            # Count documents
            cursor = await db.execute("SELECT COUNT(*) FROM documents")
            stats["total_documents"] = (await cursor.fetchone())[0]

            # Count chunks
            cursor = await db.execute("SELECT COUNT(*) FROM document_chunks")
            stats["total_chunks"] = (await cursor.fetchone())[0]

            # Count queries
            cursor = await db.execute("SELECT COUNT(*) FROM user_queries")
            stats["total_queries"] = (await cursor.fetchone())[0]

            # Get processing status breakdown
            cursor = await db.execute("""
                SELECT status, COUNT(*) 
                FROM documents 
                GROUP BY status
            """)
            status_breakdown = await cursor.fetchall()
            stats["status_breakdown"] = {status: count for status, count in status_breakdown}

            # Get team breakdown
            cursor = await db.execute("""
                SELECT team, COUNT(*) 
                FROM documents 
                GROUP BY team
            """)
            team_breakdown = await cursor.fetchall()
            stats["team_breakdown"] = {team: count for team, count in team_breakdown}

            return stats

    except Exception as e:
        logger.error(f"Error getting database stats: {str(e)}")
        return {}

async def cleanup_orphaned_chunks():
    """Remove document chunks that don't have parent documents"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute("""
                DELETE FROM document_chunks 
                WHERE document_id NOT IN (SELECT id FROM documents)
            """)
            await db.commit()

            deleted_count = cursor.rowcount
            logger.info(f"Cleaned up {deleted_count} orphaned chunks")
            return deleted_count

    except Exception as e:
        logger.error(f"Error cleaning up orphaned chunks: {str(e)}")
        return 0

async def get_recent_queries(limit: int = 10) -> List[Dict]:
    """Get recent user queries"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute("""
                SELECT question, confidence, response_time_ms, created_at
                FROM user_queries 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
            
            rows = await cursor.fetchall()
            queries = []
            for row in rows:
                queries.append({
                    "question": row[0],
                    "confidence": row[1],
                    "response_time_ms": row[2],
                    "created_at": row[3]
                })

            return queries

    except Exception as e:
        logger.error(f"Error getting recent queries: {str(e)}")
        return []
