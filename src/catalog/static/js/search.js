document.addEventListener('DOMContentLoaded', function() {
    // Handle missing previews gracefully
    const previewImages = document.querySelectorAll('.preview-image');
    previewImages.forEach(img => {
        img.onerror = function() {
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

    searchForm.addEventListener('submit', function(e) {
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
    // Preserve taxonomy filter values if they exist
    const urlParams = new URLSearchParams(window.location.search);
    const primaryCategory = urlParams.get('primary_category') || '';
    const subcategory = urlParams.get('subcategory') || '';
    const filterType = urlParams.get('filter_type') || '';
    const filterYear = urlParams.get('filter_year') || '';
    const filterLocation = urlParams.get('filter_location') || '';
    
    // Build URL with all parameters
    const url = `/search?q=${encodeURIComponent(query)}&page=1` +
        `&sort_by=${sortBy}&sort_dir=${sortDir}` +
        (primaryCategory ? `&primary_category=${encodeURIComponent(primaryCategory)}` : '') +
        (subcategory ? `&subcategory=${encodeURIComponent(subcategory)}` : '') +
        (filterType ? `&filter_type=${encodeURIComponent(filterType)}` : '') +
        (filterYear ? `&filter_year=${encodeURIComponent(filterYear)}` : '') +
        (filterLocation ? `&filter_location=${encodeURIComponent(filterLocation)}` : '');

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
        console.log("Search results:", data);
        try {
            updateResults(data);
            // Update URL without page reload
            const newUrl = new URL(window.location);
            newUrl.searchParams.set('q', query);
            newUrl.searchParams.set('page', 1);
            newUrl.searchParams.set('sort_by', sortBy);
            newUrl.searchParams.set('sort_dir', sortDir);
            window.history.pushState({}, '', newUrl);
            
            // Also update taxonomy facets if present
            if (data.taxonomy_facets) {
                updateTaxonomyFacets(data.taxonomy_facets);
            }
        } catch (error) {
            console.error("Error updating results:", error);
            // Show error in the results grid
            if (resultsGrid) {
                resultsGrid.innerHTML = `
                    <div class="col-span-full text-center py-8">
                        <p class="text-red-500">Error processing results: ${error.message}</p>
                        <p class="text-gray-500 mt-2">Please try again later</p>
                    </div>
                `;
            }
        }
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
    document.addEventListener('click', function(e) {
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
            
            // Also update taxonomy facets if present
            if (data.taxonomy_facets) {
                updateTaxonomyFacets(data.taxonomy_facets);
            }
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
    const grid = document.getElementById('resultsGrid');

    if (!grid) return;

    // Clear the grid
    grid.innerHTML = '';

    // Validate input data
    if (!data) {
        console.error("No data provided to updateResults");
        grid.innerHTML = `
            <div class="col-span-full text-center py-8">
                <p class="text-red-500">Error: Invalid search results data</p>
            </div>
        `;
        return;
    }

    // Check if we have the new data structure
    const results = data.results || [];
    const pagination = data.pagination || null;

    // Store response time for display
    if (data.response_time_ms) {
        window.lastResponseTime = Math.round(data.response_time_ms);
    }

    // Handle empty results
    if (!results || !Array.isArray(results) || results.length === 0) {
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
        // Create a card safely
        try {
            const card = document.createElement('div');
            card.className = 'bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow';

            // Start building the HTML structure
            let cardHTML = `
                <div class="w-full h-48 bg-gray-100 flex items-center justify-center">
                    ${doc.preview
                        ? `<img src="${doc.preview}" 
                               alt="Preview of ${doc.filename || 'document'}" 
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
                    <h3 class="text-lg font-semibold text-gray-900 mb-2">${doc.filename || 'Untitled Document'}</h3>
                    <p class="text-sm text-gray-500 mb-2">Uploaded: ${doc.upload_date || 'Unknown date'}</p>
            `;

            // Add hierarchical keywords if available
            if (doc.hierarchical_keywords && doc.hierarchical_keywords.length > 0) {
                cardHTML += `
                    <div class="mb-3">
                        <div class="flex flex-wrap gap-1 mt-1">
                `;
                
                doc.hierarchical_keywords.forEach(kw => {
                    if (kw && kw.term) {
                        cardHTML += `
                            <span class="keyword-badge inline-flex flex-col px-2 py-1 rounded-md text-xs bg-blue-50 text-blue-700">
                                <span>${kw.term}</span>
                                <span class="keyword-category text-blue-400">${kw.subcategory || ''}</span>
                            </span>
                        `;
                    }
                });
                
                cardHTML += `
                        </div>
                    </div>
                `;
            }
            
            // Add summary
            cardHTML += `
                <div class="mb-4">
                    <p class="text-sm text-gray-600 line-clamp-3">${doc.summary || 'No summary available'}</p>
                </div>
            `;
            
            // Add key details
            cardHTML += `<div class="grid grid-cols-2 gap-2 text-xs">`;
            
            if (doc.document_type) {
                cardHTML += `
                    <div class="flex items-center">
                        <span class="text-gray-500 mr-1">Type:</span>
                        <span class="text-gray-700">${doc.document_type}</span>
                    </div>
                `;
            }
            
            if (doc.election_year) {
                cardHTML += `
                    <div class="flex items-center">
                        <span class="text-gray-500 mr-1">Year:</span>
                        <span class="text-gray-700">${doc.election_year}</span>
                    </div>
                `;
            }
            
            if (doc.location) {
                cardHTML += `
                    <div class="flex items-center">
                        <span class="text-gray-500 mr-1">Location:</span>
                        <span class="text-gray-700">${doc.location}</span>
                    </div>
                `;
            }
            
            if (doc.document_tone) {
                cardHTML += `
                    <div class="flex items-center">
                        <span class="text-gray-500 mr-1">Tone:</span>
                        <span class="text-gray-700">${doc.document_tone}</span>
                    </div>
                `;
            }
            
            cardHTML += `</div>`;
            
            cardHTML += `
                <div class="mt-4">
                    <a href="/document/${encodeURIComponent(doc.filename || 'Untitled Document')}" 
                       target="_blank" 
                       rel="noopener noreferrer"
                       class="view-document-button w-full block text-center px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50">
                        View Document
                    </a>
                </div>
            `;
            
            cardHTML += `</div>`;
            
            // Set the HTML content
            card.innerHTML = cardHTML;
            grid.appendChild(card);
        } catch (err) {
            console.error("Error creating document card:", err);
        }
    });

    // Update document count and pagination
    try {
        if (pagination) {
            updateDocumentCount(pagination.total, pagination);
            updatePagination(pagination);
        } else {
            updateDocumentCount(results.length);
            updatePagination(null);
        }
    } catch (error) {
        console.error("Error updating document count and pagination:", error);
    }

    // Reattach event handlers for image error handling
    try {
        const previewImages = document.querySelectorAll('.preview-image');
        previewImages.forEach(img => {
            img.onerror = function() {
                this.src = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIiB2aWV3Qm94PSIwIDAgMjQgMjQiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzY2NiIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0xNCAySDZhMiAyIDAgMCAwLTIgMnYxNmEyIDIgMCAwIDAgMiAyaDEyYTIgMiAwIDAgMCAyLTJWOHoiPjwvcGF0aD48cG9seWxpbmUgcG9pbnRzPSIxNCAyIDE0IDggMjAgOCI+PC9wb2x5bGluZT48L3N2Zz4=";
                this.classList.add('fallback-icon');
            };
        });
    } catch (error) {
        console.error("Error setting up image error handlers:", error);
    }
}

// Update document count
function updateDocumentCount(count, pagination) {
    const countElement = document.querySelector('.document-count');
    if (!countElement) return;

    if (pagination && pagination.total > 0) {
        const start = Math.max((pagination.page - 1) * pagination.per_page + 1, 1);
        let end = start + pagination.per_page - 1;
        if (end > pagination.total) {
            end = pagination.total;
        }
        const responseTime = window.lastResponseTime ? `<span class="text-sm">(${window.lastResponseTime}ms)</span>` : '';

        countElement.innerHTML = `Showing ${start} to ${end} of ${pagination.total} document${pagination.total !== 1 ? 's' : ''} ${responseTime}`;
    } else {
        countElement.textContent = `Found ${count} document${count !== 1 ? 's' : ''}`;
    }
}

// Update pagination controls
function updatePagination(pagination) {
    try {
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
        const primaryCategory = urlParams.get('primary_category') || '';
        const subcategory = urlParams.get('subcategory') || '';
        const filterType = urlParams.get('filter_type') || '';
        const filterYear = urlParams.get('filter_year') || '';
        const filterLocation = urlParams.get('filter_location') || '';

        // Create a document fragment for better performance
        const fragment = document.createDocumentFragment();
        const nav = document.createElement('nav');
        nav.className = 'inline-flex rounded-md shadow';

        // Previous button
        if (pagination.has_prev) {
            const prevLink = document.createElement('a');
            prevLink.href = `/search?q=${encodeURIComponent(query)}&page=${pagination.prev_page}` +
                `&per_page=${pagination.per_page}&sort_by=${sortBy}&sort_dir=${sortDir}` +
                `${primaryCategory ? '&primary_category=' + encodeURIComponent(primaryCategory) : ''}` +
                `${subcategory ? '&subcategory=' + encodeURIComponent(subcategory) : ''}` +
                `${filterType ? '&filter_type=' + encodeURIComponent(filterType) : ''}` +
                `${filterYear ? '&filter_year=' + encodeURIComponent(filterYear) : ''}` +
                `${filterLocation ? '&filter_location=' + encodeURIComponent(filterLocation) : ''}`;
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
        for (let i = 1; i <= pagination.pages; i++) {
            const isActive = i === pagination.page;
            const pageLink = document.createElement('a');
            pageLink.href = `/search?q=${encodeURIComponent(query)}&page=${i}` +
                `&per_page=${pagination.per_page}&sort_by=${sortBy}&sort_dir=${sortDir}` +
                `${primaryCategory ? '&primary_category=' + encodeURIComponent(primaryCategory) : ''}` +
                `${subcategory ? '&subcategory=' + encodeURIComponent(subcategory) : ''}` +
                `${filterType ? '&filter_type=' + encodeURIComponent(filterType) : ''}` +
                `${filterYear ? '&filter_year=' + encodeURIComponent(filterYear) : ''}` +
                `${filterLocation ? '&filter_location=' + encodeURIComponent(filterLocation) : ''}`;
            pageLink.className = `pagination-link relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium ${isActive ? 'text-indigo-600 bg-indigo-50' : 'text-gray-700 hover:bg-gray-50'}`;
            pageLink.textContent = i;
            nav.appendChild(pageLink);
        }

        // Next button
        if (pagination.has_next) {
            const nextLink = document.createElement('a');
            nextLink.href = `/search?q=${encodeURIComponent(query)}&page=${pagination.next_page}` +
                `&per_page=${pagination.per_page}&sort_by=${sortBy}&sort_dir=${sortDir}` +
                `${primaryCategory ? '&primary_category=' + encodeURIComponent(primaryCategory) : ''}` +
                `${subcategory ? '&subcategory=' + encodeURIComponent(subcategory) : ''}` +
                `${filterType ? '&filter_type=' + encodeURIComponent(filterType) : ''}` +
                `${filterYear ? '&filter_year=' + encodeURIComponent(filterYear) : ''}` +
                `${filterLocation ? '&filter_location=' + encodeURIComponent(filterLocation) : ''}`;
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
    } catch (error) {
        console.error("Error updating pagination:", error);
    }
}

// Update taxonomy facets
function updateTaxonomyFacets(facets) {
    try {
        // Primary Categories
        const primaryCategoriesContainer = document.querySelector('.facet-primary-categories');
        if (primaryCategoriesContainer && facets.primary_categories) {
            let html = '';
            facets.primary_categories.forEach(category => {
                html += `
                    <div class="facet-item ${category.selected ? 'selected' : ''}" 
                         onclick="updateTaxonomyFilter('primary_category', '${category.name}')">
                        <span>${category.name}</span>
                        <span class="text-xs text-gray-500">(${category.count})</span>
                    </div>
                `;
            });
            primaryCategoriesContainer.innerHTML = html;
        }
        
        // Subcategories
        const subcategoriesContainer = document.querySelector('.facet-subcategories');
        const subcategoriesSection = document.querySelector('.subcategories-section');
        
        if (subcategoriesContainer && facets.subcategories && facets.subcategories.length > 0) {
            let html = '';
            facets.subcategories.forEach(subcategory => {
                html += `
                    <div class="facet-item ${subcategory.selected ? 'selected' : ''}"
                         onclick="updateTaxonomyFilter('subcategory', '${subcategory.name}')">
                        <span>${subcategory.name}</span>
                        <span class="text-xs text-gray-500">(${subcategory.count})</span>
                    </div>
                `;
            });
            subcategoriesContainer.innerHTML = html;
            if (subcategoriesSection) {
                subcategoriesSection.style.display = 'block';
            }
        } else if (subcategoriesSection) {
            subcategoriesSection.style.display = 'none';
        }
        
        // Terms
        const termsContainer = document.querySelector('.facet-terms');
        const termsSection = document.querySelector('.terms-section');
        
        if (termsContainer && facets.terms && facets.terms.length > 0) {
            let html = '';
            facets.terms.forEach(term => {
                html += `
                    <div class="facet-item ${term.selected ? 'selected' : ''}"
                         onclick="updateTaxonomyFilter('specific_term', '${term.name}')">
                        <span>${term.name}</span>
                        <span class="text-xs text-gray-500">(${term.count})</span>
                    </div>
                `;
            });
            termsContainer.innerHTML = html;
            if (termsSection) {
                termsSection.style.display = 'block';
            }
        } else if (termsSection) {
            termsSection.style.display = 'none';
        }
        
        // Update clear filters button
        const clearFiltersBtn = document.querySelector('.clear-taxonomy-filters');
        if (clearFiltersBtn) {
            const urlParams = new URLSearchParams(window.location.search);
            const primaryCategory = urlParams.get('primary_category');
            const subcategory = urlParams.get('subcategory');
            const specificTerm = urlParams.get('specific_term');
            
            if (primaryCategory || subcategory || specificTerm) {
                clearFiltersBtn.style.display = 'block';
            } else {
                clearFiltersBtn.style.display = 'none';
            }
        }
    } catch (error) {
        console.error("Error updating taxonomy facets:", error);
    }
}