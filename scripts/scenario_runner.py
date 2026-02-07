#!/usr/bin/env python3
"""
instech 시나리오 범용 러너
- 시나리오 JSON을 읽어서 모든 step을 자동으로 Playwright 코드로 변환/실행
- 전체 시나리오 실행 및 특정 시나리오 반복 실행 지원
"""

import glob
import json
import os
import re
import urllib.request
from playwright.sync_api import sync_playwright

SCENARIOS_BASE_URL = "https://hj8902.github.io/instech_scenarios/scenarios"
ACTION_SETTLE_MS = 200  # React 상태 커밋 대기 (fill/blur/click/clear 후)


# ── JSON fetch ──

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "scenario-runner"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_index():
    return fetch_json(f"{SCENARIOS_BASE_URL}/index.json")


def fetch_scenario(path):
    return fetch_json(f"{SCENARIOS_BASE_URL}/{path}")


# ── 변수 치환 ──

def substitute_variables(obj, variables):
    """JSON 내의 {{변수명}} 패턴을 치환"""
    if isinstance(obj, str):
        for key, value in variables.items():
            obj = obj.replace(f"{{{{{key}}}}}", value)
        return obj
    if isinstance(obj, dict):
        return {k: substitute_variables(v, variables) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute_variables(item, variables) for item in obj]
    return obj


# ── 약관 동의 공통 처리 ──

def handle_terms(page):
    """약관 동의 바텀시트 처리 - 공통 패턴"""
    page.wait_for_timeout(1000)
    dialog = page.locator("[role='dialog'][aria-modal='true']")
    if dialog.count() > 0 and dialog.first.is_visible():
        checkboxes = dialog.locator("input[type='checkbox']")
        for i in range(checkboxes.count()):
            cb = checkboxes.nth(i)
            if cb.is_visible() and not cb.is_checked():
                cb.click(force=True)
                page.wait_for_timeout(300)

        page.wait_for_timeout(500)
        agree_btn = dialog.locator("button").last
        if agree_btn.is_visible() and agree_btn.is_enabled():
            agree_btn.click()
            page.wait_for_timeout(1000)
            return "약관 동의 완료"
        return "동의 버튼 비활성"
    return "약관 바텀시트 미노출 (이미 동의됨)"


# ── Step 실행 ──

