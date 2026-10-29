#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selfcheck.py —— spec_drift 自身的回归断言（零依赖）

为什么需要：一个只会"输出看起来很有道理的结果"的检查器是不可信的。
必须能断言"在已知缺陷的样例上，它必须报出这几条；在已知干净的样例上，它必须不报"。
这就是本仓库主张的"第三方可复跑"的最低标准：连工具自己的判定也要能被断言。

跑法：
  python selfcheck.py          # 全部通过则 exit 0
"""
import os, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec_drift as sd

HERE = os.path.dirname(os.path.abspath(__file__))
FAILS = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ✓ {name}")
    else:
        print(f"  ✗ {name}  {detail}")
        FAILS.append(name)


def rules(findings):
    return [f"{f['rule']}:{f.get('fr','-')}:{f['feature']}" for f in findings]


print("\n[1] 在 demo/ 上必须检出四类判定")
r = sd.judge(os.path.join(HERE, "demo"))
got = rules(r["findings"])
check("spec 解析到 2 份", len(r["specs"]) == 2, f"实际 {len(r['specs'])}")
check("测试文件被找到", r["tests_found"] >= 1, f"实际 {r['tests_found']}")

has = lambda rule, fr=None: any(f["rule"] == rule and (fr is None or f.get("fr") == fr)
                                for f in r["findings"])
check("D1 未闭环澄清项被检出", has("D1"))
check("D2 状态与实现不符被检出", has("D2"))
check("D3 检出 001-FR-001 无锚点", has("D3", "FR-001"))
check("D3 检出 001-FR-003 无锚点", has("D3", "FR-003"))
check("D4 检出跨 spec 疑似取代", has("D4"))
check("001-FR-002 不该被误报（格式校验确有测试）",
      not any(f["rule"] == "D3" and f.get("fr") == "FR-002" and "001-user-login" in f["feature"]
              for f in r["findings"]))

print("\n[2] 注释不能制造假阳性（核心回归）")
# demo/tests/test_auth.py 末尾的注释里写着 sign / lock / expire / reject 等词。
# 若工具没剥离注释，这些 FR 就会被误判为"有锚点"。
with open(os.path.join(HERE, "demo", "tests", "test_auth.py"), encoding="utf-8") as f:
    raw = f.read()
stripped = sd.strip_comments(raw, "test_auth.py")
check("剥离注释后 'sign' 消失", "sign" not in stripped, "注释未被剥离")
check("剥离注释后 'expire' 消失", "expire" not in stripped, "注释未被剥离")
check("剥离注释后断言仍在", "validate_email" in stripped, "剥离过度")

print("\n[3] 干净样例必须零误报")
clean = sd.judge(os.path.join(HERE, "clean"))
clean_d3 = [f for f in clean["findings"] if f["rule"] == "D3"]
check("clean 项目无 D3 误报", len(clean_d3) == 0, f"实际 {len(clean_d3)} 条: {rules(clean_d3)[:3]}")
check("clean 项目 spec 被读到", len(clean["specs"]) == 1, f"实际 {len(clean['specs'])}")

print("\n[4] 边界：空目录不崩溃")
empty = sd.judge(os.path.join(HERE, "demo", "src"))
check("无 spec 目录时返回空 findings", empty["findings"] == [])

print("\n" + "=" * 60)
if FAILS:
    print(f"失败 {len(FAILS)} 项：{FAILS}")
    sys.exit(1)
print("全部通过（self-check clean）")
