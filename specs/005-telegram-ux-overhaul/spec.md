# Feature Specification: Telegram UX Overhaul

**Feature Branch**: `005-telegram-ux-overhaul`  
**Created**: 2025-12-19  
**Status**: Draft  
**Input**: User description: "Interface evolution to reduce cognitive load - replace command-based interaction with recognition-based patterns using inline keyboards, auto-session creation, real-time progress feedback, humanized error messages, and accessibility-first design."

**Constitution**: This spec MUST be compatible with `.specify/memory/constitution.md`.

## Overview

The current Telegram bot interface requires users to memorize and type multiple commands, conflicting with the constitutional pillar of **User Autonomy & Low Cognitive Load**. This feature transforms the interaction model from memorization-based to recognition-based, enabling users to capture voice narratives with minimal conscious effort while maintaining full control.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Zero-Command Voice Capture (Priority: P1)

A user wants to capture meeting notes via voice without learning any commands. They open the Telegram bot chat and simply send a voice message. The system automatically creates a session, confirms receipt with a friendly message, and presents inline buttons for next actions. The user continues sending voice messages, receiving brief confirmations. When finished, they tap "Finalize" and receive their transcription—all without typing a single command.

**Why this priority**: This is the core value proposition. It directly addresses the constitutional conflict by eliminating command memorization entirely. A working zero-command flow delivers immediate value and proves the recognition-over-recall principle.

**Independent Test**: Send a voice message to the bot with no active session; verify session auto-creation, confirmation message with inline buttons, and ability to complete full transcription flow using only taps.

**Acceptance Scenarios**:

1. **Given** no active session exists, **When** user sends a voice message, **Then** system creates a session automatically and responds with confirmation message containing inline action buttons
2. **Given** an active session exists, **When** user sends additional voice messages, **Then** system confirms receipt with brief "Audio N received" and updates the audio counter
3. **Given** user has sent one or more voice messages, **When** user taps "Finalize" button, **Then** system processes all audio and delivers transcription results
4. **Given** processing completes, **When** transcription is ready, **Then** user receives notification with preview and action buttons (view full, search, start pipeline)

---

### User Story 2 - Real-Time Progress Feedback (Priority: P2)

During transcription processing, the user sees a visual progress indicator that updates in real-time. Instead of waiting in uncertainty, they see "Processing 3 audios... ▓▓▓▓░░░░ 60%" which gives them confidence the system is working and an estimate of remaining time.

**Why this priority**: Progress feedback transforms waiting from anxiety to assurance. It's essential for user confidence but depends on the core flow (US1) being functional first.

**Independent Test**: Initiate transcription of multiple audio files; verify progress message appears immediately and updates at least 3 times before completion.

**Acceptance Scenarios**:

1. **Given** user taps "Finalize" with multiple audios, **When** processing begins, **Then** system displays progress indicator within 2 seconds
2. **Given** processing is in progress, **When** each significant milestone is reached, **Then** progress indicator updates to reflect current state
3. **Given** processing completes, **When** final result is ready, **Then** progress indicator shows 100% before transitioning to results view

---

### User Story 3 - Humanized Error Recovery (Priority: P2)

When an error occurs (disk full, timeout, network issue), the user receives a clear, non-technical message explaining what happened and presenting actionable recovery options as inline buttons. No stack traces or error codes are shown as primary content.

**Why this priority**: Error handling is critical for user trust and autonomy. Users must be able to recover from errors without external help. Grouped with P2 as it enhances the core flow reliability.

**Independent Test**: Simulate a storage error during audio save; verify error message is user-friendly, contains recovery suggestions, and offers retry button.

**Acceptance Scenarios**:

1. **Given** a recoverable error occurs, **When** error is detected, **Then** system displays human-readable message with recovery suggestions and action buttons
2. **Given** an error message is displayed, **When** user selects a suggested action, **Then** system attempts recovery and provides feedback on result
3. **Given** any error occurs, **When** error message is shown, **Then** message contains no technical jargon, stack traces, or implementation details visible to user

---

### User Story 4 - Session Conflict Protection (Priority: P3)

When a user attempts to start a new session while one is already active, the system prevents accidental data loss by presenting options: finalize current session, cancel action, or return to active session.

**Why this priority**: Protects user data and prevents frustration from accidental overwrites. Lower priority because it's a protective measure rather than core functionality.

**Independent Test**: With an active session containing audio, attempt to trigger a new session; verify confirmation dialog appears with clear options.

**Acceptance Scenarios**:

1. **Given** an active session with recorded audio exists, **When** user action would create a new session, **Then** system presents confirmation with current session status and options
2. **Given** confirmation dialog is shown, **When** user chooses "Finalize and start new", **Then** current session is properly finalized before new one begins
3. **Given** confirmation dialog is shown, **When** user chooses "Return to current", **Then** user is returned to active session with no data loss

---

### User Story 5 - Contextual Help Discovery (Priority: P3)

Instead of requiring users to remember `/help`, the system provides contextual guidance at each interaction point. Help text appears naturally within the flow, and a subtle help button is always available in inline keyboards.

**Why this priority**: Reduces reliance on memorized commands and supports discoverability. Lower priority as core flows should be self-explanatory first.

**Independent Test**: Navigate through session flow; verify help hints appear contextually and help button is present in all inline keyboards.

