import React from 'react';
import { Button, ButtonGroup, Typography, Box } from '@mui/material';

export default function ModeSelector({ mode, onModeChange }) {
  return (
    <Box sx={{ my: 2 }}>
      <Typography variant="body2" sx={{ mb: 1 }}>
        Select experiment type to filter:
      </Typography>
      <ButtonGroup variant="outlined" size="large">
        <Button
          variant={mode === 'patch' ? 'contained' : 'outlined'}
          onClick={() => onModeChange('patch')}
        >
          Patch Clamp
        </Button>
        <Button
          variant={mode === 'mea' ? 'contained' : 'outlined'}
          onClick={() => onModeChange('mea')}
        >
          MEA
        </Button>
        <Button
          variant={mode === 'all' ? 'contained' : 'outlined'}
          onClick={() => onModeChange('all')}
        >
          All
        </Button>
      </ButtonGroup>
    </Box>
  );
}
