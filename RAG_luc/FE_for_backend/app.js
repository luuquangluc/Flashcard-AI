/**
 * RAG Flashcard Generator - Frontend Application
 * Handles UI interactions, RAG API calls, and flashcard rendering
 */

const API_BASE = '';  // Same origin - Flask serves both FE and API

// DOM Elements
const inputText = document.getElementById('inputText');
const charCount = document.getElementById('charCount');
const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const uploadLabel = document.getElementById('uploadLabel');
const generateBtn = document.getElementById('generateBtn');
const generateLabel = document.getElementById('generateLabel');
const pageRangeInput = null; // Removed - using unified inputText
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const fileRemove = document.getElementById('fileRemove');
const errorMessage = document.getElementById('errorMessage');
const errorText = document.getElementById('errorText');
const loadingSection = document.getElementById('loadingSection');
const loadingText = document.getElementById('loadingText');
const resultSection = document.getElementById('resultSection');
const tracingSection = document.getElementById('tracingSection');
const tracingConsole = document.getElementById('tracingConsole');
const resultsSection = document.getElementById('resultsSection');
const resultsCount = document.getElementById('resultsCount');
const flashcardsGrid = document.getElementById('flashcardsGrid');
const exportAnki = document.getElementById('exportAnki');
const bgParticles = document.getElementById('bgParticles');

// Modal Elements
const editModal = document.getElementById('editModal');
const closeModalBtn = document.getElementById('closeModalBtn');
const cancelEditBtn = document.getElementById('cancelEditBtn');
const saveEditBtn = document.getElementById('saveEditBtn');
// const editContextDiv = document.getElementById('editContext');  // Removed raw text section
const editQuestion = document.getElementById('editQuestion');
const editAnswer = document.getElementById('editAnswer');
const modalCardBadge = document.getElementById('modalCardBadge');
const pdfViewer = document.getElementById('pdfViewer');
const pdfFallback = document.getElementById('pdfFallback');
const pdfDownloadLink = document.getElementById('pdfDownloadLink');

// Unified Input UI elements
const inputInstruction = document.getElementById('inputInstruction');
const inputHint = document.getElementById('inputHint');
const structureWarning = document.getElementById('structureWarning');

// State
let flashcards = [];
let isLoading = false;
let isUploading = false;
let isRAGInitialized = false;
let isStructureGood = true;
let currentInputMode = 'topic'; // 'topic' or 'page'
let currentEditingIndex = -1;
let currentView = 'generator';
let currentUser = null;
let currentRole = null;
let currentDesireMode = 'default'; // 'default' or 'language'

// Sidebar Elements
const navGenerator = document.getElementById('navGenerator');
const navLibrary = document.getElementById('navLibrary');
const navAnalytics = document.getElementById('navAnalytics');
const navStudy = document.getElementById('navStudy');
const generatorView = document.getElementById('generatorView');
const libraryView = document.getElementById('libraryView');
const analyticsView = document.getElementById('analyticsView');
const studyView = document.getElementById('studyView');
const navItems = document.querySelectorAll('.nav-item');

// Library Elements
const libraryGrid = document.getElementById('libraryGrid');
const libSetCount = document.getElementById('libSetCount');
const libEmptyState = document.getElementById('libEmptyState');
const saveToLibraryBtn = document.getElementById('saveToLibraryBtn');

// GameFi Elements
const playerStatsBar = document.getElementById('playerStats');
const xpBar = document.getElementById('xpBar');
const playerLevelLabel = document.getElementById('playerLevel');
const playerRankLabel = document.getElementById('playerRank');
const currentXpLabel = document.getElementById('currentXp');
const nextLevelXpLabel = document.getElementById('nextLevelXp');
const streakCountLabel = document.getElementById('streakCount');
const startMatchingGameBtn = document.getElementById('startMatchingGame');

// Game Arena Elements
const gameArena = document.getElementById('gameArena');
const exitGameBtn = document.getElementById('exitGameBtn');
const gameTimerLabel = document.getElementById('gameTimer');
const gameComboLabel = document.getElementById('gameCombo');
const gameProgressBar = document.getElementById('gameProgress');
const qGrid = document.getElementById('qGrid');
const aGrid = document.getElementById('aGrid');

// ============================================
// Navigation & View Switching
// ============================================
function switchView(viewName) {
    currentView = viewName;
    
    // Update Sidebar
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.classList.toggle('active', item.dataset.view === viewName);
    });
    
    // Update View Containers
    const generatorView = document.getElementById('generatorView');
    const libraryView = document.getElementById('libraryView');
    const analyticsView = document.getElementById('analyticsView');
    const gameView = document.getElementById('gameView');
    const studyView = document.getElementById('studyView');

    if (generatorView) generatorView.style.display = (viewName === 'generator') ? 'block' : 'none';
    if (analyticsView) analyticsView.style.display = (viewName === 'analytics') ? 'block' : 'none';
    if (gameView) gameView.style.display = (viewName === 'game') ? 'block' : 'none';
    if (studyView) studyView.style.display = (viewName === 'study') ? 'block' : 'none';
    
    if (viewName === 'library') {
        if (libraryView) libraryView.style.display = 'block';
        LibrarySystem.load();
        LibrarySystem.loadDocuments();
    } else {
        if (libraryView) libraryView.style.display = 'none';
    }

    if (viewName === 'study') {
        StudyManager.init();
    }

    if (viewName === 'game') {
        LibrarySystem.renderSetsForGame();
    }

    if (viewName === 'analytics') {
        AnalyticsManager.render();
    }
}

// ============================================
// Authentication System
// ============================================

// Switch between Login/Register tabs
function switchAuthTab(tab) {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const tabLogin = document.getElementById('tabLogin');
    const tabRegister = document.getElementById('tabRegister');
    const authTitle = document.getElementById('authTitle');
    const authSubtitle = document.getElementById('authSubtitle');

    if (tab === 'login') {
        loginForm.style.display = 'flex';
        registerForm.style.display = 'none';
        tabLogin.classList.add('active');
        tabRegister.classList.remove('active');
        authTitle.textContent = 'Flashcard AI';
        authSubtitle.textContent = 'Vui lòng đăng nhập để tiếp tục';
    } else {
        loginForm.style.display = 'none';
        registerForm.style.display = 'flex';
        tabLogin.classList.remove('active');
        tabRegister.classList.add('active');
        authTitle.textContent = 'Tạo tài khoản';
        authSubtitle.textContent = 'Đăng ký miễn phí, bắt đầu ngay hôm nay';
    }
}

// Toggle show/hide password
function togglePassword(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '🙈';
    } else {
        input.type = 'password';
        btn.textContent = '👁️';
    }
}

