import sqlite3
from datetime import datetime

DB_PATH = 'app_database.db'

def update_test_questions():
    """Atualiza o teste de Altas Habilidades com todas as questões do PDF"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        print("\n" + "="*70)
        print("ATUALIZANDO TESTE DE ALTAS HABILIDADES COM QUESTÕES DO PDF")
        print("="*70)
        
        # Buscar o teste
        cursor.execute("SELECT id FROM tests WHERE titulo LIKE '%Altas Habilidades%'")
        test = cursor.fetchone()
        
        if not test:
            print("\n❌ Teste não encontrado!")
            return
        
        test_id = test[0]
        
        # Deletar questões antigas
        cursor.execute("DELETE FROM questions WHERE test_id = ?", (test_id,))
        print(f"\n✓ Questões antigas removidas")
        
        # Lista completa de questões baseadas no PDF
        questions = [
            # SEÇÃO II - Desenvolvimento
            ("text", "A mãe teve algum problema durante a gestação?", "", 1, True),
            ("text", "O parto foi normal ou cesárea?", "", 1, True),
            ("textarea", "Houve algum problema durante ou após o parto? Descreva:", "", 1, False),
            ("text", "Quando bebê, ele(a) dormia bem?", "", 1, True),
            ("textarea", "Atualmente, como é o sono dele(a)?", "", 1, True),
            ("text", "Começou a andar com quantos anos e meses?", "", 1, True),
            ("text", "Começou a falar com quantos anos e meses?", "", 1, True),
            ("text", "Frases completas com quantos anos e meses?", "", 1, True),
            ("textarea", "Seu filho(a) teve algum problema de saúde durante os primeiros anos de vida? Qual?", "", 1, False),
            
            # SEÇÃO III - Vida Escolar
            ("text", "O ingresso na escola foi aos quantos anos e meses?", "", 1, True),
            ("yes_no", "Antes de ingressar na escola, já sabia ler ou escrever?", "Sim,Não", 1, True),
            ("textarea", "Se sim, especifique o que já sabia:", "", 1, False),
            ("text", "Começou a ler aos quantos anos e meses?", "", 1, True),
            ("text", "Começou a escrever aos quantos anos e meses?", "", 1, True),
            ("text", "Começou a fazer cálculos matemáticos aos quantos anos e meses?", "", 1, True),
            ("multiple_choice", "Em relação aos estudantes da mesma faixa etária, ele(a) é considerado(a):", "com dificuldade,com facilidade para aprender", 1, True),
            ("multiple_choice", "Geralmente faz seus deveres:", "sozinho(a),com ajuda de alguém", 1, True),
            ("text", "Quem o(a) ajuda nas tarefas escolares?", "", 1, False),
            ("textarea", "Em quais disciplinas tem mais facilidade?", "", 1, True),
            ("textarea", "Em quais disciplinas tem mais dificuldade?", "", 1, False),
            ("textarea", "Meu(minha) filho(a) demonstra habilidade em:", "", 2, True),
            ("textarea", "O assunto que tem mais interesse é:", "", 1, True),
            ("yes_no", "Gosta de ler?", "Sim,Não", 1, True),
            ("multiple_choice", "Qual tipo de leitura?", "livros técnicos,gibis,literatura,outros", 1, False),
            ("multiple_choice", "Qual a opinião do seu filho(a) com relação à escola?", "gosta,não gosta", 1, True),
            ("textarea", "Por quê?", "", 1, False),
            ("textarea", "O que ele(a) acha dos professores?", "", 1, True),
            ("textarea", "O que os professores falam a respeito dele(a)?", "", 2, True),
            ("textarea", "O que ele(a) pensa dos colegas?", "", 1, True),
            ("yes_no", "Já participou de concursos na escola?", "Sim,Não", 1, False),
            ("textarea", "Foi premiado(a)? Especifique:", "", 1, False),
            ("yes_no", "Já foi acelerado(a) alguma vez?", "Sim,Não", 1, False),
            ("text", "Para qual série?", "", 1, False),
            ("yes_no", "Já reprovou alguma vez?", "Sim,Não", 1, False),
            ("text", "Em qual(is) série(s)?", "", 1, False),
            
            # SEÇÃO IV - Vida Social
            ("yes_no", "Tem muitos amigos?", "Sim,Não", 1, True),
            ("multiple_choice", "Gosta de ficar:", "sozinho,em grupo,sempre com alguma companhia", 1, True),
            ("textarea", "Como é o relacionamento com os familiares?", "", 2, True),
            ("yes_no", "Pratica algum esporte?", "Sim,Não", 1, False),
            ("text", "Qual esporte?", "", 1, False),
            ("text", "Com que frequência pratica esporte?", "", 1, False),
            ("yes_no", "Vai a teatros, cinemas, museus, etc.?", "Sim,Não", 1, False),
            ("text", "Com que frequência vai a eventos culturais?", "", 1, False),
            ("yes_no", "Tem alguma religião?", "Sim,Não", 1, False),
            ("text", "Especifique a religião:", "", 1, False),
            ("yes_no", "Vai à Igreja?", "Sim,Não", 1, False),
            ("text", "Com que frequência vai à Igreja?", "", 1, False),
            ("yes_no", "Participa de alguma atividade extraescolar?", "Sim,Não", 1, False),
            ("textarea", "Especifique as atividades extraescolares:", "", 1, False),
            ("textarea", "Nas horas de lazer o que ele(a) mais gosta de fazer?", "", 2, True),
            ("textarea", "Houve alguma mudança significativa durante o desenvolvimento de seu filho(a)? Especifique:", "", 2, False),
            ("yes_no", "É hábito da família realizar alguma atividade em comum?", "Sim,Não", 1, True),
            ("textarea", "Especifique atividades em comum e frequência:", "", 1, False),
            
            # SEÇÃO V - Características (24 itens de checklist)
            ("yes_no", "Facilidade em processar informações e emitir respostas apropriadas", "Sim,Não", 1, True),
            ("yes_no", "Aprendizagem rápida/fácil e com pouca repetição", "Sim,Não", 1, True),
            ("yes_no", "Pensador crítico; gosta de lidar com problemas abstratos/complexos", "Sim,Não", 1, True),
            ("yes_no", "Boa memória e facilidade para acumular conhecimento", "Sim,Não", 1, True),
            ("yes_no", "Habilidade de raciocínio lógico-matemático", "Sim,Não", 1, True),
            ("yes_no", "Apresenta vocabulário avançado para idade/série; é verbalmente fluente", "Sim,Não", 1, True),
            ("yes_no", "Capacidade de generalizar e transferir aprendizagem", "Sim,Não", 1, True),
            ("yes_no", "Mostra percepções incomuns na resolução de problemas", "Sim,Não", 1, True),
            ("yes_no", "Facilidade e agilidade para produzir ideias", "Sim,Não", 1, True),
            ("yes_no", "Flexibilidade ou facilidade para pensar fora dos padrões", "Sim,Não", 1, True),
            ("yes_no", "Originalidade de pensamento ou respostas diferentes/incomuns", "Sim,Não", 1, True),
            ("yes_no", "Capacidade de resolver problemas de forma criativa e efetiva", "Sim,Não", 1, True),
            ("yes_no", "Abertura a novas experiências; disposição para correr riscos", "Sim,Não", 1, True),
            ("yes_no", "Vê relações entre ideias aparentemente diversas", "Sim,Não", 1, True),
            ("yes_no", "Independência e autonomia de pensamento", "Sim,Não", 1, True),
            ("yes_no", "Apurado senso de humor", "Sim,Não", 1, True),
            ("yes_no", "Interesse constante por certos tópicos ou problemas", "Sim,Não", 1, True),
            ("yes_no", "Tendência a iniciar suas próprias atividades", "Sim,Não", 1, True),
            ("yes_no", "Persistência na realização das tarefas de seu interesse", "Sim,Não", 1, True),
            ("yes_no", "Auto-imposição para atingir a perfeição", "Sim,Não", 1, True),
            ("yes_no", "Ocupa seu tempo de forma produtiva sem estimulação constante", "Sim,Não", 1, True),
            ("yes_no", "Concentra-se em uma atividade por período prolongado", "Sim,Não", 1, True),
            ("yes_no", "Preferência por situações com responsabilidade pessoal", "Sim,Não", 1, True),
            ("yes_no", "Obstinação em procurar informações sobre tópicos de interesse", "Sim,Não", 1, True),
            
            # Questões finais
            ("textarea", "Toma alguma medicação controlada? Especifique:", "", 1, False),
            ("textarea", "Faz algum acompanhamento médico/psicológico/psicopedagógico? Especifique:", "", 1, False),
            ("textarea", "Observações gerais:", "", 2, False),
        ]
        
        # Inserir questões
        ordem = 1
        for tipo, enunciado, opcoes, pontos, obrigatoria in questions:
            cursor.execute('''
                INSERT INTO questions (
                    test_id, ordem, tipo, enunciado, opcoes,
                    resposta_esperada, pontos, obrigatoria, ativa
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                test_id, ordem, tipo, enunciado, opcoes,
                '', pontos, 1 if obrigatoria else 0, 1
            ))
            ordem += 1
        
        # Atualizar tempo estimado e pontuação máxima
        cursor.execute('''
            UPDATE tests 
            SET tempo_estimado = 30, 
                pontuacao_maxima = ?,
                descricao = ?
            WHERE id = ?
        ''', (
            len(questions),
            'Questionário completo para identificação de indicadores de altas habilidades/superdotação em crianças e adolescentes. Baseado no formulário oficial da SEEDF.',
            test_id
        ))
        
        conn.commit()
        
        print(f"✓ {len(questions)} questões adicionadas")
        print(f"✓ Tempo estimado atualizado: 30 minutos")
        print(f"✓ Pontuação máxima: {len(questions)} pontos")
        
        print("\n" + "="*70)
        print("✅ ATUALIZAÇÃO CONCLUÍDA COM SUCESSO!")
        print("="*70)
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    update_test_questions()
