# Implementation Plan: Conditional CloudFormation Resources

## Overview

This plan restructures the CloudFormation template into a dedicated `infrastructure/` folder, adds conditional resource creation (NLB, Target Group, S3 Bucket, RDS Replica) using CloudFormation Conditions and `Fn::If` intrinsic functions, adds `AWS::CloudFormation::Interface` metadata for Console UX, updates documentation, and adds structural correctness tests using pytest.

## Tasks

- [x] 1. Relocate template and remove obsolete files
  - [x] 1.1 Move CloudFormation template to infrastructure folder
    - Create `infrastructure/` directory
    - Copy `cloudformation_NLB_TG_with_RDS_RR.json` to `infrastructure/cloudformation_NLB_TG_with_RDS_RR.json`
    - Delete the original `cloudformation_NLB_TG_with_RDS_RR.json` from the project root
    - Delete `example-parameters.json` from the repository
    - _Requirements: 1.1, 1.3, 1.4_

- [x] 2. Add conditional parameters and conditions to the template
  - [x] 2.1 Add Create* flag parameters and conditional resource parameters
    - Add `CreateNLB` parameter (String, AllowedValues `true`/`false`, default `false`)
    - Add `CreateTargetGroup` parameter (String, AllowedValues `true`/`false`, default `false`)
    - Add `CreateS3Bucket` parameter (String, AllowedValues `true`/`false`, default `false`)
    - Add `CreateRDSReplica` parameter (String, AllowedValues `true`/`false`, default `false`)
    - Add `NLBSubnetIds` parameter (CommaDelimitedList)
    - Add `VpcId` parameter (AWS::EC2::VPC::Id)
    - Add `NLBScheme` parameter (String, AllowedValues `internet-facing`/`internal`, default `internal`)
    - Add `SourceDBInstanceIdentifier` parameter (String, no default)
    - Add `DBInstanceClass` parameter (String, default `db.r5.large`, with AllowedValues)
    - Update all parameter `Description` fields to document when each is required
    - _Requirements: 2.1, 2.5, 2.6, 2.7, 3.1, 4.1, 5.1, 5.5, 5.6, 7.1, 7.3_

  - [x] 2.2 Add Conditions section to the template
    - Add `CreateNLBCondition`: `Fn::Equals: [!Ref CreateNLB, "true"]`
    - Add `CreateTargetGroupCondition`: `Fn::Equals: [!Ref CreateTargetGroup, "true"]`
    - Add `CreateS3BucketCondition`: `Fn::Equals: [!Ref CreateS3Bucket, "true"]`
    - Add `CreateRDSReplicaCondition`: `Fn::Equals: [!Ref CreateRDSReplica, "true"]`
    - Add `CreateNLBAndTargetGroupCondition`: `Fn::And` combining both NLB and TG conditions
    - _Requirements: 2.2, 3.2, 4.2, 5.2, 6.2_

- [x] 3. Add conditional resources
  - [x] 3.1 Add conditional NLB resource
    - Add `AWS::ElasticLoadBalancingV2::LoadBalancer` resource with `Condition: CreateNLBCondition`
    - Set Type to `network`, Scheme from `NLBScheme` param, Subnets from `NLBSubnetIds` param
    - Add Application, Environment, Owner tags
    - _Requirements: 2.3, 2.4_

  - [x] 3.2 Add conditional Target Group resource
    - Add `AWS::ElasticLoadBalancingV2::TargetGroup` resource with `Condition: CreateTargetGroupCondition`
    - Set TargetType `ip`, Protocol `TCP`, Port from `RDSListenerPort`, VpcId from `VpcId` param
    - Configure health check with Protocol `TCP` and Port from `RDSListenerPort`
    - Add Application, Environment, Owner tags
    - _Requirements: 3.2, 3.3, 3.4, 3.5_

  - [x] 3.3 Add conditional NLB Listener resource
    - Add `AWS::ElasticLoadBalancingV2::Listener` resource with `Condition: CreateNLBAndTargetGroupCondition`
    - Set LoadBalancerArn from created NLB, Port from `RDSListenerPort`, Protocol `TCP`
    - Set DefaultActions to forward to created Target Group
    - _Requirements: 6.2, 6.6_

  - [x] 3.4 Add conditional S3 Bucket resource
    - Add `AWS::S3::Bucket` resource with `Condition: CreateS3BucketCondition`
    - Enable all four Block Public Access settings
    - Configure default encryption using SSE-S3 (AES256)
    - Enable versioning
    - Add Application, Environment, Owner tags
    - _Requirements: 4.2, 4.3, 4.4_

  - [x] 3.5 Add conditional RDS Read Replica resource
    - Add `AWS::RDS::DBInstance` resource with `Condition: CreateRDSReplicaCondition`
    - Set `SourceDBInstanceIdentifier` from param, `DBInstanceClass` from param
    - Add Application, Environment, Owner tags
    - _Requirements: 5.2, 5.3, 5.4_

