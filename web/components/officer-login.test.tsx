import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';

import { OfficerLogin } from './officer-login';

afterEach(() => sessionStorage.clear());

test('shows rejected login without retaining a token', async () => {
  const user = userEvent.setup();
  const api = {
    login: vi.fn().mockRejectedValue(new Error('Invalid email or password')),
    getMe: vi.fn(),
  };

  render(<OfficerLogin api={api} onAuthenticated={vi.fn()} />);
  await user.type(screen.getByLabelText('Email'), 'officer@example.test');
  await user.type(screen.getByLabelText('Password'), 'incorrect');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));

  expect(await screen.findByText('Invalid email or password')).toBeVisible();
  expect(sessionStorage.getItem('mosaic.access-token')).toBeNull();
});
