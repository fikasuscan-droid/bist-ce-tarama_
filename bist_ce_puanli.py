#!/usr/bin/env python3
"""
BIST CE Sinyali + Puanlama Sistemi — GitHub Actions için
CE(5,2.0) + EMA200 + ADX + Hacim + Uyum puanlaması
BIST100 + Yıldız Pazar hisseleri
4-5 puan alan sinyaller Telegram'a gönderilir
"""

import yfinance as yf
import pandas as pd
import numpy as np
import urllib.request
import urllib.parse
from datetime import datetime
import json
import os

try:
    from sinyal_kaydet import sinyal_kaydet
    KAYIT_VAR = True
except ImportError:
    KAYIT_VAR = False

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

CE_PERIOD = 5
CE_MULT   = 2.0
EMA_LEN   = 200
ADX_LEN   = 14
MIN_PUAN  = 4  # minimum puan (0-5 arası)

STATE_FILE = "bist_ce_puanli_state.json"

HISSE_LISTESI = [
    "AEFES","AGHOL","AKBNK","AKSA","AKSEN","ALARK","ALFAS","ALTNY","ANSGR","ARCLK",
    "ASELS","ASTOR","BERA","BIENY","BIMAS","BRSAN","BRYAT","BTCIM","CANTE","CCOLA",
    "CIMSA","CWENE","DOAS","DOHOL","ECILC","ECZYT","EGEEN","EKGYO","ENERY","ENJSA",
    "ENKAI","EREGL","EUPWR","EUREN","FROTO","GARAN","GENIL","GESAN","GOLTS","GUBRF",
    "HALKB","HEKTS","ISCTR","IZMDC","KCHOL","KLKIM","KONTR","KORDS","KOZAA","KOZAL",
    "KRDMD","KTLEV","MAVI","MGROS","MPARK","NTGAZ","ODAS","OTKAR","OYAKC","PAHOL",
    "PETKM","PGSUS","SAHOL","SASA","SELEC","SISE","SKBNK","SOKM","TAVHL","TCELL",
    "THYAO","TKFEN","TOASO","TSKB","TTKOM","TTRAK","TUPRS","TURSG","ULKER","VAKBN",
    "VESBE","VESTL","YKBNK","ZOREN","DOCO","FORTE","KLRHO","CWENE","ENERY","ENJSA",
    "EKGYO","ASELS","AKBNK","THYAO","ENKAI","FROTO","EREGL","PETKM","KCHOL","GARAN"
]
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

def adx_hesapla(df, period=14):
    high  = df['High']
    low   = df['Low']
    close = df['Close']

    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low  - close.shift(1))
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    up_move   = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm  = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    atr14     = tr.ewm(span=period, adjust=False).mean()
    di_plus   = pd.Series(plus_dm,  index=df.index).ewm(span=period, adjust=False).mean() / atr14 * 100
    di_minus  = pd.Series(minus_dm, index=df.index).ewm(span=period, adjust=False).mean() / atr14 * 100

    dx  = (abs(di_plus - di_minus) / (di_plus + di_minus) * 100).fillna(0)
    adx = dx.ewm(span=period, adjust=False).mean()
    return adx

def ce_hesapla(df, period=5, mult=2.0):
    high  = df['High']
    low   = df['Low']
    close = df['Close']

    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low  - close.shift(1))
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    h_shifted = high.shift(1)
    l_shifted = low.shift(1)
    c_shifted = close.shift(1)

    highest_high = h_shifted.rolling(window=period).max()
    lowest_low   = l_shifted.rolling(window=period).min()

    long_stop  = highest_high - mult * atr
    short_stop = lowest_low   + mult * atr

    ce_dir = pd.Series(index=df.index, dtype=int)
    ce_dir.iloc[0] = 1

    for i in range(1, len(df)):
        c_prev  = c_shifted.iloc[i]
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

