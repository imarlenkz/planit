# Planit — БЖБ / ТЖБ / АБ жұмыстарын AI арқылы тексеру

Planit мұғалімге қағаз жүзіндегі бөлім бойынша жиынтық бағалау (БЖБ), тоқсандық жиынтық бағалау (ТЖБ) және аралық бағалау (АБ) жұмыстарын сканерлеп, автоматты түрде тексеруге көмектеседі:

**скан (PDF / фото) → алдын ала өңдеу → OCR (kk/ru/en) → тапсырмалар мен оқушыны анықтау → жауаптарды шығару → бағалау кілтімен / дескрипторлармен салыстыру → AI арқылы ашық жауаптарды бағалау → сенімділік → мұғалімнің тексеруі → нәтижелер, талдау, Excel / PDF / Word есептері.**

AI тек ұсыныс береді: соңғы шешімді әрқашан мұғалім қабылдайды (human-in-the-loop). Баллды AI емес, жеке `ScoringEngine` есептейді, ал AI жауаптары JSON Schema бойынша тексеріледі.

| Dashboard | Мұғалімнің тексеруі |
|---|---|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Review](docs/screenshots/review.png) |
| **Сканерлеу** | **Талдау** |
| ![Scan](docs/screenshots/scan.png) | ![Analytics](docs/screenshots/analytics.png) |

Архитектура және деректер қорының схемасы: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). API құжаттамасы (OpenAPI): іске қосылған жүйеде `/api/docs` (Swagger) және `/api/openapi.json`.

## Жылдам бастау (демо)

```bash
cp .env.example .env
sed -i 's/^SEED_DEMO=.*/SEED_DEMO=true/; s/^DEMO_AUTORUN=.*/DEMO_AUTORUN=true/' .env   # тек сынап көру үшін
docker compose up -d --build
# http://localhost  →  teacher@planit.kz / demo12345
```

`SEED_DEMO=true` болғанда бірінші іске қосылғанда демо мектеп құрылады (5А, 5Б, 6А, 7А, 8Б сыныптары, 56 оқушы, Математика БЖБ, Қазақ тілі БЖБ, Жаратылыстану ТЖБ, Ағылшын тілі АБ) және `DEMO_AUTORUN=true` болса, 5А сыныбының Математика БЖБ-сының нақты сканға ұқсас 52 беттік PDF-і толық pipeline арқылы өтеді (≈1 минут). Жүйе ашылғанда нәтижелер тексеруге дайын тұрады.

| Рөл | Email | Құпиясөз |
|---|---|---|
| Мұғалім | `teacher@planit.kz` | `demo12345` |
| Екінші мұғалім | `teacher2@planit.kz` | `demo12345` |
| Мектеп әкімшілігі | `director@planit.kz` | `demo12345` |
| Жүйе әкімшісі | `admin@planit.kz` | `demo12345` |
| Оқушы | `student@planit.kz` | `demo12345` |

Демо сценарий: **БЖБ → «Математика БЖБ №2» → «Сканерлеу» → «Демо сканмен тексеру»** (немесе «Демо PDF жүктеп алу» арқылы файлды алып, қолмен жүктеңіз) → прогресс → «Тексеруге өту» → күмәнді жауаптарды қарау → «Барлық сенімді нәтижелерді бекіту» → «Есептер» → Excel / PDF / Word.

---

## 1. Installation

Талаптар:

* Docker 24+ және Docker Compose v2.24+ (production overlay `!reset` синтаксисін қолданады), **немесе**
* жергілікті әзірлеу үшін: Python 3.12, Node.js 20, PostgreSQL 16, Redis 7, Tesseract 5 (`kaz`, `rus`, `eng` тілдерімен), `libzbar0`, `libmagic1`, DejaVu қаріптері.

```bash
git clone https://github.com/imarlenkz/planit.git
cd planit
cp .env.example .env
```

Құрылым:

```
backend/    FastAPI, SQLAlchemy, Alembic, Celery, OCR/AI/scoring сервистері, тесттер
frontend/   Next.js 15 (App Router), TypeScript, Tailwind, shadcn-стиліндегі компоненттер, Playwright E2E
nginx/      reverse proxy (HTTP және HTTPS конфигурациялары)
deploy/     сервердегі deploy скрипті
docs/       архитектура, скриншоттар
```

## 2. Environment variables

Барлық айнымалылар `.env.example` файлында түсіндірмесімен берілген. Ең маңыздылары:

