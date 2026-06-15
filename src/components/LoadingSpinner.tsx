import React from 'react';

const LoadingSpinner: React.FC<{ message?: string }> = ({ message = 'Loading…' }) => (
  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: 200, color: '#aaa', gap: 12 }}>
    <div style={{ width: 36, height: 36, border: '3px solid #333', borderTop: '3px solid #4f8ef7', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
    <p style={{ fontSize: 14, margin: 0 }}>{message}</p>
    <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
  </div>
);

export default LoadingSpinner;
