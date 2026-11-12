# (다) worker 태스크 역할의 정책: 동작과 자원에 * 가 통째로 없고, 업로드 버킷에 한정된다.
#
# 정책은 JSON 글자다. jsondecode 로 풀어 문장(Statement)마다 본다.
# flatten([x]) 는 "글자 하나든 목록이든 목록으로 만든다"는 뜻이다(IAM 은 Action 과 Resource 에 둘 다 받는다).

mock_provider "aws" {
  override_during = plan
}

variables {
  name               = "test"
  uploads_bucket_arn = "arn:aws:s3:::test-uploads-bucket"
  # 000000000000 은 가짜 계정 번호다.
  ecr_repository_arns = [
    "arn:aws:ecr:ap-northeast-2:000000000000:repository/test/server",
    "arn:aws:ecr:ap-northeast-2:000000000000:repository/test/parser",
  ]
  log_group_arns = [
    "arn:aws:logs:ap-northeast-2:000000000000:log-group:/ecs/test/api",
  ]
  secret_arns = [
    "arn:aws:secretsmanager:ap-northeast-2:000000000000:secret:test/database-url-AbCdEf",
  ]
}

run "worker_task_role_has_no_wildcards_and_is_scoped_to_uploads_bucket" {
  command = plan

  module {
    source = "../../modules/iam"
  }

  # 역할마다 다른 가짜 id 를 준다(정책이 어느 역할에 붙었는지 가리려고).
  override_resource {
    target          = aws_iam_role.execution
    override_during = plan
    values          = { id = "test-task-execution" }
  }
  override_resource {
    target          = aws_iam_role.api_task
    override_during = plan
    values          = { id = "test-api-task" }
  }
  override_resource {
    target          = aws_iam_role.worker_task
    override_during = plan
    values          = { id = "test-worker-task" }
  }

  # 전부 Allow 이고, NotAction·NotResource 같은 "이것만 빼고 전부" 꼴이 없다.
  assert {
    condition = alltrue([
      for s in jsondecode(aws_iam_role_policy.worker_task.policy).Statement :
      s.Effect == "Allow" && !can(s.NotAction) && !can(s.NotResource) && can(s.Action) && can(s.Resource)
    ])
    error_message = "worker 태스크 역할의 정책에 Allow 가 아닌 문장이나 NotAction/NotResource 가 있다."
  }

  # 동작: "*" 도 "s3:*" 같은 "서비스의 전부"도 없다. 그리고 전부 s3 의 동작이다.
  assert {
    condition = alltrue(flatten([
      for s in jsondecode(aws_iam_role_policy.worker_task.policy).Statement : [
        for a in flatten([s.Action]) : !strcontains(a, "*") && startswith(a, "s3:")
      ]
    ]))
    error_message = "worker 태스크 역할의 동작에 * 가 있거나 s3 가 아닌 동작이 있다: ${aws_iam_role_policy.worker_task.policy}"
  }

  # 자원: "*" 가 통째로 없고, 전부 업로드 버킷 자신이거나 그 안의 파일이다.
  assert {
    condition = alltrue(flatten([
      for s in jsondecode(aws_iam_role_policy.worker_task.policy).Statement : [
        for r in flatten([s.Resource]) :
        r != "*" && (r == var.uploads_bucket_arn || startswith(r, "${var.uploads_bucket_arn}/"))
      ]
    ]))
    error_message = "worker 태스크 역할의 자원이 업로드 버킷 밖을 가리키거나 * 다: ${aws_iam_role_policy.worker_task.policy}"
  }

  # worker 가 하는 일은 읽기(GetObject)와 실행 파일 쓰기(PutObject)뿐이다. 지우기 등이 생기면 이 테스트를 같이 고친다
  # (일부러 걸리게 둔다).
  assert {
    condition = toset(flatten([
      for s in jsondecode(aws_iam_role_policy.worker_task.policy).Statement : flatten([s.Action])
    ])) == toset(["s3:GetObject", "s3:PutObject"])
    error_message = "worker 태스크 역할의 동작이 s3:GetObject·s3:PutObject 둘이 아니다. 넓혔다면 까닭과 함께 이 테스트를 고친다."
  }

  # 쓰는 문장이 있다(분모 — 아래 「runs/ 안뿐」이 빈 목록으로 참이 되지 않게).
  assert {
    condition = anytrue([
      for s in jsondecode(aws_iam_role_policy.worker_task.policy).Statement : contains(flatten([s.Action]), "s3:PutObject")
    ])
    error_message = "worker 태스크 역할에 s3:PutObject 문장이 없다."
  }

  # 쓰기(PutObject)는 실행 파일의 앞머리 runs/ 안뿐이다(esgapi/runs/calc/keys.py).
  assert {
    condition = alltrue(flatten([
      for s in jsondecode(aws_iam_role_policy.worker_task.policy).Statement : [
        for r in flatten([s.Resource]) : r == "${var.uploads_bucket_arn}/runs/*"
      ] if contains(flatten([s.Action]), "s3:PutObject")
    ]))
    error_message = "worker 태스크 역할의 PutObject 자원이 runs/ 앞머리 밖을 가리킨다: ${aws_iam_role_policy.worker_task.policy}"
  }

  # 읽기(GetObject)는 그대로 버킷 안의 파일 전부다(파서가 원본을 읽는다).
  assert {
    condition = alltrue(flatten([
      for s in jsondecode(aws_iam_role_policy.worker_task.policy).Statement : [
        for r in flatten([s.Resource]) : r == "${var.uploads_bucket_arn}/*"
      ] if contains(flatten([s.Action]), "s3:GetObject")
    ]))
    error_message = "worker 태스크 역할의 GetObject 자원이 버킷 안의 파일 전부가 아니다: ${aws_iam_role_policy.worker_task.policy}"
  }

  # 정책이 worker 의 역할에 붙어 있다.
  assert {
    condition     = aws_iam_role_policy.worker_task.role == "test-worker-task"
    error_message = "worker 의 정책이 다른 역할에 붙어 있다."
  }
}

