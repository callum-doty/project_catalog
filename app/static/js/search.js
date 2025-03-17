// static/js/search.js

document.addEventListener('DOMContentLoaded', function () {
    // Handle missing previews gracefully
    const previewImages = document.querySelectorAll('.preview-image');
    previewImages.forEach(img => {
        img.onerror = function () {
            // Replace with a generic document icon
            this.src = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIiB2aWV3Qm94PSIwIDAgMjQgMjQiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzY2NiIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0xNCAySDZhMiAyIDAgMCAwLTIgMnYxNmEyIDIgMCAwIDAgMiAyaDEyYTIgMiAwIDAgMCAyLTJWOHoiPjwvcGF0aD48cG9seWxpbmUgcG9pbnRzPSIxNCAyIDE0IDggMjAgOCI+PC9wb2x5bGluZT48L3N2Zz4=";
            this.classList.add('fallback-icon');
        };
    });

    // Cache DOM elements for better performance
    const previewContainer = document.getElementById('resultsGrid');
    const searchForm = document.getElementById('searchForm');
    const sortBySelect = document.getElementById('sort_by');
    const sortDirElement = document.getElementById('sort_direction');

    // Setup search form
    if (searchForm) {
        setupSearchForm(searchForm, sortBySelect, sortDirElement);
    }

    // Setup AJAX pagination links
    setupAjaxPagination();
});

function setupSearchForm(searchForm, sortBySelect, sortDirElement) {
    // Create a debounce function for search
    let searchTimeout;
    const DEBOUNCE_TIME = 300; // ms

    searchForm.addEventListener('submit', function (e) {
        e.preventDefault();
        clearTimeout(searchTimeout);

        searchTimeout = setTimeout(() => {
            executeSearch(new FormData(this).get('q'),
                sortBySelect?.value || 'upload_date',
                sortDirElement?.dataset?.direction || 'desc');
        }, DEBOUNCE_TIME);
    });
}

function executeSearch(query, sortBy, sortDir) {
    const url = `/search?q=${encodeURIComponent(query)}&page=1&sort_by=${sortBy}&sort_dir=${sortDir}`;

    // Show loading state
    const resultsGrid = document.getElementById('resultsGrid');
    if (resultsGrid) {
        resultsGrid.innerHTML = `
            <div class="col-span-full flex justify-center items-center py-8">
                <svg class="animate-spin -ml-1 mr-3 h-8 w-8 text-indigo-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span class="text-gray-600">Searching...</span>
            </div>
        `;
    }

    fetch(url, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Search failed: ${response.status} ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            updateResults(data);
            // Update URL without page reload
            const newUrl = new URL(window.location);
            newUrl.searchParams.set('q', query);
            newUrl.searchParams.set('page', 1);
            newUrl.searchParams.set('sort_by', sortBy);
            newUrl.searchParams.set('sort_dir', sortDir);
            window.history.pushState({}, '', newUrl);
        })
        .catch(error => {
            console.error('Search error:', error);
            // Show error message
            if (resultsGrid) {
                resultsGrid.innerHTML = `
                <div class="col-span-full text-center py-8">
                    <p class="text-red-500">Error searching: ${error.message}</p>
                    <p class="text-gray-500 mt-2">Please try again later</p>
                </div>
            `;
            }
        });
}

function setupAjaxPagination() {
    // Use event delegation for pagination links
    document.addEventListener('click', function (e) {
        const paginationLink = e.target.closest('.pagination-link');
        if (!paginationLink) return;

        e.preventDefault();
        const url = new URL(paginationLink.href);

        // Show loading state
        const resultsGrid = document.getElementById('resultsGrid');
        if (resultsGrid) {
            resultsGrid.innerHTML = `
                <div class="col-span-full flex justify-center items-center py-8">
                    <svg class="animate-spin -ml-1 mr-3 h-8 w-8 text-indigo-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span class="text-gray-600">Loading page...</span>
                </div>
            `;
        }

        // Add AJAX header
        fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Failed to load page: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                updateResults(data);
                // Update URL without page reload
                window.history.pushState({}, '', url);
                // Scroll to top of results
                document.querySelector('.document-count')?.scrollIntoView({ behavior: 'smooth' });
            })
            .catch(error => {
                console.error('Pagination error:', error);
                if (resultsGrid) {
                    resultsGrid.innerHTML = `
                    <div class="col-span-full text-center py-8">
                        <p class="text-red-500">Error loading page: ${error.message}</p>
                        <p class="text-gray-500 mt-2">Please try again</p>
                    </div>
                `;
                }
            });
    });
}

