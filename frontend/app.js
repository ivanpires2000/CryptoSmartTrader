// Configuração do axios
axios.defaults.baseURL = 'http://localhost:5000';
axios.defaults.headers.common['Content-Type'] = 'application/json';
axios.defaults.withCredentials = true;

// Interceptor para tratar erros
axios.interceptors.response.use(
    response => response,
    error => {
        let errorMessage = 'Ocorreu um erro na requisição.';
        
        if (error.response) {
            // Erro do servidor
            if (error.response.status === 429) {
                errorMessage = 'Muitas requisições. Por favor, aguarde um momento.';
            } else if (error.response.status === 500) {
                errorMessage = 'Erro interno do servidor. Tente novamente mais tarde.';
            } else if (error.response.data && error.response.data.error) {
                errorMessage = error.response.data.error;
            }
        } else if (error.request) {
            // Erro de conexão
            errorMessage = 'Não foi possível conectar ao servidor.';
        }
        
        return Promise.reject(errorMessage);
    }
);

// Variáveis globais
let priceChart = null;

// Função para mostrar mensagens
function showMessage(message, type = 'success') {
    const messagesDiv = document.getElementById('messages');
    const messageElement = document.createElement('div');
    messageElement.className = `message ${type}`;
    messageElement.textContent = message;
    messagesDiv.appendChild(messageElement);

    // Remover a mensagem após 5 segundos
    setTimeout(() => {
        messageElement.remove();
    }, 5000);
}

// Função para formatar números
function formatNumber(number, decimals = 2) {
    return new Intl.NumberFormat('pt-BR', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
        style: 'currency',
        currency: 'USD'
    }).format(number);
}

// Função para formatar data
function formatDate(timestamp) {
    return new Date(timestamp).toLocaleString('pt-BR');
}

// Função para analisar o mercado
async function analyzeMarket(cryptoId = 'bitcoin', days = 30) {
    try {
        showLoading('market-analysis');
        
        const response = await axios.get(`http://localhost:5000/analyze?crypto_id=${cryptoId}&days=${days}`);
        
        if (response.status === 200 && response.data) {
            updateMarketAnalysis(response.data);
        } else {
            showError('Erro ao obter dados do mercado');
        }
    } catch (error) {
        console.error('Erro:', error);
        let errorMessage = 'Erro ao analisar mercado';
        
        if (error.response) {
            if (error.response.status === 429) {
                errorMessage = 'Muitas requisições. Por favor, aguarde alguns segundos e tente novamente.';
            } else if (error.response.status === 503) {
                errorMessage = 'Serviço temporariamente indisponível. Tente novamente em alguns minutos.';
            } else if (error.response.status === 400) {
                errorMessage = 'Criptomoeda não suportada. Por favor, selecione outra opção.';
            } else if (error.response.data && error.response.data.error) {
                errorMessage = error.response.data.error;
            }
        } else if (error.request) {
            errorMessage = 'Não foi possível conectar ao servidor. Verifique sua conexão.';
        }
        
        showError(errorMessage);
    } finally {
        hideLoading('market-analysis');
    }
}

function showLoading(section) {
    const element = document.getElementById(section);
    if (element) {
        element.innerHTML = '<div class="loading">Carregando dados...</div>';
    }
}

function hideLoading(section) {
    const element = document.getElementById(section);
    if (element && element.querySelector('.loading')) {
        element.querySelector('.loading').remove();
    }
}

function showError(message) {
    const messagesDiv = document.getElementById('messages');
    if (messagesDiv) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'message error';
        errorDiv.textContent = message;
        messagesDiv.appendChild(errorDiv);
        
        // Remove a mensagem após 5 segundos
        setTimeout(() => {
            errorDiv.remove();
        }, 5000);
    }
}

