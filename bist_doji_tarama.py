#!/usr/bin/env python3
"""
BIST Doji Mumu Taraması
Günlük ve Haftalık periyotta Doji tespit eder
CE yönüyle uyumlu Doji'leri öne çıkarır
Her gün 18:10 TR'de çalışır (günlük)
Her Cuma 18:15 TR'de çalışır (haftalık)
"""

import yfinance as yf
import pandas as pd
import numpy as np
import urllib.request
import urllib.parse
from datetime import datetime
import os
import sys

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

CE_PERIOD   = 5
CE_MULT     = 2.0
DOJI_ESIK   = 0.1   # Gövde/Toplam oranı eşiği

HISSE_LISTESI = [
    "AEFES","AGHOL","AKBNK","AKSA","AKSEN","ALARK","ALFAS","ALTNY","ANSGR","ARCLK",
    "ASELS","ASTOR","BERA","BIENY","BIMAS","BRSAN","BRYAT","BTCIM","CANTE","CCOLA",
    "CIMSA","CWENE","DOAS","DOHOL","ECILC","ECZYT","EGEEN","EKGYO","ENERY","ENJSA",
    "ENKAI","EREGL","EUPWR","EUREN","FROTO","GARAN","GENIL","GESAN","GUBRF","HALKB",
    "HEKTS","ISCTR","KCHOL","KLKIM","KONTR","KOZAA","KOZAL","KRDMD","KTLEV","MGROS",
    "MPARK","ODAS","OTKAR","OYAKC","PETKM","PGSUS","SAHOL","SASA","SISE","SKBNK",
    "SOKM","TAVHL","TCELL","THYAO","TKFEN","TOASO","TSKB","TTKOM","TTRAK","TUPRS",
    "TURSG","ULKER","VAKBN","VESBE","VESTL","YKBNK","ZOREN"
]
HISSE_LISTESI = list(dict.fromkeys(HISSE_LISTESI))

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
            print("Telegram bildirimi gonderildi")
        except Exception as e:
            print(f"Telegram hatasi: {e}")

def ce_hesapla(df, period=5, mult=2.0):
    high  = df['High']
    low   = df['Low']
    close = df['Close']
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low  - close.shift(1))
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    h_shift = high.shift(1)
    l_shift = low.shift(1)
    c_shift = close.shift(1)
    highest_high = h_shift.rolling(window=period).max()
    lowest_low   = l_shift.rolling(window=period).min()
    long_stop  = highest_high - mult * atr
    short_stop = lowest_low   + mult * atr
    ce_dir = pd.Series(index=df.index, dtype=int)
    ce_dir.iloc[0] = 1
    for i in range(1, len(df)):
        c_prev  = c_shift.iloc[i]
        ls_prev = long_stop.iloc[i-1]
        ss_prev = short_stop.iloc[i-1]
        if pd.isna(c_prev) or pd.isna(ss_prev) or pd.isna(ls_prev):
            ce_dir.iloc[i] = ce_dir.iloc[i-1]
            continue
        if c_prev > ss_prev:
            ce_dir.iloc[i] = -1
        elif c_prev < ls_prev:
            ce_dir.iloc[i] = 1
        else:
            ce_dir.iloc[i] = ce_dir.iloc[i-1]
    return ce_dir

def doji_mu(row, esik=0.1):
    govde  = abs(row['Close'] - row['Open'])
    toplam = row['High'] - row['Low']
    if toplam == 0:
        return False
    return (govde / toplam) <= esik

def doji_turu(row):
    govde     = abs(row['Close'] - row['Open'])
    toplam    = row['High'] - row['Low']
    ust_golge = row['High'] - max(row['Close'], row['Open'])
    alt_golge = min(row['Close'], row['Open']) - row['Low']

    if toplam == 0:
        return "Doji"

    if ust_golge >= toplam * 0.6:
        return "Mezartas Doji"   # Bearish
    elif alt_golge >= toplam * 0.6:
        return "Dragonfly Doji"  # Bullish
    elif govde / toplam <= 0.05:
        return "4 Fiyat Doji"    # Notr
    else:
        return "Doji"

def gunluk_haftalik_cevir(df):
    df.index = pd.to_datetime(df.index)
    weekly = df.resample('W-FRI').agg({
        'Open':   'first',
        'High':   'max',
        'Low':    'min',
        'Close':  'last',
        'Volume': 'sum'
    }).dropna()
    return weekly

