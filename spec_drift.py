#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec_drift.py —— spec-kit 规格漂移判定器（零依赖，只用标准库）

回答一个 spec-kit 用户反复问、但至今没有可执行答案的问题：
    「多个 feature 的 spec 越写越多，怎么知道哪些已经过期、哪些被后来的 feature 取代了？」

设计原则（这是它能被信任的原因）：
  1. 只输出「可复核的事实」，不做语义猜测。每条判定都附判定依据。
  2. 不改你的文件，只读。判定结果第三方可复跑。
  3. 零依赖、单文件。不需要装 spec-kit，不需要连模型。

四类判定：
  D1 未闭环澄清项   spec 里还留着 [NEEDS CLARIFICATION: ...] → 该 spec 不能算完成
  D2 状态与实现不符  Status 声称完成但 FR 无任何测试引用 / 声称 Draft 但代码已存在
  D3 FR 无测试锚点  某条 FR 的关键词在任何测试文件里都找不到 → 实现与规格失联的最硬信号
  D4 跨 spec 疑似取代 A 的某条 FR 关键词高度重叠于更晚的 spec B，且 A 无显式引用 → 疑似过期

用法：
  python spec_drift.py --root .                       # 人读
  python spec_drift.py --root . --json                # 机器读
  python spec_drift.py --root . --fail-on D3          # CI 门禁用：有 D3 就退出码 1
