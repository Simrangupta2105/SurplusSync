import React from 'react';
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import axe from 'axe-core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LoginPage } from '../pages/LoginPage';
import { RegisterPage } from '../pages/RegisterPage';
import { BusinessDashboardPage } from '../pages/business/BusinessDashboardPage';
import { BusinessInventoryPage } from '../pages/business/BusinessInventoryPage';
import { BusinessScanPage } from '../pages/business/BusinessScanPage';
import { AuthenticatedHomePage } from '../pages/AuthenticatedHomePage';

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

const runAxe = async (container: HTMLElement) => {
  return await axe.run(container, {
    runOnly: {
      type: 'tag',
      values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice'],
    },
  });
};

describe('Axe-Core Automated Accessibility Audits (WCAG 2.1 AA)', () => {
  it('Login Page: zero accessibility violations', async () => {
    const { container } = render(
      <LoginPage
        onLoginSuccess={() => {}}
        onNavigateToRegister={() => {}}
      />
    );
    const results = await runAxe(container);
    if (results.violations.length > 0) {
      console.log('Login Page Axe Violations:', JSON.stringify(results.violations, null, 2));
    }
    expect(results.violations).toEqual([]);
  });

  it('Register Page: zero accessibility violations', async () => {
    const { container } = render(
      <RegisterPage
        onRegisterSuccess={() => {}}
        onNavigateToLogin={() => {}}
        onBackToPlatform={() => {}}
      />
    );
    const results = await runAxe(container);
    if (results.violations.length > 0) {
      console.log('Register Page Axe Violations:', JSON.stringify(results.violations, null, 2));
    }
    expect(results.violations).toEqual([]);
  });

  it('Business Dashboard Page: zero accessibility violations', async () => {
    const client = createTestQueryClient();
    const { container } = render(
      <QueryClientProvider client={client}>
        <BusinessDashboardPage
          onNavigate={() => {}}
          onOpenAddBatch={() => {}}
          onOpenCreateListing={() => {}}
          onTriggerToast={() => {}}
        />
      </QueryClientProvider>
    );
    const results = await runAxe(container);
    if (results.violations.length > 0) {
      console.log('Dashboard Axe Violations:', JSON.stringify(results.violations, null, 2));
    }
    expect(results.violations).toEqual([]);
  });

  it('Business Inventory Page: zero accessibility violations', async () => {
    const client = createTestQueryClient();
    const { container } = render(
      <QueryClientProvider client={client}>
        <BusinessInventoryPage
          onTriggerToast={() => {}}
          onOpenCreateListing={() => {}}
        />
      </QueryClientProvider>
    );
    const results = await runAxe(container);
    if (results.violations.length > 0) {
      console.log('Inventory Axe Violations:', JSON.stringify(results.violations, null, 2));
    }
    expect(results.violations).toEqual([]);
  });

  it('Business Scan Page: zero accessibility violations', async () => {
    const client = createTestQueryClient();
    const { container } = render(
      <QueryClientProvider client={client}>
        <BusinessScanPage
          onTriggerToast={() => {}}
          onNavigate={() => {}}
        />
      </QueryClientProvider>
    );
    const results = await runAxe(container);
    if (results.violations.length > 0) {
      console.log('Scan Page Axe Violations:', JSON.stringify(results.violations, null, 2));
    }
    expect(results.violations).toEqual([]);
  });

  it('Authenticated Home Page: zero accessibility violations', async () => {
    const client = createTestQueryClient();
    const { container } = render(
      <QueryClientProvider client={client}>
        <AuthenticatedHomePage
          onNavigate={() => {}}
          onOpenAddBatch={() => {}}
          onOpenCreateListing={() => {}}
        />
      </QueryClientProvider>
    );
    const results = await runAxe(container);
    if (results.violations.length > 0) {
      console.log('Home Page Axe Violations:', JSON.stringify(results.violations, null, 2));
    }
    expect(results.violations).toEqual([]);
  });
});
