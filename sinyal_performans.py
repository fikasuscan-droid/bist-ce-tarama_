#!/usr/bin/env python3
"""
Sinyal Performans Takibi
- docs/data/gecmis.json icindeki tum sinyalleri okur
- Her sinyalin T+1, T+3, T+5 getirisini hesaplar
- Sistem bazli istatistik uretir (ortalama getiri + basari orani)
- Sonuc: docs/data/performans.json
Her gun 18:30 TR'de calisir (diger taramalardan sonra)
"""

import yfinance as yf
import pandas as pd
import urllib.request
import urllib.parse
from datetime import datetime
import json
import os

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

GECMIS_DOSYA     = "docs/data/gecmis.json"
PERFORMANS_DOSYA = "docs/data/performans.json"
ARSIV_DOSYA      = "docs/data/performans_arsiv.json"   # hesaplanan sinyaller

SISTEM_ADLARI = {
    'doji_gunluk':   'Doji Gunluk',
    'doji_haftalik': 'Doji Haftalik',
    'ce_puanli':     'CE Puanli',
    'aksam_al':      'Aksam Al',
    'haftalik_ce':   'Haftalik CE',
    'tavan':         'Tavan',
}

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
            print("Telegram gonderildi")
        except Exception as e:
            print(f"Telegram hatasi: {e}")

def json_yukle(yol, varsayilan):
    if os.path.exists(yol):
        try:
            with open(yol, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return varsayilan
    return varsayilan

def json_kaydet(yol, veri):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, 'w', encoding='utf-8') as f:
        json.dump(veri, f, ensure_ascii=False, indent=1)

def arsiv_anahtar(s):
    """Sinyali benzersiz tanimlayan anahtar."""
    return f"{s.get('sistem','')}|{s.get('sembol','')}|{s.get('tarih','')}|{s.get('yon','')}"

