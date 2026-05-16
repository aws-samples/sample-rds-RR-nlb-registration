"""Unit tests for Lambda handler (populate_NLB_TG_with_RDS_RR.py)."""
import json
import pytest
from unittest.mock import patch, MagicMock

from botocore.exceptions import ClientError

from populate_NLB_TG_with_RDS_RR import lambda_handler


@pytest.fixture
def mock_context():
    """Create a mock Lambda context object with aws_request_id."""
    context = MagicMock()
    context.aws_request_id = "test-request-id-12345"
    return context


class TestHandlerHappyPath:
    """Test happy path: DNS resolves, registers new IPs, writes state."""

    @patch("populate_NLB_TG_with_RDS_RR.AwsServices")
    @patch("populate_NLB_TG_with_RDS_RR.get_rds_replica_ips_from_dns")
    def test_happy_path_registers_new_ips_and_writes_state(
        self, mock_dns, mock_aws_cls, env_setup, mock_context
    ):
        """DNS resolves IPs, some are new (not in target group), registration succeeds, state written to S3."""
        # DNS returns 3 IPs
        mock_dns.return_value = {"10.0.1.5", "10.0.2.8", "10.0.3.12"}

        # Set up AwsServices mock
        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws

        # Target group currently has 1 IP (10.0.1.5), so 2 new IPs need registration
        mock_aws.get_ip_target_list_by_target_group_arn.return_value = ["10.0.1.5"]

        # S3 has previous state with the 1 known IP
        mock_aws.download_elb_ip_from_s3.side_effect = [
            {"IPList": ["10.0.1.5"], "IPCount": 1},  # active_ip.json
            {},  # pending_ip.json (no pending deregistrations)
        ]

        # Registration succeeds
        mock_aws.register_target.return_value = True

        result = lambda_handler({}, mock_context)

        # Handler should not return None (DNS had IPs)
        assert result is None  # lambda_handler has no explicit return on success

        # Registration was called with the 2 new IPs
        mock_aws.register_target.assert_called_once()
        call_args = mock_aws.register_target.call_args
        tg_arn = call_args[0][0]
        targets = call_args[0][1]
        assert tg_arn == "arn:aws:elasticloadbalancing:us-east-1:12345:targetgroup/TG-mocked/12345abcde"
        registered_ips = {t["Id"] for t in targets}
        assert registered_ips == {"10.0.2.8", "10.0.3.12"}

        # State was written to S3 (active + pending)
        assert mock_aws.write_content_to_s3.call_count == 2


class TestHandlerEarlyExit:
    """Test early exit: DNS returns no IPs, handler returns None."""

    @patch("populate_NLB_TG_with_RDS_RR.AwsServices")
    @patch("populate_NLB_TG_with_RDS_RR.get_rds_replica_ips_from_dns")
    def test_dns_returns_no_ips_handler_returns_none(
        self, mock_dns, mock_aws_cls, env_setup, mock_context
    ):
        """When DNS returns no IPs, handler returns None and makes no target group changes."""
        # DNS returns empty set
        mock_dns.return_value = set()

        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws

        result = lambda_handler({}, mock_context)

        # Handler returns None on early exit
        assert result is None

        # No target group operations should have been called
        mock_aws.get_ip_target_list_by_target_group_arn.assert_not_called()
        mock_aws.register_target.assert_not_called()
        mock_aws.deregister_target.assert_not_called()
        mock_aws.write_content_to_s3.assert_not_called()


