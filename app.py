from flask import Flask, request, jsonify
import requests
import sqlite3
from threading import Thread
import time
from flask_mail import Mail, Message
from flask_cors import CORS
import os
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv
import numpy as np

# Carregar variáveis de ambiente
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crypto_trader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Inicializar o aplicativo Flask
app = Flask(__name__)

# Configurar CORS
CORS(app, 
     resources={r"/*": {
         "origins": ["http://localhost:8000"],
         "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         "allow_headers": ["Content-Type", "Authorization"],
         "supports_credentials": True
     }})

# Adicionar headers CORS em todas as respostas
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'http://localhost:8000')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

# Configurações de e-mail para notificações
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

mail = Mail(app)

# Base URL para a API CoinGecko
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

# Cache para dados da API
cache = {}
CACHE_DURATION = 60  # segundos

# Lista de criptomoedas suportadas
SUPPORTED_CRYPTOCURRENCIES = {
    'bitcoin': 'BTC',
    'ethereum': 'ETH',
    'cardano': 'ADA',
    'solana': 'SOL',
    'polkadot': 'DOT',
    'binancecoin': 'BNB',
    'ripple': 'XRP',
    'dogecoin': 'DOGE',
    'avalanche-2': 'AVAX',
    'chainlink': 'LINK',
    'polygon': 'MATIC',
    'uniswap': 'UNI',
    'stellar': 'XLM',
    'cosmos': 'ATOM',
    'litecoin': 'LTC'
}

# Configurações de rate limiting
RATE_LIMIT_DELAY = 1.5  # segundos entre requisições
last_request_time = 0

