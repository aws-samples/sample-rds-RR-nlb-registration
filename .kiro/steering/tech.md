# Technology Stack

## Runtime & Language
- Python 3.8
- AWS Lambda serverless execution

## AWS Services
- AWS Lambda (compute)
- Amazon S3 (state persistence)
- Amazon CloudWatch (metrics and logging)
- Elastic Load Balancing v2 (ELBv2 API)
- EventBridge (CloudWatch Events) for scheduled invocation

## Key Libraries
- `boto3` - AWS SDK for Python (S3, CloudWatch, ELBv2 clients)
- `dnspython` (dns.resolver) - DNS lookups and queries
- `pytest` - Testing framework
- `mock` - Mocking library for unit tests

## Testing
- Unit tests using pytest with mock
- Test files located in `test/` directory
- Run tests: `pytest test/`
- Test coverage includes both main logic and utility functions

## Deployment
- AWS SAM (Serverless Application Model) template
- CloudFormation template: `template_popluate_NLB_TGW_with_RDS_RR.json`
- Packaged as Lambda deployment package (zip)
- Scheduled execution via EventBridge rule (1-minute interval)

## Environment Configuration
Lambda function configured via environment variables:
- `ALB_DNS_NAME` - Target ALB DNS name
- `NLB_TG_ARN` - NLB target group ARN
- `S3_BUCKET` - State storage bucket
- `ALB_LISTENER` - ALB listener port
- `MAX_LOOKUP_PER_INVOCATION` - DNS lookup limit per run
- `INVOCATIONS_BEFORE_DEREGISTRATION` - Deregistration threshold
- `CW_METRIC_FLAG_IP_COUNT` - CloudWatch metrics toggle
- `SAME_VPC` - VPC configuration flag
- `AWS_REGION` - AWS region

## Common Commands
```bash
# Run all tests
pytest test/

# Run specific test file
pytest test/test_common.py

# Run with verbose output
pytest -v test/

# Package for Lambda deployment
zip -r function.zip *.py dns/ dnspython-2.1.0.dist-info/
```
