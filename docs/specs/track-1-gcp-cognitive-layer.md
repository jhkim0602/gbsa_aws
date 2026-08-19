# Track 1 — 인지 계층 GCP 이관 (STT / TTS / PDF)

**목표:** 음성 인식·음성 합성·문서 이해를 AWS에서 GCP로 옮긴다. LLM(Bedrock Claude)과 임베딩(Bedrock Titan)은 그대로 둔다.

**전제:** 세 서비스 모두 `shared/aws_clients/ports.py`의 Protocol 뒤에 있다. 도메인·API·워커 코드는 수정하지 않는다. 바꾸는 것은 어댑터 + `runtime/aws.py` 3줄 + IAM + 의존성이다.

**다른 트랙과의 겹침:** 없음. Track 3의 아바타 립싱크(29–30)만 이 트랙의 `speech_marks` 포맷에 의존한다 — 그 포맷을 먼저 확정해 Track 3에 알려준다.

---

## 0. 현재 상태 (코드 위치)

| 서비스 | 어댑터 | 호출 경로 | 실패 시 |
| --- | --- | --- | --- |
| TTS | `shared/aws_clients/production.py:649` `AwsPollyTextToSpeech` | 실시간 WS | `SpeechOutput(text_only=True, degraded_mode="text_only")` — 면접 계속 |
| PDF | `shared/aws_clients/production.py:707` `AwsTextract` | 워커(비동기) | 제출물 분석 실패 |
| STT | `shared/aws_clients/production.py:753` `AwsTranscribeSpeechToText` | 실시간 WS | 답변 유실 |

**Protocol 계약 (`shared/aws_clients/ports.py:151-168`) — 변경 금지:**

```python
class SpeechToText(Protocol):
    def transcribe(self, context: TenantContext, audio: bytes, *,
                   sample_rate_hz: int) -> Mapping[str, Any]: ...

class TextToSpeech(Protocol):
    def synthesize(self, context: TenantContext, text: str, *,
                   voice_id: str) -> Mapping[str, Any]: ...
```

`TextractPort`는 `workers/analysis/document_extract.py:21`에 있고 `extract_pages(context, object_id) -> tuple[TextractPage, ...]`를 요구한다. `TextractPage(page_number: int, lines: tuple[str, ...])`.

**작업 순서는 위험도 순이다: TTS → PDF → STT.** TTS는 실패해도 텍스트로 degrade되고, PDF는 워커 안이라 실시간 경로가 아니며, STT만 실시간 경로에서 실패가 곧 답변 유실이다.

---

## 1. 공통 준비 — GCP 인증

### 1.1 의존성

`pyproject.toml`에 `google-cloud-*`가 하나도 없다. 추가:

```
google-cloud-texttospeech
google-cloud-speech
google-cloud-documentai
```

`uv sync --frozen`이 CI에서 돌므로 `uv.lock`을 함께 커밋한다.

### 1.2 자격증명 — 디스크에 쓰지 않는다

`infra/README.md`의 규칙: 자격증명은 `task_environment`가 아니라 `task_secrets`로만 전달하고, Terraform에 `aws_secretsmanager_secret_version`을 두지 않는다. `GITHUB_TOKEN`이 이미 그 패턴이다 (`infra/environments/prod/main.tf:207-209`).

```hcl
task_secrets = {
  GITHUB_TOKEN        = "${module.data.application_secret_arn}:github_token::"
  GCP_CREDENTIALS_JSON = "${module.data.application_secret_arn}:gcp_credentials_json::"
}
```

`GOOGLE_APPLICATION_CREDENTIALS`(파일 경로) 방식을 쓰지 않는다. 컨테이너에 JSON 파일을 쓰는 순간 그 파일은 레이어·코어덤프·`docker cp`로 새어나간다. 메모리에서 로드한다:

```python
# backend/src/interview_evidence/shared/gcp_clients/credentials.py (신규)
def gcp_credentials(environment: Mapping[str, str]) -> Credentials:
    raw = environment.get("GCP_CREDENTIALS_JSON", "").strip()
    if not raw:
        raise RuntimeError("GCP_CREDENTIALS_JSON is required")
    return service_account.Credentials.from_service_account_info(json.loads(raw))
```

`infra/tests/test_terraform_contracts.py:329`의 `test_application_roots_deliver_the_github_credential_by_reference_only`와 같은 형태로 GCP 자격증명 테스트를 추가한다 — `task_environment`에 없고 `task_secrets`에 있음을 검증.

### 1.3 네트워크

`infra/modules/network/main.tf:214-218` 앱 SG egress가 `cidr_ipv4 = "0.0.0.0/0"`, `ip_protocol = "-1"`이므로 **GCP 아웃바운드 HTTPS는 변경 불필요**. 단 dev는 `nat_gateway_per_az`가 false라 NAT 1개를 공유한다 — STT 스트리밍 대역폭이 여기서 먼저 막힐 수 있다 (Track 4의 용량 산정 항목).

### 1.4 프로젝트 배치

`shared/gcp_clients/` 패키지를 새로 만든다. `shared/aws_clients/`와 형제. `scripts/check_module_boundaries.py`의 `LANE_MODULES`에 `shared`는 포함되지 않으므로 레인 규칙 위반이 아니다.

```
shared/gcp_clients/
  __init__.py
  credentials.py     # 위 1.2
  production.py      # 3개 어댑터
```

Protocol은 `shared/aws_clients/ports.py`에 그대로 두고 import한다. 포트를 옮기면 무관한 파일이 대량 수정된다.

---

## 2. 단계 A — TTS (Polly → GCP Text-to-Speech)

### 2.1 무엇만 바뀌는가

`AwsPollyTextToSpeech.synthesize`(`production.py:658-704`)에서 **`synthesize_speech` 호출 한 줄만** 바뀐다. S3 put + KMS SSE + presign은 그대로 유지한다 — 오디오가 테넌트 프리픽스 아래 CMK로 암호화되어 남는 것이 감사 요건이다.

```python
# 유지: object_key = f"tenants/{tenant.company_id}/speech/{uuid4()}.mp3"
# 유지: self._s3.put_object(..., ServerSideEncryption="aws:kms", SSEKMSKeyId=...)
# 유지: generate_presigned_url(..., ExpiresIn=self._expires_in_seconds)
# 반환 dict 키 3개 유지: audio_url / audio_expires_at / speech_marks_url
```

### 2.2 `speech_marks_url`을 처음으로 채운다

`production.py:703`이 `"speech_marks_url": None` 하드코딩이다. 이 필드가 아바타 립싱크의 유일한 입력인데 지금은 항상 None이므로 `Avatar.tsx`가 정지 이미지를 쓴다.

**GCP TTS는 Polly의 speech marks와 다르다.** `SynthesizeSpeechRequest`에 `enable_time_pointing=[TIMEPOINT_TYPE_SSML_MARK]`를 주고 SSML에 `<mark name="..."/>`를 심으면 `timepoints`가 돌아온다. 음소 단위가 아니라 **직접 심은 마크 단위**다. 따라서:

1. 텍스트를 SSML로 감싸고 어절 경계마다 `<mark name="w{n}"/>`를 삽입한다.
2. 응답 `timepoints`를 `[{"mark": "w0", "time_ms": 120}, ...]`로 정규화한다.
3. 이 JSON을 `tenants/{company_id}/speech/{uuid}.marks.json`으로 S3에 올리고 presign URL을 `speech_marks_url`에 넣는다.

**Track 3에 확정 통보할 스키마** — 이것이 이 트랙의 유일한 대외 계약이다:

```json
{ "marks": [ { "mark": "w0", "time_ms": 0 }, { "mark": "w1", "time_ms": 240 } ] }
```