def get_db_connection():
    conn = sqlite3.connect("crypto_smart_trader.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Criando tabela de alertas com coluna de status
    cursor.execute('''CREATE TABLE IF NOT EXISTS alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        crypto_id TEXT NOT NULL,
                        indicator TEXT NOT NULL,
                        threshold REAL NOT NULL,
                        condition TEXT NOT NULL,
                        description TEXT,
                        triggered_value REAL,
                        status TEXT DEFAULT 'active',
                        notification_sent BOOLEAN DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )''')

    # Criando tabela de histórico de preços
    cursor.execute('''CREATE TABLE IF NOT EXISTS price_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        crypto_id TEXT NOT NULL,
                        price REAL NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )''')

    conn.commit()
    conn.close()

def validate_crypto_id(crypto_id):
    return crypto_id in SUPPORTED_CRYPTOCURRENCIES

def fetch_market_data(crypto_id, days):
    global last_request_time
    if not validate_crypto_id(crypto_id):
        raise ValueError(f"Criptomoeda não suportada: {crypto_id}")

    cache_key = f"{crypto_id}_{days}"
    current_time = time.time()

    # Verificar cache
    if cache_key in cache and current_time - cache[cache_key]["timestamp"] < CACHE_DURATION:
        return cache[cache_key]["data"]

    # Rate limiting mais conservador
    time_since_last_request = current_time - last_request_time
    if time_since_last_request < RATE_LIMIT_DELAY:
        sleep_time = RATE_LIMIT_DELAY - time_since_last_request + 0.5  # Adiciona 0.5s de margem
        time.sleep(sleep_time)

    # Tentar fazer a requisição com retry e backoff exponencial
    max_retries = 5  # Aumentado de 3 para 5
    retry_delay = 2
    last_error = None
    
    for attempt in range(max_retries):
        try:
            url = f"{COINGECKO_API_URL}/coins/{crypto_id}/market_chart"
            params = {
                "vs_currency": "usd",
                "days": days,
                "interval": "daily" if days > 1 else "hourly"  # Otimiza os dados
            }
            
            last_request_time = time.time()
            response = requests.get(url, params=params, timeout=15)  # Aumentado timeout
            
            if response.status_code == 429:  # Too Many Requests
                retry_after = int(response.headers.get('Retry-After', retry_delay))
                logger.warning(f"Rate limit atingido, aguardando {retry_after} segundos...")
                time.sleep(retry_after)
                continue
                
            response.raise_for_status()
            data = response.json()
            
            # Validar dados recebidos
            if not data or 'prices' not in data or not data['prices']:
                raise ValueError("Dados inválidos recebidos da API")
                
            cache[cache_key] = {"data": data, "timestamp": current_time}
            
            # Salvar preço atual no histórico
            try:
                save_current_price(crypto_id, data['prices'][-1][1])
            except Exception as e:
                logger.error(f"Erro ao salvar preço no histórico: {e}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < max_retries - 1:
                sleep_time = retry_delay * (2 ** attempt)  # Backoff exponencial
                logger.warning(f"Tentativa {attempt + 1} falhou, aguardando {sleep_time}s...")
                time.sleep(sleep_time)
                continue
            
            # Se tiver dados em cache, mesmo que antigos, use-os em caso de erro
            if cache_key in cache and (time.time() - cache[cache_key]["timestamp"] < CACHE_DURATION):
                logger.warning("Usando dados em cache devido a erro na API")
                return cache[cache_key]["data"]
            else:
                logger.error("Dados em cache não disponíveis ou desatualizados.")
                raise ValueError("Não foi possível obter dados do mercado. Tente novamente mais tarde.")

def save_current_price(crypto_id, price):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO price_history (crypto_id, price)
                     VALUES (?, ?)''', (crypto_id, price))
    try:
        conn.commit()
    except Exception as e:
        logger.error(f"Erro ao realizar commit: {e}")
    finally:
        conn.close()

def send_alert_email(alert, current_value):
    try:
        subject = f"Alerta de Cripto: {alert['crypto_id'].upper()}"
        body = f"""
        Seu alerta foi acionado!
        
        Criptomoeda: {alert['crypto_id'].upper()}
        Indicador: {alert['indicator']}
        Condição: {alert['condition']}
        Limite: {alert['threshold']}
        Valor Atual: {current_value}
        
        Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        """
        
        msg = Message(subject,
                     sender=app.config['MAIL_USERNAME'],
                     recipients=[os.getenv('ALERT_EMAIL')])
        msg.body = body
        mail.send(msg)
        logger.info(f"E-mail de alerta enviado para {alert['crypto_id']}")
    except Exception as e:
        logger.error(f"Erro ao enviar e-mail de alerta: {e}")

def calculate_rsi(prices, period=14):
    deltas = np.diff(prices)
    gain = np.where(deltas > 0, deltas, 0)
    loss = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gain[:period])
    avg_loss = np.mean(loss[:period])
    
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gain[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i]) / period
        
    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_sma(prices, period):
    return np.convolve(prices, np.ones(period)/period, mode='valid')

def calculate_ema(prices, period):
    weights = np.exp(np.linspace(-1., 0., period))
    weights /= weights.sum()
    return np.convolve(prices, weights, mode='valid')

def calculate_macd(prices):
    ema_12 = calculate_ema(prices, 12)
    ema_26 = calculate_ema(prices, 26)
    macd_line = ema_12[-len(ema_26):] - ema_26
    signal_line = calculate_ema(macd_line, 9)
    return macd_line[-1], signal_line[-1]

def analyze_trend(prices, period=14):
    if len(prices) < period:
        return "Indefinida"
    
    sma = calculate_sma(prices, period)
    current_price = prices[-1]
    sma_current = sma[-1]
    
    if current_price > sma_current * 1.05:
        return "Forte Alta"
    elif current_price > sma_current:
        return "Alta"
    elif current_price < sma_current * 0.95:
        return "Forte Baixa"
    elif current_price < sma_current:
        return "Baixa"
    else:
        return "Lateral"

def calculate_price_changes(prices, timestamps):
    current_price = prices[-1]
    current_time = timestamps[-1]
    
    changes = {}
    periods = {
        '1h': timedelta(hours=1),
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30)
    }
    
    for period_name, period_delta in periods.items():
        target_time = current_time - period_delta
        for i in range(len(timestamps)-1, -1, -1):
            if timestamps[i] <= target_time:
                price_change = ((current_price - prices[i]) / prices[i]) * 100
                changes[period_name] = round(price_change, 2)
                break
            if i == 0:
                changes[period_name] = None
    
    return changes

def calculate_bollinger_bands(prices, period=20, num_std=2):
    sma = calculate_sma(prices[-period:], period)
    std = np.std(prices[-period:])
    upper_band = sma + (std * num_std)
    lower_band = sma - (std * num_std)
    return upper_band, sma, lower_band

def calculate_stochastic(prices, period=14):
    low_min = np.min(prices[-period:])
    high_max = np.max(prices[-period:])
    current_close = prices[-1]
    
    k = 100 * (current_close - low_min) / (high_max - low_min)
    return k

def calculate_fibonacci_levels(prices):
    max_price = np.max(prices)
    min_price = np.min(prices)
    diff = max_price - min_price
    
    levels = {
        'Retração 23.6%': max_price - (diff * 0.236),
        'Retração 38.2%': max_price - (diff * 0.382),
        'Retração 50.0%': max_price - (diff * 0.5),
        'Retração 61.8%': max_price - (diff * 0.618),
        'Retração 78.6%': max_price - (diff * 0.786)
    }
    return levels

def identify_support_resistance(prices, window=20):
    supports = []
    resistances = []
    
    for i in range(window, len(prices)-window):
        if all(prices[i] <= prices[j] for j in range(i-window, i+window)):
            supports.append(prices[i])
        if all(prices[i] >= prices[j] for j in range(i-window, i+window)):
            resistances.append(prices[i])
    
    if supports:
        support = np.mean(supports[-3:]) if len(supports) >= 3 else supports[-1]
    else:
        support = min(prices)
        
    if resistances:
        resistance = np.mean(resistances[-3:]) if len(resistances) >= 3 else resistances[-1]
    else:
        resistance = max(prices)
        
    return support, resistance

def calculate_volatility(prices, window=14):
    returns = np.diff(np.log(prices))
    volatility = np.std(returns[-window:]) * np.sqrt(252) * 100  # Anualizada em %
    return volatility

def calculate_market_strength(prices, volumes):
    """Calcula um índice de força do mercado de 0 a 100"""
    try:
        # Calcular indicadores
        rsi = calculate_rsi(prices)
        macd_line, signal_line = calculate_macd(prices)
        volatility = calculate_volatility(prices)
        stoch = calculate_stochastic(prices)
        
        # Volume médio dos últimos 7 dias vs 30 dias
        vol_ratio = np.mean(volumes[-7:]) / np.mean(volumes[-30:])
        
        # Tendência de preço
        price_trend = (prices[-1] - prices[-20]) / prices[-20] * 100
        
        # Pontuação para cada componente (0-20 pontos cada)
        rsi_score = 20 * (1 - abs(50 - rsi) / 50)  # Melhor próximo a 50
        macd_score = 20 if macd_line > signal_line else 0  # Tendência de alta
        vol_score = min(20, 20 * vol_ratio)  # Volume crescente
        trend_score = min(20, max(0, price_trend))  # Tendência de preço positiva
        stoch_score = 20 if 20 < stoch < 80 else 0  # Fora de extremos
        
        # Pontuação total (0-100)
        total_score = rsi_score + macd_score + vol_score + trend_score + stoch_score
        
        return {
            'score': round(total_score, 2),
            'components': {
                'rsi_score': round(rsi_score, 2),
                'macd_score': round(macd_score, 2),
                'volume_score': round(vol_score, 2),
                'trend_score': round(trend_score, 2),
                'stochastic_score': round(stoch_score, 2)
            }
        }
    except Exception as e:
        logger.error(f"Erro ao calcular força do mercado: {e}")
        return None

def identify_price_patterns(prices, timestamps):
    """Identifica padrões de preço comuns"""
    patterns = []
    
    try:
        # Últimos 20 períodos
        recent_prices = prices[-20:]
        
        # Padrão de Suporte/Resistência
        support, resistance = identify_support_resistance(recent_prices)
        current_price = prices[-1]
        
        if abs(current_price - support) / support < 0.02:
            patterns.append({
                'name': 'Teste de Suporte',
                'description': 'Preço testando nível de suporte importante',
                'confidence': 'Alta' if abs(current_price - support) / support < 0.01 else 'Média'
            })
            
        if abs(current_price - resistance) / resistance < 0.02:
            patterns.append({
                'name': 'Teste de Resistência',
                'description': 'Preço testando nível de resistência importante',
                'confidence': 'Alta' if abs(current_price - resistance) / resistance < 0.01 else 'Média'
            })
            
        # Padrão de Reversão
        rsi = calculate_rsi(prices)
        if rsi > 70 and current_price < prices[-2]:
            patterns.append({
                'name': 'Possível Reversão de Alta',
                'description': 'RSI em sobrecompra com sinal de reversão',
                'confidence': 'Média'
            })
        elif rsi < 30 and current_price > prices[-2]:
            patterns.append({
                'name': 'Possível Reversão de Baixa',
                'description': 'RSI em sobrevenda com sinal de reversão',
                'confidence': 'Média'
            })
            
        # Cruzamento de Médias
        if len(prices) >= 50:
            sma_20 = calculate_sma(prices, 20)[-1]
            ema_50 = calculate_ema(prices, 50)[-1]
            sma_20_prev = calculate_sma(prices[:-1], 20)[-1]
            ema_50_prev = calculate_ema(prices[:-1], 50)[-1]
            
            if sma_20_prev < ema_50_prev and sma_20 > ema_50:
                patterns.append({
                    'name': 'Cruzamento de Médias Móveis (Golden Cross)',
                    'description': 'SMA20 cruzou acima da EMA50',
                    'confidence': 'Alta'
                })
            elif sma_20_prev > ema_50_prev and sma_20 < ema_50:
                patterns.append({
                    'name': 'Cruzamento de Médias Móveis (Death Cross)',
                    'description': 'SMA20 cruzou abaixo da EMA50',
                    'confidence': 'Alta'
                })
                
        return patterns
    except Exception as e:
        logger.error(f"Erro ao identificar padrões: {e}")
        return []

def generate_trading_recommendations(prices, volumes, patterns, market_strength):
    """Gera recomendações de trading baseadas na análise técnica"""
    try:
        current_price = prices[-1]
        rsi = calculate_rsi(prices)
        macd_line, signal_line = calculate_macd(prices)
        stoch = calculate_stochastic(prices)
        
        recommendations = []
        
        # Recomendações baseadas na força do mercado
        if market_strength and market_strength['score'] > 70:
            recommendations.append({
                'type': 'COMPRA',
                'reason': 'Força do mercado muito positiva',
                'confidence': 'Alta'
            })
        elif market_strength and market_strength['score'] < 30:
            recommendations.append({
                'type': 'VENDA',
                'reason': 'Força do mercado muito negativa',
                'confidence': 'Alta'
            })
            
        # Recomendações baseadas em padrões
        for pattern in patterns:
            if pattern['name'] == 'Teste de Suporte' and pattern['confidence'] == 'Alta':
                recommendations.append({
                    'type': 'COMPRA',
                    'reason': f"Preço testando suporte forte - {pattern['description']}",
                    'confidence': 'Média'
                })
            elif pattern['name'] == 'Teste de Resistência' and pattern['confidence'] == 'Alta':
                recommendations.append({
                    'type': 'VENDA',
                    'reason': f"Preço testando resistência forte - {pattern['description']}",
                    'confidence': 'Média'
                })
                
        # Recomendações baseadas em indicadores
        if rsi < 30 and stoch < 20:
            recommendations.append({
                'type': 'COMPRA',
                'reason': 'RSI e Estocástico indicando sobrevenda',
                'confidence': 'Alta' if market_strength and market_strength['score'] > 50 else 'Média'
            })
        elif rsi > 70 and stoch > 80:
            recommendations.append({
                'type': 'VENDA',
                'reason': 'RSI e Estocástico indicando sobrecompra',
                'confidence': 'Alta' if market_strength and market_strength['score'] < 50 else 'Média'
            })
            
        return recommendations
    except Exception as e:
        logger.error(f"Erro ao gerar recomendações: {e}")
        return []

@app.route("/analyze", methods=["GET"])
def analyze_crypto():
    try:
        crypto_id = request.args.get("crypto_id", "bitcoin")
        days = request.args.get("days", 30, type=int)

        if not validate_crypto_id(crypto_id):
            return jsonify({"error": "Criptomoeda não suportada"}), 400

        try:
            market_data = fetch_market_data(crypto_id, days)
        except ValueError as e:
            return jsonify({"error": str(e)}), 503  # Service Unavailable
        except Exception as e:
            logger.error(f"Erro ao buscar dados do mercado: {e}")
            return jsonify({"error": "Erro ao obter dados do mercado"}), 503

        if not market_data or 'prices' not in market_data or not market_data['prices']:
            return jsonify({"error": "Dados de mercado inválidos"}), 503

        try:
            prices = np.array([price[1] for price in market_data["prices"]])
            timestamps = [datetime.fromtimestamp(price[0]/1000) for price in market_data["prices"]]
            volumes = [vol[1] for vol in market_data.get("total_volumes", [])]
            
            current_price = prices[-1]
            
            # Cálculos protegidos
            analysis_result = {
                "crypto_id": crypto_id,
                "symbol": SUPPORTED_CRYPTOCURRENCIES[crypto_id],
                "current_price": float(current_price),
                "prices": market_data["prices"],
                "technical_indicators": {},
                "market_analysis": {
                    "trend": "Indefinida",
                    "price_changes": {},
                    "avg_volume_7d": 0
                }
            }
            
            # Adiciona indicadores apenas se houver dados suficientes
            if len(prices) >= 14:
                rsi = calculate_rsi(prices)
                analysis_result["technical_indicators"]["rsi"] = round(float(rsi), 2)
            
            if len(prices) >= 26:
                macd_line, signal_line = calculate_macd(prices)
                analysis_result["technical_indicators"]["macd"] = {
                    "line": round(float(macd_line), 8),
                    "signal": round(float(signal_line), 8)
                }
            
            if len(prices) >= 20:
                sma_20 = calculate_sma(prices, 20)[-1]
                analysis_result["technical_indicators"]["sma_20"] = round(float(sma_20), 2)
            
            if len(prices) >= 50:
                ema_50 = calculate_ema(prices, 50)[-1]
                analysis_result["technical_indicators"]["ema_50"] = round(float(ema_50), 2)
                
                upper_band, middle_band, lower_band = calculate_bollinger_bands(prices)
                analysis_result["technical_indicators"]["bollinger_bands"] = {
                    "upper": round(float(upper_band[-1]), 2),
                    "middle": round(float(middle_band[-1]), 2),
                    "lower": round(float(lower_band[-1]), 2)
                }
            
            if len(prices) >= 14:
                stochastic_k = calculate_stochastic(prices)
                analysis_result["technical_indicators"]["stochastic"] = round(float(stochastic_k), 2)
                
                support, resistance = identify_support_resistance(prices)
                analysis_result["technical_indicators"]["support_resistance"] = {
                    "support": round(float(support), 2),
                    "resistance": round(float(resistance), 2)
                }
                
                volatility = calculate_volatility(prices)
                analysis_result["technical_indicators"]["volatility"] = round(float(volatility), 2)
                
                analysis_result["market_analysis"]["trend"] = analyze_trend(prices)
                
            if volumes:
                analysis_result["market_analysis"]["avg_volume_7d"] = round(float(np.mean(volumes[-7:])), 2)
            
            if len(prices) >= 30:
                fib_levels = calculate_fibonacci_levels(prices)
                analysis_result["fibonacci_levels"] = {k: round(float(v), 2) for k, v in fib_levels.items()}
            
            # Adicionar força do mercado à análise
            market_strength = calculate_market_strength(prices, volumes)
            if market_strength:
                analysis_result["market_strength"] = market_strength
            
            # Identificar padrões e gerar recomendações
            patterns = identify_price_patterns(prices, timestamps)
            recommendations = generate_trading_recommendations(prices, volumes, patterns, market_strength)
            
            analysis_result["patterns"] = patterns
            analysis_result["recommendations"] = recommendations
            
            return jsonify(analysis_result)
            
        except Exception as e:
            logger.error(f"Erro ao calcular indicadores: {e}")
            return jsonify({"error": "Erro ao calcular indicadores técnicos"}), 500
            
    except Exception as e:
        logger.error(f"Erro na análise de criptomoeda: {e}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@app.route("/alerts", methods=["GET", "POST"])
def manage_alerts():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "GET":
        cursor.execute("SELECT * FROM alerts WHERE status = 'active' ORDER BY created_at DESC")
        alerts = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(alerts)

    elif request.method == "POST":
        data = request.get_json()
        required_fields = ["crypto_id", "indicator", "threshold", "condition"]
        
        if not all(field in data for field in required_fields):
            conn.close()
            return jsonify({"error": "Campos obrigatórios faltando"}), 400

        if not validate_crypto_id(data["crypto_id"]):
            conn.close()
            return jsonify({"error": "Criptomoeda não suportada"}), 400

    cursor.execute('''INSERT INTO alerts (crypto_id, indicator, threshold, condition) 
                      VALUES (?, ?, ?, ?)''',
                      (data["crypto_id"], data["indicator"],
                       data["threshold"], data["condition"]))
    try:
        conn.commit()
    except Exception as e:
        logger.error(f"Erro ao realizar commit: {e}")
    finally:
        conn.close()
    alert_id = cursor.lastrowid,
    return jsonify({"id": alert_id, "message": "Alerta criado com sucesso"}), 201

@app.route("/alerts/<int:alert_id>", methods=["DELETE"])
def delete_alert(alert_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE alerts SET status = 'deleted' WHERE id = ?", (alert_id,))
    try:
        conn.commit()
    except Exception as e:
        logger.error(f"Erro ao realizar commit: {e}")
    finally:
        conn.close()
    return jsonify({"message": "Alerta excluído com sucesso"})

def create_default_alerts():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    default_alerts = [
        # Alertas de RSI
        {
            "crypto_id": "bitcoin",
            "indicator": "rsi",
            "threshold": 70,
            "condition": "above",
            "description": "RSI em sobrecompra (BTC)"
        },
        {
            "crypto_id": "bitcoin",
            "indicator": "rsi",
            "threshold": 30,
            "condition": "below",
            "description": "RSI em sobrevenda (BTC)"
        },
        # Alertas de Bandas de Bollinger
        {
            "crypto_id": "ethereum",
            "indicator": "bollinger",
            "threshold": 2,
            "condition": "above",
            "description": "Preço acima da Banda Superior (ETH)"
        },
        {
            "crypto_id": "ethereum",
            "indicator": "bollinger",
            "threshold": -2,
            "condition": "below",
            "description": "Preço abaixo da Banda Inferior (ETH)"
        },
        # Alertas de Volatilidade
        {
            "crypto_id": "bitcoin",
            "indicator": "volatility",
            "threshold": 50,
            "condition": "above",
            "description": "Volatilidade Alta (BTC)"
        },
        # Alertas de Suporte/Resistência
        {
            "crypto_id": "ethereum",
            "indicator": "support",
            "threshold": 0,
            "condition": "near",
            "description": "Próximo ao Suporte (ETH)"
        },
        {
            "crypto_id": "ethereum",
            "indicator": "resistance",
            "threshold": 0,
            "condition": "near",
            "description": "Próximo à Resistência (ETH)"
        }
    ]
    
    for alert in default_alerts:
        cursor.execute('''INSERT INTO alerts 
                         (crypto_id, indicator, threshold, condition, description, status)
                         VALUES (?, ?, ?, ?, ?, 'active')''',
                      (alert["crypto_id"], alert["indicator"], 
                       alert["threshold"], alert["condition"],
                       alert["description"]))
    
    try:
        conn.commit()
    except Exception as e:
        logger.error(f"Erro ao realizar commit: {e}")
    finally:
        conn.close()
    logger.info("Alertas padrão criados com sucesso")

def check_technical_alert(alert, data):
    if alert["indicator"] == "rsi":
        current_value = data["technical_indicators"]["rsi"]
    elif alert["indicator"] == "bollinger":
        price = data["current_price"]
        upper = data["technical_indicators"]["bollinger_bands"]["upper"]
        lower = data["technical_indicators"]["bollinger_bands"]["lower"]
        if alert["condition"] == "above":
            current_value = (price - upper) / upper * 100
        else:
            current_value = (price - lower) / lower * 100
    elif alert["indicator"] == "volatility":
        current_value = data["technical_indicators"]["volatility"]
    elif alert["indicator"] in ["support", "resistance"]:
        price = data["current_price"]
        support = data["technical_indicators"]["support_resistance"]["support"]
        resistance = data["technical_indicators"]["support_resistance"]["resistance"]
        if alert["indicator"] == "support":
            current_value = abs((price - support) / support * 100)
        else:
            current_value = abs((price - resistance) / resistance * 100)
        return current_value <= 1  # 1% de distância
        
    if alert["condition"] == "above":
        return current_value > alert["threshold"]
    elif alert["condition"] == "below":
        return current_value < alert["threshold"]
    elif alert["condition"] == "near":
        return current_value <= 1  # 1% de distância
    
    return False

def check_alerts():
    while True:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alerts WHERE status = 'active'")
            alerts = [dict(row) for row in cursor.fetchall()]

            for alert in alerts:
                crypto_id = alert["crypto_id"]
                try:
                    market_data = fetch_market_data(crypto_id, 1)
                    analysis_data = analyze_crypto_data(crypto_id, market_data)
                    
                    if alert["indicator"] == "price":
                        current_value = analysis_data["current_price"]
                        condition_met = (
                            (alert["condition"] == "above" and current_value > alert["threshold"]) or
                            (alert["condition"] == "below" and current_value < alert["threshold"])
                        )
                    else:
                        condition_met = check_technical_alert(alert, analysis_data)

                    if condition_met and not alert["notification_sent"]:
                        if alert["indicator"] == "price":
                            value_to_show = current_value
                        else:
                            value_to_show = alert["threshold"]
                            
                        send_alert_email(alert, value_to_show)
                        cursor.execute('''UPDATE alerts 
                                        SET triggered_value = ?, notification_sent = 1,
                                            updated_at = CURRENT_TIMESTAMP
                                        WHERE id = ?''',
                                     (value_to_show, alert["id"]))
                except Exception as e:
                    logger.error(f"Erro ao verificar alerta {alert['id']}: {e}")
                    continue

            conn.commit()
        except Exception as e:
            logger.error(f"Erro ao verificar alertas: {e}")
        finally:
            time.sleep(60)  # Verificar a cada minuto

@app.route("/")
def home():
    return jsonify({
        "name": "CryptoSmartTrader API",
        "version": "2.0",
        "supported_cryptocurrencies": SUPPORTED_CRYPTOCURRENCIES,
        "endpoints": {
            "GET /": "Informações da API",
            "GET /analyze": "Análise de criptomoeda",
            "GET /alerts": "Listar alertas",
            "POST /alerts": "Criar alerta",
            "DELETE /alerts/<id>": "Excluir alerta"
        }
    })

def recreate_database():
    try:
        # Remover banco de dados existente
        if os.path.exists("crypto_smart_trader.db"):
            os.remove("crypto_smart_trader.db")
    except PermissionError:
        logger.warning("Não foi possível remover o banco de dados existente. Continuando...")
    except Exception as e:
        logger.error(f"Erro ao remover banco de dados: {e}")
    
    # Criar novo banco de dados
    init_db()
    
    # Criar alertas padrão
    create_default_alerts()
    
    logger.info("Banco de dados recriado com sucesso")

def backtest_strategy(prices, strategy_params):
    results = {
        'trades': [],
        'profit_loss': 0,
        'win_rate': 0,
        'total_trades': 0
    }
    
    if len(prices) < 50:  # Precisamos de pelo menos 50 períodos para os indicadores
        return results
    
    position = None
    entry_price = 0
    total_trades = 0
    winning_trades = 0
    total_profit_loss = 0
    
    # Converter lista de preços para array numpy
    prices_array = np.array([price[1] for price in prices])
    timestamps = [price[0] for price in prices]
    
    for i in range(50, len(prices_array)-1):
        current_price = prices_array[i]
        next_price = prices_array[i+1]
        
        # Calcular indicadores
        rsi = calculate_rsi(prices_array[max(0, i-14):i+1])
        sma_20 = calculate_sma(prices_array[max(0, i-20):i+1], 20)[-1]
        ema_50 = calculate_ema(prices_array[max(0, i-50):i+1], 50)[-1]
        
        # Regras de entrada
        if position is None:  # Se não estiver em posição
            if (rsi < strategy_params.get('rsi_oversold', 30) and 
                current_price > sma_20 * 1.01):  # Confirmação de tendência
                position = 'long'
                entry_price = current_price
                results['trades'].append({
                    'type': 'entry',
                    'position': 'long',
                    'price': float(current_price),
                    'rsi': float(rsi),
                    'timestamp': timestamps[i]
                })
            elif (rsi > strategy_params.get('rsi_overbought', 70) and 
                  current_price < sma_20 * 0.99):  # Confirmação de tendência
                position = 'short'
                entry_price = current_price
                results['trades'].append({
                    'type': 'entry',
                    'position': 'short',
                    'price': float(current_price),
                    'rsi': float(rsi),
                    'timestamp': timestamps[i]
                })
        
        # Regras de saída
        elif position == 'long':
            stop_loss = entry_price * (1 - strategy_params.get('stop_loss', 0.02))
            take_profit = entry_price * (1 + strategy_params.get('stop_loss', 0.02) * 1.5)  # Take profit 1.5x o stop loss
            
            if (current_price <= stop_loss or 
                current_price >= take_profit or 
                rsi > strategy_params.get('rsi_overbought', 70)):
                pl = ((current_price - entry_price) / entry_price) * 100
                total_profit_loss += pl
                total_trades += 1
                if pl > 0:
                    winning_trades += 1
                results['trades'].append({
                    'type': 'exit',
                    'position': position,
                    'entry_price': float(entry_price),
                    'exit_price': float(current_price),
                    'profit_loss': float(pl),
                    'rsi': float(rsi),
                    'timestamp': timestamps[i]
                })
                position = None
        
        elif position == 'short':
            stop_loss = entry_price * (1 + strategy_params.get('stop_loss', 0.02))
            take_profit = entry_price * (1 - strategy_params.get('stop_loss', 0.02) * 1.5)  # Take profit 1.5x o stop loss
            
            if (current_price >= stop_loss or 
                current_price <= take_profit or 
                rsi < strategy_params.get('rsi_oversold', 30)):
                pl = ((entry_price - current_price) / entry_price) * 100
                total_profit_loss += pl
                total_trades += 1
                if pl > 0:
                    winning_trades += 1
                results['trades'].append({
                    'type': 'exit',
                    'position': position,
                    'entry_price': float(entry_price),
                    'exit_price': float(current_price),
                    'profit_loss': float(pl),
                    'rsi': float(rsi),
                    'timestamp': timestamps[i]
                })
                position = None
    
    # Fechar posição aberta no final do período
    if position is not None:
        current_price = prices_array[-1]
        if position == 'long':
            pl = ((current_price - entry_price) / entry_price) * 100
        else:
            pl = ((entry_price - current_price) / entry_price) * 100
        
        total_profit_loss += pl
        total_trades += 1
        if pl > 0:
            winning_trades += 1
        
        results['trades'].append({
            'type': 'exit',
            'position': position,
            'entry_price': float(entry_price),
            'exit_price': float(current_price),
            'profit_loss': float(pl),
            'rsi': float(rsi),
            'timestamp': timestamps[-1]
        })
    
    # Calcular estatísticas finais
    results['total_trades'] = total_trades
    results['win_rate'] = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    results['profit_loss'] = total_profit_loss
    
    # Limitar a 10 últimas operações
    results['trades'] = results['trades'][-10:]
    
    return results

@app.route("/backtest", methods=["POST"])
def run_backtest():
    try:
        data = request.get_json()
        crypto_id = data.get("crypto_id", "bitcoin")
        days = data.get("days", 30)
        strategy_params = data.get("strategy_params", {
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "stop_loss": 0.02
        })

        if not validate_crypto_id(crypto_id):
            return jsonify({"error": "Criptomoeda não suportada"}), 400

        market_data = fetch_market_data(crypto_id, days)
        if not market_data or 'prices' not in market_data:
            return jsonify({"error": "Erro ao obter dados do mercado"}), 500
            
        results = backtest_strategy(market_data["prices"], strategy_params)
        
        return jsonify({
            "crypto_id": crypto_id,
            "period": f"{days} dias",
            "strategy_params": strategy_params,
            "results": results
        })
    except Exception as e:
        logger.error(f"Erro no backtesting: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    recreate_database()  # Recriar o banco de dados
    monitor_thread = Thread(target=check_alerts, daemon=True)
    monitor_thread.start()
    app.run(debug=True, host='0.0.0.0')
