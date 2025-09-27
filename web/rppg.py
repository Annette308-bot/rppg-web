"""
Real-World rPPG Demo: Face + Palm (S01)
- Estimates HR (bpm), HRV (RMSSD, SDNN), Respiration (br/min)
- Computes windowed SpO2 trend index using Red/Green AC/DC ratio
- Saves summary_metrics.csv and plots into outputs/real_demo_noGT/analysis/

Dependencies:
    pip install numpy opencv-python matplotlib pandas
"""

import os
from pathlib import Path
import numpy as np
import cv2
import pandas as pd
import matplotlib.pyplot as plt

# --------------------------
# Configuration (edit if needed)
# --------------------------
SUBJECT = "S01"
ROOT = Path(".")
FACE_DIR = ROOT / f"Data/raw/my_phone/{SUBJECT}/face"
PALM_DIR = ROOT / f"Data/raw/my_phone/{SUBJECT}/palm"
OUTDIR = ROOT / "outputs" / "real_demo_noGT" / "analysis"
OUTDIR.mkdir(parents=True, exist_ok=True)

EXPECTED_FPS = 30            # fallback if video FPS not readable
ROI_FRAC = 0.33              # central square ROI fraction of min(H, W)
MIN_SECONDS_FOR_HR = 5       # need >=5s data to estimate spectral HR
MIN_SECONDS_FOR_RR = 10      # need >=10s data to estimate respiration

# --------------------------
# Helper functions
# --------------------------
def center_square_roi(frame, frac=0.33):
    """Return central square ROI from frame."""
    h, w = frame.shape[:2]
    s = int(min(h, w) * frac)
    y1 = h // 2 - s // 2; y2 = y1 + s
    x1 = w // 2 - s // 2; x2 = x1 + s
    return frame[y1:y2, x1:x2]

def moving_average(x, k):
    if k <= 1:
        return x.copy()
    c = np.cumsum(np.insert(x, 0, 0.0))
    return (c[k:] - c[:-k]) / float(k)

def detrend_signal(x, fs, win_sec=3.0):
    """Simple moving-average detrend with edge padding."""
    k = int(max(1, round(fs * win_sec)))
    if k % 2 == 0: k += 1
    pad = k // 2
    xpad = np.pad(x, (pad, pad), mode="edge")
    trend = moving_average(xpad, k)
    if len(trend) < len(x):
        trend = np.pad(trend, (0, len(x) - len(trend)), mode="edge")
    return x - trend[:len(x)]

def spectral_peak_bpm(x, fs, fmin=0.7, fmax=3.0):
    """
    Find dominant frequency in band [fmin, fmax] Hz -> return bpm.
    Uses simple Hanning window + rFFT.
    """
    n = len(x)
    if n < int(fs * MIN_SECONDS_FOR_HR):
        return np.nan
    x = x - np.mean(x)
    X = np.fft.rfft(x * np.hanning(n))
    freqs = np.fft.rfftfreq(n, d=1.0/fs)
    band = (freqs >= fmin) & (freqs <= fmax)
    if not np.any(band):
        return np.nan
    idx = np.argmax(np.abs(X[band]))
    f_peak = freqs[band][idx]
    return f_peak * 60.0

def detect_peaks(x, fs, min_distance_s=0.4):
    """
    Naive peak detector on z-scored signal with positive threshold.
    """
    xz = (x - np.mean(x)) / (np.std(x) + 1e-8)
    n = len(xz)
    min_dist = int(min_distance_s * fs)
    peaks = []
    last = -min_dist
    for i in range(1, n - 1):
        if xz[i] > xz[i - 1] and xz[i] > xz[i + 1] and xz[i] > 0.3:
            if i - last >= min_dist:
                peaks.append(i)
                last = i
    return np.array(peaks, dtype=int)

def hrv_time_domain(peaks, fs):
    """
    Returns RMSSD (s), SDNN (s), and IBI array (s).
    """
    if peaks is None or len(peaks) < 3:
        return np.nan, np.nan, np.array([])
    ibi = np.diff(peaks) / float(fs)  # seconds
    if len(ibi) < 2:
        return np.nan, np.nan, ibi
    sdnn = float(np.std(ibi, ddof=0))
    rmssd = float(np.sqrt(np.mean(np.square(np.diff(ibi)))))
    return rmssd, sdnn, ibi

