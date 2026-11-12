# ─────────────────────────────────────────────────────────────────────────────
# iam: 컨테이너가 AWS 에서 "누구로서" 움직이는가. compose 의 AWS_ACCESS_KEY_ID 를 대신한다.
#
# 역할(role)은 키가 없는 신분이다. ECS 가 태스크를 띄울 때 역할을 잠깐 빌려 입히고(AssumeRole),
# 컨테이너 안의 AWS SDK 는 그 임시 자격을 스스로 찾아 쓴다. 그래서 키를 환경 변수로 넣지 않는다.
#
# 역할은 두 종류다. 헷갈리기 쉽다.
#   실행 역할(execution role) : 컨테이너를 "띄우는 쪽"(ECS)이 쓴다. 이미지 받기, 비밀 읽어 환경 변수로 넣기, 기록 쓰기.
#   태스크 역할(task role)    : 컨테이너 "안의 우리 코드"가 쓴다. S3 에 올리고 읽기.
# 앱 코드가 S3 를 못 읽으면 태스크 역할을, 태스크가 아예 못 뜨면(이미지·비밀) 실행 역할을 본다.
#
# 정책은 JSON 이다. jsonencode 로 Terraform 값을 JSON 글자로 바꿔 적는다(AWS 콘솔에서 보는 JSON 과 같은 꼴).
# ─────────────────────────────────────────────────────────────────────────────

# 지금 이 Terraform 을 돌리는 계정의 번호를 물어본다(자원을 만들지 않는 조회). 아래 신뢰 정책의 조건에 쓴다.
data "aws_caller_identity" "current" {}

locals {
  # 신뢰 정책: "누가 이 역할을 빌려 입을 수 있는가". 세 역할이 같은 것을 쓴다.
  # ecs-tasks.amazonaws.com = ECS 의 태스크. 조건은 "우리 계정의 ECS 태스크일 때만"으로 좁힌다
  # (다른 계정이 ECS 를 시켜 우리 역할을 입는 일을 막는다. AWS 문서는 이 조건을 태스크 역할에 권한다.
  #  실행 역할에도 같이 걸었는데, 실행 역할에서 문제없이 도는지는 적용해 봐야 안다. 막히면 실행 역할에서만 뺀다.)
  ecs_tasks_trust_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "ecs-tasks.amazonaws.com" }
        Action    = "sts:AssumeRole"
        Condition = {
          StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
        }
      },
    ]
  })

  # 비밀이 하나도 없으면 "비밀 읽기" 문장을 통째로 뺀다(자원 목록이 빈 문장은 IAM 이 받지 않는다).
  execution_secret_statements = length(var.secret_arns) == 0 ? [] : [
    {
      Sid      = "ReadSecretsForContainerEnv"
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = var.secret_arns
    },
  ]
}

# ── 실행 역할 ────────────────────────────────────────────────────────────────

resource "aws_iam_role" "execution" {
  name               = "${var.name}-task-execution"
  assume_role_policy = local.ecs_tasks_trust_policy
}

# AWS 가 만들어 둔 관리형 정책(AmazonECSTaskExecutionRolePolicy)을 붙이면 한 줄이지만, 그것은 모든 저장소·모든 로그 그룹을
# 허용한다. 여기서는 같은 동작을 우리 자원에만 허용하도록 직접 적는다.
resource "aws_iam_role_policy" "execution" {
  name = "pull-images-write-logs-read-secrets"
  role = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          # ECR 에 로그인하는 토큰을 받는다. 이 동작은 "어느 저장소"를 고를 수 없게 만들어져 있어 Resource 가 * 여야 한다.
          # (이 파일에서 * 를 통째로 쓰는 유일한 자리다.)
          Sid      = "EcrLogin"
          Effect   = "Allow"
          Action   = ["ecr:GetAuthorizationToken"]
          Resource = "*"
        },
        {
          # 이미지의 층을 받아 온다. 우리 저장소 둘에서만.
          Sid    = "PullImages"
          Effect = "Allow"
          Action = [
            "ecr:BatchCheckLayerAvailability",
            "ecr:GetDownloadUrlForLayer",
            "ecr:BatchGetImage",
          ]
          Resource = var.ecr_repository_arns
        },
        {
          # 컨테이너의 표준 출력을 로그 그룹에 쓴다. 그룹은 logs 모듈이 미리 만들었으므로 만드는 권한은 없다.
          # 뒤의 ":*" 는 "그 그룹 안의 모든 로그 스트림"이다(스트림 = 컨테이너 하나의 기록 줄기).
          Sid      = "WriteLogs"
          Effect   = "Allow"
          Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
          Resource = [for arn in var.log_group_arns : "${arn}:*"]
        },
      ],
      local.execution_secret_statements,
    )
  })
}

# ── api 의 태스크 역할 ───────────────────────────────────────────────────────

resource "aws_iam_role" "api_task" {
  name               = "${var.name}-api-task"
  assume_role_policy = local.ecs_tasks_trust_policy
}

# api 가 S3 에 하는 일: 올릴 주소에 서명(PutObject), 다 올라왔는지 확인(HeadObject), 내려받을 주소에 서명(GetObject).
# 서명된 주소는 "서명한 역할의 권한"으로 동작한다. 그래서 api 가 직접 올리지 않아도 PutObject 권한이 있어야 한다.
resource "aws_iam_role_policy" "api_task" {
  name = "uploads-bucket"
  role = aws_iam_role.api_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # 파일(객체)에 대한 동작. 자원은 "버킷/키" 꼴이라 뒤에 /* 가 붙는다. HeadObject 는 GetObject 권한으로 된다.
        Sid      = "ReadWriteObjects"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject"]
        Resource = ["${var.uploads_bucket_arn}/*"]
      },
      {
        # 버킷 자체에 대한 동작. 이것이 없으면 "없는 파일"을 물었을 때 404(없음)가 아니라 403(권한 없음)이 온다.
        # 앱은 404 를 "아직 안 올라왔다"로 읽으므로 필요하다.
        Sid      = "ListBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [var.uploads_bucket_arn]
      },
    ]
  })
}

# ── worker 의 태스크 역할 ────────────────────────────────────────────────────
# 한 태스크의 컨테이너들은 태스크 역할을 같이 쓴다. worker 와 파서가 같은 권한을 갖는다는 뜻이다.

resource "aws_iam_role" "worker_task" {
  name               = "${var.name}-worker-task"
  assume_role_policy = local.ecs_tasks_trust_policy
}

# worker 가 S3 에 하는 일: 파서가 원본을 읽을 주소에 서명(GetObject)과, 실행기의 실행 파일 쓰기(PutObject — runs/
# 앞머리 하나). 파서의 다른 쓰기(쪽 그림 등)가 생기면 그 앞머리를 문장으로 따로 더한다.
# ★ 동작에도 자원에도 통째의 * 를 쓰지 않는다. 테스트가 이것을 지킨다.
resource "aws_iam_role_policy" "worker_task" {
  name = "uploads-bucket"
  role = aws_iam_role.worker_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = ["${var.uploads_bucket_arn}/*"]
      },
      # 실행기가 단계 산출·출력 파일을 runs/<회사>/<실행>/… 에 쓴다(esgapi/runs/calc/keys.py) — 그 앞머리만
      {
        Sid      = "WriteRunFiles"
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = ["${var.uploads_bucket_arn}/runs/*"]
      },
    ]
  })
}
