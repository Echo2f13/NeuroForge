'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { ChatMessage } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { CitationList } from '@/components/citations';

interface ChatInterfaceProps {
  messages: ChatMessage[];
  onSendMessage: (message: string) => void;
  onReset?: () => void;
  isLoading?: boolean;
  subjectId?: string;
  placeholder?: string;
}

export function ChatInterface({
  messages,
  onSendMessage,
  onReset,
  isLoading = false,
  subjectId,
  placeholder = "Ask a question about your study material...",
}: ChatInterfaceProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 150)}px`;
    }
  }, [input]);

  const handleSubmit = useCallback((e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isLoading) return;
    onSendMessage(input.trim());
    setInput('');
  }, [input, isLoading, onSendMessage]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }, [handleSubmit]);

  // Suggested prompts
  const suggestedPrompts = [
    "Explain the main concepts",
    "Give me a summary",
    "What are the key points?",
    "How does this relate to...",
  ];

  return (
    <Card className="h-[600px] flex flex-col" padding="none">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
        <div className="flex items-center gap-3">
          <span className="text-2xl">💬</span>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white">AI Tutor</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">Ask questions about your study material</p>
          </div>
        </div>
        {onReset && messages.length > 0 && (
          <Button variant="ghost" size="sm" onClick={onReset}>
            Clear chat
          </Button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center">
            <EmptyState
              icon={EmptyState.icons.chat}
              title="Start a conversation"
              description="Ask questions about your uploaded study materials"
              variant="compact"
            />
            
            {/* Suggested prompts */}
            <div className="mt-6 w-full max-w-md">
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-3 text-center">Try asking:</p>
              <div className="grid grid-cols-2 gap-2">
                {suggestedPrompts.map((prompt, i) => (
                  <button
                    key={i}
                    onClick={() => setInput(prompt)}
                    className="p-3 text-sm text-left text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded-xl hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, idx) => (
              <MessageBubble 
                key={idx} 
                message={msg} 
                subjectId={subjectId}
              />
            ))}
            
            {/* Typing indicator */}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 dark:bg-gray-800 rounded-2xl rounded-bl-md px-4 py-3">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
        <div className="flex gap-3 items-end">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              rows={1}
              disabled={isLoading}
              className="w-full px-4 py-3 pr-12 border border-gray-200 dark:border-gray-700 rounded-xl
                         bg-white dark:bg-gray-800 text-gray-900 dark:text-white
                         placeholder:text-gray-400 dark:placeholder:text-gray-500
                         focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 
                         outline-none transition-all duration-200 resize-none
                         disabled:opacity-50"
            />
            <span className="absolute right-3 bottom-3 text-xs text-gray-400">
              {input.length > 0 && `${input.length}/2000`}
            </span>
          </div>
          <Button
            type="submit"
            disabled={!input.trim() || isLoading}
            loading={isLoading}
            icon={
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            }
          >
            Send
          </Button>
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">
          Press Enter to send, Shift+Enter for new line
        </p>
      </form>
    </Card>
  );
}

// Message bubble component
function MessageBubble({ 
  message, 
  subjectId 
}: { 
  message: ChatMessage; 
  subjectId?: string;
}) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`
        max-w-[85%] rounded-2xl px-4 py-3
        ${isUser 
          ? 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-br-md' 
          : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white rounded-bl-md'
        }
      `}>
        <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        
        {/* Citation warning */}
        {!isUser && message.citationWarning && (
          <div className="mt-2 pt-2 border-t border-gray-200/30 dark:border-gray-700/30">
            <p className="text-xs text-yellow-600 dark:text-yellow-400 flex items-center gap-1">
              ⚠️ {message.citationWarning}
            </p>
          </div>
        )}
        
        {/* Citations */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-200/50 dark:border-gray-700/50">
            <CitationList 
              citations={message.citations}
              title=""
              collapsible={true}
              defaultCollapsed={false}
              compact={true}
              subjectId={subjectId}
            />
          </div>
        )}
        
        {/* Source count (fallback when no citations) */}
        {!isUser && message.sources && message.sources.length > 0 && !message.citations && (
          <div className="mt-2 pt-2 border-t border-gray-200/30 dark:border-gray-700/30">
            <p className="text-xs opacity-70 flex items-center gap-1">
              {message.isGrounded ? '✅' : '⚠️'} {message.sources.length} sources
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
