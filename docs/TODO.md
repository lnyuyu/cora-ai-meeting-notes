# Known issues and todos

Diagnosed, not yet fixed. Each entry says what was observed, the cause found in the code or logs, and the fix we expect. Dated so the evidence can be re-checked.

## 0.4.4 pre-release feedback (2026-11-13): fix in 0.4.5

Collected from testers on the 0.4.4 pre-release. More to come from today's users; add them here.

### "Identify me" shows on every new Recording

**Observed.** Every Recording in the list carries an "Identify me" pill; the tester did not know what it meant (feedback event, Install `37147905`, 0.4.4 team build).

**Cause.** `recording_stage.stage()` returns `needs_speaker_confirmation` whenever `identity.speaker_id` is missing. Only the legacy paths in `diarization.py` write `identity`: manual `confirm_speaker`, and the old Gemini diarization voice-match auto-pilot (which also needs a Person with `is_self`). The current pipeline already knows who you are from capture: `pipeline/speakers.py` labels the mic track (track 0) "You" and the system track as the others. It never writes `identity`, so every Recording it processes fails the check. The stage only gated Coaching, which moved to v1.1.

**Fix.** (1) The pipeline writes `identity` from the mic track (`confirmation_source: "mic_track"`) so export, MCP and a later Coaching agree on "You". (2) `stage()` no longer returns `needs_speaker_confirmation` for dual-track Recordings; keep it only for single-track imports, labelled "Which speaker is you?" and opening the speaker picker. (3) One-time backfill of `identity` for existing dual-track Recordings. Test: a dual-track Recording reaches "Ready" with no confirmation.

### Slack desktop huddle recorded with no participant names, silently

**Observed.** A 25-minute Slack desktop huddle (started from the call prompt) ended with `participants_captured {count: 0, method: accessibility}`; notes had no names.

**Cause.** Accessibility is not granted to the 0.4.4 app on that Mac: `detect_fallback {reason: ax_untrusted}` at launch. Slack desktop names come only through Accessibility. A new build can lose the earlier grant (same root as the 2026-11-11 `AXError -25211` entry below).

**Fix.** User side: System Settings > Privacy & Security > Accessibility, remove and re-add Cora. Product: when a Recording ends with zero participants and Accessibility is untrusted, say so on the Recording ("Cora couldn't see who was in this call: grant Accessibility") with a button to the pane, instead of failing silently. Also check after each update that the designated requirement still matches so grants survive.

### General feedback can't be sent without a thumbs up/down

**Observed.** Settings > Beta: the tester could not send a written message without first picking a rating.

**Cause.** By design in `src/ui/web/js/feedback.js` `renderGeneralFeedback()`: Send is disabled while `!generalFeedback.rating`; the click handler returns early on the same check.

**Fix.** Make the rating optional for general feedback (send `rating: null`; receiver and dashboard accept it). The per-Recording thumbs-down that asks for a reason stays as is.

### Processing mode: prefer Local, recommend by this Mac, warn on low RAM

**Observed.** Two of six team Macs have 8 GB of RAM (M1 and M2; `app_started.ram_gb`), one 8 GB Install opened Cora once and never recorded, and a teammate reported trouble (details pending). Nothing in the app tells an 8 GB user that their Mac is the problem or what to pick instead.

**Cause.** `processing.hardware()` only ever recommends a *local* mode (`local_thorough` at 24 GB+, else `local_light`); it never recommends Cloud and never warns. The UI prints the recommendation as one muted line in Settings (`processing.js`) and in onboarding step 5, where it is easy to miss (see the 2026-11-11 entry on step 5 below). Team builds hard-default to Cloud regardless of the Mac, so the recommendation is ignored anyway.

**Intent.** Local is the preferred default (privacy, no key, no cost). Cora recommends it whenever this Mac can run it well, and recommends Cloud only when it cannot.

**Fix.**
1. *One rule, one place.* `processing.recommend(hardware)` returns, for each mode, `recommended | ok | warn | blocked` plus a one-line reason. Starting point (to confirm against the local-vs-Gemini comparison and real processing times):
   - Apple Silicon, 24 GB+: **Local · Thorough** recommended; Light ok; Cloud ok.
   - 16 to 23 GB: **Local · Light** recommended; Thorough warn ("may be slow"); Cloud ok.
   - Under 16 GB (8 GB Macs): **Cloud** recommended; Light warn ("transcription competes with your call for memory; expect slow notes"); Thorough blocked.
   Onboarding, Settings, telemetry and the dashboard all read this; nothing else decides.
