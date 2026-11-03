# Planit — архитектура және деректер қорының схемасы

Planit — БЖБ / ТЖБ / АБ қағаз жұмыстарын сканерлеп, автоматты тексеретін веб-жүйе.
Негізгі өзек:

> Қағаз жұмысты жүктеймін → жүйе оқиды → оқушыны анықтайды → әр тапсырманы тексереді →
> дескриптор бойынша балл қояды → күмәнді жауаптарды көрсетеді → мұғалім бекітеді →
> дайын бағалау мен талдау.

## 1. Жүйе компоненттері

```
                ┌──────────────┐        HTTPS         ┌───────────────┐
 Браузер/телефон│  nginx (443) │ ───────────────────▶ │  frontend     │ Next.js 15, React, TS,
 ──────────────▶│  reverse     │                      │  (port 3000)  │ Tailwind, shadcn/ui
                │  proxy, TLS, │  /api, /ws           └───────────────┘
                │  rate limit  │ ───────────────────▶ ┌───────────────┐
                └──────────────┘                      │  backend      │ FastAPI (REST + WebSocket)
                                                      │  (port 8000)  │ OpenAPI: /api/docs
                                                      └──────┬────────┘
                         ┌──────────────────┬────────────────┼──────────────────┐
                         ▼                  ▼                ▼                  ▼
                   ┌──────────┐       ┌──────────┐     ┌───────────┐     ┌────────────┐
                   │PostgreSQL│       │  Redis   │     │ S3 / MinIO│     │  worker    │ Celery
                   │ (деректер)│      │ (кезек,  │     │ (файлдар, │     │ (preprocess│
                   └──────────┘       │  cache)  │     │ шифрланған)│    │  OCR, AI)  │
                                      └──────────┘     └───────────┘     └────────────┘
```

| Сервис    | Технология                         | Жауапкершілігі |
|-----------|------------------------------------|----------------|
| frontend  | Next.js 15 (App Router), TS, Tailwind, shadcn/ui, Recharts | UI, i18n (kk/ru/en), dark/light, responsive |
| backend   | Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2 | REST API, auth, RBAC, WebSocket прогресс, экспорт |
| worker    | Celery 5 (Redis broker)            | Ауыр өңдеу: PDF→сурет, preprocessing, QR, OCR, AI, бағалау |
| postgres  | PostgreSQL 16                      | Барлық деректер |
| redis     | Redis 7                            | Celery broker/result, rate-limit, cache |
| storage   | S3-compatible (MinIO / AWS S3) немесе local | Скандар, есептер. AES-GCM арқылы шифрланады |
| nginx     | nginx 1.27                         | TLS, gzip, upload лимиті, `/api` → backend, `/` → frontend |

## 2. Backend модульдері (clean / modular architecture)

```
backend/app
├── core/            config, security (JWT, bcrypt, CSRF), db, RBAC, rate limit, crypto
├── models/          SQLAlchemy ORM (барлық кестелер)
├── schemas/         Pydantic DTO (API келісімшарты)
├── api/routes/      auth, users, schools, classes, students, subjects, objectives,
│                    assessments, questions, question_bank, uploads/jobs, submissions,
│                    review, results, analytics, exports, templates, audit, settings, ws
├── services/
│   ├── storage/         StorageService: LocalStorage | S3Storage (+ шифрлау)
│   ├── preprocessing/   rotation/perspective/crop/denoise/shadow/contrast/deblur/align
│   ├── ocr/             OCRService → TesseractProvider | GoogleVisionProvider | AzureProvider | MockProvider
│   ├── detection/       QR/barcode, оқушыны анықтау, бет құрылымы, тапсырма аймақтары, OMR
│   ├── ai/              AIService → OpenAIProvider | AnthropicProvider | LocalProvider (rule-based)
│   ├── evaluation/      тапсырма түріне қарай evaluator-лар (MC, сандық, математика, ашық…)
│   ├── scoring/         ScoringEngine — балл, partial credit, confidence, статус (AI-дан тәуелсіз)
│   ├── pipeline/        Upload→Job→Queue→…→Result оркестраторы
│   ├── analytics/       сынып/тапсырма/дескриптор/оқу мақсаты талдауы, қателер категориясы
│   ├── export/          Excel (openpyxl), PDF (reportlab), Word (python-docx)
│   ├── templates/       QR-лы скан шаблонын (PDF) генерациялау
│   ├── feedback/        оқушыға кері байланыс
│   ├── generation/      AI арқылы БЖБ генерациялау
│   ├── integrations/    сыртқы электронды журнал adapter-лары (болашақ)
│   └── audit.py         audit log
├── workers/         celery_app, tasks
└── seed/            demo деректер + demo скан генераторы
```

