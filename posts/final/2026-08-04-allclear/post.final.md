# Apple 개발자 계정 이전 가이드: iOS App Transfer와 Sign in with Apple 사용자 마이그레이션

올클(AllClear)은 동아리 상세 정보와 모집공고, 활동 후기를 한곳에서 살펴보는 동아리 탐색 서비스다. 2026년 3월부터 4월까지 운영 중이던 올클 iOS 앱의 소유권을 기존 Apple Developer 계정에서 새 계정으로 이전했다. 나는 이 작업에서 iOS 서명 설정 전환과 Sign in with Apple 사용자 마이그레이션을 맡았다.

처음에는 App Store Connect에서 소유권을 넘기고 Xcode의 Team만 바꾸면 끝날 줄 알았다. Bundle ID가 유지되니 사용자에게도 별다른 변화가 없을 거라고 봤다. 하지만 이 앱은 Sign in with Apple을 사용하고 있었다.

Apple 로그인의 사용자 식별자 `sub`는 앱뿐 아니라 개발자 팀에도 종속된다. 팀이 바뀌면 같은 사용자가 로그인해도 새 팀 기준의 `sub`가 발급된다. 당시 서버는 이 값을 계정의 고유 식별자로 쓰고 있었기 때문에, 준비 없이 앱을 넘기면 기존 사용자가 신규 사용자로 인식될 수 있었다.

이 글은 계정 이전 전 준비부터 사용자 식별자 마이그레이션, iOS Team ID와 provisioning profile 전환, 실패한 접근과 로그, DB 배치 검증까지 실제 작업 순서대로 정리한 기록이다.

## 앱 이전만으로 끝나지 않았던 이유

문제는 두 갈래였다.

1. 기존 Apple 로그인 사용자를 새 팀의 사용자 식별자로 안전하게 옮겨야 했다.
2. iOS 프로젝트의 서명 설정과 capability를 새 개발자 계정에 맞게 바꿔야 했다.

처음 세운 계획은 단순했다. 기존 계정에서 앱 이전을 요청하고 새 계정에서 수락한 뒤, Xcode의 Team ID와 provisioning profile을 바꿔 새 빌드를 배포하는 순서였다.

Sign in with Apple을 사용하지 않는 앱이라면 큰 틀에서 맞는 순서다. 하지만 Apple 로그인을 쓴다면 가장 중요한 작업은 이전 요청보다 앞에 온다. 기존 사용자의 `old_sub`를 새 팀과 연결할 중간 식별자로 바꾸지 않은 채 앱부터 넘기면, 기존 사용자와 새 `sub`를 이어 줄 근거를 잃을 위험이 있기 때문이다.

실제 흐름은 다음과 같았다.

```text
기존 팀의 old_sub
  -> 이전용 transfer_identifier 생성
  -> App Store Connect에서 앱 이전
  -> 새 팀의 new_sub로 교환
  -> DB의 로그인 식별자 갱신
```

`transfer_identifier`는 임의로 만드는 값이 아니다. 기존 팀의 인증 정보로 Apple migration API를 호출하면 Apple이 사용자별로 반환하는, 이전 절차에만 쓰이는 연결 값이다.

## 이전 전에 확인한 범위

가장 먼저 Bundle ID보다 이 앱이 쓰는 Apple capability를 살폈다.

- Sign in with Apple
- App Groups
- Push Notifications
- Keychain Sharing 사용 여부
- App ID와 Services ID의 연결 관계
- 각 build configuration이 사용하는 Bundle ID
- 기존 Team ID와 새 Team ID

Sign in with Apple 앱이 그룹으로 묶여 있다면 이전 전에 그룹을 해제해야 한다. App Groups는 앱과 함께 자동으로 이전되지 않는다. Keychain Sharing은 앱 업데이트 때 새 팀 기준으로 다시 구성해야 하는 경우가 있다. “Bundle ID가 유지된다”와 “기존 서명 설정을 그대로 쓸 수 있다”는 전혀 다른 이야기였다.

