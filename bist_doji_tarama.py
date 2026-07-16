#!/usr/bin/env python3
"""
BIST Doji Mumu Taraması — Dip/Tepe Filtreli
Sadece dipte veya tepede oluşan Doji'leri bildirir
- Dipte Dragonfly/Doji + CE → potansiyel dönüş (AL adayı)
- Tepede Mezartaşı/Doji + CE → potansiyel dönüş (SAT adayı)
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
DOJI_ESIK   = 0.1
DIP_TEPE_PER = 20    # Son 20 bar içinde dip/tepe kontrolü
DIP_TEPE_ORAN = 0.2  # En düşük/yüksek %20'lik dilim

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

def dip_tepe_kontrol(df, periyot=20, oran=0.2):
    """
    Fiyat son N barın neresinde?
    'DIP'  → en düşük %20'lik dilimde
    'TEPE' → en yüksek %20'lik dilimde
    None   → ortada
    """
    son_fiyat = df['Close'].iloc[-1]
    son_n     = df['Close'].iloc[-periyot:]
    en_dusuk  = son_n.min()
    en_yuksek = son_n.max()
    aralik    = en_yuksek - en_dusuk

    if aralik == 0:
        return None

    konum = (son_fiyat - en_dusuk) / aralik

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

        # Son bar Doji mi?
        son_bar = df.iloc[-1]
        if not doji_mu(son_bar):
            return None

        # Dip/tepe kontrolü — SADECE dip veya tepede olanlar geçer
        konum = dip_tepe_kontrol(df, DIP_TEPE_PER, DIP_TEPE_ORAN)
        if konum is None:
            return None

        tur   = doji_turu(son_bar)
        fiyat = round(float(son_bar['Close']), 2)

        ce_dir = ce_hesapla(df, CE_PERIOD, CE_MULT)
        ce_yon = ce_dir.iloc[-1]
        ce_str = "YUKARI" if ce_yon == -1 else "ASAGI"

        # Süper sinyal tespiti
        super_sinyal = False
        sinyal_tur   = ""

        # CE henüz dönmemişse sinyal anlamlı
        if konum == "DIP" and ce_yon == 1:  # dipte + CE hala aşağı
            if tur == "Dragonfly Doji":
                super_sinyal = True
                sinyal_tur   = "DIP DONUS (AL ADAYI)"
            else:
                sinyal_tur = "DIPTE DOJI"
        elif konum == "TEPE" and ce_yon == -1:  # tepede + CE hala yukarı
            if tur == "Mezartas Doji":
                super_sinyal = True
                sinyal_tur   = "TEPE DONUS (SAT ADAYI)"
            else:
                sinyal_tur = "TEPEDE DOJI"
        else:
            return None  # CE zaten dönmüş, sinyal geç
            
            
        
            
            
        
            
        
            

        son_hacim = df['Volume'].iloc[-1]
        ort_hacim = df['Volume'].iloc[-20:-1].mean()
        hacim_kat = round(son_hacim / ort_hacim, 1) if ort_hacim > 0 else 0

        return {
            'sembol':       sembol,
            'fiyat':        fiyat,
            'tur':          tur,
            'konum':        konum,
            'sinyal_tur':   sinyal_tur,
            'super_sinyal': super_sinyal,
            'ce_yon':       ce_str,
            'hacim_kat':    hacim_kat
        }

    except Exception as e:
        print(f"{sembol} hata: {e}")
        return None

def tarama(periyot="gunluk"):
    print(f"\n{'='*50}")
    print(f"BIST Doji Taramasi ({periyot.upper()}) — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"Sadece DIP/TEPE Doji'leri")
    print(f"{'='*50}")

    super_liste  = []
    normal_liste = []

    for i, sembol in enumerate(HISSE_LISTESI):
        print(f"[{i+1}/{len(HISSE_LISTESI)}] {sembol}...")
        sonuc = hisse_analiz(sembol, periyot)
        if sonuc is None:
            continue
        if sonuc['super_sinyal']:
            super_liste.append(sonuc)
        else:
            normal_liste.append(sonuc)

    print(f"\nTarama tamamlandi.")
    print(f"Super sinyal: {len(super_liste)} | Normal: {len(normal_liste)}")

    super_liste.sort(key=lambda x: x['hacim_kat'], reverse=True)
    normal_liste.sort(key=lambda x: x['hacim_kat'], reverse=True)

    if super_liste or normal_liste:
        periyot_txt = "Günlük" if periyot == "gunluk" else "Haftalık"
        mesaj = f"🕯 <b>BIST Dip/Tepe Doji ({periyot_txt})</b>\n"
        mesaj += f"Tarih: {datetime.now().strftime('%d.%m.%Y')}\n\n"

        if super_liste:
            mesaj += "⭐ <b>SUPER SINYAL (Donus Adayi):</b>\n"
            for s in super_liste:
                mesaj += f"\n<b>{s['sembol']}</b> — {s['fiyat']} TL\n"
                mesaj += f"  {s['sinyal_tur']}\n"
                mesaj += f"  {s['tur']} | CE: {s['ce_yon']} | Hacim: {s['hacim_kat']}x\n"

        if normal_liste:
            mesaj += "\n🟡 <b>Dip/Tepe Doji:</b>\n"
            for s in normal_liste:
                mesaj += f"{s['sembol']} — {s['fiyat']} TL | {s['konum']} | {s['tur']} | CE: {s['ce_yon']}\n"

        telegram_gonder(mesaj)
    else:
        print("Dip/tepe Doji bulunamadi.")

if __name__ == "__main__":
    periyot = sys.argv[1] if len(sys.argv) > 1 else "gunluk"
    tarama(periyot)
