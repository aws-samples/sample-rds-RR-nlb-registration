"""Property-based tests for LambdaEnv (constant.py).

Tests use the hypothesis library to verify universal properties
of the lazy initialization configuration class.
"""

import os
import sys
import time

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constant import LambdaEnv


# --- Strategies ---

# Generate valid DNS-like names (non-empty, no commas, no whitespace-only)
dns_name_strategy = st.from_regex(r"[a-z][a-z0-9\-\.]{1,50}\.com", fullmatch=True)

# Generate a valid comma-separated DNS name string with at least one entry
valid_dns_names_strategy = st.lists(dns_name_strategy, min_size=1, max_size=5).map(
    lambda names: ",".join(names)
)

# Generate valid integer port numbers
valid_port_strategy = st.integers(min_value=1, max_value=65535)

# Generate valid positive integers for config values
positive_int_strategy = st.integers(min_value=1, max_value=1000)

# Generate valid state prefix strings (non-empty, no slashes at start)
state_prefix_strategy = st.from_regex(r"[a-z][a-z0-9\-]{1,30}", fullmatch=True)

# Generate valid S3 bucket names
bucket_strategy = st.from_regex(r"[a-z][a-z0-9\-]{2,30}", fullmatch=True)

# Generate valid ARN-like strings
arn_strategy = st.from_regex(
    r"arn:aws:elasticloadbalancing:us-east-1:\d{12}:targetgroup/[a-z\-]+/[a-f0-9]+",
    fullmatch=True,
)

# Generate valid region strings
region_strategy = st.sampled_from(
    [
        "us-east-1",
        "us-west-2",
        "eu-west-1",
        "ap-southeast-1",
    ]
)

# Generate boolean-like strings for SAME_VPC
bool_string_strategy = st.sampled_from(
    ["true", "false", "True", "False", "TRUE", "FALSE"]
)


# Composite strategy for a full valid environment configuration
@st.composite
def valid_env_config(draw):
    return {
        "RDS_REPLICA_DNS_NAMES": draw(valid_dns_names_strategy),
        "RDS_LISTENER_PORT": str(draw(valid_port_strategy)),
        "STATE_PREFIX": draw(state_prefix_strategy),
        "S3_BUCKET": draw(bucket_strategy),
        "NLB_TG_ARN": draw(arn_strategy),
        "MAX_LOOKUP_PER_INVOCATION": str(draw(positive_int_strategy)),
        "INVOCATIONS_BEFORE_DEREGISTRATION": str(draw(positive_int_strategy)),
        "SAME_VPC": draw(bool_string_strategy),
        "AWS_REGION": draw(region_strategy),
    }


def set_env(config):
    """Helper to set all environment variables from a config dict."""
    for key, value in config.items():
        os.environ[key] = value


def clear_env(config):
    """Helper to remove environment variables set by a config dict."""
    for key in config:
        os.environ.pop(key, None)


# Required env var keys for cleanup
REQUIRED_ENV_KEYS = [
    "RDS_REPLICA_DNS_NAMES",
    "RDS_LISTENER_PORT",
    "STATE_PREFIX",
    "S3_BUCKET",
    "NLB_TG_ARN",
    "MAX_LOOKUP_PER_INVOCATION",
    "INVOCATIONS_BEFORE_DEREGISTRATION",
    "SAME_VPC",
    "AWS_REGION",
    "MAX_DEREGISTRATION_PERCENT",
]


# --- Property 1: Lazy initialization reads environment variables after import ---


class TestProperty1LazyInitialization:
    """
    **Validates: Requirements 1.1, 1.3**

    For any set of valid environment variables set after the constant module
    is imported, accessing LambdaEnv properties SHALL return the values from
    those environment variables (not raise KeyError or return stale values).
    """

    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(config=valid_env_config())
    def test_lazy_init_reads_env_after_import(self, config):
        """Feature: code-quality-improvements, Property 1: Lazy initialization reads environment variables after import"""
        # Reset to force re-read
        LambdaEnv.reset()

        # Set env vars AFTER import (module already imported at top)
        set_env(config)

        try:
            # Access properties - should read from the env vars we just set
            assert LambdaEnv.RDS_REPLICA_DNS_NAMES == config["RDS_REPLICA_DNS_NAMES"]
            assert LambdaEnv.RDS_LISTENER_PORT == int(config["RDS_LISTENER_PORT"])
            assert LambdaEnv.STATE_PREFIX == config["STATE_PREFIX"]
            assert LambdaEnv.S3_BUCKET == config["S3_BUCKET"]
            assert LambdaEnv.NLB_TG_ARN == config["NLB_TG_ARN"]
            assert LambdaEnv.MAX_LOOKUP_PER_INVOCATION == int(
                config["MAX_LOOKUP_PER_INVOCATION"]
            )
            assert LambdaEnv.INVOCATIONS_BEFORE_DEREGISTRATION == int(
                config["INVOCATIONS_BEFORE_DEREGISTRATION"]
            )
            assert LambdaEnv.SAME_VPC == (config["SAME_VPC"].lower() == "true")
            assert LambdaEnv.REGION == config["AWS_REGION"]
        finally:
            # Cleanup
            LambdaEnv.reset()
            clear_env(config)


