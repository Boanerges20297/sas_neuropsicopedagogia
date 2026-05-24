import os
from memory_palace import MemoryPalace

class EdgeAIDiagnosticEngine:
    def __init__(self, memory_db_path="memory_db/memory_palace.db"):
        self.mp = MemoryPalace(db_path=memory_db_path)
        
    def _parse_age_to_months(self, years_str, months_str):
        """Converte anos e meses informados em número total de meses."""
        try:
            years = int(years_str) if years_str and years_str.isdigit() else 0
            months = int(months_str) if months_str and months_str.isdigit() else 0
            return (years * 12) + months
        except:
            return None

    def analyze_milestones(self, data):
        """Analisa os marcos de desenvolvimento físico e acadêmico contra normas pediátricas brasileiras."""
        alerts = []
        milestones = {}

        # 1. Marcha (Começou a andar - Padrão: 10 a 15 meses)
        andou_meses = self._parse_age_to_months(data.get('andou_anos'), data.get('andou_meses'))
        if andou_meses is not None:
            milestones['marcha_meses'] = andou_meses
            if andou_meses < 9:
                alerts.append({
                    'type': 'marcha_precoce',
                    'title': 'Marcha Precoce',
                    'description': f'O estudante andou com {andou_meses} meses (média de 10 a 15 meses). Pode sinalizar excelente coordenação e prontidão psicomotora precoce.'
                })
        
        # 2. Fala (Começou a falar - Padrão: 10 a 18 meses)
        falou_meses = self._parse_age_to_months(data.get('falou_anos'), data.get('falou_meses'))
        if falou_meses is not None:
            milestones['fala_meses'] = falou_meses
            if falou_meses < 9:
                alerts.append({
                    'type': 'fala_precoce',
                    'title': 'Linguagem Precoce',
                    'description': f'O estudante começou a falar com {falou_meses} meses (média de 10 a 18 meses). Indicativo comum de altas habilidades na área verbal.'
                })

        # 3. Escrita (Começou a escrever - Padrão: 5 a 6 anos)
        escrita_meses = self._parse_age_to_months(data.get('escrita_comecou_anos'), data.get('escrita_comecou_meses'))
        if escrita_meses is not None:
            milestones['escrita_meses'] = escrita_meses
            if escrita_meses < 48: # Menos de 4 anos (48 meses)
                alerts.append({
                    'type': 'escrita_precoce',
                    'title': 'Escrita Altamente Precoce',
                    'description': f'O estudante começou a escrever com {escrita_meses} meses (média de 5 a 6 anos). Forte marcador de desenvolvimento cognitivo atípico de altas habilidades.'
                })

        # 4. Leitura (Começou a ler - Padrão: 5 a 6 anos)
        leitura_meses = self._parse_age_to_months(data.get('leitura_comecou_anos'), data.get('leitura_comecou_meses'))
        if leitura_meses is not None:
            milestones['leitura_meses'] = leitura_meses
            if leitura_meses < 48: # Menos de 4 anos
                alerts.append({
                    'type': 'leitura_precoce',
                    'title': 'Leitura Precoce (Hiperlexia/AH)',
                    'description': f'O estudante começou a ler com {leitura_meses} meses. A aquisição autônoma de leitura antes dos 4 anos está fortemente ligada ao perfil de Superdotação.'
                })

        return milestones, alerts

    def analyze_renzulli_dimensions(self, characteristics_str):
        """Mapeia as 24 características de comportamento em 5 dimensões intelectuais."""
        dimensions = {
            'intelectual': {'score': 0, 'total': 0, 'name': 'Capacidade Intelectual Geral'},
            'criatividade': {'score': 0, 'total': 0, 'name': 'Pensamento Criativo'},
            'lideranca': {'score': 0, 'total': 0, 'name': 'Capacidade de Liderança'},
            'artes': {'score': 0, 'total': 0, 'name': 'Talento Artístico'},
            'psicomotora': {'score': 0, 'total': 0, 'name': 'Habilidade Psicomotora'}
        }

        if not characteristics_str:
            return {k: 0 for k in dimensions}

        # Separar a string em lista de características marcadas
        selected = [c.strip().lower() for c in characteristics_str.split(',')]

        # Mapeamento detalhado
        mappings = [
            # 0. Facilidade em processar
            {"text": "facilidade em processar", "dims": ["intelectual"]},
            # 1. Aprendizagem rápida
            {"text": "aprendizagem rápida", "dims": ["intelectual"]},
            # 2. Pensador crítico
            {"text": "pensador crítico", "dims": ["intelectual"]},
            # 3. Boa memória
            {"text": "boa memória", "dims": ["intelectual"]},
            # 4. Lógico-matemático
            {"text": "lógico-matemático", "dims": ["intelectual"]},
            # 5. Vocabulário avançado
            {"text": "vocabulário avançado", "dims": ["intelectual", "artes"]},
            # 6. Generalizar e transferir
            {"text": "generalizar e transferir", "dims": ["intelectual"]},
            # 7. Percepções incomuns
            {"text": "percepções incomuns", "dims": ["criatividade", "artes"]},
            # 8. Produzir ideias
            {"text": "produzir ideias", "dims": ["criatividade"]},
            # 9. Pensar fora dos padrões
            {"text": "pensar fora dos padrões", "dims": ["criatividade"]},
            # 10. Originalidade
            {"text": "originalidade", "dims": ["criatividade", "artes"]},
            # 11. Resolver problemas de forma criativa
            {"text": "forma criativa e efetiva", "dims": ["criatividade"]},
            # 12. Abertura a novas experiências
            {"text": "abertura a novas experiências", "dims": ["criatividade", "lideranca"]},
            # 13. Vê relações entre ideias
            {"text": "relações entre ideias diversas", "dims": ["criatividade", "intelectual"]},
            # 14. Independência e autonomia
            {"text": "independência e autonomia", "dims": ["criatividade", "lideranca"]},
            # 15. Apurado senso de humor
            {"text": "apurado senso de humor", "dims": ["criatividade", "lideranca"]},
            # 16. Interesse constante
            {"text": "interesse constante por certos", "dims": ["intelectual"]},
            # 17. Tendência a iniciar suas próprias
            {"text": "iniciar suas próprias atividades", "dims": ["lideranca"]},
            # 18. Persistência
            {"text": "persistência na realização de tarefas", "dims": ["lideranca"]},
            # 19. Auto-imposição
            {"text": "atingir a perfeição", "dims": ["lideranca"]},
            # 20. Ocupa seu tempo
            {"text": "forma produtiva", "dims": ["lideranca"]},
            # 21. Concentra-se por período
            {"text": "concentra-se por período prolongado", "dims": ["intelectual", "lideranca"]},
            # 22. Responsabilidade pessoal
            {"text": "responsabilidade pessoal sobre sua", "dims": ["lideranca"]},
            # 23. Obstinação
            {"text": "obstinação em procurar informações", "dims": ["intelectual", "lideranca"]}
        ]

        # Calcular totais possíveis para normalização em percentual
        for m in mappings:
            for d in m['dims']:
                dimensions[d]['total'] += 1

        # Calcular pontuações baseado nas seleções reais
        for sel in selected:
            for m in mappings:
                if m['text'] in sel:
                    for d in m['dims']:
                        dimensions[d]['score'] += 1
                    break

        # Normalizar para percentual (0 a 100)
        final_scores = {}
        for k, v in dimensions.items():
            final_scores[k] = int((v['score'] / v['total']) * 100) if v['total'] > 0 else 0
            
        return final_scores

    def get_clinical_insights(self, scores, alerts, data):
        """Gera parágrafos ricos de parecer neuropsicopedagógico baseados nos percentuais analisados."""
        insights = []

        # 1. Análise Geral
        max_dim = max(scores, key=scores.get)
        max_score = scores[max_dim]

        dim_names = {
            'intelectual': 'Capacidade Intelectual Geral',
            'criatividade': 'Pensamento Criativo/Originalidade',
            'lideranca': 'Habilidade de Liderança e Comprometimento',
            'artes': 'Expressividade e Talento Artístico',
            'psicomotora': 'Desenvolvimento Psicomotor'
        }

        if max_score > 70:
            insights.append(
                f"O estudante demonstra um perfil cognitivo com traços significativos de Altas Habilidades/Superdotação, "
                f"destacando-se expressivamente na dimensão de **{dim_names[max_dim]}** com uma afinidade de **{max_score}%**. "
                f"Esse índice aponta para uma capacidade acima da média que demanda intervenção pedagógica enriquecida."
            )
        else:
            insights.append(
                f"A análise preliminar aponta para um desenvolvimento intelectual homogêneo, com picos de afinidade na área de "
                f"**{dim_names[max_dim]}** ({max_score}%). Sugere-se acompanhamento longitudinal para avaliar o desdobramento dessas aptidões."
            )

        # 2. Análise de Marcos de Desenvolvimento Precoce
        precoce_alerts = [a for a in alerts if 'precoce' in a['type']]
        if len(precoce_alerts) >= 2:
            insights.append(
                "Nota-se um histórico de desenvolvimento biopsicossocial assíncrono com forte precocidade física e acadêmica "
                f"({', '.join([a['title'] for a in precoce_alerts])}). Esta aceleração nos marcos iniciais é uma correlação clássica descrita "
                "no DSM-5-TR para a prontidão intelectual atípica de estudantes com altas habilidades."
            )

        # 3. Análise de Dupla Excepcionalidade
        interesses = data.get('assunto_interesse', '').lower()
        dificuldades = data.get('disciplinas_dificuldade', '').lower()
        if interesses and ("hiperfoco" in interesses or "obsess" in interesses) and dificuldades:
            insights.append(
                "Identificados indicativos de potencial **Dupla Excepcionalidade** (Superdotação coexistindo com TDAH ou TEA). "
                "O estudante apresenta focos intensos de interesse pedagógico ao mesmo tempo em que relata dificuldades específicas em "
                "outras disciplinas. Recomenda-se triagem diagnóstica diferenciada para evitar o mascaramento mútuo dos sintomas."
            )

        return insights

    def run_full_diagnosis(self, data, context_domain="geral"):
        """Executa a análise diagnóstica completa integrando o Palácio da Memória do DSM-5."""
        characteristics = data.get('observed_characteristics', '')
        
        # 1. Análise heurística das dimensões e marcos
        scores = self.analyze_renzulli_dimensions(characteristics)
        milestones, alerts = self.analyze_milestones(data)
        
        # Adiciona dimensão psicomotora baseada em esportes
        if data.get('pratica_esporte', '').lower() == 'sim':
            scores['psicomotora'] = 80
        elif data.get('qual_esporte'):
            scores['psicomotora'] = 60
            
        insights = self.get_clinical_insights(scores, alerts, data)
        
        # 2. Busca Semântica de Suporte Científico no Palácio da Memória (DSM-5-TR)
        dsm5_citations = []
        
        # Determinar categorias para busca semântica baseado nos maiores escores
        search_terms = []
        if scores['intelectual'] > 60:
            search_terms.append("Superdotação intelectual")
        if scores['criatividade'] > 60:
            search_terms.append("Pensamento original criatividade")
        if any(a['type'] == 'leitura_precoce' for a in alerts):
            search_terms.append("Hiperlexia leitura precoce")
            
        for term in search_terms:
            memories = self.mp.search(
                query=term,
                context_domain="clinico_dsm5",
                clinical_category=None,
                limit=1
            )
            for m in memories:
                dsm5_citations.append({
                    'term_searched': term,
                    'text': m['content'],
                    'category': m['category'],
                    'score': m['score']
                })
                
        return {
            'scores': scores,
            'milestones': milestones,
            'alerts': alerts,
            'insights': insights,
            'dsm5_citations': dsm5_citations
        }
