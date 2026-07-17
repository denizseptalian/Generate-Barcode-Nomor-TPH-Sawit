# ============================================================
# Scan QR Code — Barcode TPH (Streamlit, mobile-first)
# Fokus tunggal: baca QR Code hasil generator barcode TPH secara
# LIVE (kamera menyala terus, tanpa perlu tekan tombol foto),
# dengan hasil & suara otomatis, lalu lanjut ke scan buah sawit.
# ============================================================
import io
import re
import time
import threading

import cv2
import numpy as np
import streamlit as st
from gtts import gTTS
from PIL import Image

# --- streamlit-webrtc: untuk LIVE scan QR Code (tanpa perlu tekan tombol foto) ---
# Kalau belum ter-install, otomatis fallback ke mode foto biasa (kamera snapshot).
try:
    import av
    from streamlit_webrtc import webrtc_streamer, VideoProcessorBase
    _WEBRTC_TERSEDIA = True
except ImportError:
    _WEBRTC_TERSEDIA = False

# ============================================================
# Konfigurasi
# ============================================================
# Isi dengan URL aplikasi "Ripeness Detector" (scan buah sawit) Anda yang
# sudah online, agar tombol "Lanjut Scan Buah Sawit" bisa langsung membukanya.
URL_APP_SCAN_BUAH = ""

st.set_page_config(page_title="Scan QR Barcode TPH", page_icon="📱", layout="centered")

