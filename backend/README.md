# Backend (FastAPI)

Backend-С‡Р°СЃС‚СЊ РїСЂРѕРµРєС‚Р° LLM Data Analyst Lab.

## Р—Р°РїСѓСЃРє С‡РµСЂРµР· Docker Compose

РР· РєРѕСЂРЅСЏ СЂРµРїРѕР·РёС‚РѕСЂРёСЏ:

```bash
docker compose up --build
```

Swagger:

- http://localhost:8003/docs

## OpenRouter setup

1. РЎРѕР·РґР°Р№С‚Рµ `.env` РёР· `.env.example`
2. Р—Р°РїРѕР»РЅРёС‚Рµ:
- `OPENROUTER_API_KEY=your_key`
- `LLM_PROVIDER=openrouter`
- `OPENROUTER_MODEL=openai/gpt-oss-120b:free`
3. Р—Р°РїСѓСЃС‚РёС‚Рµ:
`docker compose up --build`

РќРµ РєРѕРјРјРёС‚СЊС‚Рµ `.env`.

## Lab 2: API Pipeline

Pipeline:

1. Р§РёС‚Р°РµС‚ Uber Customer Reviews Dataset (2024)
2. РќРѕСЂРјР°Р»РёР·СѓРµС‚ РІС…РѕРґРЅС‹Рµ РїРѕР»СЏ (РІРєР»СЋС‡Р°СЏ `score`)
3. Р¤РёР»СЊС‚СЂСѓРµС‚ РґР°РЅРЅС‹Рµ РїРѕ `min_score`/`max_score`
4. Р Р°Р·Р±РёРІР°РµС‚ РЅР° batch-С‹ (`batch_size`)
5. РћС‚РїСЂР°РІР»СЏРµС‚ batch РІ Ollama (`/api/generate`, `stream=false`, `format=json`)
6. Р’Р°Р»РёРґРёСЂСѓРµС‚ СЂРµР·СѓР»СЊС‚Р°С‚ С‡РµСЂРµР· Pydantic
7. РЎРѕС…СЂР°РЅСЏРµС‚ РѕР±С‰РёР№ СЂРµР·СѓР»СЊС‚Р°С‚ РІ `outputs/lab2_result.json`

## Lab 3: Universal Analytics Agent

Lab 3 РїРѕРґРґРµСЂР¶РёРІР°РµС‚ СѓРЅРёРІРµСЂСЃР°Р»СЊРЅС‹Р№ Р°РЅР°Р»РёР· CSV/XLSX Рё upload РґР°С‚Р°СЃРµС‚РѕРІ.

РљР»СЋС‡РµРІС‹Рµ РІРѕР·РјРѕР¶РЅРѕСЃС‚Рё:

- semantic column mapping (РІРєР»СЋС‡Р°СЏ `target_column`)
- user overrides РґР»СЏ СЂРѕР»РµР№ РєРѕР»РѕРЅРѕРє
- allowlisted tools
- СЂРµР¶РёРјС‹ `fast` / `balanced` / `full`
- trace Рё РѕС‚С‡С‘С‚С‹ РІ `outputs/lab3`
- session context РґР»СЏ follow-up РІРѕРїСЂРѕСЃРѕРІ (`outputs/lab3/sessions`)
- markdown-РѕС‚РІРµС‚С‹ РІ workspace UI
- РёСЃРїСЂР°РІР»РµРЅ warning pandas date parsing РІ column mapper
- РґРѕР±Р°РІР»РµРЅ СЂРµР¶РёРј `code_interpreter`

Р РµР¶РёРјС‹:

- `fast`: С‚РѕР»СЊРєРѕ heuristics + rule-based planner + РѕРґРёРЅ LLM-РІС‹Р·РѕРІ РґР»СЏ С„РёРЅР°Р»СЊРЅРѕРіРѕ РѕС‚РІРµС‚Р°
- `balanced`: LLM planner + С„РёРЅР°Р»СЊРЅС‹Р№ РѕС‚РІРµС‚ (+ critic РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)
- `full`: LLM-assisted mapping + LLM planner + С„РёРЅР°Р»СЊРЅС‹Р№ РѕС‚РІРµС‚ (+ critic РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)
- `code_interpreter`: LLM РіРµРЅРµСЂРёСЂСѓРµС‚ Python-РєРѕРґ, backend РІС‹РїРѕР»РЅСЏРµС‚ РµРіРѕ РІ sandbox loop, РјРѕРґРµР»СЊ РїСЂРѕРґРѕР»Р¶Р°РµС‚ Р°РЅР°Р»РёР· РїРѕ СЂРµР·СѓР»СЊС‚Р°С‚Р°Рј РІС‹РїРѕР»РЅРµРЅРёСЏ

Р’ РѕС‚РІРµС‚Рµ `/api/lab3/ask`:

- `analysis_mode`
- `llm_calls_count`
- `elapsed_seconds`
- `warnings`

Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅРѕ:

