#!/usr/bin/env python3
"""
BIST Donus Avcisi Tarama
Coklu onayli donus tespiti: Mum + RSI diverjansi + Cift dip/tepe + CE + Hacim
Her onay puan verir, yuksek puanli donusler sinyal olur.
Gunluk periyot. Her aksam 18:25 TR.
"""
import yfinance as yf
import pandas as pd
import numpy as np
import urllib.request, urllib.parse
from datetime import datetime
import json, os

try:
    from sinyal_kaydet import sinyal_kaydet
    KAYIT_VAR = True
except ImportError:
    KAYIT_VAR = False

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

MIN_PUAN = 3
RSI_LEN = 14
CE_PERIOD = 5
CE_MULT = 2.0
PIVOT = 5

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
        print("Telegram eksik"); return
    for p in [mesaj[i:i+4000] for i in range(0, len(mesaj), 4000)]:
        try:
            urllib.request.urlopen(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                urllib.parse.urlencode({'chat_id':TELEGRAM_CHAT_ID,'text':p,'parse_mode':'HTML'}).encode(), timeout=10)
            print("Telegram gonderildi")
        except Exception as e:
            print(f"Telegram hata: {e}")

def rsi_hesapla(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def ce_yon(df, period=5, mult=2.0):
    high, low, close = df['High'], df['Low'], df['Close']
    tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    hh = high.rolling(period).max()
    ll = low.rolling(period).min()
    ls = hh - mult*atr
    ss = ll + mult*atr
    d = pd.Series(1, index=df.index)
    for i in range(1, len(df)):
        if pd.isna(ss.iloc[i-1]) or pd.isna(ls.iloc[i-1]):
            d.iloc[i] = d.iloc[i-1]; continue
        if close.iloc[i] > ss.iloc[i-1]: d.iloc[i] = 1
        elif close.iloc[i] < ls.iloc[i-1]: d.iloc[i] = -1
        else: d.iloc[i] = d.iloc[i-1]
    return d

def pivotlar(seri, sol, sag, tip):
    """Basit pivot tespit: tip='dip' veya 'tepe'. Son pivotlari dondur."""
    pivots = []
    for i in range(sol, len(seri)-sag):
        pencere = seri.iloc[i-sol:i+sag+1]
        if tip == 'dip' and seri.iloc[i] == pencere.min():
            pivots.append((i, seri.iloc[i]))
        elif tip == 'tepe' and seri.iloc[i] == pencere.max():
            pivots.append((i, seri.iloc[i]))
    return pivots

def analiz(sembol):
    try:
        df = yf.Ticker(f"{sembol}.IS").history(period="1y", interval="1d")
        if df is None or len(df) < 60:
            return None

        close = df['Close']; high = df['High']; low = df['Low']
        openp = df['Open']; vol = df['Volume']
        son = len(df) - 1

        # Mum formasyonu (son bar)
        govde = abs(close.iloc[-1] - openp.iloc[-1])
        ust_fitil = high.iloc[-1] - max(close.iloc[-1], openp.iloc[-1])
        alt_fitil = min(close.iloc[-1], openp.iloc[-1]) - low.iloc[-1]
        cekic = alt_fitil > govde*2 and ust_fitil < govde*0.5 and govde > 0
        ters_cekic = ust_fitil > govde*2 and alt_fitil < govde*0.5 and govde > 0
        yutan_boga = close.iloc[-1] > openp.iloc[-1] and close.iloc[-2] < openp.iloc[-2] and close.iloc[-1] > openp.iloc[-2] and openp.iloc[-1] < close.iloc[-2]
        yutan_ayi = close.iloc[-1] < openp.iloc[-1] and close.iloc[-2] > openp.iloc[-2] and close.iloc[-1] < openp.iloc[-2] and openp.iloc[-1] > close.iloc[-2]
        mum_al = bool(cekic or yutan_boga)
        mum_sat = bool(ters_cekic or yutan_ayi)

        # RSI diverjansi
        rsi = rsi_hesapla(close, RSI_LEN)
        dipler = pivotlar(low, PIVOT, PIVOT, 'dip')
        tepeler = pivotlar(high, PIVOT, PIVOT, 'tepe')
        boga_div = False; ayi_div = False
        cift_dip = False; cift_tepe = False

        if len(dipler) >= 2:
            (i1,f1),(i2,f2) = dipler[-2], dipler[-1]
            # sadece son pivot yakin zamandaysa (son 15 bar)
            if son - i2 <= 15:
                if f2 < f1 and rsi.iloc[i2] > rsi.iloc[i1]:
                    boga_div = True
                if abs(f2-f1)/f1 < 0.02:
                    cift_dip = True

        if len(tepeler) >= 2:
            (i1,f1),(i2,f2) = tepeler[-2], tepeler[-1]
            if son - i2 <= 15:
                if f2 > f1 and rsi.iloc[i2] < rsi.iloc[i1]:
                    ayi_div = True
                if abs(f2-f1)/f1 < 0.02:
                    cift_tepe = True

        # CE
        ce = ce_yon(df, CE_PERIOD, CE_MULT)
        ce_al = bool(ce.iloc[-1] == 1 and ce.iloc[-2] == -1)
        ce_sat = bool(ce.iloc[-1] == -1 and ce.iloc[-2] == 1)

        # Hacim
        hacim_ort = vol.iloc[-21:-1].mean()
        hacim_yuksek = bool(vol.iloc[-1] > hacim_ort * 1.5)

        # Puanlama
        puan_al = (1 if mum_al else 0) + (2 if boga_div else 0) + (2 if cift_dip else 0) + (1 if ce_al else 0) + (1 if hacim_yuksek else 0)
        puan_sat = (1 if mum_sat else 0) + (2 if ayi_div else 0) + (2 if cift_tepe else 0) + (1 if ce_sat else 0) + (1 if hacim_yuksek else 0)

        if puan_al >= MIN_PUAN and puan_al >= puan_sat:
            detay = []
            if mum_al: detay.append("Mum")
            if boga_div: detay.append("Diverjans")
            if cift_dip: detay.append("CiftDip")
            if ce_al: detay.append("CE")
            if hacim_yuksek: detay.append("Hacim")
            return {'sembol': sembol, 'yon': 'AL', 'tur': 'DIP DONUS',
                    'puan': int(puan_al), 'fiyat': round(float(close.iloc[-1]),2),
                    'detay': " + ".join(detay)}
        elif puan_sat >= MIN_PUAN and puan_sat > puan_al:
            detay = []
            if mum_sat: detay.append("Mum")
            if ayi_div: detay.append("Diverjans")
            if cift_tepe: detay.append("CiftTepe")
            if ce_sat: detay.append("CE")
            if hacim_yuksek: detay.append("Hacim")
            return {'sembol': sembol, 'yon': 'SAT', 'tur': 'TEPE DONUS',
                    'puan': int(puan_sat), 'fiyat': round(float(close.iloc[-1]),2),
                    'detay': " + ".join(detay)}
        return None
    except Exception as e:
        print(f"{sembol} hata: {e}")
        return None

def tarama():
    print(f"\n{'='*50}")
    print(f"Donus Avcisi Tarama - {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"Min puan: {MIN_PUAN} | {len(HISSE_LISTESI)} hisse")
    print(f"{'='*50}")

    sonuclar = []
    for i, s in enumerate(HISSE_LISTESI):
        if (i+1) % 25 == 0:
            print(f"[{i+1}/{len(HISSE_LISTESI)}]...")
        r = analiz(s)
        if r:
            sonuclar.append(r)
            print(f"  {r['tur']}: {r['sembol']} {r['puan']}/6 | {r['detay']}")

    sonuclar.sort(key=lambda x: x['puan'], reverse=True)
    dipler = [x for x in sonuclar if x['yon']=='AL']
    tepeler = [x for x in sonuclar if x['yon']=='SAT']

    print(f"\nToplam: {len(sonuclar)} donus ({len(dipler)} dip, {len(tepeler)} tepe)")

    if sonuclar:
        mesaj = f"🔄 <b>DONUS AVCISI</b>\n{datetime.now().strftime('%d.%m.%Y')} | {len(sonuclar)} sinyal\n\n"
        if dipler:
            mesaj += "🟢 <b>DIP DONUSLERI (AL):</b>\n"
            for d in dipler:
                mesaj += f"<b>{d['sembol']}</b> {d['fiyat']} TL | {d['puan']}/6\n  {d['detay']}\n"
        if tepeler:
            mesaj += "\n🔴 <b>TEPE DONUSLERI (SAT):</b>\n"
            for t in tepeler:
                mesaj += f"<b>{t['sembol']}</b> {t['fiyat']} TL | {t['puan']}/6\n  {t['detay']}\n"
        mesaj += "\n⚠️ Yuksek puan = cok katmanli onay. 5-6/6 en guclu. MTF ile teyit et."
        telegram_gonder(mesaj)
    else:
        print("Donus sinyali yok.")

    if KAYIT_VAR:
        js = [{'sembol':x['sembol'],'fiyat':x['fiyat'],'yon':x['yon'],
               'tur':f"{x['tur']} ({x['puan']}/6)",'detay':x['detay']} for x in sonuclar]
        sinyal_kaydet("donus", js)

if __name__ == "__main__":
    tarama()