이전용 API 호출에는 `.p8` 파일만 필요한 게 아니다. 발신 팀과 수신 팀의 정보를 나눠 준비했다.

| 구분 | 준비한 정보 |
|---|---|
| 기존 팀 | Team ID, Sign in with Apple Key ID, `.p8`, 앱 grouping 상태 |
| 새 팀 | Team ID, Sign in with Apple Key ID, `.p8` |
| 앱 | production Bundle ID, App ID·Services ID 관계, 사용 중인 capability |
| App Store Connect | 수신 계정의 Account Holder 이메일 |

기존 개발사에서 인증 정보를 받아야 한다면 raw `.p8`를 직접 전달받기보다 기존 개발사가 사용자별 `transfer_identifier`를 추출해 CSV로 주는 편이 안전하다. 직접 키를 받아 실행하는 경우에도 `.p8`는 저장소에 넣지 않고 로컬의 제한된 경로나 secret manager에서만 읽어야 한다.

## Apple 로그인 사용자 inventory 만들기

서버는 Apple 사용자의 `sub`를 계정 테이블의 사용자명 필드에 저장하고 있었다. 우선 이전 대상 전체를 CSV로 백업했다.

초기 쿼리는 계정과 사용자 테이블을 모두 `INNER JOIN`했다.

```sql
SELECT
  a.id AS account_id,
  a.username AS old_sub,
  au.user_id,
  u.email
FROM account a
JOIN account_user au ON au.account_id = a.id
JOIN "user" u ON u.id = au.user_id
WHERE a.type = 'apple';
```

그런데 Apple 계정 행은 있는데 결과에서 빠지는 경우가 생겼다. 조회 컬럼이 아니라 `JOIN`이 원인이었다. 일부 행이 연결 상태나 탈퇴 상태 때문에 중간 테이블에서 탈락하고 있었다.

마이그레이션 inventory는 정상 사용자만 조회하는 목록이 아니다. 이전 대상 전체를 빠짐없이 확인해야 한다. 그래서 연결 테이블을 `LEFT JOIN`으로 바꾸고 연결이 끊긴 행도 결과에 남겼다.

추출 뒤에는 다음 항목을 확인했다.

- Apple 계정 총수와 활성·탈퇴 계정 합계가 일치하는가
- `old_sub`가 중복되지 않는가
- 계정 연결이 누락된 행이 있는가
- CSV 백업의 행 수와 DB 조회 결과가 일치하는가

정확한 내부 계정 수는 공개하지 않는다. 중복된 `old_sub`는 없었다. 이 과정을 거쳐 이전 대상을 확정했다.

## 재실행할 수 있는 마이그레이션 상태 만들기

기존 `account` 테이블부터 고치지 않았다. 사용자별 진행 상태를 추적할 별도 테이블을 먼저 만들었다.

배치 전에 `account.username`의 길이도 넉넉하게 늘렸다. 기존 `sub`와 새 `sub`의 길이가 늘 같다고 가정하면 전환 중 저장 단계에서 실패할 수 있어서다.

```text
apple_account_migration
  - account_id
  - app_bundle_id
  - source_team_id
  - target_team_id
  - old_sub
  - transfer_identifier
  - new_sub
  - status
  - last_error
  - transfer_identifier_collected_at
  - new_sub_collected_at
  - migrated_at
```

상태는 다음처럼 나눴다.

```text
pending
transfer_identifier_collected
new_sub_collected
migrated
failed
```

`account_id`, `old_sub`, `transfer_identifier`, `new_sub`에는 unique index를 걸었다. 배치를 다시 실행해도 같은 사용자를 중복 처리하거나 서로 다른 계정에 같은 식별자를 넣지 못하게 하기 위해서였다.

마이그레이션 대상은 기존 Apple 계정에서 채웠다.

