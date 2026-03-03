# RDS Read Replica NLB Registration - Quick Deployment Guide

## What This Does

Automatically registers RDS Read Replica IP addresses as targets in your Network Load Balancer (NLB) target group.

## Prerequisites

- AWS Account with AWS CLI configured
- RDS Read Replicas
- Network Load Balancer with IP-based target group
- S3 bucket for state storage

## Quick Start

### Step 1: Download Required Files
1. Cloudformation template. Named as template_popluate_NLB_TG_with_RDS_RR.json
2. example parameter json file. Named as example-parameters.json
3. The python code which is a zip file. Named as populate_NLB_TG_with_RDS_RR.zip

### Step 2: Populate the values

Populate the example-parameters.json with actual values. Optionally can rename the file as well for example deployment-parameters.json instead of example-parameters.json
Note: The deploy command uses deployment-parameters.json


### Step 3: Deploy the stack
1. Copy the Python code (zip file) into your own S3 bucket.
```bash
aws s3 cp populate_NLB_TG_with_RDS_RR.zip \
  s3://{bucket-name}/lambda-code/populate_NLB_TG_with_RDS_RR.zip \
  --region {region-name}
```

2. Deploy using below command.
```bash
aws cloudformation deploy \
  --template-file template_popluate_NLB_TGW_with_RDS_RR.json \
  --stack-name rds-nlb-registration-stack \
  --parameter-overrides file://deploy-parameters.json \
  --capabilities CAPABILITY_IAM \
  --region {region-name}
```
Note: Run this command from same directory where template and parameters file are stored.

## Verification

### Check Lambda Function

```bash
aws lambda get-function --function-name RDS-NLB-Registration --region {region-name}
```

### Check Registered Targets

```bash
aws elbv2 describe-target-health \
  --target-group-arn YOUR-TARGET-GROUP-ARN \
  --region {region-name}
```

### View Logs

```bash
aws logs tail /aws/lambda/RDS-NLB-Registration --follow --region {region-name}
```

## How It Works

1. **EventBridge** triggers Lambda every 1 minute
2. **Lambda** performs DNS lookups on RDS replica endpoints
3. **Lambda** registers new IPs with NLB target group
4. **Lambda** deregisters old IPs (after threshold)
5. **S3** stores state between invocations

## Troubleshooting

### Targets Not Registering

Check CloudWatch logs:
```bash
aws logs tail /aws/lambda/RDS-NLB-Registration --since 5m --region {region-name}
```

Common issues:
- Incorrect RDS DNS names
- Wrong target group ARN
- IAM permission issues
- S3 bucket doesn't exist

### Permission Errors

The Lambda role needs:
- `elasticloadbalancing:RegisterTargets`
- `elasticloadbalancing:DeregisterTargets`
- `elasticloadbalancing:DescribeTargetHealth`
- `s3:GetObject`, `s3:PutObject`, `s3:ListBucket`

These are automatically configured by the CloudFormation template.

## Cleanup

To remove all resources:

```bash
aws cloudformation delete-stack \
  --stack-name rds-nlb-registration \
  --region us-west-2
```

## Cost Estimate

- **Lambda**: ~$0.20/month (43,200 invocations)
- **S3**: Negligible (small state files)
- **CloudWatch Logs**: ~$0.50/month

**Total**: ~$0.70/month

## Support

For issues or questions:
- Check CloudWatch logs first
- Verify all parameters are correct
- Ensure RDS replicas are running
- Confirm NLB target group exists

## Architecture

```
EventBridge (1 min) → Lambda → DNS Lookup (RDS)
                        ↓
                    S3 (state)
                        ↓
                NLB Target Group (register/deregister IPs)
```

## Files in Distribution

All files are available at: `s3://vchakrabpyfiles1/lambda-code/`

- `populate_NLB_TG_with_RDS_RR.zip` - Lambda deployment package
- `template_popluate_NLB_TGW_with_RDS_RR.json` - CloudFormation template
- `example-parameters.json` - Example parameter file
- `README.md` - Detailed documentation

## Version

Current Version: 1.0
Last Updated: March 2026