# ============================================================
# CSS — tampilan mobile-first, tema hijau kebun sawit
# ============================================================
st.markdown("""
<style>
:root {
    --hijau-utama: #1B7A3D;
    --hijau-tua: #0D3D1E;
    --hijau-terang: #2ECC71;
    --hijau-muda: #EAF7EE;
}

html, body, [data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #F3FBF5 0%, #FFFFFF 55%);
}
.block-container {
    max-width: 720px !important;
    padding-top: 1.1rem !important;
    padding-bottom: 2.5rem !important;
}
#MainMenu, footer, header { visibility: hidden; }

/* ---- Header ---- */
.app-header {
    text-align: center;
    padding: 1.6rem 1rem 1.3rem 1rem;
    background: linear-gradient(135deg, var(--hijau-utama), var(--hijau-terang));
    border-radius: 22px;
    margin-bottom: 1.3rem;
    box-shadow: 0 8px 22px rgba(27, 122, 61, 0.28);
}
.app-header-emoji { font-size: 2.6rem; line-height: 1; }
.app-header-title {
    color: #ffffff; font-size: 1.55rem; font-weight: 800;
    letter-spacing: .3px; margin-top: .3rem;
}
.app-header-subtitle {
    color: rgba(255,255,255,0.92); font-size: .92rem; margin-top: .15rem;
}

/* ---- Toggle suara ---- */
[data-testid="stToggle"] label p { font-weight: 600; color: var(--hijau-tua); }

/* ---- Kartu status "mencari QR" ---- */
.status-mencari {
    display: flex; align-items: center; justify-content: center; gap: .6rem;
    background: var(--hijau-muda); border: 1.5px dashed var(--hijau-utama);
    border-radius: 16px; padding: .9rem 1rem; margin-top: .8rem;
    color: var(--hijau-tua); font-weight: 600; font-size: .95rem;
}
.spinner-dot {
    width: 12px; height: 12px; border-radius: 50%;
    background: var(--hijau-utama); animation: pulsa 1s ease-in-out infinite;
}
@keyframes pulsa {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: .35; transform: scale(0.7); }
}

/* ---- Badge AFD ---- */
.afd-badge {
    display: inline-block; margin: 1rem auto .6rem auto;
    background: var(--hijau-tua); color: white; font-weight: 700;
    font-size: .95rem; padding: .35rem 1.1rem; border-radius: 999px;
    letter-spacing: .5px;
}
.afd-badge-wrap { text-align: center; }

/* ---- Grid hasil Blok / TPH ---- */
.hasil-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .7rem; margin-bottom: .3rem; }
.hasil-card {
    background: white; border: 2.5px solid var(--hijau-utama); border-radius: 18px;
    padding: 1rem .6rem; text-align: center; box-shadow: 0 4px 14px rgba(0,0,0,.07);
}
.hasil-label {
    font-size: .78rem; font-weight: 700; color: #5b8c6a;
    text-transform: uppercase; letter-spacing: 1.2px;
}
.hasil-nilai { font-size: 2.1rem; font-weight: 800; color: var(--hijau-tua); margin-top: .1rem; }

/* ---- Tombol ---- */
[data-testid="stButton"] button, [data-testid="stLinkButton"] a {
    min-height: 3.2rem; font-size: 1.05rem; font-weight: 700;
    border-radius: 14px; border: none;
    background: var(--hijau-utama); color: white !important;
    box-shadow: 0 4px 12px rgba(27,122,61,.28);
    transition: transform .08s ease;
}
[data-testid="stButton"] button:active { transform: scale(0.98); }
[data-testid="stButton"] button:hover, [data-testid="stLinkButton"] a:hover {
    background: var(--hijau-tua); color: white !important;
}

/* ---- Selector mode scan (segmented control / radio fallback) ---- */
[data-testid="stSegmentedControl"] button[aria-checked="true"] {
    background: var(--hijau-utama) !important; color: white !important;
    border-color: var(--hijau-utama) !important;
}
[data-testid="stSegmentedControl"] button {
    border-radius: 12px !important; font-weight: 700 !important;
}
div[role="radiogroup"] { gap: .6rem; }
div[role="radiogroup"] label {
    border: 2px solid var(--hijau-utama); border-radius: 12px;
    padding: .3rem .8rem; font-weight: 700;
}

/* ---- Alert box rounded ---- */
[data-testid="stAlert"] { border-radius: 16px; }

/* ---- Kamera live (streamlit-webrtc): dibuat besar/full, sudut membulat ---- */
iframe[title*="webrtc"], iframe[title*="streamlit_webrtc"] {
    width: 100% !important; min-height: 62vh !important;
    border-radius: 20px !important; box-shadow: 0 6px 18px rgba(0,0,0,.14);
}

/* ---- Kamera fallback (camera_input) ---- */
[data-testid="stCameraInput"] img { border-radius: 16px !important; width: 100% !important; }
[data-testid="stCameraInput"] button {
    min-height: 3.2rem; font-size: 1.1rem; border-radius: 14px;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# Deteksi & urai QR Code
# ============================================================
_qr_detector = cv2.QRCodeDetector()

# Pola payload QR sesuai format generator: "AFD {Afdeling} - BLOK {Blok} - TPH {Nomor}"
_POLA_QR = re.compile(r"AFD\s*([^\-]+?)\s*-\s*BLOK\s*([^\-]+?)\s*-\s*TPH\s*(.+)", re.IGNORECASE)


def baca_qr(bgr):
    """Coba deteksi & decode QR Code pada gambar (mendukung >1 QR sekaligus).
    Return teks payload QR pertama yang berhasil dibaca, atau None kalau
    tidak ada QR Code yang terdeteksi sama sekali."""
    try:
        retval, decoded_info, _, _ = _qr_detector.detectAndDecodeMulti(bgr)
        if retval:
            for teks in decoded_info:
                if teks:
                    return teks
    except Exception:
        pass
    try:
        data, _, _ = _qr_detector.detectAndDecode(bgr)
        return data or None
    except Exception:
        return None


def urai_payload_qr(teks):
    """Urai payload QR menjadi dict {afdeling, blok, tph}, atau None kalau
    formatnya tidak cocok dengan pola generator barcode TPH."""
    if not teks:
        return None
    m = _POLA_QR.search(teks)
    if not m:
        return None
    afdeling, blok, tph = (g.strip() for g in m.groups())
    return {"afdeling": afdeling, "blok": blok, "tph": tph}


# ============================================================
# TTS — suara Bahasa Indonesia
# ============================================================
def eja(teks):
    """Eja per karakter supaya jelas didengar: 'P67' -> 'P, 6, 7'."""
    return ", ".join(teks)


@st.cache_data(show_spinner=False)
def buat_audio(kalimat: str) -> bytes:
    tts = gTTS(text=kalimat, lang="id", slow=False)
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    return buf.getvalue()


# Kalimat lanjutan yang disambungkan di akhir pembacaan suara, supaya alur
# kerja lapangan lanjut otomatis: scan QR -> lalu scan buah sawit.
KALIMAT_LANJUT_BUAH = ("Silakan lanjutkan, arahkan kamera ke buah sawit "
                       "untuk pemindaian berikutnya.")


def tombol_lanjut_scan_buah():
    """Bagian UI setelah hasil pembacaan: ajakan lanjut ke tahap scan buah sawit."""
    st.divider()
    st.subheader("➡️ Lanjut ke Pemindaian Buah Sawit")
    if URL_APP_SCAN_BUAH:
        st.link_button("🍇 Buka Aplikasi Scan Buah Sawit", URL_APP_SCAN_BUAH,
                       use_container_width=True)
    else:
        st.info("Tombol ini belum terhubung ke aplikasi scan buah sawit. Isi "
                "variabel `URL_APP_SCAN_BUAH` di bagian atas kode dengan alamat "
                "aplikasi Ripeness Detector Anda yang sudah online.")


def _tampilkan_kartu_hasil(data_qr):
    """Render kartu hasil (AFD badge + grid Blok/TPH) — dipakai live & foto."""
    st.markdown(f"""
    <div class="afd-badge-wrap"><span class="afd-badge">AFD {data_qr['afdeling']}</span></div>
    <div class="hasil-grid">
        <div class="hasil-card">
            <div class="hasil-label">Blok</div>
            <div class="hasil-nilai">{data_qr['blok']}</div>
        </div>
        <div class="hasil-card">
            <div class="hasil-label">TPH</div>
            <div class="hasil-nilai">{data_qr['tph']}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _bacakan_hasil_qr(data_qr):
    kalimat = (
        f"Terdeteksi lewat kode Q R. Afdeling {eja(data_qr['afdeling'])}. "
        f"Nomor Blok, {eja(data_qr['blok'])}. "
        f"Nomor T P H, {eja(data_qr['tph'])}. " + KALIMAT_LANJUT_BUAH
    )
    try:
        st.audio(buat_audio(kalimat), format="audio/mp3", autoplay=True)
    except Exception:
        st.caption("🔇 Suara gagal dibuat (cek koneksi internet).")


# ============================================================
# LIVE SCAN QR CODE — pakai streamlit-webrtc (kamera menyala terus,
# QR langsung terbaca otomatis begitu terdeteksi, tanpa tekan tombol foto)
# ============================================================
if _WEBRTC_TERSEDIA:
    def get_ice_servers():
        """Ambil daftar ICE server (STUN/TURN) untuk koneksi WebRTC.

        PENTING: Streamlit Community Cloud SERING gagal konek kalau cuma
        pakai STUN saja ('Connection is taking longer than expected...')
        karena jaringannya memblokir koneksi WebRTC langsung — di situasi
        begitu, WAJIB ada TURN server.

        Dipakai TURN gratis publik (Open Relay Project, tanpa perlu
        daftar/akun) + STUN Google sebagai pelengkap.
        """
        return [
            {"urls": "stun:stun.l.google.com:19302"},
            {"urls": "turn:openrelay.metered.ca:80",
             "username": "openrelayproject", "credential": "openrelayproject"},
            {"urls": "turn:openrelay.metered.ca:443",
             "username": "openrelayproject", "credential": "openrelayproject"},
            {"urls": "turn:openrelay.metered.ca:443?transport=tcp",
             "username": "openrelayproject", "credential": "openrelayproject"},
        ]

    class QRVideoProcessor(VideoProcessorBase):
        """Proses tiap frame video: cari & decode QR Code secara live.
        Hasil disimpan di atribut (dengan lock) supaya bisa dibaca thread
        utama Streamlit untuk ditampilkan + dibacakan suaranya."""

        def __init__(self):
            self.lock = threading.Lock()
            self.hasil_qr = None       # dict {afdeling, blok, tph} kalau ketemu
            self.teks_mentah = None    # payload QR mentah (utk cek duplikat)
            self._hitung_frame = 0

        def recv(self, frame):
            img = frame.to_ndarray(format="bgr24")

            # Proses tiap 3 frame saja (hemat beban server)
            self._hitung_frame += 1
            if self._hitung_frame % 3 == 0:
                teks = baca_qr(img)
                data = urai_payload_qr(teks)
                with self.lock:
                    self.teks_mentah = teks
                    self.hasil_qr = data
            else:
                with self.lock:
                    data = self.hasil_qr

            if data:
                label = f"QR TERBACA - AFD{data['afdeling']} BLOK{data['blok']} TPH{data['tph']}"
                cv2.rectangle(img, (0, 0), (img.shape[1], 50), (27, 122, 61), -1)
                cv2.putText(img, label, (12, 34), cv2.FONT_HERSHEY_SIMPLEX,
                           0.8, (255, 255, 255), 2)

            return av.VideoFrame.from_ndarray(img, format="bgr24")


def _render_scan_qr_live(suara_aktif_qr):
    """Live scan: kamera menyala terus, QR otomatis terbaca begitu terdeteksi
    di frame — TIDAK perlu tekan tombol ambil foto."""
    webrtc_ctx = webrtc_streamer(
        key="scan-qr-live",
        video_processor_factory=QRVideoProcessor,
        rtc_configuration={"iceServers": get_ice_servers()},
        media_stream_constraints={
            "video": {"facingMode": "environment", "width": {"ideal": 1280}},
            "audio": False,
        },
        async_processing=True,
    )

    kotak_hasil = st.empty()
    KEY_TERAKHIR = "qr_live_teks_terakhir_dibacakan"

    if webrtc_ctx.state.playing and webrtc_ctx.video_processor:
        data_qr, teks_qr = None, None
        for _ in range(15):
            with webrtc_ctx.video_processor.lock:
                data_qr = webrtc_ctx.video_processor.hasil_qr
                teks_qr = webrtc_ctx.video_processor.teks_mentah
            if data_qr or not webrtc_ctx.state.playing:
                break
            time.sleep(0.3)

        sudah_dibacakan = st.session_state.get(KEY_TERAKHIR) == teks_qr

        if data_qr:
            with kotak_hasil.container():
                st.success("📡 QR Code terbaca otomatis!")
                _tampilkan_kartu_hasil(data_qr)

                if not sudah_dibacakan:
                    st.session_state[KEY_TERAKHIR] = teks_qr
                    if suara_aktif_qr:
                        _bacakan_hasil_qr(data_qr)

                tombol_lanjut_scan_buah()
                if st.button("🔄 Scan QR Berikutnya", use_container_width=True):
                    st.session_state.pop(KEY_TERAKHIR, None)
                    st.rerun()
        else:
            with kotak_hasil.container():
                st.markdown("""
                <div class="status-mencari">
                    <div class="spinner-dot"></div>
                    Mencari QR Code... arahkan kamera lebih dekat/jelas.
                </div>
                """, unsafe_allow_html=True)
            st.rerun()


def _render_scan_qr_mode_foto(suara_aktif_qr):
    """Fallback: kamera snapshot (tekan tombol foto) + upload gambar.
    Dipakai otomatis kalau streamlit-webrtc belum ter-install."""
    tab_kamera_qr, tab_upload_qr = st.tabs(["📷 Kamera", "🖼️ Upload"])
    img_file_qr = None
    with tab_kamera_qr:
        foto_qr = st.camera_input("Arahkan ke QR Code, lalu ambil foto",
                                  label_visibility="collapsed", key="kamera_qr")
        if foto_qr is not None:
            img_file_qr = foto_qr
    with tab_upload_qr:
        up_qr = st.file_uploader("Pilih foto QR Code", type=["png", "jpg", "jpeg", "bmp"],
                                 label_visibility="collapsed", key="upload_qr")
        if up_qr is not None:
            img_file_qr = up_qr

    if img_file_qr is None:
        st.info("📷 Ambil foto QR Code atau upload gambar untuk memulai.")
        return

    pil_img_qr = Image.open(img_file_qr).convert("RGB")
    bgr_qr = cv2.cvtColor(np.array(pil_img_qr), cv2.COLOR_RGB2BGR)

    with st.spinner("Membaca QR Code..."):
        teks_qr = baca_qr(bgr_qr)
        data_qr = urai_payload_qr(teks_qr)

    if data_qr:
        st.success("📡 QR Code terbaca!")
        _tampilkan_kartu_hasil(data_qr)
        if suara_aktif_qr:
            _bacakan_hasil_qr(data_qr)
        tombol_lanjut_scan_buah()
    elif teks_qr:
        st.warning(f"QR Code terbaca, tapi formatnya tidak dikenali: `{teks_qr}`. "
                   "Pastikan ini QR Code hasil generator barcode TPH.")
    else:
        st.error("Tidak ada QR Code terdeteksi pada foto. Pastikan QR Code terlihat "
                 "jelas, tidak blur, dan cukup dekat/terang.")


# ============================================================
# UI — mobile-first
# ============================================================
st.markdown("""
<div class="app-header">
    <div class="app-header-title">Scan QR Code</div>
    <div class="app-header-subtitle">Barcode TPH — Kebun Sawit</div>
    <div class="app-header-emoji" style="margin-top: 15px;">📱</div>
</div>
""", unsafe_allow_html=True)

suara_aktif_qr = st.toggle("🔊 Bacakan hasil lewat suara", value=True, key="suara_qr")

PILIHAN_MODE = ["🔴 Live (Otomatis)", "📷 Foto / Upload"]

# Pakai st.segmented_control kalau tersedia (Streamlit versi baru, tampilan
# lebih rapi), fallback ke radio horizontal kalau versi Streamlit lama.
if hasattr(st, "segmented_control"):
    mode_scan = st.segmented_control(
        "Metode Scan", PILIHAN_MODE, default=PILIHAN_MODE[0],
        label_visibility="collapsed", key="mode_scan_qr",
    )
    if not mode_scan:
        mode_scan = PILIHAN_MODE[0]
else:
    mode_scan = st.radio(
        "Metode Scan", PILIHAN_MODE, horizontal=True,
        label_visibility="collapsed", key="mode_scan_qr",
    )

if mode_scan == PILIHAN_MODE[0]:
    if _WEBRTC_TERSEDIA:
        st.caption("Arahkan kamera langsung ke stiker QR Code. Begitu terdeteksi, "
                   "hasil & suara langsung muncul otomatis — tidak perlu jepret foto.")
        _render_scan_qr_live(suara_aktif_qr)
        st.caption("⚠️ Kamera live tidak muncul / macet / koneksi gagal? "
                   f"Pilih **{PILIHAN_MODE[1]}** di atas sebagai opsi cadangan.")
    else:
        st.warning("Live-scan (kamera menyala terus tanpa perlu tekan tombol foto) "
                   "butuh library `streamlit-webrtc` dan `av`. Tambahkan keduanya ke "
                   "`requirements.txt` lalu redeploy untuk mengaktifkan mode ini. "
                   f"Untuk sementara, pilih **{PILIHAN_MODE[1]}** di atas:")
else:
    st.caption("Ambil foto QR Code lewat kamera, atau upload gambar yang sudah ada.")
    _render_scan_qr_mode_foto(suara_aktif_qr)
