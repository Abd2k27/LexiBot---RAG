"""
Module de découpage structurel des textes juridiques.
Découpe les textes par articles, chapitres, et sections plutôt que
par nombre de caractères, pour conserver le contexte sémantique.
"""
import re
from config import MAX_CHUNK_SIZE, CHUNK_OVERLAP, MIN_CHUNK_SIZE


# Patterns de structure juridique (ordre de priorité décroissant)
STRUCTURE_PATTERNS = [
    # TITRE I, TITRE II, etc.
    (r'^(TITRE\s+[IVXLCDM]+[\s:.\-].*)', 'titre'),
    # CHAPITRE I, CHAPITRE II, etc.
    (r'^(CHAPITRE\s+[IVXLCDM\d]+[\s:.\-].*)', 'chapitre'),
    # Section 1, Section 2, etc.
    (r'^(Section\s+\d+[\s:.\-].*)', 'section'),
    # Sous-section
    (r'^(Sous[- ]section\s+\d+[\s:.\-].*)', 'sous_section'),
    # Article 1, Article 2, Art. 1, etc.
    (r'^(Art(?:icle)?\.?\s*\d+[\s:.\-])', 'article'),
]


def chunk_document(pages: list[dict]) -> list[dict]:
    """
    Découpe un document en chunks structurels.
    
    Args:
        pages: Liste de pages extraites par pdf_parser
        
    Returns:
        Liste de chunks avec 'text', 'metadata' (dict avec article, chapitre, page, source)
    """
    # Concatener toutes les pages avec marqueurs de page
    full_text = ""
    page_map = []  # (position_debut, page_number, source)
    
    for page in pages:
        start_pos = len(full_text)
        full_text += page["text"] + "\n\n"
        page_map.append((start_pos, page["page_number"], page["source"]))
    
    # Découper par structure juridique
    chunks = _split_by_structure(full_text, page_map)
    
    # Si trop peu de chunks détectés, fallback vers paragraphes
    if len(chunks) < 3:
        chunks = _split_by_paragraphs(full_text, page_map)
    
    # Post-traitement : s'assurer que les chunks ne sont pas trop longs
    final_chunks = []
    for chunk in chunks:
        if len(chunk["text"]) > MAX_CHUNK_SIZE:
            sub_chunks = _split_long_chunk(chunk)
            final_chunks.extend(sub_chunks)
        elif len(chunk["text"]) >= MIN_CHUNK_SIZE:
            final_chunks.append(chunk)
    
    return final_chunks


def _split_by_structure(full_text: str, page_map: list) -> list[dict]:
    """
    Découpe le texte en se basant sur les structures juridiques
    (Articles, Chapitres, Titres, Sections).
    """
    # Trouver toutes les positions de délimiteurs
    delimiters = []
    lines = full_text.split('\n')
    pos = 0
    
    for line in lines:
        for pattern, level in STRUCTURE_PATTERNS:
            if re.match(pattern, line.strip(), re.IGNORECASE):
                delimiters.append({
                    "position": pos,
                    "level": level,
                    "header": line.strip(),
                    "line": line.strip()
                })
                break
        pos += len(line) + 1  # +1 pour le \n
    
    if not delimiters:
        return []
    
    # Construire les chunks entre les délimiteurs
    chunks = []
    current_titre = ""
    current_chapitre = ""
    current_section = ""
    
    for i, delim in enumerate(delimiters):
        # Mettre à jour le contexte hiérarchique
        if delim["level"] == "titre":
            current_titre = delim["header"]
            current_chapitre = ""
            current_section = ""
        elif delim["level"] == "chapitre":
            current_chapitre = delim["header"]
            current_section = ""
        elif delim["level"] == "section":
            current_section = delim["header"]
        
        # Extraire le texte entre ce délimiteur et le suivant
        start = delim["position"]
        end = delimiters[i + 1]["position"] if i + 1 < len(delimiters) else len(full_text)
        chunk_text = full_text[start:end].strip()
        
        if not chunk_text:
            continue
        
        # Construire le contexte hiérarchique comme préfixe
        context_parts = []
        if current_titre:
            context_parts.append(current_titre)
        if current_chapitre:
            context_parts.append(current_chapitre)
        if current_section and delim["level"] not in ("titre", "chapitre"):
            context_parts.append(current_section)
        
        # Trouver la page correspondante
        page_num = _find_page_number(start, page_map)
        source = page_map[0][2] if page_map else "inconnu"
        
        # Construire le chunk avec contexte
        context_prefix = " > ".join(context_parts)
        enriched_text = f"[{context_prefix}]\n{chunk_text}" if context_prefix else chunk_text
        
        chunks.append({
            "text": enriched_text,
            "metadata": {
                "titre": current_titre,
                "chapitre": current_chapitre,
                "section": current_section,
                "article": delim["header"] if delim["level"] == "article" else "",
                "level": delim["level"],
                "page": page_num,
                "source": source,
            }
        })
    
    return chunks


