# Product Overview

AWS Lambda function that automatically registers Application Load Balancer (ALB) IP addresses as targets in a Network Load Balancer (NLB) target group.

The solution enables static IP addresses for ALBs by placing an NLB in front of the ALB and dynamically tracking ALB node IP changes through DNS lookups. The Lambda function runs on a schedule (every minute) to:

- Perform DNS lookups to discover current ALB node IPs
- Register new IPs with the NLB target group
- Cautiously deregister IPs that are no longer active (after configurable invocation threshold)
- Track state between invocations using S3
- Optionally publish CloudWatch metrics for ALB IP count

This is particularly useful for scenarios requiring static IP addresses (e.g., firewall whitelisting) while using ALBs that have dynamic IPs.
