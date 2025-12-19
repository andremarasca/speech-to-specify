# Feature Specification: Telegram Voice Orchestrator (OATL)

**Feature Branch**: `002-telegram-voice-orchestrator`  
**Created**: 2025-12-18  
**Status**: Draft  
**Input**: User narrative describing remote voice-to-text orchestration via Telegram with local processing and data sovereignty

**Constitution**: This spec MUST be compatible with `.specify/memory/constitution.md` (OATL v2.0.0).

## Summary

Enable a single user to remotely command a local audio-to-text pipeline via Telegram. Voice messages sent through the messaging app are captured and stored locally in isolated sessions, transcribed locally, and optionally processed by downstream systems. All processing occurs on the user's local machine; Telegram serves only as a communication channel. Sessions are immutable after finalization, ensuring full auditability and reproducibility.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start New Session (Priority: P1)

As a user, I want to start a new voice capture session remotely by sending a text command via Telegram, so that I can begin dictating ideas from anywhere while knowing my data stays local.

**Why this priority**: This is the foundational interaction. Without session creation, no other functionality is possible. It establishes the core data sovereignty promise.

**Independent Test**: Can be fully tested by sending "/start" command and verifying a new session folder is created locally with correct timestamp-based naming and initial state file.

**Acceptance Scenarios**:

1. **Given** no active session exists, **When** user sends "/start" command, **Then** system creates a new session folder with unique timestamp ID and responds with confirmation message including session ID
2. **Given** an active session exists in "collecting" state, **When** user sends "/start" command, **Then** system finalizes the pending session automatically, creates the new session, and notifies user of both actions
3. **Given** system is running locally, **When** session is created, **Then** session state is persisted to a JSON file within the session folder

---

### User Story 2 - Collect Voice Messages (Priority: P1)

As a user, I want to send multiple voice messages to my Telegram bot during an active session, so that I can dictate ideas naturally without worrying about technical details.

**Why this priority**: This is the core data capture functionality. Voice collection is the primary input mechanism and must work reliably.

**Independent Test**: Can be tested by starting a session, sending 3 voice messages, and verifying all audio files are stored locally in the session folder with correct metadata.

**Acceptance Scenarios**:

1. **Given** an active session in "collecting" state, **When** user sends a voice message, **Then** audio file is downloaded to local session folder preserving original format
2. **Given** an active session, **When** multiple voice messages are received, **Then** each audio is stored with sequential ordering metadata and receipt timestamp
3. **Given** an active session, **When** audio download fails, **Then** error is logged to session metadata without affecting previously stored audios, and user is notified
4. **Given** no active session, **When** user sends a voice message, **Then** system rejects with clear message instructing user to start a session first

---

### User Story 3 - Finalize Session and Transcribe (Priority: P1)

As a user, I want to finalize my dictation session and trigger automatic transcription, so that all my voice recordings are converted to text locally.

**Why this priority**: Transcription transforms raw audio into usable text. This is the critical processing step that enables all downstream value.

**Independent Test**: Can be tested by finalizing a session with 2 audio files and verifying transcription files are generated locally for each audio.

**Acceptance Scenarios**:

1. **Given** an active session with collected audios, **When** user sends "/done" command, **Then** session state changes to "finalizing", transcription begins for all audios
2. **Given** transcription completes successfully, **When** all audios are processed, **Then** session state changes to "transcribed" and text files are stored in session folder
3. **Given** session is finalized, **When** user attempts to add more voice messages, **Then** system rejects with message explaining session is closed
4. **Given** transcription is in progress, **When** user sends status query, **Then** system reports current progress (e.g., "Transcribing 2 of 5 audios")

---

### User Story 4 - Retrieve Transcriptions (Priority: P2)

As a user, I want to request my transcriptions via Telegram, so that I can review them immediately from anywhere.

**Why this priority**: Important for user feedback loop, but not blocking for core pipeline. User can also access files directly on local machine.

**Independent Test**: Can be tested by requesting transcriptions from a "transcribed" session and verifying text content is delivered via Telegram.

**Acceptance Scenarios**:

1. **Given** a session in "transcribed" state, **When** user sends "/transcripts" command, **Then** system sends transcription text(s) back via Telegram
2. **Given** a session not yet transcribed, **When** user requests transcripts, **Then** system responds with current session state and what's needed
3. **Given** transcriptions exceed Telegram message limits, **When** user requests transcripts, **Then** system splits into multiple messages or sends as file attachment

---

### User Story 5 - Trigger Downstream Processing (Priority: P2)

As a user, I want to send my transcribed session to my existing text processing pipeline, so that complex documents can be generated from my dictation.

**Why this priority**: Enables integration with user's specialized systems. Depends on transcription being complete first.

**Independent Test**: Can be tested by commanding processing on a transcribed session and verifying the session path is correctly passed to the external subsystem.

**Acceptance Scenarios**:

1. **Given** a session in "transcribed" state, **When** user sends "/process" command, **Then** system passes session folder path to configured downstream processor
2. **Given** processing completes successfully, **When** results are available, **Then** session state updates to "processed" and user is notified
3. **Given** downstream processor fails, **When** error occurs, **Then** session remains in "transcribed" state, error is logged, and user is notified of the failure
4. **Given** session is not yet transcribed, **When** user commands processing, **Then** system rejects with clear prerequisite message

---

### User Story 6 - Query Session Status (Priority: P3)

As a user, I want to check the current status of my session at any time, so that I understand where I am in the workflow.

