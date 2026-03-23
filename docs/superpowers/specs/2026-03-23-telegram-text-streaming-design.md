# Telegram Text Streaming for Claudegram

**Date:** 2026-03-23
**Status:** Draft
**Scope:** `src/telegram/message-sender.ts` in Claudegram fork (`maksyms/claudegram`)

## Problem

Claudegram's streaming mode (`STREAMING_MODE=streaming`) is functionally identical to wait mode. The `updateStream()` method accumulates text in memory but never calls `editMessageText`, so users see only a "Processing..." spinner (and occasional terminal UI tool status) until the full response arrives. The `STREAMING_DEBOUNCE_MS` config (defined in `src/config.ts`) exists but is never referenced outside config parsing.

## Solution

Add a periodic timer (3-second interval) that edits the Telegram placeholder message with the accumulated plain text as Claude generates it. The final response is delivered as formatted MarkdownV2 (existing behavior, unchanged).

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Format during streaming | Plain text (`parse_mode: undefined`) | Partial markdown breaks MarkdownV2 parsing; plain text is always safe |
| Format on completion | MarkdownV2 (existing) | No change to `finishStreaming()` |
| Update mechanism | Periodic timer (3s interval) | Simpler than event-driven debounce; natural coalescing of rapid `onProgress` calls |
| Long text handling | Sliding window (last ~3500 chars) | Prefix with "..." when truncated; `finishStreaming()` handles Telegraph/chunking as normal |
| Tool operation interleave | Tool status takes priority | Timer checks `state.currentOperation`; defers to `flushTerminalUpdate()` when tool is active |
| Deployment | Fork first, upstream PR later | Validate in `maksyms/claudegram`, contribute back once proven |

## Changes

All changes are in `src/telegram/message-sender.ts` unless noted.

### 1. New Constant

Rename `MIN_EDIT_INTERVAL_MS` (currently `10000`) to `TEXT_STREAM_INTERVAL_MS` and reduce to `3000`:

```typescript
const TEXT_STREAM_INTERVAL_MS = 3000;  // was: MIN_EDIT_INTERVAL_MS = 10000
```

Update all references to `MIN_EDIT_INTERVAL_MS` throughout the file to use `TEXT_STREAM_INTERVAL_MS`. The periodic timer is the primary throttle; both text streaming and terminal UI edits share this interval.

### 2. StreamState Changes

Rename existing `lastUpdate` field to `lastEditMs` throughout the file (lines 28, 185, 284, 327) for clarity. Add new fields after `updateScheduled`. Full interface with changes marked:

```typescript
interface StreamState {
  chatId: number;
  threadId?: number;
  sessionKey: string;
  messageId: number | null;
  content: string;
  lastEditMs: number;              // RENAMED from lastUpdate
  updateScheduled: boolean;        // existing, currently unused
  typingInterval: NodeJS.Timeout | null;  // existing, typing indicator

  // Text streaming (NEW)
  textStreamInterval: NodeJS.Timeout | null;
  lastEditedContent: string;

  // Terminal UI mode (existing)
  terminalMode: boolean;
  spinnerIndex: number;
  spinnerInterval: NodeJS.Timeout | null;  // defined but never set via setInterval
  currentOperation: ToolOperation | null;
  backgroundTasks: Array<{ name: string; status: 'running' | 'complete' | 'error' }>;
  rateLimitedUntil: number;
}
```

**Notes:**
- `spinnerInterval` exists in the interface but is never set via `setInterval` in the current codebase. The spinner index is incremented on tool events, not by a timer. No conflict with the new text stream timer.
- `updateScheduled` is defined but unused in the current codebase.
- `typingInterval` drives the "typing..." chat action indicator (every 4s). It is independent of message edits and does not conflict with the text stream timer.

### 3. startStreaming() -- Start Timer

After creating the placeholder message (existing), start the periodic timer:

