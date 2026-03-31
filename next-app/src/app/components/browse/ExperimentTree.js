"use client"

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Box, Typography, CircularProgress, IconButton, Collapse, Chip, Button, Tooltip
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import DownloadIcon from '@mui/icons-material/Download';
import ScienceIcon from '@mui/icons-material/Science';

const LEVEL_COLORS = {
  experiment: '#4fc3f7',
  animal: '#81c784',
  preparation: '#fff176',
  cell: '#ffb74d',
  epoch_group: '#ce93d8',
  epoch_block: '#ef5350',
  epoch: '#90a4ae',
};

function TreeNode({ node, depth = 0, onLoadData }) {
  const [expanded, setExpanded] = useState(depth < 2);
  const [epochData, setEpochData] = useState(null);
  const [loadingData, setLoadingData] = useState(false);

  const hasChildren = node.children && node.children.length > 0;
  const canLoadEpochs = node.level === 'epoch_block' && node.epoch_count > 0 && !epochData;
  const canLoadResponses = node.level === 'epoch' && !epochData;

  const handleLoadData = () => {
    setLoadingData(true);
    axios.get(`http://localhost:3000/api/browse/load-data/${node.level}/${node.id}`)
      .then(res => {
        setEpochData(res.data.data);
        setLoadingData(false);
        setExpanded(true);
        if (onLoadData) onLoadData(node, res.data.data);
      })
      .catch(() => setLoadingData(false));
  };

  return (
    <Box sx={{ ml: depth > 0 ? 2 : 0 }}>
      <Box sx={{
        display: 'flex', alignItems: 'center', py: 0.3,
        '&:hover': { bgcolor: 'rgba(255,255,255,0.05)' },
        borderRadius: 1,
      }}>
        {/* Expand/collapse toggle */}
        {(hasChildren || canLoadEpochs) ? (
          <IconButton size="small" onClick={() => setExpanded(!expanded)} sx={{ p: 0.3 }}>
            {expanded ? <ExpandMoreIcon fontSize="small" /> : <ChevronRightIcon fontSize="small" />}
          </IconButton>
        ) : (
          <Box sx={{ width: 24 }} />
        )}

        {/* Level badge */}
        <Chip
          label={node.level.replace('_', ' ')}
          size="small"
          sx={{
            bgcolor: LEVEL_COLORS[node.level] || '#666',
            color: '#000',
            fontWeight: 'bold',
            fontSize: '0.65rem',
            height: 18,
            mr: 1,
            minWidth: 70,
          }}
        />

        {/* Label */}
        <Typography variant="body2" sx={{ flexGrow: 1 }}>
          {node.label || node.exp_name || `#${node.id}`}
          {node.protocol && (
            <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
              [{node.protocol}]
            </Typography>
          )}
        </Typography>

        {/* Child count / epoch count */}
        {node.child_count > 0 && !expanded && (
          <Chip label={`${node.child_count}`} size="small" variant="outlined" sx={{ height: 18, mr: 0.5 }} />
        )}
        {canLoadEpochs && (
          <Tooltip title={`Load ${node.epoch_count} epochs`}>
            <Button
              size="small" variant="outlined" color="warning"
              startIcon={loadingData ? <CircularProgress size={12} /> : <DownloadIcon fontSize="small" />}
              onClick={handleLoadData}
              disabled={loadingData}
              sx={{ fontSize: '0.7rem', py: 0, px: 1, minWidth: 0 }}
            >
              {node.epoch_count} epochs
            </Button>
          </Tooltip>
        )}
        {canLoadResponses && (
          <Tooltip title="Load responses & stimuli">
            <Button
              size="small" variant="outlined" color="info"
              startIcon={loadingData ? <CircularProgress size={12} /> : <ScienceIcon fontSize="small" />}
              onClick={handleLoadData}
              disabled={loadingData}
              sx={{ fontSize: '0.7rem', py: 0, px: 1, minWidth: 0 }}
            >
              Load data
            </Button>
          </Tooltip>
        )}
      </Box>

      {/* Children */}
      <Collapse in={expanded}>
        {hasChildren && node.children.map(child => (
          <TreeNode key={`${child.level}-${child.id}`} node={child} depth={depth + 1} onLoadData={onLoadData} />
        ))}
        {/* On-demand loaded epochs */}
        {epochData?.epochs && epochData.epochs.map(ep => (
          <TreeNode key={`epoch-${ep.id}`} node={ep} depth={depth + 1} onLoadData={onLoadData} />
        ))}
        {/* On-demand loaded responses/stimuli */}
        {epochData?.responses && (
          <Box sx={{ ml: depth > 0 ? 4 : 2, mt: 0.5 }}>
            <Typography variant="caption" color="text.secondary">
              Responses ({epochData.responses.length}):
            </Typography>
            {epochData.responses.map(r => (
              <Box key={r.id} sx={{ ml: 2, py: 0.2 }}>
                <Typography variant="body2">
                  {r.device_name} <Typography component="span" variant="caption" color="text.secondary">{r.label}</Typography>
                </Typography>
              </Box>
            ))}
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
              Stimuli ({epochData.stimuli.length}):
            </Typography>
            {epochData.stimuli.map(s => (
              <Box key={s.id} sx={{ ml: 2, py: 0.2 }}>
                <Typography variant="body2">{s.device_name}</Typography>
              </Box>
            ))}
          </Box>
        )}
      </Collapse>
    </Box>
  );
}

export default function ExperimentTree({ experimentId, experimentName }) {
  const [tree, setTree] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setTree(null);
    axios.get(`http://localhost:3000/api/browse/tree/${experimentId}`)
      .then(res => {
        setTree(res.data.tree);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [experimentId]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!tree) {
    return <Typography color="error">Failed to load experiment tree</Typography>;
  }

  return (
    <Box>
      <Typography variant="h6" sx={{ mb: 1 }}>{experimentName}</Typography>
      <TreeNode node={tree} depth={0} />
    </Box>
  );
}
