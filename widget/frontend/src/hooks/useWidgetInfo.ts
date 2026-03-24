import { useState, useEffect } from 'react';
import type { WidgetInfo } from '../types';

const DEFAULT_WIDGET_INFO: WidgetInfo = {
  title: 'Vaquill Legal AI',
  mode: 'standard',
  branding: {
    primaryColor: '#1a56db',
    logoText: 'Vaquill',
  },
  suggestedQuestions: [
    'What is Section 302 of the IPC?',
    'Explain the right to bail under CrPC.',
    'What are the grounds for divorce under the Hindu Marriage Act?',
  ],
};

export const useWidgetInfo = () => {
  const [info, setInfo] = useState<WidgetInfo>(DEFAULT_WIDGET_INFO);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchInfo = async () => {
      try {
        const response = await fetch('/api/widget/info');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data: WidgetInfo = await response.json();
        setInfo(data);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch widget info:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
        // Keep defaults on error
      } finally {
        setLoading(false);
      }
    };

    fetchInfo();
  }, []);

  return { info, loading, error };
};