class TestHandlerCircuitBreaker:
    """Test circuit breaker: deregistration skipped when threshold exceeded."""

    @patch("populate_NLB_TG_with_RDS_RR.AwsServices")
    @patch("populate_NLB_TG_with_RDS_RR.get_rds_replica_ips_from_dns")
    def test_circuit_breaker_skips_deregistration(
        self, mock_dns, mock_aws_cls, env_setup, mock_context
    ):
        """When pending deregistration exceeds threshold, deregistration is skipped but state is still written."""
        # DNS returns only 1 IP (simulating partial DNS failure)
        mock_dns.return_value = {"10.0.1.5"}

        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws

        # Target group has 4 IPs registered - 3 are no longer in DNS
        mock_aws.get_ip_target_list_by_target_group_arn.return_value = [
            "10.0.1.5", "10.0.2.8", "10.0.3.12", "10.0.4.7"
        ]

        # Previous state shows all 4 IPs were active, and 3 IPs have been pending
        # for enough invocations to trigger deregistration
        mock_aws.download_elb_ip_from_s3.side_effect = [
            {"IPList": ["10.0.1.5", "10.0.2.8", "10.0.3.12", "10.0.4.7"], "IPCount": 4},  # active
            {"10.0.2.8": 3, "10.0.3.12": 3, "10.0.4.7": 3},  # pending (count >= INVOCATIONS_BEFORE_DEREGISTRATION=3)
        ]

        # No new IPs to register
        mock_aws.register_target.return_value = False

        result = lambda_handler({}, mock_context)

        # Deregistration should NOT have been called (circuit breaker: 3/4 = 75% > 50%)
        mock_aws.deregister_target.assert_not_called()

        # State should still be written to S3 (pending IP state)
        assert mock_aws.write_content_to_s3.call_count >= 1


class TestHandlerS3WriteFailure:
    """Test S3 write failure: exception propagates from handler."""

    @patch("populate_NLB_TG_with_RDS_RR.AwsServices")
    @patch("populate_NLB_TG_with_RDS_RR.get_rds_replica_ips_from_dns")
    def test_s3_write_failure_propagates(
        self, mock_dns, mock_aws_cls, env_setup, mock_context
    ):
        """When write_content_to_s3 raises ClientError, exception propagates from handler."""
        # DNS returns IPs
        mock_dns.return_value = {"10.0.1.5", "10.0.2.8"}

        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws

        # Target group has 1 IP, so 1 new IP needs registration
        mock_aws.get_ip_target_list_by_target_group_arn.return_value = ["10.0.1.5"]

        # No previous state
        mock_aws.download_elb_ip_from_s3.return_value = {}

        # Registration succeeds
        mock_aws.register_target.return_value = True

        # S3 write fails with ClientError
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}
        mock_aws.write_content_to_s3.side_effect = ClientError(error_response, "PutObject")

        with pytest.raises(ClientError) as exc_info:
            lambda_handler({}, mock_context)

        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"


class TestHandlerFirstRun:
    """Test first run: no S3 state, registers all DNS IPs."""

    @patch("populate_NLB_TG_with_RDS_RR.AwsServices")
    @patch("populate_NLB_TG_with_RDS_RR.get_rds_replica_ips_from_dns")
    def test_first_run_registers_all_dns_ips(
        self, mock_dns, mock_aws_cls, env_setup, mock_context
    ):
        """On first run with no S3 state, all DNS IPs get registered."""
        # DNS returns 3 IPs
        mock_dns.return_value = {"10.0.1.5", "10.0.2.8", "10.0.3.12"}

        mock_aws = MagicMock()
        mock_aws_cls.return_value = mock_aws

        # Target group is empty (first run)
        mock_aws.get_ip_target_list_by_target_group_arn.return_value = []

        # S3 returns empty dicts (no previous state - first invocation)
        mock_aws.download_elb_ip_from_s3.return_value = {}

        # Registration succeeds
        mock_aws.register_target.return_value = True

        result = lambda_handler({}, mock_context)

        # Registration was called with all 3 IPs
        mock_aws.register_target.assert_called_once()
        call_args = mock_aws.register_target.call_args
        targets = call_args[0][1]
        registered_ips = {t["Id"] for t in targets}
        assert registered_ips == {"10.0.1.5", "10.0.2.8", "10.0.3.12"}

        # All targets should have integer port
        for target in targets:
            assert isinstance(target["Port"], int)
            assert target["Port"] == 3306

        # State was written to S3
        assert mock_aws.write_content_to_s3.call_count == 2

        # Verify active IP state contains all DNS IPs
        active_write_call = mock_aws.write_content_to_s3.call_args_list[0]
        active_content = json.loads(active_write_call[0][0])
        assert set(active_content["IPList"]) == {"10.0.1.5", "10.0.2.8", "10.0.3.12"}
        assert active_content["IPCount"] == 3
