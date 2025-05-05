// Minimal admin dashboard with enhanced debugging
document.addEventListener('DOMContentLoaded', function() {
  console.log('Admin dashboard script loaded');
  
  // Get the root element
  const root = document.getElementById('root');
  
  // Show status in the dashboard body
  function updateStatus(message, isError = false) {
    console.log(message);
    const statusDiv = document.getElementById('statusMessages') || document.createElement('div');
    statusDiv.id = 'statusMessages';
    statusDiv.className = 'alert ' + (isError ? 'alert-danger' : 'alert-info');
    statusDiv.innerHTML = message;
    
    // Add to beginning if not already in DOM
    if (!document.getElementById('statusMessages')) {
      root.prepend(statusDiv);
    }
  }
  
  // Show a loading indicator
  root.innerHTML = `
    <div class="container mt-4">
      <h2>Document Processing Dashboard</h2>
      <div class="alert alert-info">Loading dashboard data...</div>
      
      <div class="card mt-4">
        <div class="card-body">
          <h5 class="card-title">Debug Panel</h5>
          <button id="manualFetchBtn" class="btn btn-primary">Manually Fetch Data</button>
          <button id="generateBtn" class="btn btn-success ms-2">Generate Scorecards</button>
        </div>
      </div>
    </div>
  `;
  
  // Add debug button handlers
  document.getElementById('manualFetchBtn').addEventListener('click', fetchDashboardData);
  document.getElementById('generateBtn').addEventListener('click', generateScorecards);
  
  // Main function to fetch dashboard data
  function fetchDashboardData() {
    updateStatus('Fetching data from API...', false);
    
    // Log the URL we're fetching
    const apiUrl = '/api/admin/quality-metrics';
    console.log('Fetching from URL:', apiUrl);
    
    // Get CSRF token
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
    console.log('CSRF Token available:', !!csrfToken);
    
    // Fetch with debug information
    fetch(apiUrl, {
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json',
        'X-CSRFToken': csrfToken || ''
      }
    })
    .then(response => {
      console.log('Response status:', response.status);
      console.log('Response headers:', [...response.headers.entries()]);
      
      if (!response.ok) {
        throw new Error(`API request failed with status ${response.status}`);
      }
      
      return response.text(); // Get raw text first for debugging
    })
    .then(rawText => {
      console.log('Raw response text:', rawText);
      
      // Try parsing as JSON
      try {
        const response = JSON.parse(rawText);
        console.log('Parsed response:', response);
        
        // Extract data from response
        const data = response.data || response;
        
        // Display data
        displayDashboard(data);
        
        updateStatus('Data loaded successfully!', false);
        
      } catch (parseError) {
        console.error('Error parsing JSON:', parseError);
        updateStatus(`Error parsing API response: ${parseError.message}. Raw response: ${rawText.substring(0, 100)}...`, true);
      }
    })
    .catch(error => {
      console.error('Error fetching dashboard data:', error);
      updateStatus(`Error fetching data: ${error.message}`, true);
    });
  }
  
  // Function to display dashboard with data
  function displayDashboard(data) {
    // Build dashboard HTML
    let dashboardHtml = `
      <div class="container mt-4">
        <h2>Document Processing Dashboard</h2>
        <div id="statusMessages" class="alert alert-success">Dashboard data loaded successfully</div>
        
        <div class="row mt-4">
          <!-- KPI Cards -->
          <div class="col-md-4 mb-3">
            <div class="card">
              <div class="card-body text-center">
                <h5 class="card-title">Total Documents</h5>
                <p class="display-4">${data.total_documents || 0}</p>
              </div>
            </div>
          </div>
          
          <div class="col-md-4 mb-3">
            <div class="card">
              <div class="card-body text-center">
                <h5 class="card-title">Average Score</h5>
                <p class="display-4">${(data.average_scores && data.average_scores.total) ? data.average_scores.total.toFixed(1) : '0.0'}</p>
              </div>
            </div>
          </div>
          
          <div class="col-md-4 mb-3">
            <div class="card">
              <div class="card-body text-center">
                <h5 class="card-title">Documents for Review</h5>
                <p class="display-4">${(data.review_metrics && data.review_metrics.requires_review_count) || 0}</p>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Dashboard Controls -->
        <div class="card mt-4">
          <div class="card-body">
            <h5 class="card-title">Dashboard Controls</h5>
            <button id="refreshBtn" class="btn btn-primary">Refresh Data</button>
            <button id="scorecardsBtn" class="btn btn-success ms-2">Generate Scorecards</button>
          </div>
        </div>
        
        <!-- API Data -->
        <div class="card mt-4">
          <div class="card-body">
            <h5 class="card-title">API Data</h5>
            <pre class="bg-light p-3">${JSON.stringify(data, null, 2)}</pre>
          </div>
        </div>
      </div>
    `;
    
    // Update the root element
    root.innerHTML = dashboardHtml;
    
    // Re-attach event handlers
    document.getElementById('refreshBtn').addEventListener('click', fetchDashboardData);
    document.getElementById('scorecardsBtn').addEventListener('click', generateScorecards);
  }
  
  // Function to generate scorecards
  function generateScorecards() {
    updateStatus('Generating scorecards...', false);
    
    // Get CSRF token
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
    
    // Call API to generate scorecards
    fetch('/api/admin/generate-scorecards', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': csrfToken || ''
      }
    })
    .then(response => {
      console.log('Generate scorecards response status:', response.status);
      
      if (!response.ok) {
        throw new Error(`API request failed with status ${response.status}`);
      }
      
      return response.json();
    })
    .then(data => {
      console.log('Generate scorecards response:', data);
      updateStatus(`Scorecards generation: ${data.message || 'Completed successfully'}`, false);
      
      // Refresh data after a short delay
      setTimeout(fetchDashboardData, 1500);
    })
    .catch(error => {
      console.error('Error generating scorecards:', error);
      updateStatus(`Error generating scorecards: ${error.message}`, true);
    });
  }
  
  // Automatically fetch data on page load
  fetchDashboardData();
});