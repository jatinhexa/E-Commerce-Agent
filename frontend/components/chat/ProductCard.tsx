import React from 'react';
import styles from './chatComponents.module.css';
import { ExternalLink } from 'lucide-react';

export interface Product {
  id: string;
  title: string;
  price: string;
  imageUrl: string;
  link: string;
}

export default function ProductCard({ product }: { product: Product }) {
  return (
    <a href={product.link} target="_blank" rel="noopener noreferrer" className={styles.productCard}>
      <div className={styles.productImageWrapper}>
        <img src={product.imageUrl} alt={product.title} className={styles.productImage} />
      </div>
      <div className={styles.productInfo}>
        <h3 className={styles.productTitle}>{product.title}</h3>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'auto' }}>
          <span className={styles.productPrice}>{product.price}</span>
          <ExternalLink size={16} color="var(--brand-400)" />
        </div>
      </div>
    </a>
  );
}
