# Requirements Document

## Introduction

This feature restructures the CloudFormation infrastructure by moving the template into a dedicated `infrastructure/` folder and introducing conditional resource creation. The NLB, Target Group, S3 Bucket, and RDS instances are optional resources that may already exist in the AWS account. Using CloudFormation Conditions and Parameters, the template will only create these resources when they do not already exist, allowing the stack to adapt to pre-existing infrastructure.

## Glossary

- **Stack_Template**: The CloudFormation JSON template that defines all infrastructure resources for the RDS-NLB registration solution
- **Condition**: A CloudFormation Conditions block entry that evaluates to true or false based on parameter values, controlling whether a resource is created
- **Parameter**: A CloudFormation Parameters block entry that accepts user input at deploy time to configure the stack behavior
- **NLB**: Network Load Balancer — an AWS Elastic Load Balancing resource that distributes TCP traffic across registered targets
- **Target_Group**: An NLB target group resource that holds the IP address targets for load balancing
- **S3_Bucket**: An Amazon S3 bucket resource used for Lambda state persistence between invocations
- **RDS_Instance**: An Amazon RDS database read replica instance
- **Conditional_Resource**: A CloudFormation resource that includes a Condition property, causing it to be created only when the condition evaluates to true
- **Infrastructure_Folder**: A dedicated directory named `infrastructure/` in the project repository that contains all CloudFormation templates and parameter files

## Requirements

### Requirement 1: Relocate CloudFormation Template to Dedicated Folder

**User Story:** As a DevOps engineer, I want the CloudFormation template to reside in a dedicated infrastructure folder, so that the project structure is organized and infrastructure code is separated from application code.

#### Acceptance Criteria

1. THE Stack_Template SHALL reside in the Infrastructure_Folder at path `infrastructure/cloudformation_NLB_TG_with_RDS_RR.json`
2. WHEN the Stack_Template is relocated, THE Stack_Template SHALL retain all existing resource definitions, parameters, and outputs without modification to their logical behavior
3. WHEN the Stack_Template is relocated, THE project SHALL NOT retain the original Stack_Template at the project root
4. THE project SHALL remove the `example-parameters.json` file from the repository since parameter values will be provided at runtime through the AWS CloudFormation Console or via CLI `--parameters` inline
5. WHEN the Stack_Template is relocated, THE project documentation files (DEPLOYMENT-GUIDE.md) SHALL update all file path references to the Stack_Template to reflect the new `infrastructure/` directory location

### Requirement 2: Conditional NLB Creation

**User Story:** As a DevOps engineer, I want to optionally create the Network Load Balancer through the CloudFormation stack, so that I can skip NLB creation when one already exists in my account.

#### Acceptance Criteria

1. THE Stack_Template SHALL include a Parameter named `CreateNLB` of type String with allowed values `true` and `false` and a default value of `false`
2. THE Stack_Template SHALL include a Condition named `CreateNLBCondition` that evaluates to true when the `CreateNLB` Parameter equals `true`
3. WHEN `CreateNLBCondition` evaluates to true, THE Stack_Template SHALL create an NLB resource of type `network` with the scheme specified by a `NLBScheme` Parameter (allowed values: `internet-facing`, `internal`; default: `internal`) and subnets specified by the `NLBSubnetIds` Parameter
4. IF `CreateNLBCondition` evaluates to false, THEN THE Stack_Template SHALL not create the NLB resource nor any resources that have `CreateNLBCondition` attached
5. THE Stack_Template SHALL include a Parameter named `NLBSubnetIds` of type `CommaDelimitedList` for specifying one or more subnet IDs to assign to the NLB when `CreateNLBCondition` is true
6. THE Stack_Template SHALL include a Parameter named `VpcId` of type `AWS::EC2::VPC::Id` for specifying the VPC in which the NLB and its target group are created when `CreateNLBCondition` is true
7. THE Stack_Template SHALL include a Parameter named `NLBScheme` of type String with allowed values `internet-facing` and `internal` and a default value of `internal`

### Requirement 3: Conditional Target Group Creation

**User Story:** As a DevOps engineer, I want to optionally create the NLB Target Group through the CloudFormation stack, so that I can skip target group creation when one already exists.

