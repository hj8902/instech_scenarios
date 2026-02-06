#!/bin/bash
set -e

# ─────────────────────────────────────────────
# instech 시나리오 테스트 스킬 설치 스크립트
# ─────────────────────────────────────────────

BASE_URL="https://hj8902.github.io/instech_scenarios"
SKILL_DIR="$HOME/.claude/skills/instech-scenario-test"
SCRIPTS_DIR="$SKILL_DIR/scripts"

echo ""
echo "=========================================="
echo "  instech 시나리오 테스트 스킬 설치"
echo "=========================================="
echo ""

# ── 1. Python3 확인 ──
echo "[1/4] Python3 확인..."
if ! command -v python3 &> /dev/null; then
    echo "  !! Python3이 설치되어 있지 않습니다."
    echo "  >> brew install python3"
    exit 1
fi
PYTHON_VERSION=$(python3 --version 2>&1)
echo "  OK: $PYTHON_VERSION"

# ── 2. Playwright 설치 ──
echo ""
echo "[2/4] Playwright 확인 및 설치..."
if python3 -c "import playwright" &> /dev/null; then
    echo "  OK: Playwright 이미 설치됨"
else
    echo "  >> pip3 install playwright 설치 중..."
    pip3 install playwright --quiet
    echo "  OK: Playwright 설치 완료"
fi

echo "  >> Chromium 브라우저 확인 중..."
if python3 -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(headless=True); b.close(); p.stop()" &> /dev/null 2>&1; then
    echo "  OK: Chromium 이미 설치됨"
else
    echo "  >> Chromium 설치 중..."
    python3 -m playwright install chromium
    echo "  OK: Chromium 설치 완료"
fi

# ── 3. 스킬 파일 다운로드 ──
echo ""
echo "[3/4] 스킬 파일 다운로드..."
mkdir -p "$SCRIPTS_DIR"

echo "  >> SKILL.md 다운로드..."
curl -sL "$BASE_URL/skill/SKILL.md" -o "$SKILL_DIR/SKILL.md"

echo "  >> scenario_runner.py 다운로드..."
curl -sL "$BASE_URL/scripts/scenario_runner.py" -o "$SCRIPTS_DIR/scenario_runner.py"

echo "  >> generate_report.py 다운로드..."
curl -sL "$BASE_URL/scripts/generate_report.py" -o "$SCRIPTS_DIR/generate_report.py"

echo "  OK: 파일 설치 완료"

# ── 4. 설치 확인 ──
echo ""
echo "[4/4] 설치 확인..."

ALL_OK=true

if [ -f "$SKILL_DIR/SKILL.md" ]; then
    echo "  OK: SKILL.md"
else
    echo "  !! SKILL.md 없음"
    ALL_OK=false
fi

if [ -f "$SCRIPTS_DIR/scenario_runner.py" ]; then
    echo "  OK: scenario_runner.py"
else
    echo "  !! scenario_runner.py 없음"
    ALL_OK=false
fi

if [ -f "$SCRIPTS_DIR/generate_report.py" ]; then
    echo "  OK: generate_report.py"
else
    echo "  !! generate_report.py 없음"
    ALL_OK=false
fi

echo ""
if [ "$ALL_OK" = true ]; then
    echo "=========================================="
    echo "  설치 완료!"
    echo "=========================================="
    echo ""
    echo "  사용법:"
    echo "  1. Claude Code를 실행합니다"
    echo "  2. /instech-scenario-test 를 입력합니다"
    echo "  3. 안내에 따라 환경, 시나리오를 선택합니다"
    echo ""
    echo "  시나리오 뷰어: $BASE_URL/"
    echo ""
else
    echo "=========================================="
    echo "  설치 실패 - 위 에러를 확인해주세요"
    echo "=========================================="
    exit 1
fi
