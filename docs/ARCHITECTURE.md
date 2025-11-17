# Solution Architecture Documentation

## Table of Contents

1. [Overview](#overview)
2. [Architecture Principles](#architecture-principles)
3. [System Architecture](#system-architecture)
4. [Component Architecture](#component-architecture)
5. [Data Flow](#data-flow)
6. [Infrastructure Architecture](#infrastructure-architecture)
7. [Security Architecture](#security-architecture)
8. [Deployment Architecture](#deployment-architecture)
9. [Operational Architecture](#operational-architecture)
10. [Technology Stack](#technology-stack)

## Overview

The Aurora PostgreSQL to Snowflake replication system is a serverless, event-driven batch replication solution that securely transfers data from AWS Aurora v2 PostgreSQL to Snowflake via PrivateLink. The system is designed for reliability, security, and cost-effectiveness.

### Key Characteristics

- **Serverless**: AWS Lambda-based, no always-on infrastructure
- **Event-Driven**: Scheduled via EventBridge, can be manually triggered
- **Secure**: VPC isolation, PrivateLink connectivity, secrets in Vault
- **Infrastructure as Code**: All infrastructure managed via Terraform Cloud
- **CI/CD**: Automated builds and deployments via GitHub Actions and Harness
- **Observable**: Comprehensive logging and monitoring via CloudWatch

## Architecture Principles

1. **Security First**: All connections use encryption, VPC isolation, and secrets management
2. **Reliability**: Error handling, retry logic, and dead letter queues
3. **Scalability**: Serverless architecture scales automatically
4. **Cost Optimization**: Pay-per-use model, efficient batch processing
5. **Observability**: Comprehensive logging, metrics, and alarms
6. **Infrastructure as Code**: All infrastructure versioned and automated

## System Architecture

### High-Level Architecture Diagram

```mermaid
graph TB
    subgraph "AWS Cloud"
        subgraph "VPC"
            subgraph "Private Subnets"
                Lambda[Lambda Function]
                VPCe[VPC Endpoint<br/>Snowflake PrivateLink]
            end
            Aurora[Aurora PostgreSQL<br/>Cluster]
            SG[Security Groups]
        end
        
        EventBridge[EventBridge<br/>Scheduler]
        CloudWatch[CloudWatch<br/>Logs & Metrics]
        Vault[Hashicorp Vault<br/>Secrets]
    end
    
    subgraph "Snowflake Cloud"
        SF[Snowflake<br/>Data Warehouse]
    end
    
    subgraph "CI/CD Pipeline"
        GitHub[GitHub<br/>Actions]
        Artifactory[Artifactory<br/>Artifacts]
        Harness[Harness<br/>CD Pipeline]
    end
    
    subgraph "Infrastructure"
        Terraform[Terraform Cloud<br/>IaC]
    end
    
    EventBridge -->|Triggers| Lambda
    Lambda -->|Reads Secrets| Vault
    Lambda -->|Extracts Data| Aurora
    Lambda -->|Loads Data| VPCe
    VPCe -->|PrivateLink| SF
    Lambda -->|Logs| CloudWatch
    EventBridge -->|Metrics| CloudWatch
    
    GitHub -->|Builds| Artifactory
    Artifactory -->|Deploys| Harness
    Harness -->|Updates| Lambda
    Terraform -->|Manages| Lambda
    Terraform -->|Manages| EventBridge
    Terraform -->|Manages| VPCe
    
    style Lambda fill:#4A90E2
    style Aurora fill:#FF6B6B
    style SF fill:#29B5E8
    style Vault fill:#FFA500
```

## Component Architecture

### Component Diagram

```mermaid
graph LR
    subgraph "Lambda Function"
        Handler[Lambda Handler]
        VaultClient[Vault Client]
        AuroraClient[Aurora Client]
        SnowflakeClient[Snowflake Client]
        ReplicationEngine[Replication Engine]
        Utils[Utilities]
    end
    
    subgraph "External Services"
        Vault[Hashicorp Vault]
        Aurora[Aurora PostgreSQL]
        Snowflake[Snowflake]
    end
    
    Handler --> VaultClient
    Handler --> ReplicationEngine
    VaultClient --> Vault
    ReplicationEngine --> AuroraClient
    ReplicationEngine --> SnowflakeClient
    AuroraClient --> Aurora
    SnowflakeClient --> Snowflake
    ReplicationEngine --> Utils
    
    style Handler fill:#4A90E2
    style ReplicationEngine fill:#50C878
```

### Component Responsibilities

#### Lambda Handler (`lambda_function.py`)
- Entry point for Lambda invocations
- Retrieves configuration from environment variables
- Authenticates with Vault and retrieves secrets
- Orchestrates replication process
- Handles errors and returns responses

#### Vault Client (`vault_client.py`)
- Manages authentication to Hashicorp Vault
- Supports IAM and token-based authentication
- Retrieves secrets for Aurora and Snowflake connections
- Handles Vault API errors

#### Aurora Client (`aurora_client.py`)
- Establishes connection to Aurora PostgreSQL
- Retrieves table schema information
- Extracts data in batches
- Supports full and incremental extraction modes
- Handles connection errors and retries

#### Snowflake Client (`snowflake_client.py`)
- Establishes connection to Snowflake via PrivateLink
- Creates tables based on Aurora schema
- Loads data using INSERT statements
- Maps PostgreSQL types to Snowflake types
- Handles connection and query errors

#### Replication Engine (`replication.py`)
- Core replication logic
- Coordinates data extraction and loading
- Manages batch processing
- Tracks replication progress
- Handles incremental replication state

#### Utilities (`utils.py`)
- Logging utilities
- Response formatting
- Correlation ID generation
- Environment variable management

## Data Flow

### Replication Flow Diagram

```mermaid
sequenceDiagram
    participant EB as EventBridge
    participant Lambda as Lambda Function
    participant Vault as Hashicorp Vault
    participant Aurora as Aurora PostgreSQL
    participant SF as Snowflake
    
    EB->>Lambda: Trigger (scheduled/manual)
    Lambda->>Vault: Authenticate & Get Secrets
    Vault-->>Lambda: Aurora & Snowflake Credentials
    
    Lambda->>Aurora: Connect & Get Schema
    Aurora-->>Lambda: Table Schema
    
    Lambda->>SF: Connect via PrivateLink
    SF-->>Lambda: Connection Established
    
    Lambda->>SF: Create Table (if not exists)
    SF-->>Lambda: Table Ready
    
    loop For Each Batch
        Lambda->>Aurora: Extract Batch Data
        Aurora-->>Lambda: Batch Rows
        Lambda->>SF: Load Batch Data
        SF-->>Lambda: Rows Inserted
    end
    
    Lambda->>Lambda: Update State (if incremental)
    Lambda-->>EB: Success Response
```

### Batch Processing Flow

```mermaid
flowchart TD
    Start([Start Replication]) --> GetSchema[Get Table Schema]
    GetSchema --> CreateTable[Create/Verify Snowflake Table]
    CreateTable --> CheckMode{Replication Mode?}
    
    CheckMode -->|Full| Truncate[Truncate Target Table]
    CheckMode -->|Incremental| LoadState[Load Last Value]
    
    Truncate --> ExtractBatch[Extract Batch from Aurora]
    LoadState --> ExtractBatch
    
    ExtractBatch --> CheckData{Data Available?}
    CheckData -->|No| End([Complete])
    CheckData -->|Yes| LoadBatch[Load Batch to Snowflake]
    
    LoadBatch --> UpdateState[Update Last Value]
    UpdateState --> CheckMore{More Data?}
    
    CheckMore -->|Yes| ExtractBatch
    CheckMore -->|No| End
    
    style Start fill:#90EE90
    style End fill:#FF6B6B
    style CheckMode fill:#FFD700
    style CheckData fill:#FFD700
    style CheckMore fill:#FFD700
```

## Infrastructure Architecture

### Infrastructure Diagram

```mermaid
graph TB
    subgraph "AWS Account"
        subgraph "Region: us-east-1"
            subgraph "VPC: Production VPC"
                subgraph "Private Subnet 1"
                    Lambda1[Lambda Function<br/>ENI 1]
                end
                subgraph "Private Subnet 2"
                    Lambda2[Lambda Function<br/>ENI 2]
                end
                
                VPCe[VPC Endpoint<br/>Snowflake PrivateLink<br/>Interface Endpoint]
                
                SG[Security Group<br/>Lambda → Aurora: 5432<br/>Lambda → VPCe: 443]
            end
            
            Aurora[Aurora PostgreSQL<br/>Cluster Endpoint]
            
            subgraph "EventBridge"
                Rule[EventBridge Rule<br/>Schedule: cron]
            end
            
            subgraph "CloudWatch"
                LogGroup[Log Group<br/>/aws/lambda/...]
                Metrics[Metrics<br/>Invocations, Errors, Duration]
                Alarms[Alarms<br/>Errors, Duration]
            end
            
            subgraph "IAM"
                Role[Lambda Execution Role<br/>VPC Access<br/>CloudWatch Logs<br/>Vault Auth]
            end
        end
    end
    
    subgraph "External Services"
        Vault[Hashicorp Vault<br/>Secrets Management]
        Snowflake[Snowflake<br/>via PrivateLink]
    end
    
    Rule -->|Triggers| Lambda1
    Rule -->|Triggers| Lambda2
    Lambda1 -->|Connects| Aurora
    Lambda2 -->|Connects| Aurora
    Lambda1 -->|Connects| VPCe
    Lambda2 -->|Connects| VPCe
    VPCe -->|PrivateLink| Snowflake
    Lambda1 -->|Authenticates| Vault
    Lambda2 -->|Authenticates| Vault
    Lambda1 -->|Logs| LogGroup
    Lambda2 -->|Logs| LogGroup
    Lambda1 -->|Metrics| Metrics
    Lambda2 -->|Metrics| Metrics
    Metrics -->|Alerts| Alarms
    
    Lambda1 -.->|Uses| Role
    Lambda2 -.->|Uses| Role
    
    style Lambda1 fill:#4A90E2
    style Lambda2 fill:#4A90E2
    style Aurora fill:#FF6B6B
    style Snowflake fill:#29B5E8
    style Vault fill:#FFA500
```

### Network Architecture

```mermaid
graph TB
    subgraph "VPC: 10.0.0.0/16"
        subgraph "Private Subnet 1: 10.0.1.0/24"
            Lambda[Lambda Function]
        end
        
        subgraph "Private Subnet 2: 10.0.2.0/24"
            VPCe[VPC Endpoint<br/>10.0.2.100]
        end
        
        subgraph "Database Subnet: 10.0.10.0/24"
            Aurora[Aurora PostgreSQL<br/>10.0.10.50]
        end
        
        NAT[NAT Gateway<br/>10.0.0.100]
        IGW[Internet Gateway]
    end
    
    subgraph "Snowflake PrivateLink"
        SF[Snowflake Endpoint<br/>Private IP]
    end
    
    Lambda -->|Port 5432<br/>TCP| Aurora
    Lambda -->|Port 443<br/>HTTPS| VPCe
    VPCe -->|PrivateLink<br/>Port 443| SF
    Lambda -->|Port 443<br/>HTTPS| NAT
    NAT -->|Port 443<br/>HTTPS| Vault[Hashicorp Vault<br/>Internet]
    NAT --> IGW
    
    style Lambda fill:#4A90E2
    style Aurora fill:#FF6B6B
    style SF fill:#29B5E8
    style VPCe fill:#9370DB
```

## Security Architecture

### Security Layers Diagram

```mermaid
graph TB
    subgraph "Layer 1: Network Security"
        VPC[VPC Isolation]
        SG[Security Groups]
        NACL[Network ACLs]
        VPCe[PrivateLink Endpoint]
    end
    
    subgraph "Layer 2: Access Control"
        IAM[IAM Roles & Policies]
        VaultAuth[Vault Authentication]
        DBUsers[Database Users]
    end
    
    subgraph "Layer 3: Data Security"
        TLS1[TLS Encryption<br/>Aurora]
        TLS2[TLS Encryption<br/>Snowflake]
        TLS3[TLS Encryption<br/>Vault]
        Encryption[Encryption at Rest]
    end
    
    subgraph "Layer 4: Secrets Management"
        Vault[Hashicorp Vault]
        NoSecrets[No Secrets in Code]
        Rotation[Secret Rotation Support]
    end
    
    subgraph "Layer 5: Monitoring & Auditing"
        CloudWatch[CloudWatch Logs]
        Metrics[CloudWatch Metrics]
        Alarms[CloudWatch Alarms]
        Audit[Audit Logging]
    end
    
    VPC --> IAM
    SG --> IAM
    IAM --> VaultAuth
    VaultAuth --> Vault
    Vault --> TLS3
    TLS1 --> Encryption
    TLS2 --> Encryption
    CloudWatch --> Audit
    
    style VPC fill:#FF6B6B
    style IAM fill:#4A90E2
    style Vault fill:#FFA500
    style Encryption fill:#50C878
```

### Security Flow

```mermaid
sequenceDiagram
    participant Lambda as Lambda Function
    participant IAM as IAM Role
    participant Vault as Hashicorp Vault
    participant Aurora as Aurora PostgreSQL
    participant SF as Snowflake
    
    Lambda->>IAM: Assume Role
    IAM-->>Lambda: Temporary Credentials
    
    Lambda->>Vault: Authenticate (IAM Auth)
    Note over Lambda,Vault: Uses IAM credentials<br/>for Vault auth
    Vault-->>Lambda: Vault Token
    
    Lambda->>Vault: Get Aurora Secrets
    Vault-->>Lambda: Encrypted Secrets
    
    Lambda->>Vault: Get Snowflake Secrets
    Vault-->>Lambda: Encrypted Secrets
    
    Lambda->>Aurora: Connect (TLS Encrypted)
    Note over Lambda,Aurora: SSL/TLS encryption<br/>in transit
    Aurora-->>Lambda: Connection Established
    
    Lambda->>SF: Connect via PrivateLink (TLS)
    Note over Lambda,SF: PrivateLink + TLS<br/>encryption
    SF-->>Lambda: Connection Established
```

## Deployment Architecture

### CI/CD Pipeline Flow

```mermaid
graph LR
    subgraph "Source Control"
        GitHub[GitHub Repository]
    end
    
    subgraph "Build Pipeline"
        GA1[GitHub Actions<br/>Lint & Test]
        GA2[GitHub Actions<br/>Build Package]
        Artifactory[Artifactory<br/>Store Artifact]
    end
    
    subgraph "Infrastructure Pipeline"
        Terraform[Terraform Cloud<br/>Plan & Apply]
        AWSInfra[AWS Infrastructure]
    end
    
    subgraph "Deployment Pipeline"
        Harness[Harness CD<br/>Deploy Lambda]
        Lambda[AWS Lambda]
    end
    
    GitHub -->|Push| GA1
    GA1 -->|Pass| GA2
    GA2 -->|Upload| Artifactory
    Artifactory -->|Download| Harness
    Harness -->|Deploy| Lambda
    
    GitHub -->|Terraform Files| Terraform
    Terraform -->|Create/Update| AWSInfra
    AWSInfra --> Lambda
    
    style GitHub fill:#24292e,color:#fff
    style Artifactory fill:#FF6B6B
    style Terraform fill:#7B42BC
    style Harness fill:#00B4D8
    style Lambda fill:#4A90E2
```

### Deployment Stages

```mermaid
graph TD
    Start([Code Commit]) --> Dev[Development]
    Dev -->|Merge| Staging[Staging]
    Staging -->|Approve| Prod[Production]
    
    subgraph "Development"
        DevBuild[Build & Test]
        DevTerraform[Terraform Plan]
        DevDeploy[Deploy to Dev]
        DevTest[Integration Tests]
    end
    
    subgraph "Staging"
        StagingBuild[Build & Test]
        StagingTerraform[Terraform Apply]
        StagingDeploy[Deploy to Staging]
        StagingTest[UAT Tests]
    end
    
    subgraph "Production"
        ProdBuild[Build & Test]
        ProdTerraform[Terraform Apply]
        ProdDeploy[Deploy to Production]
        ProdMonitor[Monitor]
    end
    
    Dev --> DevBuild
    DevBuild --> DevTerraform
    DevTerraform --> DevDeploy
    DevDeploy --> DevTest
    
    Staging --> StagingBuild
    StagingBuild --> StagingTerraform
    StagingTerraform --> StagingDeploy
    StagingDeploy --> StagingTest
    
    Prod --> ProdBuild
    ProdBuild --> ProdTerraform
    ProdTerraform --> ProdDeploy
    ProdDeploy --> ProdMonitor
    
    style Dev fill:#90EE90
    style Staging fill:#FFD700
    style Prod fill:#FF6B6B
```

## Operational Architecture

### Monitoring and Observability

```mermaid
graph TB
    subgraph "Data Sources"
        Lambda[Lambda Function]
        EventBridge[EventBridge]
        VPC[VPC Flow Logs]
    end
    
    subgraph "CloudWatch"
        Logs[CloudWatch Logs]
        Metrics[CloudWatch Metrics]
        Alarms[CloudWatch Alarms]
    end
    
    subgraph "Alerting"
        SNS[SNS Topic]
        Email[Email Notifications]
        Slack[Slack Notifications]
    end
    
    subgraph "Dashboards"
        Dashboard[CloudWatch Dashboard]
        CustomMetrics[Custom Metrics]
    end
    
    Lambda -->|Structured Logs| Logs
    Lambda -->|Metrics| Metrics
    EventBridge -->|Invocation Metrics| Metrics
    VPC -->|Flow Logs| Logs
    
    Metrics --> Alarms
    Alarms --> SNS
    SNS --> Email
    SNS --> Slack
    
    Metrics --> Dashboard
    CustomMetrics --> Dashboard
    Logs --> Dashboard
    
    style Lambda fill:#4A90E2
    style Logs fill:#FFA500
    style Metrics fill:#50C878
    style Alarms fill:#FF6B6B
```

### Error Handling Flow

```mermaid
flowchart TD
    Start([Lambda Invocation]) --> Execute[Execute Replication]
    Execute --> Success{Success?}
    
    Success -->|Yes| LogSuccess[Log Success]
    LogSuccess --> ReturnSuccess[Return Success Response]
    
    Success -->|No| CatchError[Catch Exception]
    CatchError --> LogError[Log Error Details]
    LogError --> CheckRetry{Retryable?}
    
    CheckRetry -->|Yes| Retry[Retry with Backoff]
    Retry --> Execute
    
    CheckRetry -->|No| SendDLQ[Send to DLQ]
    SendDLQ --> TriggerAlarm[Trigger CloudWatch Alarm]
    TriggerAlarm --> Notify[Notify via SNS]
    Notify --> ReturnError[Return Error Response]
    
    style Success fill:#FFD700
    style CheckRetry fill:#FFD700
    style SendDLQ fill:#FF6B6B
    style ReturnSuccess fill:#50C878
```

## Technology Stack

### Application Layer

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Runtime | Python | 3.11 | Lambda runtime |
| Database Client | psycopg2-binary | 2.9.9 | Aurora PostgreSQL connection |
| Snowflake Client | snowflake-connector-python | 3.7.0 | Snowflake connection |
| Vault Client | hvac | 2.1.0 | Hashicorp Vault integration |
| AWS SDK | boto3 | 1.34.0 | AWS service integration |

### Infrastructure Layer

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Compute | AWS Lambda | Serverless execution |
| Scheduling | AWS EventBridge | Scheduled triggers |
| Networking | AWS VPC | Network isolation |
| PrivateLink | AWS VPC Endpoint | Snowflake connectivity |
| Secrets | Hashicorp Vault | Secrets management |
| Monitoring | AWS CloudWatch | Logging and metrics |
| IaC | Terraform | Infrastructure management |
| CI/CD | GitHub Actions + Harness | Build and deployment |

### Data Layer

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Source Database | AWS Aurora PostgreSQL v2 | Source data |
| Target Database | Snowflake | Target data warehouse |
| Connectivity | PrivateLink | Secure connection |

## Scalability Considerations

### Horizontal Scaling

- **Lambda**: Automatically scales based on invocations
- **EventBridge**: Handles multiple concurrent triggers
- **Aurora**: Read replicas for read scaling
- **Snowflake**: Auto-scaling warehouses

### Vertical Scaling

- **Lambda Memory**: Configurable (512MB - 10GB)
- **Lambda Timeout**: Configurable (up to 15 minutes)
- **Batch Size**: Configurable batch processing
- **Snowflake Warehouse**: Configurable compute size

### Performance Optimization

1. **Batch Processing**: Configurable batch sizes
2. **Incremental Replication**: Only replicate changed data
3. **Connection Pooling**: Reuse connections where possible
4. **Parallel Processing**: Future enhancement for large tables

## Disaster Recovery

### Backup Strategy

- **Lambda Code**: Versioned in GitHub and Artifactory
- **Infrastructure**: Terraform state in Terraform Cloud
- **Secrets**: Backed up in Hashicorp Vault
- **Data**: Aurora automated backups, Snowflake Time Travel

### Recovery Procedures

1. **Lambda Failure**: Automatic retry via EventBridge
2. **Infrastructure Failure**: Recreate via Terraform
3. **Data Corruption**: Restore from Aurora backup
4. **Secrets Loss**: Rotate via Vault

## Cost Optimization

### Cost Factors

1. **Lambda**: Pay per invocation and duration
2. **Data Transfer**: PrivateLink charges
3. **Snowflake**: Compute and storage costs
4. **CloudWatch**: Log storage and metrics

### Optimization Strategies

1. **Scheduled Execution**: Run only when needed
2. **Batch Processing**: Reduce Lambda invocations
3. **Incremental Mode**: Transfer only changed data
4. **Log Retention**: Configure appropriate retention periods
5. **Snowflake Warehouse**: Auto-suspend when idle

## Future Enhancements

### Planned Improvements

1. **Dead Letter Queue**: For failed invocations
2. **State Tracking**: DynamoDB for incremental replication
3. **Retry Logic**: Exponential backoff for transient failures
4. **COPY INTO**: Snowflake bulk loading optimization
5. **Data Validation**: Row count and checksum validation
6. **Health Checks**: Lambda health check endpoint
7. **X-Ray Tracing**: Distributed tracing support

### Potential Enhancements

1. **Change Data Capture**: Real-time replication
2. **Multi-Region**: Cross-region replication support
3. **Data Transformation**: Built-in transformation pipeline
4. **Monitoring Integration**: Datadog, New Relic support
5. **Parallel Processing**: Step Functions orchestration

## Architecture Decisions

### ADR-001: Serverless Architecture
**Decision**: Use AWS Lambda instead of EC2/ECS
**Rationale**: Cost-effective, auto-scaling, no infrastructure management
**Alternatives Considered**: ECS Fargate, EC2 instances

### ADR-002: EventBridge Scheduling
**Decision**: Use EventBridge for scheduling
**Rationale**: Native AWS service, reliable, cost-effective
**Alternatives Considered**: CloudWatch Events, Lambda scheduled events

### ADR-003: PrivateLink for Snowflake
**Decision**: Use VPC endpoint for Snowflake connectivity
**Rationale**: Secure, private, no public internet exposure
**Alternatives Considered**: Public endpoint with VPN, Direct Connect

### ADR-004: Hashicorp Vault for Secrets
**Decision**: Use Vault instead of AWS Secrets Manager
**Rationale**: Centralized secrets management, IAM auth support
**Alternatives Considered**: AWS Secrets Manager, Parameter Store

### ADR-005: Terraform Cloud for IaC
**Decision**: Use Terraform Cloud for state management
**Rationale**: Remote state, collaboration, policy enforcement
**Alternatives Considered**: S3 backend, local state

## Glossary

- **DLQ**: Dead Letter Queue - Queue for failed messages
- **ENI**: Elastic Network Interface - Network interface for Lambda in VPC
- **IaC**: Infrastructure as Code - Managing infrastructure through code
- **PrivateLink**: AWS service for private connectivity
- **VPC**: Virtual Private Cloud - Isolated network environment
- **VPCe**: VPC Endpoint - Interface for connecting to services privately

