import pdfplumber

pdf_path = "Teste altas habilidades.pdf"

with pdfplumber.open(pdf_path) as pdf:
    print("=" * 70)
    print(f"PDF: {pdf_path}")
    print(f"Total de páginas: {len(pdf.pages)}")
    print("=" * 70)
    
    for i, page in enumerate(pdf.pages, 1):
        print(f"\n--- PÁGINA {i} ---")
        text = page.extract_text()
        print(text)
        print()
