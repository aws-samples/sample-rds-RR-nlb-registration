# Requirements Document

## Introduction

This document captures the requirements for improving code quality, resilience, and security across the RDS Read Replica NLB Target Group Lambda function. The improvements address findings from three reviews: code quality, security, and system design. Requirements are organized by theme and prioritized by severity.

## Glossary

- **Lambda_Function**: The AWS Lambda function (`populate_NLB_TG_with_RDS_RR.py`) that orchestrates DNS resolution and NLB target group updates
- **LambdaEnv**: The configuration class in `constant.py` that reads and parses environment variables
- **AwsServices**: The AWS service client wrapper class in `aws_services.py`
- **DNS_Resolver**: The DNS resolution logic in `common.py` using dnspython
- **Target_Group**: The NLB target group that receives registered/deregistered IP targets
- **State_Store**: The S3-based persistence layer for active and pending IP state between invocations
- **Deregistration_Threshold**: The configurable number of consecutive missed invocations before an IP is deregistered (`INVOCATIONS_BEFORE_DEREGISTRATION`)
- **CloudFormation_Template**: The deployment template `cloudformation_NLB_TG_with_RDS_RR.json`

## Requirements

### Requirement 1: Lazy Initialization of Environment Configuration

**User Story:** As a developer, I want the `LambdaEnv` class to initialize lazily, so that environment variables are read at invocation time rather than import time, enabling accurate timestamps and straightforward testing.

#### Acceptance Criteria

1. WHEN the Lambda_Function is invoked, THE LambdaEnv SHALL read environment variables at the time of first access rather than at module import time
2. WHEN the LambdaEnv TIME field is accessed, THE LambdaEnv SHALL return the current UTC timestamp of the active invocation rather than the timestamp of the cold start
3. WHEN tests import modules that depend on LambdaEnv, THE LambdaEnv SHALL allow environment variables to be set after import without requiring import-time workarounds
4. THE LambdaEnv SHALL preserve the existing public interface (attribute names and types) so that consuming modules require no changes

### Requirement 2: Specific Exception Handling in AWS Service Layer

**User Story:** As a developer, I want the AWS service layer to catch specific boto3 exceptions, so that programming errors are not silently swallowed and operational failures are clearly distinguished from expected conditions.

#### Acceptance Criteria

1. THE AwsServices SHALL catch only `ClientError` and `BotoCoreError` exceptions from boto3 calls rather than bare `Exception`
2. WHEN a `ClientError` occurs in a write operation, THE AwsServices SHALL log the error code, message, and operation context before re-raising or returning a failure indicator
3. WHEN a `ClientError` with code "NoSuchKey" occurs in `download_elb_ip_from_s3`, THE AwsServices SHALL return an empty dictionary and log an informational message
4. WHEN a `json.JSONDecodeError` occurs while parsing S3 state content, THE AwsServices SHALL log the corruption details and raise the exception rather than returning empty state
5. WHEN an unexpected exception type propagates from a boto3 call, THE AwsServices SHALL allow it to propagate unhandled so that Lambda reports the failure
6. THE AwsServices `write_content_to_s3` method SHALL re-raise exceptions after logging so that callers can detect state persistence failures

### Requirement 3: Comprehensive Test Coverage

**User Story:** As a developer, I want comprehensive test coverage for all modules, so that regressions are caught early and refactoring can proceed with confidence.

#### Acceptance Criteria

1. THE test suite SHALL include unit tests for all public methods of the AwsServices class using mocked boto3 clients
2. THE test suite SHALL include unit tests for the `lambda_handler` function covering the happy path and early-exit conditions
3. THE test suite SHALL include unit tests for `dns_lookup` and `dns_lookup_with_retry` functions covering success, retry, and failure scenarios
4. THE test suite SHALL include tests for edge cases: empty DNS name list, all DNS lookups failing, empty target group, and first-run with no S3 state
5. WHEN tests are executed, THE test suite SHALL not require real AWS credentials or network access
6. THE test suite SHALL use top-level imports rather than function-scoped imports for the modules under test

### Requirement 4: Deregistration Safety Circuit Breaker

**User Story:** As an operator, I want a safety limit on deregistration volume, so that partial DNS failures do not cause mass deregistration and service outages.

#### Acceptance Criteria

1. WHEN the number of IPs pending deregistration exceeds a configurable percentage of currently registered targets, THE Lambda_Function SHALL skip deregistration and log a warning
2. THE Lambda_Function SHALL define a default maximum deregistration percentage of 50%
3. WHEN deregistration is skipped due to the safety threshold, THE Lambda_Function SHALL still update S3 state with the pending deregistration counters
4. THE Lambda_Function SHALL expose the maximum deregistration percentage as an environment variable (`MAX_DEREGISTRATION_PERCENT`)

### Requirement 5: S3 State Write Failure Handling

**User Story:** As an operator, I want S3 state write failures to be surfaced clearly, so that state corruption is detected and the function does not silently operate on stale data.

#### Acceptance Criteria

1. WHEN `write_content_to_s3` fails, THE AwsServices SHALL raise the exception after logging the error context
2. WHEN the active IP state write fails in the Lambda_Function, THE Lambda_Function SHALL log an error and allow the exception to propagate (failing the invocation)
3. WHEN the pending IP state write fails in the Lambda_Function, THE Lambda_Function SHALL log an error and allow the exception to propagate (failing the invocation)

### Requirement 6: Consistent Port Type Handling

**User Story:** As a developer, I want port values to have a consistent type throughout the codebase, so that type mismatches do not cause silent bugs in target registration.

