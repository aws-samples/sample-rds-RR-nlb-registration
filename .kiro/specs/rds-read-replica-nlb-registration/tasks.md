# Implementation Plan: RDS Read Replica NLB Registration

## Overview

This implementation adapts the existing ALB-to-NLB IP registration Lambda function to support RDS read replicas. The key changes are: (1) supporting multiple DNS names instead of a single ALB DNS name, (2) aggregating IPs from all read replicas, and (3) using a configurable state prefix for S3 storage. The implementation reuses most of the existing codebase with targeted modifications to constant.py, common.py, and populate_NLB_TG_with_ALB.py.

## Tasks

- [x] 1. Update configuration module for RDS environment variables
  - [x] 1.1 Modify constant.py to add RDS environment variables
    - Replace ALB_DNS_NAME with RDS_REPLICA_DNS_NAMES (comma-separated string)
    - Replace ALB_LISTENER with RDS_LISTENER_PORT
    - Add STATE_PREFIX environment variable
    - Add CLOUDWATCH_LOG_GROUP environment variable (optional)
    - Remove CW_METRIC_FLAG_IP_COUNT (CloudWatch metrics are optional for this implementation)
    - Add RDS_REPLICA_DNS_LIST property that parses and trims the comma-separated DNS names
    - Update ACTIVE_IP_LIST_KEY to use STATE_PREFIX instead of ALB_DNS_NAME
    - Update PENDING_IP_LIST_KEY to use STATE_PREFIX instead of ALB_DNS_NAME
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.3, 3.4, 3.5_
  
  - [ ]* 1.2 Write property test for DNS name parsing
    - **Property 1: DNS Name List Parsing**
    - **Validates: Requirements 1.1, 2.2, 2.3**
    - Test that parsing comma-separated strings with various whitespace produces correctly trimmed lists
    - Test that empty strings are excluded from the parsed list
  
  - [ ]* 1.3 Write unit tests for environment variable validation
    - Test missing RDS_REPLICA_DNS_NAMES raises error
    - Test empty RDS_REPLICA_DNS_NAMES raises error
    - Test invalid RDS_LISTENER_PORT raises error
    - Test STATE_PREFIX is used in S3 key computation
    - _Requirements: 2.4_

- [x] 2. Implement multi-DNS resolution in common.py
  - [x] 2.1 Add get_rds_replica_ips_from_dns() function
    - Accept list of DNS names, record type, and max lookup count
    - Iterate through each DNS name and call get_elb_ip_from_dns()
    - Wrap each DNS resolution in try-except to handle failures gracefully
    - Log errors for failed DNS names but continue processing remaining names
    - Aggregate all resolved IPs into a single set
    - Return the aggregated IP set
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 7.1, 7.2, 7.3, 7.4, 8.1_
  
  - [x] 2.2 Modify dns_lookup_with_retry() to remove early termination
    - Remove the logic that terminates early when fewer than 8 IPs are found
    - Always perform the full retry count specified by max_lookup_per_invocation
    - _Requirements: 7.2_
  
  - [ ]* 2.3 Write property test for independent DNS resolution
    - **Property 2: Independent DNS Resolution**
    - **Validates: Requirements 1.2, 1.4**
    - Test that failure to resolve one DNS name does not prevent resolution of other names
    - Use mocking to simulate DNS failures for specific names
  
  - [ ]* 2.4 Write property test for IP aggregation
    - **Property 3: IP Aggregation from Multiple Sources**
    - **Validates: Requirements 1.3, 3.1**
    - Test that all IPs from multiple DNS names are aggregated into a single set with no duplicates
    - Generate random IP sets for multiple DNS names and verify aggregation
  
  - [ ]* 2.5 Write unit tests for DNS resolution error handling
    - Test that DNS resolution continues when one name fails
    - Test that all DNS names failing results in empty set
    - Test that error details are logged for failed DNS names
    - _Requirements: 1.4, 8.1_

