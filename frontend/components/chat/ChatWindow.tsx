'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';
import styles from './chatComponents.module.css';
import MessageBubble from './MessageBubble';
import QuickActions from './QuickActions';

export type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  uiContent?: any;
};

export default function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([
    { id: '1', role: 'assistant', content: 'Hi there! 👋 I am your E-Commerce Assistant. How can I help you today?' }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim()) return;

    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_AGENT_API_URL || 'http://localhost:8003/api'}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: 'default-session', message: input })
      });

      if (!response.body) throw new Error('No response body');
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      let isDone = false;
      let finalResponse = "";
      const toolData: any[] = [];
      let pendingToolId = Date.now();
      
      while (!isDone) {
        const { value, done } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        
        let currentEvent = '';
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.substring(7).trim();
          } else if (line.startsWith('data: ')) {
            const dataStr = line.substring(6);
            if (dataStr === '{}' && currentEvent === 'done') {
               isDone = true;
               break;
            }
            try {
              const data = JSON.parse(dataStr);
              if (currentEvent === 'tool_result') {
                 toolData.push(data);
                 
                 // Update UI dynamically as soon as a tool result arrives
                 const lastTool = data;
                 if (lastTool.tool === 'generate_moodboard' && lastTool.result.products) {
                   import('./MoodBoardGrid').then(({ default: MoodBoardGrid }) => {
                     const items = lastTool.result.products.map((p: any) => ({
                       id: p.handle, imageUrl: p.images[0] || '', link: p.product_url
                     }));
                     setMessages(prev => {
                       const newMsgs = [...prev];
                       if (newMsgs[newMsgs.length - 1].role !== 'assistant') {
                         newMsgs.push({ id: (++pendingToolId).toString(), role: 'assistant', content: '', uiContent: <MoodBoardGrid items={items} /> });
                       } else {
                         newMsgs[newMsgs.length - 1].uiContent = <MoodBoardGrid items={items} />;
                       }
                       return newMsgs;
                     });
                   });
                 } else if ((lastTool.tool === 'search_products' || lastTool.tool === 'get_recommendations') && lastTool.result.length > 0) {
                   import('./ProductCard').then(({ default: ProductCard }) => {
                     setMessages(prev => {
                       const newMsgs = [...prev];
                       const ui = (
                         <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '1rem', marginTop: '1rem' }}>
                           {lastTool.result.map((p: any) => (
                             <ProductCard key={p.handle} product={{ id: p.handle, title: p.title, price: `${p.min_price} ${p.currency}`, imageUrl: p.images[0] || '', link: p.product_url }} />
                           ))}
                         </div>
                       );
                       if (newMsgs[newMsgs.length - 1].role !== 'assistant') {
                         newMsgs.push({ id: (++pendingToolId).toString(), role: 'assistant', content: '', uiContent: ui });
                       } else {
                         newMsgs[newMsgs.length - 1].uiContent = ui;
                       }
                       return newMsgs;
                     });
                   });
                 } else if (lastTool.tool === 'track_order' && !lastTool.result.error) {
                   import('./OrderStatusCard').then(({ default: OrderStatusCard }) => {
                     setMessages(prev => {
                       const newMsgs = [...prev];
                       const ui = <OrderStatusCard order={{
                           orderNumber: lastTool.result.order_number,
                           status: lastTool.result.fulfillment_status?.toLowerCase() || 'processing',
                           trackingUrl: lastTool.result.fulfillments?.[0]?.tracking_url,
                           items: lastTool.result.line_items || []
                         }} />;
                       if (newMsgs[newMsgs.length - 1].role !== 'assistant') {
                         newMsgs.push({ id: (++pendingToolId).toString(), role: 'assistant', content: '', uiContent: ui });
                       } else {
                         newMsgs[newMsgs.length - 1].uiContent = ui;
                       }
                       return newMsgs;
                     });
                   });
                 } else if (lastTool.tool === 'create_ticket' && !lastTool.result.error) {
                    import('./TicketCard').then(({ default: TicketCard }) => {
                     setMessages(prev => {
                       const newMsgs = [...prev];
                       const ui = <TicketCard ticket={{ ticketId: lastTool.result.ticket_id, subject: lastTool.input.subject, status: lastTool.result.status }} />;
                       if (newMsgs[newMsgs.length - 1].role !== 'assistant') {
                         newMsgs.push({ id: (++pendingToolId).toString(), role: 'assistant', content: '', uiContent: ui });
                       } else {
                         newMsgs[newMsgs.length - 1].uiContent = ui;
                       }
                       return newMsgs;
                     });
                   });
                 }
              } else if (currentEvent === 'text') {
                 finalResponse += data.content;
              } else if (currentEvent === 'status') {
                 // Could update typing indicator text here if desired
              }
            } catch (e) {}
          }
        }
      }

      setMessages(prev => {
        const newMsgs = [...prev];
        if (newMsgs[newMsgs.length - 1].role === 'assistant') {
           newMsgs[newMsgs.length - 1].content = finalResponse;
        } else {
           newMsgs.push({ id: (Date.now() + 1).toString(), role: 'assistant', content: finalResponse });
        }
        return newMsgs;
      });

    } catch (error) {
      console.error(error);
      setMessages(prev => [...prev, { id: Date.now().toString(), role: 'assistant', content: 'Sorry, I encountered an error communicating with the server.' }]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleQuickAction = (text: string) => {
    setInput(text);
  };

  return (
    <div className={styles.chatContainer}>
      <div className={styles.messageList}>
        {messages.map(msg => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isTyping && (
          <div className={`${styles.messageWrapper} ${styles.assistant}`}>
            <div className={`${styles.bubble} ${styles.assistant}`}>
              <div className={styles.typingIndicator}>
                <div className={styles.dot}></div>
                <div className={styles.dot}></div>
                <div className={styles.dot}></div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className={styles.inputArea}>
        {messages.length < 3 && (
           <QuickActions onAction={handleQuickAction} />
        )}
        <form onSubmit={handleSend} className={styles.inputForm}>
          <input
            type="text"
            className={styles.chatInput}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about products, orders, or styling..."
          />
          <button 
            type="submit" 
            className={styles.sendButton}
            disabled={!input.trim() || isTyping}
          >
            {isTyping ? <Loader2 className="animate-spin" size={20} /> : <Send size={20} />}
          </button>
        </form>
      </div>
    </div>
  );
}