| Айнымалы | Әдепкі | Сипаттамасы |
|---|---|---|
| `ENVIRONMENT` | `development` | `development` / `staging` / `production` |
| `SECRET_KEY` | — | JWT қолтаңбасы үшін ұзын кездейсоқ жол (production-да міндетті түрде өзгертіңіз) |
| `FRONTEND_ORIGINS` | `http://localhost` | CORS үшін рұқсат етілген origin-дер (үтір арқылы) |
| `COOKIE_SECURE` | `false` | HTTPS артында `true` |
| `POSTGRES_USER/PASSWORD/DB` | `planit` | Compose `DATABASE_URL`-ді осылардан құрастырады |
| `SEED_DEMO` | `false` | Демо мектепті құру (тек сынап көру үшін) |
| `DEMO_AUTORUN` | `false` | Демо сканды бірінші іске қосуда автоматты тексеру |
| `STORAGE_BACKEND` | `local` | `local` немесе `s3` (MinIO / AWS S3) |
| `STORAGE_ENCRYPTION_KEY` | бос | Файлдарды AES-GCM арқылы шифрлау кілті (base64, 32 байт) |
| `RETENTION_DAYS` | `365` | Скан файлдарын сақтау мерзімі; мерзімі өткендерін Celery beat жояды |
| `MAX_UPLOAD_MB` | `100` | Бір файлдың максималды өлшемі |
| `CLAMAV_HOST` | бос | Жүктелген файлдарды вирусқа тексеру (ClamAV) |
| `OCR_PROVIDER`, `OCR_FALLBACKS` | `tesseract` | OCR провайдері және резервтік тізбек |
| `AI_PROVIDER` | `local` | `local` / `openai` / `anthropic` |
| `CONFIDENCE_HIGH` / `CONFIDENCE_MEDIUM` | `95` / `80` | Сенімділік шектері (%) |
| `AUTO_APPROVE_HIGH_CONFIDENCE` | `true` | Жоғары сенімді жауаптарды автоматты бекіту |

Кейбір параметрлерді (AI/OCR провайдері, шектер, құпиялылық, сақтау мерзімі) әкімші **Баптаулар → AI және OCR** бетінен жүйені қайта іске қоспай өзгерте алады.

## 3. Database setup

PostgreSQL 16 қолданылады, схема Alembic миграцияларымен басқарылады (27 кесте).

```bash
cd backend
export DATABASE_URL=postgresql+psycopg2://planit:planit@localhost:5432/planit
alembic upgrade head          # схеманы құру / жаңарту
python -m app.seed            # демо деректер (қайта іске қосқанда өткізіп жібереді)
python -m app.seed --run-demo # + демо сканды pipeline арқылы өткізу
```

Docker-де `backend` контейнері іске қосылғанда `alembic upgrade head` автоматты түрде орындалады. Жаңа миграция: `alembic revision --autogenerate -m "..."`, тексеру: `alembic check`.

## 4. OCR configuration

* **Tesseract** (әдепкі, офлайн): `OCR_LANGUAGES=kaz+rus+eng`. Docker образында `tesseract-ocr-kaz/rus/eng` орнатылған. Сандық, формулалық, сәйкестендіру және кесте жауаптары үшін `eng` моделі қолданылады.
* **Google Vision**: `OCR_PROVIDER=google`, `GOOGLE_VISION_API_KEY=...`.
* **Azure AI Vision**: `OCR_PROVIDER=azure`, `AZURE_VISION_ENDPOINT=...`, `AZURE_VISION_KEY=...`.
* Резервтік тізбек: `OCR_FALLBACKS=google,tesseract` — бірінші провайдер қате берсе немесе сенімділігі төмен болса, келесісі қолданылады.

Ең жоғары дәлдік үшін **«Скан шаблоны (QR)»** парақтарын басып шығарыңыз: әр парақта QR-код (бағалау, нұсқа, оқушы, бет), 4 бұрыштық маркер және жауап аймақтары бар. Pipeline парақты маркерлер бойынша түзетеді, бұрылысты/қисаюды/көлеңкені жояды, OMR арқылы A/B/C/D белгілерін оқиды және қолжазба аймақтарын OCR-ға жібереді. QR болмаса, оқушы аты-жөні OCR арқылы сынып тізімімен салыстырылады, табылмаса — «Оқушыны таңдаңыз».

## 5. AI configuration

* `AI_PROVIDER=local` — сыртқы сервиссіз, ережеге негізделген семантикалық бағалау (кілт сөздер, ұғымдар, дескрипторлар). Сенімділігі әдейі шектелген (≤ 92%), сондықтан күмәнді жауаптар мұғалімге түседі.
* `AI_PROVIDER=openai` — `OPENAI_API_KEY`, `OPENAI_MODEL` (әдепкі `gpt-4o-mini`), JSON Schema форматындағы жауап.
* `AI_PROVIDER=anthropic` — `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` (әдепкі `claude-sonnet-5-5`), құрылымдық tool use арқылы.

