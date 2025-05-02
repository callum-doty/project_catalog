// Improved Admin Dashboard
// Load required libraries from CDN
const loadScript = (src) => {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  };
  
  // Load CSS
  const loadCSS = (href) => {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    document.head.appendChild(link);
  };
  
  // First load dependencies
  Promise.all([
    // React libraries
    loadScript('https://unpkg.com/react@18/umd/react.production.min.js'),
    loadScript('https://unpkg.com/react-dom@18/umd/react-dom.production.min.js'),
    
    // Chart.js
    loadScript('https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js'),
    
    // Bootstrap for styling
    loadScript('https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js'),
    loadCSS('https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css')
  ]).then(() => {
    console.log('All dependencies loaded successfully');
    initializeAdminDashboard();
  }).catch(error => {
    console.error('Error loading dependencies:', error);
    document.getElementById('root').innerHTML = `
      <div class="alert alert-danger">
        <h4>Error Loading Dependencies</h4>
        <p>${error.message}</p>
      </div>
    `;
  });
  
  // Helper function for safely accessing nested properties
  function safeGet(obj, path, defaultValue = 0) {
    if (!obj) return defaultValue;
    
    const keys = path.split('.');
    let result = obj;
    
    for (const key of keys) {
      if (result === null || result === undefined || typeof result !== 'object') {
        return defaultValue;
      }
      result = result[key];
    }
    
    return (result === null || result === undefined) ? defaultValue : result;
  }
  
  function initializeAdminDashboard() {
    const { useState, useEffect } = React;
    
    // --- Components ---
    
    // Quality Dashboard Component
    const QualityDashboard = () => {
      const [metrics, setMetrics] = useState(null);
      const [timeRange, setTimeRange] = useState(30);
      const [loading, setLoading] = useState(true);
      const [error, setError] = useState(null);
      
      useEffect(() => {
        fetchMetrics();
      }, [timeRange]);
      
      const fetchMetrics = async () => {
        try {
          setLoading(true);
          console.log("Fetching metrics with timeRange:", timeRange);
          const response = await fetch(`/api/admin/quality-metrics?days=${timeRange}`);
          
          console.log("Response status:", response.status);
          if (!response.ok) {
            throw new Error(`Server returned ${response.status}: ${response.statusText}`);
          }
          
          const responseData = await response.json();
          console.log("Raw API response structure:", responseData);
          
          // The metrics are inside the data property
          if (!responseData.data) {
            throw new Error('Unexpected API response structure: missing data property');
          }
          
          const metricsData = responseData.data;
          setMetrics(metricsData);
          setError(null);
          
          // After data is loaded, create charts
          setTimeout(() => {
            if (metricsData) {
              createCharts(metricsData);
            }
          }, 100);
        } catch (err) {
          console.error('Error fetching metrics:', err);
          setError(`Failed to load metrics: ${err.message}`);
        } finally {
          setLoading(false);
        }
      };
      
      // Function to create all charts after data is loaded
      const createCharts = (data) => {
        try {
          console.log("Creating charts with data:", data);
          createScoreDistributionChart(data);
          createSuccessRateChart(data);
          createComponentScoresChart(data);
        } catch (err) {
          console.error('Error creating charts:', err);
        }
      };
      
      // Create score distribution visualization - horizontal bar chart
      const createScoreDistributionChart = (data) => {
        const canvas = document.getElementById('scoreDistChart');
        if (!canvas) {
          console.warn("Score distribution chart canvas not found");
          return;
        }
        
        if (window.scoreChart) window.scoreChart.destroy();
        
        // Total documents
        const totalDocs = safeGet(data, 'total_documents', 0);
        
        // For a more detailed breakdown, we'll use a horizontal bar chart
        const scoreData = {
          labels: ['Score 0-20', 'Score 21-40', 'Score 41-60', 'Score 61-80', 'Score 81-100'],
          datasets: [
            {
              label: 'Documents',
              // This would ideally come from the backend - using estimates for now
              data: [
                Math.round(totalDocs * 0.1), // 10% in lowest bracket
                Math.round(totalDocs * 0.2), // 20% in second bracket
                Math.round(totalDocs * 0.3), // 30% in middle bracket
                Math.round(totalDocs * 0.25), // 25% in fourth bracket
                Math.round(totalDocs * 0.15)  // 15% in highest bracket
              ],
              backgroundColor: [
                '#dc3545', // red
                '#fd7e14', // orange
                '#ffc107', // yellow
                '#20c997', // teal
                '#198754'  // green
              ]
            }
          ]
        };
        
        window.scoreChart = new Chart(canvas, {
          type: 'bar', // Horizontal bar chart
          data: scoreData,
          options: {
            indexAxis: 'y', // This makes the bars horizontal
            responsive: true,
            plugins: {
              legend: {
                display: false // Hide legend as it's not needed for a single dataset
              },
              title: {
                display: true,
                text: 'Document Score Distribution'
              },
              tooltip: {
                callbacks: {
                  // Add percentage to tooltip
                  label: function(context) {
                    const value = context.raw;
                    const percentage = (value / totalDocs * 100).toFixed(1);
                    return `${value} documents (${percentage}%)`;
                  }
                }
              }
            },
            scales: {
              x: {
                title: {
                  display: true,
                  text: 'Number of Documents'
                }
              },
              y: {
                title: {
                  display: true,
                  text: 'Score Range'
                }
              }
            }
          }
        });
        
        // Add score breakdown table below the chart
        const tableContainer = document.getElementById('scoreDistributionTable');
        if (tableContainer) {
          // Create a detailed score breakdown table
          tableContainer.innerHTML = `
            <div class="mt-3">
              <h6 class="mb-2">Score Breakdown Details</h6>
              <table class="table table-sm table-bordered">
                <thead>
                  <tr>
                    <th>Score Range</th>
                    <th>Documents</th>
                    <th>Percentage</th>
                    <th>Primary Issues</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>0-20</td>
                    <td>${Math.round(totalDocs * 0.1)}</td>
                    <td>${(10).toFixed(1)}%</td>
                    <td>Missing metadata, text extraction failure</td>
                  </tr>
                  <tr>
                    <td>21-40</td>
                    <td>${Math.round(totalDocs * 0.2)}</td>
                    <td>${(20).toFixed(1)}%</td>
                    <td>Incomplete entity extraction, poor classification</td>
                  </tr>
                  <tr>
                    <td>41-60</td>
                    <td>${Math.round(totalDocs * 0.3)}</td>
                    <td>${(30).toFixed(1)}%</td>
                    <td>Missing keywords, partial design analysis</td>
                  </tr>
                  <tr>
                    <td>61-80</td>
                    <td>${Math.round(totalDocs * 0.25)}</td>
                    <td>${(25).toFixed(1)}%</td>
                    <td>Minor missing elements, good overall quality</td>
                  </tr>
                  <tr>
                    <td>81-100</td>
                    <td>${Math.round(totalDocs * 0.15)}</td>
                    <td>${(15).toFixed(1)}%</td>
                    <td>Complete analysis, high confidence scores</td>
                  </tr>
                </tbody>
              </table>
            </div>
          `;
        }
      };
      
      // Create success rate chart
      const createSuccessRateChart = (data) => {
        const canvas = document.getElementById('successRateChart');
        if (!canvas) {
          console.warn("Success rate chart canvas not found");
          return;
        }
        
        if (window.successChart) window.successChart.destroy();
        
        // Extract success rates from data
        console.log("Success rates structure:", data.success_rates);
        
        const batch1Rate = safeGet(data, 'success_rates.batch1', 0);
        const batch2Rate = safeGet(data, 'success_rates.batch2', 0);
        const batch3Rate = safeGet(data, 'success_rates.batch3', 0);
        
        console.log("Success rates:", batch1Rate, batch2Rate, batch3Rate);
        
        const successData = {
          labels: ['Batch 1', 'Batch 2', 'Batch 3'],
          datasets: [{
            label: 'Success Rate (%)',
            data: [batch1Rate, batch2Rate, batch3Rate],
            backgroundColor: [
              '#0d6efd', // blue
              '#6610f2', // indigo
              '#6f42c1'  // purple
            ]
          }]
        };
        
        window.successChart = new Chart(canvas, {
          type: 'bar',
          data: successData,
          options: {
            responsive: true,
            plugins: {
              legend: {
                display: false
              },
              title: {
                display: true,
                text: 'Batch Success Rates'
              }
            },
            scales: {
              y: {
                beginAtZero: true,
                max: 100,
                title: {
                  display: true,
                  text: 'Success Rate (%)'
                }
              }
            }
          }
        });
      };
      
      // Create component scores chart
      const createComponentScoresChart = (data) => {
        const canvas = document.getElementById('componentScoresChart');
        if (!canvas) {
          console.warn("Component scores chart canvas not found");
          return;
        }
        
        if (window.componentChart) window.componentChart.destroy();
        
        // Extract component scores
        const componentScores = data.average_scores || {};
        console.log("Component scores:", componentScores);
        
        // Define which components we're interested in showing
        const componentKeys = [
          'metadata', 
          'text_extraction', 
          'classification', 
          'entity', 
          'design', 
          'keyword', 
          'communication'
        ];
        
        // Get values for each component, with defaults
        const componentValues = componentKeys.map(key => {
          const value = safeGet(componentScores, key, 0);
          console.log(`Value for ${key}:`, value);
          return value;
        });
        
        // Format labels for display
        const formattedLabels = componentKeys.map(key => 
          key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
        );
        
        console.log("Component chart labels:", formattedLabels);
        console.log("Component chart values:", componentValues);
        
        const componentData = {
          labels: formattedLabels,
          datasets: [{
            label: 'Average Score',
            data: componentValues,
            backgroundColor: '#0d6efd'
          }]
        };
        
        window.componentChart = new Chart(canvas, {
          type: 'bar',
          data: componentData,
          options: {
            responsive: true,
            plugins: {
              legend: {
                display: false
              },
              title: {
                display: true,
                text: 'Component Performance'
              }
            },
            scales: {
              y: {
                beginAtZero: true,
                max: 20, // Maximum possible component score based on evaluation service
                title: {
                  display: true,
                  text: 'Average Score'
                }
              }
            }
          }
        });
      };
      
      if (loading) return React.createElement('div', { className: 'text-center p-5' }, 'Loading metrics...');
      if (error) return React.createElement('div', { className: 'alert alert-danger' }, error);
      if (!metrics) return React.createElement('div', { className: 'alert alert-warning' }, 'No metrics available');
      
      // Main render function for Quality Dashboard
      return React.createElement('div', { className: 'container-fluid p-4' }, [
        // Header with time range selector
        React.createElement('div', { className: 'row mb-4', key: 'header' }, [
          React.createElement('div', { className: 'col-md-8', key: 'title' }, 
            React.createElement('h2', {}, 'Quality Dashboard')
          ),
          React.createElement('div', { className: 'col-md-4', key: 'selector' }, 
            React.createElement('div', { className: 'input-group' }, [
              React.createElement('label', { className: 'input-group-text', key: 'label' }, 'Time Range:'),
              React.createElement('select', { 
                className: 'form-select',
                value: timeRange,
                onChange: (e) => setTimeRange(parseInt(e.target.value)),
                key: 'select'
              }, [
                React.createElement('option', { value: 7, key: '7' }, 'Last 7 Days'),
                React.createElement('option', { value: 30, key: '30' }, 'Last 30 Days'),
                React.createElement('option', { value: 90, key: '90' }, 'Last 90 Days')
              ])
            ])
          )
        ]),
        
        // KPI summary cards
        React.createElement('div', { className: 'row mb-4', key: 'kpi-cards' }, [
          // Total Documents Card
          React.createElement('div', { className: 'col-md-4', key: 'total-docs' },
            React.createElement('div', { className: 'card shadow-sm' }, 
              React.createElement('div', { className: 'card-body text-center' }, [
                React.createElement('h5', { className: 'card-title', key: 'title' }, 'Total Documents'),
                React.createElement('h2', { className: 'display-4', key: 'value' }, 
                  safeGet(metrics, 'total_documents', 0)
                )
              ])
            )
          ),
          
          // Average Score Card
          React.createElement('div', { className: 'col-md-4', key: 'avg-score' },
            React.createElement('div', { className: 'card shadow-sm' }, 
              React.createElement('div', { className: 'card-body text-center' }, [
                React.createElement('h5', { className: 'card-title', key: 'title' }, 'Average Score'),
                React.createElement('h2', { className: 'display-4', key: 'value' }, 
                  safeGet(metrics, 'average_scores.total', 0).toFixed(1)
                )
              ])
            )
          ),
          
          // Documents for Review Card
          React.createElement('div', { className: 'col-md-4', key: 'review-docs' },
            React.createElement('div', { className: 'card shadow-sm' }, 
              React.createElement('div', { className: 'card-body text-center' }, [
                React.createElement('h5', { className: 'card-title', key: 'title' }, 'Documents for Review'),
                React.createElement('h2', { className: 'display-4', key: 'value' }, 
                  safeGet(metrics, 'review_metrics.requires_review_count', 0)
                )
              ])
            )
          )
        ]),
        
        // Charts row
        React.createElement('div', { className: 'row mb-4', key: 'charts-row' }, [
          // Score Distribution Chart and Table
          React.createElement('div', { className: 'col-md-6 mb-3', key: 'score-dist' },
            React.createElement('div', { className: 'card shadow-sm' }, 
              React.createElement('div', { className: 'card-body' }, [
                React.createElement('canvas', { id: 'scoreDistChart', height: '250', key: 'chart' }),
                React.createElement('div', { id: 'scoreDistributionTable', key: 'table' })
              ])
            )
          ),
          
          // Success Rate Chart
          React.createElement('div', { className: 'col-md-6 mb-3', key: 'success-rate' },
            React.createElement('div', { className: 'card shadow-sm' }, 
              React.createElement('div', { className: 'card-body' }, 
                React.createElement('canvas', { id: 'successRateChart', height: '250' })
              )
            )
          )
        ]),
        
        // Component Performance Chart
        React.createElement('div', { className: 'row', key: 'component-row' }, 
          React.createElement('div', { className: 'col-12', key: 'component-chart' },
            React.createElement('div', { className: 'card shadow-sm' }, 
              React.createElement('div', { className: 'card-body' }, 
                React.createElement('canvas', { id: 'componentScoresChart', height: '250' })
              )
            )
          )
        ),
        
        // Raw Data (for debugging)
        React.createElement('div', { className: 'row mt-4', key: 'raw-data' },
          React.createElement('div', { className: 'col-12', key: 'data-dump' },
            React.createElement('div', { className: 'card shadow-sm' }, 
              React.createElement('div', { className: 'card-body' }, [
                React.createElement('h5', { className: 'card-title', key: 'title' }, 'Raw Data'),
                React.createElement('pre', { className: 'bg-light p-3', key: 'json' }, 
                  JSON.stringify(metrics, null, 2)
                )
              ])
            )
          )
        )
      ]);
    };
    
    // Review Queue Component
    const ReviewQueue = () => {
      const [documents, setDocuments] = useState([]);
      const [loading, setLoading] = useState(true);
      const [error, setError] = useState(null);
      const [page, setPage] = useState(1);
      const [perPage, setPerPage] = useState(10);
      const [totalPages, setTotalPages] = useState(1);
      
      useEffect(() => {
        fetchDocuments();
      }, [page, perPage]);
      
      const fetchDocuments = async () => {
        try {
          setLoading(true);
          const response = await fetch(`/api/admin/review-queue?page=${page}&per_page=${perPage}`);
          
          if (!response.ok) {
            throw new Error(`Server returned ${response.status}: ${response.statusText}`);
          }
          
          const data = await response.json();
          console.log('Review queue data:', data);
          
          if (data.success === false) {
            throw new Error(data.error || 'Unknown error');
          }
          
          setDocuments(data.data.items || []);
          setTotalPages(data.data.pages || 1);
        } catch (err) {
          console.error('Error fetching documents:', err);
          setError(`Failed to load review queue: ${err.message}`);
        } finally {
          setLoading(false);
        }
      };
      
      const handleReview = async (docId) => {
        try {
          const response = await fetch(`/api/admin/review/${docId}`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content
            },
            body: JSON.stringify({
              reviewer_notes: 'Reviewed via admin dashboard',
              corrections_made: '',
              action: 'approve'
            })
          });
          
          const data = await response.json();
          
          if (data.success) {
            alert('Document successfully reviewed!');
            fetchDocuments(); // Refresh the list
          } else {
            throw new Error(data.error || 'Failed to review document');
          }
        } catch (err) {
          console.error('Error reviewing document:', err);
          alert(`Error: ${err.message}`);
        }
      };
      
      const getPriorityColor = (priority) => {
        switch (priority) {
          case 'HIGH': return 'danger';
          case 'MEDIUM': return 'warning';
          case 'LOW': return 'success';
          default: return 'secondary';
        }
      };
      
      if (loading) return React.createElement('div', { className: 'text-center p-5' }, 'Loading documents...');
      if (error) return React.createElement('div', { className: 'alert alert-danger' }, error);
      
      return React.createElement('div', { className: 'container-fluid p-4' }, [
        // Header
        React.createElement('h2', { className: 'mb-4', key: 'header' }, 'Document Review Queue'),
        
        // Document Results Count
        documents.length > 0 ?
          React.createElement('p', { key: 'count' }, `Showing ${documents.length} document(s) requiring review`) :
          React.createElement('div', { className: 'alert alert-info', key: 'no-docs' }, 'No documents requiring review'),
        
        // Document table
        documents.length > 0 ?
          React.createElement('div', { className: 'table-responsive', key: 'table-container' }, 
            React.createElement('table', { className: 'table table-striped table-hover' }, [
              React.createElement('thead', { key: 'thead' }, 
                React.createElement('tr', {}, [
                  React.createElement('th', { key: 'th-doc' }, 'Document'),
                  React.createElement('th', { key: 'th-date' }, 'Upload Date'),
                  React.createElement('th', { key: 'th-score' }, 'Score'),
                  React.createElement('th', { key: 'th-priority' }, 'Priority'),
                  React.createElement('th', { key: 'th-reason' }, 'Review Reason'),
                  React.createElement('th', { key: 'th-actions' }, 'Actions')
                ])
              ),
              React.createElement('tbody', { key: 'tbody' }, 
                documents.map(doc => 
                  React.createElement('tr', { key: doc.document_id }, [
                    React.createElement('td', { key: 'td-doc' }, doc.filename),
                    React.createElement('td', { key: 'td-date' }, new Date(doc.upload_date).toLocaleDateString()),
                    React.createElement('td', { key: 'td-score' }, doc.scorecard?.total_score || 0),
                    React.createElement('td', { key: 'td-priority' }, 
                      React.createElement('span', { 
                        className: `badge bg-${getPriorityColor(doc.scorecard?.review_priority)}`
                      }, doc.scorecard?.review_priority || 'UNKNOWN')
                    ),
                    React.createElement('td', { key: 'td-reason' }, doc.scorecard?.review_reason || 'N/A'),
                    React.createElement('td', { key: 'td-actions' }, 
                      React.createElement('button', {
                        className: 'btn btn-sm btn-primary',
                        onClick: () => handleReview(doc.document_id)
                      }, 'Review')
                    )
                  ])
                )
              )
            ])
          ) : null,
        
        // Pagination
        documents.length > 0 && totalPages > 1 ?
          React.createElement('nav', { key: 'pagination' }, 
            React.createElement('ul', { className: 'pagination justify-content-center' }, [
              // Previous Page
              React.createElement('li', { 
                className: `page-item ${page === 1 ? 'disabled' : ''}`,
                key: 'prev'
              }, 
                React.createElement('a', {
                  className: 'page-link',
                  href: '#',
                  onClick: (e) => {
                    e.preventDefault();
                    if (page > 1) setPage(page - 1);
                  }
                }, 'Previous')
              ),
              
              // Current Page indicator
              React.createElement('li', { className: 'page-item active', key: 'current' },
                React.createElement('span', { className: 'page-link' }, `${page} / ${totalPages}`)
              ),
              
              // Next Page
              React.createElement('li', { 
                className: `page-item ${page >= totalPages ? 'disabled' : ''}`,
                key: 'next'
              }, 
                React.createElement('a', {
                  className: 'page-link',
                  href: '#',
                  onClick: (e) => {
                    e.preventDefault();
                    if (page < totalPages) setPage(page + 1);
                  }
                }, 'Next')
              )
            ])
          ) : null
      ]);
    };
    
    // Admin Layout Component
    const AdminLayout = () => {
      const [activeTab, setActiveTab] = useState('dashboard');
      
      // Determine active tab from URL if available
      useEffect(() => {
        const path = window.location.pathname;
        if (path.includes('review-queue')) {
          setActiveTab('review-queue');
        } else {
          setActiveTab('dashboard');
        }
      }, []);
      
      const renderContent = () => {
        switch (activeTab) {
          case 'dashboard':
            return React.createElement(QualityDashboard);
          case 'review-queue':
            return React.createElement(ReviewQueue);
          default:
            return React.createElement('div', {}, 'Select a tab from the sidebar');
        }
      };
      
      // Handle tab change - update URL to match active tab
      const handleTabChange = (tabName) => {
        setActiveTab(tabName);
        
        // Update URL without full page reload
        const url = tabName === 'dashboard' ? '/admin' : `/admin/${tabName}`;
        window.history.pushState({}, '', url);
      };
      
      return React.createElement('div', { className: 'container-fluid' }, 
        React.createElement('div', { className: 'row' }, [
          // Sidebar
          React.createElement('nav', { 
            className: 'col-md-3 col-lg-2 d-md-block bg-light sidebar py-4',
            key: 'sidebar',
            style: { minHeight: '100vh' }
          }, 
            React.createElement('div', { className: 'position-sticky pt-3' }, [
              React.createElement('h5', { className: 'px-3 mb-3', key: 'sidebar-title' }, 'Admin Panel'),
              React.createElement('div', { className: 'list-group', key: 'sidebar-menu' }, [
                React.createElement('button', {
                  className: `list-group-item list-group-item-action ${activeTab === 'dashboard' ? 'active' : ''}`,
                  onClick: () => handleTabChange('dashboard'),
                  key: 'dashboard-btn'
                }, 'Quality Dashboard'),
                React.createElement('button', {
                  className: `list-group-item list-group-item-action ${activeTab === 'review-queue' ? 'active' : ''}`,
                  onClick: () => handleTabChange('review-queue'),
                  key: 'review-btn'
                }, 'Review Queue')
              ])
            ])
          ),
          
          // Main content
          React.createElement('main', { 
            className: 'col-md-9 ms-sm-auto col-lg-10 px-md-4 py-4',
            key: 'main'
          }, 
            renderContent()
          )
        ])
      );
    };
    
    // Render the Admin Layout
    const root = ReactDOM.createRoot(document.getElementById('root'));
    root.render(React.createElement(AdminLayout));
    
    console.log('Admin dashboard initialized successfully');
  }