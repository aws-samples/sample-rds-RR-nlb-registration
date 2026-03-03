# Requirements Document

## Introduction

This feature adapts the existing ALB-to-NLB IP registration solution to work with RDS read replicas. The core concept remains the same: perform DNS resolution to discover IP addresses, register them with an NLB target group, track state between invocations using S3, and cautiously deregister IPs after a threshold. The key difference is that RDS provides multiple DNS names (one per read replica instance) instead of a single ALB DNS name, requiring the Lambda to resolve all read replica DNS names and aggregate their IPs for registration.

## Glossary

- **Lambda_Function**: The AWS Lambda function that performs DNS resolution and NLB target group management
- **RDS_Read_Replica**: An Amazon RDS read-only copy of a database instance
- **NLB_Target_Group**: Network Load Balancer target group that receives registered IP addresses
- **DNS_Name**: The fully qualified domain name of an RDS read replica instance
- **S3_State**: JSON files stored in S3 that track active and pending deregistration IPs between Lambda invocations
- **Invocation_Threshold**: The number of consecutive Lambda invocations required before deregistering an IP address
- **Active_IP**: An IP address currently present in DNS resolution results
- **Pending_IP**: An IP address no longer in DNS but not yet deregistered, tracked with invocation count

## Requirements

### Requirement 1: Multiple DNS Name Resolution

**User Story:** As a system operator, I want the Lambda function to resolve multiple RDS read replica DNS names, so that all read replica IPs are discovered and registered with the NLB target group.

#### Acceptance Criteria

1. WHEN the Lambda function is invoked, THE Lambda_Function SHALL read a list of RDS read replica DNS names from an environment variable
2. WHEN DNS resolution is performed, THE Lambda_Function SHALL resolve each DNS name in the list independently
3. WHEN multiple DNS names are resolved, THE Lambda_Function SHALL aggregate all resolved IPs into a single set
4. WHEN a DNS name fails to resolve, THE Lambda_Function SHALL log the failure and continue processing remaining DNS names
5. WHEN all DNS resolutions complete, THE Lambda_Function SHALL proceed with the aggregated IP set

### Requirement 2: Environment Variable Configuration

**User Story:** As a deployment engineer, I want to configure RDS read replica DNS names via environment variables, so that the Lambda function can be deployed without code changes.

#### Acceptance Criteria

1. THE Lambda_Function SHALL accept an environment variable named RDS_REPLICA_DNS_NAMES containing a comma-separated list of DNS names
2. WHEN the environment variable is read, THE Lambda_Function SHALL parse the comma-separated string into a list of DNS names
3. WHEN the environment variable contains whitespace, THE Lambda_Function SHALL trim whitespace from each DNS name
4. WHEN the environment variable is empty or missing, THE Lambda_Function SHALL log an error and exit without making changes to the NLB target group
5. THE Lambda_Function SHALL accept an environment variable named RDS_LISTENER_PORT containing the database listener port

### Requirement 3: Aggregated State Management

**User Story:** As a system operator, I want the Lambda function to track all read replica IPs in a single state file, so that IP registration and deregistration logic remains consistent with the existing ALB solution.

#### Acceptance Criteria

1. WHEN storing active IPs to S3, THE Lambda_Function SHALL combine all resolved IPs from all read replicas into a single active IP list
2. WHEN storing pending IPs to S3, THE Lambda_Function SHALL track invocation counts for IPs from any read replica in a single pending IP dictionary
3. WHEN reading state from S3, THE Lambda_Function SHALL use a single S3 key prefix for all read replica state
4. THE Lambda_Function SHALL store active IPs in S3 with key format: `{state_prefix}/active_ip.json`
5. THE Lambda_Function SHALL store pending IPs in S3 with key format: `{state_prefix}/pending_ip.json`

### Requirement 4: IP Registration and Deregistration

**User Story:** As a system operator, I want the Lambda function to register new IPs and cautiously deregister old IPs, so that the NLB target group accurately reflects current read replica endpoints.

#### Acceptance Criteria

1. WHEN new IPs are discovered in DNS, THE Lambda_Function SHALL register them with the NLB target group immediately
2. WHEN an IP is no longer present in DNS, THE Lambda_Function SHALL add it to the pending deregistration list with invocation count 1
3. WHEN a pending IP remains absent from DNS across multiple invocations, THE Lambda_Function SHALL increment its invocation count
4. WHEN a pending IP's invocation count reaches the configured threshold, THE Lambda_Function SHALL deregister it from the NLB target group
5. WHEN a pending IP reappears in DNS, THE Lambda_Function SHALL remove it from the pending deregistration list

