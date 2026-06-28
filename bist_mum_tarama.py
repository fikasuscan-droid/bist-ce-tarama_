#!/usr/bin/env python3
"""
BIST Mum Formasyonu Taraması — GitHub Actions için
CE yönüyle uyumlu mum formasyonlarını tespit eder
Her gün piyasa kapanışından sonra çalışır
Telegram'a bildirim gönderir
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

HISSE_LISTESI = [
    "AEFES","AGHOL","AKBNK","AKSA","AKSEN","ALARK","ALFAS","ALTNY","ANSGR","ARCLK",
    "ASELS","ASTOR","BERA","BIENY","BIMAS","BRSAN","BRYAT","BTCIM","CANTE","CCOLA",
    "CIMSA","CWENE","DOAS","DOHOL","ECILC","ECZYT","EGEEN","EKGYO","ENERY","ENJSA",
    "ENKAI","EREGL","EUPWR","EUREN","FROTO","GARAN","GENIL","GESAN","GUBRF","HALKB",
    "HEKTS","ISCTR","KCHOL","KLKIM","KONTR","KOZAA","KOZAL","KRDMD","KTLEV","MGROS",
    "MPARK","ODAS","OTKAR","OYAKC","PETKM","PGSUS","SAHOL","SASA","SISE","SKBNK",
    "SOKM","TAVHL","TCELL","THYAO","TKFEN","TOASO","TSKB","TTKOM","TTRAK","TUPRS",
    "TURSG","ULKER","VAKBN","VESBE","VESTL","YKBNK","ZOREN","EKGYO","ENERY","ENJSA",
    "ASELS","AKBNK","THYAO","ENKAI","FROTO","EREGL","PETKM","KCHOL","GARAN","TKFEN"
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

def ce_hesapla(df, period=5, mult=1.5):
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

def mum_formasyonlari(df):
    o = df['Open']
    h = df['High']
    l = df['Low']
    c = df['Close']

    govde     = abs(c - o)
    ust_golge = h - pd.concat([c, o], axis=1).max(axis=1)
    alt_golge = pd.concat([c, o], axis=1).min(axis=1) - l
    toplam    = h - l

    tr1 = h - l
    tr2 = abs(h - c.shift(1))
    tr3 = abs(l - c.shift(1))
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    yukselis = c > o
    dusus    = c < o

    formasyonlar = {}

    # DOJI
    formasyonlar['Doji'] = govde <= toplam * 0.1

    # HAMMER
    formasyonlar['Hammer'] = (
        (alt_golge >= govde * 2) &
        (ust_golge <= govde * 0.3) &
        (govde > atr * 0.3) &
        dusus.shift(1)
    )

    # SHOOTING STAR
    formasyonlar['Shooting Star'] = (
        (ust_golge >= govde * 2) &
        (alt_golge <= govde * 0.3) &
        (govde > atr * 0.3) &
        yukselis.shift(1)
    )

    # PINBAR YUKSELIS
    formasyonlar['Pinbar (AL)'] = (
        (alt_golge >= toplam * 0.6) &
        (govde <= toplam * 0.3)
    )

    # PINBAR DUSUS
    formasyonlar['Pinbar (SAT)'] = (
        (ust_golge >= toplam * 0.6) &
        (govde <= toplam * 0.3)
    )

    # BULL ENGULFING
    formasyonlar['Bull Engulfing'] = (
        dusus.shift(1) &
        yukselis &
        (o < c.shift(1)) &
        (c > o.shift(1)) &
        (govde > atr * 0.3)
    )

    # BEAR ENGULFING
    formasyonlar['Bear Engulfing'] = (
        yukselis.shift(1) &
        dusus &
        (o > c.shift(1)) &
        (c < o.shift(1)) &
        (govde > atr * 0.3)
    )

    # BULL HARAMI
    formasyonlar['Bull Harami'] = (
        dusus.shift(1) &
        yukselis &
        (o > c.shift(1)) &
        (c < o.shift(1)) &
        (govde < abs(c.shift(1) - o.shift(1)) * 0.5)
    )

    # BEAR HARAMI
    formasyonlar['Bear Harami'] = (
        yukselis.shift(1) &
        dusus &
        (o < c.shift(1)) &
        (c > o.shift(1)) &
        (govde < abs(c.shift(1) - o.shift(1)) * 0.5)
    )

    # MORNING STAR
    formasyonlar['Morning Star'] = (
        dusus.shift(2) &
        (abs(c.shift(1) - o.shift(1)) < atr * 0.3) &
        yukselis &
        (c > (o.shift(2) + c.shift(2)) / 2)
    )

    # EVENING STAR
    formasyonlar['Evening Star'] = (
        yukselis.shift(2) &
        (abs(c.shift(1) - o.shift(1)) < atr * 0.3) &
        dusus &
        (c < (o.shift(2) + c.shift(2)) / 2)
    )

    # THREE WHITE SOLDIERS
    formasyonlar['3 Soldiers'] = (
        yukselis & yukselis.shift(1) & yukselis.shift(2) &
        (govde > atr * 0.5) &
        (abs(c.shift(1) - o.shift(1)) > atr * 0.5) &
        (abs(c.shift(2) - o.shift(2)) > atr * 0.5)
    )

    # THREE BLACK CROWS
    formasyonlar['3 Crows'] = (
        dusus & dusus.shift(1) & dusus.shift(2) &
        (govde > atr * 0.5) &
        (abs(c.shift(1) - o.shift(1)) > atr * 0.5) &
        (abs(c.shift(2) - o.shift(2)) > atr * 0.5)
    )

    # MARUBOZU
    formasyonlar['Bull Marubozu'] = (
        yukselis &
        (ust_golge < atr * 0.05) &
        (alt_golge < atr * 0.05) &
        (govde > atr * 0.8)
    )

    formasyonlar['Bear Marubozu'] = (
        dusus &
        (ust_golge < atr * 0.05) &
        (alt_golge < atr * 0.05) &
        (govde > atr * 0.8)
    )

    return formasyonlar

# CE yönüyle uyumlu formasyonlar
YUKSELIS_FORM = ['Hammer', 'Pinbar (AL)', 'Bull Engulfing', 'Bull Harami', 'Morning Star', '3 Soldiers', 'Bull Marubozu']
DUSUS_FORM    = ['Shooting Star', 'Pinbar (SAT)', 'Bear Engulfing', 'Bear Harami', 'Evening Star', '3 Crows', 'Bear Marubozu']

def hisse_analiz(sembol):
    try:
        ticker = yf.Ticker(f"{sembol}.IS")
        df = ticker.history(period="60d", interval="1d")

        if df is None or len(df) < 20:
            return None

        ce_dir = ce_hesapla(df, CE_PERIOD, CE_MULT)
        formasyonlar = mum_formasyonlari(df)

        son_ce   = ce_dir.iloc[-1]
        fiyat    = df['Close'].iloc[-1]

        bulunan = []

        for form_adi, form_ser in formasyonlar.items():
            if form_ser.iloc[-1]:
                # CE yönüyle uyumlu mu?
                if son_ce == -1 and form_adi in YUKSELIS_FORM:
                    bulunan.append(('GUCLU_YUKSELIS', form_adi))
                elif son_ce == 1 and form_adi in DUSUS_FORM:
                    bulunan.append(('GUCLU_DUSUS', form_adi))

        if not bulunan:
            return None

        return {
            'sembol':     sembol,
            'fiyat':      round(float(fiyat), 2),
            'ce_yon':     'YUKARI' if son_ce == -1 else 'ASAGI',
            'formasyonlar': bulunan
        }

    except Exception as e:
        print(f"{sembol} hata: {e}")
        return None

def tarama():
    print(f"\n{'='*50}")
    print(f"BIST Mum Formasyon Taramasi — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"CE({CE_PERIOD},{CE_MULT}) | Gunluk | CE Uyumlu Formasyonlar")
    print(f"{'='*50}")

    yukselis_sinyaller = []
    dusus_sinyaller    = []

    for i, sembol in enumerate(HISSE_LISTESI):
        print(f"[{i+1}/{len(HISSE_LISTESI)}] {sembol} taraniyor...")
        sonuc = hisse_analiz(sembol)

        if sonuc is None:
            continue

        for tur, form in sonuc['formasyonlar']:
            if tur == 'GUCLU_YUKSELIS':
                yukselis_sinyaller.append({**sonuc, 'formasyon': form})
            elif tur == 'GUCLU_DUSUS':
                dusus_sinyaller.append({**sonuc, 'formasyon': form})

    print(f"\nTarama tamamlandi.")
    print(f"Yukselis sinyali: {len(yukselis_sinyaller)}")
    print(f"Dusus sinyali:    {len(dusus_sinyaller)}")

    if yukselis_sinyaller or dusus_sinyaller:
        mesaj = f"<b>BIST Mum Formasyon Sinyali</b>\n"
        mesaj += f"CE({CE_PERIOD},{CE_MULT}) | Gunluk\n"
        mesaj += f"Tarih: {datetime.now().strftime('%d.%m.%Y')}\n\n"

        if yukselis_sinyaller:
            mesaj += "🟢 <b>YUKSELIS Formasyonlari (CE Uyumlu):</b>\n"
            for s in yukselis_sinyaller:
                mesaj += f"\n<b>{s['sembol']}</b> — {s['fiyat']} TL\n"
                mesaj += f"  CE: {s['ce_yon']} | Formasyon: {s['formasyon']}\n"

        if dusus_sinyaller:
            mesaj += "\n🔴 <b>DUSUS Formasyonlari (CE Uyumlu):</b>\n"
            for s in dusus_sinyaller:
                mesaj += f"\n<b>{s['sembol']}</b> — {s['fiyat']} TL\n"
                mesaj += f"  CE: {s['ce_yon']} | Formasyon: {s['formasyon']}\n"

        telegram_gonder(mesaj)
    else:
        print("CE uyumlu formasyon bulunamadi, bildirim gonderilmedi.")

if __name__ == "__main__":
    tarama()
