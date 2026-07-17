#!/usr/bin/env python3
"""
Sinyal Kayıt Modülü
Her tarama scripti bunu import edip sinyallerini JSON'a kaydeder.
Web app bu JSON'ları okur.

Kullanım (tarama scriptlerine eklenecek):
    from sinyal_kaydet import sinyal_kaydet
    sinyal_kaydet("doji_gunluk", [{...}, {...}])
"""

import json
import os
from datetime import datetime

SINYAL_DIR = "docs/data"

def sinyal_kaydet(sistem_adi, sinyaller):
    """
    sistem_adi: 'doji_gunluk', 'doji_haftalik', 'ce_puanli', 'aksam_al', 'haftalik_ce', 'ce_v2'
    sinyaller: liste — her sinyal dict olmalı:
        {
            'sembol': 'AKBNK',
            'fiyat': 82.50,
            'yon': 'AL' veya 'SAT',
            'tur': 'sinyal açıklaması',
            'detay': 'ek bilgi',
            'sl': 80.1, 'tp1': 84.2, 'tp2': 86.5, 'tp3': 89.0  (opsiyonel)
        }
    """
    os.makedirs(SINYAL_DIR, exist_ok=True)

    zaman = datetime.now().strftime("%Y-%m-%d %H:%M")
    tarih = datetime.now().strftime("%Y-%m-%d")

    # 1. Güncel sinyalleri kaydet (son tarama)
    guncel_dosya = f"{SINYAL_DIR}/guncel_{sistem_adi}.json"
    with open(guncel_dosya, 'w', encoding='utf-8') as f:
        json.dump({
            'sistem': sistem_adi,
            'zaman':  zaman,
            'sinyaller': sinyaller
        }, f, ensure_ascii=False, indent=1)

    # 2. Geçmişe ekle (birikir)
    gecmis_dosya = f"{SINYAL_DIR}/gecmis.json"
    gecmis = []
    if os.path.exists(gecmis_dosya):
        try:
            with open(gecmis_dosya, 'r', encoding='utf-8') as f:
                gecmis = json.load(f)
        except:
            gecmis = []

    for s in sinyaller:
        kayit = dict(s)
        kayit['sistem'] = sistem_adi
        kayit['tarih']  = tarih
        kayit['zaman']  = zaman
        gecmis.append(kayit)

    # Son 500 kayıtla sınırla
    gecmis = gecmis[-500:]

    with open(gecmis_dosya, 'w', encoding='utf-8') as f:
        json.dump(gecmis, f, ensure_ascii=False, indent=1)

    print(f"[sinyal_kaydet] {sistem_adi}: {len(sinyaller)} sinyal kaydedildi")