def respiration_rate_from_signal(x, fs, fmin=0.1, fmax=0.5):
    """
    Estimate respiration rate via spectral peak in low-frequency band.
    """
    n = len(x)
    if n < int(fs * MIN_SECONDS_FOR_RR):
        return np.nan
    x = x - np.mean(x)
    X = np.fft.rfft(x * np.hanning(n))
    freqs = np.fft.rfftfreq(n, d=1.0/fs)
    band = (freqs >= fmin) & (freqs <= fmax)
    if not np.any(band):
        return np.nan
    idx = np.argmax(np.abs(X[band]))
    f_peak = freqs[band][idx]
    return f_peak * 60.0

def spo2_trend_rg_simple(red_raw, green_raw, fs, win_sec=10.0, hop_sec=5.0, detrend_win_sec=3.0):
    """
    Windowed SpO2 trend index:
        R_RG = (AC_red/DC_red) / (AC_green/DC_green)
    AC = std of detrended signal in the window
    DC = mean of raw signal in the window
    Returns median across windows as per-clip value + windowed series.
    """
    red_raw   = np.asarray(red_raw, dtype=float)
    green_raw = np.asarray(green_raw, dtype=float)

    # detrend to approximate AC component
    red_det   = detrend_signal(red_raw,   fs, detrend_win_sec)
    green_det = detrend_signal(green_raw, fs, detrend_win_sec)

    N    = len(red_raw)
    W    = int(max(1, round(win_sec * fs)))
    H    = int(max(1, round(hop_sec * fs)))
    idxs = range(0, max(1, N - W + 1), H)

    series, times = [], []
    for i in idxs:
        j = i + W
        rr_raw = red_raw[i:j];   gg_raw = green_raw[i:j]
        rr_det = red_det[i:j];   gg_det = green_det[i:j]
        if len(rr_raw) < W or len(gg_raw) < W:
            continue
        DC_r = float(np.mean(rr_raw)); DC_g = float(np.mean(gg_raw))
        AC_r = float(np.std(rr_det, ddof=0)); AC_g = float(np.std(gg_det, ddof=0))
        if DC_r <= 1e-6 or DC_g <= 1e-6 or AC_g <= 1e-12:
            continue
        RRG = (AC_r / DC_r) / (AC_g / DC_g)
        series.append(RRG)
        times.append((i + j) / 2.0 / fs)

    RRG_series = np.array(series) if series else np.array([np.nan])
    RRG_clip   = float(np.nanmedian(RRG_series))
    return {"times": np.array(times), "RRG_series": RRG_series, "RRG_clip": RRG_clip}

# --------------------------
# Video processing
# --------------------------
def process_video(video_path, fps_expected=EXPECTED_FPS, roi_frac=ROI_FRAC):
    p = Path(video_path)
    cap = cv2.VideoCapture(str(p))
    if not cap.isOpened():
        return {"ok": False, "reason": "open_failed", "file": str(p)}

    fs = cap.get(cv2.CAP_PROP_FPS)
    if not fs or fs <= 0:
        fs = fps_expected

    greens, reds = [], []
    frames = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames += 1
        roi = center_square_roi(frame, frac=roi_frac)
        b, g, r = cv2.split(roi)
        greens.append(float(np.mean(g)))
        reds.append(float(np.mean(r)))

    cap.release()

    greens = np.array(greens, dtype=float)
    reds   = np.array(reds,   dtype=float)

    if len(greens) < fs * MIN_SECONDS_FOR_HR:
        return {"ok": False, "reason": "too_short", "file": str(p), "frames": len(greens), "fs": fs}

    # detrend for physiological estimation
    g_det = detrend_signal(greens, fs, win_sec=3.0)

    # HR (bpm) via spectral peak in heart band
    hr_bpm = spectral_peak_bpm(g_det, fs, fmin=0.7, fmax=3.0)

    # HRV via simple peak detection
    peaks = detect_peaks(g_det, fs, min_distance_s=0.4)
    rmssd, sdnn, _ = hrv_time_domain(peaks, fs)

    # Respiration (br/min)
    rr_bpm = respiration_rate_from_signal(g_det, fs, fmin=0.1, fmax=0.5)

    # SpO2 trend index (median of windowed RRG)
   # --- Simple SpO2 Trend Index (AC/DC ratio, one value for whole clip) ---
    AC_r, DC_r = np.std(reds), np.mean(reds)
    AC_g, DC_g = np.std(greens), np.mean(greens)
    if DC_r > 0 and DC_g > 0:
        spo2_index = (AC_r / DC_r) / (AC_g / DC_g)
    else:
        spo2_index = np.nan
    return {
        "ok": True,
        "file": str(p),
        "fs": float(fs),
        "frames": int(frames),
        "hr_bpm": float(hr_bpm) if hr_bpm == hr_bpm else np.nan,
        "rmssd": float(rmssd) if rmssd == rmssd else np.nan,
        "sdnn": float(sdnn) if sdnn == sdnn else np.nan,
        "rr_bpm": float(rr_bpm) if rr_bpm == rr_bpm else np.nan,
        "spo2_index": float(spo2_index) if spo2_index == spo2_index else np.nan,
    }