```sql
INSERT INTO apple_account_migration (
  account_id,
  app_bundle_id,
  source_team_id,
  target_team_id,
  old_sub,
  status
)
SELECT
  id,
  '<APP_BUNDLE_ID>',
  '<SOURCE_TEAM_ID>',
  '<TARGET_TEAM_ID>',
  username,
  'pending'
FROM account
WHERE type = 'apple';
```

## 이전 전 `old_sub`를 `transfer_identifier`로 바꾸기

기존 팀의 Team ID, Sign in with Apple Key ID, `.p8` private key로 client secret JWT를 만들었다. 이어 Apple 토큰 API에서 `user.migration` scope의 access token을 발급받았다.

```text
POST https://appleid.apple.com/auth/token

grant_type=client_credentials
scope=user.migration
client_id=<APP_ID_OR_SERVICES_ID>
client_secret=<SOURCE_TEAM_CLIENT_SECRET>
```

발급받은 access token으로 사용자마다 `userMigrationInfo` API를 호출했다.

```text
POST https://appleid.apple.com/auth/usermigrationinfo

sub=<OLD_SUB>
target=<TARGET_TEAM_ID>
client_id=<APP_ID_OR_SERVICES_ID>
client_secret=<SOURCE_TEAM_CLIENT_SECRET>
```

응답의 `transfer_sub`를 `apple_account_migration.transfer_identifier`에 저장하고 상태를 `transfer_identifier_collected`로 바꿨다.

배치는 로컬에서 실행하되 Telepresence로 운영 DB에 연결했다. 앱 서버에 일회성 migration credential을 상시 배포하지 않으려는 선택이었다. 실행 전에 현재 database와 schema, 대상 행 수를 확인했고 스크립트와 키 파일은 커밋하지 않았다.

처음에는 한 명씩 순차 호출하면서 요청 사이에 고정 지연을 뒀다. 안전했지만 너무 느렸다. 이후 실행 방식을 다음처럼 조정했다.

- 이미 성공한 행은 다시 조회하지 않음
- 처리 단위를 batch로 가져옴
- 제한된 수의 worker로 병렬 처리
- 실패 시 정해진 횟수만 재시도
- `User not found`처럼 재시도로 해결되지 않는 오류는 별도 보관

속도를 높인 뒤에도 무제한 병렬 호출은 피했다. Apple의 rate limit에 걸리면 동시 실행 수를 낮출 수 있도록 concurrency와 요청 간격을 설정값으로 분리했다.

대부분은 정상적으로 `transfer_identifier`를 받았다. 소수 사용자는 다음 응답으로 실패했다.

```text
400 invalid_request
User not found.
```

이 행들은 반복 호출해도 결과가 달라지지 않았다. 성공한 사용자와 분리해 `failed` 상태와 오류 내용을 보관했다. 실패 목록도 따로 백업한 뒤 이전을 진행했다.

초기 성공 로그에는 식별자가 그대로 찍힐 여지가 있었다. 일회성 로컬 실행이라도 좋은 방식은 아니다. 다시 만든다면 `old_sub`, `new_sub`, 이메일, client secret은 출력하지 않고 account ID와 마스킹한 fingerprint, 처리 상태만 남길 것이다.

## 앱 이전보다 먼저 배포한 로그인 fallback

앱을 먼저 넘기고 서버를 나중에 고치면 그 사이 로그인한 기존 사용자가 새 계정으로 생성될 위험이 있다. 그래서 서버 코드를 먼저 배포했다.

이전 후 Apple의 ID token에는 새 팀 기준 `sub`와 함께 일정 기간 `transfer_sub`가 들어오기도 한다. 서버는 다음 순서로 사용자를 찾도록 바꿨다.

```text
1. 새 sub로 기존 계정 조회
2. 없고 transfer_sub가 있으면 migration 테이블 조회
3. transfer_identifier 또는 old_sub가 일치하는 기존 계정 조회
4. 기존 계정의 식별자를 새 sub로 갱신
5. migration 상태를 migrated로 변경
6. 그래도 찾지 못하면 신규 사용자 생성
```