function updateResults(data) {
    // Performance optimization: Use doc fragments and direct DOM manipulation
    const docFragment = document.createDocumentFragment();
    const grid = document.getElementById('resultsGrid');

    if (!grid) return;

    // Clear the grid
    grid.innerHTML = '';

    // Check if we have the new data structure
    const results = data.results || data;
    const pagination = data.pagination;

    // Store response time for display
    if (data.response_time_ms) {
        window.lastResponseTime = Math.round(data.response_time_ms);
    }

    if (!results || !results.length) {
        const noResultsDiv = document.createElement('div');
        noResultsDiv.className = 'col-span-1 md:col-span-2 lg:col-span-3 text-center py-8';
        noResultsDiv.innerHTML = `
            <p class="text-gray-500">
                No documents found${data.query ? ' for "' + data.query + '"' : ''}
            </p>
            ${!data.query ? '<p class="text-gray-500 mt-2">Try uploading some documents first</p>' : ''}
        `;
        grid.appendChild(noResultsDiv);

        updateDocumentCount(0);
        updatePagination(null);
        return;
    }

    // Build the grid efficiently
    results.forEach(doc => {
        const card = document.createElement('div');
        card.className = 'bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow';

        card.innerHTML = `
            <div class="w-full h-48 bg-gray-100 flex items-center justify-center">
                ${doc.preview
                ? `<img src="${doc.preview}" 
                           alt="Preview of ${doc.filename}" 
                           class="w-full h-full object-contain preview-image"
                           onerror="this.src='data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIiB2aWV3Qm94PSIwIDAgMjQgMjQiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzY2NiIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0xNCAySDZhMiAyIDAgMCAwLTIgMnYxNmEyIDIgMCAwIDAgMiAyaDEyYTIgMiAwIDAgMCAyLTJWOHoiPjwvcGF0aD48cG9seWxpbmUgcG9pbnRzPSIxNCAyIDE0IDggMjAgOCI+PC9wb2x5bGluZT48L3N2Zz4='; this.classList.add('fallback-icon');">`
                : `<div class="flex flex-col items-center text-gray-400">
                           <svg class="w-12 h-12 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                               <path stroke-linecap="round" 
                                     stroke-linejoin="round" 
                                     stroke-width="2" 
                                     d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                           </svg>
                           <span>No preview available</span>
                       </div>`
            }
            </div>
            
            <div class="p-6">
                <h3 class="text-lg font-semibold text-gray-900 mb-2">${doc.filename}</h3>
                <p class="text-sm text-gray-500 mb-4">Uploaded: ${doc.upload_date}</p>
                
                <div class="mb-4">
                    <h4 class="text-sm font-medium text-gray-700 mb-1">Summary</h4>
                    <p class="text-sm text-gray-600 line-clamp-3">${doc.summary || 'No summary available'}</p>
                </div>
                
                ${doc.keywords?.length ? `
                    <div>
                        <h4 class="text-sm font-medium text-gray-700 mb-1">Keywords</h4>
                        <div class="flex flex-wrap gap-2">
                            ${doc.keywords.map(keyword => `
                                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                    ${keyword.text}
                                    ${keyword.category
                    ? `<span class="ml-1 text-blue-600">(${keyword.category})</span>`
                    : ''}
                                </span>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;

        grid.appendChild(card);
    });

    // Update document count and pagination
    if (pagination) {
        updateDocumentCount(pagination.total, pagination);
        updatePagination(pagination);
    } else {
        updateDocumentCount(results.length);
        updatePagination(null);
    }

    // Reattach event handlers for image error handling
    const previewImages = document.querySelectorAll('.preview-image');
    previewImages.forEach(img => {
        img.onerror = function () {
            this.src = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIiB2aWV3Qm94PSIwIDAgMjQgMjQiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzY2NiIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0xNCAySDZhMiAyIDAgMCAwLTIgMnYxNmEyIDIgMCAwIDAgMiAyaDEyYTIgMiAwIDAgMCAyLTJWOHoiPjwvcGF0aD48cG9seWxpbmUgcG9pbnRzPSIxNCAyIDE0IDggMjAgOCI+PC9wb2x5bGluZT48L3N2Zz4=";
            this.classList.add('fallback-icon');
        };
    });
}

// Update document count
function updateDocumentCount(count, pagination) {
    const countElement = document.querySelector('.document-count');
    if (!countElement) return;

    if (pagination && pagination.total > 0) {
        const start = Math.max((pagination.page - 1) * pagination.per_page + 1, 1);
        const end = Math.min(start + pagination.per_page - 1, pagination.total);
        const responseTime = window.lastResponseTime ? `<span class="text-sm">(${window.lastResponseTime}ms)</span>` : '';

        countElement.innerHTML = `Showing ${start} to ${end} of ${pagination.total} document${pagination.total !== 1 ? 's' : ''} ${responseTime}`;
    } else {
        countElement.textContent = `Found ${count} document${count !== 1 ? 's' : ''}`;
    }
}

// Update pagination controls - more efficient with DocumentFragment
function updatePagination(pagination) {
    const paginationContainer = document.querySelector('.pagination-container');
    if (!paginationContainer) return;

    if (!pagination || !pagination.pages || pagination.pages <= 1) {
        paginationContainer.innerHTML = '';
        return;
    }

    // Get current query parameters
    const urlParams = new URLSearchParams(window.location.search);
    const query = urlParams.get('q') || '';
    const sortBy = urlParams.get('sort_by') || 'upload_date';
    const sortDir = urlParams.get('sort_dir') || 'desc';

    // Calculate page range
    let startPage = Math.max(pagination.page - 2, 1);
    let endPage = Math.min(startPage + 4, pagination.pages);
    startPage = Math.max(endPage - 4, 1);

    // Create a document fragment for better performance
    const fragment = document.createDocumentFragment();
    const nav = document.createElement('nav');
    nav.className = 'inline-flex rounded-md shadow';

    // Previous button
    if (pagination.has_prev) {
        const prevLink = document.createElement('a');
        prevLink.href = `/search?q=${encodeURIComponent(query)}&page=${pagination.prev_page}&per_page=${pagination.per_page}&sort_by=${sortBy}&sort_dir=${sortDir}`;
        prevLink.className = 'pagination-link relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50';
        prevLink.innerHTML = `
            <span class="sr-only">Previous</span>
            <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd" />
            </svg>
        `;
        nav.appendChild(prevLink);
    }

    // Page numbers
    for (let i = startPage; i <= endPage; i++) {
        const isActive = i === pagination.page;
        const pageLink = document.createElement('a');
        pageLink.href = `/search?q=${encodeURIComponent(query)}&page=${i}&per_page=${pagination.per_page}&sort_by=${sortBy}&sort_dir=${sortDir}`;
        pageLink.className = `pagination-link relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium ${isActive ? 'text-indigo-600 bg-indigo-50' : 'text-gray-700 hover:bg-gray-50'}`;
        pageLink.textContent = i;
        nav.appendChild(pageLink);
    }

    // Next button
    if (pagination.has_next) {
        const nextLink = document.createElement('a');
        nextLink.href = `/search?q=${encodeURIComponent(query)}&page=${pagination.next_page}&per_page=${pagination.per_page}&sort_by=${sortBy}&sort_dir=${sortDir}`;
        nextLink.className = 'pagination-link relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50';
        nextLink.innerHTML = `
            <span class="sr-only">Next</span>
            <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
            </svg>
        `;
        nav.appendChild(nextLink);
    }

    // Replace the old content with the new navigation
    paginationContainer.innerHTML = '';
    paginationContainer.appendChild(nav);
}