def performans_hesapla():
    print(f"\n{'='*50}")
    print(f"Sinyal Performans Takibi - {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"{'='*50}")

    gecmis = json_yukle(GECMIS_DOSYA, [])
    if not gecmis:
        print("gecmis.json bos veya yok - once taramalarin calismasi gerekiyor")
        return

    arsiv = json_yukle(ARSIV_DOSYA, [])
    arsiv_index = {arsiv_anahtar(a): a for a in arsiv}

    print(f"Gecmis sinyal sayisi: {len(gecmis)}")
    print(f"Arsivdeki kayit: {len(arsiv)}")

    # Yeni veya tamamlanmamis sinyalleri belirle
    islenecek = []
    for s in gecmis:
        if not s.get('sembol') or not s.get('tarih') or not s.get('fiyat'):
            continue
        k = arsiv_anahtar(s)
        mevcut = arsiv_index.get(k)
        if mevcut is None:
            # yeni kayit
            yeni = {
                'sistem': s.get('sistem',''), 'sembol': s['sembol'],
                'tarih': s['tarih'], 'yon': s.get('yon','AL'),
                'fiyat': s['fiyat'],
                't1': None, 't3': None, 't5': None, 'tamamlandi': False
            }
            arsiv.append(yeni)
            arsiv_index[k] = yeni
            islenecek.append(yeni)
        elif not mevcut.get('tamamlandi'):
            islenecek.append(mevcut)

    if not islenecek:
        print("Guncellenecek sinyal yok")
    else:
        print(f"Guncellenecek: {len(islenecek)} sinyal")

        # Fiyat gecmislerini topluca cek
        semboller = sorted(set(x['sembol'] for x in islenecek))
        print(f"Fiyat verisi cekiliyor: {len(semboller)} sembol")
        fiyatlar = {}
        for i, sem in enumerate(semboller):
            try:
                df = yf.Ticker(f"{sem}.IS").history(period="6mo", interval="1d")
                if df is not None and len(df):
                    df.index = pd.to_datetime(df.index).tz_localize(None)
                    fiyatlar[sem] = df['Close']
            except Exception as e:
                print(f"  {sem} hata: {e}")
            if (i+1) % 25 == 0:
                print(f"  {i+1}/{len(semboller)}")

        # Getirileri hesapla
        for kayit in islenecek:
            seri = fiyatlar.get(kayit['sembol'])
            if seri is None or seri.empty:
                continue
            try:
                sinyal_tarih = pd.to_datetime(kayit['tarih'])
            except:
                continue

            sonrasi = seri[seri.index > sinyal_tarih]
            baz = kayit['fiyat']
            if not baz or baz <= 0:
                continue

            # SAT sinyalinde getiri ters isaretli (dususten kazanc)
            yon_carpan = -1 if str(kayit.get('yon','')).upper().startswith('SAT') else 1

            for gun in [1, 3, 5]:
                anahtar = f"t{gun}"
                if kayit.get(anahtar) is not None:
                    continue
                if len(sonrasi) >= gun:
                    f = float(sonrasi.iloc[gun-1])
                    kayit[anahtar] = round((f - baz) / baz * 100 * yon_carpan, 2)

            if kayit.get('t5') is not None:
                kayit['tamamlandi'] = True

    # Arsivi sinirla
    arsiv = arsiv[-2000:]
    json_kaydet(ARSIV_DOSYA, arsiv)

    # ===== ISTATISTIK =====
    def ort(anahtar, liste):
        v = [x[anahtar] for x in liste if x.get(anahtar) is not None]
        return round(sum(v)/len(v), 2) if v else None

    def basari(anahtar, liste):
        v = [x[anahtar] for x in liste if x.get(anahtar) is not None]
        if not v: return None
        return round(len([y for y in v if y > 0]) / len(v) * 100, 1)

    def adet(anahtar, liste):
        return len([x for x in liste if x.get(anahtar) is not None])

    olculebilir = [a for a in arsiv if a.get('t1') is not None]
    istatistik = {
        'guncelleme': datetime.now().strftime("%Y-%m-%d %H:%M"),
        'toplam_sinyal': len(arsiv),
        'olculen': len(olculebilir),
        'sistemler': {}
    }

    for kod, ad in SISTEM_ADLARI.items():
        grup = [a for a in olculebilir if a.get('sistem') == kod]
        if not grup:
            continue
        istatistik['sistemler'][kod] = {
            'ad': ad,
            'adet': len(grup),
            't1_ort': ort('t1', grup), 't1_basari': basari('t1', grup), 't1_adet': adet('t1', grup),
            't3_ort': ort('t3', grup), 't3_basari': basari('t3', grup), 't3_adet': adet('t3', grup),
            't5_ort': ort('t5', grup), 't5_basari': basari('t5', grup), 't5_adet': adet('t5', grup),
        }

    # Genel
    if olculebilir:
        istatistik['genel'] = {
            't1_ort': ort('t1', olculebilir), 't1_basari': basari('t1', olculebilir),
            't3_ort': ort('t3', olculebilir), 't3_basari': basari('t3', olculebilir),
            't5_ort': ort('t5', olculebilir), 't5_basari': basari('t5', olculebilir),
        }

    json_kaydet(PERFORMANS_DOSYA, istatistik)

    # ===== RAPOR =====
    print(f"\nOlculen sinyal: {len(olculebilir)}")
    if not istatistik['sistemler']:
        print("Henuz istatistik cikacak kadar veri yok (en az 1 gun beklemeli)")
        return

    for kod, d in istatistik['sistemler'].items():
        print(f"\n{d['ad']} ({d['adet']} sinyal)")
        print(f"  T+1: %{d['t1_ort']} | basari %{d['t1_basari']} ({d['t1_adet']} kayit)")
        if d['t3_ort'] is not None:
            print(f"  T+3: %{d['t3_ort']} | basari %{d['t3_basari']} ({d['t3_adet']} kayit)")
        if d['t5_ort'] is not None:
            print(f"  T+5: %{d['t5_ort']} | basari %{d['t5_basari']} ({d['t5_adet']} kayit)")

    # Telegram - haftada bir (Cuma) ozet gonder
    bugun_cuma = datetime.now().weekday() == 4
    if bugun_cuma and istatistik['sistemler']:
        mesaj = "📊 <b>HAFTALIK SISTEM PERFORMANSI</b>\n"
        mesaj += f"Olculen sinyal: {len(olculebilir)}\n\n"

        # T+5 ortalamasina gore sirala (yoksa T+1)
        sirali = sorted(istatistik['sistemler'].values(),
                        key=lambda d: (d['t5_ort'] if d['t5_ort'] is not None else d['t1_ort'] or -99),
                        reverse=True)
        for d in sirali:
            mesaj += f"<b>{d['ad']}</b> ({d['adet']} sinyal)\n"
            mesaj += f"  T+1: %{d['t1_ort']} (basari %{d['t1_basari']})\n"
            if d['t3_ort'] is not None:
                mesaj += f"  T+3: %{d['t3_ort']} (basari %{d['t3_basari']})\n"
            if d['t5_ort'] is not None:
                mesaj += f"  T+5: %{d['t5_ort']} (basari %{d['t5_basari']})\n"
            mesaj += "\n"

        g = istatistik.get('genel')
        if g:
            mesaj += f"<b>GENEL</b>\nT+1: %{g['t1_ort']} (basari %{g['t1_basari']})"
            if g['t5_ort'] is not None:
                mesaj += f" | T+5: %{g['t5_ort']} (basari %{g['t5_basari']})"
            mesaj += "\n"

        mesaj += "\n⚠️ Az sayida kayitla cikan sonuclar yaniltici olabilir. En az 20-30 sinyal biriktikten sonra guvenilir olur."
        telegram_gonder(mesaj)

if __name__ == "__main__":
    performans_hesapla()