이 로직은 전체 배치가 끝나기 전에 로그인하는 사용자를 위한 안전망이었다. 정상 경로를 영구히 복잡하게 만들 목적은 아니었으므로 마이그레이션이 끝난 뒤 제거할 수 있게 별도 코드로 관리했다.

## App Store Connect에서 앱 이전하기

이전 전 준비를 마치고 나서 App Store Connect의 앱 이전을 시작했다.

1. 기존 계정의 Account Holder가 앱 이전 요청
2. 새 계정의 Account Holder가 이전 수락
3. 이전 완료 상태 확인
4. 새 팀에서 App ID와 Sign in with Apple capability 확인
5. 새 팀 기준 Sign in with Apple key와 provisioning profile 생성

production Bundle ID는 바꾸지 않았다. App Store에 올라간 같은 앱으로 이어지려면 기존 Bundle ID를 유지해야 한다. 달라진 것은 Bundle ID 자체가 아니라 그 Identifier를 소유하고 서명하는 팀이었다.

App ID와 capability만 확인하고 끝내지도 않았다. 앱 메타데이터, 연락처, 개인정보처리방침 URL, 구독 관련 설정처럼 App Store Connect에 남은 운영 정보도 별도 체크리스트로 확인했다. 앱 이전과 서명 이전은 한 번에 끝나는 단일 작업이 아니었다.

## 이전 후 `transfer_identifier`를 `new_sub`로 바꾸기

처음에는 서버의 Team ID와 Key ID 같은 운영 환경 변수도 새 팀 값으로 바꿔야 한다고 생각했다. 로그인 callback 경로를 다시 확인해 보니 런타임 서버는 클라이언트가 보낸 ID token을 검증할 뿐, migration용 Team ID·Key ID·`.p8`를 쓰지 않았다. 이 credential은 이전 전후 일회성 배치에만 필요했다. 사용처를 확인한 덕분에 관련 없는 운영 환경 변수를 건드리지 않을 수 있었다.

이전이 끝난 뒤 새 팀의 Team ID, Key ID, `.p8`로 client secret을 다시 만들었다. 토큰 발급 방식은 같지만 이번 client secret은 수신 팀 기준이다. `userMigrationInfo`에는 기존 `sub`가 아니라 이전 전에 저장한 `transfer_sub`를 전달했다.

```text
POST https://appleid.apple.com/auth/usermigrationinfo

transfer_sub=<TRANSFER_IDENTIFIER>
client_id=<APP_ID_OR_SERVICES_ID>
client_secret=<TARGET_TEAM_CLIENT_SECRET>
```

응답으로 받은 값이 새 팀에 종속된 사용자 식별자 `sub`다. 이를 migration 테이블의 `new_sub`에 먼저 저장했다.

곧바로 `account.username`을 바꾸지 않고 스크립트를 둘로 나눴다. 중간 검증 지점을 만들기 위해서였다.

1. `collect-new-sub`: `transfer_identifier -> new_sub`를 수집하고 상태를 `new_sub_collected`로 변경
2. 중복·누락·실패 건수 검증
3. `apply-new-sub`: 검증을 통과한 행만 `account.username` 갱신
4. 실제로 한 행이 변경됐을 때만 상태를 `migrated`로 변경

DB 반영 배치에는 현재 값이 여전히 `old_sub`인지 확인하는 조건을 넣었다.

```sql
UPDATE account
SET username = :new_sub,
    updated_at = CURRENT_TIMESTAMP
WHERE id = :account_id
  AND type = 'apple'
  AND username = :old_sub;
```

이미 다른 경로에서 식별자가 바뀌었거나 예상 밖의 값이 들어 있다면 덮어쓰지 않고 실패로 남기는 compare-and-set 형태다. 소량 샘플로 Apple 응답과 DB 상태를 확인한 뒤 전체 배치를 실행했다.