#### Acceptance Criteria

1. THE Stack_Template SHALL include a Parameter named `CreateTargetGroup` of type String with allowed values `true` and `false` and a default value of `false`
2. THE Stack_Template SHALL include a Condition named `CreateTargetGroupCondition` that evaluates to true when the `CreateTargetGroup` Parameter equals `true`
3. WHEN `CreateTargetGroupCondition` evaluates to true, THE Stack_Template SHALL create a Target_Group resource of type `AWS::ElasticLoadBalancingV2::TargetGroup` with target type `ip`, protocol `TCP`, port set to the `RDSListenerPort` Parameter value, and VPC ID set to the `VpcId` Parameter value
4. WHEN `CreateTargetGroupCondition` evaluates to true, THE Stack_Template SHALL configure the Target_Group health check with protocol `TCP` and port set to the `RDSListenerPort` Parameter value
5. WHEN `CreateTargetGroupCondition` evaluates to false, THE Stack_Template SHALL not create the Target_Group resource
6. THE Stack_Template SHALL resolve the effective Target Group ARN using a conditional expression (`Fn::If`) that returns the created Target_Group ARN when `CreateTargetGroupCondition` is true, or the `NLBTargetGroupARN` Parameter value when the condition is false
7. THE Stack_Template SHALL use the resolved effective Target Group ARN in both the Lambda function `NLB_TG_ARN` environment variable and the IAM policy `ELBTargetGroup` statement Resource field
8. IF `CreateTargetGroup` is `false` and `NLBTargetGroupARN` is empty, THEN THE Stack_Template SHALL fail validation, preventing deployment without a usable Target Group ARN

### Requirement 4: Conditional S3 Bucket Creation

**User Story:** As a DevOps engineer, I want to optionally create the S3 bucket for Lambda state persistence through the CloudFormation stack, so that I can skip bucket creation when one already exists.

#### Acceptance Criteria

1. THE Stack_Template SHALL include a Parameter named `CreateS3Bucket` of type String with allowed values `true` and `false` and a default value of `false`
2. THE Stack_Template SHALL include a Condition named `CreateS3BucketCondition` that evaluates to true when the `CreateS3Bucket` Parameter equals `true`
3. IF `CreateS3BucketCondition` evaluates to true, THEN THE Stack_Template SHALL create an S3_Bucket resource with all four Block Public Access settings enabled (BlockPublicAcls, BlockPublicPolicy, IgnorePublicAcls, RestrictPublicBuckets), default encryption using SSE-S3, and versioning enabled
4. IF `CreateS3BucketCondition` evaluates to false, THEN THE Stack_Template SHALL not create the S3_Bucket resource
5. THE Stack_Template SHALL set the Lambda function `S3_BUCKET` environment variable using a conditional expression that resolves to the `Ref` of the created S3_Bucket resource when `CreateS3BucketCondition` is true, or to the `S3BucketName` Parameter value when `CreateS3BucketCondition` is false
6. THE Stack_Template SHALL scope the IAM policy S3 permissions (s3:GetObject, s3:PutObject, s3:ListBucket) to the same conditional bucket reference used in the Lambda environment variable
7. THE Stack_Template SHALL require the `S3BucketName` Parameter (non-empty) when `CreateS3Bucket` is `false`, to identify the pre-existing bucket for Lambda state persistence

### Requirement 5: Conditional RDS Read Replica Creation

**User Story:** As a DevOps engineer, I want to optionally create RDS read replica instances through the CloudFormation stack, so that I can skip RDS creation when replicas already exist.

#### Acceptance Criteria

