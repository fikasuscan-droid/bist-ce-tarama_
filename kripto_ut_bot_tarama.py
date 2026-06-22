#!/usr/bin/env python3
"""
Kripto UT Bot Taraması — GitHub Actions için
UT Bot (KV5/ATR14), 30 dakikalık periyot
Binance TR üzerinden en hacimli/likit Top 100 TRY paritesi
LONG/SHORT sinyali değiştiğinde TP1/TP2/TP3/SL ile Telegram bildirimi gönderir
"""

import ccxt
import pandas as pd
import numpy as np
import urllib.request
import urllib.parse
from datetime import datetime
import json
import os

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

KEY_VALUE  = 5.0
ATR_PERIOD = 14
TIMEFRAME  = "30m"

ATR_SL_MULT  = 1.0
ATR_TP1_MULT = 1.0
ATR_TP2_MULT = 2.0
ATR_TP3_MULT = 3.0

STATE_FILE = "kripto_ut_state.json"
TOP_N = 100

exchange = ccxt.binancetr({
    'enableRateLimit': True,
})

def durum_yukle():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def durum_kaydet(durum):
    with open(STATE_FILE, 'w') as f:
        json.dump(durum, f)

def telegram_gonder(mesaj):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram token/chat_id eksik!")
        return
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        'chat_id':    TELEGRAM_CHAT_ID,
        'text':       mesaj,
        'parse_mode': 'HTML'
    }).encode()
    try:
        urllib.request.urlopen(url, data, timeout=10)
        print("Telegram bildirimi gonderildi")
    except Exception as e:
        print(f"Telegram hatasi: {e}")

def get_top_symbols(n=100):
    exchange.load_markets()
    tickers = exchange.fetch_tickers()

    try_pairs = []
    for symbol, ticker in tickers.items():
        if symbol.endswith('/TRY') and ticker.get('quoteVolume'):
            try_pairs.append({
                'symbol': symbol,
                'volume': ticker['quoteVolume']
            })

    try_pairs.sort(key=lambda x: x['volume'], reverse=True)
    return [p['symbol'] for p in try_pairs[:n]]

def get_ohlcv(symbol, timeframe='30m', limit=100):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        return None

def atr_hesapla(df, period=14):
    high  = df['high']
    low   = df['low']
    close = df['close']
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low  - close.shift(1))
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()

def ut_bot_hesapla(df, key_value=5.0, atr_period=14):
    high  = df['high']
    low   = df['low']
    close = df['close']

    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low  - close.shift(1))
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(span=atr_period, adjust=False).mean()

    n_loss = key_value * atr
    src    = close

    ts = pd.Series(index=df.index, dtype=float)
    ts.iloc[0] = src.iloc[0]

    for i in range(1, len(df)):
        prev_ts  = ts.iloc[i-1]
        prev_src = src.iloc[i-1]
        curr_src = src.iloc[i]
        loss     = n_loss.iloc[i]

        if pd.isna(loss):
            ts.iloc[i] = prev_ts
            continue

        if curr_src > prev_ts and prev_src > prev_ts:
            ts.iloc[i] = max(prev_ts, curr_src - loss)
        elif curr_src < prev_ts and prev_src < prev_ts:
            ts.iloc[i] = min(prev_ts, curr_src + loss)
        elif curr_src > prev_ts:
            ts.iloc[i] = curr_src - loss
        else:
            ts.iloc[i] = curr_src + loss

    ema3 = close.ewm(span=3, adjust=False).mean()

    pos = pd.Series(index=df.index, dtype=int)
    pos.iloc[0] = 0

    for i in range(1, len(df)):
        above = (ema3.iloc[i-1] <= ts.iloc[i-1]) and (ema3.iloc[i] > ts.iloc[i])
        below = (ema3.iloc[i-1] >= ts.iloc[i-1]) and (ema3.iloc[i] < ts.iloc[i])

        if above:
            pos.iloc[i] = 1
        elif below:
            pos.iloc[i] = -1
        else:
            pos.iloc[i] = pos.iloc[i-1]

    return pos, ts

def tp_sl_hesapla(fiyat, atr_v, pozisyon):
    if pozisyon == "LONG":
        sl  = fiyat - atr_v * ATR_SL_MULT
        tp1 = fiyat + atr_v * ATR_TP1_MULT
        tp2 = fiyat + atr_v * ATR_TP2_MULT
        tp3 = fiyat + atr_v * ATR_TP3_MULT
    else:
        sl  = fiyat + atr_v * ATR_SL_MULT
        tp1 = fiyat - atr_v * ATR_TP1_MULT
        tp2 = fiyat - atr_v * ATR_TP2_MULT
        tp3 = fiyat - atr_v * ATR_TP3_MULT
    return round(tp1, 2), round(tp2, 2), round(tp3, 2), round(sl, 2)

