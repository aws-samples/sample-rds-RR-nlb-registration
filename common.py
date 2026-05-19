import logging
from typing import Dict, List, Set

import dns.resolver
from constant import LambdaEnv

# Timeout on one NS
DNS_RESOLVER_TIMEOUT = 1
# Timeout through out all of the NS
DNS_RESOLVER_LIFETIME = 10

# DNS record type constant
DNS_RECORD_TYPE_A = "A"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def precondition(pre_condition: bool, error_message: str) -> None:
    """
    Raise ValueError when pre-condition is False
    :param pre_condition: pre-condition statement
    :param error_message: error message passed to the exception
    """
    if not pre_condition:
        logger.error(f"Pre-condition failed: {error_message}")
        raise ValueError(error_message)


def dns_lookup(domain_name: str, record_type: str) -> List[str]:
    """
    Get DNS lookup results using the system default DNS resolver.

    Uses the default resolver provided by the Lambda runtime. RDS DNS names
    (e.g., replica1.abc123.us-east-1.rds.amazonaws.com) are publicly resolvable
    and do not require VPC placement.

    Raises dns.resolver exceptions on failure, allowing caller to implement retry logic.

    :param domain_name: DNS name to resolve
    :param record_type: DNS record type (e.g., "A", "AAAA", "NS")
    :return: list of DNS lookup results
    :raises: dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout, etc.
    """
    my_resolver = dns.resolver.Resolver()
    my_resolver.rotate = True  # Randomize order of results for load distribution
    my_resolver.timeout = DNS_RESOLVER_TIMEOUT
    my_resolver.lifetime = DNS_RESOLVER_LIFETIME

    logger.info(f"Resolving query {domain_name} (type: {record_type})")

    # Let exceptions propagate to caller for retry logic
    lookup_answers = my_resolver.resolve(domain_name, record_type)
    lookup_result_list = [str(answer) for answer in lookup_answers]

    logger.debug(
        f"DNS lookup returned {len(lookup_result_list)} result(s): {lookup_result_list}"
    )
    return lookup_result_list


def dns_lookup_with_retry(
    domain_name: str, record_type: str, total_retry_count: int
) -> Set[str]:
    """
    Get DNS lookup results with retry using VPC DNS resolver.

    :param domain_name: DNS name to resolve
    :param record_type: DNS record type (e.g., "A", "AAAA")
    :param total_retry_count: Maximum number of lookup attempts on failure
    :return: Set of resolved IP addresses (typically 1 IP for RDS replicas)
    """
    dns_lookup_result_set: Set[str] = set()
    attempt = 1

    while attempt <= total_retry_count:
        try:
            logger.info(
                f"DNS lookup attempt {attempt}/{total_retry_count} for {domain_name}"
            )
            lookup_result_per_attempt = dns_lookup(domain_name, record_type)

            if lookup_result_per_attempt:
                dns_lookup_result_set.update(lookup_result_per_attempt)
                logger.debug(
                    f"DNS lookup succeeded on attempt {attempt}. "
                    f"Total IPs resolved: {len(dns_lookup_result_set)}. "
                    f"IPs: {dns_lookup_result_set}"
                )
                # Success - no need to retry for RDS (stable IPs)
                break
            else:
                logger.warning(f"DNS lookup returned empty result on attempt {attempt}")

        except Exception as e:
            logger.error(
                f"DNS lookup failed on attempt {attempt}/{total_retry_count} "
                f"for {domain_name}: {type(e).__name__}: {e}"
            )

            if attempt >= total_retry_count:
                logger.error(
                    f"All {total_retry_count} DNS lookup attempts failed for {domain_name}. "
                    f"Returning empty result."
                )
                # Return empty set after all retries exhausted
                return dns_lookup_result_set

        attempt += 1

    return dns_lookup_result_set


