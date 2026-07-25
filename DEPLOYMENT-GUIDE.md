# Deployment Guide

## What CloudFormation Creates

### Always-Created Resources

1. **LambdaFunction** (AWS::Serverless::Function) — Runs `populate_NLB_TG_with_RDS_RR.lambda_handler` on Python 3.13. Resolves RDS replica DNS names and registers IPs to the NLB target group.
2. **ScheduledRule** (AWS::Events::Rule) — EventBridge rule that triggers the Lambda every minute.
3. **LambdaInvokePermission** (AWS::Lambda::Permission) — Grants EventBridge permission to invoke the Lambda.
4. **LambdaIAMRole** (AWS::IAM::Role) — IAM execution role for Lambda with permissions for S3, CloudWatch Logs, and ELBv2 target group management.

### Conditionally-Created Resources

These resources are only created when their corresponding `Create*` flag is set to `true`:

| Resource | Condition Flag | Description |
|----------|---------------|-------------|
| Network Load Balancer | `CreateNLB=true` | NLB of type `network` with configurable scheme and subnets |
| NLB Target Group | `CreateTargetGroup=true` | IP-based TCP target group for RDS replica IPs |
| NLB Listener | `CreateNLB=true` AND `CreateTargetGroup=true` | Listener linking the created NLB to the created Target Group |
| S3 Bucket | `CreateS3Bucket=true` | Bucket for Lambda state persistence (Block Public Access, SSE-S3, versioning enabled) |
| RDS Read Replica | `CreateRDSReplica=true` | Read replica from specified primary instance |

## Prerequisites

### Lambda Code Package

The Lambda deployment package must be uploaded to S3 before deploying the stack. This step requires the CLI.

1. ZIP the Python code along with its dependency:

```bash
zip -r populate_NLB_TG_with_RDS_RR.zip *.py dns/ dnspython-2.6.1.dist-info/
```

2. Copy the ZIP to your S3 bucket:

```bash
aws s3 cp populate_NLB_TG_with_RDS_RR.zip \
  s3://{bucket-name}/lambda-code/populate_NLB_TG_with_RDS_RR.zip \
  --region {region-name}
```

### Pre-Existing Resources (when Create flags are false)

When a `Create*` flag is `false` (the default), you must provide the corresponding pre-existing resource identifier:

| If this flag is `false`... | You must provide... |
|----------------------------|---------------------|
| `CreateTargetGroup` | `NLBTargetGroupARN` — ARN of your existing NLB Target Group |
| `CreateS3Bucket` | `S3BucketName` — Name of your existing S3 bucket for state persistence |

**Note:** For S3 buckets you provide, ensure:
1. Block Public Access is enabled
2. Default encryption (SSE-S3 or SSE-KMS) is enabled
3. Versioning is enabled (recommended)

## Conditional Resource Parameters and Interdependencies

### Create Flag Parameters

All flags default to `false`. Set to `true` to have the stack create the resource.

| Parameter | Default | Effect when `true` | Required companion parameters |
|-----------|---------|-------------------|-------------------------------|
| `CreateNLB` | `false` | Creates a Network Load Balancer | `NLBSubnetIds`, `VpcId`, `NLBScheme` |
| `CreateTargetGroup` | `false` | Creates an NLB Target Group | `VpcId` |
| `CreateS3Bucket` | `false` | Creates an S3 bucket with security defaults | (none) |
| `CreateRDSReplica` | `false` | Creates an RDS read replica | `SourceDBInstanceIdentifier`, `DBInstanceClass` |

### Interdependencies

- **NLB + Target Group**: When both `CreateNLB=true` and `CreateTargetGroup=true`, an NLB Listener is automatically created to link them.
- **Target Group ARN resolution**: The Lambda and IAM policy automatically use the created Target Group ARN (when `CreateTargetGroup=true`) or the `NLBTargetGroupARN` parameter value (when `false`).
- **S3 Bucket resolution**: The Lambda and IAM policy automatically use the created bucket name (when `CreateS3Bucket=true`) or the `S3BucketName` parameter value (when `false`).
- **VpcId**: Required when either `CreateNLB=true` or `CreateTargetGroup=true`.

## Deployment

### Option 1: AWS Console (Primary)

This is the recommended approach. The template includes `AWS::CloudFormation::Interface` metadata that organizes parameters into logical groups with descriptive labels.

