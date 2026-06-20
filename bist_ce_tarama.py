#!/usr/bin/env python3
"""
BIST CE Sinyal Taraması — GitHub Actions için
BIST100 + Yıldız Pazar, saatlik periyot
AL sinyali geldiğinde TP1/TP2/TP3/SL ile Telegram bildirimi gönderir
"""

import yfinance as yf
import pandas as pd
import numpy as np
import urllib.request
import urllib.parse
from datetime import datetime
import json
import os

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

CE_PERIOD = 5
CE_MULT   = 1.5

# TP/SL ATR çarpanları (MT5 indikatörüyle aynı mantık)
ATR_SL_MULT  = 1.5
ATR_TP1_MULT = 2.0
ATR_TP2_MULT = 3.5
ATR_TP3_MULT = 5.0

STATE_FILE = "bist_ce_state.json"

HISSE_LISTESI = [
    "AEFES","AGHOL","AKBNK","AKSA","AKSEN","ALARK","ALFAS","ALTNY","ANSGR","ARCLK",
    "ASELS","ASTOR","BERA","BIENY","BIMAS","BRSAN","BRYAT","BTCIM","CANTE","CCOLA",
    "CIMSA","CWENE","DOAS","DOHOL","ECILC","ECZYT","EGEEN","EKGYO","ENERY","ENJSA",
    "ENKAI","EREGL","EUPWR","EUREN","FROTO","GARAN","GENIL","GESAN","GOLTS","GRTHO",
    "GSRAY","GUBRF","GWIND","HALKB","HEKTS","ISCTR","ISDMR","ISMEN","IZMDC","KARDEMIR",
    "KCHOL","KLKIM","KLSER","KONTR","KORDS","KOZAA","KOZAL","KRDMD","KTLEV","LMKDC",
    "MAVI","MGROS","MIATK","MPARK","NTGAZ","OBAMS","ODAS","OTKAR","OYAKC","PAHOL",
    "PENTA","PETKM","PGSUS","PSGYO","QUAGR","RALYH","REEDR","RGYAS","SAHOL","SASA",
    "SAYAS","SDTTR","SELEC","SISE","SKBNK","SMART","SMRTG","SOKM","TABGD","TARKM",
    "TATGD","TAVHL","TCELL","TEZOL","THYAO","TKFEN","TMSN","TOASO","TSKB","TTKOM",
    "TTRAK","TUKAS","TUPRS","TURSG","ULKER","VAKBN","VESBE","VESTL","YEOTK","YKBNK",
    "YYLGD","ZOREN","ZRGYO","DOCO","FORTE","HALKI","KLRHO"
]

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

def atr_hesapla(df, period=14):
    high  = df['High']
    low   = df['Low']
    close = df['Close']
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low  - close.shift(1))
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def ce_hesapla(df, period=5, mult=1.5):
    high  = df['High']
    low   = df['Low']
    close = df['Close']

    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low  - close.shift(1))
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    highest_high = high.rolling(window=period).max()
    lowest_low   = low.rolling(window=period).min()

    long_stop  = highest_high - mult * atr
    short_stop = lowest_low   + mult * atr

    ce_dir = pd.Series(index=df.index, dtype=int)
    ce_dir.iloc[0] = 1

    for i in range(1, len(df)):
        c_prev = close.iloc[i-1]
        if c_prev > short_stop.iloc[i-1]:
            ce_dir.iloc[i] = -1
        elif c_prev < long_stop.iloc[i-1]:
            ce_dir.iloc[i] = 1
        else:
            ce_dir.iloc[i] = ce_dir.iloc[i-1]

    return ce_dir, long_stop, short_stop

def tp_sl_hesapla(fiyat, atr_v, pozisyon):
    """Pozisyon yönüne göre TP1/TP2/TP3/SL hesaplar"""
    if pozisyon == "LONG":
        sl  = fiyat - atr_v * ATR_SL_MULT
        tp1 = fiyat + atr_v * ATR_TP1_MULT
        tp2 = fiyat + atr_v * ATR_TP2_MULT
        tp3 = fiyat + atr_v * ATR_TP3_MULT
    else:  # SHORT
        sl  = fiyat + atr_v * ATR_SL_MULT
        tp1 = fiyat - atr_v * ATR_TP1_MULT
        tp2 = fiyat - atr_v * ATR_TP2_MULT
        tp3 = fiyat - atr_v * ATR_TP3_MULT
    return round(tp1, 2), round(tp2, 2), round(tp3, 2), round(sl, 2)

