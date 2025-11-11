# Tehisintellekt.ee Q&A API

Veebipõhine vestluse API, mis vastab küsimustele tehisintellekt.ee veebilehe sisu põhjal, kasutades OpenAI GPT-4o-mini mudelit.


## Kiirkäivitus

### Eeldused
- Docker ja Docker Compose

### 1. Seadista API võti

Muuda .env.example fail .env failiks

Muuda .env failis OPENAI_API_KEY väärtust
OPENAI_API_KEY=your-actual-api-key-here

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

# **Täpsem kirjeldus:**

Rakendus kasutab startup-driven arhitektuuri, kus kogu sisu indekseerimine toimub üks kord FastAPI serveri käivitumisel. Lifespan context manager orkestreerib kolm kriitilist sammu: esiteks luuakse ContentIndexer OpenAI API võtmega, seejärel käivitatakse täielik saidi crawling ja indekseerimise protsess ning lõpuks initsialiseeritakse QueryProcessor, mis kasutab indekseeritud sisu.

ContentIndexer on põhiline data pipeline - see crawlib veebilehte, eraldab puhta teksti HTML-ist ja genereerib struktureeritud kokkuvõtteid kasutades LLM-e. See loob kaks põhilist data store'i: summaries (kokkuvõtted lehtede valimiseks) ja full_content (täielik tekst vastuste genereerimiseks). QueryProcessor kasutab seejärel neid store'e, et intelligentselt valida asjakohaseid lehti ja genereerida kontekstitundlikke vastuseid, kui kasutajad esitavad küsimusi läbi API endpoint'ide.

---


ContentIndexer orkestreerib kolmefaasilist sisu protsessimis pipeline'i:

Crawling Phase: Süsteem alustab kogu veebilehe crawlimisega, kasutades HTTP päringuid kõigi lehtede toomiseks ja linkide ekstraktimiseks. Iga leht salvestatakse Page objektina, mis sisaldab selle URL-i ja raw HTML sisu.

Content Extraction Phase: Toores HTML puhastatakse kasutades BeautifulSoupi, et eemaldada skriptid, stiilid ja navigatsioonielemendid. Ülejäänud tekst eraldatakse ja salvestatakse full_content dictionary'sse, säilitades täieliku loetava sisu hilisemaks päringu protsessimiseks.

Summarization Phase: Iga lehe sisu saadetakse OpenAI GPT-4o-mini mudelile struktureeritud kokkuvõtete genereerimiseks. LLM eraldab teemad, võtmepunktid, potentsiaalsed küsimused ja loob põhjaliku kokkuvõtte. See struktureeritud metadata salvestatakse summaries dictionary'sse ja kasutatakse intelligentse lehtede valimise jaoks päringute ajal.

Süsteem jälgib tokenite kasutust ja implementeerib error recovery retry loogikaga ebaõnnestunud API kutsete jaoks, tagades robustse töö isegi kui välised teenused on ebausaldusväärsed.

---

Kui kasutaja esitab küsimuse läbi FastAPI endpoint'i, järgib süsteem kolmeastmelist protsessi:

Page Selection: QueryProcessor kasutab LLM-i, et analüüsida kõiki indekseeritud lehekülje kokkuvõtteid ja valida kõige asjakohasemad URL-id konkreetsele küsimusele vastamiseks. See tagab, et ainult asjakohast sisu arvestatakse.

Context Building: Süsteem võtab valitud lehtedelt kogu teksti sisu ja konstrueerib põhjaliku konteksti stringi piirangute piires. See annab LLM-ile kogu vajaliku informatsiooni, austades samal ajal API piiranguid.

Answer Generation: Kasutades tekitatud konteksti, genereerib LLM vastuse kasutaja küsimusele, tsiteerides milliseid allikaid vastuses tegelikult kasutati. Süsteem jälgib tokenite kasutust ja tagastab struktureeritud metadata koos vastusega.