- [x] 4. Implement Fn::If resolution for Lambda and IAM
  - [x] 4.1 Update Lambda environment variables with Fn::If expressions
    - Replace `NLB_TG_ARN` value with `Fn::If` selecting between created Target Group Ref and `NLBTargetGroupARN` param based on `CreateTargetGroupCondition`
    - Replace `S3_BUCKET` value with `Fn::If` selecting between created S3 Bucket Ref and `S3BucketName` param based on `CreateS3BucketCondition`
    - _Requirements: 3.6, 3.7, 4.5, 6.4_

  - [x] 4.2 Update IAM policy resource ARNs with Fn::If expressions
    - Update `ELBTargetGroup` statement Resource to use `Fn::If` with `CreateTargetGroupCondition` selecting between created TG Ref and `NLBTargetGroupARN` param
    - Update S3 policy statement Resources to use `Fn::If` with `CreateS3BucketCondition` selecting between created bucket ARN (using Fn::Sub) and `S3BucketName` param ARN
    - _Requirements: 3.7, 4.6, 6.1, 6.3_

- [x] 5. Checkpoint - Verify template structure
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Add Metadata and Outputs
  - [x] 6.1 Add AWS::CloudFormation::Interface metadata
    - Add Metadata section with `AWS::CloudFormation::Interface`
    - Group parameters: Conditional Resource Flags, NLB Configuration, Target Group Configuration, S3 Configuration, RDS Configuration, Lambda Configuration, Tagging, Region
    - Add descriptive group labels indicating when parameters are required
    - _Requirements: 6.5, 7.2_

  - [x] 6.2 Add conditional and always-on Outputs section
    - Add `NLBArn` output with `Condition: CreateNLBCondition`
    - Add `NLBDNSName` output with `Condition: CreateNLBCondition`
    - Add `TargetGroupArn` output with `Condition: CreateTargetGroupCondition`
    - Add `StateBucketName` output with `Condition: CreateS3BucketCondition`
    - Add `RDSReplicaEndpoint` output with `Condition: CreateRDSReplicaCondition`
    - Add `LambdaFunctionArn` output (always present)
    - Add `EffectiveTargetGroupArn` output (always present, uses Fn::If)
    - Add `EffectiveBucketName` output (always present, uses Fn::If)
    - _Requirements: 5.7, 7.1_

- [x] 7. Update documentation
  - [x] 7.1 Update DEPLOYMENT-GUIDE.md with new paths and instructions
    - Update all file path references from root to `infrastructure/` directory
    - Remove references to `example-parameters.json` and `deploy-parameters.json`
    - Document Console-based deployment as the primary approach
    - Document CLI deployment with inline `--parameters` (no parameter file)
    - Document the new conditional resource parameters and their interdependencies
    - Add examples for common deployment scenarios (all Create flags false, NLB+TG true, etc.)
    - _Requirements: 1.5, 7.4_