1. Open the [AWS CloudFormation Console](https://console.aws.amazon.com/cloudformation/)
2. Click **Create stack** → **With new resources (standard)**
3. Select **Upload a template file** and upload `infrastructure/cloudformation_NLB_TG_with_RDS_RR.json`
4. Fill in the parameter form:
   - **Conditional Resource Flags** — Set any `Create*` flags to `true` for resources you want the stack to create
   - **NLB Configuration** — Fill in subnet IDs, VPC, and scheme if `CreateNLB=true`
   - **Target Group Configuration** — Provide existing Target Group ARN if `CreateTargetGroup=false`
   - **S3 Configuration** — Provide existing bucket name if `CreateS3Bucket=false`
   - **RDS Configuration** — Provide source DB identifier if `CreateRDSReplica=true`; always provide `RDSReplicaDNSNames`
   - **Lambda Configuration** — Provide `CodeS3Bucket` (the bucket where you uploaded the ZIP)
5. Check **I acknowledge that AWS CloudFormation might create IAM resources**
6. Click **Create stack**

### Option 2: AWS CLI (Alternative)

Deploy using inline `--parameters` overrides. No parameter file is needed.

```bash
aws cloudformation create-stack \
  --stack-name rds-nlb-registration-stack \
  --template-body file://infrastructure/cloudformation_NLB_TG_with_RDS_RR.json \
  --parameters \
    ParameterKey=CodeS3Bucket,ParameterValue={your-code-bucket} \
    ParameterKey=RDSReplicaDNSNames,ParameterValue='{replica1.abc123.us-east-1.rds.amazonaws.com,replica2.abc123.us-east-1.rds.amazonaws.com}' \
    ParameterKey=NLBTargetGroupARN,ParameterValue={your-target-group-arn} \
    ParameterKey=S3BucketName,ParameterValue={your-state-bucket} \
  --capabilities CAPABILITY_IAM \
  --region {region-name}
```

## Verification

### Check Lambda Function

```bash
aws lambda get-function --function-name {stack-name}-RDS-NLB-Registration --region {region-name}
```

### Check Registered Targets

```bash
aws elbv2 describe-target-health \
  --target-group-arn {your-target-group-arn} \
  --region {region-name}
```

### View Logs

```bash
aws logs tail /aws/lambda/{stack-name}-RDS-NLB-Registration --follow --region {region-name}
```

### Check Stack Outputs

```bash
aws cloudformation describe-stacks \
  --stack-name rds-nlb-registration-stack \
  --query 'Stacks[0].Outputs' \
  --region {region-name}
```

## Troubleshooting

### Targets Not Registering

Check CloudWatch logs:
```bash
aws logs tail /aws/lambda/{stack-name}-RDS-NLB-Registration --since 5m --region {region-name}
```

Common issues:
- Incorrect RDS DNS names in `RDSReplicaDNSNames`
- Wrong target group ARN (when using pre-existing TG)
- IAM permission issues
- S3 bucket doesn't exist (when using pre-existing bucket)
- Database security group not allowing traffic on TCP 3306 from NLB.

### Permission Errors

The Lambda role needs:
- `elasticloadbalancing:RegisterTargets`
- `elasticloadbalancing:DeregisterTargets`
- `elasticloadbalancing:DescribeTargetHealth`
- `s3:GetObject`, `s3:PutObject`, `s3:ListBucket`

These are automatically configured by the CloudFormation template and scoped to the effective target group and bucket (whether created by the stack or pre-existing).

### Stack Creation Fails with Parameter Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `NLBTargetGroupARN` required | `CreateTargetGroup=false` but no ARN provided | Provide `NLBTargetGroupARN` or set `CreateTargetGroup=true` |
| `S3BucketName` required | `CreateS3Bucket=false` but no bucket name provided | Provide `S3BucketName` or set `CreateS3Bucket=true` |
| NLB subnet error | `CreateNLB=true` but `NLBSubnetIds` empty | Provide valid subnet IDs |
| VPC ID invalid | `CreateNLB=true` or `CreateTargetGroup=true` but `VpcId` missing | Provide valid VPC ID |

## Cleanup

To remove all resources created by the stack:

1. Open the [AWS CloudFormation Console](https://console.aws.amazon.com/cloudformation/)
2. Click **Select stack** -> **Delete**

Note: Delete the state S3 bucket by deleting the content and empty the bucket.
