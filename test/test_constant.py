"""Unit tests for LambdaEnv edge cases in constant.py."""
import os
import pytest

from constant import LambdaEnv


# Minimal valid environment variables for LambdaEnv initialization
VALID_ENV = {
    "RDS_REPLICA_DNS_NAMES": "replica1.rds.amazonaws.com",
    "RDS_LISTENER_PORT": "3306",
    "STATE_PREFIX": "test-prefix",
    "S3_BUCKET": "test-bucket",
    "NLB_TG_ARN": "arn:aws:elasticloadbalancing:us-east-1:123456:targetgroup/TG/abc",
    "MAX_LOOKUP_PER_INVOCATION": "10",
    "INVOCATIONS_BEFORE_DEREGISTRATION": "3",
    "AWS_REGION": "us-east-1",
}


def _set_env(env_dict):
    """Set environment variables from a dictionary."""
    for key, value in env_dict.items():
        os.environ[key] = value


def _clear_env(keys):
    """Remove environment variables by key list."""
    for key in keys:
        os.environ.pop(key, None)


class TestMissingRequiredEnvVars:
    """Test that missing required env vars raise KeyError when accessed."""

    def setup_method(self):
        LambdaEnv.reset()
        _clear_env(VALID_ENV.keys())

    def teardown_method(self):
        LambdaEnv.reset()
        _clear_env(VALID_ENV.keys())

    def test_missing_rds_replica_dns_names_raises_key_error(self):
        env = {k: v for k, v in VALID_ENV.items() if k != "RDS_REPLICA_DNS_NAMES"}
        _set_env(env)
        with pytest.raises(KeyError):
            _ = LambdaEnv.RDS_REPLICA_DNS_NAMES

    def test_missing_s3_bucket_raises_key_error(self):
        env = {k: v for k, v in VALID_ENV.items() if k != "S3_BUCKET"}
        _set_env(env)
        with pytest.raises(KeyError):
            _ = LambdaEnv.S3_BUCKET

    def test_missing_nlb_tg_arn_raises_key_error(self):
        env = {k: v for k, v in VALID_ENV.items() if k != "NLB_TG_ARN"}
        _set_env(env)
        with pytest.raises(KeyError):
            _ = LambdaEnv.NLB_TG_ARN

    def test_missing_rds_listener_port_raises_key_error(self):
        env = {k: v for k, v in VALID_ENV.items() if k != "RDS_LISTENER_PORT"}
        _set_env(env)
        with pytest.raises(KeyError):
            _ = LambdaEnv.RDS_LISTENER_PORT

    def test_missing_aws_region_raises_key_error(self):
        env = {k: v for k, v in VALID_ENV.items() if k != "AWS_REGION"}
        _set_env(env)
        with pytest.raises(KeyError):
            _ = LambdaEnv.REGION


class TestDnsNameValidation:
    """Test that zero valid DNS names raises ValueError."""

    def setup_method(self):
        LambdaEnv.reset()
        _clear_env(VALID_ENV.keys())

    def teardown_method(self):
        LambdaEnv.reset()
        _clear_env(VALID_ENV.keys())

    def test_all_whitespace_dns_names_raises_value_error(self):
        env = dict(VALID_ENV)
        env["RDS_REPLICA_DNS_NAMES"] = "   ,   ,   "
        _set_env(env)
        with pytest.raises(ValueError, match="at least one valid DNS name"):
            _ = LambdaEnv.RDS_REPLICA_DNS_LIST

    def test_empty_string_dns_names_raises_value_error(self):
        env = dict(VALID_ENV)
        env["RDS_REPLICA_DNS_NAMES"] = ""
        _set_env(env)
        with pytest.raises(ValueError, match="at least one valid DNS name"):
            _ = LambdaEnv.RDS_REPLICA_DNS_LIST

    def test_only_commas_dns_names_raises_value_error(self):
        env = dict(VALID_ENV)
        env["RDS_REPLICA_DNS_NAMES"] = ",,,"
        _set_env(env)
        with pytest.raises(ValueError, match="at least one valid DNS name"):
            _ = LambdaEnv.RDS_REPLICA_DNS_LIST


class TestDefaults:
    """Test that MAX_DEREGISTRATION_PERCENT defaults to 50."""

    def setup_method(self):
        LambdaEnv.reset()
        _clear_env(VALID_ENV.keys())
        os.environ.pop("MAX_DEREGISTRATION_PERCENT", None)

    def teardown_method(self):
        LambdaEnv.reset()
        _clear_env(VALID_ENV.keys())
        os.environ.pop("MAX_DEREGISTRATION_PERCENT", None)

    def test_max_deregistration_percent_defaults_to_50(self):
        _set_env(VALID_ENV)
        # Ensure MAX_DEREGISTRATION_PERCENT is not set
        os.environ.pop("MAX_DEREGISTRATION_PERCENT", None)
        assert LambdaEnv.MAX_DEREGISTRATION_PERCENT == 50

    def test_max_deregistration_percent_reads_env_when_set(self):
        _set_env(VALID_ENV)
        os.environ["MAX_DEREGISTRATION_PERCENT"] = "75"
        assert LambdaEnv.MAX_DEREGISTRATION_PERCENT == 75


class TestPortType:
    """Test that RDS_LISTENER_PORT is integer type."""

    def setup_method(self):
        LambdaEnv.reset()
        _clear_env(VALID_ENV.keys())

    def teardown_method(self):
        LambdaEnv.reset()
        _clear_env(VALID_ENV.keys())

    def test_rds_listener_port_is_integer(self):
        _set_env(VALID_ENV)
        port = LambdaEnv.RDS_LISTENER_PORT
        assert isinstance(port, int)
        assert port == 3306

    def test_rds_listener_port_postgres(self):
        env = dict(VALID_ENV)
        env["RDS_LISTENER_PORT"] = "5432"
        _set_env(env)
        port = LambdaEnv.RDS_LISTENER_PORT
        assert isinstance(port, int)
        assert port == 5432
