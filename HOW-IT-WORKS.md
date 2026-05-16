## Architecture Overview

```
┌──────────────┐    every 1 min    ┌─────────────────────┐
│  EventBridge │──────────────────▶│   Lambda Function   │
│  (Scheduler) │                   │ (RDS-NLB-Registration)│
└──────────────┘                   └─────────┬───────────┘
                                             │
                        ┌────────────────────┼────────────────────┐
                        │                    │                    │
                        ▼                    ▼                    ▼
                ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
                │  VPC DNS     │    │   S3 Bucket  │    │  NLB Target  │
                │  Resolver    │    │  (State)     │    │  Group       │
                └──────────────┘    └──────────────┘    └──────────────┘
                        │                                        │
                        ▼                                        ▼
                ┌──────────────┐                        ┌──────────────┐
                │ RDS Read     │◀───────────────────────│ Network Load │
                │ Replicas     │      traffic flow      │ Balancer     │
                └──────────────┘                        └──────────────┘
```

## How EventBridge Triggers the Lambda

The CloudFormation template creates an EventBridge rule with `ScheduleExpression: rate(1 minute)`. This rule fires every 60 seconds and invokes the Lambda function. A `AWS::Lambda::Permission` resource grants EventBridge the right to call the function.

This 1-minute cadence means that if an RDS replica's IP changes, the NLB target group will be updated within at most 1 minute for new IPs (registration) or N minutes for stale IPs (deregistration, where N = `INVOCATIONS_BEFORE_DEREGISTRATION`).

## What the Lambda Does (Step by Step)

Each invocation follows a 7-step process:

### Step 1: DNS Resolution

The Lambda reads the `RDS_REPLICA_DNS_NAMES` environment variable (comma-separated list of replica DNS names) and resolves each one to its current IP address using the VPC DNS resolver.

For each DNS name, it attempts resolution up to `MAX_LOOKUP_PER_INVOCATION` times (default: 5). This retry mechanism handles transient DNS failures — if the first attempt times out or returns empty, it tries again. On success, it breaks early.

If no IPs are resolved at all across all replicas, the Lambda exits without making any changes to the target group. This is a safety measure — it's better to do nothing than to deregister everything because DNS was temporarily unreachable.

### Step 2: Get Current Target Group State

The Lambda calls `DescribeTargetHealth` on the NLB target group to get the list of IPs currently registered. This is the "ground truth" of what the NLB is actually routing traffic to.

### Step 3: Load Previous Invocation State from S3

The Lambda downloads two JSON files from S3:
- `{STATE_PREFIX}/active_ip.json` — the IPs that were resolved from DNS during the last successful invocation
- `{STATE_PREFIX}/pending_ip.json` — IPs that are candidates for deregistration and how many invocations they've been flagged

This state is what enables the cautious deregistration logic (explained below).

### Step 4: Determine IPs to Register

Simple set difference:

```
pending_registration = IPs_from_DNS - IPs_in_target_group
```

Any IP that DNS returned but isn't already in the target group gets registered immediately. No waiting, no grace period.

### Step 5: Determine IPs to Deregister

This is where the cautious logic kicks in. An IP becomes a deregistration candidate if:
- It was in the active list from the previous invocation but is no longer in DNS, OR
- It's currently registered in the target group but no longer in DNS

But it doesn't get deregistered right away. Instead, the Lambda tracks how many consecutive invocations each candidate IP has been flagged. This count is persisted in `pending_ip.json` on S3.

### Step 6: Execute Registration and Deregistration

- New IPs → `RegisterTargets` API call (immediate)
- Stale IPs that have hit the invocation threshold → `DeregisterTargets` API call

### Step 7: Save State to S3

- If registration succeeded, upload the current DNS IPs as `active_ip.json`
- Always upload the updated pending deregistration IP counts as `pending_ip.json`

## Why Registration is Aggressive but Deregistration is Cautious

This asymmetry is a deliberate design choice based on the consequences of getting it wrong:

