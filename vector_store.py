"""
Module de gestion du Vector Store (ChromaDB + BM25 + Sentence Transformers).
Gère l'indexation et la recherche hybride (sémantique + mots-clés) des chunks.
"""
import re
import chromadb
from chromadb.utils import embedding_functions
from rank_bm25 import BM25Okapi
from config import (
    CHROMA_DB_DIR,
    EMBEDDING_MODEL,
    COLLECTION_NAME,
    TOP_K_RESULTS,
    SIMILARITY_THRESHOLD,
)


def _tokenize_french(text: str) -> list[str]:
    """
    Tokenisation simple pour le français.
    Normalise en minuscule, supprime la ponctuation, filtre les mots courts.
    """
    text = text.lower()
    # Supprimer la ponctuation
    text = re.sub(r'[^\w\s]', ' ', text)
    # Découper et filtrer les mots trop courts (< 3 caractères)
    tokens = [word for word in text.split() if len(word) >= 3]
    return tokens


class VectorStore:
    """Gestionnaire du vector store ChromaDB + BM25 (recherche hybride)."""
    
    def __init__(self, persist_dir: str = None):
        """
        Initialise ChromaDB avec persistance locale + index BM25 en mémoire.
        
        Args:
            persist_dir: Dossier de persistance (défaut: ./chroma_db/)
        """
        persist_path = persist_dir or str(CHROMA_DB_DIR)
        
        # Client ChromaDB persistant
        self._client = chromadb.PersistentClient(path=persist_path)
        
        # Fonction d'embedding multilingue
        self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        
        # Collection ChromaDB
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )
        
        # Index BM25 (reconstruit à partir de ChromaDB)
        self._bm25_index = None
        self._bm25_docs = []      # textes bruts pour le retour
        self._bm25_metadatas = []  # métadonnées associées
        self._rebuild_bm25_index()
    
    def _rebuild_bm25_index(self):
        """Reconstruit l'index BM25 à partir des documents dans ChromaDB."""
        count = self._collection.count()
        if count == 0:
            self._bm25_index = None
            self._bm25_docs = []
            self._bm25_metadatas = []
            return
        
        # Récupérer tous les documents de ChromaDB
        all_data = self._collection.get(
            include=["documents", "metadatas"],
            limit=count,
        )
        
        self._bm25_docs = all_data["documents"]
        self._bm25_metadatas = all_data["metadatas"]
        
        # Tokeniser et construire l'index BM25
        tokenized_docs = [_tokenize_french(doc) for doc in self._bm25_docs]
        self._bm25_index = BM25Okapi(tokenized_docs)
    
    def add_documents(self, chunks: list[dict]) -> int:
        """
        Indexe une liste de chunks dans ChromaDB + BM25.
        
        Args:
            chunks: Liste de dicts avec 'text' et 'metadata'
            
        Returns:
            Nombre de chunks indexés
        """
        if not chunks:
            return 0
        
        # Préparer les données pour ChromaDB
        ids = []
        documents = []
        metadatas = []
        
        existing_count = self._collection.count()
        
        for i, chunk in enumerate(chunks):
            doc_id = f"chunk_{existing_count + i}"
            ids.append(doc_id)
            documents.append(chunk["text"])
            
            meta = {}
            for key, value in chunk.get("metadata", {}).items():
                if isinstance(value, (str, int, float, bool)):
                    meta[key] = value
                else:
                    meta[key] = str(value)
            metadatas.append(meta)
        
        # Indexer par batch dans ChromaDB
        batch_size = 100
        for start in range(0, len(ids), batch_size):
            end = start + batch_size
            self._collection.add(
                ids=ids[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
            )
        
        # Reconstruire l'index BM25 avec les nouveaux documents
        self._rebuild_bm25_index()
        
        return len(ids)
    
    def search(self, query: str, n_results: int = None) -> list[dict]:
        """
        Recherche sémantique simple (ChromaDB uniquement).
        
        Args:
            query: Question de l'utilisateur
            n_results: Nombre de résultats
            
        Returns:
            Liste de dicts avec 'text', 'metadata', 'score'
        """
        n = n_results or TOP_K_RESULTS
        
        if self._collection.count() == 0:
            return []
        
        results = self._collection.query(
            query_texts=[query],
            n_results=min(n, self._collection.count()),
            include=["documents", "metadatas", "distances"]
        )
        
        formatted = []
        for i in range(len(results["documents"][0])):
            distance = results["distances"][0][i]
            similarity = 1 - distance
            
            if similarity >= SIMILARITY_THRESHOLD:
                formatted.append({
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "score": round(similarity, 4),
                })
        
        return formatted
    
    def search_bm25(self, query: str, n_results: int = None) -> list[dict]:
        """
        Recherche par mots-clés (BM25).
        
        Args:
            query: Question de l'utilisateur
            n_results: Nombre de résultats
            
        Returns:
            Liste de dicts avec 'text', 'metadata', 'score'
        """
        n = n_results or TOP_K_RESULTS
        
        if self._bm25_index is None or not self._bm25_docs:
            return []
        
        tokenized_query = _tokenize_french(query)
        if not tokenized_query:
            return []
        
        # Obtenir les scores BM25
        scores = self._bm25_index.get_scores(tokenized_query)
        
        # Trier par score décroissant et garder les top N
        scored_indices = sorted(
            enumerate(scores), key=lambda x: x[1], reverse=True
        )[:n]
        
        results = []
        for idx, score in scored_indices:
            if score > 0:  # Garder uniquement les résultats avec un score positif
                # Normaliser le score BM25 entre 0 et 1
                max_score = scored_indices[0][1] if scored_indices[0][1] > 0 else 1
                normalized_score = score / max_score
                
                results.append({
                    "text": self._bm25_docs[idx],
                    "metadata": self._bm25_metadatas[idx],
                    "score": round(normalized_score, 4),
                })
        
        return results
    
    def search_hybrid(
        self, query: str, n_results: int = None,
        semantic_weight: float = 0.6, bm25_weight: float = 0.4
    ) -> list[dict]:
        """
        Recherche hybride combinant sémantique (ChromaDB) + mots-clés (BM25).
        
        La combinaison des deux méthodes permet de :
        - Sémantique : trouver des passages qui parlent du même sujet avec des mots différents
        - BM25 : trouver des passages contenant exactement les mots-clés de la question
        
        Args:
            query: Question de l'utilisateur
            n_results: Nombre total de résultats
            semantic_weight: Poids de la recherche sémantique (0-1)
            bm25_weight: Poids de la recherche BM25 (0-1)
            
        Returns:
            Liste fusionnée et dédupliquée de dicts avec 'text', 'metadata', 'score'
        """
        n = n_results or TOP_K_RESULTS
        
        # Lancer les deux recherches avec plus de résultats pour avoir de la marge
        fetch_n = n * 2
        semantic_results = self.search(query, n_results=fetch_n)
        bm25_results = self.search_bm25(query, n_results=fetch_n)
        
        # Fusion par score pondéré, dédupliquée par texte
        merged = {}  # text_key -> {"text", "metadata", "score"}
        
        for r in semantic_results:
            text_key = r["text"][:200]
            merged[text_key] = {
                "text": r["text"],
                "metadata": r["metadata"],
                "score": r["score"] * semantic_weight,
            }
        
        for r in bm25_results:
            text_key = r["text"][:200]
            if text_key in merged:
                # Le document est trouvé par les deux méthodes → boost du score
                merged[text_key]["score"] += r["score"] * bm25_weight
            else:
                merged[text_key] = {
                    "text": r["text"],
                    "metadata": r["metadata"],
                    "score": r["score"] * bm25_weight,
                }
        
        # Trier par score fusionné et garder les top N
        sorted_results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
        return sorted_results[:n]
    
    def search_multi_query(
        self, queries: list[str], n_results_per_query: int = 5, max_total: int = 10
    ) -> list[dict]:
        """
        Recherche hybride diversifiée avec plusieurs sous-requêtes.
        
        Pour chaque requête, lance une recherche hybride (sémantique + BM25),
        déduplique les résultats, et favorise la diversité thématique.
        
        Args:
            queries: Liste de requêtes (la question originale + sous-requêtes)
            n_results_per_query: Nombre de résultats par requête
            max_total: Nombre maximum de résultats à retourner
            
        Returns:
            Liste de dicts diversifiés avec 'text', 'metadata', 'score'
        """
        if self._collection.count() == 0:
            return []
        
        # 1. Collecter les résultats de toutes les requêtes (via recherche hybride)
        all_results = {}
        
        for query in queries:
            results = self.search_hybrid(query, n_results=n_results_per_query)
            
            for r in results:
                text_key = r["text"][:200]
                if text_key not in all_results or r["score"] > all_results[text_key]["score"]:
                    all_results[text_key] = r
        
        if not all_results:
            return []
        
        # 2. Sélection diversifiée : favoriser des chapitres/articles différents
        candidates = sorted(all_results.values(), key=lambda x: x["score"], reverse=True)
        
        selected = []
        seen_chapters = {}
        
        # Premier passage : meilleur chunk de chaque chapitre
        for result in candidates:
            chapitre = result["metadata"].get("chapitre", "")
            article = result["metadata"].get("article", "")
            chapter_key = chapitre or article or "unknown"
            
            if chapter_key not in seen_chapters:
                selected.append(result)
                seen_chapters[chapter_key] = 1
                if len(selected) >= max_total:
                    break
        
        # Deuxième passage : compléter avec les résultats restants
        if len(selected) < max_total:
            for result in candidates:
                if result not in selected:
                    selected.append(result)
                    if len(selected) >= max_total:
                        break
        
        return selected
    
    def reset(self):
        """Supprime tous les documents de la collection et l'index BM25."""
        self._client.delete_collection(COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )
        self._bm25_index = None
        self._bm25_docs = []
        self._bm25_metadatas = []
    
    def get_stats(self) -> dict:
        """Retourne les statistiques de la collection."""
        count = self._collection.count()
        return {
            "total_chunks": count,
            "collection_name": COLLECTION_NAME,
            "embedding_model": EMBEDDING_MODEL,
            "bm25_active": self._bm25_index is not None,
        }


# if __name__ == "__main__":
#     # Test rapide
#     vs = VectorStore()
#     print(f"📊 Stats: {vs.get_stats()}")
    
#     # Test d'ajout et de recherche hybride
#     test_chunks = [
#         {
#             "text": "Article 1 : Le commerce électronique est régi par les dispositions de la présente loi.",
#             "metadata": {"article": "Article 1", "page": 1, "source": "test.pdf", "chapitre": "CHAPITRE I"}
#         },
#         {
#             "text": "Article 2 : Toute personne physique ou morale peut exercer une activité de commerce électronique.",
#             "metadata": {"article": "Article 2", "page": 1, "source": "test.pdf", "chapitre": "CHAPITRE I"}
#         },
#         {
#             "text": "Article 50 : La protection des données personnelles est garantie par l'État.",
#             "metadata": {"article": "Article 50", "page": 10, "source": "test.pdf", "chapitre": "CHAPITRE IV"}
#         },
#     ]
    
#     count = vs.add_documents(test_chunks)
#     print(f"✅ {count} chunks indexés")
    
#     print("\n🔍 Recherche hybride : 'données personnelles commerce'")
#     results = vs.search_hybrid("données personnelles commerce")
#     for r in results:
#         print(f"  Score: {r['score']:.3f} | {r['text'][:80]}...")
    
#     vs.reset()
#     print("\n🗑️ Base réinitialisée")