- [x] 8. Checkpoint - Verify template and documentation
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Add structural correctness tests
  - [x]* 9.1 Create test infrastructure and template loading fixture
    - Create `test/test_cfn_template.py`
    - Add pytest fixture that loads and parses `infrastructure/cloudformation_NLB_TG_with_RDS_RR.json`
    - Verify the template is valid JSON with required top-level keys (Parameters, Conditions, Resources, Metadata)
    - _Requirements: 1.1, 1.2_

  - [x]* 9.2 Write structural tests for Create* parameters and Conditions
    - Assert all 4 `Create*` parameters exist with correct AllowedValues `["true", "false"]` and default `"false"`
    - Assert all 4 conditions exist with correct `Fn::Equals` expressions referencing corresponding parameters
    - Assert `CreateNLBAndTargetGroupCondition` exists with `Fn::And` expression
    - _Validates: Design Property 3 (Create Flag Parameter Consistency)_
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 4.1, 4.2, 5.1, 5.2_

  - [x]* 9.3 Write structural tests for conditional resources
    - Assert each conditional resource has the correct `Condition` key value
    - Assert NLB resource has Type `network` and references `NLBSubnetIds` and `NLBScheme`
    - Assert Target Group resource has TargetType `ip`, Protocol `TCP`, references `RDSListenerPort` and `VpcId`
    - Assert S3 Bucket has Block Public Access, encryption, and versioning configured
    - Assert RDS replica has `SourceDBInstanceIdentifier` property
    - Assert NLB Listener has `CreateNLBAndTargetGroupCondition`
    - _Validates: Design Property 1 (Condition Coverage)_
    - _Requirements: 2.3, 3.3, 3.4, 4.3, 5.3, 6.2_

  - [x]* 9.4 Write structural tests for Fn::If resolution
    - Assert Lambda `NLB_TG_ARN` env var uses `Fn::If` with `CreateTargetGroupCondition`
    - Assert Lambda `S3_BUCKET` env var uses `Fn::If` with `CreateS3BucketCondition`
    - Assert IAM policy Target Group resource uses `Fn::If` with `CreateTargetGroupCondition`
    - Assert IAM policy S3 resources use `Fn::If` with `CreateS3BucketCondition`
    - _Validates: Design Properties 2, 5, 6 (Fn::If Reference Resolution, Lambda Env Var Resolution, IAM Policy Alignment)_
    - _Requirements: 3.6, 3.7, 4.5, 4.6, 6.1, 6.3, 6.4_

  - [x]* 9.5 Write structural tests for Metadata and Outputs
    - Assert every parameter appears in at least one `AWS::CloudFormation::Interface` parameter group
    - Assert conditional outputs have correct `Condition` key values
    - Assert `RDSReplicaEndpoint` output has `Condition: CreateRDSReplicaCondition`
    - _Validates: Design Properties 4, 7 (Conditional Output Consistency, Interface Metadata Completeness)_
    - _Requirements: 5.7, 6.5, 7.2_

  - [x]* 9.6 Write structural test for conditional resource isolation
    - Assert that no unconditional resource directly references (via `Ref` or `Fn::GetAtt`) a conditional resource without wrapping in `Fn::If`
    - Scan the template to find all `Ref` and `Fn::GetAtt` usages and verify they are properly gated
    - _Validates: Design Property 8 (Conditional Resource Isolation)_
    - _Requirements: 2.4, 3.5, 4.4, 5.4_

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- This is an IaC-only feature — no property-based tests apply. Structural assertions (pytest) validate the CloudFormation template JSON structure instead
- The template uses CloudFormation-native patterns (Conditions, Fn::If) — no custom logic or runtime code is involved
- Tests load and parse the template JSON file directly without deploying

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2"] },
    { "id": 3, "tasks": ["3.1", "3.4", "3.5"] },
    { "id": 4, "tasks": ["3.2"] },
    { "id": 5, "tasks": ["3.3", "4.1", "4.2"] },
    { "id": 6, "tasks": ["6.1", "6.2"] },
    { "id": 7, "tasks": ["7.1"] },
    { "id": 8, "tasks": ["9.1"] },
    { "id": 9, "tasks": ["9.2", "9.3", "9.4", "9.5", "9.6"] }
  ]
}
```
