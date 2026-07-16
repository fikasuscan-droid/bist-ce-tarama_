#!/usr/bin/env python3
"""
BIST Doji Onaylı Dönüş Taraması
Mantık:
- Önceki bar (dünkü/geçen haftaki) Doji olmalı
- Doji dip veya tepe bölgesinde olmalı
- Son bar (bugünkü) onay barı olmalı:
  * Dipte Doji + bugün yükseliş kapanışı → DONUS AL onayı
  * Tepede Doji + bugün düşüş kapanışı → DONUS SAT onayı
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

CE_PERIOD    = 5
CE_MULT      = 2.0
DOJI_ESIK    = 0.1
DIP_TEPE_PER = 20
DIP_TEPE_ORAN = 0.2

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
        return "Mezartas Doji"
    elif alt_golge >= toplam * 0.6:
        return "Dragonfly Doji"
    else:
        return "Doji"

def dip_tepe_kontrol(df, bar_index, periyot=20, oran=0.2):
    """Belirtilen barın dip/tepe konumunu kontrol et"""
    fiyat = df['Close'].iloc[bar_index]
    baslangic = max(0, len(df) + bar_index - periyot)
    aralik_data = df['Close'].iloc[baslangic:bar_index if bar_index != -1 else len(df)]
    if len(aralik_data) < 5:
        return None
    en_dusuk  = aralik_data.min()
    en_yuksek = aralik_data.max()
    aralik    = en_yuksek - en_dusuk
    if aralik == 0:
        return None
    konum = (fiyat - en_dusuk) / aralik
    if konum <= oran:
        return "DIP"
    elif konum >= (1 - oran):
        return "TEPE"
    return None

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
            if len(df) < 25:
                return None
        else:
            df = df_gun

        # ÖNCEKİ BAR Doji mi? (df.iloc[-2])
        doji_bar = df.iloc[-2]
        if not doji_mu(doji_bar):
            return None

        # Doji dip/tepede miydi?
        konum = dip_tepe_kontrol(df, -2, DIP_TEPE_PER, DIP_TEPE_ORAN)
        if konum is None:
            return None

        # SON BAR onay barı mı?
        onay_bar = df.iloc[-1]
        onay_yukselis = onay_bar['Close'] > onay_bar['Open'] and onay_bar['Close'] > doji_bar['Close']
        onay_dusus    = onay_bar['Close'] < onay_bar['Open'] and onay_bar['Close'] < doji_bar['Close']

        # Onay kontrolü
        sinyal = None
        if konum == "DIP" and onay_yukselis:
            sinyal = "DONUS AL ONAYLANDI"
        elif konum == "TEPE" and onay_dusus:
            sinyal = "DONUS SAT ONAYLANDI"

        if sinyal is None:
            return None

        tur   = doji_turu(doji_bar)
        fiyat = round(float(onay_bar['Close']), 2)

        ce_dir = ce_hesapla(df, CE_PERIOD, CE_MULT)
        ce_str = "YUKARI" if ce_dir.iloc[-1] == -1 else "ASAGI"

        son_hacim = df['Volume'].iloc[-1]
        ort_hacim = df['Volume'].iloc[-20:-1].mean()
        hacim_kat = round(son_hacim / ort_hacim, 1) if ort_hacim > 0 else 0

        # Onay barı hacimli mi? (ekstra güç göstergesi)
        hacim_guclu = hacim_kat >= 1.5

        return {
            'sembol':      sembol,
            'fiyat':       fiyat,
            'tur':         tur,
            'konum':       konum,
            'sinyal':      sinyal,
            'ce_yon':      ce_str,
            'hacim_kat':   hacim_kat,
            'hacim_guclu': hacim_guclu
        }

    except Exception as e:
        print(f"{sembol} hata: {e}")
        return None

def tarama(periyot="gunluk"):
    print(f"\n{'='*50}")
    print(f"BIST Doji Onayli Donus ({periyot.upper()}) — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"Doji (onceki bar) + Onay (son bar)")
    print(f"{'='*50}")

    al_listesi  = []
    sat_listesi = []

    for i, sembol in enumerate(HISSE_LISTESI):
        print(f"[{i+1}/{len(HISSE_LISTESI)}] {sembol}...")
        sonuc = hisse_analiz(sembol, periyot)
        if sonuc is None:
            continue
        if "AL" in sonuc['sinyal']:
            al_listesi.append(sonuc)
        else:
            sat_listesi.append(sonuc)

    print(f"\nTarama tamamlandi.")
    print(f"AL onayi: {len(al_listesi)} | SAT onayi: {len(sat_listesi)}")

    al_listesi.sort(key=lambda x: x['hacim_kat'], reverse=True)
    sat_listesi.sort(key=lambda x: x['hacim_kat'], reverse=True)

    if al_listesi or sat_listesi:
        periyot_txt = "Günlük" if periyot == "gunluk" else "Haftalık"
        mesaj = f"🕯 <b>BIST Doji Onayli Donus ({periyot_txt})</b>\n"
        mesaj += f"Tarih: {datetime.now().strftime('%d.%m.%Y')}\n"
        mesaj += f"Dun Doji + Bugun Onay Bari\n\n"

        if al_listesi:
            mesaj += "🟢 <b>DONUS AL ONAYLANDI:</b>\n"
            for s in al_listesi:
                hacim_ikon = " 🔥" if s['hacim_guclu'] else ""
                mesaj += f"\n<b>{s['sembol']}</b> — {s['fiyat']} TL{hacim_ikon}\n"
                mesaj += f"  Dipte {s['tur']} + Yukselis Onayi\n"
                mesaj += f"  CE: {s['ce_yon']} | Hacim: {s['hacim_kat']}x\n"

        if sat_listesi:
            mesaj += "\n🔴 <b>DONUS SAT ONAYLANDI:</b>\n"
            for s in sat_listesi:
                hacim_ikon = " 🔥" if s['hacim_guclu'] else ""
                mesaj += f"\n<b>{s['sembol']}</b> — {s['fiyat']} TL{hacim_ikon}\n"
                mesaj += f"  Tepede {s['tur']} + Dusus Onayi\n"
                mesaj += f"  CE: {s['ce_yon']} | Hacim: {s['hacim_kat']}x\n"

        telegram_gonder(mesaj)
    else:
        print("Onaylanmis donus sinyali yok.")

if __name__ == "__main__":
    periyot = sys.argv[1] if len(sys.argv) > 1 else "gunluk"
    tarama(periyot)
