# conftest.py
import pytest
import sys
import os

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test.unittest_constant import UnittestConstant


@pytest.fixture()
def env_setup(monkeypatch):
    """
    Set up environment variables for RDS read replica testing
    :param monkeypatch:
    """
    # RDS-specific environment variables
    monkeypatch.setenv("RDS_REPLICA_DNS_NAMES", "replica1.rds.amazonaws.com, replica2.rds.amazonaws.com, replica3.rds.amazonaws.com")
    monkeypatch.setenv("RDS_LISTENER_PORT", "3306")
    monkeypatch.setenv("STATE_PREFIX", "rds-cluster-read-replicas")
    monkeypatch.setenv("CLOUDWATCH_LOG_GROUP", "/aws/lambda/rds-nlb-registration")
    
    # Common environment variables
    monkeypatch.setenv("S3_BUCKET", UnittestConstant.S3_BUCKET)
    monkeypatch.setenv("NLB_TG_ARN", UnittestConstant.NLB_TG_ARN)
    monkeypatch.setenv(
        "MAX_LOOKUP_PER_INVOCATION", UnittestConstant.MAX_LOOKUP_PER_INVOCATION
    )
    monkeypatch.setenv(
        "INVOCATIONS_BEFORE_DEREGISTRATION",
        UnittestConstant.INVOCATIONS_BEFORE_DEREGISTRATION,
    )
    monkeypatch.setenv("SAME_VPC", UnittestConstant.SAME_VPC)
    monkeypatch.setenv("AWS_REGION", UnittestConstant.AWS_REGION)
