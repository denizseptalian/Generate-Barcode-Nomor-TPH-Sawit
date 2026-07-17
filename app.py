"""
=====================================================================
Aplikasi Streamlit: Generate QR Code Massal (Barcode TPH)
=====================================================================
Fungsi:
- Membuat QR Code untuk rentang nomor TPH pada satu Afdeling & Blok
- Desain kartu: bingkai hijau rounded, logo Saraswanti (disematkan
  sebagai base64) + "AFD {xx}" di header, "BLOK {Blok} - TPH {xxx}"
  di bawahnya, QR Code besar di tengah, dan nama lengkap PT di footer
- Ekspor Opsi 1: PDF A4 dengan layout grid 2 kolom x 2 baris
  (4 QR Code per halaman)
- Ekspor Opsi 2: Gambar PNG per barcode (satu file per TPH),
  dikemas dalam satu file ZIP
- Semua hasil dibuat di memori (io.BytesIO), TIDAK ada file yang
  disimpan permanen di server -> langsung diunduh via download_button

Library yang dibutuhkan (lihat requirements.txt):
    streamlit, qrcode, reportlab, pillow

Cara menjalankan lokal:
    streamlit run app_qr_barcode_tph.py
=====================================================================
"""

import base64
import io
import re
import zipfile
from functools import lru_cache

import qrcode
import streamlit as st

from PIL import Image, ImageDraw, ImageFont

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


# =================================================================
# KONFIGURASI KEBUN (PT)
# =================================================================
# Key   = label yang tampil di dropdown Streamlit
# Value = kode singkat kebun, dipakai sebagai awalan kode barcode
DAFTAR_KEBUN = {
    "PT. Saraswanti Sawit Makmur (SSM)": "SSM",
    "PT. Saraswanti Agro Estate (SAE)": "SAE",
}

# Nama lengkap PT (dipakai sebagai teks footer di kartu, mengikuti
# desain acuan yang menampilkan "PT. Saraswanti Sawit Makmur" di bawah QR)
DAFTAR_KEBUN_NAMA_LENGKAP = {
    "SSM": "PT. Saraswanti Sawit Makmur",
    "SAE": "PT. Saraswanti Agro Estate",
}


def format_afdeling(afdeling) -> str:
    """
    Memformat nomor Afdeling menjadi 2 digit dengan awalan 0.
    Contoh: 1 -> "01", 8 -> "08", 12 -> "12"
    """
    return f"{int(afdeling):02d}"


def format_nomor_tph(nomor_tph) -> str:
    """
    Memformat nomor TPH menjadi 3 digit dengan awalan 00.
    Contoh: 1 -> "001", 25 -> "025", 100 -> "100"
    """
    return f"{int(nomor_tph):03d}"


def buat_kode_lengkap(kebun_kode, afdeling, blok, nomor_tph) -> str:
    """
    Menyusun kode identifikasi lengkap dengan format:
        KEBUN_AF{Afdeling 2 digit}_{Blok}_{TPH 3 digit}
    Contoh: SSM_AF01_A8_001
    """
    blok_bersih = sanitasi_nama_file(blok)
    return (
        f"{kebun_kode}_AF{format_afdeling(afdeling)}_"
        f"{blok_bersih}_{format_nomor_tph(nomor_tph)}"
    )


# =================================================================
# KONFIGURASI WARNA & FONT
# =================================================================
WARNA_HIJAU = HexColor("#1B7A3D")   # Warna bingkai (hijau profesional)
WARNA_TEKS = HexColor("#0D3D1E")    # Warna teks judul (hijau tua gelap)

WARNA_HIJAU_HEX = "#1B7A3D"   # Versi string hex (dipakai oleh PIL, bukan reportlab)
WARNA_TEKS_HEX = "#0D3D1E"