def puan_hesapla(df, ce_dir):
    """
    0-5 arası puanlama:
    1. EMA200 üzerinde mi? (LONG için) / altında mı? (SHORT için)
    2. ADX > 25 mi? (trend var)
    3. ADX > 35 mi? (güçlü trend)
    4. Hacim ortalamanın üzerinde mi?
    5. CE yönü EMA200 yönüyle uyumlu mu?
    """
    close   = df['Close']
    volume  = df['Volume']

    ema200  = close.ewm(span=EMA_LEN, adjust=False).mean()
    adx     = adx_hesapla(df, ADX_LEN)
    vol_avg = volume.rolling(20).mean()

    curr_dir  = ce_dir.iloc[-1]
    curr_ce   = ce_dir.iloc[-2]  # bir önceki bar
    fiyat     = close.iloc[-1]
    ema_val   = ema200.iloc[-1]
    adx_val   = adx.iloc[-1]
    vol_val   = volume.iloc[-1]
    vol_avg_v = vol_avg.iloc[-1]

    puan = 0
    detay = []

    # 1. EMA200 pozisyonu
    if curr_dir == -1 and fiyat > ema_val:  # LONG + EMA üstü
        puan += 1
        detay.append("EMA200 UST ✅")
    elif curr_dir == 1 and fiyat < ema_val:  # SHORT + EMA altı
        puan += 1
        detay.append("EMA200 ALT ✅")
    else:
        detay.append("EMA200 TERS ❌")

    # 2. ADX > 25
    if adx_val > 25:
        puan += 1
        detay.append(f"ADX>{25} ✅ ({adx_val:.1f})")
    else:
        detay.append(f"ADX<{25} ❌ ({adx_val:.1f})")

    # 3. ADX > 35
    if adx_val > 35:
        puan += 1
        detay.append("ADX>35 ✅")
    else:
        detay.append("ADX<35 ❌")

    # 4. Hacim
    if not pd.isna(vol_avg_v) and vol_val > vol_avg_v:
        puan += 1
        detay.append("HACIM YUK ✅")
    else:
        detay.append("HACIM DUS ❌")

    # 5. CE yönü EMA uyumu
    ema_trend = 1 if ema200.iloc[-1] > ema200.iloc[-5] else -1
    if curr_dir == ema_trend:
        puan += 1
        detay.append("EMA TREND UYUM ✅")
    else:
        detay.append("EMA TREND TERS ❌")

    return puan, adx_val, ema_val, detay

def hisse_sinyal(sembol):
    try:
        ticker = yf.Ticker(f"{sembol}.IS")
        df = ticker.history(period="2y", interval="1d")

        if df is None or len(df) < EMA_LEN + 10:
            return None

        ce_dir = ce_hesapla(df, CE_PERIOD, CE_MULT)

        curr_dir = ce_dir.iloc[-1]
        prev_dir = ce_dir.iloc[-2]
        fiyat    = df['Close'].iloc[-1]

        pozisyon = "LONG" if curr_dir == -1 else "SHORT"
        yeni_al  = (curr_dir == -1 and prev_dir == 1)
        yeni_sat = (curr_dir == 1  and prev_dir == -1)

        if not (yeni_al or yeni_sat):
            return None

        puan, adx_val, ema_val, detay = puan_hesapla(df, ce_dir)

        # ATR ile TP/SL
        tr = pd.concat([df['High']-df['Low'],
                        abs(df['High']-df['Close'].shift(1)),
                        abs(df['Low']-df['Close'].shift(1))], axis=1).max(axis=1)
        atr_v = tr.rolling(14).mean().iloc[-1]

        if pozisyon == "LONG":
            sl  = round(fiyat - atr_v * 1.5, 2)
            tp1 = round(fiyat + atr_v * 2.0, 2)
            tp2 = round(fiyat + atr_v * 3.5, 2)
        else:
            sl  = round(fiyat + atr_v * 1.5, 2)
            tp1 = round(fiyat - atr_v * 2.0, 2)
            tp2 = round(fiyat - atr_v * 3.5, 2)

        return {
            'sembol':   sembol,
            'fiyat':    round(float(fiyat), 2),
            'pozisyon': pozisyon,
            'puan':     puan,
            'adx':      round(adx_val, 1),
            'ema200':   round(ema_val, 2),
            'detay':    detay,
            'tp1': tp1, 'tp2': tp2, 'sl': sl
        }
    except Exception as e:
        print(f"{sembol} hata: {e}")
        return None

