# Architecture Diagrams Reference

This document contains additional detailed diagrams for the Aurora to Snowflake replication system.

## Table of Contents

1. [Detailed Component Interactions](#detailed-component-interactions)
2. [Data Replication Sequence](#data-replication-sequence)
3. [Error Handling Architecture](#error-handling-architecture)
4. [Security Architecture Details](#security-architecture-details)
5. [Network Topology](#network-topology)
6. [Deployment Sequence](#deployment-sequence)

## Detailed Component Interactions

### Lambda Function Internal Architecture

```mermaid
graph TB
    subgraph "Lambda Handler Layer"
        Handler[lambda_handler]
        Config[Configuration Manager]
        ErrorHandler[Error Handler]
    end
    
    subgraph "Client Layer"
        VaultClient[Vault Client<br/>- IAM Auth<br/>- Token Auth<br/>- Secret Retrieval]
        AuroraClient[Aurora Client<br/>- Connection<br/>- Schema Retrieval<br/>- Data Extraction]
        SnowflakeClient[Snowflake Client<br/>- Connection<br/>- Table Creation<br/>- Data Loading]
    end
    
    subgraph "Business Logic Layer"
        ReplicationEngine[Replication Engine<br/>- Batch Processing<br/>- State Management<br/>- Coordination]
    end
    
    subgraph "Utility Layer"
        Logger[Logging Utils<br/>- Structured Logs<br/>- Correlation IDs]
        Validator[Validation Utils<br/>- Input Validation<br/>- Schema Validation]
        Metrics[Metrics Utils<br/>- Custom Metrics<br/>- Performance Tracking]
    end
    
    Handler --> Config
    Handler --> ReplicationEngine
    Handler --> ErrorHandler
    
    ReplicationEngine --> VaultClient
    ReplicationEngine --> AuroraClient
    ReplicationEngine --> SnowflakeClient
    
    VaultClient --> Logger
    AuroraClient --> Logger
    SnowflakeClient --> Logger
    ReplicationEngine --> Logger
    
    ReplicationEngine --> Validator
    ReplicationEngine --> Metrics
    
    style Handler fill:#4A90E2
    style ReplicationEngine fill:#50C878
    style VaultClient fill:#FFA500
```

## Data Replication Sequence

### Complete Replication Sequence

```mermaid
sequenceDiagram
    autonumber
    participant EB as EventBridge
    participant Lambda as Lambda Handler
    participant Vault as Hashicorp Vault
    participant Aurora as Aurora PostgreSQL
    participant Engine as Replication Engine
    participant SF as Snowflake
    participant CW as CloudWatch
    
    EB->>Lambda: Trigger Event (scheduled/manual)
    Lambda->>CW: Log: Function Started
    
    Lambda->>Lambda: Get Environment Variables
    Lambda->>Lambda: Validate Configuration
    
    Lambda->>Vault: Authenticate (IAM/Token)
    Vault-->>Lambda: Vault Token
    
    Lambda->>Vault: Get Aurora Secrets
    Vault-->>Lambda: Connection Credentials
    
    Lambda->>Vault: Get Snowflake Secrets
    Vault-->>Lambda: Connection Credentials
    
    Lambda->>Engine: Initialize Replication Engine
    
    Engine->>Aurora: Connect (TLS)
    Aurora-->>Engine: Connection Established
    
    Engine->>Aurora: Get Table Schema
    Aurora-->>Engine: Schema Information
    
    Engine->>SF: Connect via PrivateLink (TLS)
    SF-->>Engine: Connection Established
    
    Engine->>SF: Create Table (if not exists)
    SF-->>Engine: Table Ready
    
    alt Full Replication Mode
        Engine->>SF: Truncate Table
        SF-->>Engine: Table Truncated
    else Incremental Replication Mode
        Engine->>Engine: Load Last Value
    end
    
    loop For Each Batch
        Engine->>Aurora: Extract Batch (LIMIT batch_size)
        Aurora-->>Engine: Batch Data
        
        Engine->>SF: Load Batch Data (INSERT)
        SF-->>Engine: Rows Inserted
        
        Engine->>Engine: Update Last Value (if incremental)
        Engine->>CW: Log: Batch Processed
    end
    
    Engine->>Engine: Save State (if incremental)
    Engine->>CW: Log: Replication Complete
    Engine->>CW: Metrics: Rows Replicated
    
    Lambda-->>EB: Success Response
```

## Error Handling Architecture

### Error Handling Flow

```mermaid
flowchart TD
    Start([Operation Start]) --> Try{Try Operation}
    
    Try -->|Success| LogSuccess[Log Success]
    LogSuccess --> ReturnSuccess([Return Success])
    
    Try -->|Exception| Catch[Catch Exception]
    Catch --> Classify{Classify Error}
    
    Classify -->|Connection Error| RetryConn[Retry Connection<br/>Exponential Backoff]
    Classify -->|Timeout Error| RetryTimeout[Retry Operation<br/>Exponential Backoff]
    Classify -->|Data Error| LogDataError[Log Data Error]
    Classify -->|Auth Error| LogAuthError[Log Auth Error]
    Classify -->|Unknown Error| LogUnknown[Log Unknown Error]
    
    RetryConn --> CheckRetries{Retries<br/>Exceeded?}
    RetryTimeout --> CheckRetries
    
    CheckRetries -->|No| Try
    CheckRetries -->|Yes| SendDLQ[Send to DLQ]
    
    LogDataError --> SendDLQ
    LogAuthError --> SendDLQ
    LogUnknown --> SendDLQ
    
    SendDLQ --> TriggerAlarm[Trigger CloudWatch Alarm]
    TriggerAlarm --> NotifySNS[Notify via SNS]
    NotifySNS --> ReturnError([Return Error])
    
    style Try fill:#FFD700
    style Classify fill:#FFD700
    style CheckRetries fill:#FFD700
    style SendDLQ fill:#FF6B6B
    style ReturnSuccess fill:#50C878
```

### Error Types and Handling

```mermaid
graph LR
    subgraph "Transient Errors - Retry"
        ConnErr[Connection Errors<br/>- Network issues<br/>- Timeout<br/>- Service unavailable]
        TempErr[Temporary Errors<br/>- Rate limiting<br/>- Throttling<br/>- Resource exhaustion]
    end
    
    subgraph "Permanent Errors - No Retry"
        AuthErr[Authentication Errors<br/>- Invalid credentials<br/>- Expired tokens<br/>- Permission denied]
        DataErr[Data Errors<br/>- Schema mismatch<br/>- Invalid data types<br/>- Constraint violations]
        ConfigErr[Configuration Errors<br/>- Missing env vars<br/>- Invalid config<br/>- Missing resources]
    end
    
    ConnErr --> Retry[Retry with<br/>Exponential Backoff]
    TempErr --> Retry
    Retry -->|Max Retries| DLQ[Dead Letter Queue]
    
    AuthErr --> DLQ
    DataErr --> DLQ
    ConfigErr --> DLQ
    
    DLQ --> Alert[Alert Operations]
    
    style ConnErr fill:#FFA500
    style TempErr fill:#FFA500
    style AuthErr fill:#FF6B6B
    style DataErr fill:#FF6B6B
    style ConfigErr fill:#FF6B6B
    style DLQ fill:#8B0000,color:#fff
```

## Security Architecture Details

### Authentication and Authorization Flow

```mermaid
sequenceDiagram
    participant Lambda as Lambda Function
    participant IAM as AWS IAM
    participant Vault as Hashicorp Vault
    participant Aurora as Aurora PostgreSQL
    participant SF as Snowflake
    
    Note over Lambda: Lambda Execution Starts
    
    Lambda->>IAM: Assume Execution Role
    IAM-->>Lambda: Temporary Credentials
    
    Lambda->>IAM: Get Caller Identity
    IAM-->>Lambda: IAM Identity
    
    Lambda->>Vault: Authenticate with IAM
    Note over Lambda,Vault: Uses IAM identity<br/>for Vault IAM auth
    Vault->>IAM: Verify IAM Identity
    IAM-->>Vault: Identity Verified
    Vault-->>Lambda: Vault Token
    
    Lambda->>Vault: Read Aurora Secrets (with token)
    Vault-->>Lambda: Aurora Credentials
    
    Lambda->>Vault: Read Snowflake Secrets (with token)
    Vault-->>Lambda: Snowflake Credentials
    
    Lambda->>Aurora: Connect with Credentials
    Note over Lambda,Aurora: TLS Encrypted<br/>VPC Isolated
    Aurora->>Aurora: Verify User Permissions
    Aurora-->>Lambda: Connection Authorized
    
    Lambda->>SF: Connect with Credentials
    Note over Lambda,SF: TLS Encrypted<br/>PrivateLink
    SF->>SF: Verify User/Role Permissions
    SF-->>Lambda: Connection Authorized
```

### Security Boundaries

```mermaid
graph TB
    subgraph "Public Internet"
        Internet[Internet]
    end
    
    subgraph "AWS VPC - Isolated Network"
        subgraph "Private Subnet - Lambda"
            Lambda[Lambda Function<br/>No Public IP]
        end
        
        subgraph "Private Subnet - Database"
            Aurora[Aurora PostgreSQL<br/>Private Endpoint]
        end
        
        subgraph "Private Subnet - VPC Endpoint"
            VPCe[VPC Endpoint<br/>Snowflake PrivateLink]
        end
        
        NAT[NAT Gateway<br/>Outbound Only]
        SG[Security Groups<br/>Restrictive Rules]
    end
    
    subgraph "Hashicorp Vault"
        Vault[Vault Server<br/>TLS Encrypted]
    end
    
    subgraph "Snowflake Cloud"
        SF[Snowflake<br/>Private Network]
    end
    
    Internet -.->|HTTPS Only| NAT
    NAT -.->|HTTPS Only| Vault
    Lambda -->|Port 5432<br/>Within VPC| Aurora
    Lambda -->|Port 443<br/>Within VPC| VPCe
    VPCe -->|PrivateLink<br/>Port 443| SF
    
    SG -.->|Controls| Lambda
    SG -.->|Controls| Aurora
    SG -.->|Controls| VPCe
    
    style Lambda fill:#4A90E2
    style Aurora fill:#FF6B6B
    style SF fill:#29B5E8
    style Vault fill:#FFA500
    style SG fill:#9370DB
```

## Network Topology

### Detailed Network Architecture

```mermaid
graph TB
    subgraph "AWS Account"
        subgraph "VPC: 10.0.0.0/16"
            subgraph "Availability Zone 1"
                subgraph "Private Subnet 1a: 10.0.1.0/24"
                    Lambda1[Lambda ENI 1<br/>10.0.1.10]
                end
                
                subgraph "Private Subnet 1b: 10.0.2.0/24"
                    VPCe1[VPC Endpoint 1<br/>10.0.2.10]
                end
            end
            
            subgraph "Availability Zone 2"
                subgraph "Private Subnet 2a: 10.0.3.0/24"
                    Lambda2[Lambda ENI 2<br/>10.0.3.10]
                end
                
                subgraph "Private Subnet 2b: 10.0.4.0/24"
                    VPCe2[VPC Endpoint 2<br/>10.0.4.10]
                end
            end
            
            subgraph "Database Subnets"
                subgraph "DB Subnet 1: 10.0.10.0/24"
                    Aurora1[Aurora Instance 1<br/>10.0.10.50]
                end
                
                subgraph "DB Subnet 2: 10.0.11.0/24"
                    Aurora2[Aurora Instance 2<br/>10.0.11.50]
                end
            end
            
            NAT1[NAT Gateway 1<br/>10.0.0.100]
            NAT2[NAT Gateway 2<br/>10.0.0.101]
            IGW[Internet Gateway]
        end
    end
    
    subgraph "Snowflake PrivateLink"
        SF1[Snowflake Endpoint 1]
        SF2[Snowflake Endpoint 2]
    end
    
    Lambda1 -->|Port 5432| Aurora1
    Lambda1 -->|Port 5432| Aurora2
    Lambda2 -->|Port 5432| Aurora1
    Lambda2 -->|Port 5432| Aurora2
    
    Lambda1 -->|Port 443| VPCe1
    Lambda2 -->|Port 443| VPCe2
    
    VPCe1 -->|PrivateLink| SF1
    VPCe2 -->|PrivateLink| SF2
    
    Lambda1 -->|Port 443| NAT1
    Lambda2 -->|Port 443| NAT2
    NAT1 --> IGW
    NAT2 --> IGW
    
    style Lambda1 fill:#4A90E2
    style Lambda2 fill:#4A90E2
    style Aurora1 fill:#FF6B6B
    style Aurora2 fill:#FF6B6B
    style SF1 fill:#29B5E8
    style SF2 fill:#29B5E8
```

## Deployment Sequence

### Complete Deployment Flow

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant GitHub as GitHub
    participant GA as GitHub Actions
    participant Artifactory as Artifactory
    participant Terraform as Terraform Cloud
    participant Harness as Harness
    participant AWS as AWS
    participant Lambda as Lambda Function
    
    Dev->>GitHub: Push Code Changes
    GitHub->>GA: Trigger Build Workflow
    
    GA->>GA: Run Linters
    GA->>GA: Run Tests
    GA->>GA: Security Scans
    
    GA->>GA: Build Lambda Package
    GA->>Artifactory: Upload Package
    
    Note over Dev,Terraform: Infrastructure Changes
    Dev->>GitHub: Push Terraform Changes
    GitHub->>Terraform: Trigger Terraform Run
    
    Terraform->>Terraform: Terraform Plan
    Terraform->>AWS: Create/Update Resources
    AWS-->>Terraform: Resources Created
    
    Note over Dev,Harness: Deployment
    Dev->>Harness: Trigger Deployment Pipeline
    
    Harness->>Terraform: Verify Infrastructure
    Terraform-->>Harness: Infrastructure Ready
    
    Harness->>Artifactory: Download Package
    Artifactory-->>Harness: Lambda Package
    
    Harness->>AWS: Update Lambda Function Code
    AWS->>Lambda: Deploy New Code
    Lambda-->>AWS: Deployment Complete
    
    Harness->>Lambda: Invoke Test
    Lambda-->>Harness: Test Successful
    
    Harness->>Harness: Verify CloudWatch Logs
    Harness-->>Dev: Deployment Complete
```

## Data Flow Details

### Incremental Replication State Flow

```mermaid
stateDiagram-v2
    [*] --> Initial: Start Replication
    
    Initial --> LoadState: Get Last Value
    LoadState --> ExtractBatch: Load from Storage
    
    ExtractBatch --> CheckData: Query Aurora
    
    CheckData --> NoData: No New Data
    CheckData --> HasData: Has New Data
    
    HasData --> LoadBatch: Extract Batch
    LoadBatch --> InsertSnowflake: Load to Snowflake
    InsertSnowflake --> UpdateState: Update Last Value
    UpdateState --> SaveState: Persist State
    SaveState --> ExtractBatch: Continue
    
    NoData --> Complete: Replication Done
    Complete --> [*]
    
    note right of LoadState
        Load from DynamoDB
        or Parameter Store
    end note
    
    note right of SaveState
        Save to DynamoDB
        or Parameter Store
    end note
```

### Batch Processing State Machine

```mermaid
stateDiagram-v2
    [*] --> Idle: System Ready
    
    Idle --> Connecting: Event Triggered
    
    Connecting --> Connected: Connection Established
    Connecting --> ConnectionFailed: Connection Error
    
    ConnectionFailed --> RetryConnection: Retry Logic
    RetryConnection --> Connecting: Retry Attempt
    RetryConnection --> Failed: Max Retries
    
    Connected --> GettingSchema: Get Table Schema
    GettingSchema --> SchemaRetrieved: Schema Loaded
    
    SchemaRetrieved --> CreatingTable: Create/Verify Table
    CreatingTable --> TableReady: Table Ready
    
    TableReady --> ProcessingBatches: Start Batch Loop
    
    ProcessingBatches --> ExtractingBatch: Extract Batch
    ExtractingBatch --> BatchExtracted: Batch Loaded
    
    BatchExtracted --> LoadingBatch: Load to Snowflake
    LoadingBatch --> BatchLoaded: Batch Inserted
    
    BatchLoaded --> MoreData: Check for More
    MoreData --> ExtractingBatch: More Data Available
    MoreData --> Completed: All Data Processed
    
    Completed --> Idle: Return to Idle
    Failed --> Idle: Error Handled
    
    note right of RetryConnection
        Exponential Backoff
        Max 3 Retries
    end note
```

## Performance Architecture

### Performance Optimization Flow

```mermaid
graph TB
    subgraph "Performance Factors"
        BatchSize[Batch Size<br/>Configurable]
        Memory[Lambda Memory<br/>512MB - 10GB]
        Timeout[Lambda Timeout<br/>Up to 15 min]
        Mode[Replication Mode<br/>Full vs Incremental]
    end
    
    subgraph "Optimization Strategies"
        Adaptive[Adaptive Batching<br/>Based on Row Size]
        Parallel[Parallel Processing<br/>Multiple Batches]
        Incremental[Incremental Mode<br/>Only Changed Data]
        COPY[COPY INTO<br/>Bulk Loading]
    end
    
    subgraph "Monitoring"
        Metrics[Performance Metrics<br/>Duration, Throughput]
        Alerts[Performance Alerts<br/>Slow Queries]
        Tuning[Auto Tuning<br/>Adjust Parameters]
    end
    
    BatchSize --> Adaptive
    Memory --> Parallel
    Timeout --> Parallel
    Mode --> Incremental
    
    Adaptive --> Metrics
    Parallel --> Metrics
    Incremental --> Metrics
    COPY --> Metrics
    
    Metrics --> Alerts
    Metrics --> Tuning
    Tuning --> BatchSize
    Tuning --> Memory
    
    style BatchSize fill:#4A90E2
    style Adaptive fill:#50C878
    style Metrics fill:#FFA500
```

