#!/usr/bin/env python3
"""
BIST Akşam Al / Sabah Sat Taraması
Kriterler:
- Hacim > 20 günlük ortalama x 2
- Yükseliş mumu (kapanış > açılış)
- CE yukarı (ekstra filtre)
Piyasa kapanışından sonra 18:05'te çalışır
"""

import yfinance as yf
import pandas as pd
import numpy as np
import urllib.request
import urllib.parse
from datetime import datetime
import os

try:
    from sinyal_kaydet import sinyal_kaydet
    KAYIT_VAR = True
except ImportError:
    KAYIT_VAR = False

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

CE_PERIOD = 5
CE_MULT   = 1.5
HACIM_KAT = 2.0
HACIM_PER = 20

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
            print(f"Telegram bildirimi gonderildi")
        except Exception as e:
            print(f"Telegram hatasi: {e}")

def ce_hesapla(df):
    high  = df['High']
    low   = df['Low']
    close = df['Close']

    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low  - close.shift(1))
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=CE_PERIOD).mean()

    h_shift = high.shift(1)
    l_shift = low.shift(1)
    c_shift = close.shift(1)

    highest_high = h_shift.rolling(window=CE_PERIOD).max()
    lowest_low   = l_shift.rolling(window=CE_PERIOD).min()

    long_stop  = highest_high - CE_MULT * atr
    short_stop = lowest_low   + CE_MULT * atr

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

def hisse_analiz(sembol):
    try:
        ticker = yf.Ticker(f"{sembol}.IS")
        df = ticker.history(period="60d", interval="1d")

        if df is None or len(df) < HACIM_PER + 5:
            return None

        # Son bar
        son_kap   = df['Close'].iloc[-1]
        son_acil  = df['Open'].iloc[-1]
        son_hacim = df['Volume'].iloc[-1]
        ort_hacim = df['Volume'].iloc[-HACIM_PER-1:-1].mean()
        son_degis = (son_kap - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100

        # Yükseliş mumu
        yukselis_mum = son_kap > son_acil

        # Hacim kriteri
        hacim_guclu = son_hacim > ort_hacim * HACIM_KAT

        # CE yönü
        ce_dir = ce_hesapla(df)
        ce_yukari = ce_dir.iloc[-1] == -1

        if not (yukselis_mum and hacim_guclu):
            return None

        return {
            'sembol':    sembol,
            'fiyat':     round(float(son_kap), 2),
            'degisim':   round(float(son_degis), 2),
            'hacim_kat': round(float(son_hacim / ort_hacim), 1),
            'ce_yukari': ce_yukari
        }

    except Exception as e:
        print(f"{sembol} hata: {e}")
        return None

def tarama():
    print(f"\n{'='*50}")
    print(f"BIST Aksam Al Taramasi — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"Kriter: Yukselis Mumu + Hacim > {HACIM_KAT}x Ortalama")
    print(f"{'='*50}")

    guclu  = []  # CE de yukarı
    normal = []  # Sadece hacim + yükseliş

    for i, sembol in enumerate(HISSE_LISTESI):
        print(f"[{i+1}/{len(HISSE_LISTESI)}] {sembol} taraniyor...")
        sonuc = hisse_analiz(sembol)

        if sonuc is None:
            continue

        if sonuc['ce_yukari']:
            guclu.append(sonuc)
        else:
            normal.append(sonuc)

    # Hacim katına göre sırala
    guclu.sort(key=lambda x: x['hacim_kat'], reverse=True)
    normal.sort(key=lambda x: x['hacim_kat'], reverse=True)

    print(f"\nTarama tamamlandi.")
    print(f"Guclu sinyal (CE+Hacim): {len(guclu)}")
    print(f"Normal sinyal (Hacim):   {len(normal)}")

    if guclu or normal:
        mesaj = f"🌙 <b>BIST Aksam Al Sinyali</b>\n"
        mesaj += f"Tarih: {datetime.now().strftime('%d.%m.%Y')}\n"
        mesaj += f"Kriter: Yukselis Mumu + Hacim {HACIM_KAT}x\n"
        mesaj += f"Hedef: Sabah acilista %2-3 gorunde sat\n\n"

        if guclu:
            mesaj += "🟢 <b>GUCLU (CE + Hacim + Yukselis):</b>\n"
            for s in guclu:
                ce_ikon = "✅ CE Yukari" if s['ce_yukari'] else ""
                mesaj += f"\n<b>{s['sembol']}</b> — {s['fiyat']} TL\n"
                mesaj += f"  Degisim: %{s['degisim']:+.2f} | Hacim: {s['hacim_kat']}x | {ce_ikon}\n"

        if normal:
            mesaj += f"\n🟡 <b>NORMAL (Hacim + Yukselis, CE ters):</b>\n"
            for s in normal[:5]:  # Sadece ilk 5
                mesaj += f"  {s['sembol']} — {s['fiyat']} TL | %{s['degisim']:+.2f} | {s['hacim_kat']}x\n"

        mesaj += f"\n⚠️ Sabah acilista takip et, %2-3 gorunde sat!"
        telegram_gonder(mesaj)
    else:
        print("Sinyal yok, bildirim gonderilmedi.")

    # Web app icin JSON kaydet
    if KAYIT_VAR:
        json_sinyaller = []
        for s in guclu:
            json_sinyaller.append({
                'sembol': s['sembol'], 'fiyat': s['fiyat'], 'yon': 'AL',
                'tur': 'GUCLU - CE + Hacim + Yukselis',
                'detay': 'Degisim: %' + str(s['degisim']) + ' | Hacim: ' + str(s['hacim_kat']) + 'x | Sabah %2-3 gorunce sat'
            })
        for s in normal[:5]:
            json_sinyaller.append({
                'sembol': s['sembol'], 'fiyat': s['fiyat'], 'yon': 'AL',
                'tur': 'NORMAL - Hacim + Yukselis (CE ters)',
                'detay': 'Degisim: %' + str(s['degisim']) + ' | Hacim: ' + str(s['hacim_kat']) + 'x'
            })
        sinyal_kaydet("aksam_al", json_sinyaller)

if __name__ == "__main__":
    tarama()
