import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import AdminLayout from './components/admin/AdminLayout';

function App() {
    return (
        <Router>
            <Routes>
                {/* Admin Routes */}
                <Route path="/admin/*" element={<AdminLayout />}>
                    <Route path="dashboard" element={<Navigate to="/admin" replace />} />
                    <Route path="" element={<Navigate to="/admin/dashboard" replace />} />
                </Route>

                {/* Default route - redirect to admin dashboard */}
                <Route path="/" element={<Navigate to="/admin/dashboard" replace />} />
            </Routes>
        </Router>
    );
}

export default App; 