Track 3은 이 배열을 오디오 `currentTime`과 비교해 입모양 프레임을 고른다. 음소가 아니라 어절이므로 프레임 3단(closed/mid/open) 중 mid/open을 어절 지속시간에 걸쳐 교차시키는 수준이 현실적 상한이다 — Track 3에 이 한계를 명시한다.

### 2.3 `voice_id` 마이그레이션 — 데이터 문제

`company_management/domain/criteria.py:33`의 기본값이 Polly 전용 `"Seoyeon"`이고, `integration/submission_interview.py:221`이 `voice_id=str(persona.get("voice_id", "Seoyeon"))`로 읽어 `InterviewPlan.voice_id`에 넣는다. DB의 `persona_definition` JSON에 이미 `"Seoyeon"`이 저장된 행들이 있다.

**어댑터에서 조용히 매핑하지 않는다.** 매핑을 어댑터에 숨기면 콘솔에 "Seoyeon"이 표시되는데 실제로는 다른 목소리가 나오는 상태가 영구화된다.

1. GCP 보이스 이름으로 기본값을 바꾼다 (`criteria.py:33`).
2. Alembic 마이그레이션으로 기존 `persona_definition->>'voice_id' = 'Seoyeon'` 행을 갱신한다. `backend/alembic/versions/company/`에 `a_005_gcp_voice_id.py`.
3. 어댑터는 알 수 없는 `voice_id`를 받으면 예외를 던진다 — `SpeechSynthesisAdapter`가 잡아 `text_only`로 degrade하므로 면접은 멈추지 않고, 로그에 남아 발견된다.

### 2.4 검증

- `interview_engine/adapters/polly.py`의 `SpeechSynthesisAdapter`는 **수정하지 않는다.** 모든 예외를 잡아 `text_only`로 degrade하는 로직이 그대로 GCP에도 적용된다.
- `AwsPollyTextToSpeech`를 삭제하고 IAM에서 `polly:SynthesizeSpeech`(`infra/modules/compute/main.tf:466`)를 제거한다. **이 문자열은 `test_terraform_contracts.py`가 검증하지 않으므로** 테스트 수정 불필요.
- 성공 기준: `question.ready` 메시지(`live_handlers.py:547`)에 `speech_marks_url`이 non-null로 나가고, `audio_url` 재생 시 한국어 발음이 정상이며, TTS를 강제 실패시키면 `text_only: true`로 degrade된다.

---

## 3. 단계 B — PDF (Textract → GCP Document AI)

### 3.1 왜 Document AI인가

Cloud Vision은 다중 페이지 PDF에 GCS 입출력을 강제한다. 우리 원본은 S3에 있으므로 GCS 왕복이 추가된다. **Document AI의 Document OCR processor는 `RawDocument`로 인라인 바이트를 받는다** — S3에서 읽어 바로 넘긴다.

Vertex AI가 아니다. 같은 서비스 계정으로 되지만 `documentai.googleapis.com`을 별도로 enable해야 한다.

### 3.2 구조가 바뀌는 지점

Textract는 `Document={"S3Object": {...}}`로 **AWS가 S3를 직접 읽었다**. GCP는 못 읽는다. 따라서 `runtime/aws.py:208-214`의 `object_key` 콜백 패턴이 사라지고, 어댑터가 `ObjectStorage`(또는 S3 클라이언트)를 받아 직접 GetObject한다.

```python
class GcpDocumentAiExtractor:
    def __init__(self, client, s3, *, bucket: str,
                 processor_name: str,
                 object_key: Callable[[TenantContext, UUID], str]) -> None: ...

    def extract_pages(self, context, object_id) -> tuple[TextractPage, ...]:
        require_tenant_context(context)
        # 1. S3 GetObject → bytes
        # 2. process_document(RawDocument(content=..., mime_type="application/pdf"))
        # 3. document.pages[i].lines → TextractPage(page_number=i+1, lines=...)
```

