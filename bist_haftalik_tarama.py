#!/usr/bin/env python3
"""
BIST Haftalık CE + EMA200 + ADX Taraması
Günlük veriyi haftalık resample ile hesaplar — daha güvenilir
Her Cuma 18:00 TR'de çalışır
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
CE_MULT   = 2.0
EMA_LEN   = 200
ADX_LEN   = 14
ADX_ESIK  = 25
MIN_HAFTA = 210  # En az 210 haftalık veri (EMA200 için)

HISSE_LISTESI = [
    # BIST100
    "AEFES","AGHOL","AKBNK","AKSA","AKSEN","ALARK","ALFAS","ALTNY","ANSGR","ARCLK",
    "ASELS","ASTOR","BERA","BIENY","BIMAS","BRSAN","BRYAT","BTCIM","CANTE","CCOLA",
    "CIMSA","CWENE","DOAS","DOHOL","ECILC","ECZYT","EGEEN","EKGYO","ENERY","ENJSA",
    "ENKAI","EREGL","EUPWR","EUREN","FROTO","GARAN","GENIL","GESAN","GUBRF","HALKB",
    "HEKTS","ISCTR","KCHOL","KLKIM","KONTR","KOZAA","KOZAL","KRDMD","KTLEV","MGROS",
    "MPARK","ODAS","OTKAR","OYAKC","PETKM","PGSUS","SAHOL","SASA","SISE","SKBNK",
    "SOKM","TAVHL","TCELL","THYAO","TKFEN","TOASO","TSKB","TTKOM","TTRAK","TUPRS",
    "TURSG","ULKER","VAKBN","VESBE","VESTL","YKBNK","ZOREN",
    # Yıldız Pazar + Ana Pazar
    "ACSEL","ADEL","AKMGY","AKPO","AKSGY","AKTAE","ALBRK","ALGYO","ALKIM","ALTIN",
    "ANGEN","ANHYT","ASUZU","ATAKP","ATATP","AVGYO","AVHOL","AVOD","AYCES","AYEN",
    "BAGFS","BAKAB","BANVT","BARMA","BFREN","BINHO","BJKAS","BMELK","BNTAS","BOSSA",
    "BUCIM","BURCE","BURVA","BVSAN","CASA","CEMAS","CEMTS","CLEBI","CMBTN","CMENT",
    "CONSE","COSMO","CRDFA","CRFSA","CUSAN","DAGHL","DAPGM","DENGE","DERHL","DERIM",
    "DESA","DESPC","DEVA","DGATE","DGKLB","DGNMO","DMSAS","DNISI","DOBUR",
    "DOCO","DOGUB","DOKTA","DORE","DURDO","DYOBY","DZGYO","EBEBK","EGGUB",
    "EGPRO","EGSER","EMKEL","EMNIS","ERBOS","ERCB","ERSU","ESCAR","ESCOM","ESEN",
    "ETILR","ETYAT","EUHOL","EUKYO","FENER","FLAP","FMIZP","FONET","FORMT","FORTE",
    "FRIGO","GARFA","GEDIK","GEDZA","GENTS","GEREL","GLBMD","GLRYH",
    "GOLTS","GOODY","GOZDE","GRSEL","GRTHO","GSDDE","GSDHO","GSRAY","GWIND",
    "HATEK","HDFGS","HEDEF","HLGYO","HRKET","HTTBT","HUBVC","HUNER",
    "HURGZ","ICBCT","ICUGS","IDGYO","IEYHO","IHEVA","IHGZT","IHLAS","IHLGM","IHYAY",
    "IMASM","INDES","INFO","INTEM","IPEKE","ISATR","ISBIR","ISFIN","ISGSY",
    "ISGYO","ISMEN","ISSEN","ISYAT","ITTFH","IZFAS","IZMDC","JANTS","KAPLM","KARTN",
    "KATMR","KAYSE","KBORU","KCAER","KENT","KERVN","KERVT","KFEIN","KGYO",
    "KLMSN","KLRHO","KLSER","KMPUR","KNFRT","KONYA","KORDS",
    "KRDMA","KRDMB","KRGYO","KRPLS","KRSTL","KRTEK","KSTUR","KUTPO",
    "LIDER","LIDFA","LMKDC","LOGO","LUKSK","MAALT","MAGEN","MARTI","MAVI","MEDTR",
    "MEGAP","MEPET","MERKO","METRO","METUR","MIATK","MIPAZ","MMCAS","MNDRS",
    "MRGYO","NATEN","NETAS","NIBAS","NTGAZ","NUGYO","NUHCM","OBAMS","OBASE",
    "ONCSM","ORCAY","ORGE","ORMA","OSMEN","OSTIM","OYAKC","OYLUM",
    "OZGYO","OZKGY","PAGYO","PAHOL","PAMEL","PAPIL","PARSN","PASEU","PCILT","PEGYO",
    "PENTA","PINSU","PKENT","PLTUR","PNLSN","POLHO","PRKAB","PRKME",
    "PRZMA","RALYH","RAYSG","RHEAG","RODRG","ROYAL","RYGYO","RYSAS","SAFKR",
    "SANEL","SAYAS","SDTTR","SEGYO","SEKFK","SEKUR","SELEC","SEYKM",
    "SILVR","SKYLP","SMART","SMRTG","SNKRN","SONME","SRVGY",
    "TATGD","TLMAN","TMSN","TNZTP","TRCAS",
    "TRGYO","TRILC","TUCLK","TURGG","ULUUN","UMPAS","UNLU","USAK","USDTR",
    "VAKFN","VAKKO","VANGD","VBTYZ","VERUS","VKGYO","VKING",
    "YAPRK","YATAS","YEOTK","YGYO","YKSLN","YUNSA","ZRGYO"
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

def gunluk_haftalik_cevir(df):
    """Günlük veriyi haftalık OHLCV'ye çevir"""
    df.index = pd.to_datetime(df.index)
    weekly = df.resample('W').agg({
        'Open':   'first',
        'High':   'max',
        'Low':    'min',
        'Close':  'last',
        'Volume': 'sum'
    }).dropna()
    return weekly

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
    atr14    = tr.ewm(span=period, adjust=False).mean()
    di_plus  = pd.Series(plus_dm, index=df.index).ewm(span=period, adjust=False).mean() / atr14 * 100
    di_minus = pd.Series(minus_dm, index=df.index).ewm(span=period, adjust=False).mean() / atr14 * 100
    dx       = (abs(di_plus - di_minus) / (di_plus + di_minus) * 100).fillna(0)
    return dx.ewm(span=period, adjust=False).mean()

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