# --- Property 2: TIME returns fresh timestamp on each access ---


class TestProperty2TimeFreshness:
    """
    **Validates: Requirements 1.2**

    For any two accesses to LambdaEnv.TIME separated by at least 1 second,
    the second value SHALL be strictly greater than the first when compared
    as timestamp strings.
    """

    @settings(max_examples=3, deadline=None)
    @given(st.just(None))
    def test_time_returns_fresh_timestamp(self, _):
        """Feature: code-quality-improvements, Property 2: TIME returns fresh timestamp on each access"""
        time1 = LambdaEnv.TIME
        time.sleep(1.1)
        time2 = LambdaEnv.TIME

        # Timestamps in "%Y-%m-%d %H:%M:%S" format are lexicographically comparable
        assert time2 > time1, f"Expected {time2} > {time1}"


# --- Property 3: LambdaEnv interface preserves attribute types ---


class TestProperty3InterfaceTypes:
    """
    **Validates: Requirements 1.4**

    For any valid environment variable configuration, all LambdaEnv attributes
    SHALL be accessible and return values matching their documented types
    (str, int, bool, List[str] as appropriate).
    """

    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(config=valid_env_config())
    def test_interface_preserves_types(self, config):
        """Feature: code-quality-improvements, Property 3: LambdaEnv interface preserves attribute types"""
        LambdaEnv.reset()
        set_env(config)

        try:
            # String attributes
            assert isinstance(LambdaEnv.RDS_REPLICA_DNS_NAMES, str)
            assert isinstance(LambdaEnv.STATE_PREFIX, str)
            assert isinstance(LambdaEnv.S3_BUCKET, str)
            assert isinstance(LambdaEnv.NLB_TG_ARN, str)
            assert isinstance(LambdaEnv.REGION, str)
            assert isinstance(LambdaEnv.ACTIVE_IP_LIST_KEY, str)
            assert isinstance(LambdaEnv.PENDING_IP_LIST_KEY, str)
            assert isinstance(LambdaEnv.TIME, str)

            # Integer attributes
            assert isinstance(LambdaEnv.RDS_LISTENER_PORT, int)
            assert isinstance(LambdaEnv.MAX_LOOKUP_PER_INVOCATION, int)
            assert isinstance(LambdaEnv.INVOCATIONS_BEFORE_DEREGISTRATION, int)
            assert isinstance(LambdaEnv.MAX_DEREGISTRATION_PERCENT, int)

            # Boolean attributes
            assert isinstance(LambdaEnv.SAME_VPC, bool)

            # List attributes
            assert isinstance(LambdaEnv.RDS_REPLICA_DNS_LIST, list)
            assert all(isinstance(name, str) for name in LambdaEnv.RDS_REPLICA_DNS_LIST)
        finally:
            # Cleanup
            LambdaEnv.reset()
            clear_env(config)


# --- Property 9: DNS name parsing rejects invalid entries ---


