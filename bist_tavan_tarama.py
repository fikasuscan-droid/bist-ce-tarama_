#!/usr/bin/env python3
"""
BIST Tavan Tarama + Performans Takibi
- Seansta tavan yapan hisseleri bulur (>= %9.5 artis)
- Hacim, EMA200, CE yonu ile birlikte kaydeder
- Onceki tavanlarin T+1, T+3, T+5 performansini gunceller
- Istatistik cikarir: tavan sonrasi ortalama getiri, basari orani
Her gun 18:20 TR'de calisir
"""

import yfinance as yf
import pandas as pd
import numpy as np
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
import json
import os

try:
    from sinyal_kaydet import sinyal_kaydet
    KAYIT_VAR = True
except ImportError:
    KAYIT_VAR = False

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

TAVAN_ESIK = 9.5      # BIST gunluk limit %10, 9.5 uzeri tavan sayilir
CE_PERIOD  = 5
CE_MULT    = 2.0
EMA_LEN    = 200
TAKIP_DOSYA = "docs/data/tavan_takip.json"   # kalici takip arsivi

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
            'chat_id': TELEGRAM_CHAT_ID, 'text': parca, 'parse_mode': 'HTML'
        }).encode()
        try:
            urllib.request.urlopen(url, data, timeout=10)
            print("Telegram bildirimi gonderildi")
        except Exception as e:
            print(f"Telegram hatasi: {e}")

def ce_hesapla(df, period=5, mult=2.0):
    high, low, close = df['High'], df['Low'], df['Close']
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low  - close.shift(1))
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    h_s, l_s, c_s = high.shift(1), low.shift(1), close.shift(1)
    hh = h_s.rolling(window=period).max()
    ll = l_s.rolling(window=period).min()
    long_stop  = hh - mult * atr
    short_stop = ll + mult * atr
    ce_dir = pd.Series(index=df.index, dtype=int)
    ce_dir.iloc[0] = 1
    for i in range(1, len(df)):
        c_prev, ls_prev, ss_prev = c_s.iloc[i], long_stop.iloc[i-1], short_stop.iloc[i-1]
        if pd.isna(c_prev) or pd.isna(ss_prev) or pd.isna(ls_prev):
            ce_dir.iloc[i] = ce_dir.iloc[i-1]
            continue
        if c_prev > ss_prev:   ce_dir.iloc[i] = -1
        elif c_prev < ls_prev: ce_dir.iloc[i] = 1
        else:                  ce_dir.iloc[i] = ce_dir.iloc[i-1]
    return ce_dir


