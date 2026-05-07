# Product Overview

AWS Lambda function that automatically registers RDS read replica IP addresses as targets in a Network Load Balancer (NLB) target group.

Since RDS (non-Aurora) does not provide a single unified endpoint for load balancing read queries across multiple read replicas, this solution places an NLB in front of the replicas and keeps the target group synchronized with the current replica IPs. The Lambda function runs on a schedule (every minute) to:

- Resolve multiple RDS read replica DNS names to their current IPs via VPC DNS
- Register newly discovered IPs with the NLB target group
- Cautiously deregister IPs that are no longer active (after a configurable invocation threshold)
- Track state between invocations using S3

Registration is aggressive (immediate), deregistration is cautious (requires N consecutive missed invocations) to avoid dropping active database connections.
