# RDS Read Replica NLB Registration

## The Challenge

Amazon RDS (without Aurora) read replica instances are each assigned their own unique DNS endpoint. However, RDS does not provide a single unified DNS endpoint capable of load balancing read queries across multiple read replica instances which Aurora provides. As a result, the responsibility falls on the application layer to distribute read queries across the available replicas in a manner that effectively balances the load.

## What This Solution Does

The solution introduces a Network Load Balancer (NLB) with an IP-based target group, positioned between the application and the RDS read replica instances, to evenly distribute read queries across the replicas. The registration and de-registration of RDS read replica instances within the NLB target group is managed by a Lambda function, which continuously monitors the IP addresses of your RDS read replicas and keeps the Network Load Balancer target group synchronized accordingly.

Every minute, a Lambda function:
- Performs DNS lookups to discover current read replica IPs
- Registers newly discovered IPs with your NLB target group
- Safely deregisters IPs that are no longer active (after a configurable grace period)
- Tracks state in S3 to maintain consistency across invocations
- See [HOW-IT-WORKS.md](HOW-IT-WORKS.md) for additional details

## How It Helps

- **Eliminates manual intervention** - No need to manually update NLB targets when replica IPs change
- **Provides static endpoints** - Your NLB maintains consistent IP addresses while backend replicas can change freely
- **Prevents service disruption** - Cautious deregistration logic ensures IPs aren't removed prematurely
- **Scales automatically** - Handles multiple read replicas across your RDS cluster
- **Maintains visibility** - Optional CloudWatch metrics for monitoring IP count changes

## Use Cases

- Exposing a single RDS read replica (not Aurora) DNS endpoint.

## Quick Start

### Prerequisites

- AWS CLI installed and configured with credentials ([install guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html))
- Python 3 installed (used by the deploy script for JSON parsing)
- `zip` command available (pre-installed on macOS and most Linux distributions)

### Deploy

Step 1: Clone the repository
```
git clone git@github.com:aws-samples/sample-rds-RR-nlb-registration.git
```

Step 2: Navigate to the cloned repository and run the deploy script
```
chmod +x deploy.sh
./deploy.sh
```
- Verifies AWS identity (account and region). Allows change of region.
- Asks if you have an S3 bucket or need to create one to store the Lambda code and CloudFormation template.
- ZIPs the Lambda code and uploads it along with the CloudFormation template to the S3 bucket.
- Prints the S3 template URL and bucket name to use in the CloudFormation Console.

Step 3: Follow the printed instructions to deploy the stack via the AWS CloudFormation Console.

## Optional Resource Creation

The CloudFormation stack supports optionally creating resources that may already exist in your environment. Set the corresponding flag to `true` during stack creation:

| Resource | Flag | When to use |
|----------|------|-------------|
| Network Load Balancer | `CreateNLB` | You don't have an existing NLB |
| NLB Target Group | `CreateTargetGroup` | You don't have an existing target group |
| S3 Bucket (state) | `CreateS3Bucket` | You don't have an existing bucket for Lambda state |
| RDS Read Replica | `CreateRDSReplica` | You want the stack to create a replica from a primary instance |

When a flag is set to `false` (default), provide the existing resource identifier (ARN or name) in the corresponding parameter.

## S3 Buckets

This solution uses two separate S3 buckets:

1. **Code bucket** — Created by the deploy script (or provided by you). Stores the Lambda ZIP package and CloudFormation template. Can be deleted when you no longer plan to update the stack.
2. **State persistence bucket** — Used by the Lambda function at runtime to store IP state between invocations. Can be newly created by the CloudFormation stack (`CreateS3Bucket=true`) or you can provide an existing bucket name.

For detailed deployment scenarios and troubleshooting, see [DEPLOYMENT-GUIDE.md](DEPLOYMENT-GUIDE.md).