Apple은 수신 팀이 이전을 수락한 뒤 60일 이내에 식별자 교환을 끝내도록 안내한다. 이 기간에는 로그인 ID token에도 `transfer_sub`가 포함되기도 한다. 하지만 60일이 지나면 API와 token의 이전 정보에 더는 의존하지 못한다. 여기서 60일은 fallback 코드를 반드시 유지해야 하는 기간이 아니라 식별자를 교환할 수 있는 최대 기한이다. 이번에는 전체 배치와 로그인 검증을 빠르게 마치고 임시 fallback을 제거했다.

## iOS Team ID와 provisioning profile 전환

서버의 사용자 마이그레이션과 별개로 iOS 프로젝트도 새 계정에 맞춰 다시 구성했다.

- 모든 iOS configuration의 Development Team을 새 팀으로 변경
- Release와 개발용 provisioning profile을 새 팀에서 다시 생성
- Release와 Staging은 이전된 production Bundle ID 유지
- Debug와 Local은 새 팀에 등록한 개발용 Bundle ID로 통일
- configuration별 entitlement 파일 분리
- 이전 팀의 App Group 참조 제거
- Debug와 Local entitlement에도 Sign in with Apple capability 추가
- 수동 서명 설정에서 configuration별 profile을 명시

설정은 다음과 같은 형태가 됐다.

```text
Release / Staging
  PRODUCT_BUNDLE_IDENTIFIER = <PRODUCTION_BUNDLE_ID>
  DEVELOPMENT_TEAM = <NEW_TEAM_ID>
  PROVISIONING_PROFILE_SPECIFIER = <NEW_RELEASE_PROFILE>

Debug / Local
  PRODUCT_BUNDLE_IDENTIFIER = <DEVELOPMENT_BUNDLE_ID>
  DEVELOPMENT_TEAM = <NEW_TEAM_ID>
  PROVISIONING_PROFILE_SPECIFIER = <NEW_DEVELOPMENT_PROFILE>
```

entitlement도 configuration별로 분리했다.

```xml
<key>com.apple.developer.applesignin</key>
<array>
  <string>Default</string>
</array>
```

기존에는 여러 configuration이 같은 entitlement를 공유하며 이전 팀의 App Group을 참조했다. 새 팀에 없는 group을 계속 요청하면 profile과 entitlement가 맞지 않아 서명 오류가 날 수 있다. 쓰지 않는 이전 팀의 group을 제거하고 실제 필요한 capability만 configuration별로 맞췄다.

## 시뮬레이터의 Apple 로그인 오류 분리

앱 코드에는 로그인 요청 뒤 `getCredentialStateForUser()`로 상태를 한 번 더 확인하는 로직이 있었다. 이 호출이 iOS 시뮬레이터에서 오류를 일으켜 새 서명 설정을 검증하기 어려웠다.

로그인 요청에서 `identityToken`을 정상적으로 받았는지 확인한 뒤 서버 callback으로 넘기도록 흐름을 단순화했다.

```ts
const response = await appleAuth.performRequest({
  requestedOperation: appleAuth.Operation.LOGIN,
  requestedScopes: [appleAuth.Scope.FULL_NAME, appleAuth.Scope.EMAIL],
})

if (!response.identityToken) {
  return
}

await authService.callback(AuthProvider.APPLE, response.identityToken)
```

이 변경으로 credential state 조회 때문에 시뮬레이터 로그인 흐름이 끊기는 문제를 분리했다. 실제 인증의 유효성은 서버의 token 검증을 기준으로 판단해야 한다.

## 실패한 접근과 확인한 로그

### 앱 이전부터 하려 했다

가장 위험했던 가설은 “App Store Connect 이전부터 하고 사용자 migration은 나중에 처리해도 된다”는 생각이었다. Apple 로그인 사용자의 `sub`가 팀에 종속된다는 사실을 확인한 뒤 순서를 바꿨다. 이전 전 `transfer_identifier` 수집과 서버 fallback 배포가 먼저였다.

