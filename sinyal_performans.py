BIST WEB APP - PERFORMANS SEKMESİ DÜZELTMESİ
=============================================

SORUN: Performans sekmesi boş görünüyordu (veri vardı ama kayboldu).

SEBEP: performans_arsiv.json içinde GARAN (2026-08-01) kaydında
"fiyat": NaN vardı. NaN, standart JSON'da GEÇERSİZDİR.
Tarayıcı JSON.parse ile bu dosyayı okurken çöküyordu -> sekme boş.
Ayrıca script her çalışmada dosyayı sıfırdan yazdığı için,
boş sonuç eski dolu veriyi eziyordu.

ÇÖZÜM (sinyal_performans.py içinde 4 düzeltme):
1. json_temizle: NaN/Infinity -> null'a çevrilir
2. json_kaydet: allow_nan=False (NaN varsa sessizce yazmaz, hata verir)
3. arsiv_temizle: mevcut bozuk NaN kayıtları temizler/atar
4. Yeni sinyal eklerken + fiyat çekerken NaN kontrolü

KURULUM:
1. sinyal_performans.py dosyasını indir
2. GitHub deposunda ESKI sinyal_performans.py'nin üstüne koy
   (repo kök dizininde)
3. Commit + push et
4. GitHub -> Actions -> "Sinyal Performans Takibi" -> "Run workflow"
   ile ELLE çalıştır (workflow_dispatch var)
5. Çalışınca performans_arsiv.json temizlenir, performans.json
   düzgün yazılır, web app'te performans sekmesi geri gelir

NOT: Verilerin GİT GEÇMİŞİNDE duruyor, hiçbir şey kalıcı kaybolmadı.
Bu düzeltme mevcut arşivi temizleyip istatistiği yeniden üretir.
