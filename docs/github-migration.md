# GitHub 이전 가이드

## 이전 기준

종료 문서 브랜치 `docs/S15P21A504-0-final-docs`를 기준으로 합니다. 기존 GitLab 기본 브랜치 `main`에는 별도로 포팅 매뉴얼, 외부 서비스 목록, DB 덤프 절차, 시연 시나리오와 스크린샷이 `exec/`에 있습니다. 필요한 시연 자료는 운영 정보나 개인정보가 포함되어 있는지 확인한 뒤 선택해서 옮깁니다.

팀과 공개 범위를 협의하기 전에는 GitHub 저장소를 Private으로 생성합니다. 공개하려면 팀 코드, 자료, 이미지, 데이터의 재배포 권한을 함께 확인합니다. 이 저장소에는 프로젝트 전체에 적용되는 라이선스 파일이 없습니다.

## 최종 버전만 옮기기

GitLab 이력을 별도로 보관하고 GitHub에는 최종본만 옮길 때 사용합니다.

1. 이전할 문서 변경을 기준 커밋에 반영합니다.
2. 원본 저장소 루트에서 `git archive --format=zip --output=../fit-source.zip HEAD`로 추적 파일을 내보냅니다.
3. ZIP을 새 디렉터리에 풀고 배포 주소, 계정 정보, 테스트 입력, 미디어와 데이터의 공개 범위를 확인합니다.
4. GitHub에 빈 저장소를 만들고, 새 디렉터리에서 아래 명령을 실행합니다. URL은 대상 저장소 주소로 바꿉니다.

```bash
git init -b main
git add --all
git commit -m "Import final Fit project"
git remote add origin https://github.com/OWNER/REPO.git
git push -u origin main
```

## 커밋 이력도 옮기기

팀원별 커밋을 보존해야 한다면 이전할 브랜치에서 도달할 수 있는 전체 이력을 먼저 검토합니다. 현재 파일에서 지운 자격 증명이나 내부 자료도 과거 커밋에 남을 수 있습니다. 기준 브랜치와 이전 커밋을 확정한 뒤 기존 GitLab 원격과 별도로 GitHub 원격을 추가합니다.

```bash
git remote add github https://github.com/OWNER/REPO.git
git push github HEAD:refs/heads/main
```

이 명령은 현재 `HEAD`를 GitHub의 빈 `main`에 올립니다. GitLab 이슈, MR, CI 변수, 러너, Jenkins 설정과 운영 DB는 별도 이전 대상입니다.

## 이전 후 확인

- GitHub 기본 브랜치에서 README와 문서 링크가 열리는지 확인합니다.
- 새로 클론한 디렉터리에서 README의 화면 데모를 실행합니다.
- GitLab 및 Jenkins 배포 설정이 필요한 경우 GitHub 저장소에 맞춰 별도로 연결합니다.