### 정상 연결된 사용자만 inventory에 넣었다

`INNER JOIN`으로 뽑은 inventory는 연결이 끊기거나 탈퇴 처리된 계정을 놓칠 수 있었다. 마이그레이션은 현재 화면에 노출되는 사용자 목록이 아니라 인증 계정 전체를 대상으로 해야 했다. 쿼리를 `LEFT JOIN`과 별도 검증 방식으로 바꿨다.

### 배치가 dev DB에 연결됐다

로컬에서 Telepresence를 쓰던 중 배치가 잘못된 환경의 DB 서비스에 연결됐다.

```text
relation "apple_account_migration" does not exist
```

처음에는 schema 문제로 봤다. `current_database()`, `current_schema()`, Apple 계정 수를 함께 확인한 뒤 접속 대상이 잘못됐다는 걸 찾았다. 배치 시작 로그에 DB 이름, schema, 대상 행 수를 출력하도록 고치고 올바른 환경에서 다시 실행했다.

### 이전 후 토큰 발급에서 `invalid_client`가 발생했다

새 팀 credential로 `user.migration` access token을 요청했지만 다음 오류가 돌아왔다.

```text
400 {"error":"invalid_client"}
```

처음에는 client secret 생성 코드를 의심했다. 민감한 원문을 출력하지 않는 범위에서 아래 항목을 차례로 확인했다.

- JWT header의 `alg`, `kid`
- payload의 `iss`, `sub`, `aud`, `iat`, `exp`
- private key fingerprint
- client secret hash와 길이
- Apple 응답 header
- App ID의 Sign in with Apple 활성화 여부
- key가 연결된 Primary App ID
- `client_id`가 Bundle ID인지 Services ID인지

JWT 구조를 확인한 다음 Apple Developer 포털에서 App ID의 Sign in with Apple 설정과 key 연결 값을 다시 적용했다. 같은 코드로 재시도하자 access token 발급에 성공했다. 사용자 식별자 교환과 DB 갱신도 이어갈 수 있었다.

Apple 내부 원인은 직접 확인하지 못했다. 그래서 “단순 반영 지연이었다”거나 “특정 설정 하나가 틀렸다”고 단정하지 않는다. 확인한 사실은 JWT 코드를 바꾸지 않은 채 포털 설정을 다시 적용한 뒤 성공했다는 점이다. 해결 기록도 추측 대신 재현 가능한 확인 순서로 남겼다.

## 앱에는 수명이 다른 식별자가 함께 있다

이번 문제는 설정 하나가 잘못돼 생긴 게 아니었다. 앱 이전에 포함되는 식별자의 범위를 너무 좁게 본 것이 근본 원인이었다.

| 구분 | 이전 시 처리 |
|---|---|
| App Store의 Bundle ID | 기존 production 값을 유지 |
| Development Team | 새 팀으로 변경 |
| Provisioning profile | 새 팀에서 재생성 |
| App Group | 자동 이전되지 않으므로 재등록 또는 제거 |
| Apple 로그인 `sub` | 팀 종속 값이므로 사용자별 migration 필요 |
| `transfer_identifier` | 이전 팀과 새 팀의 `sub`를 잇는 임시 식별자 |

App Store에 보이는 Bundle ID가 같더라도 인증과 서명에 쓰이는 모든 식별자가 유지되는 것은 아니다.

## 최종 작업 순서

### 이전 전

1. App Store Connect의 이전 가능 조건 확인
2. Sign in with Apple grouping과 Services ID 관계 확인
3. 기존 팀의 Team ID·Key ID·`.p8`와 수신 Account Holder 정보 확보
4. Apple 로그인 계정 전체 inventory와 CSV 백업 생성
5. 계정 식별자 컬럼 길이와 migration 테이블·unique index 준비
6. 기존 팀 credential로 `old_sub -> transfer_identifier` 배치 실행
7. 실패 행과 오류 원인 별도 백업
8. 로그인 callback에 `transfer_sub` fallback 구현
9. fallback 서버 코드를 production에 먼저 배포