run "api_task_role_is_scoped_to_uploads_bucket" {
  command = plan

  module {
    source = "../../modules/iam"
  }

  override_resource {
    target          = aws_iam_role.execution
    override_during = plan
    values          = { id = "test-task-execution" }
  }
  override_resource {
    target          = aws_iam_role.api_task
    override_during = plan
    values          = { id = "test-api-task" }
  }
  override_resource {
    target          = aws_iam_role.worker_task
    override_during = plan
    values          = { id = "test-worker-task" }
  }

  # 정책이 api 의 역할에 붙어 있다(worker 의 역할에 붙이면 worker 가 runs/ 밖에도 쓰고 버킷을 나열할 수 있다).
  assert {
    condition     = aws_iam_role_policy.api_task.role == "test-api-task"
    error_message = "api 의 정책이 다른 역할에 붙어 있다."
  }

  assert {
    condition = alltrue(flatten([
      for s in jsondecode(aws_iam_role_policy.api_task.policy).Statement : [
        for a in flatten([s.Action]) : !strcontains(a, "*") && startswith(a, "s3:")
      ]
    ]))
    error_message = "api 태스크 역할의 동작에 * 가 있거나 s3 가 아닌 동작이 있다."
  }

  assert {
    condition = alltrue(flatten([
      for s in jsondecode(aws_iam_role_policy.api_task.policy).Statement : [
        for r in flatten([s.Resource]) :
        r != "*" && (r == var.uploads_bucket_arn || startswith(r, "${var.uploads_bucket_arn}/"))
      ]
    ]))
    error_message = "api 태스크 역할의 자원이 업로드 버킷 밖을 가리키거나 * 다."
  }

  assert {
    condition = toset(flatten([
      for s in jsondecode(aws_iam_role_policy.api_task.policy).Statement : flatten([s.Action])
    ])) == toset(["s3:PutObject", "s3:GetObject", "s3:ListBucket"])
    error_message = "api 태스크 역할의 동작이 PutObject, GetObject, ListBucket 셋이 아니다. 넓혔다면 까닭과 함께 이 테스트를 고친다."
  }
}

