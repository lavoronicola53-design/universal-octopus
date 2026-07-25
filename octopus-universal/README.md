# Octopus Universal — Fourier Fractal Prediction Engine

Octopus Universal — piattaforma web per l'analisi di segmenti di mercato ("frattali") **selezionati
manualmente dal trader** e la generazione di proiezioni future tramite
**Trasformata di Fourier reale** (`numpy.fft`), trasformazioni geometriche
opzionali e sintesi di vere candele OHLC.

> **Il software non riconosce pattern automaticamente e non usa AI per
> cercarli.** L'identificazione del frattale (primo click = inizio, secondo
> click = fine) resta interamente responsabilità del trader. La macchina si
> occupa solo di elaborare matematicamente il segmento selezionato.

---

## ⚠️ Avvertenza importante

Questo strumento esegue un'estrapolazione matematica (continuazione di
Fourier) di un segmento storico. **Non è un modello predittivo validato
statisticamente** e non costituisce consulenza finanziaria. La Trasformata di
Fourier assume implicitamente la periodicità del segnale: estrapolare oltre i
dati osservati equivale a ipotizzare che il pattern si ripeta ciclicamente.
Le metriche di scoring (`reconstruction_error`, `correlation`, ecc.) descrivono
quanto bene le componenti selezionate spiegano **il passato**, non
garantiscono l'accuratezza nel futuro. Il trading comporta il rischio di
perdita del capitale: usa questo software come strumento di analisi, non come
sistema di trading automatico.

---



## Dati di mercato reali

Il provider di default e' `real` (`DATA_PROVIDER=real`):
- **BTC/USDT, ETH/USDT** -> dati reali da **Binance** (API pubblica, nessuna key).
- **XAU/USD (oro), XAG/USD (argento)** -> dati reali da **Stooq** (CSV storico). Su timeframe giornaliero/settimanale sono dati reali completi; su timeframe intraday (Stooq non offre intraday gratis per i metalli) le candele vengono calibrate sull'ultimo prezzo reale disponibile.
- **Forex/indici** -> Stooq.
- Se una fonte e' momentaneamente irraggiungibile, il sistema ricade automaticamente su una serie sintetica calibrata **per quel singolo asset**, così il sito non si blocca mai.

Per forzare altri provider: `DATA_PROVIDER=synthetic` (tutto simulato), `yahoo`, `ccxt`, `csv`.

> Nota: alcuni ambienti di hosting o reti aziendali bloccano host esterni; se su Render vedi dati sintetici invece che reali, verifica che l'istanza abbia accesso in uscita verso `api.binance.com` e `stooq.com`.

## Architettura

```
┌─────────────────────┐        ┌──────────────────────────────────────┐
│      Frontend        │        │                Backend                │
│  Next.js + React +   │  HTTP  │            FastAPI (Python)           │
│  TypeScript + Tailwind│◄──────►│                                        │
│  lightweight-charts   │        │  ┌────────────────────────────────┐  │
└─────────────────────┘        │  │ services/                       │  │
                                 │  │  preprocessing.py   (pulizia,   │  │
                                 │  │                      detrend,   │  │
                                 │  │                      normalizz.) │  │
                                 │  │  fourier_engine.py  (FFT reale,  │  │
                                 │  │                      estrapol.)  │  │
                                 │  │  transforms.py      (flip,      │  │
                                 │  │                      inversione,│  │
                                 │  │                      scale, ecc)│  │
                                 │  │  scoring.py         (metriche + │  │
                                 │  │                      probabilità)│  │
                                 │  │  candle_synthesis.py(OHLC future)│  │
                                 │  │  scenario_engine.py (orchestratore)│ │
                                 │  │  data_provider.py   (feed dati) │  │
                                 │  └────────────────────────────────┘  │
                                 └──────────────┬─────────────────────────┘
                                                │
                       ┌────────────────────────┼───────────────────────┐
                       │                                                │
                ┌──────▼──────┐                                 ┌───────▼──────┐
                │  PostgreSQL  │                                 │     Redis     │
                │  (pattern    │                                 │   (caching)   │
                │  library,    │                                 └──────────────┘
                │  storico     │
                │  previsioni) │
                └──────────────┘
```

