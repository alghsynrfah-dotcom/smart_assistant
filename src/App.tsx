import { useState, useRef, useEffect } from "react";
import "./App.css";

type Message = {
  role: "user" | "assistant";
  content: string;
  route?: string;
  source?: string;
  liked?: "like" | "dislike";
  responseTime?: number;
};

type ChatResponse = {
  answer: string;
  route: string;
  source: string;
};

type HistoryItem = {
  question: string;
  answer: string;
  route: string;
  source: string;
};

export default function App() {
  const [darkMode, setDarkMode] = useState(false);
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastMessage, setLastMessage] = useState("");
  const [copiedMessage, setCopiedMessage] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [recommendation, setRecommendation] = useState("");
  const [sessionId, setSessionId] = useState(() => {
  const savedSessionId = sessionStorage.getItem(
    "smart-assistant-session-id"
  );

  if (savedSessionId) {
    return savedSessionId;
  }

  const newSessionId =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `session-${Date.now()}-${Math.random()
          .toString(36)
          .slice(2)}`;

  sessionStorage.setItem(
    "smart-assistant-session-id",
    newSessionId
  );

  return newSessionId;
});
  // CV upload
  const [selectedCv, setSelectedCv] = useState<File | null>(null);
  const [isUploadingCv, setIsUploadingCv] = useState(false);
  const [uploadedCvName, setUploadedCvName] = useState("");

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const cvInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const response = await fetch(
          "http://127.0.0.1:8000/history"
        );

        if (!response.ok) {
          throw new Error("Could not load chat history");
        }

        const data: { history: HistoryItem[] } =
          await response.json();

        const historyMessages: Message[] = [];

        data.history.forEach((item) => {
          historyMessages.push({
            role: "user",
            content: item.question,
          });

          historyMessages.push({
            role: "assistant",
            content: item.answer,
            route: item.route,
            source: item.source,
          });
        });

        setMessages(historyMessages);

        if (data.history.length > 0) {
          setLastMessage(
            data.history[data.history.length - 1].question
          );
        }
      } catch (error) {
        console.error("HISTORY ERROR:", error);
      }
    };

    loadHistory();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, isLoading, error, recommendation]);

  useEffect(() => {
    document.body.style.backgroundColor = darkMode
      ? "#111827"
      : "#f7f7f8";

    return () => {
      document.body.style.backgroundColor = "";
    };
  }, [darkMode]);

  const fetchRecommendation = async (
    conversation: Message[]
  ) => {
    try {
      const response = await fetch(
        "http://127.0.0.1:8000/recommendation",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            conversation: conversation.map((msg) => ({
              role: msg.role,
              content: msg.content,
            })),
          }),
        }
      );

      if (!response.ok) {
        throw new Error("Could not get recommendation");
      }

      const data: { recommendation: string } =
        await response.json();

      setRecommendation(data.recommendation);
    } catch (error) {
      console.error("RECOMMENDATION ERROR:", error);
    }
  };

  const checkRecommendation = async (
    conversation: Message[]
  ) => {
    const userMessageCount = conversation.filter(
      (msg) => msg.role === "user"
    ).length;

    if (
      userMessageCount >= 4 &&
      userMessageCount % 4 === 0
    ) {
      await fetchRecommendation(conversation);
    }
  };

  // =========================
  // CV FILE SELECTION
  // =========================

  const handleCvSelection = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    const isPdf =
      file.type === "application/pdf" ||
      file.name.toLowerCase().endsWith(".pdf");

    if (!isPdf) {
      setError("Please select a PDF file.");
      setSelectedCv(null);

      if (cvInputRef.current) {
        cvInputRef.current.value = "";
      }

      return;
    }

    setError(null);
    setSelectedCv(file);
  };

  // =========================
  // CV UPLOAD
  // =========================

  const uploadCv = async () => {
    if (!selectedCv || isUploadingCv) {
      return;
    }

    setError(null);
    setIsUploadingCv(true);

    try {
      const formData = new FormData();

      formData.append("file", selectedCv);

      const response = await fetch(
        "http://127.0.0.1:8000/cv/upload",
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        throw new Error("CV upload failed");
      }

      const data: {
        message?: string;
        filename?: string;
      } = await response.json();

      setUploadedCvName(
        data.filename || selectedCv.name
      );

      setSelectedCv(null);

      if (cvInputRef.current) {
        cvInputRef.current.value = "";
      }
    } catch (error) {
      console.error("CV UPLOAD ERROR:", error);

      setError(
        "Could not upload the CV. Please try again."
      );
    } finally {
      setIsUploadingCv(false);
    }
  };

  const sendMessage = async (text?: string) => {
    const userText = (text ?? message).trim();

    if (!userText || isLoading) {
      return;
    }

    const startTime = performance.now();

    setError(null);
    setLastMessage(userText);
    setMessage("");
    setIsLoading(true);

    const userMessage: Message = {
      role: "user",
      content: userText,
    };

    setMessages((currentMessages) => [
      ...currentMessages,
      userMessage,
    ]);

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/chat",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
  question: userText,
  conversation_history: messages.map((msg) => ({
    role: msg.role,
    content: msg.content,
  })),
  session_id: sessionId,
}),
        }
      );

      if (!response.ok) {
        throw new Error("Backend request failed");
      }

      const route = response.headers.get("X-Route");
      const source = response.headers.get("X-Source");

      if (route === "rag") {
        if (!response.body) {
          throw new Error("Streaming response is not available");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let assistantAnswer = "";

        setMessages((currentMessages) => [
          ...currentMessages,
          {
            role: "assistant",
            content: "",
            route: "rag",
            source: source || "employee documents",
          },
        ]);

        while (true) {
          const { value, done } =
            await reader.read();

          if (done) {
            break;
          }

          const chunk = decoder.decode(value, {
            stream: true,
          });

          assistantAnswer += chunk;

          setMessages((currentMessages) => {
            const updatedMessages = [...currentMessages];
            const lastIndex =
              updatedMessages.length - 1;

            if (
              lastIndex >= 0 &&
              updatedMessages[lastIndex].role ===
                "assistant"
            ) {
              updatedMessages[lastIndex] = {
                ...updatedMessages[lastIndex],
                content: assistantAnswer,
              };
            }

            return updatedMessages;
          });
        }

        const finalChunk = decoder.decode();

        if (finalChunk) {
          assistantAnswer += finalChunk;
        }

        const responseTime = Number(
          (
            (performance.now() - startTime) /
            1000
          ).toFixed(2)
        );

        const assistantMessage: Message = {
          role: "assistant",
          content: assistantAnswer,
          route: "rag",
          source:
            source || "employee documents",
          responseTime,
        };

        setMessages((currentMessages) => {
          const updatedMessages = [...currentMessages];
          const lastIndex =
            updatedMessages.length - 1;

          if (
            lastIndex >= 0 &&
            updatedMessages[lastIndex].role ===
              "assistant"
          ) {
            updatedMessages[lastIndex] =
              assistantMessage;
          }

          return updatedMessages;
        });

        const updatedConversation: Message[] = [
          ...messages,
          userMessage,
          assistantMessage,
        ];

        await checkRecommendation(
          updatedConversation
        );

        return;
      }

      const data: ChatResponse =
        await response.json();

      const responseTime = Number(
        (
          (performance.now() - startTime) /
          1000
        ).toFixed(2)
      );

      const assistantMessage: Message = {
        role: "assistant",
        content: data.answer,
        route: data.route,
        source: data.source,
        responseTime,
      };

      setMessages((currentMessages) => [
        ...currentMessages,
        assistantMessage,
      ]);

      const updatedConversation: Message[] = [
        ...messages,
        userMessage,
        assistantMessage,
      ];

      await checkRecommendation(
        updatedConversation
      );
    } catch (error) {
      console.error("CHAT ERROR:", error);

      setError(
        "Could not connect to the backend. Please try again."
      );
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = () => {
  window.speechSynthesis.cancel();

  const newSessionId =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `session-${Date.now()}-${Math.random()
          .toString(36)
          .slice(2)}`;

  sessionStorage.setItem(
    "smart-assistant-session-id",
    newSessionId
  );

  setSessionId(newSessionId);

  setMessages([]);
    setError(null);
    setMessage("");
    setLastMessage("");
    setCopiedMessage(null);
    setSearchQuery("");
    setRecommendation("");

    setSelectedCv(null);
    setUploadedCvName("");

    if (cvInputRef.current) {
      cvInputRef.current.value = "";
    }
  };

  const copyMessage = async (
    content: string,
    index: number
  ) => {
    try {
      await navigator.clipboard.writeText(content);

      setCopiedMessage(index);

      setTimeout(() => {
        setCopiedMessage(null);
      }, 1500);
    } catch {
      setError("Could not copy the message.");
    }
  };

  const regenerateAnswer = async () => {
    if (!lastMessage || isLoading) {
      return;
    }

    await sendMessage(lastMessage);
  };

  const readMessage = (content: string) => {
    if (!content.trim()) {
      return;
    }

    if (!("speechSynthesis" in window)) {
      setError(
        "Speech is not supported in this browser."
      );
      return;
    }

    window.speechSynthesis.cancel();

    const speak = () => {
      const utterance =
        new SpeechSynthesisUtterance(content);

      utterance.lang = "ar-SA";
      utterance.rate = 0.9;
      utterance.pitch = 1;
      utterance.volume = 1;

      const voices =
        window.speechSynthesis.getVoices();

      const arabicVoice =
        voices.find((voice) =>
          voice.lang
            .toLowerCase()
            .startsWith("ar")
        ) ||
        voices.find((voice) =>
          voice.name
            .toLowerCase()
            .includes("arabic")
        );

      if (arabicVoice) {
        utterance.voice = arabicVoice;
      }

      window.speechSynthesis.speak(
        utterance
      );
    };

    const voices =
      window.speechSynthesis.getVoices();

    if (voices.length > 0) {
      speak();
    } else {
      window.speechSynthesis.onvoiceschanged =
        () => {
          speak();
          window.speechSynthesis.onvoiceschanged =
            null;
        };

      setTimeout(() => {
        if (!window.speechSynthesis.speaking) {
          speak();
        }
      }, 300);
    }
  };

  const handleFeedback = (
    index: number,
    feedback: "like" | "dislike"
  ) => {
    setMessages((currentMessages) =>
      currentMessages.map((msg, i) =>
        i === index
          ? { ...msg, liked: feedback }
          : msg
      )
    );
  };

  const filteredMessages = messages
    .map((msg, index) => ({
      message: msg,
      originalIndex: index,
    }))
    .filter(({ message: msg }) =>
      msg.content
        .toLowerCase()
        .includes(searchQuery.toLowerCase())
    );

  return (
    <div
      className={
        darkMode ? "app dark-mode" : "app"
      }
    >
      <div className="chat-container">
        <header className="chat-header">
          <button
            className="theme-btn"
            onClick={() =>
              setDarkMode(
                (current) => !current
              )
            }
          >
            {darkMode ? "☀️" : "🌙"}
          </button>

          <div>
            <h1>Smart Assistant</h1>
            <p>How can I help you today?</p>
          </div>

          <button
            className="clear-btn"
            onClick={clearChat}
            disabled={
              isLoading ||
              messages.length === 0
            }
          >
            Clear
          </button>
        </header>

        {messages.length > 0 && (
          <div className="search-area">
            <input
              type="text"
              placeholder="Search in chat..."
              value={searchQuery}
              onChange={(e) =>
                setSearchQuery(e.target.value)
              }
            />
          </div>
        )}

        <main className="chat-messages">
          {messages.length === 0 && !error ? (
            <div className="empty-state">
              <div className="empty-icon">
                ✨
              </div>

              <h2>
                Welcome to Smart Assistant
              </h2>

              <p>
                Start a conversation by
                sending a message.
              </p>
            </div>
          ) : (
            filteredMessages.map(
              ({
                message: msg,
                originalIndex,
              }) => (
                <div
                  key={originalIndex}
                  className={`message ${
                    msg.role === "user"
                      ? "user-message"
                      : "assistant-message"
                  }`}
                >
                  <div>{msg.content}</div>

                  {msg.role ===
                    "assistant" && (
                    <>
                      <div className="message-actions">
                        <button
                          className={`action-btn ${
                            copiedMessage ===
                            originalIndex
                              ? "copied-btn"
                              : ""
                          }`}
                          onClick={() =>
                            copyMessage(
                              msg.content,
                              originalIndex
                            )
                          }
                        >
                          {copiedMessage ===
                          originalIndex
                            ? "✓ Copied"
                            : "📋 Copy"}
                        </button>

                        <button
                          className="action-btn"
                          onClick={() =>
                            readMessage(
                              msg.content
                            )
                          }
                          disabled={!msg.content}
                        >
                          🔊 Read
                        </button>

                        <button
                          className={`action-btn ${
                            msg.liked ===
                            "like"
                              ? "active-feedback"
                              : ""
                          }`}
                          onClick={() =>
                            handleFeedback(
                              originalIndex,
                              "like"
                            )
                          }
                        >
                          👍
                        </button>

                        <button
                          className={`action-btn ${
                            msg.liked ===
                            "dislike"
                              ? "active-feedback"
                              : ""
                          }`}
                          onClick={() =>
                            handleFeedback(
                              originalIndex,
                              "dislike"
                            )
                          }
                        >
                          👎
                        </button>

                        {originalIndex ===
                          messages.length -
                            1 && (
                          <button
                            className="action-btn"
                            onClick={
                              regenerateAnswer
                            }
                            disabled={isLoading}
                          >
                            🔄 Regenerate
                          </button>
                        )}
                      </div>

                      {msg.source && (
  <div className="response-meta">
    <span>
      Source: {msg.source}
    </span>

    <span>
      Route: {msg.route}
    </span>

    {msg.route === "calculator" && (
      <span>
        Tool: Calculator
      </span>
    )}

    {msg.route === "cv_extraction" && (
      <span>
        Tool: CV Extraction
      </span>
    )}

    {msg.route === "rag" && (
      <span>
        Tool: RAG
      </span>
    )}

    {msg.route === "db_direct" && (
      <span>
        Tool: PostgreSQL
      </span>
    )}

    {msg.route === "llm" && (
      <span>
        Tool: LLM
      </span>
    )}

    {msg.responseTime !== undefined && (
      <span>
        Response time: {msg.responseTime}s
      </span>
    )}
  </div>
)}
                    </>
                  )}
                </div>
              )
            )
          )}

          {recommendation && (
            <div className="recommendation-box">
              <strong>
                💡 Recommendation
              </strong>

              <p>{recommendation}</p>
            </div>
          )}

          {isLoading && (
            <div className="message assistant-message loading-indicator">
              Thinking...
            </div>
          )}

          {error && (
            <div className="error-banner">
              <span>{error}</span>

              <button
                onClick={() =>
                  sendMessage(lastMessage)
                }
                disabled={
                  isLoading ||
                  !lastMessage
                }
              >
                Retry
              </button>
            </div>
          )}

          <div ref={messagesEndRef} />
        </main>

        {/* =========================
            CV UPLOAD AREA
        ========================== */}

        <div className="cv-upload-area">
          <input
            ref={cvInputRef}
            type="file"
            accept=".pdf,application/pdf"
            onChange={handleCvSelection}
            disabled={
              isLoading ||
              isUploadingCv
            }
          />

          {selectedCv && (
            <button
              type="button"
              onClick={uploadCv}
              disabled={isUploadingCv}
            >
              {isUploadingCv
                ? "Uploading..."
                : "Upload CV"}
            </button>
          )}

          {uploadedCvName && (
            <span>
              CV: {uploadedCvName}
            </span>
          )}
        </div>

        <div className="chat-input-area">
          <input
            type="text"
            placeholder="Type your message..."
            value={message}
            disabled={isLoading}
            onChange={(e) =>
              setMessage(e.target.value)
            }
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                sendMessage();
              }
            }}
          />

          <button
            className="send-btn"
            onClick={() => sendMessage()}
            disabled={
              isLoading ||
              !message.trim()
            }
          >
            {isLoading ? "..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}