**Wrong registration (registering an IP that shouldn't be there):** Low risk. The NLB performs health checks on all targets. If an IP is invalid or unreachable, the health check will mark it as unhealthy and the NLB won't route traffic to it. The IP will naturally get cleaned up in subsequent invocations when it stops appearing in DNS.

**Wrong deregistration (removing an IP that's still valid):** High risk. Active database connections flowing through that IP get dropped. Queries in progress fail. The application sees connection errors until the IP gets re-registered in the next invocation (up to 1 minute later). For a database, even brief connection drops can cause transaction failures and application errors.

So the design registers immediately (let health checks catch mistakes) but deregisters cautiously (make sure the IP is really gone before removing it).

## The Deregistration Logic in Detail

Here's how the invocation counting works with the default `INVOCATIONS_BEFORE_DEREGISTRATION = 3`:

```
Minute 0: DNS returns [10.0.1.5, 10.0.1.6], target group has [10.0.1.5, 10.0.1.6]
           → Everything matches. No action.

Minute 1: DNS returns [10.0.1.5] (10.0.1.6 disappeared — maybe a failover)
           → 10.0.1.6 flagged as pending deregistration, count = 1
           → Saved to S3: {"10.0.1.6": 1}

Minute 2: DNS still returns [10.0.1.5] only
           → 10.0.1.6 still missing, count bumped to 2
           → Saved to S3: {"10.0.1.6": 2}

Minute 3: DNS still returns [10.0.1.5] only
           → 10.0.1.6 count reaches 3 (= threshold)
           → DeregisterTargets called for 10.0.1.6
```

But if the IP comes back before hitting the threshold:

```
Minute 1: DNS returns [10.0.1.5] → 10.0.1.6 flagged, count = 1
Minute 2: DNS returns [10.0.1.5, 10.0.1.6] → 10.0.1.6 is back in DNS
           → It's removed from the pending list, counter resets
           → No deregistration happens
```

This prevents "flapping" — where a transient DNS hiccup would cause an IP to be deregistered and immediately re-registered, potentially dropping connections for no good reason.

## How the S3 Bucket Works

S3 serves as the persistent state store between Lambda invocations. Since Lambda is stateless (each invocation starts fresh), the function needs somewhere to remember what happened last time.

Two files are stored under the `STATE_PREFIX` path:

### `{STATE_PREFIX}/active_ip.json`

Contains the IPs from the most recent successful DNS resolution and registration:

```json
{
  "LoadBalancerName": "rds-cluster-read-replicas",
  "TimeStamp": "2025-01-15 10:30:00",
  "IPList": ["10.0.1.5", "10.0.1.6"],
  "IPCount": 2
}
```

This file is only updated when a registration actually succeeds. This prevents the Lambda from "forgetting" about IPs it registered if a subsequent invocation fails to register new ones.

### `{STATE_PREFIX}/pending_ip.json`

Tracks IPs that are candidates for deregistration and their invocation count:

```json
{
  "10.0.1.6": 2,
  "10.0.3.100": 1
}
```

This file is updated every invocation. It's the mechanism that implements the cautious deregistration — each IP must accumulate enough consecutive "missing" counts before it gets removed.

### First Run Behavior

On the very first invocation (or if the S3 files don't exist), the Lambda handles the missing files gracefully — it logs a warning and treats the previous state as empty. This means the first run will register all discovered IPs and start tracking from scratch.

## Configuration Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `RDSReplicaDNSNames` | — | Comma-separated DNS names of your RDS read replicas |
| `NLBTargetGroupARN` | — | The NLB target group to manage |
| `S3BucketName` | — | Bucket for state persistence |
| `RDSListenerPort` | 3306 | Database port (3306 MySQL, 5432 PostgreSQL) |
| `MAXDNSLookupPerInvocation` | 5 | DNS retry attempts per replica name |
| `InvocationBeforeDeregistration` | 3 | Consecutive misses before deregistration |
| `StatePrefix` | rds-cluster-read-replicas | S3 key prefix for state files |

## CloudWatch Logs

The Lambda function writes logs to its default CloudWatch Logs group at `/aws/lambda/{function-name}`. With the parameterized stack name, this becomes `/aws/lambda/{stack-name}-RDS-NLB-Registration`.

No custom log group configuration is needed — the Lambda runtime creates the log group automatically on first invocation. The IAM policy in the CloudFormation template grants `logs:CreateLogGroup`, `logs:CreateLogStream`, and `logs:PutLogEvents` scoped to this specific log group.

At the end of each invocation, the function emits a structured JSON summary log entry containing the request ID, number of resolved IPs, registration/deregistration counts, and whether the circuit breaker was triggered. This can be queried in CloudWatch Logs Insights:

```
fields @timestamp, dns_resolved_ips, registered, deregistered, deregistration_skipped
| filter event = "invocation_summary"
| sort @timestamp desc
| limit 20
```