### Perché questa architettura

- **Separazione netta tra identificazione (umana) ed elaborazione
  (macchina)**: il backend non contiene nessun modulo di pattern-recognition
  o ML; riceve solo `start_timestamp`/`end_timestamp` scelti dall'utente.
- **`services/` è puro e testabile senza framework**: ogni modulo
  (`fourier_engine`, `transforms`, `scoring`, `candle_synthesis`) dipende solo
  da `numpy`/`scipy`/`pandas`, così la logica matematica è verificabile con
  test unitari indipendenti da FastAPI/DB (vedi `backend/tests/`).
- **`data_provider.py` è un'astrazione**: di default usa un generatore
  sintetico deterministico (nessuna rete richiesta, utile per demo/sviluppo
  offline); include anche un provider `ccxt` pronto per dati crypto live e un
  provider CSV per dataset importati manualmente (oro/argento/forex).

---

## Flusso operativo implementato

1. **Selezione mercato** — dropdown con gli strumenti supportati
   (`BTC/USDT`, `ETH/USDT`, `XAU/USD`, `XAG/USD`, `EUR/USD`, `GBP/USD`,
   `NAS100`, `SPX500`).
2. **Selezione timeframe** — `1m 5m 15m 30m 1h 4h 1d 1w`.
3. **Selezione temporale precisa** — due modalità equivalenti:
   click diretto sul grafico (primo click = inizio, secondo click = fine) o
   input `datetime-local` (anno/mese/giorno/ora/minuto).
4. **Parametri del motore** — Fourier Components (`10…1000`), Overton Window
   (`50…2000` barre), orizzonte di proiezione, numero di scenari (`20…100`),
   preprocessing (rimozione outlier, filtraggio).
5. **Trasformazioni geometriche opzionali** — flip verticale/orizzontale,
   centro di inversione, compressione/dilatazione temporale e di ampiezza,
   traslazione, rotazione di fase: ciascuna attivabile/disattivabile.
6. **PREDICT** → il backend esegue FFT, genera N scenari, li valuta (score +
   probabilità softmax) e trasforma lo scenario dominante in **vere candele
   OHLC future** (non una linea).
7. **Output** — Scenario A..E (+ extra) ordinati per probabilità, con
   metriche di qualità (correlazione, errore di ricostruzione, coerenza
   spettrale, continuità armonica, SNR, similarità frattale).
8. **Esportazione** — PNG, PDF (screenshot del grafico), CSV, JSON.

---

## Schema database (sintesi)

| Tabella                | Scopo                                                                 |
|-------------------------|------------------------------------------------------------------------|
| `pattern_definitions`   | Pattern Library / Book dei Frattali (Pattern 1..57 + personalizzati)   |
| `prediction_records`    | Ogni richiesta Predict: parametri usati, scenario dominante, esito reale registrato a posteriori |
| `scenario_records`      | Dettaglio di ogni scenario generato per una previsione (score, probabilità, candele sintetiche) |

Schema SQL di riferimento: [`backend/init_db.sql`](backend/init_db.sql)
(le tabelle vengono comunque create automaticamente all'avvio da SQLAlchemy).

Endpoint `GET /api/stats/accuracy` e `POST /api/stats/outcome` permettono di
costruire nel tempo l'accuracy storica reale (frequenza, % di successo,
errore medio) confrontando le proiezioni salvate con l'esito di mercato
effettivamente osservato — **nessun dato di accuratezza è precompilato o
inventato**: va costruito nel tempo con l'uso reale del sistema.

---

## Installazione (Docker — consigliato)

Requisiti: Docker e Docker Compose.

```bash
git clone <questo-repository>
cd pythagoras-clone
cp .env.example .env        # personalizza se necessario
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend (API + docs Swagger): http://localhost:8000/docs
- Al primo avvio, popola la Pattern Library (57 pattern) con:

```bash
docker compose exec backend python -m app.seed_patterns
```

## Installazione manuale (sviluppo locale senza Docker)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg2://pythagoras:pythagoras@localhost:5432/pythagoras
export DATA_PROVIDER=synthetic
uvicorn app.main:app --reload
```

Test della pipeline matematica (nessuna dipendenza da DB/rete):

