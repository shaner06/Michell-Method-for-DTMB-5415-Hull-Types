"""
compare_cw.py  (Orca version)  - reads results.csv + results_meta.json written by run_5415.py.
S, L, rho, k come from there, so nothing has to be re-typed. Needs olivieri_ct.csv (Fr,CTM,Re,CF).
Stops if offsets.csv was changed after the results were made.
Other tank/CFD data (same Fr,CTM,Re,CF layout as olivieri_ct.csv) is read straight from the files named in
OTHER_EXP_FILES and CFD_FILES below; with both lists empty the script behaves exactly as before.
"""
import json, hashlib, os
import numpy as np

# ============ SETTINGS: same style as run_5415_1.py =============================
EXP_FILE = "olivieri_ct.csv"     # tank data, columns Fr, CTM, Re, CF (INSEAN 2340 = DTMB 5415 model)
OFFSETS_FILE = "offsets.csv"     # same file run_5415.py used (checked for staleness)
RESULTS_FILE = "results.csv"     # written by run_5415.py
META_FILE = "results_meta.json"  # written by run_5415.py (holds S, L, T, B, rho, k)
OUT_PNG = "cw_comparison.png"
OUT_CSV = "cw_comparison.csv"
K_EXP = 0.15                     # form factor to strip friction from the tank data; None = Prohaska estimate
PROHASKA_FR = (0.15, 0.20)       # Fn range for the Prohaska fit
REF_L, REF_B, REF_T = 5.72, 0.76, 0.248   # m, DTMB 5415 model (only used for the "different hull" warning)
OTHER_EXP_FILES = ["ahmed_2023_exp.csv"]   # more tank data
CFD_FILES = ["ahmed_2023_cfd.csv"]         # CFD results
FR_MIN_OTHER = 0.10  # ignore points below this Fn in the files above (the 2023 low-speed values are not credible); None = use all
# ===================================================================================


def prohaska_k(fr, ctm, cf, lo, hi):
    m = (fr >= lo) & (fr <= hi)
    return np.polyfit(fr[m] ** 4 / cf[m], ctm[m] / cf[m], 1)[1] - 1.0


def load_ct_csv(path, k, fr_min):
    """Read a Fr,CTM,Re,CF file (same layout as olivieri_ct.csv). Returns Fn, Cw, Ct; repeats at one Fn are averaged.
    Columns are found by header name (any order, Excel's UTF-8 BOM is tolerated). Raises ValueError with a plain
    message if the file has no usable points, so main() can skip it instead of crashing."""
    raw = np.genfromtxt(path, delimiter=",", names=True, encoding="utf-8-sig", dtype=float)
    cols = {n.lower(): np.atleast_1d(raw[n]).astype(float) for n in raw.dtype.names}
    if not all(c in cols for c in ("fr", "ctm", "cf")):
        raise ValueError(f"header must contain Fr, CTM, Re, CF - found {list(raw.dtype.names)}")
    fr, ctm, cf = cols["fr"], cols["ctm"], cols["cf"]
    ok = np.isfinite(fr) & np.isfinite(ctm) & np.isfinite(cf)          # drop blank / non-numeric rows
    fr, ctm, cf = fr[ok], ctm[ok], cf[ok]
    if fr.size == 0:
        raise ValueError("no numeric data rows found")
    keys = np.round(fr, 3); u = np.unique(keys)
    fr_u, ct_u, cf_u = (np.array([a[keys == x].mean() for x in u]) for a in (fr, ctm, cf))
    keep = fr_u >= (fr_min or 0.0)
    if not keep.any():
        raise ValueError(f"no points at Fn >= {fr_min} (the file covers Fn {fr_u.min():.3f} to {fr_u.max():.3f}); "
                         f"lower FR_MIN_OTHER or check the Fr column")
    return fr_u[keep], (ct_u - (1 + k) * cf_u)[keep], ct_u[keep]


