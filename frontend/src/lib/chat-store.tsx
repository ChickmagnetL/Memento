"use client";

import {
  createContext,
  useContext,
  useCallback,
  useEffect,
  useRef,
  useReducer,
  type ReactNode,
} from "react";
import {
  ChatSession,
  listSessions,
  getSessionMessages,
  deleteSession,
  sendChatMessage,
  createMemory,
  createSession,
  editMessage as editMessageApi,
  deleteMessage as deleteMessageApi,
} from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

const LAST_SESSION_KEY = "memento-last-chat-session";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

type Generating = {
  sessionId: string;
  status: "thinking" | "tool_call" | "streaming";
  tool?: string;
} | null;

interface State {
  sessions: ChatSession[];
  activeId: string | null;
  messagesBySession: Record<string, ChatMessage[]>;
  generating: Generating;
  pendingProposal: { sessionId: string; content: string } | null;
  error: string;
  memoryRefreshKey: number;
  composerInput: string;
}

const initialState: State = {
  sessions: [],
  activeId: null,
  messagesBySession: {},
  generating: null,
  pendingProposal: null,
  error: "",
  memoryRefreshKey: 0,
  composerInput: "",
};

type Action =
  | { type: "SET_SESSIONS"; sessions: ChatSession[] }
  | { type: "ADD_SESSION"; session: ChatSession }
  | { type: "SET_ACTIVE"; activeId: string | null }
  | { type: "SET_MESSAGES"; sessionId: string; messages: ChatMessage[] }
  | { type: "APPEND_MESSAGE"; sessionId: string; message: ChatMessage }
  | { type: "PATCH_LAST_MESSAGE"; sessionId: string; content: string; replace: boolean }
  | { type: "START_GENERATING"; sessionId: string }
  | { type: "SET_TOOL_CALL"; tool: string }
  | { type: "SET_STREAMING" }
  | { type: "STOP_GENERATING" }
  | { type: "SET_PROPOSAL"; proposal: { sessionId: string; content: string } | null }
  | { type: "SET_ERROR"; error: string }
  | { type: "BUMP_MEMORY_REFRESH" }
  | { type: "EDIT_MESSAGE"; id: string; content: string }
  | { type: "DELETE_MESSAGES"; ids: string[] }
  | { type: "RETRACT_LAST"; content: string }
  | { type: "SET_COMPOSER_INPUT"; content: string };

function lastAssistantContentAppend(prev: ChatMessage[], content: string): ChatMessage[] {
  const next = [...prev];
  const last = next[next.length - 1];
  next[next.length - 1] = { ...last, content: last.content + content };
  return next;
}