Қорғаныс: AI жауабы JSON Schema бойынша валидацияланады; уақыт шегі асса немесе схема бұзылса жауап **Manual Review Required** болады; AI ұсынған балл мен дескрипторлар сомасы сәйкес келмесе сенімділік төмендейді. `AI_SEND_STUDENT_NAMES=false` және `AI_SEND_IMAGES=false` әдепкі бойынша оқушының дербес деректері AI провайдеріне жіберілмейді.

## 6. Local development

```bash
# 1) инфрақұрылым
docker compose up -d postgres redis      # немесе жергілікті PostgreSQL/Redis

# 2) backend
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg2://planit:planit@localhost:5432/planit QUEUE_MODE=thread SEED_DEMO=true
alembic upgrade head && python -m app.seed
uvicorn app.main:app --reload --port 8000

# 3) frontend
cd ../frontend
npm ci
npm run dev        # http://localhost:3000, /api сұраулары localhost:8000-ға проксиленеді
```

`QUEUE_MODE=thread` — Celery-сіз, өңдеу API процесінің ішінде фондық ағында орындалады (әзірлеуге ыңғайлы). Production-да `QUEUE_MODE=celery` және жеке `worker` қолданылады.

## 7. Docker deployment

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
docker compose logs -f backend worker
```

Сервистер: `nginx` (80 порт), `frontend` (Next.js standalone), `backend` (FastAPI + Alembic), `worker` (Celery: OCR/AI pipeline), `beat` (ескі файлдарды тазалау), `postgres`, `redis`. Қосымша профильдер:

```bash
docker compose --profile clamav up -d   # + ClamAV, .env: CLAMAV_HOST=clamav
docker compose --profile s3 up -d       # + MinIO, .env: STORAGE_BACKEND=s3, S3_ENDPOINT_URL=http://minio:9000
```

Nginx `/api/ws/` арқылы WebSocket (өңдеу прогресі) проксилейді және 200 МБ-қа дейінгі жүктеулерге рұқсат береді. Docker Hub қолжетімсіз ортада базалық образдарды `--build-arg PYTHON_IMAGE=... NODE_IMAGE=...` арқылы ауыстыруға болады.

## 8. Production deployment

### Бір VPS-ке бір командамен (HTTPS-пен)

Доменнің A жазбасын серверге бағыттаңыз, 80/443 порттарын ашыңыз (сервер: Ubuntu 22.04+/Debian 12, ≥ 2 ядро, ≥ 4 ГБ RAM), содан кейін серверде:

```bash
curl -fsSL https://raw.githubusercontent.com/imarlenkz/planit/main/deploy/install.sh \
  | sudo DOMAIN=checker.imarlen.kz EMAIL=you@example.com bash
```

Скрипт Docker-ді орнатады, кодты `/opt/planit`-ке алады, құпиялары генерацияланған `.env` жасайды, Let's Encrypt сертификатын алады (автоматты жаңартумен), образдарды серверде жинап, стекті іске қосады. Жаңарту үшін сол команданы қайта іске қосыңыз — деректер, `.env` және сертификаттар сақталады. Әдепкі бойынша демо деректер жоқ: бұрын жасалған демо мектеп пен демо аккаунттар жойылады (`python -m app.seed purge`), ал әкімші болмаса `ADMIN_EMAIL` (әдепкі `EMAIL`) атымен бірінші әкімші жасалып, құпиясөзі экранға шығады. Сынап көру үшін ғана: `DEMO=true`.

### iMARLEN ID арқылы кіру (SSO)

Planit id.imarlen.kz-ке стандартты OIDC клиенті ретінде қосылады (authorization code + PKCE). iMARLEN ID серверінде (`/opt/iid`) клиентті тіркеңіз:

```bash
cd /opt/iid && docker compose exec id node --disable-warning=ExperimentalWarning src/cli.mjs \
  client planit "Planit" https://checker.imarlen.kz/api/auth/sso/callback https://checker.imarlen.kz/ https://checker.imarlen.kz/login
```

Шыққан `client_secret`-ті орнату командасына беріңіз (ол `.env`-ке жазылады):

```bash
curl -fsSL https://raw.githubusercontent.com/imarlenkz/planit/main/deploy/install.sh \
  | sudo DOMAIN=checker.imarlen.kz IID_CLIENT_ID=planit IID_CLIENT_SECRET=... bash