### 실제 이전

1. 기존 Account Holder가 앱 이전 요청
2. 새 Account Holder가 요청 수락
3. 이전 완료 상태 확인
4. 새 팀의 App ID, capability, Sign in with Apple key 확인
5. provisioning profile 재생성과 App Store Connect 운영 정보 확인

### 이전 후

1. 런타임과 배치의 credential 사용처를 구분
2. 새 팀 credential로 access token 발급
3. `collect-new-sub`를 소량 실행해 `new_sub` 수집
4. 중복, 누락, 실패 여부 검증 후 전체 수집 배치 실행
5. 별도 `apply-new-sub` 배치로 `account.username` 갱신
6. 계정 값이 `old_sub`와 일치하는 행만 변경됐는지 검증
7. 기존 사용자와 신규 사용자의 Apple 로그인 smoke test
8. 새 팀 기준 iOS Team, profile, entitlement 적용
9. 모든 사용자 migration 완료 후 임시 fallback 코드와 일회성 스크립트 제거

## 전환 결과와 검증

마이그레이션할 수 있는 Apple 계정의 식별자를 새 팀 기준 `sub`로 바꿨다. 정확한 내부 수치는 공개하지 않는다. 이전 전에 따로 보관한 소수 실패 행을 제외한 대상은 모두 `old_sub -> transfer_identifier -> new_sub` 순서로 전환했다.

완료 여부는 다음 조건으로 검증했다.

- `pending` 상태가 남지 않음
- 성공 행의 `transfer_identifier`와 `new_sub`가 모두 채워짐
- `new_sub` 중복이 없음
- 계정 테이블의 식별자와 migration 테이블의 `new_sub`가 일치함
- 기존 Apple 사용자가 중복 계정 없이 로그인됨
- 신규 Apple 사용자도 정상 가입됨

전체 식별자 전환 뒤에는 로그인 callback의 `transfer_sub` 임시 처리, 서버 코드의 migration 엔티티, 일회성 스크립트를 제거했다. 일시적인 이전 로직을 정상 로그인 경로에 계속 남겨 두지 않은 것도 중요한 마무리였다.

운영 DB의 migration 테이블은 곧바로 삭제하지 않았다. 전환 결과와 실패 내역을 확인할 감사 자료로 당분간 남겼다. 코드 정리와 데이터 삭제는 같은 작업이 아니므로 보존 기간과 삭제 시점을 정한 뒤 따로 처리해야 한다.

iOS는 production Bundle ID를 유지하면서 새 팀의 provisioning profile로 서명하도록 바꿨다. Debug와 Local configuration은 새 계정에 등록된 개발용 Identifier를 사용한다. 각각 필요한 Sign in with Apple entitlement도 갖추도록 정리했다.

## 작업을 마치고 배운 점

### App Transfer는 식별자 전환 작업이다

App Store Connect 화면만 보면 앱 하나를 다른 계정으로 넘기는 일처럼 보인다. 실제 작업에서는 사용자 식별자, 서명 주체, profile, capability의 소유권까지 함께 다뤄야 했다.

### 이전 전 작업이 더 중요하다

`transfer_identifier`와 fallback 서버 코드가 준비되지 않은 상태에서 앱부터 넘기면 복구가 훨씬 어려워진다. 마이그레이션에서는 “무엇을 바꿀지”만큼 “언제 바꿀지”가 중요했다.

### 배치는 재실행할 수 있어야 한다

외부 API를 사용자 수만큼 호출하는 작업에서는 중간 실패가 생긴다. 성공한 행을 건너뛰고 실패 이유를 보관하며 일부 재실행이 가능해야, 운영 중 멈춰도 안전하게 이어간다.

### 환경 이름은 로그에 남겨야 한다