class TestProperty9DnsValidation:
    """
    **Validates: Requirements 7.1, 7.2**

    For any comma-separated string where at least one entry is empty or
    whitespace-only after splitting and trimming, LambdaEnv initialization
    SHALL raise a ValueError.
    """

    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        invalid_dns=st.sampled_from(
            [
                "",
                ",",
                ",,",
                " , , ",
                "   ",
                ",  ,",
                " , ",
                "  ,  ,  ",
                "\t,\t",
                "  \t  ",
            ]
        )
    )
    def test_dns_parsing_rejects_all_invalid_entries(self, invalid_dns):
        """Feature: code-quality-improvements, Property 9: DNS name parsing rejects invalid entries"""
        LambdaEnv.reset()

        base_config = {
            "RDS_REPLICA_DNS_NAMES": invalid_dns,
            "RDS_LISTENER_PORT": "3306",
            "STATE_PREFIX": "test-prefix",
            "S3_BUCKET": "test-bucket",
            "NLB_TG_ARN": "arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/tg/abc123",
            "MAX_LOOKUP_PER_INVOCATION": "10",
            "INVOCATIONS_BEFORE_DEREGISTRATION": "3",
            "SAME_VPC": "true",
            "AWS_REGION": "us-east-1",
        }
        set_env(base_config)

        try:
            with pytest.raises(ValueError):
                _ = LambdaEnv.RDS_REPLICA_DNS_LIST
        finally:
            LambdaEnv.reset()
            clear_env(base_config)

    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        num_empty=st.integers(min_value=2, max_value=6),
        whitespace=st.sampled_from(["", " ", "  ", "\t", " \t "]),
    )
    def test_dns_parsing_rejects_generated_whitespace_only(self, num_empty, whitespace):
        """Feature: code-quality-improvements, Property 9: DNS name parsing rejects invalid entries (generated)"""
        # Build a string of only whitespace/empty entries separated by commas
        dns_string = ",".join([whitespace] * num_empty)

        LambdaEnv.reset()

        base_config = {
            "RDS_REPLICA_DNS_NAMES": dns_string,
            "RDS_LISTENER_PORT": "3306",
            "STATE_PREFIX": "test-prefix",
            "S3_BUCKET": "test-bucket",
            "NLB_TG_ARN": "arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/tg/abc123",
            "MAX_LOOKUP_PER_INVOCATION": "10",
            "INVOCATIONS_BEFORE_DEREGISTRATION": "3",
            "SAME_VPC": "true",
            "AWS_REGION": "us-east-1",
        }
        set_env(base_config)

        try:
            with pytest.raises(ValueError):
                _ = LambdaEnv.RDS_REPLICA_DNS_LIST
        finally:
            LambdaEnv.reset()
            clear_env(base_config)


# --- Property 4, 5, 6: AwsServices exception handling ---

import logging
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError, BotoCoreError

from aws_services import AwsServices


# --- Strategies for AwsServices tests ---

# Generate random error codes for ClientError
error_code_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=30,
)

# Generate random S3 object keys
object_key_strategy = st.from_regex(r"[a-z][a-z0-9\-/]{1,50}", fullmatch=True)

# Generate random bucket names
s3_bucket_strategy = st.from_regex(r"[a-z][a-z0-9\-]{2,30}", fullmatch=True)

# Generate random target group ARNs
tg_arn_strategy = st.from_regex(
    r"arn:aws:elasticloadbalancing:us-east-1:\d{12}:targetgroup/[a-z\-]+/[a-f0-9]+",
    fullmatch=True,
)

# Strategy for non-boto3 exception types
# Excludes KeyError because it wraps its arg in quotes when str() is called
non_boto3_exception_strategy = st.sampled_from(
    [
        RuntimeError,
        TypeError,
        ValueError,
        OSError,
        IOError,
        IndexError,
        AttributeError,
        MemoryError,
    ]
)

# Strategy for exception messages
exception_message_strategy = st.text(min_size=1, max_size=100)


def make_client_error(error_code, message="test error", operation_name="TestOp"):
    """Helper to create a ClientError with a given error code."""
    return ClientError(
        {"Error": {"Code": error_code, "Message": message}},
        operation_name,
    )


def make_botocore_error():
    """Helper to create a BotoCoreError."""
    return BotoCoreError()


# --- Property 4: Non-boto3 exceptions propagate from AwsServices ---


