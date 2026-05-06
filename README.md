<br><br>

## 1. 담당자

- 담당자: 안지철
- 담당 영역:
  - AI 서버 API 설계 및 구현
  - LH/SH 공고 PDF 수집 파이프라인 구현
  - OpenAI 기반 공고 문서 분석 연동
  - 온보딩 질문 답변 추출 기능 구현
  - 사용자 답변 기반 지원 자격 진단 기능 구현

<br><br>

## 공고 수집

<br>

#### LH 공고

1. 공고 상세 페이지 HTML 요청
2. 첨부파일 영역에서 `.pdf` 파일 링크 탐색
3. `fileDownLoad('file_id')` 형태의 값에서 file_id 추출
4. LH 다운로드 API로 PDF 다운로드
5. OpenAI에 전달할 PDF bytes 반환

<br>

#### SH 공고

1. 공고 URL에서 `seq` 파라미터 추출
2. 공고 상세 HTML의 script 영역에서 `initParam.downList` 추출
3. fileSeq 목록 기반으로 첨부파일 다운로드
4. PDF 파일만 선별
5. PDF가 여러 개면 페이지 단위로 병합
6. OpenAI에 전달할 단일 PDF bytes 반환

<br><br>

## 공고 PDF 기반 온보딩 답변 추출 API
<br>

### `POST /api/ingest`

공고 링크와 질문 목록을 입력받아, 공고 PDF 내용을 기반으로 각 질문에 대한 답변 초안을 생성

<br>

### 요청 

```json
{
  "link": "https://example.com/notice/detail",
  "publisher": "LH",
  "questions": [
    {
      "title": "소득 기준",
      "description": "공고에서 요구하는 소득 기준",
      "question": "이 공고의 소득 기준은 무엇인가?"
    },
    {
      "title": "거주지 조건",
      "description": "신청자의 거주지 관련 조건",
      "question": "신청 가능한 거주지 조건은 무엇인가?"
    }
  ]
}
```
<br>

### 응답 예시

```json
[
  {
    "title": "소득 기준",
    "value": "월평균 소득이 전년도 도시근로자 가구원수별 가구당 월평균소득의 100% 이하"
  },
  {
    "title": "거주지 조건",
    "value": null
  }
]
```
<br><br>

## 지원 자격 진단 API

<br>

### `POST /api/eligibility/diagnose`

공고별 지원 자격 요건과 사용자의 온보딩 답변을 비교하여 지원 가능 여부를 진단.

<br>

### 요청 예시

```json
{
  "REQUIREMENTS_JSON": [
    {
      "additionalOnboardingId": 1,
      "key": "무주택 여부",
      "value": "신청자는 무주택자여야 한다."
    },
    {
      "additionalOnboardingId": 2,
      "key": "나이 조건",
      "value": "만 19세 이상 만 39세 이하 청년이어야 한다."
    }
  ],
  "ANSWERS_JSON": [
    {
      "additionalOnboardingId": 1,
      "value": "무주택자입니다."
    },
    {
      "additionalOnboardingId": 2,
      "value": "만 27세입니다."
    }
  ]
}
```
<br>

### 응답 예시

```json
{
  "supportStatus": "ELIGIBLE",
  "trace": [
    {
      "additionalOnboardingId": 1,
      "key": "무주택 여부",
      "passed": true,
      "message": "요건은 무주택자 여부이며, 사용자 답변은 무주택자입니다. 판정 결과 PASS입니다."
    },
    {
      "additionalOnboardingId": 2,
      "key": "나이 조건",
      "passed": true,
      "message": "요건은 만 19세 이상 만 39세 이하이며, 사용자 답변은 만 27세입니다. 판정 결과 PASS입니다."
    },
    {
      "additionalOnboardingId": null,
      "key": "최종 점검",
      "passed": true,
      "message": "PENDING 또는 FAIL 조건이 없어 보수적 판정 원칙에 따라 ELIGIBLE로 결론 냈습니다."
    }
  ]
}

```
<br>

### 지원 상태

| 값 | 의미 |
|---|---|
| `ELIGIBLE` | 지원 가능 |
| `INELIGIBLE` | 지원 불가능 |
| `PENDING` | 정보 부족 또는 조건 불명확으로 진단 보류 |

<br><br>

## 기술 스택

| 구분 | 사용 기술 |
|---|---|
| Language | Python 3.11 |
| Web Framework | FastAPI |
| Data Validation | Pydantic |
| HTTP Client | requests |
| HTML Parsing | BeautifulSoup4 |
| PDF Handling | pypdf |
| AI Integration | OpenAI Files API, OpenAI Responses API |
| Environment | python-dotenv |
| Server | Uvicorn |
| Container | Docker |

<br><br>

## 패키지 구조

```text
app/
  main.py
  routes/
    ingest.py
    eligibility.py
  services/
    pipeline_runner.py
    lh/
      lh_pdf_parser.py
      lh_pdf_downloader.py
    sh/
      sh_pdf_seq_parser.py
      sh_pdf_downloader.py
    openai/
      openai_client.py
      onboarding_ai_service.py
      eligibility_ai_service.py
  prompts/
    eligibility.txt

requirements.txt
Dockerfile
```