const AuthSystem = {
    async check() {
        try {
            const res = await fetch(`${API_BASE}/api/me`);
            const data = await res.json();
            if (data.logged_in) {
                this.onLoginSuccess(data);
            } else {
                this.showLogin();
            }
        } catch (e) {
            console.error("Auth check failed", e);
            this.showLogin();
        }
    },

    async login(username, password) {
        const errorEl = document.getElementById('loginError');
        const btn = document.getElementById('loginSubmitBtn');
        if (errorEl) errorEl.style.display = 'none';
        if (btn) { btn.disabled = true; btn.innerHTML = '<span>⏳</span> Đang đăng nhập...'; }

        try {
            const res = await fetch(`${API_BASE}/api/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            const data = await res.json();
            
            if (res.ok && data.success) {
                this.onLoginSuccess(data);
            } else {
                if (errorEl) {
                    errorEl.textContent = data.error || 'Sai tài khoản hoặc mật khẩu';
                    errorEl.style.display = 'block';
                }
            }
        } catch (e) {
            if (errorEl) {
                errorEl.textContent = 'Lỗi kết nối server. Vui lòng thử lại.';
                errorEl.style.display = 'block';
            }
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = '<span>🚀</span> Đăng Nhập'; }
        }
    },

    async register(username, password) {
        const errorEl = document.getElementById('registerError');
        const successEl = document.getElementById('registerSuccess');
        const btn = document.getElementById('registerSubmitBtn');
        if (errorEl) errorEl.style.display = 'none';
        if (successEl) successEl.style.display = 'none';
        if (btn) { btn.disabled = true; btn.innerHTML = '<span>⏳</span> Đang tạo tài khoản...'; }

        try {
            const res = await fetch(`${API_BASE}/api/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            const data = await res.json();

            if (res.ok && data.success) {
                if (successEl) {
                    successEl.textContent = '✅ Tạo tài khoản thành công! Đang chuyển đến đăng nhập...';
                    successEl.style.display = 'block';
                }
                // Reset form
                document.getElementById('regUsername').value = '';
                document.getElementById('regPassword').value = '';
                document.getElementById('regConfirmPassword').value = '';
                // Switch to login after 1.5s
                setTimeout(() => switchAuthTab('login'), 1500);
            } else {
                if (errorEl) {
                    errorEl.textContent = data.error || 'Đăng ký thất bại. Vui lòng thử lại.';
                    errorEl.style.display = 'block';
                }
            }
        } catch (e) {
            if (errorEl) {
                errorEl.textContent = 'Lỗi kết nối server. Vui lòng thử lại.';
                errorEl.style.display = 'block';
            }
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = '<span>✨</span> Tạo tài khoản'; }
        }
    },

    async logout() {
        try {
            await fetch(`${API_BASE}/api/logout`, { method: 'POST' });
            window.location.reload();
        } catch (e) {
            console.error("Logout failed", e);
        }
    },

    onLoginSuccess(user) {
        currentUser = user.username || user.name;
        currentRole = user.role;
        
        // Hide login overlay
        const overlay = document.getElementById('loginOverlay');
        if (overlay) overlay.style.display = 'none';
        
        // Update sidebar profile
        const profile = document.getElementById('sidebarUserProfile');
        if (profile) {
            profile.style.display = 'block';
            document.getElementById('userNameText').textContent = user.name || currentUser;
            document.getElementById('userRoleBadge').textContent = currentRole;
        }

        // Apply role-based UI filtering
        this.applyPermissions();
        
        showSuccessToast(`Chào mừng quay trở lại, ${user.name || currentUser}!`);
    },

    showLogin() {
        const overlay = document.getElementById('loginOverlay');
        if (overlay) overlay.style.display = 'flex';
    },

    applyPermissions() {
        const adminElements = document.querySelectorAll('[data-role="admin"]');
        adminElements.forEach(el => {
            el.style.display = (currentRole === 'admin') ? '' : 'none';
        });
    }
};


