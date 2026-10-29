# Feature Specification: Health Check Endpoint

**Feature Branch**: `001-health-check`

**Created**: 2026-03-04

**Status**: Implemented

**Input**: User description: "Expose a health endpoint for the load balancer"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Load balancer probes health (Priority: P1)

The load balancer calls the health endpoint every 5 seconds and removes the instance when it reports a failure.

**Why this priority**: Without it, unhealthy instances keep receiving traffic.

**Independent Test**: Can be tested by calling the endpoint with the database up and down, and confirming the reported status flips.

**Acceptance Scenarios**:

1. **Given** the database is reachable, **When** the health endpoint is called, **Then** it returns status ok
2. **Given** the database is unreachable, **When** the health endpoint is called, **Then** it returns status degraded

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST return service status as JSON
- **FR-002**: System MUST report database connectivity in the same payload

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The endpoint responds in under 50ms at p99
