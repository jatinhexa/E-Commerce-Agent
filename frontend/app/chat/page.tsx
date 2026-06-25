'use client';
import React, { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, ShoppingBag } from 'lucide-react';
import styles from './chat.module.css';
import ChatWindow from '../../components/chat/ChatWindow';

export default function ChatPage() {
  return (
    <div className={styles.chatPage}>
      <header className={styles.header}>
        <div className={styles.title}>
          <Link href="/" className="btn-icon btn-ghost flex items-center justify-center mr-2">
            <ArrowLeft size={20} />
          </Link>
          <ShoppingBag className="text-brand-400" size={24} />
          <span className="gradient-text">E-Commerce Agent</span>
        </div>
        <div className={styles.headerActions}>
          <button className="btn btn-ghost btn-sm">Settings</button>
          <button className="btn btn-primary btn-sm">New Chat</button>
        </div>
      </header>
      <main className={styles.mainContent}>
        <div className={`${styles.bgBlob} ${styles.blob1}`}></div>
        <div className={`${styles.bgBlob} ${styles.blob2}`}></div>
        <ChatWindow />
      </main>
    </div>
  );
}