`object_key` 콜백은 유지한다 — 키 규칙(`tenants/{company_id}/submission-original/{object_id}`)이 런타임 배선에 있는 것이 옳고, 어댑터가 테넌트 프리픽스를 스스로 만들면 안 된다.

`TextractPage`의 이름은 그대로 둔다. 리네임하면 `document_extract.py`, `production.py`, `pipeline.py`가 무관하게 수정된다 — Track 2/4와 충돌한다. 이름 정리는 별건으로 남긴다.

### 3.3 페이지 번호는 1-indexed를 유지한다

Textract의 `Page`는 1부터 시작하고 `production.py:749`가 그대로 넘긴다. Document AI의 `pages[]`는 0-indexed 리스트다. **`page_number = index + 1`로 반드시 보정한다.** 여기서 틀리면 인용 페이지가 전부 1씩 밀리고, Evidence 추적성이 조용히 깨진다 (Track 2가 이 값을 읽는다).

### 3.4 크기 한계

`submission_validator.py`의 `max_file_bytes = 20 * 1024 * 1024`. Document AI 온라인 `process_document`는 페이지 수 제한이 있다(동기 처리 15~30페이지 수준). 제출된 PDF가 그보다 길면 실패한다.

- 검증 시점에 페이지 수를 세지 않으므로, **어댑터가 페이지 초과 예외를 받으면 `DocumentExtractionError`로 변환**해 `pipeline.py`가 제출물을 실패 처리하도록 한다.
- 배치 처리(GCS 필요)로 확장하는 것은 이 트랙 범위 밖. 로그로 발생 빈도를 먼저 관측한다.

### 3.5 검증

- `AwsTextract` 삭제, IAM `textract:AnalyzeDocument`(`compute/main.tf:469`) 제거. 이 문자열도 Terraform 테스트가 검증하지 않으므로 테스트 수정 불필요.
- 성공 기준: 한국어 이력서 PDF에서 `TextractPage.lines`가 Textract와 동등 이상으로 나오고, 페이지 번호가 1부터이며, 청킹(`document_chunker.py`)과 임베딩이 그대로 통과한다.

---

## 4. 단계 C — STT (Transcribe 폐기 → GCP Speech-to-Text v2)

**이 단계는 교체가 아니라 폐기·재구축이다.**

### 4.1 현재 코드가 왜 잘못됐는가 (3개 결함)

`production.py:753-819` `AwsTranscribeSpeechToText.transcribe`:

1. **실시간 경로 안의 배치 폴링.** `poll_interval_seconds=1, max_polls=120` — 최대 120초를 실시간 WebSocket 요청 안에서 블로킹한다.
2. **S3 왕복.** 청크마다 `tenants/{company_id}/transcribe/{job_id}.webm`에 put하고 `start_transcription_job`이 그것을 읽는다.
3. **거짓 포맷 계약.** `ContentType="audio/webm"`, `MediaFormat="webm"`로 올린다. 그런데 브라우저가 보내는 것은:
   - `media.ts:113` `new AudioContext({ sampleRate: 16000 })` + AudioWorklet → `Int16Array`
   - `protocolClient.ts:117-124` `codec: "pcm_s16le", sample_rate_hz: 16000, channel_count: 1`

   **원시 PCM을 webm이라고 라벨링해 업로드하고 있다.** 이 계약은 지켜지고 있는 것이 아니라 우연히 동작하거나 조용히 품질을 잃고 있다.

호출 경로는 `interview_engine/api/live_handlers.py:189-231`:
`handle_audio` → 멱등성 저장소 → `_transcribe_once` → **동기** `self._speech_to_text.transcribe(context, audio, sample_rate_hz=...)` → 빈 텍스트면 `transcript.partial(display_only=True)`, 아니면 draft 저장 + `transcript.final`.