### Requirement 5: Read Replica Addition and Removal

**User Story:** As a database administrator, I want to add or remove read replicas by updating the environment variable, so that the Lambda function automatically adapts to cluster topology changes.

#### Acceptance Criteria

1. WHEN a new DNS name is added to the environment variable, THE Lambda_Function SHALL begin resolving it on the next invocation
2. WHEN a DNS name is removed from the environment variable, THE Lambda_Function SHALL stop resolving it on the next invocation
3. WHEN a DNS name is removed, THE Lambda_Function SHALL treat its IPs as no longer in DNS and begin the cautious deregistration process
4. WHEN read replica count changes, THE Lambda_Function SHALL continue using the same S3 state files without data loss
5. WHEN the environment variable is updated, THE Lambda_Function SHALL not require code changes or redeployment

### Requirement 6: CloudWatch Metrics (Optional)

**User Story:** As a system operator, I want CloudWatch metrics for total IP count across all read replicas, so that I can monitor the health and scale of the RDS cluster.

**Note:** This requirement is optional and not required for the current implementation.

#### Acceptance Criteria

1. WHEN CloudWatch metrics are enabled, THE Lambda_Function SHALL publish the total count of active IPs across all read replicas
2. WHEN publishing metrics, THE Lambda_Function SHALL use a metric name that distinguishes RDS read replica IPs from ALB IPs
3. WHEN publishing metrics, THE Lambda_Function SHALL include a dimension identifying the RDS cluster or state prefix
4. WHEN CloudWatch metrics are disabled via environment variable, THE Lambda_Function SHALL skip metric publishing
5. THE Lambda_Function SHALL publish metrics only when IP registration succeeds

### Requirement 7: DNS Resolution Strategy

**User Story:** As a system operator, I want the Lambda function to use the same DNS resolution strategy as the ALB solution, so that IP discovery is reliable and consistent.

#### Acceptance Criteria

1. WHEN resolving RDS DNS names, THE Lambda_Function SHALL query authoritative name servers for the RDS regional domain
2. WHEN performing DNS lookups, THE Lambda_Function SHALL retry up to MAX_LOOKUP_PER_INVOCATION times per DNS name
3. WHEN DNS lookup fails for a specific name server, THE Lambda_Function SHALL retry with remaining name servers
4. THE Lambda_Function SHALL use DNS record type A for IPv4 address resolution

### Requirement 8: Error Handling and Logging

**User Story:** As a system operator, I want comprehensive error logging to CloudWatch Logs, so that I can troubleshoot issues with DNS resolution or NLB registration.

#### Acceptance Criteria

1. WHEN a DNS name fails to resolve, THE Lambda_Function SHALL log the DNS name and error details to CloudWatch Logs
2. WHEN NLB registration fails, THE Lambda_Function SHALL log the target IPs and target group ARN to CloudWatch Logs
3. WHEN NLB deregistration fails, THE Lambda_Function SHALL log the target IPs and target group ARN to CloudWatch Logs
4. WHEN S3 operations fail, THE Lambda_Function SHALL log the bucket name, object key, and error details to CloudWatch Logs
5. WHEN environment variable validation fails, THE Lambda_Function SHALL log the missing or invalid variable name to CloudWatch Logs and exit
6. THE Lambda_Function SHALL accept an environment variable named CLOUDWATCH_LOG_GROUP specifying the CloudWatch Logs group name
7. WHEN the CLOUDWATCH_LOG_GROUP environment variable is not provided, THE Lambda_Function SHALL use the default Lambda log group

### Requirement 9: State File Format

**User Story:** As a system operator, I want state files to maintain the same JSON structure as the ALB solution, so that state can be inspected and debugged using the same tools.

#### Acceptance Criteria

1. WHEN storing active IPs, THE Lambda_Function SHALL use JSON format with fields: LoadBalancerName, TimeStamp, IPList, IPCount
2. WHEN storing pending IPs, THE Lambda_Function SHALL use JSON format mapping IP addresses to invocation counts
3. WHEN the LoadBalancerName field is populated, THE Lambda_Function SHALL use the state prefix or a descriptive identifier for the RDS cluster
4. WHEN writing to S3, THE Lambda_Function SHALL serialize state as valid JSON
5. WHEN reading from S3, THE Lambda_Function SHALL parse JSON and handle missing files gracefully
