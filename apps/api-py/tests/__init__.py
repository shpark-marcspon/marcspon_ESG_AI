"""esgapi 패키지 밖의 테스트. 이미지에 들어가지 않는다.

    support/    세 층이 같이 쓰는 도구: 키 쌍, EDK 인 척 토큰 만들기, 교환해서 세션 얻기
    security/   보안 층: 앱 역할(esg_app)로 붙어 테넌트 경계·역할 권한·연결 상태를 잰다.
                따로 부른다(scripts/test-security.sh)

순수 층과 업무 층의 테스트는 모듈 곁에 있다(esgapi/<모듈>/tests/).
"""
