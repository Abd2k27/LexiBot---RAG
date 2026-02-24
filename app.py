"""
Interface Streamlit pour le chatbot RAG de documents juridiques.
Point d'entrée de l'application.
"""
import streamlit as st
import time
import os
import shutil
from pathlib import Path

from rag_pipeline import RAGPipeline
from config import OLLAMA_MODEL, DOCUMENTS_DIR


# === Configuration de la page ===
st.set_page_config(
    page_title="🤖 LexiBot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# === CSS personnalisé ===
st.markdown("""
<style>
    /* En-tête principal */
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
        text-align: center;
    }
    .main-header h1 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
    }
    .main-header p {
        margin: 0.3rem 0 0 0;
        opacity: 0.85;
        font-size: 0.95rem;
    }
    
    /* Cartes de stats */
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .stat-card .number {
        font-size: 1.8rem;
        font-weight: 700;
    }
    .stat-card .label {
        font-size: 0.8rem;
        opacity: 0.9;
    }
    
    /* Sources */
    .source-card {
        background: #f8f9fa;
        border-left: 4px solid #667eea;
        padding: 0.8rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
        font-size: 0.85rem;
    }
    .source-card .source-header {
        font-weight: 600;
        color: #1a1a2e;
        margin-bottom: 0.3rem;
    }
    .source-card .source-text {
        color: #555;
        font-style: italic;
    }
    
    /* Disclaimer */
    .disclaimer {
        background: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        font-size: 0.8rem;
        color: #856404;
        margin-top: 1rem;
    }
    
    /* Sidebar style */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }
    [data-testid="stSidebar"] * {
        color: #e0e0e0 !important;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: white !important;
    }
    
    /* Chat message styling */
    .stChatMessage {
        border-radius: 12px;
    }
</style>
""", unsafe_allow_html=True)


# === Initialisation du state ===
def init_session_state():
    """Initialise les variables de session Streamlit."""
    if "pipeline" not in st.session_state:
        st.session_state.pipeline = RAGPipeline()
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "indexed_files" not in st.session_state:
        st.session_state.indexed_files = []
    if "indexing_done" not in st.session_state:
        st.session_state.indexing_done = False

init_session_state()


# === Sidebar ===
with st.sidebar:
    st.markdown("## 🤖 LexiBot")
    st.markdown("---")
    
    # Upload de fichiers
    st.markdown("### 📄 Charger des documents")
    uploaded_files = st.file_uploader(
        "Glissez vos fichiers PDF ici",
        type=["pdf"],
        accept_multiple_files=True,
        help="Formats supportés : PDF. Vous pouvez charger plusieurs fichiers."
    )
    
    # Bouton d'indexation
    if uploaded_files:
        if st.button("🚀 Indexer les documents", use_container_width=True, type="primary"):
            with st.spinner("Indexation en cours..."):
                total_chunks = 0
                total_pages = 0
                
                for uploaded_file in uploaded_files:
                    # Sauvegarder le fichier temporairement
                    file_path = DOCUMENTS_DIR / uploaded_file.name
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Indexer
                    try:
                        stats = st.session_state.pipeline.index_pdf(str(file_path))
                        total_chunks += stats["chunks_crees"]
                        total_pages += stats["pages_extraites"]
                        
                        if uploaded_file.name not in st.session_state.indexed_files:
                            st.session_state.indexed_files.append(uploaded_file.name)
                        
                    except Exception as e:
                        st.error(f"Erreur avec {uploaded_file.name}: {str(e)}")
                
                st.session_state.indexing_done = True
                st.success(f"✅ {total_pages} pages → {total_chunks} chunks indexés !")
    
    st.markdown("---")
    
    # Statistiques
    st.markdown("### 📊 Statistiques")
    stats = st.session_state.pipeline.get_stats()
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f'<div class="stat-card">'
            f'<div class="number">{stats["total_chunks"]}</div>'
            f'<div class="label">Chunks indexés</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            f'<div class="stat-card">'
            f'<div class="number">{len(st.session_state.indexed_files)}</div>'
            f'<div class="label">Documents</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    
    # Liste des fichiers indexés
    if st.session_state.indexed_files:
        st.markdown("**Fichiers chargés :**")
        for f in st.session_state.indexed_files:
            st.markdown(f"📎 {f}")
    
    st.markdown("---")
    
    # Configuration
    st.markdown("### ⚙️ Configuration")
    st.markdown(f"**Modèle LLM :** `{OLLAMA_MODEL}`")
    st.markdown(f"**Embeddings :** `{stats['embedding_model']}`")
    
    st.markdown("---")
    
    # Réinitialiser
    if st.button("🗑️ Réinitialiser la base", use_container_width=True):
        st.session_state.pipeline.reset()
        st.session_state.messages = []
        st.session_state.indexed_files = []
        st.session_state.indexing_done = False
        st.success("Base réinitialisée !")
        st.rerun()


# === Zone principale ===
# En-tête
st.markdown(
    '<div class="main-header">'
    '<h1>🤖 LexiBot</h1>'
    '<p>Posez vos questions sur vos documents juridiques et repartez avec les idées plus claires</p>'
    '</div>',
    unsafe_allow_html=True
)

# Message d'accueil si pas de documents
if not st.session_state.indexing_done and stats["total_chunks"] == 0:
    st.info(
        "👋 **Bienvenue !** Commencez par charger un ou plusieurs fichiers PDF "
        "via la barre latérale, puis cliquez sur **Indexer les documents**."
    )
    
    # Exemples de questions
    st.markdown("#### 💡 Exemples de questions que vous pourrez poser :")
    cols = st.columns(2)
    with cols[0]:
        st.markdown(
            "- *Quelles sont les règles pour le commerce électronique ?*\n"
            "- *Quelles sanctions sont prévues en cas d'infraction ?*"
        )
    with cols[1]:
        st.markdown(
            "- *Explique-moi l'article 15 comme si je n'y connaissais rien*\n"
            "- *Quels sont mes droits en matière de données personnelles ?*"
        )

# Afficher l'historique des messages
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="🧑‍💼" if message["role"] == "user" else "⚖️"):
        st.markdown(message["content"])
        
        # Afficher les sources si c'est une réponse assistant
        if message["role"] == "assistant" and message.get("sources"):
            with st.expander(f"📌 Sources ({len(message['sources'])} extraits)", expanded=False):
                for i, source in enumerate(message["sources"], 1):
                    article = source.get("article", "")
                    chapitre = source.get("chapitre", "")
                    page = source.get("page", "")
                    pertinence = source.get("pertinence", "")
                    
                    header_parts = []
                    if article:
                        header_parts.append(article)
                    if chapitre:
                        header_parts.append(chapitre)
                    header = " | ".join(header_parts) if header_parts else f"Extrait {i}"
                    
                    st.markdown(
                        f'<div class="source-card">'
                        f'<div class="source-header">📎 {header} (p.{page}) — {pertinence}</div>'
                        f'<div class="source-text">{source["texte"]}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

# Input de chat
if prompt := st.chat_input("Pose ta question sur le numérique et tes droits..."):
    # Vérifier qu'il y a des documents indexés
    if stats["total_chunks"] == 0:
        st.warning("⚠️ Veuillez d'abord charger et indexer des documents via la barre latérale.")
    else:
        # Afficher la question utilisateur
        with st.chat_message("user", avatar="🧑‍💼"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Générer la réponse
        with st.chat_message("assistant", avatar="⚖️"):
            with st.spinner("🔍 Recherche dans les documents et génération de la réponse..."):
                result = st.session_state.pipeline.ask(prompt)
            
            st.markdown(result["answer"])
            
            # Afficher les sources
            if result["sources"]:
                with st.expander(f"📌 Sources ({len(result['sources'])} extraits)", expanded=False):
                    for i, source in enumerate(result["sources"], 1):
                        article = source.get("article", "")
                        chapitre = source.get("chapitre", "")
                        page = source.get("page", "")
                        pertinence = source.get("pertinence", "")
                        
                        header_parts = []
                        if article:
                            header_parts.append(article)
                        if chapitre:
                            header_parts.append(chapitre)
                        header = " | ".join(header_parts) if header_parts else f"Extrait {i}"
                        
                        st.markdown(
                            f'<div class="source-card">'
                            f'<div class="source-header">📎 {header} (p.{page}) — {pertinence}</div>'
                            f'<div class="source-text">{source["texte"]}</div>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
        
        # Sauvegarder dans l'historique
        st.session_state.messages.append({
            "role": "assistant",
            "content": result["answer"],
            "sources": result["sources"],
        })

# Disclaimer
st.markdown("---")
st.markdown(
    '<div class="disclaimer">'
    '⚠️ <strong>Avertissement :</strong> Cet outil fournit des informations à titre indicatif uniquement. '
    'Il ne constitue pas un conseil juridique professionnel. '
    'Vérifiez toujours les informations avec un professionnel qualifié avant de prendre des décisions.'
    '</div>',
    unsafe_allow_html=True
)