### 4.2 GCP가 오히려 더 맞는다

Speech-to-Text v2 `recognize`는 인라인 `content` + `explicit_decoding_config`를 받는다:

```
encoding=LINEAR16, sample_rate_hertz=16000, audio_channel_count=1
```

**브라우저가 보내는 것과 정확히 일치한다.** S3 왕복과 120초 폴링이 둘 다 사라진다.

### 4.3 두 단계로 나눈다

**C-1: 동기 `recognize`로 포트를 그대로 만족시킨다 (먼저 배포)**

```python
class GcpSpeechToText(SpeechToText):
    def transcribe(self, context, audio, *, sample_rate_hz) -> Mapping[str, Any]:
        require_tenant_context(context)
        # recognize(config=explicit LINEAR16/sample_rate_hz/1, content=audio)
        # → {"text": ..., "confidence": ...}
```

반환 dict의 키는 `text` / `confidence`를 유지한다 — `live_handlers.py`가 이 두 키를 읽는다. 이것만으로 `runtime/aws.py:197-201` 3줄 교체로 끝나고, 실시간 지연이 즉시 개선된다.

**C-2: 스트리밍으로 전환한다 (이미 만들어져 방치된 seam을 쓴다)**

`interview_engine/adapters/transcribe.py`에 `StreamingTranscriber` Protocol과 `StreamingTranscriptionAdapter`가 **이미 있고 아무 곳에도 배선돼 있지 않다.** 이것이 목표 형태다:

```python
class StreamingTranscriber(Protocol):
    def stream(self, context, audio) -> tuple[TranscriptionResult, ...]: ...

# TranscriptionResult(segment_sequence, text, start_ms, end_ms,
#                     confidence, is_final, display_only, review_required)
# 어댑터가 is_final → display_only, confidence < 0.75 → review_required 를 채운다
```

`live_handlers.py`가 이미 `display_only` 개념으로 `transcript.partial`/`transcript.final`을 나누므로 의미가 맞는다. `StreamingRecognize`는 양방향 스트림이라 FastAPI WebSocket 핸들러의 요청-응답 형태와 수명이 다르다 — **세션 단위로 스트림을 열고 유지하는 구조 변경이 필요하다.** 이것이 C-2가 별 단계인 이유이며, C-1을 먼저 배포해 두면 C-2가 지연돼도 손실이 없다.

### 4.4 IAM과 Terraform 테스트 — 여기서만 테스트가 깨진다

`infra/tests/test_terraform_contracts.py:298-299`:

```python
assert '"transcribe:StartTranscriptionJob"' in compute
assert '"transcribe:GetTranscriptionJob"' in compute
```

**세 서비스 중 Transcribe만 Terraform 테스트가 IAM 문자열을 검증한다.** `compute/main.tf:470-472`에서 세 `transcribe:*` 액션을 제거하고, 이 두 assert를 삭제한다. 테스트는 "GCP 이관 후 AWS 인지 서비스 권한이 남아 있지 않다"로 다시 쓴다:

```python
for action in ("transcribe:", "textract:", "polly:"):
    assert action not in compute, f"{action} survived the GCP migration"
```

### 4.5 포맷을 한 곳에 못박는다

거짓 계약을 없애는 것이 이 단계의 절반이다. `pcm_s16le` / `16000` / `1`을 **상수 하나로 선언하고 클라이언트와 서버가 같은 값을 참조**하게 한다. `packages/contracts/events/websocket/`에 이미 WebSocket 스키마가 있으므로 거기에 명시하고, 어댑터는 `sample_rate_hz`가 예상과 다르면 예외를 던진다 — 조용히 잘못된 샘플레이트로 인식하는 것보다 실패가 낫다.

---

## 5. 배선 변경 — `runtime/aws.py`

3곳만 바뀐다.

