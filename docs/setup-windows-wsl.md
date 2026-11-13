# Windows 에서 개발 환경 만들기 (WSL2)

Windows PC 에서 이 저장소를 고치고 테스트하려는 사람을 위한 글이다. macOS·리눅스는 [`development.md`](development.md) 의 「띄우는 법」을 따르면 된다.

## 먼저 알아 둘 것: Windows 네이티브로는 테스트가 돌지 않는다

`apps/api-py/esgapi/core/resources/pdf.py` 가 리눅스·macOS 전용 표준 모듈 `resource` 를 가져와 PDF 검사 프로세스의 메모리·CPU 를 제한한다(`RLIMIT_AS` 등). Windows 에는 이 모듈이 없다. Django 가 시작하면서 모든 앱을 불러오므로, 한 모듈의 테스트만 돌려도 `pytest` 가 시작 단계에서 다음 오류로 죽는다.

```
ModuleNotFoundError: No module named 'resource'
```

`uv sync` 는 Windows 에서도 통과하므로 설치만 보면 되는 것처럼 보이지만, 테스트는 돌지 않는다. **WSL2 의 Ubuntu 안에서 작업한다.** 이 코드를 Windows 용으로 고치지 않았다(리눅스의 자원 제한을 우회하는 일이고, Docker 이미지와 `scripts/verify.sh` 도 리눅스 기준이다).

## 한눈에 보기

| 단계 | 어디서 | 필요한 때 |
|---|---|---|
| 1. WSL2 + Ubuntu | Windows (관리자 PowerShell) | 항상 |
| 2. 저장소 clone, uv | Ubuntu | 항상 |
| 3. `.env`, git 훅, `uv sync` | Ubuntu | 항상 |
| 4. 기준선 테스트 | Ubuntu | 항상 |
| 5. Docker Desktop 연동 | Windows + Ubuntu | 업무·보안·통합 테스트, `docker compose` |
| 6. Node 22 이상 + pnpm 10 | Ubuntu | 웹, `scripts/verify.sh` |

모듈의 코드를 고치고 순수 층 테스트만 돌릴 때는 1~4 면 된다.

## 1. WSL2 와 Ubuntu

관리자 권한 PowerShell:

```powershell
wsl --install -d Ubuntu
```

설치가 끝나면 Ubuntu 창이 열리고 리눅스 사용자 이름과 비밀번호를 묻는다. 직접 입력한다. 재부팅을 요청하면 따른다.

확인:

```powershell
wsl -l -v        # Ubuntu 가 VERSION 2 로 보이면 된다
```

## 2. clone 과 uv (Ubuntu 안에서)

**저장소는 리눅스 홈(`~`) 아래에 둔다.** `/mnt/c/...`(Windows 폴더) 아래에 두면 파일 접근이 매우 느리다.

```bash
cd ~
git clone https://github.com/shpark-marcspon/marcspon_ESG_AI.git
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env        # 새 터미널을 열었다면 필요 없다
uv --version
```

esg-lab(공급사의 측정·실험 저장소)이 필요한 작업이면 나란히 둔다. 골든 파일을 다시 만드는 스크립트(`make-golden.sh`)가 `ESG_LAB=<경로>` 로 이 저장소를 가리킨다.

```bash
git clone https://github.com/shpark-marcspon/marcspon_ESG_lab_main.git
```

git 사용자 정보가 없으면 커밋이 실패한다.

```bash
git config --global user.name  "<이름>"
git config --global user.email "<이메일>"
```

## 3. 설정, 훅, 의존성

```bash
cd ~/marcspon_ESG_AI
cp .env.example .env                           # 로컬용 설정. 가짜 비밀번호뿐이다
git config core.hooksPath scripts/git-hooks    # 커밋 때 ruff · import-linter · 건드린 모듈의 순수 테스트
cd apps/api-py
uv sync                                        # Python 3.13 을 uv 가 알아서 받는다
```

- Python 3.13 을 따로 설치하지 않는다. `pyproject.toml` 의 `requires-python = ">=3.13,<3.14"` 를 보고 uv 가 받는다.
- **`.env` 의 LLM 키는 비워 둔다.** `LLM_RUN_MODE` 가 비면 모의 공급사만 쓰고, 키가 있어도 실제로 호출하지 않는다. `live` 로 바꾸면 실제 비용이 나간다. 켜는 조건은 `development.md` 의 「실 공급사 전환 점검표」를 따른다.
- 훅 설정(`core.hooksPath`)은 clone 마다 한 번 해야 한다. 저장소에 들어 있지 않다.
- 훅 파일에 실행 권한이 있어야 git 이 부른다. 처음 올린 저장소는 `.sh` 파일 전부가 실행 권한 없이(`100644`) 들어 있어서, 훅을 연결해도 `hint: The 'scripts/git-hooks/pre-commit' hook was ignored because it's not set as executable.` 라는 안내만 나오고 돌지 않았다. `pre-commit` 과 이 글에 나오는 실행 스크립트(`scripts/verify.sh`, `scripts/with-build-lock.sh`, `apps/api-py/scripts/test-*.sh`)에는 권한을 주어 두었다. 이 안내가 다시 보이면 `git pull` 로 최신을 받았는지 본다.
- `scripts/git-hooks/post-commit` 은 일부러 실행 권한을 주지 않았다. 공급사 내부 도구(maricom)로 커밋 트레일러를 보내는 훅이라 이 저장소를 고치는 데 필요하지 않다. 권한이 없으면 git 이 무시한다.

