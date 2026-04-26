import os


# Tests should not depend on local secret files or export traces accidentally.
os.environ.setdefault("LOGFIRE_TOKEN", "")
os.environ.setdefault("LOGFIRE_PROJECT_URL", "")
os.environ.setdefault("PYDANTIC_AI_GATEWAY_API_KEY", "")
os.environ.setdefault("PAIG_API_KEY", "")
os.environ.setdefault("PYDANTIC_AI_GATEWAY_ROUTE", "")
os.environ.setdefault("CAFETWIN_GATEWAY_ROUTE", "")
os.environ.setdefault("CAFETWIN_OPTIMIZATION_MODEL", "")
