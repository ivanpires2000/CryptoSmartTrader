function updateMarketAnalysis(data) {
    // Atualizar preço atual
    document.getElementById('current-price').textContent = `$${data.current_price.toFixed(2)}`;
    
    // Atualizar indicadores técnicos
    updateTechnicalIndicators(data.technical_indicators);
    
    // Atualizar análise de mercado
    updateMarketTrend(data.market_analysis);
    
    // Atualizar força do mercado
    if (data.market_strength) {
        const strengthHtml = `
            <div class="market-strength">
                <h3>Força do Mercado: ${data.market_strength.score}%</h3>
                <div class="strength-components">
                    <div>RSI: ${data.market_strength.components.rsi_score}/20</div>
                    <div>MACD: ${data.market_strength.components.macd_score}/20</div>
                    <div>Volume: ${data.market_strength.components.volume_score}/20</div>
                    <div>Tendência: ${data.market_strength.components.trend_score}/20</div>
                    <div>Estocástico: ${data.market_strength.components.stochastic_score}/20</div>
                </div>
            </div>
        `;
        document.getElementById('market-strength').innerHTML = strengthHtml;
    }
    
    // Atualizar padrões identificados
    if (data.patterns && data.patterns.length > 0) {
        const patternsHtml = data.patterns.map(pattern => `
            <div class="pattern-card ${pattern.confidence.toLowerCase()}">
                <h4>${pattern.name}</h4>
                <p>${pattern.description}</p>
                <span class="confidence">Confiança: ${pattern.confidence}</span>
            </div>
        `).join('');
        document.getElementById('price-patterns').innerHTML = patternsHtml;
    } else {
        document.getElementById('price-patterns').innerHTML = '<p>Nenhum padrão identificado</p>';
    }
    
    // Atualizar recomendações
    if (data.recommendations && data.recommendations.length > 0) {
        const recommendationsHtml = data.recommendations.map(rec => `
            <div class="recommendation-card ${rec.type.toLowerCase()} ${rec.confidence.toLowerCase()}">
                <h4>${rec.type}</h4>
                <p>${rec.reason}</p>
                <span class="confidence">Confiança: ${rec.confidence}</span>
            </div>
        `).join('');
        document.getElementById('trading-recommendations').innerHTML = recommendationsHtml;
    } else {
        document.getElementById('trading-recommendations').innerHTML = '<p>Nenhuma recomendação disponível</p>';
    }
    
    // Atualizar níveis de Fibonacci
    if (data.fibonacci_levels) {
        const fibHtml = Object.entries(data.fibonacci_levels).map(([level, price]) => `
            <div class="fib-level">
                <span class="level-name">${level}:</span>
                <span class="level-price">$${price.toFixed(2)}</span>
            </div>
        `).join('');
        document.getElementById('fibonacci-levels').innerHTML = fibHtml;
    }
} 