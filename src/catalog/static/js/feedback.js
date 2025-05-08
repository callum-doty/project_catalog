// src/catalog/static/js/feedback.js

document.addEventListener('DOMContentLoaded', function() {
    // Cache DOM elements
    const feedbackModal = document.getElementById('feedbackModal');
    const feedbackForm = document.getElementById('feedbackForm');
    const feedbackDocumentId = document.getElementById('feedbackDocumentId');
    const feedbackQuery = document.getElementById('feedbackQuery');
    const feedbackStatus = document.getElementById('feedbackStatus');
    const closeFeedbackModal = document.getElementById('closeFeedbackModal');
    
    // Get the current search query from URL if available
    const urlParams = new URLSearchParams(window.location.search);
    const currentQuery = urlParams.get('q') || '';
    
    // Check if the feedback elements exist
    if (!feedbackModal || !feedbackForm) {
      console.log('Feedback elements not found in the DOM');
      return; // Exit if not found
    }
    
    console.log('Feedback system initialized');
    
    // Attach event listeners to all feedback buttons using event delegation
    document.addEventListener('click', function(e) {
      const feedbackButton = e.target.closest('.feedback-btn');
      if (!feedbackButton) return;
      
      console.log('Feedback button clicked');
      
      // Get document ID from data attribute
      const documentId = feedbackButton.getAttribute('data-document-id');
      
      // Set the hidden form values
      feedbackDocumentId.value = documentId;
      feedbackQuery.value = currentQuery;
      
      // Show the modal
      feedbackModal.classList.remove('hidden');
      
      // Reset form
      feedbackForm.reset();
      feedbackStatus.classList.add('hidden');
    });
    
    // Close modal when clicking the close button
    if (closeFeedbackModal) {
      closeFeedbackModal.addEventListener('click', function() {
        feedbackModal.classList.add('hidden');
      });
    }
    
    // Close modal when clicking outside the modal content
    feedbackModal.addEventListener('click', function(e) {
      if (e.target === feedbackModal) {
        feedbackModal.classList.add('hidden');
      }
    });
    
    // Handle form submission
    feedbackForm.addEventListener('submit', function(e) {
      e.preventDefault();
      
      // Disable submit button to prevent multiple submissions
      const submitButton = feedbackForm.querySelector('button[type="submit"]');
      submitButton.disabled = true;
      submitButton.textContent = 'Submitting...';
      
      // Get form data
      const formData = new FormData(feedbackForm);
      const feedbackData = {
        document_id: parseInt(formData.get('document_id')),
        search_query: formData.get('search_query'),
        feedback_type: formData.get('feedback_type'),
        comment: formData.get('comment')
      };
      
      // Get CSRF token
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
      
      console.log('Submitting feedback:', feedbackData);
      
      // Determine the correct URL based on the current path
      // If we're on a search page, use the search prefix
      let apiUrl = '/api/search-feedback';
      if (window.location.pathname.startsWith('/search')) {
        apiUrl = '/search/api/search-feedback';
      }
      
      console.log('Using API URL:', apiUrl);
      
      // Submit feedback via AJAX
      fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrfToken || ''
        },
        body: JSON.stringify(feedbackData)
      })
      .then(response => {
        console.log('Response status:', response.status);
        if (!response.ok) {
          throw new Error(`Server error: ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        console.log('Feedback submission successful:', data);
        
        // Show success message
        feedbackStatus.textContent = 'Thank you for your feedback!';
        feedbackStatus.classList.remove('hidden', 'text-red-500');
        feedbackStatus.classList.add('text-green-500');
        
        // Close modal after a short delay
        setTimeout(() => {
          feedbackModal.classList.add('hidden');
          submitButton.disabled = false;
          submitButton.textContent = 'Submit Feedback';
        }, 1500);
      })
      .catch(error => {
        console.error('Feedback submission error:', error);
        
        // Show error message
        feedbackStatus.textContent = `Error: ${error.message}`;
        feedbackStatus.classList.remove('hidden', 'text-green-500');
        feedbackStatus.classList.add('text-red-500');
        
        // Re-enable submit button
        submitButton.disabled = false;
        submitButton.textContent = 'Submit Feedback';
      });
    });
  });