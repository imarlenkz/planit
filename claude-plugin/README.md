# iMARLEN Claude плагині

Claude-ты барлық сайттарыңызға қосатын бір сервис (`ai.imarlen.kz`). Ол екі жұмыс атқарады:

1. **Claude → сайттар (MCP).** claude.ai, Claude Desktop немесе Claude Code ішінде Claude сайттарыңыздың беттерін оқиды және Planit API арқылы жұмыстарды, нәтижелерді, аналитиканы, тексеру кезегін көреді. Деректі өзгертетін әрекеттерді (мысалы, сенімді жауаптарды бекіту) тек сіздің рұқсатыңызбен жасайды.
2. **Сайттағы чат-көмекші (виджет).** Кез келген сайтқа бір `<script>` жолын қоссаңыз, оң жақ төменгі бұрышта Claude көмекшісі пайда болады. Ол келушілерге сайт бойынша жауап береді және тек сол сайттың ашық беттерін оқи алады.

Барлық сайттардың тізімі мен құралдары бір файлда — `sites.yaml`.

```
claude-plugin/
├── server/               FastAPI + MCP сервер, Claude API, виджет
│   ├── app/              config.py, connectors.py, mcp_app.py, chat.py, main.py
│   ├── widget/widget.js  сайтқа қосылатын скрипт
│   ├── sites.example.yaml
│   └── tests/
├── plugin/               Claude Code плагині (.mcp.json + skill)
├── deploy/ai.imarlen.kz.conf   host nginx конфигі
├── docker-compose.yml
└── .env.example
```

## 1. Серверге орнату (VPS)

1. DNS: `ai.imarlen.kz` үшін `A` жазбасы → `92.38.49.148`.
2. Кодты алып, баптаңыз:
   ```bash
   cd /opt && git clone https://github.com/imarlenkz/planit.git imarlen-claude
   cd /opt/imarlen-claude/claude-plugin      # жаңарту: git pull && docker compose up -d --build
   cp .env.example .env && cp server/sites.example.yaml sites.yaml
   echo "MCP_TOKENS=$(openssl rand -hex 32)" >> .env   # бұл токенді сақтап қойыңыз
   nano .env        # ANTHROPIC_API_KEY, PLANIT_BOT_EMAIL, PLANIT_BOT_PASSWORD
   nano sites.yaml  # сайттардың мекенжайларын тексеріңіз
   docker compose up -d --build
   curl -s http://127.0.0.1:8090/health
   ```
3. nginx және сертификат:
   ```bash
   cp deploy/ai.imarlen.kz.conf /etc/nginx/sites-available/ai.imarlen.kz
   ln -s /etc/nginx/sites-available/ai.imarlen.kz /etc/nginx/sites-enabled/
   certbot certonly --nginx -d ai.imarlen.kz && nginx -t && systemctl reload nginx
   ```
4. **Planit бот аккаунты.** Planit-те admin ретінде жаңа `teacher` (немесе тек оқу керек болса — director) пайдаланушысын жасаңыз, email/құпиясөзін `.env`-ке жазыңыз. Claude Planit-ті осы аккаунт көретіндей ғана көреді.

`sites.yaml` өзгерсе: `docker compose restart claude`.

## 2. Claude-қа қосу

**claude.ai (веб / мобильді / Desktop).** Settings → Connectors → *Add custom connector*:
- Name: `iMARLEN`
- URL: `https://ai.imarlen.kz/mcp/<MCP_TOKEN>`

Токен URL ішінде тұр, сондықтан бұл сілтемені ешкімге бермеңіз. Ауыстыру керек болса, `.env` ішіндегі `MCP_TOKENS` мәнін өзгертіп, контейнерді қайта іске қосыңыз.

**Claude Code (плагин).**
```bash
export IMARLEN_MCP_TOKEN=<MCP_TOKEN>      # ~/.bashrc немесе ~/.zshrc ішіне
claude
/plugin marketplace add imarlenkz/planit
/plugin install imarlen-sites@imarlen
```
Немесе плагинсіз: `claude mcp add --transport http imarlen https://ai.imarlen.kz/mcp --header "Authorization: Bearer <MCP_TOKEN>"`.

Тексеру: «Planit-те тексеруді күтіп тұрған жұмыстар қанша?» немесе «ustaz.imarlen.kz басты бетінде не жазылған?» деп сұраңыз.

## 3. Сайтқа чат-виджет қосу

Сайттың HTML-іне, `</body>` алдына:

```html
<script src="https://ai.imarlen.kz/widget.js" data-site="planit" defer></script>
```

`data-site` — `sites.yaml` ішіндегі сайт кілті. Сол сайттың домені `widget.origins` тізімінде болуы керек, әйтпесе сервер сұрауды қабылдамайды. Next.js-те (Planit frontend) `app/layout.tsx` ішіне `<Script src="https://ai.imarlen.kz/widget.js" data-site="planit" strategy="afterInteractive" />` қойыңыз.

Әр IP-ге лимит бар (`CHAT_PER_MINUTE`, `CHAT_PER_DAY`), себебі шығынды сіздің API кілтіңіз көтереді.

## 4. Жаңа сайт немесе құрал қосу

`sites.yaml` ішінде:

```yaml
sites:
  ustaz:
    name: Ustaz
    base_url: https://ustaz.imarlen.kz
    auth: {type: bearer, token: "${USTAZ_API_TOKEN}"}   # none | bearer | header | login
    tools:
      - name: list_courses
        description: Курстар тізімі
        path: /api/courses
        params:
          q: {type: string, description: Іздеу}
      - name: get_course
        path: /api/courses/{course_id}      # {..} мәні URL-кодталып қойылады
      - name: publish_course
        method: POST                         # GET емес = деректі өзгертеді
        path: /api/courses/{course_id}/publish
    widget:
      enabled: true
      origins: [https://ustaz.imarlen.kz]
```

- `GET` құралдары тек оқиды. `POST/PUT/PATCH/DELETE` құралдары MCP-де «destructive» деп белгіленеді, Claude оларды шақырмас бұрын сізден сұрайды.
- Виджетке тек `widget: true` деп белгіленген **GET** құралдары және `fetch_page` беріледі. Өзгертетін құралдар виджетке ешқашан берілмейді.
- Құрал аты: `<сайт>__<құрал>` (мысалы `ustaz__list_courses`).

Құралдар тізімін тексеру: `curl -H "Authorization: Bearer <MCP_TOKEN>" https://ai.imarlen.kz/v1/tools`.

## Қауіпсіздік

- MCP тек `MCP_TOKENS` ішіндегі токенмен ашылады (тұрақты уақытта салыстырылады).
- `fetch_page` тек сол сайттың доменіндегі беттерді оқиды, басқа доменге шыға алмайды.
- Чат `Origin` тақырыбын тексереді: виджетті тек `widget.origins` тізіміндегі сайттар қолдана алады.
- Құпиялар тек `.env`-те; `sites.yaml` ішінде `${VAR}` түрінде сілтеме жасалады. Екеуі де `.gitignore`-да.

## Әзірлеушіге

```bash
cd claude-plugin/server
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
SITES_FILE=sites.example.yaml MCP_TOKENS=dev ANTHROPIC_API_KEY=... uvicorn --factory app.main:create_app --port 8090
```

Модель: `claude-opus-5-5` (adaptive thinking, `effort: medium`, бас тарту кезінде `fallbacks: default`). `.env` арқылы өзгертуге болады.
