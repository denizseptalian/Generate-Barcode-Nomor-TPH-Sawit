"""
=====================================================================
Aplikasi Streamlit: Generate QR Code Massal (Barcode TPH)
=====================================================================
Fungsi:
- Membuat QR Code untuk rentang nomor TPH pada satu Afdeling & Blok
- Ekspor Opsi 1: PDF A4 dengan layout grid 2 kolom x 2 baris
  (4 QR Code per halaman), bingkai hijau, judul di atas QR Code
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

import io
import re
import zipfile

import qrcode
import streamlit as st

from PIL import Image, ImageDraw, ImageFont

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


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
IMG_BORDER_TEBAL = 8     # Ketebalan garis bingkai
IMG_RADIUS = 45          # Radius sudut bingkai


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
# FUNGSI: Menggambar satu kuadran PDF (bingkai + judul + QR Code)
# ---------------------------------------------------------------
def gambar_satu_kuadran(pdf_canvas, x_awal, y_awal, afdeling, blok, nomor_tph):
    """
    Menggambar satu kotak/kuadran pada halaman PDF, berisi:
    - Bingkai hijau rounded rectangle
    - Baris 1: AFD {Afdeling}  -> bold, center
    - Baris 2: BLOK {Blok} - TPH {Nomor} -> bold, center
    - QR Code di bawahnya, proporsional & center
    """
    titik_tengah_x = x_awal + (LEBAR_SEL / 2)

    # 1. Gambar bingkai hijau
    pdf_canvas.setStrokeColor(WARNA_HIJAU)
    pdf_canvas.setLineWidth(2)
    pdf_canvas.roundRect(
        x_awal, y_awal, LEBAR_SEL, TINGGI_SEL,
        RADIUS_BINGKAI, stroke=1, fill=0
    )

    # 2. Baris teks judul (Baris 1: AFD) — font diperbesar & dipertegas
    UKURAN_FONT_BARIS_1 = 20
    UKURAN_FONT_BARIS_2 = 17

    y_baris_1 = y_awal + TINGGI_SEL - PADDING_SEL - 18
    pdf_canvas.setFont("Helvetica-Bold", UKURAN_FONT_BARIS_1)
    pdf_canvas.setFillColor(WARNA_TEKS)
    pdf_canvas.drawCentredString(titik_tengah_x, y_baris_1, f"AFD {afdeling}")
    # Trik "extra bold": gambar ulang teks dengan sedikit offset agar goresan
    # huruf terlihat lebih tebal/pekat saat dicetak
    pdf_canvas.drawCentredString(titik_tengah_x + 0.4, y_baris_1, f"AFD {afdeling}")

    # 3. Baris teks judul (Baris 2: BLOK - TPH)
    y_baris_2 = y_baris_1 - 24
    pdf_canvas.setFont("Helvetica-Bold", UKURAN_FONT_BARIS_2)
    teks_baris_2 = f"BLOK {blok} - TPH {nomor_tph}"
    pdf_canvas.drawCentredString(titik_tengah_x, y_baris_2, teks_baris_2)
    pdf_canvas.drawCentredString(titik_tengah_x + 0.4, y_baris_2, teks_baris_2)

    # 4. Payload QR Code (format sesuai spesifikasi)
    payload_qr = f"AFD {afdeling} - BLOK {blok} - TPH {nomor_tph}"
    gambar_qr_pil = buat_qr_code_pil(payload_qr)
    gambar_qr_reader = ImageReader(gambar_qr_pil)

    # 5. Hitung area kosong di bawah teks (antara teks & tepi bawah bingkai)
    batas_atas_area_qr = y_baris_2 - 14
    batas_bawah_area_qr = y_awal + PADDING_SEL
    tinggi_area_qr = batas_atas_area_qr - batas_bawah_area_qr
    lebar_area_qr = LEBAR_SEL - (2 * PADDING_SEL)

    # 6. QR Code dibuat sebesar mungkin agar proporsional mengisi area,
    #    lalu diposisikan center horizontal & vertikal di area tersebut
    ukuran_qr = min(lebar_area_qr, tinggi_area_qr) * 0.92
    x_qr = titik_tengah_x - (ukuran_qr / 2)
    y_qr = batas_bawah_area_qr + ((tinggi_area_qr - ukuran_qr) / 2)

    pdf_canvas.drawImage(
        gambar_qr_reader, x_qr, y_qr,
        width=ukuran_qr, height=ukuran_qr,
        preserveAspectRatio=True, mask="auto"
    )


# ---------------------------------------------------------------
# FUNGSI UTAMA 1: Membuat dokumen PDF (grid 2x2, multi-halaman)
# ---------------------------------------------------------------
def buat_pdf_barcode_tph(afdeling, blok, tph_awal, tph_akhir) -> io.BytesIO:
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

        gambar_satu_kuadran(pdf_canvas, x_sel, y_sel, afdeling, blok, nomor_tph)

        halaman_penuh = (posisi_dalam_halaman == 3)
        masih_ada_data_berikutnya = (indeks < len(daftar_nomor_tph) - 1)
        if halaman_penuh and masih_ada_data_berikutnya:
            pdf_canvas.showPage()

    pdf_canvas.save()
    buffer_pdf.seek(0)
    return buffer_pdf


# ---------------------------------------------------------------
# FUNGSI: Membuat SATU gambar PNG individual (bingkai + judul + QR)
# ---------------------------------------------------------------
def buat_gambar_barcode_individual(afdeling, blok, nomor_tph) -> Image.Image:
    """
    Membuat satu gambar PNG mandiri untuk satu TPH, dengan desain
    yang konsisten dengan kuadran PDF (bingkai hijau, judul bold
    center, QR Code proporsional di bawahnya).
    """
    kanvas_gambar = Image.new("RGB", (IMG_LEBAR, IMG_TINGGI), "white")
    juru_gambar = ImageDraw.Draw(kanvas_gambar)

    # 1. Bingkai hijau (rounded rectangle)
    juru_gambar.rounded_rectangle(
        [IMG_MARGIN, IMG_MARGIN, IMG_LEBAR - IMG_MARGIN, IMG_TINGGI - IMG_MARGIN],
        radius=IMG_RADIUS, outline=WARNA_HIJAU_HEX, width=IMG_BORDER_TEBAL
    )

    font_baris_1 = ambil_font_bold(60)
    font_baris_2 = ambil_font_bold(50)
    KETEBALAN_STROKE = 2  # Menambah ketebalan agar teks terlihat lebih tegas

    teks_baris_1 = f"AFD {afdeling}"
    teks_baris_2 = f"BLOK {blok} - TPH {nomor_tph}"

    # 2. Baris judul 1 (center horizontal)
    kotak_teks_1 = juru_gambar.textbbox(
        (0, 0), teks_baris_1, font=font_baris_1, stroke_width=KETEBALAN_STROKE
    )
    lebar_teks_1 = kotak_teks_1[2] - kotak_teks_1[0]
    tinggi_teks_1 = kotak_teks_1[3] - kotak_teks_1[1]
    y_baris_1 = IMG_MARGIN + 55
    juru_gambar.text(
        ((IMG_LEBAR - lebar_teks_1) / 2, y_baris_1),
        teks_baris_1, font=font_baris_1, fill=WARNA_TEKS_HEX,
        stroke_width=KETEBALAN_STROKE, stroke_fill=WARNA_TEKS_HEX
    )

    # 3. Baris judul 2 (center horizontal, di bawah baris 1)
    kotak_teks_2 = juru_gambar.textbbox(
        (0, 0), teks_baris_2, font=font_baris_2, stroke_width=KETEBALAN_STROKE
    )
    lebar_teks_2 = kotak_teks_2[2] - kotak_teks_2[0]
    tinggi_teks_2 = kotak_teks_2[3] - kotak_teks_2[1]
    y_baris_2 = y_baris_1 + tinggi_teks_1 + 25
    juru_gambar.text(
        ((IMG_LEBAR - lebar_teks_2) / 2, y_baris_2),
        teks_baris_2, font=font_baris_2, fill=WARNA_TEKS_HEX,
        stroke_width=KETEBALAN_STROKE, stroke_fill=WARNA_TEKS_HEX
    )

    # 4. QR Code — dibuat sebesar mungkin mengisi sisa ruang, lalu center
    payload_qr = f"AFD {afdeling} - BLOK {blok} - TPH {nomor_tph}"
    gambar_qr = buat_qr_code_pil(payload_qr)

    batas_atas_area_qr = y_baris_2 + tinggi_teks_2 + 50
    batas_bawah_area_qr = IMG_TINGGI - IMG_MARGIN - 50
    tinggi_area_qr = batas_bawah_area_qr - batas_atas_area_qr
    lebar_area_qr = IMG_LEBAR - (2 * IMG_MARGIN) - 100

    ukuran_qr = int(min(lebar_area_qr, tinggi_area_qr))
    gambar_qr_resize = gambar_qr.resize((ukuran_qr, ukuran_qr))

    x_qr = (IMG_LEBAR - ukuran_qr) // 2
    y_qr = int(batas_atas_area_qr + ((tinggi_area_qr - ukuran_qr) / 2))
    kanvas_gambar.paste(gambar_qr_resize, (x_qr, y_qr))

    return kanvas_gambar


# ---------------------------------------------------------------
# FUNGSI UTAMA 2: Membuat file ZIP berisi gambar PNG per barcode
# ---------------------------------------------------------------
def buat_zip_gambar_barcode(afdeling, blok, tph_awal, tph_akhir) -> io.BytesIO:
    """
    Membuat satu file ZIP berisi gambar PNG terpisah untuk setiap
    nomor TPH dari tph_awal sampai tph_akhir.
    Mengembalikan buffer ZIP (io.BytesIO) — tidak menyimpan ke disk.
    """
    buffer_zip = io.BytesIO()
    afdeling_bersih = sanitasi_nama_file(afdeling)
    blok_bersih = sanitasi_nama_file(blok)

    with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as file_zip:
        for nomor_tph in range(tph_awal, tph_akhir + 1):
            gambar = buat_gambar_barcode_individual(afdeling, blok, nomor_tph)

            buffer_gambar = io.BytesIO()
            gambar.save(buffer_gambar, format="PNG")
            buffer_gambar.seek(0)

            nama_file = f"AFD{afdeling_bersih}_BLOK{blok_bersih}_TPH{nomor_tph}.png"
            file_zip.writestr(nama_file, buffer_gambar.getvalue())

    buffer_zip.seek(0)
    return buffer_zip


# =================================================================
# ANTARMUKA STREAMLIT (UI)
# =================================================================
st.set_page_config(page_title="Generator QR Code TPH", page_icon="🔖", layout="centered")

st.title("🔖 Generator QR Code Barcode TPH")
st.write(
    "Aplikasi untuk membuat QR Code massal berdasarkan Afdeling, Blok, "
    "dan rentang nomor TPH — dapat diekspor sebagai PDF siap cetak (grid 2x2) "
    "dan/atau gambar PNG terpisah per barcode (dalam satu file ZIP)."
)

st.divider()

# --- Input Afdeling & Blok ---
kolom_1, kolom_2 = st.columns(2)
with kolom_1:
    input_afdeling = st.text_input("Afdeling (AFD)", value="1", help="Contoh: 1, 2, A, dst.")
with kolom_2:
    input_blok = st.text_input("Blok", value="12", help="Contoh: 12, 15A, dst.")

# --- Input Range Nomor TPH ---
st.subheader("Rentang Nomor TPH")
kolom_3, kolom_4 = st.columns(2)
with kolom_3:
    input_tph_awal = st.number_input("TPH Awal", min_value=1, value=1, step=1)
with kolom_4:
    input_tph_akhir = st.number_input("TPH Akhir", min_value=1, value=10, step=1)

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
    if not input_afdeling.strip() or not input_blok.strip():
        st.error("Afdeling dan Blok tidak boleh kosong.")
    elif input_tph_awal > input_tph_akhir:
        st.error("TPH Awal tidak boleh lebih besar dari TPH Akhir.")
    elif not ingin_pdf and not ingin_zip_gambar:
        st.error("Pilih minimal satu format output (PDF dan/atau Gambar ZIP).")
    else:
        afdeling_final = input_afdeling.strip()
        blok_final = input_blok.strip()
        tph_awal_final = int(input_tph_awal)
        tph_akhir_final = int(input_tph_akhir)
        jumlah_tph = tph_akhir_final - tph_awal_final + 1

        # --- Generate PDF (jika dipilih) ---
        if ingin_pdf:
            with st.spinner(f"Membuat PDF untuk {jumlah_tph} QR Code..."):
                buffer_pdf = buat_pdf_barcode_tph(
                    afdeling_final, blok_final, tph_awal_final, tph_akhir_final
                )
            st.success("✅ File PDF berhasil dibuat.")
            st.download_button(
                label="⬇️ Unduh PDF (Print_Barcode_TPH.pdf)",
                data=buffer_pdf,
                file_name="Print_Barcode_TPH.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

        # --- Generate ZIP Gambar Individual (jika dipilih) ---
        if ingin_zip_gambar:
            with st.spinner(f"Membuat {jumlah_tph} gambar PNG individual..."):
                buffer_zip = buat_zip_gambar_barcode(
                    afdeling_final, blok_final, tph_awal_final, tph_akhir_final
                )
            st.success("✅ File ZIP gambar per barcode berhasil dibuat.")
            st.download_button(
                label="⬇️ Unduh Gambar PNG per Barcode (ZIP)",
                data=buffer_zip,
                file_name="Gambar_Barcode_TPH.zip",
                mime="application/zip",
                use_container_width=True,
            )

            # Tampilkan contoh gambar pertama sebagai preview
            with st.expander("👁️ Lihat contoh preview gambar (TPH pertama)"):
                gambar_contoh = buat_gambar_barcode_individual(
                    afdeling_final, blok_final, tph_awal_final
                )
                st.image(gambar_contoh, use_container_width=True)
