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
} from "@/lib/api";

const LAST_SESSION_KEY = "memento-last-chat-session";

interface ChatMessage {
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
}

const initialState: State = {
  sessions: [],
  activeId: null,
  messagesBySession: {},
  generating: null,
  pendingProposal: null,
  error: "",
  memoryRefreshKey: 0,
};

type Action =
  | { type: "SET_SESSIONS"; sessions: ChatSession[] }
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
  | { type: "BUMP_MEMORY_REFRESH" };

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
  sendMessage: (message: string) => Promise<void>;
  rememberCommand: (content: string, raw: string) => Promise<void>;
  acceptProposal: (content: string) => Promise<void>;
  rejectProposal: () => void;
  requestDelete: (session: ChatSession) => Promise<void>;
}

const ChatStoreContext = createContext<ChatStoreValue | null>(null);

export function ChatStoreProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const activeIdRef = useRef<string | null>(null);
  useEffect(() => {
    activeIdRef.current = state.activeId;
  }, [state.activeId]);

  const selectSessionInner = useCallback(async (id: string) => {
    try {
      const msgs = await getSessionMessages(id);
      dispatch({ type: "SET_MESSAGES", sessionId: id, messages: msgs.map((m) => ({ role: m.role, content: m.content })) });
      dispatch({ type: "SET_ACTIVE", activeId: id });
      localStorage.setItem(LAST_SESSION_KEY, id);
    } catch (e) {
      dispatch({ type: "SET_ERROR", error: e instanceof Error ? e.message : "Operation failed" });
    }
  }, []);

  const loadSessions = useCallback(async () => {
    try {
      const list = await listSessions();
      dispatch({ type: "SET_SESSIONS", sessions: list });
      const last = localStorage.getItem(LAST_SESSION_KEY);
      const restoreId = last && list.some((s) => s.id === last) ? last : null;
      if (restoreId) {
        await selectSessionInner(restoreId);
      }
    } catch (e) {
      dispatch({ type: "SET_ERROR", error: e instanceof Error ? e.message : "Operation failed" });
    }
  }, [selectSessionInner]);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  const selectSession = selectSessionInner;

  const handleNew = useCallback(() => {
    dispatch({ type: "SET_MESSAGES", sessionId: "__new__", messages: [] });
    dispatch({ type: "SET_ACTIVE", activeId: null });
    localStorage.removeItem(LAST_SESSION_KEY);
  }, []);

  const sendMessage = useCallback(
    async (message: string) => {
      if (!message.trim() || state.generating) return;
      // Determine target session: existing active, or pending-new (activeId null).
      const sessionId = state.activeId;
      const bucket = sessionId ?? "__new__";
      dispatch({ type: "SET_ERROR", error: "" });
      dispatch({ type: "APPEND_MESSAGE", sessionId: bucket, message: { role: "user", content: message } });
      dispatch({ type: "APPEND_MESSAGE", sessionId: bucket, message: { role: "assistant", content: "" } });
      dispatch({ type: "START_GENERATING", sessionId: bucket });

      try {
        await sendChatMessage(message, sessionId, {
          onDelta: (delta) => {
            dispatch({ type: "SET_STREAMING" });
            dispatch({ type: "PATCH_LAST_MESSAGE", sessionId: activeIdRef.current ?? bucket, content: delta, replace: false });
          },
          onStatus: (_state, tool) => {
            dispatch({ type: "SET_TOOL_CALL", tool });
          },
          onTextReplace: (content) => {
            dispatch({ type: "PATCH_LAST_MESSAGE", sessionId: activeIdRef.current ?? bucket, content, replace: true });
          },
          onDone: async (newSessionId) => {
            // New session created server-side: migrate the __new__ bucket to the real id.
            if (!sessionId) {
              const prevMsgs = state.messagesBySession["__new__"] ?? [];
              dispatch({ type: "SET_MESSAGES", sessionId: newSessionId, messages: prevMsgs });
              dispatch({ type: "SET_MESSAGES", sessionId: "__new__", messages: [] });
              dispatch({ type: "SET_ACTIVE", activeId: newSessionId });
              activeIdRef.current = newSessionId;
              localStorage.setItem(LAST_SESSION_KEY, newSessionId);
            }
            dispatch({ type: "STOP_GENERATING" });
            try {
              dispatch({ type: "SET_SESSIONS", sessions: await listSessions() });
            } catch {
              /* non-fatal */
            }
          },
          onError: (msg) => {
            dispatch({ type: "SET_ERROR", error: msg });
            dispatch({ type: "STOP_GENERATING" });
          },
          onMemoryProposal: (content) => {
            dispatch({ type: "SET_PROPOSAL", proposal: { sessionId: activeIdRef.current ?? bucket, content } });
          },
        });
      } catch (e) {
        dispatch({ type: "SET_ERROR", error: e instanceof Error ? e.message : "Operation failed" });
        dispatch({ type: "STOP_GENERATING" });
      }
    },
    [state.generating, state.activeId, state.messagesBySession]
  );

  const rememberCommand = useCallback(
    async (content: string, raw: string) => {
      if (!content.trim()) return;
      const bucket = state.activeId ?? "__new__";
      try {
        await createMemory(content);
        dispatch({ type: "BUMP_MEMORY_REFRESH" });
        dispatch({ type: "APPEND_MESSAGE", sessionId: bucket, message: { role: "user", content: raw } });
        dispatch({ type: "APPEND_MESSAGE", sessionId: bucket, message: { role: "assistant", content: "Got it — remembered." } });
      } catch (e) {
        dispatch({ type: "SET_ERROR", error: e instanceof Error ? e.message : "Operation failed" });
      }
    },
    [state.activeId]
  );

  const acceptProposal = useCallback(async (content: string) => {
    try {
      await createMemory(content);
      dispatch({ type: "BUMP_MEMORY_REFRESH" });
    } catch (e) {
      dispatch({ type: "SET_ERROR", error: e instanceof Error ? e.message : "Operation failed" });
    }
    dispatch({ type: "SET_PROPOSAL", proposal: null });
  }, []);

  const rejectProposal = useCallback(() => dispatch({ type: "SET_PROPOSAL", proposal: null }), []);

  const requestDelete = useCallback(async (session: ChatSession) => {
    try {
      await deleteSession(session.id);
      dispatch({ type: "SET_SESSIONS", sessions: await listSessions() });
      if (state.activeId === session.id) handleNew();
    } catch (e) {
      dispatch({ type: "SET_ERROR", error: e instanceof Error ? e.message : "Operation failed" });
    }
  }, [state.activeId, handleNew]);

  const activeMessages = state.messagesBySession[state.activeId ?? "__new__"] ?? [];

  const value: ChatStoreValue = {
    state,
    activeMessages,
    selectSession,
    loadSessions,
    handleNew,
    sendMessage,
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