run "roles_can_only_be_assumed_by_ecs_tasks_of_this_account" {
  command = plan

  module {
    source = "../../modules/iam"
  }

  override_data {
    target          = data.aws_caller_identity.current
    override_during = plan
    values          = { account_id = "000000000000" }
  }

  assert {
    condition = alltrue([
      for policy in [
        aws_iam_role.execution.assume_role_policy,
        aws_iam_role.api_task.assume_role_policy,
        aws_iam_role.worker_task.assume_role_policy,
      ] :
      length(jsondecode(policy).Statement) == 1 &&
      jsondecode(policy).Statement[0].Principal == { Service = "ecs-tasks.amazonaws.com" } &&
      jsondecode(policy).Statement[0].Action == "sts:AssumeRole" &&
      jsondecode(policy).Statement[0].Condition.StringEquals["aws:SourceAccount"] == "000000000000"
    ])
    error_message = "역할의 신뢰 정책이 「이 계정의 ECS 태스크만」이 아니다."
  }
}

run "execution_role_reads_only_listed_secrets_logs_and_repositories" {
  command = plan

  module {
    source = "../../modules/iam"
  }

  override_resource {
    target          = aws_iam_role.execution
    override_during = plan
    values          = { id = "test-task-execution" }
  }
  override_resource {
    target          = aws_iam_role.api_task
    override_during = plan
    values          = { id = "test-api-task" }
  }
  override_resource {
    target          = aws_iam_role.worker_task
    override_during = plan
    values          = { id = "test-worker-task" }
  }

  assert {
    condition     = aws_iam_role_policy.execution.role == "test-task-execution"
    error_message = "실행 역할의 정책이 다른 역할에 붙어 있다."
  }

  # Resource 가 "*" 인 문장은 ECR 로그인 하나뿐이다(그 동작은 자원을 고를 수 없다).
  assert {
    condition = [
      for s in jsondecode(aws_iam_role_policy.execution.policy).Statement : flatten([s.Action])
      if contains(flatten([s.Resource]), "*")
    ] == [["ecr:GetAuthorizationToken"]]
    error_message = "실행 역할에서 Resource 가 * 인 문장이 ECR 로그인 말고 더 있다."
  }

  assert {
    condition = alltrue(flatten([
      for s in jsondecode(aws_iam_role_policy.execution.policy).Statement : [
        for a in flatten([s.Action]) : !strcontains(a, "*")
      ]
    ]))
    error_message = "실행 역할의 동작에 * 가 있다."
  }

  # 비밀 읽기는 넘겨받은 비밀에만.
  assert {
    condition = toset(flatten([
      for s in jsondecode(aws_iam_role_policy.execution.policy).Statement : flatten([s.Resource])
      if contains(flatten([s.Action]), "secretsmanager:GetSecretValue")
    ])) == toset(var.secret_arns)
    error_message = "실행 역할의 비밀 읽기 권한이 넘겨받은 비밀 목록과 다르다."
  }

  # 이미지 받기는 넘겨받은 저장소에만, 기록 쓰기는 넘겨받은 로그 그룹(의 스트림)에만. 로그 그룹을 만드는 권한은 없다.
  assert {
    condition = toset(flatten([
      for s in jsondecode(aws_iam_role_policy.execution.policy).Statement : flatten([s.Resource])
      if contains(flatten([s.Action]), "ecr:BatchGetImage")
    ])) == toset(var.ecr_repository_arns)
    error_message = "실행 역할의 이미지 받기 권한이 넘겨받은 저장소 목록과 다르다."
  }

  assert {
    condition = toset(flatten([
      for s in jsondecode(aws_iam_role_policy.execution.policy).Statement : flatten([s.Resource])
      if contains(flatten([s.Action]), "logs:PutLogEvents")
    ])) == toset([for arn in var.log_group_arns : "${arn}:*"])
    error_message = "실행 역할의 기록 쓰기 권한이 넘겨받은 로그 그룹과 다르다."
  }

  assert {
    condition = !contains(flatten([
      for s in jsondecode(aws_iam_role_policy.execution.policy).Statement : flatten([s.Action])
    ]), "logs:CreateLogGroup")
    error_message = "실행 역할에 로그 그룹을 만드는 권한이 있다. 그룹은 logs 모듈이 만든다."
  }
}

run "execution_role_has_no_secret_statement_without_secrets" {
  command = plan

  module {
    source = "../../modules/iam"
  }

  variables {
    secret_arns = []
  }

  assert {
    condition = !contains(flatten([
      for s in jsondecode(aws_iam_role_policy.execution.policy).Statement : flatten([s.Action])
    ]), "secretsmanager:GetSecretValue")
    error_message = "비밀이 없는데 실행 역할에 비밀 읽기 문장이 남아 있다."
  }
}