- [x] 3. Checkpoint - Ensure configuration and DNS resolution tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Update main handler for multiple DNS names
  - [x] 4.1 Modify populate_NLB_TG_with_ALB.py Step 1 (Get IPs from DNS)
    - Replace call to get_elb_ip_from_dns() with get_rds_replica_ips_from_dns()
    - Pass lambda_env.RDS_REPLICA_DNS_LIST instead of single DNS name
    - Pass lambda_env.RDS_LISTENER_PORT instead of ALB_LISTENER
    - Exit if no IPs are resolved from any DNS name
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  
  - [x] 4.2 Modify populate_NLB_TG_with_ALB.py Step 7 (Save State to S3)
    - Update active IP metadata to use STATE_PREFIX instead of ALB_DNS_NAME in LoadBalancerName field
    - Ensure ACTIVE_IP_LIST_KEY and PENDING_IP_LIST_KEY use STATE_PREFIX
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 9.1, 9.3_
  
  - [ ]* 4.3 Write unit tests for main handler workflow
    - Test that multiple DNS names are resolved and aggregated
    - Test that STATE_PREFIX is used in S3 keys
    - Test that metadata uses STATE_PREFIX in LoadBalancerName field
    - Mock all AWS service calls
    - _Requirements: 1.1, 1.5, 3.3, 3.4, 3.5, 9.3_

- [x] 5. Implement IP registration and deregistration logic
  - [x] 5.1 Verify get_pending_registration_ip_set() works with aggregated IPs
    - Review existing implementation in common.py
    - Ensure it correctly identifies new IPs from aggregated DNS results
    - No code changes should be needed (existing logic is generic)
    - _Requirements: 4.1_
  
  - [x] 5.2 Verify get_invocation_count_per_pending_deregistration_ip() works with aggregated IPs
    - Review existing implementation in common.py
    - Ensure it correctly tracks invocation counts for IPs from any replica
    - No code changes should be needed (existing logic is generic)
    - _Requirements: 4.2, 4.3_
  
  - [x] 5.3 Verify get_pending_deregistration_ip_set() works with threshold logic
    - Review existing implementation in common.py
    - Ensure it correctly identifies IPs that have reached the deregistration threshold
    - No code changes should be needed (existing logic is generic)
    - _Requirements: 4.4_
  
  - [ ]* 5.4 Write property test for new IP registration
    - **Property 4: New IP Registration**
    - **Validates: Requirements 4.1**
    - Test that any IP in DNS results but not in NLB target group is added to pending registration set
    - Generate random IP sets for DNS and NLB, verify pending registration calculation
  
  - [ ]* 5.5 Write property test for pending deregistration invocation counting
    - **Property 5: Pending Deregistration Invocation Counting**
    - **Validates: Requirements 4.2, 4.3**
    - Test that absent IPs have their invocation count incremented or initialized to 1
    - Generate random state transitions and verify invocation counts
  
  - [ ]* 5.6 Write property test for deregistration threshold
    - **Property 6: Deregistration Threshold**
    - **Validates: Requirements 4.4**
    - Test that IPs with invocation count >= threshold are included in deregistration set
    - Generate random pending IP states with various invocation counts
  
  - [ ]* 5.7 Write property test for pending IP recovery
    - **Property 7: Pending IP Recovery**
    - **Validates: Requirements 4.5**
    - Test that pending IPs reappearing in DNS are removed from pending deregistration list
    - Generate random state transitions where pending IPs reappear in DNS

- [x] 6. Implement dynamic DNS name management
  - [ ]* 6.1 Write property test for dynamic DNS name addition
    - **Property 8: Dynamic DNS Name Addition**
    - **Validates: Requirements 5.1**
    - Test that adding a DNS name to the list results in its IPs being included in aggregated set
    - Simulate environment variable changes across invocations
  
  - [ ]* 6.2 Write property test for dynamic DNS name removal
    - **Property 9: Dynamic DNS Name Removal**
    - **Validates: Requirements 5.2, 5.3**
    - Test that removing a DNS name causes its IPs to enter pending deregistration
    - Simulate environment variable changes and verify state transitions
  
  - [ ]* 6.3 Write property test for state persistence across configuration changes
    - **Property 10: State Persistence Across Configuration Changes**
    - **Validates: Requirements 5.4**
    - Test that S3 state files remain accessible when DNS name list changes
    - Test that pending deregistration counts are preserved across configuration changes
  
  - [ ]* 6.4 Write unit tests for DNS name list changes
    - Test adding a new DNS name to the environment variable
    - Test removing a DNS name from the environment variable
    - Test that state files continue to work after changes
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 7. Checkpoint - Ensure registration/deregistration logic tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement DNS retry and error handling
  - [ ]* 8.1 Write property test for DNS retry logic
    - **Property 11: DNS Retry Logic**
    - **Validates: Requirements 7.2, 7.3**
    - Test that DNS resolution attempts up to MAX_LOOKUP_PER_INVOCATION lookups
    - Test that alternative name servers are tried when one fails
    - Use mocking to simulate name server failures
  
  - [ ]* 8.2 Write unit tests for DNS error handling
    - Test that DNS lookup failures are logged with DNS name and error details
    - Test that DNS resolution continues with remaining name servers after failure
    - Test that all name servers failing results in empty IP set for that DNS name
    - _Requirements: 7.2, 7.3, 8.1_