# Path font Bold di server (di-install lewat packages.txt saat deploy).
# Jika tidak ditemukan, kode otomatis fallback ke font bawaan Pillow
# supaya aplikasi tetap jalan di lingkungan mana pun.
PATH_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def ambil_font_bold(ukuran: int) -> ImageFont.FreeTypeFont:
    """
    Mengambil font Bold dengan ukuran tertentu untuk digunakan pada
    gambar PNG individual. Ada fallback otomatis jika font sistem
    tidak tersedia (misalnya di lingkungan deploy yang berbeda).
    """
    try:
        return ImageFont.truetype(PATH_FONT_BOLD, ukuran)
    except Exception:
        return ImageFont.load_default(size=ukuran)


# =================================================================
# LOGO SARASWANTI (disematkan sebagai base64 di dalam kode ini)
# =================================================================
# Logo disematkan langsung (bukan file terpisah) supaya aplikasi tetap
# berupa satu file .py mandiri -> tidak ada risiko "file logo hilang"
# saat di-deploy ke Streamlit Cloud atau server lain.
LOGO_SARASWANTI_BASE64 = (
    "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"
    "u+P/BRgAEKTzF7P6rSIAAAAASUVORK5CYII="
)


@lru_cache(maxsize=1)
def ambil_logo_pil() -> Image.Image:
    """
    Mendekode logo Saraswanti (base64) menjadi PIL Image RGBA.
    Di-cache (lru_cache) agar proses decode hanya dilakukan sekali,
    walau dipanggil berulang kali untuk banyak barcode.
    """
    data_logo = base64.b64decode(LOGO_SARASWANTI_BASE64)
    return Image.open(io.BytesIO(data_logo)).convert("RGBA")


def sanitasi_nama_file(teks: str) -> str:
    """
    Membersihkan string agar aman dipakai sebagai nama file
    (menghapus spasi & karakter yang tidak valid untuk nama file).
    """
    teks_tanpa_spasi = str(teks).strip().replace(" ", "")
    return re.sub(r"[^A-Za-z0-9\-_]", "", teks_tanpa_spasi)


# =================================================================
# KONSTANTA LAYOUT PDF (Grid 2 kolom x 2 baris per halaman A4)
# =================================================================
LEBAR_HALAMAN, TINGGI_HALAMAN = A4  # Ukuran A4 Portrait (dalam poin)

MARGIN_LUAR = 20      # Jarak dari tepi kertas ke grid
JARAK_ANTAR_SEL = 12  # Jarak (gap) antar 4 kuadran
PADDING_SEL = 14      # Padding di dalam masing-masing bingkai
RADIUS_BINGKAI = 8    # Radius sudut bingkai (rounded rectangle)

LEBAR_SEL = (LEBAR_HALAMAN - (2 * MARGIN_LUAR) - JARAK_ANTAR_SEL) / 2
TINGGI_SEL = (TINGGI_HALAMAN - (2 * MARGIN_LUAR) - JARAK_ANTAR_SEL) / 2


# =================================================================
# KONSTANTA LAYOUT GAMBAR PNG INDIVIDUAL (per barcode)
# =================================================================
IMG_LEBAR = 900         # Lebar kanvas gambar (piksel)
IMG_TINGGI = 1300        # Tinggi kanvas gambar (piksel)
IMG_MARGIN = 30          # Jarak bingkai dari tepi gambar
IMG_BORDER_TEBAL = 14    # Ketebalan garis bingkai (dipertebal agar lebih tegas)
IMG_RADIUS = 45          # Radius sudut bingkai


# =================================================================
# KONSTANTA PROPORSI TATA LETAK KARTU (mengikuti desain acuan)
# Semua nilai berupa FRAKSI (0.0 - 1.0) relatif terhadap lebar/tinggi
# =================================================================
# Header: Teks AFD (Pindah ke tengah atas)
AFD_FRAC_Y_TENGAH = 0.10
AFD_FRAC_LEBAR_MAKS = 0.84

# Baris: BLOK - TPH (Di bawah AFD)
BLOK_FRAC_Y_TENGAH = 0.20
BLOK_FRAC_LEBAR_MAKS = 0.84

# Posisi Logo (Di bawah TPH, di atas QR, dipusatkan)
LOGO_FRAC_X0, LOGO_FRAC_X1 = 0.35, 0.65
LOGO_FRAC_Y0, LOGO_FRAC_Y1 = 0.24, 0.38

