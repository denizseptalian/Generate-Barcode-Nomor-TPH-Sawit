# 🔖 Generator QR Code Barcode TPH

Aplikasi Streamlit untuk membuat QR Code massal (Afdeling, Blok, rentang nomor TPH) dan mengekspornya sebagai:

1. **PDF siap cetak** — grid 2 kolom x 2 baris per halaman A4, dengan bingkai hijau dan judul di setiap barcode.
2. **Gambar PNG per barcode** — satu file gambar untuk setiap nomor TPH, dikemas dalam satu file ZIP.

Semua file dibuat langsung di memori (tidak disimpan permanen di server), lalu diunduh via tombol download.

---

## 📁 Struktur File

```
├── app.py             # Kode utama aplikasi Streamlit
├── requirements.txt    # Daftar library Python yang dibutuhkan
├── packages.txt        # Dependensi sistem (apt) — font DejaVu untuk gambar PNG
└── README.md           # Panduan ini
```

---

## ▶️ Menjalankan di Komputer Lokal

1. Pastikan Python 3.9+ sudah terinstall.
2. Install seluruh dependency:
   ```bash
   pip install -r requirements.txt
   ```
3. Jalankan aplikasi:
   ```bash
   streamlit run app.py
   ```
4. Browser akan otomatis terbuka di `http://localhost:8501`.

> Catatan: `packages.txt` hanya relevan untuk deployment di Streamlit Community Cloud (Linux/Debian). Di Windows/Mac lokal, aplikasi tetap akan berjalan normal karena ada fallback font otomatis di dalam kode.

---

## ☁️ Deploy ke Streamlit Community Cloud (Gratis)

### Langkah 1 — Upload ke GitHub
1. Buat repository baru di GitHub (bisa **public** atau **private**), misalnya `qr-barcode-tph`.
2. Upload 3 file berikut ke root repository:
   - `app.py`
   - `requirements.txt`
   - `packages.txt`

   Bisa lewat web GitHub (tombol **Add file → Upload files**) atau via Git:
   ```bash
   git init
   git add app.py requirements.txt packages.txt
   git commit -m "Initial commit: Generator QR Code Barcode TPH"
   git branch -M main
   git remote add origin https://github.com/USERNAME/qr-barcode-tph.git
   git push -u origin main
   ```

### Langkah 2 — Deploy di Streamlit Cloud
1. Buka **[share.streamlit.io](https://share.streamlit.io)** dan login menggunakan akun GitHub Anda.
2. Klik **"Create app"** (atau **"New app"**).
3. Pilih:
   - **Repository**: `USERNAME/qr-barcode-tph`
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. Klik **"Deploy"**.
5. Tunggu proses build (Streamlit Cloud otomatis membaca `requirements.txt` untuk library Python dan `packages.txt` untuk dependensi sistem/font).
6. Setelah selesai, aplikasi akan memiliki URL publik seperti:
   ```
   https://USERNAME-qr-barcode-tph.streamlit.app
   ```

### Langkah 3 — Update Aplikasi di Kemudian Hari
Setiap kali Anda melakukan `git push` ke branch `main`, Streamlit Cloud akan otomatis melakukan re-deploy dengan versi kode terbaru.

---

## 🛠️ Troubleshooting

| Masalah | Solusi |
|---|---|
| Font pada gambar PNG terlihat tipis/berbeda saat online | Pastikan file `packages.txt` ikut ter-upload ke GitHub — ini menginstall font DejaVu Bold di server. |
| Aplikasi gagal deploy karena versi library | Cek log build di dashboard Streamlit Cloud, sesuaikan versi di `requirements.txt` jika ada konflik. |
| Ingin ganti warna bingkai/teks | Edit variabel `WARNA_HIJAU`, `WARNA_HIJAU_HEX`, `WARNA_TEKS_HEX` di bagian atas `app.py`. |
| Ingin ubah ukuran gambar PNG individual | Edit konstanta `IMG_LEBAR`, `IMG_TINGGI`, `IMG_MARGIN` di bagian atas `app.py`. |

---

## 📋 Format Data QR Code

Setiap QR Code berisi payload teks dengan format:

```
AFD {Afdeling} - BLOK {Blok} - TPH {Nomor}
```

Contoh: `AFD 1 - BLOK 12 - TPH 1`
