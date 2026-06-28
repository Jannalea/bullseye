import json
import time
import feedparser
import yfinance as yf
from deep_translator import GoogleTranslator

def translate_de(text):
    try:
        result = GoogleTranslator(source='auto', target='de').translate(text)
        return result if result else text
    except Exception:
        return text

BULLISH_KW = [
    'beat','beats','exceeded','exceeds','record','surge','surges','surging','soars','soaring',
    'rises','rising','rally','rallies','jumps','gains','tops','wins','awarded',
    'growth','grows','upgrade','upgrades','upgraded','buy','outperform','strong',
    'profit','profits','launch','launches','partnership','deal','acquisition','acquires',
    'dividend','buyback','repurchase','expands','expansion','bullish','breakthrough',
    'better than expected','above expectations','revenue beat','earnings beat',
    'uebertrifft','waechst','rekord','kaufen','positiv','gewinn','steigt','auftrag',
    'partnerschaft','dividende','stark','wachstum',
]
BEARISH_KW = [
    'miss','misses','missed','cut','cuts','cutting','fall','falls','falling',
    'drop','drops','dropping','plunge','plunges','slump','slumps','slumping',
    'lawsuit','probe','investigation','recall','downgrade','downgrades','downgraded',
    'sell','underperform','weak','loss','losses','decline','declines','declining',
    'warning','warns','concern','concerns','risk','bearish','layoffs','layoff',
    'fired','bankruptcy','fraud','fine','fined','penalty','disappoints','disappointing',
    'below expectations','misses estimates','revenue miss','earnings miss',
    'charges','impairment','write-down','write-off',
    'verpasst','kuetzt','faellt','sinkt','klage','untersuchung','verkaufen',
    'schwach','verlust','entlassungen','warnung','risiko','negativ','strafe',
]

def classify_sentiment(title):
    t = title.lower()
    bull = sum(1 for w in BULLISH_KW if w in t)
    bear = sum(1 for w in BEARISH_KW if w in t)
    if bull > bear:
        return 'buy'
    if bear > bull:
        return 'sell'
    return 'neutral'

def fetch_news(ticker_obj, ticker):
    # Yahoo Finance RSS (no auth needed)
    rss_urls = [
        f'https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US',
        f'https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en',
    ]
    results = []
    seen = set()
    for url in rss_urls:
        if len(results) >= 3:
            break
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if len(results) >= 3:
                    break
                title = (entry.get('title') or '').strip()
                link  = (entry.get('link')  or '').strip()
                if not title or not link or title in seen:
                    continue
                seen.add(title)
                published = entry.get('published_parsed')
                ts = int(time.mktime(published)) if published else 0
                source = ''
                try:
                    source = entry.source.title
                except Exception:
                    source = entry.get('publisher', '')
                sentiment = classify_sentiment(title)
                title_de  = translate_de(title)
                results.append({
                    'title':     title_de,
                    'url':       link,
                    'publisher': source,
                    'time':      ts,
                    'sentiment': sentiment,
                })
        except Exception as e:
            print(f'  news RSS error for {ticker} ({url}): {e}')
    return results

TICKERS = [
    'AAPL','MSFT','NVDA','AMZN','META','SAP.DE','SIE.DE','GOOGL','ALV.DE','BAYN.DE',
    'TSLA','INTC','DTE.DE','ADS.DE','AIR.DE','MUV2.DE','JPM','NFLX','KO','V','MA',
    'BMW.DE','MBG.DE','BAS.DE','DIS','AMD','VOW3.DE','PFE',
    'CRWD','PANW','ZS','OKTA','S','FTNT','NET','SNOW','MDB','DDOG','PATH',
    'NOW','CRM','HUBS','SHOP','ZM','DOCU','TWLO','ORCL','CSCO',
    'AVGO','QCOM','MU','AMAT','ASML',
    'SPOT','UBER','ABNB','RBLX','SNAP','PINS','LYFT',
    'SQ','COIN','HOOD','PLTR',
    'GS','MS','BAC','WFC','C','BLK','BRK-B',
    'WMT','COST','HD','MCD','SBUX','NKE','LULU',
    'JNJ','UNH','LLY','ABBV','MRK','AMGN','GILD','MRNA',
    'XOM','CVX','BA','CAT','DE',
    'RIVN','LCID',
    'ASML.AS','MC.PA','OR.PA','TTE.PA','SAN.MC',
    'DHL.DE','ZAL.DE','RWE.DE','ENR.DE','CON.DE','BEI.DE','FRE.DE',
    'HNR1.DE','DB1.DE','EOAN.DE','NESN.SW','ROG.SW','NOVN.SW',
    'RHM.DE',
]

