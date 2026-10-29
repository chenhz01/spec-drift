#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ecosystem_scan.py —— 扫描 spec-kit 生态的规格健康度

做两件事，都不需要对方授权、也不产生任何对外发送：
  1. 给 #620 的回复提供生态级证据（不是我一个人觉得有问题，是 N 个项目都这样）
  2. 产出一份「谁家有具体漂移问题」的名单，可直接当免费样件的目标

只读公开 raw 文件，只算 D1（未闭环澄清项）+ D2（状态分布）+ D4（跨 spec 重叠）。
D3 需要测试文件内容，量大且噪音高，这一轮不做。
"""
import json, os, re, sys, urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "_real_spec_projects.json")
OUT = os.path.join(HERE, "_ecosystem_result.json")

FR_RE = re.compile(r"^\s*[-*]\s*\*\*(FR-\d{3})\*\*\s*[:：]\s*(.+)$", re.M)
STATUS_RE = re.compile(r"^\s*\*\*Status\*\*\s*[:：]\s*(.+)$", re.M)
CLARIFY_RE = re.compile(r"\[NEEDS CLARIFICATION:[^\]]*\]")
STOP = set("""the a an of to in on for and or with without by from as at is are be been
this that these those it its user users system must should can may will shall able
not no any all each per when then than so such via whether""".split())


def raw(url, t=20):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "zm-scan"}), timeout=t) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception:
        return ""


def kw(text, limit=12):
    t = re.sub(r"\[NEEDS CLARIFICATION:[^\]]*\]", " ", text.lower())
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", t)
    en = [w for w in t.split() if len(w) >= 3 and w not in STOP and not w.isdigit()]
    zh = re.findall(r"[\u4e00-\u9fff]{2,4}", t)
    out, seen = [], set()
    for w in en + zh:
        if w not in seen:
            seen.add(w)
            out.append(w)
    return out[:limit]


def scan_project(p):
    repo, br = p["repo"], p["branch"]
    specs = []
    for sp in p["specs"][:60]:            # 单项目上限，防极端
        txt = raw(f"https://raw.githubusercontent.com/{repo}/{br}/{urllib.request.quote(sp)}")
        if not txt:
            continue
        m = STATUS_RE.search(txt)
        status = (m.group(1).strip() if m else "Unknown").split("(")[0].strip()
        frs = [{"id": i, "kw": kw(t)} for i, t in FR_RE.findall(txt)]
        specs.append({"path": sp, "status": status, "frs": frs,
                      "clar": CLARIFY_RE.findall(txt)})
    if not specs:
        return None

    # D1：未闭环澄清项
    d1 = sum(len(s["clar"]) for s in specs)
    d1_specs = sum(1 for s in specs if s["clar"])

    # D2：状态分布
    st = Counter(s["status"] for s in specs)

    # D4：跨 spec 重叠（阈值 45%，与工具一致）
    total_fr = sum(len(s["frs"]) for s in specs)
    df = Counter()
    for s in specs:
        for fr in s["frs"]:
            for k in set(fr["kw"]):
                df[k] += 1
    common = {k for k, c in df.items() if c >= 2 and total_fr and c / total_fr > 0.4}
    d4 = 0
    for i, a in enumerate(specs):
        for b in specs[i + 1:]:
            for fa in a["frs"]:
                ka = set(fa["kw"]) - common
                if len(ka) < 3:
                    continue
                for fb in b["frs"]:
                    kb = set(fb["kw"]) - common
                    if len(kb) < 3:
                        continue
                    j = len(ka & kb) / len(ka | kb)
                    if j >= 0.45:
                        d4 += 1
                        break

    return {
        "repo": repo, "stars": p["stars"], "n_specs": len(specs),
        "n_fr": total_fr, "d1_unresolved": d1, "d1_specs": d1_specs,
        "d4_pairs": d4, "status": dict(st),
        "draft_share": round(st.get("Draft", 0) / len(specs), 2),
        "spec_paths": [s["path"] for s in specs],
    }


cands = json.load(open(SRC, encoding="utf-8"))
print(f"扫描 {len(cands)} 个真实项目（只读公开 raw 文件）...\n")
res = []
with ThreadPoolExecutor(max_workers=10) as ex:
    futs = {ex.submit(scan_project, p): p for p in cands}
    for i, f in enumerate(as_completed(futs), 1):
        try:
            r = f.result()
            if r:
                res.append(r)
        except Exception:
            pass
        if i % 10 == 0:
            print(f"  ...{i}/{len(cands)}", flush=True)

res.sort(key=lambda x: (-x["d1_unresolved"], -x["d4_pairs"]))
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

tot_specs = sum(r["n_specs"] for r in res)
tot_fr = sum(r["n_fr"] for r in res)
tot_d1 = sum(r["d1_unresolved"] for r in res)
with_d1 = sum(1 for r in res if r["d1_unresolved"] > 0)
with_d4 = sum(1 for r in res if r["d4_pairs"] > 0)
draft_specs = sum(r["status"].get("Draft", 0) for r in res)

print(f"\n{'='*86}\n生态快照（{len(res)} 个项目）\n{'='*86}")
print(f"spec 总数 {tot_specs} | FR 总数 {tot_fr} | Draft 状态 {draft_specs} 份 ({draft_specs/max(tot_specs,1):.0%})")
print(f"未闭环 NEEDS CLARIFICATION：{tot_d1} 处，分布在 {with_d1} 个项目（{with_d1/max(len(res),1):.0%}）")
print(f"跨 spec 疑似重叠（≥45%）：{sum(r['d4_pairs'] for r in res)} 组，涉及 {with_d4} 个项目")
print(f"\n{'仓库':<46}{'星':>6}{'spec':>6}{'FR':>6}{'未闭环':>8}{'重叠':>6}{'Draft%':>8}")
print("-" * 86)
for r in res[:25]:
    print(f"{r['repo']:<46}{r['stars']:>6}{r['n_specs']:>6}{r['n_fr']:>6}"
          f"{r['d1_unresolved']:>8}{r['d4_pairs']:>6}{r['draft_share']:>8.0%}")
print(f"\n已存 → {OUT}")
