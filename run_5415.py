"""
run_5415.py  (Orca version)
Inputs from Orca:  offsets.csv and the three inputs draft, wetted surface, waterline length.
Needs in the same folder: ModifiedMichellCw.py, offsets.csv
Writes: results.csv, results_meta.json
"""
import json, hashlib
import numpy as np
from scipy.interpolate import RegularGridInterpolator
import ModifiedMichellCw as MM

# ============ SETTINGS: copy these from Orca for the hull you exported =============
OFFSETS_FILE = "offsets.csv"
DRAFT_ORCA = 0.2477      # m   draft used in Orca (must equal the last depth in offsets.csv)
S_ORCA = 4.573           # m^2 Orca wetted surface area at that draft
LWL_ORCA = 5.7271       # m   Orca waterline length; None = use the x-range of offsets.csv
RHO = 998.0
NU = 1.004e-6           # m^2/s
G = 9.81
K_FORM = 0.15
FN_START, FN_STOP, FN_STEP = 0.05, 0.45, 0.01
NX, NZ, N_ANGLES = 301, 51, 400      # NX must be odd
RESULTS_FILE, META_FILE = "results.csv", "results_meta.json"
# ===================================================================================

MM.g = G
trapz = getattr(np, "trapezoid", None) or np.trapz


def main():
    raw = np.loadtxt(OFFSETS_FILE, delimiter=",")
    z_in, x_in, y_in = raw[0, 1:], raw[1:, 0], raw[1:, 1:]
    if abs(z_in[0]) > 1e-9 or np.any(np.diff(z_in) <= 0) or np.any(np.diff(x_in) <= 0) or np.isnan(y_in).any():
        raise ValueError("offsets.csv: first depth must be 0, depths and x strictly increasing, no blanks")
    T, L_file = z_in.max(), x_in.max() - x_in.min()
    if abs(T / DRAFT_ORCA - 1) > 0.01:
        raise ValueError(f"offsets.csv deepest depth {T:.4f} m != DRAFT_ORCA {DRAFT_ORCA} m. Wrong file or units?")
    L = LWL_ORCA or L_file
    if NX % 2 == 0:
        raise ValueError("NX must be odd")

    X = np.linspace(0, L_file, NX); depth = np.linspace(0, T, NZ)
    f = RegularGridInterpolator((x_in - x_in.min(), z_in), y_in, bounds_error=False, fill_value=0.0)
    XX, DD = np.meshgrid(X, depth, indexing="ij")
    Y = f(np.stack([XX, DD], -1)); Z = -depth

    vol = 2 * trapz(trapz(Y, depth, axis=1), X)
    print(f"L={L:.4f} m  T={T:.4f} m  max beam={2*Y.max():.4f} m  volume={vol:.4f} m^3  S(Orca)={S_ORCA} m^2")
    print(f"Cb = {vol/(L*2*Y.max()*T):.3f}   <- sanity check against Orca's block coefficient\n")

    rows = []
    print(f"{'Fn':>6} {'U':>8} {'Rw (N)':>11} {'Cw':>11} {'Ct':>11}")
    for Fn in np.arange(FN_START, FN_STOP + FN_STEP / 2, FN_STEP):
        U = Fn * np.sqrt(G * L)
        Rw = MM.ModMichell(Y, U, X, Z, RHO, N_ANGLES)
        Cw = Rw / (0.5 * RHO * U**2 * S_ORCA)
        CF = 0.075 / (np.log10(U * L / NU) - 2) ** 2
        Ct = (1 + K_FORM) * CF + Cw
        rows.append((Fn, U, Rw, Cw, CF, Ct))
        print(f"{Fn:6.3f} {U:8.4f} {Rw:11.4f} {Cw:11.3e} {Ct:11.3e}")
    np.savetxt(RESULTS_FILE, np.array(rows), delimiter=",", header="Fn,U_m_per_s,Rw_N,Cw,CF,Ct", comments="")
    json.dump(dict(hull_id=hashlib.sha1(open(OFFSETS_FILE, "rb").read()).hexdigest()[:10], S=S_ORCA, L=L, T=T,
                   B=2 * float(Y.max()), rho=RHO, k=K_FORM), open(META_FILE, "w"), indent=2)
    print(f"\nsaved {RESULTS_FILE}, {META_FILE}")


if __name__ == "__main__":
    main()
