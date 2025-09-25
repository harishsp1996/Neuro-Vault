# Corrected main.py file with proper imports for root-level structure
"""
HelperGPT Main Application
FastAPI backend for AI-powered internal documentation system
"""
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from typing import List, Optional, Any
import os
import logging
import uvicorn
from datetime import datetime
import asyncio

# Import our modules - Fixed imports for root-level structure
from database import init_db, get_db_connection, get_document_by_id, delete_document_by_id
from models import QuestionRequest, QuestionResponse, DocumentUpload, LoginRequest
from auth import authenticate_admin, create_access_token, verify_token
from storage import save_uploaded_file, get_file_path, delete_file
from embeddings import process_document, search_similar_documents, get_embedding_stats
from utils import extract_text_from_file, chunk_text, generate_response

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HelperGPT API",
    description="AI-powered internal documentation system",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

@app.on_event("startup")
async def startup_event():
    """Initialize database and create required directories on startup"""
    logger.info("Starting HelperGPT application...")
    
    # Initialize database
    await init_db()
    
    # Create uploads directory
    os.makedirs("uploads", exist_ok=True)
    
    # Initialize embedding manager
    try:
        from embeddings import embedding_manager
        await embedding_manager.load_index()
        logger.info("Embedding manager initialized")
    except Exception as e:
        logger.error(f"Failed to initialize embedding manager: {str(e)}")
    
    logger.info("Application startup complete")

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "HelperGPT API is running", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/auth/login")
async def login(request: LoginRequest):
    """Admin login endpoint"""
    try:
        user = await authenticate_admin(request.username, request.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        access_token = create_access_token({"sub": user["username"], "role": "admin"})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user
        }
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")

@app.post("/documents/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    team: str = Form(...),
    project: str = Form(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Upload and process documents"""
    try:
        # Verify admin token
        user = await verify_token(credentials.credentials)
        if not user or user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        
        logger.info(f"Starting upload for {len(files)} files - Team: {team}, Project: {project}")
        uploaded_files = []
        
        for file in files:
            try:
                # Validate file type
                if not file.filename.lower().endswith(('.txt', '.pdf', '.doc', '.docx')):
                    logger.warning(f"Skipping unsupported file: {file.filename}")
                    continue
                
                logger.info(f"Processing file: {file.filename}")
                
                # Save file
                file_path = await save_uploaded_file(file, team, project)
                logger.info(f"File saved to: {file_path}")
                
                # Extract text and process embeddings
                text_content = await extract_text_from_file(file_path)
                if not text_content:
                    logger.warning(f"No text extracted from {file.filename}")
                    continue
                
                logger.info(f"Extracted {len(text_content)} characters from {file.filename}")
                
                document_id = await process_document(file.filename, text_content, team, project)
                
                uploaded_files.append({
                    "filename": file.filename,
                    "team": team,
                    "project": project,
                    "document_id": document_id,
                    "status": "processed"
                })
                
                logger.info(f"Successfully processed {file.filename} with ID {document_id}")
                
            except Exception as file_error:
                logger.error(f"Error processing file {file.filename}: {str(file_error)}")
                uploaded_files.append({
                    "filename": file.filename,
                    "team": team,
                    "project": project,
                    "document_id": None,
                    "status": "error",
                    "error": str(file_error)
                })
        
        return {
            "uploaded_files": uploaded_files, 
            "message": f"Processed {len([f for f in uploaded_files if f.get('status') == 'processed'])} files successfully"
        }
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post("/ask")
async def ask_question(request: QuestionRequest):
    """Process user questions and return AI responses"""
    try:
        logger.info(f"Processing question: '{request.question}'")
        
        # Search for relevant documents
        similar_docs = await search_similar_documents(request.question, limit=5)
        logger.info(f"Found {len(similar_docs)} similar documents")
        
        # Generate AI response
        ai_response = await generate_response(request.question, similar_docs)
        
        # Prepare response
        response = QuestionResponse(
            question=request.question,
            answer=ai_response["answer"],
            sources=ai_response["sources"],
            confidence=ai_response["confidence"],
            timestamp=datetime.now()
        )
        
        logger.info(f"Generated response with {len(ai_response['sources'])} sources, confidence: {ai_response['confidence']}")
        return response
        
    except Exception as e:
        logger.error(f"Question processing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process question")

@app.get("/documents")
async def get_documents(
    team: Optional[str] = None,
    project: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get list of uploaded documents"""
    try:
        # Verify admin token
        user = await verify_token(credentials.credentials)
        if not user or user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

        conn = await get_db_connection()
        
        # Updated query to select specific columns for consistent structure
        query = "SELECT id, filename, original_filename, team, project, file_type, file_size, status, upload_date, chunk_count FROM documents"
        params: List[Any] = []
        
        if team:
            query += " WHERE team = ?"
            params.append(team)
        
        if project:
            query += " AND project = ?" if team else " WHERE project = ?"
            params.append(project)
        
        query += " ORDER BY upload_date DESC"
        
        result = await conn.execute(query, params)
        rows = await result.fetchall()
        await conn.close()
        
        # Convert to structured format for frontend
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
                "status": row[7],
                "upload_date": row[8],
                "chunk_count": row[9]
            })
        
        logger.info(f"Returning {len(documents)} documents")
        return {"documents": documents}
        
    except Exception as e:
        logger.error(f"Get documents error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get documents")

