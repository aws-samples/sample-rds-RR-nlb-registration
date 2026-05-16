"""Unit tests for AwsServices class."""
import json
import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError, BotoCoreError

from aws_services import AwsServices, RETRY_CONFIG


class TestAwsServicesInit:
    """Tests for AwsServices initialization and retry config."""

    @patch("aws_services.boto3")
    def test_init_creates_clients_with_retry_config(self, mock_boto3, env_setup):
        """Verify retry config is applied to all clients."""
        svc = AwsServices(region="us-east-1", bucket="test-bucket")

        mock_boto3.resource.assert_called_once_with(
            "s3", region_name="us-east-1", config=RETRY_CONFIG
        )
        # s3_client and elbv2 are both created via boto3.client
        calls = mock_boto3.client.call_args_list
        assert len(calls) == 2
        assert calls[0] == (("s3",), {"region_name": "us-east-1", "config": RETRY_CONFIG})
        assert calls[1] == (("elbv2",), {"region_name": "us-east-1", "config": RETRY_CONFIG})

    @patch("aws_services.boto3")
    def test_init_stores_region_and_bucket(self, mock_boto3, env_setup):
        """Verify region and bucket are stored as attributes."""
        svc = AwsServices(region="eu-west-1", bucket="my-bucket")
        assert svc.region == "eu-west-1"
        assert svc.bucket == "my-bucket"

    @patch("aws_services.boto3")
    def test_init_raises_on_empty_region(self, mock_boto3, env_setup):
        """Verify precondition rejects empty region."""
        with pytest.raises(ValueError):
            AwsServices(region="", bucket="test-bucket")

    @patch("aws_services.boto3")
    def test_init_raises_on_empty_bucket(self, mock_boto3, env_setup):
        """Verify precondition rejects empty bucket."""
        with pytest.raises(ValueError):
            AwsServices(region="us-east-1", bucket="")

    def test_retry_config_values(self):
        """Verify RETRY_CONFIG has expected retry settings."""
        assert RETRY_CONFIG.retries["max_attempts"] == 3
        assert RETRY_CONFIG.retries["mode"] == "adaptive"


class TestWriteContentToS3:
    """Tests for write_content_to_s3 method."""

    @patch("aws_services.boto3")
    def test_success_writes_content(self, mock_boto3, env_setup):
        """Verify successful write calls S3 Object.put with correct body."""
        mock_s3_resource = MagicMock()
        mock_s3_object = MagicMock()
        mock_s3_resource.Object.return_value = mock_s3_object
        mock_boto3.resource.return_value = mock_s3_resource

        svc = AwsServices(region="us-east-1", bucket="test-bucket")
        svc.write_content_to_s3('{"key": "value"}', "state/active_ip.json")

        mock_s3_resource.Object.assert_called_once_with("test-bucket", "state/active_ip.json")
        mock_s3_object.put.assert_called_once_with(Body='{"key": "value"}')

    @patch("aws_services.boto3")
    def test_client_error_reraises(self, mock_boto3, env_setup):
        """Verify ClientError is re-raised after logging."""
        mock_s3_resource = MagicMock()
        mock_s3_object = MagicMock()
        mock_s3_resource.Object.return_value = mock_s3_object
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}
        mock_s3_object.put.side_effect = ClientError(error_response, "PutObject")
        mock_boto3.resource.return_value = mock_s3_resource

        svc = AwsServices(region="us-east-1", bucket="test-bucket")

        with pytest.raises(ClientError) as exc_info:
            svc.write_content_to_s3("content", "key.json")
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"

    @patch("aws_services.boto3")
    def test_botocore_error_reraises(self, mock_boto3, env_setup):
        """Verify BotoCoreError is re-raised after logging."""
        mock_s3_resource = MagicMock()
        mock_s3_object = MagicMock()
        mock_s3_resource.Object.return_value = mock_s3_object
        mock_s3_object.put.side_effect = BotoCoreError()
        mock_boto3.resource.return_value = mock_s3_resource

        svc = AwsServices(region="us-east-1", bucket="test-bucket")

        with pytest.raises(BotoCoreError):
            svc.write_content_to_s3("content", "key.json")


