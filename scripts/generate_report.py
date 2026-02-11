#!/usr/bin/env python3
"""
instech 시나리오 테스트 HTML 리포트 생성기
- scenario_runner.py 와 연동하여 실행 결과 + 스크린샷을 HTML 리포트로 생성
"""

import base64
import glob
import os
from datetime import datetime
from scenario_runner import fetch_scenario, run_all, run_scenario
from playwright.sync_api import sync_playwright


def encode_screenshot(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def find_screenshots(prefix):
    """prefix 패턴으로 스크린샷 매핑 (step_num → base64)"""
    screenshots = {}
    for path in glob.glob(f"{prefix}_*.png"):
        basename = os.path.basename(path)
        parts = basename.replace(".png", "").split("_")
        if parts[-1].isdigit():
            screenshots[int(parts[-1])] = encode_screenshot(path)
        elif parts[-1] == "error" and len(parts) >= 2 and parts[-2].isdigit():
            screenshots[f"{int(parts[-2])}_error"] = encode_screenshot(path)
    return screenshots


# ── 공통 HTML ──

COMMON_CSS = """
  :root {
    --pass: #22c55e; --pass-bg: #f0fdf4;
    --fail: #ef4444; --fail-bg: #fef2f2;
    --setup: #3b82f6; --setup-bg: #eff6ff;
    --warn: #f59e0b; --warn-bg: #fffbeb;
    --border: #e5e7eb; --text: #1f2937; --text-light: #6b7280; --bg: #f9fafb;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans KR', sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.6;
    padding: 24px; max-width: 900px; margin: 0 auto;
  }
  h1 { font-size: 24px; font-weight: 700; margin-bottom: 8px; }
  .meta {
    background: white; border: 1px solid var(--border); border-radius: 12px;
    padding: 20px; margin-bottom: 24px;
  }
  .meta-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px; margin-top: 16px;
  }
  .meta-item { display: flex; flex-direction: column; gap: 2px; }
  .meta-label { font-size: 12px; color: var(--text-light); font-weight: 500; }
  .meta-value { font-size: 14px; font-weight: 600; }
  .summary { display: flex; gap: 12px; margin-bottom: 24px; }
  .summary-card {
    flex: 1; background: white; border: 1px solid var(--border);
    border-radius: 12px; padding: 16px; text-align: center;
  }
  .summary-card.pass { border-left: 4px solid var(--pass); }
  .summary-card.fail { border-left: 4px solid var(--fail); }
  .summary-card.total { border-left: 4px solid #8b5cf6; }
  .summary-num { font-size: 32px; font-weight: 800; line-height: 1; }
  .summary-num.pass { color: var(--pass); }
  .summary-num.fail { color: var(--fail); }
  .summary-num.total { color: #8b5cf6; }
  .summary-label { font-size: 13px; color: var(--text-light); margin-top: 4px; }

  .scenario {
    background: white; border: 1px solid var(--border);
    border-radius: 12px; margin-bottom: 16px; overflow: hidden;
  }
  .scenario-header {
    padding: 16px 20px; cursor: pointer; display: flex;
    align-items: center; gap: 12px; user-select: none; transition: background 0.15s;
  }
  .scenario-header:hover { background: var(--bg); }
  .scenario-header .arrow {
    font-size: 12px; transition: transform 0.2s;
    color: var(--text-light); flex-shrink: 0;
  }
  .scenario.open .scenario-header .arrow { transform: rotate(90deg); }
  .badge {
    display: inline-flex; align-items: center; padding: 2px 10px;
    border-radius: 999px; font-size: 12px; font-weight: 600; flex-shrink: 0;
  }
  .badge.pass { background: var(--pass-bg); color: var(--pass); }
  .badge.fail { background: var(--fail-bg); color: var(--fail); }
  .badge.setup { background: var(--setup-bg); color: var(--setup); }
  .scenario-title { font-size: 15px; font-weight: 600; flex: 1; }
  .scenario-body {
    display: none; border-top: 1px solid var(--border); padding: 16px 20px;
  }
  .scenario.open .scenario-body { display: block; }
  .scenario-desc {
    font-size: 13px; color: var(--text-light); margin-bottom: 12px; line-height: 1.7;
  }
  .precondition {
    display: flex; align-items: flex-start; gap: 6px;
    padding: 8px 12px; margin-bottom: 12px;
    background: var(--warn-bg); border: 1px solid #fde68a;
    border-radius: 8px; font-size: 13px; color: #92400e; line-height: 1.5;
  }
  .precondition-label { font-weight: 600; white-space: nowrap; }

  .step {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 8px 0; border-bottom: 1px solid #f3f4f6;
  }
  .step:last-child { border-bottom: none; }
  .step-icon {
    width: 20px; height: 20px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; flex-shrink: 0; margin-top: 2px;
  }
  .step-icon.pass { background: var(--pass-bg); color: var(--pass); }
  .step-icon.fail { background: var(--fail-bg); color: var(--fail); }
  .step-num {
    font-size: 12px; color: var(--text-light); font-weight: 500;
    min-width: 20px; margin-top: 2px;
  }
  .step-desc { font-size: 14px; flex: 1; }
  .step-error {
    font-size: 12px; color: var(--fail); margin-top: 4px;
    padding: 4px 8px; background: var(--fail-bg); border-radius: 4px;
  }
  .step-screenshot { margin-top: 10px; margin-bottom: 6px; }
  .step-screenshot img {
    max-width: 360px; border: 1px solid var(--border);
    border-radius: 8px; cursor: pointer; transition: transform 0.2s;
  }
  .step-screenshot img:hover { transform: scale(1.02); }
  .step-screenshot img.expanded { max-width: 100%; }
  .footer {
    text-align: center; font-size: 12px; color: var(--text-light);
    margin-top: 32px; padding: 16px;
  }
  @media (max-width: 640px) {
    body { padding: 12px; }
    .summary { flex-direction: column; }
    .meta-grid { grid-template-columns: 1fr; }
    .step-screenshot img { max-width: 100%; }
  }
"""


def render_steps_html(steps, screenshots):
    html = ""
    for si, step in enumerate(steps):
        icon = "&#10003;" if step["status"] == "pass" else "&#10007;"
        step_num = si + 1

        error_html = ""
        if step.get("error"):
            error_html = f'<div class="step-error">{step["error"]}</div>'

        screenshot_html = ""
        b64 = screenshots.get(step_num)
        if b64:
            screenshot_html = f'<div class="step-screenshot"><img src="data:image/png;base64,{b64}" alt="{step["desc"]}" onclick="this.classList.toggle(\'expanded\')" /></div>'
        error_b64 = screenshots.get(f"{step_num}_error")
        if error_b64:
            screenshot_html += f'<div class="step-screenshot"><img src="data:image/png;base64,{error_b64}" alt="에러" onclick="this.classList.toggle(\'expanded\')" style="border-color:var(--fail);" /></div>'

        html += f"""    <div class="step">
      <span class="step-num">{step_num}</span>
      <span class="step-icon {step['status']}">{icon}</span>
      <div style="flex:1">
        <div class="step-desc">{step['desc']}</div>
        {error_html}
        {screenshot_html}
      </div>
    </div>
"""
    return html


def render_meta_html(now, base_url, extra_items=None):
    extra = ""
    if extra_items:
        for label, value in extra_items:
            extra += f"""    <div class="meta-item">
      <span class="meta-label">{label}</span>
      <span class="meta-value">{value}</span>
    </div>
"""
    return f"""<div class="meta">
  <div style="font-size:15px;font-weight:600;margin-bottom:4px;">실행 정보</div>
  <div class="meta-grid">
    <div class="meta-item">
      <span class="meta-label">실행 일시</span>
      <span class="meta-value">{now}</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">대상 서버</span>
      <span class="meta-value">{base_url}</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">실행 도구</span>
      <span class="meta-value">Claude Code (instech-scenario-test)</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">브라우저</span>
      <span class="meta-value">Chromium (headless)</span>
    </div>
{extra}  </div>
</div>"""


# ── 공통 HTML 리포트 렌더링 ──

def _render_report_html(all_results, base_url, title="instech 시나리오 테스트 리포트", subtitle="", extra_meta=None):
    """결과 리스트 → HTML 리포트 문자열"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = len(all_results)
    passed = sum(1 for r in all_results if r["status"] == "pass")
    failed = total - passed
    total_steps = sum(len(r["steps"]) for r in all_results)
    passed_steps = sum(1 for r in all_results for s in r["steps"] if s["status"] == "pass")

    subtitle_html = f'<p style="color:var(--text-light);margin-bottom:20px;font-size:14px;">{subtitle}</p>' if subtitle else ""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>{COMMON_CSS}</style>
</head>
<body>

<h1>{title}</h1>
{subtitle_html}

{render_meta_html(now, base_url, extra_items=extra_meta)}

<div class="summary">
  <div class="summary-card total">
    <div class="summary-num total">{total}</div>
    <div class="summary-label">전체 시나리오</div>
  </div>
  <div class="summary-card pass">
    <div class="summary-num pass">{passed}</div>
    <div class="summary-label">성공</div>
  </div>
  <div class="summary-card fail">
    <div class="summary-num fail">{failed}</div>
    <div class="summary-label">실패</div>
  </div>
  <div class="summary-card total">
    <div class="summary-num total" style="color:#8b5cf6">{passed_steps}/{total_steps}</div>
    <div class="summary-label">스텝 통과율</div>
  </div>
</div>
"""

    for result in all_results:
        name = result["name"]
        status = result["status"]

        scenario_id = result.get("id", name.replace(" ", "-"))
        description = result.get("description", "")
        precondition = result.get("precondition", "")

        badge_text = "통과" if status == "pass" else "실패"
        open_class = "open" if status == "fail" else ""
        step_pass = sum(1 for s in result["steps"] if s["status"] == "pass")
        step_total = len(result["steps"])

        screenshots = find_screenshots(f"/tmp/scenario_{scenario_id}")

        precondition_html = ""
        if precondition:
            precondition_html = f'<div class="precondition"><span class="precondition-label">전제조건:</span> {precondition}</div>'

        html += f"""
<div class="scenario {open_class}">
  <div class="scenario-header" onclick="this.parentElement.classList.toggle('open')">
    <span class="arrow">&#9654;</span>
    <span class="badge {status}">{badge_text}</span>
    <span class="scenario-title">{name}</span>
    <span style="font-size:13px;color:var(--text-light)">{step_pass}/{step_total} 스텝</span>
  </div>
  <div class="scenario-body">
    {precondition_html}
    <div class="scenario-desc">{description}</div>
{render_steps_html(result["steps"], screenshots)}  </div>
</div>
"""

    html += f"""
<div class="footer">
  instech 시나리오 테스트 &middot; {now} &middot; 생성: Claude Code (instech-scenario-test)
</div>
</body>
</html>"""
    return html


# ── 전체 시나리오 리포트 ──

def generate_report(base_url, feature_path, auth_state_path, category=None, extra_vars=None, labels=None):
    all_results = run_all(base_url, feature_path, auth_state_path, category=category, extra_vars=extra_vars, labels=labels)
    return _render_report_html(all_results, base_url, subtitle="E2E 테스트 결과")


# ── 단일 시나리오 리포트 ──

def _normalize_url(base_url):
    """HTTP → HTTPS 자동 변환"""
    if base_url.startswith("http://"):
        base_url = base_url.replace("http://", "https://", 1)
        print(f"[INFO] HTTP → HTTPS 자동 변환: {base_url}")
    return base_url


def _run_single(base_url, scenario_path, auth_state_path, extra_vars=None):
    """단일 시나리오 fetch → 변수 설정 → 실행 → 결과 반환"""
    base_url = _normalize_url(base_url)

    scenario = fetch_scenario(scenario_path)
    variables = {"baseUrl": base_url}
    if scenario.get("defaults"):
        variables.update(scenario["defaults"])
    if extra_vars:
        variables.update(extra_vars)

    screenshot_prefix = f"/tmp/scenario_{scenario['id']}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        result = run_scenario(browser, scenario, variables, auth_state_path, screenshot_prefix)
        browser.close()

    return result, base_url


def generate_single_report(base_url, scenario_path, auth_state_path, extra_vars=None):
    """단일 시나리오 실행 + HTML 리포트 생성"""
    result, base_url = _run_single(base_url, scenario_path, auth_state_path, extra_vars)

    # 콘솔 요약
    step_pass = sum(1 for s in result["steps"] if s["status"] == "pass")
    step_total = len(result["steps"])
    print(f"\n결과: {result['status'].upper()} ({step_pass}/{step_total} 스텝)")

    return _render_report_html(
        [result], base_url,
        title=result["name"],
        subtitle=result.get("description", ""),
    )


# ── CLI ──

if __name__ == "__main__":
    import sys

    # --var key=value, --label value 파싱
    extra_vars = {}
    labels = []
    positional = []
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--var" and i + 1 < len(sys.argv):
            k, v = sys.argv[i + 1].split("=", 1)
            extra_vars[k] = v
            i += 2
        elif sys.argv[i] == "--label" and i + 1 < len(sys.argv):
            labels.append(sys.argv[i + 1])
            i += 2
        else:
            positional.append(sys.argv[i])
            i += 1

    mode = positional[0] if len(positional) > 0 else "all"
    base_url = positional[1] if len(positional) > 1 else "https://instech.stg.3o3.co.kr"
    auth_path = positional[2] if len(positional) > 2 else "/tmp/instech_auth_state_stg.json"

    output_path = "/tmp/instech_test_report.html"

    if mode == "all":
        feature = positional[3] if len(positional) > 3 else "age-calculation/"
        report_html = generate_report(base_url, feature, auth_path, extra_vars=extra_vars or None, labels=labels or None)
    elif mode == "single":
        scenario_path = positional[3] if len(positional) > 3 else ""
        if not scenario_path:
            print("Usage: generate_report.py single <base_url> <auth_state_path> <scenario_path> [--var key=value]")
            sys.exit(1)
        report_html = generate_single_report(base_url, scenario_path, auth_path, extra_vars=extra_vars or None)
    else:
        print(f"Unknown mode: {mode}")
        print("Usage:")
        print("  generate_report.py all    <base_url> <auth_state_path> <feature_folder> [--var k=v] [--label l]")
        print("  generate_report.py single <base_url> <auth_state_path> <scenario_path>  [--var k=v]")
        sys.exit(1)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_html)
    print(f"Report generated: {output_path}")
    print(f"File size: {os.path.getsize(output_path):,} bytes")