### 2.1 Provider abstraction

```
OCRService (services/ocr/base.py: OCRProvider protocol)
 ├── TesseractProvider   — local, kaz+rus+eng, word-level confidence
 ├── GoogleVisionProvider— cloud (OCR_PROVIDER=google, GOOGLE_VISION_API_KEY)
 ├── AzureReadProvider   — cloud (OCR_PROVIDER=azure)
 └── fallback chain      — OCR_FALLBACKS=tesseract  (бірінші провайдер құласа)

AIService (services/ai/base.py: LLMProvider protocol)
 ├── OpenAIProvider      — structured output (json_schema)
 ├── AnthropicProvider   — tool-use арқылы JSON schema
 └── LocalProvider       — желісіз rule-based семантикалық салыстыру (әдепкі, demo)
```

Барлық провайдер жауабы `jsonschema` арқылы тексеріледі (hallucination protection, §52).
Схемаға сай келмесе немесе timeout болса → `manual_review_required`.

### 2.2 ScoringEngine (AI-дан бөлек, §51)

AI тек ұсыныс береді: `detected_answer`, `confidence`, дескриптор бойынша `met: bool`,
`reason`. Нақты балды **ScoringEngine** есептейді:

* объективті түрлер (MC, бірнеше жауап, сандық, формула, сәйкестендіру, кесте) — толығымен
  детерминистік, AI шақырылмайды;
* ашық жауап/эссе/есеп — `score = Σ descriptor.points where met`, `0 ≤ score ≤ max_score`;
  AI берген `score` тек салыстыру үшін сақталады, алшақтық болса confidence төмендейді;
* `final_confidence = min(ocr_confidence, evaluation_confidence)`;
* `≥ 95%` → `auto_approved` (баптауда өшіруге болады), `80–94%` → `medium`,
  `< 80%` → `needs_review`.

## 3. Өңдеу pipeline (§34)

```
POST /api/assessments/{id}/uploads   (файлдар валидацияланады: MIME, өлшем, malware scan)
   ↓  files + processing_jobs жазбасы (status=queued)
Celery: process_job(job_id)
   1. split      PDF → беттер (PyMuPDF, 200 dpi), сурет → бет
   2. preprocess document boundary → perspective → deskew/rotation → shadow removal →
                 denoise → CLAHE contrast → unsharp (deblur) → QR бойынша alignment
   3. identify   QR (assessment_id, student_id, page, version) → немесе header OCR →
                 оқушы тізімімен fuzzy matching → немесе «Оқушыны таңдаңыз»
   4. group      беттерді оқушы жұмысына (submission) бөлу (150 бет → 30 жұмыс)
   5. structure  шаблон бар болса: layout координаталары; жоқ болса: OCR layout-тан
                 «N.» / «N-тапсырма» маркерлері арқылы аймақтарды табу
   6. extract    әр аймақты OCR / OMR (A/B/C/D, checkbox) → answers + ocr_results
   7. evaluate   evaluator (детерминистік немесе AIService) → ai_evaluations
   8. score      ScoringEngine → evaluations + evaluation_items → results
   9. finalize   статистика, күмәнділер санағы, WebSocket арқылы «Дайын»
```

