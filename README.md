# Tehisintellekt.ee Q&A API

Veebipõhine vestluse API, mis vastab küsimustele tehisintellekt.ee veebilehe sisu põhjal, kasutades OpenAI GPT-4o-mini mudelit.


## Kiirkäivitus

### Eeldused
- Docker ja Docker Compose

### 1. Seadista API võti

Muuda .env.example fail .env failiks

Muuda .env failis OPENAI_API_KEY väärtust
# OPENAI_API_KEY=your-actual-api-key-here

### 2. Käivitamine Dockeriga

```bash
# Ehita ja käivita konteiner
docker-compose up --build

# API on kättesaadav: http://localhost:8000
```

Rakenduse käivitumine võtab 2-3 minutit indekseerimise tõttu.

### API kasutamine

```bash
# Health check
curl http://localhost:8000/health

# Indekseeritud lehed
curl http://localhost:8000/source_info

# Esita küsimus
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Mis on tehisintellekt?"}'
```
Browseris saab http://localhost:8000/docs jooksutada API käske.

## Rakenduse tööpõhimõte

### Käivitusprotsess (Indexing)

```
[Crawling] → [Text Cleaning] → [LLM Summarization] → [Storage]
```

1. **Web Crawling**: Crawl-ib tehisintellekt.ee ja alamlehed
   - Järgib sama domeeni linke
   - Austab max_pages piirangut

2. **Text Cleaning**: Eraldab HTML-ist olulise teksti
   - Eemaldab skriptid, stiilid, navigatsioon
   - Säilitab põhisisu

3. **LLM Summarization**: Genereerib kokkuvõtte igale lehele
   - Tuvastab teemad
   - Eraldab võtmepunktid
   - Loob potentsiaalsed küsimused

4. **Storage**: Salvestab lühimälusse kokkuvõtted ja täistekstid

### Päringute töötlemine

```
[Query] → [LLM Page Selection] → [Context Building] → [Answer Generation]
```

1. **LLM Page Selection**: LLM valib relevantsed lehed
2. **Context Building**: Kogub valitud lehtede sisu (max 200k chars)
3. **Answer Generation**: Genereerib vastuse konteksti põhjal

## Arhitektuur

### Projektstruktuur

```
.
├── app.py              # FastAPI rakendus
├── crawler.py          # Web crawling
├── indexer.py          # Sisu indekseerimine
├── processor.py        # Päringute töötlemine
├── models.py           # Pydantic mudelid
├── requirements.txt    
├── Dockerfile
├── docker-compose.yml
├── pytest.ini
├── tests/              # Ühiktestid
└── README.md
```

### LLM-põhine kahe astmeline lahendus

Käivitamisel leheküljed crawlitakse ja sisu indekseeritakse kokkuvõtetega
1. Päringutel LLM valib välja kokkuvõtete põhjal kõige sobivamad lehed edasiseks analüüsiks
2. LLM genereerib vastuse ette valitud konteksti põhjal

Selline lähenemine optimeerib tokenite kasutamist, samas tagab täpsust küsimustele vastates.
Ühe astmeline LLM-i lahendus kasutaks liiga palju tokeneid ja täpsus oleks nõrgenenud liiga pika konteksti tõttu.
RAG põhisel lahendusel oleksid semantilised probleemid, küsimus ja õige vastus ei pruugi olla vektor andmebaasis üksteise lähedal.


## Teekide valikud

### Core
- **FastAPI**: Kiire, async, automaatne dokumentatsioon, type-safe
- **Pydantic**: Type-safe valideerimine, FastAPI integratsioon
- **Uvicorn**: ASGI server

### HTTP & Web
- **httpx**: Async HTTP klient
- **BeautifulSoup4**: Parim HTML parsing, robustne

### AI
- **OpenAI**: Ametlik library, structured outputs, token tracking

### Testing
- **pytest**: Standard framework, fixtures, parallel execution
- **pytest-asyncio**: Async testide support
- **pytest-cov**: Coverage reports
- **httpx-mock**: HTTP mokimine testides

## Production Ready täiendused

- Püsiv server luua andmebaasiga, mis hoiab indekseeritud andmeid, et ei peaks seda uuesti aktiveerimisel tegema.

- Backup andmebaas.

- Perioodiliselt uuesti indekseerida kui toimuvad lehekülje uuendused.

- Rate limiting, vältida API väär-/liigkasutamist.

- Serveri poolne monitoorimine

- API võtme valideerimine

## CI/CD Pipeline

### Pipeline etapid

1. **Test**: Linting, unit tests, coverage
2. **Build**: Docker image build, scanning, push
3. **Deploy**: Staging → Integration tests → Production
4. **Post-Deploy**: Health checks, metrics, rollback

## Azure pilve püstitamine

### Arhitektuur

```
[Azure Front Door] 
    ↓
[App Service] → [Azure OpenAI]
    ↓
[Redis Cache]
    ↓
[PostgreSQL]
    ↓
[Blob Storage]
```

## Testimine

```bash
# Kõik testid
pytest

```

### Testi struktuur
- `test_crawler.py` - Crawlimine ja sisu puhastus
- `test_indexer.py` - Indekseerimine ja kokkuvõtete genereerimine
- `test_processor.py` - Päringute töötlemine
- `test_app.py` - FastAPI endpoints
