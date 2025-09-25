"""
Embeddings module for HelperGPT
Vector embeddings generation using Azure OpenAI and FAISS similarity search
"""
import os
import json
import numpy as np
import faiss
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import asyncio
import aiofiles
from openai import AsyncAzureOpenAI
from dotenv import load_dotenv
from database import insert_document_chunk, update_document_status, get_db_connection, insert_document
from utils import chunk_text
from storage import get_file_path

load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "faiss_index.bin")
EMBEDDING_DIMENSION = 1536  # Azure OpenAI Ada-002 embedding dimension

azure_openai_client = AsyncAzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

class EmbeddingManager:
    def __init__(self):
        self.index = None
        self.document_metadata = []
        self.is_loaded = False

    async def load_index(self):
        try:
            if os.path.exists(FAISS_INDEX_PATH):
                logger.info(f"Loading FAISS index from {FAISS_INDEX_PATH}...")
                self.index = faiss.read_index(FAISS_INDEX_PATH)
                logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors")
            else:
                logger.info("No existing FAISS index found. Creating new index...")
                self.index = faiss.IndexFlatIP(EMBEDDING_DIMENSION)
            await self.load_metadata()
            self.is_loaded = True
        except Exception as e:
            logger.error(f"Error loading FAISS index: {str(e)}")
            self.index = faiss.IndexFlatIP(EMBEDDING_DIMENSION)
            self.document_metadata = []

    async def load_metadata(self):
        try:
            logger.info("Loading document chunk metadata from database...")
            # FIXED: Properly await the connection and close it
            conn = await get_db_connection()
            cursor = await conn.execute("""
                SELECT dc.id, dc.document_id, dc.chunk_index, dc.page_number,
                       d.filename, d.team, d.project
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE d.status = 'completed'
                ORDER BY dc.document_id, dc.chunk_index
            """)
            rows = await cursor.fetchall()
            await conn.close()
            
            self.document_metadata = []
            for row in rows:
                self.document_metadata.append({
                    "chunk_id": row[0],
                    "document_id": row[1],
                    "chunk_index": row[2],
                    "page_number": row[3],
                    "filename": row[4],
                    "team": row[5],
                    "project": row[6]
                })
            logger.info(f"Loaded {len(self.document_metadata)} chunk metadata records")
        except Exception as e:
            logger.error(f"Error loading metadata: {str(e)}")
            self.document_metadata = []

    async def save_index(self):
        try:
            if self.index:
                faiss.write_index(self.index, FAISS_INDEX_PATH)
                logger.info(f"Saved FAISS index to {FAISS_INDEX_PATH}")
        except Exception as e:
            logger.error(f"Error saving FAISS index: {str(e)}")

embedding_manager = EmbeddingManager()

async def generate_embedding(text: str) -> List[float]:
    try:
        response = await azure_openai_client.embeddings.create(
            input=text,
            model=EMBEDDING_DEPLOYMENT
        )
        embedding = response.data[0].embedding
        logger.debug("Generated embedding of length %d", len(embedding))
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        raise

async def process_document(filename: str, text_content: str, team: str, project: str) -> int:
    try:
        if not embedding_manager.is_loaded:
            await embedding_manager.load_index()

        logger.info(f"Inserting document record for '{filename}'")
        # FIXED: Added original_filename parameter
        document_id = await insert_document(
            filename=filename,
            original_filename=filename,  # Added this line
            team=team,
            project=project,
            file_type=filename.split('.')[-1].lower(),
            file_size=len(text_content.encode('utf-8')),
            file_path=get_file_path(filename, team, project)
        )
        logger.info(f"Document ID {document_id} created, updating status to processing")
        await update_document_status(document_id, "processing")

        chunks = chunk_text(text_content)
        logger.info(f"Text chunked into {len(chunks)} pieces for document ID {document_id}")

        if not chunks:
            logger.warning(f"No chunks created for document {filename}")
            await update_document_status(document_id, "error")
            return document_id

        embeddings = []
        chunk_metadata = []
        for i, chunk in enumerate(chunks):
            try:
                embedding = await generate_embedding(chunk)
                embeddings.append(embedding)
                chunk_id = await insert_document_chunk(
                    document_id=document_id,
                    chunk_index=i,
                    chunk_text=chunk,
                    embedding_vector=json.dumps(embedding)
                )
                chunk_metadata.append({
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "chunk_index": i,
                    "filename": filename,
                    "team": team,
                    "project": project
                })
                logger.info(f"Processed chunk {i+1}/{len(chunks)} for document ID {document_id}")
            except Exception as e:
                logger.error(f"Error processing chunk {i} for document ID {document_id}: {str(e)}")
                continue

        if embeddings:
            embeddings_array = np.array(embeddings, dtype=np.float32)
            faiss.normalize_L2(embeddings_array)
            embedding_manager.index.add(embeddings_array)
            embedding_manager.document_metadata.extend(chunk_metadata)
            await embedding_manager.save_index()
            logger.info(f"Added {len(embeddings)} embeddings to FAISS index")

        await update_document_status(document_id, "completed", len(chunks))
        logger.info(f"Completed processing document '{filename}' with ID {document_id}")
        return document_id

    except Exception as e:
        logger.error(f"Error processing document '{filename}': {str(e)}")
        if 'document_id' in locals():
            await update_document_status(document_id, "error")
        raise

