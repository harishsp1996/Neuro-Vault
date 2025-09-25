class HelperGPT {
    constructor() {
        this.isLoggedIn = false;
        this.currentUser = null;
        this.authToken = null;
        this.chatHistory = [];
        this.uploadedDocuments = [];
        
        // API Configuration
        this.API_BASE = 'http://192.168.1.215:8080';  // Adjust for your backend URL
        
        // Application data
        this.teams = [
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
            {"id": 4, "name": "HR", "projects": ["Onboarding", "Policies", "Benefits Guide"]},
        ];
        this.initializeApp();
    }
    
    initializeApp() {
        console.log('Initializing HelperGPT...');
        this.forceMainViewVisible();
        this.bindEvents();
        this.setupFileUpload();
        this.loadTeamsFromAPI();
        console.log('HelperGPT initialized successfully');
    }
    
    forceMainViewVisible() {
        const modalsAndOverlays = ['loginModal', 'uploadProgressModal', 'processingOverlay'];
        modalsAndOverlays.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.classList.add('hidden');
                el.style.display = 'none';
            }
        });
        const mainView = document.getElementById('mainView');
        const adminPanel = document.getElementById('adminPanel');
        if (mainView) {
            mainView.classList.remove('hidden');
            mainView.style.display = 'block';
        }
        if (adminPanel) {
            adminPanel.classList.add('hidden');
            adminPanel.style.display = 'none';
        }
        this.updateAuthButtons();
    }
    
    updateAuthButtons() {
        const adminLoginBtn = document.getElementById('adminLoginBtn');
        const logoutBtn = document.getElementById('logoutBtn');
        if (this.isLoggedIn) {
            if (adminLoginBtn) {
                adminLoginBtn.classList.add('hidden');
                adminLoginBtn.style.display = 'none';
            }
            if (logoutBtn) {
                logoutBtn.classList.remove('hidden');
                logoutBtn.style.display = 'inline-flex';
            }
        } else {
            if (adminLoginBtn) {
                adminLoginBtn.classList.remove('hidden');
                adminLoginBtn.style.display = 'inline-flex';
            }
            if (logoutBtn) {
                logoutBtn.classList.add('hidden');
                logoutBtn.style.display = 'none';
            }
        }
    }
    
    async makeAPICall(endpoint, options = {}) {
        try {
            const url = `${this.API_BASE}${endpoint}`;
            const config = {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers,
                },
                ...options,
            };
            if (this.authToken) {
                config.headers['Authorization'] = `Bearer ${this.authToken}`;
            }
            console.log(`Making API call to: ${url}`);
            const response = await fetch(url, config);
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API Error ${response.status}: ${errorText}`);
            }
            const data = await response.json();
            console.log(`API response:`, data);
            return data;
        } catch (error) {
            console.error('API call failed:', error);
            throw error;
        }
    }
    
    async testConnection() {
        try {
            const health = await this.makeAPICall('/health');
            console.log('Backend connection successful:', health);
            return true;
        } catch (error) {
            console.error('Backend connection failed:', error);
            this.showNotification('Backend connection failed. Please check if the server is running.', 'error');
            return false;
        }
    }
    
    async loadTeamsFromAPI() {
        try {
            const response = await this.makeAPICall('/teams');
            if (response.teams) {
                this.teams = response.teams;
                this.populateTeamSelect();
            }
        } catch (error) {
            console.error('Failed to load teams:', error);
            this.populateTeamSelect();
        }
    }
    
    populateTeamSelect() {
        const teamSelect = document.getElementById('teamSelect');
        if (!teamSelect) return;
        teamSelect.innerHTML = '<option value="">Select Team</option>';
        this.teams.forEach(team => {
            const option = document.createElement('option');
            option.value = team.name;
            option.textContent = team.name;
            teamSelect.appendChild(option);
        });
    }
    
    bindEvents() {
        this.testConnection();
        const adminLoginBtn = document.getElementById('adminLoginBtn');
        const closeLoginModal = document.getElementById('closeLoginModal');
        const loginForm = document.getElementById('loginForm');
        const logoutBtn = document.getElementById('logoutBtn');
        if (adminLoginBtn) adminLoginBtn.addEventListener('click', e => { e.preventDefault(); this.showLoginModal(); });
        if (closeLoginModal) closeLoginModal.addEventListener('click', e => { e.preventDefault(); this.hideLoginModal(); });
        if (loginForm) loginForm.addEventListener('submit', e => this.handleLogin(e));
        if (logoutBtn) logoutBtn.addEventListener('click', e => { e.preventDefault(); this.handleLogout(); });
        const askBtn = document.getElementById('askBtn');
        const questionInput = document.getElementById('questionInput');
        if (askBtn) askBtn.addEventListener('click', e => { e.preventDefault(); this.handleQuestion(); });
        if (questionInput) questionInput.addEventListener('keypress', e => { if (e.key === 'Enter') { e.preventDefault(); this.handleQuestion(); } });
        document.querySelectorAll('.quick-question-btn').forEach(btn => {
            btn.addEventListener('click', e => {
                e.preventDefault();
                const question = e.target.getAttribute('data-question');
                if (questionInput && question) {
                    questionInput.value = question;
                    this.handleQuestion();
                }
            });
        });
        const clearResultsBtn = document.getElementById('clearResultsBtn');
        const clearHistoryBtn = document.getElementById('clearHistoryBtn');
        if (clearResultsBtn) clearResultsBtn.addEventListener('click', e => { e.preventDefault(); this.clearResults(); });
        if (clearHistoryBtn) clearHistoryBtn.addEventListener('click', e => { e.preventDefault(); this.clearChatHistory(); });
        const teamSelect = document.getElementById('teamSelect');
        const uploadForm = document.getElementById('uploadForm');
        if (teamSelect) teamSelect.addEventListener('change', e => this.updateProjectSelect(e.target.value));
        if (uploadForm) uploadForm.addEventListener('submit', e => this.handleFileUpload(e));
        document.addEventListener('click', e => { if (e.target.classList.contains('modal__overlay')) { e.preventDefault(); this.hideAllModals(); } });
        document.addEventListener('keydown', e => { if (e.key === 'Escape') this.hideAllModals(); });
    }
    
    hideAllModals() {
        this.hideLoginModal();
        this.hideUploadProgressModal();
    }
    
    showLoginModal() {
        const loginModal = document.getElementById('loginModal');
        const usernameInput = document.getElementById('username');
        if (loginModal) {
            loginModal.classList.remove('hidden');
            loginModal.style.display = 'flex';
        }
        if (usernameInput) setTimeout(() => usernameInput.focus(), 100);
    }
    
    hideLoginModal() {
        const loginModal = document.getElementById('loginModal');
        const loginForm = document.getElementById('loginForm');
        if (loginModal) {
            loginModal.classList.add('hidden');
            loginModal.style.display = 'none';
        }
        if (loginForm) loginForm.reset();
    }
    
    async handleLogin(e) {
        e.preventDefault();
        const usernameEl = document.getElementById('username');
        const passwordEl = document.getElementById('password');
        if (!usernameEl || !passwordEl) return;
        const username = usernameEl.value.trim();
        const password = passwordEl.value.trim();
        if (!username || !password) {
            this.showNotification('Please enter both username and password', 'error');
            return;
        }
        try {
            this.showNotification('Logging in...', 'info');
            const response = await this.makeAPICall('/auth/login', {
                method: 'POST',
                body: JSON.stringify({username, password})
            });
            if (response?.access_token) {
                this.authToken = response.access_token;
                this.currentUser = response.user;
                this.isLoggedIn = true;
                this.hideLoginModal();
                this.showAdminPanel();
                this.showNotification('Login successful! Welcome to admin panel.', 'success');
                await this.loadDocuments();
            }
        } catch (error) {
            console.error('Login failed:', error);
            this.showNotification('Login failed. Please check your credentials.', 'error');
        }
    }
    
    handleLogout() {
        this.isLoggedIn = false;
        this.currentUser = null;
        this.authToken = null;
        this.uploadedDocuments = [];
        this.showMainView();
        this.showNotification('Logged out successfully', 'success');
    }
    
    showAdminPanel() {
        const mainView = document.getElementById('mainView');
        const adminPanel = document.getElementById('adminPanel');
        if (mainView) {
            mainView.classList.add('hidden');
            mainView.style.display = 'none';
        }
        if (adminPanel) {
            adminPanel.classList.remove('hidden');
            adminPanel.style.display = 'block';
        }
        this.updateAuthButtons();
        this.renderDocuments();
    }
    
    showMainView() {
        const mainView = document.getElementById('mainView');
        const adminPanel = document.getElementById('adminPanel');
        if (mainView) {
            mainView.classList.remove('hidden');
            mainView.style.display = 'block';
        }
        if (adminPanel) {
            adminPanel.classList.add('hidden');
            adminPanel.style.display = 'none';
        }
        this.updateAuthButtons();
    }
    
    updateProjectSelect(teamName) {
        const projectSelect = document.getElementById('projectSelect');
        if (!projectSelect) return;
        projectSelect.innerHTML = '<option value="">Select Project</option>';
        const team = this.teams.find(t => t.name === teamName);
        if (team?.projects) {
            team.projects.forEach(project => {
                const option = document.createElement('option');
                option.value = project;
                option.textContent = project;
                projectSelect.appendChild(option);
            });
        }
    }
    
    setupFileUpload() {
        const fileUploadArea = document.getElementById('fileUploadArea');
        const fileInput = document.getElementById('fileInput');
        if (!fileUploadArea || !fileInput) return;
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            fileUploadArea.addEventListener(eventName, this.preventDefaults, false);
        });
        ['dragenter', 'dragover'].forEach(eventName => {
            fileUploadArea.addEventListener(eventName, () => {
                fileUploadArea.classList.add('drag-over');
            }, false);
        });
        ['dragleave', 'drop'].forEach(eventName => {
            fileUploadArea.addEventListener(eventName, () => {
                fileUploadArea.classList.remove('drag-over');
            }, false);
        });
        fileUploadArea.addEventListener('drop', e => {
            this.handleFileSelect(e.dataTransfer.files);
        }, false);
        fileUploadArea.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', e => this.handleFileSelect(e.target.files));
    }
    
    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    handleFileSelect(files) {
        const fileList = document.getElementById('fileList');
        if (!fileList) return;
        fileList.innerHTML = '';
        Array.from(files).forEach(file => {
            if (this.isValidFile(file)) {
                const fileItem = this.createFileItem(file);
                fileList.appendChild(fileItem);
            } else {
                this.showNotification(`File ${file.name} is not supported. Please upload .txt, .pdf, .doc, or .docx files.`, 'error');
            }
        });
    }
    
    isValidFile(file) {
        const validTypes = ['.txt', '.pdf', '.doc', '.docx'];
        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
        return validTypes.includes(fileExtension);
    }
    
    createFileItem(file) {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.innerHTML = `
            <div class="file-item__info">
                <div class="file-item__name">${file.name}</div>
                <div class="file-item__size">${this.formatFileSize(file.size)}</div>
            </div>
            <button type="button" class="file-item__remove">×</button>
        `;
        const removeBtn = fileItem.querySelector('.file-item__remove');
        removeBtn.addEventListener('click', () => fileItem.remove());
        return fileItem;
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    async handleFileUpload(e) {
        e.preventDefault();
        if (!this.isLoggedIn) {
            this.showNotification('Please login first', 'error');
            return;
        }
        const teamSelect = document.getElementById('teamSelect');
        const projectSelect = document.getElementById('projectSelect');
        const fileInput = document.getElementById('fileInput');
        if (!teamSelect || !projectSelect || !fileInput) return;
        const team = teamSelect.value;
        const project = projectSelect.value;
        const files = fileInput.files;
        if (!team || !project) {
            this.showNotification('Please select both team and project', 'error');
            return;
        }
        if (!files || files.length === 0) {
            this.showNotification('Please select files to upload', 'error');
            return;
        }
        try {
            await this.uploadFiles(team, project, files);
        } catch (error) {
            console.error('Upload failed:', error);
            this.showNotification('Upload failed. Please try again.', 'error');
        }
    }
    
    async uploadFiles(team, project, files) {
        this.showUploadProgressModal();
        const formData = new FormData();
        formData.append('team', team);
        formData.append('project', project);
        Array.from(files).forEach(file => formData.append('files', file));
        try {
            const response = await fetch(`${this.API_BASE}/documents/upload`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${this.authToken}` },
                body: formData
            });
            if (!response.ok) throw new Error(`Upload failed: ${response.statusText}`);
            await response.json();
            this.hideUploadProgressModal();
            this.showNotification('Files uploaded successfully!', 'success');
            await this.loadDocuments();
            this.resetUploadForm();
        } catch (error) {
            this.hideUploadProgressModal();
            console.error('Upload error:', error);
            throw error;
        }
    }
    
    resetUploadForm() {
        const uploadForm = document.getElementById('uploadForm');
        const fileList = document.getElementById('fileList');
        const teamSelect = document.getElementById('teamSelect');
        const projectSelect = document.getElementById('projectSelect');
        if (uploadForm) uploadForm.reset();
        if (fileList) fileList.innerHTML = '';
        if (teamSelect) teamSelect.value = '';
        if (projectSelect) projectSelect.innerHTML = '<option value="">Select Project</option>';
    }
    
    showUploadProgressModal() {
        const modal = document.getElementById('uploadProgressModal');
        if (modal) {
            modal.classList.remove('hidden');
            modal.style.display = 'flex';
        }
    }
    
    hideUploadProgressModal() {
        const modal = document.getElementById('uploadProgressModal');
        if (modal) {
            modal.classList.add('hidden');
            modal.style.display = 'none';
        }
    }
    
    async loadDocuments() {
        if (!this.isLoggedIn) return;
        try {
            const response = await this.makeAPICall('/documents');
            if (response.documents) {
                this.uploadedDocuments = response.documents;
                this.renderDocuments();
            }
        } catch (error) {
            console.error('Failed to load documents:', error);
            this.showNotification('Failed to load documents', 'error');
        }
    }
    
    renderDocuments() {
        const documentsList = document.getElementById('documentsList');
        if (!documentsList) return;
        
        documentsList.innerHTML = '';
        
        this.uploadedDocuments.forEach(doc => {
            // Debug log to see document structure
            console.log('Document structure:', doc);
            
            // Handle different possible ID field names
            const docId = doc.id || doc.document_id || doc._id || doc[0]; // doc[0] for array-based response
            
            if (!docId) {
                console.error('Document missing ID:', doc);
                return;
            }
            
            const docItem = document.createElement('div');
            docItem.className = 'document-item fade-in';
            docItem.innerHTML = `
                <div class="document-item__info">
                    <div class="document-item__name">📄 ${doc.filename || doc.name || doc[1]}</div>
                    <div class="document-item__meta">
                        <span>${(doc.team || doc[2])} • ${(doc.project || doc[3])}</span>
                        <span>${doc.upload_date || doc.uploadDate || doc.created_at || 'Unknown'}</span>
                        <span>${this.formatFileSize(doc.file_size || doc.size || 0)}</span>
                        <span class="status status--${this.getStatusClass(doc.status || doc[6] || 'completed')}">
                            ${doc.status || doc[6] || 'completed'}
                        </span>
                    </div>
                </div>
                <div class="document-item__actions">
                    <button type="button" class="document-item__action" onclick="helperGPT.downloadDocument(${docId})">Download</button>
                    <button type="button" class="document-item__action document-item__action--danger" onclick="helperGPT.deleteDocument(${docId})">Delete</button>
                </div>
            `;
            documentsList.appendChild(docItem);
        });
        
        this.updateDocumentStats();
    }
    
    getStatusClass(status) {
        switch (status) {
            case 'completed': return 'success';
            case 'processing': return 'warning';
            case 'error': return 'error';
            default: return 'info';
        }
    }
    
    updateDocumentStats() {
        const totalDocsEl = document.getElementById('totalDocs');
        const totalSizeEl = document.getElementById('totalSize');
        if (!totalDocsEl || !totalSizeEl) return;
        const totalDocs = this.uploadedDocuments.length;
        const totalSize = this.uploadedDocuments.reduce((sum, doc) => sum + (doc.file_size || doc.size || 0), 0);
        totalDocsEl.textContent = totalDocs;
        totalSizeEl.textContent = this.formatFileSize(totalSize);
    }
    
    async downloadDocument(id) {
        if (!this.isLoggedIn) {
            this.showNotification('Please login first', 'error');
            return;
        }
        if (!id || id === 'undefined') {
            this.showNotification('Invalid document ID', 'error');
            return;
        }
        try {
            window.open(`${this.API_BASE}/documents/${id}/download`, '_blank');
            this.showNotification('Download started...', 'info');
        } catch (error) {
            console.error('Download failed:', error);
            this.showNotification('Download failed', 'error');
        }
    }
    
    async deleteDocument(id) {
        if (!this.isLoggedIn) {
            this.showNotification('Please login first', 'error');
            return;
        }
        if (!id || id === 'undefined') {
            this.showNotification('Invalid document ID', 'error');
            return;
        }
        if (!confirm('Are you sure you want to delete this document?')) {
            return;
        }
        try {
            await this.makeAPICall(`/documents/${id}`, { method: 'DELETE' });
            this.showNotification('Document deleted successfully', 'success');
            await this.loadDocuments();
        } catch (error) {
            console.error('Delete failed:', error);
            this.showNotification('Delete failed', 'error');
        }
    }
    
    async handleQuestion() {
        const questionInput = document.getElementById('questionInput');
        if (!questionInput) return;
        const question = questionInput.value.trim();
        if (!question) {
            this.showNotification('Please enter a question', 'error');
            return;
        }
        if (question.length < 3) {
            this.showNotification('Question must be at least 3 characters long', 'error');
            return;
        }
        this.showProcessing();
        this.addToChatHistory(question);
        try {
            const response = await this.makeAPICall('/ask', {
                method: 'POST',
                body: JSON.stringify({ question }),
            });
            this.displayResult(question, response);
            questionInput.value = '';
        } catch (error) {
            console.error('Question processing failed:', error);
            this.showNotification('Failed to process question. Please try again.', 'error');
        } finally {
            this.hideProcessing();
        }
    }
    
    displayResult(question, response) {
        const resultsSection = document.getElementById('resultsSection');
        const resultsContent = document.getElementById('resultsContent');
        if (!resultsSection || !resultsContent) return;
        resultsSection.classList.remove('hidden');
        const resultItem = document.createElement('div');
        resultItem.className = 'result-item slide-up';
        resultItem.innerHTML = `
            <div class="result-item__question">${question}</div>
            <div class="result-item__answer">${response.answer}</div>
            <div class="result-item__metadata">
                <div class="result-sources">
                    <div class="result-sources__title">Source Documents:</div>
                    <div class="result-sources__list">
                        ${response.sources.map(source => `
                            <a href="#" class="source-link" onclick="helperGPT.downloadSource('${source.filename}')">
                                📄 ${source.filename}
                            </a>
                        `).join('')}
                    </div>
                </div>
                <div class="confidence-score">
                    <span>Confidence:</span>
                    <div class="confidence-bar">
                        <div class="confidence-bar__fill" style="width: ${response.confidence * 100}%"></div>
                    </div>
                    <span>${Math.round(response.confidence * 100)}%</span>
                </div>
            </div>
        `;
        resultsContent.insertBefore(resultItem, resultsContent.firstChild);
        if (this.chatHistory.length > 0) {
            const chatHistory = document.getElementById('chatHistory');
            if (chatHistory) chatHistory.classList.remove('hidden');
        }
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }
    
    downloadSource(sourceName) {
        this.showNotification(`Downloading ${sourceName}...`, 'info');
    }
    
    addToChatHistory(question) {
        this.chatHistory.unshift(question);
        if (this.chatHistory.length > 10) {
            this.chatHistory = this.chatHistory.slice(0, 10);
        }
        this.updateChatHistoryDisplay();
    }
    
    updateChatHistoryDisplay() {
        const historyList = document.getElementById('chatHistoryList');
        if (!historyList) return;
        historyList.innerHTML = '';
        this.chatHistory.forEach(question => {
            const historyItem = document.createElement('div');
            historyItem.className = 'chat-history-item';
            historyItem.textContent = question;
            historyItem.addEventListener('click', () => {
                const questionInput = document.getElementById('questionInput');
                if (questionInput) {
                    questionInput.value = question;
                    this.handleQuestion();
                }
            });
            historyList.appendChild(historyItem);
        });
    }
    
    clearResults() {
        const resultsContent = document.getElementById('resultsContent');
        const resultsSection = document.getElementById('resultsSection');
        const chatHistory = document.getElementById('chatHistory');
        if (resultsContent) resultsContent.innerHTML = '';
        if (resultsSection) resultsSection.classList.add('hidden');
        if (chatHistory) chatHistory.classList.add('hidden');
    }
    
    clearChatHistory() {
        this.chatHistory = [];
        this.updateChatHistoryDisplay();
        const chatHistory = document.getElementById('chatHistory');
        if (chatHistory) chatHistory.classList.add('hidden');
    }
    
    showProcessing() {
        const processingOverlay = document.getElementById('processingOverlay');
        if (processingOverlay) {
            processingOverlay.classList.remove('hidden');
            processingOverlay.style.display = 'flex';
        }
    }
    
    hideProcessing() {
        const processingOverlay = document.getElementById('processingOverlay');
        if (processingOverlay) {
            processingOverlay.classList.add('hidden');
            processingOverlay.style.display = 'none';
        }
    }
    
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification--${type}`;
        const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
        notification.innerHTML = `
            <div class="notification__content">
                <span>${icons[type] || icons.info}</span>
                ${message}
            </div>
            <button class="notification__close">×</button>
        `;
        const closeBtn = notification.querySelector('.notification__close');
        if (closeBtn) closeBtn.addEventListener('click', () => notification.remove());
        document.body.appendChild(notification);
        setTimeout(() => { if (document.body.contains(notification)) notification.remove(); }, 5000);
    }
}

// Initialize application when DOM is ready
function initHelperGPT() {
    try {
        console.log('DOM ready, initializing HelperGPT...');
        window.helperGPT = new HelperGPT();
    } catch (error) {
        console.error('Failed to initialize HelperGPT:', error);
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHelperGPT);
} else {
    initHelperGPT();
}