2. *Onboarding step 5 as three cards* (Local · Light, Local · Thorough, Cloud), the recommended one preselected with a "Best for this Mac" badge, each card saying in plain words what stays on the Mac, speed, and memory need. Blocked cards are greyed with the reason. Model lists appear only after choosing a local card (folds in the step 5 entry below). Team builds use the recommendation too instead of forcing Cloud; the Gemini key step appears only if Cloud is chosen.
3. *Low-RAM warning that is hard to miss.* Under 16 GB: a yellow banner in onboarding and in Settings > Processing: "This Mac has 8 GB of memory. Cloud is recommended; Local may be slow or fail on long calls." Choosing a `warn` mode asks once to confirm.
4. *Second chance at runtime.* If a local run on a `warn` Mac fails or takes longer than the call itself, offer Cloud once on that Recording ("Process this one in the cloud?"), never automatically.
5. *Telemetry and dashboard.* `app_started` adds `recommended_mode` (from the same rule). Dashboard Installs table: "Low RAM" badge under 16 GB and a flag when the chosen mode differs from the recommendation, so we know whom to help first.
6. *Docs.* TEAM_SETUP "Before you start": 16 GB recommended; on 8 GB use Cloud.

Tests: the rule's table (8/16/18/24/64 GB, arm64 vs Intel); onboarding preselects the recommended card; a team build with 8 GB lands on Cloud and with 64 GB on Local · Thorough.

### Cloud processing freezes and crashes an 8 GB Mac at ~40%

**Observed.** A teammate on an M2 Pro with 8 GB RAM / 256 GB disk, Processing mode Cloud (Gemini, not local): processing reaches about 40%, the whole Mac starts lagging, then Cora and the browser both crash. Repeatedly, on 0.4.3. His Install does not appear in the receiver's events (no M2 Pro 8 GB `app_started`), so either usage sharing is off or the crash happens before upload; we have no logs yet.

**Cause (measured 2026-11-13, 0.4.4 bundled Python, one 10-minute dual-track Recording, sandbox data dir).** Peak memory of the pipeline process:

| Mode | Peak | Where | Why |
|---|---|---|---|
| Cloud | ~0.2 GB | transcribing | expected: ffmpeg streams audio, FLAC clips go to Gemini |
| Cloud, with fallback | **1.9 GB** | transcribing | Gemini's output for one stretch failed validation at every split level, so `windowed` handed it to `transcriber.local_fallback`, which loads local MLX Whisper ("transcribing it on this Mac") |
| Local · Light | **4.5 GB** | romanizing / generating_notes | Whisper (~1.9 GB), then Qwen3-4B for romanization and notes |

Speech detection and clip extraction are cheap (ffmpeg streams), contrary to the first guess. On an 8 GB Mac running a browser and a call, either the Cloud fallback or any Local mode pushes the Mac into swap; the freeze at "~40%" matches the transcribe/romanize boundary. The fallback only loads when a local Whisper model is downloaded, which onboarding step 5 invites.

The rejections themselves are suspect: they were for turns ending 2 to 40 s past the window (`turn ends at 304.4s outside a 302s window`), coverage under 60%, and a runaway-output check, i.e. `asr_validate` is strict enough that one Gemini timing slip escalates to splits, 3x retries per level, and finally the local model.

**Fix.** (1) Under 16 GB, never load the local fallback in Cloud mode: mark the stretch as a gap and offer "retry in the cloud" on the Recording instead. (2) Loosen `asr_validate`: clamp turns that overshoot the window end by a few seconds instead of rejecting, and count how often each rule fires (telemetry) before tuning further. (3) Local modes blocked or warned on under 16 GB per the "recommend by this Mac" entry above. (4) Never process while a call is live on under 16 GB; queue until it ends. (5) Still get his logs (Settings > Send logs) to confirm which of the two paths his Mac took.

### Seen alongside (not bugs, worth knowing)

- The tester's Mac processes locally (`local_light`, whisper-small) rather than the team's Cloud default, so transcript and name quality from it is not comparable with Cloud users.

## Participants not updated when switching huddles mid-recording (2026-11-11)

**Observed.** A recording began on a DM huddle (roster: one name, correct), the user left it and joined a second huddle with two more people while still recording; the roster stayed at one name.

**Cause.** Both huddles were collapsed to Slack's bottom mini-bar in Brave, where the page holds no participant tiles. The only name source there is the mini-bar title: "Huddle with <Name>" names the DM party, but the second huddle's title was just "Huddle", which names nobody (log `speaker-watch-meeting_2026-11-11T06-00-43-016Z.log`: two MEETING_TITLE lines, no SPEAKER_ACTIVE, no roster writes). The Accessibility fallback could not help: every scan logged `AXError -25211`, meaning the installed app is still not trusted under System Settings > Privacy & Security > Accessibility.

**Fix.** Two parts. (1) Product: when a Slack huddle is detected collapsed, nudge once in the floater: "Expand the huddle window so Cora can see who is in it", since Slack exposes names only in the expanded window. (2) Watcher: when the huddle title changes (a new huddle), re-run the roster snapshot immediately rather than waiting for the next scan, and keep both huddles' names in the roster. Independently, grant Accessibility to the installed app so the native fallback works for Zoom and the Slack desktop app.

## Capture helper death is undiagnosable remotely (2026-11-11)