// Função para atualizar o gráfico
function updateChart(prices) {
    const ctx = document.getElementById('priceChart').getContext('2d');
    
    if (priceChart) {
        priceChart.destroy();
    }

    const labels = prices.map(price => formatDate(price[0]));
    const values = prices.map(price => price[1]);

    priceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Preço USD',
                data: values,
                borderColor: '#2563eb',
                backgroundColor: 'rgba(37, 99, 235, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Data'
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Preço (USD)'
                    },
                    ticks: {
                        callback: function(value) {
                            return formatNumber(value);
                        }
                    }
                }
            }
        }
    });
}

// Função para adicionar alerta
async function addAlert() {
    const formData = {
        crypto_id: document.getElementById('crypto_id').value,
        indicator: 'price',
        threshold: parseFloat(document.getElementById('threshold').value),
        condition: document.getElementById('condition').value
    };

    try {
        const response = await axios.post('/alerts', formData);
        showMessage('Alerta criado com sucesso!');
        loadAlerts(); // Recarregar lista de alertas
        document.getElementById('alert-form').reset();
    } catch (error) {
        console.error('Erro ao criar alerta:', error);
        showMessage('Erro ao criar alerta. Tente novamente.', 'error');
    }
}

function formatIndicator(alert) {
    switch (alert.indicator) {
        case 'price':
            return `Preço ${alert.condition === 'above' ? 'acima de' : 'abaixo de'} ${formatNumber(alert.threshold)}`;
        case 'rsi':
            return `RSI ${alert.condition === 'above' ? 'acima de' : 'abaixo de'} ${alert.threshold}`;
        case 'bollinger':
            if (alert.condition === 'above')
                return `Preço acima da Banda Superior`;
            else
                return `Preço abaixo da Banda Inferior`;
        case 'volatility':
            return `Volatilidade acima de ${alert.threshold}%`;
        case 'support':
            return `Preço próximo ao Suporte`;
        case 'resistance':
            return `Preço próximo à Resistência`;
        default:
            return `${alert.indicator} ${alert.condition} ${alert.threshold}`;
    }
}

