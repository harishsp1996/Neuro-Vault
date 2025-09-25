# HelperGPT Deployment Guide

## Local Development Setup

### 1. Quick Setup
```bash
# Run automated setup
python setup.py

# Configure environment
cp .env.example .env
# Edit .env with your Azure OpenAI credentials

# Start the system
./start.sh  # Linux/Mac
start.bat   # Windows
```

### 2. Manual Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env file with your settings

# Start server
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Production Deployment

### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app/
COPY .env .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables for Production
```env
# Security
SECRET_KEY=your-production-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Database (for production scale)
DATABASE_URL=postgresql://user:password@localhost/helpergpt

# Performance
WORKERS=4
MAX_FILE_SIZE=100MB
```

## Azure OpenAI Setup

### 1. Create Azure OpenAI Resource
1. Go to Azure Portal
2. Create new Azure OpenAI resource
3. Note the endpoint and API key

### 2. Deploy Required Models
- **GPT-4**: For response generation
- **text-embedding-ada-002**: For document embeddings

### 3. Configure API Access
```env
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002
```

## System Architecture for Production

### Recommended Stack
- **Frontend**: React.js (provided)
- **Backend**: FastAPI with Uvicorn
- **Database**: PostgreSQL (for production) or SQLite (development)
- **Vector Store**: FAISS (local) or Pinecone (cloud)
- **File Storage**: Local filesystem or Azure Blob Storage
- **Deployment**: Docker containers with Nginx reverse proxy

### Scaling Considerations
- Use Redis for session management
- Implement database connection pooling
- Add horizontal scaling with load balancers
- Consider CDN for file downloads

## Monitoring and Maintenance

### Health Checks
- API endpoint: `GET /health`
- Monitor Azure OpenAI usage and costs
- Track FAISS index performance
- Monitor disk usage for uploads

### Backup Strategy
1. Regular database backups
2. FAISS index backups
3. Document file backups
4. Configuration backups

### Updates
- Monitor Azure OpenAI API updates
- Update dependencies regularly
- Test in staging environment first