# Area QR Code (Di bawah logo)
QR_FRAC_Y0, QR_FRAC_Y1 = 0.40, 0.87
QR_FRAC_LEBAR = 0.615

# Footer (Nama PT)
FOOTER_FRAC_Y_TENGAH = 0.9405
FOOTER_FRAC_LEBAR_MAKS = 0.84


# ---------------------------------------------------------------
# FUNGSI: Membuat QR Code sebagai objek PIL Image (dipakai bersama
# oleh fitur PDF maupun fitur gambar individual)
# ---------------------------------------------------------------
def buat_qr_code_pil(data_payload: str) -> Image.Image:
    """
    Menghasilkan QR Code dalam bentuk PIL Image dari string payload.
    """
    qr = qrcode.QRCode(
        version=None,               # otomatis menyesuaikan ukuran data
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data_payload)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


# ---------------------------------------------------------------
# FUNGSI BANTUAN: Mencari ukuran font (PDF) terbesar yang masih
# membuat sebuah teks muat di dalam lebar maksimum yang ditentukan.
# Berguna karena panjang teks Blok/nama PT bisa bervariasi.
# ---------------------------------------------------------------
def ambil_ukuran_font_muat_pdf(pdf_canvas, teks, ukuran_awal, ukuran_minimum, lebar_maksimum,
                                nama_font="Helvetica-Bold"):
    ukuran = ukuran_awal
    while ukuran > ukuran_minimum:
        if pdf_canvas.stringWidth(teks, nama_font, ukuran) <= lebar_maksimum:
            return ukuran
        ukuran -= 1
    return ukuran_minimum