```bash
cd backend
pytest tests/test_core_pipeline.py -v
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Collegare dati di mercato reali

Di default (`DATA_PROVIDER=synthetic`) il sistema genera serie storiche
sintetiche deterministiche, per poter usare e testare l'intera pipeline senza
credenziali né accesso di rete. Per dati reali:

- **Crypto (Binance e altri exchange)**: imposta `DATA_PROVIDER=ccxt`,
  `CCXT_EXCHANGE`, `CCXT_API_KEY`/`CCXT_API_SECRET` nel `.env`. Il provider è
  in `backend/app/services/data_provider.py` (`CCXTDataProvider`).
- **Oro / Argento / Forex**: se disponi di dataset storici CSV
  (colonne `timestamp,open,high,low,close,volume`), usa `DATA_PROVIDER=csv` e
  configura i percorsi in `Settings.csv_paths`.
- **cTrader / MetaTrader 5**: la sezione "Trading API" e i placeholder di
  navigazione nel frontend sono predisposti per un livello di integrazione
  successivo (bridge di esecuzione ordini); non incluso in questa consegna
  perché richiede credenziali broker specifiche.

---

## Struttura del repository

```
pythagoras-clone/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── init_db.sql
│   ├── app/
│   │   ├── main.py                 # entry point FastAPI
│   │   ├── config.py                # configurazione da env
│   │   ├── database.py              # SQLAlchemy engine/session
│   │   ├── models.py                 # modelli ORM
│   │   ├── schemas.py                # schemi Pydantic request/response
│   │   ├── cache.py                  # wrapper Redis
│   │   ├── seed_patterns.py          # popola i 57 pattern
│   │   ├── routers/
│   │   │   ├── market.py             # elenco mercati + OHLCV storico
│   │   │   ├── prediction.py         # endpoint /predict
│   │   │   └── patterns.py           # Pattern Library + statistiche
│   │   └── services/
│   │       ├── data_provider.py      # astrazione feed dati (synthetic/ccxt/csv)
│   │       ├── preprocessing.py      # pulizia/detrend/normalizzazione
│   │       ├── fourier_engine.py     # FFT reale + estrapolazione
│   │       ├── transforms.py         # trasformazioni geometriche opzionali
│   │       ├── scoring.py            # metriche + probabilità scenari
│   │       ├── candle_synthesis.py   # generazione vere candele OHLC future
│   │       └── scenario_engine.py    # orchestratore multi-scenario
│   └── tests/
│       └── test_core_pipeline.py     # test della pipeline matematica
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── next.config.js
    ├── tailwind.config.ts
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx                  # stato applicazione, orchestrazione
    │   └── globals.css
    ├── components/
    │   ├── TopNav.tsx
    │   ├── SpectrumTicker.tsx        # elemento ambient FFT nell'header
    │   ├── ControlPanel.tsx          # mercato/timeframe/parametri/trasform.
    │   ├── ChartPanel.tsx            # grafico + selezione manuale frattale
    │   └── ScenarioDashboard.tsx     # ranking scenari + export
    └── lib/
        ├── types.ts
        ├── api.ts
        ├── export.ts                 # export PNG/PDF/CSV/JSON
        └── datetime.ts
```

---

## Note su performance

La pipeline core (`scenario_engine.run_prediction`) è stata misurata
direttamente in questo repository con parametri al limite superiore delle
specifiche (`n_components=1000`, `n_scenarios=100`, `horizon=50`, storico di
200 candele): **~0.12 secondi**, ampiamente entro il target di 2 secondi. I
test corrispondenti sono in `backend/tests/test_core_pipeline.py`
(`test_run_prediction_respects_performance_target`). Il tempo di risposta
end-to-end percepito dall'utente include anche latenza di rete e query DB, non
misurate in questo benchmark isolato.

---

## Estensioni suggerite (non incluse in questa consegna)

- Autenticazione utenti e gestione abbonamenti/licenza.
- Bridge di esecuzione ordini reale verso cTrader/MT5.
- Migrazioni DB versionate con Alembic al posto di `create_all`.
- Job schedulato per popolare automaticamente `outcome_hit`/`outcome_error_pct`
  confrontando le proiezioni scadute con il prezzo di mercato realmente
  osservato.