Әр қадам `processing_jobs.stage/progress` өрісін жаңартады; `WS /api/ws/jobs/{id}`
нақты уақытта көрсетеді. Кез келген қадамдағы қате (corrupted PDF, OCR/AI timeout,
API error) жұмысты тоқтатпайды — тиісті бет/жауап `manual_review_required` болады.

## 4. Деректер қорының схемасы (PostgreSQL)

Барлық кестеде `id` (bigint PK), `created_at`, `updated_at`. Жеке деректері бар кестелерде
`school_id` арқылы tenant шектеуі қолданылады.

### Ұйым және пайдаланушылар
| Кесте | Негізгі өрістер |
|---|---|
| **schools** | name, city, region, settings (jsonb) |
| **users** | email (unique), password_hash, full_name, role (`admin`/`school_admin`/`teacher`/`student`), school_id→schools, locale, is_active, last_login_at |
| **teachers** | user_id→users (unique), school_id, position |
| **subjects** | name, code, school_id (null=глобал) |
| **classes** | school_id, name ("7А"), grade, letter, academic_year, homeroom_teacher_id→teachers |
| **class_teachers** | class_id, teacher_id, subject_id (мұғалім-сынып-пән байланысы, RBAC негізі) |
| **students** | school_id, class_id, user_id (null), full_name, gender (`m`/`f`), student_code (QR үшін), is_active |

### Бағалау құрылымы
| Кесте | Негізгі өрістер |
|---|---|
| **learning_objectives** | code ("5.1.2.3"), description, subject_id, grade |
| **assessments** | type (`BZhB`/`TZhB`/`AB`), title, subject_id, class_id, teacher_id, academic_year, quarter, section, topic, date, max_score, status (`draft`/`active`/`completed`), settings jsonb |
| **assessment_versions** | assessment_id, version_label ("1-нұсқа"), template_layout jsonb (бет/аймақ координаталары), is_default |
| **questions** | version_id, number, text, answer_type (13 түр), correct_answer jsonb, max_score, criteria, tolerance, options jsonb, page_hint, objective_id→learning_objectives, ordering |
| **descriptors** | question_id, number, text, points, keywords jsonb |
| **question_bank_items** | owner_id→users, subject_id, grade, section, topic, objective_id, text, answer_type, correct_answer, max_score, descriptors jsonb, tags |

### Сканерлеу және өңдеу
| Кесте | Негізгі өрістер |
|---|---|
| **files** | storage_key, original_name, mime, size, sha256, encrypted, uploaded_by, kind (`upload`/`page`/`crop`/`report`) |
| **processing_jobs** | assessment_id, created_by, status, stage, progress, total_pages, processed_pages, error, stats jsonb |
| **submissions** | assessment_id, version_id, student_id (null=анықталмаған), job_id, status (`processing`/`needs_review`/`reviewed`/`approved`/`error`), detection_method (`qr`/`name_ocr`/`manual`), detection_confidence |
| **submission_pages** | submission_id, job_id, file_id (өңделген сурет), original_file_id, page_number, source_page_index, qr_payload, quality_score, preprocessing jsonb (қолданылған операциялар), width, height |
| **ocr_results** | page_id, provider, language, full_text, words jsonb (bbox+conf), mean_confidence, duration_ms |
| **answers** | submission_id, question_id, page_id, bbox jsonb, detected_answer, raw_text, ocr_confidence, flags jsonb (`empty`, `multiple_marks`, `low_quality`…) |

