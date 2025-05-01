// Simple React Admin Bundle
// Place this in src/catalog/static/js/admin-bundle.js

// Load React and ReactDOM from CDN
const loadScript = (src) => {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  };
  
  // First load React dependencies
  Promise.all([
    loadScript('https://cdnjs.cloudflare.com/ajax/libs/react/18.2.0/umd/react.development.js'),
    loadScript('https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.2.0/umd/react-dom.development.js'),
    loadScript('https://cdnjs.cloudflare.com/ajax/libs/react-router-dom/6.10.0/react-router-dom.production.min.js'),
    loadScript('https://cdnjs.cloudflare.com/ajax/libs/axios/1.3.5/axios.min.js'),
    loadScript('https://cdnjs.cloudflare.com/ajax/libs/mui/3.7.1/js/mui.min.js'),
    loadScript('https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js')
  ]).then(() => {
    // Simple admin page to test rendering
    const AdminApp = () => {
      const [metrics, setMetrics] = React.useState(null);
      const [loading, setLoading] = React.useState(true);
      const [error, setError] = React.useState(null);
  
      React.useEffect(() => {
        // Test API connection
        axios.get('/api/admin/quality-metrics')
          .then(response => {
            setMetrics(response.data.data);
            setLoading(false);
          })
          .catch(err => {
            console.error('Error fetching metrics:', err);
            setError('Failed to load quality metrics');
            setLoading(false);
          });
      }, []);
  
      if (loading) return React.createElement('div', {}, 'Loading...');
      if (error) return React.createElement('div', { style: { color: 'red' } }, error);
  
      return React.createElement('div', {}, [
        React.createElement('h1', { key: 'title' }, 'Admin Dashboard'),
        React.createElement('div', { key: 'metrics' }, 
          metrics ? `Loaded ${Object.keys(metrics).length} metrics` : 'No metrics available'
        ),
        React.createElement('pre', { key: 'data' }, 
          JSON.stringify(metrics, null, 2)
        )
      ]);
    };
  
    // Render the app
    const root = ReactDOM.createRoot(document.getElementById('root'));
    root.render(React.createElement(AdminApp));
    
    console.log('Admin bundle loaded successfully');
  });