#!/usr/bin/env python3
"""
instech 시나리오 범용 러너
- 시나리오 JSON을 읽어서 모든 step을 자동으로 Playwright 코드로 변환/실행
- 병렬 실행 지원 (MAX_WORKERS 설정 가능)
"""

import glob
import json
import os
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright

SCENARIOS_BASE_URL = "https://hj8902.github.io/instech_scenarios/scenarios"
MAX_WORKERS = 4  # 최대 병렬 브라우저 컨텍스트 수
ACTION_SETTLE_MS = 200  # React 상태 커밋 대기 (fill/blur/click/clear 후)


# ── JSON fetch ──

def fetch_json(url):
    # GitHub Pages CDN 캐시 우회
    cache_bust = f"?_={int(time.time())}"
    req = urllib.request.Request(url + cache_bust, headers={"User-Agent": "scenario-runner"})
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
        required = step.get("required", False)
        result_msg = handle_terms(page)
        if "비활성" in result_msg:
            return {"status": "fail", "desc": f"{desc} — {result_msg}"}
        if "미노출" in result_msg and required:
            return {"status": "fail", "desc": f"{desc} — 바텀시트가 나타나야 하나 미노출 (required=true)"}
        return {"status": "pass", "desc": f"{desc} — {result_msg}"}

    elif action == "injectStoreData":
        store = step.get("store", "")
        data = step.get("data", {})
        store_var = f"__{'COUNSEL' if store == 'COUNSEL' else store}_STORE__"
        js_data = json.dumps(data)
        page.evaluate(f"""() => {{
            const store = window.{store_var};
            if (store) store.setState({js_data});
        }}""")
        return {"status": "pass", "desc": desc}

    elif action == "fetchAndInjectUserInfo":
        store = step.get("store", "")
        store_var = f"__{'COUNSEL' if store == 'COUNSEL' else store}_STORE__"
        user_data = step.get("userData")
        if not user_data:
            return {"status": "fail", "desc": desc, "error": "userData 필드가 없습니다. 시나리오에 userData를 추가하세요."}
        js_data = json.dumps(user_data, ensure_ascii=False)
        result = page.evaluate(f"""() => {{
            try {{
                const store = window.{store_var};
                if (!store) return {{ error: 'window.{store_var} not found' }};
                store.setState({{ userInfo: {js_data} }});
                return {{ ok: true }};
            }} catch (e) {{
                return {{ error: String(e) }};
            }}
        }}""")
        if result and result.get("error"):
            return {"status": "fail", "desc": f"{desc} — {result['error']}"}
        name = user_data.get("name", "?")
        gender = user_data.get("gender", "(없음)")
        return {"status": "pass", "desc": f"{desc} [name={name}, gender={gender or '(없음)'}]"}

    elif action == "setSessionStorage":
        key = step.get("key", "")
        value = step.get("value", "")
        if page.url == "about:blank":
            # 아직 navigate 전 — init script로 등록하면 다음 페이지 JS 실행 전에 설정됨
            context["browser_context"].add_init_script(f"sessionStorage.setItem('{key}', '{value}')")
        else:
            page.evaluate(f"sessionStorage.setItem('{key}', '{value}')")
        return {"status": "pass", "desc": desc}

    elif action == "saveState":
        path = context.get("auth_state_path", "/tmp/instech_auth_state.json")
        context["browser_context"].storage_state(path=path)
        return {"status": "pass", "desc": desc}

    elif action == "launchBrowser":
        # 브라우저 재실행은 러너 레벨에서 처리
        return {"status": "pass", "desc": desc}

    elif action == "retryUntilGa":
        target_ga_id_raw = step.get("targetGaCompanyId")
        max_retries = step.get("maxRetries", 20)
        click_selector = step.get("clickSelector", "button:has-text('확인했어요')")

        if not target_ga_id_raw:
            return {"status": "fail", "desc": desc, "error": "targetGaCompanyId가 지정되지 않았습니다."}

        # 변수 치환 후 문자열이 되므로 int 변환 (API 응답은 정수)
        try:
            target_ga_id = int(target_ga_id_raw)
        except (ValueError, TypeError):
            return {"status": "fail", "desc": desc, "error": f"targetGaCompanyId가 숫자가 아닙니다: {target_ga_id_raw}"}

        for attempt in range(1, max_retries + 1):
            matched = [False]
            ga_id_found = [None]
            ga_name_found = [None]

            def handle_route(route):
                """available-ga 응답을 인터셉트하여 GA ID 확인.
                매칭 시 응답을 그대로 전달 (→ onSuccess → complete 이동).
                불일치 시 abort (→ onError → ConfirmBottomSheet 유지 → 재클릭).
                """
                try:
                    response = route.fetch()
                    body = response.json()
                    ga_id = body.get("data", {}).get("gaCompanyId")
                    ga_name_found[0] = body.get("data", {}).get("gaCompanyName", "")
                    ga_id_found[0] = ga_id
                    if ga_id == target_ga_id:
                        matched[0] = True
                        route.fulfill(response=response)
                    else:
                        route.abort()
                except Exception:
                    route.abort()

            page.route("**/available-ga**", handle_route)

            try:
                page.locator(click_selector).first.click()
                page.wait_for_timeout(1500)
            except Exception as e:
                page.unroute("**/available-ga**")
                return {"status": "fail", "desc": desc, "error": f"클릭 실패: {e}"}

            page.unroute("**/available-ga**")

            if matched[0]:
                return {"status": "pass", "desc": f"{desc} — {attempt}회차에 GA 매칭 (id={ga_id_found[0]}, {ga_name_found[0]})"}

            # GA 불일치 — abort로 onError 발생, ConfirmBottomSheet 유지
            print(f"    [{attempt}/{max_retries}] GA 불일치: id={ga_id_found[0]} ({ga_name_found[0]})")
            page.wait_for_timeout(500)

        return {"status": "fail", "desc": desc, "error": f"{max_retries}회 시도 후 원하는 GA(id={target_ga_id})를 배정받지 못함"}

    elif action == "cancelExistingCounsel":
        base_url = step.get("baseUrl", "")
        page.goto(f"{base_url}/car-insurance/history")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # 상담 없으면 history.back()으로 이동하므로 URL로 판별
        if "/car-insurance/history" not in page.url:
            return {"status": "pass", "desc": f"{desc} — 기존 상담 없음 (skip)"}

        # 상담 항목 있음 — 모든 "상담 취소하기" 버튼 클릭
        cancelled = 0
        max_attempts = 10
        for _ in range(max_attempts):
            cancel_btn = page.locator("button:has-text('상담 취소하기')").first
            try:
                cancel_btn.wait_for(state="visible", timeout=3000)
            except Exception:
                break  # 더 이상 취소할 항목 없음

            cancel_btn.click()
            page.wait_for_timeout(500)

            # 모달 "상담 취소" 버튼 클릭
            modal = page.locator("[role='dialog'], [aria-modal='true']")
            if modal.count() > 0:
                confirm_btn = modal.locator("button:has-text('상담 취소')").first
                try:
                    confirm_btn.wait_for(state="visible", timeout=3000)
                    confirm_btn.click()
                    page.wait_for_timeout(1500)  # API 응답 + 리스트 갱신 대기
                    cancelled += 1
                except Exception:
                    break

            # 상담 전부 취소되면 history.back() 발생
            if "/car-insurance/history" not in page.url:
                break

        return {"status": "pass", "desc": f"{desc} — {cancelled}건 취소"}

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
    scenario_name = scenario['name']
    print(f"\n{'='*50}")
    print(f"{label}{scenario_name}")
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
    page.set_default_timeout(10000)  # 셀렉터 타임아웃 10초 (기본 30초 → 단축)

    context = {
        "screenshot_path": screenshot_prefix,
        "auth_state_path": auth_state_path,
        "browser_context": ctx,
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
            break  # 실패 시 이후 스텝은 의미 없으므로 즉시 중단

    ctx.close()
    return {
        "id": scenario.get("id", ""),
        "name": scenario_name,
        "description": scenario.get("description", ""),
        "precondition": scenario.get("precondition", ""),
        "steps": results,
        "status": scenario_status,
    }


# ── 병렬 실행을 위한 워커 함수 ──

def _run_worker_batch(batch):
    """워커 1개가 브라우저 1개로 할당된 시나리오 그룹을 순차 실행."""
    auth_state_path = batch["auth_state_path"]
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for item in batch["items"]:
            result = run_scenario(
                browser, item["scenario"], item["variables"],
                auth_state_path, item["screenshot_prefix"]
            )
            results.append((item["index"], result))
        browser.close()

    return results


# ── 전체 실행 / 반복 실행 ──

def _matches_labels(scenario_labels, filter_labels):
    """라벨 필터 매칭. 각 filter_label 간은 AND, 쉼표로 구분된 값은 OR.
    예: ["happy-path", "inperson,phone"] → happy-path AND (inperson OR phone)
    """
    for fl in filter_labels:
        alternatives = [x.strip() for x in fl.split(",")]
        if not any(alt in scenario_labels for alt in alternatives):
            return False
    return True


def _run_parallel(tasks, auth_state_path):
    """태스크 리스트를 MAX_WORKERS 만큼 병렬 실행하고 결과 리스트 반환."""
    total = len(tasks)
    workers = min(MAX_WORKERS, total)
    for i, task in enumerate(tasks):
        task["index"] = i

    batches = [{"auth_state_path": auth_state_path, "items": []} for _ in range(workers)]
    for i, task in enumerate(tasks):
        batches[i % workers]["items"].append(task)

    results = [None] * total
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_run_worker_batch, batch) for batch in batches]
        for future in as_completed(futures):
            try:
                for idx, result in future.result():
                    results[idx] = result
            except Exception as e:
                print(f"  워커 에러: {e}")
    return results