# ---------------------------------------------------------------
# FUNGSI: Menggambar satu kuadran PDF (bingkai + logo + judul + QR + footer)
# ---------------------------------------------------------------
def gambar_satu_kuadran(pdf_canvas, x_awal, y_awal, kebun_kode, afdeling, blok, nomor_tph):
    """
    Menggambar satu kotak/kuadran pada halaman PDF mengikuti desain
    kartu resmi Saraswanti, berisi:
    - Bingkai hijau rounded rectangle
    - Header: logo Saraswanti (kiri) + "AFD {xx}" (kanan logo)
    - Baris: "BLOK {Blok} - TPH {Nomor 3 digit}" -> bold, center
    - QR Code besar di tengah (payload = kode lengkap)
    - Footer: nama lengkap PT -> bold, center
    """
    titik_tengah_x = x_awal + (LEBAR_SEL / 2)
    afdeling_fmt = format_afdeling(afdeling)
    tph_fmt = format_nomor_tph(nomor_tph)
    nama_pt_lengkap = DAFTAR_KEBUN_NAMA_LENGKAP.get(kebun_kode, kebun_kode)

    def y_dari_atas(frac):
        """Konversi fraksi jarak dari tepi ATAS kuadran -> koordinat Y PDF (dari bawah)."""
        return y_awal + TINGGI_SEL * (1 - frac)

    # 1. Gambar bingkai hijau (dipertebal agar lebih tegas)
    TEBAL_GARIS_BINGKAI = 3.5
    pdf_canvas.setStrokeColor(WARNA_HIJAU)
    pdf_canvas.setLineWidth(TEBAL_GARIS_BINGKAI)
    pdf_canvas.roundRect(
        x_awal, y_awal, LEBAR_SEL, TINGGI_SEL,
        RADIUS_BINGKAI, stroke=1, fill=0
    )

    # 2. Teks "AFD {xx}" (Sekarang di tengah atas)
    teks_afd = f"AFD {afdeling_fmt}"
    lebar_maks_afd = LEBAR_SEL * AFD_FRAC_LEBAR_MAKS
    ukuran_font_afd = ambil_ukuran_font_muat_pdf(pdf_canvas, teks_afd, 26, 14, lebar_maks_afd)
    pdf_canvas.setFont("Helvetica-Bold", ukuran_font_afd)
    pdf_canvas.setFillColor(WARNA_TEKS)
    y_afd = y_dari_atas(AFD_FRAC_Y_TENGAH) - (ukuran_font_afd * 0.32)
    pdf_canvas.drawCentredString(titik_tengah_x, y_afd, teks_afd)
    pdf_canvas.drawCentredString(titik_tengah_x + 0.4, y_afd, teks_afd)  # trik extra bold

    # 3. Baris "BLOK {blok} - TPH {tph}" (center, bold, auto-fit lebar)
    teks_blok = f"BLOK {blok} - TPH {tph_fmt}"
    lebar_maks_blok = LEBAR_SEL * BLOK_FRAC_LEBAR_MAKS
    ukuran_font_blok = ambil_ukuran_font_muat_pdf(pdf_canvas, teks_blok, 20, 10, lebar_maks_blok)
    pdf_canvas.setFont("Helvetica-Bold", ukuran_font_blok)
    y_blok = y_dari_atas(BLOK_FRAC_Y_TENGAH) - (ukuran_font_blok * 0.32)
    pdf_canvas.drawCentredString(titik_tengah_x, y_blok, teks_blok)
    pdf_canvas.drawCentredString(titik_tengah_x + 0.4, y_blok, teks_blok)

    # 4. Logo Saraswanti (Di tengah, letaknya di bawah teks TPH dan di atas QR)
    logo_pil = ambil_logo_pil()
    rasio_logo = logo_pil.width / logo_pil.height
    lebar_logo = LEBAR_SEL * (LOGO_FRAC_X1 - LOGO_FRAC_X0)
    tinggi_logo_maks = TINGGI_SEL * (LOGO_FRAC_Y1 - LOGO_FRAC_Y0)
    tinggi_logo = lebar_logo / rasio_logo
    if tinggi_logo > tinggi_logo_maks:
        tinggi_logo = tinggi_logo_maks
        lebar_logo = tinggi_logo * rasio_logo
        
    x_logo = titik_tengah_x - (lebar_logo / 2)
    y_logo = y_dari_atas(LOGO_FRAC_Y1)
    pdf_canvas.drawImage(
        ImageReader(logo_pil), x_logo, y_logo,
        width=lebar_logo, height=tinggi_logo,
        preserveAspectRatio=True, mask="auto"
    )

    # 5. QR Code besar, center (payload = kode lengkap KEBUN_AFxx_Blok_TPHxxx)
    payload_qr = buat_kode_lengkap(kebun_kode, afdeling, blok, nomor_tph)
    gambar_qr_pil = buat_qr_code_pil(payload_qr)
    gambar_qr_reader = ImageReader(gambar_qr_pil)

    lebar_area_qr = LEBAR_SEL * QR_FRAC_LEBAR
    tinggi_area_qr = TINGGI_SEL * (QR_FRAC_Y1 - QR_FRAC_Y0)
    ukuran_qr = min(lebar_area_qr, tinggi_area_qr)
    x_qr = titik_tengah_x - (ukuran_qr / 2)
    y_qr_atas = y_dari_atas(QR_FRAC_Y0)
    y_qr = y_qr_atas - tinggi_area_qr + ((tinggi_area_qr - ukuran_qr) / 2)

    pdf_canvas.drawImage(
        gambar_qr_reader, x_qr, y_qr,
        width=ukuran_qr, height=ukuran_qr,
        preserveAspectRatio=True, mask="auto"
    )

    # 6. Footer: nama lengkap PT (center, bold, auto-fit lebar)
    lebar_maks_footer = LEBAR_SEL * FOOTER_FRAC_LEBAR_MAKS
    ukuran_font_footer = ambil_ukuran_font_muat_pdf(
        pdf_canvas, nama_pt_lengkap, 11, 7, lebar_maks_footer
    )
    pdf_canvas.setFont("Helvetica-Bold", ukuran_font_footer)
    y_footer = y_dari_atas(FOOTER_FRAC_Y_TENGAH) - (ukuran_font_footer * 0.32)
    pdf_canvas.drawCentredString(titik_tengah_x, y_footer, nama_pt_lengkap)


