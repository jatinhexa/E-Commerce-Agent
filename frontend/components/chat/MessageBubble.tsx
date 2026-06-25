import React from 'react';
import styles from './chatComponents.module.css';
import { Message } from './ChatWindow';

export default function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';
  
  return (
    <div className={`${styles.messageWrapper} ${isUser ? styles.user : styles.assistant}`}>
      <div className={`${styles.bubble} ${isUser ? styles.user : styles.assistant}`}>
        <p style={{ whiteSpace: 'pre-wrap' }}>{message.content}</p>
        {message.uiContent && (
          <div style={{ marginTop: '1rem' }}>
            {message.uiContent}
          </div>
        )}
      </div>
    </div>
  );
}
