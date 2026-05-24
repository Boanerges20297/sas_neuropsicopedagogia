import os
import fitz  # PyMuPDF
from memory_palace import MemoryPalace

def parse_dsm_pdf(pdf_path, memory_palace_db_path="memory_db/memory_palace.db", force=False):
    """Lê o PDF do DSM-5-TR e extrai parágrafos relevantes baseados em palavras-chave clínicas."""
    if not os.path.exists(pdf_path):
        print(f"⚠ PDF do DSM-5-TR não encontrado no caminho: {pdf_path}")
        return False
    
    mp = MemoryPalace(db_path=memory_palace_db_path)
    
    # Se já houver memórias na base e não for forçado, ignora para evitar duplicidade
    stats = mp.get_stats()
    if stats['total_memories'] > 0 and not force:
        print(f"✓ Palácio da Memória já possui {stats['total_memories']} registros indexados. Pulando parser.")
        return True

    print(f"📖 Iniciando leitura inteligente do DSM-5-TR: {pdf_path}")
    
    # Palavras-chave clínicas de interesse para o questionário de AH/SD e neurodesenvolvimento
    target_keywords = [
        "superdotação", "altas habilidades", "dupla excepcionalidade",
        "intelectual", "desenvolvimento", "déficit", "tdah", "autismo", "tea",
        "capacidade cognitiva", "precocidade", "renzulli", "marcos do desenvolvimento"
    ]
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        print(f"✓ PDF carregado com sucesso. Total de páginas: {total_pages}")
        
        imported_chunks = 0
        
        # Iterar pelas páginas do PDF
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text()
            
            # Limpeza rápida
            text_lower = text.lower()
            
            # Verifica se a página contém alguma palavra-chave de interesse
            contains_keywords = any(kw in text_lower for kw in target_keywords)
            if not contains_keywords:
                continue
                
            # Separar a página em blocos/parágrafos semânticos baseados em quebras duplas
            paragraphs = text.split('\n\n')
            for para in paragraphs:
                para = para.strip()
                if len(para) < 80 or len(para) > 1500: # Ignora cabeçalhos curtos ou blocos gigantes ruídos
                    continue
                    
                para_lower = para.lower()
                # Verifica se este parágrafo específico é relevante
                if any(kw in para_lower for kw in target_keywords):
                    # Classificação por categoria básica
                    category = "dsm5_geral"
                    if "superdotação" in para_lower or "altas habilidades" in para_lower:
                        category = "dsm5_superdotacao"
                    elif "tdah" in para_lower or "atenção" in para_lower:
                        category = "dsm5_tdah"
                    elif "autismo" in para_lower or "tea" in para_lower:
                        category = "dsm5_autismo"
                    elif "desenvolvimento" in para_lower:
                        category = "dsm5_desenvolvimento"
                        
                    # Salva no Palácio da Memória
                    mp.learn(
                        content=para,
                        context_domain="clinico_dsm5",
                        clinical_category=category,
                        target_age="todas"
                    )
                    imported_chunks += 1
                    
            # Feedback periódico no console
            if page_num > 0 and page_num % 100 == 0:
                print(f"  .. processando páginas ({page_num}/{total_pages}) - {imported_chunks} fragmentos indexados.")
                
        doc.close()
        print(f"✓ Concluído! {imported_chunks} fragmentos clínicos indexados com sucesso no Palácio da Memória!")
        return True
        
    except Exception as e:
        print(f"⚠ Erro ao processar o PDF: {e}")
        return False

if __name__ == "__main__":
    # Teste de execução rápida local
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pdf_path = os.path.join(project_root, "static", "library", "DSM-5-TR 2023 AHA portugues.pdf")
    parse_dsm_pdf(pdf_path, memory_palace_db_path="../memory_db/memory_palace.db")