def _ema(values, n):
    if len(values) < n:
        return None
    k = 2.0 / (n + 1)
    e = sum(values[:n]) / n
    for v in values[n:]:
        e = v * k + e * (1 - k)
    return e

def _macd_score(closes):
    if len(closes) < 27:
        return 50
    e12 = _ema(closes, 12)
    e26 = _ema(closes, 26)
    if e12 is None or e26 is None:
        return 50
    macd = e12 - e26
    tail = closes[-35:] if len(closes) >= 35 else closes
    mv = []
    for i in range(len(tail)):
        m12 = _ema(tail[:i+1], 12)
        m26 = _ema(tail[:i+1], 26)
        if m12 and m26:
            mv.append(m12 - m26)
    sig = _ema(mv, 9) if len(mv) >= 9 else (mv[-1] if mv else 0)
    if macd > sig and macd > 0: return 80
    if macd > sig:               return 62
    if macd <= sig and macd < 0: return 20
    return 38

def compute_feature_scores(data, closes, info):
    f = {}
    rsi = data.get('rsi', 50)
    if   rsi <= 25: f['rsi'] = 88
    elif rsi <= 35: f['rsi'] = 72
    elif rsi <= 45: f['rsi'] = 60
    elif rsi <= 55: f['rsi'] = 50
    elif rsi <= 65: f['rsi'] = 40
    elif rsi <= 75: f['rsi'] = 28
    else:           f['rsi'] = 15
    p, ma50, ma200 = data.get('p', 0), data.get('ma50', 0), data.get('ma200', 0)
    if   p > ma50 and p > ma200:  f['trend'] = 80
    elif p > ma50 or  p > ma200:  f['trend'] = 57
    elif p < ma50 and p < ma200:  f['trend'] = 20
    else:                          f['trend'] = 45
    f['macd'] = _macd_score(closes)
    if len(closes) >= 21:
        mom = (closes[-1] - closes[-21]) / closes[-21] * 100
        f['momentum'] = min(95, max(5, int(round(50 + mom * 2.5))))
    else:
        f['momentum'] = 50
    if len(closes) >= 21:
        rets = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(-20, 0)]
        vol_ann = (sum(r*r for r in rets) / len(rets)) ** 0.5 * (252 ** 0.5) * 100
        f['volatility'] = min(90, max(10, int(round(80 - vol_ann * 1.2))))
    else:
        f['volatility'] = 50
    pe = data.get('pe')
    if pe is None:  f['pe'] = 50
    elif pe <= 0:   f['pe'] = 30
    elif pe < 10:   f['pe'] = 88
    elif pe < 15:   f['pe'] = 78
    elif pe < 20:   f['pe'] = 65
    elif pe < 25:   f['pe'] = 55
    elif pe < 35:   f['pe'] = 42
    elif pe < 50:   f['pe'] = 30
    else:           f['pe'] = 15
    a = data.get('analystScore')
    f['analyst'] = int(round(max(0, min(100, (5 - a) / 4 * 100)))) if a else 50
    news = data.get('news', [])
    if news:
        sm = {'buy': 100, 'neutral': 50, 'sell': 0}
        f['newsSentiment'] = int(round(sum(sm.get(n['sentiment'], 50) for n in news) / len(news)))
    else:
        f['newsSentiment'] = 50
    rg = info.get('revenueGrowth')
    if   rg is None:  f['revenueGrowth'] = 50
    elif rg > 0.40:   f['revenueGrowth'] = 95
    elif rg > 0.20:   f['revenueGrowth'] = 80
    elif rg > 0.10:   f['revenueGrowth'] = 68
    elif rg > 0.03:   f['revenueGrowth'] = 55
    elif rg >= 0:     f['revenueGrowth'] = 42
    else:             f['revenueGrowth'] = 20
    eg = info.get('earningsGrowth')
    if   eg is None:  f['epsGrowth'] = 50
    elif eg > 0.30:   f['epsGrowth'] = 92
    elif eg > 0.15:   f['epsGrowth'] = 75
    elif eg > 0.05:   f['epsGrowth'] = 60
    elif eg >= 0:     f['epsGrowth'] = 45
    else:             f['epsGrowth'] = 18
    fcf = info.get('freeCashflow')
    rev = info.get('totalRevenue')
    if fcf and rev and rev > 0:
        m = fcf / rev
        if   m > 0.25: f['fcf'] = 92
        elif m > 0.15: f['fcf'] = 78
        elif m > 0.08: f['fcf'] = 63
        elif m > 0.02: f['fcf'] = 48
        elif m >= 0:   f['fcf'] = 33
        else:          f['fcf'] = 12
    else:
        f['fcf'] = 50
    roe = info.get('returnOnEquity')
    if   roe is None:  f['roic'] = 50
    elif roe > 0.40:   f['roic'] = 92
    elif roe > 0.25:   f['roic'] = 78
    elif roe > 0.15:   f['roic'] = 63
    elif roe > 0.05:   f['roic'] = 48
    elif roe >= 0:     f['roic'] = 35
    else:              f['roic'] = 15
    dte = info.get('debtToEquity')
    if   dte is None:  f['debt'] = 50
    elif dte < 20:     f['debt'] = 92
    elif dte < 50:     f['debt'] = 78
    elif dte < 100:    f['debt'] = 62
    elif dte < 200:    f['debt'] = 42
    elif dte < 400:    f['debt'] = 25
    else:              f['debt'] = 10
    return {k: int(v) for k, v in f.items()}

