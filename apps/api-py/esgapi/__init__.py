"""esgapi: Python(Django + django-ninja) API. 본 저장소의 바닥.

    config/        띄우는 법: 설정, 주소표, NinjaAPI 하나(모듈의 라우터를 모은다)
    core/          모듈들이 같이 딛는 바닥: 오류의 꼴, 공통 모델, 테넌시, 포트
    <모듈>/        업무 모듈 여섯. 하나가 Django app 하나다
                   greenwash · inventory · organization · reconcile · reference · user

의존은 한 방향이다(`.importlinter` 의 계약 열다섯이 지킨다).

    config ──▶ <모듈> ──▶ core
    <모듈>의 service/apis ──▶ service/services · service/selectors ──▶ models ·
        순수 모듈(calc/, engines/, service/utils/ …)
"""
