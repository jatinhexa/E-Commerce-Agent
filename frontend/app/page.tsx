import Link from "next/link";
import styles from "./page.module.css";

export default function Home() {
  return (
    <div className={styles.page} style={{ background: 'var(--bg)', color: 'var(--text)', minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
      <main className={styles.main} style={{ textAlign: 'center' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1.5rem' }}>
          <h1 style={{ fontSize: '2.5rem', fontWeight: 800 }} className="gradient-text">E-Commerce Agent Platform</h1>
          <p style={{ maxWidth: '500px', color: 'var(--text-muted)' }}>
            Welcome to the AI-powered E-Commerce assistant dashboard.
          </p>
          
          <Link href="/chat" className="btn btn-primary" style={{ padding: '1rem 2rem', fontSize: '1.1rem', marginTop: '1rem' }}>
            Open Chat Interface
          </Link>
        </div>
      </main>
    </div>
  );
}
