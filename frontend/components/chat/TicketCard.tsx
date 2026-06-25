import React from 'react';
import styles from './chatComponents.module.css';
import { Ticket } from 'lucide-react';

export interface TicketData {
  ticketId: string;
  subject: string;
  status: string;
}

export default function TicketCard({ ticket }: { ticket: TicketData }) {
  return (
    <div className={`${styles.bubble} ${styles.assistant}`} style={{ maxWidth: '100%', marginTop: '1rem', padding: '1.25rem', background: 'var(--bg-card)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
        <div style={{ width: '36px', height: '36px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(99,102,241,0.15)', color: 'var(--brand-400)' }}>
          <Ticket size={20} />
        </div>
        <div>
          <div style={{ fontWeight: 700 }}>Support Ticket Created</div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>ID: {ticket.ticketId}</div>
        </div>
      </div>
      <div style={{ fontSize: '0.9rem' }}>
        <p><strong>Subject:</strong> {ticket.subject}</p>
        <p style={{ marginTop: '0.5rem', color: 'var(--text-dim)' }}>Our team will get back to you within 24 hours.</p>
      </div>
    </div>
  );
}
