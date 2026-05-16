"""Unit tests for DNS functions in common.py"""
import pytest
from unittest.mock import patch, MagicMock

import dns.resolver

import common


class TestDnsLookup:
    """Tests for common.dns_lookup"""

    @patch("common.dns.resolver.Resolver")
    def test_success_returns_list_of_ips(self, mock_resolver_class, env_setup):
        """dns_lookup returns a list of string IPs on success."""
        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver

        # Simulate dns.resolver answer objects that convert to string IPs
        mock_answer_1 = MagicMock()
        mock_answer_1.__str__ = lambda self: "10.0.1.5"
        mock_answer_2 = MagicMock()
        mock_answer_2.__str__ = lambda self: "10.0.2.8"
        mock_resolver.resolve.return_value = [mock_answer_1, mock_answer_2]

        result = common.dns_lookup("replica1.rds.amazonaws.com", "A")

        assert result == ["10.0.1.5", "10.0.2.8"]
        mock_resolver.resolve.assert_called_once_with("replica1.rds.amazonaws.com", "A")

    @patch("common.dns.resolver.Resolver")
    def test_nxdomain_exception_propagates(self, mock_resolver_class, env_setup):
        """dns_lookup propagates NXDOMAIN exception to caller."""
        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = dns.resolver.NXDOMAIN()

        with pytest.raises(dns.resolver.NXDOMAIN):
            common.dns_lookup("nonexistent.rds.amazonaws.com", "A")

    @patch("common.dns.resolver.Resolver")
    def test_timeout_exception_propagates(self, mock_resolver_class, env_setup):
        """dns_lookup propagates Timeout exception to caller."""
        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = dns.resolver.LifetimeTimeout(
            timeout=10.0, errors=[]
        )

        with pytest.raises(dns.resolver.LifetimeTimeout):
            common.dns_lookup("slow.rds.amazonaws.com", "A")

    @patch("common.dns.resolver.Resolver")
    def test_resolver_configured_correctly(self, mock_resolver_class, env_setup):
        """dns_lookup configures resolver with rotate, timeout, and lifetime."""
        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.return_value = []

        common.dns_lookup("replica1.rds.amazonaws.com", "A")

        assert mock_resolver.rotate is True
        assert mock_resolver.timeout == 1  # DNS_RESOLVER_TIMEOUT
        assert mock_resolver.lifetime == 10  # DNS_RESOLVER_LIFETIME


class TestDnsLookupWithRetry:
    """Tests for common.dns_lookup_with_retry"""

    @patch("common.dns_lookup")
    def test_retries_on_failure_then_succeeds(self, mock_dns_lookup, env_setup):
        """dns_lookup_with_retry retries on failure and returns result on success."""
        # Fail twice, then succeed on third attempt
        mock_dns_lookup.side_effect = [
            dns.resolver.NXDOMAIN(),
            dns.resolver.NoAnswer(response=MagicMock()),
            ["10.0.1.5", "10.0.2.8"],
        ]

        result = common.dns_lookup_with_retry("replica1.rds.amazonaws.com", "A", 3)

        assert result == {"10.0.1.5", "10.0.2.8"}
        assert mock_dns_lookup.call_count == 3

    @patch("common.dns_lookup")
    def test_returns_empty_set_after_exhaustion(self, mock_dns_lookup, env_setup):
        """dns_lookup_with_retry returns empty set when all retries are exhausted."""
        mock_dns_lookup.side_effect = dns.resolver.NXDOMAIN()

        result = common.dns_lookup_with_retry("failing.rds.amazonaws.com", "A", 3)

        assert result == set()
        assert mock_dns_lookup.call_count == 3

    @patch("common.dns_lookup")
    def test_breaks_on_first_success(self, mock_dns_lookup, env_setup):
        """dns_lookup_with_retry stops retrying after first successful lookup."""
        mock_dns_lookup.return_value = ["10.0.1.5"]

        result = common.dns_lookup_with_retry("replica1.rds.amazonaws.com", "A", 5)

        assert result == {"10.0.1.5"}
        assert mock_dns_lookup.call_count == 1

    @patch("common.dns_lookup")
    def test_returns_empty_set_on_empty_results(self, mock_dns_lookup, env_setup):
        """dns_lookup_with_retry handles empty results from dns_lookup gracefully."""
        # Return empty list on all attempts (no exception, just empty)
        mock_dns_lookup.return_value = []

        result = common.dns_lookup_with_retry("replica1.rds.amazonaws.com", "A", 3)

        assert result == set()
        assert mock_dns_lookup.call_count == 3


class TestGetRdsReplicaIpsFromDns:
    """Tests for common.get_rds_replica_ips_from_dns"""

    @patch("common.dns_lookup_with_retry")
    def test_aggregates_ips_from_multiple_names(self, mock_retry, env_setup):
        """get_rds_replica_ips_from_dns aggregates IPs from multiple DNS names."""
        mock_retry.side_effect = [
            {"10.0.1.5", "10.0.1.6"},
            {"10.0.2.8"},
            {"10.0.3.10", "10.0.3.11"},
        ]

        dns_names = [
            "replica1.rds.amazonaws.com",
            "replica2.rds.amazonaws.com",
            "replica3.rds.amazonaws.com",
        ]
        result = common.get_rds_replica_ips_from_dns(dns_names, "A", 3)

        assert result == {"10.0.1.5", "10.0.1.6", "10.0.2.8", "10.0.3.10", "10.0.3.11"}
        assert mock_retry.call_count == 3

    @patch("common.dns_lookup_with_retry")
    def test_handles_partial_failures(self, mock_retry, env_setup):
        """get_rds_replica_ips_from_dns returns partial results when some names fail."""
        mock_retry.side_effect = [
            {"10.0.1.5"},
            Exception("Unexpected DNS failure"),
            {"10.0.3.10"},
        ]

        dns_names = [
            "replica1.rds.amazonaws.com",
            "failing.rds.amazonaws.com",
            "replica3.rds.amazonaws.com",
        ]
        result = common.get_rds_replica_ips_from_dns(dns_names, "A", 3)

        assert result == {"10.0.1.5", "10.0.3.10"}

    @patch("common.dns_lookup_with_retry")
    def test_empty_dns_name_list(self, mock_retry, env_setup):
        """get_rds_replica_ips_from_dns returns empty set for empty name list."""
        result = common.get_rds_replica_ips_from_dns([], "A", 3)

        assert result == set()
        mock_retry.assert_not_called()

    @patch("common.dns_lookup_with_retry")
    def test_all_lookups_fail(self, mock_retry, env_setup):
        """get_rds_replica_ips_from_dns returns empty set when all lookups return empty."""
        mock_retry.return_value = set()

        dns_names = ["replica1.rds.amazonaws.com", "replica2.rds.amazonaws.com"]
        result = common.get_rds_replica_ips_from_dns(dns_names, "A", 3)

        assert result == set()
