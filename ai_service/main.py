from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import os
from edge_ai import EdgeAIDiagnosticEngine
from memory_palace import MemoryPalace
from parser_dsm import parse_dsm_pdf

app = FastAPI(
    title="SaS Edge AI Microservice",
    description="Serviço independente e leve de inteligência diagnóstica e busca semântica do DSM-5-TR",
    version="1.0.0"
)

# Inicializar os motores com caminhos de persistência relativos à raiz do app
DB_PATH = "memory_db/memory_palace.db"
engine = EdgeAIDiagnosticEngine(memory_db_path=DB_PATH)
mp = MemoryPalace(db_path=DB_PATH)

# ==================== SCHEMAS DE DADOS ====================
class SubmissaoPaciente(BaseModel):
    observed_characteristics: Optional[str] = ""
    andou_anos: Optional[str] = ""
    andou_meses: Optional[str] = ""
    falou_anos: Optional[str] = ""
    falou_meses: Optional[str] = ""
    escrita_comecou_anos: Optional[str] = ""
    escrita_comecou_meses: Optional[str] = ""
    leitura_comecou_anos: Optional[str] = ""
    leitura_comecou_meses: Optional[str] = ""
    pratica_esporte: Optional[str] = ""
    qual_esporte: Optional[str] = ""
    assunto_interesse: Optional[str] = ""
    disciplinas_dificuldade: Optional[str] = ""
    context_domain: Optional[str] = "geral"

class AprendizadoConhecimento(BaseModel):
    content: str
    context_domain: Optional[str] = "clinico_dsm5"
    clinical_category: Optional[str] = "dsm5_manual"
    target_age: Optional[str] = "todas"

# ==================== EVENTOS DE INICIALIZAÇÃO ====================
@app.on_event("startup")
def startup_event():
    """Tenta indexar o manual do DSM-5-TR automaticamente em segundo plano se o arquivo existir."""
    print("🚀 Microsserviço de IA de Borda Iniciado!")
    
    pdf_path = os.getenv(
        "DSM_LIBRARY_PATH",
        "/code/static/library/DSM-5-TR 2023 AHA portugues.pdf"
    )
    
    if os.path.exists(pdf_path):
        print(f"📖 DSM-5-TR PDF encontrado no caminho compartilhado: {pdf_path}")
        print("⚡ Disparando indexação inicial em segundo plano...")
        try:
            # Roda de forma síncrona leve ou rápida se já tiver indexado,
            # ou em thread se for demorar. Como parser_dsm verifica duplicidade, é seguro rodar rápido
            parse_dsm_pdf(pdf_path, memory_palace_db_path=DB_PATH)
        except Exception as e:
            print(f"⚠ Erro na indexação inicial em startup: {e}")
    else:
        print(f"⚠ Arquivo DSM-5-TR não encontrado em static/library. A IA funcionará com heurísticas e indexações dinâmicas.")

# ==================== ROTAS DA API ====================

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "SaS NeuroPsicopedagogia Edge AI",
        "version": "1.0.0",
        "stats": mp.get_stats()
    }

@app.post("/api/v1/analyze")
def analyze_response(paciente: SubmissaoPaciente):
    """Analisa as respostas clínicas do paciente, cruzando-as com o Palácio da Memória do DSM-5-TR."""
    try:
        # Converter objeto Pydantic em dicionário padrão
        data = paciente.dict()
        result = engine.run_full_diagnosis(data, context_domain=paciente.context_domain)
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno no processamento diagnóstico: {str(e)}")

@app.post("/api/v1/learn")
def learn_knowledge(knowledge: AprendizadoConhecimento):
    """Alimenta dinamicamente o Palácio da Memória semântica com novas diretrizes clínicas."""
    try:
        success = mp.learn(
            content=knowledge.content,
            context_domain=knowledge.context_domain,
            clinical_category=knowledge.clinical_category,
            target_age=knowledge.target_age
        )
        if success:
            return {
                "success": True,
                "message": "Conhecimento clínico incorporado com sucesso no Palácio da Memória!",
                "stats": mp.get_stats()
            }
        else:
            raise HTTPException(status_code=400, detail="Conteúdo muito curto ou inválido para processamento semântico.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar conhecimento: {str(e)}")

@app.get("/api/v1/stats")
def get_stats():
    """Retorna estatísticas operacionais da base de conhecimento local."""
    return {
        "success": True,
        "stats": mp.get_stats()
    }

@app.post("/api/v1/trigger_dsm_load")
def trigger_dsm_load(background_tasks: BackgroundTasks):
    """Força o carregamento/indexação manual do PDF do DSM-5-TR via segundo plano (Background Task)."""
    pdf_path = os.getenv(
        "DSM_LIBRARY_PATH",
        "/code/static/library/DSM-5-TR 2023 AHA portugues.pdf"
    )
    
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Arquivo PDF do DSM-5-TR não encontrado no diretório static/library/")
        
    background_tasks.add_task(parse_dsm_pdf, pdf_path, DB_PATH, True)
    return {
        "success": True,
        "message": "Carregamento do DSM-5-TR disparado em segundo plano. Os dados estarão disponíveis em breve!"
    }
