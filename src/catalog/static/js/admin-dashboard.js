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
  
  // Initialize the dashboard UI with tabs
  function initializeDashboardUI() {
    root.innerHTML = `
      <div class="container mt-4">
        <h2>Document Processing Dashboard</h2>
        <div id="statusMessages" class="alert alert-info">Loading dashboard data...</div>
        
        <ul class="nav nav-tabs mb-4" id="dashboardTabs" role="tablist">
          <li class="nav-item" role="presentation">
            <button class="nav-link active" id="metrics-tab" data-bs-toggle="tab" data-bs-target="#metrics" 
                   type="button" role="tab" aria-controls="metrics" aria-selected="true">
              Metrics
            </button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="feedback-tab" data-bs-toggle="tab" data-bs-target="#feedback" 
                   type="button" role="tab" aria-controls="feedback" aria-selected="false">
              Search Feedback
            </button>
          </li>
        </ul>
        
        <div class="tab-content" id="dashboardTabContent">
          <!-- Metrics Tab -->
          <div class="tab-pane fade show active" id="metrics" role="tabpanel" aria-labelledby="metrics-tab">
            <div class="card mb-4">
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
            
            <div id="metricsContent">
              <div class="d-flex justify-content-center">
                <div class="spinner-border text-primary" role="status">
                  <span class="visually-hidden">Loading...</span>
                </div>
              </div>
            </div>
          </div>
          
          <!-- Search Feedback Tab -->
          <div class="tab-pane fade" id="feedback" role="tabpanel" aria-labelledby="feedback-tab">
            <div id="searchFeedbackContainer">
              <!-- React component will be mounted here -->
              <div class="d-flex justify-content-center">
                <div class="spinner-border text-primary" role="status">
                  <span class="visually-hidden">Loading...</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
    
    // Initialize tab functionality manually
    document.querySelectorAll('.nav-link').forEach(tab => {
      tab.addEventListener('click', function() {
        // Deactivate all tabs
        document.querySelectorAll('.nav-link').forEach(t => 
          t.classList.remove('active'));
        
        // Hide all tab panes
        document.querySelectorAll('.tab-pane').forEach(p => 
          p.classList.remove('show', 'active'));
        
        // Activate clicked tab
        this.classList.add('active');
        
        // Show corresponding tab pane
        const target = document.querySelector(this.getAttribute('data-bs-target'));
        if (target) {
          target.classList.add('show', 'active');
        }
      });
    });
    
    // Add event listeners for buttons
    document.getElementById('refreshBtn').addEventListener('click', fetchDashboardData);
    document.getElementById('scorecardsBtn').addEventListener('click', generateScorecards);
    document.getElementById('timeRange').addEventListener('change', function() {
      fetchDashboardDataWithDays(parseInt(this.value, 10));
    });
  }
  
  // Initialize UI immediately
  initializeDashboardUI();
  
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
  
  // Function to display dashboard with data
  function displayDashboard(data) {
    // Get metrics content container
    const metricsContainer = document.getElementById('metricsContent');
    if (!metricsContainer) {
      console.error('Metrics container not found');
      return;
    }
    
    // Build dashboard HTML
    let dashboardHtml = `
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
    `;
    
    // Update the container
    metricsContainer.innerHTML = dashboardHtml;
    
    // Add event listener for toggle button
    document.querySelector('.toggle-data')?.addEventListener('click', function() {
      const container = document.querySelector('.api-data-container');
      if (container) {
        container.style.display = container.style.display === 'none' ? 'block' : 'none';
      }
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
  
  // Initialize the React search feedback component
  function initializeSearchFeedbackComponent() {
    // Check if React and ReactDOM are available
    if (typeof React === 'undefined' || typeof ReactDOM === 'undefined') {
      console.error('React or ReactDOM not available');
      const container = document.getElementById('searchFeedbackContainer');
      if (container) {
        container.innerHTML = `
          <div class="alert alert-danger">
            <strong>Error:</strong> React libraries are not loaded properly.
            Check console for more details.
          </div>
        `;
      }
      return;
    }
    
    try {
      // Create a React div element
      const reactDiv = document.createElement('div');
      reactDiv.id = 'reactFeedbackRoot';
      
      // Add it to the container
      const container = document.getElementById('searchFeedbackContainer');
      if (container) {
        container.innerHTML = '';
        container.appendChild(reactDiv);
        
        // Render the SearchFeedbackDashboard component
        const SearchFeedbackDashboard = createSearchFeedbackComponent();
        ReactDOM.render(React.createElement(SearchFeedbackDashboard), reactDiv);
      }
    } catch (error) {
      console.error('Error initializing search feedback component:', error);
      const container = document.getElementById('searchFeedbackContainer');
      if (container) {
        container.innerHTML = `
          <div class="alert alert-danger">
            <strong>Error:</strong> Failed to initialize search feedback component.
            ${error.message}
          </div>
        `;
      }
    }
  }
  
  // Create the SearchFeedbackDashboard component
  function createSearchFeedbackComponent() {
    // This is where you would import the component in a proper React app
    // For now, defining it inline
    return function SearchFeedbackDashboard() {
      // React hooks
      const [feedbackData, setFeedbackData] = React.useState([]);
      const [loading, setLoading] = React.useState(true);
      const [error, setError] = React.useState(null);
      const [pagination, setPagination] = React.useState({
        page: 1,
        per_page: 10,
        total: 0,
        pages: 0
      });
      
      // Filter state
      const [filters, setFilters] = React.useState({
        type: '',
        startDate: '',
        endDate: ''
      });
      
      // Statistics state
      const [distribution, setDistribution] = React.useState({});
      
      // Load feedback data
      const loadFeedbackData = React.useCallback(async () => {
        setLoading(true);
        
        try {
          // Build the URL with query parameters
          const url = new URL('/api/admin/feedback', window.location.origin);
          url.searchParams.append('page', pagination.page);
          url.searchParams.append('per_page', pagination.per_page);
          
          // Add filters if they exist
          if (filters.type) url.searchParams.append('type', filters.type);
          if (filters.startDate) url.searchParams.append('start_date', filters.startDate);
          if (filters.endDate) url.searchParams.append('end_date', filters.endDate);
          
          // Get CSRF token
          const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
          
          // Fetch data
          const response = await fetch(url, {
            headers: {
              'X-Requested-With': 'XMLHttpRequest',
              'Accept': 'application/json',
              'X-CSRFToken': csrfToken || ''
            }
          });
          
          if (!response.ok) {
            throw new Error(`API request failed with status ${response.status}`);
          }
          
          const data = await response.json();
          
          if (data.success) {
            setFeedbackData(data.data.feedback);
            setPagination(data.data.pagination);
            setDistribution(data.data.distribution || {});
          } else {
            setError(data.error || 'Failed to load feedback data');
          }
        } catch (err) {
          setError(`Error loading feedback data: ${err.message}`);
          console.error('Error loading feedback data:', err);
        } finally {
          setLoading(false);
        }
      }, [pagination.page, pagination.per_page, filters]);
      
      // Load data when component mounts or filters/pagination change
      React.useEffect(() => {
        loadFeedbackData();
      }, [loadFeedbackData]);
      
      // Handle filter changes
      const handleFilterChange = (e) => {
        const { name, value } = e.target;
        setFilters(prevFilters => ({
          ...prevFilters,
          [name]: value
        }));
        
        // Reset to page 1 when filters change
        setPagination(prevPagination => ({
          ...prevPagination,
          page: 1
        }));
      };
      
      // Navigate to a specific page
      const goToPage = (page) => {
        setPagination(prevPagination => ({
          ...prevPagination,
          page
        }));
      };
      
      // Render feedback type badge with appropriate color
      const renderFeedbackTypeBadge = (type) => {
        let bgColor = 'bg-gray-100 text-gray-800';
        
        switch (type) {
          case 'relevant':
            bgColor = 'bg-green-100 text-green-800';
            break;
          case 'not_relevant':
            bgColor = 'bg-red-100 text-red-800';
            break;
          case 'other':
            bgColor = 'bg-blue-100 text-blue-800';
            break;
          default:
            break;
        }
        
        return React.createElement(
          'span',
          {
            className: `inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${bgColor}`
          },
          type
        );
      };
      
      // Render distribution chart
      const renderDistributionChart = () => {
        const types = Object.keys(distribution);
        const total = types.reduce((sum, type) => sum + distribution[type], 0);
        
        if (total === 0) {
          return React.createElement('div', { className: 'text-gray-500' }, 'No data available');
        }
        
        return React.createElement(
          'div',
          { className: 'mt-4' },
          types.map(type => {
            const percentage = Math.round((distribution[type] / total) * 100);
            let barColor = 'bg-gray-500';
            
            switch (type) {
              case 'relevant':
                barColor = 'bg-green-500';
                break;
              case 'not_relevant':
                barColor = 'bg-red-500';
                break;
              case 'other':
                barColor = 'bg-blue-500';
                break;
              default:
                break;
            }
            
            return React.createElement(
              'div',
              { key: type, className: 'mb-3' },
              React.createElement(
                'div',
                { className: 'flex items-center justify-between mb-1' },
                React.createElement('span', { className: 'text-sm font-medium text-gray-700' }, type),
                React.createElement(
                  'span',
                  { className: 'text-sm font-medium text-gray-700' },
                  `${distribution[type]} (${percentage}%)`
                )
              ),
              React.createElement(
                'div',
                { className: 'w-full bg-gray-200 rounded-full h-2.5' },
                React.createElement('div', {
                  className: `${barColor} h-2.5 rounded-full`,
                  style: { width: `${percentage}%` }
                })
              )
            );
          })
        );
      };
      
      // Main component render
      return React.createElement(
        'div',
        { className: 'container mx-auto px-4 py-8' },
        [
          // Stats Cards
          React.createElement(
            'div',
            { className: 'grid grid-cols-1 md:grid-cols-3 gap-4 mb-6', key: 'stats-cards' },
            [
              // Total Feedback Card
              React.createElement(
                'div',
                { className: 'bg-white rounded-lg shadow p-4', key: 'total-card' },
                [
                  React.createElement('h2', { className: 'text-lg font-medium mb-2' }, 'Total Feedback'),
                  React.createElement('p', { className: 'text-3xl font-bold' }, pagination.total || 0)
                ]
              ),
              
              // Distribution Card
              React.createElement(
                'div',
                { className: 'bg-white rounded-lg shadow p-4', key: 'distribution-card' },
                [
                  React.createElement('h2', { className: 'text-lg font-medium mb-2' }, 'Feedback Distribution'),
                  renderDistributionChart()
                ]
              ),
              
              // Filters Card
              React.createElement(
                'div',
                { className: 'bg-white rounded-lg shadow p-4', key: 'filters-card' },
                [
                  React.createElement('h2', { className: 'text-lg font-medium mb-2' }, 'Filters'),
                  React.createElement(
                    'div',
                    { className: 'space-y-3' },
                    [
                      // Feedback Type Filter
                      React.createElement(
                        'div',
                        { key: 'type-filter' },
                        [
                          React.createElement(
                            'label',
                            { className: 'block text-sm font-medium text-gray-700 mb-1' },
                            'Feedback Type'
                          ),
                          React.createElement(
                            'select',
                            {
                              name: 'type',
                              value: filters.type,
                              onChange: handleFilterChange,
                              className: 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500'
                            },
                            [
                              React.createElement('option', { value: '' }, 'All Types'),
                              React.createElement('option', { value: 'relevant' }, 'Relevant'),
                              React.createElement('option', { value: 'not_relevant' }, 'Not Relevant'),
                              React.createElement('option', { value: 'other' }, 'Other')
                            ]
                          )
                        ]
                      ),
                      
                      // Start Date Filter
                      React.createElement(
                        'div',
                        { key: 'start-date-filter' },
                        [
                          React.createElement(
                            'label',
                            { className: 'block text-sm font-medium text-gray-700 mb-1' },
                            'Start Date'
                          ),
                          React.createElement(
                            'input',
                            {
                              type: 'date',
                              name: 'startDate',
                              value: filters.startDate,
                              onChange: handleFilterChange,
                              className: 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500'
                            }
                          )
                        ]
                      ),
                      
                      // End Date Filter
                      React.createElement(
                        'div',
                        { key: 'end-date-filter' },
                        [
                          React.createElement(
                            'label',
                            { className: 'block text-sm font-medium text-gray-700 mb-1' },
                            'End Date'
                          ),
                          React.createElement(
                            'input',
                            {
                              type: 'date',
                              name: 'endDate',
                              value: filters.endDate,
                              onChange: handleFilterChange,
                              className: 'w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500'
                            }
                          )
                        ]
                      ),
                      
                      // Clear Filters Button
                      React.createElement(
                        'button',
                        {
                          onClick: () => setFilters({ type: '', startDate: '', endDate: '' }),
                          className: 'px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300'
                        },
                        'Clear Filters'
                      )
                    ]
                  )
                ]
              )
            ]
          ),
          
          // Error Message
          error && React.createElement(
            'div',
            { className: 'bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4', key: 'error' },
            error
          ),
          
          // Loading Indicator
          loading && React.createElement(
            'div',
            { className: 'flex justify-center items-center py-8', key: 'loading' },
            [
              React.createElement('div', {
                className: 'animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500',
                key: 'spinner'
              }),
              React.createElement('span', { className: 'ml-2', key: 'loading-text' }, 'Loading...')
            ]
          ),
          
          // Feedback Table
          !loading && feedbackData.length > 0 && React.createElement(
            'div',
            { className: 'bg-white shadow-md rounded-lg overflow-hidden mb-6', key: 'table-container' },
            React.createElement(
              'table',
              { className: 'min-w-full divide-y divide-gray-200' },
              [
                // Table Header
                React.createElement(
                  'thead',
                  { className: 'bg-gray-50', key: 'thead' },
                  React.createElement(
                    'tr',
                    {},
                    [
                      React.createElement(
                        'th',
                        { className: 'px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider' },
                        'Document'
                      ),
                      React.createElement(
                        'th',
                        { className: 'px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider' },
                        'Search Query'
                      ),
                      React.createElement(
                        'th',
                        { className: 'px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider' },
                        'Feedback Type'
                      ),
                      React.createElement(
                        'th',
                        { className: 'px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider' },
                        'Comment'
                      ),
                      React.createElement(
                        'th',
                        { className: 'px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider' },
                        'Date'
                      )
                    ]
                  )
                ),
                
                // Table Body
                React.createElement(
                  'tbody',
                  { className: 'bg-white divide-y divide-gray-200', key: 'tbody' },
                  feedbackData.map(feedback => React.createElement(
                    'tr',
                    { key: feedback.id, className: 'hover:bg-gray-50' },
                    [
                      // Document Column
                      React.createElement(
                        'td',
                        { className: 'px-6 py-4 whitespace-nowrap', key: `doc-${feedback.id}` },
                        [
                          React.createElement(
                            'div',
                            { className: 'text-sm font-medium text-gray-900' },
                            feedback.filename
                          ),
                          React.createElement(
                            'div',
                            { className: 'text-sm text-gray-500' },
                            `ID: ${feedback.document_id}`
                          )
                        ]
                      ),
                      
                      // Search Query Column
                      React.createElement(
                        'td',
                        { className: 'px-6 py-4', key: `query-${feedback.id}` },
                        React.createElement(
                          'div',
                          { className: 'text-sm text-gray-900' },
                          feedback.search_query || "—"
                        )
                      ),
                      
                      // Feedback Type Column
                      React.createElement(
                        'td',
                        { className: 'px-6 py-4 whitespace-nowrap', key: `type-${feedback.id}` },
                        renderFeedbackTypeBadge(feedback.feedback_type)
                      ),
                      
                      // Comment Column
                      React.createElement(
                        'td',
                        { className: 'px-6 py-4', key: `comment-${feedback.id}` },
                        React.createElement(
                          'div',
                          { className: 'text-sm text-gray-900 max-w-xs break-words' },
                          feedback.user_comment || "—"
                        )
                      ),
                      
                      // Date Column
                      React.createElement(
                        'td',
                        { className: 'px-6 py-4 whitespace-nowrap', key: `date-${feedback.id}` },
                        React.createElement(
                          'div',
                          { className: 'text-sm text-gray-900' },
                          feedback.feedback_date
                        )
                      )
                    ]
                  ))
                )
              ]
            )
          ),
          
          // No Results Message
          !loading && feedbackData.length === 0 && React.createElement(
            'div',
            { className: 'bg-white rounded-lg shadow-md p-8 text-center', key: 'no-results' },
            [
              React.createElement(
                'svg',
                {
                  className: 'mx-auto h-12 w-12 text-gray-400',
                  fill: 'none',
                  stroke: 'currentColor',
                  viewBox: '0 0 24 24',
                  key: 'icon'
                },
                React.createElement(
                  'path',
                  {
                    strokeLinecap: 'round',
                    strokeLinejoin: 'round',
                    strokeWidth: '2',
                    d: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z'
                  }
                )
              ),
              React.createElement(
                'h3',
                { className: 'mt-2 text-sm font-medium text-gray-900' },
                'No feedback found'
              ),
              React.createElement(
                'p',
                { className: 'mt-1 text-sm text-gray-500' },
                'No search feedback matches your criteria.'
              )
            ]
          ),
          
          // Pagination
          pagination.pages > 1 && React.createElement(
            'div',
            { className: 'flex justify-center mt-4', key: 'pagination' },
            React.createElement(
              'nav',
              { className: 'inline-flex rounded-md shadow' },
              [
                // Previous Page Button
                pagination.has_prev && React.createElement(
                  'button',
                  {
                    onClick: () => goToPage(pagination.prev_page),
                    className: 'relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50',
                    key: 'prev'
                  },
                  [
                    React.createElement('span', { className: 'sr-only' }, 'Previous'),
                    React.createElement(
                      'svg',
                      {
                        className: 'h-5 w-5',
                        xmlns: 'http://www.w3.org/2000/svg',
                        viewBox: '0 0 20 20',
                        fill: 'currentColor',
                        'aria-hidden': 'true'
                      },
                      React.createElement(
                        'path',
                        {
                          fillRule: 'evenodd',
                          d: 'M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z',
                          clipRule: 'evenodd'
                        }
                      )
                    )
                  ]
                ),
                
                // Page Numbers
                [...Array(pagination.pages)].map((_, i) => React.createElement(
                  'button',
                  {
                    key: `page-${i + 1}`,
                    onClick: () => goToPage(i + 1),
                    className: `relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium ${
                      i + 1 === pagination.page ? 'text-indigo-600 bg-indigo-50' : 'text-gray-700 hover:bg-gray-50'
                    }`
                  },
                  i + 1
                )),
                
                // Next Page Button
                pagination.has_next && React.createElement(
                  'button',
                  {
                    onClick: () => goToPage(pagination.next_page),
                    className: 'relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50',
                    key: 'next'
                  },
                  [
                    React.createElement('span', { className: 'sr-only' }, 'Next'),
                    React.createElement(
                      'svg',
                      {
                        className: 'h-5 w-5',
                        xmlns: 'http://www.w3.org/2000/svg',
                        viewBox: '0 0 20 20',
                        fill: 'currentColor',
                        'aria-hidden': 'true'
                      },
                      React.createElement(
                        'path',
                        {
                          fillRule: 'evenodd',
                          d: 'M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z',
                          clipRule: 'evenodd'
                        }
                      )
                    )
                  ]
                )
              ]
            )
          )
        ]
      );
    };
  }
  
  // Set up the page - fetch initial data and initialize React components
  fetchDashboardData();
  
  // Initialize search feedback component when the tab is clicked
  document.getElementById('feedback-tab')?.addEventListener('click', function() {
    if (!document.getElementById('reactFeedbackRoot')) {
      initializeSearchFeedbackComponent();
    }
  });
});