# ---------------------------------------------------------------
# FUNGSI UTAMA 1: Membuat dokumen PDF (grid 2x2, multi-halaman)
# ---------------------------------------------------------------
def buat_pdf_barcode_tph(kebun_kode, afdeling, blok, tph_awal, tph_akhir) -> io.BytesIO:
    """
    Membuat PDF berisi QR Code untuk setiap nomor TPH dari tph_awal
    sampai tph_akhir, disusun grid 2x2 per halaman A4.
    Mengembalikan buffer PDF (io.BytesIO) — tidak menyimpan ke disk.
    """
    buffer_pdf = io.BytesIO()
    pdf_canvas = canvas.Canvas(buffer_pdf, pagesize=A4)

    daftar_nomor_tph = list(range(tph_awal, tph_akhir + 1))

    for indeks, nomor_tph in enumerate(daftar_nomor_tph):
        posisi_dalam_halaman = indeks % 4  # 0,1,2,3 -> posisi kuadran

        baris = posisi_dalam_halaman // 2   # 0 = atas, 1 = bawah
        kolom = posisi_dalam_halaman % 2    # 0 = kiri, 1 = kanan

        x_sel = MARGIN_LUAR + kolom * (LEBAR_SEL + JARAK_ANTAR_SEL)
        y_sel = (
            TINGGI_HALAMAN - MARGIN_LUAR
            - (baris + 1) * TINGGI_SEL - baris * JARAK_ANTAR_SEL
        )

        gambar_satu_kuadran(pdf_canvas, x_sel, y_sel, kebun_kode, afdeling, blok, nomor_tph)

        halaman_penuh = (posisi_dalam_halaman == 3)
        masih_ada_data_berikutnya = (indeks < len(daftar_nomor_tph) - 1)
        if halaman_penuh and masih_ada_data_berikutnya:
            pdf_canvas.showPage()

    pdf_canvas.save()
    buffer_pdf.seek(0)
    return buffer_pdf


# ---------------------------------------------------------------
# FUNGSI BANTUAN: Mencari ukuran font (PIL) terbesar yang masih
# membuat sebuah teks muat di dalam lebar maksimum yang ditentukan.
# ---------------------------------------------------------------
def ambil_font_muat_pil(juru_gambar, teks, ukuran_awal, ukuran_minimum, lebar_maksimum,
                         stroke_width=2):
    ukuran = ukuran_awal
    while ukuran > ukuran_minimum:
        font = ambil_font_bold(ukuran)
        kotak = juru_gambar.textbbox((0, 0), teks, font=font, stroke_width=stroke_width)
        if (kotak[2] - kotak[0]) <= lebar_maksimum:
            return font, kotak
        ukuran -= 2
    font = ambil_font_bold(ukuran_minimum)
    kotak = juru_gambar.textbbox((0, 0), teks, font=font, stroke_width=stroke_width)
    return font, kotak