class TestProperty4ExceptionPropagation:
    """
    **Validates: Requirements 2.1, 2.5**

    For any AwsServices method and any exception type that is not ClientError
    or BotoCoreError, when the underlying boto3 client raises that exception,
    the AwsServices method SHALL allow it to propagate to the caller unchanged.
    """

    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        exc_type=non_boto3_exception_strategy,
        exc_msg=exception_message_strategy,
        bucket=s3_bucket_strategy,
        key=object_key_strategy,
    )
    def test_non_boto3_exceptions_propagate_from_write_content_to_s3(
        self, exc_type, exc_msg, bucket, key
    ):
        """Feature: code-quality-improvements, Property 4: Non-boto3 exceptions propagate from AwsServices (write_content_to_s3)"""
        original_exc = exc_type(exc_msg)

        with patch("aws_services.boto3") as mock_boto3:
            mock_s3_resource = MagicMock()
            mock_s3_object = MagicMock()
            mock_s3_resource.Object.return_value = mock_s3_object
            mock_s3_object.put.side_effect = original_exc
            mock_boto3.resource.return_value = mock_s3_resource
            mock_boto3.client.return_value = MagicMock()

            svc = AwsServices(region="us-east-1", bucket=bucket)
            svc.s3 = mock_s3_resource

            with pytest.raises(exc_type) as exc_info:
                svc.write_content_to_s3("test content", key)

            # Verify it's the exact same exception instance (propagated unchanged)
            assert exc_info.value is original_exc

    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        exc_type=non_boto3_exception_strategy,
        exc_msg=exception_message_strategy,
        bucket=s3_bucket_strategy,
        key=object_key_strategy,
    )
    def test_non_boto3_exceptions_propagate_from_download_elb_ip_from_s3(
        self, exc_type, exc_msg, bucket, key
    ):
        """Feature: code-quality-improvements, Property 4: Non-boto3 exceptions propagate from AwsServices (download_elb_ip_from_s3)"""
        original_exc = exc_type(exc_msg)

        with patch("aws_services.boto3") as mock_boto3:
            mock_s3_client = MagicMock()
            mock_s3_client.get_object.side_effect = original_exc
            mock_boto3.resource.return_value = MagicMock()
            mock_boto3.client.return_value = mock_s3_client

            svc = AwsServices(region="us-east-1", bucket=bucket)
            svc.s3_client = mock_s3_client

            with pytest.raises(exc_type) as exc_info:
                svc.download_elb_ip_from_s3(key)

            # Verify it's the exact same exception instance (propagated unchanged)
            assert exc_info.value is original_exc

    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        exc_type=non_boto3_exception_strategy,
        exc_msg=exception_message_strategy,
        bucket=s3_bucket_strategy,
        tg_arn=tg_arn_strategy,
    )
    def test_non_boto3_exceptions_propagate_from_register_target(
        self, exc_type, exc_msg, bucket, tg_arn
    ):
        """Feature: code-quality-improvements, Property 4: Non-boto3 exceptions propagate from AwsServices (register_target)"""
        original_exc = exc_type(exc_msg)

        with patch("aws_services.boto3") as mock_boto3:
            mock_elbv2 = MagicMock()
            mock_elbv2.register_targets.side_effect = original_exc
            mock_boto3.resource.return_value = MagicMock()
            mock_boto3.client.return_value = mock_elbv2

            svc = AwsServices(region="us-east-1", bucket=bucket)
            svc.elbv2 = mock_elbv2

            with pytest.raises(exc_type) as exc_info:
                svc.register_target(tg_arn, [{"Id": "10.0.0.1", "Port": 3306}])

            # Verify it's the exact same exception instance (propagated unchanged)
            assert exc_info.value is original_exc

    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        exc_type=non_boto3_exception_strategy,
        exc_msg=exception_message_strategy,
        bucket=s3_bucket_strategy,
        tg_arn=tg_arn_strategy,
    )
    def test_non_boto3_exceptions_propagate_from_deregister_target(
        self, exc_type, exc_msg, bucket, tg_arn
    ):
        """Feature: code-quality-improvements, Property 4: Non-boto3 exceptions propagate from AwsServices (deregister_target)"""
        original_exc = exc_type(exc_msg)

        with patch("aws_services.boto3") as mock_boto3:
            mock_elbv2 = MagicMock()
            mock_elbv2.deregister_targets.side_effect = original_exc
            mock_boto3.resource.return_value = MagicMock()
            mock_boto3.client.return_value = mock_elbv2

            svc = AwsServices(region="us-east-1", bucket=bucket)
            svc.elbv2 = mock_elbv2

            with pytest.raises(exc_type) as exc_info:
                svc.deregister_target(tg_arn, [{"Id": "10.0.0.1", "Port": 3306}])

            # Verify it's the exact same exception instance (propagated unchanged)
            assert exc_info.value is original_exc

    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        exc_type=non_boto3_exception_strategy,
        exc_msg=exception_message_strategy,
        bucket=s3_bucket_strategy,
        tg_arn=tg_arn_strategy,
    )
    def test_non_boto3_exceptions_propagate_from_get_ip_target_list(
        self, exc_type, exc_msg, bucket, tg_arn
    ):
        """Feature: code-quality-improvements, Property 4: Non-boto3 exceptions propagate from AwsServices (get_ip_target_list_by_target_group_arn)"""
        original_exc = exc_type(exc_msg)

        with patch("aws_services.boto3") as mock_boto3:
            mock_elbv2 = MagicMock()
            mock_elbv2.describe_target_health.side_effect = original_exc
            mock_boto3.resource.return_value = MagicMock()
            mock_boto3.client.return_value = mock_elbv2

            svc = AwsServices(region="us-east-1", bucket=bucket)
            svc.elbv2 = mock_elbv2

            with pytest.raises(exc_type) as exc_info:
                svc.get_ip_target_list_by_target_group_arn(tg_arn)

            # Verify it's the exact same exception instance (propagated unchanged)
            assert exc_info.value is original_exc


