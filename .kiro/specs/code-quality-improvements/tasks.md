# Implementation Plan: Code Quality Improvements

## Overview

Incremental refactoring of the RDS NLB Lambda function to address code quality, resilience, and security findings. Each task builds on the previous, starting with foundational changes (lazy init, exception handling) that unblock test improvements, then adding safety features (circuit breaker), and finishing with cleanup and infrastructure changes.

## Tasks

- [ ] 1. Refactor LambdaEnv to lazy initialization
  - [x] 1.1 Convert `constant.py` to use a lazy-loading singleton class with `@property` descriptors
    - Replace class-level attribute evaluation with a `_ensure_initialized()` pattern
    - `TIME` property always computes fresh UTC timestamp (never cached)
    - Add `reset()` method for test isolation
    - Add DNS name validation (reject empty/whitespace-only entries, require at least one valid name)
    - Use `os.getenv("SAME_VPC", "true").lower() == "true"` directly (no ternary)
    - Add `MAX_DEREGISTRATION_PERCENT` env var (default 50)
    - Add type hints to all attributes
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 7.1, 7.2, 7.3, 14.3, 9.4_
  - [x] 1.2 Write property tests for LambdaEnv
    - **Property 1: Lazy initialization reads environment variables after import**
    - **Property 2: TIME returns fresh timestamp on each access**
    - **Property 3: LambdaEnv interface preserves attribute types**
    - **Property 9: DNS name parsing rejects invalid entries**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 7.1, 7.2**
  - [x] 1.3 Write unit tests for LambdaEnv edge cases
    - Test missing required env vars raise KeyError
    - Test zero valid DNS names raises ValueError
    - Test MAX_DEREGISTRATION_PERCENT defaults to 50
    - Test port is integer type
    - _Requirements: 1.4, 6.1, 7.3_

- [ ] 2. Refactor AwsServices exception handling and retry configuration
  - [x] 2.1 Refactor `aws_services.py` with specific exceptions, retries, and type hints
    - Remove `publish_elb_ip_count_metric` method and CloudWatch client (`self.cw`)
    - Add `botocore.config.Config` with adaptive retry (max_attempts=3) for S3 and ELBv2 clients
    - `write_content_to_s3`: catch `ClientError`/`BotoCoreError`, log, re-raise
    - `download_elb_ip_from_s3`: catch `ClientError` (NoSuchKey → return {}), catch `json.JSONDecodeError` separately and raise
    - `register_target`: catch only `ClientError`, log, return False
    - `deregister_target`: catch only `ClientError`, log
    - `get_ip_target_list_by_target_group_arn`: catch only `ClientError`, log, return empty list
    - Add type hints to all methods
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 5.1, 8.1, 9.1, 12.1, 12.2, 12.3_
  - [x] 2.2 Write property tests for AwsServices
    - **Property 4: Non-boto3 exceptions propagate from AwsServices**
    - **Property 5: write_content_to_s3 re-raises on failure**
    - **Property 6: Write operation ClientErrors are logged with context**
    - **Validates: Requirements 2.1, 2.2, 2.5, 2.6, 5.1**
  - [x] 2.3 Write unit tests for AwsServices
    - Test each method: success path with mocked boto3
    - Test download_elb_ip_from_s3: NoSuchKey returns {}, other ClientError raises, JSONDecodeError raises
    - Test register_target: ClientError returns False, success returns True
    - Test write_content_to_s3: ClientError re-raises
    - Test retry config is applied to clients
    - _Requirements: 2.3, 2.4, 3.1, 12.1, 12.2, 12.3_