# ---------------------------------------------------------------
# FUNGSI: Membuat SATU gambar PNG individual (bingkai + logo + judul + QR + footer)
# ---------------------------------------------------------------
def buat_gambar_barcode_individual(kebun_kode, afdeling, blok, nomor_tph) -> Image.Image:
    """
    Membuat satu gambar PNG mandiri untuk satu TPH, mengikuti desain
    kartu resmi Saraswanti:
    - Bingkai hijau rounded rectangle
    - Header: logo Saraswanti (kiri) + "AFD {xx}" (kanan logo)
    - Baris "BLOK {Blok} - TPH {Nomor 3 digit}" -> bold, center
    - QR Code besar di tengah
    - Footer: nama lengkap PT -> bold, center
    """
    kanvas_gambar = Image.new("RGB", (IMG_LEBAR, IMG_TINGGI), "white")
    juru_gambar = ImageDraw.Draw(kanvas_gambar)

    afdeling_fmt = format_afdeling(afdeling)
    tph_fmt = format_nomor_tph(nomor_tph)
    nama_pt_lengkap = DAFTAR_KEBUN_NAMA_LENGKAP.get(kebun_kode, kebun_kode)
    KETEBALAN_STROKE = 2  # Menambah ketebalan agar teks terlihat lebih tegas

    # 1. Bingkai hijau (rounded rectangle)
    juru_gambar.rounded_rectangle(
        [IMG_MARGIN, IMG_MARGIN, IMG_LEBAR - IMG_MARGIN, IMG_TINGGI - IMG_MARGIN],
        radius=IMG_RADIUS, outline=WARNA_HIJAU_HEX, width=IMG_BORDER_TEBAL
    )

    # 2. Teks "AFD {xx}" (Center, letaknya paling atas)
    teks_afd = f"AFD {afdeling_fmt}"
    lebar_maks_afd = IMG_LEBAR * AFD_FRAC_LEBAR_MAKS
    font_afd, kotak_afd = ambil_font_muat_pil(
        juru_gambar, teks_afd, 76, 40, lebar_maks_afd, KETEBALAN_STROKE
    )
    lebar_teks_afd = kotak_afd[2] - kotak_afd[0]
    y_tengah_afd = IMG_TINGGI * AFD_FRAC_Y_TENGAH
    x_afd = (IMG_LEBAR - lebar_teks_afd) / 2 - kotak_afd[0]
    y_afd = y_tengah_afd - (kotak_afd[1] + kotak_afd[3]) / 2
    juru_gambar.text(
        (x_afd, y_afd), teks_afd, font=font_afd, fill=WARNA_TEKS_HEX,
        stroke_width=KETEBALAN_STROKE, stroke_fill=WARNA_TEKS_HEX
    )

    # 3. Baris "BLOK {blok} - TPH {tph}" (Center, letaknya di bawah AFD)
    teks_blok = f"BLOK {blok} - TPH {tph_fmt}"
    lebar_maks_blok = IMG_LEBAR * BLOK_FRAC_LEBAR_MAKS
    font_blok, kotak_blok = ambil_font_muat_pil(
        juru_gambar, teks_blok, 64, 28, lebar_maks_blok, KETEBALAN_STROKE
    )
    lebar_blok = kotak_blok[2] - kotak_blok[0]
    y_tengah_blok = IMG_TINGGI * BLOK_FRAC_Y_TENGAH
    x_blok = (IMG_LEBAR - lebar_blok) / 2 - kotak_blok[0]
    y_blok = y_tengah_blok - (kotak_blok[1] + kotak_blok[3]) / 2
    juru_gambar.text(
        (x_blok, y_blok), teks_blok, font=font_blok, fill=WARNA_TEKS_HEX,
        stroke_width=KETEBALAN_STROKE, stroke_fill=WARNA_TEKS_HEX
    )

    # 4. Logo Saraswanti (Center, letaknya di bawah TPH dan di atas QR)
    logo_pil = ambil_logo_pil()
    rasio_logo = logo_pil.width / logo_pil.height
    lebar_logo = int(IMG_LEBAR * (LOGO_FRAC_X1 - LOGO_FRAC_X0))
    tinggi_logo_maks = int(IMG_TINGGI * (LOGO_FRAC_Y1 - LOGO_FRAC_Y0))
    tinggi_logo = int(lebar_logo / rasio_logo)
    if tinggi_logo > tinggi_logo_maks:
        tinggi_logo = tinggi_logo_maks
        lebar_logo = int(tinggi_logo * rasio_logo)

    x_logo = (IMG_LEBAR - lebar_logo) // 2
    y_logo = int(IMG_TINGGI * LOGO_FRAC_Y0)
    logo_resize = logo_pil.resize((lebar_logo, tinggi_logo), Image.LANCZOS)
    kanvas_gambar.paste(logo_resize, (x_logo, y_logo), logo_resize)

    # 5. QR Code besar, center (payload = kode lengkap)
    payload_qr = buat_kode_lengkap(kebun_kode, afdeling, blok, nomor_tph)
    gambar_qr = buat_qr_code_pil(payload_qr)

    y_qr_atas = IMG_TINGGI * QR_FRAC_Y0
    tinggi_area_qr = IMG_TINGGI * (QR_FRAC_Y1 - QR_FRAC_Y0)
    lebar_area_qr = IMG_LEBAR * QR_FRAC_LEBAR
    ukuran_qr = int(min(lebar_area_qr, tinggi_area_qr))
    gambar_qr_resize = gambar_qr.resize((ukuran_qr, ukuran_qr))

    x_qr = (IMG_LEBAR - ukuran_qr) // 2
    y_qr = int(y_qr_atas + (tinggi_area_qr - ukuran_qr) / 2)
    kanvas_gambar.paste(gambar_qr_resize, (x_qr, y_qr))

    # 6. Footer: nama lengkap PT (center, bold, auto-fit lebar)
    lebar_maks_footer = IMG_LEBAR * FOOTER_FRAC_LEBAR_MAKS
    font_footer, kotak_footer = ambil_font_muat_pil(
        juru_gambar, nama_pt_lengkap, 40, 20, lebar_maks_footer, 1
    )
    lebar_footer = kotak_footer[2] - kotak_footer[0]
    y_tengah_footer = IMG_TINGGI * FOOTER_FRAC_Y_TENGAH
    x_footer = (IMG_LEBAR - lebar_footer) / 2 - kotak_footer[0]
    y_footer = y_tengah_footer - (kotak_footer[1] + kotak_footer[3]) / 2
    juru_gambar.text(
        (x_footer, y_footer), nama_pt_lengkap, font=font_footer, fill=WARNA_TEKS_HEX,
        stroke_width=1, stroke_fill=WARNA_TEKS_HEX
    )

    return kanvas_gambar