# --- Property 5: write_content_to_s3 re-raises on failure ---


class TestProperty5WriteReraises:
    """
    **Validates: Requirements 2.6, 5.1**

    For any ClientError or BotoCoreError raised during an S3 put operation,
    write_content_to_s3 SHALL re-raise the same exception after logging.
    """

    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        error_code=error_code_strategy,
        bucket=s3_bucket_strategy,
        key=object_key_strategy,
    )
    def test_write_content_to_s3_reraises_client_error(self, error_code, bucket, key):
        """Feature: code-quality-improvements, Property 5: write_content_to_s3 re-raises on failure (ClientError)"""
        original_error = make_client_error(error_code)

        with patch("aws_services.boto3") as mock_boto3:
            mock_s3_resource = MagicMock()
            mock_s3_object = MagicMock()
            mock_s3_resource.Object.return_value = mock_s3_object
            mock_s3_object.put.side_effect = original_error
            mock_boto3.resource.return_value = mock_s3_resource
            mock_boto3.client.return_value = MagicMock()

            svc = AwsServices(region="us-east-1", bucket=bucket)
            svc.s3 = mock_s3_resource

            with pytest.raises(ClientError) as exc_info:
                svc.write_content_to_s3("test content", key)

            # Verify it's the exact same exception instance
            assert exc_info.value is original_error

    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        bucket=s3_bucket_strategy,
        key=object_key_strategy,
    )
    def test_write_content_to_s3_reraises_botocore_error(self, bucket, key):
        """Feature: code-quality-improvements, Property 5: write_content_to_s3 re-raises on failure (BotoCoreError)"""
        original_error = make_botocore_error()

        with patch("aws_services.boto3") as mock_boto3:
            mock_s3_resource = MagicMock()
            mock_s3_object = MagicMock()
            mock_s3_resource.Object.return_value = mock_s3_object
            mock_s3_object.put.side_effect = original_error
            mock_boto3.resource.return_value = mock_s3_resource
            mock_boto3.client.return_value = MagicMock()

            svc = AwsServices(region="us-east-1", bucket=bucket)
            svc.s3 = mock_s3_resource

            with pytest.raises(BotoCoreError) as exc_info:
                svc.write_content_to_s3("test content", key)

            # Verify it's the exact same exception instance
            assert exc_info.value is original_error


# --- Property 6: Write operation ClientErrors are logged with context ---