function lastAssistantContentReplace(prev: ChatMessage[], content: string): ChatMessage[] {
  const next = [...prev];
  const last = next[next.length - 1];
  next[next.length - 1] = { ...last, content };
  return next;
}

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "SET_SESSIONS":
      return { ...state, sessions: action.sessions };
    case "ADD_SESSION": {
      // Avoid duplicates: if the session id is already present, replace it.
      const filtered = state.sessions.filter((s) => s.id !== action.session.id);
      return { ...state, sessions: [action.session, ...filtered] };
    }
    case "SET_ACTIVE":
      return { ...state, activeId: action.activeId };
    case "SET_MESSAGES":
      return {
        ...state,
        messagesBySession: { ...state.messagesBySession, [action.sessionId]: action.messages },
      };
    case "APPEND_MESSAGE":
      return {
        ...state,
        messagesBySession: {
          ...state.messagesBySession,
          [action.sessionId]: [
            ...(state.messagesBySession[action.sessionId] ?? []),
            action.message,
          ],
        },
      };
    case "PATCH_LAST_MESSAGE": {
      const prev = state.messagesBySession[action.sessionId] ?? [];
      const updated = action.replace
        ? lastAssistantContentReplace(prev, action.content)
        : lastAssistantContentAppend(prev, action.content);
      return {
        ...state,
        messagesBySession: { ...state.messagesBySession, [action.sessionId]: updated },
      };
    }
    case "START_GENERATING":
      return { ...state, generating: { sessionId: action.sessionId, status: "thinking" } };
    case "SET_TOOL_CALL":
      return state.generating
        ? { ...state, generating: { ...state.generating, status: "tool_call", tool: action.tool } }
        : state;
    case "SET_STREAMING":
      return state.generating
        ? { ...state, generating: { ...state.generating, status: "streaming", tool: undefined } }
        : state;
    case "STOP_GENERATING":
      return { ...state, generating: null };
    case "SET_PROPOSAL":
      return { ...state, pendingProposal: action.proposal };
    case "SET_ERROR":
      return { ...state, error: action.error };
    case "BUMP_MEMORY_REFRESH":
      return { ...state, memoryRefreshKey: state.memoryRefreshKey + 1 };
    case "EDIT_MESSAGE": {
      const bucketId = state.activeId;
      if (!bucketId) return state;
      const prev = state.messagesBySession[bucketId] ?? [];
      const idx = prev.findIndex((m) => m.id === action.id);
      if (idx === -1) return state;
      const updated = prev
        .slice(0, idx + 1)
        .map(m => m.id === action.id ? { ...m, content: action.content } : m);
      return {
        ...state,
        messagesBySession: { ...state.messagesBySession, [bucketId]: updated },
      };
    }
    case "DELETE_MESSAGES": {
      const bucketId = state.activeId;
      if (!bucketId) return state;
      const prev = state.messagesBySession[bucketId] ?? [];
      const updated = prev.filter((m) => !action.ids.includes(m.id));
      return {
        ...state,
        messagesBySession: { ...state.messagesBySession, [bucketId]: updated },
      };
    }
    case "RETRACT_LAST": {
      const bucketId = state.activeId;
      if (!bucketId) return state;
      const prev = state.messagesBySession[bucketId] ?? [];
      if (prev.length === 0) return state;
      // Drop ONLY trailing assistant messages (the partial AI reply being retracted).
      // Using a while loop — NOT filter(role !== assistant) — so historical assistant
      // replies (e.g. A1 in [U1,A1,U2,A2-partial]) survive.
      let end = prev.length;
      while (end > 0 && prev[end - 1].role === "assistant") end--;
      // The new tail must be the user message we want to pull back into the composer.
      if (end === 0 || prev[end - 1].role !== "user") return state;
      const remaining = prev.slice(0, end - 1);
      return {
        ...state,
        messagesBySession: { ...state.messagesBySession, [bucketId]: remaining },
        generating: null,
        composerInput: action.content,
      };
    }
    case "SET_COMPOSER_INPUT":
      return { ...state, composerInput: action.content };
    default:
      return state;
  }
}

interface ChatStoreValue {
  state: State;
  // Active session's messages (convenience accessor).
  activeMessages: ChatMessage[];
  selectSession: (id: string) => Promise<void>;
  loadSessions: () => Promise<void>;
  handleNew: () => void;
  sendMessage: (message: string, options?: { regenerate?: boolean }) => Promise<void>;
  editMessage: (messageId: string, content: string) => Promise<void>;
  deleteMessage: (messageId: string) => Promise<void>;
  retractLast: () => void;
  setComposerInput: (content: string) => void;
  rememberCommand: (content: string, raw: string) => Promise<void>;
  acceptProposal: (content: string) => Promise<void>;
  rejectProposal: () => void;
  requestDelete: (session: ChatSession) => Promise<void>;
}

const ChatStoreContext = createContext<ChatStoreValue | null>(null);

