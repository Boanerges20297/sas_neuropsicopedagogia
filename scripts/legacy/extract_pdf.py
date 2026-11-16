import fitz
from pathlib import Path

pdf_path = Path(r"c:\Users\Boanerges\Documents\Testes - Altas Habilidades\Teste altas habilidades.pdf")
out_path = Path(r"c:\Users\Boanerges\Documents\Testes - Altas Habilidades\extracted_text.txt")

if not pdf_path.exists():
    print(f"PDF not found: {pdf_path}")
    raise SystemExit(1)

with fitz.open(str(pdf_path)) as doc:
    texts = []
    for page in doc:
        texts.append(page.get_text())

out_path.write_text("\n\n---PAGE---\n\n".join(texts), encoding="utf-8")
print(f"Wrote extracted text to {out_path}")