def _split_by_paragraphs(full_text: str, page_map: list) -> list[dict]:
    """
    Fallback : découpe par paragraphes (séparés par double saut de ligne).
    """
    paragraphs = re.split(r'\n\s*\n', full_text)
    chunks = []
    pos = 0
    
    for para in paragraphs:
        para = para.strip()
        if len(para) >= MIN_CHUNK_SIZE:
            page_num = _find_page_number(pos, page_map)
            source = page_map[0][2] if page_map else "inconnu"
            
            chunks.append({
                "text": para,
                "metadata": {
                    "titre": "",
                    "chapitre": "",
                    "section": "",
                    "article": "",
                    "level": "paragraphe",
                    "page": page_num,
                    "source": source,
                }
            })
        pos += len(para) + 2  # +2 pour \n\n
    
    return chunks


def _split_long_chunk(chunk: dict) -> list[dict]:
    """
    Découpe un chunk trop long en sous-chunks avec overlap.
    """
    text = chunk["text"]
    sub_chunks = []
    start = 0
    
    while start < len(text):
        end = start + MAX_CHUNK_SIZE
        
        # Essayer de couper à une fin de phrase
        if end < len(text):
            # Chercher le dernier point, point-virgule ou saut de ligne avant end
            last_break = -1
            for sep in ['. ', '.\n', ';\n', '\n\n', '\n']:
                pos = text.rfind(sep, start, end)
                if pos > last_break:
                    last_break = pos + len(sep)
            
            if last_break > start:
                end = last_break
        
        sub_text = text[start:end].strip()
        
        if len(sub_text) >= MIN_CHUNK_SIZE:
            sub_chunks.append({
                "text": sub_text,
                "metadata": {
                    **chunk["metadata"],
                    "sub_chunk": True,
                }
            })
        
        # Avancer avec overlap
        start = end - CHUNK_OVERLAP if end < len(text) else end
    
    return sub_chunks


def _find_page_number(position: int, page_map: list) -> int:
    """
    Trouve le numéro de page correspondant à une position dans le texte complet.
    """
    page_num = 1
    for start_pos, pnum, _ in page_map:
        if position >= start_pos:
            page_num = pnum
        else:
            break
    return page_num


if __name__ == "__main__":
    # Test rapide
    from pdf_parser import extract_text_from_pdf
    import sys
    
    if len(sys.argv) > 1:
        pages = extract_text_from_pdf(sys.argv[1])
        chunks = chunk_document(pages)
        print(f"✅ {len(chunks)} chunks créés")
        for i, c in enumerate(chunks[:5]):
            meta = c["metadata"]
            print(f"\n--- Chunk {i+1} [{meta['level']}] (page {meta['page']}) ---")
            print(f"  Contexte: {meta.get('titre', '')} > {meta.get('chapitre', '')}")
            print(f"  Texte: {c['text'][:150]}...")
    else:
        print("Usage: python chunker.py <chemin_pdf>")