@app.get("/documents/{document_id}/download")
async def download_document(document_id: int):
    """Download a document by ID"""
    try:
        # Get document info using the database helper function
        document = await get_document_by_id(document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Use the file_path from database if available, otherwise construct it
        if document.get("file_path") and os.path.exists(document["file_path"]):
            file_path = document["file_path"]
        else:
            file_path = get_file_path(document["filename"], document["team"], document["project"])
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found on disk")
        
        return FileResponse(
            file_path,
            media_type="application/octet-stream",
            filename=document["original_filename"] or document["filename"]
        )
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise HTTPException(status_code=500, detail="Download failed")

@app.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Delete a document and its associated data"""
    try:
        # Verify admin token
        user = await verify_token(credentials.credentials)
        if not user or user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

        # Get document info before deletion
        document = await get_document_by_id(document_id)
        
        if document:
            # Delete physical file
            if document.get("file_path") and os.path.exists(document["file_path"]):
                file_path = document["file_path"]
            else:
                file_path = get_file_path(document["filename"], document["team"], document["project"])
            
            await delete_file(file_path)
            logger.info(f"Deleted physical file: {file_path}")
            
            # Delete from database (this also deletes associated chunks due to foreign key constraint)
            success = await delete_document_by_id(document_id)
            
            if success:
                logger.info(f"Deleted document {document_id} from database")
                
                # TODO: Remove embeddings from FAISS index
                # This requires rebuilding the index or implementing vector removal
                
                return {"message": "Document deleted successfully"}
            else:
                raise HTTPException(status_code=404, detail="Document not found in database")
        else:
            raise HTTPException(status_code=404, detail="Document not found")

    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        raise HTTPException(status_code=500, detail="Delete failed")

@app.get("/teams")
async def get_teams():
    """Get list of teams and projects"""
    teams = [
        {
            "id": 1,
            "name": "Engineering",
            "projects": [
                "Cloud Team",
                "IT Support",
                "IRI",
                "INSW",
                "Meraki",
                "Nautilux",
                "Database",
                "Custom Project…"
            ]
        },
        {"id": 2, "name": "Marketing", "projects": ["Campaign 2025", "Brand Guidelines", "Social Media"]},
        {"id": 3, "name": "Sales", "projects": ["Q1 Strategy", "Training Materials", "Product Demos"]},
        {"id": 4, "name": "HR", "projects": ["Onboarding", "Policies", "Benefits Guide"]}
    ]
    return {"teams": teams}

@app.get("/debug/processing")
async def debug_processing():
    """Debug endpoint to check document processing status"""
    try:
        async with get_db_connection() as db:
            # Check document status counts
            cursor = await db.execute("SELECT status, COUNT(*) FROM documents GROUP BY status")
            status_counts = dict(await cursor.fetchall())
            
            # Check recent documents
            cursor = await db.execute("""
                SELECT id, filename, status, upload_date, chunk_count 
                FROM documents 
                ORDER BY upload_date DESC 
                LIMIT 10
            """)
            recent_docs = await cursor.fetchall()
            
            # Check total chunks
            cursor = await db.execute("SELECT COUNT(*) FROM document_chunks")
            total_chunks = (await cursor.fetchone())[0]
        
        # Get embedding stats
        embedding_stats = await get_embedding_stats()
        
        return {
            "document_status_counts": status_counts,
            "recent_documents": [
                {
                    "id": row[0], 
                    "filename": row[1], 
                    "status": row[2], 
                    "upload_date": row[3],
                    "chunk_count": row[4]
                }
                for row in recent_docs
            ],
            "total_chunks_in_db": total_chunks,
            "embedding_stats": embedding_stats,
            "faiss_index_exists": os.path.exists("faiss_index.bin"),
            "database_exists": os.path.exists("metadata.db"),
            "uploads_folder_exists": os.path.exists("uploads")
        }
        
    except Exception as e:
        logger.error(f"Debug endpoint error: {str(e)}")
        return {"error": str(e)}

@app.get("/debug/test-search")
async def debug_test_search(q: str = "test query"):
    """Debug endpoint to test search functionality"""
    try:
        logger.info(f"Testing search with query: '{q}'")
        
        # Test the search function
        similar_docs = await search_similar_documents(q, limit=3)
        
        return {
            "query": q,
            "results_count": len(similar_docs),
            "results": similar_docs,
            "embedding_manager_loaded": hasattr(search_similar_documents, '__globals__') and 'embedding_manager' in search_similar_documents.__globals__
        }
        
    except Exception as e:
        logger.error(f"Debug search error: {str(e)}")
        return {"error": str(e), "query": q}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )

