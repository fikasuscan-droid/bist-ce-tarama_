#!/usr/bin/env python3
"""
BIST CE Sinyal Taraması — GitHub Actions için
CE (Chandelier Exit) indikatörü, saatlik periyot
BIST100 + Yıldız Pazar hisseleri
LONG/SHORT pozisyon değişikliğinde Telegram bildirimi gönderir
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

# CE parametreleri (Pine Script ile aynı)
CE_PERIOD = 5
CE_MULT   = 1.5
ATR_SL    = 1.5
ATR_TP1   = 2.0
ATR_TP2   = 3.5

STATE_FILE = "bist_ce_v2_state.json"

HISSE_LISTESI = [
    "AEFES","AGHOL","AKBNK","AKSA","AKSEN","ALARK","ALFAS","ALTNY","ANSGR","ARCLK",
    "ASELS","ASTOR","BERA","BIENY","BIMAS","BRSAN","BRYAT","BTCIM","CANTE","CCOLA",
    "CIMSA","CWENE","DOAS","DOHOL","ECILC","ECZYT","EGEEN","EKGYO","ENERY","ENJSA",
    "ENKAI","EREGL","EUPWR","EUREN","FROTO","GARAN","GENIL","GESAN","GOLTS","GRTHO",
    "GSRAY","GUBRF","GWIND","HALKB","HEKTS","ISCTR","ISDMR","ISMEN","IZMDC","KCHOL",
    "KLKIM","KLSER","KONTR","KORDS","KOZAA","KOZAL","KRDMD","KTLEV","LMKDC","MAVI",
    "MGROS","MIATK","MPARK","NTGAZ","OBAMS","ODAS","OTKAR","OYAKC","PAHOL","PENTA",
    "PETKM","PGSUS","PSGYO","SAHOL","SASA","SAYAS","SELEC","SISE","SKBNK","SOKM",
    "TABGD","TATGD","TAVHL","TCELL","THYAO","TKFEN","TOASO","TSKB","TTKOM","TTRAK",
    "TUPRS","TURSG","ULKER","VAKBN","VESBE","VESTL","YKBNK","YYLGD","ZOREN","ZRGYO",
    "DOCO","FORTE","KLRHO","EKGYO","ENERY","ENJSA"
]
# Tekrar edenleri temizle
HISSE_LISTESI = list(dict.fromkeys(HISSE_LISTESI))

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
    limit = 4000
    parcalar = [mesaj[i:i+limit] for i in range(0, len(mesaj), limit)]
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for parca in parcalar:
        data = urllib.parse.urlencode({
            'chat_id':    TELEGRAM_CHAT_ID,
            'text':       parca,
            'parse_mode': 'HTML'
        }).encode()
        try:
            urllib.request.urlopen(url, data, timeout=10)
            print(f"Telegram bildirimi gonderildi ({len(parca)} karakter)")
        except Exception as e:
            print(f"Telegram hatasi: {e}")

def ce_hesapla(df, period=5, mult=1.5):
    """
    Pine Script CE mantığıyla aynı:
    - Önceki kapanmış barın H/L/C verisini kullanır
    - highest_high ve lowest_low period kadar geriye bakar
    - ce_dir: -1 = LONG (fiyat yukarı), 1 = SHORT (fiyat aşağı)
    """
    high  = df['High']
    low   = df['Low']
    close = df['Close']

    # ATR hesapla
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low  - close.shift(1))
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    atr14 = tr.rolling(window=14).mean()

    # Pine Script: highest_high = ta.highest(h, ce_period) — önceki barın high'ı
    # h = high[1] olduğundan shift(1) yapıyoruz
    h_shifted = high.shift(1)
    l_shifted = low.shift(1)
    c_shifted = close.shift(1)

    highest_high = h_shifted.rolling(window=period).max()
    lowest_low   = l_shifted.rolling(window=period).min()

    long_stop  = highest_high - mult * atr
    short_stop = lowest_low   + mult * atr

    # CE yönü hesapla
    ce_dir = pd.Series(index=df.index, dtype=int)
    ce_dir.iloc[0] = 1

    for i in range(1, len(df)):
        c_prev = c_shifted.iloc[i]  # önceki kapanış
        ls_prev = long_stop.iloc[i-1] if i > 0 else long_stop.iloc[i]
        ss_prev = short_stop.iloc[i-1] if i > 0 else short_stop.iloc[i]

        if pd.isna(c_prev) or pd.isna(ss_prev) or pd.isna(ls_prev):
            ce_dir.iloc[i] = ce_dir.iloc[i-1]
            continue

        if c_prev > ss_prev:
            ce_dir.iloc[i] = -1
        elif c_prev < ls_prev:
            ce_dir.iloc[i] = 1
        else:
            ce_dir.iloc[i] = ce_dir.iloc[i-1]

    return ce_dir, long_stop, short_stop, atr14

def tp_sl_hesapla(fiyat, atr_v, yon):
    if yon == "LONG":
        sl  = round(fiyat - atr_v * ATR_SL,  2)
        tp1 = round(fiyat + atr_v * ATR_TP1, 2)
        tp2 = round(fiyat + atr_v * ATR_TP2, 2)
    else:
        sl  = round(fiyat + atr_v * ATR_SL,  2)
        tp1 = round(fiyat - atr_v * ATR_TP1, 2)
        tp2 = round(fiyat - atr_v * ATR_TP2, 2)
    return tp1, tp2, sl

def hisse_sinyal(sembol):
    try:
        ticker = yf.Ticker(f"{sembol}.IS")
        df = ticker.history(period="30d", interval="60m")

        if df is None or len(df) < CE_PERIOD + 5:
            return None

        ce_dir, long_stop, short_stop, atr14 = ce_hesapla(df, CE_PERIOD, CE_MULT)

        curr_dir = ce_dir.iloc[-1]
        prev_dir = ce_dir.iloc[-2]
        fiyat    = df['Close'].iloc[-1]
        atr_v    = atr14.iloc[-1]

        # Pozisyon: ce_dir == -1 → LONG (yukarı trend), ce_dir == 1 → SHORT
        pozisyon = "LONG" if curr_dir == -1 else "SHORT"

        yeni_al  = (curr_dir == -1 and prev_dir == 1)
        yeni_sat = (curr_dir == 1  and prev_dir == -1)

        tp1, tp2, sl = tp_sl_hesapla(fiyat, atr_v, pozisyon)

        return {
            'sembol':   sembol,
            'fiyat':    round(float(fiyat), 2),
            'pozisyon': pozisyon,
            'yeni_al':  yeni_al,
            'yeni_sat': yeni_sat,
            'tp1': tp1, 'tp2': tp2, 'sl': sl
        }
    except Exception as e:
        print(f"{sembol} hata: {e}")
        return None

def tarama():
    print(f"\n{'='*50}")
    print(f"BIST CE Sinyal Taramasi — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"CE({CE_PERIOD},{CE_MULT}) | Saatlik | BIST100+Yildiz Pazar")
    print(f"{'='*50}")

    eski_durum = durum_yukle()
    yeni_durum = {}

    yeni_long  = []
    yeni_short = []

    for i, sembol in enumerate(HISSE_LISTESI):
        print(f"[{i+1}/{len(HISSE_LISTESI)}] {sembol} taraniyor...")
        sonuc = hisse_sinyal(sembol)

        if sonuc is None:
            continue

        yeni_durum[sembol] = sonuc['pozisyon']

        onceki = eski_durum.get(sembol)

        if onceki is not None and onceki != sonuc['pozisyon']:
            if sonuc['pozisyon'] == 'LONG':
                yeni_long.append(sonuc)
            else:
                yeni_short.append(sonuc)
        elif onceki is None:
            pass  # ilk tarama, referans kaydet

    durum_kaydet(yeni_durum)

    print(f"\nTarama tamamlandi.")
    print(f"Yeni LONG : {len(yeni_long)}")
    print(f"Yeni SHORT: {len(yeni_short)}")

    if yeni_long or yeni_short:
        mesaj = f"<b>BIST CE Sinyal</b>\n"
        mesaj += f"CE({CE_PERIOD},{CE_MULT}) | Saatlik\n"
        mesaj += f"Saat: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"

        if yeni_long:
            mesaj += "🟢 <b>LONG Sinyali:</b>\n"
            for s in yeni_long:
                mesaj += f"\n<b>{s['sembol']}</b> — {s['fiyat']} TL\n"
                mesaj += f"  TP1: {s['tp1']}  |  TP2: {s['tp2']}\n"
                mesaj += f"  SL: {s['sl']}\n"

        if yeni_short:
            mesaj += "\n🔴 <b>SHORT Sinyali:</b>\n"
            for s in yeni_short:
                mesaj += f"\n<b>{s['sembol']}</b> — {s['fiyat']} TL\n"
                mesaj += f"  TP1: {s['tp1']}  |  TP2: {s['tp2']}\n"
                mesaj += f"  SL: {s['sl']}\n"

        telegram_gonder(mesaj)
    else:
        print("Pozisyon degisikligi yok, bildirim gonderilmedi.")

if __name__ == "__main__":
    tarama()
