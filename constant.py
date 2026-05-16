import os
from datetime import datetime, timezone
from typing import List


class _LambdaEnvMeta:
    """Lazy environment configuration. Reads env vars on first property access."""

    def __init__(self) -> None:
        self._initialized: bool = False
        self._cache: dict = {}

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        self._cache["RDS_REPLICA_DNS_NAMES"] = os.environ["RDS_REPLICA_DNS_NAMES"]
        self._cache["RDS_LISTENER_PORT"] = int(os.environ["RDS_LISTENER_PORT"])
        self._cache["STATE_PREFIX"] = os.environ["STATE_PREFIX"]
        self._cache["S3_BUCKET"] = os.environ["S3_BUCKET"]
        self._cache["NLB_TG_ARN"] = os.environ["NLB_TG_ARN"]
        self._cache["MAX_LOOKUP_PER_INVOCATION"] = int(os.environ["MAX_LOOKUP_PER_INVOCATION"])
        self._cache["INVOCATIONS_BEFORE_DEREGISTRATION"] = int(os.environ["INVOCATIONS_BEFORE_DEREGISTRATION"])
        self._cache["MAX_DEREGISTRATION_PERCENT"] = int(os.getenv("MAX_DEREGISTRATION_PERCENT", "50"))
        self._cache["SAME_VPC"] = os.getenv("SAME_VPC", "true").lower() == "true"
        self._cache["REGION"] = os.environ["AWS_REGION"]

        # Derived values
        dns_names = self._cache["RDS_REPLICA_DNS_NAMES"]
        dns_list = [name.strip() for name in dns_names.split(",") if name.strip()]
        if not dns_list:
            raise ValueError("RDS_REPLICA_DNS_NAMES must contain at least one valid DNS name")
        self._cache["RDS_REPLICA_DNS_LIST"] = dns_list

        prefix = self._cache["STATE_PREFIX"]
        self._cache["ACTIVE_IP_LIST_KEY"] = f"{prefix}/active_ip.json"
        self._cache["PENDING_IP_LIST_KEY"] = f"{prefix}/pending_ip.json"

        self._initialized = True

    def reset(self) -> None:
        """Reset cached state. Used in tests to re-read environment variables."""
        self._initialized = False
        self._cache.clear()

    @property
    def TIME(self) -> str:
        """Always returns current UTC time (not cached)."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    @property
    def RDS_REPLICA_DNS_NAMES(self) -> str:
        self._ensure_initialized()
        return self._cache["RDS_REPLICA_DNS_NAMES"]

    @property
    def RDS_LISTENER_PORT(self) -> int:
        self._ensure_initialized()
        return self._cache["RDS_LISTENER_PORT"]

    @property
    def STATE_PREFIX(self) -> str:
        self._ensure_initialized()
        return self._cache["STATE_PREFIX"]

    @property
    def S3_BUCKET(self) -> str:
        self._ensure_initialized()
        return self._cache["S3_BUCKET"]

    @property
    def NLB_TG_ARN(self) -> str:
        self._ensure_initialized()
        return self._cache["NLB_TG_ARN"]

    @property
    def MAX_LOOKUP_PER_INVOCATION(self) -> int:
        self._ensure_initialized()
        return self._cache["MAX_LOOKUP_PER_INVOCATION"]

    @property
    def INVOCATIONS_BEFORE_DEREGISTRATION(self) -> int:
        self._ensure_initialized()
        return self._cache["INVOCATIONS_BEFORE_DEREGISTRATION"]

    @property
    def MAX_DEREGISTRATION_PERCENT(self) -> int:
        self._ensure_initialized()
        return self._cache["MAX_DEREGISTRATION_PERCENT"]

    @property
    def SAME_VPC(self) -> bool:
        self._ensure_initialized()
        return self._cache["SAME_VPC"]

    @property
    def REGION(self) -> str:
        self._ensure_initialized()
        return self._cache["REGION"]

    @property
    def RDS_REPLICA_DNS_LIST(self) -> List[str]:
        self._ensure_initialized()
        return self._cache["RDS_REPLICA_DNS_LIST"]

    @property
    def ACTIVE_IP_LIST_KEY(self) -> str:
        self._ensure_initialized()
        return self._cache["ACTIVE_IP_LIST_KEY"]

    @property
    def PENDING_IP_LIST_KEY(self) -> str:
        self._ensure_initialized()
        return self._cache["PENDING_IP_LIST_KEY"]


LambdaEnv = _LambdaEnvMeta()
