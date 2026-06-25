import React from 'react';
import styles from './chatComponents.module.css';

interface QuickActionsProps {
  onAction: (text: string) => void;
}

export default function QuickActions({ onAction }: QuickActionsProps) {
  const actions = [
    "Show me winter jackets",
    "Track my order",
    "What's your return policy?",
    "Create an autumn outfit moodboard"
  ];

  return (
    <div className={styles.quickActions}>
      {actions.map((action, idx) => (
        <button 
          key={idx} 
          className={styles.actionChip}
          onClick={() => onAction(action)}
        >
          {action}
        </button>
      ))}
    </div>
  );
}
