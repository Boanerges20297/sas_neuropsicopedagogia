// Sistema de Pontuação de Respostas
document.addEventListener('DOMContentLoaded', function() {
    const scoreInputs = document.querySelectorAll('.score-input');
    const totalScoreDisplay = document.getElementById('totalScore');
    const saveScoreBtn = document.getElementById('saveScoreBtn');
    const notesTextarea = document.getElementById('evaluationNotes');
    const toast = document.getElementById('toast');

    // Função para atualizar o total
    function updateTotalScore() {
        let total = 0;
        scoreInputs.forEach(input => {
            const value = parseInt(input.value) || 0;
            total += value;
        });
        
        totalScoreDisplay.textContent = total;
        
        // Animação de atualização
        totalScoreDisplay.classList.add('score-updated');
        setTimeout(() => {
            totalScoreDisplay.classList.remove('score-updated');
        }, 300);
    }

    // Event listeners para inputs de pontuação
    scoreInputs.forEach(input => {
        input.addEventListener('change', updateTotalScore);
        input.addEventListener('input', updateTotalScore);
    });

    // Botões + e -
    document.querySelectorAll('.score-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const action = this.dataset.action;
            const container = this.closest('.item-score-input');
            const input = container.querySelector('.score-input');
            let currentValue = parseInt(input.value) || 0;
            const max = parseInt(input.max) || 10;
            const min = parseInt(input.min) || 0;

            if (action === 'plus' && currentValue < max) {
                input.value = currentValue + 1;
            } else if (action === 'minus' && currentValue > min) {
                input.value = currentValue - 1;
            }

            updateTotalScore();
            
            // Feedback visual
            input.classList.add('score-changed');
            setTimeout(() => {
                input.classList.remove('score-changed');
            }, 200);
        });
    });

    // Salvar pontuação
    saveScoreBtn.addEventListener('click', async function() {
        const btn = this;
        const totalScore = parseInt(totalScoreDisplay.textContent) || 0;
        const notes = notesTextarea.value.trim();

        // Desabilitar botão durante o salvamento
        btn.disabled = true;
        btn.innerHTML = '<span>⏳</span> Salvando...';

        try {
            const responseId = window.location.pathname.split('/').pop();
            const response = await fetch(`/admin/resposta/${responseId}/pontuar`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    score: totalScore,
                    notes: notes
                })
            });

            const data = await response.json();

            if (data.success) {
                showToast('✅ Pontuação salva com sucesso!', 'success');
                btn.innerHTML = '<span>✓</span> Salvo!';
                
                setTimeout(() => {
                    btn.innerHTML = '<span>💾</span> Salvar Pontuação';
                    btn.disabled = false;
                }, 2000);
            } else {
                throw new Error(data.message);
            }
        } catch (error) {
            showToast('❌ Erro ao salvar: ' + error.message, 'error');
            btn.innerHTML = '<span>💾</span> Salvar Pontuação';
            btn.disabled = false;
        }
    });

    // Função para mostrar toast
    function showToast(message, type = 'info') {
        toast.textContent = message;
        toast.className = 'toast toast-' + type + ' show';
        
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }

    // Atalhos de teclado
    document.addEventListener('keydown', function(e) {
        // Ctrl + S para salvar
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            saveScoreBtn.click();
        }
    });

    // Confirmar antes de sair se houver alterações não salvas
    let initialScore = totalScoreDisplay.textContent;
    let initialNotes = notesTextarea.value;

    window.addEventListener('beforeunload', function(e) {
        const currentScore = totalScoreDisplay.textContent;
        const currentNotes = notesTextarea.value;
        
        if (currentScore !== initialScore || currentNotes !== initialNotes) {
            e.preventDefault();
            e.returnValue = 'Você tem alterações não salvas. Deseja sair mesmo assim?';
            return e.returnValue;
        }
    });

    // Atualizar valores iniciais após salvar
    saveScoreBtn.addEventListener('click', function() {
        setTimeout(() => {
            initialScore = totalScoreDisplay.textContent;
            initialNotes = notesTextarea.value;
        }, 1000);
    });
});
