"""
Module d'extraction de texte depuis des fichiers PDF.
Utilise PyMuPDF (fitz) pour parser les PDFs tout en conservant la structure.
"""
import fitz  # PyMuPDF
import re
from pathlib import Path


def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """
    Extrait le texte d'un PDF page par page.
    
    Args:
        pdf_path: Chemin vers le fichier PDF
        
    Returns:
        Liste de dicts avec 'text', 'page_number', 'total_pages', 'source'
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Fichier PDF non trouvé : {pdf_path}")
    
    doc = fitz.open(str(pdf_path))
    pages = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        
        # Nettoyage du texte
        text = _clean_text(text)
        
        if text.strip():  # Ignorer les pages vides
            pages.append({
                "text": text,
                "page_number": page_num + 1,
                "total_pages": len(doc),
                "source": pdf_path.name
            })
    
    doc.close()
    return pages


def _clean_text(text: str) -> str:
    """
    Nettoie le texte extrait d'un PDF.
    - Normalise les espaces multiples
    - Supprime les caractères de contrôle
    - Conserve les retours à la ligne significatifs
    """
    # Supprimer les caractères de contrôle (sauf \n et \t)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    # Normaliser les espaces multiples (mais garder les \n)
    text = re.sub(r'[^\S\n]+', ' ', text)
    
    # Supprimer les lignes vides multiples (garder max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Supprimer espaces en début/fin de ligne
    text = re.sub(r' *\n *', '\n', text)
    
    return text.strip()


def get_pdf_metadata(pdf_path: str) -> dict:
    """
    Récupère les métadonnées d'un PDF (titre, auteur, etc.)
    """
    doc = fitz.open(str(pdf_path))
    metadata = doc.metadata
    metadata["page_count"] = len(doc)
    doc.close()
    return metadata


if __name__ == "__main__":
    # Test rapide
    import sys
    if len(sys.argv) > 1:
        pages = extract_text_from_pdf(sys.argv[1])
        print(f"✅ {len(pages)} pages extraites")
        print(f"\n📄 Première page (extrait):\n{pages[0]['text'][:500]}")
    else:
        print("Usage: python pdf_parser.py <chemin_pdf>")
