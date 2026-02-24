"""
Configuration centralisée du chatbot RAG.
Modifier les valeurs ici pour adapter le système.

Supporte deux modes :
  - Local : variables lues depuis le fichier .env (via python-dotenv)
  - Streamlit Cloud : variables lues depuis st.secrets (configurées dans l'UI)
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env (ignoré si absent)
load_dotenv()


def _get_secret(key: str, default: str = "") -> str:
    """
    Récupère une variable de configuration.
    Priorité : st.secrets > variable d'environnement > valeur par défaut.
    """
    # 1. Essayer st.secrets (Streamlit Cloud)
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    # 2. Fallback sur les variables d'environnement / .env
    return os.getenv(key, default)


# === Chemins ===
PROJECT_DIR = Path(__file__).parent
CHROMA_DB_DIR = PROJECT_DIR / "chroma_db"
DOCUMENTS_DIR = PROJECT_DIR / "documents"

# Créer les dossiers nécessaires
CHROMA_DB_DIR.mkdir(exist_ok=True)
DOCUMENTS_DIR.mkdir(exist_ok=True)

# === LLM Provider ===
# "groq" (cloud, gratuit) ou "ollama" (local)
LLM_PROVIDER = _get_secret("LLM_PROVIDER", "groq")

# === Groq (cloud — défaut pour Streamlit Cloud) ===
GROQ_API_KEY = _get_secret("GROQ_API_KEY", "")
GROQ_MODEL = _get_secret("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

# === Ollama (local — pour le développement) ===
OLLAMA_BASE_URL = _get_secret("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = _get_secret("OLLAMA_MODEL", "gpt-oss:120b-cloud")
OLLAMA_API_KEY = _get_secret("OLLAMA_API_KEY", "")

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