// Função para carregar alertas
async function loadAlerts() {
    try {
        const response = await axios.get('/alerts');
        const alerts = response.data;
        const tbody = document.querySelector('#alerts-table tbody');
        tbody.innerHTML = '';

        alerts.forEach(alert => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${alert.id}</td>
                <td>${alert.crypto_id.toUpperCase()}</td>
                <td>${alert.description || formatIndicator(alert)}</td>
                <td>${formatDate(alert.created_at)}</td>
                <td>${alert.triggered_value ? formatNumber(alert.triggered_value) : '-'}</td>
                <td>
                    <button onclick="deleteAlert(${alert.id})" class="delete-btn">
                        Excluir
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (error) {
        console.error('Erro ao carregar alertas:', error);
        showMessage('Erro ao carregar alertas. Tente novamente.', 'error');
    }
}

// Função para excluir alerta
async function deleteAlert(alertId) {
    if (!confirm('Tem certeza que deseja excluir este alerta?')) {
        return;
    }

    try {
        await axios.delete(`/alerts/${alertId}`);
        showMessage('Alerta excluído com sucesso!');
        loadAlerts();
    } catch (error) {
        console.error('Erro ao excluir alerta:', error);
        showMessage('Erro ao excluir alerta. Tente novamente.', 'error');
    }
}

// Atualização automática
function startAutoUpdate() {
    setInterval(() => {
        const cryptoId = document.getElementById('analysis-crypto').value;
        analyzeMarket(cryptoId);
    }, 60000); // Atualizar a cada minuto
}

// Função para executar backtest
async function runBacktest() {
    const data = {
        crypto_id: document.getElementById('backtest-crypto').value,
        days: parseInt(document.getElementById('backtest-days').value),
        strategy_params: {
            rsi_oversold: parseInt(document.getElementById('rsi-oversold').value),
            rsi_overbought: parseInt(document.getElementById('rsi-overbought').value),
            stop_loss: parseFloat(document.getElementById('stop-loss').value) / 100
        }
    };

    try {
        const response = await axios.post('/backtest', data);
        const results = response.data.results;
        
        const resultsHtml = `
            <div class="backtest-summary">
                <h3>Resultados do Backtest</h3>
                <div class="backtest-stats">
                    <div class="stat ${results.profit_loss >= 0 ? 'positive' : 'negative'}">
                        <h4>Resultado</h4>
                        <p>${results.profit_loss.toFixed(2)}%</p>
                    </div>
                    <div class="stat">
                        <h4>Total de Trades</h4>
                        <p>${results.total_trades}</p>
                    </div>
                    <div class="stat">
                        <h4>Taxa de Acerto</h4>
                        <p>${results.win_rate.toFixed(2)}%</p>
                    </div>
                </div>
                
                <h4>Últimas Operações</h4>
                <div class="trades-list">
                    ${results.trades.map(trade => `
                        <div class="trade-item ${trade.type === 'exit' ? (trade.profit_loss >= 0 ? 'positive' : 'negative') : ''}">
                            <span>${trade.type === 'entry' ? 'Entrada' : 'Saída'}</span>
                            <span>${trade.position === 'long' ? 'Compra' : 'Venda'}</span>
                            ${trade.type === 'entry' 
                                ? `<span>Preço: ${formatNumber(trade.price)}</span>`
                                : `<span>P/L: ${trade.profit_loss.toFixed(2)}%</span>`
                            }
                            <span>RSI: ${trade.rsi.toFixed(2)}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
        
        document.getElementById('backtest-results').innerHTML = resultsHtml;
        showMessage('Backtest concluído com sucesso!');
    } catch (error) {
        console.error('Erro ao executar backtest:', error);
        showMessage('Erro ao executar backtest. Tente novamente.', 'error');
    }
}

// Função para atualizar a análise de mercado
function updateMarketAnalysis(data) {
    // Atualizar preço atual
    document.getElementById('current-price').textContent = formatNumber(data.current_price);

    // Atualizar indicadores técnicos
    const technicalIndicators = document.getElementById('technical-indicators');
    technicalIndicators.innerHTML = '';

    if (data.technical_indicators) {
        // RSI
        if (data.technical_indicators.rsi !== undefined) {
            const rsiDiv = document.createElement('div');
            rsiDiv.className = 'indicator';
            rsiDiv.innerHTML = `
                <h4>RSI</h4>
                <p class="${getRSIClass(data.technical_indicators.rsi)}">
                    ${data.technical_indicators.rsi.toFixed(2)}
                </p>
            `;
            technicalIndicators.appendChild(rsiDiv);
        }

        // MACD
        if (data.technical_indicators.macd) {
            const macdDiv = document.createElement('div');
            macdDiv.className = 'indicator';
            macdDiv.innerHTML = `
                <h4>MACD</h4>
                <p>Linha: ${data.technical_indicators.macd.line.toFixed(2)}</p>
                <p>Sinal: ${data.technical_indicators.macd.signal.toFixed(2)}</p>
            `;
            technicalIndicators.appendChild(macdDiv);
        }

        // Médias Móveis
        if (data.technical_indicators.sma_20) {
            const smaDiv = document.createElement('div');
            smaDiv.className = 'indicator';
            smaDiv.innerHTML = `
                <h4>SMA 20</h4>
                <p>${formatNumber(data.technical_indicators.sma_20)}</p>
            `;
            technicalIndicators.appendChild(smaDiv);
        }

        if (data.technical_indicators.ema_50) {
            const emaDiv = document.createElement('div');
            emaDiv.className = 'indicator';
            emaDiv.innerHTML = `
                <h4>EMA 50</h4>
                <p>${formatNumber(data.technical_indicators.ema_50)}</p>
            `;
            technicalIndicators.appendChild(emaDiv);
        }

        // Bandas de Bollinger
        if (data.technical_indicators.bollinger_bands) {
            const bollingerDiv = document.createElement('div');
            bollingerDiv.className = 'indicator';
            bollingerDiv.innerHTML = `
                <h4>Bollinger Bands</h4>
                <p>Superior: ${formatNumber(data.technical_indicators.bollinger_bands.upper)}</p>
                <p>Média: ${formatNumber(data.technical_indicators.bollinger_bands.middle)}</p>
                <p>Inferior: ${formatNumber(data.technical_indicators.bollinger_bands.lower)}</p>
            `;
            technicalIndicators.appendChild(bollingerDiv);
        }

        // Estocástico
        if (data.technical_indicators.stochastic !== undefined) {
            const stochDiv = document.createElement('div');
            stochDiv.className = 'indicator';
            stochDiv.innerHTML = `
                <h4>Estocástico</h4>
                <p>${data.technical_indicators.stochastic.toFixed(2)}</p>
            `;
            technicalIndicators.appendChild(stochDiv);
        }

        // Suporte e Resistência
        if (data.technical_indicators.support_resistance) {
            const srDiv = document.createElement('div');
            srDiv.className = 'indicator';
            srDiv.innerHTML = `
                <h4>Suporte/Resistência</h4>
                <p>Suporte: ${formatNumber(data.technical_indicators.support_resistance.support)}</p>
                <p>Resistência: ${formatNumber(data.technical_indicators.support_resistance.resistance)}</p>
            `;
            technicalIndicators.appendChild(srDiv);
        }

        // Volatilidade
        if (data.technical_indicators.volatility !== undefined) {
            const volDiv = document.createElement('div');
            volDiv.className = 'indicator';
            volDiv.innerHTML = `
                <h4>Volatilidade</h4>
                <p>${data.technical_indicators.volatility.toFixed(2)}%</p>
            `;
            technicalIndicators.appendChild(volDiv);
        }
    }

    // Atualizar análise de mercado
    const marketAnalysis = document.getElementById('market-analysis');
    marketAnalysis.innerHTML = '';

    if (data.market_analysis) {
        // Tendência
        const trendDiv = document.createElement('div');
        trendDiv.className = 'analysis-item';
        trendDiv.innerHTML = `
            <h4>Tendência</h4>
            <p class="${getTrendClass(data.market_analysis.trend)}">
                ${data.market_analysis.trend}
            </p>
        `;
        marketAnalysis.appendChild(trendDiv);

        // Volume Médio
        if (data.market_analysis.avg_volume_7d) {
            const volumeDiv = document.createElement('div');
            volumeDiv.className = 'analysis-item';
            volumeDiv.innerHTML = `
                <h4>Volume Médio (7d)</h4>
                <p>${formatNumber(data.market_analysis.avg_volume_7d)}</p>
            `;
            marketAnalysis.appendChild(volumeDiv);
        }
    }

    // Atualizar níveis de Fibonacci
    const fibonacciLevels = document.getElementById('fibonacci-levels');
    fibonacciLevels.innerHTML = '';

    if (data.fibonacci_levels) {
        Object.entries(data.fibonacci_levels).forEach(([level, value]) => {
            const fibDiv = document.createElement('div');
            fibDiv.className = 'fibonacci-item';
            fibDiv.innerHTML = `
                <h4>${level}</h4>
                <p>${formatNumber(value)}</p>
            `;
            fibonacciLevels.appendChild(fibDiv);
        });
    }

    // Atualizar gráfico
    if (data.prices) {
        updateChart(data.prices);
    }
}

// Função auxiliar para determinar a classe do RSI
function getRSIClass(rsi) {
    if (rsi > 70) return 'overbought';
    if (rsi < 30) return 'oversold';
    return 'neutral';
}

// Função auxiliar para determinar a classe da tendência
function getTrendClass(trend) {
    if (trend.includes('Alta')) return 'uptrend';
    if (trend.includes('Baixa')) return 'downtrend';
    return 'neutral';
}

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    loadAlerts();
    analyzeMarket();
    startAutoUpdate();
});