| 줄 | 현재 | 이후 |
| --- | --- | --- |
| 197-201 | `AwsTranscribeSpeechToText(factory("transcribe"), s3, bucket=media_bucket)` | `GcpSpeechToText(credentials=...)` |
| 202-207 | `AwsPollyTextToSpeech(factory("polly"), s3, bucket=media_bucket, kms_key_id=...)` | `GcpTextToSpeech(client, s3, bucket=media_bucket, kms_key_id=...)` |
| 208-214 | `AwsTextract(factory("textract"), bucket=source_bucket, object_key=...)` | `GcpDocumentAiExtractor(client, s3, bucket=source_bucket, processor_name=..., object_key=...)` |

`AwsRuntimeDependencies`(`runtime/aws.py:80-95`)의 필드명은 `speech_to_text` / `text_to_speech` / `textract`를 **유지**한다. `textract`만 이름이 벤더에 묶여 있어 거슬리지만, 리네임하면 이 dataclass를 읽는 모든 호출부가 diff에 들어와 다른 트랙과 충돌한다.

`runtime/aws.py` 상단 import(26-45줄)에서 `AwsPollyTextToSpeech`, `AwsTextract`, `AwsTranscribeSpeechToText`, `PollyClient`, `TextractClient`, `TranscribeClient`를 제거한다.

**새 환경변수:** `GCP_PROJECT_ID`, `GCP_LOCATION`, `GCP_DOCUMENTAI_PROCESSOR_ID`, `GCP_TTS_VOICE_NAME`은 설정이므로 `task_environment`. `GCP_CREDENTIALS_JSON`만 `task_secrets`. `test_terraform_contracts.py:270`의 `required` set에 앞의 4개를 추가한다.

---

## 6. 지연 예산 — 측정이 이 트랙의 산출물이다

답변 1회에 다음이 **직렬**로 일어난다 (`live_handlers.py`, `interview_service.py`):

```
STT → Titan 임베딩(query_vector=None, live_handlers.py:439) → pgvector 검색
    → Bedrock 질문 생성 → TTS
```

각 구간을 계측한다 (`shared/operations.py`의 `MetricRecorder`가 이미 있다). **이 측정값이 Track 4의 용량 산정 입력이다** — "API 태스크 1개당 안전 동시 세션 수"는 이 직렬 지연 없이는 계산할 수 없다. Track 4에 넘길 것: 구간별 p50/p95, 그리고 이관 전/후 비교.

`query_vector=None`으로 매 답변에 임베딩을 새로 호출하는 것과 `interview_service.py:231`의 `older_summary=""` 하드코딩은 **Track 3의 37–38 항목**이다. 이 트랙에서 건드리지 않는다.

---

## 7. 완료 기준

1. `google-cloud-{texttospeech,speech,documentai}`가 `pyproject.toml`과 `uv.lock`에 있다.
2. `shared/gcp_clients/`에 3개 어댑터가 있고, `shared/aws_clients/production.py`에서 Polly·Textract·Transcribe 클래스가 삭제됐다.
3. `runtime/aws.py`의 3개 배선이 GCP 어댑터를 가리키고, 사용하지 않는 import가 없다.
4. `compute/main.tf`의 `ApprovedAI` 문에 `transcribe:*` / `textract:*` / `polly:*`가 없고, `test_terraform_contracts.py`가 그 부재를 검증한다.
5. `GCP_CREDENTIALS_JSON`이 `task_secrets`에만 있음을 Terraform 테스트가 검증한다.
6. `speech_marks_url`이 실제 URL을 반환하고, 그 JSON 스키마가 Track 3에 문서로 전달됐다.
7. `voice_id` 마이그레이션이 적용돼 DB에 Polly 보이스 이름이 남아 있지 않다.
8. Document AI 페이지 번호가 1-indexed다.
9. `npm run typecheck` (mypy strict) / `npm test` (pytest) / `make infra-validate` 통과.
10. 구간별 지연 측정값이 기록돼 Track 4에 전달됐다.
