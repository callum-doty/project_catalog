import React, { useState, useEffect } from 'react';
import { Line, Bar, Pie } from 'react-chartjs-2';
import {
    Card,
    CardContent,
    Grid,
    Typography,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
} from '@mui/material';
import axios from 'axios';

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
            const response = await axios.get(`/api/admin/quality-metrics?days=${timeRange}`);
            setMetrics(response.data.data);
            setError(null);
        } catch (err) {
            setError('Failed to load quality metrics');
            console.error('Error fetching metrics:', err);
        } finally {
            setLoading(false);
        }
    };

    if (loading) return <Typography>Loading...</Typography>;
    if (error) return <Typography color="error">{error}</Typography>;
    if (!metrics) return null;

    // Prepare data for charts
    const scoreDistributionData = {
        labels: ['0-20', '21-40', '41-60', '61-80', '81-100'],
        datasets: [{
            label: 'Number of Documents',
            data: [10, 20, 30, 25, 15], // This should come from the API
            backgroundColor: [
                '#ff4444',
                '#ffbb33',
                '#ffeb3b',
                '#00C851',
                '#007E33'
            ]
        }]
    };

    const successRateData = {
        labels: ['Batch 1', 'Batch 2', 'Batch 3'],
        datasets: [{
            label: 'Success Rate (%)',
            data: [
                metrics.success_rates.batch1,
                metrics.success_rates.batch2,
                metrics.success_rates.batch3
            ],
            backgroundColor: [
                '#2196F3',
                '#4CAF50',
                '#FFC107'
            ]
        }]
    };

    const componentPerformanceData = {
        labels: Object.keys(metrics.component_scores),
        datasets: [{
            label: 'Average Score',
            data: Object.values(metrics.component_scores),
            backgroundColor: '#2196F3'
        }]
    };

    return (
        <div>
            <Grid container spacing={2} alignItems="center" sx={{ mb: 2 }}>
                <Grid item>
                    <Typography variant="h4">Quality Overview Dashboard</Typography>
                </Grid>
                <Grid item>
                    <FormControl sx={{ minWidth: 120 }}>
                        <InputLabel>Time Range</InputLabel>
                        <Select
                            value={timeRange}
                            onChange={(e) => setTimeRange(e.target.value)}
                            label="Time Range"
                        >
                            <MenuItem value={7}>Last 7 days</MenuItem>
                            <MenuItem value={30}>Last 30 days</MenuItem>
                            <MenuItem value={90}>Last 90 days</MenuItem>
                        </Select>
                    </FormControl>
                </Grid>
            </Grid>

            <Grid container spacing={3}>
                {/* Overview Cards */}
                <Grid item xs={12} md={4}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6">Total Documents</Typography>
                            <Typography variant="h3">{metrics.total_documents}</Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid item xs={12} md={4}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6">Average Score</Typography>
                            <Typography variant="h3">
                                {metrics.average_scores.total.toFixed(1)}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid item xs={12} md={4}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6">Documents for Review</Typography>
                            <Typography variant="h3">
                                {metrics.review_metrics.requires_review_count}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>

                {/* Charts */}
                <Grid item xs={12} md={6}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6">Score Distribution</Typography>
                            <Pie data={scoreDistributionData} />
                        </CardContent>
                    </Card>
                </Grid>
                <Grid item xs={12} md={6}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6">Batch Success Rates</Typography>
                            <Bar data={successRateData} />
                        </CardContent>
                    </Card>
                </Grid>
                <Grid item xs={12}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6">Component Performance</Typography>
                            <Bar data={componentPerformanceData} />
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>
        </div>
    );
};

export default QualityDashboard; 