class TestDownloadElbIpFromS3:
    """Tests for download_elb_ip_from_s3 method."""

    @patch("aws_services.boto3")
    def test_success_returns_parsed_json(self, mock_boto3, env_setup):
        """Verify successful download returns parsed JSON content."""
        mock_s3_client = MagicMock()
        mock_body = MagicMock()
        state_data = {"IPList": ["10.0.1.5", "10.0.2.8"], "IPCount": 2}
        mock_body.read.return_value = json.dumps(state_data).encode()
        mock_s3_client.get_object.return_value = {"Body": mock_body}
        mock_boto3.client.return_value = mock_s3_client

        svc = AwsServices(region="us-east-1", bucket="test-bucket")
        result = svc.download_elb_ip_from_s3("state/active_ip.json")

        assert result == state_data
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="state/active_ip.json"
        )

    @patch("aws_services.boto3")
    def test_no_such_key_returns_empty_dict(self, mock_boto3, env_setup):
        """Verify NoSuchKey error returns empty dict (first invocation)."""
        mock_s3_client = MagicMock()
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
        mock_s3_client.get_object.side_effect = ClientError(error_response, "GetObject")
        mock_boto3.client.return_value = mock_s3_client

        svc = AwsServices(region="us-east-1", bucket="test-bucket")
        result = svc.download_elb_ip_from_s3("state/active_ip.json")

        assert result == {}

    @patch("aws_services.boto3")
    def test_other_client_error_raises(self, mock_boto3, env_setup):
        """Verify non-NoSuchKey ClientError is re-raised."""
        mock_s3_client = MagicMock()
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}
        mock_s3_client.get_object.side_effect = ClientError(error_response, "GetObject")
        mock_boto3.client.return_value = mock_s3_client

        svc = AwsServices(region="us-east-1", bucket="test-bucket")

        with pytest.raises(ClientError) as exc_info:
            svc.download_elb_ip_from_s3("state/active_ip.json")
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"

    @patch("aws_services.boto3")
    def test_json_decode_error_raises(self, mock_boto3, env_setup):
        """Verify JSONDecodeError from corrupted state file is re-raised."""
        mock_s3_client = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = b"not valid json {{"
        mock_s3_client.get_object.return_value = {"Body": mock_body}
        mock_boto3.client.return_value = mock_s3_client

        svc = AwsServices(region="us-east-1", bucket="test-bucket")

        with pytest.raises(json.JSONDecodeError):
            svc.download_elb_ip_from_s3("state/active_ip.json")


class TestRegisterTarget:
    """Tests for register_target method."""

    @patch("aws_services.boto3")
    def test_success_returns_true(self, mock_boto3, env_setup):
        """Verify successful registration returns True."""
        mock_elbv2 = MagicMock()
        mock_boto3.client.return_value = mock_elbv2

        svc = AwsServices(region="us-east-1", bucket="test-bucket")
        targets = [{"Id": "10.0.1.5", "Port": 3306}]
        result = svc.register_target("arn:aws:elasticloadbalancing:tg/test", targets)

        assert result is True
        mock_elbv2.register_targets.assert_called_once_with(
            TargetGroupArn="arn:aws:elasticloadbalancing:tg/test",
            Targets=targets,
        )

    @patch("aws_services.boto3")
    def test_client_error_returns_false(self, mock_boto3, env_setup):
        """Verify ClientError during registration returns False."""
        mock_elbv2 = MagicMock()
        error_response = {"Error": {"Code": "TargetGroupNotFound", "Message": "Not found"}}
        mock_elbv2.register_targets.side_effect = ClientError(error_response, "RegisterTargets")
        mock_boto3.client.return_value = mock_elbv2

        svc = AwsServices(region="us-east-1", bucket="test-bucket")
        targets = [{"Id": "10.0.1.5", "Port": 3306}]
        result = svc.register_target("arn:aws:elasticloadbalancing:tg/test", targets)

        assert result is False