class TestProperty6ErrorLogging:
    """
    **Validates: Requirements 2.2**

    For any ClientError raised during a write operation in AwsServices,
    the logged message SHALL contain the error code from the exception
    response and the operation context (bucket/key or target group ARN).
    """

    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        error_code=error_code_strategy,
        bucket=s3_bucket_strategy,
        key=object_key_strategy,
    )
    def test_write_content_to_s3_logs_error_code_and_context(
        self, error_code, bucket, key
    ):
        """Feature: code-quality-improvements, Property 6: Write operation ClientErrors are logged with context (write_content_to_s3)"""
        original_error = make_client_error(error_code)

        with patch("aws_services.boto3") as mock_boto3:
            mock_s3_resource = MagicMock()
            mock_s3_object = MagicMock()
            mock_s3_resource.Object.return_value = mock_s3_object
            mock_s3_object.put.side_effect = original_error
            mock_boto3.resource.return_value = mock_s3_resource
            mock_boto3.client.return_value = MagicMock()

            svc = AwsServices(region="us-east-1", bucket=bucket)
            svc.s3 = mock_s3_resource

            with patch("aws_services.logger") as mock_logger:
                with pytest.raises(ClientError):
                    svc.write_content_to_s3("test content", key)

                # Verify logger.error was called
                mock_logger.error.assert_called()
                log_message = mock_logger.error.call_args[0][0]

                # Log must contain the error code and the bucket/key context
                assert (
                    error_code in log_message
                ), f"Expected error code '{error_code}' in log message: {log_message}"
                assert (
                    bucket in log_message
                ), f"Expected bucket '{bucket}' in log message: {log_message}"
                assert (
                    key in log_message
                ), f"Expected key '{key}' in log message: {log_message}"

    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        error_code=error_code_strategy,
        bucket=s3_bucket_strategy,
        tg_arn=tg_arn_strategy,
    )
    def test_register_target_logs_error_code_and_context(
        self, error_code, bucket, tg_arn
    ):
        """Feature: code-quality-improvements, Property 6: Write operation ClientErrors are logged with context (register_target)"""
        original_error = make_client_error(error_code)

        with patch("aws_services.boto3") as mock_boto3:
            mock_elbv2 = MagicMock()
            mock_elbv2.register_targets.side_effect = original_error
            mock_boto3.resource.return_value = MagicMock()
            mock_boto3.client.return_value = mock_elbv2

            svc = AwsServices(region="us-east-1", bucket=bucket)
            svc.elbv2 = mock_elbv2

            with patch("aws_services.logger") as mock_logger:
                result = svc.register_target(tg_arn, [{"Id": "10.0.0.1", "Port": 3306}])

                # register_target returns False on ClientError
                assert result is False

                # Verify logger.error was called
                mock_logger.error.assert_called()
                log_message = mock_logger.error.call_args[0][0]

                # Log must contain the error code and the target group ARN
                assert (
                    error_code in log_message
                ), f"Expected error code '{error_code}' in log message: {log_message}"
                assert (
                    tg_arn in log_message
                ), f"Expected target group ARN '{tg_arn}' in log message: {log_message}"

    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        error_code=error_code_strategy,
        bucket=s3_bucket_strategy,
        tg_arn=tg_arn_strategy,
    )
    def test_deregister_target_logs_error_code_and_context(
        self, error_code, bucket, tg_arn
    ):
        """Feature: code-quality-improvements, Property 6: Write operation ClientErrors are logged with context (deregister_target)"""
        original_error = make_client_error(error_code)

        with patch("aws_services.boto3") as mock_boto3:
            mock_elbv2 = MagicMock()
            mock_elbv2.deregister_targets.side_effect = original_error
            mock_boto3.resource.return_value = MagicMock()
            mock_boto3.client.return_value = mock_elbv2

            svc = AwsServices(region="us-east-1", bucket=bucket)
            svc.elbv2 = mock_elbv2

            with patch("aws_services.logger") as mock_logger:
                svc.deregister_target(tg_arn, [{"Id": "10.0.0.1", "Port": 3306}])

                # Verify logger.error was called
                mock_logger.error.assert_called()
                log_message = mock_logger.error.call_args[0][0]

                # Log must contain the error code and the target group ARN
                assert (
                    error_code in log_message
                ), f"Expected error code '{error_code}' in log message: {log_message}"
                assert (
                    tg_arn in log_message
                ), f"Expected target group ARN '{tg_arn}' in log message: {log_message}"


# --- Property 8, 11: common.py property tests ---

from common import get_elb_ip_target_from_ip_list, precondition


# --- Strategies for common.py tests ---

# Generate valid IPv4 address strings
ipv4_strategy = st.ip_addresses(v=4).map(str)

# Generate lists of IP address strings
ip_list_strategy = st.lists(ipv4_strategy, min_size=0, max_size=20)

# Generate valid port numbers
port_strategy = st.integers(min_value=1, max_value=65535)

# Generate non-empty error message strings
error_message_strategy = st.text(min_size=1, max_size=200).filter(lambda s: s.strip())


# --- Property 8: Target dictionaries use integer port values ---