- [x] 9. Implement state serialization and persistence
  - [ ]* 9.1 Write property test for state serialization round-trip
    - **Property 12: State Serialization Round-Trip**
    - **Validates: Requirements 9.4**
    - Test that serializing and deserializing active IP state produces equivalent object
    - Test that serializing and deserializing pending IP state produces equivalent object
    - Generate random state objects and verify round-trip consistency
  
  - [ ]* 9.2 Write property test for missing state file handling
    - **Property 13: Missing State File Handling**
    - **Validates: Requirements 9.5**
    - Test that reading non-existent S3 state files returns empty dictionary without exception
    - Mock S3 to simulate missing files
  
  - [ ]* 9.3 Write unit tests for state file format
    - Test that active IP state has correct JSON structure (LoadBalancerName, TimeStamp, IPList, IPCount)
    - Test that pending IP state has correct JSON structure (IP -> invocation count mapping)
    - Test that LoadBalancerName field uses STATE_PREFIX value
    - Test that invalid JSON in S3 state files is handled gracefully
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 10. Implement comprehensive error logging
  - [ ]* 10.1 Write property test for error logging
    - **Property 14: Error Logging**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**
    - Test that DNS failures are logged with DNS name and error details
    - Test that NLB registration failures are logged with target IPs and target group ARN
    - Test that NLB deregistration failures are logged with target IPs and target group ARN
    - Test that S3 operation failures are logged with bucket name, object key, and error details
    - Test that environment variable validation failures are logged with variable name
    - Use log capture to verify log messages contain required context
  
  - [ ]* 10.2 Write unit tests for error logging paths
    - Test that each error condition produces a log entry
    - Test that log entries contain sufficient context for debugging
    - Test that errors do not prevent other operations from completing (where appropriate)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

- [x] 11. Integration and end-to-end testing
  - [ ]* 11.1 Write integration test for complete workflow
    - Mock all AWS services (S3, ELBv2, CloudWatch Logs)
    - Mock DNS resolution for multiple read replicas
    - Simulate multiple Lambda invocations to test state transitions
    - Verify that IPs are registered, tracked, and deregistered correctly
    - Verify that state files are created and updated correctly
    - _Requirements: All requirements_
  
  - [ ]* 11.2 Write integration test for error scenarios
    - Test workflow when all DNS names fail to resolve
    - Test workflow when NLB registration fails
    - Test workflow when S3 operations fail
    - Verify that errors are logged and Lambda completes gracefully
    - _Requirements: 1.4, 8.1, 8.2, 8.3, 8.4_
  
  - [ ]* 11.3 Write integration test for dynamic configuration changes
    - Simulate adding a read replica (new DNS name)
    - Simulate removing a read replica (DNS name removed)
    - Verify that state transitions correctly across configuration changes
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties (minimum 100 iterations each)
- Unit tests validate specific examples and edge cases
- The implementation reuses most of the existing ALB solution codebase
- Key changes are in constant.py (environment variables), common.py (multi-DNS resolution), and populate_NLB_TG_with_ALB.py (workflow orchestration)
- All 14 correctness properties from the design document have corresponding property-based tests
- Use `hypothesis` library for property-based testing in Python
- Each property test must include a comment with the feature name and property number