def main():
    meta = json.load(open(META_FILE))
    if hashlib.sha1(open(OFFSETS_FILE, "rb").read()).hexdigest()[:10] != meta["hull_id"]:
        raise RuntimeError("STALE: offsets.csv changed since results.csv was made. Rerun run_5415_1.py.")
    print(f"hull {meta['hull_id']}: L={meta['L']:.3f} B={meta['B']:.3f} T={meta['T']:.3f} S={meta['S']:.3f}")
    same = all(abs(meta[k] / r - 1) < 0.1 for k, r in (("L", REF_L), ("B", REF_B), ("T", REF_T)))
    if not same:
        print("*** WARNING: not the DTMB 5415 model - tank curve is a reference only ***")

    raw = np.loadtxt(EXP_FILE, delimiter=",", skiprows=1)
    fr, ctm, re, cf = raw.T
    keys = np.round(fr, 3); u = np.unique(keys)
    fr_e, ctm_e, cf_e = (np.array([a[keys == x].mean() for x in u]) for a in (fr, ctm, cf))
    k = K_EXP if K_EXP is not None else prohaska_k(fr, ctm, cf, *PROHASKA_FR)
    cw_exp = ctm_e - (1 + k) * cf_e

    res = np.loadtxt(RESULTS_FILE, delimiter=",", skiprows=1)
    fr_t, cw_th, ct_th = res[:, 0], res[:, 3], res[:, 5]
    cw_x = np.interp(fr_t, fr_e, cw_exp)
    np.savetxt(OUT_CSV, np.column_stack([fr_t, cw_th, cw_x, ct_th]), delimiter=",",
               header="Fn,Cw_Michell,Cw_exp,Ct_Michell", comments="")
    print(f"\n{'Fn':>6} {'Cw Michell':>12} {'Cw exp':>12} {'ratio':>8}")
    for f, a, b in zip(fr_t, cw_th, cw_x):
        print(f"{f:6.3f} {a:12.4e} {b:12.4e} {a / b if b > 0 else float('nan'):8.2f}")

    # ---- other comparison data, read straight from OTHER_EXP_FILES / CFD_FILES ----
    others = []
    for kind, files in (("exp", OTHER_EXP_FILES), ("cfd", CFD_FILES)):
        for path in files:
            try:
                name = os.path.splitext(os.path.basename(path))[0]
                others.append((kind, name, *load_ct_csv(path, k, FR_MIN_OTHER)))
            except (OSError, ValueError, IndexError) as err:
                print(f"\n*** skipped {path}: {err}")
    if others:
        cols, hdr = [fr_t, cw_th, cw_x, ct_th], "Fn,Cw_Michell,Cw_exp,Ct_Michell"
        for kind, name, fr_s, cw_s, ct_s in others:   # NaN outside the file's own Froude range (no extrapolation)
            cols += [np.interp(fr_t, fr_s, cw_s, left=np.nan, right=np.nan),
                     np.interp(fr_t, fr_s, ct_s, left=np.nan, right=np.nan)]
            hdr += f",Cw_{name},Ct_{name}"
        np.savetxt(OUT_CSV, np.column_stack(cols), delimiter=",", header=hdr, comments="")
        for kind, name, fr_s, cw_s, ct_s in others:   # Michell is dense, so interpolate IT onto the file's own Fn points
            cw_m = np.interp(fr_s, fr_t, cw_th, left=np.nan, right=np.nan)
            ct_m = np.interp(fr_s, fr_t, ct_th, left=np.nan, right=np.nan)
            print(f"\n{name} ({kind.upper()}, k={k:.3f}, Fn >= {FR_MIN_OTHER or 0})")
            print(f"{'Fn':>6} {'Cw Michell':>12} {'Cw file':>12} {'ratio':>8} {'Ct Michell':>12} {'Ct file':>12}")
            for f, a_, b_, c_, d_ in zip(fr_s, cw_m, cw_s, ct_m, ct_s):
                print(f"{f:6.3f} {a_:12.4e} {b_:12.4e} {a_ / b_ if b_ > 0 else float('nan'):8.2f} {c_:12.4e} {d_:12.4e}")

    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    ax[0].plot(fr_e, cw_exp, "ks-", ms=4, lw=1, label=f"5415 tank, k={k:.2f}")
    ax[0].plot(fr_t, cw_th, "o-", color="tab:blue", label=f"Michell, S={meta['S']:.3f} m$^2$ (Orca)")
    ax[0].axhline(0, color="gray", lw=.5); ax[0].set_xlabel("Froude number"); ax[0].set_ylabel("Cw")
    ax[0].set_title(f"Wave resistance coefficient [hull {meta['hull_id']}]"); ax[0].grid(True); ax[0].legend()
    ax[1].plot(fr_e, ctm_e, "ks-", ms=4, lw=1, label="5415 tank CTM")
    ax[1].plot(fr_t, ct_th, "^-", color="tab:red", label="Michell Ct")
    ax[1].set_xlabel("Froude number"); ax[1].set_ylabel("Ct"); ax[1].grid(True); ax[1].legend()
    colors = ["tab:green", "tab:orange", "tab:purple", "tab:brown", "tab:cyan", "tab:olive"]
    for i, (kind, name, fr_s, cw_s, ct_s) in enumerate(others):    # other data on both panels, then rebuild the legends
        sty = dict(ms=5, lw=1, color=colors[i % len(colors)], marker="D" if kind == "exp" else "v",
                   ls="-")
        lab = f"{name.replace('_', ' ')} ({kind.upper()})"
        ax[0].plot(fr_s, cw_s, label=f"{lab}, k={k:.2f}", **sty)
        ax[1].plot(fr_s, ct_s, label=lab, **sty)
    if others:
        ax[0].legend(fontsize=8); ax[1].legend(fontsize=8)
    if not same:
        fig.suptitle("Different hull from the 5415 - experiment for reference only", color="firebrick")
    plt.tight_layout(); plt.savefig(OUT_PNG, dpi=150)
    print(f"\nsaved {OUT_PNG}, {OUT_CSV}")
    plt.show()


if __name__ == "__main__":
    main()