- critic С„РѕСЂРјРёСЂСѓРµС‚ JSON-РѕС‚Р·С‹РІ РЅР° СЂСѓСЃСЃРєРѕРј СЏР·С‹РєРµ;
- С„РёРЅР°Р»СЊРЅС‹Р№ РѕС‚РІРµС‚ Р°РіРµРЅС‚Р° РјРѕР¶РµС‚ Р±С‹С‚СЊ Markdown (critic РЅРµ С‚СЂРµР±СѓРµС‚ JSON РѕС‚ final answer);
- РµСЃР»Рё planner РІРµСЂРЅСѓР» РЅРµРІР°Р»РёРґРЅС‹Р№ JSON, backend РёСЃРїРѕР»СЊР·СѓРµС‚ rule-based fallback СЃ РєРѕСЂРѕС‚РєРёРј warning;
- tool `describe_categorical_columns` СЂР°Р·РґРµР»СЏРµС‚ РїСЂРёР·РЅР°РєРё РЅР° `categorical`, `ordinal_or_low_cardinality_numeric` Рё `numeric_count_like_columns`.

### Upload endpoint

- `POST /api/lab3/upload-dataset`
- Р¤РѕСЂРјР°С‚С‹: `.csv`, `.xlsx`, `.xls`
- РћРіСЂР°РЅРёС‡РµРЅРёРµ: 20 MB
- РЎРѕС…СЂР°РЅРµРЅРёРµ: `datasets/uploads`
- Р‘РµР·РѕРїР°СЃРЅР°СЏ РѕР±СЂР°Р±РѕС‚РєР° РёРјРµРЅРё С„Р°Р№Р»Р° (Р±РµР· path traversal)

### РћСЃРЅРѕРІРЅС‹Рµ endpoints Lab 3

- `GET /api/lab3/status`
- `GET /api/lab3/datasets`
- `POST /api/lab3/upload-dataset`
- `GET /api/lab3/profile?dataset_name=...`
- `POST /api/lab3/map-columns`
- `GET /api/lab3/tools`
- `POST /api/lab3/run-tool`
- `POST /api/lab3/ask`
- `GET /api/lab3/session?session_id=...`
- `POST /api/lab3/reset-session`
- `GET /api/lab3/result`
- `GET /api/lab3/download-report`

### РњРѕРґРµР»Рё

- `LAB3_PLANNER_MODEL=qwen3:8b`
- `LAB3_TOOL_CALLER_MODEL=qwen2.5-coder:7b`
- `LAB3_CRITIC_MODEL=deepseek-r1:8b`

РЈСЃС‚Р°РЅРѕРІРєР° РјРѕРґРµР»РµР№:

```bash
ollama pull qwen3:8b
ollama pull qwen2.5-coder:7b
ollama pull deepseek-r1:8b
```

### Р‘РµР·РѕРїР°СЃРЅРѕСЃС‚СЊ

- CSV-СЃС‚СЂРѕРєРё СЃС‡РёС‚Р°СЋС‚СЃСЏ С‚РѕР»СЊРєРѕ РґР°РЅРЅС‹РјРё, Р° РЅРµ РёРЅСЃС‚СЂСѓРєС†РёСЏРјРё
- Р’С‹РїРѕР»РЅСЏСЋС‚СЃСЏ С‚РѕР»СЊРєРѕ tools РёР· allowlist
- РќРµС‚ РїСЂРѕРёР·РІРѕР»СЊРЅРѕРіРѕ РІС‹РїРѕР»РЅРµРЅРёСЏ Python-РєРѕРґР° РёР· РѕС‚РІРµС‚Р° LLM
- РђСЂРіСѓРјРµРЅС‚С‹ tools РІР°Р»РёРґРёСЂСѓСЋС‚СЃСЏ
- Р§СѓРІСЃС‚РІРёС‚РµР»СЊРЅС‹Рµ РєРѕР»РѕРЅРєРё (`username`, `image`) РёСЃРєР»СЋС‡Р°СЋС‚СЃСЏ РёР· РєРѕРЅС‚РµРєСЃС‚Р° LLM
- Code sandbox Р±Р»РѕРєРёСЂСѓРµС‚ РѕРїР°СЃРЅС‹Рµ РёРјРїРѕСЂС‚С‹ Рё С‚РѕРєРµРЅС‹, РѕРіСЂР°РЅРёС‡РёРІР°РµС‚ timeout Рё Р°СЂС‚РµС„Р°РєС‚С‹ РІС‹РїРѕР»РЅРµРЅРёСЏ

## РџРµСЂРµРјРµРЅРЅС‹Рµ РѕРєСЂСѓР¶РµРЅРёСЏ

- `OLLAMA_BASE_URL` (РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ `http://host.docker.internal:11434`)
- `OLLAMA_MODEL` (РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ `qwen3:8b`)
- `LAB2_DATASET_FILENAME` (РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ `customer_reviews`)
- `LAB3_PLANNER_MODEL` (РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ `qwen3:8b`)
- `LAB3_TOOL_CALLER_MODEL` (РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ `qwen2.5-coder:7b`)
- `LAB3_CRITIC_MODEL` (РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ `deepseek-r1:8b`)
- `DATASETS_DIR`
- `OUTPUTS_DIR`

## Code Interpreter sandbox contract

- DataFrame `df` загружается backend-ом до запуска кода модели.
- Модель не должна читать CSV/XLSX вручную и не должна работать с файловой системой напрямую.
- Запрещены опасные импорты и операции (`os`, `subprocess`, `open`, `eval`, `exec`, `pd.read_csv`, `pd.read_excel`).
- Ошибки/блокировки возвращаются модели как observation, чтобы она переписала код и продолжила анализ безопасно.