class TestProperty8PortType:
    """
    **Validates: Requirements 6.2**

    For any list of IP address strings and any integer port value,
    get_elb_ip_target_from_ip_list SHALL produce target dictionaries
    where the "Port" field is an integer (not a string).
    """

    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        ip_list=ip_list_strategy,
        port=port_strategy,
    )
    def test_target_dicts_have_integer_port_same_vpc(self, ip_list, port, env_setup):
        """Feature: code-quality-improvements, Property 8: Target dictionaries use integer port values (SAME_VPC=true)"""
        # env_setup sets SAME_VPC=true
        LambdaEnv.reset()

        result = get_elb_ip_target_from_ip_list(ip_list, port)

        # Every target dict must have an integer Port value
        assert len(result) == len(ip_list)
        for target in result:
            assert "Port" in target
            assert isinstance(
                target["Port"], int
            ), f"Expected Port to be int, got {type(target['Port']).__name__}: {target['Port']}"
            assert target["Port"] == port

    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        ip_list=st.lists(ipv4_strategy, min_size=1, max_size=20),
        port=port_strategy,
    )
    def test_target_dicts_have_integer_port_different_vpc(
        self, ip_list, port, monkeypatch, env_setup
    ):
        """Feature: code-quality-improvements, Property 8: Target dictionaries use integer port values (SAME_VPC=false)"""
        monkeypatch.setenv("SAME_VPC", "false")
        LambdaEnv.reset()

        result = get_elb_ip_target_from_ip_list(ip_list, port)

        # Every target dict must have an integer Port value
        assert len(result) == len(ip_list)
        for target in result:
            assert "Port" in target
            assert isinstance(
                target["Port"], int
            ), f"Expected Port to be int, got {type(target['Port']).__name__}: {target['Port']}"
            assert target["Port"] == port
            # Different VPC should also have AvailabilityZone
            assert target.get("AvailabilityZone") == "all"


# --- Property 11: Precondition logs error message not boolean value ---