class TestDeregisterTarget:
    """Tests for deregister_target method."""

    @patch("aws_services.boto3")
    def test_success_calls_deregister(self, mock_boto3, env_setup):
        """Verify successful deregistration calls ELBv2 API."""
        mock_elbv2 = MagicMock()
        mock_boto3.client.return_value = mock_elbv2

        svc = AwsServices(region="us-east-1", bucket="test-bucket")
        targets = [{"Id": "10.0.1.5", "Port": 3306}]
        svc.deregister_target("arn:aws:elasticloadbalancing:tg/test", targets)

        mock_elbv2.deregister_targets.assert_called_once_with(
            TargetGroupArn="arn:aws:elasticloadbalancing:tg/test",
            Targets=targets,
        )

    @patch("aws_services.boto3")
    def test_client_error_does_not_raise(self, mock_boto3, env_setup):
        """Verify ClientError during deregistration is logged but not raised."""
        mock_elbv2 = MagicMock()
        error_response = {"Error": {"Code": "InvalidTarget", "Message": "Bad target"}}
        mock_elbv2.deregister_targets.side_effect = ClientError(error_response, "DeregisterTargets")
        mock_boto3.client.return_value = mock_elbv2

        svc = AwsServices(region="us-east-1", bucket="test-bucket")
        targets = [{"Id": "10.0.1.5", "Port": 3306}]
        # Should not raise
        svc.deregister_target("arn:aws:elasticloadbalancing:tg/test", targets)


class TestGetIpTargetListByTargetGroupArn:
    """Tests for get_ip_target_list_by_target_group_arn method."""

    @patch("aws_services.boto3")
    def test_success_returns_ip_list(self, mock_boto3, env_setup):
        """Verify successful describe returns list of target IPs."""
        mock_elbv2 = MagicMock()
        mock_elbv2.describe_target_health.return_value = {
            "TargetHealthDescriptions": [
                {"Target": {"Id": "10.0.1.5", "Port": 3306}},
                {"Target": {"Id": "10.0.2.8", "Port": 3306}},
            ]
        }
        mock_boto3.client.return_value = mock_elbv2

        svc = AwsServices(region="us-east-1", bucket="test-bucket")
        result = svc.get_ip_target_list_by_target_group_arn("arn:tg/test")

        assert result == ["10.0.1.5", "10.0.2.8"]
        mock_elbv2.describe_target_health.assert_called_once_with(
            TargetGroupArn="arn:tg/test"
        )

    @patch("aws_services.boto3")
    def test_empty_target_group_returns_empty_list(self, mock_boto3, env_setup):
        """Verify empty target group returns empty list."""
        mock_elbv2 = MagicMock()
        mock_elbv2.describe_target_health.return_value = {
            "TargetHealthDescriptions": []
        }
        mock_boto3.client.return_value = mock_elbv2

        svc = AwsServices(region="us-east-1", bucket="test-bucket")
        result = svc.get_ip_target_list_by_target_group_arn("arn:tg/test")

        assert result == []

    @patch("aws_services.boto3")
    def test_client_error_returns_empty_list(self, mock_boto3, env_setup):
        """Verify ClientError returns empty list without raising."""
        mock_elbv2 = MagicMock()
        error_response = {"Error": {"Code": "TargetGroupNotFound", "Message": "Not found"}}
        mock_elbv2.describe_target_health.side_effect = ClientError(
            error_response, "DescribeTargetHealth"
        )
        mock_boto3.client.return_value = mock_elbv2

        svc = AwsServices(region="us-east-1", bucket="test-bucket")
        result = svc.get_ip_target_list_by_target_group_arn("arn:tg/test")

        assert result == []
