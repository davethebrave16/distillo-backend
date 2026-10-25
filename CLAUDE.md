# distillo-backend

Backend Python (Firebase Functions 2nd gen) di Distillo. **Documento master**:
`/Users/dave.rain/Workspace/distillo/docs/ARCHITECTURE.md` (in italiano, fonte di verità: se c'è
conflitto, fermarsi e chiedere). Architettura di questo repo: `docs/ARCHITECTURE.md`.

## Comandi (da `functions/`, venv in `functions/venv`)
- `venv/bin/ruff check .` · `venv/bin/ruff format --check .` · `venv/bin/mypy distillo main.py` · `venv/bin/pytest`
- Dalla root: `./setup.sh [--reauth]` (venv, file locali dagli esempi senza sovrascrivere, autorizzazione Gmail), `./rundev.sh [--seed]`, `./ingest-local.sh [--reset-user] [--lookback N]` (chiama `run_ingest` sull'emulatore con un utente di test; exit 2 = riavviare `rundev.sh`), `./deploy.sh [all|functions|rules]`
- Script: `PYTHONPATH=functions functions/venv/bin/python scripts/<script>.py`

## File chiave
`functions/main.py` · `functions/distillo/config.py` · `functions/distillo/models.py` ·
`functions/distillo/sources/registry.py` · `functions/distillo/ingest/` · `firestore.rules` · `firestore.indexes.json`

## Convenzioni di codice
- Python 3.13, tipizzato (mypy strict sul package `distillo`), `ruff` lint + format.
- Campi Firestore in camelCase, Python in snake_case: mapping via modelli Pydantic (`alias`).
- Param/secret letti solo a runtime con `.value`, mai all'import; `distillo.config` importato per primo in `main.py`.
- Test `pytest` sulle parti pure, con fixture sintetiche (le mail reali vanno in `fixtures/emails/*.eml`).

## Regole obbligatorie (§11 del master)
1. Aggiornare `docs/ARCHITECTURE.md`, `README.md` e `CLAUDE.md` **nella stessa modifica** che cambia architettura, modello dati, functions, flussi o configurazione. Se si diverge dal master, aggiornare anche il master.
2. Nessuna fonte fuori da `registry.py`: nuova fonte = una voce nel registry (+ eventuale fixture) → deploy.
3. Nessun tool calling agli LLM della pipeline: il testo di mail e articoli è input non fidato; gli LLM producono solo testo/JSON validato da schema.
4. Nessun segreto nel repo né nei log; mai loggare i corpi delle mail. I segreti non si stampano, non si passano come argomenti da riga di comando e non si scrivono in file versionati (solo in `functions/.secret.local`, modo 600, via variabili d'ambiente del singolo processo).
5. `mypy`, `ruff check`, `ruff format --check` e `pytest` devono passare.
6. Scope Gmail solo `gmail.readonly`; mai modificare la casella.
7. `setup.sh`, `rundev.sh`, `ingest-local.sh` e `deploy.sh` restano eseguibili, con `set -euo pipefail`.
8. Non fare deploy né comandi che modificano il progetto Firebase remoto senza richiesta esplicita.