**Why this priority**: Quality of life improvement. Core functionality works without it, but enhances user experience.

**Independent Test**: Can be tested by querying status at each session state and verifying accurate state information is returned.

**Acceptance Scenarios**:

1. **Given** any session state, **When** user sends "/status" command, **Then** system responds with current state, audio count, and available actions
2. **Given** no active session, **When** user queries status, **Then** system lists recent sessions with their states

---

### User Story 7 - List Session Results (Priority: P3)

As a user, I want to list all files generated in a session, so that I can selectively retrieve specific results.

**Why this priority**: Convenience feature for navigating complex outputs. Core delivery works via direct access.

**Independent Test**: Can be tested by listing files from a processed session and verifying accurate file listing is returned.

**Acceptance Scenarios**:

1. **Given** a session with generated files, **When** user sends "/list" command, **Then** system returns list of all files in session folder with types
2. **Given** user specifies a file from the list, **When** user sends "/get <filename>" command, **Then** system sends that file via Telegram

---

### Edge Cases

- **Telegram connection lost during audio collection**: System continues locally; audios received before disconnect are preserved; reconnection syncs pending commands
- **Local disk full during audio download**: Download fails gracefully; error logged to session metadata; user notified; session remains valid for existing files
- **Transcription service unavailable**: Session stays in "finalizing" state; retry mechanism with user notification; no data loss
- **Session folder manually deleted**: System detects missing folder; reports error to user; prevents operations on orphaned session
- **Concurrent commands from user**: Commands are queued and processed sequentially; deterministic ordering by receipt timestamp
- **Very long audio file**: System handles files up to reasonable limit (e.g., 20 minutes per audio); larger files rejected with clear message
- **Malformed audio file**: Transcription fails for that file only; logged; other files processed normally

## Requirements *(mandatory)*

### Functional Requirements

#### Session Management

- **FR-001**: System MUST create a new session folder with unique timestamp-based identifier when user sends start command
- **FR-002**: System MUST persist session state to a JSON file within the session folder after every state change
- **FR-003**: System MUST enforce single active session policy - only one session can be in "collecting" state at a time
- **FR-004**: System MUST auto-finalize pending session when new start command is received (deterministic conflict resolution)
- **FR-005**: Sessions MUST become immutable after finalization - no new audio can be added

#### Audio Collection

- **FR-006**: System MUST download voice messages from Telegram and store in session folder preserving original format
- **FR-007**: System MUST record metadata for each audio: sequence number, receipt timestamp, original filename, file size
- **FR-008**: System MUST handle partial collection failures without corrupting existing session data
- **FR-009**: System MUST reject voice messages when no active session exists with clear user notification

#### Transcription

- **FR-010**: System MUST transcribe all audio files locally using a speech-to-text mechanism
- **FR-011**: System MUST generate one text file per audio file, stored in session folder
- **FR-012**: System MUST update session state progressively during transcription (enabling progress queries)
- **FR-013**: System MUST transition session to "transcribed" state only when all audios are successfully processed

#### Downstream Integration

- **FR-014**: System MUST pass session folder path (and only the path) to configured downstream processor
- **FR-015**: System MUST isolate downstream failures - session remains in "transcribed" state if processor fails
- **FR-016**: System MUST log downstream processor errors with sufficient detail for diagnosis

#### Communication Channel

- **FR-017**: System MUST operate as a Telegram bot responding to text commands and receiving voice messages
- **FR-018**: System MUST maintain operation during Telegram disconnection - local state is preserved
- **FR-019**: System MUST send clear status notifications to user at each state transition
- **FR-020**: System MUST support sending text and files back to user via Telegram

#### State & Auditability

- **FR-021**: All session state MUST be stored as human-readable JSON files
- **FR-022**: System MUST log all significant events with timestamps (command received, audio stored, transcription started/completed, errors)
- **FR-023**: Session folder structure MUST be self-contained and reproducible

### Key Entities

- **Session**: Represents a single voice capture workflow. Has unique timestamp ID, current state (collecting, finalizing, transcribed, processed, error), creation timestamp, list of audio entries, list of transcription files, error log if any
- **AudioEntry**: Represents one captured voice message. Has sequence number, receipt timestamp, local filename, file size, transcription status, associated transcript filename
- **Command**: User input received via Telegram. Has type (start, done, status, transcripts, process, list, get), timestamp, raw content
- **SessionState**: Enumeration of possible session states with allowed transitions: collecting → finalizing → transcribed → processed (with error possible from any state)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: User can complete full workflow (start → collect 3 audios → finalize → receive transcripts) in under 5 minutes of active time
- **SC-002**: 95% of sessions complete without requiring user intervention for technical errors
- **SC-003**: User understands current system state with single status query (no ambiguous responses)
- **SC-004**: Session from 6 months ago can be fully reproduced using only its folder contents
- **SC-005**: Time from "/done" command to first transcript available is under 2 minutes for typical dictation (5 audio files, 1-2 minutes each)
- **SC-006**: System recovers from Telegram disconnection within 30 seconds of connectivity restoration
- **SC-007**: Zero data loss - no audio file ever lost due to system error after successful download confirmation

## Assumptions

- User has a single Telegram account configured as the authorized user
- Local machine runs continuously and has sufficient storage for audio files
- Speech-to-text mechanism is available locally (specific technology TBD in planning phase)
- Downstream processor exists and accepts session folder path as input
- User accepts that Telegram is used only as a communication channel, not for processing or storage