def execute_step(page, step, context):
    """단일 step을 실행하고 결과를 반환"""
    action = step.get("action", "")
    desc = step.get("description", action)
    screenshot_path = context.get("screenshot_path")
    step_num = context.get("step_num", 0)

    if action == "loadState":
        # loadState는 context 생성 시 이미 처리됨
        return {"status": "pass", "desc": desc}

    elif action == "navigate":
        url = step.get("url", "")
        page.goto(url)
        page.wait_for_load_state("networkidle")
        # 세션 만료 체크
        if "/web-login" in page.url:
            return {"status": "fail", "desc": desc, "error": "세션 만료 — /web-login으로 리다이렉트됨"}
        return {"status": "pass", "desc": desc}

    elif action == "fill":
        selector = step.get("selector", "input")
        value = step.get("value", "")
        el = page.locator(selector).first
        el.fill(value)
        page.wait_for_timeout(ACTION_SETTLE_MS)
        return {"status": "pass", "desc": desc}

    elif action == "blur":
        selector = step.get("selector", "input")
        page.locator(selector).first.blur()
        page.wait_for_timeout(ACTION_SETTLE_MS)
        return {"status": "pass", "desc": desc}

    elif action == "clear":
        selector = step.get("selector", "input")
        page.locator(selector).first.fill("")
        page.wait_for_timeout(ACTION_SETTLE_MS)
        return {"status": "pass", "desc": desc}

    elif action == "click":
        selector = step.get("selector", "")
        page.locator(selector).first.click()
        page.wait_for_timeout(ACTION_SETTLE_MS)
        return {"status": "pass", "desc": desc}

    elif action == "screenshot":
        if screenshot_path:
            path = f"{screenshot_path}_{step_num}.png"
            page.screenshot(path=path, full_page=True)
        return {"status": "pass", "desc": desc}

    elif action == "expect":
        expect_type = step.get("type", "")
        if expect_type == "url":
            value = step.get("value", "")
            if value in page.url:
                return {"status": "pass", "desc": desc}
            else:
                return {"status": "fail", "desc": desc, "error": f"URL 불일치: 기대 '{value}', 실제 '{page.url}'"}

        elif expect_type == "visible":
            selector = step.get("selector", "")
            # 쉼표로 분리된 복수 셀렉터 중 하나라도 visible이면 통과
            selectors = [s.strip() for s in selector.split(",")]
            for sel in selectors:
                try:
                    loc = page.locator(sel).first
                    loc.wait_for(state="visible", timeout=5000)
                    return {"status": "pass", "desc": desc}
                except Exception:
                    continue
            return {"status": "fail", "desc": desc, "error": f"셀렉터 미발견: {selector}"}

        elif expect_type == "hidden":
            selector = step.get("selector", "")
            try:
                loc = page.locator(selector)
                if loc.count() == 0 or not loc.first.is_visible():
                    return {"status": "pass", "desc": desc}
                # 잠시 대기 후 재확인
                page.wait_for_timeout(1000)
                if loc.count() == 0 or not loc.first.is_visible():
                    return {"status": "pass", "desc": desc}
                return {"status": "fail", "desc": desc, "error": f"셀렉터가 여전히 visible: {selector}"}
            except Exception:
                return {"status": "pass", "desc": desc}

        elif expect_type == "disabled":
            selector = step.get("selector", "")
            try:
                loc = page.locator(selector).first
                loc.wait_for(state="attached", timeout=5000)
                if loc.is_disabled():
                    return {"status": "pass", "desc": desc}
                return {"status": "fail", "desc": desc, "error": f"기대: disabled, 실제: enabled — {selector}"}
            except Exception as e:
                return {"status": "fail", "desc": desc, "error": str(e)}

        elif expect_type == "enabled":
            selector = step.get("selector", "")
            try:
                loc = page.locator(selector).first
                loc.wait_for(state="attached", timeout=5000)
                if loc.is_enabled():
                    return {"status": "pass", "desc": desc}
                return {"status": "fail", "desc": desc, "error": f"기대: enabled, 실제: disabled — {selector}"}
            except Exception as e:
                return {"status": "fail", "desc": desc, "error": str(e)}

    elif action == "waitForNavigation":
        page.wait_for_load_state("networkidle")
        return {"status": "pass", "desc": desc}

    elif action == "waitFor":
        selector = step.get("selector", "")
        state = step.get("state", "visible")
        page.locator(selector).first.wait_for(state=state, timeout=10000)
        return {"status": "pass", "desc": desc}

    elif action == "waitForResponse":
        url_pattern = step.get("urlPattern", "")
        page.wait_for_timeout(3000)  # 간이 대기
        return {"status": "pass", "desc": desc}

    elif action == "waitForTimeout":
        timeout = step.get("timeout", 1000)
        page.wait_for_timeout(timeout)
        return {"status": "pass", "desc": desc}

    elif action == "waitForUrl":
        pattern = step.get("pattern", "")
        exclude = step.get("exclude", "")
        timeout = step.get("timeout", 30000)
        if exclude:
            page.wait_for_url(
                lambda url, p=pattern, e=exclude: re.search(p.replace("**", ".*"), url) and e not in url,
                timeout=timeout
            )
        else:
            page.wait_for_url(lambda url, p=pattern: re.search(p.replace("**", ".*"), url), timeout=timeout)
        return {"status": "pass", "desc": desc}

    elif action == "handleTermsAgreement":
        fallback = step.get("fallback", "")
        result_msg = handle_terms(page)
        if "비활성" in result_msg and fallback != "skip":
            return {"status": "fail", "desc": f"{desc} — {result_msg}"}
        return {"status": "pass", "desc": f"{desc} — {result_msg}"}

    elif action == "saveState":
        path = context.get("auth_state_path", "/tmp/instech_auth_state.json")
        context["browser_context"].storage_state(path=path)
        return {"status": "pass", "desc": desc}

    elif action == "launchBrowser":
        # 브라우저 재실행은 러너 레벨에서 처리
        return {"status": "pass", "desc": desc}

    elif action == "injectStoreData":
        store_name = step.get("store", "")
        data = step.get("data", {})
        data = substitute_variables(data, context.get("variables", {}))
        window_key = f"__{store_name.upper()}_STORE__"
        js = f"window.{window_key}?.setState({json.dumps(data)})"
        page.evaluate(js)
        page.wait_for_timeout(300)
        return {"status": "pass", "desc": desc}

    elif action == "fetchAndInjectUserInfo":
        base_url = context.get("variables", {}).get("baseUrl", "")
        store_name = step.get("store", "COUNSEL")
        # me API 호출 (브라우저 컨텍스트의 쿠키 사용)
        user_data = page.evaluate("""async () => {
            const res = await fetch('/api/proxy/users/me');
            const json = await res.json();
            return json.data;
        }""")
        # 전화번호 포맷팅 (01012345678 → 010-1234-5678)
        phone = user_data.get("phone", "")
        if len(phone) == 11:
            phone = f"{phone[:3]}-{phone[3:7]}-{phone[7:]}"
        elif len(phone) == 10:
            phone = f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
        user_info = {
            "userId": user_data.get("userId", ""),
            "name": user_data.get("name", ""),
            "phoneNumber": phone,
            "birthDate": user_data.get("fullBirth", ""),
            "gender": user_data.get("genderCode", ""),
        }
        window_key = f"__{store_name.upper()}_STORE__"
        js = f"window.{window_key}?.setState({{ userInfo: {json.dumps(user_info)} }})"
        page.evaluate(js)
        page.wait_for_timeout(300)
        return {"status": "pass", "desc": f"{desc} — {user_info['name']} ({user_info['gender']})"}

    elif action == "setSessionStorage":
        key = step.get("key", "")
        value = step.get("value", "")
        value = substitute_variables(value, context.get("variables", {}))
        page.evaluate(f"sessionStorage.setItem('{key}', '{value}')")
        return {"status": "pass", "desc": desc}

    elif action == "manualAction":
        instruction = step.get("instruction", "")
        print(f"  [수동] {instruction}")
        return {"status": "pass", "desc": f"{desc} (수동)"}

    else:
        return {"status": "fail", "desc": desc, "error": f"알 수 없는 action: {action}"}


