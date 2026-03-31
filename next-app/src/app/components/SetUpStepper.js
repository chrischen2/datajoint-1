"use client"

import * as React from 'react';
import axios from 'axios';

import Box from '@mui/material/Box';
import Stepper from '@mui/material/Stepper';
import Step from '@mui/material/Step';
import StepLabel from '@mui/material/StepLabel';
import StepContent from '@mui/material/StepContent';
import Button from '@mui/material/Button';
import Alert from '@mui/material/Alert';
import Snackbar from '@mui/material/Snackbar';
import CircularProgress from '@mui/material/CircularProgress';
import Typography from '@mui/material/Typography';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';

import SelectDatabase from './setup/SelectDatabase';
import SetUser from './setup/SetUser';
import ModeSelector from './setup/ModeSelector';
import QueryContainer from './setup/QueryContainer';
import ExperimentBrowser from './browse/ExperimentBrowser';

const steps = [
  { label: 'Connect to database', description: 'Select a running database and connect.' },
  { label: 'Choose mode & user', description: 'Select Patch or MEA and set your username.' },
  { label: 'Browse & Query', description: '' },
];

export default function SetUpStepper({ onResultsChange }) {
  const [activeStep, setActiveStep] = React.useState(0);
  const [isConnected, setIsConnected] = React.useState(false);
  const [user, setUser] = React.useState(false);
  const [mode, setMode] = React.useState('all');
  const [queryObj, setQueryObj] = React.useState(null);
  const [excludeLevels, setExcludeLevels] = React.useState([]);
  const [response, setResponse] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [open, setOpen] = React.useState(false);
  const [isLoading, setIsLoading] = React.useState(false);
  const [browseTab, setBrowseTab] = React.useState(0);

  const handleNext = () => setActiveStep(prev => Math.min(prev + 1, steps.length - 1));
  const handleBack = () => setActiveStep(prev => prev - 1);

  const handleExec = () => {
    setIsLoading(true);
    axios.post('http://localhost:3000/api/query/execute-query', {
      query_obj: queryObj,
      exclude_levels: excludeLevels
    })
      .then(res => {
        setIsLoading(false);
        if (res.data.results) {
          onResultsChange(res.data.results);
        } else {
          setResponse(res.data.message);
          setError(null);
          setOpen(true);
        }
      })
      .catch(err => {
        setIsLoading(false);
        setError(err.response?.data?.message || 'Query failed');
        setResponse(null);
        setOpen(true);
      });
  };

  return (
    <Box sx={{ maxWidth: "none", height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Stepper activeStep={activeStep} orientation="vertical" sx={{
        '& .MuiStepConnector-line': { minHeight: "2px" },
        flexShrink: 0,
      }}>
        {steps.map((step, index) => (
          <Step key={step.label}>
            <StepLabel>
              {step.label}
            </StepLabel>
            <StepContent>
              {step.description && <Typography variant="body2" color="text.secondary">{step.description}</Typography>}

              {/* Step 0: Connect */}
              {index === 0 && <SelectDatabase onConnectionStatusChange={setIsConnected} />}

              {/* Step 1: Mode + User */}
              {index === 1 && (
                <>
                  <ModeSelector mode={mode} onModeChange={setMode} />
                  <SetUser onUserSet={setUser} />
                </>
              )}

              {/* Step 2: Browse & Query */}
              {index === 2 && (
                <Box sx={{ mt: 1 }}>
                  <Tabs value={browseTab} onChange={(_, v) => setBrowseTab(v)} size="small">
                    <Tab label="Browse Experiments" />
                    <Tab label="Advanced Query" />
                  </Tabs>
                  {browseTab === 0 && (
                    <Box sx={{ height: 'calc(100vh - 350px)', mt: 1 }}>
                      <ExperimentBrowser mode={mode} />
                    </Box>
                  )}
                  {browseTab === 1 && (
                    <Box sx={{ mt: 1 }}>
                      <QueryContainer
                        onQueryObj={setQueryObj}
                        onExcludeChange={setExcludeLevels}
                      />
                      {isLoading ? (
                        <CircularProgress sx={{ mt: 1 }} />
                      ) : (
                        <Button
                          disabled={!queryObj}
                          variant="contained"
                          onClick={handleExec}
                          sx={{ mt: 1 }}
                        >
                          View Results
                        </Button>
                      )}
                    </Box>
                  )}
                </Box>
              )}

              {/* Navigation (steps 0-1 only) */}
              {index < 2 && (
                <Box sx={{ mb: 2 }}>
                  <Button
                    disabled={(index === 0 && !isConnected) || (index === 1 && !user)}
                    variant="contained"
                    onClick={handleNext}
                    sx={{ mt: 1, mr: 1 }}
                  >
                    Next
                  </Button>
                  {index > 0 && (
                    <Button onClick={handleBack} sx={{ mt: 1, mr: 1 }}>
                      Back
                    </Button>
                  )}
                </Box>
              )}
            </StepContent>
          </Step>
        ))}
      </Stepper>

      <Snackbar open={open} autoHideDuration={6000} onClose={() => setOpen(false)}>
        <Alert
          onClose={() => setOpen(false)}
          severity={error ? "error" : "success"}
          variant="filled"
          sx={{ width: '100%' }}
        >
          {error || response}
        </Alert>
      </Snackbar>
    </Box>
  );
}
