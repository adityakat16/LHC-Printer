import React, { useState, useEffect } from 'react';
import axios from 'axios';

const STORAGE_KEY = 'print-kiosk-upload-form';

axios.defaults.withCredentials = true;

axios.interceptors.request.use((config) => {
  const csrfToken = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];

  if (csrfToken) {
    config.headers['X-CSRFToken'] = csrfToken;
  }

  return config;
});

function saveState(order, status, color){
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ order, status, color }));
  } catch (e) {
    console.warn('Unable to save upload form state', e);
  }
}

export default function UploadForm({ isAuthenticated }){
  const [file, setFile] = useState(null);
  const [color, setColor] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}').color || 'bw';
    } catch {
      return 'bw';
    }
  });
  const [status, setStatus] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}').status || 'idle';
    } catch {
      return 'idle';
    }
  });
  const [order, setOrder] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}').order || null;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    saveState(order, status, color);
  }, [order, status, color]);

  const handleFileChange = (e) => {
    const picked = e.target.files && e.target.files[0];
    if (!picked) {
      setFile(null);
      return;
    }

    const isPdf = picked.type === 'application/pdf' || picked.name.toLowerCase().endsWith('.pdf');
    if (!isPdf) {
      setFile(null);
      e.target.value = '';
      alert('Please upload a PDF file only.');
      return;
    }

    setFile(picked);
  };

  const resetOrder = () => {
    setFile(null);
    setOrder(null);
    setStatus('idle');
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      console.warn('Unable to clear form state', e);
    }
  };

  const upload = async () =>{
    if (!isAuthenticated) {
      alert('Please log in with Google before creating an order.');
      return;
    }
    if(!file) return;
    try{
      // Get CSRF cookie from Django
      await axios.get('/api/csrf/');
      setStatus('getting presign');
      const pres = await axios.post('/api/uploads/presign/');
      const file_key = pres.data.file_key;
      setStatus('uploading file');
      if(pres.data.upload_url){
        const uploadUrl = pres.data.upload_url;
        if (uploadUrl.includes('/api/uploads/local/')){
          const form = new FormData();
          form.append('file', file);
          await axios.post(uploadUrl, form, { headers: { 'Content-Type': 'multipart/form-data' } });
        } else {
          await axios.put(uploadUrl, file, {headers:{'Content-Type':'application/pdf'}});
        }
      }
      setStatus('creating order');
      const resp = await axios.post('/api/orders/', {file_key, pages_spec:'all', color_mode: color});
      setOrder(resp.data.order);
      setStatus('order created');

      const payInfo = resp.data.pay_info;
      try{
        const rp = payInfo && payInfo.razorpay;
        const rpOrderId = rp && rp.order_id;
        const keyId = rp && rp.key_id;
        const amountPaise = resp.data.order.price_cents;
        const orderId = resp.data.order.id;

        if(rpOrderId && keyId){
          const scriptUrl = 'https://checkout.razorpay.com/v1/checkout.js';
          await new Promise((resolve, reject) => {
            if(window.Razorpay){
              return resolve();
            }
            const s = document.createElement('script');
            s.src = scriptUrl;
            s.onload = () => resolve();
            s.onerror = () => reject(new Error('Failed to load Razorpay Checkout script'));
            document.body.appendChild(s);
          });

          const options = {
            key: keyId,
            amount: amountPaise,
            currency: 'INR',
            name: 'Print Kiosk',
            description: `Order ${orderId}`,
            order_id: rpOrderId,
            method: 'upi',
            handler: async function(response){
              try{
                const confirmResp = await axios.post('/api/payments/razorpay/confirm/', {
                  order_id: orderId,
                  razorpay_payment_id: response.razorpay_payment_id,
                  razorpay_order_id: response.razorpay_order_id,
                  razorpay_signature: response.razorpay_signature
                });
                if(confirmResp && confirmResp.data && confirmResp.data.order){
                  setOrder(confirmResp.data.order);
                  setStatus(confirmResp.data.order.status || 'paid');
                } else {
                  const o = await axios.get(`/api/orders/${orderId}/`);
                  setOrder(o.data);
                  setStatus(o.data.status || 'paid');
                }
                alert('Payment confirmed');
              }catch(err){
                console.error('Confirm error', err);
                setStatus('payment_failed');
                setOrder((prev) => prev ? { ...prev, status: 'payment_failed' } : prev);
                alert('Payment verification failed');
              }
            },
            modal: {
              ondismiss: function(){
                console.log('Payment popup closed');
                const currentStatus = order && order.status ? order.status : status;
                if (currentStatus !== 'paid' && currentStatus !== 'pending_payment') {
                  setStatus('payment_failed');
                  setOrder((prev) => prev ? { ...prev, status: 'payment_failed' } : prev);
                }
              }
            },
            theme: { color: '#1d4ed8' }
          };

          const rzp = new window.Razorpay(options);
          rzp.open();
        }
      } catch(e){
        console.error('Razorpay flow error', e);
        setStatus('payment_failed');
        setOrder((prev) => prev ? { ...prev, status: 'payment_failed' } : prev);
      }

    }catch(err){
      console.error(err);
      setStatus('payment_failed');
      setOrder((prev) => prev ? { ...prev, status: 'payment_failed' } : prev);
      alert(err.response && err.response.data ? JSON.stringify(err.response.data) : err.message);
    }
  }

  return (
    <div>
      <input type="file" accept="application/pdf" onChange={handleFileChange} />
      <div>
        <label><input type="radio" checked={color==='bw'} onChange={()=>setColor('bw')} /> BW</label>
        <label style={{marginLeft:10}}><input type="radio" checked={color==='color'} onChange={()=>setColor('color')} /> Color</label>
      </div>
      <button onClick={upload}>Upload & Create Order</button>
      <button type="button" onClick={resetOrder} style={{ marginLeft: 8 }}>New Order</button>
      <div>Status: {status}</div>
      {order && <pre>{JSON.stringify(order,null,2)}</pre>}
    </div>

  )
}