```

Пайдаланушы `sub` бойынша табылады, болмаса сол email-мен бар аккаунт бір рет байланыстырылады, болмаса жаңа аккаунт жасалады. Рөлдер: student → оқушы, teacher → мұғалім, school_admin → мектеп әкімшісі, platform_owner → әкімші; ата-ана кіре алмайды. Мектеп `Баптаулар → Профиль`-дегі «iMARLEN ID мектеп коды» бойынша сәйкестендіріледі (код табылмаса, `IID_AUTO_CREATE_SCHOOL=true` кезінде мектеп автоматты жасалады). Оқушы сыныбы мен аты-жөні бойынша тізімдегі жазбасына қосылады. Email/құпиясөзбен кіру қатар жұмыс істей береді.

### Registry образдары арқылы (CI/CD)

1. Серверде `/opt/planit` каталогын жасап, `.env` файлын толтырыңыз: `ENVIRONMENT=production`, күшті `SECRET_KEY`, `COOKIE_SECURE=true`, `FRONTEND_ORIGINS=https://your.domain`, `SEED_DEMO=false`, `STORAGE_ENCRYPTION_KEY`, дерекқор құпиясөздері.
2. TLS сертификаттарын `nginx/tls/fullchain.pem` және `nginx/tls/privkey.pem` ретінде орналастырыңыз.
3. Іске қосу:

```bash
export IMAGE_PREFIX=ghcr.io/imarlenkz/planit IMAGE_TAG=1.0.0
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend migrate
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**CI/CD** (`.github/workflows/ci.yml`): әр push/PR-да backend lint + тесттер (Tesseract-пен), frontend lint + typecheck + build, Docker образдарын жинау, docker compose стегінде Playwright E2E. Push кезінде образдар `ghcr.io/<owner>/planit/{backend,frontend}`-ке жіберіледі және ортаға deploy жасалады:

| Branch / tag | GitHub Environment |
|---|---|
| `develop` | `development` |
| `main` | `staging` |
| `v*` тегі | `production` |

Әр environment-ке `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` secrets (және қажет болса `DEPLOY_PATH` variable) қосыңыз; production үшін GitHub-та қолмен бекітуді (required reviewers) қосу ұсынылады. Secrets болмаса deploy қадамы өткізіліп жіберіледі.

Резервтік көшірме: `docker compose exec postgres pg_dump -U planit planit > backup.sql` және `storage` томы.

## 9. Testing

```bash
# backend: unit (scoring, нормализация, AI схемасы, парсинг) + integration (upload → OCR → бағалау → review → export)
cd backend && pytest -q

# frontend
cd frontend && npm run lint && npm run typecheck && npm run build

# E2E (жұмыс істеп тұрған стекке қарсы): мұғалім кіреді → БЖБ құрады → кілт → PDF жүктейді → тексереді → экспорттайды
cd frontend && npx playwright install chromium
BASE_URL=http://localhost npm run test:e2e
```

## 10. Troubleshooting

| Белгі | Шешім |
|---|---|
| `Вирусқа тексеру сервисі қолжетімсіз` | `CLAMAV_HOST` орнатылған, бірақ ClamAV іске қосылмаған. `--profile clamav` қосыңыз немесе айнымалыны бос қалдырыңыз. |
| Worker қайта-қайта қайта іске қосылады | `docker compose logs worker`. Redis қолжетімді екенін тексеріңіз; `requirements.txt` ішіндегі `kombu`/`redis` нұсқалары бекітілген. |
| Өңдеу «queued» күйінде қалады | `QUEUE_MODE=celery` болса `worker` жұмыс істеп тұрғанын тексеріңіз. Әзірлеуде `QUEUE_MODE=thread` қолданыңыз. |
| OCR қазақ әріптерін танымайды | `tesseract --list-langs` ішінде `kaz` бар-жоғын тексеріңіз (`apt install tesseract-ocr-kaz`). Сканды 200 dpi-ден төмен емес етіп түсіріңіз. |
| Оқушы анықталмады | QR шаблонын қолданыңыз немесе тексеру бетінде «Оқушыны таңдаңыз» тізімінен таңдаңыз. Сынып тізіміндегі аты-жөні парақтағымен сәйкес болуы керек. |
| Жауаптардың көбі «Тексеру қажет» | Скан сапасын жақсартыңыз (жарық, көлеңкесіз, парақ толық кадрда), немесе Баптауларда сенімділік шектерін реттеңіз. |
| Бірінші іске қосу баяу | `DEMO_AUTORUN=true` демо сканды өңдейді (≈1 мин). `docker compose logs -f backend`. |
| 401 / CSRF қатесі | Cookie-лер бұғатталмағанын тексеріңіз; HTTP арқылы ашқанда `COOKIE_SECURE=false` болуы керек. |
| `413 Request Entity Too Large` | `nginx.conf` ішіндегі `client_max_body_size` және `.env` ішіндегі `MAX_UPLOAD_MB` мәндерін арттырыңыз. |
| AI провайдері жауап бермейді | API кілтін тексеріңіз; уақыт шегінде жауап болмаса жүйе жауапты автоматты түрде қолмен тексеруге жібереді. |

## Лицензия және құпиялылық

Оқушы деректері тек мектеп ішінде қолжетімді (RBAC: admin, school_admin, teacher, student). Әр бағалау өзгерісі audit log-қа жазылады. Оқушы деректерін экспорттау және толық жою (right to erasure) **Оқушылар** бетінде қолжетімді.
