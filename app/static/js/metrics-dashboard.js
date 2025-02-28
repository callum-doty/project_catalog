// static/js/metrics-dashboard.js

document.addEventListener('DOMContentLoaded', function() {
    // Handle time period changes
    document.getElementById('timePeriodSelect').addEventListener('change', function() {
      window.location.href = '/metrics-dashboard?days=' + this.value;
    });
  
    // Set up chart colors
    const colors = {
      blue: 'rgb(59, 130, 246)',
      lightBlue: 'rgba(59, 130, 246, 0.2)',
      green: 'rgb(16, 185, 129)',
      lightGreen: 'rgba(16, 185, 129, 0.2)',
      red: 'rgb(239, 68, 68)',
      lightRed: 'rgba(239, 68, 68, 0.2)',
      yellow: 'rgb(245, 158, 11)',
      lightYellow: 'rgba(245, 158, 11, 0.2)',
      purple: 'rgb(139, 92, 246)',
      lightPurple: 'rgba(139, 92, 246, 0.2)',
    };
  
    // Document Status Chart
    const statusChartElement = document.getElementById('documentStatusChart');
    if (statusChartElement) {
      const statusValues = JSON.parse(statusChartElement.dataset.values);
      const statusCtx = statusChartElement.getContext('2d');
      
      new Chart(statusCtx, {
        type: 'doughnut',
        data: {
          labels: ['Completed', 'Failed', 'Pending', 'Processing'],
          datasets: [{
            data: statusValues,
            backgroundColor: [
              colors.green,
              colors.red,
              colors.yellow,
              colors.blue
            ],
            borderWidth: 0
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'bottom'
            }
          }
        }
      });
    }
    
    // Daily Processing Chart
    const dailyChartElement = document.getElementById('dailyProcessingChart');
    if (dailyChartElement) {
      const dailyLabels = JSON.parse(dailyChartElement.dataset.labels);
      const dailyCompleted = JSON.parse(dailyChartElement.dataset.completed);
      const dailyFailed = JSON.parse(dailyChartElement.dataset.failed);
      const dailyTotal = JSON.parse(dailyChartElement.dataset.total);
      const dailySuccessRate = JSON.parse(dailyChartElement.dataset.successRate);
      
      const dailyCtx = dailyChartElement.getContext('2d');
      
      new Chart(dailyCtx, {
        type: 'bar',
        data: {
          labels: dailyLabels,
          datasets: [
            {
              label: 'Completed',
              data: dailyCompleted,
              backgroundColor: colors.lightGreen,
              borderColor: colors.green,
              borderWidth: 1
            },
            {
              label: 'Failed',
              data: dailyFailed,
              backgroundColor: colors.lightRed,
              borderColor: colors.red,
              borderWidth: 1
            },
            {
              label: 'Success Rate (%)',
              data: dailySuccessRate,
              type: 'line',
              borderColor: colors.purple,
              backgroundColor: 'transparent',
              borderWidth: 2,
              pointBackgroundColor: colors.purple,
              yAxisID: 'y1'
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              stacked: true,
              title: {
                display: true,
                text: 'Date'
              }
            },
            y: {
              stacked: true,
              title: {
                display: true,
                text: 'Documents'
              }
            },
            y1: {
              position: 'right',
              grid: {
                drawOnChartArea: false
              },
              ticks: {
                max: 100,
                min: 0
              },
              title: {
                display: true,
                text: 'Success Rate (%)'
              }
            }
          }
        }
      });
    }
    
    // File Type Chart
    const fileTypeChartElement = document.getElementById('fileTypeChart');
    if (fileTypeChartElement) {
      const fileTypes = JSON.parse(fileTypeChartElement.dataset.labels);
      const fileTypeCounts = JSON.parse(fileTypeChartElement.dataset.values);
      
      const fileTypeCtx = fileTypeChartElement.getContext('2d');
      
      new Chart(fileTypeCtx, {
        type: 'polarArea',
        data: {
          labels: fileTypes,
          datasets: [{
            data: fileTypeCounts,
            backgroundColor: [
              colors.lightBlue,
              colors.lightGreen,
              colors.lightRed,
              colors.lightYellow,
              colors.lightPurple
            ],
            borderColor: [
              colors.blue,
              colors.green,
              colors.red,
              colors.yellow,
              colors.purple
            ],
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false
        }
      });
    }
    
    // Confidence Scores Chart
    const confidenceChartElement = document.getElementById('confidenceChart');
    if (confidenceChartElement) {
      const confidenceScores = JSON.parse(confidenceChartElement.dataset.values);
      
      const confidenceCtx = confidenceChartElement.getContext('2d');
      
      new Chart(confidenceCtx, {
        type: 'radar',
        data: {
          labels: ['Text Extraction', 'Classification', 'LLM Analysis'],
          datasets: [{
            label: 'Confidence (%)',
            data: confidenceScores,
            fill: true,
            backgroundColor: colors.lightBlue,
            borderColor: colors.blue,
            pointBackgroundColor: colors.blue,
            pointBorderColor: '#fff',
            pointHoverBackgroundColor: '#fff',
            pointHoverBorderColor: colors.blue
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            r: {
              angleLines: {
                display: true
              },
              suggestedMin: 0,
              suggestedMax: 100
            }
          }
        }
      });
    document.querySelectorAll('.confidence-bar').forEach(bar => {
        const width = bar.dataset.width;
        bar.style.width = width + '%';
    });
    }
  });