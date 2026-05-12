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

See [DEPLOYMENT-GUIDE.md](DEPLOYMENT-GUIDE.md) for setup instructions.
