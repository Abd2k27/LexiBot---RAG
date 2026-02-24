"""
Pipeline RAG complet : Question → Recherche → Prompt → Réponse LLM.
Orchestre le vector store et l'appel à Ollama pour générer des réponses
vulgarisées avec citations des sources.
"""
import json
import re
import requests
from pathlib import Path

from pdf_parser import extract_text_from_pdf
from chunker import chunk_document
from vector_store import VectorStore
from config import (
    LLM_PROVIDER,
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_BASE_URL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_API_KEY,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    TOP_K_RESULTS,
    MULTI_QUERY_COUNT,
)


# Prompt système optimisé pour la vulgarisation juridique
SYSTEM_PROMPT = """Tu es un assistant juridique pédagogue. Ton rôle est d'aider les gens à comprendre des textes de loi et documents juridiques.

## Tes règles absolues :

1. **Base-toi UNIQUEMENT sur les extraits fournis.** Ne réponds JAMAIS avec des connaissances extérieures.
2. **Si tu ne trouves pas la réponse dans les extraits**, dis clairement : "Je ne trouve pas d'information précise sur ce point dans les documents fournis."
3. **Cite toujours tes sources** en mentionnant l'article, la section et la page. Format : (Source : [article/section], page [X])
4. **Explique simplement** : Imagine que tu parles à quelqu'un qui n'a aucune connaissance juridique. Utilise des analogies du quotidien.
5. **Couvre TOUS les aspects pertinents** :
   - Analyse CHAQUE extrait fourni et identifie les différents thèmes/aspects qu'ils couvrent
   - Ne te limite JAMAIS à un seul article ou un seul aspect si les extraits en contiennent plusieurs
   - Organise ta réponse par thème/aspect (ex: protection des données, droit d'auteur, responsabilité pénale, etc.)
6. **Structure ta réponse** :
   - D'abord un résumé qui liste TOUS les aspects trouvés
   - Puis l'explication détaillée organisée par thème
   - Enfin les sources exactes utilisées
7. **N'utilise jamais** "vous devez" ou "il faut". Préfère "selon le texte..." ou "d'après l'article X..."
8. **Réponds toujours en français.**

## Format de réponse :

### 📋 En bref
[Résumé listant TOUS les aspects/thèmes pertinents trouvés dans les extraits]

### 📖 Explication détaillée

#### 🔹 [Thème 1 : ex. Protection des données personnelles]
[Explication du premier aspect avec sources]

#### 🔹 [Thème 2 : ex. Droit d'auteur et propriété intellectuelle]
[Explication du deuxième aspect avec sources]

#### 🔹 [Thème N : ...]
[Continuer pour chaque aspect trouvé dans les extraits]

### 📌 Sources
[Liste complète des articles/sections cités avec numéros de page]
"""

# Prompt pour la décomposition multi-requête
DECOMPOSITION_PROMPT = """Tu es un assistant qui décompose des questions juridiques en sous-requêtes.

Étant donné la question suivante, génère exactement {n} sous-requêtes de recherche qui couvrent des ASPECTS DIFFÉRENTS de la question.
Chaque sous-requête doit cibler un angle juridique distinct (ex: droit pénal, protection des données, propriété intellectuelle, responsabilité civile, etc.).

Réponds UNIQUEMENT avec un JSON valide, rien d'autre. Format :
["sous-requête 1", "sous-requête 2", "sous-requête 3"]

Question : {question}
"""