### Бағалау
| Кесте | Негізгі өрістер |
|---|---|
| **ai_evaluations** | answer_id, provider, model, request_hash, response jsonb (валидацияланған), raw_response, schema_valid, latency_ms, error |
| **evaluations** | answer_id (unique), question_id, submission_id, method (`deterministic`/`ai`/`manual`), score, max_score, ai_suggested_score, confidence, status (`correct`/`incorrect`/`partial`/`doubtful`), review_status (`auto_approved`/`needs_review`/`medium`/`approved`/`overridden`), reasoning, error_category, expected_answer |
| **evaluation_items** | evaluation_id, descriptor_id, met, points_awarded, reason, confidence |
| **manual_reviews** | evaluation_id, reviewer_id, action (`accept`/`override`/`recheck`), old_score, new_score, comment |
| **results** | submission_id (unique), student_id, assessment_id, total_score, max_score, percent, level, feedback (AI/мұғалім), strengths jsonb, weaknesses jsonb, is_final, approved_by, approved_at |
| **analytics** | assessment_id, class_id, kind (`assessment_summary`/`question`/`descriptor`/`objective`/`errors`), payload jsonb, computed_at (кэш) |
| **audit_logs** | user_id, action, entity_type, entity_id, before jsonb, after jsonb, ip, user_agent, created_at |
| **app_settings** | key, value jsonb (AI/OCR провайдері, privacy, шектер) |

### Негізгі байланыстар
```
schools 1─* users, classes, students, subjects
classes 1─* students;  classes *─* teachers (class_teachers)
assessments 1─* assessment_versions 1─* questions 1─* descriptors
questions *─1 learning_objectives
assessments 1─* processing_jobs 1─* submission_pages
assessments 1─* submissions 1─* submission_pages 1─1 ocr_results
submissions 1─* answers 1─1 evaluations 1─* evaluation_items
evaluations 1─* manual_reviews;  answers 1─* ai_evaluations
submissions 1─1 results
```

## 5. Қауіпсіздік және құпиялылық
* **Auth**: JWT access (15 мин) + refresh (7 күн) — `HttpOnly; Secure; SameSite=Lax` cookie.
  Cookie-мен келген мутациялық сұраныстарға double-submit **CSRF** токен (`X-CSRF-Token`).
* **RBAC**: `require_roles(...)` + объект деңгейінде scope: мұғалім тек `class_teachers`-тағы
  сыныптарын немесе өзі құрған бағалауды көреді; school_admin — тек өз мектебін; оқушы — тек өзін.
* bcrypt пароль хэші; login, upload, AI үшін Redis rate limit; nginx деңгейінде де лимит.
* Файл: MIME (magic bytes) тексеру, кеңейтімдер whitelist, `MAX_UPLOAD_MB`, ClamAV (опция,
  `CLAMAV_HOST`), PDF құрылымын тексеру. Сақтау — AES-256-GCM (`STORAGE_ENCRYPTION_KEY`).
* SQL injection — тек ORM/параметрленген сұраныстар; XSS — React escaping + CSP заголовкалары.
* **Privacy (§37)**: `AI_SEND_STUDENT_NAMES=false` (әдепкі) — AI-ға тек жауап мәтіні кетеді;
  `AI_ENABLED`, `AI_SEND_IMAGES` баптаулары; оқушы деректерін экспорттау (JSON) және жою
  (`DELETE /api/students/{id}?purge=true`); `RETENTION_DAYS` бойынша скан файлдарын тазалау.
* Барлық маңызды әрекет `audit_logs`-қа жазылады.

## 6. Масштабтау (§47)
* Celery worker-лар көлденең масштабталады (`docker compose up --scale worker=4`);
  бір job ішінде беттер chunk-тап параллель өңделеді.
* 150 беттік PDF request ішінде өңделмейді: upload тек файлды сақтап, job құрады.
* Analytics нәтижесі `analytics` кестесінде кэштеледі, бекіту кезінде қайта есептеледі.

## 7. Интеграцияға дайындық (§59)
`services/integrations/base.py` — `GradebookAdapter` интерфейсі (`push_results`,
`sync_students`). Kundelik/BilimClass сияқты журналдар осы адаптер арқылы қосылады.
REST API толық OpenAPI құжатталған: `/api/docs`.
