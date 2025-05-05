// Admin dashboard with enhanced debugging and fixed number handling
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
  
  // Helper function to safely parse numeric values
  function parseNumeric(value, defaultValue = 0) {
    if (value === undefined || value === null) return defaultValue;
    
    // If it's already a number, return it
    if (typeof value === 'number') return value;
    
    // Try to convert string to number
    if (typeof value === 'string') {
      const parsed = parseFloat(value);
      return isNaN(parsed) ? defaultValue : parsed;
    }
    
    return defaultValue;
  }
  
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
      
      return response.json();
    })
    .then(response => {
      console.log('Parsed response:', response);
      
      // Extract data from response
      const data = response.data || response;
      
      // Convert string numbers to actual numbers throughout the data
      if (data.average_scores) {
        Object.keys(data.average_scores).forEach(key => {
          data.average_scores[key] = parseNumeric(data.average_scores[key]);
        });
      }
      
      if (data.component_scores) {
        Object.keys(data.component_scores).forEach(key => {
          data.component_scores[key] = parseNumeric(data.component_scores[key]);
        });
      }
      
      if (data.success_rates) {
        Object.keys(data.success_rates).forEach(key => {
          data.success_rates[key] = parseNumeric(data.success_rates[key]);
        });
      }
      
      if (data.review_metrics) {
        Object.keys(data.review_metrics).forEach(key => {
          data.review_metrics[key] = parseNumeric(data.review_metrics[key]);
        });
      }
      
      // Display data
      displayDashboard(data);
      
      updateStatus('Data loaded successfully!', false);
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
                <p class="display-4">${typeof data.average_scores?.total === 'number' ? 
                  data.average_scores.total.toFixed(1) : '0.0'}</p>
              </div>
            </div>
          </div>
          
          <div class="col-md-4 mb-3">
            <div class="card">
              <div class="card-body text-center">
                <h5 class="card-title">Documents for Review</h5>
                <p class="display-4">${data.review_metrics?.requires_review_count || 0}</p>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Success Rates -->
        <div class="row mt-4">
          <div class="col-12">
            <div class="card">
              <div class="card-body">
                <h5 class="card-title">Processing Success Rates</h5>
                <div class="row text-center">
                  <div class="col-md-4">
                    <div class="p-3 bg-light rounded">
                      <h6>Batch 1</h6>
                      <div class="progress">
                        <div class="progress-bar bg-success" role="progressbar" 
                          style="width: ${data.success_rates?.batch1 || 0}%" 
                          aria-valuenow="${data.success_rates?.batch1 || 0}" aria-valuemin="0" aria-valuemax="100">
                          ${typeof data.success_rates?.batch1 === 'number' ? 
                            data.success_rates.batch1.toFixed(1) : '0'}%
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="col-md-4">
                    <div class="p-3 bg-light rounded">
                      <h6>Batch 2</h6>
                      <div class="progress">
                        <div class="progress-bar bg-info" role="progressbar" 
                          style="width: ${data.success_rates?.batch2 || 0}%" 
                          aria-valuenow="${data.success_rates?.batch2 || 0}" aria-valuemin="0" aria-valuemax="100">
                          ${typeof data.success_rates?.batch2 === 'number' ? 
                            data.success_rates.batch2.toFixed(1) : '0'}%
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="col-md-4">
                    <div class="p-3 bg-light rounded">
                      <h6>Batch 3</h6>
                      <div class="progress">
                        <div class="progress-bar bg-primary" role="progressbar" 
                          style="width: ${data.success_rates?.batch3 || 0}%" 
                          aria-valuenow="${data.success_rates?.batch3 || 0}" aria-valuemin="0" aria-valuemax="100">
                          ${typeof data.success_rates?.batch3 === 'number' ? 
                            data.success_rates.batch3.toFixed(1) : '0'}%
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
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
            <div class="form-group mt-3">
              <label for="timeRange">Time Range:</label>
              <select id="timeRange" class="form-control" style="max-width: 200px">
                <option value="7">Last 7 Days</option>
                <option value="30" selected>Last 30 Days</option>
                <option value="90">Last 90 Days</option>
                <option value="365">Last Year</option>
              </select>
            </div>
          </div>
        </div>
        
        <!-- Component Scores -->
        <div class="card mt-4">
          <div class="card-body">
            <h5 class="card-title">Component Scores</h5>
            <div class="row">
              ${Object.entries(data.component_scores || {}).map(([key, value]) => `
                <div class="col-md-3 mb-3">
                  <div class="p-3 bg-light rounded">
                    <h6>${key.charAt(0).toUpperCase() + key.slice(1)}</h6>
                    <div class="progress">
                      <div class="progress-bar" role="progressbar" 
                        style="width: ${parseNumeric(value) / 0.2}%" 
                        aria-valuenow="${parseNumeric(value)}" aria-valuemin="0" aria-valuemax="20">
                        ${parseNumeric(value).toFixed(1)}
                      </div>
                    </div>
                  </div>
                </div>
              `).join('')}
            </div>
          </div>
        </div>
        
        <!-- API Data (Debugging) -->
        <div class="card mt-4">
          <div class="card-header d-flex justify-content-between align-items-center">
            <h5 class="mb-0">API Data</h5>
            <button class="btn btn-sm btn-outline-secondary toggle-data">Show/Hide</button>
          </div>
          <div class="card-body api-data-container" style="display: none;">
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
    
    // Add time range handler
    const timeRangeSelect = document.getElementById('timeRange');
    timeRangeSelect.addEventListener('change', function() {
      fetchDashboardDataWithDays(parseInt(this.value, 10));
    });
    
    // Toggle API data visibility
    document.querySelector('.toggle-data').addEventListener('click', function() {
      const container = document.querySelector('.api-data-container');
      container.style.display = container.style.display === 'none' ? 'block' : 'none';
    });
  }
  
  // Fetch with specific days parameter
  function fetchDashboardDataWithDays(days) {
    updateStatus(`Fetching data for last ${days} days...`, false);
    
    const apiUrl = `/api/admin/quality-metrics?days=${days}`;
    console.log('Fetching from URL:', apiUrl);
    
    // Get CSRF token
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
    
    fetch(apiUrl, {
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json',
        'X-CSRFToken': csrfToken || ''
      }
    })
    .then(response => {
      if (!response.ok) {
        throw new Error(`API request failed with status ${response.status}`);
      }
      return response.json();
    })
    .then(response => {
      const data = response.data || response;
      
      // Convert string numbers to actual numbers
      if (data.average_scores) {
        Object.keys(data.average_scores).forEach(key => {
          data.average_scores[key] = parseNumeric(data.average_scores[key]);
        });
      }
      
      if (data.component_scores) {
        Object.keys(data.component_scores).forEach(key => {
          data.component_scores[key] = parseNumeric(data.component_scores[key]);
        });
      }
      
      if (data.success_rates) {
        Object.keys(data.success_rates).forEach(key => {
          data.success_rates[key] = parseNumeric(data.success_rates[key]);
        });
      }
      
      if (data.review_metrics) {
        Object.keys(data.review_metrics).forEach(key => {
          data.review_metrics[key] = parseNumeric(data.review_metrics[key]);
        });
      }
      
      // Display data
      displayDashboard(data);
      
      updateStatus(`Data loaded for last ${days} days`, false);
    })
    .catch(error => {
      console.error('Error fetching dashboard data:', error);
      updateStatus(`Error fetching data: ${error.message}`, true);
    });
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