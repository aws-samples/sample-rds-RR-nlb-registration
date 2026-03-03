# Project Structure

## Root Directory Layout
```
.
├── populate_NLB_TG_with_ALB.py    # Main Lambda handler
├── aws_services.py                 # AWS service client wrapper
├── common.py                       # Utility functions (DNS, IP logic)
├── constant.py                     # Environment variable constants
├── template_popluate_NLB_TGW_with_RDS_RR.json  # CloudFormation/SAM template
├── dns/                            # dnspython library
├── dnspython-2.1.0.dist-info/     # Package metadata
└── test/                           # Test suite
    ├── conftest.py                 # Pytest configuration
    ├── test_populate_NLB_TG_with_ALB.py  # Main handler tests
    ├── test_common.py              # Utility function tests
    └── unittest_constant.py        # Test constants
```

## Module Organization

### Core Modules

**populate_NLB_TG_with_ALB.py**
- Entry point: `lambda_handler(event, context)`
- Orchestrates the 7-step workflow
- Validates environment variables
- Coordinates DNS lookups, target group updates, and S3 state management

**aws_services.py**
- `AwsServices` class encapsulates boto3 clients
- Methods for S3 operations (read/write state)
- ELBv2 operations (register/deregister targets, describe health)
- CloudWatch metrics publishing

**common.py**
- DNS resolution utilities with retry logic
- IP set comparison logic (pending registration/deregistration)
- Target list formatting for ELBv2 API
- Logging configuration
- Precondition validation helper

**constant.py**
- `LambdaEnv` class reads environment variables
- Provides typed access to configuration
- Computes derived values (S3 keys, timestamps)

## Code Organization Patterns

### Separation of Concerns
- AWS API interactions isolated in `aws_services.py`
- Business logic for IP tracking in `common.py`
- Configuration centralized in `constant.py`
- Main orchestration in `populate_NLB_TG_with_ALB.py`

### State Management
- Active IPs stored in S3: `{ALB_DNS_NAME}/active_ip.json`
- Pending deregistration IPs: `{ALB_DNS_NAME}/pending_ip.json`
- JSON format with metadata (timestamp, IP list, count)

### Error Handling
- Precondition checks with `precondition()` helper
- Exception logging with context
- Graceful degradation (e.g., missing S3 state on first run)

### Testing Strategy
- Unit tests mock AWS services and DNS lookups
- Test both success and error paths
- Verify state transitions and invocation counting logic
- Use `unittest_constant.py` for test fixtures