// ============================================
// Library System (Supabase Cloud + localStorage fallback)
// ============================================
const LibrarySystem = {
    sets: [],
    documents: [],

    async load() {
        try {
            const res = await fetch(`${API_BASE}/api/library`);
            if (res.ok) {
                const data = await res.json();
                if (data.success) {
                    this.sets = (data.sets || []).map(s => ({
                        id: s.id,
                        title: s.title,
                        cards: s.cards,
                        count: s.card_count || (s.cards ? s.cards.length : 0),
                        createdAt: new Date(s.created_at).toLocaleString('vi-VN')
                    }));
                    this.renderSets();
                }
            }
        } catch (e) {
            console.warn('Không lấy được library từ server:', e);
        }
    },

    async loadDocuments() {
        try {
            const res = await fetch(`${API_BASE}/api/documents`);
            if (res.ok) {
                const data = await res.json();
                if (data.success) {
                    this.documents = data.documents || [];
                    this.renderDocuments();
                }
            }
        } catch (e) {
            console.warn('Không lấy được danh sách tài liệu:', e);
        }
    },

    renderDocuments() {
        const grid = document.getElementById('docsGrid');
        const empty = document.getElementById('docsEmptyState');
        if (!grid) return;
        
        grid.innerHTML = '';
        if (this.documents.length === 0) {
            if (empty) empty.style.display = 'flex';
            return;
        }
        if (empty) empty.style.display = 'none';

        this.documents.forEach(doc => {
            const card = document.createElement('div');
            card.className = 'doc-card glass-card';
            const sizeMB = (doc.file_size / (1024 * 1024)).toFixed(2);
            card.innerHTML = `
                <div class="doc-icon">📄</div>
                <div class="doc-info">
                    <div class="doc-name" title="${escapeHtml(doc.file_name)}">${escapeHtml(doc.file_name)}</div>
                    <div class="doc-meta">${sizeMB} MB • ${new Date(doc.created_at).toLocaleDateString('vi-VN')}</div>
                </div>
                <div class="doc-actions">
                    <button class="btn-doc-reuse" onclick="LibrarySystem.reuseDocument('${doc.file_url}', '${escapeHtml(doc.file_name)}')">
                        📖 Học ngay
                    </button>
                    <button class="btn-doc-delete" onclick="LibrarySystem.deleteDocument('${doc.id}')" title="Xóa tài liệu">
                        ✕
                    </button>
                </div>
            `;
            grid.appendChild(card);
        });
    },

    async deleteDocument(id) {
        if (!confirm('Bạn có chắc chắn muốn xóa tài liệu này khỏi thư viện?')) return;
        try {
            const res = await fetch(`${API_BASE}/api/documents/${id}`, { method: 'DELETE' });
            if (res.ok) {
                showSuccessToast('Đã xóa tài liệu thành công!');
                await this.loadDocuments();
            } else {
                showError('Không thể xóa tài liệu.');
            }
        } catch (e) {
            showError('Lỗi kết nối khi xóa tài liệu.');
        }
    },

    async reuseDocument(url, name) {
        if (!confirm(`Bạn muốn sử dụng lại tài liệu "${name}"?`)) return;
        
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/api/documents/reuse`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            const data = await res.json();
            if (res.ok) {
                isRAGInitialized = true;
                isStructureGood = data.is_structure_good !== false;
                showFileInfo(name);
                switchView('generator');
                showSuccessToast('Đã tải tài liệu từ thư viện!');
                updateGenerateButton();
            } else {
                showError(data.error || 'Không thể tải tài liệu');
            }
        } catch (e) {
            showError('Lỗi kết nối khi tải tài liệu');
        } finally {
            setLoading(false);
        }
    },

    renderSets() {
        const grid = document.getElementById('libraryGrid');
        const empty = document.getElementById('libEmptyState');
        if (!grid) return;
        
        grid.innerHTML = '';
        if (this.sets.length === 0) {
            if (empty) empty.style.display = 'flex';
            return;
        }
        if (empty) empty.style.display = 'none';

        this.sets.forEach(set => {
            const card = document.createElement('div');
            card.className = 'lib-card glass-card';
            card.innerHTML = `
                <div class="lib-card-header">
                    <div class="lib-card-title">${escapeHtml(set.title)}</div>
                </div>
                <div class="lib-card-info">
                    <span>🎴 ${set.count} thẻ</span>
                    <span>📅 ${set.createdAt}</span>
                </div>
                <div class="lib-card-actions">
                    <button class="btn-lib-play" onclick="playLibrarySet('${set.id}')">
                        <span>🎮</span> Chơi Ngay
                    </button>
                    <button class="btn-lib-delete" onclick="LibrarySystem.delete('${set.id}')">
                        <span>✕</span>
                    </button>
                </div>
            `;
            grid.appendChild(card);
        });
    },

    async save(title, cards) {
        if (!cards || cards.length === 0) return;
        try {
            const res = await fetch(`${API_BASE}/api/library`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, cards })
            });
            if (res.ok) {
                showSuccessToast('Đã lưu bộ thẻ vào thư viện!');
                await this.load(); 
                return;
            }
        } catch (e) {
            console.warn('Lưu cloud thất bại:', e);
        }
    },

    async delete(id) {
        if (!confirm('Bạn có chắc muốn xóa bộ thẻ này?')) return;
        try {
            const res = await fetch(`${API_BASE}/api/library/${id}`, { method: 'DELETE' });
            if (res.ok) {
                showSuccessToast('Đã xóa bộ thẻ!');
                await this.load();
                return;
            }
        } catch (e) {
            console.warn('Xóa cloud thất bại:', e);
        }
    },

    renderSetsForGame() {
        const grid = document.getElementById('gameSetsGrid');
        const empty = document.getElementById('gameEmptyState');
        if (!grid) return;
        
        grid.innerHTML = '';
        if (this.sets.length === 0) {
            if (empty) empty.style.display = 'flex';
            return;
        }
        if (empty) empty.style.display = 'none';

        this.sets.forEach(set => {
            const card = document.createElement('div');
            card.className = 'game-set-card glass-card';
            card.innerHTML = `
                <div class="game-set-icon">🧩</div>
                <div class="game-set-info">
                    <div class="game-set-title">${escapeHtml(set.title)}</div>
                    <div class="game-set-meta">${set.count} thẻ • ${set.createdAt}</div>
                </div>
                <button class="btn-game-play" onclick="playLibrarySet('${set.id}')">
                    Chơi 🎮
                </button>
            `;
            grid.appendChild(card);
        });
    }
};

// ============================================
// Study System (SRS - Spaced Repetition)
// ============================================
const StudyManager = {
    dueCards: [],
    currentIndex: 0,
    currentSetId: null,

    async init() {
        await LibrarySystem.load();
        this.filterDueCards();
        this.renderStartScreen();
    },

    filterDueCards() {
        this.dueCards = [];
        const now = new Date();
        
        LibrarySystem.sets.forEach(set => {
            if (set.cards && Array.isArray(set.cards)) {
                set.cards.forEach(card => {
                    // Nếu card chưa có srs (mới tạo) hoặc đến hạn
                    const srs = card.srs;
                    if (!srs || !srs.due_date || new Date(srs.due_date) <= now) {
                        this.dueCards.push({
                            ...card,
                            setId: set.id,
                            setName: set.title
                        });
                    }
                });
            }
        });
        
        // Shuffle cards
        this.dueCards.sort(() => Math.random() - 0.5);
    },

    renderStartScreen() {
        const startScreen = document.getElementById('studyStartScreen');
        const arena = document.getElementById('studyArena');
        const emptyState = document.getElementById('studyEmptyState');
        const dueCountEl = document.getElementById('dueCount');

        if (this.dueCards.length > 0) {
            if (startScreen) startScreen.style.display = 'block';
            if (arena) arena.style.display = 'none';
            if (emptyState) emptyState.style.display = 'none';
            if (dueCountEl) dueCountEl.textContent = this.dueCards.length;
        } else {
            if (startScreen) startScreen.style.display = 'none';
            if (arena) arena.style.display = 'none';
            if (emptyState) emptyState.style.display = 'flex';
        }
    },

    startSession() {
        this.currentIndex = 0;
        document.getElementById('studyStartScreen').style.display = 'none';
        document.getElementById('studyArena').style.display = 'block';
        this.renderCurrentCard();
    },

    renderCurrentCard() {
        if (this.currentIndex >= this.dueCards.length) {
            this.finishSession();
            return;
        }

        const card = this.dueCards[this.currentIndex];
        const container = document.getElementById('studyCardContainer');
        const progressText = document.getElementById('studyProgressText');
        const setNameText = document.getElementById('studySetName');
        const actions = document.getElementById('studyActions');
        const flipPrompt = document.getElementById('flipPrompt');

        if (progressText) progressText.textContent = `Thẻ ${this.currentIndex + 1} / ${this.dueCards.length}`;
        if (setNameText) setNameText.textContent = `Bộ thẻ: ${card.setName}`;
        if (actions) actions.style.display = 'none';
        if (flipPrompt) flipPrompt.style.display = 'block';

        if (container) {
            container.innerHTML = '';
            
            const level = card.level || 'N/A';
            const levelCssClass = typeof getLevelCssClass === 'function' ? getLevelCssClass(level) : '';
            
            // Audio button logic
            let audioBtnHtml = '';
            if (card.audio_url || card.audio) {
                const isRemote = card.audio_url ? 'true' : 'false';
                const audioSrc = card.audio_url || card.audio;
                audioBtnHtml = `
                    <button class="audio-btn" onclick="playAudio('${audioSrc}', ${isRemote}, event)" title="Nghe phát âm" style="background: none; border: none; cursor: pointer; font-size: 1.2rem; margin-left: 8px;">🔊</button>
                `;
            }

            const cardEl = document.createElement('div');
            cardEl.className = 'flashcard study-card';
            cardEl.innerHTML = `
                <div class="flashcard-inner">
                    <div class="flashcard-front">
                        <div class="flashcard-header">
                            <div class="flashcard-header-left">
                                <span class="card-level-badge ${levelCssClass}">${escapeHtml(level)}</span>
                                ${audioBtnHtml}
                            </div>
                        </div>
                        <div class="card-content-center">
                            <div class="card-question">${escapeHtml(card.question)}</div>
                        </div>
                        <div class="flip-hint">Nhấp để lật ⤵</div>
                    </div>
                    <div class="flashcard-back">
                        <div class="flashcard-header">
                            <div class="flashcard-header-left">
                                <span class="card-level-badge ${levelCssClass}">${escapeHtml(level)}</span>
                                ${audioBtnHtml}
                            </div>
                        </div>
                        <div class="card-content-center">
                            <div class="card-answer">${escapeHtml(card.answer)}</div>
                        </div>
                        <div class="flip-hint">Nhấp để lật ⤴</div>
                    </div>
                </div>
            `;
            
            cardEl.addEventListener('click', (e) => {
                if (e.target.closest('button')) return;
                cardEl.classList.toggle('flipped');
                if (cardEl.classList.contains('flipped')) {
                    if (actions) actions.style.display = 'flex';
                    if (flipPrompt) flipPrompt.style.display = 'none';
                }
            });

            container.appendChild(cardEl);
        }
    },

    async submitReview(quality) {
        const card = this.dueCards[this.currentIndex];
        
        try {
            const res = await fetch(`${API_BASE}/api/review/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    set_id: card.setId,
                    card_id: card.id,
                    quality: quality
                })
            });
            
            if (res.ok) {
                // Thưởng XP
                const xpGained = quality >= 3 ? 10 : 2;
                GameStats.addXP(xpGained);
                
                this.currentIndex++;
                this.renderCurrentCard();
            } else {
                showError('Lỗi khi gửi kết quả ôn tập');
            }
        } catch (e) {
            showError('Lỗi kết nối khi gửi review');
        }
    },

    finishSession() {
        if (typeof confetti === 'function') {
            confetti({
                particleCount: 150,
                spread: 70,
                origin: { y: 0.6 }
            });
        }
        showSuccessToast('Chúc mừng! Bạn đã hoàn thành phiên ôn tập.');
        this.init(); // Quay lại màn hình bắt đầu/trống
    }
};


function renderLibrary() {
    if (!libraryGrid) return;
    libraryGrid.innerHTML = '';
    
    LibrarySystem.sets.forEach(set => {
        const card = document.createElement('div');
        card.className = 'lib-card';
        card.innerHTML = `
            <div class="lib-card-header">
                <div class="lib-card-title">${escapeHtml(set.title)}</div>
            </div>
            <div class="lib-card-info">
                <span>🎴 ${set.count} thẻ</span>
                <span>📅 ${set.createdAt}</span>
            </div>
            <div class="lib-card-actions">
                <button class="btn-lib-play" onclick="playLibrarySet('${set.id}')">
                    <span>🎮</span> Chơi Ngay
                </button>
                <button class="btn-lib-delete" onclick="LibrarySystem.delete('${set.id}')">
                    <span>✕</span>
                </button>
            </div>
        `;
        libraryGrid.appendChild(card);
    });
}

function playLibrarySet(id) {
    const set = LibrarySystem.sets.find(s => s.id === id);
    if (set) {
        flashcards = set.cards;
        MatchingGame.init();
    }
}

