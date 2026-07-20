import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const apiSource = readFileSync(join(__dirname, "../src/lib/api.ts"), "utf8");
const chatStoreSource = readFileSync(
  join(__dirname, "../src/lib/chat-store.tsx"),
  "utf8",
);
const chatPanelSource = readFileSync(
  join(__dirname, "../src/app/chat/chat-panel.tsx"),
  "utf8",
);

test("ChatMessage interface includes an id field", () => {
  assert.match(
    chatStoreSource,
    /interface ChatMessage \{\s*id: string;\s*role: "user" \| "assistant";\s*content: string;\s*\}/,
  );
});

test("getSessionMessages hydration keeps the id (does not strip it)", () => {
  const stripPattern = /msgs\.map\(\(m\) => \(\{ role: m\.role, content: m\.content \}\)\)/;
  assert.doesNotMatch(
    chatStoreSource,
    stripPattern,
    "the old id-stripping map must be gone",
  );
  assert.match(
    chatStoreSource,
    /msgs\.map\(\(m\) => \(\{ id: m\.id, role: m\.role, content: m\.content \}\)\)/,
  );
});

test("chat-panel message list uses message.id as key, not array index", () => {
  assert.doesNotMatch(
    chatPanelSource,
    /activeMessages\.map\(\(message, index\)[\s\S]*?key=\{index\}/,
  );
  assert.match(
    chatPanelSource,
    /activeMessages\.map\(\(message\)[\s\S]*?key=\{message\.id\}/,
  );
});

test("optimistic user append carries a client id", () => {
  assert.match(
    chatStoreSource,
    /APPEND_MESSAGE[\s\S]*?\{ id: [\s\S]*?, role: "user", content: message \}/,
  );
  assert.match(
    chatStoreSource,
    /APPEND_MESSAGE[\s\S]*?\{ id: [\s\S]*?, role: "assistant", content: "" \}/,
  );
});

test("sendChatMessage forwards AbortSignal to fetch", () => {
  assert.match(
    apiSource,
    /export async function sendChatMessage\([\s\S]*?signal\?: AbortSignal[\s\S]*?\)[\s\S]*?fetch\([\s\S]*?, \{[\s\S]*?signal,[\s\S]*?\}\)/,
  );
});

test("sendChatMessage reader loop has a finally that cancels the reader", () => {
  assert.match(
    apiSource,
    /const reader = res\.body\.getReader\(\);[\s\S]*?try \{[\s\S]*?\} finally \{[\s\S]*?reader\.cancel\(\)/,
  );
});

test("editMessage wrapper issues PATCH with content", () => {
  assert.match(
    apiSource,
    /export async function editMessage\([\s\S]*?\)[\s\S]*?fetch\(`\$\{API_BASE_URL\}\/api\/sessions\/\$\{sessionId\}\/messages\/\$\{messageId\}`, \{[\s\S]*?method: "PATCH"[\s\S]*?body: JSON\.stringify\(\{ content \}\)/,
  );
  assert.match(apiSource, /await assertOk\(res, "Edit message"\)/);
});

test("deleteMessage wrapper issues DELETE", () => {
  assert.match(
    apiSource,
    /export async function deleteMessage\([\s\S]*?\)[\s\S]*?fetch\(`\$\{API_BASE_URL\}\/api\/sessions\/\$\{sessionId\}\/messages\/\$\{messageId\}`, \{[\s\S]*?method: "DELETE"[\s\S]*?\}\)/,
  );
  assert.match(apiSource, /await assertOk\(res, "Delete message"\)/);
});

test("updateSession wrapper issues PATCH with title", () => {
  assert.match(
    apiSource,
    /export async function updateSession\([\s\S]*?\)[\s\S]*?fetch\(`\$\{API_BASE_URL\}\/api\/sessions\/\$\{sessionId\}`, \{[\s\S]*?method: "PATCH"[\s\S]*?body: JSON\.stringify\(\{ title \}\)/,
  );
  assert.match(apiSource, /await assertOk\(res, "Update session"\)/);
});

test("sendMessage creates a session up-front when there is no activeId", () => {
  // Must call createSession() before sendChatMessage() when activeId is null,
  // dispatch ADD_SESSION + SET_ACTIVE so the sidebar updates immediately.
  assert.match(
    chatStoreSource,
    /const sendMessage = useCallback\([\s\S]*?if \(!activeIdRef\.current\) \{[\s\S]*?const session = await createSession\(\);[\s\S]*?dispatch\(\{ type: "ADD_SESSION", session \}\);[\s\S]*?dispatch\(\{ type: "SET_ACTIVE", activeId: session\.id \}\);[\s\S]*?activeIdRef\.current = session\.id;[\s\S]*?\}/,
  );
});

test("sendMessage no longer uses the __new__ bucket as a fallback", () => {
  // The legacy pattern `const bucket = sessionId ?? "__new__"` must be gone.
  assert.doesNotMatch(
    chatStoreSource,
    /const bucket = sessionId \?\? "__new__"/,
  );
  // ADD_SESSION action type must exist in the Action union.
  assert.match(chatStoreSource, /\| \{ type: "ADD_SESSION"; session: ChatSession \}/);
});

test("sendMessage accepts a regenerate flag", () => {
  assert.match(
    chatStoreSource,
    /const sendMessage = useCallback\(\s*async \(message: string, options\?: \{ regenerate\?: boolean \}\) => \{/,
  );
  // And forwards it to sendChatMessage.
  assert.match(
    chatStoreSource,
    /await sendChatMessage\([\s\S]*?, \{[\s\S]*?regenerate[\s\S]*?\}\);/,
  );
});

test("sendMessage finally clears sendingRef only for its own generation", () => {
  assert.match(
    chatStoreSource,
    /finally \{[\s\S]*?if \(generationTokenRef\.current === generationToken\) \{[\s\S]*?sendingRef\.current = false;/,
  );
});

test("Action union includes EDIT_MESSAGE, DELETE_MESSAGES, RETRACT_LAST", () => {
  assert.match(chatStoreSource, /\| \{ type: "EDIT_MESSAGE"; id: string; content: string \}/);
  assert.match(chatStoreSource, /\| \{ type: "DELETE_MESSAGES"; ids: string\[\] \}/);
  assert.match(chatStoreSource, /\| \{ type: "RETRACT_LAST"; content: string \}/);
});

test("reducer handles EDIT_MESSAGE (replace content + drop later messages)", () => {
  assert.match(
    chatStoreSource,
    /case "EDIT_MESSAGE": \{[\s\S]*?\.map\(m => m\.id === action\.id \? \{ \.\.\.m, content: action\.content \} : m\)/,
  );
  assert.match(
    chatStoreSource,
    /case "EDIT_MESSAGE": \{[\s\S]*?const idx = .*\.findIndex[\s\S]*?\.slice\(0, idx \+ 1\)/,
  );
});

test("reducer handles DELETE_MESSAGES by id list", () => {
  assert.match(
    chatStoreSource,
    /case "DELETE_MESSAGES": \{[\s\S]*?filter\(\(m\) => !action\.ids\.includes\(m\.id\)\)/,
  );
});

test("reducer handles RETRACT_LAST (drop ONLY trailing assistant + last user, keep history)", () => {
  assert.match(chatStoreSource, /composerInput: string/);
  // Must NOT wipe all assistant messages — only the trailing ones via a while loop,
  // otherwise historical assistant replies (e.g. A1 in [U1,A1,U2,A2]) get deleted too.
  assert.doesNotMatch(
    chatStoreSource,
    /case "RETRACT_LAST": \{[\s\S]*?filter\(\(m\) => m\.role !== "assistant"\)/,
  );
  assert.match(
    chatStoreSource,
    /case "RETRACT_LAST": \{[\s\S]*?while \(end > 0 && prev\[end - 1\]\.role === "assistant"\) end--/,
  );
  assert.match(
    chatStoreSource,
    /case "RETRACT_LAST": \{[\s\S]*?\.slice\(0, end - 1\)/,
  );
  assert.match(chatStoreSource, /composerInput: action\.content/);
});

test("ChatStoreValue exposes editMessage, deleteMessage, retractLast", () => {
  assert.match(
    chatStoreSource,
    /editMessage: \(messageId: string, content: string\) => Promise<void>;/,
  );
  assert.match(
    chatStoreSource,
    /deleteMessage: \(messageId: string\) => Promise<void>;/,
  );
  assert.match(chatStoreSource, /retractLast: \(\) => void;/);
});

test("editMessage dispatches EDIT_MESSAGE and calls API editMessage + sendMessage regenerate", () => {
  // Pattern: hold sendingRef during API edit only, optimistic EDIT_MESSAGE,
  // then sendMessage(content, { regenerate: true }) after releasing the lock.
  assert.match(
    chatStoreSource,
    /const editMessage = useCallback\([\s\S]*?sendingRef\.current = true;[\s\S]*?dispatch\(\{ type: "EDIT_MESSAGE", id: messageId, content \}\);[\s\S]*?await editMessageApi\(activeId, messageId, content\);[\s\S]*?finally \{[\s\S]*?sendingRef\.current = false;[\s\S]*?await sendMessage\(content, \{ regenerate: true \}\)/,
  );
});

test("deleteMessage calls API then dispatches DELETE_MESSAGES with server-deleted ids", () => {
  // Non-optimistic: await the API first, then dispatch with the authoritative
  // deleted-id list from the server (avoids rollback on failure).
  assert.match(
    chatStoreSource,
    /const deleteMessage = useCallback\([\s\S]*?const result = await deleteMessageApi\(activeId, messageId\);[\s\S]*?dispatch\(\{ type: "DELETE_MESSAGES", ids: result\.deleted \}\)/,
  );
});

test("retractLast invalidates stream, aborts, RETRACT_LAST, best-effort deleteMessageApi (client-id resolve)", () => {
  assert.match(
    chatStoreSource,
    /const retractLast = useCallback\(\(\) => \{[\s\S]*?generationTokenRef\.current \+= 1;[\s\S]*?const cleanupToken = generationTokenRef\.current;[\s\S]*?sendingRef\.current = false;[\s\S]*?abortControllerRef\.current\?\.abort\(\);[\s\S]*?dispatch\(\{ type: "RETRACT_LAST", content: lastUser\.content \}\);[\s\S]*?messageId\.startsWith\("client-"\)[\s\S]*?getSessionMessages\(activeId\)[\s\S]*?generationTokenRef\.current !== cleanupToken[\s\S]*?m\.content === lastUser\.content[\s\S]*?deleteMessageApi\(activeId, messageId\)/,
  );
  // Must NOT use store deleteMessage for retract cleanup (that would SET_ERROR).
  assert.doesNotMatch(
    chatStoreSource,
    /const retractLast = useCallback\(\(\) => \{[\s\S]*?void deleteMessage\(lastUser\.id\)/,
  );
});

test("retractLast guards rapid double-call with retractingRef (cleared only when generating ends)", () => {
  assert.match(chatStoreSource, /const retractingRef = useRef\(false\);/);
  assert.match(
    chatStoreSource,
    /const retractLast = useCallback\(\(\) => \{[\s\S]*?if \(!state\.generating \|\| retractingRef\.current\) return;[\s\S]*?retractingRef\.current = true;/,
  );
  // Clear only via effect when generating becomes false — not immediately in finally.
  assert.match(
    chatStoreSource,
    /useEffect\(\(\) => \{[\s\S]*?if \(!state\.generating\) \{[\s\S]*?retractingRef\.current = false;[\s\S]*?\}[\s\S]*?\}, \[state\.generating\]\);/,
  );
});

test("editMessage early-returns when generating or sending", () => {
  assert.match(
    chatStoreSource,
    /const editMessage = useCallback\([\s\S]*?if \(state\.generating \|\| sendingRef\.current\) return;[\s\S]*?const activeId = activeIdRef\.current;[\s\S]*?if \(!activeId\) return;/,
  );
  assert.match(
    chatStoreSource,
    /const editMessage = useCallback\([\s\S]*?\}, \[[\s\S]*?state\.generating[\s\S]*?\]/,
  );
});

test("chat-panel user messages render Edit and Delete buttons", () => {
  // Must import Pencil + Trash2 (or equivalent) from lucide-react.
  assert.match(chatPanelSource, /import \{[^}]*Pencil[^}]*\} from "lucide-react"/);
  assert.match(chatPanelSource, /import \{[^}]*Trash2[^}]*\} from "lucide-react"/);
  // Each user message has both buttons; aria-labels for accessibility.
  assert.match(chatPanelSource, /aria-label=\{t\("Edit"\)\}/);
  assert.match(chatPanelSource, /aria-label=\{t\("Delete"\)\}/);
});

test("edit/delete buttons are disabled while generating", () => {
  assert.match(
    chatPanelSource,
    /disabled=\{isStreaming\}[\s\S]*?aria-label=\{t\("Edit"\)\}/,
  );
  assert.match(
    chatPanelSource,
    /disabled=\{isStreaming\}[\s\S]*?aria-label=\{t\("Delete"\)\}/,
  );
});

test("edit click enters in-place textarea with confirm/cancel", () => {
  // Edit mode: render a textarea prefilled with the message content, plus
  // confirm (Check icon) and cancel (X icon) controls.
  assert.match(chatPanelSource, /editingId[\s\S]*?=== message\.id/);
  assert.match(chatPanelSource, /<textarea[\s\S]*?value=\{editDraft\}/);
  assert.match(chatPanelSource, /aria-label=\{t\("Confirm"\)\}/);
  assert.match(chatPanelSource, /aria-label=\{t\("Cancel"\)\}/);
});

test("confirm edit calls editMessage(content) from the store", () => {
  // Prefer matching the actual call form used in implementation.
  // Use this pattern (allows trim safety):
  assert.match(chatPanelSource, /void editMessage\(message\.id,/);
  assert.match(chatPanelSource, /editDraft/);
});

test("delete click shows a confirm dialog then calls deleteMessage", () => {
  assert.match(chatPanelSource, /pendingDeleteMessageId/);
  assert.doesNotMatch(chatPanelSource, /window\.confirm/);
  assert.match(chatPanelSource, /DeleteMessageDialog|delete-message-dialog/);
  assert.match(chatPanelSource, /deleteMessage\(/);
});

test("chat-panel has a keydown Escape listener gated on state.generating", () => {
  // The handler must (a) ignore non-Escape keys, (b) early-return when not
  // generating, (c) call retractLast on Escape while generating.
  assert.match(
    chatPanelSource,
    /useEffect\(\(\) => \{[\s\S]*?function handleKeyDown\(event: KeyboardEvent\) \{[\s\S]*?if \(event\.key !== "Escape"\) return;[\s\S]*?if \(!state\.generating\) return;[\s\S]*?retractLast\(\);[\s\S]*?\}[\s\S]*?window\.addEventListener\("keydown", handleKeyDown\)/,
  );
});

test("chat-panel shows a Stop button in the composer while generating", () => {
  assert.match(chatPanelSource, /import \{[^}]*CircleStop[^}]*\} from "lucide-react"/);
  // Stop replaces Send while generating
  assert.match(
    chatPanelSource,
    /isStreaming \? \([\s\S]*?onClick=\{retractLast\}[\s\S]*?aria-label=\{t\("Stop"\)\}[\s\S]*?<CircleStop/,
  );
  // StatusIndicator no longer accompanied by Stop button in the message list area
  assert.doesNotMatch(
    chatPanelSource,
    /StatusIndicator[\s\S]{0,200}retractLast/,
  );
});

test("user Edit/Delete controls sit outside the primary bubble", () => {
  assert.match(
    chatPanelSource,
    /group ml-auto flex max-w-\[85%\] items-end gap-1/,
  );
  assert.match(
    chatPanelSource,
    /disabled=\{isStreaming\}[\s\S]*?aria-label=\{t\("Edit"\)\}/,
  );
  assert.match(
    chatPanelSource,
    /disabled=\{isStreaming\}[\s\S]*?aria-label=\{t\("Delete"\)\}/,
  );
});

test("deleteMessage removes empty session after last messages deleted", () => {
  assert.match(
    chatStoreSource,
    /const deleteMessage = useCallback\([\s\S]*?deleteMessageApi[\s\S]*?getSessionMessages[\s\S]*?length === 0[\s\S]*?deleteSession[\s\S]*?handleNew/,
  );
});

test("i18n catalog has new keys for edit/delete/stop", () => {
  const i18nSource = readFileSync(
    join(__dirname, "../src/lib/i18n.tsx"),
    "utf8",
  );
  // catalog entries are "key": "translation"
  assert.match(i18nSource, /"Edit message":/);
  assert.match(i18nSource, /"Stop":/);
  assert.match(i18nSource, /"Delete message":/);
  assert.match(
    i18nSource,
    /"Delete this message and its reply\?":/,
  );
});