```typescript
state.textStreamInterval = setInterval(() => {
  this.flushTextStream(ctx, state);
}, TEXT_STREAM_INTERVAL_MS);
```

Initialize new fields in the `StreamState` object literal:
```typescript
textStreamInterval: null,  // set after setInterval
lastEditedContent: '',
lastEditMs: 0,             // renamed from lastUpdate: Date.now()
```

### 4. New Method: flushTextStream()

Core logic, called every 3 seconds by the timer:

```
private async flushTextStream(ctx: Context, state: StreamState): Promise<void> {
  // Verify state is still active
  const currentState = this.streamStates.get(state.sessionKey);
  if (!currentState || currentState !== state || !state.messageId) return;

  // 1. Respect 429 backoff
  if (Date.now() < state.rateLimitedUntil) return;

  // 2. If tool operation active + terminal mode, delegate to terminal UI and return.
  //    When terminalMode is false, skip tool status and check for text updates (steps 3-4).
  //    Note: JavaScript is single-threaded, so no race between this timer callback and
  //    direct calls to flushTerminalUpdate() from updateToolOperation(). Both share
  //    lastEditMs to prevent redundant edits within the same interval.
  if (state.currentOperation !== null && state.terminalMode) {
    await this.flushTerminalUpdate(ctx, state);
    return;
  }

  // 3. No text yet — keep placeholder
  if (state.content === '') return;

  // 4. Content unchanged since last edit — skip
  if (state.content === state.lastEditedContent) return;

  // 5. Prepare display text with sliding window
  let displayText: string;
  if (state.content.length <= 3500) {
    displayText = state.content;
  } else {
    displayText = '...\n\n' + state.content.slice(-3500);
  }

  // 6. Append cursor to signal "still generating"
  displayText += ' \u2589';

  // 7. Edit the placeholder message (plain text, no markdown parsing)
  try {
    await ctx.api.editMessageText(
      state.chatId,
      state.messageId!,
      displayText,
      { parse_mode: undefined }
    );
    state.lastEditedContent = state.content;
    state.lastEditMs = Date.now();
  } catch (error: unknown) {
    // 8. Handle 429 rate limit
    if (error instanceof GrammyError && error.error_code === 429) {
      const retryAfter = error.parameters.retry_after ?? 60;
      state.rateLimitedUntil = Date.now() + retryAfter * 1000;
      console.warn(`[TextStream] Rate limited, backing off for ${retryAfter}s`);
      return;
    }
    // 9. Silently ignore "message not modified" and "message ID invalid"
    if (error instanceof Error) {
      const msg = error.message.toLowerCase();
      if (!msg.includes('message is not modified') && !msg.includes('message_id_invalid')) {
        console.error('[TextStream] Error editing message:', error);
      }
    }
  }
}
```

**Notes:**
- Step 2: When a tool operation is active AND terminal mode is enabled, delegate to `flushTerminalUpdate()` which shows tool status. When terminal mode is disabled but a tool is active, skip tool status and check for text updates (steps 3-4). If no new text exists, nothing happens and the placeholder remains.
- Step 5: `String.slice()` operates on UTF-16 code units; splitting a surrogate pair is theoretically possible but Telegram handles malformed strings gracefully. Not worth the complexity of grapheme-aware slicing.
- Step 9: Matches the existing error handling pattern in `flushTerminalUpdate()` (lines 336-342).

### 5. flushTerminalUpdate() -- Unified Rate Limit

Modify `flushTerminalUpdate()` to share the rate limit field:

1. Rename `state.lastUpdate` to `state.lastEditMs` throughout (lines 284, 327).
2. Replace `MIN_EDIT_INTERVAL_MS` with `TEXT_STREAM_INTERVAL_MS` in the throttle check (line 285).

