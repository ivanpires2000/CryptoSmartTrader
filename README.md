# CryptoSmartTrader

Sistema de análise e monitoramento de criptomoedas com recursos avançados de trading.

## Funcionalidades

### 1. Análise Técnica em Tempo Real
- Indicadores técnicos (RSI, Médias Móveis, Bollinger Bands)
- Análise de tendências
- Identificação de suporte e resistência
- Análise de volatilidade

### 2. Sistema de Alertas
- Alertas personalizados por preço
- Alertas baseados em indicadores técnicos
- Notificações em tempo real
- Histórico de alertas disparados

### 3. Backtesting de Estratégias
- Teste de estratégias em dados históricos
- Parâmetros personalizáveis:
  - RSI (Sobrecomprado/Sobrevendido)
  - Stop Loss
  - Período de análise (1 a 365 dias)
- Métricas de performance:
  - Lucro/Prejuízo total
  - Taxa de acerto
  - Número total de operações
  - Histórico detalhado das últimas 10 operações

### 4. Criptomoedas Suportadas
- Bitcoin (BTC)
- Ethereum (ETH)
- Cardano (ADA)
- Solana (SOL)
- Polkadot (DOT)
- Binance Coin (BNB)
- Ripple (XRP)
- Dogecoin (DOGE)
- Avalanche (AVAX)
- Chainlink (LINK)
- Polygon (MATIC)
- Uniswap (UNI)
- Stellar (XLM)
- Cosmos (ATOM)
- Litecoin (LTC)

## Instalação

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/CryptoSmartTrader.git
cd CryptoSmartTrader
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

## Uso

1. Inicie o servidor backend:
```bash
python app.py
```

2. Em outro terminal, inicie o servidor frontend:
```bash
python serve.py
```

3. Acesse a aplicação em seu navegador:
```
http://localhost:8000
```

## Configuração de Alertas

1. Selecione a criptomoeda desejada
2. Defina o tipo de alerta (Preço ou Indicador)
3. Configure os parâmetros do alerta
4. Clique em "Criar Alerta"

## Executando Backtests

1. Na seção de Backtesting:
   - Selecione a criptomoeda
   - Escolha o período de análise (1-365 dias)
   - Configure os parâmetros da estratégia:
     - RSI Sobrecomprado (50-100)
     - RSI Sobrevendido (0-50)
     - Stop Loss (0.1-10%)
2. Clique em "Executar Backtest"
3. Analise os resultados:
   - Performance geral
   - Histórico de operações
   - Métricas de risco/retorno

## Contribuição

Sinta-se à vontade para contribuir com o projeto:

1. Faça um Fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes. 