def _pre_cancel_counsel(browser, base_url, auth_state_path):
    """엣지 케이스 그룹 실행 전 기존 상담 1회 취소"""
    print(f"\n{'='*50}")
    print(f"[전처리] 엣지 케이스 실행 전 기존 상담 취소")
    print(f"{'='*50}")
    try:
        ctx = browser.new_context(storage_state=auth_state_path)
        page = ctx.new_page()
        page.set_default_timeout(10000)
        step = {"action": "cancelExistingCounsel", "baseUrl": base_url, "description": "엣지 케이스 전처리 — 기존 상담 취소"}
        context = {"screenshot_path": None, "auth_state_path": auth_state_path, "browser_context": ctx, "step_num": 0}
        result = execute_step(page, step, context)
        icon = "OK" if result["status"] == "pass" else "FAIL"
        print(f"  [{icon}] {result['desc']}")
        ctx.close()
    except Exception as e:
        print(f"  [FAIL] 상담 취소 실패: {e}")
        try:
            ctx.close()
        except Exception:
            pass


def run_all(base_url, feature_path, auth_state_path, category=None, extra_vars=None, labels=None):
    """특정 기능의 전체 시나리오 실행.
    counsel 기능은 상담 충돌 방지를 위해 단일 워커로 순차 실행.
    labels: 라벨 필터 리스트. 각 항목 간 AND, 쉼표 구분 시 OR.
      예: ["happy-path", "inperson,phone"] → happy-path AND (inperson OR phone)
    """
    index = fetch_index()
    test_scenarios_meta = [
        s for s in index["scenarios"]
        if s["type"] in ("test", "state-setup") and s["path"].startswith(feature_path)
        and (labels is None or _matches_labels(s.get("labels", []), labels))
    ]

    # ── 해피패스/엣지케이스 동시 실행 방지 ──
    has_happy = any("happy-path" in s.get("labels", []) for s in test_scenarios_meta)
    has_edge = any("edge-case" in s.get("labels", []) for s in test_scenarios_meta)
    if has_happy and has_edge:
        print("\n[ERROR] 해피패스와 엣지케이스를 동시에 실행할 수 없습니다.")
        print("  → --label happy-path 또는 --label edge-case 를 추가하여 분리 실행하세요.")
        print(f"  현재 필터: {labels}")
        matched_names = [s["name"] for s in test_scenarios_meta]
        print(f"  매칭된 시나리오 ({len(matched_names)}개):")
        for name in matched_names:
            print(f"    - {name}")
        return []

    if not test_scenarios_meta:
        print("실행할 시나리오가 없습니다.")
        return []

    # HTTPS 강제
    if base_url.startswith("http://"):
        base_url = base_url.replace("http://", "https://", 1)
        print(f"[INFO] HTTP → HTTPS 자동 변환: {base_url}")

    # 시나리오 JSON 미리 fetch (병렬 실행 전)
    variables = {"baseUrl": base_url}
    tasks = []
    for meta in test_scenarios_meta:
        scenario = fetch_scenario(meta["path"])
        if scenario.get("defaults"):
            for k, v in scenario["defaults"].items():
                if k not in variables:
                    variables[k] = v
        # extra_vars는 defaults보다 우선 (사용자 지정 값)
        if extra_vars:
            variables.update(extra_vars)
        tasks.append({
            "scenario": scenario,
            "variables": dict(variables),
            "screenshot_prefix": f"/tmp/scenario_{scenario['id']}",
            "labels": meta.get("labels", []),
        })

    total = len(tasks)
    is_counsel = feature_path.startswith("counsel")

    # counsel: 해피패스(상담 생성)는 순차, 엣지케이스(UI 검증)는 병렬 가능
    if is_counsel:
        happy_tasks = [t for t in tasks if "edge-case" not in t.get("labels", [])]
        edge_tasks = [t for t in tasks if "edge-case" in t.get("labels", [])]
    else:
        happy_tasks = tasks
        edge_tasks = []

    all_results = []

    # ── 해피패스/상태설정: 순차 실행 (상담 충돌 방지) ──
    if happy_tasks:
        if is_counsel:
            print(f"\n[순차] 해피패스/상태설정 {len(happy_tasks)}개 실행 (브라우저 1개)")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                for task in happy_tasks:
                    result = run_scenario(browser, task["scenario"], task["variables"],
                                          auth_state_path, task["screenshot_prefix"])
                    all_results.append(result)
                browser.close()
        else:
            workers = min(MAX_WORKERS, len(happy_tasks))
            print(f"\n시나리오 {len(happy_tasks)}개 실행 (브라우저 {workers}개{' 순차' if workers == 1 else ' 병렬'})")
            if workers == 1:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    for task in happy_tasks:
                        result = run_scenario(browser, task["scenario"], task["variables"],
                                              auth_state_path, task["screenshot_prefix"])
                        all_results.append(result)
                    browser.close()
            else:
                all_results = _run_parallel(happy_tasks, auth_state_path)

    # ── 엣지케이스: 병렬 실행 (상담 미생성, UI 검증만) ──
    if edge_tasks:
        workers = min(MAX_WORKERS, len(edge_tasks))
        print(f"\n[병렬] 엣지케이스 {len(edge_tasks)}개 실행 (브라우저 {workers}개)")
        # 첫 실행 전 기존 상담 1회 취소
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            _pre_cancel_counsel(browser, base_url, auth_state_path)
            browser.close()
        if workers == 1:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                for task in edge_tasks:
                    result = run_scenario(browser, task["scenario"], task["variables"],
                                          auth_state_path, task["screenshot_prefix"])
                    all_results.append(result)
                browser.close()
        else:
            edge_results = _run_parallel(edge_tasks, auth_state_path)
            all_results.extend(edge_results)

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


# ── 직접 실행 시 ──

if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    base_url = sys.argv[2] if len(sys.argv) > 2 else "https://instech.stg.3o3.co.kr"
    auth_path = sys.argv[3] if len(sys.argv) > 3 else "/tmp/instech_auth_state_stg.json"

    if mode == "all":
        feature = sys.argv[4] if len(sys.argv) > 4 else "age-calculation/"
        category = sys.argv[5] if len(sys.argv) > 5 else None
        run_all(base_url, feature, auth_path, category=category)
