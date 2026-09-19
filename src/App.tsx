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
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(content);

    window.speechSynthesis.speak(utterance);
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

  return (
    <div className={`app ${darkMode ? "dark-mode" : ""}`}>
      <div className="chat-container">

        <header className="chat-header">
          <button
            className="theme-btn"
            onClick={() => setDarkMode(!darkMode)}
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

                {msg.role === "assistant" && (
                  <>
                    <div className="message-actions">

                      <button
                        className={`action-btn ${
                          copiedMessage === idx
                            ? "copied-btn"
                            : ""
                        }`}
                        onClick={() =>
                          copyMessage(msg.content, idx)
                        }
                      >
                        {copiedMessage === idx
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
                          handleFeedback(idx, "like")
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
                          handleFeedback(idx, "dislike")
                        }
                      >
                        👎
                      </button>

                      {idx === messages.length - 1 && (
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