def hisse_analiz(sembol):
    try:
        ticker = yf.Ticker(f"{sembol}.IS")
        # Günlük veri çek — daha güvenilir
        df_gun = ticker.history(period="max", interval="1d")

        if df_gun is None or len(df_gun) < 300:
            return None

        # Haftalık veriye çevir
        df = gunluk_haftalik_cevir(df_gun)

        if len(df) < MIN_HAFTA:
            return None

        # Minimum haftalık hacim kontrolü
        if df['Volume'].iloc[-4:].mean() < 10000:
            return None

        ce_dir = ce_hesapla(df, CE_PERIOD, CE_MULT)
        adx    = adx_hesapla(df, ADX_LEN)
        ema200 = df['Close'].ewm(span=EMA_LEN, adjust=False).mean()

        curr_dir = ce_dir.iloc[-1]
        prev_dir = ce_dir.iloc[-2]
        fiyat    = df['Close'].iloc[-1]
        adx_val  = adx.iloc[-1]
        ema_val  = ema200.iloc[-1]

        yeni_al  = (curr_dir == -1 and prev_dir == 1)
        yeni_sat = (curr_dir == 1  and prev_dir == -1)

        ema_long  = fiyat > ema_val
        ema_short = fiyat < ema_val
        adx_guclu = adx_val > ADX_ESIK

        filtreli_al  = yeni_al  and ema_long  and adx_guclu
        filtreli_sat = yeni_sat and ema_short and adx_guclu

        if not (yeni_al or yeni_sat):
            return None

        return {
            'sembol':       sembol,
            'fiyat':        round(float(fiyat), 2),
            'yeni_al':      yeni_al,
            'yeni_sat':     yeni_sat,
            'filtreli_al':  filtreli_al,
            'filtreli_sat': filtreli_sat,
            'adx':          round(float(adx_val), 1),
            'ema200':       round(float(ema_val), 2),
            'ema_yon':      'UST' if ema_long else 'ALT',
        }
    except Exception as e:
        print(f"{sembol} hata: {e}")
        return None