async def search_similar_documents(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    try:
        logger.info(f"Searching for similar documents with query: '{query}'")
        
        if not embedding_manager.is_loaded:
            await embedding_manager.load_index()
        
        if embedding_manager.index.ntotal == 0:
            logger.warning("No vectors in FAISS index")
            return []
        
        query_embedding = await generate_embedding(query)
        query_vector = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query_vector)
        
        scores, indices = embedding_manager.index.search(query_vector, limit)
        results = []
        
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(embedding_manager.document_metadata):
                metadata = embedding_manager.document_metadata[idx]
                # FIXED: Properly await the connection and close it
                conn = await get_db_connection()
                cursor = await conn.execute("""
                    SELECT chunk_text, page_number FROM document_chunks
                    WHERE id = ?
                """, (metadata["chunk_id"],))
                chunk_data = await cursor.fetchone()
                await conn.close()
                
                if chunk_data:
                    result = {
                        "document_id": metadata["document_id"],
                        "filename": metadata["filename"],
                        "team": metadata["team"],
                        "project": metadata["project"],
                        "chunk_text": chunk_data[0],
                        "page_number": chunk_data[1],
                        "similarity_score": float(score),
                        "chunk_index": metadata["chunk_index"]
                    }
                    results.append(result)
                    logger.info(f"Found match: {metadata['filename']} (score: {score:.3f})")
        
        logger.info(f"Found {len(results)} similar documents for query: '{query}'")
        return results
        
    except Exception as e:
        logger.error(f"Error searching documents for query '{query}': {str(e)}")
        return []

async def reindex_all_documents():
    """Reindex all documents in the database"""
    try:
        logger.info("Starting reindex of all documents...")
        
        # Clear existing index
        embedding_manager.index = faiss.IndexFlatIP(EMBEDDING_DIMENSION)
        embedding_manager.document_metadata = []
        
        # Get all processed documents
        conn = await get_db_connection()
        cursor = await conn.execute("""
            SELECT id, filename, team, project FROM documents 
            WHERE status = 'completed'
        """)
        documents = await cursor.fetchall()
        await conn.close()
        
        logger.info(f"Found {len(documents)} completed documents to reindex")
        
        # Process each document
        for doc in documents:
            doc_id, filename, team, project = doc
            
            # Get chunks for this document
            conn = await get_db_connection()
            cursor = await conn.execute("""
                SELECT chunk_text, chunk_index, id FROM document_chunks
                WHERE document_id = ?
                ORDER BY chunk_index
            """, (doc_id,))
            chunks = await cursor.fetchall()
            await conn.close()
            
            # Generate embeddings for chunks
            embeddings = []
            for chunk_text, chunk_index, chunk_id in chunks:
                try:
                    embedding = await generate_embedding(chunk_text)
                    embeddings.append(embedding)
                    
                    # Update embedding in database
                    conn = await get_db_connection()
                    await conn.execute("""
                        UPDATE document_chunks 
                        SET embedding_vector = ?
                        WHERE id = ?
                    """, (json.dumps(embedding), chunk_id))
                    await conn.commit()
                    await conn.close()
                    
                    # Add to metadata
                    embedding_manager.document_metadata.append({
                        "chunk_id": chunk_id,
                        "document_id": doc_id,
                        "chunk_index": chunk_index,
                        "filename": filename,
                        "team": team,
                        "project": project
                    })
                    
                except Exception as e:
                    logger.error(f"Error reindexing chunk {chunk_id}: {str(e)}")
                    continue
            
            # Add embeddings to FAISS
            if embeddings:
                embeddings_array = np.array(embeddings, dtype=np.float32)
                faiss.normalize_L2(embeddings_array)
                embedding_manager.index.add(embeddings_array)
                logger.info(f"Reindexed {len(embeddings)} chunks for document {filename}")
        
        # Save updated index
        await embedding_manager.save_index()
        logger.info(f"Reindexing completed. Total vectors: {embedding_manager.index.ntotal}")
        
    except Exception as e:
        logger.error(f"Error during reindexing: {str(e)}")
        raise

async def get_embedding_stats() -> Dict[str, Any]:
    """Get statistics about embeddings"""
    try:
        if not embedding_manager.is_loaded:
            await embedding_manager.load_index()
        return {
            "total_embeddings": embedding_manager.index.ntotal if embedding_manager.index else 0,
            "index_size_mb": os.path.getsize(FAISS_INDEX_PATH) / (1024*1024) if os.path.exists(FAISS_INDEX_PATH) else 0,
            "embedding_dimension": EMBEDDING_DIMENSION,
            "metadata_count": len(embedding_manager.document_metadata)
        }
    except Exception as e:
        logger.error(f"Error getting embedding stats: {str(e)}")
        return {}

async def cleanup_embeddings():
    """Clean up orphaned embeddings and rebuild index if needed"""
    try:
        logger.info("Starting embedding cleanup...")
        
        # Get all chunk IDs from database
        conn = await get_db_connection()
        cursor = await conn.execute("""
            SELECT dc.id FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE d.status = 'completed'
        """)
        valid_chunk_ids = {row[0] for row in await cursor.fetchall()}
        await conn.close()
        
        # Check metadata for orphaned entries
        valid_metadata = []
        for metadata in embedding_manager.document_metadata:
            if metadata["chunk_id"] in valid_chunk_ids:
                valid_metadata.append(metadata)
            else:
                logger.info(f"Removing orphaned metadata for chunk {metadata['chunk_id']}")
        
        # If we found orphaned metadata, rebuild the index
        if len(valid_metadata) != len(embedding_manager.document_metadata):
            logger.info("Found orphaned metadata, rebuilding index...")
            embedding_manager.document_metadata = valid_metadata
            await reindex_all_documents()
        else:
            logger.info("No orphaned metadata found")
            
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

