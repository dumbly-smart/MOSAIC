import { expect, test } from 'vitest';

test('test environment exposes DOM matchers', () => {
  document.body.innerHTML = '<button>Open workspace</button>';
  expect(document.querySelector('button')).toHaveTextContent('Open workspace');
});