def hisse_analiz(sembol, periyot="gunluk"):
    try:
        ticker = yf.Ticker(f"{sembol}.IS")
        df_gun = ticker.history(period="max", interval="1d")

        if df_gun is None or len(df_gun) < 30:
            return None

        if periyot == "haftalik":
            df = gunluk_haftalik_cevir(df_gun)
            if len(df) < 20:
                return None
        else:
            df = df_gun

        # Son bar Doji mi?
        son_bar = df.iloc[-1]
        if not doji_mu(son_bar):
            return None

        tur = doji_turu(son_bar)
        fiyat = round(float(son_bar['Close']), 2)

        # CE yönü
        ce_dir = ce_hesapla(df, CE_PERIOD, CE_MULT)
        ce_yon = ce_dir.iloc[-1]
        ce_str = "YUKARI" if ce_yon == -1 else "ASAGI"

        # CE yönüyle uyum
        # Dragonfly Doji + CE yukarı = bullish uyum
        # Mezartaşı Doji + CE aşağı = bearish uyum
        uyum = False
        if tur == "Dragonfly Doji" and ce_yon == -1:
            uyum = True
        elif tur == "Mezartas Doji" and ce_yon == 1:
            uyum = True
        elif tur == "Doji":
            uyum = None  # nötr

        # Hacim kontrolü
        son_hacim = df['Volume'].iloc[-1]
        ort_hacim = df['Volume'].iloc[-20:-1].mean()
        hacim_kat = round(son_hacim / ort_hacim, 1) if ort_hacim > 0 else 0

        return {
            'sembol':    sembol,
            'fiyat':     fiyat,
            'tur':       tur,
            'ce_yon':    ce_str,
            'uyum':      uyum,
            'hacim_kat': hacim_kat
        }

    except Exception as e:
        print(f"{sembol} hata: {e}")
        return None

def tarama(periyot="gunluk"):
    print(f"\n{'='*50}")
    print(f"BIST Doji Taramasi ({periyot.upper()}) — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"{'='*50}")

    uyumlu   = []  # CE yönüyle uyumlu
    notr     = []  # Standart Doji
    ters     = []  # CE yönüne karşı

    for i, sembol in enumerate(HISSE_LISTESI):
        print(f"[{i+1}/{len(HISSE_LISTESI)}] {sembol}...")
        sonuc = hisse_analiz(sembol, periyot)
        if sonuc is None:
            continue

        if sonuc['uyum'] is True:
            uyumlu.append(sonuc)
        elif sonuc['uyum'] is None:
            notr.append(sonuc)
        else:
            ters.append(sonuc)

    print(f"\nTarama tamamlandi.")
    print(f"Uyumlu: {len(uyumlu)} | Notr: {len(notr)} | Ters: {len(ters)}")

    # Hacim katına göre sırala
    uyumlu.sort(key=lambda x: x['hacim_kat'], reverse=True)
    notr.sort(key=lambda x: x['hacim_kat'], reverse=True)

    if uyumlu or notr or ters:
        periyot_txt = "Günlük" if periyot == "gunluk" else "Haftalık"
        mesaj = f"🕯 <b>BIST Doji Taramasi ({periyot_txt})</b>\n"
        mesaj += f"Tarih: {datetime.now().strftime('%d.%m.%Y')}\n\n"

        if uyumlu:
            mesaj += "🟢 <b>CE Uyumlu Doji:</b>\n"
            for s in uyumlu:
                mesaj += f"<b>{s['sembol']}</b> — {s['fiyat']} TL\n"
                mesaj += f"  {s['tur']} | CE: {s['ce_yon']} | Hacim: {s['hacim_kat']}x\n"

        if notr:
            mesaj += "\n🟡 <b>Standart Doji:</b>\n"
            for s in notr:
                mesaj += f"{s['sembol']} — {s['fiyat']} TL | CE: {s['ce_yon']} | {s['hacim_kat']}x\n"

        if ters:
            mesaj += "\n🔴 <b>CE Ters Doji:</b>\n"
            for s in ters:
                mesaj += f"{s['sembol']} — {s['fiyat']} TL | {s['tur']} | CE: {s['ce_yon']}\n"

        telegram_gonder(mesaj)
    else:
        print("Doji bulunamadi.")

if __name__ == "__main__":
    # Argüman ile periyot seç: python bist_doji_tarama.py gunluk veya haftalik
    periyot = sys.argv[1] if len(sys.argv) > 1 else "gunluk"
    tarama(periyot)
