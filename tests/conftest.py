import os


# Tests should not depend on local secret files or export traces accidentally.
os.environ.setdefault("LOGFIRE_TOKEN", "")
os.environ.setdefault("LOGFIRE_PROJECT_URL", "")
os.environ.setdefault("PYDANTIC_AI_GATEWAY_API_KEY", "")
os.environ.setdefault("PAIG_API_KEY", "")
os.environ.setdefault("PYDANTIC_AI_GATEWAY_ROUTE", "")
os.environ.setdefault("CAFETWIN_GATEWAY_ROUTE", "")
os.environ.setdefault("CAFETWIN_OPTIMIZATION_MODEL", "")
os.environ["MUBIT_API_KEY"] = ""
os.environ["MUBIT_ENDPOINT"] = ""
os.environ["MUBIT_HTTP_ENDPOINT"] = ""

# Disable per-IP rate limiting for the test suite — TestClient hits the
# routes hundreds of times in a single run and would otherwise trip the
# 100/day cap. Production keeps the limiter active.
os.environ["CAFETWIN_DISABLE_RATE_LIMIT"] = "1"