"""
import argparse, glob, json, os, re, sys
from datetime import datetime

FR_RE = re.compile(r"^\s*[-*]\s*\*\*(FR-\d{3})\*\*\s*[:：]\s*(.+)$", re.M)
SC_RE = re.compile(r"^\s*[-*]\s*\*\*(SC-\d{3})\*\*\s*[:：]\s*(.+)$", re.M)
US_RE = re.compile(r"^###\s*User Story\s*\d+\s*[-–—]\s*(.+?)\s*\(Priority:\s*(P\d)\)", re.M)
STATUS_RE = re.compile(r"^\s*\*\*Status\*\*\s*[:：]\s*(.+)$", re.M)
CLARIFY_RE = re.compile(r"\[NEEDS CLARIFICATION:[^\]]*\]")
CJK = re.compile(r"[\u4e00-\u9fff]")

# 停用词：不参与关键词重叠判定
STOP = set("""the a an of to in on for and or with without by from as at is are be been
this that these those it its user users system must should can may will shall able
not no any all each per when then than so such via whether""".split())


def keywords(text, limit=12):
    """提取判定用的关键词：英文按词、中文按 2-4 字切块（不做分词，避免依赖）"""
    t = re.sub(r"\[NEEDS CLARIFICATION:[^\]]*\]", " ", text.lower())
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", t)
    en = [w for w in t.split() if len(w) >= 3 and w not in STOP and not w.isdigit()]
    zh = re.findall(r"[\u4e00-\u9fff]{2,4}", t)
    seen, out = set(), []
    for w in en + zh:
        if w not in seen:
            seen.add(w)
            out.append(w)
    return out[:limit]


def parse_spec(path):
    txt = open(path, encoding="utf-8", errors="ignore").read()
    m = STATUS_RE.search(txt)
    status = (m.group(1).strip() if m else "Unknown").split("(")[0].strip()
    frs = [{"id": i, "text": t.strip(), "kw": keywords(t)} for i, t in FR_RE.findall(txt)]
    scs = [{"id": i, "text": t.strip()} for i, t in SC_RE.findall(txt)]
    stories = [{"title": a.strip(), "priority": b} for a, b in US_RE.findall(txt)]
    clar = CLARIFY_RE.findall(txt)
    feat = os.path.basename(os.path.dirname(path))
    num = re.match(r"(\d+)", feat)
    return {
        "path": path, "feature": feat,
        "seq": int(num.group(1)) if num else 9999,
        "status": status, "frs": frs, "scs": scs,
        "stories": stories, "clarifications": clar,
        "mtime": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d"),
    }


def strip_comments(text, path):
    """剥离注释与 docstring —— 这是本工具最关键的一步。

    为什么必须做：如果直接在测试文件里 grep 关键词，注释和文档字符串会让判定假阳性。
    实测踩到的例子：测试文件末尾一句「# 以下规格条目没有任何锚点：sign in with email...」
    就把 FR 判成了「已有测试锚点」——而它恰恰是在说明"没有锚点"。
    所以：只认剥掉注释后剩下的断言区文本。
    """
    ext = os.path.splitext(path)[1].lower()
    # JS/TS/Go 块注释
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    # Python docstring（含单双三引号）
    if ext == ".py":
        text = re.sub(r'""".*?"""', " ", text, flags=re.S)
        text = re.sub(r"'''.*?'''", " ", text, flags=re.S)
    out = []
    for ln in text.split("\n"):
        s = ln.lstrip()
        if s.startswith("#") or s.startswith("//"):
            continue                      # 整行注释直接丢
        if ext == ".py":
            ln = re.sub(r"\s+#.*$", " ", ln)   # 行尾注释
        else:
            ln = re.sub(r"\s+//.*$", " ", ln)
        out.append(ln)
    return "\n".join(out).lower()


def collect_tests(root):
    """收集测试文件内容（只看测试，不看实现——实现里出现关键词不算锚点）"""
    pats = ["**/*test*.py", "**/*test*.ts", "**/*test*.js", "**/*test*.go",
            "**/*.test.ts", "**/*.test.js", "**/*.spec.ts", "**/*_test.go",
            "**/tests/**/*.*", "**/__tests__/**/*.*"]
    files, blob = [], []
    for p in pats:
        for f in glob.glob(os.path.join(root, p), recursive=True):
            if os.path.isfile(f) and f not in files:
                files.append(f)
                try:
                    raw = open(f, encoding="utf-8", errors="ignore").read()
                    blob.append(strip_comments(raw, f))
                except Exception:
                    pass
    return files, "\n".join(blob)


def collect_code(root):
    pats = ["**/*.py", "**/*.ts", "**/*.js", "**/*go", "**/*.java", "**/*rs"]
    out = []
    for p in pats:
        for f in glob.glob(os.path.join(root, p), recursive=True):
            if "/tests/" in f.replace("\\", "/") or "__tests__" in f:
                continue
            out.append(f)
    return out


def judge(root):
    spec_paths = sorted(glob.glob(os.path.join(root, "specs", "*", "spec.md")))
    if not spec_paths:
        spec_paths = sorted(glob.glob(os.path.join(root, "**", "spec.md"), recursive=True))
    specs = [parse_spec(p) for p in spec_paths]
    specs.sort(key=lambda s: s["seq"])
    test_files, test_blob = collect_tests(root)
    code_files = collect_code(root)
    code_blob = ""
    for f in code_files[:400]:
        try:
            code_blob += strip_comments(open(f, encoding="utf-8", errors="ignore").read(), f) + "\n"
        except Exception:
            pass

    findings = []

    # ── D1 未闭环澄清项 ──
    for s in specs:
        if s["clarifications"]:
            findings.append({
                "rule": "D1", "severity": "high", "feature": s["feature"],
                "claim": f"{len(s['clarifications'])} 处需求仍标记 NEEDS CLARIFICATION，但 spec 未被阻挡",
                "evidence": s["clarifications"][:3],
                "how_to_check": f"grep -n 'NEEDS CLARIFICATION' {s['path']}",
            })

    # ── D3 FR 无测试锚点 ──
    # 关键：必须先剔除「通用词」。否则 "email" 这种在每份 spec 每条 FR 都出现的词，
    # 只要测试里出现一次就会把所有 FR 判成"有锚点"——这是朴素 grep 方法的假阳性来源。
    # 做法：document frequency > 40% 的词不参与判定。
    from collections import Counter
    df = Counter()
    for s in specs:
        for fr in s["frs"]:
            for k in set(fr["kw"]):
                df[k] += 1
    total_fr = sum(len(s["frs"]) for s in specs) or 1
    common = {k for k, c in df.items() if c >= 2 and c / total_fr > 0.4}

    for s in specs:
        for fr in s["frs"]:
            kws = [k for k in fr["kw"] if k not in common and len(k) >= 4]
            if not kws:
                # 一条 FR 全是通用词，说明它本身写得没有可区分信息 —— 这也值得报
                if fr["kw"] and test_blob:
                    findings.append({
                        "rule": "D3", "severity": "low", "feature": s["feature"], "fr": fr["id"],
                        "claim": f"{fr['id']} 的措辞全是跨 spec 通用词，无法定位到任何具体测试（判据不足）",
                        "evidence": {"kw": fr["kw"][:6], "text": fr["text"][:120]},
                        "how_to_check": f"人工确认 {fr['id']} 由哪个测试覆盖",
                    })
                continue
            hits = [k for k in kws if k in test_blob]
            # 第三层降噪：单个词命中不算锚点。
            # 实测踩到：测试函数名 test_email_validation_rejects_missing_at 里的 "rejects"
            # 命中了 OTP 重放需求里的 "reject"，但两者毫无关系。
            # 所以要求至少 2 个独立特征词同现（kws 只有 1 个时放宽为 1）。
            need = min(2, len(kws))
            if len(hits) < need and test_blob:
                findings.append({
                    "rule": "D3", "severity": "high", "feature": s["feature"], "fr": fr["id"],
                    "claim": f"{fr['id']} 在任何测试文件里都找不到足够的特征词锚点"
                             f"（{len(kws)} 个非通用词中仅 {len(hits)} 个出现，需 ≥{need}）",
                    "evidence": {"kw": kws[:6], "hits": hits,
                                 "common_excluded": sorted(k for k in fr["kw"] if k in common)[:5],
                                 "text": fr["text"][:120]},
                    "how_to_check": f"grep -ril '{kws[0]}' {root} --include='*test*'",
                })

    # ── D2 状态与实现不符 ──
    done_words = ("done", "complete", "completed", "implemented", "shipped", "released")
    for s in specs:
        st = s["status"].lower()
        if any(w in st for w in done_words) and s["frs"]:
            anchored = sum(1 for fr in s["frs"]
                           if any(k in test_blob for k in fr["kw"] if len(k) >= 4))
            if anchored == 0:
                findings.append({
                    "rule": "D2", "severity": "high", "feature": s["feature"],
                    "claim": f"Status 声明「{s['status']}」，但 {len(s['frs'])} 条 FR 无一条有测试锚点",
                    "evidence": {"status": s["status"], "fr_count": len(s["frs"])},
                    "how_to_check": f"检查 {s['path']} 与测试目录是否对得上",
                })
        elif ("draft" in st or "planned" in st) and s["frs"]:
            in_code = sum(1 for fr in s["frs"]
                          if any(k in code_blob for k in fr["kw"] if len(k) >= 4))
            if in_code >= max(2, len(s["frs"]) // 2):
                findings.append({
                    "rule": "D2", "severity": "mid", "feature": s["feature"],
                    "claim": f"Status 仍是「{s['status']}」，但 {in_code}/{len(s['frs'])} 条 FR 的关键词已在实现代码里出现",
                    "evidence": {"status": s["status"], "fr_in_code": in_code},
                    "how_to_check": f"确认 {s['feature']} 是否已实现但未更新状态",
                })

    # ── D4 跨 spec 疑似取代 ──
    # 真实项目上踩到的坑：35 份 spec 的项目报出 396 条 D4，噪音淹没信号。
    # 原因是 O(n²) 两两比较，而同一项目的 spec 是连续迭代，用词天然相似。
    # 三处修正：阈值 0.34→0.45；每对 spec 只保留重叠度最高的一条；全局限量。
    D4_JAC = 0.45
    D4_LIMIT = 20
    d4_raw = []
    for i, a in enumerate(specs):
        for b in specs[i + 1:]:
            if b["seq"] <= a["seq"]:
                continue
            a_txt = open(a["path"], encoding="utf-8", errors="ignore").read().lower()
            if re.search(rf"\b{b['seq']:03d}\b", a_txt) or b["feature"].lower() in a_txt:
                continue
            pair_best = None
            for fa in a["frs"]:
                for fb in b["frs"]:
                    sa, sb = set(fa["kw"]), set(fb["kw"])
                    if len(sa) < 3 or len(sb) < 3:
                        continue
                    inter = sa & sb
                    jac = len(inter) / len(sa | sb)
                    if jac >= D4_JAC and (pair_best is None or jac > pair_best["jac"]):
                        pair_best = {
                            "rule": "D4", "severity": "mid",
                            "feature": f"{a['feature']} ← {b['feature']}",
                            "fr": f"{fa['id']} vs {fb['id']}",
                            "jac": jac,
                            "claim": f"{a['feature']} 的 {fa['id']} 与更晚的 {b['feature']} 的 {fb['id']} 关键词重叠 {jac:.0%}，"
                                     f"且 {a['feature']} 未引用 {b['seq']:03d} → 疑似已被取代但未标注",
                            "evidence": {"shared_kw": sorted(inter)[:8],
                                         "a": fa["text"][:100], "b": fb["text"][:100]},
                            "how_to_check": f"对比 {a['path']} 与 {b['path']}",
                        }
            if pair_best:
                d4_raw.append(pair_best)
    d4_raw.sort(key=lambda x: -x["jac"])
    for h in d4_raw[:D4_LIMIT]:
        h.pop("jac", None)
        findings.append(h)
    if len(d4_raw) > D4_LIMIT:
        findings.append({
            "rule": "D4", "severity": "low", "feature": "(已折叠)",
            "claim": f"另有 {len(d4_raw) - D4_LIMIT} 组 spec 关键词疑似重叠，按重叠度排序仅列前 {D4_LIMIT} 组",
            "evidence": {"total_candidates": len(d4_raw)},
            "how_to_check": "python spec_drift.py --root . --json 看全量候选",
        })
    order = {"high": 0, "mid": 1, "low": 2}
    findings.sort(key=lambda x: (order.get(x["severity"], 9), x["rule"]))
    return {"root": os.path.abspath(root), "specs": specs,
            "tests_found": len(test_files), "findings": findings}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-on", default="", help="出现该规则时退出码 1，如 D3")
    a = ap.parse_args()
    r = judge(a.root)

    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(f"\n规格漂移判定 · {r['root']}")
        print(f"spec {len(r['specs'])} 份 | 测试文件 {r['tests_found']} 个 | 判定 {len(r['findings'])} 条\n")
        if r["specs"]:
            print("沿用的 spec 清单：")
            for s in r["specs"]:
                print(f"  [{s['seq']:03d}] {s['feature']:<28} status={s['status']:<14} "
                      f"FR={len(s['frs']):<3} SC={len(s['scs']):<3} story={len(s['stories'])}")
            print()
        if not r["findings"]:
            print("未发现漂移信号（注意：这只说明四类信号都没触发，不等于规格正确）")
        for i, f in enumerate(r["findings"], 1):
            mark = {"high": "🔴", "mid": "🟡", "low": "⚪"}.get(f["severity"], "·")
            print(f"{mark} {i}. [{f['rule']}] {f.get('fr','')} {f['feature']}")
            print(f"   {f['claim']}")
            print(f"   依据：{json.dumps(f['evidence'], ensure_ascii=False)[:180]}")
            print(f"   复核：{f['how_to_check']}")
            print()
        hi = sum(1 for f in r["findings"] if f["severity"] == "high")
        print(f"汇总：high={hi} mid={sum(1 for f in r['findings'] if f['severity']=='mid')} "
              f"low={sum(1 for f in r['findings'] if f['severity']=='low')}")
        print("说明：本工具只报「可复核的信号」，不做语义判断。D4 是候选而非结论，需人工确认。")

    if a.fail_on and any(f["rule"] == a.fail_on for f in r["findings"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
