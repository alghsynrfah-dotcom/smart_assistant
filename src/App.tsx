import { useState, useRef, useEffect } from "react";
import "./App.css";

type Message = {
  role: "user" | "assistant";
  content: string;
  route?: string;
  source?: string;
};

type ChatResponse = {
  answer: string;
  route: string;
  source: string;
};

export default function App() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastMessage, setLastMessage] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, isLoading, error]);

  const sendMessage = async (text?: string) => {
    const userText = (text ?? message).trim();

    if (!userText || isLoading) {
      return;
    }

    setError(null);
    setLastMessage(userText);
    setMessage("");
    setIsLoading(true);

    const currentHistory = [...messages];

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
          conversation_history: currentHistory,
        }),
      });

      if (!response.ok) {
        throw new Error("Backend request failed");
      }

      const contentType = response.headers.get("content-type") || "";

      // =========================
      // STREAMING RESPONSE
      // =========================
      if (contentType.includes("text/plain")) {
        if (!response.body) {
          throw new Error("Streaming body is not available");
        }

        const route =
          response.headers.get("X-Route") || "rag";

        const source =
          response.headers.get("X-Source") || "employees.txt";

        // Add empty assistant message first
        setMessages((currentMessages) => [
          ...currentMessages,
          {
            role: "assistant",
            content: "",
            route,
            source,
          },
        ]);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let assistantAnswer = "";

        while (true) {
          const { done, value } = await reader.read();

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

      // =========================
      // NORMAL JSON RESPONSE
      // =========================
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
    setMessages([]);
    setError(null);
    setMessage("");
    setLastMessage("");
  };

  return (
    <div className="app">
      <div className="chat-container">

        <header className="chat-header">
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
            messages.map((msg, idx) => (
              <div
                key={idx}
                className={`message ${
                  msg.role === "user"
                    ? "user-message"
                    : "assistant-message"
                }`}
              >
                <div>{msg.content}</div>

                {msg.role === "assistant" &&
                  msg.source && (
                    <div className="response-meta">
                      <span>
                        Source: {msg.source}
                      </span>

                      <span>
                        Route: {msg.route}
                      </span>
                    </div>
                  )}
              </div>
            ))
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