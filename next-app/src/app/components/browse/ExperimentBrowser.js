"use client"

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Box, List, ListItemButton, ListItemText, Typography,
  CircularProgress, TextField, InputAdornment
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import ExperimentTree from './ExperimentTree';

export default function ExperimentBrowser() {
  const [experiments, setExperiments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedExp, setSelectedExp] = useState(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    setLoading(true);
    setSelectedExp(null);
    axios.get('http://localhost:3000/api/browse/experiments')
      .then(res => {
        setExperiments(res.data.experiments || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const filtered = experiments.filter(exp =>
    exp.exp_name.toLowerCase().includes(search.toLowerCase()) ||
    (exp.label || '').toLowerCase().includes(search.toLowerCase()) ||
    (exp.experimenter || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <Box sx={{ display: 'flex', height: '100%', gap: 1 }}>
      {/* Left: experiment list */}
      <Box sx={{ width: 320, borderRight: '1px solid #444', overflow: 'auto', flexShrink: 0 }}>
        <Box sx={{ p: 1 }}>
          <TextField
            fullWidth size="small" placeholder="Search experiments..."
            value={search} onChange={e => setSearch(e.target.value)}
            InputProps={{
              startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>
            }}
          />
          <Typography variant="caption" sx={{ mt: 0.5, display: 'block' }}>
            {filtered.length} experiment{filtered.length !== 1 ? 's' : ''}
          </Typography>
        </Box>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}><CircularProgress /></Box>
        ) : (
          <List dense sx={{ pt: 0 }}>
            {filtered.map(exp => (
              <ListItemButton
                key={exp.id}
                selected={selectedExp?.id === exp.id}
                onClick={() => setSelectedExp(exp)}
              >
                <ListItemText
                  primary={exp.exp_name}
                  secondary={
                    <span>
                      {exp.experimenter && <span>{exp.experimenter} &middot; </span>}
                      {exp.start_time && exp.start_time !== 'None' && <span>{exp.start_time.split(' ')[0]}</span>}
                    </span>
                  }
                />
              </ListItemButton>
            ))}
          </List>
        )}
      </Box>

      {/* Right: tree view for selected experiment */}
      <Box sx={{ flex: 1, overflow: 'auto', p: 1 }}>
        {selectedExp ? (
          <ExperimentTree experimentId={selectedExp.id} experimentName={selectedExp.exp_name} />
        ) : (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
            <Typography color="text.secondary">Select an experiment to browse its tree</Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
}