def hisse_sinyal(sembol):
    try:
        ticker = yf.Ticker(f"{sembol}.IS")
        df = ticker.history(period="30d", interval="60m")

        if df is None or len(df) < 20:
            return None

        ce_dir, long_stop, short_stop = ce_hesapla(df, CE_PERIOD, CE_MULT)
        atr_series = atr_hesapla(df, 14)

        curr_dir = ce_dir.iloc[-1]
        prev_dir = ce_dir.iloc[-2]
        fiyat    = df['Close'].iloc[-1]
        atr_v    = atr_series.iloc[-1]

        al_sinyali  = (prev_dir == 1 and curr_dir == -1)
        sat_sinyali = (prev_dir == -1 and curr_dir == 1)

        pozisyon = "LONG" if curr_dir == -1 else "SHORT"

        tp1, tp2, tp3, sl = tp_sl_hesapla(fiyat, atr_v, pozisyon)

        return {
            'sembol': sembol,
            'fiyat': round(float(fiyat), 2),
            'pozisyon': pozisyon,
            'al_sinyali': al_sinyali,
            'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'sl': sl
        }
    except Exception as e:
        print(f"{sembol} hata: {e}")
        return None

def tarama():
    print(f"\n{'='*50}")
    print(f"BIST CE Sinyal Taramasi — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"{'='*50}")

    eski_durum = durum_yukle()
    yeni_durum = {}

    yeni_long_sinyalleri  = []
    yeni_short_sinyalleri = []

    for i, sembol in enumerate(HISSE_LISTESI):
        print(f"[{i+1}/{len(HISSE_LISTESI)}] {sembol} taraniyor...")
        sonuc = hisse_sinyal(sembol)

        if sonuc is None:
            continue

        yeni_durum[sembol] = sonuc['pozisyon']

        onceki_pozisyon = eski_durum.get(sembol)

        if onceki_pozisyon is not None and onceki_pozisyon != sonuc['pozisyon']:
            if sonuc['pozisyon'] == 'LONG':
                yeni_long_sinyalleri.append(sonuc)
            else:
                yeni_short_sinyalleri.append(sonuc)
        elif onceki_pozisyon is None and sonuc['al_sinyali']:
            yeni_long_sinyalleri.append(sonuc)

    durum_kaydet(yeni_durum)

    print(f"\nTarama tamamlandi.")
    print(f"Yeni LONG sinyalleri: {len(yeni_long_sinyalleri)}")
    print(f"Yeni SHORT sinyalleri: {len(yeni_short_sinyalleri)}")

    if yeni_long_sinyalleri or yeni_short_sinyalleri:
        mesaj = f"<b>BIST CE Sinyal Degisikligi</b>\n"
        mesaj += f"Saat: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"

        if yeni_long_sinyalleri:
            mesaj += "🟢 LONG Sinyali:\n"
            for s in yeni_long_sinyalleri:
                mesaj += f"\n<b>{s['sembol']}</b> — {s['fiyat']} TL\n"
                mesaj += f"  TP1: {s['tp1']}  |  TP2: {s['tp2']}  |  TP3: {s['tp3']}\n"
                mesaj += f"  SL: {s['sl']}\n"

        if yeni_short_sinyalleri:
            mesaj += "\n🔴 SHORT Sinyali:\n"
            for s in yeni_short_sinyalleri:
                mesaj += f"\n<b>{s['sembol']}</b> — {s['fiyat']} TL\n"
                mesaj += f"  TP1: {s['tp1']}  |  TP2: {s['tp2']}  |  TP3: {s['tp3']}\n"
                mesaj += f"  SL: {s['sl']}\n"

        telegram_gonder(mesaj)
    else:
        print("Pozisyon degisikligi yok, bildirim gonderilmedi.")

if __name__ == "__main__":
    tarama()