export function ChatStoreProvider({ children }: { children: ReactNode }) {
  const { t } = useLanguage();
  const [state, dispatch] = useReducer(reducer, initialState);
  const activeIdRef = useRef<string | null>(null);
  const generationTokenRef = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const sendingRef = useRef(false);
  const retractingRef = useRef(false);
  useEffect(() => {
    activeIdRef.current = state.activeId;
  }, [state.activeId]);
  useEffect(() => {
    if (!state.generating) {
      retractingRef.current = false;
    }
  }, [state.generating]);

  const selectSessionInner = useCallback(async (id: string) => {
    const previousActiveId = activeIdRef.current;
    activeIdRef.current = id;
    generationTokenRef.current += 1;
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    const navigationToken = generationTokenRef.current;
    dispatch({ type: "SET_ACTIVE", activeId: id });
    dispatch({ type: "STOP_GENERATING" });
    try {
      const msgs = await getSessionMessages(id);
      if (generationTokenRef.current !== navigationToken) return;
      dispatch({ type: "SET_MESSAGES", sessionId: id, messages: msgs.map((m) => ({ id: m.id, role: m.role, content: m.content })) });
      localStorage.setItem(LAST_SESSION_KEY, id);
    } catch (e) {
      if (generationTokenRef.current !== navigationToken) return;
      activeIdRef.current = previousActiveId;
      dispatch({ type: "SET_ACTIVE", activeId: previousActiveId });
      dispatch({ type: "SET_ERROR", error: e instanceof Error ? e.message : t("Operation failed") });
    }
  }, [t]);

  const loadSessions = useCallback(async () => {
    const loadToken = generationTokenRef.current;
    try {
      const list = await listSessions();
      dispatch({ type: "SET_SESSIONS", sessions: list });
      const last = localStorage.getItem(LAST_SESSION_KEY);
      const restoreId = last && list.some((s) => s.id === last) ? last : null;
      if (restoreId && generationTokenRef.current === loadToken && activeIdRef.current === null) {
        await selectSessionInner(restoreId);
      }
    } catch (e) {
      if (generationTokenRef.current !== loadToken) return;
      dispatch({ type: "SET_ERROR", error: e instanceof Error ? e.message : t("Operation failed") });
    }
  }, [selectSessionInner, t]);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  const selectSession = selectSessionInner;

  const handleNew = useCallback(() => {
    activeIdRef.current = null;
    generationTokenRef.current += 1;
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    dispatch({ type: "SET_ACTIVE", activeId: null });
    dispatch({ type: "STOP_GENERATING" });
    localStorage.removeItem(LAST_SESSION_KEY);
  }, []);

  const sendMessage = useCallback(
    async (message: string, options?: { regenerate?: boolean }) => {
      if (!message.trim() || state.generating || sendingRef.current) return;
      sendingRef.current = true;
      const regenerate = options?.regenerate === true;
      generationTokenRef.current += 1;
      const generationToken = generationTokenRef.current;

      try {
        // Resolve target session: create one up-front if none is active so the
        // sidebar shows it the instant the user sends (rather than after the
        // LLM replies). The __new__ placeholder bucket is gone.
        let sessionId = activeIdRef.current;
        if (!activeIdRef.current) {
          try {
            const session = await createSession();
            if (generationTokenRef.current !== generationToken) return;
            // Order matters for the source-level test regex:
            // ADD_SESSION → SET_ACTIVE → activeIdRef assignment
            dispatch({ type: "ADD_SESSION", session });
            dispatch({ type: "SET_ACTIVE", activeId: session.id });
            activeIdRef.current = session.id;
            sessionId = session.id;
            localStorage.setItem(LAST_SESSION_KEY, session.id);
          } catch (e) {
            if (generationTokenRef.current !== generationToken) return;
            dispatch({ type: "SET_ERROR", error: e instanceof Error ? e.message : t("Operation failed") });
            return;
          }
        }
        if (!sessionId) return;
        const bucket = sessionId;

        // AbortController for stop/retract.
        const controller = new AbortController();
        abortControllerRef.current = controller;

        dispatch({ type: "SET_ERROR", error: "" });
        if (!regenerate) {
          dispatch({
            type: "APPEND_MESSAGE",
            sessionId: bucket,
            message: { id: `client-user-${crypto.randomUUID()}`, role: "user", content: message },
          });
        }
        dispatch({
          type: "APPEND_MESSAGE",
          sessionId: bucket,
          message: { id: `client-assistant-${crypto.randomUUID()}`, role: "assistant", content: "" },
        });
        dispatch({ type: "START_GENERATING", sessionId: bucket });

        try {
          await sendChatMessage(
            message,
            sessionId,
            {
              onDelta: (delta) => {
                if (generationTokenRef.current !== generationToken) return;
                dispatch({ type: "SET_STREAMING" });
                dispatch({ type: "PATCH_LAST_MESSAGE", sessionId: bucket, content: delta, replace: false });
              },
              onStatus: (_state, tool) => {
                if (generationTokenRef.current !== generationToken) return;
                dispatch({ type: "SET_TOOL_CALL", tool });
              },
              onTextReplace: (content) => {
                if (generationTokenRef.current !== generationToken) return;
                dispatch({ type: "PATCH_LAST_MESSAGE", sessionId: bucket, content, replace: true });
              },
              onDone: async (newSessionId) => {
                if (generationTokenRef.current !== generationToken) return;
                // Always re-hydrate from the backend so client-side temp ids get
                // replaced with authoritative ones (covers edit-regenerate too).
                try {
                  const msgs = await getSessionMessages(newSessionId);
                  if (generationTokenRef.current !== generationToken) return;
                  dispatch({
                    type: "SET_MESSAGES",
                    sessionId: newSessionId,
                    messages: msgs.map((m) => ({ id: m.id, role: m.role, content: m.content })),
                  });
                } catch (e) {
                  if (generationTokenRef.current !== generationToken) return;
                  dispatch({ type: "SET_ERROR", error: e instanceof Error ? e.message : t("Operation failed") });
                }
                dispatch({ type: "STOP_GENERATING" });
                try {
                  const sessions = await listSessions();
                  if (generationTokenRef.current !== generationToken) return;
                  dispatch({ type: "SET_SESSIONS", sessions });
                } catch {
                  /* non-fatal */
                }
              },
              onError: (msg) => {
                if (generationTokenRef.current !== generationToken) return;
                dispatch({ type: "SET_ERROR", error: msg });
                dispatch({ type: "STOP_GENERATING" });
              },
              onMemoryProposal: (content) => {
                if (generationTokenRef.current !== generationToken) return;
                const currentBucket = activeIdRef.current;
                if (currentBucket !== bucket) return;
                dispatch({ type: "SET_PROPOSAL", proposal: { sessionId: bucket, content } });
              },
            }, { signal: controller.signal, regenerate });
        } catch (e) {
          if (generationTokenRef.current !== generationToken) return;
          // Aborted requests throw AbortError; treat abort as a non-error path
          // (the retractLast handler already cleaned up UI/DB).
          if (e instanceof DOMException && e.name === "AbortError") {
            return;
          }
          dispatch({ type: "SET_ERROR", error: e instanceof Error ? e.message : t("Operation failed") });
          dispatch({ type: "STOP_GENERATING" });
        } finally {
          if (abortControllerRef.current === controller) {
            abortControllerRef.current = null;
          }
        }
      } finally {
        if (generationTokenRef.current === generationToken) {
          sendingRef.current = false;
        }
      }
    },
    [state.generating, t],
  );

  const editMessage = useCallback(
    async (messageId: string, content: string) => {
      if (state.generating || sendingRef.current) return;
      const activeId = activeIdRef.current;
      if (!activeId) return;
      // Hold sendingRef only during the API edit — not across sendMessage,
      // which also uses sendingRef and would early-return if still true.
      sendingRef.current = true;
      try {
        // Optimistic: replace content locally + drop everything after.
        dispatch({ type: "EDIT_MESSAGE", id: messageId, content });
        await editMessageApi(activeId, messageId, content);
      } catch (e) {
        // Re-hydrate from backend to revert the optimistic update on failure.
        try {
          const msgs = await getSessionMessages(activeId);
          dispatch({
            type: "SET_MESSAGES",
            sessionId: activeId,
            messages: msgs.map((m) => ({ id: m.id, role: m.role, content: m.content })),
          });
        } catch {
          /* ignore */
        }
        dispatch({ type: "SET_ERROR", error: e instanceof Error ? e.message : t("Operation failed") });
        return;
      } finally {
        sendingRef.current = false;
      }
      // Then trigger regenerate via the streaming endpoint (skip re-storing user).
      await sendMessage(content, { regenerate: true });
    },
    [sendMessage, state.generating, t],
  );

  const deleteMessage = useCallback(
    async (messageId: string) => {
      const activeId = activeIdRef.current;
      if (!activeId) return;
      try {
        const result = await deleteMessageApi(activeId, messageId);
        dispatch({ type: "DELETE_MESSAGES", ids: result.deleted });
        // Refresh sidebar in case the session title was derived from this user msg.
        try {
          const sessions = await listSessions();
          dispatch({ type: "SET_SESSIONS", sessions });
        } catch {
          /* non-fatal */
        }
      } catch (e) {
        dispatch({ type: "SET_ERROR", error: e instanceof Error ? e.message : t("Operation failed") });
      }
    },
    [t],
  );

  const retractLast = useCallback(() => {
    if (!state.generating || retractingRef.current) return;
    retractingRef.current = true;
    const activeId = activeIdRef.current;
    if (!activeId) return;
    const msgs = state.messagesBySession[activeId] ?? [];
    // Find the last user message — its content is what we refill into the composer.
    const lastUser = [...msgs].reverse().find((m) => m.role === "user");

    generationTokenRef.current += 1;
    const cleanupToken = generationTokenRef.current;
    sendingRef.current = false;
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;

    if (!lastUser) {
      dispatch({ type: "STOP_GENERATING" });
      return;
    }
    dispatch({ type: "RETRACT_LAST", content: lastUser.content });

    // Best-effort server cleanup: never surface errors (UI already retracted).
    // Prefer orphan over deleting a newly sent message if generation advanced.
    void (async () => {
      try {
        let messageId = lastUser.id;
        if (messageId.startsWith("client-")) {
          const serverMsgs = await getSessionMessages(activeId);
          if (generationTokenRef.current !== cleanupToken) return;
          const serverLastUser = [...serverMsgs]
            .reverse()
            .find((m) => m.role === "user" && m.content === lastUser.content);
          if (!serverLastUser) return;
          messageId = serverLastUser.id;
        }
        if (generationTokenRef.current !== cleanupToken) return;
        await deleteMessageApi(activeId, messageId);
      } catch {
        /* best-effort */
      }
    })();
  }, [state.generating, state.messagesBySession]);

  const setComposerInput = useCallback(
    (content: string) => dispatch({ type: "SET_COMPOSER_INPUT", content }),
    [],
  );

  const rememberCommand = useCallback(
    async (content: string, raw: string) => {
      if (!content.trim()) return;
      const bucket = activeIdRef.current;
      if (!bucket) return;
      try {
        await createMemory(content);
        dispatch({ type: "BUMP_MEMORY_REFRESH" });
        dispatch({ type: "APPEND_MESSAGE", sessionId: bucket, message: { id: `client-user-${crypto.randomUUID()}`, role: "user", content: raw } });
        dispatch({ type: "APPEND_MESSAGE", sessionId: bucket, message: { id: `client-assistant-${crypto.randomUUID()}`, role: "assistant", content: t("Got it — remembered.") } });
      } catch (e) {
        dispatch({ type: "SET_ERROR", error: e instanceof Error ? e.message : t("Operation failed") });
      }
    },
    [t]
  );

  const acceptProposal = useCallback(async (content: string) => {
    try {
      await createMemory(content);
      dispatch({ type: "BUMP_MEMORY_REFRESH" });
    } catch (e) {
      dispatch({ type: "SET_ERROR", error: e instanceof Error ? e.message : t("Operation failed") });
    }
    dispatch({ type: "SET_PROPOSAL", proposal: null });
  }, [t]);

  const rejectProposal = useCallback(() => dispatch({ type: "SET_PROPOSAL", proposal: null }), []);

  const requestDelete = useCallback(async (session: ChatSession) => {
    try {
      await deleteSession(session.id);
      dispatch({ type: "SET_SESSIONS", sessions: await listSessions() });
      if (activeIdRef.current === session.id) handleNew();
    } catch (e) {
      dispatch({ type: "SET_ERROR", error: e instanceof Error ? e.message : t("Operation failed") });
    }
  }, [handleNew, t]);

  const activeMessages = state.activeId ? (state.messagesBySession[state.activeId] ?? []) : [];

  const value: ChatStoreValue = {
    state,
    activeMessages,
    selectSession,
    loadSessions,
    handleNew,
    sendMessage,
    editMessage,
    deleteMessage,
    retractLast,
    setComposerInput,
    rememberCommand,
    acceptProposal,
    rejectProposal,
    requestDelete,
  };

  return <ChatStoreContext.Provider value={value}>{children}</ChatStoreContext.Provider>;
}

export function useChatStore(): ChatStoreValue {
  const ctx = useContext(ChatStoreContext);
  if (!ctx) throw new Error("useChatStore must be used within ChatStoreProvider");
  return ctx;
}