// ============================================
// Analytics System (Tracking & Charting)
// ============================================
const AnalyticsManager = {
    history: [],
    charts: {},

    async load() {
        try {
            const res = await fetch(`${API_BASE}/api/analytics`);
            if (res.ok) {
                const data = await res.json();
                if (data.success) {
                    // Map Supabase format → app format
                    this.history = (data.history || []).map(e => ({
                        id: e.id,
                        timestamp: new Date(e.created_at).toLocaleString('vi-VN'),
                        topic: e.query,
                        mode: e.mode,
                        cardCount: e.card_count,
                        levelStats: e.level_stats,
                        tokens: e.tokens,
                        isRAG: e.is_rag
                    }));
                    this.syncOverview();
                    return;
                }
            }
        } catch (e) {
            console.warn('Load analytics từ server thất bại, dùng localStorage:', e);
        }
        // Fallback localStorage
        const saved = localStorage.getItem('rag_analytics_history');
        this.history = saved ? JSON.parse(saved) : [];
        this.syncOverview();
    },

    save() {
        localStorage.setItem('rag_analytics_history', JSON.stringify(this.history));
        this.syncOverview();
    },

    log(data) {
        const entry = {
            id: Date.now(),
            timestamp: new Date().toLocaleString('vi-VN'),
            ...data
        };
        this.history.unshift(entry);
        if (this.history.length > 50) this.history.pop();
        // localStorage cache (safe write)
        try {
            localStorage.setItem('rag_analytics_history', JSON.stringify(this.history));
        } catch (e) {
            // Quota exceeded → giữ 20 bản gần nhất
            this.history = this.history.slice(0, 20);
            try { localStorage.setItem('rag_analytics_history', JSON.stringify(this.history)); }
            catch (_) { localStorage.removeItem('rag_analytics_history'); }
        }
        this.syncOverview();
        // Sync Supabase (async, không block UI)
        fetch(`${API_BASE}/api/analytics`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        }).catch(e => console.warn('Sync analytics cloud thất bại:', e));
    },


    syncOverview() {
        const totalCards = this.history.reduce((sum, e) => sum + (e.cardCount || 0), 0);
        const totalTokens = this.history.reduce((sum, e) => sum + (e.tokens || 0), 0);
        const avgTokens = this.history.length > 0 ? Math.round(totalTokens / this.history.length) : 0;
        const hits = this.history.filter(e => e.isRAG && e.hitRate).length;
        const totalRAG = this.history.filter(e => e.isRAG).length;
        const hitRate = totalRAG > 0 ? Math.round((hits / totalRAG) * 100) : 0;

        document.getElementById('dashTotalCards').textContent = totalCards.toLocaleString();
        document.getElementById('dashTotalTokens').textContent = totalTokens.toLocaleString();
        document.getElementById('dashAvgTokens').textContent = avgTokens.toLocaleString();
        document.getElementById('dashHitRate').textContent = `${hitRate}%`;
    },

    render() {
        this.syncOverview();
        this.renderTable();
        this.initCharts();
    },

    renderTable() {
        const tbody = document.getElementById('analyticsTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';
        
        this.history.slice(0, 10).forEach(entry => {
            const tr = document.createElement('tr');
            const modeClass = entry.isRAG ? 'mode-rag' : 'mode-ai';
            const modeText = entry.isRAG ? 'RAG' : 'AI';
            
            tr.innerHTML = `
                <td>${entry.timestamp}</td>
                <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(entry.topic)}</td>
                <td><span class="mode-badge ${modeClass}">${modeText}</span></td>
                <td>${entry.cardCount}</td>
                <td data-role="admin">${entry.tokens.toLocaleString()}</td>
            `;
            tbody.appendChild(tr);
        });
        AuthSystem.applyPermissions(); // Ensure new cells are filtered
    },

    initCharts() {
        // Token Usage Bar Chart
        const tokenCtx = document.getElementById('tokenUsageChart');
        if (tokenCtx) {
            if (this.charts.token) this.charts.token.destroy();
            
            const recentHistory = [...this.history].reverse().slice(-10);
            this.charts.token = new Chart(tokenCtx, {
                type: 'bar',
                data: {
                    labels: recentHistory.map(e => e.topic.substring(0, 10) + '...'),
                    datasets: [{
                        label: 'Tokens Used',
                        data: recentHistory.map(e => e.tokens),
                        backgroundColor: '#0075de',
                        borderRadius: 4,
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } },
                        x: { grid: { display: false } }
                    },
                    plugins: { 
                        legend: { display: false },
                        tooltip: { backgroundColor: 'rgba(0,0,0,0.8)', padding: 12, borderRadius: 8 }
                    }
                }
            });
        }

        // Level Distribution Doughnut Chart
        const levelCtx = document.getElementById('levelDistChart');
        if (levelCtx) {
            if (this.charts.level) this.charts.level.destroy();
            
            const levels = { "Nhận biết": 0, "Thông hiểu": 0, "Vận dụng": 0 };
            this.history.forEach(e => {
                if (e.levelStats) {
                    Object.keys(e.levelStats).forEach(l => {
                        if (levels.hasOwnProperty(l)) levels[l] += e.levelStats[l];
                    });
                }
            });

            this.charts.level = new Chart(levelCtx, {
                type: 'doughnut',
                data: {
                    labels: Object.keys(levels),
                    datasets: [{
                        data: Object.values(levels),
                        backgroundColor: ['#1aae39', '#dd5b00', '#ef4444'],
                        borderWidth: 2,
                        borderColor: '#ffffff',
                        hoverOffset: 12
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { color: 'rgba(0,0,0,0.6)', padding: 20, font: { weight: '600' } } }
                    },
                    cutout: '75%'
                }
            });
        }
    }
};

// ============================================
// GameFi - Player Stats System (Supabase cloud sync)
// ============================================
const GameStats = {
    xp: 0,
    level: 1,
    streak: 0,
    lastDate: null,

    async load() {
        try {
            const res = await fetch(`${API_BASE}/api/stats`);
            if (res.ok) {
                const data = await res.json();
                if (data.success && data.stats) {
                    const s = data.stats;
                    this.xp = s.xp || 0;
                    this.level = s.level || 1;
                    this.streak = s.streak || 0;
                    this.lastDate = s.last_date || null;
                    this.updateStreak();
                    this.syncUI();
                    return;
                }
            }
        } catch (e) {
            console.warn('Load stats từ server thất bại, dùng localStorage:', e);
        }
        // Fallback localStorage
        const saved = localStorage.getItem('rag_flashcard_stats');
        if (saved) {
            const data = JSON.parse(saved);
            this.xp = data.xp || 0;
            this.level = data.level || 1;
            this.streak = data.streak || 0;
            this.lastDate = data.lastDate;
        }
        this.updateStreak();
        this.syncUI();
    },

    save() {
        // Lưu localStorage ngay (fast)
        localStorage.setItem('rag_flashcard_stats', JSON.stringify({
            xp: this.xp, level: this.level,
            streak: this.streak, lastDate: this.lastDate
        }));
        // Sync lên Supabase (async, không block UI)
        fetch(`${API_BASE}/api/stats`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                xp: this.xp, level: this.level,
                streak: this.streak,
                last_date: this.lastDate
            })
        }).catch(e => console.warn('Sync stats cloud thất bại:', e));
    },
    
    updateStreak() {
        const today = new Date().toDateString();
        if (this.lastDate === today) return;
        
        const last = this.lastDate ? new Date(this.lastDate) : null;
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        
        if (last && last.toDateString() === yesterday.toDateString()) {
            this.streak += 1;
        } else if (!last || last < yesterday) {
            this.streak = 1;
        }
        
        this.lastDate = today;
        this.save();
    },
    
    addXP(amount) {
        this.xp += amount;
        const nextLevelXp = this.level * 200;
        
        if (this.xp >= nextLevelXp) {
            this.level += 1;
            this.xp -= nextLevelXp;
            this.onLevelUp();
        }
        this.syncUI();
        this.save();
    },
    
    getRank() {
        if (this.level < 5) return 'Apprentice';
        if (this.level < 15) return 'Scholar';
        if (this.level < 30) return 'Sage';
        return 'Legend';
    },
    
    syncUI() {
        if (playerLevelLabel) playerLevelLabel.textContent = this.level;
        if (playerRankLabel) playerRankLabel.textContent = this.getRank();
        if (currentXpLabel) currentXpLabel.textContent = Math.floor(this.xp);
        if (nextLevelXpLabel) nextLevelXpLabel.textContent = this.level * 200;
        if (streakCountLabel) streakCountLabel.textContent = this.streak;
        if (xpBar) xpBar.style.width = `${(this.xp / (this.level * 200)) * 100}%`;
    },
    
    onLevelUp() {
        showSuccessToast(`LEVEL UP! Bạn đã đạt Cấp ${this.level}!`);
        if (window.confetti) {
            confetti({
                particleCount: 150,
                spread: 70,
                origin: { y: 0.6 },
                colors: ['#6366f1', '#06b6d4', '#f59e0b']
            });
        }
    }
};

