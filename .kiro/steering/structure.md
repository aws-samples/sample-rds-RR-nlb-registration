# Project Structure

## Root Directory Layout
```
.
├── populate_NLB_TG_with_RDS_RR.py          # Main Lambda handler
├── aws_services.py                          # AWS service client wrapper (boto3 facade)
├── common.py                                # Utility functions (DNS, IP logic)
├── constant.py                              # Environment variable constants
├── cloudformation_NLB_TG_with_RDS_RR.json   # CloudFormation/SAM template
├── deploy-parameters.json                   # Deployment parameter values
├── example-parameters.json                  # Example parameter reference
├── README.md                                # Project overview
├── HOW-IT-WORKS.md                          # Detailed architecture and flow documentation
├── DEPLOYMENT-GUIDE.md                      # Setup instructions
├── dns/                                     # Bundled dnspython 2.1.0 library
├── dnspython-2.1.0.dist-info/              # Package metadata
└── test/                                    # Test suite
    ├── conftest.py                          # Pytest fixtures (env var setup)
    ├── test_common.py                       # Utility function tests
    └── unittest_constant.py                 # Test constants
```

## Module Responsibilities

**populate_NLB_TG_with_RDS_RR.py** — Entry point (`lambda_handler`). Orchestrates the 7-step workflow: DNS resolution → target group comparison → S3 state loading → registration/deregistration decisions → target group updates → S3 state persistence.

**aws_services.py** — `AwsServices` class wrapping boto3 clients for S3, CloudWatch, and ELBv2. Provides domain-specific methods with built-in error handling.

**common.py** — DNS resolution using VPC resolver with retry logic, IP set comparison (pending registration/deregistration), target list formatting, logging config, and precondition helper.

**constant.py** — `LambdaEnv` class that reads and parses environment variables. Handles comma-separated DNS name parsing, S3 key derivation, and type conversions.

## State Management
- Active IPs stored in S3: `{STATE_PREFIX}/active_ip.json`
- Pending deregistration IPs: `{STATE_PREFIX}/pending_ip.json`
- JSON format with metadata (timestamp, IP list, count)

## Key Design Patterns
- Separation of concerns: AWS API calls in `aws_services.py`, business logic in `common.py`, config in `constant.py`
- Aggressive registration, cautious deregistration (invocation counting)
- Graceful first-run handling when S3 state doesn't exist
- Safety exit if DNS returns no IPs (avoids deregistering everything)