**Observed.** On a teammate's first-day install (0.4.0, M3 Pro, one macOS major behind the build machine) every recording attempt ended within a second with "Recording stopped unexpectedly (capture helper exited with code null)", then "No audio was found". Eight `dual-capture` crash reports in four minutes, including from the `--list-devices` call Settings makes.

**Cause (found, fixed in 0.4.1).** Running the helper by hand on his Mac printed it: dyld "Symbol not found" in CoreMedia, "built for macOS 27.0 which is newer than running OS". The Makefile compiled the Swift helpers with no `-target`, so they were linked against the build Mac's macOS. Fixed by `-target arm64-apple-macos14.0` and a check in `scripts/build-app.sh` that each helper's `minos` equals `LSMinimumSystemVersion`.

**Still open: the app told us nothing.** Code null means a signal death without an `Error:`/`Failed:` line. `capture-helper.js` pipes only speaker-watch's stderr into the per-recording log, the helper's own stderr (where dyld printed the whole answer) is dropped, and `onHelperExit` puts the exit code but not the signal into the warning and the `error {scope: capture}` event. **Fix.** (1) Write the capture helper's stderr into the same per-recording log and the first stderr line into the warning, (2) include the signal name in the event (`helper_killed_SIGABRT`), (3) emit a `permissions` payload at recording start, (4) a `--preflight` mode that opens the mic and ScreenCaptureKit for one second so a dead helper is reported before a Recording starts. See `docs/DIAGNOSTICS.md`.

## Onboarding step 5 cannot be scrolled to its top (2026-11-11)

**Observed.** On a 14-inch screen the "Models & privacy" step is taller than the window; the user could scroll down but never back to the top of the card (seen live on a teammate's screen share).

**Cause.** `.onboarding-overlay` is `display:flex; align-items:center; overflow-y:auto`. A flex item centered in a container shorter than itself overflows equally above and below, and the part above the container's origin is unreachable by scrolling. Classic centered-overlay bug.

**Fix.** Keep the overlay scrollable but center safely: `align-items:flex-start` on the overlay and `margin:auto` on `.onboarding-card` (or `align-items: safe center`). One CSS line.

## Onboarding step 5 presents local models as a required choice (2026-11-11)

**Observed.** The last onboarding step shows the full processing-controls block (mode, template, model and engine overrides, a "Save processing defaults" button) plus two radio lists of Whisper and Liquid models with sizes. A new teammate on the cloud default read it as "pick and download a model to finish".

**Cause.** `loadOnboardingModels` always renders `#onboardingProcessing`, `#onboardingWhisperOptions` and `#onboardingLiquidOptions`, regardless of the processing mode, and the embedded controls carry their own Save button although Finish setup saves everything. The team build defaults to cloud, so the local lists are irrelevant on first run.

**Fix.** Render the step as: processing mode + notes template + the keep-audio toggle. Show the Whisper/Liquid lists only when mode is a local one (toggle on the mode select), and hide the embedded "Save processing defaults" button inside onboarding (`loadProcessingControls` gets an `embedded` flag). Rename the step "Processing & privacy". Keep the "models download on first use" line.

## Teams desktop still counts as a Call from the bare process (2026-11-11)

**Observed.** `MEETING_APP_PROCESSES` treats a running `Microsoft Teams` / `Teams` process as a Call, so the 20s backstop poll can prompt whenever Teams is merely open. Zoom and Slack desktop are being moved to window- and control-based liveness in the follow-up to #20 (`docs/planning/call-detection.draft.md`); Teams was left out on purpose.

**Fix.** Same rule as the others: Teams desktop (meeting window via the `speaker-watch` probe) and `teams.microsoft.com` tabs (page snapshot) count only when live. Until then Teams is the one exception to the **Call** definition in `GLOSSARY.md`.

## Arc is not enumerated by the meeting detector (2026-11-11)

**Observed.** The detector's AppleScript lists tabs for Chrome, Edge, Brave and Safari only. A Meet, Slack huddle or Zoom web call in Arc is never detected, although `SpeakerWatcher.swift` already knows Arc for participant capture.

**Fix.** Add an Arc tab-listing handler (literal `tell application "Arc"`, guarded by the running-process check) and include Arc in the page-snapshot path. Out of 0.4.2.

## Earlier todos

- ASR validator: a consistency rule (accept when two attempts agree) and a strict-speech >= 30 % gate for sparse-speech Windows; the coverage rule alone rejected correct Gemini output on a 38-second recording (2026-11-10).
- Notification title for a Window fallback uses the folder id instead of the meeting name.
- Log a line when a Window cannot be split further.
- Microphone hardware checks from `docs/operations/release-smoke-checklist.md` (fifine, Brio, AirPods, mid-call unplug).
- Call detection: Arc and other Chromium browsers are not scripted for detection (only Chrome, Brave, Edge and Safari); a Meet or huddle in Arc never prompts (2026-11-11).
