import React from 'react';
import styles from './chatComponents.module.css';

export interface MoodBoardItem {
  id: string;
  imageUrl: string;
  link: string;
}

export default function MoodBoardGrid({ items }: { items: MoodBoardItem[] }) {
  return (
    <div className={styles.moodBoard}>
      {items.map(item => (
        <a key={item.id} href={item.link} target="_blank" rel="noopener noreferrer" className={styles.moodBoardItem}>
          <img src={item.imageUrl} alt="Moodboard item" className={styles.moodBoardImage} />
        </a>
      ))}
    </div>
  );
}