# ---------------------------------------------------------------
# FUNGSI UTAMA 2: Membuat file ZIP berisi gambar PNG per barcode
# ---------------------------------------------------------------
def buat_zip_gambar_barcode(kebun_kode, afdeling, blok, tph_awal, tph_akhir) -> io.BytesIO:
    """
    Membuat satu file ZIP berisi gambar PNG terpisah untuk setiap
    nomor TPH dari tph_awal sampai tph_akhir.
    Mengembalikan buffer ZIP (io.BytesIO) — tidak menyimpan ke disk.
    """
    buffer_zip = io.BytesIO()

    with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as file_zip:
        for nomor_tph in range(tph_awal, tph_akhir + 1):
            gambar = buat_gambar_barcode_individual(kebun_kode, afdeling, blok, nomor_tph)

            buffer_gambar = io.BytesIO()
            gambar.save(buffer_gambar, format="PNG")
            buffer_gambar.seek(0)

            nama_kode = buat_kode_lengkap(kebun_kode, afdeling, blok, nomor_tph)
            nama_file = f"{nama_kode}.png"
            file_zip.writestr(nama_file, buffer_gambar.getvalue())

    buffer_zip.seek(0)
    return buffer_zip


# =================================================================
# ANTARMUKA STREAMLIT (UI)
# =================================================================
st.set_page_config(page_title="Generator QR Code TPH", page_icon="🔖", layout="centered")

st.title("🔖 Generator QR Code Barcode TPH")
st.write(
    "Aplikasi untuk membuat QR Code massal berdasarkan Kebun, Afdeling, Blok, "
    "dan rentang nomor TPH — dapat diekspor sebagai PDF siap cetak (grid 2x2) "
    "dan/atau gambar PNG terpisah per barcode (dalam satu file ZIP). "
    "Kode identifikasi mengikuti format KEBUN_AFxx_Blok_TPHxxx, contoh: SSM_AF01_A8_001."
)

st.divider()

# --- Input Kebun (PT) ---
st.subheader("Kebun")
input_kebun_label = st.selectbox(
    "Pilih Kebun (PT)",
    options=list(DAFTAR_KEBUN.keys()),
    help="Kode kebun akan menjadi awalan pada kode barcode (mis. SSM_AF01_A8_001).",
)
input_kebun_kode = DAFTAR_KEBUN[input_kebun_label]

# --- Input Afdeling & Blok ---
kolom_1, kolom_2 = st.columns(2)
with kolom_1:
    input_afdeling = st.number_input(
        "Afdeling (AFD)", min_value=1, max_value=99, value=1, step=1,
        help="Maksimal 2 angka, otomatis diberi awalan 0. Contoh: 1 -> AF01, 12 -> AF12.",
    )
with kolom_2:
    input_blok = st.text_input("Blok", value="A8", help="Contoh: 12, A8, 15A, dst.")