def sembol_sinyal(symbol):
    try:
        df = get_ohlcv(symbol, TIMEFRAME, limit=100)

        if df is None or len(df) < 20:
            return None

        pos, ts = ut_bot_hesapla(df, KEY_VALUE, ATR_PERIOD)
        atr_series = atr_hesapla(df, ATR_PERIOD)

        curr_pos = pos.iloc[-1]
        fiyat    = df['close'].iloc[-1]
        atr_v    = atr_series.iloc[-1]

        pozisyon = "LONG" if curr_pos == 1 else "SHORT" if curr_pos == -1 else "BEKLE"

        tp1, tp2, tp3, sl = tp_sl_hesapla(fiyat, atr_v, pozisyon) if pozisyon != "BEKLE" else (None, None, None, None)

        return {
            'symbol': symbol.replace('/TRY', ''),
            'fiyat': round(float(fiyat), 2),
            'pozisyon': pozisyon,
            'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'sl': sl
        }
    except Exception as e:
        print(f"{symbol} hata: {e}")
        return None

def tarama():
    print(f"\n{'='*50}")
    print(f"Kripto UT Bot Taramasi (KV5/ATR14, {TIMEFRAME}) — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"Borsa: Binance TR (TRY paritesi)")
    print(f"{'='*50}")

    print(f"Top {TOP_N} hacimli/likit TRY paritesi aliniyor...")
    try:
        symbols = get_top_symbols(TOP_N)
        print(f"{len(symbols)} sembol bulundu.")
    except Exception as e:
        print(f"Sembol listesi alinamadi: {e}")
        return []

    eski_durum = durum_yukle()
    yeni_durum = {}

    yeni_long_sinyalleri  = []
    yeni_short_sinyalleri = []

    for i, symbol in enumerate(symbols):
        print(f"[{i+1}/{len(symbols)}] {symbol} taraniyor...")
        sonuc = sembol_sinyal(symbol)

        if sonuc is None or sonuc['pozisyon'] == 'BEKLE':
            continue

        yeni_durum[sonuc['symbol']] = sonuc['pozisyon']

        onceki_pozisyon = eski_durum.get(sonuc['symbol'])

        if onceki_pozisyon is not None and onceki_pozisyon != sonuc['pozisyon']:
            if sonuc['pozisyon'] == 'LONG':
                yeni_long_sinyalleri.append(sonuc)
            else:
                yeni_short_sinyalleri.append(sonuc)
        elif onceki_pozisyon is None:
            pass

    durum_kaydet(yeni_durum)

    print(f"\nTarama tamamlandi.")
    print(f"Yeni LONG sinyalleri: {len(yeni_long_sinyalleri)}")
    print(f"Yeni SHORT sinyalleri: {len(yeni_short_sinyalleri)}")

    if yeni_long_sinyalleri or yeni_short_sinyalleri:
        mesaj = f"<b>Kripto UT Bot Sinyal Degisikligi</b>\n"
        mesaj += f"KV5/ATR14, {TIMEFRAME} | Binance TR\n"
        mesaj += f"Saat: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"

        if yeni_long_sinyalleri:
            mesaj += "🟢 LONG Sinyali:\n"
            for s in yeni_long_sinyalleri:
                mesaj += f"\n<b>{s['symbol']}</b> — {s['fiyat']} TRY\n"
                mesaj += f"  TP1: {s['tp1']}  |  TP2: {s['tp2']}  |  TP3: {s['tp3']}\n"
                mesaj += f"  SL: {s['sl']}\n"

        if yeni_short_sinyalleri:
            mesaj += "\n🔴 SHORT Sinyali:\n"
            for s in yeni_short_sinyalleri:
                mesaj += f"\n<b>{s['symbol']}</b> — {s['fiyat']} TRY\n"
                mesaj += f"  TP1: {s['tp1']}  |  TP2: {s['tp2']}  |  TP3: {s['tp3']}\n"
                mesaj += f"  SL: {s['sl']}\n"

        telegram_gonder(mesaj)
    else:
        print("Pozisyon degisikligi yok, bildirim gonderilmedi.")

    return yeni_long_sinyalleri + yeni_short_sinyalleri

if __name__ == "__main__":
    tarama()