def get_rds_replica_ips_from_dns(
    dns_name_list: List[str], record_type: str, max_lookup_per_invocation: int
) -> Set[str]:
    """
    Resolve multiple RDS replica DNS names and aggregate all IPs.

    RDS replica DNS names are publicly resolvable (managed by Route 53) and resolve
    to private IPs. No VPC placement is required for DNS resolution.

    :param dns_name_list: List of RDS replica DNS names
    :param record_type: DNS record type (typically "A")
    :param max_lookup_per_invocation: Max DNS lookup retries per name
    :return: Set of all resolved IP addresses across all replicas
    """
    aggregated_ips: Set[str] = set()

    for dns_name in dns_name_list:
        try:
            logger.info(f"Resolving RDS DNS name: {dns_name}")
            ips = dns_lookup_with_retry(
                dns_name, record_type, max_lookup_per_invocation
            )
            if ips:
                logger.debug(f"Resolved {len(ips)} IP(s) for {dns_name}: {ips}")
                aggregated_ips.update(ips)
            else:
                logger.warning(f"No IPs resolved for DNS name: {dns_name}")
        except Exception as e:
            logger.error(f"Failed to resolve DNS name {dns_name}: {e}")
            continue

    logger.info(f"Total aggregated IPs from all DNS names: {len(aggregated_ips)}")
    return aggregated_ips


def get_pending_registration_ip_set(
    ip_from_dns_set: Set[str], ip_from_target_group_set: Set[str]
) -> Set[str]:
    """
    # Get a set of IPs that are pending for registration:
    # Pending registration IPs that meet all the following conditions:
    # 1. IPs that are currently in the DNS
    # 2. Those IPs must have not been registered yet
    :param ip_from_target_group_set: a set of IPs that are currently registered with a target group
    :param ip_from_dns_set: a set of IPs that are in the DNS
    """
    pending_registration_ip_set = ip_from_dns_set - ip_from_target_group_set
    return pending_registration_ip_set


