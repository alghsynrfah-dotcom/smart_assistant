import { useState, useRef, useEffect } from "react";
import "./App.css";

type Message = {
  role: "user" | "assistant";
  content: string;
  route?: string;
  source?: string;
  liked?: "like" | "dislike";
};

type ChatResponse = {
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

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, isLoading, error]);

  useEffect(() => {
    document.body.style.backgroundColor = darkMode
      ? "#111827"
      : "#f7f7f8";

    return () => {
      document.body.style.backgroundColor = "";
    };
  }, [darkMode]);

  const sendMessage = async (text?: string) => {
    const userText = (text ?? message).trim();

    if (!userText || isLoading) {
      return;
    }

    setError(null);
    setLastMessage(userText);
    setMessage("");
    setIsLoading(true);

    setMessages((currentMessages) => [
      ...currentMessages,
      {
        role: "user",
        content: userText,
      },
    ]);

    try {
      const response = await fetch("http://127.0.0.1:8000/chat", {
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
        }),
      });

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
            source: source || "employees.txt",
          },
        ]);

        while (true) {
          const { value, done } = await reader.read();

          if (done) {
            break;
          }

          const chunk = decoder.decode(value, {
            stream: true,
          });

          assistantAnswer += chunk;

          setMessages((currentMessages) => {
            const updatedMessages = [...currentMessages];
            const lastIndex = updatedMessages.length - 1;

            if (
              lastIndex >= 0 &&
              updatedMessages[lastIndex].role === "assistant"
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

          setMessages((currentMessages) => {
            const updatedMessages = [...currentMessages];
            const lastIndex = updatedMessages.length - 1;

            if (
              lastIndex >= 0 &&
              updatedMessages[lastIndex].role === "assistant"
            ) {
              updatedMessages[lastIndex] = {
                ...updatedMessages[lastIndex],
                content: assistantAnswer,
              };
            }

            return updatedMessages;
          });
        }

        return;
      }

      const data: ChatResponse = await response.json();

      setMessages((currentMessages) => [
        ...currentMessages,
        {
          role: "assistant",
          content: data.answer,
          route: data.route,
          source: data.source,
        },
      ]);
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

    setMessages([]);
    setError(null);
    setMessage("");
    setLastMessage("");
    setCopiedMessage(null);
    setSearchQuery("");
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
      setError("Speech is not supported in this browser.");
      return;
    }

    window.speechSynthesis.cancel();

    const speak = () => {
      const utterance = new SpeechSynthesisUtterance(content);

      utterance.lang = "ar-SA";
      utterance.rate = 0.9;
      utterance.pitch = 1;
      utterance.volume = 1;

      const voices = window.speechSynthesis.getVoices();

      const arabicVoice =
        voices.find((voice) =>
          voice.lang.toLowerCase().startsWith("ar")
        ) ||
        voices.find((voice) =>
          voice.name.toLowerCase().includes("arabic")
        );

      if (arabicVoice) {
        utterance.voice = arabicVoice;
      }

      window.speechSynthesis.speak(utterance);
    };

    const voices = window.speechSynthesis.getVoices();

    if (voices.length > 0) {
      speak();
    } else {
      window.speechSynthesis.onvoiceschanged = () => {
        speak();
        window.speechSynthesis.onvoiceschanged = null;
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
    <div className={darkMode ? "app dark-mode" : "app"}>
      <div className="chat-container">
        <header className="chat-header">
          <button
            className="theme-btn"
            onClick={() =>
              setDarkMode((current) => !current)
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
            disabled={isLoading || messages.length === 0}
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
              <div className="empty-icon">✨</div>

              <h2>Welcome to Smart Assistant</h2>

              <p>
                Start a conversation by sending a message.
              </p>
            </div>
          ) : (
            filteredMessages.map(
              ({ message: msg, originalIndex }) => (
                <div
                  key={originalIndex}
                  className={`message ${
                    msg.role === "user"
                      ? "user-message"
                      : "assistant-message"
                  }`}
                >
                  <div>{msg.content}</div>

                  {msg.role === "assistant" && (
                    <>
                      <div className="message-actions">
                        <button
                          className={`action-btn ${
                            copiedMessage === originalIndex
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
                          {copiedMessage === originalIndex
                            ? "✓ Copied"
                            : "📋 Copy"}
                        </button>

                        <button
                          className="action-btn"
                          onClick={() =>
                            readMessage(msg.content)
                          }
                          disabled={!msg.content}
                        >
                          🔊 Read
                        </button>

                        <button
                          className={`action-btn ${
                            msg.liked === "like"
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
                            msg.liked === "dislike"
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
                          messages.length - 1 && (
                          <button
                            className="action-btn"
                            onClick={regenerateAnswer}
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
                        </div>
                      )}
                    </>
                  )}
                </div>
              )
            )
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
                onClick={() => sendMessage(lastMessage)}
                disabled={isLoading || !lastMessage}
              >
                Retry
              </button>
            </div>
          )}

          <div ref={messagesEndRef} />
        </main>

        <div className="chat-input-area">
          <input
            type="text"
            placeholder="Type your message..."
            value={message}
            disabled={isLoading}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                sendMessage();
              }
            }}
          />

          <button
            className="send-btn"
            onClick={() => sendMessage()}
            disabled={isLoading || !message.trim()}
          >
            {isLoading ? "..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}