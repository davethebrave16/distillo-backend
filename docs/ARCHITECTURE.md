# distillo-backend — Architettura

Architettura di questo repo. Il documento master (fonte di verità, decisioni D1–D10, modello dati,
roadmap) è `../docs/ARCHITECTURE.md`; qui si descrive solo ciò che questo repo implementa.
In caso di conflitto vince il master.

**Stato**: roadmap step 0–1 (scaffolding + ingestione Gmail). `extract`, `enrich`, `analyze`
sono package vuoti (`__init__.py`).

## Runtime
Firebase Functions 2nd gen, Python 3.13 (`runtime: python313` in `firebase.json`), region
`europe-west1` (Firestore `(default)` è in `europe-west1`), `max_instances=3`.
Venv in `functions/venv` (richiesto dalla Firebase CLI).

## Functions (`functions/main.py`)
`main.py` importa `distillo.config` per primo (applica `set_global_options`), inizializza
`firebase_admin` una sola volta e registra:

| Function | Trigger | Note |
|---|---|---|
| `ingest_scheduled` | `on_schedule` ogni 60 minuti, `Europe/Rome` | secrets `GMAIL_*`; nell'emulatore non parte da sola (manca pubsub) |
| `run_ingest` | `on_call` | secrets `GMAIL_*`; richiede `req.auth.uid == ALLOWED_UID`, altrimenti `PERMISSION_DENIED`; ritorna il riepilogo |

Param e secret si leggono solo a runtime (`.value`), mai all'import.

## Package `functions/distillo/`
| Modulo | Ruolo |
|---|---|
| `config.py` | Param/secret (solo quelli dello step 1; gli altri sono TODO commentati con lo step che li introduce) |
| `models.py` | Modelli Pydantic `EmailDoc`, `SourceSettingsDoc`: attributi snake_case, alias camelCase (`from_address` ↔ `from`); `to_firestore()` serializza con gli alias |
| `sources/registry.py` | `SOURCES` hardcoded (tldr, techpresso) e `match_source(from_header)`: `email.utils.parseaddr`, case-insensitive, prima gli indirizzi esatti, poi i domini |
| `ingest/gmail.py` | Client Gmail da `google.oauth2.credentials.Credentials` (refresh token), scope solo `gmail.readonly`; `list_message_ids` con paginazione e tetto; `get_raw_message` (`format="raw"`) |
| `ingest/mime.py` | `decode_gmail_raw` (base64url) e `parse_email(bytes)`: stdlib `email` con `policy.default`, corpo da `get_body(("html","plain"))`; accetta anche i byte di un `.eml` |
| `ingest/html_to_md.py` | BeautifulSoup + `markdownify` → markdown leggibile riga per riga: rimuove script/style, elementi nascosti (preheader `display:none` ecc.), immagini di tracking (1×1, nascoste, host di tracking, senza alt), link di unsubscribe e le frasi orfane che lasciano (blocchi brevi che finiscono con "please ."), footer legale (solo nel 40% finale). Le tabelle di layout sono appiattite in paragrafi (si tengono solo le tabelle con `<th>` proprie); td/tr/div diventano paragrafi; i caratteri invisibili (U+200B–U+200D, U+2060, U+FEFF, U+00AD, U+034F: padding del preheader) e le sequenze di spazi sono rimossi, 3+ a-capo diventano 2. Gli URL di tracking restano intatti (li gestisce lo step 2) e i link "view in browser" restano |
| `ingest/service.py` | `build_email_doc` (pura: mail parsata → `EmailDoc`) e `ingest()` |
| `extract/`, `enrich/`, `analyze/`, `lib/`, `prompts/` | segnaposto per gli step successivi |

## Flusso di `ingest()`
1. `list` con `label:news newer_than:{INGEST_LOOKBACK_DAYS}d`, paginazione completa (limite di sicurezza `LIST_HARD_LIMIT` = 2000 ID, dal più recente).
2. Gli ID già presenti in `emails/` vengono saltati (lettura a blocchi con `get_all`, solo `__name__`). Dai restanti si prendono al massimo `INGEST_MAX_MESSAGES` (le più recenti); gli altri sono rimandati al run successivo (log `deferred`). Il tetto riguarda le mail **nuove**: le già salvate non lo consumano, quindi più run successivi avanzano fino alle mail più vecchie.
3. Per quelle selezionate: `get(format="raw")` → `parse_email` → `build_email_doc`:
   - nessuna fonte nel registry → `unmatched` (markdown vuoto);
   - fonte con `sourceSettings/{id}.enabled == false` (assente = abilitata) → `skipped` (markdown vuoto);
   - altrimenti HTML (o testo semplice) → markdown, cap a 400k caratteri (limite Firestore 1 MiB) → `pending`.