def json_temizle(o):
    """numpy/pandas tiplerini Python tiplerine cevirir (JSON hatasi onlemi)."""
    import numpy as np
    if isinstance(o, dict):
        return {k: json_temizle(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [json_temizle(x) for x in o]
    if isinstance(o, (np.bool_, bool)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if hasattr(o, 'item'):
        try:
            return o.item()
        except Exception:
            return o
    return o

def takip_yukle():
    if os.path.exists(TAKIP_DOSYA):
        try:
            with open(TAKIP_DOSYA, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def takip_kaydet(kayitlar):
    os.makedirs(os.path.dirname(TAKIP_DOSYA), exist_ok=True)
    with open(TAKIP_DOSYA, 'w', encoding='utf-8') as f:
        json.dump(json_temizle(kayitlar), f, ensure_ascii=False, indent=1)

def hisse_tavan_kontrol(sembol):
    """Bugun tavan yapmis mi? Kalite bilgileriyle dondur."""
    try:
        t = yf.Ticker(f"{sembol}.IS")
        df = t.history(period="1y", interval="1d")
        if df is None or len(df) < 60:
            return None

        son_kap  = float(df['Close'].iloc[-1])
        onceki   = float(df['Close'].iloc[-2])
        degisim  = (son_kap - onceki) / onceki * 100

        if degisim < TAVAN_ESIK:
            return None

        # Kalite gostergeleri
        hacim     = float(df['Volume'].iloc[-1])
        ort_hacim = float(df['Volume'].iloc[-21:-1].mean())
        hacim_kat = float(round(hacim / ort_hacim, 1)) if ort_hacim > 0 else 0.0

        ema200 = df['Close'].ewm(span=EMA_LEN, adjust=False).mean()
        ema_v  = float(ema200.iloc[-1])
        ema_ust = bool(son_kap > ema_v)

        ce_dir  = ce_hesapla(df, CE_PERIOD, CE_MULT)
        ce_yuk  = bool(ce_dir.iloc[-1] == -1)

        # Kalite puani (0-3): hacim + EMA200 + CE
        puan = 0
        if hacim_kat >= 2.0: puan += 1
        if ema_ust:          puan += 1
        if ce_yuk:           puan += 1

        return {
            'sembol': sembol,
            'fiyat': round(son_kap, 2),
            'degisim': round(degisim, 2),
            'hacim_kat': hacim_kat,
            'ema200_ust': ema_ust,
            'ce_yukari': ce_yuk,
            'kalite': int(puan)
        }
    except Exception as e:
        print(f"{sembol} hata: {e}")
        return None

def performans_guncelle(kayitlar):
    """Onceki tavan kayitlarinin T+1/T+3/T+5 performansini gunceller."""
    # Guncellenecek kayitlari topla (henuz tum hedefleri dolmamis)
    guncellenecek = [k for k in kayitlar if not k.get('tamamlandi')]
    if not guncellenecek:
        return kayitlar

    semboller = list(set(k['sembol'] for k in guncellenecek))
    print(f"\nPerformans guncelleniyor: {len(semboller)} hisse, {len(guncellenecek)} kayit")

    fiyat_gecmisi = {}
    for s in semboller:
        try:
            df = yf.Ticker(f"{s}.IS").history(period="3mo", interval="1d")
            if df is not None and len(df):
                df.index = pd.to_datetime(df.index).tz_localize(None)
                fiyat_gecmisi[s] = df['Close']
        except Exception as e:
            print(f"{s} fiyat gecmisi hata: {e}")

    for k in guncellenecek:
        seri = fiyat_gecmisi.get(k['sembol'])
        if seri is None or seri.empty:
            continue
        try:
            tavan_tarih = pd.to_datetime(k['tarih'])
        except:
            continue

        # Tavan gununden sonraki islem gunleri
        sonrasi = seri[seri.index > tavan_tarih]
        baz = k['fiyat']

        for gun in [1, 3, 5]:
            anahtar = f"t{gun}"
            if anahtar in k and k[anahtar] is not None:
                continue
            if len(sonrasi) >= gun:
                fiyat = float(sonrasi.iloc[gun-1])
                k[anahtar] = round((fiyat - baz) / baz * 100, 2)

        # 5 gun dolduysa tamamlandi
        if k.get('t5') is not None:
            k['tamamlandi'] = True

    return kayitlar

def istatistik_cikar(kayitlar):
    """Tavan sonrasi performans istatistigi."""
    tamam = [k for k in kayitlar if k.get('t1') is not None]
    if not tamam:
        return None

    def ortalama(anahtar, liste):
        v = [k[anahtar] for k in liste if k.get(anahtar) is not None]
        return round(sum(v)/len(v), 2) if v else None

    def basari(anahtar, liste):
        v = [k[anahtar] for k in liste if k.get(anahtar) is not None]
        if not v: return None
        return round(len([x for x in v if x > 0]) / len(v) * 100, 1)

    ist = {
        'toplam_kayit': len(tamam),
        'genel': {
            't1_ort': ortalama('t1', tamam), 't1_basari': basari('t1', tamam),
            't3_ort': ortalama('t3', tamam), 't3_basari': basari('t3', tamam),
            't5_ort': ortalama('t5', tamam), 't5_basari': basari('t5', tamam),
        }
    }

    # Kalite puanina gore ayristir
    for p in [3, 2, 1, 0]:
        grup = [k for k in tamam if k.get('kalite') == p]
        if grup:
            ist[f'kalite_{p}'] = {
                'adet': len(grup),
                't1_ort': ortalama('t1', grup), 't1_basari': basari('t1', grup),
                't3_ort': ortalama('t3', grup), 't3_basari': basari('t3', grup),
                't5_ort': ortalama('t5', grup), 't5_basari': basari('t5', grup),
            }
    return ist

def tarama():
    print(f"\n{'='*50}")
    print(f"BIST Tavan Tarama - {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"Esik: %{TAVAN_ESIK}+ | {len(HISSE_LISTESI)} hisse")
    print(f"{'='*50}")

    kayitlar = takip_yukle()

    # 1) Once eski kayitlarin performansini guncelle
    kayitlar = performans_guncelle(kayitlar)

    # 2) Bugunun tavanlarini tara
    bugun = datetime.now().strftime("%Y-%m-%d")
    tavanlar = []
    for i, s in enumerate(HISSE_LISTESI):
        if (i + 1) % 25 == 0 or i == 0:
            print(f"[{i+1}/{len(HISSE_LISTESI)}] taraniyor...")
        r = hisse_tavan_kontrol(s)
        if r:
            tavanlar.append(r)
            print(f"  TAVAN: {r['sembol']} %{r['degisim']:+.2f} | kalite {r['kalite']}/3")

    tavanlar.sort(key=lambda x: (x['kalite'], x['hacim_kat']), reverse=True)
    print(f"\nBugun tavan yapan: {len(tavanlar)} hisse")

    # 3) Yeni tavanlari takip arsivine ekle (ayni gun tekrar eklenmesin)
    mevcut = {(k['sembol'], k['tarih']) for k in kayitlar}
    for t in tavanlar:
        if (t['sembol'], bugun) in mevcut:
            continue
        kayitlar.append({
            'sembol': t['sembol'], 'tarih': bugun, 'fiyat': t['fiyat'],
            'degisim': t['degisim'], 'hacim_kat': t['hacim_kat'],
            'ema200_ust': t['ema200_ust'], 'ce_yukari': t['ce_yukari'],
            'kalite': t['kalite'],
            't1': None, 't3': None, 't5': None, 'tamamlandi': False
        })

    # Arsivi sinirla (son 500)
    kayitlar = kayitlar[-500:]
    takip_kaydet(kayitlar)

    # 4) Istatistik
    ist = istatistik_cikar(kayitlar)
    if ist:
        os.makedirs("docs/data", exist_ok=True)
        with open("docs/data/tavan_istatistik.json", 'w', encoding='utf-8') as f:
            json.dump(json_temizle(ist), f, ensure_ascii=False, indent=1)
        print(f"\nIstatistik: {ist['toplam_kayit']} kayit uzerinden")
        g = ist['genel']
        print(f"  T+1: ort %{g['t1_ort']} | basari %{g['t1_basari']}")
        print(f"  T+3: ort %{g['t3_ort']} | basari %{g['t3_basari']}")
        print(f"  T+5: ort %{g['t5_ort']} | basari %{g['t5_basari']}")

    # 5) Telegram
    if tavanlar:
        mesaj = f"🔒 <b>BIST TAVAN LISTESI</b>\n"
        mesaj += f"Tarih: {datetime.now().strftime('%d.%m.%Y')} | {len(tavanlar)} hisse\n\n"

        guclu = [t for t in tavanlar if t['kalite'] >= 2]
        zayif = [t for t in tavanlar if t['kalite'] < 2]

        if guclu:
            mesaj += "🟢 <b>KALITELI TAVAN (2-3 puan):</b>\n"
            for t in guclu:
                ikonlar = ""
                if t['hacim_kat'] >= 2.0: ikonlar += "🔥"
                if t['ema200_ust']:       ikonlar += "📈"
                if t['ce_yukari']:        ikonlar += "✅"
                mesaj += f"<b>{t['sembol']}</b> {t['fiyat']} TL (%{t['degisim']:+.2f})\n"
                mesaj += f"  Hacim: {t['hacim_kat']}x | Puan: {t['kalite']}/3 {ikonlar}\n"

        if zayif:
            mesaj += f"\n🟡 <b>ZAYIF TAVAN (0-1 puan - dikkat!):</b> {len(zayif)} hisse\n"
            for t in zayif[:15]:
                mesaj += f"  {t['sembol']} {t['fiyat']} TL | Hacim: {t['hacim_kat']}x | Puan: {t['kalite']}/3\n"
            if len(zayif) > 15:
                mesaj += f"  ... ve {len(zayif)-15} hisse daha (app'te tamami)\n"

        if ist:
            g = ist['genel']
            mesaj += f"\n📊 <b>GECMIS ISTATISTIK</b> ({ist['toplam_kayit']} kayit)\n"
            mesaj += f"T+1: %{g['t1_ort']} (basari %{g['t1_basari']})\n"
            if g['t3_ort'] is not None:
                mesaj += f"T+3: %{g['t3_ort']} (basari %{g['t3_basari']})\n"
            if g['t5_ort'] is not None:
                mesaj += f"T+5: %{g['t5_ort']} (basari %{g['t5_basari']})\n"
            k3 = ist.get('kalite_3')
            if k3:
                mesaj += f"\n3/3 puanlilar T+1: %{k3['t1_ort']} (basari %{k3['t1_basari']}, {k3['adet']} kayit)\n"

        mesaj += "\n⚠️ Tavan sonrasi acilis bosluguna dikkat! Kaliteli olanlari CE/MTF ile teyit et."
        telegram_gonder(mesaj)
    else:
        print("Bugun tavan yapan hisse yok.")

    # 6) Web app icin guncel liste
    if KAYIT_VAR:
        json_sinyaller = []
        for t in tavanlar:
            detay = f"Hacim: {t['hacim_kat']}x | Puan: {t['kalite']}/3"
            if t['ema200_ust']: detay += " | EMA200 UST"
            if t['ce_yukari']:  detay += " | CE YUK"
            json_sinyaller.append({
                'sembol': t['sembol'], 'fiyat': t['fiyat'], 'yon': 'AL',
                'tur': f"TAVAN (%{t['degisim']:+.2f})",
                'detay': detay
            })
        sinyal_kaydet("tavan", json_sinyaller)

if __name__ == "__main__":
    tarama()