- [ ] 3. Refactor common.py (logging, types, cleanup)
  - [x] 3.1 Update `common.py` with logging fix, type hints, and code cleanup
    - Fix logging: use `logging.getLogger(__name__)` and `logger.setLevel(logging.INFO)` only (no handler manipulation)
    - Define `DNS_RECORD_TYPE_A = "A"` constant
    - Replace `defaultdict(int)` with plain `dict` in `get_invocation_count_per_pending_deregistration_ip`
    - Fix `precondition` to log error message (not the boolean value)
    - Add type hints to all functions
    - Ensure `get_elb_ip_target_from_ip_list` port parameter is typed as `int`
    - _Requirements: 6.2, 9.3, 10.1, 10.2, 10.3, 14.4, 14.6, 14.7_
  - [x] 3.2 Write property tests for common.py
    - **Property 8: Target dictionaries use integer port values**
    - **Property 11: Precondition logs error message not boolean value**
    - **Validates: Requirements 6.2, 14.6**
  - [x] 3.3 Write unit tests for DNS functions
    - Test `dns_lookup`: success returns list, resolver exceptions propagate
    - Test `dns_lookup_with_retry`: retries on failure, returns empty set after exhaustion, breaks on success
    - Test `get_rds_replica_ips_from_dns`: aggregates IPs from multiple names, handles partial failures
    - _Requirements: 3.3, 3.4_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Refactor Lambda handler with circuit breaker and structured logging
  - [x] 5.1 Update `populate_NLB_TG_with_RDS_RR.py` with all handler improvements
    - Move module docstring before imports
    - Remove unused `sys` import
    - Add return type annotation to `lambda_handler`
    - Fix missing space in `get_ip_from_dns` error message concatenation
    - Add `should_skip_deregistration` function (circuit breaker logic)
    - Integrate circuit breaker into `update_target_group` flow
    - Let S3 write exceptions propagate (remove silent failure)
    - Add `log_invocation_summary` function for structured JSON logging
    - Call `log_invocation_summary` at end of handler with request_id from context
    - Add type hints to all functions
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 5.2, 5.3, 8.2, 9.2, 13.1, 13.2, 13.3, 14.1, 14.2, 14.5_
  - [x] 5.2 Write property tests for handler logic
    - **Property 7: Circuit breaker skips deregistration above threshold**
    - **Property 10: Invocation summary log is valid structured JSON**
    - **Validates: Requirements 4.1, 13.1, 13.2, 13.3**
  - [x] 5.3 Write unit tests for Lambda handler
    - Test happy path: DNS resolves, registers new IPs, writes state
    - Test early exit: DNS returns no IPs, handler returns None
    - Test circuit breaker: deregistration skipped when threshold exceeded
    - Test S3 write failure: exception propagates from handler
    - Test first run: no S3 state, registers all DNS IPs
    - _Requirements: 3.2, 3.4, 4.1, 4.3, 5.2, 5.3_

- [ ] 6. Update test infrastructure and fixtures
  - [x] 6.1 Update `test/conftest.py` and `test/unittest_constant.py`
    - Update conftest to add `MAX_DEREGISTRATION_PERCENT` env var
    - Change port values to integers in test constants
    - Remove unused constants from `unittest_constant.py` (ALB_DNS_NAME, ALB_LISTENER, CW_METRIC_FLAG_IP_COUNT)
    - Convert existing tests to use top-level imports (now possible with lazy LambdaEnv)
    - _Requirements: 3.6, 6.3, 8.3_
  - [x] 6.2 Update existing test_common.py to use top-level imports and integer ports
    - Replace function-scoped `import common` with top-level import
    - Update `test_get_elb_ip_target_from_ip_list_same_vpc` to use integer port (3306)
    - Update `test_get_elb_ip_target_from_ip_list_different_vpc` to use integer port (3306)
    - _Requirements: 3.6, 6.3_

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Update CloudFormation template
  - [x] 8.1 Update `cloudformation_NLB_TG_with_RDS_RR.json` with infrastructure improvements
    - Parameterize function name: `{"Fn::Sub": "${AWS::StackName}-RDS-NLB-Registration"}`
    - Add `ReservedConcurrentExecutions: 1` to Lambda function
    - Change `Timeout` from 300 to 60
    - Add `MAX_DEREGISTRATION_PERCENT` parameter (Type: Number, Default: 50)
    - Add `MAX_DEREGISTRATION_PERCENT` to Lambda environment variables
    - Add SQS Dead Letter Queue resource and `DeadLetterConfig` on Lambda
    - Add resource tags (Application, Environment, Owner) to Lambda, IAM Role, EventBridge Rule, and SQS queue
    - Update logging resource ARN to use parameterized function name
    - _Requirements: 11.1, 11.2, 15.1, 15.2, 15.3, 15.4_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- The lazy LambdaEnv (task 1) must be completed first as it unblocks top-level imports in tests
- Property tests use the `hypothesis` library with minimum 100 iterations per test
- Unit tests use `pytest` with `unittest.mock` for boto3 mocking
