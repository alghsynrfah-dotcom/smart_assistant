import { useState, useRef, useEffect } from "react";
import "./App.css";

type Message = {
  role: "user" | "assistant";
  content: string;
};

function App() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const sendMessage = async () => {
    if (!message.trim() || isLoading) return;

    const userMessageContent = message;
    setMessage("");
    
    // 1. Add User Message
    const updatedMessages: Message[] = [
      ...messages,
      { role: "user", content: userMessageContent }
    ];
    setMessages(updatedMessages);
    setIsLoading(true);

    try {
      // TODO: هنا رح نستبدل هذا الجزء بربط الـ Backend أو الـ Streaming API الفعلي
      // محاكاة لرد الـ Assistant بعد ثانية ونص
      setTimeout(() => {
        setMessages([
          ...updatedMessages,
          { role: "assistant", content: هذا رد تجريبي على رسالتك: "${userMessageContent}" }
        ]);
        setIsLoading(false);
      }, 1500);

    } catch (error) {
      console.error("Error sending message:", error);
      setIsLoading(false);
      // Error State handling can be added here
    }
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
            onClick={() => setMessages([])}
          >
            Clear
          </button>
        </header>

        <main className="chat-messages">
          {messages.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">✨</div>
              <h2>Welcome to Smart Assistant</h2>
              <p>Start a conversation by sending a message.</p>
            </div>
          ) : (
            messages.map((msg, index) => (
              <div
                key={index}
                className={`message ${msg.role === "user" ? "user-message" : "assistant-message"}`}
              >
                {msg.content}
              </div>
            ))
          )}

          {/* Loading State / Typing Indicator */}
          {isLoading && (
            <div className="message assistant-message loading-indicator">
              <span>.</span><span>.</span><span>.</span> جاري الكتابة
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
              if (e.key === "Enter" && !isLoading) {
                sendMessage();
              }
            }}
          />

          <button 
            className="send-btn" 
            onClick={sendMessage}
            disabled={isLoading || !message.trim()}
          >
            {isLoading ? "Sending..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;