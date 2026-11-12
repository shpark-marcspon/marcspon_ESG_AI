"""Django app 의 목록과 사용자 모델의 설정 셋. 상수뿐이다. 설정 넷(base·migrate·test_business·test_security)이 전부
이것을 읽는다.

Django 를 import 하지 않는다. core 와 실행 층(runs)과 업무 모듈이 전부 올라 있다. 모델을 처음 만드는 밴드는
이 파일을 고치지 않는다: 자기 모듈의 models(models.py 또는 models/ 패키지)를 만들고
`manage.py makemigrations <모듈>` 을 돌리면 된다.

contrib 둘(contenttypes·auth)은 사용자 표(user.User = AbstractUser)가 기댄다(K1u-a). 세션·admin·AuthenticationMiddleware
는 켜지 않는다(로그인은 K2). core 가 맨 앞이다(config/tests/test_settings.py).
"""

INSTALLED_APPS = [
    "esgapi.core",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "esgapi.organization",
    "esgapi.user",
    "esgapi.inventory",
    "esgapi.reference",
    "esgapi.reconcile",
    "esgapi.greenwash",
    "esgapi.translation",
    "esgapi.dataverify",
    "esgapi.materiality",
    "esgapi.drafting",
    "esgapi.runs",
    "esgapi.runbundle",
]

AUTH_USER_MODEL = "user.User"
# 인증 백엔드를 두지 않는다(이 밴드에서 authenticate() 를 부르는 곳이 없다 — K2 가 자기 백엔드를 단다).
# 기본값(ModelBackend 하나)이면 username 이 unique 가 아닐 때 auth.W004 가 아니라 오류 auth.E003 이다.
AUTHENTICATION_BACKENDS: list[str] = []
# username 은 회사 안에서만 unique 다(운영팀은 전역 — 조건부 UNIQUE 둘). 그래서 끄는 검사는 auth.W004 하나다(결정 6).
SILENCED_SYSTEM_CHECKS = ["auth.W004"]
