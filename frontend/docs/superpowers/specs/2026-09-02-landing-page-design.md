# 홈 랜딩페이지 설계 — (Jira 번호 미정, 임시 S15P21A504-0)

2026-09-02 · 담당: 장수철(Frontend) · 원안: `frontend/landing.md` (토스형 스크롤 스토리)

## 목표

홈(`/`)을 서비스 소개 랜딩으로 개편한다. 스크롤하면서 브랜드와 다섯 가지 분석을 이해하고,
실제 기업 검색으로 이어진다. **실제 5탭 분석 화면이 중심이고 인터랙션은 보조**다.

## 구성 (스크롤 순서)

| 구간 | 내용 | 구현 |
|---|---|---|
| 헤더 | 로고 마크 + 기업 찾기 · 분석 기준 · 기업 검색 버튼. 처음 투명 → 스크롤 시 흰 반투명 blur | `LandingHeader` |
| Scene 01 Hero | "기업은 숫자로 말합니다 / 기분은 그 변화를 읽습니다" + 검색창(기존 검색 플로우 그대로) + 데이터 점 배경 | `HeroScene` |
| Scene 02~03 | 흩어진 자료 카드 9장 → 다섯 가지 질문 카드(각 Scene 앵커) | `ProblemStory` |
| Scene 04~08 | 왼쪽 문구 5개가 스크롤에 따라 바뀌고, 오른쪽 브라우저 프레임(sticky)은 탭·패널만 전환. 각 장면에 "실제 화면에서 보기" 링크 | `ProductStory` + `DemoBrowser` |
| Scene 09 | 지원 전 세 가지(성장 신호·집중 신호·최근 이슈) 카드 + "근거 보기" → 실제 탭 | `TakeawayScene` |
| Scene 10 + Footer | 검색 CTA(히어로 검색창으로 스크롤·포커스) + 분석 가능한 기업 + 분석 기준 + 푸터 | `FinalSearchScene` |

## 결정 사항

- **검색 폼은 히어로에 하나만.** 헤더·CTA·푸터의 "기업 검색"은 그 폼으로 스크롤·포커스한다(중복 id·중복 폼 방지).
- **데모 데이터는 고정**(`data/homepageDemo.ts`). 홈이 API 여러 개에 의존해 깨지거나 애니메이션 타이밍이 흔들리지 않게 한다. 실제 검색부터 API.
- **의존성 추가 없음.** GSAP 대신 IntersectionObserver + CSS 트랜지션. 관찰이 불가하거나 모션 축소 설정이면 모든 내용이 처음부터 보인다.
- **브랜드 색은 앱과 같은 blue-600** 유지(앱 전체 색 변경은 범위 밖). 랜딩 원안의 인디고 토큰은 로고·캐릭터 색 확정 후 별도 반영.
- **거짓 표기 금지**: "최근 많이 찾은 기업" 대신 "분석 가능한 기업"(목업/시드 기업), 비교 데모는 "비교 기업 평균 · 예시 데이터"로 표기.
- **모바일**: sticky 프레임 제거, 문구 → 해당 카드 세로 흐름.
- Company Creature·데이터 파티클·영상·3D 는 후순위(에셋 준비 후).

## 필요한 에셋 (준비되면 교체)

- 글자 없는 로고 마크 SVG (지금은 임시 마크)
- Company Creature 캐릭터 이미지/애니메이션 (Hero·다섯 질문 장면)
- (선택) Hero 배경 영상 또는 데이터 파티클 루프
- 기업 로고 이미지 (데모 브라우저 헤더)

## 구조

```
pages/home/
  HomePage.tsx        검색 상태 + 장면 조립 + 검색창 포커스
  LandingHeader.tsx   고정 헤더 + LogoMark
  HeroScene.tsx       Scene 01 (+ DataDots 배경)
  ProblemStory.tsx    Scene 02~03
  ProductStory.tsx    Scene 04~08 (IntersectionObserver 로 활성 장면)
  DemoBrowser.tsx     브라우저 프레임 + 5개 DemoPanel
  TakeawayScene.tsx   Scene 09
  FinalSearchScene.tsx Scene 10 + Footer
  Reveal.tsx / useInView.ts  등장 모션
data/homepageDemo.ts  장면 문구·데모 수치·분석 가능한 기업
styles/global.css     랜딩 타이포·카드·프레임·모션 토큰·reduced-motion
```

## 테스트

- 기존 검색 플로우 테스트 유지(로딩·결과·이동·빈 결과·재시도)
- 브랜드 문구·다섯 질문·장면별 실제 화면 링크 5개·근거 보기 3개·분석 가능한 기업 링크
- CTA 클릭 시 히어로 검색창 포커스
