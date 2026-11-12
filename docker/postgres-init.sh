#!/bin/sh
# DB 를 처음 세울 때 한 번만 도는 스크립트 (postgres 이미지가 빈 데이터 폴더일 때 실행한다).
# 앱이 쓸 역할을 만든다. 프로덕션(Aurora)에서는 DB 를 만든 직후 사람이나 인프라 코드가 같은 일을 한 번 한다.
#
# 이 역할이 "RLS 를 우회하지 못하는 역할"인 까닭:
#   NOSUPERUSER  : superuser 는 RLS 를 무시한다
#   NOBYPASSRLS  : 이 속성이 있어도 RLS 를 무시한다
#   테이블의 주인이 아님 : 주인은 정책을 바꾸거나 끌 수 있다 (주인은 POSTGRES_USER 다)
#
# 값은 SQL 글자에 셸 변수로 끼우지 않는다: heredoc 은 <<'SQL'(셸 펼침 없음)이고 값은 psql -v 로 넘겨
# SQL 안에서 :'이름'(글자 값)·:"이름"(식별자)으로 쓴다 — 비번에 작은따옴표가 들어도 깨지지 않는다.
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -v app_pw="$APP_DB_PASSWORD" <<'SQL'
CREATE ROLE esg_app LOGIN PASSWORD :'app_pw' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
SQL

# Python API 뼈대(apps/api-py)의 DB. 같은 서버 안의 별도 데이터베이스다.
# 앱의 표와 Django 마이그레이션 기록표는 이 DB 에 있다(옛 TS 갈래·drizzle 은 걷혔다).
# 역할(esg_app, 주인)은 서버 단위라 새로 만들지 않는다. 앱 역할의 권한은 Django 마이그레이션이 준다(GRANT).
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v py_db="${POSTGRES_DB}_py" -v owner="$POSTGRES_USER" <<'SQL'
CREATE DATABASE :"py_db" OWNER :"owner";
SQL