# --------------------------
# Main
# --------------------------
def main():
    print("Looking for videos in:\n  FACE:", FACE_DIR, "\n  PALM:", PALM_DIR)
    pairs = [
        ("face", "rest",     FACE_DIR / "S01_rest_face.mp4"),
        ("face", "exercise", FACE_DIR / "S01_exercise_face.mp4"),
        ("face", "breath",   FACE_DIR / "S01_breath_face.mp4"),
        ("palm", "rest",     PALM_DIR / "S01_rest_palm.mp4"),
        ("palm", "exercise", PALM_DIR / "S01_exercise_palm.mp4"),
        ("palm", "breath",   PALM_DIR / "S01_breath_palm.mp4"),
    ]

    rows = []
    for modality, clip, path in pairs:
        if not Path(path).exists():
            print("[missing]", path)
            continue
        print("[proc]", modality, clip, Path(path).name)
        r = process_video(path)
        if r.get("ok"):
            rows.append({
                "subject": SUBJECT,
                "modality": modality,
                "clip": clip,
                "file": r["file"],
                "fs": r["fs"],
                "frames": r["frames"],
                "hr_bpm": r["hr_bpm"],
                "rmssd": r["rmssd"],
                "sdnn": r["sdnn"],
                "rr_bpm": r["rr_bpm"],
                "spo2_index": r["spo2_index"],
            })
        else:
            print("[warn] skipping:", r.get("reason"), "for", path)

    if not rows:
        print("[ERROR] No results. Check file paths and codecs.")
        return

    df = pd.DataFrame(rows)
    csv_path = OUTDIR / "summary_metrics.csv"
    df.to_csv(csv_path, index=False)
    print("[ok] wrote", csv_path)

    # ---- Plots ----
    plt.rcParams["figure.figsize"] = (8, 4)

    def make_plot(metric, title, fname, ylabel):
        plt.figure()
        # Keep order "rest, exercise, breath" if present
        order = ["rest", "exercise", "breath"]
        for modality in ["face", "palm"]:
            dd = df[df["modality"] == modality]
            dd = dd.set_index("clip").reindex(order).reset_index()
            if dd[metric].notna().any():
                labels = dd["clip"] + "_" + modality
                vals = dd[metric].values
                plt.bar(labels, vals)
        plt.title(title)
        plt.ylabel(ylabel)
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        plt.savefig(OUTDIR / fname, dpi=220)
        plt.close()

    make_plot("hr_bpm", "Estimated HR (bpm) per clip", "hr_per_clip.png", "HR (bpm)")
    make_plot("rr_bpm", "Estimated Respiration (breaths/min) per clip", "rr_per_clip.png", "Breaths/min")
    make_plot("rmssd", "HRV (RMSSD) per clip", "hrv_rmssd_per_clip.png", "RMSSD (s)")
    make_plot("spo2_index", "SpO₂ Trend Index (R/G AC/DC) per clip", "spo2_trend_per_clip.png", "Index (unitless)")

    print("[ok] plots saved in", OUTDIR)

if __name__ == "__main__":
    main()