def get_invocation_count_per_pending_deregistration_ip(
    ip_from_dns_set: Set[str],
    ip_from_target_group_set: Set[str],
    active_ip_set_from_previous_invocation: Set[str],
    pending_ip_dict_from_previous_invocation: Dict[str, int],
) -> Dict[str, int]:
    """
    Get a mapping of pending deregistration IP and the count of Lambda invocations that this IP has been detected
    :param ip_from_dns_set: a set of IPs that are in the DNS
    :param ip_from_target_group_set: a set of IPs that are currently registered with a target group
    :param active_ip_set_from_previous_invocation:  a set of active IPs from the previous invocation
    :param pending_ip_dict_from_previous_invocation:  a dict of pending IPs and their invocation count from the previous invocation
    :return: mapping of pending deregistration IPs and the Lambda invocations count that the IPs have been detected. e.g.
    {'172.16.2.245': 1, '172.16.3.178': 1}
    """
    # Raw pending registration IPs are the ones that: (Without considering INVOCATIONS_BEFORE_DEREGISTRATION)
    # 1. In the active IP list from the previous invocation but no longer in the DNS
    # 2. Currently registered but no longer in the DNS

    pending_ip_from_previous_invocation_set = (
        set(pending_ip_dict_from_previous_invocation.keys())
        if pending_ip_dict_from_previous_invocation
        else set()
    )

    # IPs that are in the active list from the previous invocation while not present in the DNS
    ip_in_previous_active_ip_not_in_dns = (
        active_ip_set_from_previous_invocation - ip_from_dns_set
    )
    logger.debug(
        f"IPs are previously active but no longer in the DNS: {ip_in_previous_active_ip_not_in_dns}"
    )

    # IPs that are currently registered but not in the DNS
    ip_in_target_group_not_in_dns = ip_from_target_group_set - ip_from_dns_set
    logger.debug(
        f"IPs are currently in the target group but no longer in the DNS: {ip_in_target_group_not_in_dns}"
    )

    # We keep tracking for how many invocations a pending deregistration IP has been detected.
    # The deregistration API is only called when the pending IPs's invocation count is higher than INVOCATIONS_BEFORE_DEREGISTRATION
    invocation_count_per_pending_deregistration_ip: Dict[str, int] = {}
    pending_ip_from_current_invocation_set = (
        ip_in_previous_active_ip_not_in_dns | ip_in_target_group_not_in_dns
    )
    logger.debug(
        f"Pending deregistration IPs from current invocation (without considering INVOCATIONS_BEFORE_DEREGISTRATION) - "
        f"{pending_ip_from_current_invocation_set}"
    )

    if pending_ip_from_previous_invocation_set:
        new_pending_ip_set = (
            pending_ip_from_current_invocation_set
            - pending_ip_from_previous_invocation_set
        )
        logger.debug(
            f"IPs that are detected as pending deregistration for the first time - {new_pending_ip_set}"
        )
        existing_pending_ip_set = (
            pending_ip_from_current_invocation_set - new_pending_ip_set
        )
        logger.debug(
            f"IPs that have already been detected as pending deregistration from previous invocation - {existing_pending_ip_set}"
        )
        invalid_pending_ip_set = (
            pending_ip_from_previous_invocation_set
            - pending_ip_from_current_invocation_set
        )
        logger.debug(
            f"IPs that were detected as pending deregistration but no longer considered as pending - {invalid_pending_ip_set}"
        )

        # Set the new pending IP invocation count to 1
        for new_pending_ip in new_pending_ip_set:
            invocation_count_per_pending_deregistration_ip[new_pending_ip] = 1

        # Increase the invocation count for the IPs that are already in the previous pending IP list
        for existing_pending_ip in existing_pending_ip_set:
            invocation_count_per_pending_deregistration_ip[existing_pending_ip] = (
                pending_ip_dict_from_previous_invocation[existing_pending_ip] + 1
            )

        return invocation_count_per_pending_deregistration_ip

    logger.info("No pending deregistration IP found from the previous invocations")
    for pending_ip in pending_ip_from_current_invocation_set:
        invocation_count_per_pending_deregistration_ip[pending_ip] = 1

    return invocation_count_per_pending_deregistration_ip


def get_pending_deregistration_ip_set(
    invocation_count_per_pending_deregistration_ip: Dict[str, int],
    invocation_before_deregistration: int,
) -> Set[str]:
    """
    Get a set of IPs that are pending deregistration
    :param invocation_before_deregistration: invocation count that has to be reached first before calling deregistration API
    :param invocation_count_per_pending_deregistration_ip: mapping of pending deregistration IPs and the Lambda invocations count that the IPs have been detected. e.g.
    {'172.16.2.245': 1, '172.16.3.178': 1}
    :return: a set of IPs that are pending deregistration. e.g. {'1.1.1.1', '2.2.2.2'}
    """
    pending_deregistration_ip_set: Set[str] = set()
    for ip, invocation_count in invocation_count_per_pending_deregistration_ip.items():
        if invocation_count >= invocation_before_deregistration:
            pending_deregistration_ip_set.add(ip)
    logger.debug(
        f"Pending deregistration IPs for the current invocation - {pending_deregistration_ip_set}"
    )
    return pending_deregistration_ip_set


def get_elb_ip_target_from_ip_list(
    ip_list: List[str], elb_listener: int
) -> List[Dict[str, object]]:
    """
    Get a list of targets for registration or deregistration
    :param ip_list: list of IP
    :param elb_listener: ELB listener port
    :return: a list of targets required by registration/deregistration API
    """
    target_list: List[Dict[str, object]] = []
    for ip in ip_list:
        if LambdaEnv.SAME_VPC:
            target: Dict[str, object] = {"Id": ip, "Port": elb_listener}
        else:
            target = {"Id": ip, "Port": elb_listener, "AvailabilityZone": "all"}
        target_list.append(target)
    return target_list