def tarama():
    print(f"\n{'='*50}")
    print(f"BIST Haftalik CE Taramasi — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"Toplam hisse: {len(HISSE_LISTESI)}")
    print(f"{'='*50}")

    guclu_al  = []
    guclu_sat = []
    zayif_al  = []
    zayif_sat = []

    for i, sembol in enumerate(HISSE_LISTESI):
        print(f"[{i+1}/{len(HISSE_LISTESI)}] {sembol}...")
        sonuc = hisse_analiz(sembol)
        if sonuc is None:
            continue
        if sonuc['filtreli_al']:
            guclu_al.append(sonuc)
        elif sonuc['filtreli_sat']:
            guclu_sat.append(sonuc)
        elif sonuc['yeni_al']:
            zayif_al.append(sonuc)
        elif sonuc['yeni_sat']:
            zayif_sat.append(sonuc)

    print(f"\nTarama tamamlandi.")
    print(f"Guclu AL: {len(guclu_al)} | Guclu SAT: {len(guclu_sat)}")
    print(f"Zayif AL: {len(zayif_al)} | Zayif SAT: {len(zayif_sat)}")

    if guclu_al or guclu_sat or zayif_al or zayif_sat:
        mesaj = f"📊 <b>BIST Haftalik CE Sinyali</b>\n"
        mesaj += f"CE({CE_PERIOD},{CE_MULT}) | Haftalik | EMA{EMA_LEN}+ADX>{ADX_ESIK}\n"
        mesaj += f"Tarih: {datetime.now().strftime('%d.%m.%Y')} | {len(HISSE_LISTESI)} hisse\n\n"

        if guclu_al:
            mesaj += "🟢 <b>GUCLU AL (CE+EMA200+ADX):</b>\n"
            for s in guclu_al:
                mesaj += f"<b>{s['sembol']}</b> — {s['fiyat']} TL | EMA: {s['ema_yon']} | ADX: {s['adx']}\n"

        if guclu_sat:
            mesaj += "\n🔴 <b>GUCLU SAT (CE+EMA200+ADX):</b>\n"
            for s in guclu_sat:
                mesaj += f"<b>{s['sembol']}</b> — {s['fiyat']} TL | EMA: {s['ema_yon']} | ADX: {s['adx']}\n"

        if zayif_al:
            mesaj += "\n🟡 <b>ZAYIF AL (Sadece CE):</b>\n"
            for s in zayif_al:
                mesaj += f"{s['sembol']} — {s['fiyat']} TL | ADX: {s['adx']}\n"

        if zayif_sat:
            mesaj += "\n🟠 <b>ZAYIF SAT (Sadece CE):</b>\n"
            for s in zayif_sat:
                mesaj += f"{s['sembol']} — {s['fiyat']} TL | ADX: {s['adx']}\n"

        telegram_gonder(mesaj)
    else:
        print("Sinyal yok, bildirim gonderilmedi.")

    # Web app icin JSON kaydet
    if KAYIT_VAR:
        json_sinyaller = []
        for s in guclu_al:
            json_sinyaller.append({
                'sembol': s['sembol'], 'fiyat': s['fiyat'], 'yon': 'AL',
                'tur': 'GUCLU AL (CE+EMA200+ADX)',
                'detay': 'EMA: ' + s['ema_yon'] + ' | ADX: ' + str(s['adx'])
            })
        for s in guclu_sat:
            json_sinyaller.append({
                'sembol': s['sembol'], 'fiyat': s['fiyat'], 'yon': 'SAT',
                'tur': 'GUCLU SAT (CE+EMA200+ADX)',
                'detay': 'EMA: ' + s['ema_yon'] + ' | ADX: ' + str(s['adx'])
            })
        for s in zayif_al:
            json_sinyaller.append({
                'sembol': s['sembol'], 'fiyat': s['fiyat'], 'yon': 'AL',
                'tur': 'ZAYIF AL (Sadece CE)',
                'detay': 'ADX: ' + str(s['adx'])
            })
        for s in zayif_sat:
            json_sinyaller.append({
                'sembol': s['sembol'], 'fiyat': s['fiyat'], 'yon': 'SAT',
                'tur': 'ZAYIF SAT (Sadece CE)',
                'detay': 'ADX: ' + str(s['adx'])
            })
        sinyal_kaydet("haftalik_ce", json_sinyaller)

if __name__ == "__main__":
    tarama()
