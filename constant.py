import os
from datetime import datetime, timezone
from typing import List, Optional


class LambdaEnv:
    """
    Constant extracted from Lambda environment variables
    """

    RDS_REPLICA_DNS_NAMES = os.environ["RDS_REPLICA_DNS_NAMES"]
    RDS_LISTENER_PORT = int(os.environ["RDS_LISTENER_PORT"])
    STATE_PREFIX = os.environ["STATE_PREFIX"]
    CLOUDWATCH_LOG_GROUP = os.getenv("CLOUDWATCH_LOG_GROUP")
    S3_BUCKET = os.environ["S3_BUCKET"]
    NLB_TG_ARN = os.environ["NLB_TG_ARN"]
    MAX_LOOKUP_PER_INVOCATION = int(os.environ["MAX_LOOKUP_PER_INVOCATION"])
    INVOCATIONS_BEFORE_DEREGISTRATION = int(
        os.environ["INVOCATIONS_BEFORE_DEREGISTRATION"]
    )
    SAME_VPC = True if os.getenv('SAME_VPC', "true").lower() == "true" else False
    REGION = os.environ["AWS_REGION"]
    ACTIVE_FILENAME = "active_ip.json"
    PENDING_DEREGISTRATION_FILENAME = "pending_ip.json"
    
    # Parse and trim comma-separated DNS names
    RDS_REPLICA_DNS_LIST = [name.strip() for name in RDS_REPLICA_DNS_NAMES.split(',') if name.strip()]
    
    ACTIVE_IP_LIST_KEY = f"{STATE_PREFIX}/{ACTIVE_FILENAME}"
    PENDING_IP_LIST_KEY = f"{STATE_PREFIX}/{PENDING_DEREGISTRATION_FILENAME}"
    TIME = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
