"""
Configuration centralisée du chatbot RAG.
Modifier les valeurs ici pour adapter le système.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()

# === Chemins ===
PROJECT_DIR = Path(__file__).parent
CHROMA_DB_DIR = PROJECT_DIR / "chroma_db"
DOCUMENTS_DIR = PROJECT_DIR / "documents"

# Créer les dossiers nécessaires
CHROMA_DB_DIR.mkdir(exist_ok=True)
DOCUMENTS_DIR.mkdir(exist_ok=True)

# === Ollama ===
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "glm-4.6:cloud")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")

# === Embeddings ===
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# === Chunking ===
MAX_CHUNK_SIZE = 1500        # Taille max d'un chunk en caractères
CHUNK_OVERLAP = 200          # Overlap entre chunks consécutifs
MIN_CHUNK_SIZE = 100         # Taille min pour garder un chunk

# === RAG ===
TOP_K_RESULTS = 20           # Nombre de chunks à récupérer
SIMILARITY_THRESHOLD = 0.3   # Seuil minimum de similarité (0-1, plus bas = plus permissif)
MULTI_QUERY_COUNT = 3        # Nombre de sous-requêtes pour la décomposition multi-query

# === LLM ===
LLM_TEMPERATURE = 0.1        # Basse pour précision (0.0 = déterministe)
LLM_MAX_TOKENS = 2048        # Longueur max de la réponse
LLM_CONTEXT_WINDOW = 8192    # Fenêtre de contexte du modèle

# === ChromaDB ===
COLLECTION_NAME = "documents_juridiques"