1. THE Stack_Template SHALL include a Parameter named `CreateRDSReplica` of type String with allowed values `true` and `false` and a default value of `false`
2. THE Stack_Template SHALL include a Condition named `CreateRDSReplicaCondition` that evaluates to true when the `CreateRDSReplica` Parameter equals `true`
3. WHEN `CreateRDSReplicaCondition` evaluates to true, THE Stack_Template SHALL create exactly one `AWS::RDS::DBInstance` read replica resource with the `SourceDBInstanceIdentifier` property set to the `SourceDBInstanceIdentifier` Parameter value, the `DBInstanceClass` property set to the `DBInstanceClass` Parameter value, and a `Condition` key of `CreateRDSReplicaCondition`
4. WHEN `CreateRDSReplicaCondition` evaluates to false, THE Stack_Template SHALL not create the RDS_Instance resources
5. THE Stack_Template SHALL include a Parameter named `SourceDBInstanceIdentifier` of type String with no default value and a description indicating it specifies the identifier of the primary RDS instance to replicate from
6. THE Stack_Template SHALL include a Parameter named `DBInstanceClass` of type String with a default value of `db.r5.large` and allowed values limited to valid RDS instance class prefixes (`db.t3.medium`, `db.r5.large`, `db.r5.xlarge`, `db.r6g.large`, `db.r6g.xlarge`)
7. IF `CreateRDSReplicaCondition` evaluates to true, THEN THE Stack_Template SHALL include an Output named `RDSReplicaEndpoint` with a Condition of `CreateRDSReplicaCondition` that exposes the read replica's `Endpoint.Address` attribute

### Requirement 6: Parameter Interdependency and Validation

**User Story:** As a DevOps engineer, I want the template to handle parameter interdependencies correctly, so that the stack deploys successfully regardless of which combination of optional resources I choose to create.

#### Acceptance Criteria

1. IF `CreateNLB` is `false` and `CreateTargetGroup` is `false`, THEN THE Stack_Template SHALL treat the `NLBTargetGroupARN` Parameter as required and pass its value to the Lambda environment variable `NLB_TG_ARN` and the IAM policy resource ARN for target group operations
2. IF `CreateTargetGroup` is `true` and `CreateNLB` is `true`, THEN THE Stack_Template SHALL create a Listener resource that associates the conditionally created Target_Group with the conditionally created NLB on the port specified by the `RDSListenerPort` Parameter
3. IF `CreateS3Bucket` is `false`, THEN THE Stack_Template SHALL treat the `S3BucketName` Parameter as required and pass its value to the Lambda environment variable `S3_BUCKET` and the IAM policy S3 resource ARNs
4. THE Stack_Template SHALL use `Fn::If` intrinsic functions to resolve the Lambda environment variables `NLB_TG_ARN` and `S3_BUCKET`, and the IAM policy resource ARNs, selecting between conditionally created resource attributes and user-provided parameter values based on the corresponding Condition evaluations
5. THE Stack_Template SHALL include a Metadata section with an `AWS::CloudFormation::Interface` definition that groups parameters by conditional resource selection and lists which parameters become required when their corresponding `Create*` flag is set to `false`
6. IF `CreateTargetGroup` is `true` and `CreateNLB` is `false`, THEN THE Stack_Template SHALL associate the conditionally created Target_Group with the existing NLB identified by a user-provided parameter

### Requirement 7: Console-Friendly Template with Hybrid Deployment Support

**User Story:** As a DevOps engineer deploying this solution one time, I want the CloudFormation template to be self-documenting through the AWS Console parameter form, while still supporting CLI-based deployment if preferred.

#### Acceptance Criteria

1. THE Stack_Template SHALL define all Parameters with descriptive `Description` fields that clearly explain the expected value format, valid options, and when each parameter is required (e.g., "Required when CreateNLB is false. Provide the ARN of your existing NLB Target Group.")
2. THE Stack_Template SHALL include an `AWS::CloudFormation::Interface` Metadata section that groups parameters into logical categories (Conditional Resource Flags, NLB Configuration, Target Group Configuration, S3 Configuration, RDS Configuration, Lambda Configuration) with descriptive group labels so the AWS Console renders them in an organized form
3. THE Stack_Template SHALL set sensible default values for all Parameters where applicable (e.g., `CreateNLB` defaults to `false`, `DBInstanceClass` defaults to `db.r5.large`) so that operators only need to fill in environment-specific values
4. THE Stack_Template SHALL remain fully compatible with CLI-based deployment using `aws cloudformation create-stack --parameters ParameterKey=X,ParameterValue=Y` inline overrides without requiring a parameter file