#### Acceptance Criteria

1. THE LambdaEnv SHALL expose `RDS_LISTENER_PORT` as an integer type
2. WHEN `get_elb_ip_target_from_ip_list` constructs target dictionaries, THE function SHALL use the port value as an integer matching the ELBv2 API expectation
3. THE test suite SHALL use integer port values consistent with the production code

### Requirement 7: DNS Name Validation

**User Story:** As a developer, I want DNS names to be validated at configuration load time, so that malformed input is rejected early with a clear error message.

#### Acceptance Criteria

1. WHEN `RDS_REPLICA_DNS_NAMES` is parsed, THE LambdaEnv SHALL validate that each DNS name is non-empty after trimming whitespace
2. IF a DNS name in the list is empty or contains only whitespace after splitting, THEN THE LambdaEnv SHALL raise a ValueError with a descriptive message identifying the invalid entry
3. WHEN `RDS_REPLICA_DNS_NAMES` results in zero valid DNS names, THE LambdaEnv SHALL raise a ValueError indicating that at least one valid DNS name is required

### Requirement 8: Remove Unused Code

**User Story:** As a developer, I want unused code removed, so that the codebase is easier to understand and maintain without dead code paths.

#### Acceptance Criteria

1. THE AwsServices SHALL not include the `publish_elb_ip_count_metric` method or initialize a CloudWatch client unless CloudWatch functionality is actively used
2. THE Lambda_Function module SHALL not import `sys` unless it is used
3. THE test constants file SHALL not contain constants that are unused by any test

### Requirement 9: Type Hints Throughout Codebase

**User Story:** As a developer, I want type hints on all function signatures, so that static analysis tools can catch type errors and the code is self-documenting.

#### Acceptance Criteria

1. THE Lambda_Function module SHALL have type annotations on all function parameters and return types
2. THE AwsServices class SHALL have type annotations on all method parameters and return types
3. THE common module SHALL have type annotations on all function parameters and return types
4. THE LambdaEnv class SHALL have type annotations on all class attributes

### Requirement 10: Logging Configuration Compatibility

**User Story:** As a developer, I want logging configuration to be compatible with the Lambda runtime, so that log output is not duplicated or suppressed.

#### Acceptance Criteria

1. THE common module SHALL not remove or reconfigure handlers already set by the Lambda runtime
2. THE common module SHALL set the log level without conflicting with the Lambda runtime's pre-configured root logger
3. WHEN running in the Lambda environment, THE logging configuration SHALL produce log entries without duplication

### Requirement 11: Concurrent Invocation Protection

**User Story:** As an operator, I want the Lambda function protected against concurrent execution, so that race conditions on S3 state do not cause conflicting registration decisions.

#### Acceptance Criteria

1. THE CloudFormation_Template SHALL configure the Lambda function with a reserved concurrency of 1
2. THE CloudFormation_Template SHALL set the Lambda timeout to 60 seconds to match the invocation interval and prevent overlapping executions

### Requirement 12: Retry Configuration for ELB API Calls

**User Story:** As a developer, I want explicit retry configuration on boto3 clients, so that transient ELB API failures are retried automatically with appropriate backoff.

#### Acceptance Criteria

1. THE AwsServices SHALL configure the ELBv2 client with explicit retry settings using adaptive retry mode
2. THE AwsServices SHALL configure a maximum of 3 retry attempts for ELB API calls
3. THE AwsServices SHALL configure the S3 client with explicit retry settings using adaptive retry mode

### Requirement 13: Structured Logging

**User Story:** As an operator, I want structured JSON logging, so that logs can be queried efficiently in CloudWatch Logs Insights and correlated across invocations.

#### Acceptance Criteria

1. THE Lambda_Function SHALL emit log entries in JSON format with consistent field names
2. WHEN a log entry is emitted, THE Lambda_Function SHALL include the Lambda request ID for correlation
3. THE Lambda_Function SHALL log key operational counts (resolved IPs, registered count, deregistered count) as structured fields at the end of each invocation

### Requirement 14: Code Cleanup and Style Improvements

**User Story:** As a developer, I want minor code quality issues resolved, so that the codebase follows Python best practices consistently.

#### Acceptance Criteria

1. THE Lambda_Function module SHALL place its module docstring before import statements
2. THE Lambda_Function `get_ip_from_dns` function SHALL include a space between concatenated error message strings
3. THE LambdaEnv SHALL use direct boolean evaluation (`str.lower() == "true"`) rather than a ternary `True if ... else False` pattern
4. THE common module SHALL use a plain `dict` instead of `defaultdict(int)` where explicit key assignment is used immediately after initialization
5. THE `lambda_handler` function SHALL have a return type annotation
6. THE `precondition` function SHALL log the error message rather than the pre-condition boolean value
7. THE DNS record type "A" SHALL be defined as a named constant rather than a magic string

### Requirement 15: CloudFormation Template Improvements

**User Story:** As an operator, I want the CloudFormation template to follow best practices for deployability and safety, so that the stack can be deployed multiple times and includes proper error handling infrastructure.

#### Acceptance Criteria

1. THE CloudFormation_Template SHALL parameterize the Lambda function name to allow multiple stack deployments in the same account and region
2. THE CloudFormation_Template SHALL configure a Dead Letter Queue (SQS or SNS) for the Lambda function to capture failed invocations
3. THE CloudFormation_Template SHALL add a `MAX_DEREGISTRATION_PERCENT` parameter with a default value of 50
4. THE CloudFormation_Template SHALL include resource tags on all taggable resources with at minimum: Application, Environment, and Owner keys