# ── 시나리오 실행 ──

def run_scenario(browser, scenario, variables, auth_state_path, screenshot_prefix, round_label=""):
    """단일 시나리오를 실행하고 결과 반환"""
    # 이전 실행의 스크린샷 정리
    for old in glob.glob(f"{screenshot_prefix}_*.png"):
        os.remove(old)

    label = f"{round_label} " if round_label else ""
    print(f"\n{'='*50}")
    print(f"{label}{scenario['name']}")
    print(f"{'='*50}")

    # 변수 치환
    steps = substitute_variables(scenario.get("steps", []), variables)

    # 컨텍스트 생성
    if scenario.get("requiresAuth", False):
        try:
            ctx = browser.new_context(storage_state=auth_state_path)
        except Exception:
            ctx = browser.new_context()
    else:
        ctx = browser.new_context()

    page = ctx.new_page()

    context = {
        "screenshot_path": screenshot_prefix,
        "auth_state_path": auth_state_path,
        "browser_context": ctx,
        "variables": variables,
    }

    results = []
    scenario_status = "pass"

    for i, step in enumerate(steps):
        context["step_num"] = i + 1
        try:
            result = execute_step(page, step, context)
        except Exception as e:
            # 예외 발생 시 스크린샷 캡처
            try:
                page.screenshot(path=f"{screenshot_prefix}_{i+1}_error.png", full_page=True)
            except Exception:
                pass
            result = {"status": "fail", "desc": step.get("description", step.get("action", "")), "error": str(e)}

        results.append(result)

        icon = "OK" if result["status"] == "pass" else "FAIL"
        print(f"  [{icon}] Step {i+1}: {result['desc']}")
        if result.get("error"):
            print(f"         Error: {result['error']}")

        if result["status"] == "fail":
            scenario_status = "fail"
            # 세션 만료 시 즉시 중단
            if "세션 만료" in result.get("error", ""):
                break

    ctx.close()
    return {"name": scenario["name"], "steps": results, "status": scenario_status}


# ── 전체 실행 / 반복 실행 ──

