import React from 'react';
import styles from './chatComponents.module.css';
import { Package, Truck, CheckCircle } from 'lucide-react';

export interface OrderStatus {
  orderNumber: string;
  status: 'processing' | 'shipped' | 'delivered';
  trackingUrl?: string;
  items: { title: string; quantity: number; imageUrl?: string }[];
}

export default function OrderStatusCard({ order }: { order: OrderStatus }) {
  return (
    <div className={styles.orderCard}>
      <div className={`${styles.bubble} ${styles.assistant}`} style={{ maxWidth: '100%', padding: '1.5rem', background: 'var(--bg-card)' }}>
        <div className={styles.orderHeader}>
          <span className={styles.orderTitle}>Order #{order.orderNumber}</span>
          <span className={`badge ${order.status === 'delivered' ? 'badge-green' : 'badge-blue'}`}>
            {order.status.toUpperCase()}
          </span>
        </div>
        
        <div className={styles.orderSteps}>
          <div className={`${styles.orderStep} ${order.status !== 'processing' ? styles.completed : styles.active}`}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Package size={18} color="var(--brand-400)" />
              <span>Processing</span>
            </div>
          </div>
          <div className={`${styles.orderStep} ${order.status === 'shipped' ? styles.active : (order.status === 'delivered' ? styles.completed : '')}`}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Truck size={18} color={order.status === 'shipped' || order.status === 'delivered' ? "var(--brand-400)" : "var(--gray-500)"} />
              <span>Shipped</span>
            </div>
          </div>
          <div className={`${styles.orderStep} ${order.status === 'delivered' ? styles.active : ''}`}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <CheckCircle size={18} color={order.status === 'delivered' ? "var(--success)" : "var(--gray-500)"} />
              <span>Delivered</span>
            </div>
          </div>
        </div>

        {order.trackingUrl && (
          <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
            <a href={order.trackingUrl} target="_blank" rel="noopener noreferrer" className="btn btn-primary w-full">
              Track Package
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