// ============================================
// Matching Game Logic
// ============================================
const MatchingGame = {
    selectedQ: null,
    selectedA: null,
    pairsCount: 0,
    matchedCount: 0,
    startTime: null,
    timerInterval: null,
    combo: 1,
    
    init() {
        if (flashcards.length < 2) {
            showError("Cần ít nhất 2 thẻ để chơi game!");
            return;
        }
        
        this.reset();
        gameArena.style.display = 'flex';
        
        // Pick random cards (max 6 for focus)
        const gameSize = Math.min(flashcards.length, 6);
        const ShuffledCards = [...flashcards].sort(() => 0.5 - Math.random()).slice(0, gameSize);
        this.pairsCount = gameSize;
        
        const questions = ShuffledCards.map(c => ({ id: c.id, text: c.question }));
        const answers = ShuffledCards.map(c => ({ id: c.id, text: c.answer }));
        
        // Shuffle separately
        questions.sort(() => 0.5 - Math.random());
        answers.sort(() => 0.5 - Math.random());
        
        this.render(questions, answers);
        this.startTimer();
    },
    
    reset() {
        this.matchedCount = 0;
        this.selectedQ = null;
        this.selectedA = null;
        this.combo = 1;
        clearInterval(this.timerInterval);
        if (gameComboLabel) gameComboLabel.textContent = 'x1';
        if (gameProgressBar) gameProgressBar.style.width = '0%';
    },
    
    startTimer() {
        this.startTime = Date.now();
        this.timerInterval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
            const m = Math.floor(elapsed / 60).toString().padStart(2, '0');
            const s = (elapsed % 60).toString().padStart(2, '0');
            if (gameTimerLabel) gameTimerLabel.textContent = `${m}:${s}`;
        }, 1000);
    },
    
    render(qs, as) {
        qGrid.innerHTML = '';
        aGrid.innerHTML = '';
        
        qs.forEach(q => {
            const el = document.createElement('div');
            el.className = 'matching-card';
            el.textContent = q.text;
            el.dataset.id = q.id;
            el.onclick = () => this.select('Q', el);
            qGrid.appendChild(el);
        });
        
        as.forEach(a => {
            const el = document.createElement('div');
            el.className = 'matching-card';
            el.textContent = a.text;
            el.dataset.id = a.id;
            el.onclick = () => this.select('A', el);
            aGrid.appendChild(el);
        });
    },
    
    select(type, el) {
        if (el.classList.contains('matched')) return;
        
        if (type === 'Q') {
            document.querySelectorAll('#qGrid .matching-card').forEach(c => c.classList.remove('selected'));
            this.selectedQ = el;
        } else {
            document.querySelectorAll('#aGrid .matching-card').forEach(c => c.classList.remove('selected'));
            this.selectedA = el;
        }
        
        el.classList.add('selected');
        this.checkMatch();
    },
    
    checkMatch() {
        if (!this.selectedQ || !this.selectedA) return;
        
        const qId = this.selectedQ.dataset.id;
        const aId = this.selectedA.dataset.id;
        
        if (qId === aId) {
            // MATCH!
            const sq = this.selectedQ;
            const sa = this.selectedA;
            sq.classList.add('matched');
            sa.classList.add('matched');
            
            this.matchedCount++;
            this.combo++;
            if (gameComboLabel) gameComboLabel.textContent = `x${this.combo}`;
            
            const progress = (this.matchedCount / this.pairsCount) * 100;
            if (gameProgressBar) gameProgressBar.style.width = `${progress}%`;
            
            GameStats.addXP(20 * this.combo);
            this.flashSuccess();
            
            if (this.matchedCount === this.pairsCount) {
                this.victory();
            }
        } else {
            // WRONG
            const sq = this.selectedQ;
            const sa = this.selectedA;
            sq.classList.add('wrong');
            sa.classList.add('wrong');
            this.combo = 1;
            if (gameComboLabel) gameComboLabel.textContent = 'x1';
            
            setTimeout(() => {
                sq.classList.remove('wrong', 'selected');
                sa.classList.remove('wrong', 'selected');
            }, 400);
        }
        
        this.selectedQ = null;
        this.selectedA = null;
    },
    
    flashSuccess() {
        const flash = document.createElement('div');
        flash.className = 'success-flash';
        flash.textContent = 'CORRECT!';
        document.body.appendChild(flash);
        setTimeout(() => flash.remove(), 800);
    },
    
    victory() {
        clearInterval(this.timerInterval);
        const time = gameTimerLabel ? gameTimerLabel.textContent : '??';
        
        if (window.confetti) {
            confetti({
                particleCount: 200,
                spread: 100,
                origin: { y: 0.6 }
            });
        }
        
        setTimeout(() => {
            alert(`VICTORY! Bạn đã hoàn thành trong ${time} với combo cao nhất x${this.combo}. Nhận ngay XP thưởng!`);
            gameArena.style.display = 'none';
            GameStats.addXP(100);
        }, 1000);
    }
};

// Start Mode management after state
const modeTabs = document.querySelectorAll('.mode-tab[data-mode]');
const desireTabs = document.querySelectorAll('.mode-tab[data-desire]');
const modeContainers = document.querySelectorAll('.mode-container');
// Moved structureWarning to UI elements above

// ============================================
// Background Particles
// ============================================
function createParticles() {
    // Disabled for Notion Style
}

// ============================================
// Character Count
// ============================================
if (inputText) {
    inputText.addEventListener('input', () => {
        const len = inputText.value.length;
        if (charCount && currentInputMode === 'topic') {
            charCount.textContent = `${len.toLocaleString()} characters`;
            charCount.style.display = 'inline';
        } else if (charCount) {
            charCount.style.display = 'none';
        }
        updateGenerateButton();
    });
}

function updateGenerateButton() {
    if (generateBtn && inputText) {
        const value = inputText.value.trim();
        const canGenerateWithoutRAG = currentInputMode === 'topic' && value.length > 0;
        const canGenerateWithRAG = isRAGInitialized && value.length > 0;
        
        generateBtn.disabled = !(canGenerateWithoutRAG || canGenerateWithRAG) || isLoading || isUploading;
        
        // Dynamic label
        if (generateLabel) {
            if (!isRAGInitialized && currentInputMode === 'topic') {
                generateLabel.textContent = 'Generate via AI (Knowledge)';
            } else {
                generateLabel.textContent = 'Generate via RAG';
            }
        }
    }
}

// ============================================
// File Upload (PDF for RAG)
// ============================================
if (fileInput) {
    fileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            showError('Only PDF files are supported for RAG indexing.');
            return;
        }

        hideError();
        showFileInfo(file.name);
        setUploading(true);
        isRAGInitialized = false;

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch(`${API_BASE}/api/upload`, {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to process file');
            }

            isRAGInitialized = true;
            isStructureGood = data.is_structure_good !== false;
            
            // Handle structure quality
            updateInputModeBasedOnStructure();
            
            updateGenerateButton();
            showSuccessToast('Tài liệu đã được xử lý thành công!');
        } catch (error) {
            showError(error.message);
            console.error('File upload error:', error);
        } finally {
            setUploading(false);
            fileInput.value = ''; // Reset file input
        }
    });
}

if (fileRemove) {
    fileRemove.addEventListener('click', () => {
        fileInfo.style.display = 'none';
        fileName.textContent = '';
        isRAGInitialized = false;
        updateGenerateButton();
    });
}

