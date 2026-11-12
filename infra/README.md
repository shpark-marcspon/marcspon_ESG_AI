# infra — esg-app 을 AWS 에 올릴 때의 인프라 (Terraform)

`compose.yaml` 이 내 컴퓨터에 띄우는 것(api, worker + 파서, PostgreSQL, Redis, S3 호환 저장소)을 AWS 의 자원으로 옮겨 적은 코드다. 루트 [README 의 「AWS 의 무엇에 대응하는가」](../README.md#aws-의-무엇에-대응하는가) 표를 코드로 풀어 쓴 것이라고 보면 된다.

**이 코드는 한 번도 적용(apply)되지 않았다.** AWS 계정도 자격 증명도 없이 썼고, 확인한 것은 「문법이 맞다, 자원의 인자 이름이 공급자의 정의와 맞다, 가짜 공급자 위에서 세운 계획의 값이 기대와 같다」까지다. AWS 가 이 계획을 실제로 받아 주는지는 모른다. 무엇을 확인했고 무엇을 못 했는지는 [아래](#계정-없이-확인한-것과-못-한-것)에 갈라 적었다.

스택(서버 틀, 큐의 종류, worker 의 형태)은 정해진 것이 아니다. 그래서 스택이 바뀌어도 남는 부분과 바뀌면 버리는 부분을 모듈로 갈라 두었다.

## 폴더

```
infra/
  README.md                      ← 이 글
  terraform/
    bin/tf                       Terraform 을 깔지 않고 돌리는 스크립트(고정한 공식 이미지를 컨테이너로)
    verify.sh                    전체 확인(모양 → 플러그인 → 문법 → 테스트 → 규칙·정책의 수 → git). 계정 없이 돈다
    modules/
      network/                   VPC, 서브넷, 라우팅, NAT(끄고 켠다), 보안 그룹        ┐
      storage/                   업로드용 S3 버킷(+ 프론트 버킷 자리)                 │ 스택이 바뀌어도
      registry/                  ECR 저장소 둘(server, parser)과 정리 규칙            │ 남는 것
      iam/                       실행 역할, api·worker 의 태스크 역할                 │
      logs/                      CloudWatch 로그 그룹 넷                              ┘
      queue_redis/               ElastiCache(Redis). 큐가 Redis 기반일 때만           ┐ 스택에 따라
      database/                  Aurora PostgreSQL(Serverless v2), 접속 주소 비밀 그릇 │ 달라지는 것
      compute/                   ECS 클러스터, ALB, api·worker 서비스, migrate 태스크  ┘ (변수로 끈다)
    envs/
      practice/                  모듈 여덟을 엮은 환경 하나
        main.tf                  ← 여기부터 읽는다
        variables.tf  outputs.tf  versions.tf  providers.tf
        terraform.tfvars.example 내 값을 적는 파일의 예시
        .terraform.lock.hcl      공급자의 정확한 버전과 지문(커밋한다)
        tests/*.tftest.hcl       가짜 공급자 위의 테스트
```

모듈 하나는 파일 넷이다: `main.tf`(자원), `variables.tf`(받는 값), `outputs.tf`(내주는 값), `versions.tf`(요구하는 도구 버전).

## 돌려 보기 (계정이 필요 없다)

필요한 것은 Docker 뿐이다.

```sh
infra/terraform/verify.sh          # 전부. 단계마다 EXIT=<코드> 를 찍고, 마지막 줄이 EXIT=0 이면 통과
```

하나씩 돌릴 때:

```sh
cd infra/terraform
bin/tf fmt -check -recursive                       # 글의 모양
bin/tf -chdir=envs/practice init -backend=false    # 공급자 플러그인 받기(처음 한 번은 수백 MB 를 받는다)
bin/tf -chdir=envs/practice validate               # 문법, 자원 인자의 이름과 꼴
bin/tf -chdir=envs/practice test                   # 테스트 전부
bin/tf -chdir=envs/practice test -verbose -filter=tests/network.tftest.hcl   # 하나만, 계획을 펼쳐서
```

`bin/tf` 는 Terraform 을 이 컴퓨터에 깔지 않고 돌린다. 버전을 고정한 공식 이미지를 컨테이너로 띄워 인자를 그대로 넘길 뿐이다. 컨테이너에는 저장소 폴더만 붙고(`~/.aws` 와 환경 변수가 들어가지 않는다), `init` 말고는 네트워크를 끊고 돈다. **그래서 `bin/tf` 로는 실제 AWS 에 닿을 수 없다.** 실제로 적용할 때는 직접 깐 `terraform` 을 쓴다([처음 적용하는 차례](#처음-적용하는-차례-돌려-보지-않았다)).

### 고정한 버전

| 무엇 | 버전 | 어디에 적혀 있는가 | 확인 (2026-10-05) |
|---|---|---|---|
| Terraform | 1.16.5 | `bin/tf` 의 이미지 태그와 다이제스트, `envs/practice/versions.tf` 의 `required_version` | 그날의 최신. <https://checkpoint-api.hashicorp.com/v1/check/terraform> |
| AWS 공급자 `hashicorp/aws` | 6.67.0 | `envs/practice/versions.tf`, `.terraform.lock.hcl` | 그날의 최신(2026-09-30 게시). <https://registry.terraform.io/providers/hashicorp/aws/6.67.0> |

공급자는 버전마다 자원의 인자가 달라진다. 올릴 때는 `versions.tf` 의 숫자를 바꾸고 `terraform init -upgrade` 로 잠금 파일을 새로 만든 뒤 `verify.sh` 를 다시 돌린다.

라이선스: Terraform 1.6 부터는 BSL 이다. 1.16.5 의 [LICENSE](https://github.com/hashicorp/terraform/blob/v1.16.5/LICENSE)(2026-10-05 확인)는 「Terraform 을 남에게 호스팅·내장 형태로 제공해 유료판과 경쟁하는 것」만 막고 그 밖의 운영 사용을 허락한다고 적혀 있다. 인프라를 만드는 데 쓰는 것은 여기에 해당하지 않는다고 읽었다. 다만 [공식 FAQ](https://www.hashicorp.com/license-faq) 의 「고객의 인프라를 돕는 컨설턴트」 항목은 답 본문을 읽지 못했다(페이지가 자동 조회를 막는다). 브라우저로 한 번 읽어 보기를 권한다. 같은 문법을 쓰는 OpenTofu 로 바꿀 수 있는지는 시험하지 않았다.

## 읽는 차례

AWS 가 처음이면 이 순서가 덜 힘들다. 파일마다 자원 위에 「이것이 무엇이고 왜 이 설정인가」를 적어 두었다.

1. `envs/practice/main.tf` — 모듈 여덟이 어떻게 엮이는가. 맨 위의 그림과 `module.x.y` 로 오가는 값만 본다(10분).
2. `modules/storage/main.tf` — 가장 쉽다. 버킷 하나에 설정 자원이 여럿 붙는 꼴을 익힌다.
3. `modules/network/main.tf` — 가장 낯설고 가장 중요하다. 서브넷의 공개/사설이 무엇으로 갈리는지, 보안 그룹의 그림.
4. `modules/iam/main.tf` — 실행 역할과 태스크 역할의 차이. 정책 JSON 읽는 법.
5. `modules/registry/main.tf`, `modules/logs/main.tf` — 짧다.
6. `modules/compute/main.tf` — `compose.yaml` 을 옆에 띄워 놓고 서비스 하나씩 대조하며 읽는다.
7. `modules/database/main.tf` → `modules/queue_redis/main.tf` — 비밀번호를 다루는 길, 큐로 쓸 때의 Redis 설정.
8. `envs/practice/tests/*.tftest.hcl` — 「무엇을 지키려 하는가」가 한국어 오류 문장으로 적혀 있다. `storage` → `network` → `iam` → `compute` 순.
9. 이 글의 [처음 적용하는 차례](#처음-적용하는-차례-돌려-보지-않았다)와 [돈이 드는 자원](#적용하면-돈이-드는-자원).

Terraform 의 낱말 넷만 알면 읽힌다.

- `resource "종류" "이름" { … }` — AWS 에 만들 것 하나. 다른 곳에서 `종류.이름.속성` 으로 가리킨다.
- `variable` / `output` — 모듈이 받는 값과 내주는 값. 함수의 인자와 반환값이다.
- `module "이름" { source = … }` — 모듈을 불러 쓴다. 내준 값은 `module.이름.출력` 으로 받는다.
- `count = 조건 ? 1 : 0` — 조건이 참일 때만 만든다. 이렇게 만든 것은 목록이 되어 `[0]` 으로 가리킨다.

## 모듈마다: 무엇을 만들고 왜 이 설정인가

### network (남는 것)

VPC 하나, 서브넷 넷(공개 둘, 사설 둘, 가용 영역 둘에 나눠), 인터넷 게이트웨이, 라우팅 테이블 둘, 보안 그룹 다섯.

- **Aurora 와 Redis 는 늘 사설 서브넷**에 있다. 바깥으로 가는 길도, 바깥에서 오는 길도 없다.
- **보안 그룹**이 「누가 누구에게 말을 걸 수 있는가」를 정한다. 출처를 IP 가 아니라 보안 그룹으로 적었다: DB 와 Redis 에는 api·worker 의 보안 그룹이 붙은 것만 들어온다. worker 로 들어오는 규칙은 하나도 없다.

  ```
  인터넷 ─80→ [alb] ─3000→ [api] ─5432→ [database]
                             └────6379→ [redis]
                          [worker] ─5432→ [database],  ─6379→ [redis]
  ```

- **NAT 게이트웨이는 변수로 켠다(기본 끔).** 두 구성의 차이:

  | | `enable_nat_gateway = false` (기본) | `= true` |
  |---|---|---|
  | 컨테이너가 사는 곳 | 공개 서브넷 | 사설 서브넷 |
  | 컨테이너의 공인 IP | 붙는다(이미지를 받으러 나가야 해서) | 없다 |
  | 바깥으로 나가는 길 | 인터넷 게이트웨이로 직접 | NAT 게이트웨이를 거쳐 |
  | 바깥에서 컨테이너로 | 주소는 있지만 보안 그룹이 막는다(ALB 에서 오는 3000 만) | 주소 자체가 없다 |
  | 지키는 겹 | 보안 그룹 하나 | 보안 그룹 + 주소 없음 |
  | 드는 돈 | 태스크마다 공인 IPv4 요금 | NAT 의 시간 요금 + 지나간 데이터 요금 |
  | 코드에서 달라지는 것 | `aws_eip.nat`, `aws_nat_gateway.main`, `aws_route.private_nat` 가 0 | 그 셋이 1. 출력 `task_subnet_ids`, `task_assign_public_ip` 가 바뀐다 |

  NAT 를 켠 구성에서 NAT 는 하나(가용 영역 a)만 둔다. 그 영역이 죽으면 다른 영역의 컨테이너도 바깥으로 못 나간다.

### storage (남는 것)

업로드용 버킷 하나와 그 설정: 공개 차단 넷, ACL 끄기, 저장 암호화(SSE-S3), http 요청 거절(버킷 정책), CORS(화면 주소를 줄 때만), 올리다 만 조각 정리(7일).

- 서명된 주소로 올리는 흐름이라 버킷을 공개할 일이 없다. 서명된 요청은 「서명한 역할의 권한」으로 들어온다.
- 버킷 이름은 앞머리만 정하고 뒤는 AWS 가 붙인다(이름이 전 세계에서 하나뿐이어야 해서).
- 정적 프론트용 버킷은 자리만 있다(`enable_frontend_bucket`, 기본 끔). CloudFront 는 적지 않았다.

### registry (남는 것)

ECR 저장소 둘(`server`, `parser`). 태그 덮어쓰기 금지(`IMMUTABLE`), 올릴 때 취약점 훑기, 정리 규칙(태그 없는 것은 7일 뒤, 그 밖에는 최근 20개만).

이미지를 만들고 올리는 일은 Terraform 이 하지 않는다.

### iam (남는 것)

역할 셋. 컨테이너에 키를 넣는 대신 역할을 입힌다.

| 역할 | 누가 쓰는가 | 할 수 있는 것 |
|---|---|---|
| 실행 역할 | ECS(컨테이너를 띄우는 쪽) | 우리 저장소 둘에서 이미지 받기, 우리 로그 그룹 넷에 쓰기, 접속 주소 비밀 둘 읽기 |
| api 태스크 역할 | api 컨테이너 안의 코드 | 업로드 버킷에 `PutObject`·`GetObject`, 버킷에 `ListBucket` |
| worker 태스크 역할 | worker·파서 컨테이너 안의 코드 | 업로드 버킷에서 `GetObject`, 실행 파일 앞머리 `runs/` 에 `PutObject` |

- AWS 의 관리형 정책을 붙이지 않고 직접 적었다. 관리형 정책은 모든 저장소·모든 로그 그룹을 허용한다.
- `Resource: "*"` 는 한 군데뿐이다(ECR 로그인. 그 동작은 자원을 고를 수 없다).
- api 에 `ListBucket` 이 있는 까닭: 없으면 「없는 파일」을 물었을 때 404 가 아니라 403 이 온다. 앱은 404 를 「아직 안 올라왔다」로 읽는다.

### logs (남는 것)

로그 그룹 넷(api, worker, parser, migrate), 보관 30일. 미리 만들어 두면 보관 기간을 정할 수 있고, 실행 역할에 「그룹을 만드는 권한」을 줄 필요가 없다.

### queue_redis (스택에 따라 버린다)

ElastiCache 복제 그룹(노드 하나, `cache.t4g.micro`), 서브넷 그룹, 파라미터 그룹.

- **`maxmemory-policy = noeviction`** 이 핵심이다. ElastiCache 의 기본값은 `volatile-lru`(메모리가 차면 키를 지운다)라서, 큐로 쓰면 작업이 몰래 사라질 수 있다.
- compose 와 다른 점: ElastiCache 는 디스크에 남기는 기능(AOF)을 지원하지 않는다. 노드가 하나면 그 노드가 교체될 때 큐의 작업이 사라진다. 남기려면 `node_count = 2`(요금 두 배).
- 저장·전송 암호화를 켰다. 그래서 주소가 `rediss://`(s 가 둘)다.
- 엔진은 변수다(기본 `redis` 7.1). `valkey` 로 바꾸면 더 싸다. 앱의 큐 라이브러리가 Valkey 에서 도는지는 확인하지 않았다.
- ElastiCache 「Serverless」 형은 쓰지 못한다. 메모리 정책을 바꿀 수 없다.

### database (스택에 따라 달라진다)

Aurora PostgreSQL 클러스터와 인스턴스 하나(Serverless v2, 0.5~2 ACU), 서브넷 그룹, 접속 주소를 담을 비밀 그릇 둘.

**비밀번호가 코드와 상태 파일에 평문으로 남지 않게 한 길:**

1. 주 사용자(관리자)의 비밀번호는 우리가 정하지 않는다. `manage_master_user_password = true` 로 AWS 가 만들어 Secrets Manager 에 넣고 주기적으로 바꾼다. Terraform 은 그 비밀의 위치(ARN)만 안다.
2. 앱이 쓰는 접속 주소(`DATABASE_URL`, `MIGRATE_DATABASE_URL`)는 비밀번호가 든 한 줄이다. Terraform 은 **빈 비밀 그릇만** 만들고, 값은 사람이 한 번 넣는다. 값이 Terraform 을 지나가지 않으므로 상태 파일에 없다.
3. 고르지 않은 길: 변수로 비밀번호를 받아 `master_password` 에 넣기. 값이 상태 파일에 평문으로 남는다.

그 밖에:

- 주 사용자는 앱도 마이그레이션도 쓰지 않는다. 사람이 처음에 역할 둘(주인 역할, 앱 역할 `esg_app`)을 만들 때만 쓴다. 관리형 비밀번호는 자동으로 바뀌므로 그것을 접속 주소에 옮겨 적으면 며칠 뒤 깨진다.
- 최소 크기를 0(쓰지 않을 때 멈춤)이 아니라 0.5 로 둔 까닭: api 의 `/readyz` 가 DB 를 계속 두드리므로 api 가 떠 있는 동안에는 멈추지 않는다.
- Data API 를 켰다(`enable_data_api`). 사설 서브넷의 DB 에 처음 역할을 만들 때 콘솔의 쿼리 편집기를 쓰려는 것이다.
- 연습용 기본값: 지울 때 마지막 스냅샷을 남기지 않고, 삭제 보호가 꺼져 있다. 운영에서는 둘 다 반대로 둔다.

### compute (스택에 따라 가장 많이 달라진다)

ECS 클러스터, ALB(+ 대상 그룹, 443 HTTPS 리스너, 443 으로 돌려보내기만 하는 80 리스너), 태스크 정의 셋(api, worker, migrate), 서비스 둘(api, worker).

**지금은 막혀 있다.** 이 모듈은 TS 서버(`node dist/api.js`) 기준이라 api-py·worker-py 로 다시 쓸 때까지 켜지 않는다(`sid:MARC-ISSUE-108`). 그래서 `enable_compute` 의 기본은 `false` 이고, 켜더라도 두 변수가 맞지 않으면 계획(`plan`) 단계에서 실패한다: `alb_ingress_cidr` 는 ALB 에 들어올 주소 범위로, 기본은 아무도 들이지 않는 자리표시(`192.0.2.1/32`)이며 compute 를 켠 채로 `/0`(`0.0.0.0/0`·`::/0`)이면 막힌다. `alb_certificate_arn` 은 443 HTTPS 리스너에 붙일 ACM 인증서의 ARN 으로, compute 를 켜면 필수다(없으면 변수 검사와 리스너의 precondition 이 막는다). 80 은 443 으로 돌려보내기만 하고, compute 를 켜면 `network` 의 `enable_https_ingress` 도 같이 켜져 ALB 보안 그룹에 443 이 열린다.

| compose | 여기서는 |
|---|---|
| `api` | 서비스 `api`. ALB 대상 그룹에 붙는다. 대상 확인 `/readyz`, 컨테이너 상태 확인 `/healthz` |
| `worker` + `parser` | 서비스 `worker` 의 한 태스크에 컨테이너 둘. worker 가 파서의 `HEALTHY` 를 기다린다(`dependsOn`). 로드밸런서에 붙지 않는다 |
| `PARSER_URL=http://parser:8000` | `http://localhost:8000`. 한 태스크의 컨테이너는 네트워크를 같이 쓴다 |
| `stop_grace_period` 15s / 45s | `stopTimeout` 15 / 45. Fargate 의 상한은 120초다(아래 「근거」) |
| `migrate` | 태스크 정의만. 서비스가 아니다. 배포 때 `aws ecs run-task` 로 한 번 돌린다 |
| `ports:` (parser 는 없음) | 파서에 포트 매핑이 없고, worker 의 보안 그룹에 들어오는 규칙이 없다 |

- HTTPS 리스너의 TLS 정책은 `ELBSecurityPolicy-TLS13-1-2-2021-06` 하나로 고정했다. 도메인과 인증서(ACM)가 있어야 켤 수 있다.
- 이미지의 CPU 종류는 변수다(기본 `ARM64`. 애플 실리콘 맥에서 그냥 빌드한 이미지에 맞는다).

### 근거 (공식 문서, 2026-10-05 확인)

위 설명에서 사실로 적은 것들의 출처다.

| 적은 것 | 출처 |
|---|---|
| Fargate 의 `stopTimeout` 은 기본 30초, 상한 120초. `dependsOn` 의 `HEALTHY` 는 상대에 상태 확인이 있어야 한다 | <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html> |
| 한 태스크의 컨테이너는 `localhost` 로 만난다. 이미지를 받으려면 공인 IP, NAT, VPC 엔드포인트 가운데 하나가 있어야 한다 | <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-networking.html> |
| `awsvpc` 에서 대상 그룹의 대상 종류는 `ip` | <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/alb.html> |
| 비밀을 환경 변수로 넣는 것은 실행 역할의 권한으로 한다 | <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html> |
| ElastiCache 의 `maxmemory-policy` 기본값은 `volatile-lru`, 바꿀 수 있다 | <https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/ParameterGroups.Engine.html> |
| ElastiCache 는 AOF 를 지원하지 않는다 | <https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/VersionManagementConsiderations.html> |
| ElastiCache Serverless 는 설정을 바꿀 수 없다(`volatile-lru` 고정) | <https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/RedisConfiguration.html> |
| Aurora 의 관리형 주 사용자 비밀번호, 자동 교체(기본 7일) | <https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/rds-secrets-manager.html>, 공급자 문서 `rds_cluster` |
| Serverless v2 는 `storage_encrypted` 를 적지 않으면 꺼진다. 크기 범위 0~256 ACU | <https://registry.terraform.io/providers/hashicorp/aws/6.67.0/docs/resources/rds_cluster> |
| Data API 는 서울에서 Aurora PostgreSQL 17.4 이상 | <https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Concepts.Aurora_Fea_Regions_DB-eng.Feature.Data_API.html> |
| 새 버킷은 공개 차단이 켜지고 ACL 이 꺼진 채로 만들어진다 | <https://docs.aws.amazon.com/AmazonS3/latest/userguide/about-object-ownership.html> |
| 보안 그룹 규칙은 규칙 하나를 자원 하나로 적는 것이 권장이다 | <https://registry.terraform.io/providers/hashicorp/aws/6.67.0/docs/resources/vpc_security_group_ingress_rule> |

「1 ACU 는 메모리 약 2GB」(`modules/database/variables.tf`)는 출처를 다시 확인하지 않은 값이다.

## compose 의 환경 변수가 어디서 오는가

컨테이너가 받는 이름은 TS 서버 기준의 `compose.yaml` 이름 그대로다. 값만 바뀐다. compose 와 이름을 대조하던 테스트는 compose 의 TS 서비스가 사라져 걷었다 — api-py 로 다시 쓸 때 다시 세운다(`sid:MARC-ISSUE-108`).

| 이름 | 받는 것 | AWS 에서의 값이 오는 곳 |
|---|---|---|
| `DATABASE_URL` | api, worker | 비밀 `…/database-url` (`module.database` 의 출력 `database_url_secret_arn`). 값은 손으로 넣는다. 태스크 정의의 `secrets` 로 주입 |
| `MIGRATE_DATABASE_URL` | migrate | 비밀 `…/migrate-database-url` (`migrate_database_url_secret_arn`). 값은 손으로 넣는다 |
| `REDIS_URL` | api, worker | `module.queue_redis` 의 출력 `redis_url` = `rediss://<복제 그룹의 primary_endpoint_address>:6379` |
| `S3_BUCKET` | api, worker | `module.storage` 의 출력 `uploads_bucket_name` (버킷의 `id`) |
| `S3_REGION` | api, worker | 변수 `region` |
| `S3_FORCE_PATH_STYLE` | api, worker | 고정값 `"false"` |
| `PARSER_URL` | api, worker | 고정값 `http://localhost:8000` |
| `PARSER_TIMEOUT_MS`, `QUEUE_ATTEMPTS`, `QUEUE_BACKOFF_MS`, `WORKER_LOCK_MS` | api, worker | `modules/compute` 의 변수(기본 30000, 3, 1000, 30000). `WORKER_LOCK_MS` 만 `.env.example` 의 값(5000)과 다르다: 그쪽은 로컬 실험이 빨리 끝나게 줄인 값이고, 여기는 앱의 기본값(30000)을 따랐다 |
| `PORT` | api | 고정값 `3000` |
| `SHUTDOWN_TIMEOUT_MS` | api / worker | 고정값 `10000` / `40000` (compose 와 같다) |

compose 에 있고 여기에 없는 것(일부러 뺐다):

| 이름 | 까닭 |
|---|---|
| `S3_ENDPOINT`, `S3_PUBLIC_ENDPOINT` | 진짜 S3 에서는 비운다. SDK 가 AWS 주소를 스스로 쓴다 |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | 키를 넣지 않는다. 태스크 역할이 권한을 준다 |

`.env.example` 의 나머지 이름(`COMPOSE_PROJECT_NAME`, `API_PORT`, `POSTGRES_PORT`, `STORAGE_PORT`, `POSTGRES_DB`, `POSTGRES_OWNER_USER`, `POSTGRES_OWNER_PASSWORD`, `APP_DB_PASSWORD`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`)은 compose 만 쓴다: 내 컴퓨터의 포트이거나, compose 가 접속 주소를 조립하는 재료이거나, 로컬 저장소의 키다. `.env.example` 에 이름이 새로 생기면 테스트가 멈춘다.

## 켜고 끄는 변수

`envs/practice/variables.tf` 에 있다. 내 값은 `terraform.tfvars` 에 적는다.

| 변수 | 기본 | 끄면(또는 켜면) |
|---|---|---|
| `enable_nat_gateway` | `false` | 켜면 컨테이너가 사설 서브넷으로 가고 NAT 게이트웨이가 하나 생긴다 |
| `enable_queue_redis` | `true` | 끄면 ElastiCache 자원이 0. 컨테이너에 `REDIS_URL` 을 넣지 않는다 |
| `enable_database` | `true` | 끄면 Aurora 와 비밀 그릇이 0. 컨테이너에 `DATABASE_URL` 을 넣지 않고, 실행 역할의 비밀 읽기 권한도 빠진다 |
| `enable_compute` | `false` | 끄면 ECS·ALB 자원이 0. api-py 로 다시 쓸 때까지 켜지 않는다(위 compute 절) |
| `enable_frontend_bucket` | `false` | 켜면 프론트용 버킷(자리만)이 생긴다 |
| `disposable` | `true` | `false` 면 파일이 든 버킷과 이미지가 든 저장소가 `destroy` 를 막는다 |

끄는 변수는 「계획이 깨지지 않는다」까지만 지킨다. Redis 나 DB 를 끈 채로 뜬 컨테이너는 필요한 환경 변수가 없어 기동 직후에 죽는다(앱이 그렇게 만들어져 있다). 끄는 것은 대신할 것을 넣기 위한 자리다.

### 스택이 바뀌면 어디를 고치는가

| 바뀌는 것 | 고치는 곳 |
|---|---|
| 큐가 SQS 로 | `enable_queue_redis = false`. SQS 큐(와 실패한 작업을 모으는 큐)를 적는 모듈을 새로 만들고, `iam` 의 api·worker 태스크 역할에 그 큐의 보내기·받기 권한을, `compute` 의 환경 변수에 큐 주소를 더한다. `network` 의 redis 보안 그룹은 남아도 해가 없다 |
| 서버 틀이 바뀐다(예: NestJS) | 인프라는 거의 그대로다. `compute` 의 실행 명령(`command`), 포트, 상태 확인 경로, 환경 변수 이름만 맞춘다 |
| worker 가 Lambda 로 | `compute` 에서 worker 서비스와 태스크 정의를 빼고 Lambda 를 적는 모듈을 만든다. 파서를 같은 태스크에 두는 꼴이 사라지므로 파서를 어디서 돌릴지부터 다시 정한다 |
| DB 가 Aurora 가 아니다(RDS PostgreSQL 등) | `database` 모듈을 바꾼다. 출력의 이름(`database_url_secret_arn` 등)을 지키면 나머지는 그대로다 |
| 프론트를 올린다 | `enable_frontend_bucket = true` 에 더해 CloudFront 를 적는다(없다) |

## 적용하면 돈이 드는 자원

**이 코드를 적용하면 그 순간부터 시간 단위로 요금이 나간다.** 연습이 끝나면 `terraform destroy` 로 지운다.

단가는 서울 리전(ap-northeast-2), 온디맨드, USD 다. 출처는 AWS 의 공개 요금 목록(Price List Bulk API)이고 2026-10-05 에 확인했다: `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/<서비스 코드>/current/ap-northeast-2/index.csv` (표의 「코드」 칸이 서비스 코드다). 요금은 바뀐다. 적용하기 전에 다시 확인한다.

| 자원 (모듈) | 단가 | 코드 | 기본 구성에서 한 달(730시간) 켜 두면 — **어림** |
|---|---|---|---|
| Aurora Serverless v2 (`database`) | ACU 시간당 0.20 | AmazonRDS | 최소 0.5 ACU × 730 = 73.0. 바쁘면 2 ACU 까지 늘어 최대 292.0 |
| Aurora 저장소 (`database`) | GB 월 0.12, 읽고 쓰기 100만 건당 0.24 | AmazonRDS | 쓰는 만큼 |
| ElastiCache `cache.t4g.micro` (`queue_redis`) | 노드 시간당 0.024 (Valkey 엔진이면 0.0192) | AmazonElastiCache | 17.5 |
| ALB (`compute`) | 시간당 0.0225 + LCU 시간당 0.008 | AWSELB | 16.4 + 쓰는 만큼 |
| Fargate api, 0.25 vCPU / 0.5 GB, ARM (`compute`) | vCPU 시간당 0.03725, GB 시간당 0.00409 | AmazonECS | 8.3 |
| Fargate worker, 0.5 vCPU / 1 GB, ARM (`compute`) | 같다 (x86 이면 0.04656 / 0.00511) | AmazonECS | 16.6 |
| 공인 IPv4 주소 (`network`·`compute`) | 주소 하나 시간당 0.005 | AmazonVPC | 태스크 둘 + ALB 가 쓰는 주소. 넷이라고 치면 14.6 (ALB 가 주소를 몇 개 쓰는지는 확인하지 않았다) |
| Secrets Manager 비밀 (`database`) | 비밀 하나 월 0.40 | AWSSecretsManager | 그릇 둘 0.8. AWS 가 만든 주 사용자 비밀에도 요금이 붙는지는 확인하지 않았다 |
| CloudWatch Logs (`logs`) | 수집 GB당 0.76 | AmazonCloudWatch | 쓰는 만큼 |
| ECR (`registry`) | 저장 GB 월 0.10 | AmazonECR | 쓰는 만큼 |
| S3 (`storage`) | 저장 GB 월 0.025 | AmazonS3 | 쓰는 만큼 |
| **NAT 게이트웨이** (`network`, 기본 끔) | 시간당 0.059 + 지나간 GB당 0.059 | AmazonEC2 | 켜면 43.1 + 쓰는 만큼 |

기본 구성(NAT 끔, 전부 켬)의 고정분 어림은 위 숫자를 더해 **한 달에 약 147 USD** 다(73.0 + 17.5 + 16.4 + 8.3 + 16.6 + 14.6 + 0.8). 쓰는 만큼 붙는 것(저장, 데이터 전송, 로그, LCU, DB 읽고 쓰기)과 세금은 빠져 있고, 무료 사용 한도는 넣지 않았다. 하루만 켜 두면 그 30분의 1 쯤이다. 숫자는 단가에 시간을 곱한 것일 뿐이고 실제 청구서와 맞춰 본 적이 없다.

요금이 없는 것: VPC, 서브넷, 라우팅 테이블, 인터넷 게이트웨이, 보안 그룹, IAM 역할, ECS 클러스터 자체.

## 계정 없이 확인한 것과 못 한 것

### 확인한 것 (`verify.sh`)

| 단계 | 무엇을 확인하는가 |
|---|---|
| `fmt -check` | 글의 모양 |
| `validate` | 문법, 그리고 자원의 인자 이름과 꼴이 공급자 6.67.0 의 정의와 맞는가 |
| `test` | 가짜 공급자 위에서 계획을 세워, Terraform 이 AWS 에 보내려는 값을 단언한다 |
| 보안 그룹 규칙의 수 | 보안 그룹마다 들어오는 규칙이 몇 개인가(코드를 글로 읽어 센다) |
| 모듈을 불러오는 곳 | 위아래 두 검사가 읽을 수 있는 곳(`../../modules/<이름>`)에서만 불러오는가 |
| 역할에 붙는 정책의 수 | 역할 셋에 정책 셋, 그 밖에 붙인 것이 없는가(같은 방법) |
| git | 상태 파일, 계획 파일, 플러그인, 내 변수 파일이 저장소에 들어가지 않았는가 |

테스트가 지키는 것:

- 업로드 버킷: 공개 차단 넷이 모두 켜짐, 암호화 있음, ACL 꺼짐, 버킷 정책에 Allow 가 없음
- DB 와 Redis 의 보안 그룹: 들어오는 규칙의 출처가 api·worker 의 보안 그룹이고 IP 범위가 아님, 포트 하나
- worker 태스크 역할: 동작과 자원에 `*` 가 없고 업로드 버킷에 한정. api 태스크 역할과 실행 역할도 같은 식으로
- worker 태스크 정의: 컨테이너 둘, worker 가 파서를 기다림, 포트 매핑 없음, `PARSER_URL` 이 `localhost`
- api 서비스만 대상 그룹에 붙음, 대상 확인 경로 `/readyz`, 컨테이너 상태 확인 `/healthz`
- NAT 를 끄면 0, 켜면 1. Redis·DB·compute 를 꺼도 계획이 선다
- 컨테이너 환경 변수의 이름이 `compose.yaml`, `.env.example` 과 맞음
- Redis 의 `noeviction`, Aurora 의 관리형 비밀번호와 저장 암호화
- ECR 의 태그 덮어쓰기 금지와 정리 규칙, 로그 그룹의 보관 기간

### 못 한 것 — 실제 적용에서만 드러난다

가짜 공급자는 AWS 에 묻지 않는다. 「테스트가 통과했다」는 「계획의 값이 기대와 같다」는 뜻이지 「만들어진다」는 뜻이 아니다.

1. **AWS 가 값을 받아 주는가.** 엔진 버전(Aurora `17.7`, Redis `7.1`)을 서울에서 고를 수 있는가, 가용 영역 이름(`ap-northeast-2a`, `2c`)이 그 계정에 있는가, 이름의 길이·글자 제한, Fargate 의 CPU·메모리 조합, 계정의 한도(VPC 수, 공인 IP 수 등).
2. **정책이 실제로 맞는가.** IAM 정책과 버킷 정책의 문법을 AWS 가 받는가, 권한이 모자라거나 남지 않는가(이미지 받기, 비밀 주입, S3 서명).
3. **만드는 순서와 걸리는 시간.** 자원 사이의 숨은 순서, Aurora·ElastiCache 가 만들어지는 데 걸리는 시간, `destroy` 가 깨끗이 끝나는가.
4. **컨테이너가 실제로 뜨는가.** 이미지를 받는가, 비밀이 환경 변수로 들어오는가, 상태 확인 명령이 통과하는가, worker 가 `localhost` 로 파서를 만나는가, ALB 가 `/readyz` 를 건강하다고 보는가.
5. **앱이 TLS 로 붙는가.** Redis 는 `rediss://` 다. Aurora PostgreSQL 17 도 TLS 만 받는 것이 기본이다. 앱의 DB·Redis 클라이언트가 그 주소와 AWS 의 인증서로 붙는지는 본 적이 없다.
6. **두 번째 `plan` 이 조용한가.** 적용 직후 다시 `plan` 했을 때 「바꿀 것 없음」이 나오는가. 태스크 정의의 JSON 은 AWS 가 기본값을 채워 돌려주므로 차이가 계속 뜰 수 있다.
7. **Aurora 의 관리형 비밀에 무엇이 들어 있는가.** 키가 `username`, `password` 뿐인지 공식 문서에서 확인하지 못했다.
8. **요금.** 위 표는 단가의 곱셈이다.
9. **테스트가 못 보는 꼴.** 테스트는 이름을 아는 자원의 값만 본다. 자원을 새로 더해 내는 구멍 가운데 잡는 것은 둘뿐이다: 보안 그룹의 들어오는 규칙(5단계)과 역할에 붙는 정책(5-2단계)의 수. 둘 다 `infra/terraform` 아래의 `*.tf` 를 글로 읽어 세는 것이라, 그래서 모듈을 `../../modules/<이름>` 밖에서 불러오면 멈추게 했다(5-1단계). 글자를 세는 검사라, 여기서 생각하지 못한 적는 법이 더 있을 수 있다. 그리고 `envs/practice/main.tf` 에서 모듈에 **엉뚱한 값을 넘기는 것**(DB 에 다른 보안 그룹을, worker 에 api 의 역할을, DB 를 공개 서브넷에)은 잡지 못한다. 모듈 하나씩은 단언하지만 엮음은 「계획이 선다」까지만 본다.

## 처음 적용하는 차례 (돌려 보지 않았다)

**아래는 한 번도 돌려 보지 않은 차례다.** 문서를 보고 적은 것이라 명령이나 순서가 틀렸을 수 있다. 막히면 그 자리의 오류를 읽고 고친다. 처음부터 끝까지 한 시간쯤 켜 두는 것으로 잡고, 끝나면 반드시 9번(지우기)까지 간다.

### 0. 준비

- AWS 계정. 누구 명의의 계정에 만들지, 누가 요금을 내는지가 먼저 정해져야 한다.
- 그 계정에서 자원을 만들 권한이 있는 신분(IAM Identity Center 의 사용자, 또는 IAM 사용자·역할). 연습 계정이면 `AdministratorAccess` 로 시작하는 것이 덜 막힌다. 남의 계정이면 필요한 권한의 목록을 받아야 한다(이 코드가 만지는 서비스: VPC·EC2, S3, ECR, IAM, CloudWatch Logs, ElastiCache, RDS, Secrets Manager, ECS, Elastic Load Balancing).
- 요금 알림. 콘솔의 Billing → Budgets 에서 월 예산과 알림 메일을 먼저 걸어 둔다.
- 도구: Terraform(`bin/tf` 가 아니라 직접 깐 것), AWS CLI v2, Docker, `jq`.

Terraform 을 직접 까는 법(공식 안내: <https://developer.hashicorp.com/terraform/install>). 버전은 1.16.5 이상 1.17 미만이어야 한다(`versions.tf`).

```sh
# macOS (Homebrew)
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
terraform version
```

Homebrew 가 주는 버전이 맞지 않으면 <https://releases.hashicorp.com/terraform/1.16.5/> 에서 내 컴퓨터에 맞는 zip 과 `terraform_1.16.5_SHA256SUMS` 를 받아 `shasum -a 256 -c` 로 지문을 확인한 뒤 풀어 쓴다.

### 1. 자격 증명을 둔다

키를 저장소, `terraform.tfvars`, `.env` 에 적지 않는다. Terraform 과 AWS CLI 는 같은 곳(`~/.aws` 의 프로필이나 환경 변수)에서 자격 증명을 스스로 찾는다.

```sh
aws configure sso --profile esg-practice     # IAM Identity Center 를 쓸 때(권한다). 묻는 대로 답한다
aws sso login --profile esg-practice
# 또는: aws configure --profile esg-practice  (IAM 사용자의 액세스 키. 오래 남는 키라 덜 권한다)

export AWS_PROFILE=esg-practice
export AWS_REGION=ap-northeast-2
aws sts get-caller-identity                  # 내가 누구로 들어와 있는지. 계정 번호가 맞는지 본다
```

`AWS_PROFILE` 이 걸린 셸에서는 `verify.sh` 가 멈춘다(자격 증명 없이 도는 확인이라서). 확인은 다른 셸에서 돌린다.

### 2. 먼저 compute 를 끈 채로 적용한다

이미지와 비밀이 아직 없으므로 컨테이너를 띄워도 뜨지 못한다. 그릇부터 만든다.

```sh
cd infra/terraform/envs/practice
cp terraform.tfvars.example terraform.tfvars     # enable_compute = false 인지 확인

terraform init                                   # 공급자를 받는다. 상태는 이 폴더의 terraform.tfstate 에 생긴다
terraform plan -out=tfplan                       # 무엇을 만들지 읽는다. 「N to add, 0 to change, 0 to destroy」
terraform apply tfplan                           # 만든다. Aurora 와 ElastiCache 때문에 10~20분쯤 걸릴 수 있다(어림)
terraform output                                 # 만들어진 것의 이름과 주소
```

`plan` 이 보여 주는 목록을 꼭 읽는다. 여기 적은 자원이 하나씩 보인다. 가용 영역이나 엔진 버전을 고를 수 없다는 오류가 나면 `terraform.tfvars` 에서(엔진 버전은 `main.tf` 의 모듈 호출에 `engine_version` 을 더해) 고친다.

### 3. 이미지를 만들어 올린다

저장소 루트에서 한다. 태그는 커밋 해시로 한다(같은 태그를 덮어쓸 수 없다).

```sh
cd "$(git rev-parse --show-toplevel)"
tf() { terraform -chdir=infra/terraform/envs/practice "$@"; }    # 저장소 루트에서 부르는 줄임말(이 셸에서만)
TAG=$(git rev-parse --short HEAD)
SERVER=$(tf output -raw server_repository_url)
PARSER=$(tf output -raw parser_repository_url)

aws ecr get-login-password | docker login --username AWS --password-stdin "${SERVER%%/*}"

docker build -f docker/server.Dockerfile -t "$SERVER:$TAG" .
docker build -f docker/parser.Dockerfile -t "$PARSER:$TAG" .
docker push "$SERVER:$TAG"
docker push "$PARSER:$TAG"
```

애플 실리콘 맥에서 그냥 빌드하면 ARM64 이미지다(`cpu_architecture = "ARM64"` 와 맞는다).

### 4. DB 에 역할을 만들고 접속 주소 비밀을 채운다

Aurora 는 사설 서브넷에 있어 내 컴퓨터에서 `psql` 로 닿지 않는다. 콘솔의 RDS → 쿼리 편집기(Query Editor)를 쓴다: 클러스터를 고르고, 「Secrets Manager ARN 으로 연결」에 `tf output -raw database_master_user_secret_arn` 의 값을, 데이터베이스에 `esg` 를 넣는다. 그리고 역할 둘을 만든다(비밀번호는 내가 지은 긴 무작위 값 둘).

```sql
-- 주인 역할: 테이블을 만들고 바꾼다. 마이그레이션만 쓴다.
CREATE ROLE esg_owner LOGIN PASSWORD '<주인 비밀번호>' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
GRANT ALL ON DATABASE esg TO esg_owner;
GRANT ALL ON SCHEMA public TO esg_owner;

-- 앱 역할: api 와 worker 가 쓴다. RLS 를 우회하지 못한다. (docker/postgres-init.sh 가 로컬에서 하는 일과 같다)
CREATE ROLE esg_app LOGIN PASSWORD '<앱 비밀번호>' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
```

주인 역할에 줄 권한이 이것으로 충분한지는 마이그레이션을 돌려 봐야 안다(로컬에서는 주인이 superuser 였다).

비밀 그릇 둘에 접속 주소를 넣는다. 비밀번호가 셸 기록에 남지 않게 `read -s` 로 받는다. 비밀번호에 `@ : / ?` 같은 글자가 있으면 주소가 깨지므로 영문자와 숫자로만 짓는다.

```sh
HOST=$(tf output -raw database_endpoint)        # 3번에서 만든 tf 줄임말을 쓴다(같은 셸, 저장소 루트)

read -s APP_PW   && aws secretsmanager put-secret-value \
  --secret-id "$(tf output -raw database_url_secret_arn)" \
  --secret-string "postgres://esg_app:${APP_PW}@${HOST}:5432/esg?sslmode=require"

read -s OWNER_PW && aws secretsmanager put-secret-value \
  --secret-id "$(tf output -raw migrate_database_url_secret_arn)" \
  --secret-string "postgres://esg_owner:${OWNER_PW}@${HOST}:5432/esg?sslmode=require"
unset APP_PW OWNER_PW
```

주소 끝의 `?sslmode=require` 는 빼면 안 된다. Aurora PostgreSQL 17 은 암호화된 연결(TLS)만 받는 것이 기본이다(`rds.force_ssl` 의 기본값이 1. <https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.Security.html>, 2026-10-05 확인).

**여기가 처음 막힐 가능성이 가장 큰 자리다.** 앱의 DB 클라이언트(`pg`)가 이 주소로 붙는지는 본 적이 없다. 「인증서를 확인할 수 없다」는 오류가 나면 앱이 AWS 의 인증서 묶음(RDS CA)을 믿게 해야 한다. 그것은 앱 쪽의 일이다([앱 쪽에서 바뀌어야 할 것](#앱-쪽에서-바뀌어야-할-것) 2번). 연습에서 일단 붙여 보려면 `sslmode=no-verify`(암호화는 하지만 상대가 진짜 Aurora 인지 확인하지 않는다)가 통하는지 시험해 볼 수 있다. 통하는지는 확인하지 않았고, 운영에서 쓸 값은 아니다.

### 5. compute 를 켠다

`terraform.tfvars` 에서 넷을 함께 바꾼다. 둘째 둘이 없으면 `plan` 이 실패한다(compute 절의 「지금은 막혀 있다」).

```hcl
enable_compute      = true
image_tag           = "<3번의 TAG>"
alb_ingress_cidr    = "<내 IP>/32"                                   # /0 이면 실패
alb_certificate_arn = "arn:aws:acm:ap-northeast-2:<계정 번호>:certificate/<id>"  # ALB 와 같은 리전의 ACM 인증서
```

인증서는 ACM 에서 내 도메인(예: `api.example.com`)으로 미리 발급해 둔다(DNS 검증).

```sh
cd infra/terraform/envs/practice
terraform plan -out=tfplan
terraform apply tfplan
```

서비스가 만들어지면 ECS 가 곧바로 컨테이너를 띄우기 시작한다. 아직 테이블이 없으므로 6번을 바로 이어서 한다. 그 사이 api 가 건강해지지 못해 ECS 가 첫 배포를 실패로 닫을 수 있는지는 확인하지 못했다. 그렇게 되면 6번을 마친 뒤 `aws ecs update-service --cluster "$CLUSTER" --service api --force-new-deployment` 로 다시 띄운다(`worker` 도 같다).

### 6. 마이그레이션을 한 번 돌린다

```sh
CLUSTER=$(terraform output -raw ecs_cluster_name)
SUBNETS=$(terraform output -json task_subnet_ids | jq -r 'join(",")')
SG=$(terraform output -raw worker_security_group_id)

TASK=$(aws ecs run-task \
  --cluster "$CLUSTER" \
  --task-definition "$(terraform output -raw migrate_task_definition_arn)" \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SG],assignPublicIp=ENABLED}" \
  --query 'tasks[0].taskArn' --output text)

aws ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$TASK"
aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$TASK" \
  --query 'tasks[0].containers[0].exitCode'          # 0 이어야 한다
```

NAT 를 켠 구성이면 `assignPublicIp=DISABLED` 로 바꾼다. 실패하면 `aws logs tail /ecs/esg-app-practice/migrate` 로 기록을 본다.

### 7. 확인한다

```sh
ALB=$(terraform output -raw alb_dns_name)
# 인증서의 도메인이 ALB 를 가리키게 DNS 레코드(CNAME 또는 Route 53 별칭)를 손으로 만든 뒤:
DOMAIN=api.example.com               # 인증서를 발급한 도메인
curl -s "https://$DOMAIN/healthz"    # {"status":"ok"}
curl -s "https://$DOMAIN/readyz"     # DB, Redis, 저장소까지 닿으면 200
curl -sI "http://$DOMAIN/healthz"    # 301 → https (80 은 돌려보내기만 한다)

aws ecs describe-services --cluster "$CLUSTER" --services api worker \
  --query 'services[].{name:serviceName,running:runningCount,desired:desiredCount}'
aws logs tail /ecs/esg-app-practice/api --since 10m
aws logs tail /ecs/esg-app-practice/worker --since 10m
```

그다음 루트 README 의 「줄기를 손으로 따라가기」를 `API=https://$DOMAIN` 로 바꿔 해 본다. `https://$ALB` 로 부르면 인증서의 도메인과 이름이 달라 인증서 확인이 실패한다. `alb_ingress_cidr` 는 내 IP 로 좁힌 채로 둔다(/0 은 막혀 있다).

### 8. 다시 `plan` 해 본다

```sh
terraform plan       # 「No changes」 가 나오는지. 차이가 계속 뜨면 그 자리를 적어 둔다
```

### 9. 지운다

```sh
terraform destroy    # 지울 목록을 읽고 yes
rm -f tfplan         # 저장해 둔 계획 파일. 자원의 속성이 들어 있다(git 에는 안 들어가게 막혀 있다)
```

끝난 뒤 콘솔에서 남은 것이 없는지 본다. 꼬리표 `Project = esg-app` 으로 찾으면 빠르다(Resource Groups → Tag Editor). 특히 돈이 드는 것: RDS(클러스터, 스냅샷), ElastiCache, 로드밸런서, NAT 게이트웨이, 탄력적 IP, Secrets Manager. 하루 이틀 뒤 Billing 화면에서 요금이 더 붙지 않는지 한 번 더 본다.

`terraform.tfstate` 는 지우기 전까지 잃어버리면 안 된다. 그 파일이 없으면 Terraform 은 자기가 만든 것을 모르고, 손으로 하나씩 지워야 한다. 그리고 그 파일을 저장소에 넣지 않는다.

## 여기서 일부러 안 한 것

- **실제 적용.** 계정, 자격 증명, `plan`·`apply`·`destroy` 가 없었다. LocalStack 도 쓰지 않았다.
- **CI.** 올릴 때마다 `verify.sh` 를 돌리는 장치가 없다.
- **배포 파이프라인.** 이미지를 만들어 올리고, 마이그레이션을 돌리고, 서비스를 새 버전으로 갈아 끼우는 일을 손으로 한다.
- **도메인과 인증서.** 만들지 않는다(Route 53·ACM 자원 없음). HTTPS 리스너는 있지만 인증서 ARN(`alb_certificate_arn`)과 도메인의 DNS 레코드는 손으로 준비한다.
- **관측.** 경보, 현황판, 추적이 없다. 로그 그룹뿐이다.
- **자동 확장.** 태스크 수는 고정이다(`api_desired_count`, `worker_desired_count`).
- **여러 환경.** `practice` 하나뿐이다. dev/stg/prod 를 나누지 않았다.
- **상태 백엔드.** 로컬 파일이다. S3 로 옮길 때의 꼴은 `versions.tf` 에 주석으로만 있다.
- **프론트 배포.** 버킷 자리만 있고 CloudFront 가 없다.
- **사설 구성의 VPC 엔드포인트.** NAT 대신 엔드포인트(ECR, S3, Logs, Secrets Manager)로 나가는 구성은 적지 않았다.
- **KMS 키.** 암호화는 전부 AWS 가 관리하는 키로 한다.
- **비밀의 자동 교체.** 접속 주소 비밀 둘은 손으로 넣고 손으로 바꾼다.
- **멈춘 문서를 다시 넣는 주기 작업**(EventBridge 등), 백업 정책, WAF.
- **커뮤니티 묶음 모듈**(`terraform-aws-modules/*`). 자원이 하나씩 보이게 직접 적었다. `for_each` 와 `dynamic` 으로 줄이지 않고 풀어 썼다.

## 앱 쪽에서 바뀌어야 할 것

이 폴더는 앱 코드를 고치지 않았다. 올리려면 앱에서 봐야 할 것:

1. **DB 접속 주소를 통째로 받는 것.** 호스트·사용자·비밀번호를 따로 받으면 AWS 가 관리하는 비밀을 그대로 주입할 수 있고, 비밀번호 자동 교체도 쓸 수 있다. 지금은 주소 한 줄을 손으로 만들어 넣는다.
2. **DB 와 Redis 에 TLS 로 붙기.** `rediss://` 주소와 Aurora 의 TLS 를 클라이언트가 받는지, AWS 의 인증서를 믿는지.
3. **api 가 종료 때 로드밸런서를 기다리지 않는 것**(루트 README 의 「프로덕션에서 달라지는 것」). 대상 그룹의 등록 해제 대기(30초)와 맞춰야 한다.
4. **api 에도 `PARSER_URL` 이 필수인 것.** api 는 파서를 부르지 않는데 같은 설정 검사를 지나므로, 닿지 않는 주소(`localhost:8000`)를 받는다.
5. **`MAX_UPLOAD_BYTES`, `UPLOAD_URL_TTL_SECONDS`, `QUEUE_NAME`**(server)과 **`MAX_SOURCE_BYTES`, `FETCH_TIMEOUT_SECONDS`**(파서)는 코드가 읽지만 compose 에는 없다. 여기서도 넣지 않았다(코드의 기본값을 쓴다).
