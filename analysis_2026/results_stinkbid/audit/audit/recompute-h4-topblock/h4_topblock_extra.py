"""Extra checks: (1) my shared partition reproduces the test's (M7's G = 33, G* = 10.435 on fitted rows; 59 blocks);
(2) the 0-based time-order label of each top block in its partition (the record's top_block = 16); (3) the worst-block
gate on the shared partition (context only). Same independent code as h4_topblock.py (imported from it by path)."""
import runpy
import sys

import numpy as np

sys.argv = [sys.argv[0]]
g = runpy.run_path(__file__.replace("h4_topblock_extra.py", "h4_topblock.py"), run_name="not_main")
M7, f, fe_b, month_blocks, top_block = g["M7"], g["f"], g["fe_b"], g["month_blocks"], g["top_block"]
mb_own, nm_own, mb_sh, nm_u, fitted = g["mb_own"], g["nm_own"], g["mb_sh"], g["nm_u"], g["fitted"]

# (1) G and G* of M7 on the shared partition, fitted rows (singleton coin-weeks dropped)
for tag, mb in (("shared", mb_sh), ("own", mb_own)):
    lab = mb[fitted]
    _, n = np.unique(lab, return_counts=True)
    G, Gs = len(n), (n.astype(float) ** 2).sum() ** 2 / (n.astype(float) ** 4).sum()
    print(f"{tag}: M7 fitted rows {fitted.sum()}, G = {G}, G* = {Gs:.6f}")

# (2) time-order index of the blocks
own_order = sorted(np.unique(mb_own).tolist())
sh_order = sorted(np.unique(f["mb_u"].to_numpy()).tolist())
tb_own, _ = top_block(mb_own)
tb_sh, _ = top_block(mb_sh)
print("own top block", nm_own[tb_own], "index", own_order.index(tb_own), "of", len(own_order))
print("shared top block", nm_u[tb_sh], "index", sh_order.index(tb_sh), "of", len(sh_order))

# (3) worst block (the block whose removal lowers b most) on each partition, context only
for tag, mb, nm in (("shared", mb_sh, nm_u), ("own", mb_own, nm_own)):
    best, which = np.inf, None
    for blk in np.unique(mb):
        b, _ = fe_b(M7, mb != blk)
        if np.isfinite(b) and b < best:
            best, which = b, blk
    print(f"worst block on {tag} partition: {nm[which]}, b without = {best:.10f}")

# share of M7 rows in each candidate top block, and b without each of the 4 largest shared blocks
u, c = np.unique(mb_sh, return_counts=True)
for k in np.argsort(-c)[:4]:
    b, n = fe_b(M7, mb_sh != u[k])
    print(f"shared block {nm_u[u[k]]}: {c[k]} M7 rows; b without = {b:.10f}")
u, c = np.unique(mb_own, return_counts=True)
for k in np.argsort(-c)[:4]:
    b, n = fe_b(M7, mb_own != u[k])
    print(f"own block {nm_own[u[k]]}: {c[k]} M7 rows; b without = {b:.10f}")