**Concurrency note:** JavaScript is single-threaded. `flushTerminalUpdate()` can be called from two paths:
- From the text stream timer (via `flushTextStream()` step 2) -- already throttled by the 3s interval.
- Directly from `updateToolOperation()` (line 241) on tool events -- the `TEXT_STREAM_INTERVAL_MS` check on `lastEditMs` prevents rapid event-driven edits.

Both paths are mutually exclusive within a single event loop tick, so there is no race condition. The shared `lastEditMs` field ensures at most one edit per 3-second window regardless of the call path.

### 6. finishStreaming() -- Clear Timer

Add to the beginning of `finishStreaming()`, before existing cleanup:

```typescript
if (state.textStreamInterval) {
  clearInterval(state.textStreamInterval);
  state.textStreamInterval = null;
}
```

### 7. cancelStreaming() -- Clear Timer

Same cleanup in `cancelStreaming()`:

```typescript
if (state.textStreamInterval) {
  clearInterval(state.textStreamInterval);
  state.textStreamInterval = null;
}
```

## What Does NOT Change

- `updateStream()` -- still just sets `state.content`. No async, no edits.
- `handleStreamingResponse()` / `handleWaitResponse()` in `message.handler.ts` -- unchanged.
- `finishStreaming()` formatting logic -- MarkdownV2 conversion, Telegraph routing, chunking all unchanged.
- Config schema -- no new env vars required. `STREAMING_DEBOUNCE_MS` (defined in `src/config.ts`, default `500`) stays unused. Future work can wire it as an override: `const TEXT_STREAM_INTERVAL_MS = config.STREAMING_DEBOUNCE_MS || 3000;`
- Wait mode -- completely unaffected (no `StreamState` created).

## User Experience

### Timeline Example

```
t=0.0s  User sends message
t=0.1s  Placeholder: "spinner Processing..."
t=0.2s  Claude starts generating text (onProgress fires)
t=3.0s  Timer tick -> edit: "Let me look at that file. |"
t=4.0s  Claude calls Read tool -> onToolStart
t=6.0s  Timer tick -> tool active + terminalMode -> edit: "spinner Reading src/config.ts..."
t=7.0s  Tool completes -> onToolEnd, more text arrives
t=9.0s  Timer tick -> no tool active -> edit: "Let me look at that file.\n\nHere's... |"
t=12.0s Timer tick -> more text, sliding window if >3500 chars
t=14.0s Claude finishes -> finishStreaming() -> formatted MarkdownV2 response
```

### Edge Cases

| Case | Behavior |
|---|---|
| Empty response (tools only) | Timer ticks, no content, skips. `finishStreaming()` handles normally. |
| No text yet (tools running first) | Timer skips text (step 3). Terminal UI shows tool status if enabled. Placeholder unchanged otherwise (with terminal mode disabled). |
| Fast response (<3s) | Timer starts but first tick at t=3s. `finishStreaming()` clears it before it fires. User sees: placeholder -> final formatted response. Same as current behavior. |
| Abort/cancel | Timer cleared by `cancelStreaming()`. "Request cancelled" message shown. |
| Response >2500 chars | Streams plain text with sliding window during generation. On completion, `finishStreaming()` routes to Telegraph as normal. |
| Multiple rapid onProgress calls | Natural coalescing -- timer reads latest `state.content` on tick. No wasted edits. |
| Rate limited (429) | Respects `rateLimitedUntil`, skips edits until backoff expires. |
| Terminal UI disabled + tool active | Timer falls through to show text (step 2 only delegates when `terminalMode` is true). |

## Rate Limiting

- Timer interval: 3s (max ~20 edits/min)
- Shared `lastEditMs` field between text streaming and terminal UI edits
- `flushTerminalUpdate()` throttle lowered from 10s to 3s (uses `TEXT_STREAM_INTERVAL_MS`)
- 429 backoff: existing `rateLimitedUntil` pattern, respected by both methods
- "Message not modified" / "message ID invalid" errors: silently ignored (no log)
- Well within Telegram's ~30 edits/min safe zone
