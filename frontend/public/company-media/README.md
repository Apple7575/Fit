# 기업 요약 화면 사진 (업종 그룹 단위)

사진은 기업별이 아니라 **업종 그룹 16개** 단위로 둔다. 같은 그룹의 기업은 같은 사진을 쓴다.
기업의 업종 코드(KSIC 중분류, 기본정보 API 의 `industryCode`)가 어느 그룹인지는
`src/features/company-summary/industryGroups.ts` 에 있다. 표에 없는 업종은 `life` 그룹으로 간다.
로고만 기업별이며, 파일을 두지 않고 logo.dev → Google 파비콘 → 이니셜 순으로 자동 조회한다.

## 폴더

`industry/{group}/` — group 은 semiconductor · machinery · software · bio · chemical · finance · retail · auto ·
medical · electrical · steel · food · construction · media · logistics · life

| 파일 | 용도 | 규격 |
| --- | --- | --- |
| `hero.mp4` · `hero.jpg` · `hero.png` | 첫 화면 배경 | 1920×1080. 영상은 8~12초 무음 루프 4MB 이하 |
| `point-business.*` | "알아둘 세 가지" 중 사업(매출 구성) 카드 | 960×720 |
| `point-direction.*` | 방향(키워드·R&D) 카드 | 960×720 |
| `point-momentum.*` | 흐름(실적 변화·뉴스) 카드 | 960×720 |
| `point-rank.*` | 업계 순위 카드 | 960×720 |
| `credits.json` | 사진 출처 (아래) | |

찾는 순서는 영상 → jpg → png 이다. 파일이 없는 칸은 브랜드색 바탕(배경)이나 코치 캐릭터(포인트)로 대체된다.

## 출처 표기 (`credits.json`)

CC BY · CC BY-SA 사진은 저작자와 라이선스를 밝혀야 한다. 슬롯 이름을 키로 적어 두면 화면이 사진 위에
"사진 · 저작자 · 라이선스" 캡션을 달고 원본 페이지로 연결한다. 직접 만든 이미지는 적지 않아도 된다.

```json
{
  "hero": {
    "title": "Semiconductor clean room",
    "author": "…",
    "license": "Public domain",
    "licenseUrl": null,
    "source": "https://commons.wikimedia.org/wiki/File:…"
  }
}
```

현재 사진은 위키미디어 공용(Wikimedia Commons)에서 업종 검색어로 모은 후보 중 작은 모델(Haiku)이
가이드(큰 글자·브랜드 로고·인물 주인공·옛 사진 제외)에 따라 고른 것이다.
