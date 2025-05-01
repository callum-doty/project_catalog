import React, { useState, useEffect } from 'react';
import {
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
    Typography,
    Chip,
    IconButton,
    TablePagination,
    Box,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
} from '@mui/material';
import { Edit as EditIcon } from '@mui/icons-material';
import axios from 'axios';

const ReviewQueue = () => {
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(10);
    const [selectedDoc, setSelectedDoc] = useState(null);
    const [reviewDialogOpen, setReviewDialogOpen] = useState(false);
    const [reviewNotes, setReviewNotes] = useState('');
    const [corrections, setCorrections] = useState('');

    useEffect(() => {
        fetchDocuments();
    }, [page, rowsPerPage]);

    const fetchDocuments = async () => {
        try {
            setLoading(true);
            const response = await axios.get('/api/admin/review-queue', {
                params: {
                    page: page + 1,
                    per_page: rowsPerPage,
                    sort_by: 'score',
                    sort_order: 'asc'
                }
            });
            setDocuments(response.data.data.items);
            setError(null);
        } catch (err) {
            setError('Failed to load review queue');
            console.error('Error fetching documents:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleReview = async (document) => {
        try {
            await axios.post(`/api/admin/review/${document.document_id}`, {
                reviewer_notes: reviewNotes,
                corrections_made: corrections,
                action: 'approve'
            });
            setReviewDialogOpen(false);
            fetchDocuments(); // Refresh the list
        } catch (err) {
            console.error('Error submitting review:', err);
        }
    };

    const getPriorityColor = (priority) => {
        switch (priority) {
            case 'HIGH': return 'error';
            case 'MEDIUM': return 'warning';
            case 'LOW': return 'success';
            default: return 'default';
        }
    };

    if (loading) return <Typography>Loading...</Typography>;
    if (error) return <Typography color="error">{error}</Typography>;

    return (
        <div>
            <Typography variant="h4" sx={{ mb: 3 }}>Document Review Queue</Typography>

            <TableContainer component={Paper}>
                <Table>
                    <TableHead>
                        <TableRow>
                            <TableCell>Document</TableCell>
                            <TableCell>Upload Date</TableCell>
                            <TableCell>Score</TableCell>
                            <TableCell>Priority</TableCell>
                            <TableCell>Review Reason</TableCell>
                            <TableCell>Actions</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {documents.map((doc) => (
                            <TableRow key={doc.document_id}>
                                <TableCell>{doc.filename}</TableCell>
                                <TableCell>{new Date(doc.upload_date).toLocaleDateString()}</TableCell>
                                <TableCell>{doc.scorecard.total_score}</TableCell>
                                <TableCell>
                                    <Chip
                                        label={doc.scorecard.review_priority}
                                        color={getPriorityColor(doc.scorecard.review_priority)}
                                        size="small"
                                    />
                                </TableCell>
                                <TableCell>{doc.scorecard.review_reason}</TableCell>
                                <TableCell>
                                    <IconButton
                                        onClick={() => {
                                            setSelectedDoc(doc);
                                            setReviewDialogOpen(true);
                                        }}
                                    >
                                        <EditIcon />
                                    </IconButton>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
                <TablePagination
                    component="div"
                    count={documents.length}
                    page={page}
                    onPageChange={(e, newPage) => setPage(newPage)}
                    rowsPerPage={rowsPerPage}
                    onRowsPerPageChange={(e) => {
                        setRowsPerPage(parseInt(e.target.value, 10));
                        setPage(0);
                    }}
                />
            </TableContainer>

            {/* Review Dialog */}
            <Dialog
                open={reviewDialogOpen}
                onClose={() => setReviewDialogOpen(false)}
                maxWidth="md"
                fullWidth
            >
                <DialogTitle>Review Document</DialogTitle>
                <DialogContent>
                    {selectedDoc && (
                        <Box sx={{ mt: 2 }}>
                            <Typography variant="h6">{selectedDoc.filename}</Typography>
                            <Typography color="textSecondary">
                                Uploaded: {new Date(selectedDoc.upload_date).toLocaleDateString()}
                            </Typography>

                            <Box sx={{ mt: 2 }}>
                                <Typography variant="subtitle1">Component Scores:</Typography>
                                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 1 }}>
                                    {Object.entries(selectedDoc.scorecard).map(([key, value]) => {
                                        if (typeof value === 'number') {
                                            return (
                                                <Chip
                                                    key={key}
                                                    label={`${key}: ${value}`}
                                                    color={value < 50 ? 'error' : value < 70 ? 'warning' : 'success'}
                                                />
                                            );
                                        }
                                        return null;
                                    })}
                                </Box>
                            </Box>

                            <TextField
                                fullWidth
                                multiline
                                rows={4}
                                label="Review Notes"
                                value={reviewNotes}
                                onChange={(e) => setReviewNotes(e.target.value)}
                                sx={{ mt: 2 }}
                            />

                            <TextField
                                fullWidth
                                multiline
                                rows={4}
                                label="Corrections Made"
                                value={corrections}
                                onChange={(e) => setCorrections(e.target.value)}
                                sx={{ mt: 2 }}
                            />
                        </Box>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setReviewDialogOpen(false)}>Cancel</Button>
                    <Button
                        variant="contained"
                        color="primary"
                        onClick={() => handleReview(selectedDoc)}
                    >
                        Approve
                    </Button>
                </DialogActions>
            </Dialog>
        </div>
    );
};

export default ReviewQueue; 