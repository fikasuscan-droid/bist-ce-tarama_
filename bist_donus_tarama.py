#!/usr/bin/env python3
"""
BIST Donus Avcisi Tarama v2
TradingView Donus_Avcisi.pine ile BIREBIR AYNI mantik.
- Ayni pivot tespiti (5 sol/sag)
- Ayni son_bar_filtre (15)
- Ayni cift dip/tepe tolerans (%2)
- Ayni puanlama (mum+1, RSI div+2, cift+2, CE+1, hacim+1)
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

# ==== PARAMETRELER (Pine ile birebir ayni) ====
MIN_PUAN       = 3
PIVOT_BAR      = 5      # Pine: pivot_bar
SON_BAR_FILTRE = 15     # Pine: son_bar_filtre
CIFT_TOLERANS  = 2.0    # Pine: cift_tolerans (%)
VADI_MIN       = 3.0    # iki tepe/dip arasi min fiyat farki (%) - vadi/tepe belirginligi
TREND_MIN      = 2.0    # formasyon oncesi min trend hareketi (%)
RSI_LEN        = 14
CE_PERIOD      = 5
CE_MULT        = 2.0

HISSE_LISTESI = [
"AEFES","AGHOL","AKBNK","AKSA","AKSEN","ALARK","ALFAS","ALTNY","ANSGR","ARCLK",
    "ASELS","ASTOR","BERA","BIENY","BIMAS","BRSAN","BRYAT","BTCIM","CANTE","CCOLA",
    "CIMSA","CWENE","DOAS","DOHOL","ECILC","ECZYT","EGEEN","EKGYO","ENERY","ENJSA",
    "ENKAI","EREGL","EUPWR","EUREN","FROTO","GARAN","GENIL","GESAN","GUBRF","HALKB",
    "HEKTS","ISCTR","KCHOL","KLKIM","KONTR","KOZAA","KOZAL","KRDMD","KTLEV","MGROS",
    "MPARK","ODAS","OTKAR","OYAKC","PETKM","PGSUS","SAHOL","SASA","SISE","SKBNK",
    "SOKM","TAVHL","TCELL","THYAO","TKFEN","TOASO","TSKB","TTKOM","TTRAK","TUPRS",
    "TURSG","ULKER","VAKBN","VESBE","VESTL","YKBNK","ZOREN",
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
    "ONCSM","ORCAY","ORGE","ORMA","OSMEN","OSTIM","OYLUM",
    "OZGYO","OZKGY","PAGYO","PAHOL","PAMEL","PAPIL","PARSN","PASEU","PCILT","PEGYO",
    "PENTA","PINSU","PKENT","PLTUR","PNLSN","POLHO","PRKAB","PRKME",
    "PRZMA","RALYH","RAYSG","RHEAG","RODRG","ROYAL","RYGYO","RYSAS","SAFKR",
    "SANEL","SAYAS","SDTTR","SEGYO","SEKFK","SEKUR","SELEC","SEYKM",
    "SILVR","SKYLP","SMART","SMRTG","SNKRN","SONME","SRVGY",
    "TATGD","TLMAN","TMSN","TNZTP","TRCAS",
    "TRGYO","TRILC","TUCLK","TURGG","ULUUN","UMPAS","UNLU","USAK",
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
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0.0).rolling(period).mean()
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

def pivot_bul(seri, bar, tip):
    """
    Pine ta.pivothigh/pivotlow ile ayni mantik.
    Bir nokta, SOL ve SAG 'bar' kadar cevrede en dusuk/yuksekse pivottur.
    Pivot, olustugu bar_index ile birlikte dondurulur.
    Repaint'siz: pivot ancak sag tarafta 'bar' kadar veri olunca kesinlesir.
    """
    pivots = []  # (bar_index, deger)
    n = len(seri)
    for i in range(bar, n - bar):
        pencere = seri.iloc[i-bar : i+bar+1]
        if tip == 'dip' and seri.iloc[i] == pencere.min():
            pivots.append((i, float(seri.iloc[i])))
        elif tip == 'tepe' and seri.iloc[i] == pencere.max():
            pivots.append((i, float(seri.iloc[i])))
    return pivots

def analiz(sembol):
    try:
        df = yf.Ticker(f"{sembol}.IS").history(period="1y", interval="1d")
        if df is None or len(df) < 60:
            return None

        # NaN temizligi - bozuk barlari at (yfinance BIST'te bazen NaN dondurur)
        df = df.dropna(subset=['Open','High','Low','Close'])
        if len(df) < 60:
            return None
        # Son bar fiyati gecerli mi kontrol
        if pd.isna(df['Close'].iloc[-1]) or df['Close'].iloc[-1] <= 0:
            return None

        close = df['Close']; high = df['High']; low = df['Low']; openp = df['Open']; vol = df['Volume']
        # Hacim NaN'lari 0 yap (hesap bozulmasin)
        vol = vol.fillna(0)
        son_bar = len(df) - 1
        rsi = rsi_hesapla(close, RSI_LEN)

        # ---- KATMAN 1: MUM (son bar) ----
        govde = abs(close.iloc[-1] - openp.iloc[-1])
        ust_fitil = high.iloc[-1] - max(close.iloc[-1], openp.iloc[-1])
        alt_fitil = min(close.iloc[-1], openp.iloc[-1]) - low.iloc[-1]
        cekic = alt_fitil > govde*2 and ust_fitil < govde*0.5 and govde > 0
        ters_cekic = ust_fitil > govde*2 and alt_fitil < govde*0.5 and govde > 0
        yutan_boga = close.iloc[-1] > openp.iloc[-1] and close.iloc[-2] < openp.iloc[-2] and close.iloc[-1] > openp.iloc[-2] and openp.iloc[-1] < close.iloc[-2]
        yutan_ayi = close.iloc[-1] < openp.iloc[-1] and close.iloc[-2] > openp.iloc[-2] and close.iloc[-1] < openp.iloc[-2] and openp.iloc[-1] > close.iloc[-2]
        mum_al = bool(cekic or yutan_boga)
        mum_sat = bool(ters_cekic or yutan_ayi)

        # ---- PIVOTLAR (Pine ile ayni) ----
        dipler = pivot_bul(low, PIVOT_BAR, 'dip')
        tepeler = pivot_bul(high, PIVOT_BAR, 'tepe')

        boga_div = ayi_div = cift_dip = cift_tepe = False

        # ---- KATMAN 2 & 3: DIP tarafi ----
        if len(dipler) >= 2:
            (i_onceki, f_onceki) = dipler[-2]
            (i_son, f_son) = dipler[-1]
            dip_taze = (son_bar - i_son) <= SON_BAR_FILTRE
            yeterli_mesafe = (i_son - i_onceki) >= PIVOT_BAR * 2
            if dip_taze:
                # RSI diverjansi
                if f_son < f_onceki and rsi.iloc[i_son] > rsi.iloc[i_onceki]:
                    boga_div = True
                # Cift dip: tolerans + mesafe + VADI (aralarinda belirgin tepe) + TREND (once dusus)
                if yeterli_mesafe and abs(f_son - f_onceki) / f_onceki * 100 < CIFT_TOLERANS:
                    # Vadi: iki dip arasindaki en yuksek nokta, diplerden %VADI_MIN yukarida olmali
                    ara_tepe = high.iloc[i_onceki:i_son+1].max()
                    vadi_ok = (ara_tepe - max(f_son, f_onceki)) / max(f_son, f_onceki) * 100 >= VADI_MIN
                    # Trend: ilk dipten once dusus olmali (formasyon dusus sonrasi)
                    onceki_pencere = close.iloc[max(0, i_onceki-10):i_onceki]
                    trend_ok = len(onceki_pencere) > 0 and (onceki_pencere.iloc[0] - f_onceki) / f_onceki * 100 >= TREND_MIN
                    if vadi_ok and trend_ok:
                        cift_dip = True

        # ---- KATMAN 2 & 3: TEPE tarafi ----
        if len(tepeler) >= 2:
            (i_onceki, f_onceki) = tepeler[-2]
            (i_son, f_son) = tepeler[-1]
            tepe_taze = (son_bar - i_son) <= SON_BAR_FILTRE
            yeterli_mesafe = (i_son - i_onceki) >= PIVOT_BAR * 2
            if tepe_taze:
                if f_son > f_onceki and rsi.iloc[i_son] < rsi.iloc[i_onceki]:
                    ayi_div = True
                if yeterli_mesafe and abs(f_son - f_onceki) / f_onceki * 100 < CIFT_TOLERANS:
                    # Vadi: iki tepe arasindaki en dusuk nokta, tepelerden %VADI_MIN asagida olmali
                    ara_dip = low.iloc[i_onceki:i_son+1].min()
                    vadi_ok = (min(f_son, f_onceki) - ara_dip) / ara_dip * 100 >= VADI_MIN
                    # Trend: ilk tepeden once yukselis olmali
                    onceki_pencere = close.iloc[max(0, i_onceki-10):i_onceki]
                    trend_ok = len(onceki_pencere) > 0 and (f_onceki - onceki_pencere.iloc[0]) / onceki_pencere.iloc[0] * 100 >= TREND_MIN
                    if vadi_ok and trend_ok:
                        cift_tepe = True

        # ---- KATMAN 4: CE ----
        ce = ce_yon(df, CE_PERIOD, CE_MULT)
        ce_al = bool(ce.iloc[-1] == 1 and ce.iloc[-2] == -1)
        ce_sat = bool(ce.iloc[-1] == -1 and ce.iloc[-2] == 1)

        # ---- HACIM ----
        hacim_ort = vol.iloc[-21:-1].mean()
        hacim_yuksek = bool(vol.iloc[-1] > hacim_ort * 1.5)

        # ---- PUANLAMA (Pine ile birebir) ----
        puan_al = (1 if mum_al else 0) + (2 if boga_div else 0) + (2 if cift_dip else 0) + (1 if ce_al else 0) + (1 if hacim_yuksek else 0)
        puan_sat = (1 if mum_sat else 0) + (2 if ayi_div else 0) + (2 if cift_tepe else 0) + (1 if ce_sat else 0) + (1 if hacim_yuksek else 0)

        # Fiyat gecerli degilse sinyal verme
        son_fiyat = float(close.iloc[-1])
        if pd.isna(son_fiyat) or son_fiyat <= 0:
            return None

        if puan_al >= MIN_PUAN and puan_al >= puan_sat:
            detay = []
            if mum_al: detay.append("Mum")
            if boga_div: detay.append("Diverjans")
            if cift_dip: detay.append("CiftDip")
            if ce_al: detay.append("CE")
            if hacim_yuksek: detay.append("Hacim")
            return {'sembol':sembol,'yon':'AL','tur':'DIP DONUS','puan':int(puan_al),
                    'fiyat':round(float(close.iloc[-1]),2),'detay':" + ".join(detay)}
        elif puan_sat >= MIN_PUAN and puan_sat > puan_al:
            detay = []
            if mum_sat: detay.append("Mum")
            if ayi_div: detay.append("Diverjans")
            if cift_tepe: detay.append("CiftTepe")
            if ce_sat: detay.append("CE")
            if hacim_yuksek: detay.append("Hacim")
            return {'sembol':sembol,'yon':'SAT','tur':'TEPE DONUS','puan':int(puan_sat),
                    'fiyat':round(float(close.iloc[-1]),2),'detay':" + ".join(detay)}
        return None
    except Exception as e:
        print(f"{sembol} hata: {e}")
        return None

def tarama():
    print(f"\n{'='*50}")
    print(f"Donus Avcisi v2 - {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"Min puan: {MIN_PUAN} | Pivot: {PIVOT_BAR} | Filtre: {SON_BAR_FILTRE} bar | {len(HISSE_LISTESI)} hisse")
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
