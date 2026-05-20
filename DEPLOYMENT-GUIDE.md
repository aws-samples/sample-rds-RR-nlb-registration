## What Cloudformation build :
1. LambdaFunction (AWS::Serverless::Function) = The core of the solution. Runs populate_NLB_TG_with_RDS_RR.lambda_handler on Python 3.13
2. ScheduledRule (AWS::Events::Rule) = An EventBridge rule that triggers the Lambda every minute.
3. LambdaInvokePermission (AWS::Lambda::Permission) = Grants EventBridge permission to invoke the Lambda. Without this, the scheduled rule would fire but the invocation would be denied.
4. LambdaIAMRole (AWS::IAM::Role) = IAM execution role for Lambda to allow read/write state files to the S3 bucket and manage the NLB target group.

## What needs to be manually created :
1. You must have NLB and a target group. 
2. S3 bucket. In this example two S3 bucket are used for clarity. You can optimise by having one and using prefix to distinguish. Purpose of this S3 bucket is to store the lambda code and store the lambda persistance file. Note Lmabda code is used once when deploying. The persistance file are used throughout the lifecycle. 

**Note:** 
1. Make sure Block Public Access enabled.
2. Enable default encryption (SSE-S3 or SSE-KMS)
3. Enabling versioning is recommended.


## Populate the deploy-parameters.json with actual values
	1. CodeS3Bucket : Provide S3 bucket name. Used to store lambda code. 
	2. CodeS3Key (optional) : Specify the S3 path key.
	3. RDSReplicaDNSNames : DNS Name of RDS read replica. Put the values as comma separated.
	4. NLBTargetGroupARN : NLB target group ARN
	5. S3BucketName : Provide S3 bucket name. Used for Lambda persistance. 
	6. RDSListenerPort : Specifiy the RDS port, default set to 3306
	7. Region : Specify your region, default us-west-2

## Deployment 

Note : In your CLI make sure you are in correct folder. 

1. Once repository is cloned ZIP the python code along with dependency. 
```bash
zip -r populate_NLB_TG_with_RDS_RR.zip *.py dns/dnspython-2.6.1.dist-info
```

2. Copy the ZIP code to S3 bucket

```bash
aws s3 cp populate_NLB_TG_with_RDS_RR.zip \
  s3://{bucket-name}/lambda-code/populate_NLB_TG_with_RDS_RR.zip \
  --region {region-name}
```

3. Deploy the stack

```bash
aws cloudformation create-stack \
  --template-file template_popluate_NLB_TGW_with_RDS_RR.json \
  --stack-name rds-nlb-registration-stack \
  --parameter-overrides file://deploy-parameters.json \
  --capabilities CAPABILITY_IAM \
  --region {region-name}
```  

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