**Acceptance Scenarios**:

1. **Given** user is at any interaction point, **When** inline keyboard is displayed, **Then** a help option is available without requiring typed commands
2. **Given** user selects contextual help, **When** help content is displayed, **Then** it is relevant to current state and includes actionable next steps
3. **Given** help is accessed from any state, **When** user dismisses help, **Then** they return to their previous context without losing progress

---

### User Story 6 - Long Operation Timeout Handling (Priority: P3)

For extended transcriptions, if processing exceeds expected duration, the user receives a notification asking whether to continue waiting or cancel. The user maintains control over long-running operations.

**Why this priority**: Ensures user control during edge cases. Lower priority as it only applies to unusually long operations.

**Independent Test**: Initiate transcription that exceeds timeout threshold; verify timeout notification appears with continue/cancel options.

**Acceptance Scenarios**:

1. **Given** operation exceeds configured timeout threshold, **When** timeout is detected, **Then** user receives notification with status and options to continue or cancel
2. **Given** user chooses to continue waiting, **When** operation eventually completes, **Then** normal completion flow proceeds
3. **Given** user chooses to cancel, **When** cancellation is confirmed, **Then** partial progress is preserved where possible and session state is recoverable

---

### Edge Cases

- **Empty voice message**: If user sends a voice message with no audible content, system acknowledges receipt but warns about potential transcription quality via ERR_TRANSCRIPTION_002
- **Session auto-recovery**: If bot crashes mid-session, on restart the system detects orphaned sessions and offers to resume from last checkpoint or finalize
- **Message length limits**: Transcriptions exceeding Telegram's 4096 character limit are automatically paginated with navigation buttons
- **Concurrent sessions across devices**: *(Deferred to post-MVP)* System assumes single-device usage; multi-device conflict detection is out of scope for initial release
- **Rate limiting**: If user sends voice messages faster than system can process, queue with feedback showing position and ERR_TELEGRAM_002 message

## Requirements *(mandatory)*

### Functional Requirements

#### Session Management
- **FR-001**: System MUST automatically create a session when user sends first voice message with no active session
- **FR-002**: System MUST generate a session name automatically based on timestamp (MVP: `session_YYYY-MM-DD_HH-MM-SS` format; content-based naming deferred to post-MVP)
- **FR-003**: System MUST persist session state at each significant checkpoint (audio receipt, processing start) to enable crash recovery
- **FR-004**: System MUST present confirmation dialog when user action would overwrite an active session with unsaved audio

#### User Interface
- **FR-005**: System MUST present inline keyboard buttons for all primary actions (finalize, help, cancel)
- **FR-006**: System MUST display progress indicator during transcription processing that updates at least every 5 seconds
- **FR-007**: System MUST paginate transcription results that exceed message length limits with navigation buttons
- **FR-008**: System MUST include contextual help option in all inline keyboard interactions

#### Feedback & Communication
- **FR-009**: System MUST confirm each audio receipt with brief acknowledgment including audio sequence number
- **FR-010**: System MUST send completion notification via standard Telegram message when transcription finishes
- **FR-011**: System MUST display error messages in plain language without technical details, stack traces, or implementation jargon
- **FR-012**: System MUST include actionable recovery suggestions with all error messages

#### Accessibility
- **FR-013**: All interface elements MUST include clear text descriptions suitable for screen readers
- **FR-014**: All buttons MUST have descriptive labels that convey their action without requiring visual context
- **FR-015**: Progress updates MUST include text description in addition to any visual indicators

#### Configuration
- **FR-016**: Message length limits, timeout thresholds, and progress update intervals MUST be externalized to configuration files
- **FR-017**: All user-facing message templates MUST be externalized to `src/lib/messages.py` for future localization support (MVP: Portuguese pt-BR only; language selection deferred to post-MVP)

### Key Entities

*See [data-model.md](data-model.md) for full entity definitions.*

- **Session**: Represents a voice capture context; extended with `ui_preferences` and `checkpoint_data` fields
- **UIPreferences**: User interface preferences (simplified_ui toggle) stored per-session
- **UIState**: Transient state for managing Telegram message interactions (status_message_id, keyboard type)
- **ProgressState**: Current processing status; includes completion percentage, current step description, and estimated time remaining
- **UserFacingError**: Structured error for humanized presentation with recovery actions; defined in error catalog
- **ConfirmationContext**: Context for confirmation dialogs (session conflicts, destructive actions)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users complete first transcription in under 2 minutes (from first message to receiving transcription)
- **SC-002**: Users require 3 or fewer conscious interactions (taps/commands) to complete a basic session
- **SC-003**: Session abandonment rate (sessions created but never finalized) remains below 10%
- **SC-004**: 90% or more of users who encounter an error take one of the suggested recovery actions
- **SC-005**: Generic help command usage drops below 20% of sessions, indicating effective contextual guidance
- **SC-006**: 95% of users successfully complete a session on their first attempt without external assistance

## Assumptions

- Users have access to Telegram and can send voice messages
- The existing transcription pipeline remains stable and available
- Telegram's inline keyboard API supports the proposed interaction patterns
- Session state can be persisted locally in JSON format as per existing architecture
- Network connectivity is available for Telegram message delivery (actual transcription processing is local)
