import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import csv

ROOT = Path(r"C:\Users\user\Desktop\annette_rppg")
IN_DIR = ROOT / "thesis_pipeline" / "05_cleaned_signal"
OUT_DIR = ROOT / "thesis_pipeline" / "06_fft"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# HR band used in thesis
HR_BAND = (0.7, 3.0)

def estimate_fs_from_raw_csv(stem: str):
    # We use Step 4 raw CSV to infer fps precisely
    raw_csv = ROOT / "thesis_pipeline" / "04_raw_signal" / f"{stem}_raw_rgb_tile25.csv"
    data = np.genfromtxt(raw_csv, delimiter=",", skip_header=1)
    t = data[:, 0]
    dt = float(np.median(np.diff(t)))
    return 1.0 / dt if dt > 0 else 30.0

def fft_summary(cleaned, fs):
    x = cleaned - np.mean(cleaned)
    n = len(x)
    freqs = np.fft.rfftfreq(n, d=1.0/fs)
    mag = np.abs(np.fft.rfft(x))

    mask = (freqs >= HR_BAND[0]) & (freqs <= HR_BAND[1])
    if not np.any(mask):
        return freqs, mag, np.nan, np.nan

    peak_idx = np.argmax(mag[mask])
    peak_hz = float(freqs[mask][peak_idx])
    peak_bpm = float(peak_hz * 60.0)
    return freqs, mag, peak_hz, peak_bpm

def main():
    npys = sorted(IN_DIR.glob("S01_*_cleaned_tile25.npy"))
    if not npys:
        print(f"[ERROR] No cleaned .npy found in {IN_DIR}")
        return

    for npy_path in npys:
        stem = npy_path.stem.replace("_cleaned_tile25", "")
        try:
            cleaned = np.load(npy_path).astype(np.float32)
            fs = estimate_fs_from_raw_csv(stem)

            freqs, mag, peak_hz, peak_bpm = fft_summary(cleaned, fs)

            # Save FFT plot
            png_path = OUT_DIR / f"{stem}_fft.png"
            plt.figure()
            plt.plot(freqs, mag)
            plt.xlim(0, 6)
            plt.xlabel("Frequency (Hz)")
            plt.ylabel("Magnitude (a.u.)")
            if np.isfinite(peak_hz):
                plt.title(f"{stem} – FFT (peak {peak_hz:.2f} Hz = {peak_bpm:.1f} bpm)")
            else:
                plt.title(f"{stem} – FFT")
            plt.tight_layout()
            plt.savefig(png_path, dpi=200)
            plt.close()

            # Save summary CSV
            csv_path = OUT_DIR / f"{stem}_fft_summary.csv"
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["stem", "fs_hz", "band_low_hz", "band_high_hz", "peak_hz", "peak_bpm"])
                w.writerow([stem, f"{fs:.4f}", HR_BAND[0], HR_BAND[1], f"{peak_hz:.6f}", f"{peak_bpm:.3f}"])

            print(f"[OK] Step7 FFT saved for {stem}: {png_path.name}, {csv_path.name}")

        except Exception as e:
            print(f"[FAIL] {stem}: {e}")

if __name__ == "__main__":
    main()
