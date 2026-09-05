import React, { useEffect, useState } from 'react';
import axios from 'axios';
import UploadForm from './components/UploadForm';
import './App.css';

function App(){
  const [user, setUser] = useState(null);
  const [orders, setOrders] = useState([]);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [isLoadingUser, setIsLoadingUser] = useState(true);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const authRequestId = React.useRef(0);

  const fetchUser = async () => {
    const requestId = ++authRequestId.current;
    try {
      const resp = await axios.get('/api/auth/user/');
      if (requestId !== authRequestId.current) return;
      if (resp.data && resp.data.authenticated) {
        setUser(resp.data);
      } else {
        setUser(null);
      }
    } catch (e) {
      if (requestId !== authRequestId.current) return;
      setUser(null);
    } finally {
      if (requestId === authRequestId.current) {
        setIsLoadingUser(false);
      }
    }
  };

  useEffect(() => {
    fetchUser();
  }, []);

  const fetchOrderHistory = async () => {
    if (!user) {
      setOrders([]);
      return;
    }
    setOrdersLoading(true);
    try {
      const resp = await axios.get('/api/orders/history/');
      setOrders(resp.data);
    } catch (error) {
      setOrders([]);
      console.warn('Unable to load order history', error);
    } finally {
      setOrdersLoading(false);
    }
  };

  useEffect(() => {
    fetchOrderHistory();
  }, [user]);

  const handleGoogleLogin = () => {
    window.location.href = 'http://localhost:8000/accounts/google/login/?process=login';
  };

  const handleGoogleLogout = async () => {
    authRequestId.current += 1;
    setIsLoggingOut(true);
    setUser(null);
    try {
      await axios.post('/api/auth/logout/');
    } catch (e) {
      console.warn('logout failed', e);
    }
    localStorage.removeItem('print-kiosk-upload-form');
    setIsLoggingOut(false);
  };

  return (
    <div className="app-shell">
      <div className="app-container">
      <div className="topbar">
        <div>
          <p className="eyebrow">Simple. Secure. Printed.</p>
          <h1 className="brand">Print Kiosk</h1>
        </div>
        {isLoadingUser || isLoggingOut ? (
          <span className="user-area">{isLoggingOut ? 'Logging out...' : 'Loading...'}</span>
        ) : user ? (
          <div className="user-area">
            <span>Hi, {user.full_name || user.email}</span>
            <button type="button" onClick={handleGoogleLogout} disabled={isLoggingOut}>Logout</button>
          </div>
        ) : (
          <button type="button" onClick={handleGoogleLogin}>Login with Google</button>
        )}
      </div>
      <UploadForm
        isAuthenticated={Boolean(user)}
        onOrderUpdated={fetchOrderHistory}
      />
      {user && (
        <section className="history">
          <div className="section-heading">
            <h2>Previous orders</h2>
            <div className="history-actions">
              <span className="eyebrow">Your activity</span>
              <button className="button-secondary button-small" type="button" onClick={fetchOrderHistory} disabled={ordersLoading}>
                {ordersLoading ? 'Refreshing...' : 'Refresh'}
              </button>
            </div>
          </div>
          {ordersLoading ? (
            <p className="empty-state card">Loading orders...</p>
          ) : orders.length === 0 ? (
            <p className="empty-state card">No previous orders yet.</p>
          ) : (
            <div className="order-grid">
              {orders.map((item) => (
                <div className="card order-card" key={item.id}>
                  <div className="order-top">
                    <span className="order-id">Order #{item.id}</span>
                    <span className="badge">{item.status.replace('_', ' ')}</span>
                  </div>
                  <div className="order-detail"><span>Mode</span><strong>{item.color_mode === 'color' ? 'Color' : 'Black & White'}</strong></div>
                  <div className="order-detail"><span>Pages</span><strong>{item.pages_spec}</strong></div>
                  <div className="order-detail"><span>Amount</span><strong>{item.currency} {(item.price_cents / 100).toFixed(2)}</strong></div>
                  <div className="order-detail"><span>Created</span><strong>{new Date(item.created_at).toLocaleDateString()}</strong></div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
      </div>
    </div>
  )
}

export default App;
