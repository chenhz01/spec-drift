# Feature Specification: Two-Factor Authentication

**Feature Branch**: `009-two-factor`

**Created**: 2025-11-14

**Status**: Draft

**Input**: User description: "Add an OTP step after password sign-in"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - OTP as a second step (Priority: P1)

After submitting email and password, the user receives a one-time code and must enter it before the session is created.

**Why this priority**: Compliance requirement; blocks enterprise rollout.

**Independent Test**: Can be tested by enabling 2FA on a test account and confirming the session is only created after a valid OTP.

**Acceptance Scenarios**:

1. **Given** 2FA is enabled, **When** the user submits a valid email and password, **Then** an OTP is sent and the session is not yet created
2. **Given** an OTP was requested, **When** the user submits a valid OTP, **Then** the session is created

---

### Edge Cases

- What happens when the same OTP is submitted twice?
- How does system handle an OTP requested from a different device?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST require a one-time code after the user submits email and password, before creating a session
- **FR-002**: System MUST validate email address format and password credentials before sending a one-time code
- **FR-003**: System MUST expire the one-time code after [NEEDS CLARIFICATION: expiry window not specified - 5 or 10 minutes?]
- **FR-004**: System MUST reject a one-time code that has already been used

### Key Entities

- **One-time code**: A short numeric code bound to an account and a request timestamp, single use

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users complete the second step in under 30 seconds
- **SC-002**: Fewer than 1% of valid codes are rejected due to timing