def run_all(base_url, feature_path, auth_state_path, category=None):
    """특정 기능의 전체 시나리오 1회 실행. category='happy'/'edge'로 필터 가능."""
    index = fetch_index()
    test_scenarios = [
        s for s in index["scenarios"]
        if s["type"] == "test" and s["path"].startswith(feature_path)
        and (category is None or s.get("category", "happy") == category)
    ]

    variables = {"baseUrl": base_url}
    all_results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for scenario_meta in test_scenarios:
            scenario = fetch_scenario(scenario_meta["path"])
            # defaults 병합
            if scenario.get("defaults"):
                for k, v in scenario["defaults"].items():
                    if k not in variables:
                        variables[k] = v

            prefix = f"/tmp/scenario_{scenario['id']}"
            result = run_scenario(browser, scenario, variables, auth_state_path, prefix)
            all_results.append(result)

        browser.close()

    # 요약
    print(f"\n{'='*50}")
    print(f"전체 시나리오 테스트 결과")
    print(f"대상: {base_url}")
    print(f"{'='*50}")

    pass_count = sum(1 for r in all_results if r["status"] == "pass")
    fail_count = len(all_results) - pass_count

    for r in all_results:
        icon = "PASS" if r["status"] == "pass" else "FAIL"
        step_pass = sum(1 for s in r["steps"] if s["status"] == "pass")
        step_total = len(r["steps"])
        fail_info = ""
        if r["status"] == "fail":
            fail_step = next((s for s in r["steps"] if s["status"] == "fail"), None)
            if fail_step:
                fail_info = f" — {fail_step['desc']}"
                if fail_step.get("error"):
                    fail_info += f": {fail_step['error']}"
        print(f"  {icon} {r['name']} ({step_pass}/{step_total} 스텝){fail_info}")

    print(f"\n전체: {len(all_results)}개 중 {pass_count}개 성공, {fail_count}개 실패")
    return all_results


def run_repeat(base_url, scenario_path, repeat_count, auth_state_path):
    """특정 시나리오를 N회 반복 실행"""
    scenario = fetch_scenario(scenario_path)
    variables = {"baseUrl": base_url}
    if scenario.get("defaults"):
        variables.update(scenario["defaults"])

    all_rounds = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for r in range(1, repeat_count + 1):
            prefix = f"/tmp/scenario_{scenario['id']}_r{r}"
            result = run_scenario(browser, scenario, variables, auth_state_path, prefix, f"[{r}/{repeat_count}회차]")
            result["round"] = r
            all_rounds.append(result)

            # 세션 만료 시 중단
            if any("세션 만료" in s.get("error", "") for s in result["steps"]):
                print(f"\n세션 만료 — 재로그인 필요. 테스트 중단.")
                break

        browser.close()

    # 요약
    print(f"\n{'='*50}")
    print(f"반복 테스트 결과 — {scenario['name']} ({len(all_rounds)}회)")
    print(f"대상: {base_url}")
    print(f"{'='*50}")

    pass_count = sum(1 for r in all_rounds if r["status"] == "pass")
    fail_count = len(all_rounds) - pass_count

    for r in all_rounds:
        icon = "PASS" if r["status"] == "pass" else "FAIL"
        step_pass = sum(1 for s in r["steps"] if s["status"] == "pass")
        step_total = len(r["steps"])
        fail_info = ""
        if r["status"] == "fail":
            fail_step = next((s for s in r["steps"] if s["status"] == "fail"), None)
            if fail_step:
                fail_info = f" — {fail_step['desc']}"
                if fail_step.get("error"):
                    fail_info += f": {fail_step['error']}"
        print(f"  {r['round']}회차: {icon} ({step_pass}/{step_total} 스텝){fail_info}")

    rate = (pass_count / len(all_rounds) * 100) if all_rounds else 0
    print(f"\n요약: {len(all_rounds)}회 중 {pass_count}회 성공, {fail_count}회 실패 (성공률 {rate:.1f}%)")
    return all_rounds


# ── 직접 실행 시 ──

if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    base_url = sys.argv[2] if len(sys.argv) > 2 else "https://instech.stg.3o3.co.kr"
    auth_path = sys.argv[3] if len(sys.argv) > 3 else "/tmp/instech_auth_state_stg.json"

    if mode == "all":
        feature = sys.argv[4] if len(sys.argv) > 4 else "age-calculation/"
        run_all(base_url, feature, auth_path)
    elif mode == "repeat":
        scenario_path = sys.argv[4] if len(sys.argv) > 4 else "age-calculation/input-to-result.json"
        repeat_count = int(sys.argv[5]) if len(sys.argv) > 5 else 3
        run_repeat(base_url, scenario_path, repeat_count, auth_path)
