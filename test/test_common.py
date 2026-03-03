import pytest
from unittest.mock import patch, MagicMock, call

MOCKED_DNS_NAME = "mocked.domain.name.com"
MOCKED_DNS_RECORD_TYPE = "A"
MOCKED_DNS_SERVERS = ["1.1.1.1", "2.2.2.2"]


@patch("common.logger", return_value=MagicMock())
def test_precondition(mocked_logger, env_setup):
    import common as common_util

    # Case 1: When pre-condition is True. No exception should be raised
    pre_condition = True
    mocked_error_messages = "mocked_error_messages"
    common_util.precondition(pre_condition, mocked_error_messages)
    mocked_logger.error.assert_not_called()

    # Case 2: When pre-condition is False. exception is raised
    pre_condition = False
    with pytest.raises(ValueError):
        common_util.precondition(pre_condition, mocked_error_messages)
        mocked_logger.error.assert_called_once_with(mocked_error_messages)


@patch("common.logger", return_value=MagicMock())
def test_get_pending_registration_ip_set(mocked_logger):
    import common as common_util

    # Return the IPs that are in DNS but not in the target group
    ip_from_dns_set = {"1.1.1.1", "2.2.2.2", "3.3.3.3"}
    ip_from_target_group_set = {"1.1.1.1"}

    expected_result = {"2.2.2.2", "3.3.3.3"}
    actual_result = common_util.get_pending_registration_ip_set(
        ip_from_dns_set,
        ip_from_target_group_set
    )
    assert actual_result == expected_result


@patch("common.logger", return_value=MagicMock())
def test_get_invocation_count_per_pending_deregistration_ip_without_pending(
        mocked_logger,
):
    # When there is no pending IP from the previous invocation
    # Pending deregistration IPs (Without considering INVOCATIONS_BEFORE_DEREGISTRATION) are:
    # 1. In the active IP list from the previous invocation but no longer in the DNS
    # 2. Currently registered but no longer in the DNS

    import common as common_util

    ip_from_dns_set = {"1.1.1.1", "2.2.2.2", "3.3.3.3"}
    ip_from_target_group_set = {"1.1.1.1", "5.5.5.5"}
    active_ip_set_from_previous_invocation = {"2.2.2.2", "6.6.6.6"}

    # 6.6.6.6 is no longer in the DNS while it is in the active IP list from the previous invocation
    # 5.5.5.5 is no longer in the DNS while it is in the target group
    pending_ip_dict_from_previous_invocation = {}
    expected_result = {"5.5.5.5": 1, "6.6.6.6": 1}
    actual_result = common_util.get_invocation_count_per_pending_deregistration_ip(
        ip_from_dns_set,
        ip_from_target_group_set,
        active_ip_set_from_previous_invocation,
        pending_ip_dict_from_previous_invocation,
    )

    assert actual_result == expected_result


@patch("common.logger", return_value=MagicMock())
def test_get_invocation_count_per_pending_deregistration_ip_with_pending(mocked_logger):
    # When there are pending IPs from the previous invocation
    # Pending deregistration IPs (Without considering INVOCATIONS_BEFORE_DEREGISTRATION) are:
    # 1. In the active IP list from the previous invocation but no longer in the DNS
    # 2. Currently registered but no longer in the DNS

    import common as common_util

    ip_from_dns_set = {"1.1.1.1", "2.2.2.2", "3.3.3.3"}
    ip_from_target_group_set = {"1.1.1.1", "5.5.5.5"}
    active_ip_set_from_previous_invocation = {"2.2.2.2", "6.6.6.6"}

    pending_ip_dict_from_previous_invocation = {
        "1.1.1.1": 1,
        "2.2.2.2": 2,
        "5.5.5.5": 3,
    }
    expected_result = {"5.5.5.5": 4, "6.6.6.6": 1}
    actual_result = common_util.get_invocation_count_per_pending_deregistration_ip(
        ip_from_dns_set,
        ip_from_target_group_set,
        active_ip_set_from_previous_invocation,
        pending_ip_dict_from_previous_invocation,
    )
    assert actual_result == expected_result


@patch("common.logger", return_value=MagicMock())
def test_get_pending_deregistration_ip_set(mocked_logger):
    import common as common_util

    invocation_count_per_pending_deregistration_ip = {
        "1.1.1.1": 1,
        "2.2.2.2": 2,
        "3.3.3.3": 3,
    }
    invocation_before_deregistration = 3
    actual_result = common_util.get_pending_deregistration_ip_set(
        invocation_count_per_pending_deregistration_ip, invocation_before_deregistration
    )
    expected_result = {"3.3.3.3"}
    assert actual_result == expected_result


def test_get_elb_ip_target_from_ip_list_same_vpc():
    import common as common_util

    ip_list = ["1.1.1.1", "2.2.2.2"]
    elb_listener = "80"
    actual_result = common_util.get_elb_ip_target_from_ip_list(ip_list, elb_listener)
    expected_result = [
        {"Id": "1.1.1.1", "Port": "80", },
        {"Id": "2.2.2.2", "Port": "80", },
    ]
    assert actual_result == expected_result


def test_get_elb_ip_target_from_ip_list_different_vpc():
    import common as common_util

    ip_list = ["1.1.1.1", "2.2.2.2"]
    elb_listener = "80"
    with patch("common.LambdaEnv.SAME_VPC", False):
        actual_result = common_util.get_elb_ip_target_from_ip_list(
            ip_list, elb_listener
        )
        expected_result = [
            {"Id": "1.1.1.1", "Port": "80", "AvailabilityZone": "all"},
            {"Id": "2.2.2.2", "Port": "80", "AvailabilityZone": "all"},
        ]
        assert actual_result == expected_result
