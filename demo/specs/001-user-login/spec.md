# Feature Specification: User Login

**Feature Branch**: `001-user-login`

**Created**: 2025-06-02

**Status**: Implemented

**Input**: User description: "Users can sign in with email and password"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Email and password sign-in (Priority: P1)

A registered user signs in with their email address and password to reach the dashboard.

**Why this priority**: Without sign-in nothing else is reachable.

**Independent Test**: Can be fully tested by submitting valid credentials on the login form and confirming the dashboard loads.

**Acceptance Scenarios**:

1. **Given** a registered account, **When** the user submits a valid email and password, **Then** a session is created and the dashboard loads
2. **Given** a registered account, **When** the user submits a valid email with a wrong password, **Then** the form shows an authentication error

---

### Edge Cases

- What happens when the email contains uppercase letters?
- How does system handle a password with trailing whitespace?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow users to sign in with email and password
- **FR-002**: System MUST validate email address format before submitting credentials
- **FR-003**: System MUST lock the account for 15 minutes after 5 consecutive failed attempts

### Key Entities

- **Account**: A registered user identity with email, password hash, failed attempt counter, lock timestamp

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A returning user completes sign-in in under 15 seconds on first attempt
- **SC-002**: Fewer than 2% of sign-in attempts fail due to validation errors