function showFileInfo(name) {
    if (fileName && fileInfo) {
        fileName.textContent = name;
        fileInfo.style.display = 'flex';
    }
}

function setUploading(state) {
    isUploading = state;
    if (uploadLabel) uploadLabel.textContent = state ? 'Uploading...' : 'Upload PDF';
    if (uploadBtn) {
        uploadBtn.style.opacity = state ? '0.6' : '1';
        uploadBtn.style.pointerEvents = state ? 'none' : 'auto';
    }
    updateGenerateButton();
}

// ============================================
// Generate Flashcards (via RAG Query)
// ============================================
if (generateBtn) {
    generateBtn.addEventListener('click', generateRAGFlashcards);
}

function addTraceLine(text) {
    if (tracingConsole) {
        const line = document.createElement('div');
        line.className = 'terminal-line';
        line.textContent = text;
        tracingConsole.appendChild(line);
        tracingConsole.scrollTop = tracingConsole.scrollHeight;
    }
}

async function generateRAGFlashcards() {
    const value = inputText.value.trim();
    const numCards = parseInt(document.getElementById('cardCountSlider')?.value || 3);

    if (!value) {
        showError(currentInputMode === 'topic' ? 'Vui lòng nhập chủ đề.' : 'Vui lòng nhập dải trang.');
        return;
    }

    hideError();
    setLoading(true);
    
    // Tracing now only logs to backend/browser console, not displayed in UI
    // if (tracingConsole) tracingConsole.innerHTML = '<div class="terminal-line">Starting RAG pipeline...</div>';
    if (tracingSection) tracingSection.style.display = 'none';

    // UI Feedback: Loading
    generateBtn.disabled = true;
    inputText.disabled = true;
    const cardCountSlider = document.getElementById('cardCountSlider');
    if (cardCountSlider) cardCountSlider.disabled = true;
    if (pageRangeInput) pageRangeInput.disabled = true;

    try {
        let desireValue = '';
        if (currentDesireMode === 'language') {
            desireValue = '[MODE_LANGUAGE] Tập trung trích xuất các từ vựng, cụm từ hoặc thuật ngữ mới từ văn bản. Bạn chỉ cần cung cấp từ/cụm từ gốc trong phần câu hỏi.';
        }

        const payload = {
            num_cards: numCards,
            user_desire: desireValue
        };
        
        if (currentInputMode === 'topic') {
            payload.query = value;
            payload.page_range = '';
        } else {
            payload.query = '';
            payload.page_range = value;
        }

        const response = await fetch(`${API_BASE}/api/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.error || 'Failed to generate flashcards');
        }

        // Handle SSE Stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            
            // SSE splitting by double newline
            const lines = buffer.split('\n\n');
            buffer = lines.pop(); // Keep partial last line

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const jsonStr = line.replace('data: ', '');
                    try {
                        const data = JSON.parse(jsonStr);
                        
                        if (data.type === 'status') {
                            addTraceLine(data.content);
                        } else if (data.type === 'result') {
                            flashcards = data.flashcards;
                            console.log('📥 Received flashcards:', flashcards.length, flashcards);
                            renderFlashcards(flashcards);
                            if (startMatchingGameBtn) startMatchingGameBtn.style.display = 'inline-flex';
                            showResults();
                            showSuccessToast(`Successfully generated ${flashcards.length} flashcards!`);
                            
                            // Stats & Analytics (không block UI nếu lỗi)
                            try {
                                GameStats.addXP(50);
                                const levelStats = flashcards.reduce((acc, card) => {
                                    const lvl = card.level || "N/A";
                                    acc[lvl] = (acc[lvl] || 0) + 1;
                                    return acc;
                                }, {});
                                AnalyticsManager.log({
                                    topic: value,
                                    isRAG: isRAGInitialized,
                                    cardCount: flashcards.length,
                                    tokens: (data.usage?.input || 0) + (data.usage?.output || 0),
                                    levelStats: levelStats,
                                    hitRate: isRAGInitialized && flashcards.length > 0
                                });
                            } catch (statsErr) {
                                console.warn('Stats/Analytics error (UI vẫn OK):', statsErr);
                            }
                        } else if (data.type === 'error') {
                            throw new Error(data.content);
                        }
                    } catch (e) {
                        console.error("Error parsing SSE chunk:", e, jsonStr);
                    }
                }
            }
        }
    } catch (error) {
        showError(error.message);
        console.error('Generate error:', error);
    } finally {
        setLoading(false);
        // Re-enable UI elements for next generation
        if (generateBtn) generateBtn.disabled = false;
        if (inputText) inputText.disabled = false;
        const cardCountSlider = document.getElementById('cardCountSlider');
        if (cardCountSlider) cardCountSlider.disabled = false;
        if (pageRangeInput) pageRangeInput.disabled = false;
    }
}

function setLoading(state) {
    isLoading = state;
    if (loadingSection) loadingSection.style.display = state ? 'flex' : 'none';
    if (generateLabel) {
        if (state) {
            generateLabel.textContent = 'Generating...';
        } else {
            updateGenerateButton(); // Reset to correct dynamic label
        }
    }
    updateGenerateButton();
}

// ============================================
// Input Mode Management (Tabs)
// ============================================
function updateInputModeBasedOnStructure() {
    const topicTab = document.getElementById('modeTopic');
    const pageTab = document.getElementById('modePage');
    
    if (!isStructureGood) {
        // Disable topic mode and switch to page mode
        if (topicTab) topicTab.disabled = true;
        if (structureWarning) structureWarning.style.display = 'block';
        switchInputMode('page');
    } else {
        if (topicTab) topicTab.disabled = false;
        if (structureWarning) structureWarning.style.display = 'none';
        // Keep current mode or default to topic
    }
}

function switchInputMode(mode) {
    currentInputMode = mode;
    
    // Update tabs UI
    modeTabs.forEach(tab => {
        tab.classList.toggle('active', tab.dataset.mode === mode);
    });
    
    // Update input hint and textarea behavior
    if (inputText) {
        if (mode === 'topic') {
            inputInstruction.textContent = 'Nhập chủ đề hoặc câu hỏi muốn tạo thẻ:';
            inputHint.textContent = 'Ví dụ: Định nghĩa RAG là gì?';
            inputText.placeholder = 'Nhập chủ đề hoặc câu hỏi...';
            inputText.rows = 6;
            if (charCount) charCount.style.display = 'inline';
        } else {
            inputInstruction.textContent = 'Nhập dải trang muốn tạo thẻ:';
            inputHint.textContent = 'Ví dụ: 1-3, 5, 8-12';
            inputText.placeholder = 'Nhập dải trang (ví dụ: 1-5)...';
            inputText.rows = 3;
            if (charCount) charCount.style.display = 'none';
        }
    }
    
    updateGenerateButton();
}

// Add event listeners for tabs
if (modeTabs) {
    modeTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            if (!tab.disabled) switchInputMode(tab.dataset.mode);
        });
    });
}

function switchDesireMode(mode) {
    currentDesireMode = mode;
    
    if (desireTabs) {
        desireTabs.forEach(tab => {
            tab.classList.toggle('active', tab.dataset.desire === mode);
        });
    }
    
    const hintDiv = document.getElementById('desireHint');
    if (hintDiv) {
        if (mode === 'language') {
            hintDiv.innerHTML = '<p>⚠️ <strong>Chế độ Trích xuất từ vựng:</strong> AI sẽ tự động trích xuất từ vựng, thuật ngữ mới kèm theo nghĩa, phiên âm và phát âm.</p>';
        } else {
            hintDiv.innerHTML = '<p>⚠️ <strong>Chế độ Trích xuất nội dung:</strong> AI sẽ tự động trích xuất nội dung theo chủ đề hoặc dải trang và tạo thành câu hỏi, câu trả lời.</p>';
        }
    }
}

if (desireTabs) {
    desireTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            if (!tab.disabled) switchDesireMode(tab.dataset.desire);
        });
    });
}

// ============================================
// Render Flashcards
// ============================================
function renderFlashcards(cards) {
    if (!flashcardsGrid) return;
    flashcardsGrid.innerHTML = '';

    cards.forEach((card, index) => {
        const cardEl = document.createElement('div');
        cardEl.classList.add('flashcard');
        cardEl.setAttribute('data-index', index);
        cardEl.style.animationDelay = `${index * 0.08}s`;

        const level = card.level || 'N/A';
        const levelCssClass = getLevelCssClass(level);

        // Audio button logic (Support both local filename and remote URL)
        let audioBtnHtml = '';
        if (card.audio_url || card.audio) {
            const isRemote = card.audio_url ? 'true' : 'false';
            const audioSrc = card.audio_url || card.audio;
            audioBtnHtml = `
                <button class="audio-btn" onclick="playAudio('${audioSrc}', ${isRemote}, event)" title="Nghe phát âm" style="background: none; border: none; cursor: pointer; font-size: 1.2rem; margin-left: 8px;">🔊</button>
            `;
        }

        cardEl.innerHTML = `
            <div class="flashcard-inner">
                <div class="flashcard-front">
                    <div class="flashcard-header">
                        <div class="flashcard-header-left" style="display: flex; align-items: center;">
                            <span class="card-level-badge ${levelCssClass}">${escapeHtml(level)}</span>
                            ${audioBtnHtml}
                        </div>
                        <div class="flashcard-header-right">
                            <button class="edit-btn" onclick="openEditModal(${index})" title="Edit Flashcard" aria-label="Edit card ${index + 1}">✏️</button>
                        </div>
                    </div>
                    <div class="card-content-center">
                        <div class="card-question">${escapeHtml(card.question)}</div>
                    </div>
                    <div class="flip-hint">Nhấp để lật ⤵</div>
                </div>
                <div class="flashcard-back">
                    <div class="flashcard-header">
                        <div class="flashcard-header-left" style="display: flex; align-items: center;">
                            <span class="card-level-badge ${levelCssClass}">${escapeHtml(level)}</span>
                            ${audioBtnHtml}
                        </div>
                        <div class="flashcard-header-right">
                            <button class="edit-btn" onclick="openEditModal(${index})" title="Edit Flashcard" aria-label="Edit card ${index + 1}">✏️</button>
                        </div>
                    </div>
                    <div class="card-content-center">
                        <div class="card-answer">${escapeHtml(card.answer)}</div>
                    </div>
                    <div class="flip-hint">Nhấp để lật ⤴</div>
                </div>
            </div>
        `;

        // Flip logic
        cardEl.addEventListener('click', (e) => {
            if (e.target.closest('button')) return;
            cardEl.classList.toggle('flipped');
        });

        flashcardsGrid.appendChild(cardEl);
    });

    if (resultsCount) resultsCount.textContent = `${cards.length} cards`;
}

window.playAudio = function(audioSrc, isRemote, event) {
    if (event) {
        event.stopPropagation();
    }
    const url = isRemote ? audioSrc : `${API_BASE}/api/audio?filename=${audioSrc}`;
    const audio = new Audio(url);
    audio.play().catch(e => console.error("Error playing audio:", e));
};

function getLevelCssClass(level) {
    const l = (level || '').toLowerCase();
    if (l.includes('nhận biết')) return 'level-nhan-biet';
    if (l.includes('thông hiểu')) return 'level-thong-hieu';
    if (l.includes('vận dụng')) return 'level-van-dung';
    return '';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// Show / Hide Sections
// ============================================
function showResults() {
    if (resultsSection) resultsSection.style.display = 'block';
}

function hideResults() {
    if (resultsSection) resultsSection.style.display = 'none';
}

function showError(msg) {
    if (errorText && errorMessage) {
        errorText.textContent = msg;
        errorMessage.style.display = 'flex';
    }
}

function hideError() {
    if (errorMessage) errorMessage.style.display = 'none';
}

function showSuccessToast(message) {
    // Simplified Toast logic or alert
    console.log("Success:", message);
}

// ============================================
// Export Anki Function
// ============================================
if (exportAnki) {
    exportAnki.addEventListener('click', async () => {
        if (!flashcards.length) return;

        exportAnki.disabled = true;
        exportAnki.innerHTML = '<span>⏳</span> Đang tạo file Anki...';

        try {
            const defaultName = "Flashcard_AI_Deck";
            let deckName = defaultName;
            if (inputText && inputText.value) {
                deckName = inputText.value.substring(0, 30).replace(/[^a-zA-Z0-9_]/g, '_');
                if (!deckName) deckName = defaultName;
            }

            const res = await fetch(`${API_BASE}/api/export_anki`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cards: flashcards, deck_name: deckName })
            });

            if (!res.ok) {
                let errStr = 'Lỗi khi export Anki';
                try {
                    const err = await res.json();
                    errStr = err.error || errStr;
                } catch (e) {}
                throw new Error(errStr);
            }

            const blob = await res.blob();
            downloadFile(blob, `${deckName}.apkg`, 'application/octet-stream');
            showSuccessToast('Đã tải xuống file .apkg. Bạn có thể import vào Anki!');
        } catch (e) {
            console.error('Error exporting Anki:', e);
            showError('Lỗi tạo file Anki: ' + e.message);
        } finally {
            exportAnki.disabled = false;
            exportAnki.innerHTML = '<span>🗂️</span> Export Anki';
        }
    });
}

function downloadFile(content, filename, mimeType) {
    const blob = content instanceof Blob
        ? content
        : new Blob([content], { type: `${mimeType};charset=utf-8` });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
}

// ============================================
// Keyboard Shortcuts
// ============================================
document.addEventListener('keydown', (e) => {
    // Ctrl+Enter → Generate flashcards
    if (e.ctrlKey && e.key === 'Enter' && generateBtn && !generateBtn.disabled) {
        generateRAGFlashcards();
    }
    // Escape → Close edit modal
    if (e.key === 'Escape' && editModal && editModal.style.display !== 'none') {
        closeEditModal();
    }
});

// ============================================
// Slider
// ============================================
const cardCountSlider = document.getElementById('cardCountSlider');
const sliderValue = document.getElementById('sliderValue');

if (cardCountSlider && sliderValue) {
    cardCountSlider.addEventListener('input', (e) => {
        sliderValue.textContent = e.target.value;
    });
}


// ============================================
// Edit Modal Logic
// ============================================

window.openEditModal = async function(index) {
    currentEditingIndex = index;
    const card = flashcards[index];
    
    // Fill modal fields
    if (editQuestion) editQuestion.value = card.question;
    if (editAnswer) editAnswer.value = card.answer;
    if (modalCardBadge) modalCardBadge.textContent = card.level || 'N/A';
    
    // Reset PDF Viewer state
    if (pdfViewer) pdfViewer.style.opacity = '0.5';
    if (pdfFallback) pdfFallback.style.display = 'none';

    // Directly load the pre-generated PDF for this card
    const t = new Date().getTime();
    const filename = `card_highlight_${card.id}.pdf`;
    
    if (pdfViewer) {
        // Tìm trang chứa nhiều highlight nhất (Dominant Page)
        let targetPage = 1;
        let scrollRatio = 0; // Tỷ lệ vị trí highlight trên trang (0.0 = đỉnh, 1.0 = đáy)
        
        if (card.bboxes && card.bboxes.length > 0) {
            const pageCounts = {};
            card.bboxes.forEach(b => {
                const p = b.p || 1;
                pageCounts[p] = (pageCounts[p] || 0) + 1;
            });
            let maxCount = 0;
            for (const p in pageCounts) {
                if (pageCounts[p] > maxCount) {
                    maxCount = pageCounts[p];
                    targetPage = parseInt(p);
                }
            }
            
            const pageBboxes = card.bboxes.filter(b => b.p === targetPage);
            let y0_min = Infinity;
            pageBboxes.forEach(b => {
                const [x0, y0, x1, y1] = b.b;
                y0_min = Math.min(y0_min, y0);
            });
            
            // Chuyển đổi tọa độ Top-Left của PyMuPDF sang Bottom-Left của Chrome PDF Viewer
            const PAGE_HEIGHT = 842; // Chuẩn A4
            // Dùng +20 để góc nhìn cao hơn dòng bôi vàng 20px -> Dòng bôi vàng sẽ nằm sát mép trên cùng
            let pdfTop = PAGE_HEIGHT - y0_min + 20;
            
            pdfFragment = `#page=${targetPage}&view=FitH,${Math.round(pdfTop)}`;
        }
        
        const pdfBaseUrl = card.pdf_url ? card.pdf_url : `${API_BASE}/api/pdf?filename=${filename}&t=${t}`;
        const pdfUrl = `${pdfBaseUrl}${pdfFragment}`;
        pdfViewer.src = pdfUrl;
        pdfViewer.style.opacity = '1';
    }
    
    if (pdfDownloadLink) {
        pdfDownloadLink.href = card.pdf_url ? card.pdf_url : `${API_BASE}/api/pdf?filename=${filename}&t=${t}`;
    }

    // Show modal
    if (editModal) editModal.classList.add('active');
    setTimeout(() => { if (editQuestion) editQuestion.focus(); }, 280);
};