# --- Input Range Nomor TPH ---
st.subheader("Rentang Nomor TPH")
kolom_3, kolom_4 = st.columns(2)
with kolom_3:
    input_tph_awal = st.number_input(
        "TPH Awal", min_value=1, value=1, step=1,
        help="Otomatis diberi awalan 00. Contoh: 1 -> 001.",
    )
with kolom_4:
    input_tph_akhir = st.number_input("TPH Akhir", min_value=1, value=10, step=1)

# --- Preview Kode Lengkap ---
if input_blok.strip():
    kode_contoh = buat_kode_lengkap(
        input_kebun_kode, input_afdeling, input_blok.strip(), input_tph_awal
    )
    st.caption("Contoh kode untuk TPH pertama:")
    st.code(kode_contoh, language=None)

# --- Pilihan Format Output ---
st.subheader("Format Output")
kolom_5, kolom_6 = st.columns(2)
with kolom_5:
    ingin_pdf = st.checkbox("📄 PDF Gabungan (grid 2x2 per halaman)", value=True)
with kolom_6:
    ingin_zip_gambar = st.checkbox("🖼️ Gambar PNG per Barcode (ZIP)", value=True)

st.divider()

# --- Tombol Proses ---
if st.button("🚀 Generate", type="primary", use_container_width=True):

    # Validasi input dasar
    if not input_blok.strip():
        st.error("Blok tidak boleh kosong.")
    elif input_tph_awal > input_tph_akhir:
        st.error("TPH Awal tidak boleh lebih besar dari TPH Akhir.")
    elif not ingin_pdf and not ingin_zip_gambar:
        st.error("Pilih minimal satu format output (PDF dan/atau Gambar ZIP).")
    else:
        kebun_kode_final = input_kebun_kode
        afdeling_final = int(input_afdeling)
        blok_final = input_blok.strip()
        tph_awal_final = int(input_tph_awal)
        tph_akhir_final = int(input_tph_akhir)
        jumlah_tph = tph_akhir_final - tph_awal_final + 1

        # --- Generate PDF (jika dipilih) ---
        if ingin_pdf:
            with st.spinner(f"Membuat PDF untuk {jumlah_tph} QR Code..."):
                buffer_pdf = buat_pdf_barcode_tph(
                    kebun_kode_final, afdeling_final, blok_final,
                    tph_awal_final, tph_akhir_final
                )
            st.success("✅ File PDF berhasil dibuat.")
            nama_pdf = f"Print_Barcode_TPH_{kebun_kode_final}_AF{format_afdeling(afdeling_final)}_{sanitasi_nama_file(blok_final)}.pdf"
            st.download_button(
                label=f"⬇️ Unduh PDF ({nama_pdf})",
                data=buffer_pdf,
                file_name=nama_pdf,
                mime="application/pdf",
                use_container_width=True,
            )

        # --- Generate ZIP Gambar Individual (jika dipilih) ---
        if ingin_zip_gambar:
            with st.spinner(f"Membuat {jumlah_tph} gambar PNG individual..."):
                buffer_zip = buat_zip_gambar_barcode(
                    kebun_kode_final, afdeling_final, blok_final,
                    tph_awal_final, tph_akhir_final
                )
            st.success("✅ File ZIP gambar per barcode berhasil dibuat.")
            nama_zip = f"Gambar_Barcode_TPH_{kebun_kode_final}_AF{format_afdeling(afdeling_final)}_{sanitasi_nama_file(blok_final)}.zip"
            st.download_button(
                label=f"⬇️ Unduh Gambar PNG per Barcode ({nama_zip})",
                data=buffer_zip,
                file_name=nama_zip,
                mime="application/zip",
                use_container_width=True,
            )

            # Tampilkan contoh gambar pertama sebagai preview
            with st.expander("👁️ Lihat contoh preview gambar (TPH pertama)"):
                gambar_contoh = buat_gambar_barcode_individual(
                    kebun_kode_final, afdeling_final, blok_final, tph_awal_final
                )
                st.image(gambar_contoh, use_container_width=True)