4. Scrittura con `create()` (idempotente: `AlreadyExists` = un altro run ha vinto la gara).
5. Un messaggio che fallisce (fetch, parsing, corpo vuoto) non ferma il run: viene contato in
   `errors` e scritto con `status: 'error'` e `error`. **I documenti `error` non vengono riprovati**
   (l'ID esiste già): per riprovare, cancellare il documento da Firestore.
6. Ritorna `{listed, created, skipped, unmatched, errors}`; `created` conta i soli `pending`.

Log strutturati con `firebase_functions.logger`; mai segreti né corpi delle mail.

## Sicurezza
- Scope Gmail solo `gmail.readonly`; nessuna modifica alla casella.
- I segreti non si stampano, non si passano come argomenti da riga di comando e non si scrivono in file versionati.
- `firestore.rules`: lettura solo per l'uid ammesso (costante `REPLACE_WITH_UID` in `allowedUid()`);
  scrittura client solo su `sourceSettings/*` (`enabled`, `updatedAt`) e sui campi `read`/`starred`
  degli `items/*` esistenti (`diff().affectedKeys().hasOnly`); il resto solo via Admin SDK.
- `firestore.indexes.json`: indici compositi `category + firstSeen desc` e `starred + firstSeen desc`
  su `items`. `firstSeen desc` da solo è un indice a campo singolo, creato in automatico da Firestore.
  Il vector index arriva con lo step 5.

## Script
Gli script Python in `scripts/` si lanciano dalla root del repo col venv delle functions.
- `setup.sh [--reauth]` (root, idempotente): crea il venv e installa le dipendenze; crea `functions/.env.local` e `functions/.secret.local` dagli `.example` solo se mancano; `chmod 600` su `.secret.local`. Se `GMAIL_REFRESH_TOKEN` manca o è vuoto in `.secret.local` (o con `--reauth`): riusa `GMAIL_CLIENT_ID`/`GMAIL_CLIENT_SECRET` già presenti, altrimenti li chiede (`read -r` per l'ID, `read -rs` per il secret) e lancia `gmail_auth.py --write-secret-local` passando i valori solo come variabili d'ambiente di quel processo (non esportate nella shell). Altrimenti salta ("Gmail already authorised"). Infine stampa i prossimi passi, inclusi i tre `firebase functions:secrets:set` per la produzione (la CLI chiede i valori da sé).
- `scripts/gmail_auth.py [--write-secret-local]`: `InstalledAppFlow.run_local_server(port=0, access_type="offline", prompt="consent")` con client config costruita da `GMAIL_CLIENT_ID`/`GMAIL_CLIENT_SECRET` (ambiente, mai argomenti). Senza flag stampa il refresh token solo a terminale; con il flag scrive le tre chiavi `GMAIL_*` in `functions/.secret.local` (creato se manca, aggiorna solo quelle tre chiavi preservando le altre righe, scrittura atomica, modo 600) e stampa solo una conferma.
- `scripts/seed_emulator.py`: carica `fixtures/emails/*.eml` in `emails/` dell'emulatore; rifiuta di partire senza `FIRESTORE_EMULATOR_HOST`.
- `ingest-local.sh [--reset-user] [--lookback N]` (root): chiama `run_ingest` sull'emulatore locale con l'utente di test `dave@test.local` (REST dell'Auth emulator, `key=fake-api-key`: `signInWithPassword`, altrimenti `signUp`). Parla solo con 127.0.0.1 (host/porte da `firebase.json`, progetto da `.firebaserc`, region `europe-west1`) e rifiuta di partire se Auth o Functions non sono raggiungibili. Allinea `ALLOWED_UID` (e con `--lookback` `INGEST_LOOKBACK_DAYS`) in `functions/.env.local` aggiornando solo quella chiave; poiché i param si leggono all'avvio dell'emulatore, in tal caso esce con codice 2 chiedendo di riavviare `rundev.sh`. Altrimenti chiama la callable con `Authorization: Bearer <idToken>` e stampa il riepilogo. Exit: 0 ok, 1 errore, 2 riavvio necessario. Non stampa mai i token.
- `rundev.sh`, `deploy.sh`: come §12.1 e §12.2 del master.

## Configurazione
Valori non segreti in `functions/.env` (deploy) e `functions/.env.local` (emulatore); secret per
l'emulatore in `functions/.secret.local`. Le versioni `.example` (commentate con dove trovare i valori)
sono versionate; `.env.local` e `.secret.local` no.

## Test
`pytest` su parti pure: registry, MIME (multipart annidati, base64url, charset, fallback plain),
HTML→markdown, `build_email_doc`, scrittura di `.secret.local` (`update_env_file`). Fixture sintetiche
generate nei test (le mail reali in `fixtures/emails/*.eml` sono gitignorate perché contengono i link di tracking dell'iscritto; restano solo `README.md` e `.gitkeep`). `ingest()` con Gmail e Firestore reali e il flusso OAuth non sono coperti da test automatici.
