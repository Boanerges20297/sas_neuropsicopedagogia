// Dashboard - Dropdown do usuário e inicialização dos gráficos
document.addEventListener('DOMContentLoaded', function() {
    // Dropdown do usuário
    const userBtn = document.querySelector('.user-btn');
    if (userBtn) {
        userBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            this.parentElement.classList.toggle('active');
        });
    }

    document.addEventListener('click', function(e) {
        const dropdown = document.querySelector('.user-dropdown');
        if (dropdown && !dropdown.contains(e.target)) {
            dropdown.classList.remove('active');
        }
    });

    // Inicializar gráficos com dados dos data attributes
    initDashboardCharts();
});

// Função para inicializar os gráficos
function initDashboardCharts() {
    // Ler dados do elemento com data attributes
    const chartDataElement = document.getElementById('chartData');
    if (!chartDataElement) return;

    const testTypesData = JSON.parse(chartDataElement.dataset.testTypes || '{"labels":[],"values":[]}');
    const dailyResponsesData = JSON.parse(chartDataElement.dataset.dailyResponses || '{"labels":[],"values":[]}');
    // Gráfico de Tipos de Teste (Doughnut)
    const testTypesCtx = document.getElementById('testTypesChart');
    if (testTypesCtx) {
        new Chart(testTypesCtx, {
            type: 'doughnut',
            data: {
                labels: testTypesData.labels,
                datasets: [{
                    data: testTypesData.values,
                    backgroundColor: [
                        '#667eea',
                        '#f093fb',
                        '#4facfe',
                        '#43e97b',
                        '#fa709a',
                        '#fee140'
                    ],
                    borderWidth: 0,
                    hoverOffset: 15
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            font: {
                                size: 12,
                                family: "'Inter', sans-serif"
                            },
                            usePointStyle: true,
                            pointStyle: 'circle'
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        cornerRadius: 8,
                        titleFont: {
                            size: 14,
                            weight: 'bold'
                        },
                        bodyFont: {
                            size: 13
                        }
                    }
                },
                cutout: '70%'
            }
        });
    }

    // Gráfico de Respostas Diárias (Bar)
    const dailyResponsesCtx = document.getElementById('dailyResponsesChart');
    if (dailyResponsesCtx) {
        new Chart(dailyResponsesCtx, {
            type: 'bar',
            data: {
                labels: dailyResponsesData.labels,
                datasets: [{
                    label: 'Respostas',
                    data: dailyResponsesData.values,
                    backgroundColor: 'rgba(49, 91, 97, 0.8)',
                    borderColor: '#315b61',
                    borderWidth: 2,
                    borderRadius: 8,
                    hoverBackgroundColor: '#315b61'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        cornerRadius: 8
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1,
                            font: {
                                size: 12
                            }
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            font: {
                                size: 12
                            }
                        }
                    }
                }
            }
        });
    }
}
