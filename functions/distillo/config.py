from firebase_functions import options
from firebase_functions.params import IntParam, SecretParam, StringParam

options.set_global_options(
    region=options.SupportedRegion.EUROPE_WEST1,
    max_instances=3,
)

# TODO(step 2): OPENAI_API_KEY (SecretParam), MODEL_EXTRACT (StringParam)
# TODO(step 4): JINA_API_KEY (SecretParam), MODEL_ANALYZE (StringParam)
# TODO(step 5): MODEL_EMBEDDING (StringParam, default="text-embedding-3-small"),
#               CLUSTER_THRESHOLD (FloatParam, default=0.15)
GMAIL_CLIENT_ID = SecretParam("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = SecretParam("GMAIL_CLIENT_SECRET")
GMAIL_REFRESH_TOKEN = SecretParam("GMAIL_REFRESH_TOKEN")

ALLOWED_UID = StringParam("ALLOWED_UID")
INGEST_LOOKBACK_DAYS = IntParam("INGEST_LOOKBACK_DAYS", default=3)
INGEST_MAX_MESSAGES = IntParam("INGEST_MAX_MESSAGES", default=50)

INGEST_SCHEDULE = "every 60 minutes"

GMAIL_SECRETS = [GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN]
