import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { RootErrorBoundary } from '@app/ErrorBoundary.root';
import { AppProviders } from '@app/router';
import '@design-system/theme/globals.css';

async function bootstrap(): Promise<void> {
  const container = document.getElementById('root');
  if (container === null) {
    throw new Error('Root element #root was not found in index.html.');
  }

  if (import.meta.env.VITE_USE_MSW === 'true') {
    const { worker } = await import('./test/msw/browser');
    await worker.start({ onUnhandledRequest: 'bypass' });
  }

  createRoot(container).render(
    <StrictMode>
      <RootErrorBoundary>
        <AppProviders />
      </RootErrorBoundary>
    </StrictMode>,
  );
}

void bootstrap();
