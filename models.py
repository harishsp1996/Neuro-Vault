"""
Pydantic models for HelperGPT API
Request and response schemas
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class FileType(str, Enum):
    """Supported file types"""
    TXT = "txt"
    PDF = "pdf" 
    DOC = "doc"
    DOCX = "docx"

class LoginRequest(BaseModel):
    """Admin login request model"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)

class LoginResponse(BaseModel):
    """Admin login response model"""
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

class QuestionRequest(BaseModel):
    """User question request model"""
    question: str = Field(..., min_length=3, max_length=1000)
    context: Optional[str] = Field(None, max_length=2000)
    team: Optional[str] = Field(None, max_length=50)
    project: Optional[str] = Field(None, max_length=50)

class Source(BaseModel):
    """Source document reference"""
    document_id: int
    filename: str
    team: str
    project: str
    relevance_score: float
    page_numbers: Optional[List[int]] = None

class QuestionResponse(BaseModel):
    """AI response to user question"""
    question: str
    answer: str
    sources: List[Source] = []
    confidence: float = Field(..., ge=0.0, le=1.0)
    timestamp: datetime
    response_time_ms: Optional[int] = None

class DocumentUpload(BaseModel):
    """Document upload request model"""
    team: str = Field(..., min_length=1, max_length=50)
    project: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=500)

class DocumentInfo(BaseModel):
    """Document information model"""
    id: int
    filename: str
    team: str
    project: str
    file_type: FileType
    file_size: int
    upload_date: datetime
    processed_date: Optional[datetime] = None
    chunk_count: int = 0
    status: str = "pending"  # pending, processing, completed, error

class DocumentListResponse(BaseModel):
    """Response for document list"""
    documents: List[DocumentInfo]
    total_count: int
    team_filter: Optional[str] = None
    project_filter: Optional[str] = None

class Team(BaseModel):
    """Team model"""
    id: int
    name: str = Field(..., min_length=1, max_length=50)
    projects: List[str] = []
    document_count: int = 0
    created_date: datetime = Field(default_factory=datetime.now)

class TeamsResponse(BaseModel):
    """Teams list response"""
    teams: List[Team]

class UploadProgress(BaseModel):
    """File upload progress model"""
    filename: str
    status: str  # uploading, processing, completed, error
    progress: int = Field(..., ge=0, le=100)
    message: Optional[str] = None
    document_id: Optional[int] = None

class ChatMessage(BaseModel):
    """Chat message model"""
    id: str
    question: str
    answer: str
    timestamp: datetime
    sources: List[Source] = []
    confidence: float

class ChatHistory(BaseModel):
    """Chat history model"""
    messages: List[ChatMessage] = []
    session_id: str
    created_at: datetime

class SearchSuggestion(BaseModel):
    """Search suggestion model"""
    text: str
    category: str
    frequency: int = 0

class SystemStats(BaseModel):
    """System statistics model"""
    total_documents: int
    total_teams: int
    total_projects: int
    total_queries: int
    avg_response_time: float
    last_updated: datetime

class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: str
    timestamp: datetime = Field(default_factory=datetime.now)
    request_id: Optional[str] = None

class HealthCheck(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    services: Dict[str, str] = {}  # service_name: status
    version: str = "1.0.0"

# Validators
class DocumentUploadValidator:
    """Validators for document uploads"""

    @staticmethod
    def validate_file_size(file_size: int) -> bool:
        """Validate file size (max 50MB)"""
        max_size = 50 * 1024 * 1024  # 50MB
        return file_size <= max_size

    @staticmethod
    def validate_file_type(filename: str) -> bool:
        """Validate file extension"""
        allowed_extensions = {'.txt', '.pdf', '.doc', '.docx'}
        file_ext = os.path.splitext(filename)[1].lower()
        return file_ext in allowed_extensions

    @staticmethod
    def validate_team_project(team: str, project: str) -> bool:
        """Validate team and project combination"""
        # Add business logic for valid team/project combinations
        return len(team) > 0 and len(project) > 0

# Request/Response models for specific endpoints

class BulkUploadRequest(BaseModel):
    """Bulk upload request"""
    team: str
    project: str
    files: List[str]  # List of file identifiers
    overwrite: bool = False

class BulkUploadResponse(BaseModel):
    """Bulk upload response"""
    uploaded_count: int
    failed_count: int
    uploaded_files: List[DocumentInfo] = []
    failed_files: List[str] = []
    processing_time_seconds: float

class SearchRequest(BaseModel):
    """Advanced search request"""
    query: str
    team_filter: Optional[str] = None
    project_filter: Optional[str] = None
    file_type_filter: Optional[FileType] = None
    limit: int = Field(default=10, ge=1, le=50)
    include_content: bool = False

class SearchResponse(BaseModel):
    """Search response"""
    query: str
    results: List[DocumentInfo]
    total_matches: int
    search_time_ms: int
    filters_applied: Dict[str, Any] = {}

# Configuration models
class AzureOpenAIConfig(BaseModel):
    """Azure OpenAI configuration"""
    api_key: str
    endpoint: str
    api_version: str = "2024-02-15-preview"
    deployment_name: str = "gpt-4"
    embedding_deployment: str = "text-embedding-ada-002"
    max_tokens: int = 1000
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

class FAISSConfig(BaseModel):
    """FAISS configuration"""
    index_path: str = "faiss_index.bin"
    dimension: int = 1536  # Ada-002 embedding dimension
    metric_type: str = "cosine"
    nprobe: int = 10
