import { useState, useRef, useEffect } from "react";
import "./App.css";

type Message = {
  role: "user" | "assistant";
  content: string;
};

export default function App() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, isLoading, error]);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  const sendMessage = () => {
    if (!message.trim() || isLoading) {
      return;
    }

    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    setError(null);

    const userText = message.trim();
    setMessage("");

    const userMessage: Message = {
      role: "user",
      content: userText,
    };

    const assistantMessage: Message = {
      role: "assistant",
      content: "",
    };

    const newMessages = [...messages, userMessage, assistantMessage];

    setMessages(newMessages);
    setIsLoading(true);

    const botReply =
      "Hello! This is a simulated response. The real API and streaming will be connected when the backend endpoint is available.";

    let currentText = "";
    let i = 0;

    timerRef.current = setInterval(() => {
      if (i < botReply.length) {
        currentText += botReply[i];
        i++;

        setMessages((currentMessages) => {
          const updatedMessages = [...currentMessages];

          updatedMessages[updatedMessages.length - 1] = {
            role: "assistant",
            content: currentText,
          };

          return updatedMessages;
        });
      } else {
        if (timerRef.current) {
          clearInterval(timerRef.current);
          timerRef.current = null;
        }

        setIsLoading(false);
      }
    }, 25);
  };

  const clearChat = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    setMessages([]);
    setError(null);
    setMessage("");
    setIsLoading(false);
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
            disabled={isLoading}
          >
            Clear
          </button>
        </header>

        <main className="chat-messages">
          {messages.length === 0 && !error ? (
            <div className="empty-state">
              <div className="empty-icon">✨</div>

              <h2>Welcome to Smart Assistant</h2>

              <p>Start a conversation by sending a message.</p>
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
                {msg.content}
              </div>
            ))
          )}

          {isLoading && (
            <div className="message assistant-message loading-indicator">
              Typing...
            </div>
          )}

          {error && (
            <div className="error-banner">
              {error}
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
            onClick={sendMessage}
            disabled={isLoading || !message.trim()}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}