dev와 production의 서비스 이름이 비슷하면 잘못 연결하기 쉽다. DB host를 그대로 노출할 필요는 없지만 환경명, database, schema, 대상 행 수는 배치 시작 로그에 남기는 편이 좋다.

### `invalid_client`는 확인 순서가 중요하다

`invalid_client`가 났다고 곧바로 JWT 생성 코드 문제로 볼 수는 없다. JWT claim과 key fingerprint를 먼저 살폈다. 이어 App ID, Services ID, Primary App ID, key 연결 상태를 포털에서 다시 확인·적용하는 순서가 유용했다. 이번에는 포털 설정을 재적용한 뒤 같은 코드가 성공했다. 하지만 Apple 내부 원인까지 확인한 것은 아니다.

### 60일은 유예 기간이지 작업 일정이 아니다

Apple이 안내하는 60일은 사용자 식별자를 교환할 수 있는 최대 기한이다. fallback을 60일 내내 유지하라는 뜻은 아니다. 배치와 검증을 일찍 끝냈다면 임시 로그인 분기를 빠르게 제거하는 편이 정상 경로를 단순하게 유지하는 데 도움이 된다.

### 일회성 스크립트도 secret과 로그를 안전하게 다뤄야 한다

로컬에서 한 번만 실행하는 코드라도 `.p8`, DB credential, 사용자 식별자를 코드나 로그에 그대로 남기면 안 된다. 이번 스크립트는 커밋하지 않고 실행 뒤 삭제했다. 다시 설계한다면 환경 변수나 secret manager를 사용하고 로그에는 마스킹된 식별자만 남길 것이다.

## 같은 문제를 겪는다면 확인할 것

- [ ] production Bundle ID를 그대로 유지하는가
- [ ] Sign in with Apple 사용자 `sub`를 DB 어디에 저장하는지 찾았는가
- [ ] 이전 대상 전체를 CSV로 백업했는가
- [ ] Sign in with Apple app grouping을 해제했는가
- [ ] 기존 팀의 Team ID, Key ID, `.p8`를 확보했는가
- [ ] 새 팀의 Team ID, Key ID, `.p8`와 수신 Account Holder 정보를 확보했는가
- [ ] `.p8`와 DB credential이 저장소·로그에 남지 않는가
- [ ] 사용자별 `transfer_identifier`를 이전 전에 수집했는가
- [ ] 앱 이전 전에 `transfer_sub` fallback 서버를 배포했는가
- [ ] 새 팀에서 App ID와 Sign in with Apple key를 확인했는가
- [ ] 이전 수락 후 60일 안에 `new_sub` 교환을 끝낼 계획이 있는가
- [ ] 배치를 소량으로 먼저 실행하고 전체 실행했는가
- [ ] `new_sub` 수집과 계정 테이블 반영을 분리했는가
- [ ] 계정의 현재 값이 `old_sub`일 때만 갱신하도록 보호했는가
- [ ] 실패 행, 중복 식별자, 누락 행을 별도로 검증했는가
- [ ] Release, Debug, Local의 Bundle ID와 profile을 각각 확인했는가
- [ ] 이전 팀의 App Group이나 Keychain Group이 entitlement에 남아 있지 않은가
- [ ] App Store Connect의 연락처·정책 URL·구독 관련 정보를 확인했는가
- [ ] 기존 사용자와 신규 사용자의 Apple 로그인을 모두 테스트했는가
- [ ] 완료 후 임시 migration 코드·스크립트·secret을 제거했는가
- [ ] migration 테이블의 보존 기간과 삭제 시점을 정했는가

## 참고 자료

- [Apple: Overview of app transfer](https://developer.apple.com/help/app-store-connect/transfer-an-app/overview-of-app-transfer/)
- [Apple: Transferring your apps and users to another team](https://developer.apple.com/documentation/signinwithapple/transferring-your-apps-and-users-to-another-team)
- [Apple: Bringing new apps and users into your team](https://developer.apple.com/documentation/signinwithapple/bringing-new-apps-and-users-into-your-team)