## 4. 기준선 확인

코드를 고치기 전에 한 번 돌려서, 나중에 깨진 것이 내 변경 때문인지 가린다.

```bash
cd ~/marcspon_ESG_AI/apps/api-py
uv run pytest -q -m "not django_db and not security" esgapi/drafting
```

기대 결과(2026-11-13, Ubuntu on WSL2, uv 0.13.8 에서 확인):

```
412 passed, 122 deselected in 7s
```

`122 deselected` 는 정상이다. DB 가 필요한 업무 층(`django_db`) 시험이라 위 조건으로 뺀 것이다.

다른 모듈도 같은 꼴이다.

```bash
uv run pytest -q -m "not django_db and not security" esgapi/<모듈>
```

## 5. Docker Desktop (업무·통합 시험, 컨테이너)

> 이 단계는 아직 이 PC들에서 끝까지 확인하지 못했다. 막히면 아래 「막힐 때」를 보고, 해결한 방법을 이 문서에 보태 달라.

1. Windows 에 Docker Desktop 을 설치하고 **실행**한다. 꺼져 있으면 `docker` 명령이 엔진에 못 닿는다.
2. Docker Desktop → Settings → Resources → WSL integration 에서 **Ubuntu 를 켠다**.
3. Ubuntu 에서 확인한다.

```bash
docker info | head -3
cd ~/marcspon_ESG_AI && docker compose up -d --build --wait
docker compose ps -a        # 여섯이 running, migrate-py 는 Exited (0) 이면 된다
```

이미지를 동시에 지으면 메모리가 모자라 죽는다. 이 저장소는 빌드 잠금(`scripts/with-build-lock.sh`)을 둔다. 손으로 지을 때는 `scripts/with-build-lock.sh docker compose build` 를 쓴다.

## 6. Node 와 pnpm (웹, 전량 게이트)

> 이 단계도 아직 확인하지 못했다. 보고서 같은 Python 모듈만 고칠 때는 필요 없다.

`package.json` 이 Node 22 이상, `pnpm@10.28.1` 을 요구한다. `scripts/verify.sh --fast` 도 `pnpm install` 과 typecheck 를 돌리므로 Node 가 없으면 중간에 실패한다.

```bash
# nvm 등으로 Node 22 이상을 설치한 뒤
corepack enable
corepack prepare pnpm@10.28.1 --activate
```

## 작업 규칙 (모르고 하면 막히는 것)

- **코드는 Ubuntu 의 `~/marcspon_ESG_AI` 에서만 고친다.** Windows 폴더에 같은 저장소를 또 clone 해서 두 곳을 같이 고치지 않는다.
- 줄바꿈은 `.gitattributes` 가 LF 로 고정한다(`* text=auto eol=lf`). 골든 파일을 sha256·바이트로 견주는 시험이 있어서, CRLF 로 풀리면 깨진다. 새 clone 은 저절로 맞다.
- 완료 판정은 `scripts/verify.sh` 의 `VERIFY=PASS` 다. `--fast` 는 컨테이너 없이 도는 빠른 게이트이고 완료 판정이 아니다.
- 시험을 약하게 고쳐서 통과시키지 않는다(`scripts/check_test_weakening.py` 가 잡는다).
- 모듈끼리 import 하는 방향은 계약(`lint-imports`)으로 고정돼 있다. 다른 흐름의 엔진을 가져다 쓰면 실패한다.
- 시험 파일은 `esgapi/<모듈>/tests/` 아래 정해진 자리에 둔다(`scripts/check_test_layout.py`).

## 막힐 때

| 증상 | 원인 | 처방 |
|---|---|---|
| `ModuleNotFoundError: No module named 'resource'` | Windows 네이티브 Python 으로 돌렸다 | WSL2 Ubuntu 안에서 돌린다 |
| `uv: command not found` | 설치 직후 PATH 가 옛 값이다 | 터미널(VS Code 면 VS Code 전체)을 닫고 다시 연다. Ubuntu 에서는 `source $HOME/.local/bin/env` |
| `error during connect ... dockerDesktopLinuxEngine` | Docker Desktop 이 꺼져 있다 | Docker Desktop 을 실행한다 |
| Ubuntu 안에서 `docker` 가 없다 | WSL integration 이 꺼져 있다 | 5 단계의 2 |
| 파일 접근·`uv sync` 가 유난히 느리다 | 저장소가 `/mnt/c/...` 아래에 있다 | `~` 아래로 옮긴다 |
| 커밋이 `Please tell me who you are` 로 실패한다 | git 사용자 정보가 없다 | 2 단계의 `git config --global` |

## VS Code

확장 「WSL」을 설치하고, Ubuntu 터미널에서 다음을 실행하면 그 clone 이 그대로 열린다.

```bash
cd ~/marcspon_ESG_AI && code .
```

권장 확장: Ruff(`charliermarsh.ruff`), Pylance, Python. 이 저장소는 pyright strict 로 검사한다.
