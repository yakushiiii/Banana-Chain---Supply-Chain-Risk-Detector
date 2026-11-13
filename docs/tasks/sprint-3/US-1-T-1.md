---
id: US-85-T-1
story: US-85
sprint: 3
assignee: Justin Thai
estimate_hours: 3
---

# Connect scan submission form to API and display scan status progression

## Description
Serves User Story #85 (Full risk detection and security scoring for projects / Issue #55). This task connects the scan input forms in `frontend/src/App.tsx` to the backend scan initiation endpoint. It replaces simulated dummy text with live network submissions, captures and displays backend validation errors (specifically HTTP 422 repository validation errors from issue #17), and polls scan status (`queued`, `cloning`, `scanning`, `normalizing`, `completed`, `failed`) to render a live multi-step pipeline progress indicator.

Rendering the detailed component/vulnerability table (owned by `samuelrenteria2005` in issue #70) and the CycloneDX JSON download button (owned by `fromfacade` in issue #72) are out of scope.

## Specs
- In `frontend/src/App.tsx`:
  - Submitting a GitHub URL sends a `POST` request with `{ "repo_url": "..." }` (or `FormData`) to the scan initiation API.
  - Submitting project files sends a `POST` request with `FormData` containing the selected files.
  - While a request is in flight or a scan is active:
    - Input fields and submit buttons are disabled to prevent duplicate submissions.
    - The submit button displays a loading spinner and "Initiating scan...".
- Validation error handling:
  - If the API returns HTTP 422 or 400 (e.g. from `InvalidRepoUrl`), renders an alert banner containing the backend `detail` error message above the form without reloading the page.
  - Modifying the input field clears the active error message.
- Pipeline status progression:
  - On receipt of a valid `scan_id`, the UI renders a status progression banner reflecting the current `ScanStatus` values (`queued` -> `cloning` -> `scanning` -> `normalizing` -> `completed`).
  - Polls the scan status endpoint every 2 seconds until reaching a terminal state (`completed` or `failed`).
  - If the status becomes `failed`, displays an error alert with the failure reason and a "Scan Another Project" button to restore the form.
  - When the status reaches `completed`, displays a completion banner with the scanned target and component count, providing the mounting container for the results table.
- Automated tests in `frontend/src/App.test.tsx` using Vitest / React Testing Library mocking successful scans, validation errors, and status polling.

## Requirements
- Built using React, TypeScript, and Tailwind CSS already configured in `frontend/`.
- Must consume `ScanStatus` enum values consistent with `app/schemas/scan.py`.
- Live `/health` monitoring badges must remain operational and unobstructed.
- No new npm packages.

## Acceptance criteria
1. Submitting a repository URL triggers a `POST` request to initiate a scan.
2. An HTTP 422 error from the API displays the validation error message in an alert banner.
3. Form inputs and submit buttons are disabled while a scan is in progress.
4. The UI displays the active pipeline stage (`queued`, `cloning`, `scanning`, `completed`) returned from status polling.
5. If a scan fails, the UI displays an error banner and provides a button to reset the form.
6. When the scan status reaches `completed`, the completed summary card is displayed.