class RAGPipeline:
    """Pipeline RAG complet pour l'analyse de documents juridiques."""
    
    def __init__(self):
        self.vector_store = VectorStore()
        self._conversation_history = []
    
    def index_pdf(self, pdf_path: str) -> dict:
        """
        Indexe un fichier PDF dans le vector store.
        
        Args:
            pdf_path: Chemin vers le PDF
            
        Returns:
            Dict avec statistiques d'indexation
        """
        # 1. Extraire le texte
        pages = extract_text_from_pdf(pdf_path)
        
        # 2. Découper en chunks structurels
        chunks = chunk_document(pages)
        
        # 3. Indexer dans ChromaDB
        count = self.vector_store.add_documents(chunks)
        
        return {
            "pages_extraites": len(pages),
            "chunks_crees": count,
            "source": Path(pdf_path).name,
        }
    
    def ask(self, question: str, n_results: int = None) -> dict:
        """
        Pose une question et obtient une réponse basée sur les documents.
        Utilise la décomposition multi-requête pour couvrir plusieurs aspects.
        
        Args:
            question: Question en français
            n_results: Nombre de chunks à récupérer
            
        Returns:
            Dict avec 'answer', 'sources', 'model'
        """
        n = n_results or TOP_K_RESULTS
        
        # 1. Décomposer la question en sous-requêtes couvrant différents aspects
        sub_queries = self._decompose_question(question)
        all_queries = [question] + sub_queries
        
        # 2. Recherche diversifiée avec toutes les requêtes
        results = self.vector_store.search_multi_query(
            queries=all_queries,
            n_results_per_query=5,
            max_total=n,
        )
        
        # Fallback sur recherche simple si multi-query échoue
        if not results:
            results = self.vector_store.search(question, n_results=n)
        
        if not results:
            return {
                "answer": "⚠️ Aucun document n'est indexé ou aucun passage pertinent n'a été trouvé. "
                          "Veuillez d'abord charger un document PDF.",
                "sources": [],
                "model": self._get_model_name(),
            }
        
        # 3. Construire le contexte à partir des chunks
        context = self._build_context(results)
        
        # 4. Construire le prompt utilisateur
        user_prompt = self._build_user_prompt(question, context)
        
        # 5. Appeler le LLM
        answer = self._call_llm(user_prompt)
        
        # 6. Formater les sources
        sources = self._format_sources(results)
        
        # 7. Sauvegarder dans l'historique
        self._conversation_history.append({
            "question": question,
            "answer": answer,
        })
        
        return {
            "answer": answer,
            "sources": sources,
            "model": self._get_model_name(),
        }
    
    def _build_context(self, results: list[dict]) -> str:
        """Construit le contexte textuel à partir des résultats de recherche."""
        context_parts = []
        for i, r in enumerate(results, 1):
            meta = r["metadata"]
            source_info = []
            if meta.get("article"):
                source_info.append(meta["article"])
            if meta.get("chapitre"):
                source_info.append(meta["chapitre"])
            if meta.get("page"):
                source_info.append(f"page {meta['page']}")
            
            source_str = " | ".join(source_info) if source_info else "Non spécifié"
            context_parts.append(
                f"--- EXTRAIT {i} (Pertinence: {r['score']:.0%}) [{source_str}] ---\n"
                f"{r['text']}\n"
            )
        
        return "\n".join(context_parts)
    
    def _get_model_name(self) -> str:
        """Retourne le nom du modèle actif selon le provider."""
        if LLM_PROVIDER == "groq":
            return GROQ_MODEL
        return OLLAMA_MODEL
    
    def _decompose_question(self, question: str) -> list[str]:
        """
        Décompose une question en sous-requêtes couvrant différents aspects.
        Utilise le LLM pour identifier les facettes juridiques de la question.
        """
        prompt = DECOMPOSITION_PROMPT.format(n=MULTI_QUERY_COUNT, question=question)
        
        try:
            content = self._call_llm_raw(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=256,
                timeout=60,
            )
            
            # Extraire le JSON de la réponse (le LLM peut ajouter du texte autour)
            json_match = re.search(r'\[.*?\]', content, re.DOTALL)
            if json_match:
                sub_queries = json.loads(json_match.group())
                if isinstance(sub_queries, list) and len(sub_queries) > 0:
                    return [str(q) for q in sub_queries[:MULTI_QUERY_COUNT]]
            
        except Exception:
            pass  # En cas d'erreur, on continue avec la question originale seule
        
        return []
    
    def _build_user_prompt(self, question: str, context: str) -> str:
        """Construit le prompt complet pour le LLM."""
        return (
            f"Voici les extraits pertinents des documents juridiques :\n\n"
            f"{context}\n\n"
            f"---\n\n"
            f"Question de l'utilisateur : {question}\n\n"
            f"IMPORTANT : Analyse TOUS les extraits ci-dessus. Identifie chaque thème/aspect "
            f"juridique distinct qu'ils couvrent et organise ta réponse par thème. "
            f"Ne te limite pas à un seul article. Si l'information n'est pas dans les extraits, dis-le clairement."
        )
    
    def _call_llm(self, user_prompt: str) -> str:
        """Appelle le LLM (Groq ou Ollama) pour générer une réponse."""
        try:
            return self._call_llm_raw(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
                timeout=300,
            )
        except requests.exceptions.ConnectionError:
            provider = "Groq" if LLM_PROVIDER == "groq" else "Ollama"
            return (
                f"❌ **Impossible de se connecter à {provider}.** \n\n"
                + ("Vérifiez votre clé API Groq et votre connexion Internet."
                   if LLM_PROVIDER == "groq" else
                   "Assurez-vous qu'Ollama est en cours d'exécution :\n"
                   "```bash\nollama serve\n```")
            )
        except requests.exceptions.Timeout:
            return (
                "⏳ **Le modèle met trop de temps à répondre.** \n\n"
                "Essayez avec une question plus courte."
            )
        except Exception as e:
            return f"❌ **Erreur lors de l'appel au LLM :** {str(e)}"
    
    def _call_llm_raw(
        self, messages: list[dict], temperature: float,
        max_tokens: int, timeout: int
    ) -> str:
        """
        Appel bas niveau au LLM. Supporte Groq (OpenAI-compatible) et Ollama.
        
        Returns:
            Le contenu texte de la réponse du LLM.
        Raises:
            Exceptions requests en cas d'erreur réseau.
        """
        if LLM_PROVIDER == "groq":
            return self._call_groq(messages, temperature, max_tokens, timeout)
        else:
            return self._call_ollama(messages, temperature, max_tokens, timeout)
    
    def _call_groq(
        self, messages: list[dict], temperature: float,
        max_tokens: int, timeout: int
    ) -> str:
        """Appelle l'API Groq (format OpenAI-compatible)."""
        payload = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}",
        }
        response = requests.post(GROQ_BASE_URL, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
    
    def _call_ollama(
        self, messages: list[dict], temperature: float,
        max_tokens: int, timeout: int
    ) -> str:
        """Appelle l'API Ollama (format natif)."""
        url = f"{OLLAMA_BASE_URL}/api/chat"
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "stream": False,
        }
        headers = {"Content-Type": "application/json"}
        if OLLAMA_API_KEY:
            headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        result = response.json()
        return result.get("message", {}).get("content", "Erreur : réponse vide du modèle.")
    
    def _format_sources(self, results: list[dict]) -> list[dict]:
        """Formate les sources pour l'affichage."""
        sources = []
        for r in results:
            meta = r["metadata"]
            sources.append({
                "texte": r["text"][:300] + ("..." if len(r["text"]) > 300 else ""),
                "article": meta.get("article", ""),
                "chapitre": meta.get("chapitre", ""),
                "section": meta.get("section", ""),
                "page": meta.get("page", ""),
                "source": meta.get("source", ""),
                "pertinence": f"{r['score']:.0%}",
            })
        return sources
    
    def reset(self):
        """Réinitialise le vector store et l'historique."""
        self.vector_store.reset()
        self._conversation_history = []
    
    def get_stats(self) -> dict:
        """Retourne les statistiques du pipeline."""
        vs_stats = self.vector_store.get_stats()
        return {
            **vs_stats,
            "model": self._get_model_name(),
            "provider": LLM_PROVIDER,
            "questions_posees": len(self._conversation_history),
        }


if __name__ == "__main__":
    # Test rapide
    import sys
    
    pipeline = RAGPipeline()
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        print(f"📄 Indexation de {pdf_path}...")
        stats = pipeline.index_pdf(pdf_path)
        print(f"✅ {stats}")
        
        question = "Quelles sont les règles pour le commerce électronique ?"
        if len(sys.argv) > 2:
            question = sys.argv[2]
        
        print(f"\n❓ Question : {question}")
        print("⏳ Génération de la réponse...\n")
        
        result = pipeline.ask(question)
        print(result["answer"])
        print(f"\n📌 Sources ({len(result['sources'])}) :")
        for s in result["sources"]:
            print(f"  - {s['article']} ({s['source']}, p.{s['page']}) [{s['pertinence']}]")
    else:
        print("Usage: python rag_pipeline.py <chemin_pdf> [question]")
