# 현대 또는 기아 개발자 프로젝트 준비

[English](developer-setup.md) | [한국어](developer-setup.ko.md)

이 통합 구성요소는 대한민국 개발자 서비스를 사용합니다. 현대와 기아는 개발자
회원 및 프로젝트를 각각 만들어야 합니다.

| 브랜드 | 공식 안내 | 개발자 콘솔 |
| --- | --- | --- |
| 현대 | [콘솔 안내](https://developers.kia.com/web/v1/hyundai/guide_console) | [console.developers.hyundai.com](https://console.developers.hyundai.com) |
| 기아 | [콘솔 안내](https://developers.kia.com/web/v1/kia/guide_console) | [console.developers.kia.com](https://console.developers.kia.com) |

## 1. 커넥티드 카 계정 준비

차량을 소유한 Bluelink 또는 Kia Connect 계정을 사용하세요. 공유받은 차량은
개발자 콘솔이나 차량 목록에 표시되지 않을 수 있습니다.

두 브랜드 차량을 모두 소유했다면 현대와 기아에 대해 이 과정을 각각 진행하세요.

## 2. 프로젝트 생성

1. 올바른 브랜드의 개발자 서비스에 가입하고 콘솔에 로그인합니다.
2. 개발 프로젝트를 만들고 콘솔에 표시되는 약관에 동의합니다.
3. 프로젝트의 **Client ID**와 **Client Secret**을 비밀번호 관리자에
   보관합니다.
4. **Account API Redirect URL**을 다음과 정확히 입력합니다.

   ```text
   https://example.com/redirect
   ```

   URL 끝에 `/`를 추가하지 마세요.

Client ID, Client Secret 또는 인증 코드가 포함된 OAuth 리디렉션 URL을 커밋,
게시 또는 스크린샷으로 공유하지 마세요.

## 3. 차량 활성화

개발자 콘솔의 **My Vehicle**에서 커넥티드 카 계정이 소유한 차량을
활성화합니다. 차량이 없다면 브랜드 계정, 차량 소유 관계 및 Bluelink 또는 Kia
Connect 가입 상태를 확인하세요.

프로젝트 준비가 끝났습니다. [Home Assistant 설정](../README.ko.md#계정과-차량-추가)으로
돌아가세요.

이 프로젝트는 대한민국 개발자 서비스를 이용한 개인 용도를 대상으로 합니다.
API 제공과 이용 조건은 제조사가 관리합니다.
