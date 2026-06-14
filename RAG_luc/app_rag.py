import os
import sys
import logging
from flask import Flask, send_from_directory
from flask_cors import CORS

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Load centralized config (this also loads .env)
from config.settings import FLASK_SECRET_KEY, MAX_CONTENT_LENGTH, FLASK_PORT

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='FE_for_backend')
app.secret_key = FLASK_SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
CORS(app, supports_credentials=True)

# ----------------------------------------------------------------
# Register API Blueprints
# ----------------------------------------------------------------
from api_routes.auth import auth_bp
from api_routes.library import library_bp
from api_routes.stats import stats_bp
from api_routes.flashcards import flashcards_bp
from api_routes.notifications import notifications_bp
from api_routes.rag import rag_bp
from api_routes.admin import admin_bp

app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(library_bp, url_prefix='/api')
app.register_blueprint(stats_bp, url_prefix='/api')
app.register_blueprint(flashcards_bp, url_prefix='/api')
app.register_blueprint(notifications_bp, url_prefix='/api')
app.register_blueprint(rag_bp, url_prefix='/api')
app.register_blueprint(admin_bp)

# ----------------------------------------------------------------
# ChatMemoryDB — TẮT ĐỂ TIẾT KIỆM RAM TRÊN RENDER
# ----------------------------------------------------------------
# chat_memory_db đã bị vô hiệu hóa trong chat_handler.py
# Không cần khởi tạo ở đây nữa
logger.info("[App] ChatMemoryDB disabled — skipping initialization.")

# ----------------------------------------------------------------
# Frontend Routes
# ----------------------------------------------------------------
@app.route('/')
def index():
    response = send_from_directory(app.static_folder, 'index.html')
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

@app.route('/<path:path>')
def static_proxy(path):
    response = send_from_directory(app.static_folder, path)
    if path.endswith(('.html', '.js', '.css')):
        ct = response.headers.get('Content-Type', '')
        if 'charset' not in ct:
            if path.endswith('.html'):
                response.headers['Content-Type'] = 'text/html; charset=utf-8'
            elif path.endswith('.js'):
                response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
            elif path.endswith('.css'):
                response.headers['Content-Type'] = 'text/css; charset=utf-8'
    return response

if __name__ == '__main__':
    frontend_dir = os.path.join(os.path.dirname(__file__), 'FE_for_backend')
    if not os.path.exists(frontend_dir):
        os.makedirs(frontend_dir)
        
    port = FLASK_PORT
    logger.info(f"Starting Flask server on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