def compute_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains = losses = 0.0
    for i in range(len(closes) - period, len(closes)):
        diff = closes[i] - closes[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100
    return round(100 - 100 / (1 + avg_gain / avg_loss))

def fetch_fx():
    try:
        fx = yf.Ticker('EURUSD=X')
        hist = fx.history(period='5d')
        if not hist.empty:
            price = float(hist['Close'].iloc[-1])
            if price > 0:
                return round(1 / price, 4)
    except Exception as e:
        print(f'  FX error: {e}')
    return 0.92

def fetch_ticker(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period='1y', interval='1d', auto_adjust=True)
        if hist.empty:
            return None
        closes = [float(x) for x in hist['Close'].tolist() if x == x and x > 0]
        if len(closes) < 2:
            return None

        cur_p = closes[-1]
        prev_p = closes[-2]
        ch_pct = (cur_p - prev_p) / prev_p * 100

        try:
            fi = t.fast_info
            mp = getattr(fi, 'last_price', None)
            if mp and mp > 0:
                cur_p = float(mp)
            pc = getattr(fi, 'previous_close', None)
            if pc and pc > 0:
                ch_pct = (cur_p - float(pc)) / float(pc) * 100
            currency_code = getattr(fi, 'currency', '') or ''
        except Exception:
            currency_code = ''

        currency = 'E' if currency_code in ('EUR', 'GBp', 'GBX') else '$'
        rsi = compute_rsi(closes)
        ma50  = round(sum(closes[-50:])  / 50,  4) if len(closes) >= 50  else 0.0
        ma200 = round(sum(closes[-200:]) / 200, 4) if len(closes) >= 200 else 0.0

        full_info = {}
        pe = None
        analyst_score = None
        try:
            full_info = t.info
            pe = full_info.get('trailingPE') or full_info.get('forwardPE')
        except Exception:
            pass
        try:
            rec = t.recommendations_summary
            if rec is not None and not rec.empty:
                r0 = rec[rec['period'] == '0m'] if 'period' in rec.columns else rec.head(1)
                if not r0.empty:
                    row = r0.iloc[0]
                    sb  = float(row.get('strongBuy',  0) or 0)
                    b   = float(row.get('buy',         0) or 0)
                    h   = float(row.get('hold',        0) or 0)
                    s   = float(row.get('sell',        0) or 0)
                    ss  = float(row.get('strongSell',  0) or 0)
                    total = sb + b + h + s + ss
                    if total > 0:
                        analyst_score = (sb*1 + b*2 + h*3 + s*4 + ss*5) / total
        except Exception:
            pass

        result = {
            'p':            round(cur_p, 4),
            'ch':           round(ch_pct, 4),
            'currency':     currency,
            'closes':       [round(x, 4) for x in closes[-252:]],
            'rsi':          rsi,
            'ma50':         ma50,
            'ma200':        ma200,
            'pe':           round(float(pe), 2) if pe else None,
            'analystScore': round(float(analyst_score), 3) if analyst_score else None,
            'news':         fetch_news(t, ticker),
            'ts':           int(time.time() * 1000),
        }
        result['features'] = compute_feature_scores(result, closes, full_info)
        return result
    except Exception as e:
        print(f'  {ticker}: ERROR - {e}')
        return None

def main():
    print('Fetching FX rate...')
    fx_usd_eur = fetch_fx()
    print(f'  EURUSD = {1/fx_usd_eur:.4f}  →  FX_USDEUR = {fx_usd_eur}')

    data = {}
    for ticker in TICKERS:
        print(f'Fetching {ticker}...')
        result = fetch_ticker(ticker)
        if result:
            data[ticker] = result
            print(f'  OK: p={result["p"]:.2f} ch={result["ch"]:.2f}% rsi={result["rsi"]}')
        time.sleep(0.25)

    output = {
        'ts':       int(time.time() * 1000),
        'fxUsdEur': fx_usd_eur,
        'data':     data,
    }

    with open('data.json', 'w') as f:
        json.dump(output, f, separators=(',', ':'))

    print(f'\nDone! {len(data)}/{len(TICKERS)} tickers written to data.json')

if __name__ == '__main__':
    main()
