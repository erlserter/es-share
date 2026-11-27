# ES-Share

Tek bir klavye ve fareyi aynı yerel ağ (Wi-Fi / Ethernet) üzerinden **Mac (Ana PC) ↔ Windows** arasında paylaşmanızı sağlayan hafif, modern web arayüzlü yazılım KVM aracı.

## Özellikler

- **Tek Klavye & Fare Paylaşımı:** Düşük gecikmeli TCP (`TCP_NODELAY`) aktarımı ve çözünürlükten bağımsız göreceli fare hareketi.
- **Akıllı Kenar Geçişi & İmleç Kilidi:** Fareyi ekranın sağ/sol kenarına götürerek Mac ↔ Windows arasında otomatik geçiş yapın; Windows kontrolündeyken Mac imleci sabit kalır.
- **Acil Dönüş Kısayolları:** `Ctrl + Alt + S` veya 1 saniye içinde `3× Esc` ile anında Mac'e geri dönün.
- **Otomatik Tuş Eşleme:** Mac `Cmd` ↔ Windows `Ctrl` eşlemesi (kopyala/yapıştır kısayolları için) ve cihaz değişiminde takılı tuş koruması.
- **Çift Yönlü Ortak Pano (Copy–Paste):** Harici paket gerektirmeden Mac (`pbcopy`/`pbpaste`) ve Windows (`ctypes` Win32 Clipboard) arasında metin senkronizasyonu.
- **Sürükle–Bırak Dosya Transferi:** Web arayüzü üzerinden dosya ve görselleri doğrudan karşı bilgisayarın `~/Downloads/ES-Share` klasörüne gönderin.
- **Modern Web Arayüzü (`shadcn/ui`):** React + TypeScript + Tailwind CSS v4 ile görsel masaüstü tuvali, karanlık/aydınlık tema ve canlı günlük paneli.

---

## Gereksinimler

- **Python 3.10+** (Mac ve Windows)
- **Node.js 20+** *(yalnızca web arayüzünü `ui/` içinden yeniden derlemek isterseniz)*

---

## Kurulum

### 1. Mac (Ana Bilgisayar / Server)

```bash
git clone https://github.com/erlserter/es-share.git
cd es-share

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Web arayüzünü derleyin
cd ui && npm install && npm run build && cd ..
```

Başlatmak için:
- Masaüstündeki / klasördeki **`Mac_Baslat.command`** dosyasına çift tıklayın *(önerilen — Terminal üzerinden açıldığı için Erişilebilirlik iznini temiz şekilde devralır)*, veya
- Terminal'den çalıştırın:
  ```bash
  .venv/bin/python app.py
  ```

Tarayıcınızda **`http://127.0.0.1:8765`** açılır. **Sunucuyu Başlat**'a basın ve ekranda görünen yerel IP adresinizi not alın.

### 2. Windows (Bağlanan Cihaz / Client)

Klasörü Windows makinenize alın ve bağımlılığı kurun:

```bat
pip install -r requirements.txt
```

- **Web arayüzü ile:**
  ```bat
  python app.py
  ```
  **Windows — Bağlanan Cihaz (Client)** sekmesine Mac'in IP adresini yazıp **Mac'e Bağlan**'a basın. Aynı sekmeden Mac'e sürükle–bırak ile dosya/görsel gönderebilirsiniz.

- **Komut satırından doğrudan bağlanmak için:**
  ```bat
  python app.py client --host <MAC_IP_ADRESI>
  ```

### Windows `.exe` Oluşturma (Opsiyonel)

Python kurulu bir Windows makinede tek `.exe` üretmek için `build_windows.bat` dosyasına çift tıklayabilir veya şu komutları çalıştırabilirsiniz:

```bat
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --onefile --name ES-Share --add-data "ui\dist;ui\dist" --hidden-import=pynput.keyboard._win32 --hidden-import=pynput.mouse._win32 app.py
```

---

## İzinler ve Güvenlik Notu

- **macOS İzinleri:** İlk çalıştırmada **Sistem Ayarları > Gizlilik ve Güvenlik > Erişilebilirlik** altından **Terminal** (ve Homebrew Python kullanıyorsanız **Python.app**) için izin verin.
- **Windows Güvenlik Duvarı:** İlk bağlantıda sorulursa **Özel Ağlar** için erişime izin verin (varsayılan port: `24800`).
- **Ağ Güvenliği:** ES-Share yerel ağ içi kullanım için tasarlanmıştır ve TCP trafiği şifresizdir. Yalnızca güvendiğiniz yerel ağlarda (ev/ofis Wi-Fi) kullanın.

---

## Testler

```bash
.venv/bin/python -m unittest discover -s tests -v
```