function closeEditModal() {
    if (editModal) {
        editModal.classList.remove('active');
        // Also ensure style display is reset if needed, though class removal is enough now
        setTimeout(() => {
            if (!editModal.classList.contains('active')) {
                editModal.style.display = 'none';
            }
        }, 300); // Wait for fade out animation
    }
    currentEditingIndex = -1;
}

if (closeModalBtn) closeModalBtn.addEventListener('click', closeEditModal);
if (cancelEditBtn) cancelEditBtn.addEventListener('click', closeEditModal);

if (saveEditBtn) {
    saveEditBtn.addEventListener('click', () => {
        if (currentEditingIndex < 0 || currentEditingIndex >= flashcards.length) return;

        const newQuestion = editQuestion ? editQuestion.value.trim() : '';
        const newAnswer = editAnswer ? editAnswer.value.trim() : '';

        if (!newQuestion || !newAnswer) {
            // Highlight empty fields
            if (!newQuestion && editQuestion) editQuestion.style.borderColor = 'rgba(239,68,68,0.6)';
            if (!newAnswer && editAnswer) editAnswer.style.borderColor = 'rgba(239,68,68,0.6)';
            setTimeout(() => {
                if (editQuestion) editQuestion.style.borderColor = '';
                if (editAnswer) editAnswer.style.borderColor = '';
            }, 1500);
            return;
        }

        const savedIndex = currentEditingIndex;
        flashcards[savedIndex].question = newQuestion;
        flashcards[savedIndex].answer = newAnswer;

        renderFlashcards(flashcards);
        closeEditModal();
        GameStats.addXP(30); // Reward for editing

        // Flash success on the saved card
        const savedCard = flashcardsGrid?.querySelector(`[data-index="${savedIndex}"]`);
        if (savedCard) {
            savedCard.classList.add('just-saved');
            savedCard.addEventListener('animationend', () => savedCard.classList.remove('just-saved'), { once: true });
        }
    });
}

