// Create a new file app/static/js/infinite-scroll.js

document.addEventListener('DOMContentLoaded', function() {
    // Only initialize if we're on the search page with results
    if (!document.getElementById('resultsGrid')) return;
    
    let page = 1;
    let loading = false;
    let hasMore = true;
    
    // Get query parameters from the current URL
    const urlParams = new URLSearchParams(window.location.search);
    let query = urlParams.get('q') || '';
    const sort_by = urlParams.get('sort_by') || 'upload_date';
    const sort_dir = urlParams.get('sort_dir') || 'desc';
    
    // Function to load more results
    function loadMoreResults() {
      if (loading || !hasMore) return;
      
      loading = true;
      page++;
      
      // Show loading indicator
      const loadingIndicator = document.getElementById('loadingIndicator');
      if (loadingIndicator) loadingIndicator.classList.remove('hidden');
      
      // Fetch more results
      fetch(`/api/search?q=${encodeURIComponent(query)}&page=${page}&sort_by=${sort_by}&sort_dir=${sort_dir}`, {
        headers: {
          'X-Requested-With': 'XMLHttpRequest'
        }
      })
      .then(response => response.json())
      .then(data => {
        // Hide loading indicator
        if (loadingIndicator) loadingIndicator.classList.add('hidden');
        
        if (data.results && data.results.length > 0) {
          // Append new results to the grid
          appendResults(data.results);
          
          // Check if there are more pages
          hasMore = data.pagination.has_next;
        } else {
          hasMore = false;
        }
        
        loading = false;
      })
      .catch(error => {
        console.error('Error loading more results:', error);
        loading = false;
        if (loadingIndicator) loadingIndicator.classList.add('hidden');
      });
    }
    
    // Function to append results to the grid
    function appendResults(results) {
      const resultsGrid = document.getElementById('resultsGrid');
      if (!resultsGrid) return;
      
      results.forEach(doc => {
        // Create document card and append it
        const card = createDocumentCard(doc);
        resultsGrid.appendChild(card);
      });
    }
    
    // Create a document card element
    function createDocumentCard(doc) {
      const card = document.createElement('div');
      card.className = 'document-card bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow';
      
      // Generate card HTML based on your template
      card.innerHTML = `
        <!-- Card content based on your template -->
        <div class="preview-container" data-filename="${doc.filename}" data-loaded="false">
          <!-- Preview placeholder -->
        </div>
        <div class="p-6">
          <h3 class="text-lg font-semibold text-gray-900">${doc.filename}</h3>
          <!-- Other document details -->
        </div>
      `;
      
      return card;
    }
    
    // Set up intersection observer for infinite scrolling
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && !loading && hasMore) {
          loadMoreResults();
        }
      });
    }, {
      rootMargin: '200px' // Load when within 200px of viewport bottom
    });
    
    // Observe the loading indicator
    const loadingTrigger = document.getElementById('loadingTrigger');
    if (loadingTrigger) {
      observer.observe(loadingTrigger);
    }
  });