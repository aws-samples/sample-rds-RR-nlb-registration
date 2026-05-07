# Technology Stack

## Runtime & Language
- Python 3.13
- AWS Lambda serverless execution (runs inside VPC for RDS DNS resolution)

## AWS Services
- AWS Lambda (compute)
- Amazon S3 (state persistence between invocations)
- Amazon CloudWatch (logging)
- Elastic Load Balancing v2 (ELBv2 API for NLB target group management)
- EventBridge (scheduled invocation every 1 minute)

## Key Libraries
- `boto3` / `botocore` — AWS SDK (S3, CloudWatch, ELBv2 clients)
- `dnspython` 2.1.0 (`dns.resolver`) — DNS lookups via VPC resolver
- `pytest` — Testing framework
- `mock` — Mocking library for unit tests

## Environment Variables
- `RDS_REPLICA_DNS_NAMES` — Comma-separated RDS read replica DNS names
- `RDS_LISTENER_PORT` — Database port (e.g., 3306 for MySQL, 5432 for PostgreSQL)
- `NLB_TG_ARN` — NLB target group ARN
- `S3_BUCKET` — State storage bucket
- `STATE_PREFIX` — S3 key prefix for state files
- `MAX_LOOKUP_PER_INVOCATION` — DNS retry attempts per replica name
- `INVOCATIONS_BEFORE_DEREGISTRATION` — Consecutive misses before deregistration
- `SAME_VPC` — VPC configuration flag (default: true)
- `CLOUDWATCH_LOG_GROUP` — Optional log group name
- `AWS_REGION` — AWS region

## Testing
- Unit tests in `test/` directory using pytest with mock
- Test fixtures set up RDS-specific environment variables via `conftest.py`
- Run tests: `pytest test/`
- Run verbose: `pytest -v test/`
- Run specific file: `pytest test/test_common.py`

## Deployment
- CloudFormation/SAM template: `cloudformation_NLB_TG_with_RDS_RR.json`
- Lambda handler: `populate_NLB_TG_with_RDS_RR.lambda_handler`
- Package: `zip -r function.zip *.py dns/ dnspython-2.1.0.dist-info/`
- `dns/` directory is the bundled dnspython library (required since Lambda has no pip access at runtime)