class TestProperty11PreconditionLog:
    """
    **Validates: Requirements 14.6**

    For any falsy pre-condition value and any error message string,
    when precondition is called, the logged error output SHALL contain
    the error message string and SHALL NOT contain the string representation
    of the boolean value as the primary diagnostic.
    """

    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        error_msg=st.text(min_size=1, max_size=100).filter(
            lambda s: s.strip() and s != "False"
        ),
    )
    def test_precondition_logs_error_message_not_boolean(self, error_msg):
        """Feature: code-quality-improvements, Property 11: Precondition logs error message not boolean value"""
        with patch("common.logger") as mock_logger:
            with pytest.raises(ValueError):
                precondition(False, error_msg)

            # Verify logger.error was called
            mock_logger.error.assert_called_once()
            log_message = mock_logger.error.call_args[0][0]

            # The log message SHALL contain the error message
            assert (
                error_msg in log_message
            ), f"Expected error message '{error_msg}' in log output: '{log_message}'"

            # The log format should be "Pre-condition failed: {error_message}"
            # Verify it uses the expected format (not the old format that logged the boolean)
            assert (
                log_message == f"Pre-condition failed: {error_msg}"
            ), f"Log message should follow format 'Pre-condition failed: <msg>'. Got: '{log_message}'"

    @settings(
        max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @given(
        error_msg=st.text(min_size=5, max_size=100).filter(
            lambda s: s.strip() and "False" not in s
        ),
    )
    def test_precondition_log_does_not_contain_false_as_diagnostic(self, error_msg):
        """Feature: code-quality-improvements, Property 11: Precondition logs error message not boolean value (no False in output)"""
        with patch("common.logger") as mock_logger:
            with pytest.raises(ValueError):
                precondition(False, error_msg)

            mock_logger.error.assert_called_once()
            log_message = mock_logger.error.call_args[0][0]

            # When the error message itself doesn't contain "False",
            # the log output should not contain "False" either
            # This verifies the boolean value is NOT being logged
            assert "False" not in log_message, (
                f"Log message should not contain 'False' when error message doesn't. "
                f"Got: '{log_message}'"
            )

            # But it SHOULD contain the actual error message
            assert (
                error_msg in log_message
            ), f"Expected error message '{error_msg}' in log output: '{log_message}'"


# --- Property 7, 10: Handler logic property tests ---

from populate_NLB_TG_with_RDS_RR import (
    should_skip_deregistration,
    log_invocation_summary,
)


# --- Property 7: Circuit breaker skips deregistration above threshold ---


class TestProperty7CircuitBreaker:
    """
    **Validates: Requirements 4.1**

    For any combination of pending deregistration count and registered target count
    where (pending / registered) * 100 > max_deregistration_percent, the
    should_skip_deregistration function SHALL return True.
    """

    @settings(max_examples=100)
    @given(
        pending=st.integers(min_value=1, max_value=10000),
        registered=st.integers(min_value=1, max_value=10000),
        max_percent=st.integers(min_value=1, max_value=100),
    )
    def test_circuit_breaker_returns_true_above_threshold(
        self, pending, registered, max_percent
    ):
        """Feature: code-quality-improvements, Property 7: Circuit breaker skips deregistration above threshold (above)"""
        # **Validates: Requirements 4.1**
        deregistration_percent = (pending / registered) * 100

        # Only test cases where the threshold IS exceeded
        if deregistration_percent > max_percent:
            result = should_skip_deregistration(pending, registered, max_percent)
            assert result is True, (
                f"Expected True when pending={pending}, registered={registered}, "
                f"max_percent={max_percent}, actual_percent={deregistration_percent:.2f}"
            )

    @settings(max_examples=100)
    @given(
        pending=st.integers(min_value=0, max_value=10000),
        registered=st.integers(min_value=1, max_value=10000),
        max_percent=st.integers(min_value=1, max_value=100),
    )
    def test_circuit_breaker_returns_false_at_or_below_threshold(
        self, pending, registered, max_percent
    ):
        """Feature: code-quality-improvements, Property 7: Circuit breaker skips deregistration above threshold (at or below)"""
        # **Validates: Requirements 4.1**
        deregistration_percent = (pending / registered) * 100

        # Only test cases where the threshold is NOT exceeded
        if deregistration_percent <= max_percent:
            result = should_skip_deregistration(pending, registered, max_percent)
            assert result is False, (
                f"Expected False when pending={pending}, registered={registered}, "
                f"max_percent={max_percent}, actual_percent={deregistration_percent:.2f}"
            )

    @settings(max_examples=100)
    @given(
        pending=st.integers(min_value=0, max_value=10000),
        max_percent=st.integers(min_value=1, max_value=100),
    )
    def test_circuit_breaker_returns_false_when_registered_is_zero(
        self, pending, max_percent
    ):
        """Feature: code-quality-improvements, Property 7: Circuit breaker skips deregistration above threshold (zero registered)"""
        # **Validates: Requirements 4.1**
        result = should_skip_deregistration(pending, 0, max_percent)
        assert result is False, (
            f"Expected False when registered_target_count=0, "
            f"pending={pending}, max_percent={max_percent}"
        )


# --- Property 10: Invocation summary log is valid structured JSON ---


class TestProperty10StructuredLog:
    """
    **Validates: Requirements 13.1, 13.2, 13.3**

    For any call to log_invocation_summary, the emitted log message SHALL be
    valid JSON containing the keys: event, request_id, dns_resolved_ips,
    registered, deregistered, and deregistration_skipped.
    """

    @settings(max_examples=100)
    @given(
        request_id=st.text(min_size=0, max_size=100),
        dns_ip_count=st.integers(min_value=0, max_value=10000),
        registered_count=st.integers(min_value=0, max_value=10000),
        deregistered_count=st.integers(min_value=0, max_value=10000),
        skipped_deregistration=st.booleans(),
    )
    def test_invocation_summary_emits_valid_json_with_required_keys(
        self,
        request_id,
        dns_ip_count,
        registered_count,
        deregistered_count,
        skipped_deregistration,
    ):
        """Feature: code-quality-improvements, Property 10: Invocation summary log is valid structured JSON"""
        # **Validates: Requirements 13.1, 13.2, 13.3**
        with patch("populate_NLB_TG_with_RDS_RR.logger") as mock_logger:
            log_invocation_summary(
                request_id=request_id,
                dns_ip_count=dns_ip_count,
                registered_count=registered_count,
                deregistered_count=deregistered_count,
                skipped_deregistration=skipped_deregistration,
            )

            # Verify logger.info was called exactly once
            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args[0][0]

            # Parse the log message as JSON - must not raise
            import json as json_lib

            parsed = json_lib.loads(log_message)

            # Verify all required keys are present
            required_keys = {
                "event",
                "request_id",
                "dns_resolved_ips",
                "registered",
                "deregistered",
                "deregistration_skipped",
            }
            assert required_keys.issubset(
                parsed.keys()
            ), f"Missing keys: {required_keys - set(parsed.keys())}. Got: {set(parsed.keys())}"

            # Verify values match inputs
            assert parsed["event"] == "invocation_summary"
            assert parsed["request_id"] == request_id
            assert parsed["dns_resolved_ips"] == dns_ip_count
            assert parsed["registered"] == registered_count
            assert parsed["deregistered"] == deregistered_count
            assert parsed["deregistration_skipped"] == skipped_deregistration
