import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { Root } from '@app/Root';

const container = document.getElementById('root');
if (container === null) {
  throw new Error('Root element #root was not found in index.html.');
}

createRoot(container).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