// Close modal when clicking outside (on overlay)
if (editModal) {
    editModal.addEventListener('click', (e) => {
        if (e.target === editModal) closeEditModal();
    });
}
// Initialize app
createParticles();
GameStats.load();
LibrarySystem.load();
AnalyticsManager.load();

// Sidebar Navigation
navItems.forEach(item => {
    item.addEventListener('click', () => switchView(item.dataset.view));
});

// Library Tab Switching
const libTabs = document.querySelectorAll('.lib-tab');
if (libTabs) {
    libTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.libTab;
            
            // UI Update
            libTabs.forEach(t => t.classList.toggle('active', t.dataset.libTab === target));
            
            // Content Update
            const docsContent = document.getElementById('libDocsContent');
            const setsContent = document.getElementById('libSetsContent');
            
            if (docsContent) docsContent.style.display = (target === 'docs') ? 'block' : 'none';
            if (setsContent) setsContent.style.display = (target === 'sets') ? 'block' : 'none';
            
            if (target === 'docs') LibrarySystem.loadDocuments();
            else LibrarySystem.load();
        });
    });
}

// Auth Listeners
const loginFormEl = document.getElementById('loginForm');
if (loginFormEl) {
    loginFormEl.addEventListener('submit', (e) => {
        e.preventDefault();
        const user = document.getElementById('loginUsername').value.trim();
        const pass = document.getElementById('loginPassword').value;
        AuthSystem.login(user, pass);
    });
}

// Register form
const registerFormEl = document.getElementById('registerForm');
if (registerFormEl) {
    // Real-time password match validation
    const regConfirm = document.getElementById('regConfirmPassword');
    const regPass = document.getElementById('regPassword');
    const matchHint = document.getElementById('passwordMatchHint');

    function checkPasswordMatch() {
        const pw = regPass ? regPass.value : '';
        const confirm = regConfirm ? regConfirm.value : '';
        if (!confirm) { if (matchHint) matchHint.style.display = 'none'; return; }
        if (pw === confirm) {
            if (matchHint) {
                matchHint.textContent = '✓ Mật khẩu khớp';
                matchHint.className = 'pw-match-hint match';
                matchHint.style.display = 'block';
            }
        } else {
            if (matchHint) {
                matchHint.textContent = '✗ Mật khẩu không khớp';
                matchHint.className = 'pw-match-hint no-match';
                matchHint.style.display = 'block';
            }
        }
    }

    if (regConfirm) regConfirm.addEventListener('input', checkPasswordMatch);
    if (regPass) regPass.addEventListener('input', checkPasswordMatch);

    registerFormEl.addEventListener('submit', (e) => {
        e.preventDefault();
        const username = document.getElementById('regUsername').value.trim();
        const password = document.getElementById('regPassword').value;
        const confirm = document.getElementById('regConfirmPassword').value;

        const errorEl = document.getElementById('registerError');

        // Client-side validation
        if (username.length < 3) {
            if (errorEl) { errorEl.textContent = 'Tên tài khoản phải có ít nhất 3 ký tự.'; errorEl.style.display = 'block'; }
            return;
        }
        if (password.length < 6) {
            if (errorEl) { errorEl.textContent = 'Mật khẩu phải có ít nhất 6 ký tự.'; errorEl.style.display = 'block'; }
            return;
        }
        if (password !== confirm) {
            if (errorEl) { errorEl.textContent = 'Mật khẩu xác nhận không khớp.'; errorEl.style.display = 'block'; }
            return;
        }

        AuthSystem.register(username, password);
    });
}

// Check initial auth state
AuthSystem.check();

// Logout button
const logoutBtn = document.getElementById('logoutBtn');
if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
        if (confirm("Bạn có chắc chắn muốn đăng xuất?")) {
            AuthSystem.logout();
        }
    });
}


// Save to Library
if (saveToLibraryBtn) {
    saveToLibraryBtn.addEventListener('click', () => {
        if (flashcards.length === 0) {
            showError("Không có thẻ nào để lưu!");
            return;
        }
        
        const defaultName = inputText.value ? inputText.value.substring(0, 30) + (inputText.value.length > 30 ? '...' : '') : 'Bộ thẻ mới';
        const name = prompt("Nhập tên cho bộ thẻ này:", defaultName);
        if (name !== null) {
            LibrarySystem.save(name, flashcards);
        }
    });
}



// Game Launching
if (startMatchingGameBtn) {
    startMatchingGameBtn.addEventListener('click', () => {
        MatchingGame.init();
    });
}

if (exitGameBtn) {
    exitGameBtn.addEventListener('click', () => {
        if (confirm("Bạn có chắc muốn thoát trò chơi? Tiến trình hiện tại sẽ mất.")) {
            clearInterval(MatchingGame.timerInterval);
            gameArena.style.display = 'none';
        }
    });
}

// Study Navigation
if (navStudy) {
    navStudy.addEventListener('click', () => switchView('study'));
}

if (document.getElementById('startStudyBtn')) {
    document.getElementById('startStudyBtn').addEventListener('click', () => {
        StudyManager.startSession();
    });
}
