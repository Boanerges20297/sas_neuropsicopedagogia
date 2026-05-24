import os
import json
import math
import re
import sqlite3

class MemoryPalace:
    def __init__(self, db_path="memory_db/memory_palace.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Inicializa o banco de dados local SQLite para o Palácio da Memória."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                context_domain TEXT NOT NULL,
                clinical_category TEXT NOT NULL,
                target_age TEXT,
                content TEXT NOT NULL,
                tokens TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def _tokenize(self, text):
        """Tokenização simples: minúsculas, remove caracteres especiais e stopwords básicas."""
        text = text.lower()
        # Remove acentuações simples e caracteres especiais
        text = re.sub(r'[^\w\s]', '', text)
        tokens = text.split()
        # Stopwords comuns em português para filtrar ruído semântico
        stopwords = {
            'de', 'a', 'o', 'que', 'e', 'do', 'da', 'em', 'um', 'para', 'com', 'neste',
            'na', 'no', 'uma', 'os', 'as', 'dos', 'das', 'ao', 'aos', 'por', 'mais',
            'se', 'como', 'mais', 'ou', 'este', 'esta', 'seus', 'suas', 'ele', 'ela'
        }
        return [t for t in tokens if t not in stopwords and len(t) > 2]

    def learn(self, content, context_domain="geral", clinical_category="dsm5", target_age="todas"):
        """Armazena um novo fragmento de conhecimento no Palácio da Memória."""
        if not content or len(content.strip()) < 10:
            return False
        
        tokens = self._tokenize(content)
        tokens_json = json.dumps(tokens)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO memories (context_domain, clinical_category, target_age, content, tokens)
            VALUES (?, ?, ?, ?, ?)
        ''', (context_domain, clinical_category, target_age, content.strip(), tokens_json))
        conn.commit()
        conn.close()
        return True

    def search(self, query, context_domain=None, clinical_category=None, target_age=None, limit=3):
        """Busca semântica por Similaridade de Cosseno sobre vetores TF-IDF no contexto especificado."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Conectar e buscar memórias filtradas por contexto
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        sql = "SELECT id, context_domain, clinical_category, target_age, content, tokens FROM memories"
        params = []
        conditions = []
        
        if context_domain:
            conditions.append("context_domain = ?")
            params.append(context_domain)
        if clinical_category:
            conditions.append("clinical_category = ?")
            params.append(clinical_category)
        if target_age and target_age != "todas":
            conditions.append("(target_age = ? OR target_age = 'todas')")
            params.append(target_age)
            
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
            
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return []

        # Processar TF-IDF em tempo real (altamente performático para bases locais de MBs)
        documents = []
        df = {} # Frequência de documento
        
        for row in rows:
            doc_id, domain, cat, age, content, tokens_json = row
            tokens = json.loads(tokens_json)
            documents.append({
                'id': doc_id,
                'domain': domain,
                'category': cat,
                'age': age,
                'content': content,
                'tokens': tokens,
                'tf': self._compute_tf(tokens)
            })
            # Incrementa contagem de DF para termos únicos
            for token in set(tokens):
                df[token] = df.get(token, 0) + 1

        num_docs = len(documents)
        
        # Calcular TF-IDF da query
        query_tf = self._compute_tf(query_tokens)
        query_tfidf = {}
        for token, tf_val in query_tf.items():
            doc_freq = df.get(token, 0)
            # IDF com suavização
            idf = math.log((1 + num_docs) / (1 + doc_freq)) + 1
            query_tfidf[token] = tf_val * idf

        # Calcular similaridade de cosseno para cada documento
        results = []
        for doc in documents:
            doc_tfidf = {}
            for token, tf_val in doc['tf'].items():
                doc_freq = df.get(token, 0)
                idf = math.log((1 + num_docs) / (1 + doc_freq)) + 1
                doc_tfidf[token] = tf_val * idf

            # Cosseno = (A . B) / (||A|| * ||B||)
            dot_product = sum(query_tfidf.get(t, 0) * doc_tfidf.get(t, 0) for t in set(query_tokens).intersection(doc['tokens']))
            
            query_norm = math.sqrt(sum(val ** 2 for val in query_tfidf.values()))
            doc_norm = math.sqrt(sum(val ** 2 for val in doc_tfidf.values()))
            
            similarity = 0.0
            if query_norm > 0 and doc_norm > 0:
                similarity = dot_product / (query_norm * doc_norm)

            if similarity > 0.05: # Threshold mínimo de relevância semântica
                results.append({
                    'content': doc['content'],
                    'context': doc['domain'],
                    'category': doc['category'],
                    'age': doc['age'],
                    'score': round(similarity, 4)
                })

        # Ordenar decrescente por score e limitar
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]

    def _compute_tf(self, tokens):
        """Calcula a frequência do termo (TF) normalizada."""
        tf = {}
        if not tokens:
            return tf
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        length = len(tokens)
        for t in tf:
            tf[t] = tf[t] / length
        return tf

    def get_stats(self):
        """Retorna estatísticas da base de conhecimento persistida."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), COUNT(DISTINCT context_domain), COUNT(DISTINCT clinical_category) FROM memories")
        count, domains, categories = cursor.fetchone()
        conn.close()
        return {
            'total_memories': count,
            'distinct_domains': domains,
            'distinct_categories': categories
        }
