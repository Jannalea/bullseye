import json
import time
import yfinance as yf

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
    try:
        raw = ticker_obj.news or []
        results = []
        seen = set()
        for item in sorted(raw, key=lambda x: x.get('providerPublishTime', 0), reverse=True):
            title = (item.get('title') or '').strip()
            url   = (item.get('link')  or '').strip()
            if not title or not url or title in seen:
                continue
            seen.add(title)
            results.append({
                'title':     title,
                'url':       url,
                'publisher': item.get('publisher', ''),
                'time':      item.get('providerPublishTime', 0),
                'sentiment': classify_sentiment(title),
            })
            if len(results) == 3:
                break
        return results
    except Exception as e:
        print(f'  news error for {ticker}: {e}')
        return []

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
]

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

        pe = None
        analyst_score = None
        try:
            info = t.info
            pe = info.get('trailingPE') or info.get('forwardPE')
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

        return {
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