def tarama():
    print(f"\n{'='*50}")
    print(f"BIST CE Puanli Tarama — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"CE({CE_PERIOD},{CE_MULT}) | Gunluk | Min Puan: {MIN_PUAN}/5")
    print(f"{'='*50}")

    eski_durum = durum_yukle()
    yeni_durum = {}

    guclu_long  = []  # puan >= MIN_PUAN
    guclu_short = []
    zayif_long  = []  # puan < MIN_PUAN
    zayif_short = []

    for i, sembol in enumerate(HISSE_LISTESI):
        print(f"[{i+1}/{len(HISSE_LISTESI)}] {sembol} taraniyor...")
        sonuc = hisse_sinyal(sembol)

        if sonuc is None:
            continue

        yeni_durum[sembol] = sonuc['pozisyon']
        onceki = eski_durum.get(sembol)

        if onceki is not None and onceki != sonuc['pozisyon']:
            if sonuc['puan'] >= MIN_PUAN:
                if sonuc['pozisyon'] == 'LONG':
                    guclu_long.append(sonuc)
                else:
                    guclu_short.append(sonuc)
            else:
                if sonuc['pozisyon'] == 'LONG':
                    zayif_long.append(sonuc)
                else:
                    zayif_short.append(sonuc)

    durum_kaydet(yeni_durum)

    # Puana göre sırala
    guclu_long.sort(key=lambda x: x['puan'], reverse=True)
    guclu_short.sort(key=lambda x: x['puan'], reverse=True)

    print(f"\nTarama tamamlandi.")
    print(f"Guclu LONG  ({MIN_PUAN}+ puan): {len(guclu_long)}")
    print(f"Guclu SHORT ({MIN_PUAN}+ puan): {len(guclu_short)}")
    print(f"Zayif LONG  (<{MIN_PUAN} puan): {len(zayif_long)}")
    print(f"Zayif SHORT (<{MIN_PUAN} puan): {len(zayif_short)}")

    if guclu_long or guclu_short or zayif_long or zayif_short:
        mesaj = f"<b>BIST CE Puanli Sinyal</b>\n"
        mesaj += f"CE({CE_PERIOD},{CE_MULT}) | Gunluk\n"
        mesaj += f"Saat: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"

        if guclu_long:
            mesaj += f"🟢🟢 <b>GUCLU LONG ({MIN_PUAN}+ puan):</b>\n"
            for s in guclu_long:
                mesaj += f"\n<b>{s['sembol']}</b> — {s['fiyat']} TL | Puan: {s['puan']}/5\n"
                mesaj += f"  ADX: {s['adx']} | EMA200: {s['ema200']}\n"
                mesaj += f"  TP1: {s['tp1']} | TP2: {s['tp2']} | SL: {s['sl']}\n"

        if guclu_short:
            mesaj += f"\n🔴🔴 <b>GUCLU SHORT ({MIN_PUAN}+ puan):</b>\n"
            for s in guclu_short:
                mesaj += f"\n<b>{s['sembol']}</b> — {s['fiyat']} TL | Puan: {s['puan']}/5\n"
                mesaj += f"  ADX: {s['adx']} | EMA200: {s['ema200']}\n"
                mesaj += f"  TP1: {s['tp1']} | TP2: {s['tp2']} | SL: {s['sl']}\n"

        if zayif_long:
            mesaj += f"\n🟡 <b>ZAYIF LONG (<{MIN_PUAN} puan):</b>\n"
            for s in zayif_long:
                mesaj += f"  {s['sembol']} — {s['fiyat']} TL | Puan: {s['puan']}/5\n"

        if zayif_short:
            mesaj += f"\n🟠 <b>ZAYIF SHORT (<{MIN_PUAN} puan):</b>\n"
            for s in zayif_short:
                mesaj += f"  {s['sembol']} — {s['fiyat']} TL | Puan: {s['puan']}/5\n"

        telegram_gonder(mesaj)
    else:
        print("Sinyal yok, bildirim gonderilmedi.")

    # Web app icin JSON kaydet
    if KAYIT_VAR:
        json_sinyaller = []
        for s in guclu_long:
            json_sinyaller.append({
                'sembol': s['sembol'], 'fiyat': s['fiyat'], 'yon': 'AL',
                'tur': "GUCLU LONG " + str(s['puan']) + "/5 puan",
                'detay': "ADX: " + str(s['adx']) + " | EMA200: " + str(s['ema200']),
                'sl': s['sl'], 'tp1': s['tp1'], 'tp2': s['tp2']
            })
        for s in guclu_short:
            json_sinyaller.append({
                'sembol': s['sembol'], 'fiyat': s['fiyat'], 'yon': 'SAT',
                'tur': "GUCLU SHORT " + str(s['puan']) + "/5 puan",
                'detay': "ADX: " + str(s['adx']) + " | EMA200: " + str(s['ema200']),
                'sl': s['sl'], 'tp1': s['tp1'], 'tp2': s['tp2']
            })
        for s in zayif_long:
            json_sinyaller.append({
                'sembol': s['sembol'], 'fiyat': s['fiyat'], 'yon': 'AL',
                'tur': "ZAYIF LONG " + str(s['puan']) + "/5 puan", 'detay': ''
            })
        for s in zayif_short:
            json_sinyaller.append({
                'sembol': s['sembol'], 'fiyat': s['fiyat'], 'yon': 'SAT',
                'tur': "ZAYIF SHORT " + str(s['puan']) + "/5 puan", 'detay': ''
            })
        sinyal_kaydet("ce_puanli", json_sinyaller)

if __name__ == "__main__":
    tarama()
