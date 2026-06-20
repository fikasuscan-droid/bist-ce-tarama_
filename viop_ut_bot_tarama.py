#!/usr/bin/env python3
"""
Pay Vadeli UT Bot Taraması — GitHub Actions için
UT Bot (KV4/ATR14), 15 dakikalık periyot
Gerçek VIOP vadeli kontrat fiyatları (borsapy ile)
AL/SAT (LONG/SHORT) sinyali değiştiğinde Telegram bildirimi gönderir
"""

import borsapy as bp
import pandas as pd
import numpy as np
import urllib.request
import urllib.parse
from datetime import datetime
import json
import os

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

KEY_VALUE  = 4.0
ATR_PERIOD = 14

STATE_FILE = "viop_ut_state.json"

HISSE_LISTESI = [
    "VAKBN","GARAN","ISCTR","AKBNK","YKBNK","THYAO","EREGL","SAHOL","TCELL","TUPRS",
    "ARCLK","EKGYO","KRDMD","KCHOL","PGSUS","PETKM","TOASO","TTKOM","HALKB","SISE",
    "VESTL","SOKM","OYAKC","GUBRF","ASELS","CCOLA","DOHOL","ENJSA","ENKAI","FROTO",
    "KOZAA","KOZAL","TSKB","ULKER","TKFEN","TAVHL","SASA","BIMAS","MGROS","AEFES",
    "ALKIM","ECILC","HEKTS","IPEKE","ISFIN","ISGYO","KARSN","MPARK","ODAS","SKBNK",
    "TRGYO","TURSG"
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

def en_yakin_kontrat_bul(dayanak):
    try:
        sonuclar = bp.search(dayanak, type="futures", exchange="BIST")
        if not sonuclar:
            return None
        return sonuclar[0]
    except Exception as e:
        print(f"{dayanak} kontrat arama hatasi: {e}")
        return None

def ut_bot_hesapla(df, key_value=4.0, atr_period=14):
    high  = df['High']
    low   = df['Low']
    close = df['Close']

    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low  - close.shift(1))
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=atr_period).mean()

    n_loss = key_value * atr
    src    = close

    trailing_stop = pd.Series(index=df.index, dtype=float)
    trailing_stop.iloc[0] = src.iloc[0]

    for i in range(1, len(df)):
        prev_ts = trailing_stop.iloc[i-1]
        prev_src = src.iloc[i-1]
        curr_src = src.iloc[i]
        loss = n_loss.iloc[i]

        if pd.isna(loss):
            trailing_stop.iloc[i] = prev_ts
            continue

        if curr_src > prev_ts and prev_src > prev_ts:
            trailing_stop.iloc[i] = max(prev_ts, curr_src - loss)
        elif curr_src < prev_ts and prev_src < prev_ts:
            trailing_stop.iloc[i] = min(prev_ts, curr_src + loss)
        elif curr_src > prev_ts:
            trailing_stop.iloc[i] = curr_src - loss
        else:
            trailing_stop.iloc[i] = curr_src + loss

    ema3 = close.ewm(span=3, adjust=False).mean()

    pos = pd.Series(index=df.index, dtype=int)
    pos.iloc[0] = 0

    for i in range(1, len(df)):
        above = (ema3.iloc[i-1] <= trailing_stop.iloc[i-1]) and (ema3.iloc[i] > trailing_stop.iloc[i])
        below = (ema3.iloc[i-1] >= trailing_stop.iloc[i-1]) and (ema3.iloc[i] < trailing_stop.iloc[i])

        if above:
            pos.iloc[i] = 1
        elif below:
            pos.iloc[i] = -1
        else:
            pos.iloc[i] = pos.iloc[i-1]

    return pos, trailing_stop

def hisse_sinyal(dayanak):
    try:
        kontrat = en_yakin_kontrat_bul(dayanak)

        if kontrat is None:
            ticker = bp.Ticker(dayanak)
            df = ticker.history(period="5g", interval="15m")
            sembol_gosterim = dayanak + " (spot)"
        else:
            sembol = kontrat.get('symbol', dayanak)
            ticker = bp.Ticker(sembol)
            df = ticker.history(period="5g", interval="15m")
            sembol_gosterim = sembol

        if df is None or len(df) < 20:
            return None

        pos, ts = ut_bot_hesapla(df, KEY_VALUE, ATR_PERIOD)

        curr_pos = pos.iloc[-1]
        fiyat     = df['Close'].iloc[-1]

        pozisyon = "LONG" if curr_pos == 1 else "SHORT" if curr_pos == -1 else "BEKLE"

        return {
            'dayanak': dayanak,
            'kontrat': sembol_gosterim,
            'fiyat': round(float(fiyat), 2),
            'pozisyon': pozisyon
        }
    except Exception as e:
        print(f"{dayanak} hata: {e}")
        return None

def tarama():
    print(f"\n{'='*50}")
    print(f"Pay Vadeli UT Bot Taramasi (KV4/ATR14, 15dk) — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"{'='*50}")

    eski_durum = durum_yukle()
    yeni_durum = {}

    yeni_long_sinyalleri  = []
    yeni_short_sinyalleri = []

    for i, dayanak in enumerate(HISSE_LISTESI):
        print(f"[{i+1}/{len(HISSE_LISTESI)}] {dayanak} taraniyor...")
        sonuc = hisse_sinyal(dayanak)

        if sonuc is None or sonuc['pozisyon'] == 'BEKLE':
            continue

        yeni_durum[dayanak] = sonuc['pozisyon']

        onceki_pozisyon = eski_durum.get(dayanak)

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
        mesaj = f"<b>Pay Vadeli UT Bot Sinyal Degisikligi</b>\n"
        mesaj += f"KV4/ATR14, 15dk\n"
        mesaj += f"Saat: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"

        if yeni_long_sinyalleri:
            mesaj += "LONG Sinyali:\n"
            for s in yeni_long_sinyalleri:
                mesaj += f"  {s['dayanak']} ({s['kontrat']}) - {s['fiyat']}\n"

        if yeni_short_sinyalleri:
            mesaj += "\nSHORT Sinyali:\n"
            for s in yeni_short_sinyalleri:
                mesaj += f"  {s['dayanak']} ({s['kontrat']}) - {s['fiyat']}\n"

        telegram_gonder(mesaj)
    else:
        print("Pozisyon degisikligi yok, bildirim gonderilmedi.")

if __name__ == "__main__":
    tarama()
