import React, { useEffect, useState } from 'react';
import axios from 'axios';
import UploadForm from './components/UploadForm';

function App(){
  const [user, setUser] = useState(null);

  const fetchUser = async () => {
    try {
      const resp = await axios.get('/api/auth/user/');
      if (resp.data && resp.data.authenticated) {
        setUser(resp.data);
      } else {
        setUser(null);
      }
    } catch (e) {
      setUser(null);
    }
  };

  useEffect(() => {
    fetchUser();
  }, []);

  const handleGoogleLogin = () => {
    window.location.href = 'http://localhost:8000/accounts/google/login/?process=login';
  };

  const handleGoogleLogout = async () => {
    try {
      await axios.post('/api/auth/logout/');
    } catch (e) {
      console.warn('logout failed', e);
    }
    localStorage.removeItem('print-kiosk-upload-form');
    setUser(null);
    window.location.href = 'http://localhost:3001/';
  };

  return (
    <div style={{padding:20}}>
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:20}}>
        <h1 style={{margin:0}}>Print Kiosk - Demo</h1>
        {user ? (
          <div style={{display:'flex', alignItems:'center', gap:12}}>
            <span>Hi, {user.full_name || user.email}</span>
            <button type="button" onClick={handleGoogleLogout}>Logout</button>
          </div>
        ) : (
          <button type="button" onClick={handleGoogleLogin}>Login with Google</button>
        )}
      </div>
      <UploadForm isAuthenticated={Boolean(user)} />
    </div>
  )
}

export default App;
